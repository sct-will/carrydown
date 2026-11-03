# Inputs checklist

This optional checklist helps you prepare for the planning interview. The ground-truth skill interviews you for these inputs. You can prepare them first, or answer as it asks. Use defaults or mark undecided details as "decide later".

## Three inputs

0. **Who may see the documents.** Required, and asked first. One question: "Can everyone who can read this repository see all of these documents and your staffing notes?" See [section 0](#0-who-may-see-the-documents) below.
1. **The ground truth.** Required. Keep one or more source files where you keep them now, and give the agent their paths. You do not need to copy them into the project. Word, Markdown and plain text render directly. The agent can inspect readable PDF, image and other files and create reviewed Markdown renderings. It reports unreadable files and continues when at least one intended source can be processed.
2. **Your project constraints.** Optional, in any combination: the people, each with a track, a percent allocation, a start date and days off, and the target, a date or a number of working weeks, plus breaks as date ranges. You may also give engineers' skills and work preferences. The agent asks one question: "What constraints do you have? The people, the target date or weeks, both, or neither for now."

Percent allocation is the share of a person's working time that goes to this plan. The agent assumes 100 percent for everyone and asks you once to confirm: "I will assume everyone is allocated full time to this plan. Is that right, or should any of them be lower?" If someone works on the plan three days in five, say 60.

The rule: give both and the plan fits them. Give one and the agent backs into the other. Give neither and it proposes a default and asks. There are four modes.

- **Fit.** People and target given. The plan fits them, and the checker flags over-capacity and target misses.
- **Derive the date.** People given, no target. The plan's end date is the critical path end. It is written to `plan.yaml` as `target: {date: ..., derived: true}`.
- **Derive the capacity.** Target given, no people. The agent proposes tracks and a head count at 100 percent that meets the date, as `people` entries with `derived: true` and placeholder names such as "Engineer 1". Replace them with real people.
- **Neither given.** No people and no target. The agent proposes a default team of two tracks, "Engineer 1" and "Engineer 2" at 100 percent, and a derived date, marks both as derived, and asks you to confirm or to give real constraints.

A worked example of Derive the date, produced by running the checker on the sample with its target removed, is in [derive-the-date.md](derive-the-date.md).

Each work item gets a size, written as a word and a number of days, for example "Small, about 2 days" or "Medium, about 3 days". The agent proposes the sizes. The checker reads the number after "about" for the load table, so keep that form if you edit `plan.yaml` yourself.

In your working `plan.yaml` the inputs appear under `sources`, in precedence order. Each entry records an id, a display name, the original file, the rendered path, the version, the status, the coverage limit, the use and the classification (`repo-readers`, `restricted` or `public`), with the digests of the original and the rendering. The plan that is released and committed keeps only the id, the name and the version of each source, so a clean clone needs neither the original nor the rendering. `project.ground_truth` is optional and is kept only for older tools. Work items use `source_refs` to cite sections from one or more sources. Tracks and specialized items can record `skill_needs`. The optional `target` block holds `date` or `weeks`, next to the `breaks` list.

The `people` list in `plan.yaml` holds an id and a track for each person, and nothing else. Everything personal goes to `people.yaml` in your private workspace, with the same ids: the name, the GitHub login, `allocation` (a whole number from 1 to 100, 100 if omitted), the start date, days off, and the optional `skills`, `preferences` and `assignment_rationale`. The agent writes that file for you.

Skills and preferences are advisory. Leave them out when they are unknown or irrelevant. The agent still assigns work with the existing rules for tracks, capacity, dependencies, theme continuity and reduced handoffs. When supplied, they guide a proposed best match. Unclear or incomplete staffing context never stops or fails the plan.

Two more things come out of the planning conversation, and it helps to think about them. Themes: the parts of the system each track touches, in a few words each, such as "web client" or "export job". Each item gets one, so the plan can keep a person on one part at a time. Rationale: why each milestone holds its items, what the engineers show together at its demonstration, and why each track's items are in their order. The agent drafts these with you and writes them into `plan.yaml` as `theme`, `rationale`, `joint_demonstration` and `order_rationale`. The checker fails a plan without the rationale.

The sections below list these and the smaller inputs the interview also asks for.

## 0. Who may see the documents

| Ask yourself | Example | Default |
| --- | --- | --- |
| Can everyone who can read this repository see all of these documents and your staffing notes? | Yes: a team whose documents are approved for everyone with repository access. No: a governance policy only the owner and two reviewers may read. | Ask. There is no default, and the answer is never guessed. |
| If no, which documents are restricted? | The company governance policy. The architecture document is shareable. | All of them. |
| If no, who may approve that a document is shared with the repository's readers? | Two GitHub logins. | You. Collect logins, never email addresses. |
| If no, are the raw inputs kept after a release? | Keep them in the private workspace. | Kept in the workspace, never in the repository. If you choose deletion, the export deletes the files in the workspace's `sources/` folder after the release and records what it deleted. Copies elsewhere stay. |

The answer picks the path:

| | Yes | No |
| --- | --- | --- |
| Where drafting happens | In the repository, as before. | In the private workspace on your machine. |
| Where the documents can be | Where you keep them, or an ignored local `docs/source/`. | In your authorized document system, or in the workspace. Never copied into the project folder. |
| Local files that are not committed | `.carrydown/local.yaml` (the pointer to your private workspace), `.carrydown/cache/` and `people.yaml`, all ignored by git. | The same. |
| What you need beyond the two skills | Nothing. | The organization pieces in [organization setup for private drafting](setup.md#organization-setup-for-private-drafting) and a private staging repository. |
| Checks before you start | None. | `python3 scripts/workspace.py doctor --root .` (offline) and `python3 scripts/release.py doctor --root .` (live). Each prints a short table of what is verified, not verifiable or missing, and a missing item names its reason code. |

If a document is already inside the project, the agent reports it and does not call it safe. `python3 scripts/release.py inventory --root .` lists tracked originals, renderings and staffing fields and whether they are in git history. An ignore rule keeps new files out of git and does not erase history. See [the enterprise security questions](enterprise-security.md).

## 1. Ground truth documents

| Ask yourself | Example | Default |
| --- | --- | --- |
| Which files must the project obey? | An architecture document in Word. Requirements in Markdown. Governance rules in PDF. A development standard in plain text. A diagram in PNG. | At least one readable source. |
| Which wins when two disagree? | Governance, then standard, then architecture, then requirements, then notes. | That order. |
| Which version is final enough? | Version 0.3, reviewed on a given date. | Latest. |
| Are the sections numbered? | Headings like 3.2 and 4.1. | Number them. The agent can suggest numbering. |
| Did every file render reliably? | The policy PDF rendered. One low-resolution image is recorded as unreadable. | Review extractions and record every coverage limit. |

Give the paths of the files where they are. Do not copy a confidential document into the project folder, and use an ignored `docs/source/` if you want a local copy. Direct rendering accepts `.docx`, `.md`, `.markdown` and UTF-8 `.txt`. The agent-reviewed extraction path covers readable PDF, image and other formats. A Word document's header and footer markings, hidden text and tracked changes are shown to you before anything is rendered into a file you will share.

## 2. People and tracks

Everything you answer here is saved to `people.yaml` in your private workspace. The plan keeps only ids and tracks.

| Ask yourself | Example | Default |
| --- | --- | --- |
| Who does the work? | Two engineers. | One to four people. |
| Which track does each own? | Workflow and Experience. | One track each. |
| Skills that should influence the match? | Python services, accessible interfaces, database design. | Optional. Use the default assignment approach when absent. |
| Work preferences that should influence the match? | Contract design, user-facing workflows. | Optional soft guidance. |
| Which parts of the system does each track touch? | Web client, notification worker, expense service, export job. | Ask. They become the themes. |
| Percent allocation? | 100, or 60 for three days in five. | 100 for everyone. The agent asks once to confirm. |
| Start dates and days off? | Start 2027-02-01. Off 2027-02-22. | Same start date, no days off. |
| Who advises and owns no items? | Someone from security, or the author of a policy. | None. |
| Their GitHub logins, if they should be assigned? | Leave empty for none. | Empty. |

## 3. The target and the breaks

| Ask yourself | Example | Default |
| --- | --- | --- |
| Target date or number of weeks? (optional) | 2027-04-23, or 11 weeks of work. | Ask. |
| Breaks? | A company offsite week, as a date range. | None. |
| Longest work unit? | Three weeks. | Three weeks. |
| Integration check day and length? The plan sets the date of each checkpoint. | Fridays, 30 minutes. | Friday, 30 minutes. |

## 4. Repository and Epic

| Ask yourself | Example | Default |
| --- | --- | --- |
| Which repository holds the issues? | your-org/your-repo | Ask. |
| Does a parent Epic issue exist? | Issue 262, or none. | None. The script can create one. |
| Which labels exist? | Any you want kept. | Ignore. |
| Which branch holds the specification folder? | main | main |

## 5. Agents in use

Which agentic editors do the engineers use? Any editor or command line agent that reads Agent Skills works. The setup guide contains the agent install list. The engineers' skill is installed once per engineer per agent.

## 6. Demonstration audience

| Ask yourself | Example | Default |
| --- | --- | --- |
| Who are the stakeholders, the people accountable for the outcome, who watch the demonstrations and decide pass or fail? | The product manager and the head of operations. | Ask. |
| How long can they give? | 45 minutes. | 45 minutes. |
| What must they see to say a milestone is done? | "A manager approves a report from the inbox." | Write it in their words. |
| Who gives each demonstration? | The engineers whose tracks meet in the milestone, together. | That. |

## 7. Work outside the plan

| Ask yourself | Example | Default |
| --- | --- | --- |
| What work is owned outside the team and kept out of the plan? | Recruiting pilot teams. Approvals. Security review. Legal text. | None. |
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
Can everyone who can read the repository see all the documents and the staffing notes (yes or no):
If no, restricted documents (default all), who may approve sharing (GitHub logins), keep raw inputs:
Ground truth files:
Wins on conflict:
Version:
People (name, track if fixed, percent allocation, start date, days off, GitHub login):
Optional skills and work preferences:
Parts of the system each track touches (themes):
Advisors:
Target date or weeks:
Breaks (date ranges):
Longest work unit:
Repository:
Epic number or none:
Agents in use:
Demonstration audience and length:
Who gives each demonstration:
What they must see:
Work owned outside the team and the items that wait for it:
Test command / lint command / feature flag:
Other rules for the definition of done:
```
