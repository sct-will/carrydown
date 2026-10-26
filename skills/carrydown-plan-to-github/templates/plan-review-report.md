# Second-pass plan review

## Review record

| Input | Reviewed version or evidence | Limit or assumption |
| --- | --- | --- |
| Ground truth and precedence | Record paths, versions and source sections. | Record missing or conflicting inputs. |
| Confirmed constraints and decisions | Record the owner's confirmation and planning mode. | Distinguish defaults and derived values. |
| Staffing context | Record supplied skills and work preferences, or state that default assignment was used. | Missing optional staffing context is not a limit or finding. |
| Plan and specification set | Record revision and paths. | Record incomplete artifacts. |
| Checker and schedule reports | Record commands, results and date. | A clean check does not prove source coverage. |
| Published artifacts and engineers' skill | Record actual identifiers and versions, or not yet published. | Record unavailable artifacts. |
| Review context | Record fresh context or a separate pass in the current context. | Record the limits of independence. |

## Staffing match

When skills or preferences were supplied, use this table. Otherwise state that default assignment was used and omit the table. Missing optional staffing context is valid. Remove these instructions when writing the report.

| Engineer | Supplied skills | Work preferences | Proposed track and work | Match reasoning | Risk or tradeoff |
| --- | --- | --- | --- | --- | --- |

## Scope coverage

Use one row per actionable source obligation or an explicitly traceable group. Include a row for each review area in the prompt. Link the work item and acceptance evidence. Record exclusions only with an owner decision. Remove these instructions when writing the report.

| Source obligation or review area | Work items and acceptance evidence | Result | Evidence and reasoning or review limit |
| --- | --- | --- | --- |

## Findings and risk

Use stable identifiers such as R-01. Ratings are high, medium or low, with reasons. Give facts and references that another reader can check. Remove these instructions when writing the report.

| Review identifier and type | Affected work and source evidence | Finding and reasoning | Likelihood and impact with reasons | Confidence | Proposed repair and effects |
| --- | --- | --- | --- | --- | --- |

## Decisions, repairs and verification

Do not mark a finding fixed until the repair and its effects have been checked. External work can remain publication pending after local verification. Remove these instructions when writing the report.

| Review identifier | Owner decision and reason | Changed files or external identifiers | Verification evidence | Status and remaining risk |
| --- | --- | --- | --- | --- |

## Review outcome

Record the finding counts, unresolved decisions, accepted residual risks and whether publication is pending. If there are no findings, say so with the scope and limits of the completed review. Do not claim that agent review guarantees correctness.
