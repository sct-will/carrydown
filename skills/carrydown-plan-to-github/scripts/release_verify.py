#!/usr/bin/env python3
"""Verification of releases, as pure logic over an evidence reader. Standard library only.

This module reads no network, no token, no environment and no engineering checkout. Everything it
knows about the outside world comes through an EvidenceReader, an interface of read-only methods
that a real deployment backs with the GitHub API (release_github.py) and a test backs with an
in-memory model (tests/mock/fake_evidence.py). It imports only release_schema and the standard
library, so the independent verifier can carry it unchanged.

What is here (the names of section D15 of the specification)
  enrollment_id_of, policy_sha256_of   the stable identity and the policy digest of an enrollment (D9)
  load_current_enrollment              the current protected policy, found by the actual repository id
  verify_request                       a historical approval: the merged request, its review and its bytes
  verify_candidate                     the premerge check of a pending request or state branch
  replay_staging                       the authenticated event history of the staging repository
  authorize_content                    a short-lived VerifiedContext for release-class writes
  authorize_state_receipt              a VerifiedStateContext for state-only receipt writes
  verify_prerequisites, verify_targets component-by-component results from current evidence
Local owner approval (the "yes" path) has the same shape: load_local_evidence, verify_local_request
and local_replay build an ApprovalRecord from the private workspace, labeled authenticated false.

Rules this module keeps
  - A stored digest is never trusted. Every digest is recomputed from the bytes it names.
  - There is no force, ignore or skip argument anywhere.
  - A listing that is incomplete or truncated raises EvidenceUnavailable. It is never a clean result.
  - A refusal is a SchemaError whose code is a fixed reason code and whose message never holds a value
    from the data. Transport errors are mapped to evidence-unavailable without locators or bodies.
  - A VerifiedContext can be made only here, by authorize_content. A receipt, a request, a plain
    dict or a caller-supplied flag is never a context.

This module is imported by the other scripts. Run with --help to see this text.
"""
import argparse
import calendar
import os
import re
import stat as _stat
import sys
import time
from typing import NamedTuple, Optional

import release_schema as RS
from release_schema import SchemaError, canonical_json, loads_strict, sha256_bytes

CONTEXT_MAX_AGE_SECONDS = 60
POLL_EVENT_DIR = "events"
REQUEST_BRANCH = re.compile(r"request/([0-9a-f]{64})\Z")
STATE_BRANCH = re.compile(r"state/([0-9a-f]{64})\Z")
WORKFLOW_PATH = ".github/workflows/open-release-request.yml"
STAGING_CHECK = "carrydown-staging-verifier"
ENGINEERING_CHECK = "carrydown-release-verifier"
APPROVAL_TYPES = ("github-review", "local-owner")
LOCAL_COMMIT = "0" * 40

# component statuses of verify_prerequisites
VERIFIED = "verified"
NOT_VERIFIABLE = "not verifiable"
MISSING = "missing"

# Components that must be verified before a private upload, and before an export or a publication.
UPLOAD_COMPONENTS = ("enrollment", "staging-identity", "staging-readers", "staging-workflow", "staging-ruleset")
EXPORT_COMPONENTS = UPLOAD_COMPONENTS + ("verifier-code", "engineering-ruleset", "approvers", "scan-health",
                                         "runtime-isolation", "workspace-access")

# The reason code a component that is not verified maps to.
COMPONENT_CODES = {
    "enrollment": "policy-pointer-mismatch", "staging-identity": "staging-access-not-verified",
    "staging-readers": "staging-access-not-verified", "staging-workflow": "setup-not-verified",
    "staging-ruleset": "setup-not-verified", "verifier-code": "verifier-code-mismatch",
    "engineering-ruleset": "setup-not-verified", "approvers": "setup-not-verified",
    "scan-health": "verifier-unhealthy", "runtime-isolation": "setup-not-verified",
    "workspace-access": "workspace-unavailable", "destinations": "destination-access-not-verified",
}


# ---------------------------------------------------------------------------
# Errors and small helpers
# ---------------------------------------------------------------------------

class EvidenceUnavailable(SchemaError):
    """The evidence could not be read completely: a transport error, a permission the caller lacks,
    or a listing that is truncated. The message names no locator and no response body."""

    def __init__(self, detail=""):
        super().__init__("evidence-unavailable", "", detail)


def refuse(code, field="", detail=""):
    raise SchemaError(code, field, detail)


def clock():
    """The current time as seconds since the epoch. Tests replace this to fake time."""
    return time.time()


def to_epoch(text, field="time"):
    """Seconds since the epoch for a UTC time such as 2027-01-20T14:03:00Z."""
    if not (isinstance(text, str) and re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z", text)):
        refuse("schema-invalid", field, "must be a UTC time")
    return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ"))


def utc_text(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(seconds)))


def enrollment_id_of(host, tooling_repository_id, repository_id):
    """The stable identity of an enrolled project (D9): the digest of its host, the tooling repository
    id and the engineering repository id. It does not change when the policy changes."""
    return sha256_bytes(canonical_json({"host": host, "tooling_repository_id": tooling_repository_id,
                                        "repository_id": repository_id}))


def policy_sha256_of(entry):
    """The policy digest of an enrollment entry: the canonical entry with only policy_sha256 omitted."""
    if not isinstance(entry, dict):
        refuse("schema-invalid", "enrollment", "entry must be an object")
    return sha256_bytes(canonical_json({k: v for k, v in entry.items() if k != "policy_sha256"}))


def expected_artifacts(entries):
    """The repository artifacts of a manifest, as a receipt lists them: paths without repo/, sorted,
    without payloads. Raises when a file sits outside repo/ and payloads/."""
    out = []
    for e in entries:
        if not e["path"].startswith(("repo/", "payloads/")):
            refuse("receipt-projection-mismatch", "manifest", "a snapshot file is outside repo/ and payloads/")
        if e["path"].startswith("repo/"):
            rel = e["path"][len("repo/"):]
            RS.check_path(rel, "manifest")
            if rel.startswith("docs/release/"):
                refuse("receipt-projection-mismatch", "manifest", "a receipt is listed as an artifact")
            out.append({"path": rel, "sha256": e["sha256"], "bytes": e["bytes"], "mode": e["mode"]})
    return out


# ---------------------------------------------------------------------------
# The evidence reader interface
# ---------------------------------------------------------------------------

class EvidenceReader:
    """Read-only access to the facts a verification needs. Every method raises EvidenceUnavailable
    when the answer cannot be had completely. A list method follows every page of the listing, and
    raises when it cannot. Methods return None for a thing that does not exist (repository,
    pull_request, file_at).

    Shapes
      repository(ref)            ref is a numeric id or "owner/name". {id, full_name, private,
                                 visibility, default_branch, host, archived}
      branch_head(repo, branch)  the commit sha at the tip of the branch, or None
      first_parent_history(repo, ref)   commit shas from the oldest to ref, following first parents
      is_ancestor(repo, a, b)    True when commit a is an ancestor of, or equal to, commit b
      commit_exists(repo, sha)   True or False
      pull_requests(repo, base, state)  state open, closed or all; each {number, state, merged,
                                 merged_at, merge_commit_sha, head: {sha, ref, repo_id}, base:
                                 {ref, sha}, user: {id, login}}
      pull_request(repo, n)      one such record, or None
      pull_request_files(repo, n)   [{filename, status, sha}] for every file the request changes
      reviews(repo, n)           [{id, user: {id, login}, state, commit_id, submitted_at}]
      commits(repo, n)           [{sha}] oldest first, the last being the head
      tree(repo, sha)            the complete recursive tree: [{path, mode, type, sha, size}]
      blob(repo, sha)            the bytes of a blob, by blob sha
      file_at(repo, ref, path)   the bytes of a file at a commit, or None
      rulesets(repo)             the rulesets in the shape of the REST API
      collaborators(repo)        every account with access, direct and inherited: [{id, login, permission}]
      teams(repo)                [{id, slug, permission}]
      installations(repo)        installed Apps: [{id, slug}]
      deploy_keys(repo)          [{id, read_only}]
      actions_settings(repo)     {can_create_pull_requests, default_workflow_permissions}
      secret_names(repo)         the names (never the values) of the repository's Actions secrets
      workflow_runs(repo, workflow, branch)   [{id, status, conclusion, created_at}]
      scan_health(repo)          {completed_at, policy_commit_sha, complete, oldest_outstanding_age_seconds}
      project(node_id)           {id, owner_id, owner_type, public, repository_ids, reader_ids}
      user(user_id)              {id, login} or None
    """

    def _no(self):
        raise EvidenceUnavailable("this evidence reader does not provide that fact")

    def repository(self, ref): self._no()
    def branch_head(self, repo, branch): self._no()
    def first_parent_history(self, repo, ref): self._no()
    def is_ancestor(self, repo, ancestor, descendant): self._no()
    def commit_exists(self, repo, sha): self._no()
    def pull_requests(self, repo, base, state): self._no()
    def pull_request(self, repo, number): self._no()
    def pull_request_files(self, repo, number): self._no()
    def reviews(self, repo, number): self._no()
    def commits(self, repo, number): self._no()
    def tree(self, repo, sha): self._no()
    def blob(self, repo, sha): self._no()
    def file_at(self, repo, ref, path): self._no()
    def rulesets(self, repo): self._no()
    def collaborators(self, repo): self._no()
    def teams(self, repo): self._no()
    def installations(self, repo): self._no()
    def deploy_keys(self, repo): self._no()
    def actions_settings(self, repo): self._no()
    def secret_names(self, repo): self._no()
    def workflow_runs(self, repo, workflow, branch=None): self._no()
    def scan_health(self, repo): self._no()
    def project(self, node_id): self._no()
    def user(self, user_id): self._no()


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

class Enrollment(NamedTuple):
    """The captured protected policy of one enrolled repository (D9). entry is the full enrollment
    entry. parse turns the bytes of enrollment.yaml into a value (the caller supplies a YAML reader)."""
    host: str
    tooling_repository_id: int
    tooling_repository: str
    repository_id: int
    policy_commit_sha: str
    policy_sha256: str
    enrollment_id: str
    entry: dict
    parse: object

    enrolled = True

    @property
    def approver_ids(self):
        return [a["id"] for a in self.entry["approvers"]]

    @property
    def verifier_app_id(self):
        return self.entry.get("verifier_app_id")

    @property
    def governed_paths(self):
        return list(self.entry.get("governed_paths") or [])

    @property
    def engineer_edits(self):
        return dict(self.entry.get("engineer_edits") or {})


class LocalPolicy(NamedTuple):
    """The policy of a project that is not enrolled (the "yes" path). Its digest covers the released
    handling block, so a changed answer to the one question changes the policy and forces a new request."""
    policy_commit_sha: str
    policy_sha256: str
    enrollment_id: str

    enrolled = False


def local_policy(handling, repository):
    """LocalPolicy for a project that is not enrolled. handling is the released handling block of the
    plan (a dict). repository is owner/name. The stand-in values can never equal an enrollment."""
    body = {"handling": {k: handling[k] for k in sorted(handling or {})}, "kind": "local-owner"}
    return LocalPolicy(LOCAL_COMMIT, sha256_bytes(canonical_json(body)),
                       sha256_bytes(canonical_json({"kind": "local-owner", "repository": str(repository).casefold()})))


class ReviewInfo(NamedTuple):
    review_id: object
    reviewer_id: object
    pr_number: object
    head_sha: object
    merge_sha: object
    approved_at: str


class ApprovalRecord(NamedTuple):
    """A historical approval: a validated request, its manifest and activation batch, and the
    mechanism and identity that approved them. It proves approval, not active state and not
    present-day permission to publish."""
    request: dict
    request_id: str
    release_id: str
    manifest_bytes: bytes
    entries: list
    event: dict
    approval: object              # release_schema.VerifiedApproval
    review: object                # ReviewInfo, or None for a local approval
    policy: object                # the captured Enrollment, or the LocalPolicy

    @property
    def mechanism(self):
        return self.approval.type


class History(NamedTuple):
    """The authenticated event history. replay is a release_schema.ReplayResult. events are the
    verified batches in merge order. reviews maps event id to ReviewInfo (empty on the local path).
    tip is the staging default-branch head, if any."""
    replay: object
    events: tuple
    reviews: dict
    tip: Optional[str]


class Component(NamedTuple):
    name: str
    status: str
    evidence: str
    code: str


class CandidateReport(NamedTuple):
    ok: bool
    code: str
    kind: str
    request_id: Optional[str]
    event_id: Optional[str]
    reviewed: bool


class ResolvedTarget(NamedTuple):
    """A destination as the API describes it now. identity holds the same keys as the approved
    target (id, host, repository_id, repository or owner_id and project_id). public is True when
    anyone can read it. readers is the list of account ids that can read it, or None when they
    cannot be enumerated."""
    identity: dict
    public: bool
    readers: Optional[list]


_MINT = object()


class VerifiedContext:
    """Proof that a content write was authorized a moment ago. Made only by authorize_content. The
    release gate accepts nothing else for the release class, and only while it is fresh."""
    __slots__ = ("kind", "request_id", "release_id", "event_id", "mechanism", "authenticated", "policy_sha256",
                 "enrollment_id", "audience", "destinations", "target_ids", "targets", "entries", "receipt_digests",
                 "expires_at", "issued_at", "_frozen")

    def __init__(self, _mint=None, **fields):
        if _mint is not _MINT:
            raise TypeError("a verified context is made only by authorize_content or authorize_state_receipt")
        object.__setattr__(self, "_frozen", False)
        for name in self.__slots__:
            if name != "_frozen":
                object.__setattr__(self, name, fields.pop(name))
        if fields:
            raise TypeError("unknown context field")
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value):
        raise AttributeError("a verified context cannot be changed")

    def age(self, now=None):
        return (clock() if now is None else now) - self.issued_at

    def __repr__(self):
        return f"<VerifiedContext {self.kind} request {self.request_id[:12]}>"


# ---------------------------------------------------------------------------
# The enrollment (D9)
# ---------------------------------------------------------------------------

_ENTRY_KEYS = ("repository", "repository_id", "enrollment_id", "policy_sha256", "staging_repository",
               "staging_repository_id", "staging_workflow_sha256", "staging_readers", "approvers", "administrators",
               "allowed_targets", "governed_paths", "offline_grace_days", "verifier_sha", "attestations")


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check_entry(entry, host, tooling_id, repository_id):
    """Validate the parts of an enrollment entry this module relies on. Raises on a malformed entry."""
    if not isinstance(entry, dict):
        refuse("policy-pointer-mismatch", "enrollment", "entry must be an object")
    for key in _ENTRY_KEYS:
        if key not in entry:
            refuse("policy-pointer-mismatch", "enrollment", f"entry lacks {key}")
    if not _is_int(entry["repository_id"]) or entry["repository_id"] != repository_id:
        refuse("target-identity-mismatch", "enrollment", "entry names another repository id")
    want = enrollment_id_of(host, tooling_id, repository_id)
    if entry["enrollment_id"] != want:
        refuse("policy-pointer-mismatch", "enrollment", "enrollment_id does not match the stable identity")
    if entry["policy_sha256"] != policy_sha256_of(entry):
        refuse("policy-revision-mismatch", "enrollment", "policy_sha256 does not match the recomputed digest")
    for who in ("approvers", "administrators"):
        rows = entry[who]
        if not isinstance(rows, list) or not all(isinstance(r, dict) and _is_int(r.get("id")) for r in rows):
            refuse("policy-pointer-mismatch", "enrollment", f"{who} must be a list of account ids")
    readers = entry["staging_readers"]
    if not (isinstance(readers, dict) and isinstance(readers.get("user_ids"), list)):
        refuse("policy-pointer-mismatch", "enrollment", "staging_readers must list user_ids")
    if not isinstance(entry["attestations"], list):
        refuse("policy-pointer-mismatch", "enrollment", "attestations must be a list")
    if not isinstance(entry["allowed_targets"], dict) or not entry["allowed_targets"]:
        refuse("policy-pointer-mismatch", "enrollment", "allowed_targets must name at least one target")
    return entry


_GIT_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
EDIT_POLICIES = ("allowed", "request-only")


def _check_current(entry):
    """The fields only a current policy needs (WP7): the verifier App id that both required checks must
    come from, the pinned verifier commit, and the governed paths with their engineer edit policy. A
    historical policy captured by an older request is not asked for them."""
    if not _is_int(entry.get("verifier_app_id")) or entry["verifier_app_id"] <= 0:
        refuse("policy-pointer-mismatch", "enrollment", "verifier_app_id must be the numeric id of the verifier App")
    if not isinstance(entry.get("verifier_sha"), str) or not _GIT_COMMIT.match(entry["verifier_sha"]):
        refuse("policy-pointer-mismatch", "enrollment", "verifier_sha must be a full commit id")
    paths = entry["governed_paths"]
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p and not p.startswith("/") for p in paths):
        refuse("policy-pointer-mismatch", "enrollment", "governed_paths must list repository paths such as docs/spec/**")
    edits = entry.get("engineer_edits", {})
    if not isinstance(edits, dict) or not all(isinstance(k, str) and v in EDIT_POLICIES for k, v in edits.items()):
        refuse("policy-pointer-mismatch", "enrollment", "engineer_edits must map a governed path to allowed or request-only")
    return entry


def _parse_enrollment(parse, data):
    try:
        text = bytes(data).decode("utf-8")
        value = (parse or loads_strict)(text)
    except (SchemaError, ValueError, UnicodeDecodeError):
        refuse("policy-pointer-mismatch", "enrollment", "enrollment.yaml cannot be read")
    except Exception:   # a YAML reader raises its own error type; none of its text is repeated
        refuse("policy-pointer-mismatch", "enrollment", "enrollment.yaml cannot be read")
    if not isinstance(value, dict) or value.get("format") != 1 or not isinstance(value.get("repositories"), list):
        refuse("policy-pointer-mismatch", "enrollment", "enrollment.yaml has an unknown format")
    return value


def _find_entry(doc, repository_id):
    rows = [r for r in doc["repositories"] if isinstance(r, dict) and r.get("repository_id") == repository_id]
    if len(rows) != 1:
        refuse("policy-pointer-mismatch", "enrollment", "the repository is not enrolled exactly once")
    return rows[0]


def load_current_enrollment(repository_id, reader, tooling_repository, parse=None, pointer_enrollment_id=None,
                            host="github.com"):
    """The current protected policy for the repository with this numeric id (D9).

    repository_id is the actual id the API reports, never a name from a proposed file. tooling_repository
    is owner/name or an id. The policy is read from the tooling repository's default-branch tip, and its
    commit is recorded. parse turns enrollment.yaml text into a value; it defaults to strict JSON, and a
    caller that reads YAML passes its own reader. pointer_enrollment_id, when given, is the id in the
    project's .carrydown/release-policy.yaml, which must equal the stable id (policy-pointer-mismatch).
    Raises SchemaError with a fixed code."""
    tooling = reader.repository(tooling_repository)
    if tooling is None:
        refuse("policy-pointer-mismatch", "enrollment", "the tooling repository cannot be found")
    tip = reader.branch_head(tooling["id"], tooling["default_branch"])
    if not tip:
        refuse("evidence-unavailable", "enrollment", "the tooling repository has no default-branch head")
    data = reader.file_at(tooling["id"], tip, "enrollment.yaml")
    if data is None:
        refuse("policy-pointer-mismatch", "enrollment", "enrollment.yaml is missing")
    doc = _parse_enrollment(parse, data)
    if doc.get("host") != host or doc.get("tooling_repository_id") != tooling["id"]:
        refuse("policy-pointer-mismatch", "enrollment", "enrollment.yaml names another host or tooling repository")
    entry = _check_current(_check_entry(_find_entry(doc, repository_id), host, tooling["id"], repository_id))
    if pointer_enrollment_id is not None and pointer_enrollment_id != entry["enrollment_id"]:
        refuse("policy-pointer-mismatch", "pointer", "the project's pointer names another enrollment")
    return Enrollment(host, tooling["id"], tooling["full_name"], repository_id, tip, entry["policy_sha256"],
                      entry["enrollment_id"], entry, parse)


def capture_enrollments(reader, tooling_repository, policy_commit_sha, policy_bytes, parse=None, host="github.com"):
    """Every enrolled repository of one captured policy, for a verifier run (D9).

    The launcher reads enrollment.yaml from its own checkout of the tooling repository's protected default
    branch and passes the file and its commit here as data. This function accepts them only when the commit
    is the current head of the tooling repository's default branch and the API returns the same bytes for
    that commit, so a file from another branch or a stale checkout is refused (policy-revision-mismatch).
    The result is a list of Enrollment records, one per repository, each fully validated."""
    tooling = reader.repository(tooling_repository)
    if tooling is None:
        refuse("policy-pointer-mismatch", "enrollment", "the tooling repository cannot be found")
    tip = reader.branch_head(tooling["id"], tooling["default_branch"])
    if not tip or tip != policy_commit_sha:
        refuse("policy-revision-mismatch", "policy_commit_sha", "is not the head of the protected default branch")
    served = reader.file_at(tooling["id"], tip, "enrollment.yaml")
    if served is None or bytes(served) != bytes(policy_bytes):
        refuse("policy-revision-mismatch", "enrollment", "the policy file differs from the protected default branch")
    doc = _parse_enrollment(parse, policy_bytes)
    if doc.get("host") != host or doc.get("tooling_repository_id") != tooling["id"]:
        refuse("policy-pointer-mismatch", "enrollment", "enrollment.yaml names another host or tooling repository")
    out, seen = [], set()
    for row in doc["repositories"]:
        rid = row.get("repository_id") if isinstance(row, dict) else None
        if not _is_int(rid) or rid in seen:
            refuse("policy-pointer-mismatch", "enrollment", "a repository is listed twice or has no numeric id")
        seen.add(rid)
        entry = _check_current(_check_entry(row, host, tooling["id"], rid))
        out.append(Enrollment(host, tooling["id"], tooling["full_name"], rid, tip, entry["policy_sha256"],
                              entry["enrollment_id"], entry, parse))
    return out


def captured_policy(reader, enrollment, commit_sha, policy_sha256):
    """The policy a request or event captured, taken from an ancestor of the tooling repository's
    current protected tip (D9). Raises policy-revision-mismatch when the commit is not such an
    ancestor, or when the digest or the stable identity differ."""
    if commit_sha == enrollment.policy_commit_sha:
        entry = enrollment.entry
    else:
        if not reader.commit_exists(enrollment.tooling_repository_id, commit_sha) or \
                not reader.is_ancestor(enrollment.tooling_repository_id, commit_sha, enrollment.policy_commit_sha):
            refuse("policy-revision-mismatch", "policy_commit_sha", "is not an ancestor of the current protected policy")
        data = reader.file_at(enrollment.tooling_repository_id, commit_sha, "enrollment.yaml")
        if data is None:
            refuse("policy-revision-mismatch", "policy_commit_sha", "has no enrollment.yaml")
        doc = _parse_enrollment(enrollment.parse, data)
        entry = _find_entry(doc, enrollment.repository_id)
        _check_entry(entry, enrollment.host, enrollment.tooling_repository_id, enrollment.repository_id)
    if entry["policy_sha256"] != policy_sha256 or entry["enrollment_id"] != enrollment.enrollment_id:
        refuse("policy-revision-mismatch", "policy_sha256", "does not match the captured policy")
    return enrollment._replace(policy_commit_sha=commit_sha, policy_sha256=entry["policy_sha256"], entry=entry)


# ---------------------------------------------------------------------------
# Staging objects (D10): reading and checking a request pull request
# ---------------------------------------------------------------------------

def _staging(enrollment):
    return enrollment.entry["staging_repository_id"]


def _default_branch(reader, repo_id):
    repo = reader.repository(repo_id)
    if repo is None:
        refuse("staging-access-not-verified", "staging", "the repository cannot be found by its numeric id")
    return repo["default_branch"]


def _json_at(reader, repo_id, head, merge, path, label):
    """The bytes of path, identical at the final reviewed head and the merge commit (merge is None
    for a pending branch, which has only a head)."""
    a = reader.file_at(repo_id, head, path)
    if a is None:
        refuse("approval-not-found", label, "is missing at the final head")
    if merge is not None:
        b = reader.file_at(repo_id, merge, path)
        if b is None:
            refuse("approval-not-found", label, "is missing at the merge commit")
        if a != b:
            refuse("sha256-mismatch", label, "differs between the final head and the merge commit")
    return bytes(a)


def _verify_snapshot(reader, repo_id, sha, release_id, entries):
    """The snapshot under releases/<release id>/snapshot at one revision holds exactly the manifest's
    files: no missing, extra or unsafe file, with the manifest's bytes, length and mode."""
    prefix = f"releases/{release_id}/snapshot/"
    found = {}
    for node in reader.tree(repo_id, sha):
        path = node["path"]
        if path.startswith(prefix):
            if node["type"] == "tree":
                continue
            if node["type"] != "blob" or node["mode"] not in RS.MODES:
                refuse("unsafe-artifact-path", "snapshot", "contains a link, a submodule or an unsafe file mode")
            found[path[len(prefix):]] = node
    want = {e["path"]: e for e in entries}
    if set(found) != set(want):
        refuse("sha256-mismatch", "snapshot", "membership differs from the manifest")
    for path, entry in sorted(want.items()):
        node = found[path]
        if node["mode"] != entry["mode"]:
            refuse("sha256-mismatch", "snapshot", "a file mode differs from the manifest")
        data = reader.blob(repo_id, node["sha"])
        if len(data) != entry["bytes"] or sha256_bytes(data) != entry["sha256"]:
            refuse("sha256-mismatch", "snapshot", "a file differs from the manifest")


def fetch_snapshot(reader, enrollment, record):
    """{snapshot path: bytes} of an approved release, read from the staging repository at the merge commit
    and checked against the manifest. It rebuilds a workspace that lost its snapshot from verified
    evidence; nothing it returns is trusted before that check."""
    repo_id = _staging(enrollment)
    sha = record.review.merge_sha
    _verify_snapshot(reader, repo_id, sha, record.release_id, record.entries)
    prefix = f"releases/{record.release_id}/snapshot/"
    out = {}
    for node in reader.tree(repo_id, sha):
        if node["path"].startswith(prefix) and node["type"] == "blob":
            out[node["path"][len(prefix):]] = bytes(reader.blob(repo_id, node["sha"]))
    return out


def _effective_review(reviews, commits, head_sha, merged_at, approver_ids):
    """The effective approving review on the final head by an authorized account, or a refusal.

    Per reviewer only the last approving, changes-requested or dismissed review counts, so a later
    changes request or a dismissal removes an approval. The review must name the final head, must
    precede the merge, and no commit may follow the head."""
    last = {}
    for r in sorted(reviews, key=lambda r: (to_epoch(r["submitted_at"], "review") if r.get("submitted_at") else 0, str(r["id"]))):
        if r["state"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            last[r["user"]["id"]] = r
    approved = [r for r in last.values() if r["state"] == "APPROVED"]
    if not approved:
        refuse("approval-not-found", "review", "no approving review is in effect")
    if not commits or commits[-1]["sha"] != head_sha:
        refuse("approval-not-on-final-revision", "review", "a commit follows the reviewed head")
    on_head = [r for r in approved if r["commit_id"] == head_sha]
    if not on_head:
        refuse("approval-not-on-final-revision", "review", "the approval was given to an earlier revision")
    if merged_at is not None:
        on_head = [r for r in on_head if to_epoch(r["submitted_at"], "review") <= merged_at]
        if not on_head:
            refuse("approval-not-on-final-revision", "review", "the approval came after the merge")
    allowed = set(approver_ids)
    authorized = [r for r in on_head if r["user"]["id"] in allowed]
    if not authorized:
        refuse("approver-not-authorized", "review", "the approving account is not an authorized approver")
    best = max(authorized, key=lambda r: (to_epoch(r["submitted_at"], "review"), str(r["id"])))
    return best


def _classify_files(files, kind, ident):
    """The paths a candidate branch adds, grouped. Every file must be added, never modified, removed or
    renamed, and must sit in a known immutable location."""
    out = {"event": None, "request": None, "releases": []}
    for f in files:
        if f["status"] != "added":
            refuse("artifact-operation-unsupported", "candidate", "changes, removes or renames an existing file")
        path = f["filename"]
        parts = path.split("/")
        if len(parts) == 2 and parts[0] == "events" and re.fullmatch(r"[0-9a-f]{64}\.json", parts[1]):
            if out["event"] is not None:
                refuse("unsafe-artifact-path", "candidate", "adds more than one event batch")
            out["event"] = path
        elif kind == "request" and path == f"requests/{ident}/approval-request.json":
            out["request"] = path
        elif kind == "request" and len(parts) >= 3 and parts[0] == "releases" and re.fullmatch(r"[0-9a-f]{64}", parts[1]) and \
                (parts[2] == "snapshot" or (len(parts) == 3 and parts[2] == "content-manifest.json")):
            out["releases"].append(path)
        else:
            refuse("unsafe-artifact-path", "candidate", "adds a file outside the allowed locations")
    if out["event"] is None:
        refuse("unsafe-artifact-path", "candidate", "adds no event batch")
    if kind == "request" and out["request"] is None:
        refuse("unsafe-artifact-path", "candidate", "adds no request")
    return out


def _read_request_objects(reader, repo_id, head, merge, request_id, files=None):
    """The request, manifest and entries named by a request branch, verified at the head (and at the
    merge commit when there is one). Returns (request, manifest_bytes, entries)."""
    raw = _json_at(reader, repo_id, head, merge, f"requests/{request_id}/approval-request.json", "request")
    request = loads_strict(raw)
    RS.validate_request(request)
    if request["request_sha256"] != request_id or RS.hash_request(request) != request_id:
        refuse("sha256-mismatch", "request", "the request digest does not match its id")
    release_id = request["release_id"]
    manifest_bytes = _json_at(reader, repo_id, head, merge, f"releases/{release_id}/content-manifest.json", "manifest")
    if sha256_bytes(manifest_bytes) != release_id:
        refuse("sha256-mismatch", "manifest", "the manifest digest does not match the release id")
    entries = RS.validate_manifest(manifest_bytes)
    if request["receipt_template"]["artifacts"] != expected_artifacts(entries):
        refuse("receipt-projection-mismatch", "request", "the receipt template does not match the manifest")
    for sha in (head,) if merge is None else (head, merge):
        _verify_snapshot(reader, repo_id, sha, release_id, entries)
    return request, manifest_bytes, entries


def _event_for(reader, repo_id, head, merge, path, ident_kind, ident, request_id):
    raw = _json_at(reader, repo_id, head, merge, path, "event")
    event = loads_strict(raw)
    RS.validate_event(event)
    if f"events/{event['event_id']}.json" != path:
        refuse("sha256-mismatch", "event", "the event digest does not match its file name")
    if ident_kind == "state" and event["event_id"] != ident:
        refuse("sha256-mismatch", "event", "the event id does not match the branch")
    if ident_kind == "request":
        mine = [t for t in event["transitions"] if t["request_id"] == request_id]
        if len(mine) != 1 or (mine[0]["from"], mine[0]["to"]) != ("prepared", "active"):
            refuse("state-history-invalid", "event", "does not activate the request it carries")
    return event


def _verify_merged(reader, enrollment, pr, now=None):
    """Verify one merged pull request of the staging repository: its branch, files, bytes at the head
    and the merge commit, and its review. Returns (kind, ident, event, review_info, request_objects)."""
    repo_id = _staging(enrollment)
    branch = (pr.get("head") or {}).get("ref", "")
    m = REQUEST_BRANCH.fullmatch(branch)
    kind, ident = ("request", m.group(1)) if m else ("state", (STATE_BRANCH.fullmatch(branch) or [None, None])[1])
    if ident is None:
        refuse("approval-not-found", "branch", "is not a request or state branch")
    if not pr.get("merged") or not pr.get("merge_commit_sha"):
        refuse("approval-not-found", "pull request", "is not merged")
    if (pr["head"].get("repo_id") != repo_id) or (pr.get("base") or {}).get("ref") != _default_branch(reader, repo_id):
        refuse("target-identity-mismatch", "pull request", "does not belong to the staging repository's default branch")
    head, merge = pr["head"]["sha"], pr["merge_commit_sha"]
    paths = _classify_files(reader.pull_request_files(repo_id, pr["number"]), kind, ident)
    request_objects = None
    if kind == "request":
        request_objects = _read_request_objects(reader, repo_id, head, merge, ident)
    event = _event_for(reader, repo_id, head, merge, paths["event"], kind, ident, ident if kind == "request" else None)
    captured = captured_policy(reader, enrollment, event["policy_commit_sha"], event["policy_sha256"])
    merged_at = to_epoch(pr["merged_at"], "merged_at") if pr.get("merged_at") else None
    review = _effective_review(reader.reviews(repo_id, pr["number"]), reader.commits(repo_id, pr["number"]), head,
                               merged_at, captured.approver_ids)
    info = ReviewInfo(review["id"], review["user"]["id"], pr["number"], head, merge, review["submitted_at"])
    return kind, ident, event, info, request_objects


def _merged_prs(reader, enrollment):
    repo_id = _staging(enrollment)
    base = _default_branch(reader, repo_id)
    merged = [p for p in reader.pull_requests(repo_id, base, "closed") if p.get("merged")]
    order = reader.first_parent_history(repo_id, reader.branch_head(repo_id, base))
    index = {sha: i for i, sha in enumerate(order)}
    rows = []
    for p in merged:
        branch = (p.get("head") or {}).get("ref", "")
        if not (REQUEST_BRANCH.fullmatch(branch) or STATE_BRANCH.fullmatch(branch)):
            continue
        if p.get("merge_commit_sha") not in index:
            refuse("state-history-invalid", "history", "a merged request is not on the default branch")
        rows.append((index[p["merge_commit_sha"]], p))
    return [p for _, p in sorted(rows, key=lambda r: r[0])], reader.branch_head(repo_id, base)


def replay_staging(reader, enrollment):
    """The authenticated event history of the staging repository (D13), replayed in merge order.

    Every merged request or state pull request is verified: its files, its bytes at the final head and
    the merge commit, and an effective authorized review under the policy the batch captured. Then
    release_schema.replay_state checks the chain. Returns History. Raises state-history-invalid for a
    broken chain, mixed-release when a second request would become active, and the specific code for
    a pull request that fails verification."""
    prs, tip = _merged_prs(reader, enrollment)
    events, reviews = [], {}
    for pr in prs:
        _, _, event, info, _ = _verify_merged(reader, enrollment, pr)
        events.append(event)
        reviews[event["event_id"]] = info
    return History(_replay(events), tuple(events), reviews, tip)


def _replay(events):
    try:
        return RS.replay_state(events)
    except SchemaError as e:
        if e.code == "state-history-invalid" and "more than one request would be active" in (e.detail or ""):
            refuse("mixed-release", e.field, "more than one request would be active")
        raise


# ---------------------------------------------------------------------------
# verify_request, verify_candidate
# ---------------------------------------------------------------------------

def verify_request(request_id, reader, enrollment):
    """The historical approval of one request (D10). Finds exactly one merged request pull request in the
    enrolled staging repository by branch and request id, reads the request, manifest, snapshot and
    activation batch at the final head and the merge commit, recomputes every digest and checks the
    effective authorized review on the final head. It proves approval, not that the request is
    active, unexpired or allowed under today's policy; see authorize_content. Returns ApprovalRecord."""
    if not (isinstance(request_id, str) and re.fullmatch(r"[0-9a-f]{64}", request_id)):
        refuse("approval-not-found", "request_id", "must be 64 lowercase hexadecimal characters")
    repo_id = _staging(enrollment)
    base = _default_branch(reader, repo_id)
    branch = f"request/{request_id}"
    candidates = [p for p in reader.pull_requests(repo_id, base, "all") if (p.get("head") or {}).get("ref") == branch]
    merged = [p for p in candidates if p.get("merged")]
    if len(merged) != 1:
        refuse("approval-not-found", "pull request", "no single merged request was found")
    kind, ident, event, info, objects = _verify_merged(reader, enrollment, merged[0])
    request, manifest_bytes, entries = objects
    captured = captured_policy(reader, enrollment, request["policy_commit_sha"], request["policy_sha256"])
    if request["enrollment_id"] != enrollment.enrollment_id:
        refuse("policy-pointer-mismatch", "request", "names another enrollment")
    if info.reviewer_id not in captured.approver_ids:
        refuse("approver-not-authorized", "review", "the approving account is not an authorized approver")
    approval = RS.VerifiedApproval(request_id, "github-review", True)
    return ApprovalRecord(request, request_id, request["release_id"], manifest_bytes, entries, event, approval, info, captured)


def _expected_previous(history_events):
    """The tip a new batch must name as its predecessor."""
    return history_events[-1]["event_id"] if history_events else None


def verify_candidate(reader, enrollment, pull_number, now=None):
    """The premerge check of the staging repository for one open pull request (D10, WP7 item 5).

    Validates a request or state branch against the current protected policy and the current default
    branch: only new immutable files; exact snapshot membership; digest exclusions; the receipt
    template against the manifest; the request's policy against the current policy; the expected
    predecessor event; an up-to-date branch; and an effective authorized review on the final head.
    Returns a CandidateReport and never raises for a failed check. ok is True only when every check
    passes, including the review. A branch with no review yet reports code approval-not-found and
    reviewed False, so a caller can tell a pending branch from a bad one."""
    repo_id = _staging(enrollment)
    request_id = event_id = None
    kind = "unknown"
    try:
        pr = reader.pull_request(repo_id, pull_number)
        if pr is None or pr.get("state") != "open" or pr.get("merged"):
            refuse("approval-not-found", "pull request", "is not open")
        branch = (pr.get("head") or {}).get("ref", "")
        m = REQUEST_BRANCH.fullmatch(branch)
        s = STATE_BRANCH.fullmatch(branch)
        if not (m or s):
            refuse("unsafe-artifact-path", "branch", "is not a request or state branch")
        kind, ident = ("request", m.group(1)) if m else ("state", s.group(1))
        request_id = ident if m else None
        base = _default_branch(reader, repo_id)
        if pr["head"].get("repo_id") != repo_id or pr["base"]["ref"] != base:
            refuse("target-identity-mismatch", "pull request", "does not belong to the staging repository's default branch")
        head = pr["head"]["sha"]
        tip = reader.branch_head(repo_id, base)
        if not reader.is_ancestor(repo_id, tip, head):
            refuse("state-history-invalid", "branch", "is not up to date with the default branch")
        paths = _classify_files(reader.pull_request_files(repo_id, pull_number), kind, ident)
        request = None
        if kind == "request":
            request, _, _ = _read_request_objects(reader, repo_id, head, None, ident)
            if request["policy_sha256"] != enrollment.policy_sha256 or request["policy_commit_sha"] != enrollment.policy_commit_sha:
                refuse("policy-revision-mismatch", "request", "does not capture the current policy")
            if request["enrollment_id"] != enrollment.enrollment_id:
                refuse("policy-pointer-mismatch", "request", "names another enrollment")
        event = _event_for(reader, repo_id, head, None, paths["event"], kind, ident, request_id)
        event_id = event["event_id"]
        if event["policy_sha256"] != enrollment.policy_sha256 or event["policy_commit_sha"] != enrollment.policy_commit_sha:
            refuse("policy-revision-mismatch", "event", "does not capture the current policy")
        history = replay_staging(reader, enrollment)
        tip_event = history.replay.tip
        if any(t["previous_event_id"] != tip_event for t in event["transitions"]):
            refuse("state-history-invalid", "event", "names a predecessor that is no longer the current state")
        # the batch must replay cleanly on top of the current history
        _replay(list(history.events) + [event])
        if request is not None and request["supersedes_request_id"] != history.replay.active:
            refuse("state-history-invalid", "request", "supersedes a request that is not the current active one")
        if request is not None and request["supersedes_request_id"] is not None:
            if not any(t["request_id"] == request["supersedes_request_id"] and t["to"] == "superseded" for t in event["transitions"]):
                refuse("state-history-invalid", "event", "does not supersede the request it replaces")
        if kind == "state":
            for t in event["transitions"]:
                if t["to"] == "active":
                    refuse("state-history-invalid", "event", "a state branch cannot activate a request")
        commits = reader.commits(repo_id, pull_number)
        _effective_review(reader.reviews(repo_id, pull_number), commits, head, None, enrollment.approver_ids)
        return CandidateReport(True, "", kind, request_id, event_id, True)
    except SchemaError as e:
        return CandidateReport(False, e.code, kind, request_id, event_id, e.code not in ("approval-not-found",))


# ---------------------------------------------------------------------------
# The local ("yes" path) equivalents
# ---------------------------------------------------------------------------

class LocalEvidence(NamedTuple):
    request_bytes: bytes
    approval: dict
    manifest_bytes: bytes
    events: tuple


def _read_regular(path):
    try:
        st = os.lstat(path)
        if not _stat.S_ISREG(st.st_mode):
            refuse("approval-not-found", "workspace", "a record is not a regular file")
        with open(path, "rb") as handle:
            return handle.read()
    except FileNotFoundError:
        return None
    except OSError:
        refuse("evidence-unavailable", "workspace", "a record cannot be read")


def local_events(workspace):
    """Every event batch in <workspace>/events, ordered by the chain of previous_event_id from the
    first batch. A file that is not a valid batch, a gap or a fork raises state-history-invalid."""
    folder = os.path.join(workspace, "events")
    batches = {}
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if not re.fullmatch(r"[0-9a-f]{64}\.json", name):
                continue
            raw = _read_regular(os.path.join(folder, name))
            batch = loads_strict(raw)
            RS.validate_event(batch)
            if f"{batch['event_id']}.json" != name:
                refuse("sha256-mismatch", "event", "the event digest does not match its file name")
            batches[batch["event_id"]] = batch
    ordered, tip = [], None
    remaining = dict(batches)
    while remaining:
        nxt = [b for b in remaining.values() if b["transitions"][0]["previous_event_id"] == tip]
        if len(nxt) != 1:
            refuse("state-history-invalid", "events", "the event chain has a gap or a fork")
        ordered.append(nxt[0])
        tip = nxt[0]["event_id"]
        del remaining[tip]
    return tuple(ordered)


def local_replay(workspace):
    """History for the "yes" path, from the owner's own event files. Labeled unauthenticated by its
    records; never accepted for an enrolled project."""
    events = local_events(workspace)
    return History(_replay(list(events)), events, {}, None)


def load_local_evidence(workspace, request_id):
    """The private records of one request: the request, its approval.json and the manifest."""
    if not (isinstance(request_id, str) and re.fullmatch(r"[0-9a-f]{64}", request_id)):
        refuse("approval-not-found", "request_id", "must be 64 lowercase hexadecimal characters")
    folder = os.path.join(workspace, "requests", request_id)
    request_bytes = _read_regular(os.path.join(folder, "approval-request.json"))
    if request_bytes is None:
        refuse("approval-not-found", "request", "the request record is missing")
    approval_bytes = _read_regular(os.path.join(folder, "approval.json"))
    if approval_bytes is None:
        refuse("approval-not-found", "approval", "no approval was recorded for this request")
    request = loads_strict(request_bytes)
    release_id = request.get("release_id") if isinstance(request, dict) else None
    if not (isinstance(release_id, str) and re.fullmatch(r"[0-9a-f]{64}", release_id)):
        refuse("schema-invalid", "request", "has no release id")
    manifest_bytes = _read_regular(os.path.join(workspace, "releases", release_id, "content-manifest.json"))
    if manifest_bytes is None:
        refuse("approval-not-found", "manifest", "the manifest record is missing")
    return LocalEvidence(request_bytes, loads_strict(approval_bytes), manifest_bytes, local_events(workspace))


APPROVAL_FILE_KEYS = ("type", "authenticated", "request_sha256", "content_manifest_sha256", "approved_at", "git_identity",
                      "event_id")


def verify_local_request(evidence, request_id, policy=None):
    """The "yes" path approval of a request, from the private records (D6, D10). Evidence is
    local-owner and authenticated false. Checks, in order: the request's recomputed digest against the
    digest the approval names (approval-scope-mismatch when a request was edited after approval), the
    request digest against its id, the manifest against the release id, and the activation batch.
    approval.json that says anything but local-owner and false is refused (unauthenticated-release)."""
    approval = evidence.approval
    if not isinstance(approval, dict) or set(approval) != set(APPROVAL_FILE_KEYS):
        refuse("approval-not-found", "approval", "is not a recognized approval record")
    if approval["type"] != "local-owner" or approval["authenticated"] is not False:
        refuse("unauthenticated-release", "approval", "is not a local owner approval")
    request = loads_strict(evidence.request_bytes)
    if not isinstance(request, dict) or "request_sha256" not in request:
        refuse("schema-invalid", "request", "has no digest field")
    try:
        recomputed = RS.hash_request(request)
    except SchemaError:
        refuse("approval-scope-mismatch", "request", "can no longer be read as the approved request")
    if approval["request_sha256"] != recomputed or request_id != recomputed:
        refuse("approval-scope-mismatch", "request", "differs from the request that was approved")
    RS.validate_request(request)
    manifest_bytes = evidence.manifest_bytes
    if sha256_bytes(manifest_bytes) != request["release_id"] or approval["content_manifest_sha256"] != request["release_id"]:
        refuse("sha256-mismatch", "manifest", "does not match the approved release id")
    entries = RS.validate_manifest(manifest_bytes)
    if request["receipt_template"]["artifacts"] != expected_artifacts(entries):
        refuse("receipt-projection-mismatch", "request", "the receipt template does not match the manifest")
    event = next((b for b in evidence.events if b["event_id"] == approval["event_id"]), None)
    if event is None:
        refuse("approval-not-found", "event", "the activation batch is missing")
    mine = [t for t in event["transitions"] if t["request_id"] == request_id]
    if len(mine) != 1 or (mine[0]["from"], mine[0]["to"]) != ("prepared", "active"):
        refuse("state-history-invalid", "event", "does not activate this request")
    if policy is not None and (request["policy_sha256"], request["enrollment_id"]) != (policy.policy_sha256, policy.enrollment_id):
        pass   # a policy change is a matter for authorize_content, which reports policy-revision-mismatch
    verified = RS.VerifiedApproval(request_id, "local-owner", False)
    info = ReviewInfo(None, None, None, None, None, approval["approved_at"])
    captured = LocalPolicy(request["policy_commit_sha"], request["policy_sha256"], request["enrollment_id"])
    return ApprovalRecord(request, request_id, request["release_id"], manifest_bytes, entries, event, verified, info, captured)


def verify_snapshot_dir(snapshot_dir, entries):
    """The snapshot folder on disk holds exactly the manifest's files, with the manifest's bytes. A
    symbolic link, a non-regular file, a missing or extra file or a digest difference raises before
    any other work. Nothing is written."""
    found = RS._walk_snapshot(snapshot_dir)        # refuses links, submodules and non-regular files
    by_path = {rel: full for rel, full in found}
    want = {e["path"]: e for e in entries}
    if set(by_path) != set(want):
        refuse("sha256-mismatch", "snapshot", "membership differs from the manifest")
    for path, entry in want.items():
        digest, size = RS._digest_and_size(by_path[path])
        if digest != entry["sha256"] or size != entry["bytes"]:
            refuse("sha256-mismatch", "snapshot", "a file differs from the manifest")


# ---------------------------------------------------------------------------
# authorize_content, authorize_state_receipt
# ---------------------------------------------------------------------------

def _same_identity(approved, actual):
    """The approved target and the resolved one agree on every key except the display fields. The
    numeric ids decide; a renamed repository keeps its identity, and a different repository that took
    the old name does not inherit the approval."""
    keys = [k for k in approved if k not in ("id", "repository")]
    return all(actual.get(k) == approved[k] for k in keys)


def verify_targets(reader, policy, wanted_targets, audience):
    """Resolve the destinations of a request against the API now (D4, D14). wanted_targets is the
    request's list of target dicts. Returns {target id: ResolvedTarget}. An enrolled policy also
    requires each target to equal an entry of the enrollment's allowed_targets. A repository that
    cannot be found, a changed numeric id, another host, a board with a different node id or owner,
    or a public destination for a repo-readers audience is refused before any write."""
    out = {}
    allowed = policy.entry["allowed_targets"] if getattr(policy, "enrolled", False) else None
    for t in wanted_targets:
        if allowed is not None:
            row = allowed.get(t["id"])
            if not isinstance(row, dict) or {k: v for k, v in t.items() if k != "id"} != row:
                refuse("destination-not-allowed", "targets", "a target is not in the enrollment's allowed targets")
        if "project_id" in t:
            proj = reader.project(t["project_id"])
            if proj is None or proj.get("id") != t["project_id"] or proj.get("owner_id") != t["owner_id"]:
                refuse("target-identity-mismatch", "targets", "the board has another node id or owner")
            if t["repository_id"] not in (proj.get("repository_ids") or []):
                refuse("target-identity-mismatch", "targets", "the board is not linked to the approved repository")
            ident = dict(t)
            readers = proj.get("reader_ids")
            if audience == "repo-readers" and getattr(policy, "enrolled", False):
                if readers is None:
                    if not _attested(policy.entry, "destination-readers", {"repository_id": t["repository_id"], "owner_id": t["owner_id"],
                                                                         "project_id": t["project_id"]}, clock()):
                        refuse("destination-access-not-verified", "targets", "the board's readers cannot be listed and no current attestation covers them")
                else:
                    eng, _why = _call(reader.collaborators, t["repository_id"])
                    if eng is not None and set(readers) - {p["id"] for p in eng}:
                        refuse("audience-visibility-mismatch", "targets", "the board can be read by accounts that cannot read the repository")
            out[t["id"]] = ResolvedTarget(ident, bool(proj.get("public")), readers)
        else:
            repo = reader.repository(t["repository_id"])
            if repo is None:
                refuse("target-identity-mismatch", "targets", "the repository cannot be found by its numeric id")
            ident = {"id": t["id"], "host": repo.get("host", "github.com"), "repository_id": repo["id"], "repository": repo["full_name"]}
            out[t["id"]] = ResolvedTarget(ident, repo.get("visibility") == "public" or repo.get("private") is False, None)
        if out[t["id"]].identity.get("host") != t["host"] or out[t["id"]].identity.get("repository_id") != t["repository_id"]:
            refuse("target-identity-mismatch", "targets", "the destination has another host or numeric id")
        if audience == "repo-readers" and out[t["id"]].public:
            refuse("audience-visibility-mismatch", "targets", "a destination is public but the audience is repository readers")
    return out


def _state_refusal(replay, request_id):
    st = replay.requests.get(request_id)
    if st is None or st.state == "prepared":
        refuse("not-approved", "state", "the request was never activated")
    if st.state == "superseded":
        refuse("superseded", "state", "the request was superseded")
    if st.state == "withdrawn":
        refuse("withdrawn", "state", "the request was withdrawn")
    return st


def authorize_content(record, replay, policy, targets, now=None, receipts=None):
    """A short-lived VerifiedContext for release-class writes, or a fixed refusal (D2, D15).

    record is an ApprovalRecord (verify_request or verify_local_request). replay is the ReplayResult of
    the authenticated events. policy is the current Enrollment, or the LocalPolicy of a project that is
    not enrolled. targets is verify_targets output: the destinations as the API describes them now.
    receipts maps a repository path such as docs/release/<id>.receipt.json to the digest of the receipt
    that export is about to write (the active receipt and published predecessors).

    The request must be active in the replay, unexpired at now, captured under the current policy
    digest, approved by an account that is still authorized, and its target identities must equal the
    resolved ones. A local approval is refused for an enrolled project (unauthenticated-release)."""
    when = clock() if now is None else now
    request = record.request
    if getattr(policy, "enrolled", False) and record.approval.type != "github-review":
        refuse("unauthenticated-release", "approval", "a local owner approval is not accepted for an enrolled project")
    if not getattr(policy, "enrolled", False) and record.approval.type != "local-owner":
        refuse("unauthenticated-release", "approval", "this project has no enrollment to verify a staging approval against")
    state = _state_refusal(replay, record.request_id)
    if replay.active != record.request_id:
        refuse("mixed-release", "state", "another request is the active one")
    template = request["receipt_template"]
    if template["expires_at"] and to_epoch(template["expires_at"], "expires_at") <= when:
        refuse("expired", "state", "the approval has expired")
    if request["policy_sha256"] != policy.policy_sha256 or request["enrollment_id"] != policy.enrollment_id:
        refuse("policy-revision-mismatch", "request", "was approved under another policy")
    if getattr(policy, "enrolled", False):
        if record.review is None or record.review.reviewer_id not in policy.approver_ids:
            refuse("approver-not-authorized", "review", "the approving account is no longer an authorized approver")
    resolved = {}
    if targets is None:
        # An offline context (the "yes" path writing files into the working tree) checks no destination
        # identity, so it names no target and the gate refuses it for every GitHub write.
        if getattr(policy, "enrolled", False):
            refuse("target-identity-mismatch", "targets", "an enrolled project needs its destinations resolved through the API")
        template = dict(template, targets=[])
    for t in template["targets"]:
        got = (targets or {}).get(t["id"])
        if got is None or not _same_identity(t, got.identity):
            refuse("target-identity-mismatch", "targets", "a target does not match the approved identity")
        if template["audience"] == "repo-readers" and got.public:
            refuse("audience-visibility-mismatch", "targets", "a destination is public but the audience is repository readers")
        resolved[t["id"]] = t
    entries = {e["path"]: (e["sha256"], e["mode"]) for e in record.entries}
    return VerifiedContext(
        _mint=_MINT, kind="content", request_id=record.request_id, release_id=record.release_id, event_id=state.event_id,
        mechanism=record.approval.type, authenticated=record.approval.authenticated, policy_sha256=policy.policy_sha256,
        enrollment_id=policy.enrollment_id, audience=template["audience"], destinations=tuple(template["destinations"]),
        target_ids=tuple(sorted(resolved)), targets=tuple(sorted(resolved.items())), entries=entries,
        receipt_digests=dict(receipts or {}), expires_at=template["expires_at"],
        issued_at=when if now is not None else clock())


def authorize_state_receipt(record, replay, policy, receipts, now=None):
    """A VerifiedStateContext for state-only writes (D2, D13), or a fixed refusal.

    record is the ApprovalRecord of a historically valid request. replay shows that request in a
    terminal state (superseded or withdrawn) through an authenticated event. policy is current: the
    transition must have been authorized by an account that current policy still lists. receipts maps
    each already-published receipt path (docs/release/<request id>.receipt.json) to the digest of the
    exact terminal projection. The context permits only those paths. It does not require the request
    to be active, and it carries no content or payload permission."""
    when = clock() if now is None else now
    state = replay.requests.get(record.request_id)
    if state is None or state.state not in RS.TERMINAL_STATES:
        refuse("not-approved", "state", "the request has no authenticated terminal transition")
    if getattr(policy, "enrolled", False):
        if record.approval.type != "github-review":
            refuse("unauthenticated-release", "approval", "a local owner approval is not accepted for an enrolled project")
        if record.request["enrollment_id"] != policy.enrollment_id:
            refuse("policy-pointer-mismatch", "request", "names another enrollment")
    paths = {}
    for path, digest in (receipts or {}).items():
        if not re.fullmatch(r"docs/release/[0-9a-f]{64}\.receipt\.json", path):
            refuse("state-only-content-write", "receipts", "a state-only write may name only receipt paths")
        paths[path] = digest
    own = f"docs/release/{record.request_id}.receipt.json"
    if own not in paths:
        refuse("state-only-content-write", "receipts", "does not include the receipt of the affected request")
    return VerifiedContext(
        _mint=_MINT, kind="state", request_id=record.request_id, release_id=record.release_id, event_id=state.event_id,
        mechanism=record.approval.type, authenticated=record.approval.authenticated, policy_sha256=policy.policy_sha256,
        enrollment_id=policy.enrollment_id, audience=record.request["receipt_template"]["audience"], destinations=(),
        target_ids=(), targets=(), entries={}, receipt_digests=paths, expires_at=None,
        issued_at=when if now is not None else clock())


# ---------------------------------------------------------------------------
# Prerequisites (D14, WP7 item 7)
# ---------------------------------------------------------------------------

def _attested(entry, component, subject, now, exact=False):
    """True when a scoped administrator attestation for this component is current (D9): the component
    and subject equal (the subject may carry no extra facts when exact), the author an administrator
    id, the dates valid and unexpired."""
    admins = {a["id"] for a in entry["administrators"]}
    for att in entry["attestations"]:
        if not isinstance(att, dict) or att.get("component") != component or att.get("by_id") not in admins:
            continue
        try:
            at, expires = to_epoch(att.get("at"), "at"), to_epoch(att.get("expires_at"), "expires_at")
        except SchemaError:
            continue
        subj = att.get("subject")
        if not isinstance(subj, dict):
            continue
        if exact and subj != subject:
            continue
        if any(subj.get(k) != v for k, v in subject.items()):
            continue
        if at <= now < expires:
            return True
    return False


def _call(fn, *args):
    """Run an evidence call. Returns (value, None), or (None, reason) when the fact is unavailable."""
    try:
        return fn(*args), None
    except EvidenceUnavailable as e:
        return None, e.detail or "unavailable"


VERIFIER_SECRET_PREFIX = "CARRYDOWN_APP"
VERIFIER_WORKFLOW = ".github/workflows/carrydown-release-verify.yml"


def _verifier_isolation(reader, enrollment, now):
    """(status, evidence) for the part of the verifier-code component that is about credentials (WP7 item 1):
    the engineering and staging repositories hold no verifier workflow and no secret of the verifier App.
    A workflow file is read through the contents API. Secret names need administrative read, so when they
    cannot be listed only a current scoped verifier-isolation attestation satisfies the component."""
    entry = enrollment.entry
    unreadable, problems = [], []
    for label, repo_id in (("engineering", enrollment.repository_id), ("staging", _staging(enrollment))):
        repo, why = _call(reader.repository, repo_id)
        if why is not None or repo is None:
            unreadable.append(f"the {label} repository")
            continue
        wf, why = _call(reader.file_at, repo_id, repo["default_branch"], VERIFIER_WORKFLOW)
        if why is not None:
            unreadable.append(f"the {label} workflows")
        elif wf is not None:
            problems.append(f"the {label} repository holds a verifier workflow")
        names, why = _call(reader.secret_names, repo_id)
        if why is not None:
            unreadable.append(f"the {label} secret names")
        elif any(str(n).upper().startswith(VERIFIER_SECRET_PREFIX) for n in names or []):
            problems.append(f"the {label} repository holds a secret of the verifier App")
    if problems:
        return MISSING, "; ".join(problems)
    if unreadable:
        subject = {"repository_id": enrollment.repository_id, "staging_repository_id": _staging(enrollment)}
        if _attested(entry, "verifier-isolation", subject, now):
            return VERIFIED, "a separate verifier commit exists, and a current verifier-isolation attestation covers " + ", ".join(sorted(set(unreadable)))
        return NOT_VERIFIABLE, "cannot inspect " + ", ".join(sorted(set(unreadable))) + " and no current verifier-isolation attestation matches"
    return VERIFIED, "a verifier commit separate from the policy commit exists, and neither repository holds the verifier workflow or its secrets"


def _check_staging_readers(reader, enrollment, now):
    entry = enrollment.entry
    repo_id = _staging(enrollment)
    allowed_users = set(entry["staging_readers"]["user_ids"]) | {a["id"] for a in entry["approvers"]} | {a["id"] for a in entry["administrators"]}
    allowed_services = set(entry["staging_readers"].get("approved_service_ids") or [])
    subject = {"repository_id": repo_id, "reader_ids": sorted(entry["staging_readers"]["user_ids"]),
               "service_ids": sorted(allowed_services)}
    problems, unreadable = [], []
    people, why = _call(reader.collaborators, repo_id)
    if people is None:
        unreadable.append("collaborators")
    else:
        extra = sorted({p["id"] for p in people} - allowed_users)
        if extra:
            problems.append(f"{len(extra)} account(s) can read the staging repository that the enrollment does not list")
    teams, why = _call(reader.teams, repo_id)
    if teams is None:
        unreadable.append("teams")
    elif teams:
        problems.append(f"{len(teams)} team(s) can read the staging repository")
    apps, why = _call(reader.installations, repo_id)
    if apps is None:
        unreadable.append("installed Apps")
    else:
        extra = sorted({str(a.get("slug", a.get("id"))) for a in apps} - {str(s) for s in allowed_services})
        if extra:
            problems.append(f"{len(extra)} installed App(s) are not on the approved service list")
    keys, why = _call(reader.deploy_keys, repo_id)
    if keys is None:
        unreadable.append("deploy keys")
    elif keys:
        problems.append(f"{len(keys)} deploy key(s) exist")
    if problems:
        return Component("staging-readers", MISSING, "; ".join(problems), COMPONENT_CODES["staging-readers"])
    if unreadable:
        if _attested(entry, "staging-readers", subject, now, exact=True):
            return Component("staging-readers", VERIFIED, "a current administrator attestation covers " + ", ".join(unreadable),
                             COMPONENT_CODES["staging-readers"])
        return Component("staging-readers", NOT_VERIFIABLE,
                         "cannot inspect " + ", ".join(unreadable) + " and no current staging-readers attestation matches",
                         COMPONENT_CODES["staging-readers"])
    return Component("staging-readers", VERIFIED, "effective readers, teams, Apps and deploy keys match the enrollment",
                     COMPONENT_CODES["staging-readers"])


def _ruleset_rules(rulesets, default_branch_hint=True):
    """Merge the active branch rulesets that target the default branch into one summary."""
    summary = {"reviews": 0, "stale": False, "last_push": None, "checks": [], "strict": False, "no_force": False,
               "no_delete": False, "bypass": False, "merge_methods": None}
    for rs in rulesets:
        if rs.get("enforcement") != "active" or rs.get("target") != "branch":
            continue
        include = ((rs.get("conditions") or {}).get("ref_name") or {}).get("include") or []
        if not any(x in ("~DEFAULT_BRANCH", "~ALL") for x in include):
            continue
        if rs.get("bypass_actors"):
            summary["bypass"] = True
        for rule in rs.get("rules") or []:
            p = rule.get("parameters") or {}
            t = rule.get("type")
            if t == "pull_request":
                summary["reviews"] = max(summary["reviews"], p.get("required_approving_review_count", 0))
                summary["stale"] = summary["stale"] or bool(p.get("dismiss_stale_reviews_on_push"))
                summary["last_push"] = p.get("require_last_push_approval")
                if p.get("allowed_merge_methods") is not None:
                    summary["merge_methods"] = list(p["allowed_merge_methods"])
            elif t == "required_status_checks":
                summary["strict"] = summary["strict"] or bool(p.get("strict_required_status_checks_policy"))
                summary["checks"] += [(c.get("context"), c.get("integration_id")) for c in p.get("required_status_checks") or []]
            elif t == "non_fast_forward":
                summary["no_force"] = True
            elif t == "deletion":
                summary["no_delete"] = True
    return summary


def _check_from_app(summary, name, app_id):
    """None when the rules require check name from the verifier App with this integration id, else a plain
    description. A check name alone is not enough: any other App could report a check with the same name."""
    found = [i for c, i in summary["checks"] if c == name]
    if not found:
        return f"the check {name} is not required"
    if app_id is not None and app_id not in found:
        return f"the check {name} is not required from the verifier App (integration id {app_id})"
    return None


def staging_ruleset_problem(rulesets, app_id=None):
    """None when the staging rulesets encode D10 item 3, else a plain description of what is wrong.
    A last-pusher approval requirement is reported as such: the sole owner cannot satisfy it. app_id is
    the numeric id of the verifier App (the enrollment's verifier_app_id). When it is given the required
    check must come from that integration, not merely carry the right name."""
    s = _ruleset_rules(rulesets)
    if s["reviews"] < 1:
        return "the default branch does not require an approving review"
    if not s["stale"]:
        return "approvals are not dismissed when new commits are pushed"
    if s["last_push"] is not False:
        return "require_last_push_approval is on or unset. The sole owner pushed the branch, so a second human would be needed. Turn it off"
    why = _check_from_app(s, STAGING_CHECK, app_id)
    if why:
        return why
    if not s["strict"]:
        return "branches are not required to be up to date before merging"
    if not (s["no_force"] and s["no_delete"]):
        return "force pushes or deletions of the default branch are allowed"
    if s["bypass"]:
        return "a bypass actor can skip the review rules"
    if s["merge_methods"] is not None and s["merge_methods"] != ["merge"]:
        return "merge methods other than a merge commit are allowed"
    return None


def engineering_ruleset_problem(rulesets, app_id=None):
    """None when the engineering default branch requires the release check from the verifier App, with no
    bypass, no force push and no deletion (WP7 item 3), else a plain description of what is wrong."""
    s = _ruleset_rules(rulesets)
    why = _check_from_app(s, ENGINEERING_CHECK, app_id)
    if why:
        return why
    if s["bypass"]:
        return "a bypass actor can skip the rules of the default branch"
    if not (s["no_force"] and s["no_delete"]):
        return "force pushes or deletions of the default branch are allowed"
    return None


def verify_prerequisites(reader, enrollment, now=None, workspace_access=None):
    """Component-by-component results from current evidence (D14, WP7 item 7). Returns a list of
    Component(name, status, evidence, code) for every component of EXPORT_COMPONENTS. status is
    verified, not verifiable or missing. An unreadable live fact is never turned into success by a
    generic attestation: only an attestation whose subject matches the exact component and facts
    counts, and only for the components that are configuration or access facts.

    workspace_access is None (not checked), True or False, from the local doctor. The caller refuses a
    private upload unless every component of UPLOAD_COMPONENTS is verified, and an export or a
    publication unless every component of EXPORT_COMPONENTS is verified (require)."""
    when = clock() if now is None else now
    entry = enrollment.entry
    staging_id = _staging(enrollment)
    out = []

    def add(name, status, evidence):
        out.append(Component(name, status, evidence, COMPONENT_CODES[name]))

    add("enrollment", VERIFIED, "resolved by the repository's numeric id; stable id, policy digest and protected revision valid")
    repo, why = _call(reader.repository, staging_id)
    if why is not None:
        add("staging-identity", NOT_VERIFIABLE, "the staging repository cannot be read")
    elif repo is None or repo.get("id") != staging_id:
        add("staging-identity", MISSING, "no repository has the enrolled numeric id")
    elif repo.get("private") is not True or repo.get("visibility") not in (None, "private"):
        add("staging-identity", MISSING, "the staging repository is not private")
    elif repo.get("full_name", "").casefold() != str(entry["staging_repository"]).casefold():
        add("staging-identity", MISSING, "the enrolled numeric id belongs to another repository name")
    else:
        add("staging-identity", VERIFIED, "numeric id, private visibility and name match the enrollment")
    out.append(_check_staging_readers(reader, enrollment, when))
    wf, why = _call(reader.file_at, staging_id, repo["default_branch"] if repo else "HEAD", WORKFLOW_PATH)
    settings, why2 = _call(reader.actions_settings, staging_id)
    if why is not None:
        add("staging-workflow", NOT_VERIFIABLE, "the workflow file cannot be read")
    elif wf is None:
        add("staging-workflow", MISSING, "the request-opening workflow is not installed on the default branch")
    elif sha256_bytes(wf) != entry["staging_workflow_sha256"]:
        add("staging-workflow", MISSING, "the installed workflow does not match the enrolled digest")
    elif why2 is not None:
        add("staging-workflow", NOT_VERIFIABLE, "the Actions settings cannot be read")
    elif not (settings or {}).get("can_create_pull_requests"):
        add("staging-workflow", MISSING, "Actions may not create pull requests in the staging repository")
    else:
        add("staging-workflow", VERIFIED, "the installed workflow matches the enrolled digest and Actions may open pull requests")
    rulesets, why = _call(reader.rulesets, staging_id)
    if why is not None:
        add("staging-ruleset", NOT_VERIFIABLE, "the staging rulesets cannot be read")
    else:
        problem = staging_ruleset_problem(rulesets, enrollment.verifier_app_id)
        add("staging-ruleset", MISSING if problem else VERIFIED, problem or "the ruleset encodes the review, check and up-to-date rules")
    tooling_id = enrollment.tooling_repository_id
    sha = entry["verifier_sha"]
    exists, why = _call(reader.commit_exists, tooling_id, sha)
    if why is not None:
        add("verifier-code", NOT_VERIFIABLE, "the pinned verifier commit cannot be looked up")
    elif not exists or sha == enrollment.policy_commit_sha:
        add("verifier-code", MISSING, "the pinned verifier commit does not exist or is the policy commit")
    else:
        add("verifier-code", *_verifier_isolation(reader, enrollment, when))
    eng_rulesets, why = _call(reader.rulesets, enrollment.repository_id)
    cover = {"repository_id": enrollment.repository_id, "integration_id": enrollment.verifier_app_id}
    if why is None:
        problem = engineering_ruleset_problem(eng_rulesets, enrollment.verifier_app_id)
        add("engineering-ruleset", MISSING if problem else VERIFIED,
            problem or f"the default branch requires {ENGINEERING_CHECK} from the verifier App, with no bypass, force push or deletion")
    elif _attested(entry, "ruleset-coverage", cover, when):
        add("engineering-ruleset", VERIFIED, "a current ruleset-coverage attestation covers the engineering repository")
    else:
        add("engineering-ruleset", NOT_VERIFIABLE, "the engineering rulesets cannot be read and no ruleset-coverage attestation is current")
    missing_ids = []
    for who in list(entry["approvers"]) + list(entry["administrators"]):
        u, why = _call(reader.user, who["id"])
        if why is not None:
            add("approvers", NOT_VERIFIABLE, "account ids cannot be looked up")
            break
        if u is None or (who.get("login") and u.get("login", "").casefold() != str(who["login"]).casefold()):
            missing_ids.append(who["id"])
    else:
        add("approvers", MISSING if missing_ids else VERIFIED,
            f"{len(missing_ids)} approver or administrator id(s) do not resolve to the listed login" if missing_ids
            else "approver and administrator ids resolve")
    health, why = _call(reader.scan_health, tooling_id)
    max_age = entry.get("check_health_max_age_seconds", 900)
    if why is not None:
        add("scan-health", NOT_VERIFIABLE, "the verifier's scan health cannot be read")
    elif not health or not health.get("complete") or not health.get("completed_at"):
        add("scan-health", MISSING, "no complete verifier scan is recorded")
    elif when - to_epoch(health["completed_at"], "completed_at") > max_age or \
            (health.get("oldest_outstanding_age_seconds") or 0) > max_age:
        add("scan-health", MISSING, "the last complete scan or the oldest outstanding check is older than the health limit")
    elif health.get("policy_commit_sha") not in (None, enrollment.policy_commit_sha):
        add("scan-health", MISSING, "the last complete scan captured an earlier policy revision than the current one")
    else:
        add("scan-health", VERIFIED, "the last complete scan is within the health limit. A health check cannot expire an old GitHub success")
    if _attested(entry, "runtime-isolation", {"repository_id": enrollment.repository_id}, when):
        add("runtime-isolation", VERIFIED, "a current administrator attestation covers the agent environment")
    else:
        add("runtime-isolation", MISSING, "no current runtime-isolation attestation")
    if workspace_access is None:
        add("workspace-access", NOT_VERIFIABLE, "not checked")
    else:
        add("workspace-access", VERIFIED if workspace_access else MISSING,
            "the workspace is owner only" if workspace_access else "the workspace is not owner only")
    return out


def verify_destinations(reader, enrollment, audience="repo-readers"):
    """The intended destinations of the enrollment against the API now (WP7 item 7): each allowed target
    resolves by its numeric identity and none is broader than the audience. A Component named destinations.
    The doctor shows it. An export or a publication checks the exact targets of its own request instead."""
    wanted = [dict(id=name, **row) for name, row in sorted(enrollment.entry["allowed_targets"].items())]
    try:
        verify_targets(reader, enrollment, wanted, audience)
    except EvidenceUnavailable:
        return Component("destinations", NOT_VERIFIABLE, "a destination cannot be read", COMPONENT_CODES["destinations"])
    except SchemaError as e:
        status = NOT_VERIFIABLE if e.code == "destination-access-not-verified" else MISSING
        return Component("destinations", status, f"{e.code}: {e.detail or e.field}", COMPONENT_CODES["destinations"])
    return Component("destinations", VERIFIED, "each destination matches its numeric identity and no destination is broader than the audience",
                     COMPONENT_CODES["destinations"])


# The administrator attestation that can stand in for a component whose live fact cannot be read with the
# caller's credential (D9). Absent names, such as enrollment and scan-health, can never be attested.
ATTESTATION_FOR = {"staging-readers": "staging-readers", "engineering-ruleset": "ruleset-coverage", "runtime-isolation": "runtime-isolation",
                   "verifier-code": "verifier-isolation", "destinations": "destination-readers"}


def require(components, names):
    """Raise a fixed refusal for the first of names (in order) whose component is not verified."""
    by = {c.name: c for c in components}
    for name in names:
        c = by.get(name)
        if c is None or c.status != VERIFIED:
            refuse(COMPONENT_CODES[name], name, "is " + (c.status if c else MISSING))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Verification of releases as pure logic over an evidence reader (enrollment, approval, event history, "
                    "contexts, prerequisites). A library: import it, do not run it. Standard library only; it reads no "
                    "network, no token and no environment.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
