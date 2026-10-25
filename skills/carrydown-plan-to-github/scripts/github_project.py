#!/usr/bin/env python3
"""Create or configure a GitHub Project (v2) board from plan.yaml, and fill it.

What it builds
  fields   Work unit (iteration field, one iteration per milestone with its own length, gaps for breaks)
           Track (single select, one option per track)
           Complete by (date)
           Checkpoint (date)
  views    Table, Board and Roadmap, with the plan fields visible
  items    every sub-epic, work item issue and the Epic (if any) added to the project,
           with Work unit, Track, Complete by and Checkpoint filled in

What the API cannot set, so you click it once (see references/project-board.md in the
carrydown-plan-to-github skill)
  group by Work unit, sort order, slice by, field sums, the Board column field,
  the Roadmap date fields, markers and zoom level, and the project workflows
  (auto-add, close sets status). The script prints this list again at the end.

Safety
  Dry run unless you pass --apply. A dry run reads from GitHub when a token is available and
  prints what it would create. Fields and views that exist are left alone. The Work unit
  iterations are replaced only with --reconfigure-iterations. The token is never printed.

Usage
  python3 scripts/github_project.py --root . --repo owner/name            dry run
  python3 scripts/github_project.py --root . --repo owner/name --apply    write
  python3 scripts/github_project.py --root . --repo owner/name --verify   read and report
"""
import argparse
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import github_client as G  # noqa: E402
import github_sync as S  # noqa: E402

CLICK = [
    "Group the Table view by Work unit (View menu, Group by).",
    "Sort the Table view by Complete by (View menu, Sort).",
    "Set the Board view columns (Column field) to Status, or to Work unit if you prefer.",
    "Roadmap view: choose Complete by (and Checkpoint if you like) as the date fields, set the zoom level, show markers for iterations.",
    "Optional: slice by Track, and turn on field sums.",
    "Project settings, Workflows: turn on 'Auto-add to project' for the repository, and set 'Item closed' to Status Done.",
    "Optional: write a one-paragraph project description and README in Settings.",
]

FIELD_Q = """
query($p: ID!) { node(id: $p) { ... on ProjectV2 {
  id title number url
  fields(first: 50) { nodes {
    ... on ProjectV2Field { id name dataType }
    ... on ProjectV2SingleSelectField { id name dataType options { id name } }
    ... on ProjectV2IterationField { id name dataType configuration { iterations { id title startDate duration } completedIterations { id title startDate duration } } }
  } }
  views(first: 20) { nodes { id name number layout filter groupByFields(first: 5) { nodes { ... on ProjectV2FieldCommon { name } } }
    fields(first: 30) { nodes { ... on ProjectV2FieldCommon { id } } } } }
} } }
"""
ITEMS_Q = """
query($p: ID!, $after: String) { node(id: $p) { ... on ProjectV2 {
  items(first: 100, after: $after) { pageInfo { hasNextPage endCursor } nodes {
    id content { ... on Issue { number } }
    fieldValues(first: 30) { nodes {
      ... on ProjectV2ItemFieldIterationValue { iterationId field { ... on ProjectV2FieldCommon { name } } }
      ... on ProjectV2ItemFieldSingleSelectValue { optionId field { ... on ProjectV2FieldCommon { name } } }
      ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } }
    } }
  } }
} } }
"""


def days_inclusive(start, end):
    return (L.parse_date(end) - L.parse_date(start)).days + 1


def desired_iterations(plan):
    """One iteration per milestone. Weekends between two work units belong to the earlier one,
    so they do not show as breaks. A declared break leaves a real gap in the iterations."""
    out = []
    ms = plan["milestones"]
    for i, m in enumerate(ms):
        start = L.parse_date(m["start"])
        end = L.parse_date(m["end"])
        if i + 1 < len(ms):
            nxt = L.parse_date(ms[i + 1]["start"])
            stops = [L.parse_date(b["start"]) for b in plan["breaks"] if end < L.parse_date(b["start"]) < nxt]
            end = (min(stops) if stops else nxt) - dt.timedelta(days=1)
        out.append({"title": f"Work unit {m['number']}, {m['name']}", "startDate": m["start"], "duration": (end - start).days + 1})
    return out


def break_ranges(plan):
    """The gaps GitHub will show as breaks: from the declared break start to the day before the next work unit."""
    out = []
    ms = plan["milestones"]
    for b in plan["breaks"]:
        bs = L.parse_date(b["start"])
        nxt = next((L.parse_date(m["start"]) for m in ms if L.parse_date(m["start"]) > bs), None)
        out.append((b["name"], bs, (nxt - dt.timedelta(days=1)) if nxt else L.parse_date(b["end"])))
    return out


def find_project(gh, owner, owner_type, title, number=None):
    root = "organization" if owner_type == "Organization" else "user"
    q = f"""query($l: String!) {{ {root}(login: $l) {{ projectsV2(first: 100) {{ nodes {{ id title number url closed }} }} }} }}"""
    nodes = gh.graphql(q, {"l": owner})[root]["projectsV2"]["nodes"]
    for n in nodes:
        if n["closed"]:
            continue
        if (number and n["number"] == number) or (not number and n["title"] == title):
            return n
    return None


def load_project(gh, pid):
    return gh.graphql(FIELD_Q, {"p": pid})["node"]


def field_map(proj):
    return {f["name"]: f for f in proj["fields"]["nodes"] if f}


def load_items(gh, pid):
    out, after = {}, None
    while True:
        d = gh.graphql(ITEMS_Q, {"p": pid, "after": after})["node"]["items"]
        for n in d["nodes"]:
            num = (n["content"] or {}).get("number")
            if num is None:
                continue
            vals = {}
            for fv in n["fieldValues"]["nodes"]:
                if not fv or "field" not in fv or not fv["field"]:
                    continue
                name = fv["field"].get("name")
                vals[name] = fv.get("iterationId") or fv.get("optionId") or fv.get("date")
            out[num] = {"id": n["id"], "values": vals}
        if not d["pageInfo"]["hasNextPage"]:
            return out
        after = d["pageInfo"]["endCursor"]


def run(argv=None):
    try:
        return _run(argv)
    except G.GitHubError as e:
        return G.report(e)


def _run(argv=None):
    ap = argparse.ArgumentParser(
        description="Create or configure a GitHub Project (v2) from plan.yaml and fill it with the plan's issues. Dry run unless --apply.",
        epilog="The token needs the project scope (classic) or Projects read and write (fine-grained), plus repo access. It is never printed.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--repo", help="owner/name of the repository whose issues go on the board")
    ap.add_argument("--owner", help="user or organization that owns the project (default: the repository owner)")
    ap.add_argument("--title", help="project title (default: project.project_title in plan.yaml)")
    ap.add_argument("--project-number", type=int, help="configure this existing project instead of finding or creating one by title")
    ap.add_argument("--token-file", help="file that holds the GitHub token")
    ap.add_argument("--apply", action="store_true", help="write to GitHub. Without it nothing is written")
    ap.add_argument("--verify", action="store_true", help="read the project and report fields, views and filled values, then exit")
    ap.add_argument("--reconfigure-iterations", action="store_true", help="replace the Work unit iterations if they differ from the plan")
    ap.add_argument("--offline", action="store_true", help="do not call GitHub; print the intended configuration only")
    a = ap.parse_args(argv)
    if a.offline and (a.apply or a.verify):
        L.die(f"--offline cannot be combined with {'--apply' if a.apply else '--verify'}: both need GitHub. "
              "Leave out --offline to write or verify, or leave out the other flag for an offline dry run")
    if a.project_number is not None and a.project_number < 1:
        L.die("--project-number must be a project number, 1 or more")

    root = L.project_root(a.root)
    plan_path = L.find_plan(root, a.plan)
    if not plan_path.exists():
        L.die(f"no plan at {plan_path}")
    plan, problems = L.load_plan(plan_path)
    if problems:
        L.say("plan.yaml has problems:")
        for p in problems:
            L.say("  - " + p)
        return 1
    owner_repo, name = L.repo_parts(plan, a.repo)
    plan["project"]["repo"] = f"{owner_repo}/{name}"
    owner = a.owner or owner_repo
    title = a.title or plan["project"]["project_title"]
    iterations = desired_iterations(plan)

    L.say("")
    L.say(f"carrydown github_project  {'APPLY' if a.apply else 'VERIFY' if a.verify else 'DRY RUN (nothing will be written)'}")
    L.say(f"project: {title!r}  owner: {owner}  repository: {owner_repo}/{name}")
    L.say("fields to ensure:")
    L.say("  Work unit (iteration): " + "; ".join(f"{i['title']} {i['startDate']} +{i['duration']}d" for i in iterations))
    for name_, bs, be in break_ranges(plan):
        L.say(f"    gap left for break {name_!r}: {bs} to {be} (shows as a break)")
    L.say("  Track (single select): " + ", ".join(t["label"] for t in plan["tracks"]))
    L.say("  Complete by (date), Checkpoint (date)")
    L.say("views to ensure: Table, Board, Roadmap")
    if a.offline:
        L.say("offline: nothing read from GitHub")
        return 0
    token = G.read_token(a.token_file, required=a.apply or a.verify)
    if not token:
        L.say(f"not checked against GitHub (no token): showing the intended configuration only. To set one up, run: python3 {G.TOKEN_SCRIPT}")
        return 0
    gh = G.GitHub(token, pause=0.3)
    st, ujs = gh.rest_status("GET", f"/users/{owner}")
    if st == 404:
        L.die(f"owner {owner} not found")
    owner_type, owner_node = ujs["type"], ujs["node_id"]
    st, rjs = gh.rest_status("GET", f"/repos/{owner_repo}/{name}")
    if st == 404:
        L.say(f"repository {owner_repo}/{name} not found, or the token cannot see it")
        return 1
    repo_node = rjs["node_id"]
    base = f"/repos/{owner_repo}/{name}"

    # issues to place: only issues with the project label, matched by marker, then by title.
    # Titles printed below are the plan's, never the ones fetched from GitHub.
    sync = S.Sync(plan, root, gh, owner_repo, name, False)
    placements = []   # (issue, kind, milestone, item, plan title)
    epic = plan["project"].get("epic")
    epic_issue = None
    if epic:
        epic_issue = gh.rest("GET", f"{base}/issues/{epic}")
    else:
        epic_issue = sync.find("EPIC", plan["project"]["epic_title"])
    if epic_issue:
        placements.append((epic_issue, "epic", None, None, plan["project"]["epic_title"]))
    missing = []
    for ms in plan["milestones"]:
        t = S.subepic_title(plan, ms)
        iss = sync.find(f"M{ms['number']}", t)
        (placements.append((iss, "subepic", ms, None, t)) if iss else missing.append(t))
    for it in plan["items"]:
        t = S.item_title(plan, it)
        iss = sync.find(L.tag(plan, it["id"]), t)
        (placements.append((iss, "item", L.milestone_by_num(plan)[it["milestone"]], it, t)) if iss else missing.append(t))
    L.say(f"issues found in the repository: {len(placements)}; missing: {len(missing)}")
    for t in missing:
        L.say(f"  missing issue: {t}  (run github_sync.py --apply first)")
    if missing and a.apply:
        L.say("Create the issues first, then rerun this script.")
        return 1

    proj = find_project(gh, owner, owner_type, title, a.project_number)
    if a.project_number and not proj:
        L.die(f"project #{a.project_number} was not found for {owner}, or it is closed, so nothing was created. "
              "Check the number in the project's address, or leave out --project-number to find or create the project by title", 1)
    if a.verify and not proj:
        L.say("project not found")
        return 1
    if proj:
        L.say(f"project exists: #{proj['number']} {proj['url']}")
    else:
        L.say(f"project does not exist yet. {'Creating' if a.apply else 'Would create'} {title!r}.")
        if a.apply:
            r = gh.graphql("mutation($o: ID!, $t: String!, $r: ID) { createProjectV2(input: {ownerId: $o, title: $t, repositoryId: $r}) { projectV2 { id title number url } } }",
                           {"o": owner_node, "t": title, "r": repo_node})
            proj = r["createProjectV2"]["projectV2"]
            L.say(f"  created #{proj['number']} {proj['url']}")
            try:
                gh.graphql("mutation($p: ID!, $r: ID!) { linkProjectV2ToRepository(input: {projectId: $p, repositoryId: $r}) { repository { id } } }", {"p": proj["id"], "r": repo_node})
                L.say("  linked the project to the repository")
            except G.GitHubError as e:
                L.say(f"  could not link to the repository: {e}")
    if not proj:
        L.say("\nDry run complete. Add --apply to create the project, fields, views and items.")
        return 0

    pdata = load_project(gh, proj["id"])
    fields = field_map(pdata)

    # ---------------- fields ----------------
    L.say("\nFields")
    if "Work unit" not in fields:
        L.say(f"  {'create' if a.apply else 'would create'} Work unit with {len(iterations)} iterations")
        if a.apply:
            first = iterations[0]
            gh.graphql("""mutation($p: ID!, $c: ProjectV2IterationFieldConfigurationInput!) {
              createProjectV2Field(input: {projectId: $p, dataType: ITERATION, name: "Work unit", iterationConfiguration: $c}) { projectV2Field { ... on ProjectV2IterationField { id } } } }""",
                       {"p": proj["id"], "c": {"startDate": first["startDate"], "duration": first["duration"], "iterations": iterations}})
    else:
        have = fields["Work unit"]["configuration"]["iterations"] + fields["Work unit"]["configuration"].get("completedIterations", [])
        have_t = sorted((i["title"], i["startDate"], i["duration"]) for i in have)
        want_t = sorted((i["title"], i["startDate"], i["duration"]) for i in iterations)
        if have_t == want_t:
            L.say("  Work unit exists with the planned iterations")
        elif a.reconfigure_iterations and a.apply:
            first = iterations[0]
            gh.graphql("""mutation($f: ID!, $c: ProjectV2IterationFieldConfigurationInput!) {
              updateProjectV2Field(input: {fieldId: $f, iterationConfiguration: $c}) { projectV2Field { ... on ProjectV2IterationField { id } } } }""",
                       {"f": fields["Work unit"]["id"], "c": {"startDate": first["startDate"], "duration": first["duration"], "iterations": iterations}})
            L.say("  Work unit iterations replaced to match the plan")
        else:
            L.say("  Work unit exists but its iterations differ from the plan. Rerun with --reconfigure-iterations to replace them.")
    if "Track" not in fields:
        L.say(f"  {'create' if a.apply else 'would create'} Track with {len(plan['tracks'])} options")
        if a.apply:
            opts = [{"name": t["label"], "color": str(t.get("color", "GRAY")).upper(), "description": f"{t['label']} track"} for t in plan["tracks"]]
            gh.graphql("""mutation($p: ID!, $o: [ProjectV2SingleSelectFieldOptionInput!]) {
              createProjectV2Field(input: {projectId: $p, dataType: SINGLE_SELECT, name: "Track", singleSelectOptions: $o}) { projectV2Field { ... on ProjectV2SingleSelectField { id } } } }""",
                       {"p": proj["id"], "o": opts})
    else:
        have = {o["name"] for o in fields["Track"]["options"]}
        want = {t["label"] for t in plan["tracks"]}
        L.say("  Track exists" + (f" but lacks options {sorted(want - have)}" if want - have else " with the planned options"))
    for fname in ("Complete by", "Checkpoint"):
        if fname not in fields:
            L.say(f"  {'create' if a.apply else 'would create'} {fname} (date)")
            if a.apply:
                gh.graphql("mutation($p: ID!, $n: String!) { createProjectV2Field(input: {projectId: $p, dataType: DATE, name: $n}) { projectV2Field { ... on ProjectV2Field { id } } } }", {"p": proj["id"], "n": fname})
        else:
            L.say(f"  {fname} exists")
    if a.apply:
        pdata = load_project(gh, proj["id"])
        fields = field_map(pdata)

    # ---------------- views ----------------
    L.say("\nViews")
    views = pdata["views"]["nodes"]
    names = {v["name"]: v for v in views}
    visible = [fields[n]["id"] for n in ("Title", "Assignees", "Status", "Work unit", "Track", "Complete by", "Checkpoint", "Parent issue") if n in fields and fields[n].get("id")]
    wanted = [("Table", "TABLE_LAYOUT"), ("Board", "BOARD_LAYOUT"), ("Roadmap", "ROADMAP_LAYOUT")]
    for vname, layout in wanted:
        if vname in names:
            L.say(f"  {vname} exists ({names[vname]['layout']})")
            continue
        default = next((v for v in views if v["name"] in ("View 1",) and v["layout"] == layout), None)
        if default:
            L.say(f"  {'rename' if a.apply else 'would rename'} the default view to {vname}")
            if a.apply:
                gh.graphql("mutation($v: ID!, $n: String!) { updateProjectV2View(input: {viewId: $v, name: $n}) { projectV2View { id } } }", {"v": default["id"], "n": vname})
                names[vname] = default
            continue
        L.say(f"  {'create' if a.apply else 'would create'} {vname} view ({layout})")
        if a.apply:
            r = gh.graphql("mutation($p: ID!, $n: String!, $l: ProjectV2ViewLayout!) { createProjectV2View(input: {projectId: $p, name: $n, layout: $l}) { projectV2View { id name layout } } }",
                           {"p": proj["id"], "n": vname, "l": layout})
            names[vname] = r["createProjectV2View"]["projectV2View"]
    if a.apply:
        for vname, layout in wanted:
            v = names.get(vname)
            if layout == "ROADMAP_LAYOUT" or not (v and visible):
                continue   # GitHub rejects visible fields on roadmap views
            shown = {f.get("id") for f in ((v.get("fields") or {}).get("nodes") or []) if f}
            if set(visible) <= shown:
                continue   # already shows the plan fields: a rerun sends nothing
            try:
                gh.graphql("mutation($v: ID!, $f: [ID!]) { updateProjectV2View(input: {viewId: $v, configuration: {visibleFieldIds: $f}}) { projectV2View { id } } }", {"v": v["id"], "f": visible})
            except G.GitHubError as e:
                L.say(f"  could not set visible fields on {vname}: {str(e)[:160]}")
        L.say("  visible fields set on the Table and Board views (the Roadmap view takes its fields from its settings)")

    # ---------------- items ----------------
    L.say("\nItems")
    iter_field = fields.get("Work unit")
    iter_ids = {}
    if iter_field and iter_field.get("configuration"):
        for i in iter_field["configuration"]["iterations"] + iter_field["configuration"].get("completedIterations", []):
            iter_ids[i["title"]] = i["id"]
    track_ids = {o["name"]: o["id"] for o in (fields.get("Track") or {}).get("options", [])}
    existing = load_items(gh, proj["id"])
    added = 0
    filled = 0
    for issue, kind, ms, it, ptitle in placements:
        num = issue["number"]
        if num not in existing:
            if not a.apply:
                L.say(f"  would add #{num} {ptitle}")
                continue
            r = gh.graphql("mutation($p: ID!, $c: ID!) { addProjectV2ItemById(input: {projectId: $p, contentId: $c}) { item { id } } }", {"p": proj["id"], "c": issue["node_id"]})
            existing[num] = {"id": r["addProjectV2ItemById"]["item"]["id"], "values": {}}
            added += 1
            L.say(f"  added #{num} {ptitle}")
        if not a.apply or kind == "epic":
            continue
        desired = {}
        wu_title = f"Work unit {ms['number']}, {ms['name']}"
        if "Work unit" in fields and wu_title in iter_ids:
            desired["Work unit"] = ("iterationId", iter_ids[wu_title])
        if kind == "item":
            if "Track" in fields:
                tl = L.track_label(plan, it["track"])
                if tl in track_ids:
                    desired["Track"] = ("singleSelectOptionId", track_ids[tl])
            desired["Complete by"] = ("date", it["complete_by"])
            desired["Checkpoint"] = ("date", it["checkpoint"])
        else:
            desired["Complete by"] = ("date", ms["end"])
            desired["Checkpoint"] = ("date", ms["demo"])
        for fname, (key, val) in desired.items():
            if fname not in fields:
                continue
            if existing[num]["values"].get(fname) == val:
                continue
            gh.graphql("mutation($p: ID!, $i: ID!, $f: ID!, $v: ProjectV2FieldValue!) { updateProjectV2ItemFieldValue(input: {projectId: $p, itemId: $i, fieldId: $f, value: $v}) { projectV2Item { id } } }",
                       {"p": proj["id"], "i": existing[num]["id"], "f": fields[fname]["id"], "v": {key: val}})
            filled += 1
            time.sleep(0.1)
    L.say(f"  items added: {added}; field values set: {filled}")

    # ---------------- report ----------------
    if a.apply or a.verify:
        L.say("\nVerification (read only)")
        pdata = load_project(gh, proj["id"])
        fields = field_map(pdata)
        existing = load_items(gh, proj["id"])
        wanted_nums = {p[0]["number"] for p in placements}
        L.say(f"  project items that are plan issues: {len(wanted_nums & set(existing))} of {len(wanted_nums)}")
        n_sub = sum(1 for p in placements if p[1] == "subepic")
        n_item = sum(1 for p in placements if p[1] == "item")
        expect = {"Work unit": n_sub + n_item, "Track": n_item, "Complete by": n_sub + n_item, "Checkpoint": n_sub + n_item}
        for fname in ("Work unit", "Track", "Complete by", "Checkpoint"):
            if fname not in fields:
                L.say(f"  field {fname}: MISSING")
                continue
            n = sum(1 for num in wanted_nums & set(existing) if existing[num]["values"].get(fname))
            L.say(f"  field {fname}: present, filled on {n} of {expect[fname]} items")
        for v in pdata["views"]["nodes"]:
            groups = [g["name"] for g in (v["groupByFields"] or {}).get("nodes", []) if g]
            L.say(f"  view {v['name']}: {v['layout']}, group by {groups or 'none'}")
        it_cfg = fields.get("Work unit", {}).get("configuration", {})
        L.say(f"  Work unit iterations: {len(it_cfg.get('iterations', [])) + len(it_cfg.get('completedIterations', []))}")
        L.say(f"  project: {proj['url']}")
    L.say("\nThe API cannot set these. Click them once in the project (see references/project-board.md in the carrydown-plan-to-github skill):")
    for c in CLICK:
        L.say("  - " + c)
    if not a.apply and not a.verify:
        L.say("\nDry run complete. Add --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
