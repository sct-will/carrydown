"""Tests for publishing an approved release to GitHub: payloads, substitutions and the journal
(github_sync.py, github_project.py, github_repair.py, release_sync.py, release_payloads.py).

The GitHub API is the loopback mock of tests/mock/mockgh.py. No token and no network are used. Tests
tagged [G1], [G4] and [G6] are negative tests of the specification (Part G) that WP11 collects.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import github_client as G  # noqa: E402
import github_project as GP  # noqa: E402
import github_repair as GR  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release as R  # noqa: E402
import release_build as B  # noqa: E402
import release_fixture as F  # noqa: E402
import release_gate as RG  # noqa: E402
import release_github as RGH  # noqa: E402
import release_payloads as RP  # noqa: E402
import release_schema as RS  # noqa: E402
import release_sync as RSY  # noqa: E402
import release_verify as V  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
REPO = "sct-will/carrydown-sample"
GOLDEN_BODIES = "11e4320d8460658ccbf26787509e3812705a00c318b4f930d47cd4b2f933836c"


def writes(log):
    """The mock requests that changed something: REST writes, and GraphQL mutations (a GraphQL query is a read)."""
    return [(m, p) for m, p in log if m != "GET" and p != "/graphql"] + [("GRAPHQL", op) for op in mockgh.S.gql if op in mockgh.MUTATIONS]


class PubCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-publication-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        mockgh.S.__init__()
        mockgh.S.repos.add(REPO)
        mockgh.S.repo_ids = {REPO: 4200}
        self.board = mockgh.add_project("Expense approvals plan")
        self.server, self.url = mockgh.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.env = {"CARRYDOWN_GITHUB_TOKEN": "ghp_" + "Z" * 36, "HOME": str(self.base), "USERPROFILE": str(self.base)}
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(os.environ, self.env))
        self.stack.enter_context(mock.patch.object(time, "sleep", lambda s: None))
        self.stack.enter_context(mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"))
        self.stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None)))

    def project(self, **kw):
        self.yp = F.YesProject(self.base / "yes", board=True, board_project_id=self.board["id"], **kw)
        self.root, self.ws = self.yp.root, self.yp.workspace
        return self.yp

    def released(self, **kw):
        self.project(**kw)
        return self.yp.release()

    def sync(self, *args):
        return F.run(GS.run, ["--root", str(self.root), "--skip-check"] + list(args))

    def board_run(self, *args):
        return F.run(GP.run, ["--root", str(self.root)] + list(args))

    def issue_by_key(self, key):
        return next(i for i in mockgh.S.issues if f"<!-- carrydown:{key} -->" in (i.get("body") or ""))


class PayloadTests(unittest.TestCase):
    def test_the_sample_issue_bodies_are_byte_for_byte_what_they_were(self):
        plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        h = hashlib.sha256()
        for it in plan["items"]:
            h.update((GS.build_item_body(plan, SAMPLE, it) + "\n").encode("utf-8"))
        for ms in plan["milestones"]:
            h.update((GS.build_subepic_body(plan, SAMPLE, ms) + "\n").encode("utf-8"))
        # the order of the recorded digest is: work items, then sub-epics, as the offline show-body printed them
        self.assertEqual(h.hexdigest(), GOLDEN_BODIES)

    def test_a_payload_with_the_permitted_substitutions_equals_the_legacy_body(self):
        plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        numbers = {RP.item_keys(plan).copy().pop(): 99}
        numbers = {L.tag(plan, it["id"]): 100 + n for n, it in enumerate(plan["items"])}
        numbers.update({f"M{m['number']}": 10 + m["number"] for m in plan["milestones"]})
        for it in plan["items"]:
            key = L.tag(plan, it["id"])
            payload = RP.item_payload(plan, SAMPLE, it)
            spec_url, skill_url = RP.urls_for(payload, "github.com", REPO, "main")
            body = GS.with_marker(RP.substitute(payload["body"], numbers, spec_url, skill_url), key)
            self.assertEqual(body, GS.build_item_body(plan, SAMPLE, it, numbers), key)
            self.assertEqual(GS.with_marker(RP.substitute(payload["body"], {}, spec_url, skill_url), key), GS.build_item_body(plan, SAMPLE, it), key)
        for ms in plan["milestones"]:
            payload = RP.subepic_payload(plan, SAMPLE, ms)
            spec_url, _ = RP.urls_for(payload, "github.com", REPO, "main")
            self.assertEqual(GS.with_marker(RP.substitute(payload["body"], numbers, spec_url), f"M{ms['number']}"),
                             GS.build_subepic_body(plan, SAMPLE, ms, numbers))
        payload = RP.rollup_payload(plan)
        self.assertEqual(RP.substitute(payload["body"], numbers, RP.urls_for(payload, "github.com", REPO, "main")[0]), GS.build_rollup(plan, numbers, 1))

    def test_logins_are_approved_values_in_the_payload_and_follow_the_flag(self):
        plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        staffed, _ = L.load_plan_with_people(SAMPLE / "docs/spec/plan.yaml", SAMPLE, people_path=SAMPLE / "people.yaml")
        it = plan["items"][0]
        self.assertEqual(RP.item_payload(plan, SAMPLE, it, staffed, {"assignees": False, "capacity_summary": False, "evidence": "synthetic-only"})["assignees"], [])
        # the sample's fictional people have no login, so even an allowed flag publishes none
        self.assertEqual(RP.item_payload(plan, SAMPLE, it, staffed, {"assignees": True, "capacity_summary": False, "evidence": "synthetic-only"})["assignees"], [])

    def test_the_capacity_summary_follows_its_flag(self):
        plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        on = RP.rollup_payload(plan, None, {"assignees": False, "capacity_summary": True, "evidence": "synthetic-only"})["body"]
        off = RP.rollup_payload(plan, None, {"assignees": False, "capacity_summary": False, "evidence": "synthetic-only"})["body"]
        self.assertIn("Track Workflow: 1 person", on)
        self.assertNotIn("Track Workflow", off)
        self.assertIn("Target delivery", off)

    def test_only_whole_issue_numbers_are_substituted(self):
        text = "WI-01 ({{issue:WI-01}}) and {{issue:WI-02}} WI-02 and {{other:x}}"
        self.assertEqual(RP.substitute(text, {"WI-01": 7, "WI-02": 8}), "WI-01 (#7) and #8 WI-02 and {{other:x}}")
        self.assertEqual(RP.substitute(text, {}), "WI-01 and WI-02 and {{other:x}}")
        for bad in ("7", "#7", 0, -1, True, 7.5, "7; DROP"):
            with self.subTest(number=bad):
                try:
                    RP.substitute(text, {"WI-01": bad})
                except RS.SchemaError as e:
                    self.assertEqual(e.code, "unapproved-substitution")
                else:
                    self.fail("a number that is not a whole number was substituted")

    def test_payload_files_carry_destination_target_and_substitution_paths(self):
        plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        files = RP.build_payloads(plan, SAMPLE)
        self.assertIn("payloads/issue/WI-06.json", files)
        payload = RS.loads_strict(files["payloads/issue/WI-06.json"])
        self.assertEqual(payload["destination_id"], "engineering")
        self.assertEqual(payload["target"], {"kind": "issue", "key": "WI-06", "marker": "<!-- carrydown:WI-06 -->"})
        self.assertEqual(payload["relationships"]["parent"], "M3")
        self.assertEqual(payload["substitutions"]["spec_path"], "docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md")
        self.assertEqual(RS.loads_strict(files["payloads/board/project.json"])["destination_id"], "board")
        self.assertEqual(files["payloads/issue/WI-06.json"], RS.canonical_json(payload))


class SyncTests(PubCase):
    def test_a_release_publishes_every_target_from_its_payloads_and_a_rerun_changes_nothing(self):
        self.released()
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("verification passed", out)
        self.assertEqual(len(mockgh.S.issues), 15)
        self.assertFalse((self.root / "docs/spec/github-issues.json").exists())
        journal = RS.loads_strict((self.ws / "publication" / f"{self.yp.request_id}.journal.json").read_bytes())
        entry = journal["targets"]["issue/WI-03"]
        self.assertEqual((entry["state"], entry["request_id"], entry["history"]), ("completed", self.yp.request_id, []))
        self.assertEqual(len(entry["managed_state_sha256"]), 64)
        n_before = len(writes(mockgh.S.log))
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(mockgh.S.issues), 15)
        self.assertEqual(len(writes(mockgh.S.log)), n_before)
        self.assertEqual(self.sync("--verify")[0], 0)

    def test_bodies_on_github_equal_the_legacy_builders_with_the_real_numbers(self):
        self.released()
        self.sync("--apply")
        plan, _ = L.load_plan(self.root / "docs/spec/plan.yaml", self.root)
        numbers = {}
        for i in mockgh.S.issues:
            for key in set(RP.MARKER_RE.findall(i["body"])):
                numbers[key] = i["number"]
        for it in plan["items"]:
            key = L.tag(plan, it["id"])
            self.assertEqual(self.issue_by_key(key)["body"], GS.build_item_body(plan, self.root, it, numbers), key)

    def test_dry_run_writes_nothing(self):
        self.released()
        before = len(writes(mockgh.S.log))
        code, out, err = self.sync()
        self.assertEqual(code, 0, out + err)
        self.assertIn("Dry run complete", out)
        self.assertEqual(len(writes(mockgh.S.log)), before)
        self.assertEqual(mockgh.S.issues, [])

    def test_an_interrupted_run_resumes_without_a_duplicate(self):
        self.released()
        mockgh.S.fail[("POST", r"/repos/[^/]+/[^/]+/issues")] = [None, None, "401"]
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertEqual(len(mockgh.S.issues), 2)
        journal = RS.loads_strict((self.ws / "publication" / f"{self.yp.request_id}.journal.json").read_bytes())
        self.assertEqual(sorted(journal["targets"]), sorted(["epic/EPIC", "subepic/M1"] + [f"label/{n}" for n in ("expense-approvals", "experience", "sub-epic", "workflow")]))
        self.assertEqual({v["state"] for k, v in journal["targets"].items() if not k.startswith("label")}, {"started"})
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(mockgh.S.issues), 15)
        titles = [i["title"] for i in mockgh.S.issues]
        self.assertEqual(len(titles), len(set(titles)))

    def test_G2_a_changed_managed_region_on_a_completed_item_stops_the_run(self):
        """[G2]"""
        self.released()
        self.assertEqual(self.sync("--apply")[0], 0)
        issue = self.issue_by_key("WI-03")
        issue["body"] = issue["body"].replace("Target completion", "Target completion (edited by hand)", 1)
        before = len(writes(mockgh.S.log))
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("target changed since publication: WI-03", out)
        self.assertEqual(len(writes(mockgh.S.log)), before)

    def test_text_outside_the_managed_region_is_not_a_change(self):
        self.released()
        self.assertEqual(self.sync("--apply")[0], 0)
        issue = self.issue_by_key("WI-03")
        issue["body"] = "A human note above.\n\n" + issue["body"]
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(issue["body"].startswith("A human note above."))

    def test_two_active_releases_are_a_mixed_release(self):
        self.released()
        tip = V.local_replay(str(self.ws)).replay.tip
        event = B.build_event([B.transition("f" * 64, "prepared", "active", tip, "release-approved")], V.local_policy({}, "o/r"),
                              created="2027-02-01T00:00:00Z", nonce="1" * 32)
        (self.ws / "events" / f"{event['event_id']}.json").write_bytes(RS.canonical_json(event))
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("mixed-release", out + err)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_G4_a_withdrawn_release_makes_every_publisher_refuse_before_any_write(self):
        """[G4] [G6]"""
        rid = self.released()
        self.assertEqual(F.run(R.main, ["withdraw", "--root", str(self.root), "--request", rid, "--reason", "error-found", "--apply"])[0], 0)
        for run in (lambda: self.sync("--apply"), lambda: self.board_run("--apply")):
            code, out, err = run()
            self.assertEqual(code, 1)
            self.assertIn("withdrawn", out + err)
        self.assertEqual(writes(mockgh.S.log), [])
        self.assertEqual(mockgh.S.issues, [])

    def test_G1_a_project_that_was_never_approved_publishes_nothing(self):
        """[G1]"""
        self.project()
        self.yp.prepare()
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("not-approved", out + err)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_repository_named_on_the_command_line_must_be_the_approved_one(self):
        self.released()
        code, out, err = self.sync("--apply", "--repo", "o/r")
        self.assertEqual(code, 1)
        self.assertIn("target-identity-mismatch", out + err)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_repository_with_another_numeric_id_is_refused_before_a_write(self):
        self.released()
        mockgh.S.repo_ids[REPO] = 7777
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("target-identity-mismatch", out + err)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_public_repository_is_refused_for_a_repository_readers_release(self):
        self.released()
        mockgh.S.private = False
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("audience-visibility-mismatch", out + err)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_label_that_is_neither_present_nor_approved_stops_the_run(self):
        self.project()
        self.yp.prepare("--destinations", "engineering-repo,issue,subepic,epic,epic-comment")
        self.yp.approve()
        self.yp.export()
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("destination-not-allowed", out)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_snapshot_payload_that_was_edited_after_approval_is_refused(self):
        self.released()
        request = R.load_request(self.ws, self.yp.request_id)
        payload = self.ws / "releases" / request["release_id"] / "snapshot" / "payloads" / "issue" / "WI-03.json"
        payload.write_bytes(payload.read_bytes().replace(b"Approval routing engine", b"Something else"))
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("sha256-mismatch", out + err)
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_write_that_belongs_to_no_target_is_refused_by_the_client_guard(self):
        self.released()
        gh = G.GitHub("ghp_" + "Z" * 36)
        pub = RSY.open_publication(self.root, mock.Mock(token_file=None), gh)
        RSY.install_guard(gh, self.root, pub)
        for method, path, data in (("POST", f"/repos/{REPO}/labels", {"name": "surprise", "color": "ffffff", "description": ""}),
                                   ("PATCH", f"/repos/{REPO}/issues/9999", {"body": "x"}),
                                   ("POST", f"/repos/{REPO}/issues", {"title": "x", "body": "no marker"})):
            with self.subTest(path=path):
                try:
                    gh.rest(method, path, data)
                except RSY.PublicationRefused as e:
                    self.assertEqual(e.code, "destination-not-allowed")
                else:
                    self.fail("an unapproved write was sent")
        self.assertEqual(writes(mockgh.S.log), [])

    def test_a_body_that_differs_from_the_payload_is_an_unapproved_substitution(self):
        self.released()
        pub = RSY.open_publication(self.root, mock.Mock(token_file=None), G.GitHub("ghp_" + "Z" * 36))
        payload = pub.payload("issue", "WI-03")[1]
        pub.check_sent(payload, {}, pub.text_for(payload, {}))
        try:
            pub.check_sent(payload, {}, pub.text_for(payload, {}) + "\nextra line")
        except RSY.PublicationRefused as e:
            self.assertEqual(e.code, "unapproved-substitution")
        else:
            self.fail("a changed body was accepted")

    def test_a_repair_may_set_only_what_the_payload_lists(self):
        self.released()
        pub = RSY.open_publication(self.root, mock.Mock(token_file=None), G.GitHub("ghp_" + "Z" * 36))
        live = {"assignees": [], "labels": [{"name": "workflow"}]}
        RSY.check_patch(pub, "WI-03", live, {"title": pub.payload("issue", "WI-03")[1]["title"]})
        for patch in ({"title": "Another title"}, {"assignees": ["stranger"]}, {"labels": ["workflow", "surprise"]}):
            with self.subTest(patch=patch):
                try:
                    RSY.check_patch(pub, "WI-03", live, patch)
                except RSY.PublicationRefused as e:
                    self.assertEqual(e.code, "unapproved-substitution")
                else:
                    self.fail("an unapproved repair was accepted")

    def test_an_approved_assignee_login_is_published_and_one_that_does_not_resolve_stops_the_run(self):
        self.project()
        (self.ws / "people.yaml").write_text((SAMPLE / "people.yaml").read_text(encoding="utf-8").replace("github: \"\"", 'github: "tamsin-gh"', 1), encoding="utf-8")
        text = (self.ws / "people.yaml").read_text(encoding="utf-8")
        self.assertIn("tamsin-gh", text, "the fixture people file has no github field to fill")
        self.assertEqual(self.yp.prepare("--assignees", "yes")[0], 0)
        self.yp.approve()
        self.yp.export()
        mockgh.S.missing_users.add("tamsin-gh")
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("assignee-unresolved", out)
        self.assertEqual(writes(mockgh.S.log), [])
        mockgh.S.missing_users.clear()
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertEqual([a["login"] for a in self.issue_by_key("WI-01").get("assignees", [])], ["tamsin-gh"])

    def test_a_replacement_updates_the_same_issues_and_keeps_the_earlier_request_in_the_history(self):
        first = self.released()
        self.assertEqual(self.sync("--apply")[0], 0)
        numbers = {i["title"]: i["number"] for i in mockgh.S.issues}
        spec = self.root / "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md"
        spec.write_text(spec.read_text(encoding="utf-8").replace("## Acceptance criteria\n", "## Acceptance criteria\n\n- A replacement release changed this criterion.\n", 1), encoding="utf-8")
        self.assertEqual(self.yp.prepare(nonce=None, created=None)[0], 0)
        second = self.yp.request_id
        self.assertNotEqual(first, second)
        self.assertEqual(self.yp.approve()[0], 0)
        self.assertEqual(self.yp.export()[0], 0)
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertEqual({i["title"]: i["number"] for i in mockgh.S.issues}, numbers)
        self.assertIn("A replacement release changed this criterion", self.issue_by_key("WI-03")["body"])
        journal = RS.loads_strict((self.ws / "publication" / f"{second}.journal.json").read_bytes())
        entry = journal["targets"]["issue/WI-03"]
        self.assertEqual((entry["state"], entry["request_id"]), ("completed", second))
        self.assertEqual([h["request_id"] for h in entry["history"]], [first])

    def test_a_legacy_project_still_publishes_as_before_and_the_gate_is_asked_for_each_write(self):
        legacy = self.base / "legacy"
        shutil.copytree(SAMPLE, legacy)
        F.strip_handling(legacy)
        calls = []
        real = RG.check

        def spy(*a, **k):
            calls.append((a[0], a[1]))
            return real(*a, **k)
        with mock.patch.object(RG, "check", spy), contextlib.redirect_stderr(io.StringIO()):
            code, out, err = F.run(GS.run, ["--root", str(legacy), "--repo", REPO, "--skip-check", "--apply", "--create-epic"])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(mockgh.S.issues), 15)
        release_calls = [c for c in calls if c[0] == "release"]
        self.assertGreaterEqual(len(release_calls), len(writes(mockgh.S.log)))


class BoardTests(PubCase):
    def test_the_board_is_built_from_the_approved_payload_and_resumes_from_its_journal(self):
        self.released()
        self.assertEqual(self.sync("--apply")[0], 0)
        code, out, err = self.board_run("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("verification passed", out)
        self.assertEqual(len(mockgh.S.projects[0]["items"]), 15)
        journal = RS.loads_strict((self.ws / "publication" / f"{self.yp.request_id}.journal.json").read_bytes())
        self.assertEqual(journal["targets"]["board/project"]["state"], "completed")
        before = len(mockgh.S.gql)
        code, out, err = self.board_run("--apply")
        self.assertEqual(code, 0, out + err)
        item = mockgh.S.projects[0]["items"][3]
        field = next(iter(item["values"]))
        item["values"][field] = {"date": "2030-01-01"} if "date" in item["values"][field] else item["values"][field]
        item["values"][field] = {"date": "2030-01-01"}
        code, out, err = self.board_run("--apply")
        self.assertEqual(code, 1)
        self.assertIn("target changed since publication: board", out)

    def test_a_board_that_does_not_exist_is_never_created_by_a_release(self):
        self.project()
        self.yp.board_project_id = "PVT_missing"
        self.yp.release()
        self.assertEqual(self.sync("--apply")[0], 1)       # the target resolution already refuses
        mockgh.S.projects.clear()
        before = len(mockgh.S.projects)
        code, out, err = self.board_run("--apply")
        self.assertEqual(code, 1)
        self.assertEqual(len(mockgh.S.projects), before)
        self.assertNotIn("createProjectV2", mockgh.S.gql)

    def test_a_board_with_a_wider_audience_is_refused_before_any_write(self):
        self.released()
        self.board["public"] = True
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 1)
        self.assertIn("audience-visibility-mismatch", out + err)
        self.assertEqual(writes(mockgh.S.log), [])


if __name__ == "__main__":
    unittest.main()
