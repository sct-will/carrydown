# Verification

Run these after the writes. They only read.

```bash
python3 scripts/github_sync.py --root . --repo owner/name --verify
python3 scripts/github_project.py --root . --repo owner/name --verify
```

## What the sync verification checks

- All planned labels exist.
- One sub-epic per milestone exists.
- One issue per work item exists.
- Each sub-epic has exactly its work item issues as sub-issues.
- Each work item body has all seven headings.
- If there is an Epic, every sub-epic is under it and the roll-up comment exists.

## What the project verification checks

- Plan issues on the board, as a count against the plan.
- For Work unit, Track, Complete by and Checkpoint, how many items have a value.
- The views and their layouts.
- The number of iterations.

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
