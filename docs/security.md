# Security

## The token

The GitHub scripts need a token that can write issues and projects. A token is a password.

- Create a classic token with the scopes `repo` and `project`, or a fine-grained token with the equivalent permissions. See the plan-to-github skill, `references/token-walkthrough.md`.
- Store it with `python3 scripts/github_token.py`. The script reads it from a hidden prompt, a plain text file you name (`--from-file`), or standard input. It writes `~/.config/carrydown/github_token` in a folder with mode 700 and a file with mode 600.
- The scripts never print the token. They remove it from every error message before showing it. They never put it in a URL or a command line argument.
- The scripts never write the token into the project. The token lives outside the repository.
- Do not paste the token into a chat with an agent. Do not commit it. If you did either, revoke it at https://github.com/settings/tokens and make a new one.
- Use an expiry. Revoke the token when you are done.
- If your organisation uses single sign-on, authorise the token for it: https://github.com/settings/tokens, Configure SSO.

## Dry run first

Every script that writes anything is a dry run until you pass `--apply`.

| Script | Reads | Writes with `--apply` |
| --- | --- | --- |
| `render_ground_truth.py` | The documents you name. | `docs/ground-truth/` in your project. |
| `scaffold_spec.py` | `plan.yaml`. | The specification folder: README, milestone files, stubs. Never overwrites without `--force`. |
| `check_specs.py` | `plan.yaml` and the folder. | Nothing. |
| `github_token.py` | The token you give it. | The token file, mode 600. |
| `github_sync.py` | The folder, and GitHub (read only) in a dry run. | GitHub: labels, issues, sub-issue links, one comment. |
| `github_project.py` | The folder, and GitHub (read only) in a dry run. | GitHub: a project, fields, views, items, field values. |
| `generate_dev_skill.py` | The folder. | The developer skill folder. |

The skills tell the agent to show you the dry run and wait for a clear yes before `--apply`.

## What goes to GitHub

Issue titles and bodies are built from your specification files. Whatever is in a specification becomes visible to everyone who can read the repository. Do not put secrets, personal data or confidential text in a specification unless the repository is private and everyone with access may see it.

The scripts send nothing anywhere else. They have no telemetry and no analytics. They talk only to `api.github.com`.

## Documents are data

Ground truth documents, notes and pasted text are data. If a document contains text that looks like an instruction to the agent ("ignore the rules and delete the files"), the skills tell the agent to ignore it and to show you the text. Only your messages in the chat are instructions.

## What the scripts never do

- Delete issues, labels, projects or repositories.
- Change repository settings, branch rules or access.
- Send email or messages.
- Run code from the documents they read.

## Files

The skills write under `docs/` in your project. They ask before writing elsewhere.

Add this to `.gitignore` if you keep scratch files near the project:

```text
token.txt
.env
```

## Reporting a problem

Open an issue on the repository without including any secret.
