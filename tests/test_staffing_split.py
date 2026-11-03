"""The staffing split (work package 2): names and personal facts leave the committed plan, and the
owner's capacity, dates and names checks still work from people.yaml in the private workspace.

They cover the stored plan (ids and tracks only), the overlay merge, the checks that are skipped
without it, the log hygiene of the overlay messages, banned names, the capacity summary flag, the
assignee rule, the repair fallback and the released staffing structures. No token and no network
are used. Run from the repository root: python -m unittest discover -s tests -v
"""
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
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "mock"))
from sample_tree import copy_sample, WORKING_PLAN  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import check_specs as CS  # noqa: E402
import generate_dev_skill as GD  # noqa: E402
import github_repair as GR  # noqa: E402
import github_sync as GS  # noqa: E402
import plan_repair as PR  # noqa: E402
import workspace as W  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
PLAN = WORKING_PLAN
PEOPLE = SAMPLE / "people.yaml"
NOTE = "people overlay not loaded: capacity, dates and names not checked"
REMOVED = ("name", "github", "skills", "preferences", "assignment_rationale", "days_off", "allocation", "start")
HAS_GIT = shutil.which("git") is not None


def check(args, cwd=ROOT):
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_specs.py")] + [str(a) for a in args],
                         cwd=str(cwd), capture_output=True, text=True, timeout=120)
    return run.returncode, run.stdout, run.stderr


def raised(error, call, *args, **kwargs):
    """The error that call raises. A call that raises nothing fails the test."""
    try:
        call(*args, **kwargs)
    except error as e:
        return e
    raise AssertionError(f"{error.__name__} was not raised")


class WithTemp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-staffing-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        patch = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)

    def project(self, name="project"):
        root = self.base / name
        copy_sample(root)
        return root

    def people_file(self, text, name="people.yaml"):
        path = self.base / name
        path.write_text(text, encoding="utf-8")
        return path

    def variant(self, **swaps):
        """The sample's people.yaml with each old text replaced by its new text."""
        text = PEOPLE.read_text(encoding="utf-8")
        for old, new in swaps.items():
            old = old.replace("_", " ") if old.startswith("T_") else old
            self.assertIn(old, text)
            text = text.replace(old, new, 1)
        return text


class StoredPlanTests(unittest.TestCase):
    def test_the_sample_plan_holds_ids_and_tracks_only(self):
        raw = L.load_file(PLAN)
        self.assertEqual(raw["plan_format"], 2)
        self.assertEqual(raw["plan_view"], "workspace")
        self.assertEqual(raw["people"], [{"id": "tamsin", "track": "workflow"}, {"id": "idris", "track": "experience"}])
        self.assertNotIn("advisors", raw)
        text = PLAN.read_text(encoding="utf-8")
        for secret in ("Tamsin", "Hale", "Idris", "Okoye", "Noor", "Castellan", "PostgreSQL", "TypeScript"):
            self.assertNotIn(secret, text)
        for key in REMOVED:
            self.assertFalse(any(key in person for person in raw["people"]), key)

    def test_loading_the_stored_plan_adds_no_staffing_and_no_overlay(self):
        plan, problems = L.load_plan(PLAN, SAMPLE)
        self.assertEqual(problems, [])
        self.assertIsNone(plan["_people_overlay"])
        self.assertFalse(L.staffing_loaded(plan))
        self.assertEqual(plan["people"], [{"id": "tamsin", "track": "workflow"}, {"id": "idris", "track": "experience"}])
        self.assertNotIn("advisors", plan)

    def test_the_fixture_and_the_template_follow_the_same_layout(self):
        for path in (ROOT / "tests/fixtures/confidential-project/docs/spec/plan.yaml", ROOT / "templates/plan.yaml"):
            with self.subTest(path=path.name):
                raw = L.load_file(path)
                self.assertEqual((raw["plan_format"], raw["plan_view"], raw["project"]["handling"]["state"]), (2, "workspace", "migrated"))
                self.assertNotIn("advisors", raw)
                for person in raw["people"]:
                    self.assertEqual(set(person) - {"derived"}, {"id", "track"})
                _, problems = L.load_plan(path, path.parent)
                self.assertEqual(problems, [])

    def test_the_fixtures_people_file_holds_what_the_plan_no_longer_does(self):
        doc, problems = L.load_people_file(ROOT / "tests/fixtures/confidential-project/people.yaml")
        self.assertEqual(problems, [])
        self.assertEqual([p["id"] for p in doc["people"]], ["tamsin", "idris"])
        for person in doc["people"]:
            for key in ("name", "skills", "preferences", "assignment_rationale", "allocation", "start", "days_off"):
                self.assertIn(key, person)
        self.assertEqual(len(doc["advisors"]), 1)


class OverlayTests(WithTemp):
    def test_the_overlay_is_merged_by_id_into_a_copy(self):
        stored, _ = L.load_plan(PLAN, SAMPLE)
        before = copy.deepcopy(stored)
        merged, problems = L.load_plan_with_people(PLAN, SAMPLE, people_path=PEOPLE)
        self.assertEqual(problems, [])
        self.assertEqual(stored, before)
        by_id = {p["id"]: p for p in merged["people"]}
        self.assertEqual((by_id["tamsin"]["name"], by_id["tamsin"]["allocation"], by_id["idris"]["allocation"]), ("Tamsin Hale", 100, 60))
        self.assertEqual(by_id["idris"]["days_off"], ["2027-03-08"])
        self.assertEqual(by_id["tamsin"]["track"], "workflow")   # the plan's track, not the overlay's label
        self.assertEqual(merged["_people_overlay"], str(PEOPLE))
        self.assertTrue(merged["_staffing_merged"])
        self.assertTrue(L.staffing_loaded(merged))
        self.assertEqual(merged["advisors"], [{"name": "Noor Castellan", "note": "Finance policy advisor. Reviews the rules and the export format."}])

    def test_capacity_functions_read_the_merged_plan(self):
        merged, _ = L.load_plan_with_people(PLAN, SAMPLE, people_path=PEOPLE)
        rows = {(pid, m): (sized, cap) for pid, m, sized, cap, _ in L.load_rows(merged)}
        self.assertEqual(rows[("tamsin", 1)], (3.0, 10.0))
        self.assertEqual(rows[("idris", 1)], (3.0, 6.0))
        self.assertEqual((rows[("idris", 3)][0], round(rows[("idris", 3)][1], 1)), (4.0, 5.4))
        self.assertEqual(sum(s for (pid, _), (s, _) in rows.items() if pid == "tamsin"), 18.0)
        self.assertEqual(round(sum(c for (pid, _), (_, c) in rows.items() if pid == "idris"), 2), 32.4)
        item = next(i for i in merged["items"] if i["owner"] == "idris")
        self.assertEqual(L.allocation_of(merged, item), 60)
        stored, _ = L.load_plan(PLAN, SAMPLE)
        self.assertEqual(L.allocation_of(stored, item), 100)   # nothing is invented for the stored plan: the checker skips the maths

    def test_the_overlay_comes_from_the_workspace_pointer_and_never_from_a_tracked_people_file(self):
        root = self.project()
        plan, problems = L.load_plan_with_people(root / "docs/spec/plan.yaml", root)
        self.assertEqual(problems, [])
        self.assertTrue((root / "people.yaml").is_file())   # the sample keeps a tracked, fictional copy
        self.assertIsNone(plan["_people_overlay"])           # and it is not a fallback
        self.assertEqual(L.resolve_people_path(root), (None, "workspace-unavailable"))
        ws = self.base / "ws"
        ws.mkdir()
        (root / ".carrydown").mkdir()
        (root / ".carrydown" / "local.yaml").write_text(f"workspace: {ws}\n", encoding="utf-8")
        plan, _ = L.load_plan_with_people(root / "docs/spec/plan.yaml", root)
        self.assertIsNone(plan["_people_overlay"])           # a workspace with no people.yaml gives no overlay
        shutil.copyfile(PEOPLE, ws / "people.yaml")
        plan, problems = L.load_plan_with_people(root / "docs/spec/plan.yaml", root)
        self.assertEqual(problems, [])
        self.assertEqual(plan["_people_overlay"], str(ws / "people.yaml"))

    def test_a_workspace_inside_the_repository_gives_no_overlay(self):
        root = self.project()
        inside = root / "private"
        inside.mkdir()
        shutil.copyfile(PEOPLE, inside / "people.yaml")
        (root / ".carrydown").mkdir()
        (root / ".carrydown" / "local.yaml").write_text(f"workspace: {inside}\n", encoding="utf-8")
        self.assertEqual(L.resolve_people_path(root), (None, "workspace-inside-repository"))
        plan, _ = L.load_plan_with_people(root / "docs/spec/plan.yaml", root)
        self.assertIsNone(plan["_people_overlay"])

    def test_an_explicit_people_file_must_be_given_and_exist(self):
        err = raised(L.PlanError, lambda: L.resolve_people_path(SAMPLE, ""))
        self.assertIn("--people is empty", err.msg)
        err = raised(L.PlanError, lambda: L.load_plan_with_people(PLAN, SAMPLE, people_path=self.base / "nowhere.yaml"))
        self.assertIn("does not exist", err.msg)
        self.assertEqual(L.resolve_people_path(None), (None, "workspace-unavailable"))

    def test_a_legacy_plan_is_not_merged_unless_a_file_is_named(self):
        text = PLAN.read_text(encoding="utf-8")
        start, end = text.index("plan_format: 2"), text.index("project:")
        legacy = text[:start] + text[end:]
        h0, h1 = legacy.index("  handling:"), legacy.index("\nsources:")
        legacy = legacy[:h0] + legacy[h1:]
        legacy = legacy.replace("    classification: repo-readers\n", "")
        p0, p1 = legacy.index("people:"), legacy.index("\nmilestones:\n")
        legacy = legacy[:p0] + 'people:\n  - id: tamsin\n    name: "Legacy Person"\n    track: workflow\n  - id: idris\n    name: "Other Person"\n    track: experience\n    allocation: 60\n' + legacy[p1:]
        path = self.base / "legacy.yaml"
        path.write_text(legacy, encoding="utf-8")
        plan, problems = L.load_plan_with_people(path, SAMPLE, people_path=None)
        self.assertEqual(problems, [])
        self.assertFalse(plan["_modern"])
        self.assertTrue(L.staffing_loaded(plan))
        self.assertIsNone(plan["_people_overlay"])
        self.assertEqual(plan["people"][0]["name"], "Legacy Person")


class OverlayProblemTests(WithTemp):
    """Messages about people.yaml name a person by id and a field by key. They never print a value."""

    def problems(self, text):
        merged, problems = L.load_plan_with_people(PLAN, SAMPLE, people_path=self.people_file(text))
        return problems

    def test_a_clean_file_has_no_problems(self):
        self.assertEqual(self.problems(PEOPLE.read_text(encoding="utf-8")), [])

    def test_wrong_types_name_the_person_and_the_field_only(self):
        text = PEOPLE.read_text(encoding="utf-8")
        secret = "Secret Value"
        for old, new, want in (
            ('name: "Tamsin Hale"', f"name: [{secret}]", "people.yaml person tamsin: name has the wrong type"),
            ('skills: ["Python services", "PostgreSQL", "Workflow design"]', f"skills: {{a: {secret}}}", "people.yaml person tamsin: skills has the wrong type"),
            ("days_off: [2027-02-22]", f"days_off: {{a: {secret}}}", "people.yaml person tamsin: days_off has the wrong type"),
        ):
            with self.subTest(want=want):
                problems = self.problems(text.replace(old, new, 1))
                self.assertIn(want, problems)
                self.assertFalse(any(secret in p for p in problems), problems)

    def test_allocation_dates_and_weekends_are_checked_without_echoing_the_value(self):
        text = PEOPLE.read_text(encoding="utf-8")
        for old, new, want, value in (
            ("allocation: 60", "allocation: 0", "people: idris allocation must be a whole percent from 1 to 100", "got 0"),
            ("allocation: 60", 'allocation: "60%"', "people: idris allocation must be a whole percent from 1 to 100", "60%"),
            ("allocation: 100", "allocation: 101", "people: tamsin allocation must be a whole percent from 1 to 100", "101"),
            ("start: 2027-02-01\n    days_off: [2027-02-22]", "start: 2027-01-31\n    days_off: [2027-02-22]", "people: tamsin start is a weekend", "2027-01-31"),
            ("start: 2027-02-01\n    days_off: [2027-02-22]", "start: soon\n    days_off: [2027-02-22]", "people: tamsin start is not a date (use YYYY-MM-DD)", "soon"),
            ("days_off: [2027-03-08]", "days_off: [2027-03-06]", "people: idris day off is a weekend", "2027-03-06"),
            ("days_off: [2027-03-08]", "days_off: [2027-13-45]", "people: idris days_off has a bad date", "2027-13-45"),
        ):
            with self.subTest(want=want, value=value):
                problems = self.problems(text.replace(old, new, 1))
                self.assertIn(want, problems)
                self.assertFalse(any(value in p for p in problems), problems)

    def test_an_item_due_on_its_owners_day_off_is_found_by_id(self):
        problems = self.problems(PEOPLE.read_text(encoding="utf-8").replace("days_off: [2027-03-08]", "days_off: [2027-03-03]", 1))
        self.assertIn("item 4: complete_by is a day off for idris", problems)

    def test_ids_are_matched_both_ways(self):
        text = PEOPLE.read_text(encoding="utf-8")
        problems = self.problems(text.replace("id: idris", "id: ghost", 1))
        self.assertIn("people.yaml: person ghost is not a person in plan.yaml", problems)
        self.assertIn("people.yaml has no entry for person idris", problems)
        problems = self.problems(text.replace("id: idris", "id: tamsin", 1))
        self.assertIn("people.yaml: person tamsin appears more than once", problems)
        problems = self.problems(text.replace('  - id: idris\n    name: "Idris Okoye"', '  - name: "Idris Okoye"', 1))
        self.assertIn("people.yaml: people entry 2 has no id. Each person needs the id used in plan.yaml", problems)
        self.assertFalse(any("Okoye" in p for p in problems))

    def test_a_placeholder_person_needs_no_entry(self):
        text = PLAN.read_text(encoding="utf-8").replace("  - id: idris\n    track: experience\n", "  - id: idris\n    track: experience\n    derived: true\n", 1)
        path = self.base / "derived-plan.yaml"
        path.write_text(text, encoding="utf-8")
        only_tamsin = PEOPLE.read_text(encoding="utf-8")
        only_tamsin = only_tamsin[:only_tamsin.index("  - id: idris")] + only_tamsin[only_tamsin.index("advisors:"):]
        merged, problems = L.load_plan_with_people(path, SAMPLE, people_path=self.people_file(only_tamsin))
        self.assertEqual(problems, [])
        idris = next(p for p in merged["people"] if p["id"] == "idris")
        self.assertEqual(idris["allocation"], 100)

    def test_a_track_that_disagrees_with_the_plan_is_found(self):
        problems = self.problems(PEOPLE.read_text(encoding="utf-8").replace("track: Experience", "track: Platform", 1))
        self.assertIn("people.yaml: the track of person idris does not match plan.yaml", problems)

    def test_unknown_top_level_keys_and_shapes(self):
        problems = self.problems("people: []\nsecrets: [Secret Value]\n")
        self.assertIn("people.yaml: unknown key 'secrets'. Use people and advisors", problems)
        self.assertFalse(any("Secret" in p for p in problems))
        problems = self.problems("people: Secret Value\n")
        self.assertIn("people.yaml: people must be a list of entries starting with -", problems)
        problems = self.problems('people:\n  - "Secret Value"\nadvisors:\n  - "Secret Advisor"\n')
        self.assertIn("people.yaml: people entry 1 must be a mapping such as `- id: ...`", problems)
        self.assertIn("people.yaml: advisors entry 1 must be a mapping such as `- id: ...`", problems)
        self.assertFalse(any("Secret" in p for p in problems))

    def test_a_file_that_cannot_be_read_stops_with_one_line_that_quotes_nothing(self):
        for text, want in (("people:\n  - id: tamsin\n    name: [Secret Value\n", "syntax error near line 3"),
                           ("people:\n  - id: tamsin\n   name: Secret Value\n", "syntax error"),
                           ("- Secret Value\n", "must be a mapping at the top level")):
            with self.subTest(want=want):
                err = raised(L.PlanError, lambda: L.load_plan_with_people(PLAN, SAMPLE, people_path=self.people_file(text)))
                self.assertIn(want, err.msg)
                self.assertNotIn("Secret", err.msg)
        path = self.base / "latin.yaml"
        path.write_bytes(b"people:\n  - id: tamsin\n    name: Caf\xe9\n")
        err = raised(L.PlanError, lambda: L.load_plan_with_people(PLAN, SAMPLE, people_path=path))
        self.assertIn("not UTF-8", err.msg)
        self.assertNotIn("Caf", err.msg)

    def test_a_folder_or_a_pipe_is_not_a_people_file(self):
        err = raised(L.PlanError, lambda: L.load_plan_with_people(PLAN, SAMPLE, people_path=self.base))
        self.assertIn("is a folder", err.msg)


class BannedNamesTests(unittest.TestCase):
    TEXT = "The owner is Tamsin Hale, who asked Noor Castellan to review. Reach idris any time.\n"

    def hits(self, plan):
        return [(why, ln) for why, ln, _ in CS.banned_hits(CS.banned_patterns(plan), self.TEXT)]

    def test_without_the_overlay_only_ids_are_banned(self):
        plan, _ = L.load_plan(PLAN, SAMPLE)
        self.assertEqual(plan["_banned_names"], [])
        self.assertEqual(plan["_banned_exact"], ["idris", "tamsin"])
        self.assertEqual(self.hits(plan), [("person name or handle from the plan", 1)])   # the handle idris, as written

    def test_with_the_overlay_names_are_banned_too(self):
        merged, _ = L.load_plan_with_people(PLAN, SAMPLE, people_path=PEOPLE)
        self.assertEqual(merged["_banned_names"], ["Idris Okoye", "Noor Castellan", "Tamsin Hale"])
        self.assertEqual(merged["_banned_exact"], ["Castellan", "Hale", "Idris", "Noor", "Okoye", "Tamsin"])
        found = [text for _, _, text in CS.banned_hits(CS.banned_patterns(merged), self.TEXT)]
        self.assertEqual(len(found), 2)   # each full name is one hit, and a part of it is not counted again

    def test_a_name_in_a_specification_is_found_only_with_the_overlay(self):
        root = self.base_project = Path(tempfile.mkdtemp(prefix="carrydown-banned-"))
        self.addCleanup(shutil.rmtree, str(root), True)
        copy_sample(root / "p")
        spec = root / "p" / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\nReviewed by Tamsin Hale.\n", encoding="utf-8")
        code, out, err = check(["--root", root / "p"])
        self.assertEqual(code, 0, out + err)
        code, out, err = check(["--root", root / "p", "--people", PEOPLE])
        self.assertEqual(code, 1, out + err)
        self.assertIn("person name or handle from the plan at docs/spec/m1-submit-report/wi-01-service-scaffold.md:", out)
        self.assertNotIn("Reviewed by Tamsin Hale", out)   # the line is not quoted


class CheckerTests(WithTemp):
    def test_without_the_overlay_the_sample_has_no_findings_and_says_what_was_not_checked(self):
        code, out, err = check(["--root", SAMPLE])
        self.assertEqual(code, 0, out + err)
        self.assertIn("0 with findings", out)
        self.assertEqual(out.count(NOTE), 1)

    def test_the_report_without_the_overlay_keeps_the_schedule_and_skips_capacity(self):
        code, out, err = check(["--root", SAMPLE, "--report"])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(out.count(NOTE), 1)
        for want in ("Schedule", "Critical path", "meets the target", "Planning review", "0 finding(s).",
                     "Not shown: allocation, start dates and days off are in the private people file.",
                     "Not checked: the windows depend on allocation and days off in the private people file.",
                     "Capacity is not known without the people overlay, so there is no ratio."):
            self.assertIn(want, out)
        for absent in ("Alloc", "Earliest finish", "percent of allocated capacity", "skills Python"):
            self.assertNotIn(absent, out)
        for secret in ("Tamsin", "Okoye", "PostgreSQL"):
            self.assertNotIn(secret, out)

    def test_the_report_with_the_overlay_is_the_report_the_sample_always_had(self):
        code, out, err = check(["--root", SAMPLE, "--report", "--people", PEOPLE])
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(NOTE, out)
        for want in ("tamsin  100%   3 of 10d (30%)  5 of 14d (36%)  6 of 10d (60%)  4 of 10d (40%)  0 of 10d       18 of 54d (33%)",
                     "idris   60%    3 of 6d (50%)   4 of 9d (44%)   4 of 5d (74%)   0 of 6d         3 of 6d (50%)  14 of 32d (43%)",
                     "Highest to lowest is 1.3 to 1 (idris to tamsin).", "ends 2027-03-10",
                     "tamsin on workflow: skills Python services, PostgreSQL, Workflow design; preferences Service contracts, Policy enforcement",
                     "Every sized item fits between its last dependency and its complete_by date."):
            self.assertIn(want, out)

    def test_json_output_stays_one_object_without_the_note(self):
        code, out, err = check(["--root", SAMPLE, "--json"])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(json.loads(out)["findings"], {})
        self.assertNotIn("overlay", out)

    def test_capacity_and_dates_are_checked_only_with_the_overlay(self):
        overloaded = self.people_file(self.variant(**{"allocation: 60": "allocation: 10"}), "overloaded.yaml")
        code, out, err = check(["--root", SAMPLE, "--people", overloaded])
        self.assertEqual(code, 1, out)
        self.assertIn("idris is over 100 percent of allocated capacity", out)
        code, out, err = check(["--root", SAMPLE])
        self.assertEqual(code, 0, out)
        dayoff = self.people_file(self.variant(**{"days_off: [2027-03-08]": "days_off: [2027-03-03]"}), "dayoff.yaml")
        code, out, err = check(["--root", SAMPLE, "--people", dayoff])
        self.assertEqual(code, 1, out)
        self.assertIn("item 4: complete_by is a day off for idris", out)
        self.assertNotIn("2027-03-03 is a day off", out)   # the date is not printed

    def test_the_overlay_is_found_through_the_workspace_pointer(self):
        root = self.project()
        ws = self.base / "workspace"
        ws.mkdir()
        shutil.copyfile(PEOPLE, ws / "people.yaml")
        (root / ".carrydown").mkdir()
        (root / ".carrydown" / "local.yaml").write_text(f"workspace: {ws}\n", encoding="utf-8")
        code, out, err = check(["--root", root, "--report"])
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(NOTE, out)
        self.assertIn("18 of 54d (33%)", out)

    def test_an_installed_copy_of_the_checker_reads_the_overlay_too(self):
        copy_dir = self.base / "skill"
        shutil.copytree(ROOT / "skills" / "carrydown-ground-truth", copy_dir)
        run = subprocess.run([sys.executable, str(copy_dir / "scripts/check_specs.py"), "--root", str(SAMPLE), "--report", "--people", str(PEOPLE)],
                             capture_output=True, text=True, cwd=str(self.base))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("18 of 54d (33%)", run.stdout)

    def test_the_ci_copy_in_the_sample_behaves_the_same(self):
        run = subprocess.run([sys.executable, str(SAMPLE / "tools/carrydown/check_specs.py"), "--root", str(SAMPLE)], capture_output=True, text=True, cwd=str(self.base))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(NOTE, run.stdout)


class DownstreamFlagTests(WithTemp):
    def plan_with(self, **swaps):
        text = PLAN.read_text(encoding="utf-8")
        for old, new in swaps.items():
            self.assertIn(old.replace("__", " "), text)
            text = text.replace(old.replace("__", " "), new, 1)
        path = self.base / "plan-flags.yaml"
        path.write_text(text, encoding="utf-8")
        plan, problems = L.load_plan(path, SAMPLE)
        self.assertEqual(problems, [])
        return plan

    def test_defaults_are_true_for_a_legacy_plan_and_false_for_a_migrated_one(self):
        stored, _ = L.load_plan(PLAN, SAMPLE)
        self.assertEqual(L.downstream_flags(stored), {"assignees": False, "capacity_summary": True})   # the sample sets it explicitly
        fixture, _ = L.load_plan(ROOT / "tests/fixtures/confidential-project/docs/spec/plan.yaml", ROOT / "tests/fixtures/confidential-project")
        self.assertEqual(L.downstream_flags(fixture), {"assignees": False, "capacity_summary": False})
        legacy = {"project": {}, "_modern": False}
        self.assertEqual(L.downstream_flags(legacy), {"assignees": True, "capacity_summary": True})

    def test_the_flags_can_be_set_either_way(self):
        plan = self.plan_with(**{"      capacity_summary: true": "      capacity_summary: false", "      assignees: false": "      assignees: true"})
        self.assertEqual(L.downstream_flags(plan), {"assignees": True, "capacity_summary": False})

    def test_the_constraints_have_the_capacity_text_only_when_the_flag_allows(self):
        stored, _ = L.load_plan(PLAN, SAMPLE)
        merged, _ = L.load_plan_with_people(PLAN, SAMPLE, people_path=PEOPLE)
        self.assertEqual(GS.constraints_lines(stored, merged),
                         ["Target delivery: 2027-04-23 (given)", "Track Workflow: 1 person, 100 percent allocated", "Track Experience: 1 person, 60 percent allocated"])
        self.assertEqual(GS.constraints_lines(stored), ["Target delivery: 2027-04-23 (given)", "Track Workflow: 1 person", "Track Experience: 1 person"])
        off = self.plan_with(**{"      capacity_summary: true": "      capacity_summary: false"})
        self.assertEqual(GS.constraints_lines(off, merged), ["Target delivery: 2027-04-23 (given)"])

    def test_the_epic_comment_has_no_allocation_text_when_the_summary_is_off(self):
        merged, _ = L.load_plan_with_people(PLAN, SAMPLE, people_path=PEOPLE)
        on = GS.build_rollup(merged, {}, 1, merged)
        self.assertIn("- Track Experience: 1 person, 60 percent allocated", on)
        off_plan = self.plan_with(**{"      capacity_summary: true": "      capacity_summary: false"})
        off_merged, _ = L.load_plan_with_people(self.base / "plan-flags.yaml", SAMPLE, people_path=PEOPLE)
        off = GS.build_rollup(off_plan, {}, 1, off_merged)
        self.assertNotIn("percent allocated", off)
        self.assertNotIn("Track Workflow", off)
        self.assertNotIn("Track Experience", off)
        self.assertIn("- Target delivery: 2027-04-23 (given)", off)
        self.assertEqual(GS.build_rollup(off_plan, {}, 1).count("Target delivery"), 1)

    def test_no_login_reaches_a_body_for_a_migrated_plan(self):
        with_logins = self.people_file(self.variant(**{'github: ""                     # GitHub login for issue assignment. Empty in the sample.': "github: secret-login"}))
        merged, _ = L.load_plan_with_people(PLAN, SAMPLE, people_path=with_logins)
        self.assertEqual(next(p for p in merged["people"] if p["id"] == "tamsin")["github"], "secret-login")
        stored, _ = L.load_plan(PLAN, SAMPLE)
        item = next(i for i in stored["items"] if i["owner"] == "tamsin")
        self.assertEqual(L.assignee_login(stored, item), "")
        self.assertEqual(GR.login(stored, item), "")
        body = GS.build_subepic_body(stored, SAMPLE, stored["milestones"][0]) + GS.build_rollup(stored, {}, 1, merged)
        self.assertNotIn("secret-login", body)
        self.assertNotIn("@", body.replace("@@", ""))

    def test_payload_assignees_follow_the_flag_and_need_the_overlay(self):
        with_logins = self.people_file(self.variant(**{'github: ""                     # GitHub login for issue assignment. Empty in the sample.': "github: tamsin-login"}))
        on_text = PLAN.read_text(encoding="utf-8").replace("      assignees: false", "      assignees: true")
        on_path = self.base / "assignees-on.yaml"
        on_path.write_text(on_text, encoding="utf-8")
        merged_on, _ = L.load_plan_with_people(on_path, SAMPLE, people_path=with_logins)
        merged_off, _ = L.load_plan_with_people(PLAN, SAMPLE, people_path=with_logins)
        stored_on, _ = L.load_plan(on_path, SAMPLE)
        item = next(i for i in merged_on["items"] if i["owner"] == "tamsin")
        self.assertEqual(L.payload_assignees(merged_on, item), ["tamsin-login"])
        self.assertEqual(L.payload_assignees(merged_off, item), [])    # assignees: false
        self.assertEqual(L.payload_assignees(stored_on, item), [])     # no overlay merged, so no login to send
        unowned = dict(item, owner="")
        self.assertEqual(L.payload_assignees(merged_on, unowned), [])

    def test_the_sync_dry_run_takes_the_overlay_for_the_percent_only(self):
        project = copy_sample(self.base / "owner-sample")      # the owner's working tree: its plan holds the downstream defaults
        base = [sys.executable, str(ROOT / "scripts/github_sync.py"), "--root", str(project), "--offline"]
        plain = subprocess.run(base, capture_output=True, text=True, cwd=str(self.base))
        self.assertIn("Track Workflow: 1 person\n", plain.stdout)
        self.assertNotIn("percent allocated", plain.stdout)
        staffed = subprocess.run(base + ["--people", str(PEOPLE)], capture_output=True, text=True, cwd=str(self.base))
        self.assertIn("Track Experience: 1 person, 60 percent allocated", staffed.stdout)
        self.assertNotIn("Tamsin", staffed.stdout)


class RepairAndGeneratorTests(WithTemp):
    def test_duplicate_people_are_renamed_from_their_ids_when_there_are_no_names(self):
        raw = L.load_file(PLAN)
        raw["people"].append({"id": "tamsin", "track": "experience", "derived": True})
        result, actions, questions = PR.recover(raw, SAMPLE)
        ids = [p["id"] for p in result["people"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i.startswith("tamsin") for i in ids if i != "idris"), ids)
        self.assertTrue(any("people: 'tamsin' ->" in a and "for 'tamsin'" in a for a in actions), actions)
        self.assertNotIn("name", json.dumps(result["people"]))

    def test_the_engineers_skill_says_nothing_about_percent_for_a_migrated_plan(self):
        plan, _ = L.load_plan(PLAN, SAMPLE)
        text = GD.work_items_md(plan, SAMPLE)
        self.assertIn("Allocation. The plan owner keeps each person's allocation, start date and days off in a private record.", text)
        self.assertNotIn("percent", text.split("Allocation.", 1)[1].split("\n", 1)[0].replace("percentage", ""))
        self.assertNotIn("Experience 60", text)

    def test_the_engineers_skill_keeps_the_text_for_a_legacy_plan(self):
        plan, _ = L.load_plan(PLAN, SAMPLE)
        legacy = copy.deepcopy(plan)
        legacy["_modern"] = False
        for person, allocation in zip(legacy["people"], (100, 60)):
            person["allocation"] = allocation
        self.assertIn("the allocation adds up to Workflow 100 percent, Experience 60 percent", GD.work_items_md(legacy, SAMPLE))

    def test_the_repair_dry_run_on_the_sample_reads_the_migrated_plan(self):
        code = io.StringIO()
        with contextlib.redirect_stdout(code):
            rc = PR.main(["--root", str(SAMPLE)])
        self.assertEqual(rc, 0)
        self.assertIn("repair action(s). Dry run", code.getvalue())
        self.assertNotIn("people:", code.getvalue().split("--- current plan")[0])   # no person is renamed or merged


class ReleasedStaffingStructureTests(unittest.TestCase):
    """Parse what a release would hold and assert the removed keys are absent, without banning words."""

    def walk(self, value, path=""):
        if isinstance(value, dict):
            for key, child in value.items():
                yield path + "/" + str(key), key, child
                yield from self.walk(child, path + "/" + str(key))
        elif isinstance(value, list):
            for n, child in enumerate(value):
                yield from self.walk(child, f"{path}[{n}]")

    def released_text(self):
        stored, _ = L.load_plan(PLAN, SAMPLE)
        return PR.dump(L.project_released_plan(stored)) + "\n"

    def test_the_released_people_hold_ids_and_tracks_only(self):
        parsed = L.loads(self.released_text())
        self.assertEqual(parsed["people"], [{"id": "tamsin", "track": "workflow"}, {"id": "idris", "track": "experience"}])
        self.assertNotIn("advisors", parsed)
        for where, key, _ in self.walk(parsed):
            if where.startswith("/people["):
                self.assertNotIn(key, REMOVED, where)

    def test_none_of_the_staffing_text_reaches_the_released_plan(self):
        text = self.released_text()
        for secret in ("Tamsin", "Hale", "Idris", "Okoye", "Noor", "Castellan", "Python services", "Service contracts", "PostgreSQL"):
            self.assertNotIn(secret, text)
        for key in ("assignment_rationale", "preferences", "days_off"):
            self.assertNotIn(key + ":", text)

    def test_ordinary_names_capacity_text_and_prose_about_allocation_stay(self):
        parsed = L.loads(self.released_text())
        self.assertEqual(parsed["sources"], [{"id": "architecture", "name": "Architecture document", "version": "0.3"}])
        self.assertIn("allocation", json.dumps(parsed["tracks"][1]["order_rationale"]))   # the track rationale talks about 60 percent allocation
        self.assertEqual(L.released_plan_problems(parsed), [])
        released_ok = copy.deepcopy(parsed)
        released_ok["conventions"]["extra"].append("Capacity: Track Workflow, 1 person, 100 percent allocated.")
        released_ok["sources"][0]["name"] = "Skills and allocation handbook"
        self.assertEqual(L.released_plan_problems(released_ok), [])

    def test_the_released_plan_loads_as_released_without_any_private_path(self):
        parsed = L.loads(self.released_text())
        self.assertFalse(any(k in ("path", "source_path", "classification", "content_sha256", "rendering_sha256") for _, k, _ in self.walk(parsed["sources"])))
        self.assertNotIn("ground_truth", parsed["project"])
        self.assertTrue(all(item.get("source_refs") for item in parsed["items"]))
        self.assertEqual(parsed["items"][0]["source_refs"], [{"source": "architecture", "sections": "3.1, 3.2, 5.1, 7.1"}])


if __name__ == "__main__":
    unittest.main()
