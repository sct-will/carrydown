"""The migration inventories and the reports that never print GitHub's text (work package 8, items 4 to 6).

  release.py inventory   what a legacy project tracks and has in git history; writes nothing
  github_sync --inventory   every managed issue: pristine or not, text outside the managed region, whether
                            it predates the active release; writes nothing and proposes no rewrite
  issue_drift and find   the plan key, the issue number and a digest, never the body or GitHub's title

The first runs on a temporary git repository. The others run against the local mock of the GitHub API
(tests/mock/mockgh.py). No token and no network are used.
"""
import contextlib
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import github_client as G  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release as R  # noqa: E402
import release_fixture as F  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
REPO = "sct-will/carrydown-sample"
TOKEN_BODY = "ZEBRA-BODY-TOKEN-7731"
TOKEN_TITLE = "ZEBRA-TITLE-TOKEN-4409"


def tree_state(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(folder).parts}


def sh(args, cwd):
    return F.sh(args, cwd).stdout


class ReleaseInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-inventory-")
        cls.root = Path(cls.temp.name) / "legacy"
        shutil.copytree(SAMPLE, cls.root)
        F.strip_handling(cls.root)
        (cls.root / "docs" / "source").mkdir(parents=True)
        (cls.root / "docs" / "source" / "architecture.docx").write_bytes(b"original")
        (cls.root / "docs" / "source" / "old-notes.docx").write_bytes(b"old")
        F.init_git(cls.root)
        sh(["git", "add", "-A"], cls.root)
        sh(["git", "commit", "-q", "-m", "legacy project"], cls.root)
        sh(["git", "rm", "-q", "docs/source/old-notes.docx"], cls.root)
        sh(["git", "commit", "-q", "-m", "drop the notes"], cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_inventory(self):
        return F.run(R.main, ["inventory", "--root", str(self.root)])

    def test_it_lists_tracked_originals_renderings_staffing_fields_and_generated_references(self):
        code, out, err = self.run_inventory()
        self.assertEqual(code, 0, out + err)
        self.assertIn("Project state: legacy (no handling policy)", out)
        self.assertRegex(out, r"Tracked originals: \d+\n  docs/source/architecture\.docx")
        self.assertIn("  docs/ground-truth/architecture.md", out)
        self.assertIn("  people.yaml is tracked", out)
        self.assertIn("  people:tamsin:name in docs/spec/plan.yaml", out)
        self.assertIn("  people:tamsin:allocation in docs/spec/plan.yaml", out)
        self.assertIn("  people:idris:skills in docs/spec/plan.yaml", out)
        self.assertRegex(out, r"Generated references of the engineers' skill: 3\n  docs/dev/skills/expense-approvals-dev/references/contracts\.md")

    def test_it_says_which_of_them_are_in_history_including_a_file_removed_since(self):
        code, out, err = self.run_inventory()
        self.assertRegex(out, r"docs/source/architecture\.docx   in history, first added in commit [0-9a-f]{7,}")
        self.assertRegex(out, r"removed since, still in history: docs/source/old-notes\.docx   first added in commit [0-9a-f]{7,}")
        self.assertRegex(out, r"staffing fields of docs/spec/plan\.yaml appear in 1 commit\(s\); the newest is [0-9a-f]{7,}")

    def test_it_states_that_history_cannot_be_rewritten_and_links_githubs_guidance(self):
        code, out, err = self.run_inventory()
        self.assertIn("Carrydown cannot rewrite git history.", out)
        self.assertIn("https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository", out)
        self.assertIn("This is the first step of migrating a legacy project.", out)

    def test_it_never_prints_a_value_only_field_names_and_paths(self):
        code, out, err = self.run_inventory()
        plan_text = (self.root / "docs/spec/plan.yaml").read_text(encoding="utf-8")
        for value in re.findall(r'(?m)^    name: "([^"]+)"', plan_text):
            self.assertNotIn(value, out)

    def test_it_writes_nothing(self):
        before = (tree_state(self.root), sh(["git", "status", "--porcelain"], self.root), sh(["git", "rev-list", "--all", "--count"], self.root),
                  sh(["git", "branch", "-a"], self.root))
        self.run_inventory()
        self.run_inventory()
        after = (tree_state(self.root), sh(["git", "status", "--porcelain"], self.root), sh(["git", "rev-list", "--all", "--count"], self.root),
                 sh(["git", "branch", "-a"], self.root))
        self.assertEqual(before, after)

    def test_a_folder_that_is_not_a_git_repository_says_so(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-inventory-nogit-") as tmp:
            shutil.copytree(SAMPLE, Path(tmp) / "p")
            with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": tmp}):
                code, out, err = F.run(R.main, ["inventory", "--root", str(Path(tmp) / "p")])
            self.assertEqual(code, 0, out + err)
            self.assertIn("not inside a git repository", out)
            self.assertIn("Nothing was changed.", out)

    def test_a_migrated_project_with_nothing_private_tracked_says_so(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-inventory-clean-") as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            F.init_git(root)
            sh(["git", "add", "-A"], root)
            sh(["git", "commit", "-q", "-m", "first"], root)
            code, out, err = F.run(R.main, ["inventory", "--root", str(root)])
            self.assertEqual(code, 0, out + err)
            self.assertIn("Nothing private was found in tracked files or in history.", out)


class MockCase(unittest.TestCase):
    """A legacy copy of the sample on the local mock, with every issue created by github_sync --apply."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.url = mockgh.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-legacy-mock-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "legacy"
        shutil.copytree(SAMPLE, self.root)
        F.strip_handling(self.root)
        mockgh.S.__init__()
        mockgh.S.repos.add(REPO)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        env = {"CARRYDOWN_GITHUB_TOKEN": "ghp_" + "Z" * 36, "HOME": self.temp.name, "USERPROFILE": self.temp.name}
        self.stack.enter_context(mock.patch.dict(os.environ, env))
        self.stack.enter_context(mock.patch.object(time, "sleep", lambda s: None))
        self.stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None)))

    def sync(self, *args):
        return F.run(GS.run, ["--root", str(self.root), "--repo", REPO, "--skip-check"] + list(args))

    def created(self):
        code, out, err = self.sync("--apply", "--create-epic")
        self.assertEqual(code, 0, out + err)

    def issue(self, key):
        return next(i for i in mockgh.S.issues if f"<!-- carrydown:{key} -->" in (i.get("body") or ""))

    def writes(self):
        return [(m, p) for m, p in mockgh.S.log if m != "GET" and p != "/graphql"]


class IssueInventoryTests(MockCase):
    def test_a_hand_edited_legacy_body_is_reported_as_unmanaged_text_and_nothing_is_rewritten(self):
        self.created()
        legacy = self.issue("WI-03")
        legacy["body"] = "Hand written by a person before carrydown, with " + TOKEN_BODY + ".\n\n<!-- carrydown:WI-03 -->"
        edited_region = self.issue("WI-04")
        edited_region["body"] = edited_region["body"] + "\n\nA human note below the managed region."
        before = [dict(i) for i in mockgh.S.issues]
        mark = len(mockgh.S.log)
        code, out, err = self.sync("--inventory")
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, r"WI-03 #\d+: body was edited or is older than the generator; unmanaged text present;")
        self.assertRegex(out, r"WI-04 #\d+: body is pristine; unmanaged text present;|WI-04 #\d+: body was edited or is older than the generator; unmanaged text present;")
        self.assertRegex(out, r"WI-01 #\d+: body is pristine; no text outside the managed region;")
        self.assertIn("replacing the region does not remove it", out)
        self.assertIn("This report proposes no rewrite.", out)
        self.assertEqual(self.writes()[len(self.writes()):], [])
        self.assertEqual([m for m, p in mockgh.S.log[mark:] if m != "GET"], [])
        self.assertEqual(before, mockgh.S.issues, "an inventory changes nothing")
        self.assertNotIn(TOKEN_BODY, out)
        self.assertNotIn("Hand written by a person", out)
        self.assertNotIn("A human note", out)

    def test_every_issue_of_a_fresh_apply_is_pristine_and_without_unmanaged_text(self):
        self.created()
        code, out, err = self.sync("--inventory")
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, r"15 managed issue\(s\) found, 0 missing; 15 pristine; 0 with text outside the managed region\.")
        self.assertNotIn("replacing the region", out)
        self.assertIn("predates the active release (no release has published it)", out)

    def test_an_issue_that_is_missing_is_counted_and_no_issue_is_created(self):
        self.created()
        mockgh.S.issues = [i for i in mockgh.S.issues if "<!-- carrydown:WI-02 -->" not in (i.get("body") or "")]
        (self.root / "docs/spec/github-issues.json").unlink()
        mark = len(mockgh.S.log)
        code, out, err = self.sync("--inventory")
        self.assertEqual(code, 0, out + err)
        self.assertIn("  WI-02: no issue found", out)
        self.assertEqual([m for m, p in mockgh.S.log[mark:] if m != "GET"], [])

    def test_a_mapped_issue_that_no_longer_matches_is_reported_by_key_and_the_rest_goes_on(self):
        self.created()
        mockgh.S.issues = [i for i in mockgh.S.issues if "<!-- carrydown:WI-02 -->" not in (i.get("body") or "")]
        code, out, err = self.sync("--inventory")
        self.assertEqual(code, 0, out + err)
        self.assertIn("  WI-02: not matched to one issue (WI-02: persisted issue mapping failed identity verification; review its issue number before proceeding)", out)
        self.assertRegex(out, r"14 managed issue\(s\) found, 1 missing;")

    def test_inventory_cannot_be_combined_with_a_write(self):
        for flags in (["--inventory", "--apply"], ["--inventory", "--verify"], ["--inventory", "--preflight"], ["--inventory", "--offline"]):
            code, out, err = self.sync(*flags)
            self.assertNotEqual(code, 0, flags)
            self.assertIn("only reads", out + err)


class NoGitHubTextTests(MockCase):
    def fake_edit(self, key):
        issue = self.issue(key)
        issue["title"] = TOKEN_TITLE
        issue["body"] = "<!-- carrydown-managed:start -->\n" + TOKEN_BODY + "\n<!-- carrydown-managed:end -->\n\n<!-- carrydown:%s -->\n" % key
        return issue

    def test_issue_drift_output_has_no_substring_of_the_body_or_the_title_on_github(self):
        self.created()
        issue = self.fake_edit("WI-03")
        code, out, err = self.sync("--verify")
        self.assertEqual(code, 1)
        self.assertRegex(out, rf"WI-03 #{issue['number']} title: differs \(expected sha256 [0-9a-f]{{12}}, actual sha256 [0-9a-f]{{12}}\)")
        self.assertRegex(out, rf"WI-03 #{issue['number']} managed body and marker: differs \(expected sha256 [0-9a-f]{{12}}, actual sha256 [0-9a-f]{{12}}\)")
        for fragment in (TOKEN_BODY, TOKEN_TITLE, "ZEBRA", "<!--"):
            self.assertNotIn(fragment, out + err)
        # the plan's own title is not printed in the drift line either
        self.assertNotIn("Approval routing engine' ", out)

    def test_reconcile_prints_the_same_digest_lines_and_repairs_nothing_in_a_dry_run(self):
        self.created()
        self.fake_edit("WI-04")
        mark = len(mockgh.S.log)
        code, out, err = self.sync("--reconcile")
        self.assertIn("differs (expected sha256", out)
        self.assertNotIn("ZEBRA", out + err)
        self.assertEqual([m for m, p in mockgh.S.log[mark:] if m != "GET"], [])

    def test_the_ambiguity_table_names_issues_by_number_and_digest(self):
        self.created()
        original = self.fake_edit("WI-03")       # neither candidate is then the exact managed one
        (self.root / "docs/spec/github-issues.json").unlink()        # no persisted choice: the two candidates are ambiguous
        twin = mockgh.S.add_issue("another title " + TOKEN_TITLE, TOKEN_BODY + "\n\n<!-- carrydown:WI-03 -->", ["expense-approvals", "workflow"], repository=REPO)
        code, out, err = self.sync("--verify")
        self.assertNotEqual(code, 0)
        text = out + err
        self.assertIn("key | issue | state | marker | body sha256 | title matches the plan", text)
        self.assertRegex(text, rf"WI-03 \| #{original['number']} \| open \| True \| [0-9a-f]{{12}} \| False")
        self.assertRegex(text, rf"WI-03 \| #{twin['number']} \| open \| True \| [0-9a-f]{{12}} \| False")
        self.assertIn("ambiguous issue identity", text)
        for fragment in (TOKEN_BODY, TOKEN_TITLE, "ZEBRA"):
            self.assertNotIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
