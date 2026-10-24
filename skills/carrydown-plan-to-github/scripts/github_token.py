#!/usr/bin/env python3
"""Set up a GitHub token for the carrydown scripts, safely.

The GitHub scripts need a token that can write issues and projects. This script
walks you through creating one, stores it in a file only you can read, and checks
that it has what the scripts need. It never prints the token.

Steps it prints and follows
  1. Create a token with a 7-day expiry. For a board owned by an organisation, use a
     fine-grained token limited to the one repository, with Issues (read and write),
     Metadata (read) and the organisation permission Projects (read and write). GitHub
     does not let fine-grained tokens use projects that belong to a user account, so
     for a board owned by your own account use a classic token with the scopes "repo"
     and "project".
  2. Paste it when asked. The input is hidden. It is written to
     ~/.config/carrydown/github_token with mode 600 in a folder with mode 700.
  3. The script asks GitHub who the token belongs to and which scopes it has.
  4. If your organisation enforces single sign-on (SSO), the token must be
     authorised for it. The script tells you how if GitHub says so.

Usage
  python3 scripts/github_token.py                    walk through it
  python3 scripts/github_token.py --dry-run          print the steps, store nothing, ask nothing
  python3 scripts/github_token.py --check            check the stored token and exit
  python3 scripts/github_token.py --check --repo owner/name   also check access to that repository
  printf '%s' "$TOKEN" | python3 scripts/github_token.py --stdin   non-interactive store
  python3 scripts/github_token.py --from-file ~/Downloads/token.txt   no prompt: read a plain text file

The --from-file form is for people who prefer not to use a terminal prompt. Paste the token into
a plain text file with any editor, save it outside the project, and give the script the path.
The script keeps that file. Delete it yourself once the token is stored, or pass --delete-after
to have the script delete it after the token is stored and verified. It never prints the token.

Before anything is sent to GitHub, the script checks that the text looks like a GitHub personal
access token (it starts with ghp_ or github_pat_). If it does not, nothing is sent.
"""
import argparse
import getpass
import os
import re
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import github_client as G  # noqa: E402

CLASSIC_URL = "https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown"
FINE_URL = "https://github.com/settings/personal-access-tokens/new"
SSO_URL = "https://github.com/settings/tokens"
TOKEN_RE = re.compile(r"^(ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,255})$")
NOT_A_TOKEN = "that is not a GitHub personal access token (it starts with ghp_ or github_pat_). Nothing was sent."
NEW_TOKEN = (f"make a new token (fine-grained for an organisation board: {FINE_URL}; "
             f"classic for a board on your own account: {CLASSIC_URL}) and store it again")


def walkthrough(say):
    """The token steps, fine-grained first. Printed before the prompt and by --dry-run."""
    say("Create a token first, with a 7-day expiry. Pick the kind by who owns the board:")
    say(f"  Board owned by an organisation: a fine-grained token. {FINE_URL}")
    say("    Resource owner: the organisation. Expiration: 7 days. Repository access: only the one repository.")
    say("    Repository permissions: Issues read and write, Metadata read. Organisation permission: Projects read and write.")
    say(f"  Board owned by your own account: a classic token. This link ticks repo and project and names it: {CLASSIC_URL}")
    say("    Set Expiration to 7 days. GitHub does not let fine-grained tokens use boards on a personal account.")
    say("  Copy the token. GitHub shows it once. Revoke it when the GitHub step is done.")


def short(path):
    home = str(Path.home())
    p = str(path)
    return "~" + p[len(home):] if p.startswith(home) else p


def store(path, token):
    path = Path(os.path.expanduser(str(path)))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token.strip() + "\n")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return path


def check(token, repo=None):
    gh = G.GitHub(token)
    try:
        me = gh.whoami()
    except G.GitHubError as e:
        if e.kind == "auth":
            L.say(f"GitHub rejected the token (HTTP 401). Fix: {NEW_TOKEN}. Check that you copied the whole token and that it has not expired.")
        else:
            L.say(f"Could not check the token: {e.line()}")
        return 1
    scopes = [s.strip() for s in (gh.scopes or "").split(",") if s.strip()]
    L.say(f"The token belongs to {me['login']}.")
    ok = True
    if scopes:
        L.say(f"Scopes: {', '.join(scopes)}")
        for need in ("repo", "project"):
            if need not in scopes:
                ok = False
                L.say(f"  missing scope: {need}.")
                L.say(f"  Fix: create a new classic token with the pre-filled link {CLASSIC_URL} (it ticks repo and project), then store it again.")
        if "delete_repo" in scopes:
            L.say("  note: this token can delete repositories. The carrydown scripts never use that power. Consider a token without it.")
    else:
        L.say("This looks like a fine-grained token (GitHub shows no scope list for those).")
        L.say("It needs Issues (read and write) and Metadata (read) on the repository, and Projects (read and write) for an organisation-owned project.")
    if repo:
        org = repo.split("/")[0]
        sso = False
        try:
            status, js = gh.rest_status("GET", f"/repos/{repo}")
        except G.GitHubError as e:
            if e.kind not in ("sso", "forbidden", "auth"):
                L.say(f"Could not check {repo}: {e.line()}")
                return 1
            status, js, sso = e.status, {}, e.kind == "sso"
        if status == 200:
            perms = js.get("permissions") or {}
            L.say(f"Repository {repo}: found (private: {js.get('private')}), push access: {perms.get('push')}.")
            if not perms.get("push", True):
                ok = False
                L.say(f"  Fix: ask an organisation admin of {org} for permission to create issues and Projects in it. The token cannot push to this repository.")
        elif sso:
            ok = False
            L.say(f"Repository {repo}: not reachable with this token (HTTP {status}): {org} uses single sign-on and the token is not authorised for it.")
            L.say(f"  Fix: open {SSO_URL}, click Configure SSO next to the token, then click Authorize next to {org}. Then run this check again.")
        else:
            ok = False
            L.say(f"Repository {repo}: not reachable with this token (HTTP {status}). There are two usual causes.")
            L.say(f"  Fix 1, single sign-on: open {SSO_URL}, click Configure SSO next to the token, then click Authorize next to {org}.")
            L.say(f"  Fix 2, missing permission: check the repository name, or ask an organisation admin of {org} for permission to create issues and Projects.")
            L.say("  Then run this check again.")
    L.say("Token check " + ("passed." if ok else "found problems."))
    return 0 if ok else 1


def main(argv=None):
    try:
        return _main(argv)
    except G.GitHubError as e:
        return G.report(e)


def _main(argv=None):
    ap = argparse.ArgumentParser(
        description="Walk through creating a GitHub token, store it safely and check it. The token is never printed.",
        epilog="Storage: ~/.config/carrydown/github_token, mode 600. The GitHub scripts read it from there.",
    )
    ap.add_argument("--token-file", default=G.DEFAULT_TOKEN_FILE, help=f"where to store or read the token (default: {G.DEFAULT_TOKEN_FILE})")
    ap.add_argument("--check", action="store_true", help="check the token already stored, store nothing")
    ap.add_argument("--repo", help="owner/name. Also check that the token reaches this repository")
    ap.add_argument("--stdin", action="store_true", help="read the token from standard input instead of prompting")
    ap.add_argument("--from-file", metavar="PATH", help="read the token from this plain text file instead of prompting")
    ap.add_argument("--delete-after", action="store_true",
                    help="delete the --from-file file after the token is stored and verified. Off by default: the file is kept and you delete it yourself")
    # Older instructions pass --no-delete-after. Keeping the file is now the default, so accept it quietly.
    ap.add_argument("--no-delete-after", dest="delete_after", action="store_false", help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="print the steps and the storage path. Ask for nothing, store nothing, call nothing")
    a = ap.parse_args(argv)
    dest = Path(os.path.expanduser(a.token_file))

    if a.dry_run:
        L.say("Dry run. These are the steps:")
        lines = []
        walkthrough(lines.append)
        L.say("1. " + lines[0])
        for line in lines[1:]:
            L.say("   " + line)
        L.say("2. Paste it when the script asks. The input is hidden.")
        L.say(f"3. The script writes it to {short(dest)} with mode 600.")
        L.say("4. The script asks GitHub who you are and which scopes the token has.")
        L.say(f"5. If your organisation uses single sign-on, open {SSO_URL}, choose Configure SSO next to the token and authorise the organisation.")
        L.say("Nothing was asked, stored or sent.")
        return 0

    if a.check:
        token = G.read_token(a.token_file, required=False)
        if not token:
            L.say(f"No token found at {short(dest)}. Run python3 {G.TOKEN_SCRIPT} without --check to set one up.")
            return 1
        return check(token, a.repo)

    if a.from_file:
        src = Path(os.path.expanduser(a.from_file))
        if not src.is_file():
            L.die(f"{a.from_file} is not a file")
        raw = src.read_bytes()
        if raw[:5] == b"{\\rtf" or b"\x00" in raw[:200]:
            L.die("that file is not plain text. In TextEdit choose Format, Make Plain Text, then save again")
        token = raw.decode("utf-8-sig", "replace").strip().strip("\ufeff").strip()
    elif a.stdin:
        token = sys.stdin.read().strip()
    else:
        walkthrough(L.say)
        L.say("")
        if not sys.stdin.isatty():
            L.die("no terminal to prompt on. Use --stdin to pass the token on standard input.")
        token = getpass.getpass("Paste the token (hidden), then press Enter: ").strip()
    if not token:
        L.die("no token entered")
    if not TOKEN_RE.match(token):
        L.die(NOT_A_TOKEN)
    try:
        G.GitHub(token).whoami()
    except G.GitHubError as e:
        if e.kind == "auth":
            L.say(f"GitHub rejected the token, so it was not stored. Fix: check that you copied the whole token and that it has not expired, or {NEW_TOKEN}.")
        else:
            L.say(f"The token was not stored, because GitHub could not check it: {e.line()}")
        return 1
    path = store(dest, token)
    L.say(f"Stored at {short(path)} with mode 600.")
    rc = check(token, a.repo)
    L.say("")
    if a.from_file:
        src = Path(os.path.expanduser(a.from_file))
        if a.delete_after and src.resolve() != path.resolve():
            try:
                src.unlink()
                L.say(f"Deleted {a.from_file}, as --delete-after asked. The token now lives only at {short(path)}.")
            except OSError as e:
                L.say(f"Could not delete {a.from_file} ({e.strerror}). Delete it yourself. It still holds the token in plain text.")
        elif src.resolve() != path.resolve():
            L.say(f"The token is stored at {short(path)}. Now delete {a.from_file} yourself: it still holds the token in plain text.")
    L.say("Never paste the token into a chat, a commit or an issue. If you do, revoke it at the same address and make a new one.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
