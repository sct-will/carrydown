#!/usr/bin/env python3
"""Create the GitHub structure for a plan: labels, sub-epics, work item issues, links, Epic comment.

Everything is derived from plan.yaml and the specification folder.

  labels         one for the project, one per track, and "sub-epic"
  sub-epics      one issue per milestone. Body comes from milestone.md: purpose, expected outcomes,
                 acceptance criteria, demonstration expectations and the work item list
  work items     one issue per item. Body: Work item, AI engineering notes (specification link and
                 developer skill line), Depends on, Acceptance criteria, Evidence of completion,
                 Integration points, Definition of done
  sub-issues     each work item under its sub-epic, each sub-epic under the Epic if there is one
  dependencies   ids in issue bodies rewritten to issue links, for example "WI-01 (#12)"
  Epic comment   one roll-up comment with nested checkboxes, created once and updated on reruns

Safety
  This is a dry run unless you pass --apply. The dry run reads from GitHub when a token is
  available (it never writes) and prints what it would create. Run it first and read it.
  Issues are matched by exact title, so a rerun creates nothing twice.
  Existing issue bodies are left alone unless you pass --update-bodies.
  The token is read from a file and is never printed.

Usage
  python3 scripts/github_sync.py --root . --repo owner/name            dry run
  python3 scripts/github_sync.py --root . --repo owner/name --apply    write
  python3 scripts/github_sync.py --root . --verify                     check what exists
  python3 scripts/github_sync.py --root . --offline --show-body 3      print one issue body, no network
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import check_specs  # noqa: E402

COLORS = {"GRAY": "6e7781", "BLUE": "1d76db", "GREEN": "0e8a16", "YELLOW": "fbca04", "ORANGE": "d93f0b",
          "RED": "b60205", "PINK": "e99695", "PURPLE": "5319e7"}
MARKER = "<!-- carrydown:rollup -->"
SEVEN = ["Work item", "AI engineering notes", "Depends on", "Acceptance criteria", "Evidence of completion", "Integration points", "Definition of done"]


def subepic_title(plan, ms):
    return f"{plan['project']['subepic_prefix']} {ms['number']}, {ms['name']}"


def item_title(plan, it):
    return plan["project"]["title_format"].format(id=L.tag(plan, it["id"]), label=it["label"], lower=L.tag(plan, it["id"]).lower())


def definition_of_done(plan):
    c = plan["conventions"]
    items = ["Every acceptance criterion is proven by a test or a recorded check named in the pull request."]
    land = f"The work landed on {plan['project']['branch']}"
    if c.get("feature_flag"):
        land += f" behind the {c['feature_flag']} flag"
    items.append(land + ".")
    checks = [f"`{c[k]}`" for k in ("test_command", "lint_command") if c.get(k)]
    if checks:
        items.append(" and ".join(checks) + " pass.")
    for extra in c.get("extra") or []:
        items.append(extra if extra.endswith(".") else extra + ".")
    items.append("The \"Decisions recorded\" section of the specification is updated if the implementation departed from it.")
    items.append("The item is demonstrated at its checkpoint with the joint check run.")
    items.append("The closing comment on this issue follows the template in the specification folder README (Demo, Evidence, Decisions, Handoff) with every artifact listed above attached.")
    return "\n".join(f"- [ ] {i}" for i in items)


def first_paragraph(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return paras[0] if paras else ""


def link_ids(plan, text, numbers):
    prefix = re.escape(plan["project"]["id_prefix"])

    def sub(m):
        n = int(m.group(2))
        key = L.tag(plan, n)
        if key in numbers:
            return f"{m.group(0)} (#{numbers[key]})"
        return m.group(0)

    out = []
    for line in text.split("\n"):
        # the skill invocation line names an id the agent must read as plain text
        out.append(line if line.startswith("Install it once") else re.sub(rf"\b({prefix})-(\d+)\b(?! \(#)", sub, line))
    return "\n".join(out)


def build_item_body(plan, root, it, numbers=None):
    numbers = numbers or {}
    sp = L.spec_path(plan, root, it)
    spec = L.read_spec(sp)
    rel = sp.relative_to(root).as_posix()
    cp = L.checkpoint_of(plan, it) or {"date": it["checkpoint"], "name": ""}
    proj = plan["project"]
    skill = ""
    if proj.get("dev_skill_path") and proj.get("repo"):
        skill = (
            f"Developer skill: {L.github_tree_url(plan, proj['dev_skill_path'])}\n\n"
            f"Install it once following its README, then start this item by asking your coding agent to work on {L.tag(plan, it['id'])}. "
            "The skill makes the agent read the specification above, the ground truth sections it cites and the project conventions "
            "before it changes code. You review every change."
        )
    deps = [f"- {L.tag(plan, d)} {L.item_by_id(plan)[d]['label']}" for d in it["depends"]]
    if it["program_input"]:
        deps.append(f"- Program input: {it['program_input']}")
    values = {
        "complete_by": it["complete_by"],
        "checkpoint": f"{cp['date']}, {cp['name']}",
        "description": first_paragraph(L.section_text(spec, "Why this work item exists")) or first_paragraph(L.section_text(spec, "Outcome")),
        "spec_url": L.github_blob_url(plan, rel),
        "skill_line": skill,
        "ground_truth": it.get("ground_truth") or spec["rows"].get("Ground truth", ""),
        "depends": "\n".join(deps) if deps else "None.",
        "acceptance": L.section_text(spec, "Acceptance criteria"),
        "evidence": L.section_text(spec, "Evidence of completion"),
        "integration": L.section_text(spec, "Integration points"),
        "definition_of_done": definition_of_done(plan),
    }
    body = L.fill(L.read_template("issue-body.md"), values)
    body = re.sub(r"\n{3,}", "\n\n", body)
    if not skill:
        body = body.replace("Specification: " + values["spec_url"] + "\n\n\n", "Specification: " + values["spec_url"] + "\n\n")
    return link_ids(plan, body.rstrip() + "\n", numbers)


def build_subepic_body(plan, root, ms, numbers=None):
    numbers = numbers or {}
    p = L.milestone_path(plan, root, ms)
    spec = L.read_spec(p)
    rel = p.relative_to(root).as_posix()
    lines = [L.section_text(spec, "Purpose"), "", f"**Exit gate.** {ms['gate']}", "",
             f"**Due.** {ms['end']}. **Demonstration.** {ms['demo']}.", "",
             "### Expected outcomes", "", L.section_text(spec, "Expected outcomes"), "",
             "### Acceptance criteria", "", L.section_text(spec, "Acceptance criteria"), "",
             "### Demonstration expectations", "", L.section_text(spec, "Demonstration expectations"), "",
             "### Work items", ""]
    people = {pp["id"]: pp for pp in plan["people"]}
    for it in plan["items"]:
        if it["milestone"] != ms["number"]:
            continue
        t = L.tag(plan, it["id"])
        who = people.get(it["owner"], {}).get("github")
        ref = f"#{numbers[t]} " if t in numbers else ""
        lines.append(f"- [ ] {ref}{t} {it['label']}" + (f", @{who}" if who else "") + f", by {it['complete_by']}")
    lines += ["", f"Milestone file: {L.github_blob_url(plan, rel)}"]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip() + "\n"


def build_rollup(plan, numbers, epic_number):
    proj = plan["project"]
    readme = L.github_blob_url(plan, f"{proj['spec_dir']}/README.md")
    intro = (f"{len(plan['milestones'])} sub-epics, one per milestone, each holding its work item issues as sub-issues. A box is checked when its issue closes. "
             f"Conventions, the checkpoint schedule and the comment templates are in [{proj['spec_dir']}/README.md]({readme}).")
    if plan["program"]["items"]:
        intro += " Program items are tracked outside these issues."
    out = [MARKER, f"## Development plan, {proj['name']}", "", intro, ""]
    people = {pp["id"]: pp for pp in plan["people"]}
    for ms in plan["milestones"]:
        sk = f"M{ms['number']}"
        ref = f"#{numbers[sk]} " if sk in numbers else ""
        out.append(f"- [ ] {ref}{subepic_title(plan, ms)}, due {ms['end']}")
        for it in plan["items"]:
            if it["milestone"] == ms["number"]:
                t = L.tag(plan, it["id"])
                who = people.get(it["owner"], {}).get("github")
                r = f"#{numbers[t]} " if t in numbers else ""
                out.append(f"  - [ ] {r}{t} {it['label']}" + (f", @{who}" if who else "") + f", by {it['complete_by']}")
    out += ["", "### How progress is shown", "",
            "Each milestone is a sub-epic with its acceptance criteria and demonstration expectations in its body. "
            "The demonstration is given by the people who own the items, in a meeting, and its outcome is noted on the sub-epic. "
            "Weekly checkpoints between the tracks are integration checks, not demonstrations, and their short records are comments here. "
            "Each work item closes with an evidence comment on its own issue (Demo, Evidence, Decisions, Handoff)."]
    return "\n".join(out) + "\n"


class Sync:
    def __init__(self, plan, root, gh, owner, repo, apply):
        self.plan, self.root, self.gh, self.owner, self.repo, self.apply = plan, Path(root), gh, owner, repo, apply
        self.base = f"/repos/{owner}/{repo}"
        self.issues = None
        self.numbers = {}   # "M1" / "WI-01" -> issue number
        self.ids = {}       # same keys -> issue id (for sub-issue links)
        self.created = set()
        self.planned = set()
        self.counts = {"labels": 0, "subepics": 0, "items": 0, "links": 0, "bodies": 0}

    def load_issues(self):
        if self.issues is None:
            self.issues = {}
            for i in self.gh.paged(f"{self.base}/issues?state=all"):
                if "pull_request" not in i:
                    self.issues.setdefault(i["title"], i)
        return self.issues

    def desired_labels(self):
        proj = self.plan["project"]
        out = [(proj["slug"], "6e7781", f"Work item of {proj['name']}"), ("sub-epic", "5319e7", "Milestone sub-epic")]
        for t in self.plan["tracks"]:
            out.append((t["id"], COLORS.get(str(t.get("color", "GRAY")).upper(), "6e7781"), f"{t['label']} track"))
        return out

    def labels(self):
        have = {l["name"].lower() for l in self.gh.paged(f"{self.base}/labels")} if self.gh else set()
        for name, color, desc in self.desired_labels():
            if name.lower() in have:
                L.say(f"  label exists: {name}")
                continue
            L.say(f"  {'create' if self.apply else 'would create'} label: {name}")
            if self.apply:
                self.gh.rest("POST", f"{self.base}/labels", {"name": name, "color": color, "description": desc})
            self.counts["labels"] += 1

    def create_or_find(self, title, body, labels, assignees, key, issue_type=""):
        issues = self.load_issues() if self.gh else {}
        if title in issues:
            iss = issues[title]
            self.numbers[key], self.ids[key] = iss["number"], iss["id"]
            L.say(f"  exists #{iss['number']}: {title}")
            return iss, False
        L.say(f"  {'create' if self.apply else 'would create'}: {title}")
        if not self.apply:
            self.planned.add(key)
            return None, True
        payload = {"title": title, "body": body, "labels": labels}
        if assignees:
            payload["assignees"] = assignees
        if issue_type:
            payload["type"] = issue_type
        iss = self.gh.rest("POST", f"{self.base}/issues", payload)
        issues[title] = iss
        self.numbers[key], self.ids[key] = iss["number"], iss["id"]
        self.created.add(key)
        time.sleep(0.8)
        L.say(f"    -> #{iss['number']}")
        return iss, True

    def ensure_sub(self, parent_key, child_key):
        parent, child = self.numbers.get(parent_key), self.ids.get(child_key)
        if not parent or not child:
            return
        subs = {s["number"] for s in self.gh.paged(f"{self.base}/issues/{parent}/sub_issues")}
        if self.numbers[child_key] in subs:
            return
        L.say(f"  link #{self.numbers[child_key]} under #{parent}")
        self.gh.rest("POST", f"{self.base}/issues/{parent}/sub_issues", {"sub_issue_id": child})
        self.counts["links"] += 1
        time.sleep(0.5)


def run(argv=None):
    ap = argparse.ArgumentParser(
        description="Create labels, sub-epics, work item issues, links and the Epic roll-up comment from plan.yaml. Dry run unless --apply.",
        epilog="The token is read from --token-file, CARRYDOWN_GITHUB_TOKEN or ~/.config/carrydown/github_token. It is never printed.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--repo", help="owner/name. Overrides project.repo in plan.yaml")
    ap.add_argument("--token-file", help="file that holds the GitHub token")
    ap.add_argument("--apply", action="store_true", help="write to GitHub. Without it nothing is written")
    ap.add_argument("--offline", action="store_true", help="do not call GitHub at all, even to read")
    ap.add_argument("--verify", action="store_true", help="read GitHub and check that the structure matches the plan, then exit")
    ap.add_argument("--create-epic", action="store_true", help="create a parent Epic issue when project.epic is empty")
    ap.add_argument("--update-bodies", action="store_true", help="also rewrite the bodies of issues that already exist")
    ap.add_argument("--skip-comment", action="store_true", help="do not post or update the Epic roll-up comment")
    ap.add_argument("--skip-check", action="store_true", help="do not run the specification checker first")
    ap.add_argument("--issue-type", default="", help="GitHub issue type for work items, for example Task (organisations only)")
    ap.add_argument("--show-body", metavar="ID", help="print the issue body for one work item and exit (no network). Accepts WI-07 or 7")
    a = ap.parse_args(argv)

    root = Path(a.root).resolve()
    plan_path = L.find_plan(root, a.plan)
    if not plan_path.exists():
        L.die(f"no plan at {plan_path}")
    plan, problems = L.load_plan(plan_path)
    if problems:
        L.say("plan.yaml has problems:")
        for p in problems:
            L.say("  - " + p)
        return 1
    if a.show_body:
        m = re.search(r"(\d+)\s*$", str(a.show_body))
        wanted = int(m.group(1)) if m else None
        it = L.item_by_id(plan).get(wanted)
        if not it:
            L.die(f"no item with id {a.show_body}. Use the tag (for example {L.tag(plan, plan['items'][0]['id'])}) or the number")
        L.say(build_item_body(plan, root, it))
        return 0
    if not a.skip_check:
        rc = check_specs.main(["--root", str(root), "--plan", str(plan_path), "--quiet"])
        if rc != 0:
            L.say("The checker found problems. Run check_specs.py to see them, fix them, or pass --skip-check.")
            return 1
    owner, repo = L.repo_parts(plan, a.repo)
    plan["project"]["repo"] = f"{owner}/{repo}"
    proj = plan["project"]
    gh = None
    if not a.offline:
        token = L.read_token(a.token_file, required=a.apply or a.verify)
        if token:
            gh = L.GitHub(token)
    L.say("")
    L.say(f"carrydown github_sync  {'APPLY' if a.apply else 'VERIFY (read only)' if a.verify else 'DRY RUN (nothing will be written)'}")
    L.say(f"repository: {owner}/{repo}    plan: {plan_path.relative_to(root)}")
    L.say(f"{len(plan['milestones'])} milestones, {len(plan['items'])} work items, {len(plan['tracks'])} tracks, {len(plan['program']['items'])} program items kept outside the plan")
    if gh is None:
        L.say("no token available or --offline: showing the plan only, nothing is read from GitHub")
    s = Sync(plan, root, gh, owner, repo, a.apply)
    if gh:
        status, js = gh.rest_status("GET", s.base)
        if status == 404:
            L.say(f"repository {owner}/{repo} was not found, or the token cannot see it.")
            if a.apply or a.verify:
                return 1
            gh = s.gh = None
        elif not a.apply:
            L.say(f"repository found (private: {js.get('private')}). Reading existing labels and issues.")
    if a.verify:
        return verify(s, plan, root)

    L.say("\nLabels")
    if gh:
        s.labels()
    else:
        for name, _, desc in s.desired_labels():
            L.say(f"  would create label if missing: {name}")

    epic = proj.get("epic")
    if epic and gh:
        e = gh.rest("GET", f"{s.base}/issues/{epic}")
        s.numbers["EPIC"], s.ids["EPIC"] = e["number"], e["id"]
        L.say(f"\nEpic: #{epic} {e['title']}")
    elif a.create_epic and not epic:
        L.say("\nEpic")
        body = f"Parent Epic for {proj['name']}. The sub-epics and work items are linked below as sub-issues.\n"
        s.create_or_find(proj["epic_title"], body, [proj["slug"]], [], "EPIC")
    elif not epic:
        L.say("\nEpic: none. Sub-epics will be created without a parent. Use --create-epic to create one.")

    people = {p["id"]: p for p in plan["people"]}
    L.say("\nSub-epics")
    for ms in plan["milestones"]:
        s.create_or_find(subepic_title(plan, ms), build_subepic_body(plan, root, ms), [proj["slug"], "sub-epic"], [], f"M{ms['number']}")
    L.say("\nWork items")
    for it in plan["items"]:
        t = L.tag(plan, it["id"])
        assignee = people.get(it["owner"], {}).get("github")
        s.create_or_find(item_title(plan, it), build_item_body(plan, root, it), [proj["slug"], it["track"]], [assignee] if assignee else [], t, a.issue_type)
    if not a.apply:
        n_epic = 1 if "EPIC" in s.planned else 0
        n_sub = sum(1 for k in s.planned if re.fullmatch(r"M\d+", k))
        n_it = len(s.planned) - n_epic - n_sub
        L.say(f"\nSummary: would create {n_epic} Epic, {n_sub} sub-epics and {n_it} work item issues"
              f" ({len(plan['milestones']) - n_sub} sub-epics and {len(plan['items']) - n_it} issues already exist).")
        L.say("Would then link each work item under its sub-epic" + (" and each sub-epic under the Epic" if epic or a.create_epic else "") + ",")
        L.say("rewrite dependency ids in the bodies to issue links, update the sub-epic work item lists,")
        L.say("and " + ("post" if not a.skip_comment and (epic or a.create_epic) else "skip") + " the Epic roll-up comment.")
        for it in plan["items"]:
            L.say(f"  {L.tag(plan, it['id'])}  {it['track']:<12} {it['complete_by']}  depends: {', '.join(L.tag(plan, d) for d in it['depends']) or '-'}" + (f"  program input: {it['program_input']}" if it['program_input'] else ""))
        L.say("\nDry run complete. Read it, then add --apply to write.")
        return 0

    L.say("\nLinks")
    epic_key = "EPIC" if "EPIC" in s.numbers else None
    for ms in plan["milestones"]:
        if epic_key:
            s.ensure_sub(epic_key, f"M{ms['number']}")
    for it in plan["items"]:
        s.ensure_sub(f"M{it['milestone']}", L.tag(plan, it["id"]))
    L.say("\nLinking dependency ids and work item lists")
    issues = s.load_issues()
    for ms in plan["milestones"]:
        key = f"M{ms['number']}"
        cur = issues[subepic_title(plan, ms)]
        want = build_subepic_body(plan, root, ms, s.numbers)
        have = (cur.get("body") or "").replace("\r\n", "\n")
        if want != have and (key in s.created or a.update_bodies):
            gh.rest("PATCH", f"{s.base}/issues/{cur['number']}", {"body": want})
            cur["body"] = want
            s.counts["bodies"] += 1
            L.say(f"  updated work item list in #{cur['number']}")
            time.sleep(0.4)
    for it in plan["items"]:
        t = L.tag(plan, it["id"])
        title = item_title(plan, it)
        cur = issues[title]
        want = build_item_body(plan, root, it, s.numbers)
        have = (cur.get("body") or "").replace("\r\n", "\n")
        is_new = t in s.created
        if want != have and (is_new or a.update_bodies):
            gh.rest("PATCH", f"{s.base}/issues/{cur['number']}", {"body": want})
            cur["body"] = want
            s.counts["bodies"] += 1
            L.say(f"  linked dependencies in #{cur['number']} {t}")
            time.sleep(0.4)
    if not a.skip_comment and epic_key:
        L.say("\nEpic roll-up comment")
        num = s.numbers["EPIC"]
        text = build_rollup(plan, s.numbers, num)
        existing = [c for c in gh.paged(f"{s.base}/issues/{num}/comments") if MARKER in (c.get("body") or "")]
        if existing:
            if existing[0]["body"].replace("\r\n", "\n") != text:
                gh.rest("PATCH", f"{s.base}/issues/comments/{existing[0]['id']}", {"body": text})
                L.say(f"  updated comment {existing[0]['html_url']}")
            else:
                L.say("  comment already up to date")
        else:
            c = gh.rest("POST", f"{s.base}/issues/{num}/comments", {"body": text})
            L.say(f"  posted comment {c['html_url']}")
    elif not epic_key:
        L.say("\nNo Epic, so no roll-up comment. The sub-epics hold their own work item lists.")
    L.say("\nSummary")
    L.say(f"  labels created: {s.counts['labels']}")
    L.say("  sub-epics: " + ", ".join(f"#{s.numbers[f'M{m['number']}']}" for m in plan["milestones"]))
    L.say(f"  work items: {len(plan['items'])} ({s.numbers[L.tag(plan, plan['items'][0]['id'])]} to {max(s.numbers[L.tag(plan, i['id'])] for i in plan['items'])})")
    L.say(f"  new sub-issue links: {s.counts['links']}, bodies rewritten: {s.counts['bodies']}")
    L.say("Next: python3 scripts/github_project.py to build the board. Then run this script with --verify.")
    return 0


def verify(s, plan, root):
    gh = s.gh
    L.say("\nVerification (read only)")
    ok = True
    labels = {l["name"].lower() for l in gh.paged(f"{s.base}/labels")}
    want_labels = [n for n, _, _ in s.desired_labels()]
    miss = [n for n in want_labels if n.lower() not in labels]
    L.say(f"  labels: {len(want_labels) - len(miss)} of {len(want_labels)} present" + (f", missing {miss}" if miss else ""))
    ok &= not miss
    issues = s.load_issues()
    sub_ok = 0
    item_ok = 0
    link_total = 0
    for ms in plan["milestones"]:
        t = subepic_title(plan, ms)
        if t not in issues:
            L.say(f"  MISSING sub-epic: {t}")
            ok = False
            continue
        sub_ok += 1
        s.numbers[f"M{ms['number']}"] = issues[t]["number"]
    for it in plan["items"]:
        t = item_title(plan, it)
        if t not in issues:
            L.say(f"  MISSING work item: {t}")
            ok = False
            continue
        item_ok += 1
        s.numbers[L.tag(plan, it["id"])] = issues[t]["number"]
    L.say(f"  sub-epics: {sub_ok} of {len(plan['milestones'])}")
    L.say(f"  work item issues: {item_ok} of {len(plan['items'])}")
    for ms in plan["milestones"]:
        key = f"M{ms['number']}"
        if key not in s.numbers:
            continue
        subs = {x["number"] for x in gh.paged(f"{s.base}/issues/{s.numbers[key]}/sub_issues")}
        want = {s.numbers[L.tag(plan, it["id"])] for it in plan["items"] if it["milestone"] == ms["number"] and L.tag(plan, it["id"]) in s.numbers}
        link_total += len(subs & want)
        if subs != want:
            L.say(f"  sub-issues of #{s.numbers[key]}: expected {sorted(want)}, found {sorted(subs)}")
            ok = False
    L.say(f"  sub-issue links work item to sub-epic: {link_total} of {len(plan['items'])}")
    bad = 0
    for it in plan["items"]:
        t = item_title(plan, it)
        if t in issues:
            body = (issues[t].get("body") or "").replace("\r\n", "\n")
            heads = [l[4:] for l in body.split("\n") if l.startswith("### ")]
            if not all(h in heads for h in SEVEN):
                bad += 1
                L.say(f"  body of #{issues[t]['number']} lacks a required heading")
            unlinked = [m.group(0) for m in re.finditer(rf"\b{re.escape(plan['project']['id_prefix'])}-\d+\b(?! \(#)", body)]
            if unlinked and L.tag(plan, it["id"]) in s.numbers:
                # ids that are not links yet (the item's own id in a heading is allowed)
                pass
    L.say(f"  bodies with all seven headings: {item_ok - bad} of {item_ok}")
    ok &= bad == 0
    epic = plan["project"].get("epic") or (issues.get(plan["project"]["epic_title"]) or {}).get("number")
    if epic:
        subs = {x["number"] for x in gh.paged(f"{s.base}/issues/{epic}/sub_issues")}
        want = {s.numbers[f"M{m['number']}"] for m in plan["milestones"] if f"M{m['number']}" in s.numbers}
        L.say(f"  sub-epics under Epic #{epic}: {len(subs & want)} of {len(want)}")
        com = [c for c in gh.paged(f"{s.base}/issues/{epic}/comments") if MARKER in (c.get("body") or "")]
        L.say(f"  Epic roll-up comment: {'present' if com else 'missing'}")
        ok &= bool(com) and subs >= want
    L.say("verification " + ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
