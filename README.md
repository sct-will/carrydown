# carrydown

carrydown uses two packaged artificial intelligence (AI) agent skills to turn your architecture document into a project plan, specifications, GitHub issues and a project board. It then generates a project-specific skill that guides each engineer's coding agent through the work.

[![Continuous integration status](https://github.com/sct-will/carrydown/actions/workflows/ci.yml/badge.svg)](https://github.com/sct-will/carrydown/actions/workflows/ci.yml) [![License](https://img.shields.io/github/license/sct-will/carrydown?v=2)](LICENSE) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-2%20skills-teal)](https://agentskills.io)

[Quick start](#quick-start) | [How it works](#how-it-works) | [Explore the sample](#explore-the-sample) | [What you get](#what-you-get) | [What the agent asks you](#what-the-agent-asks-you) | [Requirements and installation options](#requirements-and-installation-options) | [Contributing and license](#contributing-and-license)

<br />

## Quick start

Start with the [setup guide](docs/setup.md). It walks you through preparing your computer. If your coding agent, Node.js, Python and Git are ready, follow these steps.

1. **Open your project folder.** This is the folder where your document and the plan will live. Open an existing project in your coding agent, or create and open a new folder named `carrydown-plan`.
2. **Install the two skills.** Open a terminal in that folder. A terminal is where you enter commands; use your agent's terminal if it has one. Copy this command, paste it into the terminal and press Enter:

   ```bash
   npx skills add sct-will/carrydown
   ```

   If asked to download the `skills` installer, confirm to continue. Select both `carrydown-ground-truth` and `carrydown-plan-to-github`, your coding agent, and **Project** scope. If asked for an installation method, keep **Symlink**, the recommended choice. [The installation walkthrough](docs/setup.md#install-the-two-skills) explains the choices and what success looks like.
3. **Check the installation.** In the same terminal, run:

   ```bash
   npx skills list
   ```

   Look for both skill names. Then close and reopen your coding agent or start a new agent session, and open the same project folder. If either skill is missing, use the [installation help](docs/setup.md#when-something-does-not-work).
4. **Add your document and start.** In your project folder, create a folder named `docs`, then a folder named `source` inside it. Copy your Word (`.docx`) or Markdown (`.md`) document into `docs/source/`. In the agent's chat, say:

   > Set up a project plan from this document.

   Your agent checks the setup, then interviews you about the document and your constraints. If it asks to initialize Git, it is asking to keep a local history of your plan. You can approve that for this project. You review the plan and specifications before anything goes to GitHub.

<br />

## How it works

![How carrydown works. Two lanes. Plan owner, an engineering or product manager: step 1 Generate, the plan owner runs carrydown-ground-truth in their agent, in: architecture document plus people and dates, out: plan.yaml and one spec per work item; step 2 Review, the plan and specs are human reviewed, with the agent making the edits; step 3 Carry down to GitHub, the plan owner runs carrydown-plan-to-github in their agent, out: epic, a sub-epic per milestone, issues with specs, board, engineers' skill, with the note dry run first, nothing is written until you say yes. One install line goes down to the Engineers lane: step 4 Work the issues, the engineer says "Work on WI-03" for work item WI-03, the agent invokes the skill, reads the spec and the cited sections, then plans the code. The ground truth document is the only amber element. A thin amber thread, labeled ground truth, cited by section, runs from it through steps 1 and 3 into step 4.](docs/images/handoff.png)

1. **Generate.** Give your agent the ground truth, usually an architecture document, and any other relevant context. If you know the team size and target project duration, include them. The [carrydown-ground-truth](skills/carrydown-ground-truth/SKILL.md) skill interviews you, then drafts a plan and one specification per work item around your constraints. Each engineer has a track, or lane of work. Each milestone ends with an integrated demonstration.
2. **Review.** Review the plan in `docs/spec/plan.yaml` and the specifications under `docs/spec/`. Edit them with your agent until they are right. You decide the owners, dates, scope and order.
3. **Carry down to GitHub.** Commit and push the approved plan and specifications first. Then say "Put the plan on GitHub." The [carrydown-plan-to-github](skills/carrydown-plan-to-github/SKILL.md) skill shows dry runs and asks for approval before creating the issues and board. It creates a parent epic for the plan, a sub-epic for each milestone, and an issue linking to each work item's specification. Finally, it generates the engineers' skill.
4. **Work the issues.** Each engineer installs the generated skill once, then names a work item: "Work on WI-03." Their agent reads the specification and the sections it cites, then plans the code. The generated skill is named after the project.

<details>
<summary>Install the generated skill for engineers</summary>

Commit and push the generated skill folder before engineers install it. Use your repository, branch, project name and agent in this command:

```bash
npx skills add https://github.com/<owner>/<repo>/tree/<branch>/docs/dev/skills/<project>-dev -a <agent>
```

</details>

<br />

## Explore the sample

Explore carrydown's sample project board, milestone epics and work item issues. Each work item links to its specification. You can browse the sample before installing.

The sample is based on a fictional expense approvals service, so the company, the people and the dates are invented. Everything the two skills made from it is real and public in [carrydown-sample](https://github.com/sct-will/carrydown-sample): [plan.yaml](https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/plan.yaml), [the nine specifications](https://github.com/sct-will/carrydown-sample/tree/main/docs/spec), [fifteen issues](https://github.com/sct-will/carrydown-sample/issues?q=is%3Aissue), [the board](https://github.com/users/sct-will/projects/2) and [the generated engineers' skill](https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev). A copy sits in [`sample/expense-approvals/`](sample/expense-approvals/) for the self test, and [a recorded run](docs/sample-run.md) shows what each script printed when the sample was carried into a throwaway repository.

[![Issue 9 in the sample repository, WI-03 Approval routing engine, as GitHub renders it. Open, parent Milestone 2, Route to approvers. The body gives the target completion date, the checkpoint, why the item exists, then the AI engineering notes: a link to the specification, a link to the engineers' skill, the instruction to install it once and ask your coding agent to work on WI-03, and the ground truth sections 3.4, 3.5 and 7.1.](docs/images/issue-9.png)](https://github.com/sct-will/carrydown-sample/issues/9)

*What step 4 opens: [issue 9](https://github.com/sct-will/carrydown-sample/issues/9) and [the specification it links to](https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md).*

[![The sample's GitHub Project as a table grouped by work unit, with the Title, Track, Complete by and Checkpoint columns. Five work units from 1 February to 23 April 2027, each with its milestone row and its work items, for example WI-03 Approval routing engine on the Workflow track, complete by 19 February 2027, checkpoint 26 February 2027.](docs/images/board.png)](https://github.com/users/sct-will/projects/2)

*What step 3 built: [the board](https://github.com/users/sct-will/projects/2), shown as a table grouped by work unit, a time box of one to three weeks with an exit gate.*

<br />

## What you get

The plan and every specification trace back to the same ground truth, with dates and capacity checked against the named team.

- **A plan** in `docs/spec/plan.yaml`: milestones, tracks, owners and dates fitted to your people and time, with a load table and a critical path, and a written reason for every milestone.
- **One specification per work item**, the smallest piece of work an engineer can finish and show, citing the sections it comes from and checked against the plan by a script that also runs in continuous integration (automatic checks on every pull request).
- **GitHub issues**, one per work item under a sub-epic per milestone, each telling the engineer's agent what to read.
- **A GitHub Project board** with work units, tracks, dates and checkpoints filled in.
- **The engineers' skill**, generated from your specifications and committed in your repository, so "Work on WI-03" tells the coding agent to read the specification and its sections before touching code.

<details>
<summary>Where the files go in your project</summary>

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

</details>

[Read the planning method](docs/method.md) for the rules behind milestones, tracks, capacity and checkpoints.

<br />

## What the agent asks you

At startup, the [carrydown-ground-truth](skills/carrydown-ground-truth/SKILL.md) skill interviews you in six short steps.

| The agent asks | You answer with |
| --- | --- |
| Which documents must the project obey, and which wins if two disagree? | File paths, and the winner |
| Who does the work, which part of the system does each person own, from when, and at what share of their time? | Names, a track each (a lane of work one engineer owns, such as back end or front end), allocation percentages, start dates, days off |
| When must it ship, or how many weeks do you have? | A date, a number of weeks, or "derive the date" |
| Which repository, and which coding agents do the engineers use? | owner/repo and the agents |
| What must the stakeholders see at each milestone demonstration to call it done? | Their words, which become acceptance criteria |
| How is the code built, tested and merged here? | The commands and the branch rule |

After the interview, the agent shows you the schedule and each person's load per work unit, or time block. It shows the critical path, the chain of items that sets the end date, and the slack, or days to spare, before each checkpoint. A checkpoint is a dated integration check between tracks. Then it asks you to review the plan. If you have a date and no team, it derives the capacity needed. If you have a team and no date, it derives the date. [Read the input guide](docs/inputs.md) for details.

<br />

## Requirements and installation options

For the usual installation, follow [Quick start](#quick-start). This section explains what you need and offers other ways to install.

| What you need | Why you need it | Where to start |
| --- | --- | --- |
| A coding agent with access to your project files and permission to run commands | It runs the skills and helps you review the plan. | Use your team's agent, or choose one from the install list below. Its account or subscription is separate from carrydown. |
| Node.js 22.20 or later | It provides `npx`, which runs the skills installer. | [Prepare your computer](docs/setup.md#prepare-your-computer). |
| Python 3.9 or later | It runs the planning and checking scripts. | [Prepare your computer](docs/setup.md#prepare-your-computer). Install a current Python 3 release if you are starting fresh. |
| Git | The installer uses it to download the skills. It also keeps a history of your plan and specifications. | [Prepare your computer](docs/setup.md#prepare-your-computer). Git works locally before you connect to GitHub. |

### Choose where to install

**This project is the recommended starting point.** The skills are available in the project folder where you run the command. Open that folder whenever you use carrydown.

**All your projects is a personal installation.** It makes the skills available to your agent across projects on this computer. It does not install them for other people. Choose one scope; you do not need to run both commands.

Open your agent's entry below for complete commands and its official setup instructions. Each command selects both carrydown skills and the named agent. You still review the installer's confirmation. After installation, [check the skills and reopen your agent](docs/setup.md#check-the-installation).

<details>
<summary>Claude Code</summary>

[Set up Claude Code](https://code.claude.com/docs/en/quickstart) if you have not installed and signed in to it yet.

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

[Set up GitHub Copilot](https://code.visualstudio.com/docs/setup/copilot) if you have not installed and signed in to it yet.

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

[Set up Cursor](https://cursor.com/docs) if you have not installed and signed in to it yet.

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

[Set up Codex](https://developers.openai.com/codex/quickstart) if you have not installed and signed in to it yet.

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

[Set up Gemini CLI](https://geminicli.com/docs/get-started/installation/) if you have not installed and signed in to it yet.

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

[Set up IBM Bob](https://www.ibm.com/products/bob) if you have not installed and signed in to it yet.

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent bob
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent bob --global
```

</details>

The installer supports [more agents](https://github.com/vercel-labs/skills/blob/main/docs/agents.md). The skills use the [Agent Skills format](https://agentskills.io). Run the installation where your agent works; a remote workspace needs the skills and supporting software in that workspace.

<details>
<summary>Install by copying folders, without Node.js</summary>

Use the [manual installation walkthrough](docs/setup.md#manual-install-without-nodejs). It explains how to download the repository, find the two skill folders and copy them to the right place. You still need a coding agent, Python and Git for planning.

These are the destination folders. A dot at the beginning means the folder may be hidden. `~/` means your home folder, such as `/Users/your-name/` on macOS or `C:\Users\your-name\` on Windows. Use the project column for this project or the home column for a personal installation.

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

For most people, choosing one agent in Quick start is enough.

</details>

### Get help with installation

The [setup guide](docs/setup.md) covers [macOS](docs/setup.md#macos), [Windows](docs/setup.md#windows), [Linux](docs/setup.md#linux), [checking the installation](docs/setup.md#check-the-installation) and [common problems](docs/setup.md#when-something-does-not-work). The installer may show security scan results; [the security guide](docs/security.md#what-skillssh-shows) explains them.

### When you are ready for GitHub

You can draft and review the plan locally first. To publish it, you need a GitHub repository, permission to create issues there, permission to create the project board, and a GitHub token. The second skill walks you through these when you say "Put the plan on GitHub." It shows a dry run and waits for your approval before publishing. The [plan owner guide](docs/plan-owner-guide.md#the-github-step) explains the handoff.

<br />

## Contributing and license

[CONTRIBUTING.md](CONTRIBUTING.md) shows how to run the scripts and checks yourself, under the [code of conduct](CODE_OF_CONDUCT.md); [SECURITY.md](SECURITY.md) covers private reports. Everything in this repository is licensed under [Apache 2.0](LICENSE). More: [plan owner guide](docs/plan-owner-guide.md), [FAQ](docs/faq.md), [method](docs/method.md), [changelog](CHANGELOG.md).

If carrydown helped you, star the repository so the next plan owner finds it. If you see any bug, open an [issue](https://github.com/sct-will/carrydown/issues).
