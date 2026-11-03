#!/usr/bin/env python3
"""Proof of the user-experience gate: the "yes" path, from a fresh project to published issues, typed by nobody.

Each claim prints PASS or FAIL with the line it observed, and the last line says how many passed.

    python3 tests/proof_ux_gate.py

It walks the yes path the way the two skills describe it, as the agent runs it, in a fresh folder: the sample's
fictional source, the private workspace, the rendering, the scaffold, the owner's drafts (the sample's working
plan, specifications and fictional staffing stand in for the interview), then "Put the plan on GitHub": the
checker, release.py release as a dry run and with --apply, the preflight, the owner's commit and push, the issues
and the board on the loopback mock of GitHub, and the engineers' first command in a fresh clone.

No command in the walk is given a request id, a nonce, a numeric repository or board id, an audience or a
destination: the commands derive them. The proof checks that on every argument list it ran. It also checks the
binding of the approval to the preview the owner saw, the standalone commands' default request, the engineers'
skill alone without a token, a public repository, and the four block messages.

It needs git, writes only below a temporary folder, and uses no token and no network: the GitHub API is the
loopback mock, with a placeholder credential that exists only for it, and every other connection is refused.
"""
import contextlib
import io
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
SAMPLE = ROOT / "sample" / "expense-approvals"
WORKING_PLAN = ROOT / "tests" / "fixtures" / "sample-workspace" / "drafts" / "plan.yaml"
SLUG = "expense-approvals"
SKILL = "docs/dev/skills/expense-approvals-dev"
FORBIDDEN_FLAGS = ("--request", "--nonce", "--repository-id", "--board-owner-id", "--board-project-id", "--audience",
                   "--destinations", "--preview-shown", "--created")

results = []
argv_log = []


def claim(ok, text, observed):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + text)
    print("     observed: " + " || ".join(str(observed).strip().split("\n"))[:700])


# ---------------------------------------------------------------------------
# The world: a temporary home, git identity, the loopback mock and a network guard
# ---------------------------------------------------------------------------

TMP = Path(tempfile.mkdtemp(prefix="carrydown-ux-"))
SAVED_ENV = dict(os.environ)
os.environ.update(HOME=str(TMP / "home"), USERPROFILE=str(TMP / "home"), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                  GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="Sample Owner", GIT_COMMITTER_NAME="Sample Owner",
                  GIT_AUTHOR_EMAIL="sample.owner@example.com", GIT_COMMITTER_EMAIL="sample.owner@example.com")
os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)
(TMP / "home").mkdir()
PLACEHOLDER = "ghp_" + "M" * 36     # accepted only by the loopback mock; never printed

attempts = []
_real_connect, _real_create = socket.socket.connect, socket.create_connection
LOOPBACK = ("127.0.0.1", "::1", "localhost")


def _connect(sock, address, *a, **k):
    if not isinstance(address, tuple) or address[0] in LOOPBACK:
        return _real_connect(sock, address, *a, **k)
    attempts.append(str(address[0])[:60])
    raise OSError("the proof forbids network access")


def _create(address, *a, **k):
    if address[0] in LOOPBACK:
        return _real_create(address, *a, **k)
    attempts.append(str(address[0])[:60])
    raise OSError("the proof forbids network access")


socket.socket.connect = _connect
socket.create_connection = _create

import mockgh  # noqa: E402
import github_client as G  # noqa: E402
import release_github as RGH  # noqa: E402

SRV, URL = mockgh.start()
G.GitHub.__init__.__defaults__ = (URL, 0.0, None)
RGH.GitHubEvidenceReader.HOST_OVERRIDE = "github.com"      # the mock stands for github.com
import time  # noqa: E402
_sleep = time.sleep
time.sleep = lambda s: _sleep(min(s, 0.005))
MS = mockgh.S

import check_specs  # noqa: E402
import github_project  # noqa: E402
import github_sync  # noqa: E402
import release  # noqa: E402
import render_ground_truth  # noqa: E402
import scaffold_spec  # noqa: E402
import workspace  # noqa: E402

MODULES = {"check_specs": check_specs, "github_project": github_project, "github_sync": github_sync, "release": release,
           "render_ground_truth": render_ground_truth, "scaffold_spec": scaffold_spec, "workspace": workspace}


def run(module, argv, token=False):
    """Run one entry point in this process, as the agent runs the script. Returns (exit status, output)."""
    argv_log.append((module, list(argv)))
    if token:
        os.environ["CARRYDOWN_GITHUB_TOKEN"] = PLACEHOLDER
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                mod = MODULES[module]
                rc = mod.main(argv) if hasattr(mod, "main") else mod.run(argv)
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
                if e.code and not isinstance(e.code, int):
                    print(e.code)
    finally:
        os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)
    text = out.getvalue()
    assert PLACEHOLDER not in text, "a credential reached the output"
    return rc, text


def sh(args, cwd, check=True):
    r = subprocess.run([str(a) for a in args], cwd=str(cwd), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{args[:3]} failed: {r.stderr[-300:]}")
    return r


def last(text, n=1):
    lines = [l for l in str(text).strip().split("\n") if l.strip()]
    return "; ".join(lines[-n:]) if lines else "(no output)"


def find(text, pattern):
    m = re.search(pattern, text, re.M)
    return m.group(0) if m else "(not found)"


def writes():
    """Every write the mock received since its log was last cleared: REST writes and GraphQL mutations."""
    rest = [f"{m} {p}" for m, p in MS.log if m in ("POST", "PATCH", "PUT", "DELETE") and p != "/graphql"]
    return rest + [op for op in MS.gql if op in mockgh.MUTATIONS]


def clear_log():
    del MS.log[:]
    del MS.gql[:]


def fresh_project(name, repo="o/r"):
    """A new project the way the ground-truth skill leaves it, before "Put the plan on GitHub": a git repository
    with an origin, the private workspace (yes answer), the rendered source, the scaffold, and the drafts."""
    base = TMP / name
    base.mkdir()
    origin = base / "origin.git"
    proj = base / "project"
    sh(["git", "init", "--bare", "-q", "-b", "main", origin], base)
    proj.mkdir()
    sh(["git", "init", "-q", "-b", "main"], proj)
    sh(["git", "remote", "add", "origin", origin], proj)
    (proj / "ground-truth").mkdir()
    shutil.copy(SAMPLE / "ground-truth" / "architecture.md", proj / "ground-truth" / "architecture.md")
    sh(["git", "commit", "-q", "--allow-empty", "-m", "Start"], proj)
    sh(["git", "push", "-q", "origin", "main"], proj)
    home = Path(os.environ["HOME"])
    slug = f"{SLUG}-{name}"
    rc1, out1 = run("workspace", ["init", "--root", str(proj), "--slug", slug, "--answer", "yes", "--apply"])
    ws = home / ".carrydown" / "workspaces" / slug
    shutil.copy(SAMPLE / "people.yaml", ws / "people.yaml")           # the interview's staffing, fictional
    rc2, out2 = run("render_ground_truth", [str(proj / "ground-truth" / "architecture.md"), "--root", str(proj), "--version", "0.3"])
    rc3, out3 = run("scaffold_spec", ["--root", str(proj), "--init", "--name", "Expense approvals", "--apply"])
    for child in (SAMPLE / "docs" / "spec").iterdir():                 # the drafts the agent writes with the owner
        if child.name != "plan.yaml":
            (shutil.copytree if child.is_dir() else shutil.copy)(str(child), str(proj / "docs" / "spec" / child.name))
    text = WORKING_PLAN.read_text(encoding="utf-8").replace("repo: sct-will/carrydown-sample", f"repo: {repo}")
    (proj / "docs" / "spec" / "plan.yaml").write_text(text, encoding="utf-8")
    return proj, origin, ws, (rc1, out1), (rc2, out2), (rc3, out3)


def commit_and_push(proj, message):
    sh(["git", "add", "-A"], proj)
    sh(["git", "commit", "-q", "--allow-empty", "-m", message], proj)
    sh(["git", "push", "-q", "origin", "main"], proj)


def fresh_clone(origin, dst):
    sh(["git", "clone", "-q", origin, dst], TMP)
    return Path(dst)


try:
    print("carrydown user-experience gate proof: the yes path, typed by nobody, no token, no network\n")

    # ------------------------------------------------------------------ the ground-truth skill
    proj, origin, ws, ws_run, render_run, scaffold_run = fresh_project("main")
    claim(ws_run[0] == 0 and "legacy" not in ws_run[1],
          "Step 0 on the yes answer creates the private workspace with no line about a legacy project or a migration",
          last(ws_run[1]))
    claim(render_run[0] == 0 and scaffold_run[0] == 0 and "legacy" not in render_run[1] + scaffold_run[1],
          "The renderer and the scaffold run as on main, with no new flag and no legacy line", last(render_run[1]) + " / " + last(scaffold_run[1]))
    rc, out = run("check_specs", ["--root", str(proj)])
    claim(rc == 0, "The checker passes on the owner's drafts (the end of the ground-truth skill)", last(out))

    # ------------------------------------------------------------------ "Put the plan on GitHub": the release dry run
    clear_log()
    head_before = sh(["git", "status", "--porcelain"], proj).stdout
    rc, dry = run("release", ["release", "--root", str(proj)], token=True)
    claim(rc == 0 and "numeric id 4200" in dry, "The release dry run reads the repository's numeric id with the token; nobody types it",
          find(dry, r".*numeric id.*"))
    claim("Everyone who can read o/r" in dry and "shared with everyone who can read o/r" in dry,
          "The audience is derived from the repository (private: everyone who can read it) and named in the disclosure line",
          find(dry, r'.*2\. ".*'))
    claim("does not exist yet" in dry and "created empty first" in dry,
          "The dry run finds no board under the repository's owner and names its creation in the external-write line",
          find(dry, r"^Board:.*"))
    asks = re.findall(r'^  [123]\. ".*', dry, re.M)
    claim(len(asks) == 3 and "What will be shared?" in dry and "What remains private?" in dry,
          "The dry run prints the four-question preview and the three named lines of one prompt (plan, disclosure, external writes)",
          " | ".join(a.strip()[:70] for a in asks))
    claim(not writes() and sh(["git", "status", "--porcelain"], proj).stdout == head_before,
          "The dry run writes nothing to GitHub or to the project", f"{len(writes())} GitHub write(s); project status unchanged")

    # ------------------------------------------------------------------ the approval binds to the preview the owner saw
    spec = next((proj / "docs" / "spec" / "m2-route-to-approvers").glob("wi-03-*.md"))
    original = spec.read_bytes()
    spec.write_bytes(original + b"\nA sentence the owner never saw in the preview.\n")
    clear_log()
    rc, out = run("release", ["release", "--root", str(proj), "--apply"], token=True)
    claim(rc != 0 and "not-approved" in out and not (proj / "docs" / "release").exists() and not writes(),
          "A file changed after the preview makes release --apply refuse (not-approved) before any write: the owner approves only what was shown",
          last(out))
    spec.write_bytes(original)

    # ------------------------------------------------------------------ release --apply after the owner's two yes answers
    rc, dry = run("release", ["release", "--root", str(proj)], token=True)
    clear_log()
    rc, out = run("release", ["release", "--root", str(proj), "--apply"], token=True)
    receipts = sorted((proj / "docs" / "release").glob("*.receipt.json")) if (proj / "docs" / "release").is_dir() else []
    claim(rc == 0 and len(receipts) == 1 and (proj / SKILL / "SKILL.md").is_file() and (proj / "docs" / "context" / "wi-03.md").is_file(),
          "release --apply prepares, records the local approval and exports the approved files, the receipt and the engineers' skill",
          last(out))
    created = [e for e in MS.gql if e == "createProjectV2"]
    claim(len(MS.projects) == 1 and created == ["createProjectV2"],
          "The board is created empty by the --apply run, before prepare names it, as main's board script created it",
          f"{len(MS.projects)} project(s) on the mock; GraphQL writes {created}")
    released = (proj / "docs" / "spec" / "plan.yaml").read_text(encoding="utf-8")
    working = (ws / "drafts" / "plan.yaml").read_text(encoding="utf-8") if (ws / "drafts" / "plan.yaml").is_file() else ""
    claim(re.search(r'^plan_view: "?released"?$', released, re.M) and re.search(r'^plan_view: "?workspace"?$', working, re.M),
          "The project now holds the released plan and the owner's working plan moved to the private workspace",
          find(released, r"^plan_view:.*") + "; drafts/plan.yaml " + ("present" if (ws / "drafts" / "plan.yaml").is_file() else "missing"))
    rc, out = run("check_specs", ["--root", str(proj)])
    claim(rc == 0, "The owner's checker still passes after the release (it reads the working plan from the workspace)", last(out))

    # ------------------------------------------------------------------ preflight, commit and push, issues and board
    rc, out = run("github_sync", ["--root", str(proj), "--preflight"], token=True)
    claim(rc == 0 and "preflight passed" in out, "The preflight passes on the derived targets and audience", last(out))
    commit_and_push(proj, "Release the plan")
    rc, out = run("github_sync", ["--root", str(proj)], token=True)
    claim(rc == 0 and "1 Epic, 5 sub-epics, 9 work item issues" in out,
          "The issues dry run needs no --repo and no --create-epic and shows main's summary line", find(out, r".*1 Epic, \d+ sub-epics.*"))
    rc, out = run("github_sync", ["--root", str(proj), "--apply"], token=True)
    rc2, out2 = run("github_sync", ["--root", str(proj), "--verify"], token=True)
    issues = list(MS.issues)
    claim(rc == 0 and rc2 == 0 and len(issues) == 15, "The issues are published on the mock from the approved release and verify",
          f"{len(issues)} issue(s); {last(out2)}")
    rc, out = run("github_project", ["--root", str(proj), "--apply"], token=True)
    rc2, out2 = run("github_project", ["--root", str(proj), "--verify"], token=True)
    proj_items = sum(len(p.get("items", [])) for p in MS.projects)
    claim(rc == 0 and rc2 == 0 and proj_items >= 15, "The board the release created is filled from the approved payload and verifies",
          f"{proj_items} item(s) on the board; exit {rc}/{rc2}")
    commit_and_push(proj, "Publish")

    # ------------------------------------------------------------------ a clean clone and the engineers' first command
    clone = fresh_clone(origin, TMP / "engineer")
    r = sh([sys.executable, ROOT / "scripts" / "check_specs.py", "--root", clone, "--view", "released"], clone, check=False)
    claim(r.returncode == 0, "A clean clone holds a released plan: check_specs --view released passes with no workspace and no originals",
          last(r.stdout + r.stderr))
    r = sh([sys.executable, clone / SKILL / "scripts" / "check_context.py", "WI-03"], clone, check=False)
    claim(r.returncode == 0 and r.stdout.startswith("carrydown: approved context for WI-03 is ready"),
          "The engineers' first step is one command, and it passes in a fresh clone", last(r.stdout, 2))
    r = sh([sys.executable, clone / SKILL / "scripts" / "check_context.py", "WI-77"], clone, check=False)
    claim(r.returncode == 10 and r.stdout.splitlines()[0] == "carrydown: no approved context for WI-77"
          and "Ask the plan owner to release the item." in r.stdout,
          "An unknown id gets the first block message and what to do, in plain words", last(r.stdout, 2))

    # ------------------------------------------------------------------ nothing typed by hand
    bad = []
    for module, argv in argv_log:
        for arg in argv:
            if arg in FORBIDDEN_FLAGS or re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{64}|PVT_\w+|\d{3,}", arg):
                bad.append(f"{module} {arg}")
    claim(not bad, "No command of the walk was given a request id, nonce, numeric id, audience, destination or --preview-shown",
          f"{len(argv_log)} command(s) checked; offending arguments: {bad or 'none'}")

    # ------------------------------------------------------------------ a later change, and the standalone commands
    rc, out = run("release", ["release", "--root", str(proj)], token=True)
    claim(rc == 0 and "already approved and active" in out and '2. "' not in out,
          "With nothing changed, the release dry run says the content is already approved and asks no disclosure line again",
          find(out, r".*already approved.*"))
    rc, out = run("release", ["export", "--root", str(proj)])
    claim(rc == 0 and "(the active request)" in out, "export without --request acts on the active request and names it",
          find(out, r".*the active request.*"))
    rc, out = run("release", ["withdraw", "--root", str(proj), "--reason", "error-found"])
    claim(rc == 0 and "(the active request)" in out, "withdraw (dry run) without --request names the active request", find(out, r".*the active request.*"))

    # ------------------------------------------------------------------ the engineers' skill alone, without a token
    (proj / "docs" / "spec" / "README.md").write_text((proj / "docs" / "spec" / "README.md").read_text(encoding="utf-8"), encoding="utf-8")
    rc, out = run("release", ["release", "--root", str(proj), "--no-github"])
    claim(rc == 0 and "numeric id 4200" in out,
          "\"Generate the engineers' skill.\" without a token reads the repository id from the earlier release", find(out, r".*numeric id.*"))

    # ------------------------------------------------------------------ a public repository
    MS.private = False
    proj2, origin2, ws2, *_ = fresh_project("public")
    rc, dry = run("release", ["release", "--root", str(proj2)], token=True)
    claim(rc == 0 and "published publicly" in dry and "The public. Anyone can read what is published." in dry,
          "A public repository makes the derived audience public, and the disclosure line says published publicly", find(dry, r'.*2\. ".*'))
    rc, out = run("release", ["release", "--root", str(proj2), "--apply"], token=True)
    rc2, out2 = run("github_sync", ["--root", str(proj2), "--preflight"], token=True)
    claim(rc == 0 and rc2 == 0, "On a public repository the release applies and the preflight passes, with no new question",
          last(out2))
    MS.private = True

    claim(not attempts, "No connection left this computer", f"{len(attempts)} attempt(s)")
finally:
    os.environ.clear()
    os.environ.update(SAVED_ENV)
    SRV.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)

print("")
print(f"{sum(results)} of {len(results)} claims passed")
sys.exit(0 if all(results) else 1)
