"""Tests for scripts/release_verify.py over the in-memory model of GitHub in tests/mock/fake_evidence.py.

Offline. No token, no network. Tests marked [G1], [G2], [G4] or [G6] are the negative tests of the
specification (Part G) that WP11 collects.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import fake_evidence as F  # noqa: E402
import release_build as B  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402


def refused(call, *args, **kwargs):
    """The reason code a call is refused with, or None when it succeeds."""
    try:
        call(*args, **kwargs)
    except RS.SchemaError as e:
        return e.code
    return None


class World:
    pass


class VerifyBase(unittest.TestCase):
    def setUp(self):
        self.w = F.World()
        self.r = self.w.reader
        self.enr = self.w.enrollment()

    def approved(self, **kw):
        c = F.make_candidate(self.w, **kw)
        c.land()
        return c

    def targets(self, c):
        return V.verify_targets(self.r, self.enr, c.request["receipt_template"]["targets"], c.request["receipt_template"]["audience"])

    def context(self, c, now=None):
        rec = V.verify_request(c.rid, self.r, self.enr)
        hist = V.replay_staging(self.r, self.enr)
        return V.authorize_content(rec, hist.replay, self.enr, self.targets(c), now=now)


class EnrollmentTests(VerifyBase):
    def test_identity_is_stable_and_the_policy_digest_changes_with_the_policy(self):
        before = self.enr
        self.assertEqual(before.enrollment_id, V.enrollment_id_of("github.com", 4100, 4200))
        after = self.w.update_policy(lambda e: e["approvers"].append({"id": 5, "login": "second"}))
        self.assertEqual(after.enrollment_id, before.enrollment_id)
        self.assertNotEqual(after.policy_sha256, before.policy_sha256)
        self.assertEqual(V.policy_sha256_of(after.entry), after.policy_sha256)

    def test_a_policy_digest_that_does_not_match_its_entry_is_refused(self):
        self.w.entry["policy_sha256"] = "0" * 64
        import json
        doc = {"format": 1, "host": "github.com", "tooling_repository_id": 4100, "repositories": [self.w.entry]}
        self.r.set_file(4100, "enrollment.yaml", json.dumps(doc).encode())
        self.assertEqual(refused(self.w.enrollment), "policy-revision-mismatch")

    def test_a_replacement_repository_with_the_same_name_is_not_the_enrolled_one(self):
        self.assertEqual(refused(V.load_current_enrollment, 9999, self.r, "acme/carrydown-tooling"), "policy-pointer-mismatch")

    def test_a_pointer_that_names_another_enrollment_is_refused(self):
        code = refused(V.load_current_enrollment, 4200, self.r, "acme/carrydown-tooling", None, "f" * 64)
        self.assertEqual(code, "policy-pointer-mismatch")

    def test_a_captured_policy_must_be_an_ancestor_of_the_protected_tip(self):
        old = self.enr
        self.w.update_policy(lambda e: e.update(offline_grace_days=3))
        current = self.w.enrollment()
        self.assertEqual(V.captured_policy(self.r, current, old.policy_commit_sha, old.policy_sha256).policy_sha256, old.policy_sha256)
        # a commit on another branch of the tooling repository is not an ancestor
        stray = self.r.commit(4100, {"enrollment.yaml": b"{}"}, [self.r.repos[4100]["branches"]["main"]])
        stray_tree = self.r.repos[4100]["commits"][stray]["parents"] = []
        self.assertEqual(refused(V.captured_policy, self.r, current, stray, old.policy_sha256), "policy-revision-mismatch")


class ApprovalTests(VerifyBase):
    def test_valid_content_with_an_authorized_review_on_the_final_head_verifies(self):
        c = self.approved()
        rec = V.verify_request(c.rid, self.r, self.enr)
        self.assertEqual((rec.request_id, rec.release_id, rec.mechanism), (c.rid, c.release_id, "github-review"))
        self.assertEqual((rec.approval.type, rec.approval.authenticated), ("github-review", True))
        self.assertEqual(rec.review.reviewer_id, F.OWNER[0])
        self.assertEqual(rec.manifest_bytes, c.manifest)
        hist = V.replay_staging(self.r, self.enr)
        self.assertEqual(hist.replay.active, c.rid)

    def test_G2_a_review_of_an_earlier_commit_is_not_an_approval(self):
        """[G2]"""
        c = F.make_candidate(self.w)
        n = self.r.open_pr(F.STAGING_ID, c.branch, c.files())
        self.r.review(F.STAGING_ID, n, *F.OWNER)
        self.r.push_more(F.STAGING_ID, n, {})
        self.r.merge(F.STAGING_ID, n)
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "approval-not-on-final-revision")

    def test_a_dismissed_review_is_not_an_approval(self):
        c = F.make_candidate(self.w)
        n = self.r.open_pr(F.STAGING_ID, c.branch, c.files())
        review = self.r.review(F.STAGING_ID, n, *F.OWNER)
        self.r.dismiss(F.STAGING_ID, n, review)
        self.r.merge(F.STAGING_ID, n)
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "approval-not-found")

    def test_a_later_changes_request_by_the_same_reviewer_removes_the_approval(self):
        c = F.make_candidate(self.w)
        n = self.r.open_pr(F.STAGING_ID, c.branch, c.files())
        self.r.review(F.STAGING_ID, n, *F.OWNER)
        self.r.review(F.STAGING_ID, n, F.OWNER[0], F.OWNER[1], state="CHANGES_REQUESTED")
        self.r.merge(F.STAGING_ID, n)
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "approval-not-found")

    def test_an_approval_by_an_account_the_policy_does_not_list_is_refused(self):
        c = F.make_candidate(self.w)
        c.land(reviewer=F.OUTSIDER)
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "approver-not-authorized")

    def test_a_merge_with_no_review_is_not_approved(self):
        c = F.make_candidate(self.w)
        c.land(approve=False)
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "approval-not-found")

    def test_an_unmerged_request_is_not_approved(self):
        c = F.make_candidate(self.w)
        c.land(merge=False)
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "approval-not-found")

    def test_G2_request_bytes_that_differ_in_the_merge_commit_are_refused(self):
        """[G2]"""
        c = self.approved()
        merge = self.r.repos[F.STAGING_ID]["branches"]["main"]
        path = f"requests/{c.rid}/approval-request.json"
        self.r.repos[F.STAGING_ID]["commits"][merge]["tree"][path] = ("100644", c.files()[path] + b" ")
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "sha256-mismatch")

    def test_G2_manifest_bytes_that_differ_in_the_merge_commit_are_refused(self):
        """[G2]"""
        c = self.approved()
        merge = self.r.repos[F.STAGING_ID]["branches"]["main"]
        path = f"releases/{c.release_id}/content-manifest.json"
        self.r.repos[F.STAGING_ID]["commits"][merge]["tree"][path] = ("100644", c.manifest + b" ")
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "sha256-mismatch")

    def test_a_snapshot_file_that_differs_in_the_merge_commit_is_refused(self):
        c = self.approved()
        merge = self.r.repos[F.STAGING_ID]["branches"]["main"]
        path = f"releases/{c.release_id}/snapshot/repo/docs/spec/plan.yaml"
        self.r.repos[F.STAGING_ID]["commits"][merge]["tree"][path] = ("100644", b"changed\n")
        self.r.repos[F.STAGING_ID]["blobs"][F.blob_sha(b"changed\n")] = b"changed\n"
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "sha256-mismatch")

    def test_an_extra_file_in_the_snapshot_or_a_changed_mode_is_refused(self):
        c = self.approved()
        merge = self.r.repos[F.STAGING_ID]["branches"]["main"]
        tree = self.r.repos[F.STAGING_ID]["commits"][merge]["tree"]
        tree[f"releases/{c.release_id}/snapshot/repo/extra.md"] = ("100644", b"x")
        self.r.repos[F.STAGING_ID]["blobs"][F.blob_sha(b"x")] = b"x"
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "sha256-mismatch")
        del tree[f"releases/{c.release_id}/snapshot/repo/extra.md"]
        path = f"releases/{c.release_id}/snapshot/repo/docs/spec/plan.yaml"
        tree[path] = ("100755", tree[path][1])
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "sha256-mismatch")
        tree[path] = ("120000", tree[path][1])
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "unsafe-artifact-path")

    def test_a_stored_digest_changed_without_its_input_fails_recomputation(self):
        c = F.make_candidate(self.w)
        files = c.files()
        path = f"requests/{c.rid}/approval-request.json"
        tampered = files[path].replace(c.rid.encode(), (("0" if c.rid[0] != "0" else "1") + c.rid[1:]).encode())
        files[path] = tampered
        self.w.land(files, c.branch)
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "sha256-mismatch")

    def test_a_pull_request_that_edits_an_existing_file_is_refused(self):
        self.approved()
        c2 = F.make_candidate(self.w, files={"repo/docs/spec/plan.yaml": b"second\n"})
        files = c2.files()
        files["releases/" + c2.release_id + "/snapshot/repo/docs/spec/plan.yaml"] = b"second\n"
        files[".github/workflows/open-release-request.yml"] = b"name: changed\n"
        n = self.r.open_pr(F.STAGING_ID, c2.branch, files)
        self.r.review(F.STAGING_ID, n, *F.OWNER)
        report = V.verify_candidate(self.r, self.enr, n)
        self.assertEqual((report.ok, report.code), (False, "artifact-operation-unsupported"))

    def test_an_unmanifested_file_in_a_request_branch_is_refused(self):
        c = F.make_candidate(self.w)
        files = c.files()
        files[".github/workflows/open-release-request.yml"] = b"name: changed\n"
        n = self.r.open_pr(F.STAGING_ID, c.branch, files)
        self.assertEqual(V.verify_candidate(self.r, self.enr, n).code, "artifact-operation-unsupported")
        files = c.files()
        files["notes/private.md"] = b"x"
        n = self.r.open_pr(F.STAGING_ID, "request/" + "a" * 64, files)
        self.assertEqual(V.verify_candidate(self.r, self.enr, n).code, "unsafe-artifact-path")


class StateTests(VerifyBase):
    def test_G1_a_request_that_was_never_activated_authorizes_nothing(self):
        """[G1]"""
        c = self.approved()
        rec = V.verify_request(c.rid, self.r, self.enr)
        empty = RS.replay_state([])
        self.assertEqual(refused(V.authorize_content, rec, empty, self.enr, self.targets(c)), "not-approved")

    def test_first_approval_activates_without_an_earlier_state_file(self):
        c = self.approved()
        hist = V.replay_staging(self.r, self.enr)
        self.assertEqual(hist.replay.requests[c.rid].state, "active")
        ctx = self.context(c)
        self.assertEqual((ctx.kind, ctx.request_id, ctx.authenticated), ("content", c.rid, True))

    def test_replacement_supersedes_the_old_request_and_activates_the_new_one_in_one_batch(self):
        a = self.approved()
        b = F.make_candidate(self.w, files={"repo/docs/spec/plan.yaml": b"second\n"}, supersedes=a.rid)
        self.assertEqual([t["to"] for t in b.event["transitions"]], ["superseded", "active"])
        b.land()
        hist = V.replay_staging(self.r, self.enr)
        self.assertEqual((hist.replay.requests[a.rid].state, hist.replay.requests[b.rid].state), ("superseded", "active"))
        self.assertEqual(hist.replay.requests[a.rid].superseded_by, b.rid)
        self.assertEqual(hist.replay.requests[b.rid].supersedes, a.rid)
        # only the new request authorizes content; the old one is superseded
        rec_a = V.verify_request(a.rid, self.r, self.enr)
        self.assertEqual(refused(V.authorize_content, rec_a, hist.replay, self.enr, self.targets(a)), "superseded")
        self.assertEqual(self.context(b).request_id, b.rid)

    def test_G6_withdrawal_ends_content_publication_but_state_only_receipts_remain_possible(self):
        """[G4] [G6]"""
        c = self.approved()
        event = B.withdrawal_event(c.rid, self.enr, tip_of(self.w), "error-found", created=self.r.tick(), nonce=B.new_nonce())
        self.w.land(B.state_branch_files(event), f"state/{event['event_id']}")
        rec = V.verify_request(c.rid, self.r, self.enr)
        hist = V.replay_staging(self.r, self.enr)
        self.assertEqual(hist.replay.requests[c.rid].state, "withdrawn")
        self.assertEqual(refused(V.authorize_content, rec, hist.replay, self.enr, self.targets(c)), "withdrawn")
        receipt = RS.project_receipt(rec.request, rec.manifest_bytes, hist.replay.requests[c.rid], rec.approval)
        path = f"docs/release/{c.rid}.receipt.json"
        ctx = V.authorize_state_receipt(rec, hist.replay, self.enr, {path: RS.sha256_bytes(receipt)})
        self.assertEqual((ctx.kind, sorted(ctx.receipt_digests)), ("state", [path]))
        self.assertEqual(ctx.entries, {})
        # a spec cannot ride along with the receipt
        self.assertEqual(refused(V.authorize_state_receipt, rec, hist.replay, self.enr, {path: "0" * 64, "docs/spec/plan.yaml": "0" * 64}),
                         "state-only-content-write")

    def test_a_state_context_needs_a_terminal_state(self):
        c = self.approved()
        rec = V.verify_request(c.rid, self.r, self.enr)
        hist = V.replay_staging(self.r, self.enr)
        self.assertEqual(refused(V.authorize_state_receipt, rec, hist.replay, self.enr, {f"docs/release/{c.rid}.receipt.json": "0" * 64}),
                         "not-approved")

    def test_a_terminal_request_never_becomes_active_again(self):
        c = self.approved()
        w = B.withdrawal_event(c.rid, self.enr, tip_of(self.w), "other", created=self.r.tick(), nonce=B.new_nonce())
        self.w.land(B.state_branch_files(w), f"state/{w['event_id']}")
        back = B.build_event([B.transition(c.rid, "prepared", "active", w["event_id"], "release-approved")], self.enr,
                             created=self.r.tick(), nonce=B.new_nonce())
        self.w.land(B.state_branch_files(back), f"state/{back['event_id']}")
        self.assertEqual(refused(V.replay_staging, self.r, self.enr), "state-history-invalid")

    def test_two_active_requests_are_a_mixed_release(self):
        a = self.approved()
        b = F.make_candidate(self.w, files={"repo/docs/spec/plan.yaml": b"second\n"})     # does not supersede a
        b.land()
        self.assertEqual(refused(V.replay_staging, self.r, self.enr), "mixed-release")

    def test_G2_two_concurrent_replacements_cannot_both_merge(self):
        """[G2] The second branch names a predecessor that is no longer the tip, and is no longer up to date."""
        a = self.approved()
        base = self.r.repos[F.STAGING_ID]["branches"]["main"]
        b = F.make_candidate(self.w, files={"repo/docs/spec/plan.yaml": b"b\n"}, supersedes=a.rid)
        c = F.make_candidate(self.w, files={"repo/docs/spec/plan.yaml": b"c\n"}, supersedes=a.rid)
        nb = self.r.open_pr(F.STAGING_ID, b.branch, b.files())
        nc = self.r.open_pr(F.STAGING_ID, c.branch, c.files())
        for n in (nb, nc):
            self.r.review(F.STAGING_ID, n, *F.OWNER)
        self.assertTrue(V.verify_candidate(self.r, self.enr, nb).ok)
        self.assertTrue(V.verify_candidate(self.r, self.enr, nc).ok)
        self.r.merge(F.STAGING_ID, nb)
        report = V.verify_candidate(self.r, self.enr, nc)
        self.assertEqual((report.ok, report.code), (False, "state-history-invalid"))
        # rebuilt on the new tip and reviewed again, it names the new predecessor and passes only if it supersedes b
        c2 = F.make_candidate(self.w, files={"repo/docs/spec/plan.yaml": b"c\n"}, supersedes=b.rid, nonce=B.new_nonce())
        n2 = self.r.open_pr(F.STAGING_ID, c2.branch, c2.files())
        self.assertEqual(V.verify_candidate(self.r, self.enr, n2).code, "approval-not-found")     # no review yet
        self.r.review(F.STAGING_ID, n2, *F.OWNER)
        self.assertTrue(V.verify_candidate(self.r, self.enr, n2).ok)

    def test_a_forged_by_field_and_a_state_json_grant_no_authority(self):
        c = self.approved()
        files = {"events/" + "9" * 64 + ".json": b'{"by": "sct-will", "to": "active"}', "state.json": b'{"state": "active"}'}
        n = self.r.open_pr(F.STAGING_ID, "state/" + "9" * 64, files)
        self.r.review(F.STAGING_ID, n, *F.OWNER)
        self.assertFalse(V.verify_candidate(self.r, self.enr, n).ok)
        self.assertEqual(V.replay_staging(self.r, self.enr).replay.active, c.rid)

    def test_G4_expiry_is_computed_from_the_approved_time(self):
        """[G4]"""
        soon = V.utc_text(V.clock() + 3600)
        c = self.approved(expires=soon)
        self.assertEqual(self.context(c).expires_at, soon)
        rec = V.verify_request(c.rid, self.r, self.enr)
        hist = V.replay_staging(self.r, self.enr)
        self.assertEqual(refused(V.authorize_content, rec, hist.replay, self.enr, self.targets(c), now=V.clock() + 7200), "expired")

    def test_the_approver_must_still_be_authorized_and_the_policy_must_be_current(self):
        c = self.approved()
        rec = V.verify_request(c.rid, self.r, self.enr)
        hist = V.replay_staging(self.r, self.enr)
        gone = self.w.update_policy(lambda e: e.update(approvers=[{"id": 777, "login": "someone-else"}]))
        self.r.users[777] = {"id": 777, "login": "someone-else"}
        self.assertEqual(refused(V.authorize_content, rec, hist.replay, gone, self.targets(c)), "policy-revision-mismatch")

    def test_local_owner_evidence_is_refused_for_an_enrolled_project(self):
        c = self.approved()
        rec = V.verify_request(c.rid, self.r, self.enr)
        local = rec._replace(approval=RS.VerifiedApproval(c.rid, "local-owner", False))
        hist = V.replay_staging(self.r, self.enr)
        self.assertEqual(refused(V.authorize_content, local, hist.replay, self.enr, self.targets(c)), "unauthenticated-release")

    def test_wrong_target_identity_and_visibility_are_refused_before_any_write(self):
        c = self.approved()
        rec = V.verify_request(c.rid, self.r, self.enr)
        hist = V.replay_staging(self.r, self.enr)
        good = self.targets(c)
        bad = dict(good)
        bad["engineering"] = V.ResolvedTarget(dict(good["engineering"].identity, repository_id=1), False, None)
        self.assertEqual(refused(V.authorize_content, rec, hist.replay, self.enr, bad), "target-identity-mismatch")
        self.assertEqual(refused(V.authorize_content, rec, hist.replay, self.enr, {}), "target-identity-mismatch")
        self.r.repos[4200]["private"], self.r.repos[4200]["visibility"] = False, "public"
        self.assertEqual(refused(self.targets, c), "audience-visibility-mismatch")

    def test_a_renamed_repository_keeps_its_identity_and_a_replacement_with_the_old_name_does_not(self):
        c = self.approved()
        self.r.repos[4200]["full_name"] = "acme/renamed"
        self.assertEqual(self.targets(c)["engineering"].identity["repository"], "acme/renamed")
        ctx = self.context(c)
        self.assertEqual(ctx.target_ids, ("engineering",))
        self.r.repos[5555] = dict(self.r.repos.pop(4200), id=5555, full_name="acme/expense-approvals")
        self.assertEqual(refused(self.targets, c), "target-identity-mismatch")

    def test_a_board_with_another_node_id_or_a_broader_audience_is_refused(self):
        board = dict(id="board", **self.w.entry["allowed_targets"]["board"])
        c = self.approved(targets=[dict(id="engineering", **self.w.entry["allowed_targets"]["engineering"]), board], destinations=("engineering-repo", "board"))
        self.assertEqual(sorted(self.targets(c)), ["board", "engineering"])
        self.r.projects["PVT_example"]["reader_ids"].append(999999)
        self.assertEqual(refused(self.targets, c), "audience-visibility-mismatch")
        self.r.projects["PVT_example"]["reader_ids"] = None
        self.assertEqual(refused(self.targets, c), "destination-access-not-verified")
        self.r.projects["PVT_example"]["reader_ids"] = [F.OWNER[0]]
        self.r.projects["PVT_example"]["owner_id"] = 1
        self.assertEqual(refused(self.targets, c), "target-identity-mismatch")


class ListingTests(VerifyBase):
    def test_an_incomplete_listing_is_a_refusal_and_never_a_clean_result(self):
        self.approved()
        self.r.truncate("pull_requests")
        self.assertEqual(refused(V.replay_staging, self.r, self.enr), "evidence-unavailable")
        self.assertEqual(refused(V.verify_request, "a" * 64, self.r, self.enr), "evidence-unavailable")

    def test_a_listing_that_cannot_be_read_is_a_refusal(self):
        c = self.approved()
        self.r.fail("reviews", F.STAGING_ID)
        self.assertEqual(refused(V.verify_request, c.rid, self.r, self.enr), "evidence-unavailable")


class PrerequisiteTests(VerifyBase):
    def statuses(self, comps=None):
        comps = comps or V.verify_prerequisites(self.r, self.enr, workspace_access=True)
        return {c.name: c.status for c in comps}

    def test_a_healthy_organization_verifies_every_component(self):
        self.assertEqual(set(self.statuses().values()), {V.VERIFIED})
        self.assertIsNone(refused(V.require, V.verify_prerequisites(self.r, self.enr, workspace_access=True), V.EXPORT_COMPONENTS))

    def test_D14_an_unauthorized_direct_collaborator_blocks_the_first_upload(self):
        self.r.collaborators_by_repo[F.STAGING_ID].append({"id": 999, "login": "outsider", "permission": "read"})
        comps = V.verify_prerequisites(self.r, self.enr, workspace_access=True)
        self.assertEqual(self.statuses(comps)["staging-readers"], V.MISSING)
        self.assertEqual(refused(V.require, comps, V.UPLOAD_COMPONENTS), "staging-access-not-verified")

    def test_an_inherited_team_reader_a_deploy_key_and_an_unexpected_app_block_the_upload(self):
        for attr, row in (("teams_by_repo", {"id": 1, "slug": "everyone", "permission": "pull"}),
                          ("deploy_keys_by_repo", {"id": 1, "read_only": True}),
                          ("installations_by_repo", {"id": 9, "slug": "stray-app"})):
            with self.subTest(attr=attr):
                getattr(self.r, attr)[F.STAGING_ID] = [row]
                self.assertEqual(self.statuses()["staging-readers"], V.MISSING)
                getattr(self.r, attr)[F.STAGING_ID] = []

    def test_an_approved_service_reader_passes(self):
        self.w.update_policy(lambda e: e["staging_readers"].update(approved_service_ids=["carrydown-app-installation"]))
        enr = self.w.enrollment()
        self.r.installations_by_repo[F.STAGING_ID] = [{"id": 9, "slug": "carrydown-app-installation"}]
        comps = V.verify_prerequisites(self.r, enr, workspace_access=True)
        self.assertEqual(self.statuses(comps)["staging-readers"], V.VERIFIED)

    def test_an_unreadable_access_list_needs_a_current_scoped_attestation(self):
        self.r.fail("collaborators", F.STAGING_ID)
        self.assertEqual(self.statuses()["staging-readers"], V.NOT_VERIFIABLE)
        subject = {"repository_id": F.STAGING_ID, "reader_ids": sorted(self.w.entry["staging_readers"]["user_ids"]), "service_ids": []}

        def attest(expires_in, by=F.ADMIN[0], subj=subject):
            att = {"component": "staging-readers", "by_id": by, "at": V.utc_text(V.clock() - 60), "expires_at": V.utc_text(V.clock() + expires_in),
                   "subject": subj, "note": "inspected"}
            return self.w.update_policy(lambda e: e["attestations"].append(att))
        expired = attest(-30)
        self.assertEqual(self.statuses(V.verify_prerequisites(self.r, expired, workspace_access=True))["staging-readers"], V.NOT_VERIFIABLE)
        self.w.entry["attestations"] = [a for a in self.w.entry["attestations"] if a["component"] != "staging-readers"]
        good = attest(3600)
        self.assertEqual(self.statuses(V.verify_prerequisites(self.r, good, workspace_access=True))["staging-readers"], V.VERIFIED)
        # an attestation by someone who is not an administrator, or for a different reader set, counts for nothing
        self.w.entry["attestations"] = [a for a in self.w.entry["attestations"] if a["component"] != "staging-readers"]
        by_stranger = attest(3600, by=777)
        self.assertEqual(self.statuses(V.verify_prerequisites(self.r, by_stranger, workspace_access=True))["staging-readers"], V.NOT_VERIFIABLE)
        self.w.entry["attestations"] = [a for a in self.w.entry["attestations"] if a["component"] != "staging-readers"]
        other = attest(3600, subj=dict(subject, reader_ids=[1, 2]))
        self.assertEqual(self.statuses(V.verify_prerequisites(self.r, other, workspace_access=True))["staging-readers"], V.NOT_VERIFIABLE)

    def test_an_attestation_never_substitutes_for_a_live_fact(self):
        # the scan health is a live fact: an attestation does not cover it
        att = {"component": "scan-health", "by_id": F.ADMIN[0], "at": V.utc_text(V.clock() - 60), "expires_at": V.utc_text(V.clock() + 3600),
               "subject": {"repository_id": 4200}, "note": "x"}
        enr = self.w.update_policy(lambda e: e["attestations"].append(att))
        self.r.scan[4100]["completed_at"] = V.utc_text(V.clock() - 86400)
        self.assertEqual(self.statuses(V.verify_prerequisites(self.r, enr, workspace_access=True))["scan-health"], V.MISSING)
        self.assertEqual(refused(V.require, V.verify_prerequisites(self.r, enr, workspace_access=True), V.EXPORT_COMPONENTS), "verifier-unhealthy")

    def test_expired_runtime_isolation_blocks_export_but_not_the_upload(self):
        for a in self.w.entry["attestations"]:
            if a["component"] == "runtime-isolation":
                a["expires_at"] = V.utc_text(V.clock() - 5)
        enr = self.w.update_policy(lambda e: None)
        comps = V.verify_prerequisites(self.r, enr, workspace_access=True)
        self.assertIsNone(refused(V.require, comps, V.UPLOAD_COMPONENTS))
        self.assertEqual(refused(V.require, comps, V.EXPORT_COMPONENTS), "setup-not-verified")

    def test_a_last_pusher_approval_requirement_is_reported_as_such(self):
        self.r.rulesets_by_repo[F.STAGING_ID] = [F.staging_ruleset(last_push=True)]
        self.assertIn("require_last_push_approval", V.staging_ruleset_problem(self.r.rulesets(F.STAGING_ID)))
        self.assertEqual(self.statuses()["staging-ruleset"], V.MISSING)
        for bad in (F.staging_ruleset(reviews=0), F.staging_ruleset(stale=False), F.staging_ruleset(check="other"), F.staging_ruleset(strict=False),
                    F.staging_ruleset(no_force=False), F.staging_ruleset(bypass=True), F.staging_ruleset(methods=("merge", "squash"))):
            self.assertIsNotNone(V.staging_ruleset_problem([bad]))
        self.assertIsNone(V.staging_ruleset_problem([F.staging_ruleset()]))

    def test_the_workflow_must_match_the_enrolled_digest(self):
        self.r.set_file(F.STAGING_ID, ".github/workflows/open-release-request.yml", b"name: tampered\n")
        self.assertEqual(self.statuses()["staging-workflow"], V.MISSING)

    def test_a_staging_repository_that_is_not_private_is_refused(self):
        self.r.repos[F.STAGING_ID]["private"], self.r.repos[F.STAGING_ID]["visibility"] = False, "public"
        self.assertEqual(self.statuses()["staging-identity"], V.MISSING)

    def test_the_engineering_ruleset_must_require_the_release_check(self):
        self.r.rulesets_by_repo[F.ENGINEERING_ID] = []
        self.assertEqual(self.statuses()["engineering-ruleset"], V.MISSING)
        self.r.fail("rulesets", F.ENGINEERING_ID)
        self.assertEqual(self.statuses()["engineering-ruleset"], V.NOT_VERIFIABLE)

    def test_the_pinned_verifier_commit_must_exist_and_differ_from_the_policy_commit(self):
        enr = self.w.update_policy(lambda e: e.update(verifier_sha="1" * 40), keep_verifier=True)
        self.assertEqual(self.statuses(V.verify_prerequisites(self.r, enr, workspace_access=True))["verifier-code"], V.MISSING)

    def test_G5_verification_reads_through_the_reader_only(self):
        c = self.approved()
        before = len(self.r.calls)
        V.verify_request(c.rid, self.r, self.enr)
        self.assertGreater(len(self.r.calls), before)
        self.assertFalse([m for m in dir(V.EvidenceReader) if m.startswith(("push", "write", "create", "put", "delete", "set", "merge"))])


def tip_of(world):
    return F.tip_of(world)


if __name__ == "__main__":
    unittest.main()
