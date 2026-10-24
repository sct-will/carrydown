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

You can go straight to https://github.com/sct-will/carrydown/security/advisories/new.

Please do not include a real token, a real password or real personal data in the report. A redacted example is enough. The maintainer aims to acknowledge a report within seven days and to say what happens next within fourteen days. This is a one-person project, so those are targets and not promises.

## What the carrydown skills store

- The GitHub token, when you run `github_token.py`. It is written to `~/.config/carrydown/github_token`, in a folder with mode 700, in a file with mode 600. Nothing else is stored outside your project.
- The files it writes under `docs/` in your project when you run it with `--apply`. Those files can hold the text of your documents. Treat them as you treat the documents.

The scripts talk only to `api.github.com`. They have no telemetry and no analytics.

## What the carrydown skills never do

- It never prints the token. Error messages have the token removed before they are shown.
- It never writes the token into your project, into a commit, into an issue or into a URL.
- It never deletes issues, labels, projects or repositories.
- It never runs code from the documents it reads.
- It never writes to GitHub unless you pass `--apply`.

## What counts as a vulnerability

Reports of these are welcome:

- A way to make a script print, log or store the token somewhere it should not.
- A way to make a script write outside the folders it documents.
- A way for the text of a document to make a script run a command.
- A weakness in the way a script handles a downloaded or pasted file.

## Your part

Create the token with only the permissions the carrydown skills need, which are `repo` and `project`. Set an expiry. Revoke it when you finish. If you think a token leaked, revoke it at https://github.com/settings/tokens and make a new one. More guidance is in [docs/security.md](docs/security.md).
