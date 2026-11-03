"""The six negative tests of the specification (Part G, G1 to G6), collected as one group (work package 11).

The tests themselves live beside the code they test (test_release, test_publication, test_release_verify, test_verifier,
test_verifier_setup) and carry the tag of the negative test they prove, in the first line of their docstring, as `[G1]`, or in
their name, as `test_G1_...`. This module finds them by that tag and runs them as a group, so the continuous integration job
reports G1 to G6 one by one. It adds the tests of G3 that no earlier package could write (the allowlisted projections and the
attested runtime prerequisite), and a few tests that keep the group honest. It duplicates no assertion of the tests it collects.

  python3 tests/test_negative_release.py            run G1 to G6, one after the other, and print one summary line each
  python3 tests/test_negative_release.py G2 G5      run only these
  python3 tests/test_negative_release.py --list     list the collected tests by group
  python3 -m unittest discover -s tests             run the tests of this module only (the collected tests run in their own modules)

The tags and what each negative test proves are in Part G of the specification. Six tests are the agreed minimum, not proof of
complete security: the group says what the fake organization can show, and the real GitHub run of work package 7 is a separate
prerequisite.
"""
import importlib
import re
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
sys.path.insert(0, str(ROOT / "tests"))
import carrydown_lib as L  # noqa: E402
import compile_bundles as CB  # noqa: E402
import fake_evidence as FE  # noqa: E402
import plan_repair as PR  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402

GROUPS = ("G1", "G2", "G3", "G4", "G5", "G6")
STATEMENTS = {
    "G1": "an unapproved draft cannot be exported",
    "G2": "changing approved bytes, destination or audience invalidates approval",
    "G3": "an engineering clone carries no private workspace or staging locator and no withheld source content (configuration separation)",
    "G4": "an expired, withdrawn or superseded release gets the behavior embedded delivery promises",
    "G5": "a modified project checker cannot authorize its own restricted release",
    "G6": "regeneration and repair cannot bypass the release process",
}
FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
TAG = re.compile(r"\[(G[1-6])\]")
NAME_TAG = re.compile(r"^test_(G[1-6])_")
UNCITED_RESTRICTED = ("Records of decisions are kept for 7 years", "Internal audit reads decision records", "Nobody decides their own report")


def tags_of(case):
    """The negative-test tags of one test: from the first lines of its docstring and from its name."""
    method = getattr(case, case._testMethodName, None)
    doc = (getattr(method, "__doc__", None) or "")
    return set(TAG.findall(doc)) | set(NAME_TAG.findall(case._testMethodName))


def modules_with_tags():
    """The test modules whose source mentions a tag. They are found by reading the files, so a module is imported only when it has one."""
    names = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if path.stem != Path(__file__).stem and (re.search(r"\[G[1-6]\]", text) or re.search(r"def test_G[1-6]_", text)):
            names.append(path.stem)
    return names


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def collect():
    """{group: [test, ...]}, in file order. Tests that share a class stay together so the class builds its fixture once."""
    loader = unittest.TestLoader()
    found = {g: [] for g in GROUPS}
    for name in modules_with_tags() + [Path(__file__).stem]:
        module = importlib.import_module(name)
        for case in flatten(loader.loadTestsFromModule(module)):
            for tag in sorted(tags_of(case)):
                found[tag].append(case)
    return found


def group_suite(tests):
    by_class = {}
    for case in tests:
        by_class.setdefault(type(case), []).append(case)
    suite = unittest.TestSuite()
    for cases in by_class.values():
        suite.addTest(unittest.TestSuite(cases))
    return suite


# ---------------------------------------------------------------------------
# G3: what an engineering clone carries
# ---------------------------------------------------------------------------

class ConfigurationSeparationTests(unittest.TestCase):
    """G3 is configuration separation. These tests check the allowlisted projections. They do not claim that the engineer's runtime
    cannot read a known owner-only path: that is an organization-attested prerequisite, which the second test shows is enforced as one."""

    def test_G3_the_released_plan_and_the_bundles_carry_no_private_path_staging_locator_or_withheld_section(self):
        """[G3] The projection is an allowlist: a private key added to the workspace plan later does not appear in the released one."""
        plan, problems = L.load_plan(FIXTURE / "docs" / "spec" / "plan.yaml", FIXTURE)
        self.assertEqual(problems, [])
        plan["project"]["secret_note"] = "STAGING-LOCATOR acme/expense-approvals-releases"
        plan["sources"][1]["private_note"] = "a note about the restricted source"
        released = L.project_released_plan(plan)
        text = PR.dump(released)
        for private in ("secret_note", "private_note", "STAGING-LOCATOR", "source_path:", "classification:", "content_sha256:", "rendering_sha256:",
                        "approvers:", "retain_raw_inputs:", "expense-approvals-releases", ".carrydown", "workspace:"):
            self.assertNotIn(private, text, private)
        for source in released["sources"]:
            self.assertEqual(sorted(source), ["id", "name", "version"])
        files = CB.compile_bundles(plan, FIXTURE / "docs" / "ground-truth", FIXTURE / "docs" / "spec")
        self.assertTrue(files)
        for path, data in files.items():
            blob = data.decode("utf-8")
            for private in UNCITED_RESTRICTED + ("source_path", "docs/source/", "expense-approvals-releases", str(FIXTURE)):
                self.assertNotIn(private, blob, f"{path}: {private}")
            if path.endswith(".bundle.json"):
                side = RS.loads_strict(data)
                self.assertLessEqual(set(side), {"bundle_format", "work_item", "obligations", "conflicts", "shared_with", "downstream", "content_sha256",
                                                 "extensions", "restricted_destination"})
                for obligation in side["obligations"]:
                    self.assertEqual(sorted(obligation), ["heading", "section", "sha256", "source", "version"])

    def test_G3_the_public_receipt_names_no_staging_repository_reviewer_or_private_reason(self):
        """[G3]"""
        world = FE.World()
        candidate = FE.make_candidate(world)
        state = RS.RequestState(candidate.rid, "active", candidate.event["event_id"], None, None)
        receipt = RS.project_receipt(candidate.request, candidate.manifest, state, RS.VerifiedApproval(candidate.rid, "github-review", True)).decode("utf-8")
        for private in (world.entry["staging_repository"], "sct-will", str(FE.OWNER[0]), "reviewer", "review_id", "reason", "policy_commit_sha", "classification", "workspace"):
            self.assertNotIn(private, receipt, private)
        self.assertEqual(sorted(RS.loads_strict(receipt.encode("utf-8"))["approval"]), ["authenticated", "ref", "type"])

    def test_G3_runtime_isolation_is_a_prerequisite_that_an_administrator_attests(self):
        """[G3] Nothing in this test proves that an engineer's agent cannot read an owner-only path. The live doctor refuses to call the
        prerequisite verified without a current administrator attestation of the agent environment."""
        bare = FE.World(attest_runtime=False)
        rows = {c.name: c.status for c in V.verify_prerequisites(bare.reader, bare.enrollment(), workspace_access=True)}
        self.assertNotEqual(rows["runtime-isolation"], V.VERIFIED)
        attested = FE.World(attest_runtime=True)
        rows = {c.name: c.status for c in V.verify_prerequisites(attested.reader, attested.enrollment(), workspace_access=True)}
        self.assertEqual(rows["runtime-isolation"], V.VERIFIED)


# ---------------------------------------------------------------------------
# Keeping the group honest
# ---------------------------------------------------------------------------

class GroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = collect()

    def test_every_negative_test_has_at_least_one_collected_test(self):
        for group in GROUPS:
            self.assertTrue(self.found[group], f"{group} ({STATEMENTS[group]}) has no test")

    def test_the_tags_are_on_tests_that_exist_in_the_modules_the_group_imports(self):
        names = {type(case).__module__ for tests in self.found.values() for case in tests}
        self.assertTrue(names >= {"test_release", "test_release_verify", "test_verifier"}, names)

    def test_the_continuous_integration_workflow_reports_each_group_and_both_scenarios(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("tests/scenario_embedded_release.py", text)
        self.assertIn("tests/test_negative_release.py", text)
        for group in GROUPS:
            self.assertIn(f'"{group}"', text, group)

    def test_the_scenarios_name_every_step_of_the_specification(self):
        import scenario_embedded_release as SC
        steps = {entry["id"].split(".")[0] for entry in SC.ORDER}
        wanted = {f"A{i}" for i in (1, 2, 3)} | {f"B{i}" for i in (1, 2, 3, 4)} | {f"C{i}" for i in range(1, 8)}
        self.assertEqual(sorted(wanted - steps), [], "steps with no named assertion")
        for entry in SC.ORDER:
            self.assertRegex(entry["id"], r"^[ABC][1-7]\.\d+$")
            self.assertTrue(entry["text"].strip())


# ---------------------------------------------------------------------------
# The group runner
# ---------------------------------------------------------------------------

def load_tests(loader, standard_tests, pattern):
    """Under discover this module runs its own tests only. The collected tests run in their own modules there."""
    return standard_tests


def run_group(group, verbosity=2):
    """Run one group. Returns (result, seconds)."""
    started = time.time()
    tests = collect()[group]
    print(f"\n=== {group}: {STATEMENTS[group]} ({len(tests)} test(s)) ===", flush=True)
    result = unittest.TextTestRunner(verbosity=verbosity, stream=sys.stdout).run(group_suite(tests))
    return result, time.time() - started, len(tests)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--list" in args:
        for group, tests in collect().items():
            print(f"{group}: {STATEMENTS[group]}")
            for case in tests:
                print(f"    {type(case).__module__}.{type(case).__name__}.{case._testMethodName}")
        return 0
    wanted = [a for a in args if a != "all"] or list(GROUPS)
    for name in wanted:
        if name not in GROUPS:
            print(f"error: {name!r} is not one of {', '.join(GROUPS)}", file=sys.stderr)
            return 2
    summary = []
    for group in wanted:
        result, seconds, count = run_group(group)
        ok = result.wasSuccessful() and count > 0
        summary.append((group, ok, count, len(result.failures), len(result.errors), len(result.skipped), seconds))
    print("\nNegative tests (Part G)")
    for group, ok, count, failed, errors, skipped, seconds in summary:
        print(f"{'PASS' if ok else 'FAIL'} {group}: {count} test(s), {failed} failure(s), {errors} error(s), {skipped} skipped, {seconds:.1f} s. {STATEMENTS[group]}")
    passed = sum(1 for row in summary if row[1])
    print(f"{passed} of {len(summary)} negative test groups passed")
    return 0 if passed == len(summary) else 1


if __name__ == "__main__":
    sys.exit(main())
