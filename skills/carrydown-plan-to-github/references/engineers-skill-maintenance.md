# Keeping the engineers' skill current

The skill copies conventions and indexes from files that change. Treat it as a build product of the specification folder.

## When to regenerate

| Change | Action |
| --- | --- |
| A date, owner or dependency changes in `plan.yaml` | Refresh the headers with `scaffold_spec.py --refresh-headers --apply`, then regenerate the references. Then release the change: it reaches the engineers only through a new approved release. |
| A new version of a source is rendered | The approved contexts change. Release again: on the yes answer `release.py release` (step 3 of the skill), on the no answer `preview`, `prepare`, the approval and `export`. The release regenerates the bundles and `references/ground-truth-map.md`, and the engineers get them with the export. |
| A specification gains or loses a Contract or Protocol section | Regenerate `references/contracts.md`. |
| The conventions in the spec README change | Update `SKILL.md` in the same pull request. |
| An item is added or removed | Regenerate everything and review `README.md`. |
| The project changes whether engineers may edit approved text | Regenerate. The generated wording about change requests follows the policy, and a kept `SKILL.md` or `README.md` follows it only where the generated sentence is still word for word. |

The skill folder is part of the release: the release generates it in memory, keeps your hand edits to `SKILL.md` and `README.md`, and exports it with the other approved files. On an enrolled project, `generate_dev_skill.py --apply` refuses (`not-approved`) when no release is active. After a release it refuses to overwrite an approved file that differs from the release (`working-copy-differs`). Never edit `docs/context/` or `docs/release/`.

Both skills ship `scaffold_spec.py`. Run the header refresh from either skill's folder:

```bash
python3 <skill>/scripts/scaffold_spec.py --root . --refresh-headers --apply
```

It rewrites only the header tables and the sections written from the plan, and keeps rows that people filled in or added. It also works on a released plan.

Refresh the references with:

```bash
python3 <skill>/scripts/generate_dev_skill.py --root . --only references --apply
```

`--only references` replaces the three files under `references/` and nothing else, so it needs no `--force`. It leaves `SKILL.md` and `README.md` alone, so your hand edits stay. Pass `--force` without `--only` only when you want a fresh `SKILL.md` and `README.md`. Keep a copy of hand edits first, or regenerate into a scratch folder and merge.

## What the issues say

The sync script writes a line into every GitHub issue that points to the skill folder on the branch and tells the engineer to ask their agent to work on the item's id. Keep `project.dev_skill_path` stable once issues exist. If you move the folder, update `project.dev_skill_path` and run `github_sync.py --update-bodies`.

## Version

Skills installed with the command line tool are copies. After a change, everyone runs the install line again. Skills installed by symbolic link follow `git pull`.

## Retire

When the project ends, leave the skill in place. It is the record of how the work was carried out. Remove it from the agents with `npx skills remove` if it should no longer trigger.
