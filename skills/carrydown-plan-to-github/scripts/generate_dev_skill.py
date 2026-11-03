#!/usr/bin/env python3
"""Generate the per-project engineers' skill from the specification folder.

Output, under project.dev_skill_path in plan.yaml
  SKILL.md                         when to use it, how to orient on an item, conventions, definition of done
  README.md                        what it is and how to install it for each agent
  references/work-items.md         the index of work items with dates, dependencies and file paths
  references/contracts.md          the headings of every Contract or Protocol section, by item, and each item's approved context
  references/ground-truth-map.md   the source sections inside the approved contexts, by source id and section number
  scripts/check_context.py         the engineer's check: local validity, freshness, expiry (offline except one fetch)

The files are generated from plan.yaml, the specs and the approved contexts in docs/context/ (see
compile_bundles.py). The skill holds no original filename, no rendering path and no source text:
the map lists only the sections that appear in at least one bundle. Read the files after generating:
add the topics and contracts only a person knows to be important.

Dry run unless --apply. Existing files are replaced only with --force.

Usage
  python3 scripts/generate_dev_skill.py --root .                              dry run
  python3 scripts/generate_dev_skill.py --root . --apply                      write
  python3 scripts/generate_dev_skill.py --root . --only references --apply    refresh only the references
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import release_gate as RG  # noqa: E402

md_table = L.md_table
CONTEXT_DIR = "docs/context"


def work_items_md(plan, root):
    out = ["# Work item index", "",
           "Generated from `plan.yaml`. The GitHub issues hold the owners, status and dates of record.", "",
           "## Work units and milestones", "",
           L.schedule_table(plan), ""]
    tdate, ttext = L.target_date(plan)
    by_track = {}
    for person in plan["people"]:
        by_track[person["track"]] = by_track.get(person["track"], 0) + person.get("allocation", 100)
    alloc = ", ".join(f"{L.track_label(plan, t)} {pct} percent" for t, pct in by_track.items())
    # A migrated plan holds no allocation (it is in the private people file), and a capacity summary
    # is published only when the owner allowed it. Without both, the paragraph says nothing about numbers.
    show_alloc = L.staffing_loaded(plan) and L.downstream_flags(plan)["capacity_summary"]
    last = max((L.parse_date(it["complete_by"]) for it in plan["items"]), default=None)
    if tdate and L.target_is_constraint(plan):
        out += [f"Target. {ttext}. The plan was fitted to it.", ""]
    else:
        out += [f"Target. Derived from the critical path: {L.fmt_date(last) if last else 'not known yet'}. It is the plan's end date, not a constraint.", ""]
    if plan["people"] and not show_alloc:
        out += ["Allocation. The plan owner keeps each person's allocation, start date and days off in a private record. The dates in this plan already account for them.", ""]
    elif plan["people"]:
        derived_note = " Some people are placeholders marked derived in plan.yaml." if any(p.get("derived") for p in plan["people"]) else ""
        out += [f"Allocation. People are allocated as a percentage of their working time to this plan. By track, the allocation adds up to {alloc}. The dates in this plan already account for it, so a track at less than 100 percent has fewer working days in each work unit.{derived_note}", ""]
    else:
        out += ["Allocation. The plan names no people yet, so the dates are not fitted to anyone's capacity.", ""]
    spec_dir = plan["project"]["spec_dir"]
    for m in plan["milestones"]:
        out += [f"## Milestone {m['number']}, {m['name']} (`{m['folder']}`)", "",
                f"Exit gate. {m['gate']}", ""]
        rows = []
        for it in plan["items"]:
            if it["milestone"] != m["number"]:
                continue
            deps = ", ".join(L.tag(plan, d) for d in it["depends"]) or "None"
            if it["external_input"]:
                deps += f"; external input: {it['external_input']}"
            rows.append([L.tag(plan, it["id"]), it["label"], L.track_label(plan, it["track"]), it["complete_by"], deps,
                         f"`{spec_dir}/{m['folder']}/{L.tag(plan, it['id']).lower()}-{it['slug']}.md`"])
        out += [md_table(["Id", "Work item", "Track", "Complete by", "Depends on", "File"], rows), ""]
    if plan["external"]["items"]:
        out += ["## External items and external inputs", "",
                "These are owned outside the team, not by the engineers. They have no work item file. An item that needs one says \"external input\" in its Depends on row. If the input is missing, say so in the pull request and do not invent it.", "",
                md_table(["Id", "External item", "Note"], [[L.tag(plan, p["id"]), p["label"], p.get("note", "")] for p in plan["external"]["items"]]), ""]
    return "\n".join(out).rstrip() + "\n"


def contracts_md(plan, root):
    spec_dir = plan["project"]["spec_dir"]
    out = ["# Contracts quick reference", "",
           "Where each contract is defined. The owning work item file holds the contract text. The approved context of the item, docs/context/<id>.md, holds the source text the contract comes from. "
           "When a contract changes, the work item file changes first and this page follows.", "",
           "## Where each contract is defined", ""]
    rows = []
    blocks = []
    for it in plan["items"]:
        sp = L.spec_path(plan, root, it)
        if not sp.exists():
            continue
        spec = L.read_spec(sp)
        name = "Contract" if "Contract" in spec["sections"] else "Protocol" if "Protocol" in spec["sections"] else None
        if not name:
            continue
        body = spec["sections"][name]
        subs = [m.group(1).strip() for m in re.finditer(r"(?m)^### (.+)$", body)]
        tables = len(re.findall(r"(?m)^\| --- ", body))
        fences = len(re.findall(r"(?m)^```", body)) // 2
        ms = L.milestone_by_num(plan)[it["milestone"]]
        rel = f"{spec_dir}/{ms['folder']}/{sp.name}"
        rows.append([L.tag(plan, it["id"]), it["label"], name, f"`{rel}`", f"`{CONTEXT_DIR}/{L.tag(plan, it['id']).lower()}.md`"])
        blocks.append((it, name, subs, tables, fences, rel))
    out += [md_table(["Id", "Work item", "Section", "File", "Approved context"], rows), ""]
    for it, name, subs, tables, fences, rel in blocks:
        out += [f"## {L.tag(plan, it['id'])} {it['label']}", "", f"Section `## {name}` in `{rel}`. {tables} table(s), {fences} code block(s)."]
        if subs:
            out += ["", "Parts:"] + [f"- {s}" for s in subs]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def read_sidecars(root, bundles=None):
    """The bundle sidecars of the project as {work item tag: sidecar}. bundles maps a path such as
    docs/context/wi-06.bundle.json to its bytes (what compile_bundles returns); without it the files
    under root/docs/context are read. A file that is not a sidecar is skipped."""
    raw = {}
    if bundles is not None:
        raw = {p: b for p, b in bundles.items() if p.endswith(".bundle.json")}
    else:
        folder = Path(root) / CONTEXT_DIR
        if L.exists(folder) and folder.is_dir():
            for f in sorted(folder.glob("*.bundle.json")):
                if f.is_file() and not f.is_symlink():
                    raw[f"{CONTEXT_DIR}/{f.name}"] = f.read_bytes()
    out = {}
    for path, data in raw.items():
        try:
            side = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(side, dict) and isinstance(side.get("work_item"), str) and isinstance(side.get("obligations"), list):
            out[side["work_item"]] = side
    return out


def section_key(number):
    return tuple(int(part) if part.isdecimal() else 0 for part in str(number).split("."))


def tag_key(tag):
    tail = tag.rsplit("-", 1)[-1]
    return int(tail) if tail.isdecimal() else 0


def ground_truth_map_md(plan, root, bundles=None):
    """The map of source sections that the approved contexts hold, built from the bundle sidecars alone.
    It names no original file, no rendering path, no version and no coverage limit, and it lists only
    sections that appear in at least one bundle."""
    sidecars = read_sidecars(root, bundles)
    sections = {}        # source id -> {section: [heading, [item tags]]}
    for tag, side in sidecars.items():
        for ob in side["obligations"]:
            if not (isinstance(ob, dict) and isinstance(ob.get("source"), str) and isinstance(ob.get("section"), str)):
                continue
            row = sections.setdefault(ob["source"], {}).setdefault(ob["section"], [str(ob.get("heading") or ""), []])
            row[1].append(tag)
    out = ["# Ground truth map", "",
           "The source sections inside the approved contexts of this project, by source id and section number. "
           "Read a section through the approved context of a work item, `docs/context/<id>.md`, after "
           "`scripts/check_context.py <ID>` passes. The sources themselves are not in this repository, and this skill "
           "does not look for them. When sources conflict, the earlier source in this file wins unless the plan owner "
           "recorded another decision.", ""]
    if not sections:
        out += ["No approved context has been released yet. Ask the plan owner to release the project.", ""]
        return "\n".join(out).rstrip() + "\n"
    names = L.source_by_id(plan)
    present = [s for s in L.ground_truth_sources(plan) if s["id"] in sections]
    present += [{"id": sid, "name": sid} for sid in sections if sid not in names]
    out += ["## Sources and precedence", "",
            md_table(["Precedence", "Source id", "Document"], [[str(n), s["id"], s.get("name") or s["id"]] for n, s in enumerate(present, 1)]), ""]
    for source in present:
        rows = [[num, row[0], ", ".join(sorted(set(row[1]), key=tag_key))]
                for num, row in sorted(sections[source["id"]].items(), key=lambda kv: section_key(kv[0]))]
        out += [f"## {source.get('name') or source['id']} (`{source['id']}`)", "",
                md_table(["Section", "Heading", "In the approved context of"], rows), ""]
    by_item = []
    for it in plan["items"]:
        tag = L.tag(plan, it["id"])
        side = sidecars.get(tag)
        if side is None:
            by_item.append([tag, it["label"], "Not released", ""])
            continue
        per_source = {}
        for ob in side["obligations"]:
            per_source.setdefault(ob["source"], []).append(ob["section"])
        cited = "; ".join(f"{sid} {', '.join(sorted(nums, key=section_key))}" for sid, nums in per_source.items()) or "No source sections"
        by_item.append([tag, it["label"], f"`{CONTEXT_DIR}/{tag.lower()}.md`", cited])
    out += ["## By work item", "", md_table(["Id", "Work item", "Approved context", "Sections"], by_item), ""]
    return "\n".join(out).rstrip() + "\n"


DECISIONS_ALLOWED = ('If the implementation departs from the file, append a short entry under "Decisions recorded" at the end of the file, '
                     'with the pull request number, in the same pull request.')
DECISIONS_REQUEST_ONLY = (
    'Do not edit "Decisions recorded" or any other part of an approved work item file: this project takes changes to a rule as requests, '
    'and the independent check on pull requests fails an edit that no release covers. If the implementation departs from the file, '
    'or a rule looks wrong, unclear or missing, draft a comment for the work item issue titled `Rule clarification request`. It names the '
    'section, states the question and says what you did meanwhile. Show it to the user, and post it only after the user gives permission '
    'and has authorized a tool that can post: this skill holds no token and cannot post by itself. Then continue only with what the '
    'approved context permits.')

CHANGES_ALLOWED = """Do not edit a bundle, a receipt or a source. If you think a rule in the approved context is wrong, unclear or missing, say so to the plan owner and carry on only with what the bundle permits.

- Ask your agent to draft a comment on the work item issue titled `Rule clarification request`, with the section number and your question. The agent posts it only after you give permission, and only with a tool you have authorized. The generated skill holds no token and cannot post by itself.
- This project allows engineers to append a dated entry under "Decisions recorded" in the work item file, in your pull request. The next release reassesses it.
- The plan owner updates the sources, prepares and approves a new release, and exports it. A new release supersedes the old one, and your next check picks it up."""

CHANGES_REQUEST_ONLY = """Do not edit a bundle, a receipt, a source or an approved work item file. This project takes changes to a rule as requests. A pull request that edits "Decisions recorded" or any other part of an approved specification fails the independent check on pull requests unless a release covers it. If you think a rule in the approved context is wrong, unclear or missing, say so to the plan owner and carry on only with what the bundle permits.

- Ask your agent to draft a comment on the work item issue titled `Rule clarification request`, with the section number and your question. The agent shows it to you and posts it only after you give permission, and only with a tool you have authorized. The generated skill holds no token and cannot post by itself.
- The plan owner decides, updates the workspace and runs the release steps again: preview, prepare, approve and export. A reviewed activation batch supersedes the previous release, and the new receipt names the request it replaces. The reasons stay with the plan owner and are not in the receipt.
- Your next check picks up the new release."""


def align_edits(rel, text, engineer_edits):
    """text of a kept (hand-edited) SKILL.md or README.md with the generated wording of the other mode
    swapped for the wording of engineer_edits, where the generated wording is still there word for word.
    A sentence the owner rewrote is left alone. Other files and an unknown mode are returned unchanged."""
    if engineer_edits not in L.ENGINEER_EDITS:
        return text
    pairs = {"SKILL.md": (DECISIONS_ALLOWED, DECISIONS_REQUEST_ONLY), "README.md": (CHANGES_ALLOWED, CHANGES_REQUEST_ONLY)}.get(rel)
    if pairs is None:
        return text
    allowed, request_only = pairs
    old, new = (allowed, request_only) if engineer_edits == "request-only" else (request_only, allowed)
    return text.replace(old, new)


def engineer_edits_of(plan, override=None):
    """allowed or request-only for the specification files. override (the enrollment's value, which the
    release command passes) wins over project.handling.engineer_edits. With neither, engineers may append
    to "Decisions recorded", which is how a project works before it is released."""
    handling = (plan.get("project") or {}).get("handling")
    value = override or (handling.get("engineer_edits") if isinstance(handling, dict) else None)
    return value if value in L.ENGINEER_EDITS else "allowed"


DESCRIPTION_TARGET = 250
DESCRIPTION_WARN = 300


def make_description(plan):
    """The description agents read to decide when to load the skill: what it does, then the words
    that should trigger it (one work item id as an example, one file name, the specification folder).
    The example is the first planned item, never a range, because a range would include the ids of
    external items, which have no specification. Short, because every description of every
    installed skill shares one listing budget."""
    proj = plan["project"]
    first = plan["items"][0]
    tag = L.tag(plan, first["id"])
    stem = f"{tag.lower()}-{first['slug']}"
    d = (f"Orients on one {proj['name']} work item before any code change, reading its spec, the ground truth sections it cites "
         f"and the conventions. Use when the user names a work item id such as {tag}, a file such as {stem}, or {proj['spec_dir']}/.")
    d = d.replace("<", "").replace(">", "")      # angle brackets are not allowed in a skill description
    if len(d) >= 1024:
        d = d[:1020].rsplit(" ", 1)[0] + "."
    return d


def tests_text(plan):
    """Only what the conventions do not already say. The commands, the flag and the extra rules
    are printed once, by conventions_text, which is the single source for them."""
    c = plan["conventions"]
    lines = []
    if c.get("test_command") or c.get("lint_command"):
        lines.append("- Run the test and lint commands above before every commit. New work gets new tests. Fix findings instead of silencing them.")
    lines.append("- Commit messages are in the imperative. The pull request description lists the acceptance criteria and the proof for each.")
    lines.append("- Raw outputs, run records and screenshots go on the GitHub issue, not into the repository, unless the work item file says otherwise.")
    return "\n".join(lines)


def dod_checkboxes(plan):
    c = plan["conventions"]
    items = ["Every acceptance criterion in the work item file is proven by a named test or a recorded check, and the pull request lists each one with its proof."]
    if c.get("test_command") or c.get("lint_command") or c.get("feature_flag") or c.get("extra"):
        items.append("The project conventions above hold, the test and lint commands pass, and the continuous integration run is green.")
    items.append("Departures from the file are recorded under \"Decisions recorded\" with the pull request number. A conflict with the ground truth is fixed in the work item file in the same pull request.")
    items.append("The closing comment on the issue follows the template in the specification folder README (Demo, Evidence, Decisions, Handoff) and carries every artifact named under \"Evidence of completion\". The agent assembles it, the engineer checks and posts it.")
    items.append("The joint check named under \"Integration points\" has run at the item's checkpoint with both tracks present, or the Handoff line says what still needs to run.")
    return "\n".join(f"- [ ] {i}" for i in items)


def skill_target(plan):
    """(skill name, skill path) of the plan, after the checks that make them usable. A problem stops the
    script with one line."""
    proj = plan["project"]
    skill_path = proj.get("dev_skill_path")
    skill_name = proj.get("dev_skill")
    if not skill_path or not skill_name:
        L.die("project.dev_skill and project.dev_skill_path are required in plan.yaml")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", skill_name):
        L.die("project.dev_skill must be lowercase words joined by hyphens")
    if len(skill_name) > 64:
        L.die(f"project.dev_skill is {len(skill_name)} characters. A skill name has at most 64")
    if Path(skill_path).name != skill_name:
        L.die(f"the last folder of project.dev_skill_path ({Path(skill_path).name}) must equal project.dev_skill ({skill_name}). "
              "Agents load a skill only when its folder and its name match")
    if not plan["items"]:
        L.die("plan.yaml has no items yet, so there is nothing for the engineers' skill to describe")
    return skill_name, skill_path


def skill_makers(plan, root, bundles=None, engineer_edits=None):
    """{relative path: function that returns the file's text} for the engineers' skill. root is the folder
    that holds the specification and, unless bundles is given, docs/context. bundles maps a path such as
    docs/context/wi-06.bundle.json to its bytes (what compile_bundles returns). engineer_edits is allowed
    or request-only (engineer_edits_of): it decides the wording of step 8 and of the change-request
    section of the README."""
    request_only = engineer_edits_of(plan, engineer_edits) == "request-only"
    proj = plan["project"]
    skill_name, skill_path = skill_target(plan)
    first = plan["items"][0]
    ms1 = L.milestone_by_num(plan)[first["milestone"]]
    stem = f"{L.tag(plan, first['id']).lower()}-{first['slug']}"
    description = make_description(plan)
    values = {
        # a JSON string is a valid YAML double-quoted value, so ": " or " #" in a project name cannot break the frontmatter
        "skill_name": skill_name, "project_name": proj["name"], "description": json.dumps(description, ensure_ascii=False),
        "id_prefix": proj["id_prefix"], "context_dir": CONTEXT_DIR,
        "purpose_extra": "Its conventions come from the plan folder, and its references are generated from the same files.",
        "spec_dir": proj["spec_dir"], "example_id": L.tag(plan, first["id"]), "example_stem": stem,
        "example_path": f"{proj['spec_dir']}/{ms1['folder']}/{stem}.md",
        "conventions": L.conventions_text(plan), "branch": proj["branch"],
        "definition_of_done": dod_checkboxes(plan), "tests": tests_text(plan),
        "item_count": len(plan["items"]), "skill_path": skill_path, "skill_path_win": skill_path.replace("/", "\\"),
        "tree_url": L.github_tree_url(plan, skill_path) if proj.get("repo") else "<repository tree url for this folder>",
        "decisions_step": DECISIONS_REQUEST_ONLY if request_only else DECISIONS_ALLOWED,
        "change_requests": CHANGES_REQUEST_ONLY if request_only else CHANGES_ALLOWED,
    }
    return {
        "SKILL.md": lambda: L.fill(L.read_template("dev-skill", "SKILL.md.tmpl"), values),
        "README.md": lambda: L.fill(L.read_template("dev-skill", "README.md.tmpl"), values),
        "references/work-items.md": lambda: work_items_md(plan, root),
        "references/contracts.md": lambda: contracts_md(plan, root),
        "references/ground-truth-map.md": lambda: ground_truth_map_md(plan, root, bundles=bundles),
        "scripts/check_context.py": lambda: L.fill(L.read_template("dev-skill", "scripts", "check_context.py"), values),
    }


def skill_files(plan, root, bundles=None, engineer_edits=None):
    """{relative path: text} of every file of the engineers' skill, built from the plan, the
    specifications under root and the bundles (see skill_makers). Nothing is read from or written to
    docs/dev."""
    return {rel: make() for rel, make in skill_makers(plan, root, bundles, engineer_edits).items()}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Generate the engineers' skill folder (SKILL.md, README.md, references/) from plan.yaml, the specs and the rendered ground truth. Dry run unless --apply.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--apply", action="store_true", help="write the files. Without it this is a dry run")
    ap.add_argument("--force", action="store_true", help="replace files that already exist")
    ap.add_argument("--only", choices=["references"], help="write only references/ (always replaced: they are generated). "
                    "Use it after plan.yaml or a specification changes; SKILL.md and README.md keep their hand edits")
    a = ap.parse_args(argv)
    root = L.project_root(a.root)
    plan_path = L.owner_plan(root, a.plan)
    if not L.exists(plan_path):
        L.die(f"no plan at {plan_path}")
    plan, problems = L.load_plan(plan_path, root)
    if problems:
        L.say("plan.yaml has problems:")
        for p in problems:
            L.say("  - " + p)
        return 1
    proj = plan["project"]
    skill_name, skill_path = skill_target(plan)
    description = make_description(plan)
    outputs = skill_makers(plan, root)
    if a.only == "references":
        # the references follow plan.yaml and the specs; SKILL.md and README.md may hold hand edits
        outputs = {k: v for k, v in outputs.items() if k.startswith("references/")}
    dest = L.inside(root, root / skill_path, "project.dev_skill_path")
    if a.only == "references" and not L.exists(dest / "SKILL.md"):
        # references alone would leave a folder no agent loads: SKILL.md is what makes it a skill
        L.die(f"{skill_path}/SKILL.md does not exist yet, so there is no engineers' skill to refresh. "
              "Run this script without --only first: it writes SKILL.md, README.md and the references")
    L.say(f"engineers' skill: {skill_name}  ->  {skill_path}")
    L.say(f"description length: {len(description)} characters (target under {DESCRIPTION_TARGET}, limit 1024)")
    released = read_sidecars(root)
    L.say(f"approved contexts found in {CONTEXT_DIR}/: {len(released)} of {len(plan['items'])} work items" +
          ("" if released else ". The map will say none is released. Compile them with compile_bundles.py first"))
    if len(description) > DESCRIPTION_WARN:
        L.say(f"warning: the description is over {DESCRIPTION_WARN} characters. Shorten project.name: long descriptions are the first to be dropped when an agent lists many skills")
    n = 0
    for rel, make in outputs.items():
        content = make()
        p = L.inside(dest, dest / rel, "output")
        if p.exists() and not (a.force or a.only == "references"):
            L.say(f"  skip (exists): {rel}")
            continue
        L.say(f"  {'write' if a.apply else 'would write'}: {rel} ({len(content.splitlines())} lines)")
        if a.apply:
            shown = p.relative_to(root).as_posix() if root in p.parents else str(p)
            RG.require(RG.maintenance_class(root), shown, L.sha256_text(content), "engineers-skill", root)
            L.write_text(p, content)
        n += 1
    L.say(f"{n} file(s) {'written' if a.apply else 'would be written'}." + ("" if a.apply else " Dry run. Add --apply to write."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
