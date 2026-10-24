# WI-03 Approval routing engine

| | |
| --- | --- |
| Milestone | Milestone 2, Route to approvers (`m2-route-to-approvers`), work unit 2 |
| Track | Workflow |
| Target | Complete by 2027-02-24 (work unit 2, Route to approvers, 2027-02-15 to 2027-03-05) |
| Checkpoint | 2027-02-26, Routing meets inbox |
| Demonstration | 2027-03-05, milestone 2 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Large, about 5 days |
| Depends on | WI-01 |
| Unblocks | WI-04, WI-06, WI-07 |
| Ground truth | Sections 3.4, 3.5, 7.1 |

## Why this work item exists

A submitted report must reach the right approvers without manual routing (goal G2 in section 1.2, requirement FR-4 in section 2.1). Section 3.5 turns the base total into an ordered list of approval steps. Section 3.4 lists the only state changes a report may make. Without this item a draft can be submitted but nobody can decide it, because no steps exist. It is its own item because the approver inbox (WI-04), the rules module (WI-06) and the audit writer (WI-07) all read the steps and states that it creates.

## Outcome

- `src/routing/engine.js` computes the base total in integer cents, builds the approval steps of section 3.5 and applies the state table of section 3.4.
- `POST /reports/{id}/submit` stores the `approval_step` rows, moves the report to In approval and answers 202 with the state. A base total above 25,000.00 answers E_LIMIT (422) and changes nothing.
- `GET /inbox` in `src/api/inbox.js` lists, oldest first, the reports whose current step belongs to the caller.
- `POST /reports/{id}/decisions` in `src/api/decisions.js` moves the report by approve, reject or return, and answers E_STATE (409) for every transition the table does not list.
- The engine counts business days, so the reminder after 3 business days and the escalation after 5 are computed and tested, including a report submitted on a weekend.

## Context for the agent

- The repository is new. WI-01 creates `src/server.js`, `src/config/flags.js`, `contracts/openapi.yaml`, the contract test runner, the first migration with the six tables of section 3.3 (without logic) and a stub server. Read them first.
- This item creates `src/routing/engine.js`, `src/api/reports.js` (the submit handler), `src/api/inbox.js` and `src/api/decisions.js`. Mount them only when `EXPENSE_APPROVALS_ENABLED` is on. With the flag off only the health check answers.
- This item creates no audit or rules code. WI-07 creates `src/audit/writer.js` and WI-06 creates `src/rules/index.js`. Route every state change through one engine function, `transition(tx, report, event, actor)`, that updates the row and calls the handlers registered for `afterChange` in the same transaction. WI-07 registers the audit writer there.
- The decisions handler calls a `checkRules` function before it writes. Until WI-06 lands, a placeholder allows only the approver of the current step, and WI-06 replaces it.
- The ground truth gives no table for the reporting line, the finance reviewers or the rate table. Read them through three functions passed in to the engine, with fixtures in the tests. Verify at implementation which module loads the real data.
- Money is integer cents everywhere. The thresholds are 50000, 500000 and 2500000 cents. Run `npm test`, `npm run test:contract`, `npm run lint` and `npm run migrate` before each pull request.

## Contract

Fields used by this item. Report `state`, `base_total_cents`, `submitted_at`, `decided_at` and `version`, and every field of `approval_step`. All identifiers are UUIDs (universally unique identifiers) and all timestamps are UTC (Coordinated Universal Time). Report lifecycle, section 3.4.

| From | Event | To | Who may cause it |
| --- | --- | --- | --- |
| Draft | submit | Submitted | Submitter |
| Submitted | routed | In approval | Service |
| In approval | approve (last step) | Approved | Approver or delegate |
| In approval | approve (not last step) | In approval | Approver or delegate |
| In approval | reject | Rejected | Approver or delegate |
| In approval | return | Returned | Approver or delegate |
| Returned | submit | Submitted | Submitter |
| Approved | export | Exported | Export job |

Rejected and Exported are final. Any other transition is refused with the error code E_STATE.

Routing, section 3.5. The routing engine builds the steps when a report moves from Submitted to In approval. It uses the base total of the report.

| Base total (USD) | Steps in order |
| --- | --- |
| Up to 500.00 | Line manager |
| 500.01 to 5,000.00 | Line manager, department head |
| 5,000.01 to 25,000.00 | Line manager, department head, finance reviewer |
| Above 25,000.00 | Not routed. The service returns E_LIMIT and the submitter follows the offline exception process. |

1. If an approver in a step is the submitter, that step moves to the next person up the reporting line.
2. Steps are decided in order. A later step does not see the report until the earlier step approves.
3. A reminder goes to the current approver after 3 business days without a decision. After 5 business days the step escalates to the next person up the reporting line, and the audit trail records the escalation.
4. The routing result is stored as approval_step rows and does not change after routing, except by escalation.

Edge cases, section 6.2. In item 2, the report total is the sum of the converted lines, rounded half up to the cent after summing. In item 3, a returned report keeps its line items and receipts, and the version number goes up when it is submitted again. In item 4, a report submitted on a weekend counts its business days from the next Monday.

From section 7.1. All paths start with `/v1`. The caller's identity comes from the gateway header `X-Employee-Id`. `POST /reports/{id}/submit` submits a draft or returned report (success 202 with the state). `GET /inbox` lists the reports waiting for the caller, oldest first (200 with a page). `POST /reports/{id}/decisions` approves, rejects or returns (200 with the report).

| Code | Status | Meaning |
| --- | --- | --- |
| E_VALIDATION | 400 | The body or a field fails its rule. The message names the field. |
| E_STATE | 409 | The transition is not allowed from the current state (section 3.4). |
| E_LIMIT | 422 | The base total is above 25,000.00 and cannot be routed. |

Decision request `{ "decision": "approve", "comment": "" }`. `decision` is `approve`, `reject` or `return`. `comment` is required and not blank for `reject` and `return`.

## Implementation guide

1. Read `contracts/openapi.yaml` from WI-01. Check that the step fields, the step states and the inbox page are described. If not, open a pull request that changes only the contract first (DS-1.4, the delivery standard). Check by `npm run test:contract`.
2. Create `baseTotalCents(lines, rates)` in `src/routing/engine.js`. Convert with integer arithmetic, sum, then round half up once. Check by `tests/routing.engine.test.js` with mixed currencies and a half-cent case.
3. Create `buildSteps(report, lookups)` for the table of section 3.5 with the self-approver rule. Test the cents 50000, 50001, 500000, 500001, 2500000 and 2500001, and a submitter who is their own line manager.
4. Create `transition` and the state table of section 3.4. Test every listed row, then every other pair of state and event, which must give E_STATE in `tests/routing.states.test.js`.
5. Create the submit handler, `src/api/inbox.js` and `src/api/decisions.js`. Roll back the whole request on any failure. Test that a decision on step 2 is refused until step 1 approves (the later step is not visible).
6. Create `addBusinessDays`, `reminderDue` and `escalationDue`. Test a Friday start, a Saturday start and a Sunday start in `tests/routing.business-days.test.js`.
7. Create `escalate(step)`. It changes `approver_id` only and calls `afterChange` with the event `escalation`. Test that no other step row changes. Add `tests/contract/routing.contract.test.js` for the three endpoints. Run `npm test`, `npm run test:contract` and `npm run lint`, all clean.

## Acceptance criteria

- [ ] The base total is computed in cents by the rule of section 6.2 item 2, and each row of the table in section 3.5 stores its steps in order with the roles named (`tests/routing.engine.test.js`).
- [ ] A base total of 2500001 cents answers E_LIMIT with status 422 and leaves the report and its steps unchanged (`tests/routing.states.test.js`).
- [ ] When an approver is the submitter, the step moves up the reporting line (`tests/routing.engine.test.js`).
- [ ] Every row of the section 3.4 table works, and every other transition answers E_STATE with status 409 (`tests/routing.states.test.js`).
- [ ] A later step does not appear in the inbox until the earlier step approves (`tests/contract/routing.contract.test.js`).
- [ ] The reminder is due after 3 business days and the escalation after 5, and a weekend submission counts from the next Monday (`tests/routing.business-days.test.js`).
- [ ] Escalation changes only the approver of the overdue step and every handler for `afterChange` is called in the same transaction (`tests/routing.engine.test.js`).
- [ ] A blank comment on reject or return answers E_VALIDATION naming the field, and every error uses the envelope (`tests/contract/routing.contract.test.js`).
- [ ] With `EXPENSE_APPROVALS_ENABLED` off, the three endpoints answer 404 (`tests/contract/routing.contract.test.js`).
- [ ] No log line, test fixture or error message carries an amount or a comment (reviewed in the pull request).

## Evidence of completion

Demo. Submit three reports of 400.00, 4,000.00 and 6,000.00 USD (United States dollar) against the service, then call `GET /inbox` as each first approver. The responses show one, two and three steps. Run the 25,000.01 case to see E_LIMIT. It takes under two minutes with saved requests.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests, including any contract-only pull request.
- The suites `tests/routing.engine.test.js`, `tests/routing.states.test.js` and `tests/routing.business-days.test.js` with `npm test`, and `tests/contract/routing.contract.test.js` with `npm run test:contract`.
- A table of the `approval_step` rows for the three demo reports. Remove employee identifiers from any pasted response that is not a fixture.

The coding agent produces these from the commands above. The developer checks them before posting.

## Integration points

The counterpart on the Experience track is WI-04, Approver inbox and decisions, and WI-02, Report form and receipt upload, which calls the submit endpoint.

- Crosses the boundary. `GET /inbox` and `POST /reports/{id}/decisions` in `contracts/openapi.yaml`, with the step states and error codes in it.
- Joint check. A submitted report produces the approval steps of section 3.5, and the inbox contract returns them for the first approver. This item shows the stored steps and the inbox response for the demo reports.
- Handoff on close. Tell the Experience owner the step role names, the step states, the page shape of the inbox and the fact that the rules check is a placeholder until WI-06.

## Out of scope

- The rules of GOV-1, including who may decide, limits per step and separation of duties. WI-06 owns them.
- Writing audit events and log lines belong to WI-07. This item only provides the `afterChange` hook.
- Reminder emails and the notification event belong to WI-08, which also owns the delegate inbox. This item only says when a reminder or escalation is due.
- The inbox screen and the decision dialog belong to WI-04.
- The nightly export and the move to Exported belong to WI-09.

## Watch out for

- Reminders. The business analyst note asks for 2 business days (section 6.1 and 6.2 item 6). Section 3.5 says 3. Use 3. The next version of the document should settle the number.
- Step states are not listed in the ground truth. Choose the smallest set, record it in `contracts/openapi.yaml` and keep rows after a return so the history stays (GOV-2.4, the seven year keep rule).
- Business days are Monday to Friday. The ground truth names no public holidays, so do not invent a calendar. The clock for a step starts at the earlier step's `decided_at`, or at `submitted_at` for step 1, and a weekend start counts from the next Monday. No new column is needed. The ground truth also names no scheduler for reminders and escalations, so provide the functions and a tested entry point and raise the owner at the checkpoint.
- If the move up the line lands on a person who already holds a step, move up again, because GOV-1.3, the rule that the people in one route differ, needs different people. The ground truth does not say this, so test and mention it.
- Whether an E_LIMIT submit leaves the report in Draft or Returned is not stated. Leave it unchanged and say so in the pull request.

## References

- Sections [3.4, Report lifecycle](../../ground-truth/architecture.md#34-report-lifecycle) and [3.5, Routing](../../ground-truth/architecture.md#35-routing)
- [Section 7.1, REST API](../../ground-truth/architecture.md#71-rest-api)
- [Section 6.2, Edge cases](../../ground-truth/architecture.md#62-edge-cases-the-interviews-surfaced)
- [WI-01 Service scaffold, flag and API contract](../m1-submit-report/wi-01-service-scaffold.md)
- [WI-04 Approver inbox and decisions](wi-04-approver-inbox.md)
- [WI-06 Approval limits and separation of duties](../m3-enforce-policy/wi-06-limits-and-duties.md)
- [WI-07 Audit log and retention](../m3-enforce-policy/wi-07-audit-log.md)

## Decisions recorded

None yet.
