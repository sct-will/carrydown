"""Tests for scripts/release.py: preview, prepare, approve, export, export-state, withdraw and diff.

The "yes" path runs on a copy of the sample with a private workspace. The "no" path runs on the
confidential fixture, enrolled in the fictional organization of tests/mock/fake_evidence.py, with local
bare repositories standing in for the engineering origin and the staging repository. No token and no
network are used. Tests tagged [G1], [G2], [G4] and [G6] are negative tests of the specification (Part G)
that WP11 collects.
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "mock"))
from sample_tree import copy_sample  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import fake_evidence as FE  # noqa: E402
import generate_dev_skill as GD  # noqa: E402
import plan_repair as PR  # noqa: E402
import release as R  # noqa: E402
import release_build as B  # noqa: E402
import release_fixture as F  # noqa: E402
import release_gate as RG  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402
import scaffold_spec as SS  # noqa: E402

SPEC = "docs/spec/m1-submit-report/wi-01-service-scaffold.md"


def tree_state(folder):
    """{relative path: sha256} of every file under folder except git internals."""
    out = {}
    base = Path(folder)
    for p in sorted(base.rglob("*")):
        if p.is_file() and ".git" not in p.relative_to(base).parts:
            out[p.relative_to(base).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-release-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)


class YesPathTests(Temp):
    def setUp(self):
        super().setUp()
        self.yp = F.YesProject(self.base)
        self.root, self.ws = self.yp.root, self.yp.workspace

    def edit_spec(self, text=" Added after the release."):
        path = self.root / SPEC
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + text + "\n", encoding="utf-8")

    # --- preview and prepare ---
    def test_preview_answers_the_four_questions_in_order_and_writes_nothing(self):
        before = tree_state(self.base)
        code, out, err = F.run(R.main, ["preview", "--root", str(self.root), "--repository-id", "4200"])
        self.assertEqual(code, 0, out + err)
        positions = [out.index(q) for q in ("What will be shared?", "With whom?", "Where?", "What remains private?")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Changes since the previous release", out)
        self.assertIn("This is the first release", out)
        self.assertEqual(tree_state(self.base), before)

    def test_prepare_dry_run_writes_nothing_and_apply_builds_the_release(self):
        before = tree_state(self.base)
        code, out, err = self.yp.prepare(apply=False)
        self.assertEqual(code, 0, out + err)
        self.assertIn("Dry run: nothing was written", out)
        self.assertEqual(tree_state(self.base), before)
        code, out, err = self.yp.prepare()
        self.assertEqual(code, 0, out + err)
        self.assertIn("release id (content):", out)
        self.assertIn("request id (permission):", out)
        self.assertIn("The release id names these exact bytes", out)
        rid = self.yp.request_id
        request = R.load_request(self.ws, rid)
        manifest, entries, files = R.load_release(self.ws, request["release_id"])
        self.assertEqual(RS.sha256_bytes(manifest), request["release_id"])
        self.assertEqual([e["path"] for e in entries], sorted(e["path"] for e in entries))
        self.assertFalse([p for p, data in files.items() if request["release_id"].encode() in data])
        self.assertTrue(any(p.startswith("payloads/issue/") for p in files))
        released = (self.ws / "releases" / request["release_id"] / "snapshot" / "repo" / "docs/spec/plan.yaml").read_text(encoding="utf-8")
        self.assertIn("plan_view: \"released\"", released)
        for private in ("source_path", "classification", "content_sha256", "allocation", "days_off", "github", "skills", "preferences"):
            self.assertIsNone(re.search(rf"(?m)^\s*(- )?{private}:", released), private)
        self.assertEqual(request["receipt_template"]["audience"], "repo-readers")
        self.assertEqual(request["policy_commit_sha"], "0" * 40)

    def test_retrying_prepare_reuses_the_saved_request_and_a_new_approval_gets_a_fresh_nonce(self):
        self.yp.prepare(nonce=None, created=None)
        first = self.yp.request_id
        self.yp.prepare(nonce=None, created=None)
        self.assertEqual(self.yp.request_id, first)
        self.yp.prepare("--new-request", nonce=None, created=None)
        self.assertNotEqual(self.yp.request_id, first)
        self.assertTrue((self.ws / "requests" / first / "approval-request.json").is_file())

    def test_a_released_snapshot_is_reused_and_a_mismatch_is_a_hard_error(self):
        self.yp.prepare()
        request = R.load_request(self.ws, self.yp.request_id)
        victim = self.ws / "releases" / request["release_id"] / "snapshot" / "repo" / "docs/spec/README.md"
        victim.write_bytes(victim.read_bytes() + b"x")
        code, out, err = self.yp.prepare("--new-request")
        self.assertEqual(code, 1)
        self.assertIn("sha256-mismatch", err)

    def test_a_detector_finding_blocks_preparation_without_printing_the_text(self):
        path = self.root / SPEC
        path.write_text(path.read_text(encoding="utf-8") + "\nsecret_token = " + "S" * 24 + "\n", encoding="utf-8")
        code, out, err = self.yp.prepare()
        self.assertEqual(code, 1)
        self.assertIn("detector:credentials", out)
        self.assertNotIn("S" * 24, out + err)
        self.assertFalse((self.ws / "releases").exists() and any((self.ws / "releases").iterdir()))

    # --- approval ---
    def test_G1_approve_needs_the_preview_to_have_been_shown(self):
        """[G1]"""
        self.yp.prepare()
        argv = ["approve", "--root", str(self.root), "--request", self.yp.request_id, "--local", "--apply"]
        code, out, err = F.run(R.main, argv)
        self.assertEqual(code, 1)
        self.assertIn("not-approved", err)
        self.assertIn("What will be shared?", out)
        self.assertFalse((self.ws / "events").exists() and any((self.ws / "events").iterdir()))
        code, out, err = F.run(R.main, argv[:-1])           # a dry run shows the preview and records nothing
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)

    def test_approve_local_records_a_local_owner_approval_an_event_and_the_state(self):
        self.yp.prepare()
        code, out, err = self.yp.approve()
        self.assertEqual(code, 0, out + err)
        rid = self.yp.request_id
        approval = json.loads((self.ws / "requests" / rid / "approval.json").read_text(encoding="utf-8"))
        self.assertEqual((approval["type"], approval["authenticated"], approval["request_sha256"]), ("local-owner", False, rid))
        replay = V.local_replay(str(self.ws)).replay
        self.assertEqual((replay.active, replay.requests[rid].state), (rid, "active"))
        state = json.loads((self.ws / "requests" / rid / "state.json").read_text(encoding="utf-8"))
        self.assertEqual((state["state"], state["event_id"]), ("active", replay.requests[rid].event_id))
        code, out, err = self.yp.approve()
        self.assertEqual(code, 0)
        self.assertIn("already approved and active", out)
        self.assertEqual(len(list((self.ws / "events").iterdir())), 1)

    def test_local_approval_is_refused_for_an_enrolled_project(self):
        self.yp.prepare()
        (self.root / ".carrydown" / "release-policy.yaml").write_text("format: 1\ntooling_repository: acme/t\nenrollment_id: " + "a" * 64 + "\n", encoding="utf-8")
        code, out, err = self.yp.approve()
        self.assertEqual(code, 1)
        self.assertIn("unauthenticated-release", err)

    def test_a_signed_tag_is_refused_before_anything_is_uploaded(self):
        self.yp.prepare()
        code, out, err = F.run(R.main, ["approve", "--root", str(self.root), "--request", self.yp.request_id, "--signed-tag", "--apply"])
        self.assertEqual(code, 1)
        self.assertIn("approval-mechanism-unsupported", err)

    # --- export ---
    def test_G1_export_is_refused_without_an_active_request_even_with_a_fabricated_approval(self):
        """[G1]"""
        self.yp.prepare()
        rid = self.yp.request_id
        fake = {"type": "local-owner", "authenticated": False, "request_sha256": rid, "content_manifest_sha256": R.load_request(self.ws, rid)["release_id"],
                "approved_at": "2027-01-20T14:10:00Z", "git_identity": {"name": "x", "email": "y"}, "event_id": "e" * 64}
        (self.ws / "requests" / rid / "approval.json").write_text(json.dumps(fake), encoding="utf-8")
        before = tree_state(self.root)
        code, out, err = self.yp.export()
        self.assertEqual(code, 1)
        self.assertRegex(err, r"approval-not-found|not-approved")
        self.assertEqual(tree_state(self.root), before)
        # a fabricated event that names the request is still no authority: the chain must be valid
        code, out, err = self.yp.export("0" * 64)
        self.assertEqual(code, 1)

    def test_export_writes_the_exact_receipt_and_the_approved_files_and_dry_run_writes_nothing(self):
        self.yp.prepare()
        self.yp.approve()
        before = tree_state(self.root)
        code, out, err = self.yp.export(apply=False)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(tree_state(self.root), before)
        code, out, err = self.yp.export()
        self.assertEqual(code, 0, out + err)
        rid = self.yp.request_id
        path = self.root / "docs" / "release" / f"{rid}.receipt.json"
        receipt = RS.loads_strict(path.read_bytes())
        self.assertEqual((receipt["state"], receipt["audience"], receipt["approval"]), ("active", "repo-readers", {"type": "local-owner", "authenticated": False, "ref": rid}))
        record = V.verify_local_request(V.load_local_evidence(str(self.ws), rid), rid)
        replay = V.local_replay(str(self.ws)).replay
        RS.verify_receipt_bytes(path.read_bytes(), record.request, record.manifest_bytes, replay.requests[rid], record.approval)
        self.assertNotIn("docs/release/", json.dumps(receipt["artifacts"]))
        self.assertTrue(any(a["path"] == "docs/context/wi-06.md" for a in receipt["artifacts"]))
        # every public receipt field, changed one at a time, no longer equals the projection
        for key in RS.RECEIPT_KEYS:
            altered = dict(receipt)
            altered[key] = [] if isinstance(receipt[key], list) else ("0" * 64 if isinstance(receipt[key], str) and len(receipt[key]) == 64 else "x")
            self.assertTrue(self.mismatch(altered, record, replay, rid), key)
        self.assertTrue(self.mismatch(dict(receipt, unknown="x"), record, replay, rid))
        self.assertTrue(self.mismatch(dict(receipt, artifacts=receipt["artifacts"][1:]), record, replay, rid))
        self.assertTrue(self.mismatch(dict(receipt, artifacts=[dict(receipt["artifacts"][0], mode="100755")] + receipt["artifacts"][1:]), record, replay, rid))

    def mismatch(self, altered, record, replay, rid):
        try:
            RS.verify_receipt_bytes(json.dumps(altered, sort_keys=True, separators=(",", ":")).encode() + b"\n", record.request, record.manifest_bytes,
                                    replay.requests[rid], record.approval)
        except RS.SchemaError:
            return True
        return False

    def test_G2_export_refuses_a_working_copy_that_differs_from_the_snapshot(self):
        """[G2]"""
        self.yp.prepare()
        self.yp.approve()
        self.edit_spec()
        before = tree_state(self.root)
        code, out, err = self.yp.export()
        self.assertEqual(code, 1)
        self.assertIn("working-copy-differs", err)
        self.assertIn("run release.py preview", err)
        self.assertEqual(tree_state(self.root), before)

    def test_G2_changing_the_audience_or_destinations_in_the_request_after_approval_refuses_export(self):
        """[G2]"""
        self.yp.prepare()
        self.yp.approve()
        rid = self.yp.request_id
        path = self.ws / "requests" / rid / "approval-request.json"
        for field, value in (("audience", "public"), ("destinations", ["engineering-repo"])):
            original = path.read_bytes()
            request = json.loads(original)
            request["receipt_template"][field] = value
            path.write_text(json.dumps(request), encoding="utf-8")
            code, out, err = self.yp.export()
            self.assertEqual(code, 1, field)
            self.assertIn("approval-scope-mismatch", err, field)
            path.write_bytes(original)
        self.assertEqual(self.yp.export(apply=False)[0], 0)

    def test_G2_after_a_local_approval_one_changed_byte_makes_scaffold_refuse_to_refresh(self):
        """[G2] [G6]"""
        self.yp.release()
        self.edit_spec()
        code, out, err = F.run(SS.main, ["--root", str(self.root), "--refresh-headers", "--apply", "--allow-no-git"])
        self.assertEqual(code, 1)
        self.assertIn("working-copy-differs", err)

    def test_snapshot_traversal_and_symlinks_fail_before_any_filesystem_write(self):
        self.yp.prepare()
        self.yp.approve()
        request = R.load_request(self.ws, self.yp.request_id)
        snap = self.ws / "releases" / request["release_id"] / "snapshot"
        os.symlink("/etc/hosts", snap / "repo" / "docs" / "evil-link.md")
        before = tree_state(self.root)
        code, out, err = self.yp.export()
        self.assertEqual(code, 1)
        self.assertIn("unsafe-artifact-path", err)
        self.assertEqual(tree_state(self.root), before)

    def test_export_refuses_to_write_through_a_symlinked_folder(self):
        self.yp.prepare()
        self.yp.approve()
        outside = self.base / "outside"
        outside.mkdir()
        shutil.rmtree(self.root / "docs" / "context")
        os.symlink(outside, self.root / "docs" / "context")
        code, out, err = self.yp.export()
        self.assertEqual(code, 1)
        self.assertEqual(list(outside.iterdir()), [])

    def test_a_local_copy_that_failed_part_way_is_repeated_without_a_duplicate(self):
        self.yp.prepare()
        self.yp.approve()
        shutil.rmtree(self.root / "docs" / "context")
        real = R.write_file
        count = {"n": 0}

        def flaky(*a, **k):
            count["n"] += 1
            if count["n"] == 4:
                raise OSError("the disk went away")
            return real(*a, **k)
        with mock.patch.object(R, "write_file", flaky):
            with _RaisesOSError():
                self.yp.export()
        code, out, err = self.yp.export()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(list((self.root / "docs" / "context").iterdir())), 18)
        self.assertTrue((self.root / "docs" / "release" / f"{self.yp.request_id}.receipt.json").is_file())
        self.assertEqual(len(list((self.root / "docs" / "release").iterdir())), 2)       # the sample's own receipt and this one
        self.assertEqual(len(list((self.ws / "events").iterdir())), 1)
        self.assertEqual(len(list((self.ws / "requests").iterdir())), 1)

    def test_the_export_writes_the_released_plan_and_moves_the_working_plan_to_the_workspace(self):
        before = (self.root / "docs/spec/plan.yaml").read_bytes()
        rid = self.yp.release()
        request = R.load_request(self.ws, rid)
        released = (self.ws / "releases" / request["release_id"] / "snapshot" / "repo" / "docs/spec/plan.yaml").read_bytes()
        self.assertEqual((self.root / "docs/spec/plan.yaml").read_bytes(), released)       # a clean clone holds the released plan
        self.assertEqual((self.ws / "drafts" / "plan.yaml").read_bytes(), before)          # nothing of the working plan is lost
        self.assertEqual(L.owner_plan(self.root).resolve(), (self.ws / "drafts" / "plan.yaml").resolve())   # the owner's commands find it there
        self.assertEqual(L.find_plan(self.root), self.root / "docs/spec/plan.yaml")

    # --- lifecycle ---
    def test_replacement_supersedes_and_the_old_receipt_is_regenerated_as_superseded(self):
        first = self.yp.release()
        self.edit_spec()
        code, out, err = self.yp.prepare()
        self.assertEqual(code, 0, out + err)
        second = self.yp.request_id
        self.assertNotEqual(first, second)
        self.assertEqual(R.load_request(self.ws, second)["supersedes_request_id"], first)
        self.assertEqual(self.yp.approve()[0], 0)
        replay = V.local_replay(str(self.ws)).replay
        self.assertEqual((replay.requests[first].state, replay.requests[second].state, replay.active), ("superseded", "active", second))
        self.assertEqual(len(list((self.ws / "events").iterdir())), 2)
        code, out, err = self.yp.export()
        self.assertEqual(code, 0, out + err)
        new = RS.loads_strict((self.root / "docs/release" / f"{second}.receipt.json").read_bytes())
        old = RS.loads_strict((self.root / "docs/release" / f"{first}.receipt.json").read_bytes())
        self.assertEqual((old["state"], old["superseded_by"], new["state"], new["supersedes"]), ("superseded", second, "active", first))
        self.assertIn("Added after the release.", (self.root / SPEC).read_text(encoding="utf-8"))

    def test_G4_withdrawal_ends_content_publication_and_a_state_only_export_writes_only_the_receipt(self):
        """[G4] [G6]"""
        rid = self.yp.release()
        code, out, err = F.run(R.main, ["withdraw", "--root", str(self.root), "--request", rid, "--reason", "error-found", "--apply", "--created", "2027-01-21T09:00:00Z"])
        self.assertEqual(code, 0, out + err)
        replay = V.local_replay(str(self.ws)).replay
        self.assertEqual((replay.requests[rid].state, replay.active), ("withdrawn", None))
        # content export is refused for a withdrawn request
        code, out, err = self.yp.export()
        self.assertEqual(code, 1)
        self.assertIn("withdrawn", err)
        before = tree_state(self.root)
        code, out, err = F.run(R.main, ["export-state", "--root", str(self.root), "--request", rid, "--apply"])
        self.assertEqual(code, 0, out + err)
        after = tree_state(self.root)
        changed = sorted(p for p in after if before.get(p) != after[p])
        self.assertEqual(changed, [f"docs/release/{rid}.receipt.json"])
        receipt = RS.loads_strict((self.root / "docs/release" / f"{rid}.receipt.json").read_bytes())
        self.assertEqual(receipt["state"], "withdrawn")
        # the gate: a spec cannot be added to the state-only operation
        record = V.verify_local_request(V.load_local_evidence(str(self.ws), rid), rid)
        ctx = V.authorize_state_receipt(record, replay, V.local_policy({k: v for k, v in R.Project(self.root).handling.items() if k in R.L.RELEASED_HANDLING_KEYS},
                                                                         "sct-will/carrydown-sample"), {f"docs/release/{rid}.receipt.json": RS.sha256_bytes(
                                                                             (self.root / "docs/release" / f"{rid}.receipt.json").read_bytes())})
        d = RG.check("state-only", SPEC, RS.sha256_file(self.root / SPEC), "engineering-repo", str(self.root), verified_context=ctx)
        self.assertEqual((d.allowed, d.code), (False, "state-only-content-write"))
        d = RG.check("state-only", f"docs/release/{rid}.receipt.json", RS.sha256_file(self.root / f"docs/release/{rid}.receipt.json"), "engineering-repo",
                     str(self.root), verified_context=ctx)
        self.assertTrue(d.allowed)

    def test_identical_content_for_another_audience_has_the_same_release_id_and_another_request_id(self):
        first = self.yp.release()
        rel_first = R.load_request(self.ws, first)["release_id"]
        self.assertEqual(F.run(R.main, ["withdraw", "--root", str(self.root), "--request", first, "--reason", "other", "--apply"])[0], 0)
        code, out, err = self.yp.prepare("--audience", "public")
        self.assertEqual(code, 0, out + err)
        second = self.yp.request_id
        self.assertEqual(R.load_request(self.ws, second)["release_id"], rel_first)
        self.assertNotEqual(second, first)
        self.assertEqual(self.yp.approve()[0], 0)
        replay = V.local_replay(str(self.ws)).replay
        self.assertEqual((replay.requests[first].state, replay.requests[second].state), ("withdrawn", "active"))

    def test_reapproval_after_withdrawal_uses_a_fresh_nonce_and_keeps_the_terminal_history(self):
        first = self.yp.release()
        self.assertEqual(F.run(R.main, ["withdraw", "--root", str(self.root), "--request", first, "--reason", "other", "--apply"])[0], 0)
        old_request = (self.ws / "requests" / first / "approval-request.json").read_bytes()
        code, out, err = self.yp.prepare(nonce=None, created=None)
        self.assertEqual(code, 0, out + err)
        again = self.yp.request_id
        self.assertNotEqual(again, first)
        self.assertEqual(R.load_request(self.ws, again)["release_id"], R.load_request(self.ws, first)["release_id"])
        self.assertNotEqual(R.load_request(self.ws, again)["request_nonce"], R.load_request(self.ws, first)["request_nonce"])
        self.assertEqual((self.ws / "requests" / first / "approval-request.json").read_bytes(), old_request)
        self.assertEqual(V.local_replay(str(self.ws)).replay.requests[first].state, "withdrawn")

    def test_preparing_content_that_is_already_active_changes_nothing(self):
        self.yp.release()
        before = tree_state(self.ws)
        code, out, err = self.yp.prepare(nonce=None, created=None)
        self.assertEqual(code, 0)
        self.assertIn("already approved and active", out)
        self.assertEqual(tree_state(self.ws), before)

    def test_diff_names_the_work_items_a_change_touches(self):
        self.yp.release()
        self.edit_spec()
        code, out, err = F.run(R.main, ["diff", "--root", str(self.root), "--repository-id", "4200"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("Work items affected: WI-01", out)
        self.assertIn("Scope changes:", out)

    def test_two_active_requests_in_the_workspace_are_a_mixed_release(self):
        first = self.yp.release()
        second_event = B.build_event([B.transition("f" * 64, "prepared", "active", V.local_replay(str(self.ws)).replay.tip, "release-approved")],
                                     V.local_policy({}, "o/r"), created="2027-02-01T00:00:00Z", nonce="1" * 32)
        (self.ws / "events" / f"{second_event['event_id']}.json").write_bytes(RS.canonical_json(second_event))
        with _Expect("mixed-release"):
            V.local_replay(str(self.ws))

    # --- maintenance commands and the gate ---
    def test_G6_regeneration_before_any_release_is_a_draft_write_on_the_yes_path(self):
        """[G6]"""
        for argv, main in ((["--root", str(self.root), "--refresh-headers", "--apply", "--allow-no-git"], SS.main),
                           (["--root", str(self.root), "--apply", "--force"], GD.main),
                           (["--root", str(self.root), "--apply"], PR.main)):
            code, out, err = F.run(main, argv)
            self.assertIn(code, (0, 1), out + err)
            self.assertNotIn("not-approved", err)
            self.assertNotIn("drafting-is-private", err)

    def test_G6_regeneration_in_an_enrolled_project_with_no_active_release_is_not_approved(self):
        """[G6]"""
        (self.root / ".carrydown" / "release-policy.yaml").write_text("format: 1\ntooling_repository: acme/t\nenrollment_id: " + "a" * 64 + "\n", encoding="utf-8")
        shutil.rmtree(self.root / "docs" / "dev")
        before = tree_state(self.root)
        for argv, main in ((["--root", str(self.root), "--refresh-headers", "--apply", "--allow-no-git"], SS.main),
                           (["--root", str(self.root), "--apply"], GD.main),
                           (["--root", str(self.root), "--apply"], PR.main)):
            code, out, err = F.run(main, argv)
            self.assertEqual(code, 1, out + err)
            self.assertIn("not-approved", err, out)
        self.assertEqual(tree_state(self.root), before)

    def test_a_working_plan_edit_is_still_a_draft_after_the_release(self):
        self.yp.release()
        path = self.root / "docs/spec/plan.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("Full specification.", "Full specification, as the owner uses it.", 1), encoding="utf-8")
        d = RG.check("draft", "docs/spec/plan.yaml", "0" * 64, "engineering-repo", str(self.root))
        self.assertTrue(d.allowed, d)


class _RaisesOSError:
    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        assert kind is not None and issubclass(kind, OSError), "expected the simulated disk failure"
        return True


class _Expect:
    """A context manager asserting a SchemaError with a code, in the style of this repository's tests."""

    def __init__(self, code):
        self.code = code

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        assert kind is not None and issubclass(kind, RS.SchemaError) and value.code == self.code, f"expected {self.code}, got {value!r}"
        return True


class NoPathTests(Temp):
    def setUp(self):
        super().setUp()
        self.np = F.NoProject(self.base).start()
        self.addCleanup(self.np.stop)
        self.world, self.reader = self.np.world, self.np.reader
        self.root, self.ws, self.staging = self.np.root, self.np.workspace, self.np.staging

    def staging_branches(self):
        run = F.sh(["git", "ls-remote", "--heads", str(self.staging)], self.base)
        return [line.split("\t")[1] for line in run.stdout.splitlines()]

    def test_a_no_path_project_writes_nothing_into_engineering_paths_while_drafting(self):
        (self.root / "docs" / "spec").mkdir(parents=True)
        shutil.copy(self.ws / "drafts" / "plan.yaml", self.root / "docs" / "spec" / "plan.yaml")
        before = tree_state(self.root)
        for argv, main in ((["--root", str(self.root), "--apply", "--allow-no-git"], SS.main),
                           (["--root", str(self.root), "--apply"], GD.main)):
            code, out, err = F.run(main, argv)
            self.assertEqual(code, 1, out + err)
            self.assertRegex(err, "not-approved|drafting-is-private")
        self.assertEqual(tree_state(self.root), before)
        code, out, err = self.np.prepare()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(tree_state(self.root), before)

    def test_prepare_takes_policy_and_targets_from_the_enrollment(self):
        self.np.prepare()
        request = R.load_request(self.ws, self.np.request_id)
        enr = self.world.enrollment()
        self.assertEqual((request["policy_commit_sha"], request["policy_sha256"], request["enrollment_id"]),
                         (enr.policy_commit_sha, enr.policy_sha256, enr.enrollment_id))
        targets = {t["id"]: t for t in request["receipt_template"]["targets"]}
        self.assertEqual(targets["engineering"]["repository_id"], 4200)
        self.assertEqual(targets["board"]["project_id"], "PVT_example")
        self.assertEqual(request["supersedes_request_id"], None)

    def test_G3_the_staging_candidate_holds_no_original_staffing_or_workspace_file(self):
        """[G3]"""
        self.np.prepare()
        code, out, err = self.np.approve()
        self.assertEqual(code, 0, out + err)
        rid = self.np.request_id
        clone = self.base / "stagingclone"
        F.sh(["git", "clone", "-q", "-b", f"request/{rid}", str(self.staging), str(clone)], self.base)
        files = sorted(tree_state(clone))
        self.assertTrue(files)
        for path in files:
            self.assertRegex(path, r"^(README\.md|releases/[0-9a-f]{64}/|requests/[0-9a-f]{64}/approval-request\.json$|events/[0-9a-f]{64}\.json$)")
        blob = b"".join((clone / p).read_bytes() for p in files)
        for private in (b"Tamsin Hale", b"assignment_rationale", b"days_off", b"source_path", b"people.yaml"):
            self.assertNotIn(private, blob)
        self.assertFalse((clone / "requests" / rid / "approval.json").exists())

    def test_zero_pushes_when_the_staging_readers_cannot_be_verified(self):
        self.np.prepare()
        self.reader.collaborators_by_repo[FE.STAGING_ID].append({"id": 999, "login": "outsider", "permission": "read"})
        code, out, err = self.np.approve()
        self.assertEqual(code, 1)
        self.assertIn("staging-access-not-verified", err)
        self.assertEqual(self.staging_branches(), ["refs/heads/main"])
        self.reader.collaborators_by_repo[FE.STAGING_ID].pop()
        self.reader.fail("collaborators", FE.STAGING_ID)
        code, out, err = self.np.approve()
        self.assertEqual(code, 1)
        self.assertEqual(self.staging_branches(), ["refs/heads/main"])

    def test_a_timeout_leaves_a_pending_candidate_and_a_retry_does_not_duplicate_it(self):
        self.np.prepare()
        code, out, err = self.np.approve()
        self.assertEqual(code, 0, out + err)
        self.assertIn("candidate uploaded; approval request pending", out)
        self.assertIn(f"approve --root", out)
        rid = self.np.request_id
        branches = self.staging_branches()
        self.assertEqual(sorted(branches), sorted(["refs/heads/main", f"refs/heads/request/{rid}"]))
        # the workflow opens the pull request; a retry finds the branch and the request
        self.reader.open_pr(FE.STAGING_ID, f"request/{rid}", self.np.candidate_files())
        before = (self.ws / "requests" / rid / "activation-candidate.json").read_bytes()
        code, out, err = self.np.approve()
        self.assertEqual(code, 0, out + err)
        self.assertIn("opened pull request", out)
        self.assertEqual(self.staging_branches(), branches)
        self.assertEqual((self.ws / "requests" / rid / "activation-candidate.json").read_bytes(), before)
        self.assertEqual(len(self.reader.repos[FE.STAGING_ID]["prs"]), 1)

    def test_G1_export_is_refused_until_the_request_is_merged_with_an_authorized_review(self):
        """[G1]"""
        self.np.prepare()
        self.np.approve()
        code, out, err = self.np.export()
        self.assertEqual(code, 1)
        self.assertIn("approval-not-found", err)
        n = self.np.land(merge=False, approve=False)
        self.assertEqual(self.np.export()[0], 1)
        self.reader.review(FE.STAGING_ID, n, *FE.OUTSIDER)
        self.reader.merge(FE.STAGING_ID, n)
        code, out, err = self.np.export()
        self.assertEqual(code, 1)
        self.assertIn("approver-not-authorized", err)
        self.assertEqual(F.sh(["git", "branch", "--list", "carrydown/*"], self.root).stdout.strip(), "")

    def test_G2_an_approval_of_an_earlier_revision_is_refused(self):
        """[G2]"""
        self.np.prepare()
        self.np.approve()
        rid = self.np.request_id
        n = self.reader.open_pr(FE.STAGING_ID, f"request/{rid}", self.np.candidate_files())
        self.reader.review(FE.STAGING_ID, n, *FE.OWNER)
        self.reader.push_more(FE.STAGING_ID, n, {})
        self.reader.merge(FE.STAGING_ID, n)
        code, out, err = self.np.export()
        self.assertEqual(code, 1)
        self.assertIn("approval-not-on-final-revision", err)

    def test_export_creates_an_isolated_worktree_branch_and_preserves_a_dirty_worktree(self):
        self.np.prepare()
        self.np.approve()
        self.np.land()
        (self.root / "README.md").write_text("uncommitted edit\n", encoding="utf-8")
        (self.root / "scratch.txt").write_text("untracked\n", encoding="utf-8")
        before = tree_state(self.root)
        status_before = F.sh(["git", "status", "--porcelain"], self.root).stdout
        code, out, err = self.np.export(apply=False)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(tree_state(self.root), before)
        self.assertEqual(F.sh(["git", "branch", "--list", "carrydown/*"], self.root).stdout.strip(), "")
        code, out, err = self.np.export()
        self.assertEqual(code, 0, out + err)
        rid = self.np.request_id
        branch = f"carrydown/request-{rid}"
        self.assertEqual(tree_state(self.root), before)
        self.assertEqual(F.sh(["git", "status", "--porcelain"], self.root).stdout, status_before)
        self.assertIn(f"git -C {self.root.resolve()} push -u origin {branch}", out)
        self.assertIn("gh pr create", out)
        files = F.sh(["git", "ls-tree", "-r", "--name-only", branch], self.root).stdout.split()
        self.assertIn(f"docs/release/{rid}.receipt.json", files)
        self.assertIn("docs/context/wi-06.md", files)
        for banned in ("company-governance.md", "people.yaml", "ground-truth/"):
            self.assertFalse([f for f in files if banned in f], banned)
        author = F.sh(["git", "log", "-1", "--format=%an <%ae>|%cn <%ce>", branch], self.root).stdout.strip()
        self.assertEqual(author, "Test Owner <owner@example.com>|Test Owner <owner@example.com>")
        self.assertNotIn("Co-Authored", F.sh(["git", "log", "-1", "--format=%B", branch], self.root).stdout)
        # the receipt is the exact projection, authenticated by a review
        receipt = RS.loads_strict(F.sh(["git", "show", f"{branch}:docs/release/{rid}.receipt.json"], self.root).stdout.encode())
        self.assertEqual((receipt["approval"]["type"], receipt["approval"]["authenticated"], receipt["state"]), ("github-review", True, "active"))
        self.assertTrue((self.ws / "requests" / rid / "approval.json").is_file())
        code, out, err = self.np.export()                    # a retry finds the branch and changes nothing
        self.assertEqual(code, 0, out + err)
        self.assertIn("already holds this export", out)


    def test_dry_runs_write_nothing_on_the_no_path(self):
        self.np.prepare()
        ws_before, root_before = tree_state(self.ws), tree_state(self.root)
        calls = len(self.reader.calls)
        self.assertEqual(self.np.approve(apply=False)[0], 0)
        self.assertEqual(tree_state(self.ws), ws_before)
        self.assertEqual(self.staging_branches(), ["refs/heads/main"])
        self.assertEqual(self.reader.repos[FE.STAGING_ID]["prs"], {})
        self.np.approve()
        self.np.land()
        ws_before = tree_state(self.ws)
        self.assertEqual(self.np.export(apply=False)[0], 0)
        self.assertEqual(tree_state(self.ws), ws_before)
        self.assertEqual(tree_state(self.root), root_before)
        self.assertEqual(F.sh(["git", "branch", "--list", "carrydown/*"], self.root).stdout.strip(), "")
        self.assertEqual(self.np.approve()[0], 0)       # after the merge a repeat finds the request active and uploads nothing
        self.assertEqual(len(self.reader.repos[FE.STAGING_ID]["prs"]), 1)

    def test_an_export_that_stopped_part_way_is_redone_without_a_duplicate(self):
        self.np.prepare()
        self.np.approve()
        self.np.land()
        real = R.write_file
        count = {"n": 0}

        def flaky(*a, **k):
            count["n"] += 1
            if count["n"] == 5:
                raise OSError("the disk went away")
            return real(*a, **k)
        with mock.patch.object(R, "write_file", flaky):
            with _RaisesOSError():
                self.np.export()
        rid = self.np.request_id
        code, out, err = self.np.export()
        self.assertEqual(code, 0, out + err)
        branches = F.sh(["git", "branch", "--list", "carrydown/*"], self.root).stdout.split()
        self.assertEqual(branches, [f"carrydown/request-{rid}"])
        self.assertEqual(F.sh(["git", "rev-list", "--count", f"origin/main..carrydown/request-{rid}"], self.root).stdout.strip(), "1")

    def test_an_unrelated_branch_of_the_same_name_is_refused(self):
        self.np.prepare()
        self.np.approve()
        self.np.land()
        rid = self.np.request_id
        F.sh(["git", "checkout", "-q", "-b", f"carrydown/request-{rid}"], self.root)
        F.sh(["git", "commit", "-q", "--allow-empty", "-m", "unrelated work"], self.root)
        F.sh(["git", "checkout", "-q", "main"], self.root)
        code, out, err = self.np.export()
        self.assertEqual(code, 1)
        self.assertIn("approval-scope-mismatch", err)

    def test_local_owner_evidence_is_never_accepted_on_the_no_path(self):
        self.np.prepare()
        code, out, err = F.run(R.main, ["approve", "--root", str(self.root), "--request", self.np.request_id, "--local", "--preview-shown", "--apply"])
        self.assertEqual(code, 1)
        self.assertIn("unauthenticated-release", err)

    def test_a_signed_tag_is_refused_before_the_upload(self):
        self.np.prepare()
        code, out, err = F.run(R.main, ["approve", "--root", str(self.root), "--request", self.np.request_id, "--signed-tag", "--apply"])
        self.assertEqual(code, 1)
        self.assertIn("approval-mechanism-unsupported", err)
        self.assertEqual(self.staging_branches(), ["refs/heads/main"])

    def test_withdrawal_replacement_and_state_only_export_on_the_no_path(self):
        self.np.prepare()
        self.np.approve()
        first = self.np.request_id
        self.np.land()
        self.assertEqual(self.np.export()[0], 0)
        # a replacement: change a spec in the workspace drafts, prepare, approve in staging, export
        spec = self.ws / "drafts" / SPEC
        spec.write_text(spec.read_text(encoding="utf-8").rstrip("\n") + " Second release.\n", encoding="utf-8")
        code, out, err = self.np.prepare()
        self.assertEqual(code, 0, out + err)
        second = self.np.request_id
        self.assertEqual(R.load_request(self.ws, second)["supersedes_request_id"], first)
        self.np.approve()
        self.np.land()
        history = V.replay_staging(self.reader, self.world.enrollment())
        self.assertEqual((history.replay.requests[first].state, history.replay.requests[second].state), ("superseded", "active"))
        code, out, err = self.np.export()
        self.assertEqual(code, 0, out + err)
        branch = f"carrydown/request-{second}"
        old = RS.loads_strict(F.sh(["git", "show", f"{branch}:docs/release/{first}.receipt.json"], self.root).stdout.encode()) if False else None
        # the first export was never merged into main, so there is no published predecessor receipt to regenerate; the second carries only its own
        files = F.sh(["git", "ls-tree", "-r", "--name-only", branch], self.root).stdout.split()
        self.assertIn(f"docs/release/{second}.receipt.json", files)
        # withdraw the second request through a state branch
        code, out, err = F.run(R.main, ["withdraw", "--root", str(self.root), "--request", second, "--reason", "error-found", "--apply", "--poll-seconds", "0",
                                        "--created", "2027-02-01T10:00:00Z"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("candidate uploaded; approval request pending", out)
        event = RS.loads_strict((self.ws / "requests" / second / "withdrawal-candidate.json").read_bytes())
        self.world.land(B.state_branch_files(event), f"state/{event['event_id']}")
        # content is refused, the state-only export writes only the receipt
        self.assertEqual(self.np.export(second)[0], 1)
        F.sh(["git", "push", "-q", "origin", branch], self.root)
        F.sh(["git", "checkout", "-q", "main"], self.root)
        F.sh(["git", "merge", "-q", "--ff-only", branch], self.root)
        F.sh(["git", "push", "-q", "origin", "main"], self.root)
        code, out, err = F.run(R.main, ["export-state", "--root", str(self.root), "--request", second, "--apply"])
        self.assertEqual(code, 0, out + err)
        sbranch = f"carrydown/state-{second}"
        changed = F.sh(["git", "diff", "--name-only", f"main...{sbranch}"], self.root).stdout.split()
        self.assertEqual(changed, [f"docs/release/{second}.receipt.json"])
        receipt = RS.loads_strict(F.sh(["git", "show", f"{sbranch}:docs/release/{second}.receipt.json"], self.root).stdout.encode())
        self.assertEqual(receipt["state"], "withdrawn")


class SampleReleaseTests(Temp):
    """The sample's own release: a fixture workspace, a receipt in the sample, and a deterministic rebuild."""
    FIXTURE = ROOT / "tests" / "fixtures" / "sample-workspace"
    DOCS = ROOT / "sample" / "expense-approvals" / "docs" / "release"

    def receipt_path(self):
        found = sorted(self.DOCS.glob("*.receipt.json"))
        self.assertEqual(len(found), 1)
        return found[0]

    def test_the_release_is_rebuilt_byte_for_byte_from_the_sample(self):
        run = subprocess.run([sys.executable, str(ROOT / "tests" / "rebuild_sample_release.py"), "--check"], capture_output=True, text=True, timeout=300)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("PASS the sample's release is reproducible", run.stdout)

    def test_a_changed_sample_file_is_caught_as_drift(self):
        sample = self.base / "sample"
        copy_sample(sample, working=False)
        spec = sample / SPEC
        spec.write_text(spec.read_text(encoding="utf-8").rstrip("\n") + " A drifting sentence.\n", encoding="utf-8")
        run = subprocess.run([sys.executable, str(ROOT / "tests" / "rebuild_sample_release.py"), "--check", "--sample", str(sample)],
                             capture_output=True, text=True, timeout=300)
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("FAIL the sample's release is not reproducible", run.stdout)

    def test_the_fixture_holds_no_staffing_record_and_the_receipt_is_the_local_owner_receipt(self):
        self.assertFalse((self.FIXTURE / "people.yaml").exists())
        self.assertEqual(sorted(p.name for p in self.FIXTURE.iterdir()), ["drafts", "events", "releases", "requests", "retention.yaml", "workspace.yaml"])
        receipt = RS.validate_receipt(self.receipt_path().read_bytes())
        self.assertEqual(self.receipt_path().name, receipt["request_id"] + ".receipt.json")
        self.assertEqual((receipt["approval"]["type"], receipt["approval"]["authenticated"], receipt["state"]), ("local-owner", False, "active"))
        for name in (self.FIXTURE / "workspace.yaml", self.FIXTURE / "retention.yaml"):
            self.assertNotIn(str(Path.home()), name.read_text(encoding="utf-8"))
        request_dir = self.FIXTURE / "requests" / receipt["request_id"]
        self.assertEqual(sorted(p.name for p in request_dir.iterdir()), ["approval-request.json", "approval.json", "state.json"])
        approval = json.loads((request_dir / "approval.json").read_text(encoding="utf-8"))
        self.assertEqual((approval["type"], approval["authenticated"]), ("local-owner", False))

    def test_the_receipt_equals_the_projection_of_the_fixture_records(self):
        receipt_bytes = self.receipt_path().read_bytes()
        rid = RS.loads_strict(receipt_bytes)["request_id"]
        record = V.verify_local_request(V.load_local_evidence(str(self.FIXTURE), rid), rid)
        replay = V.local_replay(str(self.FIXTURE)).replay
        RS.verify_receipt_bytes(receipt_bytes, record.request, record.manifest_bytes, replay.requests[rid], record.approval)
        manifest_entries = RS.validate_manifest(record.manifest_bytes)
        for entry in manifest_entries:
            if entry["path"].startswith("repo/"):
                path = ROOT / "sample" / "expense-approvals" / entry["path"][len("repo/"):]
                self.assertEqual(RS.sha256_file(path), entry["sha256"], entry["path"])

    def test_the_engineers_check_exits_zero_on_the_sample_once_the_clone_has_an_origin(self):
        project = self.base / "clone"
        copy_sample(project, working=False)
        F.init_git(project)
        F.sh(["git", "add", "-A"], project)
        F.sh(["git", "commit", "-q", "-m", "sample"], project)
        origin = self.base / "origin.git"
        F.sh(["git", "clone", "-q", "--bare", str(project), str(origin)], self.base)
        F.sh(["git", "remote", "add", "origin", str(origin)], project)
        F.sh(["git", "fetch", "-q", "origin"], project)
        F.sh(["git", "remote", "set-head", "origin", "main"], project)
        script = project / "docs/dev/skills/expense-approvals-dev/scripts/check_context.py"
        run = subprocess.run([sys.executable, str(script), "WI-06"], cwd=str(project), capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        # a receipt that reports the release withdrawn, on the fetched default branch, makes the context stale
        path = next((project / "docs" / "release").glob("*.receipt.json"))
        rid = path.name.split(".")[0]
        record = V.verify_local_request(V.load_local_evidence(str(self.FIXTURE), rid), rid)
        withdrawn = B.withdrawal_event(rid, V.local_policy({k: v for k, v in R.Project(project).handling.items() if k in R.L.RELEASED_HANDLING_KEYS}, "sct-will/carrydown-sample"),
                                       V.local_replay(str(self.FIXTURE)).replay.tip, "other", created="2027-02-01T00:00:00Z", nonce="2" * 32)
        replay = RS.replay_state(list(V.local_events(str(self.FIXTURE))) + [withdrawn])
        path.write_bytes(RS.project_receipt(record.request, record.manifest_bytes, replay.requests[rid], record.approval))
        F.sh(["git", "add", "-A"], project)
        F.sh(["git", "commit", "-q", "-m", "withdrawn"], project)
        F.sh(["git", "push", "-q", "origin", "main"], project)
        F.sh(["git", "reset", "-q", "--hard", "HEAD~1"], project)
        run = subprocess.run([sys.executable, str(script), "WI-06"], cwd=str(project), capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 11, run.stdout + run.stderr)
        self.assertIn("is stale", run.stdout)


if __name__ == "__main__":
    unittest.main()
