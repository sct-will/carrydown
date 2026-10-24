![carrydown](docs/images/hero.png)

# carrydown

Turn your architecture document into a plan your team and its AI coding agents can follow: dated milestones, one spec per task tied to the paragraph it came from, GitHub issues, a filled project board, and a skill that makes each developer's agent read the spec first.

[![Licence](https://img.shields.io/github/license/sct-will/carrydown?v=2)](LICENSE) [![Last commit](https://img.shields.io/github/last-commit/sct-will/carrydown?v=2)](https://github.com/sct-will/carrydown/commits/main) [![Issues](https://img.shields.io/github/issues/sct-will/carrydown?v=2)](https://github.com/sct-will/carrydown/issues) [![CI](https://github.com/sct-will/carrydown/actions/workflows/ci.yml/badge.svg)](https://github.com/sct-will/carrydown/actions/workflows/ci.yml) [![Content: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-blue)](LICENSE-CONTENT.md) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-3%20skills-teal)](https://agentskills.io) [![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](#prerequisites) [![Open in Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sct-will/carrydown)

[How it works](#how-it-works) · [Getting started](#getting-started) · [Prerequisites](#prerequisites) · [What you get](#what-you-get) · [Install options](#install-options) · [Sample](#sample) · [FAQ](#faq) · [Contributing](#contributing) · [Licence](#licence) · [For agents](AGENTS.md)

## How it works

![How carrydown works](docs/images/flow.png)

Planning decisions stay with people. The skills set up, draft to templates, validate and populate.

**`carrydown-ground-truth`**
- Interviews you, renders your documents to Markdown with stable section anchors, and scaffolds `docs/spec/` with `plan.yaml`.
- Drafts the plan with you: milestones, work units, tracks, dates, dependencies, load table, critical path, program boundary.
- Writes one specification per work item to a template, runs the checker, and gives review prompts for the document and the plan.
- Run by: the Plan owner. Reviewed by the Lead reviewer.

**`carrydown-plan-to-github`**
- Walks you through a GitHub token safely and runs a dry run before anything is written.
- After your yes, creates labels, one sub-epic per milestone, one issue per work item with sub-issue links, dependency links and an Epic roll-up comment that states the target delivery and the people by track.
- Builds the project board with work unit, track and date fields and three views, verifies the counts, and lists what you click by hand.
- Run by: the Plan owner or a delivery manager with permission to create issues and a Project.

**`carrydown-dev-skill`**
- Generates the developer skill for your project from the specification folder.
- The skill makes each developer's agent read the spec, the cited sections and the conventions before it changes code.
- Its README shows each teammate how to install it in their agent.
- Run by: the Plan owner, once, to generate the skill. The generated skill is installed and used every day by the Engineers, who start an item by naming it, for example "Work on WI-07".

**Roles**

| Role | What they do | Which skill |
| --- | --- | --- |
| Plan owner | The engineering lead or product manager who owns the plan. Gives the documents and any constraints, answers the interview, approves the plan, says yes before anything is written to GitHub, and generates the developer skill. | `carrydown-ground-truth`, `carrydown-plan-to-github`, `carrydown-dev-skill` |
| Lead reviewer | A senior engineer who spends about an hour reading the generated specifications as the person who will build them. | Reviews the output of `carrydown-ground-truth` |
| Engineers | The people building the work items, each with their own coding agent. They start an item by naming it, for example "Work on WI-07". | The generated developer skill, made by `carrydown-dev-skill` |
| Program | The people who watch the demonstrations and decide pass or fail. They run nothing. They attend. | None |

## Getting started

### Prerequisites

- **Inputs.** The ground truth is required. Your project constraints are optional: the people with their percent allocation, and the target date or weeks. Give both and the plan fits them. Give one and the skill backs into the other. Give neither and it proposes a default and asks.
- **A terminal and Node.js**, only to run the install line. Get Node.js from https://nodejs.org (choose LTS). Nothing in the skills needs it after that.
- **Python 3.9 or later**, to run the scripts. Check with `python3 --version`. Nothing else to install, not even for Word files.
- **git**, to keep the plan under version control.
- **GitHub permission** to create issues in the repository and to create a Project in the organisation or account. Ask an organisation admin if you do not have it. Planning works without it. Only the GitHub step needs it.
- **Single sign-on (SSO).** If your organisation enforces it, authorise the token: github.com/settings/tokens, click the token's "Configure SSO" button, click "Authorize" next to the organisation.
- **A token**, only at the GitHub step. For a board owned by an organisation, a fine-grained token for the one repository with Issues read and write, Metadata read, and the organisation permission Projects read and write. Only for a board owned by your user account, a classic token from the pre-filled link https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown, which ticks `repo` and `project`. Set a 7-day expiry and revoke the token when you are done. [docs/plan-owner-guide.md](docs/plan-owner-guide.md#the-token) has the steps.

Pick your system. Each block takes you from nothing to a project folder. The full steps are in [docs/setup.md](docs/setup.md): [macOS](docs/setup.md#macos), [Windows](docs/setup.md#windows), [Linux](docs/setup.md#linux).

<details>
<summary>macOS</summary>

1. Open Terminal: press Command and Space, type Terminal, press Return.
2. Install Node.js: download the LTS installer from https://nodejs.org and open it. Or run `brew install node` if you use Homebrew.
3. Check it: run `node --version` and `npm --version`. Each prints a version number.
4. Run `python3 --version` and `git --version`. A window may offer to install developer tools. Click Install and wait.
5. Make your project folder: `mkdir my-plan`, then `cd my-plan`, then `git init`. Or `cd` into an existing folder.
6. Run the install line below.

</details>

<details>
<summary>Windows</summary>

1. Open PowerShell: click Start, type PowerShell, press Enter.
2. Install Node.js LTS from https://nodejs.org with its installer. Tick the option to install necessary tools if offered.
3. Install Python 3 from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
4. Install Git for Windows from https://git-scm.com.
5. Close PowerShell and open it again. Run `node --version`, `npm --version`, `python --version` and `git --version`. Each prints a version number. On Windows the command may be `python` and not `python3`. The scripts accept either.
6. Make your project folder: `mkdir my-plan; cd my-plan; git init`. Or `cd` into an existing folder.
7. Run the install line below.

</details>

<details>
<summary>Linux</summary>

1. Open a terminal.
2. Debian or Ubuntu: `sudo apt install nodejs npm python3 git`. Fedora: `sudo dnf install nodejs npm python3 git`. If `node --version` is below 22.20, install Node.js from https://nodejs.org instead.
3. Check with `node --version`, `npm --version`, `python3 --version` and `git --version`.
4. Make your project folder: `mkdir my-plan`, then `cd my-plan`, then `git init`. Or `cd` into an existing folder.
5. Run the install line below.

</details>

To run the scripts outside a skill, see the [contributing guide](CONTRIBUTING.md#run-the-scripts-yourself).

Install the agent skills:

Using npx:

```bash
npx skills add sct-will/carrydown --all
```

Manually:

<details>
<summary>Manual install (no Node.js)</summary>

1. Open https://github.com/sct-will/carrydown, click the green Code button, then Download ZIP, and unzip it.
2. Copy the three folders inside `skills/` into your agent's skills folder. The paths are in the table under [Install options](#install-options).
3. Restart your agent.

</details>

Restart your agent.

1. **Plan owner.** Open your coding agent in your project folder (the folder you made above). No folder yet? Say:

   > Make a folder called my-plan with a git repository and work there.

   You will see: the agent working in the new folder.

2. **Plan owner.** Say:

   > Do you have the carrydown-ground-truth skill?

   You will see: yes, and its start sentence.

3. **Plan owner.** Put your document (.docx or .md) in `docs/source/`, then say:

   > Set up a project plan from docs/source/\<file\>.

   Then answer the interview, or say "use your default". The document is the only required input. You will also be asked about your constraints: the people, the target date or weeks, both, or neither for now. Everyone is assumed to be full time unless you say otherwise. You will see: "carrydown: interview, step 1 of 6".

4. **Plan owner.** Review the plan. Say:

   > Show me the load table and the critical path.

   Then, when it is right:

   > Yes, the plan is right.

   You will see: the checker reporting 0 findings.

5. **Lead reviewer.** A senior engineer reads the generated specifications in `docs/spec/` for about an hour and asks for changes before anything goes to GitHub.

6. **Plan owner or delivery manager.** Say:

   > Create the GitHub issues and the board.

   Open the token link the agent gives you. Read the dry-run counts, then say:

   > Go ahead.

   You will see: the board link.

7. **Plan owner, then Engineers.** Say:

   > Generate the developer skill.

   Send the install line to each engineer. They start an item by naming it, for example "Work on WI-07". You will see: the install line per agent.

**Program.** Attends each milestone demonstration and decides pass or fail against the criteria written before the work.

The long form, with the interview, the review hour, the token and the team rhythm, is [docs/plan-owner-guide.md](docs/plan-owner-guide.md).

## What you get

```text
docs/
  ground-truth/        rendered Markdown, section index, figures
  spec/
    plan.yaml          the schedule as data
    README.md          conventions, schedule, comment templates, index
    m1-.../            one folder per milestone
      milestone.md     the sub-epic content
      <id>-<slug>.md   one specification per work item
  dev/skills/<project>-dev/
    SKILL.md  README.md  references/
```

On GitHub: labels, one Epic, one sub-epic per milestone, one issue per work item as a sub-issue of its sub-epic, an Epic roll-up comment (with a Constraints block: target delivery, and people and allocation by track), and a project board with the Work unit, Track, Complete by and Checkpoint fields and Table, Board and Roadmap views.

## Install options

- `--all` installs the three skills for every coding agent found on this computer, without asking. The installer adds folders such as `.claude/` and `.agents/` to your project. Commit only the ones your team uses.
- `-a <agent>` installs for one agent. Example: `npx skills add sct-will/carrydown --skill '*' -a claude-code`.
- `-g` installs for your user instead of the current project.
- `--list` shows the skills without installing them. With no options the installer lets you choose from a list.

| Agent | `-a` value | Project folder | User folder |
| --- | --- | --- | --- |
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` | `~/.copilot/skills/` |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `codex` | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` |
| IBM Bob | `bob` | `.bob/skills/` | `~/.bob/skills/` |

The installer supports many more agents. The full and current list is in its documentation: https://github.com/vercel-labs/skills/blob/main/docs/agents.md.

Generic path. Any other agent that reads the Agent Skills format (https://agentskills.io) can use the skills. Copy the three folders in `skills/` into the folder where that agent looks for skills, or tell the agent to read `skills/<name>/SKILL.md`.

No Node.js? Skip the installer. Copy the three folders in `skills/` into your agent's skills folder from the table above. They are self-contained.

## Sample

The sample is a fictional expense approvals service: requirements, two governance rules, a development standard, a business analyst note, two people and eleven weeks. The carrydown skills turned that ground truth into a plan, specifications, issues and a board.

- The repository, with the ground truth, the plan and every specification: https://github.com/sct-will/carrydown-sample
- The issues the skills created: https://github.com/sct-will/carrydown-sample/issues
- The public project board: https://github.com/users/sct-will/projects/2
- Its README, which holds the renderings and the sample output: https://github.com/sct-will/carrydown-sample#readme

## FAQ

**Does it write code?** No. It carries the plan down to the point where a developer and their agent can start. The developer skill then makes each work item start from its specification.

**What does it send to GitHub?** Issue titles and bodies built from your specification files, labels, and project fields. Nothing is sent without `--apply`. The scripts talk only to `api.github.com`. See [docs/security.md](docs/security.md).

**Can I use Jira?** Not yet. The GitHub scripts are for GitHub only. The specification folder and `plan.yaml` are plain files that another tool can read.

**What if my document has no section numbers?** Ask the agent to propose numbering in the source document, approve it, and have the agent render the document again. Specifications cite sections by number.

**How do I remove it?** Run `npx skills remove`, or delete the three skill folders. The files under `docs/` in your project are yours.

More answers, including "npx: command not found", are in [docs/faq.md](docs/faq.md).

## Words used here

<details>
<summary>Eight terms</summary>

- **Ground truth.** The document or documents the project must obey: architecture, requirements, rules, standards.
- **Work item.** The smallest piece of work a person can finish, show and close. It has one specification and one issue.
- **Work unit.** A time block with its own length and an exit gate. It replaces the fixed-length sprint.
- **Sub-epic.** A GitHub issue for one milestone, placed under the Epic. Its work items are sub-issues.
- **Load table.** A table of how much work each person has in each work unit.
- **Critical path.** The longest chain of items that depend on each other. It sets the earliest finish date.
- **Exit gate.** The one sentence that must be true for a work unit to count as done.
- **Program item.** Work the program owns outside the plan, such as recruiting a pilot team or getting an approval.

</details>

## Contributing

Contributions are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) explains how to report a problem, propose a change, run the checks (`python3 scripts/selftest.py` and `python3 scripts/lint_prose.py`) and get a review. Issue forms and a pull request template guide you.

## Code of conduct

This project follows the Contributor Covenant. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). To report a problem, open an issue with the Conduct report form.

## Security

Report a vulnerability privately through GitHub. See [SECURITY.md](SECURITY.md). The carrydown skills store only your GitHub token file, and it never prints or commits the token.

## Licence

Code is licensed under the Apache License 2.0, see [LICENSE](LICENSE). The sample document, the templates text, the skills prose, the documents and the images are licensed under Creative Commons Attribution 4.0 International, see [LICENSE-CONTENT.md](LICENSE-CONTENT.md).

Will Scott, Ph.D.
