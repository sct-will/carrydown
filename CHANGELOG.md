# Changelog

All notable changes to this project are written here. The format follows Keep a Changelog. Versions follow semantic versioning.

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
