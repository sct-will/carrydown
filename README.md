![carrydown. Give every AI coding agent the architecture, not just the ticket. One ground-truth document becomes the plan, the specs, the issues, the project board and the developer skill in every agentic editor.](docs/images/hero.png)

# Give every AI coding agent the architecture, not just the ticket.

I wrote most of a sixty-page architecture document this year, and I doubt anyone has read it end to end since the review, because nobody can hold sixty pages in their head while they build, me included. An AI agent can hold all of it, every section and every rule. carrydown has that agent carry the right paragraph to every engineer, through a plan dated around your real people, one specification per piece of work citing its section, GitHub issues, a board, and a skill that makes each coding agent read it all before it changes code.

*Will Scott*

[![Work item WI-03 from the sample as a GitHub issue, beside the specification file its AI engineering notes link to. The issue gives the target date, the checkpoint, a link to the specification, a link to the developer skill and the ground truth sections 3.4, 3.5 and 7.1. The specification lists the milestone, track, dates, size and dependencies, then an outline from "Why this work item exists" to "Decisions recorded", with a contract that excerpts the cited sections.](docs/images/issue-and-spec.png)](https://github.com/sct-will/carrydown-sample/issues/9)

*A rendering of [the live WI-03 issue](https://github.com/sct-will/carrydown-sample/issues/9): its notes send the agent to the specification, and the specification to the sections it cites.*

## Getting started

Three ways in, and the first two need no install.

**Look.** Open the [public sample board](https://github.com/users/sct-will/projects/2), click WI-03, then follow its specification link to the sections it cites. That is what an engineer's agent reads before it starts.

**Try.** [Open the sample in a Codespace](https://codespaces.new/sct-will/carrydown), a ready-made computer in your browser. As it starts it runs the checker on the bundled sample, printing the schedule, the load table and the critical path, then a dry run of the issues it would create, without touching GitHub. "Codespaces: View Creation Log" shows it again.

**Install.** Run this line in your project folder, pick your coding agents, then tell your agent "Set up a project plan from this document." Nothing is written to GitHub until you say yes.

```bash
npx skills add sct-will/carrydown
```

## What it sounds like

The sample, from document to board. Code lines are what the scripts print; the rest is shortened.

> **You:** Set up a project plan from this document. It is `docs/source/architecture.md`.
>
> **Agent:** `carrydown: interview, step 1 of 6`. Which documents must the project obey, and which wins if two disagree? Five short steps follow, on people, dates, the repository, agents and tests.
>
> **You:** Show me the load table and the critical path.
>
> **Agent:** Each person's work against their allocated time, per work unit: `idris  60%  3 of 6d (50%)  4 of 9d (44%)  4 of 5d (74%)  0 of 6d  3 of 6d (50%)`. Nobody is over 100 percent, and the critical path `WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11` meets the target with two days to spare.
>
> **You:** Yes, the plan is right. Create the GitHub issues and the board.
>
> **Agent:** Dry run, nothing written yet: `1 Epic, 5 sub-epics, 9 work item issues`. Shall I go ahead?
>
> **You:** Go ahead. Then generate the developer skill.
>
> **Agent:** Done, and the board is at https://github.com/users/sct-will/projects/2. Send each engineer the line for their agent, such as `npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a claude-code`, or `-a cursor`, `-a github-copilot`, `-a codex`, `-a gemini-cli` or `-a bob`. They start an item by saying "Work on WI-03".

Before the GitHub step, a senior engineer reads the specifications for about an hour. The full output is in [a recorded run](docs/sample-run.md).

## How it works

![How carrydown works, in six steps. Step 1, two inputs: the ground truth, which is required and can be architecture, requirements, analyst notes, governance rules and development standards as Word or Markdown files; and the project constraints, which are optional: the people, the track each owns, the percent of their time, start dates, days off, and a delivery date or number of weeks with any breaks. The agent takes what you have: give both and the plan fits them, give one and the agent backs into the other. Step 2, carrydown-ground-truth renders the document to Markdown with a section index that every later file cites. Step 3, the plan and the specs: the plan file, one milestone file per milestone and one specification per work item, checked against the plan; the ground truth carries down into every spec and the agent's instructions, and the constraints become dates, owners and fields. Step 4, carrydown-plan-to-github creates the GitHub issues: labels, sub-epics, work item issues, sub-issue links and an epic roll-up comment, dry run first, then apply. Step 5, the GitHub Project board with Work unit, Track, Complete by and Checkpoint fields and table, board and roadmap views. Step 6, carrydown-dev-skill generates the developer skill, installed in every agentic editor; an engineer says "Work on WI-07" and their agent reads the spec and the cited ground truth before planning any code. Nothing is written to GitHub until you confirm, and every GitHub step runs as a dry run first.](docs/images/flow.png)

## What you get

Everything starts from your ground truth, the documents your project must obey: architecture, requirements, governance rules, standards. From it you get:

- **A plan** with milestones, owners and dates fitted to your people and time, a load table of each person's work per time block, and a critical path, the chain of items that sets the end date.
- **One specification per work item**, the smallest piece of work an engineer can finish and show, citing its sections and checked against the plan by a script that also runs in continuous integration.
- **GitHub issues**, one per work item, grouped under a sub-epic per milestone, each telling the agent what to read.
- **A GitHub Project board** with work units, tracks and dates filled in.
- **A developer skill** each engineer installs once, so "Work on WI-07" makes their agent read the specification and its sections before touching code.

[![The sample's GitHub Project board as a table grouped by work unit. Each milestone and work item shows its track, complete-by date, checkpoint and parent issue, for example WI-03 Approval routing engine on the Workflow track, complete by 24 February 2027, checkpoint "Routing meets inbox" on 26 February.](docs/images/board-table.png)](https://github.com/users/sct-will/projects/2)

*A rendering of [the live board](https://github.com/users/sct-will/projects/2), grouped by work unit.*

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

## Who does what

carrydown is for engineering leads, product managers and designers who own a plan and want every agent to follow it. You talk to the agent, which makes you the plan owner, and you need not write code. A senior engineer reads the specifications for about an hour before anything reaches GitHub, engineers install the skill the agent makes, and the people accountable watch each milestone's demonstration and decide whether it passed. The [plan owner guide](docs/plan-owner-guide.md#who-runs-what) has the full table.

## How it compares

Plan mode and spec-driven tools plan one task from one specification, and CCPM turns requirements into issues; carrydown carries one agreed ground truth across every task, dates the plan around named people and checks every specification against it, so it sits beside any of them. The FAQ has [the longer comparison](docs/faq.md#how-does-this-compare-with-plan-mode-spec-driven-tools-superpowers-and-ccpm) and [whether this is just prompts](docs/faq.md#isnt-this-just-prompts).

It is not waterfall: the plan is files in Git, the work units stretch to fit the work, and [changing the plan is cheap](docs/faq.md#isnt-this-waterfall).

## Why "carrydown"

Systems engineers call it flow-down: a requirement at the top of a system traced to every part below that must honour it. [The method](docs/method.md) carries it to the keyboard.

## Prerequisites

You need a coding agent and Node.js 22.20 or later; your agent checks for Python 3.9 and git and tells you what to do. GitHub permissions and a token matter only at the GitHub step, where the agent walks you through them.

## Install options

<details>
<summary>Install for one agent, every agent, your user account or by hand</summary>

- `--skill '*' -a <agent>` installs all three skills for one agent without questions, for example `npx skills add sct-will/carrydown --skill '*' -a claude-code`.
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

The installer knows [many more agents](https://github.com/vercel-labs/skills/blob/main/docs/agents.md), and any agent that reads the [Agent Skills format](https://agentskills.io) can use the skills. Without Node.js, copy the three folders in `skills/` into the folder from the table. Restart your agent afterwards.

The installer prints third-party security scans; [docs/security.md](docs/security.md) explains what each skill touches.

</details>

<details>
<summary>Set up macOS, Windows or Linux from nothing</summary>

[docs/setup.md](docs/setup.md) goes from a computer with nothing installed to a project folder ready for the install line: [macOS](docs/setup.md#macos), [Windows](docs/setup.md#windows), [Linux](docs/setup.md#linux). If you cannot install programs, the Codespace has everything.

</details>

## The sample

The sample is a fictional expense approvals service, so the company, people and dates are invented. What is real is everything the skills made from it: the plan, the nine specifications, the issues and the board, all live in [carrydown-sample](https://github.com/sct-will/carrydown-sample). A copy sits in [`sample/expense-approvals/`](sample/expense-approvals/) for the self test.

## Contributing and licence

[CONTRIBUTING.md](CONTRIBUTING.md) shows how to run the scripts and checks yourself, under the [code of conduct](CODE_OF_CONDUCT.md); [SECURITY.md](SECURITY.md) covers private reports. Code is under [Apache 2.0](LICENSE) and the words and images under [CC BY 4.0](LICENSE-CONTENT.md), so reuse the diagrams with attribution to Will Scott. More: [plan owner guide](docs/plan-owner-guide.md), [FAQ](docs/faq.md), [method](docs/method.md), [changelog](CHANGELOG.md).

[![CI](https://github.com/sct-will/carrydown/actions/workflows/ci.yml/badge.svg)](https://github.com/sct-will/carrydown/actions/workflows/ci.yml) [![Licence](https://img.shields.io/github/license/sct-will/carrydown?v=2)](LICENSE) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-3%20skills-teal)](https://agentskills.io)

If carrydown helped you, star the repository so the next plan owner finds it. If it broke on your document, open a ["My ground truth looks like this"](https://github.com/sct-will/carrydown/issues/new?template=ground_truth.yml) issue, because that is the feedback I most want.
