# Work item index

Generated from `plan.yaml`. The GitHub issues hold the owners, status and dates of record.

## Work units and milestones

| Work unit | Dates | Gate |
| --- | --- | --- |
| 1, Submit an expense report | 2027-02-01 to 2027-02-12 | A staff member creates a report with a receipt in the web client and submits it through the service. |
| 2, Route to approvers | 2027-02-15 to 2027-03-05 | A submitted report reaches the right approvers in order and an approver decides it from the inbox. |
| 3, Enforce policy | 2027-03-08 to 2027-03-19 | Every decision obeys the approval limits and separation of duties, every change is in the audit trail, and submitters are notified. |
| Offsite and planning week | 2027-03-22 to 2027-03-26 | None committed. |
| 4, Pilot with one team | 2027-03-29 to 2027-04-09 | A pilot team's approved reports reach the ledger by the nightly file. |
| 5, Release | 2027-04-12 to 2027-04-23 | The flag is on in production, the runbook is handed to operations and finance has signed off. |

Target. 2027-04-23. The plan was fitted to it.

Allocation. People are allocated as a percentage of their working time to this plan. By track, the allocation adds up to Workflow 100 percent, Experience 60 percent. The dates in this plan already account for it, so a track at less than 100 percent has fewer working days in each work unit.

## Milestone 1, Submit an expense report (`m1-submit-report`)

Exit gate. A staff member creates a report with a receipt in the web client and submits it through the service.

| Id | Work item | Track | Complete by | Depends on | File |
| --- | --- | --- | --- | --- | --- |
| WI-01 | Service scaffold, flag and API contract | Workflow | 2027-02-03 | None | `docs/spec/m1-submit-report/wi-01-service-scaffold.md` |
| WI-02 | Report form and receipt upload | Experience | 2027-02-10 | WI-01 | `docs/spec/m1-submit-report/wi-02-report-form.md` |

## Milestone 2, Route to approvers (`m2-route-to-approvers`)

Exit gate. A submitted report reaches the right approvers in order and an approver decides it from the inbox.

| Id | Work item | Track | Complete by | Depends on | File |
| --- | --- | --- | --- | --- | --- |
| WI-03 | Approval routing engine | Workflow | 2027-02-19 | WI-01 | `docs/spec/m2-route-to-approvers/wi-03-routing-engine.md` |
| WI-04 | Approver inbox and decisions | Experience | 2027-03-03 | WI-02, WI-03 | `docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md` |

## Milestone 3, Enforce policy (`m3-enforce-policy`)

Exit gate. Every decision obeys the approval limits and separation of duties, every change is in the audit trail, and submitters are notified.

| Id | Work item | Track | Complete by | Depends on | File |
| --- | --- | --- | --- | --- | --- |
| WI-06 | Approval limits and separation of duties | Workflow | 2027-03-08 | WI-03 | `docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md` |
| WI-07 | Audit log and retention | Workflow | 2027-03-17 | WI-03 | `docs/spec/m3-enforce-policy/wi-07-audit-log.md` |
| WI-08 | Notifications and delegates | Experience | 2027-03-17 | WI-04, WI-06 | `docs/spec/m3-enforce-policy/wi-08-notifications-delegates.md` |

## Milestone 4, Pilot with one team (`m4-pilot`)

Exit gate. A pilot team's approved reports reach the ledger by the nightly file.

| Id | Work item | Track | Complete by | Depends on | File |
| --- | --- | --- | --- | --- | --- |
| WI-09 | Ledger export job | Workflow | 2027-04-06 | WI-07; program input: the pilot team, named by the stakeholders | `docs/spec/m4-pilot/wi-09-ledger-export.md` |

## Milestone 5, Release (`m5-release`)

Exit gate. The flag is on in production, the runbook is handed to operations and finance has signed off.

| Id | Work item | Track | Complete by | Depends on | File |
| --- | --- | --- | --- | --- | --- |
| WI-11 | Release readiness and runbook | Experience | 2027-04-21 | WI-08, WI-09; program input: finance sign-off on the export format and retention period | `docs/spec/m5-release/wi-11-release-readiness.md` |

## Work the plan does not schedule

This work is owned outside the team, not by the engineers. It has no work item file. An item that needs its result says "program input" in its Depends on row. If the input is missing, say so in the pull request and do not invent it.

| Id | Outside item | Note |
| --- | --- | --- |
| WI-05 | Pilot team recruitment | The stakeholders name the pilot team and confirm their cost centres before work unit 4. |
| WI-10 | Finance sign-off | Finance operations approves the export format and the retention period before the release. |
