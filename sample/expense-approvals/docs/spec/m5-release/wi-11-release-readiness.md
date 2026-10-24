# WI-11 Release readiness and runbook

| | |
| --- | --- |
| Milestone | Milestone 5, Release (`m5-release`), work unit 5 |
| Track | Experience |
| Target | Complete by 2027-04-21 (work unit 5, Release, 2027-04-12 to 2027-04-23) |
| Checkpoint | 2027-04-23, Release |
| Demonstration | 2027-04-23, milestone 5 demonstration (acceptance criteria in `milestone.md` in this folder) |
| Size | Medium, about 3 days |
| Depends on | WI-08, WI-09; program input: finance sign-off on the export format and retention period |
| Unblocks | None |
| Ground truth | Sections 5.1, 8.1 |

## Why this work item exists

The service goes to production behind the flag `EXPENSE_APPROVALS_ENABLED` (sections 3.6 and 5.1), and operations will run it. Until this item, nothing shows that the finished system meets the quality requirements for speed (NFR-1), accessibility (NFR-3) and recovery (NFR-5), or that the responses to the five risks of section 8.1 are in place. This is its own item because it can only start when the feature items are done, and it needs the web client, the export job and a staging environment together. Without it, operations has no written way to start, stop, restore or switch the feature, and the release gate of milestone 5 has no proof behind it.

## Outcome

- `docs/runbook.md` holds the runbook with six procedures. They are start, stop, flag on and off, nightly job failure, re-route request and restore from backup.
- A rehearsal record in `docs/runbook.md` shows one full pass in staging with the flag on, from the form to the nightly ledger file.
- A load check script in `tests/` sends 200 requests per second to staging, and its recorded result shows the 95th percentile against the 400 ms target (NFR-1).
- An accessibility record covers every page of the web client in `web/src/` against WCAG 2.2 level AA (NFR-3).
- A restore record shows the recovery point and the recovery time measured against NFR-5.
- A risk review table in `docs/runbook.md` has one row for each of R1 to R5, with the evidence that its response exists.
- The state of the finance sign-off on the export format and retention period is written in the runbook and in the checkpoint comment.
- Defects found are fixed in the web client where small, or raised as issues for the owning item.

## Context for the agent

- The sample repository is new and empty. By this item the earlier items have created the service (WI-01), the report form (WI-02), the routing engine (WI-03), the inbox (WI-04), the rules module (WI-06), the audit writer (WI-07), the notification worker and the delegate screen (WI-08) and the ledger job (WI-09). Read those specifications first.
- This item creates `docs/runbook.md`, the load check script under `tests/` and the records. It does not add product features.
- WCAG means the Web Content Accessibility Guidelines. The recovery point objective (RPO) is 15 minutes and the recovery time objective (RTO) is 4 hours (NFR-5).
- A program input is something an item needs from work the plan does not schedule, owned outside the team. This item has one, the finance sign-off on the export format and retention period. The stakeholders obtain it. This item only records whether it has arrived.
- The three environments are test, staging and production (section 3.6). The rehearsal, load check and restore run in staging. Production is changed only by operations, with the runbook, after the checkpoint passes.
- The service is one container in all three environments. Migrations only move forward, so a failed release is handled by turning the flag off, not by undoing a migration.
- The ground truth does not give the load duration, the request mix, the backup tool or how operations pages someone. Verify each at implementation with the platform engineering team and record the answer.
- Use fixtures. No real names, amounts, comments or receipts enter the rehearsal data, the load data or the records (DS-1.8).

## Contract

Fields used by this item. These are the targets and rules the checks must prove.

| Id | Requirement |
| --- | --- |
| NFR-1 | The 95th percentile response time of the API is under 400 ms at 200 requests per second. |
| NFR-3 | The web client meets WCAG 2.2 level AA. WCAG is the Web Content Accessibility Guidelines. |
| NFR-5 | The recovery point objective is 15 minutes and the recovery time objective is 4 hours. |

Section 3.6. The service runs as one container behind the company gateway, in three environments: test, staging and production. Database migrations only move forward. The export job runs at 02:00 UTC and writes to the ledger drop folder. The whole feature sits behind the flag EXPENSE_APPROVALS_ENABLED (section 5.1). With the flag off the service starts, answers its health check and refuses every other request with the status 404.

DS-1.1. All new behaviour sits behind EXPENSE_APPROVALS_ENABLED, off by default. With the flag off, nothing observable changes except the health check.

Section 7.3, first paragraph. One file per night, named `expenses-YYYYMMDD.csv`, with a second file `expenses-YYYYMMDD.sha256` that holds the SHA-256 checksum of the first. One row per approved line item of every report that moved to Approved since the last export. After writing, the job moves those reports to Exported.

GOV-2.4. Reports, line items, approval steps and audit events are kept for 7 years from the decision date. Receipt files are kept as long as their report.

Section 8.1 risks to review.

| Id | Risk | Response |
| --- | --- | --- |
| R1 | The reporting line data is out of date, so routing picks the wrong manager. | Routing reads the line once at submit time and records it. Finance can ask for a re-route. |
| R2 | Managers ignore reminders and reports pile up. | Escalation after 5 business days (section 3.5). The pilot measures time to decision. |
| R3 | The export format changes after finance review. | The file format sits in one module and a contract test. The program owns the sign-off. |
| R4 | Receipts hold personal data. | Receipt store keys are random. Receipts are never logged or put in events (GOV-2). |
| R5 | The two tracks drift on the API. | Contracts first (DS-1.4) and a joint check at every checkpoint. |

## Implementation guide

1. Draft `docs/runbook.md` with the six procedures. For each, give the trigger, the steps, who acts, the expected result and how to confirm it. Check that each step uses only commands and flags named in the repository.
2. Rehearse start, stop and the flag in staging. Confirm that with the flag off only the health check answers and everything else returns 404, then turn it on and repeat the calls. Record the result.
3. Run the full release rehearsal in staging with the flag on. Start by 2027-04-19 so a 02:00 UTC export run falls inside it. Create, submit, approve in order, read the notice and the audit trail, and open the next file and its checksum.
4. Fail the nightly job on purpose in staging, follow the runbook to run it again, and confirm no row is duplicated. Record the result.
5. Write and run the load check script in `tests/` at 200 requests per second against staging. Record the request mix, the duration, the count and the 95th percentile.
6. Check every page of the web client against WCAG 2.2 AA with an automated tool, keyboard only and a screen reader. Fix small defects and open issues for the rest. Record the result.
7. Restore staging from backup to a point inside the RPO, time it against the RTO, and check that reports, approval steps and the audit table are present. Record both times.
8. Review R1 to R5 one by one. For each, record the evidence that the response works and the owner of any remaining risk.
9. Record the finance sign-off state. Run `npm test`, `npm run test:contract` and `npm run lint` on the release candidate. Give the runbook to the Workflow track for review.

## Acceptance criteria

- [ ] `docs/runbook.md` has the six procedures, and each was followed once in staging with the result recorded (rehearsal record).
- [ ] The release rehearsal passes in staging with the flag on, from a new report to the nightly file and its `.sha256` file (rehearsal record, checkpoint check).
- [ ] With the flag off in staging only the health check answers and every other path returns 404 (rehearsal record, DS-1.1).
- [ ] The load check records a 95th percentile under 400 ms at 200 requests per second (load check output, NFR-1).
- [ ] The accessibility record shows no open WCAG 2.2 AA failure on any page of the web client (accessibility record, NFR-3).
- [ ] The restore record shows a recovery point of at most 15 minutes and a recovery time under 4 hours (restore record, NFR-5).
- [ ] A failed nightly run was repeated without duplicate rows, and the runbook says how (rehearsal record).
- [ ] The re-route procedure says what version 1 does today and does not invent a path (runbook review by the Workflow track).
- [ ] Risks R1 to R5 each have a row with evidence and an owner for any residue (risk review table).
- [ ] The finance sign-off state is written in the runbook and the checkpoint comment (checkpoint comment).
- [ ] `npm test`, `npm run test:contract` and `npm run lint` pass on the release candidate, and no secret, name, amount or receipt is in any record (DS-1.2, DS-1.3, DS-1.8, GOV-2.6).

## Evidence of completion

Demo. At the Release checkpoint on 2027-04-23, show the rehearsal record as one table of pass or fail rows. Then, in staging with the flag on, submit a report, approve it, open its audit trail and show the nightly file with its checksum. Switch the flag off and show the 404. The run takes under two minutes.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests for `docs/runbook.md`, the load script and any accessibility fixes.
- `npm test`, `npm run test:contract` and `npm run lint` output for the release candidate.
- The load check output with request count, duration and the 95th percentile, and the accessibility record by page.
- The rehearsal, restore and risk review tables, with identifiers only and no names, amounts or receipts.
- A line stating whether the finance sign-off has arrived, as told by the stakeholders.

The coding agent produces these from the commands above. The developer checks them before posting.

## Integration points

The counterpart on the other track is WI-09, Ledger export job (Workflow). Its job, its file and its failure handling are what the runbook describes.

- Crosses the boundary. The nightly job and ledger drop folder procedures, and the backup and restore facts. The Workflow track supplies them and the Experience track writes them into the runbook.
- Joint check. This item's share of the Release check on 2027-04-23. The Experience track runs the rehearsal through the web client in staging with the flag on and records that it passes. The Workflow track shows the file, the checksum and the audit events from the same run.
- Handoff on close. Give the Workflow track the runbook for review before it goes to operations. List any risk with a residue, and say whether the finance sign-off has arrived.

## Out of scope

- New features, and fixes to defects that need design work. Raise an issue for the owning item.
- The finance sign-off and the decision to turn the production flag on. The stakeholders own them.
- Monitoring and alerting for the 99.5 percent availability target (NFR-2). The platform engineering team owns them.
- Push delivery of the inbox. Decision D2 puts it after version 1.
- Pilot readout work and the pilot measurements. The stakeholders and the pilot checkpoint own them.
- Changes to `contracts/openapi.yaml`. They are their own pull request (DS-1.4).

## Watch out for

- Section 3.5 rule 4 says steps do not change after routing except by escalation, and R1 says finance can ask for a re-route. Section 7.1 has no re-route endpoint. The ground truth does not define the path, so the runbook says what the service does today and names the stakeholders as the owners of the gap.
- The business analyst note asks for a reminder after 2 business days and section 3.5 says 3. The work items use 3. The runbook and the R2 review must say 3, and the next version of the architecture document should settle the number.
- Do not replace the 02:00 UTC run with a manual run in the rehearsal. It needs the real schedule once, so start early enough (see Implementation guide step 3).
- NFR-5 covers the database. The ground truth is silent on backups of the receipt store. Ask the platform engineering team and record the answer in the restore record.
- The load check must use fixture data. A run that creates thousands of reports must not leave Approved reports that the next staging export writes into the ledger drop folder.
- Turning the flag off does not remove data. The runbook must say this, and that migrations are never undone.
- The flag is a single process-wide setting (decision D4), read once at start-up. The runbook must say that a change needs a restart.

## References

- Ground truth. [5.1 DS-1 Delivery standard](../../ground-truth/architecture.md#51-ds-1-delivery-standard), [8.1 Risks](../../ground-truth/architecture.md#81-risks), [3.6 Deployment](../../ground-truth/architecture.md#36-deployment), [2.2 Quality requirements](../../ground-truth/architecture.md#22-quality-requirements).
- Ground truth. [7.3 Ledger export file](../../ground-truth/architecture.md#73-ledger-export-file), [4.2 GOV-2 Audit and retention](../../ground-truth/architecture.md#42-gov-2-audit-and-retention), [3.5 Routing](../../ground-truth/architecture.md#35-routing).
- Dependency. [WI-08 Notifications and delegates](../m3-enforce-policy/wi-08-notifications-delegates.md).
- Dependency. [WI-09 Ledger export job](../m4-pilot/wi-09-ledger-export.md).
- Earlier items the checks cover. [WI-01](../m1-submit-report/wi-01-service-scaffold.md), [WI-02](../m1-submit-report/wi-02-report-form.md), [WI-04](../m2-route-to-approvers/wi-04-approver-inbox.md).

## Decisions recorded

None yet.
