# Sample: expense approvals

An AI agent plans the project around real people, then carries the architecture to every issue and every engineer's coding agent. Two skills you install, one skill is generated for your engineers.

This is a sample. The project is fictional. The people, the company and the numbers are made up. Replace all of it with your own material.

It shows what the two carrydown skills produce from a short ground truth, including the skill they generate for the engineers. It is a project after its release: the plan owner answered yes to the question "Can everyone who can read this repository see all of these documents and your staffing notes?", approved the exact outputs, and exported them with a receipt.

This folder is published twice. It lives in [the main carrydown repository](https://github.com/sct-will/carrydown) at `sample/expense-approvals/`, and it is the root of [the carrydown-sample repository](https://github.com/sct-will/carrydown-sample), where the carrydown scripts created the real issues and the project board from this plan. The README of that repository shows the renderings and the sample output.

## What is here

| Path | What it is | Made by |
| --- | --- | --- |
| `ground-truth/architecture.md` | The source document. About eight pages: context, requirements, architecture, two governance rules, a development standard, a business analyst note, interfaces and risks. A public, fictional fixture. A real project does not need its originals in git. | The plan owner |
| `people.yaml` | Two people with tracks, percent allocation (one at 100, one at 60), days off, and an advisor. A public, fictional fixture. In a real project this file lives in the private workspace and never in git. | The interview |
| `timeline.yaml` | Start date, target date, 11 weeks of work, a break week, the work owned outside the team, conventions. | The interview |
| `docs/ground-truth/architecture.md` | The rendering with a section index. Optional in a project: the checks pass without it. | `render_ground_truth.py` |
| `docs/ground-truth/architecture.index.txt` | One line per heading with its line number. | `render_ground_truth.py` |
| `docs/spec/plan.yaml` | The released plan: five milestones, nine work items, two tracks, one break, checkpoints. It holds ids and tracks for the people and, for each source, only an id, a name and a version. No name, no source path, no classification, no digest. | `release.py prepare`, from the owner's plan |
| `docs/spec/README.md` | Conventions, schedule, comment templates and the index. It names no source path. | `scaffold_spec.py` |
| `docs/spec/m*/milestone.md` | One file per milestone: the sub-epic content. | `scaffold_spec.py`, then written |
| `docs/spec/m*/wi-NN-*.md` | One specification per work item. It cites source sections as `architecture section 3.5` lines. | `scaffold_spec.py --stubs`, then written |
| `docs/context/wi-NN.md` and `wi-NN.bundle.json` | The approved context of each work item: the exact text of the sections it cites, the decisions that settle conflicts and what the text may be used for, with its integrity record. | `compile_bundles.py`, through `release.py prepare` |
| `docs/release/<request id>.receipt.json` | The public receipt of the release: its ids, state, audience, targets, source versions and the digest of every file. It carries local owner evidence, labeled not authenticated. | `release.py export` |
| `docs/dev/skills/expense-approvals-dev/` | The engineers' skill for this project, with `scripts/check_context.py`. | `generate_dev_skill.py`, the last step of `carrydown-plan-to-github` |
| `.github/workflows/check-specs.yml` and `tools/carrydown/` | The checker in continuous integration, and its copy. | `scaffold_spec.py --ci` |
| `.gitignore` | The four ignore lines the scaffold writes: `docs/source/`, `people.yaml`, `.carrydown/local.yaml` and `.carrydown/cache/`. | `scaffold_spec.py --init` |

Ids 5 and 10 are missing on purpose. They are work the plan does not schedule, owned outside the team (pilot team recruitment, finance sign-off), and appear in the specifications only as an "external input".

## Why the originals and the staffing are here

A real project does not copy staffing records or confidential originals into git. The sample keeps `people.yaml` and `ground-truth/architecture.md` because they are explicitly public and fictional, and because they let you run every step. `.gitignore` lists `people.yaml` the way a real project's would, and git still tracks the file here because it was added before the line.

The released project does not need them. A fresh clone with no private workspace, no original, no rendering and no `people.yaml` passes the checker (`check_specs.py --view released`, 0 findings) and the engineers' context check (`check_context.py WI-06`, exit 0 once the clone has an `origin` to refresh from). The line `people overlay not loaded: capacity, dates and names not checked` is expected there. Those planning checks run on the owner's machine, where the people file is.

The owner's side of the sample is a test fixture in the main carrydown repository, at `tests/fixtures/sample-workspace/`. It holds the owner's working plan, `drafts/plan.yaml`, with the classification of the source (`repo-readers`), the path of the original and of the rendering and their digests, and the release records: the snapshot, the manifest, the request, the local approval and the activation event. `python3 tests/rebuild_sample_release.py --check` rebuilds the whole release from this folder and compares every byte.

## Run it

From the root of the main carrydown repository. The renderer example writes to a separate folder inside the sample, `sample/expense-approvals/my-test/`, so it does not overwrite the shipped rendering. Git ignores that folder. Delete it when you are done.

```bash
python3 scripts/check_specs.py --root sample/expense-approvals
python3 scripts/check_specs.py --root sample/expense-approvals --view released
python3 scripts/check_specs.py --root sample/expense-approvals --report --people sample/expense-approvals/people.yaml
python3 scripts/render_ground_truth.py sample/expense-approvals/ground-truth/architecture.md --root sample/expense-approvals --out-dir my-test/ground-truth --version 0.3
python3 scripts/github_sync.py --root sample/expense-approvals --offline
python3 tests/rebuild_sample_release.py --check
```

None of these needs a token or the network. The `--offline` form of `github_sync.py` shows the plan without reading GitHub. To see the release commands on a throwaway copy of the sample, with the owner's working plan in place, read the first section of [the recorded run](https://github.com/sct-will/carrydown/blob/main/docs/sample-run.md) in the main repository: it shows `release.py preview`, `prepare`, `approve --local` and `export` with what each prints. Every command that writes is a dry run until you pass `--apply`. Use a throwaway repository of your own for any GitHub write, and add `--apply` only when you have read what it would do.

## On GitHub

The issues and the public board for this plan are in the sample repository: [its issues](https://github.com/sct-will/carrydown-sample/issues) and [the public board](https://github.com/users/sct-will/projects/2). Start with the board's Board view. The Roadmap view shows bars only after its date fields are chosen by hand once (Complete by, and Checkpoint for markers), because the script does not set them yet. That click is in the list `github_project.py` prints at the end of every run. The sample repository was published before the release layout existed, so its issues and files predate the approved contexts and the receipt until it is published again from this folder.

## Make it yours

Replace `ground-truth/architecture.md` with your document and say to your agent: "Set up a project plan from this document." Put "Use the carrydown-ground-truth skill." in front if it does not pick the skill up. The agent first asks who may see your documents. Answer for your own documents, not the sample's, and read [who may see your documents](https://github.com/sct-will/carrydown/blob/main/docs/setup.md#before-you-add-documents-who-may-see-them) before you copy anything into a project.
