"""Destination projections (work package 8, item 1).

templates/projections.yaml lists, for each GitHub destination, the keys a payload may hold, the plan
fields it reads and the specification sections that flow into its body as text or as a link. The
tests prove the default is today's layout byte for byte, that an issue whose approved context holds a
section of a restricted source keeps its seven headings and links the three long sections, and that
the builders refuse a key their projection does not list. No token and no network are used.
"""
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "mock"))
from sample_tree import copy_sample, WORKING_PLAN  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import github_sync as GS  # noqa: E402
import release_assemble as A  # noqa: E402
import release_fixture as F  # noqa: E402
import release_payloads as RP  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
# The digest of the 14 offline bodies of the sample. It was 11e4320d8460658c... until the sample cited its sections in
# source_refs: the only change is the "Ground truth:" line of the nine issues, which now names the source
# ("Architecture document: Sections 3.1, ..."). Every other line of every body is unchanged.
GOLDEN_BODIES = "ed60a4b5f2221d26b341806ba6f96c470255ab75d57ec03f261aa39891cc0a7b"


def headings(body):
    return [ln[4:] for ln in body.split("\n") if ln.startswith("### ")]


def section(spec_text, name):
    m = re.search(rf"(?ms)^## {re.escape(name)}\n(.*?)(?=^## |\Z)", spec_text)
    return m.group(1).strip() if m else ""


class ProjectionFileTests(unittest.TestCase):
    def setUp(self):
        RP._PROJECTIONS.clear()
        self.addCleanup(RP._PROJECTIONS.clear)

    def test_every_github_destination_has_a_default_projection(self):
        doc = RP.load_projections()
        self.assertEqual(set(doc["destinations"]), set(RP.PAYLOAD_KINDS))
        for name in RP.PAYLOAD_KINDS:
            name_, proj = RP.projection(name)
            self.assertEqual(name_, "full")
            self.assertIn("destination_id", proj["payload_fields"])
            self.assertIn("target", proj["payload_fields"])

    def test_the_issue_projection_for_restricted_sources_links_exactly_three_sections(self):
        _, full = RP.projection("issue")
        name, links = RP.projection("issue", restricted_bundle=True)
        self.assertEqual(name, "links")
        changed = sorted(k for k in full["sections"] if full["sections"][k] != links["sections"][k])
        self.assertEqual(changed, ["Acceptance criteria", "Evidence of completion", "Integration points"])
        self.assertTrue(all(links["sections"][k] == "link" for k in changed))
        self.assertEqual(full["payload_fields"], links["payload_fields"])

    def test_no_other_destination_changes_with_a_restricted_bundle(self):
        for name in RP.PAYLOAD_KINDS:
            if name != "issue":
                self.assertEqual(RP.projection(name, restricted_bundle=True)[0], "full")

    def test_a_malformed_file_is_refused(self):
        good = L.read_template("projections.yaml")
        bad_texts = {
            "no destinations": "format: 1\n",
            "a missing destination": good.replace("  label:\n    default: full\n", "  labels:\n    default: full\n", 1),
            "a default that does not exist": good.replace("    default: full\n    projections:\n      full:\n        payload_fields: [destination_id, target, title, body, labels, assignees, relationships, substitutions]\n        plan_fields: [name, epic_title",
                                                          "    default: nothing\n    projections:\n      full:\n        payload_fields: [destination_id, target, title, body, labels, assignees, relationships, substitutions]\n        plan_fields: [name, epic_title", 1),
            "an unknown mode": good.replace("Acceptance criteria: link", "Acceptance criteria: summary", 1),
            "an unknown applies": good.replace("applies: bundle-has-restricted-source", "applies: sometimes", 1),
        }
        for what, text in bad_texts.items():
            with self.subTest(what=what):
                RP._PROJECTIONS.clear()
                with mock.patch.object(L, "read_template", lambda *parts, _t=text: _t):
                    with self.assertRaisesRegex(ValueError, ""):
                        RP.load_projections()

    def test_a_builder_cannot_add_a_key_its_projection_does_not_list(self):
        _, proj = RP.projection("label")
        RP.check_payload_fields("label", {"destination_id": "engineering", "target": {}, "name": "a", "color": "b", "description": "c"}, proj)
        with self.assertRaisesRegex(ValueError, ""):
            RP.check_payload_fields("label", {"destination_id": "engineering", "target": {}, "name": "a", "assignees": ["x"]}, proj)

    def test_every_payload_the_sample_builds_stays_inside_its_projection(self):
        plan, _ = L.load_plan(WORKING_PLAN, SAMPLE)
        files = RP.build_payloads(plan, SAMPLE, flags={"assignees": True, "capacity_summary": True})
        self.assertGreater(len(files), 15)
        for path, data in files.items():
            kind = path.split("/")[1]
            RP.check_payload_fields(kind, json.loads(data), RP.projection(kind)[1])


class DefaultBodiesTests(unittest.TestCase):
    """A release for repository readers whose items cite only repository-readers sources yields today's bodies."""

    def test_the_offline_show_body_output_of_the_sample_is_byte_for_byte_what_it_was(self):
        plan, _ = L.load_plan(WORKING_PLAN, SAMPLE)
        h = hashlib.sha256()
        for it in plan["items"]:
            code, out, err = F.run(GS.run, ["--root", str(SAMPLE), "--offline", "--show-body", str(it["id"])])
            self.assertEqual(code, 0, err)
            h.update(out.encode("utf-8"))
        for ms in plan["milestones"]:
            code, out, err = F.run(GS.run, ["--root", str(SAMPLE), "--offline", "--show-body", f"M{ms['number']}"])
            self.assertEqual(code, 0, err)
            h.update(out.encode("utf-8"))
        self.assertEqual(h.hexdigest(), GOLDEN_BODIES)

    def test_the_payload_bodies_of_a_release_of_the_sample_are_the_legacy_bodies_and_no_issue_uses_links(self):
        with tempfile.TemporaryDirectory(prefix="carrydown-projection-") as tmp:
            root = copy_sample(Path(tmp) / "owner")        # the owner's working tree: a release is prepared from its workspace plan
            asm = A.assemble(root, with_board=False)
            self.assertEqual(asm.problems, [])
            self.assertEqual(asm.link_items, ())
            plan, _ = L.load_plan(WORKING_PLAN, root)
            for it in plan["items"]:
                key = L.tag(plan, it["id"])
                payload = json.loads(asm.files[f"payloads/issue/{key}.json"])
                spec_url = L.github_blob_url(plan, L.spec_path(plan, root, it).relative_to(root).as_posix())
                sent = RP.substitute(payload["body"], {}, spec_url, L.github_tree_url(plan, plan["project"]["dev_skill_path"]))
                self.assertEqual(sent, GS.build_item_body(plan, root, it, mark=False))
                self.assertNotIn("](" + "{{spec_url}}#acceptance-criteria)", payload["body"])
                self.assertEqual(headings(payload["body"]), RP.SEVEN)


class RestrictedSourceTests(unittest.TestCase):
    """The confidential fixture: company-governance is a restricted source and WI-06 cites it."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-projection-")
        cls.np = F.NoProject(Path(cls.temp.name))
        cls.asm = A.assemble(cls.np.root, with_board=False)
        cls.drafts = cls.np.workspace / "drafts"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def body(self, key):
        return json.loads(self.asm.files[f"payloads/issue/{key}.json"])["body"]

    def spec(self, name):
        return next((self.drafts / "docs/spec").rglob(name)).read_text(encoding="utf-8")

    def test_the_assembly_has_no_problem_and_names_the_item_that_cites_a_restricted_source(self):
        self.assertEqual(self.asm.problems, [])
        self.assertEqual(self.asm.link_items, ("WI-06",))

    def test_the_issue_keeps_its_seven_headings_and_has_no_acceptance_text(self):
        body = self.body("WI-06")
        self.assertEqual(headings(body), RP.SEVEN)
        text = self.spec("wi-06-*.md")
        for name in ("Acceptance criteria", "Evidence of completion", "Integration points"):
            section_text = section(text, name)
            self.assertTrue(section_text)
            for line in [ln.strip() for ln in section_text.splitlines() if len(ln.strip()) >= 20]:
                self.assertNotIn(line, body, f"{name}: {line[:40]}")
            self.assertIn(f"[{name}]({{{{spec_url}}}}#{L.anchor_slug(name)})", body)

    def test_the_links_resolve_to_the_specification_when_the_permitted_substitution_is_applied(self):
        payload = json.loads(self.asm.files["payloads/issue/WI-06.json"])
        url = "https://github.com/acme/expense-approvals/blob/main/" + payload["substitutions"]["spec_path"]
        sent = RP.substitute(payload["body"], {}, url, None)
        self.assertIn(f"[Acceptance criteria]({url}#acceptance-criteria)", sent)
        self.assertNotIn("{{", sent.replace("{{skill_url}}", ""))

    def test_an_issue_that_cites_only_repository_readers_sources_keeps_its_text(self):
        body = self.body("WI-03")
        text = self.spec("wi-03-*.md")
        for name in ("Acceptance criteria", "Evidence of completion", "Integration points"):
            line = next(ln.strip() for ln in section(text, name).splitlines() if len(ln.strip()) >= 30 and "WI-" not in ln)
            self.assertIn(line, body)
        self.assertNotIn("#acceptance-criteria", body)

    def test_the_payload_of_a_linked_issue_has_the_same_keys_as_any_other(self):
        a, b = (json.loads(self.asm.files[f"payloads/issue/{k}.json"]) for k in ("WI-06", "WI-03"))
        self.assertEqual(sorted(a), sorted(b))

    def test_the_sub_epic_and_the_other_destinations_are_unchanged(self):
        # a sub-epic body carries its own milestone file's sections, whatever the issues below it cite
        for kind in ("subepic", "epic-comment", "label"):
            self.assertTrue([p for p in self.asm.files if p.startswith(f"payloads/{kind}/")])

    def test_the_preview_says_how_many_issues_hold_links(self):
        import release as R
        import release_build as B
        project = R.Project(self.np.root)
        _, release_id, entries = B.build_manifest(self.asm.files)
        params = {"audience": "repo-readers", "destinations": self.asm.destinations, "targets": [], "sources": self.asm.sources,
                  "downstream": {"assignees": False, "capacity_summary": False, "evidence": "synthetic-only"}, "offline_grace_days": 7,
                  "expires_at": None, "policy_sha256": "0" * 64}
        preview = R.build_preview(project, self.asm, params, entries, None)
        shared = "\n".join(preview["What will be shared"])
        self.assertIn("1 issue(s) hold links instead of the text of Acceptance criteria, Evidence of completion and Integration points", shared)
        self.assertIn("WI-06", shared)


if __name__ == "__main__":
    unittest.main()
