# Verification

Run these after the writes. They only read.

```bash
python3 <skill>/scripts/github_sync.py --root . --repo owner/name --verify
python3 <skill>/scripts/github_project.py --root . --repo owner/name --verify
```

## What the sync verification checks

- All planned labels exist.
- One sub-epic per milestone exists.
- One issue per work item exists.
- Every issue has its planned title, managed body content and links, marker, required labels, planned assignee and parent. An explicit planned state is checked too. Unrelated labels and assignees remain.
- The repository and the board are still as visible as when they were last published: one visibility line for each, and a change since the last apply is a failure (`visibility CHANGED since publication`). For a release the audience also has to match, so a public repository for a release for repository readers is refused before anything is read.
- Each sub-epic has exactly its work item issues as sub-issues.
- Each work item body has all seven headings.
- If there is an Epic, every sub-epic is under it and the roll-up comment exists.

## What the project verification checks

- Membership of each planned issue on the board.
- Exact Work unit, Track, Complete by and Checkpoint values for each issue, with expected and actual values in every finding.
- The views and their layouts.
- The number of iterations.
- Visible managed fields on Table and Board after apply.

Apply runs verification automatically and returns nonzero for required drift. Use `github_sync.py --reconcile` for a minimal issue repair preview, then add `--apply` only after approval. Board dry runs preview missing membership, fields and options. Board apply repairs those and verifies the result. Run both verification commands because they cover different publication surfaces.

A drift finding names the plan key, the issue number and the field, with a short digest (SHA-256, twelve characters) of the expected and the actual value. It never prints an issue body or the title GitHub holds, because that text is data from outside. To see what differs, open the issue.

Issue identity prefers the verified mapping in `docs/spec/github-issues.json`. A tied candidate table requires the plan owner's selection through `--select-issue KEY=NUMBER`. Preview duplicate-marker neutralization before applying. No issue is deleted or closed.

## Expected counts

For a plan with M milestones and N work items:

| Thing | Expected |
| --- | --- |
| Labels | 2 plus the number of tracks |
| Sub-epics | M |
| Work item issues | N |
| Sub-issue links, sub-epic to work item | N |
| Sub-issue links, Epic to sub-epic | M, when an Epic exists |
| Board items | M + N, plus 1 for the Epic |
| Work unit filled | M + N |
| Track filled | N |
| Complete by and Checkpoint filled | M + N |
| Views | 3 |
| Iterations | M |

## States to report after an update

After a release that carries an approved update, report these states separately. Use text labels. Each is one of its two values. A state not reached yet is pending, never left out.

| State | Values | Where it comes from |
| --- | --- | --- |
| Draft reconciliation | accepted, or not yet accepted | The planning skill's apply step. |
| Release | approved, or not yet approved | `release.py release`, with the owner's approvals. |
| Engineering repository update | pending, or available | The committed and pushed release files (step 4 commit and push check). |
| Issue updates | pending, or verified | `github_sync.py --verify`. |
| Board updates | pending, or verified | `github_project.py --verify`. |
| Engineer action | required, with the work items, or none | The work items whose approved specification or context changed. |

Do not say "up to date" while a required publication step is pending. A verified surface says only that the managed content matches the release. Engineers can still hold old material: an offline checkout or an open conversation keeps what it had. Do not say that every engineer has received or understood the update. Tell the owner which work items need engineer action and what the engineer does: update the checkout through the normal reviewed repository update, reread the approved changes and reassess their plan.

## By hand

Open the project link. Check the Table view shows the fields. Open one issue and read its body from top to bottom. Check one dependency link and one sub-issue link. Then do the clicks listed in `project-board.md`.
