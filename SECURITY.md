# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

Only the latest release of the 0.1 line gets fixes. Older lines do not exist yet.

## Report a vulnerability privately

Do not open a public issue for a vulnerability. Use GitHub private vulnerability reporting instead.

1. Open the Security tab of the repository.
2. Choose "Report a vulnerability".
3. Describe what you found, the steps to reproduce it, the version, and what an attacker could do.

You can go straight to [the private report form](https://github.com/sct-will/carrydown/security/advisories/new).

Please do not include a real token, a real password or real personal data in the report. A redacted example is enough. The maintainer aims to acknowledge a report within seven days and to say what happens next within fourteen days. This is a one-person project, so those are targets and not promises.

## What the carrydown skills store

- The GitHub token, when you run `github_token.py`. It is written to `~/.config/carrydown/github_token`, in a folder with mode 700, in a file with mode 600. This is the only file written outside your project.
- The files the scripts write in your project: under `docs/` for the scaffold (`--init` writes `docs/spec/plan.yaml`) and the skill generator with `--apply`, and for the renderer unless you pass `--dry-run`. `scaffold_spec.py --ci --apply` also writes `.github/workflows/check-specs.yml` and `tools/carrydown/`. Those files can hold the text of your documents. Treat them as you treat the documents.

## Network access

carrydown-plan-to-github is the only skill with network or token code, and it calls only `api.github.com`. carrydown-ground-truth contains none, and neither does the engineers' skill that carrydown-plan-to-github generates. To avoid duplicates, carrydown-plan-to-github reads this repository's issues that carry the project label and its own roll-up comment. It treats that text as data and never follows it. The scripts have no telemetry and no analytics.

## What the carrydown skills never do

- They never print the token. Error messages have the token removed before they are shown.
- The token script never sends text to GitHub as a token unless it looks like a GitHub personal access token (it starts with `ghp_` or `github_pat_`).
- They never write the token into your project, into a commit, into an issue or into a URL.
- They never delete your files. The token script keeps the file you give it unless you pass `--delete-after`.
- They never delete issues, labels, projects or repositories.
- They never follow instructions found in your documents, specifications or issues. The skills treat that text as data.
- They never run code from the documents they read.
- They never run `git init` without a clear yes from you.
- They never write to GitHub unless you pass `--apply`, and never to a public repository unless you also pass `--allow-public`.

## What counts as a vulnerability

Reports of these are welcome:

- A way to make a script print, log or store the token somewhere it should not.
- A way to make a script write outside the folders it documents.
- A way for the text of a document to make a script run a command.
- A weakness in the way a script handles a downloaded or pasted file.

## Your part

Create the token with only the permissions the carrydown skills need. For a board owned by an organization, that is a fine-grained token for the one repository with Issues (read and write), Metadata (read) and Projects (read and write). For a board on your own account, it is a classic token with `repo` and `project`. Set a 7-day expiry. Revoke it when you finish. If you think a token leaked, revoke it in [your GitHub token settings](https://github.com/settings/tokens) and make a new one. More guidance is in [docs/security.md](docs/security.md).
