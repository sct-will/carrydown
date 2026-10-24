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
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
DEFAULT_TOKEN_FILE = "~/.config/carrydown/github_token"
# The token script that sits next to this file, so messages name a path that exists
# wherever the skill is installed.
TOKEN_SCRIPT = Path(__file__).resolve().parent / "github_token.py"
TOKENS_PAGE = "https://github.com/settings/tokens"


def token_candidates(explicit=None):
    out = []
    if explicit:
        out.append(("--token-file", Path(os.path.expanduser(explicit))))
    out.append(("default file", Path(os.path.expanduser(DEFAULT_TOKEN_FILE))))
    return out


def read_token(explicit=None, required=True):
    """Return the token string, or None. Never prints it."""
    env = os.environ.get("CARRYDOWN_GITHUB_TOKEN")
    if env and not explicit:
        return env.strip()
    for _, p in token_candidates(explicit):
        try:
            if p.exists():
                return p.read_text(encoding="utf-8-sig").strip()
        except OSError:
            continue
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
    where = f"open {url} and authorise the token" if url else (
        f"open {TOKENS_PAGE}, choose Configure SSO next to the token and authorise the organisation")
    return f"your organisation uses single sign-on, so {where}. Then rerun"


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
                with urllib.request.urlopen(req, timeout=60) as r:
                    self._last = time.time()
                    self.scopes = r.headers.get("X-OAuth-Scopes", self.scopes)
                    raw = r.read()
                    return r.status, (json.loads(raw) if raw else None), r.headers
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

    def paged(self, path, key=None):
        out, page = [], 1
        sep = "&" if "?" in path else "?"
        while True:
            js = self.rest("GET", f"{path}{sep}per_page=100&page={page}")
            chunk = js.get(key, []) if key else js
            out.extend(chunk)
            if len(chunk) < 100:
                return out
            page += 1

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
