# Milestone 4, Pilot with one team

Sub-epic of the Expense approvals Epic. Work unit 4, 2027-03-29 to 2027-04-09 (`m4-pilot`).

| | |
| --- | --- |
| Due | 2027-04-09 |
| Exit gate | A pilot team's approved reports reach the ledger by the nightly file. |
| Work items | WI-09 |
| Demonstration | 2027-04-09, both people, in a meeting session with the program. |

## Purpose

This milestone puts the service in the hands of one real team. The nightly ledger file carries their approved reports to finance with no re-keying.
It is the first time outsiders use the product, so the demonstration is also the first reading of the measures that matter to the program.
It depends on a pilot team that the program names, and the plan holds a place for that input.
It feeds the release decision.

## Expected outcomes

- The nightly job writes the ledger file and its checksum for every report approved since the last run.
- Reports move to Exported after the file is written, and a failed run does not duplicate rows.
- The pilot team submits and approves real reports in the staging environment with the flag on.
- The pilot readout records time to decision and the count of reports that needed a re-route.

## Acceptance criteria

The milestone is accepted when the program has seen each of these at the demonstration.

- [ ] The file `expenses-YYYYMMDD.csv` for the pilot team opened in the finance tool with no manual change.
- [ ] The checksum file matched the content of the CSV file.
- [ ] A rerun after a forced failure produced no duplicate rows.
- [ ] Every exported report showed the Exported state and an audit event.
- [ ] The program received the readout of time to decision for the pilot reports.

## Demonstration expectations

- Given on 2027-04-09 by the people who own the items, to the program, in one meeting session, showing the work items of this milestone working together.
- Nothing about the session is automated. The people decide what to show. The acceptance criteria above say what must be seen.
- The outcome, pass or fail against the acceptance criteria, is noted as a comment on this sub-epic the same day.

## Work items

| Id | Work item | Track | Complete by |
| --- | --- | --- | --- |
| WI-09 | [Ledger export job](wi-09-ledger-export.md) | Workflow | 2027-04-06 |

## References

- `wi-09-ledger-export.md`
- The ground truth, `docs/ground-truth/architecture.md`
- The schedule and checkpoint tables in `../README.md`

## Decisions recorded

None yet.
