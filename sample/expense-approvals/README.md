# Sample: expense approvals

This is a sample. The project is fictional. The people, the company and the numbers are made up. Replace all of it with your own material.

It shows what the three carrydown skills produce from a short ground truth.

## What is here

| Path | What it is | Made by |
| --- | --- | --- |
| `ground-truth/architecture.md` | The source document. About eight pages: context, requirements, architecture, two governance rules, a development standard, a business analyst note, interfaces and risks. | You |
| `people.yaml` | Two people with tracks, days off, and an advisor. | The interview |
| `timeline.yaml` | Start date, target date, 11 weeks of work, a pause week, the program-owned items, conventions. | The interview |
| `docs/ground-truth/architecture.md` | The rendering with a section index. | `render_ground_truth.py` |
| `docs/ground-truth/architecture.index.txt` | One line per heading with its line number. | `render_ground_truth.py` |
| `docs/spec/plan.yaml` | The plan: five milestones, nine work items, two tracks, one pause, checkpoints. | You and the agent |
| `docs/spec/README.md` | Conventions, schedule, comment templates and the index. | `scaffold_spec.py` |
| `docs/spec/m*/milestone.md` | One file per milestone: the sub-epic content. | `scaffold_spec.py`, then written |
| `docs/spec/m*/wi-NN-*.md` | One specification per work item. | `scaffold_spec.py --stubs`, then written |
| `docs/dev/skills/expense-approvals-dev/` | The developer skill for this project. | `generate_dev_skill.py` |
| `.github/workflows/check-specs.yml` and `tools/carrydown/` | The checker in continuous integration, and its copy. | `scaffold_spec.py --ci` |

Ids 5 and 10 are missing on purpose. They belong to the program (pilot team recruitment, finance sign-off) and appear in the specifications only as a "program input".

## Run it

From the root of the kit repository:

```bash
python3 scripts/render_ground_truth.py sample/expense-approvals/ground-truth/architecture.md --root sample/expense-approvals --version 0.3
python3 scripts/check_specs.py --root sample/expense-approvals
python3 scripts/check_specs.py --root sample/expense-approvals --report
python3 scripts/github_sync.py --root sample/expense-approvals --repo YOUR-USER/YOUR-TEST-REPO
python3 scripts/github_project.py --root sample/expense-approvals --repo YOUR-USER/YOUR-TEST-REPO
```

The last two are dry runs. Use a throwaway repository of your own, and add `--apply` only when you have read what they would do. `docs/sample-run.md` at the top of the repository shows a real run.

## Make it yours

Copy the folder, replace `ground-truth/architecture.md` with your document, and ask your agent to use the `carrydown-ground-truth` skill.
