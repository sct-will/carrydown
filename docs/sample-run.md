# A recorded run of the sample

The run was made against a private throwaway repository that was used only for this test. Names and project links below are placeholders.

This page records a real run of the carrydown skills on the sample project `sample/expense-approvals/`, against a throwaway private repository, from the renderer to the project board. It shows what each script prints so you know what to expect before you run it on your own material.

How it was made.

- A new private repository, `your-user/your-test-repo` (a placeholder for the real name), held a copy of the sample folder so that the links in the issues resolve.
- The commands ran from the root of the repository. Output is as printed, with the token removed and file paths shortened. The scripts never print the token.
- The scripts have since gained a Constraints block in the Epic comment (the target delivery and the allocation by track) and a target delivery line in every sub-epic. The write blocks below predate it. The dry runs print the block before anything is written. The project is fictional. The numbers are the real issue numbers the run created: Epic #1, sub-epics #2 to #6, work items #7 to #15.
- The sample dates have since moved so that every item has slack before its checkpoint, and the plan gained its rationale. The write blocks below show the earlier dates. The blocks that need no GitHub account show the current ones.
- The blocks that need no GitHub account were run again with the current scripts: the help text, the token walkthrough, the renderer, the scaffold, the checker, the dry runs (with `--offline`, so they read nothing from GitHub) and the engineers' skill. The blocks that talk to GitHub are as recorded in the original run: the token check, the writes, the second runs, the verifications and the independent count.
- Section 0 below is new and was run with the current scripts. The GitHub blocks in sections 2, 6 and 7 were recorded before releases existed, so they show the legacy project flow. A project with a release policy publishes from the approved release instead: the dry runs begin with the destination preflight, which prints one visibility line for each target, and then list the payloads and the request id. Those blocks have not been recorded again, because that needs a real repository and a token.
- Section 10 is new and was run with the current scripts in a throwaway copy of the sample. It records an update after planning: a changed source, the review of its effects, an engineer's correction and a drafted request that is labeled not sent. It makes no GitHub call.
- The scripts took about three and a half minutes in total, most of it pauses that keep GitHub from rate limiting the writes. Reading the dry runs takes longer than running the scripts.

Each GitHub step shows the dry run first and the write second. A second run of each write step finds everything in place and creates nothing.

## 0. The release, run on the sample

This section was run again with the current scripts, in a throwaway copy of the sample, against the loopback mock of GitHub that the tests use (`tests/mock/mockgh.py`) in place of github.com, so it needs no real token and no network. The ids in it differ from the committed receipt, which `tests/rebuild_sample_release.py` makes with a fixed time and request nonce. The sample answers yes to the one question, so its fictional documents are approved for everyone who can read the repository. It shows what a project holds before and after a release, and which commands print what. The private path, with a staging repository and the independent verifier, needs an organization's setup and has not been run on real GitHub. [The setup guide](setup.md#organization-setup-for-private-drafting) says so.

**What the sample is.** The committed sample is a project after its release. Its `docs/spec/plan.yaml` is the released plan: ids and tracks for the people, and for each source only an id, a display name and a version. It holds no source path, no classification, no digest and no personal fact. The two documents in the sample, the original `ground-truth/architecture.md` and its rendering, and the fictional `people.yaml`, are public fixtures. They are here so the sample can show every step. A real project does not copy staffing records or confidential originals into git, and the sample's `.gitignore` carries the same four lines that `scaffold_spec.py --init` writes: `docs/source/`, `people.yaml`, `.carrydown/local.yaml` and `.carrydown/cache/`.

The owner's side of the sample is a test fixture, `tests/fixtures/sample-workspace/`. It holds the owner's working plan (`drafts/plan.yaml`, the workspace view, with the classification, the paths of the original and of the rendering and their digests), and the release records: the snapshot, the manifest, the request, the approval and the event. `python3 tests/rebuild_sample_release.py --check` rebuilds the whole release from the sample and compares every byte, so a change to any sample file, template or script that the release depends on is caught.

```text
$ python3 scripts/workspace.py init --root . --slug expense-approvals --answer yes --apply
carrydown: private workspace ready at <tmp>/workspace (owner only, git initialized)
[exit 0]
```

After "Put the plan on GitHub." and the token, the agent runs one command as a dry run. It reads the repository's numeric id with the token, derives the audience from the repository and looks the board up by the plan's project title. Nobody types an id, an audience or a destination.

```text
$ python3 scripts/release.py release --root .
carrydown release  DRY RUN (nothing will be written)

release id (the content): 06a45d2a3fb46a17f54e76e0b69adb08697ecf5b725758a1454218392d19f92e


What will be shared?
  40 repository file(s): the released plan, 16 specification file(s), 18 approved context file(s) and the engineers' skill.
  (the 40 paths are listed here)
  9 issue payload(s) for GitHub: WI-01, WI-02, WI-03, WI-04, WI-06, WI-07, WI-08, WI-09, WI-11
  5 subepic payload(s) for GitHub: M1, M2, M3, M4, M5
  1 epic payload(s) for GitHub: EPIC
  1 epic-comment payload(s) for GitHub: rollup
  4 label payload(s) for GitHub: expense-approvals, experience, sub-epic, workflow
  1 board payload(s) for GitHub: project
  Obligations present in the bundles: 47 of 47. Presence is checked by the compiler. Whether each bundle is enough to do the work is your review.

With whom?
  Everyone who can read sct-will/carrydown-sample
  No assignee login is published.
  The capacity summary (people by track) is published.
  Evidence in tests and code: synthetic data only.

Where?
  Repository: sct-will/carrydown-sample (numeric id 4200) on github.com.
  Destinations: engineering-repo, issue, subepic, epic, epic-comment, label, board, engineers-skill.

What remains private?
  The sources and their originals stay in the private workspace or the system they came from.
  Staffing records (names, skills, allocation, days off, start dates) stay in the private workspace; the released plan holds ids and tracks only.

Changes since the previous release
  This is the first release. Nothing is being replaced.

Limitations
  None found. The detectors are a safety net and do not prove safety.

Board: the board 'Expense approvals plan' does not exist yet under sct-will. The run with --apply creates it empty, linked to sct-will/carrydown-sample, before it prepares the release.

Ask the owner in one prompt, with the preview above it. Each line is answered on its own:
  1. "The plan and specifications are correct." (only if not already approved in this session)
  2. "These exact outputs may be shared with everyone who can read sct-will/carrydown-sample."
  3. "Carrydown may create or update these GitHub items: 1 Epic, 5 sub-epics, 9 work item issues, 1 Epic comment, 4 labels, the board 'Expense approvals plan' (created empty first, then filled)."

Dry run: nothing was written to the project or to GitHub. The private workspace keeps a digest of this preview, so the approval of --apply covers exactly what is shown here. After a yes to line 2, run this command again with --apply. If line 3 was not a yes, add --no-github to both runs: the release then carries no GitHub items.
[exit 0]
```

The agent shows the preview and asks lines 2 and 3 in one prompt; line 1 was answered at the end of planning. On a yes to both it runs the same command with `--apply`. That run approves only what the preview showed: the dry run left a digest of it in the private workspace, and a file changed in between makes `--apply` refuse with `not-approved` before it writes anything.

```text
$ python3 scripts/release.py release --root . --apply
carrydown release  APPLY
Created the empty board 'Expense approvals plan' for sct-will, linked to sct-will/carrydown-sample. It holds nothing until the release is published.
carrydown release prepare  APPLY

release id (content): 06a45d2a3fb46a17f54e76e0b69adb08697ecf5b725758a1454218392d19f92e
request id (permission): db2d1727f7cc97302be9aaaf17e9e6d0ce4c7eb1168d25ac7cc0db9aadebe802
The release id names these exact bytes. The request id names one permission decision over them: this audience, these
destinations, these targets and these downstream uses. The same content can have several requests, and approving one
never approves another.
61 file(s) in the snapshot; audience repo-readers; destinations engineering-repo, issue, subepic, epic, epic-comment, label, board, engineers-skill.

carrydown release approve --local  APPLY
The owner approved this preview in the dry run of release: db2d1727f7cc97302be9aaaf17e9e6d0ce4c7eb1168d25ac7cc0db9aadebe802
Approved locally. The request db2d1727f7cc97302be9aaaf17e9e6d0ce4c7eb1168d25ac7cc0db9aadebe802 is active. This approval is labeled not authenticated.

carrydown release export  APPLY
request db2d1727f7cc97302be9aaaf17e9e6d0ce4c7eb1168d25ac7cc0db9aadebe802  release 06a45d2a3fb46a17f54e76e0b69adb08697ecf5b725758a1454218392d19f92e
40 approved repository file(s), 1 receipt(s). Evidence: local owner approval, not authenticated
1 file(s) and 1 receipt(s) would be written; 39 already match.
  docs/spec/plan.yaml becomes the released plan. Your working plan, with its comments, moves to the private workspace as drafts/plan.yaml, where the scripts find it from now on.
Exported 1 file(s) and 1 receipt(s) into your working tree. Review them with git status, then commit and push as you usually do.

Released. Ask the owner to commit and push these files as they do today. Then the GitHub step publishes from this release.
[exit 0]
```

In this run the 39 other files already match because the owner had drafted them in the working tree. The export writes the released plan and the receipt, `docs/release/db2d1727f7cc97302be9aaaf17e9e6d0ce4c7eb1168d25ac7cc0db9aadebe802.receipt.json`. The receipt is the small public file of the release. It holds the request id, the release id, the manifest digest, the state `active`, the audience, the destinations, the targets with their numeric ids, the source ids and versions, the list of artifacts with their digests, the downstream permissions, the grace period of 7 days, and `"approval": {"type": "local-owner", "authenticated": false}`. It holds no staging name, no reviewer, no source classification and no private reason. The receipt does not list itself in the manifest, and the verifier regenerates it from the approved records and compares every byte. The sample's committed receipt is the same file for the fixed time and nonce of `tests/rebuild_sample_release.py`.

From a fresh clone of the sample, with no private workspace and no original or rendering, both checks pass:

```text
$ python3 scripts/check_specs.py --root sample/expense-approvals --view released
15 files clean, 0 with findings (9 work items, 5 milestones)
people overlay not loaded: capacity, dates and names not checked
detectors: no findings (this does not prove safety)
[exit 0]
```

```text
$ python3 docs/dev/skills/expense-approvals-dev/scripts/check_context.py WI-06      # the engineers' check
carrydown: approved context for WI-06 is ready
Read docs/context/wi-06.md. Do not open docs/ground-truth/ or any source.
baseline: request 59151c0c1a4033a36b7b1137f8a4ce0c7d9c1bafb1f190319e021a0ee009ec98, specification 6f3e13ccb352a77994e98abd912aecd2d4f78ac81d9043ccfaaf34a61cbcac0a
[exit 0]
```

The engineers' check prints a short block when the inputs are ready, with the `baseline:` line that a rule clarification request quotes. When the approved inputs changed since the engineer's last check for the item, it adds the approved delta after the block. Otherwise it stops with one of six messages (exits 10 to 15). It refreshes with `git fetch` of the default branch, so it needs the clone to have an `origin`. The line "people overlay not loaded" in the checker output above is expected: the capacity, date and name checks run on the owner's machine, where `people.yaml` is.

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
                        [--force] [--apply] [--allow-no-git]
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
                       [--stdin] [--from-file PATH] [--delete-after]
                       [--dry-run]
[exit 0]
```

```text
$ python3 scripts/github_sync.py --help
usage: github_sync.py [-h] [--root ROOT] [--plan PLAN] [--repo REPO]
                      [--token-file TOKEN_FILE] [--apply] [--preflight]
                      [--inventory] [--offline] [--verify] [--create-epic]
                      [--update-bodies] [--skip-comment] [--skip-check]
                      [--people PEOPLE] [--issue-type ISSUE_TYPE]
                      [--show-body ID] [--select-issue KEY=NUMBER]
                      [--reconcile]
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
                             [--force] [--only {references}]
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
1. Create a token first, with a 7-day expiry. Pick the kind by who owns the board:
     Board owned by an organization: a fine-grained token. https://github.com/settings/personal-access-tokens/new
       Resource owner: the organization. Expiration: 7 days. Repository access: only the one repository.
       Repository permissions: Issues read and write, Metadata read. Organization permission: Projects read and write.
     Board owned by your own account: a classic token. This link ticks repo and project and names it: https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown
       Set Expiration to 7 days. GitHub does not let fine-grained tokens use boards on a personal account.
     Copy the token. GitHub shows it once. Revoke it when the GitHub step is done.
2. Paste it when the script asks. The input is hidden.
3. The script writes it to ~/.config/carrydown/github_token with mode 600.
4. The script asks GitHub who you are and which scopes the token has.
5. If your organization uses single sign-on, open https://github.com/settings/tokens, choose Configure SSO next to the token and authorize the organization.
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

The sample already has its folder, so the scaffold script skips every file. In a copy that holds only `plan.yaml` it writes the README, the milestone files and the stubs, and the checker then refuses the stubs because they still hold TODO lines. It also notes that the ground truth is not rendered in that copy, so its citations are not checked.

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
1 files clean, 15 with findings (9 work items, 5 milestones)
14 file(s) still hold template text (TODO). That is expected until the specifications are written.
[exit 1]
```

```text
$ python3 scripts/check_specs.py --root . --item 3
0 files clean, 1 with findings (1 work items, 0 milestones)
1 file(s) still hold template text (TODO). That is expected until the specifications are written.
WI-03 docs/spec/m2-route-to-approvers/wi-03-routing-engine.md:
  - unfinished template text (TODO) at line 17, and 1 other finding(s) that usually go when the template text is replaced
[exit 1]
```

```text
$ python3 scripts/github_sync.py --root . --repo your-user/your-test-repo   # in the same copy: the checker gate stops it
1 files clean, 15 with findings (9 work items, 5 milestones)
14 file(s) still hold template text (TODO). That is expected until the specifications are written.
The checker found problems. Run check_specs.py to see them, fix them, or pass --skip-check.
[exit 1]
```

## 5. Check

The checker finds the worked sample clean. The report shows the sources, advisory staffing context, schedule, load table, critical path, external items, checkpoints and planning review.

Run from a clean clone, the checker has no private people file. It prints one line, `people overlay not loaded: capacity, dates and names not checked`, and skips the capacity, date and name checks. Those are planning checks that run where the owner runs them. The report below is the owner's run, which loads the sample's fictional copy of the people file with `--people`. In a real project the checker finds the private file through the pointer `.carrydown/local.yaml`, and you pass no flag.

```text
$ python3 scripts/check_specs.py --root sample/expense-approvals
15 files clean, 0 with findings (9 work items, 5 milestones)
people overlay not loaded: capacity, dates and names not checked
detectors: no findings (this does not prove safety)
[exit 0]
```

```text
$ python3 scripts/check_specs.py --root sample/expense-approvals --report --people sample/expense-approvals/people.yaml
Plan: Expense approvals

Sources (highest precedence first)
  1. Architecture document: reviewed; not rendered -> not rendered

Staffing context (advisory)
  Track workflow needs: Service APIs, Workflow rules, Relational data
  Track experience needs: Accessible web interfaces, Client integration, Notifications
  tamsin on workflow: skills Python services, PostgreSQL, Workflow design; preferences Service contracts, Policy enforcement
    Assignment rationale: The workflow track best matches the supplied service, data and workflow skills and the preference for policy work.
  idris on experience: skills TypeScript, Accessible web interfaces, Notification flows; preferences User-facing workflows, Integration demonstrations
    Assignment rationale: The experience track best matches the supplied interface and notification skills and the preference for user-facing work.
  Skills and preferences guide the agent's proposed match. They do not make the checker pass or fail; uncertain matches use the default assignment rules.

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
  idris   60%    3 of 6d (50%)   4 of 9d (44%)   4 of 5d (74%)   0 of 6d         3 of 6d (50%)  14 of 32d (43%)
  No person is over 100 percent of allocated capacity in any work unit.

Critical path (longest dependency chain to the last item)
  WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11  (79 calendar days)
    WI-01 Service scaffold, flag and API contract, by 2027-02-03, tamsin
    WI-02 Report form and receipt upload, by 2027-02-10, idris
    WI-04 Approver inbox and decisions, by 2027-03-03, idris
    WI-08 Notifications and delegates, by 2027-03-17, idris
    WI-11 Release readiness and runbook, by 2027-04-21, idris

Target
  Target: 2027-04-23
  The critical path ends 2027-04-21: it meets the target with 2 day(s) to spare.

Fit (working days each item needs, from its size and its owner's allocation, against its window)
  Every sized item fits between its last dependency and its complete_by date.

Earliest finish (forward pass over the dependencies, from sizes and allocation)
  WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11  ends 2027-03-10
    WI-01 2027-02-01 to 2027-02-03, about 3.0 working days
    WI-02 2027-02-04 to 2027-02-10, about 5.0 working days
    WI-04 2027-02-11 to 2027-02-19, about 6.7 working days
    WI-08 2027-02-22 to 2027-03-02, about 6.7 working days
    WI-11 2027-03-03 to 2027-03-10, about 5.0 working days
  It meets the target 2027-04-23 with 44 day(s) to spare. The planned dates add the slack between items.
  Owners are not serialized in this pass. The load table above shows whether each person's work fits each work unit.

External items (outside the development plan; referenced only as external input)
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

Planning review (advisory, except lines marked finding; the rules are in references/planning.md)
  Milestone composition (rules 1 to 3)
    Milestone 1, Submit an expense report: Workflow (WI-01), Experience (WI-02).
      The joint check on 2027-02-12 names Workflow and Experience.
    Milestone 2, Route to approvers: Workflow (WI-03), Experience (WI-04).
      The joint check on 2027-03-05 names Workflow and Experience.
    Milestone 3, Enforce policy: Workflow (WI-06, WI-07), Experience (WI-08).
      The joint check on 2027-03-19 names Workflow and Experience.
    Milestone 4, Pilot with one team: Workflow (WI-09) only.
      One track, because: The pilot adds no screen and no notification. The Experience work it needs is support for the pilot team on the existing web client, which is not a deliverable item.
      The joint check on 2027-04-09 names Workflow and Experience.
    Milestone 5, Release: Experience (WI-11) only.
      One track, because: Release readiness is one item of rehearsal and runbook work. It sits on the Experience track because the rehearsal runs through the web client. The Workflow engineer takes part in the rehearsal and owns no new item.
      The joint check on 2027-04-23 names Workflow and Experience.
  Order of work per track (rules 4, 5 and 10)
    Workflow: WI-01, WI-03, WI-06, WI-07, WI-09. Order rationale given.
    Experience: WI-02, WI-04, WI-08, WI-11. Order rationale given.
  Theme switches (consecutive items of one owner, by date)
    tamsin: 1 switch, 0 inside a milestone.
      WI-07 (expense service) to WI-09 (export job), across milestones 3 and 4.
    idris: 2 switches, 0 inside a milestone.
      WI-04 (web client) to WI-08 (notification worker), across milestones 2 and 3.
      WI-08 (notification worker) to WI-11 (release), across milestones 3 and 5.
  Slack before checkpoints (rule 7)
    Every item completes before its checkpoint. The least slack is 2 working day(s), WI-01 before 2027-02-05.
  Critical path owners (rule 8)
    WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11: tamsin (WI-01), idris (WI-02, WI-04, WI-08, WI-11).
  Load ratio (rule 6)
    Share of allocated capacity over the plan: tamsin 18 of 54d (33%), idris 14 of 32d (43%).
    Highest to lowest is 1.3 to 1 (idris to tamsin).
  0 finding(s).
[exit 0]
```

## 6. Issues

The dry run, then the write. The Epic is created because the sample plan names none. The dry run here uses `--offline`: it shows the plan and counts every issue as new, because it reads nothing from GitHub. Without `--offline` and with a token, it reads the repository first and counts only what is missing.

<details>
<summary>Dry run</summary>

```text
$ python3 scripts/github_sync.py --root sample/expense-approvals --repo your-user/your-test-repo --create-epic --offline
15 files clean, 0 with findings (9 work items, 5 milestones)

carrydown github_sync  DRY RUN (nothing will be written)
repository: your-user/your-test-repo    plan: docs/spec/plan.yaml
5 milestones, 9 work items, 2 tracks, 2 external items kept outside the plan
Constraints (they go into the Epic comment, and the target into every sub-epic):
  Target delivery: 2027-04-23 (given)
  Track Workflow: 1 person, 100 percent allocated
  Track Experience: 1 person, 60 percent allocated
not checked against GitHub (--offline): showing the plan only, nothing is read from GitHub

Labels
  would create label if missing: expense-approvals
  would create label if missing: sub-epic
  would create label if missing: workflow
  would create label if missing: experience

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

Summary
1 Epic, 5 sub-epics, 9 work item issues
  not checked against GitHub (--offline), so this counts every issue as new: 1 Epic, 5 sub-epics, 9 work item issues.
Would then link each work item under its sub-epic and each sub-epic under the Epic,
rewrite dependency ids in the bodies to issue links, update the sub-epic work item lists,
and post the Epic roll-up comment.
  WI-01  workflow     2027-02-03  depends: -
  WI-02  experience   2027-02-10  depends: WI-01
  WI-03  workflow     2027-02-19  depends: WI-01
  WI-04  experience   2027-03-03  depends: WI-02, WI-03
  WI-06  workflow     2027-03-08  depends: WI-03
  WI-07  workflow     2027-03-17  depends: WI-03
  WI-08  experience   2027-03-17  depends: WI-04, WI-06
  WI-09  workflow     2027-04-06  depends: WI-07  external input: the pilot team, named by the stakeholders
  WI-11  experience   2027-04-21  depends: WI-08, WI-09  external input: finance sign-off on the export format and retention period

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
5 milestones, 9 work items, 2 tracks, 2 external items kept outside the plan

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
5 milestones, 9 work items, 2 tracks, 2 external items kept outside the plan

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
5 milestones, 9 work items, 2 tracks, 2 external items kept outside the plan
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

The dry run uses `--offline`, so it shows the fields and views the plan calls for and does not look for the project or the issues. The write that follows ran against the repository from step 6.

<details>
<summary>Dry run</summary>

```text
$ python3 scripts/github_project.py --root sample/expense-approvals --repo your-user/your-test-repo --offline

carrydown github_project  DRY RUN (nothing will be written)
project: 'Expense approvals plan'  owner: your-user  repository: your-user/your-test-repo
fields to ensure:
  Work unit (iteration): Work unit 1, Submit an expense report 2027-02-01 +14d; Work unit 2, Route to approvers 2027-02-15 +21d; Work unit 3, Enforce policy 2027-03-08 +14d; Work unit 4, Pilot with one team 2027-03-29 +14d; Work unit 5, Release 2027-04-12 +12d
    gap left for break 'Offsite and planning week': 2027-03-22 to 2027-03-28 (shows as a break)
  Track (single select): Workflow, Experience
  Complete by (date), Checkpoint (date)
views to ensure: Table, Board, Roadmap
offline: nothing read from GitHub
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

The scripts verify their own work. This separate script reads the GitHub application programming interface (API) directly and counts, so the numbers do not depend on the scripts that wrote them.

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

## 9. The engineers' skill

The last step of `carrydown-plan-to-github` generates the skill the engineers install. It needs no token. The sample already has its generated skill, so the dry run skips every file.

```text
$ python3 scripts/generate_dev_skill.py --root sample/expense-approvals
engineers' skill: expense-approvals-dev  ->  docs/dev/skills/expense-approvals-dev
description length: 248 characters (target under 250, limit 1024)
  skip (exists): SKILL.md
  skip (exists): README.md
  skip (exists): references/work-items.md
  skip (exists): references/contracts.md
  skip (exists): references/ground-truth-map.md
0 file(s) would be written. Dry run. Add --apply to write.
[exit 0]
```

## 10. An update after planning

Projects change after planning. This section records the update path of `carrydown-ground-truth` on the sample, with real output. The story is fictional. The finance policy team revises the delegated approval rule in the architecture document, and an engineer meets the same gap in a specification.

How it was made.

- The commands ran in a throwaway copy of the sample with its owner workspace, in a temporary home folder, the way `tests/rebuild_sample_release.py` wires the fixture. The copy was released first with the real release commands, so it holds the same receipt as the committed sample. The committed sample was not touched.
- A local bare repository served as `origin`, so the engineer's `git fetch` needed no network. Nothing was sent to GitHub, and no token was read.
- The sample's release counts as published here. The recording made no GitHub call, so the journal that the publishing skill would have written was created by hand. Without it, `status` answers "Approved release awaiting publication".
- The plan owner never types these commands. The agent runs them and explains the result in plain words. They are shown so you know what each prints. Paths in the workspace are shortened to `<workspace>`, and the proposal and checkpoint ids are the real ones.
- Not recorded here: the new release and its publication. They are the ordinary steps of sections 0, 6 and 7. The engineer's view of the approved delta after that release has no recording yet.

### The reviewed starting point

The owner asks "Is this project up to date?". The agent runs `status`. It has never recorded a reviewed checkpoint of the sources, so it cannot compare anything, and it says so.

```text
$ python3 scripts/reconcile.py status --root .
carrydown project status
State: Observable inputs unchanged
No change can be observed against a reviewed checkpoint, because none is recorded.
Next: Nothing to update. Tell the owner what was checked and what was not observed.

What was checked: the working plan; the current renderings of the reviewed sources; the private workspace: reviewed checkpoints, saved updates, release and publication records.
What was not observed:
  Outstanding engineer requests were not observed: the publishing skill's authorized read has not run.
  A previous complete source checkpoint is unavailable. Review the current sources to establish one. Earlier uncited changes cannot be assessed automatically.
  Sources kept elsewhere were not observed. Only the renderings held in this project or in the private workspace were checked.
[exit 0]
```

The owner reviews the current architecture rendering with the agent and accepts it. That review becomes the first checkpoint. `prepare --apply` saves a proposal, and the proposal folder holds the descriptor of the sources that the checkpoint command needs. Nothing is compared yet, because there is nothing to compare with.

```text
$ python3 scripts/reconcile.py prepare --root . --apply
carrydown update: compare changed sources
A previous complete source checkpoint is unavailable. Review the current sources to establish one. Earlier uncited changes cannot be assessed automatically.
architecture: 30 sections cannot be compared, because there is no earlier checkpoint. Treat each as unassessable history and review the current source with the owner.
0 changed block(s) in 0 source(s); 0 direct consumer(s); index: 20591 bytes, 2016 words, about 5148 tokens (approximate)

The full record is in the private workspace, folder drafts/proposals/6b3fffe052b282b9b8ff2b21fc60922edba5a50e40284602f098d15917a6cb3f/ (inputs, blocks, consumers, the index, dispositions).
When the owner accepts the sources, descriptor.json in that folder is the descriptor for workspace.py checkpoint prepare.
proposal: 6b3fffe052b282b9b8ff2b21fc60922edba5a50e40284602f098d15917a6cb3f
[exit 0]
```

The checkpoint is recorded in two steps, each one a preview first. `prepare` copies the reviewed rendering into the private workspace. `commit` stores it in the workspace's own git history through an isolated index, reads it back, and only then records it in `workspace.yaml`. Nothing is pushed.

```text
$ python3 scripts/workspace.py checkpoint prepare --root . --descriptor <workspace>/drafts/proposals/<proposal>/descriptor.json --rendering-dir docs/ground-truth
checkpoint 7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446  DRY RUN (nothing was written)
  would write workspace:renderings/reviewed/architecture/architecture.index.txt
  would write workspace:renderings/reviewed/architecture/architecture.md
  would write workspace:drafts/checkpoints/7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446/descriptor.json
  would write workspace:drafts/checkpoints/7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446/checkpoint.json
Add --apply to write these files. Then commit the checkpoint with: workspace.py checkpoint commit --id 7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446 --apply
[exit 0]
```

```text
$ python3 scripts/workspace.py checkpoint prepare --root . --descriptor <workspace>/drafts/proposals/<proposal>/descriptor.json --rendering-dir docs/ground-truth --apply
checkpoint 7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446
  wrote workspace:renderings/reviewed/architecture/architecture.index.txt
  wrote workspace:renderings/reviewed/architecture/architecture.md
  wrote workspace:drafts/checkpoints/7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446/descriptor.json
  wrote workspace:drafts/checkpoints/7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446/checkpoint.json
[exit 0]

$ python3 scripts/workspace.py checkpoint commit --root . --id <checkpoint>
checkpoint 7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446  DRY RUN (nothing was committed)
would commit 4 file(s) from renderings/reviewed/ and drafts/checkpoints/ through an isolated index, then read the commit back and record it in workspace.yaml
Add --apply to commit.
[exit 0]

$ python3 scripts/workspace.py checkpoint commit --root . --id <checkpoint> --apply
checkpoint 7d51dd0871a0cc0fa42ebe6573842977202ad1869bd5be7e2643c5a765972446 committed and read back. Recorded in workspace.yaml
[exit 0]
```

### A source changes

The finance policy team revises the architecture document, which is the source of truth. Two edits. Section 3.5, routing, gets a fifth rule: when an approver has a delegate record that covers the day of routing, the step goes to the approver and the delegate, and the first decision closes it. Section 4.1, the governance rule GOV-1, has item 4 split into two sentences. The owner edits the original, so the original is the source of truth, and renders it again as version 0.4.

```text
$ git diff -- ground-truth/architecture.md
@@ -134,6 +134,7 @@ Rules that apply to every route.
 3. A reminder goes to the current approver after 3 business days without a decision. After 5 business days the step escalates to the next person up the reporting line, and the audit trail records the escalation.
 4. The routing result is stored as approval_step rows and does not change after routing, except by escalation.
+5. If an approver in a step has a delegate record that covers the day of routing, the step is assigned to the approver and to the delegate. Either one may decide it, and the first decision closes the step.

@@ -148,7 +149,7 @@ Owner: the finance policy team. Applies to every decision, in every environment.
 3. The people in the steps of one report must all be different people.
-4. A delegate may act only for dates inside the delegate record, and never on a report that the delegator submitted.
+4. A delegate acts only for dates inside the delegate record. A delegate never acts on a report that the delegator submitted.
 5. Limits per step. A line manager's approval counts only for a base total up to 5,000.00. A department head's approval counts up to 25,000.00. Nothing above 25,000.00 can be approved in the service (section 3.5).
```

```text
$ python3 scripts/render_ground_truth.py ground-truth/architecture.md --root . --version 0.4 --date 2027-02-10
wrote docs/ground-truth/architecture.md: 345 lines, 31 headings, 0 figures
wrote docs/ground-truth/architecture.index.txt
1 document(s) rendered
recorded content_sha256 and rendering_sha256 for architecture in the workspace plan
[exit 0]
```

The new rendering replaced the working copy, but the reviewed rendering is safe in the checkpoint, so the agent can compare the two. The agent runs `prepare` as a dry run first. It prints the counts sentence, one line for each changed block, and the work items that cite a changed block. It also names the items that a block touches without citing it. A scheduling or integration link alone needs no rewrite, so the agent reads those items instead of patching them.

```text
$ python3 scripts/reconcile.py prepare --root .
carrydown update: compare changed sources  DRY RUN (nothing will be written)
2 changed block(s) in 1 source(s); 7 direct consumer(s); index: 20591 bytes, 2016 words, about 5148 tokens (approximate)
  architecture/3.5  modified  was "3.5 Routing", now "3.5 Routing"  formatting only: no
  architecture/4.1  modified  was "4.1 GOV-1 Approval limits and separation of duties", now "4.1 GOV-1 Approval limits and separation of duties"  formatting only: no

Direct consumers (who cites a changed block):
  block                        work item relationship       cites     working copy
  architecture/3.5             WI-03     citation           3.5       matches the released copy
  architecture/3.5             WI-06     citation           3.5       matches the released copy
  architecture/3.5             WI-08     citation           3.5       matches the released copy
  architecture/3.5             WI-11     citation           3.5       matches the released copy
  architecture/4.1             WI-01     contract           -         matches the released copy
  architecture/4.1             WI-02     contract           -         matches the released copy
  architecture/4.1             WI-04     citation           4.1       matches the released copy
  architecture/4.1             WI-06     citation           4.1       matches the released copy
  architecture/4.1             WI-08     citation           4.1       matches the released copy
  architecture/3.5 also touches, without citing it (a scheduling or integration link alone needs no rewrite): WI-01 (dependency, integration), WI-02 (integration), WI-04 (dependency, integration), WI-07 (dependency, integration), WI-09 (dependency, integration)
  architecture/4.1 also touches, without citing it (a scheduling or integration link alone needs no rewrite): WI-03 (dependency, integration), WI-07 (integration), WI-11 (dependency)

Nothing was written. Add --apply to save the proposal in the private workspace.
proposal: bcb1656ed6f562559afe5946bacfeb91ba57c0aedc0bb48d6ba6269e5f7cd340
[exit 0]
```

The same command with `--apply` saves the proposal in the private workspace: the inputs and their digests, the changed blocks, the consumers, the impact index and a `dispositions.json` that starts with every block marked `pending`. The impact index lists every work item, so the agent can look beyond the citations. Here the routing rule also reaches the approver inbox, WI-04, which does not cite section 3.5.

### One disposition for every changed block

The agent reads the changed text and the work items that depend on it, then proposes one disposition for each block. Until it does, `check` refuses the proposal and names what is missing.

```text
$ python3 scripts/reconcile.py check --root . --proposal <proposal>
carrydown update: check
  - pending-disposition: architecture/3.5 still has a pending disposition. Decide it with the owner before applying
  - pending-disposition: architecture/4.1 still has a pending disposition. Decide it with the owner before applying
carrydown: proposal bcb1656ed6f562559afe5946bacfeb91ba57c0aedc0bb48d6ba6269e5f7cd340 has 2 finding(s)
[exit 1]
```

The filled `dispositions.json` follows. The agent wrote both records and showed them in one review to the owner, who accepted them. The block 3.5 is an `update`. It carries two patches, the routing specification (WI-03) and the inbox specification (WI-04), each with the digest of the file it was written against and the full text after the change. The block 4.1 is `no-impact`, with the reason and the context that supports it. Here the long fields are shortened. A patch holds the whole text of the file.

```json
{
  "format": 1,
  "dispositions": [
    {
      "block": "architecture/3.5",
      "disposition": "update",
      "item": "WI-03",
      "patch": [
        {
          "item": "WI-03",
          "path": "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md",
          "before_sha256": "23b6e60ae3ca...",
          "after_text": "<the whole file, 13913 characters>"
        },
        {
          "item": "WI-04",
          "path": "docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md",
          "before_sha256": "f5192fe752fb...",
          "after_text": "<the whole file, 14401 characters>"
        }
      ],
      "note": "Routing assigns a step to the approver and the delegate (WI-03). The inbox lists it for both (WI-04). WI-06, WI-08 and WI-11 cite section 3.5 and were read. Their text does not conflict with a second person on a step."
    },
    {
      "block": "architecture/4.1",
      "disposition": "no-impact",
      "reason": "Item 4 was split into two sentences. The rule is the same: the delegate dates and the delegator's own report.",
      "context": "WI-04, WI-06 and WI-08 cite 4.1. WI-06 states both conditions in its rule 4 and its GOV-1.4 acceptance criterion, and WI-08 leaves the decision to GOV-1.4 on the server."
    }
  ]
}
```

```text
$ python3 scripts/reconcile.py check --root . --proposal <proposal>
carrydown update: check
carrydown: proposal bcb1656ed6f562559afe5946bacfeb91ba57c0aedc0bb48d6ba6269e5f7cd340 has 0 finding(s)
[exit 0]
```

Zero findings means the proposal is fresh, every changed block has exactly one valid disposition, every patch stays inside the allowed draft paths and no patch rewrites a recorded decision. It does not mean the update is right. The owner decides that, in the one consolidated review.

### Applying the accepted update

After the owner says yes, the agent runs `apply` as a preview, reads it, then writes. Each write goes through the release gate as a draft write, only when the file still holds the digest the patch was written against, and is read back.

```text
$ python3 scripts/reconcile.py apply --root . --proposal <proposal>
carrydown update: apply  DRY RUN (nothing will be written)
  would change project/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md  (23b6e60ae3ca to 695d5b0b290d, 13913 bytes)
  would change project/docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md  (f5192fe752fb to e733c540dd5c, 14401 bytes)
Nothing was written. Add --apply to write these changes.
proposal: bcb1656ed6f562559afe5946bacfeb91ba57c0aedc0bb48d6ba6269e5f7cd340
[exit 0]

$ python3 scripts/reconcile.py apply --root . --proposal <proposal> --apply
carrydown update: applied 2 patches now and checked 2 patches by reading it back.
The working drafts are changed. The released copy is not. Nothing is published.
Next: record the accepted source checkpoint with workspace.py checkpoint (preview first), then say: Put the plan on GitHub.
proposal: bcb1656ed6f562559afe5946bacfeb91ba57c0aedc0bb48d6ba6269e5f7cd340
[exit 0]
```

Each patch changed only the lines it needed. This is the difference in WI-03, a new rule and a new acceptance criterion. The WI-04 patch added one acceptance criterion in the same way.

```text
$ git diff -- docs/spec/m2-route-to-approvers/wi-03-routing-engine.md
@@ -63,6 +63,7 @@ Routing, section 3.5. The routing engine builds the steps when a report moves fr
 4. The routing result is stored as approval_step rows and does not change after routing, except by escalation.
+5. If an approver in a step has a delegate record that covers the day of routing, the step is assigned to the approver and to the delegate. Either one may decide it, and the first decision closes the step.

@@ -91,6 +92,7 @@ Decision request `{ "decision": "approve", "comment": "" }`. `decision` is `appr
 - [ ] When an approver is the submitter, the step moves up the reporting line (`tests/routing.engine.test.js`).
+- [ ] When the approver of a step has a delegate record that covers the day of routing, the step is assigned to both people, and the first decision closes it (`tests/routing.engine.test.js`).
```

The owner has accepted the revised source, so the agent records the new reviewed checkpoint with the same two steps as before, then asks `status` where things stand. The working drafts now differ from the active release, and the next action belongs to the publishing skill.

```text
$ python3 scripts/workspace.py checkpoint commit --root . --id <checkpoint> --apply
checkpoint c5fb6851fd32998e14c5b1e21854bb842ac065f05d5b56044f2b96c896b61bfa committed and read back. Recorded in workspace.yaml
[exit 0]

$ python3 scripts/reconcile.py status --root .
carrydown project status
State: Accepted drafts awaiting release
2 files of the working drafts differ from the active release.
Next: Continue with carrydown-plan-to-github. The owner says: Put the plan on GitHub.

What was checked: the working plan; the current renderings of the reviewed sources; the private workspace: reviewed checkpoints, saved updates, release and publication records.
What was not observed:
  Outstanding engineer requests were not observed: the publishing skill's authorized read has not run.
  Sources kept elsewhere were not observed. Only the renderings held in this project or in the private workspace were checked.
[exit 0]
```

### An engineer corrects a specification

Meanwhile an engineer works on WI-04 in a clone of the repository, with the engineers' skill. The first command for every item is the check. A good fetch records the engineer's baseline for the item.

```text
$ python3 docs/dev/skills/expense-approvals-dev/scripts/check_context.py WI-04
carrydown: approved context for WI-04 is ready
Read docs/context/wi-04.md. Do not open docs/ground-truth/ or any source.
baseline: request 59151c0c1a4033a36b7b1137f8a4ce0c7d9c1bafb1f190319e021a0ee009ec98, specification f5192fe752fb21fe57a468d18592d4652eb71b78d40ba7c7ff1a6c1c48e512a7
[exit 0]
```

The sample lets engineers record decisions. While the owner's update is still in progress, the engineer records one departure under "Decisions recorded" in the same pull request. It is the first entry, so it replaces the `None yet.` line.

```text
$ git diff docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md
@@ -152,4 +152,4 @@ The counterpart items on the Workflow track are WI-03 Approval routing engine, w
 ## Decisions recorded
 
-None yet.
+- 2027-02-22. Until the plan owner answers the request about delegates, the inbox lists only the steps assigned to the caller (pull request 14).
```

The check, run offline with `--no-refresh`, still exits 0. It shows the note and says it is not an approval. It also says the freshness was not confirmed, because the engineer's last refresh is inside the offline grace period.

```text
$ python3 docs/dev/skills/expense-approvals-dev/scripts/check_context.py WI-04 --no-refresh
carrydown: approved context for WI-04 is ready
Read docs/context/wi-04.md. Do not open docs/ground-truth/ or any source.
baseline: request 59151c0c1a4033a36b7b1137f8a4ce0c7d9c1bafb1f190319e021a0ee009ec98, specification f5192fe752fb21fe57a468d18592d4652eb71b78d40ba7c7ff1a6c1c48e512a7
note: 1 new note(s) under Decisions recorded in your copy of the specification. They are not an approval. The plan owner reviews them
warning: freshness not confirmed; within offline grace
[exit 0]
```

Anything else is not a decision note. When the engineer edits an acceptance criterion, which is approved text, the check exits 14 and says what to do.

```text
$ python3 docs/dev/skills/expense-approvals-dev/scripts/check_context.py WI-04 --no-refresh   # after editing an acceptance criterion
carrydown: the specification for WI-04 does not match its approved release
reason: the specification differs from its approved text outside Decisions recorded. Only new dated decision entries may be added there (body-changed)
file: docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md
Restore the approved file, or ask the plan owner. If a rule looks wrong, draft a Rule clarification request. Do not edit an approved specification outside what this project allows.
[exit 14]
```

An edit to an earlier approved entry gets the same exit 14, with the reason `entry-edited`. The committed sample has no approved entry, because every "Decisions recorded" section still says `None yet.`. The run below is from a temporary copy in which an engineer's entry in WI-03 was merged, the owner's update kept it, and the update was released (`release.py prepare`, `approve --local` and `export`, as the sample rebuild does). An engineer then edits that approved entry.

```text
$ python3 docs/dev/skills/expense-approvals-dev/scripts/check_context.py WI-03 --no-refresh   # after editing the approved old entry
carrydown: the specification for WI-03 does not match its approved release
reason: an earlier entry under Decisions recorded was changed or removed. Only new entries may be added (entry-edited)
file: docs/spec/m2-route-to-approvers/wi-03-routing-engine.md
Restore the approved file, or ask the plan owner. If a rule looks wrong, draft a Rule clarification request. Do not edit an approved specification outside what this project allows.
[exit 14]
```

### The engineer's request, not sent

The engineer's note records what they did. It does not change a rule. For that the engineer says to the agent:

> This specification seems wrong because the inbox spec lists the reports waiting for the caller, and the approved text says a delegate sees the approver's inbox, but it never says who the step is assigned to.

The generated skill drafts a `Rule clarification request` from the fields its `SKILL.md` lists, quoting only what the approved context holds, with the baseline from the last check. The sample names no recipient for requests, so the draft is addressed to the plan owner. The text below was written by hand from those fields. It is **not sent**: the skill holds no token, posts nothing by itself, and the engineer has not yet said yes to posting.

```text
Rule clarification request

Work item: WI-04, Approver inbox and decisions.
Place: "Outcome" and "Acceptance criteria" in docs/spec/m2-route-to-approvers/wi-04-approver-inbox.md.
Problem: The specification lists the reports waiting for the caller. FR-8 in the approved context says "The delegate sees the approver's inbox for that range." Neither text says who the approval step is assigned to when the approver has named a delegate, or whether a decision by one of them removes the report from the other's inbox.
Proposed question: Is the step assigned to both the approver and the delegate, and does the first decision close it?
Baseline: request 59151c0c1a4033a36b7b1137f8a4ce0c7d9c1bafb1f190319e021a0ee009ec98, specification f5192fe752fb21fe57a468d18592d4652eb71b78d40ba7c7ff1a6c1c48e512a7.
Unaffected work: The inbox page, the decision dialog and the error display do not depend on the answer and can continue. The delegate case of the inbox waits.
Next action for the plan owner: Decide accepted, declined or deferred on this issue.
```

Until the plan owner decides, the request stays `pending`. In the story above, the owner's decision is the source change at the start of this section. The publishing skill lists the outstanding requests and records the decision on the issue. Then the agent carries the owner's accepted decision into the update.

## What the API did not set

The run created the project, three fields, the Work unit iteration field with five iterations and a break, three views and 15 items with their values. The API did not set how the Table view groups and sorts, the Board column field, the Roadmap date fields and zoom, or the project workflows. The scripts print that list at the end, and the plan-to-github skill explains each click.

## Cleaning up

The scripts delete nothing. When you finish with a test repository, delete the repository and the project yourself in the GitHub settings. A token that can delete repositories is more power than the carrydown skills need.
