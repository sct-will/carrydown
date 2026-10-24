# Milestone 1, Submit an expense report

Sub-epic of the Expense approvals Epic. Work unit 1, 2027-02-01 to 2027-02-12 (`m1-submit-report`).

| Field | Value |
| --- | --- |
| Due | 2027-02-12 |
| Exit gate | A staff member creates a report with a receipt in the web client and submits it through the service. |
| Work items | WI-01, WI-02 |
| Demonstration | 2027-02-12, both people, in a meeting session with the stakeholders. |

## Purpose

This is the first time a staff member can start an expense report in the web client and have the service accept it.
Before this milestone the client and the service were designed against the same contract but had never met.
The demonstration proves that the contract frozen at the first checkpoint holds from the form to the stored report.
It feeds the start of work unit 2. The routing engine takes real submitted reports as its input from here on.

## Why these items form this milestone

<!-- Written from plan.yaml. Change it there, then run scaffold_spec.py --refresh-headers --apply. -->

The service scaffold with the API contract and the report form are the thinnest slice that proves the whole path: a report goes from the web client through the API to the database. The contract comes first so the form starts from a frozen shape at the Contract freeze checkpoint. Routing, rules and export stay out, so the path is proven with the least behaviour.

- Workflow: WI-01 (expense service).
- Experience: WI-02 (web client).

## Expected outcomes

- The service runs behind the feature flag, answers its health check with the flag off and refuses every other path.
- The API contract describes every endpoint and error code of the architecture document, and a contract test checks the service against it.
- A submitter creates a draft with line items, attaches receipts and submits it in the web client.
- A submitted report is stored in the Submitted state. The exit gate holds.

## Acceptance criteria

The milestone is accepted when the stakeholders have seen each of these at the demonstration.

- [ ] The web client created a draft, added two line items in different currencies and attached one receipt that covers both lines.
- [ ] The same report was submitted and the service answered 202 with the state Submitted.
- [ ] With the flag off, every path except the health check answered 404.
- [ ] A response from the service validated against `contracts/openapi.yaml` during the demonstration.
- [ ] The receipt larger than 10 MB and the file of a wrong type were both refused with E_VALIDATION.

## Joint demonstration

<!-- Written from plan.yaml. Change it there, then run scaffold_spec.py --refresh-headers --apply. -->

The Experience engineer creates a report with one receipt in the web client and submits it. The Workflow engineer shows the Submitted state and the stored receipt in the database from the same run.

Given together on 2027-02-12 by the engineers of the Workflow and Experience tracks.
The joint check for that date, Milestone 1 demonstration: A report with one receipt goes from the form to the Submitted state, with the audit-ready state change visible in the database. Experience drives the form and Workflow shows the database.

## Demonstration expectations

- Given on 2027-02-12 by the people who own the items, to the stakeholders, in one meeting session, showing the work items of this milestone working together.
- Nothing about the session is automated. The people decide what to show. The acceptance criteria above say what must be seen.
- The outcome, pass or fail against the acceptance criteria, is noted as a comment on this sub-epic the same day.

## Work items

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| WI-01 | [Service scaffold, flag and API contract](wi-01-service-scaffold.md) | Workflow | 2027-02-03 |
| WI-02 | [Report form and receipt upload](wi-02-report-form.md) | Experience | 2027-02-10 |

## References

- `wi-01-service-scaffold.md`
- `wi-02-report-form.md`
- The ground truth, `docs/ground-truth/architecture.md`
- The schedule and checkpoint tables in `../README.md`

## Decisions recorded

None yet.
