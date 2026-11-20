"""The plan page: scripts/plan_page.py writes one private HTML file for the plan owner.

Each test runs on a copy of the sample project as the owner drafts it, in a temporary HOME with a fixed git
identity and a real private workspace made by workspace.py init. No token and no network are used.
Run from the repository root: python3 -m unittest tests.test_plan_page -v
"""
import contextlib
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import check_specs as CS  # noqa: E402
import plan_page as PP  # noqa: E402
import reconcile as R  # noqa: E402
import workspace as W  # noqa: E402
from sample_tree import copy_sample, WORKING_PLAN  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
HAS_GIT = shutil.which("git") is not None
IDENTITY = {"GIT_AUTHOR_NAME": "Test Owner", "GIT_AUTHOR_EMAIL": "owner@example.com",
            "GIT_COMMITTER_NAME": "Test Owner", "GIT_COMMITTER_EMAIL": "owner@example.com"}
RENDERING = "docs/ground-truth/architecture.md"
REMINDER = "after 3 business days without a decision"
SECTION_TITLES = ["Project overview", "People and feasibility", "Milestone details", "Work item details", "Review findings"]


def call(main, argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    return code, out.getvalue(), err.getvalue()


class Outline(HTMLParser):
    """Headings with the h2 section they sit in, and every table as caption and rows of cell text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heads = []          # (tag, text, section id)
        self.tables = []         # {"caption": text, "rows": [[cell text]]}
        self.section = None
        self._head = None
        self._cell = None
        self._caption = None
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4"):
            self._head = [tag, "", a.get("id")]
        elif tag == "table":
            self.tables.append({"caption": "", "rows": []})
        elif tag == "caption":
            self._caption = ""
        elif tag == "tr" and self.tables:
            self.tables[-1]["rows"].append([])
        elif tag in ("td", "th") and self.tables:
            self._cell = ""

    def handle_endtag(self, tag):
        if self._head and tag == self._head[0]:
            t, text, hid = self._head
            if t == "h2":
                self.section = hid
            self.heads.append((t, " ".join(text.split()), self.section))
            self._head = None
        elif tag == "caption" and self._caption is not None:
            self.tables[-1]["caption"] = " ".join(self._caption.split())
            self._caption = None
        elif tag in ("td", "th") and self._cell is not None:
            self.tables[-1]["rows"][-1].append(" ".join(self._cell.split()))
            self._cell = None

    def handle_data(self, data):
        if self._head is not None:
            self._head[1] += data
        if self._caption is not None:
            self._caption += data
        if self._cell is not None:
            self._cell += data


def outline(text):
    p = Outline()
    p.feed(text)
    p.close()
    return p


@unittest.skipUnless(HAS_GIT, "git is needed")
class PlanPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-plan-page-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        env = {"HOME": str(self.home), "USERPROFILE": str(self.home), "XDG_CONFIG_HOME": str(self.home / "xdg"), "GIT_CONFIG_NOSYSTEM": "1"}
        env.update(IDENTITY)
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        self.root = self.base / "project"
        copy_sample(self.root, working=True, ignore=shutil.ignore_patterns("release"))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(self.root), capture_output=True, check=True)
        self.ws = self.base / "workspace"
        code, out, err = call(W.main, ["init", "--root", str(self.root), "--slug", "sample", "--workspace", str(self.ws), "--answer", "yes", "--apply"])
        self.assertEqual(code, 0, out + err)
        self.ws = Path(os.path.realpath(str(self.ws)))
        shutil.copyfile(str(SAMPLE / "people.yaml"), str(self.ws / "people.yaml"))
        self.page = self.ws / "review" / "plan-page.html"

    def write_page(self, *extra, root=None):
        code, out, err = call(PP.main, ["--root", str(root or self.root)] + list(extra))
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"plan page: {self.page}", out)
        return self.page.read_text(encoding="utf-8")

    def plan(self):
        plan, _problems = L.load_plan_with_people(L.owner_plan(self.root), self.root)
        return plan

    # -- where and how it is written

    def test_the_page_is_written_in_the_workspace_with_owner_only_permissions(self):
        self.write_page()
        self.assertTrue(self.page.is_file())
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.page.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(self.page.parent.stat().st_mode), 0o700)
        self.assertFalse(any(p.name == "plan-page.html" for p in self.root.rglob("*")))

    def test_a_dry_run_writes_nothing(self):
        code, out, err = call(PP.main, ["--root", str(self.root), "--dry-run"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("Dry run: nothing was written.", out)
        self.assertFalse((self.ws / "review").exists())

    def test_no_workspace_exits_2(self):
        code, out, err = call(PP.main, ["--root", str(SAMPLE), "--dry-run"])
        self.assertEqual(code, 2)
        self.assertIn("workspace-unavailable", err)
        self.assertIn("workspace.py init", err)

    def test_an_unknown_proposal_is_a_usage_error(self):
        code, out, err = call(PP.main, ["--root", str(self.root), "--proposal", "unknown"])
        self.assertEqual(code, 2, out + err)
        self.assertIn("proposal-not-found", err)
        self.assertFalse(self.page.exists())

    # -- what it shows

    def test_the_outline_has_one_h1_five_sections_and_one_h3_per_milestone_and_item(self):
        text = self.write_page()
        doc = outline(text)
        plan = self.plan()
        self.assertEqual([h for h in doc.heads if h[0] == "h1"], [("h1", "Expense approvals", None)])
        self.assertEqual([h[1] for h in doc.heads if h[0] == "h2"], SECTION_TITLES)
        self.assertEqual(len([h for h in doc.heads if h[0] == "h3" and h[2] == "milestones"]), len(plan["milestones"]))
        self.assertEqual(len([h for h in doc.heads if h[0] == "h3" and h[2] == "work-items"]), len(plan["items"]))
        self.assertIn("<title>Expense approvals: plan page</title>", text)
        self.assertIn('<html lang="en">', text)
        self.assertIn('aria-label="Sections"', text)

    def test_the_load_table_is_the_checkers(self):
        doc = outline(self.write_page())
        plan = self.plan()
        load = [t for t in doc.tables if t["caption"].startswith("Load:")]
        self.assertEqual(len(load), 1)
        head, rows, _sentences, _over = CS.load_table(plan)
        self.assertEqual(load[0]["rows"][0], head)
        self.assertEqual(load[0]["rows"][1:], [[" ".join(str(c).split()) for c in r] for r in rows])
        by = {r[0]: r for r in load[0]["rows"][1:]}
        for pid, mnum, sized, cap, _pct in L.load_rows(plan):
            self.assertTrue(by[pid][head.index(f"WU{mnum}")].startswith(f"{sized:g} of {cap:.0f}d"))

    def test_the_target_sentence_is_the_checkers(self):
        text = self.write_page()
        plan = self.plan()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            CS.report(plan)
        lines = CS.target_lines(plan)
        self.assertTrue(lines)
        for line in lines:
            self.assertIn("  " + line, buf.getvalue())
            self.assertIn(line, text.replace("&#x27;", "'"))

    def test_names_show_only_with_the_people_overlay(self):
        self.assertIn("Tamsin Hale", self.write_page())
        (self.ws / "people.yaml").unlink()
        text = self.write_page()
        self.assertNotIn("Tamsin Hale", text)
        self.assertNotIn("Idris Okoye", text)
        self.assertIn(CS.OVERLAY_NOTE, text)

    def test_specifications_and_sources_are_shown_and_linked(self):
        text = self.write_page()
        self.assertIn("A base total of 2500001 cents answers E_LIMIT with status 422", text)
        self.assertNotIn("Not done", text)
        listed = PP.markdown("- [x] The first check passes.\n- [ ] The second check passes.")
        self.assertIn('<ul class="checks">', listed)
        self.assertIn('<li><strong class="badge">Done</strong> The first check passes.</li>', listed)
        self.assertIn("<li>The second check passes.</li>", listed)
        self.assertIn('<time datetime="2027-02-01">2027-02-01</time>', text)
        spec = (self.root / "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md").resolve().as_uri()
        self.assertIn(f'href="{spec}"', text)
        rendering = (self.root / RENDERING).resolve().as_uri()
        self.assertIn(f'href="{rendering}#35-routing"', text)

    def test_the_page_is_self_contained(self):
        text = self.write_page()
        self.assertNotIn("<script", text.lower())
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)
        self.assertNotIn(chr(0x2014), text)    # em dash
        self.assertNotIn(chr(0x2013), text)    # en dash
        self.assertNotIn("<link", text.lower())
        self.assertNotIn("<img", text.lower())

    # -- an update to an existing project

    def make_checkpoint(self):
        project = R.Project(self.root)
        gathered = R.Gathered(project)
        files = [(e["id"], e["path"]) for e in gathered.sources]
        files += [(e["id"], e["path"].with_name(e["path"].name[:-3] + ".index.txt")) for e in gathered.sources
                  if e["path"].with_name(e["path"].name[:-3] + ".index.txt").is_file()]
        made = W.checkpoint_prepare(self.root, self.ws, files, gathered.descriptor, apply=True)
        done = W.checkpoint_commit(self.ws, made["id"], apply=True, root=self.root)
        self.assertIn(done["status"], ("committed", "already-recorded"), done)

    def test_a_saved_proposal_leads_the_page(self):
        self.make_checkpoint()
        rendering = self.root / RENDERING
        text = rendering.read_text(encoding="utf-8")
        self.assertIn(REMINDER, text)
        rendering.write_bytes((text.replace(REMINDER, "after 4 business days without a decision")).encode("utf-8"))
        code, out, err = call(R.main, ["prepare", "--root", str(self.root), "--apply"])
        self.assertEqual(code, 0, out + err)
        change_id = out.strip().splitlines()[-1].split()[-1]
        page = self.write_page()
        doc = outline(page)
        self.assertEqual([h[1] for h in doc.heads if h[0] == "h2"], ["What changed"] + SECTION_TITLES)
        blocks = [t for t in doc.tables if t["caption"] == "Changed blocks"]
        self.assertEqual(blocks[0]["rows"][1][0], "architecture/3.5")
        consumers = [t for t in doc.tables if t["caption"].startswith("Direct consumers")]
        self.assertIn(["architecture/3.5", "WI-03 Approval routing engine", "citation", "3.5"], consumers[0]["rows"])
        self.assertIn("pending: no decision recorded yet", page)
        self.assertIn(">What changed</h2>", self.write_page("--proposal", change_id))

    # -- the private path: the agent runs plan commands with --root <workspace>/drafts

    def drafts_root(self):
        drafts = self.ws / "drafts"
        shutil.copytree(str(self.root / "docs"), str(drafts / "docs"))
        shutil.copyfile(str(WORKING_PLAN), str(drafts / "plan.yaml"))
        return drafts

    def test_a_drafts_root_writes_the_page_in_its_workspace(self):
        drafts = self.drafts_root()
        code, out, err = call(PP.main, ["--root", str(drafts), "--plan", str(drafts / "plan.yaml")])
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"plan page: {self.page}", out)
        self.assertTrue(self.page.is_file())

    def test_a_drafts_root_loads_names_without_people(self):
        drafts = self.drafts_root()
        code, out, err = call(PP.main, ["--root", str(drafts), "--plan", str(drafts / "plan.yaml")])
        self.assertEqual(code, 0, out + err)
        self.assertIn("Tamsin Hale", self.page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
