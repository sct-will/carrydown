"""The user-experience gate of the "yes" path (specification A2 and the Part C yes-path table).

On the yes path the owner answers the prompts of today plus one disclosure line, and types no request id,
nonce, numeric id, audience or destination: release.py release derives them, creates the empty board the
release names, and binds the approval to the preview the owner saw. These tests cover each of those
derivations and refusals, the released plan the export leaves in the project, the text citation kept in the
released plan, the request a standalone command acts on when --request is left out, the gate's silence
about migration on a new project, the recorded "no" answer, and the export-state retry.

The GitHub API is the loopback mock of tests/mock/mockgh.py. No token and no network are used.
"""
import contextlib
import io
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import github_client as G  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release as R  # noqa: E402
import release_fixture as F  # noqa: E402
import release_gate as RG  # noqa: E402
import release_github as RGH  # noqa: E402
import release_verify as V  # noqa: E402
import scaffold_spec as SS  # noqa: E402
import workspace as W  # noqa: E402

REPO = "sct-will/carrydown-sample"
SPEC = "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md"
HEX64 = re.compile(r"[0-9a-f]{64}")


def gh_writes():
    return [(m, p) for m, p in mockgh.S.log if m != "GET" and p != "/graphql"] + [op for op in mockgh.S.gql if op in mockgh.MUTATIONS]


class MockCase(unittest.TestCase):
    """A copy of the sample with a private workspace (yes answer), and the loopback mock of GitHub with
    the sample's repository and no board."""

    token = True

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-ux-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        mockgh.S.__init__()
        mockgh.S.repos.add(REPO)
        mockgh.S.repo_ids = {REPO: 4200}
        self.server, self.url = mockgh.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        env = {"HOME": str(self.base), "USERPROFILE": str(self.base)}
        if self.token:
            env["CARRYDOWN_GITHUB_TOKEN"] = "ghp_" + "U" * 36       # accepted by the loopback mock only
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.dict(os.environ, env))
        if not self.token:
            os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)
        stack.enter_context(mock.patch.object(time, "sleep", lambda s: None))
        stack.enter_context(mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"))
        stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None)))
        self.yp = F.YesProject(self.base / "yes")
        self.root, self.ws = self.yp.root, self.yp.workspace

    def release(self, *extra):
        return F.run(R.main, ["release", "--root", str(self.root)] + list(extra))

    def edit_spec(self):
        path = self.root / SPEC
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + " Added after the preview.\n", encoding="utf-8")


class ReleaseCommandTests(MockCase):
    def test_the_dry_run_derives_the_repository_id_the_audience_and_the_board_and_writes_nothing(self):
        before = F.tree_state(self.root) if hasattr(F, "tree_state") else None
        log = self.ws / "publication" / "gate.log"
        log_before = log.read_bytes() if log.exists() else None
        code, out, err = self.release()
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"Repository: {REPO} (numeric id 4200) on github.com.", out)
        self.assertIn(f'2. "These exact outputs may be shared with everyone who can read {REPO}."', out)
        self.assertIn("does not exist yet under sct-will", out)
        self.assertRegex(out, r'3\. "Carrydown may create or update these GitHub items: 1 Epic, 5 sub-epics, 9 work item issues, .*'
                              r"the board 'Expense approvals plan' \(created empty first, then filled\)")
        self.assertEqual(gh_writes(), [])
        self.assertEqual(len(list((self.root / "docs" / "release").glob("*.receipt.json"))), 1)     # only the sample's own
        self.assertFalse(any((self.ws / "requests").iterdir()))
        self.assertTrue((self.ws / R.SHOWN_RECORD).is_file())      # the digest of what the owner saw, in the private workspace
        self.assertEqual(log.read_bytes() if log.exists() else None, log_before, "the dry run added a line to the gate log")
        if before is not None:
            self.assertEqual(F.tree_state(self.root), before)

    def test_apply_without_a_shown_preview_is_refused_before_any_write(self):
        code, out, err = self.release("--apply")
        self.assertEqual(code, 1, out + err)
        self.assertIn("not-approved", out + err)
        self.assertEqual(gh_writes(), [])
        self.assertFalse(any((self.ws / "requests").iterdir()))

    def test_apply_after_a_change_to_the_files_is_refused_before_any_write(self):
        self.assertEqual(self.release()[0], 0)
        self.edit_spec()
        code, out, err = self.release("--apply")
        self.assertEqual(code, 1, out + err)
        self.assertIn("not-approved", out + err)
        self.assertEqual(gh_writes(), [])
        self.assertEqual(mockgh.S.projects, [])
        self.assertEqual(len(list((self.root / "docs" / "release").glob("*.receipt.json"))), 1)     # only the sample's own

    def test_apply_after_the_preview_creates_the_board_prepares_approves_and_exports(self):
        self.assertEqual(self.release()[0], 0)
        code, out, err = self.release("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(mockgh.S.projects), 1)
        self.assertEqual(mockgh.S.projects[0]["title"], "Expense approvals plan")
        self.assertEqual(mockgh.S.projects[0]["items"], [])                      # created empty
        self.assertEqual(mockgh.S.projects[0].get("repo_ids"), [4200])           # and linked to the repository
        receipts = list((self.root / "docs" / "release").glob("*.receipt.json"))
        self.assertEqual(len(receipts), 2)                                        # the sample's own and this one
        self.assertNotIn("--preview-shown", out)
        self.assertIn("approved this preview in the dry run", out)
        code, out, err = F.run(GS.run, ["--root", str(self.root), "--preflight"])
        self.assertEqual(code, 0, out + err)

    def test_a_public_repository_gives_the_public_audience(self):
        mockgh.S.private = False
        code, out, err = self.release()
        self.assertEqual(code, 0, out + err)
        self.assertIn('2. "These exact outputs may be published publicly."', out)
        self.assertIn("The public. Anyone can read what is published.", out)

    def test_nothing_changed_since_the_active_release_asks_no_disclosure_line(self):
        self.assertEqual(self.release()[0], 0)
        self.assertEqual(self.release("--apply")[0], 0)
        code, out, err = self.release()
        self.assertEqual(code, 0, out + err)
        self.assertIn("already approved and active", out)
        self.assertNotIn('2. "', out)

    def test_the_no_path_is_refused(self):
        plan = self.root / "docs" / "spec" / "plan.yaml"
        plan.write_text(plan.read_text(encoding="utf-8").replace("repo_audience_approved: true", "repo_audience_approved: false"), encoding="utf-8")
        code, out, err = self.release()
        self.assertEqual(code, 1, out + err)
        self.assertIn("unauthenticated-release", out + err)
        self.assertEqual(gh_writes(), [])

    def test_the_issues_dry_run_of_a_release_shows_the_summary_line_of_today(self):
        self.assertEqual(self.release()[0], 0)
        self.assertEqual(self.release("--apply")[0], 0)
        code, out, err = F.run(GS.run, ["--root", str(self.root), "--skip-check"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("1 Epic, 5 sub-epics, 9 work item issues", out)
        self.assertIn("to create now: 1 Epic, 5 sub-epics, 9 work item issues.", out)


class WithoutTokenTests(MockCase):
    token = False

    def test_without_a_token_or_an_earlier_release_the_repository_id_is_asked_for_plainly(self):
        code, out, err = F.run(R.main, ["prepare", "--root", str(self.root), "--no-github"])
        self.assertEqual(code, 1, out + err)
        self.assertIn("is not known yet", out + err)
        self.assertNotIn("--repository-id", out + err)

    def test_the_engineers_skill_alone_reuses_the_repository_id_of_an_earlier_release(self):
        self.yp.release()                                   # an earlier release with the id 4200
        self.edit_spec()
        code, out, err = self.release("--no-github")
        self.assertEqual(code, 0, out + err)
        self.assertIn("numeric id 4200", out)
        self.assertNotIn("3. ", out)


class DefaultRequestTests(MockCase):
    token = False

    def test_approve_takes_the_request_prepare_saved_and_export_the_active_one(self):
        code, out, err = self.yp.prepare()
        self.assertEqual(code, 0, out + err)
        code, out, err = F.run(R.main, ["approve", "--root", str(self.root), "--local", "--preview-shown", "--apply"])
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"request {self.yp.request_id} (the one prepare saved last)", out)
        code, out, err = F.run(R.main, ["export", "--root", str(self.root), "--apply"])
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"request {self.yp.request_id} (the active request)", out)

    def test_withdraw_takes_the_active_request_and_export_state_the_one_it_ended(self):
        rid = self.yp.release()
        code, out, err = F.run(R.main, ["withdraw", "--root", str(self.root), "--reason", "error-found", "--apply"])
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"request {rid} (the active request)", out)
        code, out, err = F.run(R.main, ["export-state", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"request {rid} (the one the most recent state change ended)", out)

    def test_with_nothing_prepared_approve_refuses_instead_of_guessing(self):
        code, out, err = F.run(R.main, ["approve", "--root", str(self.root), "--local", "--preview-shown", "--apply"])
        self.assertEqual(code, 1, out + err)
        self.assertIn("approval-not-found", out + err)
        code, out, err = F.run(R.main, ["export", "--root", str(self.root)])
        self.assertEqual(code, 1, out + err)
        self.assertIn("not-approved", out + err)


class WorkingPlanTests(MockCase):
    token = False

    def test_after_a_release_the_owner_side_commands_read_the_working_plan(self):
        import check_specs as CS
        import plan_repair as PR
        self.yp.release()
        (self.ws / "people.yaml").write_bytes((F.SAMPLE / "people.yaml").read_bytes())      # the fictional staffing of the interview
        working = (self.ws / "drafts" / "plan.yaml").resolve()
        self.assertEqual(L.owner_plan(self.root).resolve(), working)
        self.assertEqual(L.find_plan(self.root), self.root / "docs" / "spec" / "plan.yaml")       # a clean clone's view
        code, out, err = F.run(CS.main, ["--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        released = (self.root / "docs" / "spec" / "plan.yaml").read_bytes()
        code, out, err = F.run(PR.main, ["--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.root / "docs" / "spec" / "plan.yaml").read_bytes(), released)    # the dry run touched nothing


class CitationTests(unittest.TestCase):
    def plan(self):
        sources = [{"id": "architecture", "name": "Architecture document", "path": "docs/ground-truth/architecture.md", "status": "reviewed"}]
        return {"project": {"ground_truth": "docs/ground-truth/architecture.md"}, "sources": sources}

    def test_a_text_citation_is_kept_beside_the_source_refs_it_resolves_to(self):
        item = {"id": 3, "ground_truth": "Sections 3.4, 3.5", "depends": [], "unblocks": []}
        out = L._released_item(self.plan(), item)
        self.assertEqual(out["ground_truth"], "Sections 3.4, 3.5")
        self.assertEqual(out["source_refs"], [{"source": "architecture", "sections": "3.4, 3.5"}])
        released = dict(self.plan(), plan_view="released")
        self.assertEqual(L.ground_truth_citation(released, out), "Sections 3.4, 3.5")     # the row the specification shows

    def test_an_item_with_its_own_source_refs_keeps_the_row_written_from_them(self):
        item = {"id": 3, "ground_truth": "Sections 3.4", "source_refs": [{"source": "architecture", "sections": "3.4"}],
                "depends": [], "unblocks": []}
        workspace_row = L.ground_truth_citation(self.plan(), item)
        self.assertEqual(workspace_row, "Architecture document: Sections 3.4")
        out = L._released_item(self.plan(), item)
        self.assertEqual(out["ground_truth"], "")
        self.assertEqual(L.ground_truth_citation(dict(self.plan(), plan_view="released"), out), workspace_row)


class NewProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-ux-new-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        F.init_git(self.root)
        patcher = mock.patch.dict(os.environ, {"HOME": str(self.base), "USERPROFILE": str(self.base)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def init(self, answer):
        return F.run(W.main, ["init", "--root", str(self.root), "--slug", "new", "--workspace", str(self.base / "ws"), "--answer", answer, "--apply"])

    def test_step_0_on_yes_prints_no_legacy_or_migration_line(self):
        code, out, err = self.init("yes")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("legacy", out + err)
        code, out, err = F.run(SS.main, ["--root", str(self.root), "--init", "--name", "New", "--apply"])
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("legacy", out + err)

    def test_a_recorded_no_answer_refuses_a_draft_written_into_the_repository(self):
        code, out, err = self.init("no")
        self.assertEqual(code, 0, out + err)
        self.assertIn("repo_audience_approved: false", (self.base / "ws" / "workspace.yaml").read_text(encoding="utf-8"))
        code, out, err = F.run(SS.main, ["--root", str(self.root), "--init", "--name", "New", "--apply"])
        self.assertNotEqual(code, 0, out + err)
        self.assertIn("drafting-is-private", out + err)
        self.assertFalse((self.root / "docs" / "spec" / "plan.yaml").exists())


if __name__ == "__main__":
    unittest.main()
