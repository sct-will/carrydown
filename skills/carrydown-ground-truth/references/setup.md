# Setup checks

Run these before the interview. Do not install software yourself. If something is missing, tell the user how to install it and stop until they say it is done.

## Python

Run `python3 --version`. On Windows the command is often `python`, so try `python --version` there. Use whichever one prints Python 3.9 or later, and use that command for every script. Word documents are read with the standard library, so no package is needed.

If Python is missing or older than 3.9:

- macOS. The command may open a window offering the command line developer tools. Tell the user what the window is. They can click Install and wait a few minutes, or install Python from [the Python downloads page](https://www.python.org/downloads/). Then they run the check again.
- Windows. They install Python 3 from [the Python downloads page](https://www.python.org/downloads/) and tick "Add python.exe to PATH" on the first screen, then open a new terminal.
- Linux. They install `python3` with the system package manager, or ask their administrator to install it.

## Node.js

Node.js is needed only for the installer, not for the scripts. If it is missing, say so, but do not block.

## git

Run `git --version`, then `git rev-parse --is-inside-work-tree` in the project folder.

If the folder is not inside a git repository, explain why git matters: the plan, the specifications and every later change are kept in git, so each change is reviewed and can be undone. Ask whether to run `git init`. Run it only after a clear yes, and only in the project folder. Do not scaffold `docs/spec/` outside a git repository. The scaffold script also refuses, and says why.

If git is missing, the user installs it from [the Git website](https://git-scm.com), or on macOS through the same developer tools window.
