#!/usr/bin/env python3
"""Pure builders for the records of a release: manifest, receipt template, request, event batch and the
files of a staging candidate branch. Standard library only. No network, no environment, no checkout.

The builders compute every digest from bytes (release_schema) and validate what they build, so a
record this module returns is already a strict, canonical record. They hold no policy and make no
decision: the release gate and release_verify decide. release.py gathers the inputs (plan, snapshot,
policy) and calls these functions; the tests build records with them too.

This module is imported by the other scripts. Run with --help to see this text.
"""
import argparse
import secrets
import sys

import release_schema as RS
import release_verify as V

ACTIVATE_REASON = "release-approved"
SUPERSEDE_REASON = "replaced"
# The reasons an owner may give for a withdrawal. They are fixed words: the private story stays private.
WITHDRAW_REASONS = ("error-found", "no-longer-needed", "source-changed", "policy-changed", "access-changed", "other")


def new_nonce():
    """A fresh random 128-bit nonce as 32 lowercase hexadecimal characters."""
    return secrets.token_hex(16)


def derived_nonce(nonce, label):
    """A nonce derived from another, so a reproducible run (--nonce) gets reproducible event ids."""
    return RS.sha256_text(f"{nonce}:{label}")[:32]


def now_text():
    return V.utc_text(V.clock())


def build_manifest(files, modes=None):
    """(manifest bytes, release id, entries) for files, a mapping of snapshot path to bytes. Every file
    is 100644 unless modes names it 100755. The manifest is canonical and sorted by path."""
    modes = dict(modes or {})
    entries = []
    for path in sorted(files):
        data = bytes(files[path])
        entries.append({"path": path, "sha256": RS.sha256_bytes(data), "bytes": len(data), "mode": modes.get(path, "100644")})
    manifest, release_id = RS.manifest_from_entries(entries)
    return manifest, release_id, RS.validate_manifest(manifest)


def build_template(release_id, entries, *, created, expires_at, audience, destinations, targets, sources, downstream,
                   offline_grace_days, enrollment_id):
    """The receipt template of a request (E4): exactly the static field list. release_id is the digest of
    the manifest and entries are its entries; the artifact list is their repository projection."""
    return {
        "receipt_format": 1, "content_manifest_sha256": release_id, "created": created, "expires_at": expires_at,
        "audience": audience, "destinations": [d for d in RS.DESTINATIONS if d in destinations],
        "targets": sorted((dict(t) for t in targets), key=lambda t: t["id"]),
        "sources": sorted((dict(s) for s in sources), key=lambda s: s["id"]),
        "artifacts": V.expected_artifacts(entries),
        "downstream": dict(downstream), "offline_grace_days": offline_grace_days, "enrollment_id": enrollment_id,
    }


def build_request(template, release_id, policy, *, created, nonce, supersedes=None, preview, exceptions=()):
    """The complete approval request with its request_sha256, validated. policy supplies
    policy_commit_sha, policy_sha256 and enrollment_id (an Enrollment or a LocalPolicy). The template
    gets the manifest digest, creation time and enrollment id of the request, so the three agree."""
    template = dict(template)
    template["content_manifest_sha256"] = release_id
    template["created"] = created
    template["enrollment_id"] = policy.enrollment_id
    request = {
        "request_format": 1, "release_id": release_id, "request_nonce": nonce, "created": created,
        "policy_commit_sha": policy.policy_commit_sha, "policy_sha256": policy.policy_sha256,
        "enrollment_id": policy.enrollment_id, "activate": True, "supersedes_request_id": supersedes,
        "receipt_template": {k: template[k] for k in RS.TEMPLATE_KEYS}, "preview": preview,
        "detector_exceptions": [dict(e) for e in exceptions],
    }
    request["request_sha256"] = RS.hash_request(request)
    RS.validate_request(request)
    return request


def build_event(transitions, policy, *, created, nonce):
    """An event batch with its event_id, validated. transitions is a list of dicts with request_id,
    from, to, previous_event_id, replacement_request_id and reason_code."""
    batch = {
        "event_format": 1, "event_nonce": nonce, "policy_commit_sha": policy.policy_commit_sha,
        "policy_sha256": policy.policy_sha256, "created": created,
        "transitions": [dict(t) for t in transitions],
    }
    batch["event_id"] = RS.hash_event(batch)
    RS.validate_event(batch)
    return batch


def transition(request_id, frm, to, previous_event_id, reason_code, replacement_request_id=None):
    return {"request_id": request_id, "from": frm, "to": to, "previous_event_id": previous_event_id,
            "replacement_request_id": replacement_request_id, "reason_code": reason_code}


def activation_event(request, policy, tip, *, created, nonce):
    """The batch that activates a request (D13): one prepared to active transition, or, when the request
    replaces another, the atomic pair that supersedes the current request and activates the new one."""
    rid = request["request_sha256"]
    steps = []
    old = request["supersedes_request_id"]
    if old:
        steps.append(transition(old, "active", "superseded", tip, SUPERSEDE_REASON, rid))
    steps.append(transition(rid, "prepared", "active", tip, ACTIVATE_REASON))
    return build_event(steps, policy, created=created, nonce=nonce)


def withdrawal_event(request_id, policy, tip, reason_code, *, created, nonce):
    """The batch that withdraws an active request. The reason is one of WITHDRAW_REASONS."""
    if reason_code not in WITHDRAW_REASONS:
        raise RS.SchemaError("schema-invalid", "reason", "must be one of " + ", ".join(WITHDRAW_REASONS))
    return build_event([transition(request_id, "active", "withdrawn", tip, reason_code)], policy, created=created, nonce=nonce)


def canonical_bytes(record):
    return RS.canonical_json(record)


def request_branch_files(request, manifest_bytes, snapshot_files, event):
    """What a request/<id> branch adds in the staging repository (D10 item 1): the snapshot and the
    manifest under releases/<release id>/, the request under requests/<id>/ and the activation batch
    under events/. Nothing else: no original, no staffing file, no approval record."""
    release_id = request["release_id"]
    out = {f"releases/{release_id}/content-manifest.json": bytes(manifest_bytes),
           f"requests/{request['request_sha256']}/approval-request.json": canonical_bytes(request),
           f"events/{event['event_id']}.json": canonical_bytes(event)}
    for path, data in snapshot_files.items():
        out[f"releases/{release_id}/snapshot/{path}"] = bytes(data)
    return out


def state_branch_files(event):
    """What a state/<event id> branch adds: only the event batch."""
    return {f"events/{event['event_id']}.json": canonical_bytes(event)}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Pure builders for the records of a release (manifest, receipt template, request, event "
                    "batch, staging branch files). A library: import it, do not run it. Standard library only.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
