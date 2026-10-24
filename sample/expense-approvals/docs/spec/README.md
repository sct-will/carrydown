# Work item specifications for Expense approvals

One file per development work item, plus `milestone.md` per milestone folder. The GitHub issue for a work item links to its file here, and the milestone sub-epic links to `milestone.md`. Each file gives the engineer, and the coding agent in their editor, the context needed to complete the item without opening the original ground truth documents. Where a file excerpts a contract, the excerpt is normative for the item. Where it conflicts with the ground truth, the ground truth wins and the file is corrected in the same pull request.

## What is in this folder

| Path | What it is |
| --- | --- |
| `README.md` | This page. Conventions, schedule, checkpoint and comment templates, the index of work items. |
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
| 2027-02-12 | Milestone 1 demonstration | WI-02 | A report with one receipt goes from the form to the Submitted state, with the audit-ready state change visible in the database. |
| 2027-02-26 | Routing meets inbox | WI-03 | A submitted report produces the approval steps of section 3.5, and the inbox contract returns them for the first approver. |
| 2027-03-05 | Milestone 2 demonstration | WI-04 | A report is approved by two approvers in order from the inbox in the web client. |
| 2027-03-12 | Rules meet routing | WI-06 | A refused decision shows the rule number in the web client error message, and the report state does not change. |
| 2027-03-19 | Milestone 3 demonstration | WI-07, WI-08 | A decision produces an audit event and a notification, and the submitter sees the new state. |
| 2027-04-09 | Pilot readout | WI-09 | The nightly file for the pilot team's reports opens in the finance tool with no manual change. |
| 2027-04-23 | Release | WI-11 | The release rehearsal passes with the flag on in the staging environment. |

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
| [wi-02-report-form](m1-submit-report/wi-02-report-form.md) | Report form and receipt upload | Experience | 2027-02-12 |

Milestone 2, Route to approvers (`m2-route-to-approvers`), work unit 2

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-03-routing-engine](m2-route-to-approvers/wi-03-routing-engine.md) | Approval routing engine | Workflow | 2027-02-24 |
| [wi-04-approver-inbox](m2-route-to-approvers/wi-04-approver-inbox.md) | Approver inbox and decisions | Experience | 2027-03-05 |

Milestone 3, Enforce policy (`m3-enforce-policy`), work unit 3

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-06-limits-and-duties](m3-enforce-policy/wi-06-limits-and-duties.md) | Approval limits and separation of duties | Workflow | 2027-03-10 |
| [wi-07-audit-log](m3-enforce-policy/wi-07-audit-log.md) | Audit log and retention | Workflow | 2027-03-17 |
| [wi-08-notifications-delegates](m3-enforce-policy/wi-08-notifications-delegates.md) | Notifications and delegates | Experience | 2027-03-19 |

Milestone 4, Pilot with one team (`m4-pilot`), work unit 4

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-09-ledger-export](m4-pilot/wi-09-ledger-export.md) | Ledger export job | Workflow | 2027-04-06 |

Milestone 5, Release (`m5-release`), work unit 5

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| [wi-11-release-readiness](m5-release/wi-11-release-readiness.md) | Release readiness and runbook | Experience | 2027-04-21 |
