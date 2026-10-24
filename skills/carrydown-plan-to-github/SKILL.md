---
name: carrydown-plan-to-github
description: Use when a docs/spec folder with plan.yaml exists and the user wants the plan on GitHub. Walks through creating and storing a GitHub token safely, runs a dry run first, then after the user says yes creates labels, one sub-epic per milestone, one issue per work item with sub-issue links, dependency links and an Epic roll-up comment, and builds a GitHub Project (v2) board with work unit, track and date fields and table, board and roadmap views. Verifies the counts through the API and lists what must be clicked by hand. Start it when the user says exactly "Create the GitHub issues and the board." It also fits "put the plan on GitHub".
---

# Put the plan on GitHub

Start phrase: "Create the GitHub issues and the board."

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
- Never print, log, echo, paste or commit the token. Never ask the user to paste it into the chat. The token goes into a plain text file that the user names and that `github_token.py --from-file` reads, or into the hidden prompt of `github_token.py`. It ends up in a file with mode 600.
- Never put the token in a URL, a command line argument or an environment variable that gets logged.
- Do not delete issues, labels, projects or repositories. If something must be removed, tell the user how to do it themselves.
- Keep to the repository and owner the user named.

## Where the files are

The scripts folder and the templates folder are inside this skill, next to this SKILL.md. In the commands below, `<skill>` stands for the folder that holds this SKILL.md. Run the scripts with `python3` from the user's project root and pass `--root .`. On Windows the command is often `python` and not `python3`. Use whichever one runs Python 3.9 or later. Python 3.9 or later. No packages to install.

## The flow

### 1. Preconditions

```bash
python3 <skill>/scripts/check_specs.py --root .
```

It must report 0 findings. If it does not, stop and go back to `carrydown-ground-truth`. The sync script runs the checker again before it does anything.

Confirm with the user, in plain words: the repository (`owner/name`), whether a parent Epic issue exists (its number) or may be created, the people's GitHub logins if they should be assigned, and the owner of the project board (the user or the organisation). Put the repository, Epic number and project title in `plan.yaml` under `project`.

### 2. Token

Read `references/token-walkthrough.md`. The user creates a classic token in the browser with the pre-filled link https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown, which ticks `repo` and `project` for them. They set an expiry and copy the token when GitHub shows it. A fine-grained token also works for a project owned by an organisation, with Issues read and write, Metadata read and the organisation permission Projects read and write. It does not work for a project owned by a user account. Then pick one of two paths.

Preferred path, no terminal prompt. The user pastes the token into a plain text file (in TextEdit, Format then Make Plain Text before saving) and tells you the file path. They never paste the token into the chat. You run:

```bash
python3 <skill>/scripts/github_token.py --from-file <path> --repo owner/name
```

The script reads the file, stores the token at `~/.config/carrydown/github_token` with mode 600, asks GitHub who owns it and which scopes it has, and then deletes the file (`--no-delete-after` keeps it). It prints a message saying it deleted the file. If the message says it could not, ask the user to delete the file.

Alternative path. The user runs the script themselves in a terminal and types the token at a hidden prompt (nothing appears as they type):

```bash
python3 <skill>/scripts/github_token.py
```

Either way, then check:

```bash
python3 <skill>/scripts/github_token.py --dry-run                         # shows the steps, asks nothing
python3 <skill>/scripts/github_token.py --check --repo owner/name
```

`--check` says who owns the token, its scopes, and whether the repository is reachable with push access. If it says the repository is not reachable or that the token cannot push, tell the user they probably lack the organisation permission to create issues and Projects, and that an organisation administrator must grant it. If the organisation enforces single sign-on (SSO), the token must be authorised for it. In words: go to github.com/settings/tokens, find the token, click its "Configure SSO" button, and click "Authorize" next to the organisation, then run `--check` again. If a token already exists, run only `--check`.

### 3. Dry run of the issues

```bash
python3 <skill>/scripts/github_sync.py --root . --repo owner/name
```

Show the user the summary line, which reads exactly `1 Epic, N sub-epics, N work item issues` with the real numbers, and which of them exist already. Offer `--show-body ID` to print one issue body without any network call. Read `references/github-structure.md` so you can explain what each part is.

Ask: "This will create 1 Epic, N sub-epics and N work item issues in owner/name. Shall I go ahead?" Wait for a yes ("Go ahead.").

### 4. Apply

```bash
python3 <skill>/scripts/github_sync.py --root . --repo owner/name --apply
```

Add `--create-epic` if the user agreed to a new parent Epic, `--issue-type Task` if the organisation uses issue types, `--update-bodies` only if the user wants existing bodies rewritten. Then verify:

```bash
python3 <skill>/scripts/github_sync.py --root . --repo owner/name --verify
```

### 5. Project board

```bash
python3 <skill>/scripts/github_project.py --root . --repo owner/name            # dry run
```

Show the fields and views it would create. Ask for a yes. Then:

```bash
python3 <skill>/scripts/github_project.py --root . --repo owner/name --apply
python3 <skill>/scripts/github_project.py --root . --repo owner/name --verify
```

Read `references/project-board.md` for the fields, how breaks are made and what the API cannot set.

### 6. Tell the user what to click

The API cannot group a view, set the board column field, choose roadmap date fields or turn on the workflows. Give the user the list printed by `github_project.py` and the project URL. `references/project-board.md` has the steps.

### 7. After

Show the user the counts and the project link. Remind them of the rhythm: closing comment on every issue, a checkpoint comment each week, a demonstration note on each sub-epic. Suggest the next skill: `carrydown-dev-skill`.

## When something fails

Read `references/troubleshooting.md`. Do not retry blindly. Report the HTTP status and the message the script printed (the scripts redact the token) and propose the fix.
