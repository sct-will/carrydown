# WI-07 Audit log and retention

| Field | Value |
| --- | --- |
| Milestone | Milestone 3, Enforce policy (`m3-enforce-policy`), work unit 3 |
| Track | Workflow |
| Target | Complete by 2027-03-17 (work unit 3, Enforce policy, 2027-03-08 to 2027-03-19) |
| Checkpoint | 2027-03-19, Milestone 3 demonstration |
| Demonstration | 2027-03-19, milestone 3 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Medium, about 3 days |
| Depends on | WI-03 |
| Unblocks | WI-09 |
| Ground truth | Sections 3.3, 4.2 |

## Why this work item exists

Today nobody can show who approved what, or when, and two audit findings last year named the missing trail (section 1.1). GOV-2, the audit and retention rule owned by internal audit (section 4.2), asks for a trail that cannot be edited, is written with every change, and is deleted only after 7 years. Goal G4 in section 1.2 depends on it. It is its own item because the guarantees live in the database (rights, one transaction) and not in the routing logic. The ledger export in WI-09 must record its own events through the writer, so it waits for this item.

## Outcome

- `src/audit/writer.js` appends one `audit_event` for every state change, inside the same database transaction as the change.
- A migration under `migrations/` gives the application account insert and select rights on `audit_event`, and no update or delete right.
- `detail` holds identifiers only. The writer refuses anything else, and the change then fails.
- `GET /reports/{id}/audit` in `src/api/audit.js` returns a page of the trail to auditors only, and records an event of type `audit.viewed`.
- Log lines carry report identifiers and event types, never amounts, comments or receipt contents.
- `src/audit/retentionJob.js` deletes reports, line items, approval steps, audit events and receipt files 7 years after the decision date, and skips any report under a legal hold.
- The suites listed in the acceptance criteria pass with `npm test` and `npm run test:contract`.

## Context for the agent

- The repository is new. WI-01 created `src/config/flags.js`, `contracts/openapi.yaml`, the migration for the six tables of section 3.3 (the `audit_event` table has no logic yet) and the stub server. Read them first.
- WI-03 created `src/routing/engine.js`. Its `transition(tx, report, event, actor)` function calls the handlers registered for `afterChange` in the same transaction, and escalation uses it too. This item registers the writer there and adds no second path.
- This item creates `src/audit/writer.js`, `src/api/audit.js`, `src/audit/retentionJob.js`, the migration or migrations, and the tests. Mount the endpoint only when `EXPENSE_APPROVALS_ENABLED` is on.
- One PostgreSQL database holds reports and the trail (section 8.2, D1), which is why one transaction can cover both.
- WI-06 creates `src/rules/index.js`. A refused decision changes nothing, so it reaches no writer and leaves no event.
- Sections 4.2 and 3.3 give no source for the auditor role and no field for a legal hold. Verify at implementation how WI-03 reads roles, and read the choices under "Watch out for".
- Run `npm test`, `npm run test:contract`, `npm run lint` and `npm run migrate` before each pull request.

## Contract

Fields used by this item. Table `audit_event` in full, `report.decided_at`, and the keys of `line_item`, `approval_step` and `receipt` that the retention job deletes. All identifiers are UUIDs (universally unique identifiers). All timestamps are UTC (Coordinated Universal Time).

| Table | Key fields |
| --- | --- |
| report | id, submitter_id, state, base_total_cents, submitted_at, decided_at, version |
| audit_event | id, occurred_at, actor_id, report_id, event_type, from_state, to_state, detail (JSON) |

GOV-2, section 4.2. The owner is internal audit, and the rules apply to every table named below.

1. Every state change of a report writes one audit_event in the same database transaction. If the audit write fails, the change fails.
2. The audit table is append only. The application account has insert and select rights on it and no update or delete right.
3. An audit_event records who, when, what changed (from_state and to_state), and a small detail object. It holds identifiers, never names, receipt contents or email addresses.
4. Reports, line items, approval steps and audit events are kept for 7 years from the decision date. Receipt files are kept as long as their report.
5. Deletion happens only by a retention job after the 7 years, and never for a report under a legal hold.
6. Log lines carry report identifiers and event types. They never carry amounts, comments or receipt contents.
7. Reading the audit trail of a report is itself recorded as an audit_event of type audit.viewed.

From section 7.1. `GET /reports/{id}/audit` reads the audit trail (auditors only) and answers 200 with a page.

| Code | Status | Meaning |
| --- | --- | --- |
| E_FORBIDDEN | 403 | A governance rule or a role check refused the call. `rule` names the rule. |
| E_NOT_FOUND | 404 | The report does not exist or the caller may not know it exists. |

## Implementation guide

1. Read the engine's `transition` and `afterChange`. Fix the `event_type` names (the events of section 3.4 plus `escalation` and `audit.viewed`) and the allowed `detail` keys for each. Check by listing them in the header comment of `src/audit/writer.js`.
2. Write the migration with the rights, the retention role and the legal hold column. Check by `tests/migrations.audit.test.js`, which runs it on an empty database and on a copy of the previous schema (DS-1.5, the delivery standard).
3. Implement `append(tx, event)` with an allow-list of keys and a check that each value is a UUID, an integer or a boolean. Check by `tests/audit.writer.test.js`, with cases for a comment, an amount, a name and an email address.
4. Register `append` with `afterChange`. Force the writer to fail and check that the state, the step and the version are unchanged and the response uses the envelope.
5. Implement `GET /reports/{id}/audit`. Refuse non-auditors with E_FORBIDDEN and write no event. For auditors, read the page and append `audit.viewed` in one transaction. Check by `tests/contract/audit.contract.test.js`.
6. Add `logLine({ reportId, eventType })` to the writer and use it for the audit paths. Check by `tests/audit.logs.test.js`, which runs a decision with a known amount and comment and scans the captured output.
7. Implement `runRetention(now)` in `src/audit/retentionJob.js`. It runs as the retention role, deletes children first and the receipt files with their report, and skips reports with a hold. Check by `tests/audit.retention.test.js` with a fixed clock.
8. Prove the rights with `tests/audit.permissions.test.js`. As the application account, insert and select work, update and delete fail.
9. Run `npm test`, `npm run test:contract` and `npm run lint`, all clean.

## Acceptance criteria

- [ ] Every transition of the section 3.4 table and every escalation writes exactly one `audit_event` in the same transaction (`tests/audit.writer.test.js`).
- [ ] When the audit write fails, the report, steps and version are unchanged and the caller gets an error envelope (`tests/audit.writer.test.js`).
- [ ] The application account can insert and select on `audit_event`, and update and delete are refused by the database (`tests/audit.permissions.test.js`).
- [ ] `detail` accepts identifiers only, and a comment, amount, name or email address is refused (`tests/audit.writer.test.js`).
- [ ] An auditor reading `GET /reports/{id}/audit` gets a page and one new `audit.viewed` event per call. Anyone else gets E_FORBIDDEN and no event (`tests/contract/audit.contract.test.js`).
- [ ] Log lines from a decision carry the report identifier and event type, and no amount, comment or receipt content (`tests/audit.logs.test.js`).
- [ ] The retention job deletes nothing younger than 7 years from `decided_at`, and nothing under a legal hold (`tests/audit.retention.test.js`).
- [ ] The job removes the receipt files together with their report and leaves other reports untouched (`tests/audit.retention.test.js`).
- [ ] The migration passes on an empty database and on a copy of the previous schema (`tests/migrations.audit.test.js`).
- [ ] With `EXPENSE_APPROVALS_ENABLED` off the audit endpoint answers 404 (`tests/contract/audit.contract.test.js`).
- [ ] No fixture, log or test holds a secret or personal data (DS-1.8), recorded in the pull request.

## Evidence of completion

Demo. Approve a report from the inbox, then call `GET /reports/{id}/audit` as an auditor. The page shows the event with `from_state`, `to_state` and identifiers only. Call it again and show the new `audit.viewed` event. Then show an update on `audit_event` failing as the application account. It takes under two minutes with saved requests.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests, with the migration in its own pull request if it is large.
- The suites `tests/audit.writer.test.js`, `tests/audit.permissions.test.js`, `tests/audit.logs.test.js`, `tests/audit.retention.test.js` and `tests/migrations.audit.test.js` with `npm test`, and `tests/contract/audit.contract.test.js` with `npm run test:contract`.
- A table of the `audit_event` rows for the demo report, with identifiers only.
- The captured output of the failed update, with the database error text.
- Redactions. Remove employee identifiers from pasted responses that are not fixtures.

The coding agent produces these from the commands above. The engineer checks them before posting.

## Integration points

The counterpart on the Experience track is WI-08, Notifications and delegates, which turns the same state change into an email.

- Crosses the boundary. The state change that both the audit event and the notification event of section 7.2 come from, with the same `report_id` and `to_state`, and the `event_type` names.
- Joint check. A decision produces an audit event and a notification, and the submitter sees the new state. This item shows the `audit_event` row for the decision that the notification came from.
- Handoff on close. Give WI-08 the `event_type` names and say that log lines in the worker follow the same rule (identifiers and event types only).
- Timing. WI-08 completes on 2027-03-17, the same day as this item. Agree the event fields by the Rules meet routing checkpoint on 2027-03-12.

## Out of scope

- The rules of GOV-1 and the refusal of decisions belong to WI-06.
- The notification event, the queue and the email belong to WI-08.
- The nightly export and its `export` event belong to WI-09, which calls the writer from this item.
- Setting or releasing a legal hold has no endpoint in section 7.1. It belongs to the stakeholders.
- Changing the retention period, or signing it off, belongs to the stakeholders.
- An auditor screen in the web client is not in the plan.

## Watch out for

- The retention job must delete, while the application account must not. Run the job as a separate database role that only the job uses. The ground truth does not name it, so confirm with internal audit.
- Section 3.3 has no legal hold field. This item adds a boolean on `report`, false by default, in a forward migration. Confirm with internal audit.
- A write failure has no code in the table of section 7.1. Answer status 500 in the envelope and put the new code in a contract pull request (DS-1.4).
- An approve that is not the last step keeps the state In approval, so `from_state` equals `to_state`. Write the event anyway.
- The ground truth gives no actor for events the service causes, such as `routed`. Use a fixed service identifier from configuration, never a name.
- Count `audit.viewed` once per request, including later pages. A refused read writes none. If the event cannot be written, the read fails.
- Reports never decided have no decision date, so the job leaves them alone.

## References

- [Section 3.3, Data model](../../ground-truth/architecture.md#33-data-model)
- [Section 4.2, GOV-2](../../ground-truth/architecture.md#42-gov-2-audit-and-retention)
- [Section 7.1, REST API](../../ground-truth/architecture.md#71-rest-api)
- [WI-03 Approval routing engine](../m2-route-to-approvers/wi-03-routing-engine.md)
- [WI-09 Ledger export job](../m4-pilot/wi-09-ledger-export.md)
- [WI-08 Notifications and delegates](wi-08-notifications-delegates.md)

## Decisions recorded

None yet.
