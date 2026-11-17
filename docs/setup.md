# Install carrydown and start your first plan

## The short path

1. **What you need.** A coding agent that supports Agent Skills, and Node.js 22.20 or later and Git for the one-line installer. To check them by hand, the steps for [macOS](#macos), [Windows](#windows) and [Linux](#linux) show the command for each. If you cannot install Node.js, use the [manual install](install-options.md#manual-install-without-nodejs). You do not need to install Python first: the skill checks Python and Git when it starts, and offers to install Python after your yes.
2. **Where you type the installer.** In your terminal, in your project folder, once. [Open your project folder](#open-your-project-folder) shows how. Choose both skills, your agent and the project scope, as [install the two skills](#install-the-two-skills) shows:

   ```bash
   npx skills add sct-will/carrydown
   ```

3. **How you know it worked.** The installer's summary names `carrydown-ground-truth` and `carrydown-plan-to-github`. Start a new agent session in the same folder and say the sentence in step 4. The agent lists your files, then asks who may see them in a reply that begins `carrydown: interview, step 0 of 6`. If no reply carries that line, the agent has not loaded the skill: see [the agent does not see the skills](#the-agent-does-not-see-the-skills).
4. **What to say to start.** In the agent's chat, say this and give the paths of your documents:

   > Set up a project plan from these documents.

5. **What to have ready.** The locations of your documents and the answers in [what the agent asks you](plan-owner-guide.md#what-the-agent-asks-you). If some documents are confidential, read [who may see your documents](#before-you-add-documents-who-may-see-them) before you copy anything into a project.

## Words you will meet

- **Agent skill.** A folder of instructions that your coding agent loads to do one kind of work. carrydown installs two.
- **Node.js and npx.** Node.js is a free program that runs JavaScript on your computer, and `npx` is the command it provides to download and run the skills installer.
- **Ground truth.** The documents the project must obey, such as architecture, requirements and company rules.
- **Track.** A lane of work that one engineer owns, such as back end or front end.
- **Milestone and demonstration.** A milestone is a group of work that ends with a demonstration, a meeting where the engineers show the stakeholders that part working.
- **Work item.** The smallest piece of work an engineer can finish and show, with one specification each.
- **Dry run.** A preview of what a command would do. It writes nothing, and the agent shows it to you before the real run.

The [glossary](plan-owner-guide.md#glossary) has the other words.

## The steps in detail

Follow the steps below from computer setup through your first conversation with carrydown. They include installation, verification and troubleshooting.

**My computer is ready:** skip to [open your project folder](#open-your-project-folder).

**The skills are already installed:** skip to [who may see your documents](#before-you-add-documents-who-may-see-them), then [start your plan](#start-your-plan).

[Python](#before-anything-python) | [Choose an agent](#choose-a-coding-agent) | [Prepare your computer](#prepare-your-computer) | [Open a project](#open-your-project-folder) | [Install](#install-the-two-skills) | [Check](#check-the-installation) | [Who may see your documents](#before-you-add-documents-who-may-see-them) | [Start a plan](#start-your-plan) | [Other options](install-options.md) | [Organization setup](organization-setup.md) | [Get help](#when-something-does-not-work)

## Before anything: Python

The carrydown scripts need Python 3.9 or newer. You do not have to install it first. When you start a skill, your agent checks for Python and, if it is missing or too old, asks once: "Python is needed to run the carrydown scripts. Install it now?" Say yes and it installs Python with the official installer for your system, and tells you each step to click. Say no and it stops and explains what cannot run without Python.

If you prefer to do it yourself, or your agent is not set up yet, follow the heading for your system. The links go to python.org, the official Python site.

### Python on macOS

1. **Open Terminal.** Press Command and Space together, type `Terminal`, then press Return.
2. **Check for Python.** Type this and press Return:

   ```bash
   python3 --version
   ```

   If it prints `Python 3.9` or later, such as `Python 3.12.4`, you are done. If a window offers developer tools, a message says the command is not found, or the version is older than 3.9, continue.
3. **Install it.** If you use Homebrew, run `brew install python`. Otherwise [download the official installer](https://www.python.org/ftp/python/3.15.2/python-3.15.2-macos11.pkg), double-click the downloaded file, follow the prompts and enter the computer password when it asks. The [macOS downloads page](https://www.python.org/downloads/macos/) always lists the newest version. If the installer will not open, run `xcode-select --install` and follow Apple's window.
4. **Check again in a new window.** Close Terminal, open it again and run the check from step 2.

### Python on Windows

1. **Open PowerShell.** Click the Start button, type `PowerShell`, then click Windows PowerShell.
2. **Check for Python.** Type this and press Enter:

   ```powershell
   py -3 --version
   ```

   If it prints `Python 3.9` or later, you are done. If it says the command is not found, opens the Microsoft Store or shows an older version, continue.
3. **Install it.** Windows 10 and 11 include a tool called winget. Run:

   ```powershell
   winget install --id Python.Python.3.12 -e --source winget
   ```

   If winget is not available, [download the official installer](https://www.python.org/ftp/python/3.15.2/python-3.15.2-amd64.exe) (on an ARM processor, [use this one](https://www.python.org/ftp/python/3.15.2/python-3.15.2-arm64.exe)), double-click it and tick the box "Add python.exe to PATH" on the first screen before you click Install Now. If your computer blocks the installer, send the [Windows downloads page](https://www.python.org/downloads/windows/) to your administrator and ask them to install Python 3.9 or newer.
4. **Check again in a new window.** Close PowerShell, open it again and run the check from step 2.

### Python on Linux

Open Terminal from your application menu and run `python3 --version`. If it is missing or older than 3.9, install it with your package manager, for example `sudo apt install python3` on Debian or Ubuntu or `sudo dnf install python3` on Fedora, or ask your administrator. The [release page](https://www.python.org/downloads/release/python-3152/) lists every official file.

The commands in this documentation are written for macOS and Linux. On Windows, your agent uses the Windows form of each command from its preflight, so you never have to translate them.

## Choose a coding agent

Choose a coding agent that supports Agent Skills and can read and edit project files and run commands. carrydown uses those capabilities to draft and check the plan.

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

Pick your system: [macOS](#macos), [Windows](#windows) or [Linux](#linux). These tools are free. Your coding agent may require a separate subscription. For [manual installation without Node.js](install-options.md#manual-install-without-nodejs), skip Node.js and prepare Python and Git before opening your project folder.

Run the commands below in your terminal, one line at a time. For missing commands or installation errors, use [installation help](#when-something-does-not-work).

### macOS

1. **Open Terminal.** Press Command and Space, type `Terminal`, then press Return.
2. **Check for Node.js.** Run:

   ```bash
   node --version
   ```

   Confirm Node.js is version 22.20 or later. If the command is missing or the version is too old, open the [Node.js download page](https://nodejs.org/en/download). Choose an LTS release and the macOS Installer (`.pkg`). Open the downloaded file and follow its installer. Close Terminal and reopen it, then run the check again.
3. **Check for Python.** Follow [Python on macOS](#python-on-macos) above.
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
3. **Check for Python.** Follow [Python on Windows](#python-on-windows) above.
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

There is no third skill to install. The first skill, `carrydown-ground-truth`, covers initial planning and later updates, and the second, `carrydown-plan-to-github`, publishes. The generated engineers' skill is installed separately.

To change the installed skills later, run the installer again.

If your agent is missing from the chooser, use its [complete installation command](install-options.md#choose-where-to-install). Then continue to the installation check.

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

## Before you add documents: who may see them

Before it renders or copies anything, the agent asks you one question:

> Can everyone who can read this repository see all of these documents and your staffing notes?

**If you can answer yes, you are done with this section.** That is the case for most teams. You work as before: the agent drafts in the repository, you keep the documents where they are or in an ignored `docs/source/` folder, and the only things that change are these. Your staffing notes go to a private file on your machine instead of the plan. Originals are optional in the project. When you put the plan on GitHub, you approve a short preview of what will be shared, in the same prompt as the GitHub question you already answer. Nothing else is required, and you can skip [organization setup](organization-setup.md), which is for the private path only.

If you want a local copy of the documents on a yes answer, use `docs/source/` and add `docs/source/` to `.gitignore` before you copy anything into it. The agent adds that line when it scaffolds the plan, but not before. Read [the enterprise security questions](enterprise-security.md) if you are unsure what carrydown protects.

<details>
<summary>If some documents are confidential, answer no and read this</summary>

Everyone who can read your project repository can read what you commit to it. When some documents are not for them, answer no. Then:

| | Yes | No |
| --- | --- | --- |
| Where drafting happens | In the repository, as before. | In a private workspace on your machine, including for documents you call shareable. Nothing is drafted in the repository before approval. |
| What reaches the repository | Renderings, the plan, specifications, approved contexts and a receipt. Never staffing notes. | Only the outputs you approve after a preview, exported on a new branch. |
| What you need | The two skills. | An organization that has installed the pieces in [organization setup for private drafting](organization-setup.md), and a private staging repository for your project. |

What this means in practice:

- **Keep confidential documents where they are.** Give the agent their paths in the system your organization already uses. Do not copy a confidential document into the project folder. The checks pass in a clean clone without originals.
- **Staffing stays private on both answers.** Names, GitHub logins, skills, preferences, days off, allocation and start dates go to `people.yaml` in the private workspace, never into the plan or any file in the project. The load table and the date checks run on your machine.
- **An ignore rule does not erase history.** If a confidential file was ever committed, it is still in the repository's history. `release.py inventory` lists tracked originals, renderings and staffing fields and whether they appear in history. carrydown cannot rewrite history. [GitHub's guidance on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) applies.
- **The approved context is readable by everyone who can read the repository.** Version 1 cannot hide a section from a teammate who has repository access. Material that some of those readers must not see needs a delivery mode that is planned and not yet available. See [delivery modes](delivery-modes.md).
- **Answer once.** The agent records your answer for each document and shows it in two lines, with where drafting will happen. Change it only by running step 0 again.

</details>

## Start your plan

1. Collect the locations of the files the project must obey: architecture, requirements, governance rules, development standards and company context as needed. Word, Markdown and plain UTF-8 text render directly. The agent can inspect readable PDF, PNG and other files and create reviewed Markdown renderings. Export older Word files to `.docx` first. You can include more than one file. You do not need to create a folder or copy anything into the project. Read [who may see your documents](#before-you-add-documents-who-may-see-them) first if you have not.
2. In the agent's chat, say:

   > Set up a project plan from these documents.

   Give the paths of the files to use. One file is fine.
3. The agent inventories the files and reports how each will be processed. It identifies unreadable files and continues with readable sources. It stops only when none of the intended ground truth can be processed. It reports a file that is already inside the project folder. It does not call that file safe and does not delete it. It also checks the setup and requests approval if Git needs to be initialized. Initialization is local and does not upload the project.
4. The first reply is `carrydown: interview, step 0 of 6`, and it asks the one question above. After your answer the agent creates the private workspace on your machine with owner-only permissions, and tells you where drafting will happen. On the no answer it also prints the commands that create the private staging repository. It does not run them.
5. The interview continues. Replies identify the current step as `carrydown: interview, step N of 6`. Dates, team size and other constraints can remain undecided; the agent proposes assumptions for review. Staffing details you give in step 2 are saved to the private workspace.
   Skills and work preferences are optional. Supply them only when you want them to influence the proposed tracks and assignments. Missing or unclear staffing context does not stop planning.

**You are ready when the agent begins the interview.**

**Next:** [Review and publish your plan](plan-owner-guide.md). That guide helps you answer the interview, review the drafts and carry the approved plan into GitHub. It also explains what to say [when the project changes](plan-owner-guide.md#when-the-project-changes). Planning locally needs no GitHub token. When you are ready to publish, its [token section](plan-owner-guide.md#the-token) lists the exact repository and project permissions for organization-owned and user-owned boards.

## Other installation options

To install for all your projects, name your agent in the command or install without Node.js, read [other installation options](install-options.md).

## Organization setup for private drafting

Only for the private path, when some documents are not for everyone who can read the repository: your administrator follows [organization setup for private drafting](organization-setup.md).

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

   > Use the carrydown-ground-truth skill. Set up a project plan from these documents.

5. If the skills are still missing, use the complete command for your agent in the [agent command list](install-options.md#choose-where-to-install) and repeat the check. If the installer reports a permission error creating a symlink, choose **Copy** or use the manual installation route.

### You need help from your organization

If you cannot install software, send your support team this request:

> I need to run the carrydown planning skills in a local project folder. Please help me set up an approved coding agent with file and command access, Node.js 22.20 or later with npx, a current Python 3 release and Git. The installer needs access to the Node package registry and GitHub. I will need repository and project-board permissions later, when I publish the reviewed plan.
