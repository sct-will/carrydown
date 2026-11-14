"""Reconciliation helpers (specs/reconciliation-design.md, sections 7, 8 and 12): scripts/reconcile_core.py.

One test class per function. They cover the pure scenarios of section 16.1: no relevant change, a
formatting-only change, a changed quantity, exception or negation, a removal, an ambiguous renumbering, a
unique move, a scheduling dependency that is not a content consumer, missing, duplicate and malformed
dispositions, changed and missing digests, index budgets and omitted word counts, restricted rows left
out of the public index and counted for the owner, and deterministic order. The sample project is read
only. No token and no network are used.
Run from the repository root: python3 -m unittest tests.test_reconcile_core -v
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import reconcile_core as R  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
ARCH = (SAMPLE / "docs" / "ground-truth" / "architecture.md").read_text(encoding="utf-8")


def doc(*sections, title="Fictional document"):
    """A rendering built from (number, heading, body) tuples. A body may be ''. The level follows the number."""
    out = [f"# {title}", "", "A subtitle line.", ""]
    for number, heading, body in sections:
        out.append("#" * (number.count(".") + 2) + f" {number} {heading}")
        out.append("")
        if body:
            out += [body, ""]
    return "\n".join(out)


def kinds(blocks):
    return sorted((b["kind"], b["previous_number"], b["current_number"]) for b in blocks)


def sample_plan():
    plan, problems = L.load_plan(SAMPLE / "docs" / "spec" / "plan.yaml", SAMPLE)
    assert problems == [], problems
    specs = {it["id"]: L.read_text(L.spec_path(plan, SAMPLE, it)) for it in plan["items"]}
    return plan, specs


def small_plan(items, sources=("architecture",)):
    """A plan as the loader would give it, with only what the helpers read."""
    return {"project": {"id_prefix": "WI", "spec_dir": "docs/spec"},
            "sources": [{"id": s, "name": s.title(), "path": f"docs/ground-truth/{s}.md", "status": "reviewed"} for s in sources],
            "milestones": [{"number": 1, "name": "One", "folder": "m1-one", "start": "2027-01-04", "end": "2027-01-15"}],
            "items": items}


def item(number, label="Item", refs="", depends=(), unblocks=(), **more):
    row = {"id": number, "slug": f"item-{number}", "label": label, "milestone": 1, "depends": list(depends), "unblocks": list(unblocks),
           "external_input": "", "source_refs": [{"source": "architecture", "sections": refs}] if refs else [], "ground_truth": ""}
    row.update(more)
    return row


def spec(why="It exists.", criteria=("One thing works.",), contract="", integration="", decisions="None yet.", refs=()):
    lines = ["# WI-01 Item", "", "## Why this work item exists", "", why, "", "## Acceptance criteria", ""]
    lines += [f"- [ ] {c}" for c in criteria]
    if contract:
        lines += ["", "## Contract", "", contract]
    if integration:
        lines += ["", "## Integration points", "", integration]
    lines += ["", "## References", ""] + [f"- architecture section {r}" for r in refs]
    lines += ["", "## Decisions recorded", "", decisions, ""]
    return "\n".join(lines)


class TestHelpers(unittest.TestCase):
    def test_sha256_text_matches_the_library_and_rejects_non_text(self):
        self.assertEqual(R.sha256_text("abc"), L.sha256_text("abc"))
        self.assertRegex(R.sha256_text(""), r"^[0-9a-f]{64}$")
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.sha256_text(b"abc")
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.sha256_text("a\x00b")

    def test_normalize_ignores_white_space_emphasis_wrapping_and_bullets(self):
        a = "Some **bold** text,   wrapped\nacross lines.\n\n\n* one\n* two\n"
        b = "Some bold text, wrapped across lines.\n\n- one\n- two"
        self.assertEqual(R.normalize_block(a), R.normalize_block(b))
        self.assertEqual(R.normalize_block("a\r\nb  \r\n"), R.normalize_block("a b"))

    def test_normalize_keeps_every_word_number_and_negation(self):
        for word in ("not", "never", "unless", "except", "only", "must", "must not", "at most", "at least"):
            self.assertIn(word, R.normalize_block(f"The service **{word}** retries 3 times after 5 seconds."))
        self.assertIn("25,000.00", R.normalize_block("Limit *25,000.00* USD"))
        self.assertNotEqual(R.normalize_block("It must retry."), R.normalize_block("It must not retry."))

    def test_normalize_keeps_code_fences_inline_code_and_tables(self):
        code = "```yaml\nkey:   value\n  nested: *x*\n```\n"
        self.assertIn("key:   value\n  nested: *x*", R.normalize_block(code))
        self.assertIn("`a*b*c`", R.normalize_block("Use `a*b*c` here."))
        self.assertEqual(R.normalize_block("|a|  b |\n|--|:-:|\n|1|2|"), "| a | b |\n| --- | :---: |\n| 1 | 2 |\n")
        self.assertNotEqual(R.normalize_block("| a | 5 |"), R.normalize_block("| a | 6 |"))
        self.assertNotEqual(R.normalize_block("```\nx = 1\n```"), R.normalize_block("```\nx = 2\n```"))

    def test_normalize_keeps_identifiers_with_underscores_and_empty_text(self):
        self.assertIn("E_LIMIT", R.normalize_block("Answers E_LIMIT and snake_case_name."))
        self.assertEqual(R.normalize_block(""), "")
        self.assertEqual(R.normalize_block("\n\n  \n"), "")


class TestCompareSections(unittest.TestCase):
    BASE = doc(("1", "Rules", "Intro."),
               ("1.1", "Limit", "The limit is 5,000 dollars. A manager may approve."),
               ("1.2", "Approval", "Approval is required."),
               ("2", "Interfaces", "Two endpoints."))

    def test_no_relevant_change_gives_no_blocks(self):
        self.assertEqual(R.compare_sections(self.BASE, self.BASE), [])
        self.assertEqual(R.compare_sections(ARCH, ARCH), [])
        crlf = self.BASE.replace("\n", "\r\n") + "   "
        self.assertEqual(R.compare_sections(self.BASE, crlf), [])

    def test_trailing_spaces_alone_are_not_a_change(self):
        self.assertEqual(R.compare_sections(self.BASE, self.BASE.replace("required.", "required.   ")), [])

    def test_formatting_only_change_is_flagged_not_meaningful(self):
        cur = self.BASE.replace("Approval is required.", "**Approval**   is   required.")
        blocks = R.compare_sections(self.BASE, cur)
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual((block["kind"], block["previous_number"], block["current_number"]), ("modified", "1.2", "1.2"))
        self.assertTrue(block["formatting_only"])
        self.assertFalse(block["text_changed"])
        self.assertEqual(block["previous_digest"], block["current_digest"])

    def test_rewrapping_and_a_heading_level_change_are_formatting_only(self):
        cur = self.BASE.replace("The limit is 5,000 dollars. A manager may approve.", "The limit is 5,000\ndollars. A manager\nmay approve.")
        self.assertTrue(all(b["formatting_only"] for b in R.compare_sections(self.BASE, cur)))
        cur = self.BASE.replace("### 1.2 Approval", "#### 1.2 Approval")
        blocks = R.compare_sections(self.BASE, cur)
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0]["formatting_only"])

    def test_changed_quantity_is_meaningful(self):
        blocks = R.compare_sections(self.BASE, self.BASE.replace("5,000", "6,000"))
        self.assertEqual(kinds(blocks), [("modified", "1.1", "1.1")])
        self.assertFalse(blocks[0]["formatting_only"])
        self.assertTrue(blocks[0]["text_changed"])
        self.assertNotEqual(blocks[0]["previous_digest"], blocks[0]["current_digest"])

    def test_changed_exception_and_negation_are_meaningful(self):
        for old, new in (("A manager may approve.", "A manager may approve, except the submitter."),
                         ("Approval is required.", "Approval is not required."),
                         ("A manager may approve.", "A manager must not approve."),
                         ("5,000 dollars", "5,000 euros")):
            blocks = R.compare_sections(self.BASE, self.BASE.replace(old, new))
            self.assertEqual(len(blocks), 1, new)
            self.assertFalse(blocks[0]["formatting_only"], new)

    def test_a_changed_table_cell_and_code_line_are_meaningful(self):
        old = doc(("1", "Data", "| Field | Max |\n| --- | --- |\n| name | 40 |\n\n```json\n{\"a\": 1}\n```"))
        self.assertEqual(len(R.compare_sections(old, old.replace("| 40 |", "| 50 |"))), 1)
        self.assertEqual(len(R.compare_sections(old, old.replace('"a": 1', '"a": 2'))), 1)
        for b in R.compare_sections(old, old.replace("| name | 40 |", "|name|   40|")):
            self.assertTrue(b["formatting_only"])

    def test_removal_is_reported_with_its_old_number(self):
        cur = doc(("1", "Rules", "Intro."), ("1.1", "Limit", "The limit is 5,000 dollars. A manager may approve."),
                  ("2", "Interfaces", "Two endpoints."))
        blocks = R.compare_sections(self.BASE, cur)
        self.assertEqual(kinds(blocks), [("removed", "1.2", None)])
        self.assertIsNone(blocks[0]["current_heading"])
        self.assertEqual(blocks[0]["previous_heading"], "Approval")
        self.assertFalse(blocks[0]["ambiguous"])

    def test_addition_is_reported(self):
        cur = self.BASE + "\n### 2.1 Errors\n\nE_STATE is 409.\n"
        self.assertEqual(kinds(R.compare_sections(self.BASE, cur)), [("added", None, "2.1")])

    def test_unique_move_is_proposed_as_a_mapping(self):
        prev = doc(("1", "Rules", ""), ("1.1", "Limit", "The limit is 5,000 dollars."), ("2", "Interfaces", "Two endpoints."))
        cur = doc(("1", "Rules", ""), ("2", "Interfaces", "Two endpoints."), ("2.1", "Limit", "The limit is 5,000 dollars."))
        blocks = R.compare_sections(prev, cur)
        self.assertEqual(kinds(blocks), [("moved", "1.1", "2.1")])
        block = blocks[0]
        self.assertTrue(block["exact_move"])
        self.assertEqual(block["mapping_basis"], "exact-body")
        self.assertEqual(block["previous_digest"], block["current_digest"])
        self.assertFalse(block["ambiguous"])

    def test_a_shift_with_the_same_parent_is_renumbered(self):
        prev = doc(("1", "Rules", ""), ("1.1", "Limit", "The limit is 5,000 dollars."), ("1.2", "Approval", "Approval is required."))
        cur = doc(("1", "Rules", ""), ("1.1", "Scope", "Something new."), ("1.2", "Limit", "The limit is 5,000 dollars."),
                  ("1.3", "Approval", "Approval is required."))
        blocks = R.compare_sections(prev, cur)
        got = kinds(blocks)
        self.assertIn(("renumbered", "1.1", "1.2"), got)
        self.assertIn(("renumbered", "1.2", "1.3"), got)
        self.assertTrue(all(b["exact_move"] for b in blocks if b["kind"] == "renumbered"))
        # both numbers exist on both sides, so each is also a modified section at its own number
        self.assertIn(("modified", "1.1", "1.1"), got)
        self.assertIn(("modified", "1.2", "1.2"), got)
        self.assertNotIn(("added", None, "1.3"), got)

    def test_ambiguous_renumbering_is_reported_and_never_mapped(self):
        same = "Identical body text for two sections."
        prev = doc(("1", "Rules", ""), ("1.1", "Alpha", same), ("2", "Other", "Other."))
        cur = doc(("1", "Rules", ""), ("2", "Other", "Other."), ("3", "Beta", same), ("4", "Gamma", same))
        blocks = R.compare_sections(prev, cur)
        self.assertFalse(any(b["exact_move"] for b in blocks))
        self.assertFalse(any(b["kind"] in ("moved", "renumbered") for b in blocks))
        removed = [b for b in blocks if b["kind"] == "removed"]
        self.assertEqual(len(removed), 1)
        self.assertTrue(removed[0]["ambiguous"])
        self.assertEqual(removed[0]["candidates"], ["3", "4"])
        added = [b for b in blocks if b["kind"] == "added"]
        self.assertEqual(sorted(b["current_number"] for b in added), ["3", "4"])
        self.assertTrue(all(b["ambiguous"] and b["candidates"] == ["1.1"] for b in added))

    def test_a_changed_section_whose_old_text_may_sit_in_two_places_carries_candidates(self):
        same = "Identical body text for the old section."
        prev = doc(("1", "Rules", ""), ("1.1", "Alpha", same), ("2", "Other", "Other."))
        cur = doc(("1", "Rules", ""), ("1.1", "Alpha", "Rewritten text."), ("2", "Other", "Other."),
                  ("3", "Beta", same), ("4", "Gamma", same))
        blocks = R.compare_sections(prev, cur)
        modified = [b for b in blocks if b["kind"] == "modified"]
        self.assertEqual(len(modified), 1)
        self.assertTrue(modified[0]["ambiguous"])
        self.assertEqual(modified[0]["candidates"], ["3", "4"])
        self.assertFalse(any(b["exact_move"] for b in blocks))

    def test_two_identical_removed_bodies_are_ambiguous_too(self):
        same = "Identical body text."
        prev = doc(("1", "A", same), ("2", "B", same), ("3", "C", "Keep."))
        cur = doc(("3", "C", "Keep."), ("4", "D", same))
        blocks = R.compare_sections(prev, cur)
        self.assertFalse(any(b["exact_move"] for b in blocks))
        self.assertTrue(all(b["ambiguous"] for b in blocks if b["kind"] in ("removed", "added")))

    def test_a_unique_heading_match_with_changed_text_is_proposed_but_not_exact(self):
        prev = doc(("1", "Rules", ""), ("1.1", "Limit", "The limit is 5,000 dollars."))
        cur = doc(("1", "Rules", ""), ("1.2", "Limit", "The limit is 6,000 dollars."))
        blocks = R.compare_sections(prev, cur)
        self.assertEqual(kinds(blocks), [("renumbered", "1.1", "1.2")])
        self.assertFalse(blocks[0]["exact_move"])
        self.assertEqual(blocks[0]["mapping_basis"], "heading")
        self.assertTrue(blocks[0]["text_changed"])

    def test_empty_sections_are_never_mapped_by_their_text(self):
        prev = doc(("1", "Alpha", ""), ("2", "Beta", ""))
        cur = doc(("3", "Gamma", ""))
        self.assertEqual(kinds(R.compare_sections(prev, cur)), [("added", None, "3"), ("removed", "1", None), ("removed", "2", None)])

    def test_a_repeated_number_is_unreadable(self):
        cur = self.BASE + "\n### 1.2 Approval again\n\nOther text.\n"
        blocks = R.compare_sections(self.BASE, cur)
        self.assertEqual([b["kind"] for b in blocks], ["unreadable"])
        self.assertIn("1.2", blocks[0]["reason"])

    def test_numbered_headings_on_one_side_only_is_unreadable(self):
        blocks = R.compare_sections(self.BASE, "# Title\n\nJust prose, no numbers.\n")
        self.assertEqual([b["kind"] for b in blocks], ["unreadable"])
        self.assertIn("current", blocks[0]["reason"])

    def test_a_rendering_without_numbers_is_compared_as_one_document(self):
        a, b = "# T\n\nProse A.\n", "# T\n\nProse B.\n"
        self.assertEqual(R.compare_sections(a, a), [])
        blocks = R.compare_sections(a, b)
        self.assertEqual(kinds(blocks), [("modified", "whole document", "whole document")])

    def test_precedence_change_is_reported_for_the_source(self):
        blocks = R.compare_sections(self.BASE, self.BASE, source_id="gov", previous_precedence=["gov", "arch"],
                                    current_precedence=["arch", "gov"])
        self.assertEqual([b["kind"] for b in blocks], ["precedence"])
        self.assertEqual((blocks[0]["previous_rank"], blocks[0]["current_rank"]), (1, 2))
        self.assertEqual(blocks[0]["ref"], "gov/precedence")
        both = R.precedence_blocks(["gov", "arch"], ["arch", "gov"])
        self.assertEqual(sorted(b["source"] for b in both), ["arch", "gov"])
        self.assertEqual(R.precedence_blocks(["a", "b"], ["a", "b"]), [])

    def test_the_source_id_goes_into_the_ref_and_refs_are_unique(self):
        blocks = R.compare_sections(self.BASE, self.BASE.replace("5,000", "6,000"), source_id="architecture")
        self.assertEqual(blocks[0]["ref"], "architecture/1.1")
        many = R.compare_sections(ARCH, ARCH.replace("25,000.00", "30,000.00").replace("3 business days", "4 business days"))
        self.assertEqual(len({b["ref"] for b in many}), len(many))

    def test_a_subsection_change_is_not_a_change_of_its_parent(self):
        blocks = R.compare_sections(self.BASE, self.BASE.replace("5,000", "6,000"))
        self.assertEqual([b["previous_number"] for b in blocks], ["1.1"])

    def test_headings_in_code_fences_are_not_sections(self):
        text = doc(("1", "Rules", "```\n### 9.9 Not a heading\n```"))
        sections, dups = R.split_sections(text)
        self.assertEqual(list(sections), ["1"])
        self.assertEqual(dups, [])

    def test_the_sample_rendering_has_its_thirty_sections_and_a_real_change_is_found(self):
        sections, dups = R.split_sections(ARCH)
        self.assertEqual((len(sections), dups), (30, []))
        blocks = R.compare_sections(ARCH, ARCH.replace("25,000.00", "30,000.00", 1), source_id="architecture")
        self.assertEqual([(b["kind"], b["previous_number"]) for b in blocks], [("modified", "3.5")])

    def test_a_negation_added_to_the_sample_is_meaningful(self):
        changed = ARCH.replace("Approval is required", "Approval is not required", 1)
        if changed == ARCH:
            changed = ARCH.replace(" must ", " must not ", 1)
        blocks = R.compare_sections(ARCH, changed)
        self.assertEqual(len(blocks), 1)
        self.assertFalse(blocks[0]["formatting_only"])

    def test_digests_and_order_are_deterministic(self):
        cur = self.BASE.replace("5,000", "6,000") + "\n## 3 New\n\nText.\n"
        first = R.compare_sections(self.BASE, cur)
        self.assertEqual(first, R.compare_sections(self.BASE, cur))
        self.assertEqual([b["ref"] for b in first], sorted([b["ref"] for b in first], key=lambda r: [int(p) for p in r.replace("none>", "").split(".")]))

    def test_malformed_input_raises_a_clear_error(self):
        for args in ((None, "x"), ("x", None), (b"x", "x"), ("x\x00", "x")):
            with self.assertRaisesRegex(R.ReconcileError, ""):
                R.compare_sections(*args)
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.compare_sections("x", "y", previous_precedence=["a"])
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.compare_sections("x", "y", source_id="a", previous_precedence=["a", "a"], current_precedence=["a"])
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.compare_sections("x", "y", source_id="")


class TestBuildImpactIndex(unittest.TestCase):
    def test_the_sample_has_one_sorted_row_per_item_with_every_field(self):
        plan, specs = sample_plan()
        index, measure = R.build_impact_index(plan, specs)
        self.assertEqual([r["id"] for r in index["rows"]], sorted(it["id"] for it in plan["items"]))
        self.assertEqual(measure["rows"], 9)
        row = next(r for r in index["rows"] if r["tag"] == "WI-03")
        for key in ("id", "tag", "title", "specification", "scope", "acceptance", "sources", "contracts", "dependencies",
                    "decisions", "completion", "conventions"):
            self.assertIn(key, row)
        self.assertEqual(row["title"], "Approval routing engine")
        self.assertTrue(row["specification"]["path"].endswith("m2-route-to-approvers/wi-03-routing-engine.md"))
        self.assertTrue(row["specification"]["present"])
        self.assertEqual(row["completion"], "unknown")
        self.assertEqual(row["sources"][0]["source"], "architecture")
        self.assertIn("3.5", row["sources"][0]["sections"])
        self.assertIn("6.2", row["sources"][0]["only_in_specification"])
        self.assertEqual(row["dependencies"]["depends_on"], ["WI-01"])
        self.assertEqual(row["dependencies"]["unblocks"], ["WI-04", "WI-06", "WI-07"])
        self.assertIn("WI-04", row["dependencies"]["integration"]["counterparts"])
        self.assertIn("Routing (section 3.5)", row["contracts"]["headings"])
        self.assertEqual(row["contracts"]["section"], "Contract")
        self.assertTrue(row["decisions"]["excerpt"])
        self.assertEqual(row["decisions"]["entries"], [])

    def test_conventions_appear_once_at_the_top_and_rows_reference_them(self):
        plan, specs = sample_plan()
        index, _ = R.build_impact_index(plan, specs)
        self.assertIn("EXPENSE_APPROVALS_ENABLED", index["conventions"]["text"])
        self.assertEqual(len({r["conventions"] for r in index["rows"]}), 1)
        self.assertEqual(index["rows"][0]["conventions"], index["conventions"]["id"])
        self.assertIn("Contract tests pass with", index["conventions"]["text"])
        self.assertNotIn("Contract tests pass with", json.dumps(index["rows"]))
        index2, _ = R.build_impact_index(plan, specs, conventions_text="")
        self.assertIsNone(index2["conventions"])
        self.assertTrue(all(r["conventions"] is None for r in index2["rows"]))

    def test_default_budgets_truncate_and_record_omitted_words_and_the_full_path(self):
        plan, specs = sample_plan()
        index, measure = R.build_impact_index(plan, specs)
        self.assertEqual(index["budgets"], {"scope": 60, "acceptance": 100, "decisions": 60})
        for row in index["rows"]:
            self.assertLessEqual(len(row["scope"]["excerpt"].split()), 60)
            self.assertLessEqual(sum(len(c.split()) for c in row["acceptance"]["excerpt"]), 100)
        row = next(r for r in index["rows"] if r["tag"] == "WI-03")
        self.assertGreater(row["scope"]["omitted_words"], 0)
        self.assertEqual(row["scope"]["full_specification"], row["specification"]["path"])
        self.assertGreater(row["acceptance"]["omitted_words"], 0)
        self.assertLess(row["acceptance"]["criteria_shown"], row["acceptance"]["criteria_total"])
        self.assertEqual(row["acceptance"]["criteria_total"], 10)
        self.assertGreater(measure["truncated_fields"], 0)
        self.assertGreater(measure["omitted_words"], 0)

    def test_omitted_words_plus_shown_words_equal_the_whole_field(self):
        why = " ".join(f"w{n}" for n in range(1, 101))
        plan = small_plan([item(1, refs="1")])
        index, _ = R.build_impact_index(plan, {1: spec(why=why)})
        scope = index["rows"][0]["scope"]
        self.assertEqual(len(scope["excerpt"].split()), 60)
        self.assertEqual(scope["omitted_words"], 40)
        self.assertEqual(scope["excerpt"].split()[-1], "w60")
        small, _ = R.build_impact_index(plan, {1: spec(why=why)}, budgets={"scope": 100})
        self.assertEqual(small["rows"][0]["scope"]["omitted_words"], 0)
        self.assertNotIn("full_specification", small["rows"][0]["scope"])
        tiny, _ = R.build_impact_index(plan, {1: spec(why=why, criteria=["one two three", "four five six", "seven eight nine"])},
                                       budgets={"acceptance": 4})
        acceptance = tiny["rows"][0]["acceptance"]
        self.assertEqual(acceptance["excerpt"], ["one two three", "four"])
        self.assertEqual(acceptance["omitted_words"], 5)
        self.assertEqual((acceptance["criteria_shown"], acceptance["criteria_total"]), (2, 3))

    def test_invalid_budgets_and_plans_are_rejected(self):
        plan = small_plan([item(1, refs="1")])
        for bad in ({"scope": 0}, {"scope": "60"}, {"nope": 5}, {"scope": True}, {"scope": 10 ** 6}, []):
            with self.assertRaisesRegex(R.ReconcileError, ""):
                R.build_impact_index(plan, {1: spec()}, budgets=bad)
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.build_impact_index(plan, {2: spec()})
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.build_impact_index(plan, {"1": spec()})
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.build_impact_index(plan, {1: 5})
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.build_impact_index({"items": []}, {})
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.build_impact_index(small_plan([item(1), item(1)]), {})

    def test_decisions_are_an_excerpt_and_the_latest_entries_win(self):
        decisions = "\n".join(f"- 2027-02-0{n}. Entry {n} " + "word " * 20 for n in range(1, 5))
        plan = small_plan([item(1, refs="1")])
        index, _ = R.build_impact_index(plan, {1: spec(decisions=decisions)})
        block = index["rows"][0]["decisions"]
        self.assertTrue(block["excerpt"])
        self.assertEqual(block["entry_count"], 4)
        self.assertGreater(block["omitted_words"], 0)
        self.assertTrue(block["entries"][-1].startswith("2027-02-04"))
        self.assertEqual(block["full_specification"], index["rows"][0]["specification"]["path"])
        given, _ = R.build_impact_index(plan, {1: spec(decisions=decisions)}, decisions_by_item={1: ["2027-03-01. Chose X."]})
        self.assertEqual(given["rows"][0]["decisions"]["entries"], ["2027-03-01. Chose X."])
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.build_impact_index(plan, {1: spec()}, decisions_by_item={1: 5})

    def test_completion_is_unknown_unless_a_record_says_otherwise(self):
        plan = small_plan([item(1, refs="1"), item(2, refs="1", state="closed"), item(3, refs="1")])
        specs = {n: spec() for n in (1, 2, 3)}
        index, _ = R.build_impact_index(plan, specs, completion_by_item={3: "merged in pull request 12"})
        by_id = {r["id"]: r["completion"] for r in index["rows"]}
        self.assertEqual(by_id[1], "unknown")
        self.assertEqual(by_id[2], {"state": "closed", "source": "plan"})
        self.assertEqual(by_id[3], {"state": "merged in pull request 12", "source": "provided"})
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.build_impact_index(plan, specs, completion_by_item={1: ""})

    def test_a_missing_specification_is_a_row_marked_missing(self):
        plan = small_plan([item(1, refs="1"), item(2, refs="2")])
        index, measure = R.build_impact_index(plan, {1: spec()})
        self.assertEqual([r["specification"]["present"] for r in index["rows"]], [True, False])
        self.assertEqual(measure["missing_specifications"], 1)
        self.assertEqual(index["rows"][1]["scope"]["excerpt"], "")

    def test_measure_reports_exact_bytes_words_and_labeled_approximate_tokens(self):
        plan, specs = sample_plan()
        index, measure = R.build_impact_index(plan, specs)
        encoded = json.dumps(index, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.assertEqual(measure["bytes"], len(encoded))
        self.assertEqual(measure["approx_tokens"], -(-len(encoded) // 4))
        self.assertIn("estimate", measure["approx_tokens_method"])
        self.assertGreater(measure["words"], 1000)
        self.assertEqual(measure, R.measure_index(index))
        self.assertEqual(measure["excluded_rows"], 0)

    def test_rows_and_measure_are_deterministic_and_independent_of_input_order(self):
        plan, specs = sample_plan()
        first = R.build_impact_index(plan, specs)
        shuffled = copy.deepcopy(plan)
        shuffled["items"].reverse()
        second = R.build_impact_index(shuffled, dict(reversed(list(specs.items()))))
        self.assertEqual(first, second)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(R.build_impact_index(plan, specs), sort_keys=True))

    def test_inputs_are_not_changed(self):
        plan, specs = sample_plan()
        before = copy.deepcopy(plan)
        R.build_impact_index(plan, specs, public=True)
        self.assertEqual(plan, before)

    def _restricted_plan(self):
        plan = small_plan([item(1, "Open work", refs="1"),
                           item(2, "Secret payroll rules", refs="2", depends=[1], restricted=True,
                                restricted_summary="Payroll work for the finance owner."),
                           item(3, "After the secret", refs="1", depends=[2])])
        specs = {1: spec(why="Open scope."), 2: spec(why="SECRETTEXT payroll."), 3: spec(why="Later scope.")}
        return plan, specs

    def test_public_index_leaves_restricted_rows_out_and_counts_them_only_in_the_measure(self):
        plan, specs = self._restricted_plan()
        index, measure = R.build_impact_index(plan, specs, public=True)
        self.assertEqual([r["id"] for r in index["rows"]], [1, 3])
        self.assertEqual(measure["excluded_rows"], 1)
        text = json.dumps(index)
        self.assertNotIn("SECRETTEXT", text)
        self.assertNotIn("Secret payroll rules", text)
        self.assertNotIn("WI-02", text)
        self.assertNotIn("excluded", text)
        row3 = index["rows"][1]
        self.assertEqual(row3["dependencies"]["depends_on"], [])
        self.assertIn("Payroll work for the finance owner.", row3["dependencies"]["external_input"])

    def test_owner_index_includes_restricted_rows(self):
        plan, specs = self._restricted_plan()
        index, measure = R.build_impact_index(plan, specs, public=False)
        self.assertEqual([r["id"] for r in index["rows"]], [1, 2, 3])
        self.assertEqual(measure["excluded_rows"], 0)
        self.assertIn("SECRETTEXT", json.dumps(index))
        self.assertEqual(index["rows"][2]["dependencies"]["depends_on"], ["WI-02"])


class TestFindDirectConsumers(unittest.TestCase):
    def setUp(self):
        self.plan = small_plan([
            item(1, "Base", refs="1.1", unblocks=[2, 3]),
            item(2, "Waits on base", refs="3", depends=[1]),
            item(3, "Cites the parent", refs="1", depends=[1]),
            item(4, "Cites the whole", refs="whole document"),
            item(5, "Only in the specification", refs="3"),
            item(6, "Contract only", refs="3", integration=""),
            item(7, "Counterpart", refs="3"),
        ])
        self.specs = {
            1: spec(refs=["1.1"], integration="The counterpart is WI-07."),
            2: spec(refs=["3"]),
            3: spec(refs=["1"]),
            4: spec(refs=[]),
            5: spec(refs=["3", "1.1"]),
            6: spec(refs=["3"], contract="Limits, section 1.1. The limit is quoted from the source."),
            7: spec(refs=["3"], integration="The counterpart is WI-01."),
        }
        self.block = {"ref": "architecture/1.1", "kind": "modified", "source": "architecture", "previous_number": "1.1",
                      "current_number": "1.1", "previous_heading": "Limit", "current_heading": "Limit"}

    def one(self, block=None, **kw):
        return R.find_direct_consumers(self.plan, self.specs, [block or self.block], "architecture", **kw)[0]

    def test_a_citation_in_the_plan_or_the_specification_is_a_consumer(self):
        found = self.one()
        by_item = {c["item"]: c for c in found["consumers"]}
        self.assertEqual(by_item[1]["relationship"], "citation")
        self.assertEqual(by_item[1]["via"], ["plan", "specification"])
        self.assertEqual(by_item[5]["relationship"], "citation")
        self.assertEqual(by_item[5]["via"], ["specification"])
        self.assertEqual(by_item[1]["matched_on"], "previous")

    def test_a_parent_citation_and_a_whole_document_citation_share_the_obligation(self):
        by_item = {c["item"]: c for c in self.one()["consumers"]}
        self.assertEqual(by_item[3]["relationship"], "shared-obligation")
        self.assertEqual(by_item[3]["cited"], "1")
        self.assertEqual(by_item[4]["relationship"], "shared-obligation")
        self.assertEqual(by_item[4]["cited"], "whole document")

    def test_a_contract_that_names_the_section_is_a_consumer_when_citations_do_not(self):
        by_item = {c["item"]: c for c in self.one()["consumers"]}
        self.assertEqual(by_item[6]["relationship"], "contract")
        self.assertNotIn(7, by_item)

    def test_a_scheduling_dependency_is_not_a_content_consumer(self):
        found = self.one()
        consumers = {c["item"] for c in found["consumers"]}
        self.assertNotIn(2, consumers)
        related = [r for r in found["related"] if r["item"] == 2]
        self.assertEqual([(r["relationship"], r["content_consumer"]) for r in related], [("dependency", False)])
        self.assertEqual(related[0]["direction"], "waits-on-consumer")

    def test_an_integration_counterpart_is_related_not_a_consumer(self):
        found = self.one()
        self.assertNotIn(7, {c["item"] for c in found["consumers"]})
        self.assertIn(("integration", 7), [(r["relationship"], r["item"]) for r in found["related"]])

    def test_a_block_with_no_citation_has_no_consumers_and_empty_uncited_candidates(self):
        block = dict(self.block, ref="architecture/9.9", previous_number="9.9", current_number="9.9")
        found = self.one(block)
        self.assertEqual([c["item"] for c in found["consumers"]], [4])   # only the whole-document citation
        self.assertEqual(found["related"], [r for r in found["related"] if r["of"] == 4])
        self.assertEqual(found["uncited_candidates"], [])

    def test_a_moved_block_is_found_by_its_previous_and_its_mapped_number(self):
        plan = small_plan([item(1, refs="1.1"), item(2, refs="2.1")])
        specs = {1: spec(refs=["1.1"]), 2: spec(refs=["2.1"])}
        block = {"ref": "architecture/1.1>2.1", "kind": "moved", "source": "architecture", "previous_number": "1.1",
                 "current_number": "2.1", "previous_heading": "Limit", "current_heading": "Limit", "exact_move": True}
        found = R.find_direct_consumers(plan, specs, [block], "architecture")[0]
        self.assertEqual([(c["item"], c["matched_on"]) for c in found["consumers"]], [(1, "previous"), (2, "current")])

    def test_a_removed_block_is_found_by_its_previous_number_only(self):
        plan = small_plan([item(1, refs="1.1"), item(2, refs="2.1")])
        specs = {1: spec(refs=["1.1"]), 2: spec(refs=["2.1"])}
        block = {"ref": "architecture/1.1>none", "kind": "removed", "source": "architecture", "previous_number": "1.1",
                 "current_number": None, "previous_heading": "Limit", "current_heading": None}
        found = R.find_direct_consumers(plan, specs, [block], "architecture")[0]
        self.assertEqual([c["item"] for c in found["consumers"]], [1])

    def test_results_follow_the_block_order_and_are_deterministic(self):
        blocks = [dict(self.block, ref=f"architecture/{n}", previous_number=n, current_number=n) for n in ("3", "1.1")]
        first = R.find_direct_consumers(self.plan, self.specs, blocks, "architecture")
        self.assertEqual([r["block"] for r in first], ["architecture/3", "architecture/1.1"])
        self.assertEqual(first, R.find_direct_consumers(self.plan, self.specs, blocks, "architecture"))

    def test_the_sample_finds_the_consumers_of_a_real_change(self):
        from reconcile_core import compare_sections
        plan, specs = sample_plan()
        blocks = compare_sections(ARCH, ARCH.replace("25,000.00", "30,000.00", 1), source_id="architecture")
        found = R.find_direct_consumers(plan, specs, blocks, "architecture")[0]
        tags = [c["tag"] for c in found["consumers"]]
        self.assertIn("WI-03", tags)
        self.assertIn("WI-06", tags)
        self.assertTrue(all(c["relationship"] in R.CONTENT_RELATIONSHIPS for c in found["consumers"]))
        self.assertTrue(all(r["relationship"] in ("dependency", "integration") for r in found["related"]))

    def test_public_leaves_restricted_items_out(self):
        self.plan["items"][4]["restricted"] = True
        by_item = {c["item"] for c in self.one(public=True)["consumers"]}
        self.assertNotIn(5, by_item)
        self.assertIn(5, {c["item"] for c in self.one()["consumers"]})

    def test_bad_input_raises(self):
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.find_direct_consumers(self.plan, self.specs, [self.block], "other")
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.find_direct_consumers(self.plan, self.specs, [self.block], "")
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.find_direct_consumers(self.plan, self.specs, [dict(self.block, source="other")], "architecture")
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.find_direct_consumers(self.plan, self.specs, [{"ref": "x"}], "architecture")
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.find_direct_consumers(self.plan, self.specs, [self.block, self.block], "architecture")
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.find_direct_consumers(self.plan, self.specs, [dict(self.block, kind="odd")], "architecture")
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.find_direct_consumers(self.plan, self.specs, "blocks", "architecture")


class TestValidateDispositions(unittest.TestCase):
    BLOCKS = [{"ref": "a/1", "kind": "modified", "previous_number": "1", "current_number": "1"},
              {"ref": "a/2", "kind": "removed", "previous_number": "2", "current_number": None},
              {"ref": "a/3", "kind": "modified", "previous_number": "3", "current_number": "3", "formatting_only": True}]

    def good(self):
        return [
            {"block": "a/1", "disposition": "update", "item": 3, "patch": "Change the limit to 6,000."},
            {"block": "a/2", "disposition": "no-impact", "reason": "No item cites it.", "context": "Read the index."},
            {"block": "a/3", "disposition": "no-impact", "reason": "Formatting only.", "context": "Digests are equal."},
        ]

    def codes(self, dispositions, **kw):
        return sorted(p["code"] for p in R.validate_dispositions(self.BLOCKS, dispositions, **kw))

    def test_a_complete_valid_set_has_no_problems(self):
        self.assertEqual(R.validate_dispositions(self.BLOCKS, self.good()), [])

    def test_every_disposition_kind_with_its_required_fields_is_valid(self):
        records = [
            {"disposition": "update", "item": "WI-03", "patch": "p"},
            {"disposition": "add", "scope": "New item for X.", "decision": "Owner chose to add it."},
            {"disposition": "assess-completed", "evidence": "Merged in PR 9.", "follow_up": "Owner decides."},
            {"disposition": "no-impact", "reason": "r", "context": "c"},
            {"disposition": "defer", "consequence": "Old limit stays.", "affected": ["WI-03"], "remaining": "Decide by May."},
            {"disposition": "unresolved", "missing": "The finance owner's answer."},
        ]
        blocks = [{"ref": f"s/{n}", "kind": "added", "previous_number": None, "current_number": str(n)} for n in range(len(records))]
        dispositions = [dict(r, block=b["ref"]) for r, b in zip(records, blocks)]
        self.assertEqual(R.validate_dispositions(blocks, dispositions), [])
        self.assertEqual(sorted(R.REQUIRED_FIELDS), sorted(R.DISPOSITIONS))

    def test_a_block_without_a_disposition_is_a_problem(self):
        problems = R.validate_dispositions(self.BLOCKS, self.good()[:2])
        self.assertEqual([(p["code"], p["block"]) for p in problems], [("missing-disposition", "a/3")])
        self.assertIn("No proposed patch is not no impact", problems[0]["message"])

    def test_formatting_only_blocks_can_be_waived_by_the_caller(self):
        self.assertEqual(self.codes(self.good()[:2]), ["missing-disposition"])
        self.assertEqual(self.codes(self.good()[:2], formatting_only_auto=True), [])
        self.assertEqual(self.codes(self.good()[:1], formatting_only_auto=True), ["missing-disposition"])

    def test_a_duplicate_disposition_is_a_problem(self):
        dispositions = self.good() + [dict(self.good()[0])]
        problems = R.validate_dispositions(self.BLOCKS, dispositions)
        self.assertEqual([(p["code"], p["block"]) for p in problems], [("duplicate-disposition", "a/1")])
        conflicting = self.good() + [{"block": "a/1", "disposition": "unresolved", "missing": "x"}]
        self.assertEqual(self.codes(conflicting), ["duplicate-disposition"])

    def test_an_unknown_block_is_a_problem(self):
        problems = R.validate_dispositions(self.BLOCKS, self.good() + [{"block": "a/99", "disposition": "unresolved", "missing": "x"}])
        self.assertEqual([(p["code"], p["block"]) for p in problems], [("unknown-block", "a/99")])

    def test_missing_fields_are_named(self):
        for record, field in (({"disposition": "update", "item": 3}, "patch"),
                              ({"disposition": "update", "patch": "p"}, "item"),
                              ({"disposition": "no-impact", "reason": "r"}, "context"),
                              ({"disposition": "no-impact", "context": "c"}, "reason"),
                              ({"disposition": "defer", "consequence": "c", "affected": [], "remaining": "r"}, "affected"),
                              ({"disposition": "defer", "consequence": "c", "affected": "WI-03"}, "remaining"),
                              ({"disposition": "unresolved", "missing": "  "}, "missing"),
                              ({"disposition": "add", "scope": "s"}, "decision"),
                              ({"disposition": "assess-completed", "evidence": "e"}, "follow_up")):
            dispositions = self.good()[1:] + [dict(record, block="a/1")]
            problems = R.validate_dispositions(self.BLOCKS, dispositions)
            self.assertEqual([p["code"] for p in problems], ["missing-field"], record)
            self.assertIn(field, problems[0]["message"])

    def test_no_proposed_patch_is_not_a_disposition(self):
        dispositions = self.good()[1:] + [{"block": "a/1", "patch": "Change it."}]
        self.assertEqual([p["code"] for p in R.validate_dispositions(self.BLOCKS, dispositions)], ["patch-without-disposition"])
        dispositions = self.good()[1:] + [{"block": "a/1"}]
        self.assertEqual([p["code"] for p in R.validate_dispositions(self.BLOCKS, dispositions)], ["malformed-record"])
        bad = self.good()[1:] + [{"block": "a/1", "disposition": "no-impact", "reason": "r", "context": "c", "patch": "p"}]
        self.assertEqual([p["code"] for p in R.validate_dispositions(self.BLOCKS, bad)], ["malformed-record"])

    def test_an_unknown_disposition_and_malformed_records_are_problems(self):
        dispositions = self.good()[1:] + [{"block": "a/1", "disposition": "ignore"}, "text", {"disposition": "update"}, 5]
        codes = sorted(p["code"] for p in R.validate_dispositions(self.BLOCKS, dispositions))
        self.assertEqual(codes, ["malformed-record", "malformed-record", "malformed-record", "unknown-disposition"])
        # the unusable record leaves a/1 uncovered only when it never named it
        self.assertNotIn("missing-disposition", codes)

    def test_structurally_wrong_arguments_raise(self):
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.validate_dispositions(self.BLOCKS, {"a/1": {}})
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.validate_dispositions("blocks", [])
        with self.assertRaisesRegex(R.ReconcileError, ""):
            R.validate_dispositions([{"ref": "x", "kind": "modified", "previous_number": "1", "current_number": 5}], [])

    def test_no_blocks_and_no_dispositions_is_valid(self):
        self.assertEqual(R.validate_dispositions([], []), [])

    def test_blocks_from_compare_sections_work_directly(self):
        prev = doc(("1", "A", "One."), ("2", "B", "Two."))
        cur = doc(("1", "A", "One changed."))
        blocks = R.compare_sections(prev, cur, source_id="s")
        self.assertEqual([b["ref"] for b in blocks], ["s/1", "s/2>none"])
        self.assertEqual(len(R.validate_dispositions(blocks, [])), 2)


class TestCheckInputDigests(unittest.TestCase):
    A, B, C, D = (R.sha256_text(x) for x in "abcd")

    def test_identical_digests_are_fresh(self):
        result = R.check_input_digests({"x.md": self.A, "y.md": self.B}, {"y.md": self.B, "x.md": self.A})
        self.assertEqual(result, {"changed": [], "missing": [], "added": [], "fresh": True})

    def test_changed_missing_and_added_are_listed_sorted(self):
        recorded = {"b.md": self.A, "a.md": self.B, "gone.md": self.C, "same.md": self.D}
        current = {"b.md": self.B, "a.md": self.C, "same.md": self.D, "new.md": self.A, "also.md": self.B}
        result = R.check_input_digests(recorded, current)
        self.assertEqual(result["changed"], ["a.md", "b.md"])
        self.assertEqual(result["missing"], ["gone.md"])
        self.assertEqual(result["added"], ["also.md", "new.md"])
        self.assertFalse(result["fresh"])

    def test_one_changed_file_alone_makes_it_stale(self):
        result = R.check_input_digests({"x": self.A}, {"x": self.B})
        self.assertEqual((result["changed"], result["fresh"]), (["x"], False))

    def test_everything_missing_is_stale(self):
        self.assertEqual(R.check_input_digests({"x": self.A}, {})["missing"], ["x"])

    def test_malformed_input_raises(self):
        for recorded, current in (({}, {"x": self.A}), ([], {}), ({"x": self.A}, None), ({"x": "abc"}, {"x": self.A}),
                                  ({"x": self.A.upper()}, {"x": self.A}), ({"x": self.A}, {"": self.A}),
                                  ({"/etc/x": self.A}, {}), ({"../x": self.A}, {}), ({"a\\b": self.A}, {}),
                                  ({"x": 5}, {}), ({"x": self.A}, {"a//b": self.A})):
            with self.assertRaisesRegex(R.ReconcileError, "", msg=repr((recorded, current))):
                R.check_input_digests(recorded, current)

    def test_a_real_file_digest_round_trips(self):
        text = ARCH
        digest = R.sha256_text(text)
        self.assertTrue(R.check_input_digests({"docs/ground-truth/architecture.md": digest},
                                              {"docs/ground-truth/architecture.md": R.sha256_text(text)})["fresh"])
        self.assertFalse(R.check_input_digests({"docs/ground-truth/architecture.md": digest},
                                               {"docs/ground-truth/architecture.md": R.sha256_text(text + "x")})["fresh"])


class TestModuleBoundary(unittest.TestCase):
    def test_it_imports_nothing_with_network_or_token_code(self):
        source = (ROOT / "scripts" / "reconcile_core.py").read_text(encoding="utf-8")
        for name in ("github_client", "github_token", "release_github", "import release ", "subprocess", "urllib", "socket", "open("):
            self.assertNotIn(name, source)

    def test_help_prints_the_module_text(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, ""):
                R.main(["--help"])
        self.assertIn("Pure comparison", out.getvalue())


if __name__ == "__main__":
    unittest.main()
