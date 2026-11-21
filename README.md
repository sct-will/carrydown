# carrydown

[Carried-context development](https://carriedcontext.dev) is an approach to agentic development that ties every spec to the same ground truth, cites the sources, and delivers every approved change to every coding agent. carrydown is the open source reference implementation. Your agent uses two carrydown skills to turn agreed project sources into a project plan, specifications, GitHub epics and issues, and a project board. The sources can include architecture, requirements, governance rules, development standards and company context. The last step generates a project-specific skill for your engineers' coding agents.

**Keep your team aligned as the project changes.**

Tell your agent what changed or where a specification seems wrong. It identifies potentially affected work, preserves engineer corrections and carries approved updates into the engineering handoff.

The name reflects the idea: carry agreed decisions and rules down into the plan, the GitHub work and the instructions your engineers’ coding agents use.

**That generated skill is the handoff.** An engineer installs it once, then names a work item. The skill directs their coding agent to read the specification, the source sections it cites and the project conventions before planning the code.

The plan is built around your team's availability and target date. You can also supply engineers' skills and work preferences, and the agent proposes best-match tracks and assignments with its reasoning. These inputs are optional. When they are absent or unclear, planning continues with the default capacity, dependency and context-switching rules. Scripts check the specifications against the plan. A second-pass agent review then challenges the completed plan against its sources, constraints, staffing choices and engineering handoffs. It records coverage, reasoning and risk in tables, and the agent fixes the findings you accept. You approve the plan and publication to GitHub.

[![Continuous integration status](https://github.com/sct-will/carrydown/actions/workflows/ci.yml/badge.svg)](https://github.com/sct-will/carrydown/actions/workflows/ci.yml) [![License](https://img.shields.io/github/license/sct-will/carrydown?v=2)](LICENSE) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-2%20skills-teal)](https://agentskills.io)

[Start here](#start-here) | [What to say](#what-to-say) | [FAQ](https://carriedcontext.dev/faq/) | [How it works](#how-it-works) | [Explore the sample](#explore-the-sample) | [What you get](#what-you-get) | [AI governance](#how-does-carrydown-support-ai-governance) | [Contributing and license](#contributing-and-license)

<br />

## Start here

**Starting a new plan?** Follow [Install carrydown and start your first plan](docs/setup.md). It covers computer setup, installation and the first conversation with your agent. If you have already installed the skills, use the shortcut at the top of that guide. The agent asks one extra question before it starts: whether everyone who can read the repository may see all of your documents and staffing notes. Most teams answer yes and nothing else changes. If some documents are confidential, read [who may see your documents](docs/setup.md#before-you-add-documents-who-may-see-them) first.

**Requirements.** A coding agent that supports Agent Skills, and Node.js 22.20 or later for the standard installer, which also uses Git. Without Node.js, use the [manual installation](docs/install-options.md#manual-install-without-nodejs). The skills also need Python 3.9 or newer and Git. They check both when they start, and offer to install Python after your yes. The [setup guide](docs/setup.md#before-anything-python) shows the manual Python steps for macOS, Windows and Linux.

**Three words you meet first.** The ground truth is the set of documents your project must obey, a skill is a folder of instructions that your coding agent loads, and a dry run previews what a command would do and writes nothing. The [glossary](docs/plan-owner-guide.md#glossary) explains the others.

**Have a plan to review or publish?** Continue with [Review and publish your plan](docs/plan-owner-guide.md).

**The project changed after planning?** Read [when the project changes](#when-the-project-changes) and say what changed.

**Something is not working?** Read [troubleshooting](docs/troubleshooting.md): installation, source formats, GitHub permissions, publishing and updates.

<br />

## What to say

Ordinary language is the normal entry point. You do not need to learn the names of the skills or the scripts.

**Plan owner**

| What you want to do | What to say |
| --- | --- |
| Create a plan | "Set up a project plan from these documents." |
| Publish the approved plan | "Put the plan on GitHub." |
| Update an existing project | "This changed: [describe the change or provide revised documents]." |

**Engineers**

| What you want to do | What to say |
| --- | --- |
| Start a work item | "Work on WI-03." |
| Raise a specification problem | "This specification seems wrong because [explanation]." |

When an engineer raises a problem, the agent drafts a request and shows it. It is not sent until the engineer posts it.

The first owner row is for a project that has no plan yet. For a project that already has one, use the third row, even when you bring revised documents.

The plan owner uses the two installed skills, engineers use the generated project skill, and stakeholders review milestone outcomes.

If your agent does not pick up the right skill, name it. This is a fallback, not the main phrase:

> "Use carrydown-ground-truth to update this existing project."

<br />

## How it works

![A context folder with DOCX, PDF, TXT and PNG files and optional team availability, skills and work preferences feed the carrydown flow. Your AI agent proposes best-match tracks and assignments, plans around capacity and dependencies, and drafts a specification for each work item. After script checks, a second-pass agent review challenges scope, staffing choices, dates, tracks, milestones and dependencies. It produces coverage and risk tables. You decide which findings the agent repairs and approve the result. The agent then creates GitHub epics, issues, a project board and the engineers' skill after dry runs. Engineers name a work item by its identifier, and that skill directs their agent to the specification and cited source sections. An amber thread carries the agreed context through each handoff.](docs/images/handoff.png)

*The diagram predates the confidentiality controls and is kept as a legacy picture until it is redrawn. Read it with these two corrections. The context folder can stay outside the project. The engineers' agent reads the approved context of the work item, which holds the exact text of the cited sections, not the source documents.*

1. **Plan for your team.** Tell the agent where the ground truth is. It can include Word, Markdown, plain text, PDF and image files for architecture, requirements, governance rules, development standards and company context. The agent inventories the files and creates reviewable Markdown renderings. It reports files it cannot read and continues with the sources it can process. Put higher-precedence sources first when they can conflict. If you know the team size and target project duration, include them. You may also supply each engineer's skills and preferred work. The agent uses them to propose best-match tracks and assignments, explains tradeoffs, and falls back to the default assignment approach when the information is missing or unclear. The `carrydown-ground-truth` skill interviews you, then drafts a plan and one specification per work item around your constraints. Each engineer has a track, or lane of work. Each milestone ends with an integrated demonstration. Names, skills, days off and allocation are kept in a private file on your machine, not in the plan. Confidential documents can stay outside the project: the first question the agent asks decides whether drafting happens in the repository or in a private workspace.
2. **Challenge, repair and approve.** After the normal checks, the agent makes a separate adversarial pass over the completed plan and specifications. It looks for missing scope, resource conflicts, dependency errors and better sequencing. Review its coverage and risk tables in `docs/spec/plan-review.md`, then let the agent apply the repairs you accept. You decide the owners, dates, scope and order.
3. **Publish to GitHub.** Say "Put the plan on GitHub." The `carrydown-plan-to-github` skill shows a short preview of what will be shared, with whom and where, and asks in one prompt whether those outputs may be shared and whether it may create the GitHub items. It then writes the approved files, a small receipt and the engineers' skill, and commits and pushes them after a separate yes from you. After dry runs it creates a parent epic for the plan, a sub-epic for each milestone, an issue linking to each work item's specification, and the board.
4. **Start a work item.** Each engineer installs the generated skill once, then names the work item identifier, for example, "Work on [work item ID]". The skill checks that the item's approved context is intact and current. Its agent then reads the specification, the approved context and the project conventions before planning the code. The approved context holds the exact text of the source sections the item cites, and nothing else from your documents. Every reader of the repository can read it, so only text approved for all of them is ever in it. The generated skill is named after the project.
5. **Update when the project changes.** Say "This changed: [describe the change or provide revised documents]." The `carrydown-ground-truth` skill compares the change with the reviewed sources and the current work, and the plan owner approves the update. The `carrydown-plan-to-github` skill then carries it into the engineering handoff.

<br />

## When the project changes

Projects change after planning. A requirement is revised, a company rule changes, or an engineer finds that a specification does not fit the implementation. The ground-truth skill compares that information with the reviewed sources and current work. It prepares focused corrections and shows conflicts to the plan owner. After approval, the existing publishing skill carries the update into the engineering handoff.

In more detail, and before any name for it: your agent looks at what changed, finds the work that the change could touch, and checks the work an engineer has already corrected. It keeps those corrections when they fit the change and shows you the ones that conflict. You see one review, decide, and approve. Nothing is rewritten because regenerating it would be easier. The same path serves a changed source and an engineer's report that a specification seems wrong. The method pages call this step reconciliation.

**How to hand over a revised document.** Open your agent in the project's own folder, the one your plan was made in. Then name where the revised file is in the same sentence, for example: "This changed: the revised architecture document is at ~/Documents/architecture.docx." Keep the file where you keep your sources. You do not need to move it into the project. You can also describe the change in words or paste the changed passage. The agent reads and compares before it shows you anything, so the review takes a while to appear.

**One approval, then one more sentence.** Your approval of the review accepts the changes to the drafts. It publishes nothing. "Put the plan on GitHub." is a separate sentence: the publishing skill then shows what would be shared, with whom and where, and asks for that disclosure approval on its own line before it writes anything.

**How engineers learn of an update.** Nothing is pushed or sent to them. GitHub may notify people who watch an updated issue, which is not a delivery guarantee. After the update is released and published, an engineer's next run of the check for a work item shows the approved delta: the files and passages that changed since their last check. An engineer who does not pull or does not run the check keeps the earlier material, so tell the team when the timing matters.

Repository checks assess the material they can observe. For sources kept elsewhere, provide the revised material. A configured integration can add automatic observation later. The owner guidance also prompts review when the team makes significant decisions. When you are unsure whether a change is significant, say it anyway: the agent assesses it.

There are still two skills you install and one skill generated for your engineers. The first skill, `carrydown-ground-truth`, now covers initial planning and updates. It does not watch your documents, and an update starts when you say so. The [owner guide](docs/plan-owner-guide.md#when-the-project-changes) lists what counts as a significant change, what the one review shows and how to resume an interrupted update.

[Recover a plan or publication](docs/recovery.md) covers identity choices, source references, issue reconciliation and resumable board updates. If an update stopped partway, say "Resume the project update." and read [resume a project update](docs/recovery.md#resume-a-project-update).

<br />

## Explore the sample

You can inspect a fictional expense approvals project before installing anything. The company, the people and the dates are invented. The planning artifacts are real output from an AI agent using carrydown.

Employees submit expense reports with receipts. Approval follows spending limits and reporting lines, with no self-approval and delegates for absent approvers. The service sends notifications, keeps an uneditable audit trail for seven years and exports approved expenses to finance each night.

The ground truth is one architecture document of about 3,000 words: requirements, design, company rules and their owners, user findings, interfaces and risks. Its logging rule is deliberately simple, so you can trace it from the source through the specifications to the instructions for the coding agents. Real projects involve many documents, overlapping rules, exceptions and decisions from different owners.

Start with [the sample project board](https://github.com/users/sct-will/projects/2). Open a work item, for example [issue 9, the approval routing engine](https://github.com/sct-will/carrydown-sample/issues/9), to find its specification and the source sections it cites. As you explore, notice:

- **The complete set of artifacts the AI agent generated.** A dated plan with five milestones and nine work items across two tracks. Each work item has a specification and an issue on the board. A generated, project-specific skill carries the instructions for the engineers' coding agents. Each milestone also states what the team must demonstrate together.
- **The detail carried down from the source.** Open [the ledger export specification](sample/expense-approvals/docs/spec/m4-pilot/wi-09-ledger-export.md). Its "Ground truth" row names the source sections. Its "Contract" section quotes the applicable rules, and its acceptance criteria turn them into checks. The rule that log lines never carry amounts appears in both.
- **How related work connects.** The ledger export depends on [the audit log](sample/expense-approvals/docs/spec/m3-enforce-policy/wi-07-audit-log.md). Its specification says why and names the shared behavior. Both specifications quote the same logging rule, word for word, from the same section of the source. When that rule changes, tell your agent. It finds the work the change may affect and brings the proposed updates together for your approval.
- **What reaches the coding agent.** Read [the generated skill](sample/expense-approvals/docs/dev/skills/expense-approvals-dev/SKILL.md). It directs the coding agent to check its approved inputs, then read the approved source excerpts, the full specification and the project conventions before planning the code. If the approved inputs have changed, it directs the agent to reassess its plan.

[![Issue 9 in the sample repository, WI-03 Approval routing engine, as GitHub renders it. Open, parent Milestone 2, Route to approvers. The body gives the target completion date, the checkpoint, why the item exists, then the AI engineering notes: a link to the specification, a link to the engineers' skill, the instruction to install it once and ask your coding agent to work on WI-03, and the ground truth sections 3.4, 3.5 and 7.1.](docs/images/issue-9.png)](https://github.com/sct-will/carrydown-sample/issues/9)

*Issue 9 as GitHub renders it, and [the specification it links to](https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md).*

Everything the two skills made is public in [carrydown-sample](https://github.com/sct-will/carrydown-sample), and a copy sits in [`sample/expense-approvals/`](sample/expense-approvals/) for the self test. [A recorded run](docs/sample-run.md) shows what each script printed when the sample was carried into a throwaway repository. With a local copy of this repository you can also run the sample's read-only preview, which changes no file and needs no token; [the sample's own page](sample/expense-approvals/README.md#run-it) shows the command and what it prints.

The public repository, its issues, its board and the screenshot above were made before approved contexts and receipts existed. They are waiting to be republished from the current sample, which needs the owner's own GitHub account. Until then, the copy in this repository is the current output.

<br />

## What you get

Your AI agent generates these artifacts using the carrydown skills. The plan records each source in precedence order. Every work item can cite sections from one or more sources, with dates and capacity checked against the named team.

- **A plan** you review as a page in your browser: milestones, tracks, owners and dates fitted to your people and time, with a load table and a critical path, and a written reason for every milestone. Optional skills and work preferences inform explainable best-match assignments without becoming prerequisites. The agent writes the plan page into your private workspace from the same data the checks use and refreshes it after every change, and you ask for changes in the conversation. The committed plan, `docs/spec/plan.yaml`, holds ids and tracks only. Names, skills, days off and allocation stay in a private file on your machine, and the load table and date checks run there.
- **One specification per work item**, the smallest piece of work an engineer can finish and show, citing the sections it comes from and checked against the plan by a script that also runs in continuous integration (automatic checks on every pull request). The checks pass from a clean clone, with no private workspace and no original documents.
- **One approved context per work item** in `docs/context/`: the exact text of the source sections the item cites, the decisions that settle conflicts between them and what the text may be used for. You approve this text for everyone who can read the repository, and it is the only part of your documents that reaches the engineers' agents.
- **A release receipt** in `docs/release/`: a small public file that names the approved release, its state and its expiry, so the checks and the engineers' skill can find it.
- **A second-pass review report**, with source coverage, evidence, reasoning and risk, plus your decisions and the checks on accepted repairs. The agent challenges how the plan will work for each engineer, beyond the script's consistency checks.
- **GitHub issues**, one per work item under a sub-epic per milestone, each telling the engineer's agent what to read.
- **A GitHub Project board** with work units, tracks, dates and checkpoints filled in.
- **The engineers' skill**, generated from your specifications and committed in your repository, so "Work on [work item ID]" tells the coding agent to check and read that item's specification and approved context before touching code.

> **Important: when the project changes**
>
> If requirements, architecture or company rules change significantly, or an engineer finds a specification problem, say:
>
> **"This changed: [describe the change or provide revised documents]."**
>
> Your agent will review the existing project, preserve engineer corrections and show proposed updates for approval.

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
    SKILL.md  README.md  references/  scripts/check_context.py  scripts/check_python.py
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

Some documents are not for everyone who can read the project repository. carrydown can keep those in a private workspace and share only the sections you approve. It cannot hide text from a teammate who can read the repository, and it cannot recall text that has already been delivered. For what carrydown protects and what it cannot, read the [enterprise security questions](docs/enterprise-security.md).

<br />

## Contributing and license

[CONTRIBUTING.md](CONTRIBUTING.md) shows how to run the scripts and checks yourself, under the [code of conduct](CODE_OF_CONDUCT.md); [SECURITY.md](SECURITY.md) covers private reports. Everything in this repository is licensed under [Apache 2.0](LICENSE). Optional reading: [troubleshooting](docs/troubleshooting.md), [enterprise security questions](docs/enterprise-security.md) beside the [security guide](docs/security.md), [changelog](CHANGELOG.md).

**Want to add an integration?** See the [community integration invitations](https://github.com/sct-will/carrydown/issues/1). We welcome contributors for Jira, Azure Boards, GitLab, Linear, Confluence, SharePoint, Figma and Slack. Each issue describes a first contribution and how the pieces could connect. Comment with your proposed approach before starting. These are community opportunities, with no committed delivery dates.

If carrydown helped you, star the repository so the next plan owner finds it. If you see any bug, open an [issue](https://github.com/sct-will/carrydown/issues).
