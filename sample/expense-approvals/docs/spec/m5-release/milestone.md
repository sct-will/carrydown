# Milestone 5, Release

Sub-epic of the Expense approvals Epic. Work unit 5, 2027-04-12 to 2027-04-23 (`m5-release`).

| | |
| --- | --- |
| Due | 2027-04-23 |
| Exit gate | The flag is on in production, the runbook is handed to operations and finance has signed off. |
| Work items | WI-11 |
| Demonstration | 2027-04-23, both people, in a meeting session with the program. |

## Purpose

This milestone ends the plan. It turns a working service into one that operations can run and finance has signed off.
The last item is the runbook and the release rehearsal. It needs the program's finance sign-off, which is tracked outside the plan.
The demonstration proves the service can be switched on in production, run, and switched off again.
After it, the service is in the hands of operations.

## Expected outcomes

- The runbook covers start, stop, the flag, the nightly job, re-route requests and restore from backup.
- The release rehearsal passes in staging with the flag on.
- The load check meets the response time target at 200 requests per second.
- The web client passes the accessibility check against WCAG 2.2 level AA.

## Acceptance criteria

The milestone is accepted when the program has seen each of these at the demonstration.

- [ ] The release rehearsal ran from the runbook alone and passed.
- [ ] The 95th percentile response time was under 400 ms at 200 requests per second.
- [ ] The accessibility check of the report form and the inbox reported no failures at level AA.
- [ ] Switching the flag off returned the service to health check only, and switching it on restored it.
- [ ] The program recorded finance sign-off before the demonstration.

## Demonstration expectations

- Given on 2027-04-23 by the people who own the items, to the program, in one meeting session, showing the work items of this milestone working together.
- Nothing about the session is automated. The people decide what to show. The acceptance criteria above say what must be seen.
- The outcome, pass or fail against the acceptance criteria, is noted as a comment on this sub-epic the same day.

## Work items

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| WI-11 | [Release readiness and runbook](wi-11-release-readiness.md) | Experience | 2027-04-21 |

## References

- `wi-11-release-readiness.md`
- The ground truth, `docs/ground-truth/architecture.md`
- The schedule and checkpoint tables in `../README.md`

## Decisions recorded

None yet.
