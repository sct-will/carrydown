#!/usr/bin/env python3
"""A re-runnable proof of the work package 8 and 9 acceptance claims. Standard library only.

Run it from the repository root, with no token and no network:

  python3 tests/proof_wp8_wp9.py

For each claim it runs the real scripts, in a subprocess (release.py, github_sync.py, github_project.py,
github_repair.py, generate_dev_skill.py, check_context.py, grep) or in this process against the local mock
of GitHub (tests/mock/mockgh.py) and the in-memory model of the organization (tests/mock/fake_evidence.py),
and prints one line, PASS or FAIL, then the line it observed that proves the claim. It does not read test
results or file dates. It exits 0 only when every claim passes.

One acceptance bullet of work package 9 is not claimed here: "with engineer_edits: request-only, the
verifier fails a pull request that edits Decisions recorded" belongs to the verifier (work package 7). This
script proves the owner side and the skill side of change requests.
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
import time
import traceback
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)
import carrydown_lib as L  # noqa: E402
import fake_evidence as FE  # noqa: E402
import github_client as G  # noqa: E402
import github_project as GP  # noqa: E402
import github_repair as GR  # noqa: E402
import github_sync as GS  # noqa: E402
import mockgh  # noqa: E402
import release as R  # noqa: E402
import release_assemble as A  # noqa: E402
import release_fixture as F  # noqa: E402
import release_github as RGH  # noqa: E402
import release_payloads as RP  # noqa: E402
import release_sync as RSY  # noqa: E402
import release_verify as V  # noqa: E402
import restricted_fixture as RF  # noqa: E402

PY = sys.executable
RESULTS = []
CLAIMS = []
TMP = Path(tempfile.mkdtemp(prefix="carrydown-proof89-"))
GOLDEN = "11e4320d8460658ccbf26787509e3812705a00c318b4f930d47cd4b2f933836c"
REPO = "sct-will/carrydown-sample"
ENGINEERING = {"id": "engineering", "host": "github.com", "repository_id": 4200, "repository": "acme/expense-approvals"}
BOARD = {"id": "board", "host": "github.com", "repository_id": 4200, "owner_id": 4400, "project_id": "PVT_example"}


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


def check(condition, message="condition failed"):
    if not condition:
        raise AssertionError(message)


def last_line(text, contains=None):
    lines = [x for x in text.splitlines() if x.strip() and (contains is None or contains in x)]
    check(lines, f"no line containing {contains!r} in: {text[-200:]!r}")
    return lines[-1].strip()


def tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(folder).parts}


def script(name, *args, cwd=None, env=None, timeout=300):
    return subprocess.run([PY, str(ROOT / "scripts" / name)] + [str(a) for a in args], cwd=str(cwd or ROOT), capture_output=True, text=True,
                          env=env or dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=timeout)


class Mock:
    """The local mock of GitHub, with the token, the time and the base address replaced for this process."""

    def __init__(self, base):
        mockgh.S.__init__()
        mockgh.S.repos.add(REPO)
        mockgh.S.repo_ids = {REPO: 4200}
        self.server, self.url = mockgh.start()
        self.stack = contextlib.ExitStack()
        env = {"CARRYDOWN_GITHUB_TOKEN": "ghp_" + "Z" * 36, "HOME": str(base), "USERPROFILE": str(base)}
        for p in (mock.patch.dict(os.environ, env), mock.patch.object(time, "sleep", lambda s: None),
                  mock.patch.object(RGH.GitHubEvidenceReader, "HOST_OVERRIDE", "github.com"),
                  mock.patch.object(G.GitHub.__init__, "__defaults__", (self.url, 0.0, None))):
            self.stack.enter_context(p)

    def close(self):
        self.stack.close()
        self.server.shutdown()
        self.server.server_close()

    @staticmethod
    def writes():
        return [(m, p) for m, p in mockgh.S.log if m != "GET" and p != "/graphql"] + [("GRAPHQL", op) for op in mockgh.S.gql if op in mockgh.MUTATIONS]


def exported(base, **kw):
    """A copy of the sample with work item 7 restricted (drafts in the private workspace), released through the
    real release.py commands, as the owner would."""
    yp = RF.restricted_project(base, **kw)
    code, out, err = yp.prepare()
    check(code == 0, out + err)
    check(yp.approve()[0] == 0)
    code, out, err = yp.export()
    check(code == 0, out + err)
    request = R.load_request(yp.workspace, yp.request_id)
    yp.snapshot = yp.workspace / "releases" / request["release_id"] / "snapshot"
    return yp


# ---------------------------------------------------------------------------
# WP8: projections
# ---------------------------------------------------------------------------

@claim("WP8 a repo-readers-only release yields today's issue and sub-epic bodies byte for byte (the sample's --show-body output)")
def _(base):
    plan, _ = L.load_plan(F.SAMPLE / "docs/spec/plan.yaml", F.SAMPLE)
    h = hashlib.sha256()
    for key in [str(it["id"]) for it in plan["items"]] + [f"M{m['number']}" for m in plan["milestones"]]:
        out = script("github_sync.py", "--root", F.SAMPLE, "--offline", "--show-body", key)
        check(out.returncode == 0, out.stderr)
        h.update(out.stdout.encode("utf-8"))
    check(h.hexdigest() == GOLDEN, h.hexdigest())
    asm = A.assemble(F.SAMPLE, with_board=False)
    check(asm.problems == [] and asm.link_items == ())
    return f"sha256 of the 14 bodies {h.hexdigest()[:16]}... equals the recorded digest; no issue of the release uses the links projection"


@claim("WP8 a release containing a restricted source yields issue payloads with seven headings and no acceptance text")
def _(base):
    np_ = F.NoProject(base)
    asm = A.assemble(np_.root, with_board=False)
    check(asm.problems == [], asm.problems)
    check(asm.link_items == ("WI-06",), asm.link_items)
    body = json.loads(asm.files["payloads/issue/WI-06.json"])["body"]
    heads = [ln[4:] for ln in body.split("\n") if ln.startswith("### ")]
    check(heads == RP.SEVEN, heads)
    spec = next((np_.workspace / "drafts" / "docs/spec").rglob("wi-06-*.md")).read_text(encoding="utf-8")
    for name in ("Acceptance criteria", "Evidence of completion", "Integration points"):
        section = re.search(rf"(?ms)^## {name}\n(.*?)(?=^## |\Z)", spec).group(1)
        for line in [x.strip() for x in section.splitlines() if len(x.strip()) >= 20]:
            check(line not in body, f"{name} text is in the issue body")
    other = json.loads(asm.files["payloads/issue/WI-03.json"])["body"]
    check("tests/routing.engine.test.js" in other and "#acceptance-criteria" not in other)
    return f"WI-06 headings {len(heads)} of 7, {len(body.splitlines())} lines, links {re.findall(r'#[a-z-]+', body)[:3]}; WI-03 keeps its text"


# ---------------------------------------------------------------------------
# WP8: preflight
# ---------------------------------------------------------------------------

def request(audience="repo-readers", targets=(ENGINEERING, BOARD)):
    return {"receipt_template": {"audience": audience, "targets": [dict(t) for t in targets]}}


def code_of(fn):
    try:
        out = fn()
    except RSY.PublicationRefused as e:
        return e.code
    return "ok" if out else "empty"


@claim("WP8 preflight against a fake public repository refuses a repo-readers release, and proceeds for a public release")
def _(base):
    w = FE.World()
    w.reader.repos[4200].update(private=False, visibility="public")
    w.reader.projects["PVT_example"]["public"] = True
    enr = w.enrollment()
    refused = code_of(lambda: RSY.publication_preflight(None, None, enr, request("repo-readers"), reader=w.reader))
    check(refused == "audience-visibility-mismatch", refused)
    out = RSY.publication_preflight(None, None, enr, request("public"), reader=w.reader)
    check(out.visibility == {"engineering": "public", "board": "public"})
    return f"repo-readers: {refused}; public: {last_line(chr(10).join(out.lines), 'acme/expense-approvals')}"


@claim("WP8 a private board with an extra reader, a changed node id, a wrong repository id or no access evidence refuses; a membership change ends stale evidence")
def _(base):
    seen = []

    def fresh():
        w = FE.World()
        return w, w.reader, w.enrollment()
    w, r, enr = fresh()
    r.projects["PVT_example"]["reader_ids"].append(5555)
    seen.append("extra reader=" + code_of(lambda: RSY.publication_preflight(None, None, enr, request(), reader=r)))
    w, r, enr = fresh()
    local = V.local_policy({"repo_audience_approved": True}, "acme/expense-approvals")
    other = dict(BOARD, project_id="PVT_other")
    seen.append("changed node id=" + code_of(lambda: RSY.publication_preflight(None, None, local, request(targets=(ENGINEERING, other)), reader=r)))
    seen.append("wrong repository id=" + code_of(lambda: RSY.publication_preflight(None, None, local, request(targets=(dict(ENGINEERING, repository_id=7777),)), reader=r)))
    w, r, enr = fresh()
    r.projects["PVT_example"]["reader_ids"] = None
    seen.append("no access evidence=" + code_of(lambda: RSY.publication_preflight(None, None, enr, request(), reader=r)))
    project = r.projects["PVT_example"]
    people = [p["id"] for p in r.collaborators_by_repo[4200]]
    att = {"component": "destination-readers", "by_id": FE.ADMIN[0], "at": V.utc_text(V.clock() - 3600), "expires_at": V.utc_text(V.clock() + 86400),
           "subject": RSY.board_subject(BOARD, project["repository_ids"], people, project["public"]), "note": "same readers as the repository"}
    enr = w.update_policy(lambda e: e["attestations"].append(att))
    seen.append("attested=" + code_of(lambda: RSY.publication_preflight(None, None, enr, request(), reader=r)))
    r.collaborators_by_repo[4200].append({"id": 4321, "login": "newcomer", "permission": "read"})
    seen.append("after a membership change=" + code_of(lambda: RSY.publication_preflight(None, None, enr, request(), reader=r)))
    want = ["extra reader=audience-visibility-mismatch", "changed node id=target-identity-mismatch", "wrong repository id=target-identity-mismatch",
            "no access evidence=destination-access-not-verified", "attested=ok", "after a membership change=destination-access-not-verified"]
    check(seen == want, seen)
    return "; ".join(seen)


@claim("WP8 the publishing commands refuse a public repository or a bad board before any API write, and --preflight writes nothing")
def _(base):
    m = Mock(base)
    try:
        yp = F.YesProject(base / "p", board=True, board_project_id=mockgh.add_project("Expense approvals plan")["id"])
        yp.release()
        mockgh.S.private = False
        seen = []
        for name, runner, args in (("github_sync --apply", GS.run, ["--apply"]), ("github_sync --preflight", GS.run, ["--preflight"]),
                                   ("github_project --apply", GP.run, ["--apply"])):
            code, out, err = F.run(runner, ["--root", str(yp.root)] + ([] if runner is GP.run else ["--skip-check"]) + args)
            check(code == 1 and "audience-visibility-mismatch" in out + err, f"{name}: {code} {out[-120:]}{err[-120:]}")
            seen.append(f"{name}: {last_line(out + err, 'audience-visibility-mismatch')[-60:]}")
        check(m.writes() == [], m.writes())
        mockgh.S.private = True
        code, out, err = F.run(GS.run, ["--root", str(yp.root), "--skip-check", "--preflight"])
        check(code == 0 and "preflight passed" in out and m.writes() == [], out + err)
        return f"{seen[0]} || GitHub writes: {len(m.writes())} || {last_line(out, 'preflight passed')[:70]}"
    finally:
        m.close()


@claim("WP8 a public derivative at its exact approved public target succeeds, and --verify reports a visibility change since publication")
def _(base):
    m = Mock(base)
    try:
        board = mockgh.add_project("Expense approvals plan")
        yp = F.YesProject(base / "p", board=True, board_project_id=board["id"])
        check(yp.prepare("--audience", "public")[0] == 0 and yp.approve()[0] == 0 and yp.export()[0] == 0)
        mockgh.S.private = False
        board["public"] = True
        code, out, err = F.run(GS.run, ["--root", str(yp.root), "--skip-check", "--apply"])
        check(code == 0 and "a public release" in out, out + err)
        issues = len(mockgh.S.issues)
        mockgh.S.private = True
        board["public"] = False
        code, out, err = F.run(GS.run, ["--root", str(yp.root), "--skip-check", "--verify"])
        check(code == 1, out + err)
        return f"{issues} issues created on the public repository; verify: {last_line(out, 'CHANGED')[:100]}"
    finally:
        m.close()


@claim("WP8 --allow-public is gone from github_sync.py, github_project.py and github_repair.py")
def _(base):
    seen = []
    for name in ("github_sync.py", "github_project.py", "github_repair.py"):
        out = script(name, "--root", F.SAMPLE, "--allow-public")
        check(out.returncode == 2 and "unrecognized arguments: --allow-public" in out.stderr, f"{name}: {out.returncode} {out.stderr[-100:]}")
        check("allow-public" not in script(name, "--help").stdout)
        seen.append(name)
    return "all three exit 2 with: " + last_line(out.stderr, "unrecognized")


# ---------------------------------------------------------------------------
# WP8: inventories and reports
# ---------------------------------------------------------------------------

@claim("WP8 github_sync --inventory reports unmanaged text for a hand-edited legacy body, proposes no rewrite and writes nothing")
def _(base):
    m = Mock(base)
    try:
        root = base / "legacy"
        shutil.copytree(F.SAMPLE, root)
        F.strip_handling(root)
        args = ["--root", str(root), "--repo", REPO, "--skip-check"]
        code, out, err = F.run(GS.run, args + ["--apply", "--create-epic"])
        check(code == 0, out + err)
        issue = next(i for i in mockgh.S.issues if "<!-- carrydown:WI-03 -->" in (i.get("body") or ""))
        issue["body"] = "Written by hand before carrydown existed, SECRET-LEGACY-TEXT.\n\n<!-- carrydown:WI-03 -->"
        before = json.dumps(mockgh.S.issues, sort_keys=True)
        mark = len(mockgh.S.log)
        code, out, err = F.run(GS.run, args + ["--inventory"])
        check(code == 0, out + err)
        line = last_line(out, "WI-03 #")
        check("unmanaged text present" in line and "SECRET-LEGACY-TEXT" not in out)
        check("This report proposes no rewrite." in out and "replacing the region does not remove it" in out)
        check([x for x in mockgh.S.log[mark:] if x[0] != "GET"] == [] and json.dumps(mockgh.S.issues, sort_keys=True) == before)
        return line[:140]
    finally:
        m.close()


@claim("WP8 issue_drift and find print the plan key, the issue number and a digest, never the body or the title GitHub holds")
def _(base):
    m = Mock(base)
    try:
        root = base / "legacy"
        shutil.copytree(F.SAMPLE, root)
        F.strip_handling(root)
        args = ["--root", str(root), "--repo", REPO, "--skip-check"]
        check(F.run(GS.run, args + ["--apply", "--create-epic"])[0] == 0)
        issue = next(i for i in mockgh.S.issues if "<!-- carrydown:WI-04 -->" in (i.get("body") or ""))
        issue["title"] = "ZEBRA-TITLE-4409"
        issue["body"] = "<!-- carrydown-managed:start -->\nZEBRA-BODY-7731\n<!-- carrydown-managed:end -->\n\n<!-- carrydown:WI-04 -->\n"
        code, out, err = F.run(GS.run, args + ["--verify"])
        check(code == 1 and "ZEBRA" not in out + err, out[-300:])
        drift = last_line(out, "managed body and marker")
        (root / "docs/spec/github-issues.json").unlink()
        twin = mockgh.S.add_issue("twin ZEBRA-TITLE-1", "ZEBRA-BODY-1\n\n<!-- carrydown:WI-04 -->", ["expense-approvals"], repository=REPO)
        code, out, err = F.run(GS.run, args + ["--verify"])
        number = twin["number"]
        check("ambiguous issue identity" in out + err and "ZEBRA" not in out + err and f"WI-04 | #{number}" in out + err)
        return f"{drift} || {last_line(out + err, f'WI-04 | #{number}')}"
    finally:
        m.close()


@claim("WP8 release.py inventory lists tracked originals, staffing fields and history, says history cannot be rewritten, and writes nothing")
def _(base):
    root = base / "legacy"
    shutil.copytree(F.SAMPLE, root)
    F.strip_handling(root)
    (root / "docs" / "source").mkdir(parents=True)
    (root / "docs" / "source" / "architecture.docx").write_bytes(b"original")
    F.init_git(root)
    F.sh(["git", "add", "-A"], root)
    F.sh(["git", "commit", "-q", "-m", "legacy project"], root)
    F.sh(["git", "rm", "-q", "-r", "docs/source"], root)
    F.sh(["git", "commit", "-q", "-m", "drop the original"], root)
    before = (tree(root), F.sh(["git", "status", "--porcelain"], root).stdout, F.sh(["git", "rev-list", "--all", "--count"], root).stdout)
    out = script("release.py", "inventory", "--root", root)
    check(out.returncode == 0, out.stderr)
    after = (tree(root), F.sh(["git", "status", "--porcelain"], root).stdout, F.sh(["git", "rev-list", "--all", "--count"], root).stdout)
    check(before == after, "the inventory changed something")
    text = out.stdout
    check("people:tamsin:allocation in docs/spec/plan.yaml" in text and "people.yaml is tracked" in text)
    check(re.search(r"removed since, still in history: docs/source/architecture\.docx", text))
    check("Carrydown cannot rewrite git history." in text and "docs.github.com" in text)
    return last_line(text, "removed since")[:120]


@claim("WP8 the publishing skill runs the preflight before any instruction to commit or push, and starts migration with the inventory")
def _(base):
    text = (ROOT / "skills/carrydown-plan-to-github/SKILL.md").read_text(encoding="utf-8")
    pre = text.index("github_sync.py --root . --preflight")
    first_git = text.index("git status --porcelain docs/spec")
    inventory = text.index("release.py inventory --root .")
    apply_at = text.index("github_sync.py --root . --repo owner/name --create-epic --apply")
    check(pre < first_git < apply_at, (pre, first_git, apply_at))
    check(inventory < pre, "the inventory is not the first migration step")
    check("Do not ask the user to commit or push anything before the preflight has passed." in text)
    return f"--preflight at character {pre}, the commit and push check at {first_git}, the first --apply at {apply_at}; the inventory comes first at {inventory}"


# ---------------------------------------------------------------------------
# WP9: restricted items
# ---------------------------------------------------------------------------

@claim("WP9 a restricted item exports a plan without it, an external item with exactly the owner's summary, and no bundle, spec or payload; grep finds nothing")
def _(base):
    yp = exported(base / "a")
    snap = yp.snapshot
    plan, problems = L.plan_from_data(L.loads((snap / "repo/docs/spec/plan.yaml").read_text(encoding="utf-8")), "released plan", None, "released")
    check(problems == [] and 7 not in [i["id"] for i in plan["items"]])
    check([r for r in plan["external"]["items"] if r["id"] == 7] == [{"id": 7, "label": RF.SUMMARY}])
    nine = next(i for i in plan["items"] if i["id"] == 9)
    check(nine["depends"] == [] and nine["external_input"].endswith(RF.SUMMARY))
    names = [p.name for p in snap.rglob("*") if p.is_file()]
    check(not [n for n in names if "wi-07" in n.lower() or "audit-log" in n])
    spec = (yp.drafts / "docs/spec/m3-enforce-policy/wi-07-audit-log.md").read_text(encoding="utf-8")
    others = "\n".join(p.read_text(encoding="utf-8") for p in (yp.drafts / "docs/spec").rglob("wi-*.md") if "wi-07" not in p.name)
    approved = "\n".join(f.read_text(encoding="utf-8") for f in (snap / "repo/docs/context").glob("*.md"))     # source text the bundles quote
    lines = [x.strip() for x in spec.splitlines() if len(x.strip()) >= 60 and not x.startswith(("|", "#")) and x.strip() not in others and x.strip() not in approved]
    check(len(lines) >= 8)
    hits = subprocess.run(["grep", "-rliF", "--", RF.LABEL, str(snap)], capture_output=True, text=True).stdout.split()
    for line in lines:
        hits += subprocess.run(["grep", "-rlF", "--", line, str(snap)], capture_output=True, text=True).stdout.split()
    check(hits == [], hits[:2])
    return f"external item {{'id': 7, 'label': '{RF.SUMMARY[:30]}...'}}; WI-09 depends {nine['depends']}; grep for the label and {len(lines)} specification lines: no file"


@claim("WP9 every private field of the restricted item can change and the snapshot does not: only the owner's summary and instruction appear")
def _(base):
    a = RF.restricted_project(base / "a", summary="SUMMARY-ONE words", placeholder="INSTRUCTION-ONE words")
    b = RF.restricted_project(base / "b", summary="SUMMARY-TWO words", placeholder="INSTRUCTION-TWO words", label="Quarterly zebra census",
                              slug="zebra-census", theme="zebra herds", size="Large, about 5 days",
                              extra_spec_line="Zebra stripes are counted every quarter by the census team in the field.")
    fa, fb = A.assemble(a.root, with_board=True), A.assemble(b.root, with_board=True)
    check(fa.problems == [] and fb.problems == [], (fa.problems, fb.problems))
    swapped = {p: d.replace(b"SUMMARY-TWO words", b"SUMMARY-ONE words").replace(b"INSTRUCTION-TWO words", b"INSTRUCTION-ONE words") for p, d in fb.files.items()}
    differ = sorted(p for p in fa.files if fa.files[p] != swapped[p] and not p.endswith("wi-07.bundle.json"))
    check(sorted(fa.files) == sorted(fb.files) and differ == [], differ)
    check(b"zebra" not in b"".join(fb.files.values()).lower())
    holders = sorted(p for p, d in fa.files.items() if b"SUMMARY-ONE words" in d)
    check(len(holders) == 6, holders)
    return f"{len(fa.files)} files identical after swapping the two markers; the summary is in {len(holders)} files: {', '.join(Path(h).name for h in holders)}"


@claim("WP9 an approved placeholder prints the fourth message, a wholly withheld id prints the first, and no registry of private ids is exported")
def _(base):
    def clone_with_origin(project, name):
        F.init_git(project, "Proof Owner", "proof.owner@example.com")
        F.sh(["git", "add", "-A"], project)
        F.sh(["git", "commit", "-q", "-m", "release"], project)
        origin = base / f"{name}.git"
        F.sh(["git", "clone", "-q", "--bare", str(project), str(origin)], base)
        F.sh(["git", "remote", "add", "origin", str(origin)], project)
        F.sh(["git", "fetch", "-q", "origin"], project)
        F.sh(["git", "remote", "set-head", "origin", "main"], project)
        return project / "docs/dev/skills/expense-approvals-dev/scripts/check_context.py"

    def check_context(project, checker, item):
        return subprocess.run([PY, str(checker), item], cwd=str(project), capture_output=True, text=True, timeout=120)
    placeholder = exported(base / "p", placeholder=RF.INSTRUCTION)
    checker = clone_with_origin(placeholder.root, "p")
    fourth = check_context(placeholder.root, checker, "WI-07")
    check(fourth.returncode == 13 and fourth.stdout.splitlines()[0] == "carrydown: WI-07 has a restricted destination that this project does not publish", fourth.stdout)
    plain = exported(base / "q")
    checker2 = clone_with_origin(plain.root, "q")
    withheld, unknown = check_context(plain.root, checker2, "WI-07"), check_context(plain.root, checker2, "WI-99")
    check(withheld.returncode == unknown.returncode == 10)
    check(withheld.stdout == unknown.stdout.replace("WI-99", "WI-07"), (withheld.stdout, unknown.stdout))
    names = sorted(p.relative_to(plain.snapshot).as_posix() for p in plain.snapshot.rglob("*") if p.is_file() and re.search(r"(?i)wi-07", p.read_text(encoding="utf-8", errors="replace")))
    check(names == ["repo/docs/dev/skills/expense-approvals-dev/references/work-items.md", "repo/docs/spec/README.md"], names)
    return f"placeholder: exit {fourth.returncode} {fourth.stdout.splitlines()[0][:70]}...; withheld id: exit {withheld.returncode} {withheld.stdout.splitlines()[0]}; same as unknown id"


@claim("WP9 under engineer_edits: request-only the engineers' skill asks for a Rule clarification request comment with permission; allowed keeps today's step")
def _(base):
    seen = []
    for mode in ("allowed", "request-only"):
        root = base / mode
        shutil.copytree(F.SAMPLE, root)
        shutil.rmtree(root / "docs/dev")
        plan = root / "docs/spec/plan.yaml"
        text = plan.read_text(encoding="utf-8").replace("    state: migrated\n", f"    state: migrated\n    engineer_edits: {mode}\n", 1)
        plan.write_text(text, encoding="utf-8")
        out = script("generate_dev_skill.py", "--root", root, "--apply")
        check(out.returncode == 0, out.stdout + out.stderr)
        skill = (root / "docs/dev/skills/expense-approvals-dev/SKILL.md").read_text(encoding="utf-8")
        readme = (root / "docs/dev/skills/expense-approvals-dev/README.md").read_text(encoding="utf-8")
        step = next(ln for ln in skill.splitlines() if ln.startswith("8. "))
        if mode == "request-only":
            check("`Rule clarification request`" in step and "only after the user gives permission" in step and "continue only with what the approved context permits" in step)
            check("fails the independent check on pull requests" in readme)
        else:
            check(step.startswith('8. If the implementation departs from the file, append a short entry under "Decisions recorded"'))
        for path in (root / "docs/dev/skills/expense-approvals-dev").rglob("*"):
            if path.is_file():
                body = path.read_text(encoding="utf-8")
                check(not any(w in body for w in ("github_client", "urllib", "Authorization", "api.github.com")), str(path))
        seen.append(f"{mode}: {step[:78]}...")
    return " || ".join(seen)


@claim("WP9 the owner side of a change request: a new release supersedes the old one and the receipt names the request it replaces")
def _(base):
    yp = exported(base / "p")
    first = yp.request_id
    spec = next((yp.drafts / "docs/spec").rglob("wi-06-*.md"))
    spec.write_text(spec.read_text(encoding="utf-8").rstrip("\n") + "\n\n## Decisions recorded\n\n- Clarified after a rule clarification request.\n", encoding="utf-8")
    out = script("release.py", "preview", "--root", yp.root)
    check(out.returncode == 0 and "Changed:" in out.stdout, out.stdout[-200:] + out.stderr)
    code, out2, err = yp.prepare(nonce="ffeeddccbbaa99887766554433221100")
    check(code == 0, out2 + err)
    second = yp.request_id
    check(second != first and R.load_request(yp.workspace, second)["supersedes_request_id"] == first)
    check(yp.approve(second, created="2027-01-21T10:00:00Z")[0] == 0 and yp.export(second)[0] == 0)
    receipts = {p.name[:-len(".receipt.json")]: json.loads(p.read_text(encoding="utf-8")) for p in (yp.root / "docs/release").glob("*.receipt.json")}
    check(receipts[second]["supersedes"] == first and receipts[first]["state"] == "superseded" and receipts[first]["superseded_by"] == second)
    check("reason" not in json.dumps(receipts), "a private reason reached a receipt")
    return f"receipt {second[:12]}... supersedes {receipts[second]['supersedes'][:12]}...; the old receipt is {receipts[first]['state']}"


def main():
    print("carrydown WP8 and WP9 proof: the real scripts, no token, no network\n")
    for run in CLAIMS:
        run()
    passed = sum(RESULTS)
    print(f"\n{passed} of {len(RESULTS)} claims passed")
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
