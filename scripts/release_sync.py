#!/usr/bin/env python3
"""Publish the GitHub payloads of an approved release. Network code: it ships only with the
carrydown-plan-to-github skill. Standard library only.

github_sync.py, github_project.py and github_repair.py call open_publication() before they write
anything for a project that has a handling policy. It verifies, through the API where the project is
enrolled and through the private workspace where it is not, that exactly one request is active, that
its approval verifies, that it has not expired and that every destination is the one approved. It
returns a Publication that

  * holds the payloads of the snapshot, never the working files (specification D4);
  * hands out a VerifiedContext no older than half a minute, re-verifying when it is older, and asks
    the release gate before every mutation through guard();
  * keeps the publication journal (D5): for each target, started and completed, the GitHub id, the
    payload digest, the digest of the managed state read back after the write, and the requests
    that wrote the same target before.

If the request is withdrawn, superseded, expired, under another policy or has no approval, opening
the publication refuses with the fixed reason code and nothing has been written.

publication_preflight() is the check every publishing command runs before its first write, and
github_sync.py --preflight runs on its own (specification WP8). It resolves the approved targets by
numeric identity, and refuses a release for repository readers on a public destination and a board
that more accounts can read than the repository. No flag overrides it.

This module is imported by the other scripts. Run with --help to see this text.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402
import release as R  # noqa: E402
import release_gate as RG  # noqa: E402
import release_github as RGH  # noqa: E402
import release_payloads as RP  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402

CONTEXT_REFRESH_SECONDS = 30      # the gate accepts a context for 60; this one is renewed before half of that is gone
JOURNAL_FORMAT = 1


class PublicationRefused(Exception):
    """Publication stops with a fixed reason code and one line. Nothing printed holds a value from the data."""

    def __init__(self, code, text):
        super().__init__(text)
        self.code, self.text = code, text

    def line(self):
        return f"{self.code}: {self.text}"


def managed_digest(state):
    return RS.sha256_bytes(RS.canonical_json(state))


class Journal:
    """publication/<request id>.journal.json: what has been published for this request, for resume."""

    def __init__(self, project, request_id, release_id, repository_id):
        self.project, self.rid, self.release_id, self.repository_id = project, request_id, release_id, repository_id
        self.rel = f"publication/{request_id}.journal.json"
        self.path = Path(project.workspace) / self.rel
        self.targets = {}
        self.visibility = {}      # target id -> "public" or "private" as last seen by a publishing run
        if self.path.is_file():
            data = RS.loads_strict(self.path.read_bytes())
            if data.get("journal_format") != JOURNAL_FORMAT or data.get("request_id") != request_id:
                raise PublicationRefused("state-history-invalid", "the publication journal belongs to another request")
            if data.get("repository_id") not in (None, repository_id):
                raise PublicationRefused("target-identity-mismatch", "the journal names another repository id than the approved one")
            self.targets = data.get("targets", {})
            self.visibility = data.get("visibility") if isinstance(data.get("visibility"), dict) else {}

    def others(self):
        out = {}
        folder = self.path.parent
        for p in sorted(folder.glob("*.journal.json")):
            if p.name == self.path.name:
                continue
            try:
                data = RS.loads_strict(p.read_bytes())
            except RS.SchemaError:
                continue
            for key, entry in (data.get("targets") or {}).items():
                out.setdefault(key, []).append(entry)
        return out

    def save(self):
        doc = {"journal_format": JOURNAL_FORMAT, "request_id": self.rid, "release_id": self.release_id,
               "repository_id": self.repository_id, "targets": self.targets}
        if self.visibility:
            doc["visibility"] = self.visibility
        R.workspace_put(self.project, self.rel, RS.canonical_json(doc))

    def record_visibility(self, visibility):
        """Keep what the preflight of this run saw, so --verify can report a change."""
        if dict(visibility) != self.visibility:
            self.visibility = dict(visibility)
            self.save()

    def get(self, key):
        return self.targets.get(key)

    def start(self, key, **fields):
        entry = self.targets.setdefault(key, {})
        if entry.get("state") != "completed":
            entry["state"] = "started"
        entry.update(fields)
        entry["request_id"], entry["release_id"] = self.rid, self.release_id
        entry.setdefault("history", [])
        if not entry["history"]:
            for prior in self.others().get(key, []):
                entry["history"].append({"request_id": prior.get("request_id"), "release_id": prior.get("release_id"),
                                         "payload_sha256": prior.get("payload_sha256")})
        self.save()

    def complete(self, key, payload_sha256, managed_state_sha256):
        entry = self.targets[key]
        entry.update({"state": "completed", "payload_sha256": payload_sha256, "managed_state_sha256": managed_state_sha256})
        self.save()


class Publication:
    """An approved release opened for publication. See the module text."""

    def __init__(self, project, args, gh, request_id=None):
        self.project, self.args, self.gh = project, args, gh
        self.root = project.root
        self.reader = RGH.GitHubEvidenceReader(gh)
        self.asked_for = request_id
        self._ctx = None
        self._ctx_at = 0.0
        self.verify()
        self.journal = Journal(project, self.rid, self.release_id, self.repository_id)

    # --- verification ---
    def verify(self):
        project, a = self.project, self.args
        try:
            policy, enrollment, reader = R.current_policy(project, a, self.reader)
            history = R.local_or_staging_history(project, enrollment, self.reader)
            replay = history.replay
            rid = self.asked_for or replay.active
            if getattr(self, "journal", None) is not None and rid != self.journal.rid:
                raise PublicationRefused("mixed-release", "the active request changed while publishing")
            if rid is None:
                ended = [st for st in replay.requests.values() if st.state in RS.TERMINAL_STATES]
                if ended:
                    last = max(ended, key=lambda st: list(replay.requests).index(st.request_id))
                    raise PublicationRefused(last.state, f"the latest request ended ({last.state}), so nothing may be published")
                raise PublicationRefused("not-approved", "there is no active approved request. Prepare and approve a release first")
            if enrollment is not None:
                comps = V.verify_prerequisites(self.reader, enrollment, workspace_access=R.workspace_ok(project.workspace))
                V.require(comps, V.EXPORT_COMPONENTS)
            record = R.load_record(project, a, rid, enrollment, self.reader)
            ws = project.need_workspace()
            manifest, entries, files = R.load_release_or_rebuild(project, ws, record, self.reader, enrollment)
            template = record.request["receipt_template"]
            targets = V.verify_targets(self.reader, policy, template["targets"], template["audience"])
            ctx = V.authorize_content(record, replay, policy, targets)
        except (RS.SchemaError, R.Refused) as e:
            raise PublicationRefused(getattr(e, "code", "evidence-unavailable"), str(getattr(e, "text", None) or e))
        self.policy, self.enrollment, self.record, self.history = policy, enrollment, record, history
        self.rid, self.release_id, self.entries, self.files = rid, record.release_id, entries, files
        self.targets_resolved = targets
        self._ctx, self._ctx_at = ctx, V.clock()
        eng = targets.get("engineering")
        self.repository_id = eng.identity["repository_id"] if eng else None
        self.host = eng.identity["host"] if eng else "github.com"
        self.repository = eng.identity["repository"] if eng else None
        if getattr(self, "payloads", None) is None:
            self._load_payloads()

    def _load_payloads(self):
        self.payloads = {}
        for e in self.entries:
            path = e["path"]
            if path.startswith("payloads/"):
                payload = RP.load_payload(self.files[path])
                tgt = payload["target"]
                self.payloads[(tgt["kind"], tgt["key"])] = (path, payload, e["sha256"])
        spec_dir = self.project.state.spec_dir
        plan_bytes = self.files.get(f"repo/{spec_dir}/plan.yaml")
        self.released_plan_text = plan_bytes.decode("utf-8") if plan_bytes else None
        self.plan = None
        if self.released_plan_text is not None:
            plan, problems = L.plan_from_data(L.loads(self.released_plan_text), "released plan", None, "released")
            self.plan = plan
        self.branch = self.plan["project"]["branch"] if self.plan else "main"

    # --- the gate ---
    def context(self):
        if self._ctx is None or V.clock() - self._ctx_at > CONTEXT_REFRESH_SECONDS:
            self.verify()
        return self._ctx

    def payload(self, kind, key):
        found = self.payloads.get((kind, key))
        if found is None:
            raise PublicationRefused("destination-not-allowed", f"{kind} {key} is not a target of this release")
        return found

    def guard(self, kind, key):
        """Ask the gate before one mutation of target (kind, key). Returns the payload dict."""
        path, payload, sha = self.payload(kind, key)
        ctx = self.context()
        decision = RG.check("release", path, sha, payload["destination_id"], self.root, request_id=self.rid, verified_context=ctx)
        if not decision.allowed:
            raise PublicationRefused(decision.code, f"the release gate refused the write of {kind} {key}. Nothing more was written")
        return payload

    def urls(self, payload):
        return RP.urls_for(payload, self.host, self.repository, self.branch)

    def text_for(self, payload, numbers):
        """The body that may be sent for a payload: the permitted substitutions and nothing else."""
        spec_url, skill_url = self.urls(payload)
        return RP.substitute(payload["body"], numbers, spec_url, skill_url)

    def check_sent(self, payload, numbers, sent_managed_body):
        """A body about to be sent must be exactly the payload with the permitted substitutions."""
        if sent_managed_body.strip() != self.text_for(payload, numbers).strip() and sent_managed_body.strip() != self.text_for(payload, {}).strip():
            raise PublicationRefused("unapproved-substitution", "the text about to be sent differs from the approved payload")


def open_publication(root, args, gh, request_id=None):
    """Open the active approved release of the project for publication, or raise PublicationRefused.
    Returns None for a project with no handling policy (legacy), which publishes as it always did."""
    project = R.Project(root)
    if RG._is_legacy(project.state):
        return None
    if project.workspace is None:
        raise PublicationRefused(project.why or "workspace-unavailable", "there is no private workspace, so no approved release can be found. "
                                                                     "Create it with workspace.py init, then prepare and approve a release")
    return Publication(project, args, gh, request_id)


# ---------------------------------------------------------------------------
# Publication preflight (specification WP8, item 2)
# ---------------------------------------------------------------------------

class Preflight(NamedTuple):
    lines: tuple          # what to print, one visibility line per target
    visibility: dict      # target id -> "public" or "private" as seen now
    targets: dict         # target id -> release_verify.ResolvedTarget


def _try(fn, *args):
    """(value, None), or (None, reason) when the fact cannot be read completely."""
    try:
        return fn(*args), None
    except V.EvidenceUnavailable as e:
        return None, e.detail or "unavailable"


def _attested(entry, component, subject):
    """True when a current administrator attestation covers this component and every key of subject (D9).
    The author must be an administrator of the enrollment and the dates must be valid now. A key the
    attestation does not carry, or carries with another value, means it does not cover this subject, so a
    changed visibility, a changed link between board and repository or a changed reader set ends it."""
    admins = {a["id"] for a in entry.get("administrators") or []}
    now = V.clock()
    for att in entry.get("attestations") or []:
        if not isinstance(att, dict) or att.get("component") != component or att.get("by_id") not in admins:
            continue
        try:
            at, expires = V.to_epoch(att.get("at"), "at"), V.to_epoch(att.get("expires_at"), "expires_at")
        except RS.SchemaError:
            continue
        subj = att.get("subject")
        if isinstance(subj, dict) and all(subj.get(k) == v for k, v in subject.items()) and at <= now < expires:
            return True
    return False


def _visibility_name(public):
    return "public" if public else "private"


def board_subject(target, repository_ids, repo_reader_ids, public):
    """What a destination-readers attestation must carry to cover the board as it is now."""
    subject = {"project_id": target["project_id"], "owner_id": target["owner_id"], "repository_id": target["repository_id"],
               "public": bool(public), "repository_ids": sorted(repository_ids)}
    if repo_reader_ids is not None:
        subject["repository_reader_ids"] = sorted(repo_reader_ids)
    return subject


def _board_line(reader, policy, target, resolved, audience):
    """The visibility line of a board, or PublicationRefused. For a repository-readers release the board's
    readers must be a subset of the repository's. When the board's readers cannot be listed, an enrolled
    project needs a current destination-readers attestation (subject: board, link and reader set), and a
    project that is not enrolled has no administrator to supply one, so it proceeds and says so."""
    shown = f"board {target['project_id']}"
    if audience == "public":
        return f"visibility: {shown} {_visibility_name(resolved.public)} (a public release: no reader check)"
    proj, why = _try(reader.project, target["project_id"])
    if proj is None:
        raise PublicationRefused("destination-access-not-verified", "the board cannot be read again, so its readers cannot be checked")
    people, people_why = _try(reader.collaborators, target["repository_id"])
    readers = proj.get("reader_ids")
    if readers is not None and people is not None:
        extra = set(readers) - {x["id"] for x in people}
        if extra:
            raise PublicationRefused("audience-visibility-mismatch", f"the board can be read by {len(extra)} account(s) that cannot read the repository")
        return f"visibility: {shown} {_visibility_name(resolved.public)}; {len(readers)} reader(s), all of them readers of the repository"
    if people is None and readers is not None:
        why = "the repository's readers cannot be listed"
    reason = "the board's readers cannot be listed" if readers is None else why
    if getattr(policy, "enrolled", False):
        subject = board_subject(target, proj.get("repository_ids") or [], [x["id"] for x in people] if people is not None else None, proj.get("public"))
        if _attested(policy.entry, "destination-readers", subject):
            return f"visibility: {shown} {_visibility_name(resolved.public)}; readers not listed, covered by a current destination-readers attestation"
        raise PublicationRefused("destination-access-not-verified", f"{reason} and no current destination-readers attestation covers the board as it is now")
    return (f"visibility: {shown} {_visibility_name(resolved.public)}; readers not listed ({reason}). This project has no administrator "
            "attestation, so the board's readers are the ones you approved by naming it in the request")


def publication_preflight(gh, plan, enrollment, request, reader=None, resolved=None):
    """The check every publishing command runs before its first write. It reads and writes nothing.

    gh          the GitHub client (used only to build the evidence reader when none is given)
    plan        the released plan, or None
    enrollment  the Enrollment, or the LocalPolicy of a project that is not enrolled (release_verify)
    request     the approval request, whose receipt_template names the audience and the targets
    reader      an EvidenceReader; a test supplies a fake
    resolved    verify_targets output from a moment ago, to avoid reading it twice

    It resolves every approved target by numeric identity (host, repository id, and for a board the owner
    id, the node id and the link to the repository), then refuses
      * a repository-readers release to a public repository or board (audience-visibility-mismatch);
      * a board that more accounts can read than the repository, even when both are private
        (audience-visibility-mismatch), and a board whose readers cannot be listed and that no current
        destination-readers attestation covers (destination-access-not-verified);
      * a repository or board whose identity is not the approved one (target-identity-mismatch).
    A public release proceeds at its approved identities, whatever the visibility of the sources. There is
    no flag to override any of this. Returns a Preflight, or raises PublicationRefused."""
    template = request["receipt_template"]
    audience, wanted = template["audience"], template["targets"]
    reader = reader or RGH.GitHubEvidenceReader(gh)
    try:
        targets = resolved if resolved is not None else V.verify_targets(reader, enrollment, wanted, audience)
        lines, visibility = [], {}
        for t in wanted:
            r = targets[t["id"]]
            visibility[t["id"]] = _visibility_name(r.public)
            if "project_id" in t:
                lines.append(_board_line(reader, enrollment, t, r, audience))
            else:
                lines.append(f"visibility: {t['repository']} {_visibility_name(r.public)} (numeric id {t['repository_id']})"
                             + (", a public release" if audience == "public" and r.public else ""))
    except (RS.SchemaError, R.Refused) as e:
        raise PublicationRefused(getattr(e, "code", "evidence-unavailable"), str(getattr(e, "text", None) or e))
    return Preflight(tuple(lines), visibility, targets)


def preflight_for(pub):
    """The preflight of an opened Publication: its targets were resolved a moment ago, so they are reused.
    Prints nothing; the caller prints the lines."""
    return publication_preflight(pub.gh, pub.plan, pub.policy, pub.record.request, reader=pub.reader, resolved=pub.targets_resolved)


def visibility_report(recorded, current):
    """(lines, changed) comparing the visibility recorded at publication with what the targets show now."""
    lines, changed = [], False
    for name in sorted(current):
        before = (recorded or {}).get(name)
        if before is None:
            lines.append(f"  visibility of {name}: {current[name]} (no earlier record)")
        elif before != current[name]:
            changed = True
            lines.append(f"  visibility of {name} CHANGED since publication: was {before}, now {current[name]}. Reassess the release before anything more is published")
        else:
            lines.append(f"  visibility of {name}: {current[name]} (unchanged since publication)")
    return lines, changed


def legacy_visibility(gh, base):
    """(visibility, line) of a repository for a project that has no release policy. A project with no
    policy has no approved audience to compare with, so the line is information, not a refusal."""
    status, js = gh.rest_status("GET", base)
    if status != 200 or not isinstance(js, dict):
        return None, None
    vis = "public" if js.get("private") is False else "private"
    return vis, f"visibility: {base[len('/repos/'):]} {vis}" + (". This project has no release policy, so no audience was checked" if vis == "public" else "")


# ---------------------------------------------------------------------------
# Managed state read back from GitHub, and its digest
# ---------------------------------------------------------------------------

def issue_state(managed_content, gh, base, payload, issue):
    wanted_labels = {x.casefold() for x in payload.get("labels", [])}
    wanted_assignees = {x.casefold() for x in payload.get("assignees", [])}
    status, parent = gh.rest_status("GET", f"{base}/issues/{issue['number']}/parent")
    return {"title": issue["title"], "body": managed_content(issue.get("body")),
            "labels": sorted(x["name"].casefold() for x in issue.get("labels", []) if x["name"].casefold() in wanted_labels),
            "assignees": sorted(x["login"].casefold() for x in issue.get("assignees", []) if x["login"].casefold() in wanted_assignees),
            "parent": parent.get("number") if status == 200 else None}


def board_state(existing, placements, plan):
    """The board's managed state as read back: for each plan key the project item's field values."""
    out = {}
    for issue, kind, ms, it, _title in placements:
        key = L.tag(plan, it["id"]) if it else (f"M{ms['number']}" if ms else "EPIC")
        row = existing.get(issue["number"])
        out[key] = dict(sorted((row or {"values": {}})["values"].items()))
    return out


def check_patch(pub, key, live, patch):
    """A metadata repair of an issue may set only values the approved payload lists: its title, and logins
    that are already assigned or listed in the payload. Anything else is deny(unapproved-substitution)."""
    kind = kind_of(key)
    payload = pub.payload(kind, key)[1]
    if "title" in patch and patch["title"] != payload["title"]:
        raise PublicationRefused("unapproved-substitution", f"the title of {key} would differ from the approved payload")
    if "assignees" in patch:
        allowed = {x.casefold() for x in payload.get("assignees", [])} | {x["login"].casefold() for x in live.get("assignees", [])}
        if any(x.casefold() not in allowed for x in patch["assignees"]):
            raise PublicationRefused("unapproved-substitution", f"an assignee of {key} is not in the approved payload")
    if "labels" in patch:
        allowed = {x.casefold() for x in payload.get("labels", [])} | {x["name"].casefold() for x in live.get("labels", [])}
        if any(x.casefold() not in allowed for x in patch["labels"]):
            raise PublicationRefused("unapproved-substitution", f"a label of {key} is not in the approved payload")


def kind_of(key):
    if key == "EPIC":
        return "epic"
    return "subepic" if re.fullmatch(r"M\d+", key) else "issue"


def _number_to_key(pub, sync, number):
    for k, n in (sync.numbers if sync else {}).items():
        if n == number:
            return k
    for jkey, entry in pub.journal.targets.items():
        if entry.get("number") == number and jkey.split("/", 1)[0] in ("issue", "subepic", "epic"):
            return jkey.split("/", 1)[1]
    return None


def _id_to_key(pub, sync, github_id):
    for k, n in (sync.ids if sync else {}).items():
        if n == github_id:
            return k
    for jkey, entry in pub.journal.targets.items():
        if entry.get("github_id") == github_id and jkey.split("/", 1)[0] in ("issue", "subepic", "epic"):
            return jkey.split("/", 1)[1]
    return None


def target_of_write(pub, sync, method, path, data):
    """The (kind, key) target a GitHub write belongs to, from the request alone. A write that belongs to
    no target of the release is refused: there are no helper writes outside the manifest."""
    data = data if isinstance(data, dict) else {}
    if path == "/graphql":
        return "board", "project"
    m = re.match(r"^/repos/[^/]+/[^/]+(/.*)$", path)
    sub = m.group(1) if m else ""
    if sub == "/labels":
        return "label", str(data.get("name"))
    if sub == "/issues":
        found = RP.MARKER_RE.findall(data.get("body") or "")
        if len(set(found)) != 1:
            raise PublicationRefused("destination-not-allowed", "an issue without exactly one plan marker cannot be created")
        return kind_of(found[0]), found[0]
    mm = re.fullmatch(r"/issues/(\d+)", sub)
    if mm:
        key = _number_to_key(pub, sync, int(mm.group(1)))
        if key:
            return kind_of(key), key
    mm = re.fullmatch(r"/issues/(\d+)/sub_issues", sub)
    if mm:
        key = _id_to_key(pub, sync, data.get("sub_issue_id"))
        if key:
            return kind_of(key), key
    if re.fullmatch(r"/issues/\d+/comments", sub) or re.fullmatch(r"/issues/comments/\d+", sub):
        return "epic-comment", "rollup"
    raise PublicationRefused("destination-not-allowed", "a GitHub write does not belong to any target of the approved release")


def install_guard(gh, root, pub=None, sync=None):
    """Make every write of the client ask the release gate first. With a Publication the write is mapped to
    its target and checked against the approved payload. Without one (a legacy project) the gate answers
    legacy and the write goes ahead as it always did, but it is still asked."""
    if pub is None:
        def legacy(method, path, data=None):
            RG.require("release", f"github:{method} {path.split('?')[0]}", RS.sha256_text(f"{method} {path}"), "engineering", root)
        gh.write_guard = legacy
        return

    def guarded(method, path, data=None):
        kind, key = target_of_write(pub, sync, method, path, data)
        pub.guard(kind, key)
    gh.write_guard = guarded


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Open an approved release for publication and keep its journal. A library: import it, do not run it. "
                    "github_sync.py, github_project.py and github_repair.py use it.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
