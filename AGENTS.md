# AGENTS.md

Read this when you open the carrydown repository.

## What this repository is

- Two Agent Skills: `carrydown-ground-truth` and `carrydown-plan-to-github`. Two skills you install, one skill is generated for your engineers: the last step of `carrydown-plan-to-github` generates it for each project. The first skill covers initial planning and updates to an existing project. The second publishes.
- The Python scripts and Markdown templates the skills run, each skill carrying its own copy.
- A fictional sample, `sample/expense-approvals/`, with its worked output.

It carries a ground-truth document down into a plan, specifications, GitHub issues, a project board and the engineers' skill. When the project changes, it compares the change with the reviewed sources and the current work, and carries the approved update down again.

## Product intent

carrydown extends isolated specifications with three connected capabilities:

- **Project decisions stay connected across work items.** The plan and specifications use agreed sources. Dependencies, shared interfaces and acceptance criteria are reviewed together for gaps and conflicts.
- **Decisions and sources reach each coding agent.** The generated project skill checks approved inputs and directs the agent to read the specification, cited source excerpts and project conventions before planning code.
- **The handoff stays aligned through reviewed changes.** Updates assess potentially affected work, preserve engineer corrections that still fit and return conflicts to the plan owner. The owner decides what changes and approves publication.

## What it is not

It does not write application code. Planning decisions (owners, dates, scope, order) stay with the plan owner. The skills draft, check and populate. A person decides.

## Where things live

| Path | What is there |
| --- | --- |
| `skills/<name>/SKILL.md` | The skill. `scripts/` and `templates/` sit beside it, plus `references/`. |
| `scripts/`, `templates/` | The canonical copies of everything the skills carry. Edit these. |
| `scripts/reconcile.py`, `scripts/reconcile_core.py` | The local update workflow for the agent, and its pure comparison helpers. No network, no token, no model call. |
| `scripts/decision_overlay.py` | The validator for permitted decision notes. The engineers' check and the independent verifier share it. |
| `scripts/workspace.py` | The private workspace. `workspace.py checkpoint` records and reads back a reviewed source checkpoint. |
| `sample/expense-approvals/` | The sample: ground truth, plan, specifications, engineers' skill. |
| `docs/` | Method, inputs, troubleshooting, security, setup, plan owner guide, sample pointer. |
| `.github/` | Issue forms, pull request template, workflows. |
| `tests/acceptance/` | The runner and its tests for the acceptance run on real GitHub. The owner runs it once against a throwaway organization. |

## Rules for working here

- Never print, log or commit a token. Do not put one in a URL or a command line.
- Every script that writes to GitHub is a dry run unless you pass `--apply`. The scaffold and the skill generator write local files in the project only with `--apply`; the renderer writes them unless you pass `--dry-run`. Run the dry run, read it, then apply.
- Ask the user before anything touches GitHub. Never delete issues, labels, projects or repositories.
- Prose style: US English spelling, sentence-case headings, short sentences, no em or en dashes, spell out acronyms on first use.
- Exception: the website footer carries a copyright line, © 2026-present Will Scott, PhD.
- No AI vendor names outside the agent install lists. One retired word for this product, the three-letter "k" noun for a set of tools, is banned. Say "the carrydown skills", "the two skills" or "the repository". `lint_prose.py` rejects it. No copyright lines, use an attribution line.
- After you change a file in `scripts/` or `templates/`, refresh the skill copies: `python3 scripts/sync_skill_assets.py --apply`. Check with `--check`.
- Commits carry a real human author and an imperative message. No generated-by lines and no co-author trailers.
- Keep the two-skill boundary. Do not add a third skill. Only `carrydown-plan-to-github` carries the GitHub client, the token reader and the release publication code. The reconciliation scripts stay local, and `carrydown-ground-truth` must not import a publishing module.
- Source checkpoints stay in the private workspace. Never place a full rendering in a release snapshot or an upload input, and never push the workspace history.
- The stronger specification check and the decision overlay validator land together. Change the engineers' check and the independent verifier in the same pull request.
- Do not name the reconciliation scripts, a proposal identifier or a digest in owner-facing text. The owner says what changed. The agent runs the scripts.
- Do not rename scripts, skills or folders without an issue.

## How to verify a change

```bash
python3 scripts/selftest.py        # every step must pass, no token, on Python 3.9 or later
python3 scripts/lint_prose.py      # must report 0 findings
python3 scripts/check_specs.py --root sample/expense-approvals --report
python3 -m unittest discover -s tests -v
python3 scripts/sync_skill_assets.py --check
```

The self test runs every script's `--help` and dry run on the sample. If you change a script, run the dry run on the sample again and read the output.

If you change the website, also run `npm run build` and then `npm test` in `website/`.

A pull request runs the prose lint, and for a change outside `website/` the self test on Ubuntu 24.04 with Python 3.9 and on Windows with the current Python, the two acceptance scenario runs and the six negative tests in one job. A change to a page the website is built from (`website/`, `docs/`, the README, the sample's README and images) runs the website build and tests without deploying. The full self test matrix, macOS included, runs on every push to `main` and nightly, so a pass on a pull request is not the last word.

## Using the skills from a user's project

Follow the README's "Start here" link to the setup guide and install both skills there. The README's "What to tell your agent, and when" section has tables with the same phrases. The plan owner has three actions:

1. "Set up a project plan from these documents." (`carrydown-ground-truth`) The plan owner then reviews the plan and the specifications with the agent and edits them until they are right.
2. "Put the plan on GitHub." (`carrydown-plan-to-github`) Its last step generates the engineers' skill. "Generate the engineers' skill." runs that step on its own.
3. "This changed: [describe the change or provide revised documents]." (`carrydown-ground-truth`) The agent reviews the existing project, preserves engineer corrections and shows proposed updates for approval. "Resume the project update." continues an unfinished one. The approved update then goes through `carrydown-plan-to-github`.

The engineers have two actions, both through the generated skill: "Work on WI-03." starts a work item, and "This specification seems wrong because [explanation]." raises a specification problem as a drafted `Rule clarification request`. The skill holds no posting credential. It posts only when the engineer explicitly permits it and an authorized tool is available.

Roles: the plan owner, an engineering manager or a product manager, runs both skills and reviews what they produce. The engineers install the generated skill once and start a work item by naming it, for example "Work on [work item ID]". The stakeholders, the people accountable for the outcome, watch each milestone demonstration and decide pass or fail. They run nothing.

If a skill is not picked up, name it first: "Use the carrydown-ground-truth skill." For an update, "Use carrydown-ground-truth to update this existing project." When a person asks where to start, point them to the README. Its "Start here" section leads to the installation guide and the plan owner guide. The plan owner guide's "What the agent asks you" section shows the interview questions and what to answer.

## Pull requests

- Use the pull request template. Say which script or skill changed.
- Update the docs in the same pull request as the code.
- If a script changed, re-run the sample dry runs and paste the checker summary line.
- Keep the change small. Open an issue first for anything larger than a fix.
- See `CONTRIBUTING.md` for the full process.
