# WI-08 Notifications and delegates

| | |
| --- | --- |
| Milestone | Milestone 3, Enforce policy (`m3-enforce-policy`), work unit 3 |
| Track | Experience |
| Target | Complete by 2027-03-19 (work unit 3, Enforce policy, 2027-03-08 to 2027-03-19) |
| Checkpoint | 2027-03-19, Milestone 3 demonstration |
| Demonstration | 2027-03-19, milestone 3 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Medium, about 4 days |
| Depends on | WI-04, WI-06 |
| Unblocks | WI-11 |
| Ground truth | Sections 6.1, 6.2, 7.2 |

## Why this work item exists

Submitters do not learn what happened to a report, and reports wait when a manager is on leave (6.1 BA-4, BA-5). The functional requirements (FR) of 2.1 ask that the submitter is told of each decision and state change (FR-7) and that an approver can name a delegate for a range of dates (FR-8). The business analyst (BA) findings add that a delegate fixes most of the waiting and that a return needs a visible reason. The Experience track owns the notification worker and the delegate screen (3.2). This item is separate because it needs the inbox and decisions of WI-04 to cause state changes and the rules of WI-06 to govern delegates. Without it the gate of milestone 3, submitters are notified, cannot be shown, and WI-11 has no notification path to rehearse.

## Outcome

- `src/notify/worker.js` reads each `report.state_changed` event of 7.2 and sends one email to `recipient_id`, with content for every state change of 3.4.
- The email reads amounts and comments from the API, the application programming interface, with the service account. The event stays free of them (FR-7, BA-5).
- A reminder email goes to the current approver after 3 business days without a decision (3.5 rule 3).
- A delegate screen under `web/src/` creates or replaces the caller's delegate record with `PUT /delegates` (FR-8, BA-4).
- A delegate sees the approver's inbox from WI-04 for the date range of the record.
- With the flag off, the worker sends nothing and `PUT /delegates` answers 404.

## Context for the agent

- The sample repository is new and empty. This item creates `src/notify/worker.js` (templates may sit next to it in `src/notify/`), the delegate screen under `web/src/` and the tests. It adds no other server code.
- WI-01 creates `contracts/openapi.yaml`, `src/config/flags.js`, the stub server, the contract test runner and the migration for the six tables of 3.3, which includes delegate. WI-04 creates the inbox page and the error display in `web/src/`. Reuse them.
- WI-06 creates `src/rules/index.js`, which applies GOV-1 (the governance rule on approval limits and separation of duties) on the server. GOV-1.4 governs delegates, so the screen never decides what a delegate may do.
- 7.2 says the API puts one event on the queue for each state change. The plan names no Workflow item as the publisher. Verify at implementation which merged item publishes it. Until then build against fixture events that follow 7.2.
- The ground truth does not say which queue product is used, how the worker turns an employee id into an email address, or how the service account signs in. Verify these with the Workflow track. No address goes into an event or an audit record.
- WI-03 creates business day counting in `src/routing/engine.js`, including the weekend rule of 6.2 item 4. Verify the exported name and reuse it.
- Commands are `npm test`, `npm run test:contract` and `npm run lint`. All new behaviour sits behind `EXPENSE_APPROVALS_ENABLED`, off by default (DS-1, the delivery standard). The reminder comes after 3 business days, and finance asked for 2 (see Watch out for).

## Contract

Fields used by this item, quoted from 7.2, 7.1, 3.3, 3.4, 3.5 and 4.1. The API puts one event on the queue for each state change. The worker turns it into an email.

```json
{
  "event_id": "string, UUID",
  "event_type": "report.state_changed",
  "occurred_at": "string, UTC timestamp",
  "report_id": "string, UUID",
  "from_state": "string, one of the states in 3.4",
  "to_state": "string, one of the states in 3.4",
  "recipient_id": "string, employee id",
  "comment_present": "boolean"
}
```

The event never carries amounts, comments or names. The worker reads those from the API with the service account when it builds the email.

| Method and path | Purpose | Success |
| --- | --- | --- |
| GET /reports/{id} | Read a report with line items, receipts and steps. | 200 |
| PUT /delegates | Create or replace the caller's delegate record. | 200 |

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

- Table delegate (3.3), key fields: id, approver_id, delegate_id, starts_on, ends_on.
- FR-7. "The submitter is notified of each decision and each state change."
- FR-8. "An approver names a delegate for a range of dates. The delegate sees the approver's inbox for that range."
- 3.5 rule 3. "A reminder goes to the current approver after 3 business days without a decision."
- GOV-1.4. "A delegate may act only for dates inside the delegate record, and never on a report that the delegator submitted."
- GOV-2.6 (GOV-2 is the audit and retention rule). "Log lines carry report identifiers and event types. They never carry amounts, comments or receipt contents."
- DS-1.6. "Every error response uses the envelope of section 7.1." The codes used here are E_VALIDATION (400) and E_FORBIDDEN (403, `rule` names the rule).

## Implementation guide

1. Read `PUT /delegates` and `GET /reports/{id}` in `contracts/openapi.yaml` and run `npm run test:contract`. Verify the request body of `PUT /delegates`. A contract change is its own pull request (DS-1.4).
2. Write fixture events for every from and to pair of 3.4. Add `tests/contract/notification-event.test.js`, which accepts the eight fields of 7.2 and rejects any other field.
3. Build `src/notify/worker.js`. Check the flag, drop an event_id seen before, read the report with the service account, build the email by `to_state`, send it, and log only the report id and event type. Check with `tests/notify-worker.test.js`, using a fake mailer and a fake API.
4. Write the content for each state change. For Rejected and Returned, add the approver's comment when `comment_present` is true (BA-5). Check with one test case per pair of 3.4.
5. Add the reminder with the 3 held in one constant, reusing the business day counting of WI-03. Check with `tests/notify-reminder.test.js` and a fixed clock, covering day 2, day 3 and a weekend submission.
6. Build the delegate screen in `web/src/`. Show the current record, say that saving replaces it, and block an end date before the start date. Show envelope errors. Check with `tests/delegates-screen.test.js` and `tests/contract/delegates.contract.test.js`.
7. Check by keyboard and with a screen reader that every field has a label and every error is tied to its field. Record the steps.
8. Run a decision from the inbox through the event, the email and the submitter's view, then run `npm run lint`, `npm test` and `npm run test:contract`. Keep each pull request under 400 changed lines where possible, one for the worker and one for the screen.

## Acceptance criteria

- [ ] For each valid event the worker sends exactly one email to `recipient_id`, for every from and to pair of 3.4 (`tests/notify-worker.test.js`).
- [ ] Fixture events carry only the eight fields of 7.2 (`tests/contract/notification-event.test.js`).
- [ ] Amounts and comments come from `GET /reports/{id}` read with the service account. A comment appears only when `comment_present` is true (`tests/notify-worker.test.js`).
- [ ] The same event_id delivered twice sends one email (`tests/notify-worker.test.js`).
- [ ] Captured log lines hold report ids and event types only, with no amount, comment, receipt content or address (GOV-2.6, `tests/notify-worker.test.js`).
- [ ] A reminder goes to the current approver on the third business day and not on the second, and a weekend submission counts from the next Monday (`tests/notify-reminder.test.js`).
- [ ] The delegate screen saves with `PUT /delegates`, blocks an end date before the start date and shows service errors from the envelope (`tests/delegates-screen.test.js`).
- [ ] Requests and responses of `PUT /delegates` validate against `contracts/openapi.yaml` (`tests/contract/delegates.contract.test.js`).
- [ ] A delegate sees the approver's inbox inside the range, and a decision outside it shows the GOV-1.4 refusal (recorded run, with WI-06 merged).
- [ ] The delegate screen works by keyboard and a screen reader, to WCAG, the Web Content Accessibility Guidelines, 2.2 level AA (recorded walkthrough).
- [ ] With the flag off the worker sends nothing and `PUT /delegates` answers 404 (DS-1.1, `tests/notify-worker.test.js`).
- [ ] `npm run lint`, `npm test` and `npm run test:contract` pass, and no secret or personal data is in code, tests, logs or fixtures (DS-1.3, DS-1.8).

## Evidence of completion

Demo. At the 2027-03-19 checkpoint, return a report with a comment from the inbox. Show the event on the queue, the email the test mailer captured with the new state and the comment, and the submitter opening the report to see Returned. Then save a delegate record from the screen. This takes under two minutes.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests, including any separate contract pull request.
- Unit tests, `npm test`: `tests/notify-worker.test.js`, `tests/notify-reminder.test.js`, `tests/delegates-screen.test.js`. Contract tests, `npm run test:contract`: `tests/contract/notification-event.test.js`, `tests/contract/delegates.contract.test.js`.
- The event JSON and the captured email for one return, side by side, and the `PUT /delegates` response body.
- A screenshot of the delegate screen and the keyboard and screen reader walkthrough with each step and result. Redactions. Use made-up ids, amounts and addresses only, and remove real names and comments.

The coding agent produces these from the commands above. The developer checks them before posting.

## Integration points

The counterpart items on the Workflow track are WI-07 Audit log and retention, which records the same state change, and WI-06 Approval limits and separation of duties, which enforces the delegate rules.

- Crosses the boundary. The `report.state_changed` event of 7.2 on the queue, the service account that reads `GET /reports/{id}`, and `PUT /delegates` in `contracts/openapi.yaml`.
- Joint check. A decision produces an audit event and a notification, and the submitter sees the new state. This item shows the notification and the submitter's view for the decision made together. The Workflow person shows the audit_event row for the same decision.
- Handoff on close. Tell the Workflow track which item publishes the event, what the service account reads, the request body of `PUT /delegates`, and where the reminder number 3 is held.
- Timing. WI-07 is due on 2027-03-17, one day before this item. Agree the decision used for the joint check by 2027-03-15.

## Out of scope

- Checking delegate dates and refusing decisions belongs to WI-06. The screen only helps the user.
- Publishing the event, the audit record and the queue itself belong to the Workflow track (WI-07 for the audit record).
- Routing and escalation belong to WI-03, and the inbox page and decision dialog belong to WI-04. This item only words and sends the reminder.
- Other channels than email, push updates and removing a delegate record are not in the ground truth. The program decides them, and a delete would need a contract change.

## Watch out for

- Reminder days. BA-6 (6.1) and 6.2 item 6 ask for 2 business days. Section 3.5 says 3. The architecture document is the ground truth and an earlier section wins over the business analyst note, so use 3. The next document version should settle the number. Keep it in one constant.
- 7.2 defines only `report.state_changed`. It defines no reminder or escalation event. Agree with the Workflow track how the worker learns a reminder is due. Do not invent an event type without a contract pull request.
- The email may hold amounts and comments, but the event, the queue and the logs must not (R4 of 8.1, GOV-2.6). An address never goes into an event or an audit record (GOV-2.3). The worker uses `recipient_id` and never picks the recipient. Build the email at send time and keep nothing.
- The queue may deliver an event twice. Use `event_id` to send once. The ground truth does not state the delivery guarantee, so verify it.
- `PUT /delegates` replaces the record. The ground truth does not say whether `ends_on` is inclusive. Treat both dates as inside the record, verify with the finance policy team and record the answer.

## References

- Ground truth sections [6.1](../../ground-truth/architecture.md#61-what-people-asked-for), [6.2](../../ground-truth/architecture.md#62-edge-cases-the-interviews-surfaced) and [7.2](../../ground-truth/architecture.md#72-notification-event). Also [3.4](../../ground-truth/architecture.md#34-report-lifecycle), [3.5](../../ground-truth/architecture.md#35-routing) and [4.1](../../ground-truth/architecture.md#41-gov-1-approval-limits-and-separation-of-duties). Depends on [WI-04 Approver inbox and decisions](../m2-route-to-approvers/wi-04-approver-inbox.md) and [WI-06 Approval limits and separation of duties](wi-06-limits-and-duties.md). Unblocks [WI-11 Release readiness and runbook](../m5-release/wi-11-release-readiness.md). Related [WI-03](../m2-route-to-approvers/wi-03-routing-engine.md) and [WI-07](wi-07-audit-log.md)

## Decisions recorded

None yet.
