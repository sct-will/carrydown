# Install carrydown and start your first plan

Follow this page from computer setup through your first conversation with carrydown. It includes installation, verification and troubleshooting.

**My computer is ready:** skip to [open your project folder](#open-your-project-folder).

**The skills are already installed:** skip to [who may see your documents](#before-you-add-documents-who-may-see-them), then [start your plan](#start-your-plan).

[Choose an agent](#choose-a-coding-agent) | [Prepare your computer](#prepare-your-computer) | [Open a project](#open-your-project-folder) | [Install](#install-the-two-skills) | [Check](#check-the-installation) | [Who may see your documents](#before-you-add-documents-who-may-see-them) | [Start a plan](#start-your-plan) | [Other options](#other-installation-options) | [Organization setup](#organization-setup-for-private-drafting) | [Get help](#when-something-does-not-work)

**Documents that are confidential?** Read [who may see your documents](#before-you-add-documents-who-may-see-them) before you copy anything into a project.

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

## Before you add documents: who may see them

Before it renders or copies anything, the agent asks you one question:

> Can everyone who can read this repository see all of these documents and your staffing notes?

**If you can answer yes, you are done with this section.** That is the case for most teams. You work as before: the agent drafts in the repository, you keep the documents where they are or in an ignored `docs/source/` folder, and the only things that change are these. Your staffing notes go to a private file on your machine instead of the plan. Originals are optional in the project. When you put the plan on GitHub, you approve a short preview of what will be shared, in the same prompt as the GitHub question you already answer. Nothing else is required, and the rest of this page applies to you only when you reach [organization setup](#organization-setup-for-private-drafting), which you can skip.

If you want a local copy of the documents on a yes answer, use `docs/source/` and add `docs/source/` to `.gitignore` before you copy anything into it. The agent adds that line when it scaffolds the plan, but not before. Read [the enterprise security questions](enterprise-security.md) if you are unsure what carrydown protects.

<details>
<summary>If some documents are confidential, answer no and read this</summary>

Everyone who can read your project repository can read what you commit to it. When some documents are not for them, answer no. Then:

| | Yes | No |
| --- | --- | --- |
| Where drafting happens | In the repository, as before. | In a private workspace on your machine, including for documents you call shareable. Nothing is drafted in the repository before approval. |
| What reaches the repository | Renderings, the plan, specifications, approved contexts and a receipt. Never staffing notes. | Only the outputs you approve after a preview, exported on a new branch. |
| What you need | The two skills. | An organization that has installed the pieces in [organization setup for private drafting](#organization-setup-for-private-drafting), and a private staging repository for your project. |

What this means in practice:

- **Keep confidential documents where they are.** Give the agent their paths in the system your organization already uses. Do not copy a confidential document into the project folder. The checks pass in a clean clone without originals.
- **Staffing stays private on both answers.** Names, GitHub logins, skills, preferences, days off, allocation and start dates go to `people.yaml` in the private workspace, never into the plan or any file in the project. The load table and the date checks run on your machine.
- **An ignore rule does not erase history.** If a confidential file was ever committed, it is still in the repository's history. `release.py inventory` lists tracked originals, renderings and staffing fields and whether they appear in history. Carrydown cannot rewrite history. [GitHub's guidance on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) applies.
- **The approved context is readable by everyone who can read the repository.** Version 1 cannot hide a section from a teammate who has repository access. Material that some of those readers must not see needs a delivery mode that is planned and not yet available. See [delivery modes](delivery-modes.md).
- **Answer once.** The agent records your answer for each document and shows it in two lines, with where drafting will happen. Change it only by running step 0 again.

</details>

## Start your plan

1. Collect the locations of the files the project must obey: architecture, requirements, governance rules, development standards and company context as needed. Word, Markdown and plain UTF-8 text render directly. The agent can inspect readable PDF, PNG and other files and create reviewed Markdown renderings. Export older Word files to `.docx` first. You can include more than one file. You do not need to create a folder or copy anything into the project. Read [who may see your documents](#before-you-add-documents-who-may-see-them) first if you have not.
2. In the agent's chat, say:

   > Set up a project plan from this document.

   For multiple documents, give the paths of the files to use.
3. The agent inventories the files and reports how each will be processed. It identifies unreadable files and continues with readable sources. It stops only when none of the intended ground truth can be processed. It reports a file that is already inside the project folder. It does not call that file safe and does not delete it. It also checks the setup and requests approval if Git needs to be initialized. Initialization is local and does not upload the project.
4. The first reply is `carrydown: interview, step 0 of 6`, and it asks the one question above. After your answer the agent creates the private workspace on your machine with owner-only permissions, and tells you where drafting will happen. On the no answer it also prints the commands that create the private staging repository. It does not run them.
5. The interview continues. Replies identify the current step as `carrydown: interview, step N of 6`. Dates, team size and other constraints can remain undecided; the agent proposes assumptions for review. Staffing details you give in step 2 are saved to the private workspace.
   Skills and work preferences are optional. Supply them only when you want them to influence the proposed tracks and assignments. Missing or unclear staffing context does not stop planning.

**You are ready when the agent begins the interview.**

**Next:** [Review and publish your plan](plan-owner-guide.md). That guide helps you answer the interview, review the drafts and carry the approved plan into GitHub. Planning locally needs no GitHub token. When you are ready to publish, its [token section](plan-owner-guide.md#the-token) lists the exact repository and project permissions for organization-owned and user-owned boards.

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

## Organization setup for private drafting

Read this section only when the answer to "Can everyone who can read this repository see all of these documents and your staffing notes?" is no. The "yes" path needs none of it. The private path adds three pieces that an organization administrator installs once, and a short enrollment for each project:

- **A tooling repository.** It holds the independent verifier and the enrollment file. Only release owners and administrators can write to it.
- **A staging repository for each project.** It holds release candidates while the plan owner approves them, before anything reaches the engineering repository.
- **A verifier App.** A GitHub App that reports two required checks. It has its own credential, which only the tooling repository holds.

The plan owner then runs two checks, the offline and the live doctor, and reads one short table. Engineers see one required check on their pull requests.

### What the administrator needs first

- Permission to create repositories and a GitHub App in the organization, and to manage rulesets and Actions settings on the engineering and staging repositories.
- A plan that supports the features below. Before you offer this path, prove on your plan that App-specific required checks, repository rulesets, the up-to-date branch requirement, pull requests opened by Actions and the App permissions work. GitHub.com and GitHub Enterprise Cloud can use this setup when verified. GitHub Enterprise Server is unverified until you test it on your server version.
- The numeric ids of the repositories and accounts. For a repository, `gh api repos/OWNER/NAME --jq .id`. For an account, `gh api users/LOGIN --jq .id`. Logins are hints. The numeric id is the authority.
- Time to read what you install. This section links no code that you should install unread.

### Step 1: create the tooling repository

1. Create a private repository, by default `carrydown-tooling`: `gh repo create OWNER/carrydown-tooling --private`.
2. Limit write access to the release owners and administrators. Protect the default branch with a ruleset that requires a pull request review, blocks force pushes and deletion, and allows no bypass. Changes to the verifier or to the enrollment then go through review.
3. Copy two folders, whole, from a clone of the carrydown repository into the tooling repository: `scripts/` and `verifier/`. They are the pinned verifier code. Do not copy from an installed skill. An installed skill carries only the scripts it runs, and the verifier also needs `release_engineering.py` and `release_scan.py`, which no skill carries. Copy `verifier/carrydown-release-verify.yml` to `.github/workflows/carrydown-release-verify.yml` in the tooling repository. Merge that commit first. It is the commit that the enrollment pins as the verifier code, and the enrollment goes in a later commit.
4. Read `.github/workflows/carrydown-release-verify.yml` before you merge it. It checks out the policy and the code into separate folders, proves the code checkout is exactly the pinned commit, and runs the verifier with `python3 -I`. Its actions are pinned by full commit SHA (Secure Hash Algorithm). Confirm each pinned commit against the action's release page.

### Step 2: create the verifier App

1. Create a GitHub App owned by the organization. Turn webhooks off. Grant only these repository permissions: Contents read, Pull requests read, Checks write and Metadata read.
2. Install it on the tooling repository and on each engineering and staging repository you enroll. Grant no other repository.
3. Write down the App's numeric id. It becomes `verifier_app_id` in the enrollment, and both required checks must come from this App.
4. Generate a private key. Store the App id and the key as two repository secrets of the tooling repository only, named `CARRYDOWN_APP_ID` and `CARRYDOWN_APP_PRIVATE_KEY`. Never use an organization secret, and never store them in an engineering or staging repository. With the GitHub command line, `gh secret set CARRYDOWN_APP_PRIVATE_KEY --repo OWNER/carrydown-tooling < key.pem` reads the key from the file, so it never appears on a command line. Delete the file afterward.

The verifier mints a short-lived installation token from these two secrets at the start of every run. It never prints the token.

### Step 3: create the staging repository and its rules

For each engineering repository:

1. Create a private repository for release candidates. The plan owner's `python3 scripts/workspace.py init --root . --answer no --apply` prints the exact commands. The staging repository receives snapshots and manifests only, never originals or staffing records.
2. Copy `templates/staging/open-release-request.yml` to `.github/workflows/open-release-request.yml` on its default branch. Another administrator reviews it, and nobody edits it afterward, because the enrollment pins its digest: `shasum -a 256 .github/workflows/open-release-request.yml`. The workflow runs from the default branch on a schedule and on manual dispatch. It lists the `request/*` and `state/*` branches as data and opens a pull request for each, with `contents: read` and `pull-requests: write` only. It never runs or imports a file from a candidate branch. The plan owner's `release.py approve --github` dispatches it when the owner's permissions allow, and otherwise the schedule picks the branch up. A delay is normal, and a wait that ends without a pull request leaves a pending candidate and no approval.
3. Under Settings, Actions, General, allow GitHub Actions to create pull requests. This is how the owner is not the author of the request.
4. Allow merge commits only. Squash and rebase would stop the verifier from comparing the reviewed head with the merged tree.
5. Create the rulesets. Print them with the App's id filled in, then import each JSON file under Settings, Rules, Rulesets:

   ```bash
   python3 verifier/verify_release.py ruleset --kind staging --app-id <app id> > staging-ruleset.json
   python3 verifier/verify_release.py ruleset --kind engineering --app-id <app id> > engineering-ruleset.json
   ```

   The staging ruleset requires one approving review, dismisses stale approvals when new commits arrive, restricts force pushes and deletion, allows no bypass, requires the `carrydown-staging-verifier` check from the App, and requires branches to be up to date before merging. It sets `require_last_push_approval` to false on purpose. The plan owner pushes the candidate and may be the only authorized human. Do not turn that setting on. The engineering ruleset requires `carrydown-release-verifier` from the same App, blocks force pushes and deletion, and allows no bypass.
6. Check who can read the staging repository. The permitted set is the plan owner, the approved disclosure reviewers, the necessary organization administrators and specifically approved services. Include organization base permissions, teams, outside collaborators, repository administrators, installed Apps and deploy keys. Private visibility alone is not evidence of that set.

### Step 4: enroll the project

1. Add an entry to `enrollment.yaml` in the tooling repository. [The enrollment reference](../verifier/enrollment.schema.md) lists every field with a worked example. Set `verifier_sha` to the commit from step 1 and `verifier_app_id` to the App id.
2. Fill in the two digests. `python3 verifier/verify_release.py digests --policy-file enrollment.yaml` prints the `enrollment_id` and `policy_sha256` each entry should carry, and says whether the file already holds them. Run it again after every edit. Any change to a permission changes the policy digest, and that forces reassessment of every earlier approval.
3. Merge the enrollment through a reviewed pull request. The merge commit is the policy commit. It must be later than the verifier commit.
4. In the engineering repository, add the pointer `.carrydown/release-policy.yaml`:

   ```yaml
   format: 1
   tooling_repository: OWNER/carrydown-tooling
   enrollment_id: <the enrollment_id of the entry>
   ```

   The pointer is only a pointer. The verifier resolves the project by the repository's numeric id and compares the pointer with the enrollment. Deleting the pointer or the handling block fails the check. It never turns an enrolled project into a legacy one.

### Step 5: attest what the plan owner cannot inspect

Some facts cannot be read with an ordinary token: the Apps installed on the staging repository, the readers of a project board, the engineering rulesets when the owner lacks administrative read access, the secret names of a repository, and the organization's agent environment. An administrator can vouch for each fact with a scoped attestation in the enrollment, [described in the reference](../verifier/enrollment.schema.md#attestations). Rules that always hold:

- The author must be one of the enrollment's administrators, by numeric id, and the attestation must sit in the protected history of `enrollment.yaml`. Record the tooling pull request review that approved it in `note`.
- The subject must match the exact component. A change to the reader set, the repository or the App makes the old attestation stop matching.
- It has an expiry. Choose a lifetime you will keep renewing. Carrydown supplies no attestation that never expires.
- It never replaces a live content hash, an approval identity, an event state, an expiry or the verifier's scan health.

An expired or missing attestation blocks the first upload to staging, not the later audit. Renew it before it lapses.

### Step 6: run the doctor

The doctor has two forms. Both print a short table of components with a status of verified, not verifiable or missing.

```bash
python3 scripts/workspace.py doctor --root .
python3 scripts/release.py doctor --root .
```

- **The offline doctor** (`workspace.py doctor`) checks the workspace permissions, that the workspace is outside the repository, the ignore rules and the local plan schema. It makes no network call. It lists every remote component as not verifiable, because the first skill holds no token code.
- **The live doctor** (`release.py doctor`) adds the remote components, read with the owner's token: the enrollment found by the repository's numeric id, the pinned verifier commit and the absence of a verifier credential in the engineering and staging repositories, the staging repository's identity, privacy and effective readers, the installed request workflow against its enrolled digest, both rulesets (including the App that owns each required check), the approver and administrator accounts, the destinations, the verifier's scan health and the runtime-isolation attestation. It ends with two lines that say whether a private upload to staging is allowed and whether export and publication are allowed. The same checks run again before every upload, export and publication.

On the private path every mandatory component must be verified before anything is uploaded or released. A not verifiable or missing component blocks the step that needs it and names the reason code. On the "yes" path the remote checks are informational.

From an installed skill, `workspace.py` is in the `scripts/` folder of `carrydown-ground-truth` and `release.py` is in the `scripts/` folder of `carrydown-plan-to-github`. The examples use the paths of a carrydown clone.

The owner's token needs read access only for the doctor: Metadata, Contents, Pull requests and Administration (read) on the engineering and staging repositories, and Actions (read) on the tooling repository. It reads rulesets, collaborators, deploy keys and the verifier's last completed run.

The doctor also reports the verifier's health. A scan counts as healthy when its last completed run covered every open pull request and is no older than `check_health_max_age_seconds` (900 seconds by default). When the verifier is stale, owner-side writes refuse and the doctor tells you to restore it or to run the workflow by hand. The health check is an operational safeguard. It cannot expire a check that GitHub already shows as successful.

### Step 7: the owner's release commands

This step is for the private path. A yes-path owner does not need it: the agent runs the release for you, and [the plan owner guide](plan-owner-guide.md#release-what-the-engineers-will-see) shows what it runs. On the private path too, the agent runs these commands and shows you each dry run, and you never type a request id. They are listed so you and your administrator can see what happens. Every command that writes is a dry run until `--apply`. Run these from the project root.

```bash
python3 scripts/release.py preview --root .
python3 scripts/release.py prepare --root .
python3 scripts/release.py prepare --root . --apply
```

`preview` answers four questions in order: what will be shared, with whom, where, and what remains private. It then lists the changes since the last release. `prepare --apply` writes only into the private workspace. It prints two ids. The release id names the exact content. The request id names one permission decision over that content. The same content can have several requests, and approving one never approves another.

Run the live doctor, then upload the candidate, review it in GitHub and export.

```bash
python3 scripts/release.py doctor --root .
python3 scripts/release.py approve --root . --github
python3 scripts/release.py approve --root . --github --apply
```

None of these commands needs a request id: `approve` takes the request `prepare` saved last, `export` and `withdraw` the active request, and `export-state` the request the most recent state change ended. Each prints the id it uses, and `--request <request id>` names another one. The dry run of `approve --github` checks the staging repository without pushing anything. The `--apply` run first repeats the live checks, then pushes the branch `request/<request id>` to the staging repository with your own git credentials. No token goes into a URL. It waits up to two minutes for the staging workflow to open the pull request. A timeout prints `candidate uploaded; approval request pending` and the retry command. That is neither an approval nor a reason to upload again. In GitHub, review the final revision of the pull request, approve it and merge it with a merge commit. Then export:

```bash
python3 scripts/release.py export --root .
python3 scripts/release.py export --root . --apply
```

`export --apply` verifies the approval through the GitHub API before it writes anything. It makes an isolated worktree on a new branch `carrydown/request-<request id>`, copies only the approved files and the receipt, and commits as you. It prints the push and `gh pr create` commands. It does not run them. Creating the engineering pull request is a separate write that needs your approval.

When something changes, `release.py diff --root .` names the work items a change touches, and a new `preview`, `prepare` and approval follow. To end the active request, run `release.py withdraw --root . --reason <code>` and `--apply`, approve the state change the same way, then `release.py export-state --root . --apply` to publish the terminal receipt. [Recover a plan or publication](recovery.md#resume-an-interrupted-release) says how to resume each step if it is interrupted.

Minimum GitHub access for these commands:

| Command | Access it needs |
| --- | --- |
| `doctor`, `approve --github`, `export`, `export-state` on the "no" path | The read-only token above, for the checks. Your git credentials with write access to the staging repository, to push the candidate branch. |
| Pushing the export branch and opening the engineering pull request | Your git credentials with write access to the engineering repository, and your own `gh` sign-in to create the pull request. |
| Publishing issues and the board with `carrydown-plan-to-github` | The token in [the plan owner guide](plan-owner-guide.md#the-token): Issues read and write, Metadata read, and Projects read and write. |

### Who holds which credential

| Credential | Held by | Can do |
| --- | --- | --- |
| The plan owner's token | The owner's machine, never a repository | Read the facts above. The owner's git credentials push candidate branches to staging. |
| The verifier App's key | Secrets of the tooling repository only | Read contents and pull requests of enrolled repositories and write checks. |
| The staging workflow's `GITHUB_TOKEN` | The staging repository's Actions run | Read contents and write pull requests, so it can open a request. Nothing else. |
| Engineering repositories | Nothing | They hold no verifier workflow and no verifier secret. The doctor checks this. |

### Limits to state to your reviewers

- **Five minutes is a requested interval, not a deadline.** GitHub documents that scheduled runs can be delayed or dropped. An administrator can run the workflow by hand with Run workflow, and an optional webhook hosted by the organization can request an earlier run. Neither removes queueing or the race below.
- **A successful check can outlive its inputs.** GitHub does not expire an old success. If the scheduler stops, an old success can stay mergeable. The scan health check makes owner-side writes refuse when the verifier is stale. It does not invalidate a success that already exists.
- **State can change between a poll and a merge.** The reference deployment promises verification at the observed revisions. It does not promise continuous authorization or immediate revocation at the moment of merge. An organization that needs fresh authorization enforced at the exact merge must supply its own trusted merge controller. This deployment does not claim to be one.
- **Withdrawal reaches engineers only after the receipt update merges.** Staging state is authoritative at once for owner-side writes. Engineers learn it from the receipts on their fetched default branch.
- **Runtime isolation is attested, not proven.** The tests prove that an engineering clone carries no workspace locator or withheld text. They do not prove that an engineer's agent cannot read an owner-only folder. The runtime-isolation attestation records an administrator's claim about the real environment.

### Acceptance on real GitHub

Status: **not yet performed.** The fake-API tests cover the logic of every item below. They cannot show how GitHub counts reviews or which identity authored the request, so this run is a release prerequisite. The plan owner runs it only after explicitly authorizing it. Use a dedicated test organization, a fictional candidate, one human owner, the real App and the exported rulesets. Do not delete any resource the run creates.

Run these steps in order, and record the outcome of each in the table.

1. Install the tooling repository, the App, the staging repository and the engineering repository as above. Run the live doctor. Every component must be verified.
2. Prepare a fictional candidate, approve it with `release.py approve --root . --github --apply`, and confirm that the request pull request was opened by the Actions identity, not by the owner.
3. As the owner, approve the final head. Push another commit and confirm the approval is dismissed as stale. Approve the new head again.
4. Confirm that `require_last_push_approval` is off and that the owner, who pushed the branch, can approve it.
5. Confirm that `carrydown-staging-verifier` passes only after the authorized review of the final head, and fails before it.
6. Merge with a merge commit. Confirm that activation happened: the request is active and `release.py export` accepts it.
7. Export, open the engineering pull request, and confirm that `carrydown-release-verifier` passes. Then change one byte of an exported file and confirm the check fails.
8. Prepare a replacement, approve and merge it, and confirm the first request becomes superseded in one batch and the engineering receipts update.
9. Withdraw the active request. Confirm the receipt-only pull request passes and that a content publication stays refused.
10. Stop the scheduled workflow, wait past `check_health_max_age_seconds`, and confirm the doctor reports the scan health as missing. Restart it.

Record the results here when the run is done.

| Item | Record |
| --- | --- |
| Date of the run | Not yet performed |
| Platform and plan | Not yet performed |
| Repository ids (tooling, engineering, staging) | Not yet performed |
| App id and permissions | Not yet performed |
| Ruleset ids and the settings they hold | Not yet performed |
| Request opened by the Actions identity (step 2) | Not yet performed |
| Owner approval and stale-review dismissal (step 3) | Not yet performed |
| Last-pusher setting off (step 4) | Not yet performed |
| Staging check outcomes (step 5) | Not yet performed |
| Merge activation (step 6) | Not yet performed |
| Engineering check outcomes (step 7) | Not yet performed |
| Replacement (step 8) | Not yet performed |
| Receipt-only withdrawal (step 9) | Not yet performed |
| Scan health and scheduler behavior (step 10) | Not yet performed |
| Sanitized check outcomes (ids and reason codes only) | Not yet performed |

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
