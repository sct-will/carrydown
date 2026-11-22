"""Tests for the obligation-uncited check: a rule that the Contract or the Acceptance criteria of a specification
name must be among the sections the item cites, because the release compiler builds the approved context only from
those citations.

The workspace view runs on a copy of the sample with the owner's working plan and the rendering in docs/ground-truth/.
The released view runs on the sample as committed, and on a copy whose WI-08 bundle lacks the 4.2 obligation, with a
receipt rebuilt for it. Release preparation runs the "yes" path project of tests/mock/release_fixture.py. No token and
no network. Run from the repository root: python -m unittest discover -s tests -v
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "mock"))
from sample_tree import copy_sample  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import check_specs as CS  # noqa: E402
import release_fixture as F  # noqa: E402
import release_schema as RS  # noqa: E402
import test_release_schema as T  # noqa: E402  (its helpers build a request and a receipt)

SAMPLE = ROOT / "sample" / "expense-approvals"
SCRIPT = ROOT / "scripts" / "check_specs.py"
WI01 = "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
WI02 = "docs/spec/m1-submit-report/wi-02-report-form.md"
WI03 = "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md"
WI08 = "docs/spec/m3-enforce-policy/wi-08-notifications-delegates.md"
CITE_42 = re.compile(r"(?m)^- architecture section 4\.2, .*\n")
MESSAGE = ("WI-08: the acceptance criteria name GOV-2.6, which is in section 4.2 of architecture, but the item does not "
           "cite 4.2. Add the citation to the References section or to the plan.")


def check(root, *args):
    r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)] + list(args), capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def edit(path, change):
    text = path.read_text(encoding="utf-8")
    new = change(text)
    assert new != text, f"the edit did not change {path.name}"
    path.write_bytes(new.encode("utf-8"))


def uncited(out):
    return [line.strip()[2:] for line in out.splitlines() if "but the item does not cite" in line]


def rebuild_receipt(root):
    """A receipt that covers the plan and the approved contexts of root as they are now."""
    snap = Path(root).parent / "snapshot"
    shutil.rmtree(snap, ignore_errors=True)
    for path in [root / "docs/spec/plan.yaml"] + sorted((root / "docs/context").glob("*")):
        dst = snap / "repo" / path.relative_to(root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)
    manifest, _ = RS.hash_manifest(snap)
    request = T.make_request(manifest)
    request["request_sha256"] = RS.hash_request(request)
    rid = request["request_sha256"]
    state = RS.RequestState(rid, "active", T.H("event"), None, None)
    receipt = RS.project_receipt(request, manifest, state, RS.VerifiedApproval(rid, "local-owner", False))
    folder = root / "docs/release"
    shutil.rmtree(folder)
    folder.mkdir()
    (folder / f"{rid}.receipt.json").write_bytes(receipt)


class WithTemp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-obligation-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)


class RuleTests(unittest.TestCase):
    def test_only_the_contract_and_the_acceptance_criteria_bind(self):
        text = (SAMPLE / WI03).read_text(encoding="utf-8")
        self.assertIn("GOV-2.4", text.split("## Watch out for", 1)[1])
        self.assertNotIn("GOV-2.4", [ident for _, ident in CS.binding_mentions(text)])

    def test_an_identifier_inside_a_fenced_code_block_is_not_read(self):
        for rel in (WI01, WI02):
            text = (SAMPLE / rel).read_text(encoding="utf-8")
            contract = text.split("## Contract", 1)[1].split("\n## ", 1)[0]
            self.assertIn("GOV-1.3", contract, rel)
            self.assertNotIn("GOV-1.3", [ident for _, ident in CS.binding_mentions(text)], rel)
        fenced = "## Contract\n\n```json\n{\"rule\": \"GOV-1.3\"}\n```\n\n~~~\nGOV-2.1\n~~~\n\n## Acceptance criteria\n\n- [ ] DS-1.2 holds.\n"
        self.assertEqual(CS.binding_mentions(fenced), [("the acceptance criteria name", "DS-1.2")])

    def test_identifiers_are_whole_tokens_and_their_base_is_the_prefix_and_first_number(self):
        text = "## Contract\n\nGOV-2.6, xGOV-1, GOV-1-b, (DS-1.4) and GOV-1.\n"
        self.assertEqual([i for _, i in CS.binding_mentions(text)], ["GOV-2.6", "DS-1.4", "GOV-1"])
        self.assertEqual([CS.ident_base(i) for i in ("GOV-2.6", "DS-1.4", "GOV-1")], ["GOV-2", "DS-1", "GOV-1"])
        self.assertEqual(CS.heading_bases("GOV-2 Audit and retention"), {"GOV-2"})

    def test_a_parent_section_and_the_whole_document_cover(self):
        self.assertTrue(CS.section_is_cited("architecture", "4.2", [("architecture", "4")]))
        self.assertTrue(CS.section_is_cited("architecture", "4.2", [("architecture", "whole document")]))
        self.assertFalse(CS.section_is_cited("architecture", "4.2", [("architecture", "4.1"), ("other", "4.2")]))
        self.assertFalse(CS.section_is_cited("architecture", "4.2", [("architecture", "4.20")]))

    def test_one_cited_candidate_suffices_and_the_message_names_every_candidate(self):
        text = "## Contract\n\nGOV-1.2 applies.\n"
        both = lambda _: [("architecture", "4.1"), ("policy", "2.3")]
        self.assertEqual(CS.obligation_findings("WI-05", text, both, lambda _, c: ("policy", "2.3") in c), [])
        found = CS.obligation_findings("WI-05", text, both, lambda _, c: False)
        self.assertEqual(found, ["WI-05: the contract names GOV-1.2, which is in section 4.1 of architecture or section 2.3 of policy, "
                                 "but the item does not cite 4.1 of architecture or 2.3 of policy. Add the citation to the References "
                                 "section or to the plan."])


class WorkspaceViewTests(WithTemp):
    def project(self):
        return copy_sample(self.base / "sample")

    def test_the_sample_reports_no_findings(self):
        code, out = check(self.project())
        self.assertEqual(code, 0, out)
        self.assertIn("0 with findings", out)

    def test_wi08_without_its_42_citation_names_gov_2_6_and_42(self):
        proj = self.project()
        edit(proj / WI08, lambda t: CITE_42.sub("", t))
        code, out = check(proj)
        self.assertEqual(code, 1, out)
        self.assertIn(MESSAGE, uncited(out))
        self.assertTrue(all("GOV-2" in line and "4.2" in line for line in uncited(out)), out)
        self.assertFalse([line for line in uncited(out) if not line.startswith("WI-08:")], out)

    def test_an_unresolved_identifier_produces_nothing(self):
        proj = self.project()
        text = (proj / WI08).read_text(encoding="utf-8")
        self.assertIn("FR-7", text.split("## Contract", 1)[1].split("\n## ", 1)[0])
        edit(proj / WI03, lambda t: t.replace("## Acceptance criteria\n\n", "## Acceptance criteria\n\n- [ ] FR-1, NFR-3 and BA-6 hold.\n", 1))
        code, out = check(proj)
        self.assertEqual(code, 0, out)

    def test_without_the_fence_the_gov_1_3_mention_would_bind(self):
        proj = self.project()
        edit(proj / WI01, lambda t: t.replace('    "rule": "GOV-1.3",', '    "rule": "GOV-1.3",\n```\n\nGOV-1.3 applies.\n\n```json', 1))
        code, out = check(proj)
        self.assertEqual(code, 1, out)
        self.assertIn("WI-01: the contract names GOV-1.3, which is in section 4.1 of architecture, but the item does not cite 4.1.", out)

    def test_a_parent_citation_covers_the_rule(self):
        proj = self.project()
        edit(proj / WI08, lambda t: CITE_42.sub("- architecture section 4, Governance rules\n", t))
        code, out = check(proj)
        self.assertEqual(uncited(out), [], out)

    def test_a_whole_document_citation_covers_the_rule(self):
        proj = self.project()
        edit(proj / WI08, lambda t: CITE_42.sub("", t))
        edit(proj / "docs/spec/plan.yaml", lambda t: t.replace('sections: "6.1, 6.2, 7.2"', 'sections: "whole document"', 1))
        code, out = check(proj)
        self.assertEqual(uncited(out), [], out)

    def test_a_plan_citation_covers_the_rule(self):
        proj = self.project()
        edit(proj / WI08, lambda t: CITE_42.sub("", t))
        edit(proj / "docs/spec/plan.yaml", lambda t: t.replace('sections: "6.1, 6.2, 7.2"', 'sections: "4.2, 6.1, 6.2, 7.2"', 1))
        code, out = check(proj)
        self.assertEqual(uncited(out), [], out)


class ReleasedViewTests(WithTemp):
    def test_the_sample_reports_no_findings(self):
        code, out = check(SAMPLE, "--view", "released")
        self.assertEqual(code, 0, out)
        self.assertIn("0 with findings", out)

    def released_without_42(self, keep_reference):
        proj = copy_sample(self.base / "released" / "repo", working=False)
        side = proj / "docs/context/wi-08.bundle.json"
        data = RS.loads_strict(side.read_bytes())
        data["obligations"] = [o for o in data["obligations"] if o["section"] != "4.2"]
        side.write_bytes(RS.canonical_json(data))
        if not keep_reference:
            edit(proj / WI08, lambda t: CITE_42.sub("", t))
        rebuild_receipt(proj)
        return proj

    def test_a_bundle_without_the_42_obligation_reports_the_finding(self):
        proj = self.released_without_42(keep_reference=False)
        code, out = check(proj)
        self.assertEqual(code, 1, out)
        self.assertIn(MESSAGE, uncited(out))
        self.assertNotIn("obligation not in the approved context", out)

    def test_with_the_reference_kept_both_findings_appear(self):
        proj = self.released_without_42(keep_reference=True)
        code, out = check(proj)
        self.assertEqual(code, 1, out)
        self.assertIn("obligation not in the approved context: architecture 4.2", out)
        self.assertIn(MESSAGE, uncited(out))

    def test_the_released_rule_reads_only_the_bundles(self):
        known = [("architecture", "4.2", "GOV-2 Audit and retention"), ("architecture", "2.1", "Functional requirements")]
        text = "## Contract\n\nGOV-2.6 and FR-7.\n\n## Acceptance criteria\n\n- [ ] GOV-9 holds.\n"
        self.assertEqual(CS.bundle_obligation_findings("WI-08", text, known[:1], known), [])
        found = CS.bundle_obligation_findings("WI-08", text, known[1:], known)
        self.assertEqual(found, ["WI-08: the contract names GOV-2.6, which is in section 4.2 of architecture, but the item does not "
                                 "cite 4.2. Add the citation to the References section or to the plan."])


class ReleasePreparationTests(WithTemp):
    def test_the_sample_prepares(self):
        yp = F.YesProject(self.base)
        code, out, err = yp.prepare(apply=False)
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("obligation-uncited", out + err)

    def test_preparation_fails_on_wi08_without_its_42_citation(self):
        yp = F.YesProject(self.base)
        edit(yp.root / WI08, lambda t: CITE_42.sub("", t))
        code, out, err = yp.prepare(apply=False)
        self.assertEqual(code, 1, out + err)
        self.assertIn(MESSAGE[:-1] + " (obligation-uncited)", out + err)


if __name__ == "__main__":
    unittest.main()
