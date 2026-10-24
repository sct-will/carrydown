# Milestone 3, Enforce policy

Sub-epic of the Expense approvals Epic. Work unit 3, 2027-03-08 to 2027-03-19 (`m3-enforce-policy`).

| | |
| --- | --- |
| Due | 2027-03-19 |
| Exit gate | Every decision obeys the approval limits and separation of duties, every change is in the audit trail, and submitters are notified. |
| Work items | WI-06, WI-07, WI-08 |
| Demonstration | 2027-03-19, both people, in a meeting session with the program. |

## Purpose

This milestone makes the service safe to put in front of real money. It enforces the approval limits and separation of duties, writes the audit trail and tells submitters what happened.
Finance policy and internal audit each own a rule that this milestone implements. They are the audience that cares most.
The demonstration proves that a refused decision names its rule and changes nothing, and that every change leaves a trace.
It feeds the pilot in work unit 4.

## Expected outcomes

- Every decision passes the seven checks of GOV-1 on the server, and a refusal names the rule number.
- Every state change writes one audit event in the same transaction, and the audit table cannot be edited by the application.
- Submitters receive an email for each state change, and approvers can name a delegate for a date range.
- The retention job exists and respects legal holds.

## Acceptance criteria

The milestone is accepted when the program has seen each of these at the demonstration.

- [ ] An approver trying to decide their own report was refused with E_FORBIDDEN and the rule number GOV-1.1.
- [ ] A delegate acting outside the dates of the delegate record was refused.
- [ ] The audit trail of one report listed every state change in order, and reading it produced an audit.viewed event.
- [ ] An attempt to update or delete an audit row from the application account failed.
- [ ] The submitter received an email for the decision, and the email carried no amount and no comment text.

## Demonstration expectations

- Given on 2027-03-19 by the people who own the items, to the program, in one meeting session, showing the work items of this milestone working together.
- Nothing about the session is automated. The people decide what to show. The acceptance criteria above say what must be seen.
- The outcome, pass or fail against the acceptance criteria, is noted as a comment on this sub-epic the same day.

## Work items

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| WI-06 | [Approval limits and separation of duties](wi-06-limits-and-duties.md) | Workflow | 2027-03-12 |
| WI-07 | [Audit log and retention](wi-07-audit-log.md) | Workflow | 2027-03-17 |
| WI-08 | [Notifications and delegates](wi-08-notifications-delegates.md) | Experience | 2027-03-18 |

## References

- `wi-06-limits-and-duties.md`
- `wi-07-audit-log.md`
- `wi-08-notifications-delegates.md`
- The ground truth, `docs/ground-truth/architecture.md`
- The schedule and checkpoint tables in `../README.md`

## Decisions recorded

None yet.
