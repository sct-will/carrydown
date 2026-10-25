## What changed

A short description of the change and why it is needed. Link the issue it closes.

## Which script or skill

- [ ] A script in `scripts/`:
- [ ] A template in `templates/`
- [ ] A skill (`skills/<name>/`):
- [ ] The sample
- [ ] Documentation only

## Checks

- [ ] `python3 scripts/selftest.py` passes. This runs the checker and the dry runs on the sample.
- [ ] `python3 scripts/lint_prose.py` passes.
- [ ] If I changed a script or template, I ran `python3 scripts/sync_skill_assets.py --apply` so the skill copies are current.
- [ ] If the change talks to GitHub, I tested it on a throwaway private repository and describe it below.

Checker result on the sample (paste the summary line):

```text
```

## Documentation

- [ ] README, docs or skill references updated where the change affects them.
- [ ] CHANGELOG.md has an entry under the next version, if behavior changed.

## Style

- [ ] Sentence-case headings, short sentences, no em or en dashes.
- [ ] No AI vendor names outside the agent install list, and no credit lines.
- [ ] No tokens, passwords or private text anywhere in the change.
- [ ] Every commit has a real author and an imperative message.

## Notes for the reviewer
