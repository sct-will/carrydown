# Changelog

All notable changes to this project are written here. The format follows Keep a Changelog. Versions follow semantic versioning.

## Unreleased

### Changed

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
