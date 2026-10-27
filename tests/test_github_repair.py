"""Exercise the isolated metadata repair path against the local GitHub mock."""
import contextlib
import copy
import io
import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests/mock"))
import carrydown_lib as L
import github_client as G
import github_repair as R
import github_sync as S
import github_project as P
import mockgh


class RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.url = mockgh.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-metadata-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        shutil.copytree(ROOT / "sample/expense-approvals", self.root)
        self.before, problems = L.load_plan(self.root / "docs/spec/plan.yaml", self.root)
        self.assertFalse(problems)
        self.before["people"][0]["github"] = "old-owner"
        self.plan = copy.deepcopy(self.before)
        mockgh.S = mockgh.State()
        self.m = mockgh.S
        self.gh = G.GitHub("test-credential", api=self.url, pause=0)
        self.m.labels = [{"name": name} for name in ("expense-approvals", "sub-epic", "workflow", "experience")]
        self.objects = {}
        epic = self.m.add_issue(self.before["project"]["epic_title"], S.marker("EPIC"), ["expense-approvals"])
        self.objects["EPIC"] = epic
        for key, (title, item, parent) in R.entries(self.before).items():
            labels = ["expense-approvals", item["track"] if item else "sub-epic"]
            issue = self.m.add_issue(title, "A human note stays here.\n\n" + S.marker(key), labels)
            issue["assignees"] = [{"login": R.login(self.before, item)}] if item and R.login(self.before, item) else []
            self.objects[key] = issue
            desired_parent = self.objects[parent or "EPIC"]["number"]
            self.m.subs.setdefault(desired_parent, []).append(issue["number"])

    def repair(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return R.repair(self.gh, self.before, self.plan, self.root, "o", "r", **kwargs)

    def writes(self):
        return [(method, path) for method, path in self.m.log if method != "GET"]

    def test_dry_run_and_verify_never_write(self):
        self.plan["people"][0]["github"] = "new-owner"
        self.assertEqual(self.repair(), 0)
        self.assertEqual(self.repair(verify=True), 1)
        self.assertEqual(self.writes(), [])

    def test_repair_preserves_human_content_and_unrelated_metadata(self):
        self.plan["people"][0]["github"] = "new-owner"
        issue = self.objects["WI-03"]
        issue["labels"].append({"name": "security-review"})
        issue["assignees"].append({"login": "reviewer"})
        issue["state"] = "closed"
        self.m.add_comment(issue["number"], "Evidence recorded by a person.")
        number, body = issue["number"], issue["body"]
        self.assertEqual(self.repair(apply=True), 0)
        self.assertEqual(issue["number"], number)
        self.assertEqual(issue["body"], body)
        self.assertEqual(issue["state"], "closed")
        self.assertEqual({a["login"] for a in issue["assignees"]}, {"new-owner", "reviewer"})
        self.assertIn({"name": "security-review"}, issue["labels"])
        self.assertEqual(self.m.comments[number][0]["body"], "Evidence recorded by a person.")
        self.assertEqual(self.repair(verify=True), 0)
        self.m.log.clear()
        self.assertEqual(self.repair(apply=True), 0)
        self.assertEqual(self.writes(), [])

    def test_track_title_and_parent_repairs_keep_the_same_issue(self):
        item = next(i for i in self.plan["items"] if i["id"] == 3)
        item["track"], item["owner"], item["milestone"] = "experience", "idris", 3
        item["label"] = "Routing and approval contract"
        issue = self.objects["WI-03"]
        number, body = issue["number"], issue["body"]
        self.assertEqual(self.repair(apply=True), 0)
        self.assertEqual(issue["number"], number)
        self.assertEqual(issue["body"], body)
        self.assertEqual(issue["title"], "WI-03 Routing and approval contract")
        self.assertEqual({l["name"] for l in issue["labels"]}, {"expense-approvals", "experience"})
        self.assertNotIn(number, self.m.subs[self.objects["M2"]["number"]])
        self.assertIn(number, self.m.subs[self.objects["M3"]["number"]])
        self.assertEqual(self.repair(verify=True), 0)
        self.assertFalse(any(method == "DELETE" for method, _ in self.m.log))

    def test_human_title_conflict_blocks_all_writes(self):
        self.objects["WI-03"]["title"] = "A title the owner wrote"
        self.plan["people"][0]["github"] = "new-owner"
        self.assertEqual(self.repair(apply=True), 1)
        self.assertEqual(self.writes(), [])

    def test_unrelated_parent_blocks_all_writes(self):
        child = self.objects["WI-03"]["number"]
        self.m.subs[self.objects["M2"]["number"]].remove(child)
        outside = self.m.add_issue("Unrelated project", "", [])
        self.m.subs[outside["number"]] = [child]
        self.assertEqual(self.repair(apply=True), 1)
        self.assertEqual(self.writes(), [])

    def test_missing_or_ambiguous_marker_is_not_adopted(self):
        self.objects["WI-03"]["body"] = "Human text without a marker"
        self.assertEqual(self.repair(apply=True), 1)
        self.assertEqual(self.writes(), [])
        self.objects["WI-03"]["body"] = S.marker("WI-03")
        self.m.add_issue("Duplicate marker", S.marker("WI-03"), ["expense-approvals"])
        self.assertEqual(self.repair(apply=True), 1)
        self.assertEqual(self.writes(), [])

    def test_retired_item_is_reported_without_deletion(self):
        self.plan["items"] = [i for i in self.plan["items"] if i["id"] != 3]
        self.assertEqual(self.repair(apply=True), 1)
        self.assertEqual(self.writes(), [])

    def test_partial_failure_can_be_recovered_without_duplicates(self):
        self.plan["people"][0]["github"] = "new-owner"
        self.m.fail[("PATCH", r"/repos/o/r/issues/\d+")] = [None, "502-after"]
        with self.assertRaisesRegex(G.GitHubError, "502"):
            self.repair(apply=True)
        count = len(self.m.issues)
        self.assertEqual(self.repair(apply=True), 0)
        self.assertEqual(len(self.m.issues), count)
        self.assertEqual(self.repair(verify=True), 0)

    def test_public_apply_guard_prevents_writes(self):
        self.m.private = False
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "before.yaml"
            before.write_text((self.root / "docs/spec/plan.yaml").read_text())
            original_init = G.GitHub.__init__
            def init(obj, token, **kwargs):
                original_init(obj, token, api=self.url, pause=0)
            with patch.object(G, "read_token", return_value="test-credential"), patch.object(G.GitHub, "__init__", init):
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(SystemExit, "^1$") as raised:
                    R.main(["--root", str(self.root), "--before", str(before), "--repo", "o/r", "--apply"])
            self.assertEqual(raised.exception.code, 1)
        self.assertEqual(self.writes(), [])


class PublicationRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.url = mockgh.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-publication-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        shutil.copytree(ROOT / "sample/expense-approvals", self.root)
        self.plan, _ = L.load_plan(self.root / "docs/spec/plan.yaml", self.root)
        mockgh.S = mockgh.State()
        self.m = mockgh.S
        self.gh = G.GitHub("test-credential", api=self.url, pause=0)
        self.m.labels = [{"name": name} for name in ("expense-approvals", "sub-epic", "workflow", "experience")]
        self.objects = {}
        for ms in self.plan["milestones"]:
            key = f"M{ms['number']}"
            self.objects[key] = self.m.add_issue(S.subepic_title(self.plan, ms), S.build_subepic_body(self.plan, self.root, ms), ["expense-approvals", "sub-epic"])
        for item in self.plan["items"]:
            key = L.tag(self.plan, item["id"])
            self.objects[key] = self.m.add_issue(S.item_title(self.plan, item), S.build_item_body(self.plan, self.root, item), ["expense-approvals", item["track"]])
            self.m.subs.setdefault(self.objects[f"M{item['milestone']}"]["number"], []).append(self.objects[key]["number"])
        numbers = {key: issue["number"] for key, issue in self.objects.items()}
        for ms in self.plan["milestones"]:
            self.objects[f"M{ms['number']}"]["body"] = S.build_subepic_body(self.plan, self.root, ms, numbers)
        for item in self.plan["items"]:
            self.objects[L.tag(self.plan, item["id"])]["body"] = S.build_item_body(self.plan, self.root, item, numbers)

    def sync(self, apply=False, selections=None):
        return S.Sync(self.plan, self.root, self.gh, "o", "r", apply, selections)

    def test_duplicate_identity_requires_decision_then_persists_and_neutralizes(self):
        issue = self.objects["WI-01"]
        duplicate = self.m.add_issue(issue["title"], issue["body"], ["expense-approvals", "workflow"])
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(G.GitHubError, "ambiguous issue identity"):
            self.sync().find("WI-01", issue["title"])
        preview = self.sync(selections={"WI-01": issue["number"]})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(preview.find("WI-01", issue["title"])["id"], issue["id"])
        self.assertIn(S.marker("WI-01"), duplicate["body"])
        self.assertFalse(preview.mapping_path.exists())
        applied = self.sync(True, {"WI-01": issue["number"]})
        with contextlib.redirect_stdout(io.StringIO()):
            chosen = applied.find("WI-01", issue["title"])
            applied.remember("WI-01", chosen)
        self.assertNotIn(S.marker("WI-01"), duplicate["body"])
        self.assertEqual(duplicate["state"], "open")
        self.assertTrue(applied.mapping_path.exists())
        self.assertEqual(self.sync().find("WI-01", issue["title"])["id"], issue["id"])

    def test_verified_mapping_wins_over_duplicate_and_missing_labels(self):
        issue = self.objects["WI-01"]
        sync = self.sync(True)
        sync.remember("WI-01", issue)
        issue["labels"] = []
        duplicate = self.m.add_issue(issue["title"], issue["body"], ["expense-approvals"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.sync().find("WI-01", issue["title"])["id"], issue["id"])
        self.assertIn(S.marker("WI-01"), duplicate["body"])

    def test_one_candidate_with_complete_managed_metadata_is_canonical(self):
        issue = self.objects["WI-01"]
        self.m.add_issue(issue["title"], issue["body"], ["expense-approvals", "experience"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.sync().find("WI-01", issue["title"])["id"], issue["id"])

    def test_one_issue_cannot_silently_represent_two_work_items(self):
        issue = self.objects["WI-01"]
        issue["body"] += S.marker("WI-02")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(G.GitHubError, "several plan identities"):
            self.sync().find("WI-01", issue["title"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.sync(True, {"WI-01": issue["number"]}).find("WI-01", issue["title"])
        self.assertIn(S.marker("WI-01"), issue["body"])
        self.assertNotIn(S.marker("WI-02"), issue["body"])

    def test_reconcile_preview_apply_verify_and_rerun(self):
        issue = self.objects["WI-03"]
        issue["title"] = "Drifted title"
        issue["body"] = "A human prefix.\n" + issue["body"].replace("### Acceptance criteria", "### Drifted criteria") + "\nHuman suffix. WI-01 is mentioned without a managed link.\n"
        issue["labels"] = [{"name": "unrelated"}]
        issue["assignees"] = [{"login": "reviewer"}]
        issue["state"] = "closed"
        self.plan["people"][0]["github"] = "planned-owner"
        self.m.add_comment(issue["number"], "Human evidence.")
        before = copy.deepcopy(issue)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(S.reconcile(self.sync(), self.plan, self.root, True), 0)
        self.assertEqual(issue, before)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(S.verify(self.sync(), self.plan, self.root, True), 1)
            self.assertEqual(S.reconcile(self.sync(True), self.plan, self.root, True), 0)
        self.assertIn("A human prefix.", issue["body"])
        self.assertIn("Human suffix.", issue["body"])
        self.assertIn({"name": "unrelated"}, issue["labels"])
        self.assertIn({"login": "reviewer"}, issue["assignees"])
        self.assertEqual(issue["state"], "closed")
        self.assertEqual(self.m.comments[issue["number"]][0]["body"], "Human evidence.")
        self.m.log.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(S.reconcile(self.sync(True), self.plan, self.root, True), 0)
        self.assertFalse([method for method, _ in self.m.log if method != "GET"])

    def test_managed_body_drift_failure_reports_expected_actual(self):
        issue = self.objects["WI-01"]
        issue["body"] = issue["body"].replace("npm test", "wrong command")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(S.verify(self.sync(), self.plan, self.root, True), 1)
        self.assertIn(f"WI-01 #{issue['number']}", output.getvalue())
        self.assertIn("expected", output.getvalue())
        self.assertIn("actual", output.getvalue())

    def test_board_partial_field_failure_and_resume_only_remaining_drift(self):
        original = self.gh.graphql
        failed = []
        def fail_one(query, variables=None):
            if "updateProjectV2ItemFieldValue(" in query and not failed:
                failed.append(copy.deepcopy(variables))
                raise G.GitHubError("permission denied", 403, "forbidden")
            return original(query, variables)
        args = ["--root", str(self.root), "--repo", "o/r", "--apply"]
        out = io.StringIO()
        with patch.object(G, "read_token", return_value="test-credential"), patch.object(G, "GitHub", return_value=self.gh), patch.object(self.gh, "graphql", side_effect=fail_one), patch.object(P.time, "sleep"), contextlib.redirect_stdout(out):
            self.assertEqual(P.run(args), 1)
        self.assertTrue(failed)
        self.assertIn("intended", out.getvalue())
        self.assertIn("permission denied", out.getvalue())
        self.assertIn("verification FAILED", out.getvalue())
        before = len(self.m.gql)
        with patch.object(G, "read_token", return_value="test-credential"), patch.object(G, "GitHub", return_value=self.gh), patch.object(P.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(P.run(args), 0)
        writes = [op for op in self.m.gql[before:] if op in mockgh.MUTATIONS]
        self.assertEqual(writes, ["updateProjectV2ItemFieldValue"])

    def test_board_retry_transient_field_assignment_then_verify(self):
        original = self.gh.graphql
        failures = []
        def fail_twice(query, variables=None):
            if "updateProjectV2ItemFieldValue(" in query and len(failures) < 2:
                failures.append(variables)
                raise G.GitHubError("temporary server failure", 503, "server")
            return original(query, variables)
        args = ["--root", str(self.root), "--repo", "o/r", "--apply"]
        with patch.object(G, "read_token", return_value="test-credential"), patch.object(G, "GitHub", return_value=self.gh), patch.object(self.gh, "graphql", side_effect=fail_twice), patch.object(P.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(P.run(args), 0)
        self.assertEqual(len(failures), 2)

    def test_board_verifies_visible_fields_after_mutation_failure(self):
        original = self.gh.graphql
        def fail_views(query, variables=None):
            if "updateProjectV2View(" in query and "configuration" in query:
                raise G.GitHubError("permission denied", 403, "forbidden")
            return original(query, variables)
        args = ["--root", str(self.root), "--repo", "o/r", "--apply"]
        out = io.StringIO()
        with patch.object(G, "read_token", return_value="test-credential"), patch.object(G, "GitHub", return_value=self.gh), patch.object(self.gh, "graphql", side_effect=fail_views), patch.object(P.time, "sleep"), contextlib.redirect_stdout(out):
            self.assertEqual(P.run(args), 1)
        self.assertIn("visible fields", out.getvalue())
        self.assertIn("verification FAILED", out.getvalue())

    def test_board_dry_run_previews_exact_field_drift_without_writes(self):
        args = ["--root", str(self.root), "--repo", "o/r"]
        with patch.object(G, "read_token", return_value="test-credential"), patch.object(G, "GitHub", return_value=self.gh), patch.object(P.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(P.run(args + ["--apply"]), 0)
        project = self.m.projects[0]
        fid = next(f["id"] for f in project["fields"] if f["name"] == "Complete by")
        project["items"][0]["values"][fid] = {"date": "2020-01-01"}
        before = len(self.m.gql)
        out = io.StringIO()
        with patch.object(G, "read_token", return_value="test-credential"), patch.object(G, "GitHub", return_value=self.gh), patch.object(P.time, "sleep"), contextlib.redirect_stdout(out):
            self.assertEqual(P.run(args), 0)
        self.assertIn("would set", out.getvalue())
        self.assertIn("actual '2020-01-01'", out.getvalue())
        self.assertFalse([op for op in self.m.gql[before:] if op in mockgh.MUTATIONS])


if __name__ == "__main__":
    unittest.main()
