# Troubleshooting

This page lists the problems you may meet while you install, plan, publish and update, each with its cause and its fix. For questions about the method, read the [carried-context development FAQ](https://carriedcontext.dev/faq/).

## Installing

### The terminal says `npx: command not found`

The terminal cannot find the installer command supplied by Node.js. Follow [the installation fix](setup.md#the-install-command-is-missing-or-blocked) for the checks and next action.

### Something is missing on this computer

carrydown needs a coding agent, Node.js for the installer, Python 3.9 or newer for the scripts and Git. You use a terminal to install and check the skills. After installation, you work in your agent's chat.

The first thing each skill does is check for Python 3.9 or newer. If Python is missing, it asks once whether to install it, and installs it from the official source after your yes. You still install Node.js and Git yourself. The [computer preparation steps](setup.md#prepare-your-computer) list versions and checks. If you would rather install Python yourself, [follow your system's steps](setup.md#before-anything-python). The [installation walkthrough](setup.md#install-the-two-skills) explains where to enter the commands and what to select. [Manual installation](install-options.md#manual-install-without-nodejs) is available if you cannot use Node.js.

### A hosted coding agent cannot refresh the engineers' check

Hosted coding agents can read the approved contexts from the repository, so they need no local workspace. The engineers' check refreshes with a `git fetch` of the default branch, and whether a hosted environment allows that depends on the host. If the fetch fails, the check applies the offline grace rule or stops.

carrydown's tests do not run inside a hosted agent, so confirm the fetch behavior for yours.

### I want to remove carrydown

The installer put the skill folders in your project. Run `npx skills remove`, or delete the skill folders. The files under `docs/` in your project are yours.

## Planning

### My document is a Word file with no section numbers

The agent can render it, but numbered sections make citations easier to maintain. Ask the agent to propose numbering in the source document and review it before planning.

### My source is a PDF, an image or plain text

Word, Markdown and UTF-8 plain text render directly. The agent can inspect readable PDF, image and other files and create a Markdown rendering with numbered sections and provenance.

Give the agent the files where you keep them, or keep a local copy in an ignored `docs/source/` folder. Review extracted rules, tables and diagram meaning before planning. If one file cannot be read reliably, the agent records the coverage limit and continues with the readable sources. It stops only when none of the intended ground truth can be processed.

## Publishing and updating

### I do not know which GitHub token permissions to request

No token is needed to plan locally. Publishing issues and a project board requires a GitHub personal access token. The permissions depend on who owns the board:

| Board owner | Token | Required access |
| --- | --- | --- |
| Organization | Fine-grained token limited to the repository | Repository permissions **Issues: read and write** and **Metadata: read**; organization permission **Projects: read and write** |
| Your user account | Classic token | `repo` and `project` scopes |

GitHub does not currently let fine-grained tokens access user-owned projects. The token cannot give you access that your GitHub account does not already have, and an organization may require administrator approval. Follow [the token walkthrough](plan-owner-guide.md#the-token) to create, check, store and revoke it without putting it in the repository or chat.

### I need to be sure a document never reaches the project repository

A document reaches the project repository only if you say everyone who can read the repository may see it. The project holds the outputs you approved, never a restricted original or its full rendering. Originals are optional in the project even when a document is public, and the checks pass in a clean clone without them.

Answer no to the agent's first question for that document, and keep it where it is. An ignore rule keeps new files out of git, but it does not erase a file that an earlier commit already holds. The inventory command, `release.py inventory`, lists what a legacy project tracks and whether it is in history. carrydown cannot rewrite history. See [who may see your documents](setup.md#before-you-add-documents-who-may-see-them), and the [security guide](security.md) for the model.

### A released document needs to be recalled

Text already delivered, in a clone, a fork, an issue, a stored copy or an agent transcript, cannot be recalled. Immediate revocation is not an embedded-delivery promise.

Ask the agent to withdraw the release, and give a reason, as [reapprove or withdraw a release](plan-owner-guide.md#reapprove-or-withdraw-a-release) shows. A withdrawal stops further publication and tells the engineers' check to stop on the next refresh. It does not remove anything.

### The board needs settings by hand, and the roadmap shows breaks

The GitHub application programming interface (API) cannot set every board setting. After it creates the board, the agent gives you a list. It includes view settings such as grouping, sorting and roadmap dates, plus workflows. Finish those settings in GitHub as part of [the publishing steps](plan-owner-guide.md#the-github-step).

Between two iterations with a gap in the dates, GitHub shows a break. The scripts leave the gaps from your `breaks` list, so the breaks in the roadmap are expected.

### An engineer's recorded decision and a source change disagree

When the engineer's decision and the revised source fit together, the update keeps both and the review explains the result. When they conflict, the review shows both sides and the plan owner decides. The agent does not overwrite an engineer's correction to make a regenerated specification simpler.

Decide the conflict in the review. A recorded decision does not change an obligation by itself. A released update does.

### An update stopped partway

The agent saved a proposal or started a publication that did not finish. A failure does not authorize a reset, a forced approval, a blind retry or the removal of human work.

Say "Resume the project update." The agent finds the saved proposal or the unfinished publication and continues from what is verified. See [resume a project update](recovery.md#resume-a-project-update).

### I am not sure the project is up to date

"Up to date" means that, for the sources the agent could observe, each change has a recorded disposition, you approved the update and every required publication step is verified. It does not mean that the agent saw sources it was not given, that no impact was missed or that every engineer has received the update.

Ask the agent. While a publication step is pending, it says so.

### The plan must change after the issues exist

You can change the plan after the issues exist. Existing issue bodies are updated only when requested, and issues are never deleted by the scripts.

Review local changes first, then preview the updates to GitHub. A changed source or an engineer's correction follows the same path: say what changed, review the one proposed update and approve it. Follow [update the plan](plan-owner-guide.md#update-the-plan).

### I found a bug or a security issue

A bug is reported in public. A security issue is reported privately.

Report a bug with [the bug report form](https://github.com/sct-will/carrydown/issues/new?template=bug_report.yml) on the carrydown repository. Leave out any token, password or private document text.

Report a security issue privately. Do not open a public issue for it. Use GitHub private vulnerability reporting through [the private report form](https://github.com/sct-will/carrydown/security/advisories/new) on the carrydown repository. Only the maintainer can read what you send. [SECURITY.md](../SECURITY.md) says what to put in the report and when to expect a reply.
