#!/usr/bin/env python3
"""Run one command for a field run and log it.

prepare_field_run.py copies this script into the field-run folder. The owner's agent puts it in front of every
command:

  python3 RUN_FOLDER/run_logged.py -- python3 RUN_FOLDER/install/carrydown-ground-truth/scripts/reconcile.py status --root .

It runs the command in the current folder with HOME set to the run folder's own home folder, with no token in the
environment, and with the output passed through. It appends one line to transcript/commands.log:

  [2026-11-14T10:00:00Z] exit=0 $ python3 .../reconcile.py status --root .

and exits with the command's own exit code. `--now` prints the current UTC time in the same form, for the
agent's other transcript entries. Standard library only. No network.
"""
import datetime as dt
import os
import shlex
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv == ["--now"]:
        print(now())
        return 0
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("usage: run_logged.py -- COMMAND [ARGUMENTS...]   (or --now)", file=sys.stderr)
        return 2
    home = RUN / "home"
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home / "xdg"), GIT_CONFIG_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1")
    for name in ("CARRYDOWN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GIT_CONFIG_GLOBAL"):
        env.pop(name, None)
    try:
        out = subprocess.run(argv, env=env)
        code = out.returncode
    except FileNotFoundError:
        print(f"run_logged: command not found: {argv[0]}", file=sys.stderr)
        code = 127
    line = f"[{now()}] exit={code} $ {' '.join(shlex.quote(a) for a in argv)}\n"
    log = RUN / "transcript" / "commands.log"
    log.parent.mkdir(exist_ok=True)
    with open(str(log), "a", encoding="utf-8") as fh:
        fh.write(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
