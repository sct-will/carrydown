# Sample: expense approvals

This is a sample. The project is fictional. The people, the company and the numbers are made up. Replace all of it with your own material.

It shows what the three carrydown skills produce from a short ground truth.

This folder is published twice. It lives in the main carrydown repository at `sample/expense-approvals/`, and it is the root of the repository https://github.com/sct-will/carrydown-sample, where the carrydown scripts created the real issues and the project board from this plan. The README of that repository shows the renderings and the sample output.

## What is here

| Path | What it is | Made by |
| --- | --- | --- |
| `ground-truth/architecture.md` | The source document. About eight pages: context, requirements, architecture, two governance rules, a development standard, a business analyst note, interfaces and risks. | The plan owner |
| `people.yaml` | Two people with tracks, percent allocation (one at 100, one at 60), days off, and an advisor. | The interview |
| `timeline.yaml` | Start date, target date, 11 weeks of work, a pause week, the program-owned items, conventions. | The interview |
| `docs/ground-truth/architecture.md` | The rendering with a section index. | `render_ground_truth.py` |
| `docs/ground-truth/architecture.index.txt` | One line per heading with its line number. | `render_ground_truth.py` |
| `docs/spec/plan.yaml` | The plan: five milestones, nine work items, two tracks, one pause, checkpoints. | The plan owner and the agent |
| `docs/spec/README.md` | Conventions, schedule, comment templates and the index. | `scaffold_spec.py` |
| `docs/spec/m*/milestone.md` | One file per milestone: the sub-epic content. | `scaffold_spec.py`, then written |
| `docs/spec/m*/wi-NN-*.md` | One specification per work item. | `scaffold_spec.py --stubs`, then written |
| `docs/dev/skills/expense-approvals-dev/` | The developer skill for this project. | `generate_dev_skill.py` |
| `.github/workflows/check-specs.yml` and `tools/carrydown/` | The checker in continuous integration, and its copy. | `scaffold_spec.py --ci` |

Ids 5 and 10 are missing on purpose. They belong to the program (pilot team recruitment, finance sign-off) and appear in the specifications only as a "program input".

## Run it

From the root of the repository. The renderer example writes to a separate folder, `my-test/`, so it does not overwrite the shipped sample. Delete that folder when you are done.

```bash
python3 scripts/render_ground_truth.py sample/expense-approvals/ground-truth/architecture.md --root sample/expense-approvals --out-dir ../../my-test/ground-truth --version 0.3
python3 scripts/check_specs.py --root sample/expense-approvals
python3 scripts/check_specs.py --root sample/expense-approvals --report
python3 scripts/github_sync.py --root sample/expense-approvals --offline
python3 scripts/github_sync.py --root sample/expense-approvals --repo YOUR-USER/YOUR-TEST-REPO
python3 scripts/github_project.py --root sample/expense-approvals --repo YOUR-USER/YOUR-TEST-REPO
```

The first three need no token and no network. The `--offline` form of `github_sync.py` shows the plan without a token and without reading GitHub. The full dry run on the last two lines reads GitHub, so it needs a token (run `python3 scripts/github_token.py` first) and a repository that exists. Both are dry runs. Use a throwaway repository of your own, and add `--apply` only when you have read what they would do. `docs/sample-run.md` at the top of the repository shows a real run.

## Make it yours

Copy the folder, replace `ground-truth/architecture.md` with your document, and say to your agent: "Set up a project plan from this document." Put "Use the carrydown-ground-truth skill." in front if it does not pick the skill up.
