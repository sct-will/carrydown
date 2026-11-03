"""Tests for the verifier program, its launcher, the setup check (doctor) and the staging prerequisites.

Work package 7. Offline: no token and no network. Tests marked [G3] or [G5] are the negative tests of the
specification (Part G) that WP11 collects.
"""
import hashlib
import http.client
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import fake_evidence as FE  # noqa: E402
import github_client as G  # noqa: E402
import release as R  # noqa: E402
import release_fixture as F  # noqa: E402
import release_github as RGH  # noqa: E402
import release_scan as S  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402
import workspace as W  # noqa: E402

spec = importlib.util.spec_from_file_location("verify_release", ROOT / "verifier" / "verify_release.py")
VR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VR)

TOOLING = "acme/carrydown-tooling"


def refused(call, *args, **kwargs):
    try:
        call(*args, **kwargs)
    except RS.SchemaError as e:
        return e.code
    except VR.VerifierError as e:
        return e.code
    return None


def unavailable(call, *args):
    """The message of the EvidenceUnavailable a call ends with, or None when it does not."""
    try:
        call(*args)
    except V.EvidenceUnavailable as e:
        return str(e)
    return None


def admin_attestation(world, component, subject, days=30, begin=-3600):
    now = world.reader._clock
    return {"component": component, "by_id": world.admins[0][0], "at": V.utc_text(now + begin), "expires_at": V.utc_text(now + 86400 * days),
            "subject": subject, "note": "reviewed in the tooling repository"}


def readers_subject(world):
    return {"repository_id": FE.STAGING_ID, "reader_ids": sorted(world.entry["staging_readers"]["user_ids"]),
            "service_ids": sorted(world.entry["staging_readers"].get("approved_service_ids") or [])}


class Temp(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="carrydown-setup-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)


# ---------------------------------------------------------------------------
# The program: pinned imports, policy and code checkouts
# ---------------------------------------------------------------------------

class ProgramTests(Temp):
    def test_every_module_in_use_comes_from_the_pinned_scripts_folder(self):
        self.assertIsNone(VR.pinned_import_problem())

    def test_G5_a_module_of_the_same_name_on_the_current_folder_is_never_imported(self):
        """[G5] Under python -I the current folder and PYTHONPATH are ignored, so a planted module is not run."""
        canary = self.base / "canary.txt"
        for name in ("carrydown_lib", "release_verify", "release_schema", "github_client"):
            (self.base / f"{name}.py").write_text(f"open({str(canary)!r}, 'w').write('imported')\n", encoding="utf-8")
        run = subprocess.run([sys.executable, "-I", str(ROOT / "verifier" / "verify_release.py"), "ruleset", "--kind", "staging", "--app-id", "5"],
                             cwd=str(self.base), capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(self.base)))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(canary.exists())
        self.assertEqual(json.loads(run.stdout)["rules"][3]["parameters"]["required_status_checks"][0]["integration_id"], 5)

    STDLIB = {"argparse", "base64", "calendar", "copy", "datetime", "hashlib", "json", "os", "re", "stat", "string", "subprocess", "sys", "tempfile",
              "time", "typing", "urllib", "pathlib", "http", "socket", "ssl", "errno", "io", "random", "secrets", "unicodedata", "collections"}

    def test_the_verifier_runs_with_the_standard_library_only(self):
        import ast
        paths = [ROOT / "verifier" / "verify_release.py"] + [ROOT / "scripts" / f"{m}.py" for m in
                                                            ("release_engineering", "release_scan", "release_verify", "release_github", "release_schema", "github_client", "detectors")]
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
                for name in names:
                    top = name.split(".")[0]
                    self.assertTrue(top in self.STDLIB or (ROOT / "scripts" / f"{top}.py").exists(), (path.name, top))

    def init_repo(self, name="code", extra=None):
        repo = self.base / name
        repo.mkdir()
        F.init_git(repo)
        (repo / "a.txt").write_text("a\n", encoding="utf-8")
        F.sh(["git", "add", "a.txt"], repo)
        F.sh(["git", "commit", "-q", "-m", "one"], repo)
        return repo

    def test_the_code_checkout_must_be_exactly_its_commit(self):
        repo = self.init_repo()
        sha = F.sh(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        self.assertEqual(VR.detect_code_sha(repo), sha)
        (repo / "a.txt").write_text("changed\n", encoding="utf-8")
        self.assertEqual(refused(VR.detect_code_sha, repo), "verifier-code-mismatch")
        F.sh(["git", "checkout", "--", "a.txt"], repo)
        (repo / "new.py").write_text("print(1)\n", encoding="utf-8")
        self.assertEqual(refused(VR.detect_code_sha, repo), "verifier-code-mismatch")
        self.assertEqual(refused(VR.detect_code_sha, self.base / "nowhere"), "verifier-code-mismatch")

    def world_policy(self, world):
        r = world.reader
        tip = r.branch_head(FE.TOOLING_ID, "main")
        return tip, r.file_at(FE.TOOLING_ID, tip, "enrollment.yaml")

    def test_separate_policy_and_code_checkouts_work_when_the_enrollment_pins_an_earlier_code_commit(self):
        w = FE.World()
        tip, data = self.world_policy(w)
        code = w.entry["verifier_sha"]
        self.assertNotEqual(code, tip)
        self.assertTrue(w.reader.commit_exists(FE.TOOLING_ID, code))
        report = VR.run_scan(data, tip, TOOLING, code, w.reader, FE.FakeCheckPublisher())
        self.assertTrue(report.complete)
        self.assertEqual(report.policy_commit_sha, tip)

    def test_a_code_checkout_that_is_the_policy_commit_or_that_no_enrollment_pins_is_refused(self):
        w = FE.World()
        tip, data = self.world_policy(w)
        self.assertEqual(refused(VR.run_scan, data, tip, TOOLING, tip, w.reader, FE.FakeCheckPublisher()), "verifier-code-mismatch")
        self.assertEqual(refused(VR.run_scan, data, tip, TOOLING, "1" * 40, w.reader, FE.FakeCheckPublisher()), "verifier-code-mismatch")

    def test_editing_policy_changes_the_policy_digest_and_not_the_enrollment_identity(self):
        w = FE.World()
        before = w.enrollment()
        after = w.update_policy(lambda e: e.update(offline_grace_days=3))
        self.assertEqual(before.enrollment_id, after.enrollment_id)
        self.assertNotEqual(before.policy_sha256, after.policy_sha256)

    def test_digest_self_fields_are_excluded_exactly_once(self):
        w = FE.World()
        entry = w.enrollment().entry
        self.assertEqual(V.policy_sha256_of(entry), V.policy_sha256_of(dict(entry, policy_sha256="f" * 64)))
        self.assertEqual(V.policy_sha256_of(entry), RS.sha256_bytes(RS.canonical_json({k: v for k, v in entry.items() if k != "policy_sha256"})))
        self.assertNotEqual(V.policy_sha256_of(entry), RS.sha256_bytes(RS.canonical_json(entry)), "the digest field itself is part of the input only when it is not omitted")
        c = FE.make_candidate(w)
        self.assertEqual(RS.hash_request(c.request), c.request["request_sha256"])
        self.assertEqual(RS.hash_request(dict(c.request, request_sha256="e" * 64)), c.request["request_sha256"])
        self.assertEqual(RS.hash_event(dict(c.event, event_id="e" * 64)), c.event["event_id"])

    def test_a_fake_policy_from_an_unprotected_branch_is_rejected(self):
        w = FE.World()
        r = w.reader
        tip, data = self.world_policy(w)
        forged = json.loads(data)
        forged["repositories"][0]["approvers"].append({"id": 999, "login": "outsider"})
        forged["repositories"][0]["policy_sha256"] = V.policy_sha256_of(forged["repositories"][0])
        forged_bytes = json.dumps(forged).encode()
        side = r.commit(FE.TOOLING_ID, {"enrollment.yaml": forged_bytes}, [r.repos[FE.TOOLING_ID]["branches"]["main"]], branch="evil")
        # the forged commit is not the head of the protected default branch
        self.assertEqual(refused(V.capture_enrollments, r, TOOLING, side, forged_bytes), "policy-revision-mismatch")
        # the right commit with the forged file is refused as well
        self.assertEqual(refused(V.capture_enrollments, r, TOOLING, tip, forged_bytes), "policy-revision-mismatch")
        # and a stale commit is not the head once the policy moves on
        w.update_policy(lambda e: e.update(offline_grace_days=3))
        self.assertEqual(refused(V.capture_enrollments, r, TOOLING, tip, data), "policy-revision-mismatch")

    def test_every_enrolled_repository_of_a_captured_policy_is_validated(self):
        w = FE.World()
        tip, data = self.world_policy(w)
        got = V.capture_enrollments(w.reader, TOOLING, tip, data)
        self.assertEqual([e.repository_id for e in got], [FE.ENGINEERING_ID])
        broken = json.loads(data)
        broken["repositories"][0]["verifier_app_id"] = 0
        broken["repositories"][0]["policy_sha256"] = V.policy_sha256_of(broken["repositories"][0])
        w.reader.set_file(FE.TOOLING_ID, "enrollment.yaml", json.dumps(broken).encode())
        tip2 = w.reader.branch_head(FE.TOOLING_ID, "main")
        self.assertEqual(refused(V.capture_enrollments, w.reader, TOOLING, tip2, w.reader.file_at(FE.TOOLING_ID, tip2, "enrollment.yaml")), "policy-pointer-mismatch")

    def test_a_renamed_repository_keeps_its_enrollment_and_a_replacement_with_the_old_name_does_not(self):
        w = FE.World()
        r = w.reader
        before = w.enrollment()
        r.repos[FE.ENGINEERING_ID]["full_name"] = "acme/expense-approvals-renamed"
        r.add_repo(9100, "acme/expense-approvals")          # a new repository takes the old name
        self.assertEqual(V.load_current_enrollment(FE.ENGINEERING_ID, r, TOOLING).enrollment_id, before.enrollment_id)
        self.assertEqual(refused(V.load_current_enrollment, 9100, r, TOOLING), "policy-pointer-mismatch")

    def test_a_board_with_another_node_id_or_a_broader_audience_is_refused_before_a_write(self):
        w = FE.World()
        r, enr = w.reader, w.enrollment()
        board = dict(id="board", **w.entry["allowed_targets"]["board"])
        self.assertIn("board", V.verify_targets(r, enr, [board], "repo-readers"))
        r.projects["PVT_example"]["owner_id"] = 5555
        self.assertEqual(refused(V.verify_targets, r, enr, [board], "repo-readers"), "target-identity-mismatch")
        r.projects["PVT_example"]["owner_id"] = 4400
        r.projects["PVT_example"]["reader_ids"] = r.projects["PVT_example"]["reader_ids"] + [31337]
        self.assertEqual(refused(V.verify_targets, r, enr, [board], "repo-readers"), "audience-visibility-mismatch")
        r.projects["PVT_example"]["reader_ids"] = None            # readers cannot be listed
        self.assertEqual(refused(V.verify_targets, r, enr, [board], "repo-readers"), "destination-access-not-verified")
        w.update_policy(lambda e: e["attestations"].append(admin_attestation(w, "destination-readers", {"repository_id": 4200, "owner_id": 4400, "project_id": "PVT_example"})))
        self.assertIn("board", V.verify_targets(r, w.enrollment(), [board], "repo-readers"))
        w.update_policy(lambda e: e["attestations"].__setitem__(-1, admin_attestation(w, "destination-readers", {"repository_id": 4200, "owner_id": 4400, "project_id": "PVT_other"})))
        self.assertEqual(refused(V.verify_targets, r, w.enrollment(), [board], "repo-readers"), "destination-access-not-verified")

    def test_scan_health_must_name_the_current_policy_revision(self):
        w = FE.World()
        r = w.reader
        names = lambda: {c.name: c for c in V.verify_prerequisites(r, w.enrollment(), workspace_access=True)}
        self.assertEqual(names()["scan-health"].status, V.VERIFIED)
        r.scan[FE.TOOLING_ID]["policy_commit_sha"] = "1" * 40
        self.assertEqual(names()["scan-health"].status, V.MISSING)
        r.scan[FE.TOOLING_ID]["policy_commit_sha"] = r.branch_head(FE.TOOLING_ID, "main")
        r.scan[FE.TOOLING_ID]["complete"] = False
        self.assertEqual(names()["scan-health"].status, V.MISSING)

    def test_the_command_line_names_a_fixed_code_and_never_a_token(self):
        err = subprocess.run([sys.executable, "-I", str(ROOT / "verifier" / "verify_release.py"), "scan", "--policy-file", str(self.base / "none"),
                              "--policy-commit", "a" * 40, "--code-dir", str(self.base)],
                             capture_output=True, text=True, env={k: v for k, v in os.environ.items() if not k.startswith("CARRYDOWN")})
        self.assertEqual(err.returncode, 1)
        self.assertRegex(err.stderr, r"^[a-z-]+: ")
        self.assertNotIn("ghs_", err.stdout + err.stderr)

    def test_help_prints_the_description_and_exits_zero(self):
        run = subprocess.run([sys.executable, str(ROOT / "verifier" / "verify_release.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0)
        self.assertIn("cannot modify", run.stdout)


class TokenTests(unittest.TestCase):
    def test_the_app_token_request_is_short_lived_scoped_and_signed_by_a_replaceable_signer(self):
        seen = {}

        def signer(pem, data):
            seen["data"] = data
            return b"signature"
        jwt = VR.app_jwt(77, "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----", now=1_800_000_000, sign=signer)
        header, claims, sig = jwt.split(".")
        pad = lambda s: s + "=" * (-len(s) % 4)
        import base64
        self.assertEqual(json.loads(base64.urlsafe_b64decode(pad(header))), {"alg": "RS256", "typ": "JWT"})
        body = json.loads(base64.urlsafe_b64decode(pad(claims)))
        self.assertEqual((body["iss"], body["exp"] - body["iat"]), ("77", 600))
        self.assertEqual(seen["data"], f"{header}.{claims}".encode())
        self.assertEqual(base64.urlsafe_b64decode(pad(sig)), b"signature")

    def test_the_installation_token_is_requested_for_exactly_the_enrolled_repositories_with_read_and_check_permissions(self):
        sent = []

        class App:
            def __init__(self, jwt, api):
                self.jwt = jwt

            def rest(self, method, path, data=None, ok=None):
                sent.append((method, path, data))
                if path.endswith("/installation"):
                    return {"id": 31}
                return {"token": "ghs_example"}
        token = VR.mint_installation_token("https://api.example", 77, "KEY", ["acme/carrydown-tooling", "acme/expense-approvals", "acme/expense-approvals-releases"],
                                           now=1, sign=lambda p, d: b"s", factory=App)
        self.assertEqual(token, "ghs_example")
        method, path, data = sent[-1]
        self.assertEqual((method, path), ("POST", "/app/installations/31/access_tokens"))
        self.assertEqual(data["permissions"], {"contents": "read", "pull_requests": "read", "checks": "write", "metadata": "read"})
        self.assertEqual(data["repositories"], ["carrydown-tooling", "expense-approvals", "expense-approvals-releases"])

    def test_repositories_in_more_than_one_installation_are_refused(self):
        class App:
            def __init__(self, jwt, api):
                self.n = 0

            def rest(self, method, path, data=None, ok=None):
                self.n += 1
                return {"id": self.n}
        self.assertEqual(refused(VR.mint_installation_token, "https://api.example", 77, "KEY", ["a/b", "a/c"], 1, lambda p, d: b"s", App), "setup-not-verified")

    def test_the_private_key_goes_to_a_private_file_that_is_removed(self):
        seen = {}

        def runner(args, input=None, capture_output=None, timeout=None):
            path = args[-1]
            seen["mode"] = os.stat(path).st_mode & 0o777
            seen["path"] = path
            seen["text"] = Path(path).read_text()
            return subprocess.CompletedProcess(args, 0, stdout=b"sig", stderr=b"")
        self.assertEqual(VR.openssl_sign("-----BEGIN PRIVATE KEY-----\nabc\n", b"data", runner), b"sig")
        self.assertEqual(seen["mode"], 0o600)
        self.assertFalse(os.path.exists(seen["path"]))
        self.assertFalse(os.path.exists(os.path.dirname(seen["path"])))

    def test_a_missing_credential_is_a_fixed_refusal(self):
        with mock.patch.dict(os.environ, {"CARRYDOWN_APP_ID": "", "CARRYDOWN_APP_PRIVATE_KEY": ""}):
            self.assertEqual(refused(VR._environment), "evidence-unavailable")


# ---------------------------------------------------------------------------
# The launcher, the staging workflow and the reference rulesets
# ---------------------------------------------------------------------------

class WorkflowTests(unittest.TestCase):
    LAUNCHER = (ROOT / "verifier" / "carrydown-release-verify.yml").read_text(encoding="utf-8")
    STAGING = (ROOT / "templates" / "staging" / "open-release-request.yml").read_text(encoding="utf-8")

    def code_lines(self, text):
        return [l for l in text.splitlines() if not l.lstrip().startswith("#")]

    def test_the_launcher_runs_every_five_minutes_off_the_hour_and_on_dispatch_only(self):
        body = "\n".join(self.code_lines(self.LAUNCHER))
        self.assertRegex(body, r'cron: "3-58/5 \* \* \* \*"')
        self.assertIn("workflow_dispatch:", body)
        for trigger in ("pull_request", "pull_request_target", "push:", "workflow_run", "issue_comment"):
            self.assertNotIn(trigger, body)

    def test_every_action_is_pinned_by_a_full_commit_sha(self):
        for text in (self.LAUNCHER, self.STAGING):
            for line in self.code_lines(text):
                if "uses:" in line:
                    self.assertRegex(line, r"uses:\s+[\w./-]+@[0-9a-f]{40}\b", line)

    def test_the_launcher_has_read_only_contents_and_never_persists_credentials(self):
        body = "\n".join(self.code_lines(self.LAUNCHER))
        self.assertRegex(body, r"(?m)^permissions:\n  contents: read\n")
        self.assertNotIn("write", re.search(r"(?ms)^permissions:\n(.*?)\n\S", body).group(1))
        self.assertEqual(body.count("persist-credentials: false"), body.count("actions/checkout@"))
        self.assertEqual(body.count("submodules: false"), body.count("actions/checkout@"))

    def test_the_credentials_appear_only_in_the_scan_step_and_the_policy_and_code_are_separate_folders(self):
        body = "\n".join(self.code_lines(self.LAUNCHER))
        self.assertEqual(body.count("secrets."), 2)
        scan_step = body[body.index("Scan every open pull request"):]
        self.assertEqual(scan_step.count("secrets."), 2)
        self.assertIn("path: policy", body)
        self.assertIn("path: code", body)
        self.assertIn("ref: ${{ matrix.code_commit }}", body)
        self.assertIn("python3 -I -B code/verifier/verify_release.py scan", body)
        self.assertNotIn("run: |\n          pip", body)

    def test_the_launcher_serializes_runs_and_never_checks_out_an_engineering_repository(self):
        body = "\n".join(self.code_lines(self.LAUNCHER))
        self.assertIn("group: carrydown-release-verify", body)
        self.assertIn("cancel-in-progress: false", body)
        self.assertNotIn("repository:", body, "no checkout names another repository")

    def test_the_staging_workflow_is_the_narrow_request_opener_the_specification_describes(self):
        body = "\n".join(self.code_lines(self.STAGING))
        self.assertRegex(body, r"(?m)^permissions:\n  contents: read\n  pull-requests: write\n")
        self.assertIn("schedule:", body)
        self.assertIn("workflow_dispatch:", body)
        for forbidden in ("pull_request_target", "actions/checkout", "uses:", "secrets.", "push:", "workflow_run", "issues: write", "contents: write"):
            self.assertNotIn(forbidden, body)
        self.assertIn("matching-refs/heads/request/", body)
        self.assertIn("matching-refs/heads/state/", body)
        self.assertIn("^(request|state)/[0-9a-f]{64}$", body)

    def test_the_installed_workflow_digest_is_the_one_the_doctor_compares(self):
        digest = hashlib.sha256((ROOT / "templates" / "staging" / "open-release-request.yml").read_bytes()).hexdigest()
        w = FE.World()
        w.reader.set_file(FE.STAGING_ID, V.WORKFLOW_PATH, self.STAGING.encode())
        w.update_policy(lambda e: e.update(staging_workflow_sha256=digest))
        by = {c.name: c for c in V.verify_prerequisites(w.reader, w.enrollment())}
        self.assertEqual(by["staging-workflow"].status, V.VERIFIED)


class RulesetTests(unittest.TestCase):
    def load(self, name, app_id):
        data = json.loads((ROOT / "verifier" / name).read_text(encoding="utf-8"))
        for rule in data["rules"]:
            if rule["type"] == "required_status_checks":
                for check in rule["parameters"]["required_status_checks"]:
                    check["integration_id"] = app_id
        return data

    def test_the_staging_reference_ruleset_encodes_the_review_rules_with_last_pusher_approval_off(self):
        data = self.load("ruleset-staging.json", 77)
        self.assertIsNone(V.staging_ruleset_problem([data], 77))
        pull = next(r for r in data["rules"] if r["type"] == "pull_request")["parameters"]
        self.assertIs(pull["require_last_push_approval"], False)
        self.assertEqual(pull["allowed_merge_methods"], ["merge"])
        self.assertEqual(data["bypass_actors"], [])

    def test_the_engineering_reference_ruleset_requires_the_release_check_from_the_app(self):
        data = self.load("ruleset-engineering.json", 77)
        self.assertIsNone(V.engineering_ruleset_problem([data], 77))
        self.assertEqual(data["bypass_actors"], [])

    def test_the_placeholder_integration_id_is_not_accepted_until_it_is_replaced(self):
        for name, check in (("ruleset-staging.json", V.staging_ruleset_problem), ("ruleset-engineering.json", V.engineering_ruleset_problem)):
            raw = json.loads((ROOT / "verifier" / name).read_text(encoding="utf-8"))
            self.assertIn("integration", check([raw], 77))

    def test_a_check_of_the_right_name_from_another_app_is_not_enough(self):
        self.assertIn("verifier App", V.staging_ruleset_problem([self.load("ruleset-staging.json", 5)], 77))
        self.assertIn("verifier App", V.engineering_ruleset_problem([self.load("ruleset-engineering.json", 5)], 77))

    def test_both_protected_branches_require_the_checks_from_the_expected_installation(self):
        w = FE.World()
        by = {c.name: c for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}
        self.assertEqual((by["staging-ruleset"].status, by["engineering-ruleset"].status), (V.VERIFIED, V.VERIFIED))
        w.reader.rulesets_by_repo[FE.ENGINEERING_ID] = [FE.engineering_ruleset(integration=5)]
        w.reader.rulesets_by_repo[FE.STAGING_ID] = [FE.staging_ruleset(integration=5)]
        by = {c.name: c for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}
        self.assertEqual((by["staging-ruleset"].status, by["engineering-ruleset"].status), (V.MISSING, V.MISSING))
        self.assertIn("integration id 77", by["engineering-ruleset"].evidence)

    def test_force_pushes_deletions_and_bypass_on_the_engineering_branch_are_reported(self):
        w = FE.World()
        for kwargs in ({"bypass": True}, {"no_force": False}, {"no_delete": False}):
            w.reader.rulesets_by_repo[FE.ENGINEERING_ID] = [FE.engineering_ruleset(**kwargs)]
            by = {c.name: c for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}
            self.assertEqual(by["engineering-ruleset"].status, V.MISSING, kwargs)

    def test_the_staging_reference_matches_the_template_the_owner_installs_except_for_the_integration_id(self):
        a = json.loads((ROOT / "verifier" / "ruleset-staging.json").read_text(encoding="utf-8"))
        b = json.loads((ROOT / "templates" / "staging" / "ruleset.json").read_text(encoding="utf-8"))
        for data in (a, b):
            for rule in data["rules"]:
                if rule["type"] == "required_status_checks":
                    for check in rule["parameters"]["required_status_checks"]:
                        check.pop("integration_id", None)
        self.assertEqual(a, b)

    def test_the_enrollment_reference_example_is_a_valid_entry(self):
        text = (ROOT / "verifier" / "enrollment.schema.md").read_text(encoding="utf-8")
        block = re.search(r"## Example.*?```yaml\n(.*?)```", text, re.S).group(1)
        doc = L.loads(block)
        entry = doc["repositories"][0]
        V._check_current(V._check_entry(entry, doc["host"], doc["tooling_repository_id"], entry["repository_id"]))
        digest = hashlib.sha256((ROOT / "templates" / "staging" / "open-release-request.yml").read_bytes()).hexdigest()
        self.assertEqual(entry["staging_workflow_sha256"], digest)
        for line in re.findall(r"(?m)^\s*(?:- )?verifier_sha: (.*)$", block):
            self.assertRegex(line, r"^[0-9a-f]{40}$")


# ---------------------------------------------------------------------------
# The reader and the publisher over the real client
# ---------------------------------------------------------------------------

class Scripted(G.GitHub):
    """The real client with the transport replaced: GET lists are served 100 rows per page with a Link
    header, exactly as GitHub does, and an exception can be scripted for any path."""

    def __init__(self, routes):
        super().__init__("ghs_example", api="https://api.example")
        self.routes = routes
        self.seen = []

    def _send(self, method, url, data=None, ok=(200, 201, 202, 204), retries=4, safe=None):
        path = url.replace(self.api, "")
        base, _, query = path.partition("?")
        self.seen.append((method, base))
        route = self.routes.get((method, base))
        if isinstance(route, Exception):
            raise route
        if callable(route):
            return route(data)
        if isinstance(route, dict) and "rows" in route:
            page = int(re.search(r"(?:^|&)page=(\d+)", query).group(1))
            rows = route["rows"]
            chunk = rows[(page - 1) * 100: page * 100]
            body = {route["key"]: chunk} if route.get("key") else chunk
            link = f'<{self.api}{base}?page={page + 1}>; rel="next"' if page * 100 < len(rows) else None
            return 200, body, {"Link": link} if link else {}
        return 200, route, {}


def pr_row(n):
    return {"number": n, "state": "open", "merged_at": None, "head": {"sha": f"{n:040x}", "ref": f"b{n}", "repo": {"id": 4200}},
            "base": {"ref": "main", "sha": "0" * 40}, "user": {"id": 1, "login": "u"}}


class ReaderTests(unittest.TestCase):
    def reader(self, routes):
        routes[("GET", "/repositories/4200")] = {"id": 4200, "full_name": "acme/expense-approvals", "private": True, "visibility": "private", "default_branch": "main"}
        return RGH.GitHubEvidenceReader(Scripted(routes), host="github.com")

    def test_every_listing_follows_the_pages_beyond_the_first(self):
        routes = {("GET", "/repos/acme/expense-approvals/pulls"): {"rows": [pr_row(n) for n in range(1, 251)]},
                  ("GET", "/repos/acme/expense-approvals/pulls/7/reviews"): {"rows": [{"id": n, "user": {"id": n, "login": "x"}, "state": "APPROVED", "commit_id": "a", "submitted_at": "2027-01-01T00:00:00Z"} for n in range(1, 131)]},
                  ("GET", "/repos/acme/expense-approvals/pulls/7/files"): {"rows": [{"filename": f"f{n}", "status": "added", "sha": "a"} for n in range(1, 301)]}}
        r = self.reader(routes)
        self.assertEqual(len(r.pull_requests(4200, "main", "open")), 250)
        self.assertEqual(len(r.reviews(4200, 7)), 130)
        files = r.pull_request_files(4200, 7)
        self.assertEqual(len(files), 300)
        self.assertIn("previous_filename", files[0])

    def test_a_listing_at_the_documented_ceiling_is_truncated_and_refuses(self):
        routes = {("GET", "/repos/acme/expense-approvals/pulls/7/files"): {"rows": [{"filename": f"f{n}", "status": "added", "sha": "a"} for n in range(RGH.MAX_FILES)]},
                  ("GET", "/repos/acme/expense-approvals/pulls/7/commits"): {"rows": [{"sha": f"{n:040x}"} for n in range(RGH.MAX_COMMITS)]}}
        r = self.reader(routes)
        self.assertIn("truncated", unavailable(r.pull_request_files, 4200, 7))
        self.assertIn("truncated", unavailable(r.commits, 4200, 7))

    def test_a_truncated_tree_refuses(self):
        r = self.reader({("GET", "/repos/acme/expense-approvals/git/trees/abc"): {"truncated": True, "tree": []}})
        self.assertIn("truncated", unavailable(r.tree, 4200, "abc"))

    def test_rate_limit_exhaustion_is_evidence_unavailable_without_a_locator(self):
        limit = G.GitHubError("GET /repos/acme/secret-name/pulls -> 403: rate limit", 403, "rate_limit", "wait")
        r = self.reader({("GET", "/repos/acme/expense-approvals/pulls"): limit})
        message = unavailable(r.pull_requests, 4200, "main", "open")
        self.assertIsNotNone(message)
        self.assertNotIn("secret-name", message)
        self.assertNotIn("403", message)

    def test_an_engineering_scan_with_a_rate_limited_listing_is_incomplete(self):
        w = FE.World()
        w.reader.fail("pull_requests", FE.ENGINEERING_ID)
        tip = w.reader.branch_head(FE.TOOLING_ID, "main")
        enrollments = V.capture_enrollments(w.reader, TOOLING, tip, w.reader.file_at(FE.TOOLING_ID, tip, "enrollment.yaml"))
        report = S.scan(w.reader, FE.FakeCheckPublisher(), enrollments)
        self.assertFalse(report.complete)

    def test_the_check_publisher_moves_an_existing_run_back_to_in_progress_and_posts_only_while_newest(self):
        runs = [{"id": 5, "app": {"id": 77}}]
        patches = []

        def patch(data):
            patches.append(data)
            return 200, {"id": 5}, {}
        routes = {("GET", "/repositories/4200"): {"id": 4200, "full_name": "acme/expense-approvals"},
                  ("GET", f"/repos/acme/expense-approvals/commits/{'a' * 40}/check-runs"): lambda d: (200, {"check_runs": runs}, {}),
                  ("PATCH", "/repos/acme/expense-approvals/check-runs/5"): patch}
        pub = RGH.GitHubCheckPublisher(Scripted(routes), 77, clock=lambda: 1_800_000_000)
        self.assertEqual(pub.start(4200, "a" * 40, V.ENGINEERING_CHECK), 5)
        self.assertEqual(patches[0]["status"], "in_progress")
        self.assertTrue(pub.finish(4200, "a" * 40, V.ENGINEERING_CHECK, 5, "failure", "carrydown: withdrawn", "withdrawn"))
        self.assertEqual((patches[1]["status"], patches[1]["conclusion"]), ("completed", "failure"))
        runs.append({"id": 9, "app": {"id": 77}})        # a newer run now exists
        self.assertFalse(pub.finish(4200, "a" * 40, V.ENGINEERING_CHECK, 5, "success", "carrydown: release verified", "ok"))
        self.assertEqual(len(patches), 2)

    def test_the_check_publisher_creates_a_run_when_none_exists_and_ignores_other_apps(self):
        created = []

        def post(data):
            created.append(data)
            return 201, {"id": 12}, {}
        runs = [{"id": 40, "app": {"id": 999}}]
        routes = {("GET", "/repositories/4200"): {"id": 4200, "full_name": "acme/expense-approvals"},
                  ("GET", f"/repos/acme/expense-approvals/commits/{'b' * 40}/check-runs"): lambda d: (200, {"check_runs": runs}, {}),
                  ("POST", "/repos/acme/expense-approvals/check-runs"): post}
        pub = RGH.GitHubCheckPublisher(Scripted(routes), 77, clock=lambda: 1_800_000_000)
        self.assertEqual(pub.start(4200, "b" * 40, V.ENGINEERING_CHECK), 12)
        self.assertEqual((created[0]["name"], created[0]["head_sha"], created[0]["status"]), (V.ENGINEERING_CHECK, "b" * 40, "in_progress"))

    def test_a_failed_check_request_is_evidence_unavailable(self):
        bad = G.GitHubError("POST /x -> 500", 500, "server", "")
        routes = {("GET", "/repositories/4200"): {"id": 4200, "full_name": "acme/expense-approvals"},
                  ("GET", f"/repos/acme/expense-approvals/commits/{'c' * 40}/check-runs"): lambda d: (200, {"check_runs": []}, {}),
                  ("POST", "/repos/acme/expense-approvals/check-runs"): bad}
        pub = RGH.GitHubCheckPublisher(Scripted(routes), 77)
        self.assertIsNotNone(unavailable(pub.start, 4200, "c" * 40, V.ENGINEERING_CHECK))

    def test_secret_names_are_listed_without_values_and_a_denied_token_is_unavailable(self):
        r = self.reader({("GET", "/repos/acme/expense-approvals/actions/secrets"): {"total_count": 2, "secrets": [{"name": "A"}, {"name": "B"}]}})
        self.assertEqual(r.secret_names(4200), ["A", "B"])
        denied = G.GitHubError("GET /x -> 403", 403, "forbidden", "")
        r = self.reader({("GET", "/repos/acme/expense-approvals/actions/secrets"): denied})
        self.assertIsNotNone(unavailable(r.secret_names, 4200))


# ---------------------------------------------------------------------------
# Prerequisites: the first staging upload (D14)
# ---------------------------------------------------------------------------

class UploadTests(Temp):
    def project(self, mutate=None):
        world = FE.World()
        if mutate:
            mutate(world)
        folder = self.base / f"p{len(list(self.base.iterdir()))}"
        folder.mkdir()
        np = F.NoProject(folder, world=world).start()
        self.addCleanup(np.stop)
        code, out, err = np.prepare()
        self.assertEqual(code, 0, out + err)
        return np

    def branches(self, np):
        run = F.sh(["git", "ls-remote", "--heads", str(np.staging)], self.base)
        return [line.split("\t")[1] for line in run.stdout.splitlines()]

    def refuse_upload(self, np):
        code, out, err = np.approve()
        self.assertEqual(code, 1, out + err)
        self.assertIn("staging-access-not-verified", err)
        self.assertEqual(self.branches(np), ["refs/heads/main"], "nothing was pushed")
        self.assertEqual(np.dispatches, [], "no workflow was dispatched")
        for method, repo in np.reader.calls:
            self.assertNotIn(method, ("push", "create", "post", "write", "merge"))

    def test_G3_an_unauthorized_direct_collaborator_prevents_the_first_upload(self):
        """[G3]"""
        np = self.project()
        np.reader.collaborators_by_repo[FE.STAGING_ID].append({"id": 999, "login": "outsider", "permission": "read"})
        self.refuse_upload(np)

    def test_G3_an_inherited_team_reader_prevents_the_first_upload(self):
        """[G3]"""
        np = self.project()
        np.reader.teams_by_repo[FE.STAGING_ID] = [{"id": 1, "slug": "all-engineers", "permission": "pull"}]
        self.refuse_upload(np)

    def test_G3_an_unexpected_app_or_deploy_key_prevents_the_first_upload(self):
        """[G3]"""
        np = self.project()
        np.reader.installations_by_repo[FE.STAGING_ID] = [{"id": 3, "slug": "some-other-app"}]
        self.refuse_upload(np)
        np.reader.installations_by_repo[FE.STAGING_ID] = []
        np.reader.deploy_keys_by_repo[FE.STAGING_ID] = [{"id": 8, "read_only": True}]
        self.refuse_upload(np)

    def test_G3_an_unreadable_access_list_with_no_attestation_prevents_the_first_upload(self):
        """[G3]"""
        np = self.project()
        np.reader.fail("collaborators", FE.STAGING_ID)
        self.refuse_upload(np)

    def test_G3_an_expired_attestation_prevents_the_first_upload(self):
        """[G3]"""
        def expired(world):
            world.update_policy(lambda e: e["attestations"].append(admin_attestation(world, "staging-readers", readers_subject(world), days=-1, begin=-86400 * 3)))
        np = self.project(expired)
        np.reader.fail("collaborators", FE.STAGING_ID)
        self.refuse_upload(np)

    def test_G3_an_attestation_by_someone_who_is_not_an_administrator_does_not_count(self):
        """[G3]"""
        def forged(world):
            att = admin_attestation(world, "staging-readers", readers_subject(world))
            att["by_id"] = FE.OUTSIDER[0]
            world.update_policy(lambda e: e["attestations"].append(att))
        np = self.project(forged)
        np.reader.fail("collaborators", FE.STAGING_ID)
        self.refuse_upload(np)

    def test_a_current_scoped_attestation_covers_an_unreadable_list_and_the_upload_proceeds(self):
        def attest(world):
            world.update_policy(lambda e: e["attestations"].append(admin_attestation(world, "staging-readers", readers_subject(world))))
        np = self.project(attest)
        np.reader.fail("collaborators", FE.STAGING_ID)
        np.reader.fail("installations", FE.STAGING_ID)
        code, out, err = np.approve()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.branches(np), ["refs/heads/main", f"refs/heads/request/{np.request_id}"])

    def test_approved_service_readers_pass(self):
        def services(world):
            world.update_policy(lambda e: e["staging_readers"].update(approved_service_ids=["carrydown-app-installation"]))
            world.reader.installations_by_repo[FE.STAGING_ID] = [{"id": 3, "slug": "carrydown-app-installation"}]
        np = self.project(services)
        code, out, err = np.approve()
        self.assertEqual(code, 0, out + err)

    def test_changing_a_known_reader_set_invalidates_its_attestation(self):
        w = FE.World()
        w.update_policy(lambda e: e["attestations"].append(admin_attestation(w, "staging-readers", readers_subject(w))))
        w.reader.fail("collaborators", FE.STAGING_ID)
        by = lambda: {c.name: c for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}
        self.assertEqual(by()["staging-readers"].status, V.VERIFIED)
        w.reader.users[777] = {"id": 777, "login": "new-reader"}
        w.update_policy(lambda e: e["staging_readers"]["user_ids"].append(777))
        self.assertEqual(by()["staging-readers"].status, V.NOT_VERIFIABLE)

    def test_an_attestation_never_substitutes_for_a_live_problem(self):
        w = FE.World()
        w.update_policy(lambda e: e["attestations"].append(admin_attestation(w, "staging-readers", readers_subject(w))))
        w.reader.collaborators_by_repo[FE.STAGING_ID].append({"id": 999, "login": "outsider", "permission": "read"})
        by = {c.name: c for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}
        self.assertEqual(by["staging-readers"].status, V.MISSING)


# ---------------------------------------------------------------------------
# The doctor
# ---------------------------------------------------------------------------

class NoNetwork:
    """Any attempt to open a connection fails the test."""

    def __enter__(self):
        def boom(*a, **k):
            raise AssertionError("the offline doctor tried to use the network")
        self.patches = [mock.patch.object(socket.socket, "connect", boom), mock.patch.object(socket, "create_connection", boom),
                        mock.patch.object(urllib.request, "urlopen", boom), mock.patch.object(http.client.HTTPConnection, "connect", boom),
                        mock.patch.object(G, "_urlopen", boom)]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


class DoctorTests(Temp):
    def no_project(self, mutate=None):
        world = FE.World()
        if mutate:
            mutate(world)
        folder = self.base / f"d{len(list(self.base.iterdir()))}"
        folder.mkdir()
        np = F.NoProject(folder, world=world).start()
        self.addCleanup(np.stop)
        return np

    def doctor(self, np, token=True):
        argv = ["doctor", "--root", str(np.root)]
        with mock.patch.object(R, "token_available", lambda args: token):
            return F.run(R.main, argv)

    def component_lines(self, out):
        rows = {}
        for line in out.splitlines():
            m = re.match(r"  (verified|not verifiable|missing)\s+([a-z-]+): (.*)", line)
            if m:
                rows[m.group(2)] = (m.group(1), m.group(3))
        return rows

    def test_offline_doctor_makes_no_network_call_and_labels_every_remote_component_not_verifiable(self):
        np = self.no_project()
        with NoNetwork():
            code, out, err = F.run(W.main, ["doctor", "--root", str(np.root)])
        for name in W.REMOTE_COMPONENTS:
            self.assertRegex(out, rf"info\s+{name}\s+not verifiable offline", name)
        self.assertNotIn("verified ", out.replace("not verifiable", ""))
        self.assertIn("permissions", out)

    def test_the_offline_remote_list_matches_the_components_the_live_check_reads(self):
        self.assertEqual(set(W.REMOTE_COMPONENTS), (set(V.EXPORT_COMPONENTS) - {"workspace-access"}) | {"destinations"})

    def test_offline_doctor_on_the_yes_path_says_no_remote_component_applies(self):
        yp = F.YesProject(self.base)
        with NoNetwork():
            code, out, err = F.run(W.main, ["doctor", "--root", str(yp.root)])
        self.assertIn("none apply", out)

    def test_a_healthy_organization_verifies_every_component_and_allows_upload_and_export(self):
        np = self.no_project()
        code, out, err = self.doctor(np)
        rows = self.component_lines(out)
        self.assertEqual({n for n, (s, e) in rows.items() if s != "verified"}, set(), out)
        self.assertIn("private upload to the staging repository: allowed", out)
        self.assertIn("export and publication: allowed", out)
        self.assertIn("does not expire an old GitHub success", out)

    def test_a_non_verifiable_configuration_component_with_no_attestation_blocks_upload_and_export(self):
        np = self.no_project()
        np.reader.fail("collaborators", FE.STAGING_ID)
        code, out, err = self.doctor(np)
        self.assertEqual(code, 1, out)
        self.assertEqual(self.component_lines(out)["staging-readers"][0], "not verifiable")
        self.assertIn("private upload to the staging repository: blocked until verified: staging-readers", out)
        self.assertIn("blocked until verified: staging-readers", out.split("export and publication:")[1])
        self.assertIn("attestation named staging-readers", out)

    def test_an_engineering_ruleset_that_cannot_be_read_blocks_export_but_not_the_upload(self):
        np = self.no_project()
        np.reader.fail("rulesets", FE.ENGINEERING_ID)
        code, out, err = self.doctor(np)
        self.assertEqual(code, 1)
        self.assertIn("private upload to the staging repository: allowed", out)
        self.assertIn("export and publication: blocked until verified: engineering-ruleset", out)

    def test_a_valid_scoped_attestation_satisfies_only_that_component(self):
        def attest(world):
            world.update_policy(lambda e: e["attestations"].append(admin_attestation(world, "ruleset-coverage", {"repository_id": FE.ENGINEERING_ID, "integration_id": FE.APP_ID})))
        np = self.no_project(attest)
        np.reader.fail("rulesets", FE.ENGINEERING_ID)
        np.reader.fail("collaborators", FE.STAGING_ID)
        code, out, err = self.doctor(np)
        rows = self.component_lines(out)
        self.assertEqual(rows["engineering-ruleset"][0], "verified")
        self.assertEqual(rows["staging-readers"][0], "not verifiable", "the other component is not helped by an attestation for this one")
        self.assertEqual(code, 1)

    def test_an_attestation_for_another_integration_does_not_satisfy_the_ruleset_component(self):
        def attest(world):
            world.update_policy(lambda e: e["attestations"].append(admin_attestation(world, "ruleset-coverage", {"repository_id": FE.ENGINEERING_ID, "integration_id": 5})))
        np = self.no_project(attest)
        np.reader.fail("rulesets", FE.ENGINEERING_ID)
        code, out, err = self.doctor(np)
        self.assertEqual(self.component_lines(out)["engineering-ruleset"][0], "not verifiable")

    def test_expired_runtime_evidence_and_stale_scan_health_still_block(self):
        def expire(world):
            world.update_policy(lambda e: [a.update(expires_at=V.utc_text(world.reader._clock - 60)) for a in e["attestations"]])
        np = self.no_project(expire)
        code, out, err = self.doctor(np)
        self.assertEqual(self.component_lines(out)["runtime-isolation"][0], "missing")
        self.assertIn("private upload to the staging repository: allowed", out)
        self.assertIn("export and publication: blocked until verified: runtime-isolation", out)
        np = self.no_project()
        np.reader.scan[FE.TOOLING_ID]["completed_at"] = V.utc_text(V.clock() - 5000)
        code, out, err = self.doctor(np)
        self.assertEqual(self.component_lines(out)["scan-health"][0], "missing")
        self.assertIn("blocked until verified: scan-health", out)
        self.assertEqual(code, 1)

    def test_a_last_pusher_approval_requirement_is_reported_without_telling_the_owner_to_find_another_account(self):
        np = self.no_project()
        np.reader.rulesets_by_repo[FE.STAGING_ID] = [FE.staging_ruleset(last_push=True)]
        code, out, err = self.doctor(np)
        evidence = self.component_lines(out)["staging-ruleset"][1]
        self.assertIn("require_last_push_approval", evidence)
        self.assertIn("Turn it off", evidence)
        self.assertNotIn("another account", out.lower())
        self.assertNotIn("second reviewer", out.lower())

    def test_without_a_token_every_remote_component_is_not_verifiable_and_the_no_path_is_blocked(self):
        np = self.no_project()
        code, out, err = self.doctor(np, token=False)
        self.assertEqual(code, 1)
        self.assertIn("no token", out)
        self.assertIn("private upload to the staging repository: blocked", out)

    def test_the_yes_path_remote_checks_are_informational(self):
        yp = F.YesProject(self.base)
        code, out, err = F.run(R.main, ["doctor", "--root", str(yp.root)])
        self.assertIn("The \"yes\" path needs none", out)
        self.assertNotIn("blocked", out)

    def test_the_doctor_prints_ids_and_codes_but_no_token_or_private_value(self):
        np = self.no_project()
        code, out, err = self.doctor(np)
        for private in ("Tamsin", "ghs_", "ghp_", "BEGIN"):
            self.assertNotIn(private, out + err)

    def test_the_destinations_are_checked_against_the_enrollment(self):
        np = self.no_project()
        np.reader.projects["PVT_example"]["owner_id"] = 5
        code, out, err = self.doctor(np)
        self.assertEqual(self.component_lines(out)["destinations"][0], "missing")


if __name__ == "__main__":
    unittest.main()
