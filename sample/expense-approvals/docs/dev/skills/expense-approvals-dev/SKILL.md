---
name: expense-approvals-dev
description: Use when working on a work item of the Expense approvals project in this repository, named by id (for example WI-01 or WI-11), by a file name such as wi-01-service-scaffold, or by its specification under docs/spec/. Gives the steps to orient on one item. The agent reads its specification, the ground truth sections it cites and the project conventions before changing code. Covers the definition of done, the test and lint commands, the work item index (9 items), the contract headings and the ground truth map.
---

# Expense approvals development

## Purpose

This skill orients a coding agent on one work item of the Expense approvals plan in this repository. Its conventions come from the plan folder, and its references are generated from the same files.

The specification folder `docs/spec/` is canonical. This skill carries its conventions and points at it. Where the skill and the folder disagree, the folder wins. Where a work item file and the ground truth disagree, the ground truth wins and the work item file is corrected in the same pull request.

## Orient on a work item

1. Take the id from the GitHub issue or the branch name, for example `WI-01` or `wi-01-service-scaffold`.
2. Find the file in `references/work-items.md`. The path is `docs/spec/<milestone folder>/<id>-<slug>.md`, for example `docs/spec/m1-submit-report/wi-01-service-scaffold.md`.
3. Read the whole work item file. Note its header table (milestone, track, target date, checkpoint, milestone demonstration, depends on, unblocks, ground truth sections), its acceptance criteria, its "Evidence of completion" section (what the closing comment carries) and its "Integration points" section (the counterpart items on the other track and the joint check).
4. Read only the ground truth sections the file cites, in `docs/ground-truth/architecture.md`. Use `references/ground-truth-map.md` for the anchors, or read a range with `sed -n 'START,ENDp'` using the line numbers in `docs/ground-truth/architecture.index.txt`.
5. Read the code the file names before changing it. Check each function and file name in the repository. If a detail cannot be verified, write "verify at implementation" and say what to look for.
6. Check that the items it depends on have landed. A dependency marked "program input" is provided by the program outside the plan. If it is missing, say so in the pull request and do not invent it.
7. Write a short plan in the pull request description before code. Name the files you will touch.

## Project conventions

Copied from `docs/spec/README.md`.

- Feature flag. `EXPENSE_APPROVALS_ENABLED` gates the new behaviour. Off by default until the release. With the flag off, nothing existing changes.
- Tests. Run `npm test`. New suites accompany each work item.
- Lint and format. `npm run lint` passes on every pull request.
- Contract tests pass with `npm run test:contract`, and a change to `contracts/openapi.yaml` is its own pull request.
- Secrets and personal data never appear in code, tests, logs or fixtures.
- Documentation style in this folder. Sentence-case headings, short sentences, no em dashes or en dashes, no names of people. Owners and dates live in the GitHub issues.
- Existing behaviour is not changed by a work item unless its file says so.

How to use a specification.

1. Read the whole file, then the code it points to. Open the ground truth only for the sections the file cites.
2. Propose the change in a short plan in the pull request description before writing code.
3. Work in small pull requests on `main`.
4. Prove each acceptance criterion with a test or a recorded check. The pull request lists them.
5. If the implementation departs from the file, append a short entry under "Decisions recorded" at the end of the file with the pull request number, in the same pull request.

## Definition of done

A work item is done when all of these hold.

- [ ] Every acceptance criterion in the work item file is proven by a named test or a recorded check, and the pull request lists each one with its proof.
- [ ] `npm test` and `npm run lint` pass, and the continuous integration run is green.
- [ ] With `EXPENSE_APPROVALS_ENABLED` off, existing behaviour and responses are unchanged.
- [ ] Contract tests pass with `npm run test:contract`, and a change to `contracts/openapi.yaml` is its own pull request.
- [ ] Secrets and personal data never appear in code, tests, logs or fixtures.
- [ ] Departures from the file are recorded under "Decisions recorded" with the pull request number. A conflict with the ground truth is fixed in the work item file in the same pull request.
- [ ] The closing comment on the issue follows the template in the specification folder README (Demo, Evidence, Decisions, Handoff) and carries every artifact named under "Evidence of completion". The agent assembles it, the developer checks and posts it.
- [ ] The joint check named under "Integration points" has run at the item's checkpoint with both tracks present, or the Handoff line says what still needs to run.

## Tests and workflow

- Run the tests with `npm test` before every commit. New work gets new tests.
- Run `npm run lint`. Fix findings instead of silencing them.
- Keep new behaviour behind `EXPENSE_APPROVALS_ENABLED`. With the flag off, existing behaviour is unchanged.
- Commit messages are in the imperative. The pull request description lists the acceptance criteria and the proof for each.
- Raw outputs, run records and screenshots go on the GitHub issue, not into the repository, unless the work item file says otherwise.

## Reference files

- `references/work-items.md`. The work item index with track, date, dependencies and specification path, and the program inputs.
- `references/contracts.md`. Where each contract is defined, with the headings of every Contract or Protocol section.
- `references/ground-truth-map.md`. Ground truth headings with anchors and line numbers, and the sections each work item cites.

Keep these files in step with the specification folder. When an item changes, run `generate_dev_skill.py` again or edit the reference by hand, and say so in the pull request.
