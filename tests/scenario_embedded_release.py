#!/usr/bin/env python3
"""The acceptance scenarios of the confidential ground truth specification (work package 11, Part F).

Run it from the repository root. No token, no network, no real clock:

  python3 tests/scenario_embedded_release.py              run everything, print one line per step
  python3 tests/scenario_embedded_release.py --list       list the named assertions without running them
  python3 tests/scenario_embedded_release.py --only A,C1  run the steps whose id starts with one of these

It drives the real scripts through their command lines or public entry points: workspace.py,
render_ground_truth.py, scaffold_spec.py, plan_repair.py, generate_dev_skill.py, release.py (prepare,
approve, export, export-state, withdraw, diff, preview), github_sync.py, check_specs.py, the generated
check_context.py and verifier/verify_release.py. The GitHub API is the in-memory model of
tests/mock/fake_evidence.py (the organization, the staging repository, the verifier's check runs) and
the loopback server of tests/mock/mockgh.py (issues). The origin and staging repositories are bare git
repositories on disk. Time is fake: every request and event carries an explicit --created, and the
engineers' check receives its own clock. Nothing here reimplements the logic it tests.

The steps follow Part F, WP11, of the specification by number:

  A1 to A3   Scenario A, the genuine "yes" path
  B1 to B4   Scenario B, the genuine "no" path
  C1 to C7   the shared lifecycle and adversarial continuation. A step that applies to both paths runs
             on each ("yes path" and "no" path in the name); a step that needs the staging repository, the
             enrollment or the verifier runs on the "no" path only, and says so.

Every assertion has the number of its step in its name. A line is PASS, FAIL, SKIP (with the reason),
or XFAIL (an expected failure: the scenario found a behavior of the product that the specification
step does not allow, and the reason names it; the Opus reviewer fixes the product, then removes the
marker). The last line is "N of N steps passed", where N counts every assertion that ran and was not
expected to fail. The exit status is 0 only when no assertion failed and no expected failure passed.
"""
import contextlib
import copy
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import carrydown_lib as L  # noqa: E402
import engineering_fixture as EF  # noqa: E402
import fake_evidence as FE  # noqa: E402
import github_client as G  # noqa: E402
import github_project as GP  # noqa: E402
import github_repair as GR  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release as R  # noqa: E402
import release_build as B  # noqa: E402
import release_fixture as F  # noqa: E402
import release_gate as RG  # noqa: E402
import release_github as RGH  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402
import workspace as W  # noqa: E402

_spec = importlib.util.spec_from_file_location("verify_release", ROOT / "verifier" / "verify_release.py")
VR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(VR)

PY = sys.executable
TOOLING = "acme/carrydown-tooling"
POINTER = ".carrydown/release-policy.yaml"
SPEC_FILE = "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
SEEDS = ("Tamsin Hale", "Idris Okoye", "Noor Castellan", "assignment_rationale", "days_off", "preferences")
# Sections of the restricted source that no work item cites. None of their words may reach an engineering repository.
UNCITED_RESTRICTED = ("Records of decisions are kept for 7 years", "Internal audit reads decision records", "Nobody decides their own report",
                      "A delegate never decides a report that the delegator submitted")
STAGING_LOCATOR = "expense-approvals-releases"
CLOCK0 = dt.datetime(2027, 2, 1, 12, 0, 0, tzinfo=dt.timezone.utc)


def day(n):
    return f"2027-01-{20 + n:02d}T14:03:00Z"


def nonce(n):
    return f"{n:032x}"


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

class Skip(Exception):
    """The assertion cannot run here, for a stated reason."""


ORDER = []
RESULTS = []


def step(ident, text, flows=(None,), xfail=None):
    """Register a named assertion. flows runs it once for each path named ("yes", "no")."""
    def deco(fn):
        for flow in flows:
            ORDER.append({"id": ident, "flow": flow, "text": text, "fn": fn, "xfail": xfail})
        return fn
    return deco


def label(entry):
    path = {"yes": " (yes path)", "no": " (no path)", None: ""}[entry["flow"]]
    return f"{entry['id']} {entry['text']}{path}"


def run_all(selected=None):
    started = time.time()
    S.start()
    for entry in ORDER:
        if selected and not any(entry["id"].startswith(p) for p in selected):
            continue
        t0 = time.time()
        name = label(entry)
        observed = None
        try:
            observed = entry["fn"](S.flow(entry["flow"])) if entry["flow"] else entry["fn"]()
            status, detail = "PASS", ""
        except Skip as e:
            status, detail = "SKIP", str(e)
        except Exception as e:      # a failed assertion is reported and the rest still run
            status, detail = "FAIL", f"{type(e).__name__}: {str(e)[:500]}"
            if os.environ.get("SCENARIO_TRACE"):
                traceback.print_exc()
        expected = entry["xfail"].get(entry["flow"]) if isinstance(entry["xfail"], dict) else entry["xfail"]
        if expected:
            if status == "FAIL":
                status, detail = "XFAIL", expected
            elif status == "PASS":
                status, detail = "FAIL", "expected to fail (" + expected + ") but passed: remove the marker"
        RESULTS.append(status)
        line = f"{status} {name}"
        if detail:
            line += f"\n     {detail}"
        elif status == "PASS" and isinstance(observed, str):
            line += f"\n     observed: {observed}"
        print(line, flush=True)
        if os.environ.get("SCENARIO_TIMES"):
            print(f"     ({time.time() - t0:.1f} s)")
    S.cleanup()
    ran = [r for r in RESULTS if r in ("PASS", "FAIL")]
    passed = ran.count("PASS")
    print()
    print(f"{passed} of {len(ran)} steps passed")
    extra = f"expected failures: {RESULTS.count('XFAIL')}; skipped: {RESULTS.count('SKIP')}; elapsed {time.time() - started:.1f} s"
    print(extra)
    return 0 if passed == len(ran) else 1


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def need(condition, message="condition failed"):
    if not condition:
        raise AssertionError(message)


def equal(actual, expected, what=""):
    if actual != expected:
        raise AssertionError(f"{what}: expected {expected!r}, got {actual!r}")


def tree_state(folder):
    """{relative path: sha256} of every regular file under folder except git internals and caches."""
    out = {}
    base = Path(folder)
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base).parts
        if p.is_file() and not p.is_symlink() and ".git" not in rel and "__pycache__" not in rel:
            out[p.relative_to(base).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rid_of(out):
    for line in out.splitlines():
        if line.startswith("request id (permission):"):
            return line.split(":", 1)[1].split()[0]
    raise AssertionError("prepare printed no request id: " + out[-300:])


def last(text, n=1):
    lines = [x for x in text.strip().splitlines() if x.strip()]
    return " | ".join(x.strip() for x in lines[-n:])


class Net:
    """Records every attempt to open a network connection while active, and refuses it. A connection to this computer
    (the loopback mock of GitHub) is allowed and is not an attempt."""

    LOOPBACK = ("127.0.0.1", "::1", "localhost")

    def __init__(self):
        self.attempts = []
        self.stack = None

    def start(self):
        real_connect, real_create = socket.socket.connect, socket.create_connection

        def host_of(address):
            return address[0] if isinstance(address, tuple) else str(address)

        def connect(sock, address, *a, **k):
            if host_of(address) in self.LOOPBACK or not isinstance(address, tuple):
                return real_connect(sock, address, *a, **k)
            self.attempts.append(host_of(address)[:60])
            raise OSError("the scenario forbids network access here")

        def create(address, *a, **k):
            if host_of(address) in self.LOOPBACK:
                return real_create(address, *a, **k)
            self.attempts.append(host_of(address)[:60])
            raise OSError("the scenario forbids network access here")
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(mock.patch.object(socket.socket, "connect", connect))
        self.stack.enter_context(mock.patch.object(socket, "create_connection", create))

    def stop(self):
        if self.stack is not None:
            self.stack.close()
            self.stack = None


def git(root, *args, check=True):
    return F.sh(["git"] + [str(a) for a in args], root, check=check)


_TREES = {}


def read_tree(root, ref):
    """{path: (mode, bytes)} of every file of a commit. One git process lists the tree and one reads every blob."""
    commit = git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.strip()
    if (str(root), commit) not in _TREES:
        listing = git(root, "ls-tree", "-r", "-z", commit).stdout
        entries = []
        for row in filter(None, listing.split("\0")):
            meta, path = row.split("\t", 1)
            mode, _kind, sha = meta.split()
            entries.append((path, mode, sha))
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        run = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"], input=("\n".join(e[2] for e in entries) + "\n").encode("ascii"),
                             capture_output=True, check=True, env=env)
        data, at, out = run.stdout, 0, {}
        for path, mode, sha in entries:
            end = data.index(b"\n", at)
            header = data[at:end].split()
            need(len(header) == 3 and header[0].decode("ascii") == sha, f"git cat-file answered {header!r} for {sha}")
            size = int(header[2])
            out[path] = (mode, data[end + 1:end + 1 + size])
            at = end + 1 + size + 1
        _TREES[(str(root), commit)] = out
    return dict(_TREES[(str(root), commit)])


def ls_heads(bare):
    out = git(bare, "for-each-ref", "--format=%(refname)").stdout.split()
    return sorted(out)


def tracked(root):
    return git(root, "ls-files").stdout.split("\n")


def scan_text(files, needles):
    """The needles found in any of the files ({path: bytes}); each as (path, needle)."""
    hits = []
    for path, data in files.items():
        blob = data[1] if isinstance(data, tuple) else data
        for needle in needles:
            if needle.encode("utf-8") in blob:
                hits.append((path, needle))
    return hits


def run_script(script, *args, cwd=None, home=None, check_ok=False):
    """A script of this repository (or any path) as a subprocess with a clean environment."""
    env = dict(os.environ, HOME=str(home or S.home), USERPROFILE=str(home or S.home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1")
    env.pop("CARRYDOWN_GITHUB_TOKEN", None)
    path = Path(script)
    if not path.is_absolute():
        path = ROOT / "scripts" / script
    out = subprocess.run([PY, str(path)] + [str(a) for a in args], cwd=str(cwd or ROOT), capture_output=True, text=True, env=env, timeout=300)
    if check_ok and out.returncode != 0:
        raise AssertionError(f"{path.name} {args[:2]} exited {out.returncode}: {out.stdout[-300:]}{out.stderr[-300:]}")
    return out


_CC_MODULES = {}


def check_context(script, root, item, now=CLOCK0, refresh=True):
    """The engineers' check, the generated copy in the project, through its public entry point with a fake clock.
    Returns (exit status, printed text)."""
    key = str(script)
    if key not in _CC_MODULES:
        spec = importlib.util.spec_from_file_location(f"check_context_{len(_CC_MODULES)}", str(script))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CC_MODULES[key] = module
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = _CC_MODULES[key].main([item, "--root", str(root)] + ([] if refresh else ["--no-refresh"]), now=now)
    return code, out.getvalue()


def skill_script(root, slug="expense-approvals-dev"):
    return Path(root) / "docs" / "dev" / "skills" / slug / "scripts" / "check_context.py"


def plan_ids(root):
    plan, problems = L.load_plan(Path(root) / "docs/spec/plan.yaml", root)
    return plan, [L.tag(plan, it["id"]) for it in plan["items"]]


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class State:
    """The scenario's shared fixtures. Nothing is created until start(), so importing this module has no side effect."""

    def __init__(self):
        self.tmp = None
        self.home = None
        self.net = Net()
        self.flows = {}
        self.memo = {}
        self.env = None

    def start(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="carrydown-scenario-")).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home), "GIT_TERMINAL_PROMPT": "0",
                                                "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
        self.env.start()
        os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)      # restored when the scenarios end; they never use a token

    def once(self, key, build):
        """Build a fixture once. A build that raised raises the same error for every later step."""
        if key not in self.memo:
            try:
                self.memo[key] = ("ok", build())
            except Exception as e:
                self.memo[key] = ("error", e)
        kind, value = self.memo[key]
        if kind == "error":
            raise AssertionError(f"setup of {key} failed earlier: {type(value).__name__}: {str(value)[:300]}")
        return value

    def flow(self, name):
        return self.flows[name]() if callable(self.flows.get(name)) else self.flows[name]

    def cleanup(self):
        self.net.stop()
        if self.env is not None:
            self.env.stop()
            self.env = None
        if self.tmp is not None:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None


S = State()


# ---------------------------------------------------------------------------
# The "yes" path: a project whose documents everyone who can read the repository may see
# ---------------------------------------------------------------------------

def modernize_citations(plan_file, spec_root):
    """Write the citations of the fixture's work items the way the interview writes them today: structured source_refs in
    the plan, and the Ground truth row of each specification naming the source. (The fixture keeps the older one-line
    text citation on eight of its nine items. A1.x to A3.x use the modern form; A3.6 uses the older one.)"""
    plan_file = Path(plan_file)
    text = plan_file.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^    ground_truth: "Sections ([^"]+)"$', r'    source_refs:\n      - source: architecture\n        sections: "\1"', text)
    plan_file.write_text(text, encoding="utf-8")
    for md in Path(spec_root).rglob("wi-*.md"):
        body = md.read_text(encoding="utf-8")
        new = re.sub(r"(?m)^\| Ground truth \| (Sections [^|]+?) \|$", r"| Ground truth | Architecture document: \1 |", body)
        if new != body:
            md.write_text(new, encoding="utf-8")


def legacy_citations(spec_root):
    """The reverse of modernize_citations for the specification headers: the older one-line text in the Ground truth row."""
    for md in Path(spec_root).rglob("wi-*.md"):
        body = md.read_text(encoding="utf-8")
        new = re.sub(r"(?m)^\| Ground truth \| Architecture document: (Sections [^|;]+?) \|$", r"| Ground truth | \1 |", body)
        if new != body:
            md.write_text(new, encoding="utf-8")


class YesFlow:
    """The confidential fixture with both sources approved for repository readers (or public), a private
    workspace for the staffing records, and a bare repository standing in for the origin."""
    path = "yes"

    def __init__(self, base, public=(), modern=True):
        self.base = Path(base)
        self.root = self.base / "project"
        self.ws = self.base / "workspace"
        self.intake = self.base / "intake"
        self.public = tuple(public)
        self.rids = []
        self.k = 0
        self.rid = None
        self.origin = None
        shutil.copytree(F.FIXTURE, self.root)
        shutil.rmtree(self.root / "docs" / "ground-truth")
        self.intake.mkdir()
        (self.root / "people.yaml").rename(self.intake / "people.yaml")
        plan = self.root / "docs" / "spec" / "plan.yaml"
        text = plan.read_text(encoding="utf-8")
        text = text.replace("repo_audience_approved: false", "repo_audience_approved: true").replace('approvers: ["example-approver"]', "approvers: []")
        text = text.replace("classification: restricted", "classification: repo-readers")
        for source in self.public:
            text = re.sub(r"(id: %s\n(?:.*\n)*?    classification: )repo-readers" % re.escape(source), r"\1public", text, count=1)
        plan.write_text(text, encoding="utf-8")
        if modern:
            modernize_citations(plan, self.root / "docs" / "spec")
        F.init_git(self.root)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "Sources and drafts")

    def common(self):
        return ["--root", str(self.root)]

    def init_workspace(self):
        return F.run(W.main, ["init", "--root", str(self.root), "--slug", "expense-approvals", "--workspace", str(self.ws), "--answer", "yes", "--apply"])

    def put_staffing(self):
        shutil.copy(self.intake / "people.yaml", self.ws / "people.yaml")

    def render_all(self):
        out = []
        for source, version in (("architecture", "0.3"), ("company-governance", "2027.1")):
            r = run_script("render_ground_truth.py", self.root / "ground-truth" / f"{source}.md", "--root", self.root, "--source-id", source,
                           "--version", version, "--date", "2027-01-05", cwd=self.root)
            out.append((source, r.returncode, r.stdout + r.stderr))
        return out

    def prepare(self, *extra, apply=True, fresh=True):
        argv = ["prepare"] + self.common() + ["--repository-id", "4200"]
        if fresh:
            self.k += 1
            argv += ["--nonce", nonce(self.k), "--created", day(self.k)]
        argv += list(extra)
        if apply:
            argv.append("--apply")
        code, out, err = F.run(R.main, argv)
        if code == 0 and apply:
            self.rid = rid_of(out)
            if self.rid not in self.rids:
                self.rids.append(self.rid)
        return code, out, err

    def approve(self, rid=None, apply=True, shown=True):
        argv = ["approve"] + self.common() + ["--request", rid or self.rid, "--local", "--created", f"2027-01-{20 + self.k:02d}T15:00:00Z"]
        if shown:
            argv.append("--preview-shown")
        if apply:
            argv.append("--apply")
        return F.run(R.main, argv)

    def export(self, rid=None, apply=True):
        return F.run(R.main, ["export"] + self.common() + ["--request", rid or self.rid] + (["--apply"] if apply else []))

    def withdraw(self, rid=None, apply=True):
        self.k += 1
        return F.run(R.main, ["withdraw"] + self.common() + ["--request", rid or self.rid, "--reason", "error-found", "--created", day(self.k)] + (["--apply"] if apply else []))

    def export_state(self, rid=None, apply=True):
        return F.run(R.main, ["export-state"] + self.common() + ["--request", rid or self.rid] + (["--apply"] if apply else []))

    def edit_source(self, old, new):
        """The owner edits a cited section of a source and renders it again with the real renderer."""
        path = self.root / "ground-truth" / "company-governance.md"
        text = path.read_text(encoding="utf-8")
        need(old in text, "the section to edit is not in the source")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        r = run_script("render_ground_truth.py", path, "--root", self.root, "--source-id", "company-governance", "--version", "2027.2",
                       "--date", "2027-01-25", cwd=self.root)
        need(r.returncode == 0, "the renderer refused: " + r.stdout[-200:] + r.stderr[-200:])

    def diff(self):
        return F.run(R.main, ["diff"] + self.common() + ["--repository-id", "4200"])

    def publish(self, message="Release"):
        """Commit the working tree and push it to the origin, as the owner does after reviewing the changes."""
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", message)
        if self.origin is None:
            self.origin = self.base / "origin.git"
            git(self.base, "clone", "-q", "--bare", self.root, self.origin)
            git(self.root, "remote", "add", "origin", self.origin)
            git(self.root, "fetch", "-q", "origin")
            git(self.root, "branch", "-q", "--set-upstream-to=origin/main", "main")
        else:
            git(self.root, "push", "-q", "origin", "main")

    def clone(self, name):
        dest = self.base / name
        git(self.base, "clone", "-q", self.origin, dest)
        git(dest, "config", "user.name", "Engineer")
        git(dest, "config", "user.email", "engineer@example.com")
        return dest

    def receipt(self, rid, root=None):
        return RS.loads_strict((Path(root or self.root) / "docs" / "release" / f"{rid}.receipt.json").read_bytes())

    # the steps C1 to C7 use the same names on both paths
    def activate(self, rid=None):
        code, out, err = self.approve(rid)
        need(code == 0, out + err)

    def retire(self, rid=None):
        code, out, err = self.withdraw(rid)
        need(code == 0, out + err)

    def publish_release(self, rid):
        self.publish("Release " + rid[:12])

    def publish_state(self, rid):
        self.publish("State of " + rid[:12])

    def old_clone(self):
        return stage("yes.clone")

    def replay(self):
        return V.local_replay(str(self.ws)).replay

    def records(self, rid):
        record = V.verify_local_request(V.load_local_evidence(str(self.ws), rid), rid)
        return record, V.local_replay(str(self.ws)).replay


def yes():
    """The project of Scenario A. It is created on first use, with the network guard on."""
    def build():
        S.net.start()
        return YesFlow(S.tmp / "yes")
    return S.once("yes", build)


def posix_only():
    if os.name != "posix":
        raise Skip("the owner-only mode check is a POSIX check; Windows uses an access control list, which workspace.py verifies with icacls")


BUILD, DEPS = {}, {}


def builder(key, *deps):
    """Register how a fixture stage is built and which stages it needs first. stage(key) builds a stage once, after its needs."""
    def deco(fn):
        BUILD[key], DEPS[key] = fn, deps
        return fn
    return deco


def stage(key):
    for need_ in DEPS[key]:
        stage(need_)
    return S.once(key, BUILD[key])


@builder("yes.init")
def _():
    return yes().init_workspace()


@builder("yes.staffing", "yes.init")
def _():
    yes().put_staffing()


@builder("yes.render", "yes.staffing")
def _():
    return yes().render_all()


@builder("yes.prepare", "yes.render")
def _():
    return yes().prepare()


@builder("yes.approve", "yes.prepare")
def _():
    return yes().approve()


@builder("yes.export", "yes.approve")
def _():
    return yes().export()


# --- A1 ---------------------------------------------------------------------

@step("A1.1", "step 0 answered yes: the private workspace is created owner only with git, and the untracked pointer is written")
def _():
    y = yes()
    code, out, err = stage("yes.init")
    need(code == 0, out + err)
    need("private workspace ready" in out, out)
    need((y.ws / ".git").is_dir() and (y.root / ".carrydown" / "local.yaml").is_file())
    ignored = git(y.root, "check-ignore", ".carrydown/local.yaml", check=False)
    need(ignored.returncode == 0, "the pointer is not ignored")
    need(".carrydown/local.yaml" not in tracked(y.root))
    posix_only()
    equal(oct(os.stat(y.ws).st_mode & 0o777), "0o700", "workspace mode")


@step("A1.2", "the answer is recorded once: the plan says repository readers approved, shared drafting, and no source is restricted")
def _():
    y = yes()
    stage("yes.init")
    plan, problems = L.load_plan(y.root / "docs/spec/plan.yaml", y.root)
    equal(plan["project"]["handling"]["repo_audience_approved"], True, "repo_audience_approved")
    equal(sorted(s["classification"] for s in plan["sources"]), ["repo-readers", "repo-readers"], "classifications")
    data = L.load_file(y.ws / "workspace.yaml")
    equal(data["slug"], "expense-approvals", "slug")
    status = run_script("workspace.py", "status", "--root", y.root, cwd=y.root)
    need(status.returncode == 0 and "state:" in status.stdout, status.stdout + status.stderr)


@step("A1.3", "fictional staffing goes to the private workspace and is in no tracked file of the engineering repository")
def _():
    y = yes()
    stage("yes.staffing")
    status = run_script("workspace.py", "status", "--root", y.root, cwd=y.root)
    need("people.yaml: 2 people" in status.stdout, status.stdout)
    need("people.yaml" not in " ".join(tracked(y.root)), "a people file is tracked")
    files = {p: (y.root / p).read_bytes() for p in tracked(y.root) if p}
    equal(scan_text(files, SEEDS), [], "staffing strings in tracked files")
    plan, _p = L.load_plan(y.root / "docs/spec/plan.yaml", y.root)
    for person in plan["people"]:
        need(set(person) <= {"id", "track", "derived"}, f"people:{person['id']} holds more than an id and a track")


@step("A1.4", "no staging repository, enrollment, policy pointer or App is configured, and the offline doctor does not block")
def _():
    y = yes()
    stage("yes.init")
    data = L.load_file(y.ws / "workspace.yaml")
    for key in ("staging_repository", "tooling_repository", "enrollment_id", "policy_commit_sha"):
        need(not data.get(key), f"workspace.yaml names {key}")
    need(not (y.root / POINTER).exists(), "a policy pointer exists")
    doctor = run_script("workspace.py", "doctor", "--root", y.root, cwd=y.root)
    equal(doctor.returncode, 0, "workspace.py doctor exit status: " + doctor.stdout[-300:])


# --- A2 ---------------------------------------------------------------------

@step("A2.1", "shareable material is drafted and rendered in the engineering repository by the real renderer (a draft write)")
def _():
    y = yes()
    results = stage("yes.render")
    for source, code, text in results:
        need(code == 0, f"{source}: {text[-300:]}")
        need((y.root / "docs" / "ground-truth" / f"{source}.md").is_file(), f"{source} was not rendered into docs/ground-truth")
    need(not list((y.ws / "renderings").iterdir()), "a repository-readers rendering went to the workspace")


@step("A2.2", "the checker passes on the drafts and, with the staffing overlay on the owner's machine, checks capacity too")
def _():
    y = yes()
    stage("yes.render")
    r = run_script("check_specs.py", "--root", y.root, "--report", cwd=y.root)
    need(r.returncode == 0 and "0 finding(s)" in r.stdout, r.stdout[-500:] + r.stderr[-300:])
    need("people overlay not loaded" not in r.stdout, "the owner's machine did not load the staffing overlay from the workspace")
    shutil.move(str(y.ws / "people.yaml"), str(y.ws / "people.hidden"))
    try:
        r = run_script("check_specs.py", "--root", y.root, "--report", cwd=y.root)
        need(r.returncode == 0 and "0 finding(s)" in r.stdout and "people overlay not loaded" in r.stdout, "without the overlay the checker must pass and say it skipped the staffing checks: " + r.stdout[-300:])
    finally:
        shutil.move(str(y.ws / "people.hidden"), str(y.ws / "people.yaml"))


@step("A2.3", "after drafting, staffing is still only in the workspace: no repository file holds a name or a staffing field")
def _():
    y = yes()
    stage("yes.render")
    files = {p.relative_to(y.root).as_posix(): p.read_bytes() for p in y.root.rglob("*") if p.is_file() and ".git" not in p.relative_to(y.root).parts}
    equal(scan_text(files, SEEDS), [], "staffing strings in the working tree")
    need((y.ws / "people.yaml").read_text(encoding="utf-8").count("Tamsin Hale") == 1, "the staffing record is missing from the workspace")


@step("A2.4", "prepare is a dry run until --apply: the dry run writes nothing, the apply builds the immutable snapshot")
def _():
    y = yes()
    stage("yes.render")
    before_root, before_ws = tree_state(y.root), tree_state(y.ws)
    code, out, err = y.prepare(apply=False)
    need(code == 0 and "Dry run: nothing was written" in out, out + err)
    equal((tree_state(y.root), tree_state(y.ws)), (before_root, before_ws), "files after the dry run")
    y.k -= 1        # the dry run consumed a counter value; the apply uses the next, as a retry would
    code, out, err = stage("yes.prepare")
    need(code == 0, out + err)
    request = R.load_request(y.ws, y.rid)
    manifest, entries, files = R.load_release(y.ws, request["release_id"])
    equal(RS.sha256_bytes(manifest), request["release_id"], "release id is the manifest digest")
    equal(RS.hash_request(request), y.rid, "request id is the recomputed request digest")
    need(re.fullmatch(r"[0-9a-f]{32}", request["request_nonce"]), "nonce")
    need(not [p for p, data in files.items() if request["release_id"].encode() in data], "a snapshot file holds the release id")


@step("A2.5", "the released plan is the modern allowlisted view: no source path, classification, digest or staffing field")
def _():
    y = yes()
    stage("yes.prepare")
    request = R.load_request(y.ws, y.rid)
    text = (y.ws / "releases" / request["release_id"] / "snapshot" / "repo" / "docs/spec/plan.yaml").read_text(encoding="utf-8")
    plan = L.loads(text)
    equal((plan.get("plan_format"), plan.get("plan_view")), (2, "released"), "plan format and view")
    for source in plan["sources"]:
        equal(sorted(source), ["id", "name", "version"], "released source keys")
    for person in plan["people"]:
        need(set(person) <= {"id", "track", "derived"}, "people carry more than ids and tracks")
    need("advisors" not in plan, "advisors are released")
    equal(scan_text({"plan": text.encode("utf-8")}, SEEDS), [], "staffing strings in the released plan")


@step("A2.6", "bundles are prepared for every work item and payloads are bound to a destination and a target")
def _():
    y = yes()
    stage("yes.prepare")
    _plan, ids = plan_ids(y.root)
    request = R.load_request(y.ws, y.rid)
    _m, _e, files = R.load_release(y.ws, request["release_id"])
    for item in ids:
        stem = item.lower()
        need(f"repo/docs/context/{stem}.md" in files and f"repo/docs/context/{stem}.bundle.json" in files, f"{item} has no bundle")
        side = RS.loads_strict(files[f"repo/docs/context/{stem}.bundle.json"])
        equal(side["content_sha256"], RS.sha256_bytes(files[f"repo/docs/context/{stem}.md"]), f"{item} bundle digest")
        need("release_id" not in side, "a bundle sidecar carries the release id")
    payload = RS.loads_strict(files["payloads/issue/WI-06.json"])
    equal(payload["destination_id"], "engineering", "issue payload destination")
    equal(payload["target"]["key"], "WI-06", "issue payload target")
    need({t["id"] for t in request["receipt_template"]["targets"]} >= {"engineering"}, "the request names no engineering target")


@step("A2.7", "the four-question preview comes first, in order, and a local approval without it is refused")
def _():
    y = yes()
    stage("yes.prepare")
    code, out, err = F.run(R.main, ["preview"] + y.common() + ["--repository-id", "4200"])
    need(code == 0, out + err)
    positions = [out.index(q) for q in ("What will be shared?", "With whom?", "Where?", "What remains private?")]
    equal(positions, sorted(positions), "order of the four questions")
    before = tree_state(y.ws)
    code, out, err = y.approve(shown=False)
    need(code == 1 and "not-approved" in err, out + err)
    equal(tree_state(y.ws), before, "workspace after the refused approval")


@step("A2.8", "the owner approves locally with the saved request id: local-owner evidence, authenticated false, one activation event")
def _():
    y = yes()
    stage("yes.prepare")
    equal(R.load_request(y.ws, y.rid)["request_sha256"], y.rid, "the request saved under its own id")
    code, out, err = stage("yes.approve")
    need(code == 0, out + err)
    approval = read_json(y.ws / "requests" / y.rid / "approval.json")
    equal((approval["type"], approval["authenticated"], approval["request_sha256"]), ("local-owner", False, y.rid), "approval")
    events = sorted((y.ws / "events").iterdir())
    equal(len(events), 1, "event files")
    event = RS.loads_strict(events[0].read_bytes())
    equal([(t["request_id"], t["from"], t["to"], t["previous_event_id"]) for t in event["transitions"]], [(y.rid, "prepared", "active", None)], "activation")
    return f"approval.json type={approval['type']} authenticated={approval['authenticated']}; event {event['event_id'][:12]} prepared -> active"


# --- A3 ---------------------------------------------------------------------

@step("A3.1", "export on the existing branch is a dry run first, then writes the files and the exact receipt: local-owner, authenticated false")
def _():
    y = yes()
    stage("yes.approve")
    before = tree_state(y.root)
    code, out, err = y.export(apply=False)
    need(code == 0 and "Dry run: nothing was written" in out, out + err)
    equal(tree_state(y.root), before, "working tree after the export dry run")
    code, out, err = stage("yes.export")
    need(code == 0, out + err)
    receipt = y.receipt(y.rid)
    equal(receipt["approval"], {"type": "local-owner", "authenticated": False, "ref": y.rid}, "receipt approval")
    equal(receipt["state"], "active", "receipt state")
    record, replay = y.records(y.rid)
    RS.verify_receipt_bytes((y.root / "docs" / "release" / f"{y.rid}.receipt.json").read_bytes(), record.request, record.manifest_bytes,
                            replay.requests[y.rid], record.approval)
    return f"receipt {y.rid[:12]} approval={receipt['approval']['type']} authenticated={receipt['approval']['authenticated']} state={receipt['state']}; equals the projection"


def strip_clone(clone):
    """The independent clone loses access to the workspace and to every optional original and full rendering."""
    for folder in ("ground-truth", "docs/ground-truth", "docs/source"):
        shutil.rmtree(Path(clone) / folder, ignore_errors=True)
    need(not (Path(clone) / ".carrydown" / "local.yaml").exists(), "the clone has a workspace pointer")


def clean_clone(y, name):
    y.publish("Release")
    clone = y.clone(name)
    strip_clone(clone)
    return clone


@builder("yes.clone", "yes.export")
def _():
    return clean_clone(yes(), "clone-yes")


@step("A3.2", "in an independent clone with no workspace and no originals or full renderings, the engineers' context check passes for every work item")
def _():
    y = yes()
    stage("yes.export")
    clone = stage("yes.clone")
    _plan, ids = plan_ids(y.root)
    need(L.workspace_root(clone)[0] is None, "the clone can reach a workspace")
    for item in ids:
        r = run_script(skill_script(clone), item, "--root", clone, cwd=clone)
        need(r.returncode == 0, f"{item}: {r.stdout[-200:]}")


def swap_released_plan(y, clone):
    """The clone already holds the snapshot's released plan, because the yes-path export writes it (and moves the owner's
    working plan to the private workspace). Check that instead of copying it in."""
    request = R.load_request(y.ws, y.rid)
    released = (y.ws / "releases" / request["release_id"] / "snapshot" / "repo" / "docs/spec/plan.yaml").read_bytes()
    need((Path(clone) / "docs/spec/plan.yaml").read_bytes() == released, "the clone does not hold the released plan of the snapshot")


@step("A3.3", "the released-view checker passes on the exported tree of the clone, which has no original and no full rendering")
def _():
    y = yes()
    clone = stage("yes.clone")
    r = run_script("check_specs.py", "--root", clone, "--view", "released", cwd=clone)
    need(r.returncode == 0, r.stdout[-300:])


@step("A3.4", "with the released plan of the snapshot in place the released schema, the citations and the bundle hashes pass in that clone, and one changed bundle byte fails")
def _():
    y = yes()
    clone = stage("yes.clone")
    swap_released_plan(y, clone)
    r = run_script("check_specs.py", "--root", clone, "--view", "released", cwd=clone)
    need(r.returncode == 0, r.stdout[-400:] + r.stderr[-300:])
    bundle = clone / "docs/context/wi-06.md"
    original = bundle.read_bytes()
    bundle.write_bytes(original.replace(b"25,000.00", b"26,000.00", 1))
    need(bundle.read_bytes() != original, "the bundle byte was not changed")
    r = run_script("check_specs.py", "--root", clone, "--view", "released", cwd=clone)
    need(r.returncode != 0, "a changed bundle byte passed the released check")
    bundle.write_bytes(original)


@step("A3.5", "a source classified public gives the same result: its original and its rendering are optional in the clone too")
def _():
    def build():
        y = YesFlow(S.tmp / "yes-public", public=("architecture",))
        y.init_workspace()
        y.put_staffing()
        for source, code, text in y.render_all():
            need(code == 0, text[-300:])
        for call in (y.prepare, y.approve, y.export):
            code, out, err = call()
            need(code == 0, out + err)
        clone = clean_clone(y, "clone-public")
        swap_released_plan(y, clone)
        return y, clone
    y, clone = S.once("yes.public", build)
    plan, _p = L.load_plan(y.ws / "drafts" / "plan.yaml", y.root)     # the working plan: the project holds the released one
    equal({s["id"]: s["classification"] for s in plan["sources"]}, {"architecture": "public", "company-governance": "repo-readers"}, "classes")
    r = run_script("check_specs.py", "--root", clone, "--view", "released", cwd=clone)
    need(r.returncode == 0, r.stdout[-400:])
    for item in ("WI-01", "WI-06"):
        r = run_script(skill_script(clone), item, "--root", clone, cwd=clone)
        need(r.returncode == 0, f"{item}: {r.stdout[-200:]}")
    need(not (clone / "docs/ground-truth").exists() and not (clone / "ground-truth").exists(), "an original or a rendering is in the clone")


@step("A3.6", "a release whose plan and specifications keep the older one-line text citation passes the released-view checker in a clean clone")
def _():
    def build():
        y = YesFlow(S.tmp / "yes-text", modern=False)
        y.init_workspace()
        y.put_staffing()
        for source, code, text in y.render_all():
            need(code == 0, text[-300:])
        for call in (y.prepare, y.approve, y.export):
            code, out, err = call()
            need(code == 0, out + err)
        return y, clean_clone(y, "clone-text")
    y, clone = S.once("yes.text", build)
    plan, _p = L.load_plan(y.ws / "drafts" / "plan.yaml", y.root)
    texts = [it["id"] for it in plan["items"] if it.get("ground_truth") and not it.get("source_refs")]
    need(len(texts) == 8, f"the working plan should keep 8 text citations, has {len(texts)}")
    r = run_script("check_specs.py", "--root", clone, "--view", "released", cwd=clone)
    need(r.returncode == 0, last(r.stdout, 2))
    return f"{len(texts)} items cited as text; " + last(r.stdout)


@step("A3.7", "the whole path ran without enterprise infrastructure: no token, no enrollment, no staging repository, no network attempt")
def _():
    y = yes()
    stage("yes.export")
    need("CARRYDOWN_GITHUB_TOKEN" not in os.environ, "a token is set")
    need(not (y.root / POINTER).exists(), "a policy pointer exists")
    equal(S.net.attempts, [], "network connection attempts during Scenario A")
    S.net.stop()
    return "0 connection attempts; no token; no enrollment pointer; no staging repository in workspace.yaml"


# ---------------------------------------------------------------------------
# The "no" path: one restricted source, one individually shareable source, an enrolled organization
# ---------------------------------------------------------------------------

def scan_world(world, pub=None):
    """The verifier's entry point: capture the current protected policy, check the code pin, scan every open pull request
    of the enrolled repositories and post the check runs. Returns (report, publisher)."""
    pub = pub or FE.FakeCheckPublisher()
    tip = world.reader.branch_head(FE.TOOLING_ID, "main")
    data = world.reader.file_at(FE.TOOLING_ID, tip, "enrollment.yaml")
    report = VR.run_scan(data, tip, TOOLING, world.entry["verifier_sha"], world.reader, pub)
    return report, pub


def check_run(world, pub, repo_id, number, name):
    head = world.reader.repos[repo_id]["prs"][number]["head"]["sha"]
    return pub.state(repo_id, head, name)


def verdict(world, number, pub=None, kind="engineering"):
    """(conclusion, title) of the check the verifier posted for one pull request, after a full scan."""
    report, pub = scan_world(world, pub)
    repo = FE.ENGINEERING_ID if kind == "engineering" else FE.STAGING_ID
    run = check_run(world, pub, repo, number, V.ENGINEERING_CHECK if kind == "engineering" else V.STAGING_CHECK)
    return run["conclusion"], run["title"], pub, report


class Exported:
    """What Case needs of an exported release: the organization, the request id, the files and the pointer."""

    def __init__(self, world, rid, files, pointer):
        self.world, self.rid, self.files, self.pointer = world, rid, files, pointer

    @property
    def receipt_path(self):
        return f"docs/release/{self.rid}.receipt.json"


class NoFlow:
    """The confidential fixture on the "no" path, enrolled in the fictional organization of fake_evidence.py: a local bare
    repository is the engineering origin and another is the private staging repository."""
    path = "no"

    def __init__(self, base, world=None):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
        self.world = world or FE.World()
        self.np = F.NoProject(self.base, world=self.world).start()
        self.reader = self.world.reader
        self.root, self.ws, self.staging, self.origin = self.np.root, self.np.workspace, self.np.staging, self.np.origin
        self.pub = FE.FakeCheckPublisher()
        self.k = 0
        self.rid = None
        self.rids = []
        modernize_citations(self.ws / "drafts" / "plan.yaml", self.ws / "drafts" / "docs" / "spec")

    def common(self):
        return ["--root", str(self.root)]

    def put_staffing(self):
        shutil.copy(F.FIXTURE / "people.yaml", self.ws / "people.yaml")

    def stage_renderings(self):
        """The owner's sources go to the workspace and the real renderer stages both renderings there."""
        shutil.rmtree(self.ws / "renderings")
        (self.ws / "renderings").mkdir()
        (self.ws / "sources").mkdir(exist_ok=True)
        out = []
        for source, version in (("architecture", "0.3"), ("company-governance", "2027.1")):
            shutil.copy(F.FIXTURE / "ground-truth" / f"{source}.md", self.ws / "sources" / f"{source}.md")
            r = run_script("render_ground_truth.py", self.ws / "sources" / f"{source}.md", "--root", self.root, "--source-id", source,
                           "--version", version, "--date", "2027-01-05", cwd=self.root)
            out.append((source, r.returncode, r.stdout + r.stderr))
        return out

    def edit_source(self, old, new):
        path = self.ws / "sources" / "company-governance.md"
        text = path.read_text(encoding="utf-8")
        need(old in text, "the section to edit is not in the source")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        r = run_script("render_ground_truth.py", path, "--root", self.root, "--source-id", "company-governance", "--version", "2027.2",
                       "--date", "2027-01-25", cwd=self.root)
        need(r.returncode == 0, "the renderer refused: " + r.stdout[-200:] + r.stderr[-200:])

    def prepare(self, *extra, apply=True, fresh=True):
        kw = {"nonce": None, "created": None}
        if fresh:
            self.k += 1
            kw = {"nonce": nonce(self.k), "created": day(self.k)}
        code, out, err = self.np.prepare(*extra, apply=apply, **kw)
        if code == 0 and apply:
            self.rid = self.np.request_id
            if self.rid not in self.rids:
                self.rids.append(self.rid)
        return code, out, err

    def approve(self, rid=None, apply=True):
        return self.np.approve(rid or self.rid, apply=apply)

    def scan(self):
        return scan_world(self.world, self.pub)

    def staging_check(self, number):
        return check_run(self.world, self.pub, FE.STAGING_ID, number, V.STAGING_CHECK)

    def land(self, rid=None, files=None, branch=None):
        """The trusted workflow on the staging default branch opens the pull request (its author is the Actions identity, not the
        owner), the verifier checks it, the owner reviews the final head, the verifier checks it again, and it is merged.
        Returns (pull request number, check before the review, check after the review)."""
        rid = rid or self.rid
        files = files or self.np.candidate_files(rid)
        n = self.reader.open_pr(FE.STAGING_ID, branch or f"request/{rid}", files, user=(0, "github-actions[bot]"))
        self.scan()
        before = dict(self.staging_check(n))
        self.reader.review(FE.STAGING_ID, n, *FE.OWNER)
        self.scan()
        after = dict(self.staging_check(n))
        if after["conclusion"] == "success":
            self.reader.merge(FE.STAGING_ID, n)
        return n, before, after

    def export(self, rid=None, apply=True):
        return self.np.export(rid or self.rid, apply=apply)

    def branch_files(self, rid=None):
        """{path: (mode, bytes)} of the export branch, without the files the engineering repository already had, and the pointer."""
        tree = read_tree(self.root, f"carrydown/request-{rid or self.rid}")
        pointer = tree.pop(POINTER)[1]
        for plain in ("README.md", ".gitignore"):
            tree.pop(plain, None)
        return tree, pointer

    def exported(self, rid=None):
        files, pointer = self.branch_files(rid)
        return Exported(self.world, rid or self.rid, files, pointer)

    def publish_branch(self, branch):
        """The owner's separately authorized push, and the merge of the engineering pull request (a fast-forward of the default branch)."""
        git(self.root, "push", "-q", "origin", branch)
        git(self.root, "push", "-q", "origin", f"{branch}:main")

    def withdraw(self, rid=None, reason="error-found", apply=True):
        rid = rid or self.rid
        self.k += 1
        code, out, err = F.run(R.main, ["withdraw"] + self.common() + ["--request", rid, "--reason", reason] + (["--apply"] if apply else [])
                               + ["--poll-seconds", "0", "--created", day(self.k)])
        return code, out, err

    def land_withdrawal(self, rid=None):
        rid = rid or self.rid
        event = RS.loads_strict((self.ws / "requests" / rid / "withdrawal-candidate.json").read_bytes())
        return self.land(files=B.state_branch_files(event), branch=f"state/{event['event_id']}")

    def export_state(self, rid=None, apply=True):
        return F.run(R.main, ["export-state"] + self.common() + ["--request", rid or self.rid] + (["--apply"] if apply else []))

    def clone(self, name):
        dest = self.base / name
        git(self.base, "clone", "-q", self.origin, dest)
        git(dest, "config", "user.name", "Engineer")
        git(dest, "config", "user.email", "engineer@example.com")
        return dest

    def replay(self):
        return V.replay_staging(self.reader, self.world.enrollment()).replay

    # the steps C1 to C7 use the same names on both paths
    def diff(self):
        return F.run(R.main, ["diff"] + self.common())

    def activate(self, rid=None):
        code, out, err = self.approve(rid)
        need(code == 0, out + err)
        number, before, after = self.land(rid or self.rid)
        need(after["conclusion"] == "success", f"staging check {after['title']}")
        return number

    def retire(self, rid=None):
        code, out, err = self.withdraw(rid)
        need(code == 0, out + err)
        number, before, after = self.land_withdrawal(rid)
        need(after["conclusion"] == "success", f"staging check {after['title']}")
        return number

    def publish_release(self, rid):
        self.publish_branch(f"carrydown/request-{rid}")

    def publish_state(self, rid):
        self.publish_branch(f"carrydown/state-{rid}")

    def old_clone(self):
        return stage("no.clone")

    def staging_heads(self):
        return ls_heads(self.staging)

    def record(self, rid=None):
        return V.verify_request(rid or self.rid, self.reader, self.world.enrollment())


def no():
    return S.once("no", lambda: NoFlow(S.tmp / "no"))


@builder("no.staffing")
def _():
    no().put_staffing()


@builder("no.renderings", "no.staffing")
def _():
    results = no().stage_renderings()
    for source, code, text in results:
        need(code == 0, f"{source}: {text[-300:]}")
    return results


@builder("no.prepare", "no.renderings")
def _():
    return no().prepare()


@builder("no.upload", "no.prepare")
def _():
    n = no()
    out = n.approve()
    n.pre_land = copy.deepcopy(n.world)
    return out


@builder("no.land", "no.upload")
def _():
    return no().land()


@builder("no.export", "no.land")
def _():
    n = no()
    out = n.export()
    if out[0] == 0:
        # the organization and the exported release as they are right after the first release: later steps change both
        first = n.rids[0]
        files, pointer = n.branch_files(first)
        n.frozen = Exported(copy.deepcopy(n.world), first, files, pointer)
    return out


@builder("no.frozen", "no.export")
def _():
    return no().frozen


@builder("no.published", "no.export")
def _():
    n = no()
    n.publish_branch(f"carrydown/request-{n.rid}")


@builder("no.clone", "no.published")
def _():
    return no().clone("clone-no")


def no_path_staged():
    stage("no.renderings")
    return no()


# --- B1 ---------------------------------------------------------------------

@step("B1.1", "step 0 answered no: the workspace exists, the sources are classified (one restricted, one repository readers), and the staging commands were printed but not run")
def _():
    n = no()
    data = L.load_file(n.ws / "workspace.yaml")
    equal(data.get("staging_repository"), "acme/expense-approvals-releases", "staging repository named in workspace.yaml")
    plan, _p = L.load_plan(n.ws / "drafts" / "plan.yaml", n.root)
    equal(plan["project"]["handling"]["repo_audience_approved"], False, "the answer")
    equal({s["id"]: s["classification"] for s in plan["sources"]}, {"architecture": "repo-readers", "company-governance": "restricted"}, "classification")
    code, out, err = F.run(W.main, ["init", "--root", str(n.root), "--slug", "expense-approvals", "--workspace", str(n.ws), "--answer", "no",
                                    "--staging-repository", "acme/expense-approvals-releases"])
    need(code == 0 and "acme/expense-approvals-releases" in out and "does not run these commands" in out, out + err)
    equal(n.staging_heads(), ["refs/heads/main"], "the staging repository after the dry run")


@step("B1.2", "fictional staffing is initialized in the workspace and nowhere in the engineering repository")
def _():
    n = no()
    stage("no.staffing")
    status = run_script("workspace.py", "status", "--root", n.root, cwd=n.root)
    need("people.yaml: 2 people" in status.stdout, status.stdout)
    files = {p: (n.root / p).read_bytes() for p in tracked(n.root) if p}
    equal(scan_text(files, SEEDS), [], "staffing strings in the engineering repository")


@step("B1.3", "both renderings, the restricted source and the individually shareable one, are staged in the workspace by the real renderer")
def _():
    n = no()
    before = tree_state(n.root)
    for source, code, text in stage("no.renderings"):
        need(code == 0, f"{source}: {text[-300:]}")
        need((n.ws / "renderings" / f"{source}.md").is_file(), f"{source} is not in the workspace renderings")
    equal(tree_state(n.root), before, "the engineering repository after rendering")
    need(not (n.root / "docs").exists(), "a docs folder appeared in the engineering repository")
    plan, _p = L.load_plan(n.ws / "drafts" / "plan.yaml", n.root)
    need(all(s.get("content_sha256") and s.get("rendering_sha256") for s in plan["sources"]), "digests were not recorded in the workspace plan")


@step("B1.4", "zero draft content is written into engineering paths before approval, the shareable source included: drafting there is refused and the tree is unchanged")
def _():
    n = no_path_staged()
    expected = {"README.md", ".gitignore", POINTER}
    equal(set(tracked(n.root)) - {""}, expected, "tracked files")
    untracked = git(n.root, "status", "--porcelain", "--ignored").stdout
    need("docs/" not in untracked and "people.yaml" not in untracked, untracked)
    r = run_script("render_ground_truth.py", n.ws / "sources" / "architecture.md", "--root", n.root, "--source-id", "architecture",
                   "--out-dir", "docs/ground-truth", "--dry-run", cwd=n.root)
    need(r.returncode != 0, "the shareable source can be rendered into the engineering repository on the no path: " + r.stdout[-200:])
    (n.root / "docs" / "spec").mkdir(parents=True)
    shutil.copy(n.ws / "drafts" / "plan.yaml", n.root / "docs" / "spec" / "plan.yaml")
    try:
        before = tree_state(n.root)
        for script, args in (("scaffold_spec.py", ["--apply", "--allow-no-git"]), ("generate_dev_skill.py", ["--apply"]), ("plan_repair.py", ["--apply"])):
            r = run_script(script, "--root", n.root, *args, cwd=n.root)
            need(r.returncode != 0 and re.search("not-approved|drafting-is-private|workspace-unavailable", r.stderr), f"{script}: {r.returncode} {r.stderr[-200:]}")
        equal(tree_state(n.root), before, "the engineering repository after refused drafting")
    finally:
        shutil.rmtree(n.root / "docs")


@step("B1.5", "the fake organization is enrolled with an authorized approver account id, and the policy revision and the pinned verifier code are separate commits")
def _():
    n = no()
    enrollment = n.world.enrollment()
    equal([a["id"] for a in enrollment.entry["approvers"]], [FE.OWNER[0]], "approver ids")
    code_sha = enrollment.entry["verifier_sha"]
    need(code_sha != enrollment.policy_commit_sha, "policy and code are the same commit")
    need(n.reader.is_ancestor(FE.TOOLING_ID, code_sha, enrollment.policy_commit_sha), "the pinned code commit is not an ancestor of the policy commit")
    pointer = L.load_file(n.root / POINTER)
    equal(pointer["enrollment_id"], enrollment.enrollment_id, "the policy pointer")
    equal(sorted(pointer), ["enrollment_id", "format", "tooling_repository"], "pointer keys")


# --- B2 ---------------------------------------------------------------------

@step("B2.1", "prepare builds the immutable manifest, the request with its receipt template, and the initial activation batch (a dry run first)")
def _():
    n = no_path_staged()
    before_root, before_ws = tree_state(n.root), tree_state(n.ws)
    code, out, err = n.prepare(apply=False)
    need(code == 0 and "Dry run: nothing was written" in out, out + err)
    equal((tree_state(n.root), tree_state(n.ws)), (before_root, before_ws), "files after the prepare dry run")
    n.k -= 1
    code, out, err = stage("no.prepare")
    need(code == 0, out + err)
    request = R.load_request(n.ws, n.rid)
    manifest, entries, files = R.load_release(n.ws, request["release_id"])
    equal(RS.sha256_bytes(manifest), request["release_id"], "release id")
    equal(RS.hash_request(request), n.rid, "request id")
    equal(sorted(request["receipt_template"]), sorted(RS.TEMPLATE_KEYS), "receipt template keys")
    need(re.fullmatch(r"[0-9a-f]{32}", request["request_nonce"]), "request nonce")
    equal(request["enrollment_id"], n.world.enrollment().enrollment_id, "enrollment id in the request")
    control = [p for p in files if p.rsplit("/", 1)[-1] in ("approval-request.json", "approval.json", "state.json", "content-manifest.json", "activation-candidate.json")
               or p.startswith(("events/", "requests/", "releases/"))]
    equal(control, [], "control files inside the snapshot")
    need(not (n.ws / "requests" / n.rid / "activation-candidate.json").exists(), "the activation batch exists before the request was approved for upload")
    need(not [p for p, data in files.items() if request["release_id"].encode() in data], "a snapshot file holds the release id")


@step("B2.2", "a private upload with an overbroad staging reader is refused with zero pushes")
def _():
    n = no()
    stage("no.prepare")
    writes_before = (n.staging_heads(), len(n.reader.repos[FE.STAGING_ID]["prs"]), len(n.reader.repos[FE.STAGING_ID]["commits"]), list(n.np.dispatches))
    n.reader.collaborators_by_repo[FE.STAGING_ID].append({"id": 999, "login": "outsider", "permission": "read"})
    try:
        code, out, err = n.approve()
        need(code == 1 and "staging-access-not-verified" in err, out + err)
    finally:
        n.reader.collaborators_by_repo[FE.STAGING_ID].pop()
    writes_after = (n.staging_heads(), len(n.reader.repos[FE.STAGING_ID]["prs"]), len(n.reader.repos[FE.STAGING_ID]["commits"]), list(n.np.dispatches))
    equal(writes_after, writes_before, "pushes, pull requests, commits and workflow dispatches on the staging repository")
    equal(n.staging_heads(), ["refs/heads/main"], "staging refs")
    return f"staging-access-not-verified; refs {n.staging_heads()}, {writes_after[1]} pull requests, {writes_after[2]} commits, {len(writes_after[3])} dispatches: unchanged"


@step("B2.3", "a private upload with an unreadable access list and no attestation is refused with zero pushes")
def _():
    n = no()
    stage("no.prepare")
    n.reader.fail("collaborators", FE.STAGING_ID)
    try:
        code, out, err = n.approve()
        need(code == 1 and "staging-access-not-verified" in err, out + err)
    finally:
        n.reader.failures.pop(("collaborators", FE.STAGING_ID), None)
    equal(n.staging_heads(), ["refs/heads/main"], "staging refs")
    equal(list(n.np.dispatches), [], "workflow dispatches")


@step("B2.4", "a valid scoped administrator attestation lets the upload proceed while the list is unreadable; the policy change forces a new request")
def _():
    base = S.tmp / "no-attested"
    world = FE.World()
    now = world.reader._clock
    subject = {"repository_id": FE.STAGING_ID, "reader_ids": sorted(world.entry["staging_readers"]["user_ids"]), "service_ids": []}
    attestation = {"component": "staging-readers", "by_id": world.admins[0][0], "at": V.utc_text(now - 3600), "expires_at": V.utc_text(now + 86400 * 30),
                   "subject": subject, "note": "effective readers inspected, including inherited access"}
    n = no()
    n.np.stop()
    try:
        scratch = NoFlow(base, world=world)
        try:
            scratch.stage_renderings()
            code, out, err = scratch.prepare()
            need(code == 0, out + err)
            first = scratch.rid
            scratch.reader.fail("collaborators", FE.STAGING_ID)
            code, out, err = scratch.approve()
            need(code == 1 and "staging-access-not-verified" in err, "without the attestation: " + out + err)
            equal(scratch.staging_heads(), ["refs/heads/main"], "refs before the attestation")
            world.update_policy(lambda e: e["attestations"].append(attestation))
            code, out, err = scratch.approve()
            need(code == 1 and "policy-revision-mismatch" in err, "an old request under a changed policy: " + out + err)
            equal(scratch.staging_heads(), ["refs/heads/main"], "refs after a stale request")
            code, out, err = scratch.prepare()
            need(code == 0 and scratch.rid != first, out + err)
            code, out, err = scratch.approve()
            need(code == 0 and "candidate uploaded" in out, out + err)
            need(f"refs/heads/request/{scratch.rid}" in scratch.staging_heads(), "the attested upload did not push")
        finally:
            scratch.np.stop()
    finally:
        n.np.start()


@step("B2.5", "with verified access the candidate is uploaded: only the snapshot, manifest, request and activation batch; no original, staffing file or approval record")
def _():
    n = no()
    stage("no.prepare")
    ws_before, heads = tree_state(n.ws), n.staging_heads()
    code, out, err = n.approve(apply=False)
    need(code == 0 and "Dry run" in out, out + err)
    equal((tree_state(n.ws), n.staging_heads()), (ws_before, heads), "the workspace and the staging repository after the approve dry run")
    code, out, err = stage("no.upload")
    need(code == 0 and "candidate uploaded; approval request pending" in out, out + err)
    equal(sorted(n.staging_heads()), sorted(["refs/heads/main", f"refs/heads/request/{n.rid}"]), "staging refs")
    event = RS.loads_strict((n.ws / "requests" / n.rid / "activation-candidate.json").read_bytes())
    equal([(t["request_id"], t["from"], t["to"], t["previous_event_id"]) for t in event["transitions"]], [(n.rid, "prepared", "active", None)], "initial activation batch")
    equal(RS.hash_event(event), event["event_id"], "event id is the recomputed batch digest")
    clone = S.tmp / "staging-clone"
    git(S.tmp, "clone", "-q", "-b", f"request/{n.rid}", n.staging, clone)
    files = tree_state(clone)
    for path in files:
        need(re.match(r"^(README\.md|releases/[0-9a-f]{64}/|requests/[0-9a-f]{64}/approval-request\.json$|events/[0-9a-f]{64}\.json$)", path), f"unexpected staging file {path}")
    blob = b"".join((clone / p).read_bytes() for p in files)
    need(not scan_text({"blob": blob}, SEEDS + ("people.yaml", "source_path")), "private strings in the staging candidate")
    need(not (clone / "requests" / n.rid / "approval.json").exists(), "approval evidence is in the candidate")


@step("B2.6", "the default-branch bot opens the request, the final-head owner review and the staging check succeed, and the merge activates it")
def _():
    n = no()
    stage("no.upload")
    number, before, after = stage("no.land")
    pr = n.reader.repos[FE.STAGING_ID]["prs"][number]
    equal(pr["user"]["login"], "github-actions[bot]", "request author")
    need(pr["user"]["id"] not in {a["id"] for a in n.world.enrollment().entry["approvers"]}, "the author is an approver")
    equal(before["conclusion"], "failure", "the check before any review")
    equal(after["conclusion"], "success", "the check after the owner's review of the final head")
    review = pr["reviews"][-1]
    equal((review["user"]["id"], review["state"], review["commit_id"]), (FE.OWNER[0], "APPROVED", pr["head"]["sha"]), "the review")
    need(pr["merged"], "the pull request did not merge")
    return f"author {pr['user']['login']}; check before review: {before['title']}; reviewer id {review['user']['id']} on the final head; check after: {after['title']}; merged"


@step("B2.7", "the first activation works without an older active state file: the staging history alone makes the request active")
def _():
    n = no()
    stage("no.land")
    need(not (n.ws / "requests" / n.rid / "state.json").exists(), "a state file existed before the export")
    replay = n.replay()
    equal((replay.requests[n.rid].state, replay.active), ("active", n.rid), "replayed state")
    event = RS.loads_strict((n.ws / "requests" / n.rid / "activation-candidate.json").read_bytes())
    equal(replay.tip, event["event_id"], "tip")
    record = n.record()
    equal(record.request["request_sha256"], n.rid, "verified request")


@step("B2.8", "local-owner evidence is rejected on this path: approve --local refuses and the verifier rejects a local-owner receipt")
def _():
    n = no()
    stage("no.land")
    code, out, err = F.run(R.main, ["approve"] + n.common() + ["--request", n.rid, "--local", "--preview-shown", "--apply"])
    need(code == 1 and "unauthenticated-release" in err, out + err)
    need(not (n.ws / "requests" / n.rid / "approval.json").exists(), "local approval evidence was recorded")
    record = n.record()
    state = n.replay().requests[n.rid]
    local = RS.project_receipt(record.request, record.manifest_bytes, state, RS.VerifiedApproval(n.rid, "local-owner", False))
    files = n.np.candidate_files(n.rid)
    plan = {p[len("releases/"):]: v for p, v in files.items()}
    snapshot = {p.split("/snapshot/", 1)[1]: v for p, v in files.items() if "/snapshot/repo/" in p}
    case_files = {p[len("repo/"):]: ("100644", v) for p, v in snapshot.items() if p.startswith("repo/")}
    case_files[f"docs/release/{n.rid}.receipt.json"] = ("100644", local)
    pointer = (n.root / POINTER).read_bytes()
    case = EF.Case(Exported(n.world, n.rid, case_files, pointer))
    number = case.open()
    conclusion, title, _p, _r = verdict(case.world, number)
    equal((conclusion, title), ("failure", "carrydown: unauthenticated-release"), "verifier on a local-owner receipt")


# --- B3 ---------------------------------------------------------------------

@step("B3.1", "export uses an isolated worktree: a dry run makes no branch, the apply commits as the owner on carrydown/request-<id>, and the owner's dirty tree is preserved")
def _():
    n = no()
    stage("no.land")
    (n.root / "README.md").write_text("uncommitted edit\n", encoding="utf-8")
    (n.root / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    before, status = tree_state(n.root), git(n.root, "status", "--porcelain").stdout
    code, out, err = n.export(apply=False)
    need(code == 0, out + err)
    equal(git(n.root, "branch", "--list", "carrydown/*").stdout.strip(), "", "branches after the export dry run")
    code, out, err = stage("no.export")
    need(code == 0, out + err)
    branch = f"carrydown/request-{n.rid}"
    equal(git(n.root, "branch", "--list", "carrydown/*").stdout.split(), [branch], "branches")
    equal(tree_state(n.root), before, "the owner's working tree")
    equal(git(n.root, "status", "--porcelain").stdout, status, "git status")
    equal(git(n.root, "rev-list", "--count", f"origin/main..{branch}").stdout.strip(), "1", "commits on the export branch")
    equal(git(n.root, "log", "-1", "--format=%an <%ae>|%cn <%ce>", branch).stdout.strip(), "Test Owner <owner@example.com>|Test Owner <owner@example.com>", "author")
    need("Co-Authored" not in git(n.root, "log", "-1", "--format=%B", branch).stdout, "a trailer was added")
    need(len([x for x in git(n.root, "worktree", "list").stdout.splitlines() if x.strip()]) == 1, "the isolated worktree was left behind")
    need(f"push -u origin {branch}" in out and "gh pr create" in out, "the push and pull request commands were not printed")
    (n.root / "scratch.txt").unlink()
    git(n.root, "checkout", "--", "README.md")


@step("B3.2", "the export holds the bundles of every work item and the exact public receipt")
def _():
    n = no()
    stage("no.export")
    files, _pointer = n.branch_files()
    _plan, ids = plan_ids_released(files)
    for item in ids:
        need(f"docs/context/{item.lower()}.md" in files and f"docs/context/{item.lower()}.bundle.json" in files, f"{item} has no bundle")
    receipt_path = f"docs/release/{n.rid}.receipt.json"
    need(receipt_path in files, "no receipt")
    record = n.record()
    state = n.replay().requests[n.rid]
    RS.verify_receipt_bytes(files[receipt_path][1], record.request, record.manifest_bytes, state, record.approval)
    receipt = RS.loads_strict(files[receipt_path][1])
    equal(receipt["approval"], {"type": "github-review", "authenticated": True, "ref": n.rid}, "receipt approval")
    equal(receipt["state"], "active", "receipt state")
    need(receipt_path not in [a["path"] for a in receipt["artifacts"]], "the receipt lists itself")


def plan_ids_released(files):
    plan = L.loads(files["docs/spec/plan.yaml"][1].decode("utf-8"))
    return plan, [L.tag(plan, it["id"]) for it in plan["items"]]


STRUCTURAL_PRIVATE = ("name", "github", "skills", "preferences", "assignment_rationale", "days_off", "allocation", "start")


@step("B3.3", "the export holds no restricted full rendering, original, staffing structure, private source metadata, staging locator or approval identity field")
def _():
    n = no()
    stage("no.export")
    files, pointer = n.branch_files()
    paths = sorted(files)
    for bad in ("ground-truth/", "people.yaml", "docs/source/", ".carrydown/local.yaml", "renderings/"):
        need(not [p for p in paths if bad in p], f"{bad} is in the export")
    equal(scan_text(files, UNCITED_RESTRICTED), [], "uncited restricted text in the export")
    equal(scan_text(files, SEEDS), [], "seeded staffing strings in the export")
    equal(scan_text(files, (STAGING_LOCATOR, str(n.ws), str(S.tmp), "request/" + n.rid)), [], "staging locator or private path in the export")
    plan, _ids = plan_ids_released(files)
    for person in plan["people"]:
        need(set(person) <= {"id", "track", "derived"}, f"people:{person['id']} holds a staffing field")
    need("advisors" not in plan, "advisors in the released plan")
    for source in plan["sources"]:
        equal(sorted(source), ["id", "name", "version"], "released source keys")
    receipt = RS.loads_strict(files[f"docs/release/{n.rid}.receipt.json"][1])
    for key in receipt:
        need(key not in ("reviewer", "review_id", "pull_request", "by", "approver", "staging_repository", "classification"), f"receipt field {key}")
    equal(sorted(receipt["approval"]), ["authenticated", "ref", "type"], "receipt approval keys")
    for path, (_mode, data) in files.items():
        if path.endswith(".json"):
            keys = set(json_keys(json.loads(data.decode("utf-8"))))
            need(not keys & {"reviewer", "review_id", "reviewer_id", "staging_repository", "approver", "classification", "source_path", "content_sha256_of_source"}, f"{path} holds a private structural key")


def json_keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from json_keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from json_keys(v)


@step("B3.4", "the independent verifier, run on the proposed engineering tree, reports success and writes nothing to the repositories")
def _():
    n = no()
    exported = stage("no.frozen")
    case = EF.Case(exported)
    number = case.open()
    state_before = (len(case.reader.repos[FE.ENGINEERING_ID]["commits"]), len(case.reader.repos[FE.STAGING_ID]["commits"]),
                    len(case.reader.repos[FE.STAGING_ID]["prs"]), len(case.reader.repos[FE.ENGINEERING_ID]["prs"]))
    conclusion, title, pub, report = verdict(case.world, number)
    equal((conclusion, title), ("success", "carrydown: release verified"), "verifier check")
    equal((len(case.reader.repos[FE.ENGINEERING_ID]["commits"]), len(case.reader.repos[FE.STAGING_ID]["commits"]),
           len(case.reader.repos[FE.STAGING_ID]["prs"]), len(case.reader.repos[FE.ENGINEERING_ID]["prs"])), state_before, "repository writes by the verifier")
    need(all(c[0] in ("start", "finish") for c in pub.calls), pub.calls)
    return f"{title}; check calls: {sorted(set(c[0] for c in pub.calls))} only"


# --- B4 ---------------------------------------------------------------------

@step("B4.1", "the owner pushes the export branch and the engineering pull request merges: the fresh clone has no workspace, and the released checker passes on it")
def _():
    n = no()
    stage("no.export")
    stage("no.published")
    clone = stage("no.clone")
    equal(L.workspace_root(clone)[0], None, "workspace reachable from the clone")
    need(not (clone / ".carrydown" / "local.yaml").exists())
    for extra in (["--view", "released"], []):
        r = run_script("check_specs.py", "--root", clone, "--report", *extra, cwd=clone)
        need(r.returncode == 0 and "0 finding(s)" in r.stdout, f"check_specs {' '.join(extra)}: {r.stdout[-400:]}{r.stderr[-200:]}")
    need("people overlay not loaded" in r.stdout, "the released clone should say the overlay is not loaded")


def section_text(rendering, number):
    """The text under the heading of one numbered section of a rendering: the lines after the heading up to the next heading."""
    lines = rendering.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^#{{2,6}} {re.escape(number)}( |$)", line):
            level = len(line) - len(line.lstrip("#"))
            out = []
            for later in lines[i + 1:]:
                m = re.match(r"^(#+) ", later)
                if m and len(m.group(1)) <= level:
                    break
                out.append(later)
            return "\n".join(x.rstrip() for x in out).strip("\n")
    raise AssertionError(f"section {number} is not in the rendering")


@step("B4.2", "the bundle of WI-06 holds every cited obligation as normalized verbatim text and the recorded decision, and no section that nothing cites")
def _():
    n = no()
    clone = stage("no.clone")
    md = (clone / "docs/context/wi-06.md").read_text(encoding="utf-8")
    side = read_json(clone / "docs/context/wi-06.bundle.json")
    cited = {(o["source"], o["section"]) for o in side["obligations"]}
    equal(cited, {("architecture", "3.5"), ("architecture", "4.1"), ("architecture", "7.1"), ("company-governance", "1.5"), ("company-governance", "2.3")}, "obligations")
    for source, number in sorted(cited):
        text = L.normalize_section_text(section_text((n.ws / "renderings" / f"{source}.md").read_text(encoding="utf-8"), number))
        need(text and text in md, f"the text of {source} {number} is not in the bundle")
    need("## Conflict resolution that applies" in md, "the recorded decision is missing")
    need("1.5" in md.split("## Conflict resolution that applies", 1)[1], "the decision does not name the conflicting section")
    all_cited = set()
    for sidecar in sorted((clone / "docs/context").glob("*.bundle.json")):
        data = read_json(sidecar)
        sections = {(o["source"], o["section"]) for o in data["obligations"]}
        all_cited |= sections
        text = sidecar.with_suffix("").with_suffix(".md").read_text(encoding="utf-8")
        headings = set(re.findall(r"(?m)^### (\S+) (\S+) ", text.split("## Conflict resolution", 1)[0].split("## Shared obligations", 1)[0]))
        need({(s, c) for s, c in headings} <= sections, f"{sidecar.name}: the Markdown holds a section its sidecar does not list")
    blob = {p.name: p.read_bytes() for p in (clone / "docs/context").glob("*.md")}
    equal(scan_text(blob, UNCITED_RESTRICTED), [], "uncited restricted text in a bundle")
    rendering = (n.ws / "renderings" / "architecture.md").read_text(encoding="utf-8")
    uncited = [num for num in re.findall(r"(?m)^#{2,6} (\d+(?:\.\d+)+) ", rendering) if ("architecture", num) not in all_cited]
    need(uncited, "every architecture section is cited by some bundle, so the check of unrelated sections has nothing to test")
    first = section_text(rendering, uncited[0]).strip().splitlines()[0] if section_text(rendering, uncited[0]).strip() else ""
    if len(first) > 30:
        equal(scan_text(blob, (first,)), [], f"the text of the uncited section {uncited[0]} in a bundle")


@step("B4.3", "a successful first fetch records the right repository, default branch revision and request id; the engineers' check passes")
def _():
    n = no()
    clone = stage("no.clone")
    script = skill_script(clone)
    code, text = check_context(script, clone, "WI-06", now=CLOCK0)
    need(code == 0 and "approved context for WI-06 is ready" in text, text)
    need("warning" not in text, text)
    record = read_json(clone / ".carrydown" / "cache" / "last-refresh")
    head = git(clone, "rev-parse", "origin/main").stdout.strip()
    equal(sorted(record), ["cache_format", "commit", "repository", "request_id", "time"], "record keys")
    equal(record["commit"], head, "default branch revision")
    equal(record["request_id"], n.rid, "request id")
    equal(record["repository"], str(n.origin)[:-len(".git")], "repository identity")
    equal(record["time"], CLOCK0.strftime("%Y-%m-%dT%H:%M:%SZ"), "recorded time (the fake clock)")
    return f"repository {record['repository'][-20:]} commit {record['commit'][:12]} request {record['request_id'][:12]} time {record['time']}"


@step("B4.4", "a failed first fetch grants no offline grace, and a record for another request or repository grants none either")
def _():
    n = no()
    source = stage("no.clone")
    fresh = S.tmp / "clone-first-fetch-fails"
    shutil.copytree(source, fresh)
    shutil.rmtree(fresh / ".carrydown" / "cache", ignore_errors=True)
    git(fresh, "remote", "set-url", "origin", S.tmp / "no-such-origin.git")
    code, text = check_context(skill_script(fresh), fresh, "WI-06", now=CLOCK0)
    need(code == 11 and "is stale" in text and "could-not-refresh" in text, text)
    need(not (fresh / ".carrydown" / "cache" / "last-refresh").exists(), "a failed fetch recorded a refresh")
    head = git(fresh, "rev-parse", "HEAD").stdout.strip()
    identity = str(S.tmp / "no-such-origin.git")[:-len(".git")]
    for label_, record in (("another request", {"cache_format": 1, "repository": identity, "commit": head, "request_id": "0" * 64, "time": CLOCK0.strftime("%Y-%m-%dT%H:%M:%SZ")}),
                           ("another repository", {"cache_format": 1, "repository": "elsewhere/repo", "commit": head, "request_id": n.rid, "time": CLOCK0.strftime("%Y-%m-%dT%H:%M:%SZ")}),
                           ("a future time", {"cache_format": 1, "repository": identity, "commit": head, "request_id": n.rid, "time": "2027-12-31T00:00:00Z"})):
        (fresh / ".carrydown" / "cache").mkdir(parents=True, exist_ok=True)
        (fresh / ".carrydown" / "cache" / "last-refresh").write_text(json.dumps(record), encoding="utf-8")
        code, text = check_context(skill_script(fresh), fresh, "WI-06", now=CLOCK0)
        need(code == 11 and "could-not-refresh" in text, f"{label_}: {text}")


# ---------------------------------------------------------------------------
# The shared lifecycle and adversarial continuation
# ---------------------------------------------------------------------------

S.flows = {"yes": yes, "no": no}
SECOND_EXPIRES = "2027-03-01T00:00:00Z"
OLD_LIMIT, NEW_LIMIT = "| Department head | Up to 25,000.00 |", "| Department head | Up to 30,000.00 |"


def cstage(f, name, build):
    return S.once(f"{f.path}.{name}", build)


def events_of(f):
    """The event batches of the project in the order they took effect."""
    if f.path == "yes":
        return list(V.local_events(str(f.ws)))
    return list(V.replay_staging(f.reader, f.world.enrollment()).events)


def receipts_of_export(f, rid):
    """{request id: receipt} of docs/release/ in what the last export wrote: the working tree on the yes path, the export branch on the no path."""
    out = {}
    if f.path == "yes":
        for p in sorted((f.root / "docs" / "release").glob("*.receipt.json")):
            out[p.name.split(".")[0]] = RS.loads_strict(p.read_bytes())
    else:
        for path, (_mode, data) in read_tree(f.root, f"carrydown/request-{rid}").items():
            if path.startswith("docs/release/"):
                out[path.split("/")[-1].split(".")[0]] = RS.loads_strict(data)
    return out


def history_baseline(f, rid):
    """The bytes of the approval history of a request that must never change: its snapshot, manifest, request and the events so far."""
    request = R.load_request(f.ws, rid)
    base = {}
    for rel in (Path("releases") / request["release_id"], Path("requests") / rid / "approval-request.json", Path("events")):
        target = f.ws / rel
        if target.is_dir():
            for p in sorted(target.rglob("*")):
                if p.is_file():
                    base[p.relative_to(f.ws).as_posix()] = p.read_bytes()
        elif target.is_file():
            base[rel.as_posix()] = target.read_bytes()
    if f.path == "no":
        tip = f.reader.repos[FE.STAGING_ID]["branches"]["main"]
        tree = f.reader.repos[FE.STAGING_ID]["commits"][tip]["tree"]
        for p, (_mode, data) in tree.items():
            if p.startswith(f"releases/{request['release_id']}/") or p.startswith(f"requests/{rid}/") or p.startswith("events/"):
                base["staging:" + p] = data
    return base


def c1_prepare(f):
    """Everything C1 needs, in order: the baseline, the edit, the diff, the new request."""
    stage(f"{f.path}.clone")        # the first release is exported, published, and an engineer holds a clone of it
    first = f.rids[0]
    base = history_baseline(f, first)
    f.edit_source(OLD_LIMIT, NEW_LIMIT)
    diff = f.diff()
    code, out, err = f.prepare("--expires", SECOND_EXPIRES)
    return {"first": first, "base": base, "diff": diff, "prepare": (code, out, err), "second": f.rid if code == 0 else None}


@step("C1.1", "after a cited source changes in the owner's workspace, diff names the affected work item and the changed scope", flows=("yes", "no"))
def _(f):
    c = cstage(f, "c1", lambda: c1_prepare(f))
    code, out, err = c["diff"]
    need(code == 0, out + err)
    need("Work items affected: WI-06" in out, "the affected work items: " + last(out, 6))
    need(re.search(r"changed: .*docs/context/wi-06", out), "the changed bundle is not listed")
    need("Scope changes:" in out, "no scope line: " + last(out, 4))
    other = [line for line in out.splitlines() if re.match(r"\s+changed: .*docs/context/wi-0[^6]", line)]
    equal(other, [], "bundles of other work items reported as changed")


@step("C1.2", "a new request supersedes the first: same project, other content, other nonce, with the approved expiry in its template", flows=("yes", "no"))
def _(f):
    c = cstage(f, "c1", lambda: c1_prepare(f))
    code, out, err = c["prepare"]
    need(code == 0, out + err)
    first, second = R.load_request(f.ws, c["first"]), R.load_request(f.ws, c["second"])
    equal(second["supersedes_request_id"], c["first"], "supersedes")
    need(second["release_id"] != first["release_id"], "the release id did not change with the content")
    need(second["request_nonce"] != first["request_nonce"], "the nonce was reused")
    equal(second["receipt_template"]["expires_at"], SECOND_EXPIRES, "approved expiry")


def c1_activate(f):
    c = cstage(f, "c1", lambda: c1_prepare(f))
    f.activate(c["second"])
    return events_of(f)


@step("C1.3", "approving the replacement is one reviewed batch: the first request becomes superseded and the second active, atomically", flows=("yes", "no"))
def _(f):
    c = cstage(f, "c1", lambda: c1_prepare(f))
    events = cstage(f, "c1.activate", lambda: c1_activate(f))
    batch = events[-1]
    equal([(t["request_id"], t["from"], t["to"], t["replacement_request_id"]) for t in batch["transitions"]],
          [(c["first"], "active", "superseded", c["second"]), (c["second"], "prepared", "active", None)], "the batch")
    replay = f.replay()
    equal((replay.requests[c["first"]].state, replay.requests[c["second"]].state, replay.active), ("superseded", "active", c["second"]), "replayed states")
    return f"one batch {batch['event_id'][:12]}: {c['first'][:8]} active -> superseded, {c['second'][:8]} prepared -> active"
    if f.path == "no":
        pr = [p for p in f.reader.repos[FE.STAGING_ID]["prs"].values() if p["head"]["ref"] == f"request/{c['second']}"][0]
        equal((pr["user"]["login"], pr["reviews"][-1]["user"]["id"]), ("github-actions[bot]", FE.OWNER[0]), "request author and reviewer")


def c1_export(f):
    c = cstage(f, "c1", lambda: c1_prepare(f))
    cstage(f, "c1.activate", lambda: c1_activate(f))
    code, out, err = f.export(c["second"])
    need(code == 0, out + err)
    receipts = receipts_of_export(f, c["second"])
    cstage(f, "c2.copies", lambda: make_old_copies(f, c["second"]))
    f.publish_release(c["second"])
    return receipts


@step("C1.4", "export writes the new active receipt and regenerates the prior receipt as terminal (superseded)", flows=("yes", "no"))
def _(f):
    c = cstage(f, "c1", lambda: c1_prepare(f))
    receipts = cstage(f, "c1.export", lambda: c1_export(f))
    first, second = receipts[c["first"]], receipts[c["second"]]
    equal((first["state"], first["superseded_by"], second["state"], second["supersedes"]), ("superseded", c["second"], "active", c["first"]), "receipts")
    equal(second["expires_at"], SECOND_EXPIRES, "receipt expiry")
    record = f.record(c["first"]) if f.path == "no" else f.records(c["first"])[0]
    state = f.replay().requests[c["first"]]
    approval = record.approval
    RS.verify_receipt_bytes(RS.canonical_json(first), record.request, record.manifest_bytes, state, approval)


@step("C1.5", "the original approval and snapshot history stay immutable: every byte of the first release, request and events is unchanged", flows=("yes", "no"))
def _(f):
    c = cstage(f, "c1", lambda: c1_prepare(f))
    cstage(f, "c1.export", lambda: c1_export(f))
    now = history_baseline(f, c["first"])
    for path, data in c["base"].items():
        need(path in now, f"{path} was removed")
        need(now[path] == data, f"{path} was changed")


# --- C2 ---------------------------------------------------------------------

def make_old_copies(f, second):
    """Two copies of the old clone with a good refresh recorded at CLOCK0, made before the replacement reaches the origin. The old
    clone was made when the first release was published, so it holds the first release only."""
    old = f.old_clone()
    need(not (old / "docs" / "release" / f"{second}.receipt.json").exists(), "the old clone already holds the replacement")
    code, text = check_context(skill_script(old), old, "WI-06", now=CLOCK0)
    need(code == 0 and "ready" in text, "the old clone was not valid before the change: " + text)
    for name in ("clone-online", "clone-offline"):
        shutil.copytree(old, S.tmp / f"{f.path}-{name}")
    return S.tmp / f"{f.path}-clone-online", S.tmp / f"{f.path}-clone-offline"


@contextlib.contextmanager
def origin_away(f):
    """The origin is unavailable for a while: its folder moves away, and the address every clone holds stays the same."""
    away = Path(str(f.origin) + ".away")
    os.rename(str(f.origin), str(away))
    try:
        yield
    finally:
        os.rename(str(away), str(f.origin))


def old_copies(f):
    cstage(f, "c1.export", lambda: c1_export(f))
    return S.memo[f"{f.path}.c2.copies"][1]


@step("C2.1", "from an old clone, a successful refresh sees the supersession and blocks the old context with the stale message", flows=("yes", "no"))
def _(f):
    online, _offline = old_copies(f)
    code, text = check_context(skill_script(online), online, "WI-06", now=CLOCK0)
    need(code == 11 and "carrydown: the approved context for WI-06 is stale" in text and "superseded" in text, text)
    need(f.rids[1] not in text and "30,000" not in text, "the stale message holds more than the fixed words")
    return "exit 11: " + " | ".join(text.strip().splitlines()[:2])


@step("C2.2", "with the origin unavailable and a valid matching earlier refresh inside the grace period, local validity is allowed with a warning", flows=("yes", "no"))
def _(f):
    _online, offline = old_copies(f)
    record = read_json(offline / ".carrydown" / "cache" / "last-refresh")
    equal(record["request_id"], cstage(f, "c1", lambda: c1_prepare(f))["first"], "the recorded refresh names the first request")
    with origin_away(f):
        code, text = check_context(skill_script(offline), offline, "WI-06", now=CLOCK0 + dt.timedelta(days=3))
        need(code == 0 and "warning: freshness not confirmed; within offline grace" in text, text)
        need("superseded" not in text, "an offline clone cannot know an event it has not fetched")
        offline_line = text.strip().splitlines()[-1]
    code, text = check_context(skill_script(offline), offline, "WI-06", now=CLOCK0 + dt.timedelta(days=3))
    need(code == 11 and "superseded" in text, "once the origin is back the supersession is seen: " + text)
    return f"offline inside grace: exit 0, {offline_line}; origin back: exit 11 superseded"


@step("C2.3", "outside the grace period, or with no valid refresh record, the offline clone is blocked with could not refresh", flows=("yes", "no"))
def _(f):
    _online, offline = old_copies(f)
    cache = offline / ".carrydown" / "cache" / "last-refresh"
    saved = cache.read_bytes()
    with origin_away(f):
        code, text = check_context(skill_script(offline), offline, "WI-06", now=CLOCK0 + dt.timedelta(days=3))
        need(code == 0 and "within offline grace" in text, "control, inside grace: " + text)
        code, text = check_context(skill_script(offline), offline, "WI-06", now=CLOCK0 + dt.timedelta(days=8))
        need(code == 11 and "could-not-refresh" in text, "outside grace: " + text)
        cache.unlink()
        code, text = check_context(skill_script(offline), offline, "WI-06", now=CLOCK0 + dt.timedelta(days=1))
        need(code == 11 and "could-not-refresh" in text, "no record: " + text)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(b"{not json")
        code, text = check_context(skill_script(offline), offline, "WI-06", now=CLOCK0 + dt.timedelta(days=1))
        need(code == 11 and "could-not-refresh" in text, "malformed record: " + text)
        forged = json.loads(saved)
        forged["request_id"] = "0" * 64
        cache.write_text(json.dumps(forged), encoding="utf-8")
        code, text = check_context(skill_script(offline), offline, "WI-06", now=CLOCK0 + dt.timedelta(days=1))
        need(code == 11 and "could-not-refresh" in text, "a record of another request: " + text)
        cache.write_bytes(saved)


@step("C2.4", "approved expiry is exercised on the local clock: ready before expires_at, stale with the reason expired after it", flows=("yes", "no"))
def _(f):
    cstage(f, "c1.export", lambda: c1_export(f))
    clone = cstage(f, "c2.fresh", lambda: f.clone(f"{f.path}-clone-current"))
    second = cstage(f, "c1", lambda: c1_prepare(f))["second"]
    receipt = RS.loads_strict((clone / "docs" / "release" / f"{second}.receipt.json").read_bytes())
    equal(receipt["expires_at"], SECOND_EXPIRES, "expires_at")
    code, text = check_context(skill_script(clone), clone, "WI-06", now=CLOCK0)
    need(code == 0 and "ready" in text, "before expiry: " + text)
    code, text = check_context(skill_script(clone), clone, "WI-06", now=dt.datetime(2027, 3, 2, 0, 0, 0, tzinfo=dt.timezone.utc))
    need(code == 11 and "expired" in text, "after expiry: " + text)
    code, text = check_context(skill_script(clone), clone, "WI-06", now=dt.datetime(2027, 2, 28, 23, 59, 59, tzinfo=dt.timezone.utc))
    need(code == 0, "one second before expiry: " + text)
    return f"expires_at {SECOND_EXPIRES}: ready at 2027-02-01 and 2027-02-28T23:59:59, stale (expired) at 2027-03-02"


# --- C3 ---------------------------------------------------------------------

REPO = "sct-will/carrydown-sample"


def writes(log):
    """The mock requests that changed something: REST writes, and GraphQL mutations (a GraphQL query is a read)."""
    return [(m, p) for m, p in log if m != "GET" and p != "/graphql"] + [("GRAPHQL", op) for op in mockgh.S.gql if op in mockgh.MUTATIONS]


class MockGH:
    """The loopback GitHub of tests/mock/mockgh.py with a placeholder token that exists only in this process. It is the only
    network the scenarios open, and only for the publishers of the yes path."""

    def __enter__(self):
        mockgh.S.__init__()
        mockgh.S.repos.add(REPO)
        mockgh.S.repo_ids = {REPO: 4200}
        self.server, self.url = mockgh.start()
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(mock.patch.dict(os.environ, {"CARRYDOWN_GITHUB_TOKEN": "ghp_" + "Z" * 36}))
        self.stack.enter_context(mock.patch.object(time, "sleep", lambda s: None))
        self.stack.enter_context(mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"))
        self.stack.enter_context(mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None)))
        return self

    def __exit__(self, *exc):
        self.stack.close()
        self.server.shutdown()
        self.server.server_close()

    def issue_count(self):
        return len(mockgh.S.issues)


def refusal_code(call, *args, **kwargs):
    try:
        call(*args, **kwargs)
    except RS.SchemaError as e:
        return e.code
    raise AssertionError("no refusal")


def c3_retire(f):
    c = cstage(f, "c1", lambda: c1_prepare(f))
    cstage(f, "c1.export", lambda: c1_export(f))
    second = c["second"]
    ws_before = tree_state(f.ws)
    heads = ls_heads(f.staging) if f.path == "no" else None
    code, out, err = f.withdraw(second, apply=False)
    need(code == 0 and "Dry run" in out, "withdraw without --apply: " + out + err)
    equal(tree_state(f.ws), ws_before, "the workspace after the withdraw dry run")
    if f.path == "no":
        equal(ls_heads(f.staging), heads, "the staging repository after the withdraw dry run")
    f.k -= 1        # the dry run drew a time stamp; the apply uses the same one
    number = f.retire(second)
    return {"second": second, "number": number}


@step("C3.1", "the active request is withdrawn: the terminal event is authenticated and merged, and replay shows it withdrawn with nothing active", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c3", lambda: c3_retire(f))
    replay = f.replay()
    equal((replay.requests[r["second"]].state, replay.active), ("withdrawn", None), "replayed state")
    batch = events_of(f)[-1]
    equal([(t["request_id"], t["from"], t["to"], t["reason_code"]) for t in batch["transitions"]], [(r["second"], "active", "withdrawn", "error-found")], "terminal batch")
    if f.path == "no":
        pr = f.reader.repos[FE.STAGING_ID]["prs"][r["number"]]
        equal((pr["head"]["ref"], pr["user"]["login"], pr["reviews"][-1]["user"]["id"]), (f"state/{batch['event_id']}", "github-actions[bot]", FE.OWNER[0]), "state pull request")
    return f"event {batch['event_id'][:12]}: {r['second'][:8]} active -> withdrawn (error-found); active request: none"


@step("C3.2", "after the withdrawal every content publisher refuses, and none of them writes", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c3", lambda: c3_retire(f))
    second = r["second"]
    before = tree_state(f.root)
    code, out, err = f.export(second)
    need(code == 1 and "withdrawn" in err, "release.py export: " + out + err)
    equal(tree_state(f.root), before, "the working tree after the refused export")
    if f.path == "yes":
        with MockGH():
            before_writes = len(writes(mockgh.S.log))
            code, out, err = F.run(GS.run, ["--root", str(f.root), "--skip-check", "--apply"])
            need(code != 0 and re.search("withdrawn|not-approved", out + err), "github_sync.py --apply: " + out + err)
            code, out, err = F.run(GP.run, ["--root", str(f.root), "--apply"])
            need(code != 0 and re.search("withdrawn|not-approved", out + err), "github_project.py --apply: " + out + err)
            code, out, err = F.run(GR.run, ["--root", str(f.root), "--before", "docs/spec/plan.yaml", "--apply"])
            need(code != 0 and re.search("withdrawn|not-approved", out + err), "github_repair.py --apply: " + out + err)
            equal(len(writes(mockgh.S.log)), before_writes, "GitHub writes")
            equal(mockgh.S.issues, [], "issues created")
    else:
        record = f.record(second)
        enrollment = f.world.enrollment()
        targets = V.verify_targets(f.reader, enrollment, record.request["receipt_template"]["targets"], record.request["receipt_template"]["audience"])
        equal(refusal_code(V.authorize_content, record, f.replay(), enrollment, targets), "withdrawn", "content authorization of the withdrawn request")
        first_record = f.record(c1_prepare_cached(f)["first"])
        equal(refusal_code(V.authorize_content, first_record, f.replay(), enrollment, targets), "superseded", "content authorization of the superseded request")
        decision = RG.check("release", SPEC_FILE, "0" * 64, "engineering-repo", str(f.root), request_id=second)
        need(not decision.allowed, f"the gate allowed a release-class write: {decision}")
        return f"withdrawn: {decision.code}; superseded: refused; export refused with withdrawn; release-class gate decision: deny({decision.code})"
    return "export, github_sync, github_project and github_repair refused; GitHub writes 0; issues 0"


def c1_prepare_cached(f):
    return cstage(f, "c1", lambda: c1_prepare(f))


def engineering_from_origin(f):
    """The fictional engineering repository holding what the origin's default branch holds now, ready for a pull request against it.
    Returns (case, the files of the default branch)."""
    tree = read_tree(f.root, "origin/main")
    pointer = tree.pop(POINTER)[1]
    for plain in ("README.md", ".gitignore"):
        tree.pop(plain, None)
    case = EF.Case(Exported(f.world, "0" * 64, {}, pointer))
    tip = case.reader.repos[FE.ENGINEERING_ID]["branches"]["main"]
    case.reader.commit(FE.ENGINEERING_ID, {path: (mode, data) for path, (mode, data) in tree.items()}, [tip], branch="main")
    return case, tree


def flaky_write(*a, **k):
    raise OSError("the disk went away")


def c3_state_export(f):
    """The receipt update of the withdrawn request: a dry run, a first attempt that the disk interrupts, and the resumed run."""
    r = cstage(f, "c3", lambda: c3_retire(f))
    second = r["second"]
    events_before = len(events_of(f))
    pending = f.clone(f"{f.path}-clone-pending")
    pending_check = check_context(skill_script(pending), pending, "WI-06", now=CLOCK0)
    if f.path == "no":
        git(f.root, "fetch", "-q", "origin")
    before = tree_state(f.root)
    dry = f.export_state(second, apply=False)
    after_dry = tree_state(f.root)
    interrupted = False
    with mock.patch.object(R, "write_file", flaky_write):
        try:
            f.export_state(second)
        except OSError:
            interrupted = True
    events_interrupted = len(events_of(f))
    resume = f.export_state(second)       # the repeated command finishes the branch the interrupted run left, by itself
    final = resume
    return {"second": second, "dry": dry, "before": before, "after_dry": after_dry, "interrupted": interrupted, "resume": resume,
            "apply": final, "after": tree_state(f.root), "events_before": events_before, "events_interrupted": events_interrupted,
            "events_after": len(events_of(f)), "pending": pending, "pending_check": pending_check}


@step("C3.3", "state-only export succeeds: it regenerates only the receipt of the withdrawn request, and the engineering verification passes", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c3.state", lambda: c3_state_export(f))
    second = r["second"]
    receipt_path = f"docs/release/{second}.receipt.json"
    code, out, err = r["dry"]
    need(code == 0 and "Only its receipt will be rewritten" in out, out + err)
    equal(r["before"], r["after_dry"], "files after the export-state dry run")
    code, out, err = r["apply"]
    need(code == 0, out + err)
    if f.path == "yes":
        changed = sorted(p for p in r["after"] if r["before"].get(p) != r["after"][p])
        equal(changed, [receipt_path], "files changed by export-state")
        equal(f.receipt(second)["state"], "withdrawn", "receipt state")
    else:
        branch = f"carrydown/state-{second}"
        changed = git(f.root, "diff", "--name-only", f"origin/main...{branch}").stdout.split()
        equal(changed, [receipt_path], "files changed by export-state")
        receipt = RS.loads_strict(git(f.root, "show", f"{branch}:{receipt_path}").stdout.encode())
        equal(receipt["state"], "withdrawn", "receipt state")
        case, tree = engineering_from_origin(f)
        number = case.reader.open_pr(FE.ENGINEERING_ID, "state-export", {receipt_path: ("100644", git(f.root, "show", f"{branch}:{receipt_path}").stdout.encode())},
                                     user=FE.OWNER)
        conclusion, title, _p, _r = verdict(case.world, number)
        equal((conclusion, title), ("success", "carrydown: release verified"), "verifier on the receipt-only pull request")
        return f"changed files {changed}; verifier on the receipt-only pull request: {conclusion} ({title})"
    return f"changed files {changed}; receipt state withdrawn"


@step("C3.4", "adding a specification to the same state-only request fails", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c3.state", lambda: c3_state_export(f))
    second = r["second"]
    receipt_path = f"docs/release/{second}.receipt.json"
    if f.path == "yes":
        record, replay = f.records(second)
        policy = V.local_policy({k: v for k, v in R.Project(f.root).handling.items() if k in L.RELEASED_HANDLING_KEYS}, "sct-will/carrydown-sample")
        digest = RS.sha256_bytes((f.root / receipt_path).read_bytes())
        ctx = V.authorize_state_receipt(record, replay, policy, {receipt_path: digest})
        d = RG.check("state-only", SPEC_FILE, RS.sha256_file(f.root / SPEC_FILE), "engineering-repo", str(f.root), verified_context=ctx)
        equal((d.allowed, d.code), (False, "state-only-content-write"), "gate decision for a spec in a state-only write")
        d = RG.check("state-only", receipt_path, digest, "engineering-repo", str(f.root), verified_context=ctx)
        need(d.allowed, "the gate refused the receipt itself")
        equal(refusal_code(V.authorize_state_receipt, record, replay, policy, {receipt_path: digest, SPEC_FILE: "0" * 64}), "state-only-content-write", "context for a receipt plus a spec")
        return "gate: a specification in a state-only write is deny(state-only-content-write); the receipt itself is allowed"
    else:
        branch = f"carrydown/state-{second}"
        case, tree = engineering_from_origin(f)
        receipt = git(f.root, "show", f"{branch}:{receipt_path}").stdout.encode()
        spec = tree[SPEC_FILE][1] + b"\nAn extra sentence that nobody approved.\n"
        number = case.reader.open_pr(FE.ENGINEERING_ID, "state-plus-spec", {receipt_path: ("100644", receipt), SPEC_FILE: ("100644", spec)}, user=FE.OWNER)
        conclusion, title, _p, _r = verdict(case.world, number)
        need(conclusion == "failure" and re.fullmatch(r"carrydown: [a-z-]+", title), f"{conclusion} {title}")
        control = case.reader.open_pr(FE.ENGINEERING_ID, "state-only", {receipt_path: ("100644", receipt)}, user=FE.OWNER)
        equal(verdict(case.world, control)[:2], ("success", "carrydown: release verified"), "the same receipt without the specification")
        record = f.record(second)
        policy = f.world.enrollment()
        replay = f.replay()
        equal(refusal_code(V.authorize_state_receipt, record, replay, policy, {receipt_path: "0" * 64, SPEC_FILE: "0" * 64}), "state-only-content-write", "context for a receipt plus a spec")
        return f"verifier on receipt plus specification: {conclusion} ({title}); the receipt alone passes; context for both: state-only-content-write"


@step("C3.5", "an interruption after the terminal event is merged but before the receipt update is published is reported as pending: engineers still see the active receipt and no event is added", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c3.state", lambda: c3_state_export(f))
    code, text = r["pending_check"]
    need(code == 0 and "ready" in text, "engineers fetch the default branch, which still shows the active receipt: " + text)
    code, out, err = r["dry"]
    need(code == 0 and "Only its receipt will be rewritten" in out, out + err)
    need("Dry run: nothing was written" in out or "Would commit the regenerated receipt on carrydown/state-" in out, "the pending update is not reported: " + out)
    need(r["interrupted"], "the interruption did not happen")
    equal(r["events_interrupted"], r["events_before"], "events after the interruption")
    return "engineers fetch a default branch that still shows the active receipt (exit 0); the dry run reports the update as not yet written; the interrupted run added no event"


@step("C3.6", "the interrupted receipt update resumes without a new event, and once it reaches the default branch engineers see the withdrawal",
      flows=("yes", "no"))
def _(f):
    r = cstage(f, "c3.state", lambda: c3_state_export(f))
    try:
        code, out, err = r["resume"]
        need(code == 0, "the repeated command refused: " + (err.strip().splitlines() or [out])[-1])
        equal(r["events_after"], r["events_before"], "events after the resume")
        if f.path == "no":
            equal(git(f.root, "branch", "--list", "carrydown/state-*").stdout.split(), [f"carrydown/state-{r['second']}"], "state branches")
    finally:
        cstage(f, "c3.publish", lambda: f.publish_state(r["second"]))


@step("C3.7", "once the receipt update reaches the default branch, the engineers' check reports the withdrawal", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c3.state", lambda: c3_state_export(f))
    cstage(f, "c3.publish", lambda: f.publish_state(r["second"]))
    code, text = check_context(skill_script(r["pending"]), r["pending"], "WI-06", now=CLOCK0)
    need(code == 11 and "withdrawn" in text, text)
    need("30,000" not in text and r["second"] not in text, "the message holds more than the fixed words")
    return "exit 11: " + " | ".join(text.strip().splitlines()[:2])


# --- C4 ---------------------------------------------------------------------

def request_of(f, rid):
    return R.load_request(f.ws, rid)


def c4_run(f):
    """After the withdrawal: the same content for another audience, then a reapproval of the withdrawn scope."""
    c3 = cstage(f, "c3", lambda: c3_retire(f))
    cstage(f, "c3.state", lambda: c3_state_export(f))
    cstage(f, "c3.publish", lambda: f.publish_state(c3["second"]))
    second = c3["second"]
    base = {"second_request_bytes": (f.ws / "requests" / second / "approval-request.json").read_bytes(), "events_before": len(events_of(f))}
    code, out, err = f.prepare("--audience", "public")
    need(code == 0, "prepare for another audience: " + out + err)
    third = f.rid
    f.activate(third)
    events_third = list(events_of(f))
    f.retire(third)
    code, out, err = f.prepare("--expires", SECOND_EXPIRES, fresh=False)      # no --nonce and no --created: the command draws a fresh nonce
    need(code == 0, "prepare after the withdrawal: " + out + err)
    fourth = f.rid
    f.activate(fourth)
    if f.path == "yes":
        code, out, err = f.export(fourth)
        need(code == 0, out + err)
    return {"second": second, "third": third, "fourth": fourth, "base": base, "events_third": events_third}


@step("C4.1", "identical content approved for a different audience has the same release id and another request id, and the withdrawn request stays withdrawn", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c4", lambda: c4_run(f))
    second, third = request_of(f, r["second"]), request_of(f, r["third"])
    equal(third["release_id"], second["release_id"], "release id")
    need(third["request_sha256"] != second["request_sha256"], "the request ids are the same")
    equal((second["receipt_template"]["audience"], third["receipt_template"]["audience"]), ("repo-readers", "public"), "audiences")
    need(third["request_nonce"] != second["request_nonce"], "the nonce was reused")
    equal(third["supersedes_request_id"], None, "a withdrawn request is not superseded")
    replay = f.replay()
    equal((replay.requests[r["second"]].state, replay.requests[r["third"]].state), ("withdrawn", "withdrawn"), "states once both are withdrawn")
    activated = r["events_third"][-1]
    equal([(t["request_id"], t["from"], t["to"]) for t in activated["transitions"]], [(r["third"], "prepared", "active")], "activation of the other-audience request")
    return f"release id {second['release_id'][:12]} for both; request ids {second['request_sha256'][:8]} (repo-readers) and {third['request_sha256'][:8]} (public)"


@step("C4.2", "approval lookup is unambiguous and terminal history is preserved: each request id finds its own approval, and no earlier byte changed", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c4", lambda: c4_run(f))
    ids = (r["second"], r["third"], r["fourth"])
    equal(len(set(ids)), 3, "three distinct request ids")
    for rid in ids:
        record = f.record(rid) if f.path == "no" else f.records(rid)[0]
        equal(record.request_id, rid, "the approval found for a request id")
        equal(record.request["request_sha256"], rid, "the request found for a request id")
    equal(request_of(f, r["fourth"])["release_id"], request_of(f, r["second"])["release_id"], "release id after the reapproval")
    equal((f.ws / "requests" / r["second"] / "approval-request.json").read_bytes(), r["base"]["second_request_bytes"], "the first request bytes")
    replay = f.replay()
    equal({rid: replay.requests[rid].state for rid in ids}, {r["second"]: "withdrawn", r["third"]: "withdrawn", r["fourth"]: "active"}, "states")
    equal(replay.active, r["fourth"], "the one active request")
    names = [t["request_id"] for e in events_of(f) for t in e["transitions"]]
    equal((names.count(r["second"]), names.count(r["third"]), names.count(r["fourth"])), (2, 2, 1), "transitions per request (activation and withdrawal)")


@step("C4.3", "reapproval after withdrawal gets a fresh nonce: the same approved scope gives another request id, and the withdrawn one does not return", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c4", lambda: c4_run(f))
    second, fourth = request_of(f, r["second"]), request_of(f, r["fourth"])
    strip = lambda t: {k: v for k, v in t.items() if k != "created"}      # noqa: E731
    equal(strip(fourth["receipt_template"]), strip(second["receipt_template"]), "the approved scope")
    need(fourth["request_nonce"] != second["request_nonce"], "the nonce was reused")
    need(fourth["request_sha256"] != second["request_sha256"], "the same request id")
    equal(f.replay().requests[r["second"]].state, "withdrawn", "the first request")
    # a terminal request never becomes active again, even when an event tries it
    tip = f.replay().tip
    policy = f.world.enrollment() if f.path == "no" else V.local_policy({k: v for k, v in R.Project(f.root).handling.items() if k in L.RELEASED_HANDLING_KEYS}, "sct-will/carrydown-sample")
    back = B.build_event([B.transition(r["second"], "prepared", "active", tip, "release-approved")], policy, created="2027-02-01T00:00:00Z", nonce=nonce(900))
    events = events_of(f) + [back]
    equal(refusal_code(RS.replay_state, events), "state-history-invalid", "a terminal request returning to active")


def mutate(value):
    """A different value of the same kind."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return ("0" if not value.startswith("0") else "1") + value[1:] if value else "x"
    if isinstance(value, list):
        return value[:-1] if value else ["x"]
    if isinstance(value, dict):
        return dict(value, unexpected_field="x")
    return "x"


def request_mutations(request):
    """(name, mutated request) for each field of the request and each field of its template and targets, one at a time."""
    for key in RS.REQUEST_KEYS:
        if key == "request_sha256":
            continue
        out = dict(request)
        out[key] = mutate(request[key])
        yield f"request.{key}", out
    out = dict(request)
    out["unknown_field"] = "x"
    yield "request.unknown_field", out
    for key in RS.TEMPLATE_KEYS:
        out = json.loads(json.dumps(request))
        out["receipt_template"][key] = mutate(request["receipt_template"][key])
        yield f"receipt_template.{key}", out
    for key in request["receipt_template"]["targets"][0]:
        out = json.loads(json.dumps(request))
        out["receipt_template"]["targets"][0][key] = mutate(request["receipt_template"]["targets"][0][key])
        yield f"targets[0].{key}", out


def tampered_reader(reader, repo_id, path, new_bytes):
    """A copy of the model of GitHub in which every revision that holds the file holds new bytes instead."""
    copy_ = copy.deepcopy(reader)
    repo = copy_.repos[repo_id]
    for commit in repo["commits"].values():
        if path in commit["tree"]:
            commit["tree"][path] = (commit["tree"][path][0], new_bytes)
    repo["blobs"][FE.blob_sha(new_bytes)] = new_bytes
    return copy_


@step("C4.4", "an attempted mutation of one request, template or target field, taken one at a time, no longer verifies", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c4", lambda: c4_run(f))
    rid = r["fourth"]
    request = request_of(f, rid)
    seen = {}
    if f.path == "yes":
        path = f.ws / "requests" / rid / "approval-request.json"
        original = path.read_bytes()
        try:
            for name, mutated in request_mutations(request):
                path.write_bytes(json.dumps(mutated, sort_keys=True).encode("utf-8"))
                try:
                    V.verify_local_request(V.load_local_evidence(str(f.ws), rid), rid)
                    raise AssertionError(f"{name}: the mutated request verified")
                except RS.SchemaError as e:
                    seen[name] = e.code
        finally:
            path.write_bytes(original)
        V.verify_local_request(V.load_local_evidence(str(f.ws), rid), rid)
    else:
        enrollment = f.world.enrollment()
        path = f"requests/{rid}/approval-request.json"
        for name, mutated in request_mutations(request):
            reader = tampered_reader(f.reader, FE.STAGING_ID, path, json.dumps(mutated, sort_keys=True).encode("utf-8"))
            try:
                V.verify_request(rid, reader, enrollment)
                raise AssertionError(f"{name}: the mutated request verified")
            except RS.SchemaError as e:
                seen[name] = e.code
        V.verify_request(rid, f.reader, enrollment)
    need(len(seen) >= len(RS.TEMPLATE_KEYS) + len(RS.REQUEST_KEYS), f"only {len(seen)} mutations were tried")
    need(set(seen.values()) <= RG.REASON_CODES | {"schema-invalid"}, "a code outside the fixed set: " + str(sorted(set(seen.values()))))
    return f"{len(seen)} one-field mutations of the request, its template and its first target all refused; codes: {sorted(set(seen.values()))}"


@step("C4.5", "a changed audience or destination list in the stored request after approval makes export refuse, and restoring it lets export proceed (dry run)", flows=("yes",))
def _(f):
    r = cstage(f, "c4", lambda: c4_run(f))
    rid = r["fourth"]
    path = f.ws / "requests" / rid / "approval-request.json"
    original = path.read_bytes()
    request = json.loads(original)
    try:
        for field, value in (("audience", "public"), ("destinations", ["engineering-repo"])):
            changed = json.loads(original)
            changed["receipt_template"][field] = value
            path.write_text(json.dumps(changed), encoding="utf-8")
            code, out, err = f.export(rid, apply=False)
            need(code == 1 and "approval-scope-mismatch" in err, f"{field}: {out}{err}")
    finally:
        path.write_bytes(original)
    equal(f.export(rid, apply=False)[0], 0, "export after restoring the request")
    need(request["receipt_template"]["audience"] == "repo-readers")


def receipt_mutations(receipt):
    for key in RS.RECEIPT_KEYS:
        out = dict(receipt)
        out[key] = mutate(receipt[key]) if receipt[key] is not None else "x"
        yield f"receipt.{key}", out
    yield "receipt.unknown_field", dict(receipt, unknown_field="x")
    yield "receipt.artifact omitted", dict(receipt, artifacts=receipt["artifacts"][1:])
    yield "receipt.artifact mode", dict(receipt, artifacts=[dict(receipt["artifacts"][0], mode="100755")] + receipt["artifacts"][1:])
    yield "receipt.artifact bytes", dict(receipt, artifacts=[dict(receipt["artifacts"][0], bytes=receipt["artifacts"][0]["bytes"] + 1)] + receipt["artifacts"][1:])
    yield "receipt.target repository_id", dict(receipt, targets=[dict(receipt["targets"][0], repository_id=receipt["targets"][0]["repository_id"] + 1)] + receipt["targets"][1:])
    yield "receipt.state", dict(receipt, state="withdrawn" if receipt["state"] == "active" else "active")


def canonical_bytes_of(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


@step("C4.6", "an attempted mutation of one public receipt field, taken one at a time, differs from the exact projection and fails", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c4", lambda: c4_run(f))
    rid = r["fourth"]
    if f.path == "yes":
        record, replay = f.records(rid)
        receipt = f.receipt(rid)
        actual = (f.root / "docs" / "release" / f"{rid}.receipt.json").read_bytes()
    else:
        record = f.record(rid)
        replay = f.replay()
        state = replay.requests[rid]
        actual = RS.project_receipt(record.request, record.manifest_bytes, state, record.approval)
        receipt = RS.loads_strict(actual)
    RS.verify_receipt_bytes(actual, record.request, record.manifest_bytes, replay.requests[rid], record.approval)
    tried = 0
    for name, mutated in receipt_mutations(receipt):
        try:
            RS.verify_receipt_bytes(canonical_bytes_of(mutated), record.request, record.manifest_bytes, replay.requests[rid], record.approval)
        except RS.SchemaError:
            tried += 1
            continue
        raise AssertionError(f"{name}: the mutated receipt equals the projection")
    need(tried >= len(RS.RECEIPT_KEYS) + 4, f"only {tried} mutations were tried")
    return f"{tried} one-field mutations of the receipt (every public field, an unknown field, an omitted artifact, a mode, a byte count, a target id, the state) all differ from the projection"


@step("C4.7", "state mutations grant no authority: a mutable state file, a forged event author and a receipt that claims active for an ended request change nothing", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c4", lambda: c4_run(f))
    second = r["second"]
    state_file = f.ws / "requests" / second / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    saved = state_file.read_bytes() if state_file.exists() else None
    state_file.write_text(json.dumps({"request_id": second, "release_id": request_of(f, second)["release_id"], "state": "active", "event_id": "0" * 64, "staging_tip": "0" * 64}), encoding="utf-8")
    try:
        code, out, err = f.export(second, apply=False)
        need(code == 1 and "withdrawn" in err, "export trusted a state file: " + out + err)
        equal(f.replay().requests[second].state, "withdrawn", "replayed state")
    finally:
        if saved is None:
            state_file.unlink()
        else:
            state_file.write_bytes(saved)
    if f.path == "no":
        forged = {"events/" + "9" * 64 + ".json": b'{"by": "sct-will", "to": "active"}', "state.json": b'{"state": "active"}'}
        number = f.reader.open_pr(FE.STAGING_ID, "state/" + "9" * 64, forged)
        f.reader.review(FE.STAGING_ID, number, *FE.OWNER)
        report = V.verify_candidate(f.reader, f.world.enrollment(), number)
        need(not report.ok, "a forged event branch verified")
        f.reader.close(FE.STAGING_ID, number)
        equal(f.replay().active, r["fourth"], "the active request after the forged branch")
        exported = stage("no.frozen")
        case = EF.Case(exported)
        receipt = RS.loads_strict(exported.files[exported.receipt_path][1])
        # the frozen world is the first release, still active there; withdraw it in the copy and present a receipt that says active
        event = B.withdrawal_event(exported.rid, case.world.enrollment(), V.replay_staging(case.reader, case.world.enrollment()).replay.tip, "error-found",
                                   created=case.reader.tick(), nonce=B.new_nonce())
        case.world.land(B.state_branch_files(event), f"state/{event['event_id']}")
        number = case.open()
        conclusion, title, _p, _r = verdict(case.world, number)
        equal((conclusion, title), ("failure", "carrydown: withdrawn"), "verifier on a receipt that says active for a withdrawn request")
    else:
        tip = f.replay().tip
        policy = V.local_policy({k: v for k, v in R.Project(f.root).handling.items() if k in L.RELEASED_HANDLING_KEYS}, "sct-will/carrydown-sample")
        try:
            forged = B.build_event([B.transition(second, "withdrawn", "active", tip, "release-approved")], policy, created="2027-02-01T00:00:00Z", nonce=nonce(901))
            forged["transitions"][0]["by"] = "someone"
            RS.replay_state(events_of(f) + [forged])
        except RS.SchemaError:
            return "a forged terminal-to-active event with a by field is not replayed"
        raise AssertionError("a forged event was replayed")


@step("C4.8", "a destination whose numeric identity changed is refused before any write", flows=("no",))
def _(f):
    record = f.record(f.rids[-1])
    enrollment = f.world.enrollment()
    wanted = record.request["receipt_template"]["targets"]
    audience = record.request["receipt_template"]["audience"]
    V.verify_targets(f.reader, enrollment, wanted, audience)
    copy_ = copy.deepcopy(f.reader)
    copy_.projects["PVT_example"]["owner_id"] = 5555
    equal(refusal_code(V.verify_targets, copy_, enrollment, wanted, audience), "target-identity-mismatch", "board with another owner id")
    copy_ = copy.deepcopy(f.reader)
    copy_.projects["PVT_example"]["reader_ids"] = copy_.projects["PVT_example"]["reader_ids"] + [31337]
    equal(refusal_code(V.verify_targets, copy_, enrollment, wanted, audience), "audience-visibility-mismatch", "board with an extra reader")


# --- C5 ---------------------------------------------------------------------

def issue_by_key(key):
    return next(i for i in mockgh.S.issues if f"<!-- carrydown:{key} -->" in (i.get("body") or ""))


def c5_publish(f):
    """The yes-path publisher against the loopback GitHub: interrupted after the second write, resumed, read back, then a completed
    target is edited by hand."""
    r = cstage(f, "c4", lambda: c4_run(f))
    rid = r["fourth"]
    out = {"rid": rid}
    argv = ["--root", str(f.root), "--skip-check"]
    with MockGH():
        mockgh.S.fail[("POST", r"/repos/[^/]+/[^/]+/issues")] = [None, None, "401"]
        out["first"] = F.run(GS.run, argv + ["--apply"])
        out["issues_after_interruption"] = len(mockgh.S.issues)
        out["journal_after_interruption"] = RS.loads_strict((f.ws / "publication" / f"{rid}.journal.json").read_bytes())
        mockgh.S.fail.clear()
        out["resume"] = F.run(GS.run, argv + ["--apply"])
        out["titles"] = [i["title"] for i in mockgh.S.issues]
        out["journal"] = RS.loads_strict((f.ws / "publication" / f"{rid}.journal.json").read_bytes())
        out["writes_after_resume"] = len(writes(mockgh.S.log))
        out["verify"] = F.run(GS.run, argv + ["--verify"])
        out["rerun"] = F.run(GS.run, argv + ["--apply"])
        out["writes_after_rerun"] = len(writes(mockgh.S.log))
        issue = issue_by_key("WI-03")
        issue["body"] = issue["body"].replace("Target completion", "Target completion (edited by hand)", 1)
        out["tamper"] = F.run(GS.run, argv + ["--apply"])
        out["writes_after_tamper"] = len(writes(mockgh.S.log))
        out["tampered_body_kept"] = "(edited by hand)" in issue_by_key("WI-03")["body"]
        out["issue_count"] = len(mockgh.S.issues)
    return out


@step("C5.1", "issue publication interrupted after the second write resumes from the journal, reads every managed field back, and creates no duplicate", flows=("yes",))
def _(f):
    o = cstage(f, "c5", lambda: c5_publish(f))
    code, text, err = o["first"]
    need(code == 1, "the interrupted run did not stop: " + text + err)
    equal(o["issues_after_interruption"], 2, "issues after the interruption")
    started = {k for k, v in o["journal_after_interruption"]["targets"].items() if v["state"] == "started"}
    need(started, "the journal recorded nothing as started")
    code, text, err = o["resume"]
    need(code == 0, "the resume failed: " + text + err)
    equal(len(o["titles"]), 15, "issues after the resume")
    equal(len(o["titles"]), len(set(o["titles"])), "duplicate titles")
    targets = o["journal"]["targets"]
    need(targets and all(v["state"] == "completed" and re.fullmatch(r"[0-9a-f]{64}", v["managed_state_sha256"]) and v["request_id"] == o["rid"] for k, v in targets.items()
                         if not k.startswith("label/")), "a target is not completed with its managed state digest")
    equal(o["verify"][0], 0, "github_sync.py --verify (the read back): " + o["verify"][1][-200:])
    code, text, err = o["rerun"]
    need(code == 0, text + err)
    equal(o["writes_after_rerun"], o["writes_after_resume"], "writes by a rerun of a completed publication")
    return f"interrupted at {o['issues_after_interruption']} issues; resumed to {len(o['titles'])} with no duplicate title; --verify exit 0; a rerun made 0 writes"


@step("C5.2", "a hand edit of a completed target stops the publication for the owner: the run reports it, writes nothing and does not rewrite the item", flows=("yes",))
def _(f):
    o = cstage(f, "c5", lambda: c5_publish(f))
    code, text, err = o["tamper"]
    need(code == 1 and "target changed since publication: WI-03" in text + err, text + err)
    equal(o["writes_after_tamper"], o["writes_after_rerun"], "writes after the tamper")
    need(o["tampered_body_kept"], "the edited item was silently rewritten")
    equal(o["issue_count"], 15, "issues")
    return "target changed since publication: WI-03; GitHub writes after the stop: 0; the hand edit was not rewritten"


def competing_candidates(frozen):
    case = EF.Case(frozen)
    world, reader = case.world, case.reader
    enrollment = world.enrollment()
    tip = V.replay_staging(reader, enrollment).replay.tip
    a = FE.make_candidate(world, files={"repo/docs/spec/a.md": b"# A\n"}, destinations=("engineering-repo",), supersedes=frozen.rid, tip=tip)
    b = FE.make_candidate(world, files={"repo/docs/spec/b.md": b"# B\n"}, destinations=("engineering-repo",), supersedes=frozen.rid, tip=tip)
    na = world.land(a.files(), a.branch, approve=False, merge=False)
    nb = world.land(b.files(), b.branch, approve=False, merge=False)
    reader.review(FE.STAGING_ID, na, *FE.OWNER)
    reader.review(FE.STAGING_ID, nb, *FE.OWNER)
    both = []
    for number in (na, nb):
        conclusion, title, _p, _r = verdict(world, number, kind="staging")
        both.append(conclusion)
    reader.merge(FE.STAGING_ID, na)
    conclusion, title, pub, _r = verdict(world, nb, kind="staging")
    stale = (conclusion, title)
    rebuilt = FE.make_candidate(world, files={"repo/docs/spec/b.md": b"# B\n"}, destinations=("engineering-repo",), supersedes=a.rid, nonce=B.new_nonce())
    nr = world.land(rebuilt.files(), rebuilt.branch, approve=False, merge=False)
    before_review = verdict(world, nr, kind="staging")[:2]
    reader.review(FE.STAGING_ID, nr, *FE.OWNER)
    after_review = verdict(world, nr, kind="staging")[:2]
    return {"both": both, "stale": stale, "before_review": before_review, "after_review": after_review}


@step("C5.3", "two competing replacement candidates name the same predecessor: both pass alone, the second cannot merge once the first has, and a rebuilt candidate needs a fresh review", flows=("no",))
def _(f):
    frozen = stage("no.frozen")
    o = competing_candidates(frozen)
    equal(o["both"], ["success", "success"], "both candidates against the same tip")
    equal(o["stale"], ("failure", "carrydown: state-history-invalid"), "the second candidate after the first merged")
    equal(o["before_review"], ("failure", "carrydown: approval-not-found"), "the rebuilt candidate before a review")
    equal(o["after_review"], ("success", "carrydown: candidate verified"), "the rebuilt candidate after a review")
    return f"both: {o['both']}; second after the first merged: {o['stale'][1]}; rebuilt: {o['before_review'][1]} then {o['after_review'][1]}"


@step("C5.4", "the staging ruleset must require up-to-date branches: without that requirement the doctor does not verify it", flows=("no",))
def _(f):
    world = FE.World()
    good = {c.name: c.status for c in V.verify_prerequisites(world.reader, world.enrollment(), workspace_access=True)}
    equal(good["staging-ruleset"], V.VERIFIED, "ruleset as exported")
    world.reader.rulesets_by_repo[FE.STAGING_ID] = [FE.staging_ruleset(strict=False)]
    bad = {c.name: c.status for c in V.verify_prerequisites(world.reader, world.enrollment(), workspace_access=True)}
    need(bad["staging-ruleset"] != V.VERIFIED, "a ruleset without the up-to-date requirement was verified")
    world.reader.rulesets_by_repo[FE.STAGING_ID] = [FE.staging_ruleset(last_push=True)]
    bad = {c.name: c.status for c in V.verify_prerequisites(world.reader, world.enrollment(), workspace_access=True)}
    need(bad["staging-ruleset"] != V.VERIFIED, "a ruleset that requires a second human by last-push approval was verified")


# --- C6 ---------------------------------------------------------------------

def frozen_case():
    return EF.Case(stage("no.frozen"))


def success_case():
    case = frozen_case()
    number = case.open()
    conclusion, title, pub, report = verdict(case.world, number)
    need(conclusion == "success", "the control did not pass: " + title)
    head = case.reader.repos[FE.ENGINEERING_ID]["prs"][number]["head"]["sha"]
    return case, number, pub, head


@step("C6.1", "an engineering head that stays unchanged flips from success to failure after a withdrawal, an approver removal or a policy change, at the next poll", flows=("no",))
def _(f):
    seen = {}
    case, number, pub, head = success_case()
    case.withdraw()
    conclusion, title, pub, _r = verdict(case.world, number, pub)
    seen["withdrawal"] = (conclusion, title)
    need(case.reader.repos[FE.ENGINEERING_ID]["prs"][number]["head"]["sha"] == head, "the head changed")
    case, number, pub, head = success_case()
    case.reader.users[4242] = {"id": 4242, "login": "someone-else"}
    case.world.update_policy(lambda e: e.update(approvers=[{"id": 4242, "login": "someone-else"}]))
    seen["approver removed"] = verdict(case.world, number, pub)[:2]
    case, number, pub, head = success_case()
    case.world.update_policy(lambda e: e.update(offline_grace_days=3))
    seen["policy change"] = verdict(case.world, number, pub)[:2]
    equal(seen["withdrawal"], ("failure", "carrydown: withdrawn"), "withdrawal")
    equal(seen["approver removed"][0], "failure", "approver removed")
    need(seen["approver removed"][1] in ("carrydown: policy-revision-mismatch", "carrydown: approver-not-authorized"), str(seen))
    equal(seen["policy change"], ("failure", "carrydown: policy-revision-mismatch"), "policy change")
    return "head unchanged; " + "; ".join(f"{k} -> {v[1].replace('carrydown: ', '')}" for k, v in seen.items())


@step("C6.2", "a request that was pending when the engineering pull request opened passes at the next poll once it is approved, with no engineering push", flows=("no",))
def _(f):
    n = no()
    stage("no.land")
    files, pointer = n.branch_files(n.rids[0])
    pending = Exported(n.pre_land, n.rids[0], files, pointer)
    case = EF.Case(pending)
    world = case.world
    staging_pr = world.land(n.np.candidate_files(n.rids[0]), f"request/{n.rids[0]}", approve=False, merge=False)
    number = case.open()
    conclusion, title, pub, _r = verdict(world, number)
    equal((conclusion, title), ("failure", "carrydown: approval-not-found"), "before the approval")
    head = case.reader.repos[FE.ENGINEERING_ID]["prs"][number]["head"]["sha"]
    case.reader.review(FE.STAGING_ID, staging_pr, *FE.OWNER)
    case.reader.merge(FE.STAGING_ID, staging_pr)
    conclusion, title, pub, _r = verdict(world, number, pub)
    equal((conclusion, title), ("success", "carrydown: release verified"), "after the approval")
    equal(case.reader.repos[FE.ENGINEERING_ID]["prs"][number]["head"]["sha"], head, "engineering head")
    starts = [c for c in pub.calls if c[0] == "start" and c[1] == FE.ENGINEERING_ID]
    equal(len(starts), 2, "start calls on the one check run")
    return f"head {head[:12]} unchanged: failure (approval-not-found) then success; {len(starts)} start calls on one check run"


@step("C6.3", "a read error replaces an observed success with a failed check; a scheduler outage leaves the old success in place, which is the documented limit", flows=("no",))
def _(f):
    case, number, pub, head = success_case()
    silent = check_run(case.world, pub, FE.ENGINEERING_ID, number, V.ENGINEERING_CHECK)
    equal(silent["conclusion"], "success", "the check before any later poll")
    need("does not guarantee continuous authorization" in silent["summary"], "the success text lacks the limit: " + silent["summary"])
    case.withdraw()
    equal(check_run(case.world, pub, FE.ENGINEERING_ID, number, V.ENGINEERING_CHECK)["conclusion"], "success",
          "with no poll at all the old success stays, whatever happened in staging (a scheduler outage does not expire it)")
    case.reader.fail("tree", FE.ENGINEERING_ID)
    conclusion, title, pub, _r = verdict(case.world, number, pub)
    equal((conclusion, title), ("failure", "carrydown: evidence-unavailable"), "after a read error during the poll")
    case, number, pub, head = success_case()
    case.reader.fail("tree", FE.ENGINEERING_ID)
    conclusion, title, pub, _r = verdict(case.world, number, pub)
    equal((conclusion, title), ("failure", "carrydown: evidence-unavailable"), "a read error must not reuse the earlier success")
    return "with no poll the old success stays (documented limit); a read error during a poll -> failure (carrydown: evidence-unavailable)"


@step("C6.4", "an incomplete listing fails the check and the scan is not reported as complete", flows=("no",))
def _(f):
    case, number, pub, head = success_case()
    case.reader.truncate("pull_request_files")
    conclusion, title, pub, report = verdict(case.world, number, pub)
    equal((conclusion, title), ("failure", "carrydown: evidence-unavailable"), "a truncated file listing")
    case, number, pub, head = success_case()
    case.reader.fail("pull_requests", FE.ENGINEERING_ID)
    report, pub = scan_world(case.world, pub)
    need(not report.complete, "a scan that could not list the pull requests reported itself complete")
    equal(check_run(case.world, pub, FE.ENGINEERING_ID, number, V.ENGINEERING_CHECK)["conclusion"], "success",
          "a listing outage posts nothing: the earlier result stays, and the scan is not healthy")


@step("C6.5", "two concurrent scans cannot let an older result overwrite a newer failure", flows=("no",))
def _(f):
    case = frozen_case()
    number = case.open()
    pub = FE.FakeCheckPublisher()

    def newer(repo_id, head_sha, name):
        if repo_id == FE.ENGINEERING_ID:
            run = pub.new_run(repo_id, head_sha, name)
            pub.finish(repo_id, head_sha, name, run, "failure", "carrydown: withdrawn", "withdrawn")
    pub.before_finish = newer
    report, pub = scan_world(case.world, pub)
    state = check_run(case.world, pub, FE.ENGINEERING_ID, number, V.ENGINEERING_CHECK)
    need(report.superseded == 1 and state["conclusion"] == "failure", f"superseded={report.superseded} {state['conclusion']}")


@step("C6.7", "every listing the verifier reads follows all pages; a truncated listing and an exhausted rate limit fail instead of passing", flows=("no",))
def _(f):
    sys.path.insert(0, str(ROOT / "tests"))
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
    equal(pages, 250, "pull requests read over three pages")
    need("truncated" in truncated, f"a 3000-file listing was accepted: {truncated}")
    need(limited is not None, "a rate-limit failure was accepted")
    return f"{pages} pull requests over 3 pages; 3000-file listing: {truncated}; rate limit: {limited}"


@step("C6.6", "the scan health record is partial after an outage and the owner-side writes refuse when it is stale", flows=("no",))
def _(f):
    world = FE.World()
    fresh = {c.name: c.status for c in V.verify_prerequisites(world.reader, world.enrollment(), workspace_access=True)}
    equal(fresh["scan-health"], V.VERIFIED, "scan health")
    world.reader.scan[FE.TOOLING_ID]["completed_at"] = V.utc_text(V.clock() - 3 * 3600)
    stale = {c.name: c.status for c in V.verify_prerequisites(world.reader, world.enrollment(), workspace_access=True)}
    need(stale["scan-health"] != V.VERIFIED, "a stale scan was healthy")
    world.reader.scan[FE.TOOLING_ID]["completed_at"] = V.utc_text(V.clock() - 60)
    world.reader.scan[FE.TOOLING_ID]["complete"] = False
    partial = {c.name: c.status for c in V.verify_prerequisites(world.reader, world.enrollment(), workspace_access=True)}
    need(partial["scan-health"] != V.VERIFIED, "a partial scan was healthy")


# --- C7 ---------------------------------------------------------------------

@step("C7.1", "editing approved working files makes engineering-target maintenance refuse, and drafting in the private workspace stays allowed", flows=("yes", "no"))
def _(f):
    r = cstage(f, "c4", lambda: c4_run(f))
    if f.path == "yes":
        root = f.root
        spec = root / SPEC_FILE
        spec.write_text(spec.read_text(encoding="utf-8").rstrip("\n") + " Edited after approval.\n", encoding="utf-8")
        refusing = (("scaffold_spec.py", ["--refresh-headers", "--apply", "--allow-no-git"]), ("plan_repair.py", ["--apply"]))
        wanted = "working-copy-differs"
    else:
        root = S.tmp / "no-edited-clone"
        git(S.tmp, "clone", "-q", f.origin, root)
        spec = root / SPEC_FILE
        spec.write_text(spec.read_text(encoding="utf-8").rstrip("\n") + " Edited after approval.\n", encoding="utf-8")
        refusing = (("generate_dev_skill.py", ["--apply", "--force"]), ("plan_repair.py", ["--apply"]))
        wanted = "not-approved"
    before = tree_state(root)
    seen = []
    for script, args in refusing:
        res = run_script(script, "--root", root, *args, cwd=root)
        need(res.returncode == 1 and wanted in res.stderr, f"{script}: exit {res.returncode}: {res.stderr[-250:]}")
        seen.append(f"{script} -> {wanted}")
    res = run_script("generate_dev_skill.py", "--root", root, "--apply", "--force", cwd=root)
    need(res.returncode in (0, 1), res.stderr[-200:])
    equal(tree_state(root), before, "files changed by maintenance after the edit")
    # private drafting: a candidate write in the workspace is allowed, and the preview reads without writing
    decision = RG.check("candidate", "drafts/plan.yaml", "0" * 64, "workspace", str(f.root))
    need(decision.allowed, f"the gate refused a workspace write: {decision}")
    ws_before = tree_state(f.ws)
    code, out, err = F.run(R.main, ["preview"] + f.common() + (["--repository-id", "4200"] if f.path == "yes" else []))
    need(code == 0, out + err)
    equal(tree_state(f.ws), ws_before, "workspace after the preview")
    if f.path == "yes":
        spec.write_text(spec.read_text(encoding="utf-8").replace(" Edited after approval.\n", "\n"), encoding="utf-8")
    else:
        shutil.rmtree(root)
    return "; ".join(seen) + "; the workspace write is allowed"


@step("C7.7", "scaffold_spec.py --refresh-headers on a clone of the released tree refuses with a fixed reason code", flows=("no",))
def _(f):
    stage("no.clone")
    root = S.tmp / "no-scaffold-clone"
    git(S.tmp, "clone", "-q", f.origin, root)
    before = tree_state(root)
    res = run_script("scaffold_spec.py", "--root", root, "--refresh-headers", "--apply", "--allow-no-git", cwd=root)
    equal(tree_state(root), before, "files written")
    need(res.returncode == 1 and re.search("not-approved|working-copy-differs|drafting-is-private", res.stderr) and "Traceback" not in res.stderr, res.stderr[-200:])
    return res.stderr.strip().splitlines()[-1][:160]


def verdict_without_processes(case, number):
    def refuse(*a, **k):
        raise AssertionError("the verifier started a process")
    with mock.patch.object(subprocess, "run", refuse), mock.patch.object(subprocess, "Popen", refuse), mock.patch.object(os, "system", refuse):
        return verdict(case.world, number)


@step("C7.2", "a pull request that edits the checker to always pass and adds a governed specification fails on the governed file; the edited checker never ran", flows=("no",))
def _(f):
    canary = S.tmp / "canary.txt"
    checker = ("import sys\nfrom pathlib import Path\nPath(%r).write_text('ran')\nsys.exit(0)\n" % str(canary)).encode()
    case = frozen_case()
    case.reader.set_file(FE.ENGINEERING_ID, "tools/carrydown/check_specs.py", b"# the original checker\n")
    number = case.open(edit={"tools/carrydown/check_specs.py": checker, "docs/spec/unreleased.md": b"# A specification with no release\n"})
    conclusion, title, _p, _r = verdict_without_processes(case, number)
    equal((conclusion, title), ("failure", "carrydown: governed-file-without-release"), "verifier on the edited checker")
    need(not canary.exists(), "the edited checker ran")
    case = frozen_case()
    case.reader.set_file(FE.ENGINEERING_ID, "tools/carrydown/check_specs.py", b"# the original checker\n")
    number = case.open(only={"tools/carrydown/check_specs.py": checker})
    conclusion, title, _p, _r = verdict_without_processes(case, number)
    equal(conclusion, "success", "a pull request that touches only the checker has no governed change")
    need(not canary.exists(), "the edited checker ran in the control")
    return "failure (carrydown: governed-file-without-release); canary file created: False; processes started: 0"


@step("C7.3", "deleting the handling block of the released plan, or the policy pointer, is rejected; neither downgrades an enrolled project", flows=("no",))
def _(f):
    exported = stage("no.frozen")
    plan = exported.files["docs/spec/plan.yaml"][1].decode("utf-8")
    keep, skip = [], False
    for line in plan.split("\n"):
        if line.startswith("  handling:"):
            skip = True
            continue
        if skip and line.startswith("    "):
            continue
        skip = False
        keep.append(line)
    case = frozen_case()
    number = case.open(edit={"docs/spec/plan.yaml": "\n".join(keep).encode("utf-8")})
    equal(verdict_without_processes(case, number)[:2], ("failure", "carrydown: enrolled-project-missing-handling"), "handling deleted")
    case = frozen_case()
    number = case.open(only={POINTER: None})
    equal(verdict_without_processes(case, number)[:2], ("failure", "carrydown: policy-pointer-mismatch"), "pointer deleted")
    case = frozen_case()
    wrong = f"format: 1\ntooling_repository: {TOOLING}\nenrollment_id: {'0' * 64}\n".encode()
    number = case.open(only={POINTER: wrong})
    equal(verdict_without_processes(case, number)[:2], ("failure", "carrydown: policy-pointer-mismatch"), "pointer altered")


@step("C7.4", "an unsafe artifact path is rejected", flows=("no",))
def _(f):
    case = frozen_case()
    number = case.open(edit={"docs/spec/../../outside.md": b"# not inside the repository\n"})
    conclusion, title, _p, _r = verdict_without_processes(case, number)
    need(conclusion == "failure" and title in ("carrydown: unsafe-artifact-path", "carrydown: governed-file-without-release"), f"{conclusion} {title}")
    case = frozen_case()
    number = case.open(edit={"docs/spec/link.md": ("120000", b"/etc/hosts")})
    conclusion, title, _p, _r = verdict_without_processes(case, number)
    need(conclusion == "failure" and re.fullmatch(r"carrydown: (unsafe-artifact-path|sha256-mismatch|governed-file-without-release)", title), f"a symlink: {conclusion} {title}")


@step("C7.5", "a smuggled private staffing field in the released plan is rejected and the public check text names the location, never the value", flows=("no",))
def _(f):
    exported = stage("no.frozen")
    plan = exported.files["docs/spec/plan.yaml"][1].decode("utf-8")
    smuggled = plan.replace('  - id: "tamsin"\n', '  - id: "tamsin"\n    days_off: ["2027-02-22"]\n    name: "Tamsin Hale"\n', 1)
    need(smuggled != plan, "the person was not found in the released plan")
    case = frozen_case()
    number = case.open(edit={"docs/spec/plan.yaml": smuggled.encode("utf-8")})
    conclusion, title, pub, _r = verdict_without_processes(case, number)
    need(conclusion == "failure" and re.fullmatch(r"carrydown: [a-z-]+", title), f"{conclusion} {title}")
    run = check_run(case.world, pub, FE.ENGINEERING_ID, number, V.ENGINEERING_CHECK)
    text = run["title"] + run["summary"]
    equal(scan_text({"check": text.encode("utf-8")}, ("Tamsin Hale", "2027-02-22")), [], "the private value in the public check text")


@step("C7.6", "changing the approved bytes of a governed file, or its mode, fails even beside a valid receipt", flows=("no",))
def _(f):
    exported = stage("no.frozen")
    spec = next(p for p in sorted(exported.files) if p.rsplit("/", 1)[-1].startswith("wi-") and b"## Decisions recorded" in exported.files[p][1])
    case = frozen_case()
    number = case.open(edit={spec: exported.files[spec][1] + b"\nA sentence the owner never approved.\n"})
    equal(verdict_without_processes(case, number)[:2], ("failure", "carrydown: sha256-mismatch"), "changed bytes")
    case = frozen_case()
    number = case.open(edit={spec: ("100755", exported.files[spec][1])})
    equal(verdict_without_processes(case, number)[:2], ("failure", "carrydown: sha256-mismatch"), "changed mode")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="The acceptance scenarios of the confidential ground truth specification (Part F, WP11).")
    ap.add_argument("--list", action="store_true", help="list the named assertions without running them")
    ap.add_argument("--only", help="comma-separated step id prefixes to run, such as A,B1,C3 (later steps may depend on earlier ones)")
    a = ap.parse_args(argv)
    if a.list:
        for entry in ORDER:
            print(label(entry))
        print(f"{len(ORDER)} named assertions")
        S.cleanup()
        return 0
    try:
        return run_all([x.strip() for x in a.only.split(",")] if a.only else None)
    finally:
        S.net.stop()


if __name__ == "__main__":
    sys.exit(main())
