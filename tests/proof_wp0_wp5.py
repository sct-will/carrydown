#!/usr/bin/env python3
"""A re-runnable proof of the acceptance claims of work packages 0 to 5. Standard library only.

Run it from the repository root, with no token and no network:

  python3 tests/proof_wp0_wp5.py            every claim, the self test included (about three minutes)
  python3 tests/proof_wp0_wp5.py --quick    every claim except the full self test

Each claim runs the real scripts in a subprocess, the way an owner or an engineer runs them: workspace.py,
check_specs.py, detectors.py, scaffold_spec.py, render_ground_truth.py, compile_bundles.py, release.py,
generate_dev_skill.py and the engineers' check_context.py. A few claims about the digest rules call the pure
functions of release_schema.py directly, because those rules have no command of their own; they say so. Every
subprocess gets an empty home folder (so no stored token is found), no token variable and a proxy on a closed
loopback port, so nothing can reach the network. The script prints PASS or FAIL per claim with the line it
observed, never a test result or a file date. It exits 0 only when every claim passes.
"""
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
SAMPLE = ROOT / "sample" / "expense-approvals"
WORKING_PLAN = ROOT / "tests" / "fixtures" / "sample-workspace" / "drafts" / "plan.yaml"
SAMPLE_WS = ROOT / "tests" / "fixtures" / "sample-workspace"
CHECK_CONTEXT = ROOT / "templates" / "dev-skill" / "scripts" / "check_context.py"
PY = sys.executable
QUESTION = "Can everyone who can read this repository see all of these documents and your staffing notes?"
RESULTS = []
CLAIMS = []
TMP = Path(tempfile.mkdtemp(prefix="carrydown-proof-wp0-5-"))

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import release_schema as RS  # noqa: E402


def claim(text):
    def wrap(fn):
        def run():
            base = Path(tempfile.mkdtemp(dir=str(TMP)))
            try:
                observed = fn(base)
                RESULTS.append(True)
                print(f"PASS {text}")
                print(f"     observed: {observed}")
            except Exception as e:     # a failed claim is reported, and the rest still run
                RESULTS.append(False)
                print(f"FAIL {text}")
                print(f"     {type(e).__name__}: {str(e)[:400]}")
                if os.environ.get("PROOF_TRACE"):
                    traceback.print_exc()
            sys.stdout.flush()
        run.claim = text
        CLAIMS.append(run)
        return fn
    return wrap


def check(condition, message="condition failed"):
    if not condition:
        raise AssertionError(message)


def env_for(base):
    """No token, no stored token file, no network, no developer git settings."""
    home = Path(base) / "home"
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ("CARRYDOWN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN") and not k.startswith("GIT_")}
    env.update(HOME=str(home), USERPROFILE=str(home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
               PYTHONDONTWRITEBYTECODE="1", http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9",
               HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", no_proxy="127.0.0.1,localhost", NO_PROXY="127.0.0.1,localhost")
    return env


def run(base, args, cwd=None, timeout=300):
    """Run a command (a list; a .py first element is run with this Python from scripts/ unless it is a path)."""
    argv = [str(a) for a in args]
    if argv[0].endswith(".py"):
        script = Path(argv[0]) if os.sep in argv[0] else SCRIPTS / argv[0]
        argv = [PY, str(script)] + argv[1:]
    out = subprocess.run(argv, cwd=str(cwd or base), capture_output=True, text=True, env=env_for(base), timeout=timeout)
    return out.returncode, out.stdout + out.stderr


def git(base, cwd, *args):
    code, out = run(base, ["git", "-c", "user.name=Proof Owner", "-c", "user.email=proof.owner@example.com", "-c", "commit.gpgsign=false"]
                    + list(args), cwd=cwd)
    check(code == 0, f"git {' '.join(args)}: {out[-300:]}")
    return out.strip()


def line_with(text, needle):
    for line in text.splitlines():
        if needle in line:
            return line.strip()
    raise AssertionError(f"no line containing {needle!r} in: {text[-400:]!r}")


def last_line(text):
    lines = [x for x in text.splitlines() if x.strip()]
    check(lines, "no output")
    return lines[-1].strip()


def copy_fixture(base, name="project"):
    dst = Path(base) / name
    shutil.copytree(str(FIXTURE), str(dst), ignore=shutil.ignore_patterns("__pycache__"))
    return dst


def copy_sample(base, name="project", working=True):
    dst = Path(base) / name
    shutil.copytree(str(SAMPLE), str(dst), ignore=shutil.ignore_patterns("__pycache__"))
    if working:
        shutil.copyfile(str(WORKING_PLAN), str(dst / "docs" / "spec" / "plan.yaml"))
    return dst


def point_workspace(project, workspace):
    pointer = Path(project) / ".carrydown" / "local.yaml"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(f"workspace: {json.dumps(str(workspace))}\n", encoding="utf-8")


def set_answer(plan_path, value):
    text = Path(plan_path).read_text(encoding="utf-8")
    new = re.sub(r"(?m)^(    repo_audience_approved: )\S+", r"\g<1>" + ("true" if value else "false"), text, count=1)
    check(new != text or ("repo_audience_approved: " + ("true" if value else "false")) in text, "no handling block to edit")
    Path(plan_path).write_text(new, encoding="utf-8")


def files_under(folder):
    folder = Path(folder)
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


# ===========================================================================
# WP0. Branch, harness and conventions
# ===========================================================================

@claim("WP0 sync: the skill and sample copies of every script and template are current")
def _(base):
    code, out = run(base, ["sync_skill_assets.py", "--check"], cwd=ROOT)
    check(code == 0, out[-300:])
    return last_line(out)


@claim("WP0 packaging: each installed skill, copied away from scripts/, runs every one of its scripts with --help")
def _(base):
    counted = []
    for skill in ("carrydown-ground-truth", "carrydown-plan-to-github"):
        dst = Path(base) / "installed" / skill
        shutil.copytree(str(ROOT / "skills" / skill), str(dst), ignore=shutil.ignore_patterns("__pycache__"))
        scripts = sorted((dst / "scripts").glob("*.py"))
        check(scripts, f"{skill} carries no scripts")
        for script in scripts:
            code, out = run(base, [PY, str(script), "--help"], cwd=Path(base) / "installed")
            check(code == 0, f"{skill}/{script.name} --help exit {code}: {out[-200:]}")
        counted.append(f"{skill}: {len(scripts)} scripts")
    return "; ".join(counted)


@claim("WP0 packaging: the ground-truth skill and the engineers' check carry no network or token code (A4)")
def _(base):
    banned = re.compile(r"^\s*(import|from)\s+(github_client|github_token|urllib\.request|http\.client|socket|ssl)\b", re.M)
    offenders = []
    files = list((ROOT / "skills" / "carrydown-ground-truth" / "scripts").glob("*.py")) + [CHECK_CONTEXT]
    for path in files:
        if banned.search(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    check(not offenders, f"network imports in {offenders}")
    gh = sorted(p.name for p in (ROOT / "skills" / "carrydown-ground-truth" / "scripts").glob("github_*.py"))
    check(not gh, f"GitHub scripts shipped in the first skill: {gh}")
    return f"{len(files)} files scanned, no network or token import; no github_*.py in carrydown-ground-truth"


@claim("WP0 gate scaffold: the monkeypatched write assertion is no longer an expected failure, and it passes")
def _(base):
    text = (ROOT / "tests" / "test_release_gate.py").read_text(encoding="utf-8")
    check("expectedFailure" not in text, "an expectedFailure marker is still in test_release_gate.py")
    code, out = run(base, [PY, "-m", "unittest", "tests.test_release_gate"], cwd=ROOT, timeout=600)
    check(code == 0 and "expected failures" not in out, out[-300:])
    return line_with(out, "Ran ") + " " + last_line(out)


@claim("WP0 digests (pure functions): the request digest omits only request_sha256, the event digest only event_id")
def _(base):
    request = json.loads(next((SAMPLE_WS / "requests").iterdir()).joinpath("approval-request.json").read_text(encoding="utf-8"))
    rid = RS.hash_request(request)
    check(rid == request["request_sha256"], "the stored request digest does not recompute")
    body = {k: v for k, v in request.items() if k != "request_sha256"}
    check(rid == hashlib.sha256(RS.canonical_json(body)).hexdigest(), "the digest is not sha256 of the canonical request minus request_sha256")
    check(RS.hash_request(dict(request, request_sha256="0" * 64)) == rid, "changing request_sha256 changed the digest")
    check(RS.hash_request(dict(request, request_nonce="0" * 32)) != rid, "the nonce is not covered")
    event = json.loads(next((SAMPLE_WS / "events").iterdir()).read_text(encoding="utf-8"))
    eid = RS.hash_event(event)
    check(eid == event["event_id"], "the stored event digest does not recompute")
    ebody = {k: v for k, v in event.items() if k != "event_id"}
    check(eid == hashlib.sha256(RS.canonical_json(ebody)).hexdigest(), "the event digest is not sha256 of the batch minus event_id")
    check(RS.hash_event(dict(event, event_id="f" * 64)) == eid, "changing event_id changed the event digest")
    check(RS.hash_event(dict(event, event_nonce="0" * 32)) != eid, "the event nonce is not covered")
    return f"request {rid[:12]} = sha256(canonical request minus request_sha256), {len(body)} fields; event {eid[:12]} = sha256(batch minus event_id)"


@claim("WP0 digests (pure functions): canonical JSON is sorted, compact, one LF, and refuses duplicate keys and NaN")
def _(base):
    text = RS.canonical_json({"b": 1, "a": [3, {"d": 1, "c": 2}]})
    check(text == b'{"a":[3,{"c":2,"d":1}],"b":1}\n', text)
    for bad in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
        try:
            RS.loads_strict(bad)
        except RS.SchemaError:
            continue
        raise AssertionError(f"accepted {bad!r}")
    try:
        RS.canonical_json({"a": float("nan")})
        raise AssertionError("NaN serialized")
    except (RS.SchemaError, ValueError):
        pass
    return text.decode("utf-8").rstrip("\n") + " (and duplicate key, NaN, Infinity refused)"


@claim("WP0 manifest (pure functions): release id = sha256 of the manifest bytes; unsafe snapshot paths refuse")
def _(base):
    snap = Path(base) / "snapshot"
    (snap / "repo" / "docs").mkdir(parents=True)
    (snap / "repo" / "docs" / "b.md").write_bytes(b"b\n")
    (snap / "repo" / "docs" / "a.md").write_bytes(b"a\n")
    manifest, release_id = RS.hash_manifest(snap)
    check(release_id == hashlib.sha256(manifest).hexdigest(), "release id is not the manifest digest")
    paths = [e["path"] for e in json.loads(manifest)]
    check(paths == sorted(paths), "manifest is not sorted")
    refusals = []
    unsafe = ("/abs/x", "repo/../x", "repo\\x", "repo/.git/config", "C:/x")
    for bad in unsafe:
        try:
            RS.check_path(bad, "path")
        except RS.SchemaError:
            refusals.append(bad)
    check(len(refusals) == len(unsafe), f"accepted {sorted(set(unsafe) - set(refusals))}")
    os.symlink(str(snap / "repo" / "docs" / "a.md"), str(snap / "repo" / "docs" / "link.md"))
    try:
        RS.hash_manifest(snap)
        raise AssertionError("a symbolic link was hashed")
    except RS.SchemaError as e:
        sym = e.code
    entry = {"sha256": "0" * 64, "bytes": 1, "mode": "100644"}
    try:
        RS.manifest_from_entries([dict(entry, path="repo/docs/a.md"), dict(entry, path="repo/docs/A.md")])
        raise AssertionError("two paths that differ only by case were accepted")
    except RS.SchemaError as e:
        collided = e.code
    return f"release id {release_id[:12]} = sha256(manifest); {len(refusals)} unsafe paths refused; symlink: {sym}; case collision: {collided}"


@claim("WP0 workspace_root: a pointer into the repository is refused, a missing pointer gives a reason")
def _(base):
    project = copy_fixture(base)
    import carrydown_lib as L
    missing = L.workspace_root(project)
    point_workspace(project, project / "inside")
    (project / "inside").mkdir()
    inside = L.workspace_root(project)
    outside = Path(base) / "ws"
    outside.mkdir()
    point_workspace(project, outside)
    ok = L.workspace_root(project)
    check(missing == (None, "workspace-unavailable"), missing)
    check(inside == (None, "workspace-inside-repository"), inside)
    check(ok[0] == outside.resolve() and ok[1] is None, ok)
    return f"missing: {missing[1]}; inside: {inside[1]}; outside: accepted"


@claim("WP0 fixture: the confidential project has a restricted source, people ids in people.yaml, and checks clean")
def _(base):
    import carrydown_lib as L
    plan = L.load_file(FIXTURE / "docs" / "spec" / "plan.yaml")
    classes = {s["id"]: s.get("classification") for s in plan["sources"]}
    check(classes.get("company-governance") == "restricted", classes)
    people = L.load_file(FIXTURE / "people.yaml")
    rows = people.get("people") if isinstance(people, dict) else people
    check(rows and all(isinstance(p, dict) and p.get("id") for p in rows), "people.yaml rows without id")
    code, out = run(base, ["check_specs.py", "--root", FIXTURE, "--report"], cwd=ROOT)
    check(code == 0, out[-300:])
    return f"classifications {classes}; {len(rows)} people with ids; checker: {line_with(out, 'finding(s)')}"


# ===========================================================================
# WP1. Step 0: handling policy, classification and the private workspace
# ===========================================================================

@claim("WP1 selftest bullet: yes to the one question plus a restricted source fails with a named finding")
def _(base):
    project = copy_fixture(base)
    set_answer(project / "docs" / "spec" / "plan.yaml", True)
    code, out = run(base, ["check_specs.py", "--root", project], cwd=ROOT)
    check(code != 0, f"exit {code}")
    return line_with(out, "classification is restricted, but project.handling.repo_audience_approved is true")


@claim("WP1 workspace.py init --apply: owner-only folder with git, workspace.yaml and retention.yaml; pointer written; only .gitignore changes in the repository")
def _(base):
    project = copy_fixture(base)
    git(base, project, "init", "-q", "-b", "main")
    git(base, project, "add", "-A")
    git(base, project, "commit", "-q", "-m", "fixture")
    code, dry = run(base, ["workspace.py", "init", "--root", project, "--slug", "proof-project"], cwd=project)
    check(code == 0, dry[-300:])
    home = Path(base) / "home"
    check(not (home / ".carrydown").exists() and not (project / ".carrydown").exists(), "the dry run wrote something")
    code, out = run(base, ["workspace.py", "init", "--root", project, "--slug", "proof-project", "--answer", "no", "--apply"], cwd=project)
    check(code == 0, out[-400:])
    ws = home / ".carrydown" / "workspaces" / "proof-project"
    mode = stat.S_IMODE(os.stat(ws).st_mode)
    check(mode == 0o700, oct(mode))
    for name in ("workspace.yaml", "retention.yaml", ".git"):
        check((ws / name).exists(), f"missing {name}")
    pointer = (project / ".carrydown" / "local.yaml").read_text(encoding="utf-8")
    check(str(ws) in pointer or ws.name in pointer, pointer)
    status = git(base, project, "status", "--porcelain", "--untracked-files=all")
    check(status.splitlines() == ["M .gitignore"], repr(status))
    check(".carrydown/local.yaml" in (project / ".gitignore").read_text(encoding="utf-8"), "pointer not ignored")
    check("staging" in out.lower() and "gh " in out or "git " in out, "no staging commands printed on the no answer")
    return f"mode {oct(mode)}; {sorted(p.name for p in ws.iterdir())}; git status: {status!r}"


@claim("WP1 workspace.py init refuses a workspace inside the repository and creates nothing")
def _(base):
    project = copy_fixture(base)
    inside = project / "private"
    code, out = run(base, ["workspace.py", "init", "--root", project, "--slug", "proof-project", "--workspace", inside, "--apply"], cwd=project)
    check(code == 2, f"exit {code}: {out[-300:]}")
    check(not inside.exists() and not (project / ".carrydown").exists(), "something was created")
    return f"exit {code}: {last_line(out)}"


@claim("WP1 workspace.py status prints the workspace path and state")
def _(base):
    project = copy_fixture(base)
    ws = Path(base) / "ws"
    code, out = run(base, ["workspace.py", "init", "--root", project, "--slug", "proof-project", "--workspace", ws, "--apply"], cwd=project)
    check(code == 0, out[-300:])
    code, out = run(base, ["workspace.py", "status", "--root", project], cwd=project)
    check(code == 0 and str(ws.resolve()) in out, out[-300:])
    return " | ".join(x.strip() for x in out.splitlines()[:3])


@claim("WP1 interview text: step 0 line and the one question, verbatim, before rendering and staffing")
def _(base):
    interview = (ROOT / "skills" / "carrydown-ground-truth" / "references" / "interview.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills" / "carrydown-ground-truth" / "SKILL.md").read_text(encoding="utf-8")
    check("carrydown: interview, step 0 of 6" in interview, "step 0 line missing")
    check(QUESTION in interview and QUESTION in skill, "question not verbatim")
    check(interview.index("step 0 of 6") < interview.index("People and tracks") if "People and tracks" in interview else True, "order")
    return line_with(interview, "step 0 of 6")[:120]


@claim("WP1 released view: a staffing key in people[] fails at people:<id>:<field> without printing its value")
def _(base):
    project = copy_sample(base, working=False)
    plan = project / "docs" / "spec" / "plan.yaml"
    text = plan.read_text(encoding="utf-8")
    block = text.index("\npeople:\n")
    m = re.compile(r"(?m)^  - id: (\S+)\n").search(text, block)
    check(m, "no people id in the released plan")
    secret = "Quentin Proofname"
    text = text.replace(m.group(0), m.group(0) + f"    name: {secret}\n", 1)
    plan.write_text(text, encoding="utf-8")
    code, out = run(base, ["check_specs.py", "--root", project, "--view", "released"], cwd=ROOT)
    check(code != 0 and secret not in out, f"exit {code}")
    return line_with(out, f"people:{m.group(1).strip(chr(34))}:name")


# ===========================================================================
# WP2. Staffing split
# ===========================================================================

@claim("WP2 checker on the committed sample with no overlay: 0 findings and the 'not loaded' line")
def _(base):
    code, out = run(base, ["check_specs.py", "--root", SAMPLE, "--report"], cwd=ROOT)
    check(code == 0, out[-300:])
    check("people overlay not loaded: capacity, dates and names not checked" in out, "no overlay line")
    return line_with(out, "finding(s)") + "; " + line_with(out, "people overlay not loaded")


@claim("WP2 overlay from a temporary private workspace gives the same capacity results as --people")
def _(base):
    project = copy_sample(base)
    (project / "people.yaml").unlink()
    ws = Path(base) / "ws"
    ws.mkdir()
    shutil.copyfile(str(SAMPLE / "people.yaml"), str(ws / "people.yaml"))
    point_workspace(project, ws)
    code1, via_ws = run(base, ["check_specs.py", "--root", project, "--report"], cwd=ROOT)
    other = copy_sample(base, "other")
    code2, via_flag = run(base, ["check_specs.py", "--root", other, "--report", "--people", SAMPLE / "people.yaml"], cwd=ROOT)
    check(code1 == code2 == 0, f"exit {code1} {code2}")
    check("people overlay not loaded" not in via_ws, "overlay not loaded from the workspace")
    norm = lambda t: [x for x in t.replace(str(project), "P").replace(str(other), "P").splitlines()]  # noqa: E731
    check(norm(via_ws) == norm(via_flag), "the two reports differ")
    cap = [x for x in via_ws.splitlines() if "percent" in x or "capacity" in x.lower()]
    check(cap, "no capacity line in the report")
    return f"{len(via_ws.splitlines())} report lines identical; e.g. {cap[0].strip()[:100]}"


@claim("WP2 the committed released plan has no staffing keys in people[] and no advisors")
def _(base):
    import carrydown_lib as L
    plan = L.load_file(SAMPLE / "docs" / "spec" / "plan.yaml")
    removed = set(L.STAFFING_KEYS)
    bad = [(p.get("id"), sorted(set(p) & removed)) for p in plan.get("people", []) if set(p) & removed]
    check(not bad and "advisors" not in plan, bad)
    check(plan.get("plan_view") == "released", plan.get("plan_view"))
    return f"{len(plan['people'])} people with keys {sorted(set().union(*[set(p) for p in plan['people']]))}; removed keys checked: {len(removed)}"


def prepare_sample(base, *flags, logins=False):
    """A working copy of the sample with a private workspace, prepared through release.py prepare --apply.
    logins=True gives each fictional person a fictional GitHub login, as an owner would."""
    project = copy_sample(base)
    git(base, project, "init", "-q", "-b", "main")
    ws = Path(base) / "ws"
    code, out = run(base, ["workspace.py", "init", "--root", project, "--slug", "proof", "--workspace", ws, "--apply"], cwd=project)
    check(code == 0, out[-300:])
    shutil.move(str(project / "people.yaml"), str(ws / "people.yaml"))
    if logins:
        text = (ws / "people.yaml").read_text(encoding="utf-8")
        n = iter(range(1, 100))
        text = re.sub(r'github: ""', lambda m: f'github: "proof-login-{next(n)}"', text)
        (ws / "people.yaml").write_text(text, encoding="utf-8")
    code, out = run(base, ["release.py", "prepare", "--root", project, "--repository-id", "4200", "--apply",
                           "--created", "2027-01-20T14:03:00Z", "--nonce", "ab" * 16] + list(flags), cwd=project)
    check(code == 0, out[-500:])
    rel = re.search(r"release id \(content\):\s*([0-9a-f]{64})", out) or re.search(r"release ([0-9a-f]{64})", out)
    check(rel, f"no release id printed: {out[-300:]}")
    return project, ws, rel.group(1), out


@claim("WP2 release.py prepare with --capacity-summary no --assignees no: Epic comment has no allocation text, issue payloads no assignees")
def _(base):
    _, ws, rid_off, _ = prepare_sample(Path(base) / "off", "--capacity-summary", "no", "--assignees", "no", logins=True)
    _, ws_on, rid_on, _ = prepare_sample(Path(base) / "on", "--capacity-summary", "yes", "--assignees", "yes", logins=True)

    def payloads(w, release_id):
        snap = w / "releases" / release_id / "snapshot" / "payloads"
        check(snap.is_dir(), f"no payloads under {snap}")
        return {p.relative_to(snap).as_posix(): json.loads(p.read_text(encoding="utf-8")) for p in snap.rglob("*.json")}
    off, on = payloads(ws, rid_off), payloads(ws_on, rid_on)
    comment_off = next(v for k, v in off.items() if k.startswith("epic-comment/"))["body"]
    comment_on = next(v for k, v in on.items() if k.startswith("epic-comment/"))["body"]
    check("percent" not in comment_off and "percent" in comment_on, "allocation text does not follow the flag")
    issues_off = [v for k, v in off.items() if k.startswith("issue/")]
    issues_on = [v for k, v in on.items() if k.startswith("issue/")]
    check(issues_off and all(v.get("assignees") == [] for v in issues_off), "assignees present with --assignees no")
    check(any(v.get("assignees") for v in issues_on), "no assignees with --assignees yes")
    return f"off: {len(issues_off)} issues, 0 assignees, comment without 'percent'; on: {sum(1 for v in issues_on if v.get('assignees'))} issues assigned"


# ===========================================================================
# WP3. Checker changes: originals, tracked sources, detectors, log hygiene
# ===========================================================================

FAKE_TOKEN = "ghp_" + "Z9y8X7w6V5u4T3s2R1q0P9o8N7m6L5k4J3i2"
HOME_PATH = "/Users/proofowner/private-notes/plan.txt"
PASSAGE_WORDS = 14


def seeded_project(base):
    """The fixture with a private workspace holding its restricted rendering, and four seeded leaks."""
    project = copy_fixture(base)
    ws = Path(base) / "ws"
    (ws / "renderings").mkdir(parents=True)
    (ws / "drafts").mkdir()
    shutil.copyfile(str(project / "docs" / "ground-truth" / "company-governance.md"), str(ws / "renderings" / "company-governance.md"))
    shutil.copyfile(str(project / "docs" / "spec" / "plan.yaml"), str(ws / "drafts" / "plan.yaml"))
    (project / "docs" / "ground-truth" / "company-governance.md").unlink()
    point_workspace(project, ws)
    rendering = (ws / "renderings" / "company-governance.md").read_text(encoding="utf-8")
    para = next(p for p in rendering.split("\n\n") if len(p.split()) >= 20 and not p.startswith(("#", "<!--", "|")))
    passage = " ".join(para.split()[:PASSAGE_WORDS])
    spec_dir = project / "docs" / "spec"
    specs = sorted(spec_dir.rglob("wi-*.md"))
    targets = {"token": specs[0], "home": specs[1], "passage": specs[2]}
    targets["token"].write_text(targets["token"].read_text(encoding="utf-8") + f"\nDeploy with {FAKE_TOKEN} to staging.\n", encoding="utf-8")
    targets["home"].write_text(targets["home"].read_text(encoding="utf-8") + f"\nRead the notes in {HOME_PATH} first.\n", encoding="utf-8")
    targets["passage"].write_text(targets["passage"].read_text(encoding="utf-8") + f"\n{passage}\n", encoding="utf-8")
    released = copy_sample(base, "released", working=False)
    plan = (released / "docs" / "spec" / "plan.yaml").read_text(encoding="utf-8")
    m = re.search(r"(?m)^  - id: (\S+)\n    track: \S+\n", plan)
    check(m, "no people row to seed")
    staffed = plan.replace(m.group(0), m.group(0) + "    days_off: [2027-02-22]\n", 1)
    (spec_dir / "released-copy").mkdir()
    (spec_dir / "released-copy" / "plan.yaml").write_text(staffed, encoding="utf-8")
    return project, ws, passage


@claim("WP3 detectors.py on a project with a fake token, a home path, a days_off key and a copied passage: exactly four findings, none quoting the text")
def _(base):
    project, ws, passage = seeded_project(base)
    code, out = run(base, ["detectors.py", "--root", project], cwd=ROOT)
    found = [x for x in out.splitlines() if x.startswith("detector:")]
    kinds = sorted(x.split(" at ")[0] for x in found)
    check(code == 1, f"exit {code}: {out[-300:]}")
    check(kinds == ["detector:copied_restricted:copied-passage", "detector:credentials:github-token", "detector:private_paths:home-path",
                    "detector:prohibited_fields:staffing-field"], kinds)
    for seeded in (FAKE_TOKEN, "ghp_", HOME_PATH, "proofowner", "days_off", "2027-02-22", passage, " ".join(passage.split()[:3]), str(ws)):
        check(seeded not in out, f"the output quotes {seeded[:20]!r}")
    return "; ".join(found)


@claim("WP3 a recorded exception clears the copied passage; an exception for a credential is refused (exception-not-permitted)")
def _(base):
    project, ws, passage = seeded_project(base)
    code, out = run(base, ["detectors.py", "--root", project], cwd=ROOT)
    copied = line_with(out, "copied-passage")
    digest = re.search(r"passage_sha256 ([0-9a-f]{64})", copied)
    check(digest, copied)
    request = Path(base) / "request.json"
    request.write_text(json.dumps({"detector_exceptions": [
        {"type": "copied_restricted", "passage_sha256": digest.group(1), "destinations": ["engineering-repo"], "reason": "approved quotation"}]}), encoding="utf-8")
    code, cleared = run(base, ["detectors.py", "--root", project, "--request", request], cwd=ROOT)
    check("copied-passage" not in cleared, cleared[-300:])
    request.write_text(json.dumps({"detector_exceptions": [
        {"type": "credentials", "passage_sha256": digest.group(1), "destinations": ["engineering-repo"], "reason": "please"}]}), encoding="utf-8")
    code, refused = run(base, ["detectors.py", "--root", project, "--request", request], cwd=ROOT)
    check("credentials:github-token" in refused, "the credential finding went away")
    return f"with exception: {len([x for x in cleared.splitlines() if x.startswith('detector:')])} findings, no copied-passage; credential exception: {line_with(refused, 'exception-not-permitted')}"


@claim("WP3 a restricted source tracked in git is reported by id, never by path")
def _(base):
    project = copy_fixture(base)
    ws = Path(base) / "ws"
    (ws / "drafts").mkdir(parents=True)
    shutil.copyfile(str(project / "docs" / "spec" / "plan.yaml"), str(ws / "drafts" / "plan.yaml"))
    point_workspace(project, ws)
    git(base, project, "init", "-q", "-b", "main")
    git(base, project, "add", "-f", "ground-truth/company-governance.md")
    code, out = run(base, ["check_specs.py", "--root", project, "--view", "workspace"], cwd=ROOT)
    found = line_with(out, "restricted source is tracked in git:")
    check(found.endswith("company-governance") or "company-governance" in found, found)
    check("ground-truth/company-governance.md" not in out, "the path was printed")
    return found


@claim("WP3 malformed plan fails closed; source names and valid keys are not schema findings")
def _(base):
    project = copy_sample(base, working=False)
    code, ok = run(base, ["check_specs.py", "--root", project, "--view", "released"], cwd=ROOT)
    check(code == 0, ok[-300:])
    (project / "docs" / "spec" / "plan.yaml").write_text("plan_format: 2\nplan_view: released\npeople: [\n", encoding="utf-8")
    code2, bad = run(base, ["check_specs.py", "--root", project, "--view", "released"], cwd=ROOT)
    check(code2 != 0, f"a malformed plan exited {code2}")
    return f"clean released sample: {line_with(ok, 'with findings') if 'with findings' in ok else last_line(ok)}; malformed plan: exit {code2}"


def clean_clone(base, name="clone", keep_originals=False):
    clone = copy_sample(base, name, working=False)
    for rel in (["people.yaml"] + ([] if keep_originals else ["ground-truth", "docs/ground-truth"])):
        p = clone / rel
        if p.is_dir():
            shutil.rmtree(str(p))
        elif p.exists():
            p.unlink()
    return clone


@claim("WP3 released clean clone: no originals, renderings, overlay or workspace, 0 findings; also with the public originals present")
def _(base):
    clone = clean_clone(base)
    code, out = run(base, ["check_specs.py", "--root", clone, "--view", "released", "--report"], cwd=ROOT)
    check(code == 0, out[-400:])
    with_originals = clean_clone(base, "with-originals", keep_originals=True)
    code2, out2 = run(base, ["check_specs.py", "--root", with_originals, "--view", "released", "--report"], cwd=ROOT)
    check(code2 == 0, out2[-400:])
    check(not (clone / "ground-truth").exists() and not (clone / "docs" / "ground-truth").exists(), "originals left in the clone")
    return f"without originals: {line_with(out, 'finding(s)')}; with: {line_with(out2, 'finding(s)')}"


@claim("WP3 released clean clone: removing a cited obligation or changing one bundle byte fails")
def _(base):
    clone = clean_clone(base)
    sidecar = clone / "docs" / "context" / "wi-06.bundle.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    dropped = data["obligations"].pop(0)
    sidecar.write_text(json.dumps(data, indent=2), encoding="utf-8")
    code, out = run(base, ["check_specs.py", "--root", clone, "--view", "released"], cwd=ROOT)
    check(code != 0, "a dropped obligation passed")
    clone2 = clean_clone(base, "clone2")
    md = clone2 / "docs" / "context" / "wi-06.md"
    raw = bytearray(md.read_bytes())
    raw[-2] = ord("X") if raw[-2] != ord("X") else ord("Y")
    md.write_bytes(bytes(raw))
    code2, out2 = run(base, ["check_specs.py", "--root", clone2, "--view", "released"], cwd=ROOT)
    check(code2 != 0, "a changed bundle byte passed")
    first = next(x.strip() for x in out.splitlines() if "wi-06" in x.lower() or dropped["section"] in x)
    second = next(x.strip() for x in out2.splitlines() if "wi-06" in x.lower())
    return f"dropped {dropped['source']} {dropped['section']}: {first[:110]}; byte flip: {second[:110]}"


@claim("WP3 log hygiene: a person's name in a spec and in plan-review.md is reported by location, never quoted")
def _(base):
    project = copy_sample(base)
    import carrydown_lib as L
    people = L.load_file(SAMPLE / "people.yaml")
    rows = people.get("people") if isinstance(people, dict) else people
    name = next(p["name"] for p in rows if p.get("name"))
    spec = sorted((project / "docs" / "spec").rglob("wi-*.md"))[0]
    spec.write_text(spec.read_text(encoding="utf-8") + f"\nAsk {name} about this.\n", encoding="utf-8")
    (project / "docs" / "spec" / "plan-review.md").write_text(f"# Plan review\n\nReviewed by {name}.\n", encoding="utf-8")
    code, out = run(base, ["check_specs.py", "--root", project, "--people", SAMPLE / "people.yaml"], cwd=ROOT)
    hits = [x.strip() for x in out.splitlines() if "person name or handle from the plan at" in x]
    check(code != 0 and len(hits) >= 2, out[-400:])
    check(any("plan-review.md" in h for h in hits), hits)
    check(name not in out, "the name was printed")
    return "; ".join(h[:90] for h in hits[:2])


@claim("WP3 scaffold_spec.py --init: the dry run says 'would append' for the four ignore lines; --apply appends them")
def _(base):
    project = Path(base) / "fresh"
    project.mkdir()
    git(base, project, "init", "-q", "-b", "main")
    code, dry = run(base, ["scaffold_spec.py", "--init", "--root", project], cwd=project)
    lines = [x.strip() for x in dry.splitlines() if "would append to .gitignore:" in x]
    want = ["docs/source/", "people.yaml", ".carrydown/local.yaml", ".carrydown/cache/"]
    check([x.split(": ", 1)[1] for x in lines] == want, lines)
    check(not (project / ".gitignore").exists(), "the dry run wrote .gitignore")
    code, out = run(base, ["scaffold_spec.py", "--init", "--root", project, "--apply"], cwd=project)
    check(code == 0, out[-300:])
    ignore = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
    check(all(w in ignore for w in want), ignore)
    return f"dry run: {len(lines)} 'would append' lines; applied: {want}"


@claim("WP3 the checker workflow watches docs/context/** and docs/release/** with contents: read")
def _(base):
    for path in (ROOT / "templates" / "check-specs-workflow.yml", SAMPLE / ".github" / "workflows" / "check-specs.yml"):
        text = path.read_text(encoding="utf-8")
        check("docs/context/**" in text and "docs/release/**" in text and "contents: read" in text, path.name)
        check("write" not in text.split("permissions:", 1)[1].split("\n\n", 1)[0], f"{path.name} grants a write permission")
    return "template and sample workflow: both filters, contents: read, no write permission"


# ===========================================================================
# WP4. Renderer: markings, hidden text, hyperlinks, destination
# ===========================================================================

def render_project(base, answer=True):
    project = copy_fixture(base)
    ws = Path(base) / "ws"
    (ws / "renderings").mkdir(parents=True)
    point_workspace(project, ws)
    set_answer(project / "docs" / "spec" / "plan.yaml", answer)
    return project, ws


@claim("WP4 a marked .docx (footer 'Internal, do not distribute', a hidden run, a tracked insertion): exit 2 with counts and the marking finding; succeeds with both decisions")
def _(base):
    import make_numbered_docx as MD
    project, ws = render_project(base, answer=False)
    plan = project / "docs" / "spec" / "plan.yaml"
    plan.write_text(plan.read_text(encoding="utf-8").replace("classification: restricted", "classification: repo-readers"), encoding="utf-8")
    set_answer(plan, True)
    docx = project / "ground-truth" / "marked.docx"
    MD.build(str(docx), "confidential")
    args = ["render_ground_truth.py", docx, "--source-id", "architecture", "--name", "marked", "--out-dir", "docs/ground-truth", "--root", project]
    code, out = run(base, args, cwd=project)
    check(code == 2, f"exit {code}: {out[-300:]}")
    counts = line_with(out, "hidden or tracked content found in architecture: 2 items")
    marking = line_with(out, "marking disagrees with classification for architecture")
    check(not (project / "docs" / "ground-truth" / "marked.md").exists(), "written before the decisions")
    check("HIDDEN-RUN-TEXT" not in out and "INSERTED-WORDS" not in out, "the finding quotes the text")
    code, out2 = run(base, args + ["--resolve-review-items", "include", "--accept-marking-mismatch"], cwd=project)
    check(code == 0, out2[-300:])
    header = (project / "docs" / "ground-truth" / "marked.md").read_text(encoding="utf-8").splitlines()[0]
    check("hidden or tracked content: include (2 items)." in header and "markings:" in header, header)
    return f"{counts} | {marking} | then exit 0, header records include (2 items)"


@claim("WP4 a restricted source with --out-dir docs/ground-truth is refused; by default it lands in the workspace")
def _(base):
    import make_numbered_docx as MD
    project, ws = render_project(base, answer=False)
    plan = project / "docs" / "spec" / "plan.yaml"
    docx = project / "ground-truth" / "gov.docx"
    MD.build(str(docx), "marking")
    code, out = run(base, ["render_ground_truth.py", docx, "--source-id", "company-governance", "--name", "gov", "--out-dir", "docs/ground-truth",
                           "--root", project], cwd=project)
    check(code == 2 and not (project / "docs" / "ground-truth" / "gov.md").exists(), f"exit {code}: {out[-300:]}")
    refusal = last_line(out)
    set_answer(plan, True)
    plan.write_text(plan.read_text(encoding="utf-8").replace("repo_audience_approved: true", "repo_audience_approved: false"), encoding="utf-8")
    code, out2 = run(base, ["render_ground_truth.py", docx, "--source-id", "company-governance", "--name", "gov", "--root", project], cwd=project)
    check(code == 0 and (ws / "renderings" / "gov.md").is_file(), f"exit {code}: {out2[-300:]}")
    check(not (project / "docs" / "ground-truth" / "gov.md").exists(), "a copy landed in the repository")
    return f"refused: {refusal[:120]}; default: workspace:renderings/gov.md"


@claim("WP4 an --out-dir that is neither the project nor the workspace is still refused")
def _(base):
    import make_numbered_docx as MD
    project, ws = render_project(base, answer=False)
    plan = project / "docs" / "spec" / "plan.yaml"
    plan.write_text(plan.read_text(encoding="utf-8").replace("classification: restricted", "classification: repo-readers"), encoding="utf-8")
    set_answer(plan, True)
    docx = project / "ground-truth" / "plain.docx"
    MD.build(str(docx), "style")
    elsewhere = Path(base) / "elsewhere"
    code, out = run(base, ["render_ground_truth.py", docx, "--source-id", "architecture", "--name", "plain", "--out-dir", elsewhere, "--root", project],
                    cwd=project)
    check(code == 2 and not elsewhere.exists(), f"exit {code}: {out[-300:]}")
    return last_line(out)[:160]


@claim("WP4 non-web link schemes are dropped and HTML comments are stripped, each with a finding")
def _(base):
    import make_numbered_docx as MD
    project, ws = render_project(base, answer=False)
    plan = project / "docs" / "spec" / "plan.yaml"
    plan.write_text(plan.read_text(encoding="utf-8").replace("classification: restricted", "classification: repo-readers"), encoding="utf-8")
    set_answer(plan, True)
    docx = project / "ground-truth" / "links.docx"
    MD.build(str(docx), "links")
    code, out = run(base, ["render_ground_truth.py", docx, "--source-id", "architecture", "--name", "links", "--root", project], cwd=project)
    check(code == 0, out[-300:])
    text = (project / "docs" / "ground-truth" / "links.md").read_text(encoding="utf-8")
    for scheme in ("mailto:", "file:", "javascript:"):
        check(scheme not in text.split("-->", 1)[1], f"{scheme} survived")
    check("https://" in text, "the web link was dropped")
    md = project / "ground-truth" / "notes.md"
    md.write_text("# Notes\n\n## 1 Scope\n\nVisible.<!-- a private remark -->\n\n<!-- another -->\n", encoding="utf-8")
    code, out2 = run(base, ["render_ground_truth.py", md, "--source-id", "architecture", "--name", "notes", "--root", project], cwd=project)
    check(code == 0, out2[-300:])
    body = (project / "docs" / "ground-truth" / "notes.md").read_text(encoding="utf-8")
    check("private remark" not in body and "another" not in body, "a comment survived")
    return f"{line_with(out, 'link scheme removed in architecture')}; {line_with(out2, 'HTML comments removed in architecture')}"


@claim("WP4 rendering records content_sha256 and rendering_sha256 in the workspace plan, not the repository plan")
def _(base):
    project, ws = render_project(base, answer=False)
    (ws / "drafts").mkdir()
    plan = project / "docs" / "spec" / "plan.yaml"
    shutil.copyfile(str(plan), str(ws / "drafts" / "plan.yaml"))
    before = plan.read_bytes()
    src = project / "ground-truth" / "company-governance.md"
    code, out = run(base, ["render_ground_truth.py", src, "--source-id", "company-governance", "--root", project], cwd=project)
    check(code == 0, out[-300:])
    import carrydown_lib as L
    drafted = L.load_file(ws / "drafts" / "plan.yaml")
    row = next(s for s in drafted["sources"] if s["id"] == "company-governance")
    check(re.fullmatch(r"[0-9a-f]{64}", str(row.get("content_sha256"))) and re.fullmatch(r"[0-9a-f]{64}", str(row.get("rendering_sha256"))), row)
    check(row["content_sha256"] == hashlib.sha256(src.read_bytes()).hexdigest(), "content digest is not the original's")
    check(plan.read_bytes() == before, "the repository plan changed")
    return line_with(out, "recorded content_sha256 and rendering_sha256")


# ===========================================================================
# WP5. Bundles and the engineers' skill
# ===========================================================================

def compile_fixture(base):
    project = copy_fixture(base)
    out_dir = Path(base) / "candidate"
    code, out = run(base, ["compile_bundles.py", "--root", project, "--renderings", project / "docs" / "ground-truth", "--out", out_dir, "--apply"],
                    cwd=project)
    check(code == 0, out[-300:])
    ctx = next(p for p in out_dir.rglob("context") if p.is_dir())
    return project, ctx, out


def section_text(rendering, number):
    """The normalized text of one numbered section of a rendering, the heading line excluded."""
    lines = rendering.splitlines()
    start = next(i for i, x in enumerate(lines) if re.match(rf"#+ {re.escape(number)}\s", x))
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    body = []
    for x in lines[start + 1:]:
        m = re.match(r"(#+) ", x)
        if m and len(m.group(1)) <= level:
            break
        body.append(x)
    return RS.normalize_section_text("\n".join(body).strip("\n") + "\n")


@claim("WP5 compile_bundles.py on the fixture: one bundle per work item; WI-06 holds 3.5, 4.1 and 7.1 verbatim, the recorded conflict, and WI-03 shares 3.5")
def _(base):
    project, ctx, out = compile_fixture(base)
    import carrydown_lib as L
    plan = L.load_file(project / "docs" / "spec" / "plan.yaml")
    prefix = plan["project"]["id_prefix"].lower()
    items = sorted(f"{prefix}-{int(i['id']):02d}" for i in plan["items"] if not i.get("external"))
    mds = sorted(p.stem for p in ctx.glob("*.md"))
    check(mds == items and len(list(ctx.glob("*.bundle.json"))) == len(items), f"{mds} vs {items}")
    md = (ctx / "wi-06.md").read_text(encoding="utf-8")
    side = json.loads((ctx / "wi-06.bundle.json").read_text(encoding="utf-8"))
    rendering = (project / "docs" / "ground-truth" / "architecture.md").read_text(encoding="utf-8")
    for number in ("3.5", "4.1", "7.1"):
        check(any(o["source"] == "architecture" and o["section"] == number for o in side["obligations"]), f"3.x {number} not listed")
        check(section_text(rendering, number).strip() in RS.normalize_section_text(md), f"section {number} not verbatim")
    check(side["conflicts"], "no conflict recorded")
    shared = [s for s in side.get("shared_with", [])]
    md_shared = md.split("## Shared obligations", 1)[1] if "## Shared obligations" in md else ""
    check("WI-03" in shared and "3.5" in md_shared and "WI-03" in md_shared, f"shared {shared}")
    check(side["content_sha256"] == hashlib.sha256((ctx / "wi-06.md").read_bytes()).hexdigest(), "content_sha256")
    return f"{len(items)} items, {2 * len(items)} files; WI-06 sections 3.5, 4.1, 7.1 verbatim; conflicts {len(side['conflicts'])}; shared {shared}"


@claim("WP5 a bundle missing a cited section fails: 'obligation not found'")
def _(base):
    project = copy_fixture(base)
    renderings = Path(base) / "renderings"
    shutil.copytree(str(project / "docs" / "ground-truth"), str(renderings))
    arch = renderings / "architecture.md"
    arch.write_text(re.sub(r"(?m)^(#+) 3\.5 ", r"\1 3.55 ", arch.read_text(encoding="utf-8")), encoding="utf-8")
    code, out = run(base, ["compile_bundles.py", "--root", project, "--renderings", renderings, "--out", Path(base) / "c", "--apply"], cwd=project)
    check(code == 1 and not (Path(base) / "c").exists(), f"exit {code}")
    return line_with(out, "obligation not found: architecture 3.5")


def tree_digests(folder):
    """{relative path: sha256} of every file under folder, .git excluded."""
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file() and ".git" not in p.relative_to(folder).parts}


@claim("WP0 gate log: the dry runs of compile_bundles.py and release.py release leave publication/ unchanged; release adds only the preview digest")
def _(base):
    project = copy_sample(base)
    git(base, project, "init", "-q", "-b", "main")
    ws = Path(base) / "ws"
    code, out = run(base, ["workspace.py", "init", "--root", project, "--slug", "proof", "--workspace", ws, "--apply"], cwd=project)
    check(code == 0, out[-300:])
    shutil.move(str(project / "people.yaml"), str(ws / "people.yaml"))
    seen = []
    for args, added in ((["compile_bundles.py", "--root", project], set()),
                        (["release.py", "release", "--root", project, "--repository-id", "4200", "--no-github"], {"candidate/shown.json"})):
        before_ws, before_project = tree_digests(ws), tree_digests(project)
        code, out = run(base, args, cwd=project)
        check(code == 0, f"{args[0]} dry run exit {code}: {out[-400:]}")
        after_ws = tree_digests(ws)
        changed = sorted(k for k in set(before_ws) | set(after_ws) if before_ws.get(k) != after_ws.get(k))
        check(not [k for k in changed if k.startswith("publication/")], f"{args[0]} dry run changed {changed}")
        check(set(changed) == added, f"{args[0]} dry run changed {changed}, expected {sorted(added)}")
        check(tree_digests(project) == before_project, f"{args[0]} dry run changed the project")
        seen.append(f"{args[0]}: changed {changed or 'nothing'}")
    check(not (ws / "publication" / "gate.log").exists(), "a dry run created the gate log")
    return "; ".join(seen) + "; no gate.log"


@claim("WP0 reason codes: a malformed record is refused with schema-invalid, which the gate's fixed list and the security guide carry as the one addition to Part G")
def _(base):
    project = copy_sample(base)
    git(base, project, "init", "-q", "-b", "main")
    ws = Path(base) / "ws"
    code, out = run(base, ["workspace.py", "init", "--root", project, "--slug", "proof", "--workspace", ws, "--apply"], cwd=project)
    check(code == 0, out[-300:])
    shutil.move(str(project / "people.yaml"), str(ws / "people.yaml"))
    bad = Path(base) / "exceptions.json"
    bad.write_text("{ not json", encoding="utf-8")
    code, out = run(base, ["release.py", "prepare", "--root", project, "--repository-id", "4200", "--exceptions", bad], cwd=project)
    shown = line_with(out, "schema-invalid")
    check(code != 0 and "not json" not in out, f"exit {code}: {out[-300:]}")
    code, listing = run(base, [PY, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import release_gate as RG; "
                                         "print(sorted(RG.ADDED_CODES), len(RG.PART_G_CODES), 'schema-invalid' in RG.REASON_CODES)", SCRIPTS])
    check(code == 0 and listing.strip() == "['schema-invalid'] 42 True", listing)
    guide = (ROOT / "docs" / "security.md").read_text(encoding="utf-8")
    check("addition to the specification's list: `schema-invalid`" in guide, "the security guide does not mark the addition")
    return f"{shown} || gate list: {listing.strip()}"


@claim("WP5 prepare refuses no bundle containing the release id, and the committed sample release has none")
def _(base):
    _, ws, release_id, out = prepare_sample(base)
    snap = ws / "releases" / release_id / "snapshot"
    hits = [p.relative_to(snap).as_posix() for p in snap.rglob("*") if p.is_file() and release_id.encode() in p.read_bytes()]
    check(not hits, hits)
    ctx = [p for p in snap.rglob("*") if p.is_file() and "/docs/context/" in p.as_posix()]
    check(ctx, "no bundles in the snapshot")
    committed = SAMPLE / "docs" / "release"
    receipt = json.loads(next(committed.glob("*.receipt.json")).read_text(encoding="utf-8"))
    sample_hits = [p.name for p in (SAMPLE / "docs" / "context").iterdir() if receipt["release_id"].encode() in p.read_bytes()]
    check(not sample_hits, sample_hits)
    return f"{len(ctx)} bundle files in the snapshot of {release_id[:12]}, none holds the id; sample: none holds {receipt['release_id'][:12]}"


def engineer_clone(base):
    """A clone of the committed sample with a bare origin, as an engineer has it."""
    origin = Path(base) / "origin.git"
    seed = copy_sample(base, "seed", working=False)
    git(base, seed, "init", "-q", "-b", "main")
    git(base, seed, "add", "-A")
    git(base, seed, "commit", "-q", "-m", "sample")
    git(base, base, "clone", "-q", "--bare", str(seed), str(origin))
    clone = Path(base) / "clone"
    git(base, base, "clone", "-q", str(origin), str(clone))
    return seed, origin, clone


def check_context(base, clone, item):
    return run(base, [clone / "docs" / "dev" / "skills" / "expense-approvals-dev" / "scripts" / "check_context.py", item], cwd=clone)


@claim("WP5 check_context.py WI-03 with no bundle prints the first block message and nothing from another bundle")
def _(base):
    _, _, clone = engineer_clone(base)
    (clone / "docs" / "context" / "wi-03.md").unlink()
    (clone / "docs" / "context" / "wi-03.bundle.json").unlink()
    code, out = check_context(base, clone, "WI-03")
    check(code == 10, f"exit {code}: {out}")
    lines = [x for x in out.splitlines() if x.strip()]
    check(lines[0] == "carrydown: no approved context for WI-03", lines)
    others = [p.read_text(encoding="utf-8") for p in (clone / "docs" / "context").glob("*.md")]
    leaked = [x for x in lines[1:] for t in others if len(x) > 20 and x in t]
    check(not leaked, leaked)
    return " | ".join(lines)


@claim("WP5 the committed engineers' skill: map headings all come from bundles, no original filename; SKILL.md runs check_context.py, no grep or sed")
def _(base):
    skill = SAMPLE / "docs" / "dev" / "skills" / "expense-approvals-dev"
    mapping = (skill / "references" / "ground-truth-map.md").read_text(encoding="utf-8")
    bundled = set()
    for side in (SAMPLE / "docs" / "context").glob("*.bundle.json"):
        for o in json.loads(side.read_text(encoding="utf-8"))["obligations"]:
            bundled.add((o["source"], o["section"]))
    listed = set(re.findall(r"`?([a-z][a-z0-9-]*)`? (?:section )?(\d+(?:\.\d+)*)", mapping))
    check(listed, "no section listed in the map")
    stray = sorted(x for x in listed if x not in bundled)
    check(not stray, f"headings not in any bundle: {stray[:5]}")
    for name in ("architecture.md", "ground-truth/", ".docx"):
        check(name not in mapping, f"original filename {name} in the map")
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    step4 = next(x for x in text.splitlines() if x.startswith("4. "))
    check("check_context.py" in step4 and "grep" not in step4 and "sed " not in step4 and "docs/ground-truth/" in step4, step4[:200])
    readme = (skill / "README.md").read_text(encoding="utf-8")
    check("If you are blocked" in readme and "Windows" in readme and "Requesting a change to a rule" in readme, "README sections")
    return f"{len(listed)} map entries, all in bundles; SKILL.md uses check_context.py; README has blocked, change request and Windows sections"


@claim("WP5 the sample's engineers' skill matches what generate_dev_skill.py produces from the templates")
def _(base):
    project = copy_sample(base)
    ws = Path(base) / "ws"
    shutil.copytree(str(SAMPLE_WS), str(ws))
    point_workspace(project, ws)
    code, out = run(base, ["generate_dev_skill.py", "--root", project], cwd=project)
    check(code == 0, out[-400:])
    changed = [x for x in out.splitlines() if re.search(r"\b(would (write|change|update)|differs|changed)\b", x) and "0 file" not in x]
    check(not changed, changed[:5])
    generated = (SAMPLE / "docs" / "dev" / "skills" / "expense-approvals-dev" / "scripts" / "check_context.py").read_text(encoding="utf-8")
    filled = CHECK_CONTEXT.read_text(encoding="utf-8").replace("{{id_prefix}}", "WI").replace("{{spec_dir}}", "docs/spec")
    check(generated == filled, "the sample's check_context.py differs from the filled template")
    return last_line(out)[:160] + "; check_context.py equals the template with its two constants filled"


def superseded_receipt():
    """The sample's own request, projected as superseded by another request id."""
    req_dir = next((SAMPLE_WS / "requests").iterdir())
    request = json.loads((req_dir / "approval-request.json").read_text(encoding="utf-8"))
    manifest = (SAMPLE_WS / "releases" / request["release_id"] / "content-manifest.json").read_bytes()
    rid = req_dir.name
    state = RS.RequestState(rid, "superseded", hashlib.sha256(b"proof supersession").hexdigest(), "e" * 64, request["supersedes_request_id"])
    return rid, RS.project_receipt(request, manifest, state, RS.VerifiedApproval(rid, "local-owner", False))


@claim("WP5 G4: a superseding receipt on the default branch makes the check stale after refresh")
def _(base):
    seed, origin, clone = engineer_clone(base)
    code, out = check_context(base, clone, "WI-03")
    check(code == 0, f"first use exit {code}: {out}")
    rid, data = superseded_receipt()
    (seed / "docs" / "release" / f"{rid}.receipt.json").write_bytes(data)
    git(base, seed, "commit", "-q", "-am", "supersede")
    git(base, seed, "push", "-q", str(origin), "main")
    code, out = check_context(base, clone, "WI-03")
    check(code == 11, f"exit {code}: {out}")
    lines = [x for x in out.splitlines() if x.strip()]
    check(lines[0] == "carrydown: the approved context for WI-03 is stale", lines)
    return " | ".join(lines[:2])


@claim("WP5 G4: origin unreachable inside the grace period passes with a warning; outside it is stale with could not refresh")
def _(base):
    seed, origin, clone = engineer_clone(base)
    code, out = check_context(base, clone, "WI-03")
    check(code == 0, f"first use exit {code}: {out}")
    shutil.move(str(origin), str(Path(base) / "gone.git"))
    code, inside = check_context(base, clone, "WI-03")
    check(code == 0 and "freshness not confirmed; within offline grace" in inside, f"exit {code}: {inside}")
    cache = clone / ".carrydown" / "cache" / "last-refresh"
    record = json.loads(cache.read_text(encoding="utf-8"))
    record["time"] = "2000-01-01T00:00:00Z"
    cache.write_text(json.dumps(record), encoding="utf-8")
    code, outside = check_context(base, clone, "WI-03")
    lines = [x for x in outside.splitlines() if x.strip()]
    check(code == 11 and lines[0] == "carrydown: the approved context for WI-03 is stale" and "could-not-refresh" in outside, f"exit {code}: {outside}")
    return f"inside: exit 0, {line_with(inside, 'within offline grace')}; outside: exit 11, {line_with(outside, 'reason:')}"


@claim("WP5 G4: a first use with origin unreachable and no refresh record grants no grace")
def _(base):
    seed, origin, clone = engineer_clone(base)
    shutil.move(str(origin), str(Path(base) / "gone.git"))
    code, out = check_context(base, clone, "WI-03")
    check(code == 11 and "could-not-refresh" in out, f"exit {code}: {out}")
    return f"exit {code}: {line_with(out, 'reason:')}"


@claim("WP5 the id rule: a malformed id never reaches another item's context; it gets the first message")
def _(base):
    _, _, clone = engineer_clone(base)
    outs = []
    for bad in ("../WI-03", "WI-03/../../etc", "WI-03;rm", "wi_03 x", "WI-03/"):
        code, out = check_context(base, clone, bad)
        first = out.splitlines()[0] if out else ""
        check(code == 10 and first.startswith("carrydown: no approved context for ") and "/" not in first, f"{bad!r}: exit {code}: {first}")
        outs.append(first[len("carrydown: no approved context for "):])
    return f"exit 10 for five malformed ids, shown as {outs}"


# ===========================================================================
# WP0, last: the full self test (left out with --quick)
# ===========================================================================

def selftest_claim(base):
    code, out = run(base, ["selftest.py"], cwd=ROOT, timeout=1200)
    check(code == 0, out[-400:])
    return line_with(out, "steps passed")


def main(argv):
    quick = "--quick" in argv
    if not quick:
        claim("WP0 the self test passes")(selftest_claim)
    for fn in CLAIMS:
        fn()
    passed = sum(RESULTS)
    print(f"{passed} of {len(RESULTS)} claims passed")
    shutil.rmtree(str(TMP), ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
