# Changelog

All notable changes to this project are written here. The format follows Keep a Changelog. Versions follow semantic versioning.

## Unreleased

### Added

- Planning rigor. `plan.yaml` records why the plan is composed the way it is: `rationale`, `joint_demonstration` and `single_track_reason` on each milestone, `order_rationale` on each track and `theme` on each item. The ten planning rules are in the ground-truth skill's `references/planning.md` and in `docs/method.md`.
- `scaffold_spec.py` writes "Why these items form this milestone" and "Joint demonstration" into each `milestone.md`, and "How this plan was composed" into the specification README. `--refresh-headers` rewrites or adds these sections and leaves other edits alone.
- `check_specs.py` has a planning review. A milestone on one track without a reason, and a missing rationale, joint demonstration or order rationale, are findings. `--report` ends with advisory lines: the tracks each milestone covers and whether its joint check names them, items with no slack, theme switches per owner, critical path owners and the load ratio.

### Changed

- A tie between critical path chains goes to the chain with more items, so the path keeps the dependency it starts from.
- The sample moves five dates and one size so that every item has slack before its checkpoint, names both tracks in each demonstration's joint check, and carries its rationale and themes.
- The plan template has a second item, so its example milestone covers both tracks and meets at a joint check.
- The three skills and the generated developer skill treat documents, specifications, plan.yaml and issue text as data and never follow instructions found in them.
- `carrydown-plan-to-github` never opens the token file, asks for an explicit yes before writing to a public repository, and gives links for the user to open.
- Token guidance leads with a fine-grained token for organisation boards, keeps the classic token for user-owned boards only, and sets a 7-day expiry and revocation when done.
- After `github_token.py --from-file`, the user deletes their own token file. The documents no longer say the script deletes it.
- `carrydown-ground-truth` runs `git init` only after a clear yes and no longer asks the user to install software through a system dialog.
- Shorter skill descriptions and bodies, with `license`, `compatibility` and `metadata` in the frontmatter. Setup checks moved to `references/setup.md`.
- The generated developer skill finds a work item file by glob and reads cited ground truth sections by line range instead of reading the whole index.
- One set of role names (plan owner, lead reviewer, engineers, program) across the skills, templates and documents. The interview now asks who the lead reviewer is.
- The README leads with the interactive install line, explains what `--all` and `-g` create, notes the installer's scanner labels, and adds a "See it in 60 seconds" block.
- One statement of versions everywhere: Python 3.9 or later, Node.js 22.20 or later.
- `docs/inputs.md` explains the size format, "Small, about 2 days".
- The project board reference says what the script does not set yet, instead of what the API cannot set.
- The generated developer skill ships only the scripts it runs: `generate_dev_skill.py` and `check_specs.py`.
- `scaffold_spec.py --refresh-headers` keeps rows a person filled in or added, and `generate_dev_skill.py --only references` refreshes just the references.
- The generated skill description is quoted and checked: the name length, the folder name, a target under 250 characters and a warning above 300.
- The window and earliest-finish checks compare each item with its size and allocation, and the sample dates are adjusted to fit.
- The name check uses the plan's people.
- The self test grew to 153 steps, with a loopback GitHub mock, built Word fixtures and planning review cases.

### Security

- The GitHub client moved to its own module, `scripts/github_client.py`, which ships only with `carrydown-plan-to-github`.
- `github_token.py` keeps the token file unless you pass `--delete-after`, and it checks the token format before any request.
- Sign-on, rate limit and timeout errors from GitHub print as one-line messages that say how to fix them.
- GitHub requests are retried only for reads. Issues are matched by a hidden marker, so a failed create does not make a duplicate.
- A rerun of `github_sync.py` repairs missing links, and `--verify` fails on unlinked ids.
- `--apply` to a public repository stops unless you pass `--allow-public`.
- The workflow actions are pinned by commit.
- The renderer copies images only from the document folder, and every script writes only inside the project.

### Fixed

- Word automatic heading numbers are rendered, headings without a number are reported, and citations are reported as unchecked when the rendered document has no numbers.
- The plan is validated before `--report` and every other check, and bad input gives one-line findings, not tracebacks.
- A byte order mark in a file and a Windows console encoding no longer stop a script.

## 0.1.0

First release.

### Added

- Three Agent Skills: `carrydown-ground-truth`, `carrydown-plan-to-github` and `carrydown-dev-skill`, each with reference files.
- `scripts/render_ground_truth.py`: Word and Markdown input to Markdown with stable section anchors, a section index, a line index and figures.
- `scripts/scaffold_spec.py`: starter `plan.yaml`, specification README, milestone files, work item stubs, and header refresh.
- `scripts/check_specs.py`: mechanical checks of specifications, milestone files and the plan itself, plus a report with the load table and critical path.
- `scripts/github_token.py`: guided, safe token storage and scope check.
- `scripts/github_sync.py`: labels, sub-epics, work item issues, sub-issue links, dependency links and the Epic roll-up comment. Dry run by default.
- `scripts/github_project.py`: GitHub Project (v2) with a Work unit iteration field of custom length, Track, Complete by and Checkpoint fields, three views, and every issue placed and filled. Dry run by default.
- `scripts/generate_dev_skill.py`: the per-project developer skill.
- `scripts/sync_skill_assets.py`: copies scripts and templates into each skill folder.
- Templates for the plan, specification, milestone file, specification README, issue body, closing comment, checkpoint comment and developer skill.
- Sample project `sample/expense-approvals/` with its ground truth, inputs, plan, five milestones, nine specifications and generated developer skill.
- Documents: method, inputs checklist, FAQ, security notes and a recorded run of the sample.
- Repository conventions: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue forms (bug report, feature request, question, conduct report), a pull request template and `CODEOWNERS`.
- `scripts/selftest.py`, which runs the checker on the sample and every script's `--help` and dry run without a token, and `scripts/lint_prose.py`, which checks dashes, credit lines and vendor names.
- Two GitHub Actions workflows that run those two scripts on every push and pull request.
- `scripts/scaffold_spec.py --ci`, which adds the specification checker to continuous integration.
