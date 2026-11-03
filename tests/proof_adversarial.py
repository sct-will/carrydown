#!/usr/bin/env python3
"""Adversarial attempts on the release gate, the receipt validation, the engineers' check and the
independent verifier, recorded so anyone can run them again. Standard library only, no token, no network.

  python3 tests/proof_adversarial.py

Each attempt tries to get something past a control that the specification says must stop it, and prints
PASS when the control held (the attempt was refused, with the reason it observed) or FAIL when the attempt
got through. The gate attempts run the real commands (release.py, scaffold_spec.py) on a copy of the sample
with a private workspace; the receipt attempts run check_specs.py and the engineers' check_context.py on a
clean clone of the committed sample; the verifier attempts run release_engineering.verify_engineering over
the in-memory model of an organization that the verifier tests use, because the verifier reads GitHub only
through the API. Every subprocess and this process get an empty home folder, so no stored token is found,
and a proxy on a closed loopback port, so nothing can reach the network.
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="carrydown-adversarial-"))
HOME = TMP / "home"
HOME.mkdir()
for name in ("CARRYDOWN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
    os.environ.pop(name, None)
os.environ.update(HOME=str(HOME), USERPROFILE=str(HOME), http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9",
                  HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", no_proxy="127.0.0.1,localhost", NO_PROXY="127.0.0.1,localhost",
                  GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
from sample_tree import copy_sample  # noqa: E402
import release_schema as RS  # noqa: E402

PY = sys.executable
SAMPLE = ROOT / "sample" / "expense-approvals"
CHECK_CONTEXT = "docs/dev/skills/expense-approvals-dev/scripts/check_context.py"
CREATED = "2027-01-20T14:03:00Z"
NONCE = "cd" * 16
RESULTS = []
ATTEMPTS = []


def attempt(text):
    def wrap(fn):
        def run():
            base = Path(tempfile.mkdtemp(dir=str(TMP)))
            try:
                observed = fn(base)
                RESULTS.append(True)
                print(f"PASS {text}")
                print(f"     held: {observed}")
            except Exception as e:     # a control that let the attempt through is reported, and the rest still run
                RESULTS.append(False)
                print(f"FAIL {text}")
                print(f"     {type(e).__name__}: {str(e)[:400]}")
                if os.environ.get("PROOF_TRACE"):
                    traceback.print_exc()
            sys.stdout.flush()
        run.text = text
        ATTEMPTS.append(run)
        return fn
    return wrap


def check(condition, message="condition failed"):
    if not condition:
        raise AssertionError(message)


def last(text):
    lines = [x for x in text.splitlines() if x.strip()]
    return lines[-1].strip() if lines else ""


class Owner:
    """A yes-path owner's project: a git copy of the sample, its private workspace, the real commands."""

    def __init__(self, base):
        self.base = Path(base)
        self.root = self.base / "project"
        copy_sample(self.root)
        self.ws = self.base / "workspace"
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Proof Owner")
        self.git("config", "user.email", "proof.owner@example.com")
        self.run("workspace.py", "init", "--root", self.root, "--slug", "proof", "--workspace", self.ws, "--apply")

    def git(self, *args):
        return subprocess.run(["git"] + [str(a) for a in args], cwd=str(self.root), check=True, capture_output=True, text=True)

    def run(self, script, *args, ok=True):
        out = subprocess.run([PY, str(ROOT / "scripts" / script)] + [str(a) for a in args], cwd=str(self.root), capture_output=True,
                             text=True, timeout=300)
        out.text = out.stdout + out.stderr
        if ok and out.returncode != 0:
            raise AssertionError(f"{script} {args[:1]} exit {out.returncode}: {out.text[-400:]}")
        return out

    def prepare(self, *extra, nonce=NONCE):
        out = self.run("release.py", "prepare", "--root", self.root, "--repository-id", "4200", "--apply", "--created", CREATED,
                       "--nonce", nonce, *extra)
        return re.search(r"request id \(permission\):\s*([0-9a-f]{64})", out.text).group(1)

    def approve(self, rid, ok=True):
        return self.run("release.py", "approve", "--root", self.root, "--request", rid, "--local", "--preview-shown", "--apply", ok=ok)

    def export(self, rid, ok=True):
        return self.run("release.py", "export", "--root", self.root, "--request", rid, "--apply", ok=ok)

    def released(self):
        rid = self.prepare()
        self.approve(rid)
        self.export(rid)
        return rid


def refused(out, code):
    check(out.returncode != 0, f"exit 0: {last(out.text)}")
    check(code in out.text, f"expected {code}: {last(out.text)}")
    return f"exit {out.returncode}: {last(out.text)[:150]}"


# ===========================================================================
# The release gate and the owner's commands
# ===========================================================================

@attempt("gate 1: a fabricated approval.json and state.json saying active do not let an unapproved request export (G1)")
def _(base):
    o = Owner(base)
    rid = o.prepare()
    folder = o.ws / "requests" / rid
    (folder / "approval.json").write_text(json.dumps({"type": "local-owner", "authenticated": True, "request_sha256": rid}), encoding="utf-8")
    (folder / "state.json").write_text(json.dumps({"request_id": rid, "state": "active"}), encoding="utf-8")
    before = sorted(p.name for p in (o.root / "docs" / "release").iterdir())
    out = o.export(rid, ok=False)
    check(sorted(p.name for p in (o.root / "docs" / "release").iterdir()) == before, "a receipt was written")
    return refused(out, "approval-not-found")


@attempt("gate 2: an activation event edited by hand (its event_id no longer recomputes) is refused, not replayed")
def _(base):
    o = Owner(base)
    rid = o.prepare()
    o.approve(rid)
    path = next((o.ws / "events").glob("*.json"))
    batch = json.loads(path.read_text(encoding="utf-8"))
    batch["created"] = "2027-01-21T00:00:00Z"
    path.write_bytes(RS.canonical_json(batch))
    return refused(o.export(rid, ok=False), "sha256-mismatch")


@attempt("gate 3: reproducing a withdrawn request's id with --nonce and --created cannot make it active again (D13)")
def _(base):
    o = Owner(base)
    rid = o.released()
    o.run("release.py", "withdraw", "--root", o.root, "--request", rid, "--reason", "other", "--apply")
    again = o.prepare()
    check(again == rid, "the same inputs gave another id, so this attempt did not test replay")
    return refused(o.approve(rid, ok=False), "withdrawn")


@attempt("gate 4: docs/context as a symbolic link to a folder outside the repository: export writes nothing through it")
def _(base):
    o = Owner(base)
    rid = o.prepare()
    o.approve(rid)
    outside = Path(base) / "outside"
    outside.mkdir()
    shutil.rmtree(str(o.root / "docs" / "context"))
    os.symlink(str(outside), str(o.root / "docs" / "context"))
    out = o.export(rid, ok=False)
    check(not list(outside.iterdir()), "files were written outside the repository")
    return refused(out, "unsafe-artifact-path")


@attempt("gate 5: a dangling symbolic link at an approved file's path: export refuses and creates nothing at the link's target")
def _(base):
    o = Owner(base)
    rid = o.prepare()
    o.approve(rid)
    target = o.root / "docs" / "context" / "wi-03.md"
    target.unlink()
    os.symlink(str(Path(base) / "nowhere.md"), str(target))
    out = o.export(rid, ok=False)
    check(not (Path(base) / "nowhere.md").exists(), "the link's target was created")
    return refused(out, "working-copy-differs")


@attempt("gate 6: after a release, an edited spec cannot be refreshed into the repository through a symlinked alias of the root (G6)")
def _(base):
    o = Owner(base)
    o.released()
    spec = next((o.root / "docs" / "spec").rglob("wi-03*.md"))
    spec.write_text(spec.read_text(encoding="utf-8") + "\nAn edit after approval.\n", encoding="utf-8")
    alias = Path(base) / "alias"
    os.symlink(str(o.root), str(alias))
    return refused(o.run("scaffold_spec.py", "--refresh-headers", "--apply", "--root", alias, ok=False), "working-copy-differs")


@attempt("gate 7: an enrolled project cannot approve locally, and a pointer whose format is 1.0 instead of 1 does not unenroll it")
def _(base):
    o = Owner(base)
    rid = o.prepare()
    pointer = o.root / ".carrydown" / "release-policy.yaml"
    pointer.write_text("format: 1\ntooling_repository: acme/carrydown-tooling\nenrollment_id: " + "7" * 64 + "\n", encoding="utf-8")
    first = refused(o.approve(rid, ok=False), "unauthenticated-release")
    pointer.write_text("format: 1.0\ntooling_repository: acme/carrydown-tooling\nenrollment_id: " + "7" * 64 + "\n", encoding="utf-8")
    refused(o.approve(rid, ok=False), "unauthenticated-release")
    import release_gate as RG
    RG._STATE_CACHE.clear()
    state = RG.project_state(str(o.root))
    check(state.enrolled and not state.pointer_ok, f"a format 1.0 pointer was accepted as well formed: {state.pointer}")
    decision = RG.check("draft", "docs/spec/README.md", "0" * 64, "engineering-repo", str(o.root))
    check(not decision.allowed and decision.code == "policy-pointer-mismatch", decision)
    return f"{first}; format 1.0 pointer: draft write denied {decision.code}"


@attempt("gate 8: a plain dict, a lookalike object and a context made without authorize_content are not verified contexts")
def _(base):
    import release_gate as RG
    import release_verify as V
    o = Owner(base)
    rid = o.prepare()
    fake = {"kind": "content", "request_id": rid, "issued_at": V.clock(), "mechanism": "local-owner", "authenticated": True}

    class Lookalike:
        kind, request_id, issued_at, mechanism = "content", rid, V.clock(), "local-owner"
    codes = []
    for ctx in (fake, Lookalike()):
        d = RG.check("release", "docs/context/wi-03.md", "0" * 64, "engineering-repo", str(o.root), request_id=rid, verified_context=ctx)
        check(not d.allowed, d)
        codes.append(d.code)
    try:
        V.VerifiedContext(kind="content")
        raise AssertionError("a context was made without authorize_content")
    except TypeError:
        codes.append("TypeError")
    return f"dict: {codes[0]}; lookalike: {codes[1]}; direct construction: {codes[2]}"


@attempt("gate 9: a genuine context older than 60 seconds, or issued in the future, does not authorize a write")
def _(base):
    import release as R
    import release_gate as RG
    import release_verify as V
    o = Owner(base)
    rid = o.prepare()
    o.approve(rid)
    project = R.Project(str(o.root))
    args = argparse.Namespace(token_file=None, request=rid)
    with redirect_stdout(io.StringIO()):
        ev = R.gather(project, args, rid, content=True, check_existing=None)
    rel = "docs/context/wi-03.md"
    digest = RS.sha256_bytes(ev.files["repo/" + rel])
    fresh = RG.check("release", rel, digest, "engineering-repo", str(o.root), request_id=rid, verified_context=ev.ctx)
    check(fresh.allowed, f"the genuine fresh context was refused: {fresh}")
    digests = {p: RS.sha256_bytes(b) for p, b in ev.receipts.items()}
    codes = []
    for shift in (-61, 30):
        ctx = V.authorize_content(ev.record, ev.history.replay, ev.policy, None, now=V.clock() + shift, receipts=digests)
        d = RG.check("release", rel, digest, "engineering-repo", str(o.root), request_id=rid, verified_context=ctx)
        check(not d.allowed, f"a context {shift:+d} s old was accepted")
        codes.append(d.code)
    wrong = RG.check("release", rel, "0" * 64, "engineering-repo", str(o.root), request_id=rid, verified_context=ev.ctx)
    check(not wrong.allowed, "other bytes were accepted under the fresh context")
    return f"fresh context: allowed; 61 s old: {codes[0]}; 30 s in the future: {codes[1]}; other bytes: {wrong.code}"


# ===========================================================================
# Receipts, read by the released checker and by the engineers' check
# ===========================================================================

def clean_clone(base):
    clone = copy_sample(Path(base) / "clone", working=False)
    for rel in ("people.yaml", "ground-truth", "docs/ground-truth"):
        p = clone / rel
        if p.is_dir():
            shutil.rmtree(str(p))
        elif p.exists():
            p.unlink()
    return clone


def receipt_path(clone):
    return next((clone / "docs" / "release").glob("*.receipt.json"))


def released_check(clone):
    out = subprocess.run([PY, str(ROOT / "scripts" / "check_specs.py"), "--root", str(clone), "--view", "released"], capture_output=True, text=True,
                         timeout=300)
    out.text = out.stdout + out.stderr
    return out


@attempt("receipt 1: format fields written 1.0 instead of the integer 1 are refused in the receipt, the request, its template and an event (H1)")
def _(base):
    raw = receipt_path(SAMPLE).read_bytes()
    receipt = RS.loads_strict(raw)
    request = json.loads(next((ROOT / "tests" / "fixtures" / "sample-workspace" / "requests").glob("*/approval-request.json")).read_text(encoding="utf-8"))
    event = json.loads(next((ROOT / "tests" / "fixtures" / "sample-workspace" / "events").glob("*.json")).read_text(encoding="utf-8"))
    tried = []

    def refuses(label, fn):
        try:
            fn()
        except RS.SchemaError as e:
            tried.append(f"{label}: {e.code}")
            return
        raise AssertionError(f"{label} accepted")
    refuses("receipt_format 1.0", lambda: RS.validate_receipt(RS.canonical_json(dict(receipt, receipt_format=1.0))))
    bare = {k: v for k, v in request.items() if k != "request_sha256"}
    bare_event = {k: v for k, v in event.items() if k != "event_id"}
    refuses("request_format 1.0", lambda: RS.validate_request(dict(bare, request_format=1.0), check_digest=False))
    refuses("template receipt_format 1.0", lambda: RS.validate_request(dict(bare, receipt_template=dict(bare["receipt_template"], receipt_format=1.0)),
                                                                        check_digest=False))
    refuses("event_format 1.0", lambda: RS.validate_event(dict(bare_event, event_format=1.0), check_digest=False))
    check(RS.validate_request(dict(bare), check_digest=False) and RS.validate_event(dict(bare_event), check_digest=False), "the unchanged records fail")
    clone = clean_clone(base)
    path = receipt_path(clone)
    path.write_bytes(path.read_bytes().replace(b'"receipt_format":1,', b'"receipt_format":1.0,'))
    out = released_check(clone)
    check(out.returncode != 0, "the released checker accepted a receipt with receipt_format 1.0")
    cc = subprocess.run([PY, str(clone / CHECK_CONTEXT), "WI-03", "--no-refresh"], cwd=str(clone), capture_output=True, text=True, timeout=120)
    check(cc.returncode != 0, f"the engineers' check accepted it: {cc.stdout}")
    return "; ".join(tried) + f"; released checker exit {out.returncode}; engineers' check exit {cc.returncode}"


@attempt("receipt 2: a duplicate key, a byte order mark, CRLF line ends or added whitespace make the receipt invalid for the checker")
def _(base):
    raw = receipt_path(SAMPLE).read_bytes()
    variants = {
        "duplicate key": raw.replace(b'{"approval":', b'{"approval":{"type":"github-review","authenticated":true,"ref":"' + b"0" * 64 + b'"},"approval":', 1),
        "byte order mark": b"\xef\xbb\xbf" + raw,
        "CRLF": raw.replace(b"\n", b"\r\n"),
        "pretty printed": json.dumps(json.loads(raw), indent=1, sort_keys=True).encode() + b"\n",
    }
    seen = []
    for label, data in variants.items():
        clone = clean_clone(Path(base) / label.replace(" ", "-"))
        receipt_path(clone).write_bytes(data)
        out = released_check(clone)
        check(out.returncode != 0, f"{label} passed the released checker")
        seen.append(f"{label}: exit {out.returncode}")
    return "; ".join(seen)


@attempt("receipt 3: a local-owner receipt that claims authenticated true, or whose state was edited, fails")
def _(base):
    raw = receipt_path(SAMPLE).read_bytes()
    receipt = RS.loads_strict(raw)
    out = []
    forged = dict(receipt, approval=dict(receipt["approval"], authenticated=True))
    try:
        RS.validate_receipt(RS.canonical_json(forged))
        raise AssertionError("authenticated true accepted for local-owner")
    except RS.SchemaError as e:
        out.append(f"authenticated true: {e.code}")
    clone = clean_clone(base)
    receipt_path(clone).write_bytes(RS.canonical_json(dict(receipt, expires_at="2000-01-01T00:00:00Z")))
    res = released_check(clone)
    check(res.returncode != 0, "an expiry edited into the past passed")
    out.append(f"expired by edit: checker exit {res.returncode}")
    return "; ".join(out)


@attempt("receipt 4: a refresh record dated in the future grants no offline grace to the engineers' check (D7)")
def _(base):
    seed = copy_sample(Path(base) / "seed", working=False)
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["-c", "user.name=P", "-c", "user.email=p@example.com", "commit", "-q", "-m", "s"]):
        subprocess.run(["git"] + args, cwd=str(seed), check=True, capture_output=True)
    origin = Path(base) / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(origin)], check=True, capture_output=True)
    clone = Path(base) / "clone"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True, capture_output=True)
    ok = subprocess.run([PY, str(clone / CHECK_CONTEXT), "WI-03"], cwd=str(clone), capture_output=True, text=True, timeout=120)
    check(ok.returncode == 0, ok.stdout)
    cache = clone / ".carrydown" / "cache" / "last-refresh"
    record = json.loads(cache.read_text(encoding="utf-8"))
    record["time"] = "2999-01-01T00:00:00Z"
    cache.write_text(json.dumps(record), encoding="utf-8")
    shutil.move(str(origin), str(Path(base) / "gone.git"))
    out = subprocess.run([PY, str(clone / CHECK_CONTEXT), "WI-03"], cwd=str(clone), capture_output=True, text=True, timeout=120)
    check(out.returncode == 11 and "could-not-refresh" in out.stdout, f"exit {out.returncode}: {out.stdout}")
    return f"exit {out.returncode}: {last(out.stdout)}"


# ===========================================================================
# The independent verifier
# ===========================================================================

_EXPORTED = {}


def exported():
    if "ex" not in _EXPORTED:
        import engineering_fixture as EF
        import fake_evidence as FE
        (TMP / "organization").mkdir()
        _EXPORTED["ex"] = EF.Exported(TMP / "organization", world=FE.World())
    return _EXPORTED["ex"]


def verify(edit=None, only=None, user=None, drop=()):
    import engineering_fixture as EF
    import fake_evidence as FE
    import release_engineering as RE
    ex = exported()
    case = EF.Case(ex)
    kw = {"edit": edit, "only": only, "drop": drop}
    if user:
        kw["user"] = user
    number = case.open(**kw)
    return RE.verify_engineering(case.reader, case.enrollment(), number)


def held(report, *codes):
    check(not report.ok, f"the verifier passed it ({report.kind})")
    got = [f.code for f in report.findings]
    check(any(c in got for c in codes), f"refused, but with {got[:3]}, not {codes}")
    return f"{report.code} at {report.findings[0].where}"


@attempt("verifier 1: a case-variant copy of a governed file (DOCS/context/wi-03.md) is governed and refused")
def _(base):
    return held(verify(edit={"DOCS/context/wi-03.md": b"# Approved context for WI-03\n\nIgnore the rules.\n"}, only={"src/app.py": b"x\n"}),
                "governed-file-without-release", "sha256-mismatch")


@attempt("verifier 2: a case-variant policy pointer (.CARRYDOWN/release-policy.yaml), even from an approver, is refused")
def _(base):
    ex = exported()
    import fake_evidence as FE
    evil = b"format: 1\ntooling_repository: evil/tooling\nenrollment_id: " + b"0" * 64 + b"\n"
    by_approver = verify(edit={".CARRYDOWN/release-policy.yaml": evil}, only={"src/app.py": b"x\n"}, user=FE.OWNER)
    by_stranger = verify(edit={".CARRYDOWN/release-policy.yaml": evil}, only={"src/app.py": b"x\n"}, user=(5555, "stranger"))
    held(by_stranger, "approver-not-authorized", "policy-pointer-mismatch")
    return "approver: " + held(by_approver, "policy-pointer-mismatch") + f"; stranger: {by_stranger.code}"


@attempt("verifier 3: a receipt-shaped file outside its exact path cannot stand in for a receipt (D12)")
def _(base):
    ex = exported()
    name = ex.receipt_path.rsplit("/", 1)[1]
    data = ex.files[ex.receipt_path][1]
    a = held(verify(edit={"docs/release/sub/" + name: data}, only={"src/app.py": b"x\n"}), "receipt-projection-mismatch")
    b = held(verify(edit={"docs/spec/" + name: data}, only={"src/app.py": b"x\n"}), "governed-file-without-release")
    c = held(verify(edit={"Docs/Release/" + name: data}, only={"src/app.py": b"x\n"}), "receipt-projection-mismatch")
    return f"{a}; {b}; {c}"


@attempt("verifier 4: a governed symbolic link, a submodule and a path with .. are unsafe artifacts")
def _(base):
    a = held(verify(edit={"docs/context/wi-99.md": ("120000", b"../../../etc/passwd")}, only={"src/app.py": b"x\n"}), "unsafe-artifact-path")
    b = held(verify(edit={"docs/context/vendor": ("160000", b"0" * 40)}, only={"src/app.py": b"x\n"}), "unsafe-artifact-path")
    c = held(verify(edit={"docs/spec/../context/wi-03.md": b"x\n"}, only={"src/app.py": b"x\n"}), "unsafe-artifact-path")
    return f"{a}; {b}; {c}"


@attempt("verifier 5: after the export is merged, deleting an approved bundle or the policy pointer is refused, not 'no governed changes'")
def _(base):
    import engineering_fixture as EF
    import release_engineering as RE
    case = EF.Case(exported())
    merged = case.open()
    check(RE.verify_engineering(case.reader, case.enrollment(), merged).ok, "the export itself did not pass")
    case.merge(merged)
    gone = case.open(only={"docs/context/wi-03.md": None}, branch="delete-bundle")
    a = held(RE.verify_engineering(case.reader, case.enrollment(), gone), "artifact-operation-unsupported")
    unpointed = case.open(only={EF.POINTER: None}, branch="delete-pointer")
    b = held(RE.verify_engineering(case.reader, case.enrollment(), unpointed), "policy-pointer-mismatch")
    return f"{a}; {b}"


@attempt("verifier 6: a receipt with format 1.0 or an extra field fails the exact projection")
def _(base):
    ex = exported()
    data = ex.files[ex.receipt_path][1]
    a = held(verify(edit={ex.receipt_path: data.replace(b'"receipt_format":1,', b'"receipt_format":1.0,')}), "receipt-projection-mismatch")
    extra = RS.loads_strict(data)
    extra["note"] = "approved by the owner"
    b = held(verify(edit={ex.receipt_path: json.dumps(extra, sort_keys=True, separators=(",", ":")).encode() + b"\n"}), "receipt-projection-mismatch")
    return f"{a}; {b}"


# ===========================================================================
# Tokens
# ===========================================================================

@attempt("token 1: a malformed token in CARRYDOWN_GITHUB_TOKEN is refused without being echoed, and a server message holding the token is redacted")
def _(base):
    import github_client as G
    bad = "ghp_" + "A" * 36 + "\nsecond-line"
    env = dict(os.environ, CARRYDOWN_GITHUB_TOKEN=bad)
    out = subprocess.run([PY, str(ROOT / "scripts" / "github_sync.py"), "--root", str(SAMPLE), "--verify"], capture_output=True, text=True, env=env,
                         timeout=120)
    text = out.stdout + out.stderr
    check(out.returncode != 0 and "A" * 36 not in text, "the token was echoed or accepted")
    token = "ghp_" + "B" * 36
    import mockgh
    server, url = mockgh.start()
    try:
        gh = G.GitHub(token, api=url, pause=0)
        try:
            gh._send("GET", url + "/this/route/does/not/exist")
        except G.GitHubError as e:
            message = str(e) + " " + getattr(e, "fix", "")
        else:
            message = ""
        check(token not in message, "the token appeared in an error")
        check(G.redact(f"server said {token}", token) == "server said <redacted>", "redact")
    finally:
        server.shutdown()
    return f"malformed: exit {out.returncode}, {last(text)[:110]}; mock error: {message[:80] or 'no error'}"


def main():
    for fn in ATTEMPTS:
        fn()
    passed = sum(RESULTS)
    print(f"{passed} of {len(RESULTS)} attempts held")
    shutil.rmtree(str(TMP), ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
