---
name: carrydown-plan-to-github
description: Use when a docs/spec folder with plan.yaml exists and the user wants the plan on GitHub. Walks through creating and storing a GitHub token safely, runs a dry run first, then after the user says yes creates labels, one sub-epic per milestone, one issue per work item with sub-issue links, dependency links and an Epic roll-up comment, and builds a GitHub Project (v2) board with work unit, track and date fields and table, board and roadmap views. Verifies the counts through the API and lists what must be clicked by hand. Also use when the user says "create the GitHub issues and the board", "put the plan on GitHub", "create the issues" or "build the project board".
---

# Put the plan on GitHub

## What this skill does

It reads `docs/spec/plan.yaml` and the specification folder and builds, on GitHub:

- labels: one for the project, one per track, one for sub-epics,
- one sub-epic issue per milestone, with a body from `milestone.md`,
- one issue per work item with a templated body, as a sub-issue of its sub-epic,
- links from dependency ids to issue numbers,
- one roll-up comment with nested checkboxes on the parent Epic, if there is one,
- a GitHub Project (v2) board with a Work unit iteration field of custom lengths, a Track field, Complete by and Checkpoint date fields, and table, board and roadmap views, with every issue placed and every field filled.

The scripts are idempotent. Issues are matched by exact title, so a rerun creates nothing twice.

## Rules that never bend

- Ask before you write anything to GitHub. Always run the dry run first, show the user its summary, and wait for a clear yes. Writing means `--apply`. A yes to one run is not a yes to the next.
- Never print, log, echo, paste or commit the token. Never ask the user to paste it into the chat. The token goes into a hidden prompt of `github_token.py` and a file with mode 600.
- Never put the token in a URL, a command line argument or an environment variable that gets logged.
- Do not delete issues, labels, projects or repositories. If something must be removed, tell the user how to do it themselves.
- Keep to the repository and owner the user named.

## Where the files are

Scripts are in `scripts/` and templates in `templates/` inside this skill folder. Run them from the user's project root with `python3` and `--root .`. Python 3.9 or later. No packages to install.

## The flow

### 1. Preconditions

```bash
python3 scripts/check_specs.py --root .
```

It must report 0 findings. If it does not, stop and go back to `carrydown-ground-truth`. The sync script runs the checker again before it does anything.

Confirm with the user, in plain words: the repository (`owner/name`), whether a parent Epic issue exists (its number) or may be created, the people's GitHub logins if they should be assigned, and the owner of the project board (the user or the organisation). Put the repository, Epic number and project title in `plan.yaml` under `project`.

### 2. Token

Read `references/token-walkthrough.md`. In short:

```bash
python3 scripts/github_token.py --dry-run      # shows the steps, asks nothing
python3 scripts/github_token.py                # the user runs this; the input is hidden
python3 scripts/github_token.py --check --repo owner/name
```

The user creates a classic token with the scopes `repo` and `project` (or a fine-grained token with the equivalent permissions), pastes it into the hidden prompt, and the script stores it at `~/.config/carrydown/github_token` with mode 600 and checks its scopes. If the organisation enforces single sign-on (SSO), the token must be authorised for it. The walkthrough explains how. If a token already exists, run only `--check`.

### 3. Dry run of the issues

```bash
python3 scripts/github_sync.py --root . --repo owner/name
```

Show the user the summary: how many labels, sub-epics and issues, which exist already, the Epic decision. Offer `--show-body ID` to print one issue body without any network call. Read `references/github-structure.md` so you can explain what each part is.

Ask: "This will create N issues in owner/name. Shall I go ahead?" Wait for a yes.

### 4. Apply

```bash
python3 scripts/github_sync.py --root . --repo owner/name --apply
```

Add `--create-epic` if the user agreed to a new parent Epic, `--issue-type Task` if the organisation uses issue types, `--update-bodies` only if the user wants existing bodies rewritten. Then verify:

```bash
python3 scripts/github_sync.py --root . --repo owner/name --verify
```

### 5. Project board

```bash
python3 scripts/github_project.py --root . --repo owner/name            # dry run
```

Show the fields and views it would create. Ask for a yes. Then:

```bash
python3 scripts/github_project.py --root . --repo owner/name --apply
python3 scripts/github_project.py --root . --repo owner/name --verify
```

Read `references/project-board.md` for the fields, how breaks are made and what the API cannot set.

### 6. Tell the user what to click

The API cannot group a view, set the board column field, choose roadmap date fields or turn on the workflows. Give the user the list printed by `github_project.py` and the project URL. `references/project-board.md` has the steps.

### 7. After

Show the user the counts and the project link. Remind them of the rhythm: closing comment on every issue, a checkpoint comment each week, a demonstration note on each sub-epic. Suggest the next skill: `carrydown-dev-skill`.

## When something fails

Read `references/troubleshooting.md`. Do not retry blindly. Report the HTTP status and the message the script printed (the scripts redact the token) and propose the fix.
