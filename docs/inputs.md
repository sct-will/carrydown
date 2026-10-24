# Inputs checklist

The ground-truth skill interviews you for these. You can prepare them first, or answer as it asks. If you do not know an answer, use the default or say "decide later" and the agent will mark it.

## Three required inputs

The agent will not draft a plan until it has these three.

1. **The ground truth.** One or more documents, as .docx or .md files.
2. **The people.** Each with a track, a percent allocation, a start date and days off. Percent allocation is the share of a person's working time that goes to this plan. The agent assumes 100 percent for everyone and asks you once to confirm: "I will assume everyone is allocated full time to this plan. Is that right, or should any of them be lower?" If someone works on the plan three days in five, say 60.
3. **The target.** A date, or a number of working weeks, plus any breaks given as date ranges.

In `plan.yaml` they appear as the documents under `project.ground_truth`, the `people` list with `allocation` (a whole number from 1 to 100, 100 if omitted), and a `target` block with `date` or `weeks`, next to the `breaks` list.

The sections below list these and the smaller inputs the interview also asks for.

## 1. Ground truth documents

| Ask yourself | Example | Default |
| --- | --- | --- |
| Which documents must the project obey? | An architecture document in Word. A requirements file. A business analyst note. A governance rule set. A development standard. | At least one. |
| Which wins when two disagree? | Governance, then standard, then architecture, then requirements, then notes. | That order. |
| Which version is final enough? | Version 0.3, reviewed on a given date. | Latest. |
| Are the sections numbered? | Headings like 3.2 and 4.1. | Number them. The agent can suggest numbering. |

Files can be `.docx` or `.md`. Give paths.

## 2. People and tracks

| Ask yourself | Example | Default |
| --- | --- | --- |
| Who does the work? | Two developers. | One to four people. |
| Which track does each own? | Workflow and Experience. | One track each. |
| Percent allocation? | 100, or 60 for three days in five. | 100 for everyone. The agent asks once to confirm. |
| Start dates and days off? | Start 2027-02-01. Off 2027-02-22. | Same start date, no days off. |
| Who advises and owns no items? | A policy owner. | None. |
| Their GitHub logins, if they should be assigned? | Leave empty for none. | Empty. |

## 3. The target and the breaks

| Ask yourself | Example | Default |
| --- | --- | --- |
| Target date or number of weeks? (required) | 2027-04-23, or 11 weeks of work. | Ask. |
| Breaks? (required, "none" is an answer) | A company offsite week, as a date range. | None. |
| Longest work unit? | Three weeks. | Three weeks. |
| Integration check rhythm? | Weekly, Fridays, 30 minutes. | Weekly. |

## 4. Repository and Epic

| Ask yourself | Example | Default |
| --- | --- | --- |
| Which repository holds the issues? | your-org/your-repo | Ask. |
| Does a parent Epic issue exist? | Issue 262, or none. | None. The script can create one. |
| Which labels exist? | Any you want kept. | Ignore. |
| Which branch holds the specification folder? | main | main |

## 5. Agents in use

Which agentic editors does the team use? Any editor or command line agent that reads Agent Skills works. The README lists the ones the installer knows. The developer skill is installed once per person per agent.

## 6. Demonstration audience

| Ask yourself | Example | Default |
| --- | --- | --- |
| Who watches the demonstrations? | The product owner and the head of operations. | The program. |
| How long can they give? | 45 minutes. | 45 minutes. |
| What must they see to say a milestone is done? | "A manager approves a report from the inbox." | Write it in their words. |

## 7. Program-owned boundary

| Ask yourself | Example | Default |
| --- | --- | --- |
| What does the program own and keep outside the plan? | Recruiting pilot teams. Approvals. Security review. Legal text. | None. |
| Which development items wait for these? | The pilot item waits for the pilot team. | None. |

## 8. Engineering conventions

| Ask yourself | Example | Default |
| --- | --- | --- |
| Test command? | `npm test` | Ask. |
| Lint command? | `npm run lint` | Ask. |
| Feature flag? | `MY_FEATURE_ENABLED`, off by default. | None. |
| Rules for secrets, logs or personal data? | No secrets in logs. | Same. |
| Pull request size or review rule? | Under 400 changed lines. | None. |

## A form to copy

```text
Ground truth files:
Wins on conflict:
Version:
People (name, track, percent allocation, start date, days off, GitHub login):
Advisors:
Target date or weeks:
Breaks (date ranges):
Longest work unit:
Repository:
Epic number or none:
Agents in use:
Demonstration audience and length:
What they must see:
Program-owned work and the items that wait for it:
Test command / lint command / feature flag:
Other rules for the definition of done:
```
