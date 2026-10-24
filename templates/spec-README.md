# Work item specifications for {{project_name}}

One file per development work item, plus `milestone.md` per milestone folder. The GitHub issue for a work item links to its file here, and the milestone sub-epic links to `milestone.md`. Each file gives the engineer, and the coding agent in their editor, the context needed to complete the item without opening the original ground truth documents. Where a file excerpts a contract, the excerpt is normative for the item. Where it conflicts with the ground truth, the ground truth wins and the file is corrected in the same pull request.

## What is in this folder

| Path | What it is |
| --- | --- |
| `README.md` | This page. Conventions, how the plan was composed, schedule, checkpoint and comment templates, the index of work items. |
| `plan.yaml` | The schedule as data: milestones, work items, owners, dates, dependencies, checkpoints. The checker and the GitHub scripts read it. |
| `m1-.../` and the other milestone folders | The work item files, one per item, and `milestone.md` for each milestone. |

The rendered ground truth lives at `{{ground_truth}}`. The engineers' skill that loads these conventions into a coding agent lives at `{{dev_skill_path}}`. Its README has the install steps.

## How to use a specification

The shortest route is the engineers' skill. It makes a coding agent read the right specification, the ground truth sections it cites and these conventions before it changes code. You do not paste that context by hand.

1. Read the whole file, then the code it points to. Open the ground truth only for the sections the file cites.
2. Propose the change in a short plan in the pull request description before writing code. Name the files you will touch.
3. Work in small pull requests on `{{branch}}`.
4. Prove each acceptance criterion with a test or a recorded check. The pull request lists them.
5. If the implementation departs from the file, append a short entry under "Decisions recorded" at the end of the file with the pull request number, in the same pull request.

## Source documents

{{source_table}}

## Project conventions

{{conventions}}

Words used in every file. A work unit is a time box of variable length with an exit gate. A checkpoint is a dated integration check between the tracks. Its joint check is the one-sentence test the tracks run together there to prove the parts they built fit. A demonstration is the milestone roll-up that the engineers give to the stakeholders. An external input is something an item needs from an external item, work outside the plan that is owned outside the team.

The Ground truth row in a work item's header lists the sections the item is built from. The body may cite other sections for context.

## How this plan was composed

{{composition}}

## Schedule

Work is organized in work units of variable length, each with an exit gate. Work items carry a completion date and name the checkpoint and the demonstration they feed.

{{schedule_table}}

### Demonstrations and checkpoints

Progress is shown as a roll-up, not reported item by item. Two mechanisms carry it.

Milestones are sub-epics. Each milestone is a GitHub sub-epic, and its work item issues are sub-issues of that sub-epic. `milestone.md` in the milestone folder is the sub-epic content: the exit gate, the acceptance criteria and the demonstration expectations, written before the work starts.

{{milestone_table}}

Checkpoints. A 30-minute integration check every week with all tracks present. The current end-to-end flow is run and the joint check for the date is executed between the tracks. Checkpoints are not demonstrations.

{{checkpoint_table}}

### Closing comment on an issue

The coding agent assembles the evidence named in the work item file. The engineer checks it and posts it as the closing comment, in this shape.

```
{{closing_comment}}
```

### Checkpoint comment on the Epic

Posted after each checkpoint by one of the engineers, taking turns. The outcome of a milestone demonstration is noted as a comment on its sub-epic.

```
{{checkpoint_comment}}
```

{{external_section}}## Index

Each milestone folder also holds `milestone.md`, the sub-epic content for that milestone (exit gate, acceptance criteria, demonstration expectations, work item list).

{{index}}
