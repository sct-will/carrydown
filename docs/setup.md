# Install carrydown and start your first plan

Follow this page from computer setup through your first conversation with carrydown. It includes installation, verification and troubleshooting.

**My computer is ready:** skip to [open your project folder](#open-your-project-folder).

**The skills are already installed:** skip to [start your plan](#start-your-plan).

[Choose an agent](#choose-a-coding-agent) | [Prepare your computer](#prepare-your-computer) | [Open a project](#open-your-project-folder) | [Install](#install-the-two-skills) | [Check](#check-the-installation) | [Start a plan](#start-your-plan) | [Other options](#other-installation-options) | [Get help](#when-something-does-not-work)

## Choose a coding agent

Choose a coding agent that supports Agent Skills and can read and edit project files and run commands. Carrydown uses those capabilities to draft and check the plan.

If your team already uses one, start there. Otherwise, choose one from this install list and follow its official setup instructions. Install it and sign in, then continue below. Its account, subscription and organization permissions are separate from carrydown.

| Agent | Official setup instructions |
| --- | --- |
| Claude Code | [Install and sign in](https://code.claude.com/docs/en/quickstart) |
| GitHub Copilot | [Set up the agent in your editor](https://code.visualstudio.com/docs/setup/copilot) |
| Cursor | [Get started](https://cursor.com/docs) |
| Codex | [Install and sign in](https://developers.openai.com/codex/quickstart) |
| Gemini CLI | [Install the agent](https://geminicli.com/docs/get-started/installation/) |
| IBM Bob | [Download and get started](https://www.ibm.com/products/bob) |

The installer supports [more agents](https://github.com/vercel-labs/skills/blob/main/docs/agents.md). Use the agent's local project mode for this walkthrough. If your team uses a remote workspace, prepare that workspace instead: the files, tools and skills must be available where the agent runs.

## Prepare your computer

| Tool | What it does | Required version |
| --- | --- | --- |
| Node.js | Provides `npx`, which downloads and runs the skills installer. | 22.20 or later. Choose a supported long-term support (LTS) release for a new installation. |
| Python | Runs the carrydown scripts that create and check planning files. | 3.9 or later. Choose a current Python 3 release for a new installation. |
| Git | Downloads the skills and records changes to the plan. | Use a current release provided for your system. |

Pick your system: [macOS](#macos), [Windows](#windows) or [Linux](#linux). These tools are free. Your coding agent may require a separate subscription. For [manual installation without Node.js](#manual-install-without-nodejs), skip Node.js and prepare Python and Git before opening your project folder.

Run the commands below in your terminal, one line at a time. For missing commands or installation errors, use [installation help](#when-something-does-not-work).

### macOS

1. **Open Terminal.** Press Command and Space, type `Terminal`, then press Return.
2. **Check for Node.js.** Run:

   ```bash
   node --version
   ```

   Confirm Node.js is version 22.20 or later. If the command is missing or the version is too old, open the [Node.js download page](https://nodejs.org/en/download). Choose an LTS release and the macOS Installer (`.pkg`). Open the downloaded file and follow its installer. Close Terminal and reopen it, then run the check again.
3. **Check for Python.** Run:

   ```bash
   python3 --version
   ```

   Look for `Python 3.9` or later; `3.10`, `3.11` and later versions also qualify. If it is missing or too old, install a current Python 3 release from the [Python macOS downloads](https://www.python.org/downloads/macos/). Open the downloaded `.pkg` and follow its installer. If macOS offers command line developer tools when you run the check, you can install those, then check the Python version again.
4. **Check for Git.** Run:

   ```bash
   git --version
   ```

   If macOS offers command line developer tools, click Install and wait for them to finish. If Git is still missing, run:

   ```bash
   xcode-select --install
   ```

   Follow the installation window, then run the Git check again. See [Git's macOS instructions](https://git-scm.com/install/mac) if the installation does not complete.

Close and reopen your coding agent after installing software so it can find the new tools. Continue to [open your project folder](#open-your-project-folder).

### Windows

1. **Open PowerShell.** Click Start, type `PowerShell`, then open Windows PowerShell or PowerShell. You will enter the commands below in that window.
2. **Check for Node.js.** Run:

   ```powershell
   node --version
   ```

   Look for version 22.20 or later, such as `v24.0.0`. If it is missing or too old, open the [Node.js download page](https://nodejs.org/en/download). Choose an LTS release and the Windows Installer (`.msi`). Open the download and follow its installer. Close PowerShell and reopen it, then check again.
3. **Check for Python.** Run:

   ```powershell
   python --version
   ```

   Look for `Python 3.9` or later. If Python is missing, opens a store page or reports an older version, install the Python install manager from the [Python Windows downloads](https://www.python.org/downloads/windows/). Then close and reopen PowerShell and run the check again. The manager can install a current Python release on first use. If you already have a working Python 3.9 or later, keep using it. [Python's Windows guide](https://docs.python.org/3/using/windows.html) covers installation and command problems.
4. **Check for Git.** Run:

   ```powershell
   git --version
   ```

   If the command is not recognized, download and run the installer from [Git for Windows](https://git-scm.com/install/windows). The default choices are suitable for this walkthrough. Close PowerShell and reopen it, then check again.

Close and reopen your coding agent after installing software so it can find the new tools. Continue to [open your project folder](#open-your-project-folder).

### Linux

1. **Open Terminal** from your application menu.
2. **Check the tools.** Run each command separately:

   ```bash
   node --version
   python3 --version
   git --version
   ```

   You need Node.js 22.20 or later, Python 3.9 or later, and a result beginning with `git version`. Skip installation for any tool that already meets the requirement.
3. **Install missing Python or Git.** On Debian or Ubuntu, run:

   ```bash
   sudo apt update
   sudo apt install python3 git
   ```

   On Fedora, use this instead:

   ```bash
   sudo dnf install python3 git
   ```

   These commands require administrator privileges. Password input may be hidden. On other distributions, follow [Python's Unix guide](https://docs.python.org/3/using/unix.html) and [Git's Linux instructions](https://git-scm.com/install/linux).
4. **Install missing or older Node.js.** Open the [Node.js download page](https://nodejs.org/en/download), select Linux and an LTS release, and follow the instructions for your installation method. Distribution packages can be older than carrydown's requirement. Check the result with `node --version`; if you need help choosing a method, ask your system administrator for Node.js 22.20 or later with `npx` available.

Close and reopen your terminal and coding agent after installing software, then run the checks again. Continue below once all three tools are available.

## Open your project folder

Use an existing software project or create a dedicated folder for the plan.

1. **Choose a folder.** To start fresh, use Finder on macOS, File Explorer on Windows or your Linux file manager to create a folder named `carrydown-plan` in Documents. If you already have a project, use that folder instead.
2. **Open it in your coding agent.** Use the application's Open Folder or Open Project control. If your agent runs in a terminal, open a terminal in the folder and start the agent using its setup instructions.
3. **Open a terminal in that folder.** If your application has a Terminal menu, open a new terminal there. Otherwise, open your system terminal, type `cd` followed by a space, then drag the project folder into the terminal. Keep the inserted path and its quoting, then press Enter. If dragging is unavailable, copy the folder's full path from your file manager and paste it after `cd `, with quotation marks around the path.
4. **Check the location.** On macOS or Linux, run:

   ```bash
   pwd
   ```

   On Windows PowerShell, run:

   ```powershell
   Get-Location
   ```

   The printed path should end with your project folder's name. If it points somewhere else, return to step 3 before installing.

Run the remaining terminal commands from this folder. If your coding agent occupies the terminal, use a second terminal opened in the same folder for installation.

## Install the two skills

Run this from your project folder:

```bash
npx skills add sct-will/carrydown
```

The installer downloads the skills into your project. Installation requires an internet connection but no GitHub token.

The choices can vary by installer version. Use these answers when they appear:

| If the installer asks about | Choose |
| --- | --- |
| Downloading or running the `skills` package | Confirm to continue. |
| Which skills to install | Both `carrydown-ground-truth` and `carrydown-plan-to-github`. |
| Which agent to use | The coding agent you opened for this project. |
| Installation scope | **Project**, so the skills are installed for this folder. |
| Installation method | **Symlink**, the recommended default. It creates links to one copy of each skill. If your computer does not allow links, choose **Copy** instead. |
| Confirming the installation | Review the selected skills, agent and project scope, then confirm. |

Use the arrow keys to move through terminal menus. In a multiple-selection list, Space usually selects or clears a choice, and Enter continues. Follow the key hints shown by your installer.

Wait until the installer reports completion and the terminal is ready for another command. You should see both skill names in its installation summary. Security scan results may also appear; the optional [security guide](security.md#what-skillssh-shows) explains them.

If your agent is missing from the chooser, use its [complete installation command below](#choose-where-to-install). Then continue to the installation check.

## Check the installation

From the same project folder, run:

```bash
npx skills list
```

Look for both `carrydown-ground-truth` and `carrydown-plan-to-github`. Other skills may also appear. A personal installation uses this check instead:

```bash
npx skills list --global
```

The list confirms the installed files. To make the agent load them, close and reopen the application or end the current agent session and start a new one. Open the same project folder. If the agent still cannot use either skill, follow [the help below](#the-agent-does-not-see-the-skills).

## Start your plan

1. In the project folder, create a folder named `docs`, then a folder named `source` inside it. Use your file manager or ask the agent to create them.
2. Copy the files the project must obey into `docs/source/`. Include architecture, requirements, governance rules, development standards and company context as needed. Word, Markdown and plain UTF-8 text render directly. The agent can inspect readable PDF, PNG and other files and create reviewed Markdown renderings. Export older Word files to `.docx` first. You can include more than one file.
3. In the agent's chat, say:

   > Set up a project plan from this document.

   For multiple documents, specify which files to use. The agent can list the files in `docs/source/`.
4. The agent inventories the folder and reports how each file will be processed. It identifies unreadable files and continues with readable sources. It stops only when none of the intended ground truth can be processed. It also checks the setup and requests approval if Git needs to be initialized. Initialization is local and does not upload the project.
5. The interview begins. Replies identify the current step as `carrydown: interview, step N of 6`. Dates, team size and other constraints can remain undecided; the agent proposes assumptions for review.
   Skills and work preferences are optional. Supply them only when you want them to influence the proposed tracks and assignments. Missing or unclear staffing context does not stop planning.

**You are ready when the agent begins the interview.**

**Next:** [Review and publish your plan](plan-owner-guide.md). That guide helps you answer the interview, review the drafts and carry the approved plan into GitHub.

---

## Other installation options

The default route above installs both skills for one agent in one project. Use these options only if you want a different scope, need to select an agent explicitly or cannot use the installer. After an alternative installation, continue with [check the installation](#check-the-installation), or [start your plan](#start-your-plan) after a manual installation.

### Choose where to install

**This project is the recommended starting point.** The skills are available in the project folder where you run the command. Open that folder whenever you use carrydown.

**All your projects is a personal installation.** It makes the skills available to your agent across projects on this computer. It does not install them for other people. Choose one scope; you do not need to run both commands.

Open your agent's entry below for complete commands. Each command selects both carrydown skills and the named agent. You still review the installer's confirmation.

<details>
<summary>Claude Code</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent claude-code
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent claude-code --global
```

</details>

<details>
<summary>GitHub Copilot</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent github-copilot
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent github-copilot --global
```

</details>

<details>
<summary>Cursor</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent cursor
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent cursor --global
```

</details>

<details>
<summary>Codex</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent codex
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent codex --global
```

</details>

<details>
<summary>Gemini CLI</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent gemini-cli
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent gemini-cli --global
```

</details>

<details>
<summary>IBM Bob</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent bob
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent bob --global
```

</details>

### Manual install, without Node.js

<details>
<summary>Installation steps and destination folders</summary>

Use this route if you cannot install Node.js. You still need a coding agent, Python and Git to use carrydown for planning. Skip the `npx` commands in this guide.

1. Open [the carrydown repository](https://github.com/sct-will/carrydown) in your browser. Choose **Code**, then **Download ZIP**.
2. Extract the downloaded archive. Open the extracted folder, then open `skills`. It contains `carrydown-ground-truth` and `carrydown-plan-to-github`.
3. Find your agent in the destination table below. Choose the project column for this project, or the home column for a personal installation. Create the destination folders if they do not exist. On Windows, your home folder is usually under `C:\Users\` followed by your account name.
4. Copy both complete skill folders into that destination. Copy their contents together, including `SKILL.md`, `scripts`, `templates` and `references`. Copying only `SKILL.md` leaves the scripts out.
5. If folders beginning with a dot are hidden, press Command, Shift and Period in macOS Finder. In Windows File Explorer, enable **Hidden items** in the View menu. On many Linux file managers, Control and H shows hidden files.
6. Open each copied skill folder and confirm that `SKILL.md` and its supporting folders are inside. For example, a project installation using the shared skills folder has `.agents/skills/carrydown-ground-truth/SKILL.md` and `.agents/skills/carrydown-plan-to-github/SKILL.md`.
7. Close and reopen your agent in the project folder. Continue at [start your plan](#start-your-plan). If the agent does not recognize the first skill, use the explicit start phrase in [the help below](#the-agent-does-not-see-the-skills).

A dot at the beginning of a folder name means it may be hidden. `~/` means your home folder, such as `/Users/your-name/` on macOS or `C:\Users\your-name\` on Windows.

| Agent | Inside your project folder | Inside your home folder |
| --- | --- | --- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `.agents/skills/` | `~/.copilot/skills/` |
| Cursor | `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `.agents/skills/` | `~/.gemini/skills/` |
| IBM Bob | `.bob/skills/` | `~/.bob/skills/` |

</details>

<details>
<summary>Preview the skills or install for every agent</summary>

**Preview before installing.** This lists the skills available from carrydown. It does not install them.

```bash
npx skills add sct-will/carrydown --list
```

**Install for every supported agent.** This installs both skills for all agents at project scope and skips the installer's confirmation prompts. Use it only when you want that broader installation.

```bash
npx skills add sct-will/carrydown --all
```

For the usual installation, use the default route above.

</details>

## When something does not work

### The install command is missing or blocked

**`npx: command not found` or `npx` is not recognized.** Install Node.js using the instructions for your system, then close and reopen the terminal and agent. Check:

```bash
node --version
npx --version
```

Both should print version numbers. If Node.js works but `npx` does not, repair or reinstall Node.js with its package tools included.

**PowerShell says `npx.ps1` cannot run because scripts are disabled.** Use this command instead:

```powershell
npx.cmd skills add sct-will/carrydown
```

For the installation check, run:

```powershell
npx.cmd skills list
```

This uses the Windows command launcher without changing your execution policy.

**The installer cannot download the skills.** Check your internet connection. On a managed computer, ask your support team whether downloads from the Node package registry and GitHub are allowed. Copy the error message when asking for help.

### Python or Git is missing

**The agent cannot find Python.** On macOS or Linux, check:

```bash
python3 --version
```

On Windows, check:

```powershell
python --version
```

If you installed it recently, close and reopen the agent. If the check still fails, return to your system's preparation steps. Tell the agent which command worked so it can use that command for the scripts.

**`git` is not recognized or not found.** Follow your system's Git installation steps, then reopen the terminal and agent.

**The folder is not a Git repository.** This is different from Git being missing. Ask the agent to initialize Git in your project folder. Review the folder it names, then approve. You can draft a plan locally before connecting a GitHub repository.

### The agent does not see the skills

Check these in order:

1. Open the same project folder where you installed the skills. A project installation is available in that folder.
2. Follow [check the installation](#check-the-installation) for your chosen scope. Both skill names should appear. For a manual installation, check the copied folders as described above.
3. End the agent session and start a new one, or close and reopen the application. Enable Agent Skills in its settings if the agent requires that.
4. In its chat, say:

   > Use the carrydown-ground-truth skill. Set up a project plan from this document.

5. If the skills are still missing, use the complete command for your agent in the [agent command list](#choose-where-to-install) and repeat the check. If the installer reports a permission error creating a symlink, choose **Copy** or use the manual installation route.

### You need help from your organization

If you cannot install software, send your support team this request:

> I need to run the carrydown planning skills in a local project folder. Please help me set up an approved coding agent with file and command access, Node.js 22.20 or later with npx, a current Python 3 release and Git. The installer needs access to the Node package registry and GitHub. I will need repository and project-board permissions later, when I publish the reviewed plan.
