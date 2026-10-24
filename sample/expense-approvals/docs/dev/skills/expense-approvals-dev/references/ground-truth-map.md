# Ground truth map

Headings of `docs/ground-truth/architecture.md` with GitHub anchors and line numbers, then the sections each work item cites. Regenerating the rendering may move line numbers. Run `generate_dev_skill.py` again then.

## By heading

| Line | Level | Heading | Anchor |
| --- | --- | --- | --- |
| 42 | ## | 1. Context and goals | `#1-context-and-goals` |
| 44 | ### | 1.1 Problem | `#11-problem` |
| 48 | ### | 1.2 Goals | `#12-goals` |
| 58 | ### | 1.3 Users and roles | `#13-users-and-roles` |
| 68 | ### | 1.4 Scope boundary | `#14-scope-boundary` |
| 72 | ## | 2. Requirements | `#2-requirements` |
| 74 | ### | 2.1 Functional requirements | `#21-functional-requirements` |
| 89 | ### | 2.2 Quality requirements | `#22-quality-requirements` |
| 99 | ## | 3. Architecture | `#3-architecture` |
| 101 | ### | 3.1 Overview | `#31-overview` |
| 114 | ### | 3.2 Components | `#32-components` |
| 127 | ### | 3.3 Data model | `#33-data-model` |
| 140 | ### | 3.4 Report lifecycle | `#34-report-lifecycle` |
| 155 | ### | 3.5 Routing | `#35-routing` |
| 173 | ### | 3.6 Deployment | `#36-deployment` |
| 177 | ## | 4. Governance rules | `#4-governance-rules` |
| 179 | ### | 4.1 GOV-1 Approval limits and separation of duties | `#41-gov-1-approval-limits-and-separation-of-duties` |
| 191 | ### | 4.2 GOV-2 Audit and retention | `#42-gov-2-audit-and-retention` |
| 203 | ## | 5. Development standard | `#5-development-standard` |
| 205 | ### | 5.1 DS-1 Delivery standard | `#51-ds-1-delivery-standard` |
| 218 | ## | 6. Business analyst note | `#6-business-analyst-note` |
| 222 | ### | 6.1 What people asked for | `#61-what-people-asked-for` |
| 233 | ### | 6.2 Edge cases the interviews surfaced | `#62-edge-cases-the-interviews-surfaced` |
| 242 | ## | 7. Interfaces | `#7-interfaces` |
| 244 | ### | 7.1 REST API | `#71-rest-api` |
| 289 | ### | 7.2 Notification event | `#72-notification-event` |
| 308 | ### | 7.3 Ledger export file | `#73-ledger-export-file` |
| 325 | ## | 8. Risks and decisions | `#8-risks-and-decisions` |
| 327 | ### | 8.1 Risks | `#81-risks` |
| 337 | ### | 8.2 Decisions | `#82-decisions` |

## By work item

| Id | Work item | Ground truth sections |
| --- | --- | --- |
| WI-01 | Service scaffold, flag and API contract | Sections 3.1, 3.2, 5.1, 7.1 |
| WI-02 | Report form and receipt upload | Sections 2.1, 3.3, 6.2, 7.1 |
| WI-03 | Approval routing engine | Sections 3.4, 3.5, 7.1 |
| WI-04 | Approver inbox and decisions | Sections 2.1, 3.4, 6.1, 7.1 |
| WI-06 | Approval limits and separation of duties | Sections 3.5, 4.1, 7.1 |
| WI-07 | Audit log and retention | Sections 3.3, 4.2 |
| WI-08 | Notifications and delegates | Sections 6.1, 6.2, 7.2 |
| WI-09 | Ledger export job | Sections 3.6, 4.2, 7.3 |
| WI-11 | Release readiness and runbook | Sections 5.1, 8.1 |
