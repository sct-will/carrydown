"""Step 0, the private workspace and the plan layouts (work package 1).

They cover the one question and its record, the workspace that scripts/workspace.py creates (folder,
permissions, files, the untracked pointer and the ignore rule), the refusal of a workspace inside the
engineering repository, the plan views (workspace and released) of validate_plan, the allowlist
projection, and the staging workflow template. No token and no network are used. The GitHub
repository commands that init prints are checked as text and never run.
Run from the repository root: python -m unittest discover -s tests -v
"""
import contextlib
import copy
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import release_gate as RG  # noqa: E402
import workspace as W  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
SAMPLE = ROOT / "sample" / "expense-approvals"
QUESTION = "Can everyone who can read this repository see all of these documents and your staffing notes?"
HAS_GIT = shutil.which("git") is not None
POSIX = os.name == "posix"


def run_main(argv):
    """Run workspace.main in this process. Returns (exit code, standard output, standard error)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = W.main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
    return code, out.getvalue(), err.getvalue()


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com"] + list(args),
                          cwd=str(cwd), capture_output=True, text=True)


def raised(error, call, *args, **kwargs):
    """The error that call raises. A call that raises nothing fails the test."""
    try:
        call(*args, **kwargs)
    except error as e:
        return e
    raise AssertionError(f"{error.__name__} was not raised")


class TempProject(unittest.TestCase):
    """A copy of the confidential fixture as an engineering repository, and a temporary HOME."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-workspace-test-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = base / "home"
        self.home.mkdir()
        self.root = base / "engineering"
        shutil.copytree(FIXTURE, self.root)
        if HAS_GIT:
            git(self.root, "init", "-q")
            git(self.root, "add", "-A")
            git(self.root, "commit", "-qm", "fixture")
        patch = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)
        self.workspace = self.home / ".carrydown" / "workspaces" / "confidential-fixture"

    def init(self, *extra, apply=True, answer="no"):
        argv = ["init", "--root", str(self.root), "--slug", "confidential-fixture", "--answer", answer] + list(extra)
        return run_main(argv + (["--apply"] if apply else []))


class InterviewTextTests(unittest.TestCase):
    def test_the_interview_holds_the_step_zero_line_and_the_question_verbatim(self):
        text = (ROOT / "skills/carrydown-ground-truth/references/interview.md").read_text(encoding="utf-8")
        self.assertIn("carrydown: interview, step 0 of 6", text)
        self.assertIn(QUESTION, text)
        self.assertEqual(text.count(QUESTION), 1)

    def test_the_follow_ups_come_only_on_no_with_their_defaults(self):
        text = (ROOT / "skills/carrydown-ground-truth/references/interview.md").read_text(encoding="utf-8")
        step0 = text[text.index("## Step 0 of 6"):text.index("## Step 1 of 6")]
        for want in ("**Yes.**", "**No.** Ask three follow-ups", "Default: all of them", "Default: the owner's GitHub login",
                     "Default: kept in the private workspace, never in the repository"):
            self.assertIn(want, step0)

    def test_the_skill_prints_the_step_zero_line_first_and_asks_before_rendering(self):
        skill = (ROOT / "skills/carrydown-ground-truth/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`carrydown: interview, step 0 of 6`", skill)
        self.assertIn(QUESTION, skill)
        self.assertLess(skill.index(QUESTION), skill.index("### 2. Render the ground truth"))
        self.assertIn("workspace.py init", skill)
        self.assertIn("never to `plan.yaml`", skill)

    def test_staffing_is_collected_after_the_workspace_and_written_to_people_yaml(self):
        text = (ROOT / "skills/carrydown-ground-truth/references/interview.md").read_text(encoding="utf-8")
        step2 = text[text.index("## Step 2 of 6"):text.index("## Step 3 of 6")]
        self.assertIn("people.yaml", step2)
        self.assertIn("only after the workspace exists", step2)
        self.assertNotIn("names stay in `plan.yaml`", step2.lower())


class PlanViewTests(unittest.TestCase):
    """validate_plan in the workspace, released and legacy views."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-planview-")
        cls.base = Path(cls.temp.name)
        cls.text = (FIXTURE / "docs/spec/plan.yaml").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def load(self, text, view=None, name="plan.yaml"):
        path = self.base / name
        path.write_text(text, encoding="utf-8")
        return L.load_plan(path, FIXTURE, view)

    def replaced(self, old, new):
        self.assertIn(old, self.text)
        return self.text.replace(old, new, 1)

    def test_the_fixture_is_a_valid_workspace_plan(self):
        plan, problems = self.load(self.text)
        self.assertEqual(problems, [])
        self.assertEqual((plan["plan_format"], plan["plan_view"], plan["_view"], plan["_modern"]), (2, "workspace", "workspace", True))
        self.assertIsNone(plan["_people_overlay"])

    def test_yes_to_the_question_with_a_restricted_source_fails_with_a_named_finding(self):
        _, problems = self.load(self.replaced("repo_audience_approved: false", "repo_audience_approved: true"))
        self.assertEqual(len([p for p in problems if "restricted" in p]), 1, problems)
        self.assertIn("sources:company-governance: classification is restricted, but project.handling.repo_audience_approved is true", problems[0])

    def test_no_to_the_question_needs_an_approver(self):
        _, problems = self.load(self.replaced('    approvers: ["example-approver"]', "    approvers: []"))
        self.assertTrue(any("approvers needs at least one GitHub login" in p for p in problems), problems)
        _, problems = self.load(self.replaced('["example-approver"]', '["not a login"]'))
        self.assertTrue(any("approvers must be a list of GitHub logins" in p for p in problems), problems)

    def test_classification_is_required_and_from_a_fixed_set(self):
        _, problems = self.load(self.replaced("    classification: repo-readers\n", ""))
        self.assertIn("sources:architecture:classification is required: repo-readers, restricted or public", problems)
        _, problems = self.load(self.replaced("classification: restricted", "classification: secret"))
        self.assertTrue(any("sources:company-governance:classification must be repo-readers, restricted or public" in p for p in problems), problems)
        _, problems = self.load(self.replaced("classification: restricted", "classification: public"))
        self.assertEqual(problems, [])

    def test_digests_in_a_workspace_plan_must_be_full_hex(self):
        _, problems = self.load(self.replaced("classification: repo-readers\n", "classification: repo-readers\n    content_sha256: abc\n"))
        self.assertIn("sources:architecture:content_sha256 must be 64 lowercase hexadecimal characters", problems)
        _, problems = self.load(self.replaced("classification: repo-readers\n", "classification: repo-readers\n    content_sha256: " + "a" * 64 + "\n    rendering_sha256: " + "b" * 64 + "\n"))
        self.assertEqual(problems, [])

    def test_handling_is_checked_without_echoing_values(self):
        for old, new, want in (
            ("    policy_version: 1\n", "    policy_version: 2\n", "policy_version must be 1"),
            ("    repo_audience_approved: false", "    repo_audience_approved: maybe", "repo_audience_approved must be true or false"),
            ("    retain_raw_inputs: keep\n", "    retain_raw_inputs: forever\n", "retain_raw_inputs must be keep or delete-after-release"),
            ("    state: migrated\n", "    state: pending\n", "project.handling.state must be legacy or migrated"),
            ("    state: migrated\n", "    state: migrated\n    surprise: 1\n", "project.handling: unknown key 'surprise'"),
            ("    state: migrated\n", "    state: migrated\n    downstream:\n      capacity_summary: yes please\n", "downstream.capacity_summary must be true or false"),
            ("    state: migrated\n", "    state: migrated\n    engineer_edits: sometimes\n", "engineer_edits must be allowed or request-only"),
        ):
            with self.subTest(want=want):
                _, problems = self.load(self.replaced(old, new))
                self.assertTrue(any(want in p for p in problems), problems)

    def test_a_migrated_plan_without_handling_is_refused(self):
        start = self.text.index("  handling:")
        end = self.text.index("\nsources:")
        _, problems = self.load(self.text[:start] + self.text[end:])
        self.assertTrue(any("project.handling is required in a migrated plan" in p for p in problems), problems)

    def test_staffing_keys_in_a_workspace_plan_are_found_by_location_and_never_by_value(self):
        for key, value in (("name", '"Secret Person"'), ("github", "secret-login"), ("skills", '["Secret skill"]'), ("preferences", '["Secret wish"]'),
                           ("assignment_rationale", '"Secret reason"'), ("days_off", "[2027-02-22]"), ("allocation", "60"), ("start", "2027-02-01")):
            with self.subTest(key=key):
                _, problems = self.load(self.replaced("  - id: idris\n    track: experience\n", f"  - id: idris\n    track: experience\n    {key}: {value}\n"))
                self.assertIn(f"people:idris:{key} is a staffing field. Keep it in people.yaml in the private workspace, not in plan.yaml", problems)
                self.assertFalse(any("Secret" in p or "secret-login" in p for p in problems), problems)

    def test_an_empty_staffing_key_is_still_found(self):
        _, problems = self.load(self.replaced("  - id: idris\n    track: experience\n", "  - id: idris\n    track: experience\n    github:\n    days_off: []\n"))
        self.assertTrue(any(p.startswith("people:idris:github ") for p in problems), problems)
        self.assertTrue(any(p.startswith("people:idris:days_off ") for p in problems), problems)

    def test_an_advisors_list_is_found_even_when_it_is_empty(self):
        for block in ('advisors:\n  - name: "Secret Advisor"\n', "advisors: []\n", "advisors:\n"):
            with self.subTest(block=block):
                _, problems = self.load(self.replaced("\nmilestones:\n", "\n" + block + "\nmilestones:\n"))
                self.assertIn("advisors is a staffing field. Keep advisors in people.yaml in the private workspace, not in plan.yaml", problems)
                self.assertFalse(any("Secret" in p for p in problems), problems)

    def test_a_migrated_person_needs_an_id_and_a_known_track_but_no_name(self):
        _, problems = self.load(self.replaced("  - id: idris\n    track: experience\n", "  - id: idris\n    track: nowhere\n"))
        self.assertTrue(any("people: idris has unknown track 'nowhere'" in p for p in problems), problems)
        _, problems = self.load(self.replaced("  - id: idris\n    track: experience\n", "  - track: experience\n"))
        self.assertTrue(any(p.startswith("people: each person needs id (entry 2)") for p in problems), problems)

    def test_the_layout_fields_are_checked(self):
        _, problems = self.load(self.replaced("plan_format: 2\n", "plan_format: 3\n"))
        self.assertTrue(any("plan_format must be 2, got 3" in p for p in problems), problems)
        _, problems = self.load(self.replaced("plan_format: 2\n", ""))
        self.assertIn("plan_format: 2 is required (a migrated plan declares its layout)", problems)
        _, problems = self.load(self.replaced("plan_view: workspace\n", ""))
        self.assertIn("plan_view is required: workspace or released", problems)
        _, problems = self.load(self.replaced("plan_view: workspace\n", "plan_view: private\n"))
        self.assertTrue(any("plan_view must be workspace or released" in p for p in problems), problems)

    def test_a_plan_is_refused_in_the_other_view_with_the_view_mismatch_code(self):
        _, problems = self.load(self.text, view="released")
        self.assertIn("plan_view is workspace, but this check needs the released view (schema-view-mismatch)", problems)
        released = L.project_released_plan(self.load(self.text)[0])
        path = self.base / "released.yaml"
        import plan_repair
        path.write_text(plan_repair.dump(released) + "\n", encoding="utf-8")
        _, problems = L.load_plan(path, FIXTURE, "workspace")
        self.assertIn("plan_view is released, but this check needs the workspace view (schema-view-mismatch)", problems)
        _, problems = L.load_plan(path, FIXTURE, "released")
        self.assertEqual(problems, [])
        _, problems = L.load_plan(path, FIXTURE)   # no view asked: the plan's own view
        self.assertEqual(problems, [])

    def test_a_legacy_plan_is_refused_when_a_view_is_required(self):
        plan = self.legacy_plan()
        self.assertFalse(plan["_modern"])
        problems = L.validate_plan(plan, "released")
        self.assertTrue(any("(schema-view-mismatch)" in p for p in problems), problems)
        problems = L.validate_plan(plan, "workspace")
        self.assertTrue(any("(schema-view-mismatch)" in p for p in problems), problems)
        raised(ValueError, lambda: L.validate_plan(plan, "private"))

    def legacy_plan(self, extra_people=""):
        """The fixture in the layout before the confidential work: no layout fields, no handling, staffing in the plan."""
        text = self.text.replace("plan_format: 2\nplan_view: workspace\n", "")
        start, end = text.index("  handling:"), text.index("\nsources:")
        text = text[:start] + text[end:]
        text = text.replace("    classification: repo-readers\n", "").replace("    classification: restricted\n", "")
        start, end = text.index("people:"), text.index("\nmilestones:\n")
        text = text[:start] + '''people:
  - id: tamsin
    name: "Tamsin Hale"
    github: ""
    track: workflow
    allocation: 100
    start: 2027-02-01
    days_off: [2027-02-22]
  - id: idris
    name: "Idris Okoye"
    github: ""
    track: experience
    allocation: 60
    start: 2027-02-01
    days_off: [2027-03-08]
''' + extra_people + "\nadvisors:\n  - name: \"Noor Castellan\"\n" + text[end:]
        plan, problems = self.load(text, name="legacy.yaml")
        self.assertEqual(problems, [])
        return plan

    def test_a_legacy_plan_keeps_the_legacy_rules(self):
        plan = self.legacy_plan()
        self.assertEqual(L.validate_plan(plan), [])
        self.assertEqual(plan["people"][1]["allocation"], 60)
        self.assertTrue(L.staffing_loaded(plan))
        self.assertIn("Tamsin Hale", plan["_banned_names"])
        self.assertEqual(L.downstream_flags(plan), {"assignees": True, "capacity_summary": True})
        broken = copy.deepcopy(plan)
        broken["people"][0]["allocation"] = 0
        self.assertIn("people: tamsin allocation must be a whole percent from 1 to 100, got 0", L.validate_plan(broken))
        nameless = copy.deepcopy(plan)
        del nameless["people"][0]["name"]
        self.assertEqual([p for p in L.validate_plan(nameless) if "needs id" in p], ["people: each person needs id and name (entry 1)"])

    def test_an_enrolled_repository_cannot_be_legacy(self):
        project = self.base / "enrolled"
        shutil.copytree(FIXTURE, project)
        plan = self.legacy_plan()
        text = (project / "docs/spec/plan.yaml").read_text(encoding="utf-8")
        legacy_text = self.base / "legacy.yaml"
        (project / "docs/spec/plan.yaml").write_text(legacy_text.read_text(encoding="utf-8"), encoding="utf-8")
        _, problems = L.load_plan(project / "docs/spec/plan.yaml", project)
        self.assertEqual(problems, [])
        pointer = project / ".carrydown"
        pointer.mkdir()
        (pointer / "release-policy.yaml").write_text("format: 1\ntooling_repository: acme/tooling\nenrollment_id: " + "a" * 64 + "\n", encoding="utf-8")
        _, problems = L.load_plan(project / "docs/spec/plan.yaml", project)
        self.assertTrue(any("(enrolled-project-missing-handling)" in p for p in problems), problems)
        (project / "docs/spec/plan.yaml").write_text(text, encoding="utf-8")   # a migrated plan in an enrolled repository is fine
        _, problems = L.load_plan(project / "docs/spec/plan.yaml", project)
        self.assertEqual(problems, [])
        del plan

    def test_a_key_that_starts_with_an_underscore_is_reserved(self):
        err = raised(L.PlanError, lambda: self.load(self.text + "_people_overlay: elsewhere\n"))
        self.assertIn("reserved", err.msg)


class ReleasedViewTests(unittest.TestCase):
    """The released plan: what it rejects and what it accepts."""

    @classmethod
    def setUpClass(cls):
        cls.plan, problems = L.load_plan(FIXTURE / "docs/spec/plan.yaml", FIXTURE)
        assert problems == [], problems
        cls.released = L.project_released_plan(cls.plan)

    def check(self, data):
        """Problems of a released plan given as data, as the verifier would see them."""
        return L.released_plan_problems(data)

    def test_the_projection_validates_as_released(self):
        self.assertEqual(self.check(self.released), [])
        self.assertEqual((self.released["plan_format"], self.released["plan_view"]), (2, "released"))

    def test_each_removed_people_key_is_rejected_by_location_without_its_value(self):
        for key in ("name", "github", "skills", "preferences", "assignment_rationale", "days_off", "allocation", "start"):
            with self.subTest(key=key):
                data = copy.deepcopy(self.released)
                data["people"][0][key] = "Secret Value" if key != "days_off" else ["Secret Value"]
                problems = self.check(data)
                self.assertIn(f"people:tamsin:{key} is a staffing field. Keep it in people.yaml in the private workspace, not in plan.yaml", problems)
                self.assertFalse(any("Secret" in p for p in problems), problems)

    def test_a_top_level_advisors_field_is_rejected(self):
        data = copy.deepcopy(self.released)
        data["advisors"] = [{"name": "Secret Advisor"}]
        problems = self.check(data)
        self.assertTrue(any(p.startswith("advisors is a staffing field") for p in problems), problems)
        self.assertFalse(any("Secret" in p for p in problems), problems)

    def test_private_source_fields_are_rejected_and_the_display_name_is_not(self):
        for key, value in (("path", "docs/ground-truth/x.md"), ("source_path", "ground-truth/x.md"), ("classification", "repo-readers"),
                           ("content_sha256", "a" * 64), ("rendering_sha256", "b" * 64)):
            with self.subTest(key=key):
                data = copy.deepcopy(self.released)
                data["sources"][0][key] = value
                self.assertIn(f"sources:architecture:{key} is not allowed in a released plan. It stays in the private workspace plan", self.check(data))
        data = copy.deepcopy(self.released)
        data["sources"][0]["name"] = "Skills matrix and allocation guide"
        self.assertEqual(self.check(data), [])

    def test_a_released_plan_needs_no_original_no_rendering_and_no_ground_truth_path(self):
        data = copy.deepcopy(self.released)
        self.assertNotIn("ground_truth", data["project"])
        self.assertFalse(any("path" in s for s in data["sources"]))
        self.assertEqual(self.check(data), [])
        plan, _ = L.plan_from_data(copy.deepcopy(data), "released", None, "released")
        self.assertNotIn("ground_truth", plan["project"])

    def test_a_released_source_needs_a_version(self):
        data = copy.deepcopy(self.released)
        del data["sources"][0]["version"]
        self.assertIn("sources:architecture:version is required in a released plan", self.check(data))

    def test_handling_in_a_released_plan_holds_the_answer_and_not_the_approvers(self):
        self.assertEqual(self.released["project"]["handling"], {"policy_version": 1, "repo_audience_approved": False, "state": "migrated"})
        data = copy.deepcopy(self.released)
        data["project"]["handling"]["approvers"] = ["secret-approver"]
        data["project"]["handling"]["retain_raw_inputs"] = "keep"
        problems = self.check(data)
        self.assertIn("project.handling.approvers is not allowed in a released plan. It stays in the private workspace plan", problems)
        self.assertIn("project.handling.retain_raw_inputs is not allowed in a released plan. It stays in the private workspace plan", problems)

    def test_banned_names_and_restricted_flags_do_not_survive_in_a_released_plan(self):
        data = copy.deepcopy(self.released)
        data["banned"] = {"names": ["Secret Person"]}
        self.assertTrue(any(p.startswith("banned:names is not allowed") for p in self.check(data)))
        data = copy.deepcopy(self.released)
        data["items"][0]["restricted"] = True
        data["items"][0]["restricted_summary"] = "Secret summary"
        problems = self.check(data)
        self.assertIn("items:1:restricted is not allowed in a released plan. Restricted items are omitted from it", problems)
        self.assertIn("items:1:restricted_summary is not allowed in a released plan", problems)
        self.assertFalse(any("Secret" in p for p in problems), problems)

    def test_prose_about_skills_and_allocation_is_not_a_schema_failure(self):
        data = copy.deepcopy(self.released)
        data["tracks"][0]["order_rationale"] = "The Experience engineer is allocated 60 percent, so the skills of the Workflow track carry the days off."
        data["conventions"]["extra"] = ["Document allocation, skills and days_off in the runbook."]
        data["sources"][0]["name"] = "Name, skills and allocation policy"
        data["project"]["name"] = "Skills and allocation tracker"
        self.assertEqual(self.check(data), [])

    def test_a_valid_release_with_a_board_field_called_name_is_not_a_schema_failure(self):
        data = copy.deepcopy(self.released)
        data["tracks"][0]["name"] = "Board field called name"   # not a person, so not a staffing location
        self.assertEqual(self.check(data), [])


class ProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, _ = L.load_plan(FIXTURE / "docs/spec/plan.yaml", FIXTURE)

    def test_the_projection_is_a_new_object_and_the_input_is_unchanged(self):
        before = copy.deepcopy(self.plan)
        out = L.project_released_plan(self.plan)
        self.assertEqual(self.plan, before)
        out["people"][0]["id"] = "changed"
        out["items"][0]["label"] = "changed"
        out["sources"][0]["name"] = "changed"
        out["tracks"][0]["label"] = "changed"
        self.assertEqual(self.plan, before)

    def test_only_allowlisted_keys_are_projected(self):
        plan = copy.deepcopy(self.plan)
        plan["people"][0]["notes"] = "kept private because it is not on the allowlist"
        plan["sources"][0]["use"] = "private description"
        plan["project"]["secret_setting"] = "x"
        plan["items"][0]["internal_note"] = "x"
        plan["banned"]["names"] = ["Secret Person"]
        out = L.project_released_plan(plan)
        self.assertEqual(out["people"][0], {"id": "tamsin", "track": "workflow"})
        self.assertEqual(out["sources"][0], {"id": "architecture", "name": "Architecture document", "version": "0.3"})
        self.assertNotIn("secret_setting", out["project"])
        self.assertNotIn("internal_note", out["items"][0])
        self.assertNotIn("names", out.get("banned", {}))
        self.assertEqual(L.released_plan_problems(out), [])

    def test_the_staffing_merged_view_is_refused(self):
        merged, problems = L.load_plan_with_people(FIXTURE / "docs/spec/plan.yaml", FIXTURE, people_path=FIXTURE / "people.yaml")
        self.assertEqual(problems, [])
        self.assertTrue(merged["_staffing_merged"])
        err = raised(L.PlanViewError, lambda: L.project_released_plan(merged))
        self.assertEqual(err.code, "schema-view-mismatch")
        self.assertNotIn("Tamsin", str(err))

    def test_a_legacy_plan_and_a_released_plan_are_refused(self):
        legacy = copy.deepcopy(self.plan)
        legacy.pop("plan_format"), legacy.pop("plan_view"), legacy["project"].pop("handling")
        legacy["_modern"], legacy["_view"] = False, "legacy"
        raised(L.PlanViewError, lambda: L.project_released_plan(legacy))
        released = L.project_released_plan(self.plan)
        raised(L.PlanViewError, lambda: L.project_released_plan(released))

    def test_restricted_items_are_omitted_and_the_hook_is_called_with_their_ids(self):
        plan = copy.deepcopy(self.plan)
        item = next(i for i in plan["items"] if i["id"] == 11)
        item["restricted"] = True
        item["restricted_summary"] = "Owner summary"
        seen = {}

        def hook(workspace_plan, projected, omitted):
            seen["omitted"] = omitted
            return projected
        with mock.patch.object(L, "_restricted_hook", hook):
            out = L.project_released_plan(plan)
        self.assertEqual(seen["omitted"], [11])
        self.assertEqual([i["id"] for i in out["items"]], [i["id"] for i in self.plan["items"] if i["id"] != 11])
        self.assertNotIn("restricted", {k for i in out["items"] for k in i})
        # nothing depends on item 11 in the fixture, so the omission leaves a valid released plan
        self.assertEqual(L.released_plan_problems(out), [])

    def test_an_item_that_depends_on_an_omitted_one_gets_an_external_item_with_the_owners_summary(self):
        plan = copy.deepcopy(self.plan)
        item = next(i for i in plan["items"] if i["id"] == 3)
        item["restricted"] = True
        item["restricted_summary"] = "Owner summary"
        out = L.project_released_plan(plan)
        self.assertEqual(L.released_plan_problems(out), [])
        self.assertIn({"id": 3, "label": "Owner summary"}, out["external"]["items"])
        dependents = [i for i in plan["items"] if 3 in i["depends"]]
        self.assertTrue(dependents)
        for d in dependents:
            released = next(i for i in out["items"] if i["id"] == d["id"])
            self.assertNotIn(3, released["depends"])
            self.assertTrue(released["external_input"].endswith("Owner summary"), released["external_input"])

    def test_the_projection_dumps_and_reloads_to_the_same_released_plan(self):
        import plan_repair
        out = L.project_released_plan(self.plan)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.yaml"
            path.write_text(plan_repair.dump(out) + "\n", encoding="utf-8")
            plan, problems = L.load_plan(path, None, "released")
        self.assertEqual(problems, [])
        again = L.project_released_plan.__wrapped__ if hasattr(L.project_released_plan, "__wrapped__") else None
        self.assertIsNone(again)
        self.assertEqual([i["id"] for i in plan["items"]], [i["id"] for i in self.plan["items"]])
        self.assertNotIn("Hale", str(out))


@unittest.skipUnless(HAS_GIT, "git is not installed")
class WorkspaceInitTests(TempProject):
    def test_a_dry_run_writes_nothing_and_says_so(self):
        code, out, err = self.init(apply=False)
        self.assertEqual(code, 0, out + err)
        self.assertIn("DRY RUN (nothing will be written)", out)
        self.assertIn("Dry run complete. Add --apply", out)
        self.assertFalse(self.workspace.exists())
        self.assertFalse((self.root / ".carrydown").exists())
        self.assertEqual(git(self.root, "status", "--porcelain").stdout, "")

    def test_apply_creates_the_workspace_with_its_files(self):
        code, out, err = self.init()
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"carrydown: private workspace ready at {self.workspace}", out)
        for name in ("workspace.yaml", "retention.yaml", "people.yaml", ".git"):
            self.assertTrue((self.workspace / name).exists(), name)
        for sub in W.SUBFOLDERS:
            self.assertTrue((self.workspace / sub).is_dir(), sub)
        data = L.load_file(self.workspace / "workspace.yaml")
        self.assertEqual((data["format"], data["slug"], data["state"], data["policy_version"]), (1, "confidential-fixture", "drafting", 1))
        self.assertEqual(os.path.realpath(data["engineering_repo"]["path"]), os.path.realpath(str(self.root)))
        self.assertEqual(data["staging_repository"], "sct-will/confidential-fixture-releases")
        retention = L.load_file(self.workspace / "retention.yaml")
        self.assertEqual((retention["raw_inputs"], retention["history"]), ("keep", "keep"))
        self.assertIn("does not remove them from any backup, remote or copy made earlier", retention["limits"])
        doc, problems = L.load_people_file(self.workspace / "people.yaml")
        self.assertEqual((doc, problems), ({"people": [], "advisors": []}, []))

    @unittest.skipUnless(POSIX, "the mode check is for POSIX systems; Windows reads an access control list back")
    def test_the_folder_is_owner_only_and_the_mode_is_read_back(self):
        self.init()
        self.assertEqual(os.stat(self.workspace).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(self.workspace.parent).st_mode & 0o777, 0o700)   # created by init, so owner only too
        self.assertIsNone(W.posix_permission_problem(self.workspace))
        os.chmod(self.workspace, 0o755)
        self.assertIn("mode 0755, not 0700", W.posix_permission_problem(self.workspace))

    @unittest.skipUnless(POSIX, "the mode check is for POSIX systems")
    def test_init_stops_and_cleans_up_when_the_mode_cannot_be_verified(self):
        with mock.patch.object(W, "restrict_folder", lambda path: os.chmod(str(path), 0o755)):
            code, out, err = self.init()
        self.assertEqual(code, 2)
        self.assertIn("permissions could not be verified", err)
        self.assertFalse(self.workspace.exists())
        self.assertFalse((self.root / ".carrydown").exists())

    def test_the_pointer_is_written_untracked_and_git_shows_nothing_new(self):
        self.init()
        pointer = (self.root / ".carrydown" / "local.yaml").read_text(encoding="utf-8")
        self.assertIn("workspace:", pointer)
        self.assertEqual(L.workspace_root(self.root), (self.workspace.resolve(), None))
        ignore = (self.root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".carrydown/local.yaml", ignore)
        self.assertEqual(ignore[:2], ["__pycache__/", "*.pyc"])   # the existing lines are kept
        status = git(self.root, "status", "--porcelain", "--untracked-files=all").stdout.splitlines()
        self.assertEqual(status, [" M .gitignore"])
        self.assertEqual(git(self.root, "check-ignore", ".carrydown/local.yaml").returncode, 0)

    def test_the_ignore_line_is_not_added_twice(self):
        self.init()
        self.init()
        lines = (self.root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines.count(".carrydown/local.yaml"), 1)

    def test_a_project_without_a_gitignore_gets_one(self):
        (self.root / ".gitignore").unlink()
        git(self.root, "rm", "-q", "--cached", ".gitignore")
        self.init()
        self.assertEqual((self.root / ".gitignore").read_text(encoding="utf-8"), ".carrydown/local.yaml\n")

    def test_running_init_again_changes_nothing(self):
        self.init()
        before = {p.name: p.read_bytes() for p in (self.workspace / "workspace.yaml", self.workspace / "retention.yaml")}
        (self.workspace / "people.yaml").write_text("people:\n  - id: tamsin\n    name: \"Fictional Person\"\nadvisors: []\n", encoding="utf-8")
        code, out, err = self.init()
        self.assertEqual(code, 0, out + err)
        self.assertEqual({p.name: p.read_bytes() for p in (self.workspace / "workspace.yaml", self.workspace / "retention.yaml")}, before)
        self.assertIn("Fictional Person", (self.workspace / "people.yaml").read_text(encoding="utf-8"))

    def test_a_workspace_inside_the_engineering_repository_is_refused(self):
        for inside in (self.root / "private", self.root / "docs" / "spec" / "workspace", self.root):
            with self.subTest(path=str(inside.relative_to(self.root))):
                code, out, err = self.init("--workspace", str(inside))
                self.assertEqual(code, 2)
                self.assertIn("workspace-inside-repository", err)
                self.assertFalse((self.root / ".carrydown").exists())
        self.assertFalse((self.root / "private").exists())

    def test_a_home_folder_inside_the_repository_is_refused_too(self):
        inner = self.root / "fake-home"
        inner.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(inner), "USERPROFILE": str(inner)}):
            code, out, err = self.init()
        self.assertEqual(code, 2)
        self.assertIn("workspace-inside-repository", err)
        self.assertFalse((inner / ".carrydown").exists())

    @unittest.skipUnless(POSIX, "symbolic links")
    def test_a_link_that_leads_into_the_repository_is_refused(self):
        link = Path(self.temp.name) / "link-to-repo"
        link.symlink_to(self.root, target_is_directory=True)
        code, out, err = self.init("--workspace", str(link / "hidden"))
        self.assertEqual(code, 2)
        self.assertIn("workspace-inside-repository", err)

    def test_a_bad_slug_is_refused(self):
        for slug in ("../evil", "Upper", "a b", "", "x" * 80, "-lead"):
            with self.subTest(slug=slug):
                code, out, err = run_main(["init", "--root", str(self.root), "--slug", slug, "--apply"])
                self.assertEqual(code, 2)
                self.assertIn("--slug", err)
        self.assertFalse((self.home / ".carrydown").exists())

    def test_the_slug_defaults_to_the_plan_and_the_answer_to_the_plan(self):
        code, out, err = run_main(["init", "--root", str(self.root), "--apply"])
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.home / ".carrydown" / "workspaces" / "expense-approvals" / "workspace.yaml").is_file())
        self.assertIn("gh repo create", out)   # the plan answers no, so the staging commands are printed

    def test_a_folder_that_is_not_a_workspace_is_never_used(self):
        self.workspace.mkdir(parents=True)
        (self.workspace / "stranger.txt").write_text("not mine", encoding="utf-8")
        code, out, err = self.init()
        self.assertEqual(code, 2)
        self.assertIn("not empty, and it is not a carrydown workspace", err)
        self.assertEqual([p.name for p in self.workspace.iterdir()], ["stranger.txt"])
        self.assertFalse((self.root / ".carrydown").exists())

    def test_a_workspace_of_another_project_is_never_taken_over(self):
        self.init()
        other = Path(self.temp.name) / "other"
        shutil.copytree(FIXTURE, other)
        code, out, err = run_main(["init", "--root", str(other), "--slug", "confidential-fixture", "--apply"])
        self.assertEqual(code, 2)
        self.assertIn("already a workspace for another project", err)
        self.assertFalse((other / ".carrydown").exists())

    def test_a_pointer_to_another_workspace_is_never_replaced(self):
        self.init()
        code, out, err = run_main(["init", "--root", str(self.root), "--slug", "second", "--apply"])
        self.assertEqual(code, 2)
        self.assertIn("already points to another workspace", err)
        self.assertEqual(L.workspace_root(self.root), (self.workspace.resolve(), None))

    def test_the_no_answer_prints_the_staging_commands_and_runs_none_of_them(self):
        real = subprocess.run
        calls = []

        def spy(cmd, *args, **kwargs):
            calls.append(list(cmd))
            return real(cmd, *args, **kwargs)
        with mock.patch.object(subprocess, "run", spy):
            code, out, err = self.init()
        self.assertEqual(code, 0, out + err)
        for want in ("gh repo create sct-will/confidential-fixture-releases --private", "open-release-request.yml",
                     "default_workflow_permissions=read", "can_approve_pull_request_reviews=true", "Carrydown does not run these commands"):
            self.assertIn(want, out)
        self.assertEqual([c[0] for c in calls if c[0] in ("gh", "curl")], [])
        self.assertTrue(all(c[0] == "git" for c in calls), calls)   # only git init and the remote lookup ran
        self.assertFalse(any("push" in c or "clone" in c or "create" in c for c in calls))

    def test_the_yes_answer_prints_no_staging_commands(self):
        code, out, err = self.init(answer="yes")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("gh repo create", out)
        self.assertEqual(len(out.strip().splitlines()), 1)   # one line: the workspace is ready
        self.assertNotIn("staging_repository", (self.workspace / "workspace.yaml").read_text(encoding="utf-8"))

    def test_the_staging_repository_can_be_named(self):
        code, out, err = self.init("--staging-repository", "acme/releases")
        self.assertEqual(code, 0, out + err)
        self.assertIn("gh repo create acme/releases --private", out)
        self.assertEqual(L.load_file(self.workspace / "workspace.yaml")["staging_repository"], "acme/releases")
        code, out, err = self.init("--staging-repository", "no-slash")
        self.assertEqual(code, 2)

    def test_retention_follows_the_flag(self):
        self.init("--retain", "delete-after-release")
        self.assertEqual(L.load_file(self.workspace / "retention.yaml")["raw_inputs"], "delete-after-release")

    def test_a_remote_with_a_token_in_it_is_stored_without_the_token(self):
        git(self.root, "remote", "add", "origin", "https://user:ghp_" + "A" * 36 + "@github.com/acme/app.git")
        self.init()
        text = (self.workspace / "workspace.yaml").read_text(encoding="utf-8")
        self.assertNotIn("ghp_", text)
        self.assertNotIn("user:", text)
        self.assertIn("https://github.com/acme/app.git", text)
        self.assertEqual(W.clean_remote("git@github.com:acme/app.git"), "git@github.com:acme/app.git")
        self.assertEqual(W.clean_remote("https://x-access-token:abc@github.com/a/b"), "https://github.com/a/b")
        self.assertEqual(W.remote_owner("git@github.com:acme/app.git"), "acme")
        self.assertEqual(W.remote_owner("https://github.com/acme/app"), "acme")

    def test_each_write_into_the_engineering_repository_asks_the_gate_first(self):
        asked = []
        real = RG.check

        def spy(write_class, artifact_path, content_digest, destination, root, **kwargs):
            asked.append((write_class, artifact_path, len(content_digest)))
            return real(write_class, artifact_path, content_digest, destination, root, **kwargs)
        with mock.patch.object(RG, "check", spy):
            self.init()
        self.assertEqual(asked, [("draft", ".carrydown/local.yaml", 64), ("draft", ".gitignore", 64)])

    def test_a_refusal_by_the_gate_stops_the_write(self):
        deny = RG.Decision(False, "deny", "drafting-is-private", None)
        with mock.patch.object(RG, "check", lambda *a, **k: deny):
            code, out, err = self.init()
        self.assertEqual(code, 2)
        self.assertIn("drafting-is-private", err)
        self.assertFalse((self.root / ".carrydown" / "local.yaml").exists())
        self.assertEqual(git(self.root, "status", "--porcelain").stdout, "")


@unittest.skipUnless(HAS_GIT, "git is not installed")
class WorkspaceStatusAndDoctorTests(TempProject):
    def rows(self):
        return {name: (level, detail) for level, name, detail in W.doctor_rows(self.root)}

    def test_status_without_a_workspace_says_so_with_a_fixed_code(self):
        code, out, err = run_main(["status", "--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("workspace: unavailable (workspace-unavailable)", out)
        self.assertIn("workspace.py init --root . --slug <slug> --apply", out)

    def test_status_prints_paths_state_and_counts_but_no_names(self):
        self.init()
        shutil.copyfile(FIXTURE / "people.yaml", self.workspace / "people.yaml")
        code, out, err = run_main(["status", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        for want in (f"workspace: {self.workspace}", "state: drafting", "permissions: owner only", "people.yaml: 2 people, 1 advisors",
                     "staging repository: sct-will/confidential-fixture-releases", "releases: 0, requests: 0, events: 0"):
            self.assertIn(want, out)
        for secret in ("Tamsin", "Idris", "Noor", "Hale"):
            self.assertNotIn(secret, out)

    def test_doctor_is_clean_after_init(self):
        self.init()
        code, out, err = run_main(["doctor", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        rows = self.rows()
        for name in ("pointer", "path separation", "permissions", "workspace.yaml", "retention.yaml", "git", "plan schema"):
            self.assertEqual(rows[name][0], "ok", (name, rows[name]))
        self.assertIn("offline", out.splitlines()[0])
        self.assertIn("plan_format 2, workspace view, handling migrated; valid", rows["plan schema"][1])

    def test_doctor_without_a_workspace_fails_on_the_pointer_and_the_ignore_rule(self):
        rows = self.rows()
        self.assertEqual(rows["pointer"][0], "FAIL")
        self.assertIn("workspace-unavailable", rows["pointer"][1])
        code, out, err = run_main(["doctor", "--root", str(self.root)])
        self.assertEqual(code, 1)

    def test_doctor_fails_when_the_pointer_is_not_ignored_or_is_tracked(self):
        self.init()
        (self.root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        pointer_rule = [r for r in W.doctor_rows(self.root) if r[1] == "ignore rule" and r[2].startswith(".carrydown/local.yaml")]
        self.assertEqual([r[0] for r in pointer_rule], ["FAIL"])
        git(self.root, "add", "-f", ".carrydown/local.yaml")
        self.assertEqual(self.rows()["tracked pointer"][0], "FAIL")

    @unittest.skipUnless(POSIX, "mode bits")
    def test_doctor_fails_when_the_folder_is_opened_to_others(self):
        self.init()
        os.chmod(self.workspace, 0o755)
        level, detail = self.rows()["permissions"]
        self.assertEqual(level, "FAIL")
        self.assertIn("0755", detail)

    def test_doctor_reports_a_workspace_inside_the_repository_as_a_path_failure(self):
        inside = self.root / "inside"
        inside.mkdir()
        (self.root / ".carrydown").mkdir()
        (self.root / ".carrydown" / "local.yaml").write_text(f"workspace: {inside}\n", encoding="utf-8")
        rows = self.rows()
        self.assertEqual(rows["path separation"][0], "FAIL")
        self.assertIn("workspace-inside-repository", rows["pointer"][1])

    def test_doctor_counts_plan_problems_without_printing_the_plan(self):
        self.init()
        plan = self.root / "docs/spec/plan.yaml"
        plan.write_text(plan.read_text(encoding="utf-8").replace("  - id: idris\n    track: experience\n", '  - id: idris\n    name: "Secret Person"\n    track: experience\n'), encoding="utf-8")
        level, detail = self.rows()["plan schema"]
        self.assertEqual(level, "FAIL")
        self.assertIn("1 problem(s)", detail)
        code, out, err = run_main(["doctor", "--root", str(self.root)])
        self.assertNotIn("Secret", out + err)

    def test_doctor_checks_people_yaml_by_count(self):
        self.init()
        shutil.copyfile(FIXTURE / "people.yaml", self.workspace / "people.yaml")
        self.assertEqual(self.rows()["people.yaml"], ("ok", "2 people, 1 advisors"))
        (self.workspace / "people.yaml").write_text("people:\n  - name: \"Secret Person\"\n", encoding="utf-8")
        level, detail = self.rows()["people.yaml"]
        self.assertEqual(level, "FAIL")
        self.assertNotIn("Secret", detail)

    def test_doctor_warns_about_the_ignore_rules_the_scaffold_adds(self):
        self.init()
        rows = [r for r in W.doctor_rows(self.root) if r[1] == "ignore rule"]
        self.assertEqual([r[0] for r in rows], ["ok", "warn", "warn", "warn"])


class WindowsPermissionTextTests(unittest.TestCase):
    """The Windows branch reads an access control list back with icacls. The parser is plain text work and runs everywhere."""

    PATH = "C:\\Users\\me\\.carrydown\\workspaces\\project"
    ONLY_ME = PATH + " DESKTOP-1\\me:(OI)(CI)(F)\n\nSuccessfully processed 1 files; Failed processing 0 files\n"
    OPEN = (PATH + " NT AUTHORITY\\SYSTEM:(I)(OI)(CI)(F)\n"
            "                                  BUILTIN\\Administrators:(I)(OI)(CI)(F)\n"
            "                                  DESKTOP-1\\me:(I)(OI)(CI)(F)\n"
            "                                  NT AUTHORITY\\Authenticated Users:(I)(OI)(CI)(M)\n\n"
            "Successfully processed 1 files; Failed processing 0 files\n")

    def test_the_principals_are_read_from_the_first_and_later_lines(self):
        self.assertEqual(W.parse_icacls(self.ONLY_ME, self.PATH), ["DESKTOP-1\\me"])
        self.assertEqual(W.parse_icacls(self.OPEN, self.PATH),
                         ["NT AUTHORITY\\SYSTEM", "BUILTIN\\Administrators", "DESKTOP-1\\me", "NT AUTHORITY\\Authenticated Users"])
        self.assertEqual(W.parse_icacls("", self.PATH), [])

    def test_only_the_current_user_passes(self):
        self.assertIsNone(W.windows_acl_problem(["DESKTOP-1\\me"], "DESKTOP-1\\me"))
        self.assertIsNone(W.windows_acl_problem(["desktop-1\\ME"], "DESKTOP-1\\me"))
        self.assertIn("3 other principal(s)", W.windows_acl_problem(W.parse_icacls(self.OPEN, self.PATH), "DESKTOP-1\\me"))
        self.assertIn("could not be read back", W.windows_acl_problem([], "DESKTOP-1\\me"))
        self.assertIn("1 other principal", W.windows_acl_problem(["DESKTOP-1\\me", "Everyone"], "DESKTOP-1\\me"))

    def test_the_windows_branch_runs_icacls_to_set_and_to_read_back(self):
        calls = []

        def fake(cmd, *args, **kwargs):
            calls.append(list(cmd))
            if cmd[0] == "whoami":
                return subprocess.CompletedProcess(cmd, 0, "DESKTOP-1\\me\n", "")
            if cmd[:2] == ["icacls", self.PATH] and len(cmd) == 2:
                return subprocess.CompletedProcess(cmd, 0, self.ONLY_ME, "")
            return subprocess.CompletedProcess(cmd, 0, "Successfully processed 1 files; Failed processing 0 files\n", "")
        with mock.patch.object(W.os, "name", "nt"), mock.patch.object(subprocess, "run", fake):
            self.assertIsNone(W.restrict_folder(self.PATH))
            self.assertIsNone(W.permission_problem(self.PATH))
        self.assertIn(["icacls", self.PATH, "/inheritance:r", "/grant:r", "DESKTOP-1\\me:(OI)(CI)F"], calls)
        self.assertIn(["icacls", self.PATH], calls)

    def test_an_open_list_is_reported_by_the_windows_branch(self):
        def fake(cmd, *args, **kwargs):
            if cmd[0] == "whoami":
                return subprocess.CompletedProcess(cmd, 0, "DESKTOP-1\\me\n", "")
            return subprocess.CompletedProcess(cmd, 0, self.OPEN, "")
        with mock.patch.object(W.os, "name", "nt"), mock.patch.object(subprocess, "run", fake):
            self.assertIn("other principal(s) can open the workspace", W.permission_problem(self.PATH))

    def test_the_help_documents_the_windows_twin(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts/workspace.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("icacls", run.stdout)
        self.assertIn("%USERPROFILE%", run.stdout)
        self.assertIn("(OI)(CI)F", run.stdout)


class GitignoreHelperTests(unittest.TestCase):
    def test_an_entry_is_found_only_as_a_whole_line(self):
        self.assertTrue(W.gitignore_has("a\n.carrydown/local.yaml\n", ".carrydown/local.yaml"))
        self.assertTrue(W.gitignore_has("/.carrydown/local.yaml  \n", ".carrydown/local.yaml"))
        self.assertFalse(W.gitignore_has("# .carrydown/local.yaml\n", ".carrydown/local.yaml"))
        self.assertFalse(W.gitignore_has(".carrydown/local.yaml.bak\n", ".carrydown/local.yaml"))
        self.assertEqual(W.with_gitignore_entry("a", "b"), "a\nb\n")
        self.assertEqual(W.with_gitignore_entry("", "b"), "b\n")


class StagingWorkflowTemplateTests(unittest.TestCase):
    PATH = ROOT / "templates" / "staging" / "open-release-request.yml"

    @classmethod
    def setUpClass(cls):
        cls.text = cls.PATH.read_text(encoding="utf-8")
        cls.doc = L.loads(cls.text)

    def test_it_runs_on_a_schedule_and_on_dispatch_only(self):
        self.assertEqual(set(self.doc["on"]), {"schedule", "workflow_dispatch"})
        self.assertEqual(self.doc["on"]["schedule"][0]["cron"], "*/5 * * * *")

    def test_the_token_can_read_contents_and_write_pull_requests_and_nothing_else(self):
        self.assertEqual(self.doc["permissions"], {"contents": "read", "pull-requests": "write"})

    def test_it_never_checks_out_or_executes_candidate_content(self):
        for forbidden in ("actions/checkout", "uses:", "pull_request_target", "git checkout", "git clone", "bash -c", "eval ", "source ", "npm ", "pip "):
            self.assertNotIn(forbidden, self.text)
        self.assertNotIn("pull_request", self.doc["on"])
        self.assertNotIn("push", self.doc["on"])

    def test_branch_names_are_data_and_are_matched_before_use(self):
        self.assertIn("matching-refs/heads/request/", self.text)
        self.assertIn("matching-refs/heads/state/", self.text)
        self.assertIn("^(request|state)/[0-9a-f]{64}$", self.text)
        self.assertLess(self.text.index("^(request|state)/[0-9a-f]{64}$"), self.text.index("--method POST"))

    def test_no_expression_is_interpolated_into_the_script(self):
        script = self.text[self.text.index("run: |"):]
        self.assertNotIn("${{", script)
        self.assertIn("GH_TOKEN: ${{ github.token }}", self.text)

    def test_it_opens_a_pull_request_only_for_a_branch_that_has_none(self):
        self.assertIn("-f state=all", self.text)
        self.assertLess(self.text.index('existing=$(gh api'), self.text.index("--method POST"))
        self.assertIn('if [[ "${existing}" != "0" ]]; then', self.text)

    def test_the_workflow_is_installed_with_the_ground_truth_skill(self):
        copy_path = ROOT / "skills" / "carrydown-ground-truth" / "templates" / "staging" / "open-release-request.yml"
        self.assertEqual(copy_path.read_bytes(), self.PATH.read_bytes())

    def test_the_printed_commands_name_the_installed_template(self):
        lines = "\n".join(W.staging_commands("acme/releases"))
        self.assertIn(str(L.templates_dir() / "staging" / "open-release-request.yml"), lines)
        self.assertIn("gh repo create acme/releases --private", lines)
        self.assertNotIn("OWNER/NAME", lines)
        self.assertIn("OWNER/NAME", "\n".join(W.staging_commands(None)))


if __name__ == "__main__":
    unittest.main()
