#!/usr/bin/env python3
"""The verifier's polling loop (D11): reevaluate every open pull request, post one check each. Standard
library only. It takes an EvidenceReader to read with and a check publisher to post with, so the same
code runs against GitHub in the tooling repository's Actions environment and against an in-memory
model in the tests.

The loop, for each enrolled repository of one captured policy
  1. List every open pull request targeting the engineering default branch, and every open pull request
     of the staging repository. Every listing follows all pages. A listing that cannot be read completely
     makes the scan incomplete. It is never read as "nothing to check".
  2. For each pull request, move the verifier's own check to in_progress, even when the head already has
     a success or a failure. No result is cached by head commit.
  3. Evaluate it. Engineering pull requests go to release_engineering.verify_engineering. Staging pull
     requests go to release_verify.verify_candidate, plus the staging access prerequisites.
  4. Before posting, read the head, the base, the policy revision, the staging tip and every approving
     review the verdict leaned on again, and recheck expiry against the clock. If anything changed,
     discard the verdict and evaluate once more. If it keeps changing, or the API fails, the check ends
     as a failure with a fixed code. An earlier success is never kept as a fallback.
  5. Post only while this run's check is still the newest of its name on the head, so an older run
     cannot overwrite a newer decision.

The public text of a check holds identifiers and fixed reason codes, never file content. The private
input record of each evaluation (repository id, pull request number, head and base commits, policy
commit and digest, verifier commit, request ids, evidence revisions, staging tip and the UTC time) is
returned for the verifier to keep. A scan that finished with every listing complete and every check
posted is healthy; otherwise it is not, and the workflow run fails.

Limits, stated plainly. A scheduled run can be delayed or dropped. A check that succeeded stays
mergeable during an outage. State can change between a poll and a merge. This reference deployment
promises verification at the observed revisions, not continuous authorization.

This module is imported by the verifier. Run with --help to see this text.
"""
import argparse
import re
import sys
from typing import NamedTuple

import release_engineering as RE
import release_schema as RS
import release_verify as V
from release_schema import SchemaError

ENGINEERING_CHECK = V.ENGINEERING_CHECK
STAGING_CHECK = V.STAGING_CHECK
MAX_ATTEMPTS = 2        # one evaluation and one retry (D11 step 4)


class Evaluation(NamedTuple):
    conclusion: str        # success or failure
    code: str              # "" on success, else a fixed reason code
    title: str
    summary: str
    record: dict           # the private input record
    kind: str


class ScanReport:
    def __init__(self, policy_commit_sha, started):
        self.policy_commit_sha = policy_commit_sha
        self.started = started
        self.finished = None
        self.checks = []          # public view: repository id, kind, number, head, conclusion, code
        self.records = []         # the private input records
        self.errors = []          # operational problems: a listing or a post that did not complete
        self.superseded = 0       # results discarded because a newer check exists
        self.outstanding = 0      # checks started and never finished

    @property
    def complete(self):
        return not self.errors and self.outstanding == 0

    def health_record(self):
        """The private scan-health record (WP7 item 2): the captured policy revision, the completion time
        and the outstanding checks. A partially enumerated scan is not healthy."""
        return {"complete": self.complete, "completed_at": self.finished, "policy_commit_sha": self.policy_commit_sha,
                "checks": len(self.checks), "outstanding": self.outstanding, "errors": len(self.errors),
                "oldest_outstanding_age_seconds": 0}


# ---------------------------------------------------------------------------
# Observing the inputs
# ---------------------------------------------------------------------------

_FULL_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class ImmutableReads:
    """Passes every read through and remembers, for the length of one scan, the answers that cannot change:
    a tree, a blob or a file at a full commit id, the history up to a full commit id, whether one full commit
    is an ancestor of another, and that a commit exists. Content addressed objects are the only thing the
    specification lets a verifier cache. Pull requests, reviews, branch heads and listings are always read
    again. A new scan starts with an empty memory."""

    def __init__(self, reader):
        object.__setattr__(self, "_reader", reader)
        object.__setattr__(self, "_memo", {})

    def __getattr__(self, name):
        return getattr(self._reader, name)

    def _once(self, key, call, keep=True):
        if key in self._memo:
            return self._memo[key]
        value = call()
        if keep and value is not None:
            self._memo[key] = value
        return value

    def tree(self, repo, sha):
        return self._once(("tree", repo, sha), lambda: self._reader.tree(repo, sha), _FULL_SHA.match(sha) is not None)

    def blob(self, repo, sha):
        return self._once(("blob", repo, sha), lambda: self._reader.blob(repo, sha))

    def file_at(self, repo, ref, path):
        return self._once(("file", repo, ref, path), lambda: self._reader.file_at(repo, ref, path), _FULL_SHA.match(ref) is not None)

    def first_parent_history(self, repo, ref):
        return self._once(("history", repo, ref), lambda: self._reader.first_parent_history(repo, ref), _FULL_SHA.match(ref) is not None)

    def is_ancestor(self, repo, ancestor, descendant):
        both = _FULL_SHA.match(ancestor) is not None and _FULL_SHA.match(descendant) is not None
        return self._once(("ancestor", repo, ancestor, descendant), lambda: self._reader.is_ancestor(repo, ancestor, descendant), both)

    def commit_exists(self, repo, sha):
        found = self._once(("exists", repo, sha), lambda: self._reader.commit_exists(repo, sha) or None)
        return bool(found)

class RecordingReader:
    """Passes every read through and remembers the reviews it returned, by pull request, so the same
    reviews can be read again after the verdict and compared (D11 step 4)."""

    def __init__(self, reader):
        object.__setattr__(self, "_reader", reader)
        object.__setattr__(self, "reviews_seen", {})

    def __getattr__(self, name):
        return getattr(self._reader, name)

    def reviews(self, repo, number):
        rows = self._reader.reviews(repo, number)
        self.reviews_seen[(repo, number)] = _reviews_digest(rows)
        return rows


def _reviews_digest(rows):
    keyed = sorted((str(r.get("id")), str(r.get("state")), str(r.get("commit_id")), str((r.get("user") or {}).get("id"))) for r in rows)
    return RS.sha256_bytes(RS.canonical_json([list(k) for k in keyed]))


def _observe(reader, enrollment, kind, number):
    """The inputs a verdict depends on, as they are right now."""
    repo_id = enrollment.repository_id if kind == "engineering" else enrollment.entry["staging_repository_id"]
    pr = reader.pull_request(repo_id, number)
    if pr is None:
        return {"pull_request": None}
    staging = reader.repository(enrollment.entry["staging_repository_id"])
    tooling = reader.repository(enrollment.tooling_repository_id)
    return {"pull_request": pr["state"], "head": pr["head"]["sha"], "base_tip": reader.branch_head(repo_id, pr["base"]["ref"]),
            "policy_tip": reader.branch_head(enrollment.tooling_repository_id, tooling["default_branch"]),
            "staging_tip": reader.branch_head(staging["id"], staging["default_branch"])}


def _fixed(kind, code):
    return Evaluation("failure", code, f"carrydown: {code}", f"The verifier could not confirm this change. Reason code: {code}.", {}, kind)


def _summary(report, head, extra=()):
    lines = [f"Verified at head {head[:12]}." if report.ok else f"Not verified at head {head[:12]}."]
    if report.ok:
        lines.append("No governed changes." if report.kind == "no-governed-changes" else f"Kind: {report.kind}.")
    for f in report.findings[:30]:
        lines.append(f"- {f.code}: {f.where}" if f.where else f"- {f.code}")
    if len(report.findings) > 30:
        lines.append(f"- {len(report.findings) - 30} more finding(s)")
    lines.extend(extra)
    lines.append("This check verifies the observed revisions. It does not guarantee continuous authorization.")
    return "\n".join(lines)


def _evaluate_engineering(reader, enrollment, number, now):
    report = RE.verify_engineering(reader, enrollment, number, now=now)
    pr = reader.pull_request(enrollment.repository_id, number)
    head = pr["head"]["sha"] if pr else "0" * 40
    if report.ok:
        title = "carrydown: no governed changes" if report.kind == "no-governed-changes" else "carrydown: release verified"
        return Evaluation("success", "", title, _summary(report, head), {"request_ids": list(report.request_ids),
                          "evidence": [list(e) for e in report.evidence], "expires_at": report.expires_at}, "engineering")
    return Evaluation("failure", report.code, f"carrydown: {report.code}", _summary(report, head),
                      {"request_ids": list(report.request_ids), "evidence": [list(e) for e in report.evidence], "expires_at": None}, "engineering")


STAGING_NEEDED = ("staging-identity", "staging-readers")


def _evaluate_staging(reader, enrollment, number, now):
    pr = reader.pull_request(enrollment.entry["staging_repository_id"], number)
    head = pr["head"]["sha"] if pr else "0" * 40
    report = V.verify_candidate(reader, enrollment, number, now=now)
    extra, code = [], report.code
    if report.ok:
        by = {c.name: c for c in V.verify_prerequisites(reader, enrollment, now=now)}
        for name in STAGING_NEEDED:
            if by[name].status != V.VERIFIED:
                code = by[name].code
                extra.append(f"- {code}: {name} is {by[name].status}")
        if by["staging-workflow"].status == V.MISSING:
            code = by["staging-workflow"].code
            extra.append(f"- {code}: staging-workflow is {V.MISSING}")
    if report.ok and not code:
        return Evaluation("success", "", "carrydown: candidate verified",
                          "\n".join([f"Verified at head {head[:12]}.", f"Kind: {report.kind}.", "An authorized review of the final revision is in effect.",
                                     "This check verifies the observed revisions. It does not guarantee continuous authorization."]),
                          {"request_ids": [report.request_id] if report.request_id else [], "event_id": report.event_id, "evidence": [], "expires_at": None}, "staging")
    waiting = not report.reviewed and report.code == "approval-not-found"
    text = ["Not verified at head " + head[:12] + ".", f"- {code}" + (": waiting for an authorized review of the final revision" if waiting else "")] + extra
    text.append("This check verifies the observed revisions. It does not guarantee continuous authorization.")
    return Evaluation("failure", code, f"carrydown: {code}", "\n".join(text),
                      {"request_ids": [report.request_id] if report.request_id else [], "event_id": report.event_id, "evidence": [], "expires_at": None}, "staging")


def evaluate(reader, enrollment, kind, number, expected_head=None, verifier_sha=None, clock=None):
    """One Evaluation for one pull request, with the recheck of D11 step 4. Never raises for a transport
    failure: that is a failure with evidence-unavailable. kind is engineering or staging."""
    clock = clock or V.clock
    repo_id = enrollment.repository_id if kind == "engineering" else enrollment.entry["staging_repository_id"]
    result = None
    for _attempt in range(MAX_ATTEMPTS):
        recording = RecordingReader(reader)
        try:
            before = _observe(recording, enrollment, kind, number)
            if before.get("pull_request") != "open":
                result = _fixed(kind, "inputs-changed-during-verification")
                break
            if expected_head is not None and before["head"] != expected_head:
                result = _fixed(kind, "inputs-changed-during-verification")
                break
            when = clock()
            result = (_evaluate_engineering if kind == "engineering" else _evaluate_staging)(recording, enrollment, number, when)
            after = _observe(reader, enrollment, kind, number)
            reviews_now = {key: _reviews_digest(reader.reviews(*key)) for key in recording.reviews_seen}
        except V.EvidenceUnavailable:
            return _fixed(kind, "evidence-unavailable")
        except SchemaError as e:
            return _fixed(kind, e.code)
        if before == after and reviews_now == recording.reviews_seen:
            expires = result.record.get("expires_at")
            if result.conclusion == "success" and expires and V.to_epoch(expires, "expires_at") <= clock():
                result = _fixed(kind, "expired")
            result.record.update(_input_record(enrollment, kind, repo_id, number, before, verifier_sha, result, clock))
            return result
        result = None
    return _fixed(kind, "inputs-changed-during-verification") if result is None else result


def _input_record(enrollment, kind, repo_id, number, observed, verifier_sha, result, clock):
    return {"repository_id": repo_id, "kind": kind, "pull_request": number, "head_sha": observed.get("head"),
            "base_tip": observed.get("base_tip"), "policy_commit_sha": enrollment.policy_commit_sha,
            "policy_sha256": enrollment.policy_sha256, "verifier_sha": verifier_sha or enrollment.entry["verifier_sha"],
            "staging_tip": observed.get("staging_tip"), "conclusion": result.conclusion, "code": result.code,
            "evaluated_at": V.utc_text(clock())}


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------

def _post(report, publisher, reader, enrollment, kind, repo_id, number, head, name, verifier_sha, clock):
    try:
        check_id = publisher.start(repo_id, head, name)
    except V.EvidenceUnavailable:
        report.errors.append(f"{kind} pull request {number}: the check could not be started")
        return
    report.outstanding += 1
    result = evaluate(reader, enrollment, kind, number, expected_head=head, verifier_sha=verifier_sha, clock=clock)
    try:
        posted = publisher.finish(repo_id, head, name, check_id, result.conclusion, result.title, result.summary)
    except V.EvidenceUnavailable:
        report.errors.append(f"{kind} pull request {number}: the result could not be posted")
        return
    report.outstanding -= 1
    if not posted:
        report.superseded += 1
        return
    report.checks.append({"repository_id": repo_id, "kind": kind, "pull_request": number, "head_sha": head,
                          "conclusion": result.conclusion, "code": result.code})
    report.records.append(dict(result.record, check_run=check_id))


def scan(reader, publisher, enrollments, code_sha=None, clock=None):
    """One complete pass over the enrolled repositories of a captured policy. enrollments are the
    release_verify.Enrollment records of one policy commit (capture_enrollments). A repository whose
    enrollment pins another verifier commit than code_sha is left to the run of that commit. Returns a
    ScanReport; its complete property is the health of the scan."""
    clock = clock or V.clock
    reader = ImmutableReads(reader)
    report = ScanReport(enrollments[0].policy_commit_sha if enrollments else None, V.utc_text(clock()))
    for e in enrollments:
        if code_sha is not None and e.entry["verifier_sha"] != code_sha:
            continue
        jobs = (("engineering", e.repository_id, ENGINEERING_CHECK), ("staging", e.entry["staging_repository_id"], STAGING_CHECK))
        for kind, repo_id, name in jobs:
            try:
                repo = reader.repository(repo_id)
                if repo is None:
                    raise V.EvidenceUnavailable("the repository cannot be found by its numeric id")
                prs = reader.pull_requests(repo_id, repo["default_branch"], "open")
            except V.EvidenceUnavailable:
                report.errors.append(f"{kind} repository {repo_id}: the open pull requests cannot be listed completely")
                continue
            for pr in prs:
                _post(report, publisher, reader, e, kind, repo_id, pr["number"], pr["head"]["sha"], name, code_sha, clock)
    report.finished = V.utc_text(clock())
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
