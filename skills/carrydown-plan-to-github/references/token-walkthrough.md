# Token walkthrough

The scripts need a GitHub token that can write issues and projects. The token is a password for your account. Treat it like one.

## Which token

Classic personal access token. The simplest choice. It works for projects owned by a user and by an organisation.

- Scopes: `repo` and `project`.
- Create it at https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown
- Set an expiry. Thirty days is enough for a planning session. Copy the token when GitHub shows it. It is shown once.

Fine-grained token. Fits a stricter policy, with one catch.

- Resource owner: the organisation that owns the repository.
- Repository access: only the one repository.
- Repository permissions: Issues read and write, Metadata read.
- Organisation permission: Projects read and write.
- GitHub does not let fine-grained tokens use projects that belong to a user account. For a user-owned board, use a classic token.
- Create it at https://github.com/settings/personal-access-tokens/new

## Store it safely

Never paste the token into the agent chat. Pick one of two paths.

Preferred path, no terminal prompt. Paste the token into a plain text file, for example `Downloads/token.txt`. In TextEdit choose Format, then Make Plain Text, before you save. Tell the agent the file path. The agent runs:

```bash
python3 <skill>/scripts/github_token.py --from-file <path> --repo owner/name
```

The script reads the file, writes the token to `~/.config/carrydown/github_token` in a folder with mode 700 and a file with mode 600, asks GitHub who the token belongs to, compares the scopes with what the scripts need, and tells you to delete your copy of the file. Delete it. The script never deletes it for you.

Alternative path. Run the script yourself in a terminal and type the token at the hidden prompt. Nothing appears as you type.

```bash
python3 <skill>/scripts/github_token.py
```

It stores and checks the token the same way. The script never prints the token.

Non-interactive form for automation (the token comes from another secret store, not from a file in the project):

```bash
printf '%s' "$TOKEN_FROM_SECRET_STORE" | python3 <skill>/scripts/github_token.py --stdin
```

## Check it

```bash
python3 <skill>/scripts/github_token.py --check --repo owner/name
```

The output says who owns the token, its scopes, and whether the repository is reachable with push access.

If it says the repository is not reachable, or that the token cannot push, the usual causes are single sign-on (next section) and a missing organisation permission. Ask an organisation administrator for permission to create issues and Projects in the organisation. Then run the check again.

## Single sign-on

Many organisations require single sign-on (SSO). A token that works for your own repositories can still be refused by the organisation's. The signs are an HTTP 403 or 404 on the organisation's repository and a message that mentions SAML or SSO.

To fix it:

1. Open https://github.com/settings/tokens.
2. Find the token and click its Configure SSO button.
3. Click Authorize next to the organisation and complete the sign-in.
4. Run `github_token.py --check --repo owner/name` again.

If you do not see the organisation, your administrator may need to allow tokens. Ask them; do not work around it.

## Where the scripts look

In this order: the `--token-file` option, the environment variable `CARRYDOWN_GITHUB_TOKEN`, then `~/.config/carrydown/github_token`.

## Never

- Never commit the token or the folder it lives in. Do not store it under a project directory.
- Never print it, echo it or put it in a command line.
- Never paste it into an issue, chat or document. If you do, revoke it right away at https://github.com/settings/tokens and make a new one.
- Revoke the token when the planning session ends if you do not need it again.
