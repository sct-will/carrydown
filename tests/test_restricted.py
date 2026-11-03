"""Restricted work items and change requests (work package 9).

A work item the owner marks restricted is left out of the released plan, the specifications, the
bundles and the payloads. What it leaves behind is an external item whose only text is the owner's
summary, wherever another item depends on it, and an optional published placeholder. The tests prove
that on a copy of the sample (the "yes" path, with the drafts in the private workspace), that
nothing else of the item reaches the release by changing every private field and comparing the
snapshots, and that the engineers' skill and its README ask for a change request when the project
takes changes to a rule as requests. No token and no network are used.
"""
import copy
import importlib.util
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
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import compile_bundles as CB  # noqa: E402
import generate_dev_skill as GD  # noqa: E402
import release as R  # noqa: E402
import release_assemble as A  # noqa: E402
import release_fixture as F  # noqa: E402
import release_schema as RS  # noqa: E402
import restricted_fixture as RF  # noqa: E402
import scaffold_spec as SS  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
TEMPLATE = ROOT / "templates" / "dev-skill" / "scripts" / "check_context.py"
spec = importlib.util.spec_from_file_location("check_context_under_test_wp9", str(TEMPLATE))
CC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CC)

FIRST = "carrydown: no approved context for {id}"
FOURTH = "carrydown: {id} has a restricted destination that this project does not publish"


def snapshot_dir(yp, rid=None):
    request = R.load_request(yp.workspace, rid or yp.request_id)
    return yp.workspace / "releases" / request["release_id"] / "snapshot"


def snapshot_files(yp, rid=None):
    base = snapshot_dir(yp, rid)
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def grep(pattern, folder, fixed=True):
    """The files under folder that hold pattern (grep -r, case-insensitive)."""
    run = subprocess.run(["grep", "-rli", "-F" if fixed else "-E", "--", pattern, str(folder)], capture_output=True, text=True)
    return [x for x in run.stdout.splitlines() if x]


class WithholdTests(unittest.TestCase):
    """carrydown_lib.withhold and withheld_view: the one rule for what a restricted item leaves behind."""

    def setUp(self):
        self.plan, problems = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        self.assertEqual(problems, [])

    def restrict(self, plan, item_id, summary="Owned elsewhere.", placeholder=None):
        item = next(i for i in plan["items"] if i["id"] == item_id)
        item["restricted"], item["restricted_summary"] = True, summary
        if placeholder:
            item["restricted_placeholder"] = placeholder

    def test_a_dependent_loses_the_dependency_and_gains_the_summary_as_external_input(self):
        plan = copy.deepcopy(self.plan)
        self.restrict(plan, 7, "Retention is owned elsewhere.")
        view = L.withheld_view(plan)
        self.assertNotIn(7, [i["id"] for i in view["items"]])
        nine = next(i for i in view["items"] if i["id"] == 9)
        self.assertEqual(nine["depends"], [])
        self.assertEqual(nine["external_input"], "the pilot team, named by the stakeholders; Retention is owned elsewhere.")
        self.assertIn({"id": 7, "label": "Retention is owned elsewhere."}, view["external"]["items"])
        self.assertEqual([r["id"] for r in view["external"]["items"]], [5, 7, 10])

    def test_nothing_else_of_the_item_is_used_and_the_input_is_not_changed(self):
        plan = copy.deepcopy(self.plan)
        self.restrict(plan, 7)
        before = copy.deepcopy(plan)
        L.withheld_view(plan)
        self.assertEqual(plan, before)
        view = L.withheld_view(plan)
        self.assertNotIn("Audit log", json.dumps(view["external"]), "the label is not used")
        self.assertNotIn("restricted", {k for i in view["items"] for k in i})

    def test_unblocks_of_the_others_no_longer_name_it(self):
        plan = copy.deepcopy(self.plan)
        self.restrict(plan, 7)
        view = L.withheld_view(plan)
        three = next(i for i in view["items"] if i["id"] == 3)
        self.assertNotIn(7, three["unblocks"])
        self.assertNotIn(7, three["_derived_unblocks"])

    def test_an_item_nobody_depends_on_and_without_a_placeholder_leaves_no_trace(self):
        plan = copy.deepcopy(self.plan)
        self.restrict(plan, 11)             # nothing depends on WI-11
        view = L.withheld_view(plan)
        self.assertEqual([r["id"] for r in view["external"]["items"]], [5, 10])

    def test_a_placeholder_keeps_the_item_as_an_external_item_even_when_nothing_depends_on_it(self):
        plan = copy.deepcopy(self.plan)
        self.restrict(plan, 11, "Release readiness is run by the platform team.", "Ask the platform team.")
        view = L.withheld_view(plan)
        self.assertIn({"id": 11, "label": "Release readiness is run by the platform team."}, view["external"]["items"])

    def test_two_restricted_dependencies_join_their_summaries_without_repeating_one(self):
        plan = copy.deepcopy(self.plan)
        self.restrict(plan, 8, "Owned elsewhere.")
        self.restrict(plan, 9, "Owned elsewhere.")
        view = L.withheld_view(plan)
        eleven = next(i for i in view["items"] if i["id"] == 11)
        self.assertEqual(eleven["depends"], [])
        self.assertEqual(eleven["external_input"], "finance sign-off on the export format and retention period; Owned elsewhere.")

    def test_the_released_plan_projection_uses_the_same_rule(self):
        plan = copy.deepcopy(self.plan)
        plan["_view"] = "workspace"
        self.restrict(plan, 7, "Retention is owned elsewhere.")
        out = L.project_released_plan(plan)
        self.assertEqual(L.released_plan_problems(out), [])
        view = L.withheld_view(plan)
        self.assertEqual(out["external"]["items"], view["external"]["items"])
        self.assertEqual([i["external_input"] for i in out["items"]], [i["external_input"] for i in view["items"]])
        self.assertEqual([i["depends"] for i in out["items"]], [i["depends"] for i in view["items"]])


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)

    def problems(self, **fields):
        plan = copy.deepcopy(self.plan)
        plan["items"][5].update(fields)
        return [p for p in L.validate_plan(plan) if "restricted" in p]

    def test_a_summary_and_a_placeholder_are_one_line_and_short(self):
        self.assertEqual(self.problems(restricted=True, restricted_summary="Fine.", restricted_placeholder="Ask someone."), [])
        self.assertTrue(self.problems(restricted=True, restricted_summary="two\nlines"))
        self.assertTrue(self.problems(restricted=True, restricted_summary="x" * 201))
        self.assertTrue(self.problems(restricted=True, restricted_summary="Fine.", restricted_placeholder="two\nlines"))
        self.assertTrue(self.problems(restricted=True, restricted_summary="Fine.", restricted_placeholder="x" * 601))
        self.assertTrue(self.problems(restricted=True, restricted_summary="Fine.", restricted_placeholder="   "))

    def test_the_summary_the_placeholder_and_the_evidence_belong_to_a_restricted_item_only(self):
        self.assertTrue(self.problems(restricted_summary="Fine."))
        self.assertTrue(self.problems(restricted=False, restricted_placeholder="Ask."))
        self.assertTrue(self.problems(restricted_evidence="Done."))
        self.assertEqual(self.problems(restricted=True, restricted_summary="Fine.", restricted_evidence="Signed off on 2027-03-01, note in the vault."), [])
        self.assertTrue(self.problems(restricted=True, restricted_summary="Fine.", restricted_evidence="two\nlines"))

    def test_neither_is_allowed_in_a_released_plan(self):
        plan = copy.deepcopy(self.plan)
        plan["_view"] = "workspace"
        out = L.project_released_plan(plan)
        out["items"][0]["restricted_summary"] = "x"
        out["items"][0]["restricted_placeholder"] = "y"
        out["items"][0]["restricted_evidence"] = "z"
        found = [p for p in L.released_plan_problems(out) if "released plan" in p]
        self.assertEqual(len(found), 3, found)


class PlaceholderBundleTests(unittest.TestCase):
    def test_a_restricted_item_with_a_placeholder_gets_a_bundle_with_no_source_text(self):
        plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        item = next(i for i in plan["items"] if i["id"] == 7)
        item["restricted"], item["restricted_summary"], item["restricted_placeholder"] = True, "Owned elsewhere.", "Ask the records office."
        result = CB.compile_report(plan, SAMPLE / "docs/ground-truth", SAMPLE / "docs/spec")
        self.assertEqual(result.problems, [])
        md = result.files["docs/context/wi-07.md"].decode("utf-8")
        side = json.loads(result.files["docs/context/wi-07.bundle.json"])
        self.assertTrue(side["restricted_destination"])
        self.assertEqual((side["obligations"], side["conflicts"], side["shared_with"]), ([], [], []))
        self.assertEqual(side["content_sha256"], L.sha256_text(md))
        self.assertIn("Owned elsewhere.", md)
        self.assertIn("Ask the records office.", md)
        self.assertNotIn("Audit log", md)
        self.assertEqual(len(result.files), 18, "the 8 other items and the placeholder, two files each")
        import check_specs
        self.assertIsNone(check_specs._sidecar_problem(side, "WI-07"))
        self.assertEqual(CB.parse_obligations(md), [])

    def test_without_a_placeholder_there_is_no_bundle(self):
        plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        item = next(i for i in plan["items"] if i["id"] == 7)
        item["restricted"], item["restricted_summary"] = True, "Owned elsewhere."
        result = CB.compile_report(plan, SAMPLE / "docs/ground-truth", SAMPLE / "docs/spec")
        self.assertNotIn("docs/context/wi-07.md", result.files)
        self.assertNotIn("WI-07", "".join(v.decode("utf-8") for v in result.files.values()))


class ReleaseTests(unittest.TestCase):
    """A release of the sample with work item 7 restricted. The base project has a placeholder and a board."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-restricted-")
        cls.base = Path(cls.temp.name)
        cls.yp = RF.restricted_project(cls.base / "a", placeholder=RF.INSTRUCTION, board=True)
        code, out, err = cls.yp.prepare()
        assert code == 0, out + err
        assert cls.yp.approve()[0] == 0
        code, out, err = cls.yp.export()
        assert code == 0, out + err
        cls.snap = snapshot_dir(cls.yp)
        cls.files = snapshot_files(cls.yp)
        cls.rid = cls.yp.request_id
        # the same project without a placeholder
        cls.plain = RF.restricted_project(cls.base / "b")
        cls.plain.prepare()
        cls.plain_files = snapshot_files(cls.plain)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def text(self, files, path):
        return files[path].decode("utf-8")

    def test_the_exported_plan_has_no_restricted_item_and_an_external_item_with_exactly_the_summary(self):
        plan, problems = L.plan_from_data(L.loads(self.text(self.files, "repo/docs/spec/plan.yaml")), "released plan", None, "released")
        self.assertEqual(problems, [])
        self.assertNotIn(7, [i["id"] for i in plan["items"]])
        mine = [row for row in plan["external"]["items"] if row["id"] == 7]
        self.assertEqual(mine, [{"id": 7, "label": RF.SUMMARY}])
        nine = next(i for i in plan["items"] if i["id"] == 9)
        self.assertEqual(nine["depends"], [])
        self.assertEqual(nine["external_input"], "the pilot team, named by the stakeholders; " + RF.SUMMARY)
        for word in ("restricted", "restricted_summary", "restricted_placeholder"):
            self.assertNotIn(word, self.text(self.files, "repo/docs/spec/plan.yaml"))

    def test_no_specification_bundle_or_payload_exists_for_a_restricted_item_without_a_placeholder(self):
        names = " ".join(self.plain_files)
        for needle in ("wi-07", "WI-07", "audit-log"):
            self.assertNotIn(needle, names)

    def test_grep_over_the_snapshot_finds_neither_the_label_nor_the_specification_text(self):
        plain_dir = snapshot_dir(self.plain)
        spec_text = (self.plain.drafts / "docs/spec/m3-enforce-policy/wi-07-audit-log.md").read_text(encoding="utf-8")
        others = "\n".join(p.read_text(encoding="utf-8") for p in (self.plain.drafts / "docs/spec").rglob("wi-*.md") if "wi-07" not in p.name)
        bundles = "\n".join(v.decode("utf-8") for k, v in self.plain_files.items() if k.startswith("repo/docs/context/"))
        lines = [ln.strip() for ln in spec_text.splitlines() if len(ln.strip()) >= 60 and not ln.startswith(("|", "#"))]
        # a sentence that another specification or an approved bundle holds as well is not the restricted item's own text
        lines = [ln for ln in lines if ln not in others and ln not in bundles]
        self.assertGreaterEqual(len(lines), 8)
        self.assertEqual(grep(RF.LABEL, plain_dir), [])
        self.assertEqual(grep(RF.LABEL, self.snap), [])
        for line in lines:
            self.assertEqual(grep(line, plain_dir), [], line[:40])

    def test_the_skill_the_boards_and_the_payloads_have_no_restricted_item(self):
        board = json.loads(self.files["payloads/board/project.json"])
        self.assertNotIn("WI-07", board["items"])
        self.assertFalse([p for p in self.files if p.startswith("payloads/") and p.endswith("WI-07.json")])
        epic_comment = self.text(self.files, "payloads/epic-comment/rollup.json")
        self.assertNotIn("WI-07", epic_comment)
        self.assertNotIn("Audit log", epic_comment)
        m3 = json.loads(self.files["payloads/subepic/M3.json"])
        self.assertNotIn("WI-07", m3["body"])

    def test_the_others_no_longer_name_it_as_something_they_unblock(self):
        three = self.text(self.files, "repo/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md")
        row = next(ln for ln in three.splitlines() if ln.startswith("| Unblocks |"))
        self.assertNotIn("WI-07", row)
        nine = self.text(self.files, "repo/docs/spec/m4-pilot/wi-09-ledger-export.md")
        row = next(ln for ln in nine.splitlines() if ln.startswith("| Depends on |"))
        self.assertEqual(row, "| Depends on | external input: the pilot team, named by the stakeholders; " + RF.SUMMARY + " |")

    def test_the_drafts_of_a_restricted_item_in_the_repository_are_called_out_in_the_preview(self):
        base = Path(self.temp.name) / "c"
        yp = RF.restricted_project(base, private_drafts=False)
        # the working files are the drafts: the sample's own receipt and skill are still in the tree
        asm = A.assemble(yp.root, with_board=False)
        self.assertTrue(any("Keep drafts of restricted items in the private workspace" in n for n in asm.notes), asm.notes)

    def test_every_string_the_external_item_path_emits_is_the_owners_summary_or_a_fixed_label(self):
        """Non-interference. Everything private about the restricted item is changed, and the summary and
        the instruction are changed to markers: the two snapshots must differ only where the markers are.
        So no label, slug, theme, size, specification text or other field of the item can be in a file."""
        a = RF.restricted_project(self.base / "n1", summary="SUMMARY-ONE words", placeholder="INSTRUCTION-ONE words")
        b = RF.restricted_project(self.base / "n2", summary="SUMMARY-TWO words", placeholder="INSTRUCTION-TWO words",
                                  label="Quarterly zebra census", slug="zebra-census", theme="zebra herds", size="Large, about 5 days",
                                  extra_spec_line="Zebra stripes are counted every quarter by the census team in the field.")
        fa = A.assemble(a.root, with_board=True)
        fb = A.assemble(b.root, with_board=True)
        self.assertEqual(fa.problems, [], fa.problems)
        self.assertEqual(fb.problems, [], fb.problems)
        self.assertEqual(sorted(fa.files), sorted(fb.files))
        swapped = {}
        for path, data in fb.files.items():
            swapped[path] = data.replace(b"SUMMARY-TWO words", b"SUMMARY-ONE words").replace(b"INSTRUCTION-TWO words", b"INSTRUCTION-ONE words")
        changed = sorted(p for p in fa.files if fa.files[p] != swapped[p] and not p.endswith("wi-07.bundle.json"))
        self.assertEqual(changed, [], "a private field of the restricted item reached these files")
        # the placeholder sidecar differs only by the digest of its Markdown, which holds the instruction
        sa, sb = json.loads(fa.files["repo/docs/context/wi-07.bundle.json"]), json.loads(swapped["repo/docs/context/wi-07.bundle.json"])
        self.assertEqual(sa["content_sha256"], L.sha256_text(fa.files["repo/docs/context/wi-07.md"].decode("utf-8")))
        sa.pop("content_sha256"), sb.pop("content_sha256")
        self.assertEqual(sa, sb)
        self.assertNotIn(b"zebra", b"".join(fb.files.values()).lower())
        # and the files that hold the summary are exactly the surfaces the external item path writes to
        holders = sorted(p for p, data in fa.files.items() if b"SUMMARY-ONE words" in data)
        self.assertEqual(holders, ["payloads/issue/WI-09.json", "repo/docs/context/wi-07.md",
                                   "repo/docs/dev/skills/expense-approvals-dev/references/work-items.md", "repo/docs/spec/README.md",
                                   "repo/docs/spec/m4-pilot/wi-09-ledger-export.md", "repo/docs/spec/plan.yaml"])
        instruction = sorted(p for p, data in fa.files.items() if b"INSTRUCTION-ONE words" in data)
        self.assertEqual(instruction, ["repo/docs/context/wi-07.md"])

    def test_the_placeholder_bundle_is_the_only_trace_of_the_id_besides_the_external_item_tables(self):
        holders = sorted(p for p, data in self.files.items() if b"WI-07" in data or b"wi-07" in data)
        self.assertEqual(holders, ["repo/docs/context/wi-07.bundle.json", "repo/docs/context/wi-07.md",
                                   "repo/docs/dev/skills/expense-approvals-dev/references/work-items.md", "repo/docs/spec/README.md"])
        plain_holders = sorted(p for p, data in self.plain_files.items() if b"WI-07" in data or b"wi-07" in data)
        self.assertEqual(plain_holders, ["repo/docs/dev/skills/expense-approvals-dev/references/work-items.md", "repo/docs/spec/README.md"])

    def test_no_registry_of_private_ids_is_exported(self):
        # a second restricted item with no dependents and no placeholder is in no file at all
        yp = RF.restricted_project(self.base / "r1")
        plan_path = yp.drafts / "plan.yaml"
        text = plan_path.read_text(encoding="utf-8")
        start, end = RF._item_block(text, 11)
        block = text[start:end]
        marker = block.index("    complete_by")
        block = block[:marker] + '    restricted: true\n    restricted_summary: "Handled by the platform team."\n' + block[marker:]
        plan_path.write_text(text[:start] + block + text[end:], encoding="utf-8")
        for path in (yp.drafts / "docs/spec").rglob("*.md"):
            if "wi-11" in path.name:
                continue
            body = path.read_text(encoding="utf-8")
            new = re.sub(r"\[[^\]]*\]\([^)]*wi-11[^)]*\)", "the release item", body)
            new = re.sub(r"(?i)release readiness and runbook", "the release item", new)
            new = re.sub(r"\bWI-11\b", "the release item", new)
            if new != body:
                path.write_text(new, encoding="utf-8")
        asm = A.assemble(yp.root, with_board=False)
        self.assertEqual(asm.problems, [], asm.problems)
        everything = b"\n".join(asm.files.values()).decode("utf-8")
        self.assertNotIn("WI-11", everything)
        self.assertNotIn("wi-11", everything)
        self.assertNotIn("Handled by the platform team", everything)
        self.assertEqual(asm.restricted_items, 2)
        self.assertEqual([w[0] for w in asm.withheld], ["WI-07"])

    def test_a_leak_of_the_label_in_another_file_stops_the_release_and_names_no_text(self):
        yp = RF.restricted_project(self.base / "l1")
        spec_path = next((yp.drafts / "docs/spec").rglob("wi-02-*.md"))
        spec_path.write_text(spec_path.read_text(encoding="utf-8").rstrip("\n") + "\n\nSee also the audit log and retention work.\n", encoding="utf-8")
        asm = A.assemble(yp.root, with_board=False)
        leaks = [p for p in asm.problems if p.startswith("restricted-leak:")]
        self.assertTrue(leaks, asm.problems)
        self.assertTrue(all("restricted item WI-07" in p and "audit log" not in p.lower() for p in leaks), leaks)
        code, out, err = yp.prepare(apply=False)
        self.assertEqual(code, 1)
        self.assertIn("restricted-leak", out)

    def test_a_restricted_item_stays_open_until_the_owner_records_evidence_and_nothing_is_posted(self):
        request = R.load_request(self.yp.workspace, self.rid)
        limits = "\n".join(request["preview"]["Limitations"])
        self.assertIn("Restricted work item WI-07 is still open: no evidence is recorded in your workspace plan (restricted_evidence). "
                      "Nothing is posted to GitHub for it.", limits)
        yp = RF.restricted_project(self.base / "e1")
        plan_path = yp.drafts / "plan.yaml"
        text = plan_path.read_text(encoding="utf-8")
        plan_path.write_text(text.replace('    restricted_summary: "' + RF.SUMMARY + '"\n',
                                          '    restricted_summary: "' + RF.SUMMARY + '"\n    restricted_evidence: "Signed off by the records office, note PRIVATE-NOTE-88."\n', 1), encoding="utf-8")
        code, out, err = F.run(R.main, ["preview", "--root", str(yp.root)])
        self.assertEqual(code, 0, out + err)
        self.assertIn("Restricted work item WI-07 is done: you recorded evidence in your workspace plan. Nothing is posted to GitHub for it.", out)
        asm = A.assemble(yp.root, with_board=True)
        self.assertEqual(asm.problems, [], asm.problems)
        self.assertNotIn(b"PRIVATE-NOTE-88", b"".join(asm.files.values()))
        self.assertNotIn(b"restricted_evidence", b"".join(asm.files.values()))
        self.assertFalse([p for p in asm.files if p.endswith("WI-07.json")])
        self.assertEqual(asm.restricted_status, (("WI-07", True),))

    def test_the_summary_is_shown_to_the_approver_in_the_preview_with_the_placeholder(self):
        request = R.load_request(self.yp.workspace, self.rid)
        shared = "\n".join(request["preview"]["What will be shared"])
        self.assertIn(f'External item WI-07, published with this text from you and nothing else: "{RF.SUMMARY}"', shared)
        self.assertIn(f'Placeholder for WI-07, shown to an engineer who asks for it: "{RF.INSTRUCTION}"', shared)
        private = "\n".join(request["preview"]["What remains private"])
        self.assertIn("1 restricted work item(s) are not published: no specification, no approved context and no GitHub issue.", private)

    def test_the_placeholder_prints_the_fourth_message_and_a_withheld_id_prints_the_first(self):
        root = self.yp.root
        receipt_path = next((root / "docs/release").glob("*.receipt.json"))
        receipt = CC.parse_receipt(receipt_path.read_bytes())
        with mock.patch.object(CC, "refresh", return_value=("fresh", receipt, "a" * 40)):
            code, lines = CC.check(root, "WI-07")
        self.assertEqual((code, lines[0]), (13, FOURTH.format(id="WI-07")))
        self.assertIn("The owner's approved instruction is in docs/context/wi-07.md.", lines)
        # the project without a placeholder: the withheld id and an id nobody ever had read the same
        plain_root = self.plain.root
        self.plain.approve()
        self.plain.export()
        receipt = CC.parse_receipt(next((plain_root / "docs/release").glob("*.receipt.json")).read_bytes())
        with mock.patch.object(CC, "refresh", return_value=("fresh", receipt, "a" * 40)):
            withheld = CC.check(plain_root, "WI-07")
            unknown = CC.check(plain_root, "WI-99")
        self.assertEqual(withheld[0], unknown[0])
        self.assertEqual(withheld[1], [ln.replace("WI-99", "WI-07") for ln in unknown[1]])
        self.assertEqual(withheld[1][0], FIRST.format(id="WI-07"))

    def test_an_unrestricted_id_is_unaffected(self):
        root = self.yp.root
        receipt = CC.parse_receipt(next((root / "docs/release").glob("*.receipt.json")).read_bytes())
        with mock.patch.object(CC, "refresh", return_value=("fresh", receipt, "a" * 40)):
            code, lines = CC.check(root, "WI-09")
        self.assertEqual(code, 0, lines)


class ChangeRequestTests(unittest.TestCase):
    """Change requests under engineer_edits: request-only (WP9 behavior 4 and 5)."""

    def setUp(self):
        self.plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)

    def skill(self, edits):
        return GD.skill_files(self.plan, SAMPLE, engineer_edits=edits)

    def test_request_only_step_8_asks_for_a_rule_clarification_request_comment_with_permission(self):
        text = self.skill("request-only")["SKILL.md"]
        step = next(ln for ln in text.splitlines() if ln.startswith("8. "))
        self.assertIn("`Rule clarification request`", step)
        self.assertIn("only after the user gives permission", step)
        self.assertIn("continue only with what the approved context permits", step)
        self.assertIn('Do not edit "Decisions recorded"', step)
        self.assertNotIn("append a short entry", step)

    def test_allowed_keeps_todays_step_8(self):
        text = self.skill("allowed")["SKILL.md"]
        step = next(ln for ln in text.splitlines() if ln.startswith("8. "))
        self.assertEqual(step, '8. If the implementation departs from the file, append a short entry under "Decisions recorded" at the end of the file, '
                               'with the pull request number, in the same pull request.')
        self.assertEqual(self.skill(None)["SKILL.md"], text, "the default is allowed")

    def test_the_plan_handling_decides_when_the_caller_does_not(self):
        plan = copy.deepcopy(self.plan)
        plan["project"]["handling"]["engineer_edits"] = "request-only"
        text = GD.skill_files(plan, SAMPLE)["SKILL.md"]
        self.assertIn("Rule clarification request", text)
        self.assertEqual(GD.skill_files(plan, SAMPLE, engineer_edits="allowed")["SKILL.md"], self.skill("allowed")["SKILL.md"], "the caller wins")

    def test_the_readme_says_the_same_in_the_same_mode(self):
        request_only = self.skill("request-only")["README.md"]
        allowed = self.skill("allowed")["README.md"]
        section = request_only.split("## Requesting a change to a rule", 1)[1].split("## How the skill relates", 1)[0]
        self.assertIn("fails the independent check on pull requests", section)
        self.assertIn("`Rule clarification request`", section)
        self.assertIn("supersedes the previous release, and the new receipt names the request it replaces", section)
        self.assertIn("preview, prepare, approve and export", section)
        self.assertNotIn("append a dated entry", section)
        mine = allowed.split("## Requesting a change to a rule", 1)[1].split("## How the skill relates", 1)[0]
        self.assertIn("append a dated entry under \"Decisions recorded\"", mine)
        self.assertIn("`Rule clarification request`", mine)

    def test_the_generated_skill_has_no_token_code_and_cannot_post(self):
        for edits in ("allowed", "request-only"):
            for path, text in self.skill(edits).items():
                for word in ("github_client", "urllib", "Authorization", "api.github.com", "http.client", "import socket"):
                    self.assertNotIn(word, text, f"{path} ({edits})")
        self.assertIn("this skill holds no token and cannot post by itself", self.skill("request-only")["SKILL.md"])

    def test_the_enrollment_value_decides_for_an_enrolled_project_and_the_default_is_the_stricter_one(self):
        enrolled = mock.Mock(enrolled=True, entry={"engineer_edits": {"docs/spec/**": "allowed"}})
        self.assertEqual(R.engineer_edits_of(enrolled), "allowed")
        enrolled.entry = {"engineer_edits": {"docs/spec/**": "request-only"}}
        self.assertEqual(R.engineer_edits_of(enrolled), "request-only")
        enrolled.entry = {}
        self.assertEqual(R.engineer_edits_of(enrolled), "request-only")
        self.assertIsNone(R.engineer_edits_of(None))
        self.assertIsNone(R.engineer_edits_of(mock.Mock(enrolled=False)))

    def test_a_release_carries_the_enrollments_wording_into_the_snapshot_skill(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-change-") as tmp:
            yp = RF.restricted_project(Path(tmp) / "p", restrict=False)       # no skill folder yet: the files are generated
            skill_rel = "repo/docs/dev/skills/expense-approvals-dev/"
            asm = A.assemble(yp.root, with_board=False, engineer_edits="request-only")
            self.assertEqual(asm.problems, [], asm.problems)
            self.assertIn("Rule clarification request", asm.files[skill_rel + "SKILL.md"].decode("utf-8"))
            self.assertIn("fails the independent check on pull requests", asm.files[skill_rel + "README.md"].decode("utf-8"))
            asm = A.assemble(yp.root, with_board=False)
            self.assertNotIn("Rule clarification request", asm.files[skill_rel + "SKILL.md"].decode("utf-8"))

    def test_a_kept_skill_follows_a_change_of_policy_but_keeps_the_owners_other_edits(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-change-") as tmp:
            yp = RF.restricted_project(Path(tmp) / "p", restrict=False)
            skill_dir = yp.drafts / "docs/dev/skills/expense-approvals-dev"
            for rel, text in GD.skill_files(yp_plan(yp), yp.drafts, engineer_edits="allowed").items():
                (skill_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (skill_dir / rel).write_text(text, encoding="utf-8")
            (skill_dir / "SKILL.md").write_text((skill_dir / "SKILL.md").read_text(encoding="utf-8") + "\nOwner's own line.\n", encoding="utf-8")
            asm = A.assemble(yp.root, with_board=False, engineer_edits="request-only")
            kept = asm.files["repo/docs/dev/skills/expense-approvals-dev/SKILL.md"].decode("utf-8")
            self.assertIn("Rule clarification request", kept)
            self.assertIn("Owner's own line.", kept)
            # a sentence the owner rewrote is not touched
            rewritten = (skill_dir / "SKILL.md").read_text(encoding="utf-8").replace(GD.DECISIONS_ALLOWED, "Write decisions down however you like.")
            (skill_dir / "SKILL.md").write_text(rewritten, encoding="utf-8")
            asm = A.assemble(yp.root, with_board=False, engineer_edits="request-only")
            self.assertEqual(asm.files["repo/docs/dev/skills/expense-approvals-dev/SKILL.md"].decode("utf-8"), rewritten)


class ConfidentialFixtureTests(unittest.TestCase):
    """The standard fixture (tests/fixtures/confidential-project): work item 6 cites the restricted source."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-restricted-fixture-")
        cls.np = F.NoProject(Path(cls.temp.name))
        drafts = cls.np.workspace / "drafts"
        plan_path = drafts / "plan.yaml"
        text = plan_path.read_text(encoding="utf-8")
        start, end = RF._item_block(text, 6)
        block = text[start:end]
        marker = block.index("    complete_by")
        block = block[:marker] + '    restricted: true\n    restricted_summary: "Limits are handled by the finance policy team."\n' + block[marker:]

        def scrub(t):
            t = re.sub(r"(?i)approval limits and separation of duties", "the limits item", t)
            return re.sub(r"\bWI-06\b", "the limits item", t)
        plan_path.write_text(scrub(text[:start]) + block + scrub(text[end:]), encoding="utf-8")
        for path in sorted((drafts / "docs/spec").rglob("*.md")):
            if not path.name.startswith("wi-06"):
                body = path.read_text(encoding="utf-8")
                new = scrub(re.sub(r"\[[^\]]*\]\([^)]*wi-06[^)]*\)", "the limits item", body))
                if new != body:
                    path.write_text(new, encoding="utf-8")
        cls.asm = A.assemble(cls.np.root, with_board=False)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_the_release_can_be_prepared_and_nothing_of_the_item_or_its_source_is_in_a_bundle(self):
        self.assertEqual(self.asm.problems, [])
        self.assertFalse([p for p in self.asm.files if "wi-06" in p.lower()])
        sources = {o["source"] for p, d in self.asm.files.items() if p.endswith(".bundle.json") for o in json.loads(d)["obligations"]}
        self.assertEqual(sources, {"architecture"})
        self.assertEqual(self.asm.link_items, ())
        holders = [p for p, d in self.asm.files.items() if b"ompany governance" in d or b"company-governance" in d]
        self.assertEqual(holders, ["repo/docs/spec/plan.yaml"], "the source is listed by id, name and version only")

    def test_the_item_that_depended_on_it_shows_the_owners_summary_and_the_plan_has_one_external_item_for_it(self):
        plan, problems = L.plan_from_data(L.loads(self.asm.files["repo/docs/spec/plan.yaml"].decode("utf-8")), "released plan", None, "released")
        self.assertEqual(problems, [])
        self.assertIn({"id": 6, "label": "Limits are handled by the finance policy team."}, plan["external"]["items"])
        eight = next(i for i in plan["items"] if i["id"] == 8)
        self.assertEqual((eight["depends"], eight["external_input"]), ([4], "Limits are handled by the finance policy team."))
        body = json.loads(self.asm.files["payloads/issue/WI-08.json"])["body"]
        self.assertIn("- External input: Limits are handled by the finance policy team.", body)
        self.assertNotIn("WI-06", body)

    def test_grep_over_the_written_snapshot_finds_nothing_of_the_item(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-restricted-grep-") as out:
            for path, data in self.asm.files.items():
                target = Path(out) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            # the label is also the heading of section 4.1 of the architecture document, which the approved
            # contexts of other items quote verbatim, so those files are approved source text and not searched
            def outside_approved_text(hits):
                return [h for h in hits if "/repo/docs/context/" not in h and not h.endswith("/references/ground-truth-map.md")]
            self.assertEqual(outside_approved_text(grep("Approval limits and separation", out)), [])
            self.assertTrue(grep("Approval limits and separation", out), "the fixture's label is also a source heading, which is the point of the exemption")
            spec = next((self.np.workspace / "drafts/docs/spec").rglob("wi-06-*.md")).read_text(encoding="utf-8")
            own = [ln.strip() for ln in spec.splitlines() if len(ln.strip()) >= 60 and not ln.startswith(("|", "#"))]
            self.assertGreater(len(own), 5)
            others = "\n".join(d.decode("utf-8") for p, d in self.asm.files.items() if p.startswith("repo/docs/spec/") and p.endswith(".md"))
            for line in own:
                if line not in others:
                    self.assertEqual(outside_approved_text(grep(line, out)), [], line[:40])


def yp_plan(yp):
    plan, problems = L.load_plan(yp.drafts / "plan.yaml", yp.root)
    assert problems == [], problems
    return plan


class SupersessionTests(unittest.TestCase):
    """The owner side of a change request: update the workspace, then preview, prepare, approve, export."""

    def test_a_new_release_supersedes_the_old_one_and_the_receipt_names_it(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-supersede-") as tmp:
            yp = RF.restricted_project(Path(tmp) / "p")
            self.assertEqual(yp.prepare()[0], 0)
            first = yp.request_id
            self.assertEqual(yp.approve()[0], 0)
            self.assertEqual(yp.export()[0], 0)
            # the engineer's request is answered: the owner clarifies a rule in the workspace draft
            spec_path = next((yp.drafts / "docs/spec").rglob("wi-06-*.md"))
            spec_path.write_text(spec_path.read_text(encoding="utf-8").rstrip("\n") + "\n", encoding="utf-8")
            body = spec_path.read_text(encoding="utf-8").replace("## Decisions recorded", "## Decisions recorded\n\n- Clarified after a rule clarification request.", 1)
            if "## Decisions recorded" not in spec_path.read_text(encoding="utf-8"):
                body = spec_path.read_text(encoding="utf-8") + "\n## Decisions recorded\n\n- Clarified after a rule clarification request.\n"
            spec_path.write_text(body, encoding="utf-8")
            code, out, err = F.run(R.main, ["preview", "--root", str(yp.root)])
            self.assertEqual(code, 0, out + err)
            self.assertIn("Changed:", out)
            self.assertEqual(yp.prepare(nonce="ffeeddccbbaa99887766554433221100")[0], 0)
            second = yp.request_id
            self.assertNotEqual(first, second)
            request = R.load_request(yp.workspace, second)
            self.assertEqual(request["supersedes_request_id"], first)
            self.assertEqual(yp.approve(second, created="2027-01-21T10:00:00Z")[0], 0)
            code, out, err = yp.export(second)
            self.assertEqual(code, 0, out + err)
            receipts = {p.name[:-len(".receipt.json")]: json.loads(p.read_text(encoding="utf-8")) for p in (yp.root / "docs/release").glob("*.receipt.json")}
            self.assertEqual(receipts[second]["supersedes"], first)
            self.assertEqual(receipts[second]["state"], "active")
            self.assertEqual((receipts[first]["state"], receipts[first]["superseded_by"]), ("superseded", second))
            for receipt in receipts.values():
                self.assertNotIn("reason", json.dumps(receipt), "private reasons stay in the event batch")


if __name__ == "__main__":
    unittest.main()
