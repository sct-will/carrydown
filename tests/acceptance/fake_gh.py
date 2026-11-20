#!/usr/bin/env python3
"""A fake gh command line tool for the tests of live_github_run.py. Standard library only. No network.

The test writes a small shell wrapper named gh that runs this file, and puts it first on PATH. Two environment
variables say where it keeps its state and its call log:

  FAKE_GH_STATE   a JSON file with the model of the organization (created on first use)
  FAKE_GH_LOG     a JSON lines file. One line per call: {"args": [...], "stdin": "..."}

It models only what the runner calls: the signed-in user, one organization, repositories with Git data (blobs,
trees, commits, refs), rulesets, Actions settings, secret names, App installations, collaborators and workflow
runs. A call it does not know answers 404, as GitHub does for a missing resource.

The state may hold a "leak" object {"path": REGEX, "text": STRING}: a call whose path matches then fails with
status 500 and writes STRING to standard error. The redaction test puts a token shape in STRING.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

STATE = os.environ.get("FAKE_GH_STATE", "")
LOG = os.environ.get("FAKE_GH_LOG", "")


def load():
    p = Path(STATE)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save(s):
    Path(STATE).write_bytes((json.dumps(s)).encode("utf-8"))


def sha1(text):
    return hashlib.sha1(text.encode()).hexdigest()


def blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def fail(status, text="Not Found"):
    sys.stderr.write(f"gh: {text} (HTTP {status})\n")
    sys.exit(1)


def out(obj):
    print(json.dumps(obj))
    sys.exit(0)


def new_id(s):
    s["next_id"] = s.get("next_id", 1000) + 1
    return s["next_id"]


def repo_obj(s, name):
    r = s["repos"][name]
    org = s["org"]
    return {"id": r["id"], "name": name.split("/", 1)[1], "full_name": name, "private": r["private"], "default_branch": r["default_branch"],
            "allow_merge_commit": r["allow_merge_commit"], "allow_squash_merge": r["allow_squash_merge"],
            "allow_rebase_merge": r["allow_rebase_merge"], "html_url": f"https://github.com/{name}", "owner": {"login": org}}


def make_tree(s, repo, items):
    key = sha1(json.dumps(sorted(items.items())))
    repo["trees"][key] = items
    return key


def make_commit(repo, tree, parents, message):
    sha = sha1(json.dumps([tree, parents, message, len(repo["commits"])]))
    repo["commits"][sha] = {"tree": tree, "parents": parents, "message": message}
    return sha


def create_repo(s, name, body):
    full = f"{s['org']}/{name}"
    repo = {"id": new_id(s), "private": bool(body.get("private")), "default_branch": "main", "allow_merge_commit": True,
            "allow_squash_merge": True, "allow_rebase_merge": True, "refs": {}, "commits": {}, "trees": {}, "blobs": {},
            "rulesets": [], "secrets": list(s.get("pending_secrets", {}).get(name, [])),
            "actions": {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False}}
    s["repos"][full] = repo
    readme = b"# " + name.encode() + b"\n"
    repo["blobs"][blob_sha(readme)] = base64.b64encode(readme).decode()
    tree = make_tree(s, repo, {"README.md": [blob_sha(readme), "100644"]})
    repo["refs"]["main"] = make_commit(repo, tree, [], "Initial commit")
    return full


def head_tree(repo, branch=None):
    return repo["trees"][repo["commits"][repo["refs"][branch or repo["default_branch"]]]["tree"]]


def clone(s, full, dest):
    repo = s["repos"][full]
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    subprocess.run(["git", "init", "-q", "-b", "main", dest], check=True, env=env)
    for path, (sha, mode) in head_tree(repo).items():
        target = Path(dest) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(repo["blobs"][sha]))
    for cmd in (["add", "-A"], ["-c", "user.name=Fake", "-c", "user.email=fake@example.com", "commit", "-q", "-m", "clone"],
                ["remote", "add", "origin", f"https://github.com/{full}.git"]):
        subprocess.run(["git", "-C", dest] + cmd, check=True, env=env, capture_output=True)


def api(s, args, stdin):
    method = "GET"
    path = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-X", "--method"):
            method = args[i + 1].upper()
            i += 1
        elif a.startswith("-X") and len(a) > 2:
            method = a[2:].upper()
        elif a == "--input":
            if method == "GET":
                method = "POST"
            i += 1
        elif not a.startswith("-") and path is None:
            path = a
        i += 1
    body = json.loads(stdin) if stdin.strip() else {}
    full_path = path
    path = path.split("?", 1)[0].strip("/")
    query = full_path.split("?", 1)[1] if "?" in full_path else ""
    leak = s.get("leak")
    if leak and re.search(leak["path"], path):
        sys.stderr.write(leak["text"] + "\n")
        sys.stderr.write("gh: Server Error (HTTP 500)\n")
        sys.exit(1)
    org = s["org"]
    if path == "user":
        out(s["user"])
    if path == f"orgs/{org}":
        out({"login": org, "plan": {"name": s.get("plan", "team")}})
    if path == f"user/memberships/orgs/{org}":
        out({"role": "admin"})
    if path == f"orgs/{org}/repos" and method == "POST":
        full = create_repo(s, body["name"], body)
        save(s)
        out(repo_obj(s, full))
    if path == f"orgs/{org}/actions/secrets":
        out({"secrets": []})
    if path == f"orgs/{org}/installations":
        out({"installations": s.get("installations", [])})
    m = re.fullmatch(r"user/installations/(\d+)/repositories(?:/(\d+))?", path)
    if m:
        names = s.setdefault("install_repos", {}).setdefault(m.group(1), [])
        if method == "PUT":
            for full, r in s["repos"].items():
                if str(r["id"]) == m.group(2) and full.split("/")[1] not in names:
                    names.append(full.split("/")[1])
            save(s)
            out({})
        out({"repositories": [{"name": n} for n in names]})
    m = re.fullmatch(rf"repos/({re.escape(org)}/[^/]+)(?:/(.*))?", path)
    if not m or m.group(1) not in s["repos"]:
        fail(404)
    name, rest = m.group(1), m.group(2) or ""
    repo = s["repos"][name]
    if rest == "":
        if method == "PATCH":
            repo.update({k: v for k, v in body.items() if k in ("allow_merge_commit", "allow_squash_merge", "allow_rebase_merge")})
            save(s)
        out(repo_obj(s, name))
    m = re.fullmatch(r"git/ref/heads/(.+)", rest)
    if m:
        if m.group(1) not in repo["refs"]:
            fail(404)
        out({"object": {"sha": repo["refs"][m.group(1)]}})
    m = re.fullmatch(r"git/commits/([0-9a-f]+)", rest)
    if m:
        c = repo["commits"].get(m.group(1))
        if c is None:
            fail(404)
        out({"sha": m.group(1), "tree": {"sha": c["tree"]}, "parents": [{"sha": p} for p in c["parents"]]})
    m = re.fullmatch(r"git/trees/([0-9a-f]+)", rest)
    if m:
        items = repo["trees"].get(m.group(1))
        if items is None:
            fail(404)
        out({"truncated": False, "tree": [{"path": p, "mode": v[1], "type": "blob", "sha": v[0]} for p, v in sorted(items.items())]})
    if rest == "git/blobs" and method == "POST":
        data = base64.b64decode(body["content"])
        repo["blobs"][blob_sha(data)] = body["content"] if len(data) < 30000 else ""      # large files are not read back, so they are not kept
        save(s)
        out({"sha": blob_sha(data)})
    if rest == "git/trees" and method == "POST":
        items = dict(repo["trees"][next(k for k in repo["trees"] if k == body["base_tree"])])
        for e in body["tree"]:
            items[e["path"]] = [e["sha"], e["mode"]]
        key = make_tree(s, repo, items)
        save(s)
        out({"sha": key})
    if rest == "git/commits" and method == "POST":
        sha = make_commit(repo, body["tree"], body["parents"], body["message"])
        repo["commits"][sha]["login"] = s["user"]["login"]
        save(s)
        out({"sha": sha})
    m = re.fullmatch(r"git/refs/heads/(.+)", rest)
    if m and method == "PATCH":
        repo["refs"][m.group(1)] = body["sha"]
        for pr in repo.get("pulls", {}).values():          # a push to a pull request branch: new head, and stale approvals are dismissed
            if pr["head"]["ref"] == m.group(1) and pr["state"] == "open":
                pr["head"]["sha"] = body["sha"]
                for r in pr["reviews"]:
                    if r["state"] == "APPROVED" and r["commit_id"] != body["sha"]:
                        r["state"] = "DISMISSED"
        save(s)
        out({"ref": m.group(1)})
    # pull requests, reviews, merges and the verifier's check runs (a check passes when the head holds an approving review)
    if rest == "pulls":
        branch = re.search(r"head=[^:&]+:([^&]+)", query)
        out([pr for pr in repo.get("pulls", {}).values() if not branch or pr["head"]["ref"] == branch.group(1)])
    m = re.fullmatch(r"pulls/(\d+)(?:/(reviews|merge))?", rest)
    if m:
        pr = repo.get("pulls", {}).get(m.group(1))
        if pr is None:
            fail(404)
        if m.group(2) == "reviews":
            out(pr["reviews"])
        if m.group(2) == "merge":
            if pr["merged"] or body.get("sha") != pr["head"]["sha"]:
                fail(409, "Head branch was modified")
            base = repo["refs"][repo["default_branch"]]
            merged_tree = repo["commits"][pr["head"]["sha"]]["tree"]
            merge = make_commit(repo, merged_tree, [base, pr["head"]["sha"]], "Merge pull request")
            repo["refs"][repo["default_branch"]] = merge
            pr.update(merged=True, state="closed", merge_commit_sha=merge)
            save(s)
            out({"merged": True, "sha": merge})
        out(pr)
    m = re.fullmatch(r"commits/([0-9a-f]+)(/check-runs)?", rest)
    if m:
        c = repo["commits"].get(m.group(1))
        if c is None:
            fail(404)
        if m.group(2):
            runs = []
            for pr in repo.get("pulls", {}).values():
                if pr["head"]["sha"] == m.group(1):
                    ok = any(r["state"] == "APPROVED" and r["commit_id"] == m.group(1) for r in pr["reviews"])
                    runs.append({"id": 8000 + len(m.group(1)), "name": "carrydown-staging-verifier", "status": "completed",
                                 "conclusion": "success" if ok else "failure", "app": {"id": 555},
                                 "output": {"title": "verified" if ok else "approval-not-found"}})
            out({"check_runs": runs})
        login = c.get("login", s["user"]["login"])
        out({"sha": m.group(1), "parents": [{"sha": p} for p in c["parents"]], "author": {"login": login}, "committer": {"login": login}})
    if rest == "commits":
        branch = repo["default_branch"]
        sha, rows = repo["refs"][branch], []
        while sha:
            c = repo["commits"][sha]
            rows.append({"sha": sha, "commit": {"message": c["message"]}})
            sha = c["parents"][0] if c["parents"] else None
        out(rows)
    m = re.fullmatch(r"contents/(.+)", rest)
    if m:
        item = head_tree(repo).get(m.group(1))
        if item is None:
            fail(404)
        out({"encoding": "base64", "content": repo["blobs"][item[0]], "sha": item[0]})
    if rest == "rulesets":
        if method == "POST":
            body = dict(body, id=new_id(s))
            repo["rulesets"].append(body)
            save(s)
            out({"id": body["id"]})
        out([{"id": r["id"], "name": r["name"]} for r in repo["rulesets"]])
    m = re.fullmatch(r"rulesets/(\d+)", rest)
    if m:
        for r in repo["rulesets"]:
            if str(r["id"]) == m.group(1):
                out(r)
        fail(404)
    if rest == "actions/permissions/workflow":
        if method == "PUT":
            repo["actions"].update(body)
            save(s)
            out({})
        out(repo["actions"])
    if rest == "actions/secrets":
        out({"secrets": [{"name": n} for n in repo["secrets"]]})
    if rest == "collaborators":
        out([s["user"]])
    if rest in ("teams", "keys"):
        out([])
    m = re.fullmatch(r"actions/workflows/([^/]+)/runs", rest)
    if m:
        tip = repo["refs"][repo["default_branch"]]
        out({"workflow_runs": [{"id": 7001, "conclusion": "success", "head_sha": tip, "updated_at": "2027-01-01T00:00:00Z"}]})
    if re.fullmatch(r"actions/workflows/[^/]+/dispatches", rest):
        s.setdefault("dispatched", []).append(rest)
        save(s)
        out({})
    fail(404)


def main():
    args = sys.argv[1:]
    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    if LOG:
        with open(LOG, "a") as f:
            f.write(json.dumps({"args": args, "stdin": stdin}) + "\n")
    s = load()
    if args[:2] == ["auth", "status"]:
        if s.get("auth") == "none":
            sys.stderr.write("You are not logged into any GitHub hosts. To log in, run: gh auth login\n")
            sys.exit(1)
        print(f"github.com\n  Logged in to github.com account {s['user']['login']} (keyring)\n  - Token: gho_************************************\n"
              "  - Token scopes: 'admin:org', 'repo', 'workflow'")
        sys.exit(0)
    if args[0] == "api":
        api(s, args[1:], stdin)
    if args[:2] == ["secret", "set"]:
        name = args[2]
        repo = args[args.index("--repo") + 1]
        s["repos"][repo]["secrets"].append(name) if name not in s["repos"][repo]["secrets"] else None
        save(s)
        sys.exit(0)
    if args[:2] == ["repo", "clone"]:
        clone(s, args[2], args[3])
        sys.exit(0)
    sys.stderr.write("fake gh: unsupported call " + " ".join(args) + "\n")
    sys.exit(2)


main()
