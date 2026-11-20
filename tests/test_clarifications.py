"""Engineer clarification requests on the owner and GitHub side (specification 9.2 and 9.3, github_sync.py).

An engineer's request is a comment whose first line is "Rule clarification request". The owner's decision is a later
comment that starts with "Clarification disposition:" and names the request. These tests use the loopback mock of
tests/mock/mockgh.py, a temporary private workspace and a temporary HOME. No token and no network are used.
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
from release_fixture import strip_handling  # noqa: E402
from sample_tree import copy_sample, WORKING_PLAN  # noqa: E402
import test_publication as TP  # noqa: E402

SAMPLE = ROOT / "sample" / "expense-approvals"
TOKEN = "ghp_" + "Z" * 36
MARK = "SECRET-MARKER-9183"          # planted in comment bodies: it must never appear in any output
REQUEST = "Rule clarification request"
CLARIFICATION_KEY = '  clarification:\n    channel: "mention"\n    login: "plan-owner"\n'
OBSERVATION_KEYS = ["issue", "item", "state", "url", "comment_id", "created_at", "decided_url", "decided_by"]


def request_body(item="WI-03", marker=MARK):
    return f"{REQUEST}\n\nWork item: {item}\nBaseline request: 1, specification digest: abc\n{marker} the engineer's reasoning.\n"


def with_clarification(plan_path, block=CLARIFICATION_KEY):
    """The plan text with the project.clarification block added at the end of the project mapping."""
    text = Path(plan_path).read_text(encoding="utf-8")
    text, count = re.subn(r"(?m)^(  dev_skill_path:.*\n)", lambda m: m.group(1) + block, text, count=1)
    assert count == 1, "the plan has no dev_skill_path line to add the block after"
    Path(plan_path).write_bytes((text).encode("utf-8"))


def refresh_generated_files(root):
    """Bring the engineers' skill files of a copy of the sample up to the current templates, as the sample's own
    regeneration does. A copy whose files are already current is unchanged."""
    skill = Path(root) / "docs" / "dev" / "skills" / "expense-approvals-dev"
    source = ROOT / "templates" / "dev-skill" / "scripts" / "check_context.py"
    if (skill / "scripts" / "check_context.py").is_file():
        text = source.read_text(encoding="utf-8")
        for name, value in (("id_prefix", "WI"), ("spec_dir", "docs/spec"), ("skill_path", "docs/dev/skills/expense-approvals-dev"), ("engineer_edits", "allowed")):
            text = text.replace("{{" + name + "}}", value)
        (skill / "scripts" / "check_context.py").write_bytes((text).encode("utf-8"))


class ParserTests(unittest.TestCase):
    def test_the_request_heading_is_recognized_on_the_first_line_only(self):
        for body in (REQUEST, REQUEST + "\nmore", "\n\n" + REQUEST, "## " + REQUEST, "**Rule clarification request**", "> " + REQUEST + ": WI-03",
                     REQUEST.upper(), "  " + REQUEST + "  \r\nbody"):
            with self.subTest(body=body):
                self.assertTrue(GS.is_request(body))
        for body in ("", "Please see the Rule clarification request below", "Rule clarification requests are welcome", "Rule clarification\nrequest",
                     "Clarification disposition: accepted", None):
            with self.subTest(body=body):
                self.assertFalse(GS.is_request(body))

    def test_a_disposition_names_one_of_three_states_on_its_first_line(self):
        self.assertEqual(GS.disposition_state("Clarification disposition: Accepted\nRequest: x"), "accepted")
        self.assertEqual(GS.disposition_state("**Clarification disposition:** declined"), None)      # the colon sits inside the bold marks
        self.assertEqual(GS.disposition_state("Clarification disposition: deferred"), "deferred")
        for body in ("Clarification disposition: pending", "Clarification disposition: maybe", "Thanks\nClarification disposition: accepted", ""):
            with self.subTest(body=body):
                self.assertIsNone(GS.disposition_state(body))

    def comments(self):
        return [{"id": 10, "body": request_body("WI-01")}, {"id": 11, "body": "a human reply"}, {"id": 12, "body": request_body("WI-02")}]

    def test_a_request_with_no_disposition_is_pending(self):
        rows = GS.conversation_requests(self.comments())
        self.assertEqual([(r["comment"]["id"], r["state"], r["decided"]) for r in rows], [(10, "pending", None), (12, "pending", None)])

    def test_a_disposition_that_names_the_comment_id_decides_that_request_only(self):
        for text in ("Clarification disposition: accepted\nRequest: https://github.com/o/r/issues/1#issuecomment-12",
                     "Clarification disposition: accepted\nRequest: 12", "Clarification disposition: accepted\nRequest: comment #12"):
            with self.subTest(text=text):
                rows = GS.conversation_requests(self.comments() + [{"id": 13, "body": text, "html_url": "https://github.com/o/r/issues/1#issuecomment-13"}])
                self.assertEqual([r["state"] for r in rows], ["pending", "accepted"])
                self.assertEqual(rows[1]["decided"]["id"], 13)

    def test_a_disposition_that_names_another_request_does_not_apply(self):
        rows = GS.conversation_requests(self.comments() + [{"id": 13, "body": "Clarification disposition: declined\nRequest: 9999"}])
        self.assertEqual([r["state"] for r in rows], ["pending", "pending"])

    def test_a_disposition_before_the_request_does_not_apply(self):
        early = {"id": 9, "body": "Clarification disposition: accepted\nRequest: 10"}
        self.assertEqual([r["state"] for r in GS.conversation_requests([early] + self.comments())], ["pending", "pending"])

    def test_a_quoted_heading_line_names_a_request_only_when_it_is_the_one_with_that_line(self):
        distinct = [{"id": 10, "body": "Rule clarification request: WI-01 section 4\nx"}, {"id": 12, "body": "Rule clarification request: WI-02 section 1\nx"}]
        quote = {"id": 13, "body": "Clarification disposition: deferred\n> Rule clarification request: WI-02 section 1"}
        self.assertEqual([r["state"] for r in GS.conversation_requests(distinct + [quote])], ["pending", "deferred"])
        # two requests with the same bare heading: the quote does not say which one, so neither is decided
        bare = [{"id": 10, "body": REQUEST}, {"id": 12, "body": REQUEST}]
        self.assertEqual([r["state"] for r in GS.conversation_requests(bare + [{"id": 13, "body": f"Clarification disposition: accepted\n> {REQUEST}"}])],
                         ["pending", "pending"])
        # one request with the bare heading: the quote is enough
        self.assertEqual([r["state"] for r in GS.conversation_requests(bare[:1] + [{"id": 13, "body": f"Clarification disposition: accepted\n> {REQUEST}"}])], ["accepted"])

    def test_the_latest_disposition_wins(self):
        rows = GS.conversation_requests(self.comments()[:1] + [{"id": 13, "body": "Clarification disposition: deferred\nRequest: 10"},
                                                               {"id": 14, "body": "Clarification disposition: accepted\nRequest: 10"}])
        self.assertEqual((rows[0]["state"], rows[0]["decided"]["id"]), ("accepted", 14))

    def test_a_disposition_by_an_account_that_is_not_permitted_decides_nothing(self):
        request = {"id": 10, "body": request_body("WI-01"), "user": {"login": "engineer"}}
        stranger = {"id": 13, "body": "Clarification disposition: accepted\nRequest: 10", "user": {"login": "Stranger"}}
        owner = {"id": 14, "body": "Clarification disposition: declined\nRequest: 10", "user": {"login": "Plan-Owner"}}
        rows = GS.conversation_requests([request, stranger], {"plan-owner"})
        self.assertEqual((rows[0]["state"], rows[0]["decided"], [c["id"] for c in rows[0]["unverified"]]), ("pending", None, [13]))
        rows = GS.conversation_requests([request, stranger, owner], {"plan-owner"})
        self.assertEqual((rows[0]["state"], rows[0]["decided"]["id"], [c["id"] for c in rows[0]["unverified"]]), ("declined", 14, [13]))
        # a later disposition by another account does not undo a permitted one
        rows = GS.conversation_requests([request, owner, dict(stranger, id=15)], {"plan-owner"})
        self.assertEqual((rows[0]["state"], rows[0]["decided"]["id"]), ("declined", 14))
        # with no permitted set the parser counts every disposition, as before
        self.assertEqual(GS.conversation_requests([request, stranger])[0]["state"], "accepted")
        # a comment that names no author is never permitted
        self.assertEqual(GS.conversation_requests([request, {"id": 16, "body": "Clarification disposition: accepted\nRequest: 10"}], {"plan-owner"})[0]["state"], "pending")

    def test_the_clarification_line_follows_the_channel(self):
        plan = {"project": {}}
        self.assertEqual(GS.clarification_line(plan), "")
        plan["project"]["clarification"] = {"channel": "mention", "login": "plan-owner"}
        self.assertEqual(GS.clarification_line(plan), "Clarification requests: mention @plan-owner on this issue.")
        plan["project"]["clarification"] = {"channel": "issue", "issue": 7}
        self.assertEqual(GS.clarification_line(plan), "Clarification requests: comment on issue #7.")
        plan["project"]["clarification"] = {"channel": "mention"}
        self.assertEqual(GS.clarification_line(plan), "Clarification requests: comment on this issue, addressed to the plan owner.")
        plan["project"]["clarification"] = {"channel": "mention", "login": "bad login; drop"}
        self.assertEqual(GS.clarification_line(plan), "Clarification requests: comment on this issue, addressed to the plan owner.")

    def test_the_line_is_added_once_before_the_depends_on_section(self):
        plan = {"project": {"clarification": {"channel": "issue", "issue": 7}}}
        body = "### Work item\n\nx\n\n### AI engineering notes\n\nGround truth: y\n\n### Depends on\n\nnone\n"
        once = GS.add_clarification_line(plan, body)
        self.assertEqual(once, "### Work item\n\nx\n\n### AI engineering notes\n\nGround truth: y\n\nClarification requests: comment on issue #7.\n\n### Depends on\n\nnone\n")
        self.assertEqual(GS.add_clarification_line(plan, once), once)
        self.assertEqual(GS.add_clarification_line({"project": {}}, body), body)


class DeciderTests(unittest.TestCase):
    """Who may decide a request (specification 4: the owner decides)."""

    class FakeGitHub:
        def __init__(self, login=None, fail=False):
            self.login, self.fail = login, fail

        def whoami(self):
            if self.fail:
                raise GS.G.GitHubError("no answer")
            return {"login": self.login}

    class Args:
        offline = False

    def plan(self, clarification=None, approvers=None):
        project = {"handling": {"approvers": approvers or []}}
        if clarification:
            project["clarification"] = clarification
        return {"project": project}

    def test_the_mention_login_and_the_token_account_decide_and_release_approvers_do_not(self):
        working = self.plan({"channel": "mention", "login": "Plan-Owner"}, approvers=["release-approver"])
        found = GS.permitted_deciders(self.Args(), (working,), self.FakeGitHub("Token-Owner"))
        self.assertEqual(found, {"plan-owner", "token-owner"})

    def test_the_issue_channel_leaves_only_the_token_account_and_a_failed_read_adds_nobody(self):
        working = self.plan({"channel": "issue", "issue": 7}, approvers=["release-approver"])
        self.assertEqual(GS.permitted_deciders(self.Args(), (working,), self.FakeGitHub("token-owner")), {"token-owner"})
        self.assertEqual(GS.permitted_deciders(self.Args(), (working,), self.FakeGitHub(fail=True)), set())
        rows = GS.conversation_requests([{"id": 1, "body": "Rule clarification request\nWI-03", "user": {"login": "engineer"}},
                                         {"id": 2, "body": "Clarification disposition: accepted\nRequest: 1", "user": {"login": "release-approver"}}],
                                        GS.permitted_deciders(self.Args(), (working,), self.FakeGitHub(fail=True)))
        self.assertEqual((rows[0]["state"], rows[0]["decided"], len(rows[0]["unverified"])), ("pending", None, 1))


class IssueBodyTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-clarification-body-")
        self.addCleanup(self.temp.cleanup)
        self.root = copy_sample(Path(self.temp.name) / "project")

    def body(self, block):
        plan_path = self.root / "docs" / "spec" / "plan.yaml"
        plan_path.write_bytes((WORKING_PLAN.read_text(encoding="utf-8")).encode("utf-8"))
        if block:
            with_clarification(plan_path, block)
        plan, problems = L.load_plan(plan_path, self.root)
        self.assertEqual(problems, [])
        return plan, GS.build_item_body(plan, self.root, plan["items"][0])

    def managed(self, text):
        return GS.MANAGED_RE.search(text).group(1)

    def test_the_sample_body_is_unchanged_without_the_key(self):
        _plan, text = self.body("")
        self.assertNotIn("Clarification requests", text)

    def test_each_channel_puts_one_line_inside_the_managed_region(self):
        for block, line in ((CLARIFICATION_KEY, "Clarification requests: mention @plan-owner on this issue."),
                            ('  clarification:\n    channel: "issue"\n    issue: 7\n', "Clarification requests: comment on issue #7.")):
            with self.subTest(line=line):
                _plan, text = self.body(block)
                inside = self.managed(text)
                self.assertEqual(inside.count(line), 1)
                self.assertEqual(text.count("Clarification requests:"), 1)
                self.assertLess(inside.index("Ground truth:"), inside.index(line))
                self.assertLess(inside.index(line), inside.index("### Depends on"))

    def test_the_offline_show_body_prints_the_line(self):
        plan_path = self.root / "docs" / "spec" / "plan.yaml"
        plan_path.write_bytes((WORKING_PLAN.read_text(encoding="utf-8")).encode("utf-8"))
        with_clarification(plan_path)
        import release_fixture as F
        code, out, err = F.run(GS.run, ["--root", str(self.root), "--offline", "--show-body", "3"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("Clarification requests: mention @plan-owner on this issue.", out)


class LegacyPublicationTests(unittest.TestCase):
    """A project with no handling policy publishes the line, and its drift check accepts it."""

    def setUp(self):
        import contextlib
        import tempfile
        import time
        from unittest import mock
        import github_client as G
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-clarification-legacy-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        mockgh.S.__init__()
        mockgh.S.repos.add(TP.REPO)
        self.server, self.url = mockgh.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.dict(os.environ, {"CARRYDOWN_GITHUB_TOKEN": TOKEN, "HOME": str(base), "USERPROFILE": str(base)}))
        stack.enter_context(mock.patch.object(time, "sleep", lambda s: None))
        stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None)))
        self.root = copy_sample(base / "project")
        strip_handling(self.root)
        with_clarification(self.root / "docs" / "spec" / "plan.yaml")

    def test_the_line_is_published_inside_the_region_and_verify_passes(self):
        import release_fixture as F
        code, out, err = F.run(GS.run, ["--root", str(self.root), "--skip-check", "--create-epic", "--apply"])
        self.assertEqual(code, 0, out + err)
        bodies = [i["body"] for i in mockgh.S.issues if re.search(r"<!-- carrydown:WI-\d+ -->", i["body"] or "")]
        self.assertEqual(len(bodies), 9)
        for body in bodies:
            inside = GS.MANAGED_RE.search(body).group(1)
            self.assertEqual(inside.count("Clarification requests: mention @plan-owner on this issue."), 1)
            self.assertNotIn("Clarification requests", body.replace(GS.MANAGED_RE.search(body).group(0), ""))
        code, out, err = F.run(GS.run, ["--root", str(self.root), "--skip-check", "--verify", "--skip-comment"])
        self.assertEqual(code, 0, out + err)


class ClarificationCase(TP.PubCase):
    """A released and published sample, so the work item issues, the journal and the private workspace exist."""

    def setUp(self):
        super().setUp()
        self.project()
        refresh_generated_files(self.root)
        with_clarification(self.root / "docs" / "spec" / "plan.yaml")
        self.yp.release()
        code, out, err = self.sync("--apply")
        self.assertEqual(code, 0, out + err)
        self.observation = self.ws / "events" / "clarifications.json"
        self.item = self.issue_by_key("WI-03")
        self.other = self.issue_by_key("WI-04")

    def ask(self, *args):
        return self.sync("--clarifications", *args)

    def request(self, issue=None, **kw):
        return mockgh.S.add_comment((issue or self.item)["number"], request_body(**kw), login="engineer", created_at="2020-01-01T00:00:00Z", repository=TP.REPO)

    def decide(self, request, state="accepted", issue=None):
        return mockgh.S.add_comment((issue or self.item)["number"], f"Clarification disposition: {state}\nRequest: {request['html_url']}\n", repository=TP.REPO)


class ListTests(ClarificationCase):
    def test_an_undecided_request_is_pending(self):
        request = self.request()
        before = len(TP.writes(mockgh.S.log))
        code, out, err = self.ask()
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"WI-03 | #{self.item['number']} | pending | ", out)
        self.assertIn(request["html_url"], out)
        self.assertEqual(len(TP.writes(mockgh.S.log)), before)

    def test_no_comment_text_and_no_token_is_ever_printed(self):
        self.request()
        mockgh.S.add_comment(self.item["number"], "Rule clarification request\n" + MARK, login="engineer")
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        for text in (out, err):
            self.assertNotIn(MARK, text)
            self.assertNotIn("Z" * 36, text)
            self.assertNotIn("engineer's reasoning", text)

    def test_a_disposition_comment_decides_the_request_and_sets_decided_url(self):
        for state in ("accepted", "declined", "deferred"):
            with self.subTest(state=state):
                mockgh.S.comments.clear()
                request = self.request()
                decision = self.decide(request, state)
                code, out, err = self.ask("--apply")
                self.assertEqual(code, 0, out + err)
                self.assertIn(f"WI-03 | #{self.item['number']} | {state} | ", out)
                doc = json.loads(self.observation.read_text(encoding="utf-8"))
                self.assertEqual((doc["requests"][0]["state"], doc["requests"][0]["decided_url"]), (state, decision["html_url"]))

    def test_a_disposition_that_names_a_different_request_does_not_apply(self):
        first, second = self.request(), self.request()
        self.decide(second, "declined")
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        rows = json.loads(self.observation.read_text(encoding="utf-8"))["requests"]
        self.assertEqual([(r["comment_id"], r["state"]) for r in rows], [(first["id"], "pending"), (second["id"], "declined")])
        self.assertIsNone(rows[0]["decided_url"])

    def test_a_disposition_on_another_issue_does_not_apply(self):
        request = self.request()
        mockgh.S.add_comment(self.other["number"], f"Clarification disposition: accepted\nRequest: {request['html_url']}\n", repository=TP.REPO)
        self.ask("--apply")
        self.assertEqual(json.loads(self.observation.read_text(encoding="utf-8"))["requests"][0]["state"], "pending")

    def test_the_observation_has_exactly_the_contract_shape(self):
        request = self.request()
        other = self.request(self.other, item="WI-04")
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        text = self.observation.read_text(encoding="utf-8")
        doc = json.loads(text)
        self.assertEqual(list(doc), ["format", "observed", "repository", "requests"])
        self.assertEqual((doc["format"], doc["repository"]), (1, TP.REPO))
        self.assertRegex(doc["observed"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(len(doc["requests"]), 2)
        for row, issue, comment, item in ((doc["requests"][0], self.item, request, "WI-03"), (doc["requests"][1], self.other, other, "WI-04")):
            self.assertEqual(list(row), OBSERVATION_KEYS)
            self.assertEqual(row, {"issue": issue["number"], "item": item, "state": "pending", "url": comment["html_url"], "comment_id": comment["id"], "created_at": "2020-01-01T00:00:00Z", "decided_url": None, "decided_by": None})
        self.assertTrue(text.endswith("\n"))
        self.assertIn("Recorded the observation in the private workspace", out)

    def test_each_request_records_its_creation_time_and_the_update_status_reads_it(self):
        self.request()
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        row = json.loads(self.observation.read_text(encoding="utf-8"))["requests"][0]
        self.assertEqual(row["created_at"], "2020-01-01T00:00:00Z")
        import contextlib
        import io
        import reconcile as R
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(R.main(["status", "--root", str(self.root), "--json"]), 0)
        requests = json.loads(buffer.getvalue())["requests"]
        self.assertTrue(requests["observed"], requests)
        self.assertRegex(requests["requests"][0]["age"], r"^\d+ days$")

    def test_the_creation_time_is_normalized_to_utc_or_left_out(self):
        self.assertEqual(GS._created_at("2026-11-14T09:30:00Z"), "2026-11-14T09:30:00Z")
        self.assertEqual(GS._created_at("2026-11-14T11:30:00+02:00"), "2026-11-14T09:30:00Z")
        for bad in (None, "", "yesterday", "2026-11-14", 5):
            self.assertIsNone(GS._created_at(bad))

    def test_a_dry_run_records_nothing(self):
        self.request()
        code, out, err = self.ask()
        self.assertEqual(code, 0, out + err)
        self.assertFalse(self.observation.exists())
        self.assertIn("Nothing was recorded", out)

    def test_the_observation_replaces_the_previous_one(self):
        request = self.request()
        self.ask("--apply")
        self.decide(request, "accepted")
        self.ask("--apply")
        rows = json.loads(self.observation.read_text(encoding="utf-8"))["requests"]
        self.assertEqual([r["state"] for r in rows], ["accepted"])
        self.assertEqual(sorted(p.name for p in (self.ws / "events").iterdir() if not re.fullmatch(r"[0-9a-f]{64}\.json", p.name)), ["clarifications.json"])

    def test_the_observation_goes_only_into_the_workspace(self):
        self.request()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}
        self.ask("--apply")
        after = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}
        self.assertEqual(before, after)
        self.assertTrue(self.observation.is_file())

    def test_a_workspace_events_folder_that_leaves_the_workspace_is_refused(self):
        self.request()
        outside = self.base / "outside"
        outside.mkdir()
        import shutil
        shutil.rmtree(self.ws / "events")
        os.symlink(outside, self.ws / "events")
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("The observation was not recorded", out)
        self.assertEqual(list(outside.iterdir()), [])

    def test_without_a_workspace_the_list_prints_and_says_it_was_not_recorded(self):
        self.request()
        (self.root / ".carrydown" / "local.yaml").unlink()
        code, out, err = self.sync("--clarifications", "--apply", "--repo", TP.REPO)
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"WI-03 | #{self.item['number']} | pending", out)
        self.assertIn("The observation was not recorded", out)
        self.assertFalse(self.observation.exists())

    def decide_as(self, request, login, state="accepted"):
        return mockgh.S.add_comment(self.item["number"], f"Clarification disposition: {state}\nRequest: {request['html_url']}\n", login=login, repository=TP.REPO)

    def test_a_disposition_by_the_login_the_plan_names_counts(self):
        request = self.request()
        decision = self.decide_as(request, "plan-owner")
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("unverified disposition", out)
        row = json.loads(self.observation.read_text(encoding="utf-8"))["requests"][0]
        self.assertEqual((row["state"], row["decided_url"], row["decided_by"]), ("accepted", decision["html_url"], "plan-owner"))

    def test_a_disposition_by_the_account_of_the_token_counts(self):
        request = self.request()
        decision = self.decide_as(request, mockgh.LOGIN, "deferred")
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        row = json.loads(self.observation.read_text(encoding="utf-8"))["requests"][0]
        self.assertEqual((row["state"], row["decided_url"], row["decided_by"]), ("deferred", decision["html_url"], mockgh.LOGIN))

    def test_a_disposition_by_another_account_is_reported_and_the_request_stays_pending(self):
        request = self.request()
        decision = self.decide_as(request, "drive-by-reader")
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        line = next(x for x in out.splitlines() if "unverified disposition by another account" in x)
        self.assertIn("(drive-by-reader)", line)
        self.assertIn(decision["html_url"], line)
        self.assertIn(f"WI-03 | #{self.item['number']} | pending | ", out)
        self.assertIn("1 pending", out)
        doc = json.loads(self.observation.read_text(encoding="utf-8"))
        row = doc["requests"][0]
        self.assertEqual((row["state"], row["decided_url"], row["decided_by"]), ("pending", None, None))
        self.assertNotIn(decision["html_url"], json.dumps(doc), "an unverified disposition is never written into the observation as a decision")

    def test_the_owner_decision_applies_after_a_disposition_by_another_account(self):
        request = self.request()
        self.decide_as(request, "drive-by-reader", "accepted")
        decision = self.decide_as(request, "plan-owner", "declined")
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("unverified disposition by another account", out)
        row = json.loads(self.observation.read_text(encoding="utf-8"))["requests"][0]
        self.assertEqual((row["state"], row["decided_url"], row["decided_by"]), ("declined", decision["html_url"], "plan-owner"))

    def test_the_clarification_issue_is_read_when_the_plan_names_one(self):
        shared = mockgh.S.add_issue("Rule questions for the owner", "a plain issue with no marker", repository=TP.REPO)
        self.assertIsNotNone(shared)
        mockgh.S.add_comment(shared["number"], request_body("WI-06"), login="engineer", repository=TP.REPO)
        plan, _ = L.load_plan(self.root / "docs" / "spec" / "plan.yaml", self.root)
        plan["project"]["clarification"] = {"channel": "issue", "issue": shared["number"]}
        self.assertEqual(GS._clarification_issue(plan), shared["number"])
        self.assertEqual(GS._request_item(plan, request_body("WI-06"), ""), "WI-06")
        self.assertEqual(GS._request_item(plan, request_body("WI-99"), ""), "")

    def test_an_offline_run_reads_nothing(self):
        before = len(mockgh.S.log)
        code, out, err = F_run(GS.run, ["--root", str(self.root), "--offline", "--clarifications"])
        self.assertEqual((code, out.strip(), err), (0, "offline: nothing read from GitHub", ""))
        self.assertEqual(len(mockgh.S.log), before)

    def test_no_requests_prints_that_there_are_none(self):
        code, out, err = self.ask("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("No clarification requests", out)
        self.assertEqual(json.loads(self.observation.read_text(encoding="utf-8"))["requests"], [])


def F_run(main, argv):
    import release_fixture as F
    return F.run(main, argv)


class DispositionTests(ClarificationCase):
    def post(self, *args, apply=False, issue=None, state="accepted", comment=None, note=None):
        argv = ["--clarification-disposition", str((issue or self.item)["number"]), state]
        argv += ["--request-comment", str(comment)] if comment is not None else []
        argv += ["--note", note] if note is not None else []
        return self.sync(*argv, *args, *(["--apply"] if apply else []))

    def comments_of(self, issue):
        return list(mockgh.S.comments.get(issue["number"], []))

    def test_the_dry_run_prints_the_exact_comment_and_posts_nothing(self):
        request = self.request()
        before = len(TP.writes(mockgh.S.log))
        code, out, err = self.post(comment=request["id"], note="Fix the interface, then rebuild.")
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"  | Clarification disposition: accepted\n  | Request: {request['html_url']}\n  | Note: Fix the interface, then rebuild.\n", out)
        self.assertIn("Dry run complete", out)
        self.assertEqual(len(TP.writes(mockgh.S.log)), before)
        self.assertEqual(len(self.comments_of(self.item)), 1)
        self.assertNotIn(MARK, out)

    def test_apply_posts_the_comment_and_reads_it_back(self):
        request = self.request()
        code, out, err = self.post(comment=request["id"], apply=True, state="deferred")
        self.assertEqual(code, 0, out + err)
        comments = self.comments_of(self.item)
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[1]["body"], f"Clarification disposition: deferred\nRequest: {request['html_url']}")
        self.assertIn("verified by reading it back", out)
        self.assertIn(comments[1]["html_url"], out)
        # the observation now reads the request as deferred, with the new comment as the decision
        self.sync("--clarifications", "--apply")
        row = json.loads(self.observation.read_text(encoding="utf-8"))["requests"][0]
        self.assertEqual((row["state"], row["decided_url"]), ("deferred", comments[1]["html_url"]))

    def test_a_disposition_by_another_account_is_named_in_the_dry_run_and_does_not_block_the_owner(self):
        request = self.request()
        stranger = mockgh.S.add_comment(self.item["number"], f"Clarification disposition: accepted\nRequest: {request['html_url']}\n", login="drive-by-reader", repository=TP.REPO)
        code, out, err = self.post(comment=request["id"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("reads as pending now", out)
        self.assertIn(f"unverified disposition by another account (drive-by-reader): {stranger['html_url']}. It is ignored.", out)
        self.assertNotIn("already recorded", out)
        code, out, err = self.post(comment=request["id"], apply=True)
        self.assertEqual(code, 0, out + err)
        self.assertIn("verified by reading it back", out)

    def test_the_engineers_comment_is_untouched_and_the_issue_stays_open(self):
        request = self.request()
        snapshot = dict(request)
        mark = len(mockgh.S.log)
        self.post(comment=request["id"], apply=True)
        self.assertEqual(self.comments_of(self.item)[0], snapshot)
        self.assertEqual(self.item["state"], "open")
        self.assertEqual([(m, p) for m, p in mockgh.S.log[mark:] if m != "GET" and p != "/graphql"], [("POST", f"/repos/{TP.REPO}/issues/{self.item['number']}/comments")])

    def test_a_state_other_than_the_three_is_refused(self):
        request = self.request()
        for state in ("pending", "closed", "ACCEPTED-NOW", ""):
            with self.subTest(state=state):
                before = len(TP.writes(mockgh.S.log))
                code, out, err = self.post(comment=request["id"], apply=True, state=state)
                self.assertEqual(code, 2)
                self.assertIn("the state must be one of accepted, declined, deferred", err)
                self.assertEqual(len(TP.writes(mockgh.S.log)), before)

    def test_an_issue_that_is_not_a_work_item_issue_is_refused(self):
        stranger = mockgh.S.add_issue("Someone else's issue", "no marker here", repository=TP.REPO)
        request = mockgh.S.add_comment(stranger["number"], request_body(), login="engineer", repository=TP.REPO)
        before = len(TP.writes(mockgh.S.log))
        code, out, err = self.post(comment=request["id"], apply=True, issue=stranger)
        self.assertEqual(code, 1)
        self.assertIn("neither a work item issue of this project nor its clarification issue", out)
        self.assertEqual(len(TP.writes(mockgh.S.log)), before)

    def test_the_configured_clarification_issue_is_accepted(self):
        shared = mockgh.S.add_issue("Rule questions for the owner", "no marker", repository=TP.REPO)
        request = mockgh.S.add_comment(shared["number"], request_body("WI-06"), login="engineer", repository=TP.REPO)
        plan, _ = L.load_plan(self.root / "docs" / "spec" / "plan.yaml", self.root)
        plan["project"]["clarification"] = {"channel": "issue", "issue": shared["number"]}
        self.assertEqual(GS._clarification_issue(plan), shared["number"])
        self.assertEqual(GS._clarification_issue({"project": {"clarification": {"channel": "mention", "login": "x"}}}), None)
        self.assertEqual(request["id"], GS.conversation_requests(mockgh.S.comments[shared["number"]])[0]["comment"]["id"])

    def test_a_comment_that_is_not_a_request_is_refused(self):
        human = mockgh.S.add_comment(self.item["number"], "A human note.", repository=TP.REPO)
        before = len(TP.writes(mockgh.S.log))
        code, out, err = self.post(comment=human["id"], apply=True)
        self.assertEqual(code, 1)
        self.assertIn("is not a Rule clarification request", out)
        self.assertEqual(len(TP.writes(mockgh.S.log)), before)
        code, out, err = self.post(comment=987654321, apply=True)
        self.assertEqual(code, 1)

    def test_a_request_comment_is_required_and_the_note_is_one_short_line(self):
        request = self.request()
        self.assertEqual(self.post()[0], 2)
        for note in ("two\nlines", "x" * 501):
            with self.subTest(note=note[:8]):
                self.assertEqual(self.post(comment=request["id"], note=note)[0], 2)
        self.assertEqual(self.post(comment=request["id"], note="x" * 500)[0], 0)

    def test_a_decided_request_with_the_same_state_posts_nothing_again(self):
        request = self.request()
        self.post(comment=request["id"], apply=True)
        before = len(TP.writes(mockgh.S.log))
        code, out, err = self.post(comment=request["id"], apply=True)
        self.assertEqual(code, 0, out + err)
        self.assertIn("already recorded as accepted", out)
        self.assertEqual(len(TP.writes(mockgh.S.log)), before)

    def test_a_posted_comment_that_GitHub_lost_is_found_again_and_not_posted_twice(self):
        request = self.request()
        mockgh.S.fail[("POST", r"/repos/[^/]+/[^/]+/issues/\d+/comments")] = ["502-after"]
        code, out, err = self.post(comment=request["id"], apply=True)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(self.comments_of(self.item)), 2)

    def test_the_token_never_appears(self):
        request = self.request()
        code, out, err = self.post(comment=request["id"], apply=True)
        self.assertNotIn("Z" * 36, out + err)
        self.assertNotIn(MARK, out + err)

    def test_offline_cannot_post(self):
        code, out, err = F_run(GS.run, ["--root", str(self.root), "--offline", "--clarification-disposition", "1", "accepted", "--request-comment", "5"])
        self.assertEqual(code, 2)
        self.assertIn("needs GitHub", err)


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *argv):
        import release_fixture as F
        return F.run(GS.run, ["--root", str(SAMPLE)] + list(argv))

    def test_the_clarification_flags_are_their_own_runs(self):
        for argv in (["--clarifications", "--verify"], ["--clarifications", "--reconcile"], ["--clarifications", "--clarification-disposition", "1", "accepted"],
                     ["--clarification-disposition", "1", "accepted", "--inventory"]):
            with self.subTest(argv=argv):
                code, out, err = self.run_cli(*argv)
                self.assertEqual(code, 2)
                self.assertIn("is its own run", err)

    def test_the_request_flags_need_the_disposition(self):
        for flag in (["--note", "x"], ["--request-comment", "5"]):
            with self.subTest(flag=flag):
                self.assertEqual(self.run_cli(*flag)[0], 2)

    def test_the_offline_sample_run_prints_the_offline_sentence(self):
        code, out, err = self.run_cli("--offline", "--clarifications")
        self.assertEqual((code, out.strip()), (0, "offline: nothing read from GitHub"))


if __name__ == "__main__":
    unittest.main()
