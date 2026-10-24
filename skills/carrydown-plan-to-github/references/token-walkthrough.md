# Token walkthrough

This page speaks to the plan owner. Relay it in your own words. Give each link for the user to open themselves. Do not open it with a browser tool.

The scripts need a GitHub token that can write issues and projects. The token is a password for your account. Treat it like one.

## Which token

Pick by who owns the project board.

Fine-grained token, for a board owned by an organisation. Use this whenever you can. It reaches only the one repository.

- Create it on [the new fine-grained token page](https://github.com/settings/personal-access-tokens/new).
- Token name: carrydown. Expiration: 7 days.
- Resource owner: the organisation that owns the repository.
- Repository access: only the one repository.
- Repository permissions: Issues read and write, Metadata read.
- Organisation permissions: Projects read and write.
- Some organisations must approve a fine-grained token before it works. If yours does, the token waits for an administrator.

Classic token, only for a board owned by your user account. GitHub does not let fine-grained tokens use projects that belong to a user account.

- Create it with [the pre-filled new classic token page](https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown). It ticks `repo` and `project` and names the token for you.
- Set the expiry to 7 days.

Copy the token when GitHub shows it. It is shown once. When the plan and the board are on GitHub, revoke the token. Make a new one if you need it again.

## Store it safely

Never paste the token into the agent chat. Pick one of two paths.

Preferred path, no terminal prompt. Paste the token into a plain text file outside your project, for example `Downloads/token.txt`. In TextEdit choose Format, then Make Plain Text, before you save. Tell the agent the file path, not the token. The agent never opens the file. It passes the path to the script:

```bash
python3 <skill>/scripts/github_token.py --from-file <path> --repo owner/name
```

The script reads the file, writes the token to `~/.config/carrydown/github_token` in a folder with mode 700 and a file with mode 600, asks GitHub who the token belongs to, and checks what it can do. It keeps your file. Delete the file yourself once the check passes, because it still holds the token in plain text.

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

The output says who owns the token, what it can do, and whether the repository is reachable with push access.

If it says the repository is not reachable, or that the token cannot push, the usual causes are single sign-on (next section) and a missing organisation permission. Ask an organisation administrator for permission to create issues and Projects in the organisation. Then run the check again.

## Single sign-on

Many organisations require single sign-on (SSO). A classic token that works for your own repositories can still be refused by the organisation's. A fine-grained token is tied to the organisation when you create it, so this section is mainly for classic tokens. The signs are an HTTP 403 or 404 on the organisation's repository and a message that mentions SAML or SSO.

To fix it:

1. Open [your GitHub tokens page](https://github.com/settings/tokens).
2. Find the token and click its Configure SSO button.
3. Click Authorize next to the organisation and complete the sign-in.
4. Run `github_token.py --check --repo owner/name` again.

If you do not see the organisation, your administrator may need to allow tokens. Ask them; do not work around it.

## Where the scripts look

In this order: the `--token-file` option, the environment variable `CARRYDOWN_GITHUB_TOKEN`, then `~/.config/carrydown/github_token`.

## Never

- Never commit the token or the folder it lives in. Do not store it under a project directory.
- Never print it, echo it or put it in a command line.
- Never paste it into an issue, chat or document. If you do, revoke it right away on [your GitHub tokens page](https://github.com/settings/tokens) and make a new one.
- Revoke the token when the plan and the board are on GitHub.
