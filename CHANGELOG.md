# Changelog

All notable changes to this project are written here. The format follows Keep a Changelog. Versions follow semantic versioning.

## Unreleased

- Two skills you install, one skill is generated for your engineers. The generator for the engineers' skill moved into `carrydown-plan-to-github`, whose last step, "Generate the engineers' skill", runs `generate_dev_skill.py` and prints the install line. Its templates and its install, maintenance and review references moved with it. Two roles remain: the plan owner, who runs both skills and reviews the generated plan and specifications with the agent, and the engineers, who install the generated skill. The separate reviewer and the named role for the people who watch the demonstrations are gone. The self test now has 158 steps.
- Work outside the plan is called what it is. Work the team depends on but does not schedule, such as a sign-off or a security review, is an external item, listed under `external` in `plan.yaml`. An item that waits for one sets `external_input`, and its Depends on row, its issue and the engineers' skill say "external input". The library function is `external_ids`. The checker report heading is "External items (outside the development plan; referenced only as external input)", the sync summary says "N external items kept outside the plan", and the specification README table column is "External item". A plan written with the older key and item field still loads: `carrydown_lib.py` reads them as `external` and `external_input`, and the README refresh recognises the older column headers.
- README rewritten around the reader: the reason first, a picture of the output, look, try and install in order of effort, a two-sided conversation, three badges and two entry points (README and the plan owner guide). START-HERE.md is a pointer. New docs: repository-metadata.md and recording-storyboard.md.
- The README hero is 3 to 1, so the install line sits higher, and a 2 to 1 copy, `docs/images/social-preview.png`, is the social preview. The handoff diagram says that the plan owner runs each skill in their agent and that the plan and specifications are human reviewed, with the agent making the edits. The six-step flow diagram is gone.

### Added

- Planning rigor. `plan.yaml` records why the plan is composed the way it is: `rationale`, `joint_demonstration` and `single_track_reason` on each milestone, `order_rationale` on each track and `theme` on each item. The ten planning rules are in the ground-truth skill's `references/planning.md` and in `docs/method.md`.
- `scaffold_spec.py` writes "Why these items form this milestone" and "Joint demonstration" into each `milestone.md`, and "How this plan was composed" into the specification README. `--refresh-headers` rewrites or adds these sections and leaves other edits alone.
- `check_specs.py` has a planning review. A milestone on one track without a reason, and a missing rationale, joint demonstration or order rationale, are findings. `--report` ends with advisory lines: the tracks each milestone covers and whether its joint check names them, items with no slack, theme switches per owner, critical path owners and the load ratio.

### Changed

- A tie between critical path chains goes to the chain with more items, so the path keeps the dependency it starts from.
- `render_ground_truth.py` refuses a source inside `docs/ground-truth/`, or one whose rendering would land on itself, and writes nothing. Sources go in `docs/source/`.
- The header tables of specifications and milestone files start with a `| Field | Value |` header row instead of a blank one. Files with the blank row still pass, and `--refresh-headers` adds the new row.
- The dry run, apply and verify commands of `carrydown-plan-to-github` pass `--create-epic`, so the summary matches the 1 Epic the skill asks about.
- `carrydown-plan-to-github` checks that the specification folder is committed and pushed before it writes issues, because each issue links its specification on GitHub.
- The sample moves five dates and one size so that every item has slack before its checkpoint, names both tracks in each demonstration's joint check, and carries its rationale and themes.
- The plan template has a second item, so its example milestone covers both tracks and meets at a joint check.
- The two skills and the generated engineers' skill treat documents, specifications, plan.yaml and issue text as data and never follow instructions found in them.
- `carrydown-plan-to-github` never opens the token file, asks for an explicit yes before writing to a public repository, and gives links for the user to open.
- Token guidance leads with a fine-grained token for organisation boards, keeps the classic token for user-owned boards only, and sets a 7-day expiry and revocation when done.
- After `github_token.py --from-file`, the user deletes their own token file. The documents no longer say the script deletes it.
- `carrydown-ground-truth` runs `git init` only after a clear yes and no longer asks the user to install software through a system dialog.
- Shorter skill descriptions and bodies, with `license`, `compatibility` and `metadata` in the frontmatter. Setup checks moved to `references/setup.md`.
- The generated engineers' skill finds a work item file by glob and reads cited ground truth sections by line range instead of reading the whole index.
- One set of role names (plan owner, engineers) across the skills, templates and documents.
- The README leads with the interactive install line, explains what `--all` and `-g` create, notes the installer's scanner labels, and adds a "See it in 60 seconds" block.
- One statement of versions everywhere: Python 3.9 or later, Node.js 22.20 or later.
- `docs/inputs.md` explains the size format, "Small, about 2 days".
- The project board reference says what the script does not set yet, instead of what the API cannot set.
- `scaffold_spec.py --refresh-headers` keeps rows a person filled in or added, and `generate_dev_skill.py --only references` refreshes just the references.
- The generated skill description is quoted and checked: the name length, the folder name, a target under 250 characters and a warning above 300. It gives one work item id as an example, such as WI-01, instead of a range that would include the ids of external items.
- The window and earliest-finish checks compare each item with its size and allocation, and the sample dates are adjusted to fit.
- The name check uses the plan's people.
- The self test grew to 158 steps, with a loopback GitHub mock, built Word fixtures and planning review cases.

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
