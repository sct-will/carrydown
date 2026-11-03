#!/usr/bin/env python3
"""Rebuild the sample's own "yes" path release and compare it with what the repository holds.

The sample project (sample/expense-approvals) has a release of its own: the owner's private workspace is
kept as a fixture in tests/fixtures/sample-workspace/ (releases, requests, events and the workspace
files, with no staffing record), and the receipt it exports is in sample/expense-approvals/docs/release/.
This script rebuilds that release from the sample in a temporary folder, with a fixed time, a fixed
request nonce and a fixed git identity, using the real scripts (release.py prepare, approve --local and
export), and checks that every byte is what the repository holds:

  the receipt          sample/expense-approvals/docs/release/<request id>.receipt.json
  the workspace files  releases/, requests/ and events/ of the fixture

so any change to a sample file, a template or a script that the release depends on is caught as drift.

  python3 tests/rebuild_sample_release.py --check    rebuild and compare (the default); exit 1 on drift
  python3 tests/rebuild_sample_release.py --write    rebuild and replace the fixture and the receipt

Run it from the repository root. It needs git, writes only below a temporary folder (and, with --write,
the two places above), and uses no token and no network.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
SAMPLE = ROOT / "sample" / "expense-approvals"
FIXTURE = ROOT / "tests" / "fixtures" / "sample-workspace"
CREATED = "2027-01-20T14:03:00Z"
APPROVED = "2027-01-20T14:10:00Z"
NONCE = "5a3f1c0e9b7d42a68c1e0f34d5b6a789"
REPOSITORY_ID = "4200"
BOARD = ["--board-owner-id", "4400", "--board-project-id", "PVT_sample"]
IDENTITY = ("Sample Owner", "sample.owner@example.com")
KEEP = ("releases", "requests", "events")
WORKSPACE_YAML = """format: 1
slug: expense-approvals
engineering_repo:
  path: "sample/expense-approvals"
  remote: ""
policy_version: 1
state: drafting
"""


def run(args, cwd, env):
    out = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(str(a) for a in args[:4])}\n{out.stdout}{out.stderr}")
    return out.stdout


def rebuild(base, sample=SAMPLE):
    """Rebuild in base from the sample project at sample. Returns (workspace folder, project folder, request id)."""
    base = Path(base)
    home = base / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull, PYTHONDONTWRITEBYTECODE="1")
    env.pop("CARRYDOWN_GITHUB_TOKEN", None)
    project = base / "project"
    shutil.copytree(sample, project, ignore=shutil.ignore_patterns("release", "__pycache__"))
    for stale in (project / "docs" / "release",):
        shutil.rmtree(stale, ignore_errors=True)
    run(["git", "init", "-q", "-b", "main"], project, env)
    run(["git", "config", "user.name", IDENTITY[0]], project, env)
    run(["git", "config", "user.email", IDENTITY[1]], project, env)
    workspace = base / "workspace"
    scripts = ROOT / "scripts"
    run([sys.executable, str(scripts / "workspace.py"), "init", "--root", str(project), "--slug", "expense-approvals", "--workspace", str(workspace), "--apply"],
        project, env)
    (workspace / "workspace.yaml").write_text(WORKSPACE_YAML, encoding="utf-8")       # the fixture's own, with no machine path in it
    (workspace / "people.yaml").unlink()                                                # no staffing record is part of the fixture
    release = [sys.executable, str(scripts / "release.py")]
    out = run(release + ["prepare", "--root", str(project), "--repository-id", REPOSITORY_ID, "--created", CREATED, "--nonce", NONCE, "--apply"] + BOARD, project, env)
    request_id = next(line.split(":", 1)[1].split()[0] for line in out.splitlines() if line.startswith("request id (permission):"))
    run(release + ["approve", "--root", str(project), "--request", request_id, "--local", "--preview-shown", "--created", APPROVED, "--apply"], project, env)
    run(release + ["export", "--root", str(project), "--request", request_id, "--apply"], project, env)
    return workspace, project, request_id


def files_of(folder, only=None):
    out = {}
    base = Path(folder)
    for p in sorted(base.rglob("*")):
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if only is None or rel.split("/")[0] in only:
                out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="rebuild and compare with the repository (the default)")
    mode.add_argument("--write", action="store_true", help="rebuild and replace the fixture and the receipt in the sample")
    ap.add_argument("--sample", default=str(SAMPLE), help="the sample project to rebuild from and compare with (default: the repository's own)")
    a = ap.parse_args(argv)
    sample = Path(a.sample).resolve()
    with tempfile.TemporaryDirectory(prefix="carrydown-sample-release-") as tmp:
        workspace, project, request_id = rebuild(tmp, sample)
        receipt_name = f"{request_id}.receipt.json"
        built_receipt = (project / "docs" / "release" / receipt_name).read_bytes()
        if a.write:
            shutil.rmtree(FIXTURE, ignore_errors=True)
            FIXTURE.mkdir(parents=True)
            for name in KEEP:
                shutil.copytree(workspace / name, FIXTURE / name)
            (FIXTURE / "workspace.yaml").write_text(WORKSPACE_YAML, encoding="utf-8")
            shutil.copy(workspace / "retention.yaml", FIXTURE / "retention.yaml")
            release_dir = sample / "docs" / "release"
            shutil.rmtree(release_dir, ignore_errors=True)
            release_dir.mkdir(parents=True)
            (release_dir / receipt_name).write_bytes(built_receipt)
            print(f"wrote the fixture and docs/release/{receipt_name}")
            return 0
        problems = []
        held = sorted(p.name for p in (sample / "docs" / "release").glob("*.receipt.json")) if (sample / "docs" / "release").is_dir() else []
        if held != [receipt_name]:
            problems.append(f"the sample holds receipt(s) {held or 'none'}, but the rebuilt release is {receipt_name}")
        elif (sample / "docs" / "release" / receipt_name).read_bytes() != built_receipt:
            problems.append("the receipt differs from the rebuilt one")
        built, held_files = files_of(workspace, KEEP), files_of(FIXTURE, KEEP)
        for rel in sorted(set(built) | set(held_files)):
            if built.get(rel) != held_files.get(rel):
                problems.append(f"fixture file differs or is missing: {rel}")
        for name in ("workspace.yaml", "retention.yaml"):
            if not (FIXTURE / name).is_file():
                problems.append(f"fixture file is missing: {name}")
        if (FIXTURE / "people.yaml").exists():
            problems.append("the fixture must hold no people.yaml")
        if problems:
            print("FAIL the sample's release is not reproducible from the repository")
            for line in problems[:20]:
                print("  " + line)
            print("Regenerate it with: python3 tests/rebuild_sample_release.py --write")
            return 1
        print(f"PASS the sample's release is reproducible: request {request_id}, receipt {len(built_receipt)} bytes, {len(held_files)} fixture file(s) unchanged")
        return 0


if __name__ == "__main__":
    sys.exit(main())
