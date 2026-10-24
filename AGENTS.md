# AGENTS.md

Read this when you open the carrydown repository.

## What this repository is

- Three Agent Skills: `carrydown-ground-truth`, `carrydown-plan-to-github` and `carrydown-dev-skill`.
- The Python scripts and Markdown templates the skills run, each skill carrying its own copy.
- A fictional sample, `sample/expense-approvals/`, with its worked output.

It carries a ground-truth document down into a plan, specifications, GitHub issues, a project board and a developer skill.

## What it is not

It does not write application code. Planning decisions (owners, dates, scope, order) stay with people. You draft, check and populate. A person decides.

## Where things live

| Path | What is there |
| --- | --- |
| `skills/<name>/SKILL.md` | The skill. `scripts/` and `templates/` sit beside it, plus `references/`. |
| `scripts/`, `templates/` | The canonical copies of everything the skills carry. Edit these. |
| `sample/expense-approvals/` | The sample: ground truth, plan, specifications, developer skill. |
| `docs/` | Method, inputs, FAQ, security, setup, plan owner guide, sample pointer. |
| `.github/` | Issue forms, pull request template, workflows. |

## Rules for working here

- Never print, log or commit a token. Do not put one in a URL or a command line.
- Every script that writes is a dry run unless you pass `--apply`. Run the dry run, read it, then apply.
- Ask the user before anything touches GitHub. Never delete issues, labels, projects or repositories.
- Prose style: sentence-case headings, short sentences, no em or en dashes, spell out acronyms on first use.
- No AI vendor names outside the agent install lists. One retired word for this product, the three-letter "k" noun for a set of tools, is banned. Say "the carrydown skills", "the three skills" or "the repository". `lint_prose.py` rejects it. No copyright lines, use an attribution line.
- After you change a file in `scripts/` or `templates/`, refresh the skill copies: `python3 scripts/sync_skill_assets.py --apply`. Check with `--check`.
- Commits carry a real human author and an imperative message. No generated-by lines and no co-author trailers.
- Do not rename scripts, skills or folders without an issue.

## How to verify a change

```bash
python3 scripts/selftest.py        # every step must pass, no token, on Python 3.9 and 3.12
python3 scripts/lint_prose.py      # must report 0 findings
python3 scripts/check_specs.py --root sample/expense-approvals --report
```

The self test runs every script's `--help` and dry run on the sample. If you change a script, run the dry run on the sample again and read the output.

## Using the skills from a user's project

Install them with the line in the README. Then the user says one sentence per stage:

1. "Set up a project plan from this document." (`carrydown-ground-truth`)
2. "Create the GitHub issues and the board." (`carrydown-plan-to-github`)
3. "Generate the developer skill." (`carrydown-dev-skill`)

Roles: the Plan owner runs the skills, a Lead reviewer reads the specifications for about an hour, the Engineers use the generated developer skill every day, and the Program only attends the demonstrations. The README has the table.

If a skill is not picked up, name it first: "Use the carrydown-ground-truth skill." The steps with expected output are in the README under Getting started. The long form, for the person who owns the plan, is `docs/plan-owner-guide.md`.

## Pull requests

- Use the pull request template. Say which script or skill changed.
- Update the docs in the same pull request as the code.
- If a script changed, re-run the sample dry runs and paste the checker summary line.
- Keep the change small. Open an issue first for anything larger than a fix.
- See `CONTRIBUTING.md` for the full process.
