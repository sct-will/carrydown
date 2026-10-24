# The method

Carrydown carries a ground truth document down into a governed plan. The plan has one specification per work item, a set of GitHub issues, a project board and a developer skill in every issue. This page explains the eight steps, which ones the carrydown skills do for you and which ones stay with people.

The idea is old in systems engineering, where it is called flow-down: a requirement at the top is traced to every part below it. The carrydown skills apply the same idea to software work done with coding agents. One document, one unbroken line through the plan, the specifications, the issues, the board and the agent.

## The eight steps

| Step | What happens | Who decides | What the carrydown skills give you |
| --- | --- | --- | --- |
| 1. Make the ground truth hold still | Write or collect the document or documents the project must obey. Check each claim about existing code and systems while you write. Run adversarial reviews. Record decisions and a changelog. | People | Interview prompts and review prompts in the ground-truth skill. |
| 2. Give it a machine-readable twin | Render the document to Markdown in the repository with stable section anchors. Every later artifact cites it by section number. | Automatic | `render_ground_truth.py` for Word and Markdown input. |
| 3. Draft the plan around real people | Milestones with exit gates, tracks, work items with owners, dates and dependencies, a load table, a critical path, work units of variable length. Review it adversarially. | People, with a draft from the agent | Planning guide, `plan.yaml` template, `check_specs.py --report`. |
| 4. One specification per work item | A fixed template. Contract excerpts copied from the ground truth. Written in parallel where the agent supports it, reviewed by a lead. A checker validates every file against the plan. | People review, agent drafts | Template, scaffold script, checker, writer brief. |
| 5. A developer skill | A small skill generated from the specifications. A developer names a work item id and the agent reads the specification, the cited sections and the conventions first. | Automatic, then reviewed | `carrydown-dev-skill`, `generate_dev_skill.py`. |
| 6. GitHub structure | A sub-epic per milestone, an issue per work item as a sub-issue, dependency links, a roll-up comment on the parent Epic, labels. Each issue body is templated. | Automatic, after a yes | `github_sync.py`. |
| 7. A project board | A GitHub Project (v2) with a work unit iteration field of custom length, track, dates, and three views. Every issue placed and every field filled. | Automatic, after a yes | `github_project.py`. |
| 8. Progress is shown | Evidence posted on every closed issue. A weekly integration check between tracks with a named joint check. One demonstration per milestone against criteria written in advance. | People | Comment templates, milestone files, checkpoint table. |

Planning decisions stay human. The agent drafts, validates and populates. It does not decide who does what, when, or in which order.

## Step 1 in more detail

A ground truth is any mix of:

- an architecture document,
- requirements,
- business analyst notes,
- enterprise governance rules,
- development standards.

While you write it, verify claims about the existing world. Read the code. Run the test suite. Probe the live service. Measure. Anything you cannot prove, mark "verify at implementation" instead of asserting it. Then run adversarial passes: ask a reviewer to find what is missing, wrong or contradictory, and fold the findings back in with a changelog entry and, for architecture choices, a decision record.

The carrydown skills cannot write your document for you. It can help you review it.

## Step 3 in more detail

Work units are time boxes of variable length. A thin first slice may take a week and the core may take three. Pauses sit between them. There is no sprint vocabulary, no story points and no velocity. Each work unit has an exit gate, and each milestone has acceptance criteria written before the work starts.

Items are the smallest pieces a person can finish, show and close, usually two to five days. Each has an owner on a track, a completion date, dependencies, a size and the sections of the ground truth it cites. The load table shows items and days per person per work unit. The critical path shows the longest dependency chain.

Items that depend on something the program provides (a pilot team, an approval, a review) carry a "program input" note. The program's own work is not in the plan. It leaves a gap in the numbering.

## Step 4 in more detail

Every specification has the same sections, in the same order: why the item exists, outcome, context for the agent, contract or protocol, implementation guide, acceptance criteria, evidence of completion, integration points, out of scope, watch out for, references, decisions recorded. Contract excerpts are copied word for word. When the writer finds a contradiction in the ground truth, the specification records which side wins, and the contradiction goes onto the list for the next version of the document.

The checker validates header rows against `plan.yaml`, section order, length, banned vocabulary, program ids, broken links, and the section numbers cited.

## Step 8 in more detail

Three rhythms.

- Per work item. The developer closes the issue with a comment: Demo, Evidence, Decisions, Handoff. The agent assembles the evidence from the commands in the specification.
- Weekly. A 30-minute checkpoint with all tracks. They run the current end-to-end flow and the joint check for the date. They post a short comment.
- Per milestone. A demonstration by the people who own the items, to the program. The acceptance criteria were written before the work started. The outcome is a comment on the sub-epic. Nothing about the session is automated.

## Why it scales

- Any number of tracks. Each person owns a track. Checkpoints join them.
- Any number of milestones and items. Sub-epics group them. Specifications are written in parallel by subagents, one batch per milestone, from the same ground truth and the same template.
- The program boundary. Program-owned work stays outside the plan as numbering gaps and "program input" notes.
- One skill in every editor. The same conventions and the same definition of done reach each person, in the agent they already use.

## Where it strains

- The ground truth must exist and be worth trusting. If it is thin, the plan is thin.
- The first day is review-heavy for the leader. The agent drafts quickly and a person must read what it drafted.
- Demonstrations need a program that shows up.
- The checker needs care when your conventions change.
- The agent drafts, people decide, and the leader has to keep deciding.

## The result

Everything traces back. Every issue names the sentence in the ground truth it was built from. Contracts freeze on a date. Out-of-scope sections stop scope creep one reasonable pull request at a time. The plan is files in Git, so it can be regenerated. The board is built for you. A product manager can read the board and the acceptance criteria and know where things stand.
