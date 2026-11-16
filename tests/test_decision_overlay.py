"""The decision overlay (design section 10.2): scripts/decision_overlay.py, and the copy of it that the
engineer's check carries (templates/dev-skill/scripts/check_context.py).

validate_overlay decides what an engineer may append to an approved specification. The tests cover the
request-only rule, every accepted and every rejected shape of the "Decisions recorded" section, the
pull request reference, the evidence digest, and that the three places that judge a specification (the
verifier, the engineer's check and the generated skill's wording) agree on one contract: the copy in
check_context.py must be source-identical to the module. No token and no network are used.
Run from the repository root: python -m unittest discover -s tests -v
"""
import ast
import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import decision_overlay as DO  # noqa: E402
import generate_dev_skill as GD  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
MODULE = ROOT / "scripts" / "decision_overlay.py"
TEMPLATE = ROOT / "templates" / "dev-skill" / "scripts" / "check_context.py"

HEAD = "# WI-06 Limits\n\n## Outcome\n\nA promise.\n\n## Acceptance criteria\n\n- [ ] One.\n\n"
TAIL = "\n## Notes\n\nAfter the section.\n"
EMPTY = (HEAD + "## Decisions recorded\n\nNone yet.\n").encode()
ONE = "- 2027-02-10. Used integer cents (pull request 12)."
TWO = "- 2027-02-11. Added a retry (PR #14).\n  It waits two seconds."
WITH_ONE = (HEAD + "## Decisions recorded\n\n" + ONE + "\n").encode()


def check(approved, proposed, policy="allowed", pr=False):
    return DO.validate_overlay(approved, proposed, policy, require_pr_reference=pr)


def body(entries, before="", after=""):
    return (HEAD + "## Decisions recorded\n\n" + before + "".join(e + "\n" for e in entries) + after).encode()


class RequestOnlyTests(unittest.TestCase):
    def test_identical_bytes_pass_and_anything_else_fails(self):
        self.assertEqual(check(EMPTY, EMPTY, "request-only")[:2], (True, "identical"))
        self.assertEqual(check(EMPTY, body([ONE]), "request-only")[:2], (False, "body-changed"))
        self.assertEqual(check(EMPTY, EMPTY + b"\n", "request-only")[:2], (False, "body-changed"))

    def test_an_unknown_policy_and_a_wrong_type_fail_closed(self):
        self.assertEqual(check(EMPTY, EMPTY, "whatever")[:2], (False, "policy-unknown"))
        self.assertEqual(check("text", b"text")[:2], (False, "not-bytes"))


class AllowedTests(unittest.TestCase):
    def test_the_first_entry_replaces_the_placeholder(self):
        result = check(EMPTY, body([ONE]))
        self.assertEqual((result.ok, result.reason, result.entries), (True, "entries-appended", (ONE,)))
        self.assertEqual(result.overlay_sha256, hashlib.sha256(ONE.encode()).hexdigest())

    def test_a_second_entry_may_follow_and_continuation_lines_belong_to_it(self):
        result = check(WITH_ONE, body([ONE, TWO]))
        self.assertEqual((result.ok, result.entries), (True, (TWO,)))
        both = check(EMPTY, body([ONE, "", TWO]))
        self.assertEqual((both.ok, both.entries), (True, (ONE, TWO)))
        self.assertEqual(both.overlay_sha256, hashlib.sha256((ONE + "\n" + TWO).encode()).hexdigest())

    def test_identical_bytes_pass_with_no_entries(self):
        result = check(WITH_ONE, WITH_ONE)
        self.assertEqual((result.ok, result.reason, result.entries, result.overlay_sha256), (True, "identical", (), None))

    def test_the_placeholder_kept_beside_an_entry_is_rejected(self):
        proposed = (HEAD + "## Decisions recorded\n\nNone yet.\n\n" + ONE + "\n").encode()
        self.assertEqual(check(EMPTY, proposed)[:2], (False, "placeholder-kept"))

    def test_the_placeholder_removed_without_an_entry_is_rejected(self):
        for tail in ("## Decisions recorded\n", "## Decisions recorded\n\n", "## Decisions recorded\n\n\n"):
            self.assertEqual(check(EMPTY, (HEAD + tail).encode())[:2], (False, "placeholder-removed"), tail)

    def test_the_placeholder_changed_is_not_a_dated_entry(self):
        proposed = (HEAD + "## Decisions recorded\n\nNone yet\n").encode()
        self.assertEqual(check(EMPTY, proposed)[:2], (False, "entry-undated"))

    def test_an_edited_old_entry_is_rejected(self):
        changed = (HEAD + "## Decisions recorded\n\n- 2027-02-10. Used floats (pull request 12).\n").encode()
        self.assertEqual(check(WITH_ONE, changed)[:2], (False, "entry-edited"))
        self.assertEqual(check(WITH_ONE, changed + b"- 2027-02-11. More (PR 1).\n")[:2], (False, "entry-edited"))

    def test_a_removed_old_entry_is_rejected(self):
        two_entries = body([ONE, TWO])
        self.assertEqual(check(two_entries, body([TWO]))[:2], (False, "entry-edited"))
        self.assertEqual(check(two_entries, body([ONE]))[:2], (False, "entry-edited"))

    def test_text_added_to_the_last_old_entry_is_not_a_new_dated_entry(self):
        self.assertEqual(check(WITH_ONE, body([ONE, "  and one more thing"]))[:2], (False, "entry-undated"))

    def test_an_undated_or_badly_dated_entry_is_rejected(self):
        for line in ("- Used cents (PR 1).", "Used cents (PR 1).", "- 27-02-10. Used cents.", "- 2027-02-30. Used cents.",
                     "- 2027-02-10 Used cents (PR 1).", "* 2027-02-10. Used cents (PR 1).", "### 2027-02-10. Used cents."):
            self.assertEqual(check(EMPTY, body([line]))[:2], (False, "entry-undated"), line)
        self.assertEqual(check(WITH_ONE, body([ONE, TWO, "- an undated bullet after a dated entry"]))[:2], (False, "entry-undated"))

    def test_the_body_outside_the_section_must_match_byte_for_byte(self):
        elsewhere = body([ONE]).replace(b"A promise.", b"A bigger promise.")
        self.assertEqual(check(EMPTY, elsewhere)[:2], (False, "body-changed"))
        after = (HEAD + "## Decisions recorded\n\nNone yet.\n" + TAIL).encode()
        self.assertEqual(check(after, after.replace(b"None yet.\n", (ONE + "\n").encode()))[:2], (True, "entries-appended"))
        self.assertEqual(check(after, after.replace(b"None yet.\n", (ONE + "\n").encode()).replace(b"After the section.", b"Changed."))[:2], (False, "body-changed"))
        self.assertEqual(check(EMPTY, body([ONE]).replace(b"# WI-06", b"# WI-07"))[:2], (False, "body-changed"))

    def test_an_appended_heading_or_section_is_a_change_outside_the_overlay(self):
        for text in (ONE + "\n\n## Another section\n\nText.", ONE + "\n# Top\n"):
            proposed = (HEAD + "## Decisions recorded\n\n" + text + "\n").encode()
            self.assertEqual(check(EMPTY, proposed)[:2], (False, "body-changed"), text)

    def test_line_endings_are_part_of_the_bytes(self):
        crlf = EMPTY.replace(b"\n", b"\r\n")
        proposed = body([ONE]).replace(b"\n", b"\r\n")
        self.assertEqual(check(crlf, proposed)[:2], (True, "entries-appended"))
        self.assertEqual(check(crlf, body([ONE]))[:2], (False, "body-changed"))

    def test_an_approved_file_without_a_final_line_ending_may_gain_one(self):
        approved = WITH_ONE.rstrip(b"\n")
        self.assertEqual(check(approved, body([ONE, TWO]))[:2], (True, "entries-appended"))
        self.assertEqual(check(approved, body([ONE]))[:2], (False, "body-changed"))

    def test_blank_lines_after_the_section_text_may_vary_when_an_entry_is_added(self):
        before = (HEAD + "## Decisions recorded\n\n" + ONE + "\n\n## Notes\n\nText.\n").encode()
        after = (HEAD + "## Decisions recorded\n\n" + ONE + "\n" + TWO.split("\n")[0] + "\n\n## Notes\n\nText.\n").encode()
        self.assertEqual(check(before, after)[:2], (True, "entries-appended"))


class BoundaryTests(unittest.TestCase):
    def test_a_missing_heading_is_rejected(self):
        missing = (HEAD + "None yet.\n").encode()
        self.assertEqual(check(missing, missing + b"x\n")[:2], (False, "boundary-malformed"))
        self.assertEqual(check(EMPTY, missing)[:2], (False, "boundary-malformed"))

    def test_two_headings_are_rejected(self):
        twice = EMPTY + b"\n## Decisions recorded\n\n" + ONE.encode() + b"\n"
        self.assertEqual(check(EMPTY, twice)[:2], (False, "boundary-malformed"))
        self.assertEqual(check(twice, twice + b"- 2027-02-12. More (PR 1).\n")[:2], (False, "boundary-malformed"))

    def test_a_heading_at_another_level_or_with_other_spelling_is_rejected(self):
        for heading in ("### Decisions recorded", "# Decisions recorded", "## decisions recorded", "## Decisions  recorded", "## Decisions recorded ##"):
            proposed = (HEAD + heading + "\n\nNone yet.\n").encode()
            self.assertEqual(check(EMPTY, proposed)[:2], (False, "boundary-malformed"), heading)
        proposed = EMPTY.replace(b"## Decisions recorded", b"### Decisions recorded")
        self.assertEqual(check(EMPTY, proposed + b"")[:2], (False, "boundary-malformed"))

    def test_a_heading_inside_a_code_fence_is_not_a_boundary(self):
        fenced = (HEAD + "```\n## Decisions recorded\n```\n\n## Decisions recorded\n\nNone yet.\n").encode()
        proposed = fenced.replace(b"None yet.\n", (ONE + "\n").encode())
        self.assertEqual(check(fenced, proposed)[:2], (True, "entries-appended"))

    def test_an_open_code_fence_in_a_new_entry_is_rejected(self):
        proposed = body([ONE, "```"])
        self.assertEqual(check(WITH_ONE, proposed)[:2], (False, "boundary-malformed"))


class PullRequestReferenceTests(unittest.TestCase):
    def test_a_reference_is_required_only_when_asked(self):
        bare = body(["- 2027-02-10. Used integer cents."])
        self.assertTrue(check(EMPTY, bare, pr=False).ok)
        self.assertEqual(check(EMPTY, bare, pr=True)[:2], (False, "pr-reference-missing"))

    def test_the_accepted_forms(self):
        for text in ("(pull request 12)", "(PR 12)", "(PR #12)", "in #12", "see https://example.invalid/acme/app/pull/12", "pull request #12"):
            self.assertTrue(check(EMPTY, body([f"- 2027-02-10. Used cents {text}."]), pr=True).ok, text)
        for text in ("(pull request)", "issue 12", "PR12x", "version 12"):
            self.assertEqual(check(EMPTY, body([f"- 2027-02-10. Used cents {text}."]), pr=True)[:2], (False, "pr-reference-missing"), text)

    def test_every_new_entry_needs_one(self):
        proposed = body([ONE, "- 2027-02-11. A second one without a number."])
        self.assertEqual(check(WITH_ONE, proposed, pr=True)[:2], (False, "pr-reference-missing"))

    def test_an_old_entry_without_a_reference_is_not_judged(self):
        approved = body(["- 2027-02-09. An approved entry with no number."])
        self.assertTrue(check(approved, body(["- 2027-02-09. An approved entry with no number.", ONE]), pr=True).ok)


class EvidenceTests(unittest.TestCase):
    def test_the_digest_is_of_the_new_entries_only_and_stable(self):
        first = check(EMPTY, body([ONE, TWO]))
        again = check(WITH_ONE, body([ONE, TWO]))
        self.assertNotEqual(first.overlay_sha256, again.overlay_sha256)
        self.assertEqual(again.overlay_sha256, hashlib.sha256(TWO.encode()).hexdigest())
        crlf = check(EMPTY.replace(b"\n", b"\r\n"), body([ONE, TWO]).replace(b"\n", b"\r\n"))
        self.assertEqual(crlf.overlay_sha256, first.overlay_sha256, "line endings do not change the evidence digest")

    def test_non_text_in_an_entry_is_rejected(self):
        proposed = body([ONE]).replace(b"integer", b"\xff\xfeinteger")
        self.assertEqual(check(EMPTY, proposed)[:2], (False, "encoding-invalid"))

    def test_the_wrapper_in_the_verifier_follows_the_validator(self):
        import release_engineering as RE
        self.assertTrue(RE.decisions_only_change(EMPTY, body([ONE])))
        self.assertTrue(RE.decisions_only_change(EMPTY, EMPTY))
        self.assertFalse(RE.decisions_only_change(WITH_ONE, body([ONE.replace("cents", "floats")])), "an earlier entry is no longer free to edit")
        self.assertFalse(RE.decisions_only_change(EMPTY, body([ONE]).replace(b"A promise.", b"Another.")))


class ThreePlacesAgreeTests(unittest.TestCase):
    """One contract, three places (design sections 10.1 and 15): the verifier imports scripts/decision_overlay.py,
    the engineer's check carries a copy of it, and the generated skill tells the engineer the entry form."""

    @staticmethod
    def nodes(path):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        out = {}
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
                continue        # the module docstring
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            else:
                continue
            for name in names:
                out[name] = ast.get_source_segment(text, node)
        return out

    def test_validate_overlay_and_every_helper_are_source_identical_in_the_check(self):
        module = self.nodes(MODULE)
        copy = self.nodes(TEMPLATE)
        shared = [n for n in module if n not in ("main",)]
        for needed in ("validate_overlay", "OverlayResult", "OVERLAY_HEADING", "OVERLAY_PLACEHOLDER", "OVERLAY_POLICIES",
                       "_overlay_bounds", "_overlay_entries", "_overlay_lines", "_overlay_split_blank", "_overlay_fail", "_overlay_blank"):
            self.assertIn(needed, shared, needed)
        for name in shared:
            self.assertIn(name, copy, f"{name} is missing from check_context.py")
            self.assertEqual(copy[name], module[name], f"{name} differs between decision_overlay.py and check_context.py")

    def test_the_marked_blocks_are_text_identical_too(self):
        def block(path):
            text = path.read_text(encoding="utf-8")
            start = text.index("# --- begin shared overlay code")
            end = text.index("# --- end shared overlay code ---") + len("# --- end shared overlay code ---")
            return text[start:end]
        self.assertEqual(block(MODULE), block(TEMPLATE))

    def test_both_files_say_which_test_enforces_the_copy(self):
        for path in (MODULE, TEMPLATE):
            text = path.read_text(encoding="utf-8")
            self.assertIn("tests/test_decision_overlay.py", text, path.name)
            self.assertIn("source-identical", text, path.name)

    def test_the_generated_skill_states_the_entry_form_the_validator_accepts(self):
        notes = GD.DECISION_NOTES_ALLOWED
        self.assertIn("- YYYY-MM-DD. What you did and why (pull request NN).", notes)
        self.assertIn("None yet.", notes)
        entry = "- 2027-02-10. What you did and why (pull request 12)."
        self.assertTrue(check(EMPTY, body([entry]), pr=True).ok)
        self.assertIn("exits 14", notes)
        self.assertNotIn("append a short entry", GD.DECISION_NOTES_REQUEST_ONLY)

    def test_the_template_imports_only_the_standard_library_for_the_overlay(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertEqual(imported, {"argparse", "datetime", "hashlib", "re", "sys", "typing"})


class ClarificationTests(unittest.TestCase):
    """The engineer's side of design sections 9.1 and 9.2: the request, its routing, its disposition, and the
    words about exit 14, exit 15 and the approved delta in the generated skill (section 10.3)."""

    @classmethod
    def setUpClass(cls):
        cls.plan, problems = L.load_plan(SAMPLE / "docs" / "spec" / "plan.yaml", SAMPLE)
        assert problems == [], problems

    def skill(self, clarification=None, edits=None):
        plan = copy.deepcopy(self.plan)
        if clarification is not None:
            plan["project"]["clarification"] = clarification
        return GD.skill_files(plan, SAMPLE, engineer_edits=edits)

    def test_the_skill_names_the_action_phrase_and_the_fields_of_the_request(self):
        text = self.skill()["SKILL.md"]
        section = text.split("## Raise a specification problem", 1)[1]
        self.assertIn('"This specification seems wrong because [explanation]"', section)
        for field in ("The work item id and the place in its specification", "The problem, with the evidence", "The correction you propose, or the specific question",
                      "Your approved baseline: the request id and the specification digest", "Whether work that does not depend on the question can continue",
                      "A plain next action for the plan owner"):
            self.assertIn(field, section)
        self.assertIn("`Rule clarification request`", section)

    def test_posting_needs_a_yes_and_an_authorized_tool_and_an_unsent_draft_is_labeled(self):
        section = self.skill()["SKILL.md"].split("## Raise a specification problem", 1)[1]
        self.assertIn("Post the request only after the user says yes and has authorized a tool that can post", section)
        self.assertIn('label it "not sent"', section)
        self.assertIn("A draft in the chat is not a delivered request.", section)
        self.assertIn("holds no token and cannot post by itself", section)

    def test_a_request_stays_pending_until_the_owner_decides_on_the_issue(self):
        section = self.skill()["SKILL.md"].split("## Raise a specification problem", 1)[1]
        self.assertIn("stays `pending` until the plan owner marks it `accepted`, `declined` or `deferred` on the issue", section)
        self.assertIn("Where a request goes.", self.skill()["README.md"])
        self.assertIn("`pending` until the plan owner marks it `accepted`, `declined` or `deferred`", self.skill()["README.md"])

    def test_without_a_clarification_block_the_request_goes_to_the_issue_for_the_plan_owner_and_no_login_is_guessed(self):
        self.assertNotIn("clarification", self.plan["project"], "the sample publishes no routing")
        text = self.skill()["SKILL.md"]
        self.assertIn(GD.CLARIFICATION_DEFAULT, text)
        self.assertIn("a comment on the issue of the work item", GD.CLARIFICATION_DEFAULT)
        self.assertIn("does not know the owner's login", GD.CLARIFICATION_DEFAULT)
        self.assertIn("Do not guess a person from the name of the organization or the repository", GD.CLARIFICATION_DEFAULT)
        self.assertNotIn("`@", text.split("## Raise a specification problem", 1)[1])

    def test_a_mention_names_the_approved_login_and_an_issue_channel_names_the_issue(self):
        mention = self.skill({"channel": "mention", "login": "plan-owner-1"})["SKILL.md"]
        self.assertIn("addressed to `@plan-owner-1`", mention)
        self.assertNotIn(GD.CLARIFICATION_DEFAULT, mention)
        issue = self.skill({"channel": "issue", "issue": 42})["SKILL.md"]
        self.assertIn("issue #42", issue)
        self.assertIn("Do not open a new issue for it.", issue)
        self.assertNotIn(GD.CLARIFICATION_DEFAULT, issue)
        self.assertIn("addressed to `@plan-owner-1`", self.skill({"channel": "mention", "login": "plan-owner-1"})["README.md"])

    def test_an_unusable_block_never_puts_text_from_it_into_the_skill(self):
        for block in ({"channel": "mention", "login": "bad login; rm -rf"}, {"channel": "mention"}, {"channel": "issue", "issue": 0},
                      {"channel": "issue", "issue": True}, {"channel": "other", "login": "x"}, "text"):
            text = self.skill(block)["SKILL.md"]
            self.assertIn(GD.CLARIFICATION_DEFAULT, text, block)
            self.assertNotIn("rm -rf", text)

    def test_the_plan_checks_accept_the_block_and_reject_unknown_keys_and_bad_values(self):
        def problems(block):
            plan = copy.deepcopy(self.plan)
            plan["project"]["clarification"] = block
            return L._clarification_problems(plan)
        self.assertEqual(problems({"channel": "mention", "login": "plan-owner-1"}), [])
        self.assertEqual(problems({"channel": "issue", "issue": 7}), [])
        self.assertEqual(L._clarification_problems(self.plan), [], "the block is optional")
        bad = {
            "unknown key": {"channel": "issue", "issue": 7, "email": "x@example.invalid"},
            "no channel": {"login": "plan-owner-1"},
            "bad channel": {"channel": "email", "login": "plan-owner-1"},
            "mention without login": {"channel": "mention"},
            "mention with issue": {"channel": "mention", "login": "plan-owner-1", "issue": 7},
            "issue without number": {"channel": "issue"},
            "issue with login": {"channel": "issue", "issue": 7, "login": "plan-owner-1"},
            "login with a space": {"channel": "mention", "login": "plan owner"},
            "login as a number": {"channel": "mention", "login": 12},
            "issue as text": {"channel": "issue", "issue": "7"},
            "issue zero": {"channel": "issue", "issue": 0},
            "issue negative": {"channel": "issue", "issue": -3},
            "issue boolean": {"channel": "issue", "issue": True},
        }
        for name, block in bad.items():
            self.assertTrue(problems(block), name)
        self.assertNotIn("email", " ".join(problems(bad["unknown key"])).replace("unknown key 'email'", ""), "a value is never echoed")

    def test_the_whole_plan_validation_reports_the_block_and_a_wrong_type(self):
        plan = copy.deepcopy(self.plan)
        self.assertEqual([p for p in L.validate_plan(copy.deepcopy(plan), "released") if "clarification" in p], [])
        plan["project"]["clarification"] = {"channel": "issue", "issue": "7"}
        self.assertTrue([p for p in L.validate_plan(plan, "released") if "project.clarification" in p])
        raw = L.loads((SAMPLE / "docs" / "spec" / "plan.yaml").read_text(encoding="utf-8"))
        raw["project"]["clarification"] = ["mention"]
        self.assertTrue([p for p in L.type_problems(raw) if "project.clarification must be a mapping" in p])

    def test_the_released_plan_keeps_the_block_and_the_key_list_names_it(self):
        self.assertIn("clarification", L.RELEASED_PROJECT_KEYS)

    def test_the_skill_explains_exit_14_and_15_and_the_approved_delta_block(self):
        text = self.skill()["SKILL.md"]
        step2 = text.split("2. Run ", 1)[1].split("\n3. ", 1)[0]
        self.assertIn("On exit 14", step2)
        self.assertIn("On exit 15", step2)
        self.assertIn("carrydown: approved inputs changed since your last check", step2)
        self.assertIn("Reassess your plan against them. Do not continue on the old plan.", step2)
        self.assertIn("load the current approved inputs in full", step2)
        readme = self.skill()["README.md"]
        for message in ("carrydown: the specification for <ID> does not match its approved release",
                        "carrydown: the approved inputs for <ID> come from more than one release"):
            self.assertIn(message, readme)
        self.assertIn("10, 11, 12, 13, 14 and 15", readme)
        section = readme.split("## When the project changes", 1)[1].split("## If you are blocked", 1)[0]
        self.assertIn("Run the check again for your work item", section)
        self.assertIn("docs/spec/README.md", section)
        self.assertIn("never does it for you", section)
        self.assertNotIn("Important: when the project changes", readme, "the owner's notice is not pasted into the engineers' skill")

    def test_the_skill_keeps_its_one_command_first_step_and_runs_nothing_it_discovers(self):
        step2 = self.skill()["SKILL.md"].split("2. Run ", 1)[1].split("\n3. ", 1)[0]
        self.assertTrue(step2.startswith("`python3 <skill folder>/scripts/check_context.py <ID>`"))
        self.assertIn("This is the first command for every work item.", step2)
        self.assertNotIn("npx", self.skill()["SKILL.md"].split("## Raise a specification problem", 1)[1])

    def test_the_decision_notes_wording_follows_the_edit_policy_and_the_check_is_filled_to_match(self):
        allowed, request_only = self.skill(edits="allowed"), self.skill(edits="request-only")
        self.assertIn(GD.DECISION_NOTES_ALLOWED, allowed["SKILL.md"])
        self.assertIn(GD.DECISION_NOTES_REQUEST_ONLY, request_only["SKILL.md"])
        self.assertNotIn(GD.DECISION_NOTES_ALLOWED, request_only["SKILL.md"])
        self.assertIn('ENGINEER_EDITS = "allowed"', allowed["scripts/check_context.py"])
        self.assertIn('ENGINEER_EDITS = "request-only"', request_only["scripts/check_context.py"])
        self.assertIn('SKILL_PATH = "docs/dev/skills/expense-approvals-dev"', allowed["scripts/check_context.py"])
        self.assertNotIn("{{", allowed["scripts/check_context.py"])


if __name__ == "__main__":
    unittest.main()
