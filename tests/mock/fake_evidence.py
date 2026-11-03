"""An in-memory model of GitHub for the release verification tests. Standard library only.

FakeEvidenceReader implements release_verify.EvidenceReader over a small model of git: repositories
with commits (a tree of path to mode and bytes, parents), branches, pull requests with files,
reviews and commits. Nothing here talks to a network. WP6, WP7 and WP11 reuse it.

  reader = FakeEvidenceReader()
  repo = reader.add_repo(4300, "acme/staging")
  n = reader.open_pr(4300, "request/<id>", {"path": b"bytes"})     a pull request that adds files
  reader.review(4300, n, 78674552, "sct-will")                       an approving review on the head
  reader.merge(4300, n)                                              a merge commit on the default branch

World builds the whole fictional organization of the specification: a tooling repository, an
enrolled engineering repository, a private staging repository, an enrollment file and rulesets.

Every call is recorded in reader.calls. The reader has no write method, so a test can assert that a
verification wrote nothing. reader.fail("collaborators") makes one listing unavailable;
reader.truncate("pull_requests") makes a listing raise as an incomplete one.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402

OWNER = (78674552, "sct-will")
ADMIN = (12345, "org-admin")
OUTSIDER = (999, "outsider")


def blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class FakeEvidenceReader(V.EvidenceReader):
    def __init__(self, host="github.com"):
        self.host = host
        self.repos = {}
        self.calls = []
        self.failures = {}
        self.truncated = set()
        self.users = {}
        self.rulesets_by_repo = {}
        self.collaborators_by_repo = {}
        self.teams_by_repo = {}
        self.installations_by_repo = {}
        self.deploy_keys_by_repo = {}
        self.actions_by_repo = {}
        self.projects = {}
        self.scan = {}
        self.dispatches = []
        self.on_poll = None
        self._clock = int(V.clock()) - 86400     # the model's own time starts a day ago, so real-clock checks pass
        self._counter = 0

    # --- building the model ---
    def tick(self, seconds=60):
        self._clock += seconds
        return V.utc_text(self._clock)

    def _sha(self, *parts):
        self._counter += 1
        return hashlib.sha1(("|".join(str(p) for p in parts) + f"|{self._counter}").encode()).hexdigest()

    def add_repo(self, repo_id, full_name, private=True, default_branch="main", files=None):
        repo = {"id": repo_id, "full_name": full_name, "private": private, "visibility": "private" if private else "public",
                "default_branch": default_branch, "host": self.host, "archived": False, "commits": {}, "branches": {},
                "blobs": {}, "prs": {}, "next_pr": 1}
        self.repos[repo_id] = repo
        self.commit(repo_id, files or {}, [], branch=default_branch)
        return repo

    def commit(self, repo_id, files, parents, branch=None):
        """A commit whose tree is the first parent's tree plus files (path to bytes or (mode, bytes);
        None removes a path)."""
        repo = self.repos[repo_id]
        tree = dict(repo["commits"][parents[0]]["tree"]) if parents else {}
        for path, value in files.items():
            if value is None:
                tree.pop(path, None)
                continue
            mode, data = value if isinstance(value, tuple) else ("100644", value)
            tree[path] = (mode, bytes(data))
            repo["blobs"][blob_sha(bytes(data))] = bytes(data)
        sha = self._sha(repo_id, parents, sorted(tree))
        repo["commits"][sha] = {"tree": tree, "parents": list(parents)}
        if branch:
            repo["branches"][branch] = sha
        return sha

    def set_file(self, repo_id, path, data, branch=None):
        repo = self.repos[repo_id]
        branch = branch or repo["default_branch"]
        return self.commit(repo_id, {path: data}, [repo["branches"][branch]], branch=branch)

    def open_pr(self, repo_id, branch, files, user=(0, "github-actions[bot]"), base=None, base_sha=None):
        """A branch off the base (or off base_sha) that adds files, and an open pull request for it."""
        repo = self.repos[repo_id]
        base = base or repo["default_branch"]
        start = base_sha or repo["branches"][base]
        head = self.commit(repo_id, files, [start], branch=branch)
        number = repo["next_pr"]
        repo["next_pr"] += 1
        repo["prs"][number] = {"number": number, "state": "open", "merged": False, "merged_at": None, "merge_commit_sha": None,
                               "head": {"sha": head, "ref": branch, "repo_id": repo_id}, "base": {"ref": base, "sha": start},
                               "user": {"id": user[0], "login": user[1]}, "_base_commit": start, "reviews": [], "_commits": [head]}
        return number

    def push_more(self, repo_id, number, files):
        """Another commit on the head of an open pull request."""
        pr = self.repos[repo_id]["prs"][number]
        head = self.commit(repo_id, files, [pr["head"]["sha"]], branch=pr["head"]["ref"])
        pr["head"]["sha"] = head
        pr["_commits"].append(head)
        return head

    def review(self, repo_id, number, user_id, login, state="APPROVED", commit_id=None, at=None):
        pr = self.repos[repo_id]["prs"][number]
        rid = len(pr["reviews"]) + 1
        pr["reviews"].append({"id": rid, "user": {"id": user_id, "login": login}, "state": state,
                              "commit_id": commit_id or pr["head"]["sha"], "submitted_at": at or self.tick()})
        return rid

    def dismiss(self, repo_id, number, review_id):
        for r in self.repos[repo_id]["prs"][number]["reviews"]:
            if r["id"] == review_id:
                r["state"] = "DISMISSED"

    def merge(self, repo_id, number, at=None):
        repo = self.repos[repo_id]
        pr = repo["prs"][number]
        base_branch = pr["base"]["ref"]
        tip = repo["branches"][base_branch]
        base_tree = repo["commits"][pr["_base_commit"]]["tree"]
        head_tree = repo["commits"][pr["head"]["sha"]]["tree"]
        changes = {}
        for path, value in head_tree.items():
            if base_tree.get(path) != value:
                changes[path] = value
        for path in base_tree:
            if path not in head_tree:
                changes[path] = None
        sha = self.commit(repo_id, changes, [tip], branch=base_branch)
        repo["commits"][sha]["parents"].append(pr["head"]["sha"])
        pr.update({"state": "closed", "merged": True, "merged_at": at or self.tick(), "merge_commit_sha": sha})
        return sha

    def close(self, repo_id, number):
        self.repos[repo_id]["prs"][number].update({"state": "closed"})

    def fail(self, method, repo_id=None):
        self.failures[(method, repo_id)] = True

    def truncate(self, method):
        self.truncated.add(method)

    def _enter(self, method, repo_id=None):
        self.calls.append((method, repo_id))
        if self.failures.get((method, repo_id)) or self.failures.get((method, None)):
            raise V.EvidenceUnavailable(f"{method} cannot be read")
        if method in self.truncated:
            raise V.EvidenceUnavailable(f"{method} listing is incomplete")

    def _repo(self, repo_id):
        repo = self.repos.get(repo_id)
        if repo is None:
            raise V.EvidenceUnavailable("repository cannot be found")
        return repo

    # --- the EvidenceReader interface ---
    def repository(self, ref):
        self._enter("repository", ref)
        for repo in self.repos.values():
            if ref == repo["id"] or ref == repo["full_name"]:
                return {k: repo[k] for k in ("id", "full_name", "private", "visibility", "default_branch", "host", "archived")}
        return None

    def branch_head(self, repo_id, branch):
        self._enter("branch_head", repo_id)
        return self._repo(repo_id)["branches"].get(branch)

    def first_parent_history(self, repo_id, ref):
        self._enter("first_parent_history", repo_id)
        repo = self._repo(repo_id)
        out, sha = [], ref
        while sha:
            out.append(sha)
            parents = repo["commits"][sha]["parents"]
            sha = parents[0] if parents else None
        return list(reversed(out))

    def is_ancestor(self, repo_id, ancestor, descendant):
        self._enter("is_ancestor", repo_id)
        repo = self._repo(repo_id)
        seen, todo = set(), [descendant]
        while todo:
            sha = todo.pop()
            if sha == ancestor:
                return True
            if sha in seen or sha not in repo["commits"]:
                continue
            seen.add(sha)
            todo.extend(repo["commits"][sha]["parents"])
        return False

    def commit_exists(self, repo_id, sha):
        self._enter("commit_exists", repo_id)
        return sha in self._repo(repo_id)["commits"]

    @staticmethod
    def _public_pr(pr):
        return {k: (dict(v) if isinstance(v, dict) else v) for k, v in pr.items() if not k.startswith("_") and k != "reviews"}

    def pull_requests(self, repo_id, base, state):
        self._enter("pull_requests", repo_id)
        out = []
        for pr in self._repo(repo_id)["prs"].values():
            if pr["base"]["ref"] != base:
                continue
            if state == "open" and pr["state"] != "open":
                continue
            if state == "closed" and pr["state"] != "closed":
                continue
            out.append(self._public_pr(pr))
        return out

    def pull_request(self, repo_id, number):
        self._enter("pull_request", repo_id)
        pr = self._repo(repo_id)["prs"].get(number)
        return self._public_pr(pr) if pr else None

    def pull_request_files(self, repo_id, number):
        self._enter("pull_request_files", repo_id)
        repo = self._repo(repo_id)
        pr = repo["prs"][number]
        base = repo["commits"][pr["_base_commit"]]["tree"]
        head = repo["commits"][pr["head"]["sha"]]["tree"]
        out = []
        for path in sorted(set(base) | set(head)):
            if path not in base:
                out.append({"filename": path, "status": "added", "sha": blob_sha(head[path][1])})
            elif path not in head:
                out.append({"filename": path, "status": "removed", "sha": blob_sha(base[path][1])})
            elif base[path] != head[path]:
                out.append({"filename": path, "status": "modified", "sha": blob_sha(head[path][1])})
        return out

    def reviews(self, repo_id, number):
        self._enter("reviews", repo_id)
        return [dict(r) for r in self._repo(repo_id)["prs"][number]["reviews"]]

    def commits(self, repo_id, number):
        self._enter("commits", repo_id)
        return [{"sha": sha} for sha in self._repo(repo_id)["prs"][number]["_commits"]]

    def tree(self, repo_id, sha):
        self._enter("tree", repo_id)
        tree = self._repo(repo_id)["commits"][sha]["tree"]
        return [{"path": p, "mode": mode, "type": "blob", "sha": blob_sha(data), "size": len(data)}
                for p, (mode, data) in sorted(tree.items())]

    def blob(self, repo_id, sha):
        self._enter("blob", repo_id)
        return self._repo(repo_id)["blobs"][sha]

    def file_at(self, repo_id, ref, path):
        self._enter("file_at", repo_id)
        repo = self._repo(repo_id)
        sha = repo["branches"].get(ref, ref)
        commit = repo["commits"].get(sha)
        if commit is None:
            return None
        entry = commit["tree"].get(path)
        return entry[1] if entry else None

    def rulesets(self, repo_id):
        self._enter("rulesets", repo_id)
        return json.loads(json.dumps(self.rulesets_by_repo.get(repo_id, [])))

    def collaborators(self, repo_id):
        self._enter("collaborators", repo_id)
        return [dict(x) for x in self.collaborators_by_repo.get(repo_id, [])]

    def teams(self, repo_id):
        self._enter("teams", repo_id)
        return [dict(x) for x in self.teams_by_repo.get(repo_id, [])]

    def installations(self, repo_id):
        self._enter("installations", repo_id)
        return [dict(x) for x in self.installations_by_repo.get(repo_id, [])]

    def deploy_keys(self, repo_id):
        self._enter("deploy_keys", repo_id)
        return [dict(x) for x in self.deploy_keys_by_repo.get(repo_id, [])]

    def actions_settings(self, repo_id):
        self._enter("actions_settings", repo_id)
        return dict(self.actions_by_repo.get(repo_id, {"can_create_pull_requests": True, "default_workflow_permissions": "read"}))

    def workflow_runs(self, repo_id, workflow, branch=None):
        self._enter("workflow_runs", repo_id)
        return []

    def scan_health(self, repo_id):
        self._enter("scan_health", repo_id)
        return dict(self.scan.get(repo_id)) if self.scan.get(repo_id) else None

    def project(self, node_id):
        self._enter("project", node_id)
        p = self.projects.get(node_id)
        return dict(p) if p else None

    def user(self, user_id):
        self._enter("user", user_id)
        u = self.users.get(user_id)
        return dict(u) if u else None


# ---------------------------------------------------------------------------
# The fictional organization
# ---------------------------------------------------------------------------

TOOLING_ID, ENGINEERING_ID, STAGING_ID = 4100, 4200, 4300
WORKFLOW_BYTES = b"name: Open release requests\n"


def staging_ruleset(last_push=False, reviews=1, stale=True, check=V.STAGING_CHECK, strict=True, bypass=False,
                    no_force=True, no_delete=True, methods=("merge",)):
    rules = [{"type": "pull_request", "parameters": {"required_approving_review_count": reviews,
                                                     "dismiss_stale_reviews_on_push": stale,
                                                     "require_last_push_approval": last_push,
                                                     "require_code_owner_review": False,
                                                     "required_review_thread_resolution": False,
                                                     "allowed_merge_methods": list(methods)}},
             {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": strict,
                                                               "required_status_checks": [{"context": check, "integration_id": 77}]}}]
    if no_force:
        rules.append({"type": "non_fast_forward"})
    if no_delete:
        rules.append({"type": "deletion"})
    return {"id": 4501, "name": "carrydown release", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [{"actor_id": 1, "actor_type": "Team"}] if bypass else [], "rules": rules}


class World:
    """The fictional organization: tooling repository 4100, engineering repository 4200, private staging
    repository 4300, one enrolled project, one authorized approver and one administrator."""

    def __init__(self, approvers=(OWNER,), admins=(ADMIN,), extra_readers=(), attest_runtime=True, now=None):
        self.reader = FakeEvidenceReader()
        r = self.reader
        r.add_repo(TOOLING_ID, "acme/carrydown-tooling")
        r.add_repo(ENGINEERING_ID, "acme/expense-approvals")
        r.add_repo(STAGING_ID, "acme/expense-approvals-releases", files={".github/workflows/open-release-request.yml": WORKFLOW_BYTES})
        self.approvers, self.admins = list(approvers), list(admins)
        for uid, login in list(approvers) + list(admins) + list(extra_readers) + [OUTSIDER]:
            r.users[uid] = {"id": uid, "login": login}
        r.rulesets_by_repo[STAGING_ID] = [staging_ruleset()]
        r.rulesets_by_repo[ENGINEERING_ID] = [{"id": 4500, "name": "carrydown release", "target": "branch", "enforcement": "active",
                                               "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}}, "bypass_actors": [],
                                               "rules": [{"type": "required_status_checks", "parameters": {
                                                   "required_status_checks": [{"context": V.ENGINEERING_CHECK, "integration_id": 77}]}}]}]
        readers = [{"id": u, "login": l, "permission": "write"} for u, l in list(approvers) + list(admins) + list(extra_readers)]
        r.collaborators_by_repo[STAGING_ID] = readers
        r.collaborators_by_repo[ENGINEERING_ID] = readers + [{"id": OUTSIDER[0], "login": OUTSIDER[1], "permission": "read"}]
        r.scan[TOOLING_ID] = {"completed_at": V.utc_text(V.clock() - 60), "policy_commit_sha": None, "complete": True,
                              "oldest_outstanding_age_seconds": 0}
        r.projects["PVT_example"] = {"id": "PVT_example", "owner_id": 4400, "owner_type": "Organization", "public": False,
                                     "repository_ids": [ENGINEERING_ID], "reader_ids": [u for u, _ in list(approvers) + list(admins)]}
        self.extra_readers = list(extra_readers)
        self.attest_runtime = attest_runtime
        self.entry = self._entry()
        self.publish_policy()

    def _entry(self):
        r = self.reader
        entry = {
            "repository": "acme/expense-approvals", "repository_id": ENGINEERING_ID,
            "enrollment_id": V.enrollment_id_of("github.com", TOOLING_ID, ENGINEERING_ID), "policy_sha256": "",
            "staging_repository": "acme/expense-approvals-releases", "staging_repository_id": STAGING_ID,
            "staging_workflow_sha256": RS.sha256_bytes(WORKFLOW_BYTES),
            "staging_readers": {"user_ids": sorted([u for u, _ in self.approvers + self.admins] + [u for u, _ in self.extra_readers]),
                                "approved_service_ids": []},
            "approvers": [{"id": u, "login": l} for u, l in self.approvers],
            "administrators": [{"id": u, "login": l} for u, l in self.admins],
            "allowed_targets": {
                "engineering": {"host": "github.com", "repository_id": ENGINEERING_ID, "repository": "acme/expense-approvals"},
                "board": {"host": "github.com", "repository_id": ENGINEERING_ID, "owner_id": 4400, "project_id": "PVT_example"}},
            "governed_paths": ["docs/spec/**", "docs/context/**", "docs/release/**", "docs/dev/skills/**", "docs/ground-truth/**"],
            "engineer_edits": {"docs/spec/**": "request-only"}, "reuse_unchanged_preview": False, "offline_grace_days": 7,
            "verifier_sha": "9" * 40, "check_health_max_age_seconds": 900, "attestations": [],
        }
        r.repos[TOOLING_ID]["commits"]  # tooling commit must exist for the verifier pin
        if self.attest_runtime:
            entry["attestations"].append({"component": "runtime-isolation", "by_id": self.admins[0][0], "at": V.utc_text(r._clock - 3600),
                                          "expires_at": V.utc_text(r._clock + 86400 * 30),
                                          "subject": {"repository_id": ENGINEERING_ID, "environment_id": "managed-engineering-agents"},
                                          "note": "Engineering agents run as users without read access to owner workspaces"})
        entry["policy_sha256"] = V.policy_sha256_of(entry)
        return entry

    def publish_policy(self):
        """Write the current entry to enrollment.yaml in the tooling repository (as JSON, which the
        default parser reads) and make an earlier code commit the pinned verifier."""
        r = self.reader
        self.entry["policy_sha256"] = V.policy_sha256_of(self.entry)
        doc = {"format": 1, "host": "github.com", "tooling_repository_id": TOOLING_ID, "repositories": [self.entry]}
        if self.entry["verifier_sha"] not in r.repos[TOOLING_ID]["commits"]:
            code = r.set_file(TOOLING_ID, "verifier/verify_release.py", b"# verifier code\n")
            self.entry["verifier_sha"] = code
            self.entry["policy_sha256"] = V.policy_sha256_of(self.entry)
            doc["repositories"] = [self.entry]
        return r.set_file(TOOLING_ID, "enrollment.yaml", json.dumps(doc, sort_keys=True).encode("utf-8"))

    def update_policy(self, mutate):
        """Change the enrollment entry (mutate receives it), publish it and return the new Enrollment."""
        mutate(self.entry)
        self.publish_policy()
        return self.enrollment()

    def enrollment(self):
        return V.load_current_enrollment(ENGINEERING_ID, self.reader, "acme/carrydown-tooling")

    def land(self, files, branch, reviewer=OWNER, merge=True, approve=True, user=(0, "github-actions[bot]"), base_sha=None):
        """Open the pull request for a candidate branch, optionally review and merge it. Returns the
        pull request number."""
        r = self.reader
        n = r.open_pr(STAGING_ID, branch, files, user=user, base_sha=base_sha)
        if approve:
            r.review(STAGING_ID, n, reviewer[0], reviewer[1])
        if merge:
            r.merge(STAGING_ID, n)
        return n
