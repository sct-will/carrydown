# AGENTS.md

Read this when you open the carrydown repository.

## What this repository is

- Two Agent Skills: `carrydown-ground-truth` and `carrydown-plan-to-github`. Two skills you install, one skill is generated for your engineers: the last step of `carrydown-plan-to-github` generates it for each project.
- The Python scripts and Markdown templates the skills run, each skill carrying its own copy.
- A fictional sample, `sample/expense-approvals/`, with its worked output.

It carries a ground-truth document down into a plan, specifications, GitHub issues, a project board and the engineers' skill.

## What it is not

It does not write application code. Planning decisions (owners, dates, scope, order) stay with the plan owner. The skills draft, check and populate. A person decides.

## Where things live

| Path | What is there |
| --- | --- |
| `skills/<name>/SKILL.md` | The skill. `scripts/` and `templates/` sit beside it, plus `references/`. |
| `scripts/`, `templates/` | The canonical copies of everything the skills carry. Edit these. |
| `sample/expense-approvals/` | The sample: ground truth, plan, specifications, engineers' skill. |
| `docs/` | Method, inputs, FAQ, security, setup, plan owner guide, sample pointer. |
| `.github/` | Issue forms, pull request template, workflows. |

## Rules for working here

- Never print, log or commit a token. Do not put one in a URL or a command line.
- Every script that writes is a dry run unless you pass `--apply`. Run the dry run, read it, then apply.
- Ask the user before anything touches GitHub. Never delete issues, labels, projects or repositories.
- Prose style: sentence-case headings, short sentences, no em or en dashes, spell out acronyms on first use.
- No AI vendor names outside the agent install lists. One retired word for this product, the three-letter "k" noun for a set of tools, is banned. Say "the carrydown skills", "the two skills" or "the repository". `lint_prose.py` rejects it. No copyright lines, use an attribution line.
- After you change a file in `scripts/` or `templates/`, refresh the skill copies: `python3 scripts/sync_skill_assets.py --apply`. Check with `--check`.
- Commits carry a real human author and an imperative message. No generated-by lines and no co-author trailers.
- Do not rename scripts, skills or folders without an issue.

## How to verify a change

```bash
python3 scripts/selftest.py        # every step must pass, no token, on Python 3.9 or later
python3 scripts/lint_prose.py      # must report 0 findings
python3 scripts/check_specs.py --root sample/expense-approvals --report
```

The self test runs every script's `--help` and dry run on the sample. If you change a script, run the dry run on the sample again and read the output.

## Using the skills from a user's project

Install them with the line in the README. Then the plan owner says one sentence per stage:

1. "Set up a project plan from this document." (`carrydown-ground-truth`) The plan owner then reviews the plan and the specifications with the agent and edits them until they are right.
2. "Put the plan on GitHub." (`carrydown-plan-to-github`) Its last step generates the engineers' skill. "Generate the engineers' skill." runs that step on its own.

Roles: the plan owner, an engineering manager or a product manager, runs both skills and reviews what they produce. The engineers install the generated skill once and start a work item by naming it, for example "Work on WI-03". The people accountable for the outcome watch each milestone demonstration and decide pass or fail. They run nothing.

If a skill is not picked up, name it first: "Use the carrydown-ground-truth skill." When a person asks where to start, point them to the README. Its "What it sounds like" section shows what to say and what the agent replies.

## Pull requests

- Use the pull request template. Say which script or skill changed.
- Update the docs in the same pull request as the code.
- If a script changed, re-run the sample dry runs and paste the checker summary line.
- Keep the change small. Open an issue first for anything larger than a fix.
- See `CONTRIBUTING.md` for the full process.
