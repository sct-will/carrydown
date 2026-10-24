# WI-09 Ledger export job

| | |
| --- | --- |
| Milestone | Milestone 4, Pilot with one team (`m4-pilot`), work unit 4 |
| Track | Workflow |
| Target | Complete by 2027-04-06 (work unit 4, Pilot with one team, 2027-03-29 to 2027-04-09) |
| Checkpoint | 2027-04-09, Pilot readout |
| Demonstration | 2027-04-09, milestone 4 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Medium, about 4 days |
| Depends on | WI-07; program input: the pilot team, named by the program |
| Unblocks | WI-11 |
| Ground truth | Sections 3.6, 4.2, 7.3 |

## Why this work item exists

Finance staff re-key every line of every approved report into the ledger today (1.1). Goal G5 and the functional requirement FR-9 (1.2, 2.1) ask for a nightly file in the format of 7.3. The business analyst finding BA-3 (6.1) asks for one line per approved line item, with the cost centre, so nobody splits totals by hand. This item is separate because it is a scheduled job with its own file contract and its own failure behaviour (3.6), and because it moves reports to a final state with an audit event (3.4, 4.2). It waits on WI-07 so that the move to Exported is audited in the same transaction. Without it the gate of milestone 4, a pilot team's approved reports reach the ledger, cannot be shown, and WI-11 has no job to put in the runbook.

## Outcome

- `src/export/ledgerJob.js` runs at 02:00 UTC, UTC being Coordinated Universal Time, and writes `expenses-YYYYMMDD.csv` and `expenses-YYYYMMDD.sha256` to the ledger drop folder.
- The file holds one row per line item of every report in Approved, with exactly the ten columns of 7.3 (BA-3).
- Each exported report moves to Exported and gets one audit_event, in the same transaction (3.4, GOV-2.1).
- A run that fails and is repeated leaves one file for the night, with no duplicate rows and no lost rows.
- The file holds no personal data beyond its columns, and log lines hold no amounts (GOV-2.6).
- With the flag off the job does nothing.
- Tests in `tests/export-ledger-job.test.js` and `tests/contract/ledger-format.test.js`.

## Context for the agent

- The sample repository is new and empty. This item creates `src/export/ledgerJob.js` and its tests. It adds no endpoint, so `contracts/openapi.yaml` does not change.
- WI-01 creates the migrations for the six tables of 3.3 (report, line_item, receipt, approval_step, delegate, audit_event), `src/config/flags.js`, the contract test runner and the continuous integration workflow.
- WI-03 creates the state machine of 3.4. Verify at implementation that Approved to Exported, caused by the export job, is in it, and use it instead of updating state directly.
- WI-07 creates `src/audit/writer.js` and the migration that gives the application account insert and select rights only. The job writes its audit events through the writer and runs under that account.
- This item has a program input, the pilot team, named by the program. The program also confirms their cost centres before work unit 4. The pilot readout on 2027-04-09 uses that team's approved reports. Build and test with made-up reports and cost centres. Hard code no team and no cost centre. If the team is not named when the item is due on 2027-04-06, say so on the issue.
- The service runs as one container (3.6). The name of the setting for the drop folder is not in the ground truth. Choose it and document it for WI-11.
- Commands are `npm test`, `npm run test:contract` and `npm run lint`. The job sits behind `EXPENSE_APPROVALS_ENABLED`, off by default (DS-1, the delivery standard).

## Contract

Fields used by this item, quoted from 7.3, 3.4, 3.6 and 4.2. One file per night, named `expenses-YYYYMMDD.csv`, with a second file `expenses-YYYYMMDD.sha256` that holds the SHA-256 checksum of the first. One row per approved line item of every report that moved to Approved since the last export. After writing, the job moves those reports to Exported.

| Column | Meaning |
| --- | --- |
| report_id | UUID of the report |
| line_item_id | UUID of the line item |
| employee_id | Submitter |
| cost_centre | Cost centre of the submitter at approval time |
| spent_on | Date of the expense, YYYY-MM-DD |
| category | Category code |
| amount_cents | Amount in the line currency, integer |
| currency | ISO 4217 currency code |
| base_amount_cents | Amount in USD, integer |
| approved_at | UTC timestamp of the last approval |

| From | Event | To | Who may cause it |
| --- | --- | --- | --- |
| Approved | export | Exported | Export job |

- 3.4. "Rejected and Exported are final. Any other transition is refused with the error code E_STATE."
- 3.6. "The export job runs at 02:00 UTC and writes to the ledger drop folder." "With the flag off the service starts, answers its health check and refuses every other request with the status 404."
- 3.3. "Amounts are integers in minor units (cents)."
- GOV-2.1 (GOV-2 is the audit and retention rule). "Every state change of a report writes one audit_event in the same database transaction. If the audit write fails, the change fails."
- GOV-2.2. "The audit table is append only. The application account has insert and select rights on it and no update or delete right."
- GOV-2.3. "It holds identifiers, never names, receipt contents or email addresses."
- GOV-2.6. "Log lines carry report identifiers and event types. They never carry amounts, comments or receipt contents."

## Implementation guide

1. Read the migrations from WI-01 for report, line_item and approval_step. Find where the cost centre and the category code live. If the cost centre is missing, settle it with the owner of WI-01 before coding (see Watch out for).
2. Put the file format in one place, the ten column names in order and the row builder. Add `tests/contract/ledger-format.test.js`, which checks the header and order against the table above. Run `npm run test:contract`.
3. Select the reports in Approved with their line items in a fixed order (`approved_at`, `report_id`, `line_item_id`) so a repeat run gives the same bytes. Check with `tests/export-ledger-job.test.js` on fixtures, including a mixed currency report and reports in every other state, which must not appear.
4. Write the CSV and the `.sha256` file to a staging place outside the drop folder, on the same file system. Check that the checksum file equals a fresh SHA-256 of the CSV.
5. In one transaction, move each report to Exported through the state machine and write its audit event through the writer. Check that a failing writer leaves every report in Approved.
6. After the commit, move the pair into the drop folder. At start, finish any staged pair left by an earlier failure before selecting new reports. Check with failure injection after staging, after the commit and during the move, then a rerun.
7. Schedule the run for 02:00 UTC, check the flag, and refuse a second start while a run is active. Check with a fixed clock. Log only report ids and event types.
8. Before the readout, run the job in staging on the pilot team's approved reports and open the file in the finance tool. Then run `npm run lint`, `npm test` and `npm run test:contract`. Keep each pull request under 400 changed lines where possible.

## Acceptance criteria

- [ ] The job starts at 02:00 UTC and not at other times, and a second start during a run writes nothing (`tests/export-ledger-job.test.js`, fixed clock).
- [ ] The files are named `expenses-YYYYMMDD.csv` and `expenses-YYYYMMDD.sha256`, and the second holds the SHA-256 checksum of the first (`tests/export-ledger-job.test.js`).
- [ ] The header and the order are the ten columns of 7.3 and nothing else (`tests/contract/ledger-format.test.js`).
- [ ] The file has one row per line item of every Approved report and no row for a report in any other state (`tests/export-ledger-job.test.js`).
- [ ] Amounts are the stored integers, and `cost_centre` is the value at approval time, not at export time (`tests/export-ledger-job.test.js`).
- [ ] Each exported report is Exported with one audit_event from Approved to Exported, and a failing audit write leaves it Approved with no file published (GOV-2.1, `tests/export-ledger-job.test.js`).
- [ ] After a failure at any step, a rerun leaves one file for the night with no duplicate and no lost row (`tests/export-ledger-job.test.js`).
- [ ] The file holds no merchant, note, name, email address or receipt content, and captured log lines hold no amount (GOV-2.3, GOV-2.6, `tests/export-ledger-job.test.js`).
- [ ] The job runs under the application account and needs no update or delete right on the audit table (GOV-2.2, recorded check in staging).
- [ ] With the flag off the job writes no file and changes no state (DS-1.1, `tests/export-ledger-job.test.js`).
- [ ] `npm run lint`, `npm test` and `npm run test:contract` pass, with no secret or personal data in code, tests, logs or fixtures (DS-1.2, DS-1.3, DS-1.8).
- [ ] At the pilot readout the file for the pilot team's reports opens in the finance tool with no manual change (recorded at the checkpoint).

## Evidence of completion

Demo. At the 2027-04-09 checkpoint, run the job in staging on the pilot team's approved reports. Show the two files in the drop folder, the checksum check against the `.sha256` file, the CSV open in the finance tool with no manual change, and the same reports now in Exported with their audit events. This takes under two minutes.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests.
- Unit tests, `npm test`: `tests/export-ledger-job.test.js`. Contract tests, `npm run test:contract`: `tests/contract/ledger-format.test.js`. The `npm run lint` result.
- The CSV header, the row count and the checksum check output, and a before and after table of report ids and states.
- The audit_event rows for the exported reports, identifiers only, and the failure injection test output.
- Redactions. Attach made-up rows only. For real pilot data attach the header, the row count and the checksum, never employee ids, cost centres or amounts.

The coding agent produces these from the commands above. The developer checks them before posting.

## Integration points

The counterpart item on the Experience track is WI-11 Release readiness and runbook, which describes this job in the runbook and rehearses it.

- Crosses the boundary. The two files in the ledger drop folder, their names and format, the setting that names the drop folder, and the job's log event types.
- Joint check. The nightly file for the pilot team's reports opens in the finance tool with no manual change. This item produces the file and both people open it together, check the ten columns, and verify the checksum against the `.sha256` file.
- Handoff on close. Tell the Experience track how the job starts, what the flag does, the drop folder setting, the log event types, what a rerun does after a failure, and what to check the next morning.

## Out of scope

- The retention job and any deletion (GOV-2.4, GOV-2.5) belong to WI-07. The export deletes nothing.
- Finance sign-off on the export format and the retention period belongs to the program. A format change after sign-off is new work (R3).
- Paying the employee and loading the file into the ledger belong to the finance system (1.4).
- Naming the pilot team and confirming its cost centres belong to the program.
- The runbook, alerting on a failed night and restore from backup belong to WI-11.

## Watch out for

- `cost_centre` is "of the submitter at approval time", but no table of 3.3 holds it. Do not read it live at export time, since it may have changed. If a column is needed, add it by a forward migration with its test (DS-1.5) and record it under Decisions recorded.
- 7.3 does not give a header row, a delimiter, quoting, a timestamp format, the layout of the `.sha256` file or the rule for a night with no reports. Choose a header row, commas, ISO 8601 UTC timestamps, a lowercase hexadecimal digest, and a file even on an empty night. Record each choice and confirm it through the program before the readout. Keep the format in one module (R3).
- Never append to a published file and never export an Exported report. Once a file is in the drop folder the ledger may already have read it, so a duplicate row cannot be taken back.
- Line amounts are stored integers, and the report total is rounded after summing (6.2 item 2). The rows of a report may differ from its `base_total_cents` by a cent. Export the stored values, never recompute them, and tell the program.
- The line_item table holds merchant and note. They are not columns of 7.3, so they stay out. Delete staged files after the move and never log row contents.
- There is no approval per line item. Approval is per report, so every line item of an Approved report is exported. `approved_at` is the decision time of the last approving step, so verify it equals `decided_at` of the report.

## References

- Ground truth sections [3.6](../../ground-truth/architecture.md#36-deployment), [4.2](../../ground-truth/architecture.md#42-gov-2-audit-and-retention) and [7.3](../../ground-truth/architecture.md#73-ledger-export-file). Also [3.4](../../ground-truth/architecture.md#34-report-lifecycle), [6.1](../../ground-truth/architecture.md#61-what-people-asked-for) and [8.1](../../ground-truth/architecture.md#81-risks)
- Depends on [WI-07 Audit log and retention](../m3-enforce-policy/wi-07-audit-log.md). Unblocks [WI-11 Release readiness and runbook](../m5-release/wi-11-release-readiness.md). Related [WI-03 Approval routing engine](../m2-route-to-approvers/wi-03-routing-engine.md)

## Decisions recorded

None yet.
