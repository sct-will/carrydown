"""Tests for scripts/detectors.py: the mechanical leak detectors of the confidential ground truth work.

A detector says where, never what. These tests seed a fake token, a home path, a staffing key and a
copied passage, and check that each is found once, that nothing seeded appears in the output, that an
exception clears only the two kinds that may be excepted, and that valid schema keys are not findings.
No token and no network. Run from the repository root: python -m unittest discover -s tests -v
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import detectors as D  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
SAMPLE = ROOT / "sample" / "expense-approvals"

FAKE_TOKEN = "ghp_FAKEFAKEFAKEFAKE0123456789abcdefghij"
HOME_PATH = "/Users/jdoe/projects/private-notes"
STAFFING_KEY = "days_off"


def restricted_passage(words=22):
    """A run of words from the restricted rendering of the fixture (the company governance policy)."""
    text = (FIXTURE / "docs/ground-truth/company-governance.md").read_text(encoding="utf-8")
    section = text.split("### 2.3 Approval limits", 1)[1].split("###", 1)[0]
    return " ".join(section.split()[:words])


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-detectors-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.workspace = self.base / "workspace"
        (self.workspace / "renderings").mkdir(parents=True)
        self.snap = self.base / "snapshot"
        self.passage = restricted_passage()

    def write(self, rel, text, base=None):
        path = (base or self.snap) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return rel

    def fixture_root(self):
        """A copy of the confidential fixture as the project the workspace belongs to."""
        proj = self.base / "project"
        if not proj.exists():
            shutil.copytree(FIXTURE, proj, ignore=shutil.ignore_patterns("__pycache__"))
        return proj

    def seeded(self):
        self.write("repo/docs/spec/m1/wi-01.md", f"# WI-01\n\nA line.\nDeploy with {FAKE_TOKEN} to staging.\n")
        self.write("repo/docs/spec/m1/wi-02.md", f"# WI-02\n\nRead the notes in {HOME_PATH} first.\n")
        self.write("repo/docs/spec/plan.yaml",
                   f"plan_format: 2\nplan_view: released\nsources:\n  - id: architecture\n    name: \"Architecture\"\n    version: \"0.3\"\n"
                   f"people:\n  - id: tamsin\n    track: workflow\n    {STAFFING_KEY}: [2027-02-22]\n")
        self.write("repo/docs/spec/m1/wi-03.md", f"# WI-03\n\nBackground.\n\n{self.passage}\n\nMore.\n")
        return sorted(str(p.relative_to(self.snap)).replace("\\", "/") for p in self.snap.rglob("*") if p.is_file())

    def run_seeded(self, exceptions=None):
        files = self.seeded()
        project = self.fixture_root()
        return D.run_all(project, self.workspace, {f: self.snap / f for f in files}, exceptions)

    # ---- the four seeded leaks

    def test_four_seeded_leaks_give_exactly_four_findings_and_print_none_of_them(self):
        found = self.run_seeded()
        self.assertEqual(sorted((f[0], f[1]) for f in found), [
            ("copied_restricted", "copied-passage"), ("credentials", "github-token"),
            ("private_paths", "home-path"), ("prohibited_fields", "staffing-field")], found)
        out = "\n".join(D.format_finding(f) for f in found)
        self.assertEqual(len(out.splitlines()), 4)
        for line in out.splitlines():
            self.assertRegex(line, r"^detector:[a-z_]+:[a-z-]+ at \S+:\d+")
        for seeded in (FAKE_TOKEN, "ghp_", HOME_PATH, "jdoe", STAFFING_KEY, "2027-02-22", self.passage,
                       self.passage.split()[0] + " " + self.passage.split()[1], str(self.workspace)):
            self.assertNotIn(seeded, out)

    def test_findings_are_triples_with_a_file_id_and_a_line(self):
        found = self.run_seeded()
        where = {f[0]: f[2] for f in found}
        self.assertEqual(where["credentials"], "repo/docs/spec/m1/wi-01.md:4")
        self.assertEqual(where["private_paths"], "repo/docs/spec/m1/wi-02.md:3")
        self.assertEqual(where["prohibited_fields"], "repo/docs/spec/plan.yaml:10")
        self.assertEqual(where["copied_restricted"], "repo/docs/spec/m1/wi-03.md:5")
        for f in found:
            detector, code, location = f   # unpacks as a triple
            self.assertTrue(detector and code and location)

    def test_a_clean_run_prints_the_clean_line_and_says_it_proves_nothing(self):
        self.write("repo/docs/spec/readme.md", "# Plain\n\nNothing to see here.\n")
        found = D.run_all(self.fixture_root(), self.workspace, {"repo/docs/spec/readme.md": self.snap / "repo/docs/spec/readme.md"})
        self.assertEqual(found, [])
        self.assertEqual(D.report_lines(found), ["detectors: no findings (this does not prove safety)"])

    # ---- exceptions

    def copied_finding(self):
        found = [f for f in self.run_seeded() if f[0] == "copied_restricted"]
        self.assertEqual(len(found), 1)
        return found[0]

    def test_the_copied_passage_finding_carries_the_normalized_digest(self):
        finding = self.copied_finding()
        words = [w for w in re.findall(r"[^\W_]+", self.passage.casefold())]
        import hashlib
        self.assertEqual(finding.passage_sha256, hashlib.sha256(" ".join(words).encode("utf-8")).hexdigest())
        self.assertIn(finding.passage_sha256, D.format_finding(finding))   # the owner needs it to write the exception

    def exception_for(self, finding, **override):
        ex = {"type": "copied_restricted", "passage_sha256": finding.passage_sha256,
              "destinations": ["engineering-repo"], "reason": "The owner approved quoting this rule."}
        ex.update(override)
        return ex

    def test_a_recorded_exception_clears_the_copied_passage_and_appears_in_the_preview(self):
        finding = self.copied_finding()
        ex = self.exception_for(finding)
        remaining = self.run_seeded([ex])
        self.assertEqual(sorted(f[0] for f in remaining), ["credentials", "private_paths", "prohibited_fields"])
        resolution = D.resolve([finding], [ex])
        self.assertEqual(resolution.unresolved, [])
        self.assertEqual(len(resolution.resolved), 1)
        lines = D.exception_preview_lines(resolution)
        self.assertEqual(len(lines), 1)
        self.assertIn("copied_restricted", lines[0])
        self.assertIn(finding.passage_sha256, lines[0])
        self.assertIn("engineering-repo", lines[0])
        self.assertIn("The owner approved quoting this rule.", lines[0])
        self.assertNotIn(self.passage, lines[0])

    def test_an_exception_is_scoped_to_its_passage_and_its_destination(self):
        finding = self.copied_finding()
        wrong_digest = self.exception_for(finding, passage_sha256="0" * 64)
        wrong_place = self.exception_for(finding, destinations=["issue"])
        for ex in (wrong_digest, wrong_place):
            self.assertEqual(D.resolve([finding], [ex]).unresolved, [finding])
        single = self.exception_for(finding)
        single["destination"] = single.pop("destinations")[0]   # the older spelling is read too
        self.assertEqual(D.resolve([finding], [single]).unresolved, [])

    def test_an_exception_for_a_credential_a_path_or_a_field_is_refused(self):
        found = self.run_seeded()
        for kind in ("credentials", "private_paths", "prohibited_fields"):
            finding = next(f for f in found if f[0] == kind)
            ex = {"type": kind, "passage_sha256": "a" * 64, "destinations": ["engineering-repo"], "reason": "Please."}
            resolution = D.resolve([finding], [ex])
            self.assertEqual(resolution.unresolved, [finding], kind)
            self.assertEqual([r[1] for r in resolution.refused], ["exception-not-permitted"], kind)
            remaining = self.run_seeded([ex])
            self.assertIn(("exceptions", "exception-not-permitted"), [(f[0], f[1]) for f in remaining], kind)
            self.assertIn(kind, [f[0] for f in remaining], kind)   # the finding itself stays

    def test_a_malformed_exception_is_refused_and_clears_nothing(self):
        finding = self.copied_finding()
        for bad in ({"type": "copied_restricted"}, "text", {**self.exception_for(finding), "extra": 1},
                    self.exception_for(finding, destinations=[]), self.exception_for(finding, passage_sha256="abc"),
                    self.exception_for(finding, reason=" ")):
            resolution = D.resolve([finding], [bad])
            self.assertEqual(resolution.unresolved, [finding])
            self.assertEqual([r[1] for r in resolution.refused], ["schema-invalid"])

    def test_org_phrases_are_found_in_any_case_and_resolve_by_the_phrase_digest(self):
        (self.workspace / "phrases.txt").write_text("# the organization's own phrases\nProject Nightingale\n\n", encoding="utf-8")
        self.write("repo/docs/spec/readme.md", "# Plan\n\nThis is about PROJECT nightingale in the second quarter.\n")
        found = D.run_all(self.fixture_root(), self.workspace, {"repo/docs/spec/readme.md": self.snap / "repo/docs/spec/readme.md"})
        self.assertEqual([(f[0], f[1], f[2]) for f in found], [("org_phrases", "organization-phrase", "repo/docs/spec/readme.md:3")])
        self.assertNotIn("nightingale", D.format_finding(found[0]).casefold())
        ex = {"type": "org_phrases", "passage_sha256": D.phrase_digest("Project Nightingale"),
              "destinations": ["engineering-repo"], "reason": "A public product name."}
        self.assertEqual(D.resolve(found, [ex]).unresolved, [])

    def test_the_owner_side_detectors_need_the_workspace(self):
        self.seeded()
        files = {p.relative_to(self.snap).as_posix(): p for p in self.snap.rglob("*") if p.is_file()}
        found = D.run_all(self.fixture_root(), None, files)
        self.assertNotIn("copied_restricted", [f[0] for f in found])
        self.assertIn("credentials", [f[0] for f in found])

    def test_bundles_may_quote_what_the_owner_approved(self):
        self.write("repo/docs/context/wi-06.md", f"# Approved context\n\n### company-governance 2.3 Approval limits\n{self.passage}\n")
        found = D.run_all(self.fixture_root(), self.workspace, {"repo/docs/context/wi-06.md": self.snap / "repo/docs/context/wi-06.md"})
        self.assertEqual(found, [])

    # ---- the structural rules

    def test_valid_schema_keys_and_prose_are_not_findings(self):
        self.write("plan.yaml",
                   "plan_format: 2\nplan_view: released\nsources:\n  - id: architecture\n    name: \"Architecture document\"\n    version: \"0.3\"\n"
                   "tracks:\n  - id: workflow\n    label: Workflow\n    skill_needs: [\"Service APIs\"]\n"
                   "people:\n  - id: tamsin\n    track: workflow\n    derived: true\nitems:\n  - id: 1\n    label: \"Use the name and skills fields\"\n")
        self.write("payloads/board/project.json", json.dumps({"fields": [{"name": "Status", "skills": ["none"]}]}))
        self.write("readme.md", "People need skills, a name and days off in a plan. That is ordinary prose.\n")
        self.assertEqual(D.prohibited_fields({k: (self.snap / k).read_text(encoding="utf-8") for k in
                                              ("plan.yaml", "payloads/board/project.json", "readme.md")}), [])

    def test_a_staffing_key_in_people_fails_with_a_location_and_no_value(self):
        for key, value in (("name", '"Tamsin Hale"'), ("github", "tamsin-h"), ("skills", "[Go]"), ("preferences", "[Quiet]"),
                           ("assignment_rationale", "Likes it"), ("days_off", "[2027-02-22]"), ("allocation", "60"), ("start", "2027-02-01")):
            text = f"plan_format: 2\npeople:\n  - id: tamsin\n    track: workflow\n    {key}: {value}\n"
            hits = D.prohibited_fields({"docs/spec/plan.yaml": text})
            self.assertEqual([tuple(h) for h in hits], [("staffing-field", "docs/spec/plan.yaml:5")], key)
        hits = D.prohibited_fields({"plan.yaml": "plan_format: 2\npeople:\n  - id: a\n    track: t\nadvisors:\n  - note: x\n"})
        self.assertEqual([tuple(h) for h in hits], [("advisors-list", "plan.yaml:5")])
        flow = D.prohibited_fields({"plan.yaml": "people:\n  - {id: a, track: t, name: X}\n"})
        self.assertEqual([h[0] for h in flow], ["staffing-field"])

    def test_malformed_structured_files_fail_closed(self):
        files = {"docs/spec/plan.yaml": "people:\n  - id: a\n   name: [broken\n",
                 "payloads/issue/WI-01.json": '{"a": 1, "a": 2}',
                 "payloads/issue/WI-02.json": "{not json",
                 "docs/spec/other.yaml": "key: [unclosed"}
        hits = D.prohibited_fields(files)
        self.assertEqual(sorted(h[0] for h in hits), ["malformed-structured-file"] * 4)
        self.assertEqual(sorted(h[1] for h in hits), sorted(f + ":1" for f in files))

    def test_every_credential_pattern_is_found_once_per_line(self):
        lines = ["ghp_abcdefghijklmnop", "github_pat_11ABCDEFG0abc", "AKIAABCDEFGHIJKLMNOP", "-----BEGIN PRIVATE KEY-----",
                 "api_key = abcdefgh12345", "SECRET: not-a-real-one", "token=xxxxxxxxxx", "ghp_abcdefghijklmnop token: abcdefgh12345"]
        hits = D.credentials({"f.md": "\n".join(lines) + "\n"})
        self.assertEqual([h[1] for h in hits], ["f.md:%d" % n for n in range(1, 9)])   # (code, location)
        self.assertEqual([h[0] for h in hits], ["github-token", "github-token", "access-key", "key-block",
                                                "secret-assignment", "secret-assignment", "secret-assignment", "github-token"])
        self.assertEqual(D.credentials({"f.md": "Tokens begin with ghp_ and keys with AKIA. A short token: abc.\n"}), [])

    def test_private_paths_find_home_folders_the_workspace_and_the_source_folder(self):
        ws = self.base / "my-private-workspace"
        files = {"a.md": "See /home/someone/notes.\n", "b.md": "See C:\\Users\\someone\\notes.\n",
                 "c.md": f"The folder {ws} holds it.\n", "d.md": "Keep originals in docs/source/ only.\n",
                 "e.md": "Nothing private. The users folder and a home page are fine.\n"}
        hits = D.private_paths(files, ws, self.base)
        self.assertEqual({h[1]: h[0] for h in hits}, {"a.md:1": "home-path", "b.md:1": "home-path", "c.md:1": "workspace-path", "d.md:1": "source-folder"})
        allowed = D.private_paths({"d.md": files["d.md"]}, ws, self.base, allow_source_folder=("d.md",))
        self.assertEqual(allowed, [])

    def test_the_pointer_file_names_the_workspace_to_hide(self):
        proj = self.base / "proj"
        (proj / ".carrydown").mkdir(parents=True)
        (proj / ".carrydown" / "local.yaml").write_text("workspace: /elsewhere/secret-workspace\n", encoding="utf-8")
        hits = D.private_paths({"a.md": "Path: /elsewhere/secret-workspace/people.yaml\n"}, None, proj)
        self.assertEqual([tuple(h) for h in hits], [("workspace-path", "a.md:1")])

    def test_destinations_follow_the_snapshot_layout(self):
        self.assertEqual(D.destination_of("repo/docs/spec/plan.yaml"), "engineering-repo")
        self.assertEqual(D.destination_of("repo/docs/dev/skills/x-dev/SKILL.md"), "engineers-skill")
        self.assertEqual(D.destination_of("payloads/issue/WI-01.json"), "issue")
        self.assertEqual(D.destination_of("payloads/epic-comment/rollup.json"), "epic-comment")
        self.assertEqual(D.destination_of("docs/spec/README.md"), "engineering-repo")

    def test_a_file_that_is_not_text_is_not_read(self):
        (self.snap / "repo").mkdir(parents=True)
        (self.snap / "repo" / "image.png").write_bytes(b"\x89PNG ghp_notatoken1234")
        self.assertEqual(D.run_all(self.base, None, ["repo/image.png"]), [])

    # ---- the command line

    def run_cli(self, *args):
        run = subprocess.run([sys.executable, str(ROOT / "scripts/detectors.py")] + [str(a) for a in args],
                             capture_output=True, text=True, encoding="utf-8")
        return run.returncode, run.stdout + run.stderr

    def test_the_command_line_reports_the_sample_clean_and_a_seeded_copy_not(self):
        code, out = self.run_cli("--root", SAMPLE)
        self.assertEqual((code, out.strip()), (0, D.CLEAN_LINE))
        proj = self.base / "sample"
        shutil.copytree(SAMPLE, proj)
        spec = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        spec.write_text(spec.read_text(encoding="utf-8") + f"\nKey: {FAKE_TOKEN}\n", encoding="utf-8")
        code, out = self.run_cli("--root", proj)
        self.assertEqual(code, 1)
        self.assertRegex(out, r"detector:credentials:github-token at docs/spec/m1-submit-report/wi-01-service-scaffold\.md:\d+")
        self.assertNotIn(FAKE_TOKEN, out)

    def test_the_command_line_applies_the_exceptions_of_a_request(self):
        code, out = self.run_cli("--root", SAMPLE, "--request", self.base / "missing.json")
        self.assertEqual(code, 2)
        request = self.base / "request.json"
        request.write_text(json.dumps({"detector_exceptions": []}), encoding="utf-8")
        self.assertEqual(self.run_cli("--root", SAMPLE, "--request", request)[0], 0)


if __name__ == "__main__":
    unittest.main()
