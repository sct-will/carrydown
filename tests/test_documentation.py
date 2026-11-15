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


PUBLIC_DOCS = ["README.md", "SECURITY.md", "docs/setup.md", "docs/install-options.md", "docs/organization-setup.md", "docs/security.md", "docs/faq.md", "docs/inputs.md", "docs/method.md",
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
        for link in ("(security.md)", "(delivery-modes.md)", "(organization-setup.md)", "(organization-setup.md#acceptance-on-real-github)"):
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


class InterviewNumberingTests(unittest.TestCase):
    def test_the_guide_numbers_every_question_with_the_steps_of_the_skill(self):
        skill = (ROOT / "skills" / "carrydown-ground-truth" / "references" / "interview.md").read_text(encoding="utf-8")
        steps = [(int(n), int(of)) for n, of in re.findall(r"(?m)^## Step (\d+) of (\d+)\. ", skill)]
        last = steps[-1][1]
        self.assertEqual(steps, [(n, last) for n in range(last + 1)])
        guide = (ROOT / "docs" / "plan-owner-guide.md").read_text(encoding="utf-8")
        section = guide[guide.index("## What the agent asks you"):]
        section = section[:section.index("\n## ", 3)]
        self.assertIn(f"`carrydown: interview, step N of {last}`", section)
        rows = [m.group(1) for m in re.finditer(r"(?m)^\| (\d+(?:, optional)?) \|", section)]
        self.assertEqual(sorted({int(r.split(",")[0]) for r in rows}), list(range(last + 1)), rows)
        self.assertEqual(len(rows), len(re.findall(r"(?m)^\| (?!Step |---)", section)), "a question row has no step number")


class MaintenanceNoticeTests(unittest.TestCase):
    """The notice, the completion lines and the action phrases have one source, templates/maintenance-notice.md.
    The copies in the two skills and in the specification README template must match it word for word, the two
    routing tables must be present, and the owner-facing skill text must stay clean."""
    CANON = ROOT / "templates" / "maintenance-notice.md"
    GT = ROOT / "skills" / "carrydown-ground-truth" / "SKILL.md"
    PUB = ROOT / "skills" / "carrydown-plan-to-github" / "SKILL.md"
    README_TEMPLATE = ROOT / "templates" / "spec-README.md"

    def canon_block(self, heading):
        """The quoted lines (the contiguous run of lines starting with '>') after the heading."""
        text = self.CANON.read_text(encoding="utf-8")
        after = text.split("## " + heading + "\n", 1)[1]
        lines = []
        for line in after.split("\n"):
            if line.startswith(">"):
                lines.append(line)
            elif lines:
                break
        self.assertGreater(len(lines), 0, heading)
        return "\n".join(lines)

    def test_the_canonical_template_holds_the_action_phrases_and_the_blocks_exactly(self):
        text = self.CANON.read_text(encoding="utf-8")
        for phrase in ('| Create a plan | "Set up a project plan from these documents." |',
                       '| Publish the approved plan | "Put the plan on GitHub." |',
                       '| Update an existing project | "This changed: [describe the change or provide revised documents]." |',
                       '| Start a work item | "Work on WI-03." |',
                       '| Raise a specification problem | "This specification seems wrong because [explanation]." |',
                       '> "Use carrydown-ground-truth to update this existing project."'):
            self.assertIn(phrase, text)
        self.assertEqual(self.canon_block("The notice"), "\n".join([
            "> **Important: when the project changes**",
            ">",
            "> If requirements, architecture or company rules change significantly, or an engineer finds a specification problem, say:",
            ">",
            '> **"This changed: [describe the change or provide revised documents]."**',
            ">",
            "> Your agent will review the existing project, preserve engineer corrections and show proposed updates for approval."]))
        self.assertIn("single source", text.split("-->", 1)[0])

    def test_the_notice_matches_the_canonical_template_in_the_readme_template_and_both_skills(self):
        notice = self.canon_block("The notice")
        for path in (self.README_TEMPLATE, self.GT, self.PUB):
            self.assertIn(notice, path.read_text(encoding="utf-8"), path.name)

    def test_the_completion_lines_match_the_canonical_template(self):
        self.assertIn(self.canon_block("Completion line after planning"), self.GT.read_text(encoding="utf-8"))
        self.assertIn(self.canon_block("Completion line after publication"), self.PUB.read_text(encoding="utf-8"))

    def test_the_notice_comes_before_the_routine_counts_and_links(self):
        gt = self.GT.read_text(encoding="utf-8")
        self.assertLess(gt.index("Your plan is ready for review."), gt.index("Important: when the project changes"))
        pub = self.PUB.read_text(encoding="utf-8")
        step = pub.split("### 7. After", 1)[1].split("### 8.", 1)[0]
        self.assertLess(step.index("Your approved project has been published."), step.index("Important: when the project changes"))
        self.assertLess(step.index("Important: when the project changes"), step.index("Then show the user the counts and the project link."))

    def test_the_ground_truth_skill_has_the_whole_routing_table_and_the_two_sentences(self):
        text = self.GT.read_text(encoding="utf-8")
        self.assertIn("## Route by project state", text)
        self.assertLess(text.index("## Rules that never bend"), text.index("## Route by project state"))
        for state in ("No plan", "Unapproved draft", "Existing project with changed sources or a correction", "Unfinished update",
                      "Accepted drafts awaiting release", "Approved release awaiting publication", "Observable inputs unchanged",
                      "Ambiguous project or baseline"):
            self.assertRegex(text, r"(?m)^\| " + re.escape(state) + r" \| ", state)
        self.assertIn("python3 <skill>/scripts/reconcile.py status --root .", text)
        self.assertIn("Routing works after this skill activates.", text)
        self.assertIn("does not replace the deterministic checks", text)
        for phrase in ("This changed:", "Is this project up to date?", "What's next?", "Resume the project update", "update this existing project"):
            self.assertIn(phrase, text.split("\n", 4)[2], phrase)
        self.assertIn("## The update path", text)
        self.assertIn("Never scaffold a replacement project", text)

    def test_the_publishing_skill_has_the_routing_rows_that_concern_it(self):
        text = self.PUB.read_text(encoding="utf-8")
        self.assertIn("## Route by project state", text)
        for state in ("Accepted drafts awaiting release", "Approved release awaiting publication", "Resume existing publication"):
            self.assertRegex(text, r"(?m)^\| " + re.escape(state), state)
        self.assertIn("Resume the project update.", text)
        self.assertIn("`project.clarification`", text)
        self.assertIn("`channel: mention` with `login`", text)
        self.assertIn("`channel: issue` with `issue`", text)
        self.assertIn("Do not say \"up to date\" while any publication step is pending.", text)
        self.assertIn("references/verification.md", text)

    def skill_pages(self):
        pages = [ROOT / "skills" / s / "SKILL.md" for s in ("carrydown-ground-truth", "carrydown-plan-to-github")]
        for s in ("carrydown-ground-truth", "carrydown-plan-to-github"):
            pages += sorted((ROOT / "skills" / s / "references").glob("*.md"))
        pages += [self.CANON, ROOT / "templates" / "reconcile-review.md", self.README_TEMPLATE]
        return pages

    def test_no_skill_page_or_notice_template_has_an_em_dash_or_an_en_dash(self):
        for page in self.skill_pages():
            text = page.read_text(encoding="utf-8")
            for dash in (chr(0x2014), chr(0x2013)):
                self.assertNotIn(dash, text, page.name)

    def test_the_proposal_placeholder_appears_only_in_code(self):
        for page in (self.GT, ROOT / "skills" / "carrydown-ground-truth" / "references" / "updates.md",
                     ROOT / "templates" / "reconcile-review.md", self.CANON):
            text = page.read_text(encoding="utf-8")
            prose = re.sub(r"(?s)```.*?```", "", text)          # fenced blocks
            prose = re.sub(r"`[^`\n]*`", "", prose)               # code spans
            self.assertNotIn("CHANGE_ID", prose, page.name)

    def test_the_ground_truth_skill_never_names_the_publishing_client_a_release_command_or_a_token(self):
        text = self.GT.read_text(encoding="utf-8")
        refs = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "skills" / "carrydown-ground-truth" / "references").glob("updates.md"))
        for body in (text, refs):
            self.assertNotIn("github_client.py", body)
            self.assertNotIn("release.py release", body)
        self.assertNotRegex(text, r"(?i)\btokens?\b")          # the update reference may say "approximate token count" of a model

    def test_the_owner_facing_pages_hold_no_script_command_for_the_agent_only_interface_outside_the_skill(self):
        for page in (self.CANON, ROOT / "templates" / "reconcile-review.md", self.README_TEMPLATE):
            self.assertNotIn("reconcile.py", page.read_text(encoding="utf-8"), page.name)

    def test_the_review_template_leads_with_the_counts_and_keeps_the_record_last(self):
        text = (ROOT / "templates" / "reconcile-review.md").read_text(encoding="utf-8")
        order = [text.index("## " + h) for h in ("Lead sentence", "Proposed updates", "Reviewed and unchanged", "Decisions needed",
                                                  "Disclosure effects", "Next action", "Technical record")]
        self.assertEqual(order, sorted(order))
        self.assertIn("Two specifications need updates. One completed item needs a follow-up decision. One engineer correction conflicts with the revised source.", text)
        # the automatic no-impact records of formatting-only blocks are shown to the owner, not hidden in the record
        unchanged = text[text.index("## Reviewed and unchanged"):text.index("## Decisions needed")]
        self.assertIn("only their formatting changed", unchanged)

    def test_the_update_reference_holds_the_fixed_sentences(self):
        text = (ROOT / "skills" / "carrydown-ground-truth" / "references" / "updates.md").read_text(encoding="utf-8")
        self.assertIn("> A previous complete source checkpoint is unavailable. Review the current sources to establish one. "
                      "Earlier uncited changes cannot be assessed automatically.", text)
        for heading in ("## Independent review prompt", "## The states to report", "## Engineer clarification requests"):
            self.assertIn(heading, text)
        self.assertIn("The reviewer must see the original changed blocks", text)
        self.assertIn("Have any source decisions, requirements, constraints or implementation findings changed since the last review?", text)
        self.assertIn("Resume the project update.", text)
        for state in ("Draft reconciliation", "Release", "Engineering repository update", "Issue updates", "Board updates", "Engineer action"):
            self.assertRegex(text, r"(?m)^\| " + state + r" \|", state)
        self.assertIn("approximate", text)

    def test_the_six_update_states_have_one_set_of_names_on_every_page(self):
        """The owner guide, the recovery guide and both skills' references name the six states the same way."""
        names = ("draft reconciliation", "release", "engineering repository update", "issue updates", "board updates", "engineer action")
        pages = {
            "plan-owner-guide.md": ROOT / "docs" / "plan-owner-guide.md",
            "recovery.md": ROOT / "docs" / "recovery.md",
            "updates.md": ROOT / "skills" / "carrydown-ground-truth" / "references" / "updates.md",
            "verification.md": ROOT / "skills" / "carrydown-plan-to-github" / "references" / "verification.md",
        }
        for label, page in pages.items():
            text = page.read_text(encoding="utf-8").lower()
            for name in names:
                with self.subTest(page=label, state=name):
                    self.assertIn(name, text)
            for old in ("draft changes accepted", "| draft accepted |", "| repository update pending |", "| issues pending |", "| board pending |"):
                with self.subTest(page=label, old=old):
                    self.assertNotIn(old, text)

    def test_the_readme_and_the_guide_say_how_to_hand_over_a_document_and_that_one_approval_does_not_publish(self):
        for page in (ROOT / "README.md", ROOT / "docs" / "plan-owner-guide.md"):
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=page.name):
                self.assertIn("This changed: the revised architecture document is at ~/Documents/architecture.docx.", text)
                self.assertIn("you do not need to move it into the project", text.replace("You do not", "you do not"))
                self.assertRegex(text, r"accepts the (changes to the )?drafts\. It (publishes nothing|does not publish anything)\.")
                self.assertIn("Nothing is pushed or sent to them.", text)
                self.assertIn("next run of the check for a work item shows the approved delta", text)

    def test_the_verification_and_maintenance_pages_carry_the_states_and_the_old_material_caveat(self):
        pub = ROOT / "skills" / "carrydown-plan-to-github" / "references"
        verification = (pub / "verification.md").read_text(encoding="utf-8")
        maintenance = (pub / "engineers-skill-maintenance.md").read_text(encoding="utf-8")
        self.assertIn("## States to report after an update", verification)
        self.assertIn("Do not say \"up to date\" while a required publication step is pending.", verification)
        self.assertIn("Engineers can still hold old material", verification)
        self.assertIn("Engineers can still hold old material", maintenance)
        self.assertIn("An approved update regenerates the engineers' skill through the existing release.", maintenance)


    def test_the_agent_runs_the_commit_and_push_check_and_asks_one_approval(self):
        pub = (ROOT / "skills" / "carrydown-plan-to-github" / "SKILL.md").read_text(encoding="utf-8")
        step = pub.split("### 4. Preflight", 1)[1].split("### 5.", 1)[0]
        check = step.split("**Dry run.**", 1)[0]
        self.assertIn("Run these checks yourself, from the project root. They only read, so they need no approval:", check)
        for command in ("git status --porcelain docs", "git fetch origin <branch>", "git log origin/<branch>..HEAD --oneline -- docs"):
            self.assertIn(command, check)
        self.assertIn("Tell the owner what you found in one plain sentence each, not the commands", check)
        self.assertIn("ask one approval in the chat. It is a separate question, after the disclosure and external-write lines of step 3", check)
        self.assertIn("Do nothing before a clear yes.", check)
        self.assertLess(check.index("Do nothing before a clear yes."), check.index("On the yes, commit only the released files"))
        self.assertIn("Never force a push", check)
        for old in ("Ask the user to run these commands", "Do not run them yourself", "unless the user asks for that command in this chat",
                    "ask the user to run the check again"):
            with self.subTest(old=old):
                self.assertNotIn(old, pub)

    def test_the_token_prompt_stays_with_the_owner(self):
        pub = (ROOT / "skills" / "carrydown-plan-to-github" / "SKILL.md").read_text(encoding="utf-8")
        step = pub.split("### 2. Token", 1)[1].split("### 3.", 1)[0]
        self.assertIn("Print this command for the user to run in their own terminal. Do not run it yourself.", step)
        self.assertIn("python3 <skill>/scripts/github_token.py --repo owner/name", step)
        self.assertIn("come back to the chat", step)

    def test_the_release_completion_line_and_the_owner_pages_describe_the_agent_commit(self):
        release = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")
        self.assertIn("commit and push them only after the owner approves that in the chat", release)
        self.assertIn("into your working tree. Next, check whether they are committed and pushed, and commit and push them only after the owner approves that in the chat.", release)
        self.assertNotIn("then commit and push as you usually do", release)
        self.assertIn("}. Next, check whether it is committed and pushed, and commit and push it only after the owner approves that in the chat.", release)
        self.assertNotIn("Commit it as you usually do.", release)
        self.assertNotIn("leaves commit and push to you", release)
        self.assertIn("from the snapshot, and the agent commits and pushes them only after you approve that in the chat.", release)
        guide = (ROOT / "docs" / "plan-owner-guide.md").read_text(encoding="utf-8")
        for old in ("You commit and push as you do today", "Commit and push them to the intended branch.", "Export and commit the new release first."):
            with self.subTest(old=old):
                self.assertNotIn(old, guide)
        self.assertNotIn("Commit and push the export.", (ROOT / "docs" / "recovery.md").read_text(encoding="utf-8"))
        self.assertNotIn("and you commit and push them", (ROOT / "README.md").read_text(encoding="utf-8"))


class OwnerJourneyTests(unittest.TestCase):
    """The owner's first screen: the short path at the top of the setup guide, the split pages and the first words."""

    def page(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def test_the_setup_guide_opens_with_the_short_path_and_the_start_phrase(self):
        lines = self.page("docs/setup.md").split("\n")
        self.assertEqual(lines[2], "## The short path")
        start = next(n for n, line in enumerate(lines, 1) if "Set up a project plan from these documents." in line)
        self.assertLess(start, 40)
        path = "\n".join(lines[:lines.index("## Words you will meet")])
        order = [path.index(s) for s in ("**What you need.**", "**Where you type the installer.**", "**How you know it worked.**",
                                         "**What to say to start.**", "**What to have ready.**")]
        self.assertEqual(order, sorted(order))
        for phrase in ("Node.js 22.20 or later", "install-options.md#manual-install-without-nodejs", "npx skills add sct-will/carrydown",
                       "`carrydown: interview, step 0 of 6`", "plan-owner-guide.md#what-the-agent-asks-you",
                       "#before-you-add-documents-who-may-see-them", "the skill checks Python and Git"):
            self.assertIn(phrase, path)

    def test_the_setup_guide_defines_the_first_words_in_one_sentence_each(self):
        text = self.page("docs/setup.md")
        words = text.split("## Words you will meet\n", 1)[1].split("\n## ", 1)[0]
        for term in ("Agent skill", "Node.js and npx", "Ground truth", "Track", "Milestone and demonstration", "Work item", "Dry run"):
            self.assertRegex(words, r"(?m)^- \*\*" + re.escape(term) + r"\.\*\* ", term)
        self.assertLess(len(words.split()), 200)

    def test_the_moved_sections_are_their_own_pages_and_setup_points_to_them(self):
        setup = self.page("docs/setup.md")
        self.assertNotIn("### Choose where to install", setup)
        self.assertNotIn("### Step 1: create the tooling repository", setup)
        for heading, target in (("## Other installation options", "(install-options.md)"),
                                ("## Organization setup for private drafting", "(organization-setup.md)")):
            pointer = setup.split(heading + "\n", 1)[1].split("\n## ", 1)[0]
            self.assertIn(target, pointer)
            self.assertEqual(len([line for line in pointer.split("\n") if line.strip()]), 1)
        options = self.page("docs/install-options.md")
        for heading in ("## Choose where to install", "## Manual install, without Node.js"):
            self.assertIn(heading, options)
        org = self.page("docs/organization-setup.md")
        for heading in ("## Step 7: the owner's release commands", "## Limits to state to your reviewers", "## Acceptance on real GitHub"):
            self.assertIn(heading, org)
        self.assertNotIn("It does not run them.", org)

    def test_the_readme_names_node_the_first_words_and_the_sample_preview(self):
        text = self.page("README.md")
        start = text.split("## Start here\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Node.js 22.20 or later for the standard installer", start)
        self.assertIn("(docs/install-options.md#manual-install-without-nodejs)", start)
        self.assertIn("They check both when they start", start)
        for word in ("The ground truth is", "a skill is", "a dry run previews"):
            self.assertIn(word, start)
        self.assertIn("(docs/plan-owner-guide.md#glossary)", start)
        sample = text.split("## Explore the sample\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("(sample/expense-approvals/README.md#run-it)", sample)
        self.assertIn("read-only preview", sample)
        self.assertNotIn("```", sample)

    def test_the_guide_has_dry_run_in_the_glossary_and_short_interview_paragraphs(self):
        text = self.page("docs/plan-owner-guide.md")
        self.assertRegex(text.split("## Glossary", 1)[1], r"(?m)^- \*\*Dry run\.\*\* ")
        section = text[text.index("## What the agent asks you"):]
        section = section[:section.index("\n## ", 3)]
        self.assertIn("(setup.md#words-you-will-meet)", section)
        self.assertIn("an approver can approve a submitted report from their inbox", section)
        prose = [p for p in section.split("\n\n") if p and not p.startswith(("|", "#"))]
        self.assertLess(max(len(p.split()) for p in prose), 100)

    def test_the_recovery_table_has_the_agent_run_the_retries(self):
        text = self.page("docs/recovery.md")
        table = text.split("## Resume an interrupted release", 1)[1].split("\n## ", 1)[0]
        self.assertNotRegex(table, r"\| Run `")
        self.assertNotIn("| Run the same command again.", table)
        self.assertEqual(table.count("The agent runs"), 5)

    def test_a_forgotten_resume_phrase_and_a_drafted_source_request_have_a_next_step(self):
        recovery = self.page("docs/recovery.md")
        resume = recovery.split("## Resume a project update\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("If you do not remember that phrase, or whether an update stopped, ask \"What's next?\"", resume)
        guide = self.page("docs/plan-owner-guide.md")
        self.assertIn("marked \"Nothing has been sent.\", and you send it to the author yourself.", guide)


if __name__ == "__main__":
    unittest.main()
