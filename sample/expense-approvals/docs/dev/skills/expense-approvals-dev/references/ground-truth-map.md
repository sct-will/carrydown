# Ground truth map

The source sections inside the approved contexts of this project, by source id and section number. Read a section through the approved context of a work item, `docs/context/<id>.md`, after `scripts/check_context.py <ID>` passes. The sources themselves are not in this repository, and this skill does not look for them. When sources conflict, the earlier source in this file wins unless the plan owner recorded another decision.

## Sources and precedence

| Precedence | Source id | Document |
| --- | --- | --- |
| 1 | architecture | Architecture document |

## Architecture document (`architecture`)

| Section | Heading | In the approved context of |
| --- | --- | --- |
| 2.1 | Functional requirements | WI-02, WI-04 |
| 3.1 | Overview | WI-01 |
| 3.2 | Components | WI-01 |
| 3.3 | Data model | WI-02, WI-07 |
| 3.4 | Report lifecycle | WI-03, WI-04 |
| 3.5 | Routing | WI-03, WI-06 |
| 3.6 | Deployment | WI-09 |
| 4.1 | GOV-1 Approval limits and separation of duties | WI-06 |
| 4.2 | GOV-2 Audit and retention | WI-07, WI-09 |
| 5.1 | DS-1 Delivery standard | WI-01, WI-11 |
| 6.1 | What people asked for | WI-04, WI-08 |
| 6.2 | Edge cases the interviews surfaced | WI-02, WI-08 |
| 7.1 | REST API | WI-01, WI-02, WI-03, WI-04, WI-06 |
| 7.2 | Notification event | WI-08 |
| 7.3 | Ledger export file | WI-09 |
| 8.1 | Risks | WI-11 |

## By work item

| Id | Work item | Approved context | Sections |
| --- | --- | --- | --- |
| WI-01 | Service scaffold, flag and API contract | `docs/context/wi-01.md` | architecture 3.1, 3.2, 5.1, 7.1 |
| WI-02 | Report form and receipt upload | `docs/context/wi-02.md` | architecture 2.1, 3.3, 6.2, 7.1 |
| WI-03 | Approval routing engine | `docs/context/wi-03.md` | architecture 3.4, 3.5, 7.1 |
| WI-04 | Approver inbox and decisions | `docs/context/wi-04.md` | architecture 2.1, 3.4, 6.1, 7.1 |
| WI-06 | Approval limits and separation of duties | `docs/context/wi-06.md` | architecture 3.5, 4.1, 7.1 |
| WI-07 | Audit log and retention | `docs/context/wi-07.md` | architecture 3.3, 4.2 |
| WI-08 | Notifications and delegates | `docs/context/wi-08.md` | architecture 6.1, 6.2, 7.2 |
| WI-09 | Ledger export job | `docs/context/wi-09.md` | architecture 3.6, 4.2, 7.3 |
| WI-11 | Release readiness and runbook | `docs/context/wi-11.md` | architecture 5.1, 8.1 |
