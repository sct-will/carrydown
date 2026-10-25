# Token walkthrough

This page speaks to the plan owner. Relay it in your own words. Give each link for the user to open themselves. Do not open it with a browser tool.

The scripts need a GitHub token that can write issues and projects. The token is a password for your account. Treat it like one.

## Which token

Pick by who owns the project board.

Fine-grained token, for a board owned by an organization. Use this whenever you can. It reaches only the one repository.

- Create it on [the new fine-grained token page](https://github.com/settings/personal-access-tokens/new).
- Token name: carrydown. Expiration: 7 days.
- Resource owner: the organization that owns the repository.
- Repository access: only the one repository.
- Repository permissions: Issues read and write, Metadata read.
- Organization permissions: Projects read and write.
- Some organizations must approve a fine-grained token before it works. If yours does, the token waits for an administrator.

Classic token, only for a board owned by your user account. GitHub does not let fine-grained tokens use projects that belong to a user account.

- Create it with [the pre-filled new classic token page](https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown). It ticks `repo` and `project` and names the token for you.
- Set the expiry to 7 days.

Copy the token when GitHub shows it. It is shown once. When the plan and the board are on GitHub, revoke the token. Make a new one if you need it again.

## Store it safely

Never paste the token into the agent chat. Never set or read the token in the shell. Only the scripts read it. Pick one of two paths.

Preferred path, the hidden prompt. The agent prints this command and does not run it. Run it yourself in your own terminal and paste the token at the prompt. Nothing appears as you type:

```bash
python3 <skill>/scripts/github_token.py --repo owner/name
```

The script writes the token to `~/.config/carrydown/github_token` in a folder with mode 700 and a file with mode 600, asks GitHub who the token belongs to, and checks what it can do. The script never prints the token.

Only when you have no terminal, a file. Paste the token into a plain text file in a private folder outside your project. Do not use Downloads or a folder that syncs to the cloud. In TextEdit choose Format, then Make Plain Text, before you save. Tell the agent the file path, not the token. The agent passes the path to the script and never opens, reads, copies or moves the file:

```bash
python3 <skill>/scripts/github_token.py --from-file <path> --repo owner/name
```

It stores and checks the token the same way. It keeps your file. Delete the file yourself once the check passes, because it still holds the token in plain text. If other users can read the file, the script says so in a warning line.

Non-interactive form for automation. You run it yourself. The agent never runs this form. Your secret store's own command writes the token to standard input. Do not put the token in a shell variable, a command line or a file in the project:

```bash
<your secret store's read command> | python3 <skill>/scripts/github_token.py --stdin
```

## Check it

```bash
python3 <skill>/scripts/github_token.py --check --repo owner/name
```

The output says who owns the token, what it can do, and whether the repository is reachable with push access.

If it says the repository is not reachable, or that the token cannot push, the usual causes are single sign-on (next section) and a missing organization permission. Ask an organization administrator for permission to create issues and Projects in the organization. Then run the check again.

## Single sign-on

Many organizations require single sign-on (SSO). A classic token that works for your own repositories can still be refused by the organization's. A fine-grained token is tied to the organization when you create it, so this section is mainly for classic tokens. The signs are an HTTP 403 or 404 on the organization's repository and a message that mentions SAML or SSO.

To fix it:

1. Open [your GitHub tokens page](https://github.com/settings/tokens).
2. Find the token and click its Configure SSO button.
3. Click Authorize next to the organization and complete the sign-in.
4. Run `github_token.py --check --repo owner/name` again.

If you do not see the organization, your administrator may need to allow tokens. Ask them; do not work around it.

## Where the scripts look

When you pass `--token-file`, only that file. Otherwise the environment variable `CARRYDOWN_GITHUB_TOKEN`, then `~/.config/carrydown/github_token`. A token file that other users can read is refused, with the fix `chmod 600 <path>`. Text that is not a token, or a token with a second line, is refused before anything is sent.

## Never

- Never commit the token or the folder it lives in. Do not store it under a project directory.
- Never print it, echo it or put it in a command line.
- Never paste it into an issue, chat or document. If you do, revoke it right away on [your GitHub tokens page](https://github.com/settings/tokens) and make a new one.
- Revoke the token when the plan and the board are on GitHub.
