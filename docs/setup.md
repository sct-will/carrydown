# Setup from nothing

The long form of the [prerequisites line in the README](../README.md#prerequisites). It takes you from a computer with nothing installed to a project folder where you can install the carrydown skills. Pick your system. Each section says what to click or type and what you will see.

You need four things: a terminal, Node.js (only to run the install line), Python 3.9 or later (to run the scripts) and git (to keep the plan under version control). Everything here is free.

A note on version numbers. The skills installer needs Node.js 22.20 or later. Install the version marked LTS (long-term support) from https://nodejs.org and you will have it. On Linux, the version in the system package manager is sometimes older. If `node --version` prints a number below 22.20, install from nodejs.org instead.

## macOS

1. **Open Terminal.** Press Command and Space, type `Terminal`, press Return. A window opens with a line that ends in `%` or `$`. You type commands there and press Return after each one.
2. **Install Node.js.** Go to https://nodejs.org, download the LTS installer (a `.pkg` file), open it and click Continue until it finishes. If you already use Homebrew, run `brew install node` instead.
3. **Check Node.js.** Close Terminal and open it again, then run `node --version` and `npm --version`. Each prints a version number such as `v24.11.1` and `11.6.2`. `command not found` means the installer did not finish or Terminal was not reopened.
4. **Check Python.** Run `python3 --version`. If Python is missing, macOS opens a window asking to install the command line developer tools. Click Install, accept the licence, wait a few minutes, and run the command again. It prints `Python 3.` followed by 9 or higher.
5. **Check git.** Run `git --version`. The same developer tools window may appear. Once it prints `git version 2.` and a number, tell git who you are, once:
   `git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`.
6. **Make your project folder.** Run `mkdir my-plan`, then `cd my-plan`, then `git init`. You will see `Initialized empty Git repository`. To use an existing folder, `cd` into it instead. If it is not yet a git repository, run `git init` there.
7. **Install the skills.** From inside the folder, run the install line from the README. It may ask you to confirm a download.
8. **Restart your agent** so it sees the skills.

## Windows

The steps use PowerShell, which comes with Windows.

1. **Open PowerShell.** Click Start, type `PowerShell`, press Enter. A blue or black window opens with a line that ends in `>`.
2. **Install Node.js.** Go to https://nodejs.org, download the LTS installer (a `.msi` file) and run it. Click Next until it finishes. If it offers a checkbox to install necessary tools, tick it.
3. **Install Python 3.** Go to https://www.python.org/downloads/, download the latest Python 3 and run the installer. On its first screen, tick **Add python.exe to PATH** before you click Install Now.
4. **Install Git for Windows.** Go to https://git-scm.com, download it and run the installer. The default answers are fine.
5. **Close PowerShell and open it again.** The new tools are found only by a new window.
6. **Check the three tools.** Run `node --version`, `npm --version`, `python --version` and `git --version`. Each prints a version number. On Windows the Python command is often `python` and not `python3`. The scripts and the skills accept either, so use whichever works. Tell git who you are, once: `git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`.
7. **Make your project folder.** Run `mkdir my-plan; cd my-plan; git init`. You will see `Initialized empty Git repository`. To use an existing folder, `cd` into it instead, and run `git init` there if it is new.
8. **Install the skills.** Run the install line from the README. If PowerShell says that running scripts is disabled and names `npx.ps1`, run the same line with `npx.cmd` in place of `npx`. That avoids changing any security setting.
9. **Restart your agent.**

## Linux

1. **Open a terminal.** Use your desktop's terminal application.
2. **Install the tools.** On Debian or Ubuntu run `sudo apt update` and then `sudo apt install nodejs npm python3 git`. On Fedora run `sudo dnf install nodejs npm python3 git`. If `node --version` then prints a number below 22.20, install Node.js from https://nodejs.org instead.
3. **Check them.** Run `node --version`, `npm --version`, `python3 --version` and `git --version`. Each prints a version number. Python must be 3.9 or higher.
4. **Tell git who you are**, once: `git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`.
5. **Make your project folder.** Run `mkdir my-plan`, `cd my-plan`, `git init`. Or `cd` into an existing folder and run `git init` there if it is new.
6. **Install the skills.** Run the install line from the README.
7. **Restart your agent.**

## Manual install, without Node.js

If you cannot or do not want to install Node.js, skip the installer.

1. Open https://github.com/sct-will/carrydown in your browser.
2. Click the green **Code** button, then **Download ZIP**.
3. Unzip the file. Inside it is a folder called `skills` with two folders: `carrydown-ground-truth` and `carrydown-plan-to-github`.
4. Copy those two folders into your agent's skills folder. The paths for each agent are in the table under [Install options](../README.md#install-options) in the README. Use the project folder column to install for one project, or the user folder column to install for yourself everywhere. Create the skills folder if it does not exist.
5. Restart your agent.

The skills are self-contained, so nothing else needs copying.

## When something does not work

- **`npx: command not found` or `npx` is not recognised.** Node.js is not installed, or your terminal was opened before the install. Close the terminal, open a new one and try again. See the [FAQ](faq.md#npx-command-not-found).
- **`python3: command not found` on Windows.** Use `python`. If neither works, rerun the Python installer, choose Modify, and tick Add Python to environment variables.
- **The agent does not see the skills.** Restart it. Check that the skill folders are in the agent's skills folder from the table under [Install options](../README.md#install-options) in the README.
- **`fatal: not a git repository`.** Run `git init` in your project folder, or `cd` into the folder you made.
- **You do not have permission to install software.** Ask your IT department for Node.js LTS, Python 3.9 or later and git. Or use a Codespace: the README's [Getting started](../README.md#getting-started) has a link that opens the repository in a browser with the tools already installed.
