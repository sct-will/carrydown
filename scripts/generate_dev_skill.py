#!/usr/bin/env python3
"""Generate the per-project developer skill from the specification folder.

Output, under project.dev_skill_path in plan.yaml
  SKILL.md                         when to use it, how to orient on an item, conventions, definition of done
  README.md                        what it is and how to install it for each agent
  references/work-items.md         the index of work items with dates, dependencies and file paths
  references/contracts.md          the headings of every Contract or Protocol section, by item
  references/ground-truth-map.md   ground truth headings with anchors and line numbers, and sections by item

The files are generated from plan.yaml, the specs and the rendered ground truth. Read them
after generating: add the topics and contracts only a person knows to be important.

Dry run unless --apply. Existing files are replaced only with --force.

Usage
  python3 scripts/generate_dev_skill.py --root .            dry run
  python3 scripts/generate_dev_skill.py --root . --apply    write
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import scaffold_spec as SC  # noqa: E402


def md_table(headers, rows):
    return SC.md_table(headers, rows)


def work_items_md(plan, root):
    out = ["# Work item index", "",
           "Generated from `plan.yaml`. The GitHub issues hold the owners, status and dates of record.", "",
           "## Work units and milestones", "",
           SC.schedule_table(plan), ""]
    tdate, ttext = L.target_date(plan)
    by_track = {}
    for person in plan["people"]:
        by_track[person["track"]] = by_track.get(person["track"], 0) + person.get("allocation", 100)
    alloc = ", ".join(f"{L.track_label(plan, t)} {pct} percent" for t, pct in by_track.items())
    out += [f"Target. {ttext if tdate else 'not set in plan.yaml'}.", "",
            f"Allocation. People are allocated as a percentage of their working time to this plan. By track, the allocation adds up to {alloc}. The dates in this plan already account for it, so a track at less than 100 percent has fewer working days in each work unit.", ""]
    spec_dir = plan["project"]["spec_dir"]
    for m in plan["milestones"]:
        out += [f"## Milestone {m['number']}, {m['name']} (`{m['folder']}`)", "",
                f"Exit gate. {m['gate']}", ""]
        rows = []
        for it in plan["items"]:
            if it["milestone"] != m["number"]:
                continue
            deps = ", ".join(L.tag(plan, d) for d in it["depends"]) or "None"
            if it["program_input"]:
                deps += f"; program input: {it['program_input']}"
            rows.append([L.tag(plan, it["id"]), it["label"], L.track_label(plan, it["track"]), it["complete_by"], deps,
                         f"`{spec_dir}/{m['folder']}/{L.tag(plan, it['id']).lower()}-{it['slug']}.md`"])
        out += [md_table(["Id", "Work item", "Track", "Complete by", "Depends on", "File"], rows), ""]
    if plan["program"]["items"]:
        out += ["## Program items and program inputs", "",
                "These are owned by the program, not by the developers. They have no work item file. An item that needs one says \"program input\" in its Depends on row. If the input is missing, say so in the pull request and do not invent it.", "",
                md_table(["Id", "Program item", "Note"], [[L.tag(plan, p["id"]), p["label"], p.get("note", "")] for p in plan["program"]["items"]]), ""]
    return "\n".join(out).rstrip() + "\n"


def contracts_md(plan, root):
    spec_dir = plan["project"]["spec_dir"]
    out = ["# Contracts quick reference", "",
           "Where each contract is defined. The owning work item file holds the contract text. When a contract changes, the work item file changes first and this page follows.", "",
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
        rows.append([L.tag(plan, it["id"]), it["label"], name, f"`{rel}`"])
        blocks.append((it, name, subs, tables, fences, rel))
    out += [md_table(["Id", "Work item", "Section", "File"], rows), ""]
    for it, name, subs, tables, fences, rel in blocks:
        out += [f"## {L.tag(plan, it['id'])} {it['label']}", "", f"Section `## {name}` in `{rel}`. {tables} table(s), {fences} code block(s)."]
        if subs:
            out += ["", "Parts:"] + [f"- {s}" for s in subs]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def ground_truth_map_md(plan, root):
    gt = Path(root) / plan["project"]["ground_truth"]
    out = ["# Ground truth map", "",
           f"Headings of `{plan['project']['ground_truth']}` with GitHub anchors and line numbers, then the sections each work item cites. "
           "Regenerating the rendering may move line numbers. Run `generate_dev_skill.py` again then.", ""]
    if gt.exists():
        import render_ground_truth as R
        lines = gt.read_text(encoding="utf-8").split("\n")
        heads = R.collect_headings(lines)
        anchors = R.anchors_for(heads)
        out += ["## By heading", ""]
        rows = [[f"{ln}", "#" * lvl, text, f"`#{anc}`"] for (ln, lvl, text), anc in zip(heads, anchors) if lvl > 1]
        out += [md_table(["Line", "Level", "Heading", "Anchor"], rows), ""]
    else:
        out += [f"The rendered ground truth was not found at `{plan['project']['ground_truth']}`. Render it with `render_ground_truth.py`, then run this generator again.", ""]
    out += ["## By work item", "",
            md_table(["Id", "Work item", "Ground truth sections"], [[L.tag(plan, it["id"]), it["label"], it.get("ground_truth", "")] for it in plan["items"]]), ""]
    return "\n".join(out).rstrip() + "\n"


def make_description(plan):
    proj = plan["project"]
    pre = proj["id_prefix"]
    n = len(plan["items"])
    first = plan["items"][0]
    stem = f"{L.tag(plan, first['id']).lower()}-{first['slug']}"
    d = (f"Use when working on a work item of the {proj['name']} project in this repository, named by id (for example "
         f"{L.tag(plan, plan['items'][0]['id'])} or {L.tag(plan, plan['items'][-1]['id'])}), by a file name such as {stem}, "
         f"or by its specification under {proj['spec_dir']}/. "
         f"Gives the steps to orient on one item. The agent reads its specification, the ground truth sections it cites and the project conventions "
         f"before changing code. Covers the definition of done, the test and lint commands, the work item index ({n} items), "
         f"the contract headings and the ground truth map.")
    if len(d) >= 1024:
        d = d[:1020].rsplit(" ", 1)[0] + "."
    return d


def tests_text(plan):
    c = plan["conventions"]
    lines = []
    if c.get("test_command"):
        lines.append(f"- Run the tests with `{c['test_command']}` before every commit. New work gets new tests.")
    if c.get("lint_command"):
        lines.append(f"- Run `{c['lint_command']}`. Fix findings instead of silencing them.")
    if c.get("feature_flag"):
        lines.append(f"- Keep new behaviour behind `{c['feature_flag']}`. With the flag off, existing behaviour is unchanged.")
    lines.append("- Commit messages are in the imperative. The pull request description lists the acceptance criteria and the proof for each.")
    lines.append("- Raw outputs, run records and screenshots go on the GitHub issue, not into the repository, unless the work item file says otherwise.")
    return "\n".join(lines)


def dod_checkboxes(plan):
    c = plan["conventions"]
    items = ["Every acceptance criterion in the work item file is proven by a named test or a recorded check, and the pull request lists each one with its proof."]
    cmds = [f"`{c[k]}`" for k in ("test_command", "lint_command") if c.get(k)]
    if cmds:
        items.append(" and ".join(cmds) + " pass, and the continuous integration run is green.")
    if c.get("feature_flag"):
        items.append(f"With `{c['feature_flag']}` off, existing behaviour and responses are unchanged.")
    for extra in c.get("extra") or []:
        items.append(extra)
    items.append("Departures from the file are recorded under \"Decisions recorded\" with the pull request number. A conflict with the ground truth is fixed in the work item file in the same pull request.")
    items.append("The closing comment on the issue follows the template in the specification folder README (Demo, Evidence, Decisions, Handoff) and carries every artifact named under \"Evidence of completion\". The agent assembles it, the developer checks and posts it.")
    items.append("The joint check named under \"Integration points\" has run at the item's checkpoint with both tracks present, or the Handoff line says what still needs to run.")
    return "\n".join(f"- [ ] {i}" for i in items)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Generate the developer skill folder (SKILL.md, README.md, references/) from plan.yaml, the specs and the rendered ground truth. Dry run unless --apply.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--apply", action="store_true", help="write the files. Without it this is a dry run")
    ap.add_argument("--force", action="store_true", help="replace files that already exist")
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
    proj = plan["project"]
    skill_path = proj.get("dev_skill_path")
    skill_name = proj.get("dev_skill")
    if not skill_path or not skill_name:
        L.die("project.dev_skill and project.dev_skill_path are required in plan.yaml")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", skill_name):
        L.die("project.dev_skill must be lowercase words joined by hyphens")
    first = plan["items"][0]
    ms1 = L.milestone_by_num(plan)[first["milestone"]]
    stem = f"{L.tag(plan, first['id']).lower()}-{first['slug']}"
    gt = proj["ground_truth"]
    values = {
        "skill_name": skill_name, "project_name": proj["name"], "description": make_description(plan),
        "purpose_extra": "Its conventions come from the plan folder, and its references are generated from the same files.",
        "spec_dir": proj["spec_dir"], "example_id": L.tag(plan, first["id"]), "example_stem": stem,
        "example_path": f"{proj['spec_dir']}/{ms1['folder']}/{stem}.md",
        "ground_truth": gt, "ground_truth_index": re.sub(r"\.md$", ".index.txt", gt),
        "conventions": SC.conventions_text(plan), "branch": proj["branch"],
        "definition_of_done": dod_checkboxes(plan), "tests": tests_text(plan),
        "item_count": len(plan["items"]), "skill_path": skill_path, "skill_path_win": skill_path.replace("/", "\\"),
        "tree_url": L.github_tree_url(plan, skill_path) if proj.get("repo") else "<repository tree url for this folder>",
    }
    outputs = {
        "SKILL.md": L.fill(L.read_template("dev-skill", "SKILL.md"), values),
        "README.md": L.fill(L.read_template("dev-skill", "README.md"), values),
        "references/work-items.md": work_items_md(plan, root),
        "references/contracts.md": contracts_md(plan, root),
        "references/ground-truth-map.md": ground_truth_map_md(plan, root),
    }
    dest = root / skill_path
    L.say(f"developer skill: {skill_name}  ->  {skill_path}")
    L.say(f"description length: {len(values['description'])} characters (limit 1024)")
    n = 0
    for rel, content in outputs.items():
        p = dest / rel
        if p.exists() and not a.force:
            L.say(f"  skip (exists): {rel}")
            continue
        L.say(f"  {'write' if a.apply else 'would write'}: {rel} ({len(content.splitlines())} lines)")
        if a.apply:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        n += 1
    L.say(f"{n} file(s) {'written' if a.apply else 'would be written'}." + ("" if a.apply else " Dry run. Add --apply to write."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
