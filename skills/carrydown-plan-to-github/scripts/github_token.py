#!/usr/bin/env python3
"""Set up a GitHub token for the carrydown scripts, safely.

The GitHub scripts need a token that can write issues and projects. This script
walks you through creating one, stores it in a file only you can read, and checks
that it has what the scripts need. It never prints the token.

Steps it prints and follows
  1. Create a token. A classic token with the scopes "repo" and "project" is the
     simplest and works for projects owned by a user or an organisation. A
     fine-grained token also works for organisation-owned projects when it has
     Issues (read and write), Metadata (read) and the organisation permission
     Projects (read and write). GitHub does not let fine-grained tokens use
     projects that belong to a user account, so use a classic token for those.
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
a plain text file with any editor, give the script the path, then delete that file yourself. The
script never deletes it and never prints the token.
"""
import argparse
import getpass
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402

CLASSIC_URL = "https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown"
FINE_URL = "https://github.com/settings/personal-access-tokens/new"
SSO_URL = "https://github.com/settings/tokens"


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
    gh = L.GitHub(token)
    try:
        me = gh.whoami()
    except L.GitHubError as e:
        L.say(f"GitHub rejected the token: {str(e)[:200]}")
        L.say("Check that you pasted the whole token and that it has not expired.")
        return 1
    scopes = [s.strip() for s in (gh.scopes or "").split(",") if s.strip()]
    L.say(f"The token belongs to {me['login']}.")
    ok = True
    if scopes:
        L.say(f"Scopes: {', '.join(scopes)}")
        for need in ("repo", "project"):
            if need not in scopes:
                ok = False
                L.say(f"  missing scope: {need}. Create a new token with the scopes repo and project: {CLASSIC_URL}")
        if "delete_repo" in scopes:
            L.say("  note: this token can delete repositories. The carrydown scripts never use that power. Consider a token without it.")
    else:
        L.say("This looks like a fine-grained token (GitHub shows no scope list for those).")
        L.say("It needs Issues (read and write) and Metadata (read) on the repository, and Projects (read and write) for an organisation-owned project.")
    if repo:
        status, js = gh.rest_status("GET", f"/repos/{repo}")
        if status == 200:
            perms = js.get("permissions") or {}
            L.say(f"Repository {repo}: found (private: {js.get('private')}), push access: {perms.get('push')}.")
            ok &= bool(perms.get("push", True))
            if not perms.get("push", True):
                L.say("  The token cannot push to this repository. Ask an organisation administrator for permission to create issues and Projects in it.")
        else:
            ok = False
            L.say(f"Repository {repo}: not reachable with this token (HTTP {status}).")
            L.say("  If the repository belongs to an organisation that uses single sign-on (SSO), authorise the token for it:")
            L.say(f"  open {SSO_URL}, find the token, click its Configure SSO button, then click Authorize next to the organisation.")
            L.say("  If the repository is still not reachable, you may lack the organisation permission to create issues and Projects. Ask an organisation administrator for it.")
    L.say("Token check " + ("passed." if ok else "found problems."))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Walk through creating a GitHub token, store it safely and check it. The token is never printed.",
        epilog="Storage: ~/.config/carrydown/github_token, mode 600. The GitHub scripts read it from there.",
    )
    ap.add_argument("--token-file", default=L.DEFAULT_TOKEN_FILE, help=f"where to store or read the token (default: {L.DEFAULT_TOKEN_FILE})")
    ap.add_argument("--check", action="store_true", help="check the token already stored, store nothing")
    ap.add_argument("--repo", help="owner/name. Also check that the token reaches this repository")
    ap.add_argument("--stdin", action="store_true", help="read the token from standard input instead of prompting")
    ap.add_argument("--from-file", metavar="PATH", help="read the token from this plain text file instead of prompting. Delete that file afterwards")
    ap.add_argument("--dry-run", action="store_true", help="print the steps and the storage path. Ask for nothing, store nothing, call nothing")
    a = ap.parse_args(argv)
    dest = Path(os.path.expanduser(a.token_file))

    if a.dry_run:
        L.say("Dry run. These are the steps:")
        L.say(f"1. Create a classic token with the scopes repo and project: {CLASSIC_URL}")
        L.say(f"   Or a fine-grained token (organisation-owned projects only): {FINE_URL}")
        L.say("2. Paste it when the script asks. The input is hidden.")
        L.say(f"3. The script writes it to {short(dest)} with mode 600.")
        L.say("4. The script asks GitHub who you are and which scopes the token has.")
        L.say(f"5. If your organisation uses single sign-on, open {SSO_URL}, choose Configure SSO next to the token and authorise the organisation.")
        L.say("Nothing was asked, stored or sent.")
        return 0

    if a.check:
        token = L.read_token(a.token_file, required=False)
        if not token:
            L.say(f"No token found at {short(dest)}. Run this script without --check to set one up.")
            return 1
        return check(token, a.repo)

    if a.from_file:
        src = Path(os.path.expanduser(a.from_file))
        if not src.is_file():
            L.die(f"{a.from_file} is not a file")
        raw = src.read_bytes()
        if raw[:5] == b"{\\rtf" or b"\x00" in raw[:200]:
            L.die("that file is not plain text. In TextEdit choose Format, Make Plain Text, then save again")
        token = raw.decode("utf-8", "replace").strip()
    elif a.stdin:
        token = sys.stdin.read().strip()
    else:
        L.say("Create a token first.")
        L.say(f"  Classic token (works everywhere): {CLASSIC_URL}")
        L.say("    Tick the scopes repo and project. Set an expiry. Copy the token. GitHub shows it once.")
        L.say(f"  Fine-grained token (organisation-owned projects only): {FINE_URL}")
        L.say("    Repository access: the one repository. Permissions: Issues read and write, Metadata read.")
        L.say("    Organisation permission: Projects read and write.")
        L.say("")
        if not sys.stdin.isatty():
            L.die("no terminal to prompt on. Use --stdin to pass the token on standard input.")
        token = getpass.getpass("Paste the token (hidden), then press Enter: ").strip()
    if not token:
        L.die("no token entered")
    if len(token) < 20 or any(c.isspace() for c in token):
        L.die("that does not look like a token (too short or has spaces)")
    try:
        L.GitHub(token).whoami()
    except L.GitHubError as e:
        L.say(f"GitHub rejected the token, so it was not stored: {str(e)[:120]}")
        L.say("Check that you copied the whole token and that it has not expired.")
        return 1
    path = store(dest, token)
    L.say(f"Stored at {short(path)} with mode 600.")
    rc = check(token, a.repo)
    L.say("")
    L.say("If the organisation that owns your repository uses single sign-on (SSO) and a check above failed,")
    L.say(f"open {SSO_URL}, choose Configure SSO next to this token, and authorise the organisation. Then run with --check --repo owner/name.")
    if a.from_file:
        L.say(f"Now delete {a.from_file} yourself. It still holds the token in plain text.")
    L.say("Never paste the token into a chat, a commit or an issue. If you do, revoke it at the same address and make a new one.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
