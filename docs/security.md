# Security

## The token

The GitHub scripts need a token that can write issues and projects. A token is a password.

- Use a 7-day expiry. For a board owned by an organisation, create a fine-grained token limited to the one repository, with Issues (read and write), Metadata (read) and the organisation permission Projects (read and write). For a board on your own account, create a classic token with the scopes `repo` and `project`, because GitHub does not let fine-grained tokens use those boards. See the plan-to-github skill, `references/token-walkthrough.md`.
- Store it with `python3 scripts/github_token.py`. The script reads it from a hidden prompt, a plain text file you name (`--from-file`), or standard input. It writes `~/.config/carrydown/github_token` in a folder with mode 700 and a file with mode 600.
- Before anything is sent, the script checks that the text looks like a GitHub personal access token (it starts with `ghp_` or `github_pat_`). If it does not, nothing is sent.
- With `--from-file`, the script keeps your file and tells you to delete it. It deletes the file only when you pass `--delete-after`.
- The scripts never print the token. They remove it from every error message before showing it. They never put it in a URL or a command line argument.
- The scripts never write the token into the project. The token lives outside the repository.
- Do not paste the token into a chat with an agent. Do not commit it. If you did either, revoke it at https://github.com/settings/tokens and make a new one.
- Revoke the token when the GitHub step is done.
- If your organisation uses single sign-on, authorise the token for it: https://github.com/settings/tokens, Configure SSO. The token check and the GitHub scripts say so in one line when GitHub asks for it.

## Dry run first

Every script that writes anything is a dry run until you pass `--apply`.

| Script | Reads | Writes with `--apply` |
| --- | --- | --- |
| `render_ground_truth.py` | The documents you name. | `docs/ground-truth/` in your project. |
| `scaffold_spec.py` | `plan.yaml`. | The specification folder: README, milestone files, stubs. Never overwrites without `--force`. |
| `check_specs.py` | `plan.yaml` and the folder. | Nothing. |
| `github_token.py` | The token you give it. | The token file, mode 600. It writes without `--apply`, after you give it a token. |
| `github_sync.py` | The folder, and GitHub (read only) in a dry run. | GitHub: labels, issues, sub-issue links, one comment. |
| `github_project.py` | The folder, and GitHub (read only) in a dry run. | GitHub: a project, fields, views, items, field values. |
| `generate_dev_skill.py` | The folder. | The developer skill folder. |

The skills tell the agent to show you the dry run and wait for a clear yes before `--apply`.

## What goes to GitHub

Issue titles and bodies are built from your specification files. Whatever is in a specification becomes visible to everyone who can read the repository. Do not put secrets, personal data or confidential text in a specification unless the repository is private and everyone with access may see it.

`github_sync.py --apply` refuses a public repository unless you pass `--allow-public`, because issue bodies carry text from your ground truth.

The scripts send nothing anywhere else. They have no telemetry and no analytics. They talk only to `api.github.com`.

## Network and token code

carrydown-plan-to-github is the only skill with network or token code. That code is in `github_client.py`, which ships with that skill only. It calls `api.github.com` and nothing else. carrydown-ground-truth and carrydown-dev-skill contain no network or token code, and neither does the checker copy that `scaffold_spec.py --ci` puts in your project.

To avoid creating anything twice, carrydown-plan-to-github reads back from your repository:

- the issues that carry the project label, and no others;
- the hidden marker at the end of each body, such as `<!-- carrydown:WI-07 -->`;
- on the Epic, only the roll-up comment written by the token's own account.

It treats that text as data. It compares it with the plan and never follows it. It prints issue titles from the plan, not from GitHub. It rewrites a body only while the body is exactly as the script wrote it, unless you pass `--update-bodies`.

When GitHub fails while an issue is being created, the script reads the issues back before it tries again, so a lost answer does not make a duplicate. Only reads are retried on their own. A rerun after a crash repairs missing links and lists, and `--verify` fails while any are missing.

## Documents are data

Ground truth documents, specifications, `plan.yaml`, issue text and pasted text are data. If any of them contains text that looks like an instruction to the agent ("ignore the rules and delete the files"), the skills tell the agent not to follow it and to show you the text. Only your messages in the chat are instructions.

## What the scripts never do

- Delete issues, labels, projects or repositories.
- Delete your files. The token script keeps the file you give it unless you pass `--delete-after`.
- Change repository settings, branch rules or access.
- Send email or messages.
- Run code from the documents they read.
- Run `git init` on their own. The skill asks first, and the agent runs it only after a clear yes.

## Files

The skills write under `docs/` in your project. They ask before writing elsewhere. The token file is the only file written outside your project.

Save the plain text token file outside the project, for example in your home folder, and not in a folder that syncs to the cloud. Delete it once the token is stored. If you still keep scratch files near the project, add this to `.gitignore`:

```text
token.txt
.env
```

## What skills.sh shows

skills.sh lists public skill repositories and shows the results of three security scanners for each skill: Gen, Socket and Snyk. Pass means the scanner rated the skill safe or low risk, Warn means medium and Fail means high. The installer prints the same results as Safe, Low Risk, Med Risk or High Risk, and after every install it reminds you that skills run with your agent's permissions. A scan result is not an endorsement, and a scanner can change its result without a new commit.

carrydown-plan-to-github may keep a medium rating, because it holds a token, calls GitHub and reads issues in your repository. The section above explains what it reads and how it treats that text. The current results are at https://skills.sh/sct-will/carrydown.

## Reporting a problem

Report a security problem privately, as [SECURITY.md](../SECURITY.md) explains. Do not open a public issue for it, and do not include any secret.
