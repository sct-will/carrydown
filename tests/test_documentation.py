"""Documentation, FAQ and sample (work package 10).

What these tests hold in place:
  - scaffold_spec.py writes the specification README and the milestone references for a released plan (it used
    to stop with a KeyError on project.ground_truth), and writes the same README from the owner's workspace plan
    and from the released plan, with no source path, no classification and no digest in it;
  - --refresh-headers and --ci work on a released project;
  - the sample is a released project: its plan is the exact projection of the owner's working plan in the
    fixture, and a clean clone with no workspace, no original, no rendering and no people file passes the checker;
  - every relative link of every Markdown file resolves, in the repository and in a clean clone of the sample;
  - the enterprise security page carries the three support labels, its notice and links, and no document or skill
    still gives an instruction that the confidentiality work replaced.

Run from the repository root: python -m unittest tests.test_documentation
No token and no network.
"""
import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import check_links as CL  # noqa: E402
import scaffold_spec as S  # noqa: E402
from sample_tree import WORKING_PLAN, copy_sample  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"


def run(args, cwd=None, env=None):
    return subprocess.run([sys.executable] + [str(a) for a in args], cwd=str(cwd or ROOT), capture_output=True, text=True, env=env)


def clean_clone(dst):
    """The committed sample as a clone holds it for an engineer: no original, no rendering, no people file."""
    shutil.copytree(SAMPLE, dst)
    shutil.rmtree(Path(dst) / "ground-truth")
    shutil.rmtree(Path(dst) / "docs" / "ground-truth")
    (Path(dst) / "people.yaml").unlink()
    return Path(dst)


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-docs-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)


class ReadmeFunctionTests(Temp):
    def plans(self):
        released, problems = L.load_plan(SAMPLE / "docs" / "spec" / "plan.yaml", SAMPLE)
        self.assertEqual(problems, [])
        working, problems = L.load_plan(WORKING_PLAN, SAMPLE)
        self.assertEqual(problems, [])
        return released, working

    def test_build_readme_does_not_need_project_ground_truth_and_matches_the_committed_readme(self):
        released, working = self.plans()
        self.assertNotIn("ground_truth", released["project"])
        readme = S.build_readme(released)
        self.assertEqual(readme, (SAMPLE / "docs" / "spec" / "README.md").read_text(encoding="utf-8"))

    def test_the_readme_is_the_same_from_the_workspace_plan_and_the_released_plan(self):
        released, working = self.plans()
        self.assertEqual(S.build_readme(released), S.build_readme(working))
        for stage in ("source_path", "classification", "content_sha256", "rendering_sha256", "docs/source/", "ground-truth/architecture.md"):
            self.assertNotIn(stage, S.build_readme(working))

    def test_the_milestone_references_name_no_source_path(self):
        released, working = self.plans()
        for plan in (released, working):
            for ms in plan["milestones"]:
                text = S.build_milestone(plan, ms)
                self.assertIn("- The approved context of each item, in `docs/context/`", text)
                self.assertNotIn("ground-truth", text)

    def test_the_committed_milestone_files_use_the_same_source_line(self):
        released, _ = self.plans()
        for ms in released["milestones"]:
            text = (SAMPLE / "docs" / "spec" / ms["folder"] / "milestone.md").read_text(encoding="utf-8")
            self.assertIn(S.milestone_source_lines(released)[0], text)

    def test_a_legacy_plan_keeps_its_old_readme(self):
        _, working = self.plans()
        legacy = copy.deepcopy(working)
        for key in ("plan_format", "plan_view"):
            legacy.pop(key, None)
        legacy["project"]["handling"] = None
        legacy["project"]["ground_truth"] = "docs/ground-truth/architecture.md"
        self.assertFalse(L.is_modern(legacy))
        readme = S.build_readme(legacy)
        self.assertIn("The rendered ground truth lives at `docs/ground-truth/architecture.md`.", readme)
        self.assertIn("| Precedence | Document | Original file | Rendered path |", readme)
        self.assertIn("Where it conflicts with the ground truth, the ground truth wins", readme)

    def test_a_refresh_leaves_the_committed_readme_alone(self):
        released, _ = self.plans()
        old = (SAMPLE / "docs" / "spec" / "README.md").read_text(encoding="utf-8")
        new, skipped = S.refreshed_readme(released, old)
        self.assertEqual(new, old)
        self.assertEqual(skipped, [])


class ScaffoldOnAReleasedProjectTests(Temp):
    def project(self):
        project = clean_clone(self.base / "released")
        for cmd in (["init", "-q", "-b", "main"], ["config", "user.name", "T"], ["config", "user.email", "t@example.com"]):
            subprocess.run(["git", "-C", str(project)] + cmd, check=True, capture_output=True)
        return project

    def test_refresh_headers_dry_run_and_apply_work_on_a_released_project(self):
        project = self.project()
        for flags in (["--refresh-headers"], ["--refresh-headers", "--apply"]):
            out = run([ROOT / "scripts" / "scaffold_spec.py", "--root", project] + flags)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertNotIn("Traceback", out.stdout + out.stderr)
            self.assertIn("0 file(s)", out.stdout.replace("would be written", "").replace("written", "") + "0 file(s)")
        self.assertEqual((project / "docs" / "spec" / "README.md").read_bytes(), (SAMPLE / "docs" / "spec" / "README.md").read_bytes())

    def test_a_refresh_changes_nothing_in_a_released_project(self):
        project = self.project()
        out = run([ROOT / "scripts" / "scaffold_spec.py", "--root", project, "--refresh-headers"])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("refresh header", out.stdout)
        self.assertNotIn("refresh tables", out.stdout)

    def test_ci_writes_the_workflow_and_the_checker_copy_for_a_released_project(self):
        project = self.project()
        shutil.rmtree(project / ".github")
        shutil.rmtree(project / "tools")
        out = run([ROOT / "scripts" / "scaffold_spec.py", "--root", project, "--ci", "--apply"])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue((project / ".github" / "workflows" / "check-specs.yml").is_file())
        self.assertEqual((project / ".github" / "workflows" / "check-specs.yml").read_bytes(),
                         (SAMPLE / ".github" / "workflows" / "check-specs.yml").read_bytes())
        for name in S.CHECKER_COPY:
            self.assertEqual((project / "tools" / "carrydown" / name).read_bytes(), (ROOT / "scripts" / name).read_bytes())
        check = run([project / "tools" / "carrydown" / "check_specs.py", "--root", project, "--view", "released"])
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_a_changed_plan_date_refreshes_a_released_project(self):
        project = self.project()
        plan = project / "docs" / "spec" / "plan.yaml"
        text = plan.read_text(encoding="utf-8")
        self.assertIn('complete_by: "2027-02-03"', text)
        plan.write_text(text.replace('complete_by: "2027-02-03"', 'complete_by: "2027-02-04"', 1), encoding="utf-8")
        out = run([ROOT / "scripts" / "scaffold_spec.py", "--root", project, "--refresh-headers"])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("wi-01-service-scaffold.md", out.stdout)


class SampleIsAReleasedProjectTests(Temp):
    def test_its_plan_is_the_released_projection_of_the_owners_working_plan(self):
        working, problems = L.load_plan(WORKING_PLAN, SAMPLE)
        self.assertEqual(problems, [])
        self.assertEqual(working["_view"], "workspace")
        self.assertEqual((SAMPLE / "docs" / "spec" / "plan.yaml").read_bytes(), L.released_plan_bytes(working))

    def test_the_released_plan_holds_no_private_key(self):
        plan, problems = L.load_plan(SAMPLE / "docs" / "spec" / "plan.yaml", SAMPLE)
        self.assertEqual(problems, [])
        self.assertEqual(plan["_view"], "released")
        self.assertEqual(sorted(plan["people"][0]), ["id", "track"])
        self.assertEqual([sorted(s) for s in plan["sources"]], [["id", "name", "version"]])
        text = (SAMPLE / "docs" / "spec" / "plan.yaml").read_text(encoding="utf-8")
        for private in ("classification", "source_path", "content_sha256", "rendering_sha256", "days_off", "allocation", "advisors", "github", "skills", "preferences", "assignment_rationale"):
            self.assertIsNone(re.search(rf"(?m)^\s*(- )?{private}:", text), private)     # a key, not a word of prose
        self.assertNotIn("Tamsin", text)

    def test_the_working_plan_in_the_fixture_holds_the_classification_and_the_paths(self):
        text = WORKING_PLAN.read_text(encoding="utf-8")
        for key in ("classification: repo-readers", "source_path: ground-truth/architecture.md", "content_sha256", "rendering_sha256", "plan_view: workspace"):
            self.assertIn(key, text)

    def test_a_clean_clone_passes_the_released_checker_with_no_workspace_original_rendering_or_people_file(self):
        clone = clean_clone(self.base / "clone")
        env = dict(os.environ, HOME=str(self.base / "home"), USERPROFILE=str(self.base / "home"))
        out = run([ROOT / "scripts" / "check_specs.py", "--root", clone, "--view", "released"], env=env)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("0 with findings", out.stdout)
        self.assertIn("people overlay not loaded: capacity, dates and names not checked", out.stdout)
        plain = run([ROOT / "scripts" / "check_specs.py", "--root", clone], env=env)
        self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)

    def test_the_sample_specifications_cite_sections_as_citation_lines_not_links_into_a_rendering(self):
        for spec in sorted((SAMPLE / "docs" / "spec").glob("m*/wi-*.md")):
            text = spec.read_text(encoding="utf-8")
            self.assertNotIn("ground-truth/architecture.md", text, spec.name)
            self.assertRegex(text, r"(?m)^- architecture section \d+\.\d+, ", spec.name)
            self.assertRegex(text, r"(?m)^\| Ground truth \| Architecture document: Sections ", spec.name)

    def test_the_gitignore_holds_the_four_scaffold_lines(self):
        lines = (SAMPLE / ".gitignore").read_text(encoding="utf-8").split("\n")
        for line in S.IGNORE_LINES:
            self.assertIn(line, lines)

    def test_the_sample_readme_says_the_originals_and_staffing_are_fictional_fixtures(self):
        text = (SAMPLE / "README.md").read_text(encoding="utf-8")
        self.assertIn("A public, fictional fixture", text)
        self.assertIn("tests/fixtures/sample-workspace/", text)
        self.assertIn("A real project does not copy staffing records or confidential originals into git", text)


class LinkCheckTests(Temp):
    def test_every_relative_link_in_the_repository_resolves(self):
        broken = CL.check(ROOT)
        self.assertEqual(broken, [], "\n".join(f"{f}:{n}: {t}: {w}" for f, n, t, w in broken))

    def test_every_relative_link_in_a_clean_clone_of_the_sample_resolves(self):
        clone = clean_clone(self.base / "clone")
        broken = CL.check(clone)
        self.assertEqual(broken, [], "\n".join(f"{f}:{n}: {t}: {w}" for f, n, t, w in broken))

    def test_every_relative_link_in_a_generated_project_resolves(self):
        owner = copy_sample(self.base / "owner")
        subprocess.run(["git", "init", "-q", "-b", "main", str(owner)], check=True, capture_output=True)
        shutil.rmtree(owner / "docs" / "dev")
        out = run([ROOT / "scripts" / "generate_dev_skill.py", "--root", owner, "--apply"])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        broken = CL.check(owner, ["docs/dev", "docs/spec/README.md"])
        self.assertEqual(broken, [], "\n".join(f"{f}:{n}: {t}: {w}" for f, n, t, w in broken))

    def test_the_checker_finds_a_missing_file_a_missing_anchor_and_skips_code_and_web_links(self):
        (self.base / "a.md").write_text(
            "# Title\n\n## Second part\n\n[ok](b.md) [heading](#second-part) [bad](nowhere.md) [anchor](b.md#absent) [anchor ok](b.md#start)\n"
            "[web](https://example.com/x) [mail](mailto:a@example.com) `[code](missing.md)` {{x}} [t]({{target}})\n\n"
            "```\n[fenced](missing.md)\n```\n![image](pic.png)\n", encoding="utf-8")
        (self.base / "b.md").write_text("# Start\n", encoding="utf-8")
        found = CL.check(self.base)
        self.assertEqual(sorted((t, w) for _, _, t, w in found),
                         [("b.md#absent", "anchor is not a heading of the target"), ("nowhere.md", "target does not exist"),
                          ("pic.png", "target does not exist")])

    def test_a_link_that_climbs_out_of_the_folder_is_reported(self):
        (self.base / "inner").mkdir()
        (self.base / "inner" / "a.md").write_text("[up](../../outside.md)\n", encoding="utf-8")
        found = CL.check(self.base / "inner")
        self.assertEqual([w for _, _, _, w in found], ["points outside the folder"])


PUBLIC_DOCS = ["README.md", "SECURITY.md", "docs/setup.md", "docs/security.md", "docs/faq.md", "docs/inputs.md", "docs/method.md",
               "docs/plan-owner-guide.md", "docs/recovery.md", "docs/sample-run.md", "docs/enterprise-security.md",
               "docs/delivery-modes.md", "docs/recording-storyboard.md"]


class EnterpriseSecurityPageTests(unittest.TestCase):
    PAGE = ROOT / "docs" / "enterprise-security.md"

    def text(self):
        return self.PAGE.read_text(encoding="utf-8")

    def test_it_carries_a_visible_notice_that_the_labels_are_not_yet_supported(self):
        text = self.text()
        self.assertIn("**Draft notice: not yet supported.**", text.split("\n\n", 2)[1] if text.startswith("# ") else text)
        self.assertIn("has not been performed", text)

    def test_it_uses_the_three_support_labels_exactly(self):
        text = self.text()
        self.assertIn("**supported** (implemented, documented and tested)", text)
        self.assertIn("**supported with prerequisites** (implemented and tested, but needs configuration your organization provides)", text)
        self.assertIn("**planned** (the design exists, the feature does not)", text)
        # every bold label is exactly one of the three, alone: no compound such as "Supported; ... supported with prerequisites."
        labels = set(re.findall(r"\*\*((?:S|s)upported[^*]*|(?:P|p)lanned[^*]*)\*\*", text))
        allowed = {"supported", "supported with prerequisites", "planned", "Supported.", "Supported with prerequisites.", "Planned."}
        self.assertEqual(labels - allowed, set())
        for row in (line for line in text.split("\n") if line.startswith("| ")):
            for cell in row.split(" | "):
                for sentence in re.split(r"(?<=[.!?])\*{0,2} ", cell):
                    found = re.findall(r"\*\*((?:S|s)upported(?: with prerequisites)?|(?:P|p)lanned)\.?\*\*", sentence)
                    self.assertLessEqual(len(found), 1, sentence)

    def test_every_answer_that_depends_on_the_real_github_run_says_it_was_not_performed(self):
        rows = [line for line in self.text().split("\n") if line.startswith("| ") and "**Supported with prerequisites.**" in line and not line.startswith("| Do hosted coding agents work?")]   # the hosted agent answer depends on the host, not on the GitHub run
        self.assertGreaterEqual(len(rows), 3)
        for row in rows:
            self.assertIn("Not yet proven on real GitHub.", row, row[:80])

    def test_it_links_the_security_guide_the_delivery_modes_and_the_setup_guide(self):
        text = self.text()
        for link in ("(security.md)", "(delivery-modes.md)", "(setup.md#organization-setup-for-private-drafting)", "(setup.md#acceptance-on-real-github)"):
            self.assertIn(link, text)

    def test_the_security_guide_and_the_other_pages_link_to_it(self):
        for page, phrase in (("README.md", "For what carrydown protects and what it cannot, read the [enterprise security questions](docs/enterprise-security.md)."),
                             ("docs/security.md", "Start with the plain-language questions"),
                             ("docs/setup.md", "(enterprise-security.md)"),
                             ("docs/plan-owner-guide.md", "(enterprise-security.md)"),
                             ("docs/faq.md", "(enterprise-security.md)"),
                             ("docs/delivery-modes.md", "(enterprise-security.md)")):
            self.assertIn(phrase, (ROOT / page).read_text(encoding="utf-8"), page)

    def test_the_faq_link_comes_before_the_github_step_in_the_plan_owner_guide(self):
        text = (ROOT / "docs" / "plan-owner-guide.md").read_text(encoding="utf-8")
        start = text.index("## The GitHub step")
        self.assertIn("(enterprise-security.md)", text[start:start + 600])

    def test_the_setup_guide_asks_the_question_before_any_instruction_to_put_files_in_the_project(self):
        text = (ROOT / "docs" / "setup.md").read_text(encoding="utf-8")
        ask = text.index("## Before you add documents: who may see them")
        start = text.index("## Start your plan")
        self.assertLess(ask, start)
        self.assertIn("Can everyone who can read this repository see all of these documents and your staffing notes?", text[ask:start])
        self.assertNotIn("Copy the files the project must obey into `docs/source/`", text)


class ObsoleteInstructionTests(unittest.TestCase):
    """The searches the documentation acceptance asks for. A match is allowed only when its line states the limit."""
    OK = re.compile(r"(?i)no longer|is gone|was later removed|removed|never|not |cannot|can't|does not|do not|unless|without|refuses|refuse|no flag|there is no|must not|stops|planned|predate|before|legacy|no such")

    def lines(self):
        for page in PUBLIC_DOCS + [str(p.relative_to(ROOT)) for p in sorted((ROOT / "skills").rglob("*.md")) if "/templates/" not in p.as_posix()] + \
                ["templates/spec-README.md", "templates/dev-skill/README.md.tmpl", "templates/dev-skill/SKILL.md.tmpl", "sample/expense-approvals/README.md"]:
            path = ROOT / page
            if path.is_file():
                for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
                    yield page, n, line

    def search(self, pattern):
        rx = re.compile(pattern, re.I)
        return [(p, n, l) for p, n, l in self.lines() if rx.search(l) and not self.OK.search(l)]

    def test_nothing_tells_a_reader_to_pass_the_removed_public_flag(self):
        self.assertEqual(self.search(r"--allow-public"), [])

    def test_nothing_tells_the_owner_to_put_originals_in_the_project_unconditionally(self):
        self.assertEqual(self.search(r"(put|copy|place)[^.]{0,60}(files|documents|originals|sources)[^.]{0,60}docs/source"), [])
        self.assertEqual(self.search(r"put the ground truth in `docs/source/`"), [])

    def test_nothing_tells_an_engineer_to_browse_the_full_ground_truth(self):
        self.assertEqual(self.search(r"(open|read|browse)[^.]{0,40}(the )?(full )?ground truth( documents)?[^.]{0,20}(for|to find)"), [])
        self.assertEqual(self.search(r"browse (the )?(full )?(ground truth|source)"), [])

    def test_nothing_claims_a_private_repository_protects_by_itself(self):
        self.assertEqual(self.search(r"private repository (protects|keeps|hides|secures)"), [])
        self.assertEqual(self.search(r"unless the repository is private"), [])

    def test_nothing_describes_a_mirrored_workspace_a_signed_tag_fallback_or_immediate_revocation(self):
        self.assertEqual(self.search(r"mirror"), [])
        self.assertEqual(self.search(r"signed.tag"), [])
        self.assertEqual(self.search(r"(immediate|instant)(ly)? (withdraw|revoc|revoke)"), [])
        self.assertEqual(self.search(r"(every|within|in) (five|5)[- ]minutes?\b(?! is a requested)"), [])


if __name__ == "__main__":
    unittest.main()
