"""The source-to-update-to-engineer transition on the request-trace scenario of prepare_field_run.py.

One changed logging rule (architecture section 4.2, item 6) reaches the affected specifications and their approved
context through the real update, release and publication commands. A staged decision in WI-09 survives. The same
engineer checkout refuses the superseded inputs before it fetches, reports the changed approved inputs after it pulls,
and is quiet on the next check. Everything runs in a temporary folder built by prepare_field_run.py. The update is a
deterministic replay of known patches through reconcile.py, not an agent's assessment. GitHub is the loopback mock of
tests/mock/mockgh.py, as in tests/test_publication.py, with the placeholder token the mock tests use. No model call,
no network and no credential. The assertions are facts: exit codes, files, digests and required check output.

Run from the repository root: python3 -m unittest tests.field_run.test_update_transition -v
"""
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import github_client as G  # noqa: E402
import github_project as GP  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import prepare_field_run as P  # noqa: E402
import release_github as RGH  # noqa: E402

HAS_GIT = shutil.which("git") is not None
REPO = "sct-will/carrydown-sample"     # the plan's repository, as the in-memory mock knows it
BOARD_ID = "PVT_sample"
PLACEHOLDER = "ghp_" + "Z" * 36        # the placeholder the repository's mock tests use. It is not a credential
CANONICAL = ("sample/expense-approvals", "tests/fixtures/sample-workspace")
SKILL_CHECK = "docs/dev/skills/expense-approvals-dev/scripts/check_context.py"
HUMAN_BODY = "\n\nNote from a person: the pilot team asked to see the export before the readout.\n"
HUMAN_COMMENT = "A person's comment on this work item. It is not carrydown's text."
PROHIBITION = "They never carry amounts, comments or receipt contents."

# ---------------------------------------------------------------------------
# The known patches of the scenario. Each is (item, path as reconcile.py patch takes it, [(old text, new text)]).
# The old text occurs once, before "Decisions recorded", which no patch touches. WI-07, WI-08 and WI-09 already
# cite 4.2 in the sample, so no patch adds a citation.
# ---------------------------------------------------------------------------

OLD_RULE = "Log lines carry report identifiers and event types. They never carry amounts, comments or receipt contents."
NEW_RULE = ("Log lines carry report identifiers, event types and an identifier for the request or scheduled job run. "
            "They never carry amounts, comments or receipt contents.")
OPERATION = ("the operation identifier: the identifier the API gateway assigns to the request, or the scheduler's run "
             "identifier for a nightly job, an opaque string")
WI07 = "docs/spec/m3-enforce-policy/wi-07-audit-log.md"
WI08 = "docs/spec/m3-enforce-policy/wi-08-notifications-delegates.md"
WI09 = P.WI09

PATCHES = [
    ("WI-07", WI07, [
        ("- Log lines carry report identifiers and event types, never amounts, comments or receipt contents.",
         "- Log lines carry report identifiers, event types and " + OPERATION + ". They never carry amounts, comments or receipt contents."),
        ("6. " + OLD_RULE, "6. " + NEW_RULE),
        ("6. Add `logLine({ reportId, eventType })` to the writer and use it for the audit paths.",
         "6. Add `logLine({ reportId, eventType, operationId })` to the writer and use it for the audit paths. `operationId` is "
         + OPERATION + ". The writer refuses a log line without it."),
        ("- [ ] Log lines from a decision carry the report identifier and event type, and no amount, comment or receipt content (`tests/audit.logs.test.js`).",
         "- [ ] Log lines from a decision carry the report identifier, the event type and the identifier of the request that caused it, "
         "and no amount, comment or receipt content (`tests/audit.logs.test.js`)."),
        ("say that log lines in the worker follow the same rule (identifiers and event types only).",
         "say that log lines in the worker follow the same rule (report identifiers, event types and the request or job run identifier only)."),
    ]),
    ("WI-08", WI08, [
        ('- GOV-2.6 (GOV-2 is the audit and retention rule). "' + OLD_RULE + '"',
         '- GOV-2.6 (GOV-2 is the audit and retention rule). "' + NEW_RULE + '"'),
        ("send it, and log only the report id and event type.",
         "send it, and log only the report id, the event type and the identifier of the request that caused the event, "
         "carried in the event from the decision."),
        ("- [ ] Captured log lines hold report ids and event types only, with no amount, comment, receipt content or address (GOV-2.6, `tests/notify-worker.test.js`).",
         "- [ ] Captured log lines hold report ids, event types and the identifier of the request that caused the event only, with no "
         "amount, comment, receipt content or address (GOV-2.6, `tests/notify-worker.test.js`)."),
    ]),
    ("WI-09", WI09, [
        ("- The file holds no personal data beyond its columns, and log lines hold no amounts (GOV-2.6).",
         "- The file holds no personal data beyond its columns, and log lines carry the scheduler's run identifier of the night's run "
         "and hold no amounts (GOV-2.6)."),
        ('- GOV-2.6. "' + OLD_RULE + '"', '- GOV-2.6. "' + NEW_RULE + '"'),
        ("Check with a fixed clock. Log only report ids and event types.",
         "Check with a fixed clock. Log only report ids, event types and the scheduler's run identifier of the run, in every log line "
         "of the run."),
        ("and captured log lines hold no amount (GOV-2.3, GOV-2.6, `tests/export-ledger-job.test.js`).",
         "and captured log lines carry the scheduler's run identifier and hold no amount (GOV-2.3, GOV-2.6, "
         "`tests/export-ledger-job.test.js`)."),
    ]),
]


def apply_edits(text, edits, where):
    """text with every edit applied before the section "Decisions recorded". Raises ValueError when an old text is
    not found exactly once there."""
    head, sep, tail = text.partition("\n## Decisions recorded\n")
    for old, new in edits:
        if head.count(old) != 1:
            raise ValueError(f"the text this patch edits is not found once in {where}: {old[:70]}")
        head = head.replace(old, new)
    return head + sep + tail


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def fingerprint(rel):
    root = ROOT / rel
    files = sorted((p.relative_to(root).as_posix(), p) for p in root.rglob("*") if p.is_file())
    return len(files), sha("".join(f"{sha(p.read_bytes())}  {rel}/{name}\n" for name, p in files))


def decisions_section(text):
    at = text.find("\n## Decisions recorded\n")
    return None if at < 0 else text[at + 1:]


class Failed(AssertionError):
    pass


class Transition:
    """The run folder and every command of the transition, in order."""

    def __init__(self, folder):
        self.dir = folder
        self.project = folder / "project"
        self.home = folder / "home"
        self.eng_home = folder / "engineer-home"
        self.gt = folder / "install" / "carrydown-ground-truth" / "scripts"
        self.pub = folder / "install" / "carrydown-plan-to-github" / "scripts"
        self.out = {}
        self.attempts = []

    def run(self, key, args, cwd=None, home=None, ok=(0,)):
        args = [str(a) for a in args]
        done = subprocess.run(args, cwd=str(cwd or self.project), capture_output=True, text=True, env=P.run_env(home or self.home), timeout=600)
        self.out[key] = (done.returncode, done.stdout)
        if done.returncode not in ok:
            raise Failed(f"{key}: exit {done.returncode}\n{done.stdout[-1500:]}{done.stderr[-1500:]}")
        return done.stdout

    def py(self, key, script, *args, **kw):
        return self.run(key, [sys.executable, script] + list(args), **kw)

    def git(self, key, *args, **kw):
        return self.run(key, ["git"] + list(args), **kw)

    def release(self, label, message):
        rel = self.pub / "release.py"
        board = ["--board-owner-id", "4400", "--board-project-id", BOARD_ID]
        made = self.py(f"{label} prepare", rel, "prepare", "--root", ".", "--repository-id", "4200", *board, "--apply")
        m = re.search(r"^request id \(permission\): ([0-9a-f]{64})", made, re.M)
        if not m:
            raise Failed("no request id in the output of release.py prepare")
        rid = m.group(1)
        self.py(f"{label} approve", rel, "approve", "--root", ".", "--request", rid, "--local", "--preview-shown", "--apply")
        self.py(f"{label} export", rel, "export", "--root", ".", "--request", rid, "--apply")
        self.git(f"{label} add", "add", "-A")
        self.git(f"{label} commit", "commit", "-q", "-m", message)
        self.git(f"{label} push", "push", "-q", "origin", "main")
        return rid, self.git(f"{label} head", "rev-parse", "HEAD").strip()

    def publish(self, label):
        """The publishing scripts' entry points against the mock: apply and verify for the issues and for the board."""
        for name, fn, args in (("issues apply", GS.run, ["--apply"]), ("issues verify", GS.run, ["--verify"]),
                               ("board apply", GP.run, ["--apply"]), ("board verify", GP.run, ["--verify"])):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                try:
                    code = fn(["--root", str(self.project)] + args)
                except SystemExit as e:
                    code = e.code if isinstance(e.code, int) else 2
            self.out[f"{label} {name}"] = (code or 0, buf.getvalue())
            if code:
                raise Failed(f"{label} {name}: exit {code}\n{buf.getvalue()[-1500:]}")
        return {m.group(1): i["number"] for i in mockgh.S.issues for m in [re.search(r"<!-- carrydown:([A-Za-z0-9-]+) -->", i.get("body") or "")] if m}

    def check(self, key, checkout, item, ok=(0,)):
        return self.py(key, checkout / SKILL_CHECK, item, cwd=checkout, home=self.eng_home, ok=ok)

    def update(self):
        gt, revised = self.gt, "../revision/architecture.docx"
        self.py("render", gt / "render_ground_truth.py", revised, "--root", ".", "--version", "0.4")
        made = self.py("prepare", gt / "reconcile.py", "prepare", "--root", ".", "--apply")
        pid = re.search(r"^proposal: ([0-9a-f]{64})$", made, re.M).group(1)
        workspace = Path(P.workspace_of(self.project))
        for n, (item, path, edits) in enumerate(PATCHES):
            source = workspace / path[len("workspace/"):] if path.startswith("workspace/") else self.project / path
            new = self.dir / f"patch-{n}.txt"
            new.write_bytes(apply_edits(source.read_text(encoding="utf-8"), edits, path).encode("utf-8"))
            self.py(f"patch {n}", gt / "reconcile.py", "patch", "--root", ".", "--proposal", pid, "--block", "architecture/4.2", "--item", item,
                    "--path", path, "--from", new, "--apply")
        self.py("check", gt / "reconcile.py", "check", "--root", ".", "--proposal", pid)
        self.py("apply", gt / "reconcile.py", "apply", "--root", ".", "--proposal", pid, "--apply")
        descriptor = workspace / "drafts" / "proposals" / pid / "descriptor.json"
        out = self.py("checkpoint prepare", gt / "workspace.py", "checkpoint", "prepare", "--root", ".", "--descriptor", descriptor,
                      "--rendering-dir", "docs/ground-truth", "--apply")
        cid = re.search(r"checkpoint ([0-9a-f]{64})", out).group(1)
        self.py("checkpoint commit", gt / "workspace.py", "checkpoint", "commit", "--root", ".", "--id", cid, "--apply")
        return pid, cid, workspace


@unittest.skipUnless(HAS_GIT, "git is needed")
class UpdateTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-transition-")
        cls.fingerprints_before = {rel: fingerprint(rel) for rel in CANONICAL}
        folder = Path(cls.temp.name).resolve() / "run"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = P.main(["--out", str(folder), "--scenario", "request-trace"])
        if code != 0:
            cls.temp.cleanup()
            raise AssertionError(f"prepare_field_run.py exited {code}")
        t = cls.t = Transition(folder)
        mockgh.S.__init__()
        mockgh.S.repos.add(REPO)
        mockgh.S.repo_ids = {REPO: 4200}
        mockgh.add_project("Expense approvals plan")["id"] = BOARD_ID
        server, url = mockgh.start()
        real_connect, real_create = socket.socket.connect, socket.create_connection
        loop = ("127.0.0.1", "::1", "localhost")

        def connect(sock, address, *a, **k):
            if not isinstance(address, tuple) or address[0] in loop:
                return real_connect(sock, address, *a, **k)
            t.attempts.append(str(address[0]))
            raise OSError("this test forbids network access")

        def create(address, *a, **k):
            if address[0] in loop:
                return real_create(address, *a, **k)
            t.attempts.append(str(address[0]))
            raise OSError("this test forbids network access")
        try:
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.dict(os.environ, {"CARRYDOWN_GITHUB_TOKEN": PLACEHOLDER, "HOME": str(t.home), "USERPROFILE": str(t.home)}))
                stack.enter_context(mock.patch.object(time, "sleep", lambda s: None))
                stack.enter_context(mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"))
                stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (url, 0.0, None)))
                stack.enter_context(mock.patch.object(socket.socket, "connect", connect))
                stack.enter_context(mock.patch.object(socket, "create_connection", create))
                cls.run_transition()
        except BaseException:
            server.shutdown()
            server.server_close()
            cls.temp.cleanup()
            raise
        server.shutdown()
        server.server_close()
        cls.fingerprints_after = {rel: fingerprint(rel) for rel in CANONICAL}

    @classmethod
    def run_transition(cls):
        t = cls.t
        # the approved before state: release, publication, a person's text on the WI-09 issue, an engineer checkout
        cls.rid_before, cls.commit_before = t.release("baseline", "Release the plan with the staged WI-09 decision")
        cls.issues_before = t.publish("baseline")
        issue = next(i for i in mockgh.S.issues if "<!-- carrydown:WI-09 -->" in (i.get("body") or ""))
        cls.body_before = issue["body"]
        issue["body"] += HUMAN_BODY
        mockgh.S.add_comment(issue["number"], HUMAN_COMMENT, login="a-person")
        cls.eng = t.dir / "engineer-a"
        t.git("clone", "clone", "-q", str(t.dir / "origin.git"), str(cls.eng), cwd=t.dir, home=t.eng_home)
        (cls.eng / "local-notes.txt").write_bytes(b"Local work in progress on WI-09. Not committed.\n")
        cls.first = t.check("check before", cls.eng, "WI-09")
        # the update, the release that carries it and its publication
        cls.pid, cls.cid, cls.workspace = t.update()
        cls.rid_after, cls.commit_after = t.release("update", "Release the accepted update of the logging rule")
        cls.issues_after = t.publish("update")
        cls.issue_after = next(i for i in mockgh.S.issues if "<!-- carrydown:WI-09 -->" in (i.get("body") or ""))
        cls.comments = [c.get("body") for c in mockgh.S.comments.get(cls.issue_after["number"], [])]
        cls.issue_count = len(mockgh.S.issues)
        # the same checkout: refused before it fetches the update, then changed, then quiet
        cls.refusal = t.check("check before the pull", cls.eng, "WI-09", ok=(11,))
        t.git("pull", "pull", "-q", "--ff-only", cwd=cls.eng, home=t.eng_home)
        cls.changed = t.check("check after the pull", cls.eng, "WI-09")
        cls.repeat = t.check("check again", cls.eng, "WI-09")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def show(self, ref, path):
        return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=str(self.t.project), capture_output=True, text=True).stdout

    # row 1, isolation
    def test_the_canonical_sample_and_fixture_are_unchanged_and_no_network_was_reached(self):
        self.assertEqual(self.fingerprints_after, self.fingerprints_before)
        self.assertEqual(self.t.attempts, [])

    # row 2, actual source change
    def test_the_applied_update_has_one_changed_block_and_an_accepted_checkpoint_of_the_revised_rendering(self):
        folder = self.workspace / "drafts" / "proposals" / self.pid
        self.assertEqual(json.loads((folder / "applied.json").read_text(encoding="utf-8"))["state"], "applied")
        blocks = json.loads((folder / "blocks.json").read_text(encoding="utf-8"))["blocks"]
        self.assertEqual([(b["ref"], b["kind"], b["formatting_only"]) for b in blocks], [("architecture/4.2", "modified", False)])
        rendering = (self.t.project / "docs" / "ground-truth" / "architecture.md").read_bytes()
        text = rendering.decode("utf-8")
        original = (P.SAMPLE / "docs" / "ground-truth" / "architecture.md").read_text(encoding="utf-8")
        self.assertIn(NEW_RULE, text)
        self.assertIn(PROHIBITION, text)
        heads = lambda s: [ln for ln in s.splitlines() if ln.startswith("#")]  # noqa: E731
        self.assertEqual(heads(text), heads(original))
        self.assertIn("version 0.4", text.split("\n", 1)[0])
        ws_yaml = (self.workspace / "workspace.yaml").read_text(encoding="utf-8")
        entries = [c for c in re.split(r"(?m)^  - id: ", ws_yaml)[1:] if c.startswith(f'"{self.cid}"')]
        self.assertEqual(len(entries), 1, "the accepted checkpoint is recorded in workspace.yaml")
        self.assertIn(f'sha256: "{sha(rendering)}"', entries[0])

    # row 4, focused update
    def test_every_patched_item_has_the_revised_rule_in_its_released_context_and_the_receipt_lists_it(self):
        disp = json.loads((self.workspace / "drafts" / "proposals" / self.pid / "dispositions.json").read_text(encoding="utf-8"))
        items = sorted({p["item"] for d in disp["dispositions"] if d.get("disposition") == "update" for p in d["patch"]})
        self.assertEqual(items, ["WI-07", "WI-08", "WI-09"])
        receipt = json.loads((self.t.project / "docs" / "release" / f"{self.rid_after}.receipt.json").read_text(encoding="utf-8"))
        listed = {a["path"]: a["sha256"] for a in receipt["artifacts"]}
        for item in items:
            rel = f"docs/context/{item.lower()}.md"
            released = self.show(self.commit_after, rel)
            self.assertIn(NEW_RULE, released, item)
            self.assertEqual(listed.get(rel), sha(released), item)
        before = self.show(self.commit_before, "docs/context/wi-08.md")
        self.assertIn(OLD_RULE, before, "WI-08 cites 4.2, so its context held the rule before the update")
        self.assertNotIn(NEW_RULE, before, "WI-08 gains the revised rule only through the update")

    # row 5, decision preservation
    def test_the_staged_decision_is_byte_identical_before_after_and_in_the_engineer_checkout(self):
        before = decisions_section(self.show(self.commit_before, WI09))
        after = decisions_section(self.show(self.commit_after, WI09))
        checkout = decisions_section((self.eng / WI09).read_text(encoding="utf-8"))
        self.assertIsNotNone(before)
        self.assertEqual(before.count(P.TRACE_ENTRY), 1)
        self.assertNotIn("None yet.", before)
        self.assertEqual((after, checkout), (before, before))

    # row 6, approval and publication (local service mock)
    def test_both_releases_are_approved_and_published_with_the_same_issues_and_the_human_content_kept(self):
        for rid in (self.rid_before, self.rid_after):
            receipt = json.loads((self.t.project / "docs" / "release" / f"{rid}.receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["request_id"], rid)
            self.assertTrue(receipt.get("approval"))
            journal = json.loads((self.workspace / "publication" / f"{rid}.journal.json").read_text(encoding="utf-8"))
            self.assertTrue(journal["targets"])
            self.assertEqual({v["state"] for v in journal["targets"].values()}, {"completed"}, rid[:12])
        self.assertEqual(self.issues_after, self.issues_before)
        self.assertEqual(self.issue_count, len(self.issues_before))
        self.assertNotEqual(self.issue_after["body"], self.body_before + HUMAN_BODY, "the managed region was updated")
        self.assertIn(HUMAN_BODY.strip(), self.issue_after["body"])
        self.assertIn(HUMAN_COMMENT, self.comments)

    # row 7, engineer result
    def test_the_same_checkout_refuses_the_superseded_inputs_then_reports_the_change_then_is_quiet(self):
        self.assertIn("carrydown: approved context for WI-09 is ready", self.first)
        self.assertIn(f"baseline: request {self.rid_before}", self.first)
        self.assertEqual(self.t.out["check before the pull"][0], 11)
        self.assertIn("carrydown: the approved context for WI-09 is stale", self.refusal)
        self.assertIn("(superseded)", self.refusal)
        lines = self.changed.splitlines()
        self.assertIn(f"baseline: request {self.rid_after}", self.changed)
        self.assertIn("carrydown: approved inputs changed since your last check for WI-09", lines)
        self.assertIn(f"changed: {WI09} (specification)", lines)
        self.assertIn("changed: docs/context/wi-09.md (approved context)", lines)
        self.assertTrue(any(ln.startswith("+") and "request or scheduled job run" in ln for ln in lines))
        self.assertEqual(lines[-1], "Reassess your implementation plan against the current approved inputs before you write more code. "
                                    "Do not continue on the old plan.")
        self.assertEqual(self.t.out["check again"][0], 0)
        self.assertNotIn("carrydown: approved inputs changed", self.repeat)
        cache = "".join(p.read_text(encoding="utf-8") for p in (self.eng / ".carrydown" / "cache").rglob("*") if p.is_file())
        self.assertIn(self.rid_after, cache)
        self.assertTrue((self.eng / "local-notes.txt").is_file(), "the pull kept the engineer's local work")
        self.assertIn(NEW_RULE, (self.eng / "docs" / "context" / "wi-09.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
