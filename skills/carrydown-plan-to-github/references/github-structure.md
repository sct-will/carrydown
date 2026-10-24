# What gets created

Everything comes from `plan.yaml` and the specification folder. The sync script prints each item before it writes it.

## Labels

- The project slug, for example `expense-approvals`, on every issue.
- One label per track, for example `workflow` and `experience`, with the colour from `plan.yaml`.
- `sub-epic` on milestone issues.

Existing labels with the same name are kept.

## Sub-epics

One issue per milestone. The title is `<subepic_prefix> <number>, <name>`, for example `Milestone 2, Route to approvers`. The body is built from `milestone.md`:

1. The purpose, which is the value proposition.
2. The exit gate and the due and demonstration dates, then one line: "Target delivery for the plan: <date> (given or derived)".
3. Expected outcomes.
4. Acceptance criteria as checkboxes, written before the work starts.
5. Demonstration expectations.
6. The work item list as task-list lines that link to the issues, for example `- [ ] #14 WI-03 Approval routing engine, by 2027-02-24`.
7. A link to the milestone file.

If an Epic exists, each sub-epic is linked under it as a sub-issue.

## Work item issues

The title follows `project.title_format`, by default `{id} {label}`. The body has seven headings, in this order.

1. Work item. Target date, checkpoint, and the first paragraph of "Why this work item exists".
2. AI engineering notes. The link to the specification file, the line that names the developer skill and how to invoke it, and the ground truth sections cited.
3. Depends on. The dependency ids with their labels, then any program input. After creation each id gets an issue link, for example `WI-01 (#12)`.
4. Acceptance criteria. Copied from the specification.
5. Evidence of completion. Copied from the specification.
6. Integration points. Copied from the specification.
7. Definition of done. Built from the conventions in `plan.yaml` (test command, lint command, flag, extra lines).

Each issue is a sub-issue of its sub-epic and carries the project label and the track label. If the owner has a GitHub login in `plan.yaml`, the issue is assigned.

## The Epic comment

If an Epic exists, the script posts one comment. It opens with a Constraints block: "Target delivery: <date> (given)" or "(derived from the critical path)", then one line per track such as "Track Workflow: 1 person, 100 percent allocated" (placeholder people are marked, and a plan with no people says "People: to be assigned (derived capacity: N)"). The dry run prints the same block before anything is written. Below it come nested checkboxes: each sub-epic, and under it each work item with owner and date. A box is checked when its issue closes. The comment has a hidden marker, so reruns update it instead of adding a second one.

## Idempotence and updates

- Issues are matched by exact title. A rerun finds what exists and creates only what is missing.
- Existing issue bodies are left alone. Pass `--update-bodies` to rewrite them from the specs. This overwrites hand edits on GitHub.
- Dependency links and the sub-epic lists are filled in after creation, once the issue numbers are known, for issues created in the same run.
- Renaming an item changes its title, so the next run would create a new issue. Rename on GitHub first, or leave the title alone.

## Closing the loop

The specification README has two comment templates. A closing comment on each issue: Demo, Evidence, Decisions, Handoff. A checkpoint comment on the Epic after each weekly check. The outcome of a demonstration goes on the sub-epic.
