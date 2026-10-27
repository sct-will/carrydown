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
import re
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
query($p: ID!, $fa: String, $va: String) { node(id: $p) { ... on ProjectV2 {
  id title number url
  fields(first: 50, after: $fa) { pageInfo { hasNextPage endCursor } nodes {
    ... on ProjectV2Field { id name dataType }
    ... on ProjectV2SingleSelectField { id name dataType options { id name color description } }
    ... on ProjectV2IterationField { id name dataType configuration { iterations { id title startDate duration } completedIterations { id title startDate duration } } }
  } }
  views(first: 20, after: $va) { pageInfo { hasNextPage endCursor } nodes { id name number layout filter groupByFields(first: 5) { pageInfo { hasNextPage endCursor } nodes { ... on ProjectV2FieldCommon { name } } }
    fields(first: 30) { pageInfo { hasNextPage endCursor } nodes { ... on ProjectV2FieldCommon { id } } } } }
} } }
"""
ITEMS_Q = """
query($p: ID!, $after: String) { node(id: $p) { ... on ProjectV2 {
  items(first: 100, after: $after) { pageInfo { hasNextPage endCursor } nodes {
    id content { ... on Issue { number repository { nameWithOwner } } }
    fieldValues(first: 30) { pageInfo { hasNextPage endCursor } nodes {
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


def retry_graphql(gh, query, variables, context="project lookup"):
    """Retry reads and idempotent value assignments with a bounded delay."""
    for attempt in range(3):
        try:
            return gh.graphql(query, variables)
        except G.GitHubError as e:
            if e.kind in ("server", "network", "secondary") and attempt < 2:
                time.sleep(0.1 * (2 ** attempt))
                continue
            raise G.GitHubError(f"{context}: {e.line()}; successful updates were preserved. Rerun to resume", e.status, e.kind) from e


def connection_pages(gh, query, variables, path, continuation="after", first=None):
    """Read all nodes; reject missing or repeated continuation cursors."""
    out, after, seen = [], None, set()
    connection = first
    for _ in range(10000):
        if connection is None:
            data = retry_graphql(gh, query, {**variables, continuation: after}, f"connection {'.'.join(path)} after {after!r}")
            connection = data
            try:
                for key in path:
                    connection = connection[key]
            except (KeyError, TypeError):
                raise G.GitHubError(f"connection {'.'.join(path)} after {after!r} is inaccessible or incomplete. Check project read permission and rerun to resume") from None
        if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
            raise G.GitHubError(f"connection {'.'.join(path)} after {after!r} returned no readable nodes. Check project access and rerun to resume")
        out.extend(n for n in connection.get("nodes", []) if n)
        info = connection.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            return out
        after = info.get("endCursor")
        if not after or after in seen:
            raise G.GitHubError(f"connection {'.'.join(path)} has an invalid continuation token; rerun after checking API response")
        seen.add(after)
        connection = None
    raise G.GitHubError("project connection exceeded 10000 pages; rerun with a narrower project")


def find_project(gh, owner, owner_type, title, number=None):
    root = "organization" if owner_type == "Organization" else "user"
    q = f"""query($l: String!, $after: String) {{ {root}(login: $l) {{ projectsV2(first: 100, after: $after) {{ pageInfo {{ hasNextPage endCursor }} nodes {{ id title number url closed }} }} }} }}"""
    nodes = connection_pages(gh, q, {"l": owner}, (root, "projectsV2"))
    matches = [n for n in nodes if not n["closed"] and ((number and n["number"] == number) or (not number and n["title"] == title))]
    if len(matches) > 1:
        raise G.GitHubError(f"multiple projects named {title!r}; choose --project-number from {[n['number'] for n in matches]}")
    return matches[0] if matches else None


def load_project(gh, pid):
    data = retry_graphql(gh, FIELD_Q, {"p": pid, "fa": None, "va": None})["node"]
    for name, continuation in (("fields", "fa"), ("views", "va")):
        data[name]["nodes"] = connection_pages(gh, FIELD_Q, {"p": pid, "fa": None, "va": None}, ("node", name), continuation, data[name])
    for view in data["views"]["nodes"]:
        for name, selection in (("fields", "id"), ("groupByFields", "name")):
            first = view.get(name) or {"nodes": []}
            if (first.get("pageInfo") or {}).get("hasNextPage"):
                query = f"query($p: ID!, $after: String) {{ node(id: $p) {{ ... on ProjectV2View {{ {name}(first: 100, after: $after) {{ pageInfo {{ hasNextPage endCursor }} nodes {{ ... on ProjectV2FieldCommon {{ {selection} }} }} }} }} }} }}"
                view[name]["nodes"] = connection_pages(gh, query, {"p": view["id"]}, ("node", name), first=first)
    return data


def field_map(proj):
    return {f["name"]: f for f in proj["fields"]["nodes"] if f}


def load_items(gh, pid, repo):
    out = {}
    nodes = connection_pages(gh, ITEMS_Q, {"p": pid}, ("node", "items"))
    for n in nodes:
            content = n["content"] or {}
            num = content.get("number")
            owner_name = (content.get("repository") or {}).get("nameWithOwner", "")
            if num is None or owner_name.casefold() != repo.casefold():
                continue
            vals = {}
            query = "query($p: ID!, $after: String) { node(id: $p) { ... on ProjectV2Item { fieldValues(first: 100, after: $after) { pageInfo { hasNextPage endCursor } nodes { ... on ProjectV2ItemFieldIterationValue { iterationId field { ... on ProjectV2FieldCommon { name } } } ... on ProjectV2ItemFieldSingleSelectValue { optionId field { ... on ProjectV2FieldCommon { name } } } ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } } } } } } }"
            for fv in connection_pages(gh, query, {"p": n["id"]}, ("node", "fieldValues"), first=n["fieldValues"]):
                if not fv or "field" not in fv or not fv["field"]:
                    continue
                name = fv["field"].get("name")
                vals[name] = fv.get("iterationId") or fv.get("optionId") or fv.get("date")
            out[num] = {"id": n["id"], "values": vals}
    return out


def ensure_track_options(gh, pid, fields, tracks, apply=False):
    field = fields.get("Track")
    if not field:
        return
    options = field.get("options", [])
    folded = {}
    for option in options:
        folded.setdefault(option["name"].casefold(), []).append(option)
    for key, rows in folded.items():
        if len(rows) > 1:
            raise G.GitHubError(f"Track options differ only in case: {[r['name'] for r in rows]}. Rename these options explicitly, then rerun")
    missing = [t for t in tracks if t["label"].casefold() not in folded]
    if not missing:
        return
    L.say("  Track options to add: " + ", ".join(repr(t["label"]) for t in missing))
    if not apply:
        return
    preserved = [{k: o[k] for k in ("id", "name", "color", "description") if k in o} for o in options]
    for opt in preserved:
        opt.setdefault("color", "GRAY")
        opt.setdefault("description", "")
    wanted = preserved + [{"name": t["label"], "color": str(t.get("color", "GRAY")).upper(), "description": f"{t['label']} track"} for t in missing]
    retry_graphql(gh, "mutation($f: ID!, $o: [ProjectV2SingleSelectFieldOptionInput!]) { updateProjectV2Field(input: {fieldId: $f, singleSelectOptions: $o}) { projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } } } }", {"f": field["id"], "o": wanted}, "Track options update; check Projects write permission")
    refreshed = field_map(load_project(gh, pid)).get("Track", {})
    actual = {o["name"].casefold(): o.get("id") for o in refreshed.get("options", [])}
    if any(not actual.get(t["label"].casefold()) for t in tracks):
        raise G.GitHubError("Track option IDs could not be verified. Check Projects write permission and rerun to resume")
    if any(o.get("id") and actual.get(o["name"].casefold()) != o["id"] for o in options):
        raise G.GitHubError("Existing Track option identity changed unexpectedly. Review project item values before resuming; successful updates were preserved")


def verification_problems(plan, placements, missing, pdata, existing, iterations):
    """Compare the board with the plan. Counts alone cannot detect wrong dates or tracks."""
    problems = [f"missing issue: {title}" for title in missing]
    fields = field_map(pdata)
    for name, kind in (("Work unit", "ITERATION"), ("Track", "SINGLE_SELECT"),
                       ("Complete by", "DATE"), ("Checkpoint", "DATE")):
        if name not in fields:
            problems.append(f"field {name} is missing")
        elif fields[name].get("dataType") != kind:
            problems.append(f"field {name} must have type {kind}")
    cfg = fields.get("Work unit", {}).get("configuration", {})
    have_iterations = cfg.get("iterations", []) + cfg.get("completedIterations", [])
    values = lambda rows: sorted((i["title"], i["startDate"], i["duration"]) for i in rows)
    if values(have_iterations) != values(iterations):
        problems.append("Work unit iterations differ from the plan")
    iter_ids = {i["title"]: i["id"] for i in have_iterations}
    track_ids = {o["name"].casefold(): o["id"] for o in fields.get("Track", {}).get("options", [])}
    for track in plan["tracks"]:
        if not track_ids.get(track["label"].casefold()):
            problems.append(f"Track option: expected {track['label']!r}, actual missing; preview and apply the missing option")
    views = {v["name"]: v["layout"] for v in pdata["views"]["nodes"]}
    for name, layout in (("Table", "TABLE_LAYOUT"), ("Board", "BOARD_LAYOUT"), ("Roadmap", "ROADMAP_LAYOUT")):
        if views.get(name) != layout:
            problems.append(f"view {name} is missing or does not use {layout}")
    for issue, kind, ms, it, title in placements:
        num = issue["number"]
        if num not in existing:
            problems.append(f"issue #{num} is missing from the board: {title}")
            continue
        if kind == "epic":
            continue
        desired = {
            "Work unit": iter_ids.get(f"Work unit {ms['number']}, {ms['name']}"),
            "Complete by": it["complete_by"] if it else ms["end"],
            "Checkpoint": it["checkpoint"] if it else ms["demo"],
        }
        if it:
            desired["Track"] = track_ids.get(L.track_label(plan, it["track"]).casefold())
        for name, value in desired.items():
            if value is None or existing[num]["values"].get(name) != value:
                problems.append(f"{L.tag(plan, it['id']) if it else 'M' + str(ms['number'])} issue #{num} field {name}: expected {value!r}, actual {existing[num]['values'].get(name)!r}")
    return problems


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
    ap.add_argument("--allow-public", action="store_true", help="allow approved publication of a public repository's project")
    ap.add_argument("--verify", action="store_true", help="read the project and report fields, views and filled values, then exit")
    ap.add_argument("--reconfigure-iterations", action="store_true", help="replace the Work unit iterations if they differ from the plan")
    ap.add_argument("--offline", action="store_true", help="do not call GitHub; print the intended configuration only")
    a = ap.parse_args(argv)
    if a.apply and a.verify:
        L.die("--apply and --verify are separate runs. Apply first, then verify without --apply")
    if a.offline and (a.apply or a.verify):
        L.die(f"--offline cannot be combined with {'--apply' if a.apply else '--verify'}: both need GitHub. "
              "Leave out --offline to write or verify, or leave out the other flag for an offline dry run")
    if a.project_number is not None and a.project_number < 1:
        L.die("--project-number must be a project number, 1 or more")
    for flag, value in (("--owner", a.owner), ("--title", a.title)):
        if value is not None and not value.strip():
            L.die(f"{flag} is empty. Leave it out to use the default, or give a value")
    if a.owner is not None and not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", a.owner):
        L.die(f"--owner {a.owner!r} is not a GitHub user or organization name (letters, digits and hyphens)")
    if a.title is not None and (len(a.title) > 256 or not L._one_line(a.title)):
        L.die("--title must be one line of at most 256 characters")

    root = L.project_root(a.root)
    plan_path = L.find_plan(root, a.plan)
    if not L.exists(plan_path):
        L.die(f"no plan at {plan_path}")
    plan, problems = L.load_plan(plan_path, root)
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
    if a.apply and rjs.get("private") is False and not a.allow_public:
        L.die("public repository: confirm publication and preview again with --allow-public", 1)
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
                retry_graphql(gh, "mutation($p: ID!, $r: ID!) { linkProjectV2ToRepository(input: {projectId: $p, repositoryId: $r}) { repository { id } } }", {"p": proj["id"], "r": repo_node},
                              f"project {proj['id']}, repository link, intended {owner_repo}/{name}")
                L.say("  linked the project to the repository")
            except G.GitHubError as e:
                L.say(f"  could not link to the repository: {e}")
    if not proj:
        L.say("\nDry run complete. Add --apply to create the project, fields, views and items.")
        return 0

    pdata = load_project(gh, proj["id"])
    fields = field_map(pdata)
    for fname, kind in (("Work unit", "ITERATION"), ("Track", "SINGLE_SELECT"),
                        ("Complete by", "DATE"), ("Checkpoint", "DATE")):
        if fname in fields and fields[fname].get("dataType") != kind:
            L.die(f"field {fname} has type {fields[fname].get('dataType')}, but needs {kind}. "
                  "Rename the existing field in the project, then rerun", 1)

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
            retry_graphql(gh, """mutation($f: ID!, $c: ProjectV2IterationFieldConfigurationInput!) {
              updateProjectV2Field(input: {fieldId: $f, iterationConfiguration: $c}) { projectV2Field { ... on ProjectV2IterationField { id } } } }""",
                          {"f": fields["Work unit"]["id"], "c": {"startDate": first["startDate"], "duration": first["duration"], "iterations": iterations}},
                          f"project {proj['id']}, field Work unit {fields['Work unit']['id']}, intended iterations {iterations!r}")
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
        ensure_track_options(gh, proj["id"], fields, plan["tracks"], a.apply)
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
                retry_graphql(gh, "mutation($v: ID!, $n: String!) { updateProjectV2View(input: {viewId: $v, name: $n}) { projectV2View { id } } }", {"v": default["id"], "n": vname},
                              f"project {proj['id']}, view {default['id']}, intended name {vname!r}")
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
                retry_graphql(gh, "mutation($v: ID!, $f: [ID!]) { updateProjectV2View(input: {viewId: $v, configuration: {visibleFieldIds: $f}}) { projectV2View { id } } }", {"v": v["id"], "f": visible},
                              f"project {proj['id']}, view {vname!r}, intended visible fields {visible!r}")
            except G.GitHubError as e:
                L.say(f"  could not set visible fields on {vname}: {e.line()}")
        L.say("  visible field configuration checked on Table and Board; verification follows")

    # ---------------- items ----------------
    L.say("\nItems")
    iter_field = fields.get("Work unit")
    iter_ids = {}
    if iter_field and iter_field.get("configuration"):
        for i in iter_field["configuration"]["iterations"] + iter_field["configuration"].get("completedIterations", []):
            iter_ids[i["title"]] = i["id"]
    track_ids = {o["name"].casefold(): o["id"] for o in (fields.get("Track") or {}).get("options", [])}
    existing = load_items(gh, proj["id"], f"{owner_repo}/{name}")
    added = 0
    filled = 0
    failures = []
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
        if kind == "epic":
            continue
        desired = {}
        wu_title = f"Work unit {ms['number']}, {ms['name']}"
        if "Work unit" in fields and wu_title in iter_ids:
            desired["Work unit"] = ("iterationId", iter_ids[wu_title])
        if kind == "item":
            if "Track" in fields:
                tl = L.track_label(plan, it["track"]).casefold()
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
            if not a.apply:
                L.say(f"  would set #{num} {L.tag(plan, it['id']) if it else 'M' + str(ms['number'])} field {fname}: expected {val!r}, actual {existing[num]['values'].get(fname)!r}")
                continue
            try:
                retry_graphql(gh, "mutation($p: ID!, $i: ID!, $f: ID!, $v: ProjectV2FieldValue!) { updateProjectV2ItemFieldValue(input: {projectId: $p, itemId: $i, fieldId: $f, value: $v}) { projectV2Item { id } } }",
                              {"p": proj["id"], "i": existing[num]["id"], "f": fields[fname]["id"], "v": {key: val}},
                              f"issue #{num} {L.tag(plan, it['id']) if it else 'M' + str(ms['number'])}, field {fname}, intended {val!r}")
                filled += 1
            except G.GitHubError as e:
                failures.append(e.line())
                L.say("  failed: " + e.line())
            time.sleep(0.1)
    L.say(f"  items added: {added}; field values set: {filled}")

    # ---------------- report ----------------
    if a.apply or a.verify:
        L.say("\nVerification (read only)")
        pdata = load_project(gh, proj["id"])
        fields = field_map(pdata)
        existing = load_items(gh, proj["id"], f"{owner_repo}/{name}")
        wanted_nums = {p[0]["number"] for p in placements}
        L.say(f"  project items that are plan issues: {len(wanted_nums & set(existing))} of {len(wanted_nums) + len(missing)}")
        n_sub = len(plan["milestones"])
        n_item = len(plan["items"])
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
        if a.verify or a.apply:
            problems = verification_problems(plan, placements, missing, pdata, existing, iterations)
            problems.extend(failures)
            for view in pdata["views"]["nodes"]:
                if view["name"] in ("Table", "Board"):
                    actual = {f.get("id") for f in (view.get("fields") or {}).get("nodes", []) if f}
                    if not set(visible) <= actual:
                        problems.append(f"view {view['name']} visible fields: expected {visible!r}, actual {sorted(actual)!r}; check Projects write permission and rerun")
            for problem in problems:
                L.say("  - " + problem)
            L.say("  verification FAILED" if problems else "  verification passed")
            if problems:
                return 1
    L.say("\nThe API cannot set these. Click them once in the project (see references/project-board.md in the carrydown-plan-to-github skill):")
    for c in CLICK:
        L.say("  - " + c)
    if not a.apply and not a.verify:
        L.say("\nDry run complete. Add --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
