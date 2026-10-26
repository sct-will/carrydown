# The method

An AI agent plans the project around real people, then carries the architecture to every issue and every engineer's coding agent. Two skills you install, one skill is generated for your engineers.

The carrydown skills carry an agreed set of ground-truth sources down into a governed plan. The set can combine technical documents, requirements, governance rules, standards and company context in several file formats. The plan has one specification per work item, a set of GitHub issues, a project board and the engineers' skill that every issue links to. This optional reference explains the planning rules and why they matter. The plan owner and engineers make the decisions; the skills draft and check the files.

The idea is old in systems engineering, where it is called flow-down: a requirement at the top is traced to every part below it. The carrydown skills apply the same idea to software work done with coding agents. Agreed context follows one traceable line through the plan, the specifications, the issues, the board and the agent.

## The four steps

| Step | What happens | Who decides | What it produces |
| --- | --- | --- | --- |
| 1. Generate, with `carrydown-ground-truth` | The agent interviews the plan owner about people, time and dates. It drafts the plan and one specification per work item. | The plan owner decides, the agent drafts | The rendered ground truth, `plan.yaml` with its load table and critical path, and one specification per work item. |
| 2. Review | After the ordinary checks, the agent makes a separate adversarial pass over the completed set. It records coverage, evidence, reasoning and risk. The plan owner decides the repairs, and the agent applies and verifies accepted changes. | Plan owner | A review report, accepted repairs and a plan the owner approves, with 0 findings from the checker. |
| 3. Carry down to GitHub, with `carrydown-plan-to-github` | After a dry run and the plan owner's yes, the agent creates the issues and the board. Last, it generates the engineers' skill. | Plan owner, after each dry run | Issues, the board, and the engineers' skill with the install line to send each engineer. |
| 4. Start a work item | Each engineer installs the engineers' skill once and names the work item identifier, for example, "Work on [work item ID]". The agent reads the specification, the cited sections and the conventions, then plans the code. | Engineers show, the stakeholders decide | Code, closing comments with evidence, checkpoint comments and a demonstration note on each sub-epic. |

Planning decisions stay with the plan owner. The agent drafts, validates and populates. It does not decide who does what, when, or in which order.

## Second-pass agent review

The ground-truth skill runs this pass after the completed specifications pass the checker and before final owner approval. Its prompt lives in `templates/plan-review-prompt.md`, with a report template beside it. Each installed skill carries its own copies. Detailed review instructions are loaded only when that stage starts.

![The completed plan and specifications are reviewed against the ground truth and confirmed constraints. The agent challenges scope, people, dates, tracks, milestones, dependencies and handoffs, then presents coverage and findings tables without changing the plan. The plan owner accepts, rejects or defers findings. The agent applies accepted repairs, reruns checks and records remaining risk.](images/second-pass-review.png)

The review uses the actual ground truth, confirmed constraints and completed artifacts. It checks requirement coverage, people and allocation, engineer tracks, dependencies, milestones, integration, demonstrations and schedule risk. It reads each engineer's work week by week. The checker's earliest-finish calculation does not serialize an owner's items, so the agent also considers competing demands within the available time. Uncertain inputs and inferred daily sequences are recorded as limits.

The report at `docs/spec/plan-review.md` has coverage, findings and repair tables. Each finding cites evidence and explains its risk, confidence and proposed change. The plan owner accepts, rejects or defers it. The agent repairs the accepted changes in canonical files first, refreshes generated content and checks the result. A report with no findings still records what was assessed and what could not be verified. Agent review does not prove correctness.

For a published plan, the publishing skill offers the same review and a separate repair path. It preserves issue identifiers and human edits, previews external changes and verifies issues and board values after approval. The existing creation commands, plan format and sample remain valid without a review report. There is no new installed skill or required service.

## Before step 1: a ground truth that holds still

A ground truth is any mix of:

- an architecture document,
- requirements,
- business analyst notes,
- enterprise governance rules,
- development standards,
- company-specific context such as security, privacy and accessibility rules,
- diagrams, screenshots and other visual sources whose meaning affects the work.

Put the files together in `docs/source/`. Word, Markdown and plain text render directly. The agent can extract readable PDF, image and other formats into reviewed Markdown renderings. It records unreadable files as coverage limits and continues with readable sources. It stops only when none of the intended ground truth can be processed.

While you write it, verify claims about the existing world. Read the code. Run the test suite. Probe the live service. Measure. Anything you cannot prove, mark "verify at implementation" instead of asserting it. Then run adversarial passes: ask the agent, in a fresh context, to find what is missing, wrong or contradictory, and fold the findings back in with a changelog entry and, for architecture choices, a decision record.

The carrydown skills cannot write your document for you. They can help you review it: the ground-truth skill has interview prompts and review prompts.

## Step 1 in more detail: the plan

Work units are time boxes of variable length. A thin first slice may take a week and the core may take three. Breaks sit between them. There is no sprint vocabulary, no story points and no velocity. Each work unit has an exit gate, and each milestone has acceptance criteria written before the work starts.

Items are the smallest pieces an engineer can finish, show and close, usually two to five days. Each has an owner on a track, a completion date, dependencies, a size and the sections of the ground truth it cites. The load table shows items and days per person per work unit. The critical path shows the longest dependency chain.

Items that depend on work owned outside the team (a pilot team, an approval, a review) carry an "external input" note. That work is an external item: the plan does not schedule it, and it leaves a gap in the numbering.

## Planning rigor

A generated task list and a plan look alike on a board. What separates them is the reasoning, so the plan writes it down. These ten rules were worked out by hand with a real team. The ground-truth skill drafts by them and the checker's planning review reads the plan against them.

1. A milestone is the thinnest vertical slice that proves one user-visible capability end to end, named for what a user can do after it. The first proves the whole path with the least behavior. The last proves the project can be released and run.
2. A milestone holds items from every track the capability crosses, and the tracks meet at a named joint check before the demonstration. A milestone that stays inside one track says why.
3. The exit gate is one sentence the stakeholders can check live. The engineers whose tracks meet give the demonstration together, and the plan says what they show together.
4. Inside a milestone the shared contract comes first, so both tracks can start without waiting. The first week leaves nobody idle.
5. Each engineer's consecutive items stay in one part of the system, a theme. Related items for the same person sit in adjacent days to cut context switching.
6. Size in days divided by allocation gives calendar working days: four days at 60 percent is nearly seven working days. Nobody is planned past 100 percent of allocated capacity in a work unit, aim for about 80, and days off and breaks are real.
7. Slack sits before every checkpoint and demonstration. An item that completes on its checkpoint date has none.
8. The critical path is checked for who owns each item on it, because one absent owner there would move the end date. If it runs through one person, the plan says so and offers an alternative.
9. Work outside the plan, owned outside the team, keeps its ids as gaps in the numbering.
10. The plan records its rationale where anyone can argue with it: for each milestone, why these items form it and what the joint demonstration proves, and for each track, why its items are in this order. The plan owner reads the plan week by week, adversarially, before anything is scaffolded.

In `plan.yaml` the rationale is `rationale`, `joint_demonstration` and, when needed, `single_track_reason` on each milestone, `order_rationale` on each track and `theme` on each item. The scaffold copies it into each `milestone.md` and into the "How this plan was composed" section of the specification README. The checker fails a plan that leaves a reason out, and `check_specs.py --report` ends with the planning review for the plan owner to read.

## Step 1 in more detail: the specifications

Every specification has the same sections, in the same order: why the item exists, outcome, context for the agent, contract or protocol, implementation guide, acceptance criteria, evidence of completion, integration points, out of scope, watch out for, references, decisions recorded. Contract excerpts are copied word for word. When the writer finds a contradiction in the ground truth, the specification records which side wins, and the contradiction goes onto the list for the next version of the document.

The checker validates header rows against `plan.yaml`, section order, length, banned vocabulary, the ids of external items, broken links, and the section numbers cited.

## What limits it

- Any number of tracks. Each engineer is on one track. Checkpoints join them.
- Milestones and items. The checker and the scripts set no limit on how many there are. The method has been run on one project of five milestones and thirty-seven items. Sub-epics group them. Specifications are written in parallel, one subagent per batch of two or three items. A subagent is a separate agent session that writes its batch from the same ground truth and the same template.
- Work outside the plan. Work owned outside the team stays outside the plan as numbering gaps and "external input" notes.
- One skill in every editor. The same conventions and the same definition of done reach each engineer, in the agent they already use.

## Where it strains

- The ground truth must exist and be worth trusting. If it is thin, the plan is thin.
- The first day is review-heavy for the plan owner. The agent drafts quickly and a person must read what it drafted.
- Demonstrations need the stakeholders to show up.
- The checker needs care when your conventions change.
- The agent drafts, people decide, and the plan owner has to keep deciding.

## The result

Everything traces back. Every issue names the sections of the ground truth it was built from. Contracts freeze on a date. Every specification has an out-of-scope section, so the engineer and their agent know what not to build. The plan is files in Git, so it can be regenerated. The board is built for you. The stakeholders can read the board and the acceptance criteria and know where things stand.
