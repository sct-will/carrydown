"""Offline tests for scripts/release_schema.py and the thin wrappers in carrydown_lib.

They cover canonical JSON, the digest exclusions of the content manifest, request and event,
the strict validators, the state replay and the public receipt projection. No token, no network.
Run from the repository root: python -m unittest discover -s tests -v
"""
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import release_gate as RG  # noqa: E402
import release_schema as RS  # noqa: E402


def H(label):
    """A full, fake digest that is stable for a label."""
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


TIME = "2027-01-20T14:03:00Z"


def build_snapshot(base):
    """A snapshot folder with repository artifacts and one GitHub payload."""
    files = {
        "repo/docs/spec/plan.yaml": "project:\n  name: x\n",
        "repo/docs/context/wi-06.md": "# Approved context for WI-06\n",
        "repo/docs/context/wi-06.bundle.json": '{"bundle_format":1}\n',
        "payloads/issue/WI-06.json": '{"title":"WI-06"}\n',
    }
    for rel, text in files.items():
        p = Path(base) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
    return Path(base)


def repo_artifacts(manifest_bytes):
    out = []
    for e in json.loads(manifest_bytes):
        if e["path"].startswith("repo/"):
            out.append(dict(e, path=e["path"][len("repo/"):]))
    return out


def make_request(manifest_bytes, supersedes=None, nonce="a1" * 16, **override):
    release_id = RS.release_id_of(manifest_bytes)
    template = {
        "receipt_format": 1,
        "content_manifest_sha256": release_id,
        "created": TIME,
        "expires_at": None,
        "audience": "repo-readers",
        "destinations": ["engineering-repo", "issue", "engineers-skill"],
        "targets": [
            {"id": "board", "host": "github.com", "repository_id": 4200, "owner_id": 4400, "project_id": "PVT_example"},
            {"id": "engineering", "host": "github.com", "repository_id": 4200, "repository": "acme/expense-approvals"},
        ],
        "sources": [{"id": "architecture", "version": "0.3"}, {"id": "company-governance", "version": "2027.1"}],
        "artifacts": repo_artifacts(manifest_bytes),
        "downstream": {"assignees": True, "capacity_summary": False, "evidence": "synthetic-only"},
        "offline_grace_days": 7,
        "enrollment_id": H("enrollment"),
    }
    request = {
        "request_format": 1,
        "release_id": release_id,
        "request_nonce": nonce,
        "created": TIME,
        "policy_commit_sha": "8b" * 20,
        "policy_sha256": H("policy"),
        "enrollment_id": H("enrollment"),
        "activate": True,
        "supersedes_request_id": supersedes,
        "receipt_template": template,
        "preview": {"what": "Bundles", "with_whom": "Repository readers", "where": "The engineering repository",
                    "remains_private": "Staffing records"},
        "detector_exceptions": [],
    }
    request.update(override)
    request["request_sha256"] = RS.hash_request(request)
    return request


def transition(request_id, old, new, previous, replacement=None, reason="owner-decision"):
    return {"request_id": request_id, "from": old, "to": new, "previous_event_id": previous,
            "replacement_request_id": replacement, "reason_code": reason}


def make_event(transitions, seed="1"):
    batch = {"event_format": 1, "event_nonce": hashlib.sha256(seed.encode()).hexdigest()[:32],
             "policy_commit_sha": "8b" * 20, "policy_sha256": H("policy"), "created": TIME,
             "transitions": transitions}
    batch["event_id"] = RS.hash_event(batch)
    return batch


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-release-schema-")
        self.addCleanup(self.temp.cleanup)
        self.snapshot = build_snapshot(Path(self.temp.name) / "snapshot")
        self.manifest, self.release_id = RS.hash_manifest(self.snapshot)

    def fails(self, exc, call, *args, **kwargs):
        """Run call and return the exception of type exc that it raised. No error is a test failure."""
        try:
            call(*args, **kwargs)
        except exc as error:
            return error
        self.fail("%s did not raise %s" % (getattr(call, "__name__", call), exc.__name__))

    def refuses(self, code, call, *args, **kwargs):
        error = self.fails(RS.SchemaError, call, *args, **kwargs)
        self.assertEqual(error.code, code, str(error))
        return error


class CanonicalJsonTests(Base):
    def test_sorted_keys_no_whitespace_one_trailing_lf(self):
        out = RS.canonical_json({"b": [3, 1, {"z": 1, "a": 2}], "a": "x y", "c": None, "d": True})
        self.assertEqual(out, b'{"a":"x y","b":[3,1,{"a":2,"z":1}],"c":null,"d":true}\n')
        self.assertTrue(out.endswith(b"\n") and not out.endswith(b"\n\n"))

    def test_key_order_of_the_input_does_not_matter_and_arrays_keep_order(self):
        a = RS.canonical_json({"x": 1, "y": [2, 1]})
        b = RS.canonical_json({"y": [2, 1], "x": 1})
        self.assertEqual(a, b)
        self.assertNotEqual(a, RS.canonical_json({"x": 1, "y": [1, 2]}))

    def test_utf8_not_escaped(self):
        out = RS.canonical_json({"k": "caf\u00e9"})
        self.assertEqual(out, '{"k":"caf\u00e9"}\n'.encode("utf-8"))

    def test_bytes_input_is_parsed_then_canonicalized(self):
        self.assertEqual(RS.canonical_json(b'{ "b" : 1,\n "a" : 2 }'), b'{"a":2,"b":1}\n')

    def test_a_str_is_a_json_string_value_not_a_document(self):
        self.assertEqual(RS.canonical_json('{"a":1}'), b'"{\\"a\\":1}"\n')

    def test_duplicate_keys_are_rejected_on_input(self):
        self.refuses("schema-invalid", RS.canonical_json, b'{"a":1,"a":2}')
        self.refuses("schema-invalid", RS.canonical_json, b'{"a":{"b":1,"b":1}}')
        self.refuses("schema-invalid", RS.loads_strict, '{"a":1,"a":1}')

    def test_non_finite_numbers_are_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            self.refuses("schema-invalid", RS.canonical_json, {"n": bad})
        for raw in (b'{"n":NaN}', b'{"n":Infinity}', b'{"n":-Infinity}'):
            self.refuses("schema-invalid", RS.canonical_json, raw)

    def test_non_text_keys_and_unknown_types_are_rejected(self):
        self.refuses("schema-invalid", RS.canonical_json, {1: "a"})
        self.refuses("schema-invalid", RS.canonical_json, {"a": object()})
        self.refuses("schema-invalid", RS.canonical_json, {"a": {"b"}})

    def test_invalid_json_and_bad_encoding_are_rejected(self):
        self.refuses("schema-invalid", RS.canonical_json, b"{not json")
        self.refuses("schema-invalid", RS.canonical_json, b"\xff\xfe")

    def test_sha256_bytes_known_value(self):
        self.assertEqual(RS.sha256_bytes(b"abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


class ManifestTests(Base):
    def test_manifest_is_canonical_sorted_and_the_release_id_is_its_digest(self):
        entries = json.loads(self.manifest)
        self.assertEqual([e["path"] for e in entries], sorted(e["path"] for e in entries))
        self.assertEqual(set(entries[0]), {"path", "sha256", "bytes", "mode"})
        self.assertEqual({e["mode"] for e in entries}, {"100644"})
        self.assertEqual(self.release_id, hashlib.sha256(self.manifest).hexdigest())
        self.assertEqual(self.manifest, RS.canonical_json(entries))
        self.assertEqual(len(entries), 4)
        self.assertEqual(RS.validate_manifest(self.manifest), entries)

    def test_digest_is_stable_whatever_order_files_were_written(self):
        other = Path(self.temp.name) / "other"
        for rel in reversed(sorted(str(p.relative_to(self.snapshot)) for p in self.snapshot.rglob("*") if p.is_file())):
            target = other / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.snapshot / rel, target)
        self.assertEqual(RS.hash_manifest(other), (self.manifest, self.release_id))

    def test_one_changed_byte_changes_the_release_id(self):
        path = self.snapshot / "repo/docs/spec/plan.yaml"
        path.write_bytes(path.read_bytes() + b" ")
        manifest, release_id = RS.hash_manifest(self.snapshot)
        self.assertNotEqual(release_id, self.release_id)

    def test_approved_executable_mode_changes_the_id_and_unknown_paths_are_refused(self):
        manifest, release_id = RS.hash_manifest(self.snapshot, modes={"repo/docs/spec/plan.yaml": "100755"})
        self.assertNotEqual(release_id, self.release_id)
        self.assertIn("100755", manifest.decode("utf-8"))
        self.refuses("unsafe-artifact-path", RS.hash_manifest, self.snapshot, modes={"repo/missing.txt": "100755"})
        self.refuses("unsafe-artifact-path", RS.hash_manifest, self.snapshot, modes={"repo/docs/spec/plan.yaml": "100664"})

    def test_symbolic_link_and_git_internals_are_refused_before_hashing(self):
        link = self.snapshot / "repo/docs/link.md"
        try:
            os.symlink(str(self.snapshot / "repo/docs/spec/plan.yaml"), str(link))
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are not available here")
        self.refuses("unsafe-artifact-path", RS.hash_manifest, self.snapshot)
        link.unlink()
        (self.snapshot / "repo/.git").mkdir()
        self.refuses("unsafe-artifact-path", RS.hash_manifest, self.snapshot)

    def entry(self, **over):
        e = {"path": "repo/a.txt", "sha256": H("a"), "bytes": 1, "mode": "100644"}
        e.update(over)
        return e

    def test_unsafe_paths_are_rejected(self):
        for bad in ("/etc/passwd", "../outside.txt", "repo/../../x", "repo/a/../b", "repo//a", "repo/./a", "a\\b", "C:/x",
                    "", "repo/a/", "repo/.git/config", "repo/.GIT", "repo/a:b", "repo/a\nb"):
            with self.subTest(path=bad):
                self.refuses("unsafe-artifact-path", RS.manifest_from_entries, [self.entry(path=bad)])

    def test_duplicate_and_case_colliding_paths_are_rejected(self):
        self.refuses("unsafe-artifact-path", RS.manifest_from_entries, [self.entry(), self.entry()])
        self.refuses("unsafe-artifact-path", RS.manifest_from_entries,
                     [self.entry(path="repo/Docs/A.md"), self.entry(path="repo/docs/a.md")])

    def test_modes_other_than_the_two_allowed_are_rejected(self):
        RS.manifest_from_entries([self.entry(mode="100755")])
        for bad in ("100664", "120000", "160000", "040000", "644", 100644, None):
            with self.subTest(mode=bad):
                self.refuses("unsafe-artifact-path", RS.manifest_from_entries, [self.entry(mode=bad)])

    def test_abbreviated_and_uppercase_digests_are_rejected(self):
        for bad in (H("a")[:12], H("a").upper(), "sha256:" + H("a"), H("a") + "0", "", None):
            with self.subTest(sha=bad):
                self.refuses("schema-invalid", RS.manifest_from_entries, [self.entry(sha256=bad)])

    def test_unknown_and_missing_fields_and_bad_sizes_are_rejected(self):
        self.refuses("schema-invalid", RS.manifest_from_entries, [dict(self.entry(), extra=1)])
        missing = self.entry()
        del missing["mode"]
        self.refuses("schema-invalid", RS.manifest_from_entries, [missing])
        for bad in (-1, True, 1.5, "1"):
            self.refuses("schema-invalid", RS.manifest_from_entries, [self.entry(bytes=bad)])

    def test_validate_manifest_requires_sorted_entries_and_canonical_bytes(self):
        entries = json.loads(self.manifest)
        self.refuses("schema-invalid", RS.validate_manifest, list(reversed(entries)))
        pretty = json.dumps(entries, indent=2).encode("utf-8")
        self.refuses("schema-invalid", RS.validate_manifest, pretty)
        self.refuses("schema-invalid", RS.validate_manifest, self.manifest.rstrip(b"\n"))
        self.refuses("schema-invalid", RS.validate_manifest, {"files": entries})

    def test_manifest_from_entries_sorts_and_matches_hash_manifest(self):
        entries = list(reversed(json.loads(self.manifest)))
        self.assertEqual(RS.manifest_from_entries(entries), (self.manifest, self.release_id))


class RequestTests(Base):
    def setUp(self):
        super().setUp()
        self.request = make_request(self.manifest)

    def test_a_valid_request_validates_and_its_digest_is_recomputed(self):
        RS.validate_request(self.request)
        self.assertEqual(RS.hash_request(self.request), self.request["request_sha256"])
        self.assertRegex(self.request["request_sha256"], r"^[0-9a-f]{64}$")

    def test_changing_request_sha256_does_not_change_the_recomputed_digest(self):
        base = RS.hash_request(self.request)
        for value in (H("other"), "x", None, 7):
            changed = dict(self.request, request_sha256=value)
            self.assertEqual(RS.hash_request(changed), base)
        without = {k: v for k, v in self.request.items() if k != "request_sha256"}
        self.assertEqual(RS.hash_request(without), base)

    def test_changing_any_other_field_changes_the_digest(self):
        base = RS.hash_request(self.request)

        def tweak(path, value):
            r = copy.deepcopy(self.request)
            target = r
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            return r

        changes = [
            (("request_nonce",), "b2" * 16),
            (("policy_commit_sha",), "9c" * 20),
            (("policy_sha256",), H("policy 2")),
            (("supersedes_request_id",), H("older")),
            (("preview", "what"), "Something else"),
            (("detector_exceptions",), [{"type": "copied-passage", "passage_sha256": H("p"), "destinations": ["issue"], "reason": "approved quote"}]),
            (("receipt_template", "expires_at"), "2028-01-01T00:00:00Z"),
            (("receipt_template", "audience"), "public"),
            (("receipt_template", "destinations"), ["engineering-repo"]),
            (("receipt_template", "offline_grace_days"), 3),
            (("receipt_template", "downstream", "assignees"), False),
            (("receipt_template", "sources"), [{"id": "architecture", "version": "0.4"}]),
            (("receipt_template", "targets"), [self.request["receipt_template"]["targets"][1]]),
        ]
        for path, value in changes:
            with self.subTest(field=".".join(path)):
                self.assertNotEqual(RS.hash_request(tweak(path, value)), base)
        # fields that the schema ties together change as a pair
        r = copy.deepcopy(self.request)
        r["created"] = "2027-01-21T00:00:00Z"
        r["receipt_template"]["created"] = r["created"]
        self.assertNotEqual(RS.hash_request(r), base)
        r = copy.deepcopy(self.request)
        r["enrollment_id"] = r["receipt_template"]["enrollment_id"] = H("enrollment 2")
        self.assertNotEqual(RS.hash_request(r), base)
        r = copy.deepcopy(self.request)
        r["release_id"] = r["receipt_template"]["content_manifest_sha256"] = H("release 2")
        self.assertNotEqual(RS.hash_request(r), base)

    def test_a_stored_digest_that_does_not_match_its_input_fails(self):
        forged = dict(self.request, request_sha256=H("forged"))
        self.refuses("sha256-mismatch", RS.validate_request, forged)
        edited = copy.deepcopy(self.request)
        edited["receipt_template"]["audience"] = "public"
        self.refuses("sha256-mismatch", RS.validate_request, edited)
        edited = dict(self.request, request_nonce="c3" * 16)
        self.refuses("sha256-mismatch", RS.validate_request, edited)

    def test_missing_digest_is_refused_unless_the_caller_asks_for_the_hash_only(self):
        without = {k: v for k, v in self.request.items() if k != "request_sha256"}
        self.refuses("schema-invalid", RS.validate_request, without)
        RS.validate_request(without, check_digest=False)

    def test_unknown_fields_are_rejected_everywhere(self):
        self.refuses("schema-invalid", RS.validate_request, dict(self.request, extra=1))
        for place in (("receipt_template",), ("receipt_template", "downstream"), ("receipt_template", "sources", 0),
                      ("receipt_template", "targets", 0), ("receipt_template", "artifacts", 0)):
            r = copy.deepcopy(self.request)
            target = r
            for key in place:
                target = target[key]
            target["extra"] = 1
            with self.subTest(place=place):
                self.refuses("schema-invalid", RS.hash_request, r)

    def test_the_template_cannot_supply_derived_fields(self):
        for key in ("release_id", "request_id", "state", "event_id", "supersedes", "superseded_by", "approval"):
            r = copy.deepcopy(self.request)
            r["receipt_template"][key] = H(key)
            with self.subTest(key=key):
                self.refuses("schema-invalid", RS.hash_request, r)

    def test_template_must_agree_with_the_request(self):
        for field, value in (("created", "2027-02-01T00:00:00Z"), ("enrollment_id", H("someone else")),
                             ("content_manifest_sha256", H("another manifest"))):
            r = copy.deepcopy(self.request)
            r["receipt_template"][field] = value
            with self.subTest(field=field):
                self.refuses("schema-invalid", RS.hash_request, r)

    def test_abbreviated_digests_nonce_and_times_are_rejected(self):
        for field, bad in (("release_id", H("x")[:16]), ("policy_sha256", H("x")[:7]), ("enrollment_id", "7c1e..."),
                           ("request_nonce", "a1" * 8), ("request_nonce", "A1" * 16), ("policy_commit_sha", "8b4d"),
                           ("created", "2027-01-20"), ("created", "2027-13-20T14:03:00Z"), ("supersedes_request_id", "1a2b"),
                           ("activate", False), ("activate", 1), ("request_format", 2), ("preview", {}), ("preview", "text")):
            r = copy.deepcopy(self.request)
            r[field] = bad
            with self.subTest(field=field, bad=bad):
                self.refuses("schema-invalid", RS.hash_request, r)

    def test_artifact_paths_in_the_template_are_checked(self):
        r = copy.deepcopy(self.request)
        r["receipt_template"]["artifacts"][0]["path"] = "../x"
        self.refuses("unsafe-artifact-path", RS.hash_request, r)
        r = copy.deepcopy(self.request)
        r["receipt_template"]["artifacts"][0]["mode"] = "120000"
        self.refuses("unsafe-artifact-path", RS.hash_request, r)
        r = copy.deepcopy(self.request)
        r["receipt_template"]["artifacts"].reverse()
        self.refuses("schema-invalid", RS.hash_request, r)

    def test_detector_exceptions_hold_only_the_allowed_fields(self):
        good = {"type": "copied-passage", "passage_sha256": H("p"), "destinations": ["issue"], "reason": "approved quote"}
        r = make_request(self.manifest, detector_exceptions=[good])
        RS.validate_request(r)
        for bad in (dict(good, passage="the passage itself"), dict(good, passage_sha256=H("p")[:8]),
                    dict(good, destinations=["somewhere"]), dict(good, destinations=[])):
            r = copy.deepcopy(self.request)
            r["detector_exceptions"] = [bad]
            with self.subTest(bad=bad):
                self.refuses("schema-invalid", RS.hash_request, r)


class EventTests(Base):
    def setUp(self):
        super().setUp()
        self.r1 = H("request 1")
        self.event = make_event([transition(self.r1, "prepared", "active", None)])

    def test_event_digest_excludes_only_event_id(self):
        base = RS.hash_event(self.event)
        self.assertEqual(self.event["event_id"], base)
        for value in (H("other"), None, "x"):
            self.assertEqual(RS.hash_event(dict(self.event, event_id=value)), base)
        self.assertEqual(RS.hash_event({k: v for k, v in self.event.items() if k != "event_id"}), base)
        RS.validate_event(self.event)

    def test_changing_any_other_field_changes_the_digest(self):
        base = RS.hash_event(self.event)
        for field, value in (("event_nonce", "ff" * 16), ("policy_commit_sha", "9c" * 20), ("policy_sha256", H("p2")),
                             ("created", "2027-01-21T00:00:00Z")):
            with self.subTest(field=field):
                self.assertNotEqual(RS.hash_event(dict(self.event, **{field: value})), base)
        for field, value in (("request_id", H("r2")), ("reason_code", "other-reason"), ("previous_event_id", H("p"))):
            changed = copy.deepcopy(self.event)
            changed["transitions"][0][field] = value
            with self.subTest(field=field):
                self.assertNotEqual(RS.hash_event(changed), base)

    def test_a_stored_event_id_that_does_not_match_fails(self):
        self.refuses("sha256-mismatch", RS.validate_event, dict(self.event, event_id=H("forged")))
        edited = copy.deepcopy(self.event)
        edited["transitions"][0]["reason_code"] = "edited"
        self.refuses("sha256-mismatch", RS.validate_event, edited)

    def test_unknown_fields_abbreviated_digests_and_shapes_are_rejected(self):
        self.refuses("schema-invalid", RS.hash_event, dict(self.event, extra=1))
        changed = copy.deepcopy(self.event)
        changed["transitions"][0]["by"] = "someone"
        self.refuses("schema-invalid", RS.hash_event, changed)
        changed = copy.deepcopy(self.event)
        changed["transitions"][0]["request_id"] = "5b8c"
        self.refuses("schema-invalid", RS.hash_event, changed)
        self.refuses("schema-invalid", RS.hash_event, dict(self.event, transitions=[]))
        self.refuses("schema-invalid", RS.hash_event, dict(self.event, event_nonce="ab"))

    def test_only_the_three_transitions_exist(self):
        for old, new in (("withdrawn", "active"), ("superseded", "active"), ("prepared", "withdrawn"),
                         ("active", "active"), ("prepared", "superseded"), ("active", "prepared")):
            batch = copy.deepcopy(self.event)
            batch["transitions"][0].update({"from": old, "to": new})
            with self.subTest(old=old, new=new):
                self.refuses("state-history-invalid", RS.hash_event, batch)

    def test_replacement_is_only_for_supersession_and_must_activate_in_the_same_batch(self):
        batch = copy.deepcopy(self.event)
        batch["transitions"][0]["replacement_request_id"] = H("r2")
        self.refuses("schema-invalid", RS.hash_event, batch)
        r2 = H("request 2")
        lonely = [transition(self.r1, "active", "superseded", H("e0"), replacement=r2)]
        self.refuses("state-history-invalid", RS.hash_event, {**self.event, "transitions": lonely})
        pair = [transition(self.r1, "active", "superseded", H("e0"), replacement=r2),
                transition(r2, "prepared", "active", H("e0"))]
        RS.hash_event({**self.event, "transitions": pair})

    def test_one_batch_names_one_predecessor_and_one_activation(self):
        mixed = [transition(self.r1, "active", "withdrawn", H("e0")), transition(H("r9"), "prepared", "active", None)]
        self.refuses("state-history-invalid", RS.hash_event, {**self.event, "transitions": mixed})
        twice = [transition(self.r1, "prepared", "active", None), transition(self.r1, "active", "withdrawn", None)]
        self.refuses("state-history-invalid", RS.hash_event, {**self.event, "transitions": twice})


class ReplayTests(Base):
    def setUp(self):
        super().setUp()
        self.r1, self.r2, self.r3 = H("request 1"), H("request 2"), H("request 3")
        self.e1 = make_event([transition(self.r1, "prepared", "active", None, reason="first-release")], "e1")
        self.e2 = make_event([transition(self.r1, "active", "superseded", self.e1["event_id"], replacement=self.r2, reason="replaced"),
                              transition(self.r2, "prepared", "active", self.e1["event_id"], reason="replaced")], "e2")
        self.e3 = make_event([transition(self.r2, "active", "withdrawn", self.e2["event_id"], reason="withdrawn-by-owner")], "e3")

    def test_empty_history_has_no_tip_and_no_active_request(self):
        result = RS.replay_state([])
        self.assertEqual((result.requests, result.tip, result.active), ({}, None, None))

    def test_first_approval_activates_without_a_preexisting_state_file(self):
        result = RS.replay_state([self.e1])
        self.assertEqual(result.active, self.r1)
        self.assertEqual(result.tip, self.e1["event_id"])
        self.assertEqual(result.requests[self.r1], RS.RequestState(self.r1, "active", self.e1["event_id"], None, None))

    def test_replacement_supersedes_and_activates_in_one_batch(self):
        result = RS.replay_state([self.e1, self.e2])
        self.assertEqual(result.active, self.r2)
        self.assertEqual(result.requests[self.r1], RS.RequestState(self.r1, "superseded", self.e2["event_id"], self.r2, None))
        self.assertEqual(result.requests[self.r2], RS.RequestState(self.r2, "active", self.e2["event_id"], None, self.r1))

    def test_withdrawal_leaves_history_and_no_active_request(self):
        result = RS.replay_state([self.e1, self.e2, self.e3])
        self.assertIsNone(result.active)
        self.assertEqual(result.tip, self.e3["event_id"])
        self.assertEqual(result.requests[self.r2].state, "withdrawn")
        self.assertEqual(result.requests[self.r2].event_id, self.e3["event_id"])
        self.assertEqual(result.requests[self.r1].state, "superseded")

    def test_reapproval_after_withdrawal_is_a_new_request(self):
        e4 = make_event([transition(self.r3, "prepared", "active", self.e3["event_id"], reason="reapproved")], "e4")
        result = RS.replay_state([self.e1, self.e2, self.e3, e4])
        self.assertEqual(result.active, self.r3)
        self.assertEqual(result.requests[self.r2].state, "withdrawn")

    def test_a_duplicate_event_is_idempotent(self):
        once = RS.replay_state([self.e1, self.e2])
        again = RS.replay_state([self.e1, self.e1, self.e2, self.e2, self.e1])
        self.assertEqual(once, again)

    def test_conflicting_predecessor_is_refused(self):
        competing = make_event([transition(self.r1, "active", "superseded", self.e1["event_id"], replacement=self.r3),
                                transition(self.r3, "prepared", "active", self.e1["event_id"])], "competing")
        self.refuses("state-history-invalid", RS.replay_state, [self.e1, self.e2, competing])
        wrong = make_event([transition(self.r1, "prepared", "active", H("not the tip"))], "wrong")
        self.refuses("state-history-invalid", RS.replay_state, [wrong])
        first_is_not_null = make_event([transition(self.r1, "prepared", "active", H("e0"))], "x")
        self.refuses("state-history-invalid", RS.replay_state, [first_is_not_null])

    def test_events_out_of_merge_order_are_refused(self):
        self.refuses("state-history-invalid", RS.replay_state, [self.e2, self.e1])

    def test_terminal_to_active_is_refused(self):
        revive = make_event([transition(self.r1, "prepared", "active", self.e3["event_id"], reason="revive")], "revive")
        self.refuses("state-history-invalid", RS.replay_state, [self.e1, self.e2, self.e3, revive])
        again = make_event([transition(self.r2, "prepared", "active", self.e3["event_id"], reason="revive")], "again")
        self.refuses("state-history-invalid", RS.replay_state, [self.e1, self.e2, self.e3, again])
        withdraw_twice = make_event([transition(self.r2, "active", "withdrawn", self.e3["event_id"])], "twice")
        self.refuses("state-history-invalid", RS.replay_state, [self.e1, self.e2, self.e3, withdraw_twice])

    def test_a_second_active_request_is_refused(self):
        second = make_event([transition(self.r2, "prepared", "active", self.e1["event_id"])], "second")
        self.refuses("state-history-invalid", RS.replay_state, [self.e1, second])

    def test_a_transition_from_the_wrong_state_is_refused(self):
        never_active = make_event([transition(self.r2, "active", "withdrawn", None)], "never")
        self.refuses("state-history-invalid", RS.replay_state, [never_active])
        wrong = make_event([transition(self.r1, "active", "withdrawn", self.e1["event_id"])], "wrong2")
        self.refuses("state-history-invalid", RS.replay_state, [wrong])

    def test_an_unauthorized_actor_is_refused(self):
        self.refuses("state-history-invalid", RS.replay_state, [self.e1, self.e2], authorized=lambda b: b["event_id"] != self.e2["event_id"])
        self.refuses("state-history-invalid", RS.replay_state, [self.e1], authorized=lambda b: None)
        RS.replay_state([self.e1, self.e2], authorized=lambda b: True)

    def test_a_forged_event_id_is_refused(self):
        forged = dict(self.e1, event_id=H("forged"))
        self.refuses("sha256-mismatch", RS.replay_state, [forged])

    def test_events_that_replay_cannot_read_are_refused(self):
        self.refuses("schema-invalid", RS.replay_state, [dict(self.e1, extra=1)])
        self.refuses("schema-invalid", RS.replay_state, [{"event_id": H("x")}])


class ReceiptTests(Base):
    def setUp(self):
        super().setUp()
        self.request = make_request(self.manifest)
        self.rid = self.request["request_sha256"]
        self.e1 = make_event([transition(self.rid, "prepared", "active", None)], "r-e1")
        self.state = RS.replay_state([self.e1]).requests[self.rid]
        self.approval = RS.VerifiedApproval(self.rid, "github-review", True)

    def project(self, **over):
        args = dict(request=self.request, manifest=self.manifest, verified_state=self.state, verified_approval=self.approval)
        args.update(over)
        return RS.project_receipt(args["request"], args["manifest"], args["verified_state"], args["verified_approval"])

    def test_projection_has_exactly_the_e4_field_set_in_canonical_bytes(self):
        out = self.project()
        receipt = json.loads(out)
        self.assertEqual(set(receipt), set(RS.RECEIPT_KEYS))
        self.assertEqual(set(receipt), {
            "receipt_format", "request_id", "release_id", "content_manifest_sha256", "created", "state", "event_id", "supersedes",
            "superseded_by", "expires_at", "audience", "destinations", "targets", "sources", "artifacts", "downstream",
            "offline_grace_days", "approval", "enrollment_id"})
        self.assertEqual(set(receipt["approval"]), {"type", "authenticated", "ref"})
        self.assertEqual(out, RS.canonical_json(receipt))
        self.assertTrue(out.endswith(b"\n") and not out.endswith(b"\n\n"))
        RS.validate_receipt(out)

    def test_values_come_from_the_verified_inputs(self):
        receipt = json.loads(self.project())
        self.assertEqual(receipt["request_id"], self.rid)
        self.assertEqual(receipt["release_id"], self.release_id)
        self.assertEqual(receipt["content_manifest_sha256"], self.release_id)
        self.assertEqual((receipt["state"], receipt["event_id"]), ("active", self.e1["event_id"]))
        self.assertEqual((receipt["supersedes"], receipt["superseded_by"]), (None, None))
        self.assertEqual(receipt["approval"], {"type": "github-review", "authenticated": True, "ref": self.rid})
        self.assertEqual(receipt["audience"], "repo-readers")
        self.assertEqual(receipt["enrollment_id"], H("enrollment"))

    def test_artifacts_are_the_repository_files_without_repo_prefix_payloads_and_receipts(self):
        receipt = json.loads(self.project())
        paths = [a["path"] for a in receipt["artifacts"]]
        self.assertEqual(paths, ["docs/context/wi-06.bundle.json", "docs/context/wi-06.md", "docs/spec/plan.yaml"])
        self.assertFalse(any(p.startswith(("repo/", "payloads/")) for p in paths))
        self.assertFalse(any(p.startswith("docs/release/") for p in paths))

    def test_a_valid_first_receipt_does_not_list_itself(self):
        receipt = json.loads(self.project())
        self.assertNotIn("docs/release/%s.receipt.json" % self.rid, [a["path"] for a in receipt["artifacts"]])

    def test_a_receipt_listed_in_the_manifest_is_refused(self):
        entries = json.loads(self.manifest)
        entries.append({"path": "repo/docs/release/%s.receipt.json" % self.rid, "sha256": H("r"), "bytes": 1, "mode": "100644"})
        manifest, release_id = RS.manifest_from_entries(entries)
        request = make_request(manifest)
        state = RS.replay_state([make_event([transition(request["request_sha256"], "prepared", "active", None)], "z")]).requests[request["request_sha256"]]
        approval = RS.VerifiedApproval(request["request_sha256"], "github-review", True)
        self.refuses("receipt-projection-mismatch", RS.project_receipt, request, manifest, state, approval)

    def test_local_owner_approval_is_not_authenticated(self):
        local = RS.VerifiedApproval(self.rid, "local-owner", False)
        receipt = json.loads(self.project(verified_approval=local))
        self.assertEqual(receipt["approval"], {"type": "local-owner", "authenticated": False, "ref": self.rid})
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest, self.state,
                     RS.VerifiedApproval(self.rid, "local-owner", True))
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest, self.state,
                     RS.VerifiedApproval(self.rid, "github-review", False))
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest, self.state,
                     RS.VerifiedApproval(self.rid, "signed-tag", True))

    def test_a_proposed_receipt_is_never_a_source_of_any_field(self):
        proposed = json.loads(self.project())
        proposed.update({"state": "withdrawn", "event_id": H("fake"), "expires_at": "2099-01-01T00:00:00Z", "audience": "public",
                         "approval": {"type": "github-review", "authenticated": True, "ref": H("fake")}})
        # the function takes no receipt argument
        self.fails(TypeError, RS.project_receipt, self.request, self.manifest, self.state, self.approval, proposed)
        # a plain dict, such as a proposed receipt, is refused where a verified record is required
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest, proposed, self.approval)
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest, self.state, proposed)
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest, self.state, dict(proposed["approval"]))
        # a receipt hidden inside the request is an unknown field
        self.refuses("schema-invalid", RS.project_receipt, dict(self.request, receipt=proposed), self.manifest, self.state, self.approval)
        # and the output does not move when the proposed receipt differs
        self.assertEqual(json.loads(self.project())["state"], "active")

    def test_every_public_field_is_pinned_to_the_projection(self):
        good = self.project()
        base = json.loads(good)
        other_target = [t for t in base["targets"] if t["id"] == "engineering"]
        changes = {
            "receipt_format": 2, "request_id": H("x"), "release_id": H("x"), "content_manifest_sha256": H("x"),
            "created": "2027-02-01T00:00:00Z", "state": "withdrawn", "event_id": H("x"), "supersedes": H("x"),
            "superseded_by": H("x"), "expires_at": "2099-01-01T00:00:00Z", "audience": "public", "destinations": ["issue"],
            "targets": other_target, "sources": [{"id": "architecture", "version": "0.3"}],
            "artifacts": base["artifacts"][1:], "downstream": dict(base["downstream"], assignees=False),
            "offline_grace_days": 8, "approval": dict(base["approval"], authenticated=False), "enrollment_id": H("x"),
        }
        self.assertEqual(set(changes), set(RS.RECEIPT_KEYS))
        for field, value in changes.items():
            with self.subTest(field=field):
                mutated = RS.canonical_json(dict(base, **{field: value}))
                self.assertNotEqual(mutated, good)
                self.refuses("receipt-projection-mismatch", RS.verify_receipt_bytes, mutated, self.request, self.manifest, self.state, self.approval)
        RS.verify_receipt_bytes(good, self.request, self.manifest, self.state, self.approval)

    def test_unknown_field_omitted_artifact_and_altered_mode_fail(self):
        good = self.project()
        base = json.loads(good)
        variants = {
            "unknown field": dict(base, extra="x"),
            "omitted artifact": dict(base, artifacts=base["artifacts"][:-1]),
            "altered mode": dict(base, artifacts=[dict(base["artifacts"][0], mode="100755")] + base["artifacts"][1:]),
            "private value": dict(base, staging_repository="acme/private"),
        }
        for name, value in variants.items():
            with self.subTest(name):
                self.refuses("receipt-projection-mismatch", RS.verify_receipt_bytes, RS.canonical_json(value),
                             self.request, self.manifest, self.state, self.approval)
        self.refuses("receipt-projection-mismatch", RS.verify_receipt_bytes, json.dumps(base, indent=2).encode(),
                     self.request, self.manifest, self.state, self.approval)
        self.refuses("receipt-projection-mismatch", RS.verify_receipt_bytes, good.rstrip(b"\n"),
                     self.request, self.manifest, self.state, self.approval)
        self.refuses("receipt-projection-mismatch", RS.verify_receipt_bytes, good.replace(b'"audience"', b'"audience":"x","audience"', 1),
                     self.request, self.manifest, self.state, self.approval)

    def test_template_artifacts_must_equal_the_manifest_projection(self):
        for bad in (self.request["receipt_template"]["artifacts"][:-1],
                    [dict(a, mode="100755") for a in self.request["receipt_template"]["artifacts"]],
                    [dict(a, sha256=H("other")) for a in self.request["receipt_template"]["artifacts"]]):
            request = copy.deepcopy(self.request)
            request["receipt_template"]["artifacts"] = bad
            request["request_sha256"] = RS.hash_request(request)
            state = RS.RequestState(request["request_sha256"], "active", self.e1["event_id"], None, None)
            approval = RS.VerifiedApproval(request["request_sha256"], "github-review", True)
            self.refuses("receipt-projection-mismatch", RS.project_receipt, request, self.manifest, state, approval)

    def test_manifest_state_and_approval_must_belong_to_the_request(self):
        other_manifest, _ = RS.manifest_from_entries(json.loads(self.manifest)[:2])
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, other_manifest, self.state, self.approval)
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest,
                     self.state._replace(request_id=H("another request")), self.approval)
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest, self.state,
                     self.approval._replace(request_id=H("another request")))
        self.refuses("receipt-projection-mismatch", RS.project_receipt, self.request, self.manifest,
                     self.state._replace(state="prepared"), self.approval)
        self.refuses("sha256-mismatch", RS.project_receipt, dict(self.request, request_sha256=H("forged")), self.manifest, self.state, self.approval)

    def test_terminal_receipts_keep_their_artifact_list_and_carry_the_terminal_event(self):
        r2 = make_request(self.manifest, supersedes=self.rid, nonce="b2" * 16)
        rid2 = r2["request_sha256"]
        e2 = make_event([transition(self.rid, "active", "superseded", self.e1["event_id"], replacement=rid2),
                         transition(rid2, "prepared", "active", self.e1["event_id"])], "r-e2")
        e3 = make_event([transition(rid2, "active", "withdrawn", e2["event_id"])], "r-e3")
        replay = RS.replay_state([self.e1, e2, e3])
        old = json.loads(RS.project_receipt(self.request, self.manifest, replay.requests[self.rid], self.approval))
        self.assertEqual((old["state"], old["superseded_by"], old["event_id"]), ("superseded", rid2, e2["event_id"]))
        self.assertEqual(old["artifacts"], json.loads(self.project())["artifacts"])
        new = json.loads(RS.project_receipt(r2, self.manifest, replay.requests[rid2], RS.VerifiedApproval(rid2, "github-review", True)))
        self.assertEqual((new["state"], new["supersedes"], new["event_id"]), ("withdrawn", self.rid, e3["event_id"]))
        # same content, a different request: the release id is shared, the request ids differ
        self.assertEqual(old["release_id"], new["release_id"])
        self.assertNotEqual(old["request_id"], new["request_id"])
        # the approved supersedes_request_id must agree with the activation batch
        self.refuses("receipt-projection-mismatch", RS.project_receipt, r2, self.manifest,
                     replay.requests[rid2]._replace(supersedes=None), RS.VerifiedApproval(rid2, "github-review", True))

    def test_validate_receipt_rejects_inconsistent_receipts(self):
        base = json.loads(self.project())
        for name, mutated in (("unknown", dict(base, extra=1)), ("release id differs", dict(base, release_id=H("x"))),
                              ("superseded_by while active", dict(base, superseded_by=H("x"))),
                              ("approval ref", dict(base, approval=dict(base["approval"], ref=H("x")))),
                              ("authenticated local", dict(base, approval=dict(base["approval"], type="local-owner"))),
                              ("short digest", dict(base, request_id=base["request_id"][:12])),
                              ("prepared", dict(base, state="prepared"))):
            with self.subTest(name):
                self.fails(RS.SchemaError, RS.validate_receipt, mutated)


class MessagesHoldNoValuesTests(Base):
    def test_errors_name_fields_and_never_the_value(self):
        secret = "SECRET-PASSAGE-12345"
        for call in (lambda: RS.manifest_from_entries([{"path": "../" + secret, "sha256": H("a"), "bytes": 1, "mode": "100644"}]),
                     lambda: RS.manifest_from_entries([{"path": "repo/a", "sha256": secret, "bytes": 1, "mode": "100644"}]),
                     lambda: RS.manifest_from_entries([{"path": "repo/a", "sha256": H("a"), "bytes": 1, "mode": secret}]),
                     lambda: RS.canonical_json({secret: float("nan")}),
                     lambda: RS.loads_strict('{"%s":1,"%s":2}' % (secret, secret))):
            error = self.fails(RS.SchemaError, call)
            self.assertNotIn(secret, str(error))
            self.assertIn(error.code, RG.REASON_CODES)

    def test_every_code_the_schema_raises_is_a_fixed_reason_code(self):
        import re
        source = (ROOT / "scripts" / "release_schema.py").read_text(encoding="utf-8")
        used = set(re.findall(r'(?:code = |SchemaError\(|_fail\([^\n]*?, )"([a-z0-9]+(?:-[a-z0-9]+)+)"', source))
        used |= set(re.findall(r'^\s+code = "([a-z-]+)"', source, re.M))
        self.assertTrue({"unsafe-artifact-path", "sha256-mismatch", "state-history-invalid", "receipt-projection-mismatch"} <= used, used)
        self.assertLessEqual(used, RG.REASON_CODES)


class LibraryWrapperTests(Base):
    def test_normalize_section_text(self):
        self.assertEqual(L.normalize_section_text("a  \r\nb\t\r\n\r\n\r\n"), "a\nb\n")
        self.assertEqual(L.normalize_section_text("one\n\n\n"), "one\n")
        self.assertEqual(L.normalize_section_text("no newline"), "no newline\n")
        self.assertEqual(L.normalize_section_text(""), "\n")
        self.assertEqual(L.normalize_section_text("  keep leading  \n"), "  keep leading\n")
        self.assertEqual(L.normalize_section_text("a\n\nb\n"), "a\n\nb\n")
        text = "Rule 1.  \r\nRule 2\r\n"
        self.assertEqual(L.normalize_section_text(L.normalize_section_text(text)), L.normalize_section_text(text))

    def test_hash_wrappers_delegate(self):
        self.assertEqual(L.sha256_text("abc"), RS.sha256_bytes(b"abc"))
        path = self.snapshot / "repo/docs/spec/plan.yaml"
        self.assertEqual(L.sha256_file(path), RS.sha256_bytes(path.read_bytes()))
        self.assertEqual(L.canonical_json({"b": 1, "a": 2}), RS.canonical_json({"a": 2, "b": 1}))
        self.fails(SystemExit, L.sha256_file, self.snapshot)
        self.fails(SystemExit, L.sha256_file, self.snapshot / "missing.txt")

    def project(self, name="project"):
        root = Path(self.temp.name) / name
        (root / ".carrydown").mkdir(parents=True)
        return root

    def test_workspace_root_absent_means_none_with_a_reason(self):
        root = self.project()
        self.assertEqual(L.workspace_root(root), (None, "workspace-unavailable"))
        self.assertEqual(L.workspace_root(Path(self.temp.name) / "no such folder"), (None, "workspace-unavailable"))

    def test_workspace_root_returns_a_private_folder_outside_the_repository(self):
        root = self.project()
        ws = Path(self.temp.name) / "workspaces" / "demo"
        ws.mkdir(parents=True)
        (root / ".carrydown/local.yaml").write_text("workspace: %s\n" % ws, encoding="utf-8")
        self.assertEqual(L.workspace_root(root), (ws.resolve(), None))

    def test_workspace_root_refuses_a_path_inside_the_repository(self):
        root = self.project()
        (root / "private").mkdir()
        for value in (str(root / "private"), str(root), "private", "./private/../private", str(root / "not yet made")):
            (root / ".carrydown/local.yaml").write_text("workspace: %s\n" % value, encoding="utf-8")
            with self.subTest(value=value):
                self.assertEqual(L.workspace_root(root), (None, "workspace-inside-repository"))

    def test_workspace_root_refuses_a_link_that_leads_into_the_repository(self):
        root = self.project()
        (root / "private").mkdir()
        link = Path(self.temp.name) / "innocent"
        try:
            os.symlink(str(root / "private"), str(link))
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are not available here")
        (root / ".carrydown/local.yaml").write_text("workspace: %s\n" % link, encoding="utf-8")
        self.assertEqual(L.workspace_root(root), (None, "workspace-inside-repository"))

    def test_workspace_root_uses_the_enclosing_repository_not_only_the_given_root(self):
        top = Path(self.temp.name) / "monorepo"
        (top / ".git").mkdir(parents=True)
        root = top / "services" / "demo"
        (root / ".carrydown").mkdir(parents=True)
        (top / "elsewhere").mkdir()
        (root / ".carrydown/local.yaml").write_text("workspace: %s\n" % (top / "elsewhere"), encoding="utf-8")
        self.assertEqual(L.workspace_root(root), (None, "workspace-inside-repository"))

    def test_workspace_root_bad_files_and_values(self):
        root = self.project()
        pointer = root / ".carrydown/local.yaml"
        for text in ("", "other: 1\n", "workspace:\n", "workspace: ''\n", "workspace: [a, b]\n", "- a\n- b\n", "workspace: {\n"):
            pointer.write_text(text, encoding="utf-8")
            with self.subTest(text=text):
                self.assertEqual(L.workspace_root(root), (None, "workspace-unavailable"))
        pointer.write_bytes(b"workspace: \xff\xfe\n")
        self.assertEqual(L.workspace_root(root), (None, "workspace-unavailable"))
        pointer.write_text("workspace: %s\n" % (Path(self.temp.name) / "does-not-exist"), encoding="utf-8")
        self.assertEqual(L.workspace_root(root), (None, "workspace-unavailable"))
        pointer.unlink()
        pointer.mkdir()
        self.assertEqual(L.workspace_root(root), (None, "workspace-unavailable"))


if __name__ == "__main__":
    unittest.main()
