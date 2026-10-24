# WI-01 Service scaffold, flag and API contract

| Field | Value |
| --- | --- |
| Milestone | Milestone 1, Submit an expense report (`m1-submit-report`), work unit 1 |
| Track | Workflow |
| Target | Complete by 2027-02-03 (work unit 1, Submit an expense report, 2027-02-01 to 2027-02-12) |
| Checkpoint | 2027-02-05, Contract freeze |
| Demonstration | 2027-02-12, milestone 1 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Medium, about 3 days |
| Depends on | None |
| Unblocks | WI-02, WI-03 |
| Ground truth | Sections 3.1, 3.2, 5.1, 7.1 |

## Why this work item exists

Staff submit reports by email and spreadsheet, and nothing in the company can show who approved what (section 1.1). Two tracks must build the replacement at the same time, the Workflow track for the service and the Experience track for the web client. They can only do that if the interface between them is written down first (DS-1.4, section 5.1). This item is separate because every other item needs its pieces. It creates the service skeleton, the feature flag, the API contract for section 7.1, the first migration and a stub the web client can call on day one. Without it WI-02 cannot start, and WI-03 has no service to put the routing engine in.

## Outcome

- `src/server.js` starts the Expense API as one process and answers the health check in every configuration.
- `src/config/flags.js` reads `EXPENSE_APPROVALS_ENABLED`, off by default. With the flag off, every path except the health check returns the status 404 (section 3.6).
- `contracts/openapi.yaml` describes the nine endpoints of section 7.1, the decision request, the error envelope and the five error codes.
- `src/api/` holds a stub handler for each endpoint (reports.js, inbox.js, decisions.js, delegates.js, audit.js). Each returns a fixed answer that validates against the contract, so the Experience track can call it.
- `tests/contract/` holds the contract test runner, started by `npm run test:contract`.
- `package.json` defines `npm test`, `npm run test:contract`, `npm run lint` and `npm run migrate`.
- `migrations/` holds the first migration. It creates the six tables of section 3.3 and no logic.
- A continuous integration (CI) workflow runs lint, unit tests, contract tests and the migration on every pull request.

## Context for the agent

- The sample repository is new and empty. This item creates every file named in this specification. Nothing exists to read first.
- This item creates the layout the other items fill in. Top-level folders are `contracts/`, `src/`, `migrations/`, `web/src/` and `tests/`. Do not add others.
- The modules `src/routing/engine.js`, `src/rules/index.js`, `src/audit/writer.js`, `src/export/ledgerJob.js` and `src/notify/worker.js` are not created here. WI-03, WI-06, WI-07, WI-09 and WI-08 create them with their logic.
- The stub is the first version of the API handlers. It keeps data in memory and has no database logic. WI-03 and later items replace the stub answers with real behaviour, behind the same contract.
- The database is PostgreSQL (decision D1, section 8.2). API means application programming interface. UUID means universally unique identifier. Identifiers are UUIDs and timestamps are UTC (section 3.3).
- The flag is one process-wide setting in version 1 (decision D4). Read it once at start-up.
- The ground truth gives no path for the health check, no shape for "a page" and no rule for a missing `X-Employee-Id` header. See Watch out for.

## Contract

Fields used by this item. These are the interface sources the contract file must express word for word.

Section 7.1. All paths start with `/v1`. All bodies are JSON. The caller's identity comes from the gateway header `X-Employee-Id`, which the gateway sets and clients cannot forge.

| Method and path | Purpose | Success |
| --- | --- | --- |
| POST /reports | Create a draft report. | 201 with the report |
| GET /reports/{id} | Read a report with line items, receipts and steps. | 200 |
| PUT /reports/{id} | Replace the line items of a draft or returned report. | 200 |
| POST /reports/{id}/receipts | Upload a receipt (multipart form). | 201 with the receipt |
| POST /reports/{id}/submit | Submit a draft or returned report. | 202 with the state |
| GET /inbox | List the reports waiting for the caller, oldest first. | 200 with a page |
| POST /reports/{id}/decisions | Approve, reject or return. | 200 with the report |
| PUT /delegates | Create or replace the caller's delegate record. | 200 |
| GET /reports/{id}/audit | Read the audit trail (auditors only). | 200 with a page |

Decision request.

```json
{ "decision": "approve", "comment": "" }
```

`decision` is `approve`, `reject` or `return`. `comment` is required and not blank for `reject` and `return`.

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

Section 3.6. With the flag off the service starts, answers its health check and refuses every other request with the status 404.

Section 3.3 tables for the first migration. All identifiers are UUIDs. All timestamps are UTC. Amounts are integers in minor units (cents).

| Table | Key fields |
| --- | --- |
| report | id, submitter_id, state, base_total_cents, submitted_at, decided_at, version |
| line_item | id, report_id, spent_on, category, amount_cents, currency, base_amount_cents, merchant, note |
| receipt | id, report_id, line_item_id (optional), object_key, content_type, size_bytes, sha256 |
| approval_step | id, report_id, position, role, approver_id, state, decided_at, comment |
| delegate | id, approver_id, delegate_id, starts_on, ends_on |
| audit_event | id, occurred_at, actor_id, report_id, event_type, from_state, to_state, detail (JSON) |

## Implementation guide

1. Create `package.json` with the four commands of section 5.1 and the lint configuration. Check that `npm run lint` passes on the empty skeleton with no warnings.
2. Write `src/config/flags.js`. It reads `EXPENSE_APPROVALS_ENABLED` and is off unless the value is exactly `true`. Check it with `tests/flags.test.js` for unset, `true`, `false` and an unexpected value.
3. Write `src/server.js` with the health check and a gate that answers every other path with 404 when the flag is off. Check that the gate runs before routing, so no `/v1` path leaks.
4. Write `contracts/openapi.yaml` for the nine endpoints, the decision request, the envelope and the five codes, copying names and texts from the Contract section. Check that it loads in the contract test runner.
5. Write the stub handlers in `src/api/`. Each returns an example that validates against the contract and builds errors only through one envelope helper. Check each handler with a contract test in `tests/contract/`.
6. Add an example for each error code to the contract file, each reachable by a fixed report identifier, so the Experience track can build every error screen. Check that each one validates.
7. Write the first migration in `migrations/` for the six tables and wire `npm run migrate`. Check it with `tests/migrations.test.js` on an empty database.
8. Add the CI workflow in the location the repository host requires. It runs `npm run lint`, `npm test`, `npm run test:contract` and `npm run migrate`. Check that a pull request run is green.
9. Tell the Experience track the stub address and the fixed identifiers before the checkpoint. Run the joint check from the Integration points section.

## Acceptance criteria

- [ ] With the flag unset, `GET` on the health check answers 200 and `GET /v1/reports/{id}` answers 404 (`tests/flags.test.js`).
- [ ] With the flag off, every one of the nine endpoints of section 7.1 returns the status 404 (`tests/flags.test.js`).
- [ ] With the flag on, each of the nine endpoints answers with its success status from section 7.1 and a body that validates against `contracts/openapi.yaml` (`tests/contract/`).
- [ ] Each of the five error codes has a contract example with the status of the Contract table, and the stub returns it through the envelope (`tests/contract/`).
- [ ] No error response bypasses the envelope. A response with a missing `request_id` or `code` fails the contract test (DS-1.6).
- [ ] The first migration creates the six tables of section 3.3 with the listed fields, and runs on an empty database (`tests/migrations.test.js`, DS-1.5).
- [ ] `npm run lint` reports no warnings and `npm test` and `npm run test:contract` both pass in CI (DS-1.2, DS-1.3).
- [ ] The flag is off by default, and with it off nothing observable changes except the health check (DS-1.1).
- [ ] No fixture, log line or test holds a real name, email address, amount or receipt (DS-1.8, GOV-2.6).
- [ ] The pull request description lists these criteria and the proof for each, and each pull request stays under 400 changed lines where possible (DS-1.7).

## Evidence of completion

Demo. At the Contract freeze checkpoint on 2027-02-05, start the service with the flag off and show that the health check answers while `/v1/reports` returns 404. Restart with the flag on, create a draft through the stub and show the 201 body passing the contract test. The Experience track repeats the create call from the web client. The whole run takes under two minutes.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests, with the contract file in its own pull request (DS-1.4).
- `npm run test:contract` output, covering `tests/contract/`.
- `npm test` output, covering `tests/flags.test.js` and `tests/migrations.test.js`, and the `npm run lint` output with no warnings.
- The response body of the stub for POST /reports, and the 404 body with the flag off, with identifiers only.
- The table list from the first migration run on an empty database, with no data in it.

The coding agent produces these from the commands above. The developer checks them before posting.

## Integration points

The counterpart on the other track is WI-02, Report form and receipt upload (Experience). WI-03 is on the same track and also depends on this item.

- Crosses the boundary. `contracts/openapi.yaml` and the running stub. The Experience track builds against both, and treats the contract file as the only interface (DS-1.4).
- Joint check. This item's share of the Contract freeze check on 2027-02-05. The Workflow track starts the stub with the flag on, hands over its address, and shows that the response to a create-draft call validates against `contracts/openapi.yaml`. The web client makes the call.
- Handoff on close. Tell the Experience track the stub address, the fixed identifiers for each error code, the health check path, the shape of a page, and that later changes to the contract are their own pull request announced at the next checkpoint.

## Out of scope

- Routing, steps, the state machine and business day counting. WI-03 owns them.
- The approval limits and separation of duties checks. WI-06 owns them.
- The audit writer and the rule that the application account has insert and select rights only. WI-07 owns them. This item only creates the empty `audit_event` table.
- Sending email and the delegate screen (WI-08), and the nightly ledger job and its file (WI-09).
- Pilot recruitment and finance sign-off. The stakeholders own them.

## Watch out for

- The flag gate must sit in front of everything, including routes added later. A route added after this item that skips the gate breaks DS-1.1 and section 3.6.
- The health check path is not in the ground truth, and section 7.1 says all paths start with `/v1`. Put the health check outside `/v1`, name it in the contract file and in the pull request, and tell the Experience track.
- Section 7.1 says "a page" for the inbox and audit answers but gives no shape. Define one small shape in the contract, an `items` list and a `next_cursor`, and confirm it at the Contract freeze checkpoint.
- The ground truth does not say what happens without `X-Employee-Id`. Do not invent a rule. The stub uses a fixed example identifier and the question goes to the checkpoint.
- Migrations only move forward (section 3.6, DS-1.5). The "copy of the previous schema" test has nothing to copy until the second migration, so this migration needs the empty database test only.
- The accepted flag values are not given. This item treats only `true` as on, so a typing mistake leaves the feature off.

## References

- Ground truth. [3.1 Overview](../../ground-truth/architecture.md#31-overview), [3.2 Components](../../ground-truth/architecture.md#32-components), [3.3 Data model](../../ground-truth/architecture.md#33-data-model), [3.6 Deployment](../../ground-truth/architecture.md#36-deployment).
- Ground truth. [5.1 DS-1 Delivery standard](../../ground-truth/architecture.md#51-ds-1-delivery-standard), [7.1 REST API](../../ground-truth/architecture.md#71-rest-api).
- Unblocked items. [WI-02 Report form and receipt upload](wi-02-report-form.md), [WI-03 Approval routing engine](../m2-route-to-approvers/wi-03-routing-engine.md).

## Decisions recorded

None yet.
