#!/usr/bin/env python3
"""Internal validation of the update path on a disposable copy of the expense-approvals sample.

Temporary orchestration for specs/sample-before-and-after-demo.md (sections 4, 5 and 7). It joins existing pieces:
tests/field_run/prepare_field_run.py builds the run folder, tests/field_run/mechanical_run.py is the model of the
update commands, and the loopback service mock of tests/mock/mockgh.py stands in for GitHub, as in
tests/test_publication.py. Every carrydown command is the installed skill's own script, run as its command line or
through its public entry point. No model call, no token, no network and no GitHub. Publication results are local
mock-service results, not a live publication.

  driver.py build --out DIR                  the run folder and the fingerprints of the canonical sample and fixture
  driver.py baseline --dir DIR               section 5B: release, test approval, export, push, mock publication,
                                             read-back, engineer checkouts and their first work-item checks
  driver.py update --dir DIR --mode mechanical
                                             section 5C by known patches through the real update commands
  driver.py update --dir DIR --mode agent    prints the instructions for the coordinator's agent-led run
  driver.py release --dir DIR                section 5D: release and mock publication of the accepted update
  driver.py engineer --dir DIR               section 5E: the same checkout before and after, and an unchanged item
  driver.py verdict --dir DIR                the twelve rows of section 7, verdict.json and results.md
  driver.py all --mode mechanical --out DIR  every stage in order, stopping at the first failure

Each stage saves its commands, outputs and exit codes under DIR/evidence/<stage>/ and exits non-zero on a failure.
DIR must be outside the repository. Standard library only, Python 3.9 or later.
"""
import argparse
import contextlib
import datetime as dt
import hashlib
import importlib
import io
import json
import os
import pickle
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
FIELD = HERE.parent
ROOT = FIELD.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FIELD))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import mechanical_run as MR  # noqa: E402
import patches as KP  # noqa: E402
import prepare_field_run as P  # noqa: E402

START_REVISION = "306ac84ca2a532a606494ece60a033b500fb309d"
CANONICAL = {   # the start state recorded on 2026-11-22: sha256 of the "sha256  path" listing of every file
    "sample/expense-approvals": (56, "5d0f4f90636b9338dcd37c8cbf7850eba73acb64d6ce4b9f7889e704296082ad"),
    "tests/fixtures/sample-workspace": (71, "66c8fa406b2d3cfd71d5bc5ae20dcb8a9de661a4a18ecb7d0c41e25921ddb11b"),
}
REPO = "sct-will/carrydown-sample"    # the plan's repository, as the in-memory mock knows it. Nothing reaches GitHub
BOARD_ID = "PVT_sample"
PLACEHOLDER = "ghp_" + "Z" * 36       # the fixed placeholder the repository's mock tests use. It is not a credential
WI09 = P.WI09
WI04 = "docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md"
SKILL_DIR = "docs/dev/skills/expense-approvals-dev"
HUMAN_BODY = "\n\nNote from a person: the pilot team asked to see the export before the readout.\n"
HUMAN_COMMENT = "A person's comment on this work item. It is not carrydown's text."
OLD_WORDING = ("When that rule changes, tell your agent. It finds the work the change may affect and brings the proposed updates "
               "together for your approval.")
NEW_WORDING = ("If the rule changes, tell the agent you plan with: “This changed: [describe the change].” It proposes updates "
               "to the work that may be affected and keeps engineer corrections that still fit. You review the changes before publication.")
STAGES = ("build", "baseline", "update", "release", "engineer", "verdict")
SCENARIO_TESTS = (   # tests/field_run/test_field_run_kit.py, class RequestTraceScenarioTests
    "test_the_revision_changes_the_logging_rule_and_the_version_line_only",
    "test_the_word_revision_is_one_modified_block_in_section_4_2",
    "test_the_staged_decision_is_a_valid_overlay_committed_and_not_yet_released",
    "test_the_reviewed_checkpoint_is_recorded_before_the_release",
    "test_the_persona_and_the_sentence_carry_the_simulated_owner_answers",
    "test_the_known_patches_still_apply_to_the_sample_and_keep_the_decisions",
)
AUTHORIZED_FIX = {   # the citation-missing fix (branch reconcile-citation-missing), authorized in round 2
    "CHANGELOG.md", "scripts/reconcile.py", "skills/carrydown-ground-truth/scripts/reconcile.py",
    "skills/carrydown-plan-to-github/scripts/reconcile.py", "skills/carrydown-ground-truth/references/updates.md", "tests/test_reconcile.py",
    # pull request 47, the checkpoint creation-time fix found during this work
    "scripts/workspace.py", "skills/carrydown-ground-truth/scripts/workspace.py", "skills/carrydown-plan-to-github/scripts/workspace.py",
    "tests/test_source_checkpoint.py",
}


class StageFailure(Exception):
    pass


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def fingerprint(rel):
    """(file count, digest) of a canonical folder: the sha256 of its "sha256  path" listing, sorted by path."""
    root = ROOT / rel
    files = sorted((p.relative_to(root).as_posix(), p) for p in root.rglob("*") if p.is_file())
    listing = "".join(f"{sha(p.read_bytes())}  {rel}/{name}\n" for name, p in files)
    return len(files), sha(listing)


def fingerprints():
    return {rel: {"files": n, "sha256": d} for rel, (n, d) in ((rel, fingerprint(rel)) for rel in CANONICAL)}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def decisions_section(text):
    """The bytes from the heading "## Decisions recorded" to the end of the file."""
    at = text.find("\n## Decisions recorded\n")
    return None if at < 0 else text[at + 1:]


class Run:
    """One run folder and the evidence of one stage."""

    def __init__(self, folder, stage):
        self.dir = Path(folder).resolve()
        self.stage = stage
        self.evidence = self.dir / "evidence" / stage
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.n = len(list(self.evidence.glob("[0-9][0-9][0-9]-*.txt")))
        self.codes_file = self.evidence / "exit-codes.json"
        self.codes = read_json(self.codes_file) if self.codes_file.is_file() else []
        self.manifest = read_json(self.dir / "field-run.json") if (self.dir / "field-run.json").is_file() else {}
        self.project = self.dir / "project"
        self.home = self.dir / "home"
        self.gt = self.dir / "install" / "carrydown-ground-truth" / "scripts"
        self.pub = self.dir / "install" / "carrydown-plan-to-github" / "scripts"
        self.workspace = (self.dir / self.manifest["workspace"]).resolve() if self.manifest.get("workspace") else None
        self.state_file = self.dir / "evidence" / "state.json"
        self.state = read_json(self.state_file) if self.state_file.is_file() else {}

    def save_state(self, **kv):
        self.state.update(kv)
        write_json(self.state_file, self.state)

    def record(self, name, argv, cwd, code, out, err, expect):
        self.n += 1
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]
        path = self.evidence / f"{self.n:03d}-{slug}.txt"
        shown = " ".join(str(a) for a in argv).replace(str(self.dir), "DIR")
        path.write_bytes((f"$ {shown}\ncwd: {str(cwd).replace(str(self.dir), 'DIR')}\nexit: {code}\nexpected: {list(expect)}\n"
                          f"--- stdout\n{out}--- stderr\n{err}").encode("utf-8"))
        self.codes.append({"step": self.n, "name": name, "exit": code, "expected": list(expect), "file": path.relative_to(self.dir).as_posix()})
        write_json(self.codes_file, self.codes)
        mark = "ok  " if code in expect else "FAIL"
        print(f"  {mark} [{code}] {name}")
        if code not in expect:
            raise StageFailure(f"{name}: exit {code}, expected {list(expect)}. Evidence: {path}\n{(out + err)[-1500:]}")
        return path

    def env(self, home=None):
        return P.run_env(home or self.home)

    def cmd(self, name, argv, cwd=None, expect=(0,), home=None):
        cwd = cwd or self.project
        argv = [str(a) for a in argv]
        out = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, env=self.env(home), timeout=600)
        self.record(name, argv, cwd, out.returncode, out.stdout, out.stderr, expect)
        return out.stdout

    def py(self, name, script, *args, expect=(0,), cwd=None, home=None):
        return self.cmd(name, [sys.executable, script] + list(args), cwd=cwd, expect=expect, home=home)

    def git(self, name, *args, cwd=None, expect=(0,), home=None):
        return self.cmd(name, ["git"] + list(args), cwd=cwd, expect=expect, home=home)

    def call(self, name, fn, argv, expect=(0,)):
        """An installed script's public entry point, in this process (the mock lives here)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = fn(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 2
        code = 0 if code is None else code
        self.record(name, ["(entry point)", fn.__module__ + "." + fn.__name__] + argv, self.project, code, out.getvalue(), err.getvalue(), expect)
        return out.getvalue()


# ---------------------------------------------------------------------------
# The loopback service mock, kept between stages in DIR/mock/state.pickle
# ---------------------------------------------------------------------------

class Mock:
    """The in-memory GitHub mock on 127.0.0.1, with the installed publishing scripts pointed at it. Any attempt to
    reach another host is refused and recorded."""

    def __init__(self, run):
        self.run = run
        self.file = run.dir / "mock" / "state.pickle"
        self.attempts = []

    def __enter__(self):
        # imported once per process from the installed skill, and patched in place for each session: the modules
        # the publishing scripts import keep their references to these same module objects
        sys.path.insert(0, str(self.run.pub))
        loaded = sys.modules.get("github_client")
        if loaded is not None and not str(getattr(loaded, "__file__", "")).startswith(str(self.run.pub)):
            raise StageFailure("the publishing scripts of another folder are already loaded in this process")
        self.G = importlib.import_module("github_client")
        self.GS = importlib.import_module("github_sync")
        self.GP = importlib.import_module("github_project")
        RGH = importlib.import_module("release_github")
        import mockgh
        self.M = mockgh
        mockgh.S.__init__()
        if self.file.is_file():
            mockgh.S.__dict__.update(pickle.loads(self.file.read_bytes()))
        else:
            mockgh.S.repos.add(REPO)
            mockgh.S.repo_ids = {REPO: 4200}
            board = mockgh.add_project("Expense approvals plan")
            board["id"] = BOARD_ID
        self.server, url = mockgh.start()
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(mock.patch.dict(os.environ, {"CARRYDOWN_GITHUB_TOKEN": PLACEHOLDER, "HOME": str(self.run.home),
                                                              "USERPROFILE": str(self.run.home)}))
        self.stack.enter_context(mock.patch.object(time, "sleep", lambda s: None))
        self.stack.enter_context(mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"))
        self.stack.enter_context(mock.patch.object(self.G.GitHub.__init__, "__defaults__", (url, 0.0, None)))
        # a copy of the Net guard of tests/scenario_embedded_release.py: importing that module loads the repository's own scripts,
        # which would shadow the installed skill's copies in this process
        real_connect, real_create = socket.socket.connect, socket.create_connection
        loop = ("127.0.0.1", "::1", "localhost")

        def connect(sock, address, *a, **k):
            if not isinstance(address, tuple) or address[0] in loop:
                return real_connect(sock, address, *a, **k)
            self.attempts.append(str(address[0]))
            raise OSError("the validation forbids network access")

        def create(address, *a, **k):
            if address[0] in loop:
                return real_create(address, *a, **k)
            self.attempts.append(str(address[0]))
            raise OSError("the validation forbids network access")
        self.stack.enter_context(mock.patch.object(socket.socket, "connect", connect))
        self.stack.enter_context(mock.patch.object(socket, "create_connection", create))
        return self

    def __exit__(self, *exc):
        self.stack.close()
        self.server.shutdown()
        self.server.server_close()
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_bytes(pickle.dumps(dict(self.M.S.__dict__)))
        net = self.run.dir / "evidence" / "network-attempts.json"
        before = read_json(net) if net.is_file() else []
        write_json(net, before + [{"stage": self.run.stage, "host": h} for h in self.attempts])
        sys.path.remove(str(self.run.pub))
        return False

    def sync(self, name, *args, expect=(0,)):
        return self.run.call(name, self.GS.run, ["--root", str(self.run.project)] + list(args), expect=expect)

    def board(self, name, *args, expect=(0,)):
        return self.run.call(name, self.GP.run, ["--root", str(self.run.project)] + list(args), expect=expect)

    def issues(self):
        """{plan key: {"number", "title", "body_sha256", "comments"}} read back from the mock."""
        out = {}
        for i in self.M.S.issues:
            m = re.search(r"<!-- carrydown:([A-Za-z0-9-]+) -->", i.get("body") or "")
            if m:
                comments = [c.get("body", "") for c in self.M.S.comments.get(i["number"], [])] if isinstance(self.M.S.comments, dict) else []
                out[m.group(1)] = {"number": i["number"], "title": i["title"], "body_sha256": sha(i.get("body") or ""), "comments": len(comments)}
        return out

    def issue(self, key):
        return next(i for i in self.M.S.issues if f"<!-- carrydown:{key} -->" in (i.get("body") or ""))


def publish(run, m, label):
    """The publishing skill's steps 4 and 5 against the mock: preflight, dry run, apply, verify, board, read-back."""
    m.sync(f"{label}: preflight (mock)", "--preflight")
    m.sync(f"{label}: issues dry run (mock)")
    m.sync(f"{label}: issues apply (mock)", "--apply")
    m.sync(f"{label}: issues verify (mock)", "--verify")
    m.board(f"{label}: board dry run (mock)")
    m.board(f"{label}: board apply (mock)", "--apply")
    m.board(f"{label}: board verify (mock)", "--verify")
    readback = {"label": "local service mock result, not a GitHub publication", "issues": m.issues(),
                "board_items": sum(len(p.get("items", [])) for p in m.M.S.projects), "boards": len(m.M.S.projects)}
    write_json(run.evidence / "mock-readback.json", readback)
    return readback


def journal_state(run, rid):
    path = run.workspace / "publication" / f"{rid}.journal.json"
    if not path.is_file():
        return None, {}
    data = read_json(path)
    return path, {k: v.get("state") for k, v in data.get("targets", {}).items()}


def release_cycle(run, label, message):
    """release.py prepare, local test approval and export (each a dry run first), then commit and push."""
    rel = run.pub / "release.py"
    board = ["--board-owner-id", "4400", "--board-project-id", BOARD_ID]
    run.py(f"{label}: release prepare dry run", rel, "prepare", "--root", ".", "--repository-id", "4200", *board)
    out = run.py(f"{label}: release prepare", rel, "prepare", "--root", ".", "--repository-id", "4200", *board, "--apply")
    rid = next((ln.split(":", 1)[1].split()[0] for ln in out.splitlines() if ln.startswith("request id (permission):")), None)
    if not rid:
        raise StageFailure("no request id in the output of release.py prepare")
    run.py(f"{label}: local test approval dry run", rel, "approve", "--root", ".", "--request", rid, "--local", "--preview-shown")
    run.py(f"{label}: local test approval", rel, "approve", "--root", ".", "--request", rid, "--local", "--preview-shown", "--apply")
    run.py(f"{label}: export dry run", rel, "export", "--root", ".", "--request", rid)
    run.py(f"{label}: export", rel, "export", "--root", ".", "--request", rid, "--apply")
    run.git(f"{label}: released files before commit", "status", "--porcelain")
    run.git(f"{label}: commit", "add", "-A")
    run.git(f"{label}: commit", "commit", "-q", "-m", message)
    run.git(f"{label}: push to the local origin", "push", "-q", "origin", "main")
    commit = run.git(f"{label}: commit id", "rev-parse", "HEAD").strip()
    run.git(f"{label}: nothing unpushed", "log", "origin/main..HEAD", "--oneline")
    return rid, commit


def check_context(run, name, checkout, item, expect=(0,), refresh=True):
    script = checkout / SKILL_DIR / "scripts" / "check_context.py"
    args = [item] + ([] if refresh else ["--no-refresh"])
    return run.py(name, script, *args, cwd=checkout, expect=expect, home=run.dir / "engineer-home")


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def stage_build(out):
    out = Path(out).expanduser().resolve()
    if str(out).startswith(str(ROOT) + os.sep):
        raise StageFailure("the run folder must be outside the repository")
    before = fingerprints()
    code, text = 0, io.StringIO()
    with contextlib.redirect_stdout(text), contextlib.redirect_stderr(text):
        code = P.main(["--out", str(out), "--scenario", "request-trace"])
    if code != 0:
        print(text.getvalue())
        raise StageFailure(f"prepare_field_run.py exited {code}")
    write_json(out / "fingerprints.json", {"taken": now(), "before": before,
                                           "canonical": {k: {"files": n, "sha256": d} for k, (n, d) in CANONICAL.items()}})
    run = Run(out, "build")
    run.record("prepare the run folder (request-trace scenario)", ["prepare_field_run.py", "--out", "DIR", "--scenario", "request-trace"],
               ROOT, code, text.getvalue(), "", (0,))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
    versions = {}
    for name in P.SKILLS:
        m = re.search(r'version: "([^"]+)"', (out / "install" / name / "SKILL.md").read_text(encoding="utf-8"))
        versions[name] = m.group(1) if m else None
    write_json(run.dir / "evidence" / "environment.json", {"execution_revision": head, "skills": versions, "python": sys.version.split()[0],
                                                           "created": now()})
    run.py("status after the build", run.gt / "reconcile.py", "status", "--root", ".")
    print(f"build: {out}")
    return 0


def stage_baseline(folder):
    run = Run(folder, "baseline")
    rid, commit = release_cycle(run, "baseline", "Release the plan with the staged WI-09 decision")
    with Mock(run) as m:
        readback = publish(run, m, "baseline")
        path, states = journal_state(run, rid)
        if not path or not states or set(states.values()) != {"completed"}:
            raise StageFailure(f"the publication journal of {rid[:12]} is not complete: {states}")
        # a person edits the WI-09 issue outside its managed region and comments on it
        issue = m.issue("WI-09")
        issue["body"] = (issue.get("body") or "") + HUMAN_BODY
        m.M.S.add_comment(issue["number"], HUMAN_COMMENT, login="a-person")
        write_json(run.evidence / "human-content.json", {"issue": issue["number"], "body_addition": HUMAN_BODY, "comment": HUMAN_COMMENT})
    run.py("status after the baseline release", run.gt / "reconcile.py", "status", "--root", ".")
    # the engineers: separate checkouts of the origin, with no owner workspace
    for name, item in (("engineer-a", "WI-09"), ("engineer-b", "WI-04")):
        dest = run.dir / name
        run.git(f"{name}: clone the origin", "clone", "-q", str(run.dir / "origin.git"), str(dest), cwd=run.dir, home=run.dir / "engineer-home")
        run.git(f"{name}: identity", "config", "user.name", "Test Engineer", cwd=dest, home=run.dir / "engineer-home")
        run.git(f"{name}: identity", "config", "user.email", "engineer@example.invalid", cwd=dest, home=run.dir / "engineer-home")
        (dest / "local-notes.txt").write_bytes(f"Local work in progress on {item}. Not committed.\n".encode("utf-8"))
        text = check_context(run, f"{name}: work-item check for {item} (before)", dest, item)
        cache = dest / ".carrydown" / "cache"
        files = sorted(p for p in cache.rglob("*") if p.is_file()) if cache.is_dir() else []
        if not files:
            raise StageFailure(f"{name}: the check recorded no baseline cache")
        if f"approved context for {item} is ready" not in text:
            raise StageFailure(f"{name}: the check did not say the context is ready")
    (run.dir / "evidence" / "baseline-commit.txt").write_bytes((commit + "\n").encode("utf-8"))
    run.save_state(baseline_request=rid, baseline_commit=commit, baseline_issues=readback["issues"])
    print(f"baseline: request {rid[:12]}, commit {commit[:12]}, {len(readback['issues'])} issues on the mock")
    return 0


def stage_update_mechanical(folder):
    run = Run(folder, "update")
    gt = run.gt

    class Logged(MR.Runner):
        def run(self, *args, expect=(0,)):
            cmd = [sys.executable, str(self.helper), "--", "python3"] + [str(a) for a in args]
            out = subprocess.run(cmd, cwd=str(self.project), capture_output=True, text=True)
            self.log.append((args, out.returncode))
            name = " ".join(str(a) for a in args[:2]).replace(str(gt) + "/", "")
            run.record(name, cmd, self.project, out.returncode, out.stdout, out.stderr, expect)
            return out.stdout

    r = Logged(run.dir)
    revised = f"../revision/{run.manifest['revised_file']}"
    r.run(gt / "check_python.py")
    r.script("reconcile.py", "status", "--root", ".")
    r.script("render_ground_truth.py", revised, "--root", ".", "--version", "0.4", "--dry-run")
    r.script("render_ground_truth.py", revised, "--root", ".", "--version", "0.4")
    r.script("reconcile.py", "status", "--root", ".")
    r.script("reconcile.py", "prepare", "--root", ".")
    made = r.script("reconcile.py", "prepare", "--root", ".", "--apply")
    m = re.search(r"^proposal: ([0-9a-f]{64})$", made, re.M)
    if not m:
        raise StageFailure("no proposal id in the output of reconcile.py prepare")
    pid = m.group(1)
    folder_p = run.workspace / "drafts" / "proposals" / pid
    blocks = read_json(folder_p / "blocks.json")
    refs = [b.get("ref") for b in (blocks.get("blocks", blocks) if isinstance(blocks, dict) else blocks)]
    lead = [b for b in refs if b and b.startswith("architecture/4.2")]
    if len(lead) != 1:
        raise StageFailure(f"expected one changed block in section 4.2, the proposal has {refs}")
    block = lead[0]
    tmp = run.dir / "patches"
    tmp.mkdir(exist_ok=True)
    for n, (item, path, edits) in enumerate(KP.PATCHES):
        source = run.workspace / path[len("workspace/"):] if path.startswith("workspace/") else run.project / path
        try:
            text = KP.apply_edits(source.read_text(encoding="utf-8"), edits, path)
        except ValueError as e:
            raise StageFailure(str(e))
        new = tmp / f"{n:02d}-{Path(path).name}"
        new.write_bytes(text.encode("utf-8"))
        common = ["--root", ".", "--proposal", pid, "--block", block, "--item", item, "--path", path, "--from", new]
        r.script("reconcile.py", "patch", *common)
        r.script("reconcile.py", "patch", *common, "--apply")
    # every other block gets its one disposition in dispositions.json, the file the update path edits: the version
    # line is the only other change of the revision, and it states no requirement
    doc = read_json(folder_p / "dispositions.json")
    others = [rec["block"] for rec in doc["dispositions"] if rec.get("disposition") == "pending"]
    if others:
        for rec in doc["dispositions"]:
            if rec.get("disposition") == "pending":
                rec.update({"disposition": "no-impact",
                            "reason": "The version line of the document changed from 0.3 to 0.4. It states no requirement.",
                            "context": "Only section 4.2 item 6 changes an obligation. Its patches are filed under " + block + "."})
        (folder_p / "dispositions.json").write_bytes((json.dumps(doc, indent=2) + "\n").encode("utf-8"))
    write_json(run.evidence / "other-blocks.json", {"no_impact": others})
    write_json(run.evidence / "reviewed-unchanged.json", {"label": "mechanical mode: known reasons, not an agent's assessment", "items": KP.UNCHANGED})
    r.script("reconcile.py", "check", "--root", ".", "--proposal", pid)
    r.script("reconcile.py", "apply", "--root", ".", "--proposal", pid)
    r.script("reconcile.py", "apply", "--root", ".", "--proposal", pid, "--apply")
    descriptor = folder_p / "descriptor.json"
    prep = ["checkpoint", "prepare", "--root", ".", "--descriptor", descriptor, "--rendering-dir", "docs/ground-truth"]
    r.script("workspace.py", *prep)
    out = r.script("workspace.py", *prep, "--apply")
    c = re.search(r"checkpoint ([0-9a-f]{64})", out)
    if not c:
        raise StageFailure("no checkpoint id in the output of workspace.py checkpoint prepare")
    cid = c.group(1)
    r.script("workspace.py", "checkpoint", "commit", "--root", ".", "--id", cid)
    r.script("workspace.py", "checkpoint", "commit", "--root", ".", "--id", cid, "--apply")
    r.script("reconcile.py", "status", "--root", ".")
    r.script("check_specs.py", "--root", ".")
    shutil.copyfile(str(folder_p / "blocks.json"), str(run.evidence / "blocks.json"))
    shutil.copyfile(str(folder_p / "dispositions.json"), str(run.evidence / "dispositions.json"))
    run.save_state(update_mode="mechanical", proposal=pid, checkpoint=cid, block=block)
    print(f"update (mechanical): proposal {pid[:12]}, checkpoint {cid[:12]}")
    return 0


def stage_update_agent(folder):
    run = Run(folder, "update")
    print("Agent mode: this driver runs nothing in this mode.")
    print(f"1. Start a fresh coding agent with {run.dir / 'OWNER_AGENT_BRIEF.md'} as its instructions and {run.dir} as its folder.")
    print("   The owner's sentence and the simulated answers are in the brief and in persona.md. Give it no list of patches.")
    print(f"2. When transcript/notes.md ends with DONE, write what the agent found and missed to {run.dir / 'evidence' / 'agent-assessment.md'}.")
    print(f"3. Continue with: python3 {Path(__file__).resolve()} release --dir {run.dir}")
    run.save_state(update_mode="agent")
    return 0


def stage_release(folder):
    run = Run(folder, "release")
    if "baseline_issues" not in run.state:
        raise StageFailure("run the baseline stage first")
    rid, commit = release_cycle(run, "update release", "Release the accepted update of the logging rule")
    with Mock(run) as m:
        readback = publish(run, m, "update release")
        path, states = journal_state(run, rid)
        if not path or set(states.values()) != {"completed"}:
            raise StageFailure(f"the publication journal of {rid[:12]} is not complete: {states}")
        human = read_json(run.dir / "evidence" / "baseline" / "human-content.json")
        issue = m.issue("WI-09")
        comments = [c.get("body") for c in m.M.S.comments.get(issue["number"], [])]
        facts = {"same_numbers": {k: v["number"] for k, v in readback["issues"].items()} == {k: v["number"] for k, v in run.state["baseline_issues"].items()},
                 "same_count": len(readback["issues"]) == len(run.state["baseline_issues"]),
                 "human_body_kept": HUMAN_BODY.strip() in (issue.get("body") or ""),
                 "human_comment_kept": HUMAN_COMMENT in comments,
                 "issue": human["issue"] == issue["number"],
                 "wi09_issue_body_updated": readback["issues"]["WI-09"]["body_sha256"] != run.state["baseline_issues"]["WI-09"]["body_sha256"]}
        write_json(run.evidence / "mock-identity.json", dict(facts, label="local service mock result"))
    contexts = {}
    receipt = read_json(run.project / "docs" / "release" / f"{rid}.receipt.json")
    write_json(run.evidence / "receipt-summary.json", {k: receipt.get(k) for k in ("state", "supersedes", "created", "content_manifest_sha256")})
    for n in ("07", "08", "09"):
        ctx = run.project / "docs" / "context" / f"wi-{n}.md"
        contexts[f"WI-{n}"] = ctx.is_file() and KP.NEW_RULE in ctx.read_text(encoding="utf-8")
    write_json(run.evidence / "contexts.json", contexts)
    run.save_state(update_request=rid, update_commit=commit, update_issues=readback["issues"], release_facts=facts, contexts=contexts)
    bad = [k for k, v in list(facts.items()) + list(contexts.items()) if not v]
    if bad:
        raise StageFailure("release facts that do not hold: " + ", ".join(bad))
    print(f"release: request {rid[:12]}, commit {commit[:12]}")
    return 0


def stage_engineer(folder):
    run = Run(folder, "engineer")
    if "update_request" not in run.state:
        raise StageFailure("run the release stage first")
    eng = run.dir / "engineer-a"
    cache = eng / ".carrydown" / "cache"
    before = {p.relative_to(eng).as_posix(): sha(p.read_bytes()) for p in sorted(cache.rglob("*")) if p.is_file()}
    head_before = run.git("engineer-a: checkout head before", "rev-parse", "HEAD", cwd=eng).strip()
    # 2: the refresh fetches the updated origin. The superseded inputs in the working tree must not pass as current
    refused = check_context(run, "engineer-a: check WI-09 before obtaining the update (refusal expected)", eng, "WI-09", expect=(11,))
    after_refusal = {p.relative_to(eng).as_posix(): sha(p.read_bytes()) for p in sorted(cache.rglob("*")) if p.is_file()}
    # 3: the normal git workflow, keeping local work
    run.git("engineer-a: local work before the pull", "status", "--porcelain", cwd=eng, home=run.dir / "engineer-home")
    run.git("engineer-a: pull the approved update", "pull", "-q", "--ff-only", cwd=eng, home=run.dir / "engineer-home")
    # 4 and 5
    changed = check_context(run, "engineer-a: check WI-09 after the update", eng, "WI-09")
    # 6
    repeat = check_context(run, "engineer-a: check WI-09 again with no change", eng, "WI-09")
    spec_text = (eng / WI09).read_text(encoding="utf-8")
    ctx_text = (eng / "docs" / "context" / "wi-09.md").read_text(encoding="utf-8") if (eng / "docs" / "context" / "wi-09.md").is_file() else ""
    # the engineer on an item that needed no change
    engb = run.dir / "engineer-b"
    b_before = check_context(run, "engineer-b: check WI-04 before obtaining the update", engb, "WI-04", expect=(0, 11))
    b_before_code = run.codes[-1]["exit"]
    run.git("engineer-b: pull the approved update", "pull", "-q", "--ff-only", cwd=engb, home=run.dir / "engineer-home")
    b_after = check_context(run, "engineer-b: check WI-04 after the update", engb, "WI-04")
    b_repeat = check_context(run, "engineer-b: check WI-04 again with no change", engb, "WI-04")
    headline = "carrydown: approved inputs changed since your last check for {}"
    reassess = "Reassess your implementation plan against the current approved inputs before you write more code."
    facts = {
        "same_checkout": eng.is_dir() and bool(head_before) and bool(before),
        "refused_stale_before_fetching": "carrydown: the approved context for WI-09 is stale" in refused,
        "refusal_names_superseded": "(superseded)" in refused,
        "cache_unchanged_by_refusal": before == after_refusal,
        "local_work_kept": (eng / "local-notes.txt").is_file() and (engb / "local-notes.txt").is_file(),
        "ready_after_update": "carrydown: approved context for WI-09 is ready" in changed,
        "delta_headline": headline.format("WI-09") in changed,
        "spec_listed": f"changed: {WI09} (specification)" in changed,
        "context_listed": "changed: docs/context/wi-09.md (approved context)" in changed,
        "new_rule_in_delta": any(ln.startswith("+") and "request or scheduled job run" in ln for ln in changed.splitlines()),
        "reassess_line": reassess in changed,
        "new_rule_in_approved_context": KP.NEW_RULE in ctx_text,
        "entry_survives": spec_text.count(P.TRACE_ENTRY) == 1,
        "repeat_quiet": "carrydown: approved inputs changed" not in repeat and "carrydown: approved context for WI-09 is ready" in repeat,
        "cache_names_new_request": run.state["update_request"] in "".join(p.read_text(encoding="utf-8") for p in cache.rglob("*") if p.is_file()),
        "unchanged_item_ready_after_update": "carrydown: approved context for WI-04 is ready" in b_after,
        "unchanged_item_repeat_quiet": "carrydown: approved inputs changed" not in b_repeat,
    }
    observed = {"engineer_b_before_exit": b_before_code, "engineer_b_before_first_line": (b_before.splitlines() or [""])[0],
                "engineer_b_after_delta": headline.format("WI-04") in b_after,
                "engineer_b_after_changed_lines": [ln for ln in b_after.splitlines() if ln.startswith("changed: ")]}
    write_json(run.evidence / "engineer-facts.json", {"facts": facts, "observed": observed})
    run.save_state(engineer_facts=facts, engineer_observed=observed)
    bad = [k for k, v in facts.items() if not v]
    if bad:
        raise StageFailure("engineer facts that do not hold: " + ", ".join(bad))
    print("engineer: the same checkout refused the superseded inputs, then reported the changed approved inputs")
    return 0


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------

def repo_git(*args):
    out = subprocess.run(["git"] + list(args), cwd=str(ROOT), capture_output=True, text=True)
    return out.returncode, out.stdout


def test_names(text):
    return set(re.findall(r"^\s*def (test_\w+)", text, re.M))


def outputs(run, stage):
    """The saved command outputs of a stage, in order: [{"file", "exit", "expected", "stdout"}], read from the *.txt files."""
    out = []
    folder = run.dir / "evidence" / stage
    for path in sorted(folder.glob("[0-9][0-9][0-9]-*.txt")) if folder.is_dir() else []:
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^exit: (-?\d+)\nexpected: \[([^\]]*)\]\n--- stdout\n(.*?)--- stderr\n", text, re.M | re.S)
        if m:
            expected = [int(x) for x in m.group(2).split(",") if x.strip()]
            out.append({"file": path.relative_to(run.dir).as_posix(), "exit": int(m.group(1)), "expected": expected, "stdout": m.group(3)})
    return out


def output(run, stage, slug):
    """The last saved output of a stage whose file name ends with -<slug>.txt (the slug cut as record() cuts it), or None."""
    slug = slug[:60]
    hits = [o for o in outputs(run, stage) if o["file"].endswith(f"-{slug}.txt")]
    return hits[-1] if hits else None


def request_of(run, stage):
    # the same parse as rid_of in tests/scenario_embedded_release.py, which cannot be imported here (see the Net copy above)
    o = next((o for o in outputs(run, stage) if o["file"].endswith("-release-prepare.txt")), None)
    m = re.search(r"^request id \(permission\): ([0-9a-f]{64})", o["stdout"], re.M) if o else None
    return m.group(1) if m else None


def commit_of(run, stage):
    o = next((o for o in outputs(run, stage) if o["file"].endswith("-commit-id.txt")), None)
    return o["stdout"].strip() if o and re.fullmatch(r"[0-9a-f]{40}", o["stdout"].strip()) else None


def checkpoints(ws_yaml):
    """[{"id", "created", "sha256"}] of the checkpoints in workspace.yaml, read with a pattern (the file has a fixed layout)."""
    out = []
    for chunk in re.split(r"(?m)^  - id: ", ws_yaml)[1:]:
        cid = re.match(r'"?([0-9a-f]{64})"?', chunk)
        created = re.search(r'(?m)^    created: "([^"]+)"', chunk)
        digest = re.search(r'(?m)^        sha256: "([0-9a-f]{64})"', chunk)
        version = re.search(r'(?m)^        version: "([^"]*)"', chunk)
        if cid:
            out.append({"id": cid.group(1), "created": created.group(1) if created else "", "sha256": digest.group(1) if digest else None,
                        "version": version.group(1) if version else None})
    return out


def applied_proposal(run):
    """(change id, blocks, dispositions) of the newest proposal whose applied.json says applied, or (None, [], [])."""
    best = None
    folder = run.workspace / "drafts" / "proposals" if run.workspace else None
    for path in sorted(folder.glob("*/applied.json")) if folder and folder.is_dir() else []:
        try:
            data = read_json(path)
        except ValueError:
            continue
        if data.get("state") == "applied" and (best is None or str(data.get("time")) > str(best[0].get("time"))):
            best = (data, path.parent)
    if best is None:
        return None, [], []
    blocks = read_json(best[1] / "blocks.json")
    disp = read_json(best[1] / "dispositions.json")
    return best[1].name, (blocks.get("blocks", []) if isinstance(blocks, dict) else blocks), disp.get("dispositions", [])


def git_show(run, ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=str(run.project), capture_output=True, text=True).stdout


def stage_verdict(folder):
    run = Run(folder, "verdict")
    ev = lambda *p: "/".join(("evidence",) + p)  # noqa: E731
    rows = []

    def row(n, name, status, evidence, facts):
        rows.append({"row": n, "requirement": name, "status": status, "evidence": evidence, "facts": facts})

    # 1 isolation
    fp = read_json(run.dir / "fingerprints.json") if (run.dir / "fingerprints.json").is_file() else {}
    current = fingerprints()
    net = read_json(run.dir / "evidence" / "network-attempts.json") if (run.dir / "evidence" / "network-attempts.json").is_file() else []
    canonical = {k: {"files": n, "sha256": d} for k, (n, d) in CANONICAL.items()}
    f1 = {"before_equals_now": fp.get("before") == current, "now_equals_start_state": current == canonical, "network_attempts": len(net),
          "now": current}
    row(1, "Isolation", "pass" if f1["before_equals_now"] and f1["now_equals_start_state"] and not net else "fail",
        ["fingerprints.json", ev("network-attempts.json")], f1)

    # 2 actual source change, in either mode: the applied proposal, the accepted checkpoint and the rendering decide.
    # The transcript's command log is not read here: it may corroborate, it never decides
    pid, blocks, dispositions = applied_proposal(run)
    rendering_path = run.project / "docs" / "ground-truth" / "architecture.md"
    rendering_bytes = rendering_path.read_bytes() if rendering_path.is_file() else b""
    rendering = rendering_bytes.decode("utf-8", "replace")
    original = (ROOT / "sample" / "expense-approvals" / "docs" / "ground-truth" / "architecture.md").read_text(encoding="utf-8")
    heads = lambda t: [ln for ln in t.splitlines() if ln.startswith("#")]  # noqa: E731
    ws_yaml = (run.workspace / "workspace.yaml").read_text(encoding="utf-8") if run.workspace and (run.workspace / "workspace.yaml").is_file() else ""
    base_commit = commit_of(run, "baseline")
    base_time = subprocess.run(["git", "show", "-s", "--format=%cI", base_commit], cwd=str(run.project), capture_output=True,
                               text=True).stdout.strip() if base_commit else ""
    base_utc = dt.datetime.fromisoformat(base_time).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if base_time else ""
    later = [c for c in checkpoints(ws_yaml) if base_utc and c["created"] >= base_utc]
    newest = max(later, key=lambda c: c["created"]) if later else None
    f2 = {"applied_proposal": pid, "blocks": [{"ref": b.get("ref"), "formatting_only": b.get("formatting_only")} for b in blocks],
          "one_obligation_block": len(blocks) == 1 and blocks[0].get("ref") == "architecture/4.2" and blocks[0].get("formatting_only") is False,
          "baseline_commit_time": base_utc, "accepted_checkpoint": newest,
          "checkpoint_matches_rendering": bool(newest) and newest["sha256"] == sha(rendering_bytes),
          "new_rule_rendered": KP.NEW_RULE in rendering, "prohibition_kept": "They never carry amounts, comments or receipt contents." in rendering,
          "headings_unchanged": heads(rendering) == heads(original), "version_0_4": "version 0.4" in rendering.split("\n", 1)[0],
          "known_deferred": "the checkpoint records architecture version " + str(newest["version"] if newest else None)
                            + " beside the revised digest (render_ground_truth.py does not write the version into the plan)"}
    ok2 = all(f2[k] for k in ("applied_proposal", "one_obligation_block", "checkpoint_matches_rendering", "new_rule_rendered",
                              "prohibition_kept", "headings_unchanged", "version_0_4"))
    row(2, "Actual source change", "pass" if ok2 else "fail",
        [f"workspace drafts/proposals/{(pid or 'none')[:12]}/blocks.json", "workspace workspace.yaml", "project docs/ground-truth/architecture.md"], f2)

    # 3 agent assessment
    agent = run.dir / "evidence" / "agent-assessment.md"
    if agent.is_file() and agent.read_text(encoding="utf-8").strip():
        row(3, "Agent assessment", "pass", [ev("agent-assessment.md")], {"recorded": True})
    else:
        row(3, "Agent assessment", "not run", [], {"recorded": False, "note": "this run used the mechanical mode, a known-patch replay"})

    # 4 focused update
    # the patched items come from the applied proposal's update dispositions; each must have the revised rule in the approved
    # context the release compiler built, and the receipt must list that context with its digest
    f4, ok4 = {}, False
    base, after = commit_of(run, "baseline"), commit_of(run, "release")
    rid_after = request_of(run, "release")
    patched = sorted({str(p.get("item")) for d in dispositions if isinstance(d, dict) and d.get("disposition") == "update"
                      for p in (d.get("patch") if isinstance(d.get("patch"), list) else [d.get("patch")]) if isinstance(p, dict)})
    if base and after and rid_after and patched:
        receipt_path = run.project / "docs" / "release" / f"{rid_after}.receipt.json"
        receipt = read_json(receipt_path) if receipt_path.is_file() else {}
        listed = {a.get("path"): a.get("sha256") for a in receipt.get("artifacts", []) if isinstance(a, dict)}
        items = {}
        for item in patched:
            rel = f"docs/context/{item.lower()}.md"
            released = git_show(run, after, rel)
            items[item] = {"context_holds_rule": KP.NEW_RULE in released,
                           "context_listed_in_receipt": bool(released) and listed.get(rel) == sha(released.encode("utf-8"))}
        f4 = {"applied_proposal": pid, "patched_items": patched, "items": items, "receipt": receipt_path.relative_to(run.dir).as_posix(),
              "release_commit": after}
        ok4 = all(all(v.values()) for v in items.values())
    row(4, "Focused update", "pass" if ok4 else "fail",
        [f"workspace drafts/proposals/{(pid or 'none')[:12]}/dispositions.json", f4.get("receipt", "receipt missing")], f4)

    # 5 decision preservation
    f5 = {}
    if base and after:
        def entry_at(ref):
            text = subprocess.run(["git", "show", f"{ref}:{WI09}"], cwd=str(run.project), capture_output=True, text=True).stdout
            return decisions_section(text)
        b5, a5 = entry_at(base), entry_at(after)
        eng = (run.dir / "engineer-a" / WI09)
        e5 = decisions_section(eng.read_text(encoding="utf-8")) if eng.is_file() else None
        f5 = {"baseline_section_sha256": sha(b5 or ""), "after_section_sha256": sha(a5 or ""), "engineer_checkout_sha256": sha(e5 or ""),
              "entry_once": (b5 or "").count(P.TRACE_ENTRY) == 1, "placeholder_replaced": "None yet." not in (b5 or "None yet.")}
        ok5 = b5 is not None and b5 == a5 == e5 and f5["entry_once"] and f5["placeholder_replaced"]
    else:
        ok5 = False
    row(5, "Decision preservation", "pass" if ok5 else "fail", [ev("baseline-commit.txt"), ev("engineer", "engineer-facts.json")], f5)

    # 6 approval and publication
    # 6: re-derived from the saved command outputs, the receipts and journals the product wrote and the mock's own state
    f6 = {"label": "local service mock result, not a GitHub publication"}
    ok6 = True
    for label, prefix in (("baseline", "baseline"), ("release", "update-release")):
        rid = request_of(run, label)
        steps = {s: output(run, label, f"{prefix}-{s}") for s in ("local-test-approval", "export", "issues-apply-mock", "issues-verify-mock",
                                                                     "board-apply-mock", "board-verify-mock", "push-to-the-local-origin")}
        path, states = journal_state(run, rid) if rid else (None, {})
        receipt_path = run.project / "docs" / "release" / f"{rid}.receipt.json" if rid else None
        receipt = read_json(receipt_path) if receipt_path and receipt_path.is_file() else {}
        facts6 = {"request": (rid or "none")[:12], "steps_exit_0": {s: bool(o) and o["exit"] == 0 for s, o in steps.items()},
                  "receipt_written": bool(receipt), "receipt_request_matches": receipt.get("request_id") == rid,
                  "approval_recorded": bool(receipt.get("approval")),
                  "request_record": bool(rid) and (run.workspace / "requests" / rid).exists(),
                  "journal": path.relative_to(run.dir).as_posix() if path else None,
                  "journal_complete": bool(states) and set(states.values()) == {"completed"}, "journal_targets": len(states)}
        f6[label] = facts6
        ok6 = ok6 and bool(rid) and all(facts6["steps_exit_0"].values()) and all(facts6[k] for k in (
            "receipt_written", "receipt_request_matches", "approval_recorded", "request_record", "journal_complete"))
    rb_base = run.dir / "evidence" / "baseline" / "mock-readback.json"
    rb_after = run.dir / "evidence" / "release" / "mock-readback.json"
    pickle_file = run.dir / "mock" / "state.pickle"
    if rb_base.is_file() and rb_after.is_file() and pickle_file.is_file():
        before_issues, after_issues = read_json(rb_base)["issues"], read_json(rb_after)["issues"]
        mstate = pickle.loads(pickle_file.read_bytes())
        wi09 = next((i for i in mstate.get("issues", []) if "<!-- carrydown:WI-09 -->" in (i.get("body") or "")), None)
        comments = [c.get("body") for c in (mstate.get("comments", {}).get(wi09["number"], []) if wi09 else [])]
        identity = {"same_issue_numbers": {k: v["number"] for k, v in before_issues.items()} == {k: v["number"] for k, v in after_issues.items()},
                    "no_new_issue": len(mstate.get("issues", [])) == len(before_issues),
                    "wi09_body_updated": before_issues.get("WI-09", {}).get("body_sha256") != after_issues.get("WI-09", {}).get("body_sha256"),
                    "human_text_kept": bool(wi09) and HUMAN_BODY.strip() in (wi09.get("body") or ""),
                    "human_comment_kept": HUMAN_COMMENT in comments}
    else:
        identity = {"mock_readback": False}
    f6["mock_identity"] = identity
    ok6 = ok6 and all(identity.values())
    row(6, "Approval and publication", "pass" if ok6 else "fail",
        [ev("baseline"), ev("release"), ev("baseline", "mock-readback.json"), ev("release", "mock-readback.json"), "mock/state.pickle"], f6)

    # 7: re-derived from the saved outputs of the engineers' checks and from the checkout itself
    first = output(run, "baseline", "engineer-a-work-item-check-for-wi-09-before")
    refusal = output(run, "engineer", "engineer-a-check-wi-09-before-obtaining-the-update-refusal-expected")
    pulled = output(run, "engineer", "engineer-a-pull-the-approved-update")
    changed = output(run, "engineer", "engineer-a-check-wi-09-after-the-update")
    repeat = output(run, "engineer", "engineer-a-check-wi-09-again-with-no-change")
    b_after = output(run, "engineer", "engineer-b-check-wi-04-after-the-update")
    b_repeat = output(run, "engineer", "engineer-b-check-wi-04-again-with-no-change")
    eng = run.dir / "engineer-a"
    cache = eng / ".carrydown" / "cache"
    cache_text = "".join(p.read_text(encoding="utf-8") for p in cache.rglob("*") if p.is_file()) if cache.is_dir() else ""
    rid_base = request_of(run, "baseline")
    headline = "carrydown: approved inputs changed since your last check for {}"
    txt = lambda o: o["stdout"] if o else ""  # noqa: E731
    f7 = {
        "first_check_ready_with_baseline": bool(first) and first["exit"] == 0 and bool(rid_base) and f"baseline: request {rid_base}" in txt(first),
        "refused_before_fetching": bool(refusal) and refusal["exit"] == 11 and "carrydown: the approved context for WI-09 is stale" in txt(refusal)
                                   and "(superseded)" in txt(refusal),
        "pulled_with_git": bool(pulled) and pulled["exit"] == 0,
        "ready_after_update": bool(changed) and changed["exit"] == 0 and "carrydown: approved context for WI-09 is ready" in txt(changed),
        "baseline_names_new_request": bool(rid_after) and f"baseline: request {rid_after}" in txt(changed),
        "delta_headline": headline.format("WI-09") in txt(changed),
        "spec_listed": f"changed: {WI09} (specification)" in txt(changed),
        "context_listed": "changed: docs/context/wi-09.md (approved context)" in txt(changed),
        "new_rule_in_delta": any(ln.startswith("+") and "request or scheduled job run" in ln for ln in txt(changed).splitlines()),
        "reassess_line": "Reassess your implementation plan against the current approved inputs" in txt(changed),
        "repeat_quiet": bool(repeat) and repeat["exit"] == 0 and "carrydown: approved inputs changed" not in txt(repeat),
        "same_checkout_cache_names_new_request": bool(rid_after) and rid_after in cache_text,
        "local_work_kept": (eng / "local-notes.txt").is_file() and (run.dir / "engineer-b" / "local-notes.txt").is_file(),
        "new_rule_in_approved_context": (eng / "docs" / "context" / "wi-09.md").is_file()
                                        and KP.NEW_RULE in (eng / "docs" / "context" / "wi-09.md").read_text(encoding="utf-8"),
        "entry_survives": (eng / WI09).is_file() and (eng / WI09).read_text(encoding="utf-8").count(P.TRACE_ENTRY) == 1,
        "unchanged_item_ready_after_update": bool(b_after) and b_after["exit"] == 0 and "carrydown: approved context for WI-04 is ready" in txt(b_after),
        "unchanged_item_repeat_quiet": bool(b_repeat) and b_repeat["exit"] == 0 and "carrydown: approved inputs changed" not in txt(b_repeat),
    }
    observed7 = {"unchanged_item_changed_lines": [ln for ln in txt(b_after).splitlines() if ln.startswith("changed: ")]}
    row(7, "Engineer result", "pass" if all(f7.values()) else "fail", [ev("baseline"), ev("engineer"), "engineer-a/.carrydown/cache"],
        {"facts": f7, "observed": observed7})

    # 8 regression protection (repository state)
    code, start_files = repo_git("ls-tree", "-r", "--name-only", START_REVISION, "--", "tests")
    _, head_files = repo_git("ls-files", "--", "tests")
    removed = sorted(set(start_files.split()) - set(head_files.split())) if code == 0 else ["start revision not found"]
    lost = []
    for path in start_files.split():
        if path.endswith(".py") and (ROOT / path).is_file():
            _, old = repo_git("show", f"{START_REVISION}:{path}")
            gone = test_names(old) - test_names((ROOT / path).read_text(encoding="utf-8"))
            lost += [f"{path}:{t}" for t in sorted(gone)]
    retained = (FIELD / "test_field_run_kit.py").read_text(encoding="utf-8")
    m8 = re.search(r"^class RequestTraceScenarioTests\(.*?(?=^class |\Z)", retained, re.M | re.S)
    present = sorted(test_names(m8.group(0))) if m8 else []
    unit = subprocess.run([sys.executable, "-m", "unittest", "tests.field_run.test_field_run_kit"], cwd=str(ROOT), capture_output=True, text=True,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=900)
    (run.evidence / "retained-tests.txt").write_bytes((f"$ python3 -m unittest tests.field_run.test_field_run_kit\nexit: {unit.returncode}\n"
                                                       f"--- stdout\n{unit.stdout}--- stderr\n{unit.stderr}").encode("utf-8"))
    f8 = {"removed_test_files": removed, "removed_test_methods": lost, "scenario_tests": present,
          "scenario_tests_complete": set(SCENARIO_TESTS) <= set(present), "retained_suite_exit": unit.returncode,
          "retained_suite_summary": [ln for ln in unit.stderr.splitlines() if ln.startswith(("Ran ", "OK", "FAILED"))]}
    ok8 = not removed and not lost and f8["scenario_tests_complete"] and unit.returncode == 0
    row(8, "Regression protection", "pass" if ok8 else "fail", ["git ls-tree " + START_REVISION[:12], ev("verdict", "retained-tests.txt")], f8)

    # 9 surgical scope (repository state)
    code, names = repo_git("diff", "--name-only", START_REVISION, "--")
    _, untracked = repo_git("ls-files", "--others", "--exclude-standard")
    changed = sorted(set(names.split()) | set(untracked.split()))
    allowed = [p for p in changed if p.startswith("tests/field_run/") or p == "README.md" or p in AUTHORIZED_FIX]
    outside = sorted(set(changed) - set(allowed))
    row(9, "Surgical scope", "pass" if code == 0 and not outside else "fail", ["git diff --name-only " + START_REVISION[:12]],
        {"changed": changed, "outside_scope": outside})

    # 10 user burden (repository state)
    _, start_tree = repo_git("ls-tree", "-r", "--name-only", START_REVISION)
    new_files = sorted(set(changed) - set(start_tree.split()))
    burden = [p for p in new_files if p.startswith(("docs/", "website/", "sample/")) or p.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".mp4"))]
    _, old_readme = repo_git("show", f"{START_REVISION}:README.md")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    heads = lambda t: [ln for ln in t.splitlines() if ln.startswith("#")]  # noqa: E731
    f10 = {"new_files": new_files, "reader_facing_new_files": burden, "readme_headings_unchanged": heads(old_readme) == heads(readme),
           "no_sample_update_page": not (ROOT / "docs" / "sample-update.md").exists()}
    row(10, "User burden", "pass" if not burden and f10["readme_headings_unchanged"] and f10["no_sample_update_page"] else "fail",
        ["git diff --name-only " + START_REVISION[:12], "README.md"], f10)

    # 11 approved wording (repository state). The blog document is outside the repository and not checked here
    old_n, new_n = readme.count(OLD_WORDING), readme.count(NEW_WORDING)
    if old_n == 1 and new_n == 0 and readme == old_readme:
        status11, note = "pending", "the replacement is not applied yet; it follows the internal validation"
    elif new_n == 1 and old_n == 0 and readme.replace(NEW_WORDING, OLD_WORDING) == old_readme:
        status11, note = "pass", "exactly the approved replacement, nothing else changed in README.md"
    else:
        status11, note = "fail", "README.md differs from the start revision in more than the approved replacement"
    row(11, "Approved wording", status11, ["README.md"], {"old_sentence": old_n, "new_sentence": new_n, "note": note,
                                                         "blog": "specs/ is outside the repository: not checked by this harness"})

    # 12 honest limits: the results record states each kind of evidence for what it is
    # the mode comes from the run folder, not from state the update stage sets
    if (run.dir / "evidence" / "update" / "exit-codes.json").is_file():
        mode = "mechanical"
        mode_line = (f"Update stage mode: {mode}. The mechanical mode is a deterministic replay of known patches through the real update "
                     "commands. It is not evidence of an agent's discovery.")
    elif agent.is_file():
        mode = "agent"
        mode_line = (f"Update stage mode: {mode}. The update stage was an agent-led run recorded in evidence/agent-assessment.md. "
                     "The mechanical replay of known patches is separate evidence.")
    else:
        mode = "not run"
        mode_line = f"Update stage mode: {mode}."
    limits = [
        mode_line,
        "Agent assessment: " + ("recorded in evidence/agent-assessment.md." if rows[2]["status"] == "pass" else "not run in this run."),
        "Publication: local service mock on 127.0.0.1 (tests/mock/mockgh.py), not a GitHub publication. No live test was run.",
        "The token is a fixed placeholder that only the mock accepts. No credential was read.",
        "The expense service is not implemented. The application tests the specifications name were not run.",
    ]
    # row 12 is decided on results.md as written: it must name every limit the instructions require
    rows.append({"row": 12, "requirement": "Honest limits", "status": "pending", "evidence": ["results.md"], "facts": {}})
    elapsed = None
    starts = [c for s in STAGES[:-1] for c in [run.dir / "evidence" / s]]
    stamps = [p.stat().st_mtime for s in starts if s.is_dir() for p in s.iterdir()]
    if stamps:
        elapsed = round(max(stamps) - min(stamps), 1)

    def write_results(verdict):
        lines = ["# Update validation results", "", f"Run: `{run.dir.name}`. Mode: {mode}. Verdict: **{verdict}**. Elapsed: {elapsed} seconds.", "",
                 "| # | Requirement | Result | Evidence |", "| --- | --- | --- | --- |"]
        for r in rows:
            lines.append(f"| {r['row']} | {r['requirement']} | {r['status']} | {', '.join(r['evidence']) or 'none'} |")
        lines += ["", "## Limits", ""] + [f"- {s}" for s in limits] + [""]
        gaps = [r for r in rows if r["status"] == "fail"]
        if gaps:
            lines += ["## Failed rows", ""] + [f"- Row {r['row']}, {r['requirement']}: see `verdict.json`." for r in gaps] + [""]
        (run.dir / "results.md").write_bytes("\n".join(lines).encode("utf-8"))

    write_results("pending")
    written = (run.dir / "results.md").read_text(encoding="utf-8")
    required = {"mode": f"Update stage mode: {mode}." in written and mode in ("mechanical", "agent"),
                "mechanical_is_not_agent_evidence": mode != "mechanical" or "not evidence of an agent's discovery" in written,
                "agent_run_named": mode != "agent" or ("agent-led run recorded in evidence/agent-assessment.md" in written
                                                       and "mechanical replay of known patches is separate evidence" in written),
                "agent_assessment_state": ("Agent assessment: recorded" in written) if rows[2]["status"] == "pass" else ("Agent assessment: not run" in written),
                "mock": "local service mock" in written and "not a GitHub publication" in written,
                "no_live_run": "No live test was run." in written,
                "no_credential": "No credential was read." in written,
                "service_not_implemented": "The expense service is not implemented." in written}
    rows[-1].update(status="pass" if all(required.values()) else "fail", facts={"required_statements": required})
    applies = [r for r in rows if r["status"] not in ("not run", "pending")]
    verdict = "pass" if all(r["status"] == "pass" for r in applies) else "fail"
    out = {"verdict": verdict, "created": now(), "run": str(run.dir), "mode": mode, "elapsed_seconds": elapsed,
           "execution_revision": (read_json(run.dir / "evidence" / "environment.json") if (run.dir / "evidence" / "environment.json").is_file() else {}).get("execution_revision"),
           "rows": rows}
    write_json(run.dir / "verdict.json", out)
    write_results(verdict)
    for r in rows:
        print(f"  {r['row']:>2} {r['requirement']:<26} {r['status']}")
    print(f"verdict: {verdict} ({run.dir / 'verdict.json'})")
    return 0 if verdict == "pass" else 1


# ---------------------------------------------------------------------------

def guarded(fn, *args):
    try:
        return fn(*args)
    except StageFailure as e:
        print(f"stage failed: {e}", file=sys.stderr)
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="stage", required=True)
    b = sub.add_parser("build", help="the run folder and the canonical fingerprints")
    b.add_argument("--out", required=True)
    for name in ("baseline", "release", "engineer", "verdict"):
        s = sub.add_parser(name, help=f"the {name} stage")
        s.add_argument("--dir", required=True)
    u = sub.add_parser("update", help="the update stage")
    u.add_argument("--dir", required=True)
    u.add_argument("--mode", choices=("mechanical", "agent"), required=True)
    a = sub.add_parser("all", help="every stage in order")
    a.add_argument("--mode", choices=("mechanical",), required=True)
    a.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.stage == "build":
        return guarded(stage_build, args.out)
    if args.stage == "update":
        return guarded(stage_update_mechanical if args.mode == "mechanical" else stage_update_agent, args.dir)
    if args.stage == "all":
        out = Path(args.out).expanduser().resolve()
        start = time.time()
        steps = [("build", stage_build), ("baseline", stage_baseline), ("update", stage_update_mechanical), ("release", stage_release),
                 ("engineer", stage_engineer), ("verdict", stage_verdict)]
        for name, fn in steps:
            print(f"== {name}")
            code = guarded(fn, out)
            if code != 0:
                print(f"stopped at {name} (exit {code}) after {time.time() - start:.1f} seconds", file=sys.stderr)
                return code
        print(f"all stages finished in {time.time() - start:.1f} seconds")
        return 0
    fn = {"baseline": stage_baseline, "release": stage_release, "engineer": stage_engineer, "verdict": stage_verdict}[args.stage]
    return guarded(fn, args.dir)


if __name__ == "__main__":
    sys.exit(main())
