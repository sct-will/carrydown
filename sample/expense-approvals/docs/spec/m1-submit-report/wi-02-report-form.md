# WI-02 Report form and receipt upload

| | |
| --- | --- |
| Milestone | Milestone 1, Submit an expense report (`m1-submit-report`), work unit 1 |
| Track | Experience |
| Target | Complete by 2027-02-10 (work unit 1, Submit an expense report, 2027-02-01 to 2027-02-12) |
| Checkpoint | 2027-02-12, Milestone 1 demonstration |
| Demonstration | 2027-02-12, milestone 1 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Medium, about 3 days |
| Depends on | WI-01 |
| Unblocks | WI-04 |
| Ground truth | Sections 2.1, 3.3, 6.2, 7.1 |

## Why this work item exists

Staff submit reports by email and spreadsheet today, and finance re-keys every line (section 1.1). Goal G1 is that a staff member submits a report with receipts from a web form (section 1.2). The form is a separate item because it is the first screen of the Experience track, it carries the edge cases of section 6.2 (a receipt that covers several lines, a report in mixed currencies, a returned report) and it must meet the Web Content Accessibility Guidelines (WCAG) 2.2 level AA from the start (NFR-3). Without it, milestone 1 has nothing a staff member can use, and the approver inbox (WI-04) has no submitted reports to show.

## Outcome

- A report page in `web/src/pages/` creates a draft, edits it and shows its state, reading and writing through POST /reports, GET /reports/{id} and PUT /reports/{id}.
- A line item editor in `web/src/components/` captures date, category, amount, currency, merchant and note for each line (FR-1), with errors shown next to the field named in the E_VALIDATION message.
- A receipt uploader in `web/src/components/` uploads PDF, PNG and JPEG files of at most 10 MB, up to 20 per report (FR-2), and lists what is attached.
- Drafts are saved without a submit and reopen with the same content (BA-1).
- A submit button calls POST /reports/{id}/submit and then shows the state, and a submitted report cannot be edited (FR-3).
- A report in mixed currencies shows each line in its own currency and in USD, and shows the report total as the service returns it (6.2 item 2).
- A returned report opens in the same form with the approver's comment shown, can be edited and submitted again (6.2 item 3).
- The page works with a keyboard and a screen reader, and passes a recorded WCAG 2.2 AA check (NFR-3).

## Context for the agent

- The sample repository is new and empty. WI-01 creates the service skeleton, `src/config/flags.js`, `contracts/openapi.yaml`, the stub handlers in `src/api/` and the contract test runner in `tests/contract/`. Read them first. Nothing else exists.
- This item creates everything under `web/src/` that the report form needs, and its tests in `tests/` and `tests/contract/`. It does not edit `src/`. A change to `contracts/openapi.yaml` is its own pull request (DS-1.4).
- Build against the stub that WI-01 provides, then against the service once the Workflow track replaces the stub answers for these five endpoints. The client code does not change between the two.
- API means application programming interface. The caller's identity is the gateway header `X-Employee-Id`, set by the gateway. The client never sets it and never sends it from page code.
- Amounts are integers in minor units (cents). The service converts to USD with a fixed rate table loaded as data (decision D3). The client holds no rates and does no currency arithmetic.
- The feature flag `EXPENSE_APPROVALS_ENABLED` is off by default. With it off the service answers 404 to every call, so the page must show a plain "not available" state instead of a broken form.
- Section 6.2 item 1 and the table in 3.3 make the receipt belong to the report, with an optional link to one line item.
- Verify at implementation how the multipart upload names the optional line item link. Read `contracts/openapi.yaml` and do not guess.

## Contract

Fields used by this item.

| Id | Requirement |
| --- | --- |
| FR-1 | A submitter creates a draft report with line items. Each line has a date, category, amount, currency, merchant and note. |
| FR-2 | A submitter attaches receipts to a report. Allowed types are PDF, PNG and JPEG. Each file is at most 10 MB. A report holds at most 20 receipts. |
| FR-3 | A submitter submits a draft. A submitted report cannot be edited, only returned by an approver. |
| NFR-3 | The web client meets WCAG 2.2 level AA. WCAG is the Web Content Accessibility Guidelines. |

Section 3.3 tables used by the form. All identifiers are UUIDs. All timestamps are UTC. Amounts are integers in minor units (cents).

| Table | Key fields |
| --- | --- |
| report | id, submitter_id, state, base_total_cents, submitted_at, decided_at, version |
| line_item | id, report_id, spent_on, category, amount_cents, currency, base_amount_cents, merchant, note |
| receipt | id, report_id, line_item_id (optional), object_key, content_type, size_bytes, sha256 |

Section 7.1 endpoints called by the form. All paths start with `/v1`. All bodies are JSON. The caller's identity comes from the gateway header `X-Employee-Id`, which the gateway sets and clients cannot forge.

| Method and path | Purpose | Success |
| --- | --- | --- |
| POST /reports | Create a draft report. | 201 with the report |
| GET /reports/{id} | Read a report with line items, receipts and steps. | 200 |
| PUT /reports/{id} | Replace the line items of a draft or returned report. | 200 |
| POST /reports/{id}/receipts | Upload a receipt (multipart form). | 201 with the receipt |
| POST /reports/{id}/submit | Submit a draft or returned report. | 202 with the state |

Error envelope used by every endpoint.

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
| E_LIMIT | 422 | The base total is above 25,000.00 and cannot be routed. |

Edge cases from section 6.2.

1. A single receipt can cover several line items, such as one hotel bill. The receipt belongs to the report, and the link to a line item is optional.
2. A report mixes currencies. Each line converts with the rate table. The report total is the sum of the converted lines, rounded half up to the cent after summing.
3. A returned report keeps its line items and receipts. The submitter edits and submits again, and the version number goes up.

BA-1. Submitters want to start a report on a phone and finish it on a laptop. Drafts must be saved without a submit.

## Implementation guide

1. Add a small API module in `web/src/` that wraps the five calls, reads the error envelope and raises one error type. Check it in `tests/contract/web-client-calls.test.js` by validating each request and response against `contracts/openapi.yaml`.
2. Build the report page and the line item editor with FR-1 fields, each with a visible label. Check labels and error text in `tests/report-form.test.js`.
3. Wire create and save. Create the draft with POST /reports, save with PUT /reports/{id}, and re-read the report after every save. Check reload and restore in `tests/report-form.test.js` (BA-1).
4. Build the receipt uploader. Check type, size and count in the browser before sending, then show the server message if the service still refuses. Check in `tests/receipt-upload.test.js`.
5. Add the optional link of a receipt to a line, and show unlinked receipts as belonging to the whole report. Check the several-lines case in `tests/receipt-upload.test.js` (6.2 item 1).
6. Add money display from integer cents, per currency, with the USD amount and the service total beside it. Check in `tests/money-display.test.js` (6.2 item 2).
7. Add the submit button. Disable the editor once the state is not Draft or Returned. Show E_STATE and E_LIMIT messages. Check in `tests/report-form.test.js`.
8. Show the return comment for a Returned report and allow edit and submit again. Check in `tests/report-form.test.js` (6.2 item 3).
9. Run the accessibility check, keyboard only and with a screen reader, and record the results. Check against the list in Acceptance criteria.

## Acceptance criteria

- [ ] Creating a draft calls POST /reports and the response validates against `contracts/openapi.yaml` (`tests/contract/web-client-calls.test.js`).
- [ ] A line has the six FR-1 fields, and an E_VALIDATION message shows next to the field it names (`tests/report-form.test.js`).
- [ ] A saved draft reopens with the same lines and receipts, and nothing is sent to submit (`tests/report-form.test.js`, BA-1).
- [ ] The uploader refuses a file type outside PDF, PNG and JPEG, a file over 10 MB and a 21st receipt before sending, and shows the service message when the service refuses (`tests/receipt-upload.test.js`, FR-2).
- [ ] A receipt with no line link stays in the report list and can cover several lines (`tests/receipt-upload.test.js`, 6.2 item 1).
- [ ] Amounts display from integer cents with no floating point sums, and the total shown is the service's `base_total_cents` (`tests/money-display.test.js`, 6.2 item 2).
- [ ] After submit the form is read only and the state shown comes from the response. E_STATE and E_LIMIT each show their message with the request identifier (`tests/report-form.test.js`, FR-3).
- [ ] A Returned report shows the approver's comment and can be edited and submitted again (`tests/report-form.test.js`, 6.2 item 3).
- [ ] With the flag off the page shows a "not available" state, and no console error or stack trace reaches the user (`tests/report-form.test.js`, DS-1.1).
- [ ] The recorded keyboard and screen reader walkthrough and the automated check show no WCAG 2.2 AA failure on the page (NFR-3).
- [ ] `npm test`, `npm run test:contract` and `npm run lint` pass. No fixture or log line holds a real name, amount or receipt (DS-1.2, DS-1.3, DS-1.8, GOV-2.6).

## Evidence of completion

Demo. At the Milestone 1 demonstration on 2027-02-12, open the report page with the flag on. Add two lines in two currencies, attach one PDF to the report with no line link, so it covers both lines, save, reload to show the draft again, then submit and show the state Submitted. Then repeat the first step using only the keyboard. The run takes under two minutes.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests, with no change to `contracts/openapi.yaml` unless it is its own pull request.
- `npm test` output for `tests/report-form.test.js`, `tests/receipt-upload.test.js` and `tests/money-display.test.js`.
- `npm run test:contract` output for `tests/contract/web-client-calls.test.js`.
- The accessibility record. Automated check output, the keyboard path taken and the screen reader notes, in plain text.
- Screenshots of the form with mixed currencies and of each error state, built from fixtures with no real names, amounts or receipts.

The coding agent produces these from the commands above. The developer checks them before posting.

## Integration points

The counterpart on the other track is WI-01, Service scaffold, flag and API contract (Workflow), which provides the contract and the stub this item calls.

- Crosses the boundary. `contracts/openapi.yaml` and the five endpoints of the Contract section, first on the stub and then on the service.
- Joint check. This item's share of the check at the Milestone 1 demonstration on 2027-02-12. The Experience track takes a report with one receipt from the form to the Submitted state and hands over the report id. The Workflow track shows the state change in the database.
- Handoff on close. Tell the Workflow track which calls the client makes and in what order, the byte limit used for 10 MB, and any gap found in the contract. For the inbox, tell the Experience owner of WI-04 which shared components exist in `web/src/components/` for money display and error messages.

## Out of scope

- The approver inbox, the decision dialog and decision errors. WI-04 owns them.
- Routing, steps and the 25,000.00 limit decision. WI-03 owns them. This item only shows E_LIMIT.
- Email notices and the delegate screen. WI-08 owns them.
- The governance checks of GOV-1. WI-06 owns them on the server.
- Card feeds, mileage calculation and conversion beyond the rate table (section 1.4).
- Paying the employee. The finance system does that.

## Watch out for

- The ground truth has no endpoint that lists a person's own reports. BA-1 asks to finish on another device, so the page address carries the report id and a person reopens the draft by that link. A list endpoint is a contract change in its own pull request, raised with the stakeholders.
- Never use floating point for money. Amounts are integer cents. Format by the currency's minor unit and verify at implementation how the service treats currencies without two decimals, because the ground truth only says cents.
- PUT /reports/{id} replaces the line items, so line item ids may change and a receipt link may point at an old id. Re-read the report after every save and never cache line ids.
- The client checks for type, size and count are for convenience. The service is the control. In the spirit of GOV-1.7, the web client is never the control. The ground truth does not say whether 10 MB means 10,000,000 or 10,485,760 bytes. Agree one value with the Workflow track and write it in the contract.
- Receipts may hold personal data (R4). Never log file names or contents, never keep file bytes in browser storage and never put them in error reports.
- POST /reports/{id}/submit answers 202 with the state, so routing may follow later. Do not show In approval before reading it. Show E_LIMIT when it arrives, with the offline exception process from section 3.5.
- No item in the plan says which Workflow work replaces the stub answers with stored data before 2027-02-12. The joint check needs a real state change in the database, so raise this at the Contract freeze checkpoint on 2027-02-05. This item has the four working days from 2027-02-05 to 2027-02-10.

## References

- Ground truth. [2.1 Functional requirements](../../ground-truth/architecture.md#21-functional-requirements), [3.3 Data model](../../ground-truth/architecture.md#33-data-model), [6.2 Edge cases the interviews surfaced](../../ground-truth/architecture.md#62-edge-cases-the-interviews-surfaced), [7.1 REST API](../../ground-truth/architecture.md#71-rest-api).
- Ground truth. [2.2 Quality requirements](../../ground-truth/architecture.md#22-quality-requirements) for NFR-3, and [6.1 What people asked for](../../ground-truth/architecture.md#61-what-people-asked-for) for BA-1.
- Dependency. [WI-01 Service scaffold, flag and API contract](wi-01-service-scaffold.md).
- Unblocked item. [WI-04 Approver inbox and decisions](../m2-route-to-approvers/wi-04-approver-inbox.md).

## Decisions recorded

None yet.
