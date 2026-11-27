# Contributing to carrydown

Thank you for helping. This page tells you how to report a problem, propose a change, run the checks and get a change reviewed. Please read the [code of conduct](CODE_OF_CONDUCT.md) first. If you are a coding agent working in this repository, read [AGENTS.md](AGENTS.md) too. It has the rules and the checks in short form.

## Report a problem

1. Search the existing issues first.
2. Open a new issue with the "Bug report" form. It asks which skill, which agent, which script and command, and for the dry run output.
3. Remove any token, password or private text from what you paste. If the problem is a security problem, do not open an issue. Follow [SECURITY.md](SECURITY.md).

## Ask a question or suggest a feature

Use the "Question" form for questions. Use the "Feature request" form for ideas. Say what you were trying to do before you say what you want built. The two skills stay small on purpose, so a request that makes the plan, the checker or a skill simpler is more likely to be accepted than one that adds a new concept.

## Propose a change

1. Open an issue first for anything larger than a typo, so we can agree on the approach.
2. Fork the repository and make a branch from `main`.
3. Make the change. Keep it small and focused.
4. Run the checks below.
5. Open a pull request. The template asks what changed, which script or skill it touches, the result of the checks, and whether the docs changed.

## The layout

| Path | What lives there |
| --- | --- |
| `scripts/` | The canonical Python scripts. Standard library only. |
| `templates/` | The canonical templates the scripts fill in. |
| `skills/<name>/` | Each skill: `SKILL.md`, `references/`, and its own copy of the scripts and templates it runs. |
| `sample/expense-approvals/` | The fictional sample and its worked output. |
| `docs/` | Method, inputs, troubleshooting, security notes and the recorded sample run. |

The scripts use the standard library only, so they run on a stock Python with no installation. That is why they do not use PyYAML. `plan.yaml` uses a small subset of YAML, a plain text format for settings, described at the top of `scripts/carrydown_lib.py`.

The installer copies only a skill's own folder, so each skill carries copies of the scripts and templates it needs. Edit the canonical files in `scripts/` and `templates/`, then refresh the copies:

```bash
python3 scripts/sync_skill_assets.py --apply
```

## Run the scripts yourself

You need no agent and no token for these three commands.

```bash
git clone https://github.com/sct-will/carrydown.git
cd carrydown
python3 scripts/check_specs.py --root sample/expense-approvals --report
python3 scripts/github_sync.py --root sample/expense-approvals --offline
python3 scripts/github_project.py --root sample/expense-approvals --offline
```

| Script | Purpose |
| --- | --- |
| `scripts/render_ground_truth.py` | `.docx` or `.md` to Markdown with a section index and figures. |
| `scripts/scaffold_spec.py` | Create `plan.yaml`, the README, milestone folders and stubs. Refresh headers. Add the checker to CI. |
| `scripts/check_specs.py` | Check specifications against `plan.yaml`. Print the load table and critical path. |
| `scripts/github_token.py` | Create and store a GitHub token safely, and check what it can do. |
| `scripts/github_sync.py` | Labels, sub-epics, issues, links and the Epic comment. |
| `scripts/github_project.py` | The GitHub Project board. |
| `scripts/github_repair.py` | Separate, previewed repairs to existing issue metadata after an accepted plan review. |
| `scripts/generate_dev_skill.py` | The engineers' skill folder. |
| `scripts/reconcile.py` | Agent-facing orchestration of a project update: state, preparation, checks and application of accepted draft changes. Local only, and it calls no model service. |
| `scripts/reconcile_core.py` | The pure comparison helpers that `reconcile.py` uses. Standard library only, and no network or token code. |
| `scripts/decision_overlay.py` | The validator for permitted decision notes, shared by the engineers' check and the independent verifier. |
| `scripts/workspace.py` | The private workspace. Its `checkpoint` subcommand records and reads back a reviewed source checkpoint. |
| `scripts/selftest.py` | The repository's own checks, with no token. |
| `scripts/lint_prose.py` | The prose style checks. |
| `scripts/sync_skill_assets.py` | Maintainers: copy scripts and templates into each skill folder. |

The reconciliation scripts are interfaces for the agent and for maintainers. They are not owner instructions. Do not put them, or the internal identifiers they print, in the README action tables, in owner-facing warnings or in the recovery steps for plan owners. The owner says "This changed: [describe the change or provide revised documents]." and "Resume the project update.", and the agent runs the scripts.

Every script has `--help`. Every script that writes to GitHub is a dry run unless you pass `--apply`. The scaffold and the skill generator write local files in the project only with `--apply`; the renderer writes them unless you pass `--dry-run`. The installer copies only a skill's folder, so each skill carries its own copy of the scripts and templates it runs. The top-level `scripts/` and `templates/` are the canonical copies.

## Run the checks locally

You need Python 3.9 or later. Node.js 22.20 or later is needed only for the skills installer. You do not need a GitHub token. No check writes to GitHub.

```bash
python3 scripts/selftest.py
python3 scripts/lint_prose.py
python3 scripts/check_specs.py --root sample/expense-approvals --report
python3 -m unittest discover -s tests -v
python3 scripts/sync_skill_assets.py --check
```

`selftest.py` does the following. It compiles every script, checks that the skill copies are current, runs the specification checker on the sample, and runs every script's `--help` and its dry run against the sample. It is the test expectation for a change: the dry run on the sample must still pass. `lint_prose.py` checks the style rules below.

If you changed the website, build it and run its tests too. They need Node.js 22 or later and, once, the browser the tests drive. [The website README](website/README.md) describes each test.

```bash
cd website
npm ci
npx playwright install chromium
npm run build
npm test
```

### What runs on a pull request

The checks on a pull request take about six minutes. The prose lint runs on every pull request. A change outside `website/` runs the self test on Ubuntu 24.04 with Python 3.9, the oldest version the scripts support, and on Windows with the current Python, the two acceptance scenario runs, and the six negative tests G1 to G6 in one job, one step each. A change to the website, or to a page it is built from (`docs/`, the README, the sample's README and images), runs the website build and tests without deploying. A pull request that changes only the website skips the Python jobs, and one that changes no page of the website skips the website job. The full self test matrix, every operating system on both Pythons, macOS included, runs on every push to `main`, every night at 03:17 UTC and on request from the Actions tab. The macOS runners can queue for twenty minutes, which is why they are not on the pull request path.

After you change a canonical script or template, preview the copies, read the preview, then apply:

```bash
python3 scripts/sync_skill_assets.py
python3 scripts/sync_skill_assets.py --apply
```

The unit tests install each skill into a temporary folder outside the checkout and run its scripts, so a skill that needs a file it does not carry fails the build. Two things stay fixed. There are exactly two skills you install, and `carrydown-plan-to-github` is the only skill that carries the GitHub client, the token reader and the release publication code. A change to a script that `carrydown-ground-truth` carries must not add a network call, a token read or an import of a publishing module. Put a comparison helper that both skills need in a shared local module.

The stronger specification check and the decision overlay validator land together. The engineers' check and the independent verifier must agree on one behavior, so a pull request that changes how one reads the "Decisions recorded" section, the receipt entries or the inputs of a work item changes the other in the same pull request, with tests for both. There is no old mode and no new mode.

If you change the checker, the plan format or a template, also regenerate the sample outputs you affect and run the checker on the sample again:

```bash
python3 scripts/check_specs.py --root sample/expense-approvals
```

If you change something that talks to GitHub, say in the pull request how you tested it. A dry run is not enough. Use a throwaway private repository of your own, and delete it afterward.

## Style rules for prose and comments

- Sentence-case headings.
- Short sentences. One idea each.
- US English spelling.
- No em dashes or en dashes. Use a comma, a period or the word "to".
- Spell out an acronym the first time it appears on a page.
- No marketing words.
- No AI vendor or model names, except in the list of agents in the install instructions.
- No credit lines for tools, in files or in commit messages.
- Dates are written YYYY-MM-DD.

`lint_prose.py` enforces the dash, vendor name, credit line and US spelling rules. The rest is for review.

## Commits

- Every commit has a real author. Set your name and your email address in git before you commit. A pull request with commits from an anonymous or placeholder identity will be asked to change.
- Write the message in the imperative: "Add the checker rule for X", not "Added" or "Adds".
- Do not add credit trailers or generated-by lines.
- Do not commit tokens, passwords, personal data or private documents.

## Review process

1. The checks run on your pull request. They must pass. The full matrix runs after the merge, so a change that passes on the pull request can still fail on `main`, and the maintainer will ask for a fix.
2. The maintainer reads the change, usually within a week. This is a one-person project, so replies may take time.
3. You may be asked for changes. Push them as new commits on the same branch.
4. When the change is approved the maintainer merges it. Squash merges are the default.
5. Changes that alter a script's behavior or a template get an entry in [CHANGELOG.md](CHANGELOG.md) under the next version.

## License of contributions

By contributing you agree that:

- everything you contribute (code, documents, templates, skills, the sample and any images) is licensed under the Apache License 2.0, see [LICENSE](LICENSE),
- you have the right to contribute it under those terms.
