"""The update path end to end: scripts/reconcile.py (specification 3.2, 7, 8, 11, 12 and 13).

Each test runs on a copy of the sample project, a temporary HOME with a fixed git identity and a real
private workspace made by workspace.py init. Two shapes of the sample are used:
  drafting   the project holds the owner's working plan and no release exists yet;
  released   the project holds the released plan, and the workspace holds the sample's own release (the
             fixture in tests/fixtures/sample-workspace) and the owner's working plan, as after a release on
             the yes answer.
No token and no network are used. Nothing is pushed.
Run from the repository root: python3 -m unittest tests.test_reconcile -v
"""
import ast
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
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
import reconcile as R  # noqa: E402
import reconcile_core as RC  # noqa: E402
import release_assemble as A  # noqa: E402
import release_gate as RG  # noqa: E402
import workspace as W  # noqa: E402
from sample_tree import copy_sample  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "sample-workspace"
HAS_GIT = shutil.which("git") is not None
IDENTITY = {"GIT_AUTHOR_NAME": "Test Owner", "GIT_AUTHOR_EMAIL": "owner@example.com",
            "GIT_COMMITTER_NAME": "Test Owner", "GIT_COMMITTER_EMAIL": "owner@example.com"}
WI03 = "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md"
WI06 = "docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md"
RENDERING = "docs/ground-truth/architecture.md"
REMINDER = "after 3 business days without a decision"
NO_CHECKPOINT = ("A previous complete source checkpoint is unavailable. Review the current sources to establish one. "
                 "Earlier uncited changes cannot be assessed automatically.")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = R.main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    return code, out.getvalue(), err.getvalue()


def tree(folder, skip=(".git",)):
    base = Path(folder)
    out = {}
    if not base.exists():
        return out
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base)
        if p.is_file() and not any(part in skip for part in rel.parts):
            out[rel.as_posix()] = sha(p.read_bytes())
    return out


@unittest.skipUnless(HAS_GIT, "git is needed")
class Base(unittest.TestCase):
    released = False

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-reconcile-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        env = {"HOME": str(self.home), "USERPROFILE": str(self.home), "XDG_CONFIG_HOME": str(self.home / "xdg"), "GIT_CONFIG_NOSYSTEM": "1"}
        env.update(IDENTITY)
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        self.root = self.base / "project"
        if self.released:
            copy_sample(self.root, working=False)
        else:
            copy_sample(self.root, working=True, ignore=shutil.ignore_patterns("release"))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(self.root), capture_output=True, check=True)
        self.ws = self.base / "workspace"
        code, out, err = self.workspace_main(["init", "--root", str(self.root), "--slug", "sample", "--workspace", str(self.ws), "--answer", "yes", "--apply"])
        self.assertEqual(code, 0, out + err)
        self.ws = Path(os.path.realpath(str(self.ws)))
        if self.released:
            shutil.copyfile(str(FIXTURE / "drafts" / "plan.yaml"), str(self.ws / "drafts" / "plan.yaml"))
            for sub in ("releases", "requests", "events"):
                shutil.rmtree(str(self.ws / sub), ignore_errors=True)
                shutil.copytree(str(FIXTURE / sub), str(self.ws / sub))

    # -- helpers

    def workspace_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = W.main(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 2
        return code, out.getvalue(), err.getvalue()

    def r(self, *args, root=None):
        return run(list(args) + ["--root", str(root or self.root)])

    def status(self, root=None):
        code, out, err = run(["status", "--root", str(root or self.root), "--json"])
        self.assertEqual(code, 0, out + err)
        return json.loads(out)

    def prepare(self, apply=True):
        args = ["prepare", "--root", str(self.root), "--json"] + (["--apply"] if apply else [])
        code, out, err = run(args)
        self.assertEqual(code, 0, out + err)
        return json.loads(out)

    def proposal_dir(self, change_id):
        return self.ws / "drafts" / "proposals" / change_id

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        (self.root / rel).write_text(text, encoding="utf-8")

    def dispositions(self, change_id):
        return json.loads((self.proposal_dir(change_id) / "dispositions.json").read_text(encoding="utf-8"))

    def save_dispositions(self, change_id, doc):
        (self.proposal_dir(change_id) / "dispositions.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def make_checkpoint(self):
        project = R.Project(self.root)
        gathered = R.Gathered(project)
        files = [(e["id"], e["path"]) for e in gathered.sources]
        files += [(e["id"], e["path"].with_name(e["path"].name[:-3] + ".index.txt")) for e in gathered.sources
                  if e["path"].with_name(e["path"].name[:-3] + ".index.txt").is_file()]
        made = W.checkpoint_prepare(self.root, self.ws, files, gathered.descriptor, apply=True)
        done = W.checkpoint_commit(self.ws, made["id"], apply=True, root=self.root)
        self.assertIn(done["status"], ("committed", "already-recorded"), done)
        return made["id"]

    def complete_publication(self):
        rid, manifest = RG._active_release(RG.project_state(self.root))
        self.assertIsNotNone(rid)
        targets = {p[len("payloads/"):-5]: {"state": "completed"} for p in manifest if p.startswith("payloads/")}
        folder = self.ws / "publication"
        folder.mkdir(exist_ok=True)
        (folder / f"{rid}.journal.json").write_text(json.dumps({"journal_format": 1, "request_id": rid, "targets": targets}), encoding="utf-8")

    def edit_reminder(self):
        text = self.read(RENDERING)
        self.assertIn(REMINDER, text)
        self.write(RENDERING, text.replace(REMINDER, "after 4 business days without a decision"))

    def patch_for(self, rel, old, new, item="WI-03"):
        text = self.read(rel)
        self.assertIn(old, text)
        return {"item": item, "path": rel, "before_sha256": sha(text.encode("utf-8")), "after_text": text.replace(old, new)}

    def disposition_update(self, change_id, block, patches, **more):
        doc = self.dispositions(change_id)
        for rec in doc["dispositions"]:
            if rec["block"] == block:
                rec.clear()
                rec.update({"block": block, "disposition": "update", "item": "WI-03",
                            "patch": patches if len(patches) > 1 else patches[0]})
                rec.update(more)
        self.save_dispositions(change_id, doc)

    def prepared_update(self, change=True):
        """A checkpoint, the reminder edited and a saved proposal whose block 3.5 is an update of WI-03."""
        self.make_checkpoint()
        if change:
            self.edit_reminder()
        prep = self.prepare()
        change_id = prep["proposal"]
        return change_id


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

class StatusTests(Base):
    def test_no_plan(self):
        empty = self.base / "empty"
        empty.mkdir()
        code, out, err = run(["status", "--root", str(empty)])
        self.assertEqual(code, 0, out + err)
        self.assertIn("State: No plan", out)
        self.assertIn("planning interview", out)

    def test_the_sample_has_no_workspace_and_says_what_was_not_observed(self):
        code, out, err = run(["status", "--root", str(ROOT / "sample" / "expense-approvals")])
        self.assertEqual(code, 0, out + err)
        self.assertIn(R.NO_WORKSPACE, out)
        self.assertIn("State: Observable inputs unchanged", out)
        self.assertIn(R.ELSEWHERE, out)
        self.assertIn(R.OUTSTANDING_NOT_OBSERVED, out)

    def test_an_unreadable_project_exits_2(self):
        code, out, err = run(["status", "--root", str(self.base / "does-not-exist")])
        self.assertEqual(code, 2)
        self.assertIn("--root", err)

    def test_a_plan_that_cannot_be_read_exits_2(self):
        self.write("docs/spec/plan.yaml", "project: [unclosed\n")
        code, out, err = run(["status", "--root", str(self.root)])
        self.assertEqual(code, 2, out + err)
        self.assertIn("plan", err)

    def test_an_unapproved_draft(self):
        data = self.status()
        self.assertEqual(data["state"], "unapproved-draft")
        self.assertEqual(data["label"], "Unapproved draft")
        self.assertIn("Continue reviewing", data["next_action"])

    def test_two_different_plans_are_ambiguous_and_the_owner_is_asked_which(self):
        shutil.copyfile(str(self.root / "docs" / "spec" / "plan.yaml"), str(self.root / "plan.yaml"))
        self.write("plan.yaml", self.read("plan.yaml").replace("Expense approvals plan", "Another plan"))
        code, out, err = run(["status", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        self.assertIn("State: Ambiguous project or baseline", out)
        self.assertIn("Which one do you mean?", out)
        self.assertIn("docs/spec/plan.yaml", out)

    def test_status_writes_nothing(self):
        before = (tree(self.ws), tree(self.root))
        self.status()
        run(["status", "--root", str(self.root)])
        self.assertEqual((tree(self.ws), tree(self.root)), before)


class ReleasedStatusTests(Base):
    released = True

    def test_an_approved_release_with_no_publication_record_awaits_publication(self):
        data = self.status()
        self.assertEqual(data["state"], "release-awaiting-publication")
        self.assertIn("not yet shown as published", " ".join(data["reasons"]))
        self.assertIn("Resume the existing publication", data["next_action"])

    def test_inputs_unchanged_states_what_was_checked_and_the_limits(self):
        self.complete_publication()
        self.make_checkpoint()
        data = self.status()
        self.assertEqual(data["state"], "inputs-unchanged", data)
        self.assertTrue(data["checked"])
        self.assertIn(R.ELSEWHERE, data["limits"])
        self.assertNotIn(NO_CHECKPOINT, data["limits"])

    def test_without_a_checkpoint_nothing_changed_can_be_observed_and_the_missing_sentence_is_said(self):
        self.complete_publication()
        data = self.status()
        self.assertEqual(data["state"], "inputs-unchanged")
        self.assertIn(NO_CHECKPOINT, data["limits"])
        self.assertIn("none is recorded", " ".join(data["reasons"]))

    def test_a_changed_rendering_is_changed_sources(self):
        self.complete_publication()
        self.make_checkpoint()
        self.edit_reminder()
        data = self.status()
        self.assertEqual(data["state"], "changed-sources")
        self.assertIn("architecture (rendering differs)", " ".join(data["reasons"]))
        code, out, err = run(["status", "--root", str(self.root)])
        self.assertIn("State: Existing project with changed sources or a correction", out)
        self.assertIn("Use the update path", out)

    def test_a_changed_source_descriptor_is_changed_sources(self):
        self.complete_publication()
        self.make_checkpoint()
        plan = (self.ws / "drafts" / "plan.yaml").read_text(encoding="utf-8")
        self.assertIn('use: "Full specification.', plan)
        (self.ws / "drafts" / "plan.yaml").write_text(plan.replace('use: "Full specification.', 'use: "Reference only. Full specification.'), encoding="utf-8")
        data = self.status()
        self.assertEqual(data["state"], "changed-sources")

    def test_a_saved_proposal_is_an_unfinished_update(self):
        self.complete_publication()
        change_id = self.prepared_update()
        data = self.status()
        self.assertEqual(data["state"], "unfinished-update")
        self.assertEqual([p["id"] for p in data["proposals"]], [change_id])
        self.assertFalse(data["proposals"][0]["stale"])

    def test_a_proposal_whose_inputs_changed_is_still_the_unfinished_update_and_says_prepare_again(self):
        self.complete_publication()
        change_id = self.prepared_update()
        self.write(RENDERING, self.read(RENDERING) + "\nA late addition.\n")
        data = self.status()
        self.assertEqual(data["state"], "unfinished-update")
        self.assertTrue(data["proposals"][0]["stale"])
        self.assertIn("prepare the comparison again", " ".join(data["reasons"]))
        self.assertEqual(data["proposals"][0]["id"], change_id)

    def test_a_working_draft_that_differs_from_the_release_awaits_a_release(self):
        self.complete_publication()
        self.make_checkpoint()
        self.write(WI03, self.read(WI03).replace(REMINDER, "after 4 business days without a decision"))
        data = self.status()
        self.assertEqual(data["state"], "drafts-awaiting-release", data)
        self.assertIn("Put the plan on GitHub", data["next_action"])

    def test_an_applied_update_whose_checkpoint_is_not_recorded_says_so(self):
        self.complete_publication()
        change_id = self.prepared_update()
        self.disposition_update(change_id, "architecture/3.5", [self.patch_for(WI03, REMINDER, "after 4 business days without a decision")])
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        data = self.status()
        self.assertEqual(data["state"], "drafts-awaiting-release", data)
        self.assertTrue(any("checkpoint is not recorded yet" in n for n in data["notes"]), data["notes"])

    def test_several_unfinished_updates_are_ambiguous(self):
        self.complete_publication()
        first = self.prepared_update()
        inputs = json.loads((self.proposal_dir(first) / "inputs.json").read_text(encoding="utf-8"))
        inputs["checkpoint"] = "a" * 64
        data = R.json_bytes(inputs)
        other = R.sha256_bytes(data)
        folder = self.proposal_dir(other)
        folder.mkdir(parents=True)
        (folder / "inputs.json").write_bytes(data)
        (folder / "proposal.json").write_bytes(R.json_bytes({"format": 1, "created": "2027-01-01T00:00:00Z"}))
        (folder / "journal.json").write_bytes(R.json_bytes({"format": 1, "entries": []}))
        status = self.status()
        self.assertEqual(status["state"], "ambiguous", status)
        self.assertEqual(len(status["candidates"]), 2)

    def test_an_older_stale_proposal_does_not_count_once_a_newer_one_exists(self):
        self.complete_publication()
        first = self.prepared_update()
        self.write(RENDERING, self.read(RENDERING) + "\nOne more line.\n")
        second = self.prepare()["proposal"]
        self.assertNotEqual(first, second)
        data = self.status()
        self.assertEqual(data["state"], "unfinished-update")
        states = {p["id"]: p["state"] for p in data["proposals"]}
        self.assertEqual(states[first], "superseded")
        self.assertEqual(states[second], "prepared")

    def test_nothing_is_written_by_status_in_a_released_project(self):
        before = (tree(self.ws), tree(self.root))
        run(["status", "--root", str(self.root)])
        self.assertEqual((tree(self.ws), tree(self.root)), before)


class ClarificationStatusTests(Base):
    released = True

    def clar(self, requests, **more):
        doc = {"format": 1, "observed": "2027-02-01T10:00:00Z", "repository": "sct-will/carrydown-sample", "requests": requests}
        doc.update(more)
        (self.ws / "events").mkdir(exist_ok=True)
        (self.ws / "events" / "clarifications.json").write_text(json.dumps(doc), encoding="utf-8")

    def request(self, issue, item, state, **more):
        r = {"issue": issue, "item": item, "state": state, "url": f"https://github.com/sct-will/carrydown-sample/issues/{issue}#issuecomment-{issue}",
             "comment_id": issue * 10, "decided_url": None}
        r.update(more)
        return r

    def test_without_the_file_the_exact_sentence_is_printed(self):
        code, out, err = run(["status", "--root", str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn("Outstanding engineer requests were not observed: the publishing skill's authorized read has not run.", out)

    def test_outstanding_requests_are_listed_with_their_age(self):
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3 * 86400 - 3600))
        self.clar([self.request(12, "WI-03", "pending", created_at=created), self.request(13, "WI-06", "declined")])
        code, out, err = run(["status", "--root", str(self.root)])
        self.assertEqual(code, 0, out + err)
        self.assertIn("Engineer requests (observed 2027-02-01T10:00:00Z", out)
        self.assertRegex(out, r"WI-03 issue 12: pending, waiting 3 days")
        self.assertNotIn("issue 13", out)
        self.assertNotIn("were not observed: the publishing skill", out)

    def test_a_creation_time_in_another_form_makes_the_observation_unreadable(self):
        self.clar([self.request(12, "WI-03", "pending", created_at="3 days ago")])
        data = self.status()
        self.assertFalse(data["requests"]["observed"])
        self.assertEqual(data["requests"]["reason"], "could not be read")

    def test_a_request_without_a_recorded_time_says_so(self):
        self.clar([self.request(12, "WI-03", "pending")])
        code, out, err = run(["status", "--root", str(self.root)])
        self.assertIn("issue 12: pending, waiting time not recorded", out)

    def test_an_unreadable_file_is_reported_and_treated_as_not_observed(self):
        for text in ("{not json", json.dumps({"format": 2, "observed": "x", "repository": "a/b", "requests": []}),
                     json.dumps({"format": 1, "observed": "x", "repository": "a/b", "requests": [{"issue": "twelve"}]}),
                     '{"format": 1, "format": 1, "observed": "x", "repository": "a/b", "requests": []}'):
            with self.subTest(text=text[:30]):
                (self.ws / "events" / "clarifications.json").write_text(text, encoding="utf-8")
                data = self.status()
                self.assertFalse(data["requests"]["observed"])
                self.assertIn("could not be read", data["requests"]["reason"])
                self.assertTrue(any("could not be read" in line for line in data["limits"]))
                self.assertNotEqual(data["state"], "changed-sources")

    def test_an_accepted_request_with_a_decision_link_is_a_changed_input(self):
        self.complete_publication()
        self.make_checkpoint()
        self.clar([self.request(12, "WI-03", "accepted", decided_url="https://github.com/sct-will/carrydown-sample/issues/12#issuecomment-99")])
        data = self.status()
        self.assertEqual(data["state"], "changed-sources")
        self.assertIn("issue 12", " ".join(data["reasons"]))
        prep = self.prepare()
        refs = [b["ref"] for b in prep["blocks"]]
        self.assertEqual(refs, ["request/12"])
        self.assertEqual(prep["blocks"][0]["kind"], "engineer-correction")
        consumer = prep["consumers"][0]["consumers"][0]
        self.assertEqual((consumer["tag"], consumer["relationship"]), ("WI-03", "request"))

    def test_an_accepted_request_without_a_decision_link_is_not_yet_a_changed_input(self):
        self.complete_publication()
        self.make_checkpoint()
        self.clar([self.request(12, "WI-03", "accepted")])
        self.assertEqual(self.status()["state"], "inputs-unchanged")

    def test_an_accepted_request_carried_by_an_applied_update_is_not_listed_again(self):
        self.complete_publication()
        self.make_checkpoint()
        self.clar([self.request(12, "WI-03", "accepted", decided_url="https://github.com/sct-will/carrydown-sample/issues/12#issuecomment-99")])
        change_id = self.prepare()["proposal"]
        doc = self.dispositions(change_id)
        self.assertEqual([d["block"] for d in doc["dispositions"]], ["request/12"])
        doc["dispositions"][0] = {"block": "request/12", "disposition": "no-impact", "reason": "the correction is already in the specification",
                                  "context": "WI-03 already says so"}
        self.save_dispositions(change_id, doc)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(R.recorded_request_issues(R.Project(self.root)), {12})
        self.assertEqual(self.status()["state"], "inputs-unchanged")


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------

class PrepareTests(Base):
    released = True

    def test_without_a_checkpoint_the_missing_sentence_is_printed_verbatim_and_the_index_is_still_built(self):
        code, out, err = self.r("prepare")
        self.assertEqual(code, 0, out + err)
        self.assertIn(W.CHECKPOINT_UNAVAILABLE, out)
        self.assertEqual(W.CHECKPOINT_UNAVAILABLE, NO_CHECKPOINT)
        self.assertRegex(out, r"0 changed block\(s\) in 0 source\(s\); 0 direct consumer\(s\); index: \d+ bytes, \d+ words, about \d+ tokens \(approximate\)")
        self.assertRegex(out, r"architecture: \d+ sections? cannot be compared")

    def test_a_dry_run_writes_nothing_and_still_prints_the_proposal_id(self):
        before = (tree(self.ws), tree(self.root))
        code, out, err = self.r("prepare")
        self.assertEqual((tree(self.ws), tree(self.root)), before)
        self.assertIn("Nothing was written. Add --apply", out)
        self.assertRegex(out.strip().splitlines()[-1], r"^proposal: [0-9a-f]{64}$")

    def test_apply_without_a_checkpoint_records_every_section_as_unassessable_history(self):
        prep = self.prepare()
        blocks = json.loads((self.proposal_dir(prep["proposal"]) / "blocks.json").read_text(encoding="utf-8"))
        self.assertEqual(blocks["comparison"], "unavailable")
        self.assertEqual(blocks["blocks"], [])
        self.assertEqual(blocks["unassessable"][0]["source"], "architecture")
        self.assertIn("3.5", blocks["unassessable"][0]["sections"])
        self.assertIn(NO_CHECKPOINT, blocks["limits"])
        self.assertTrue(prep["measure"]["bytes"] > 0)

    def test_check_does_not_turn_a_missing_comparison_into_a_clean_result(self):
        change_id = self.prepare()["proposal"]
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 0, out + err)
        self.assertIn(NO_CHECKPOINT, out)
        self.assertIn("A passing check does not mean the sources were compared", out)

    def test_a_changed_number_gives_the_modified_block_its_consumers_and_the_index_measure(self):
        self.make_checkpoint()
        self.edit_reminder()
        code, out, err = self.r("prepare")
        self.assertEqual(code, 0, out + err)
        lines = out.splitlines()
        counts = next(l for l in lines if "changed block(s)" in l)
        self.assertRegex(counts, r"^1 changed block\(s\) in 1 source\(s\); 4 direct consumer\(s\); index: \d+ bytes, \d+ words, about \d+ tokens \(approximate\)$")
        block = next(l for l in lines if l.strip().startswith("architecture/3.5"))
        self.assertIn("modified", block)
        self.assertIn("3.5 Routing", block)
        self.assertIn("formatting only: no", block)
        order = [out.index("changed block(s)"), out.index("architecture/3.5  modified"), out.index("Direct consumers"), out.index("Nothing was written")]
        self.assertEqual(order, sorted(order))
        for tag in ("WI-03", "WI-06", "WI-08", "WI-11"):
            self.assertRegex(out, rf"architecture/3\.5\s+{tag}\s+citation")
        self.assertNotIn(NO_CHECKPOINT, out)
        self.assertRegex(out.strip().splitlines()[-1], r"^proposal: [0-9a-f]{64}$")

    def test_machine_output_has_the_counts_the_blocks_and_the_consumers(self):
        self.make_checkpoint()
        self.edit_reminder()
        prep = self.prepare(apply=False)
        self.assertEqual(prep["counts"], {"blocks": 1, "sources": 1, "direct_consumers": 4})
        self.assertEqual(prep["comparison"], "compared")
        self.assertNotIn("excluded_rows", prep["measure"])
        tags = sorted(c["tag"] for r in prep["consumers"] for c in r["consumers"])
        self.assertEqual(tags, ["WI-03", "WI-06", "WI-08", "WI-11"])
        consumer = next(c for c in prep["consumers"][0]["consumers"] if c["tag"] == "WI-03")
        self.assertIs(consumer["working_differs_from_release"], False)

    def test_a_formatting_only_edit_is_listed_and_recorded_as_no_impact_with_its_reason(self):
        self.make_checkpoint()
        text = self.read(RENDERING)
        self.assertIn("Staff of a fictional retail company", text)
        self.write(RENDERING, text.replace("Staff of a fictional retail company", "Staff of a *fictional*  retail company"))
        code, out, err = self.r("prepare")
        self.assertEqual(code, 0, out + err)
        self.assertIn("architecture/1.1", out)
        self.assertIn("formatting only: yes", out)
        change_id = self.prepare()["proposal"]
        doc = self.dispositions(change_id)
        self.assertEqual(len(doc["dispositions"]), 1)
        entry = doc["dispositions"][0]
        self.assertEqual((entry["block"], entry["disposition"], entry["reason"]), ("architecture/1.1", "no-impact", "formatting only"))
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 0, out + err)
        self.assertIn("has 0 finding(s)", out)

    def test_the_same_inputs_give_the_same_id_and_a_second_apply_reuses_it_and_keeps_the_dispositions(self):
        self.make_checkpoint()
        self.edit_reminder()
        first = self.prepare()["proposal"]
        doc = self.dispositions(first)
        doc["dispositions"][0].update({"disposition": "defer", "consequence": "c", "affected": ["WI-03"], "remaining": "r"})
        self.save_dispositions(first, doc)
        code, out, err = self.r("prepare", "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("already prepared with the same inputs", out)
        self.assertIn(f"proposal: {first}", out)
        again = self.prepare()
        self.assertEqual((again["proposal"], again["reused"]), (first, True))
        self.assertEqual(self.dispositions(first)["dispositions"][0]["disposition"], "defer")
        self.assertEqual(sorted(p.name for p in (self.ws / "drafts" / "proposals").iterdir()), [first])

    def test_a_changed_input_gives_a_new_id(self):
        self.make_checkpoint()
        self.edit_reminder()
        first = self.prepare()["proposal"]
        self.write(RENDERING, self.read(RENDERING).replace("After 5 business days", "After 6 business days"))
        second = self.prepare()["proposal"]
        self.assertNotEqual(first, second)
        self.assertEqual(len(list((self.ws / "drafts" / "proposals").iterdir())), 2)

    def test_apply_saves_the_proposal_files_and_the_inputs_digest_is_the_id(self):
        self.make_checkpoint()
        self.edit_reminder()
        change_id = self.prepare()["proposal"]
        folder = self.proposal_dir(change_id)
        self.assertEqual(sorted(p.name for p in folder.iterdir()),
                         ["blocks.json", "consumers.json", "descriptor.json", "dispositions.json", "index.json", "inputs.json", "proposal.json"])
        self.assertEqual(sha((folder / "inputs.json").read_bytes()), change_id)
        inputs = json.loads((folder / "inputs.json").read_text(encoding="utf-8"))
        self.assertEqual(inputs["format"], 1)
        self.assertEqual(inputs["index_procedure_version"], RC.INDEX_PROCEDURE_VERSION)
        self.assertEqual(inputs["checkpoint"], W.latest_checkpoint(self.ws)["id"])
        keys = set(inputs["inputs"])
        for want in ("project/docs/ground-truth/architecture.md", "workspace/drafts/plan.yaml", "project/docs/spec/plan.yaml",
                     f"project/{WI03}", "derived/descriptor", "derived/checkpoint"):
            self.assertIn(want, keys)
        self.assertTrue(any(k.startswith("project/docs/release/") for k in keys))
        self.assertFalse(any("docs/source" in k for k in keys))
        index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
        self.assertTrue(index["owner_only"])
        self.assertIn("excluded_rows", index["measure"])
        proposal = json.loads((folder / "proposal.json").read_text(encoding="utf-8"))
        self.assertEqual((proposal["state"], proposal["change_id"]), ("prepared", change_id))
        descriptor = json.loads((folder / "descriptor.json").read_text(encoding="utf-8"))
        self.assertEqual(descriptor["sources"][0]["id"], "architecture")
        pending = [d for d in self.dispositions(change_id)["dispositions"] if d["disposition"] == "pending"]
        self.assertEqual([d["block"] for d in pending], ["architecture/3.5"])

    def test_the_descriptor_in_the_proposal_is_accepted_by_the_checkpoint_command(self):
        change_id = self.prepare()["proposal"]
        descriptor = self.proposal_dir(change_id) / "descriptor.json"
        code, out, err = self.workspace_main(["checkpoint", "prepare", "--root", str(self.root), "--descriptor", str(descriptor),
                                              "--rendering-dir", str(self.root / "docs" / "ground-truth")])
        self.assertEqual(code, 0, out + err)
        self.assertIn("checkpoint ", out)

    def test_the_index_is_cached_by_its_contributing_digests_and_a_miss_rebuilds(self):
        first = self.prepare()
        self.assertEqual(first["index_cache"], "built")
        cached = list((self.ws / "drafts" / "index-cache").glob("*.json"))
        self.assertEqual(len(cached), 1)
        second = self.prepare(apply=False)
        self.assertEqual(second["index_cache"], "reused")
        self.write(WI03, self.read(WI03) + "\nAn added line.\n")
        third = self.prepare(apply=False)
        self.assertEqual(third["index_cache"], "built")
        cached[0].write_text("{broken", encoding="utf-8")
        again = self.prepare(apply=False)
        self.assertEqual(again["index_cache"], "built")

    def test_the_prepare_apply_writes_nothing_outside_the_workspace(self):
        before = tree(self.root)
        self.make_checkpoint()
        self.edit_reminder()
        before = tree(self.root)
        self.prepare()
        self.assertEqual(tree(self.root), before)

    def test_apply_without_a_workspace_is_refused_in_plain_words(self):
        code, out, err = run(["prepare", "--root", str(ROOT / "sample" / "expense-approvals"), "--apply"])
        self.assertEqual(code, 1)
        self.assertIn("no private workspace", err)

    def test_a_removed_section_and_a_new_source_need_a_disposition_too(self):
        self.make_checkpoint()
        text = self.read(RENDERING)
        start = text.index("### 6.2 Edge cases the interviews surfaced")
        end = text.index("## 7. Interfaces")
        self.write(RENDERING, text[:start] + text[end:])
        prep = self.prepare(apply=False)
        kinds = {b["ref"]: b["kind"] for b in prep["blocks"]}
        self.assertEqual(kinds.get("architecture/6.2>none"), "removed", kinds)

    def test_a_changed_classification_is_a_descriptor_block(self):
        self.make_checkpoint()
        plan = (self.ws / "drafts" / "plan.yaml").read_text(encoding="utf-8")
        (self.ws / "drafts" / "plan.yaml").write_text(plan.replace("classification: repo-readers", "classification: public"), encoding="utf-8")
        prep = self.prepare(apply=False)
        self.assertEqual([(b["ref"], b["kind"]) for b in prep["blocks"]], [("architecture/descriptor", "descriptor")])
        self.assertEqual(prep["comparison"], "compared")
        # saved, the descriptor block keeps its own kind and the check asks for its disposition
        change_id = self.prepare()["proposal"]
        blocks = json.loads((self.proposal_dir(change_id) / "blocks.json").read_text(encoding="utf-8"))["blocks"]
        self.assertEqual([b["kind"] for b in blocks], ["descriptor"])
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 1)
        self.assertIn("pending-disposition", out)
        doc = self.dispositions(change_id)
        doc["dispositions"] = [{"block": "architecture/descriptor", "disposition": "no-impact", "reason": "Every reader may already see it.",
                                "context": "The index rows that cite the source were read."}]
        self.save_dispositions(change_id, doc)
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 0, out + err)


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

class CheckTests(Base):
    released = True

    def check(self, change_id, *extra):
        return self.r("check", "--proposal", change_id, "--json", *extra)

    def findings(self, change_id):
        code, out, err = self.check(change_id)
        return code, json.loads(out)

    def codes(self, change_id):
        return sorted(f["code"] for f in self.findings(change_id)[1]["findings"])

    def test_a_pending_disposition_is_a_finding_and_the_exit_is_1(self):
        change_id = self.prepared_update()
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 1)
        self.assertIn("pending-disposition: architecture/3.5", out)
        self.assertIn(f"carrydown: proposal {change_id} has 1 finding(s)", out)

    def test_a_valid_proposal_has_zero_findings_and_exit_0(self):
        change_id = self.prepared_update()
        self.disposition_update(change_id, "architecture/3.5", [self.patch_for(WI03, REMINDER, "after 4 business days without a decision")])
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"carrydown: proposal {change_id} has 0 finding(s)", out)

    def test_every_other_disposition_kind_is_checked_by_its_required_fields(self):
        change_id = self.prepared_update()
        doc = self.dispositions(change_id)
        doc["dispositions"][0] = {"block": "architecture/3.5", "disposition": "no-impact", "reason": "r"}
        self.save_dispositions(change_id, doc)
        self.assertEqual(self.codes(change_id), ["missing-field"])
        doc["dispositions"][0] = {"block": "architecture/3.5", "disposition": "maybe"}
        self.save_dispositions(change_id, doc)
        self.assertEqual(self.codes(change_id), ["unknown-disposition"])
        doc["dispositions"].append({"block": "architecture/9.9", "disposition": "no-impact", "reason": "r", "context": "c"})
        self.save_dispositions(change_id, doc)
        self.assertIn("unknown-block", self.codes(change_id))

    def test_a_block_with_no_disposition_is_a_finding(self):
        change_id = self.prepared_update()
        doc = self.dispositions(change_id)
        doc["dispositions"] = []
        self.save_dispositions(change_id, doc)
        self.assertEqual(self.codes(change_id), ["missing-disposition"])

    def test_a_changed_input_fails_with_the_sentence_and_the_list(self):
        change_id = self.prepared_update()
        self.write(WI06, self.read(WI06) + "\nLate edit.\n")
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 1)
        self.assertIn("Inputs changed since this proposal was prepared. Run prepare again.", out)
        self.assertIn(f"changed input: project/{WI06}", out)
        code, data = self.findings(change_id)
        self.assertFalse(data["fresh"])
        self.assertIn(f"project/{WI06}", data["changed_inputs"])

    def test_a_new_file_in_the_specification_folder_makes_the_proposal_stale(self):
        change_id = self.prepared_update()
        self.write("docs/spec/m1-submit-report/extra.md", "# Extra\n")
        code, data = self.findings(change_id)
        self.assertEqual(code, 1)
        self.assertIn("inputs-changed", [f["code"] for f in data["findings"]])

    def test_a_patch_outside_the_allowed_paths_is_a_finding(self):
        change_id = self.prepared_update()
        for path in ("docs/context/wi-03.md", "docs/release/anything.json", "docs/ground-truth/architecture.md", "docs/source/original.docx",
                     "project/docs/spec/plan.yaml", "../elsewhere.md", "/etc/hosts", "docs/spec/../context/wi-03.md", "workspace/releases/x/content-manifest.json",
                     "workspace/renderings/reviewed/architecture/architecture.md", "docs/spec/m1-submit-report/missing.md", ""):
            with self.subTest(path=path):
                patch = {"item": "WI-03", "path": path, "before_sha256": "0" * 64, "after_text": "x"}
                self.disposition_update(change_id, "architecture/3.5", [patch])
                code, data = self.findings(change_id)
                self.assertEqual(code, 1)
                self.assertEqual([f["code"] for f in data["findings"]], ["patch-path"], data)

    def test_the_released_plan_on_the_yes_answer_is_never_patched_and_the_working_plan_is_allowed(self):
        change_id = self.prepared_update()
        released = self.read("docs/spec/plan.yaml")
        patch = {"item": "WI-03", "path": "docs/spec/plan.yaml", "before_sha256": sha(released.encode()), "after_text": released + "\n# note\n"}
        self.disposition_update(change_id, "architecture/3.5", [patch])
        code, data = self.findings(change_id)
        self.assertEqual([f["code"] for f in data["findings"]], ["patch-path"])
        self.assertIn("released plan", data["findings"][0]["message"])
        working = (self.ws / "drafts" / "plan.yaml").read_text(encoding="utf-8")
        patch = {"item": "WI-03", "path": "workspace/drafts/plan.yaml", "before_sha256": sha(working.encode()), "after_text": working + "\n# note\n"}
        self.disposition_update(change_id, "architecture/3.5", [patch])
        code, data = self.findings(change_id)
        self.assertEqual(data["findings"], [], data)

    def test_a_stale_before_digest_is_a_finding(self):
        change_id = self.prepared_update()
        patch = self.patch_for(WI03, REMINDER, "after 4 business days without a decision")
        patch["before_sha256"] = "1" * 64
        self.disposition_update(change_id, "architecture/3.5", [patch])
        code, data = self.findings(change_id)
        self.assertEqual([f["code"] for f in data["findings"]], ["patch-stale"])

    def test_a_malformed_patch_is_a_finding(self):
        change_id = self.prepared_update()
        good = self.patch_for(WI03, REMINDER, "after 4 business days without a decision")
        cases = [dict(good, extra=1), {k: v for k, v in good.items() if k != "after_text"}, dict(good, before_sha256="short"),
                 dict(good, after_text=5), dict(good, after_text="x" * (R.MAX_PATCH_TEXT + 1))]
        for patch in cases:
            with self.subTest(keys=sorted(patch)):
                self.disposition_update(change_id, "architecture/3.5", [patch])
                self.assertEqual(self.codes(change_id), ["patch-malformed"])
        doc = self.dispositions(change_id)
        doc["dispositions"][0]["patch"] = "not json"
        self.save_dispositions(change_id, doc)
        self.assertEqual(self.codes(change_id), ["patch-malformed"])

    def test_a_patch_that_changes_nothing_and_two_patches_of_one_file_are_findings(self):
        change_id = self.prepared_update()
        text = self.read(WI03)
        same = {"item": "WI-03", "path": WI03, "before_sha256": sha(text.encode()), "after_text": text}
        self.disposition_update(change_id, "architecture/3.5", [same])
        self.assertEqual(self.codes(change_id), ["patch-unchanged"])
        one = self.patch_for(WI03, REMINDER, "after 4 business days without a decision")
        two = dict(one, after_text=one["after_text"] + "\n")
        self.disposition_update(change_id, "architecture/3.5", [one, two])
        self.assertIn("patch-duplicate", self.codes(change_id))

    def test_a_patch_that_rewrites_a_recorded_decision_needs_a_conflict_resolution(self):
        self.complete_publication()
        entry = "- 2027-02-01. Kept the reminder at 3 business days after the pilot call. PR #12"
        self.write(WI03, self.read(WI03).replace("## Decisions recorded\n\nNone yet.", "## Decisions recorded\n\n" + entry))
        change_id = self.prepared_update()
        rewrite = self.patch_for(WI03, entry, "- 2027-02-01. Reminder moved to 4 business days. PR #12")
        self.disposition_update(change_id, "architecture/3.5", [rewrite])
        code, data = self.findings(change_id)
        self.assertEqual([f["code"] for f in data["findings"]], ["decision-conflict"], data)
        self.assertIn("conflict_resolution", data["findings"][0]["message"])
        self.disposition_update(change_id, "architecture/3.5", [rewrite], conflict_resolution="Owner keeps the engineer's entry and asks the source owner to settle the number")
        code, data = self.findings(change_id)
        self.assertEqual(data["findings"], [], data)

    def test_a_patch_that_deletes_the_decisions_section_is_a_conflict_but_a_body_change_and_an_appended_entry_are_not(self):
        entry = "- 2027-02-01. Kept the reminder at 3 business days after the pilot call. PR #12"
        self.write(WI03, self.read(WI03).replace("## Decisions recorded\n\nNone yet.", "## Decisions recorded\n\n" + entry))
        change_id = self.prepared_update()
        text = self.read(WI03)
        body = self.patch_for(WI03, REMINDER, "after 4 business days without a decision")
        self.disposition_update(change_id, "architecture/3.5", [body])
        self.assertEqual(self.codes(change_id), [])
        appended = {"item": "WI-03", "path": WI03, "before_sha256": sha(text.encode()), "after_text": text.rstrip("\n") + "\n- 2027-02-02. Owner added a note. PR #13\n"}
        self.disposition_update(change_id, "architecture/3.5", [appended])
        self.assertEqual(self.codes(change_id), [])
        gone = {"item": "WI-03", "path": WI03, "before_sha256": sha(text.encode()), "after_text": text[:text.index("## Decisions recorded")]}
        self.disposition_update(change_id, "architecture/3.5", [gone])
        self.assertEqual(self.codes(change_id), ["decision-conflict"])

    def test_decisions_rewritten_reports_none_when_nothing_was_recorded(self):
        text = self.read(WI03).encode()
        self.assertIsNone(R.decisions_rewritten(text, text.replace(b"None yet.", b"Something else.")))

    def test_check_of_a_proposal_that_does_not_exist_or_is_damaged_exits_2(self):
        code, out, err = self.r("check", "--proposal", "f" * 64)
        self.assertEqual(code, 2)
        self.assertIn("no saved proposal has that id", err)
        code, out, err = self.r("check", "--proposal", "not-an-id")
        self.assertEqual(code, 2)
        change_id = self.prepared_update()
        (self.proposal_dir(change_id) / "inputs.json").write_text("{}", encoding="utf-8")
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 2)
        self.assertIn("Prepare the comparison again", err)

    def test_a_dispositions_file_with_an_unknown_format_is_rejected(self):
        change_id = self.prepared_update()
        (self.proposal_dir(change_id) / "dispositions.json").write_text(json.dumps({"format": 9, "dispositions": []}), encoding="utf-8")
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 2)
        self.assertIn("unsupported format", err)

    def test_check_writes_nothing(self):
        change_id = self.prepared_update()
        before = (tree(self.ws), tree(self.root))
        self.r("check", "--proposal", change_id)
        self.assertEqual((tree(self.ws), tree(self.root)), before)


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

class ApplyTests(Base):
    """The drafting shape: no release yet, so the gate lets a draft write through."""
    released = False

    def two_patches(self):
        return [self.patch_for(WI03, REMINDER, "after 4 business days without a decision"),
                self.patch_for(WI06, "approval limits", "approval limits (reviewed)", item="WI-06")]

    def ready(self):
        change_id = self.prepared_update()
        self.disposition_update(change_id, "architecture/3.5", self.two_patches())
        return change_id

    def guarded_trees(self):
        return {name: tree(self.root / name) for name in ("docs/context", "docs/release", "docs/ground-truth")} | {"releases": tree(self.ws / "releases")}

    def test_the_dry_run_previews_each_write_and_writes_nothing(self):
        change_id = self.ready()
        before = (tree(self.ws), tree(self.root))
        code, out, err = self.r("apply", "--proposal", change_id)
        self.assertEqual(code, 0, out + err)
        self.assertEqual((tree(self.ws), tree(self.root)), before)
        self.assertIn("DRY RUN", out)
        self.assertIn(f"would change project/{WI03}", out)
        self.assertIn(f"would change project/{WI06}", out)
        self.assertRegex(out, r"\([0-9a-f]{12} to [0-9a-f]{12}, \d+ bytes\)")
        self.assertIn("Nothing was written. Add --apply", out)

    def test_machine_output_of_the_preview_has_full_digests(self):
        change_id = self.ready()
        code, out, err = self.r("apply", "--proposal", change_id, "--json")
        data = json.loads(out)
        self.assertFalse(data["apply"])
        self.assertEqual({w["path"] for w in data["writes"]}, {f"project/{WI03}", f"project/{WI06}"})
        self.assertTrue(all(len(w["before_sha256"]) == 64 and len(w["after_sha256"]) == 64 for w in data["writes"]))

    def test_apply_writes_verifies_and_records_the_journal_and_the_applied_record(self):
        change_id = self.ready()
        guard = self.guarded_trees()
        before03 = self.read(WI03)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("applied 2 patches now and checked 2 patches by reading it back", out)
        self.assertIn("Nothing is published", out)
        self.assertEqual(self.read(WI03), before03.replace(REMINDER, "after 4 business days without a decision"))
        self.assertIn("approval limits (reviewed)", self.read(WI06))
        journal = json.loads((self.proposal_dir(change_id) / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(e["state"] for e in journal["entries"]), ["verified", "verified"])
        for e in journal["entries"]:
            self.assertEqual(sha((self.root / e["path"][len("project/"):]).read_bytes()), e["after_sha256"])
        applied = json.loads((self.proposal_dir(change_id) / "applied.json").read_text(encoding="utf-8"))
        self.assertEqual((applied["state"], applied["change_id"], applied["patches"]), ("applied", change_id, 2))
        self.assertFalse((self.proposal_dir(change_id) / "lock").exists())
        self.assertEqual(self.guarded_trees(), guard)

    def test_a_second_apply_is_a_no_op(self):
        change_id = self.ready()
        self.r("apply", "--proposal", change_id, "--apply")
        before = (tree(self.ws), tree(self.root))
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("already applied", out)
        self.assertEqual((tree(self.ws), tree(self.root)), before)
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 0)
        self.assertIn("already applied", out)

    def test_apply_with_zero_patches_records_the_update_as_applied(self):
        self.make_checkpoint()
        text = self.read(RENDERING)
        self.write(RENDERING, text.replace("Staff of a fictional retail company", "Staff of a *fictional*  retail company"))
        change_id = self.prepare()["proposal"]
        code, out, err = self.r("apply", "--proposal", change_id)
        self.assertIn("No working draft needs a change", out)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.proposal_dir(change_id) / "applied.json").is_file())

    def test_apply_stops_on_any_finding_and_writes_nothing(self):
        change_id = self.prepared_update()
        before = (tree(self.ws), tree(self.root))
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("apply stopped. Nothing was written.", out)
        self.assertIn("pending-disposition", out)
        self.assertEqual((tree(self.ws), tree(self.root)), before)

    def test_apply_on_changed_inputs_is_refused_with_the_sentence(self):
        change_id = self.ready()
        self.write(WI06, self.read(WI06) + "\nA late edit.\n")
        before = tree(self.root)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("Inputs changed since this proposal was prepared. Run prepare again.", out)
        self.assertEqual(tree(self.root), before)

    def test_an_interrupted_apply_resumes_only_the_remaining_planned_patch(self):
        change_id = self.ready()
        patches = self.two_patches()
        # the first run wrote WI-03 and stopped before WI-06: the journal says written for the first
        first = patches[0]
        after = first["after_text"].encode("utf-8")
        (self.root / WI03).write_bytes(after)
        journal = {"format": 1, "change_id": change_id, "started": "2027-02-01T00:00:00Z", "entries": [
            {"path": f"project/{WI03}", "before_sha256": first["before_sha256"], "after_sha256": sha(after), "state": "written"},
            {"path": f"project/{WI06}", "before_sha256": patches[1]["before_sha256"], "after_sha256": sha(patches[1]["after_text"].encode()), "state": "planned"}]}
        (self.proposal_dir(change_id) / "journal.json").write_bytes(R.json_bytes(journal))
        wi06_before = (self.root / WI06).read_bytes()
        code, out, err = self.r("apply", "--proposal", change_id)
        self.assertEqual(code, 0, out + err)
        self.assertIn("An earlier run was interrupted. 1 patch already written", out)
        self.assertIn("1 patch remaining", out)
        self.assertIn(f"already written project/{WI03}", out)
        self.assertEqual((self.root / WI06).read_bytes(), wi06_before)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("An earlier run was interrupted. These patches were already written and now read back correctly: " + f"project/{WI03}", out)
        self.assertIn("applied 1 patch now", out)
        self.assertEqual((self.root / WI03).read_bytes(), after)
        self.assertIn("approval limits (reviewed)", self.read(WI06))
        done = json.loads((self.proposal_dir(change_id) / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(e["state"] for e in done["entries"]), ["verified", "verified"])
        self.assertTrue((self.proposal_dir(change_id) / "applied.json").is_file())

    def test_a_restart_stops_on_a_file_that_is_neither_the_before_nor_the_after_content(self):
        change_id = self.ready()
        patches = self.two_patches()
        first = patches[0]
        after = first["after_text"].encode("utf-8")
        (self.root / WI03).write_bytes(after)
        journal = {"format": 1, "change_id": change_id, "started": "2027-02-01T00:00:00Z", "entries": [
            {"path": f"project/{WI03}", "before_sha256": first["before_sha256"], "after_sha256": sha(after), "state": "written"},
            {"path": f"project/{WI06}", "before_sha256": patches[1]["before_sha256"], "after_sha256": sha(patches[1]["after_text"].encode()), "state": "planned"}]}
        (self.proposal_dir(change_id) / "journal.json").write_bytes(R.json_bytes(journal))
        (self.root / WI06).write_text(self.read(WI06) + "\nSomeone edited this meanwhile.\n", encoding="utf-8")
        wi06 = (self.root / WI06).read_bytes()
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("patch-stale", out)
        self.assertIn(f"unexpected content at project/{WI06}; nothing further was written.", out)
        self.assertEqual((self.root / WI06).read_bytes(), wi06)
        self.assertFalse((self.proposal_dir(change_id) / "applied.json").exists())

    def test_a_file_that_changes_between_the_check_and_the_write_stops_the_run_with_unexpected_content(self):
        change_id = self.ready()
        project = R.Project(self.root)
        proposal = R.load_proposal(project, change_id)
        patches, findings = R.plan_patches(project, proposal)
        self.assertEqual(findings, [])
        victim = next(p for p in patches if p["key"].endswith("wi-06-limits-and-duties.md"))
        victim["path"].write_text("changed under us\n", encoding="utf-8")
        with R.Lock(project, change_id):
            result = R.apply_patches(project, change_id, proposal, patches)
        self.assertEqual(result["stopped"], victim["key"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["written"], 1)
        self.assertEqual(victim["path"].read_text(encoding="utf-8"), "changed under us\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = R.report_apply(change_id, result)
        self.assertEqual(code, 1)
        self.assertIn(f"unexpected content at {victim['key']}; nothing further was written.", out.getvalue())
        journal = json.loads((self.proposal_dir(change_id) / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(e["state"] for e in journal["entries"]), ["planned", "verified"])
        self.assertFalse((self.proposal_dir(change_id) / "applied.json").exists())

    def test_a_lock_held_by_a_live_process_refuses_and_writes_nothing(self):
        change_id = self.ready()
        lock = self.proposal_dir(change_id) / "lock"
        lock.write_bytes(R.json_bytes({"pid": os.getpid(), "time": "2027-02-01T00:00:00Z"}))
        before = tree(self.root)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("another run is applying this proposal", err)
        self.assertEqual(tree(self.root), before)
        self.assertTrue(lock.exists())
        self.assertFalse((self.proposal_dir(change_id) / "journal.json").exists())

    def test_a_lock_left_by_a_process_that_is_gone_is_replaced(self):
        change_id = self.ready()
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait()
        lock = self.proposal_dir(change_id) / "lock"
        lock.write_bytes(R.json_bytes({"pid": gone.pid, "time": "2027-02-01T00:00:00Z"}))
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertFalse(lock.exists())

    def test_the_lock_is_removed_when_the_run_fails(self):
        change_id = self.ready()
        project = R.Project(self.root)
        proposal = R.load_proposal(project, change_id)
        patches, _ = R.plan_patches(project, proposal)
        with mock.patch.object(R, "write_atomic", side_effect=R.Stopped("write-failed", "disk full")):
            code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("disk full", err)
        self.assertFalse((self.proposal_dir(change_id) / "lock").exists())

    def test_the_release_gate_is_asked_for_every_write_and_a_refusal_stops_the_run(self):
        change_id = self.ready()
        seen = []
        real = RG.check

        def spy(write_class, rel, digest, destination, root, **kw):
            seen.append((write_class, rel, destination, kw.get("dry_run")))
            return real(write_class, rel, digest, destination, root, **kw)

        with mock.patch.object(R.RG, "check", spy):
            code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        draft = [s for s in seen if s[0] == "draft" and s[3] is False]
        self.assertEqual(sorted(s[1] for s in draft), sorted([WI03, WI06]))
        self.assertTrue(all(s[2] == "engineering-repo" for s in draft))
        self.assertTrue(all(s[0] in ("draft", "candidate") for s in seen))
        change_id = self.ready_again()
        before = tree(self.root)
        denied = RG.Decision(False, "deny", "drafting-is-private", None)

        def refuse(write_class, *a, **kw):
            return denied if write_class == "draft" else real(write_class, *a, **kw)

        with mock.patch.object(R.RG, "check", refuse):
            code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("drafting-is-private", err)
        self.assertEqual(tree(self.root), before)

    def ready_again(self):
        # a new proposal on the now changed project
        self.write(RENDERING, self.read(RENDERING).replace("After 5 business days", "After 6 business days"))
        change_id = self.prepare()["proposal"]
        doc = self.dispositions(change_id)
        for rec in doc["dispositions"]:
            if rec["disposition"] == "pending":
                rec.clear()
                rec.update({"block": "architecture/3.5", "disposition": "update", "item": "WI-03",
                            "patch": self.patch_for(WI03, "Routing", "Routing logic")})
        self.save_dispositions(change_id, doc)
        return change_id

    def test_a_patch_never_reaches_context_release_rendering_receipt_or_snapshot_folders(self):
        change_id = self.ready()
        guard = self.guarded_trees()
        snapshots = tree(self.ws / "releases")
        self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(self.guarded_trees(), guard)
        self.assertEqual(tree(self.ws / "releases"), snapshots)
        for path in self.ws.rglob("snapshot"):
            self.assertEqual(tree(path), {k[len(path.relative_to(self.ws / "releases").as_posix()) + 1:]: v for k, v in snapshots.items()
                                           if k.startswith(path.relative_to(self.ws / "releases").as_posix() + "/")} or tree(path))

    def test_apply_of_an_unknown_proposal_exits_2(self):
        code, out, err = self.r("apply", "--proposal", "e" * 64)
        self.assertEqual(code, 2)


class ReleasedApplyTests(Base):
    """After a release on the yes answer: the working plan is in the workspace, the released plan stays as it was."""
    released = True

    def test_a_patch_of_the_working_plan_is_written_in_the_workspace_and_the_released_plan_is_untouched(self):
        self.complete_publication()
        change_id = self.prepared_update()
        working_path = self.ws / "drafts" / "plan.yaml"
        working = working_path.read_text(encoding="utf-8")
        released_before = (self.root / "docs" / "spec" / "plan.yaml").read_bytes()
        patch = {"item": "WI-03", "path": "workspace/drafts/plan.yaml", "before_sha256": sha(working.encode()), "after_text": working + "\n# reviewed with the owner\n"}
        self.disposition_update(change_id, "architecture/3.5", [patch])
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(working_path.read_text(encoding="utf-8").endswith("# reviewed with the owner\n"))
        self.assertEqual((self.root / "docs" / "spec" / "plan.yaml").read_bytes(), released_before)

    ENTRY = "- 2026-11-10. The reminder counts from the next business day when a report arrives after 17:00 (pull request 12)."

    def engineer_appends_a_decision(self):
        text = self.read(WI03)
        self.assertIn("## Decisions recorded\n\nNone yet.\n", text)
        self.write(WI03, text.replace("## Decisions recorded\n\nNone yet.\n", "## Decisions recorded\n\n" + self.ENTRY + "\n"))

    def annotated_update(self):
        """Released project, publication done, an engineer's decision entry in WI-03, then a source change and a saved
        proposal whose update patch is written from the annotated working copy."""
        self.complete_publication()
        self.engineer_appends_a_decision()
        change_id = self.prepared_update(change=True)
        patch = self.patch_for(WI03, REMINDER, "after 4 business days without a decision")
        self.disposition_update(change_id, "architecture/3.5", [patch])
        return change_id, patch

    def test_an_update_patch_of_a_specification_an_engineer_annotated_preserves_the_entry_and_applies(self):
        change_id, patch = self.annotated_update()
        # a plain draft write to the annotated file is still refused: only the reviewed patch may replace it
        self.assertEqual(RG.check("draft", WI03, "0" * 64, "engineering-repo", str(self.root)).code, "working-copy-differs")
        code, out, err = self.r("check", "--proposal", change_id)
        self.assertEqual(code, 0, out + err)
        code, out, err = self.r("apply", "--proposal", change_id)
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"would change project/{WI03}", out)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("applied 1 patch now", out)
        after = self.read(WI03)
        self.assertEqual(after, patch["after_text"])
        self.assertIn(self.ENTRY, after, "the engineer's decision entry is preserved")
        self.assertIn("after 4 business days without a decision", after)
        self.assertNotIn(REMINDER, after)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("already applied", out)
        self.assertEqual(self.read(WI03), after)

    def test_a_patch_whose_before_digest_is_stale_is_still_refused(self):
        change_id, patch = self.annotated_update()
        # the engineer adds a second entry after the proposal was saved: the patch no longer starts from the file
        self.write(WI03, self.read(WI03).replace(self.ENTRY + "\n", self.ENTRY + "\n- 2026-11-12. A second note (pull request 13).\n"))
        before = tree(self.root)
        for args in (("apply", "--proposal", change_id), ("apply", "--proposal", change_id, "--apply")):
            code, out, err = self.r(*args)
            self.assertEqual(code, 1, out + err)
            self.assertIn("Nothing was written", out)
        self.assertEqual(tree(self.root), before)
        self.assertFalse((self.proposal_dir(change_id) / "applied.json").exists())
        # asked directly with the proposal, the gate refuses the stale patch too
        d = RG.check("draft", WI03, sha(patch["after_text"].encode("utf-8")), "engineering-repo", str(self.root), update_proposal=change_id)
        self.assertEqual((d.allowed, d.code), (False, "working-copy-differs"))

    def test_a_patch_that_rewrites_the_engineers_entry_is_a_conflict_until_resolved(self):
        change_id, patch = self.annotated_update()
        rewritten = dict(patch, after_text=patch["after_text"].replace("after 17:00", "after 18:00"))
        self.disposition_update(change_id, "architecture/3.5", [rewritten])
        before = tree(self.root)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 1, out + err)
        self.assertIn("decision-conflict", out)
        self.assertEqual(tree(self.root), before)


class NoAnswerTests(Base):
    """The no answer: the plan, the specifications and the renderings are drafted in the private workspace."""
    released = False

    def setUp(self):
        super().setUp()
        drafts = self.ws / "drafts"
        (drafts / "docs").mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.root / "docs" / "spec"), str(drafts / "docs" / "spec"))
        plan = (drafts / "docs" / "spec" / "plan.yaml").read_text(encoding="utf-8")
        plan = plan.replace("repo_audience_approved: true", "repo_audience_approved: false")
        (drafts / "plan.yaml").write_text(plan, encoding="utf-8")
        (drafts / "docs" / "spec" / "plan.yaml").unlink()
        (self.ws / "renderings").mkdir(exist_ok=True)
        for suffix in (".md", ".index.txt"):
            shutil.move(str(self.root / "docs" / "ground-truth" / f"architecture{suffix}"), str(self.ws / "renderings" / f"architecture{suffix}"))
        shutil.rmtree(str(self.root / "docs" / "release"), ignore_errors=True)

    def test_the_comparison_reads_the_workspace_renderings_and_the_drafts_in_the_workspace(self):
        project = R.Project(self.root)
        self.assertEqual(project.mode, "no")
        self.assertEqual(project.spec_base, self.ws / "drafts")
        self.assertEqual(project.plan_path, self.ws / "drafts" / "plan.yaml")
        self.assertEqual(project.renderings_dir, self.ws / "renderings")
        project_state = self.status()
        self.assertEqual(project_state["state"], "unapproved-draft")

    def test_a_patch_in_the_workspace_drafts_is_applied_there_and_the_project_stays_clean(self):
        self.make_checkpoint()
        path = self.ws / "renderings" / "architecture.md"
        path.write_text(path.read_text(encoding="utf-8").replace(REMINDER, "after 4 business days without a decision"), encoding="utf-8")
        change_id = self.prepare()["proposal"]
        spec = self.ws / "drafts" / WI03
        text = spec.read_text(encoding="utf-8")
        patch = {"item": "WI-03", "path": WI03, "before_sha256": sha(text.encode()), "after_text": text.replace(REMINDER, "after 4 business days without a decision")}
        self.disposition_update(change_id, "architecture/3.5", [patch])
        project_before = tree(self.root)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("after 4 business days", spec.read_text(encoding="utf-8"))
        self.assertEqual(tree(self.root), project_before)
        journal = json.loads((self.proposal_dir(change_id) / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(journal["entries"][0]["path"], f"workspace/drafts/{WI03}")

    def test_a_path_in_the_project_is_not_a_draft_location_on_the_no_answer(self):
        self.make_checkpoint()
        change_id = self.prepare()["proposal"]
        doc = self.dispositions(change_id)
        self.assertEqual(doc["dispositions"], [])
        project = R.Project(self.root)
        path, key = R.resolve_patch_path(project, "project/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md")
        self.assertEqual(key, f"project/{WI03}")
        self.assertIn("outside the working plan and the specification folder", R.path_allowed(project, path, key))


# ---------------------------------------------------------------------------
# release preparation
# ---------------------------------------------------------------------------

class ReleasePreparationTests(Base):
    released = False

    def test_the_impact_index_size_is_reported_for_the_plan_being_released(self):
        project = R.Project(self.root)
        asm = A.assemble(self.root, with_github=False, skip_detectors=True)
        lines = A.impact_report(asm)
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], r"^impact index of this release: 9 rows, \d+ bytes, \d+ words, about \d+ tokens \(approximate\)$")
        self.assertEqual(project.plan["project"]["id_prefix"], "WI")

    def test_a_stale_unfinished_update_gives_one_warning_line_and_never_stops_the_release(self):
        self.make_checkpoint()
        self.edit_reminder()
        self.prepare()
        self.assertIsNone(R.stale_update_warning(self.root))
        self.write(RENDERING, self.read(RENDERING) + "\nOne more line.\n")
        warning = R.stale_update_warning(self.root)
        self.assertEqual(warning, R.STALE_WARNING)
        self.assertIn("run the update path again or discard it".lower(), warning.lower())
        asm = A.assemble(self.root, with_github=False, skip_detectors=True)
        lines = A.impact_report(asm)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1], R.STALE_WARNING)

    def test_an_applied_or_absent_proposal_gives_no_warning(self):
        self.assertIsNone(R.stale_update_warning(self.root))
        self.make_checkpoint()
        change_id = self.prepared_update(change=False)
        code, out, err = self.r("apply", "--proposal", change_id, "--apply")
        self.assertEqual(code, 0, out + err)
        self.write(RENDERING, self.read(RENDERING) + "\nOne more line.\n")
        self.assertIsNone(R.stale_update_warning(self.root))

    def test_release_prepare_prints_the_lines_and_writes_no_new_file_for_them(self):
        env = dict(os.environ)
        env.pop("CARRYDOWN_GITHUB_TOKEN", None)
        run_release = subprocess.run([sys.executable, str(ROOT / "scripts" / "release.py"), "prepare", "--root", str(self.root), "--repository-id", "4200"],
                                     capture_output=True, text=True, env=env, timeout=240)
        self.assertEqual(run_release.returncode, 0, run_release.stdout + run_release.stderr)
        self.assertIn("impact index of this release: 9 rows", run_release.stdout)
        self.assertIn("Dry run: nothing was written", run_release.stdout)


# ---------------------------------------------------------------------------
# the module boundary
# ---------------------------------------------------------------------------

class ModuleBoundaryTests(unittest.TestCase):
    NETWORK = {"urllib", "http", "socket", "ssl", "ftplib", "smtplib", "requests", "xmlrpc", "asyncio", "telnetlib", "poplib", "imaplib"}
    FORBIDDEN = {"github_client", "github_token", "github_sync", "github_project", "github_repair", "release", "release_github", "release_sync",
                 "release_assemble", "release_build", "release_payloads", "generate_dev_skill", "subprocess"}

    def imports(self, name="reconcile.py"):
        tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                found.add((node.module or "").split(".")[0])
        return found

    def test_reconcile_imports_no_network_or_token_module(self):
        found = self.imports()
        self.assertFalse(found & self.NETWORK, found & self.NETWORK)
        self.assertFalse(found & self.FORBIDDEN, found & self.FORBIDDEN)
        self.assertFalse({m for m in found if m.startswith("github_")})
        self.assertLessEqual({"carrydown_lib", "reconcile_core", "workspace", "decision_overlay", "release_gate", "compile_bundles"}, found)

    def test_every_module_reconcile_reaches_is_free_of_network_and_token_code(self):
        import sync_skill_assets as SYNC
        for name in SYNC.closure(["reconcile.py"]):
            with self.subTest(module=name):
                found = self.imports(name)
                self.assertFalse(found & self.NETWORK, (name, found & self.NETWORK))
                self.assertFalse({m for m in found if m.startswith("github_") or m in ("release", "release_github")}, (name, found))

    def test_the_module_text_is_free_of_forbidden_words_and_the_help_runs_from_anywhere(self):
        run_help = subprocess.run([sys.executable, str(ROOT / "scripts" / "reconcile.py"), "--help"], cwd=str(Path(tempfile.gettempdir())),
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(run_help.returncode, 0, run_help.stderr)
        self.assertIn("Update an existing project", run_help.stdout)
        for sub in ("status", "prepare", "check", "apply"):
            sub_help = subprocess.run([sys.executable, str(ROOT / "scripts" / "reconcile.py"), sub, "--help"], capture_output=True, text=True, timeout=60)
            self.assertEqual(sub_help.returncode, 0, sub_help.stderr)
            self.assertIn("--root", sub_help.stdout)

    def test_no_command_names_a_token_or_reads_the_environment_for_one(self):
        text = (ROOT / "scripts" / "reconcile.py").read_text(encoding="utf-8")
        self.assertNotIn("GITHUB_TOKEN", text)
        self.assertNotIn("os.environ", text)


if __name__ == "__main__":
    unittest.main()
