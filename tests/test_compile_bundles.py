"""Bundles (work package 5): scripts/compile_bundles.py and the content-free map of the engineers' skill.

They cover the compiler on the confidential fixture (one bundle per item, verbatim section text, the
recorded conflict, shared obligations, no release id), the completeness check, the sidecar fields
(versions, downstream flags), the command line (dry run, candidate folder, the release gate), restricted
items, and the generated ground-truth-map.md. No token and no network are used.
Run from the repository root: python -m unittest discover -s tests -v
"""
import contextlib
import copy
import io
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
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import carrydown_lib as L  # noqa: E402
import compile_bundles as CB  # noqa: E402
import generate_dev_skill as GD  # noqa: E402
import plan_repair as PR  # noqa: E402
import release_gate as RG  # noqa: E402
import release_schema as RS  # noqa: E402
import test_release_schema as T  # noqa: E402  (its helpers build a manifest, a request and a receipt)

FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
SAMPLE = ROOT / "sample" / "expense-approvals"
RENDERINGS = FIXTURE / "docs" / "ground-truth"
SPEC_DIR = FIXTURE / "docs" / "spec"
ARCH = (RENDERINGS / "architecture.md").read_text(encoding="utf-8")
GOV = (RENDERINGS / "company-governance.md").read_text(encoding="utf-8")


def load_fixture_plan(root=FIXTURE):
    plan, problems = L.load_plan(Path(root) / "docs" / "spec" / "plan.yaml", root)
    assert problems == [], problems
    return plan


def section_text(rendering, number):
    """The text under the numbered heading, found here without the compiler: from the heading to the
    next heading of the same or a higher level, normalized, with the blank lines around it dropped."""
    lines = rendering.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+" + re.escape(number) + r"\.?\s", line)
        if m:
            level = len(m.group(1))
            body = []
            for later in lines[i + 1:]:
                h = re.match(r"^(#+)\s", later)
                if h and len(h.group(1)) <= level:
                    break
                body.append(later)
            return L.normalize_section_text("\n".join(body).strip("\n"))
    raise AssertionError(f"no section {number}")


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = CB.main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
            if isinstance(e.code, str):
                err.write(e.code)
    return code, out.getvalue(), err.getvalue()


class Compiled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = load_fixture_plan()
        cls.files = CB.compile_bundles(cls.plan, RENDERINGS, SPEC_DIR)

    def md(self, tag):
        return self.files[f"docs/context/{tag.lower()}.md"].decode("utf-8")

    def side(self, tag):
        return json.loads(self.files[f"docs/context/{tag.lower()}.bundle.json"].decode("utf-8"))


class CompileFixtureTests(Compiled):
    def test_one_bundle_per_work_item(self):
        tags = [L.tag(self.plan, it["id"]) for it in self.plan["items"]]
        self.assertEqual(len(tags), 9)
        self.assertEqual(sorted(self.files), sorted([f"docs/context/{t.lower()}.md" for t in tags] +
                                                    [f"docs/context/{t.lower()}.bundle.json" for t in tags]))
        for tag in tags:
            self.assertEqual(self.side(tag)["work_item"], tag)
            self.assertTrue(self.md(tag).startswith(f"# Approved context for {tag}, "))

    def test_wi06_holds_the_cited_sections_verbatim(self):
        text = self.md("WI-06")
        for rendering, source, numbers in ((ARCH, "architecture", ("3.5", "4.1", "7.1")), (GOV, "company-governance", ("1.5", "2.3"))):
            for number in numbers:
                expected = section_text(rendering, number)
                self.assertIn(expected, text, f"{source} {number}")
                self.assertIn(f"### {source} {number} ", text)
        # a section that WI-06 does not cite is not there
        self.assertNotIn(section_text(ARCH, "3.4"), text)
        self.assertNotIn("### architecture 3.4", text)

    def test_wi06_carries_the_recorded_conflict(self):
        text = self.md("WI-06")
        self.assertIn("## Conflict resolution that applies", text)
        self.assertIn("The plan says the policy wins when they disagree.", text)
        conflicts = self.side("WI-06")["conflicts"]
        policy = next(c for c in conflicts if "The plan says the policy wins" in c["decision"])
        self.assertEqual(policy["between"], ["architecture 3.5", "company-governance 1.5", "company-governance 2.3"])
        self.assertIsNone(policy["recorded"])
        # a bullet that names no cited section is not a conflict note
        self.assertFalse(any("Compare dates as UTC" in c["decision"] for c in conflicts))

    def test_wi03_is_listed_as_sharing_section_3_5(self):
        line06 = next(l for l in self.md("WI-06").split("\n") if l.startswith("- architecture 3.5 Routing, also cited by "))
        self.assertIn("WI-03", line06.split("also cited by ")[1].rstrip(".").split(", "))
        self.assertNotIn("WI-06", line06)
        self.assertIn("WI-03", self.side("WI-06")["shared_with"])
        line03 = next(l for l in self.md("WI-03").split("\n") if l.startswith("- architecture 3.5 Routing, also cited by "))
        self.assertIn("WI-06", line03.split("also cited by ")[1].rstrip(".").split(", "))
        self.assertNotIn("WI-07", self.side("WI-07")["shared_with"])

    def test_no_bundle_file_contains_the_release_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "snapshot"
            for rel, data in self.files.items():
                path = snapshot / "repo" / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            manifest, release_id = RS.hash_manifest(snapshot)
        for rel, data in self.files.items():
            self.assertNotIn(release_id.encode(), data, rel)
            if rel.endswith(".bundle.json"):
                self.assertFalse([k for k in json.loads(data) if "release" in k or "request" in k], rel)

    def test_sidecar_fields_and_digests(self):
        keys = {"bundle_format", "work_item", "obligations", "conflicts", "shared_with", "downstream", "content_sha256", "extensions"}
        for tag in ("WI-01", "WI-06", "WI-11"):
            side = self.side(tag)
            self.assertEqual(set(side), keys)
            self.assertEqual(side["bundle_format"], 1)
            self.assertEqual(side["extensions"], {})
            self.assertEqual(side["downstream"], {"code": True, "tests": True, "issues": False, "evidence": "synthetic-only"})
            raw = self.files[f"docs/context/{tag.lower()}.md"]
            self.assertEqual(side["content_sha256"], RS.sha256_bytes(raw))
            self.assertEqual(self.files[f"docs/context/{tag.lower()}.bundle.json"], RS.canonical_json(side))
            # the per-obligation digests are those of the normalized text found in the Markdown
            found = CB.parse_obligations(raw)
            self.assertEqual([(s, n, h) for s, n, h, _ in found],
                             [(o["source"], o["section"], o["heading"]) for o in side["obligations"]])
            for (_, _, _, text), ob in zip(found, side["obligations"]):
                self.assertEqual(ob["sha256"], L.sha256_text(text))
        versions = {(o["source"], o["version"]) for o in self.side("WI-06")["obligations"]}
        self.assertEqual(versions, {("architecture", "0.3"), ("company-governance", "2027.1")})

    def test_the_bundle_says_where_it_comes_from_and_what_it_may_be_used_for(self):
        head = self.md("WI-06").split("## Obligations")[0]
        self.assertIn("Bundle format 1. Sources: architecture 0.3 (reviewed), company-governance 2027.1 (reviewed).", head)
        self.assertIn("Downstream use: approved for implementation in this repository's code and tests.", head)
        self.assertIn("Evidence may include response bodies with synthetic data only.", head)

    def test_output_is_deterministic_and_lf_only(self):
        again = CB.compile_bundles(load_fixture_plan(), RENDERINGS, SPEC_DIR)
        self.assertEqual(again, self.files)
        for rel, data in self.files.items():
            self.assertNotIn(b"\r", data, rel)
            self.assertTrue(data.endswith(b"\n") and not data.endswith(b"\n\n"), rel)

    def test_crlf_renderings_give_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for p in RENDERINGS.glob("*.md"):
                (Path(tmp) / p.name).write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
            again = CB.compile_bundles(load_fixture_plan(), tmp, SPEC_DIR)
        self.assertEqual(again, self.files)

    def test_trailing_blanks_in_a_rendering_do_not_change_the_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            for p in RENDERINGS.glob("*.md"):
                (Path(tmp) / p.name).write_text(p.read_text(encoding="utf-8").replace("\n1. ", " \t\n1. "), encoding="utf-8")
            again = CB.compile_bundles(load_fixture_plan(), tmp, SPEC_DIR)
        self.assertEqual(again["docs/context/wi-06.md"], self.files["docs/context/wi-06.md"])

    def test_every_item_cites_numbered_sections_so_each_has_obligations(self):
        for it in self.plan["items"]:
            tag = L.tag(self.plan, it["id"])
            self.assertTrue(self.side(tag)["obligations"], tag)


class CompletenessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-bundles-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.renderings = self.base / "renderings"
        shutil.copytree(RENDERINGS, self.renderings)
        self.plan = load_fixture_plan()

    def test_a_missing_section_is_named_by_source_and_number(self):
        arch = self.renderings / "architecture.md"
        arch.write_text(arch.read_text(encoding="utf-8").replace("### 3.5 Routing", "### Routing"), encoding="utf-8")
        result = CB.compile_report(self.plan, self.renderings, SPEC_DIR)
        self.assertEqual(result.files, {})
        self.assertIn("obligation not found: architecture 3.5 (cited by WI-03)", result.problems)
        self.assertIn("obligation not found: architecture 3.5 (cited by WI-06)", result.problems)
        rows = {r[0]: r[2:] for r in result.rows}
        self.assertEqual(rows["WI-06"], (4, 5))
        self.assertEqual(rows["WI-03"], (3, 4))       # its specification also links a section its header does not cite
        self.assertEqual(rows["WI-01"], (6, 6))
        error = None
        try:
            CB.compile_bundles(self.plan, self.renderings, SPEC_DIR)
        except CB.CompileError as e:
            error = e
        self.assertIsNotNone(error)
        self.assertIn("obligation not found: architecture 3.5", error.problems[0])

    def test_a_missing_rendering_makes_every_cited_section_missing(self):
        (self.renderings / "company-governance.md").unlink()
        problems = CB.compile_report(self.plan, self.renderings, SPEC_DIR).problems
        self.assertEqual(sorted(problems), ["obligation not found: company-governance 1.5 (cited by WI-06)",
                                            "obligation not found: company-governance 2.3 (cited by WI-06)"])

    def test_text_that_looks_like_the_bundle_layout_is_refused(self):
        arch = self.renderings / "architecture.md"
        arch.write_text(arch.read_text(encoding="utf-8").replace("### 3.5 Routing\n", "### 3.5 Routing\n\n```\n## Shared obligations\n```\n", 1), encoding="utf-8")
        problems = CB.compile_report(self.plan, self.renderings, SPEC_DIR).problems
        self.assertIn("obligation text collides with the bundle layout: architecture 3.5 (cited by WI-06)", problems)

    def test_a_source_that_the_plan_does_not_list_is_not_found(self):
        plan = copy.deepcopy(self.plan)
        plan["items"][4]["source_refs"].append({"source": "unlisted", "sections": "1.1"})
        self.assertIn("obligation not found: unlisted 1.1 (cited by WI-06)", CB.compile_report(plan, self.renderings, SPEC_DIR).problems)

    def test_an_item_that_cites_nothing_still_gets_a_bundle(self):
        plan = copy.deepcopy(self.plan)
        plan["items"][0]["ground_truth"] = ""
        files = CB.compile_bundles(plan, self.renderings, self.base / "no-specifications")
        text = files["docs/context/wi-01.md"].decode("utf-8")
        self.assertIn("This work item cites no source sections.", text)
        self.assertEqual(json.loads(files["docs/context/wi-01.bundle.json"])["obligations"], [])

    def test_a_rendering_that_is_not_utf8_is_one_line_without_content(self):
        (self.renderings / "architecture.md").write_bytes(b"\xff\xfe not text")
        problems = CB.compile_report(self.plan, self.renderings, SPEC_DIR).problems
        self.assertIn("the rendering of source architecture cannot be read as UTF-8 text", problems)
        self.assertFalse([p for p in problems if "not text" in p])


class SidecarFieldTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_fixture_plan()

    def side(self, plan, renderings=RENDERINGS, tag="wi-06", **kw):
        files = CB.compile_bundles(plan, renderings, SPEC_DIR, **kw)
        return json.loads(files[f"docs/context/{tag}.bundle.json"])

    def test_the_downstream_flags_can_be_overridden_for_one_item(self):
        self.plan["items"][4]["downstream"] = {"issues": True, "evidence": "approved", "tests": False}
        self.assertEqual(self.side(self.plan)["downstream"], {"code": True, "tests": False, "issues": True, "evidence": "approved"})
        self.assertEqual(self.side(self.plan, tag="wi-01")["downstream"]["tests"], True)
        text = CB.compile_bundles(self.plan, RENDERINGS, SPEC_DIR)["docs/context/wi-06.md"].decode("utf-8")
        self.assertIn("approved for implementation in this repository's code, not in tests.", text)
        self.assertIn("May be quoted in issue text.", text)
        self.assertIn("Evidence may include real data that the plan owner approved.", text)

    def test_the_caller_can_change_the_defaults(self):
        side = self.side(self.plan, defaults={"code": False, "issues": True})
        self.assertEqual(side["downstream"], {"code": False, "tests": True, "issues": True, "evidence": "synthetic-only"})

    def test_the_evidence_default_follows_the_plan_handling_when_it_is_set(self):
        self.plan["project"]["handling"]["downstream"] = {"evidence": "approved"}
        self.assertEqual(self.side(self.plan)["downstream"]["evidence"], "approved")

    def test_a_bad_override_is_a_problem_and_names_the_item(self):
        self.plan["items"][4]["downstream"] = {"code": "yes", "reviewers": True}
        problems = CB.compile_report(self.plan, RENDERINGS, SPEC_DIR).problems
        self.assertEqual(problems, ["WI-06: downstream.code has an unsupported value", "WI-06: downstream has an unknown key 'reviewers'"])

    def test_the_version_comes_from_the_plan_then_the_rendering_header_then_unversioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            for p in RENDERINGS.glob("*.md"):
                shutil.copy(p, tmp)
            plan = load_fixture_plan()
            for s in plan["sources"]:
                s.pop("version")
            versions = {(o["source"], o["version"]) for o in self.side(plan, tmp)["obligations"]}
            self.assertEqual(versions, {("architecture", "0.3"), ("company-governance", "2027.1")})   # from the header comment
            for p in Path(tmp).glob("*.md"):
                p.write_text(re.sub(r"<!-- Generated from .*? -->", "", p.read_text(encoding="utf-8")), encoding="utf-8")
            versions = {o["version"] for o in self.side(plan, tmp)["obligations"]}
            self.assertEqual(versions, {"unversioned"})

    def test_conflict_notes_from_a_plan_field_and_the_date_in_them(self):
        self.plan["items"][4]["decisions"] = ["Decision recorded 2027-01-14: GOV-1.5 wins over architecture 3.5 for the line manager limit."]
        conflicts = self.side(self.plan)["conflicts"]
        note = next(c for c in conflicts if c["decision"].startswith("Decision recorded"))
        self.assertEqual(note["recorded"], "2027-01-14")
        self.assertEqual(note["between"], ["architecture 3.5", "architecture 4.1"])

    def test_a_restricted_item_has_no_bundle_and_leaves_no_trace_in_the_others(self):
        self.plan["items"][2]["restricted"] = True       # WI-03
        self.plan["items"][2]["restricted_summary"] = "Handled outside this project."
        files = CB.compile_bundles(self.plan, RENDERINGS, SPEC_DIR)
        self.assertNotIn("docs/context/wi-03.md", files)
        self.assertEqual(len(files), 16)
        self.assertNotIn("WI-03", files["docs/context/wi-06.md"].decode("utf-8"))
        self.assertNotIn("WI-03", json.loads(files["docs/context/wi-06.bundle.json"])["shared_with"])


class NamingTests(unittest.TestCase):
    OBS = [{"source": "architecture", "section": "3.5", "heading": "Routing"},
           {"source": "architecture", "section": "4.1", "heading": "GOV-1 Approval limits"},
           {"source": "company-governance", "section": "2.3", "heading": "Approval limits"},
           {"source": "company-governance", "section": "3.5", "heading": "Retention"}]
    SOURCES = {"architecture": {"id": "architecture", "name": "Architecture document"},
               "company-governance": {"id": "company-governance", "name": "Company governance policy"}}

    def names(self, text):
        return [CB._obligation_label(o) for o in CB.named_obligations(text, self.OBS, self.SOURCES)]

    def test_section_numbers_ids_and_identifiers(self):
        self.assertEqual(self.names("See section 4.1 for the limits."), ["architecture 4.1"])
        self.assertEqual(self.names("GOV-1.5 says no."), ["architecture 4.1"])
        self.assertEqual(self.names("The limit in company-governance 2.3 wins."), ["company-governance 2.3"])
        self.assertEqual(self.names("Rule 2.3 of the Company governance policy applies."), ["company-governance 2.3"])
        self.assertEqual(self.names("GOV-2.6 and section 9.9 are not cited here."), [])
        self.assertEqual(self.names("Nothing is named."), [])

    def test_a_number_that_two_sources_share_is_narrowed_by_the_source_named(self):
        self.assertEqual(self.names("Section 3.5 of the architecture document is the rule."), ["architecture 3.5"])
        self.assertEqual(self.names("The company governance policy, section 3.5, decides."), ["company-governance 3.5"])
        both = self.names("Section 3.5 decides.")
        self.assertEqual(both, ["architecture 3.5", "company-governance 3.5"])

    def test_a_longer_number_is_not_the_cited_section(self):
        self.assertEqual(self.names("Section 3.5.1 is a detail."), [])
        self.assertEqual(self.names("architecture 3.55 is another section."), [])

    def test_watch_out_bullets_are_joined_and_split(self):
        text = "## Watch out for\n\n- First bullet\n  continues here.\n- Second bullet.\n\n## References\n- x\n"
        self.assertEqual(CB.watch_out_notes(text), ["First bullet continues here.", "Second bullet."])
        self.assertEqual(CB.watch_out_notes("# Title\n\nNothing here.\n"), [])


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-bundles-cli-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        patch = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)
        self.root = self.base / "engineering"
        shutil.copytree(FIXTURE, self.root)

    def make_workspace(self):
        ws = self.base / "workspace"
        (ws / "renderings").mkdir(parents=True)
        for p in RENDERINGS.glob("*.md"):
            shutil.copy(p, ws / "renderings" / p.name)
        shutil.rmtree(self.root / "docs" / "ground-truth")        # the "no" path keeps no rendering in the project
        (self.root / ".carrydown").mkdir()
        (self.root / ".carrydown" / "local.yaml").write_text(f"workspace: {ws}\n", encoding="utf-8")
        return ws

    def test_the_dry_run_prints_the_table_and_writes_nothing(self):
        ws = self.make_workspace()
        code, out, err = run_cli(["--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        self.assertIn("WI-06  obligations present: 5 of 5   Approval limits and separation of duties", out)
        self.assertIn("WI-01  obligations present: 6 of 6", out)
        self.assertIn("renderings from the private workspace", out)
        self.assertIn("18 file(s) would be written under docs/context/", out)
        self.assertIn("Dry run. Add --apply to write.", out)
        self.assertIn("Whether each bundle is enough to do the work is your review.", out)
        self.assertEqual(list(ws.glob("candidate")), [])
        self.assertFalse((self.root / "docs" / "context").exists())

    def test_apply_writes_the_candidate_folder_of_the_workspace_by_default(self):
        ws = self.make_workspace()
        code, out, err = run_cli(["--root", str(self.root), "--apply"])
        self.assertEqual(code, 0, out + err)
        folder = ws / "candidate" / "snapshot" / "repo" / "docs" / "context"
        self.assertEqual(len(list(folder.iterdir())), 18)
        self.assertEqual((folder / "wi-06.md").read_bytes(), CB.compile_bundles(load_fixture_plan(), RENDERINGS, SPEC_DIR)["docs/context/wi-06.md"])
        self.assertFalse((self.root / "docs" / "context").exists(), "nothing is written into the engineering repository")
        code, out, err = run_cli(["--root", str(self.root), "--apply"])
        self.assertEqual(code, 0)

    def test_apply_without_a_workspace_and_without_out_is_refused(self):
        code, out, err = run_cli(["--root", str(self.root), "--apply"])
        self.assertEqual(code, 2, out + err)
        self.assertIn("workspace-unavailable", out + err)
        self.assertFalse((self.root / "docs" / "context").exists())

    def test_out_writes_under_the_folder_given(self):
        target = self.base / "snapshot"
        code, out, err = run_cli(["--root", str(self.root), "--renderings", str(RENDERINGS), "--out", str(target), "--apply"])
        self.assertEqual(code, 0, out + err)
        self.assertTrue((target / "docs" / "context" / "wi-06.bundle.json").is_file())
        self.assertIn("in the candidate folder", out)

    def test_a_missing_obligation_exits_1_and_writes_nothing(self):
        arch = self.root / "docs" / "ground-truth" / "architecture.md"
        arch.write_text(arch.read_text(encoding="utf-8").replace("### 7.1 REST API", "### REST API"), encoding="utf-8")
        target = self.base / "snapshot"
        code, out, err = run_cli(["--root", str(self.root), "--renderings", str(arch.parent), "--out", str(target), "--apply"])
        self.assertEqual(code, 1, out + err)
        self.assertIn("obligation not found: architecture 7.1 (cited by WI-06)", out)
        self.assertIn("WI-06  obligations present: 4 of 5", out)
        self.assertIn("No bundle was compiled.", out)
        self.assertFalse(target.exists())

    def test_the_release_gate_is_asked_before_any_write_and_can_refuse(self):
        calls = []

        def deny(write_class, path, digest, destination, root, **kw):
            calls.append((write_class, path, digest))
            return RG.Decision(False, "deny", "not-approved", None)

        target = self.base / "snapshot"
        with mock.patch.object(RG, "check", deny):
            code, out, err = run_cli(["--root", str(self.root), "--renderings", str(RENDERINGS), "--out", str(target), "--apply"])
        self.assertEqual(code, 2, out + err)
        self.assertIn("not-approved", out + err)
        self.assertFalse(target.exists())
        self.assertEqual({c[0] for c in calls}, {"candidate"})
        self.assertEqual(len(calls), 1, "the first refusal stops the run before any file is written")
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", c[2]) for c in calls))

    def test_a_write_into_the_project_is_a_draft_write(self):
        classes = set()

        def record(write_class, path, digest, destination, root, **kw):
            classes.add(write_class)
            return RG.Decision(True, "legacy", "no-handling-policy", None)

        with mock.patch.object(RG, "check", record):
            code, out, err = run_cli(["--root", str(self.root), "--renderings", str(RENDERINGS), "--out", ".", "--apply"])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(classes, {"draft"})
        self.assertTrue((self.root / "docs" / "context" / "wi-06.md").is_file())

    def test_stale_files_are_reported_and_left_alone(self):
        target = self.base / "snapshot"
        (target / "docs" / "context").mkdir(parents=True)
        (target / "docs" / "context" / "wi-99.md").write_text("old\n", encoding="utf-8")
        code, out, err = run_cli(["--root", str(self.root), "--renderings", str(RENDERINGS), "--out", str(target), "--apply"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("not in this compile and left in place: docs/context/wi-99.md", out)
        self.assertTrue((target / "docs" / "context" / "wi-99.md").exists())

    def test_a_released_plan_is_refused(self):
        released = L.project_released_plan(load_fixture_plan())
        text = json.dumps(released)
        plan_path = self.base / "released.json"
        plan_path.write_text(text, encoding="utf-8")
        code, out, err = run_cli(["--root", str(self.root), "--plan", str(plan_path)])
        self.assertEqual(code, 2, out + err)
        self.assertIn("schema-view-mismatch", out + err)

    def test_it_runs_as_a_script_and_prints_help(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_bundles.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0)
        self.assertIn("--apply", run.stdout)


class SampleBundleTests(unittest.TestCase):
    """The committed bundles of the sample are what the compiler makes from its renderings."""

    def test_the_committed_bundles_match_a_fresh_compile(self):
        plan, problems = L.load_plan(SAMPLE / "docs" / "spec" / "plan.yaml", SAMPLE)
        self.assertEqual(problems, [])
        fresh = CB.compile_bundles(plan, SAMPLE / "docs" / "ground-truth", SAMPLE / "docs" / "spec")
        committed = {f"docs/context/{p.name}": p.read_bytes() for p in (SAMPLE / "docs" / "context").iterdir()}
        self.assertEqual(committed, fresh)
        self.assertEqual(len(committed), 18)

    def test_the_sample_bundle_for_wi06_has_its_three_sections(self):
        side = json.loads((SAMPLE / "docs" / "context" / "wi-06.bundle.json").read_text(encoding="utf-8"))
        self.assertEqual([o["section"] for o in side["obligations"]], ["3.5", "4.1", "7.1"])
        self.assertIn("WI-03", side["shared_with"])


class GroundTruthMapTests(unittest.TestCase):
    """The generated ground-truth-map.md is content-free: only headings that are in a bundle."""

    @classmethod
    def setUpClass(cls):
        cls.plan = load_fixture_plan()
        cls.files = CB.compile_bundles(cls.plan, RENDERINGS, SPEC_DIR)
        cls.map = GD.ground_truth_map_md(cls.plan, FIXTURE, bundles=cls.files)

    def test_it_lists_only_headings_that_are_in_a_bundle(self):
        in_bundles = set()
        for rel, data in self.files.items():
            if rel.endswith(".bundle.json"):
                in_bundles |= {(o["source"], o["section"], o["heading"]) for o in json.loads(data)["obligations"]}
        for rendering, source in ((ARCH, "architecture"), (GOV, "company-governance")):
            for _, _, title in L.collect_headings(rendering.split("\n")):
                m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", title)
                if not m:
                    continue
                listed = f"| {m.group(1)} | {m.group(2)} |" in self.map
                if (source, m.group(1), m.group(2)) in in_bundles:
                    self.assertTrue(listed, title)
                else:
                    self.assertFalse(listed, f"{title} is in no bundle but is in the map")
        self.assertNotIn("Review cycle", self.map)          # company-governance 1.4, cited by nobody
        self.assertIn("| 1.5 | Sole approver | WI-06 |", self.map)

    def test_it_names_no_original_file_no_rendering_path_no_version(self):
        for forbidden in ("architecture.md", "company-governance.md", "ground-truth/", "source_path", "Original file", "Rendered path",
                          "Section index", "Coverage limit", "0.3", "2027.1", ".index.txt"):
            self.assertNotIn(forbidden, self.map)
        self.assertIn("| 1 | architecture | Architecture document |", self.map)
        self.assertIn("| 2 | company-governance | Company governance policy |", self.map)

    def test_it_is_built_from_the_files_of_the_project_when_no_bundles_are_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rel, data in self.files.items():
                path = Path(tmp) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            from_files = GD.ground_truth_map_md(self.plan, tmp)
        self.assertEqual(from_files, self.map)

    def test_without_any_bundle_it_says_none_is_released(self):
        text = GD.ground_truth_map_md(self.plan, FIXTURE)       # the fixture has no docs/context
        self.assertIn("No approved context has been released yet.", text)
        self.assertNotIn("Section", text.split("\n", 3)[3])

    def test_the_sample_map_is_the_one_the_generator_makes(self):
        plan, _ = L.load_plan(SAMPLE / "docs" / "spec" / "plan.yaml", SAMPLE)
        committed = (SAMPLE / "docs" / "dev" / "skills" / "expense-approvals-dev" / "references" / "ground-truth-map.md").read_text(encoding="utf-8")
        self.assertEqual(committed, GD.ground_truth_map_md(plan, SAMPLE))


def released_project(base, source, edit=lambda text: text):
    """A released clone of a project, in a temporary folder: the released plan, the specifications with
    their Ground truth rows as that plan states them, the bundles this compiler writes, and one receipt
    that lists the plan and the bundles. It holds no original, no rendering and no overlay."""
    base = Path(base)
    root = base / "released"
    shutil.copytree(source, root, ignore=shutil.ignore_patterns(".gitignore", "people.yaml", "__pycache__", "ground-truth", "dev", "tools", ".github", "release"))
    stored_path = base / "workspace-plan.yaml"
    stored_path.write_text(edit((source / "docs" / "spec" / "plan.yaml").read_text(encoding="utf-8")), encoding="utf-8")
    stored, problems = L.load_plan(stored_path, source)
    assert not problems, problems
    plan_path = root / "docs" / "spec" / "plan.yaml"
    plan_path.write_text(PR.dump(L.project_released_plan(stored)) + "\n", encoding="utf-8")
    plan, problems = L.load_plan(plan_path, root)
    assert not problems and plan["_view"] == "released", problems
    for it in plan["items"]:
        path = L.spec_path(plan, root, it)
        want = dict(L.expected_header(plan, it))["Ground truth"]
        path.write_text(re.sub(r"(?m)^\| Ground truth \| .* \|$", lambda m: f"| Ground truth | {want} |", path.read_text(encoding="utf-8")), encoding="utf-8")
    files = CB.compile_bundles(stored, source / "docs" / "ground-truth", root / "docs" / "spec")
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    snap = base / "snapshot"
    for path in [plan_path] + sorted((root / "docs" / "context").glob("*")):
        dst = snap / "repo" / path.relative_to(root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)
    manifest, _ = RS.hash_manifest(snap)
    request = T.make_request(manifest)
    rid = request["request_sha256"]
    receipt = RS.project_receipt(request, manifest, RS.RequestState(rid, "active", T.H("event"), None, None), RS.VerifiedApproval(rid, "local-owner", False))
    (root / "docs" / "release").mkdir(parents=True)
    (root / "docs" / "release" / f"{rid}.receipt.json").write_bytes(receipt)
    return root, files


def run_checker(root):
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_specs.py"), "--root", str(root)], capture_output=True, text=True, timeout=120)
    return run.returncode, run.stdout + run.stderr


class SpecCitationTests(unittest.TestCase):
    """The compiler puts into a bundle every section the specification cites, so the released checker passes."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-bundles-released-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()

    def sections(self, files, tag):
        return {(o["source"], o["section"]) for o in json.loads(files[f"docs/context/{tag.lower()}.bundle.json"])["obligations"]}

    def test_a_section_the_specification_links_but_the_header_does_not_cite_is_in_the_bundle(self):
        plan = load_fixture_plan()
        files = CB.compile_bundles(plan, RENDERINGS, SPEC_DIR)
        self.assertIn(("architecture", "3.3"), self.sections(files, "WI-01"))       # WI-01 links 3.3 and 3.6, and cites 3.1, 3.2, 5.1, 7.1
        self.assertIn(("architecture", "3.6"), self.sections(files, "WI-01"))
        self.assertIn("### architecture 3.3 Data model", files["docs/context/wi-01.md"].decode("utf-8"))

    def test_references_lines_in_the_new_form_are_in_the_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = Path(tmp) / "spec"
            shutil.copytree(SPEC_DIR, spec_dir)
            spec = spec_dir / "m3-enforce-policy" / "wi-07-audit-log.md"
            spec.write_text(spec.read_text(encoding="utf-8").replace("## References\n", "## References\n\n- company-governance section 3.1, Retention\n- architecture section 2.2\n", 1), encoding="utf-8")
            files = CB.compile_bundles(load_fixture_plan(), RENDERINGS, spec_dir)
            self.assertLessEqual({("company-governance", "3.1"), ("architecture", "2.2")}, self.sections(files, "WI-07"))
            self.assertIn("### company-governance 3.1 Retention", files["docs/context/wi-07.md"].decode("utf-8"))
            bad = spec.read_text(encoding="utf-8").replace("architecture section 2.2", "architecture section 9.9")
            spec.write_text(bad, encoding="utf-8")
            problems = CB.compile_report(load_fixture_plan(), RENDERINGS, spec_dir).problems
            self.assertEqual(problems, ["obligation not found: architecture 9.9 (cited by WI-07)"])

    def test_a_link_into_a_code_block_or_to_a_heading_that_is_not_there_cites_nothing(self):
        sources = {"architecture": {}}
        sections = CB.parse_rendering(ARCH)
        text = "```\n[x](../../ground-truth/architecture.md#35-routing)\n```\n[y](../../ground-truth/architecture.md#99-nothing)\n[z](other/architecture.md#35-routing)\n"
        self.assertEqual(CB.spec_cited_keys(text, sources, lambda sid: sections), [])
        text = "[x](../../ground-truth/architecture.md#35-routing)\n[x](../../ground-truth/architecture.md#41-gov-1-approval-limits-and-separation-of-duties)\n"
        self.assertEqual(CB.spec_cited_keys(text, sources, lambda sid: sections), [("architecture", "3.5"), ("architecture", "4.1")])

    def test_every_obligation_version_is_the_version_of_the_source_in_the_plan(self):
        plan = load_fixture_plan()
        versions = {s["id"]: str(s["version"]) for s in plan["sources"]}
        files = CB.compile_bundles(plan, RENDERINGS, SPEC_DIR)
        for rel, data in files.items():
            if rel.endswith(".bundle.json"):
                for o in json.loads(data)["obligations"]:
                    self.assertEqual(o["version"], versions[o["source"]], rel)

    def test_a_whole_document_reference_is_one_obligation_with_the_section_whole_document(self):
        plan = load_fixture_plan()
        plan["items"][0]["source_refs"] = [{"source": "architecture", "sections": "whole document"}]
        plan["items"][0]["ground_truth"] = ""
        files = CB.compile_bundles(plan, RENDERINGS, SPEC_DIR)
        side = json.loads(files["docs/context/wi-01.bundle.json"])
        whole = [o for o in side["obligations"] if o["section"] == "whole document"]
        self.assertEqual(len(whole), 1)
        self.assertEqual(whole[0]["source"], "architecture")
        self.assertEqual(whole[0]["heading"], "Expense approvals service, architecture document")
        text = files["docs/context/wi-01.md"].decode("utf-8")
        self.assertIn("### architecture whole document Expense approvals service, architecture document", text)
        self.assertIn(section_text(ARCH, "3.5"), text)
        self.assertNotIn("Generated from", text)          # the header comment names the original file, so it is left out
        self.assertNotIn("architecture.md", text)
        (_, _, _, body), = [o for o in CB.parse_obligations(files["docs/context/wi-01.md"]) if o[1] == "whole document"]
        self.assertEqual(whole[0]["sha256"], L.sha256_text(body))

    def test_the_released_checker_passes_on_the_fixture_with_the_compiled_bundles(self):
        root, files = released_project(self.base, FIXTURE)
        code, out = run_checker(root)
        self.assertEqual(code, 0, out)
        self.assertIn("0 with findings", out)

    def test_the_released_checker_passes_on_the_sample_with_the_compiled_bundles(self):
        root, files = released_project(self.base, SAMPLE)
        code, out = run_checker(root)
        self.assertEqual(code, 0, out)
        self.assertIn("0 with findings", out)

    def test_the_released_checker_passes_when_an_item_cites_the_whole_document(self):
        edit = lambda text: text.replace('    ground_truth: "Sections 3.1, 3.2, 5.1, 7.1"', '    source_refs:\n      - source: architecture\n        sections: "whole document"')
        root, files = released_project(self.base, FIXTURE, edit)
        self.assertIn(("architecture", "whole document"), self.sections(files, "WI-01"))
        code, out = run_checker(root)
        self.assertEqual(code, 0, out)

    def test_dropping_a_compiled_obligation_is_a_released_failure(self):
        root, files = released_project(self.base, FIXTURE)
        side_path = root / "docs" / "context" / "wi-06.bundle.json"
        side = json.loads(side_path.read_text(encoding="utf-8"))
        side["obligations"] = [o for o in side["obligations"] if o["section"] != "3.5"]
        side_path.write_bytes(RS.canonical_json(side))
        code, out = run_checker(root)
        self.assertEqual(code, 1, out)


class ContractsPointToBundlesTests(unittest.TestCase):
    def test_each_contract_row_names_the_approved_context(self):
        plan, _ = L.load_plan(SAMPLE / "docs" / "spec" / "plan.yaml", SAMPLE)
        text = GD.contracts_md(plan, SAMPLE)
        self.assertIn("| Id | Work item | Section | File | Approved context |", text)
        self.assertIn("`docs/context/wi-06.md`", text)


if __name__ == "__main__":
    unittest.main()
