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

    def test_is_format_takes_only_the_integer(self):
        self.assertTrue(RS.is_format(1))
        for value in NOT_ONE:
            self.assertFalse(RS.is_format(value), value)

    def test_the_receipt_refuses_a_format_that_is_not_the_integer_1(self):
        _, raw = sample_receipt()
        receipt = RS.loads_strict(raw)
        RS.validate_receipt(raw)
        for value in NOT_ONE:
            with self.assertRaises(RS.SchemaError, msg=value):
                RS.validate_receipt(RS.canonical_json(dict(receipt, receipt_format=value)))

    def test_the_request_its_template_and_an_event_refuse_it(self):
        request = {k: v for k, v in sample_request().items() if k != "request_sha256"}
        event = {k: v for k, v in sample_event().items() if k != "event_id"}
        RS.validate_request(dict(request), check_digest=False)
        RS.validate_event(dict(event), check_digest=False)
        for value in NOT_ONE:
            with self.assertRaises(RS.SchemaError, msg=value):
                RS.validate_request(dict(request, request_format=value), check_digest=False)
            with self.assertRaises(RS.SchemaError, msg=value):
                RS.validate_request(dict(request, receipt_template=dict(request["receipt_template"], receipt_format=value)), check_digest=False)
            with self.assertRaises(RS.SchemaError, msg=value):
                RS.validate_event(dict(event, event_format=value), check_digest=False)

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


if __name__ == "__main__":
    unittest.main()
