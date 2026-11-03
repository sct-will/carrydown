"""Tests for scripts/release_gate.py.

1. Legacy: a project with no handling policy gets legacy(no-handling-policy) for every write class.
2. Decisions: draft, candidate, release and state-only, each with its refusals, on the sample (the "yes"
   path) and on the confidential fixture (the "no" path). A receipt, a plain dict and a caller flag are
   never a context. The gate has no bypass and reads no environment.
3. The write assertion of the specification (D2): every write outside the private workspace is preceded
   by a gate decision. The commands run against a copy of the sample that has an approved release and the
   loopback mock of GitHub. A positive control proves the recorder sees the writes.

No token and no network are used. Run from the repository root: python -m unittest discover -s tests -v
"""
import ast
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "mock"))
from sample_tree import copy_sample  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import generate_dev_skill as GD  # noqa: E402
import github_client as G  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release_fixture as F  # noqa: E402
import release_gate as RG  # noqa: E402
import release_github as RGH  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402
import scaffold_spec as SS  # noqa: E402

GATE = ROOT / "scripts" / "release_gate.py"
FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
ZERO = "0" * 64


strip_handling = F.strip_handling


class TempCase(unittest.TestCase):
    def fails(self, exc_type, call, *args, **kwargs):
        try:
            call(*args, **kwargs)
        except exc_type:
            return
        self.fail(f"{getattr(call, '__name__', call)} did not raise {exc_type.__name__}")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-gate-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)


class GateLegacyTests(TempCase):
    def test_a_project_with_no_handling_is_legacy_for_every_write_class(self):
        root = self.base / "legacy"
        copy_sample(root)
        strip_handling(root)
        self.assertEqual(RG.WRITE_CLASSES, ("draft", "candidate", "release", "state-only"))
        for write_class in RG.WRITE_CLASSES:
            with self.subTest(write_class=write_class):
                with contextlib.redirect_stderr(io.StringIO()):
                    decision = RG.check(write_class, "docs/spec/plan.yaml", ZERO, "engineering-repo", str(root))
                self.assertIsInstance(decision, RG.Decision)
                self.assertEqual(decision._fields, ("allowed", "outcome", "code", "request_id"))
                self.assertEqual((decision.allowed, decision.outcome, decision.code), (True, "legacy", "no-handling-policy"))

    def test_the_request_id_is_echoed_for_a_legacy_project(self):
        root = self.base / "legacy"
        copy_sample(root)
        strip_handling(root)
        with contextlib.redirect_stderr(io.StringIO()):
            decision = RG.check("release", "WI-01", "a" * 64, "engineering", str(root), request_id="b" * 64, event_id="c" * 64,
                                verified_context={"authenticated": True})
        self.assertEqual((decision.outcome, decision.request_id), ("legacy", "b" * 64))

    def test_the_legacy_notice_goes_to_standard_error_once(self):
        root = self.base / "legacy"
        copy_sample(root)
        strip_handling(root)
        RG._noticed.discard("legacy")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            RG.check("draft", "x", ZERO, "engineering-repo", str(root))
            RG.check("draft", "y", ZERO, "engineering-repo", str(root))
        self.assertEqual(err.getvalue().count("legacy"), 1)

    def test_an_unknown_write_class_is_a_caller_bug(self):
        self.fails(ValueError, RG.check, "anything", "x", ZERO, "d", ".")

    def test_decision_codes_and_outcomes_are_fixed_vocabularies(self):
        self.assertEqual(RG.OUTCOMES, ("legacy", "allow", "deny"))
        self.assertIn("no-handling-policy", RG.REASON_CODES)
        self.assertEqual(len(RG.REASON_CODES), 42)
        for code in ("not-approved", "drafting-is-private", "working-copy-differs", "mixed-release", "state-only-content-write",
                     "enrolled-project-missing-handling", "schema-view-mismatch"):
            self.assertIn(code, RG.REASON_CODES)

    def test_the_gate_has_no_command_line_bypass(self):
        run = subprocess.run([sys.executable, str(GATE), "--help"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotRegex(run.stdout, r"(?i)--(force|bypass|skip|ignore|no-gate|unsafe|allow)")
        for flag in ("--force", "--bypass", "--skip-gate", "--ignore-security", "--no-gate", "--authenticated"):
            with self.subTest(flag=flag):
                run = subprocess.run([sys.executable, str(GATE), flag], capture_output=True, text=True)
                self.assertEqual(run.returncode, 2)

    def test_the_gate_is_offline_and_reads_no_environment(self):
        tree = ast.parse(GATE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, {"argparse", "os", "sys", "time", "typing", "release_schema", "release_verify", "carrydown_lib"})
        source = GATE.read_text(encoding="utf-8")
        for name in ("os.environ", "getenv", "socket", "urllib", "subprocess"):
            self.assertNotIn(name, source)
        verify = (ROOT / "scripts" / "release_verify.py").read_text(encoding="utf-8")
        self.assertLessEqual({n.split(".")[0] for node in ast.walk(ast.parse(verify)) if isinstance(node, ast.Import) for n in [a.name for a in node.names]},
                             {"argparse", "calendar", "os", "re", "stat", "sys", "time", "typing", "release_schema"})


class GateDecisionTests(TempCase):
    """The decisions on the "yes" path, with a real approved release in a copy of the sample."""

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory(prefix="carrydown-gate-yes-")
        cls.yp = F.YesProject(cls.shared.name)
        cls.rid = cls.yp.release()

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        super().setUp()
        self.root = self.base / "project"
        self.ws = self.base / "workspace"
        shutil.copytree(self.yp.root, self.root)
        shutil.copytree(self.yp.workspace, self.ws)
        (self.root / ".carrydown").mkdir(exist_ok=True)
        (self.root / ".carrydown" / "local.yaml").write_text(f'workspace: "{self.ws.as_posix()}"\n', encoding="utf-8")
        os.chmod(self.ws, 0o700)

    def context(self, receipts=None):
        policy = V.local_policy({k: v for k, v in L.load_plan(self.root / "docs/spec/plan.yaml", self.root)[0]["project"]["handling"].items()
                                 if k in L.RELEASED_HANDLING_KEYS}, "sct-will/carrydown-sample")
        record = V.verify_local_request(V.load_local_evidence(str(self.ws), self.rid), self.rid)
        replay = V.local_replay(str(self.ws)).replay
        return V.authorize_content(record, replay, policy, None, receipts=receipts or {})

    def check(self, write_class, path, digest, destination="engineering-repo", **kw):
        return RG.check(write_class, path, digest, destination, str(self.root), **kw)

    def digest_of(self, rel):
        return RS.sha256_file(self.root / rel)

    def test_candidate_is_always_allowed(self):
        d = self.check("candidate", "releases/x", ZERO, "workspace")
        self.assertEqual((d.allowed, d.outcome), (True, "allow"))

    def test_a_release_write_without_a_context_is_not_approved(self):
        for ctx in (None, {"authenticated": True}, {"approved": True, "state": "active"}, True, object(), "x"):
            with self.subTest(context=repr(ctx)[:20]):
                d = self.check("release", "docs/spec/README.md", self.digest_of("docs/spec/README.md"), verified_context=ctx)
                self.assertEqual((d.allowed, d.code), (False, "not-approved"))

    def test_a_receipt_is_not_a_context(self):
        receipt = next((self.root / "docs" / "release").glob("*.receipt.json"))
        d = self.check("release", "docs/spec/README.md", self.digest_of("docs/spec/README.md"), verified_context=RS.loads_strict(receipt.read_bytes()))
        self.assertEqual(d.code, "not-approved")

    def test_a_verified_context_allows_an_approved_artifact(self):
        d = self.check("release", "docs/spec/README.md", self.digest_of("docs/spec/README.md"), verified_context=self.context(), request_id=self.rid)
        self.assertEqual((d.allowed, d.outcome, d.request_id), (True, "allow", self.rid))

    def test_a_context_cannot_be_forged_or_altered(self):
        self.fails(TypeError, V.VerifiedContext, kind="content")
        ctx = self.context()
        self.fails(AttributeError, setattr, ctx, "request_id", "x" * 64)

    def test_refusals_of_a_release_write(self):
        ctx = self.context()
        rel = "docs/spec/README.md"
        sha = self.digest_of(rel)
        cases = [
            ("a digest that is not the approved one", dict(path=rel, digest=ZERO), "sha256-mismatch"),
            ("a path the manifest does not list", dict(path="docs/spec/other.md", digest=sha), "approval-scope-mismatch"),
            ("a destination that is not approved", dict(path=rel, digest=sha, destination="board"), "destination-not-allowed"),
            ("another request id", dict(path=rel, digest=sha, request_id="f" * 64), "approval-scope-mismatch"),
        ]
        for label, spec, code in cases:
            with self.subTest(label):
                d = self.check("release", spec["path"], spec["digest"], spec.get("destination", "engineering-repo"),
                               verified_context=ctx, request_id=spec.get("request_id", self.rid))
                self.assertEqual((d.allowed, d.code), (False, code))

    def test_a_context_older_than_sixty_seconds_is_refused(self):
        ctx = self.context()
        later = V.clock() + 61
        with mock.patch.object(V, "clock", lambda: later):
            d = self.check("release", "docs/spec/README.md", self.digest_of("docs/spec/README.md"), verified_context=ctx)
        self.assertEqual(d.code, "not-approved")

    def test_an_expired_approval_is_refused(self):
        ctx = self.context()
        object.__setattr__(ctx, "expires_at", "2000-01-01T00:00:00Z")
        d = self.check("release", "docs/spec/README.md", self.digest_of("docs/spec/README.md"), verified_context=ctx)
        self.assertEqual(d.code, "expired")

    def test_a_changed_handling_policy_refuses_the_release_write(self):
        ctx = self.context()
        path = self.root / "docs/spec/plan.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("policy_version: 1", "policy_version: 2", 1), encoding="utf-8")
        d = self.check("release", "docs/spec/README.md", self.digest_of("docs/spec/README.md"), verified_context=ctx)
        self.assertEqual(d.code, "policy-revision-mismatch")

    def test_state_only_needs_its_own_context_and_names_only_receipts(self):
        ctx = self.context()
        d = self.check("state-only", "docs/release/x.receipt.json", ZERO, verified_context=ctx)
        self.assertEqual(d.code, "not-approved")           # a content context is not a state context
        d = self.check("state-only", "docs/spec/README.md", ZERO, verified_context=None)
        self.assertEqual(d.code, "not-approved")

    def test_the_gate_log_records_the_request_and_the_path_without_content(self):
        self.check("release", "docs/spec/README.md", self.digest_of("docs/spec/README.md"), verified_context=self.context(), request_id=self.rid)
        line = (self.ws / "publication" / "gate.log").read_text(encoding="utf-8").strip().splitlines()[-1]
        self.assertIn(self.rid, line)
        self.assertIn("allow release docs/spec/README.md", line)
        self.assertNotIn("Expense", line)

    def test_a_draft_write_to_an_approved_file_that_was_edited_is_refused(self):
        rel = "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        d = self.check("draft", rel, ZERO)
        self.assertEqual((d.allowed, d.outcome), (True, "allow"))       # still the approved bytes
        path = self.root / rel
        path.write_bytes(path.read_bytes() + b" ")
        d = self.check("draft", rel, ZERO)
        self.assertEqual((d.allowed, d.code), (False, "working-copy-differs"))
        self.assertEqual(self.check("draft", "docs/spec/not-released.md", ZERO).outcome, "allow")

    def test_the_working_plan_that_is_the_draft_of_the_released_plan_is_not_a_difference(self):
        self.assertEqual(self.check("draft", "docs/spec/plan.yaml", ZERO).outcome, "allow")

    def test_a_rendering_of_a_restricted_source_is_not_drafted_in_the_project(self):
        d = self.check("draft", "docs/ground-truth/x.md", ZERO, verified_context={"source_classification": "restricted"})
        self.assertEqual(d.code, "drafting-is-private")
        d = self.check("draft", "docs/ground-truth/x.md", ZERO, verified_context={"source_classification": "repo-readers"})
        self.assertTrue(d.allowed)

    def test_maintenance_class_follows_the_policy_pointer(self):
        self.assertEqual(RG.maintenance_class(self.root), "draft")
        (self.root / ".carrydown" / "release-policy.yaml").write_text("format: 1\ntooling_repository: acme/t\nenrollment_id: " + "a" * 64 + "\n", encoding="utf-8")
        self.assertEqual(RG.maintenance_class(self.root), "release")
        d = self.check("release", "docs/spec/README.md", ZERO)
        self.assertEqual(d.code, "not-approved")
        (self.root / ".carrydown" / "release-policy.yaml").write_text("format: 1\nnonsense: 2\n", encoding="utf-8")
        self.assertEqual(self.check("draft", "docs/spec/README.md", ZERO).code, "policy-pointer-mismatch")


class GateNoPathTests(TempCase):
    def setUp(self):
        super().setUp()
        self.root = self.base / "project"
        shutil.copytree(FIXTURE, self.root)

    def check(self, write_class, path, **kw):
        return RG.check(write_class, path, ZERO, "engineering-repo", str(self.root), **kw)

    def test_drafting_in_the_repository_is_private_on_the_no_path(self):
        d = self.check("draft", "docs/spec/README.md")
        self.assertEqual((d.allowed, d.outcome, d.code), (False, "deny", "drafting-is-private"))

    def test_the_pointer_and_the_ignore_file_derive_from_no_source(self):
        for path in (".carrydown/local.yaml", ".gitignore"):
            with self.subTest(path=path):
                self.assertTrue(self.check("draft", path).allowed)

    def test_candidate_writes_are_allowed_and_a_release_write_needs_a_context(self):
        self.assertTrue(self.check("candidate", "releases/x").allowed)
        self.assertEqual(self.check("release", "docs/spec/README.md").code, "not-approved")

    def test_an_enrolled_project_without_handling_is_refused(self):
        strip_handling(self.root)
        (self.root / ".carrydown").mkdir(exist_ok=True)
        (self.root / ".carrydown" / "release-policy.yaml").write_text("format: 1\ntooling_repository: acme/t\nenrollment_id: " + "a" * 64 + "\n", encoding="utf-8")
        for write_class in ("draft", "release"):
            with self.subTest(write_class=write_class):
                self.assertEqual(self.check(write_class, "docs/spec/README.md").code, "enrolled-project-missing-handling")

    def test_a_workspace_with_a_staging_repository_cannot_become_legacy(self):
        strip_handling(self.root)
        ws = self.base / "workspace"
        ws.mkdir(mode=0o700)
        (ws / "workspace.yaml").write_text("format: 1\nslug: x\nstaging_repository: acme/x-releases\n", encoding="utf-8")
        (self.root / ".carrydown").mkdir(exist_ok=True)
        (self.root / ".carrydown" / "local.yaml").write_text(f'workspace: "{ws.as_posix()}"\n', encoding="utf-8")
        self.assertEqual(self.check("draft", "docs/spec/README.md").code, "drafting-is-private")


class Recorder:
    """Records, in order, each gate decision, each file write through carrydown_lib.write_text and
    each GitHub request that changes anything."""

    def __init__(self):
        self.events = []

    def gate(self, real):
        def spy(write_class, artifact_path, content_digest, destination, root, **kwargs):
            self.events.append(("gate", write_class, str(artifact_path), str(root)))
            return real(write_class, artifact_path, content_digest, destination, root, **kwargs)
        return spy

    def file(self, real):
        def spy(path, text):
            self.events.append(("file", str(Path(path).resolve())))
            return real(path, text)
        return spy

    def github(self, real):
        def spy(client, method, url, data=None, *args, **kwargs):
            query = (data or {}).get("query", "") if isinstance(data, dict) else ""
            is_read = method == "GET" or (url.endswith("/graphql") and query.lstrip().startswith("query"))
            if not is_read:
                self.events.append(("github", method, url))
            return real(client, method, url, data, *args, **kwargs)
        return spy

    def writes(self):
        return [(i, e) for i, e in enumerate(self.events) if e[0] in ("file", "github")]


class WriteAssertionScaffold(TempCase):
    """The monkeypatched write assertion of D2. Commands that write into the engineering repository
    or to GitHub run against a copy of the sample with an approved release, and the loopback mock."""

    def setUp(self):
        super().setUp()
        self.home = self.base / "home"
        self.home.mkdir()
        mockgh.S.__init__()
        mockgh.S.repos.add("sct-will/carrydown-sample")
        mockgh.S.repo_ids["sct-will/carrydown-sample"] = 4200
        self.project = F.YesProject(self.base / "yes")
        self.root = self.project.root
        self.project.release()
        # make the commands have something to write
        (self.root / "docs/spec/README.md").unlink()
        shutil.rmtree(self.root / "docs/dev")
        self.server, self.url = mockgh.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def run_writing_commands(self):
        rec = Recorder()
        env = {"CARRYDOWN_GITHUB_TOKEN": "ghp_" + "Z" * 36, "HOME": str(self.home), "USERPROFILE": str(self.home)}
        real_send = G.GitHub._send
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, env))
            stack.enter_context(mock.patch.object(time, "sleep", lambda seconds: None))
            stack.enter_context(mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"))
            stack.enter_context(mock.patch.object(RG, "check", rec.gate(RG.check)))
            stack.enter_context(mock.patch.object(L, "write_text", rec.file(L.write_text)))
            stack.enter_context(mock.patch.object(G.GitHub, "_send", lambda c, m, u, d=None, *a, **k: rec.github(real_send)(c, m, u, d, *a, **k)))
            stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None)))
            self.statuses = {
                "scaffold": F.run(SS.main, ["--root", str(self.root), "--apply", "--allow-no-git"])[0],
                "dev skill": F.run(GD.main, ["--root", str(self.root), "--apply"])[0],
                "github_sync": F.run(GS.run, ["--root", str(self.root), "--skip-check", "--apply"])[0],
            }
        return rec

    def test_positive_control_the_recorder_sees_the_writes(self):
        rec = self.run_writing_commands()
        self.assertEqual(self.statuses, {"scaffold": 0, "dev skill": 0, "github_sync": 0}, self.statuses)
        kinds = {}
        for _, event in rec.writes():
            kinds.setdefault(event[0], []).append(event)
        files = {Path(e[1]).name for e in kinds["file"]}
        self.assertIn("README.md", files)
        self.assertIn("SKILL.md", files)
        self.assertTrue((self.root / "docs/spec/README.md").is_file())
        self.assertTrue((self.root / "docs/dev/skills/expense-approvals-dev/SKILL.md").is_file())
        issue_posts = [e for e in kinds["github"] if e[1] == "POST" and e[2].endswith("/issues")]
        self.assertGreaterEqual(len(issue_posts), 10)
        self.assertEqual(len(mockgh.S.issues), len(issue_posts))
        self.assertTrue([e for e in rec.events if e[0] == "gate"])

    def test_every_write_outside_the_workspace_is_preceded_by_a_gate_decision(self):
        """A file write needs an earlier gate call for the same path. A GitHub write needs an earlier
        release-class gate call, and there must be at least one such call for each write, because the
        approval is rechecked before each target mutation."""
        rec = self.run_writing_commands()
        writes = rec.writes()
        self.assertTrue(writes, "the commands wrote nothing, so the scaffold proves nothing")
        for index, event in writes:
            earlier = [e for e in rec.events[:index] if e[0] == "gate"]
            if event[0] == "file":
                wanted = Path(event[1])
                known = [Path(g[3], g[2]).resolve() for g in earlier]
                self.assertIn(wanted, known, f"file write without a gate decision: {wanted.name}")
            else:
                self.assertTrue([g for g in earlier if g[1] == "release"], f"GitHub write without a release gate decision: {event[1]}")
        github_writes = [e for _, e in writes if e[0] == "github"]
        all_release = [e for e in rec.events if e[0] == "gate" and e[1] == "release"]
        self.assertGreaterEqual(len(all_release), len(github_writes))


if __name__ == "__main__":
    unittest.main()
