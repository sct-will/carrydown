<!-- The body of issue 9 of sct-will/carrydown-sample, title "WI-03 Approval routing engine", as `gh issue view 9 --repo sct-will/carrydown-sample --json title,body` returned it on 28 November 2026 (issue last updated 2026-11-23T14:45:02Z). tests/sample-excerpts.mjs checks the issue excerpt on the sample page against this copy. -->

<!-- carrydown-managed:start -->
### Work item

Target completion on or before 2027-02-19. Checkpoint 2027-02-26, Routing meets inbox.

A submitted report must reach the right approvers without manual routing (goal G2 in section 1.2, requirement FR-4 in section 2.1). Section 3.5 turns the base total into an ordered list of approval steps. Section 3.4 lists the only state changes a report may make. Without this item a draft can be submitted but nobody can decide it, because no steps exist. It is its own item because the approver inbox (WI-04 (#10)), the rules module (WI-06 (#11)) and the audit writer (WI-07 (#12)) all read the steps and states that it creates.

### AI engineering notes

Specification: https://github.com/sct-will/carrydown-sample/blob/main/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md

Engineers' skill: https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev

Install it once following its README, then start this item by asking your coding agent to work on WI-03. The skill makes the agent read the specification above, the ground truth sections it cites and the project conventions before it changes code. You review every change.

Ground truth: Architecture document: Sections 3.4, 3.5, 7.1

### Depends on

- WI-01 (#7) Service scaffold, flag and API contract

### Acceptance criteria

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

### Evidence of completion

Demo. Submit three reports of 400.00, 4,000.00 and 6,000.00 USD (United States dollar) against the service, then call `GET /inbox` as each first approver. The responses show one, two and three steps. Run the 25,000.01 case to see E_LIMIT. It takes under two minutes with saved requests.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests, including any contract-only pull request.
- The suites `tests/routing.engine.test.js`, `tests/routing.states.test.js` and `tests/routing.business-days.test.js` with `npm test`, and `tests/contract/routing.contract.test.js` with `npm run test:contract`.
- A table of the `approval_step` rows for the three demo reports. Remove employee identifiers from any pasted response that is not a fixture.

The coding agent produces these from the commands above. The engineer checks them before posting.

### Integration points

The counterpart on the Experience track is WI-04 (#10), Approver inbox and decisions, and WI-02 (#8), Report form and receipt upload, which calls the submit endpoint.

- Crosses the boundary. `GET /inbox` and `POST /reports/{id}/decisions` in `contracts/openapi.yaml`, with the step states and error codes in it.
- Joint check. A submitted report produces the approval steps of section 3.5, and the inbox contract returns them for the first approver. This item shows the stored steps and the inbox response for the demo reports.
- Handoff on close. Tell the Experience owner the step role names, the step states, the page shape of the inbox and the fact that the rules check is a placeholder until WI-06 (#11).

### Definition of done

- [ ] Every acceptance criterion is proven by a test or a recorded check named in the pull request.
- [ ] The work landed on main behind the EXPENSE_APPROVALS_ENABLED flag.
- [ ] `npm test` and `npm run lint` pass.
- [ ] Contract tests pass with `npm run test:contract`, and a change to `contracts/openapi.yaml` is its own pull request.
- [ ] Secrets and personal data never appear in code, tests, logs or fixtures.
- [ ] The "Decisions recorded" section of the specification is updated if the implementation departed from it.
- [ ] The item is demonstrated at its checkpoint with the joint check run.
- [ ] The closing comment on this issue follows the template in the specification folder README (Demo, Evidence, Decisions, Handoff) with every artifact listed above attached.
<!-- carrydown-managed:end -->

<!-- carrydown:WI-03 -->

