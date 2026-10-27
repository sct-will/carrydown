"""Offline regressions for local and publication recovery, including apply boundaries."""
import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L
import github_client as G
import github_project as P
import github_sync as S
import github_token as T
import lint_prose as LP
import plan_repair as R


def quiet(call, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return call(*args, **kwargs)


class PlanRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-plan-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project with spaces"
        shutil.copytree(ROOT / "sample/expense-approvals", self.root)
        subprocess.run(["git", "init", str(self.root)], capture_output=True, check=True)
        self.path = self.root / "docs/spec/plan.yaml"
        self.raw = L.load_file(self.path)

    def recover(self, raw=None, decisions=None):
        return R.recover(raw or self.raw, self.root, decisions)

    def test_uniqueness_detected_before_lookup(self):
        for group, key in (("tracks", "id"), ("tracks", "label"), ("people", "id"), ("checkpoints", "date")):
            with self.subTest(group=group, key=key):
                data = copy.deepcopy(self.raw)
                data[group][1][key] = data[group][0][key]
                self.path.write_text(R.dump(data), encoding="utf-8")
                _, problems = L.load_plan(self.path, self.root)
                self.assertTrue(any("duplicate" in p for p in problems), problems)

    def test_identical_records_collapse_and_labels_become_unique(self):
        self.raw["people"].append(copy.deepcopy(self.raw["people"][0]))
        self.raw["checkpoints"].append(copy.deepcopy(self.raw["checkpoints"][0]))
        self.raw["tracks"][1]["label"] = self.raw["tracks"][0]["label"]
        result, actions, questions = self.recover()
        self.assertFalse(questions)
        self.assertEqual(len(result["people"]), 2)
        self.assertEqual(len(result["checkpoints"]), len(self.raw["checkpoints"]) - 1)
        self.assertEqual(len({t["label"] for t in result["tracks"]}), 2)
        self.assertTrue(all(t["id"] in t["label"] for t in result["tracks"]))

    def test_duplicate_people_rewrite_only_provable_ownership(self):
        self.raw["people"][1]["id"] = self.raw["people"][0]["id"]
        for item in self.raw["items"]:
            item["owner"] = self.raw["people"][0]["id"]
        result, _, questions = self.recover()
        self.assertFalse(questions)
        people = {p["track"]: p["id"] for p in result["people"]}
        for item in result["items"]:
            self.assertEqual(item["owner"], people[item["track"]])
        self.raw["people"][1]["track"] = self.raw["people"][0]["track"]
        _, _, questions = self.recover()
        self.assertTrue(questions)
        self.assertTrue(all(len(q["options"]) == 2 for q in questions))

    def test_duplicate_tracks_require_concrete_reference_choices(self):
        self.raw["tracks"][1]["id"] = self.raw["tracks"][0]["id"]
        for item in self.raw["items"]:
            item["track"] = self.raw["tracks"][0]["id"]
        result, actions, questions = self.recover()
        self.assertEqual(len({t["id"] for t in result["tracks"]}), 2)
        self.assertTrue(questions)
        self.assertTrue(any("items." in a and "candidates" in a for a in actions))
        confirmed = {q["path"]: q["options"][0] for q in questions}
        _, _, remaining = self.recover(decisions=confirmed)
        self.assertFalse(remaining)

    def test_external_ids_preserve_all_work_ids(self):
        self.raw["external"]["items"] += [{"id": 1, "label": "Other work"}, {"id": 5, "label": "Second external"}]
        result, _, questions = self.recover()
        ids = [row["id"] for row in result["external"]["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(set(ids) & {it["id"] for it in result["items"]})
        self.assertEqual([it["id"] for it in result["items"]], [it["id"] for it in self.raw["items"]])

    def test_joint_checkpoint_requires_confirmation_and_keeps_date(self):
        cp = copy.deepcopy(self.raw["checkpoints"][0])
        cp["name"], cp["joint_check"] = "Second check", "An additional joint check."
        self.raw["checkpoints"].append(cp)
        _, _, questions = self.recover()
        question = next(q for q in questions if q["path"].startswith("checkpoints."))
        combined = question["options"][0]
        result, _, remaining = self.recover(decisions={question["path"]: combined})
        self.assertFalse(remaining)
        self.assertIn("Second check", combined["name"])
        self.assertIn(cp["joint_check"], combined["joint_check"])
        self.assertEqual(len([c for c in result["checkpoints"] if c["date"] == cp["date"]]), 1)

    def test_legacy_refs_convert_and_prose_numbers_are_not_sections(self):
        result, actions, questions = self.recover()
        self.assertFalse(questions)
        self.assertEqual(result["items"][0]["source_refs"], [{"source": "architecture", "sections": "3.1, 3.2, 5.1, 7.1"}])
        self.raw["items"][0]["ground_truth"] = "Architecture document version 3.1 for WI-01"
        _, _, questions = self.recover()
        self.assertTrue(any(q["path"] == "items.1.source_refs" for q in questions))
        self.assertEqual(L.explicit_sections("version 3.1, WI-01; Sections 5.1, 7.1"), ["5.1", "7.1"])

    def test_specification_prose_cannot_replace_plan_refs(self):
        self.raw["items"][0]["ground_truth"] = ""
        self.path.write_text(R.dump(self.raw), encoding="utf-8")
        _, problems = L.load_plan(self.path, self.root)
        self.assertTrue(any("plan-level source_refs" in p for p in problems))
        result, _, questions = self.recover()
        # The old specification has sections but does not identify a source by name.
        self.assertTrue(any(q["path"] == "items.1.source_refs" for q in questions))

    def test_unreadable_unknown_empty_and_duplicate_refs(self):
        self.raw["sources"].append({"id": "unreadable", "name": "Unreadable", "status": "unreadable", "limit": "Cannot extract"})
        for refs in ([{"source": "unknown", "sections": "1"}], [{"source": "unreadable", "sections": "1"}], [{"source": "architecture", "sections": ""}]):
            self.raw["items"][0]["source_refs"] = refs
            result, _, questions = self.recover()
            question = next(q for q in questions if q["path"] == "items.1.source_refs")
            self.assertTrue(all(choice[0]["source"] == "architecture" for choice in question["options"]))
        self.raw["items"][0]["source_refs"] = [{"source": "architecture", "sections": "3.1"}] * 2
        result, _, questions = self.recover()
        self.assertEqual(len(result["items"][0]["source_refs"]), 1)

    def test_multiple_sources_without_identity_need_a_choice(self):
        other = copy.deepcopy(self.raw["sources"][0])
        other.update(id="governance", name="Company governance", path="docs/ground-truth/governance.md")
        self.raw["sources"].append(other)
        (self.root / other["path"]).write_text("# 1 Rules\n", encoding="utf-8")
        self.raw["items"][0]["ground_truth"] = ""
        _, _, questions = self.recover()
        question = next(q for q in questions if q["path"] == "items.1.source_refs")
        self.assertEqual({option[0]["source"] for option in question["options"]}, {"architecture", "governance"})

    def test_missing_section_is_not_manufactured(self):
        self.raw["items"][0]["ground_truth"] = "Sections 999.1"
        _, _, questions = self.recover()
        self.assertTrue(any(q["path"] == "items.1.source_refs" for q in questions))

    def test_portable_relative_path_separators(self):
        self.assertTrue(L.relative_inside("docs/spec/item.md"))
        self.assertTrue(L.relative_inside("docs\\spec\\item.md"))
        self.assertFalse(L.relative_inside("..\\secret.txt"))
        self.assertFalse(L.relative_inside("C:\\private\\secret.txt"))
        self.assertFalse(L.relative_inside("\\\\server\\share\\secret.txt"))

    def test_preview_apply_validation_and_idempotence_with_unicode_newlines(self):
        before = self.path.read_bytes()
        self.assertEqual(quiet(R.main, ["--root", str(self.root)]), 0)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(quiet(R.main, ["--root", str(self.root), "--apply"]), 0)
        applied = self.path.read_bytes()
        self.assertIn(b"source_refs:", applied)
        self.assertEqual(quiet(R.main, ["--root", str(self.root), "--apply"]), 0)
        self.assertEqual(self.path.read_bytes(), applied)
        value = {"text": "Caf\u00e9\nsecond line", "path": "docs/spec/item.md", "list": [{"name": "A"}]}
        self.assertEqual(L.loads(R.dump(value)), value)


class ConnectionTests(unittest.TestCase):
    def test_empty_single_and_later_page_projects(self):
        for pages in ([[]], [[{"id": "last", "title": "Plan", "number": 3, "url": "u", "closed": False}]], [[], [{"id": "last", "title": "Plan", "number": 3, "url": "u", "closed": False}]]):
            calls = []
            def query(q, variables):
                calls.append(variables)
                index = int(variables.get("after") or 0)
                return {"user": {"projectsV2": {"nodes": pages[index], "pageInfo": {"hasNextPage": index + 1 < len(pages), "endCursor": str(index + 1)}}}}
            gh = Mock(graphql=query)
            found = P.find_project(gh, "owner", "User", "Plan")
            self.assertEqual(found is not None, any(pages))
            self.assertEqual(len(calls), len(pages))

    def test_fields_views_and_nested_connections_exhaust_pages(self):
        first = {"fields": {"nodes": [{"id": "f1", "name": "First"}], "pageInfo": {"hasNextPage": True, "endCursor": "f2"}},
                 "views": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "v2"}}}
        view = {"id": "v", "name": "Table", "fields": {"nodes": [{"id": "f1"}], "pageInfo": {"hasNextPage": True, "endCursor": "vf2"}},
                "groupByFields": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "g2"}}}
        def query(q, v):
            if v["p"] == "v":
                name = "groupByFields" if "groupByFields(" in q else "fields"
                return {"node": {name: {"nodes": [{"id": "f2", "name": "Track"}], "pageInfo": {"hasNextPage": False}}}}
            if v.get("fa"):
                return {"node": {"fields": {"nodes": [{"id": "f2", "name": "Track"}], "pageInfo": {"hasNextPage": False}}}}
            if v.get("va"):
                return {"node": {"views": {"nodes": [copy.deepcopy(view)], "pageInfo": {"hasNextPage": False}}}}
            return {"node": copy.deepcopy(first)}
        data = P.load_project(Mock(graphql=query), "p")
        self.assertEqual(set(P.field_map(data)), {"First", "Track"})
        self.assertEqual(len(data["views"]["nodes"]), 1)
        self.assertEqual(len(data["views"]["nodes"][0]["fields"]["nodes"]), 2)
        self.assertEqual(len(data["views"]["nodes"][0]["groupByFields"]["nodes"]), 1)

    def test_items_and_item_values_later_pages_and_repository_identity(self):
        def query(q, v):
            if v["p"] == "item":
                return {"node": {"fieldValues": {"nodes": [{"field": {"name": "Track"}, "optionId": "later"}], "pageInfo": {"hasNextPage": False}}}}
            nodes = [] if not v.get("after") else [{"id": "item", "content": {"number": 7, "repository": {"nameWithOwner": "o/r"}},
                      "fieldValues": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "values2"}}}]
            return {"node": {"items": {"nodes": nodes, "pageInfo": {"hasNextPage": not v.get("after"), "endCursor": "items2"}}}}
        self.assertEqual(P.load_items(Mock(graphql=query), "p", "O/R")[7]["values"]["Track"], "later")

    def test_later_page_failure_is_bounded_and_resumable(self):
        calls = []
        def query(q, v):
            calls.append(v.get("after"))
            if v.get("after"):
                raise G.GitHubError("temporary", 503, "server")
            return {"node": {"items": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "page2"}}}}
        with patch.object(P.time, "sleep"), self.assertRaisesRegex(G.GitHubError, "page2.*Rerun to resume"):
            P.load_items(Mock(graphql=query), "p", "o/r")
        self.assertEqual(calls, [None, "page2", "page2", "page2"])

    def test_inaccessible_later_page_is_actionable(self):
        def query(q, v):
            if v.get("after"):
                return {"node": None}
            return {"node": {"items": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "later"}}}}
        with self.assertRaisesRegex(G.GitHubError, "later.*permission.*resume"):
            P.load_items(Mock(graphql=query), "p", "o/r")

    def test_track_options_preview_apply_preserve_and_permission_failure(self):
        field = {"id": "track", "name": "Track", "options": [{"id": "a", "name": "BACKEND", "color": "BLUE", "description": "Keep"}, {"id": "extra", "name": "Other", "color": "RED", "description": "Unrelated"}]}
        fields = {"Track": field}
        tracks = [{"label": "Backend"}, {"label": "Frontend"}]
        mutations = []
        def query(q, v):
            if q.startswith("mutation"):
                mutations.append(v)
                field["options"] = [{"id": str(i), **o} for i, o in enumerate(v["o"])]
                return {}
            return {"node": {"fields": {"nodes": [copy.deepcopy(field)]}, "views": {"nodes": []}}}
        gh = Mock(graphql=query)
        quiet(P.ensure_track_options, gh, "p", fields, tracks)
        self.assertFalse(mutations)
        quiet(P.ensure_track_options, gh, "p", fields, tracks, True)
        self.assertEqual([o["name"] for o in mutations[0]["o"]], ["BACKEND", "Other", "Frontend"])
        self.assertEqual([o.get("id") for o in mutations[0]["o"]], ["a", "extra", None])
        quiet(P.ensure_track_options, gh, "p", {"Track": field}, tracks, True)
        self.assertEqual(len(mutations), 1)
        gh = Mock(graphql=Mock(side_effect=G.GitHubError("permission denied", 403, "forbidden")))
        with self.assertRaisesRegex(G.GitHubError, "Track options.*permission.*resume"):
            quiet(P.ensure_track_options, gh, "p", fields, [{"label": "Missing"}], True)


class TokenRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-token-regression-")
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "explicit-source.txt"
        # Synthetic test data never leaves the mocked client.
        self.source.write_text("ghp_" + "a" * 36, encoding="utf-8")
        self.dest = Path(self.temp.name) / "private" / "stored"
        self.argv = ["--from-file", str(self.source), "--token-file", str(self.dest), "--repo", "o/r", "--delete-after"]

    def test_authentication_or_permission_failure_retains_source(self):
        for error in (G.GitHubError("auth", 401, "auth"), G.GitHubError("network", None, "network")):
            with patch.object(G, "GitHub", return_value=Mock(whoami=Mock(side_effect=error))):
                self.assertEqual(quiet(T.main, self.argv), 1)
            self.assertTrue(self.source.exists())
        with patch.object(G, "GitHub", return_value=Mock(whoami=Mock(return_value={"login": "person"}))), patch.object(T, "check", return_value=1):
            self.assertEqual(quiet(T.main, self.argv), 1)
        self.assertTrue(self.source.exists())

    def test_success_deletes_only_the_identified_regular_file(self):
        with patch.object(G, "GitHub", return_value=Mock(whoami=Mock(return_value={"login": "person"}))), patch.object(T, "check", return_value=0) as check:
            self.assertEqual(quiet(T.main, self.argv), 0)
        check.assert_called_once_with("ghp_" + "a" * 36, "o/r", require_permissions=True)
        self.assertFalse(self.source.exists())
        self.assertTrue(self.dest.exists())

    def test_symlinks_directories_and_implicit_sources_rejected(self):
        with self.assertRaisesRegex(SystemExit, ".*"):
            quiet(T.main, ["--delete-after", "--stdin"])
        with self.assertRaisesRegex(SystemExit, ".*"):
            quiet(T.main, ["--from-file", self.temp.name, "--delete-after", "--repo", "o/r"])
        link = Path(self.temp.name) / "link"
        try:
            link.symlink_to(self.source)
        except OSError:
            return  # Some Windows accounts cannot create links.
        argv = list(self.argv)
        argv[1] = str(link)
        with self.assertRaisesRegex(SystemExit, ".*"):
            quiet(T.main, argv)
        self.assertTrue(self.source.exists())

    def test_replaced_source_is_retained(self):
        def checked(*args, **kwargs):
            old = self.source.with_suffix(".old")
            self.source.rename(old)
            self.source.write_text("replacement", encoding="utf-8")
            return 0
        with patch.object(G, "GitHub", return_value=Mock(whoami=Mock(return_value={"login": "person"}))), patch.object(T, "check", side_effect=checked):
            self.assertEqual(quiet(T.main, self.argv), 1)
        self.assertEqual(self.source.read_text(encoding="utf-8"), "replacement")

    def test_all_permission_check_failures_retain_source(self):
        for scopes, response in (("repo", (200, {"permissions": {"push": True}})),
                                 ("repo, project", (404, {})),
                                 ("repo, project", (200, {"permissions": {"push": False}})),
                                 ("", (200, {"permissions": {"push": True}}))):
            client = Mock(scopes=scopes, whoami=Mock(return_value={"login": "person"}), rest_status=Mock(return_value=response))
            with patch.object(G, "GitHub", return_value=client):
                self.assertEqual(quiet(T.main, self.argv), 1)
            self.assertTrue(self.source.is_file())

    def test_store_failure_retains_source(self):
        with patch.object(G, "GitHub", return_value=Mock(whoami=Mock(return_value={"login": "person"}))), patch.object(T, "store", side_effect=SystemExit(1)):
            with self.assertRaisesRegex(SystemExit, "1"):
                quiet(T.main, self.argv)
        self.assertTrue(self.source.is_file())

    def test_deletion_permission_failure_retains_source_and_returns_nonzero(self):
        with patch.object(G, "GitHub", return_value=Mock(whoami=Mock(return_value={"login": "person"}))), patch.object(T, "check", return_value=0), patch.object(Path, "unlink", side_effect=PermissionError("cannot remove")):
            self.assertEqual(quiet(T.main, self.argv), 1)
        self.assertTrue(self.source.is_file())


class ProseDiscoveryTests(unittest.TestCase):
    def test_git_discovery_and_broader_scan(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-prose-regression-") as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", str(root)], capture_output=True, check=True)
            (root / ".gitignore").write_text("scratch/\n", encoding="utf-8")
            (root / "tracked.md").write_text("Clean.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "tracked.md", ".gitignore"], check=True)
            (root / "new.md").write_text("New.\r\n", encoding="utf-8")
            (root / "scratch").mkdir()
            ignored = root / "scratch/ignored.md"
            ignored.write_text(chr(0x2014), encoding="utf-8")
            with patch.object(LP, "ROOT", root):
                files = list(LP.files([]))
                self.assertEqual(files, [root / "new.md", root / "tracked.md"])
                self.assertIn(ignored, list(LP.files([], broad=True)))
                self.assertEqual(list(LP.files([str(ignored)])), [ignored.resolve()])
                self.assertEqual(quiet(LP.main, []), 0)
                self.assertEqual(quiet(LP.main, [str(ignored)]), 1)

    def test_nongit_order_is_deterministic_and_environments_excluded(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-nongit-regression-") as tmp:
            root = Path(tmp)
            for name in ("z.md", "a.md", ".venv/a.md", "build/a.md"):
                file = root / name
                file.parent.mkdir(exist_ok=True)
                file.write_text("Clean", encoding="utf-8")
            with patch.object(LP, "ROOT", root):
                self.assertEqual([p.name for p in LP.files([])], ["a.md", "z.md"])


if __name__ == "__main__":
    unittest.main()
