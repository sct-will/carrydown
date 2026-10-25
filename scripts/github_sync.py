#!/usr/bin/env python3
"""Create the GitHub structure for a plan: labels, sub-epics, work item issues, links, Epic comment.

Everything is derived from plan.yaml and the specification folder.

  labels         one for the project, one per track, and "sub-epic"
  sub-epics      one issue per milestone. Body comes from milestone.md: purpose, expected outcomes,
                 acceptance criteria, demonstration expectations and the work item list
  work items     one issue per item. Body: Work item, AI engineering notes (specification link and
                 engineers' skill line), Depends on, Acceptance criteria, Evidence of completion,
                 Integration points, Definition of done
  sub-issues     each work item under its sub-epic, each sub-epic under the Epic if there is one
  dependencies   ids in issue bodies rewritten to issue links, for example "WI-01 (#12)"
  Epic comment   one roll-up comment with a Constraints block (target delivery, people by track)
                 and nested checkboxes, created once and updated on reruns

Safety
  This is a dry run unless you pass --apply. The dry run reads from GitHub when a token is
  available (it never writes) and prints what it would create. Run it first and read it.
  Only issues that carry the project label count. Each body ends with a hidden marker such as
  <!-- carrydown:WI-07 -->, and issues are matched by that marker first and by exact title
  second, so a rerun creates nothing twice. If GitHub fails while creating an issue, the
  script reads the issues back before it tries again.
  A rerun after a crash repairs what is missing: sub-issue links, dependency links and the
  sub-epic work item lists. It rewrites a body only while it is exactly as this script wrote
  it. Bodies a person edited are left alone unless you pass --update-bodies.
  --apply to a public repository is refused unless you pass --allow-public.
  Text fetched from GitHub is treated as data: it is compared, never followed, and issue
  titles are printed from the plan, not from GitHub.
  The token is read from a file and is never printed.

Usage
  python3 scripts/github_sync.py --root . --repo owner/name            dry run
  python3 scripts/github_sync.py --root . --repo owner/name --apply    write
  python3 scripts/github_sync.py --root . --verify                     check what exists
  python3 scripts/github_sync.py --root . --offline --show-body 3      print one issue body, no network
  python3 scripts/github_sync.py --root . --offline --show-body M2     print one sub-epic body, no network
"""
import argparse
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import github_client as G  # noqa: E402
import check_specs  # noqa: E402

COLORS = {"GRAY": "6e7781", "BLUE": "1d76db", "GREEN": "0e8a16", "YELLOW": "fbca04", "ORANGE": "d93f0b",
          "RED": "b60205", "PINK": "e99695", "PURPLE": "5319e7"}
MARKER = "<!-- carrydown:rollup -->"
MARKER_RE = re.compile(r"<!-- carrydown:([A-Za-z0-9_-]+) -->")
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


def plan_end_date(plan):
    return max((L.parse_date(it["complete_by"]) for it in plan["items"]), default=None)


def target_phrase(plan):
    """(date text, 'given' or 'derived') for the plan's target delivery."""
    tdate, _ = L.target_date(plan)
    if tdate and L.target_is_constraint(plan):
        return L.fmt_date(tdate), "given"
    end = plan_end_date(plan)
    return (L.fmt_date(end) if end else "not known yet"), "derived"


def constraints_lines(plan):
    """The project constraints as they appear on GitHub: target delivery, then people by track."""
    date, how = target_phrase(plan)
    lines = [f"Target delivery: {date} (" + ("given" if how == "given" else "derived from the critical path") + ")"]
    people = plan["people"]
    if not people:
        lines.append(f"People: to be assigned (derived capacity: {len(plan['tracks'])})")
        return lines
    for t in plan["tracks"]:
        mine = [p for p in people if p.get("track") == t["id"]]
        if not mine:
            continue
        n = len(mine)
        total = sum(p.get("allocation", 100) for p in mine)
        holder = " (placeholder)" if any(p.get("derived") for p in mine) else ""
        lines.append(f"Track {t['label']}: {n} {'person' if n == 1 else 'people'}{holder}, {total} percent allocated")
    return lines


def marker(key):
    """The hidden line at the end of each body that ties an issue to its plan key (WI-07, M1, EPIC)."""
    return f"<!-- carrydown:{key} -->"


def with_marker(body, key):
    return body.rstrip("\n") + "\n\n" + marker(key) + "\n"


def unlinked_ids(plan, text, numbers):
    """Ids of work items that have an issue but appear in text without their link."""
    prefix = re.escape(plan["project"]["id_prefix"])
    out = []
    for line in text.split("\n"):
        if line.startswith("Install it once") or MARKER_RE.search(line):
            continue
        for m in re.finditer(rf"\b({prefix})-(\d+)\b(?! \(#)", line):
            key = L.tag(plan, int(m.group(2)))
            if key in numbers:
                out.append(key)
    return out


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


def build_item_body(plan, root, it, numbers=None, mark=True):
    numbers = numbers or {}
    sp = L.spec_path(plan, root, it)
    spec = L.read_spec(sp)
    rel = sp.relative_to(root).as_posix()
    cp = L.checkpoint_of(plan, it) or {"date": it["checkpoint"], "name": ""}
    proj = plan["project"]
    skill = ""
    if proj.get("dev_skill_path") and proj.get("repo"):
        skill = (
            f"Engineers' skill: {L.github_tree_url(plan, proj['dev_skill_path'])}\n\n"
            f"Install it once following its README, then start this item by asking your coding agent to work on {L.tag(plan, it['id'])}. "
            "The skill makes the agent read the specification above, the ground truth sections it cites and the project conventions "
            "before it changes code. You review every change."
        )
    deps = [f"- {L.tag(plan, d)} {L.item_by_id(plan)[d]['label']}" for d in it["depends"]]
    if it["external_input"]:
        deps.append(f"- External input: {it['external_input']}")
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
    body = link_ids(plan, body.rstrip() + "\n", numbers)
    return with_marker(body, L.tag(plan, it["id"])) if mark else body


def optional_section(spec, name):
    """A heading and the section text, without the HTML comments scaffold_spec.py writes into
    generated sections. Nothing when the milestone file has no such section."""
    text = re.sub(r"<!--.*?-->", "", L.section_text(spec, name), flags=re.S).strip()
    return [f"### {name}", "", text, ""] if text else []


def build_subepic_body(plan, root, ms, numbers=None, mark=True):
    numbers = numbers or {}
    p = L.milestone_path(plan, root, ms)
    spec = L.read_spec(p)
    rel = p.relative_to(root).as_posix()
    lines = [L.section_text(spec, "Purpose"), "", f"**Exit gate.** {ms['gate']}", "",
             f"**Due.** {ms['end']}. **Demonstration.** {ms['demo']}.", "",
             f"Target delivery for the plan: {target_phrase(plan)[0]} ({target_phrase(plan)[1]})", ""]
    lines += optional_section(spec, "Why these items form this milestone")
    lines += ["### Expected outcomes", "", L.section_text(spec, "Expected outcomes"), ""]
    lines += optional_section(spec, "Joint demonstration")
    lines += ["### Acceptance criteria", "", L.section_text(spec, "Acceptance criteria"), "",
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
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip() + "\n"
    return with_marker(body, f"M{ms['number']}") if mark else body


def safe_to_rewrite(have, pristine):
    """True when a body is still exactly as this script wrote it (with or without the marker),
    so a rerun may add the links. A body a person edited is never in this set."""
    norm = have.replace("\r\n", "\n").rstrip()
    return any(norm == p.rstrip() for p in pristine)


def build_rollup(plan, numbers, epic_number):
    proj = plan["project"]
    readme = L.github_blob_url(plan, f"{proj['spec_dir']}/README.md")
    intro = (f"{len(plan['milestones'])} sub-epics, one per milestone, each holding its work item issues as sub-issues. A box is checked when its issue closes. "
             f"Conventions, the checkpoint schedule and the comment templates are in [{proj['spec_dir']}/README.md]({readme}).")
    if plan["external"]["items"]:
        intro += " External items are owned outside the team and tracked outside these issues."
    out = [MARKER, f"## Development plan, {proj['name']}", "", "**Constraints**", ""] + [f"- {l}" for l in constraints_lines(plan)] + ["", intro, ""]
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
            "Checkpoints between the tracks, each on its date in the plan, are integration checks, not demonstrations, and their short records are comments here. "
            "Each work item closes with an evidence comment on its own issue (Demo, Evidence, Decisions, Handoff)."]
    return "\n".join(out) + "\n"


class Sync:
    def __init__(self, plan, root, gh, owner, repo, apply):
        self.plan, self.root, self.gh, self.owner, self.repo, self.apply = plan, Path(root), gh, owner, repo, apply
        self.base = f"/repos/{owner}/{repo}"
        self.issues = None  # title -> issue, only issues with the project label
        self.by_key = {}    # marker key -> issue, only issues with the project label
        self.objs = {}      # "EPIC" / "M1" / "WI-01" -> the issue used for that key
        self.numbers = {}   # "M1" / "WI-01" -> issue number
        self.ids = {}       # same keys -> issue id (for sub-issue links)
        self.created = set()
        self.planned = set()
        self.counts = {"labels": 0, "subepics": 0, "items": 0, "links": 0, "bodies": 0}

    def load_issues(self):
        """Read the issues that carry the project label, open first, and index them by title and
        by marker. Issues without the label are never matched, linked or changed."""
        if self.issues is None:
            self.issues, self.by_key = {}, {}
            slug = self.plan["project"]["slug"]
            found = self.gh.paged(f"{self.base}/issues?state=all&labels={urllib.parse.quote(slug)}")
            found = [i for i in found if "pull_request" not in i
                     and slug.lower() in {str(lb.get("name", "")).lower() for lb in (i.get("labels") or []) if isinstance(lb, dict)}]
            found.sort(key=lambda i: i.get("state") != "open")
            for i in found:
                self.issues.setdefault(i["title"], i)
                m = MARKER_RE.search(i.get("body") or "")
                if m:
                    self.by_key.setdefault(m.group(1), i)
        return self.issues

    def find(self, key, title):
        """The labeled issue for a plan key: by its marker first, then by exact title."""
        issues = self.load_issues() if self.gh else {}
        return self.by_key.get(key) or issues.get(title)

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

    def remember(self, key, iss):
        self.objs[key] = iss
        self.numbers[key], self.ids[key] = iss["number"], iss["id"]

    def create_or_find(self, title, body, labels, assignees, key, issue_type=""):
        """Find the issue for key, or create it. Titles printed are the plan's, never GitHub's."""
        iss = self.find(key, title)
        if iss:
            self.remember(key, iss)
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
        for attempt in (1, 2):
            try:
                iss = self.gh.rest("POST", f"{self.base}/issues", payload)
                break
            except G.GitHubError as e:
                if e.kind not in ("server", "network"):
                    raise
                # GitHub may have created the issue and lost the answer: read back before trying again
                L.say(f"    GitHub answered with an error ({e.status or e.kind}). Reading the issues back before trying again.")
                self.issues = None
                iss = self.find(key, title)
                if iss:
                    L.say(f"    found it after the error: #{iss['number']}")
                    break
                if attempt == 2:
                    raise
        self.issues[title] = iss
        self.by_key[key] = iss
        self.remember(key, iss)
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
    try:
        return _run(argv)
    except G.GitHubError as e:
        return G.report(e)


def _run(argv=None):
    ap = argparse.ArgumentParser(
        description="Create labels, sub-epics, work item issues, links and the Epic roll-up comment from plan.yaml. Dry run unless --apply.",
        epilog="The token is read from --token-file, CARRYDOWN_GITHUB_TOKEN or ~/.config/carrydown/github_token. It is never printed.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--repo", help="owner/name. Overrides project.repo in plan.yaml")
    ap.add_argument("--token-file", help="file that holds the GitHub token")
    ap.add_argument("--apply", action="store_true", help="write to GitHub. Without it nothing is written")
    ap.add_argument("--allow-public", action="store_true", help="allow --apply to a public repository. Issue bodies carry text from your ground truth")
    ap.add_argument("--offline", action="store_true", help="do not call GitHub at all, even to read")
    ap.add_argument("--verify", action="store_true", help="read GitHub and check that the structure matches the plan, then exit")
    ap.add_argument("--create-epic", action="store_true", help="create a parent Epic issue when project.epic is empty")
    ap.add_argument("--update-bodies", action="store_true", help="also rewrite the bodies of issues that already exist")
    ap.add_argument("--skip-comment", action="store_true", help="do not post or update the Epic roll-up comment")
    ap.add_argument("--skip-check", action="store_true", help="do not run the specification checker first")
    ap.add_argument("--issue-type", default="", help="GitHub issue type for work items, for example Task (organizations only)")
    ap.add_argument("--show-body", metavar="ID", help="print the issue body for one work item or sub-epic and exit (no network). Accepts WI-07, 7 or M2")
    a = ap.parse_args(argv)
    if a.offline and (a.apply or a.verify):
        L.die(f"--offline cannot be combined with {'--apply' if a.apply else '--verify'}: both need GitHub. "
              "Leave out --offline to write or verify, or leave out the other flag for an offline dry run")
    if a.apply and a.verify:
        L.die("--apply and --verify are separate runs. Run --apply first, then --verify")

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
    if a.show_body:
        sm = re.fullmatch(r"\s*[Mm](\d+)\s*", str(a.show_body))
        if sm:
            ms = {m["number"]: m for m in plan["milestones"]}.get(int(sm.group(1)))
            if not ms:
                L.die(f"no milestone {a.show_body}. Use M followed by the milestone number, for example M{plan['milestones'][0]['number']}")
            L.say(build_subepic_body(plan, root, ms))
            return 0
        m = re.search(r"(\d+)\s*$", str(a.show_body))
        wanted = int(m.group(1)) if m else None
        it = L.item_by_id(plan).get(wanted)
        if not it:
            example = f"for example {L.tag(plan, plan['items'][0]['id'])}" if plan["items"] else "the plan has no items yet"
            L.die(f"no item with id {a.show_body}. Use the tag ({example}) or the number, or M and a milestone number")
        L.say(build_item_body(plan, root, it))
        return 0
    if not a.skip_check:
        rc = check_specs.main(["--root", str(root), "--plan", str(plan_path), "--quiet"])
        if rc != 0:
            L.say("The checker found problems, so nothing was sent to GitHub. Run check_specs.py to see them and fix them, then run this again.")
            return 1
    owner, repo = L.repo_parts(plan, a.repo)
    plan["project"]["repo"] = f"{owner}/{repo}"
    proj = plan["project"]
    gh = None
    unchecked = "--offline"
    if not a.offline:
        token = G.read_token(a.token_file, required=a.apply or a.verify)
        if token:
            gh = G.GitHub(token)
        else:
            unchecked = "no token"
    L.say("")
    L.say(f"carrydown github_sync  {'APPLY' if a.apply else 'VERIFY (read only)' if a.verify else 'DRY RUN (nothing will be written)'}")
    plan_shown = plan_path.relative_to(root) if root in plan_path.parents else plan_path.name
    L.say(f"repository: {owner}/{repo}    plan: {plan_shown}")
    L.say(f"{len(plan['milestones'])} milestones, {len(plan['items'])} work items, {len(plan['tracks'])} tracks, {len(plan['external']['items'])} external items kept outside the plan")
    L.say("Constraints (they go into the Epic comment, and the target into every sub-epic):")
    for line in constraints_lines(plan):
        L.say("  " + line)
    if gh is None:
        L.say(f"not checked against GitHub ({unchecked}): showing the plan only, nothing is read from GitHub")
        if unchecked == "no token":
            L.say(f"To compare with what is on GitHub, set up a token: python3 {G.TOKEN_SCRIPT}")
    s = Sync(plan, root, gh, owner, repo, a.apply)
    if gh:
        status, js = gh.rest_status("GET", s.base)
        if status == 404:
            L.say(f"repository {owner}/{repo} was not found, or the token cannot see it.")
            if a.apply or a.verify:
                return 1
            gh = s.gh = None
            unchecked = "repository not reachable"
        else:
            public = js.get("private") is False
            if public and a.apply and not a.allow_public:
                L.die(f"{owner}/{repo} is public. Issue bodies carry text from your ground truth. Rerun with --allow-public if that is intended.")
            if not a.apply:
                L.say(f"repository found (private: {js.get('private')}). Reading existing labels and issues.")
            if public and not a.allow_public and not a.verify:
                L.say(f"note: {owner}/{repo} is public, and issue bodies carry text from your ground truth. --apply will need --allow-public.")
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
        s.remember("EPIC", e)
        L.say(f"\nEpic: #{epic} (project.epic in plan.yaml)")
    elif a.create_epic and not epic:
        L.say("\nEpic")
        body = with_marker(f"Parent Epic for {proj['name']}. The sub-epics and work items are linked below as sub-issues.\n", "EPIC")
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
        has_epic = bool(epic) or a.create_epic
        L.say("\nSummary")
        L.say(f"{1 if has_epic else 0} Epic, {len(plan['milestones'])} sub-epics, {len(plan['items'])} work item issues")
        if gh:
            L.say(f"  to create now: {n_epic} Epic, {n_sub} sub-epics, {n_it} work item issues. Already on GitHub: the rest.")
        else:
            L.say(f"  not checked against GitHub ({unchecked}), so this counts every issue as new: {n_epic} Epic, {n_sub} sub-epics, {n_it} work item issues.")
        L.say("Would then link each work item under its sub-epic" + (" and each sub-epic under the Epic" if epic or a.create_epic else "") + ",")
        L.say("rewrite dependency ids in the bodies to issue links, update the sub-epic work item lists,")
        L.say("and " + ("post" if not a.skip_comment and (epic or a.create_epic) else "skip") + " the Epic roll-up comment.")
        for it in plan["items"]:
            L.say(f"  {L.tag(plan, it['id'])}  {it['track']:<12} {it['complete_by']}  depends: {', '.join(L.tag(plan, d) for d in it['depends']) or '-'}" + (f"  external input: {it['external_input']}" if it['external_input'] else ""))
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
    for ms in plan["milestones"]:
        key = f"M{ms['number']}"
        cur = s.objs[key]
        want = build_subepic_body(plan, root, ms, s.numbers)
        have = (cur.get("body") or "").replace("\r\n", "\n")
        pristine = [build_subepic_body(plan, root, ms), build_subepic_body(plan, root, ms, mark=False),
                    build_subepic_body(plan, root, ms, s.numbers, mark=False)]
        if want != have and (key in s.created or a.update_bodies or safe_to_rewrite(have, pristine)):
            gh.rest("PATCH", f"{s.base}/issues/{cur['number']}", {"body": want})
            cur["body"] = want
            s.counts["bodies"] += 1
            L.say(f"  updated work item list in #{cur['number']}")
            time.sleep(0.4)
    for it in plan["items"]:
        t = L.tag(plan, it["id"])
        cur = s.objs[t]
        want = build_item_body(plan, root, it, s.numbers)
        have = (cur.get("body") or "").replace("\r\n", "\n")
        is_new = t in s.created
        pristine = [build_item_body(plan, root, it), build_item_body(plan, root, it, mark=False),
                    build_item_body(plan, root, it, s.numbers, mark=False)]
        if want != have and (is_new or a.update_bodies or safe_to_rewrite(have, pristine)):
            gh.rest("PATCH", f"{s.base}/issues/{cur['number']}", {"body": want})
            cur["body"] = want
            s.counts["bodies"] += 1
            L.say(f"  linked dependencies in #{cur['number']} {t}")
            time.sleep(0.4)
    if not a.skip_comment and epic_key:
        L.say("\nEpic roll-up comment")
        num = s.numbers["EPIC"]
        text = build_rollup(plan, s.numbers, num)
        existing = own_rollups(gh, s.base, num)
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
    sub_epic_numbers = [str(s.numbers["M%d" % m["number"]]) for m in plan["milestones"]]
    L.say("  sub-epics: #" + ", #".join(sub_epic_numbers))
    L.say(f"  work items: {len(plan['items'])} ({s.numbers[L.tag(plan, plan['items'][0]['id'])]} to {max(s.numbers[L.tag(plan, i['id'])] for i in plan['items'])})")
    L.say(f"  new sub-issue links: {s.counts['links']}, bodies rewritten: {s.counts['bodies']}")
    L.say(f"Next: python3 {Path(__file__).resolve().parent / 'github_project.py'} to build the board. Then run this script with --verify.")
    return 0


def own_rollups(gh, base, num):
    """Roll-up comments on the Epic written by the token's own account. A comment from anyone
    else is ignored, even when it carries the marker."""
    me = gh.whoami().get("login")
    return [c for c in gh.paged(f"{base}/issues/{num}/comments")
            if MARKER in (c.get("body") or "") and (c.get("user") or {}).get("login") == me]


def verify(s, plan, root):
    gh = s.gh
    L.say("\nVerification (read only)")
    ok = True
    labels = {l["name"].lower() for l in gh.paged(f"{s.base}/labels")}
    want_labels = [n for n, _, _ in s.desired_labels()]
    miss = [n for n in want_labels if n.lower() not in labels]
    L.say(f"  labels: {len(want_labels) - len(miss)} of {len(want_labels)} present" + (f", missing {miss}" if miss else ""))
    ok &= not miss
    sub_ok = 0
    item_ok = 0
    link_total = 0
    for ms in plan["milestones"]:
        t = subepic_title(plan, ms)
        iss = s.find(f"M{ms['number']}", t)
        if not iss:
            L.say(f"  MISSING sub-epic: {t}")
            ok = False
            continue
        sub_ok += 1
        s.remember(f"M{ms['number']}", iss)
    for it in plan["items"]:
        t = item_title(plan, it)
        iss = s.find(L.tag(plan, it["id"]), t)
        if not iss:
            L.say(f"  MISSING work item: {t}")
            ok = False
            continue
        item_ok += 1
        s.remember(L.tag(plan, it["id"]), iss)
    L.say(f"  sub-epics: {sub_ok} of {len(plan['milestones'])}")
    L.say(f"  work item issues: {item_ok} of {len(plan['items'])}")
    lists_bad = 0
    for ms in plan["milestones"]:
        key = f"M{ms['number']}"
        if key not in s.numbers:
            continue
        mine = [L.tag(plan, it["id"]) for it in plan["items"] if it["milestone"] == ms["number"] and L.tag(plan, it["id"]) in s.numbers]
        subs = {x["number"] for x in gh.paged(f"{s.base}/issues/{s.numbers[key]}/sub_issues")}
        want = {s.numbers[t] for t in mine}
        link_total += len(subs & want)
        if subs != want:
            L.say(f"  sub-issues of #{s.numbers[key]}: expected {sorted(want)}, found {sorted(subs)}")
            ok = False
        body = (s.objs[key].get("body") or "").replace("\r\n", "\n")
        unlisted = [t for t in mine if f"#{s.numbers[t]} {t}" not in body]
        if unlisted:
            lists_bad += 1
            L.say(f"  work item list of #{s.numbers[key]} lacks the issue numbers of {', '.join(unlisted)}")
    L.say(f"  sub-issue links work item to sub-epic: {link_total} of {len(plan['items'])}")
    L.say(f"  sub-epic work item lists with every issue number: {sub_ok - lists_bad} of {sub_ok}")
    ok &= lists_bad == 0
    bad = 0
    unlinked_total = 0
    for it in plan["items"]:
        key = L.tag(plan, it["id"])
        if key not in s.objs:
            continue
        body = (s.objs[key].get("body") or "").replace("\r\n", "\n")
        heads = [l[4:] for l in body.split("\n") if l.startswith("### ")]
        if not all(h in heads for h in SEVEN):
            bad += 1
            L.say(f"  body of #{s.numbers[key]} {key} lacks a required heading")
        unlinked = sorted(set(unlinked_ids(plan, body, s.numbers)))
        if unlinked:
            unlinked_total += 1
            L.say(f"  body of #{s.numbers[key]} {key} has unlinked ids: {', '.join(unlinked)}")
    L.say(f"  bodies with all seven headings: {item_ok - bad} of {item_ok}")
    L.say(f"  bodies with every dependency id linked: {item_ok - unlinked_total} of {item_ok}")
    ok &= bad == 0 and unlinked_total == 0
    epic = plan["project"].get("epic") or (s.find("EPIC", plan["project"]["epic_title"]) or {}).get("number")
    if epic:
        subs = {x["number"] for x in gh.paged(f"{s.base}/issues/{epic}/sub_issues")}
        want = {s.numbers[f"M{m['number']}"] for m in plan["milestones"] if f"M{m['number']}" in s.numbers}
        L.say(f"  sub-epics under Epic #{epic}: {len(subs & want)} of {len(want)}")
        com = own_rollups(gh, s.base, epic)
        L.say(f"  Epic roll-up comment: {'present' if com else 'missing'}")
        ok &= bool(com) and subs >= want
    L.say("verification " + ("passed" if ok else "FAILED"))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(run())
