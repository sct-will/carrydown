![carrydown. An AI agent plans the project around real people, then carries the architecture to every issue and every engineer's coding agent. Two skills you install, one skill is generated for your engineers. On the right, the architecture document feeds the plan, one spec per work item, sub-epics and issues, the project board, and the engineer in the agentic editor.](docs/images/hero.png)

# carrydown

Give your coding agent the architecture document, or other context, and optionally the project constraints: the number of engineers who will work on the project and the target duration. It drafts the plan, writes one specification per work item, carries both into GitHub as milestones, issues and a project board, and generates an agent skill every engineer's agent uses to read the right sections before it writes code. Two skills you install, one skill is generated for your engineers.

[![CI](https://github.com/sct-will/carrydown/actions/workflows/ci.yml/badge.svg)](https://github.com/sct-will/carrydown/actions/workflows/ci.yml) [![Licence](https://img.shields.io/github/license/sct-will/carrydown?v=2)](LICENSE) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-2%20skills-teal)](https://agentskills.io)

## Getting started

Run this in your project folder and pick your coding agent:

```bash
npx skills add sct-will/carrydown
```

Put your document in `docs/source/` and tell your agent:

> Set up a project plan from this document.

To look before you install, open [the sample board](https://github.com/users/sct-will/projects/2), or [open the sample in a Codespace](https://codespaces.new/sct-will/carrydown) and watch the checker and a dry run of the issues without touching GitHub.

## How it works

![How carrydown works. Two lanes. Plan owner, an engineering or product manager: step 1 Generate with carrydown-ground-truth, in: architecture document plus people and dates, out: plan.yaml and one spec per work item; step 2 Review, no skill, read and edit the plan and specs with the agent; step 3 Carry down to GitHub with carrydown-plan-to-github, out: epic, a sub-epic per milestone, issues with specs, board, engineers' skill. One install line goes down to the Engineers lane: step 4 Work the issues, "Work on WI-03", the agent invokes the skill, reads the spec and the cited sections, then plans the code. The ground truth document is the only amber element and a thin amber thread runs from it through steps 1 and 3 into step 4.](docs/images/handoff.png)

1. **Generate.** You have the ground truth, usually an architecture document. Your agent interviews you about people, time and dates, then writes the plan and one specification per work item. Skill: [carrydown-ground-truth](skills/carrydown-ground-truth/SKILL.md).
2. **Review.** You read the plan and the specifications and edit them with the agent until they are right. No separate reviewer.
3. **Carry down to GitHub.** Say "put the plan on GitHub". Then the agent generates an epic, a sub-epic per milestone, an issue per work item with its specification, the board and the engineers' skill. It shows a dry run first and writes nothing until you say yes. Skill: [carrydown-plan-to-github](skills/carrydown-plan-to-github/SKILL.md).
4. **Work the issues.** Each engineer installs the engineers' skill once and says "Work on WI-03". Their agent reads the specification and the sections it cites, then plans the code. The install line names the skill's folder in your repository and the engineer's agent:

   ```bash
   npx skills add https://github.com/<owner>/<repo>/tree/main/docs/dev/skills/<project>-dev -a <agent>
   ```

   In the sample it is `npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a claude-code`.

You are the plan owner, an engineering manager or a product manager, and you need not write code. The [plan owner guide](docs/plan-owner-guide.md) walks each step with you.

## The sample, real and public

[![Issue 9 in the sample repository, WI-03 Approval routing engine, as GitHub renders it. Open, parent Milestone 2, Route to approvers. The body gives the target completion date, the checkpoint, why the item exists, then the AI engineering notes: a link to the specification, a link to the engineers' skill, the instruction to install it once and ask your coding agent to work on WI-03, and the ground truth sections 3.4, 3.5 and 7.1.](docs/images/issue-9.png)](https://github.com/sct-will/carrydown-sample/issues/9)

*What step 4 opens: [issue 9](https://github.com/sct-will/carrydown-sample/issues/9) and [the specification it links to](https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md).*

[![The sample's GitHub Project as a table grouped by work unit, with the Title, Track, Complete by and Checkpoint columns. Five work units from 1 February to 23 April 2027, each with its milestone row and its work items, for example WI-03 Approval routing engine on the Workflow track, complete by 19 February 2027, checkpoint 26 February 2027.](docs/images/board.png)](https://github.com/users/sct-will/projects/2)

*What step 3 built: [the board](https://github.com/users/sct-will/projects/2), shown as a table grouped by work unit.*

The sample is a fictional expense approvals service, so the company, the people and the dates are invented. Everything the two skills made from it is real and public in [carrydown-sample](https://github.com/sct-will/carrydown-sample): [plan.yaml](https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/plan.yaml), the nine specifications, fifteen issues, the board and [the generated engineers' skill](https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev). A copy sits in [`sample/expense-approvals/`](sample/expense-approvals/) for the self test.

## What the agent asks you

The first skill interviews you in six short steps. Nothing is written to GitHub until the second skill shows you a dry run and you say yes.

| The agent asks | You answer with |
| --- | --- |
| Which documents must the project obey, and which wins if two disagree? | File paths, and the winner |
| Who does the work, which part of the system does each person own, from when, and at what share of their time? | Names, a track each, start dates, days off |
| When must it ship, or how many weeks do you have? | A date, a number of weeks, or "derive the date" |
| Which repository, and which coding agents do the engineers use? | owner/repo and the agents |
| What must the people who watch each milestone demonstration see to call it done? | Their words, which become acceptance criteria |
| How is the code built, tested and merged here? | The commands and the branch rule |

Then it shows the schedule, each person's load per work unit, the critical path (the chain of items that sets the end date) and the slack (days to spare) before every checkpoint, and asks you to review. If you have a date and no team, say so, and it derives the capacity; if you have a team and no date, it derives the date. [docs/inputs.md](docs/inputs.md) has the details.

## What you get

- **A plan** in `docs/spec/plan.yaml`: milestones, tracks, owners and dates fitted to your people and time, with a load table and a critical path, and a written reason for every milestone.
- **One specification per work item**, the smallest piece of work an engineer can finish and show, citing the sections it comes from and checked against the plan by a script that also runs in continuous integration.
- **GitHub issues**, one per work item under a sub-epic per milestone, each telling the engineer's agent what to read.
- **A GitHub Project board** with work units, tracks, dates and checkpoints filled in.
- **The engineers' skill**, generated from your specifications and committed in your repository, so "Work on WI-03" makes any coding agent read the specification and its sections before touching code.

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

## How the plan is composed

The agent builds the plan around people and the part of the system each one owns. Each engineer owns one track and stays on one theme, one part of the system, at a time, so they switch context less. A milestone takes items from the tracks it needs. The tracks meet at a named joint check, a short dated integration check between tracks. The milestone ends with one demonstration of integrated functionality, given by the engineers whose tracks meet. Size divided by allocation gives calendar time, and nobody passes 100 percent of their time in a work unit. Slack, the days to spare, sits before every checkpoint. The critical path, the chain of items that sets the end date, is read for single points of failure. The reason for each milestone is written in the plan, and the checker's "Planning review" reports coverage, theme switches, slack and load so you can argue with it. [The method](docs/method.md) lists the ten rules.

## How it compares

Plan mode and spec-driven tools plan one task from one specification, and Claude Code Project Management (CCPM) turns requirements into issues; carrydown carries one agreed ground truth across every task, dates the plan around named people and checks every specification against it, so it sits beside any of them. The FAQ has [the longer comparison](docs/faq.md#how-does-this-compare-with-plan-mode-spec-driven-tools-superpowers-and-ccpm) and [whether this is just prompts](docs/faq.md#isnt-this-just-prompts).

It is not waterfall: the plan is files in Git, the work units stretch to fit the work, and [changing the plan is cheap](docs/faq.md#isnt-this-waterfall).

## Why "carrydown"

Systems engineers call it flow-down: a requirement at the top of a system traced to every part below that must honour it. [The method](docs/method.md) carries it to the keyboard.

## Prerequisites

You need a coding agent and Node.js 22.20 or later; your agent checks for Python 3.9 and git and tells you what to do. For step 3 you need permission to create issues and a project in the repository, and a GitHub token, which the second skill helps you create.

## Install options

<details>
<summary>Install for one agent, every agent, your user account or by hand</summary>

- `--skill '*' -a <agent>` installs both skills for one agent without questions, for example `npx skills add sct-will/carrydown --skill '*' -a claude-code`.
- `--all` installs for every supported agent; commit only the folders your engineers use.
- `-g -a <agent>` installs for your user account. Keep the `-a`, or `-g` writes into every supported agent's folder.
- `--list` shows the skills without installing them.

| Agent | `-a` value | Project folder | User folder |
| --- | --- | --- | --- |
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` | `~/.copilot/skills/` |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `codex` | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` |
| IBM Bob | `bob` | `.bob/skills/` | `~/.bob/skills/` |

The installer knows [many more agents](https://github.com/vercel-labs/skills/blob/main/docs/agents.md), and any agent that reads the [Agent Skills format](https://agentskills.io) can use the skills. Without Node.js, copy the two folders in `skills/` into the folder from the table. Restart your agent afterwards.

The installer prints third-party security scans; [docs/security.md](docs/security.md) explains what each skill touches.

</details>

<details>
<summary>Set up macOS, Windows or Linux from nothing</summary>

[docs/setup.md](docs/setup.md) goes from a computer with nothing installed to a project folder ready for the install line: [macOS](docs/setup.md#macos), [Windows](docs/setup.md#windows), [Linux](docs/setup.md#linux). If you cannot install programs, the Codespace has everything.

</details>

## Contributing and licence

[CONTRIBUTING.md](CONTRIBUTING.md) shows how to run the scripts and checks yourself, under the [code of conduct](CODE_OF_CONDUCT.md); [SECURITY.md](SECURITY.md) covers private reports. Code is under [Apache 2.0](LICENSE) and the words and images under [CC BY 4.0](LICENSE-CONTENT.md), so reuse the diagrams with attribution to Will Scott. More: [plan owner guide](docs/plan-owner-guide.md), [FAQ](docs/faq.md), [method](docs/method.md), [changelog](CHANGELOG.md).

If carrydown helped you, star the repository so the next plan owner finds it. If it broke on your document, open a ["My ground truth looks like this"](https://github.com/sct-will/carrydown/issues/new?template=ground_truth.yml) issue, because that is the feedback I most want.
