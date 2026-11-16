"""Tests for tests/acceptance/live_github_run.py, the runner of the acceptance run on real GitHub.

No token and no network. A fake gh executable (tests/acceptance/fake_gh.py) sits first on PATH. It models a small
organization, answers canned JSON and logs every argument array it receives, so the tests can assert what the
runner called and that it called nothing that writes in a dry run.

Every call to a fake executable costs a process start, so the organization after steps S1 to S5 is built once per
test run (snapshot) and the tests that need it start from a copy.

Run from the repository root:
  python3 -m unittest tests.acceptance.test_live_runner -v
"""
import atexit
import base64
import contextlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))
import live_github_run as live  # noqa: E402
import carrydown_lib as L  # noqa: E402

ORG = "acme-throwaway"
TOKEN_SHAPE = re.compile(r"gh[pos]_[A-Za-z0-9]{20,}|github_pat_")
APP = {"id": 900, "app_id": 555, "app_slug": "carrydown-verifier-acme-throwaway", "repository_selection": "selected",
       "permissions": {"contents": "read", "pull_requests": "read", "checks": "write", "metadata": "read"}}


def read_only(args):
    """An independent statement of what counts as a read: api with GET or no method flag and no body, auth status, repo view."""
    if args[:2] in (["auth", "status"], ["repo", "view"]):
        return True
    if not args or args[0] != "api":
        return False
    flags = args[1:]
    if any(f in ("-f", "-F", "--field", "--raw-field", "--input") for f in flags):
        return False
    method = None
    for i, f in enumerate(flags):
        if f in ("-X", "--method") and i + 1 < len(flags):
            method = flags[i + 1].upper()
    return method in (None, "GET")


class World:
    """A temporary folder with the fake gh first on PATH, and the paths of its state, its call log and the record file."""

    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        wrapper = self.bin / "gh"
        wrapper.write_text(f'#!{sys.executable} -S\nimport runpy\nrunpy.run_path("{HERE / "fake_gh.py"}", run_name="__main__")\n')
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
        self.state = self.tmp / "state.json"
        self.log = self.tmp / "calls.jsonl"
        self.record = self.tmp / "run.jsonl"
        (self.tmp / "home").mkdir()
        # A fixed commit identity in a global configuration file of its own, as the rest of the suite does, so the doctor's
        # identity row does not depend on the person's own configuration, on HOME or on the checkout's local configuration.
        self.gitconfig = self.tmp / "gitconfig"
        self.gitconfig.write_text("[user]\n\tname = Test Owner\n\temail = owner@example.com\n")
        self.env = {"PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""), "FAKE_GH_STATE": str(self.state),
                    "FAKE_GH_LOG": str(self.log), "HOME": str(self.tmp / "home"), "USERPROFILE": str(self.tmp / "home"),
                    "XDG_CONFIG_HOME": str(self.tmp / "home" / "xdg"), "GIT_CONFIG_GLOBAL": str(self.gitconfig),
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}

    def seed(self, app=True, **extra):
        state = {"user": {"login": "will-test", "id": 101}, "org": ORG, "repos": {}, "plan": "team"}
        if app:
            state["installations"] = [APP]
            state["install_repos"] = {"900": ["carrydown-tooling"]}
            state["pending_secrets"] = {"carrydown-tooling": ["CARRYDOWN_APP_PRIVATE_KEY"]}
        state.update(extra)
        self.state.write_text(json.dumps(state))


def drive(world, argv, answers=None):
    """live.main(argv) with the fake gh, the operator's answers and no waiting. Returns (exit status, output, prompts)."""
    out = io.StringIO()
    answers = list(answers or [])
    asked = []

    def fake_ask(prompt):
        asked.append(prompt)
        if not answers:
            raise EOFError
        a = answers.pop(0)
        return a() if callable(a) else a
    with mock.patch.dict(os.environ, dict(world.env)), contextlib.redirect_stdout(out), mock.patch.object(live, "ask", fake_ask), \
            mock.patch.object(live, "sleep", lambda s: None):
        os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)
        code = live.main(argv)
    return code, out.getvalue(), asked


_SNAPSHOT = {}


def snapshot():
    """The organization after steps S1 to S5 on the fake, built once. Returns the state, the record, the output and the prompts."""
    if not _SNAPSHOT:
        tmp = Path(tempfile.mkdtemp(prefix="carrydown-live-snapshot-"))
        atexit.register(shutil.rmtree, tmp, True)
        world = World(tmp)
        world.seed()
        code, out, asked = drive(world, ["run", "--org", ORG, "--throwaway", "--record", str(world.record), "--carrydown", str(ROOT), "--apply",
                                         "--to", "S5"], answers=["vouch"])
        _SNAPSHOT.update(state=world.state.read_text(), record=world.record.read_text(), output=out, code=code, asked=asked)
    return _SNAPSHOT


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="carrydown-live-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.world = World(self.tmp)
        self.bin, self.state, self.log, self.record = self.world.bin, self.world.state, self.world.log, self.world.record
        patcher = mock.patch.dict(os.environ, self.world.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("CARRYDOWN_GITHUB_TOKEN", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"):
            os.environ.pop(name, None)
        self.seed()

    def seed(self, app=True, **extra):
        self.world.seed(app, **extra)

    def restore_after_s5(self):
        snap = snapshot()
        self.state.write_text(snap["state"])
        self.record.write_text(snap["record"])

    def calls(self):
        if not self.log.is_file():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]

    def main(self, argv, answers=None):
        code, out, asked = drive(self.world, argv, answers)
        self.asked = asked
        return code, out

    def run_args(self, *extra, carry=None):
        return ["run", "--org", ORG, "--throwaway", "--record", str(self.record), "--carrydown", str(carry or ROOT)] + list(extra)

    def records(self):
        return live.load_records(self.record)


class PlanTests(Base):
    def test_plan_lists_all_17_steps_with_the_human_ones_marked(self):
        code, out = self.main(["plan"])
        self.assertEqual(code, 0)
        rows = re.findall(r"(?m)^(S\d+|A\d+)\s+\[([^\]]+)\]", out)
        self.assertEqual([r[0] for r in rows], ["S1", "S2", "S3", "S4", "S5", "S6", "S7"] + [f"A{i}" for i in range(1, 11)])
        self.assertEqual(len(rows), 17)
        human = {sid for sid, tag in rows if "HUMAN" in tag}
        self.assertEqual(human, {"S2", "S5", "A3", "A7", "A8", "A9"})
        auto = {sid for sid, tag in rows if tag == "AUTOMATIC"}
        self.assertTrue({"S1", "S4", "A2", "A5"} <= auto)
        for needle in ("--org", "--record", "--carrydown", "sample/expense-approvals", "tests/fixtures/sample-workspace", "second account"):
            self.assertIn(needle, out)
        self.assertEqual(self.calls(), [], "plan must not call gh")

    def test_plan_is_the_default_and_needs_no_gh(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        self.world.env["PATH"] = str(empty)
        code, out = self.main([])
        self.assertEqual(code, 0)
        self.assertIn("17 steps", out)
        done = subprocess.run([sys.executable, str(HERE / "live_github_run.py"), "plan"], capture_output=True, text=True,
                              env=dict(os.environ, PATH=str(empty)))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_help_runs(self):
        done = subprocess.run([sys.executable, str(HERE / "live_github_run.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0)
        self.assertIn("render", done.stdout)


class DoctorTests(Base):
    def setUp(self):
        """The doctor reads the commit identity in the folder it runs from. Run it from a folder outside every repository, so a
        checkout's local configuration cannot supply or hide the identity, and the result is the same in a fresh clone."""
        super().setUp()
        self.outside = self.tmp / "outside"
        self.outside.mkdir()
        os.environ["GIT_CEILING_DIRECTORIES"] = str(self.tmp)
        here = os.getcwd()
        os.chdir(self.outside)
        self.addCleanup(os.chdir, here)

    def test_missing_gh_prints_the_install_lines_and_exits_1(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        self.world.env["PATH"] = str(empty)
        code, out = self.main(["doctor", "--org", ORG])
        self.assertEqual(code, 1)
        for line in ("brew install gh", "winget install", "apt install gh", "gh auth login"):
            self.assertIn(line, out)
        self.assertRegex(out, r"gh is installed\s+not verified")
        self.assertRegex(out, r"organization exists\s+not verified\s+needs gh")
        self.assertEqual(self.calls(), [])

    def test_doctor_table_with_gh(self):
        code, out = self.main(["doctor", "--org", ORG])
        self.assertEqual(code, 0, out)
        for row in ("gh is installed", "gh is signed in", "gh token scopes", "signed-in login", "organization exists", "role in the organization",
                    "Python 3.9 or later", "git identity", "candidate builds a release locally"):
            self.assertRegex(out, re.escape(row) + r"\s+verified")
        self.assertIn("will-test", out)
        self.assertIsNone(TOKEN_SHAPE.search(out))
        self.assertTrue(all(read_only(c["args"]) for c in self.calls()), [c["args"] for c in self.calls() if not read_only(c["args"])])

    def test_doctor_without_a_commit_identity_is_not_ready(self):
        empty = self.tmp / "empty-gitconfig"
        empty.write_text("")
        self.world.env["GIT_CONFIG_GLOBAL"] = str(empty)
        code, out = self.main(["doctor", "--org", ORG])
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"git identity\s+not verified\s+run git config --global user.name and user.email")
        self.assertIn("Not ready.", out)

    def test_doctor_with_a_name_and_no_email_is_not_ready(self):
        half = self.tmp / "half-gitconfig"
        half.write_text("[user]\n\tname = Test Owner\n")
        self.world.env["GIT_CONFIG_GLOBAL"] = str(half)
        code, out = self.main(["doctor", "--org", ORG])
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"git identity\s+not verified")

    def test_not_signed_in_is_not_verified(self):
        self.seed(auth="none")
        code, out = self.main(["doctor", "--org", ORG])
        self.assertEqual(code, 1)
        self.assertRegex(out, r"gh is signed in\s+not verified")
        self.assertIn("gh auth login", out)

    def test_free_plan_is_not_verified(self):
        self.seed(plan="free")
        code, out = self.main(["doctor", "--org", ORG])
        self.assertEqual(code, 1)
        self.assertRegex(out, r"plan holds rulesets on private repositories\s+not verified")


class SafetyTests(Base):
    def test_run_refuses_an_org_without_throwaway(self):
        code, out = self.main(["run", "--org", ORG, "--record", str(self.record), "--apply"])
        self.assertEqual(code, 2)
        self.assertIn("--throwaway", out)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.record.exists())

    def test_the_gh_wrapper_refuses_every_delete(self):
        gh = live.Gh(apply=True)
        for args in (["api", "-X", "DELETE", "repos/a/b"], ["api", "--method", "delete", "repos/a/b"], ["api", "--method=DELETE", "repos/a/b"],
                     ["api", "-XDELETE", "repos/a/b"], ["repo", "delete", "a/b"], ["secret", "delete", "X"], ["ruleset", "delete", "1"]):
            with self.assertRaisesRegex(live.Refused, "", msg=args):
                gh.run(args)
        self.assertEqual(self.calls(), [], "a refused call must never reach gh")

    def test_no_command_line_option_can_delete(self):
        with self.assertRaisesRegex(SystemExit, ""), contextlib.redirect_stderr(io.StringIO()):
            live.main(self.run_args("--delete"))

    def test_the_wrapper_refuses_a_write_without_apply(self):
        with self.assertRaisesRegex(live.DryRunStop, ""):
            live.Gh(apply=False).run(["api", "-X", "POST", "orgs/x/repos", "--input", "-"], stdin="{}")
        self.assertEqual(self.calls(), [])

    def test_read_only_classification(self):
        for args in (["api", "user"], ["api", "-X", "GET", "repos/a/b"], ["auth", "status"], ["repo", "view", "a/b"]):
            self.assertTrue(live.is_read_only(args), args)
        for args in (["api", "-X", "POST", "x"], ["api", "x", "--input", "-"], ["api", "x", "-f", "a=b"], ["secret", "set", "X"],
                     ["api", "-X", "PUT", "x"], []):
            self.assertFalse(live.is_read_only(args), args)

    def test_the_source_calls_gh_only_with_argument_arrays(self):
        text = (HERE / "live_github_run.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", text)
        self.assertNotIn("os.system", text)
        self.assertNotIn("push --force", text)


class DryRunTests(Base):
    def check_reads_only(self):
        calls = self.calls()
        self.assertTrue(calls, "the dry run should read something")
        bad = [c["args"] for c in calls if not read_only(c["args"])]
        self.assertEqual(bad, [], "a dry run called a write")

    def test_run_without_apply_performs_only_reads(self):
        code, out = self.main(self.run_args())
        self.assertEqual(code, 0, out)
        self.check_reads_only()
        self.assertIn("DRY RUN", out)
        self.assertIn("would act", out)
        self.assertFalse(self.record.exists(), "a dry run records nothing")
        self.assertFalse((self.tmp / "run.work").exists(), "a dry run writes no working folder")
        self.assertEqual(json.loads(self.state.read_text())["repos"], {}, "nothing was created")

    def test_apply_with_dry_run_still_only_reads(self):
        code, out = self.main(self.run_args("--apply", "--dry-run"))
        self.assertEqual(code, 0, out)
        self.check_reads_only()
        self.assertFalse(self.record.exists())

    def test_a_dry_run_over_a_finished_organization_reads_only_and_reports_finished_steps(self):
        self.restore_after_s5()
        code, out = self.main(self.run_args("--to", "S7"))
        self.assertEqual(code, 0, out)
        for sid in ("S1", "S2", "S3", "S4", "S5"):
            self.assertIn(f"[{sid}] already recorded as finished", out)
        self.assertIn("[S6]", out)
        bad = [c["args"] for c in self.calls() if not read_only(c["args"])]
        self.assertEqual(bad, [])


class ApplyTests(Base):
    def test_steps_s1_to_s5_are_recorded_with_evidence(self):
        snap = snapshot()
        self.assertEqual(snap["code"], 0, snap["output"])
        rows = [json.loads(line) for line in snap["record"].splitlines()]
        self.assertEqual([r["step"] for r in rows], ["S1", "S2", "S3", "S4", "S5"])
        for r in rows:
            self.assertEqual(sorted(r), ["evidence", "finished", "sanitized", "started", "state", "step"])
            self.assertIs(r["sanitized"], True)
            self.assertIn(r["state"], ("done", "skipped", "human", "failed"))
            self.assertTrue(r["started"] <= r["finished"])
        self.assertEqual({r["step"]: r["state"] for r in rows}, {"S1": "done", "S2": "done", "S3": "done", "S4": "done", "S5": "human"})
        by = {r["step"]: r["evidence"] for r in rows}
        self.assertEqual(len(by["S1"]["ids"]["verifier_sha"]), 40)
        self.assertEqual(by["S2"]["ids"]["app_id"], 555)
        self.assertEqual(by["S2"]["settings"]["permissions"], APP["permissions"])
        s3 = by["S3"]["settings"]
        self.assertEqual(s3["staging_ruleset"]["require_last_push_approval"], False)
        self.assertEqual(s3["staging_ruleset"]["dismiss_stale_reviews_on_push"], True)
        self.assertEqual(s3["staging_ruleset"]["strict_required_status_checks_policy"], True)
        self.assertEqual(s3["staging_ruleset"]["required_checks"], ["carrydown-staging-verifier@555"])
        self.assertEqual(s3["engineering_ruleset"]["required_checks"], ["carrydown-release-verifier@555"])
        self.assertEqual(s3["merge_methods"], {"allow_merge_commit": True, "allow_squash_merge": False, "allow_rebase_merge": False})
        self.assertEqual(s3["staging_ruleset"]["bypass_actors"], 0)
        self.assertEqual(len(by["S4"]["ids"]["enrollment_id"]), 64)
        self.assertNotEqual(by["S4"]["ids"]["policy_commit_sha"], by["S1"]["ids"]["verifier_sha"])
        self.assertIn("tooling_ruleset_id", by["S5"]["ids"])
        self.assertEqual(len(snap["asked"]), 1, "only the administrator's vouch is asked when the App already exists")
        self.assertIsNone(TOKEN_SHAPE.search(snap["record"]))

    def test_the_enrollment_pushed_to_the_tooling_repository_is_valid_and_pinned(self):
        state = json.loads(snapshot()["state"])
        tooling = state["repos"][f"{ORG}/carrydown-tooling"]
        tree = tooling["trees"][tooling["commits"][tooling["refs"]["main"]]["tree"]]
        text = base64.b64decode(tooling["blobs"][tree["enrollment.yaml"][0]]).decode()
        self.assertRegex(text, r"(?m)^\s*verifier_sha: [0-9a-f]{40}$")
        for component in ("staging-readers", "runtime-isolation", "verifier-isolation"):
            self.assertIn(f"component: {component}", text)
        self.assertIn("verifier_app_id: 555", text)
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "enrollment.yaml"
            f.write_text(text)
            done = subprocess.run([sys.executable, str(ROOT / "verifier" / "verify_release.py"), "digests", "--policy-file", str(f)],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("matches the file", done.stdout)
        for path in ("scripts/release.py", "verifier/verify_release.py", ".github/workflows/carrydown-release-verify.yml"):
            self.assertIn(path, tree)
        engineering = state["repos"][f"{ORG}/expense-approvals"]
        self.assertIn(".carrydown/release-policy.yaml", engineering["trees"][engineering["commits"][engineering["refs"]["main"]]["tree"]])
        staging = state["repos"][f"{ORG}/expense-approvals-releases"]
        self.assertEqual([r["name"] for r in staging["rulesets"]], ["carrydown release"])
        self.assertEqual([r["name"] for r in tooling["rulesets"]], ["carrydown tooling"])
        self.assertEqual(staging["allow_squash_merge"], False)
        self.assertTrue(staging["actions"]["can_approve_pull_request_reviews"])

    def test_a_human_step_waits_then_reverifies_through_gh(self):
        self.seed(app=False)

        def operator_creates_the_app():
            state = json.loads(self.state.read_text())
            state["installations"] = [APP]
            state["install_repos"] = {"900": ["carrydown-tooling"]}
            state["repos"][f"{ORG}/carrydown-tooling"]["secrets"].append("CARRYDOWN_APP_PRIVATE_KEY")
            self.state.write_text(json.dumps(state))
            return ""
        code, out = self.main(self.run_args("--apply", "--to", "S2"), answers=["", operator_creates_the_app])
        self.assertEqual(code, 0, out)
        self.assertIn("HUMAN STEP: create the verifier App", out)
        self.assertIn("gh api -X POST app-manifests/CODE/conversions", out)
        self.assertIn("Not yet verified", out, "the first enter, before the App exists, must be rejected")
        self.assertEqual(len(self.asked), 2)
        self.assertEqual({r["step"]: r["state"] for r in self.records()}, {"S1": "done", "S2": "human"})
        page = self.tmp / "run.work" / "app-manifest.html"
        text = page.read_text()
        self.assertIn("settings/apps/new", text)
        self.assertIn("&quot;pull_requests&quot;: &quot;read&quot;", text)
        self.assertNotIn("hook_attributes", text)

    def test_a_human_step_with_no_operator_fails_and_can_be_retried(self):
        self.seed(app=False)
        code, out = self.main(self.run_args("--apply", "--to", "S2"))
        self.assertEqual(code, 1)
        last = self.records()[-1]
        self.assertEqual((last["step"], last["state"], last["evidence"]["reason_codes"]), ("S2", "failed", ["no-operator"]))
        self.assertEqual([r["step"] for r in self.records() if r["state"] == "done"], ["S1"])

    def test_a_second_run_repeats_nothing(self):
        self.restore_after_s5()
        code, out = self.main(self.run_args("--apply", "--to", "S5"))
        self.assertEqual(code, 0)
        for sid in ("S1", "S2", "S3", "S4", "S5"):
            self.assertIn(f"[{sid}] already recorded as finished", out)
        self.assertEqual(self.calls(), [], "a finished run needs no gh call at all")
        self.assertEqual(len(self.records()), 5)

    def test_from_resumes_without_repeating_done_steps(self):
        self.restore_after_s5()
        rows = self.records()
        self.record.write_text("".join(json.dumps(r) + "\n" for r in rows[:2]))      # S1 and S2 are done, the rest was never recorded
        code, out = self.main(self.run_args("--apply", "--from", "S3", "--to", "S5"))
        self.assertEqual(code, 0, out)
        self.assertNotIn("[S1]", out)
        self.assertNotIn("[S2]", out)
        posts = [c["args"] for c in self.calls() if c["args"][:3] == ["api", "-X", "POST"]]
        self.assertEqual([a for a in posts if a[3].endswith("/repos")], [], "no repository is created twice")
        self.assertEqual([a for a in posts if a[3].endswith("/rulesets")], [], "no ruleset is created twice")
        self.assertEqual([a for a in posts if a[3].endswith("/git/blobs")], [], "no commit is pushed twice")
        after = self.records()
        self.assertEqual([r["step"] for r in after], ["S1", "S2", "S3", "S4", "S5"])
        self.assertEqual([r["state"] for r in after[2:]], ["skipped", "skipped", "skipped"])
        self.assertEqual(after[2]["evidence"]["ids"]["staging_ruleset_id"], rows[2]["evidence"]["ids"]["staging_ruleset_id"])

    def test_a_later_step_reads_earlier_ids_from_github_when_the_record_is_lost(self):
        self.restore_after_s5()
        self.record.write_text("")
        code, out = self.main(self.run_args("--apply", "--from", "S4", "--to", "S4"))
        self.assertEqual(code, 0, out)
        self.assertEqual([r["state"] for r in self.records()], ["skipped"])

    def test_resuming_after_a_failed_step_retries_it(self):
        self.seed(leak={"path": r"repos/acme-throwaway/expense-approvals$", "text": "boom"})
        code, out = self.main(self.run_args("--apply", "--to", "S3"))
        self.assertEqual(code, 1)
        self.assertEqual([r["state"] for r in self.records()], ["done", "done", "failed"])
        state = json.loads(self.state.read_text())
        state.pop("leak")
        self.state.write_text(json.dumps(state))
        code, out = self.main(self.run_args("--apply", "--to", "S3"))
        self.assertEqual(code, 0, out)
        self.assertEqual([r["state"] for r in self.records()], ["done", "done", "failed", "done"])

    RID = "ab" * 32

    def stub_carry(self):
        """A copy of the carrydown checkout whose release.py is a stub that needs no token: the doctor says every component is verified."""
        carry = self.tmp / "carry"
        for part in ("scripts", "verifier", "templates"):
            shutil.copytree(ROOT / part, carry / part, ignore=shutil.ignore_patterns("__pycache__"))
        (carry / "tests" / "fixtures").mkdir(parents=True)
        shutil.copytree(ROOT / "tests" / "fixtures" / "sample-workspace", carry / "tests" / "fixtures" / "sample-workspace")
        (carry / "sample" / "expense-approvals").mkdir(parents=True)
        for part in ("docs/spec", "docs/ground-truth"):
            shutil.copytree(ROOT / "sample" / "expense-approvals" / part, carry / "sample" / "expense-approvals" / part)
        (carry / "scripts" / "release.py").write_text(
            "import sys\n"
            "cmd = sys.argv[1]\n"
            "if cmd == 'doctor':\n"
            "    print('private upload to the staging repository: allowed')\n"
            "    print('export and publication: allowed')\n"
            "    print('  verified        enrollment: ok')\n"
            "    print('  verified        scan-health: ok')\n"
            "elif cmd == 'prepare':\n"
            f"    print('release id (content): {'cd' * 32}')\n"
            f"    print('request id (permission): {self.RID}')\n"
            "else:\n"
            "    print('preview or a dry run')\n")
        return carry

    def test_a2_to_a6_check_who_opened_the_pull_request_the_dismissal_and_the_merge(self):
        """The staging workflow's pull request is seeded, as the stub of release.py approve cannot open one. Everything else is the runner's own."""
        carry = self.stub_carry()
        self.restore_after_s5()
        state = json.loads(self.state.read_text())
        stg = state["repos"][f"{ORG}/expense-approvals-releases"]
        main = stg["refs"]["main"]
        head = "11" * 20
        stg["commits"][head] = {"tree": stg["commits"][main]["tree"], "parents": [main], "message": "request", "login": "will-test"}
        stg["refs"][f"request/{self.RID}"] = head
        stg["pulls"] = {"1": {"number": 1, "state": "open", "merged": False, "merge_commit_sha": None, "html_url": "https://github.com/x/pull/1",
                              "head": {"ref": f"request/{self.RID}", "sha": head}, "user": {"login": "github-actions[bot]", "type": "Bot"}, "reviews": []}}
        self.state.write_text(json.dumps(state))

        def owner_approves():
            now = json.loads(self.state.read_text())
            pr = now["repos"][f"{ORG}/expense-approvals-releases"]["pulls"]["1"]
            pr["reviews"].append({"id": 300 + len(pr["reviews"]), "state": "APPROVED", "commit_id": pr["head"]["sha"], "user": {"login": "will-test"}})
            self.state.write_text(json.dumps(now))
            return ""
        code, out = self.main(self.run_args("--apply", "--from", "S6", "--to", "A6", carry=carry), answers=[owner_approves, owner_approves])
        self.assertEqual(code, 0, out)
        by = {r["step"]: r for r in self.records()}
        self.assertEqual([r for r in by if r.startswith("A")], ["A1", "A2", "A3", "A4", "A5", "A6"])
        self.assertEqual(by["A1"]["evidence"]["settings"]["organization_plan"], "team")
        a2 = by["A2"]["evidence"]
        self.assertEqual(a2["settings"]["opened_by"], "github-actions[bot]")
        self.assertEqual(a2["settings"]["check_before_review"]["conclusion"], "failure")
        self.assertIn("approval-not-found", a2["settings"]["check_before_review"]["reason_codes"])
        a3 = by["A3"]
        self.assertEqual(a3["state"], "human")
        self.assertTrue(a3["evidence"]["settings"]["first_approval_dismissed"])
        self.assertEqual(len(a3["evidence"]["ids"]["dismissed_review_ids"]), 1)
        self.assertNotEqual(a3["evidence"]["ids"]["final_head_sha"], head)
        self.assertEqual(len(self.asked), 2, "the owner is asked to approve twice")
        a4 = by["A4"]["evidence"]["settings"]
        self.assertEqual((a4["require_last_push_approval"], a4["pusher_is_approver"], a4["approved_by"]), (False, True, "will-test"))
        a5 = by["A5"]["evidence"]["settings"]
        self.assertEqual((a5["before_review"]["conclusion"], a5["after_review"]["conclusion"], a5["check_app_id"]), ("failure", "success", 555))
        a6 = by["A6"]["evidence"]
        self.assertEqual((a6["settings"]["merge_commit_parents"], a6["settings"]["export_dry_run_exit"]), (2, 0))
        merges = [c["args"] for c in self.calls() if c["args"][:3] == ["api", "-X", "PUT"] and c["args"][3].endswith("/merge")]
        self.assertEqual(len(merges), 1)
        merged_body = [c["stdin"] for c in self.calls() if c["args"][:3] == ["api", "-X", "PUT"] and c["args"][3].endswith("/merge")][0]
        self.assertEqual(json.loads(merged_body)["merge_method"], "merge")
        self.assertIsNone(TOKEN_SHAPE.search(self.record.read_text()))

    def test_s6_and_s7_create_the_candidate_and_record_the_request_id(self):
        carry = self.stub_carry()
        rid = self.RID
        self.restore_after_s5()
        code, out = self.main(self.run_args("--apply", "--from", "S6", "--to", "S7", carry=carry))
        self.assertEqual(code, 0, out)
        by = {r["step"]: r for r in self.records()}
        self.assertEqual(by["S6"]["state"], "done")
        self.assertEqual(by["S6"]["evidence"]["settings"]["components"], {"enrollment": "verified", "scan-health": "verified"})
        self.assertEqual(by["S7"]["evidence"]["ids"]["request_id"], rid)
        work = self.tmp / "run.work"
        plan = (work / "workspace" / "drafts" / "plan.yaml").read_text()
        self.assertIn(f"repo: {ORG}/expense-approvals", plan)
        self.assertIn("repo_audience_approved: false", plan)
        self.assertIn('approvers: ["will-test"]', plan)
        self.assertTrue((work / "workspace" / "drafts" / "docs" / "spec" / "README.md").is_file())
        self.assertTrue((work / "workspace" / "renderings" / "architecture.md").is_file())
        self.assertTrue((work / "project" / ".carrydown" / "release-policy.yaml").is_file())


class CandidateWiringTests(unittest.TestCase):
    def test_the_candidate_the_runner_wires_prepares_and_uploads_on_the_no_path(self):
        """The runner wires the candidate from the sample. Here the same files go into the in-memory organization of the mocked
        scenarios, where release.py prepare and approve --github run for real against local bare repositories."""
        sys.path.insert(0, str(ROOT / "tests" / "mock"))
        import release_fixture as F
        tmp = Path(tempfile.mkdtemp(prefix="carrydown-wiring-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        project = F.NoProject(tmp).start()
        self.addCleanup(project.stop)
        shutil.rmtree(project.workspace / "drafts")
        shutil.rmtree(project.workspace / "renderings")
        live.write_candidate(ROOT, project.workspace, "acme", "sct-will")
        code, out, err = project.prepare("--no-github")
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, r"request id \(permission\): [0-9a-f]{64}")
        self.assertRegex(out, r"release id \(content\): [0-9a-f]{64}")
        code, out, err = project.approve()
        self.assertEqual(code, 0, out + err)
        self.assertIn("Branch request/", out)


class RedactionTests(Base):
    def test_no_token_shape_reaches_the_record_or_the_output(self):
        leaked = "bad credentials for ghp_" + "A" * 36 + " and github_pat_" + "B" * 40 + " and gho_" + "C" * 30
        self.seed(leak={"path": r"repos/acme-throwaway/carrydown-tooling$", "text": leaked})
        code, out = self.main(self.run_args("--apply", "--to", "S1"))
        self.assertEqual(code, 1)
        text = self.record.read_text()
        self.assertTrue(text.strip(), "the failure is recorded")
        self.assertIsNone(TOKEN_SHAPE.search(text))
        self.assertIsNone(TOKEN_SHAPE.search(out))
        self.assertNotIn("A" * 20, text + out)
        row = json.loads(text.splitlines()[-1])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["evidence"]["reason_codes"], ["gh-http-500"])
        self.assertIn("<redacted>", text)

    def test_redact_and_sanitize(self):
        self.assertEqual(live.redact("x ghp_" + "a" * 30 + " y"), "x <redacted> y")
        self.assertNotIn("PRIVATE", live.redact("-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"))
        self.assertIn("<redacted>", live.redact("Authorization: Bearer abcdef"))
        cleaned = live.sanitize({"ids": {"app_id": 1}, "token": "x", "private_key": "y", "nested": [{"api_key": "z", "ok": "ghs_" + "q" * 25}], "n": None})
        self.assertEqual(cleaned, {"ids": {"app_id": 1}, "nested": [{"ok": "<redacted>"}], "n": None})

    def test_an_error_text_from_gh_is_redacted_before_it_is_shown(self):
        self.seed(leak={"path": r"user$", "text": "ghp_" + "Z" * 36})
        with self.assertRaisesRegex(live.GhError, "") as raised:
            live.Gh(apply=False).api("user")
        self.assertNotIn("Z" * 20, raised.exception.text)

    def test_the_runner_never_reads_a_token(self):
        text = (HERE / "live_github_run.py").read_text(encoding="utf-8")
        self.assertNotIn("GITHUB_TOKEN", text)
        self.assertNotIn('"auth", "token"', text)
        self.assertEqual(text.count("read_token("), 1, "only the doctor's opt-in fallback hands the stored token to github_client")


class RenderTests(Base):
    def setup_rows(self):
        text = (ROOT / "docs" / "organization-setup.md").read_text(encoding="utf-8")
        section = text[text.index("Record the results here"):text.index("## Run it with the runner")]
        return [line for line in section.splitlines() if line.startswith("| ")][2:]

    def test_the_rows_match_docs_setup_in_label_and_order(self):
        lines = live.render_table([]).splitlines()
        self.assertEqual(lines[0], "| Item | Record |")
        held = self.setup_rows()
        self.assertEqual(len(lines) - 2, len(held))
        for mine, theirs in zip(lines[2:], held):
            self.assertEqual(mine, theirs)        # with no records every row says Not yet performed, as the document does

    def write_records(self):
        rows = [
            {"step": "S1", "started": "2027-02-01T10:00:00Z", "finished": "2027-02-01T10:01:00Z", "state": "done", "sanitized": True,
             "evidence": {"ids": {"tooling_repository_id": 11, "verifier_sha": "a" * 40}, "urls": ["https://github.com/acme/carrydown-tooling"]}},
            {"step": "S3", "started": "2027-02-01T10:10:00Z", "finished": "2027-02-01T10:12:00Z", "state": "done", "sanitized": True,
             "evidence": {"ids": {"engineering_repository_id": 12, "staging_repository_id": 13, "staging_ruleset_id": 21},
                          "settings": {"staging_ruleset": {"require_last_push_approval": False}}}},
            {"step": "A2", "started": "2027-02-01T11:00:00Z", "finished": "2027-02-01T11:05:00Z", "state": "done", "sanitized": True,
             "evidence": {"ids": {"staging_pull_request": 1}, "logins": ["github-actions[bot]", "will-test"]}},
            {"step": "A5", "started": "2027-02-01T11:30:00Z", "finished": "2027-02-01T11:35:00Z", "state": "failed", "sanitized": True,
             "evidence": {"reason_codes": ["staging-check-not-success-after-review"]}},
        ]
        self.record.write_text("".join(json.dumps(r) + "\n" for r in rows))

    def test_render_fills_the_rows_that_have_records_and_leaves_the_rest(self):
        self.write_records()
        code, out = self.main(["render", "--record", str(self.record)])
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 2 + 15)
        table = {}
        for line in lines[2:]:
            label, text = line[2:-2].split(" | ", 1)
            table[label] = text
        self.assertEqual(list(table), [label for label, _ in live.TABLE_ROWS])
        self.assertTrue(table["Date of the run"].startswith("2027-02-01"))
        self.assertIn("tooling_repository_id", table["Repository ids (tooling, engineering, staging)"])
        self.assertIn("staging_repository_id", table["Repository ids (tooling, engineering, staging)"])
        self.assertIn("github-actions[bot]", table["Request opened by the Actions identity (step 2)"])
        self.assertIn("failed", table["Staging check outcomes (step 5)"])
        self.assertIn("staging-check-not-success-after-review", table["Sanitized check outcomes (ids and reason codes only)"])
        for label in ("Platform and plan", "App id and permissions", "Owner approval and stale-review dismissal (step 3)", "Merge activation (step 6)",
                      "Engineering check outcomes (step 7)", "Replacement (step 8)", "Receipt-only withdrawal (step 9)",
                      "Scan health and scheduler behavior (step 10)", "Last-pusher setting off (step 4)"):
            self.assertEqual(table[label], "Not yet performed", label)
        for line in lines:
            self.assertEqual(line.count("|"), 3, line)

    def test_render_of_a_missing_file_says_so(self):
        code, out = self.main(["render", "--record", str(self.tmp / "none.jsonl")])
        self.assertEqual(code, 2)


class HelperTests(unittest.TestCase):
    def test_enrollment_text_parses_with_the_repositorys_own_reader_and_keeps_the_verifier_line(self):
        entry = {
            "repository": "acme/expense-approvals", "repository_id": 4200, "enrollment_id": "", "policy_sha256": "",
            "staging_repository": "acme/expense-approvals-releases", "staging_repository_id": 4300, "staging_workflow_sha256": "f" * 64,
            "staging_readers": {"user_ids": [1, 2], "approved_service_ids": ["carrydown-verifier-acme"]},
            "approvers": [{"id": 1, "login": "will-test"}], "administrators": [{"id": 1, "login": "will-test"}],
            "allowed_targets": {"engineering": {"host": "github.com", "repository_id": 4200, "repository": "acme/expense-approvals"}},
            "governed_paths": ["docs/spec/**", "docs/release/**"], "engineer_edits": {"docs/spec/**": "request-only"},
            "reuse_unchanged_preview": False, "offline_grace_days": 7, "verifier_sha": "9" * 40, "verifier_app_id": 555,
            "check_health_max_age_seconds": 900,
            "attestations": [{"component": "runtime-isolation", "by_id": 1, "at": "2027-01-10T09:00:00Z", "expires_at": "2027-02-10T09:00:00Z",
                              "subject": {"repository_id": 4200, "environment_id": "x"}, "note": "A note, with a comma: and a colon"}],
        }
        text = live.enrollment_text("github.com", 4100, entry)
        parsed = L.loads(text)
        self.assertEqual(parsed["repositories"][0], entry)
        self.assertEqual(parsed["tooling_repository_id"], 4100)
        self.assertRegex(text, r"(?m)^\s*(-\s+)?verifier_sha:\s*[0-9a-f]{40}\s*$")
        self.assertEqual(len(re.findall(r"verifier_sha:", text)), 1)

    def test_working_plan_text_changes_exactly_three_lines(self):
        sample = (ROOT / "tests" / "fixtures" / "sample-workspace" / "drafts" / "plan.yaml").read_text(encoding="utf-8")
        text = live.working_plan_text(sample, "acme", "will-test")
        changed = [(a, b) for a, b in zip(sample.splitlines(), text.splitlines()) if a != b]
        self.assertEqual(len(changed), 3)
        with self.assertRaisesRegex(live.StepFailed, ""):
            live.working_plan_text("project:\n  repo: other\n", "acme", "x")

    def test_ruleset_problem_detects_a_difference_and_ignores_extra_fields(self):
        printed = subprocess.run([sys.executable, str(ROOT / "verifier" / "verify_release.py"), "ruleset", "--kind", "staging", "--app-id", "5"],
                                 capture_output=True, text=True).stdout
        wanted = json.loads(printed)
        existing = json.loads(printed)
        existing["id"], existing["source"] = 9, "acme/x"
        self.assertIsNone(live.ruleset_problem(existing, wanted))
        existing["rules"][2]["parameters"]["require_last_push_approval"] = True
        self.assertIn("require_last_push_approval", live.ruleset_problem(existing, wanted))
        existing = json.loads(printed)
        existing["bypass_actors"] = [{"actor_id": 1}]
        self.assertEqual(live.ruleset_problem(existing, wanted), "a bypass actor is set")

    def test_check_codes(self):
        self.assertEqual(live.check_codes("approval-not-found and x"), ["approval-not-found"])


if __name__ == "__main__":
    unittest.main()
