"""Tests for scripts/release_gate.py.

Two parts.
1. The stub: until the release work package lands, check() returns legacy(no-handling-policy) for
   every call, and no flag or environment variable can bypass the gate.
2. The write assertion scaffold of the specification (D2): every write outside the private
   workspace must be preceded by a gate decision. The assertion is marked expectedFailure because no
   command calls the gate yet. A positive control proves the recorder really sees the writes, so the
   expected failure is an assertion about missing gate calls and not a broken harness. When the
   release work package wires the gate, remove the expectedFailure marker and this test must pass.

No token and no network are used: the GitHub API is the loopback mock in tests/mock/.
Run from the repository root: python -m unittest discover -s tests -v
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
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import generate_dev_skill as GD  # noqa: E402
import github_client as G  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release_gate as RG  # noqa: E402
import scaffold_spec as SS  # noqa: E402

GATE = ROOT / "scripts" / "release_gate.py"


def quiet(call, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return call(*args, **kwargs)


class GateStubTests(unittest.TestCase):
    def test_every_write_class_is_legacy_today(self):
        self.assertEqual(RG.WRITE_CLASSES, ("draft", "candidate", "release", "state-only"))
        for write_class in RG.WRITE_CLASSES:
            with self.subTest(write_class=write_class):
                decision = RG.check(write_class, "docs/spec/plan.yaml", "0" * 64, "engineering", str(ROOT / "sample/expense-approvals"))
                self.assertIsInstance(decision, RG.Decision)
                self.assertEqual(decision._fields, ("allowed", "outcome", "code", "request_id"))
                self.assertEqual((decision.allowed, decision.outcome, decision.code, decision.request_id),
                                 (True, "legacy", "no-handling-policy", None))

    def test_the_request_id_is_echoed_and_keyword_arguments_are_accepted(self):
        decision = RG.check("release", "WI-01", "a" * 64, "engineering", ".", request_id="b" * 64, event_id="c" * 64,
                            verified_context={"authenticated": True})
        self.assertEqual(decision.outcome, "legacy")
        self.assertEqual(decision.request_id, "b" * 64)

    def test_a_caller_supplied_context_does_not_manufacture_an_allow(self):
        for context in ({"authenticated": True}, {"approved": True, "state": "active"}, True, object()):
            with self.subTest(context=repr(context)[:30]):
                self.assertNotEqual(RG.check("release", "x", "0" * 64, "d", ".", verified_context=context).outcome, "allow")

    def test_an_unknown_write_class_is_a_caller_bug(self):
        try:
            RG.check("anything", "x", "0" * 64, "d", ".")
        except ValueError:
            return
        self.fail("an unknown write class was accepted")

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
        self.assertLessEqual(imported, {"argparse", "sys", "typing"})
        source = GATE.read_text(encoding="utf-8")
        for name in ("os.environ", "getenv", "open(", "socket", "urllib"):
            self.assertNotIn(name, source)


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


class WriteAssertionScaffold(unittest.TestCase):
    """The monkeypatched write assertion of D2. Commands that write into the engineering repository
    or to GitHub run against a copy of the sample and the loopback mock."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-gate-scaffold-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.root = Path(self.temp.name) / "project"
        shutil.copytree(ROOT / "sample/expense-approvals", self.root)
        # make the commands have something to write
        (self.root / "docs/spec/README.md").unlink()
        shutil.rmtree(self.root / "docs/dev")
        mockgh.S.__init__()
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
            stack.enter_context(mock.patch.object(RG, "check", rec.gate(RG.check)))
            stack.enter_context(mock.patch.object(L, "write_text", rec.file(L.write_text)))
            stack.enter_context(mock.patch.object(G.GitHub, "_send", lambda c, m, u, d=None, *a, **k: rec.github(real_send)(c, m, u, d, *a, **k)))
            stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None)))
            self.statuses = {
                "scaffold": quiet(SS.main, ["--root", str(self.root), "--apply", "--allow-no-git"]),
                "dev skill": quiet(GD.main, ["--root", str(self.root), "--apply"]),
                "github_sync": quiet(GS.run, ["--root", str(self.root), "--repo", "o/r", "--skip-check", "--apply", "--create-epic"]),
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
        self.assertIn("github-issues.json", files)
        self.assertTrue((self.root / "docs/spec/README.md").is_file())
        self.assertTrue((self.root / "docs/dev/skills/expense-approvals-dev/SKILL.md").is_file())
        issue_posts = [e for e in kinds["github"] if e[1] == "POST" and e[2].endswith("/issues")]
        self.assertGreaterEqual(len(issue_posts), 10)
        self.assertEqual(len(mockgh.S.issues), len(issue_posts))
        # today nothing consults the gate, which is what the expected failure below records
        self.assertEqual([e for e in rec.events if e[0] == "gate"], [])

    @unittest.expectedFailure
    def test_every_write_outside_the_workspace_is_preceded_by_a_gate_decision(self):
        """Fails until the release work package wires the gate into every write site. Then remove
        the expectedFailure marker. A file write needs an earlier gate call for the same path. A
        GitHub write needs an earlier release-class gate call, and there must be at least one such
        call for each write, because the approval is rechecked before each target mutation."""
        rec = self.run_writing_commands()
        writes = rec.writes()
        self.assertTrue(writes, "the commands wrote nothing, so the scaffold proves nothing")
        release_calls = 0
        for index, event in writes:
            earlier = [e for e in rec.events[:index] if e[0] == "gate"]
            if event[0] == "file":
                wanted = Path(event[1])
                known = [Path(g[3], g[2]).resolve() for g in earlier]
                self.assertIn(wanted, known, f"file write without a gate decision: {wanted.name}")
            else:
                release_calls = len([g for g in earlier if g[1] == "release"])
                self.assertTrue(release_calls, f"GitHub write without a release gate decision: {event[1]}")
        github_writes = [e for _, e in writes if e[0] == "github"]
        all_release = [e for e in rec.events if e[0] == "gate" and e[1] == "release"]
        self.assertGreaterEqual(len(all_release), len(github_writes))


if __name__ == "__main__":
    unittest.main()
