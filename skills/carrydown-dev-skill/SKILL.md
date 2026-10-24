---
name: carrydown-dev-skill
description: Use when a project has a docs/spec folder with plan.yaml and the user wants a developer skill generated from it, so that a coding agent starts any work item by its id and reads the specification, the ground truth sections it cites and the project conventions before changing code. Generates the skill folder with SKILL.md, a README with install steps, and references for the work item index, contracts and ground truth map, then explains how each team member installs it in their agent. Start it when the user says exactly "Generate the developer skill." It also fits "install the skill for the team".
---

# Generate the developer skill

Start phrase: "Generate the developer skill."

## What this skill does

The specification folder is canonical, but a developer should not have to paste it into a prompt. A developer skill is a small folder in the Agent Skills format: a `SKILL.md` and reference files. Once installed, a developer says "work on WI-07" and the coding agent reads the specification, the ground truth sections it cites and the project conventions first.

This skill generates that folder from `plan.yaml`, the specifications and the rendered ground truth, then helps each person install it.

## Rules that never bend

- The specification folder wins over the skill. The generator copies conventions from the plan. It never invents contracts. Review what it wrote before you tell the user it is done.
- Do not put secrets, tokens or personal data in the skill.
- Ask before you write outside `docs/`.
- Style: sentence-case headings, short sentences, no em dashes or en dashes, spell out an acronym on first use.

## Where the files are

The scripts folder and the templates folder are inside this skill, next to this SKILL.md. In the commands below, `<skill>` stands for the folder that holds this SKILL.md. Run the scripts with `python3` from the user's project root and pass `--root .`. The generator is `<skill>/scripts/generate_dev_skill.py` and its templates are in the `dev-skill` folder inside the templates folder.

## The flow

### 1. Preconditions

- `docs/spec/plan.yaml` exists and `check_specs.py --root .` is clean (run `python3 <skill>/scripts/check_specs.py --root .`, using the copy in this skill's scripts folder).
- `project.dev_skill` (a lowercase name with hyphens) and `project.dev_skill_path` are set in `plan.yaml`. A good default is `<slug>-dev` at `docs/dev/skills/<slug>-dev`.
- The ground truth is rendered at `project.ground_truth`.
- `project.repo` and `project.branch` are set, so install lines can point at the folder on GitHub.

### 2. Dry run, then generate

```bash
python3 <skill>/scripts/generate_dev_skill.py --root .            # dry run
python3 <skill>/scripts/generate_dev_skill.py --root . --apply    # write
```

It writes `SKILL.md`, `README.md`, `references/work-items.md`, `references/contracts.md` and `references/ground-truth-map.md` under `project.dev_skill_path`. It skips files that exist unless you pass `--force`. It prints the length of the description, which must stay under 1,024 characters.

### 3. Review and finish by hand

Read `references/review-checklist.md` and go through it with the user. Add what only a person knows:

- extra triggers in the `description`, such as file names or folders the project cares about,
- module layout and flags, if the project has them,
- the contracts that matter most, with a pointer to the file that holds each,
- topics in the ground truth map, such as "retention" mapped to the sections that cover it.

### 4. Install

Read `references/install.md`. Each person installs the skill once in the agent they use. Give them the line for their agent from the generated README. Show them how to start a work item:

> Work on WI-07.

Then they review every change the agent makes.

### 5. Keep it current

Read `references/maintenance.md`. Regenerate the references whenever the plan, the specs or the rendering change. A pull request that changes the conventions in the spec README updates the skill in the same pull request.

## What the issues say

The sync script writes a line into every GitHub issue that points to this skill folder and tells the developer to ask their agent to work on the item's id. Keep `project.dev_skill_path` stable once issues exist, or update the issue bodies with `github_sync.py --update-bodies`.
