"""The confidential project fixture stays valid, so later work packages can rely on it.

It is the expense approvals sample plus one restricted source, company-governance. These tests
check its shape and that today's checker accepts it. No token and no network are used.
Run from the repository root: python -m unittest discover -s tests -v
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"


class ConfidentialFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.problems = L.load_plan(FIXTURE / "docs/spec/plan.yaml", FIXTURE)

    def test_the_current_checker_passes_on_the_fixture(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts/check_specs.py"), "--root", str(FIXTURE), "--report"],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("0 finding(s).", run.stdout)
        self.assertEqual(self.problems, [])

    def test_sources_are_classified(self):
        sources = {s["id"]: s for s in self.plan["sources"]}
        self.assertEqual(set(sources), {"architecture", "company-governance"})
        self.assertEqual(sources["architecture"]["classification"], "repo-readers")
        self.assertEqual(sources["company-governance"]["classification"], "restricted")
        for source in sources.values():
            self.assertEqual(source["status"], "reviewed")
            self.assertTrue((FIXTURE / source["path"]).is_file())
            self.assertTrue((FIXTURE / source["source_path"]).is_file())

    def test_the_governance_source_has_the_sections_later_tests_cite(self):
        text = (FIXTURE / "docs/ground-truth/company-governance.md").read_text(encoding="utf-8")
        for heading in ("### 1.5 Sole approver", "### 2.3 Approval limits"):
            self.assertIn(heading, text)
        arch = (FIXTURE / "docs/ground-truth/architecture.md").read_text(encoding="utf-8")
        self.assertIn("### 3.5 Routing", arch)
        self.assertIn("| 500.01 to 5,000.00 | Line manager, department head |", arch)
        self.assertIn("up to 2,500.00 is decided by the line manager alone", text)

    def test_a_spec_cites_a_section_of_the_restricted_source(self):
        item = next(i for i in self.plan["items"] if i["id"] == 6)
        refs = {r["source"]: r["sections"] for r in item["source_refs"]}
        self.assertEqual(refs["company-governance"], "1.5, 2.3")
        spec = (FIXTURE / "docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md").read_text(encoding="utf-8")
        self.assertIn("Company governance policy: Sections 1.5, 2.3", spec)

    def test_people_are_keyed_by_the_plan_ids_and_fictional(self):
        people = L.load_file(FIXTURE / "people.yaml")["people"]
        self.assertEqual({p["id"] for p in people}, {p["id"] for p in self.plan["people"]})
        self.assertTrue(all(p["name"] for p in people))

    def test_the_fixture_stays_small(self):
        self.assertFalse((FIXTURE / "docs/dev").exists())
        self.assertFalse((FIXTURE / "tools").exists())
        total = sum(f.stat().st_size for f in FIXTURE.rglob("*") if f.is_file())
        self.assertLess(total, 400 * 1024)


if __name__ == "__main__":
    unittest.main()
