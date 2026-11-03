#!/usr/bin/env python3
"""The engineering side of the independent verifier: one open pull request against the enrolled
repository's default branch (WP7 item 4, D9, D11, D12). Standard library only. It reads no network,
no token and no environment: everything comes through a release_verify.EvidenceReader, so the
verifier can run it from its own pinned checkout and a test can run it over an in-memory model.

What it does with one pull request
  1. Reads the full list of changed files and the proposed tree as API data. An incomplete listing
     raises EvidenceUnavailable and is never a clean result.
  2. Sorts the changes into the policy pointer, receipt envelopes (docs/release/<request id>.receipt.json),
     governed artifacts (the enrollment's governed_paths) and everything else.
  3. Pointer: a deleted pointer fails. A changed pointer must name the same enrollment and tooling
     repository and be authored by an authorized approver. A pull request with no governed change and
     no pointer change reports "no governed changes", after the listing was complete.
  4. Receipts: each changed receipt must equal, byte for byte, release_schema.project_receipt over the
     verified request, manifest, authenticated state and approval. A receipt that claims "active" for a
     request the staging history shows as superseded or withdrawn fails with that state. A receipt is
     never required to list itself. A file under docs/release/ with any other name fails.
  5. Artifacts: every changed governed file must match, in path, bytes and mode, the manifest of the one
     active request whose receipt is in the proposed tree, and that request must be approved by an
     authorized account, unexpired and captured under the current policy digest. Removals, renames,
     links and submodules fail. An unlisted file fails even when the pull request also holds a valid receipt.
     With engineer_edits "allowed" for a path, a change that touches only "Decisions recorded" of an
     exported specification is permitted; "request-only" (the default) permits none.
  6. Content checks on the changed artifacts: the released-plan schema and project.handling of a plan,
     the bundle digest of each bundle pair, and the detectors that no exception can clear.
  7. Base drift: a governed file that reached the default branch after the pull request was opened must
     appear in some receipt of the default branch, so a direct push that bypassed review is caught.

Nothing from the pull request is imported, executed, rendered or built. A refusal names a fixed reason
code and a repository path or a request id, never a value from a file.

This module is imported by release_scan.py and the verifier. Run with --help to see this text.
"""
import argparse
import re
import sys
from typing import NamedTuple, Optional

import carrydown_lib as L
import compile_bundles as CB
import detectors as D
import release_schema as RS
import release_verify as V
from release_schema import SchemaError, sha256_bytes

POINTER_PATH = ".carrydown/release-policy.yaml"
POINTER_KEYS = ("format", "tooling_repository", "enrollment_id")
RECEIPT_DIR = "docs/release/"
RECEIPT_PATH = re.compile(r"docs/release/([0-9a-f]{64})\.receipt\.json\Z")
PLAN_NAME = "plan.yaml"
DECISIONS_HEADING = "## Decisions recorded"
MAX_FINDINGS = 40
NO_GOVERNED = "no governed changes"


class Finding(NamedTuple):
    code: str
    where: str


class EngineeringReport(NamedTuple):
    """ok is True only when every check passed. kind is no-governed-changes, content, state-only or
    refused. findings are (code, where) pairs, the first being the headline. request_ids are the
    requests whose receipts were verified. evidence lists the staging pull requests the verdict leaned on
    ((pull request number, merge commit)), for the verifier's private input record."""
    ok: bool
    code: str
    kind: str
    findings: tuple
    request_ids: tuple
    evidence: tuple
    expires_at: Optional[str]


# ---------------------------------------------------------------------------
# Governed paths
# ---------------------------------------------------------------------------

_PATTERNS = {}


def _pattern(glob):
    """A compiled regular expression for a governed path such as docs/spec/**. ** crosses folders, *
    does not. Matching ignores case so a differently cased folder on a case-insensitive disk cannot
    slip past."""
    if glob not in _PATTERNS:
        out, i = [], 0
        text = glob.casefold()
        while i < len(text):
            if text.startswith("**", i):
                out.append(".*")
                i += 2
            elif text[i] == "*":
                out.append("[^/]*")
                i += 1
            elif text[i] == "?":
                out.append("[^/]")
                i += 1
            else:
                out.append(re.escape(text[i]))
                i += 1
        _PATTERNS[glob] = re.compile("".join(out) + r"\Z")
    return _PATTERNS[glob]


def is_governed(path, patterns):
    low = path.casefold()
    return low.startswith(RECEIPT_DIR) or any(_pattern(g).match(low) for g in patterns)


def edit_policy(path, engineer_edits):
    """allowed or request-only for a governed path: the most specific listed pattern that matches (the
    longest), and request-only when none does."""
    low = path.casefold()
    hits = [(len(g), v) for g, v in (engineer_edits or {}).items() if _pattern(g).match(low)]
    return max(hits)[1] if hits else "request-only"


def decisions_only_change(approved, proposed):
    """True when the two texts of a specification differ only inside the "Decisions recorded" section.
    Both must have that heading; the section runs to the next heading of the same level."""
    try:
        a, b = bytes(approved).decode("utf-8"), bytes(proposed).decode("utf-8")
    except UnicodeDecodeError:
        return False

    def outside(text):
        lines, out, skip, seen = text.splitlines(keepends=True), [], False, False
        for line in lines:
            bare = line.rstrip("\r\n")
            if bare == DECISIONS_HEADING:
                skip, seen = True, True
                out.append(line)
                continue
            if skip and bare.startswith("## "):
                skip = False
            if not skip:
                out.append(line)
        return "".join(out), seen
    left, seen_a = outside(a)
    right, seen_b = outside(b)
    return seen_a and seen_b and left == right


# ---------------------------------------------------------------------------
# The verification
# ---------------------------------------------------------------------------

class _Run:
    """The state of one verification: findings, caches and the reads it made."""

    def __init__(self, reader, enrollment, pr, when):
        self.reader, self.enrollment, self.pr, self.when = reader, enrollment, pr, when
        self.repo_id = enrollment.repository_id
        self.findings = []
        self.records = {}          # request id -> ApprovalRecord, or the SchemaError that verifying it raised
        self.verified = {}         # request id -> True once its receipt and authorization passed
        self.nodes = {}
        self.history = None
        self.evidence = []
        self.expiries = []
        self.blobs = {}
        self.staging_trees = {}

    def fail(self, code, where=""):
        if len(self.findings) < MAX_FINDINGS:
            self.findings.append(Finding(code, where))

    # --- reads
    def blob(self, path):
        if path not in self.blobs:
            node = self.nodes.get(path)
            self.blobs[path] = bytes(self.reader.blob(self.repo_id, node["sha"])) if node else None
        return self.blobs[path]

    def get_history(self):
        if self.history is None:
            self.history = V.replay_staging(self.reader, self.enrollment)
        return self.history

    def record(self, rid):
        got = self.records.get(rid)
        if got is None:
            try:
                got = V.verify_request(rid, self.reader, self.enrollment)
            except SchemaError as e:
                got = e
            self.records[rid] = got
        if isinstance(got, SchemaError):
            raise got
        return got


def _classify(files, patterns):
    """(pointer status or None, {receipt path: status}, {artifact path: status}, [(code, path)])."""
    pointer, receipts, artifacts, refused = None, {}, {}, []
    for f in files:
        status = f["status"]
        names = [f["filename"]] + ([f["previous_filename"]] if f.get("previous_filename") else [])
        for name in names:
            if name.casefold() == POINTER_PATH:
                if status in ("removed", "renamed"):
                    refused.append(("policy-pointer-mismatch", name))
                else:
                    pointer = status
                continue
            if not is_governed(name, patterns):
                continue
            try:
                RS.check_path(name, "changed path")
            except SchemaError:
                refused.append(("unsafe-artifact-path", name))
                continue
            if name.casefold().startswith(RECEIPT_DIR):
                if not RECEIPT_PATH.match(name):
                    refused.append(("receipt-projection-mismatch", name))
                elif status in ("removed", "renamed"):
                    refused.append(("artifact-operation-unsupported", name))
                else:
                    receipts[name] = status
            elif status in ("removed", "renamed"):
                refused.append(("artifact-operation-unsupported", name))
            elif status in ("added", "modified", "changed", "copied"):
                artifacts[name] = status
            else:
                refused.append(("artifact-operation-unsupported", name))
    return pointer, receipts, artifacts, refused


def _check_pointer(run, status, base_has):
    """D9 and E5: a deleted pointer fails, a changed one must resolve to this enrollment and be authored
    by an authorized approver."""
    head_has = POINTER_PATH in run.nodes
    if base_has and not head_has:
        run.fail("policy-pointer-mismatch", POINTER_PATH)
        return
    if status is None or not head_has:
        return
    node = run.nodes[POINTER_PATH]
    if node["type"] != "blob" or node["mode"] != "100644":
        run.fail("unsafe-artifact-path", POINTER_PATH)
        return
    try:
        data = run.blob(POINTER_PATH)
        doc = L.loads(data.decode("utf-8"))
    except Exception:       # a YAML reader raises its own error type, none of whose text is repeated
        run.fail("policy-pointer-mismatch", POINTER_PATH)
        return
    e = run.enrollment
    if not isinstance(doc, dict) or set(doc) != set(POINTER_KEYS) or doc.get("format") != 1 \
            or str(doc.get("tooling_repository", "")).casefold() != e.tooling_repository.casefold() \
            or doc.get("enrollment_id") != e.enrollment_id:
        run.fail("policy-pointer-mismatch", POINTER_PATH)
        return
    author = (run.pr.get("user") or {}).get("id")
    if author not in e.approver_ids:
        run.fail("approver-not-authorized", POINTER_PATH)


def _light_targets(reader, enrollment, template):
    """The resolved targets of a receipt for authorize_content. The verifier credential cannot read
    projects, so a board target is held to the enrollment's allowed identity and nothing more; the owner's
    export and publication resolve boards with the owner's token. A repository target is resolved by id."""
    allowed = enrollment.entry["allowed_targets"]
    out = {}
    for t in template["targets"]:
        row = allowed.get(t["id"])
        if not isinstance(row, dict) or {k: v for k, v in t.items() if k != "id"} != row:
            V.refuse("destination-not-allowed", "targets", "a target is not in the enrollment's allowed targets")
        if "project_id" in t:
            out[t["id"]] = V.ResolvedTarget(dict(t), False, None)
            continue
        repo = reader.repository(t["repository_id"])
        if repo is None:
            V.refuse("target-identity-mismatch", "targets", "the repository cannot be found by its numeric id")
        ident = {"id": t["id"], "host": repo.get("host", "github.com"), "repository_id": repo["id"], "repository": repo["full_name"]}
        out[t["id"]] = V.ResolvedTarget(ident, repo.get("visibility") == "public" or repo.get("private") is False, None)
    return out


def _check_receipt(run, rid, path, data, status):
    """One receipt envelope: its approval, its state, its authorization when it claims to be active, and
    the exact projection. Returns True when it passed. data is the receipt file at the head."""
    where = f"{path}"
    try:
        proposed = RS.validate_receipt(data)
    except SchemaError:
        run.fail("receipt-projection-mismatch", where)
        return False
    if proposed["request_id"] != rid:
        run.fail("receipt-projection-mismatch", where)
        return False
    if proposed["approval"]["type"] != "github-review" or proposed["approval"]["authenticated"] is not True:
        run.fail("unauthenticated-release", where)
        return False
    try:
        history = run.get_history()
        record = run.record(rid)
        state = history.replay.requests.get(rid)
        if state is None or state.state == "prepared":
            V.refuse("not-approved", "state", "the request was never activated")
        if state.state != "active" and proposed["state"] == "active":
            V._state_refusal(history.replay, rid)
        if state.state == "active":
            if history.replay.active != rid:
                V.refuse("mixed-release", "state", "another request is the active one")
            targets = _light_targets(run.reader, run.enrollment, record.request["receipt_template"])
            V.authorize_content(record, history.replay, run.enrollment, targets, now=run.when)
            if any(e["path"].startswith("repo/") for e in record.entries):
                eng = [t for t in record.request["receipt_template"]["targets"] if t["id"] == "engineering"]
                if len(eng) != 1 or eng[0]["repository_id"] != run.repo_id:
                    V.refuse("target-identity-mismatch", "targets", "the release is not approved for this repository")
            exp = record.request["receipt_template"]["expires_at"]
            if exp:
                run.expiries.append(exp)
        else:
            if status == "added":
                V.refuse("receipt-projection-mismatch", "receipt", "a terminal receipt may only update one that was published")
            V.authorize_state_receipt(record, history.replay, run.enrollment, {path: sha256_bytes(data)}, now=run.when)
        RS.verify_receipt_bytes(data, record.request, record.manifest_bytes, state, record.approval)
    except SchemaError as e:
        run.fail(e.code, where)
        return False
    run.evidence.append((record.review.pr_number, record.review.merge_sha))
    return True


def _snapshot_file(run, record, rel):
    """The approved bytes of one repository artifact, read from the staging merge commit."""
    repo_id = run.enrollment.entry["staging_repository_id"]
    sha = record.review.merge_sha
    if sha not in run.staging_trees:
        run.staging_trees[sha] = {n["path"]: n for n in run.reader.tree(repo_id, sha)}
    node = run.staging_trees[sha].get(f"releases/{record.release_id}/snapshot/repo/{rel}")
    return bytes(run.reader.blob(repo_id, node["sha"])) if node else None


def _check_artifacts(run, artifacts):
    """Each changed governed file against the one active request whose receipt is in the proposed tree."""
    if not artifacts:
        return
    history = run.get_history()
    active = history.replay.active
    if active is None:
        # Name what the proposed receipts say: a withdrawn or superseded release is the useful answer.
        code = "governed-file-without-release"
        for rid in sorted(set(run.records) | {m.group(1) for m in (RECEIPT_PATH.match(p) for p in run.nodes) if m}):
            st = history.replay.requests.get(rid)
            if st is not None and st.state in RS.TERMINAL_STATES:
                code = st.state
                break
        for path in sorted(artifacts):
            run.fail(code, path)
        return
    rpath = f"{RECEIPT_DIR}{active}.receipt.json"
    if rpath not in run.nodes:
        for path in sorted(artifacts):
            run.fail("governed-file-without-release", path)
        return
    if active not in run.verified:
        node = run.nodes[rpath]
        if node["type"] != "blob" or node["mode"] != "100644" or not _check_receipt(run, active, rpath, run.blob(rpath), "modified"):
            run.verified[active] = False
        else:
            run.verified[active] = True
    if not run.verified[active]:
        for path in sorted(artifacts):
            run.fail("governed-file-without-release", path)
        return
    record = run.record(active)
    entries = {e["path"][len("repo/"):]: e for e in record.entries if e["path"].startswith("repo/")}
    edits = run.enrollment.engineer_edits
    for path in sorted(artifacts):
        node = run.nodes.get(path)
        if node is None or node["type"] != "blob" or node["mode"] not in RS.MODES:
            run.fail("unsafe-artifact-path", path)
            continue
        entry = entries.get(path)
        if entry is not None and node["mode"] == entry["mode"] and node.get("size", entry["bytes"]) == entry["bytes"]:
            data = run.blob(path)
            if len(data) == entry["bytes"] and sha256_bytes(data) == entry["sha256"]:
                continue
        if edit_policy(path, edits) == "allowed" and entry is not None and path.casefold().endswith(".md") \
                and node["mode"] == entry["mode"]:
            approved = _snapshot_file(run, record, path)
            if approved is not None and decisions_only_change(approved, run.blob(path)):
                continue
        run.fail("sha256-mismatch" if entry is not None else "governed-file-without-release", path)


def _check_content(run, artifacts):
    """The released plan, the bundle pairs and the detectors, for the artifacts that changed."""
    texts = {}
    for path in sorted(artifacts):
        node = run.nodes.get(path)
        if node is None or node["type"] != "blob":
            continue
        data = run.blob(path)
        low = path.casefold()
        text = None
        if low.endswith(D.TEXT_SUFFIXES):
            texts[path] = data[:D.MAX_BYTES].decode("utf-8", errors="replace").replace("\r\n", "\n")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = None
        if low.rsplit("/", 1)[-1] == PLAN_NAME:
            _check_plan(run, path, text)
        if low.startswith("docs/context/") and (low.endswith(".bundle.json") or low.endswith(".md")):
            _check_bundle(run, path)
    findings = [("credentials", D.credentials(texts)), ("private_paths", D.private_paths(texts)),
                ("prohibited_fields", D.prohibited_fields(texts))]
    for detector, hits in findings:
        for hit in hits:
            run.fail("exception-not-permitted", f"detector:{detector}:{hit[0]} at {hit[1]}")


def _check_plan(run, path, text):
    if text is None:
        run.fail("schema-view-mismatch", path)
        return
    try:
        raw = L.loads(text)
    except Exception:
        run.fail("schema-view-mismatch", path)
        return
    project = raw.get("project") if isinstance(raw, dict) else None
    handling = project.get("handling") if isinstance(project, dict) else None
    if not isinstance(handling, dict) or handling.get("state") != "migrated":
        run.fail("enrolled-project-missing-handling", path)
        return
    try:
        import copy
        plan, problems = L.plan_from_data(copy.deepcopy(raw), "released plan", None, "released")
    except Exception:
        plan, problems = None, ["unreadable"]
    if problems or plan is None:
        run.fail("schema-view-mismatch", f"{path} ({len(problems)} problem(s) in the released view)")
        return
    _check_citations(run, plan)


def _check_citations(run, plan):
    """Released citation validation (E1): every source section a work item cites resolves against the
    obligations of that item's approved bundle. No source file or rendering is needed or read."""
    for item in plan.get("items") or []:
        if L.restricted_item(item):
            continue
        tag = L.tag(plan, item["id"])
        side_path = f"docs/context/{tag.lower()}.bundle.json"
        cited = [(ref.get("source"), number) for ref in L.item_source_refs(plan, item) for number in CB.cited_sections(ref)]
        if side_path not in run.nodes:
            if cited:
                run.fail("sha256-mismatch", f"the bundle of {tag} is missing")
            continue
        try:
            side = RS.loads_strict(run.blob(side_path))
            have = {(o["source"], o["section"]) for o in side["obligations"]}
        except (SchemaError, KeyError, TypeError):
            run.fail("schema-view-mismatch", side_path)
            continue
        missing = [key for key in cited if key not in have]
        if missing:
            run.fail("schema-view-mismatch", f"{tag} cites {len(missing)} obligation(s) that its bundle does not hold")


def _check_bundle(run, path):
    low = path.casefold()
    stem = path[:-len(".bundle.json")] if low.endswith(".bundle.json") else path[:-len(".md")]
    side_path, md_path = stem + ".bundle.json", stem + ".md"
    if side_path not in run.nodes or md_path not in run.nodes:
        run.fail("sha256-mismatch", path)
        return
    try:
        side = RS.loads_strict(run.blob(side_path))
    except SchemaError:
        run.fail("schema-view-mismatch", side_path)
        return
    if not isinstance(side, dict) or side.get("bundle_format") != 1 or not isinstance(side.get("content_sha256"), str):
        run.fail("schema-view-mismatch", side_path)
        return
    if side["content_sha256"] != sha256_bytes(run.blob(md_path)):
        run.fail("sha256-mismatch", md_path)
    if str(side.get("work_item", "")).casefold() != stem.rsplit("/", 1)[-1].casefold():
        run.fail("schema-view-mismatch", side_path)


def _base_drift(run, base_tip, changed):
    """Governed files that reached the default branch after the pull request was opened must appear in a
    receipt of the default branch. A file that is in no receipt arrived without a release."""
    pr = run.pr
    if base_tip is None or base_tip == pr["base"]["sha"]:
        return
    old = {n["path"]: (n["mode"], n["sha"]) for n in run.reader.tree(run.repo_id, pr["base"]["sha"])}
    new = {n["path"]: n for n in run.reader.tree(run.repo_id, base_tip)}
    patterns = run.enrollment.governed_paths
    drift = [p for p, n in sorted(new.items())
             if n["type"] == "blob" and is_governed(p, patterns) and not p.casefold().startswith(RECEIPT_DIR)
             and old.get(p) != (n["mode"], n["sha"]) and p not in changed]
    if not drift:
        return
    covered = set()
    for p, n in new.items():
        if RECEIPT_PATH.match(p) and n["type"] == "blob":
            try:
                receipt = RS.validate_receipt(bytes(run.reader.blob(run.repo_id, n["sha"])))
            except SchemaError:
                continue
            covered.update((a["path"], a["sha256"], a["mode"]) for a in receipt["artifacts"])
    for p in drift:
        n = new[p]
        digest = sha256_bytes(bytes(run.reader.blob(run.repo_id, n["sha"])))
        if (p, digest, n["mode"]) not in covered:
            run.fail("governed-file-without-release", p)


def verify_engineering(reader, enrollment, pull_number, now=None):
    """The verdict on one open pull request of the enrolled repository (WP7 item 4). Returns an
    EngineeringReport. A transport failure or a truncated listing raises EvidenceUnavailable: the caller
    turns that into a failed check, never a clean result. Every other refusal is in the report."""
    when = V.clock() if now is None else now
    repo_id = enrollment.repository_id
    pr = reader.pull_request(repo_id, pull_number)
    if pr is None or pr.get("state") != "open" or pr.get("merged"):
        return EngineeringReport(False, "inputs-changed-during-verification", "refused",
                                 (Finding("inputs-changed-during-verification", f"pull request {pull_number}"),), (), (), None)
    repo = reader.repository(repo_id)
    if repo is None or repo["id"] != repo_id or pr["base"]["ref"] != repo["default_branch"]:
        return EngineeringReport(False, "target-identity-mismatch", "refused",
                                 (Finding("target-identity-mismatch", f"pull request {pull_number}"),), (), (), None)
    run = _Run(reader, enrollment, pr, when)
    patterns = enrollment.governed_paths
    files = reader.pull_request_files(repo_id, pull_number)
    head = pr["head"]["sha"]
    base_tip = reader.branch_head(repo_id, pr["base"]["ref"])
    run.nodes = {n["path"]: n for n in reader.tree(repo_id, head)}
    pointer, receipts, artifacts, refused = _classify(files, patterns)
    for code, path in refused:
        run.fail(code, path)
    base_has = reader.file_at(repo_id, base_tip, POINTER_PATH) is not None if base_tip else False
    _check_pointer(run, pointer, base_has)
    governed = bool(receipts or artifacts or refused)
    changed = set(receipts) | set(artifacts)
    if receipts or artifacts:
        for path in sorted(artifacts):
            node = run.nodes.get(path)
            if node is None or node["type"] != "blob" or node["mode"] not in RS.MODES:
                run.fail("unsafe-artifact-path", path)
                artifacts = {p: s for p, s in artifacts.items() if p != path}
        _check_content(run, artifacts)
        for path, status in sorted(receipts.items()):
            node = run.nodes.get(path)
            if node is None or node["type"] != "blob" or node["mode"] != "100644":
                run.fail("unsafe-artifact-path", path)
                continue
            rid = RECEIPT_PATH.match(path).group(1)
            run.verified[rid] = _check_receipt(run, rid, path, run.blob(path), status)
        try:
            _check_artifacts(run, artifacts)
        except SchemaError as e:
            run.fail(e.code, "release history")
    _base_drift(run, base_tip, changed)
    request_ids = tuple(sorted(rid for rid, ok in run.verified.items() if ok))
    if run.findings:
        first = run.findings[0].code
        return EngineeringReport(False, first, "refused", tuple(run.findings), request_ids, tuple(run.evidence), None)
    if not governed and pointer is None:
        return EngineeringReport(True, "", "no-governed-changes", (), (), (), None)
    kind = "state-only" if receipts and not artifacts and pointer is None and all(
        run.history is not None and run.history.replay.requests[RECEIPT_PATH.match(p).group(1)].state in RS.TERMINAL_STATES for p in receipts) \
        else "content"
    soonest = min(run.expiries) if run.expiries else None
    return EngineeringReport(True, "", kind, (), request_ids, tuple(run.evidence), soonest)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
