"""Tests for the defects the verification review found and fixed.

Each class names the defect. No token and no network: the release records are the sample's own fixture
(tests/fixtures/sample-workspace), the verifier runs over the in-memory organization of
tests/mock/fake_evidence.py, and the commands run in subprocesses on temporary copies.
Run from the repository root: python -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import release_gate as RG  # noqa: E402
import release_schema as RS  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
SAMPLE_WS = ROOT / "tests" / "fixtures" / "sample-workspace"
TEMPLATE = ROOT / "templates" / "dev-skill" / "scripts" / "check_context.py"

_spec = importlib.util.spec_from_file_location("check_context_review", str(TEMPLATE))
CC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CC)

NOT_ONE = (1.0, True, "1", 2, None)


def sample_receipt():
    path = next((SAMPLE / "docs" / "release").glob("*.receipt.json"))
    return path, path.read_bytes()


def sample_request():
    return json.loads(next(SAMPLE_WS.glob("requests/*/approval-request.json")).read_text(encoding="utf-8"))


def sample_event():
    return json.loads(next(SAMPLE_WS.glob("events/*.json")).read_text(encoding="utf-8"))


class FormatFieldTests(unittest.TestCase):
    """A format field is the integer 1 (specification Part H1). Before the fix 1.0 passed every reader,
    because 1.0 == 1 in Python: a receipt, a request, its receipt template and an event batch with format
    1.0 validated, and the gate took a policy pointer with format 1.0 as well formed."""

    def schema_error(self, call, *args, **kwargs):
        """Run call and return the SchemaError it raised. No error is a test failure."""
        try:
            call(*args, **kwargs)
        except RS.SchemaError as error:
            return error
        self.fail("%s did not refuse" % getattr(call, "__name__", call))

    def test_is_format_takes_only_the_integer(self):
        self.assertTrue(RS.is_format(1))
        for value in NOT_ONE:
            self.assertFalse(RS.is_format(value), value)

    def test_the_receipt_refuses_a_format_that_is_not_the_integer_1(self):
        _, raw = sample_receipt()
        receipt = RS.loads_strict(raw)
        RS.validate_receipt(raw)
        for value in NOT_ONE:
            self.schema_error(RS.validate_receipt, RS.canonical_json(dict(receipt, receipt_format=value)))

    def test_the_request_its_template_and_an_event_refuse_it(self):
        request = {k: v for k, v in sample_request().items() if k != "request_sha256"}
        event = {k: v for k, v in sample_event().items() if k != "event_id"}
        RS.validate_request(dict(request), check_digest=False)
        RS.validate_event(dict(event), check_digest=False)
        for value in NOT_ONE:
            self.schema_error(RS.validate_request, dict(request, request_format=value), check_digest=False)
            self.schema_error(RS.validate_request, dict(request, receipt_template=dict(request["receipt_template"], receipt_format=value)),
                              check_digest=False)
            self.schema_error(RS.validate_event, dict(event, event_format=value), check_digest=False)

    def test_the_engineers_check_refuses_a_receipt_or_a_cache_with_format_1_0(self):
        _, raw = sample_receipt()
        self.assertIsNotNone(CC.parse_receipt(raw))
        self.assertIsNone(CC.parse_receipt(raw.replace(b'"receipt_format":1,', b'"receipt_format":1.0,')))

    def test_the_gate_takes_a_pointer_with_format_1_0_as_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".carrydown").mkdir()
            pointer = root / ".carrydown" / "release-policy.yaml"
            for text, ok in (("format: 1\n", True), ("format: 1.0\n", False), ("format: true\n", False)):
                pointer.write_text(text + "tooling_repository: acme/carrydown-tooling\nenrollment_id: " + "7" * 64 + "\n", encoding="utf-8")
                RG._STATE_CACHE.clear()
                state = RG.project_state(str(root))
                self.assertTrue(state.enrolled)
                self.assertEqual(state.pointer_ok, ok, text)
            decision = RG.check("draft", "docs/spec/README.md", "0" * 64, "engineering-repo", str(root))
            self.assertEqual((decision.allowed, decision.code), (False, "policy-pointer-mismatch"))

    def test_the_released_checker_reports_a_receipt_with_format_1_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "clone"
            shutil.copytree(str(SAMPLE), str(clone))
            path = next((clone / "docs" / "release").glob("*.receipt.json"))
            path.write_bytes(path.read_bytes().replace(b'"receipt_format":1,', b'"receipt_format":1.0,'))
            run = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_specs.py"), "--root", str(clone), "--view", "released"],
                                 capture_output=True, text=True, timeout=300)
            self.assertNotEqual(run.returncode, 0, run.stdout)
            self.assertIn("is not a valid receipt", run.stdout + run.stderr)


class PointerSpellingTests(unittest.TestCase):
    """Before the fix the verifier matched the policy pointer without regard to case, then read only the
    exact path, so a pull request from an approver that added .CARRYDOWN/release-policy.yaml naming
    another enrollment passed with "content". On a disk that ignores case that file replaces the real
    pointer in the clone."""

    @classmethod
    def setUpClass(cls):
        import engineering_fixture as EF
        import fake_evidence as FE
        cls.tmp = tempfile.mkdtemp(prefix="carrydown-review-")
        cls.ex = EF.Exported(Path(cls.tmp), world=FE.World())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def verify(self, files, user):
        import engineering_fixture as EF
        import release_engineering as RE
        case = EF.Case(self.ex)
        number = case.open(edit=files, only={"src/app.py": b"print(1)\n"}, user=user)
        return RE.verify_engineering(case.reader, case.enrollment(), number)

    def test_another_spelling_of_the_pointer_fails_even_from_an_approver(self):
        import fake_evidence as FE
        evil = b"format: 1\ntooling_repository: evil/tooling\nenrollment_id: " + b"0" * 64 + b"\n"
        for name in (".CARRYDOWN/release-policy.yaml", ".carrydown/Release-Policy.yaml"):
            report = self.verify({name: evil}, FE.OWNER)
            self.assertFalse(report.ok, name)
            self.assertIn(("policy-pointer-mismatch", name), [(f.code, f.where) for f in report.findings])

    def test_an_unrelated_change_still_has_no_governed_changes(self):
        import fake_evidence as FE
        report = self.verify({"src/other.py": b"x = 1\n"}, FE.OWNER)
        self.assertTrue(report.ok, report.findings)
        self.assertEqual(report.kind, "no-governed-changes")


class RetentionTests(unittest.TestCase):
    """raw_inputs: delete-after-release (specification E2). Before the fix it was recorded in
    retention.yaml and never acted on: the raw inputs stayed in the workspace after the release."""

    def setUp(self):
        import hashlib
        from sample_tree import copy_sample
        self.hashlib = hashlib
        self.tmp = Path(tempfile.mkdtemp(prefix="carrydown-retention-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        home = self.tmp / "home"
        home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k not in ("CARRYDOWN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")}
        self.env.update(HOME=str(home), USERPROFILE=str(home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")
        self.root = self.tmp / "project"
        copy_sample(self.root)
        self.ws = self.tmp / "workspace"
        for args in (["init", "-q", "-b", "main"], ["config", "user.name", "Test Owner"], ["config", "user.email", "test.owner@example.com"]):
            subprocess.run(["git"] + args, cwd=str(self.root), check=True, capture_output=True, env=self.env)

    def run_script(self, script, *args):
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / script)] + [str(a) for a in args], cwd=str(self.root),
                             capture_output=True, text=True, env=self.env, timeout=300)
        self.assertEqual(run.returncode, 0, run.stdout[-400:] + run.stderr[-400:])
        return run.stdout + run.stderr

    def release(self, retain):
        self.run_script("workspace.py", "init", "--root", self.root, "--slug", "proof", "--workspace", self.ws, "--retain", retain, "--apply")
        sources = self.ws / "sources"
        (sources / "notes").mkdir(parents=True)
        (sources / "architecture.docx").write_bytes(b"original bytes of a raw input\n")
        (sources / "notes" / "interview.txt").write_text("raw interview notes\n", encoding="utf-8")
        self.outside = self.tmp / "elsewhere.md"
        self.outside.write_text("a file the owner keeps elsewhere\n", encoding="utf-8")
        if os.name == "posix":
            os.symlink(str(self.outside), str(sources / "linked.md"))
        out = self.run_script("release.py", "prepare", "--root", self.root, "--repository-id", "4200", "--apply")
        rid = out.split("request id (permission):", 1)[1].split()[0]
        self.run_script("release.py", "approve", "--root", self.root, "--request", rid, "--local", "--preview-shown", "--apply")
        dry = self.run_script("release.py", "export", "--root", self.root, "--request", rid)
        applied = self.run_script("release.py", "export", "--root", self.root, "--request", rid, "--apply")
        return rid, dry, applied

    def test_delete_after_release_removes_the_raw_inputs_after_the_export_and_records_it(self):
        rid, dry, applied = self.release("delete-after-release")
        self.assertIn("would be deleted", dry)
        self.assertIn("retention: deleted", applied)
        self.assertEqual(sorted(p.name for p in (self.ws / "sources").iterdir()), [])
        self.assertTrue(self.outside.is_file(), "the target of a link was deleted")
        records = [json.loads(x) for x in (self.ws / "retention-log.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["request_id"], rid)
        by_path = {d["path"]: d for d in records[0]["deleted"]}
        self.assertEqual(by_path["architecture.docx"]["sha256"], self.hashlib.sha256(b"original bytes of a raw input\n").hexdigest())
        self.assertIn("notes/interview.txt", by_path)
        if os.name == "posix":
            self.assertEqual(by_path["linked.md"], {"path": "linked.md", "link": True})
        log = (self.ws / "retention-log.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("raw interview notes", log)
        self.assertNotIn("original bytes", log)
        self.assertTrue((self.root / "docs" / "release" / f"{rid}.receipt.json").is_file(), "the export did not finish first")

    def test_keep_deletes_nothing(self):
        _, dry, applied = self.release("keep")
        self.assertNotIn("retention:", dry + applied)
        self.assertTrue((self.ws / "sources" / "architecture.docx").is_file())
        self.assertFalse((self.ws / "retention-log.jsonl").exists())

    def test_a_dry_run_or_a_sources_link_changes_nothing(self):
        import workspace as W
        ws = self.tmp / "ws"
        (ws / "sources").mkdir(parents=True)
        (ws / "retention.yaml").write_text("raw_inputs: delete-after-release\nhistory: keep\n", encoding="utf-8")
        (ws / "sources" / "a.txt").write_text("a\n", encoding="utf-8")
        lines = W.apply_retention(ws, "0" * 64, apply=False)
        self.assertTrue(lines and "would be deleted" in lines[0])
        self.assertTrue((ws / "sources" / "a.txt").exists())
        if os.name == "posix":
            other = self.tmp / "other"
            other.mkdir()
            (other / "keep.txt").write_text("keep\n", encoding="utf-8")
            shutil.rmtree(str(ws / "sources"))
            os.symlink(str(other), str(ws / "sources"))
            self.assertEqual(W.apply_retention(ws, "0" * 64, apply=True), [])
            self.assertTrue((other / "keep.txt").exists())
        (ws / "retention.yaml").write_text("raw_inputs: delete-after-relase\n", encoding="utf-8")
        self.assertEqual(W.retention_choice(ws), "keep")


class SampleIgnoreTests(unittest.TestCase):
    """WP10 defect 7: the sample's .gitignore lists people.yaml while git tracks the sample's fictional
    people.yaml. The file itself now says why, next to the line, as the sample README does."""

    def test_the_ignore_file_explains_the_tracked_fixture_next_to_the_line(self):
        lines = (SAMPLE / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("people.yaml", lines)
        comment = " ".join(x for x in lines[:lines.index("people.yaml")] if x.startswith("#"))
        for words in ("still tracks its people.yaml", "fictional fixture", "private workspace", "README.md"):
            self.assertIn(words, comment)


class StalePublicSampleTests(unittest.TestCase):
    """WP10 defect 8: the public sample repository and docs/images/issue-9.png predate the release layout
    and need the owner's account to republish. Until then the README and the storyboard say so."""

    def test_the_readme_and_the_storyboard_mark_them_as_waiting_to_be_republished(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("waiting to be republished from the current sample", readme)
        storyboard = (ROOT / "docs" / "recording-storyboard.md").read_text(encoding="utf-8")
        row = next(x for x in storyboard.splitlines() if x.startswith("| `docs/images/issue-9.png`"))
        self.assertIn("Legacy pending replacement", row)


if __name__ == "__main__":
    unittest.main()
