# Milestone 2, Route to approvers

Sub-epic of the Expense approvals Epic. Work unit 2, 2027-02-15 to 2027-03-05 (`m2-route-to-approvers`).

| Field | Value |
| --- | --- |
| Due | 2027-03-05 |
| Exit gate | A submitted report reaches the right approvers in order and an approver decides it from the inbox. |
| Work items | WI-03, WI-04 |
| Demonstration | 2027-03-05, both people, in a meeting session with the stakeholders. |

## Purpose

This milestone turns a submitted report into a decision. The service builds the approval steps and an approver works through them from an inbox.
It is the core of the product. Everything after it adds rules, trail and edges to a flow that already works.
The demonstration proves that routing and the inbox agree on the step order, and that a report can be approved by two people in turn.
It feeds work unit 3, where the rules and the audit trail attach to decisions that already exist.

## Why these items form this milestone

<!-- Written from plan.yaml. Change it there, then run scaffold_spec.py --refresh-headers --apply. -->

Routing and the inbox are the two halves of one capability: a submitted report reaches its approvers and they decide it. Neither can be shown alone, because the steps mean nothing without an inbox and the inbox is empty without steps. The Routing meets inbox checkpoint on 2027-02-26 joins them a week before the demonstration.

- Workflow: WI-03 (expense service).
- Experience: WI-04 (web client).

## Expected outcomes

- A submitted report receives approval steps by the table in section 3.5 of the architecture document.
- An approver sees waiting reports oldest first, with total and submitter visible.
- An approver approves, rejects or returns a report, and a comment is required for the last two.
- A report moves through the states of section 3.4 and refuses any other transition with E_STATE.

## Acceptance criteria

The milestone is accepted when the stakeholders have seen each of these at the demonstration.

- [ ] Three reports with totals of 400.00, 3,000.00 and 8,000.00 received one, two and three steps.
- [ ] The first approver saw only the reports waiting for them, oldest first.
- [ ] A report was approved by two approvers in order and moved to Approved only after the last step.
- [ ] A reject without a comment was refused, and a return with a comment reached the submitter as Returned.
- [ ] A report above 25,000.00 answered E_LIMIT and was not routed.

## Joint demonstration

<!-- Written from plan.yaml. Change it there, then run scaffold_spec.py --refresh-headers --apply. -->

The Workflow engineer submits reports in each band of section 3.5 and shows the steps built for them. The Experience engineer approves one report as two approvers in turn from the inbox, and it reaches Approved only after the last step.

Given together on 2027-03-05 by the engineers of the Workflow and Experience tracks.
The joint check for that date, Milestone 2 demonstration: A report is approved by two approvers in order from the inbox in the web client. Workflow starts a report with two steps and Experience approves it at both.

## Demonstration expectations

- Given on 2027-03-05 by the people who own the items, to the stakeholders, in one meeting session, showing the work items of this milestone working together.
- Nothing about the session is automated. The people decide what to show. The acceptance criteria above say what must be seen.
- The outcome, pass or fail against the acceptance criteria, is noted as a comment on this sub-epic the same day.

## Work items

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| WI-03 | [Approval routing engine](wi-03-routing-engine.md) | Workflow | 2027-02-19 |
| WI-04 | [Approver inbox and decisions](wi-04-approver-inbox.md) | Experience | 2027-03-03 |

## References

- `wi-03-routing-engine.md`
- `wi-04-approver-inbox.md`
- The ground truth, `docs/ground-truth/architecture.md`
- The schedule and checkpoint tables in `../README.md`

## Decisions recorded

None yet.
