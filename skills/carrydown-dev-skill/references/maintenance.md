# Keeping the skill current

The skill copies conventions and indexes from files that change. Treat it as a build product of the specification folder.

## When to regenerate

| Change | Action |
| --- | --- |
| A date, owner or dependency changes in `plan.yaml` | `scaffold_spec.py --refresh-headers --apply`, then regenerate `references/work-items.md`. |
| A new version of the ground truth is rendered | Regenerate `references/ground-truth-map.md`, since line numbers move. |
| A specification gains or loses a Contract or Protocol section | Regenerate `references/contracts.md`. |
| The conventions in the spec README change | Update `SKILL.md` in the same pull request. |
| An item is added or removed | Regenerate everything and review `README.md`. |

Regenerate with:

```bash
python3 scripts/generate_dev_skill.py --root . --apply --force
```

`--force` replaces `SKILL.md` and `README.md` too. Keep a copy of hand edits first, or regenerate into a scratch folder and merge.

## What the sync script writes into issues

Each issue links to the skill folder on the branch. If you move the folder, update `project.dev_skill_path` and run `github_sync.py --update-bodies`.

## Version

Skills installed with the command line tool are copies. After a change, everyone runs the install line again. Skills installed by symbolic link follow `git pull`.

## Retire

When the project ends, leave the skill in place. It is the record of how the work was carried out. Remove it from the agents with `npx skills remove` if it should no longer trigger.
