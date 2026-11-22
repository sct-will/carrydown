"""The field-run tools: prepare_field_run.py, mechanical_run.py and measure_field_run.py.

prepare_field_run.py builds a self-contained folder for a run of the update path by a fresh agent. These tests
check that the folder is complete, that the two installed skills are exactly the two skills, that the project is
a released git repository with a local origin and a planted engineer entry, and that the revised Word document
renders and differs from the reviewed baseline in the planned sections only. measure_field_run.py is checked on
small synthetic transcripts, one measurement at a time, and on the project state that the expected command
sequence (mechanical_run.py, no agent) leaves.

No token and no network are used. Nothing is pushed. A temporary HOME inside each folder keeps the owner's
workspace away from the real one.
Run from the repository root: python3 -m unittest tests.field_run.test_field_run_kit -v
"""
import contextlib
import hashlib
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))
import measure_field_run as M  # noqa: E402
import mechanical_run as MR  # noqa: E402
import prepare_field_run as P  # noqa: E402
import reconcile_core as RC  # noqa: E402

HAS_GIT = shutil.which("git") is not None
WI03 = P.WI03
WI07 = "docs/spec/m3-enforce-policy/wi-07-audit-log.md"


def quiet(call, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = call(*args)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
    return code, out.getvalue(), err.getvalue()


def prepare(out, *more):
    return quiet(P.main, ["--out", str(out)] + list(more))


def run_in(folder, rel, *cmd):
    """Run a command in folder/rel with the run's own HOME. Returns the completed process."""
    env = dict(os.environ, HOME=str(Path(folder) / "home"), USERPROFILE=str(Path(folder) / "home"), PYTHONDONTWRITEBYTECODE="1")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    for name in ("CARRYDOWN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        env.pop(name, None)
    return subprocess.run([str(c) for c in cmd], cwd=str(Path(folder) / rel), capture_output=True, text=True, env=env)


def vcs(folder, *args):
    return run_in(folder, "project", "git", *args)


def status_text(folder):
    skill = Path(folder) / "install" / "carrydown-ground-truth" / "scripts" / "reconcile.py"
    return run_in(folder, "project", sys.executable, skill, "status", "--root", ".").stdout


def pointer_of(folder):
    """The workspace folder the project's untracked pointer names."""
    text = (Path(folder) / "project" / ".carrydown" / "local.yaml").read_text(encoding="utf-8")
    return text.split("workspace:", 1)[1].strip().strip('"')


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# prepare_field_run.py
# ---------------------------------------------------------------------------

@unittest.skipUnless(HAS_GIT, "git is needed")
class PrepareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-field-prepare-")
        cls.base = Path(cls.temp.name).resolve()
        cls.fr = cls.base / "run"
        code, out, err = prepare(cls.fr)
        if code != 0:
            raise AssertionError(out + err)
        cls.manifest = json.loads((cls.fr / "field-run.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_parts_are_present(self):
        for rel in ("install", "project", "revision", "persona.md", "OWNER_AGENT_BRIEF.md", "OBSERVER_BRIEF.md", "run_logged.py",
                    "field-run.json", "home/.gitconfig", "origin.git", "transcript/questions.md", "transcript/to_owner.md",
                    "transcript/commands.log", "transcript/notes.md", "transcript/observer.md"):
            self.assertTrue((self.fr / rel).exists(), rel)
        for name in ("questions.md", "to_owner.md", "commands.log", "notes.md", "observer.md"):
            self.assertEqual((self.fr / "transcript" / name).read_text(encoding="utf-8"), "", name)

    def test_the_install_folder_holds_exactly_the_two_skills_as_an_installer_places_them(self):
        install = self.fr / "install"
        self.assertEqual(sorted(p.name for p in install.iterdir()), ["carrydown-ground-truth", "carrydown-plan-to-github"])
        for name in P.SKILLS:
            source = ROOT / "skills" / name
            copy = install / name
            self.assertTrue((copy / "SKILL.md").is_file(), name)
            want = sorted(p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
            have = sorted(p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file())
            self.assertEqual(have, want, name)
            for rel in want:
                self.assertEqual(sha_of(copy / rel), sha_of(source / rel), f"{name}/{rel}")
        self.assertFalse((install / "carrydown-ground-truth" / "scripts" / "github_client.py").exists())
        self.assertTrue((install / "carrydown-plan-to-github" / "scripts" / "github_client.py").is_file())
        every = {p.name for p in install.rglob("*") if p.is_file()}
        self.assertFalse(every & {"selftest.py", "AGENTS.md", "README.md.bak", "reconciliation-design.md"})
        self.assertFalse(list(install.rglob("sample")) or list(install.rglob("tests")))

    def test_the_project_is_a_released_git_repository_with_a_local_origin(self):
        project = self.fr / "project"
        self.assertEqual(vcs(self.fr, "status", "--porcelain").stdout.strip(), "")
        self.assertGreaterEqual(len(vcs(self.fr, "log", "--oneline").stdout.splitlines()), 3)
        url = vcs(self.fr, "remote", "get-url", "origin").stdout.strip()
        self.assertEqual(Path(url).resolve(), (self.fr / "origin.git").resolve())
        remote = vcs(self.fr, "ls-remote", "origin", "refs/heads/main").stdout.split()
        self.assertEqual(remote[0], vcs(self.fr, "rev-parse", "HEAD").stdout.strip())
        self.assertEqual(self.manifest["baseline_commit"], remote[0])
        self.assertTrue(list((project / "docs" / "release").glob("*.receipt.json")))
        self.assertTrue((project / "docs" / "dev" / "skills" / "expense-approvals-dev" / "scripts" / "check_context.py").is_file())

    def test_the_workspace_sits_under_the_runs_own_home_and_the_pointer_names_it(self):
        workspace = self.fr / "home" / ".carrydown" / "workspaces" / P.SLUG
        self.assertTrue((workspace / "workspace.yaml").is_file())
        self.assertEqual((self.fr / self.manifest["workspace"]).resolve(), workspace.resolve())
        self.assertEqual(os.path.realpath(pointer_of(self.fr)), os.path.realpath(str(workspace)))
        self.assertTrue((workspace / "drafts" / "plan.yaml").is_file())
        self.assertTrue(list((workspace / "releases").iterdir()))

    def test_the_workspace_holds_the_samples_staffing_overlay_so_the_checker_loads_it(self):
        workspace = self.fr / "home" / ".carrydown" / "workspaces" / P.SLUG
        self.assertEqual(sha_of(workspace / "people.yaml"), sha_of(P.SAMPLE / "people.yaml"))
        script = self.fr / "install" / "carrydown-ground-truth" / "scripts" / "check_specs.py"
        res = run_in(self.fr, "project", sys.executable, script, "--root", ".", "--report")
        self.assertNotIn("people overlay not loaded", res.stdout)
        self.assertNotIn("has no entry for person", res.stdout + res.stderr)
        self.assertIn("0 finding(s)", res.stdout, res.stdout[-600:])

    def test_the_project_starts_released_reviewed_and_unchanged(self):
        text = status_text(self.fr)
        self.assertIn("State: Observable inputs unchanged", text)
        self.assertNotIn("checkpoint is unavailable", text)

    def test_the_engineer_decision_entry_is_planted_committed_and_released(self):
        committed = vcs(self.fr, "show", f"HEAD:{WI03}").stdout
        self.assertIn(P.ENTRY, committed)
        self.assertEqual((self.fr / "project" / WI03).read_text(encoding="utf-8"), committed)
        self.assertNotIn("None yet.", committed.split("## Decisions recorded")[-1])
        original = vcs(self.fr, "show", f"{self.manifest['baseline_commit']}~2:{WI03}").stdout
        self.assertIn("None yet.", original.split("## Decisions recorded")[-1])
        self.assertEqual(self.manifest["planted_entry"], {"path": WI03, "text": P.ENTRY})

    def test_the_revision_exists_as_markdown_and_word_and_changes_the_planned_sections(self):
        revision = self.fr / "revision"
        self.assertEqual(sorted(p.name for p in revision.iterdir()), ["architecture.docx", "architecture.md"])
        original = (P.SAMPLE / "ground-truth" / "architecture.md").read_text(encoding="utf-8")
        revised = (revision / "architecture.md").read_text(encoding="utf-8")
        self.assertEqual(revised, P.revise_architecture(original))
        self.assertIn("after 2 business days", revised)
        self.assertIn("### 4.3 GOV-3 Audit of delegated decisions", revised)
        self.assertEqual([ln for ln in original.split("\n") if ln.startswith("#")], [ln for ln in revised.split("\n") if ln.startswith("#") and "4.3" not in ln])

    def render(self, source):
        """The rendering of the revised document in a scratch project, and the blocks against the reviewed baseline."""
        with tempfile.TemporaryDirectory(prefix="carrydown-field-render-") as tmp:
            script = self.fr / "install" / "carrydown-ground-truth" / "scripts" / "render_ground_truth.py"
            res = subprocess.run([sys.executable, str(script), str(source), "--root", tmp, "--version", "0.4", "--date", "2027-02-10"],
                                 capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertNotIn("warning", res.stdout.lower())
            new = (Path(tmp) / "docs" / "ground-truth" / "architecture.md").read_text(encoding="utf-8")
        old = (self.fr / "project" / "docs" / "ground-truth" / "architecture.md").read_text(encoding="utf-8")
        return RC.compare_sections(old, new, "architecture")

    def test_the_word_document_renders_and_the_changed_sections_are_modified_plus_one_added(self):
        blocks = self.render(self.fr / "revision" / "architecture.docx")
        kinds = {b["ref"]: b["kind"] for b in blocks}
        self.assertEqual(kinds, {"architecture/3.5": "modified", "architecture/4.1": "modified", "architecture/6.2": "modified",
                                 "architecture/none>4.3": "added"})
        self.assertFalse([b for b in blocks if b.get("formatting_only")])
        self.assertFalse([b for b in blocks if b["kind"] in ("moved", "renumbered", "removed", "unreadable")])
        self.assertEqual(sum(1 for b in blocks if b["kind"] == "added"), 1)

    def test_the_markdown_and_the_word_revision_say_the_same_thing(self):
        self.assertEqual(self.render(self.fr / "revision" / "architecture.md"), self.render(self.fr / "revision" / "architecture.docx"))

    def test_the_uncited_rule_is_cited_by_no_specification(self):
        specs = "\n".join(p.read_text(encoding="utf-8") for p in (self.fr / "project" / "docs" / "spec").rglob("*.md"))
        self.assertIsNone(re.search(r"\b4\.3\b", specs))
        self.assertNotIn("GOV-3", specs)
        self.assertEqual(self.manifest["uncited"]["expected_candidate"], "WI-07")

    def test_the_persona_answers_every_question_the_skill_may_ask(self):
        persona = (self.fr / "persona.md").read_text(encoding="utf-8")
        for entry in ("### P1.", "### P2.", "### P3.", "### P4.", "### P5."):
            self.assertIn(entry, persona)
        self.assertIn("not listed here", persona)
        self.assertIn("unnecessary question", persona)
        self.assertIn("shortest truthful answer", persona)
        self.assertIn("revision/architecture.docx", persona)
        self.assertNotIn("reminder", persona.lower())        # the persona does not hand the agent the answer key
        self.assertNotIn("delegate", persona.lower())

    def test_the_owner_agent_brief_gives_the_exact_instructions(self):
        brief = (self.fr / "OWNER_AGENT_BRIEF.md").read_text(encoding="utf-8")
        self.assertIn("> This changed: the revised architecture document is at revision/architecture.docx", brief)
        self.assertEqual(self.manifest["owner_sentence"], "This changed: the revised architecture document is at revision/architecture.docx")
        for text in (str(self.fr / "install"), str(self.fr / "project"), str(self.fr / "home"), "transcript/questions.md",
                     "transcript/commands.log", "transcript/to_owner.md", "transcript/notes.md", "persona.md", "exit=<code>",
                     "Do not touch GitHub", "Where to stop", "DONE", "templates/reconcile-review.md"):
            self.assertIn(text, brief)
        observer = (self.fr / "OBSERVER_BRIEF.md").read_text(encoding="utf-8")
        self.assertIn("measure_field_run.py --dir " + str(self.fr), observer)

    def test_the_helper_logs_a_command_with_its_exit_code_and_runs_with_the_runs_home(self):
        helper = self.fr / "run_logged.py"
        log = self.fr / "transcript" / "commands.log"
        before = log.read_text(encoding="utf-8")
        try:
            res = run_in(self.fr, "project", sys.executable, helper, "--", sys.executable, "-c", "import os,sys; print(os.environ['HOME']); sys.exit(3)")
            self.assertEqual(res.returncode, 3)
            self.assertEqual(res.stdout.strip(), str(self.fr / "home"))
            line = log.read_text(encoding="utf-8").strip().split("\n")[-1]
            self.assertRegex(line, r"^\[\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\] exit=3 \$ ")
            parsed, unparsed = M.parse_commands(line + "\n")
            self.assertEqual((len(parsed), unparsed, parsed[0]["code"]), (1, 0, 3))
        finally:
            log.write_bytes((before).encode("utf-8"))

    def test_a_folder_that_is_not_empty_is_refused_and_the_real_project_flags_go_together(self):
        code, out, err = prepare(self.fr)
        self.assertEqual(code, 2, out + err)
        self.assertIn("not empty", err)
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = prepare(Path(tmp) / "x", "--project", str(self.fr / "project"))
            self.assertEqual(code, 2)
            self.assertIn("go together", err)
            code, out, err = prepare(Path(tmp) / "y", "--establish-checkpoint")
            self.assertEqual(code, 2)

    def test_a_sample_that_changed_under_the_revision_is_reported_and_not_patched_around(self):
        try:
            P.revise_architecture("# A different document\n")
        except ValueError as e:
            self.assertIn("changed", str(e))
        else:
            self.fail("a changed sample was patched around")

    def test_a_real_project_is_copied_with_its_workspace_and_the_original_is_untouched(self):
        workspace = self.fr / "home" / ".carrydown" / "workspaces" / P.SLUG
        head_before = vcs(self.fr, "rev-parse", "HEAD").stdout
        yaml_before = sha_of(workspace / "workspace.yaml")
        with tempfile.TemporaryDirectory(prefix="carrydown-field-real-") as tmp:
            out = Path(tmp).resolve() / "real"
            code, text, err = prepare(out, "--project", str(self.fr / "project"), "--workspace", str(workspace),
                                      "--revised-doc", str(self.fr / "revision" / "architecture.docx"))
            self.assertEqual(code, 0, text + err)
            manifest = json.loads((out / "field-run.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["mode"], "project")
            self.assertIsNone(manifest["planted_entry"])
            self.assertEqual(manifest["probes"], [])
            self.assertEqual(manifest["owner_sentence"], "This changed: the revised architecture document is at revision/architecture.docx")
            self.assertEqual(sorted(p.name for p in (out / "install").iterdir()), list(P.SKILLS))
            self.assertTrue((out / "revision" / "architecture.docx").is_file())
            copied = out / "home" / ".carrydown" / "workspaces" / P.SLUG
            self.assertTrue((copied / "workspace.yaml").is_file())
            self.assertEqual(os.path.realpath(pointer_of(out)), os.path.realpath(str(copied)))
            self.assertEqual(Path(vcs(out, "remote", "get-url", "origin").stdout.strip()).resolve(), (out / "origin.git").resolve())
            self.assertIn("State: Observable inputs unchanged", status_text(out))
            doctor = run_in(out, "project", sys.executable, out / "install" / "carrydown-ground-truth" / "scripts" / "workspace.py", "doctor", "--root", ".")
            self.assertEqual(doctor.returncode, 0, doctor.stdout)
            self.assertNotIn("another engineering folder", doctor.stdout)
        self.assertEqual(vcs(self.fr, "rev-parse", "HEAD").stdout, head_before)
        self.assertEqual(sha_of(workspace / "workspace.yaml"), yaml_before)


# ---------------------------------------------------------------------------
# measure_field_run.py on synthetic transcripts
# ---------------------------------------------------------------------------

def q(number, entry, question="a question", time="2026-11-14T10:00:00Z"):
    return f"## Q{number} {time}\nPersona entry: {entry}\nQuestion: {question}\nAnswer: yes\n\n"


def m(number, text, time="2026-11-14T10:00:00Z"):
    return f"## M{number} {time}\n{text}\n\n"


REVIEW = ("Two specifications need updates. One engineer correction conflicts with the revised source.\n\n"
          "## Proposed updates\n| WI-03 | the reminder | the new number | 3.5 |\n\n## Reviewed and unchanged\n| WI-04 | no change |\n\n"
          "## Decisions needed\n| conflict | WI-03 | which wins |\n\n## Disclosure effects\nNothing new is shared.\n\n"
          "## Next action\nApprove the update, then say Put the plan on GitHub.\n")
STATES = ("Draft reconciliation: accepted. Release: not yet approved. Engineering repository update: pending. Issue updates: pending. "
          "Board updates: pending. Engineer action: required for WI-03. Next, say: Put the plan on GitHub.")


class MeasureFunctionTests(unittest.TestCase):
    def test_a_multi_line_command_is_one_command_and_not_a_line_that_was_not_understood(self):
        log = ("[2026-11-14T10:00:00Z] exit=0 $ python3 -c 'import hashlib\nprint(1)\n'\n"
               "[2026-11-14T10:01:00Z] exit=0 $ python3 /r/install/carrydown-ground-truth/scripts/reconcile.py status --root .\n")
        commands, unparsed = M.parse_commands(log)
        self.assertEqual((len(commands), unparsed), (2, 0))
        self.assertEqual(commands[0]["tokens"][:2], ["python3", "-c"])
        self.assertIn("\n", commands[0]["raw"])
        self.assertEqual(M.parse_commands("stray text\n" + log)[1], 1)
        report = M.measure_deviations(commands, None, None, owner_transcript=False)
        self.assertEqual([d for d in report["deviations"] if d["code"] != "missing-step"], [])
        self.assertIn("python3 -c 'import hashlib print(1)", report["other_commands"][0])

    def test_diff_and_grep_exit_1_are_not_failures_but_other_exit_1_is(self):
        commands = M.parse_commands("[2026-11-14T10:00:00Z] exit=1 $ diff a b\n[2026-11-14T10:01:00Z] exit=1 $ grep -q x f\n"
                                    "[2026-11-14T10:02:00Z] exit=2 $ grep x missing\n[2026-11-14T10:03:00Z] exit=1 $ ls nothing\n")[0]
        failed = [d["command"] for d in M.measure_deviations(commands, None, None, owner_transcript=False)["deviations"] if d["code"] == "command-failed"]
        self.assertEqual(failed, ["grep x missing", "ls nothing"])

    def test_an_unnecessary_question_and_a_repeated_entry_are_counted(self):
        text = q(1, "P2") + q(2, "none", "Can everyone who can read this repository see these documents?") + q(3, "P2") + q(4, "P5") + q(5, "P9")
        qs = M.blocks_of(text, "Q")
        r = M.measure_interactions(qs)
        self.assertEqual(r["count"], 5)
        self.assertEqual([x["number"] for x in r["unnecessary"]], [2, 5])
        self.assertIn("none", r["unnecessary"][0]["why"])
        self.assertEqual(r["repeated"], [{"entry": "P2", "questions": [1, 3]}])
        self.assertEqual(r["approval_question"], 4)

    def test_a_clean_run_has_two_interactions_and_no_unnecessary_question(self):
        r = M.measure_interactions(M.blocks_of(q(1, "P3+P4", time="2026-11-14T10:05:00Z") + q(2, "P5", time="2026-11-14T10:06:30Z"), "Q"))
        self.assertEqual((r["count"], r["unnecessary"], r["repeated"], r["has_approval"]), (2, [], [], True))
        self.assertEqual(r["approval_time"], M.parse_time("2026-11-14T10:06:30Z"))

    def test_a_question_with_no_persona_entry_is_unnecessary(self):
        r = M.measure_interactions(M.blocks_of("## Q1 2026-11-14T10:00:00Z\nQuestion: which python?\n", "Q"))
        self.assertEqual(len(r["unnecessary"]), 1)

    def test_commands_flags_scripts_digests_and_block_references_shown_to_the_owner_are_counted(self):
        digest = "ab" * 32
        messages = M.blocks_of(
            m(1, "Run python3 reconcile.py prepare --root . --apply to save it.") + m(2, f"The proposal id is {digest}.")
            + m(3, "The block architecture/3.5 changed.") + m(4, "Edit dispositions.json by hand.") + m(5, "See the Technical record below.\n## Technical record\nx")
            + m(6, "Two specifications need updates. WI-03 takes the new reminder number from section 3.5.") + m(7, "The digest is not shown."), "M")
        r = M.measure_owner_text(messages)
        by = {h["message"]: h["kinds"] for h in r["hard"]}
        self.assertIn("flag", by[1])
        self.assertIn("script or file name", by[1])
        self.assertIn("digest or identifier", by[2])
        self.assertIn("block reference", by[3])
        self.assertIn("script or file name", by[4])
        self.assertIn("technical record", by[5])
        self.assertNotIn(6, by)
        self.assertEqual([s["message"] for s in r["soft"]], [7])
        self.assertEqual(M.measure_owner_text(M.blocks_of(m(1, "Two specifications need updates."), "M"))["hard"], [])

    def test_one_review_with_the_lead_sentence_is_found_and_a_missing_lead_is_reported(self):
        r = M.measure_review(M.blocks_of(m(1, "Hello.") + m(2, REVIEW), "M"))
        self.assertEqual((r["count"], r["with_lead"]), (1, 1))
        self.assertEqual(r["reviews"][0]["lead_sentence"], "Two specifications need updates. One engineer correction conflicts with the revised source.")
        bare = M.measure_review(M.blocks_of(m(1, REVIEW.split("\n", 2)[2]), "M"))
        self.assertEqual((bare["count"], bare["with_lead"]), (1, 0))
        twice = M.measure_review(M.blocks_of(m(1, REVIEW) + m(2, REVIEW), "M"))
        self.assertEqual(twice["count"], 2)
        shaped = M.measure_review(M.blocks_of(m(1, "**One completed item needs a follow-up decision.**\n\n" + REVIEW.split("\n", 2)[2]), "M"))
        self.assertEqual(shaped["with_lead"], 1)

    def test_the_six_states_and_the_next_action_are_looked_for_in_the_last_messages(self):
        ok = M.measure_states(M.blocks_of(m(1, REVIEW) + m(2, STATES), "M"))
        self.assertEqual((ok["missing"], ok["next_action"]), ([], True))
        weak = M.measure_states(M.blocks_of(m(1, "All done. Engineer action: none."), "M"))
        self.assertIn("Release", weak["missing"])
        self.assertFalse(weak["next_action"])
        self.assertFalse(M.measure_states([])["measured"])

    def test_elapsed_time_runs_from_the_first_command_to_the_approval_question(self):
        log = ("[2026-11-14T10:00:00Z] exit=0 $ python3 /r/run_logged.py -- python3 /r/install/carrydown-ground-truth/scripts/reconcile.py status --root .\n"
               "[2026-11-14T10:03:00Z] exit=0 $ python3 /r/install/carrydown-ground-truth/scripts/reconcile.py prepare --root .\n")
        commands, unparsed = M.parse_commands(log)
        self.assertEqual(unparsed, 0)
        self.assertEqual(commands[0]["tokens"][1].rsplit("/", 1)[-1], "reconcile.py")        # the helper is stripped
        e = M.measure_elapsed(commands, M.parse_time("2026-11-14T10:04:30Z"))
        self.assertEqual((e["to_approval"], e["machine"]), (270.0, 180.0))
        self.assertEqual(M.fmt_seconds(270), "4 min 30 s")
        self.assertIsNone(M.measure_elapsed(commands, None)["to_approval"])

    def test_the_command_log_is_compared_with_the_expected_sequence(self):
        gt = "/r/install/carrydown-ground-truth/scripts/"
        pub = "/r/install/carrydown-plan-to-github/scripts/"

        def log(*cmds):
            lines = []
            for i, (code, cmd) in enumerate(cmds):
                lines.append(f"[2026-11-14T10:{i:02d}:00Z] exit={code} $ {cmd}")
            return M.parse_commands("\n".join(lines) + "\n")[0]

        good = log((0, f"python3 {gt}check_python.py"), (0, f"python3 {gt}reconcile.py status --root ."),
                   (0, f"python3 {gt}render_ground_truth.py ../revision/architecture.docx --root . --version 0.4 --dry-run"),
                   (0, f"python3 {gt}render_ground_truth.py ../revision/architecture.docx --root . --version 0.4"),
                   (0, f"python3 {gt}reconcile.py prepare --root ."), (0, f"python3 {gt}reconcile.py prepare --root . --apply"),
                   (0, f"python3 {gt}reconcile.py check --root . --proposal {'a' * 64}"),
                   (0, f"python3 {gt}reconcile.py apply --root . --proposal {'a' * 64}"),
                   (0, f"python3 {gt}reconcile.py apply --root . --proposal {'a' * 64} --apply"),
                   (0, f"python3 {gt}workspace.py checkpoint prepare --root . --descriptor d.json --rendering-dir docs/ground-truth"),
                   (0, f"python3 {gt}workspace.py checkpoint prepare --root . --descriptor d.json --rendering-dir docs/ground-truth --apply"),
                   (0, f"python3 {gt}workspace.py checkpoint commit --root . --id {'b' * 64}"),
                   (0, f"python3 {gt}workspace.py checkpoint commit --root . --id {'b' * 64} --apply"), (0, "git status"), (0, "cat notes.md"))
        r = M.measure_deviations(good, None, None, owner_transcript=False)
        self.assertEqual(r["deviations"], [])
        self.assertEqual(r["other_commands"], ["git status", "cat notes.md"])
        bad = log((0, f"python3 {gt}reconcile.py prepare --root . --apply"), (0, f"python3 {gt}reconcile.py status --root ."),
                  (0, f"python3 {gt}render_ground_truth.py ../revision/architecture.docx --root ."),
                  (1, f"python3 {gt}reconcile.py check --root . --proposal {'a' * 64}"),
                  (0, f"python3 {gt}reconcile.py apply --root . --proposal {'a' * 64} --apply"),
                  (0, f"python3 {pub}release.py prepare --root ."), (0, "git push origin main"), (2, "curl https://example.com"),
                  (0, f"python3 {pub}reconcile.py status --root ."))
        codes = [d["code"] for d in M.measure_deviations(bad, None, None, owner_transcript=True)["deviations"]]
        for want in ("forbidden-script", "git-write", "network", "no-preview", "apply-without-check", "missing-step", "out-of-order",
                     "compared-before-render", "other-skill", "command-failed", "no-approval-recorded"):
            self.assertIn(want, codes)

    def test_the_patch_command_is_a_known_step_and_needs_its_preview_and_the_saved_proposal(self):
        gt = "/r/install/carrydown-ground-truth/scripts/"
        pid = "a" * 64
        patch = f"python3 {gt}reconcile.py patch --root . --proposal {pid} --block architecture/3.5 --item WI-03 --path x.md --from /t/x.md"
        base = [f"python3 {gt}check_python.py", f"python3 {gt}reconcile.py status --root .",
                f"python3 {gt}render_ground_truth.py ../revision/architecture.docx --root . --version 0.4 --dry-run",
                f"python3 {gt}render_ground_truth.py ../revision/architecture.docx --root . --version 0.4",
                f"python3 {gt}reconcile.py prepare --root .", f"python3 {gt}reconcile.py prepare --root . --apply"]
        tail = [f"python3 {gt}reconcile.py check --root . --proposal {pid}", f"python3 {gt}reconcile.py apply --root . --proposal {pid}",
                f"python3 {gt}reconcile.py apply --root . --proposal {pid} --apply"]

        def log(cmds):
            return M.parse_commands("\n".join(f"[2026-11-14T10:{i:02d}:00Z] exit=0 $ {c}" for i, c in enumerate(cmds)) + "\n")[0]

        good = M.measure_deviations(log(base + [patch, patch + " --apply"] + tail), None, None, owner_transcript=False)
        self.assertEqual([d["code"] for d in good["deviations"] if d["code"] != "missing-step"], [])
        self.assertNotIn(patch, good["other_commands"])
        self.assertIn("patch-write", good["sequence"])
        unpreviewed = M.measure_deviations(log(base + [patch + " --apply"] + tail), None, None, owner_transcript=False)
        self.assertIn("no-preview", [n["code"] for n in unpreviewed["notes"]])
        early = M.measure_deviations(log(base[:4] + [patch, patch + " --apply"] + base[4:] + tail), None, None, owner_transcript=False)
        self.assertIn("patch-before-proposal", [d["code"] for d in early["deviations"]])
        late = M.measure_deviations(log(base + tail + [patch, patch + " --apply"]), None, None, owner_transcript=False)
        self.assertIn("patch-after-apply", [d["code"] for d in late["deviations"]])

    def test_apply_before_the_approval_question_is_a_deviation(self):
        gt = "/r/install/carrydown-ground-truth/scripts/"
        commands = M.parse_commands(
            f"[2026-11-14T10:00:00Z] exit=0 $ python3 {gt}reconcile.py check --root . --proposal {'a' * 64}\n"
            f"[2026-11-14T10:01:00Z] exit=0 $ python3 {gt}reconcile.py apply --root . --proposal {'a' * 64}\n"
            f"[2026-11-14T10:02:00Z] exit=0 $ python3 {gt}reconcile.py apply --root . --proposal {'a' * 64} --apply\n")[0]
        late = M.measure_deviations(commands, None, M.parse_time("2026-11-14T10:05:00Z"))
        self.assertIn("apply-before-approval", [d["code"] for d in late["deviations"]])
        early = M.measure_deviations(commands, None, M.parse_time("2026-11-14T10:01:30Z"))
        self.assertNotIn("apply-before-approval", [d["code"] for d in early["deviations"]])


# ---------------------------------------------------------------------------
# measure_field_run.py on the state the expected command sequence leaves
# ---------------------------------------------------------------------------

@unittest.skipUnless(HAS_GIT, "git is needed")
class MeasureStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="carrydown-field-measure-")
        cls.fr = Path(cls.temp.name).resolve() / "run"
        code, out, err = prepare(cls.fr)
        if code != 0:
            raise AssertionError(out + err)
        code, out, err = quiet(MR.main, ["--dir", str(cls.fr)])
        if code != 0:
            raise AssertionError(out + err)
        cls.run_obj = M.Run(cls.fr)
        cls.proposal = M.find_proposal(cls.run_obj, M.parse_commands((cls.fr / "transcript" / "commands.log").read_text(encoding="utf-8"))[0])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def measure(self):
        return M.measure(self.fr)

    def test_the_mechanical_run_is_reported_correctly_with_zero_owner_interactions(self):
        r = self.measure()
        self.assertEqual(r["interactions"]["count"], 0)
        self.assertFalse(r["owner_transcript"])
        self.assertEqual(r["commands"], 15)
        self.assertEqual(r["deviations"]["deviations"], [])
        self.assertTrue(r["dispositions"]["complete"])
        self.assertEqual((r["dispositions"]["blocks"], r["dispositions"]["check_exit"]), (4, 0))
        self.assertTrue(r["preservation"]["survived"])
        self.assertTrue(r["candidate"]["named"])
        self.assertEqual(r["patches"]["applied_state"], "applied")
        self.assertEqual(len(r["patches"]["patches"]), 5)   # WI-03, WI-06, WI-07, WI-08 and the plan, which gives WI-07 its citation of 4.3
        self.assertTrue(all(p["file_matches_patch"] and p["journal_matches"] and p["allowed_path"] and not p["large"] for p in r["patches"]["patches"]))
        self.assertTrue(all(p["ok"] for p in r["probes"]), r["probes"])
        targets = {name: v for name, v, _ in r["targets"]}
        self.assertEqual(targets["One compact review"], "not measured")
        self.assertEqual(targets["Every changed block has a disposition"], "met")
        self.assertEqual(targets["Deviations from the skill's steps"], "none")

    def test_main_prints_the_report_and_writes_report_md(self):
        code, out, err = quiet(M.main, ["--dir", str(self.fr)])
        self.assertEqual(code, 0, err)
        report = (self.fr / "report.md").read_text(encoding="utf-8")
        self.assertIn("# Field run report", report)
        self.assertIn("## Targets of specification 3.6", report)
        self.assertIn("| Every changed block has a disposition | met |", report)
        self.assertIn("No owner transcript was written", report)
        self.assertIn("report.md", out)
        code, out, err = quiet(M.main, ["--dir", str(self.fr), "--json", "--no-write"])
        self.assertEqual(json.loads(out)["interactions"]["count"], 0)

    def test_a_folder_that_is_not_a_field_run_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = quiet(M.main, ["--dir", tmp])
        self.assertEqual(code, 2)
        self.assertIn("not a field run", err)

    def dispositions_path(self):
        return self.run_obj.proposals / self.proposal / "dispositions.json"

    def test_a_block_with_no_finished_disposition_is_reported(self):
        path = self.dispositions_path()
        original = path.read_text(encoding="utf-8")
        try:
            doc = json.loads(original)
            doc["dispositions"][1] = {"block": doc["dispositions"][1]["block"], "disposition": "pending"}
            del doc["dispositions"][0]
            path.write_bytes((json.dumps(doc)).encode("utf-8"))
            r = M.measure_dispositions(self.run_obj, self.proposal)
            self.assertFalse(r["complete"])
            codes = " ".join(r["problems"])
            self.assertIn("missing-disposition", codes)
            self.assertIn("pending-disposition", codes)
            targets = {name: v for name, v, _ in self.measure()["targets"]}
            self.assertEqual(targets["Every changed block has a disposition"], "not met")
        finally:
            path.write_bytes((original).encode("utf-8"))
        self.assertTrue(M.measure_dispositions(self.run_obj, self.proposal)["complete"])

    def test_the_engineer_entry_surviving_is_detected_and_its_loss_is_too(self):
        spec = self.fr / "project" / WI03
        original = spec.read_text(encoding="utf-8")
        try:
            self.assertTrue(M.measure_preservation(self.run_obj)["survived"])
            spec.write_bytes((original.replace(P.ENTRY, P.ENTRY.replace("3 business days", "2 business days"))).encode("utf-8"))
            self.assertFalse(M.measure_preservation(self.run_obj)["survived"])
            spec.write_bytes((original.replace(P.ENTRY + "\n", "None yet.\n")).encode("utf-8"))
            self.assertFalse(M.measure_preservation(self.run_obj)["survived"])
            targets = {name: v for name, v, _ in self.measure()["targets"]}
            self.assertEqual(targets["Engineer decision entry kept (WI-03)"], "not met")
        finally:
            spec.write_bytes((original).encode("utf-8"))
        self.assertTrue(M.measure_preservation(self.run_obj)["survived"])

    def test_wi_07_named_for_the_uncited_rule_is_detected_in_the_disposition_or_an_owner_message(self):
        path = self.dispositions_path()
        original = path.read_text(encoding="utf-8")
        try:
            self.assertTrue(M.measure_candidate(self.run_obj, self.proposal, [])["in_disposition"])
            doc = json.loads(original)
            for rec in doc["dispositions"]:
                if rec["block"].endswith("4.3"):
                    rec.clear()
                    rec.update({"block": "architecture/none>4.3", "disposition": "no-impact", "reason": "Nothing cites it.", "context": "Read the index."})
            path.write_bytes((json.dumps(doc)).encode("utf-8"))
            missed = M.measure_candidate(self.run_obj, self.proposal, [])
            self.assertEqual((missed["block_found"], missed["in_disposition"], missed["named"]), (True, False, False))
            said = M.measure_candidate(self.run_obj, self.proposal, M.blocks_of(m(1, "The new audit rule in section 4.3 reaches WI-07, the audit log."), "M"))
            self.assertEqual((said["in_disposition"], said["in_owner_message"], said["named"]), (False, True, True))
            unrelated = M.measure_candidate(self.run_obj, self.proposal, M.blocks_of(m(1, "WI-07 is unaffected by the reminder."), "M"))
            self.assertFalse(unrelated["named"])
        finally:
            path.write_bytes((original).encode("utf-8"))
        self.assertTrue(M.measure_candidate(self.run_obj, self.proposal, [])["named"])

    def test_a_patch_whose_file_no_longer_matches_is_reported_and_a_stale_consumer_fails_its_probe(self):
        spec = self.fr / "project" / "docs/spec/m3-enforce-policy/wi-08-notifications-delegates.md"
        original = spec.read_text(encoding="utf-8")
        try:
            spec.write_bytes((original.replace("after 2 business days", "after 3 business days")).encode("utf-8"))
            r = M.measure_patches(self.run_obj, self.proposal)
            wi08 = [p for p in r["patches"] if p["item"] == "WI-08"][0]
            self.assertFalse(wi08["file_matches_patch"])
            probes = {p["name"]: p for p in M.measure_probes(self.run_obj)}
            stale = [p for n, p in probes.items() if n.startswith("WI-08 takes the revised reminder")][0]
            self.assertFalse(stale["ok"])
            self.assertIn("still present", " ".join(stale["problems"]))
            targets = {name: v for name, v, _ in self.measure()["targets"]}
            self.assertEqual(targets["Applied patches match the proposal"], "not met")
        finally:
            spec.write_bytes((original).encode("utf-8"))
        self.assertTrue(all(p["file_matches_patch"] for p in M.measure_patches(self.run_obj, self.proposal)["patches"]))

    def test_a_whole_file_rewrite_is_flagged_as_a_large_patch(self):
        path = self.dispositions_path()
        original = path.read_text(encoding="utf-8")
        try:
            doc = json.loads(original)
            for rec in doc["dispositions"]:
                if rec["block"] == "architecture/4.1":
                    rec["patch"]["after_text"] = "# Rewritten\n\n" + "\n".join(f"line {i}" for i in range(200)) + "\n"
            path.write_bytes((json.dumps(doc)).encode("utf-8"))
            wi06 = [p for p in M.measure_patches(self.run_obj, self.proposal)["patches"] if p["item"] == "WI-06"][0]
            self.assertTrue(wi06["large"])
        finally:
            path.write_bytes((original).encode("utf-8"))

    def stamped_log(self, original):
        """commands.log with one line per minute from 10:00, so the times are fixed."""
        out = []
        for i, line in enumerate(original.strip().split("\n")):
            out.append(f"[2026-11-14T10:{i:02d}:00Z]" + line.split("]", 1)[1])
        return "\n".join(out) + "\n"

    def test_a_synthetic_transcript_over_the_state_gives_the_owner_measurements_in_the_report(self):
        t = self.fr / "transcript"
        files = {name: (t / name).read_text(encoding="utf-8") for name in ("questions.md", "to_owner.md", "commands.log")}
        try:
            (t / "to_owner.md").write_bytes((m(1, REVIEW, "2026-11-14T10:05:00Z") + m(2, STATES, "2026-11-14T10:12:00Z")).encode("utf-8"))
            (t / "questions.md").write_bytes((q(1, "P3+P4", time="2026-11-14T10:05:10Z") + q(2, "P5", time="2026-11-14T10:06:00Z")).encode("utf-8"))
            (t / "commands.log").write_bytes((self.stamped_log(files["commands.log"])).encode("utf-8"))
            r = self.measure()
            targets = {name: v for name, v, _ in r["targets"]}
            self.assertEqual(targets["One compact review"], "met")
            self.assertEqual(targets["One final approval interaction"], "met")
            self.assertEqual(targets["No owner-entered commands or identifiers"], "met")
            self.assertEqual(targets["No repeated or unnecessary questions"], "met")
            self.assertEqual(targets["Explicit state and next action"], "met")
            self.assertEqual(targets["Deviations from the skill's steps"], "none")
            self.assertEqual(r["elapsed"]["to_approval"], 360.0)
            self.assertIn("6 min 00 s", M.render_report(r))
            # the same run with the approval recorded after the write is a deviation, and three questions are too many
            (t / "questions.md").write_bytes((q(1, "P3+P4", time="2026-11-14T10:05:10Z") + q(2, "none", time="2026-11-14T10:06:00Z")
                                            + q(3, "P5", time="2026-11-14T10:13:00Z")).encode("utf-8"))
            late = self.measure()
            self.assertIn("apply-before-approval", [d["code"] for d in late["deviations"]["deviations"]])
            names = {name: v for name, v, _ in late["targets"]}
            self.assertEqual(names["One final approval interaction"], "not met")
            self.assertEqual(names["No repeated or unnecessary questions"], "not met")
            self.assertEqual(len(late["interactions"]["unnecessary"]), 1)
        finally:
            for name, text in files.items():
                (t / name).write_bytes((text).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
