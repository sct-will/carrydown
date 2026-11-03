#!/usr/bin/env python3
"""The GitHub destination payloads of a release, as pure functions. Offline. Standard library only.

A release does not publish GitHub items from working files. At preparation each target gets a payload
file in the snapshot (snapshot/payloads/<destination>/<target key>.json): the exact title, body,
labels, assignees and relationships the owner approves. Publication reads those files and applies the
substitutions below, and nothing else.

Permitted substitutions (specification D4). They apply to payloads at publication, never to repository
artifacts:
  {{issue:KEY}}   the number of the issue recorded for KEY, as "#123". Digits only. It is written in
                  two fixed shapes: " ({{issue:KEY}})" after an id, and "{{issue:KEY}} " before one.
                  A placeholder whose issue does not exist yet is left out, with its parentheses or
                  trailing space, so the first body of an issue is complete without the link.
  {{spec_url}}    the blob URL of the payload's spec_path, from the approved host and repository
  {{skill_url}}   the tree URL of the payload's skill_path
Any other difference between a payload and the text sent is deny(unapproved-substitution).

The body builders here are the ones github_sync.py used to hold. github_sync.py and github_project.py
import them again, so a dry run, a show-body and a publication print the same text.

This module is imported by the other scripts. Run with --help to see this text.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import release_schema as RS  # noqa: E402

COLORS = {"GRAY": "6e7781", "BLUE": "1d76db", "GREEN": "0e8a16", "YELLOW": "fbca04", "ORANGE": "d93f0b",
          "RED": "b60205", "PINK": "e99695", "PURPLE": "5319e7"}
MARKER = "<!-- carrydown:rollup -->"
MARKER_RE = re.compile(r"<!-- carrydown:([A-Za-z0-9_-]+) -->")
SEVEN = ["Work item", "AI engineering notes", "Depends on", "Acceptance criteria", "Evidence of completion", "Integration points", "Definition of done"]
PAYLOAD_KINDS = ("issue", "subepic", "epic", "epic-comment", "label", "board")
ENGINEERING = "engineering"
BOARD = "board"

_INLINE = re.compile(r" \(\{\{issue:([A-Za-z0-9_-]+)\}\}\)")
_PREFIX = re.compile(r"\{\{issue:([A-Za-z0-9_-]+)\}\} ")
_ANY_ISSUE = re.compile(r"\{\{issue:[^}]*\}\}")


# ---------------------------------------------------------------------------
# Titles, small texts
# ---------------------------------------------------------------------------

def subepic_title(plan, ms):
    return f"{plan['project']['subepic_prefix']} {ms['number']}, {ms['name']}"


def item_title(plan, it):
    """The issue title of a work item. validate_plan has checked project.title_format, and every
    script stops on a plan problem before it calls this."""
    return L.format_title(plan["project"]["title_format"], L.tag(plan, it["id"]), it["label"])


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


def constraints_lines(plan, staffed=None, flags=None):
    """The project constraints as they appear on GitHub: target delivery, then people by track.

    The people by track are the capacity summary. They appear only when the downstream capacity_summary
    flag allows: flags when given (a release request carries them), else the plan's own
    (L.downstream_flags: true for a legacy plan, false for a migrated one unless the owner set it).
    Percent allocated comes from staffed, the plan with people.yaml merged in; a migrated plan on its
    own holds no allocation, so the percent is left out."""
    date, how = target_phrase(plan)
    lines = [f"Target delivery: {date} (" + ("given" if how == "given" else "derived from the critical path") + ")"]
    if not (flags if flags is not None else L.downstream_flags(plan))["capacity_summary"]:
        return lines
    people = plan["people"]
    if not people:
        lines.append(f"People: to be assigned (derived capacity: {len(plan['tracks'])})")
        return lines
    known = staffed if staffed is not None else plan
    percent = L.staffing_loaded(known)
    allocation = {p.get("id"): p.get("allocation", 100) for p in known["people"]}
    for t in plan["tracks"]:
        mine = [p for p in people if p.get("track") == t["id"]]
        if not mine:
            continue
        n = len(mine)
        total = sum(allocation.get(p.get("id"), 100) for p in mine)
        holder = " (placeholder)" if any(p.get("derived") for p in mine) else ""
        lines.append(f"Track {t['label']}: {n} {'person' if n == 1 else 'people'}{holder}" + (f", {total} percent allocated" if percent else ""))
    return lines


def marker(key):
    """The hidden line at the end of each body that ties an issue to its plan key (WI-07, M1, EPIC)."""
    return f"<!-- carrydown:{key} -->"


def with_marker(body, key):
    return "<!-- carrydown-managed:start -->\n" + body.rstrip("\n") + "\n<!-- carrydown-managed:end -->\n\n" + marker(key) + "\n"


def first_paragraph(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return paras[0] if paras else ""


def login_for(plan, staffed, it, flags=None):
    """The login that may be published for an item, or "". With no flags the plan's own rule applies
    (L.payload_assignees). With flags, assignees must be true and a migrated plan needs its staffing
    overlay (staffed); a login is never read from anywhere else."""
    basis = staffed if staffed is not None else plan
    if flags is None:
        found = L.payload_assignees(basis, it)
        return found[0] if found else ""
    if not flags.get("assignees"):
        return ""
    if basis.get("_modern") and not basis.get("_people_overlay"):
        return ""
    return L.assignee_login(basis, it)


# ---------------------------------------------------------------------------
# Substitution
# ---------------------------------------------------------------------------

def placeholderize(plan, text, keys):
    """Write an {{issue:KEY}} placeholder after every work item id in text whose key is in keys. The
    line that tells an agent to start an item is left alone, as link_ids always did. Apply it once."""
    prefix = re.escape(plan["project"]["id_prefix"])

    def sub(m):
        key = L.tag(plan, int(m.group(2)))
        return f"{m.group(0)} ({{{{issue:{key}}}}})" if key in keys else m.group(0)

    out = []
    for line in text.split("\n"):
        out.append(line if line.startswith("Install it once") else re.sub(rf"\b({prefix})-(\d+)\b(?! \(#)", sub, line))
    return "\n".join(out)


def substitute(text, numbers=None, spec_url=None, skill_url=None):
    """Apply the permitted substitutions to text. numbers maps a key to its issue number, a whole
    number. A placeholder whose key has no number is left out. Raises SchemaError
    (unapproved-substitution) for a number that is not a whole number."""
    numbers = numbers or {}
    for key, n in numbers.items():
        if not (isinstance(n, int) and not isinstance(n, bool) and n > 0):
            raise RS.SchemaError("unapproved-substitution", "issue", "an issue number must be a whole number")

    def inline(m):
        n = numbers.get(m.group(1))
        return f" (#{n})" if n else ""

    def prefix(m):
        n = numbers.get(m.group(1))
        return f"#{n} " if n else ""

    text = _INLINE.sub(inline, text)
    text = _PREFIX.sub(prefix, text)
    if spec_url is not None:
        text = text.replace("{{spec_url}}", spec_url)
    if skill_url is not None:
        text = text.replace("{{skill_url}}", skill_url)
    return text


def leftover_placeholders(text):
    """Issue placeholders still in text after substitution, in a shape the table does not permit."""
    return _ANY_ISSUE.findall(text)


def blob_url(host, repository, branch, path):
    owner, name = repository.split("/", 1)
    return f"https://{host}/{owner}/{name}/blob/{branch}/{path}"


def tree_url(host, repository, branch, path):
    owner, name = repository.split("/", 1)
    return f"https://{host}/{owner}/{name}/tree/{branch}/{path}"


def urls_for(payload, host, repository, branch):
    """(spec_url, skill_url) for a payload from its approved substitution paths, or None for each path
    the payload does not name."""
    subs = payload.get("substitutions") or {}
    spec = blob_url(host, repository, branch, subs["spec_path"]) if subs.get("spec_path") else None
    skill = tree_url(host, repository, branch, subs["skill_path"]) if subs.get("skill_path") else None
    return spec, skill


# ---------------------------------------------------------------------------
# Work item, sub-epic and roll-up bodies
# ---------------------------------------------------------------------------

def item_keys(plan):
    return {L.tag(plan, it["id"]) for it in plan["items"]}


def _item_values(plan, root, it, urls):
    """The template values of an issue body. urls is True to resolve the spec and skill links now, False
    to leave {{spec_url}} and {{skill_url}} for publication."""
    sp = L.spec_path(plan, root, it)
    spec = L.read_spec(sp)
    rel = sp.relative_to(root).as_posix()
    cp = L.checkpoint_of(plan, it) or {"date": it["checkpoint"], "name": ""}
    proj = plan["project"]
    skill = ""
    if proj.get("dev_skill_path") and proj.get("repo"):
        skill_url = L.github_tree_url(plan, proj["dev_skill_path"]) if urls else "{{skill_url}}"
        skill = (
            f"Engineers' skill: {skill_url}\n\n"
            f"Install it once following its README, then start this item by asking your coding agent to work on {L.tag(plan, it['id'])}. "
            "The skill makes the agent read the specification above, the ground truth sections it cites and the project conventions "
            "before it changes code. You review every change."
        )
    deps = [f"- {L.tag(plan, d)} {L.item_by_id(plan)[d]['label']}" for d in it["depends"]]
    if it["external_input"]:
        deps.append(f"- External input: {it['external_input']}")
    return {
        "complete_by": it["complete_by"],
        "checkpoint": f"{cp['date']}, {cp['name']}",
        "description": first_paragraph(L.section_text(spec, "Why this work item exists")) or first_paragraph(L.section_text(spec, "Outcome")),
        "spec_url": L.github_blob_url(plan, rel) if urls else "{{spec_url}}",
        "skill_line": skill,
        "ground_truth": L.ground_truth_citation(plan, it) or spec["rows"].get("Ground truth", ""),
        "depends": "\n".join(deps) if deps else "None.",
        "acceptance": L.section_text(spec, "Acceptance criteria"),
        "evidence": L.section_text(spec, "Evidence of completion"),
        "integration": L.section_text(spec, "Integration points"),
        "definition_of_done": definition_of_done(plan),
    }, skill, rel


def item_body_raw(plan, root, it):
    """The managed body of a work item with placeholders: {{spec_url}}, {{skill_url}} and an
    {{issue:KEY}} after every work item id. No wrapper and no marker."""
    values, skill, rel = _item_values(plan, root, it, urls=False)
    body = L.fill(L.read_template("issue-body.md"), values)
    body = re.sub(r"\n{3,}", "\n\n", body)
    if not skill:
        body = body.replace("Specification: " + values["spec_url"] + "\n\n\n", "Specification: " + values["spec_url"] + "\n\n")
    return placeholderize(plan, body.rstrip() + "\n", item_keys(plan))


def build_item_body(plan, root, it, numbers=None, mark=True):
    """The issue body of a work item: item_body_raw with the links to the issues in numbers, and the
    spec and skill links of the plan's own repository. mark wraps it in the managed region."""
    numbers = numbers or {}
    values, skill, rel = _item_values(plan, root, it, urls=True)
    raw = item_body_raw(plan, root, it)
    spec_url = values["spec_url"]
    skill_url = L.github_tree_url(plan, plan["project"]["dev_skill_path"]) if skill else None
    body = substitute(raw, numbers, spec_url, skill_url)
    return with_marker(body, L.tag(plan, it["id"])) if mark else body


def link_ids(plan, text, numbers):
    """Text with " (#n)" after each work item id that has an issue in numbers."""
    return substitute(placeholderize(plan, text, set(numbers)), numbers)


def optional_section(spec, name):
    """A heading and the section text, without the HTML comments scaffold_spec.py writes into
    generated sections. Nothing when the milestone file has no such section."""
    text = re.sub(r"<!--.*?-->", "", L.section_text(spec, name), flags=re.S).strip()
    return [f"### {name}", "", text, ""] if text else []


def subepic_body_raw(plan, root, ms, staffed=None, flags=None):
    """The managed body of a sub-epic with {{spec_url}} and {{issue:KEY}} placeholders."""
    p = L.milestone_path(plan, root, ms)
    spec = L.read_spec(p)
    lines = [L.section_text(spec, "Purpose"), "", f"**Exit gate.** {ms['gate']}", "",
             f"**Due.** {ms['end']}. **Demonstration.** {ms['demo']}.", "",
             f"Target delivery for the plan: {target_phrase(plan)[0]} ({target_phrase(plan)[1]})", ""]
    lines += optional_section(spec, "Why these items form this milestone")
    lines += ["### Expected outcomes", "", L.section_text(spec, "Expected outcomes"), ""]
    lines += optional_section(spec, "Joint demonstration")
    lines += ["### Acceptance criteria", "", L.section_text(spec, "Acceptance criteria"), "",
              "### Demonstration expectations", "", L.section_text(spec, "Demonstration expectations"), "",
              "### Work items", ""]
    for it in plan["items"]:
        if it["milestone"] != ms["number"]:
            continue
        t = L.tag(plan, it["id"])
        who = login_for(plan, staffed, it, flags)
        lines.append(f"- [ ] {{{{issue:{t}}}}} {t} {it['label']}" + (f", @{who}" if who else "") + f", by {it['complete_by']}")
    lines += ["", "Milestone file: {{spec_url}}"]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip() + "\n"


def build_subepic_body(plan, root, ms, numbers=None, mark=True, staffed=None, flags=None):
    p = L.milestone_path(plan, root, ms)
    rel = p.relative_to(root).as_posix()
    body = substitute(subepic_body_raw(plan, root, ms, staffed, flags), numbers or {}, L.github_blob_url(plan, rel))
    return with_marker(body, f"M{ms['number']}") if mark else body


def rollup_raw(plan, staffed=None, flags=None):
    """The roll-up comment of the Epic with {{spec_url}} and {{issue:KEY}} placeholders."""
    proj = plan["project"]
    intro = (f"{len(plan['milestones'])} sub-epics, one per milestone, each holding its work item issues as sub-issues. A box is checked when its issue closes. "
             f"Conventions, the checkpoint schedule and the comment templates are in [{proj['spec_dir']}/README.md]({{{{spec_url}}}}).")
    if plan["external"]["items"]:
        intro += " External items are owned outside the team and tracked outside these issues."
    out = [MARKER, f"## Development plan, {proj['name']}", "", "**Constraints**", ""] + [f"- {l}" for l in constraints_lines(plan, staffed, flags)] + ["", intro, ""]
    for ms in plan["milestones"]:
        sk = f"M{ms['number']}"
        out.append(f"- [ ] {{{{issue:{sk}}}}} {subepic_title(plan, ms)}, due {ms['end']}")
        for it in plan["items"]:
            if it["milestone"] == ms["number"]:
                t = L.tag(plan, it["id"])
                who = login_for(plan, staffed, it, flags)
                out.append(f"  - [ ] {{{{issue:{t}}}}} {t} {it['label']}" + (f", @{who}" if who else "") + f", by {it['complete_by']}")
    out += ["", "### How progress is shown", "",
            "Each milestone is a sub-epic with its acceptance criteria and demonstration expectations in its body. "
            "The demonstration is given by the people who own the items, in a meeting, and its outcome is noted on the sub-epic. "
            "Checkpoints between the tracks, each on its date in the plan, are integration checks, not demonstrations, and their short records are comments here. "
            "Each work item closes with an evidence comment on its own issue (Demo, Evidence, Decisions, Handoff)."]
    return "\n".join(out) + "\n"


def build_rollup(plan, numbers, epic_number, staffed=None, flags=None):
    proj = plan["project"]
    readme = L.github_blob_url(plan, f"{proj['spec_dir']}/README.md")
    return substitute(rollup_raw(plan, staffed, flags), numbers or {}, readme)


def epic_body_raw(plan):
    return f"Parent Epic for {plan['project']['name']}. The sub-epics and work items are linked below as sub-issues.\n"


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

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


def desired_labels(plan):
    proj = plan["project"]
    out = [(proj["slug"], "6e7781", f"Work item of {proj['name']}"), ("sub-epic", "5319e7", "Milestone sub-epic")]
    for t in plan["tracks"]:
        out.append((t["id"], COLORS.get(str(t.get("color", "GRAY")).upper(), "6e7781"), f"{t['label']} track"))
    return out


# ---------------------------------------------------------------------------
# Payload files
# ---------------------------------------------------------------------------

def payload_path(kind, key):
    return f"payloads/{kind}/{key}.json"


def item_payload(plan, root, it, staffed=None, flags=None):
    key = L.tag(plan, it["id"])
    slug = plan["project"]["slug"]
    login = login_for(plan, staffed, it, flags)
    rel = L.spec_path(plan, root, it).relative_to(root).as_posix()
    payload = {
        "destination_id": ENGINEERING,
        "target": {"kind": "issue", "key": key, "marker": marker(key)},
        "title": item_title(plan, it), "body": item_body_raw(plan, root, it),
        "labels": [slug, it["track"]], "assignees": [login] if login else [],
        "relationships": {"parent": f"M{it['milestone']}", "depends_on": [L.tag(plan, d) for d in it["depends"]]},
        "substitutions": {"spec_path": rel, "skill_path": plan["project"].get("dev_skill_path") or None},
    }
    if it.get("state"):
        payload["state"] = it["state"]
    return payload


def subepic_payload(plan, root, ms, staffed=None, flags=None, epic=False):
    key = f"M{ms['number']}"
    p = L.milestone_path(plan, root, ms)
    return {
        "destination_id": ENGINEERING,
        "target": {"kind": "subepic", "key": key, "marker": marker(key)},
        "title": subepic_title(plan, ms), "body": subepic_body_raw(plan, root, ms, staffed, flags),
        "labels": [plan["project"]["slug"], "sub-epic"], "assignees": [],
        "relationships": {"parent": "EPIC" if epic else None,
                          "children": [L.tag(plan, it["id"]) for it in plan["items"] if it["milestone"] == ms["number"]]},
        "substitutions": {"spec_path": p.relative_to(root).as_posix(), "skill_path": None},
    }


def epic_payload(plan):
    return {
        "destination_id": ENGINEERING,
        "target": {"kind": "epic", "key": "EPIC", "marker": marker("EPIC")},
        "title": plan["project"]["epic_title"], "body": epic_body_raw(plan),
        "labels": [plan["project"]["slug"]], "assignees": [],
        "relationships": {"parent": None, "children": [f"M{m['number']}" for m in plan["milestones"]]},
        "substitutions": {"spec_path": None, "skill_path": None},
    }


def rollup_payload(plan, staffed=None, flags=None):
    return {
        "destination_id": ENGINEERING,
        "target": {"kind": "epic-comment", "key": "rollup", "marker": MARKER, "epic": "EPIC"},
        "body": rollup_raw(plan, staffed, flags),
        "substitutions": {"spec_path": f"{plan['project']['spec_dir']}/README.md", "skill_path": None},
    }


def label_payload(name, color, description):
    return {"destination_id": ENGINEERING, "target": {"kind": "label", "key": name}, "name": name, "color": color,
            "description": description}


def board_payload(plan):
    """The project board: its fields, its views and the value of each field for each key."""
    iterations = desired_iterations(plan)
    titles = {m["number"]: f"Work unit {m['number']}, {m['name']}" for m in plan["milestones"]}
    items = {}
    for ms in plan["milestones"]:
        items[f"M{ms['number']}"] = {"Work unit": titles[ms["number"]], "Complete by": ms["end"], "Checkpoint": ms["demo"]}
    for it in plan["items"]:
        items[L.tag(plan, it["id"])] = {"Work unit": titles[it["milestone"]], "Track": L.track_label(plan, it["track"]),
                                        "Complete by": it["complete_by"], "Checkpoint": it["checkpoint"]}
    return {
        "destination_id": BOARD,
        "target": {"kind": "board", "key": "project", "title": plan["project"]["project_title"]},
        "fields": {"Work unit": {"type": "ITERATION", "iterations": iterations},
                   "Track": {"type": "SINGLE_SELECT",
                             "options": [{"name": t["label"], "color": str(t.get("color", "GRAY")).upper(), "description": f"{t['label']} track"} for t in plan["tracks"]]},
                   "Complete by": {"type": "DATE"}, "Checkpoint": {"type": "DATE"}},
        "views": [{"name": "Table", "layout": "TABLE_LAYOUT"}, {"name": "Board", "layout": "BOARD_LAYOUT"}, {"name": "Roadmap", "layout": "ROADMAP_LAYOUT"}],
        "items": items,
    }


def build_payloads(plan, root, *, staffed=None, flags=None, with_board=True, with_epic=None):
    """{snapshot path: canonical JSON bytes} for every GitHub target of the plan: one payload per issue,
    sub-epic, label, the Epic (when the plan names none), the roll-up comment and the board. root is the
    folder that holds the specification (the project, or the workspace drafts folder)."""
    root = Path(root).resolve()
    epic = (not plan["project"].get("epic")) if with_epic is None else with_epic
    out = {}

    def put(kind, key, payload):
        out[payload_path(kind, key)] = RS.canonical_json(payload)

    for name, color, desc in desired_labels(plan):
        put("label", name, label_payload(name, color, desc))
    if epic:
        put("epic", "EPIC", epic_payload(plan))
    for ms in plan["milestones"]:
        put("subepic", f"M{ms['number']}", subepic_payload(plan, root, ms, staffed, flags, epic=bool(epic or plan["project"].get("epic"))))
    for it in plan["items"]:
        put("issue", L.tag(plan, it["id"]), item_payload(plan, root, it, staffed, flags))
    put("epic-comment", "rollup", rollup_payload(plan, staffed, flags))
    if with_board:
        put("board", "project", board_payload(plan))
    return out


def load_payload(data):
    """A payload from its snapshot bytes, strictly parsed."""
    value = RS.loads_strict(data)
    if not isinstance(value, dict) or "destination_id" not in value or "target" not in value:
        raise RS.SchemaError("schema-invalid", "payload", "is not a payload")
    return value


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="The GitHub destination payloads of a release and the permitted substitutions "
                    "({{issue:KEY}}, {{spec_url}}, {{skill_url}}). A library: import it, do not run it.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
