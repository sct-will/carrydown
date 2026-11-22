"""Reviewed source checkpoints in the private workspace (specification 6.1 to 6.3).

They cover preparing a checkpoint (copies and descriptor, a dry run that writes nothing), committing it
in the workspace's own git repository through an isolated index, the read-back that must pass before the
record is written to workspace.yaml, the refusals (staged changes, missing git identity, a path outside
the checkpoint folders), tamper detection, binding to a release and request with history kept, the
lookups, and the status and doctor lines. A temporary HOME and fixed git identity variables are used. No
token and no network are used, and nothing is pushed.
Run from the repository root: python3 -m unittest tests.test_source_checkpoint -v
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import release_gate as RG  # noqa: E402
import workspace as W  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
HAS_GIT = shutil.which("git") is not None
IDENTITY = {"GIT_AUTHOR_NAME": "Test Owner", "GIT_AUTHOR_EMAIL": "owner@example.com",
            "GIT_COMMITTER_NAME": "Test Owner", "GIT_COMMITTER_EMAIL": "owner@example.com"}
PLAN_SHA = hashlib.sha256(b"the assessed plan").hexdigest()
RELEASE_A, REQUEST_A = "a" * 64, "b" * 64
RELEASE_B, REQUEST_B = "c" * 64, "d" * 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = W.main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
    return code, out.getvalue(), err.getvalue()


def plain_git(cwd, *args, env=None):
    full = dict(os.environ)
    full.update(env or {})
    return subprocess.run(["git", "-C", str(cwd)] + list(args), capture_output=True, env=full)


@unittest.skipUnless(HAS_GIT, "git is needed")
class CheckpointCase(unittest.TestCase):
    """A copy of the confidential fixture, a temporary HOME with no git configuration, a real owner-only
    workspace made by init, and the two renderings of the fixture as the reviewed set."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-checkpoint-test-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = base / "home"
        self.home.mkdir()
        self.root = base / "engineering"
        shutil.copytree(FIXTURE, self.root)
        env = {"HOME": str(self.home), "USERPROFILE": str(self.home), "XDG_CONFIG_HOME": str(self.home / "xdg"),
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        env.update(IDENTITY)
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        for name in ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "EMAIL"):   # no identity reaches git from the caller's environment
            os.environ.pop(name, None)
        code, out, err = run_main(["init", "--root", str(self.root), "--slug", "confidential-fixture", "--answer", "no", "--apply"])
        self.assertEqual(code, 0, out + err)
        self.workspace = self.home / ".carrydown" / "workspaces" / "confidential-fixture"
        self.ground = self.root / "docs" / "ground-truth"
        self.names = ("architecture", "company-governance")
        self.files = [self.ground / f"{n}{s}" for n in self.names for s in (".md", ".index.txt")]
        self.descriptor = {
            "plan_sha256": PLAN_SHA,
            "sources": [
                {"id": "architecture", "version": "0.3", "rendering_sha256": sha((self.ground / "architecture.md").read_bytes()),
                 "precedence": 1, "classification": "repo-readers", "applicability": ["all work items"],
                 "extraction_limits": {"images": "not extracted", "tables": "kept"}},
                {"id": "company-governance", "version": "2027.1", "precedence": 2, "classification": "restricted",
                 "applicability": "global conventions"}]}

    # -- helpers

    def tree(self, folder=None):
        base = Path(folder or self.workspace)
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file() and ".git" not in p.relative_to(base).parts)

    def prepare(self, apply=True, **kw):
        return W.checkpoint_prepare(self.root, self.workspace, kw.get("files", self.files), kw.get("descriptor", self.descriptor), apply=apply)

    def committed(self):
        cid = self.prepare()["id"]
        result = W.checkpoint_commit(self.workspace, cid, apply=True, root=self.root)
        self.assertEqual(result["status"], "committed", result)
        return cid, result["commit"]

    def git(self, *args, env=None):
        return plain_git(self.workspace, *args, env=env)

    def ref_tree(self, ref=W.CHECKPOINT_REF):
        run = self.git("ls-tree", "-r", "--name-only", ref)
        return sorted(run.stdout.decode().split()) if run.returncode == 0 else None

    def problem(self, call, *args, **kwargs):
        try:
            call(*args, **kwargs)
        except W.CheckpointProblem as e:
            return e
        self.fail("CheckpointProblem was not raised")


class PrepareTests(CheckpointCase):
    def test_a_dry_run_writes_nothing(self):
        before = self.tree()
        result = self.prepare(apply=False)
        self.assertEqual(self.tree(), before)
        self.assertFalse((self.workspace / "renderings" / "reviewed").exists())
        self.assertFalse((self.workspace / "drafts" / "checkpoints").exists())
        self.assertFalse(result["apply"])
        paths = [f["path"] for f in result["files"]]
        self.assertIn("renderings/reviewed/architecture/architecture.md", paths)
        self.assertIn("renderings/reviewed/company-governance/company-governance.index.txt", paths)
        self.assertIn(f"drafts/checkpoints/{result['id']}/descriptor.json", paths)
        self.assertIn(f"drafts/checkpoints/{result['id']}/checkpoint.json", paths)
        self.assertTrue(all(f["action"] == "write" for f in result["files"]))

    def test_apply_writes_private_copies_and_the_descriptor_and_leaves_the_originals_alone(self):
        originals = {p: p.read_bytes() for p in self.files}
        result = self.prepare()
        for p in self.files:
            self.assertEqual(p.read_bytes(), originals[p])
            name = p.name
            sid = "architecture" if name.startswith("architecture") else "company-governance"
            copy = self.workspace / "renderings" / "reviewed" / sid / name
            self.assertEqual(copy.read_bytes(), originals[p])
            self.assertNotEqual(os.stat(str(copy)).st_ino, os.stat(str(p)).st_ino)
            self.assertFalse(copy.is_symlink())
        folder = self.workspace / "drafts" / "checkpoints" / result["id"]
        meta = json.loads((folder / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["id"], result["id"])
        self.assertEqual(meta["plan_sha256"], PLAN_SHA)
        self.assertEqual([s["id"] for s in meta["sources"]], ["architecture", "company-governance"])
        self.assertEqual(meta["sources"][0]["sha256"], sha(originals[self.ground / "architecture.md"]))
        descriptor = json.loads((folder / "descriptor.json").read_text(encoding="utf-8"))
        self.assertEqual(descriptor["plan_sha256"], PLAN_SHA)
        self.assertEqual(descriptor["sources"][0]["extraction_limits"], {"images": "not extracted", "tables": "kept"})
        # nothing in the project and nothing under releases/ or a snapshot
        self.assertEqual(self.tree(self.workspace / "releases"), [])
        self.assertFalse(any("snapshot" in p for p in self.tree()))

    def test_the_id_is_the_digest_of_the_sorted_path_and_digest_list(self):
        result = self.prepare(apply=False)
        entries = [(f["path"], f["sha256"]) for f in result["files"] if "/checkpoints/" not in f["path"]]
        descriptor_sha = next(f["sha256"] for f in result["files"] if f["path"].endswith("descriptor.json"))
        pairs = sorted(entries + [("descriptor.json", descriptor_sha)])
        self.assertEqual(result["id"], hashlib.sha256(json.dumps(pairs, separators=(",", ":")).encode("ascii")).hexdigest())
        self.assertEqual(result["id"], self.prepare(apply=False)["id"])

    def test_the_id_changes_with_a_rendering_or_the_plan_digest(self):
        first = self.prepare(apply=False)["id"]
        changed = self.ground / "architecture.md"
        changed.write_bytes((changed.read_text(encoding="utf-8") + "\nOne more rule.\n").encode("utf-8"))
        self.assertNotEqual(self.prepare(apply=False)["id"], first)
        other = dict(self.descriptor, plan_sha256=sha(b"another plan"))
        self.assertNotEqual(self.prepare(apply=False, descriptor=other)["id"], self.prepare(apply=False)["id"])

    def test_a_second_apply_changes_nothing(self):
        self.prepare()
        again = self.prepare()
        self.assertTrue(all(f["action"] == "unchanged" for f in again["files"]))

    def test_a_second_apply_keeps_the_creation_time_when_the_clock_moved(self):
        # The record carries a creation time. A repeat of the same checkpoint a second later must not rewrite it.
        with mock.patch.object(W, "_now", return_value="2027-01-01T00:00:00Z"):
            first = self.prepare()
        with mock.patch.object(W, "_now", return_value="2027-01-01T00:00:01Z"):
            again = self.prepare()
        self.assertEqual(again["created"], first["created"])
        self.assertTrue(all(f["action"] == "unchanged" for f in again["files"]))

    def test_a_descriptor_key_outside_the_allowlist_is_refused_so_staffing_cannot_ride_along(self):
        for bad in (dict(self.descriptor, people=[{"id": "tamsin"}]), dict(self.descriptor, staffing="x")):
            e = self.problem(W.checkpoint_prepare, self.root, self.workspace, self.files, bad, apply=True)
            self.assertEqual(e.code, "checkpoint-invalid")
        sources = [dict(self.descriptor["sources"][0], name="Architecture document"), self.descriptor["sources"][1]]
        e = self.problem(W.checkpoint_prepare, self.root, self.workspace, self.files, dict(self.descriptor, sources=sources), apply=True)
        self.assertEqual(e.code, "checkpoint-invalid")
        sources = [dict(self.descriptor["sources"][0], source_path="ground-truth/architecture.md"), self.descriptor["sources"][1]]
        e = self.problem(W.checkpoint_prepare, self.root, self.workspace, self.files, dict(self.descriptor, sources=sources), apply=True)
        self.assertEqual(e.code, "checkpoint-invalid")
        self.assertFalse((self.workspace / "drafts" / "checkpoints").exists())

    def test_project_descriptor_drops_everything_but_the_allowlist(self):
        plan_sources = [{"id": "architecture", "name": "Architecture document", "version": "0.3", "path": "docs/ground-truth/architecture.md",
                         "source_path": "ground-truth/architecture.md", "classification": "repo-readers", "content_sha256": "a" * 64},
                        {"id": "company-governance", "version": "2027.1", "classification": "restricted", "precedence": 5}]
        projected = W.project_descriptor(plan_sources, PLAN_SHA)
        self.assertEqual(sorted(projected), ["plan_sha256", "sources"])
        self.assertEqual(projected["sources"][0], {"id": "architecture", "version": "0.3", "classification": "repo-readers",
                                                    "content_sha256": "a" * 64, "precedence": 1})
        self.assertEqual(projected["sources"][1]["precedence"], 5)
        self.assertEqual(W.checkpoint_prepare(self.root, self.workspace, self.files, projected, apply=False)["plan_sha256"], PLAN_SHA)

    def test_an_original_is_never_copied(self):
        source = self.root / "ground-truth" / "architecture.md"
        e = self.problem(W.checkpoint_prepare, self.root, self.workspace, [source, self.ground / "company-governance.md"],
                         dict(self.descriptor), apply=True)
        self.assertEqual(e.code, "checkpoint-invalid")
        self.assertIn("generated header", e.message)
        kept = self.workspace / "sources" / "architecture.md"
        kept.parent.mkdir(exist_ok=True)
        shutil.copyfile(self.ground / "architecture.md", kept)
        e = self.problem(W.checkpoint_prepare, self.root, self.workspace, [kept, self.ground / "company-governance.md"], dict(self.descriptor), apply=True)
        self.assertIn("originals", e.message)
        self.assertFalse((self.workspace / "renderings" / "reviewed").exists())

    def test_a_source_without_its_rendering_or_an_unknown_file_is_refused(self):
        e = self.problem(W.checkpoint_prepare, self.root, self.workspace, [self.ground / "architecture.md"], self.descriptor, apply=True)
        self.assertIn("company-governance", e.message)
        stray = self.ground / "stray.md"
        stray.write_bytes((self.files[0].read_text(encoding="utf-8")).encode("utf-8"))
        e = self.problem(W.checkpoint_prepare, self.root, self.workspace, self.files + [stray], self.descriptor, apply=True)
        self.assertEqual(e.code, "checkpoint-invalid")

    def test_a_link_for_a_rendering_or_for_the_destination_is_refused(self):
        link = self.ground / "linked.md"
        link.symlink_to(self.ground / "architecture.md")
        descriptor = dict(self.descriptor, sources=[dict(self.descriptor["sources"][0], rendering="linked"), self.descriptor["sources"][1]])
        e = self.problem(W.checkpoint_prepare, self.root, self.workspace, [link, self.ground / "company-governance.md"], descriptor, apply=True)
        self.assertEqual(e.code, "checkpoint-invalid")
        outside = Path(self.temp.name) / "elsewhere"
        outside.mkdir()
        reviewed = self.workspace / "renderings" / "reviewed"
        reviewed.symlink_to(outside)
        e = self.problem(self.prepare)
        self.assertEqual(e.code, "checkpoint-path-refused")
        self.assertEqual(list(outside.iterdir()), [])

    def test_each_write_asks_the_release_gate_as_a_candidate_write_and_a_refusal_stops_everything(self):
        calls = []
        real = RG.check

        def spy(write_class, rel, digest, destination, root, **kw):
            calls.append((write_class, rel, destination, kw.get("dry_run")))
            return real(write_class, rel, digest, destination, root, **kw)

        with mock.patch.object(RG, "check", side_effect=spy):
            result = self.prepare(apply=False)
        self.assertEqual(len(calls), len(result["files"]))
        self.assertTrue(all(c[0] == "candidate" and c[2] == "workspace" and c[3] is True for c in calls))
        refusal = RG.Decision(False, "deny", "drafting-is-private", None)
        with mock.patch.object(RG, "check", return_value=refusal):
            e = self.problem(self.prepare)
        self.assertEqual(e.code, "checkpoint-gate-refused")
        self.assertFalse((self.workspace / "renderings" / "reviewed").exists())


class CommitTests(CheckpointCase):
    def test_a_dry_run_commits_and_records_nothing(self):
        cid = self.prepare()["id"]
        before = (self.workspace / "workspace.yaml").read_bytes()
        result = W.checkpoint_commit(self.workspace, cid, apply=False)
        self.assertEqual(result["status"], "would-commit")
        self.assertIsNone(self.ref_tree())
        self.assertEqual((self.workspace / "workspace.yaml").read_bytes(), before)
        self.assertEqual(W.checkpoint_records(self.workspace), [])

    def test_apply_commits_exactly_the_checkpoint_files_and_reads_them_back(self):
        cid, commit = self.committed()
        names = self.ref_tree()
        self.assertEqual(names, sorted([
            "renderings/reviewed/architecture/architecture.md", "renderings/reviewed/architecture/architecture.index.txt",
            "renderings/reviewed/company-governance/company-governance.md", "renderings/reviewed/company-governance/company-governance.index.txt",
            f"drafts/checkpoints/{cid}/descriptor.json", f"drafts/checkpoints/{cid}/checkpoint.json"]))
        self.assertEqual(self.git("rev-parse", W.CHECKPOINT_REF).stdout.decode().strip(), commit)
        record = W.latest_checkpoint(self.workspace)
        self.assertEqual(record["id"], cid)
        self.assertEqual(record["commit"], commit)
        self.assertIsNone(record["release_id"])
        self.assertIsNone(record["request_id"])
        self.assertEqual(record["plan_sha256"], PLAN_SHA)
        self.assertEqual([s["id"] for s in record["sources"]], ["architecture", "company-governance"])
        self.assertEqual(record["sources"][0]["sha256"], sha((self.ground / "architecture.md").read_bytes()))
        self.assertEqual(record["sources"][0]["version"], "0.3")
        self.assertRegex(record["created"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertIsNone(W.checkpoint_verify(self.workspace, cid))

    def test_the_commit_is_authored_by_the_configured_identity(self):
        cid, commit = self.committed()
        fmt = self.git("log", "-1", "--format=%an <%ae>|%cn <%ce>|%s", commit).stdout.decode().strip()
        self.assertEqual(fmt, f"Test Owner <owner@example.com>|Test Owner <owner@example.com>|Record reviewed source checkpoint {cid[:12]}")
        self.assertNotIn("Co-", self.git("log", "-1", "--format=%B", commit).stdout.decode())     # no trailer of any kind

    def test_the_branch_and_the_normal_index_are_untouched(self):
        self.committed()
        self.assertNotEqual(self.git("rev-parse", "--verify", "-q", "HEAD").returncode, 0)     # still unborn
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, b"")
        self.assertEqual(self.git("ls-files").stdout, b"")
        leftovers = [p.name for p in (self.workspace / ".git").iterdir() if p.name.startswith("carrydown-checkpoint-")]
        self.assertEqual(leftovers, [])

    def test_people_sources_retention_and_workspace_yaml_never_enter_the_commit(self):
        (self.workspace / "sources").mkdir(exist_ok=True)
        (self.workspace / "sources" / "architecture.docx").write_bytes(b"raw original")
        (self.workspace / ".env").write_bytes(("TOKEN=secret\n").encode("utf-8"))
        (self.workspace / "drafts").mkdir(exist_ok=True)
        (self.workspace / "drafts" / "plan.yaml").write_bytes(("people: []\n").encode("utf-8"))
        (self.workspace / "people.yaml").write_bytes(("people:\n  - id: tamsin\n    name: \"Tamsin Secret\"\n").encode("utf-8"))
        cid, commit = self.committed()
        names = self.ref_tree()
        for bad in ("people.yaml", "retention.yaml", "workspace.yaml", ".env", "drafts/plan.yaml", "sources/architecture.docx"):
            self.assertNotIn(bad, names)
        self.assertTrue(all(n.startswith(W.CHECKPOINT_PREFIXES) for n in names), names)
        blobs = subprocess.run(["git", "-C", str(self.workspace), "grep", "-l", "-e", "Tamsin", "-e", "TOKEN=", commit],
                               capture_output=True, text=True)
        self.assertEqual(blobs.stdout, "")

    def test_an_unrelated_staged_change_is_refused_and_never_enters_the_checkpoint(self):
        cid = self.prepare()["id"]
        (self.workspace / "people.yaml").write_bytes(("people:\n  - id: tamsin\n    name: \"Tamsin Secret\"\n").encode("utf-8"))
        self.assertEqual(self.git("add", "people.yaml").returncode, 0)
        e = self.problem(W.checkpoint_commit, self.workspace, cid, apply=True, root=self.root)
        self.assertEqual(e.code, "checkpoint-staged-changes")
        self.assertIn("Nothing was committed", e.message)
        self.assertNotIn("people.yaml", e.message)
        self.assertIsNone(self.ref_tree())
        self.assertEqual(W.checkpoint_records(self.workspace), [])
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout.decode().split(), ["people.yaml"])    # left as it was
        e = self.problem(W.checkpoint_commit, self.workspace, cid, apply=False)                                    # a dry run refuses too
        self.assertEqual(e.code, "checkpoint-staged-changes")
        self.git("rm", "--cached", "-q", "people.yaml")
        self.assertEqual(W.checkpoint_commit(self.workspace, cid, apply=True)["status"], "committed")
        self.assertNotIn("people.yaml", self.ref_tree())

    def test_a_missing_git_identity_is_refused_in_plain_words_and_no_author_is_invented(self):
        cid = self.prepare()["id"]
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_AUTHOR") and not k.startswith("GIT_COMMITTER")}
        clean.pop("EMAIL", None)
        with mock.patch.dict(os.environ, clean, clear=True):
            for apply in (False, True):
                e = self.problem(W.checkpoint_commit, self.workspace, cid, apply=apply)
                self.assertEqual(e.code, "checkpoint-identity-missing")
                self.assertIn("git config --global user.name", e.message)
                self.assertIn("nothing was committed", e.message)
        self.assertIsNone(self.ref_tree())
        self.assertEqual(W.checkpoint_records(self.workspace), [])

    def test_an_identity_from_git_configuration_is_enough(self):
        cid = self.prepare()["id"]
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_AUTHOR") and not k.startswith("GIT_COMMITTER")}
        with mock.patch.dict(os.environ, clean, clear=True):
            self.git("config", "user.name", "Configured Owner")
            self.git("config", "user.email", "configured@example.com")
            self.assertEqual(W.checkpoint_commit(self.workspace, cid, apply=True)["status"], "committed")
        self.assertIn("Configured Owner", self.git("log", "-1", "--format=%an", W.CHECKPOINT_REF).stdout.decode())

    def test_an_unprepared_or_changed_checkpoint_is_refused(self):
        e = self.problem(W.checkpoint_commit, self.workspace, "f" * 64, apply=True)
        self.assertEqual(e.code, "checkpoint-missing")
        e = self.problem(W.checkpoint_commit, self.workspace, "not-an-id", apply=True)
        self.assertEqual(e.code, "checkpoint-invalid")
        cid = self.prepare()["id"]
        copy = self.workspace / "renderings" / "reviewed" / "architecture" / "architecture.md"
        copy.write_bytes((copy.read_text(encoding="utf-8") + "edited\n").encode("utf-8"))
        e = self.problem(W.checkpoint_commit, self.workspace, cid, apply=True)
        self.assertEqual(e.code, "checkpoint-mismatch")
        self.assertIsNone(self.ref_tree())

    def test_a_file_listed_outside_the_checkpoint_folders_is_refused(self):
        cid = self.prepare()["id"]
        meta_path = self.workspace / "drafts" / "checkpoints" / cid / "checkpoint.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["files"].append({"path": "people.yaml", "sha256": sha(b"x" * 3)})
        meta_path.write_bytes((json.dumps(meta)).encode("utf-8"))
        e = self.problem(W.checkpoint_commit, self.workspace, cid, apply=True)
        self.assertEqual(e.code, "checkpoint-path-refused")
        self.assertIsNone(self.ref_tree())

    def test_committing_again_is_a_no_op(self):
        cid, commit = self.committed()
        again = W.checkpoint_commit(self.workspace, cid, apply=True)
        self.assertEqual(again["status"], "already-recorded")
        self.assertEqual(again["commit"], commit)
        self.assertEqual(len(W.checkpoint_records(self.workspace)), 1)

    def test_a_second_checkpoint_chains_and_the_first_still_reads_its_own_text(self):
        first, first_commit = self.committed()
        reviewed = self.ground / "architecture.md"
        reviewed.write_bytes((reviewed.read_text(encoding="utf-8") + "\n## 99. New\n\nA new obligation.\n").encode("utf-8"))
        second = self.prepare(descriptor=dict(self.descriptor, plan_sha256=sha(b"later plan")))["id"]
        self.assertNotEqual(first, second)
        result = W.checkpoint_commit(self.workspace, second, apply=True)
        self.assertEqual(self.git("rev-parse", result["commit"] + "^").stdout.decode().strip(), first_commit)
        self.assertEqual([r["id"] for r in W.checkpoint_records(self.workspace)], [first, second])
        self.assertEqual(W.latest_checkpoint(self.workspace)["id"], second)
        old = W.checkpoint_read(self.workspace, first)
        new = W.checkpoint_read(self.workspace, second)
        self.assertNotIn("A new obligation", old["renderings"]["architecture/architecture.md"])
        self.assertIn("A new obligation", new["renderings"]["architecture/architecture.md"])
        self.assertIn("renderings/reviewed/architecture/architecture.md", old["working_copy_differs"])       # a later checkpoint replaced the file
        self.assertEqual(new["working_copy_differs"], [])


class ReadBackAndBindTests(CheckpointCase):
    def test_read_returns_the_descriptor_and_the_texts_from_git(self):
        cid, commit = self.committed()
        data = W.checkpoint_read(self.workspace, cid)
        self.assertEqual(data["id"], cid)
        self.assertEqual(data["commit"], commit)
        self.assertEqual(data["descriptor"]["plan_sha256"], PLAN_SHA)
        self.assertEqual([s["id"] for s in data["descriptor"]["sources"]], ["architecture", "company-governance"])
        self.assertEqual(data["renderings"]["architecture/architecture.md"], (self.ground / "architecture.md").read_text(encoding="utf-8"))
        self.assertEqual(sorted(data["renderings"]), ["architecture/architecture.index.txt", "architecture/architecture.md",
                                                       "company-governance/company-governance.index.txt", "company-governance/company-governance.md"])
        self.assertEqual(data["working_copy_differs"], [])

    def test_the_texts_come_from_git_and_not_from_the_working_files(self):
        cid, _ = self.committed()
        copy = self.workspace / "renderings" / "reviewed" / "architecture" / "architecture.md"
        original = (self.ground / "architecture.md").read_text(encoding="utf-8")
        copy.write_bytes(("tampered\n").encode("utf-8"))
        data = W.checkpoint_read(self.workspace, cid)
        self.assertEqual(data["renderings"]["architecture/architecture.md"], original)
        self.assertEqual(data["working_copy_differs"], ["renderings/reviewed/architecture/architecture.md"])

    def test_a_tampered_working_file_is_detected_when_the_working_copy_is_checked(self):
        cid, _ = self.committed()
        copy = self.workspace / "renderings" / "reviewed" / "architecture" / "architecture.md"
        copy.write_bytes(("tampered\n").encode("utf-8"))
        e = self.problem(W.checkpoint_read, self.workspace, cid, check_working=True)
        self.assertEqual(e.code, "checkpoint-mismatch")
        self.assertEqual(W.checkpoint_verify(self.workspace, cid, check_working=True), "checkpoint-mismatch")
        self.assertIsNone(W.checkpoint_verify(self.workspace, cid))

    def forge(self, cid, commit):
        """A commit with the same paths and one changed rendering, made with git plumbing, and the record
        pointed at it."""
        index = self.workspace / ".git" / "forge.index"
        env = {"GIT_INDEX_FILE": str(index)}
        self.assertEqual(plain_git(self.workspace, "read-tree", commit, env=env).returncode, 0)
        blob = subprocess.run(["git", "-C", str(self.workspace), "hash-object", "-w", "--stdin"], input=b"forged\n", capture_output=True).stdout.decode().strip()
        plain_git(self.workspace, "update-index", "--cacheinfo", f"100644,{blob},renderings/reviewed/architecture/architecture.md", env=env)
        tree = plain_git(self.workspace, "write-tree", env=env).stdout.decode().strip()
        forged = plain_git(self.workspace, "commit-tree", tree, "-m", "forged").stdout.decode().strip()
        index.unlink()
        path = self.workspace / "workspace.yaml"
        path.write_bytes((path.read_text(encoding="utf-8").replace(commit, forged)).encode("utf-8"))
        return forged

    def test_a_commit_whose_content_was_replaced_is_a_mismatch(self):
        cid, commit = self.committed()
        self.forge(cid, commit)
        e = self.problem(W.checkpoint_read, self.workspace, cid)
        self.assertEqual(e.code, "checkpoint-mismatch")
        self.assertEqual(W.checkpoint_verify(self.workspace, cid), "checkpoint-mismatch")

    def test_a_record_that_disagrees_with_the_commit_is_a_mismatch(self):
        cid, commit = self.committed()
        path = self.workspace / "workspace.yaml"
        recorded = sha((self.ground / "architecture.md").read_bytes())
        path.write_bytes((path.read_text(encoding="utf-8").replace(recorded, "0" * 64)).encode("utf-8"))
        self.assertEqual(W.checkpoint_verify(self.workspace, cid), "checkpoint-mismatch")
        path.write_bytes((path.read_text(encoding="utf-8").replace("0" * 64, recorded).replace(PLAN_SHA, "1" * 64)).encode("utf-8"))
        self.assertEqual(W.checkpoint_verify(self.workspace, cid), "checkpoint-mismatch")

    def test_a_commit_that_is_gone_is_missing(self):
        cid, commit = self.committed()
        path = self.workspace / "workspace.yaml"
        path.write_bytes((path.read_text(encoding="utf-8").replace(commit, "e" * 40)).encode("utf-8"))
        e = self.problem(W.checkpoint_read, self.workspace, cid)
        self.assertEqual(e.code, "checkpoint-missing")
        self.assertIn("Review the current sources", e.message)
        e = self.problem(W.checkpoint_read, self.workspace, "9" * 64)
        self.assertEqual(e.code, "checkpoint-missing")

    def test_bind_records_the_association_and_appends_history_never_overwrites(self):
        cid, _ = self.committed()
        dry = W.checkpoint_bind(self.workspace, cid, RELEASE_A, REQUEST_A, apply=False)
        self.assertEqual(dry["status"], "would-bind")
        self.assertIsNone(W.latest_checkpoint(self.workspace)["release_id"])
        first = W.checkpoint_bind(self.workspace, cid, RELEASE_A, REQUEST_A, apply=True, root=self.root, when="2026-11-14T10:00:00Z")
        self.assertEqual(first["status"], "bound")
        record = W.latest_checkpoint(self.workspace)
        self.assertEqual((record["release_id"], record["request_id"], record["history"]), (RELEASE_A, REQUEST_A, []))
        again = W.checkpoint_bind(self.workspace, cid, RELEASE_A, REQUEST_A, apply=True)
        self.assertEqual(again["status"], "unchanged")
        second = W.checkpoint_bind(self.workspace, cid, RELEASE_B, REQUEST_B, apply=True, when="2026-11-15T10:00:00Z")
        self.assertEqual(second["status"], "bound")
        record = W.latest_checkpoint(self.workspace)
        self.assertEqual((record["release_id"], record["request_id"]), (RELEASE_B, REQUEST_B))
        self.assertEqual(record["history"], [{"release_id": RELEASE_A, "request_id": REQUEST_A, "replaced": "2026-11-15T10:00:00Z"}])
        W.checkpoint_bind(self.workspace, cid, RELEASE_A, REQUEST_A, apply=True, when="2026-11-16T10:00:00Z")
        history = W.latest_checkpoint(self.workspace)["history"]
        self.assertEqual([h["release_id"] for h in history], [RELEASE_A, RELEASE_B])
        self.assertEqual(W.checkpoint_read(self.workspace, cid)["history"], history)
        self.assertIsNone(W.checkpoint_verify(self.workspace, cid))

    def test_bind_refuses_a_missing_checkpoint_a_bad_id_and_a_checkpoint_that_does_not_verify(self):
        e = self.problem(W.checkpoint_bind, self.workspace, "f" * 64, RELEASE_A, REQUEST_A, apply=True)
        self.assertEqual(e.code, "checkpoint-missing")
        cid, commit = self.committed()
        e = self.problem(W.checkpoint_bind, self.workspace, cid, "has space", REQUEST_A, apply=True)
        self.assertEqual(e.code, "checkpoint-invalid")
        self.forge(cid, commit)
        e = self.problem(W.checkpoint_bind, self.workspace, cid, RELEASE_A, REQUEST_A, apply=True)
        self.assertEqual(e.code, "checkpoint-mismatch")
        self.assertIsNone(W.latest_checkpoint(self.workspace)["release_id"])

    def test_the_lookups_return_none_without_a_checkpoint_and_the_message_is_the_specified_one(self):
        self.assertIsNone(W.latest_checkpoint(self.workspace))
        self.assertIsNone(W.checkpoint_for_sources(self.workspace, ["architecture"]))
        self.assertEqual(W.CHECKPOINT_UNAVAILABLE,
                         "A previous complete source checkpoint is unavailable. Review the current sources to establish one. "
                         "Earlier uncited changes cannot be assessed automatically.")
        cid, _ = self.committed()
        self.assertEqual(W.checkpoint_for_sources(self.workspace, ["architecture"])["id"], cid)
        self.assertEqual(W.checkpoint_for_sources(self.workspace, ["architecture", "company-governance"])["id"], cid)
        self.assertIsNone(W.checkpoint_for_sources(self.workspace, ["architecture", "other"]))

    def test_the_record_keeps_the_layout_other_readers_use(self):
        cid, _ = self.committed()
        W.checkpoint_bind(self.workspace, cid, RELEASE_A, REQUEST_A, apply=True)
        data = L.load_file(self.workspace / "workspace.yaml")
        self.assertEqual(data["state"], "drafting")
        self.assertEqual(data["slug"], "confidential-fixture")
        self.assertEqual(sorted(data["checkpoints"][0]), ["commit", "created", "history", "id", "plan_sha256", "release_id", "request_id", "sources"])
        text = (self.workspace / "workspace.yaml").read_text(encoding="utf-8")
        self.assertEqual(text.count("checkpoints:"), 1)


class CommandAndReportTests(CheckpointCase):
    def write_descriptor(self):
        path = Path(self.temp.name) / "descriptor.json"
        path.write_bytes((json.dumps(self.descriptor)).encode("utf-8"))
        return path

    def args(self, *more):
        return ["checkpoint"] + list(more) + ["--root", str(self.root)]

    def test_the_command_is_a_dry_run_until_apply_and_runs_the_whole_cycle(self):
        descriptor = str(self.write_descriptor())
        before = self.tree()
        code, out, err = run_main(self.args("prepare", "--descriptor", descriptor, "--rendering-dir", str(self.ground)))
        self.assertEqual(code, 0, out + err)
        self.assertIn("DRY RUN", out)
        self.assertEqual(self.tree(), before)
        code, out, err = run_main(self.args("prepare", "--descriptor", descriptor, "--rendering-dir", str(self.ground), "--apply"))
        self.assertEqual(code, 0, out + err)
        cid = out.splitlines()[0].split()[1]
        self.assertRegex(cid, r"^[0-9a-f]{64}$")
        code, out, err = run_main(self.args("commit", "--id", cid))
        self.assertEqual(code, 0, out + err)
        self.assertIn("DRY RUN", out)
        self.assertIsNone(self.ref_tree())
        code, out, err = run_main(self.args("commit", "--id", cid, "--apply"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("committed and read back", out)
        code, out, err = run_main(self.args("bind", "--id", cid, "--release-id", RELEASE_A, "--request-id", REQUEST_A))
        self.assertIn("DRY RUN", out)
        self.assertIsNone(W.latest_checkpoint(self.workspace)["release_id"])
        code, out, err = run_main(self.args("bind", "--id", cid, "--release-id", RELEASE_A, "--request-id", REQUEST_A, "--apply"))
        self.assertEqual(code, 0, out + err)
        code, out, err = run_main(self.args("list"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("source checkpoints: 1", out)
        self.assertIn(f"latest checkpoint: {cid} (commit verifies)", out)

    def test_a_refusal_prints_one_plain_error_and_exits_nonzero(self):
        cid = self.prepare()["id"]
        self.git("add", "-A", "drafts")
        code, out, err = run_main(self.args("commit", "--id", cid, "--apply"))
        self.assertEqual(code, 2)
        self.assertIn("checkpoint-staged-changes", err)
        code, out, err = run_main(self.args("bind", "--id", "f" * 64, "--release-id", RELEASE_A, "--request-id", REQUEST_A, "--apply"))
        self.assertEqual(code, 1)
        self.assertIn("checkpoint-missing", err)

    def test_status_and_doctor_report_the_count_the_latest_id_and_the_verification_without_content(self):
        code, out, err = run_main(["status", "--root", str(self.root)])
        self.assertIn("source checkpoints: 0", out)
        rows = {name: (level, detail) for level, name, detail in W.doctor_rows(self.root)}
        self.assertEqual(rows["checkpoints"][0], "ok")
        self.assertIn("none recorded", rows["checkpoints"][1])
        cid, _ = self.committed()
        code, out, err = run_main(["status", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        self.assertIn("source checkpoints: 1", out)
        self.assertIn(f"latest checkpoint: {cid} (commit verifies)", out)
        code, doc, err = run_main(["doctor", "--root", str(self.root)])
        self.assertEqual(code, 0, doc + err)
        level, detail = {name: (level, detail) for level, name, detail in W.doctor_rows(self.root)}["checkpoints"]
        self.assertEqual(level, "ok")
        self.assertIn("1 recorded", detail)
        self.assertIn(cid[:12], detail)
        text = (self.ground / "architecture.md").read_text(encoding="utf-8")
        headings = [line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")]
        for shown in (out, doc):
            self.assertNotIn("Generated from", shown)
            for heading in headings[:5]:
                self.assertNotIn(heading, shown)
            self.assertNotIn("ground-truth", shown)

    def test_status_and_doctor_show_a_checkpoint_that_no_longer_verifies(self):
        cid, commit = self.committed()
        path = self.workspace / "workspace.yaml"
        path.write_bytes((path.read_text(encoding="utf-8").replace(commit, "e" * 40)).encode("utf-8"))
        code, out, err = run_main(["status", "--root", str(self.root)])
        self.assertIn("commit does NOT verify: checkpoint-missing", out)
        code, doc, err = run_main(["doctor", "--root", str(self.root)])
        self.assertEqual(code, 1, doc)
        row = {name: (level, detail) for level, name, detail in W.doctor_rows(self.root)}["checkpoints"]
        self.assertEqual(row[0], "FAIL")
        self.assertIn("does not verify", row[1])

    def test_an_unreadable_record_is_reported_and_not_hidden_as_no_checkpoint(self):
        path = self.workspace / "workspace.yaml"
        path.write_bytes((path.read_text(encoding="utf-8") + "checkpoints: nonsense\n").encode("utf-8"))
        row = {name: (level, detail) for level, name, detail in W.doctor_rows(self.root)}["checkpoints"]
        self.assertEqual(row[0], "FAIL")


@unittest.skipUnless(HAS_GIT, "git is needed")
class RetentionTextTests(CheckpointCase):
    def test_retention_says_that_deleting_raw_inputs_does_not_erase_rendering_history(self):
        retention = L.load_file(self.workspace / "retention.yaml")
        self.assertIn("does not remove them from any backup, remote or copy made earlier", retention["limits"])
        self.assertIn("Reconciliation keeps earlier reviewed renderings privately", retention["limits"])
        self.assertIn("does not erase rendering history, backups or earlier copies", retention["limits"])
        self.assertTrue(W.RETENTION_LIMITS.startswith("Deleting files from this workspace does not remove them"))
        (self.workspace / "retention.yaml").write_bytes((W.retention_yaml_text("delete-after-release")).encode("utf-8"))
        (self.workspace / "sources").mkdir(exist_ok=True)
        (self.workspace / "sources" / "a.docx").write_bytes(b"x")
        lines = W.apply_retention(self.workspace, "r" * 8, False)
        self.assertIn("does not erase rendering history", lines[0])


if __name__ == "__main__":
    unittest.main()
