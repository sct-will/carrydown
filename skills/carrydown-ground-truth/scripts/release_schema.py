#!/usr/bin/env python3
"""Offline schema and digest functions for confidential releases. Standard library only.

This module has no dependency on carrydown_lib or on any other carrydown script, so the
independent verifier and the installed skills can carry it unchanged. It reads no network, no
token and no environment. Every function is pure except hash_manifest, which only reads the
snapshot folder it is given.

What is here
- canonical_json: the one serialization every digest in a release is computed over.
- Digests: sha256_bytes, hash_manifest, hash_request and hash_event. Each digest excludes only the
  field the specification names, and nothing else.
- Strict validators: validate_manifest, validate_request, validate_event and validate_receipt.
  They reject unknown fields, abbreviated digests, unsafe paths and unsupported file modes.
- replay_state: the state machine of the event batches (prepared, active, superseded, withdrawn).
- project_receipt: the public receipt, built only from verified inputs.

Errors are SchemaError. Its code is a fixed reason code, its field names the location, and its
message never holds a value from the data, so a confidential string cannot leak through it.

This module is imported by the other scripts. Run with --help to see this text.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import stat as _stat
import sys
import unicodedata
from typing import NamedTuple, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODES = ("100644", "100755")
STATES = ("prepared", "active", "superseded", "withdrawn")
TERMINAL_STATES = ("superseded", "withdrawn")
RECEIPT_STATES = ("active", "superseded", "withdrawn")
TRANSITIONS = (("prepared", "active"), ("active", "superseded"), ("active", "withdrawn"))
AUDIENCES = ("repo-readers", "public")
EVIDENCE = ("synthetic-only", "approved")
APPROVAL_TYPES = {"github-review": True, "local-owner": False}
# Canonical order of the destinations a receipt may name. A receipt lists a subset in this order.
DESTINATIONS = ("engineering-repo", "issue", "subepic", "epic", "epic-comment", "label", "board", "engineers-skill")

MANIFEST_ENTRY_KEYS = ("path", "sha256", "bytes", "mode")
REQUEST_KEYS = ("request_format", "release_id", "request_nonce", "created", "policy_commit_sha", "policy_sha256",
                "enrollment_id", "activate", "supersedes_request_id", "receipt_template", "preview",
                "detector_exceptions", "request_sha256")
TEMPLATE_KEYS = ("receipt_format", "content_manifest_sha256", "created", "expires_at", "audience", "destinations",
                 "targets", "sources", "artifacts", "downstream", "offline_grace_days", "enrollment_id")
EXCEPTION_KEYS = ("type", "passage_sha256", "destinations", "reason")
EVENT_KEYS = ("event_format", "event_nonce", "policy_commit_sha", "policy_sha256", "created", "transitions", "event_id")
TRANSITION_KEYS = ("request_id", "from", "to", "previous_event_id", "replacement_request_id", "reason_code")
RECEIPT_KEYS = ("receipt_format", "request_id", "release_id", "content_manifest_sha256", "created", "state", "event_id",
                "supersedes", "superseded_by", "expires_at", "audience", "destinations", "targets", "sources",
                "artifacts", "downstream", "offline_grace_days", "approval", "enrollment_id")
APPROVAL_KEYS = ("type", "authenticated", "ref")
DOWNSTREAM_KEYS = ("assignees", "capacity_summary", "evidence")
SOURCE_KEYS = ("id", "version")
REPO_TARGET_KEYS = ("id", "host", "repository_id", "repository")
BOARD_TARGET_KEYS = ("id", "host", "repository_id", "owner_id", "project_id")

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{32}\Z")
_GIT_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_WORDS = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_HOST = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class SchemaError(ValueError):
    """A release record that is malformed or unsafe. code is a fixed reason code, field says where.
    The message holds the code and the field and never a value from the data."""

    def __init__(self, code, field="", detail=""):
        self.code = code
        self.field = field
        self.detail = detail
        text = code + (f" at {field}" if field else "") + (f": {detail}" if detail else "")
        super().__init__(text)


# ---------------------------------------------------------------------------
# Canonical JSON and digests
# ---------------------------------------------------------------------------

def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise SchemaError("schema-invalid", "", "duplicate object key")
        seen[key] = value
    return seen


def _no_constant(name):
    raise SchemaError("schema-invalid", "", "non-finite number")


def loads_strict(data):
    """Parse a JSON document (bytes or text) and reject duplicate object keys and the non-finite
    numbers NaN, Infinity and -Infinity. A leading byte order mark is refused."""
    if isinstance(data, (bytes, bytearray)):
        try:
            data = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            raise SchemaError("schema-invalid", "", "not UTF-8")
    if not isinstance(data, str):
        raise SchemaError("schema-invalid", "", "not text")
    try:
        return json.loads(data, object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except SchemaError:
        raise
    except (ValueError, RecursionError):
        raise SchemaError("schema-invalid", "", "not valid JSON")


def _json_value(value, depth=0):
    """Refuse what JSON cannot hold exactly: a non-text key, a non-finite number, a type other
    than null, bool, number, text, list and object."""
    if depth > 64:
        raise SchemaError("schema-invalid", "", "value is nested too deeply")
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise SchemaError("schema-invalid", "", "non-finite number")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _json_value(item, depth + 1)
        return
    if isinstance(value, dict):
        for k, item in value.items():
            if not isinstance(k, str):
                raise SchemaError("schema-invalid", "", "object keys must be text")
            _json_value(item, depth + 1)
        return
    raise SchemaError("schema-invalid", "", "value cannot be written as canonical JSON")


def canonical_json(value):
    """The canonical bytes of value: UTF-8, sorted object keys, no insignificant whitespace and
    exactly one trailing LF. A bytes argument is treated as a JSON document: it is parsed with
    duplicate keys and non-finite numbers rejected, then serialized. Any other argument is a Python
    value, and a str is a JSON string value, not a document. A non-finite number, a non-string key
    or a value that JSON cannot hold raises SchemaError."""
    if isinstance(value, (bytes, bytearray)):
        value = loads_strict(value)
    _json_value(value)
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return text.encode("utf-8") + b"\n"
    except (ValueError, TypeError, RecursionError, UnicodeEncodeError):
        raise SchemaError("schema-invalid", "", "value cannot be written as canonical JSON")


def sha256_bytes(data):
    """The lowercase hex SHA-256 of data."""
    return hashlib.sha256(bytes(data)).hexdigest()


def sha256_text(text):
    """The lowercase hex SHA-256 of text encoded as UTF-8."""
    return sha256_bytes(text.encode("utf-8"))


def _digest_and_size(path):
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def sha256_file(path):
    """The lowercase hex SHA-256 of a file, read in chunks. The caller decides what kind of file
    is acceptable; an unreadable path raises OSError."""
    return _digest_and_size(path)[0]


_LINE_END_SPACE = " \t\r\f\v"


def normalize_section_text(text):
    """The text of a source section as the compiler and the verifier both compare it: CRLF becomes
    LF, trailing spaces, tabs and form feeds are removed from every line, and the text ends with
    exactly one newline. Nothing else changes, so the words of a rule are never altered."""
    lines = text.replace("\r\n", "\n").split("\n")
    return "\n".join(line.rstrip(_LINE_END_SPACE) for line in lines).rstrip("\n") + "\n"


def _without(obj, field):
    return {k: v for k, v in obj.items() if k != field}


def hash_request(request):
    """The request digest: the canonical request with only request_sha256 omitted. The stored
    value is never trusted: the argument may carry it or not, and it is dropped before hashing.
    Every other field is checked against the strict request schema first."""
    _request_fields(request, with_digest=False)
    return sha256_bytes(canonical_json(_without(request, "request_sha256")))


def hash_event(batch):
    """The event digest: the canonical batch with only event_id omitted."""
    _event_fields(batch, with_digest=False)
    return sha256_bytes(canonical_json(_without(batch, "event_id")))


# ---------------------------------------------------------------------------
# Field checks. Each raises SchemaError and names a field, never a value.
# ---------------------------------------------------------------------------

def _fail(field, detail, code="schema-invalid"):
    raise SchemaError(code, field, detail)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _exact_keys(obj, keys, field, allow_missing=()):
    if not isinstance(obj, dict):
        _fail(field, "must be an object")
    for k in obj:
        if not isinstance(k, str):
            _fail(field, "keys must be text")
    unknown = sorted(set(obj) - set(keys))
    if unknown:
        _fail(field, "unknown field " + ", ".join(unknown))
    missing = [k for k in keys if k not in obj and k not in allow_missing]
    if missing:
        _fail(field, "missing field " + ", ".join(missing))


def _sha(v, field, none=False):
    if v is None and none:
        return
    if not (isinstance(v, str) and _SHA256.match(v)):
        _fail(field, "must be 64 lowercase hexadecimal characters")


def _nonce(v, field):
    if not (isinstance(v, str) and _NONCE.match(v)):
        _fail(field, "must be 32 lowercase hexadecimal characters")


def _git_sha(v, field):
    if not (isinstance(v, str) and _GIT_SHA.match(v)):
        _fail(field, "must be a full 40 or 64 character lowercase hexadecimal commit id")


def _time(v, field, none=False):
    if v is None and none:
        return
    if not (isinstance(v, str) and _TIME.match(v)):
        _fail(field, "must be a UTC time such as 2027-01-20T14:03:00Z")
    try:
        _dt.datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        _fail(field, "must be a real date and time")


def _text(v, field, words=False, limit=200):
    if not (isinstance(v, str) and v.strip() and len(v) <= limit and not _CONTROL.search(v)):
        _fail(field, "must be one line of text")
    if words and not _WORDS.match(v):
        _fail(field, "must be lowercase words joined by hyphens")


def is_format(value, expected=1):
    """True when value is the integer expected. A format field is an integer (Part H1): 1.0, true and "1"
    are not format 1, even though 1.0 == 1 and True == 1 in Python."""
    return type(value) is int and value == expected


def _bool(v, field, want=None):
    if not isinstance(v, bool) or (want is not None and v is not want):
        _fail(field, "must be " + ("true or false" if want is None else str(want).lower()))


def check_path(path, field="path"):
    """Refuse a path that could escape the destination or collide on another file system: absolute,
    drive letter, backslash, empty, dot or dot-dot component, a control character, or a .git
    component. Paths use / separators. Returns the path."""
    code = "unsafe-artifact-path"
    if not isinstance(path, str) or not path:
        _fail(field, "path must be non-empty text", code)
    if _CONTROL.search(path):
        _fail(field, "path has a control character", code)
    if path.startswith("/") or "\\" in path or re.match(r"[A-Za-z]:", path):
        _fail(field, "path must be relative and use / separators", code)
    for part in path.split("/"):
        if part in ("", ".", ".."):
            _fail(field, "path has an empty, dot or dot-dot component", code)
        if ":" in part:
            _fail(field, "path component has a colon", code)
        if part.casefold() == ".git":
            _fail(field, "path enters git internals", code)
    return path


def _collision_key(path):
    return unicodedata.normalize("NFC", path).casefold()


def _check_unique_sorted(paths, field):
    """paths are already checked. They must be sorted, unique and free of case collisions."""
    seen = set()
    for p in paths:
        key = _collision_key(p)
        if key in seen:
            _fail(field, "duplicate or case-colliding path", "unsafe-artifact-path")
        seen.add(key)
    if list(paths) != sorted(paths):
        _fail(field, "entries must be sorted by path")


def _entries(value, field):
    """Validate a list of {path, sha256, bytes, mode} entries. Returns a new list of copies."""
    if not isinstance(value, list):
        _fail(field, "must be a list")
    out = []
    for i, e in enumerate(value):
        where = f"{field}[{i}]"
        _exact_keys(e, MANIFEST_ENTRY_KEYS, where)
        check_path(e["path"], where + ".path")
        _sha(e["sha256"], where + ".sha256")
        if not _is_int(e["bytes"]) or e["bytes"] < 0:
            _fail(where + ".bytes", "must be a whole number, zero or more")
        if e["mode"] not in MODES:
            _fail(where + ".mode", "must be 100644 or 100755", "unsafe-artifact-path")
        out.append(dict(e))
    _check_unique_sorted([e["path"] for e in out], field)
    return out


def _canonical_bytes_match(raw, value, what):
    if canonical_json(value) != bytes(raw):
        _fail(what, "bytes are not canonical JSON", "receipt-projection-mismatch" if what == "receipt" else "schema-invalid")


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def validate_manifest(manifest):
    """Validate a content manifest and return its entries as a new list. The manifest is a JSON
    array of {path, sha256, bytes, mode}, sorted by path. Pass the parsed list, or the bytes of
    content-manifest.json, which must also be canonical JSON."""
    if isinstance(manifest, (bytes, bytearray)):
        parsed = loads_strict(manifest)
        entries = _entries(parsed, "manifest")
        _canonical_bytes_match(manifest, parsed, "manifest")
        return entries
    return _entries(manifest, "manifest")


def manifest_from_entries(entries):
    """(canonical manifest bytes, release id) for entries given as dicts with path, sha256, bytes
    and mode. The entries are sorted by path, then validated. No approval or state field exists."""
    if not isinstance(entries, (list, tuple)):
        _fail("manifest", "must be a list")
    ordered = sorted((dict(e) if isinstance(e, dict) else e for e in entries),
                     key=lambda e: str(e.get("path")) if isinstance(e, dict) else "")
    checked = _entries(ordered, "manifest")
    data = canonical_json(checked)
    return data, sha256_bytes(data)


def release_id_of(manifest_bytes):
    """The release id: the SHA-256 of the bytes of content-manifest.json."""
    return sha256_bytes(manifest_bytes)


def _walk_snapshot(snapshot_dir):
    base = os.path.abspath(snapshot_dir)
    try:
        top = os.lstat(base)
    except OSError:
        _fail("snapshot", "folder cannot be read", "unsafe-artifact-path")
    if not _stat.S_ISDIR(top.st_mode):
        _fail("snapshot", "must be a folder", "unsafe-artifact-path")
    found = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        for name in list(dirnames) + list(filenames):
            full = os.path.join(dirpath, name)
            mode = os.lstat(full).st_mode
            if _stat.S_ISLNK(mode):
                _fail("snapshot", "contains a symbolic link", "unsafe-artifact-path")
            if _stat.S_ISDIR(mode):
                if name.casefold() == ".git":
                    _fail("snapshot", "contains git internals or a submodule", "unsafe-artifact-path")
                continue
            if not _stat.S_ISREG(mode):
                _fail("snapshot", "contains a file that is not a regular file", "unsafe-artifact-path")
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            found.append((rel, full))
    return found


def hash_manifest(snapshot_dir, modes=None):
    """Hash every regular file under snapshot_dir. Returns (canonical manifest bytes, release id).

    Every file is 100644 unless modes (a mapping of snapshot path to "100755") says the owner
    approved it as executable. A symbolic link, a submodule, a non-regular file, an absolute or
    dot-dot path, a duplicate path or a case collision raises SchemaError before anything is
    hashed into a manifest."""
    modes = dict(modes or {})
    found = _walk_snapshot(snapshot_dir)
    entries = []
    for rel, full in found:
        check_path(rel, "snapshot")
        mode = modes.get(rel, "100644")
        if mode not in MODES:
            _fail("modes", "must be 100644 or 100755", "unsafe-artifact-path")
        digest, size = _digest_and_size(full)
        entries.append({"path": rel, "sha256": digest, "bytes": size, "mode": mode})
    unknown = sorted(set(modes) - {rel for rel, _ in found})
    if unknown:
        _fail("modes", "names a path that is not in the snapshot", "unsafe-artifact-path")
    return manifest_from_entries(entries)


# ---------------------------------------------------------------------------
# Receipt template, request, event, receipt
# ---------------------------------------------------------------------------

def _destinations(value, field):
    if not isinstance(value, list) or not value:
        _fail(field, "must be a non-empty list")
    for d in value:
        if d not in DESTINATIONS:
            _fail(field, "names a destination that is not supported")
    if value != [d for d in DESTINATIONS if d in value]:
        _fail(field, "must be unique and in the canonical order")


def _targets(value, field):
    if not isinstance(value, list) or not value:
        _fail(field, "must be a non-empty list")
    ids = []
    for i, t in enumerate(value):
        where = f"{field}[{i}]"
        if not isinstance(t, dict):
            _fail(where, "must be an object")
        keys = BOARD_TARGET_KEYS if "project_id" in t or "owner_id" in t else REPO_TARGET_KEYS
        _exact_keys(t, keys, where)
        _text(t["id"], where + ".id", words=True)
        if not (isinstance(t["host"], str) and _HOST.match(t["host"])):
            _fail(where + ".host", "must be a host name")
        if not _is_int(t["repository_id"]) or t["repository_id"] <= 0:
            _fail(where + ".repository_id", "must be a positive number")
        if keys is REPO_TARGET_KEYS:
            if not (isinstance(t["repository"], str) and _REPO.match(t["repository"])):
                _fail(where + ".repository", "must look like owner/name")
        else:
            if not _is_int(t["owner_id"]) or t["owner_id"] <= 0:
                _fail(where + ".owner_id", "must be a positive number")
            _text(t["project_id"], where + ".project_id")
        ids.append(t["id"])
    if len(set(ids)) != len(ids) or ids != sorted(ids):
        _fail(field, "targets must have unique ids and be sorted by id")


def _sources(value, field):
    if not isinstance(value, list):
        _fail(field, "must be a list")
    ids = []
    for i, s in enumerate(value):
        where = f"{field}[{i}]"
        _exact_keys(s, SOURCE_KEYS, where)
        _text(s["id"], where + ".id", words=True)
        _text(s["version"], where + ".version")
        ids.append(s["id"])
    if len(set(ids)) != len(ids) or ids != sorted(ids):
        _fail(field, "sources must have unique ids and be sorted by id")


def _downstream(value, field):
    _exact_keys(value, DOWNSTREAM_KEYS, field)
    _bool(value["assignees"], field + ".assignees")
    _bool(value["capacity_summary"], field + ".capacity_summary")
    if value["evidence"] not in EVIDENCE:
        _fail(field + ".evidence", "must be synthetic-only or approved")


def _public_common(obj, field):
    """The fields a receipt template and a receipt share."""
    _time(obj["created"], field + ".created")
    _time(obj["expires_at"], field + ".expires_at", none=True)
    if obj["audience"] not in AUDIENCES:
        _fail(field + ".audience", "must be repo-readers or public")
    _destinations(obj["destinations"], field + ".destinations")
    _targets(obj["targets"], field + ".targets")
    _sources(obj["sources"], field + ".sources")
    _entries(obj["artifacts"], field + ".artifacts")
    _downstream(obj["downstream"], field + ".downstream")
    if not _is_int(obj["offline_grace_days"]) or obj["offline_grace_days"] < 0:
        _fail(field + ".offline_grace_days", "must be a whole number, zero or more")
    _sha(obj["enrollment_id"], field + ".enrollment_id")


def validate_receipt_template(template):
    """Validate the approved receipt template inside a request. Exactly the static field list of the
    specification. The template cannot carry release_id, request_id, state, event_id, supersedes,
    superseded_by or approval: those come only from verified records."""
    _exact_keys(template, TEMPLATE_KEYS, "receipt_template")
    if not is_format(template["receipt_format"]):
        _fail("receipt_template.receipt_format", "must be 1")
    _sha(template["content_manifest_sha256"], "receipt_template.content_manifest_sha256")
    _public_common(template, "receipt_template")
    return template


def _preview_ok(v, field, depth=0):
    if depth > 6:
        _fail(field, "is nested too deeply")
    if isinstance(v, str):
        if _CONTROL.search(v.replace("\n", "")):
            _fail(field, "has a control character")
    elif isinstance(v, list):
        for i, item in enumerate(v):
            _preview_ok(item, f"{field}[{i}]", depth + 1)
    elif isinstance(v, dict):
        for k, item in v.items():
            if not isinstance(k, str) or not k:
                _fail(field, "keys must be text")
            _preview_ok(item, f"{field}.{k}", depth + 1)
    else:
        _fail(field, "may hold only text, lists and objects")


def _request_fields(request, with_digest):
    _exact_keys(request, REQUEST_KEYS, "request", allow_missing=() if with_digest else ("request_sha256",))
    if not is_format(request["request_format"]):
        _fail("request.request_format", "must be 1")
    _sha(request["release_id"], "request.release_id")
    _nonce(request["request_nonce"], "request.request_nonce")
    _time(request["created"], "request.created")
    _git_sha(request["policy_commit_sha"], "request.policy_commit_sha")
    _sha(request["policy_sha256"], "request.policy_sha256")
    _sha(request["enrollment_id"], "request.enrollment_id")
    _bool(request["activate"], "request.activate", want=True)
    _sha(request["supersedes_request_id"], "request.supersedes_request_id", none=True)
    validate_receipt_template(request["receipt_template"])
    t = request["receipt_template"]
    if t["created"] != request["created"]:
        _fail("receipt_template.created", "must equal the request creation time")
    if t["enrollment_id"] != request["enrollment_id"]:
        _fail("receipt_template.enrollment_id", "must equal the request enrollment id")
    if t["content_manifest_sha256"] != request["release_id"]:
        _fail("receipt_template.content_manifest_sha256", "must equal the request release id")
    if not isinstance(request["preview"], dict) or not request["preview"]:
        _fail("request.preview", "must be a non-empty object")
    _preview_ok(request["preview"], "request.preview")
    exceptions = request["detector_exceptions"]
    if not isinstance(exceptions, list):
        _fail("request.detector_exceptions", "must be a list")
    for i, ex in enumerate(exceptions):
        where = f"request.detector_exceptions[{i}]"
        _exact_keys(ex, EXCEPTION_KEYS, where)
        _text(ex["type"], where + ".type", words=True, limit=64)
        _sha(ex["passage_sha256"], where + ".passage_sha256")
        dests = ex["destinations"]
        if not isinstance(dests, list) or not dests or any(d not in DESTINATIONS for d in dests):
            _fail(where + ".destinations", "must name supported destinations")
        _text(ex["reason"], where + ".reason")


def validate_request(request, check_digest=True):
    """Validate an approval request against the strict schema of the specification. With
    check_digest (the default) request_sha256 must be present and equal to the recomputed digest.
    The stored digest is never trusted. Returns the request."""
    _request_fields(request, with_digest=check_digest)
    if check_digest:
        _sha(request["request_sha256"], "request.request_sha256")
        if request["request_sha256"] != hash_request(request):
            _fail("request.request_sha256", "does not match the recomputed digest", "sha256-mismatch")
    return request


def _event_fields(batch, with_digest):
    _exact_keys(batch, EVENT_KEYS, "event", allow_missing=() if with_digest else ("event_id",))
    if not is_format(batch["event_format"]):
        _fail("event.event_format", "must be 1")
    _nonce(batch["event_nonce"], "event.event_nonce")
    _git_sha(batch["policy_commit_sha"], "event.policy_commit_sha")
    _sha(batch["policy_sha256"], "event.policy_sha256")
    _time(batch["created"], "event.created")
    transitions = batch["transitions"]
    if not isinstance(transitions, list) or not transitions:
        _fail("event.transitions", "must be a non-empty list")
    seen = set()
    for i, tr in enumerate(transitions):
        where = f"event.transitions[{i}]"
        _exact_keys(tr, TRANSITION_KEYS, where)
        _sha(tr["request_id"], where + ".request_id")
        if (tr["from"], tr["to"]) not in TRANSITIONS:
            _fail(where, "transition is not prepared to active, active to superseded or active to withdrawn", "state-history-invalid")
        _sha(tr["previous_event_id"], where + ".previous_event_id", none=True)
        if tr["to"] == "superseded":
            _sha(tr["replacement_request_id"], where + ".replacement_request_id")
            if tr["replacement_request_id"] == tr["request_id"]:
                _fail(where + ".replacement_request_id", "must differ from the request")
        elif tr["replacement_request_id"] is not None:
            _fail(where + ".replacement_request_id", "is allowed only on supersession")
        _text(tr["reason_code"], where + ".reason_code", words=True, limit=64)
        if tr["request_id"] in seen:
            _fail(where + ".request_id", "appears twice in one batch", "state-history-invalid")
        seen.add(tr["request_id"])
    for i, tr in enumerate(transitions):
        if tr["to"] == "superseded":
            rep = [x for x in transitions if x["request_id"] == tr["replacement_request_id"]]
            if len(rep) != 1 or (rep[0]["from"], rep[0]["to"]) != ("prepared", "active"):
                _fail(f"event.transitions[{i}].replacement_request_id", "must be activated in the same batch", "state-history-invalid")
    if len({tr["previous_event_id"] for tr in transitions}) != 1:
        _fail("event.transitions", "every transition must name the same previous event", "state-history-invalid")
    if sum(1 for tr in transitions if tr["to"] == "active") > 1:
        _fail("event.transitions", "a batch activates at most one request", "state-history-invalid")


def validate_event(batch, check_digest=True):
    """Validate an event batch. With check_digest event_id must equal the recomputed digest.
    Predecessor references are checked separately, by replay_state. Returns the batch."""
    _event_fields(batch, with_digest=check_digest)
    if check_digest:
        _sha(batch["event_id"], "event.event_id")
        if batch["event_id"] != hash_event(batch):
            _fail("event.event_id", "does not match the recomputed digest", "sha256-mismatch")
    return batch


def validate_receipt(receipt):
    """Validate a public receipt against the strict schema of the specification. Pass the parsed
    object, or the bytes of the file, which must also be canonical JSON. Whether the receipt equals
    the projection of verified records is a separate question: see verify_receipt_bytes."""
    if isinstance(receipt, (bytes, bytearray)):
        parsed = loads_strict(receipt)
        validate_receipt(parsed)
        _canonical_bytes_match(receipt, parsed, "receipt")
        return parsed
    _exact_keys(receipt, RECEIPT_KEYS, "receipt")
    if not is_format(receipt["receipt_format"]):
        _fail("receipt.receipt_format", "must be 1")
    _sha(receipt["request_id"], "receipt.request_id")
    _sha(receipt["release_id"], "receipt.release_id")
    _sha(receipt["content_manifest_sha256"], "receipt.content_manifest_sha256")
    if receipt["release_id"] != receipt["content_manifest_sha256"]:
        _fail("receipt.release_id", "must equal content_manifest_sha256")
    if receipt["state"] not in RECEIPT_STATES:
        _fail("receipt.state", "must be active, superseded or withdrawn")
    _sha(receipt["event_id"], "receipt.event_id")
    _sha(receipt["supersedes"], "receipt.supersedes", none=True)
    _sha(receipt["superseded_by"], "receipt.superseded_by", none=True)
    if (receipt["state"] == "superseded") != (receipt["superseded_by"] is not None):
        _fail("receipt.superseded_by", "is set exactly when the state is superseded")
    if receipt["request_id"] in (receipt["supersedes"], receipt["superseded_by"]):
        _fail("receipt.request_id", "a request cannot supersede itself")
    _public_common(receipt, "receipt")
    approval = receipt["approval"]
    _exact_keys(approval, APPROVAL_KEYS, "receipt.approval")
    if approval["type"] not in APPROVAL_TYPES:
        _fail("receipt.approval.type", "must be github-review or local-owner")
    _bool(approval["authenticated"], "receipt.approval.authenticated")
    if approval["authenticated"] is not APPROVAL_TYPES[approval["type"]]:
        _fail("receipt.approval.authenticated", "does not match the approval type")
    _sha(approval["ref"], "receipt.approval.ref")
    if approval["ref"] != receipt["request_id"]:
        _fail("receipt.approval.ref", "must equal request_id")
    return receipt


# ---------------------------------------------------------------------------
# State replay
# ---------------------------------------------------------------------------

class RequestState(NamedTuple):
    """The authenticated state of one request, as replay_state derives it."""
    request_id: str
    state: str
    event_id: str
    superseded_by: Optional[str]
    supersedes: Optional[str]


class ReplayResult(NamedTuple):
    """requests maps request id to RequestState. tip is the id of the last event, or None.
    active is the one active request id, or None."""
    requests: dict
    tip: Optional[str]
    active: Optional[str]


def replay_state(verified_events, authorized=None):
    """Replay event batches given in authenticated merge order and return a ReplayResult.

    The caller has already verified each batch's bytes and review. This function checks the
    chain: each batch names the previous tip, each transition starts from the request's current
    state, a terminal request never becomes active again, and at most one request is active after
    each batch. A batch that appears again unchanged is skipped (idempotent). Anything else raises
    SchemaError with code state-history-invalid. authorized, when given, is called with each new
    batch and must return True, otherwise the history is invalid."""
    states = {}
    last_event = {}
    superseded_by = {}
    supersedes = {}
    applied = set()
    tip = None
    for raw in verified_events:
        batch = validate_event(raw)
        eid = batch["event_id"]
        if eid in applied:
            continue
        if authorized is not None and authorized(batch) is not True:
            _fail("event", "batch was not authorized", "state-history-invalid")
        for i, tr in enumerate(batch["transitions"]):
            where = f"event.transitions[{i}]"
            if tr["previous_event_id"] != tip:
                _fail(where + ".previous_event_id", "does not match the current tip", "state-history-invalid")
            current = states.get(tr["request_id"], "prepared")
            if current in TERMINAL_STATES:
                _fail(where, "a terminal request cannot change state", "state-history-invalid")
            if current != tr["from"]:
                _fail(where + ".from", "does not match the current state of the request", "state-history-invalid")
        staged = dict(states)
        for tr in batch["transitions"]:
            staged[tr["request_id"]] = tr["to"]
        if sum(1 for s in staged.values() if s == "active") > 1:
            _fail("event", "more than one request would be active", "state-history-invalid")
        states = staged
        for tr in batch["transitions"]:
            last_event[tr["request_id"]] = eid
            if tr["to"] == "superseded":
                superseded_by[tr["request_id"]] = tr["replacement_request_id"]
                supersedes[tr["replacement_request_id"]] = tr["request_id"]
        applied.add(eid)
        tip = eid
    requests = {rid: RequestState(rid, st, last_event[rid], superseded_by.get(rid), supersedes.get(rid))
                for rid, st in states.items()}
    active = [rid for rid, st in states.items() if st == "active"]
    return ReplayResult(requests, tip, active[0] if active else None)


# ---------------------------------------------------------------------------
# Public receipt projection
# ---------------------------------------------------------------------------

class VerifiedApproval(NamedTuple):
    """What the verifier establishes about an approval: the request it names and the mechanism.
    Built only by verification code, never read from a proposed receipt or a request."""
    request_id: str
    type: str
    authenticated: bool


def _repo_artifacts(manifest_entries):
    out = []
    for e in manifest_entries:
        if not e["path"].startswith(("repo/", "payloads/")):
            _fail("manifest", "a snapshot file is outside repo/ and payloads/", "receipt-projection-mismatch")
        if e["path"].startswith("repo/"):
            rel = e["path"][len("repo/"):]
            check_path(rel, "manifest")
            if rel.startswith("docs/release/"):
                _fail("manifest", "a receipt or control file is listed as an artifact", "receipt-projection-mismatch")
            out.append({"path": rel, "sha256": e["sha256"], "bytes": e["bytes"], "mode": e["mode"]})
    return out


def project_receipt(request, manifest, verified_state, verified_approval):
    """The exact public receipt for one request, as canonical JSON bytes.

    Every field is built from verified inputs. request is the strict request (its digest is
    recomputed). manifest is the canonical content-manifest bytes or its parsed entries.
    verified_state is a RequestState from replay_state. verified_approval is a VerifiedApproval.
    A proposed receipt is not an input, and a plain dict is refused where a verified record is
    required. A mismatch raises SchemaError with code receipt-projection-mismatch."""
    validate_request(request)
    request_id = request["request_sha256"]
    entries = validate_manifest(manifest)
    manifest_bytes = bytes(manifest) if isinstance(manifest, (bytes, bytearray)) else canonical_json(entries)
    release_id = sha256_bytes(manifest_bytes)
    code = "receipt-projection-mismatch"
    if release_id != request["release_id"]:
        _fail("manifest", "does not match the request release id", code)
    if not isinstance(verified_state, RequestState):
        _fail("verified_state", "must be a RequestState produced by replay_state", code)
    if not isinstance(verified_approval, VerifiedApproval):
        _fail("verified_approval", "must be a VerifiedApproval produced by verification", code)
    if verified_state.request_id != request_id or verified_approval.request_id != request_id:
        _fail("verified_state", "names a different request", code)
    if verified_state.state not in RECEIPT_STATES:
        _fail("verified_state.state", "a request that was never activated has no receipt", code)
    _sha(verified_state.event_id, "verified_state.event_id")
    if verified_state.supersedes != request["supersedes_request_id"]:
        _fail("verified_state.supersedes", "disagrees with the approved supersedes_request_id", code)
    if (verified_state.state == "superseded") != (verified_state.superseded_by is not None):
        _fail("verified_state.superseded_by", "is set exactly when the state is superseded", code)
    if verified_approval.type not in APPROVAL_TYPES or verified_approval.authenticated is not APPROVAL_TYPES[verified_approval.type]:
        _fail("verified_approval", "mechanism and authentication disagree", code)
    template = request["receipt_template"]
    artifacts = _repo_artifacts(entries)
    if artifacts != template["artifacts"]:
        _fail("receipt_template.artifacts", "must equal the repository artifacts of the manifest", code)
    receipt = {
        "receipt_format": template["receipt_format"],
        "request_id": request_id,
        "release_id": release_id,
        "content_manifest_sha256": release_id,
        "created": template["created"],
        "state": verified_state.state,
        "event_id": verified_state.event_id,
        "supersedes": request["supersedes_request_id"],
        "superseded_by": verified_state.superseded_by,
        "expires_at": template["expires_at"],
        "audience": template["audience"],
        "destinations": list(template["destinations"]),
        "targets": [dict(t) for t in template["targets"]],
        "sources": [dict(s) for s in template["sources"]],
        "artifacts": artifacts,
        "downstream": dict(template["downstream"]),
        "offline_grace_days": template["offline_grace_days"],
        "approval": {"type": verified_approval.type, "authenticated": verified_approval.authenticated, "ref": request_id},
        "enrollment_id": template["enrollment_id"],
    }
    validate_receipt(receipt)
    return canonical_json(receipt)


def verify_receipt_bytes(actual, request, manifest, verified_state, verified_approval):
    """Raise SchemaError (receipt-projection-mismatch) unless actual, the bytes of a receipt file,
    equal project_receipt of the verified inputs byte for byte. Returns None."""
    expected = project_receipt(request, manifest, verified_state, verified_approval)
    try:
        loads_strict(actual)
    except SchemaError:
        _fail("receipt", "is not strict JSON", "receipt-projection-mismatch")
    if bytes(actual) != expected:
        _fail("receipt", "differs from the projection of the verified records", "receipt-projection-mismatch")


# ---------------------------------------------------------------------------
# Command line: this module is a library. Running it only prints its help.
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Offline schema and digest functions for confidential releases (canonical JSON, release id, "
                    "request id, event id, receipt projection, state replay). A library: import it, do not run it. "
                    "Standard library only; it reads no network and no token.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
