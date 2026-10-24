#!/usr/bin/env python3
"""GitHub client for the carrydown-plan-to-github scripts. Standard library only.

Contents
- Where the token is stored, and a reader for it that never prints it.
- A minimal client for the GitHub REST and GraphQL APIs at api.github.com.

Only github_token.py, github_sync.py and github_project.py import this module, and it
ships only with the carrydown-plan-to-github skill. The shared library carrydown_lib.py
holds no network or token code. This module is not run on its own.
"""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_TOKEN_FILE = "~/.config/carrydown/github_token"


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
                return p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    if required:
        raise SystemExit(
            "No GitHub token found. Run: python3 scripts/github_token.py\n"
            f"It stores the token at {DEFAULT_TOKEN_FILE} with mode 600. "
            "Or pass --token-file PATH, or set CARRYDOWN_GITHUB_TOKEN."
        )
    return None


def redact(text, secret):
    if not secret:
        return text
    return str(text).replace(secret, "<redacted>")


class GitHubError(RuntimeError):
    pass


class GitHub:
    """Minimal GitHub client. The token never leaves this object and never appears in messages."""

    def __init__(self, token, api="https://api.github.com", pause=0.4, log=None):
        self._token = token
        self.api = api.rstrip("/")
        self.pause = pause
        self._last = 0.0
        self.log = log
        self.scopes = None

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "carrydown",
        }

    def _send(self, method, url, data=None, ok=(200, 201, 202, 204), retries=4):
        body = json.dumps(data).encode() if data is not None else None
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
                retry_after = e.headers.get("Retry-After")
                secondary = e.code in (403, 429) and ("secondary rate limit" in raw.lower() or retry_after)
                if (e.code in (502, 503, 504) or secondary) and attempt < retries:
                    time.sleep(float(retry_after) if retry_after else 5 * (attempt + 1))
                    continue
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
                raise GitHubError(f"{method} {url.replace(self.api, '')} -> {e.code}: {msg}")
            except urllib.error.URLError as e:
                if attempt < retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise GitHubError(f"{method} {url.replace(self.api, '')} failed: {redact(e.reason, self._token)}")

    def rest(self, method, path, data=None, ok=(200, 201, 202, 204)):
        status, js, _ = self._send(method, self.api + path, data, ok)
        return js

    def rest_status(self, method, path, data=None):
        """Return (status, json) and treat 404 as a normal answer."""
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
        status, js, _ = self._send("POST", self.api + "/graphql", {"query": query, "variables": variables or {}})
        if js is None:
            raise GitHubError("GraphQL returned no body")
        if js.get("errors"):
            raise GitHubError("GraphQL: " + redact(json.dumps(js["errors"])[:600], self._token))
        return js["data"]

    def whoami(self):
        status, js, headers = self._send("GET", self.api + "/user")
        self.scopes = headers.get("X-OAuth-Scopes", "")
        return js
