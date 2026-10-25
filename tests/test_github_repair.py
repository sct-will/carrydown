"""Exercise the isolated metadata repair path against the local GitHub mock."""
import contextlib
import copy
import io
import os
import sys
import tempfile
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
        self.root = ROOT / "sample/expense-approvals"
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


if __name__ == "__main__":
    unittest.main()
