#!/usr/bin/env python3
"""Repair existing issue metadata after an approved plan review. Dry run unless --apply.

This separate path changes generated titles, the plan owner's assignment, the track label
and parent links. It never changes bodies, comments, issue state or unrelated labels and
assignees. Body and board updates use their existing scripts after their own previews.

Usage
  python3 scripts/github_repair.py --root PROJECT --offline
  python3 scripts/github_repair.py --root PROJECT --before PATH
  python3 scripts/github_repair.py --root PROJECT --before PATH --apply
  python3 scripts/github_repair.py --root PROJECT --before PATH --verify

--before is the saved plan from before the accepted repairs. Keep it until publication is
verified. No issues, labels, projects or repositories are created or deleted here.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import carrydown_lib as L
import github_client as G
import github_sync as S


def entries(plan):
    out = {}
    for ms in plan["milestones"]:
        out[f"M{ms['number']}"] = (S.subepic_title(plan, ms), None, None)
    for it in plan["items"]:
        out[L.tag(plan, it["id"])] = (S.item_title(plan, it), it, f"M{it['milestone']}")
    return out


def login(plan, item):
    people = {p["id"]: p for p in plan["people"]}
    return str(people.get(item.get("owner"), {}).get("github") or "") if item else ""


def issue_patch(before, plan, key, live):
    """Only replace a title still written from the old plan; preserve human body edits."""
    title, item, _ = entries(plan)[key]
    old_title, old_item, _ = entries(before).get(key, (title, item, None))
    patch, conflicts = {}, []
    if live["title"] != title:
        if live["title"] != old_title:
            conflicts.append(f"{key}: title was edited outside the saved plan; reconcile it explicitly")
        else:
            patch["title"] = title
    if item:
        labels = {x["name"] for x in live.get("labels", [])}
        wanted = set(labels)
        if old_item and old_item["track"] != item["track"]:
            wanted.discard(old_item["track"])
        wanted.add(item["track"])
        if wanted != labels:
            patch["labels"] = sorted(wanted)
        assigned = {x["login"].casefold(): x["login"] for x in live.get("assignees", [])}
        wanted = dict(assigned)
        old_login, new_login = login(before, old_item), login(plan, item)
        if old_login.casefold() != new_login.casefold():
            wanted.pop(old_login.casefold(), None)
        if new_login:
            wanted[new_login.casefold()] = new_login
        if set(wanted) != set(assigned):
            patch["assignees"] = sorted(wanted.values(), key=str.casefold)
    return patch, conflicts


def parent_of(gh, base, issue):
    status, parent = gh.rest_status("GET", f"{base}/issues/{issue['number']}/parent")
    return parent if status == 200 else None


def fingerprint(issue):
    return (issue["title"], sorted(x["name"] for x in issue.get("labels", [])),
            sorted(x["login"].casefold() for x in issue.get("assignees", [])))


def repair(gh, before, plan, root, owner, repo, apply=False, verify=False, selections=None):
    sync = S.Sync(plan, root, gh, owner, repo, False, selections)
    base = sync.base
    expected = entries(plan)
    known = entries(before)
    conflicts, actions = [], []
    # Use the same complete candidate comparison and persisted mapping as synchronization.
    objects = {}
    for key, (title, _, _) in expected.items():
        try:
            issue = sync.find(key, title)
        except G.GitHubError as e:
            conflicts.append(e.line())
            continue
        mark = S.MARKER_RE.search(issue.get("body") or "") if issue else None
        if not mark or mark.group(1) != key:
            conflicts.append(f"{key}: marked issue missing; create or identify it through reviewed staged creation first")
        else:
            objects[key] = issue
    for key in set(known) - set(expected):
        conflicts.append(f"{key}: retired from the plan; preserve its issue and resolve its disposition with the owner")
    labels = {x["name"] for x in gh.paged(f"{base}/labels")}
    missing = {it["track"] for it in plan["items"]} - labels
    if missing:
        conflicts.append("create the approved track labels before metadata repair: " + ", ".join(sorted(missing)))
    epic = plan["project"].get("epic")
    epic_issue = gh.rest("GET", f"{base}/issues/{epic}") if epic else sync.find("EPIC", plan["project"]["epic_title"])
    managed_ids = {i["id"] for i in objects.values()}
    # A retired milestone may still be the old parent of an item that moved.
    for key, (title, _, _) in known.items():
        if key.startswith("M"):
            old_parent = sync.find(key, title)
            if old_parent:
                managed_ids.add(old_parent["id"])
    if epic_issue:
        managed_ids.add(epic_issue["id"])
    for key, issue in objects.items():
        patch, problems = issue_patch(before, plan, key, issue)
        conflicts.extend(problems)
        parent_key = expected[key][2]
        desired_parent = objects.get(parent_key) if parent_key else epic_issue
        parent = parent_of(gh, base, issue)
        move = desired_parent if desired_parent and (not parent or parent["id"] != desired_parent["id"]) else None
        if move and parent and parent["id"] not in managed_ids:
            conflicts.append(f"{key}: current parent is outside this plan; reconcile it explicitly")
        if patch or move:
            actions.append((key, issue, patch, move, parent))
            L.say(f"  {key} #{issue['number']}: " + json.dumps(patch, sort_keys=True))
            if move:
                L.say(f"    parent: {parent['number'] if parent else 'none'} -> #{move['number']}")
    for problem in conflicts:
        L.say("  blocked: " + problem)
    if conflicts:
        L.say("No repairs applied. Resolve the blocked decisions and preview again.")
        return 1
    if verify:
        L.say(f"metadata verification: {len(actions)} difference(s)")
        return 1 if actions else 0
    if not apply:
        L.say(f"{len(actions)} issue(s) would be repaired. Bodies, comments and issue state are untouched.")
        return 0
    for key, issue, patch, move, parent in actions:
        current = gh.rest("GET", f"{base}/issues/{issue['number']}")
        current_parent = parent_of(gh, base, current)
        if fingerprint(current) != fingerprint(issue) or (current_parent or {}).get("id") != (parent or {}).get("id"):
            L.die(f"{key} changed during this run. Stop and preview again", 1)
        if patch:
            gh.rest("PATCH", f"{base}/issues/{issue['number']}", patch)
        if move:
            gh.rest("POST", f"{base}/issues/{move['number']}/sub_issues",
                    {"sub_issue_id": issue["id"], "replace_parent": True})
        L.say(f"  repaired {key} #{issue['number']}")
    # Persist only after the entire approved metadata preview has passed its guards.
    sync.apply = True
    sync.issues = None
    for key, (title, _, _) in expected.items():
        sync.find(key, title)
    sync.save_mapping()
    L.say("Verify repaired metadata automatically.")
    return repair(gh, before, plan, root, owner, repo, verify=True, selections=selections)


def run(argv=None):
    try:
        return main(argv)
    except G.GitHubError as e:
        return G.report(e)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Repair existing plan issue metadata after review. Dry run unless --apply.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--plan", help="current approved plan, relative to the project root")
    ap.add_argument("--before", help="saved plan from before the accepted repairs")
    ap.add_argument("--repo", help="owner/name, overriding the plan repository")
    ap.add_argument("--token-file")
    ap.add_argument("--offline", action="store_true", help="show intended metadata without a token or network")
    ap.add_argument("--apply", action="store_true", help="apply the previewed repairs")
    ap.add_argument("--allow-public", action="store_true", help="allow approved repairs in a public repository")
    ap.add_argument("--verify", action="store_true", help="read and compare metadata; never write")
    ap.add_argument("--select-issue", action="append", default=[], metavar="KEY=NUMBER", help="choose a canonical issue after the ambiguity preview")
    a = ap.parse_args(argv)
    if sum((a.offline, a.apply, a.verify)) > 1:
        L.die("--offline, --apply and --verify are separate modes")
    for flag, value in (("--before", a.before), ("--plan", a.plan), ("--repo", a.repo), ("--token-file", a.token_file)):
        if value is not None and not value.strip():
            L.die(f"{flag} is empty")
    root = L.project_root(a.root)
    path = L.find_plan(root, a.plan)
    plan, problems = L.load_plan(path, root)
    if problems:
        L.die("plan has problems: " + "; ".join(problems), 1)
    L.say("carrydown github_repair " + ("APPLY" if a.apply else "VERIFY" if a.verify else "DRY RUN"))
    if a.offline:
        for key, (title, item, parent) in entries(plan).items():
            L.say(f"  {key}: {title}; parent {parent or 'plan epic when present'}" +
                  (f"; track {item['track']}; assigned engineer {login(plan, item) or 'none'}" if item else ""))
        L.say("offline: nothing read from GitHub; no files written")
        return 0
    if not a.before:
        L.die("--before is required for online repair; save the approved pre-repair plan first")
    before_path = Path(a.before)
    if not before_path.is_absolute():
        before_path = root / before_path
    before, problems = L.load_plan(before_path, root)
    if problems:
        L.die("saved plan has problems: " + "; ".join(problems), 1)
    for field in ("slug", "id_prefix", "repo"):
        if before["project"][field] != plan["project"][field]:
            L.die(f"project.{field} changed; this command cannot migrate project identity", 1)
    # The checker remains unchanged and is always run before any online operation.
    check = subprocess.run([sys.executable, str(Path(__file__).with_name("check_specs.py")),
                            "--root", str(root), "--plan", str(path)])
    if check.returncode:
        return check.returncode
    owner, repo = L.repo_parts(plan, a.repo)
    gh = G.GitHub(G.read_token(a.token_file))
    status, repository = gh.rest_status("GET", f"/repos/{owner}/{repo}")
    if status != 200:
        L.die("repository not found or inaccessible", 1)
    if a.apply and not repository.get("private") and not a.allow_public:
        L.die("public repository: explicit publication approval and --allow-public are required", 1)
    selections = {}
    for selection in a.select_issue:
        key, sep, number = selection.partition("=")
        if not sep or not key or not number.isascii() or not number.isdigit() or int(number) < 1:
            L.die("--select-issue must be KEY=NUMBER")
        selections[key] = int(number)
    return repair(gh, before, plan, root, owner, repo, a.apply, a.verify, selections)


if __name__ == "__main__":
    raise SystemExit(run())
