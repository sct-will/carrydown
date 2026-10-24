---
name: carrydown-ground-truth
description: Use when a team wants to carry an architecture document, requirements, business analyst notes, governance rules or a development standard down into a governed plan with one specification per work item. Interviews the user for inputs, renders the documents to Markdown, scaffolds the docs/spec folder and plan.yaml, drafts milestones, work units, tracks, items, dates and dependencies with the human, writes milestone files and one specification per item to a template, and runs a checker. Also use when the user says "set up a project plan from this document", "plan this from the architecture document", "write the specs", "set up the spec folder" or "carry this document down".
---

# Carry a ground truth down into a plan

## What this skill does

A ground truth is the document a project must obey: an architecture document, requirements, a business analyst note, governance rules, a development standard. Often it is a Word file. This skill turns it into a plan that a coding agent and a person can both follow.

1. It interviews the user for the inputs.
2. It renders the documents to Markdown with stable section anchors.
3. It scaffolds `docs/spec/` with `plan.yaml`, a README and one folder per milestone.
4. It drafts the plan with the user: milestones, work units, tracks, items, dates, dependencies, load, critical path and the program boundary.
5. It writes `milestone.md` and one specification per work item to a fixed template.
6. It runs the checker, then adversarial review prompts on the document and on the plan.

The next skill, `carrydown-plan-to-github`, puts the plan on GitHub. The one after, `carrydown-dev-skill`, makes the developer skill.

## Rules that never bend

- Planning decisions stay with the human. You draft, the user decides. Never pick owners, dates, scope or order without an explicit yes.
- Ask before you write any file outside `docs/`, and never write to GitHub in this skill.
- Every claim in a specification traces to a section of the ground truth. If it cannot be traced or verified, write "verify at implementation" and say what to look for. Never invent a function name, a file or a number.
- Contract excerpts (schemas, rule texts, message texts) are copied word for word from the ground truth.
- Specifications never name people, never reference AI vendors, never use the program-owned ids. The checker enforces this.
- Prose style in everything you write: sentence-case headings, short sentences, no em dashes or en dashes, spell out an acronym on first use, no marketing words.

## Where the files are

The scripts and templates sit inside this skill folder, next to this file: `scripts/` and `templates/`. Run them with `python3` from the user's project root and pass `--root .`. Python 3.9 or later is enough. Reading a Word document needs the `lxml` package (`pip install lxml`). Run any script with `--help` to see its options. The scripts that write files are dry runs unless you pass `--apply`.

## The flow

### 1. Interview

Read `references/interview.md` and run the interview. Collect these, in small groups, and do not start before the user confirms your summary.

- The ground truth documents (any mix, `.docx` or `.md`), and which one wins when they disagree.
- The people: names or handles, the track each owns, start dates, days off, advisors who own no items.
- The time frame: a target date or a number of weeks, pause windows, the longest a work unit may run.
- The repository and organisation, whether a parent Epic exists, which labels exist.
- The agentic editors the team uses.
- Who watches the demonstrations.
- What the program owns and keeps outside the plan.
- Engineering conventions for the definition of done: test command, feature flag, lint command.

If the user wants to see the whole flow first, offer the sample in `sample/expense-approvals/` of the kit repository.

### 2. Render the ground truth

```bash
python3 scripts/render_ground_truth.py path/to/document.docx --root . --version 0.1
python3 scripts/render_ground_truth.py notes.md standards.md --root .
```

Use `--dry-run` first if the user wants to see what will be written. The output goes to `docs/ground-truth/<name>.md` with a section index, plus `<name>.index.txt` (one line per heading) and `figures/`. The source document stays the source of truth. Tell the user which headings have no numbers: specifications cite sections by number, so a numbered ground truth works best. Offer to renumber the source, not the rendering.

### 3. Scaffold

```bash
python3 scripts/scaffold_spec.py --root . --init --name "Project name" --apply
```

This writes a starter `docs/spec/plan.yaml` from `templates/plan.yaml`. Fill it in during step 4. When the plan is approved:

```bash
python3 scripts/scaffold_spec.py --root .                 # dry run
python3 scripts/scaffold_spec.py --root . --apply --stubs # README, milestone folders, one stub per item
```

### 4. Draft the plan with the user

Read `references/planning.md`. Work in this order and stop for a decision at each point.

1. Read the rendered ground truth end to end. List what must exist at the end, in the document's own words.
2. Propose milestones, each with an exit gate that someone can check at a demonstration.
3. Propose work units of variable length that fit the time frame and the pauses.
4. Propose work items with ids, labels, track, owner, size, dependencies and sections cited.
5. Set dates with the people's start dates and days off. Order work to avoid context switching and to put the shared contract first.
6. Show the load table and the critical path: `python3 scripts/check_specs.py --root . --report`.
7. Mark the program boundary. Program-owned items get an id gap and appear only as "program input".
8. Run an adversarial review of the plan with `references/review-prompts.md`. Start with this sentence, word for word: "List what is missing, wrong or improvable in this plan, reading it as each engineer would live it week by week." Fold in what the user accepts.

Save the result in `plan.yaml`. Run `check_specs.py --report` again. The plan section of the checker validates dates, owners, weekends, days off, cycles and checkpoints.

### 5. Write milestones and specifications

Read `references/writing-specs.md` and `references/milestone-and-demo.md`. Fill the TODO lines in each `milestone.md` and each stub. If your client supports subagents, write the specifications in parallel, one subagent per batch of two or three items, using `references/spec-writer-brief.md` as the brief. Otherwise write them one by one. Review every file yourself afterwards: the lead reads all of them.

When a specification finds a conflict inside the ground truth, resolve it in the specification (the ground truth wins; an earlier numbered section wins over a note), say so under "Watch out for", and list it for the next version of the document.

### 6. Check

```bash
python3 scripts/check_specs.py --root .
```

Fix every finding. `references/checker.md` explains each check. Offer to add the checker to continuous integration so it fails loudly on every pull request: `python3 scripts/scaffold_spec.py --root . --ci --apply` writes `.github/workflows/check-specs.yml` and copies the checker to `tools/carrydown/`. The same command runs locally. Re-run `scaffold_spec.py --refresh-headers --apply` after any change to dates, owners or dependencies, so the header tables follow the plan.

### 7. Review and hand off

Run the document and plan review prompts from `references/review-prompts.md` once more on the finished set. Show the user the index, the load table and the checker result. If a product manager is driving, recommend that a senior engineer spends an hour as lead reviewer of the generated specifications, reading them as the person who will build the item. Ask for approval. Then suggest the next skill: `carrydown-plan-to-github`.

## What good looks like

- Every item has a file that a coding agent can start from without opening the original document.
- Every acceptance criterion can be proven by a named test or a recorded check.
- Every milestone has an exit gate and acceptance criteria written before the work starts.
- The checker reports 0 findings, and the user has read the plan.
