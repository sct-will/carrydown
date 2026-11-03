"""The publication preflight (work package 8, item 2), the visibility line and the removal of --allow-public.

publication_preflight is tested against the in-memory model of GitHub (tests/mock/fake_evidence.py): a
repository for repository readers on a public repository, a board that more accounts can read than the
repository, a changed project node id, a wrong repository id, readers that cannot be listed with and
without a current destination-readers attestation, and a public derivative at its exact public target.
Commands are tested against the local mock of the GitHub API (tests/mock/mockgh.py): the refusal comes
before any write, --preflight writes nothing, and --verify reports a change of visibility.
No token and no network are used.
"""
import copy
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
sys.path.insert(0, str(ROOT / "tests"))
import fake_evidence as FE  # noqa: E402
import github_project as GP  # noqa: E402
import github_repair as GR  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release_fixture as F  # noqa: E402
import release_sync as RSY  # noqa: E402
import release_verify as V  # noqa: E402
from test_publication import PubCase, writes  # noqa: E402

ENGINEERING = {"id": "engineering", "host": "github.com", "repository_id": 4200, "repository": "acme/expense-approvals"}
BOARD = {"id": "board", "host": "github.com", "repository_id": 4200, "owner_id": 4400, "project_id": "PVT_example"}
OUTSIDER_ID = FE.OUTSIDER[0]


def request(audience="repo-readers", targets=(ENGINEERING, BOARD)):
    return {"receipt_template": {"audience": audience, "targets": [dict(t) for t in targets]}}


class PreflightUnitTests(unittest.TestCase):
    def setUp(self):
        self.world = FE.World()
        self.reader = self.world.reader
        self.enrollment = self.world.enrollment()

    def preflight(self, req=None, policy=None, reader=None):
        return RSY.publication_preflight(None, None, policy or self.enrollment, req or request(), reader=reader or self.reader)

    def refused(self, code, **kw):
        with self.assertRaisesRegex(RSY.PublicationRefused, "") as raised:
            self.preflight(**kw)
        self.assertEqual(raised.exception.code, code, raised.exception.text)
        return raised.exception

    def test_an_approved_private_repository_and_a_board_whose_readers_are_repository_readers_pass(self):
        out = self.preflight()
        self.assertEqual(out.visibility, {"engineering": "private", "board": "private"})
        self.assertIn("visibility: acme/expense-approvals private (numeric id 4200)", out.lines)
        self.assertTrue(any(ln.startswith("visibility: board PVT_example private; 2 reader(s), all of them readers of the repository") for ln in out.lines), out.lines)

    def test_a_repository_readers_release_on_a_public_repository_is_refused(self):
        self.reader.repos[4200].update(private=False, visibility="public")
        self.refused("audience-visibility-mismatch")

    def test_a_public_release_and_restricted_sources_proceed_at_the_exact_public_target(self):
        self.reader.repos[4200].update(private=False, visibility="public")
        self.reader.projects["PVT_example"]["public"] = True
        out = self.preflight(request("public"))
        self.assertEqual(out.visibility, {"engineering": "public", "board": "public"})
        self.assertIn("visibility: acme/expense-approvals public (numeric id 4200), a public release", out.lines)
        # the identities are still the approved ones: another repository that took the name does not inherit the approval
        self.reader.repos[4200]["id"] = 4201
        self.reader.repos[4201] = self.reader.repos.pop(4200)
        with self.assertRaisesRegex(RSY.PublicationRefused, "") as raised:
            self.preflight(request("public"))
        self.assertIn(raised.exception.code, ("target-identity-mismatch", "destination-not-allowed"))

    def test_a_public_release_may_target_a_private_repository(self):
        self.assertEqual(self.preflight(request("public")).visibility["engineering"], "private")

    def test_a_private_board_with_an_extra_reader_is_refused_even_though_both_are_private(self):
        self.reader.projects["PVT_example"]["reader_ids"].append(5555)
        err = self.refused("audience-visibility-mismatch")
        self.assertIn("accounts that cannot read the repository", err.text)
        self.assertNotIn("5555", err.text)
        # and the same for a project that is not enrolled, where the preflight itself does the comparison
        local = V.local_policy({"repo_audience_approved": True}, "acme/expense-approvals")
        err = self.refused("audience-visibility-mismatch", policy=local)
        self.assertIn("1 account(s) that cannot read the repository", err.text)

    def test_a_public_board_is_refused_for_repository_readers(self):
        self.reader.projects["PVT_example"]["public"] = True
        self.refused("audience-visibility-mismatch")

    def test_a_changed_project_node_id_is_refused(self):
        other = dict(BOARD, project_id="PVT_other")
        # not in the enrollment's allowed targets
        self.refused("destination-not-allowed", req=request(targets=(ENGINEERING, other)))
        # and for a project that is not enrolled, a node id that does not exist is not the approved board
        local = V.local_policy({"repo_audience_approved": True}, "acme/expense-approvals")
        self.refused("target-identity-mismatch", req=request(targets=(ENGINEERING, other)), policy=local)
        self.reader.projects["PVT_example"]["id"] = "PVT_renumbered"
        self.refused("target-identity-mismatch")

    def test_a_board_not_linked_to_the_approved_repository_or_with_another_owner_is_refused(self):
        self.reader.projects["PVT_example"]["repository_ids"] = [9999]
        self.refused("target-identity-mismatch")
        self.reader.projects["PVT_example"]["repository_ids"] = [4200]
        self.reader.projects["PVT_example"]["owner_id"] = 1
        self.refused("target-identity-mismatch")

    def test_a_wrong_repository_id_is_refused(self):
        local = V.local_policy({"repo_audience_approved": True}, "acme/expense-approvals")
        wrong = dict(ENGINEERING, repository_id=7777)
        self.refused("target-identity-mismatch", req=request(targets=(wrong,)), policy=local)
        self.refused("destination-not-allowed", req=request(targets=(wrong, BOARD)))

    def attest(self, **changes):
        """Publish a destination-readers attestation that covers the board as it is now."""
        project = self.reader.projects["PVT_example"]
        people = [p["id"] for p in self.reader.collaborators_by_repo[4200]]
        subject = RSY.board_subject(BOARD, project["repository_ids"], people, project["public"])
        subject.update(changes.pop("subject", {}))
        att = {"component": "destination-readers", "by_id": FE.ADMIN[0], "at": V.utc_text(V.clock() - 3600), "expires_at": V.utc_text(V.clock() + 86400),
               "subject": subject, "note": "The board has the same readers as the repository"}
        att.update(changes)
        self.enrollment = self.world.update_policy(lambda entry: entry["attestations"].append(att))
        return att

    def test_readers_that_cannot_be_listed_need_a_current_scoped_attestation(self):
        self.reader.projects["PVT_example"]["reader_ids"] = None
        self.refused("destination-access-not-verified")
        self.attest()
        out = self.preflight()
        self.assertTrue(any("covered by a current destination-readers attestation" in ln for ln in out.lines), out.lines)

    def test_an_expired_or_unauthorized_attestation_covers_nothing(self):
        self.reader.projects["PVT_example"]["reader_ids"] = None
        self.attest(expires_at=V.utc_text(V.clock() - 60))
        self.refused("destination-access-not-verified")
        self.attest(by_id=OUTSIDER_ID, expires_at=V.utc_text(V.clock() + 86400))
        self.refused("destination-access-not-verified")

    def test_a_membership_or_link_change_invalidates_the_evidence(self):
        self.reader.projects["PVT_example"]["reader_ids"] = None
        self.attest()
        self.preflight()
        # a new account can read the repository: the attested reader set is no longer the current one
        self.reader.collaborators_by_repo[4200].append({"id": 4321, "login": "newcomer", "permission": "read"})
        self.refused("destination-access-not-verified")
        self.reader.collaborators_by_repo[4200].pop()
        self.preflight()
        # the board is linked to another repository as well
        self.reader.projects["PVT_example"]["repository_ids"] = [4200, 4300]
        self.refused("destination-access-not-verified")

    def test_a_board_whose_repository_readers_cannot_be_listed_is_not_verified_either(self):
        self.reader.fail("collaborators")
        self.refused("destination-access-not-verified")

    def test_a_project_that_is_not_enrolled_proceeds_and_says_the_readers_were_not_listed(self):
        local = V.local_policy({"repo_audience_approved": True}, "acme/expense-approvals")
        self.reader.projects["PVT_example"]["reader_ids"] = None
        out = self.preflight(policy=local)
        self.assertTrue(any("readers not listed (the board's readers cannot be listed)" in ln and "no administrator attestation" in ln for ln in out.lines), out.lines)
        # an extra reader is still refused, enrolled or not
        self.reader.projects["PVT_example"]["reader_ids"] = [5555]
        self.refused("audience-visibility-mismatch", policy=local)

    def test_the_preflight_only_reads(self):
        self.preflight()
        self.assertTrue(self.reader.calls)
        self.assertFalse([c for c in self.reader.calls if c[0].startswith(("set", "put", "post", "write", "merge", "commit"))], self.reader.calls)

    def test_an_unreadable_destination_is_evidence_unavailable(self):
        self.reader.fail("repository")
        self.refused("evidence-unavailable")


class RelationshipTests(unittest.TestCase):
    def payloads(self):
        def row(kind, key, **rel):
            return (kind, key), ("payloads/x.json", {"relationships": rel}, "0" * 64)
        return dict([row("epic", "EPIC", parent=None, children=["M1"]), row("subepic", "M1", parent="EPIC", children=["WI-01", "WI-02"]),
                     row("issue", "WI-01", parent="M1", depends_on=[]), row("issue", "WI-02", parent="M1", depends_on=["WI-01"])])

    def test_relationships_inside_the_release_pass_and_an_epic_that_exists_already_is_allowed(self):
        payloads = self.payloads()
        self.assertEqual(RSY.relationship_problems(payloads), [])
        del payloads[("epic", "EPIC")]
        self.assertEqual(RSY.relationship_problems(payloads), [])

    def test_a_relationship_that_points_outside_the_release_is_a_problem(self):
        payloads = self.payloads()
        payloads[("issue", "WI-02")][1]["relationships"]["depends_on"] = ["WI-09"]
        payloads[("issue", "WI-01")][1]["relationships"]["parent"] = "M7"
        problems = RSY.relationship_problems(payloads)
        self.assertEqual(problems, ["issue WI-01 names the parent M7, which is not in this release",
                                    "issue WI-02 names WI-09 in depends_on, which is not in this release"])


class VisibilityReportTests(unittest.TestCase):
    def test_a_change_is_reported_and_an_unchanged_value_is_not(self):
        lines, changed = RSY.visibility_report({"engineering": "private"}, {"engineering": "private"})
        self.assertFalse(changed)
        self.assertIn("unchanged since publication", lines[0])
        lines, changed = RSY.visibility_report({"engineering": "public"}, {"engineering": "private"})
        self.assertTrue(changed)
        self.assertIn("CHANGED since publication: was public, now private", lines[0])
        lines, changed = RSY.visibility_report({}, {"engineering": "private"})
        self.assertFalse(changed)
        self.assertIn("no earlier record", lines[0])


class PreflightCommandTests(PubCase):
    """The publishing commands against the local mock of GitHub."""

    def test_preflight_alone_prints_the_visibility_line_and_writes_nothing(self):
        self.released()
        code, out, err = self.sync("--preflight")
        self.assertEqual(code, 0, out + err)
        self.assertIn("PREFLIGHT (reads only; nothing will be written)", out)
        self.assertIn("visibility: sct-will/carrydown-sample private (numeric id 4200)", out)
        self.assertIn("preflight passed", out)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_dry_run_prints_one_visibility_line_for_each_target(self):
        self.released()
        code, out, err = self.sync()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len([ln for ln in out.splitlines() if ln.startswith("visibility:")]), 2, out)

    def test_a_public_repository_is_refused_by_every_publisher_before_any_write(self):
        self.released()
        mockgh.S.private = False
        for runner, args in ((self.sync, ("--apply",)), (self.sync, ("--preflight",)), (self.board_run, ("--apply",)), (self.board_run, ())):
            with self.subTest(args=args):
                code, out, err = runner(*args)
                self.assertEqual(code, 1)
                self.assertIn("audience-visibility-mismatch", out + err)
        code, out, err = F.run(GR.run, ["--root", str(self.root), "--before", str(self.root / "docs/spec/plan.yaml"), "--apply"])
        self.assertEqual(code, 1)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_board_with_another_node_id_or_a_wrong_link_is_refused_before_a_write(self):
        self.released()
        old = self.board["id"]
        self.board["id"] = "PVT_renumbered"
        code, out, err = self.board_run("--apply")
        self.assertEqual(code, 1)
        self.assertIn("target-identity-mismatch", out + err)
        self.board["id"] = old
        self.board["repo_ids"] = [9999]
        code, out, err = self.board_run("--apply")
        self.assertEqual(code, 1)
        self.assertIn("target-identity-mismatch", out + err)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_public_derivative_at_its_exact_approved_public_target_succeeds(self):
        self.project()
        self.assertEqual(self.yp.prepare("--audience", "public")[0], 0)
        self.assertEqual(self.yp.approve()[0], 0)
        self.assertEqual(self.yp.export()[0], 0)
        mockgh.S.private = False
        self.board["public"] = True
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("visibility: sct-will/carrydown-sample public (numeric id 4200), a public release", out)
        self.assertEqual(len(mockgh.S.issues), 15)

    def test_verify_reports_a_change_of_visibility_since_the_last_apply(self):
        self.project()
        self.assertEqual(self.yp.prepare("--audience", "public")[0], 0)
        self.assertEqual(self.yp.approve()[0], 0)
        self.assertEqual(self.yp.export()[0], 0)
        mockgh.S.private = False
        self.board["public"] = True
        self.assertEqual(self.sync("--apply")[0], 0)
        journal = json.loads((self.ws / "publication" / f"{self.yp.request_id}.journal.json").read_text(encoding="utf-8"))
        self.assertEqual(journal["visibility"]["engineering"], "public")
        code, out, err = self.sync("--verify")
        self.assertEqual(code, 0, out + err)
        self.assertIn("visibility of engineering: public (unchanged since publication)", out)
        mockgh.S.private = True
        self.board["public"] = False
        code, out, err = self.sync("--verify")
        self.assertEqual(code, 1)
        self.assertIn("visibility of engineering CHANGED since publication: was public, now private", out)

    def test_the_issue_inventory_of_a_release_says_what_the_active_release_published(self):
        self.released()
        code, out, err = self.sync("--inventory")
        self.assertEqual(code, 0, out + err)
        self.assertIn("active request: " + self.yp.request_id, out)
        self.assertIn("0 managed issue(s) found, 14 missing", out)
        self.assertEqual(self.sync("--apply")[0], 0)
        code, out, err = self.sync("--inventory")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(out.count("matches what the active release published"), 15, out)
        self.assertRegex(out, r"15 managed issue\(s\) found, 0 missing; 15 pristine; 0 with text outside the managed region\.")
        # a person edits the managed region of one issue and adds a note below another
        edited = self.issue_by_key("WI-03")
        edited["body"] = edited["body"].replace("Target completion on or before", "Target completion, changed by hand, on or before", 1)
        noted = self.issue_by_key("WI-04")
        noted["body"] = noted["body"] + "\n\nA note from a person."
        mark = len(mockgh.S.log)
        code, out, err = self.sync("--inventory")
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, r"WI-03 #\d+: body was edited or is older than the generator; no text outside the managed region; differs from what the active release published;")
        self.assertRegex(out, r"WI-04 #\d+: body was edited or is older than the generator; unmanaged text present;|WI-04 #\d+: body is pristine; unmanaged text present;")
        self.assertIn("replacing the region does not remove it", out)
        self.assertNotIn("A note from a person.", out)
        self.assertEqual([m for m, p in mockgh.S.log[mark:] if m != "GET" and p != "/graphql"], [])

    def test_allow_public_no_longer_exists(self):
        self.released()
        for runner in (self.sync, self.board_run):
            code, out, err = runner("--allow-public")
            self.assertEqual(code, 2)
            self.assertIn("unrecognized arguments: --allow-public", out + err)

    def test_publishing_reads_no_projection(self):
        self.released()
        import release_payloads as RP
        from unittest import mock
        with mock.patch.object(RP, "load_projections", side_effect=AssertionError("publication read a projection")):
            code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)


class LegacyVisibilityTests(unittest.TestCase):
    """A project with no release policy has no approved audience: a public repository is reported, not refused."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.url = mockgh.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_a_legacy_project_on_a_public_repository_is_not_asked_anything_new(self):
        import contextlib
        import os
        import shutil
        import tempfile
        import time
        from unittest import mock
        import github_client as G
        with tempfile.TemporaryDirectory(prefix="carrydown-legacy-vis-") as tmp:
            root = Path(tmp) / "legacy"
            shutil.copytree(ROOT / "sample/expense-approvals", root)
            F.strip_handling(root)
            mockgh.S.__init__()
            mockgh.S.repos.add("sct-will/carrydown-sample")
            mockgh.S.private = False
            env = {"CARRYDOWN_GITHUB_TOKEN": "ghp_" + "Z" * 36, "HOME": tmp, "USERPROFILE": tmp}
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.dict(os.environ, env))
                stack.enter_context(mock.patch.object(time, "sleep", lambda s: None))
                stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None)))
                code, out, err = F.run(GS.run, ["--root", str(root), "--repo", "sct-will/carrydown-sample", "--skip-check", "--apply", "--create-epic"])
                self.assertEqual(code, 0, out + err)
                self.assertIn("visibility: sct-will/carrydown-sample public. This project has no release policy, so no audience was checked", out)
                self.assertNotIn("--allow-public", out)
                code, out, err = F.run(GS.run, ["--root", str(root), "--repo", "sct-will/carrydown-sample", "--skip-check", "--preflight"])
                self.assertEqual(code, 0, out + err)
                self.assertIn("no approved audience to compare with", out)
                code, out, err = F.run(GS.run, ["--root", str(root), "--repo", "sct-will/carrydown-sample", "--skip-check", "--verify", "--create-epic"])
                self.assertEqual(code, 0, out + err)
                self.assertIn("visibility: public (unchanged since the last apply)", out)
                mockgh.S.private = True
                code, out, err = F.run(GS.run, ["--root", str(root), "--repo", "sct-will/carrydown-sample", "--skip-check", "--verify", "--create-epic"])
                self.assertEqual(code, 1)
                self.assertIn("visibility CHANGED since the last apply: was public, now private", out)


if __name__ == "__main__":
    unittest.main()
