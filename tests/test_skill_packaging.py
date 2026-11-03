"""An installed skill is self-contained.

The installer copies only a skill's own folder. This test copies each skill folder to a temporary
folder, runs it from there with no path to the repository's scripts/ folder, and checks that:
- every script in the copy answers --help;
- the same smoke commands that scripts/selftest.py runs for the installed-skill step succeed;
- the modules the copy imports come from the copy;
- the first skill carries no network or token code.

To cover a new script, add a row to SMOKE: (skill, script, arguments, text the output must hold).
In the arguments, {sample} is the sample project as committed (a released project), {owner} is a copy that holds the owner's working plan, and {fixture} is the confidential project fixture.
No token and no network are used. Run from the repository root:
python -m unittest discover -s tests -v
"""
import ast
import os
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
import sync_skill_assets as SYNC  # noqa: E402

GROUND_TRUTH = "carrydown-ground-truth"
PLAN_TO_GITHUB = "carrydown-plan-to-github"
SKILLS = (GROUND_TRUTH, PLAN_TO_GITHUB)
SAMPLE = ROOT / "sample" / "expense-approvals"
FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"

# (skill, script, arguments, text the output must hold). The first four rows are the commands that
# scripts/selftest.py runs for the installed-skill step. Add a row when a skill gains a script.
SMOKE = [
    (GROUND_TRUTH, "check_specs.py", ["--root", "{sample}", "--quiet"], ()),
    (PLAN_TO_GITHUB, "github_sync.py", ["--root", "{sample}", "--offline", "--show-body", "3"], ()),
    (GROUND_TRUTH, "scaffold_spec.py", ["--root", "{sample}", "--refresh-headers"], ()),
    (PLAN_TO_GITHUB, "generate_dev_skill.py", ["--root", "{sample}"], ("engineers' skill: expense-approvals-dev",)),
    (PLAN_TO_GITHUB, "generate_dev_skill.py", ["--root", "{sample}", "--only", "references"],
     ("would write: references/work-items.md", "would write: references/ground-truth-map.md")),
    (PLAN_TO_GITHUB, "check_specs.py", ["--root", "{sample}", "--quiet"], ()),
    (GROUND_TRUTH, "check_specs.py", ["--root", "{fixture}", "--quiet"], ()),
    (PLAN_TO_GITHUB, "github_project.py", ["--root", "{sample}", "--offline"], ()),
    (PLAN_TO_GITHUB, "github_repair.py", ["--root", "{sample}", "--offline"], ("offline: nothing read from GitHub",)),
    (GROUND_TRUTH, "plan_repair.py", ["--root", "{sample}"], ("Dry run",)),
    (GROUND_TRUTH, "render_ground_truth.py",
     ["{sample}/ground-truth/architecture.md", "--root", "{sample}", "--version", "0.3", "--dry-run"], ()),
    (GROUND_TRUTH, "workspace.py", ["init", "--root", "{sample}", "--slug", "sample-check"], ("DRY RUN", "would create the folder with owner-only permissions")),
    (GROUND_TRUTH, "check_specs.py", ["--root", "{sample}", "--report", "--people", "{sample}/people.yaml"], ("Alloc", "18 of 54d (33%)")),
    (GROUND_TRUTH, "compile_bundles.py", ["--root", "{owner}"], ("WI-06  obligations present: 3 of 3", "18 file(s) would be written")),
    (PLAN_TO_GITHUB, "compile_bundles.py", ["--root", "{owner}"], ("WI-06  obligations present: 3 of 3", "18 file(s) would be written")),
    (PLAN_TO_GITHUB, "release.py", ["preview", "--root", "{owner}", "--repository-id", "4200"], ("What will be shared?", "With whom?", "Where?", "What remains private?")),
    (PLAN_TO_GITHUB, "release.py", ["prepare", "--root", "{owner}", "--repository-id", "4200"], ("DRY RUN", "Dry run: nothing was written")),
    (PLAN_TO_GITHUB, "release.py", ["diff", "--root", "{owner}", "--repository-id", "4200"], ("This is the first release",)),
    (PLAN_TO_GITHUB, "release.py", ["inventory", "--root", "{sample}"], ("carrydown release inventory", "Nothing was changed.")),
    (GROUND_TRUTH, "check_python.py", [], ("is ready",)),
    (PLAN_TO_GITHUB, "check_python.py", [], ("is ready",)),
    (GROUND_TRUTH, "release_gate.py", ["--help"], ("The release gate",)),
    (GROUND_TRUTH, "release_verify.py", ["--help"], ("Verification of releases",)),
    (PLAN_TO_GITHUB, "release_verify.py", ["--help"], ("Verification of releases",)),
]

LIBRARIES = ("carrydown_lib.py",)
NETWORK_MODULES = {"urllib", "http", "socket", "ssl", "ftplib", "smtplib", "requests", "xmlrpc"}


def clean_env(home):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYTHON") and k not in ("CARRYDOWN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "HOME": str(home), "USERPROFILE": str(home)})
    return env


class SkillPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-packaging-")
        cls.base = Path(cls.temp.name)
        cls.home = cls.base / "home"
        cls.home.mkdir()
        cls.work = cls.base / "elsewhere"
        cls.work.mkdir()
        cls.copy = {}
        for skill in SKILLS:
            cls.copy[skill] = cls.base / "installed" / skill
            shutil.copytree(ROOT / "skills" / skill, cls.copy[skill])
        cls.env = clean_env(cls.home)
        cls.owner = copy_sample(cls.base / "owner-sample")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_script(self, skill, script, args):
        path = self.copy[skill] / "scripts" / script
        argv = [sys.executable, str(path)] + [a.format(sample=SAMPLE, fixture=FIXTURE, owner=self.owner) for a in args]
        # the working folder is outside the repository, so nothing resolves to scripts/ by accident
        return subprocess.run(argv, cwd=str(self.work), env=self.env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)

    def scripts(self, skill):
        return sorted(p.name for p in (self.copy[skill] / "scripts").glob("*.py"))

    def test_each_skill_folder_holds_its_instructions_and_scripts(self):
        for skill in SKILLS:
            with self.subTest(skill=skill):
                self.assertTrue((self.copy[skill] / "SKILL.md").is_file())
                self.assertTrue(self.scripts(skill))

    def test_every_script_in_each_copy_answers_help(self):
        for skill in SKILLS:
            for script in self.scripts(skill):
                with self.subTest(skill=skill, script=script):
                    run = self.run_script(skill, script, ["--help"])
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                    self.assertNotIn("Traceback", run.stdout + run.stderr)
                    if script not in LIBRARIES and script != "github_client.py":
                        self.assertIn("usage:", run.stdout.lower(), script)

    def test_smoke_commands_succeed_from_the_copy(self):
        for skill, script, args, wants in SMOKE:
            with self.subTest(skill=skill, script=script, args=" ".join(args)[:60]):
                self.assertIn(script, self.scripts(skill), f"{skill} does not carry {script}")
                run = self.run_script(skill, script, args)
                out = run.stdout + run.stderr
                self.assertEqual(run.returncode, 0, out[-600:])
                self.assertNotIn("Traceback", out)
                for want in wants:
                    self.assertIn(want, out)

    def test_each_copy_carries_exactly_the_scripts_the_inventory_lists(self):
        for skill in SKILLS:
            with self.subTest(skill=skill):
                self.assertEqual(self.scripts(skill), SYNC.closure(SYNC.NEEDS[skill]["scripts"]))

    def test_the_schema_module_ships_in_both_skills_unchanged(self):
        canonical = (ROOT / "scripts" / "release_schema.py").read_bytes()
        for skill in SKILLS:
            with self.subTest(skill=skill):
                self.assertEqual((self.copy[skill] / "scripts" / "release_schema.py").read_bytes(), canonical)

    def test_the_engineers_check_ships_as_a_template_and_runs_once_generated(self):
        template = self.copy[PLAN_TO_GITHUB] / "templates" / "dev-skill" / "scripts" / "check_context.py"
        self.assertTrue(template.is_file())
        self.assertEqual(template.read_bytes(), (ROOT / "templates" / "dev-skill" / "scripts" / "check_context.py").read_bytes())
        self.assertFalse((self.copy[GROUND_TRUTH] / "templates" / "dev-skill").exists(), "the first skill does not generate the engineers' skill")
        project = self.base / "generated-project"
        copy_sample(project, ignore=shutil.ignore_patterns("dev", "release"))
        run = self.run_script(PLAN_TO_GITHUB, "generate_dev_skill.py", ["--root", str(project), "--apply"])
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("write: scripts/check_context.py", run.stdout)
        generated = project / "docs" / "dev" / "skills" / "expense-approvals-dev" / "scripts" / "check_context.py"
        text = generated.read_text(encoding="utf-8")
        self.assertIn('ID_PREFIX = "WI"', text)
        self.assertNotIn("{{", text)
        for args, want, code in ((["--help"], "usage:", 0), (["WI-06", "--root", str(project)], "carrydown: no approved context for WI-06", 10)):
            check = subprocess.run([sys.executable, str(generated)] + args, cwd=str(self.work), env=self.env,
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(check.returncode, code, check.stdout + check.stderr)
            self.assertIn(want, check.stdout.lower() if want == "usage:" else check.stdout)
            self.assertNotIn("Traceback", check.stdout + check.stderr)

    def test_the_helpers_in_the_shared_library_work_from_the_copy(self):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import carrydown_lib as L; "
                "print(L.sha256_text('abc')); print(L.normalize_section_text('a \\r\\n')); "
                "print(L.canonical_json({'b': 1, 'a': 2}).decode().strip()); print(L.workspace_root(sys.argv[2])[1])")
        for skill in SKILLS:
            with self.subTest(skill=skill):
                run = subprocess.run([sys.executable, "-c", code, str(self.copy[skill] / "scripts"), str(self.work)],
                                     cwd=str(self.work), env=self.env, capture_output=True, text=True, timeout=60)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(run.stdout.split("\n")[:5], [
                    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "a", "", '{"a":2,"b":1}', "workspace-unavailable"])

    def test_imports_resolve_inside_the_copy(self):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import carrydown_lib, release_schema; "
                "print(carrydown_lib.__file__); print(release_schema.__file__)")
        for skill in SKILLS:
            with self.subTest(skill=skill):
                run = subprocess.run([sys.executable, "-c", code, str(self.copy[skill] / "scripts")],
                                     cwd=str(self.work), env=self.env, capture_output=True, text=True, timeout=60)
                self.assertEqual(run.returncode, 0, run.stderr)
                home = str(self.copy[skill].resolve())
                for line in run.stdout.split():
                    self.assertEqual(os.path.commonpath([home, str(Path(line).resolve())]), home, line)

    def test_the_first_skill_carries_no_network_or_token_code(self):
        self.assertNotIn("github_client.py", self.scripts(GROUND_TRUTH))
        for script in self.scripts(GROUND_TRUTH):
            tree = ast.parse((self.copy[GROUND_TRUTH] / "scripts" / script).read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    imported.add((node.module or "").split(".")[0])
            with self.subTest(script=script):
                self.assertFalse(imported & NETWORK_MODULES, imported & NETWORK_MODULES)
                self.assertFalse({m for m in imported if m.startswith("github_")}, imported)

    def test_the_schema_module_is_standard_library_only(self):
        tree = ast.parse((ROOT / "scripts" / "release_schema.py").read_text(encoding="utf-8"))
        local = {p.stem for p in (ROOT / "scripts").glob("*.py")} - {"release_schema"}
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            for name in names:
                self.assertNotIn(name, local, name)
                self.assertNotIn(name, NETWORK_MODULES, name)


if __name__ == "__main__":
    unittest.main()
