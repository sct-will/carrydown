#!/usr/bin/env python3
"""Check that the approved inputs of one work item can be used, then say so or stop.

Run it from the repository, before you read anything for a work item:
  python3 check_context.py WI-03

It prints a short block and exits 0 when the inputs are ready to read. Otherwise it prints one of six
messages and exits with the code beside it:
  10  carrydown: no approved context for <ID>
  11  carrydown: the approved context for <ID> is stale
  12  carrydown: <ID> cites an obligation that is not in its approved context
  13  carrydown: <ID> has a restricted destination that this project does not publish
  14  carrydown: the specification for <ID> does not match its approved release
  15  carrydown: the approved inputs for <ID> come from more than one release
A line `warning: freshness not confirmed; within offline grace` means the inputs passed but the
default branch could not be reached. The message never holds withheld text, a heading of a
restricted source, a private path or the name of an approver.

What it checks, in this order
  1. Local validity, offline. docs/context/<id>.md and <id>.bundle.json exist, the Markdown
     matches content_sha256 in the sidecar, every source section the specification cites is an
     obligation of the bundle, and a receipt in docs/release/ marked active lists both files with
     matching digests.
  2. The approved inputs, offline. ONE active receipt must also list, with matching digests, the
     unique specification file of the item (<id>-*.md under the specification folder), the released
     plan, the specification folder README, the generated skill's SKILL.md and README.md, and the
     specification of every other work item that the specification names under "Integration points"
     or "References" (the whole shared file, which is the conservative reading). Files that match
     different receipts, or two active receipts that each cover a different part, are exit 15. Two
     active receipts that list this item and disagree on any of these files are exit 15 too, even when
     your files match one of them: only one release can be in force. A missing, ambiguous, unlisted or
     changed file is exit 14.
     A specification may differ from its approved bytes only by the decision overlay, and only where the
     project lets engineers record decisions: new dated entries under "Decisions recorded", with every
     earlier entry unchanged. The approved bytes are read from git history, and only a version whose
     sha256 matches the receipt counts. If git holds none, the specification is unverified (exit 14).
     In a project that takes changes as requests, any change to an approved specification is exit 14.
  3. Freshness. `git fetch origin <default branch>`, then the receipts of the fetched commit are
     read. The inputs are fresh only when an active receipt there lists every file with the same
     digests. A receipt that is superseded or withdrawn, here or there, makes them stale: an older
     active receipt never replaces a newer terminal one. After a good fetch the check records the
     repository, the fetched commit, the request id and the time in .carrydown/cache/last-refresh
     (untracked), and, for this item, the digest of every approved input and of the decision overlay.
  4. Offline grace. If the fetch fails, the check proceeds only when that record matches this
     repository and this request, is not dated in the future, and is no older than the receipt's
     offline_grace_days. With no valid record, or past the grace period, it is stale with the
     reason "could not refresh". Nothing is assumed about a release the clone has not seen.
  5. Expiry. The receipt's expires_at is compared with this computer's clock.
  6. The approved delta. After a good fetch the check compares the approved inputs with the ones it
     recorded at your last check for this item. When any changed it prints a block that starts
     `carrydown: approved inputs changed since your last check for <ID>`: which files changed and the
     changed passages of the Markdown files, read from git history by digest. It ends by telling you to
     reassess your implementation plan. If git holds no copy of the previous version it says so.
     The check never pulls, merges or changes a file of your working tree.

What this script is and is not. It lives in the engineer's checkout, so the engineer can edit it. It
is a convenience and an integrity check for the engineer. It is not a security control. The controls
are the release gate on the owner's side and the independent verifier on pull requests. It reads only
this repository, never a token, and its one network use is a `git fetch` with the credentials you
already have. It cannot recall text you already copied.

The decision overlay code below, between the two marker comments, is a copy of scripts/decision_overlay.py in
the carrydown repository. The generated skill ships this file alone, so the copy is here. The copy must stay
source-identical: tests/test_decision_overlay.py parses both files and fails when they differ. The independent
verifier imports the original, so the engineer's check, the verifier and the skill text agree on one rule.

Options
  --root DIR      the repository (default: the top of the git repository you are in)
  --no-refresh    do not fetch; follow the offline grace rule

Exit status is 0, 10, 11, 12, 13, 14 or 15 as above, 2 for a wrong argument, and 3 when the Python that
runs it is older than 3.9. Neither 2 nor 3 prints a line that starts with "carrydown:".
"""
import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional

ID_PREFIX = "WI"
SPEC_DIR = "docs/spec"
SKILL_PATH = "docs/dev/skills/expense-approvals-dev"
ENGINEER_EDITS = "allowed"

CONTEXT_DIR = "docs/context"
RELEASE_DIR = "docs/release"
CACHE_FILE = ".carrydown/cache/last-refresh"
FETCH_TIMEOUT = 60
MAX_BYTES = 4 * 1024 * 1024
MAX_RECEIPTS = 500
STATES = ("active", "superseded", "withdrawn")

KINDS = {
    "missing": (10, "carrydown: no approved context for {id}", "Ask the plan owner to release the item."),
    "stale": (11, "carrydown: the approved context for {id} is stale", "Ask the plan owner to re-release, or connect and refresh."),
    "cites": (12, "carrydown: {id} cites an obligation that is not in its approved context", "Ask the plan owner. Do not guess the rule."),
    "restricted": (13, "carrydown: {id} has a restricted destination that this project does not publish", "Follow the owner's approved instruction."),
    "spec": (14, "carrydown: the specification for {id} does not match its approved release",
             "Restore the approved file, or ask the plan owner. If a rule looks wrong, draft a Rule clarification request. Do not edit an approved specification outside what this project allows."),
    "mixed": (15, "carrydown: the approved inputs for {id} come from more than one release",
              "Pull the default branch so every approved file comes from one release, then run the check again. If it persists, ask the plan owner."),
}

REASSESS = "Reassess your implementation plan against the current approved inputs before you write more code. Do not continue on the old plan."
DELTA_HEADLINE = "carrydown: approved inputs changed since your last check for {id}"
NO_PREVIOUS = "previous version unavailable locally; load the current approved inputs"
DELTA_LINES = 60
DELTA_TOTAL = 160

# --- begin shared overlay code: keep identical to the copy in templates/dev-skill/scripts/check_context.py ---
OVERLAY_HEADING = b"## Decisions recorded"
OVERLAY_PLACEHOLDER = b"None yet."
OVERLAY_POLICIES = ("allowed", "request-only")
_OVERLAY_ANY_HEADING = re.compile(rb"#{1,6}[ \t]+Decisions[ \t]+recorded[ \t]*#*[ \t]*\Z", re.I)
_OVERLAY_TOP_HEADING = re.compile(rb"#{1,2}[ \t]")
_OVERLAY_FENCE = re.compile(rb"[ \t]{0,3}(```|~~~)")
_OVERLAY_ENTRY = re.compile(rb"- (\d{4})-(\d{2})-(\d{2})\.(?:[ \t]|\Z)")
_OVERLAY_BULLET = re.compile(rb"(?:[-*+]|\d+[.)])[ \t]")
_OVERLAY_PR = re.compile(rb"(?:#\d+\b|/pull/\d+\b|\b(?:PR|pull request)[ \t]+#?\d+\b)", re.I)


class OverlayResult(NamedTuple):
    """ok is True for identical bytes and for a valid overlay. reason is a plain machine code. entries are
    the new entries (text), overlay_sha256 the digest of their text, None when there are none."""
    ok: bool
    reason: str
    entries: tuple
    overlay_sha256: Optional[str]


def _overlay_fail(reason):
    return OverlayResult(False, reason, (), None)


def _overlay_lines(data):
    """The lines of data with their endings. Only a line feed ends a line."""
    return re.findall(rb"[^\n]*\n|[^\n]+", data)


def _overlay_blank(line):
    return not line.strip()


def _overlay_bounds(lines):
    """(heading line index, index of the first line after the section), or None when the section boundary
    is missing, repeated, at another level or cut by an open code fence. Headings inside code fences do
    not count. The section ends at the next heading of level 1 or 2."""
    fence = None
    exact, odd, tops = [], 0, []
    for index, line in enumerate(lines):
        bare = line.rstrip(b"\r\n")
        mark = _OVERLAY_FENCE.match(bare)
        if mark:
            if fence is None:
                fence = mark.group(1)
            elif fence == mark.group(1):
                fence = None
            continue
        if fence is not None:
            continue
        if bare == OVERLAY_HEADING:
            exact.append(index)
        elif _OVERLAY_ANY_HEADING.match(bare):
            odd += 1
        if _OVERLAY_TOP_HEADING.match(bare):
            tops.append(index)
    if fence is not None or len(exact) != 1 or odd:
        return None
    start = exact[0]
    after = [i for i in tops if i > start]
    return start, (after[0] if after else len(lines))


def _overlay_split_blank(lines):
    """(lines up to the last one that holds text, the blank lines after it)."""
    end = len(lines)
    while end and _overlay_blank(lines[end - 1]):
        end -= 1
    return lines[:end], lines[end:]


def _overlay_entries(lines):
    """The new entries in lines as a list of bytes, or the reason code when the lines are not entries only."""
    entries = []
    for line in lines:
        bare = line.rstrip(b"\r\n")
        start = _OVERLAY_ENTRY.match(bare)
        if start:
            try:
                dt.date(int(start.group(1)), int(start.group(2)), int(start.group(3)))
            except ValueError:
                return "entry-undated"
            entries.append([line])
        elif not entries:
            if bare.strip():
                return "entry-undated"
        elif _OVERLAY_BULLET.match(bare):
            return "entry-undated"
        else:
            entries[-1].append(line)
    return [b"".join(parts).rstrip() for parts in entries]


def validate_overlay(approved_bytes, proposed_bytes, policy, require_pr_reference=False):
    """Judge proposed_bytes (the specification in the working tree or the pull request) against
    approved_bytes (the version a verified receipt lists) under policy, allowed or request-only. Returns an
    OverlayResult. Both arguments are bytes. Nothing is read or written."""
    try:
        approved, proposed = bytes(approved_bytes), bytes(proposed_bytes)
    except (TypeError, ValueError):
        return _overlay_fail("not-bytes")
    if policy not in OVERLAY_POLICIES:
        return _overlay_fail("policy-unknown")
    if approved == proposed:
        return OverlayResult(True, "identical", (), None)
    if policy == "request-only":
        return _overlay_fail("body-changed")
    old_lines, new_lines = _overlay_lines(approved), _overlay_lines(proposed)
    old_bounds, new_bounds = _overlay_bounds(old_lines), _overlay_bounds(new_lines)
    if old_bounds is None or new_bounds is None:
        return _overlay_fail("boundary-malformed")
    (old_start, old_end), (new_start, new_end) = old_bounds, new_bounds
    if old_lines[:old_start + 1] != new_lines[:new_start + 1] or old_lines[old_end:] != new_lines[new_end:]:
        return _overlay_fail("body-changed")
    old_core, old_blank = _overlay_split_blank(old_lines[old_start + 1:old_end])
    new_core, new_blank = _overlay_split_blank(new_lines[new_start + 1:new_end])
    lead = 0
    while lead < len(old_core) and _overlay_blank(old_core[lead]):
        lead += 1
    placeholder = len(old_core) == lead + 1 and old_core[lead].rstrip(b"\r\n") == OVERLAY_PLACEHOLDER
    if placeholder:
        if not new_core:
            return _overlay_fail("placeholder-removed")
        if new_core[:lead] != old_core[:lead]:
            return _overlay_fail("entry-edited")
        added = new_core[lead:]
        if added and added[0].rstrip(b"\r\n") == OVERLAY_PLACEHOLDER:
            return _overlay_fail("placeholder-kept" if len(added) > 1 else "body-changed")
    else:
        keep = len(old_core)
        if len(new_core) < keep:
            return _overlay_fail("entry-edited")
        if keep:
            last = old_core[-1]
            if new_core[:keep - 1] != old_core[:keep - 1] or (new_core[keep - 1] != last and new_core[keep - 1].rstrip(b"\r\n") != last):
                return _overlay_fail("entry-edited")
        added = new_core[keep:]
        if not added:
            return _overlay_fail("body-changed")
    found = _overlay_entries(added)
    if isinstance(found, str):
        return _overlay_fail(found)
    if not found:
        return _overlay_fail("entry-undated")
    if require_pr_reference and not all(_OVERLAY_PR.search(entry) for entry in found):
        return _overlay_fail("pr-reference-missing")
    try:
        entries = tuple(entry.decode("utf-8").replace("\r\n", "\n") for entry in found)
    except UnicodeDecodeError:
        return _overlay_fail("encoding-invalid")
    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return OverlayResult(True, "entries-appended", entries, digest)
# --- end shared overlay code ---


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,200}\Z")
_NUMBER = r"\d+(?:\.\d+)*"


class Block(Exception):
    """The inputs cannot be used. kind is a key of KINDS; reason is a fixed reason code; where is the
    repository path of the file at fault, if one is."""

    def __init__(self, kind, reason="", where=None):
        super().__init__(kind)
        self.kind = kind
        self.reason = reason
        self.where = where


def prefix():
    return ID_PREFIX if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", ID_PREFIX) else "WI"


def spec_dir():
    value = SPEC_DIR if re.fullmatch(r"[A-Za-z0-9_./-]+", SPEC_DIR) and ".." not in SPEC_DIR.split("/") else "docs/spec"
    return value.strip("/") or "docs/spec"


def item_number(text):
    """The item number in an id written 3, 03, WI-03, wi-3 or WI03, or None."""
    m = re.fullmatch(r"\s*(?:" + re.escape(prefix()) + r"-?)?0*([0-9]+)\s*", str(text), re.I)
    return int(m.group(1)) if m else None


def shown_id(text, number):
    """The id as printed. A readable id is normalized to the project's form; anything else is cut
    down to safe characters, so an odd argument cannot put markup or a path into the message."""
    if number is not None:
        return f"{prefix()}-{number:02d}"
    return re.sub(r"[^A-Za-z0-9._-]", "", str(text))[:40] or "(no id)"


# The second line of a stale message, in plain words, with the fixed code in brackets for the plan owner.
REASONS = {
    "superseded": "a newer release replaced this one. Pull the default branch",
    "withdrawn": "the plan owner withdrew this release",
    "expired": "the release has passed its expiry date",
    "could-not-refresh": "the default branch could not be fetched to confirm the context is current, and the offline grace period does not apply",
    "sha256-mismatch": "the default branch holds a different version of this context. Pull the default branch",
    "approval-not-found": "the default branch has no active release that lists this context",
    "spec-missing": "no specification file for this item was found. Restore it from the default branch",
    "spec-ambiguous": "more than one specification file matches this item. Keep one",
    "not-in-release": "the approved release does not list this file",
    "input-missing": "this approved file is missing or is not a plain file. Restore it from the default branch",
    "input-changed": "this approved file differs from the version the release lists. Restore it, or pull the default branch",
    "approved-copy-unavailable": "git holds no copy of the approved version to compare with, so the file is unverified. Fetch the default branch, then check again",
    "body-changed": "the specification differs from its approved text, and this project does not let engineers edit specifications",
    "entry-edited": "an earlier entry under Decisions recorded was changed or removed. Only new entries may be added",
    "entry-undated": "a new note under Decisions recorded is not a dated entry. Write it as - YYYY-MM-DD. Text",
    "placeholder-kept": "the line None yet. must be replaced by your first entry, not kept beside it",
    "placeholder-removed": "the line None yet. was removed without a new entry",
    "boundary-malformed": "the heading Decisions recorded is missing, repeated or at another level",
    "encoding-invalid": "a new note under Decisions recorded is not valid text",
    "inputs-from-different-releases": "the files you hold match different releases, so no one release covers them all",
    "two-active-releases": "two active releases list this work item and disagree. The plan owner must supersede or withdraw one of them",
}


# body-changed on a project that permits decision notes: the edit is outside the one place engineers may write.
BODY_CHANGED_ALLOWED = ("the specification differs from its approved text outside Decisions recorded. "
                        "Only new dated decision entries may be added there")


def reason_text(reason):
    """The plain words for a reason code, matched to the project's edit policy."""
    if reason == "body-changed" and edit_policy() == "allowed":
        return BODY_CHANGED_ALLOWED
    return REASONS.get(reason, reason.replace("-", " "))


def message(kind, item_id, reason="", extra=(), where=None):
    code, first, action = KINDS[kind]
    lines = [first.format(id=item_id)]
    if reason:
        lines.append(f"reason: {reason_text(reason)} ({reason})")
    if where:
        lines.append(f"file: {where}")
    lines += list(extra)
    lines.append(action)
    return code, lines


# ---------------------------------------------------------------------------
# Reading files safely
# ---------------------------------------------------------------------------

def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _no_constant(name):
    raise ValueError("non-finite number")


def parse_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_constant=_no_constant)


def read_regular(path):
    """The bytes of a regular file that is not a link, or None."""
    try:
        if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_time(text):
    if not isinstance(text, str) or not _TIME.match(text):
        return None
    try:
        return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Local validity
# ---------------------------------------------------------------------------

def load_sidecar(raw, tag):
    """The parsed sidecar, or Block when it is not a sidecar of this item."""
    try:
        side = parse_json(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Block("missing")
    if not isinstance(side, dict) or not is_int(side.get("bundle_format")) or side["bundle_format"] != 1 \
            or side.get("work_item") != tag or not isinstance(side.get("obligations"), list) \
            or not isinstance(side.get("content_sha256"), str) or not _SHA256.match(side["content_sha256"]):
        raise Block("missing")
    if "restricted_destination" in side and not isinstance(side["restricted_destination"], bool):
        raise Block("missing")
    for ob in side["obligations"]:
        if not isinstance(ob, dict) or not isinstance(ob.get("source"), str) or not isinstance(ob.get("section"), str):
            raise Block("missing")
    return side


def find_specs(root, tag):
    """The repository paths (forward slashes) of the plain files that match <id>-*.md under the
    specification folder, sorted. More than one means the specification is ambiguous."""
    base = Path(root) / spec_dir()
    try:
        files = sorted(p for p in base.rglob(f"{tag.lower()}-*.md") if p.is_file() and not p.is_symlink())[:6]
        return [p.relative_to(Path(root)).as_posix() for p in files]
    except (OSError, ValueError):
        return []


def section_body(text, name):
    """The text under the level 2 heading `## <name>`, up to the next level 2 heading, or None."""
    m = re.search(r"(?ms)^## " + re.escape(name) + r"[ \t]*\n(.*?)(?=^## |\Z)", text)
    return m.group(1) if m else None


def spec_citations(root, tag, known_sources):
    """The (source id, section) pairs the specification of the item cites in its References section.
    The form is `- <source id> section <n.n>, <heading>`. A relative link into a rendering whose file
    name is a source id of the bundle, with "section n.n" in its label, counts too."""
    found = []
    for rel in find_specs(root, tag)[:5]:
        raw = read_regular(Path(root) / rel)
        if raw is None:
            continue
        body = section_body(raw.decode("utf-8", "replace"), "References")
        if body is None:
            continue
        for line in body.split("\n"):
            new = re.match(r"^\s*[-*]\s+(\S+)\s+section\s+(" + _NUMBER + r")\b", line, re.I)
            if new:
                found.append((new.group(1), new.group(2)))
                continue
            for link in re.finditer(r"\[([^\]]*)\]\(([^)\s]+)\)", line):
                label = re.search(r"(?i)\bsections?\s+(" + _NUMBER + r")\b", link.group(1))
                stem = Path(link.group(2).split("#")[0]).stem
                if label and stem in known_sources:
                    found.append((stem, label.group(1)))
    return list(dict.fromkeys(found))


def parse_receipt(raw, name=None):
    """A receipt as a dict, or None when it is not shaped like one. This is a shape check for the
    convenience of the engineer. The verifier checks the whole schema."""
    try:
        r = parse_json(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    if not isinstance(r, dict) or not is_int(r.get("receipt_format")) or r["receipt_format"] != 1 or r.get("state") not in STATES:
        return None
    rid = r.get("request_id")
    if not isinstance(rid, str) or not _SHA256.match(rid) or (name is not None and name != rid + ".receipt.json"):
        return None
    arts = r.get("artifacts")
    if not isinstance(arts, list) or not all(isinstance(a, dict) and isinstance(a.get("path"), str)
                                             and isinstance(a.get("sha256"), str) and is_int(a.get("bytes")) for a in arts):
        return None
    if r.get("expires_at") is not None and parse_time(r["expires_at"]) is None:
        return None
    grace = r.get("offline_grace_days")
    if not is_int(grace) or grace < 0:
        return None
    if parse_time(r.get("created")) is None:
        return None
    return r


def local_receipts(root):
    out = {}
    folder = Path(root) / RELEASE_DIR
    try:
        names = sorted(p.name for p in folder.iterdir() if re.fullmatch(r"[0-9a-f]{64}\.receipt\.json", p.name))[:MAX_RECEIPTS]
    except OSError:
        return out
    for name in names:
        raw = read_regular(folder / name)
        r = parse_receipt(raw, name) if raw is not None else None
        if r is not None:
            out[r["request_id"]] = r
    return out


def lists(receipt, files):
    """True when the receipt lists every file (path -> (sha256, size)) with the same digest and length."""
    by_path = {a["path"]: a for a in receipt["artifacts"]}
    return all(p in by_path and by_path[p]["sha256"] == d and by_path[p]["bytes"] == n for p, (d, n) in files.items())


def terminal_reason(receipts):
    return "withdrawn" if any(r["state"] == "withdrawn" for r in receipts) else "superseded"


def newest(receipts):
    return sorted(receipts, key=lambda r: (r["created"], r["request_id"]))[-1]


# ---------------------------------------------------------------------------
# The approved inputs: the specification, the shared files and the decision overlay
# ---------------------------------------------------------------------------

OKAY = ("ok", "overlay")


def edit_policy():
    """allowed or request-only for the specification files, as the generated skill states it. Anything
    else, and a copy that was never filled in, is the stricter request-only."""
    return ENGINEER_EDITS if ENGINEER_EDITS in OVERLAY_POLICIES else "request-only"


def skill_dir():
    """The folder of the generated skill, or None when this copy does not know it."""
    value = SKILL_PATH if re.fullmatch(r"[A-Za-z0-9_./-]+", SKILL_PATH) and ".." not in SKILL_PATH.split("/") else ""
    return value.strip("/") or None


def neighbor_stems(text, tag):
    """The stems (wi-04) of the other work items that the specification names under "Integration points"
    or "References". The whole specification of each is a required input: the conservative reading of
    "shared contract"."""
    own = tag.lower()
    found = []
    pattern = re.compile(r"\b" + re.escape(prefix()) + r"-(\d+)\b", re.I)
    for name in ("Integration points", "References"):
        for m in pattern.finditer(section_body(text, name) or ""):
            stem = f"{prefix()}-{int(m.group(1)):02d}".lower()
            if stem != own and stem not in found:
                found.append(stem)
    return sorted(found)


def local_inputs(root, tag):
    """What this checkout holds for the item besides its context: the path of its one specification, the
    shared files every item needs, and the stems of the neighbors its specification names. Raises Block
    when the specification is missing or ambiguous."""
    found = find_specs(root, tag)
    if not found:
        raise Block("spec", "spec-missing")
    if len(found) > 1:
        raise Block("spec", "spec-ambiguous")
    base, skill = spec_dir(), skill_dir()
    shared = [f"{base}/plan.yaml", f"{base}/README.md"] + ([f"{skill}/SKILL.md", f"{skill}/README.md"] if skill else [])
    raw = read_regular(Path(root) / found[0])
    text = raw.decode("utf-8", "replace") if raw is not None else ""
    return {"own": found[0], "shared": shared, "stems": neighbor_stems(text, tag)}


def approved_copy(root, rel, digest, commits=()):
    """The bytes of rel in some commit of this repository whose sha256 is digest, or None. The commits
    given are tried first, then the newest 200 changes of the file on every ref. A version counts only
    when its digest is the one a receipt lists. Nothing is fetched and nothing is changed."""
    candidates = [c for c in commits if isinstance(c, str) and _GIT_SHA.match(c)]
    status, out = git(root, "log", "--all", "--format=%H", "-n", "200", "--", rel)
    if status == 0:
        candidates += [c for c in out.decode("ascii", "replace").split() if _GIT_SHA.match(c)]
    seen = set()
    for commit in candidates:
        if commit in seen:
            continue
        seen.add(commit)
        status, blob = git(root, "cat-file", "blob", f"{commit}:{rel}")
        if status == 0 and len(blob) <= MAX_BYTES and sha256(blob) == digest:
            return blob
    return None


def judge_input(root, receipt, rel, is_spec, cache):
    """(status, approved bytes, overlay result) for one input of the item against one receipt. status is
    ok, overlay or a reason code. For a specification under the allowed policy, a file that differs from
    its approved bytes is judged by the decision overlay."""
    entry = {a["path"]: a for a in receipt["artifacts"]}.get(rel)
    if entry is None:
        return "not-in-release", None, None
    raw = read_regular(Path(root) / rel)
    if raw is None:
        return "input-missing", None, None
    if sha256(raw) == entry["sha256"] and len(raw) == entry["bytes"]:
        return "ok", raw, None
    if not is_spec:
        return "input-changed", None, None
    if edit_policy() != "allowed":
        return "body-changed", None, None
    key = (rel, entry["sha256"])
    if key not in cache:
        cache[key] = approved_copy(root, rel, entry["sha256"])
    approved = cache[key]
    if approved is None:
        return "approved-copy-unavailable", None, None
    result = validate_overlay(approved, raw, "allowed")
    return ("overlay", approved, result) if result.ok else (result.reason, None, None)


def evaluate(root, receipt, inputs, cache):
    """[(path, status, approved bytes, overlay result)] for every input the receipt requires: the
    specification of the item first, then the neighbors' specifications the receipt lists, then the shared files."""
    base = spec_dir()
    listed = [a["path"] for a in receipt["artifacts"]]
    specs, ambiguous = [inputs["own"]], []
    for stem in inputs["stems"]:
        hits = sorted(p for p in listed if p.startswith(base + "/") and p.rsplit("/", 1)[-1].startswith(stem + "-") and p.endswith(".md"))
        if len(hits) > 1:
            ambiguous.append((hits[0], "spec-ambiguous", None, None))
        specs += hits[:1]
    rows = [(rel,) + judge_input(root, receipt, rel, True, cache) for rel in specs] + ambiguous
    rows += [(rel,) + judge_input(root, receipt, rel, False, cache) for rel in inputs["shared"]]
    return rows


def disagreement(receipts, paths):
    """The first of paths that the receipts list with different digests or lengths, or that some of them
    do not list at all, or None when they all agree on every one."""
    for path in paths:
        listed = set()
        for r in receipts:
            entry = {a["path"]: a for a in r["artifacts"]}.get(path)
            listed.add(None if entry is None else (entry["sha256"], entry["bytes"]))
        if len(listed) > 1:
            return path
    return None


def choose(root, local, ctx, tag, restricted):
    """(receipt, rows): the one receipt that is active and lists the context and every other approved
    input with matching digests. Raises Block when there is none: missing (10) when no receipt lists the
    context, stale (11) when only ended ones do, mixed (15) when the files match different active
    receipts or when two active receipts that list this item disagree on any approved input, and spec
    (14) when a file matches none. Active receipts that agree on every input are one release in effect,
    and the newest is used."""
    matching = [r for r in local.values() if lists(r, ctx)]
    if not matching:
        raise Block("missing")
    active = [r for r in matching if r["state"] == "active"]
    if not active:
        raise Block("stale", terminal_reason(matching))
    if restricted:
        return newest(active), []          # a placeholder has no specification to check
    inputs = local_inputs(root, tag)
    cache = {}
    rows = {r["request_id"]: evaluate(root, r, inputs, cache) for r in active}
    # every active receipt that lists this item's context files, whatever digests it gives them
    claims = [r for r in local.values() if r["state"] == "active" and all(p in {a["path"] for a in r["artifacts"]} for p in ctx)]
    paths = list(ctx)
    for r in active:
        paths += [row[0] for row in rows[r["request_id"]] if row[0] not in paths]
    split = disagreement(claims, paths) if len(claims) > 1 else None
    full = [r for r in active if all(row[1] in OKAY for row in rows[r["request_id"]])]
    if full and split is None:
        best = newest(full)
        return best, rows[best["request_id"]]
    seen = {}
    for r in active:
        for row in rows[r["request_id"]]:
            seen.setdefault(row[0], []).append(row[1])
    if not full and all(any(s in OKAY for s in states) for states in seen.values()):
        raise Block("mixed", "inputs-from-different-releases")
    if split is not None:
        raise Block("mixed", "two-active-releases", split)
    best = newest(active)
    for row in rows[best["request_id"]]:
        if row[1] not in OKAY:
            raise Block("spec", row[1], row[0])
    raise Block("spec", "input-changed")


def input_files(receipt, rows):
    """{path: (sha256, bytes)} of the approved inputs, as the receipt lists them."""
    by_path = {a["path"]: a for a in receipt["artifacts"]}
    return {row[0]: (by_path[row[0]]["sha256"], by_path[row[0]]["bytes"]) for row in rows}


def input_label(path, tag):
    base, skill = spec_dir(), skill_dir()
    if path == f"{CONTEXT_DIR}/{tag.lower()}.md":
        return "approved context"
    if path == f"{CONTEXT_DIR}/{tag.lower()}.bundle.json":
        return "context sidecar"
    if path == f"{base}/plan.yaml":
        return "released plan"
    if path == f"{base}/README.md":
        return "specification folder README"
    if skill and path == f"{skill}/SKILL.md":
        return "engineers' skill instructions"
    if skill and path == f"{skill}/README.md":
        return "engineers' skill README"
    return "specification" if path.rsplit("/", 1)[-1].startswith(tag.lower() + "-") else "shared specification"


# ---------------------------------------------------------------------------
# The approved delta
# ---------------------------------------------------------------------------

def read_cache(root):
    raw = read_regular(Path(root) / CACHE_FILE)
    try:
        record = parse_json(raw) if raw is not None else None
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return record if isinstance(record, dict) else None


def write_cache(root, record):
    path = Path(root) / CACHE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(path))
    except OSError:
        pass


def read_baseline(root, identity, tag):
    """The approved inputs recorded at the last check of this item in this repository, or None."""
    record = read_cache(root)
    if record is None or identity is None or record.get("repository") != identity:
        return None
    items = record.get("items")
    base = items.get(tag) if isinstance(items, dict) else None
    if not isinstance(base, dict) or not isinstance(base.get("request_id"), str):
        return None
    files = base.get("files")
    if not isinstance(files, dict) or not all(isinstance(k, str) and isinstance(v, str) and _SHA256.match(v) for k, v in files.items()):
        return None
    return base


def record_baseline(root, identity, tag, baseline):
    """Add or replace the item's entry in the refresh record. It never creates a record: the record exists
    only after a good fetch."""
    record = read_cache(root)
    if record is None or identity is None or record.get("repository") != identity:
        return
    items = record.get("items") if isinstance(record.get("items"), dict) else {}
    items[tag] = baseline
    record["items"] = items
    write_cache(root, record)


def shows_passages(path):
    skill = skill_dir()
    return path.endswith(".md") and not (skill and path == f"{skill}/README.md")


def passage_diff(old, new, path):
    """Changed passages of one Markdown file, two lines of context, from the previous approved bytes."""
    before = old.decode("utf-8", "replace").splitlines()
    after = new.decode("utf-8", "replace").splitlines()
    diff = list(difflib.unified_diff(before, after, f"{path} (previous)", f"{path} (current)", n=2, lineterm=""))
    out = [line[:300] for line in diff[:DELTA_LINES]]
    if len(diff) > DELTA_LINES:
        out.append(f"(more changed lines in {path} are not shown. Read the file.)")
    return out


def delta_lines(root, tag, previous, current, request_id, approved, commit):
    """The approved delta since the last check: [] when nothing changed and no newer release replaced
    the one recorded, a one-line note when only the release changed (a provenance refresh), else the block
    that names the changed files, shows the changed passages and ends with the reassessment instruction.
    current is {path: sha256}; approved is {path: approved bytes}."""
    before = previous["files"]
    changed = [p for p in sorted(set(before) | set(current)) if before.get(p) != current.get(p)]
    if not changed:
        if previous["request_id"] != request_id:
            return [f"note: a newer release covers the same approved inputs for {tag}. Only its provenance changed, so nothing in your plan needs to change"]
        return []
    lines = [DELTA_HEADLINE.format(id=tag)]
    for p in changed:
        state = "new in this release" if p not in before else "no longer an input" if p not in current else "changed"
        lines.append(f"{state}: {p} ({input_label(p, tag)})")
    for p in changed:
        if p not in before or p not in current or not shows_passages(p):
            continue
        old = approved_copy(root, p, before[p], commits=[commit] if commit else ())
        if old is None or p not in approved:
            lines.append(f"{p}: {NO_PREVIOUS}")
        else:
            lines += passage_diff(old, approved[p], p)
    if len(lines) > DELTA_TOTAL:
        lines = lines[:DELTA_TOTAL] + ["(the rest of the delta is not shown. Read the changed files.)"]
    return lines + [REASSESS]


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------

def git(root, *args, timeout=FETCH_TIMEOUT):
    """(exit status, stdout bytes). A missing git or a timeout is status 127."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    try:
        run = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError):
        return 127, b""
    return run.returncode, run.stdout


def default_branch(root):
    status, out = git(root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    if status == 0:
        ref = out.decode("utf-8", "replace").strip()
        branch = ref[len("refs/remotes/origin/"):] if ref.startswith("refs/remotes/origin/") else ""
    else:
        status, out = git(root, "ls-remote", "--symref", "origin", "HEAD")
        m = re.search(r"(?m)^ref: refs/heads/(\S+)\s+HEAD$", out.decode("utf-8", "replace")) if status == 0 else None
        branch = m.group(1) if m else ""
    return branch if _BRANCH.match(branch) else None


def fetched_receipts(root, commit):
    """{request id: receipt} read from docs/release/ of a fetched commit, or None when it cannot be read."""
    status, out = git(root, "ls-tree", "-r", "-z", "--name-only", commit, "--", RELEASE_DIR)
    if status != 0:
        return None
    names = [n for n in out.decode("utf-8", "replace").split("\0")
             if re.fullmatch(re.escape(RELEASE_DIR) + r"/[0-9a-f]{64}\.receipt\.json", n)]
    if len(names) > MAX_RECEIPTS:
        return None
    found = {}
    for name in names:
        status, blob = git(root, "cat-file", "blob", f"{commit}:{name}")
        if status != 0:
            return None
        r = parse_receipt(blob, name.rsplit("/", 1)[1]) if len(blob) <= MAX_BYTES else None
        if r is not None:
            found[r["request_id"]] = r
    return found


def merge(local, fetched):
    """Receipts by request id. A terminal state is never replaced by an active one."""
    out = dict(local)
    for rid, r in fetched.items():
        old = out.get(rid)
        if old is not None and old["state"] != "active" and r["state"] == "active":
            continue
        out[rid] = r
    return out


def judge_fetched(local, fetched, files):
    """("fresh", receipt) or ("stale", reason code) from the receipts of the fetched commit."""
    merged = merge(local, fetched)
    fresh = [merged[rid] for rid in fetched if merged[rid]["state"] == "active" and lists(merged[rid], files)]
    if fresh:
        return "fresh", newest(fresh)
    ended = [r for r in merged.values() if r["state"] != "active" and lists(r, files)]
    if ended:
        return "stale", terminal_reason(ended)
    paths = set(files)
    if any(r["state"] == "active" and paths & {a["path"] for a in r["artifacts"]} for r in fetched.values()):
        return "stale", "sha256-mismatch"
    return "stale", "approval-not-found"


def origin_identity(root):
    """The identity of this repository as the cache records it: the origin address without
    credentials, scheme or a trailing .git."""
    status, out = git(root, "config", "--get", "remote.origin.url")
    url = out.decode("utf-8", "replace").strip() if status == 0 else ""
    m = re.match(r"^(?:[A-Za-z][A-Za-z0-9+.-]*://)?(?:[^@/]*@)?([^/:]+)[:/](.+?)(?:\.git)?/?$", url)
    return (f"{m.group(1).lower()}/{m.group(2)}" if m else re.sub(r"\.git/?$", "", url)) or None


def refresh(root, files, local):
    """Fetch the default branch and judge its receipts. Returns ("fresh", receipt, commit),
    ("stale", reason, None) or ("unreachable", "could-not-refresh", None)."""
    branch = default_branch(root)
    if branch is None:
        return "unreachable", "could-not-refresh", None
    status, _ = git(root, "fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "origin", f"refs/heads/{branch}")
    if status != 0:
        return "unreachable", "could-not-refresh", None
    status, out = git(root, "rev-parse", "--verify", "--quiet", "FETCH_HEAD^{commit}")
    commit = out.decode("ascii", "replace").strip()
    if status != 0 or not _GIT_SHA.match(commit):
        return "unreachable", "could-not-refresh", None
    fetched = fetched_receipts(root, commit)
    if fetched is None:
        return "unreachable", "could-not-refresh", None
    verdict, detail = judge_fetched(local, fetched, files)
    if verdict == "stale":
        return "stale", detail, None
    return "fresh", detail, commit


def record_refresh(root, identity, commit, request_id, now):
    record = {"cache_format": 1, "repository": identity, "commit": commit, "request_id": request_id,
              "time": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    old = read_cache(root)
    if old is not None and old.get("repository") == identity and isinstance(old.get("items"), dict):
        record["items"] = old["items"]        # the per-item baselines survive a refresh
    write_cache(root, record)


def grace_allows(root, identity, receipt, now):
    """True when the last good refresh matches this repository and this request and is within grace."""
    raw = read_regular(Path(root) / CACHE_FILE)
    try:
        record = parse_json(raw) if raw is not None else None
    except (ValueError, UnicodeDecodeError, RecursionError):
        return False
    if not isinstance(record, dict) or set(record) - {"items"} != {"cache_format", "repository", "commit", "request_id", "time"} \
            or not isinstance(record.get("items", {}), dict):
        return False
    when = parse_time(record["time"])
    if not is_int(record["cache_format"]) or record["cache_format"] != 1 or when is None or identity is None or record["repository"] != identity:
        return False
    if record["request_id"] != receipt["request_id"] or not isinstance(record["commit"], str) or not _GIT_SHA.match(record["commit"]):
        return False
    days = receipt["offline_grace_days"]
    if days == 0 or when > now or (now - when) > dt.timedelta(days=days):
        return False
    status, _ = git(root, "cat-file", "-e", record["commit"] + "^{commit}")
    return status == 0


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

def check(root, argument, now=None, refresh_allowed=True):
    """Run the check. Returns (exit status, lines to print)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    number = item_number(argument)
    tag = shown_id(argument, number)
    try:
        if number is None:
            raise Block("missing")
        stem = f"{tag.lower()}"
        md_rel, js_rel = f"{CONTEXT_DIR}/{stem}.md", f"{CONTEXT_DIR}/{stem}.bundle.json"
        md, js = read_regular(Path(root) / md_rel), read_regular(Path(root) / js_rel)
        if md is None or js is None:
            raise Block("missing")
        side = load_sidecar(js, tag)
        if sha256(md) != side["content_sha256"]:
            raise Block("missing")
        have = {(ob["source"], ob["section"]) for ob in side["obligations"]}
        for cited in spec_citations(root, tag, {s for s, _ in have}):
            if cited not in have:
                raise Block("cites")
        ctx = {md_rel: (sha256(md), len(md)), js_rel: (sha256(js), len(js))}
        restricted = side.get("restricted_destination") is True
        local = local_receipts(root)
        receipt, rows = choose(root, local, ctx, tag, restricted)
        files = dict(ctx, **input_files(receipt, rows))
        approved = {md_rel: md}
        approved.update({row[0]: row[2] for row in rows if row[2] is not None})
        warnings = []
        identity = origin_identity(root)
        previous = read_baseline(root, identity, tag)
        outcome, detail, commit = refresh(root, files, local) if refresh_allowed else ("unreachable", "could-not-refresh", None)
        if outcome == "stale":
            raise Block("stale", detail)
        if outcome == "fresh":
            receipt = detail
            record_refresh(root, identity, commit, receipt["request_id"], now)
        elif grace_allows(root, identity, receipt, now):
            warnings.append("warning: freshness not confirmed; within offline grace")
        else:
            raise Block("stale", "could-not-refresh")
        if receipt["expires_at"] is not None and now >= parse_time(receipt["expires_at"]):
            raise Block("stale", "expired")
        if restricted:
            raise Block("restricted")
    except Block as block:
        extra = [f"The owner's approved instruction is in {md_rel}."] if block.kind == "restricted" else []
        code, lines = message(block.kind, tag, block.reason, extra, block.where)
        return code, lines
    own = rows[0]
    overlays = {row[0]: row[3].overlay_sha256 for row in rows if row[3] is not None and row[3].overlay_sha256}
    lines = [f"carrydown: approved context for {tag} is ready", f"Read {md_rel}. Do not open docs/ground-truth/ or any source.",
             f"baseline: request {receipt['request_id']}, specification {files[own[0]][0]}"]
    if own[3] is not None and own[3].entries:
        lines.append(f"note: {len(own[3].entries)} new note(s) under Decisions recorded in your copy of the specification. They are not an approval. The plan owner reviews them")
    if outcome == "fresh":
        current = {path: digest for path, (digest, _) in files.items()}
        if previous is not None:
            lines += delta_lines(root, tag, previous, current, receipt["request_id"], approved, commit)
        record_baseline(root, identity, tag, {"request_id": receipt["request_id"], "files": current,
                                              "overlay_sha256": overlays.get(own[0]), "overlays": overlays})
    return 0, lines + warnings


def repository_top(start):
    status, out = git(start, "rev-parse", "--show-toplevel", timeout=15)
    top = out.decode("utf-8", "replace").strip() if status == 0 else ""
    return Path(top) if top and os.path.isdir(top) else Path(start)


def help_epilog():
    """The exit codes for --help: each of the six codes with its message, then 2 and 3."""
    lines = ["exit status:", "  0   the inputs are ready to read"]
    for code, first, _ in sorted(KINDS.values()):
        lines.append(f"  {code}  {first.format(id='<ID>')}")
    lines += ["  2   a wrong argument (no line starts with carrydown:)",
              "  3   the Python that runs it is older than 3.9 (no line starts with carrydown:)",
              "",
              "A line `warning: freshness not confirmed; within offline grace` means the inputs passed but the",
              "default branch could not be reached."]
    return "\n".join(lines)


def main(argv=None, now=None):
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Check that the approved inputs of one work item can be used: its context, its\n"
                    "specification and the files they depend on. Prints a short block and exits 0, or\n"
                    "prints one of six carrydown messages and exits 10, 11, 12, 13, 14 or 15.\n"
                    "It is a convenience check for the engineer, not a security control.",
        epilog=help_epilog())
    ap.add_argument("id", help="the work item id, such as WI-03")
    ap.add_argument("--root", help="the repository (default: the top of the git repository you are in)")
    ap.add_argument("--no-refresh", action="store_true", help="do not run git fetch. Follow the offline grace rule")
    a = ap.parse_args(argv)
    root = Path(a.root).expanduser() if a.root else repository_top(os.getcwd())
    if not root.is_dir():
        print("error: --root is not a folder", file=sys.stderr)
        return 2
    code, lines = check(root.resolve(), a.id, now=now, refresh_allowed=not a.no_refresh)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    if tuple(sys.version_info)[:2] < (3, 9):
        # no line starts with "carrydown:", so the skill sends the agent to references/preflight.md
        print("error: this check needs Python 3.9 or newer. Follow references/preflight.md in the skill folder", file=sys.stderr)
        sys.exit(3)
    sys.exit(main())
