# Setup checks

Run these before the interview. Python is handled by the preflight, which can install it after a yes. For everything else, do not install software yourself. If something is missing, tell the user how to install it and stop until they say it is done.

## Python

Follow `references/preflight.md`. It detects the system, checks for Python 3.9 or later with `check_python.py`, and offers to install Python when it is missing. It is the one place where this skill installs software, and only after the person says yes. Word documents are read with the standard library, so no package is needed.

## Node.js

Node.js is needed only for the installer, not for the scripts. If it is missing, say so, but do not block.

## git

Run `git --version`, then `git rev-parse --is-inside-work-tree` in the project folder.

If the folder is not inside a git repository, explain why git matters: the plan, the specifications and every later change are kept in git, so each change is reviewed and can be undone. Ask whether to run `git init`. Run it only after a clear yes, and only in the project folder. Do not scaffold `docs/spec/` outside a git repository. The scaffold script also refuses, and says why.

If git is missing, the user installs it from [the Git website](https://git-scm.com), or on macOS through the same developer tools window.
