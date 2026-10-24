# A recorded run of the sample

The run was made against a private throwaway repository that was used only for this test. Names and project links below are placeholders.

This page records a real run of the carrydown skills on the sample project `sample/expense-approvals/`, against a throwaway private repository, from the renderer to the project board. It shows what each script prints so you know what to expect before you run it on your own material.

How it was made.

- A new private repository, `your-user/your-test-repo` (a placeholder for the real name), held a copy of the sample folder so that the links in the issues resolve.
- The commands ran from the root of the repository. Output is as printed, with the token removed and file paths shortened. The scripts never print the token.
- The scripts have since gained a Constraints block in the Epic comment (the target delivery and the allocation by track) and a target delivery line in every sub-epic. The recorded output below predates it. The dry run now prints the same block before anything is written. The project is fictional. The numbers are the real issue numbers the run created: Epic #1, sub-epics #2 to #6, work items #7 to #15.
- The scripts took about three and a half minutes in total, most of it pauses that keep GitHub from rate limiting the writes. Reading the dry runs takes longer than running the scripts.

Each GitHub step shows the dry run first and the write second. A second run of each write step finds everything in place and creates nothing.

## 1. The scripts answer --help

Every script has `--help`. Here is the first part of each. The full text is one command away.

```text
$ python3 scripts/render_ground_truth.py --help
usage: render_ground_truth.py [-h] [--root ROOT] [--out-dir OUT_DIR]
                              [--name NAME] [--version VERSION] [--date DATE]
                              [--dry-run]
                              inputs [inputs ...]
[exit 0]
```

```text
$ python3 scripts/scaffold_spec.py --help
usage: scaffold_spec.py [-h] [--root ROOT] [--plan PLAN] [--init]
                        [--name NAME] [--stubs] [--refresh-headers] [--ci]
                        [--force] [--apply]
[exit 0]
```

```text
$ python3 scripts/check_specs.py --help
usage: check_specs.py [-h] [--root ROOT] [--plan PLAN] [--item ITEM]
                      [--report] [--json] [--quiet]
[exit 0]
```

```text
$ python3 scripts/github_token.py --help
usage: github_token.py [-h] [--token-file TOKEN_FILE] [--check] [--repo REPO]
                       [--stdin] [--from-file PATH] [--dry-run]
[exit 0]
```

```text
$ python3 scripts/github_sync.py --help
usage: github_sync.py [-h] [--root ROOT] [--plan PLAN] [--repo REPO]
                      [--token-file TOKEN_FILE] [--apply] [--offline]
                      [--verify] [--create-epic] [--update-bodies]
                      [--skip-comment] [--skip-check]
                      [--issue-type ISSUE_TYPE] [--show-body ID]
[exit 0]
```

```text
$ python3 scripts/github_project.py --help
usage: github_project.py [-h] [--root ROOT] [--plan PLAN] [--repo REPO]
                         [--owner OWNER] [--title TITLE]
                         [--project-number PROJECT_NUMBER]
                         [--token-file TOKEN_FILE] [--apply] [--verify]
                         [--reconfigure-iterations] [--offline]
[exit 0]
```

```text
$ python3 scripts/generate_dev_skill.py --help
usage: generate_dev_skill.py [-h] [--root ROOT] [--plan PLAN] [--apply]
                             [--force]
[exit 0]
```

```text
$ python3 scripts/sync_skill_assets.py --help
usage: sync_skill_assets.py [-h] [--apply] [--check]
[exit 0]
```

## 2. Token

The token was stored earlier with `github_token.py --from-file`. The dry run prints the steps and sends nothing. The check asks GitHub who the token belongs to and what it can reach.

```text
$ python3 scripts/github_token.py --dry-run
Dry run. These are the steps:
1. Create a classic token with the scopes repo and project: https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown
   Or a fine-grained token (organisation-owned projects only): https://github.com/settings/personal-access-tokens/new
2. Paste it when the script asks. The input is hidden.
3. The script writes it to ~/.config/carrydown/github_token with mode 600.
4. The script asks GitHub who you are and which scopes the token has.
5. If your organisation uses single sign-on, open https://github.com/settings/tokens, choose Configure SSO next to the token and authorise the organisation.
Nothing was asked, stored or sent.
[exit 0]
```

```text
$ python3 scripts/github_token.py --check --repo your-user/your-test-repo
The token belongs to your-user.
Scopes: project, repo
Repository your-user/your-test-repo: found (private: True), push access: True.
Token check passed.
[exit 0]
```

## 3. Render the ground truth

A dry run first, then the write. The sample source is Markdown. The Word example is a small made-up file with a table, a list, a code block and a figure.

```text
$ python3 scripts/render_ground_truth.py sample/expense-approvals/ground-truth/architecture.md --root sample/expense-approvals --version 0.3 --date 2026-10-24 --dry-run
would write docs/ground-truth/architecture.md: 344 lines, 31 headings, 0 figures
would write docs/ground-truth/architecture.index.txt
1 document(s) checked
[exit 0]
```

```text
$ python3 scripts/render_ground_truth.py sample/expense-approvals/ground-truth/architecture.md --root sample/expense-approvals --version 0.3 --date 2026-10-24
wrote docs/ground-truth/architecture.md: 344 lines, 31 headings, 0 figures
wrote docs/ground-truth/architecture.index.txt
1 document(s) rendered
[exit 0]
```

```text
$ python3 scripts/render_ground_truth.py interface-addendum.docx --root . --version 0.1 --dry-run   # a Word file with a table, a list, code and a figure
would write docs/ground-truth/addendum.md: 41 lines, 5 headings, 1 figures
would write docs/ground-truth/addendum.index.txt
1 document(s) checked
[exit 0]
```

## 4. Scaffold

The sample already has its folder, so the scaffold script skips every file. In a copy that holds only `plan.yaml` it writes the README, the milestone files and the stubs, and the checker then refuses the stubs because they still hold TODO lines.

```text
$ python3 scripts/scaffold_spec.py --root sample/expense-approvals --stubs
would skip (exists): docs/spec/README.md  [README]
would skip (exists): docs/spec/m1-submit-report/milestone.md  [milestone]
would skip (exists): docs/spec/m1-submit-report/wi-01-service-scaffold.md  [stub]
would skip (exists): docs/spec/m1-submit-report/wi-02-report-form.md  [stub]
would skip (exists): docs/spec/m2-route-to-approvers/milestone.md  [milestone]
would skip (exists): docs/spec/m2-route-to-approvers/wi-03-routing-engine.md  [stub]
would skip (exists): docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md  [stub]
would skip (exists): docs/spec/m3-enforce-policy/milestone.md  [milestone]
would skip (exists): docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md  [stub]
would skip (exists): docs/spec/m3-enforce-policy/wi-07-audit-log.md  [stub]
would skip (exists): docs/spec/m3-enforce-policy/wi-08-notifications-delegates.md  [stub]
would skip (exists): docs/spec/m4-pilot/milestone.md  [milestone]
would skip (exists): docs/spec/m4-pilot/wi-09-ledger-export.md  [stub]
would skip (exists): docs/spec/m5-release/milestone.md  [milestone]
would skip (exists): docs/spec/m5-release/wi-11-release-readiness.md  [stub]
15 action(s), 0 file(s) would be written. Dry run. Add --apply to write.
[exit 0]
```

<details>
<summary>Scaffold in an empty copy that holds only plan.yaml</summary>

```text
$ python3 scripts/scaffold_spec.py --root . --apply --stubs   # in an empty copy that holds only plan.yaml
create: docs/spec/README.md  [README]
create: docs/spec/m1-submit-report/milestone.md  [milestone]
create: docs/spec/m1-submit-report/wi-01-service-scaffold.md  [stub]
create: docs/spec/m1-submit-report/wi-02-report-form.md  [stub]
create: docs/spec/m2-route-to-approvers/milestone.md  [milestone]
create: docs/spec/m2-route-to-approvers/wi-03-routing-engine.md  [stub]
create: docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md  [stub]
create: docs/spec/m3-enforce-policy/milestone.md  [milestone]
create: docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md  [stub]
create: docs/spec/m3-enforce-policy/wi-07-audit-log.md  [stub]
create: docs/spec/m3-enforce-policy/wi-08-notifications-delegates.md  [stub]
create: docs/spec/m4-pilot/milestone.md  [milestone]
create: docs/spec/m4-pilot/wi-09-ledger-export.md  [stub]
create: docs/spec/m5-release/milestone.md  [milestone]
create: docs/spec/m5-release/wi-11-release-readiness.md  [stub]
15 action(s), 15 file(s) written.
[exit 0]
```

</details>

```text
$ python3 scripts/check_specs.py --root . --quiet   # the stubs hold TODO lines, so the checker refuses them
1 files clean, 14 with findings (9 work items, 5 milestones)
[exit 1]
```

```text
$ python3 scripts/check_specs.py --root . --item 3
0 files clean, 1 with findings (1 work items, 0 milestones)
WI-03 docs/spec/m2-route-to-approvers/wi-03-routing-engine.md:
  - unfinished template text (TODO) at line 17
  - length 76 lines is outside 80 to 340
[exit 1]
```

```text
$ python3 scripts/github_sync.py --root . --repo your-user/your-test-repo   # in the same copy: the checker gate stops it
1 files clean, 14 with findings (9 work items, 5 milestones)
The checker found problems. Run check_specs.py to see them, fix them, or pass --skip-check.
[exit 1]
```

## 5. Check

The checker finds the worked sample clean. The report shows the schedule, the load table, the critical path, the program items and the checkpoints.

```text
$ python3 scripts/check_specs.py --root sample/expense-approvals
15 files clean, 0 with findings (9 work items, 5 milestones)
[exit 0]
```

```text
$ python3 scripts/check_specs.py --root sample/expense-approvals --report
Plan: Expense approvals

Schedule
  Work unit 1, Submit an expense report: 2027-02-01 to 2027-02-12 (demonstration 2027-02-12)
  Work unit 2, Route to approvers: 2027-02-15 to 2027-03-05 (demonstration 2027-03-05)
  Work unit 3, Enforce policy: 2027-03-08 to 2027-03-19 (demonstration 2027-03-19)
  Work unit 4, Pilot with one team: 2027-03-29 to 2027-04-09 (demonstration 2027-04-09)
  Work unit 5, Release: 2027-04-12 to 2027-04-23 (demonstration 2027-04-23)
  Break, Offsite and planning week: 2027-03-22 to 2027-03-26

Load (sized days of work against allocated capacity, per person and work unit)
  Capacity is the working days a person has in the work unit, minus days off, times their percent allocation.
  Person  Alloc  WU1             WU2             WU3             WU4             WU5            Total          
  tamsin  100%   3 of 10d (30%)  5 of 14d (36%)  6 of 10d (60%)  4 of 10d (40%)  0 of 10d       18 of 54d (33%)
  idris   60%    4 of 6d (67%)   4 of 9d (44%)   4 of 5d (74%)   0 of 6d         3 of 6d (50%)  15 of 32d (46%)
  No person is over 100 percent of allocated capacity in any work unit.

Critical path (longest dependency chain to the last item)
  WI-02 -> WI-04 -> WI-08 -> WI-11  (79 calendar days)
    WI-02 Report form and receipt upload, by 2027-02-10, idris
    WI-04 Approver inbox and decisions, by 2027-03-03, idris
    WI-08 Notifications and delegates, by 2027-03-18, idris
    WI-11 Release readiness and runbook, by 2027-04-21, idris

Target
  Target: 2027-04-23
  The critical path ends 2027-04-21: it meets the target with 2 day(s) to spare.

Program-owned items (outside the development plan; referenced only as program input)
  WI-05 Pilot team recruitment
  WI-10 Finance sign-off

Checkpoints
  2027-02-05  Contract freeze: WI-01
  2027-02-12  Milestone 1 demonstration: WI-02
  2027-02-26  Routing meets inbox: WI-03
  2027-03-05  Milestone 2 demonstration: WI-04
  2027-03-12  Rules meet routing: WI-06
  2027-03-19  Milestone 3 demonstration: WI-07, WI-08
  2027-04-09  Pilot readout: WI-09
  2027-04-23  Release: WI-11
[exit 0]
```

## 6. Issues

The dry run, then the write. The Epic is created because the sample plan names none.

<details>
<summary>Dry run</summary>

```text
$ python3 scripts/github_sync.py --root sample/expense-approvals --repo your-user/your-test-repo --create-epic
15 files clean, 0 with findings (9 work items, 5 milestones)

carrydown github_sync  DRY RUN (nothing will be written)
repository: your-user/your-test-repo    plan: docs/spec/plan.yaml
5 milestones, 9 work items, 2 tracks, 2 program items kept outside the plan
repository found (private: True). Reading existing labels and issues.

Labels
  would create label: expense-approvals
  would create label: sub-epic
  would create label: workflow
  would create label: experience

Epic
  would create: Expense approvals, development plan

Sub-epics
  would create: Milestone 1, Submit an expense report
  would create: Milestone 2, Route to approvers
  would create: Milestone 3, Enforce policy
  would create: Milestone 4, Pilot with one team
  would create: Milestone 5, Release

Work items
  would create: WI-01 Service scaffold, flag and API contract
  would create: WI-02 Report form and receipt upload
  would create: WI-03 Approval routing engine
  would create: WI-04 Approver inbox and decisions
  would create: WI-06 Approval limits and separation of duties
  would create: WI-07 Audit log and retention
  would create: WI-08 Notifications and delegates
  would create: WI-09 Ledger export job
  would create: WI-11 Release readiness and runbook

Summary: would create 1 Epic, 5 sub-epics and 9 work item issues (0 sub-epics and 0 issues already exist).
Would then link each work item under its sub-epic and each sub-epic under the Epic,
rewrite dependency ids in the bodies to issue links, update the sub-epic work item lists,
and post the Epic roll-up comment.
  WI-01  workflow     2027-02-04  depends: -
  WI-02  experience   2027-02-10  depends: WI-01
  WI-03  workflow     2027-02-24  depends: WI-01
  WI-04  experience   2027-03-03  depends: WI-02, WI-03
  WI-06  workflow     2027-03-12  depends: WI-03
  WI-07  workflow     2027-03-17  depends: WI-03
  WI-08  experience   2027-03-18  depends: WI-04, WI-06
  WI-09  workflow     2027-04-06  depends: WI-07  program input: the pilot team, named by the program
  WI-11  experience   2027-04-21  depends: WI-08, WI-09  program input: finance sign-off on the export format and retention period

Dry run complete. Read it, then add --apply to write.
[exit 0]
```

</details>

<details>
<summary>Write (labels, Epic, sub-epics, work items, links, roll-up comment)</summary>

```text
$ python3 scripts/github_sync.py --root sample/expense-approvals --repo your-user/your-test-repo --create-epic --apply
15 files clean, 0 with findings (9 work items, 5 milestones)

carrydown github_sync  APPLY
repository: your-user/your-test-repo    plan: docs/spec/plan.yaml
5 milestones, 9 work items, 2 tracks, 2 program items kept outside the plan

Labels
  create label: expense-approvals
  create label: sub-epic
  create label: workflow
  create label: experience

Epic
  create: Expense approvals, development plan
    -> #1

Sub-epics
  create: Milestone 1, Submit an expense report
    -> #2
  create: Milestone 2, Route to approvers
    -> #3
  create: Milestone 3, Enforce policy
    -> #4
  create: Milestone 4, Pilot with one team
    -> #5
  create: Milestone 5, Release
    -> #6

Work items
  create: WI-01 Service scaffold, flag and API contract
    -> #7
  create: WI-02 Report form and receipt upload
    -> #8
  create: WI-03 Approval routing engine
    -> #9
  create: WI-04 Approver inbox and decisions
    -> #10
  create: WI-06 Approval limits and separation of duties
    -> #11
  create: WI-07 Audit log and retention
    -> #12
  create: WI-08 Notifications and delegates
    -> #13
  create: WI-09 Ledger export job
    -> #14
  create: WI-11 Release readiness and runbook
    -> #15

Links
  link #2 under #1
  link #3 under #1
  link #4 under #1
  link #5 under #1
  link #6 under #1
  link #7 under #2
  link #8 under #2
  link #9 under #3
  link #10 under #3
  link #11 under #4
  link #12 under #4
  link #13 under #4
  link #14 under #5
  link #15 under #6

Linking dependency ids and work item lists
  updated work item list in #2
  updated work item list in #3
  updated work item list in #4
  updated work item list in #5
  updated work item list in #6
  linked dependencies in #7 WI-01
  linked dependencies in #8 WI-02
  linked dependencies in #9 WI-03
  linked dependencies in #10 WI-04
  linked dependencies in #11 WI-06
  linked dependencies in #12 WI-07
  linked dependencies in #13 WI-08
  linked dependencies in #14 WI-09
  linked dependencies in #15 WI-11

Epic roll-up comment
  posted comment https://github.com/your-user/your-test-repo/issues/1#issuecomment-6381482321

Summary
  labels created: 4
  sub-epics: #2, #3, #4, #5, #6
  work items: 9 (7 to 15)
  new sub-issue links: 14, bodies rewritten: 14
Next: python3 scripts/github_project.py to build the board. Then run this script with --verify.
[exit 0]
```

</details>

The second run finds everything in place.

<details>
<summary>Second run</summary>

```text
$ python3 scripts/github_sync.py --root sample/expense-approvals --repo your-user/your-test-repo --create-epic --apply   # second run: nothing new
15 files clean, 0 with findings (9 work items, 5 milestones)

carrydown github_sync  APPLY
repository: your-user/your-test-repo    plan: docs/spec/plan.yaml
5 milestones, 9 work items, 2 tracks, 2 program items kept outside the plan

Labels
  label exists: expense-approvals
  label exists: sub-epic
  label exists: workflow
  label exists: experience

Epic
  exists #1: Expense approvals, development plan

Sub-epics
  exists #2: Milestone 1, Submit an expense report
  exists #3: Milestone 2, Route to approvers
  exists #4: Milestone 3, Enforce policy
  exists #5: Milestone 4, Pilot with one team
  exists #6: Milestone 5, Release

Work items
  exists #7: WI-01 Service scaffold, flag and API contract
  exists #8: WI-02 Report form and receipt upload
  exists #9: WI-03 Approval routing engine
  exists #10: WI-04 Approver inbox and decisions
  exists #11: WI-06 Approval limits and separation of duties
  exists #12: WI-07 Audit log and retention
  exists #13: WI-08 Notifications and delegates
  exists #14: WI-09 Ledger export job
  exists #15: WI-11 Release readiness and runbook

Links

Linking dependency ids and work item lists

Epic roll-up comment
  comment already up to date

Summary
  labels created: 0
  sub-epics: #2, #3, #4, #5, #6
  work items: 9 (7 to 15)
  new sub-issue links: 0, bodies rewritten: 0
Next: python3 scripts/github_project.py to build the board. Then run this script with --verify.
[exit 0]
```

</details>

```text
$ python3 scripts/github_sync.py --root sample/expense-approvals --repo your-user/your-test-repo --create-epic --verify
15 files clean, 0 with findings (9 work items, 5 milestones)

carrydown github_sync  VERIFY (read only)
repository: your-user/your-test-repo    plan: docs/spec/plan.yaml
5 milestones, 9 work items, 2 tracks, 2 program items kept outside the plan
repository found (private: True). Reading existing labels and issues.

Verification (read only)
  labels: 4 of 4 present
  sub-epics: 5 of 5
  work item issues: 9 of 9
  sub-issue links work item to sub-epic: 9 of 9
  bodies with all seven headings: 9 of 9
  sub-epics under Epic #1: 5 of 5
  Epic roll-up comment: present
verification passed
[exit 0]
```

## 7. Project board


<details>
<summary>Dry run</summary>

```text
$ python3 scripts/github_project.py --root sample/expense-approvals --repo your-user/your-test-repo

carrydown github_project  DRY RUN (nothing will be written)
project: 'Expense approvals plan'  owner: your-user  repository: your-user/your-test-repo
fields to ensure:
  Work unit (iteration): Work unit 1, Submit an expense report 2027-02-01 +14d; Work unit 2, Route to approvers 2027-02-15 +21d; Work unit 3, Enforce policy 2027-03-08 +14d; Work unit 4, Pilot with one team 2027-03-29 +14d; Work unit 5, Release 2027-04-12 +12d
    gap left for break 'Offsite and planning week': 2027-03-22 to 2027-03-28 (shows as a break)
  Track (single select): Workflow, Experience
  Complete by (date), Checkpoint (date)
views to ensure: Table, Board, Roadmap
issues found in the repository: 15; missing: 0
project does not exist yet. Would create 'Expense approvals plan'.

Dry run complete. Add --apply to create the project, fields, views and items.
[exit 0]
```

</details>

<details>
<summary>Write (project, fields, views, items, values)</summary>

```text
$ python3 scripts/github_project.py --root sample/expense-approvals --repo your-user/your-test-repo --apply

carrydown github_project  APPLY
project: 'Expense approvals plan'  owner: your-user  repository: your-user/your-test-repo
fields to ensure:
  Work unit (iteration): Work unit 1, Submit an expense report 2027-02-01 +14d; Work unit 2, Route to approvers 2027-02-15 +21d; Work unit 3, Enforce policy 2027-03-08 +14d; Work unit 4, Pilot with one team 2027-03-29 +14d; Work unit 5, Release 2027-04-12 +12d
    gap left for break 'Offsite and planning week': 2027-03-22 to 2027-03-28 (shows as a break)
  Track (single select): Workflow, Experience
  Complete by (date), Checkpoint (date)
views to ensure: Table, Board, Roadmap
issues found in the repository: 15; missing: 0
project does not exist yet. Creating 'Expense approvals plan'.
  created #2 https://github.com/users/your-user/projects/N
  linked the project to the repository

Fields
  create Work unit with 5 iterations
  create Track with 2 options
  create Complete by (date)
  create Checkpoint (date)

Views
  rename the default view to Table
  create Board view (BOARD_LAYOUT)
  create Roadmap view (ROADMAP_LAYOUT)
  visible fields set on the Table and Board views (the Roadmap view takes its fields from its settings)

Items
  added #1 Expense approvals, development plan
  added #2 Milestone 1, Submit an expense report
  added #3 Milestone 2, Route to approvers
  added #4 Milestone 3, Enforce policy
  added #5 Milestone 4, Pilot with one team
  added #6 Milestone 5, Release
  added #7 WI-01 Service scaffold, flag and API contract
  added #8 WI-02 Report form and receipt upload
  added #9 WI-03 Approval routing engine
  added #10 WI-04 Approver inbox and decisions
  added #11 WI-06 Approval limits and separation of duties
  added #12 WI-07 Audit log and retention
  added #13 WI-08 Notifications and delegates
  added #14 WI-09 Ledger export job
  added #15 WI-11 Release readiness and runbook
  items added: 15; field values set: 51

Verification (read only)
  project items that are plan issues: 15 of 15
  field Work unit: present, filled on 14 of 14 items
  field Track: present, filled on 9 of 9 items
  field Complete by: present, filled on 14 of 14 items
  field Checkpoint: present, filled on 14 of 14 items
  view Table: TABLE_LAYOUT, group by none
  view Board: BOARD_LAYOUT, group by none
  view Roadmap: ROADMAP_LAYOUT, group by none
  Work unit iterations: 5
  project: https://github.com/users/your-user/projects/N

The API cannot set these. Click them once in the project (see docs/faq.md):
  - Group the Table view by Work unit (View menu, Group by).
  - Sort the Table view by Complete by (View menu, Sort).
  - Set the Board view columns (Column field) to Status, or to Work unit if you prefer.
  - Roadmap view: choose Complete by (and Checkpoint if you like) as the date fields, set the zoom level, show markers for iterations.
  - Optional: slice by Track, and turn on field sums.
  - Project settings, Workflows: turn on 'Auto-add to project' for the repository, and set 'Item closed' to Status Done.
  - Optional: write a one-paragraph project description and README in Settings.
[exit 0]
```

</details>

The second run finds the project, fields, views and values in place.

<details>
<summary>Second run and verification</summary>

```text
$ python3 scripts/github_project.py --root sample/expense-approvals --repo your-user/your-test-repo --apply   # second run: nothing new

carrydown github_project  APPLY
project: 'Expense approvals plan'  owner: your-user  repository: your-user/your-test-repo
fields to ensure:
  Work unit (iteration): Work unit 1, Submit an expense report 2027-02-01 +14d; Work unit 2, Route to approvers 2027-02-15 +21d; Work unit 3, Enforce policy 2027-03-08 +14d; Work unit 4, Pilot with one team 2027-03-29 +14d; Work unit 5, Release 2027-04-12 +12d
    gap left for break 'Offsite and planning week': 2027-03-22 to 2027-03-28 (shows as a break)
  Track (single select): Workflow, Experience
  Complete by (date), Checkpoint (date)
views to ensure: Table, Board, Roadmap
issues found in the repository: 15; missing: 0
project exists: #2 https://github.com/users/your-user/projects/N

Fields
  Work unit exists with the planned iterations
  Track exists with the planned options
  Complete by exists
  Checkpoint exists

Views
  Table exists (TABLE_LAYOUT)
  Board exists (BOARD_LAYOUT)
  Roadmap exists (ROADMAP_LAYOUT)
  visible fields set on the Table and Board views (the Roadmap view takes its fields from its settings)

Items
  items added: 0; field values set: 0

Verification (read only)
  project items that are plan issues: 15 of 15
  field Work unit: present, filled on 14 of 14 items
  field Track: present, filled on 9 of 9 items
  field Complete by: present, filled on 14 of 14 items
  field Checkpoint: present, filled on 14 of 14 items
  view Table: TABLE_LAYOUT, group by none
  view Board: BOARD_LAYOUT, group by none
  view Roadmap: ROADMAP_LAYOUT, group by none
  Work unit iterations: 5
  project: https://github.com/users/your-user/projects/N

The API cannot set these. Click them once in the project (see docs/faq.md):
  - Group the Table view by Work unit (View menu, Group by).
  - Sort the Table view by Complete by (View menu, Sort).
  - Set the Board view columns (Column field) to Status, or to Work unit if you prefer.
  - Roadmap view: choose Complete by (and Checkpoint if you like) as the date fields, set the zoom level, show markers for iterations.
  - Optional: slice by Track, and turn on field sums.
  - Project settings, Workflows: turn on 'Auto-add to project' for the repository, and set 'Item closed' to Status Done.
  - Optional: write a one-paragraph project description and README in Settings.
[exit 0]
```

</details>

```text
$ python3 scripts/github_project.py --root sample/expense-approvals --repo your-user/your-test-repo --verify

carrydown github_project  VERIFY
project: 'Expense approvals plan'  owner: your-user  repository: your-user/your-test-repo
fields to ensure:
  Work unit (iteration): Work unit 1, Submit an expense report 2027-02-01 +14d; Work unit 2, Route to approvers 2027-02-15 +21d; Work unit 3, Enforce policy 2027-03-08 +14d; Work unit 4, Pilot with one team 2027-03-29 +14d; Work unit 5, Release 2027-04-12 +12d
    gap left for break 'Offsite and planning week': 2027-03-22 to 2027-03-28 (shows as a break)
  Track (single select): Workflow, Experience
  Complete by (date), Checkpoint (date)
views to ensure: Table, Board, Roadmap
issues found in the repository: 15; missing: 0
project exists: #2 https://github.com/users/your-user/projects/N

Fields
  Work unit exists with the planned iterations
  Track exists with the planned options
  Complete by exists
  Checkpoint exists

Views
  Table exists (TABLE_LAYOUT)
  Board exists (BOARD_LAYOUT)
  Roadmap exists (ROADMAP_LAYOUT)

Items
  items added: 0; field values set: 0

Verification (read only)
  project items that are plan issues: 15 of 15
  field Work unit: present, filled on 14 of 14 items
  field Track: present, filled on 9 of 9 items
  field Complete by: present, filled on 14 of 14 items
  field Checkpoint: present, filled on 14 of 14 items
  view Table: TABLE_LAYOUT, group by none
  view Board: BOARD_LAYOUT, group by none
  view Roadmap: ROADMAP_LAYOUT, group by none
  Work unit iterations: 5
  project: https://github.com/users/your-user/projects/N

The API cannot set these. Click them once in the project (see docs/faq.md):
  - Group the Table view by Work unit (View menu, Group by).
  - Sort the Table view by Complete by (View menu, Sort).
  - Set the Board view columns (Column field) to Status, or to Work unit if you prefer.
  - Roadmap view: choose Complete by (and Checkpoint if you like) as the date fields, set the zoom level, show markers for iterations.
  - Optional: slice by Track, and turn on field sums.
  - Project settings, Workflows: turn on 'Auto-add to project' for the repository, and set 'Item closed' to Status Done.
  - Optional: write a one-paragraph project description and README in Settings.
[exit 0]
```

## 8. Independent check of the counts

The scripts verify their own work. This separate script reads the GitHub API directly and counts, so the numbers do not depend on the scripts that wrote them.

```text
$ # independent check: a separate script reads the GitHub API directly and counts
issues in repository: 15
  epic: 1  sub-epics: 5  work items: 9
  numbers: epic #1, sub-epics ['#2', '#3', '#4', '#5', '#6'], work items ['#7', '#8', '#9', '#10', '#11', '#12', '#13', '#14', '#15']
  #1 Expense approvals, development plan          has 5 sub-issues: ['#2', '#3', '#4', '#5', '#6']
  #2 Milestone 1, Submit an expense report        has 2 sub-issues: ['#7', '#8']
  #3 Milestone 2, Route to approvers              has 2 sub-issues: ['#9', '#10']
  #4 Milestone 3, Enforce policy                  has 3 sub-issues: ['#11', '#12', '#13']
  #5 Milestone 4, Pilot with one team             has 1 sub-issues: ['#14']
  #6 Milestone 5, Release                         has 1 sub-issues: ['#15']
  sub-issue links in total: 14
  labels present: ['expense-approvals', 'experience', 'sub-epic', 'workflow']
  work item bodies with a Depends on section resolved: 9 of 9
project: Expense approvals plan  https://github.com/users/your-user/projects/N
  items on the board: 15
  field Work unit (ITERATION) Work unit 1 2027-02-01 +14d; Work unit 2 2027-02-15 +21d; Work unit 3 2027-03-08 +14d; Work unit 4 2027-03-29 +14d; Work unit 5 2027-04-12 +12d
  field Track (SINGLE_SELECT) options Workflow, Experience
  field Complete by (DATE)
  field Checkpoint (DATE)
  views: Table (TABLE_LAYOUT), Board (BOARD_LAYOUT), Roadmap (ROADMAP_LAYOUT)
[exit 0]
```

## 9. Developer skill

The sample already has its generated skill, so the dry run skips every file.

```text
$ python3 scripts/generate_dev_skill.py --root sample/expense-approvals
developer skill: expense-approvals-dev  ->  docs/dev/skills/expense-approvals-dev
description length: 512 characters (limit 1024)
  skip (exists): SKILL.md
  skip (exists): README.md
  skip (exists): references/work-items.md
  skip (exists): references/contracts.md
  skip (exists): references/ground-truth-map.md
0 file(s) would be written. Dry run. Add --apply to write.
[exit 0]
```

## What the API did not set

The run created the project, three fields, the Work unit iteration field with five iterations and a break, three views and 15 items with their values. The API did not set how the Table view groups and sorts, the Board column field, the Roadmap date fields and zoom, or the project workflows. The scripts print that list at the end, and the plan-to-github skill explains each click.

## Cleaning up

The scripts delete nothing. When you finish with a test repository, delete the repository and the project yourself in the GitHub settings. A token that can delete repositories is more power than the carrydown skills need.
