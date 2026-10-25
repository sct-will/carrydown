#!/usr/bin/env python3
"""GitHub client for the carrydown-plan-to-github scripts. Standard library only.

Contents
- Where the token is stored, and a reader for it that never prints it.
- A minimal client for the GitHub REST and GraphQL APIs at api.github.com.
- One-line messages, each with its fix, for the failures people meet: a rejected token,
  single sign-on, rate limits, server errors and timeouts.

Only github_token.py, github_sync.py and github_project.py import this module, and it
ships only with the carrydown-plan-to-github skill. The shared library carrydown_lib.py
holds no network or token code. This module is not run on its own.
"""
import datetime as _dt
import http.client
import json
import os
import re
import socket
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
DEFAULT_TOKEN_FILE = "~/.config/carrydown/github_token"
# The token script that sits next to this file, so messages name a path that exists
# wherever the skill is installed.
TOKEN_SCRIPT = Path(__file__).resolve().parent / "github_token.py"
TOKENS_PAGE = "https://github.com/settings/tokens"


# A GitHub personal access token: classic (ghp_) or fine-grained (github_pat_). The same pattern
# is used when a token is stored and when it is read, so nothing else is ever sent as a token.
TOKEN_RE = re.compile(r"^(ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,255})$")
TOKEN_SHAPE = "a GitHub personal access token (it starts with ghp_ or github_pat_)"
MAX_TOKEN_FILE = 4096   # bytes. A token is under 300; a larger file is not a token file


def refuse(msg):
    """Stop with one line on standard error and exit status 1. Never called with a token in msg."""
    raise SystemExit(f"error: {msg}")


def loose_mode(path):
    """The mode of a file that others can read or write, such as 0o644, or None when it is private.
    Only POSIX systems have these bits. On Windows the folder permissions protect the file."""
    if os.name != "posix":
        return None
    mode = stat.S_IMODE(os.stat(path).st_mode)
    return mode if mode & 0o077 else None


def read_token_file(path, what):
    """The token in path, checked. Refuses a file others can read, a file that is not UTF-8 text,
    an empty file, and text that is not a token, without ever printing the file's contents."""
    shown = str(path)
    if not path.is_file():
        refuse(f"{what} {shown} is not a regular file")
    mode = loose_mode(path)
    if mode is not None:
        refuse(f"{what} {shown} can be read by other users (mode {mode:o}), so it was not used. Fix: chmod 600 {shown}")
    try:
        if path.stat().st_size > MAX_TOKEN_FILE:
            refuse(f"{what} {shown} is larger than a token file can be, so it was not used. Store the token again with python3 {TOKEN_SCRIPT}")
        token = path.read_bytes().decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        refuse(f"{what} {shown} is not plain UTF-8 text, so it was not used. Store the token again with python3 {TOKEN_SCRIPT}")
    except OSError as e:
        refuse(f"cannot read {what} {shown}: {e.strerror or e}")
    if not token:
        refuse(f"{what} {shown} is empty. Store the token again with python3 {TOKEN_SCRIPT}")
    if not TOKEN_RE.match(token):
        refuse(f"{what} {shown} does not hold {TOKEN_SHAPE}, or holds more than one line. Nothing was sent. "
               f"Store the token again with python3 {TOKEN_SCRIPT}")
    return token


def read_token(explicit=None, required=True):
    """Return the token string, or None. Never prints it.

    An explicit --token-file is the only source when it is given, and a missing one is an error.
    Otherwise CARRYDOWN_GITHUB_TOKEN, then the stored file. Every token is checked against TOKEN_RE
    before it is used, so a stray line or a quoted value is never sent."""
    if explicit is not None:
        if not str(explicit).strip():
            refuse("--token-file is empty. Give the path of the token file, or leave out --token-file to use the stored token")
        p = Path(os.path.expanduser(explicit))
        try:
            found = p.exists()
        except (OSError, ValueError) as e:
            refuse(f"the token file {explicit} cannot be used: {getattr(e, 'strerror', None) or e}")
        if not found:
            refuse(f"token file not found: {explicit}. Check the path, or leave out --token-file to use the stored token")
        return read_token_file(p, "the token file")
    env = os.environ.get("CARRYDOWN_GITHUB_TOKEN")
    if env is not None and env.strip():
        token = env.strip()
        if not TOKEN_RE.match(token):
            refuse(f"CARRYDOWN_GITHUB_TOKEN does not hold {TOKEN_SHAPE}, or holds more than one line. Nothing was sent")
        return token
    p = Path(os.path.expanduser(DEFAULT_TOKEN_FILE))
    if p.exists():
        return read_token_file(p, "the stored token file")
    if required:
        raise SystemExit(
            f"No GitHub token found. Run: python3 {TOKEN_SCRIPT}\n"
            f"It stores the token at {DEFAULT_TOKEN_FILE} with mode 600. "
            "Or pass --token-file PATH, or set CARRYDOWN_GITHUB_TOKEN."
        )
    return None


def redact(text, secret):
    if not secret:
        return text
    return str(text).replace(secret, "<redacted>")


class GitHubError(RuntimeError):
    """One failed GitHub call. str(e) is one line; e.fix is the one-line fix when it is known.

    kind is one of: auth (401), sso (403, single sign-on), rate_limit (primary limit used up),
    secondary (secondary rate limit still in force after retries), forbidden (other 403),
    server (5xx), network (no answer or a timeout), http (anything else)."""

    def __init__(self, message, status=None, kind="http", fix=""):
        super().__init__(message)
        self.status, self.kind, self.fix = status, kind, fix

    def line(self):
        text = str(self).rstrip()
        if self.fix:
            text += ("" if text.endswith((".", "!", "?")) else ".") + f" Fix: {self.fix}."
        return text


def report(e):
    """Print a GitHubError as one line on standard error and return exit status 1."""
    print(f"error: {e.line()}", file=sys.stderr, flush=True)
    return 1


def sso_fix(headers=None):
    url = ""
    for part in str((headers or {}).get("X-GitHub-SSO") or "").split(";"):
        part = part.strip()
        if part.startswith("url=https://github.com/"):
            url = part[4:]
    where = f"open {url} and authorize the token" if url else (
        f"open {TOKENS_PAGE}, choose Configure SSO next to the token and authorize the organization")
    return f"your organization uses single sign-on, so {where}. Then rerun"


def _reset_time(headers):
    try:
        at = _dt.datetime.fromtimestamp(int(headers.get("X-RateLimit-Reset")))
        return at.strftime("%H:%M" if at.date() == _dt.date.today() else "%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


RERUN = "a rerun picks up where this one stopped and creates nothing twice"


def classify(code, raw_message, headers, method, path):
    """Turn an HTTP error into a GitHubError with a one-line fix."""
    msg = f"{method} {path} -> {code}: {raw_message}"
    headers = headers or {}
    remaining = str(headers.get("X-RateLimit-Remaining") or "")
    if code == 401:
        return GitHubError(msg, code, "auth", f"the token is wrong, expired or revoked. Make a new one and store it with python3 {TOKEN_SCRIPT}")
    if code == 403 and headers.get("X-GitHub-SSO"):
        return GitHubError(msg, code, "sso", sso_fix(headers))
    if code in (403, 429) and remaining == "0":
        at = _reset_time(headers)
        return GitHubError(msg, code, "rate_limit", f"the rate limit for this token is used up{' until ' + at if at else ''}. Wait, then rerun; {RERUN}")
    if code == 429 or (code == 403 and ("secondary rate limit" in raw_message.lower() or headers.get("Retry-After"))):
        return GitHubError(msg, code, "secondary", f"GitHub is slowing this token down (secondary rate limit). Wait a few minutes, then rerun; {RERUN}")
    if code == 403:
        return GitHubError(msg, code, "forbidden", f"the token lacks a permission this step needs. Check it with python3 {TOKEN_SCRIPT} --check --repo owner/name")
    if code in (500, 502, 503, 504):
        return GitHubError(msg, code, "server", f"GitHub had a server error. Rerun in a few minutes; {RERUN}")
    return GitHubError(msg, code, "http")


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to the host the request went to. A redirect to any other host is
    refused, so the Authorization header never reaches it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if (new.scheme, new.netloc.lower()) != (old.scheme, old.netloc.lower()):
            raise GitHubError(f"{req.get_method()} {old.path} -> {code}: GitHub redirected to another host ({new.netloc}). "
                              "The redirect was not followed, so the token was not sent there", code, "redirect",
                              "check the repository name and the owner, then rerun")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameHostRedirect)


def _urlopen(req, timeout):
    """Every request goes through here: the opener that refuses redirects to another host."""
    return _OPENER.open(req, timeout=timeout)


class GitHub:
    """Minimal GitHub client. The token never leaves this object and never appears in messages."""

    def __init__(self, token, api=API, pause=0.4, log=None):
        self._token = token
        self.api = api.rstrip("/")
        self.pause = pause
        self._last = 0.0
        self.log = log
        self.scopes = None
        self._me = None

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "carrydown",
        }

    def _send(self, method, url, data=None, ok=(200, 201, 202, 204), retries=4, safe=None):
        """Send one request. A server error or a lost connection is retried only when the request
        is safe to repeat (GET, or a GraphQL query), because GitHub may already have acted on a
        write whose answer was lost. A secondary rate limit is retried for every method: GitHub
        refuses the request before acting on it. Callers recover a failed write by reading back."""
        if safe is None:
            safe = method == "GET"
        body = json.dumps(data).encode() if data is not None else None
        path = url.replace(self.api, "")
        for attempt in range(retries + 1):
            wait = self.pause - (time.time() - self._last)
            if wait > 0 and method != "GET":
                time.sleep(wait)
            req = urllib.request.Request(url, method=method, data=body, headers=self._headers())
            try:
                with _urlopen(req, timeout=60) as r:
                    self._last = time.time()
                    self.scopes = r.headers.get("X-OAuth-Scopes", self.scopes)
                    raw = r.read()
                    try:
                        parsed = json.loads(raw) if raw else None
                    except ValueError:
                        raise GitHubError(f"{method} {path} -> {r.status}: the answer is not JSON, so it is not from the GitHub API", r.status, "http",
                                          "check the network: a proxy or a captive portal may have answered instead of GitHub")
                    return r.status, parsed, r.headers
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                self._last = time.time()
                if e.code in ok:
                    return e.code, None, e.headers
                try:
                    parsed = json.loads(raw)
                    msg = parsed.get("message", raw) if isinstance(parsed, dict) else raw
                    if isinstance(parsed, dict) and parsed.get("errors"):
                        msg += " " + json.dumps(parsed["errors"])[:300]
                except ValueError:
                    msg = raw
                msg = redact(" ".join(str(msg).split())[:500], self._token)
                err = classify(e.code, msg, e.headers, method, path)
                retry_after = e.headers.get("Retry-After")
                if (err.kind == "secondary" or (err.kind == "server" and safe)) and attempt < retries:
                    try:
                        delay = float(retry_after) if retry_after else 5 * (attempt + 1)
                    except ValueError:
                        delay = 5 * (attempt + 1)
                    time.sleep(min(delay, 120))
                    continue
                raise err
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, http.client.HTTPException) as e:
                reason = getattr(e, "reason", None) or e
                if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason):
                    reason = "no answer within 60 seconds"
                if safe and attempt < retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise GitHubError(f"{method} {path} failed: {redact(reason, self._token)}", None, "network",
                                  f"check the network connection, then rerun; {RERUN}")

    def rest(self, method, path, data=None, ok=(200, 201, 202, 204)):
        status, js, _ = self._send(method, self.api + path, data, ok)
        return js

    def rest_status(self, method, path, data=None):
        """Return (status, json) and treat 404, 409 and 422 as normal answers."""
        status, js, _ = self._send(method, self.api + path, data, ok=(200, 201, 202, 204, 404, 409, 422))
        return status, js

    def paged(self, path, key=None, limit=1000):
        """Every page of a list. GitHub names the next page in the Link header; when it names
        none, this was the last page. Without a Link header, a page shorter than 100 is the last.
        Only the page number is taken from the header, so a request never goes to a host the
        header names. limit stops a server that never ends the list."""
        out, page = [], 1
        sep = "&" if "?" in path else "?"
        while page <= limit:
            _, js, headers = self._send("GET", f"{self.api}{path}{sep}per_page=100&page={page}")
            chunk = (js.get(key, []) if key else js) if isinstance(js, (dict, list)) else []
            if not isinstance(chunk, list):
                raise GitHubError(f"GET {path} returned {type(chunk).__name__}, not a list", None, "http")
            out.extend(chunk)
            link = (headers or {}).get("Link") if headers is not None else None
            if link is not None:
                nxt = re.search(r'<[^>]*[?&]page=([0-9]+)[^>]*>\s*;\s*rel="next"', link)
                if not nxt or int(nxt.group(1)) <= page:
                    return out
                page = int(nxt.group(1))
                continue
            if len(chunk) < 100:
                return out
            page += 1
        raise GitHubError(f"GET {path} had more than {limit} pages", None, "http")

    def graphql(self, query, variables=None):
        safe = query.lstrip().startswith("query")   # a read; a mutation is never repeated
        status, js, _ = self._send("POST", self.api + "/graphql", {"query": query, "variables": variables or {}}, safe=safe)
        if js is None:
            raise GitHubError("GraphQL returned no body")
        if js.get("errors"):
            raise GitHubError("GraphQL: " + redact(json.dumps(js["errors"])[:600], self._token))
        return js["data"]

    def whoami(self):
        if self._me is None:
            status, js, headers = self._send("GET", self.api + "/user")
            self.scopes = headers.get("X-OAuth-Scopes", "")
            self._me = js
        return self._me
