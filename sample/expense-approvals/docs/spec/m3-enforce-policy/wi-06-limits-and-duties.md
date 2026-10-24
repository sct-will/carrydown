# WI-06 Approval limits and separation of duties

| Field | Value |
| --- | --- |
| Milestone | Milestone 3, Enforce policy (`m3-enforce-policy`), work unit 3 |
| Track | Workflow |
| Target | Complete by 2027-03-08 (work unit 3, Enforce policy, 2027-03-08 to 2027-03-19) |
| Checkpoint | 2027-03-12, Rules meet routing |
| Demonstration | 2027-03-19, milestone 3 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Medium, about 3 days |
| Depends on | WI-03 |
| Unblocks | WI-08 |
| Ground truth | Sections 3.5, 4.1, 7.1 |

## Why this work item exists

Staff approve money, so the finance policy team set two things in GOV-1, the rule on approval limits and separation of duties (section 4.1). Nobody may decide their own report, people in one route must differ, delegates have limits, and nothing above 25,000.00 is approved in the service. Routing (WI-03) puts the right people in the steps, but it does not stop a wrong person from calling the decision endpoint. The control must sit on the server for every decision (GOV-1.7), so it is a separate item with one test per rule. Without it the delegate work in WI-08 has no limit to honour, and goal G3 in section 1.2 is not met.

## Outcome

- `src/rules/index.js` exports `checkDecision`, which applies GOV-1.1 to GOV-1.7 to every decision and returns either success or the rule number and a message.
- `POST /reports/{id}/decisions` calls `checkDecision` before it writes anything. A refusal answers E_FORBIDDEN (403) with the rule number in `error.rule`.
- A refused decision changes nothing. The report, the `approval_step` rows and the audit table are the same before and after.
- A delegate acts only inside the dates of the `delegate` record, and never on a report the delegator submitted.
- Approvals respect the limit of the approver's role, and nothing above 25,000.00 can be approved.
- `tests/rules.test.js` has one test group for each of GOV-1.1 to GOV-1.7, and `tests/contract/rules.contract.test.js` proves the envelope and the unchanged state.
- The placeholder `checkRules` that WI-03 left in `src/api/decisions.js` is gone.

## Context for the agent

- The repository is new. WI-01 created the flag in `src/config/flags.js`, `contracts/openapi.yaml` and the migration with the `delegate` table. Read them first.
- WI-03 created `src/routing/engine.js` (the `transition` function and the reporting line lookup), `src/api/decisions.js` with the placeholder `checkRules`, and `src/api/inbox.js`. This item creates `src/rules/index.js` and replaces the placeholder.
- WI-08 creates `src/api/delegates.js` and the delegate screen. This item only reads the `delegate` table, with rows created by the tests.
- The decision handler works in one database transaction and locks the report row before it checks, so two decisions cannot race past a rule. A refusal rolls the transaction back.
- Use the same reporting line and finance reviewer lookups as the engine. Verify at implementation how WI-03 named them.
- This item needs no new endpoint and no change to `contracts/openapi.yaml`. If the shape of the error `message` must change, make that its own pull request (DS-1.4, the delivery standard).
- Run `npm test`, `npm run test:contract` and `npm run lint` before each pull request.

## Contract

Fields used by this item. Report `submitter_id`, `base_total_cents` and `state`, `approval_step` `role`, `approver_id` and `position`, and `delegate` `approver_id`, `delegate_id`, `starts_on` and `ends_on`.

GOV-1, section 4.1. The owner is the finance policy team, and the rules apply to every decision, in every environment.

1. Nobody approves, rejects or returns their own report, directly or as a delegate.
2. An approver must stand above the submitter in the reporting line, or be a finance reviewer.
3. The people in the steps of one report must all be different people.
4. A delegate may act only for dates inside the delegate record, and never on a report that the delegator submitted.
5. Limits per step. A line manager's approval counts only for a base total up to 5,000.00. A department head's approval counts up to 25,000.00. Nothing above 25,000.00 can be approved in the service (section 3.5).
6. A refused decision returns the error code E_FORBIDDEN, names the rule number (for example GOV-1.3) and changes nothing.
7. The rules module applies these checks on the server for every decision. The web client may hide a button, but it is never the control.

Section 3.5 routes a base total "Above 25,000.00" as "Not routed. The service returns E_LIMIT and the submitter follows the offline exception process."

The decision request of section 7.1 is `{ "decision": "approve", "comment": "" }`, and `decision` is `approve`, `reject` or `return`. The error envelope is used by every endpoint.

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
| E_FORBIDDEN | 403 | A governance rule or a role check refused the call. `rule` names the rule. |

## Implementation guide

1. Read `src/api/decisions.js` and the engine lookups. List the inputs each rule needs. Check by writing the list as the argument type of `checkDecision` in `src/rules/index.js`.
2. Write the failing tests first in `tests/rules.test.js`, one group per rule number, each with a case that passes and a case that is refused.
3. Implement GOV-1.1 and GOV-1.2 (the submitter, the reporting line, the finance reviewer). Check by the groups for those rules.
4. Implement GOV-1.3 and GOV-1.4 (earlier steps of the same report, the delegate dates, the delegator who submitted). Test the first and last date of a delegate record and the day after.
5. Implement GOV-1.5 with integer cents against 500000 and 2500000, and test the edges 500000, 500001, 2500000 and 2500001.
6. Wire `checkDecision` into `src/api/decisions.js` after the checks for existence, validation and state, and inside the transaction. Remove the placeholder. Check by `tests/contract/rules.contract.test.js`.
7. Prove GOV-1.6. For every refusal, compare the `report`, `approval_step` and `audit_event` rows before and after, and assert the envelope fields `code`, `rule`, `message` and `request_id`.
8. Prove GOV-1.7 by calling the API directly with no web client, for every rule, and with the flag on only.
9. Run `npm test`, `npm run test:contract` and `npm run lint`, all clean.

## Acceptance criteria

- [ ] GOV-1.1 refuses approve, reject and return by the submitter, and by a delegate who is the submitter (`tests/rules.test.js`).
- [ ] GOV-1.2 refuses an approver who is not above the submitter and not a finance reviewer (`tests/rules.test.js`).
- [ ] GOV-1.3 refuses a person who already decided or holds another step of the same report (`tests/rules.test.js`).
- [ ] GOV-1.4 refuses a delegate outside the dates, and on a report the delegator submitted, and allows the first and last day (`tests/rules.test.js`).
- [ ] GOV-1.5 refuses an approval above the limit of the role, and any approval above 25,000.00 (`tests/rules.test.js`).
- [ ] GOV-1.6 answers E_FORBIDDEN (403) with `rule` set, and the report, steps and audit rows are unchanged (`tests/contract/rules.contract.test.js`).
- [ ] GOV-1.7 holds with the web client absent, for every rule (`tests/contract/rules.contract.test.js`).
- [ ] Each refusal message starts with the rule number, as in the example of section 7.1, and holds no amount, name or comment (`tests/rules.test.js`).
- [ ] No log line written during a refusal carries an amount or a comment (GOV-2.6, the audit and retention rule on log lines), checked by capturing the output in `tests/rules.test.js`.
- [ ] With `EXPENSE_APPROVALS_ENABLED` off the decision endpoint answers 404 and the module is not called (`tests/contract/rules.contract.test.js`).
- [ ] The placeholder `checkRules` no longer exists, and `npm test`, `npm run test:contract` and `npm run lint` pass.

## Evidence of completion

Demo. Call `POST /reports/{id}/decisions` as the submitter of a report in approval, then as a delegate outside the dates. Show the 403 body with `GOV-1.1` and `GOV-1.4` in `error.rule`, then `GET /reports/{id}` showing the same state and version as before. It takes under two minutes with saved requests.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests.
- The suite `tests/rules.test.js` with `npm test`, and `tests/contract/rules.contract.test.js` with `npm run test:contract`.
- A table of the seven rule numbers, the test name that proves each and the refusal message it returns.
- The before and after row counts for one refused decision, with identifiers only.
- Redactions. Remove employee identifiers from pasted responses that are not fixtures.

The coding agent produces these from the commands above. The developer checks them before posting.

## Integration points

The counterpart items on the Experience track are WI-04, Approver inbox and decisions, which shows the refusal, and WI-08, Notifications and delegates, which writes the delegate records.

- Crosses the boundary. The error envelope of `POST /reports/{id}/decisions`, with `error.rule` and `error.message`, as described in `contracts/openapi.yaml`, and the `delegate` record fields.
- Joint check. A refused decision shows the rule number in the web client error message, and the report state does not change. This item supplies the refusing call and the proof that the rows are unchanged.
- Handoff on close. Give WI-04 the list of rule numbers and message texts, and give WI-08 the date rule, inclusive of the first and last day, and the delegate fields the rules read.

## Out of scope

- Routing and the E_LIMIT answer at submit belong to WI-03.
- The delegate screen and `PUT /delegates` belong to WI-08.
- Audit events and the append only table belong to WI-07. A refusal changes nothing, so it writes no event.
- Showing, hiding or disabling buttons belongs to WI-04. The client is never the control.
- Changing a limit or a rule belongs to the finance policy team, through a new version of the ground truth.

## Watch out for

- Section 3.5 puts a line manager first on routes up to 25,000.00, while GOV-1.5 says a line manager counts only up to 5,000.00. Read "counts" as the approval that completes the report. Refuse an approve with GOV-1.5 when the last step approver's role limit is below the total, and always above 25,000.00. The ground truth gives the finance reviewer no limit, so use 25,000.00. Confirm with the finance policy team.
- Order of checks is not stated. Do E_NOT_FOUND, E_VALIDATION and E_STATE first, then the rules in ascending rule number, and return the first refusal. Say so in the pull request.
- A caller who is neither the current approver nor an active delegate is refused by a role check, which has no GOV rule. The ground truth gives no value for `rule` then, so settle it in a contract pull request.
- GOV-1.3 and a delegate. Treat the person who acts as the person in the step, so a delegate who holds another step of the same report is refused.
- Compare dates as UTC (Coordinated Universal Time) dates. Whether the last day is included is not stated, so include it and test it.
- A refusal must not leak. Keep amounts, names and comments out of the message and out of log lines (GOV-2.6).

## References

- [Section 3.5, Routing](../../ground-truth/architecture.md#35-routing)
- [Section 4.1, GOV-1](../../ground-truth/architecture.md#41-gov-1-approval-limits-and-separation-of-duties)
- [Section 7.1, REST API](../../ground-truth/architecture.md#71-rest-api)
- [WI-03 Approval routing engine](../m2-route-to-approvers/wi-03-routing-engine.md)
- [WI-04 Approver inbox and decisions](../m2-route-to-approvers/wi-04-approver-inbox.md)
- [WI-08 Notifications and delegates](wi-08-notifications-delegates.md)

## Decisions recorded

None yet.
