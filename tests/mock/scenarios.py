#!/usr/bin/env python3
"""Run one GitHub scenario against the loopback mock in mockgh.py. Standard library only.

Usage
  python3 tests/mock/scenarios.py SCENARIO

Scenarios
  retry502      GitHub creates an issue but answers 502: no duplicate, links complete
  partial       a run stops on a rate limit while linking; a plain rerun repairs every link
  unlinked      --verify fails when an issue body holds a dependency id that is not a link
  sso           single sign-on 403: one-line messages with the fix, no traceback
  timeout       GitHub does not answer: one-line message, no traceback
  public        --apply to a public repository is refused unless --allow-public is passed
  ownership     only issues with the project label and only the token owner's comments count
  project       github_project.py finds every plan issue by its marker, prints plan titles only
  tokenfile     --from-file: a file with a byte order mark works, the file is kept, and text
                that is not a token is refused before anything is sent
  tokenenv      --check reads CARRYDOWN_GITHUB_TOKEN like the GitHub scripts, --token-file wins
                over it, and the token is never printed
  tokenrules    a token file others can read, a missing --token-file, an empty or non-UTF-8 file,
                a token with a second line, a bad environment variable, a symbolic link and an
                unwritable folder are refused with one line, and nothing is sent
  redirect      a redirect to another host is not followed, so the token never reaches it; a
                redirect on the same host is followed
  repos         owner and repository names with "-" and ".", a repository that does not exist,
                and --issue-type on the work items
  board         github_project.py creates the board, a rerun changes nothing, --verify passes,
                --reconfigure-iterations replaces changed iterations
  projectnumber --project-number for a project that does not exist is an error, not a create

Each check prints PASS or FAIL. Exit status is 0 when every check passes. Nothing here
talks to GitHub: the client is pointed at the mock on 127.0.0.1, and HOME is a temporary
folder so no stored token is read.
"""
import atexit
import contextlib
import io
import os
import re
import shutil
import stat
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SAMPLE = str(ROOT / "sample" / "expense-approvals")
TMP = tempfile.mkdtemp(prefix="carrydown-mock-")
atexit.register(shutil.rmtree, TMP, True)
os.environ["HOME"] = TMP
os.environ["CARRYDOWN_GITHUB_TOKEN"] = "ghp_" + "Z" * 36
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))
import mockgh  # noqa: E402
import github_client as G  # noqa: E402
import github_project as GP  # noqa: E402
import github_sync as GS  # noqa: E402
import github_token as GT  # noqa: E402

SRV, URL = mockgh.start()
G.GitHub.__init__.__defaults__ = (URL, 0.0, None)
_sleep = time.sleep
time.sleep = lambda s: _sleep(min(s, 0.005))
M = mockgh.S
failures = []


def check(ok, what):
    print(("PASS " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def call(fn, args):
    """Run a script entry point; return (exit status, captured output)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            rc = fn(args)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
            if e.code and not isinstance(e.code, int):
                print(e.code)
        except Exception as e:  # an unhandled error is a failure of the scenario
            rc = f"unhandled {type(e).__name__}: {e}"
    return rc, out.getvalue()


EPIC_TITLE = "Expense approvals, development plan"
SYNC = ["--root", SAMPLE, "--repo", "o/r", "--skip-check"]


def sync(*extra):
    return call(GS.run, SYNC + list(extra))


def titles():
    return [i["title"] for i in M.issues]


def one_line_error(text):
    errs = [ln for ln in text.splitlines() if ln.startswith("error:")]
    return len(errs) == 1 and "Fix:" in errs[0] and "Traceback" not in text


def links_complete():
    """Every work item under its sub-epic and every sub-epic under the Epic."""
    by = {i["title"]: i["number"] for i in M.issues}
    epic = next(i["number"] for i in M.issues if i["title"] == EPIC_TITLE)
    subs = [i for i in M.issues if i["title"].startswith("Milestone ")]
    items = [i for i in M.issues if re.match(r"WI-\d+", i["title"])]
    under = {n for v in M.subs.values() for n in v}
    return (len(subs) == 5 and len(items) == 9 and all(i["number"] in under for i in items)
            and sorted(M.subs.get(epic, [])) == sorted(i["number"] for i in subs)), by


def scenario_retry502():
    # epic, five sub-epics and two items succeed; the third item is created but answered with 502
    M.fail[("POST", r"/repos/\w+/\w+/issues")] = [None] * 8 + ["502-after"]
    rc, out = sync("--apply", "--create-epic")
    check(rc == 0, f"apply exits 0 after a 502 on a create (got {rc})")
    t = titles()
    dups = sorted({x for x in t if t.count(x) > 1})
    check(len(t) == 15 and not dups, f"15 issues and no duplicates (got {len(t)}, duplicates {dups})")
    posts = [x for x in M.log if x == ("POST", "/repos/o/r/issues")]
    check(len(posts) == 15, f"the failed create was not sent again (POSTs to issues: {len(posts)})")
    check("found it after the error" in out, "the run says it found the issue after the error")
    ok, _ = links_complete()
    check(ok, "every sub-issue link is in place")
    rc, out = sync("--verify")
    check(rc == 0, f"--verify passes (got {rc})")


def scenario_partial():
    M.fail[("POST", r"/repos/\w+/\w+/issues/\d+/sub_issues")] = ["403-primary"]
    rc, out = sync("--apply", "--create-epic")
    check(rc == 1, f"the interrupted run exits 1 (got {rc})")
    check(one_line_error(out), "the interruption is one line with the fix, no traceback")
    w4 = next(i for i in M.issues if i["title"].startswith("WI-04"))
    check("WI-02 (#" not in w4["body"], "after the interruption the dependency ids are not links yet")
    rc, out = call(GS.run, SYNC + ["--verify"])
    check(rc == 1, f"--verify fails on the half-built board (got {rc})")
    rc, out = sync("--apply", "--create-epic")
    check(rc == 0, f"a plain rerun exits 0 (got {rc})")
    check(len(M.issues) == 15, f"the rerun creates nothing twice ({len(M.issues)} issues)")
    ok, _ = links_complete()
    check(ok, "the rerun repaired every sub-issue link")
    w4 = next(i for i in M.issues if i["title"].startswith("WI-04"))
    check("WI-02 (#" in w4["body"], "the rerun linked the dependency ids in the bodies")
    m1 = next(i for i in M.issues if i["title"].startswith("Milestone 1"))
    check("- [ ] #" in m1["body"], "the rerun filled the issue numbers into the sub-epic lists")
    epic = next(i for i in M.issues if i["title"] == EPIC_TITLE)
    check(len(M.comments.get(epic["number"], [])) == 1, "one roll-up comment on the Epic")
    rc, out = sync("--verify")
    check(rc == 0 and "verification passed" in out, f"--verify passes after the rerun (got {rc})")


def scenario_unlinked():
    rc, _ = sync("--apply", "--create-epic")
    check(rc == 0, f"apply exits 0 (got {rc})")
    rc, out = sync("--verify")
    check(rc == 0, f"--verify passes on the complete board (got {rc})")
    w4 = next(i for i in M.issues if i["title"].startswith("WI-04"))
    w4["body"] = re.sub(r"(WI-\d+) \(#\d+\)", r"\1", w4["body"])
    rc, out = sync("--verify")
    check(rc == 1, f"--verify exits 1 when a body has an unlinked id (got {rc})")
    check("unlinked" in out and "FAILED" in out, "the verification names the unlinked ids")


def scenario_sso():
    M.fail[("GET", r"/repos/\w+/\w+")] = ["403-sso"] * 20
    rc, out = call(lambda a: GT.check(os.environ["CARRYDOWN_GITHUB_TOKEN"], "o/r"), None)
    check(rc == 1, f"the token check exits 1 (got {rc})")
    check("not reachable" in out and "single sign-on" in out and "Configure SSO" in out and "Traceback" not in out,
          "the token check prints the not reachable guidance with the single sign-on fix")
    rc, out = sync()
    check(rc == 1, f"the dry run exits 1 (got {rc})")
    check(one_line_error(out) and "single sign-on" in out, "the dry run prints one line with the single sign-on fix")


def scenario_timeout():
    real = G._urlopen
    G._urlopen = lambda req, timeout=None: real(req, timeout=0.2)
    M.timeout = 0.6
    M.fail[("GET", r"/user")] = ["timeout"] * 20
    rc, out = call(lambda a: GT.check(os.environ["CARRYDOWN_GITHUB_TOKEN"]), None)
    check(rc == 1 and "Traceback" not in out and "unhandled" not in str(rc), f"a timeout gives exit 1, not a traceback (got {rc})")
    check("no answer" in out and "Fix:" in out, "the message says GitHub did not answer and gives the fix")
    G._urlopen = real


def scenario_public():
    M.private = False
    rc, out = sync("--apply")
    check(rc not in (0, None) and "is public. Issue bodies carry text from your ground truth. Rerun with --allow-public if that is intended." in out,
          f"--apply to a public repository is refused (got {rc})")
    check(not [x for x in M.log if x[0] != "GET"], "nothing was written to the public repository")
    rc, out = sync()
    check(rc == 0 and "--allow-public" in out, "the dry run warns that the repository is public")
    rc, out = sync("--apply", "--allow-public")
    check(rc == 0 and len(M.issues) == 14, f"--allow-public lets the run go ahead (got {rc}, {len(M.issues)} issues)")


def scenario_ownership():
    # an unlabeled issue with a plan title, and a roll-up comment from someone else on the Epic
    M.labels.append({"name": "expense-approvals"})
    stray = M.add_issue("Milestone 1, Submit an expense report", "not ours")
    epic = M.add_issue("An Epic renamed by hand", "Body edited by hand.\n\n<!-- carrydown:EPIC -->", ["expense-approvals"])
    rc, out = sync("--apply", "--create-epic")
    epic_title = [i["title"] for i in M.issues if i["number"] == epic["number"]][0]
    check(rc == 0, f"apply exits 0 (got {rc})")
    m1 = [i for i in M.issues if i["title"] == stray["title"]]
    check(len(m1) == 2 and stray["body"] == "not ours", "the unlabeled issue with the same title was not adopted or changed")
    check(stray["number"] not in {n for v in M.subs.values() for n in v} and stray["number"] not in M.subs,
          "the unlabeled issue got no links")
    check("not ours" not in out, "no text fetched from GitHub is printed")
    ours = [i for i in M.issues if "<!-- carrydown:EPIC -->" in (i["body"] or "")]
    check(len(ours) == 1 and epic_title == "An Epic renamed by hand", "the renamed Epic was found by its marker, not created again")
    M.add_comment(ours[0]["number"], "<!-- carrydown:rollup -->\nplanted", login="someone-else")
    before = len(M.comments[ours[0]["number"]])
    rc, out = sync("--apply", "--create-epic")
    after = M.comments[ours[0]["number"]]
    planted = [c for c in after if c["user"]["login"] == "someone-else"]
    check(rc == 0 and len(after) == before and planted[0]["body"].endswith("planted"),
          "a roll-up comment from another account is ignored and left alone")


def scenario_project():
    rc, _ = sync("--apply", "--create-epic")
    check(rc == 0, f"apply exits 0 (got {rc})")
    for i in M.issues:   # rename every issue on GitHub; the markers still tie them to the plan
        i["title"] = "renamed by hand " + str(i["number"])
    rc, out = call(GP.run, ["--root", SAMPLE, "--repo", "o/r"])
    check(rc == 0 and "issues found in the repository: 15; missing: 0" in out, f"the board script finds all 15 issues by marker (got {rc})")
    check("renamed by hand" not in out, "no title fetched from GitHub is printed")
    rc, out = sync("--apply", "--create-epic")
    check(rc == 0 and len(M.issues) == 15 and "renamed by hand" not in out, "a rerun after renames creates nothing and prints plan titles")
    check("new sub-issue links: 0, bodies rewritten: 0" in out, "the rerun changes nothing on a complete board")


def scenario_tokenfile():
    src = Path(TMP) / "token.txt"
    dest = Path(TMP) / "store" / "github_token"
    src.write_bytes(b"\xef\xbb\xbf" + b"ghp_" + b"Z" * 36 + b"\r\n")
    rc, out = call(GT.main, ["--from-file", str(src), "--token-file", str(dest)])
    check(rc == 0, f"a token file saved with a byte order mark is accepted (got {rc})")
    check(src.exists() and "Now delete" in out, "the file is kept and the user is told to delete it")
    check(dest.read_text(encoding="utf-8") == "ghp_" + "Z" * 36 + "\n", "the stored token has no byte order mark")
    rc, out = call(GT.main, ["--from-file", str(src), "--token-file", str(dest), "--delete-after"])
    check(rc == 0 and not src.exists(), "--delete-after deletes the file")
    n = len(M.log)
    src.write_text("password123456789012345\n", encoding="utf-8")
    rc, out = call(GT.main, ["--from-file", str(src), "--token-file", str(dest)])
    check(rc == 2 and "that is not a GitHub personal access token (it starts with ghp_ or github_pat_). Nothing was sent." in out,
          "text that is not a token is refused")
    check(len(M.log) == n, "nothing was sent to the mock for it")


def scenario_tokenenv():
    # Fake values planted for the test. They go only to the mock on 127.0.0.1.
    env_token = "ghp_" + "E" * 36
    file_token = "ghp_" + "F" * 36
    os.environ["CARRYDOWN_GITHUB_TOKEN"] = env_token
    rc, out = call(GT.main, ["--check", "--repo", "o/r"])
    check(rc == 0 and "The token belongs to tester." in out and "Token check passed." in out,
          f"--check with only CARRYDOWN_GITHUB_TOKEN set checks that token (got {rc})")
    check(bool(M.auth) and M.auth[-1] == "Bearer " + env_token, "the token sent is the one from CARRYDOWN_GITHUB_TOKEN")
    check(env_token not in out, "the token is not printed")
    token_file = Path(TMP) / "explicit_token"
    token_file.write_text(file_token + "\n", encoding="utf-8")
    token_file.chmod(0o600)
    rc, out = call(GT.main, ["--check", "--token-file", str(token_file)])
    check(rc == 0 and M.auth[-1] == "Bearer " + file_token, f"--token-file wins over CARRYDOWN_GITHUB_TOKEN, as in the GitHub scripts (got {rc})")
    check(file_token not in out and env_token not in out, "neither token is printed")
    n = len(M.log)
    del os.environ["CARRYDOWN_GITHUB_TOKEN"]
    rc, out = call(GT.main, ["--check"])
    check(rc == 1 and "No token found in CARRYDOWN_GITHUB_TOKEN or at" in out, f"with no token anywhere the message names both places (got {rc})")
    check(len(M.log) == n, "nothing was sent when there was no token")


def feed(text):
    """Standard input for one --stdin call."""
    sys.stdin = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")


def private_file(path, data):
    path = Path(path)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    path.chmod(0o600)
    return str(path)


def scenario_tokenrules():
    good = "ghp_" + "G" * 36
    del os.environ["CARRYDOWN_GITHUB_TOKEN"]
    d = Path(TMP) / "rules"
    d.mkdir()
    n = len(M.log)

    def refused(args, want, what, env=None):
        if env is not None:
            os.environ["CARRYDOWN_GITHUB_TOKEN"] = env
        rc, out = call(GT.main, args)
        os.environ.pop("CARRYDOWN_GITHUB_TOKEN", None)
        lines = [ln for ln in out.splitlines() if ln.startswith("error:")]
        check(rc not in (0, None) and len(lines) == 1 and want in lines[0] and "Traceback" not in out and good not in out,
              f"{what}: one line, no token in it (got {rc}: {out.strip()[:160]})")
        return out

    loose = d / "loose"
    loose.write_text(good + "\n", encoding="utf-8")
    loose.chmod(0o644)
    out = refused(["--check", "--token-file", str(loose)], f"Fix: chmod 600 {loose}", "a token file others can read is refused")
    # the stored token must not be used when --token-file names a file that does not exist
    store = Path(TMP) / ".config/carrydown"
    store.mkdir(parents=True, exist_ok=True)
    private_file(store / "github_token", good + "\n")
    refused(["--check", "--token-file", str(d / "missing")], "token file not found", "a missing --token-file is an error, not a fallback")
    refused(["--check", "--token-file", private_file(d / "empty", "")], "is empty", "an empty token file is refused")
    refused(["--check", "--token-file", private_file(d / "latin", b"ghp_\xe9\xe9\n")], "not plain UTF-8 text", "a token file that is not UTF-8 is refused")
    refused(["--check", "--token-file", private_file(d / "twolines", good + "\nsecond line\n")], "does not hold a GitHub personal access token",
            "a token file with a second line is refused")
    refused(["--check", "--token-file", private_file(d / "comment", good + " # mine\n")], "does not hold", "a token with a trailing comment is refused")
    refused(["--check"], "CARRYDOWN_GITHUB_TOKEN does not hold", "a bad CARRYDOWN_GITHUB_TOKEN is refused", env=good + "\nsecond")
    check(len(M.log) == n, f"nothing was sent for any refused token ({len(M.log) - n} requests)")
    rc, out = call(GS.run, SYNC + ["--token-file", str(d / "missing")])
    check(rc == 1 and "token file not found" in out and len(M.log) == n, f"github_sync does not fall back to the stored token either (got {rc})")
    # storing: never through a symbolic link, only new folders are made private, no traceback on a folder that cannot be written
    target = d / "elsewhere"
    target.write_text("keep\n", encoding="utf-8")
    link = d / "link"
    link.symlink_to(target)
    feed(good + "\n")
    out = refused(["--stdin", "--token-file", str(link)], "symbolic link", "storing through a symbolic link is refused")
    sys.stdin = sys.__stdin__
    check(target.read_text(encoding="utf-8") == "keep\n", "the file the link points at is unchanged")
    shared = d / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    feed(good + "\n")
    rc, out = call(GT.main, ["--stdin", "--token-file", str(shared / "new" / "tok")])
    sys.stdin = sys.__stdin__
    mode = lambda x: stat.S_IMODE(os.stat(x).st_mode)
    check(rc == 0 and mode(shared / "new" / "tok") == 0o600 and mode(shared / "new") == 0o700 and mode(shared) == 0o755,
          f"the token is stored 600, the new folder is 700 and the existing folder keeps its mode (got {rc}, {oct(mode(shared))})")
    check(good not in out, "the stored token is not printed")
    ro = d / "readonly"
    ro.mkdir()
    ro.chmod(0o500)
    feed(good + "\n")
    rc, out = call(GT.main, ["--stdin", "--token-file", str(ro / "tok")])
    sys.stdin = sys.__stdin__
    ro.chmod(0o700)
    check(rc == 2 and "cannot write the token" in out and "Traceback" not in out and good not in out,
          f"a folder that cannot be written gives one line (got {rc})")


class _Catcher(BaseHTTPRequestHandler):
    """A second loopback server that records the Authorization header of anything sent to it."""
    seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        _Catcher.seen.append(self.headers.get("Authorization"))
        body = b'{"private": true}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def scenario_redirect():
    other = HTTPServer(("127.0.0.1", 0), _Catcher)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    where = f"http://127.0.0.1:{other.server_address[1]}/repos/o/r"
    M.redirect[("GET", r"/repos/o/r")] = where
    token = os.environ["CARRYDOWN_GITHUB_TOKEN"]
    rc, out = sync()
    check(rc == 1 and one_line_error(out) and "redirected to another host" in out, f"a redirect to another host stops the run with one line (got {rc})")
    check(not [h for h in _Catcher.seen if h], f"the other host never received an Authorization header ({_Catcher.seen})")
    check(token not in out, "the token is not printed")
    M.redirect.clear()
    M.redirect[("GET", r"/repos/o/old")] = URL + "/repos/o/r"
    gh = G.GitHub(token)
    status, js = gh.rest_status("GET", "/repos/o/old")
    check(status == 200 and M.auth[-1] == "Bearer " + token, "a redirect on the same host is followed with the token")
    other.shutdown()


def scenario_repos():
    M.repos.add("my-org/my.repo_1")
    rc, out = call(GS.run, ["--root", SAMPLE, "--repo", "my-org/my.repo_1", "--skip-check"])
    check(rc == 0 and "repository found" in out, f"an owner with a hyphen and a name with a dot and an underscore work (got {rc})")
    rc, out = call(GS.run, ["--root", SAMPLE, "--repo", "o/missing", "--skip-check", "--apply"])
    check(rc == 1 and "was not found" in out and not [x for x in M.log if x[0] != "GET"], f"--apply to a repository that does not exist stops and writes nothing (got {rc})")
    rc, out = call(GT.main, ["--check", "--repo", "o/missing"])
    check(rc == 1 and "not reachable with this token (HTTP 404)" in out, f"the token check reports a missing repository (got {rc})")
    rc, out = call(GS.run, ["--root", SAMPLE, "--repo", "../x", "--skip-check"])
    check(rc == 2 and "must look like owner/name" in out and "Traceback" not in out, f"a repository with .. is refused (got {rc})")
    rc, out = sync("--apply", "--create-epic", "--issue-type", "Task")
    typed = [i for i in M.issues if (i.get("type") or {}).get("name") == "Task"]
    check(rc == 0 and len(typed) == 9 and all(re.match(r"WI-\d+", i["title"]) for i in typed), f"--issue-type sets the type on the 9 work items only ({len(typed)})")


def board(*extra, root=None):
    return call(GP.run, ["--root", root or SAMPLE, "--repo", "o/r"] + list(extra))


def scenario_board():
    rc, _ = sync("--apply", "--create-epic")
    check(rc == 0, f"issues created first (got {rc})")
    rc, out = board()
    check(rc == 0 and "Would create" in out and not M.projects, f"the dry run creates nothing (got {rc})")
    rc, out = board("--apply")
    pr = M.projects[0] if M.projects else {"fields": [], "views": [], "items": []}
    names = {f["name"] for f in pr["fields"]}
    check(rc == 0 and {"Work unit", "Track", "Complete by", "Checkpoint"} <= names, f"--apply creates the project and the four fields (got {rc}, {sorted(names)})")
    check(sorted(v["name"] for v in pr["views"]) == ["Board", "Roadmap", "Table"], f"three views: {sorted(v['name'] for v in pr['views'])}")
    check(len(pr["items"]) == 15 and "filled on 14 of 14 items" in out, f"15 issues on the board, values filled ({len(pr['items'])})")
    before = list(M.gql)
    rc, out = board("--apply")
    writes = [g for g in M.gql[len(before):] if g in mockgh.MUTATIONS]
    check(rc == 0 and not writes, f"a rerun sends no write (sent {writes})")
    rc, out = board("--verify")
    check(rc == 0 and "field Track: present, filled on 9 of 9 items" in out, f"--verify passes (got {rc})")
    rc, out = board("--verify", "--project-number", "1")
    check(rc == 0 and "project exists: #1" in out, f"--project-number finds the project (got {rc})")
    proj = Path(TMP) / "moved"
    shutil.copytree(SAMPLE, proj)
    plan = proj / "docs/spec/plan.yaml"
    plan.write_text(plan.read_text(encoding="utf-8").replace("    end: 2027-04-23\n", "    end: 2027-04-30\n"), encoding="utf-8")
    rc, out = board("--apply", root=str(proj))
    check(rc == 0 and "iterations differ from the plan" in out and "updateProjectV2Field" not in M.gql, "changed dates are reported, not applied, without --reconfigure-iterations")
    rc, out = board("--apply", "--reconfigure-iterations", root=str(proj))
    wu = next(f for f in M.projects[0]["fields"] if f["name"] == "Work unit")
    last = wu["configuration"]["iterations"][-1]
    check(rc == 0 and "updateProjectV2Field" in M.gql and last["duration"] == 19, f"--reconfigure-iterations replaces them (got {rc}, last {last['duration']} days)")
    rc, out = board("--apply", root=str(proj))
    check(rc == 0 and "Work unit exists with the planned iterations" in out, "the next run finds the planned iterations")


def scenario_projectnumber():
    rc, _ = sync("--apply", "--create-epic")
    n = len(M.gql)
    rc, out = board("--apply", "--project-number", "7")
    check(rc == 1 and "project #7 was not found" in out and "createProjectV2" not in M.gql[n:] and "Traceback" not in out,
          f"--project-number for a missing project is an error and creates nothing (got {rc})")
    rc, out = board("--project-number", "7")
    check(rc == 1 and "createProjectV2" not in M.gql and "Would create" not in out, f"the dry run says so too (got {rc})")


def main(argv):
    name = argv[1] if len(argv) > 1 else ""
    fn = globals().get(f"scenario_{name}")
    if not fn:
        print(__doc__)
        return 2
    fn()
    print(f"{name}: {'all checks passed' if not failures else str(len(failures)) + ' check(s) failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
