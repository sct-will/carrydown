#!/usr/bin/env python3
"""The GitHub API behind release_verify.EvidenceReader. Network code: it ships only with the
carrydown-plan-to-github skill, with github_client.py. Standard library only.

GitHubEvidenceReader answers the read-only questions a verification asks (repositories, pull requests,
reviews, trees, rulesets, access lists) through the owner's client. Every listing follows every page;
a listing that GitHub truncates raises EvidenceUnavailable instead of returning a partial answer. A
transport or permission failure raises EvidenceUnavailable with a fixed phrase: no URL, no response
body and no token is ever put in the message.

This module is imported by release.py. Run with --help to see this text.
"""
import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_client as G  # noqa: E402
import release_verify as V  # noqa: E402

MAX_FILES = 3000       # GitHub lists at most this many files of a pull request
MAX_COMMITS = 250      # and at most this many commits
MAX_WALK = 5000


class GitHubEvidenceReader(V.EvidenceReader):
    HOST_OVERRIDE = None     # a test points the API at a local mock and names the host it stands for

    def __init__(self, gh, host=None):
        self.gh = gh
        api = gh.api.replace("https://", "").replace("http://", "")
        self.host = host or self.HOST_OVERRIDE or ("github.com" if api.startswith("api.github.com") else api.split("/")[0])
        self._names = {}

    def _name(self, repo_id):
        if repo_id not in self._names:
            info = self.repository(repo_id)
            if info is None:
                raise V.EvidenceUnavailable("a repository cannot be found by its numeric id")
            self._names[repo_id] = info["full_name"]
        return self._names[repo_id]

    def _get(self, what, path, none_on_404=False):
        try:
            status, js = self.gh.rest_status("GET", path)
        except G.GitHubError:
            raise V.EvidenceUnavailable(f"{what} cannot be read")
        if status == 404 and none_on_404:
            return None
        if status != 200:
            raise V.EvidenceUnavailable(f"{what} cannot be read")
        return js

    def _paged(self, what, path, limit=None):
        try:
            rows = self.gh.paged(path)
        except G.GitHubError:
            raise V.EvidenceUnavailable(f"{what} cannot be listed completely")
        if limit is not None and len(rows) >= limit:
            raise V.EvidenceUnavailable(f"{what} listing is truncated")
        return rows

    # --- repositories and git ---
    def repository(self, ref):
        path = f"/repositories/{ref}" if isinstance(ref, int) else f"/repos/{ref}"
        js = self._get("a repository", path, none_on_404=True)
        if js is None:
            return None
        self._names[js["id"]] = js["full_name"]
        return {"id": js["id"], "full_name": js["full_name"], "private": bool(js.get("private")),
                "visibility": js.get("visibility") or ("private" if js.get("private") else "public"),
                "default_branch": js.get("default_branch", "main"), "host": self.host, "archived": bool(js.get("archived"))}

    def branch_head(self, repo, branch):
        js = self._get("a branch", f"/repos/{self._name(repo)}/branches/{branch}", none_on_404=True)
        return js["commit"]["sha"] if js else None

    def first_parent_history(self, repo, ref):
        name, out, sha = self._name(repo), [], ref
        while sha:
            out.append(sha)
            if len(out) > MAX_WALK:
                raise V.EvidenceUnavailable("the history is too long to read completely")
            js = self._get("a commit", f"/repos/{name}/git/commits/{sha}")
            sha = js["parents"][0]["sha"] if js.get("parents") else None
        return list(reversed(out))

    def is_ancestor(self, repo, ancestor, descendant):
        if ancestor == descendant:
            return True
        js = self._get("a comparison", f"/repos/{self._name(repo)}/compare/{ancestor}...{descendant}", none_on_404=True)
        return bool(js) and js.get("status") in ("ahead", "identical")

    def commit_exists(self, repo, sha):
        return self._get("a commit", f"/repos/{self._name(repo)}/git/commits/{sha}", none_on_404=True) is not None

    @staticmethod
    def _pr(js):
        head, base = js["head"], js["base"]
        return {"number": js["number"], "state": js["state"], "merged": bool(js.get("merged_at") or js.get("merged")),
                "merged_at": js.get("merged_at"), "merge_commit_sha": js.get("merge_commit_sha") if js.get("merged_at") or js.get("merged") else None,
                "head": {"sha": head["sha"], "ref": head["ref"], "repo_id": (head.get("repo") or {}).get("id")},
                "base": {"ref": base["ref"], "sha": base["sha"]}, "user": {"id": (js.get("user") or {}).get("id"), "login": (js.get("user") or {}).get("login")}}

    def pull_requests(self, repo, base, state):
        rows = self._paged("pull requests", f"/repos/{self._name(repo)}/pulls?state={state}&base={base}")
        return [self._pr(r) for r in rows]

    def pull_request(self, repo, number):
        js = self._get("a pull request", f"/repos/{self._name(repo)}/pulls/{number}", none_on_404=True)
        return self._pr(js) if js else None

    def pull_request_files(self, repo, number):
        rows = self._paged("pull request files", f"/repos/{self._name(repo)}/pulls/{number}/files", MAX_FILES)
        return [{"filename": r["filename"], "status": r["status"], "sha": r.get("sha"), "previous_filename": r.get("previous_filename")}
                for r in rows]

    def reviews(self, repo, number):
        rows = self._paged("reviews", f"/repos/{self._name(repo)}/pulls/{number}/reviews")
        return [{"id": r["id"], "user": {"id": (r.get("user") or {}).get("id"), "login": (r.get("user") or {}).get("login")},
                 "state": r["state"], "commit_id": r.get("commit_id"), "submitted_at": r.get("submitted_at")} for r in rows]

    def commits(self, repo, number):
        rows = self._paged("pull request commits", f"/repos/{self._name(repo)}/pulls/{number}/commits", MAX_COMMITS)
        return [{"sha": r["sha"]} for r in rows]

    def tree(self, repo, sha):
        js = self._get("a tree", f"/repos/{self._name(repo)}/git/trees/{sha}?recursive=1")
        if js.get("truncated"):
            raise V.EvidenceUnavailable("the tree is truncated")
        return [{"path": n["path"], "mode": n["mode"], "type": n["type"], "sha": n["sha"], "size": n.get("size", 0)} for n in js["tree"]]

    def blob(self, repo, sha):
        js = self._get("a blob", f"/repos/{self._name(repo)}/git/blobs/{sha}")
        if js.get("encoding") != "base64":
            raise V.EvidenceUnavailable("a blob has an unknown encoding")
        return base64.b64decode(js["content"])

    def file_at(self, repo, ref, path):
        js = self._get("a file", f"/repos/{self._name(repo)}/contents/{path}?ref={ref}", none_on_404=True)
        if js is None:
            return None
        if isinstance(js, list) or js.get("encoding") != "base64" or "content" not in js:
            raise V.EvidenceUnavailable("a file cannot be read whole")
        return base64.b64decode(js["content"])

    # --- configuration and access ---
    def rulesets(self, repo):
        name = self._name(repo)
        out = []
        for row in self._paged("rulesets", f"/repos/{name}/rulesets"):
            out.append(self._get("a ruleset", f"/repos/{name}/rulesets/{row['id']}"))
        return out

    def collaborators(self, repo):
        rows = self._paged("collaborators", f"/repos/{self._name(repo)}/collaborators?affiliation=all")
        return [{"id": r["id"], "login": r["login"], "permission": r.get("role_name") or "read"} for r in rows]

    def teams(self, repo):
        rows = self._paged("teams", f"/repos/{self._name(repo)}/teams")
        return [{"id": r["id"], "slug": r["slug"], "permission": r.get("permission")} for r in rows]

    def installations(self, repo):
        raise V.EvidenceUnavailable("installed Apps cannot be listed with this token")

    def deploy_keys(self, repo):
        rows = self._paged("deploy keys", f"/repos/{self._name(repo)}/keys")
        return [{"id": r["id"], "read_only": bool(r.get("read_only"))} for r in rows]

    def actions_settings(self, repo):
        js = self._get("Actions settings", f"/repos/{self._name(repo)}/actions/permissions/workflow")
        return {"can_create_pull_requests": bool(js.get("can_approve_pull_request_reviews")),
                "default_workflow_permissions": js.get("default_workflow_permissions")}

    def secret_names(self, repo):
        """The names of the repository's Actions secrets. GitHub shows them only to a token with administrative
        read, so a token without it gets EvidenceUnavailable and the caller needs an attestation."""
        js = self._get("secret names", f"/repos/{self._name(repo)}/actions/secrets")
        names = js.get("secrets") or []
        if len(names) >= 100 or js.get("total_count", len(names)) > len(names):
            raise V.EvidenceUnavailable("secret names listing is truncated")
        return [n["name"] for n in names]

    def workflow_runs(self, repo, workflow, branch=None):
        suffix = f"?branch={branch}" if branch else ""
        js = self._get("workflow runs", f"/repos/{self._name(repo)}/actions/workflows/{workflow}/runs{suffix}")
        return [{"id": r["id"], "status": r["status"], "conclusion": r.get("conclusion"), "created_at": r.get("created_at")} for r in js.get("workflow_runs", [])]

    def scan_health(self, repo):
        runs = self._get("scan health", f"/repos/{self._name(repo)}/actions/workflows/carrydown-release-verify.yml/runs?status=completed&per_page=1",
                         none_on_404=True)
        if not runs or not runs.get("workflow_runs"):
            return None
        r = runs["workflow_runs"][0]
        return {"completed_at": r.get("updated_at"), "policy_commit_sha": r.get("head_sha"), "complete": r.get("conclusion") == "success",
                "oldest_outstanding_age_seconds": 0}

    def project(self, node_id):
        query = ("query($p: ID!) { node(id: $p) { ... on ProjectV2 { id public owner { ... on Organization { databaseId } ... on User { databaseId } } "
                 "repositories(first: 100) { nodes { databaseId } } } } }")
        try:
            data = self.gh.graphql(query, {"p": node_id})
        except G.GitHubError:
            raise V.EvidenceUnavailable("a project cannot be read")
        node = data.get("node") or {}
        if not node.get("id"):
            return None
        return {"id": node["id"], "owner_id": (node.get("owner") or {}).get("databaseId"), "owner_type": None, "public": bool(node.get("public")),
                "repository_ids": [n["databaseId"] for n in (node.get("repositories") or {}).get("nodes", [])], "reader_ids": None}

    def user(self, user_id):
        js = self._get("an account", f"/user/{user_id}", none_on_404=True)
        return {"id": js["id"], "login": js["login"]} if js else None


class GitHubCheckPublisher:
    """Posts the verifier's check runs (WP7, D11) through an installation token of the verifier App.

    A check run is found by its name and the App that owns it. start() moves an existing one back to
    in_progress, or creates it, so a head that already has a success or a failure is never skipped.
    finish() completes it only while it is still the newest run of that name on the head, so an older
    scan cannot overwrite a newer decision. The title and summary hold identifiers and fixed reason
    codes only. Every request goes through GitHub.rest, so a failure raises GitHubError."""

    def __init__(self, gh, app_id, clock=None):
        self.gh = gh
        self.app_id = app_id
        self._clock = clock
        self._names = {}

    def _name(self, repo_id):
        if repo_id not in self._names:
            status, js = self.gh.rest_status("GET", f"/repositories/{repo_id}")
            if status != 200:
                raise V.EvidenceUnavailable("a repository cannot be found by its numeric id")
            self._names[repo_id] = js["full_name"]
        return self._names[repo_id]

    def _now(self):
        return V.utc_text(self._clock() if self._clock else V.clock())

    def _runs(self, repo_id, head_sha, name):
        try:
            rows = self.gh.paged(f"/repos/{self._name(repo_id)}/commits/{head_sha}/check-runs?check_name={name}&app_id={self.app_id}", key="check_runs")
        except G.GitHubError:
            raise V.EvidenceUnavailable("check runs cannot be listed completely")
        return [r for r in rows if (r.get("app") or {}).get("id") in (None, self.app_id)]

    def latest_id(self, repo_id, head_sha, name):
        runs = self._runs(repo_id, head_sha, name)
        return max((r["id"] for r in runs), default=None)

    def start(self, repo_id, head_sha, name, summary="Verification is running."):
        body = {"status": "in_progress", "started_at": self._now(), "output": {"title": "carrydown: verification is running", "summary": summary}}
        try:
            runs = self._runs(repo_id, head_sha, name)
            if runs:
                newest = max(runs, key=lambda r: r["id"])
                self.gh.rest("PATCH", f"/repos/{self._name(repo_id)}/check-runs/{newest['id']}", dict(body, name=name))
                return newest["id"]
            made = self.gh.rest("POST", f"/repos/{self._name(repo_id)}/check-runs", dict(body, name=name, head_sha=head_sha))
            return made["id"]
        except G.GitHubError:
            raise V.EvidenceUnavailable("a check run cannot be started")

    def finish(self, repo_id, head_sha, name, check_id, conclusion, title, summary):
        """True when the result was posted, False when a newer check run of the same name exists."""
        newest = self.latest_id(repo_id, head_sha, name)
        if newest is not None and newest != check_id:
            return False
        try:
            self.gh.rest("PATCH", f"/repos/{self._name(repo_id)}/check-runs/{check_id}",
                         {"status": "completed", "conclusion": conclusion, "completed_at": self._now(),
                          "output": {"title": title[:200], "summary": summary[:60000]}})
        except G.GitHubError:
            raise V.EvidenceUnavailable("a check run cannot be completed")
        return True


def main(argv=None):
    ap = argparse.ArgumentParser(description="The GitHub API behind release_verify.EvidenceReader, and the check run publisher of the "
                                             "independent verifier. A library: import it, do not run it.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
