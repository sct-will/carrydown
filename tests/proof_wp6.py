#!/usr/bin/env python3
"""A re-runnable proof of the work package 6 acceptance claims. Standard library only.

Run it from the repository root, with no token and no network:

  python3 tests/proof_wp6.py

For each claim it runs the real scripts, in a subprocess (release.py, scaffold_spec.py, generate_dev_skill.py,
plan_repair.py, check_context.py, rebuild_sample_release.py) or in this process against the local mock of
GitHub (github_sync.py, github_project.py) and the in-memory model of the staging repository, and prints one
line, PASS or FAIL, then the line it observed that proves the claim. It does not read test results or file
dates. It exits 0 only when every claim passes.
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
import time
import traceback
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "mock"))
from sample_tree import copy_sample, WORKING_PLAN  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)
import fake_evidence as FE  # noqa: E402
import github_client as G  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release as R  # noqa: E402
import release_build as B  # noqa: E402
import release_fixture as F  # noqa: E402
import release_gate as RG  # noqa: E402
import release_github as RGH  # noqa: E402
import release_payloads as RP  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402
import carrydown_lib as L  # noqa: E402

PY = sys.executable
SPEC = "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
RESULTS = []
TMP = Path(tempfile.mkdtemp(prefix="carrydown-proof-"))


def claim(text):
    def wrap(fn):
        def run():
            base = Path(tempfile.mkdtemp(dir=TMP))
            try:
                observed = fn(base)
                RESULTS.append(True)
                print(f"PASS {text}")
                print(f"     observed: {observed}")
            except Exception as e:     # a failed claim is reported, and the rest still run
                RESULTS.append(False)
                print(f"FAIL {text}")
                print(f"     {type(e).__name__}: {str(e)[:300]}")
                if os.environ.get("PROOF_TRACE"):
                    traceback.print_exc()
        run.claim = text
        CLAIMS.append(run)
        return fn
    return wrap


CLAIMS = []


def check(condition, message="condition failed"):
    if not condition:
        raise AssertionError(message)


def last_line(text, contains=None):
    lines = [x for x in text.splitlines() if x.strip() and (contains is None or contains in x)]
    check(lines, f"no line containing {contains!r} in: {text[-200:]!r}")
    return lines[-1].strip()


class Cli:
    """The yes path through the real command line: a copy of the sample with a private workspace."""

    def __init__(self, base):
        self.base = Path(base)
        self.root = self.base / "project"
        copy_sample(self.root)
        self.env = dict(os.environ, HOME=str(self.base), USERPROFILE=str(self.base), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                        PYTHONDONTWRITEBYTECODE="1")
        self.workspace = self.base / "workspace"
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(self.root), check=True, env=self.env)
        subprocess.run(["git", "config", "user.name", "Proof Owner"], cwd=str(self.root), check=True, env=self.env)
        subprocess.run(["git", "config", "user.email", "proof.owner@example.com"], cwd=str(self.root), check=True, env=self.env)
        self.run("workspace.py", "init", "--root", str(self.root), "--slug", "proof", "--workspace", str(self.workspace), "--apply")
        self.rid = None

    def run(self, script, *args, check_ok=True):
        out = subprocess.run([PY, str(ROOT / "scripts" / script)] + [str(a) for a in args], cwd=str(self.root), capture_output=True, text=True,
                             env=self.env, timeout=300)
        if check_ok and out.returncode != 0:
            raise AssertionError(f"{script} {args[0]} failed: {out.stdout[-300:]}{out.stderr[-300:]}")
        return out

    def release(self, *args, check_ok=True):
        return self.run("release.py", *args, check_ok=check_ok)

    def prepare(self, *extra, nonce=None):
        argv = ["prepare", "--root", self.root, "--repository-id", "4200", "--apply"] + list(extra)
        if nonce:
            argv += ["--nonce", nonce]
        out = self.release(*argv)
        self.rid = next(x.split(":", 1)[1].split()[0] for x in out.stdout.splitlines() if x.startswith("request id (permission):"))
        return self.rid

    def approve(self, rid=None):
        return self.release("approve", "--root", self.root, "--request", rid or self.rid, "--local", "--preview-shown", "--apply")

    def export(self, rid=None, apply=True, check_ok=True):
        return self.release("export", "--root", self.root, "--request", rid or self.rid, *(["--apply"] if apply else []), check_ok=check_ok)

    def edit_spec(self):
        path = self.root / SPEC
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + " Edited after approval.\n", encoding="utf-8")


def tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(folder).parts}


# ---------------------------------------------------------------------------
# G1: an unapproved draft cannot be exported
# ---------------------------------------------------------------------------

@claim("G1 content export without verifiable approval is refused, even with a fabricated approval.json")
def _(base):
    c = Cli(base)
    rid = c.prepare()
    request = json.loads((c.workspace / "requests" / rid / "approval-request.json").read_text(encoding="utf-8"))
    fake = {"type": "local-owner", "authenticated": False, "request_sha256": rid, "content_manifest_sha256": request["release_id"],
            "approved_at": "2027-01-20T14:10:00Z", "git_identity": {"name": "x", "email": "y"}, "event_id": "e" * 64}
    (c.workspace / "requests" / rid / "approval.json").write_text(json.dumps(fake), encoding="utf-8")
    before = tree(c.root)
    out = c.export(check_ok=False)
    check(out.returncode == 1 and tree(c.root) == before, "export did not refuse or wrote files")
    return last_line(out.stderr)


@claim("G1 approve --local without a shown preview and without a terminal is refused; the evidence is local owner, not authenticated")
def _(base):
    c = Cli(base)
    rid = c.prepare()
    out = c.release("approve", "--root", c.root, "--request", rid, "--local", "--apply", check_ok=False)
    check(out.returncode == 1 and "not-approved" in out.stderr)
    first = last_line(out.stderr)
    c.approve()
    approval = json.loads((c.workspace / "requests" / rid / "approval.json").read_text(encoding="utf-8"))
    check((approval["type"], approval["authenticated"]) == ("local-owner", False))
    return f"{first} || approval.json type={approval['type']} authenticated={approval['authenticated']}"


@claim("G1 on the no path, export is refused until the request is merged with an authorized review")
def _(base):
    np_ = F.NoProject(base).start()
    try:
        np_.prepare()
        np_.approve()
        code, out, err = np_.export()
        check(code == 1 and "approval-not-found" in err)
        n = np_.land(merge=False, approve=False)
        np_.reader.review(FE.STAGING_ID, n, *FE.OUTSIDER)
        np_.reader.merge(FE.STAGING_ID, n)
        code, out, err = np_.export()
        check(code == 1 and "approver-not-authorized" in err)
        branches = F.sh(["git", "branch", "--list", "carrydown/*"], np_.root).stdout.strip()
        check(branches == "")
        return last_line(err)
    finally:
        np_.stop()


# ---------------------------------------------------------------------------
# G2: changing approved bytes, destination or audience invalidates the approval
# ---------------------------------------------------------------------------

@claim("G2 after approve --local, one changed byte of a spec makes scaffold_spec.py --refresh-headers --apply refuse")
def _(base):
    c = Cli(base)
    c.prepare()
    c.approve()
    c.export()
    c.edit_spec()
    out = c.run("scaffold_spec.py", "--root", c.root, "--refresh-headers", "--apply", "--allow-no-git", check_ok=False)
    check(out.returncode == 1 and "working-copy-differs" in out.stderr)
    return last_line(out.stderr)


@claim("G2 a working copy that differs from the snapshot stops export and writes nothing")
def _(base):
    c = Cli(base)
    c.prepare()
    c.approve()
    c.edit_spec()
    before = tree(c.root)
    out = c.export(check_ok=False)
    check(out.returncode == 1 and "working-copy-differs" in out.stderr and tree(c.root) == before)
    return last_line(out.stderr)


@claim("G2 changing audience or destinations in the request after approval makes export refuse")
def _(base):
    c = Cli(base)
    rid = c.prepare()
    c.approve()
    path = c.workspace / "requests" / rid / "approval-request.json"
    original = path.read_bytes()
    seen = []
    for field, value in (("audience", "public"), ("destinations", ["engineering-repo"])):
        request = json.loads(original)
        request["receipt_template"][field] = value
        path.write_text(json.dumps(request), encoding="utf-8")
        out = c.export(check_ok=False)
        check(out.returncode == 1 and "approval-scope-mismatch" in out.stderr, field)
        seen.append(last_line(out.stderr))
    return seen[0]


@claim("G2 D10 verification over the fake API: each failure gives its fixed code, a good approval passes")
def _(base):
    w = FE.World()
    r, enr = w.reader, w.enrollment()
    codes = []

    def code_of(call, *a):
        try:
            call(*a)
        except RS.SchemaError as e:
            return e.code
        return "ok"
    good = FE.make_candidate(w)
    good.land()
    check(code_of(V.verify_request, good.rid, r, enr) == "ok")
    cases = {}
    # build every candidate on the same tip first: a bad merge makes the later history unreadable, which is the point
    c, d, e = (FE.make_candidate(w, files={"repo/docs/spec/plan.yaml": x}, supersedes=good.rid) for x in (b"x\n", b"y\n", b"z\n"))
    n = r.open_pr(FE.STAGING_ID, c.branch, c.files())
    r.review(FE.STAGING_ID, n, *FE.OWNER)
    r.push_more(FE.STAGING_ID, n, {})
    r.merge(FE.STAGING_ID, n)
    cases["review on an earlier commit"] = (code_of(V.verify_request, c.rid, r, enr), "approval-not-on-final-revision")
    n = r.open_pr(FE.STAGING_ID, d.branch, d.files())
    rv = r.review(FE.STAGING_ID, n, *FE.OWNER)
    r.dismiss(FE.STAGING_ID, n, rv)
    r.merge(FE.STAGING_ID, n)
    cases["dismissed review"] = (code_of(V.verify_request, d.rid, r, enr), "approval-not-found")
    n = r.open_pr(FE.STAGING_ID, e.branch, e.files())
    r.review(FE.STAGING_ID, n, *FE.OUTSIDER)
    r.merge(FE.STAGING_ID, n)
    cases["unauthorized account id"] = (code_of(V.verify_request, e.rid, r, enr), "approver-not-authorized")
    merge = r.repos[FE.STAGING_ID]["prs"][1]["merge_commit_sha"]        # the merge commit of the good request
    path = f"requests/{good.rid}/approval-request.json"
    r.repos[FE.STAGING_ID]["commits"][merge]["tree"][path] = ("100644", good.files()[path] + b" ")
    cases["request bytes differ in the merge"] = (code_of(V.verify_request, good.rid, r, enr), "sha256-mismatch")
    for label, (got, want) in cases.items():
        check(got == want, f"{label}: {got} != {want}")
        codes.append(f"{label}={got}")
    return "; ".join(codes)


@claim("G2 two concurrent replacements: after the first merges, the second cannot pass the staging check until rebuilt and reviewed again")
def _(base):
    w = FE.World()
    r, enr = w.reader, w.enrollment()
    a = FE.make_candidate(w)
    a.land()
    b = FE.make_candidate(w, files={"repo/docs/spec/plan.yaml": b"b\n"}, supersedes=a.rid)
    c = FE.make_candidate(w, files={"repo/docs/spec/plan.yaml": b"c\n"}, supersedes=a.rid)
    nb, nc = (r.open_pr(FE.STAGING_ID, x.branch, x.files()) for x in (b, c))
    for n in (nb, nc):
        r.review(FE.STAGING_ID, n, *FE.OWNER)
    check(V.verify_candidate(r, enr, nb).ok and V.verify_candidate(r, enr, nc).ok)
    r.merge(FE.STAGING_ID, nb)
    report = V.verify_candidate(r, enr, nc)
    check(not report.ok and report.code == "state-history-invalid")
    return f"second branch after the first merged: ok={report.ok} code={report.code}"


@claim("G2 a forged by field and an edited state.json grant no authority; a terminal request never becomes active")
def _(base):
    w = FE.World()
    r, enr = w.reader, w.enrollment()
    a = FE.make_candidate(w)
    a.land()
    n = r.open_pr(FE.STAGING_ID, "state/" + "9" * 64, {"events/" + "9" * 64 + ".json": b'{"by": "sct-will", "to": "active"}', "state.json": b'{"state": "active"}'})
    r.review(FE.STAGING_ID, n, *FE.OWNER)
    report = V.verify_candidate(r, enr, n)
    check(not report.ok)
    wd = B.withdrawal_event(a.rid, enr, FE.tip_of(w), "other", created=r.tick(), nonce=B.new_nonce())
    w.land(B.state_branch_files(wd), f"state/{wd['event_id']}")
    back = B.build_event([B.transition(a.rid, "prepared", "active", wd["event_id"], "release-approved")], enr, created=r.tick(), nonce=B.new_nonce())
    w.land(B.state_branch_files(back), f"state/{back['event_id']}")
    try:
        V.replay_staging(r, enr)
    except RS.SchemaError as e:
        check(e.code == "state-history-invalid")
        return f"forged branch ok={report.ok} code={report.code}; terminal to active: {e.code}"
    raise AssertionError("a terminal request became active again")


# ---------------------------------------------------------------------------
# G4 and G6: state, withdrawal, regeneration
# ---------------------------------------------------------------------------

@claim("G4 first approval activates without a state file, replacement supersedes in one batch, withdrawal exports only the receipt, a spec is denied")
def _(base):
    c = Cli(base)
    first = c.prepare()
    c.approve()
    c.export()
    check(not (c.workspace / "requests" / first / "state.json").exists() or json.loads((c.workspace / "requests" / first / "state.json").read_text())["state"] == "active")
    events_first = len(list((c.workspace / "events").iterdir()))
    c.edit_spec()
    second = c.prepare()
    c.approve()
    c.export()
    replay = V.local_replay(str(c.workspace)).replay
    check((replay.requests[first].state, replay.requests[second].state) == ("superseded", "active"))
    old = json.loads((c.root / "docs/release" / f"{first}.receipt.json").read_text())
    c.release("withdraw", "--root", c.root, "--request", second, "--reason", "error-found", "--apply")
    out = c.export(second, check_ok=False)
    check(out.returncode == 1 and "withdrawn" in out.stderr)
    before = tree(c.root)
    c.release("export-state", "--root", c.root, "--request", second, "--apply")
    after = tree(c.root)
    changed = sorted(p for p in after if before.get(p) != after[p])
    check(changed == [f"docs/release/{second}.receipt.json"], str(changed))
    receipt = json.loads((c.root / "docs/release" / f"{second}.receipt.json").read_text())
    check(receipt["state"] == "withdrawn" and old["state"] == "superseded" and old["superseded_by"] == second)
    record = V.verify_local_request(V.load_local_evidence(str(c.workspace), second), second)
    replay = V.local_replay(str(c.workspace)).replay
    policy = V.local_policy({k: v for k, v in R.Project(c.root).handling.items() if k in L.RELEASED_HANDLING_KEYS}, "sct-will/carrydown-sample")
    path = f"docs/release/{second}.receipt.json"
    ctx = V.authorize_state_receipt(record, replay, policy, {path: RS.sha256_file(c.root / path)})
    denied = RG.check("state-only", SPEC, RS.sha256_file(c.root / SPEC), "engineering-repo", str(c.root), verified_context=ctx)
    check(not denied.allowed and denied.code == "state-only-content-write")
    return (f"events {events_first}->{len(list((c.workspace / 'events').iterdir()))}; first receipt state={old['state']}, "
            f"withdrawn receipt state={receipt['state']}; state-only export changed {changed}; spec in state-only: {denied.code}")


@claim("G4 identical content for another audience has the same release id and another request id; reapproval after withdrawal uses a fresh nonce")
def _(base):
    c = Cli(base)
    first = c.prepare()
    c.approve()
    c.export()
    c.release("withdraw", "--root", c.root, "--request", first, "--reason", "other", "--apply")
    second = c.prepare("--audience", "public")
    r1 = json.loads((c.workspace / "requests" / first / "approval-request.json").read_text())
    r2 = json.loads((c.workspace / "requests" / second / "approval-request.json").read_text())
    check(r1["release_id"] == r2["release_id"] and first != second)
    c.approve()
    replay = V.local_replay(str(c.workspace)).replay
    check((replay.requests[first].state, replay.requests[second].state) == ("withdrawn", "active"))
    c.release("withdraw", "--root", c.root, "--request", second, "--reason", "other", "--apply")
    third = c.prepare()
    r3 = json.loads((c.workspace / "requests" / third / "approval-request.json").read_text())
    check(third not in (first, second) and r3["request_nonce"] not in (r1["request_nonce"], r2["request_nonce"]))
    return f"release id {r1['release_id'][:12]} twice; request ids {first[:8]} != {second[:8]}; third nonce {r3['request_nonce'][:8]} is new"


@claim("G6 plan_repair, generate_dev_skill and scaffold --refresh-headers refuse with not-approved when enrolled with no active release, and succeed before a release on the yes path")
def _(base):
    c = Cli(base / "yes")
    for script, args in (("scaffold_spec.py", ["--refresh-headers", "--apply", "--allow-no-git"]), ("generate_dev_skill.py", ["--apply", "--force"]), ("plan_repair.py", ["--apply"])):
        out = c.run(script, "--root", c.root, *args, check_ok=False)
        check("not-approved" not in out.stderr and "drafting-is-private" not in out.stderr, f"{script}: {out.stderr[-200:]}")
    e = Cli(base / "enrolled")
    (e.root / ".carrydown" / "release-policy.yaml").write_text("format: 1\ntooling_repository: acme/tooling\nenrollment_id: " + "a" * 64 + "\n", encoding="utf-8")
    shutil.rmtree(e.root / "docs" / "dev")
    seen = []
    for script, args in (("scaffold_spec.py", ["--refresh-headers", "--apply", "--allow-no-git"]), ("generate_dev_skill.py", ["--apply"]), ("plan_repair.py", ["--apply"])):
        out = e.run(script, "--root", e.root, *args, check_ok=False)
        check(out.returncode == 1 and "not-approved" in out.stderr, f"{script}: {out.stdout[-100:]}{out.stderr[-200:]}")
        seen.append(f"{script}: {last_line(out.stderr)}")
    return seen[0]


@claim("G6 the monkeypatched write assertion: every write outside the workspace is preceded by a gate decision")
def _(base):
    mockgh.S.__init__()
    mockgh.S.repos.add("sct-will/carrydown-sample")
    mockgh.S.repo_ids = {"sct-will/carrydown-sample": 4200}
    server, url = mockgh.start()
    events = []
    real_check, real_write, real_send = RG.check, L.write_text, G.GitHub._send
    project = F.YesProject(base)
    project.release()
    (project.root / "docs/spec/README.md").unlink()
    shutil.rmtree(project.root / "docs/dev")

    def spy_check(write_class, path, digest, destination, root, **kw):
        events.append(("gate", write_class, str(path), str(root)))
        return real_check(write_class, path, digest, destination, root, **kw)

    def spy_write(path, text):
        events.append(("file", str(Path(path).resolve())))
        return real_write(path, text)

    def spy_send(client, method, u, data=None, *a, **k):
        query = (data or {}).get("query", "") if isinstance(data, dict) else ""
        if not (method == "GET" or (u.endswith("/graphql") and query.lstrip().startswith("query"))):
            events.append(("github", method, u))
        return real_send(client, method, u, data, *a, **k)
    env = {"CARRYDOWN_GITHUB_TOKEN": "ghp_" + "Z" * 36, "HOME": str(base), "USERPROFILE": str(base)}
    import scaffold_spec as SS
    import generate_dev_skill as GD
    with contextlib.ExitStack() as stack:
        for p in (mock.patch.dict(os.environ, env), mock.patch.object(time, "sleep", lambda s: None),
                  mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"), mock.patch.object(RG, "check", spy_check),
                  mock.patch.object(L, "write_text", spy_write), mock.patch.object(G.GitHub, "_send", spy_send),
                  mock.patch.object(G.GitHub.__init__, "__defaults__", (url, 0.0, None))):
            stack.enter_context(p)
        codes = [F.run(SS.main, ["--root", str(project.root), "--apply", "--allow-no-git"])[0], F.run(GD.main, ["--root", str(project.root), "--apply"])[0],
                 F.run(GS.run, ["--root", str(project.root), "--skip-check", "--apply"])[0]]
    server.shutdown()
    server.server_close()
    check(codes == [0, 0, 0], str(codes))
    writes = [(i, e) for i, e in enumerate(events) if e[0] in ("file", "github")]
    for i, e in writes:
        earlier = [g for g in events[:i] if g[0] == "gate"]
        if e[0] == "file":
            check(Path(e[1]) in [Path(g[3], g[2]).resolve() for g in earlier], f"file write without a gate decision: {e[1]}")
        else:
            check(any(g[1] == "release" for g in earlier), f"GitHub write without a release gate decision: {e[1:]}")
    files = [e for _, e in writes if e[0] == "file"]
    github = [e for _, e in writes if e[0] == "github"]
    gates = [e for e in events if e[0] == "gate" and e[1] == "release"]
    check(len(gates) >= len(github))
    return f"{len(files)} file writes and {len(github)} GitHub writes, each after a gate decision ({len(gates)} release-class decisions)"


@claim("The gate has no command-line bypass and answers legacy(no-handling-policy) for a project with no policy")
def _(base):
    out = subprocess.run([PY, str(ROOT / "scripts" / "release_gate.py"), "--help"], capture_output=True, text=True)
    check(out.returncode == 0 and "--force" not in out.stdout and "--bypass" not in out.stdout)
    bad = subprocess.run([PY, str(ROOT / "scripts" / "release_gate.py"), "--force"], capture_output=True, text=True)
    check(bad.returncode == 2)
    legacy = base / "legacy"
    copy_sample(legacy)
    F.strip_handling(legacy)
    with contextlib.redirect_stderr(io.StringIO()):
        d = RG.check("release", "docs/spec/plan.yaml", "0" * 64, "engineering-repo", str(legacy))
    check((d.outcome, d.code) == ("legacy", "no-handling-policy"))
    return f"--force exits {bad.returncode}; legacy decision: {d.outcome}({d.code})"


# ---------------------------------------------------------------------------
# Receipts and the sample
# ---------------------------------------------------------------------------

@claim("A valid first receipt equals project_receipt and lists no receipt; every public field changed one at a time differs")
def _(base):
    c = Cli(base)
    rid = c.prepare()
    c.approve()
    c.export()
    path = c.root / "docs" / "release" / f"{rid}.receipt.json"
    record = V.verify_local_request(V.load_local_evidence(str(c.workspace), rid), rid)
    replay = V.local_replay(str(c.workspace)).replay
    RS.verify_receipt_bytes(path.read_bytes(), record.request, record.manifest_bytes, replay.requests[rid], record.approval)
    receipt = json.loads(path.read_text())
    check(not any(a["path"].startswith("docs/release/") for a in receipt["artifacts"]))
    mismatched = 0
    for key in RS.RECEIPT_KEYS:
        altered = dict(receipt)
        altered[key] = [] if isinstance(receipt[key], list) else ("0" * 64 if isinstance(receipt[key], str) and len(receipt[key]) == 64 else "x")
        try:
            RS.verify_receipt_bytes(json.dumps(altered, sort_keys=True, separators=(",", ":")).encode() + b"\n", record.request, record.manifest_bytes,
                                    replay.requests[rid], record.approval)
        except RS.SchemaError:
            mismatched += 1
    check(mismatched == len(RS.RECEIPT_KEYS), f"{mismatched} of {len(RS.RECEIPT_KEYS)}")
    return f"receipt fields: state={receipt['state']} approval={receipt['approval']['type']}/{receipt['approval']['authenticated']}; {mismatched} of {len(RS.RECEIPT_KEYS)} one-field changes rejected"


@claim("The sample's own release exists, check_context.py WI-06 exits 0 once the clone has an origin, and the release is rebuilt byte for byte")
def _(base):
    run = subprocess.run([PY, str(ROOT / "tests" / "rebuild_sample_release.py"), "--check"], capture_output=True, text=True, timeout=300)
    check(run.returncode == 0, run.stdout + run.stderr)
    project = base / "clone"
    copy_sample(project)
    F.init_git(project)
    F.sh(["git", "add", "-A"], project)
    F.sh(["git", "commit", "-q", "-m", "sample"], project)
    origin = base / "origin.git"
    F.sh(["git", "clone", "-q", "--bare", str(project), str(origin)], base)
    F.sh(["git", "remote", "add", "origin", str(origin)], project)
    F.sh(["git", "fetch", "-q", "origin"], project)
    F.sh(["git", "remote", "set-head", "origin", "main"], project)
    script = project / "docs/dev/skills/expense-approvals-dev/scripts/check_context.py"
    out = subprocess.run([PY, str(script), "WI-06"], cwd=str(project), capture_output=True, text=True, timeout=120)
    check(out.returncode == 0, out.stdout + out.stderr)
    return f"{run.stdout.strip()} || check_context.py WI-06 exit {out.returncode}: {last_line(out.stdout)}"


@claim("The sample's issue bodies are byte for byte what they were before payloads existed")
def _(base):
    plan, _ = L.load_plan(WORKING_PLAN, F.SAMPLE)
    h = hashlib.sha256()
    for it in plan["items"]:
        h.update((GS.build_item_body(plan, F.SAMPLE, it) + "\n").encode())
    for ms in plan["milestones"]:
        h.update((GS.build_subepic_body(plan, F.SAMPLE, ms) + "\n").encode())
    want = "ed60a4b5f2221d26b341806ba6f96c470255ab75d57ec03f261aa39891cc0a7b"
    check(h.hexdigest() == want, h.hexdigest())
    return f"sha256 of the 14 bodies {h.hexdigest()[:16]}... equals the recorded digest (the earlier 11e4320d... changed only in the Ground truth line of nine issues)"


# ---------------------------------------------------------------------------
# Publication: payloads, the journal and the refusals
# ---------------------------------------------------------------------------

class Mock:
    def __init__(self, base):
        mockgh.S.__init__()
        mockgh.S.repos.add("sct-will/carrydown-sample")
        mockgh.S.repo_ids = {"sct-will/carrydown-sample": 4200}
        self.server, self.url = mockgh.start()
        self.stack = contextlib.ExitStack()
        env = {"CARRYDOWN_GITHUB_TOKEN": "ghp_" + "Z" * 36, "HOME": str(base), "USERPROFILE": str(base)}
        for p in (mock.patch.dict(os.environ, env), mock.patch.object(time, "sleep", lambda s: None),
                  mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"),
                  mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None))):
            self.stack.enter_context(p)
        self.project = F.YesProject(base / "yes")
        self.root, self.ws = self.project.root, self.project.workspace

    def close(self):
        self.stack.close()
        self.server.shutdown()
        self.server.server_close()

    def sync(self, *args):
        return F.run(GS.run, ["--root", str(self.root), "--skip-check"] + list(args))


def mock_writes():
    return [(m, p) for m, p in mockgh.S.log if m != "GET" and p != "/graphql"] + [op for op in mockgh.S.gql if op in mockgh.MUTATIONS]


@claim("github_sync --apply interrupted after two creates resumes with no duplicate; a changed managed region stops with target changed since publication")
def _(base):
    m = Mock(base)
    try:
        m.project.release()
        mockgh.S.fail[("POST", r"/repos/[^/]+/[^/]+/issues")] = [None, None, "401"]
        code, out, err = m.sync("--apply")
        check(code == 1 and len(mockgh.S.issues) == 2, f"{code} {len(mockgh.S.issues)}")
        code, out, err = m.sync("--apply")
        check(code == 0 and len(mockgh.S.issues) == 15, out[-300:] + err)
        titles = [i["title"] for i in mockgh.S.issues]
        check(len(titles) == len(set(titles)))
        issue = next(i for i in mockgh.S.issues if "<!-- carrydown:WI-03 -->" in i["body"])
        issue["body"] = issue["body"].replace("Target completion", "Target completion (edited)", 1)
        before = len(mock_writes())
        code, out, err = m.sync("--apply")
        check(code == 1 and len(mock_writes()) == before)
        return f"after the interruption {2} issues, after the resume {len(mockgh.S.issues)}; then: {last_line(out, 'target changed')}"
    finally:
        m.close()


@claim("github_sync --apply refuses before any write for a withdrawn release, a never-approved one and two active releases")
def _(base):
    m = Mock(base)
    try:
        rid = m.project.release()
        tip = V.local_replay(str(m.ws)).replay.tip
        event = B.build_event([B.transition("f" * 64, "prepared", "active", tip, "release-approved")], V.local_policy({}, "o/r"), created="2027-02-01T00:00:00Z", nonce="1" * 32)
        path = m.ws / "events" / f"{event['event_id']}.json"
        path.write_bytes(RS.canonical_json(event))
        code, out, err = m.sync("--apply")
        check(code == 1 and "mixed-release" in out + err and not mock_writes())
        mixed = last_line(out + err, "mixed-release")
        path.unlink()
        F.run(R.main, ["withdraw", "--root", str(m.root), "--request", rid, "--reason", "error-found", "--apply"])
        code, out, err = m.sync("--apply")
        check(code == 1 and "withdrawn" in out + err and not mock_writes())
        return f"{mixed} || {last_line(out + err, 'withdrawn')} || GitHub writes: {len(mock_writes())}"
    finally:
        m.close()


@claim("The client guard refuses a GitHub write that belongs to no approved target, and a repository with another numeric id")
def _(base):
    m = Mock(base)
    try:
        m.project.release()
        import release_sync as RSY
        gh = G.GitHub("ghp_" + "Z" * 36)
        pub = RSY.open_publication(m.root, mock.Mock(token_file=None), gh)
        RSY.install_guard(gh, m.root, pub)
        try:
            gh.rest("POST", "/repos/sct-will/carrydown-sample/labels", {"name": "surprise", "color": "ffffff", "description": ""})
            raise AssertionError("an unapproved label was created")
        except RSY.PublicationRefused as e:
            check(e.code == "destination-not-allowed")
            first = e.line()
        mockgh.S.repo_ids["sct-will/carrydown-sample"] = 7777
        code, out, err = m.sync("--apply")
        check(code == 1 and "target-identity-mismatch" in out + err and not mock_writes())
        return f"{first} || {last_line(out + err, 'target-identity-mismatch')}"
    finally:
        m.close()


# ---------------------------------------------------------------------------
# The no path: private upload, isolated export
# ---------------------------------------------------------------------------

@claim("No path: zero pushes when staging readers cannot be verified; a signed tag refuses before any upload; a timeout then a retry makes one request")
def _(base):
    np_ = F.NoProject(base).start()
    try:
        np_.prepare()
        np_.reader.collaborators_by_repo[FE.STAGING_ID].append({"id": 999, "login": "outsider", "permission": "read"})
        code, out, err = np_.approve()
        check(code == 1 and "staging-access-not-verified" in err)
        refused = last_line(err)
        np_.reader.collaborators_by_repo[FE.STAGING_ID].pop()

        def branches():
            return [x.split("\t")[1] for x in F.sh(["git", "ls-remote", "--heads", str(np_.staging)], base).stdout.splitlines()]
        check(branches() == ["refs/heads/main"])
        code, out, err = F.run(R.main, ["approve", "--root", str(np_.root), "--request", np_.request_id, "--signed-tag", "--apply"])
        check(code == 1 and "approval-mechanism-unsupported" in err and branches() == ["refs/heads/main"])
        code, out, err = np_.approve()
        check(code == 0 and "candidate uploaded; approval request pending" in out)
        pending = last_line(out, "pending")
        np_.reader.open_pr(FE.STAGING_ID, f"request/{np_.request_id}", np_.candidate_files())
        code, out, err = np_.approve()
        check(code == 0 and len(branches()) == 2 and len(np_.reader.repos[FE.STAGING_ID]["prs"]) == 1)
        return f"{refused} || zero pushes (branches {branches()[:1]}) || {pending} || retry found the pull request, 1 request"
    finally:
        np_.stop()


@claim("No path: export uses an isolated worktree, preserves a dirty tree byte for byte, commits as the owner and prints the push commands; dry runs write nothing")
def _(base):
    np_ = F.NoProject(base).start()
    try:
        np_.prepare()
        np_.approve()
        np_.land()
        (np_.root / "README.md").write_text("uncommitted edit\n", encoding="utf-8")
        before, status = tree(np_.root), F.sh(["git", "status", "--porcelain"], np_.root).stdout
        code, out, err = np_.export(apply=False)
        check(code == 0 and tree(np_.root) == before)
        code, out, err = np_.export()
        check(code == 0 and tree(np_.root) == before and F.sh(["git", "status", "--porcelain"], np_.root).stdout == status, out + err)
        branch = f"carrydown/request-{np_.request_id}"
        files = F.sh(["git", "ls-tree", "-r", "--name-only", branch], np_.root).stdout.split()
        check(f"docs/release/{np_.request_id}.receipt.json" in files and not [f for f in files if "company-governance" in f or "people.yaml" in f])
        who = F.sh(["git", "log", "-1", "--format=%an <%ae>", branch], np_.root).stdout.strip()
        receipt = json.loads(F.sh(["git", "show", f"{branch}:docs/release/{np_.request_id}.receipt.json"], np_.root).stdout)
        check(receipt["approval"] == {"type": "github-review", "authenticated": True, "ref": np_.request_id})
        return f"committed on {branch[:30]}... as {who}; receipt approval={receipt['approval']['type']}/{receipt['approval']['authenticated']}; {last_line(out, 'git -C')[:60]}..."
    finally:
        np_.stop()


def main():
    print("carrydown WP6 proof: the real scripts, no token, no network\n")
    for run in CLAIMS:
        run()
    passed = sum(RESULTS)
    print(f"\n{passed} of {len(RESULTS)} claims passed")
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
