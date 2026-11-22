"""The renderer on confidential projects: markings, hidden and tracked content, links, comments,
where the rendering is written, and the digests recorded in the plan (work package 4).

Every test builds its project in a temporary folder from tests/fixtures/confidential-project and
its Word files with tests/fixtures/make_numbered_docx.py. No token and no network are used.
Run from the repository root: python -m unittest discover -s tests -v
"""
import hashlib
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
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import carrydown_lib as L  # noqa: E402
import make_numbered_docx as fixtures  # noqa: E402
import render_ground_truth as R  # noqa: E402
import workspace as W  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
SAMPLE = ROOT / "sample" / "expense-approvals"
RENDER = ROOT / "scripts" / "render_ground_truth.py"

# text that must never appear in a finding, only in --show-review-items and in an included rendering
SECRETS = ("HIDDEN-RUN-TEXT", "INSERTED-WORDS", "do not distribute", "Project Atlas")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


class RenderCase(unittest.TestCase):
    """A project folder copied from the fixture, an owner-only workspace beside it, and a runner."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="carrydown-render-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.project = self.tmp / "project"
        shutil.copytree(FIXTURE, self.project)
        self.strip_handling()
        self.workspace = self.tmp / "workspace"
        (self.workspace / "renderings").mkdir(parents=True)
        self.link_workspace()

    # -- setup helpers

    def link_workspace(self, path=None):
        pointer = self.project / ".carrydown" / "local.yaml"
        pointer.parent.mkdir(exist_ok=True)
        pointer.write_bytes((f"workspace: {json.dumps(str(path or self.workspace))}\n").encode("utf-8"))

    def strip_handling(self, project=None):
        """Remove a copied project's project.handling block so each test starts from a project with
        classified sources and no answer yet, and sets the answer it needs with set_handling. The
        sample and the fixture are both migrated plans now, so a legacy project is made this way."""
        plan = (project or self.project) / "docs" / "spec" / "plan.yaml"
        lines = plan.read_text(encoding="utf-8").splitlines(keepends=True)
        out, skipping = [], False
        for line in lines:
            if line.startswith("  handling:"):
                skipping = True
                continue
            if skipping and (line.startswith("    ") or line.strip() == ""):
                continue
            skipping = False
            out.append(line)
        plan.write_bytes(("".join(out)).encode("utf-8"))

    def set_handling(self, repo_audience_approved):
        """Set the answer to the one question. The fixture already carries a handling block
        (it is the "no" path), so the value is rewritten in place; a plan without one gets a block."""
        plan = self.project / "docs" / "spec" / "plan.yaml"
        text = plan.read_text(encoding="utf-8")
        value = "true" if repo_audience_approved else "false"
        if re.search(r"(?m)^    repo_audience_approved: ", text):
            text = re.sub(r"(?m)^(    repo_audience_approved: )\S+", r"\g<1>" + value, text, count=1)
        else:
            block = ("project:\n  handling:\n    policy_version: 1\n"
                     f"    repo_audience_approved: {value}\n"
                     "    state: migrated\n")
            self.assertIn("project:\n", text)
            text = text.replace("project:\n", block, 1)
        plan.write_bytes((text).encode("utf-8"))
        return plan

    def make_docx(self, mode, name=None):
        path = self.project / "ground-truth" / ((name or mode) + ".docx")
        fixtures.build(str(path), mode)
        return path

    def render(self, *args):
        run = subprocess.run([sys.executable, str(RENDER), *[str(a) for a in args], "--root", str(self.project)],
                             capture_output=True, text=True, timeout=120)
        return run.returncode, run.stdout + run.stderr

    def ws_rendering(self, name):
        return self.workspace / "renderings" / f"{name}.md"

    def project_rendering(self, name):
        return self.project / "docs" / "ground-truth" / f"{name}.md"


class MarkingAndReviewItemTests(RenderCase):
    """A marked Word file: a footer saying Internal, one hidden run, one tracked insertion."""

    def render_marked(self, *extra, source="architecture", name="marked"):
        path = self.make_docx("confidential", name)
        return self.render(path, "--source-id", source, "--name", name, "--out-dir", "docs/ground-truth", *extra)

    def test_stops_with_exit_2_counts_and_the_marking_finding_until_decided(self):
        code, out = self.render_marked()
        self.assertEqual(code, 2, out)
        self.assertIn("hidden or tracked content found in architecture: 2 items; review with --show-review-items", out)
        self.assertIn("marking disagrees with classification for architecture", out)
        self.assertIn("Nothing was written", out)
        self.assertFalse(self.project_rendering("marked").exists())
        self.assertFalse((self.project / "docs" / "ground-truth" / "marked.index.txt").exists())

    def test_succeeds_with_both_decisions_and_records_them_in_the_header(self):
        code, out = self.render_marked("--resolve-review-items", "include", "--accept-marking-mismatch")
        self.assertEqual(code, 0, out)
        text = self.project_rendering("marked").read_text(encoding="utf-8")
        header = text.splitlines()[0]
        self.assertIn('markings: "Project Atlas working copy / Internal, do not distribute".', header)
        self.assertIn("hidden or tracked content: include (2 items).", header)
        self.assertIn("marking mismatch accepted by the owner.", header)
        self.assertTrue(header.startswith("<!-- Generated from") and header.endswith("-->"))
        self.assertIn("HIDDEN-RUN-TEXT", text)
        self.assertIn("INSERTED-WORDS", text)
        self.assertNotIn("--", header[4:-3])

    def test_the_page_number_field_is_not_a_marking(self):
        code, out = self.render_marked("--resolve-review-items", "include", "--accept-marking-mismatch")
        self.assertEqual(code, 0, out)
        header = self.project_rendering("marked").read_text(encoding="utf-8").splitlines()[0]
        self.assertNotIn("/ 1", header)

    def test_each_decision_is_needed_on_its_own(self):
        code, out = self.render_marked("--resolve-review-items", "include")
        self.assertEqual(code, 2, out)
        self.assertIn("marking disagrees with classification for architecture", out)
        self.assertNotIn("hidden or tracked content found", out)
        code, out = self.render_marked("--accept-marking-mismatch")
        self.assertEqual(code, 2, out)
        self.assertIn("hidden or tracked content found in architecture: 2 items", out)
        self.assertNotIn("marking disagrees", out)
        self.assertIn("marking mismatch accepted for architecture", out)
        self.assertFalse(self.project_rendering("marked").exists())

    def test_exclude_leaves_hidden_text_and_insertions_out(self):
        code, out = self.render_marked("--resolve-review-items", "exclude", "--accept-marking-mismatch")
        self.assertEqual(code, 0, out)
        text = self.project_rendering("marked").read_text(encoding="utf-8")
        self.assertNotIn("HIDDEN-RUN-TEXT", text)
        self.assertNotIn("INSERTED-WORDS", text)
        self.assertIn("A visible sentence.", text)
        self.assertIn("hidden or tracked content: exclude (2 items).", text.splitlines()[0])

    def test_findings_never_print_the_text(self):
        code, out = self.render_marked()
        self.assertEqual(code, 2)
        for secret in SECRETS:
            self.assertNotIn(secret, out)
        code, out = self.render_marked("--resolve-review-items", "include", "--accept-marking-mismatch", "--dry-run")
        self.assertEqual(code, 0, out)
        for secret in SECRETS:
            self.assertNotIn(secret, out)

    def test_show_review_items_lists_paragraph_kind_and_text_for_the_owner(self):
        code, out = self.render_marked("--show-review-items")
        self.assertEqual(code, 2, out)
        self.assertIn("1. paragraph 4, hidden: HIDDEN-RUN-TEXT", out)
        self.assertIn("2. paragraph 5, inserted: INSERTED-WORDS", out)
        self.assertNotIn("Project Atlas", out)

    def test_a_restricted_source_has_no_marking_mismatch(self):
        path = self.make_docx("marking")
        code, out = self.render(path, "--source-id", "company-governance", "--name", "marked")
        self.assertEqual(code, 0, out)
        self.assertNotIn("marking disagrees", out)
        header = self.ws_rendering("marked").read_text(encoding="utf-8").splitlines()[0]
        self.assertIn('markings: "Project Atlas working copy / Internal, do not distribute".', header)

    def test_marking_words(self):
        for text in ("Confidential", "COMPANY RESTRICTED", "Internal use", "Please Do Not Distribute"):
            self.assertTrue(R.marking_conflicts([text]), text)
        for text in ("Project Atlas working copy", "Draft 3", ""):
            self.assertFalse(R.marking_conflicts([text]), text)

    def test_an_unclassified_legacy_source_is_reported_but_not_stopped(self):
        legacy = self.tmp / "legacy"
        copy_sample(legacy)
        self.strip_handling(legacy)
        path = legacy / "ground-truth" / "marked.docx"
        fixtures.build(str(path), "confidential")
        run = subprocess.run([sys.executable, str(RENDER), str(path), "--root", str(legacy), "--dry-run"],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("hidden or tracked content found in marked: 2 items", run.stdout)
        self.assertNotIn("marking disagrees", run.stdout)


class ReviewItemCollectionTests(RenderCase):
    def test_hidden_runs_styles_insertions_and_deletions_are_collected_with_paragraph_numbers(self):
        path = self.make_docx("review")
        code, out = self.render(path, "--source-id", "architecture", "--out-dir", "docs/ground-truth", "--show-review-items")
        self.assertEqual(code, 2, out)
        self.assertIn("review items in architecture: 4", out)
        self.assertIn("1. paragraph 4, hidden: HIDDEN-RUN-TEXT", out)
        self.assertIn("2. paragraph 5, hidden: HIDDEN-STYLE-TEXT", out)
        self.assertIn("3. paragraph 7, inserted: INSERTED-WORDS", out)
        self.assertIn("4. paragraph 7, deleted: DELETED-WORDS", out)
        self.assertNotIn("SHOWN-DESPITE-FLAG", out)    # w:vanish with value 0 is visible text

    def test_deleted_text_is_never_rendered_and_a_visible_flag_is_kept(self):
        path = self.make_docx("review")
        for decision in ("include", "exclude"):
            code, out = self.render(path, "--source-id", "architecture", "--name", decision, "--out-dir", "docs/ground-truth",
                                    "--resolve-review-items", decision)
            self.assertEqual(code, 0, out)
            text = self.project_rendering(decision).read_text(encoding="utf-8")
            self.assertNotIn("DELETED-WORDS", text)
            self.assertIn("SHOWN-DESPITE-FLAG", text)
            self.assertEqual("HIDDEN-STYLE-TEXT" in text, decision == "include")
            self.assertEqual("HIDDEN-RUN-TEXT" in text, decision == "include")

    def test_a_document_with_nothing_hidden_renders_without_a_decision(self):
        path = self.make_docx("marking")
        code, out = self.render(path, "--source-id", "company-governance")
        self.assertEqual(code, 0, out)
        self.assertNotIn("hidden or tracked", out)


class LinkAndCommentTests(RenderCase):
    def test_only_http_and_https_links_survive_in_word_files(self):
        path = self.make_docx("links")
        code, out = self.render(path, "--out-dir", "docs/ground-truth")
        self.assertEqual(code, 0, out)
        self.assertIn("link scheme removed in links", out)
        text = self.project_rendering("links").read_text(encoding="utf-8")
        self.assertIn("[Handbook](https://example.com/handbook)", text)
        self.assertIn("[Plain page](http://example.com/plain)", text)
        for text_only in ("Mail the owner", "Local plan", "Script link", "Finance share"):
            self.assertIn(text_only, text)
        for gone in ("mailto:", "file:", "javascript:", "corp-fs", "owner@example.com", "C:/Users"):
            self.assertNotIn(gone, text)

    def test_link_finding_names_the_source_id(self):
        path = self.make_docx("links")
        code, out = self.render(path, "--source-id", "architecture", "--out-dir", "docs/ground-truth", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("link scheme removed in architecture", out)

    def test_markdown_links_with_other_schemes_lose_the_target(self):
        md = self.project / "ground-truth" / "links.md"
        md.write_bytes(("# Links\n\n## 1. Ways\n\nSee [web](https://example.com/a), [local](file:///Users/me/x), "
                      "[mail](mailto:a@b.example), [rel](other.md#top), [anchor](#ways) and `[code](file:///kept)`.\n\n"
                      "![img](https://example.com/i.png)\n").encode("utf-8"))
        code, out = self.render(md, "--out-dir", "docs/ground-truth")
        self.assertEqual(code, 0, out)
        self.assertIn("link scheme removed in links (2 links)", out)
        text = self.project_rendering("links").read_text(encoding="utf-8")
        self.assertIn("[web](https://example.com/a), local, mail, [rel](other.md#top), [anchor](#ways)", text)
        self.assertIn("`[code](file:///kept)`", text)
        self.assertIn("![img](https://example.com/i.png)", text)

    def test_html_comments_are_stripped_and_counted(self):
        md = self.project / "ground-truth" / "notes.md"
        md.write_bytes(("# Notes\n\n<!-- reviewer: ask legal -->\n## 1. Scope\n\nText <!-- inline remark --> stays.\n\n"
                      "<!--\nmultiline\nnote\n-->\n\n```\n<!-- kept in code -->\n```\n\nUse `<!-- kept too -->` here.\n\n"
                      "<!-- never closed\nhidden to the end\n").encode("utf-8"))
        code, out = self.render(md, "--out-dir", "docs/ground-truth")
        self.assertEqual(code, 0, out)
        self.assertIn("HTML comments removed in notes: 4", out)
        text = self.project_rendering("notes").read_text(encoding="utf-8")
        for gone in ("reviewer", "inline remark", "multiline", "never closed", "hidden to the end"):
            self.assertNotIn(gone, text)
        self.assertIn("Text  stays.", text)
        self.assertIn("<!-- kept in code -->", text)
        self.assertIn("`<!-- kept too -->`", text)
        self.assertNotIn("\n<!-- reviewer", text)

    def test_the_comment_count_is_not_printed_when_there_are_none(self):
        code, out = self.render(FIXTURE / "ground-truth" / "architecture.md", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertNotIn("HTML comments", out)


class DestinationTests(RenderCase):
    def test_restricted_source_with_an_engineering_out_dir_is_refused(self):
        before = (self.project / "docs/ground-truth/company-governance.md").read_bytes()
        code, out = self.render(FIXTURE / "ground-truth" / "company-governance.md", "--out-dir", "docs/ground-truth")
        self.assertEqual(code, 2, out)
        self.assertIn("destination-not-allowed", out)
        self.assertIn("Nothing was written", out)
        self.assertEqual((self.project / "docs/ground-truth/company-governance.md").read_bytes(), before)
        self.assertFalse(self.ws_rendering("company-governance").exists())

    def test_restricted_source_goes_to_the_workspace_by_default(self):
        before = (self.project / "docs/ground-truth/company-governance.md").read_bytes()
        code, out = self.render(self.project / "ground-truth" / "company-governance.md", "--version", "2027.1")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.ws_rendering("company-governance").is_file())
        self.assertTrue((self.workspace / "renderings" / "company-governance.index.txt").is_file())
        self.assertEqual((self.project / "docs/ground-truth/company-governance.md").read_bytes(), before)
        self.assertIn("wrote workspace:renderings/company-governance.md", out)
        self.assertNotIn(str(self.workspace), out)     # the owner's folder is not printed

    def test_restricted_source_also_cannot_use_another_folder_in_the_project(self):
        code, out = self.render(self.project / "ground-truth" / "company-governance.md", "--out-dir", "docs/elsewhere")
        self.assertEqual(code, 2, out)
        self.assertIn("destination-not-allowed", out)
        self.assertFalse((self.project / "docs" / "elsewhere").exists())

    def test_restricted_source_may_name_a_folder_in_the_workspace(self):
        target = self.workspace / "renderings" / "custom"
        code, out = self.render(self.project / "ground-truth" / "company-governance.md", "--out-dir", target)
        self.assertEqual(code, 0, out)
        self.assertTrue((target / "company-governance.md").is_file())

    def test_restricted_source_without_a_workspace_is_refused_with_a_reason(self):
        (self.project / ".carrydown" / "local.yaml").unlink()
        index_before = (self.project / "docs/ground-truth/company-governance.index.txt").read_bytes()
        code, out = self.render(self.project / "ground-truth" / "company-governance.md")
        self.assertEqual(code, 2, out)
        self.assertIn("workspace-unavailable", out)
        self.assertEqual((self.project / "docs/ground-truth/company-governance.index.txt").read_bytes(), index_before)

    def test_a_workspace_inside_the_project_is_not_used(self):
        inner = self.project / "private"
        inner.mkdir()
        self.link_workspace(inner)
        code, out = self.render(self.project / "ground-truth" / "company-governance.md")
        self.assertEqual(code, 2, out)
        self.assertIn("workspace-inside-repository", out)
        self.assertFalse((inner / "renderings").exists())

    def test_yes_path_repo_readers_source_is_a_draft_write_in_the_project(self):
        self.set_handling(True)
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "0.3")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.project_rendering("architecture").is_file())
        self.assertFalse(self.ws_rendering("architecture").exists())

    def test_yes_path_restricted_source_is_still_refused_under_the_project(self):
        self.set_handling(True)
        code, out = self.render(self.project / "ground-truth" / "company-governance.md", "--out-dir", "docs/ground-truth")
        self.assertEqual(code, 2, out)
        self.assertIn("destination-not-allowed", out)
        code, out = self.render(self.project / "ground-truth" / "company-governance.md")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.ws_rendering("company-governance").is_file())

    def test_no_path_sends_every_rendering_to_the_workspace(self):
        self.set_handling(False)
        self.index_before = (self.project / "docs/ground-truth/architecture.index.txt").read_bytes()
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "0.3")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.ws_rendering("architecture").is_file())
        self.assertTrue((self.workspace / "renderings" / "architecture.index.txt").is_file())
        self.assertEqual((self.project / "docs/ground-truth/architecture.index.txt").read_bytes(), self.index_before)

    def test_no_path_refuses_an_engineering_out_dir_even_for_a_shareable_source(self):
        self.set_handling(False)
        before = (self.project / "docs/ground-truth/architecture.md").read_bytes()
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--out-dir", "docs/ground-truth")
        self.assertEqual(code, 2, out)
        self.assertIn("drafting-is-private", out)
        self.assertEqual((self.project / "docs/ground-truth/architecture.md").read_bytes(), before)
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--out-dir", "docs/other")
        self.assertEqual(code, 2, out)
        self.assertIn("drafting-is-private", out)

    def test_no_path_without_a_workspace_is_refused(self):
        self.set_handling(False)
        (self.project / ".carrydown" / "local.yaml").unlink()
        code, out = self.render(self.project / "ground-truth" / "architecture.md")
        self.assertEqual(code, 2, out)
        self.assertIn("workspace-unavailable", out)

    def test_a_path_that_is_neither_the_project_nor_the_workspace_is_still_refused(self):
        for source in ("architecture", "company-governance"):
            code, out = self.render(self.project / "ground-truth" / f"{source}.md", "--out-dir", self.tmp / "elsewhere")
            self.assertEqual(code, 2, out)
            self.assertIn("outside the project folder", out)
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--out-dir", "../elsewhere")
        self.assertEqual(code, 2, out)
        self.assertIn("outside the project folder", out)
        self.assertFalse((self.tmp / "elsewhere").exists())

    def test_the_out_dir_refusal_says_where_a_relative_folder_is_read_from(self):
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--out-dir", self.tmp / "elsewhere", "--dry-run")
        self.assertEqual(code, 2, out)
        self.assertIn(f"is outside the project folder {self.project.resolve()}, so nothing was written. "
                      "A relative --out-dir is read from the project root (--root). Give a folder inside it, such as my-test/ground-truth", out)
        self.assertNotIn("Dry run: nothing was written.", out)
        # the example works, and so does an absolute path inside the project
        for out_dir in ("my-test/ground-truth", self.project / "my-test" / "absolute"):
            code, out = self.render(self.project / "ground-truth" / "architecture.md", "--out-dir", out_dir, "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertNotIn("outside the project folder", out)

    def test_a_source_kept_in_the_workspace_renderings_is_not_overwritten(self):
        kept = self.workspace / "renderings" / "company-governance.md"
        shutil.copy(FIXTURE / "ground-truth" / "company-governance.md", kept)
        before = kept.read_bytes()
        code, out = self.render(kept)
        self.assertEqual(code, 2, out)
        self.assertIn("would overwrite the source", out)
        self.assertEqual(kept.read_bytes(), before)

    def test_a_source_reached_through_a_link_is_compared_by_its_resolved_path(self):
        target = self.workspace / "renderings" / "target.md"
        try:
            target.symlink_to(self.project / "ground-truth" / "architecture.md")
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are not available here")
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--source-id", "company-governance", "--name", "target")
        self.assertEqual(code, 2, out)
        self.assertIn("would overwrite the source", out)

    def test_two_inputs_each_go_where_their_classification_says(self):
        code, out = self.render(self.project / "ground-truth" / "architecture.md", self.project / "ground-truth" / "company-governance.md")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.project_rendering("architecture").is_file())
        self.assertTrue(self.ws_rendering("company-governance").is_file())

    def test_a_legacy_project_renders_where_it_always_did(self):
        legacy = self.tmp / "legacy"
        copy_sample(legacy)
        run = subprocess.run([sys.executable, str(RENDER), str(legacy / "ground-truth/architecture.md"), "--root", str(legacy), "--version", "0.3"],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("wrote docs/ground-truth/architecture.md", run.stdout)
        # the one line about the previous rendering is the only mention of a workspace
        others = [ln for ln in run.stdout.splitlines() if "workspace" in ln and not ln.startswith("warning: there is no private workspace, so the previous rendering of architecture")]
        self.assertEqual(others, [])

    def test_an_unreadable_plan_stops_the_render(self):
        (self.project / "docs" / "spec" / "plan.yaml").write_bytes(("project: [unclosed\n").encode("utf-8"))
        code, out = self.render(self.project / "ground-truth" / "architecture.md")
        self.assertEqual(code, 2, out)
        self.assertIn("cannot be read", out)

    def test_an_unknown_classification_stops_the_render(self):
        plan = self.project / "docs" / "spec" / "plan.yaml"
        plan.write_bytes((plan.read_text(encoding="utf-8").replace("classification: restricted", "classification: secret")).encode("utf-8"))
        code, out = self.render(self.project / "ground-truth" / "company-governance.md")
        self.assertEqual(code, 2, out)
        self.assertIn("must be public, repo-readers or restricted", out)

    def test_an_unknown_source_id_is_refused(self):
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--source-id", "nope")
        self.assertEqual(code, 2, out)
        self.assertIn("--source-id nope is not a source in the plan", out)


class DigestTests(RenderCase):
    def source_entry(self, plan_path, source_id):
        plan = L.load_file(plan_path)
        return next(s for s in plan["sources"] if s["id"] == source_id)

    def test_yes_path_records_digests_in_the_project_plan_and_keeps_its_layout(self):
        plan = self.set_handling(True)
        before = plan.read_text(encoding="utf-8")
        source = self.project / "ground-truth" / "architecture.md"
        code, out = self.render(source, "--version", "0.3")
        self.assertEqual(code, 0, out)
        self.assertIn("recorded content_sha256 and rendering_sha256 for architecture in docs/spec/plan.yaml", out)
        entry = self.source_entry(plan, "architecture")
        self.assertEqual(entry["content_sha256"], sha256_bytes(source.read_bytes()))
        self.assertEqual(entry["rendering_sha256"], sha256_bytes(self.project_rendering("architecture").read_bytes()))
        # only two lines were added: every other line, comments included, is as it was
        after_lines = plan.read_text(encoding="utf-8").splitlines()
        before_lines = before.splitlines()
        added = [ln for ln in after_lines if ln not in before_lines]
        self.assertEqual(len(added), 2, added)
        self.assertEqual([ln for ln in after_lines if ln in before_lines], before_lines)
        self.assertEqual(self.source_entry(plan, "company-governance").get("content_sha256"), None)

    def test_a_second_run_changes_nothing_and_a_changed_source_updates_the_digests(self):
        plan = self.set_handling(True)
        source = self.project / "ground-truth" / "architecture.md"
        self.assertEqual(self.render(source, "--version", "0.3")[0], 0)
        first = plan.read_bytes()
        self.assertEqual(self.render(source, "--version", "0.3")[0], 0)
        self.assertEqual(plan.read_bytes(), first)
        source.write_bytes((source.read_text(encoding="utf-8") + "\n## 99. Added\n\nNew rule.\n").encode("utf-8"))
        self.assertEqual(self.render(source, "--version", "0.4")[0], 0)
        entry = self.source_entry(plan, "architecture")
        self.assertEqual(entry["content_sha256"], sha256_bytes(source.read_bytes()))
        self.assertEqual(entry["rendering_sha256"], sha256_bytes(self.project_rendering("architecture").read_bytes()))
        self.assertEqual(plan.read_text(encoding="utf-8").count("content_sha256"), 1)

    def test_the_workspace_plan_is_the_one_updated_when_it_exists(self):
        self.set_handling(False)
        project_plan = self.project / "docs" / "spec" / "plan.yaml"
        (self.workspace / "drafts").mkdir()
        ws_plan = self.workspace / "drafts" / "plan.yaml"
        shutil.copy(project_plan, ws_plan)
        before = project_plan.read_bytes()
        source = self.project / "ground-truth" / "company-governance.md"
        code, out = self.render(source, "--version", "2027.1")
        self.assertEqual(code, 0, out)
        self.assertIn("in the workspace plan", out)
        self.assertEqual(project_plan.read_bytes(), before)
        entry = self.source_entry(ws_plan, "company-governance")
        self.assertEqual(entry["content_sha256"], sha256_bytes(source.read_bytes()))
        self.assertEqual(entry["rendering_sha256"], sha256_bytes(self.ws_rendering("company-governance").read_bytes()))

    def test_no_path_never_writes_digests_into_the_project_plan(self):
        project_plan = self.set_handling(False)
        before = project_plan.read_bytes()
        code, out = self.render(self.project / "ground-truth" / "architecture.md")
        self.assertEqual(code, 0, out)
        self.assertEqual(project_plan.read_bytes(), before)
        self.assertNotIn("recorded", out)

    def test_a_legacy_plan_is_not_changed(self):
        plan = self.project / "docs" / "spec" / "plan.yaml"
        before = plan.read_bytes()
        code, out = self.render(self.project / "ground-truth" / "architecture.md")
        self.assertEqual(code, 0, out)
        self.assertEqual(plan.read_bytes(), before)

    def test_a_dry_run_records_nothing(self):
        plan = self.set_handling(True)
        before = plan.read_bytes()
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("would record content_sha256 and rendering_sha256 for architecture", out)
        self.assertEqual(plan.read_bytes(), before)
        self.assertFalse(self.project_rendering("architecture").stat().st_size == 0)

    def render_sample(self, working, *extra):
        """Render the sample's source in a copy of the sample: the released plan as committed
        (working=False), or the owner's working plan in its place, as before the first release."""
        project = copy_sample(self.tmp / ("working" if working else "released"), working=working)
        source = project / "ground-truth" / "architecture.md"
        run = subprocess.run([sys.executable, str(RENDER), str(source), "--root", str(project), "--out-dir", "my-test/ground-truth",
                              "--version", "0.3", *extra], capture_output=True, text=True, timeout=120)
        return run.returncode, run.stdout + run.stderr, project / "docs" / "spec" / "plan.yaml"

    def test_a_released_plan_gets_no_digests_from_a_preview(self):
        before = (SAMPLE / "docs" / "spec" / "plan.yaml").read_bytes()
        code, out, plan = self.render_sample(False, "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertNotIn("would record", out)
        self.assertIn("note: docs/spec/plan.yaml is a released plan, so content_sha256 and rendering_sha256 for architecture "
                      "are not recorded in it. They are recorded in the workspace plan when the project has one", out)
        self.assertEqual(plan.read_bytes(), before)
        self.assertEqual(out.splitlines()[-1], "Dry run: nothing was written.")

    def test_a_released_plan_gets_no_digests_from_an_explicit_write(self):
        before = (SAMPLE / "docs" / "spec" / "plan.yaml").read_bytes()
        code, out, plan = self.render_sample(False)
        self.assertEqual(code, 0, out)
        self.assertNotIn("recorded content_sha256", out)
        self.assertIn("note: docs/spec/plan.yaml is a released plan, so content_sha256 and rendering_sha256", out)
        self.assertEqual(plan.read_bytes(), before)
        self.assertTrue((plan.parents[2] / "my-test" / "ground-truth" / "architecture.md").exists())
        self.assertNotIn("Dry run", out)
        self.assertEqual(L.load_plan(plan, root=plan.parents[2], view="released")[1], [])

    def test_the_working_plan_of_the_project_still_gets_the_digests(self):
        code, out, plan = self.render_sample(True)
        self.assertEqual(code, 0, out)
        self.assertIn("recorded content_sha256 and rendering_sha256 for architecture in docs/spec/plan.yaml", out)
        self.assertNotIn("is a released plan", out)
        entry = self.source_entry(plan, "architecture")
        self.assertEqual(entry["content_sha256"], sha256_bytes((SAMPLE / "ground-truth" / "architecture.md").read_bytes()))

    def test_an_extraction_records_the_digest_of_the_original_it_names(self):
        plan = self.set_handling(True)
        original = self.project / "docs" / "source" / "policy.txt"
        original.parent.mkdir(parents=True)
        original.write_bytes(b"original bytes of the policy")
        extraction = self.tmp / "extraction.md"
        extraction.write_bytes(("# Policy\n\n## 1. Rule\n\nUse the approved control.\n").encode("utf-8"))
        code, out = self.render(extraction, "--source-id", "architecture", "--name", "architecture",
                                "--source-label", "docs/source/policy.txt")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.source_entry(plan, "architecture")["content_sha256"], sha256_bytes(b"original bytes of the policy"))
        code, out = self.render(extraction, "--source-id", "architecture", "--name", "architecture", "--source-label", "docs/source/missing.pdf")
        self.assertEqual(code, 0, out)
        self.assertIn("content_sha256 of architecture was not recorded", out)

    def test_the_given_version_is_recorded_with_the_digests_in_the_workspace_plan(self):
        self.set_handling(False)
        project_plan = self.project / "docs" / "spec" / "plan.yaml"
        (self.workspace / "drafts").mkdir()
        ws_plan = self.workspace / "drafts" / "plan.yaml"
        shutil.copy(project_plan, ws_plan)
        before_project, before_lines = project_plan.read_bytes(), ws_plan.read_text(encoding="utf-8").splitlines()
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "0.4")
        self.assertEqual(code, 0, out)
        self.assertIn("recorded version 0.4 for architecture in the workspace plan", out)
        self.assertEqual(project_plan.read_bytes(), before_project)
        entry = self.source_entry(ws_plan, "architecture")
        self.assertEqual(entry["version"], "0.4")
        self.assertEqual(entry["rendering_sha256"], sha256_bytes(self.ws_rendering("architecture").read_bytes()))
        after_lines = ws_plan.read_text(encoding="utf-8").splitlines()
        self.assertIn('    version: "0.4"', after_lines)
        self.assertNotIn('    version: "0.3"', after_lines)
        # the version line is replaced where it was; only the two digest lines are added
        self.assertEqual(len([ln for ln in after_lines if ln not in before_lines]), 3)
        self.assertEqual(len(after_lines), len(before_lines) + 2)

    def test_the_given_version_is_recorded_in_the_project_plan_when_there_is_no_workspace_plan(self):
        plan = self.set_handling(True)
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "0.4")
        self.assertEqual(code, 0, out)
        self.assertIn("recorded version 0.4 for architecture in docs/spec/plan.yaml", out)
        entry = self.source_entry(plan, "architecture")
        self.assertEqual(entry["version"], "0.4")
        self.assertEqual(entry["rendering_sha256"], sha256_bytes(self.project_rendering("architecture").read_bytes()))
        self.assertEqual(plan.read_text(encoding="utf-8").count("version: \"0.4\""), 1)

    def test_without_a_version_the_plan_keeps_its_version_and_a_note_says_so(self):
        plan = self.set_handling(True)
        code, out = self.render(self.project / "ground-truth" / "architecture.md")
        self.assertEqual(code, 0, out)
        self.assertIn("note: --version was not given, so the version of architecture in docs/spec/plan.yaml is left as it is", out)
        self.assertIn("recorded content_sha256 and rendering_sha256 for architecture", out)
        self.assertNotIn("recorded version", out)
        entry = self.source_entry(plan, "architecture")
        self.assertEqual(entry["version"], "0.3")
        self.assertTrue(entry["rendering_sha256"])
        self.assertIn("version unversioned", self.project_rendering("architecture").read_text(encoding="utf-8").split("\n", 1)[0])

    def test_a_dry_run_with_a_version_leaves_the_plan_byte_identical(self):
        plan = self.set_handling(True)
        before = plan.read_bytes()
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "0.4", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("would record version 0.4 for architecture in docs/spec/plan.yaml", out)
        self.assertEqual(plan.read_bytes(), before)

    def test_a_released_plan_gets_no_version_from_an_explicit_write(self):
        before = (SAMPLE / "docs" / "spec" / "plan.yaml").read_bytes()
        code, out, plan = self.render_sample(False, "--version", "0.4")
        self.assertEqual(code, 0, out)
        self.assertNotIn("recorded version", out)
        self.assertEqual(plan.read_bytes(), before)
        self.assertIn("version 0.4", (plan.parents[2] / "my-test" / "ground-truth" / "architecture.md").read_text(encoding="utf-8").split("\n", 1)[0])

    def test_record_replaces_a_quoted_version_in_place_and_the_dumper_carries_it(self):
        path = self.write_plan('sources:\n  # the source\n  - id: "alpha"\n    version: "0.3"\n    name: "Alpha"\n')
        self.assertEqual(R.record_source_digests(path, {"alpha": {"rendering_sha256": "b" * 64, "version": "0.4"}}), (["alpha"], [], None))
        text = path.read_text(encoding="utf-8")
        self.assertIn('  # the source\n  - id: "alpha"\n    version: "0.4"\n    name: "Alpha"\n', text)
        path = self.write_plan('sources:\n  - {id: alpha, name: "Alpha", version: "0.3"}\n')
        self.assertEqual(R.record_source_digests(path, {"alpha": {"rendering_sha256": "b" * 64, "version": "0.4"}}), (["alpha"], [], None))
        self.assertEqual(L.load_file(path)["sources"][0], {"id": "alpha", "name": "Alpha", "version": "0.4", "rendering_sha256": "b" * 64})

    def test_record_keeps_a_trailing_comment_and_replaces_a_value_holding_a_hash(self):
        for old in ('"0.3"', "0.3", "'0.3'"):
            path = self.write_plan(f'sources:\n  - id: alpha\n    version: {old}   # bump on each issue\n    name: "Alpha"\n')
            self.assertEqual(R.record_source_digests(path, {"alpha": {"version": "0.4"}}), (["alpha"], [], None), old)
            self.assertIn('\n    version: "0.4"   # bump on each issue\n', path.read_text(encoding="utf-8"), old)
            self.assertEqual(L.load_file(path)["sources"][0]["version"], "0.4", old)
        for old, comment in (('"a #b"', ""), ('"a #b"  # note', "  # note")):
            path = self.write_plan(f'sources:\n  - id: alpha\n    version: {old}\n    name: "Alpha"\n')
            self.assertEqual(R.record_source_digests(path, {"alpha": {"version": "0.4"}}), (["alpha"], [], None), old)
            self.assertIn(f'\n    version: "0.4"{comment}\n    name', path.read_text(encoding="utf-8"), old)
            self.assertNotIn("#b", path.read_text(encoding="utf-8"), old)

    def write_plan(self, text):
        path = self.tmp / "plan.yaml"
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_record_in_place_keeps_comments_quotes_and_line_endings(self):
        text = ('# A plan\r\nproject:\r\n  name: "X"\r\n\r\nsources:\r\n  # the first source\r\n'
                '  - id: "alpha"\r\n    name: "Alpha"   # shown\r\n    version: "1"\r\n\r\n'
                '  - id: beta\r\n    name: "Beta"\r\n    content_sha256: "old"\r\n    use: "x"\r\n'
                'items: []\r\n')
        path = self.write_plan(text)
        done, missing, problem = R.record_source_digests(path, {"alpha": {"content_sha256": "a" * 64, "rendering_sha256": "b" * 64},
                                                                "beta": {"content_sha256": "c" * 64, "rendering_sha256": "d" * 64},
                                                                "gamma": {"content_sha256": "e" * 64}})
        self.assertEqual((done, missing, problem), (["alpha", "beta"], ["gamma"], None))
        data = path.read_bytes().decode("utf-8")
        self.assertNotIn("\n", data.replace("\r\n", ""))
        self.assertIn("# the first source\r\n", data)
        self.assertIn('name: "Alpha"   # shown', data)
        self.assertEqual(data.count("content_sha256"), 2)
        self.assertNotIn('"old"', data)
        parsed = L.loads(data)
        self.assertEqual(parsed["sources"][0]["rendering_sha256"], "b" * 64)
        self.assertEqual(parsed["sources"][1]["content_sha256"], "c" * 64)
        self.assertEqual(parsed["items"], [])

    def test_record_falls_back_to_the_dumper_for_a_source_written_as_a_flow_mapping(self):
        path = self.write_plan('project:\n  name: "X"\nsources:\n  - {id: alpha, name: "Alpha", version: "1"}\n')
        done, missing, problem = R.record_source_digests(path, {"alpha": {"content_sha256": "a" * 64, "rendering_sha256": "b" * 64}})
        self.assertEqual((done, missing, problem), (["alpha"], [], None))
        parsed = L.load_file(path)
        self.assertEqual(parsed["sources"][0], {"id": "alpha", "name": "Alpha", "version": "1",
                                                "content_sha256": "a" * 64, "rendering_sha256": "b" * 64})
        self.assertEqual(parsed["project"], {"name": "X"})

    def test_record_without_sources_changes_nothing(self):
        path = self.write_plan('project:\n  name: "X"\n')
        before = path.read_bytes()
        self.assertEqual(R.record_source_digests(path, {"alpha": {"content_sha256": "a" * 64}}), ([], ["alpha"], None))
        self.assertEqual(path.read_bytes(), before)


class PreviousRenderingTests(RenderCase):
    """The previous rendering is kept privately before it is replaced (specification 6.1). Rendering is not
    review: a render never changes a recorded checkpoint."""

    def history(self):
        folder = self.workspace / "renderings" / "history"
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def old_files(self):
        return (self.project / "docs/ground-truth/architecture.md").read_bytes(), (self.project / "docs/ground-truth/architecture.index.txt").read_bytes()

    def test_the_previous_rendering_is_copied_privately_before_it_is_replaced(self):
        self.set_handling(True)
        old_md, old_idx = self.old_files()
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "9.1")
        self.assertEqual(code, 0, out)
        self.assertNotEqual(self.old_files()[0], old_md)
        # a new version changes the header, so the .md is replaced and kept; the index lists the same headings and is not replaced
        self.assertEqual(self.old_files()[1], old_idx)
        self.assertEqual(self.history(), [f"architecture.{sha256_bytes(old_md)[:12]}.md"])
        folder = self.workspace / "renderings" / "history"
        self.assertEqual((folder / f"architecture.{sha256_bytes(old_md)[:12]}.md").read_bytes(), old_md)
        lines = [ln for ln in out.splitlines() if "preserved" in ln]
        self.assertEqual(lines, ["preserved the previous rendering of architecture privately in workspace:renderings/history/"])
        self.assertNotIn(str(self.workspace), out)
        self.assertLess(out.index("preserved the previous"), out.index("wrote docs/ground-truth/architecture.md"))

    def test_a_second_version_keeps_each_earlier_one_and_an_unchanged_render_keeps_nothing_new(self):
        self.set_handling(True)
        source = self.project / "ground-truth" / "architecture.md"
        self.assertEqual(self.render(source, "--version", "9.1")[0], 0)
        first_new = self.old_files()[0]
        before = self.history()
        code, out = self.render(source, "--version", "9.1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.history(), before)
        self.assertNotIn("preserved", out)
        code, out = self.render(source, "--version", "9.2")
        self.assertEqual(code, 0, out)
        self.assertIn(f"architecture.{sha256_bytes(first_new)[:12]}.md", self.history())
        self.assertEqual(len(self.history()), len(before) + 1)

    def test_a_dry_run_says_what_it_would_keep_and_keeps_nothing(self):
        self.set_handling(True)
        before = self.old_files()
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "9.1", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("would preserve the previous rendering of architecture privately in workspace:renderings/history/", out)
        self.assertEqual(self.history(), [])
        self.assertFalse((self.workspace / "renderings" / "history").exists())
        self.assertEqual(self.old_files(), before)

    def test_without_a_workspace_one_line_warns_that_the_previous_rendering_was_not_kept(self):
        self.set_handling(True)
        (self.project / ".carrydown" / "local.yaml").unlink()
        old_md = self.old_files()[0]
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "9.1")
        self.assertEqual(code, 0, out)
        warnings = [ln for ln in out.splitlines() if ln.startswith("warning:")]
        self.assertEqual(len(warnings), 1, out)
        self.assertIn("previous rendering of architecture was not preserved", warnings[0])
        self.assertIn("cannot be compared", warnings[0])
        self.assertNotEqual(self.old_files()[0], old_md)
        self.assertFalse((self.workspace / "renderings" / "history").exists())
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "9.2", "--dry-run")
        self.assertIn("would not be preserved", out)

    def test_a_first_rendering_has_nothing_to_keep_and_prints_neither_line(self):
        self.set_handling(True)
        (self.project / "docs/ground-truth/architecture.md").unlink()
        (self.project / "docs/ground-truth/architecture.index.txt").unlink()
        code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "9.1")
        self.assertEqual(code, 0, out)
        self.assertNotIn("preserved", out)
        self.assertNotIn("warning:", out)
        self.assertEqual(self.history(), [])

    def test_a_changed_index_is_kept_with_its_own_digest(self):
        self.set_handling(True)
        old_md, old_idx = self.old_files()
        source = self.project / "ground-truth" / "architecture.md"
        source.write_bytes((source.read_text(encoding="utf-8") + "\n## 99. Added\n\nNew rule.\n").encode("utf-8"))
        code, out = self.render(source, "--version", "9.1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.history(), [f"architecture.{sha256_bytes(old_md)[:12]}.md", f"architecture.{sha256_bytes(old_idx)[:12]}.index.txt"])
        self.assertEqual(len([ln for ln in out.splitlines() if "preserved" in ln]), 1)

    def test_the_no_path_keeps_the_previous_workspace_rendering_too(self):
        self.set_handling(False)
        source = self.project / "ground-truth" / "architecture.md"
        self.assertEqual(self.render(source, "--version", "9.1")[0], 0)
        first = self.ws_rendering("architecture").read_bytes()
        self.assertEqual(self.history(), [])
        code, out = self.render(source, "--version", "9.2")
        self.assertEqual(code, 0, out)
        self.assertIn(f"architecture.{sha256_bytes(first)[:12]}.md", self.history())
        self.assertIn("preserved the previous rendering of architecture privately", out)

    def test_a_rendering_already_inside_a_recorded_checkpoint_is_not_copied_and_checkpoints_are_never_changed(self):
        if shutil.which("git") is None:
            self.skipTest("git is needed")
        self.set_handling(True)
        identity = {"GIT_AUTHOR_NAME": "Test Owner", "GIT_AUTHOR_EMAIL": "owner@example.com", "GIT_COMMITTER_NAME": "Test Owner",
                    "GIT_COMMITTER_EMAIL": "owner@example.com", "HOME": str(self.tmp), "GIT_CONFIG_NOSYSTEM": "1"}
        with mock.patch.dict(os.environ, identity):
            subprocess.run(["git", "init", "-q"], cwd=str(self.workspace), check=True)
            (self.workspace / "workspace.yaml").write_bytes(("format: 1\nslug: confidential-fixture\nstate: drafting\n").encode("utf-8"))
            ground = self.project / "docs" / "ground-truth"
            descriptor = {"plan_sha256": sha256_bytes(b"plan"), "sources": [{"id": "architecture", "version": "0.3"}]}
            prepared = W.checkpoint_prepare(self.project, self.workspace, [ground / "architecture.md", ground / "architecture.index.txt"], descriptor, apply=True)
            result = W.checkpoint_commit(self.workspace, prepared["id"], apply=True)
            self.assertEqual(result["status"], "committed")
            record_before = (self.workspace / "workspace.yaml").read_bytes()
            old_md, old_idx = self.old_files()
            code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "9.1")
        self.assertEqual(code, 0, out)
        self.assertNotEqual(self.old_files()[0], old_md)
        self.assertEqual(self.history(), [])
        self.assertNotIn("preserved", out)
        self.assertNotIn("warning:", out)
        recorded = [ln for ln in out.splitlines() if "already recorded" in ln]
        self.assertEqual(recorded, [f"previous rendering of architecture already recorded in the reviewed checkpoint {prepared['id'][:12]}"])
        self.assertLess(out.index("already recorded"), out.index("wrote docs/ground-truth/architecture.md"))
        self.assertEqual((self.workspace / "workspace.yaml").read_bytes(), record_before)       # rendering is not review
        self.assertEqual(len(W.checkpoint_records(self.workspace)), 1)
        # the new rendering is not in any checkpoint, so replacing it keeps it
        with mock.patch.dict(os.environ, identity):
            code, out = self.render(self.project / "ground-truth" / "architecture.md", "--version", "9.2")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.history()), 1)
        self.assertNotIn("already recorded", out)
        self.assertEqual((self.workspace / "workspace.yaml").read_bytes(), record_before)

    def test_a_replaced_rendering_names_its_previous_version_and_a_kept_version_gets_the_next_minor_number(self):
        self.set_handling(True)
        source = self.project / "ground-truth" / "architecture.md"
        self.assertEqual(self.render(source, "--version", "0.3")[0], 0)
        code, out = self.render(source, "--version", "0.3")
        self.assertEqual(code, 0, out)
        self.assertNotIn("previous rendering of architecture: version", out)        # nothing replaced, nothing to say
        source.write_bytes((source.read_text(encoding="utf-8") + "\n## 99. Added\n\nNew rule.\n").encode("utf-8"))
        code, out = self.render(source, "--version", "0.3", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("previous rendering of architecture: version 0.3\n", out)
        self.assertIn("note: architecture changed but keeps version 0.3. If the document's own version line did not change, use --version 0.4.", out)
        code, out = self.render(source, "--version", "0.4")
        self.assertEqual(code, 0, out)
        self.assertIn("previous rendering of architecture: version 0.3\n", out)
        self.assertNotIn("keeps version", out)

    def test_the_next_minor_number(self):
        self.assertEqual([R.next_minor(v) for v in ("0.3", "1", "2.4.1", "v1.9", "unversioned", "")], ["0.4", "1.1", "2.5", "1.10", None, None])
        header = R.header_comment("architecture.docx", "0.3", "2027-01-02").encode("utf-8") + b"\n\n# Title\n"
        self.assertEqual(R.previous_version(header), "0.3")
        self.assertIsNone(R.previous_version(b"# no header\n"))

    def test_a_history_copy_that_the_gate_refuses_stops_the_render_before_anything_is_replaced(self):
        self.set_handling(True)
        before = self.old_files()
        from release_gate import Decision
        import release_gate as RG
        real = RG.check

        def deny_history(write_class, rel, digest, destination, root, **kw):
            if "renderings/history" in str(rel).replace("\\", "/"):
                return Decision(False, "deny", "workspace-unavailable", None)
            return real(write_class, rel, digest, destination, root, **kw)

        with mock.patch.object(RG, "check", side_effect=deny_history):
            code = R.main([str(self.project / "ground-truth" / "architecture.md"), "--root", str(self.project), "--version", "9.1"])
        self.assertEqual(code, 2)
        self.assertEqual(self.old_files(), before)
        self.assertEqual(self.history(), [])


class CommandLineTests(unittest.TestCase):
    def test_help_names_the_new_flags(self):
        run = subprocess.run([sys.executable, str(RENDER), "--help"], capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0)
        for flag in ("--show-review-items", "--resolve-review-items", "--accept-marking-mismatch", "--source-id", "--dry-run"):
            self.assertIn(flag, run.stdout)

    def test_html_comment_helper_leaves_inline_code_alone(self):
        text, _ = R.strip_html_comments("# T\n\n<!-- a -->\ntext\n")
        self.assertEqual(text, "# T\n\n\ntext\n")
        self.assertEqual(R.strip_html_comments("`<!-- a -->` and <!-- b -->")[1], 1)

    def test_scheme_rules(self):
        for ok in ("https://example.com", "HTTP://example.com", " https://example.com/a b"):
            self.assertTrue(R.link_is_web(ok), ok)
        for bad in ("mailto:a@b.example", "file:///C:/x", "javascript:alert(1)", "java\nscript:alert(1)", "\\\\server\\share\\f.docx", "../x.docx", "ftp://h/x"):
            self.assertFalse(R.link_is_web(bad), bad)
        self.assertTrue(R.link_has_other_scheme("java\nscript:x"))
        self.assertTrue(R.link_has_other_scheme("C:\\Users\\me\\x.docx"))
        self.assertFalse(R.link_has_other_scheme("other.md#top"))
        self.assertFalse(R.link_has_other_scheme("#anchor"))


if __name__ == "__main__":
    unittest.main()
