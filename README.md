# carrydown

carrydown is an open source project for planning and engineering handoffs with artificial intelligence (AI) coding agents. Your agent uses two carrydown skills to turn agreed project sources into a project plan, specifications, GitHub epics and issues, and a project board. The sources can include architecture, requirements, governance rules, development standards and company context. The last step generates a project-specific skill for your engineers' coding agents.

The name reflects the idea: carry agreed decisions and rules down into the plan, the GitHub work and the instructions your engineers’ coding agents use.

**That generated skill is the handoff.** An engineer installs it once, then names a work item. The skill directs their coding agent to read the specification, the source sections it cites and the project conventions before planning the code.

The plan is built around your team's availability and target date. You can also supply engineers' skills and work preferences, and the agent proposes best-match tracks and assignments with its reasoning. These inputs are optional. When they are absent or unclear, planning continues with the default capacity, dependency and context-switching rules. Scripts check the specifications against the plan. A second-pass agent review then challenges the completed plan against its sources, constraints, staffing choices and engineering handoffs. It records coverage, reasoning and risk in tables, and the agent fixes the findings you accept. You approve the plan and publication to GitHub.

[![Continuous integration status](https://github.com/sct-will/carrydown/actions/workflows/ci.yml/badge.svg)](https://github.com/sct-will/carrydown/actions/workflows/ci.yml) [![License](https://img.shields.io/github/license/sct-will/carrydown?v=2)](LICENSE) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-2%20skills-teal)](https://agentskills.io)

[Start here](#start-here) | [FAQ](#frequently-asked-questions) | [How it works](#how-it-works) | [Explore the sample](#explore-the-sample) | [What you get](#what-you-get) | [AI governance](#how-does-carrydown-support-ai-governance) | [Contributing and license](#contributing-and-license)

<br />

## Start here

**Starting a new plan?** Follow [Install carrydown and start your first plan](docs/setup.md). It covers computer setup, installation and the first conversation with your agent. If you have already installed the skills, use the shortcut at the top of that guide.

**Have a plan to review or publish?** Continue with [Review and publish your plan](docs/plan-owner-guide.md).

<br />

## How it works

![A context folder with DOCX, PDF, TXT and PNG files and optional team availability, skills and work preferences feed the carrydown flow. Your AI agent proposes best-match tracks and assignments, plans around capacity and dependencies, and drafts a specification for each work item. After script checks, a second-pass agent review challenges scope, staffing choices, dates, tracks, milestones and dependencies. It produces coverage and risk tables. You decide which findings the agent repairs and approve the result. The agent then creates GitHub epics, issues, a project board and the engineers' skill after dry runs. Engineers name a work item by its identifier, and that skill directs their agent to the specification and cited source sections. An amber thread carries the agreed context through each handoff.](docs/images/handoff.png)

1. **Plan for your team.** Put the ground truth in `docs/source/`. It can include Word, Markdown, plain text, PDF and image files for architecture, requirements, governance rules, development standards and company context. The agent inventories the folder and creates reviewable Markdown renderings. It reports files it cannot read and continues with the sources it can process. Put higher-precedence sources first when they can conflict. If you know the team size and target project duration, include them. You may also supply each engineer's skills and preferred work. The agent uses them to propose best-match tracks and assignments, explains tradeoffs, and falls back to the default assignment approach when the information is missing or unclear. The `carrydown-ground-truth` skill interviews you, then drafts a plan and one specification per work item around your constraints. Each engineer has a track, or lane of work. Each milestone ends with an integrated demonstration.
2. **Challenge, repair and approve.** After the normal checks, the agent makes a separate adversarial pass over the completed plan and specifications. It looks for missing scope, resource conflicts, dependency errors and better sequencing. Review its coverage and risk tables in `docs/spec/plan-review.md`, then let the agent apply the repairs you accept. You decide the owners, dates, scope and order.
3. **Publish to GitHub.** Commit and push the approved plan and specifications first. Then say "Put the plan on GitHub." The `carrydown-plan-to-github` skill shows dry runs and asks for approval before creating the issues and board. It creates a parent epic for the plan, a sub-epic for each milestone, and an issue linking to each work item's specification. Finally, it generates the engineers' skill.
4. **Start a work item.** Each engineer installs the generated skill once, then names the work item identifier, for example, "Work on [work item ID]". The skill directs their agent to read the specification, its cited source sections and the project conventions before planning the code. The generated skill is named after the project.

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

Your AI agent generates these artifacts using the carrydown skills. The plan records each rendered source in precedence order. Every work item can cite sections from one or more sources, with dates and capacity checked against the named team.

- **A plan** in `docs/spec/plan.yaml`: milestones, tracks, owners and dates fitted to your people and time, with a load table and a critical path, and a written reason for every milestone. Optional skills and work preferences inform explainable best-match assignments without becoming prerequisites.
- **One specification per work item**, the smallest piece of work an engineer can finish and show, citing the sections it comes from and checked against the plan by a script that also runs in continuous integration (automatic checks on every pull request).
- **A second-pass review report**, with source coverage, evidence, reasoning and risk, plus your decisions and the checks on accepted repairs. The agent challenges how the plan will work for each engineer, beyond the script's consistency checks.
- **GitHub issues**, one per work item under a sub-epic per milestone, each telling the engineer's agent what to read.
- **A GitHub Project board** with work units, tracks, dates and checkpoints filled in.
- **The engineers' skill**, generated from your specifications and committed in your repository, so "Work on [work item ID]" tells the coding agent to read that item's specification and its sections before touching code.

The plan and specifications stay in version control, with source citations, recorded planning decisions and automated consistency checks. Your team reviews the generated work and approves publication. These provide a practical foundation for governing AI-generated planning and engineering handoffs.

<details>
<summary>Where the files go in your project</summary>

```text
docs/
  ground-truth/        rendered Markdown, section index, figures
  spec/
    plan.yaml          the schedule as data
    README.md          conventions, schedule, comment templates, index
    plan-review.md     second-pass coverage, findings, decisions, repair evidence
    m1-.../            one folder per milestone
      milestone.md     the sub-epic content
      <id>-<slug>.md   one specification per work item
  dev/skills/<project>-dev/
    SKILL.md  README.md  references/
```

</details>

[Read the planning method](docs/method.md) for the rules behind milestones, tracks, capacity and checkpoints.

<br />

## How does carrydown support AI governance?

You can put governance rules, engineering standards and company-specific context in the same `docs/source/` folder as the technical document. Word, Markdown and plain text render directly. The agent can make reviewed Markdown extractions from readable PDF, image and other files while retaining the originals. The plan records original and rendered files, versions, precedence and coverage limits. Each work item records source-specific section references. The checker validates those references against the correct rendered document. The generated engineers' skill maps the citations back to each source, so the coding agent reads the applicable rules before planning code.

This makes organizational context part of the ordinary engineering handoff. A company can codify rules for security, privacy, accessibility, data handling, approved patterns or review evidence in maintained source documents, then trace each applicable rule into specifications, issues and the agentic editor. You review the drafts and approve publication after seeing a dry run. The plan, specifications, source versions and recorded decisions stay in your repository for review as the project changes.

The automated checks validate consistency with the plan and whether cited sections exist. The second-pass agent review examines whether the completed work covers the sources and fits the team's constraints, and records the evidence and risks for your decision. Agent review can miss problems. Your team still judges whether the interpretation and resulting work meet your organization's requirements.

<br />

## Frequently asked questions

<details>
<summary>What do I need to start?</summary>

Put one or more project sources in `docs/source/`, then follow [Install carrydown and start your first plan](docs/setup.md). The folder can mix Word, Markdown, plain text, PDF and image files. The agent reports unreadable files and continues when it can process at least one intended source.

</details>

<details>
<summary>Do I need to supply engineer skills and work preferences?</summary>

No. They are optional inputs for a best-match proposal. When supplied, the agent compares them with the needs of each track and specialized work item. It considers fixed staffing decisions, required capabilities, preferences, availability, dependencies, workload and reduced handoffs, then records the proposed match and its reasoning for the plan owner to review.

Missing, partial or unclear staffing context never blocks planning or becomes a review finding. The agent continues with the default track, capacity, dependency and context-switching rules. The checker reports supplied context without scoring the match, and the second-pass review challenges its tradeoffs. The plan owner makes the final assignment decisions.

</details>

<details>
<summary>Who makes the final planning decisions?</summary>

The plan owner does. The agent drafts the plan, checks it, performs the second-pass review and applies accepted repairs. A person approves the owners, dates, scope, order and GitHub publication.

</details>

<details>
<summary>What GitHub token permissions are required?</summary>

You do not need a token to plan locally. Publishing issues and a project board requires a GitHub personal access token. For an organization-owned board, use a fine-grained token limited to the repository, with repository permissions **Issues: read and write** and **Metadata: read**, plus the organization permission **Projects: read and write**. For a board owned by your user account, use a classic token with the `repo` and `project` scopes because fine-grained tokens cannot access user-owned projects. The [publishing guide](docs/plan-owner-guide.md#the-token) walks through creation, checking, storage and revocation.

</details>

[Read the full FAQ](docs/faq.md) for setup, source formats, planning, GitHub permissions and ongoing changes.

[Recover a plan or publication](docs/recovery.md) for identity choices, source references, issue reconciliation and resumable board updates.

<br />

## Contributing and license

[CONTRIBUTING.md](CONTRIBUTING.md) shows how to run the scripts and checks yourself, under the [code of conduct](CODE_OF_CONDUCT.md); [SECURITY.md](SECURITY.md) covers private reports. Everything in this repository is licensed under [Apache 2.0](LICENSE). Optional reading: [frequently asked questions](docs/faq.md), [security guide](docs/security.md), [changelog](CHANGELOG.md).

**Want to add an integration?** See the [community integration invitations](https://github.com/sct-will/carrydown/issues/1). We welcome contributors for Jira, Azure Boards, GitLab, Linear, Confluence, SharePoint, Figma and Slack. Each issue describes a first contribution and how the pieces could connect. Comment with your proposed approach before starting. These are community opportunities, with no committed delivery dates.

If carrydown helped you, star the repository so the next plan owner finds it. If you see any bug, open an [issue](https://github.com/sct-will/carrydown/issues).
