#!/usr/bin/env python3
"""A re-runnable proof of the work package 7 acceptance claims. Standard library only.

Run it from the repository root, with no token and no network:

  python3 tests/proof_wp7.py

For each claim it drives the real verifier entry point, verifier/verify_release.py (its run_scan, its
report lines, its command line), against the in-memory model of GitHub in tests/mock/fake_evidence.py,
with a real release prepared, approved, merged and exported through release.py as the content. It also
runs the real release.py and workspace.py doctor commands. It prints one line, PASS or FAIL, then the
line it observed that proves the claim. It does not read test results or file dates. It exits 0 only
when every claim passes.

The one acceptance item it cannot prove is the run on real GitHub. That needs a test organization and the
owner's explicit authorization, and docs/setup.md holds its runbook, marked not yet performed. The last
claim checks that the runbook is there and is honest about its status.
"""
import contextlib
import copy
import hashlib
import http.client
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import traceback
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)
import engineering_fixture as EF  # noqa: E402
import fake_evidence as FE  # noqa: E402
import github_client as G  # noqa: E402
import release as R  # noqa: E402
import release_build as B  # noqa: E402
import release_engineering as RE  # noqa: E402
import release_fixture as F  # noqa: E402
import release_scan as S  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402
import workspace as W  # noqa: E402

_spec = importlib.util.spec_from_file_location("verify_release", ROOT / "verifier" / "verify_release.py")
VR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(VR)

PY = sys.executable
TOOLING = "acme/carrydown-tooling"
POINTER = EF.POINTER
RESULTS = []
CLAIMS = []
TMP = Path(tempfile.mkdtemp(prefix="carrydown-proof7-"))
_FIXTURES = {}


def claim(text):
    def wrap(fn):
        def run():
            try:
                observed = fn()
                RESULTS.append(True)
                print(f"PASS {text}")
                print(f"     observed: {observed}")
            except Exception as e:     # a failed claim is reported, and the rest still run
                RESULTS.append(False)
                print(f"FAIL {text}")
                print(f"     {type(e).__name__}: {str(e)[:400]}")
                if os.environ.get("PROOF_TRACE"):
                    traceback.print_exc()
        CLAIMS.append(run)
        return fn
    return wrap


def check(condition, message="condition failed"):
    if not condition:
        raise AssertionError(message)


def exported(edits=None):
    key = json.dumps(edits, sort_keys=True)
    if key not in _FIXTURES:
        world = FE.World()
        if edits:
            world.update_policy(lambda e: e.update(engineer_edits=edits))
        folder = TMP / f"export{len(_FIXTURES)}"
        folder.mkdir()
        _FIXTURES[key] = EF.Exported(folder, world=world)
    return _FIXTURES[key]


def policy_of(reader):
    tip = reader.branch_head(FE.TOOLING_ID, "main")
    return tip, reader.file_at(FE.TOOLING_ID, tip, "enrollment.yaml")


def scan(world, pub=None):
    """The verifier entry point: capture the policy, check the code pin, scan every open pull request."""
    pub = pub or FE.FakeCheckPublisher()
    tip, data = policy_of(world.reader)
    report = VR.run_scan(data, tip, TOOLING, world.entry["verifier_sha"], world.reader, pub)
    return report, pub


def verdict(world, number, pub=None, kind="engineering"):
    """(conclusion, title) of the check the verifier posted for a pull request."""
    report, pub = scan(world, pub)
    repo = FE.ENGINEERING_ID if kind == "engineering" else FE.STAGING_ID
    head = world.reader.repos[repo]["prs"][number]["head"]["sha"]
    state = pub.state(repo, head, V.ENGINEERING_CHECK if kind == "engineering" else V.STAGING_CHECK)
    return state["conclusion"], state["title"], pub, report


class Light:
    """A small enrolled release (one Markdown file) and its engineering pull request."""

    def __init__(self, expires=None, text=b"# Notes\n"):
        self.world = FE.World()
        self.r = self.world.reader
        self.enr = self.world.enrollment()
        self.r.set_file(FE.ENGINEERING_ID, POINTER, f"format: 1\ntooling_repository: {TOOLING}\nenrollment_id: {self.enr.enrollment_id}\n".encode())
        self.c = FE.make_candidate(self.world, files={"repo/docs/spec/notes.md": text}, destinations=("engineering-repo",), expires=expires)
        self.rid, self.text = self.c.rid, text
        self.staging_pr = None

    def land(self, approve=True, merge=True):
        self.staging_pr = self.c.land(approve=approve, merge=merge)

    def open(self):
        state = RS.RequestState(self.rid, "active", self.c.event["event_id"], None, None)
        receipt = RS.project_receipt(self.c.request, self.c.manifest, state, RS.VerifiedApproval(self.rid, "github-review", True))
        return self.r.open_pr(FE.ENGINEERING_ID, "export", {"docs/spec/notes.md": self.text, f"docs/release/{self.rid}.receipt.json": receipt}, user=FE.OWNER)

    def approve(self):
        self.r.review(FE.STAGING_ID, self.staging_pr, *FE.OWNER)
        self.r.merge(FE.STAGING_ID, self.staging_pr)

    def withdraw(self):
        event = B.withdrawal_event(self.rid, self.world.enrollment(), V.replay_staging(self.r, self.world.enrollment()).replay.tip, "error-found",
                                   created=self.r.tick(), nonce=B.new_nonce())
        self.world.land(B.state_branch_files(event), f"state/{event['event_id']}")


def code_of(case, number):
    report = RE.verify_engineering(case.reader, case.enrollment(), number)
    return report.ok, report.code, report


# ---------------------------------------------------------------------------
# Engineering verification
# ---------------------------------------------------------------------------

@claim("Valid content and its regenerated receipt pass through the verifier entry point, and the receipt is not in its own manifest")
def _():
    ex = exported()
    case = EF.Case(ex)
    n = case.open()
    conclusion, title, pub, report = verdict(case.world, n)
    check(conclusion == "success", title)
    record = V.verify_request(ex.rid, case.reader, case.enrollment())
    check(not [e for e in record.entries if "docs/release/" in e["path"]])
    line = next(x for x in VR.report_lines(report) if "engineering repository" in x)
    return f"{line.strip()} || receipt listed in its manifest: no ({len(record.entries)} entries)"


@claim("Changed bytes, a changed mode, an earlier or dismissed review, a non-approver, local-owner evidence, a changed receipt scope, an altered pointer and removed handling each fail with their own code")
def _():
    ex = exported()
    spec = next(p for p in sorted(ex.files) if p.rsplit("/", 1)[-1].startswith("wi-") and b"## Decisions recorded" in ex.files[p][1])
    got = {}

    def staging_pr(case):
        return next(n for n, p in case.reader.repos[FE.STAGING_ID]["prs"].items() if p["head"]["ref"] == f"request/{ex.rid}")

    def case_with(**kw):
        case = EF.Case(ex)
        return case, case.open(**kw)

    case, n = case_with(edit={spec: ex.files[spec][1] + b"\nextra\n"})
    got["changed bytes"] = code_of(case, n)[1]
    case, n = case_with(edit={spec: ("100755", ex.files[spec][1])})
    got["changed mode"] = code_of(case, n)[1]
    case, n = case_with()
    case.reader.repos[FE.STAGING_ID]["prs"][staging_pr(case)]["reviews"][0]["commit_id"] = "0" * 40
    got["earlier review"] = code_of(case, n)[1]
    case, n = case_with()
    pr = staging_pr(case)
    case.reader.dismiss(FE.STAGING_ID, pr, case.reader.repos[FE.STAGING_ID]["prs"][pr]["reviews"][0]["id"])
    got["dismissed review"] = code_of(case, n)[1]
    case, n = case_with()
    case.reader.repos[FE.STAGING_ID]["prs"][staging_pr(case)]["reviews"][0]["user"]["id"] = 999
    got["non-approver"] = code_of(case, n)[1]
    case = EF.Case(ex)
    record = V.verify_request(ex.rid, case.reader, case.enrollment())
    state = V.replay_staging(case.reader, case.enrollment()).replay.requests[ex.rid]
    local = RS.project_receipt(record.request, record.manifest_bytes, state, RS.VerifiedApproval(ex.rid, "local-owner", False))
    got["local-owner evidence"] = code_of(case, case.open(edit={ex.receipt_path: local}))[1]
    receipt = RS.loads_strict(ex.files[ex.receipt_path][1])
    case = EF.Case(ex)
    got["changed receipt scope"] = code_of(case, case.open(edit={ex.receipt_path: RS.canonical_json(dict(receipt, audience="public"))}))[1]
    case = EF.Case(ex)
    wrong = f"format: 1\ntooling_repository: {TOOLING}\nenrollment_id: {'0' * 64}\n".encode()
    got["altered pointer"] = code_of(case, case.open(only={POINTER: wrong}))[1]
    case = EF.Case(ex)
    plan = ex.files["docs/spec/plan.yaml"][1].decode()
    keep, skip = [], False
    for line in plan.split("\n"):
        if line.startswith("  handling:"):
            skip = True
            continue
        if skip and line.startswith("    "):
            continue
        skip = False
        keep.append(line)
    got["removed handling"] = code_of(case, case.open(edit={"docs/spec/plan.yaml": "\n".join(keep).encode()}))[1]
    want = {"changed bytes": "sha256-mismatch", "changed mode": "sha256-mismatch", "earlier review": "approval-not-on-final-revision",
            "dismissed review": "approval-not-found", "non-approver": "approver-not-authorized", "local-owner evidence": "unauthenticated-release",
            "changed receipt scope": "receipt-projection-mismatch", "altered pointer": "policy-pointer-mismatch",
            "removed handling": "enrolled-project-missing-handling"}
    check(got == want, str(got))
    return "; ".join(f"{k}={v}" for k, v in got.items())


@claim("A receipt-shaped file outside its exact control path cannot bypass artifact validation, and an unlisted artifact fails beside a valid receipt")
def _():
    ex = exported()
    stray = ex.files[ex.receipt_path][1]
    a = EF.Case(ex)
    stray_artifact = code_of(a, a.open(edit={"docs/spec/extra.receipt.json": stray}))[1]
    b = EF.Case(ex)
    wrong_folder = code_of(b, b.open(edit={"docs/release/other.json": stray}))[1]
    c = EF.Case(ex)
    unlisted = code_of(c, c.open(edit={"docs/spec/surprise.md": b"# Surprise\n"}))[1]
    check((stray_artifact, wrong_folder, unlisted) == ("governed-file-without-release", "receipt-projection-mismatch", "governed-file-without-release"))
    return f"docs/spec/extra.receipt.json: {stray_artifact}; docs/release/other.json: {wrong_folder}; docs/spec/surprise.md beside a valid receipt: {unlisted}"


@claim("A pull request touching only src/ reports no governed changes, and deleting only the policy pointer fails instead")
def _():
    ex = exported()
    case = EF.Case(ex)
    ok, code, report = code_of(case, case.open(only={"src/app.py": b"print(1)\n"}))
    check(ok and report.kind == "no-governed-changes")
    other = EF.Case(ex)
    ok2, code2, report2 = code_of(other, other.open(only={POINTER: None}))
    check(not ok2 and code2 == "policy-pointer-mismatch")
    return f"src/ only: {RE.NO_GOVERNED} (kind {report.kind}); pointer deleted: {code2}"


@claim("A renamed repository keeps its identity and a replacement with the old name does not; a board with another node id or a broader audience is refused")
def _():
    w = FE.World()
    r = w.reader
    before = w.enrollment()
    r.repos[FE.ENGINEERING_ID]["full_name"] = "acme/expense-approvals-renamed"
    r.add_repo(9100, "acme/expense-approvals")
    kept = V.load_current_enrollment(FE.ENGINEERING_ID, r, TOOLING).enrollment_id == before.enrollment_id
    try:
        V.load_current_enrollment(9100, r, TOOLING)
        replacement = "enrolled"
    except RS.SchemaError as e:
        replacement = e.code
    board = dict(id="board", **w.entry["allowed_targets"]["board"])
    r.projects["PVT_example"]["owner_id"] = 5555
    codes = []
    try:
        V.verify_targets(r, w.enrollment(), [board], "repo-readers")
    except RS.SchemaError as e:
        codes.append(e.code)
    r.projects["PVT_example"]["owner_id"] = 4400
    r.projects["PVT_example"]["reader_ids"] = r.projects["PVT_example"]["reader_ids"] + [31337]
    try:
        V.verify_targets(r, w.enrollment(), [board], "repo-readers")
    except RS.SchemaError as e:
        codes.append(e.code)
    check(kept and replacement == "policy-pointer-mismatch" and codes == ["target-identity-mismatch", "audience-visibility-mismatch"])
    return f"renamed repository keeps enrollment: {kept}; replacement with the old name: {replacement}; board: {', '.join(codes)}"


# ---------------------------------------------------------------------------
# The polling loop
# ---------------------------------------------------------------------------

@claim("A previously successful head is rechecked and fails after withdrawal, expiry, approver removal, a policy update or a base change that adds an unauthorized governed file")
def _():
    seen = {}

    def fresh(expires=None):
        light = Light(expires=expires)
        light.land()
        n = light.open()
        conclusion, title, pub, _ = verdict(light.world, n)
        check(conclusion == "success", title)
        return light, n, pub

    light, n, pub = fresh()
    light.withdraw()
    seen["withdrawal"] = verdict(light.world, n, pub)[1]
    light, n, pub = fresh(expires=V.utc_text(V.clock() + 3600))
    with mock.patch.object(V, "clock", lambda: V.time.time() + 7200):
        seen["expiry"] = verdict(light.world, n, pub)[1]
    light, n, pub = fresh()
    light.r.users[4242] = {"id": 4242, "login": "someone-else"}
    light.world.update_policy(lambda e: e.update(approvers=[{"id": 4242, "login": "someone-else"}]))
    seen["approver removed"] = verdict(light.world, n, pub)[1]
    light, n, pub = fresh()
    light.world.update_policy(lambda e: e.update(offline_grace_days=3))
    seen["policy update"] = verdict(light.world, n, pub)[1]
    light, n, pub = fresh()
    light.r.set_file(FE.ENGINEERING_ID, "docs/spec/rogue.md", b"# pushed straight to the default branch\n")
    seen["base change"] = verdict(light.world, n, pub)[1]
    check(seen["withdrawal"] == "carrydown: withdrawn" and seen["expiry"] == "carrydown: expired"
          and seen["approver removed"] in ("carrydown: policy-revision-mismatch", "carrydown: approver-not-authorized")
          and seen["policy update"] == "carrydown: policy-revision-mismatch" and seen["base change"] == "carrydown: governed-file-without-release", str(seen))
    return "; ".join(f"{k} -> {v.replace('carrydown: ', '')}" for k, v in seen.items())


@claim("A previously failed head succeeds after genuine approval without an engineering push, and every poll moves the check back to in progress")
def _():
    light = Light()
    light.land(approve=False, merge=False)
    n = light.open()
    first, _t, pub, _r = verdict(light.world, n)
    head = light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"]
    light.approve()
    second, title, pub, _r = verdict(light.world, n, pub)
    check(light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"] == head)
    starts = [c for c in pub.calls if c[0] == "start" and c[1] == FE.ENGINEERING_ID]
    check((first, second) == ("failure", "success") and len(starts) == 2)
    return f"head {head[:12]} unchanged: {first} then {second}; {len(starts)} start calls on one check run"


@claim("A read error replaces the observed success with a failed check, and a scheduler outage is an operational limit, not an expiry")
def _():
    light = Light()
    light.land()
    n = light.open()
    ok, t, pub, _r = verdict(light.world, n)
    outage = dict(pub.state(FE.ENGINEERING_ID, light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"], V.ENGINEERING_CHECK))
    light.r.fail("tree", FE.ENGINEERING_ID)
    after, title, pub, _r = verdict(light.world, n, pub)
    check(ok == "success" and outage["conclusion"] == "success" and after == "failure" and title == "carrydown: evidence-unavailable")
    return f"success, then a tree read error -> {after} ({title}); with no scan at all the old check stays {outage['conclusion']} (documented limit)"


@claim("Two concurrent scans cannot let an older result overwrite a newer failure")
def _():
    light = Light()
    light.land()
    n = light.open()
    pub = FE.FakeCheckPublisher()

    def newer(repo_id, head_sha, name):
        if repo_id == FE.ENGINEERING_ID:
            run = pub.new_run(repo_id, head_sha, name)
            pub.finish(repo_id, head_sha, name, run, "failure", "carrydown: withdrawn", "withdrawn")
    pub.before_finish = newer
    report, pub = scan(light.world, pub)
    head = light.r.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"]
    state = pub.state(FE.ENGINEERING_ID, head, V.ENGINEERING_CHECK)
    check(report.superseded == 1 and state["conclusion"] == "failure")
    return f"older scan's success discarded (superseded={report.superseded}); final check: {state['conclusion']} ({state['title']})"


@claim("Listings follow every page, truncated listings and rate-limit exhaustion fail, and an incomplete scan is not healthy")
def _():
    import test_verifier_setup as TS
    rows = [TS.pr_row(n) for n in range(1, 251)]
    routes = {("GET", "/repositories/4200"): {"id": 4200, "full_name": "acme/expense-approvals", "private": True, "default_branch": "main"},
              ("GET", "/repos/acme/expense-approvals/pulls"): {"rows": rows},
              ("GET", "/repos/acme/expense-approvals/pulls/7/files"): {"rows": [{"filename": f"f{n}", "status": "added", "sha": "a"} for n in range(3000)]},
              ("GET", "/repos/acme/expense-approvals/pulls/8/files"): G.GitHubError("GET /x -> 403", 403, "rate_limit", "wait")}
    reader = TS.RGH.GitHubEvidenceReader(TS.Scripted(routes), host="github.com")
    pages = len(reader.pull_requests(4200, "main", "open"))
    truncated = TS.unavailable(reader.pull_request_files, 4200, 7)
    limited = TS.unavailable(reader.pull_request_files, 4200, 8)
    w = FE.World()
    w.reader.fail("pull_requests", FE.ENGINEERING_ID)
    report, _p = scan(w)
    check(pages == 250 and "truncated" in truncated and limited is not None and not report.complete)
    return f"{pages} pull requests over 3 pages; 3000-file listing: {truncated}; rate limit: {limited}; scan complete={report.complete}"


@claim("Both protected branches require the checks from the expected App installation, not just the check name")
def _():
    w = FE.World()
    good = {c.name: c.status for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}
    w.reader.rulesets_by_repo[FE.ENGINEERING_ID] = [FE.engineering_ruleset(integration=5)]
    w.reader.rulesets_by_repo[FE.STAGING_ID] = [FE.staging_ruleset(integration=5)]
    bad = {c.name: c for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}
    check(good["staging-ruleset"] == good["engineering-ruleset"] == V.VERIFIED)
    check(bad["staging-ruleset"].status == bad["engineering-ruleset"].status == V.MISSING)
    return f"App 77: both verified; another App with the same check names: {bad['engineering-ruleset'].evidence}"


# ---------------------------------------------------------------------------
# Policy, code and credentials
# ---------------------------------------------------------------------------

@claim("Separate policy and code checkouts work when the enrollment pins an earlier code commit, a fake policy is rejected, and editing policy changes only the policy digest")
def _():
    w = FE.World()
    tip, data = policy_of(w.reader)
    code = w.entry["verifier_sha"]
    report = VR.run_scan(data, tip, TOOLING, code, w.reader, FE.FakeCheckPublisher())
    forged = json.loads(data)
    forged["repositories"][0]["approvers"].append({"id": 999, "login": "outsider"})
    forged["repositories"][0]["policy_sha256"] = V.policy_sha256_of(forged["repositories"][0])
    side = w.reader.commit(FE.TOOLING_ID, {"enrollment.yaml": json.dumps(forged).encode()}, [w.reader.repos[FE.TOOLING_ID]["branches"]["main"]], branch="evil")
    try:
        V.capture_enrollments(w.reader, TOOLING, side, json.dumps(forged).encode())
        rejected = "accepted"
    except RS.SchemaError as e:
        rejected = e.code
    try:
        VR.run_scan(data, tip, TOOLING, tip, w.reader, FE.FakeCheckPublisher())
        same = "accepted"
    except VR.VerifierError as e:
        same = e.code
    before = w.enrollment()
    after = w.update_policy(lambda e: e.update(offline_grace_days=3))
    check(report.complete and rejected == "policy-revision-mismatch" and same == "verifier-code-mismatch"
          and before.enrollment_id == after.enrollment_id and before.policy_sha256 != after.policy_sha256)
    return (f"code {code[:8]} (policy {tip[:8]}): scan complete; fake policy: {rejected}; code equal to policy: {same}; "
            f"enrollment id unchanged, policy digest {before.policy_sha256[:8]} -> {after.policy_sha256[:8]}")


@claim("The verifier imports only from its pinned scripts folder, runs on the standard library, and the code checkout must be exactly its commit")
def _():
    check(VR.pinned_import_problem() is None)
    work = TMP / "poison"
    work.mkdir()
    canary = work / "canary.txt"
    for name in ("carrydown_lib", "release_verify", "release_schema", "github_client"):
        (work / f"{name}.py").write_text(f"open({str(canary)!r}, 'w').write('imported')\n", encoding="utf-8")
    run = subprocess.run([PY, "-I", str(ROOT / "verifier" / "verify_release.py"), "ruleset", "--kind", "staging", "--app-id", "5"],
                         cwd=str(work), capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(work)))
    check(run.returncode == 0 and not canary.exists(), run.stderr)
    repo = TMP / "codecheckout"
    repo.mkdir()
    F.init_git(repo)
    (repo / "a.py").write_text("a = 1\n", encoding="utf-8")
    F.sh(["git", "add", "a.py"], repo)
    F.sh(["git", "commit", "-q", "-m", "one"], repo)
    sha = VR.detect_code_sha(repo)
    (repo / "a.py").write_text("a = 2\n", encoding="utf-8")
    try:
        VR.detect_code_sha(repo)
        dirty = "accepted"
    except VR.VerifierError as e:
        dirty = e.code
    check(dirty == "verifier-code-mismatch")
    return f"planted modules never imported (canary absent, exit {run.returncode}); clean checkout {sha[:12]} accepted; edited checkout: {dirty}"


@claim("[G5] A pull request that edits the checker to always exit 0 and adds a governed spec with no release fails on the governed file, and the edited checker never ran")
def _():
    work = TMP / "canary"
    work.mkdir()
    canary = work / "canary.txt"
    checker = ("import sys\nfrom pathlib import Path\nPath(%r).write_text('ran')\nsys.exit(0)\n" % str(canary)).encode()
    light = Light()
    light.r.set_file(FE.ENGINEERING_ID, "tools/carrydown/check_specs.py", b"# the original checker\n")
    light.land()
    n = light.r.open_pr(FE.ENGINEERING_ID, "evil", {"tools/carrydown/check_specs.py": checker, "docs/spec/unreleased.md": b"# A spec with no release\n"}, user=(555, "engineer"))

    def refuse(*a, **k):
        raise AssertionError("the verifier started a process")
    with mock.patch.object(subprocess, "run", refuse), mock.patch.object(subprocess, "Popen", refuse), mock.patch.object(os, "system", refuse):
        conclusion, title, pub, report = verdict(light.world, n)
    check(conclusion == "failure" and title == "carrydown: governed-file-without-release" and not canary.exists())
    return f"check: {conclusion} ({title}) naming docs/spec/unreleased.md; canary file created: {canary.exists()}; processes started: 0"


@claim("The staging check requires an authorized review of the final head, refuses edits to the workflow, enrollment, an old event or a previous request, and refuses a stale predecessor")
def _():
    light = Light()
    light.land()
    w, r = light.world, light.r
    tree = r.repos[FE.STAGING_ID]["commits"][r.repos[FE.STAGING_ID]["branches"]["main"]]["tree"]
    targets = [".github/workflows/open-release-request.yml", "enrollment.yaml", next(p for p in tree if p.startswith("events/")),
               f"requests/{light.rid}/approval-request.json", next(p for p in tree if "/snapshot/" in p)]
    codes = []
    for path in targets:
        fresh = FE.make_candidate(w, supersedes=light.rid)
        files = dict(fresh.files())
        files[path] = b"edited by a candidate\n"
        n = w.land(files, fresh.branch, approve=False, merge=False)
        r.review(FE.STAGING_ID, n, *FE.OWNER)
        result = S.evaluate(r, w.enrollment(), "staging", n)
        check(result.conclusion == "failure", path)
        codes.append(result.code)
        r.close(FE.STAGING_ID, n)
    tip = V.replay_staging(r, w.enrollment()).replay.tip
    a = FE.make_candidate(w, files={"repo/docs/spec/a.md": b"# A\n"}, destinations=("engineering-repo",), supersedes=light.rid, tip=tip)
    b = FE.make_candidate(w, files={"repo/docs/spec/b.md": b"# B\n"}, destinations=("engineering-repo",), supersedes=light.rid, tip=tip)
    n1 = w.land(a.files(), a.branch, approve=False, merge=False)
    n2 = w.land(b.files(), b.branch, approve=False, merge=False)
    r.review(FE.STAGING_ID, n1, *FE.OWNER)
    r.review(FE.STAGING_ID, n2, *FE.OWNER)
    both = (S.evaluate(r, w.enrollment(), "staging", n1).conclusion, S.evaluate(r, w.enrollment(), "staging", n2).conclusion)
    r.merge(FE.STAGING_ID, n1)
    stale = S.evaluate(r, w.enrollment(), "staging", n2)
    check(both == ("success", "success") and stale.code == "state-history-invalid")
    return f"edits to workflow/enrollment/old event/previous request/old snapshot: {', '.join(sorted(set(codes)))}; stale predecessor after the first merge: {stale.code}"


@claim("An unauthorized collaborator, team reader, unexpected App or deploy key, expired attestation or unreadable list stops the first upload with zero pushes; an approved service passes; a changed reader set ends its evidence")
def _():
    results = {}

    def project(name, mutate=None):
        world = FE.World()
        if mutate:
            mutate(world)
        folder = TMP / name
        folder.mkdir()
        np_ = F.NoProject(folder, world=world).start()
        code, out, err = np_.prepare()
        check(code == 0, out + err)
        return np_

    def branches(np_):
        return [x.split("\t")[1] for x in F.sh(["git", "ls-remote", "--heads", str(np_.staging)], np_.base).stdout.splitlines()]

    def attempt(label, mutate_reader, mutate_world=None):
        np_ = project(label.replace(" ", "-"), mutate_world)
        try:
            mutate_reader(np_.reader)
            code, out, err = np_.approve()
            check(code == 1 and "staging-access-not-verified" in err, err)
            check(branches(np_) == ["refs/heads/main"] and np_.dispatches == [])
            results[label] = "0 pushes"
        finally:
            np_.stop()

    attempt("direct collaborator", lambda r: r.collaborators_by_repo[FE.STAGING_ID].append({"id": 999, "login": "outsider", "permission": "read"}))
    attempt("team reader", lambda r: r.teams_by_repo.update({FE.STAGING_ID: [{"id": 1, "slug": "all-engineers", "permission": "pull"}]}))
    attempt("unexpected App", lambda r: r.installations_by_repo.update({FE.STAGING_ID: [{"id": 3, "slug": "some-other-app"}]}))
    attempt("deploy key", lambda r: r.deploy_keys_by_repo.update({FE.STAGING_ID: [{"id": 8, "read_only": True}]}))
    attempt("unreadable list", lambda r: r.fail("collaborators", FE.STAGING_ID))

    def expired(world):
        now = world.reader._clock
        subject = {"repository_id": FE.STAGING_ID, "reader_ids": sorted(world.entry["staging_readers"]["user_ids"]), "service_ids": []}
        world.update_policy(lambda e: e["attestations"].append({"component": "staging-readers", "by_id": world.admins[0][0], "at": V.utc_text(now - 86400 * 3),
                                                                 "expires_at": V.utc_text(now - 86400), "subject": subject, "note": "expired"}))
    attempt("expired attestation", lambda r: r.fail("collaborators", FE.STAGING_ID), expired)

    def services(world):
        world.update_policy(lambda e: e["staging_readers"].update(approved_service_ids=["carrydown-app-installation"]))
        world.reader.installations_by_repo[FE.STAGING_ID] = [{"id": 3, "slug": "carrydown-app-installation"}]
    np_ = project("services", services)
    try:
        code, out, err = np_.approve()
        check(code == 0, out + err)
        results["approved service"] = "upload proceeds"
    finally:
        np_.stop()
    w = FE.World()
    now = w.reader._clock
    subject = {"repository_id": FE.STAGING_ID, "reader_ids": sorted(w.entry["staging_readers"]["user_ids"]), "service_ids": []}
    w.update_policy(lambda e: e["attestations"].append({"component": "staging-readers", "by_id": w.admins[0][0], "at": V.utc_text(now - 3600),
                                                         "expires_at": V.utc_text(now + 86400), "subject": subject, "note": "reviewed"}))
    w.reader.fail("collaborators", FE.STAGING_ID)
    before = {c.name: c.status for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}["staging-readers"]
    w.reader.users[777] = {"id": 777, "login": "new-reader"}
    w.update_policy(lambda e: e["staging_readers"]["user_ids"].append(777))
    after = {c.name: c.status for c in V.verify_prerequisites(w.reader, w.enrollment(), workspace_access=True)}["staging-readers"]
    check(before == V.VERIFIED and after == V.NOT_VERIFIABLE)
    return "; ".join(f"{k}: {v}" for k, v in results.items()) + f"; attested reader set {before}, after the reader set changed {after}"


# ---------------------------------------------------------------------------
# The doctor
# ---------------------------------------------------------------------------

@claim("The offline doctor makes no network call; the live doctor blocks on a non-verifiable component and an attestation satisfies only that component; expired evidence and stale scan health still block")
def _():
    def boom(*a, **k):
        raise AssertionError("the offline doctor used the network")

    def no_project(name, mutate=None):
        world = FE.World()
        if mutate:
            mutate(world)
        folder = TMP / name
        folder.mkdir()
        return F.NoProject(folder, world=world).start()

    def doctor(np_):
        with mock.patch.object(R, "token_available", lambda args: True):
            return F.run(R.main, ["doctor", "--root", str(np_.root)])

    np_ = no_project("offline")
    try:
        with mock.patch.object(socket.socket, "connect", boom), mock.patch.object(socket, "create_connection", boom), \
                mock.patch.object(urllib.request, "urlopen", boom), mock.patch.object(http.client.HTTPConnection, "connect", boom), mock.patch.object(G, "_urlopen", boom):
            code, out, err = F.run(W.main, ["doctor", "--root", str(np_.root)])
        offline_rows = len(re.findall(r"info\s+\S+\s+not verifiable offline", out))
        check(offline_rows == len(W.REMOTE_COMPONENTS), out)
    finally:
        np_.stop()
    np_ = no_project("blocked")
    try:
        np_.reader.fail("collaborators", FE.STAGING_ID)
        np_.reader.fail("rulesets", FE.ENGINEERING_ID)
        code, out, err = doctor(np_)
        check(code == 1 and "staging-readers: " in out and "blocked until verified: staging-readers" in out, out)
        blocked = next(x for x in out.splitlines() if x.startswith("private upload"))
    finally:
        np_.stop()

    def attest(world):
        now = world.reader._clock
        world.update_policy(lambda e: e["attestations"].append({"component": "ruleset-coverage", "by_id": world.admins[0][0], "at": V.utc_text(now - 3600),
                                                                 "expires_at": V.utc_text(now + 86400), "subject": {"repository_id": FE.ENGINEERING_ID, "integration_id": FE.APP_ID},
                                                                 "note": "reviewed"}))
    np_ = no_project("attested", attest)
    try:
        np_.reader.fail("rulesets", FE.ENGINEERING_ID)
        np_.reader.fail("collaborators", FE.STAGING_ID)
        code, out, err = doctor(np_)
        rows = dict((m.group(2), m.group(1)) for m in re.finditer(r"  (verified|not verifiable|missing)\s+([a-z-]+): ", out))
        check(rows["engineering-ruleset"] == "verified" and rows["staging-readers"] == "not verifiable", str(rows))
    finally:
        np_.stop()

    def expire(world):
        world.update_policy(lambda e: [a.update(expires_at=V.utc_text(world.reader._clock - 60)) for a in e["attestations"]])
    np_ = no_project("expired", expire)
    try:
        code, out, err = doctor(np_)
        expired_line = next(x for x in out.splitlines() if x.startswith("export and publication"))
        check("runtime-isolation" in expired_line)
    finally:
        np_.stop()
    np_ = no_project("stale")
    try:
        np_.reader.scan[FE.TOOLING_ID]["completed_at"] = V.utc_text(V.clock() - 5000)
        code, out, err = doctor(np_)
        stale_line = next(x for x in out.splitlines() if x.startswith("export and publication"))
        check("scan-health" in stale_line and code == 1)
    finally:
        np_.stop()
    return (f"offline: {offline_rows} remote components all 'not verifiable offline'; unreadable readers -> '{blocked}'; "
            f"ruleset attested -> engineering-ruleset verified, staging-readers still not verifiable; expired -> '{expired_line}'; stale -> '{stale_line}'")


# ---------------------------------------------------------------------------
# WP9 and the launcher
# ---------------------------------------------------------------------------

@claim("[WP9] With engineer_edits request-only the verifier fails a pull request that edits Decisions recorded of an exported spec without a receipt; with allowed only that section may change")
def _():
    ex = exported()
    spec = next(p for p in sorted(ex.files) if p.rsplit("/", 1)[-1].startswith("wi-") and b"## Decisions recorded" in ex.files[p][1] and b"## Outcome" in ex.files[p][1])
    edited = ex.files[spec][1].decode().rstrip("\n") + "\n\n- 2027-02-01. Departed from the contract in pull request 12.\n"
    case = EF.Case(ex)
    case.merge(case.open())
    refused = code_of(case, case.open(only={spec: edited.encode()}, branch="decisions"))
    check(not refused[0] and refused[1] == "sha256-mismatch")
    allowed = exported({"docs/spec/**": "allowed"})
    case2 = EF.Case(allowed)
    case2.merge(case2.open())
    appended = code_of(case2, case2.open(only={spec: edited.encode()}, branch="decisions"))
    changed = code_of(case2, case2.open(only={spec: edited.replace("## Outcome", "## Outcome\n\nA changed promise.", 1).encode()}, branch="outcome"))
    check(appended[0] and not changed[0] and changed[1] == "sha256-mismatch")
    return (f"request-only: edit of {spec.rsplit('/', 1)[-1]} -> {refused[1]}; allowed: append to Decisions recorded -> ok, edit of Outcome -> {changed[1]}")


@claim("The launcher runs every five minutes off the hour from separate policy and code checkouts, pins its actions, and holds the credentials in the scan step only")
def _():
    text = (ROOT / "verifier" / "carrydown-release-verify.yml").read_text(encoding="utf-8")
    body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    cron = re.search(r'cron: "([^"]+)"', body).group(1)
    uses = re.findall(r"uses:\s+(\S+)", body)
    check(cron == "3-58/5 * * * *" and uses and all(re.search(r"@[0-9a-f]{40}$", u) for u in uses))
    check(body.count("secrets.") == 2 and body.index("secrets.") > body.index("Scan every open pull request"))
    check("path: policy" in body and "path: code" in body and "python3 -I -B code/verifier/verify_release.py scan" in body)
    staging = (ROOT / "templates" / "staging" / "open-release-request.yml").read_text(encoding="utf-8")
    check("contents: read\n  pull-requests: write" in staging and "actions/checkout" not in staging)
    return f"cron {cron}; {len(uses)} action(s) pinned by full SHA; secrets in the scan step only; staging workflow permissions: contents read, pull-requests write"


@claim("The verifier's public check text and the doctor output carry ids and reason codes, never file content or a token")
def _():
    ex = exported()
    spec = next(p for p in sorted(ex.files) if p.rsplit("/", 1)[-1].startswith("wi-"))
    marker = "Secret roadmap sentence for the proof."
    case = EF.Case(ex)
    n = case.open(edit={spec: ex.files[spec][1] + f"\n{marker}\napi_key = abcdef0123456789\n".encode()})
    conclusion, title, pub, report = verdict(case.world, n)
    head = case.reader.repos[FE.ENGINEERING_ID]["prs"][n]["head"]["sha"]
    state = pub.state(FE.ENGINEERING_ID, head, V.ENGINEERING_CHECK)
    shown = state["title"] + state["summary"] + "\n".join(VR.report_lines(report))
    check(conclusion == "failure" and marker not in shown and "abcdef0123456789" not in shown and "ghs_" not in shown)
    check("exception-not-permitted" in state["summary"])
    return f"{conclusion} ({title}); summary names {spec.rsplit('/', 1)[-1]} and codes; planted sentence and planted key absent from {len(shown)} characters of public text"


# ---------------------------------------------------------------------------
# Packaging, reference files and the real-GitHub runbook
# ---------------------------------------------------------------------------

@claim("The skill copies are current and the first skill and the generated engineers' skill carry no network or token code")
def _():
    sync = subprocess.run([PY, str(ROOT / "scripts" / "sync_skill_assets.py"), "--check"], capture_output=True, text=True, cwd=str(ROOT))
    check(sync.returncode == 0, sync.stdout[-300:])
    run = subprocess.run([PY, "-m", "unittest", "tests.test_skill_packaging"], capture_output=True, text=True, cwd=str(ROOT))
    check(run.returncode == 0, run.stderr[-300:])
    tail = [x for x in run.stderr.splitlines() if x.strip()][-1]
    return f"sync --check: {sync.stdout.strip().splitlines()[-1]}; packaging tests: {tail}"


@claim("The reference rulesets, the enrollment example and the digests command agree with the verifier's own rules")
def _():
    out = {}
    for kind, check_fn in (("staging", V.staging_ruleset_problem), ("engineering", V.engineering_ruleset_problem)):
        run = subprocess.run([PY, "-I", str(ROOT / "verifier" / "verify_release.py"), "ruleset", "--kind", kind, "--app-id", "77"], capture_output=True, text=True)
        check(run.returncode == 0, run.stderr)
        out[kind] = check_fn([json.loads(run.stdout)], 77)
        check(out[kind] is None, out[kind])
    schema = (ROOT / "verifier" / "enrollment.schema.md").read_text(encoding="utf-8")
    block = re.search(r"## Example.*?```yaml\n(.*?)```", schema, re.S).group(1)
    path = TMP / "enrollment-example.yaml"
    path.write_text(block, encoding="utf-8")
    digests = subprocess.run([PY, "-I", str(ROOT / "verifier" / "verify_release.py"), "digests", "--policy-file", str(path)], capture_output=True, text=True)
    check(digests.returncode == 0 and "matches the file" in digests.stdout, digests.stdout + digests.stderr)
    return f"staging and engineering rulesets pass with App 77; {digests.stdout.strip().splitlines()[0][:80]}..."


@claim("The real GitHub acceptance run is not performed here: docs/setup.md holds the runbook and a record table marked not yet performed")
def _():
    text = (ROOT / "docs" / "setup.md").read_text(encoding="utf-8")
    section = text[text.index("### Acceptance on real GitHub"):]
    check("Status: **not yet performed.**" in section and "explicitly authorizing" in section)
    rows = [l for l in section.splitlines() if l.startswith("| ") and "Not yet performed" in l]
    check(len(rows) >= 14, str(len(rows)))
    steps = re.findall(r"(?m)^(\d+)\. ", section.split("Record the results here")[0])
    check(len(steps) == 10)
    return f"runbook of {len(steps)} steps and a record table with {len(rows)} rows, every row 'Not yet performed'; no token was used and nothing touched the network"


def main():
    print("carrydown WP7 proof: the real verifier entry point, fake evidence, no token, no network\n")
    for run in CLAIMS:
        run()
    passed = sum(RESULTS)
    print(f"\n{passed} of {len(RESULTS)} claims passed")
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
