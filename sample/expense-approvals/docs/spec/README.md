# Work item specifications for Expense approvals

One file per development work item, plus `milestone.md` per milestone folder. The GitHub issue for a work item links to its file here, and the milestone sub-epic links to `milestone.md`. Each file gives the engineer, and the coding agent in their editor, the context needed to complete the item without opening the original ground truth documents. Where a file excerpts a contract, the excerpt is normative for the item. Where it conflicts with the ground truth, the ground truth wins and the file is corrected in the same pull request.

## What is in this folder

| Path | What it is |
| --- | --- |
| `README.md` | This page. Conventions, how the plan was composed, schedule, checkpoint and comment templates, the index of work items. |
| `plan.yaml` | The schedule as data: milestones, work items, owners, dates, dependencies, checkpoints. The checker and the GitHub scripts read it. |
| `m1-.../` and the other milestone folders | The work item files, one per item, and `milestone.md` for each milestone. |

The rendered ground truth lives at `docs/ground-truth/architecture.md`. The developer skill that loads these conventions into a coding agent lives at `docs/dev/skills/expense-approvals-dev`. Its README has the install steps.

## How to use a specification

The shortest route is the developer skill. It makes a coding agent read the right specification, the ground truth sections it cites and these conventions before it changes code. You do not paste that context by hand.

1. Read the whole file, then the code it points to. Open the ground truth only for the sections the file cites.
2. Propose the change in a short plan in the pull request description before writing code. Name the files you will touch.
3. Work in small pull requests on `main`.
4. Prove each acceptance criterion with a test or a recorded check. The pull request lists them.
5. If the implementation departs from the file, append a short entry under "Decisions recorded" at the end of the file with the pull request number, in the same pull request.

## Source documents

| Document | Path | Use |
| --- | --- | --- |
| Architecture document, version 0.3 | `ground-truth/architecture.md (source), docs/ground-truth/architecture.md (rendering)` | Full specification. Section numbers in the work item files refer to it. |

## Project conventions

- Feature flag. `EXPENSE_APPROVALS_ENABLED` gates the new behaviour. Off by default until the release. With the flag off, nothing existing changes.
- Tests. Run `npm test`. New suites accompany each work item.
- Lint and format. `npm run lint` passes on every pull request.
- Contract tests pass with `npm run test:contract`, and a change to `contracts/openapi.yaml` is its own pull request.
- Secrets and personal data never appear in code, tests, logs or fixtures.
- Documentation style in this folder. Sentence-case headings, short sentences, no em dashes or en dashes, no names of people. Owners and dates live in the GitHub issues.
- Existing behaviour is not changed by a work item unless its file says so.

Words used in every file. A work unit is a time box of variable length with an exit gate. A checkpoint is a short weekly integration check between the tracks. A demonstration is the milestone roll-up that the engineers give to the program. A program input is something the program provides outside this plan.

## How this plan was composed

<!-- Written from plan.yaml. Change it there, then run scaffold_spec.py --refresh-headers --apply. -->

The plan follows ten rules. The reasons below are written in `plan.yaml`, so a reviewer can argue with each one against the dates in the schedule.

1. A milestone is the thinnest vertical slice that proves one user-visible capability end to end, named for what a user can do after it. The first proves the whole path with the least behaviour, and the last proves the project can be released and run.
2. A milestone holds items from every track the capability crosses, and the tracks meet at a named joint check before the demonstration. A milestone that stays inside one track says why.
3. The exit gate is one sentence the program can check live. The engineers whose tracks meet give the demonstration together, and the plan says what they show.
4. Inside a milestone the shared contract comes first, so both tracks can start without waiting. The first week leaves nobody idle.
5. Each engineer's consecutive items stay in one part of the system, a theme. Related items for the same person sit in adjacent days to cut context switching.
6. Size in days divided by allocation gives calendar working days: four days at 60 percent is nearly seven working days. Nobody is planned past 100 percent of allocated capacity in a work unit, aim for about 80, and days off and breaks are real.
7. Slack sits before every checkpoint and demonstration. An item that completes on its checkpoint date has none.
8. The critical path is read for single points of failure. If it runs through one person, the plan says so and offers an alternative.
9. Program-owned work stays outside the plan as id gaps.
10. The plan records its rationale where a reviewer can argue with it: for each milestone, why these items form it and what the joint demonstration proves, and for each track, why its items are in this order. The plan owner reads the plan week by week, adversarially, before anything is scaffolded.

### Order of work per track

| Track | Items in date order | Why this order |
| --- | --- | --- |
| Workflow | WI-01, WI-03, WI-06, WI-07, WI-09 | The scaffold and the API contract come first because both tracks build against contracts/openapi.yaml (DS-1.4). Routing closes on 2027-02-19, before the day off on 2027-02-22, so the inbox can start the next Monday. The limits close on 2027-03-08 so the delegates item has the GOV-1 rules from the start of work unit 3, and the audit log follows in the same service code because it shares the transaction of each state change (D1). The one theme change, to the export job, falls across the offsite week. |
| Experience | WI-02, WI-04, WI-08, WI-11 | In the first three days the Experience engineer reviews the draft contract with the Workflow engineer, so nobody is idle in the first week. The report form starts the day after the contract lands and closes on 2027-02-10, two days before the first demonstration. The inbox needs the form and the routing steps, and closes on 2027-03-03. Notifications and delegates need the inbox decisions and the GOV-1.4 delegate rule, so they come third, and release readiness comes last because it rehearses everything. The theme changes twice, to the notification worker and then to the release, each at a milestone boundary and never between adjacent days. Four of the five items on the critical path sit on this track at 60 percent allocation: if this engineer is away, the Workflow engineer takes the delegate screen of WI-08, whose rules are already theirs. |

### Milestones

| Milestone | Tracks | Why these items | Joint demonstration |
| --- | --- | --- | --- |
| 1, Submit an expense report | Workflow and Experience | The service scaffold with the API contract and the report form are the thinnest slice that proves the whole path: a report goes from the web client through the API to the database. The contract comes first so the form starts from a frozen shape at the Contract freeze checkpoint. Routing, rules and export stay out, so the path is proven with the least behaviour. | The Experience engineer creates a report with one receipt in the web client and submits it. The Workflow engineer shows the Submitted state and the stored receipt in the database from the same run. |
| 2, Route to approvers | Workflow and Experience | Routing and the inbox are the two halves of one capability: a submitted report reaches its approvers and they decide it. Neither can be shown alone, because the steps mean nothing without an inbox and the inbox is empty without steps. The Routing meets inbox checkpoint on 2027-02-26 joins them a week before the demonstration. | The Workflow engineer submits reports in each band of section 3.5 and shows the steps built for them. The Experience engineer approves one report as two approvers in turn from the inbox, and it reaches Approved only after the last step. |
| 3, Enforce policy | Workflow and Experience | Policy can be seen only when a decision is refused, recorded and told to the submitter, so the rules, the audit log and the notifications form one milestone. The rules come first because the delegates and the error display depend on GOV-1. The audit log shares the transaction of each state change (D1, GOV-2.1), so it stays with the rules in the service. | The Experience engineer makes a decision that GOV-1 refuses and shows the rule number in the web client. The Workflow engineer shows the audit event of an allowed decision, and the submitter's email from the same run is opened. |
| 4, Pilot with one team | Workflow only | The pilot proves the capability finance asked for: approved reports reach the ledger with no manual change (BA-3). The export job is the only new build, and the pilot team's real reports are the test of everything shown so far. Why one track: The pilot adds no screen and no notification. The Experience work it needs is support for the pilot team on the existing web client, which is not a deliverable item. | The Experience engineer walks one pilot report from submit to Approved in the web client. The Workflow engineer runs the nightly job on it and opens the file in the finance tool with no manual change. |
| 5, Release | Experience only | Release proves the project can be released and run: the rehearsal with the flag on, the runbook handed to operations and the finance sign-off. It holds one item because everything it rehearses was built and shown in milestones 1 to 4. Why one track: Release readiness is one item of rehearsal and runbook work. It sits on the Experience track because the rehearsal runs through the web client. The Workflow engineer takes part in the rehearsal and owns no new item. | The Experience engineer shows the rehearsal record, then submits and approves a report in staging with the flag on. The Workflow engineer shows the nightly file, its checksum and the audit events from the same run, then switches the flag off. |

## Schedule

Work is organised in work units of variable length, each with an exit gate. Work items carry a completion date and name the checkpoint and the demonstration they feed.

| Work unit | Dates | Gate |
| --- | --- | --- |
| 1, Submit an expense report | 2027-02-01 to 2027-02-12 | A staff member creates a report with a receipt in the web client and submits it through the service. |
| 2, Route to approvers | 2027-02-15 to 2027-03-05 | A submitted report reaches the right approvers in order and an approver decides it from the inbox. |
| 3, Enforce policy | 2027-03-08 to 2027-03-19 | Every decision obeys the approval limits and separation of duties, every change is in the audit trail, and submitters are notified. |
| Offsite and planning week | 2027-03-22 to 2027-03-26 | None committed. |
| 4, Pilot with one team | 2027-03-29 to 2027-04-09 | A pilot team's approved reports reach the ledger by the nightly file. |
| 5, Release | 2027-04-12 to 2027-04-23 | The flag is on in production, the runbook is handed to operations and finance has signed off. |

### Demonstrations and checkpoints

Progress is shown as a roll-up, not reported item by item. Two mechanisms carry it.

Milestones are sub-epics. Each milestone is a GitHub sub-epic, and its work item issues are sub-issues of that sub-epic. `milestone.md` in the milestone folder is the sub-epic content: the exit gate, the acceptance criteria and the demonstration expectations, written before the work starts.

| Sub-epic | Folder | Work unit | Due | Demonstration | Expected outcome |
| --- | --- | --- | --- | --- | --- |
| [Milestone 1, Submit an expense report](m1-submit-report/milestone.md) | `m1-submit-report` | 2027-02-01 to 2027-02-12 | 2027-02-12 | 2027-02-12 | A staff member creates a report with a receipt in the web client and submits it through the service. |
| [Milestone 2, Route to approvers](m2-route-to-approvers/milestone.md) | `m2-route-to-approvers` | 2027-02-15 to 2027-03-05 | 2027-03-05 | 2027-03-05 | A submitted report reaches the right approvers in order and an approver decides it from the inbox. |
| [Milestone 3, Enforce policy](m3-enforce-policy/milestone.md) | `m3-enforce-policy` | 2027-03-08 to 2027-03-19 | 2027-03-19 | 2027-03-19 | Every decision obeys the approval limits and separation of duties, every change is in the audit trail, and submitters are notified. |
| [Milestone 4, Pilot with one team](m4-pilot/milestone.md) | `m4-pilot` | 2027-03-29 to 2027-04-09 | 2027-04-09 | 2027-04-09 | A pilot team's approved reports reach the ledger by the nightly file. |
| [Milestone 5, Release](m5-release/milestone.md) | `m5-release` | 2027-04-12 to 2027-04-23 | 2027-04-23 | 2027-04-23 | The flag is on in production, the runbook is handed to operations and finance has signed off. |

Checkpoints. A 30-minute integration check every week with all tracks present. The current end-to-end flow is run and the joint check for the date is executed between the tracks. Checkpoints are not demonstrations.

| Date | Checkpoint | Items due | Joint check |
| --- | --- | --- | --- |
| 2027-02-05 | Contract freeze | WI-01 | The web client creates a draft against the service stub and the response validates against contracts/openapi.yaml. |
| 2027-02-12 | Milestone 1 demonstration | WI-02 | A report with one receipt goes from the form to the Submitted state, with the audit-ready state change visible in the database. Experience drives the form and Workflow shows the database. |
| 2027-02-26 | Routing meets inbox | WI-03 | A submitted report produces the approval steps of section 3.5, and the inbox contract returns them for the first approver. |
| 2027-03-05 | Milestone 2 demonstration | WI-04 | A report is approved by two approvers in order from the inbox in the web client. Workflow starts a report with two steps and Experience approves it at both. |
| 2027-03-12 | Rules meet routing | WI-06 | A refused decision shows the rule number in the web client error message, and the report state does not change. |
| 2027-03-19 | Milestone 3 demonstration | WI-07, WI-08 | A decision produces an audit event and a notification, and the submitter sees the new state. Workflow shows the audit event and Experience shows the notification and the submitter's view. |
| 2027-04-09 | Pilot readout | WI-09 | The nightly file for the pilot team's reports opens in the finance tool with no manual change. Workflow produces the file, and Workflow and Experience open it together and verify the checksum. |
| 2027-04-23 | Release | WI-11 | The release rehearsal passes with the flag on in the staging environment. Experience runs it through the web client and Workflow shows the file, the checksum and the audit events. |

### Closing comment on an issue

The coding agent assembles the evidence named in the work item file. The engineer checks it and posts it as the closing comment, in this shape.

```
## Done: EXP-NN <label>

**Demo.** What can be shown now that could not be before, and how to see it in under two minutes.
**Evidence.** Pull requests. Test suites by file with the run line. Artifacts attached: outputs, header dumps, record tables, screenshots or a short recording, as the work item file lists them.
**Decisions.** Departures recorded in the work item file, or "none".
**Handoff.** What the counterpart items on the other track need to know, or "none".
```

### Checkpoint comment on the Epic

Posted after each checkpoint by one of the engineers, taking turns. The outcome of a milestone demonstration is noted as a comment on its sub-epic.

```
## Checkpoint <date>, <name>

**Shown.** The end-to-end flow run so far and what it did.
**Closed since the last checkpoint.** Issue links, each with its evidence posted.
**Joint check.** The check from the schedule table, pass or fail, with what was seen.
**Blocked or at risk.** Items, cause, owner, or "none".
```

## Program-owned items

Some items depend on inputs the program provides outside this plan, such as pilot teams, approvals and reviews. Those are marked "program input" in the item files. Their ids are left as gaps in the numbering on purpose. They are tracked by the program, not as issues in this plan.

| Id | Program item | Note |
| --- | --- | --- |
| WI-05 | Pilot team recruitment | The program names the pilot team and confirms their cost centres before work unit 4. |
| WI-10 | Finance sign-off | Finance operations approves the export format and the retention period before the release. |

## Index

Each milestone folder also holds `milestone.md`, the sub-epic content for that milestone (exit gate, acceptance criteria, demonstration expectations, work item list).

Milestone 1, Submit an expense report (`m1-submit-report`), work unit 1

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-01-service-scaffold](m1-submit-report/wi-01-service-scaffold.md) | Service scaffold, flag and API contract | Workflow | 2027-02-03 |
| [wi-02-report-form](m1-submit-report/wi-02-report-form.md) | Report form and receipt upload | Experience | 2027-02-10 |

Milestone 2, Route to approvers (`m2-route-to-approvers`), work unit 2

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-03-routing-engine](m2-route-to-approvers/wi-03-routing-engine.md) | Approval routing engine | Workflow | 2027-02-19 |
| [wi-04-approver-inbox](m2-route-to-approvers/wi-04-approver-inbox.md) | Approver inbox and decisions | Experience | 2027-03-03 |

Milestone 3, Enforce policy (`m3-enforce-policy`), work unit 3

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-06-limits-and-duties](m3-enforce-policy/wi-06-limits-and-duties.md) | Approval limits and separation of duties | Workflow | 2027-03-08 |
| [wi-07-audit-log](m3-enforce-policy/wi-07-audit-log.md) | Audit log and retention | Workflow | 2027-03-17 |
| [wi-08-notifications-delegates](m3-enforce-policy/wi-08-notifications-delegates.md) | Notifications and delegates | Experience | 2027-03-17 |

Milestone 4, Pilot with one team (`m4-pilot`), work unit 4

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-09-ledger-export](m4-pilot/wi-09-ledger-export.md) | Ledger export job | Workflow | 2027-04-06 |

Milestone 5, Release (`m5-release`), work unit 5

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-11-release-readiness](m5-release/wi-11-release-readiness.md) | Release readiness and runbook | Experience | 2027-04-21 |
