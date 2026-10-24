# Contributing to carrydown

Thank you for helping. This page tells you how to report a problem, propose a change, run the checks and get a change reviewed. Please read the [code of conduct](CODE_OF_CONDUCT.md) first.

## Report a problem

1. Search the existing issues first.
2. Open a new issue with the "Bug report" form. It asks which skill, which agent, which script and command, and for the dry run output.
3. Remove any token, password or private text from what you paste. If the problem is a security problem, do not open an issue. Follow [SECURITY.md](SECURITY.md).

## Ask a question or suggest a feature

Use the "Question" form for questions. Use the "Feature request" form for ideas. Say what you were trying to do before you say what you want built. The kit stays small on purpose, so a request that makes the plan, the checker or a skill simpler is more likely to be accepted than one that adds a new concept.

## Propose a change

1. Open an issue first for anything larger than a typo, so we can agree on the approach.
2. Fork the repository and make a branch from `main`.
3. Make the change. Keep it small and focused.
4. Run the checks below.
5. Open a pull request. The template asks what changed, which script or skill it touches, the result of the checks, and whether the docs changed.

## The layout

| Path | What lives there |
| --- | --- |
| `scripts/` | The canonical Python scripts. Standard library only, except `lxml` for Word files. |
| `templates/` | The canonical templates the scripts fill in. |
| `skills/<name>/` | Each skill: `SKILL.md`, `references/`, and its own copy of the scripts and templates it runs. |
| `sample/expense-approvals/` | The fictional sample and its worked output. |
| `docs/` | Method, inputs, FAQ, security notes and the recorded sample run. |

The installer copies only a skill's own folder, so each skill carries copies of the scripts and templates it needs. Edit the canonical files in `scripts/` and `templates/`, then refresh the copies:

```bash
python3 scripts/sync_skill_assets.py --apply
```

## Run the checks locally

You need Python 3.11 or later. You do not need a GitHub token. No check writes to GitHub.

```bash
python3 scripts/selftest.py
python3 scripts/lint_prose.py
```

`selftest.py` does the following. It compiles every script, checks that the skill copies are current, runs the specification checker on the sample, and runs every script's `--help` and its dry run against the sample. It is the test expectation for a change: the dry run on the sample must still pass. `lint_prose.py` checks the style rules below.

If you change the checker, the plan format or a template, also regenerate the sample outputs you affect and run the checker on the sample again:

```bash
python3 scripts/check_specs.py --root sample/expense-approvals
```

If you change something that talks to GitHub, say in the pull request how you tested it. A dry run is not enough. Use a throwaway private repository of your own, and delete it afterwards.

## Style rules for prose and comments

- Sentence-case headings.
- Short sentences. One idea each.
- No em dashes or en dashes. Use a comma, a period or the word "to".
- Spell out an acronym the first time it appears on a page.
- No marketing words.
- No AI vendor or model names, except in the list of agents in the install instructions.
- No credit lines for tools, in files or in commit messages.
- Dates are written YYYY-MM-DD.

`lint_prose.py` enforces the dash, vendor name and credit rules. The rest is for review.

## Commits

- Every commit has a real author. Set your name and your email address in git before you commit. A pull request with commits from an anonymous or placeholder identity will be asked to change.
- Write the message in the imperative: "Add the checker rule for X", not "Added" or "Adds".
- Do not add credit trailers or generated-by lines.
- Do not commit tokens, passwords, personal data or private documents.

## Review process

1. The checks run on your pull request. They must pass.
2. The maintainer reads the change, usually within a week. This is a one-person project, so replies may take time.
3. You may be asked for changes. Push them as new commits on the same branch.
4. When the change is approved the maintainer merges it. Squash merges are the default.
5. Changes that alter a script's behavior or a template get an entry in [CHANGELOG.md](CHANGELOG.md) under the next version.

## Licence of contributions

By contributing you agree that:

- code you contribute (the Python scripts and the workflow files) is licensed under the Apache License 2.0, see [LICENSE](LICENSE),
- content you contribute (the sample, the templates text, the skills prose, the documents and any images) is licensed under Creative Commons Attribution 4.0 International, see [LICENSE-CONTENT.md](LICENSE-CONTENT.md),
- you have the right to contribute it under those terms.
