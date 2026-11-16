"""Tests for the pull request declaration check and the continuous integration files that carry it.

Specification section 11, pull request validation, and the scenarios "Code-only pull request" and
"Unknown format or malformed schema" of section 16.1. Every test reads or copies the committed sample in a
temporary folder. No token, no network and no model. Run from the repository root:
python3 -m unittest discover -s tests -v
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "mock"))
from sample_tree import copy_sample, SAMPLE  # noqa: E402

CHECK = ROOT / "scripts" / "check_specs.py"
SCAFFOLD = ROOT / "scripts" / "scaffold_spec.py"
WORKFLOW = ROOT / "templates" / "check-specs-workflow.yml"
TEMPLATE = ROOT / "templates" / "pull-request-template.md"
NEXT_ACTION = ("this pull request declares no work item. Add a line starting Work items: with the ids it carries out, "
               "for example Work items: WI-01, or a line starting Outside the plan: with the reason for this maintenance change")
LIMIT = "A declaration proves what was declared and checked, not that the code meets every requirement."


def run(script, *args, home=None):
    env = None
    if home is not None:

        env = dict(os.environ, HOME=str(home))
    r = subprocess.run([sys.executable, str(script)] + [str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    return r.returncode, r.stdout, r.stderr


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-pr-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def body(self, text, data=None):
        path = self.base / "body.txt"
        path.write_bytes(data if data is not None else text.encode("utf-8"))
        return path

    def declare(self, text, *extra, root=SAMPLE):
        code, out, err = run(CHECK, "--root", root, "--pull-request-body", self.body(text), *extra)
        return code, out, err


class DeclarationTests(Base):
    def test_valid_ids_pass_on_the_sample(self):
        code, out, err = self.declare("Work items: WI-03, WI-04\n")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(out.rstrip().endswith("carrydown: pull request declares 2 work item(s), 0 finding(s)"), out)
        self.assertIn(LIMIT, out)

    def test_ids_in_a_list_item_bold_or_lower_case_are_read(self):
        code, out, _ = self.declare("- **Work items:** `wi-03` and WI-04.\n")
        self.assertEqual(code, 0, out)
        self.assertIn("declares 2 work item(s)", out)

    def test_an_unknown_id_fails(self):
        code, out, _ = self.declare("Work items: WI-99\n")
        self.assertEqual(code, 1)
        self.assertIn("WI-99 is not in the released plan", out)
        self.assertIn("declares 1 work item(s), 1 finding(s)", out)

    def test_an_external_item_fails(self):
        code, out, _ = self.declare("Work items: WI-05\n")
        self.assertEqual(code, 1)
        self.assertIn("WI-05 is not a work item of this plan", out)

    def test_a_restricted_item_of_the_working_plan_fails(self):
        project = copy_sample(self.base / "proj")
        plan = project / "docs" / "spec" / "plan.yaml"
        text = plan.read_text(encoding="utf-8")
        match = re.search(r"^  - id: 3\n", text, re.M)
        self.assertIsNotNone(match)
        plan.write_text(text[:match.end()] + "    restricted: true\n" + text[match.end():], encoding="utf-8")
        code, out, err = self.declare("Work items: WI-03\n", root=project)
        self.assertEqual(code, 1, out + err)
        self.assertIn("WI-03 is not a work item of this plan", out)

    def test_a_declared_item_must_pass_the_released_checks(self):
        project = copy_sample(self.base / "proj", working=False)
        for path in (project / "docs" / "context").glob("wi-03.bundle.json"):
            path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        code, out, _ = self.declare("Work items: WI-03, WI-04\n", root=project)
        self.assertEqual(code, 1)
        self.assertIn("WI-03 ", out)
        self.assertNotIn("WI-04 approved", out)
        self.assertIn("declares 2 work item(s)", out)
        code, out, _ = self.declare("Work items: WI-04\n", root=project)
        self.assertEqual(code, 0, out)

    def test_outside_the_plan_passes_and_is_labeled(self):
        code, out, _ = self.declare("Outside the plan: bump a test dependency\n")
        self.assertEqual(code, 0, out)
        self.assertIn("outside the plan (reviewed maintenance path): bump a test dependency", out)
        self.assertIn("declares 0 work item(s), 0 finding(s)", out)

    def test_outside_the_plan_needs_a_reason(self):
        code, out, _ = self.declare("Outside the plan:   \nOutside the plan: --\n")
        self.assertEqual(code, 1)
        self.assertIn(NEXT_ACTION, out)

    def test_both_declarations_are_accepted(self):
        code, out, _ = self.declare("Work items: WI-03\nOutside the plan: a typo in the readme\n")
        self.assertEqual(code, 0, out)
        self.assertIn("reviewed maintenance path", out)
        self.assertIn("declares 1 work item(s)", out)

    def test_no_declaration_fails_with_the_next_action(self):
        for text in ("", "Just a change.\n", "Work items:\nOutside the plan:\n"):
            code, out, _ = self.declare(text)
            self.assertEqual(code, 1, text)
            self.assertIn(NEXT_ACTION, out)
            self.assertTrue(out.rstrip().endswith("declares 0 work item(s), 1 finding(s)"), out)

    def test_template_comments_and_fenced_examples_declare_nothing(self):
        code, out, _ = self.declare("<!-- Work items: WI-03 -->\n```\nWork items: WI-04\n```\nOutside the plan: <!-- a reason -->\n")
        self.assertEqual(code, 1)
        self.assertIn(NEXT_ACTION, out)

    def test_the_branch_is_a_hint_and_never_a_pass(self):
        code, out, _ = self.declare("A change with no declaration.\n", "--branch", "feature/wi-03-login")
        self.assertEqual(code, 1)
        self.assertIn("hint only: the branch name mentions WI-03", out)
        self.assertIn("this is not a pass", out)
        self.assertIn("declares 0 work item(s), 1 finding(s)", out)

    def test_a_branch_adds_nothing_when_the_body_declares(self):
        code, out, _ = self.declare("Work items: WI-04\n", "--branch", "feature/wi-03-login")
        self.assertEqual(code, 0, out)
        self.assertNotIn("hint", out)

    def test_a_malformed_id_is_a_finding_and_not_a_crash(self):
        for token in ("XX-03", "WI3", "WI-", "3", "WI-03x", "WI--3"):
            code, out, err = self.declare(f"Work items: {token}\n")
            self.assertEqual(code, 1, token + out + err)
            self.assertIn("which is not a work item id", out)
            self.assertNotIn("Traceback", out + err)

    def test_a_malformed_id_does_not_hide_a_valid_one(self):
        code, out, _ = self.declare("Work items: WI-03, XX-04\n")
        self.assertEqual(code, 1)
        self.assertIn('"XX-04"', out)
        self.assertIn("declares 1 work item(s), 1 finding(s)", out)

    def test_a_body_that_is_not_utf8_exits_2_with_a_plain_message(self):
        code, out, err = run(CHECK, "--root", SAMPLE, "--pull-request-body", self.body("", data=b"Work items: WI-03\n\xff\xfe\n"))
        self.assertEqual(code, 2)
        self.assertIn("is not UTF-8 text", err)
        self.assertNotIn("Traceback", out + err)
        self.assertNotIn("declares", out)

    def test_a_missing_or_folder_body_exits_2(self):
        for target in (self.base / "missing.txt", self.base):
            code, out, err = run(CHECK, "--root", SAMPLE, "--pull-request-body", target)
            self.assertEqual(code, 2, err)
            self.assertNotIn("Traceback", err)

    def test_a_json_error_for_a_bad_body_is_one_object(self):
        code, out, _ = run(CHECK, "--root", SAMPLE, "--json", "--pull-request-body", self.body("", data=b"\xff"))
        self.assertEqual(code, 2)
        self.assertIn("UTF-8", json.loads(out)["error"])

    def test_the_other_lines_of_the_body_are_never_echoed(self):
        marker = "MARKER-7f3a-private-line"
        text = (f"{marker} at the top\nWork items: WI-03\nWork items: XX-9\n"
                f"Outside the plan: reason\n{marker} at the end\n::set-output name=x::{marker}\n")
        code, out, err = self.declare(text, "--branch", marker)
        self.assertEqual(code, 1)
        self.assertNotIn(marker, out + err)
        self.assertFalse([line for line in out.splitlines() if line.startswith("::")])

    def test_the_outside_reason_is_one_clean_line(self):
        code, out, _ = self.declare("Outside the plan: ::error:: \x1b[31mred\x1b[0m " + "long " * 80 + "\n")
        self.assertEqual(code, 0)
        reasons = [line for line in out.splitlines() if line.startswith("outside the plan")]
        self.assertEqual(len(reasons), 1)
        self.assertNotIn("\x1b", out)
        self.assertLessEqual(len(reasons[0]), 260)

    def test_json_and_quiet_output(self):
        code, out, _ = self.declare("Work items: WI-03\n", "--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["work_items"], ["WI-03"])
        self.assertEqual(data["findings"], [])
        code, out, _ = self.declare("Work items: WI-03\n", "--quiet")
        self.assertEqual(out.strip(), "carrydown: pull request declares 1 work item(s), 0 finding(s)")

    def test_help_says_what_a_declaration_proves(self):
        code, out, _ = run(CHECK, "--help")
        self.assertEqual(code, 0)
        flat = " ".join(out.split())
        self.assertIn("A declaration proves what was declared and checked, not that the code meets every requirement", flat)

    def test_branch_and_report_are_refused_where_they_make_no_sense(self):
        code, _, err = run(CHECK, "--root", SAMPLE, "--branch", "x")
        self.assertEqual(code, 2)
        code, _, err = run(CHECK, "--root", SAMPLE, "--report", "--pull-request-body", self.body("Work items: WI-03"))
        self.assertEqual(code, 2)

    def test_the_declaration_check_writes_nothing(self):
        before = sorted(p.relative_to(SAMPLE).as_posix() for p in SAMPLE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        self.declare("Work items: WI-03\n")
        after = sorted(p.relative_to(SAMPLE).as_posix() for p in SAMPLE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        self.assertEqual(before, after)


class WorkflowTemplateTests(Base):
    def rendered(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import carrydown_lib as L
        return L.fill(WORKFLOW.read_text(encoding="utf-8"), {"spec_dir": "docs/spec", "ground_truth_dir": "docs/ground-truth", "branch": "main"})

    def block(self, text, name):
        """The lines of the top-level key under `on:` called name, up to the next key of the same depth."""
        lines = text.split("\n")
        start = next(i for i, line in enumerate(lines) if line == f"  {name}:")
        out = []
        for line in lines[start + 1:]:
            if re.match(r"^  \S", line) or re.match(r"^\S", line):
                break
            out.append(line)
        return "\n".join(out)

    def test_a_pull_request_runs_whatever_it_changes(self):
        text = self.rendered()
        self.assertEqual(self.block(text, "pull_request").strip(), "")
        self.assertIn("paths:", self.block(text, "push"))
        self.assertIn("pull_request:\n  push:", text)

    def test_the_merge_group_block_is_a_comment(self):
        text = self.rendered()
        self.assertIn("  # merge_group:", text)
        self.assertIn("merge queue", text)
        self.assertIn("GitHub workflow event reference", text)
        self.assertFalse([line for line in text.splitlines() if line.startswith("  merge_group:")])

    def test_permissions_stay_read_only_and_no_placeholder_is_left(self):
        text = self.rendered()
        self.assertIn("permissions:\n  contents: read\n", text)
        self.assertNotRegex(text, r"\{\{(spec_dir|ground_truth_dir|branch)\}\}")
        perms = text.split("permissions:", 1)[1].split("jobs:", 1)[0]
        self.assertNotIn("write", perms)

    def test_the_body_goes_through_an_environment_variable_and_is_never_interpolated_into_the_command(self):
        text = self.rendered()
        for line in text.splitlines():
            if "${{" in line and not line.strip().startswith("#"):
                self.assertRegex(line, r"^\s+[A-Z_]+: \$\{\{ [^}]+ \}\}$", line)
        self.assertIn("PR_BODY: ${{ github.event.pull_request.body }}", text)
        self.assertIn("printf '%s' \"$PR_BODY\"", text)
        self.assertIn("--pull-request-body \"$PR_BODY_FILE\"", text)

    def test_only_pinned_first_party_actions_are_used(self):
        for line in self.rendered().splitlines():
            m = re.match(r"\s+- uses: (\S+)", line)
            if m:
                self.assertRegex(m.group(1), r"^actions/[a-z-]+@[0-9a-f]{40}$")

    def test_the_governed_paths_filter_is_a_shell_step_with_no_third_party_action(self):
        text = self.rendered()
        self.assertIn("git diff --name-only", text)
        self.assertNotIn("paths-filter", text)
        self.assertIn("steps.scope.outputs.governed == 'true'", text)


class ScaffoldCiTests(Base):
    count = 0

    def project(self, **kw):
        ScaffoldCiTests.count += 1
        project = copy_sample(self.base / f"proj{ScaffoldCiTests.count}", **kw)
        for rel in (".github", "tools"):
            shutil.rmtree(str(project / rel), ignore_errors=True)
        return project

    def test_the_dry_run_lists_the_workflow_the_template_and_the_checker_copy(self):
        project = self.project()
        code, out, err = run(SCAFFOLD, "--root", project, "--ci", "--allow-no-git", home=self.base)
        self.assertEqual(code, 0, out + err)
        self.assertIn("would create: .github/workflows/check-specs.yml", out)
        self.assertIn("would create: .github/pull_request_template.md", out)
        self.assertIn("would create: tools/carrydown/check_specs.py", out)
        self.assertIn("three parts", out)
        self.assertFalse((project / ".github").exists())
        self.assertFalse((project / "tools").exists())

    def test_apply_writes_all_three_into_a_copy_of_the_sample(self):
        project = self.project()
        code, out, err = run(SCAFFOLD, "--root", project, "--ci", "--apply", "--allow-no-git", home=self.base)
        self.assertEqual(code, 0, out + err)
        template = (project / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
        self.assertEqual(template, TEMPLATE.read_text(encoding="utf-8"))
        workflow = (project / ".github" / "workflows" / "check-specs.yml").read_text(encoding="utf-8")
        self.assertIn("  pull_request:\n  push:", workflow)
        self.assertIn("  # merge_group:", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertTrue((project / "tools" / "carrydown" / "check_specs.py").is_file())
        code, out, _ = run(project / "tools" / "carrydown" / "check_specs.py", "--root", project, "--pull-request-body",
                           self.body("Outside the plan: a test change\n"), "--view", "workspace")
        self.assertEqual(code, 0, out)

    def test_an_existing_pull_request_template_is_never_overwritten(self):
        for force in ([], ["--force"]):
            project = self.project()
            (project / ".github").mkdir()
            mine = "My own template.\n"
            (project / ".github" / "pull_request_template.md").write_text(mine, encoding="utf-8")
            code, out, err = run(SCAFFOLD, "--root", project, "--ci", "--apply", "--allow-no-git", *force, home=self.base)
            self.assertEqual(code, 0, out + err)
            self.assertEqual((project / ".github" / "pull_request_template.md").read_text(encoding="utf-8"), mine)
            self.assertIn("already exists and was kept", out)
            self.assertTrue((project / ".github" / "workflows" / "check-specs.yml").is_file())

    def test_a_template_in_another_place_github_reads_is_kept_too(self):
        project = self.project()
        (project / "docs").mkdir(exist_ok=True)
        (project / "docs" / "pull_request_template.md").write_text("Mine.\n", encoding="utf-8")
        code, out, err = run(SCAFFOLD, "--root", project, "--ci", "--apply", "--allow-no-git", home=self.base)
        self.assertEqual(code, 0, out + err)
        self.assertFalse((project / ".github" / "pull_request_template.md").exists())
        self.assertIn("already exists and was kept", out)

    def test_the_project_template_has_the_two_lines_and_three_boxes(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^Work items:$")
        self.assertRegex(text, r"(?m)^Outside the plan:$")
        self.assertEqual(len(re.findall(r"(?m)^- \[ \] ", text)), 3)
        self.assertIn('"Decisions recorded"', text)
        self.assertNotIn(chr(0x2014), text)
        self.assertNotIn(chr(0x2013), text)

    def test_an_untouched_template_declares_nothing(self):
        code, out, _ = self.declare_file(TEMPLATE)
        self.assertEqual(code, 1)
        self.assertIn(NEXT_ACTION, out)

    def declare_file(self, path):
        code, out, err = run(CHECK, "--root", SAMPLE, "--pull-request-body", path)
        return code, out, err


if __name__ == "__main__":
    unittest.main()
