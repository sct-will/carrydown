# Changelog

All notable changes to this project are written here. The format follows Keep a Changelog. Versions follow semantic versioning.

## Unreleased

### Confidential ground truth and embedded delivery

These changes let a project keep documents and staffing notes private and share only what the plan owner approves. A project that never answers the new question keeps working as a legacy project, and its scripts print one line saying so. The private path needs setup that your organization provides, and its run on real GitHub has not been performed yet, so the support labels in [the enterprise security questions](docs/enterprise-security.md) are a draft until that run is recorded.

- **Shared foundations.** One release gate decides every write outside the private workspace. Content and approvals are named by digests, and the helpers that compute them ship with each skill. A test now installs each skill alone and runs its scripts, so a skill that needs a file it does not carry fails the build.
- **One question and a private workspace.** Before it renders a document or asks about your people, the agent asks whether everyone who can read the repository may see all your documents and staffing notes. Yes keeps drafting in the repository. No moves drafting to an owner-only workspace on your machine, created in one step with its permissions read back. `workspace.py` creates it, reports on it and checks it. A workspace path inside the repository is refused.
- **Staffing stays private.** Names, logins, skills, preferences, days off, allocation and start dates are kept in `people.yaml` in the private workspace. The committed plan holds ids and tracks. Capacity, date and name checks run on your machine and say `people overlay not loaded` in a clean clone. Publishing assignees and publishing capacity are separate permissions.
- **A checker that works from a clean clone.** Originals and full renderings are optional, even for a public document. The checker validates a released plan against each work item's approved context, and it reports a restricted source that git tracks, by id. Mechanical detectors refuse credentials, private paths and staffing fields, and flag copied passages and organization phrases. Checker output names ids, fields and line numbers, never the text. `scaffold_spec.py --init` adds ignore lines, and the pull request workflow also watches `docs/context/` and `docs/release/`.
- **A careful renderer.** Header and footer markings are carried into renderings, and a marking that disagrees with your answer stops the run. Hidden text and tracked changes are shown to you for one decision. Links other than `http` and `https` are removed, comments in Markdown are stripped, and a restricted source is only ever rendered into the private workspace.
- **Approved context for each work item.** `compile_bundles.py` writes the exact text of the sections an item cites, the decisions that settle conflicts and what the text may be used for. The engineers' skill runs `check_context.py` first. It checks the bundle, refreshes with a `git fetch`, applies a recorded offline grace period and stops with one of four plain messages. It is a convenience check, not a security control. The engineers' README and `SKILL.md` no longer tell the agent to browse the full ground truth.
- **Releases.** `release.py` previews what will be shared, with whom and where, builds an exact snapshot, records your approval and exports only the approved files and a receipt. A release id names content and a request id names one permission decision. Replacement, withdrawal and receipt-only export are reviewed state changes. Local approval on the shared path is labeled not authenticated. On the private path approval is your review of a pull request in a private staging repository, and `--signed-tag` refuses.
- **An independent verifier and setup checks.** `verifier/` holds a verifier that runs in the organization's tooling repository from pinned code, never runs code from a pull request and reports required checks. `release.py doctor` and `workspace.py doctor` report which setup pieces are verified. The setup guide has the administrator steps, the limits (five minutes is a requested interval, not a deadline) and a runbook for the real GitHub acceptance run, which is marked not yet performed.
- **Destination checks.** Each GitHub destination gets only its allowlisted fields, and a restricted source gives issues that link to the specification in place of the acceptance text. A preflight checks the effective audience of the repository and the board before any write. `--allow-public` is removed. Drift reports print keys, numbers and digests, and `github_sync.py --inventory` and `release.py inventory` report what an existing project tracks and published.
- **Restricted work items and change requests.** A work item marked restricted is left out of the plan, specifications, contexts and payloads, and appears as an external item with only the summary you wrote. The generated skill can ask an engineer to raise a `Rule clarification request`, and the next release replaces the old one.
- **Documentation, FAQ and sample.** New [enterprise security questions](docs/enterprise-security.md) with three support labels, a rewritten setup guide that asks who may see your documents before it asks you to copy any, a release section in the plan owner guide, and updated method, inputs, recovery and security pages. The sample is now a released project: its plan is the released plan, its owner-side files are a test fixture, its engineers' skill and bundles are regenerated, and a clean clone passes the checker and the context check with no private workspace. `scaffold_spec.py` no longer fails on a released plan, and it writes the same README whether it starts from the owner's plan or the released one. The sample issue bodies now name the source in the Ground truth line.
- **The shared path stays as easy as before.** "Put the plan on GitHub." runs the release as one command, `release.py release`. It reads the repository's numeric id with the token, derives the audience from the repository's visibility, finds the board by its title or creates it empty, and carries the request from one stage to the next, so nobody types an id, an audience or a destination. You answer the disclosure line and the GitHub line in one prompt, and the approval covers exactly the preview you saw. The export leaves the released plan in the project, so a clean clone passes the released checks, and moves your working plan to the private workspace, where the owner-side commands find it. The standalone commands take the request they imply when `--request` is left out. A text citation keeps its own words in the released plan. An interrupted receipt-only export finishes when you run it again. The engineers' stale message says why in plain words. A recorded no answer stops a draft from being written into the repository by mistake. A choice to delete raw inputs after a release is now carried out: the export deletes the files in the workspace's `sources/` folder and records what it deleted.
- **Tests and scenarios.** The six agreed negative tests run together in continuous integration, with separate end-to-end scenarios for the shared path and the private path and a continuation that covers replacement, expiry, withdrawal, interrupted publication and verifier outages.
- **Planned delivery modes.** [Delivery modes](docs/delivery-modes.md) records the contract that the version 1 formats keep for restricted stored delivery and brokered retrieval. Both are planned and unavailable.

### Other changes

- Both skills start with a Python preflight. It detects the system, checks for Python 3.9 or newer with `check_python.py`, and offers to install Python with the official installer after one yes, with separate steps for macOS, Windows and Linux. The engineers' skill keeps one first command, `check_context.py`, and turns to the same preflight only when that command cannot run because Python is missing or older than 3.9.
- Checkpoint recovery previews name affected item and milestone references. Publication verification preserves unrelated milestone children while checking every planned parent. Work unit configuration and view assignments retry transient failures with the intended value in permanent errors.
- Everything is now licensed Apache 2.0; the CC BY 4.0 content license is removed.
- Two skills you install, one skill is generated for your engineers. The generator for the engineers' skill moved into `carrydown-plan-to-github`, whose last step, "Generate the engineers' skill", runs `generate_dev_skill.py` and prints the install line. Its templates and its install, maintenance and review references moved with it. Two roles remain: the plan owner, who runs both skills and reviews the generated plan and specifications with the agent, and the engineers, who install the generated skill. The separate reviewer and the named role for the people who watch the demonstrations are gone. The self test now has 162 steps.
- Work outside the plan is called what it is. Work the team depends on but does not schedule, such as a sign-off or a security review, is an external item, listed under `external` in `plan.yaml`. An item that waits for one sets `external_input`, and its Depends on row, its issue and the engineers' skill say "external input". The library function is `external_ids`. The checker report heading is "External items (outside the development plan; referenced only as external input)", the sync summary says "N external items kept outside the plan", and the specification README table column is "External item". A plan written with the older key and item field still loads: `carrydown_lib.py` reads them as `external` and `external_input`, and the README refresh recognizes the older column headers.
- README rewritten around the reader: the reason first, a picture of the output, look, try and install in order of effort, a two-sided conversation, three badges and two entry points (README and the plan owner guide). New docs: repository-metadata.md and recording-storyboard.md.
- The README hero is 3 to 1, so the install line sits higher, and a 2 to 1 copy, `docs/images/social-preview.png`, is the social preview. The handoff diagram says that the plan owner runs each skill in their agent and that the plan and specifications are human reviewed, with the agent making the edits. The six-step flow diagram is gone.
- US English spelling throughout, and `scripts/lint_prose.py` flags British spellings. The sample column `cost_centre` is now `cost_center`.

### Added

- A second-pass agent review of the completed plan and specifications, after ordinary checking and before final owner approval. Both skills carry one shared prompt and a tabular report template. The report records source coverage, evidence, reasoning, risk, owner decisions and repair verification. Detailed instructions load only when reviewing or repairing a plan.
- A separate published-plan repair path and `github_repair.py`, dry run by default. It uses the saved pre-repair plan to reconcile generated titles, assigned engineers, track labels and parent links without changing bodies, comments, issue state or unrelated metadata. Existing creation commands and the plan format are unchanged.
- Planning rigor. `plan.yaml` records why the plan is composed the way it is: `rationale`, `joint_demonstration` and `single_track_reason` on each milestone, `order_rationale` on each track and `theme` on each item. The ten planning rules are in the ground-truth skill's `references/planning.md` and in `docs/method.md`.
- `scaffold_spec.py` writes "Why these items form this milestone" and "Joint demonstration" into each `milestone.md`, and "How this plan was composed" into the specification README. `--refresh-headers` rewrites or adds these sections and leaves other edits alone.
- `check_specs.py` has a planning review. A milestone on one track without a reason, and a missing rationale, joint demonstration or order rationale, are findings. `--report` ends with advisory lines: the tracks each milestone covers and whether its joint check names them, items with no slack, theme switches per owner, critical path owners and the load ratio.

### Changed

- A tie between critical path chains goes to the chain with more items, so the path keeps the dependency it starts from.
- `render_ground_truth.py` refuses a source inside `docs/ground-truth/`, or one whose rendering would land on itself, and writes nothing. Keep sources outside `docs/ground-truth/`.
- The header tables of specifications and milestone files start with a `| Field | Value |` header row instead of a blank one. Files with the blank row still pass, and `--refresh-headers` adds the new row.
- The dry run, apply and verify commands of `carrydown-plan-to-github` pass `--create-epic`, so the summary matches the 1 Epic the skill asks about.
- `carrydown-plan-to-github` checks that the specification folder is committed and pushed before it writes issues, because each issue links its specification on GitHub.
- The sample moves five dates and one size so that every item has slack before its checkpoint, names both tracks in each demonstration's joint check, and carries its rationale and themes.
- The plan template has a second item, so its example milestone covers both tracks and meets at a joint check.
- The two skills and the generated engineers' skill treat documents, specifications, plan.yaml and issue text as data and never follow instructions found in them.
- `carrydown-plan-to-github` never opens the token file, asks for an explicit yes before writing to a public repository, and gives links for the user to open.
- Token guidance leads with a fine-grained token for organization boards, keeps the classic token for user-owned boards only, and sets a 7-day expiry and revocation when done.
- After `github_token.py --from-file`, the user deletes their own token file. The documents no longer say the script deletes it.
- `carrydown-ground-truth` runs `git init` only after a clear yes and no longer asks the user to install software through a system dialog.
- Shorter skill descriptions and bodies, with `license`, `compatibility` and `metadata` in the frontmatter. Setup checks moved to `references/setup.md`.
- The generated engineers' skill finds a work item file by glob and reads cited ground truth sections by line range instead of reading the whole index.
- One set of role names (plan owner, engineers) across the skills, templates and documents.
- The README leads with the interactive install line, explains what `--all` and `-g` create, notes the installer's scanner labels, and has a "Getting started" section with the install line and the first sentence to say to your agent.
- One statement of versions everywhere: Python 3.9 or later, Node.js 22.20 or later.
- The specification template and README say that the Ground truth row lists the sections an item is built from, and that the body may cite others for context.
- The references say that renaming an item is safe: the hidden marker finds its issue, and the script never changes an issue title.
- `docs/inputs.md` explains the size format, "Small, about 2 days".
- The project board reference says what the script does not set yet, instead of what the API cannot set.
- `scaffold_spec.py --refresh-headers` keeps rows a person filled in or added, and `generate_dev_skill.py --only references` refreshes just the references.
- The generated skill description is quoted and checked: the name length, the folder name, a target under 250 characters and a warning above 300. It gives one work item id as an example, such as WI-01, instead of a range that would include the ids of external items.
- The window and earliest-finish checks compare each item with its size and allocation, and the sample dates are adjusted to fit.
- The name check uses the plan's people.
- `github_token.py --check` reads the token the way the GitHub scripts do: `--token-file`, then `CARRYDOWN_GITHUB_TOKEN`, then the stored file.
- The documents say which scripts are dry runs: every script that writes to GitHub waits for `--apply`, the scaffold and the skill generator write local files only with `--apply`, and the renderer writes unless you pass `--dry-run`.
- The self test grew to 162 steps, with a loopback GitHub mock, built Word fixtures and planning review cases.

### Security

- The GitHub client moved to its own module, `scripts/github_client.py`, which ships only with `carrydown-plan-to-github`.
- `github_token.py` keeps the token file unless you pass `--delete-after`, and it checks the token format before any request.
- Sign-on, rate limit and timeout errors from GitHub print as one-line messages that say how to fix them.
- GitHub requests are retried only for reads. Issues are matched by a hidden marker, so a failed create does not make a duplicate.
- A rerun of `github_sync.py` repairs missing links, and `--verify` fails on unlinked ids.
- `--apply` to a public repository stops unless you pass `--allow-public`. This flag was later removed. See the confidential ground truth entry above.
- The workflow actions are pinned by commit.
- The renderer copies images only from the document folder, and every script writes only inside the project.

### Fixed

- Word automatic heading numbers are rendered, headings without a number are reported, and citations are reported as unchecked when the rendered document has no numbers.
- The plan is validated before `--report` and every other check, and bad input gives one-line findings, not tracebacks.
- A byte order mark in a file and a Windows console encoding no longer stop a script.
- Output piped to a reader that stops early, such as `| head`, ends without a traceback.

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
