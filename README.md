# carrydown

carrydown is an open source project for planning and engineering handoffs with artificial intelligence (AI) coding agents. Your agent uses two carrydown skills to turn agreed project sources into a project plan, specifications, GitHub epics and issues, and a project board. The sources can include architecture, requirements, governance rules, development standards and company context. The last step generates a project-specific skill for your engineers' coding agents.

The name reflects the idea: carry agreed decisions and rules down into the plan, the GitHub work and the instructions your engineers’ coding agents use.

**That generated skill is the handoff.** An engineer installs it once, then names a work item. The skill directs their coding agent to read the specification, the source sections it cites and the project conventions before planning the code.

The plan is built around your team's availability and target date. You can also supply engineers' skills and work preferences, and the agent proposes best-match tracks and assignments with its reasoning. These inputs are optional. When they are absent or unclear, planning continues with the default capacity, dependency and context-switching rules. Scripts check the specifications against the plan. A second-pass agent review then challenges the completed plan against its sources, constraints, staffing choices and engineering handoffs. It records coverage, reasoning and risk in tables, and the agent fixes the findings you accept. You approve the plan and publication to GitHub.

[![Continuous integration status](https://github.com/sct-will/carrydown/actions/workflows/ci.yml/badge.svg)](https://github.com/sct-will/carrydown/actions/workflows/ci.yml) [![License](https://img.shields.io/github/license/sct-will/carrydown?v=2)](LICENSE) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-2%20skills-teal)](https://agentskills.io)

[Start here](#start-here) | [FAQ](#frequently-asked-questions) | [How it works](#how-it-works) | [Explore the sample](#explore-the-sample) | [What you get](#what-you-get) | [AI governance](#how-does-carrydown-support-ai-governance) | [Contributing and license](#contributing-and-license)

<br />

## Start here

**Starting a new plan?** Follow [Install carrydown and start your first plan](docs/setup.md). It covers computer setup, installation and the first conversation with your agent. If you have already installed the skills, use the shortcut at the top of that guide. The agent asks one extra question before it starts: whether everyone who can read the repository may see all of your documents and staffing notes. Most teams answer yes and nothing else changes. If some documents are confidential, read [who may see your documents](docs/setup.md#before-you-add-documents-who-may-see-them) first.

**Have a plan to review or publish?** Continue with [Review and publish your plan](docs/plan-owner-guide.md).

<br />

## How it works

![A context folder with DOCX, PDF, TXT and PNG files and optional team availability, skills and work preferences feed the carrydown flow. Your AI agent proposes best-match tracks and assignments, plans around capacity and dependencies, and drafts a specification for each work item. After script checks, a second-pass agent review challenges scope, staffing choices, dates, tracks, milestones and dependencies. It produces coverage and risk tables. You decide which findings the agent repairs and approve the result. The agent then creates GitHub epics, issues, a project board and the engineers' skill after dry runs. Engineers name a work item by its identifier, and that skill directs their agent to the specification and cited source sections. An amber thread carries the agreed context through each handoff.](docs/images/handoff.png)

*The diagram predates the confidentiality controls and is kept as a legacy picture until it is redrawn. Read it with these two corrections. The context folder can stay outside the project. The engineers' agent reads the approved context of the work item, which holds the exact text of the cited sections, not the source documents.*

1. **Plan for your team.** Tell the agent where the ground truth is. It can include Word, Markdown, plain text, PDF and image files for architecture, requirements, governance rules, development standards and company context. The agent inventories the files and creates reviewable Markdown renderings. It reports files it cannot read and continues with the sources it can process. Put higher-precedence sources first when they can conflict. If you know the team size and target project duration, include them. You may also supply each engineer's skills and preferred work. The agent uses them to propose best-match tracks and assignments, explains tradeoffs, and falls back to the default assignment approach when the information is missing or unclear. The `carrydown-ground-truth` skill interviews you, then drafts a plan and one specification per work item around your constraints. Each engineer has a track, or lane of work. Each milestone ends with an integrated demonstration. Names, skills, days off and allocation are kept in a private file on your machine, not in the plan. Confidential documents can stay outside the project: the first question the agent asks decides whether drafting happens in the repository or in a private workspace.
2. **Challenge, repair and approve.** After the normal checks, the agent makes a separate adversarial pass over the completed plan and specifications. It looks for missing scope, resource conflicts, dependency errors and better sequencing. Review its coverage and risk tables in `docs/spec/plan-review.md`, then let the agent apply the repairs you accept. You decide the owners, dates, scope and order.
3. **Publish to GitHub.** Say "Put the plan on GitHub." The `carrydown-plan-to-github` skill shows a short preview of what will be shared, with whom and where, and asks in one prompt whether those outputs may be shared and whether it may create the GitHub items. It then writes the approved files, a small receipt and the engineers' skill, and you commit and push them. After dry runs it creates a parent epic for the plan, a sub-epic for each milestone, an issue linking to each work item's specification, and the board.
4. **Start a work item.** Each engineer installs the generated skill once, then names the work item identifier, for example, "Work on [work item ID]". The skill checks that the item's approved context is intact and current. Its agent then reads the specification, the approved context and the project conventions before planning the code. The approved context holds the exact text of the source sections the item cites, and nothing else from your documents. Every reader of the repository can read it, so only text approved for all of them is ever in it. The generated skill is named after the project.

<br />

## Explore the sample

Explore carrydown's sample project board, milestone epics and work item issues. Each work item links to its specification. You can browse the sample before installing.

The sample is based on a fictional expense approvals service, so the company, the people and the dates are invented. Everything the two skills made from it is real and public in [carrydown-sample](https://github.com/sct-will/carrydown-sample): [plan.yaml](https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/plan.yaml), [the nine specifications](https://github.com/sct-will/carrydown-sample/tree/main/docs/spec), [fifteen issues](https://github.com/sct-will/carrydown-sample/issues?q=is%3Aissue), [the board](https://github.com/users/sct-will/projects/2) and [the generated engineers' skill](https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev). A copy sits in [`sample/expense-approvals/`](sample/expense-approvals/) for the self test, and [a recorded run](docs/sample-run.md) shows what each script printed when the sample was carried into a throwaway repository.

The public repository, its issues, its board and the screenshot of issue 9 below were made before approved contexts and receipts existed. They are waiting to be republished from the current sample, which needs the owner's own GitHub account. Until then, [`sample/expense-approvals/`](sample/expense-approvals/) is the current output.

[![Issue 9 in the sample repository, WI-03 Approval routing engine, as GitHub renders it. Open, parent Milestone 2, Route to approvers. The body gives the target completion date, the checkpoint, why the item exists, then the AI engineering notes: a link to the specification, a link to the engineers' skill, the instruction to install it once and ask your coding agent to work on WI-03, and the ground truth sections 3.4, 3.5 and 7.1.](docs/images/issue-9.png)](https://github.com/sct-will/carrydown-sample/issues/9)

*What step 4 opens: [issue 9](https://github.com/sct-will/carrydown-sample/issues/9) and [the specification it links to](https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md).*

[![The sample's GitHub Project as a table grouped by work unit, with the Title, Track, Complete by and Checkpoint columns. Five work units from 1 February to 23 April 2027, each with its milestone row and its work items, for example WI-03 Approval routing engine on the Workflow track, complete by 19 February 2027, checkpoint 26 February 2027.](docs/images/board.png)](https://github.com/users/sct-will/projects/2)

*What step 3 built: [the board](https://github.com/users/sct-will/projects/2), shown as a table grouped by work unit, a time box of one to three weeks with an exit gate.*

<br />

## What you get

Your AI agent generates these artifacts using the carrydown skills. The plan records each source in precedence order. Every work item can cite sections from one or more sources, with dates and capacity checked against the named team.

- **A plan** in `docs/spec/plan.yaml`: milestones, tracks, owner ids and dates fitted to your people and time, with a load table and a critical path, and a written reason for every milestone. Optional skills and work preferences inform explainable best-match assignments without becoming prerequisites. The committed plan holds ids and tracks only. Names, skills, days off and allocation stay in a private file on your machine, and the load table and date checks run there.
- **One specification per work item**, the smallest piece of work an engineer can finish and show, citing the sections it comes from and checked against the plan by a script that also runs in continuous integration (automatic checks on every pull request). The checks pass from a clean clone, with no private workspace and no original documents.
- **One approved context per work item** in `docs/context/`: the exact text of the source sections the item cites, the decisions that settle conflicts between them and what the text may be used for. You approve this text for everyone who can read the repository, and it is the only part of your documents that reaches the engineers' agents.
- **A release receipt** in `docs/release/`: a small public file that names the approved release, its state and its expiry, so the checks and the engineers' skill can find it.
- **A second-pass review report**, with source coverage, evidence, reasoning and risk, plus your decisions and the checks on accepted repairs. The agent challenges how the plan will work for each engineer, beyond the script's consistency checks.
- **GitHub issues**, one per work item under a sub-epic per milestone, each telling the engineer's agent what to read.
- **A GitHub Project board** with work units, tracks, dates and checkpoints filled in.
- **The engineers' skill**, generated from your specifications and committed in your repository, so "Work on [work item ID]" tells the coding agent to check and read that item's specification and approved context before touching code.

The plan and specifications stay in version control, with source citations, recorded planning decisions and automated consistency checks. Your team reviews the generated work and approves what is shared and what is published. These provide a practical foundation for governing AI-generated planning and engineering handoffs.

<details>
<summary>Where the files go in your project</summary>

```text
docs/
  spec/
    plan.yaml          the schedule as data: ids, tracks and decisions, no staffing details
    README.md          conventions, schedule, comment templates, index
    plan-review.md     second-pass coverage, findings, decisions, repair evidence
    m1-.../            one folder per milestone
      milestone.md     the sub-epic content
      <id>-<slug>.md   one specification per work item
  context/
    <id>.md            the approved text of the sections the item cites
    <id>.bundle.json   its integrity record
  release/
    <request-id>.receipt.json   the public receipt of one approval
  dev/skills/<project>-dev/
    SKILL.md  README.md  references/  scripts/check_context.py
  ground-truth/        optional. Renderings, only when you answered yes to the one question
  source/              optional, ignored by git. Originals, only if you want a local copy
```

Your private workspace is not in the project. It lives in `~/.carrydown/workspaces/<slug>/` and holds the staffing file, the originals and renderings of restricted documents, and every draft, snapshot and approval record. A pointer to it, `.carrydown/local.yaml`, is the only trace in the project, and git ignores it.

</details>

[Read the planning method](docs/method.md) for the rules behind milestones, tracks, capacity and checkpoints.

<br />

## How does carrydown support AI governance?

You can give the agent governance rules, engineering standards and company-specific context along with the technical document. Word, Markdown and plain text render directly. The agent can make reviewed Markdown extractions from readable PDF, image and other files. The plan records each source's version and precedence, and each work item records source-specific section references. The checker validates those references against the rendered document while you draft, and against the item's approved context in a clean clone. The generated engineers' skill checks that context and points the coding agent at it, so the agent reads the applicable rules before planning code.

This makes organizational context part of the ordinary engineering handoff. A company can codify rules for security, privacy, accessibility, data handling, approved patterns or review evidence in maintained source documents, then trace each applicable rule into specifications, issues and the agentic editor. You review the drafts and approve exactly what is shared, with whom and where, after seeing a preview and a dry run. The plan, specifications, source versions and recorded decisions stay in your repository for review as the project changes.

The automated checks validate consistency with the plan and whether cited sections exist. The second-pass agent review examines whether the completed work covers the sources and fits the team's constraints, and records the evidence and risks for your decision. Agent review can miss problems. Your team still judges whether the interpretation and resulting work meet your organization's requirements.

Some documents are not for everyone who can read the project repository. Carrydown can keep those in a private workspace and share only the sections you approve. It cannot hide text from a teammate who can read the repository, and it cannot recall text that has already been delivered. For what carrydown protects and what it cannot, read the [enterprise security questions](docs/enterprise-security.md).

<br />

## Frequently asked questions

<details>
<summary>What do I need to start?</summary>

One or more project sources, and an answer to one question: can everyone who can read this repository see all of these documents and your staffing notes? Read [who may see your documents](docs/setup.md#before-you-add-documents-who-may-see-them), then follow [Install carrydown and start your first plan](docs/setup.md). The sources can mix Word, Markdown, plain text, PDF and image files, and they can stay where you keep them. The agent reports unreadable files and continues when it can process at least one intended source.

</details>

<details>
<summary>Do my confidential documents end up in the project repository?</summary>

Not unless you say everyone who can read the repository may see them. The agent asks that one question first. On yes, it drafts in the repository as before. On no, it drafts in a private workspace on your machine, and the repository receives only the outputs you approve. Originals are optional in the project either way. Ignore rules stop new files from being tracked, but they do not erase a file an earlier commit already holds. Read [the enterprise security questions](docs/enterprise-security.md) for what carrydown protects and what it cannot.

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

[CONTRIBUTING.md](CONTRIBUTING.md) shows how to run the scripts and checks yourself, under the [code of conduct](CODE_OF_CONDUCT.md); [SECURITY.md](SECURITY.md) covers private reports. Everything in this repository is licensed under [Apache 2.0](LICENSE). Optional reading: [frequently asked questions](docs/faq.md), [enterprise security questions](docs/enterprise-security.md) beside the [security guide](docs/security.md), [changelog](CHANGELOG.md).

**Want to add an integration?** See the [community integration invitations](https://github.com/sct-will/carrydown/issues/1). We welcome contributors for Jira, Azure Boards, GitLab, Linear, Confluence, SharePoint, Figma and Slack. Each issue describes a first contribution and how the pieces could connect. Comment with your proposed approach before starting. These are community opportunities, with no committed delivery dates.

If carrydown helped you, star the repository so the next plan owner finds it. If you see any bug, open an [issue](https://github.com/sct-will/carrydown/issues).
