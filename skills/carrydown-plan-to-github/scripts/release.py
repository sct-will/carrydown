#!/usr/bin/env python3
"""Prepare, approve, export and withdraw a release of the project's approved context.

A release is approved content plus one permission decision. Two identities keep them apart:
  release id   the digest of the content manifest. It names exact bytes.
  request id   the digest of one approval request: this content, for this audience, these
               destinations and these downstream uses. The same content can have several requests,
               and approving one never approves another.

Commands (every one that writes is a dry run unless you pass --apply)
  preview   --root .                  the four-question preview and the changes since the last release
  prepare   --root . [--apply]        build the snapshot, the manifest and the approval request
  approve   --request ID --local      the "yes" path: record your own approval and an activation event
  approve   --request ID --github     the "no" path: upload the candidate to the private staging repository
  export    --request ID              copy the approved files and the receipt into the engineering repository
  export-state --request ID           write only the regenerated receipt of a superseded or withdrawn request
  withdraw  --request ID --reason CODE   prepare the terminal event that ends a request
  diff      --root .                  what changed since the active release, and which work items it touches
  inventory --root .                  what a legacy project tracks and has in git history. The first step of migrating. Writes nothing
  doctor    --root .                  the offline workspace checks, and the live checks when a token is set

How a decision is made (specification D6, D10, D13)
  "Yes" path (everyone who can read the repository may see all the documents). approve --local prints the
  four-question preview from the request, then records your approval. When a person runs it in a terminal
  it asks you to type yes. An agent that runs it passes --preview-shown after it has shown you the
  preview and you answered the disclosure line of the three approvals; without a terminal and without
  --preview-shown the command refuses. The evidence is a local owner approval, labeled
  authenticated false. A project enrolled in the tooling repository refuses it.
  "No" path. approve --github verifies the staging repository first (numeric identity, privacy, effective
  readers, workflow, ruleset) and uploads nothing until every one is verified. It pushes a branch
  request/<request id> with the snapshot, the manifest, the request and an activation event, using the git
  credentials you already have (no token is placed in a URL), then waits up to two minutes for the staging
  workflow to open the pull request. You approve that pull request in GitHub. export verifies the approval
  through the API before it writes anything.

Export. On the "no" path it makes an isolated worktree on carrydown/request-<id> from the fetched default
branch, copies only the approved files and the receipts, and commits as you; it prints the push and pull
request commands and does not run them. On the "yes" path it copies the approved files into your
working tree and writes the receipts; it refuses (working-copy-differs) when a file you edited differs
from the snapshot, and leaves commit and push to you.

--created and --nonce exist to reproduce a release exactly (tests, the sample): --created is the UTC
time (2027-01-20T14:03:00Z) used for the request and its events, and --nonce is the 32 hexadecimal
characters of the request nonce. A real run leaves them out and gets the clock and a random nonce.

Exit status 0 when the command succeeded, 1 when it was refused or something failed, 2 for a wrong argument.
Nothing printed holds the text of a source, a private path or a token; refusals are fixed reason codes.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402
import detectors as D  # noqa: E402
import release_assemble as A  # noqa: E402
import release_build as B  # noqa: E402
import release_gate as RG  # noqa: E402
import release_inventory as RI  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402

POLL_SECONDS = 120
POLL_INTERVAL = 5
FOUR_QUESTIONS = ("What will be shared", "With whom", "Where", "What remains private")
PREVIEW_KEYS = FOUR_QUESTIONS + ("Changes since the previous release", "Limitations")
QUESTION_TEXT = {"What will be shared": "What will be shared?", "With whom": "With whom?", "Where": "Where?",
                 "What remains private": "What remains private?"}
PUBLIC_RECEIPT_DIR = "docs/release"


# ---------------------------------------------------------------------------
# Seams a test replaces. Nothing else reaches the network.
# ---------------------------------------------------------------------------

def sleep(seconds):
    time.sleep(seconds)


def make_reader(args):
    """The EvidenceReader for the GitHub API, built from the owner's token. The token is read from
    --token-file, CARRYDOWN_GITHUB_TOKEN or the stored token file and is never printed."""
    import github_client as G
    import release_github as RGH
    token = G.read_token(getattr(args, "token_file", None), required=True)
    return RGH.GitHubEvidenceReader(G.GitHub(token))


def token_available(args):
    try:
        import github_client as G
        return G.read_token(getattr(args, "token_file", None), required=False) is not None
    except (ImportError, SystemExit):
        return False


def staging_remote_url(owner_repo, host="github.com", like=""):
    """The git URL to push to. The protocol follows the engineering remote (ssh or https) so the owner's
    existing credentials apply. No token is ever placed in it."""
    if str(like).startswith("git@") or str(like).startswith("ssh://"):
        return f"git@{host}:{owner_repo}.git"
    return f"https://{host}/{owner_repo}.git"


def dispatch_request_workflow(args, owner_repo, branch):
    """Ask the staging repository's default branch to run the request-opening workflow now. Best
    effort: a failure only means the schedule opens the pull request later."""
    try:
        import github_client as G
        token = G.read_token(getattr(args, "token_file", None), required=False)
        if not token:
            return False
        G.GitHub(token).rest("POST", f"/repos/{owner_repo}/actions/workflows/open-release-request.yml/dispatches", {"ref": branch})
        return True
    except Exception:       # a refusal here is expected when the token cannot dispatch workflows
        return False


# ---------------------------------------------------------------------------
# The project, its workspace and the small helpers
# ---------------------------------------------------------------------------

class Refused(Exception):
    """A command stops with a fixed reason code and one plain line."""

    def __init__(self, code, text):
        super().__init__(text)
        self.code = code
        self.text = text


def refuse(code, text):
    raise Refused(code, text)


class Project:
    """What the release commands need to know about the project, read once."""

    def __init__(self, root):
        self.root = L.project_root(root)
        self.workspace, self.why = L.workspace_root(self.root)
        self.state = RG.project_state(self.root)

    @property
    def enrolled(self):
        return self.state.enrolled

    @property
    def mode(self):
        return "no" if self.enrolled or (self.state.handling or {}).get("repo_audience_approved") is not True else "yes"

    @property
    def repository(self):
        return self.state.repository

    @property
    def handling(self):
        return self.state.handling or {}

    def need_workspace(self):
        if self.workspace is None:
            refuse(self.why or "workspace-unavailable",
                   "there is no private workspace for this project. Create it with workspace.py init --root . --apply")
        return Path(self.workspace)

    def released_handling(self):
        return {k: self.handling[k] for k in L.RELEASED_HANDLING_KEYS if k in self.handling}


def say(text=""):
    L.say(text)


def created_text(a):
    value = getattr(a, "created", None)
    if value:
        V.to_epoch(value, "--created")
        return value
    return B.now_text()


def workspace_put(project, rel, data):
    """Write a file inside the private workspace. Candidate-class writes are always allowed; the gate is
    asked so the write is logged."""
    ws = project.need_workspace()
    data = bytes(data)
    RG.require("candidate", rel, RS.sha256_bytes(data), "workspace", project.root)
    path = ws / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def read_bytes(path):
    try:
        if os.path.islink(path):
            refuse("unsafe-artifact-path", "a record is a symbolic link")
        return Path(path).read_bytes()
    except OSError:
        return None


def load_request(ws, rid):
    """The request of the workspace, strictly validated, with its digest recomputed."""
    if not re.fullmatch(r"[0-9a-f]{64}", str(rid or "")):
        refuse("approval-not-found", "--request must be the 64 character request id that prepare printed")
    raw = read_bytes(Path(ws) / "requests" / rid / "approval-request.json")
    if raw is None:
        refuse("approval-not-found", "no request with that id is in the workspace")
    request = RS.loads_strict(raw)
    RS.validate_request(request)
    if request["request_sha256"] != rid:
        refuse("sha256-mismatch", "the request in the workspace does not match its id")
    if raw != RS.canonical_json(request):
        refuse("sha256-mismatch", "the request in the workspace is not in canonical form")
    return request


def load_release(ws, release_id):
    """(manifest bytes, entries, {snapshot path: bytes}) of releases/<release id>. The snapshot is read
    only after every file, mode, membership and symlink check against the manifest has passed."""
    folder = Path(ws) / "releases" / release_id
    manifest = read_bytes(folder / "content-manifest.json")
    if manifest is None:
        refuse("approval-not-found", "the snapshot of this release is not in the workspace")
    if RS.sha256_bytes(manifest) != release_id:
        refuse("sha256-mismatch", "the manifest in the workspace does not match its release id")
    entries = RS.validate_manifest(manifest)
    V.verify_snapshot_dir(str(folder / "snapshot"), entries)
    files = {e["path"]: (folder / "snapshot" / e["path"]).read_bytes() for e in entries}
    return manifest, entries, files


def write_state_cache(project, replay, tip=None):
    """requests/<id>/state.json for each request the events know: a disposable cache, never authority."""
    ws = project.need_workspace()
    for rid, st in replay.requests.items():
        if (ws / "requests" / rid).is_dir():
            request = load_request(ws, rid)
            record = {"request_id": rid, "release_id": request["release_id"], "state": st.state, "event_id": st.event_id,
                      "staging_tip": tip}
            workspace_put(project, f"requests/{rid}/state.json", RS.canonical_json(record))


def identity(project):
    """The owner's git identity, (name, email), from git config. Empty strings when not set."""
    out = []
    for key in ("user.name", "user.email"):
        try:
            run = subprocess.run(["git", "-C", str(project.root), "config", key], capture_output=True, text=True, timeout=30)
            out.append(run.stdout.strip() if run.returncode == 0 else "")
        except (OSError, subprocess.SubprocessError):
            out.append("")
    return tuple(out)


def git(args, cwd, timeout=120, check=True, env_extra=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="true", LC_ALL="C")
    env.update(env_extra or {})
    run = subprocess.run(["git"] + list(args), cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
    if check and run.returncode != 0:
        refuse("evidence-unavailable", f"git {args[0]} failed")
    return run


def default_branch(project, fallback="main"):
    """The engineering repository's default branch: origin/HEAD, else the remote's HEAD, else the plan's branch."""
    run = git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], project.root, check=False)
    if run.returncode == 0 and run.stdout.strip().startswith("refs/remotes/origin/"):
        return run.stdout.strip()[len("refs/remotes/origin/"):]
    run = git(["ls-remote", "--symref", "origin", "HEAD"], project.root, check=False, timeout=60)
    m = re.search(r"ref: refs/heads/(\S+)\s+HEAD", run.stdout or "")
    return m.group(1) if m else fallback


# ---------------------------------------------------------------------------
# Targets and policy
# ---------------------------------------------------------------------------

def current_policy(project, args, reader=None, asm=None):
    """(policy, enrollment or None, reader or None). The "yes" path has a local policy that covers the
    released handling block. A project with a policy pointer needs the live enrollment, read through the
    API by the repository's numeric id."""
    if not project.enrolled:
        return V.local_policy(project.released_handling(), project.repository), None, reader
    pointer = project.state.pointer
    if pointer is None:
        refuse("policy-pointer-mismatch", "the policy pointer .carrydown/release-policy.yaml cannot be read")
    reader = reader or make_reader(args)
    repo = reader.repository(project.repository)
    if repo is None:
        refuse("target-identity-mismatch", "the engineering repository cannot be found by its name")
    enrollment = V.load_current_enrollment(repo["id"], reader, pointer["tooling_repository"], parse=L.loads,
                                           pointer_enrollment_id=pointer["enrollment_id"], host=repo.get("host", "github.com"))
    return enrollment, enrollment, reader


def resolve_targets(project, args, asm, enrollment, reader):
    """The target list of the request. Enrolled: the enrollment's allowed targets, selected by the
    destinations. Not enrolled: the engineering repository named in the plan, with its numeric id from
    --repository-id or the API, and the board from --board-owner-id and --board-project-id."""
    wants_board = "board" in asm.destinations
    wants_repo = any(d in asm.destinations for d in ("engineering-repo", "engineers-skill", "issue", "subepic", "epic", "epic-comment", "label"))
    out = []
    if enrollment is not None:
        allowed = enrollment.entry["allowed_targets"]
        if wants_repo:
            if "engineering" not in allowed:
                refuse("destination-not-allowed", "the enrollment allows no engineering repository target")
            out.append(dict(id="engineering", **allowed["engineering"]))
        if wants_board:
            if "board" not in allowed:
                refuse("destination-not-allowed", "the enrollment allows no board target")
            out.append(dict(id="board", **allowed["board"]))
        return sorted(out, key=lambda t: t["id"])
    repo = project.repository
    if not repo or not L.repo_ok(repo):
        refuse("target-identity-mismatch", "project.repo in the plan must be owner/name")
    rid = getattr(args, "repository_id", None)
    if rid is None and token_available(args):
        info = (reader or make_reader(args)).repository(repo)
        rid = info["id"] if info else None
    if rid is None:
        refuse("target-identity-mismatch",
               f"prepare needs the numeric id of {repo}. Pass --repository-id N (gh api repos/{repo} --jq .id), or set a token so it can be read")
    out.append({"id": "engineering", "host": "github.com", "repository_id": int(rid), "repository": repo})
    if wants_board:
        owner_id, project_id = getattr(args, "board_owner_id", None), getattr(args, "board_project_id", None)
        if owner_id is None or not project_id:
            refuse("destination-not-allowed",
                   "the board is a destination, but its identity is not known. Pass --board-owner-id and --board-project-id, "
                   "or leave the board out with --destinations")
        out.append({"id": "board", "host": "github.com", "repository_id": int(rid), "owner_id": int(owner_id), "project_id": str(project_id)})
    return sorted(out, key=lambda t: t["id"])


def current_replay(project, enrollment, reader):
    """The ReplayResult of the project's authenticated events: from the staging history when enrolled, from
    the workspace's own event files otherwise. None when there is nothing to replay yet."""
    if enrollment is not None:
        return V.replay_staging(reader, enrollment).replay
    ws = project.workspace
    if ws is None or not (Path(ws) / "events").is_dir():
        return None
    return V.local_replay(str(ws)).replay


# ---------------------------------------------------------------------------
# The preview (C5) and the diff against the previous release
# ---------------------------------------------------------------------------

def tag_of(plan, path):
    """The work item tag a snapshot path belongs to, or None."""
    prefix = re.escape(plan["project"]["id_prefix"])
    m = re.search(rf"(?i)(?:^|/)({prefix})-0*(\d+)(?:[-.]|\.json$|\.md$)", path)
    if m:
        return L.tag(plan, int(m.group(2)))
    return None


def previous_files(project, previous_id):
    """({path: sha256}, request) of the previous active request from the workspace, or ({}, None)."""
    ws = project.workspace
    if ws is None or previous_id is None:
        return {}, None
    try:
        request = load_request(ws, previous_id)
        manifest = read_bytes(Path(ws) / "releases" / request["release_id"] / "content-manifest.json")
        if manifest is None:
            return {}, request
        return {e["path"]: e["sha256"] for e in RS.validate_manifest(manifest)}, request
    except (Refused, RS.SchemaError):
        return {}, None


def diff_lines(project, asm, new_entries, request_params, previous_id):
    """Plain lines describing what differs from the previous active release."""
    old, old_request = previous_files(project, previous_id)
    if previous_id is None:
        return ["This is the first release. Nothing is being replaced."], set()
    if not old:
        return ["The previous release is known only by its id; its files are not in this workspace, so no comparison is shown."], set()
    new = {e["path"]: e["sha256"] for e in new_entries}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(p for p in set(new) & set(old) if new[p] != old[p])
    plan = asm.plan
    items = {tag_of(plan, p) for p in added + changed + removed} - {None}
    lines = [f"Added: {len(added)} file(s). Changed: {len(changed)} file(s). Removed: {len(removed)} file(s) "
             "(removal is not supported by export, so removed files stay where they are)."]
    for label, group in (("added", added), ("changed", changed), ("removed", removed)):
        for p in group[:40]:
            lines.append(f"  {label}: {p}")
        if len(group) > 40:
            lines.append(f"  ... and {len(group) - 40} more {label}")
    if items:
        lines.append("Work items affected: " + ", ".join(sorted(items)))
    if old_request is not None:
        t = old_request["receipt_template"]
        scope = []
        for key in ("audience", "destinations", "targets", "downstream", "expires_at", "offline_grace_days"):
            if t[key] != request_params.get(key):
                scope.append(key)
        if old_request["policy_sha256"] != request_params.get("policy_sha256"):
            scope.append("policy")
        if {s["id"]: s["version"] for s in t["sources"]} != {s["id"]: s["version"] for s in request_params["sources"]}:
            scope.append("source versions")
        lines.append("Scope changes: " + (", ".join(scope) if scope else "none (same audience, destinations, targets and downstream uses)"))
    return lines, items


def build_preview(project, asm, request_params, entries, previous_id):
    """The preview object stored in the request: the four questions in order, then the changes and the
    limits. Every value is a list of plain lines. It names ids, counts and paths, never source text."""
    plan = asm.plan
    flags = asm.flags
    repo_files = sorted(p[len("repo/"):] for p in asm.files if p.startswith("repo/"))
    payloads = {}
    for p in asm.payload_paths:
        payloads.setdefault(p.split("/")[1], []).append(p.rsplit("/", 1)[-1][:-len(".json")])
    shared = [f"{len(repo_files)} repository file(s): the released plan, {sum(1 for p in repo_files if p.startswith(plan['project']['spec_dir'] + '/'))} specification file(s), "
              f"{sum(1 for p in repo_files if p.startswith('docs/context/'))} approved context file(s) and the engineers' skill."]
    shared += [f"  {p}" for p in repo_files]
    for kind in A.GITHUB_DESTINATIONS:
        if kind in payloads:
            shared.append(f"{len(payloads[kind])} {kind} payload(s) for GitHub: " + ", ".join(sorted(payloads[kind])[:30]) + (" ..." if len(payloads[kind]) > 30 else ""))
    present = sum(r[2] for r in asm.rows)
    total = sum(r[3] for r in asm.rows)
    shared.append(f"Obligations present in the bundles: {present} of {total}. Presence is checked by the compiler. Whether each bundle is enough to do the work is your review.")
    if asm.resolution is not None and asm.resolution.resolved:
        shared += D.exception_preview_lines(asm.resolution)
    audience = request_params["audience"]
    repo = project.repository or "this repository"
    whom = [("Everyone who can read " + repo) if audience == "repo-readers" else "The public. Anyone can read what is published."]
    logins = sorted({a for p in asm.payload_paths if "/issue/" in p for a in json.loads(asm.files[p])["assignees"]})
    whom.append("Assignee logins named on issues: " + (", ".join(logins) if logins else "none") if flags["assignees"] else "No assignee login is published.")
    whom.append("The capacity summary (people by track) is published." if flags["capacity_summary"] else "No capacity summary (number of people by track) is published.")
    whom.append("Evidence in tests and code: " + ("synthetic data only." if flags["evidence"] == "synthetic-only" else "approved data."))
    where = []
    for t in request_params["targets"]:
        if "project_id" in t:
            where.append(f"Board: project {t['project_id']} (owner id {t['owner_id']}), linked to repository id {t['repository_id']}.")
        else:
            where.append(f"Repository: {t['repository']} (numeric id {t['repository_id']}) on {t['host']}.")
    where.append("Destinations: " + ", ".join(request_params["destinations"]) + ".")
    private = ["The sources and their originals stay in the private workspace or the system they came from.",
               "Staffing records (names, skills, allocation, days off, start dates) stay in the private workspace; the released plan holds ids and tracks only."]
    restricted_sources = [s["id"] for s in plan["sources"] if s.get("classification") == "restricted"]
    if restricted_sources:
        private.append(f"{len(restricted_sources)} restricted source(s) are not released; only the sections the bundles cite appear, as approved text.")
    if asm.restricted_items:
        hidden = asm.restricted_items - len(asm.withheld)
        private.append(f"{asm.restricted_items} restricted work item(s) are not published: no specification, no approved context and no GitHub issue."
                       + (f" {hidden} of them appear nowhere in this release." if hidden else ""))
        for tag, summary, instruction in asm.withheld:
            shared.append(f"External item {tag}, published with this text from you and nothing else: \"{summary}\"")
            if instruction:
                shared.append(f"Placeholder for {tag}, shown to an engineer who asks for it: \"{instruction}\"")
    if asm.link_items:
        shared.append(f"{len(asm.link_items)} issue(s) hold links instead of the text of Acceptance criteria, Evidence of completion and "
                      "Integration points, because their approved context holds a section of a restricted source: " + ", ".join(sorted(asm.link_items)[:20]))
    changes, _ = diff_lines(project, asm, entries, request_params, previous_id)
    limits = list(asm.notes)
    for tag, done in asm.restricted_status:
        limits.append(f"Restricted work item {tag} is " + ("done: you recorded evidence in your workspace plan." if done else
                      "still open: no evidence is recorded in your workspace plan (restricted_evidence).") + " Nothing is posted to GitHub for it.")
    if asm.resolution is not None and asm.resolution.resolved:
        limits.append(f"{len(asm.resolution.resolved)} detector finding(s) are cleared by recorded exceptions that you approve with this request.")
    if not limits:
        limits.append("None found. The detectors are a safety net and do not prove safety.")
    return {"What will be shared": shared, "With whom": whom, "Where": where, "What remains private": private,
            "Changes since the previous release": changes if isinstance(changes, list) else list(changes), "Limitations": limits}


def print_preview(preview, header="carrydown release preview"):
    say(header)
    for key in FOUR_QUESTIONS:
        say("")
        say(QUESTION_TEXT[key])
        for line in preview.get(key, []):
            say(line if line.startswith("  ") else "  " + line)
    for key in PREVIEW_KEYS[4:]:
        say("")
        say(key)
        for line in preview.get(key, []):
            say(line if line.startswith("  ") else "  " + line)


# ---------------------------------------------------------------------------
# preview, prepare, diff
# ---------------------------------------------------------------------------

def read_exceptions(path):
    if not path:
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        refuse("schema-invalid", "--exceptions must be a JSON file holding a list of detector exceptions")
    if isinstance(data, dict):
        data = data.get("detector_exceptions", [])
    if not isinstance(data, list):
        refuse("schema-invalid", "--exceptions must be a JSON file holding a list of detector exceptions")
    return data


def yes_no(value):
    return None if value is None else value == "yes"


def engineer_edits_of(enrollment):
    """allowed or request-only for docs/spec/**, from the enrollment's captured policy. None when the
    project is not enrolled: the engineers' skill then follows project.handling.engineer_edits of the plan.
    An enrollment that does not say gets the stricter value, request-only."""
    if enrollment is None or not getattr(enrollment, "enrolled", False):
        return None
    edits = enrollment.entry.get("engineer_edits")
    value = edits.get("docs/spec/**") if isinstance(edits, dict) else None
    return value if value in L.ENGINEER_EDITS else "request-only"


def build_assembly(project, a, enrollment=None):
    """The Assembly for the command's options. The board is part of the release only when its identity is
    known: given with --board-owner-id and --board-project-id, or allowed by the enrollment."""
    explicit = [d.strip() for d in a.destinations.split(",")] if getattr(a, "destinations", None) else None
    destinations = explicit
    if getattr(a, "no_github", False):
        keep = ("engineering-repo", "engineers-skill")
        destinations = [d for d in (explicit or keep) if d in keep]
    board_known = (getattr(a, "board_owner_id", None) is not None and bool(getattr(a, "board_project_id", None))) or \
        (enrollment is not None and "board" in enrollment.entry["allowed_targets"])
    with_board = board_known or (explicit is not None and "board" in explicit)
    overrides = {"assignees": yes_no(getattr(a, "assignees", None)), "capacity_summary": yes_no(getattr(a, "capacity_summary", None)),
                 "evidence": getattr(a, "evidence", None)}
    asm = A.assemble(project.root, with_github=not getattr(a, "no_github", False), exceptions=read_exceptions(getattr(a, "exceptions", None)),
                     flag_overrides=overrides, destinations=destinations, with_board=with_board, engineer_edits=engineer_edits_of(enrollment))
    if not with_board and not getattr(a, "no_github", False) and asm.payload_paths:
        asm = asm._replace(notes=asm.notes + ["The board is not in this release: its identity is not known "
                                              "(--board-owner-id and --board-project-id, or an enrollment that allows it)."])
    return asm


def report_assembly_problems(asm):
    for p in asm.problems:
        say(("  " if not p.startswith("  ") else "") + p)
    for line in D.report_lines(asm.findings) if asm.findings else []:
        say(line)
    if asm.findings:
        say("A detector finding blocks the release. Credentials, private paths and staffing fields can never be excepted. "
            "A copied passage or an organization phrase can be, with a recorded exception (--exceptions FILE) that you approve.")
    return bool(asm.problems or asm.findings)


def request_params_for(project, a, asm, entries, release_id, policy, targets, previous_id):
    handling = project.handling
    grace = handling.get("offline_grace_days")
    if getattr(policy, "enrolled", False):
        grace = policy.entry.get("offline_grace_days", grace)
    grace = grace if isinstance(grace, int) and not isinstance(grace, bool) and grace >= 0 else 7
    audience = getattr(a, "audience", None) or "repo-readers"
    expires = getattr(a, "expires", None)
    if expires:
        V.to_epoch(expires, "--expires")
    return {
        "audience": audience, "destinations": list(asm.destinations), "targets": targets, "sources": asm.sources,
        "downstream": {"assignees": bool(asm.flags["assignees"]), "capacity_summary": bool(asm.flags["capacity_summary"]),
                       "evidence": asm.flags["evidence"]},
        "offline_grace_days": grace, "expires_at": expires or None, "policy_sha256": policy.policy_sha256,
    }


def scope_digest(params, exceptions):
    body = {k: params[k] for k in ("audience", "destinations", "targets", "sources", "downstream", "offline_grace_days", "expires_at", "policy_sha256")}
    body["exceptions"] = exceptions
    return RS.sha256_bytes(RS.canonical_json(body))


def used_exceptions(asm):
    seen, out = set(), []
    if asm.resolution is None:
        return out
    for _finding, ex in asm.resolution.resolved:
        key = (ex["type"], ex["passage_sha256"], tuple(ex["destinations"]))
        if key not in seen:
            seen.add(key)
            out.append({k: ex[k] for k in RS.EXCEPTION_KEYS})
    return sorted(out, key=lambda e: (e["type"], e["passage_sha256"], e["destinations"]))


def preview_inputs(project, a):
    """(policy, enrollment, reader) for a command that only reads: the live enrollment when the project is
    enrolled and a token exists, else the local policy."""
    if project.enrolled and token_available(a):
        return current_policy(project, a)
    return V.local_policy(project.released_handling(), project.repository), None, None


def cmd_preview(a):
    project = Project(a.root)
    policy, enrollment, reader = preview_inputs(project, a)
    asm = build_assembly(project, a, enrollment)
    say("carrydown release preview (reads your working files; writes nothing)")
    if report_assembly_problems(asm):
        return 1
    manifest, release_id, entries = B.build_manifest(asm.files)
    replay = None
    try:
        replay = current_replay(project, enrollment, reader)
    except RS.SchemaError:
        replay = None
    previous_id = replay.active if replay else None
    try:
        targets = resolve_targets(project, a, asm, enrollment, reader)
    except Refused as e:
        targets = []
        asm = asm._replace(notes=asm.notes + [f"Targets not resolved yet: {e.text}"])
    params = request_params_for(project, a, asm, entries, release_id, policy, targets, previous_id)
    preview = build_preview(project, asm, params, entries, previous_id)
    say("")
    say(f"release id (the content): {release_id}")
    print_preview(preview, header="")
    say("")
    say("Nothing was written. Run prepare --apply to build the snapshot and the approval request.")
    return 0


def cmd_diff(a):
    project = Project(a.root)
    policy, enrollment, reader = preview_inputs(project, a)
    asm = build_assembly(project, a, enrollment)
    if report_assembly_problems(asm):
        return 1
    manifest, release_id, entries = B.build_manifest(asm.files)
    replay = current_replay(project, enrollment, reader)
    previous_id = replay.active if replay else None
    try:
        targets = resolve_targets(project, a, asm, enrollment, reader)
    except Refused:
        targets = []
    params = request_params_for(project, a, asm, entries, release_id, policy, targets, previous_id)
    lines, items = diff_lines(project, asm, entries, params, previous_id)
    say("carrydown release diff (reads your working files; writes nothing)")
    say(f"release id of the working files: {release_id}")
    say("active request: " + (previous_id if previous_id else "none"))
    for line in lines:
        say(line)
    return 0


def contains_release_id(files, release_id):
    needle = release_id.encode("ascii")
    return sorted(p for p, data in files.items() if needle in data)


def same_scope(old_request, release_id, params, exceptions):
    """True when an existing request approves this very content for this very scope."""
    t = old_request["receipt_template"]
    old = {"audience": t["audience"], "destinations": t["destinations"], "targets": t["targets"], "sources": t["sources"],
           "downstream": t["downstream"], "offline_grace_days": t["offline_grace_days"], "expires_at": t["expires_at"],
           "policy_sha256": old_request["policy_sha256"]}
    return old_request["release_id"] == release_id and scope_digest(old, old_request["detector_exceptions"]) == scope_digest(params, exceptions)


def cmd_prepare(a):
    project = Project(a.root)
    say("carrydown release prepare  " + ("APPLY" if a.apply else "DRY RUN (nothing will be written)"))
    policy, enrollment, reader = current_policy(project, a)
    asm = build_assembly(project, a, enrollment)
    if report_assembly_problems(asm):
        return 1
    manifest, release_id, entries = B.build_manifest(asm.files)
    bad = contains_release_id(asm.files, release_id)
    if bad:
        refuse("sha256-mismatch", f"{len(bad)} snapshot file(s) contain the release id, which would make it depend on itself")
    replay = current_replay(project, enrollment, reader)
    previous_id = replay.active if replay else None
    targets = resolve_targets(project, a, asm, enrollment, reader)
    params = request_params_for(project, a, asm, entries, release_id, policy, targets, previous_id)
    exceptions = used_exceptions(asm)
    scope = scope_digest(params, exceptions)
    if previous_id and project.workspace is not None and not getattr(a, "new_request", False):
        try:
            if same_scope(load_request(project.workspace, previous_id), release_id, params, exceptions):
                say(f"This content and scope are already approved and active as request {previous_id}. Nothing to prepare. "
                    "Use --new-request to start a new approval anyway.")
                return 0
        except (Refused, RS.SchemaError):
            pass
    ws = project.workspace
    record_path = (Path(ws) / "candidate" / "record.json") if ws is not None else None
    saved = None
    if record_path is not None and record_path.is_file():
        try:
            saved = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = None
    created = created_text(a)
    nonce = getattr(a, "nonce", None)
    if nonce is not None and not re.fullmatch(r"[0-9a-f]{32}", nonce):
        L.die("--nonce must be 32 lowercase hexadecimal characters")
    reused = False
    if nonce is None and not getattr(a, "new_request", False) and saved and saved.get("release_id") == release_id and saved.get("scope_sha256") == scope:
        nonce, created, reused = saved["request_nonce"], saved["created"], True
    if nonce is None:
        nonce = B.new_nonce()
    supersedes = previous_id
    preview = build_preview(project, asm, params, entries, previous_id)
    template = B.build_template(release_id, entries, created=created, expires_at=params["expires_at"], audience=params["audience"],
                                destinations=params["destinations"], targets=targets, sources=asm.sources, downstream=params["downstream"],
                                offline_grace_days=params["offline_grace_days"], enrollment_id=policy.enrollment_id)
    request = B.build_request(template, release_id, policy, created=created, nonce=nonce, supersedes=supersedes, preview=preview,
                              exceptions=exceptions)
    rid = request["request_sha256"]
    # a request that is already active needs nothing; a terminal one is never reused
    state = replay.requests.get(rid) if replay else None
    if state is not None and state.state == "active":
        say(f"This request is already approved and active: {rid}")
        return 0
    if state is not None and state.state in RS.TERMINAL_STATES and not getattr(a, "nonce", None):
        nonce = B.new_nonce()
        request = B.build_request(template, release_id, policy, created=created, nonce=nonce, supersedes=supersedes, preview=preview,
                                  exceptions=exceptions)
        rid, reused = request["request_sha256"], False
        say("The saved request was already used and ended, so this is a new approval with a fresh nonce.")
    say("")
    say(f"release id (content): {release_id}")
    say(f"request id (permission): {rid}" + ("  (the saved candidate was reused, so retrying changes nothing)" if reused else ""))
    say("The release id names these exact bytes. The request id names one permission decision over them: this audience, these")
    say("destinations, these targets and these downstream uses. The same content can have several requests, and approving one")
    say("never approves another.")
    say(f"{len(asm.files)} file(s) in the snapshot; audience {params['audience']}; destinations {', '.join(params['destinations'])}.")
    if supersedes:
        say(f"This request replaces the active request {supersedes}. The replacement is one reviewed batch.")
    if not a.apply:
        say("")
        say("Dry run: nothing was written. Add --apply to build the snapshot and the request.")
        if saved is None or not reused:
            say("The request id above is final only when you run --apply: a dry run does not keep its nonce.")
        return 0
    ws = project.need_workspace()
    release_dir = ws / "releases" / release_id
    if release_dir.is_dir():
        # reuse: every byte must match, a mismatch is a hard error and never an overwrite
        _, _, existing = load_release(ws, release_id)
        if existing != asm.files:
            refuse("sha256-mismatch", "a snapshot with this release id exists but differs from the files just built")
    else:
        pending = ws / "candidate" / "pending"
        if pending.exists():
            shutil.rmtree(pending)
        for path, data in sorted(asm.files.items()):
            workspace_put(project, f"candidate/pending/snapshot/{path}", data)
        workspace_put(project, "candidate/pending/content-manifest.json", manifest)
        on_disk_manifest, on_disk_id = RS.hash_manifest(str(pending / "snapshot"))
        if on_disk_manifest != manifest or on_disk_id != release_id:
            shutil.rmtree(pending)
            refuse("sha256-mismatch", "the files on disk do not hash to the manifest that was computed")
        (ws / "releases").mkdir(parents=True, exist_ok=True)
        os.replace(str(pending), str(release_dir))
    req_path = ws / "requests" / rid / "approval-request.json"
    if req_path.is_file():
        if req_path.read_bytes() != RS.canonical_json(request):
            refuse("approval-scope-mismatch", "a request with this id exists but differs")
    else:
        workspace_put(project, f"requests/{rid}/approval-request.json", RS.canonical_json(request))
    record = {"release_id": release_id, "scope_sha256": scope, "request_nonce": nonce, "created": created}
    workspace_put(project, "candidate/record.json", (json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))
    say(f"Prepared. Next: python3 {Path(__file__).resolve()} approve --root . --request {rid} "
        + ("--github --apply" if project.mode == "no" else "--local --apply"))
    return 0


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------

def confirm_preview(a, request):
    """The disclosure line (D6). The preview is printed from the request. In a terminal the owner types
    yes. An agent passes --preview-shown after it showed the preview and the owner agreed."""
    print_preview(request["preview"], header="carrydown release preview for the request " + request["request_sha256"])
    if getattr(a, "preview_shown", False):
        return True
    if sys.stdin is not None and sys.stdin.isatty():
        say("")
        answer = input("These exact outputs may be shared as described above. Type yes to approve: ").strip().lower()
        return answer == "yes"
    say("")
    refuse("not-approved", "the preview was not shown to you in this run and there is no terminal to ask. Show the preview "
                           "(run this command without --apply), ask for the disclosure approval, then pass --preview-shown")


def cmd_approve(a):
    modes = [bool(a.local), bool(a.github), bool(a.signed_tag)]
    if sum(modes) != 1:
        L.die("choose one of --local, --github")
    if a.signed_tag:
        refuse("approval-mechanism-unsupported", "signed-tag approval is not available in version 1. Nothing was uploaded. Use --github")
    project = Project(a.root)
    ws = project.need_workspace()
    request = load_request(ws, a.request)
    manifest, entries, files = load_release(ws, request["release_id"])
    if a.local:
        return approve_local(a, project, ws, request)
    return approve_github(a, project, ws, request, entries, files, manifest)


def approve_local(a, project, ws, request):
    rid = request["request_sha256"]
    if project.enrolled or project.mode != "yes":
        refuse("unauthenticated-release", "local approval is for projects whose readers may see everything. This project needs --github")
    policy = V.local_policy(project.released_handling(), project.repository)
    if (request["policy_sha256"], request["enrollment_id"]) != (policy.policy_sha256, policy.enrollment_id):
        refuse("policy-revision-mismatch", "the handling policy changed after this request was prepared. Prepare again")
    replay = V.local_replay(str(ws)).replay
    state = replay.requests.get(rid)
    if state is not None and state.state == "active":
        say(f"This request is already approved and active: {rid}")
        return 0
    if state is not None:
        refuse(state.state, f"this request already ended ({state.state}). A new approval needs a new request: prepare again")
    if request["supersedes_request_id"] != replay.active:
        if replay.active is not None and request["supersedes_request_id"] is None:
            refuse("mixed-release", "another request is active and this one does not replace it. Prepare again")
        refuse("state-history-invalid", "the active request changed since this request was prepared. Prepare again")
    say("carrydown release approve --local  " + ("APPLY" if a.apply else "DRY RUN (nothing will be written)"))
    if a.apply:
        if not confirm_preview(a, request):
            refuse("not-approved", "the disclosure was not approved")
    else:
        print_preview(request["preview"], header="carrydown release preview for the request " + rid)
    created = created_text(a)
    event = B.activation_event(request, policy, replay.tip, created=created, nonce=B.derived_nonce(request["request_nonce"], "activation"))
    if not a.apply:
        say("")
        say(f"Dry run: nothing was written. With --apply this records your approval (evidence: local owner, not authenticated) and the activation event {event['event_id']}.")
        return 0
    name, email = identity(project)
    approval = {"type": "local-owner", "authenticated": False, "request_sha256": rid, "content_manifest_sha256": request["release_id"],
                "approved_at": created, "git_identity": {"name": name, "email": email}, "event_id": event["event_id"]}
    workspace_put(project, f"events/{event['event_id']}.json", RS.canonical_json(event))
    workspace_put(project, f"requests/{rid}/approval.json", RS.canonical_json(approval))
    write_state_cache(project, V.local_replay(str(ws)).replay)
    say(f"Approved locally. The request {rid} is active. This approval is labeled not authenticated.")
    say(f"Next: python3 {Path(__file__).resolve()} export --root . --request {rid} --apply")
    return 0


def pull_request_for(reader, repo_id, branch):
    base = reader.repository(repo_id)["default_branch"]
    rows = [p for p in reader.pull_requests(repo_id, base, "all") if (p.get("head") or {}).get("ref") == branch]
    return rows[0] if rows else None


def candidate_event(project, ws, request, enrollment, tip, created):
    """The activation batch for staging. It is saved, so a retry uploads the same batch and the same
    event id, and reused while the staging tip it names is still the tip."""
    rid = request["request_sha256"]
    path = ws / "requests" / rid / "activation-candidate.json"
    if path.is_file():
        try:
            saved = RS.loads_strict(path.read_bytes())
            RS.validate_event(saved)
            if all(t["previous_event_id"] == tip for t in saved["transitions"]) and saved["policy_sha256"] == enrollment.policy_sha256:
                return saved
        except RS.SchemaError:
            pass
    event = B.activation_event(request, enrollment, tip, created=created, nonce=B.derived_nonce(request["request_nonce"], "activation"))
    workspace_put(project, f"requests/{rid}/activation-candidate.json", RS.canonical_json(event))
    return event


def clone_and_push(project, remote, branch, base_branch, files, message):
    """Push branch to remote with the given files, on top of base_branch. Returns "pushed" or "exists" when
    the branch is already there with exactly these files. A branch that exists with other content is
    refused, never overwritten. The owner's own git credentials are used; no token is in the URL."""
    work = Path(tempfile.mkdtemp(prefix="carrydown-stage-"))
    try:
        listing = git(["ls-remote", remote, f"refs/heads/{branch}"], work, check=False, timeout=120)
        if listing.returncode != 0:
            refuse("evidence-unavailable", "the staging repository cannot be reached with your git credentials")
        clone = work / "clone"
        git(["clone", "--quiet", "--branch", base_branch, remote, str(clone)], work, timeout=300)
        name, email = identity(project)
        if listing.stdout.strip():
            git(["fetch", "--quiet", "origin", f"refs/heads/{branch}:refs/remotes/origin/{branch}"], clone, timeout=300)
            changed = set(git(["diff", "--name-only", f"origin/{base_branch}...origin/{branch}"], clone).stdout.split())
            if changed != set(files) or not all(_same_bytes(clone, branch, path, data) for path, data in files.items()):
                refuse("approval-scope-mismatch", "the staging repository already has a different candidate on that branch. Nothing was changed")
            return "exists"
        git(["checkout", "--quiet", "-b", branch], clone)
        for path, data in sorted(files.items()):
            target = clone / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        git(["add", "--"] + sorted(files), clone)
        cfg = []
        if name and email:
            cfg = ["-c", f"user.name={name}", "-c", f"user.email={email}"]
        git(cfg + ["commit", "--quiet", "-m", message], clone)
        git(["push", "--quiet", "origin", f"refs/heads/{branch}:refs/heads/{branch}"], clone, timeout=300)
        return "pushed"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _same_bytes(clone, branch, path, data):
    run = subprocess.run(["git", "show", f"origin/{branch}:{path}"], cwd=str(clone), capture_output=True, timeout=60)
    return run.returncode == 0 and run.stdout == data


def approve_github(a, project, ws, request, entries, files, manifest):
    rid = request["request_sha256"]
    if not project.enrolled:
        refuse("policy-pointer-mismatch", "this project is not enrolled, so there is no staging repository to approve in. "
                                          "Use --local if everyone who can read the repository may see the documents")
    reader = make_reader(a)
    policy, enrollment, reader = current_policy(project, a, reader)
    say("carrydown release approve --github  " + ("APPLY" if a.apply else "DRY RUN (nothing will be written or uploaded)"))
    comps = V.verify_prerequisites(reader, enrollment, workspace_access=workspace_ok(ws))
    for c in comps:
        if c.name in V.UPLOAD_COMPONENTS:
            say(f"  {c.status:<14} {c.name}: {c.evidence}")
    V.require(comps, V.UPLOAD_COMPONENTS)
    history = V.replay_staging(reader, enrollment)
    state = history.replay.requests.get(rid)
    if state is not None and state.state == "active":
        say(f"This request is already approved and active in staging: {rid}")
        return 0
    if state is not None:
        refuse(state.state, f"this request already ended ({state.state}). A new approval needs a new request: prepare again")
    if request["supersedes_request_id"] != history.replay.active:
        refuse("state-history-invalid", "the active request changed since this request was prepared. Prepare again")
    if (request["policy_sha256"], request["enrollment_id"]) != (enrollment.policy_sha256, enrollment.enrollment_id):
        refuse("policy-revision-mismatch", "the policy changed after this request was prepared. Prepare again")
    created = created_text(a)
    staging = enrollment.entry["staging_repository"]
    staging_id = enrollment.entry["staging_repository_id"]
    base = reader.repository(staging_id)["default_branch"]
    branch = f"request/{rid}"
    if a.apply:
        event = candidate_event(project, ws, request, enrollment, history.replay.tip, created)
    else:
        event = B.activation_event(request, enrollment, history.replay.tip, created=created, nonce=B.derived_nonce(request["request_nonce"], "activation"))
    upload = B.request_branch_files(request, manifest, files, event)
    say(f"Branch {branch} would carry {len(files)} snapshot file(s), the manifest, the request and the activation event {event['event_id']}. "
        "No original, staffing file or approval record is included.")
    if not a.apply:
        say("")
        say("Dry run: nothing was uploaded. Carrydown writes to a private GitHub repository only after you allow it; add --apply when you do.")
        return 0
    remote = staging_remote_url(staging, enrollment.host, like=engineering_remote(project))
    outcome = clone_and_push(project, remote, branch, base, upload, f"Release request {rid}")
    say(f"Candidate {'uploaded' if outcome == 'pushed' else 'already on'} branch {branch}.")
    dispatch_request_workflow(a, staging, base)
    deadline = V.clock() + getattr(a, "poll_seconds", POLL_SECONDS)
    while True:
        pr = pull_request_for(reader, staging_id, branch)
        if pr:
            say(f"The staging workflow opened pull request #{pr['number']}. Review its final revision in GitHub and approve it only if you mean to approve "
                f"exactly this content for exactly this audience, then merge it. After the merge run: python3 {Path(__file__).resolve()} export --root . --request {rid} --apply")
            return 0
        if V.clock() >= deadline:
            break
        sleep(POLL_INTERVAL)
    say("candidate uploaded; approval request pending")
    say("It is not approved, and you do not need to upload again. When the workflow has opened the pull request, run the same command again: "
        f"python3 {Path(__file__).resolve()} approve --root . --request {rid} --github --apply")
    return 0


def engineering_remote(project):
    try:
        import workspace as W
        return W.engineering_remote(project.root)
    except Exception:
        return ""


def workspace_ok(ws):
    try:
        import workspace as W
        return W.permission_problem(ws) is None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Evidence for export and publication
# ---------------------------------------------------------------------------

class Evidence:
    """What export and publication verified: the record of one request, the replayed state, the policy,
    the resolved targets, the context and the receipts it permits."""

    def __init__(self, project, record, history, policy, enrollment, reader, targets, ctx, receipts, files, entries, manifest):
        self.project, self.record, self.history, self.policy = project, record, history, policy
        self.enrollment, self.reader, self.targets, self.ctx = enrollment, reader, targets, ctx
        self.receipts, self.files, self.entries, self.manifest = receipts, files, entries, manifest
        self.skill_prefix = None

    @property
    def request(self):
        return self.record.request

    @property
    def rid(self):
        return self.record.request_id


def published_receipts(directory):
    """{request id: parsed receipt} for the valid receipts already in docs/release of a folder."""
    out = {}
    folder = Path(directory) / PUBLIC_RECEIPT_DIR
    if folder.is_dir():
        for p in sorted(folder.glob("*.receipt.json")):
            try:
                r = RS.validate_receipt(p.read_bytes())
            except (RS.SchemaError, OSError):
                continue
            if p.name == f"{r['request_id']}.receipt.json":
                out[r["request_id"]] = r
    return out


def load_record(project, a, rid, enrollment, reader):
    if enrollment is not None:
        return V.verify_request(rid, reader, enrollment)
    ws = project.need_workspace()
    return V.verify_local_request(V.load_local_evidence(str(ws), rid), rid)


def local_or_staging_history(project, enrollment, reader):
    if enrollment is not None:
        return V.replay_staging(reader, enrollment)
    return V.local_replay(str(project.need_workspace()))


def receipt_for(record, replay):
    st = replay.requests.get(record.request_id)
    if st is None:
        refuse("not-approved", "the request has no authenticated state")
    return RS.project_receipt(record.request, record.manifest_bytes, st, record.approval)


def gather(project, a, rid, *, content, check_existing=None):
    """Verify everything the export order of D15 asks for, in order, and return an Evidence. content is
    True for an export (authorize_content, an active request) and False for a state export
    (authorize_state_receipt, a terminal one). check_existing is a folder whose published receipts are
    regenerated when their state changed."""
    ws = project.need_workspace()
    policy, enrollment, reader = current_policy(project, a)
    if enrollment is not None:
        comps = V.verify_prerequisites(reader, enrollment, workspace_access=workspace_ok(ws))
        V.require(comps, V.EXPORT_COMPONENTS)
    record = load_record(project, a, rid, enrollment, reader)
    history = local_or_staging_history(project, enrollment, reader)
    replay = history.replay
    receipts = {}
    targets = None
    if check_existing is not None:
        for old_id, old in published_receipts(check_existing).items():
            if old_id == rid:
                continue
            st = replay.requests.get(old_id)
            if st is not None and st.state != old["state"] and st.state in RS.RECEIPT_STATES:
                try:
                    old_record = load_record(project, a, old_id, enrollment, reader)
                except (RS.SchemaError, Refused):
                    say(f"note: the receipt of {old_id} is out of date but its approval record is not available here, so it was left alone")
                    continue
                receipts[f"{PUBLIC_RECEIPT_DIR}/{old_id}.receipt.json"] = receipt_for(old_record, replay)
    own_path = f"{PUBLIC_RECEIPT_DIR}/{rid}.receipt.json"
    own = receipt_for(record, replay)
    receipts[own_path] = own
    digests = {p: RS.sha256_bytes(b) for p, b in receipts.items()}
    template = record.request["receipt_template"]
    if content:
        if enrollment is not None:
            targets = V.verify_targets(reader, policy, template["targets"], template["audience"])
        else:
            targets = None
        ctx = V.authorize_content(record, replay, policy, targets, receipts=digests)
    else:
        ctx = V.authorize_state_receipt(record, replay, policy, {own_path: digests[own_path]})
        receipts = {own_path: own}
    manifest, entries, files = load_release_or_rebuild(project, ws, record, reader, enrollment)
    return Evidence(project, record, history, policy, enrollment, reader, targets, ctx, receipts, files, entries, manifest)


def load_release_or_rebuild(project, ws, record, reader, enrollment):
    """The local snapshot, verified against the approved manifest. A missing snapshot is rebuilt from the
    verified staging objects on the "no" path; a snapshot that differs is a hard error."""
    folder = Path(ws) / "releases" / record.release_id
    if not folder.is_dir() and enrollment is not None:
        for path, data in sorted(V.fetch_snapshot(reader, enrollment, record).items()):
            workspace_put(project, f"releases/{record.release_id}/snapshot/{path}", data)
        workspace_put(project, f"releases/{record.release_id}/content-manifest.json", record.manifest_bytes)
    manifest, entries, files = load_release(ws, record.release_id)
    if manifest != record.manifest_bytes:
        refuse("sha256-mismatch", "the manifest in the workspace differs from the approved manifest")
    return manifest, entries, files


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def plan_projection_matches(root, rel, snapshot_bytes):
    """True when the working docs/spec/plan.yaml is the owner's draft of the released plan in the snapshot."""
    path = Path(root) / rel
    try:
        plan, _ = L.load_plan(path, root)
        return RS.sha256_bytes(L.released_plan_bytes(plan)) == RS.sha256_bytes(snapshot_bytes)
    except (L.PlanError, L.PlanViewError, OSError):
        return False


def export_plan(ev, root, previous):
    """[(repository path, bytes, mode)] to write and notes. previous maps path to the sha256 of the
    previous active release, so a file that still holds the previous approved bytes counts as an update."""
    out = []
    for e in ev.entries:
        if not e["path"].startswith("repo/"):
            continue
        rel = e["path"][len("repo/"):]
        out.append((rel, ev.files[e["path"]], e["mode"]))
    return out


def check_conflicts(ev, root, items, previous, spec_plan_rel):
    """Paths whose working file differs from the snapshot and is not the previous approved bytes."""
    conflicts = []
    for rel, data, _ in items:
        target = Path(root) / rel
        if not os.path.lexists(target):
            continue
        if os.path.islink(target) or not target.is_file():
            conflicts.append(rel)
            continue
        have = target.read_bytes()
        if have == data:
            continue
        if rel == spec_plan_rel and plan_projection_matches(root, rel, data):
            continue
        if previous.get("repo/" + rel) == RS.sha256_bytes(have):
            continue
        conflicts.append(rel)
    return conflicts


def write_file(root, rel, data, mode, ev, write_class, destination):
    """Gate, then write one file under root. Refuses a destination that passes through a symbolic link."""
    sha = RS.sha256_bytes(data)
    RG.require(write_class, rel, sha, destination, ev.project.root, request_id=ev.rid, verified_context=ev.ctx)
    target = Path(root) / rel
    parent = target.parent
    base = Path(os.path.realpath(str(root)))
    probe = parent
    while not os.path.lexists(probe):
        probe = probe.parent
    if base not in (Path(os.path.realpath(str(probe))), *Path(os.path.realpath(str(probe))).parents):
        refuse("unsafe-artifact-path", "a destination folder passes through a symbolic link outside the repository")
    parent.mkdir(parents=True, exist_ok=True)
    if os.path.islink(target):
        refuse("unsafe-artifact-path", "a destination file is a symbolic link")
    target.write_bytes(data)
    os.chmod(str(target), 0o755 if mode == "100755" else 0o644)


def dest_for(ev, rel):
    """engineers-skill for a file in the engineers' skill folder, else engineering-repo."""
    prefix = ev.skill_prefix
    if prefix and rel.startswith(prefix + "/") and "engineers-skill" in ev.request["receipt_template"]["destinations"]:
        return "engineers-skill"
    return "engineering-repo"


def cmd_export(a):
    project = Project(a.root)
    rid = a.request
    say("carrydown release export  " + ("APPLY" if a.apply else "DRY RUN (nothing will be written)"))
    root = project.root
    ev = gather(project, a, rid, content=True, check_existing=root if project.mode == "yes" else None)
    spec_plan = f"repo/{project.state.spec_dir}/plan.yaml"
    try:
        released = L.loads(ev.files[spec_plan].decode("utf-8"))
        ev.skill_prefix = (released.get("project") or {}).get("dev_skill_path")
    except (KeyError, L.YamlError, UnicodeDecodeError):
        ev.skill_prefix = None
    previous = {}
    if ev.request["supersedes_request_id"]:
        previous, _ = previous_files(project, ev.request["supersedes_request_id"])
    items = export_plan(ev, root, previous)
    say(f"request {rid}  release {ev.record.release_id}")
    say(f"{len(items)} approved repository file(s), {len(ev.receipts)} receipt(s). Evidence: "
        + ("local owner approval, not authenticated" if ev.record.approval.type == "local-owner" else "authenticated review on the final head"))
    if project.mode == "yes":
        return export_yes(a, project, ev, items, previous, f"{project.state.spec_dir}/plan.yaml")
    return export_no(a, project, ev, items)


def export_yes(a, project, ev, items, previous, plan_rel):
    root = project.root
    conflicts = check_conflicts(ev, root, items, previous, plan_rel)
    if conflicts:
        for rel in conflicts[:30]:
            say(f"  differs: {rel}")
        refuse("working-copy-differs", "working copy differs from released snapshot; run release.py preview to see what changed, then prepare")
    writes, keep = [], []
    for rel, data, mode in items:
        target = root / rel
        if target.is_file() and target.read_bytes() == data:
            continue
        if rel == plan_rel and target.is_file() and plan_projection_matches(root, rel, data):
            keep.append(rel)
            continue
        writes.append((rel, data, mode))
    for rel in keep:
        say(f"  {rel}: your working plan is the draft of the released plan, so it is left in place")
    receipts = {p: b for p, b in ev.receipts.items() if not (root / p).is_file() or (root / p).read_bytes() != b}
    say(f"{len(writes)} file(s) and {len(receipts)} receipt(s) would be written; {len(items) - len(writes) - len(keep)} already match.")
    if not a.apply:
        for rel, _, _ in writes[:30]:
            say(f"  would write: {rel}")
        say("")
        say("Dry run: nothing was written. Add --apply.")
        return 0
    for rel, data, mode in writes:
        write_file(root, rel, data, mode, ev, "release", dest_for(ev, rel))
    for rel, data in sorted(receipts.items()):
        write_file(root, rel, data, "100644", ev, "release", "engineering-repo")
    say(f"Exported {len(writes)} file(s) and {len(receipts)} receipt(s) into your working tree. Review them with git status, then commit and push as you usually do.")
    return 0


def export_no(a, project, ev, items):
    root = project.root
    name, email = identity(project)
    if not (name and email):
        refuse("workspace-unavailable", "git has no user.name and user.email for this repository. The export commits as you, so set them first")
    branch = f"carrydown/request-{ev.rid}"
    base = default_branch(project)
    ws = project.need_workspace()
    if not a.apply:
        say(f"Would create an isolated worktree on {branch} from origin/{base}, copy {len(items)} file(s) and {len(ev.receipts)} receipt(s), and commit as {name}.")
        say("Dry run: nothing was written. Add --apply.")
        return 0
    git(["fetch", "--quiet", "origin", base], root, timeout=300)
    wt = ws / "exports" / ev.rid
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)         # left behind by an export that stopped part way
    git(["worktree", "prune"], root, check=False)
    exists = git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root, check=False)
    if exists.returncode == 0:
        tip = git(["rev-parse", f"refs/heads/{branch}"], root, check=False).stdout.strip()
        base_tip = git(["rev-parse", f"refs/remotes/origin/{base}"], root, check=False).stdout.strip()
        if tip and tip == base_tip:
            # an earlier export created the branch and stopped before committing: it holds nothing, so it is redone
            git(["branch", "-D", branch], root, check=False)
            exists = git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root, check=False)
    if exists.returncode == 0:
        expected = {rel: data for rel, data, _ in items}
        expected.update(ev.receipts)
        for rel, data in expected.items():
            shown = subprocess.run(["git", "show", f"{branch}:{rel}"], cwd=str(root), capture_output=True, timeout=60)
            if shown.returncode != 0 or shown.stdout != data:
                refuse("approval-scope-mismatch", f"a branch named {branch} exists with different content. Nothing was changed")
        say(f"The branch {branch} already holds this export. Nothing to do.")
        print_next_commands(project, branch, base, ev)
        return 0
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    wt.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "--quiet", "-b", branch, str(wt), f"origin/{base}"], root, timeout=300)
    try:
        published = published_receipts(wt)
        written = []
        for rel, data, mode in items:
            write_file(wt, rel, data, mode, ev, "release", dest_for(ev, rel))
            written.append(rel)
        # receipts: the active one, and any published predecessor whose state changed
        receipts = dict(ev.receipts)
        for old_id, old in published.items():
            path = f"{PUBLIC_RECEIPT_DIR}/{old_id}.receipt.json"
            st = ev.history.replay.requests.get(old_id)
            if old_id != ev.rid and st is not None and st.state != old["state"] and path not in receipts:
                old_record = load_record(project, a, old_id, ev.enrollment, ev.reader)
                receipts[path] = receipt_for(old_record, ev.history.replay)
        if set(receipts) - set(ev.receipts):
            digests = {p: RS.sha256_bytes(b) for p, b in receipts.items()}
            ev.ctx = V.authorize_content(ev.record, ev.history.replay, ev.policy, ev.targets, receipts=digests)
        for rel, data in sorted(receipts.items()):
            write_file(wt, rel, data, "100644", ev, "release", "engineering-repo")
            written.append(rel)
        git(["add", "--"] + sorted(written), wt)
        git(["-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "--quiet", "-m",
             f"Release {ev.rid[:12]}: approved context for {len(items)} file(s)\n\nExported from the approved request {ev.rid}."], wt)
    finally:
        git(["worktree", "remove", "--force", str(wt)], root, check=False)
    write_workspace_evidence(project, ev)
    say(f"Committed {len(written)} file(s) on {branch} as {name}. Your own working tree was not touched.")
    print_next_commands(project, branch, base, ev)
    return 0


def print_next_commands(project, branch, base, ev):
    say("Carrydown does not push or open a pull request for you; each is a separate write that needs your say-so. When you allow it:")
    say(f"  git -C {project.root} push -u origin {branch}")
    say(f"  gh pr create --base {base} --head {branch} --title \"Release {ev.rid[:12]}\" --body \"Approved context. Request {ev.rid}.\"")


def write_workspace_evidence(project, ev):
    """After a verified export on the "no" path: the workspace's own record of the approval (D10 item 4).
    It is evidence for the owner, never a trust source: every later command reads the API again."""
    ws = project.need_workspace()
    rid = ev.rid
    info = ev.record.review
    approval = {"type": "github-review", "authenticated": True, "request_sha256": rid, "content_manifest_sha256": ev.record.release_id,
                "event_id": ev.record.event["event_id"], "staging_repository_id": ev.enrollment.entry["staging_repository_id"],
                "pull_request": info.pr_number, "review_id": info.review_id, "reviewer_id": info.reviewer_id,
                "head_sha": info.head_sha, "merge_sha": info.merge_sha, "approved_at": info.approved_at}
    workspace_put(project, f"requests/{rid}/approval.json", RS.canonical_json(approval))
    for batch in ev.history.events:
        workspace_put(project, f"events/{batch['event_id']}.json", RS.canonical_json(batch))
    write_state_cache(project, ev.history.replay, ev.history.tip)


# ---------------------------------------------------------------------------
# export-state and withdraw
# ---------------------------------------------------------------------------

def cmd_export_state(a):
    project = Project(a.root)
    rid = a.request
    say("carrydown release export-state  " + ("APPLY" if a.apply else "DRY RUN (nothing will be written)"))
    root = project.root
    ev = gather(project, a, rid, content=False)
    own_path = f"{PUBLIC_RECEIPT_DIR}/{rid}.receipt.json"
    state = ev.history.replay.requests[rid].state
    say(f"request {rid} is {state}. Only its receipt will be rewritten; no spec, bundle, payload or other file.")
    if project.mode == "yes":
        target = root / own_path
        if not target.is_file():
            say("This request's receipt is not in the working tree, so there is nothing to publish.")
            return 0
        if target.read_bytes() == ev.receipts[own_path]:
            say("The receipt already shows this state.")
            return 0
        if not a.apply:
            say("Dry run: nothing was written. Add --apply.")
            return 0
        write_file(root, own_path, ev.receipts[own_path], "100644", ev, "state-only", "engineering-repo")
        say(f"Rewrote {own_path}. Commit it as you usually do.")
        return 0
    name, email = identity(project)
    if not (name and email):
        refuse("workspace-unavailable", "git has no user.name and user.email for this repository. The export commits as you, so set them first")
    base = default_branch(project)
    git(["fetch", "--quiet", "origin", base], root, timeout=300)
    shown = subprocess.run(["git", "show", f"origin/{base}:{own_path}"], cwd=str(root), capture_output=True, timeout=60)
    if shown.returncode != 0:
        say("No receipt of this request is published in the engineering repository, so there is nothing to update.")
        return 0
    if shown.stdout == ev.receipts[own_path]:
        say("The published receipt already shows this state.")
        return 0
    branch = f"carrydown/state-{rid}"
    if not a.apply:
        say(f"Would commit the regenerated receipt on {branch} from origin/{base}.")
        say("Dry run: nothing was written. Add --apply.")
        return 0
    ws = project.need_workspace()
    wt = ws / "exports" / ("state-" + rid)
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    if git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root, check=False).returncode == 0:
        existing = subprocess.run(["git", "show", f"{branch}:{own_path}"], cwd=str(root), capture_output=True, timeout=60)
        if existing.stdout != ev.receipts[own_path]:
            refuse("approval-scope-mismatch", f"a branch named {branch} exists with different content. Nothing was changed")
        say(f"The branch {branch} already holds this receipt. Nothing to do.")
        print_next_commands(project, branch, base, ev)
        return 0
    wt.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "--quiet", "-b", branch, str(wt), f"origin/{base}"], root, timeout=300)
    try:
        write_file(wt, own_path, ev.receipts[own_path], "100644", ev, "state-only", "engineering-repo")
        git(["add", "--", own_path], wt)
        git(["-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "--quiet", "-m",
             f"Report that request {rid[:12]} is {state}"], wt)
    finally:
        git(["worktree", "remove", "--force", str(wt)], root, check=False)
    write_workspace_evidence(project, ev)
    say(f"Committed the receipt on {branch} as {name}. Engineers learn of this only after it reaches the default branch they fetch.")
    print_next_commands(project, branch, base, ev)
    return 0


def cmd_withdraw(a):
    project = Project(a.root)
    ws = project.need_workspace()
    say("carrydown release withdraw  " + ("APPLY" if a.apply else "DRY RUN (nothing will be written)"))
    if a.reason not in B.WITHDRAW_REASONS:
        L.die("--reason must be one of: " + ", ".join(B.WITHDRAW_REASONS))
    rid = a.request
    request = load_request(ws, rid)
    policy, enrollment, reader = current_policy(project, a)
    history = local_or_staging_history(project, enrollment, reader)
    st = history.replay.requests.get(rid)
    if st is None or st.state != "active":
        refuse(st.state if st else "not-approved", "only an active request can be withdrawn")
    created = created_text(a)
    nonce = B.derived_nonce(request["request_nonce"], "withdraw-" + a.reason)
    event = B.withdrawal_event(rid, policy, history.replay.tip, a.reason, created=created, nonce=nonce)
    say(f"Withdrawing {rid} ({a.reason}) is the event {event['event_id']}. Content publication of this request stops once it is recorded; "
        "engineers learn of it only after the receipt update reaches their default branch.")
    if enrollment is None:
        if not a.apply:
            say("Dry run: nothing was written. Add --apply to record the withdrawal.")
            return 0
        workspace_put(project, f"events/{event['event_id']}.json", RS.canonical_json(event))
        write_state_cache(project, V.local_replay(str(ws)).replay)
        say(f"Withdrawn. Run export-state --request {rid} --apply to prepare the receipt update.")
        return 0
    comps = V.verify_prerequisites(reader, enrollment, workspace_access=workspace_ok(ws))
    V.require(comps, V.UPLOAD_COMPONENTS)
    staging = enrollment.entry["staging_repository"]
    staging_id = enrollment.entry["staging_repository_id"]
    base = reader.repository(staging_id)["default_branch"]
    branch = f"state/{event['event_id']}"
    say(f"Branch {branch} would carry only the event batch.")
    if not a.apply:
        say("Dry run: nothing was uploaded. Add --apply.")
        return 0
    workspace_put(project, f"requests/{rid}/withdrawal-candidate.json", RS.canonical_json(event))
    remote = staging_remote_url(staging, enrollment.host, like=engineering_remote(project))
    outcome = clone_and_push(project, remote, branch, base, B.state_branch_files(event), f"State change {event['event_id']}")
    say(f"Candidate {'uploaded' if outcome == 'pushed' else 'already on'} branch {branch}.")
    dispatch_request_workflow(a, staging, base)
    deadline = V.clock() + getattr(a, "poll_seconds", POLL_SECONDS)
    while True:
        pr = pull_request_for(reader, staging_id, branch)
        if pr:
            say(f"The staging workflow opened pull request #{pr['number']}. Review and approve it in GitHub, merge it, then run export-state --request {rid} --apply.")
            return 0
        if V.clock() >= deadline:
            break
        sleep(POLL_INTERVAL)
    say("candidate uploaded; approval request pending")
    say(f"Run the same command again when the workflow has opened the pull request: python3 {Path(__file__).resolve()} withdraw --root . --request {rid} --reason {a.reason} --apply")
    return 0


# ---------------------------------------------------------------------------
# inventory, doctor
# ---------------------------------------------------------------------------

def cmd_inventory(a):
    for line in RI.inventory(L.project_root(a.root)):
        say(line)
    return 0


def doctor_components(project, a, reader=None):
    """(components, problem). The live components of an enrolled project, read with the owner's token:
    release_verify.verify_prerequisites plus the destinations. problem is a fixed reason code when the
    enrollment itself could not be read, and components is then empty."""
    try:
        policy, enrollment, reader = current_policy(project, a, reader)
        components = V.verify_prerequisites(reader, enrollment, workspace_access=workspace_ok(project.workspace) if project.workspace else None)
        components.append(V.verify_destinations(reader, enrollment))
        return components, None
    except (RS.SchemaError, Refused) as e:
        return [], getattr(e, "code", "evidence-unavailable")


def cmd_doctor(a):
    """The setup check (WP7 item 7): the offline workspace checks, then the live components. On the "no"
    path every mandatory component must be verified before a private upload or a release write, and the
    exit status is 1 until they are. On the "yes" path the remote checks are informational."""
    project = Project(a.root)
    import workspace as W
    say("carrydown release doctor")
    say("offline checks (nothing is sent):")
    rows = W.doctor_rows(project.root)
    for level, name, detail in rows:
        say(f"  {level:<4}  {name}: {detail}")
    failed = sum(1 for r in rows if r[0] == "FAIL")
    say("")
    say("remote components (live):")
    if not project.enrolled:
        say("  not enrolled: no tooling repository, staging repository or verifier applies to this project. The \"yes\" path needs none, and these checks are informational.")
        return 1 if failed else 0
    if not token_available(a):
        components, problem = [], "no token"
        for name in V.EXPORT_COMPONENTS:
            if name != "workspace-access":
                say(f"  {'not verifiable':<14}  {name}: no token. Set CARRYDOWN_GITHUB_TOKEN or pass --token-file")
    else:
        components, problem = doctor_components(project, a)
        if problem:
            say(f"  {'not verifiable':<14}  enrollment: {problem}")
        for c in components:
            say(f"  {c.status:<14}  {c.name}: {c.evidence}")
            if c.status != V.VERIFIED:
                hint = V.ATTESTATION_FOR.get(c.name)
                say(f"  {'':<14}  needed: {c.code}" + (f". A current administrator attestation named {hint} for this exact subject also satisfies it" if hint else ""))
    by = {c.name: c for c in components}
    upload = [n for n in V.UPLOAD_COMPONENTS if not (n in by and by[n].status == V.VERIFIED)]
    export = [n for n in V.EXPORT_COMPONENTS if not (n in by and by[n].status == V.VERIFIED)]
    say("")
    say("private upload to the staging repository: " + ("allowed" if not upload else "blocked until verified: " + ", ".join(upload)))
    say("export and publication: " + ("allowed" if not export else "blocked until verified: " + ", ".join(export)))
    say("Limits: a verified scan health does not expire an old GitHub success, and state can change between a scheduled poll and a merge. "
        "Five minutes is a requested interval, not a deadline.")
    return 1 if failed or export else 0


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def add_common(p):
    p.add_argument("--root", default=".", help="the engineering repository (default: current directory)")
    p.add_argument("--token-file", help="file that holds the GitHub token (the \"no\" path, and API lookups)")


def add_shape(p):
    p.add_argument("--audience", choices=RS.AUDIENCES, help="who the release is approved for (default: repo-readers)")
    p.add_argument("--destinations", help="comma separated destinations to include (default: every destination the project has)")
    p.add_argument("--no-github", action="store_true", help="leave out every GitHub payload: only the repository files and the engineers' skill")
    p.add_argument("--exceptions", metavar="FILE", help="JSON list of detector exceptions to apply (copied passages and organization phrases only)")
    p.add_argument("--assignees", choices=("yes", "no"), help="publish assignee logins (default: the plan's downstream setting)")
    p.add_argument("--capacity-summary", choices=("yes", "no"), help="publish people by track in the Epic comment")
    p.add_argument("--evidence", choices=RS.EVIDENCE, help="what evidence may hold: synthetic-only or approved")
    p.add_argument("--expires", metavar="ISO-8601-UTC", help="the approval expires at this UTC time, such as 2027-06-30T00:00:00Z")
    p.add_argument("--repository-id", type=int, help="numeric id of the engineering repository, when no token can look it up")
    p.add_argument("--board-owner-id", type=int, help="numeric id of the board's owner")
    p.add_argument("--board-project-id", help="node id of the board project (PVT_...)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preview", help="the four-question preview and the changes since the last release. Writes nothing")
    add_common(p)
    add_shape(p)
    p = sub.add_parser("prepare", help="build the snapshot, the manifest and the approval request (dry run unless --apply)")
    add_common(p)
    add_shape(p)
    p.add_argument("--apply", action="store_true", help="write the snapshot and the request into the private workspace")
    p.add_argument("--new-request", action="store_true", help="start a new approval with a fresh nonce even for unchanged content and scope")
    p.add_argument("--created", metavar="ISO-8601-UTC", help="test and reproduction aid: the UTC time of the request, such as 2027-01-20T14:03:00Z")
    p.add_argument("--nonce", metavar="HEX32", help="test and reproduction aid: the request nonce, 32 lowercase hexadecimal characters")
    p = sub.add_parser("approve", help="approve a prepared request: --local for the \"yes\" path, --github for the \"no\" path")
    add_common(p)
    p.add_argument("--request", required=True, help="the request id that prepare printed")
    p.add_argument("--local", action="store_true", help="record your own approval (evidence: local owner, not authenticated)")
    p.add_argument("--github", action="store_true", help="upload the candidate to the private staging repository and wait for the request")
    p.add_argument("--signed-tag", action="store_true", help="not available in version 1; refuses before uploading anything")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--preview-shown", action="store_true", help="the preview was shown to the owner, who answered the disclosure line. For an agent that has no terminal")
    p.add_argument("--created", metavar="ISO-8601-UTC", help="test and reproduction aid: the UTC time of the approval")
    p.add_argument("--poll-seconds", type=int, default=POLL_SECONDS, help=f"how long to wait for the staging workflow's pull request (default {POLL_SECONDS})")
    p = sub.add_parser("export", help="copy the approved files and the receipt into the engineering repository")
    add_common(p)
    p.add_argument("--request", required=True)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("export-state", help="write only the regenerated receipt of a superseded or withdrawn request")
    add_common(p)
    p.add_argument("--request", required=True)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("withdraw", help="prepare the terminal event that ends an active request")
    add_common(p)
    p.add_argument("--request", required=True)
    p.add_argument("--reason", required=True, help="one of: " + ", ".join(B.WITHDRAW_REASONS))
    p.add_argument("--apply", action="store_true")
    p.add_argument("--created", metavar="ISO-8601-UTC")
    p.add_argument("--poll-seconds", type=int, default=POLL_SECONDS)
    p = sub.add_parser("diff", help="what changed since the active release, and which work items it touches. Writes nothing")
    add_common(p)
    add_shape(p)
    p = sub.add_parser("inventory", help="what a legacy project tracks and has in git history. Writes nothing")
    add_common(p)
    p = sub.add_parser("doctor", help="the offline workspace checks, and the live checks when a token is set")
    add_common(p)
    a = ap.parse_args(argv)
    commands = {"preview": cmd_preview, "prepare": cmd_prepare, "approve": cmd_approve, "export": cmd_export,
                "export-state": cmd_export_state, "withdraw": cmd_withdraw, "diff": cmd_diff, "inventory": cmd_inventory,
                "doctor": cmd_doctor}
    try:
        return commands[a.command](a)
    except Refused as e:
        print(f"{e.code}: {e.text}", file=sys.stderr)
        return 1
    except RS.SchemaError as e:
        print(f"{e.code}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
