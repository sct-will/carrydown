# carrydown

carrydown uses two packaged artificial intelligence (AI) agent skills to turn your architecture document into a project plan, specifications, GitHub issues and a project board. It then generates a project-specific skill that guides each engineer's coding agent through the work.

[![Continuous integration status](https://github.com/sct-will/carrydown/actions/workflows/ci.yml/badge.svg)](https://github.com/sct-will/carrydown/actions/workflows/ci.yml) [![License](https://img.shields.io/github/license/sct-will/carrydown?v=2)](LICENSE) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-2%20skills-teal)](https://agentskills.io)

[Start here](#start-here) | [How it works](#how-it-works) | [Explore the sample](#explore-the-sample) | [What you get](#what-you-get) | [Contributing and license](#contributing-and-license)

<br />

## Start here

**Starting a new plan?** Follow [Install carrydown and start your first plan](docs/setup.md). It covers computer setup, installation and the first conversation with your agent. If you have already installed the skills, use the shortcut at the top of that guide.

**Have a plan to review or publish?** Continue with [Review and publish your plan](docs/plan-owner-guide.md).

<br />

## How it works

![How carrydown works. Two lanes. Plan owner, an engineering or product manager: step 1 Generate, the plan owner runs carrydown-ground-truth in their agent, in: architecture document plus people and dates, out: plan.yaml and one spec per work item; step 2 Review, the plan and specs are human reviewed, with the agent making the edits; step 3 Carry down to GitHub, the plan owner runs carrydown-plan-to-github in their agent, out: epic, a sub-epic per milestone, issues with specs, board, engineers' skill, with the note dry run first, nothing is written until you say yes. One install line goes down to the Engineers lane: step 4 Work the issues, the engineer says "Work on WI-03" for work item WI-03, the agent invokes the skill, reads the spec and the cited sections, then plans the code. The ground truth document is the only amber element. A thin amber thread, labeled ground truth, cited by section, runs from it through steps 1 and 3 into step 4.](docs/images/handoff.png)

1. **Generate.** Give your agent the ground truth, usually an architecture document, and any other relevant context. If you know the team size and target project duration, include them. The `carrydown-ground-truth` skill interviews you, then drafts a plan and one specification per work item around your constraints. Each engineer has a track, or lane of work. Each milestone ends with an integrated demonstration.
2. **Review.** Review the plan in `docs/spec/plan.yaml` and the specifications under `docs/spec/`. Edit them with your agent until they are right. You decide the owners, dates, scope and order.
3. **Carry down to GitHub.** Commit and push the approved plan and specifications first. Then say "Put the plan on GitHub." The `carrydown-plan-to-github` skill shows dry runs and asks for approval before creating the issues and board. It creates a parent epic for the plan, a sub-epic for each milestone, and an issue linking to each work item's specification. Finally, it generates the engineers' skill.
4. **Work the issues.** Each engineer installs the generated skill once, then names a work item: "Work on WI-03." Their agent reads the specification and the sections it cites, then plans the code. The generated skill is named after the project.

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

## Contributing and license

[CONTRIBUTING.md](CONTRIBUTING.md) shows how to run the scripts and checks yourself, under the [code of conduct](CODE_OF_CONDUCT.md); [SECURITY.md](SECURITY.md) covers private reports. Everything in this repository is licensed under [Apache 2.0](LICENSE). Optional reading: [frequently asked questions](docs/faq.md), [security guide](docs/security.md), [changelog](CHANGELOG.md).

If carrydown helped you, star the repository so the next plan owner finds it. If you see any bug, open an [issue](https://github.com/sct-will/carrydown/issues).
