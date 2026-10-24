# The method

Carrydown carries a ground truth document down into a governed plan. The plan has one specification per work item, a set of GitHub issues, a project board and a developer skill in every issue. This page explains the eight steps, which ones the carrydown skills do for you and which ones stay with the plan owner and the engineers. Two skills you install, one skill is generated for your engineers.

The idea is old in systems engineering, where it is called flow-down: a requirement at the top is traced to every part below it. The carrydown skills apply the same idea to software work done with coding agents. One document, one unbroken line through the plan, the specifications, the issues, the board and the agent.

## The eight steps

| Step | What happens | Who decides | What the carrydown skills give you |
| --- | --- | --- | --- |
| 1. Make the ground truth hold still | Write or collect the document or documents the project must obey. Check each claim about existing code and systems while you write. Run adversarial reviews. Record decisions and a changelog. | Plan owner | Interview prompts and review prompts in the ground-truth skill. |
| 2. Give it a machine-readable twin | Render the document to Markdown in the repository with stable section anchors. Every later artifact cites it by section number. | Automatic | `render_ground_truth.py` for Word and Markdown input. |
| 3. Draft the plan around real people | Milestones with exit gates, tracks, work items with owners, dates and dependencies, a load table, a critical path, work units of variable length. Review it adversarially. | Plan owner, with a draft from the agent | Planning guide, `plan.yaml` template, `check_specs.py --report`. |
| 4. One specification per work item | A fixed template. Contract excerpts copied from the ground truth. Written in parallel where the agent supports it, reviewed by the plan owner with the agent. A checker validates every file against the plan. | Agent drafts, plan owner reviews and approves | Template, scaffold script, checker, writer brief. |
| 5. A developer skill | A small skill generated from the specifications. An engineer names a work item id and the agent reads the specification, the cited sections and the conventions first. | Automatic, then reviewed by the plan owner | `generate_dev_skill.py`, the last step of `carrydown-plan-to-github`. |
| 6. GitHub structure | A sub-epic per milestone, an issue per work item as a sub-issue, dependency links, a roll-up comment on the parent Epic, labels. Each issue body is templated. | Automatic, after the plan owner's yes | `github_sync.py`. |
| 7. A project board | A GitHub Project (v2) with a work unit iteration field of custom length, track, dates, and three views. Every issue placed and every field filled. | Automatic, after the plan owner's yes | `github_project.py`. |
| 8. Progress is shown | Evidence posted on every closed issue. A weekly integration check between tracks with a named joint check. One demonstration per milestone against criteria written in advance. | Engineers show, the people accountable for the outcome decide | Comment templates, milestone files, checkpoint table. |

Planning decisions stay with the plan owner. The agent drafts, validates and populates. It does not decide who does what, when, or in which order.

## Step 1 in more detail

A ground truth is any mix of:

- an architecture document,
- requirements,
- business analyst notes,
- enterprise governance rules,
- development standards.

While you write it, verify claims about the existing world. Read the code. Run the test suite. Probe the live service. Measure. Anything you cannot prove, mark "verify at implementation" instead of asserting it. Then run adversarial passes: ask the agent, in a fresh context, to find what is missing, wrong or contradictory, and fold the findings back in with a changelog entry and, for architecture choices, a decision record.

The carrydown skills cannot write your document for you. It can help you review it.

## Step 3 in more detail

Work units are time boxes of variable length. A thin first slice may take a week and the core may take three. Pauses sit between them. There is no sprint vocabulary, no story points and no velocity. Each work unit has an exit gate, and each milestone has acceptance criteria written before the work starts.

Items are the smallest pieces an engineer can finish, show and close, usually two to five days. Each has an owner on a track, a completion date, dependencies, a size and the sections of the ground truth it cites. The load table shows items and days per person per work unit. The critical path shows the longest dependency chain.

Items that depend on work owned outside the team (a pilot team, an approval, a review) carry an "external input" note. That work is an external item: the plan does not schedule it, and it leaves a gap in the numbering.

## Planning rigor

A generated task list and a plan look alike on a board. What separates them is the reasoning, so the plan writes it down. These ten rules were worked out by hand with a real team. The ground-truth skill drafts by them and the checker's planning review reads the plan against them.

1. A milestone is the thinnest vertical slice that proves one user-visible capability end to end, named for what a user can do after it. The first proves the whole path with the least behaviour. The last proves the project can be released and run.
2. A milestone holds items from every track the capability crosses, and the tracks meet at a named joint check before the demonstration. A milestone that stays inside one track says why.
3. The exit gate is one sentence the people accountable for the outcome can check live. The engineers whose tracks meet give the demonstration together, and the plan says what they show together.
4. Inside a milestone the shared contract comes first, so both tracks can start without waiting. The first week leaves nobody idle.
5. Each engineer's consecutive items stay in one part of the system, a theme. Related items for the same person sit in adjacent days to cut context switching.
6. Size in days divided by allocation gives calendar working days: four days at 60 percent is nearly seven working days. Nobody is planned past 100 percent of allocated capacity in a work unit, aim for about 80, and days off and breaks are real.
7. Slack sits before every checkpoint and demonstration. An item that completes on its checkpoint date has none.
8. The critical path is read for single points of failure. If it runs through one person, the plan says so and offers an alternative.
9. Work outside the plan, owned outside the team, keeps its ids as gaps in the numbering.
10. The plan records its rationale where a reviewer can argue with it: for each milestone, why these items form it and what the joint demonstration proves, and for each track, why its items are in this order. The plan owner reads the plan week by week, adversarially, before anything is scaffolded.

In `plan.yaml` the rationale is `rationale`, `joint_demonstration` and, when needed, `single_track_reason` on each milestone, `order_rationale` on each track and `theme` on each item. The scaffold copies it into each `milestone.md` and into the "How this plan was composed" section of the specification README. The checker fails a plan that leaves a reason out, and `check_specs.py --report` ends with the planning review for the plan owner to read.

## Step 4 in more detail

Every specification has the same sections, in the same order: why the item exists, outcome, context for the agent, contract or protocol, implementation guide, acceptance criteria, evidence of completion, integration points, out of scope, watch out for, references, decisions recorded. Contract excerpts are copied word for word. When the writer finds a contradiction in the ground truth, the specification records which side wins, and the contradiction goes onto the list for the next version of the document.

The checker validates header rows against `plan.yaml`, section order, length, banned vocabulary, the ids of external items, broken links, and the section numbers cited.

## Step 8 in more detail

Three rhythms.

- Per work item. The engineer closes the issue with a comment: Demo, Evidence, Decisions, Handoff. The agent assembles the evidence from the commands in the specification.
- Weekly. A 30-minute checkpoint with all tracks. They run the current end-to-end flow and the joint check for the date. They post a short comment.
- Per milestone. A demonstration by the engineers who built the items, to the people accountable for the outcome. The acceptance criteria were written before the work started. The outcome is a comment on the sub-epic. Nothing about the session is automated.

## Why it scales

- Any number of tracks. Each engineer is on one track. Checkpoints join them.
- Any number of milestones and items. Sub-epics group them. Specifications are written in parallel by subagents, one batch per milestone, from the same ground truth and the same template.
- Work outside the plan. Work owned outside the team stays outside the plan as numbering gaps and "external input" notes.
- One skill in every editor. The same conventions and the same definition of done reach each engineer, in the agent they already use.

## Where it strains

- The ground truth must exist and be worth trusting. If it is thin, the plan is thin.
- The first day is review-heavy for the plan owner. The agent drafts quickly and a person must read what it drafted.
- Demonstrations need the people accountable for the outcome to show up.
- The checker needs care when your conventions change.
- The agent drafts, people decide, and the plan owner has to keep deciding.

## The result

Everything traces back. Every issue names the sentence in the ground truth it was built from. Contracts freeze on a date. Out-of-scope sections stop scope creep one reasonable pull request at a time. The plan is files in Git, so it can be regenerated. The board is built for you. The people accountable for the outcome can read the board and the acceptance criteria and know where things stand.
