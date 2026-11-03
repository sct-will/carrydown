"""Tests for the independent verifier: engineering pull requests, the polling loop and the staging check.

Work package 7. Offline: no token and no network. The organization is the in-memory model of
tests/mock/fake_evidence.py. The heavy fixture (a real release prepared, approved, merged and exported
through release.py) is built once per class by tests/mock/engineering_fixture.py. Tests marked [G2], [G4]
or [G5] are the negative tests of the specification (Part G) that WP11 collects.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import engineering_fixture as EF  # noqa: E402
import fake_evidence as FE  # noqa: E402
import release_build as B  # noqa: E402
import release_engineering as RE  # noqa: E402
import release_scan as S  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402

POINTER = EF.POINTER
CODE = "9" * 40
TOOLING = "acme/carrydown-tooling"


def codes(report):
    return [f.code for f in report.findings]


def pointer_text(enrollment):
    return f"format: 1\ntooling_repository: {TOOLING}\nenrollment_id: {enrollment.enrollment_id}\n".encode("utf-8")


def captured(reader):
    tip = reader.branch_head(FE.TOOLING_ID, "main")
    return V.capture_enrollments(reader, TOOLING, tip, reader.file_at(FE.TOOLING_ID, tip, "enrollment.yaml"))


def run_scan(reader, publisher=None, **kw):
    publisher = publisher or FE.FakeCheckPublisher()
    return S.scan(reader, publisher, captured(reader), **kw), publisher


def check_of(reader, publisher, number, kind="engineering"):
    repo = FE.ENGINEERING_ID if kind == "engineering" else FE.STAGING_ID
    head = reader.repos[repo]["prs"][number]["head"]["sha"]
    return publisher.state(repo, head, V.ENGINEERING_CHECK if kind == "engineering" else V.STAGING_CHECK)


class ExportedBase(unittest.TestCase):
    """A real release, exported, in a fictional organization. One copy per class; each test gets its own."""
    edits = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="carrydown-verifier-")
        world = FE.World()
        if cls.edits:
            world.update_policy(lambda e: e.update(engineer_edits=cls.edits))
        cls.ex = EF.Exported(Path(cls.tmp), world=world)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.case = EF.Case(self.ex)
        self.r = self.case.reader
        self.enr = self.case.enrollment()
        self.rid = self.ex.rid
        self.receipt_path = self.ex.receipt_path
        self.spec = next(p for p in sorted(self.ex.files) if p.startswith("docs/spec/") and p.rsplit("/", 1)[-1].startswith("wi-")
                         and b"## Decisions recorded" in self.ex.files[p][1] and b"## Outcome" in self.ex.files[p][1])

    def verify(self, number, now=None):
        return RE.verify_engineering(self.r, self.enr, number, now=now)

    def text(self, path):
        return self.ex.files[path][1].decode("utf-8")


class EngineeringTests(ExportedBase):
    def test_valid_content_and_its_regenerated_receipt_pass(self):
        report = self.verify(self.case.open())
        self.assertTrue(report.ok, report.findings)
        self.assertEqual((report.kind, report.request_ids), ("content", (self.rid,)))

    def test_a_receipt_passes_without_being_listed_in_its_own_manifest(self):
        record = V.verify_request(self.rid, self.r, self.enr)
        self.assertFalse([e for e in record.entries if "docs/release/" in e["path"]])
        listed = [a["path"] for a in RS.loads_strict(self.ex.files[self.receipt_path][1])["artifacts"]]
        self.assertNotIn(self.receipt_path, listed)
        self.assertTrue(self.verify(self.case.open()).ok)

    def test_G2_changed_bytes_fail(self):
        """[G2]"""
        report = self.verify(self.case.open(edit={self.spec: self.ex.files[self.spec][1] + b"\nAn unreviewed line.\n"}))
        self.assertFalse(report.ok)
        self.assertEqual(report.code, "sha256-mismatch")
        self.assertIn(self.spec, [f.where for f in report.findings])

    def test_a_changed_file_mode_fails(self):
        report = self.verify(self.case.open(edit={self.spec: ("100755", self.ex.files[self.spec][1])}))
        self.assertEqual((report.ok, report.code), (False, "sha256-mismatch"))

    def test_G2_a_review_of_an_earlier_commit_fails(self):
        """[G2]"""
        n = self.case.open()
        pr = self.r.repos[FE.STAGING_ID]["prs"][self.staging_pr()]
        pr["reviews"][0]["commit_id"] = "0" * 40
        self.assertEqual(self.verify(n).code, "approval-not-on-final-revision")

    def test_a_dismissed_review_fails(self):
        n = self.case.open()
        number = self.staging_pr()
        self.r.dismiss(FE.STAGING_ID, number, self.r.repos[FE.STAGING_ID]["prs"][number]["reviews"][0]["id"])
        self.assertEqual(self.verify(n).code, "approval-not-found")

    def test_an_approval_by_an_account_that_is_not_an_approver_fails(self):
        n = self.case.open()
        self.r.repos[FE.STAGING_ID]["prs"][self.staging_pr()]["reviews"][0]["user"]["id"] = 999
        self.assertEqual(self.verify(n).code, "approver-not-authorized")

    def staging_pr(self):
        return next(n for n, p in self.r.repos[FE.STAGING_ID]["prs"].items() if p["head"]["ref"] == f"request/{self.rid}")

    def receipt_with(self, **changes):
        receipt = RS.loads_strict(self.ex.files[self.receipt_path][1])
        receipt.update(changes)
        return RS.canonical_json(receipt)

    def test_local_owner_evidence_fails_for_an_enrolled_project(self):
        record = V.verify_request(self.rid, self.r, self.enr)
        state = V.replay_staging(self.r, self.enr).replay.requests[self.rid]
        local = RS.project_receipt(record.request, record.manifest_bytes, state, RS.VerifiedApproval(self.rid, "local-owner", False))
        self.assertEqual(self.verify(self.case.open(edit={self.receipt_path: local})).code, "unauthenticated-release")

    def test_a_changed_receipt_scope_fails(self):
        for change in ({"audience": "public"}, {"destinations": ["engineering-repo"]}, {"expires_at": "2099-01-01T00:00:00Z"},
                       {"offline_grace_days": 30}, {"downstream": {"assignees": True, "capacity_summary": False, "evidence": "synthetic-only"}}):
            report = self.verify(self.case.open(edit={self.receipt_path: self.receipt_with(**change)}))
            self.assertEqual((report.ok, report.code), (False, "receipt-projection-mismatch"), change)

    def test_a_receipt_with_an_unknown_field_or_a_different_state_fails(self):
        for edit in (self.receipt_with(unknown="x"), self.receipt_with(state="superseded", superseded_by="1" * 64)):
            self.assertFalse(self.verify(self.case.open(edit={self.receipt_path: edit})).ok)

    def test_a_receipt_shaped_file_outside_its_exact_path_cannot_bypass_artifact_validation(self):
        stray = self.ex.files[self.receipt_path][1]
        report = self.verify(self.case.open(edit={"docs/spec/extra.receipt.json": stray}))
        self.assertEqual((report.ok, report.code), (False, "governed-file-without-release"))
        report = self.verify(self.case.open(edit={"docs/release/other.json": stray}))
        self.assertEqual((report.ok, report.code), (False, "receipt-projection-mismatch"))
        report = self.verify(self.case.open(edit={"docs/release/" + "A" * 64 + ".receipt.json": stray}))
        self.assertFalse(report.ok)

    def test_an_unlisted_artifact_fails_even_with_a_valid_receipt(self):
        report = self.verify(self.case.open(edit={"docs/spec/surprise.md": b"# Surprise\n"}))
        self.assertEqual((report.ok, report.code), (False, "governed-file-without-release"))
        self.assertIn("docs/spec/surprise.md", [f.where for f in report.findings])

    def test_a_pull_request_that_touches_only_src_reports_no_governed_changes(self):
        n = self.case.open(only={"src/app.py": b"print('hello')\n", "tests/test_app.py": b"pass\n"})
        report = self.verify(n)
        self.assertEqual((report.ok, report.kind, report.findings), (True, "no-governed-changes", ()))

    def test_deleting_only_the_policy_pointer_fails_instead_of_reporting_no_governed_changes(self):
        n = self.case.open(only={POINTER: None})
        report = self.verify(n)
        self.assertEqual((report.ok, report.code), (False, "policy-pointer-mismatch"))

    def test_an_altered_pointer_fails_and_a_valid_change_by_an_approver_passes(self):
        wrong = f"format: 1\ntooling_repository: {TOOLING}\nenrollment_id: {'0' * 64}\n".encode()
        self.assertEqual(self.verify(self.case.open(only={POINTER: wrong})).code, "policy-pointer-mismatch")
        other_tooling = f"format: 1\ntooling_repository: evil/tooling\nenrollment_id: {self.enr.enrollment_id}\n".encode()
        self.assertEqual(self.verify(self.case.open(only={POINTER: other_tooling})).code, "policy-pointer-mismatch")
        extra_key = pointer_text(self.enr) + b"policy: loose\n"
        self.assertEqual(self.verify(self.case.open(only={POINTER: extra_key})).code, "policy-pointer-mismatch")
        valid = pointer_text(self.enr) + b"# reviewed\n"
        self.assertEqual(self.verify(self.case.open(only={POINTER: valid}, user=(555, "not-an-approver"))).code, "approver-not-authorized")
        self.assertTrue(self.verify(self.case.open(only={POINTER: valid}, user=FE.OWNER)).ok)

    def test_removed_handling_fails(self):
        plan = "docs/spec/plan.yaml"
        text = self.text(plan)
        lines = text.split("\n")
        keep, skip = [], False
        for line in lines:
            if line.startswith("  handling:"):
                skip = True
                continue
            if skip and line.startswith("    "):
                continue
            skip = False
            keep.append(line)
        stripped = "\n".join(keep)
        self.assertNotIn("handling:", stripped)
        report = self.verify(self.case.open(edit={plan: stripped.encode()}))
        self.assertEqual((report.ok, report.code), (False, "enrolled-project-missing-handling"))

    def test_staffing_fields_in_a_plan_fail(self):
        plan = "docs/spec/plan.yaml"
        text = self.text(plan)
        self.assertIn("\npeople:\n", text)
        report = self.verify(self.case.open(edit={plan: text.replace("\npeople:\n  - id:", "\npeople:\n  - name: Private Person\n    id:", 1).encode()}))
        self.assertFalse(report.ok)
        self.assertTrue({"schema-view-mismatch", "exception-not-permitted", "sha256-mismatch"} & set(codes(report)))

    def test_a_cited_obligation_that_the_bundle_does_not_hold_fails_the_released_plan(self):
        import re
        plan = "docs/spec/plan.yaml"
        text = self.text(plan)
        changed = re.sub(r'(sections: ")([0-9., ]+)', lambda m: m.group(1) + m.group(2) + ", 9.9", text, count=1)
        self.assertTrue(changed != text)
        report = self.verify(self.case.open(edit={plan: changed.encode()}))
        self.assertFalse(report.ok)
        self.assertIn("schema-view-mismatch", codes(report))

    def test_an_external_item_with_only_an_id_and_a_label_is_valid_in_the_released_plan(self):
        import re
        plan = "docs/spec/plan.yaml"
        text = re.sub(r'\n      note: "[^\n]*"', "", self.text(plan))
        self.assertTrue("note:" not in text.split("external:")[1].split("limits:")[0])
        report = self.verify(self.case.open(edit={plan: text.encode()}))
        self.assertNotIn("schema-view-mismatch", codes(report))

    def test_a_credential_in_a_governed_file_fails_and_no_exception_clears_it(self):
        report = self.verify(self.case.open(edit={self.spec: self.ex.files[self.spec][1] + b"\napi_key = abcdef0123456789\n"}))
        self.assertFalse(report.ok)
        self.assertIn("exception-not-permitted", codes(report))
        shown = " ".join(f.where for f in report.findings)
        self.assertNotIn("abcdef0123456789", shown)

    def test_a_bundle_that_does_not_match_its_sidecar_fails(self):
        md = "docs/context/wi-01.md"
        report = self.verify(self.case.open(edit={md: self.ex.files[md][1] + b"altered\n"}))
        self.assertEqual((report.ok, report.code), (False, "sha256-mismatch"))
        self.assertIn(md, [f.where for f in report.findings])

    def test_a_governed_removal_and_a_rename_are_unsupported(self):
        # the file must exist on the base to be removed
        self.r.set_file(FE.ENGINEERING_ID, self.spec, b"base version\n")
        n = self.case.open(edit={self.spec: None}, branch="removal")
        self.assertEqual(self.verify(n).code, "artifact-operation-unsupported")

        class Renaming(FE.FakeEvidenceReader):
            def pull_request_files(inner, repo_id, number):
                rows = super().pull_request_files(repo_id, number)
                return rows + [{"filename": "docs/spec/new-name.md", "status": "renamed", "sha": "0" * 40, "previous_filename": "docs/spec/old-name.md"}]
        renamer = Renaming()
        renamer.__dict__.update(self.r.__dict__)
        self.assertEqual(RE.verify_engineering(renamer, self.enr, self.case.open(branch="renamed")).code, "artifact-operation-unsupported")

    def test_a_link_or_a_submodule_at_a_governed_path_fails(self):
        for mode in ("120000", "160000"):
            report = self.verify(self.case.open(edit={self.spec: (mode, b"../../elsewhere")}))
            self.assertEqual((report.ok, report.code), (False, "unsafe-artifact-path"), mode)

    def test_a_governed_file_that_reached_the_base_without_a_release_fails_the_open_pull_request(self):
        n = self.case.open()
        self.assertTrue(self.verify(n).ok)
        self.r.set_file(FE.ENGINEERING_ID, "src/app.py", b"print('a change elsewhere')\n")
        self.assertTrue(self.verify(n).ok, "an unrelated change on the base is no reason to fail")
        self.r.set_file(FE.ENGINEERING_ID, "docs/spec/rogue.md", b"# Pushed straight to the default branch\n")
        report = self.verify(n)
        self.assertEqual((report.ok, report.code), (False, "governed-file-without-release"))
        self.assertIn("docs/spec/rogue.md", [f.where for f in report.findings])

    def test_a_pull_request_touching_a_governed_file_with_no_release_at_all_fails(self):
        report = self.verify(self.case.open(only={"docs/spec/orphan.md": b"# Orphan\n"}))
        self.assertEqual((report.ok, report.code), (False, "governed-file-without-release"))

    def test_the_report_names_paths_and_codes_but_no_file_content(self):
        text = self.ex.files[self.spec][1] + b"\nSecret roadmap sentence.\n"
        report = self.verify(self.case.open(edit={self.spec: text}))
        shown = json.dumps([list(f) for f in report.findings])
        self.assertNotIn("Secret roadmap sentence", shown)


class RequestOnlyTests(ExportedBase):
    """engineer_edits request-only is the default for an enrolled project."""

    def release_on_main(self):
        self.case.merge(self.case.open())

    def test_WP9_an_edit_to_decisions_recorded_without_a_receipt_fails(self):
        self.release_on_main()
        text = self.text(self.spec)
        self.assertIn("## Decisions recorded", text)
        edited = text.rstrip("\n") + "\n\n- 2027-02-01. Departed from the contract in pull request 12.\n"
        n = self.case.open(only={self.spec: edited.encode()})
        report = self.verify(n)
        self.assertEqual((report.ok, report.code), (False, "sha256-mismatch"))
        self.assertIn(self.spec, [f.where for f in report.findings])

    def test_an_unchanged_receipt_still_covers_an_unchanged_approved_artifact(self):
        self.release_on_main()
        n = self.case.open(only={"docs/spec/m1-submit-report/new.md": b"# New\n"})
        self.assertFalse(self.verify(n).ok)
        again = self.case.open(only={self.spec: self.ex.files[self.spec][1]}, branch="same-bytes")
        self.assertTrue(self.verify(again).ok, "an artifact with the approved bytes needs no change at all")


class EngineerEditsAllowedTests(ExportedBase):
    edits = {"docs/spec/**": "allowed"}

    def test_WP9_with_edits_allowed_an_append_to_decisions_recorded_passes_and_other_edits_fail(self):
        self.case.merge(self.case.open())
        text = self.text(self.spec)
        appended = text.rstrip("\n") + "\n\n- 2027-02-01. Departed from the contract in pull request 12.\n"
        report = self.verify(self.case.open(only={self.spec: appended.encode()}, branch="decisions"))
        self.assertTrue(report.ok, report.findings)
        elsewhere = appended.replace("## Outcome", "## Outcome\n\nA changed promise.", 1)
        self.assertNotEqual(elsewhere, appended)
        report = self.verify(self.case.open(only={self.spec: elsewhere.encode()}, branch="outcome"))
        self.assertEqual((report.ok, report.code), (False, "sha256-mismatch"))


class StateTests(ExportedBase):
    def published(self):
        """The export merged into the default branch, so its receipt is already published."""
        self.case.merge(self.case.open())

    def terminal_receipt(self):
        record = V.verify_request(self.rid, self.r, self.enr)
        state = V.replay_staging(self.r, self.enr).replay.requests[self.rid]
        return RS.project_receipt(record.request, record.manifest_bytes, state, record.approval)

    def test_G4_after_withdrawal_a_receipt_only_pull_request_passes_and_nothing_else_does(self):
        """[G4]"""
        self.published()
        self.case.withdraw()
        enr = self.case.enrollment()
        n = self.case.open(only={self.receipt_path: self.terminal_receipt()}, branch="state-only")
        report = RE.verify_engineering(self.r, enr, n)
        self.assertEqual((report.ok, report.kind), (True, "state-only"), report.findings)
        # a spec riding along is not covered: withdrawn content authorizes nothing
        n = self.case.open(only={self.receipt_path: self.terminal_receipt(), self.spec: self.ex.files[self.spec][1] + b"\nmore\n"}, branch="piggyback")
        report = RE.verify_engineering(self.r, enr, n)
        self.assertEqual((report.ok, report.code), (False, "withdrawn"))

    def test_G4_a_receipt_that_still_says_active_for_a_withdrawn_request_fails_with_the_state(self):
        """[G4]"""
        n = self.case.open()
        self.assertTrue(self.verify(n).ok)
        self.case.withdraw()
        report = RE.verify_engineering(self.r, self.case.enrollment(), n)
        self.assertEqual((report.ok, report.code), (False, "withdrawn"))

    def test_a_forged_terminal_receipt_fails_the_projection(self):
        self.published()
        self.case.withdraw()
        forged = RS.loads_strict(self.terminal_receipt())
        forged["event_id"] = "1" * 64
        n = self.case.open(only={self.receipt_path: RS.canonical_json(forged)}, branch="forged")
        report = RE.verify_engineering(self.r, self.case.enrollment(), n)
        self.assertEqual((report.ok, report.code), (False, "receipt-projection-mismatch"))

    def test_a_terminal_receipt_for_a_request_that_was_never_published_is_refused(self):
        self.case.withdraw()
        n = self.case.open(only={self.receipt_path: self.terminal_receipt()}, branch="never-published")
        report = RE.verify_engineering(self.r, self.case.enrollment(), n)
        self.assertEqual((report.ok, report.code), (False, "receipt-projection-mismatch"))

    def test_a_request_that_was_never_activated_authorizes_nothing(self):
        other = FE.make_candidate(self.case.world, supersedes=self.rid, tip=None)
        receipt = RS.project_receipt(other.request, other.manifest, RS.RequestState(other.rid, "active", other.event["event_id"], None, self.rid),
                                     RS.VerifiedApproval(other.rid, "github-review", True))
        n = self.case.open(only={f"docs/release/{other.rid}.receipt.json": receipt})
        self.assertEqual(self.verify_with(n).code, "approval-not-found")

    def verify_with(self, n):
        return RE.verify_engineering(self.r, self.case.enrollment(), n)


class Light:
    """A small enrolled release (one Markdown file) and its engineering pull request, for the scan tests."""

    def __init__(self, expires=None, world=None, text=b"# Notes\n", branch="export", files=None):
        self.world = world or FE.World()
        self.r = self.world.reader
        self.enr = self.world.enrollment()
        self.r.set_file(FE.ENGINEERING_ID, POINTER, pointer_text(self.enr))
        self.files = dict(files or {"docs/spec/notes.md": text})
        self.c = FE.make_candidate(self.world, files={f"repo/{p}": b for p, b in self.files.items()}, destinations=("engineering-repo",), expires=expires)
        self.rid = self.c.rid
        self.text = text
        self.branch = branch
        self.staging_pr = None

    def land(self, approve=True, merge=True):
        self.staging_pr = self.c.land(approve=approve, merge=merge)
        return self.staging_pr

    def receipt(self):
        state = RS.RequestState(self.rid, "active", self.c.event["event_id"], None, None)
        return RS.project_receipt(self.c.request, self.c.manifest, state, RS.VerifiedApproval(self.rid, "github-review", True))

    def open(self, **kw):
        files = dict(self.files, **{f"docs/release/{self.rid}.receipt.json": self.receipt()})
        return self.r.open_pr(FE.ENGINEERING_ID, self.branch, files, user=FE.OWNER, **kw)

    def approve(self):
        self.r.review(FE.STAGING_ID, self.staging_pr, *FE.OWNER)
        self.r.merge(FE.STAGING_ID, self.staging_pr)


class ScanTests(unittest.TestCase):
    def test_a_previously_failed_head_succeeds_after_genuine_approval_without_an_engineering_push(self):
        light = Light()
        light.land(approve=False, merge=False)
        n = light.open()
        report, pub = run_scan(light.r)
        self.assertEqual(check_of(light.r, pub, n)["conclusion"], "failure")
        head = light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"]
        light.approve()
        report, pub = run_scan(light.r, pub)
        self.assertEqual(light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"], head, "no engineering push happened")
        self.assertEqual(check_of(light.r, pub, n)["conclusion"], "success")

    def test_every_poll_moves_the_check_to_in_progress_even_for_a_head_with_a_result(self):
        light = Light()
        light.land()
        n = light.open()
        report, pub = run_scan(light.r)
        report, pub = run_scan(light.r, pub)
        starts = [c for c in pub.calls if c[0] == "start" and c[1] == FE.ENGINEERING_ID]
        self.assertEqual(len(starts), 2)
        self.assertEqual(check_of(light.r, pub, n)["conclusion"], "success")
        self.assertEqual(len(pub.runs[(FE.ENGINEERING_ID, light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"], V.ENGINEERING_CHECK)]), 1)

    def test_G4_a_success_becomes_a_failure_after_withdrawal(self):
        """[G4]"""
        light = Light()
        light.land()
        n = light.open()
        report, pub = run_scan(light.r)
        self.assertEqual(check_of(light.r, pub, n)["conclusion"], "success")
        import release_build as B2
        event = B2.withdrawal_event(light.rid, light.world.enrollment(), V.replay_staging(light.r, light.world.enrollment()).replay.tip, "error-found",
                                    created=light.r.tick(), nonce=B2.new_nonce())
        light.world.land(B2.state_branch_files(event), f"state/{event['event_id']}")
        report, pub = run_scan(light.r, pub)
        state = check_of(light.r, pub, n)
        self.assertEqual((state["conclusion"], state["title"]), ("failure", "carrydown: withdrawn"))

    def test_G4_a_success_becomes_a_failure_after_expiry(self):
        """[G4]"""
        soon = V.utc_text(V.clock() + 3600)
        light = Light(expires=soon)
        light.land()
        n = light.open()
        report, pub = run_scan(light.r)
        self.assertEqual(check_of(light.r, pub, n)["conclusion"], "success")
        with mock.patch.object(V, "clock", lambda: V.time.time() + 7200):
            report, pub = run_scan(light.r, pub)
        state = check_of(light.r, pub, n)
        self.assertEqual((state["conclusion"], state["title"]), ("failure", "carrydown: expired"))

    def test_a_success_becomes_a_failure_after_approver_removal_or_a_policy_update(self):
        for change in (lambda e: e.update(approvers=[{"id": 4242, "login": "someone-else"}]),
                       lambda e: e.update(offline_grace_days=3)):
            light = Light()
            light.land()
            n = light.open()
            report, pub = run_scan(light.r)
            self.assertEqual(check_of(light.r, pub, n)["conclusion"], "success")
            light.r.users[4242] = {"id": 4242, "login": "someone-else"}
            light.world.update_policy(change)
            report, pub = run_scan(light.r, pub)
            state = check_of(light.r, pub, n)
            self.assertEqual(state["conclusion"], "failure")
            self.assertIn(state["title"], ("carrydown: policy-revision-mismatch", "carrydown: approver-not-authorized"))

    def test_a_base_change_that_adds_an_unauthorized_governed_file_fails_a_previous_success(self):
        light = Light()
        light.land()
        n = light.open()
        report, pub = run_scan(light.r)
        self.assertEqual(check_of(light.r, pub, n)["conclusion"], "success")
        light.r.set_file(FE.ENGINEERING_ID, "docs/spec/rogue.md", b"# not released\n")
        report, pub = run_scan(light.r, pub)
        state = check_of(light.r, pub, n)
        self.assertEqual((state["conclusion"], state["title"]), ("failure", "carrydown: governed-file-without-release"))

    def test_a_read_error_replaces_the_observed_success_with_a_failed_check(self):
        light = Light()
        light.land()
        n = light.open()
        report, pub = run_scan(light.r)
        self.assertEqual(check_of(light.r, pub, n)["conclusion"], "success")
        light.r.fail("tree", FE.ENGINEERING_ID)
        report, pub = run_scan(light.r, pub)
        state = check_of(light.r, pub, n)
        self.assertEqual((state["conclusion"], state["title"]), ("failure", "carrydown: evidence-unavailable"))
        self.assertNotIn("success", [c["conclusion"] for c in report.checks])

    def test_a_scheduler_outage_is_a_limit_not_an_expiry(self):
        light = Light()
        light.land()
        n = light.open()
        report, pub = run_scan(light.r)
        before = dict(check_of(light.r, pub, n))
        # no scan runs now: the old success stays exactly as it was, which is the documented limit
        self.assertEqual(check_of(light.r, pub, n), before)
        self.assertEqual(before["conclusion"], "success")

    def test_a_listing_that_cannot_be_read_makes_the_scan_incomplete(self):
        light = Light()
        light.land()
        light.open()
        light.r.fail("pull_requests", FE.ENGINEERING_ID)
        report, pub = run_scan(light.r)
        self.assertFalse(report.complete)
        self.assertEqual(report.checks and [c for c in report.checks if c["kind"] == "engineering"], [])
        self.assertFalse(report.health_record()["complete"])

    def test_a_truncated_listing_is_a_refusal_and_never_a_clean_result(self):
        light = Light()
        light.land()
        n = light.open()
        light.r.truncate("pull_request_files")
        report, pub = run_scan(light.r)
        state = check_of(light.r, pub, n)
        self.assertEqual((state["conclusion"], state["title"]), ("failure", "carrydown: evidence-unavailable"))

    def test_G5_two_concurrent_scans_cannot_let_an_older_result_overwrite_a_newer_failure(self):
        """The older scan evaluates while the repository is healthy and is slow to post. A newer scan sees the
        withdrawal and posts a failure first. The older scan then must not replace it."""
        light = Light()
        light.land()
        n = light.open()
        head = light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"]
        pub = FE.FakeCheckPublisher()

        def newer_scan(repo_id, head_sha, name):
            if repo_id != FE.ENGINEERING_ID:
                return
            newer = pub.new_run(repo_id, head_sha, name)
            pub.finish(repo_id, head_sha, name, newer, "failure", "carrydown: withdrawn", "withdrawn")
        pub.before_finish = newer_scan
        report, pub = run_scan(light.r, pub)
        self.assertEqual(report.superseded, 1)
        self.assertEqual([c for c in report.checks if c["kind"] == "engineering"], [], "the discarded result is not reported as posted")
        state = check_of(light.r, pub, n)
        self.assertEqual((state["conclusion"], state["title"]), ("failure", "carrydown: withdrawn"))
        self.assertEqual(head, light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"])

    def test_inputs_that_change_during_verification_are_retried_once_then_fail(self):
        light = Light()
        light.land()
        n = light.open()
        moves = {"count": 0}
        real = light.r.branch_head

        def moving(repo_id, branch):
            if repo_id == FE.STAGING_ID:
                moves["count"] += 1
                light.r.set_file(FE.STAGING_ID, "noise.txt", b"%d" % moves["count"])      # the staging tip moves on every read
            return real(repo_id, branch)
        with mock.patch.object(light.r, "branch_head", moving):
            report, pub = run_scan(light.r)
        state = check_of(light.r, pub, n)
        self.assertEqual((state["conclusion"], state["title"]), ("failure", "carrydown: inputs-changed-during-verification"))

    def test_content_addressed_reads_are_remembered_for_one_scan_and_nothing_else(self):
        light = Light()
        light.land()
        light.open()
        before = len(light.r.calls)
        reads = S.ImmutableReads(light.r)
        head = light.r.branch_head(FE.ENGINEERING_ID, "main")
        reads.tree(FE.ENGINEERING_ID, head)
        reads.tree(FE.ENGINEERING_ID, head)
        reads.file_at(FE.ENGINEERING_ID, "main", POINTER)
        reads.file_at(FE.ENGINEERING_ID, "main", POINTER)
        names = [c[0] for c in light.r.calls[before:]]
        self.assertEqual(names.count("tree"), 1, "a tree at a full commit id is read once")
        self.assertEqual(names.count("file_at"), 2, "a file at a branch name is read every time")
        self.assertEqual(names.count("branch_head"), 1)

    def test_a_failure_to_post_makes_the_scan_incomplete_and_leaves_an_outstanding_check(self):
        light = Light()
        light.land()
        light.open()
        pub = FE.FakeCheckPublisher()
        pub.fail_finish = True
        report, pub = run_scan(light.r, pub)
        self.assertFalse(report.complete)
        self.assertEqual(report.outstanding, 1)

    def test_every_pull_request_of_both_repositories_is_checked_and_the_scan_is_complete(self):
        light = Light()
        light.land()
        n = light.open()
        other = FE.make_candidate(light.world, files={"repo/docs/spec/more.md": b"# More\n"}, destinations=("engineering-repo",),
                                  supersedes=light.rid)
        s = other.land(approve=False, merge=False)       # an open staging candidate, not yet reviewed
        report, pub = run_scan(light.r)
        self.assertTrue(report.complete, report.errors)
        kinds = sorted((c["kind"], c["conclusion"]) for c in report.checks)
        self.assertEqual(kinds, [("engineering", "success"), ("staging", "failure")])
        staging = check_of(light.r, pub, s, "staging")
        self.assertEqual(staging["title"], "carrydown: approval-not-found")
        self.assertIn("waiting for an authorized review", staging["summary"])
        self.assertNotIn("success", [r["conclusion"] for r in report.checks if r["kind"] == "staging"])

    def test_the_public_check_text_holds_identifiers_and_codes_only(self):
        light = Light()
        light.land()
        n = light.open(base_sha=None)
        report, pub = run_scan(light.r)
        state = check_of(light.r, pub, n)
        self.assertNotIn("Notes", state["summary"])
        self.assertNotIn("Notes", state["title"])
        self.assertTrue(report.records and "request_ids" in report.records[0])
        record = [r for r in report.records if r.get("kind") == "engineering"][0]
        for key in ("repository_id", "pull_request", "head_sha", "base_tip", "policy_commit_sha", "policy_sha256", "verifier_sha", "staging_tip", "evaluated_at"):
            self.assertIn(key, record)


class BundleTests(unittest.TestCase):
    def test_an_approved_bundle_whose_sidecar_does_not_match_its_markdown_still_fails(self):
        md = b"# Approved context for WI-99\n"
        side = RS.canonical_json({"bundle_format": 1, "work_item": "WI-99", "obligations": [], "conflicts": [], "shared_with": [],
                                  "downstream": {"code": True, "tests": True, "issues": False, "evidence": "synthetic-only"},
                                  "content_sha256": "0" * 64, "extensions": {}})
        light = Light(files={"docs/context/wi-99.md": md, "docs/context/wi-99.bundle.json": side})
        light.land()
        n = light.open()
        report = RE.verify_engineering(light.r, light.world.enrollment(), n)
        self.assertEqual((report.ok, report.code), (False, "sha256-mismatch"), report.findings)
        self.assertIn("docs/context/wi-99.md", [f.where for f in report.findings])
        good = RS.canonical_json(dict(RS.loads_strict(side), content_sha256=RS.sha256_bytes(md)))
        light = Light(files={"docs/context/wi-99.md": md, "docs/context/wi-99.bundle.json": good})
        light.land()
        self.assertTrue(RE.verify_engineering(light.r, light.world.enrollment(), light.open()).ok)


    def test_a_placeholder_bundle_of_a_restricted_item_is_accepted(self):
        md = b"# Approved context for WI-05, Restricted work\n\nBundle format 1. Sources: none.\n"
        side = RS.canonical_json({"bundle_format": 1, "work_item": "WI-05", "obligations": [], "conflicts": [], "shared_with": [],
                                  "downstream": {"code": False, "tests": False, "issues": False, "evidence": "synthetic-only"},
                                  "content_sha256": RS.sha256_bytes(md), "extensions": {}, "restricted_destination": True})
        light = Light(files={"docs/context/wi-05.md": md, "docs/context/wi-05.bundle.json": side})
        light.land()
        report = RE.verify_engineering(light.r, light.world.enrollment(), light.open())
        self.assertTrue(report.ok, report.findings)


class CaptureTests(unittest.TestCase):
    def test_a_policy_commit_that_is_no_longer_the_head_is_refused_even_when_the_file_is_unchanged(self):
        w = FE.World()
        tip = w.reader.branch_head(FE.TOOLING_ID, "main")
        data = w.reader.file_at(FE.TOOLING_ID, tip, "enrollment.yaml")
        self.assertEqual(len(V.capture_enrollments(w.reader, TOOLING, tip, data)), 1)
        w.reader.set_file(FE.TOOLING_ID, "README.md", b"an unrelated commit\n")
        try:
            V.capture_enrollments(w.reader, TOOLING, tip, data)
            code = "accepted"
        except RS.SchemaError as e:
            code = e.code
        self.assertEqual(code, "policy-revision-mismatch")


class G5CanaryTests(unittest.TestCase):
    def test_G5_a_pull_request_that_edits_the_checker_to_always_pass_still_fails_on_the_governed_file(self):
        """[G5] The edited checker would create a canary file if anything ran it. The verifier reads the pull
        request as data, so the canary is never created, and no process is started at all."""
        with tempfile.TemporaryDirectory() as tmp:
            canary = Path(tmp) / "canary.txt"
            checker = ("import sys\nfrom pathlib import Path\nPath(%r).write_text('ran')\nsys.exit(0)\n" % str(canary)).encode()
            light = Light()
            light.r.set_file(FE.ENGINEERING_ID, "tools/carrydown/check_specs.py", b"# the original checker\n")
            light.land()
            files = {"tools/carrydown/check_specs.py": checker, "docs/spec/unreleased.md": b"# A spec with no release\n"}
            n = light.r.open_pr(FE.ENGINEERING_ID, "evil", files, user=(555, "engineer"))

            def refuse(*a, **k):
                raise AssertionError("the verifier started a process")
            with mock.patch.object(subprocess, "run", refuse), mock.patch.object(subprocess, "Popen", refuse), \
                    mock.patch.object(os, "system", refuse), mock.patch.object(os, "execv", refuse):
                report, pub = run_scan(light.r)
            state = check_of(light.r, pub, n)
            self.assertEqual((state["conclusion"], state["title"]), ("failure", "carrydown: governed-file-without-release"))
            self.assertIn("docs/spec/unreleased.md", state["summary"])
            self.assertFalse(canary.exists(), "the edited checker must never run")
            self.assertEqual(os.listdir(tmp), [])


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.light = Light()
        self.w, self.r = self.light.world, self.light.r
        self.enr = self.w.enrollment()

    def candidate_check(self, number):
        return S.evaluate(self.r, self.w.enrollment(), "staging", number)

    def test_a_reviewed_candidate_passes_and_an_unreviewed_one_waits(self):
        n = self.light.land(approve=False, merge=False)
        waiting = self.candidate_check(n)
        self.assertEqual((waiting.conclusion, waiting.code), ("failure", "approval-not-found"))
        self.r.review(FE.STAGING_ID, n, *FE.OWNER)
        self.assertEqual(self.candidate_check(n).conclusion, "success")

    def test_a_review_by_an_account_that_is_not_an_approver_fails(self):
        n = self.light.land(approve=False, merge=False)
        self.r.review(FE.STAGING_ID, n, *FE.OUTSIDER)
        self.assertEqual(self.candidate_check(n).code, "approver-not-authorized")

    def test_candidate_edits_to_the_workflow_the_enrollment_an_old_event_or_a_previous_request_fail(self):
        light = self.light
        light.land()
        old_event = next(p for p in self.r.repos[FE.STAGING_ID]["commits"][self.r.repos[FE.STAGING_ID]["branches"]["main"]]["tree"] if p.startswith("events/"))
        old_request = f"requests/{light.rid}/approval-request.json"
        snapshot = next(p for p in self.r.repos[FE.STAGING_ID]["commits"][self.r.repos[FE.STAGING_ID]["branches"]["main"]]["tree"] if "/snapshot/" in p)
        for path in (".github/workflows/open-release-request.yml", "enrollment.yaml", old_event, old_request, snapshot):
            fresh = FE.make_candidate(self.w, supersedes=light.rid)
            files = dict(fresh.files())
            files[path] = b"edited by a candidate\n"
            n = self.w.land(files, fresh.branch, approve=False, merge=False)
            self.r.review(FE.STAGING_ID, n, *FE.OWNER)
            result = self.candidate_check(n)
            self.assertEqual(result.conclusion, "failure", path)
            self.assertIn(result.code, ("artifact-operation-unsupported", "unsafe-artifact-path"), path)
            self.r.close(FE.STAGING_ID, n)

    def test_G2_after_one_replacement_merges_a_concurrent_stale_predecessor_branch_cannot_pass(self):
        """[G2]"""
        light = self.light
        light.land()
        tip = V.replay_staging(self.r, self.w.enrollment()).replay.tip
        first = FE.make_candidate(self.w, files={"repo/docs/spec/a.md": b"# A\n"}, destinations=("engineering-repo",), supersedes=light.rid, tip=tip)
        second = FE.make_candidate(self.w, files={"repo/docs/spec/b.md": b"# B\n"}, destinations=("engineering-repo",), supersedes=light.rid, tip=tip)
        n1 = self.w.land(first.files(), first.branch, approve=False, merge=False)
        n2 = self.w.land(second.files(), second.branch, approve=False, merge=False)
        self.r.review(FE.STAGING_ID, n1, *FE.OWNER)
        self.r.review(FE.STAGING_ID, n2, *FE.OWNER)
        self.assertEqual(self.candidate_check(n1).conclusion, "success")
        self.assertEqual(self.candidate_check(n2).conclusion, "success")
        self.r.merge(FE.STAGING_ID, n1)
        stale = self.candidate_check(n2)
        self.assertEqual(stale.conclusion, "failure")
        self.assertIn(stale.code, ("state-history-invalid",))

    def test_the_staging_check_requires_the_staging_readers_to_be_verified(self):
        n = self.light.land(approve=False, merge=False)
        self.r.review(FE.STAGING_ID, n, *FE.OWNER)
        self.assertEqual(self.candidate_check(n).conclusion, "success")
        self.r.collaborators_by_repo[FE.STAGING_ID].append({"id": 999, "login": "outsider", "permission": "read"})
        result = self.candidate_check(n)
        self.assertEqual((result.conclusion, result.code), ("failure", "staging-access-not-verified"))

    def test_an_installed_workflow_that_differs_from_the_enrolled_digest_fails_the_check(self):
        n = self.light.land(approve=False, merge=False)
        self.r.review(FE.STAGING_ID, n, *FE.OWNER)
        self.r.set_file(FE.STAGING_ID, V.WORKFLOW_PATH, b"name: something else\n")
        result = self.candidate_check(n)
        self.assertEqual(result.conclusion, "failure")


if __name__ == "__main__":
    unittest.main()
