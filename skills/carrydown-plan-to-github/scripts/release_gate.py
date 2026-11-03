#!/usr/bin/env python3
"""The release gate: the one module every command that writes outside the private workspace calls
first. Standard library only. Offline. It never reads a token and never talks to a network.

Write classes
  draft       a working file written into the engineering repository while drafting
  candidate   a file written into the private workspace
  release     approved content: repository artifacts, issue bodies, labels, board values, comments
  state-only  regenerated receipts that report an authenticated withdrawal or supersession

What the gate decides
  A project with no handling policy and no enrollment pointer is legacy: the gate answers
  legacy(no-handling-policy) and callers behave as they always did.
  draft       allowed when the owner answered yes to the one question and the file is derived only from
              sources approved for everyone who reads the repository. Otherwise deny(drafting-is-private).
              Once a request is active, a draft write to a file the request approved is refused with
              working-copy-differs when the file no longer holds the approved bytes.
  candidate   always allowed.
  release     allowed only with a verified context made by release_verify.authorize_content no more than
              60 seconds ago, for an active, unexpired request under current policy, whose target
              identities match and whose manifest lists the artifact or payload digest.
  state-only  allowed only with a verified state context, for a receipt path that context names, with the
              digest of the exact terminal projection.
A receipt, a caller-supplied flag and a plain dict are never a context. The gate has no command-line
option and no environment variable that changes a decision, and none will be added. Each allowed write
appends one line (time, request id, decision, write class, artifact path, no content) to
<workspace>/publication/gate.log when the project has a private workspace.

This module is imported by the other scripts. Run with --help to see this text.
"""
import argparse
import os
import sys
import time
from typing import NamedTuple, Optional

import release_schema as RS
import release_verify as V

WRITE_CLASSES = ("draft", "candidate", "release", "state-only")
OUTCOMES = ("legacy", "allow", "deny")
# Files the gate lets through as draft writes on any path: they derive from no source.
UNSOURCED_DRAFTS = (".carrydown/local.yaml", ".gitignore")
POINTER_FILE = ".carrydown/release-policy.yaml"
POINTER_KEYS = ("format", "tooling_repository", "enrollment_id")
MAX_CONTEXT_AGE = V.CONTEXT_MAX_AGE_SECONDS

# The fixed reason codes. The gate and the verifier print these and never attach content.
REASON_CODES = frozenset("""
not-approved approval-not-found approval-not-on-final-revision approver-not-authorized approval-scope-mismatch
unauthenticated-release sha256-mismatch working-copy-differs destination-not-allowed audience-visibility-mismatch
superseded withdrawn expired could-not-refresh mixed-release unapproved-substitution assignee-unresolved
drafting-is-private no-handling-policy enrolled-project-missing-handling policy-pointer-mismatch
workspace-unavailable workspace-inside-repository setup-not-verified restricted-destination-unsupported
governed-file-without-release exception-not-permitted
approval-mechanism-unsupported staging-access-not-verified destination-access-not-verified target-identity-mismatch
receipt-projection-mismatch state-history-invalid state-only-content-write policy-revision-mismatch
verifier-code-mismatch verifier-unhealthy evidence-unavailable inputs-changed-during-verification
unsafe-artifact-path artifact-operation-unsupported schema-view-mismatch
""".split())


class Decision(NamedTuple):
    """The gate's answer. allowed says whether the write may go ahead. outcome is legacy, allow or
    deny. code is a fixed reason code (empty for allow). request_id names the approval that
    authorized the write, when there is one."""
    allowed: bool
    outcome: str
    code: str
    request_id: Optional[str]


class ProjectState(NamedTuple):
    """What the gate learned about the project without any network: the handling block, whether the
    repository is enrolled (a policy pointer exists), the private workspace and why it is missing."""
    handling: Optional[dict]
    enrolled: bool
    pointer: Optional[dict]
    pointer_ok: bool
    workspace: Optional[str]
    repository: str
    spec_dir: str
    has_history: bool


def _lib():
    try:
        import carrydown_lib as lib
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import carrydown_lib as lib
    return lib


def _raw_plan(lib, path):
    if not os.path.isfile(path):
        return None
    try:
        data = lib.load_file(path)
    except (Exception, SystemExit):       # a broken plan is a legacy-or-nothing question for the gate, never a crash
        return None
    return data if isinstance(data, dict) else None


_STATE_CACHE = {}


def _signature(base):
    """What the project state is read from, as (name, size, modification time) of each file and folder, so a
    cached state is reused only while none of them has changed."""
    names = [os.path.join(base, POINTER_FILE), os.path.join(base, ".carrydown", "local.yaml"), os.path.join(base, "docs", "spec", "plan.yaml"),
             os.path.join(base, "plan.yaml")]
    out = []
    pointer = os.path.join(base, ".carrydown", "local.yaml")
    if os.path.isfile(pointer):
        try:
            with open(pointer, "r", encoding="utf-8") as handle:
                names.append(handle.read())
        except OSError:
            pass
    for path in names:
        try:
            st = os.lstat(path)
            out.append((path if len(path) < 400 else path[:400], st.st_size, st.st_mtime_ns))
        except OSError:
            out.append((path if len(path) < 400 else path[:400], None, None))
    return tuple(out)


def project_state(root):
    """The ProjectState of root, read again whenever a file it depends on has changed. See _read_state."""
    base = os.path.abspath(str(root))
    sig = _signature(base)
    cached = _STATE_CACHE.get(base)
    state = cached[1] if cached and cached[0] == sig else None
    if state is not None:
        ws = state.workspace
        if ws:
            extra = tuple((p, *_stat_pair(p)) for p in (os.path.join(ws, "workspace.yaml"), os.path.join(ws, "drafts", "plan.yaml"),
                                                          os.path.join(ws, "requests"), os.path.join(ws, "events")))
            if cached[2] == extra:
                return state
        else:
            return state
    state = _read_state(root)
    extra = tuple((p, *_stat_pair(p)) for p in (os.path.join(state.workspace, "workspace.yaml"), os.path.join(state.workspace, "drafts", "plan.yaml"),
                                                 os.path.join(state.workspace, "requests"), os.path.join(state.workspace, "events"))) if state.workspace else ()
    _STATE_CACHE[base] = (sig, state, extra)
    return state


def _stat_pair(path):
    try:
        st = os.lstat(path)
        return st.st_size, st.st_mtime_ns
    except OSError:
        return None, None


def _read_state(root):
    """Read, offline, what decides the gate: the policy pointer, the private workspace and the handling
    block. The workspace plan (drafts/plan.yaml) wins over the project plan, because on the "no" path
    the answer is recorded in the workspace first. A workspace that names a staging repository, or that
    holds any request, counts as a project with a policy even when no plan carries the block."""
    lib = _lib()
    base = os.path.abspath(str(root))
    pointer = None
    pointer_ok = False
    pointer_path = os.path.join(base, POINTER_FILE)
    enrolled = os.path.lexists(pointer_path)
    if enrolled:
        data = _raw_plan(lib, pointer_path)
        if isinstance(data, dict) and set(data) == set(POINTER_KEYS) and data.get("format") == 1 \
                and isinstance(data.get("tooling_repository"), str) and isinstance(data.get("enrollment_id"), str):
            pointer, pointer_ok = data, True
    workspace, _ = lib.workspace_root(base)
    workspace = str(workspace) if workspace is not None else None
    handling = None
    repository = ""
    spec_dir = "docs/spec"
    plans = []
    if workspace:
        plans.append(os.path.join(workspace, "drafts", "plan.yaml"))
    try:
        plans.append(str(lib.find_plan(base, None)))
    except Exception:
        pass
    for path in plans:
        raw = _raw_plan(lib, path) if os.path.isfile(path) else None
        project = raw.get("project") if isinstance(raw, dict) else None
        if isinstance(project, dict):
            repository = repository or str(project.get("repo") or "")
            spec_dir = str(project.get("spec_dir") or spec_dir)
            if handling is None and isinstance(project.get("handling"), dict):
                handling = dict(project["handling"])
    has_history = False
    if workspace:
        info = _raw_plan(lib, os.path.join(workspace, "workspace.yaml")) or {}
        has_history = bool(info.get("staging_repository")) or any(
            os.path.isdir(os.path.join(workspace, d)) and os.listdir(os.path.join(workspace, d)) for d in ("requests", "events"))
        if handling is None and info.get("staging_repository"):
            handling = {"repo_audience_approved": False, "state": "migrated"}   # fail closed: a staging repository means the "no" path
    return ProjectState(handling, enrolled, pointer, pointer_ok, workspace, repository, spec_dir, has_history)


def _is_legacy(state):
    if state.enrolled:
        return False
    if state.handling is None:
        return not state.has_history
    return state.handling.get("state") == "legacy" and not state.has_history


def maintenance_class(root):
    """The write class for commands that regenerate or repair files in the engineering repository
    (plan_repair, generate_dev_skill, scaffold_spec --refresh-headers): release when the repository is
    enrolled, so that nothing is written without an approved request, and draft otherwise."""
    return "release" if os.path.lexists(os.path.join(os.path.abspath(str(root)), POINTER_FILE)) else "draft"


def _workspace_log(state, request_id, decision, write_class, artifact_path):
    if not state.workspace:
        return
    try:
        folder = os.path.join(state.workspace, "publication")
        os.makedirs(folder, exist_ok=True)
        line = "{} {} {} {} {}\n".format(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), request_id or "-", decision,
                                         write_class, str(artifact_path).replace("\n", " ").replace("\r", " "))
        with open(os.path.join(folder, "gate.log"), "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


_noticed = set()


def legacy_notice(write_class):
    """One line per command run, on standard error, the first time a legacy project asks the gate."""
    if "legacy" not in _noticed:
        _noticed.add("legacy")
        print("carrydown: this project has no handling policy (legacy), so the release gate is not in force. "
              "Run step 0 of the ground-truth skill to migrate it.", file=sys.stderr)


def _deny(state, request_id, write_class, artifact_path, code):
    return Decision(False, "deny", code, request_id)


def _allow(state, request_id, write_class, artifact_path, outcome="allow"):
    _workspace_log(state, request_id, outcome, write_class, artifact_path)
    return Decision(True, outcome, "" if outcome == "allow" else "no-handling-policy", request_id)


def _active_release(state):
    """(request id, {manifest path: sha256}) of the one active request in the workspace's own event
    files, or (None, {}). A broken event chain raises SchemaError."""
    if not state.workspace:
        return None, {}
    if not os.path.isdir(os.path.join(state.workspace, "events")):
        return None, {}
    replay = V.local_replay(state.workspace).replay
    rid = replay.active
    if rid is None:
        return None, {}
    with open(os.path.join(state.workspace, "requests", rid, "approval-request.json"), "rb") as handle:
        request = RS.loads_strict(handle.read())
    with open(os.path.join(state.workspace, "releases", request["release_id"], "content-manifest.json"), "rb") as handle:
        manifest = handle.read()
    return rid, {e["path"]: e["sha256"] for e in RS.validate_manifest(manifest)}


def _working_matches(state, root, artifact_path, approved_sha):
    """True when the working copy of artifact_path holds the approved bytes. The plan is a special
    case: the working plan may be the owner's draft of the released plan, so its released projection is
    compared instead."""
    path = os.path.join(os.path.abspath(str(root)), artifact_path)
    if not os.path.lexists(path):
        return True
    if not os.path.isfile(path) or os.path.islink(path):
        return False
    if RS.sha256_file(path) == approved_sha:
        return True
    if artifact_path == f"{state.spec_dir}/plan.yaml":
        lib = _lib()
        try:
            plan, _ = lib.load_plan(path, os.path.abspath(str(root)))
            return RS.sha256_bytes(lib.released_plan_bytes(plan)) == approved_sha
        except Exception:
            return False
    return False


def _check_draft(state, artifact_path, destination, root, request_id, verified_context):
    path = str(artifact_path).replace("\\", "/")
    if path in UNSOURCED_DRAFTS:
        return None
    handling = state.handling
    if handling is None:
        return "enrolled-project-missing-handling"
    if handling.get("repo_audience_approved") is not True:
        return "drafting-is-private"
    hint = verified_context.get("source_classification") if isinstance(verified_context, dict) else None
    if hint is not None and hint not in ("repo-readers", "public"):
        return "drafting-is-private"
    try:
        rid, manifest = _active_release(state)
    except (RS.SchemaError, OSError, ValueError):
        return "state-history-invalid"
    if rid is not None:
        approved = manifest.get("repo/" + path)
        if approved is not None and not _working_matches(state, root, path, approved):
            return "working-copy-differs"
    return None


def _local_policy_sha(state):
    handling = state.handling or {}
    lib = _lib()
    released = {k: handling[k] for k in lib.RELEASED_HANDLING_KEYS if k in handling}
    return V.local_policy(released, state.repository).policy_sha256


def _check_release(state, artifact_path, content_digest, destination, request_id, ctx, now):
    if not isinstance(ctx, V.VerifiedContext) or ctx.kind != "content":
        return "not-approved"
    age = now - ctx.issued_at
    if age < 0 or age > MAX_CONTEXT_AGE:
        return "not-approved"
    if request_id is not None and request_id != ctx.request_id:
        return "approval-scope-mismatch"
    if ctx.expires_at and V.to_epoch(ctx.expires_at, "expires_at") <= now:
        return "expired"
    if state.enrolled:
        if not state.pointer_ok or state.pointer["enrollment_id"] != ctx.enrollment_id:
            return "policy-pointer-mismatch"
        if ctx.mechanism != "github-review":
            return "unauthenticated-release"
    else:
        if ctx.mechanism != "local-owner":
            return "unauthenticated-release"
        if state.handling is None or ctx.policy_sha256 != _local_policy_sha(state):
            return "policy-revision-mismatch"
    # Repository files go to engineering-repo or engineers-skill; a GitHub write names a target id whose
    # identity the context resolved through the API. An offline context names no target.
    if not (destination in ctx.target_ids or (destination in ("engineering-repo", "engineers-skill") and destination in ctx.destinations)):
        return "destination-not-allowed"
    path = str(artifact_path).replace("\\", "/")
    if path in ctx.receipt_digests:
        return None if ctx.receipt_digests[path] == content_digest else "receipt-projection-mismatch"
    key = path if path.startswith("payloads/") else "repo/" + path
    entry = ctx.entries.get(key)
    if entry is None:
        return "approval-scope-mismatch"
    return None if entry[0] == content_digest else "sha256-mismatch"


def _check_state_only(state, artifact_path, content_digest, request_id, ctx, now):
    if not isinstance(ctx, V.VerifiedContext) or ctx.kind != "state":
        return "not-approved"
    age = now - ctx.issued_at
    if age < 0 or age > MAX_CONTEXT_AGE:
        return "not-approved"
    if request_id is not None and request_id != ctx.request_id:
        return "approval-scope-mismatch"
    path = str(artifact_path).replace("\\", "/")
    if path not in ctx.receipt_digests:
        return "state-only-content-write"
    return None if ctx.receipt_digests[path] == content_digest else "receipt-projection-mismatch"


def check(write_class, artifact_path, content_digest, destination, root, *,
          request_id=None, event_id=None, verified_context=None):
    """Ask whether a write is permitted. Call this before every write outside the private workspace.

    write_class is one of WRITE_CLASSES. artifact_path is the file, relative to root, or the payload path
    such as payloads/issue/WI-07.json for a GitHub target. content_digest is the lowercase SHA-256 of the
    bytes to be written (for a GitHub target, of the payload file in the manifest). destination is
    engineering-repo, workspace or a target id or destination category. root is the project folder.
    request_id and event_id name the approval and the state batch in play.

    verified_context is, for a release write, the VerifiedContext of release_verify.authorize_content and,
    for a state-only write, the context of authorize_state_receipt. For a draft write it may be a dict
    with source_classification, which can only narrow the answer: a rendering of a source that is not
    repo-readers or public is denied. Nothing else counts as a context.

    An unknown write class is a bug in the caller and raises ValueError."""
    if write_class not in WRITE_CLASSES:
        raise ValueError(f"unknown write class {write_class!r}. Use one of: {', '.join(WRITE_CLASSES)}")
    now = V.clock()
    state = project_state(root)
    if write_class == "candidate":
        if _is_legacy(state):
            return Decision(True, "legacy", "no-handling-policy", request_id)
        return _allow(state, request_id, write_class, artifact_path)
    if _is_legacy(state):
        legacy_notice(write_class)
        return Decision(True, "legacy", "no-handling-policy", request_id)
    if state.enrolled and not state.pointer_ok:
        return _deny(state, request_id, write_class, artifact_path, "policy-pointer-mismatch")
    if write_class == "draft":
        code = _check_draft(state, artifact_path, destination, root, request_id, verified_context)
    elif write_class == "release":
        if state.handling is None and state.enrolled:
            code = "enrolled-project-missing-handling"
        else:
            code = _check_release(state, artifact_path, content_digest, destination, request_id, verified_context, now)
    else:
        code = _check_state_only(state, artifact_path, content_digest, request_id, verified_context, now)
    if code:
        return _deny(state, request_id, write_class, artifact_path, code)
    rid = request_id or (verified_context.request_id if isinstance(verified_context, V.VerifiedContext) else None)
    return _allow(state, rid, write_class, artifact_path)


def require(write_class, artifact_path, content_digest, destination, root, **kwargs):
    """check, then stop the command with one line when the answer is deny. Returns the Decision."""
    decision = check(write_class, artifact_path, content_digest, destination, root, **kwargs)
    if not decision.allowed:
        _lib().die(f"{decision.code}: the release gate refused the write of {artifact_path}. Nothing was changed", 1)
    return decision


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="The release gate for commands that write outside the private workspace. A library: "
                    "import it and call check(). No option and no environment variable changes a decision. "
                    "It answers legacy(no-handling-policy) for a project with no handling policy.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
