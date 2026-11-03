"""Helpers that build releases for the tests. Standard library only. No network.

  run(module, argv)           call a script's main() in this process, capture its output
  YesProject(base)            a copy of the sample with a private workspace, ready for the "yes" path
  NoProject(base, world)      a copy of the confidential fixture, enrolled in a fake organization, with a
                              local bare repository standing in for the engineering origin and another for staging

Both build the project in a temporary folder under base and keep every path they need as attributes.
"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import release as R  # noqa: E402
import workspace as W  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
CREATED = "2027-01-20T14:03:00Z"
NONCE = "00112233445566778899aabbccddeeff"


def run(main, argv, env=None, stdin=None):
    """(exit status, stdout, stderr) of main(argv) run in this process."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.ExitStack() as stack:
        stack.enter_context(contextlib.redirect_stdout(out))
        stack.enter_context(contextlib.redirect_stderr(err))
        if env:
            stack.enter_context(mock.patch.dict(os.environ, env))
        try:
            code = main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
            if isinstance(e.code, str):
                err.write(e.code)
    return (code or 0), out.getvalue(), err.getvalue()


def sh(args, cwd, check=True):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    run_ = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, env=env)
    if check and run_.returncode != 0:
        raise AssertionError(f"{args} failed: {run_.stderr}")
    return run_


def init_git(path, name="Test Owner", email="owner@example.com"):
    sh(["git", "init", "-q", "-b", "main"], path)
    sh(["git", "config", "user.name", name], path)
    sh(["git", "config", "user.email", email], path)


def bare_origin(base, name, files=None):
    """A bare repository with one commit on main, standing in for a remote. Returns its path."""
    bare = Path(base) / f"{name}.git"
    sh(["git", "init", "-q", "--bare", "-b", "main", str(bare)], base)
    seed = Path(base) / f"{name}-seed"
    seed.mkdir()
    init_git(seed)
    for rel, data in (files or {"README.md": b"seed\n"}).items():
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_bytes(data)
    sh(["git", "add", "-A"], seed)
    sh(["git", "commit", "-q", "-m", "seed"], seed)
    sh(["git", "remote", "add", "origin", str(bare)], seed)
    sh(["git", "push", "-q", "origin", "main"], seed)
    shutil.rmtree(seed)
    return bare


class YesProject:
    """The sample with a private workspace. prepare, approve and export are methods."""

    def __init__(self, base, repository_id=4200, board=False, git=True, board_project_id="PVT_example"):
        self.base = Path(base)
        self.root = self.base / "project"
        shutil.copytree(SAMPLE, self.root)
        if git:
            init_git(self.root)
        self.workspace = self.base / "workspace"
        code, out, err = run(W.main, ["init", "--root", str(self.root), "--slug", "sample-ws", "--workspace", str(self.workspace), "--apply"])
        assert code == 0, out + err
        self.repository_id = repository_id
        self.board = board
        self.board_project_id = board_project_id
        self.request_id = None

    def common(self):
        return ["--root", str(self.root)]

    def prepare(self, *extra, apply=True, nonce=NONCE, created=CREATED):
        argv = ["prepare"] + self.common() + ["--repository-id", str(self.repository_id)]
        if self.board:
            argv += ["--board-owner-id", "4400", "--board-project-id", self.board_project_id]
        if nonce:
            argv += ["--nonce", nonce]
        if created:
            argv += ["--created", created]
        argv += list(extra)
        if apply:
            argv.append("--apply")
        code, out, err = run(R.main, argv)
        if code == 0 and apply:
            for line in out.splitlines():
                if line.startswith("request id (permission):"):
                    self.request_id = line.split(":", 1)[1].split()[0]
        return code, out, err

    def approve(self, request_id=None, created="2027-01-20T14:10:00Z", apply=True, extra=()):
        argv = ["approve"] + self.common() + ["--request", request_id or self.request_id, "--local", "--created", created, "--preview-shown"]
        if apply:
            argv.append("--apply")
        return run(R.main, argv + list(extra))

    def export(self, request_id=None, apply=True):
        argv = ["export"] + self.common() + ["--request", request_id or self.request_id]
        if apply:
            argv.append("--apply")
        return run(R.main, argv)

    def release(self):
        """prepare, approve and export; returns the request id."""
        code, out, err = self.prepare()
        assert code == 0, out + err
        code, out, err = self.approve()
        assert code == 0, out + err
        code, out, err = self.export()
        assert code == 0, out + err
        return self.request_id


def strip_handling(root):
    """Make a copy of the sample a legacy project: no project.handling block, no plan format, and people who
    carry a name and a login again. The release gate then answers legacy and the GitHub scripts behave as
    they did before releases existed."""
    import re
    path = Path(root) / "docs" / "spec" / "plan.yaml"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?ms)^  handling:.*?(?=^\S|^  \S)", "", text, count=1)
    text = re.sub(r"(?m)^plan_(format|view):.*\n", "", text)
    text = re.sub(r"(?m)^  - id: (\w+)\n    track: (\w+)\n", lambda m: f'  - id: {m.group(1)}\n    name: "{m.group(1).title()}"\n    track: {m.group(2)}\n', text)
    path.write_text(text, encoding="utf-8")
