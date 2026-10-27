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

## By hand

Open the project link. Check the Table view shows the fields. Open one issue and read its body from top to bottom. Check one dependency link and one sub-issue link. Then do the clicks listed in `project-board.md`.
