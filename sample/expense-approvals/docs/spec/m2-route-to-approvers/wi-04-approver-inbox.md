# WI-04 Approver inbox and decisions

| Field | Value |
| --- | --- |
| Milestone | Milestone 2, Route to approvers (`m2-route-to-approvers`), work unit 2 |
| Track | Experience |
| Target | Complete by 2027-03-03 (work unit 2, Route to approvers, 2027-02-15 to 2027-03-05) |
| Checkpoint | 2027-03-05, Milestone 2 demonstration |
| Demonstration | 2027-03-05, milestone 2 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Medium, about 4 days |
| Depends on | WI-02, WI-03 |
| Unblocks | WI-08 |
| Ground truth | Sections 2.1, 3.4, 6.1, 7.1 |

## Why this work item exists

Approvers cannot decide a report that they cannot see. A report waits 11 days on average for approval today, and managers decide in the gaps of their day (1.1, 6.1). The functional requirements (FR) of 2.1 ask for one inbox, oldest first (FR-5), and for approve, reject and return, with a comment on the last two (FR-6). The business analyst (BA) findings add that the total and the submitter must be visible without opening a report (BA-2) and that a comment on a return is not optional (BA-5). This item is separate because it needs submitted reports from WI-02 and approval steps from WI-03. Without it the gate of milestone 2, an approver decides a report from the inbox, cannot be shown, and WI-08 has no inbox to extend.

## Outcome

- An inbox page under `web/src/` that calls `GET /inbox` and lists the reports waiting for the caller, oldest first, in the order returned. Each row shows the submitter and the base total without opening the report (BA-2, FR-5).
- A decision dialog with approve, reject and return that calls `POST /reports/{id}/decisions` with the body of 7.1. The comment is required and not blank for reject and return, with an error tied to the field (FR-6, BA-5).
- Error display for the envelope of 7.1. E_FORBIDDEN shows the message and the rule number from the `rule` field. E_STATE says the report changed and reloads the inbox.
- Keyboard and screen reader operation of the inbox and the dialog, to WCAG, the Web Content Accessibility Guidelines, 2.2 level AA (NFR-3, a quality requirement of 2.2).
- Unit tests in `tests/` and contract tests in `tests/contract/` for both endpoints.

## Context for the agent

- The sample repository is new and empty. This item creates the inbox page, the decision dialog and the error display under `web/src/`, and their tests. It creates no server code.
- WI-01 creates `contracts/openapi.yaml`, the stub server that the Experience track calls, `src/server.js`, `src/config/flags.js`, the contract test runner and the lint setup. Read the `/inbox` and `/reports/{id}/decisions` paths in the contract first. WI-02 creates the web client under `web/src/`. Reuse its API client and error display if it made them (verify at implementation what it exports).
- WI-03 creates `src/routing/engine.js`, the approval_step rows and the state machine of 3.4, so a submitted report has steps and a first approver. The Workflow track owns the handlers `src/api/inbox.js` and `src/api/decisions.js`. Until they are merged, work against the stub.
- WI-06 creates `src/rules/index.js`, due 2027-03-08, after this item's target of 2027-03-03. Until then the service may not refuse a decision, so test the E_FORBIDDEN display with a fixture that follows the envelope.
- The caller's identity comes from the gateway header `X-Employee-Id`. The client never decides who the caller is. How the stub takes an identity is in the WI-01 output (verify at implementation).
- Verify at implementation the shape of the page that `GET /inbox` returns. 7.1 says "200 with a page" and lists no fields. The row needs the submitter, the base total and the submitted date. If the contract lacks one, change it in its own pull request (DS-1.4, the contracts first rule of the delivery standard DS-1). Commands are `npm test`, `npm run test:contract` and `npm run lint`, and new behaviour sits behind `EXPENSE_APPROVALS_ENABLED`, off by default.

## Contract

Fields used by this item, quoted from 7.1, 3.4, 6.1 and 4.1 (GOV-1, the governance rule on approval limits and separation of duties). All paths start with `/v1`. All bodies are JSON. The caller's identity comes from the gateway header `X-Employee-Id`, which the gateway sets and clients cannot forge.

| Method and path | Purpose | Success |
| --- | --- | --- |
| GET /inbox | List the reports waiting for the caller, oldest first. | 200 with a page |
| POST /reports/{id}/decisions | Approve, reject or return. | 200 with the report |

```json
{ "decision": "approve", "comment": "" }
```

`decision` is `approve`, `reject` or `return`. `comment` is required and not blank for `reject` and `return`.

```json
{
  "error": {
    "code": "E_FORBIDDEN",
    "message": "GOV-1.3 refused this decision: the approver already decided an earlier step.",
    "rule": "GOV-1.3",
    "request_id": "9f0c1c0e-6a52-4c0f-b3a6-6d3a1a2c9a10"
  }
}
```

| Code | Status | Meaning |
| --- | --- | --- |
| E_VALIDATION | 400 | The body or a field fails its rule. The message names the field. |
| E_FORBIDDEN | 403 | A governance rule or a role check refused the call. `rule` names the rule. |
| E_NOT_FOUND | 404 | The report does not exist or the caller may not know it exists. |
| E_STATE | 409 | The transition is not allowed from the current state (section 3.4). |

| From | Event | To | Who may cause it |
| --- | --- | --- | --- |
| In approval | approve (last step) | Approved | Approver or delegate |
| In approval | approve (not last step) | In approval | Approver or delegate |
| In approval | reject | Rejected | Approver or delegate |
| In approval | return | Returned | Approver or delegate |

Rejected and Exported are final. Any other transition is refused with the error code E_STATE.

- FR-6. "An approver approves, rejects or returns a report, and must give a comment when rejecting or returning."
- BA-2. "Managers decide in the gaps of their day. They want one inbox, the oldest report first, with the total and the submitter visible without opening it."
- GOV-1.7. "The rules module applies these checks on the server for every decision. The web client may hide a button, but it is never the control."

## Implementation guide

1. Read the two paths in `contracts/openapi.yaml` and run `npm run test:contract` on a clean checkout. Check that the inbox page has the submitter, base total and submitted date. If not, open a separate contract pull request and announce it at the next checkpoint.
2. Add `getInbox` and `postDecision` calls to the API client from WI-02, with the base path `/v1`. Check with `tests/inbox-api.test.js` against stub responses, including each error code.
3. Build the inbox page in `web/src/`. Keep the order the service returns. Show submitter and base total in each row, formatted from integer cents with two decimals and no floating point arithmetic. Check with `tests/inbox.test.js`, including the empty list and a list of three.
4. Poll the inbox on a fixed interval (decision D2 of 8.2, push comes later if the pilot asks). The ground truth gives no interval, so the developer picks one and records it in the pull request. A refresh must not move focus or close an open dialog. Check with a test that refreshes while the dialog is open.
5. Build the decision dialog. Reject and return need a comment that is not blank, and whitespace only counts as blank. Approve sends `"comment": ""`. Check with `tests/decision-dialog.test.js` that no request is sent for a blank comment and that the body matches 7.1.
6. Build the error display. Read `code`, `message`, `rule` and `request_id` from the envelope only, never from the message text. Check with `tests/decision-errors.test.js`, using the exact E_FORBIDDEN example above, then E_STATE, E_VALIDATION and E_NOT_FOUND.
7. On a 200, remove the row, announce the result in a live region and move focus to the next row or the page heading. Check by keyboard and with a screen reader, and record the steps and the result.
8. Run the flow against the routing engine once WI-03 is merged, with two approvers in order, and record it. Run `npm run lint`, `npm test` and `npm run test:contract`. Keep the pull request under 400 changed lines where possible and list each criterion with its proof in the description.

## Acceptance criteria

- [ ] `GET /inbox` rows are shown oldest first, in the order returned, with submitter and base total visible, the total formatted from integer cents such as 25,000.00 (`tests/inbox.test.js`).
- [ ] Approve, reject and return each send the body of 7.1 to `POST /reports/{id}/decisions`. Reject and return with a blank comment send no request and show an error tied to the field (`tests/decision-dialog.test.js`).
- [ ] An E_FORBIDDEN response shows its message and the rule number from `rule`, and the report stays in the inbox (`tests/decision-errors.test.js`).
- [ ] An E_STATE response tells the approver the report changed and reloads the inbox (`tests/decision-errors.test.js`).
- [ ] The client holds no copy of the GOV-1 rules. Every refusal shown comes from the service (GOV-1.7; review of `web/src/` recorded in the pull request).
- [ ] The inbox and dialog work by keyboard alone, with focus kept in the dialog and returned on close, and are announced by a screen reader, to WCAG 2.2 level AA (recorded walkthrough).
- [ ] Requests and responses validate against `contracts/openapi.yaml` (`tests/contract/inbox-decisions.test.js`, `npm run test:contract`).
- [ ] With the flag off, the service answers 404 to `GET /inbox` and the client shows a plain not available message (DS-1.1, `tests/inbox-api.test.js`).
- [ ] No comment, amount or identity is written to the browser console, a URL or a fixture that holds real data (DS-1.8, review recorded).
- [ ] `npm run lint` passes with no warnings, and `npm test` and `npm run test:contract` pass (DS-1.2, DS-1.3).

## Evidence of completion

Demo. At the 2027-03-05 checkpoint, open the web client as the line manager of a report with a base total between 500.01 and 5,000.00, approve it from the inbox, then open the inbox of the department head and approve it there. The report then reads Approved. Then show a refused decision from the stub with its rule number in the message. This takes under two minutes.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests, including any separate contract pull request.
- Unit tests, `npm test`: `tests/inbox-api.test.js`, `tests/inbox.test.js`, `tests/decision-dialog.test.js`, `tests/decision-errors.test.js`. Contract tests, `npm run test:contract`: `tests/contract/inbox-decisions.test.js`. The `npm run lint` result.
- The two approver run as a short recording or screenshots, with the `GET /reports/{id}` body showing the state and both steps, and the keyboard and screen reader walkthrough with each step and result.
- Redactions. Show made-up ids and amounts only. Remove real identities, comments and request ids from the screenshots.

The coding agent produces these from the commands above. The engineer checks them before posting.

## Integration points

The counterpart items on the Workflow track are WI-03 Approval routing engine, which produces the steps and handles decisions, and WI-06 Approval limits and separation of duties, which produces the refusals this item displays.

- Crosses the boundary. `GET /inbox` and `POST /reports/{id}/decisions` as written in `contracts/openapi.yaml`, with the error envelope, served by the stub first and by `src/api/inbox.js` and `src/api/decisions.js` later.
- Joint check. A report is approved by two approvers in order from the inbox in the web client. The Workflow person starts a report with two steps, the Experience person approves as the first approver, confirms the report has left that inbox and appears in the second, and approves it there. `GET /reports/{id}` then shows state Approved and both steps approved.
- Handoff on close. Tell the Workflow track which inbox fields the page reads, which envelope fixtures the tests use, any contract pull request, and that the 2027-03-12 check must show a rule number in the client.

## Out of scope

- The delegate screen, the notification emails and reminders belong to WI-08.
- Enforcing approval limits and separation of duties belongs to WI-06, and building steps, reminders and escalation belongs to WI-03. The client only displays the results.
- Creating, editing and submitting reports belongs to WI-02. The audit trail endpoint belongs to WI-07.
- Push updates (D2) and bulk decisions are not in the ground truth. The stakeholders decide them.

## Watch out for

- GOV-1.7. Hiding or disabling a button is never the control. A button that looks allowed may still be refused, so always handle E_FORBIDDEN.
- Show the rule number from the `rule` field. Do not parse it out of `message`, whose wording may change.
- E_STATE happens when two people act on one report, or the report moved since the page loaded. 7.1 has no version field in the decision request, so do not invent one.
- E_NOT_FOUND also covers a report the caller may not know exists. Say only that it is not available, never why.
- Comments can hold personal data. Do not log them, put them in a URL, or keep them after the dialog closes. Money is integer cents (3.3). Format it, never use floating point.
- E_FORBIDDEN cannot be tested against real rules before WI-06 lands on 2027-03-08. Keep the fixture, then repeat the check with real rules.

## References

- Ground truth sections [2.1](../../ground-truth/architecture.md#21-functional-requirements), [3.4](../../ground-truth/architecture.md#34-report-lifecycle), [6.1](../../ground-truth/architecture.md#61-what-people-asked-for) and [7.1](../../ground-truth/architecture.md#71-rest-api). Also [4.1, GOV-1](../../ground-truth/architecture.md#41-gov-1-approval-limits-and-separation-of-duties) and [2.2, quality requirements](../../ground-truth/architecture.md#22-quality-requirements)
- Depends on [WI-02 Report form and receipt upload](../m1-submit-report/wi-02-report-form.md) and [WI-03 Approval routing engine](wi-03-routing-engine.md). Unblocks [WI-08 Notifications and delegates](../m3-enforce-policy/wi-08-notifications-delegates.md). Related [WI-06 Approval limits and separation of duties](../m3-enforce-policy/wi-06-limits-and-duties.md)

## Decisions recorded

None yet.
