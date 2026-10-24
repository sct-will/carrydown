#!/usr/bin/env python3
"""Scaffold the specification folder from plan.yaml.

What it creates, under <root>/<spec_dir> (docs/spec by default)
  plan.yaml                  from the annotated template, with --init
  README.md                  conventions, schedule, comment templates and the index
  <milestone folder>/        one per milestone
  <milestone folder>/milestone.md   the sub-epic content, with TODO lines to fill in
  <milestone folder>/<id>-<slug>.md one stub per work item, with --stubs

Rules
  Nothing is written unless you pass --apply. The default is a dry run.
  Existing files are never overwritten unless you pass --force.
  --refresh-headers rewrites only the header table of existing files so they match plan.yaml
  after you change a date, an owner or a dependency. It also rewrites the sections written from
  the plan's rationale: "Why these items form this milestone" and "Joint demonstration" in each
  milestone.md, and "How this plan was composed" in the README. It adds them where they are
  missing. The rest of each file is left alone.

Usage
  python3 scripts/scaffold_spec.py --root . --init --name "My project"   write a starter plan.yaml
  python3 scripts/scaffold_spec.py --root .                              dry run
  python3 scripts/scaffold_spec.py --root . --apply --stubs              write the folder and the stubs
  python3 scripts/scaffold_spec.py --root . --apply --ci                 add the continuous integration workflow and the checker copy
  python3 scripts/scaffold_spec.py --root . --apply --refresh-headers    sync headers with the plan
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402


md_table = L.md_table
conventions_text = L.conventions_text
schedule_table = L.schedule_table


def milestone_table(plan):
    rows = []
    for m in plan["milestones"]:
        rows.append([
            f"[Milestone {m['number']}, {m['name']}]({m['folder']}/milestone.md)",
            f"`{m['folder']}`", f"{m['start']} to {m['end']}", m["end"], m["demo"], m["gate"],
        ])
    return md_table(["Sub-epic", "Folder", "Work unit", "Due", "Demonstration", "Expected outcome"], rows)


def checkpoint_table(plan):
    rows = []
    for c in sorted(plan["checkpoints"], key=lambda c: c["date"]):
        due = [L.tag(plan, it["id"]) for it in plan["items"] if it["checkpoint"] == c["date"]]
        rows.append([c["date"], c["name"], ", ".join(due) or "none closing", c.get("joint_check", "")])
    return md_table(["Date", "Checkpoint", "Items due", "Joint check"], rows)


def work_table(plan, ms, link_prefix=""):
    rows = []
    for it in plan["items"]:
        if it["milestone"] == ms["number"]:
            fname = f"{L.tag(plan, it['id']).lower()}-{it['slug']}.md"
            rows.append([L.tag(plan, it["id"]), f"[{it['label']}]({link_prefix}{fname})", L.track_label(plan, it["track"]), it["complete_by"]])
    return md_table(["Id", "Work item", "Track", "Complete by"], rows)


def index_text(plan):
    out = []
    for m in plan["milestones"]:
        out.append(f"Milestone {m['number']}, {m['name']} (`{m['folder']}`), work unit {m['number']}")
        out.append("")
        rows = []
        for it in plan["items"]:
            if it["milestone"] == m["number"]:
                stem = f"{L.tag(plan, it['id']).lower()}-{it['slug']}"
                rows.append([f"[{stem}]({m['folder']}/{stem}.md)", it["label"], L.track_label(plan, it["track"]), it["complete_by"]])
        out.append(md_table(["Id", "Work item", "Track", "Complete by"], rows))
        out.append("")
    return "\n".join(out).rstrip()


GENERATED_NOTE = "<!-- Written from plan.yaml. Change it there, then run scaffold_spec.py --refresh-headers --apply. -->"


def track_list(plan, ids):
    labels = [L.track_label(plan, t) for t in ids]
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]


def composition_text(plan, ms):
    """Body of "Why these items form this milestone": the rationale, then the items per track."""
    out = [GENERATED_NOTE, "",
           ms.get("rationale") or "TODO: Why these items form this milestone, two to four sentences. Write it under `rationale` "
                                  "for this milestone in plan.yaml, then run scaffold_spec.py --refresh-headers --apply."]
    covered = L.milestone_tracks(plan, ms)
    if covered:
        out.append("")
        for t, its in covered:
            out.append(f"- {L.track_label(plan, t)}: " + ", ".join(
                L.tag(plan, it["id"]) + (f" ({it['theme']})" if it.get("theme") else "") for it in its) + ".")
    if ms.get("single_track_reason"):
        out += ["", f"Why one track: {ms['single_track_reason']}"]
    return "\n".join(out)


def joint_demonstration_text(plan, ms):
    """Body of "Joint demonstration": what the engineers show together, who, and the joint check."""
    out = [GENERATED_NOTE, "",
           ms.get("joint_demonstration") or "TODO: What the engineers whose tracks meet show together, one or two sentences. "
                                            "Write it under `joint_demonstration` for this milestone in plan.yaml, then run scaffold_spec.py --refresh-headers --apply."]
    cp = L.demo_checkpoint(plan, ms)
    tracks = [t for t, _ in L.milestone_tracks(plan, ms)]
    if cp:
        tracks += [t for t in L.tracks_named(plan, cp.get("joint_check", "")) if t not in tracks]
    if tracks:
        order = [t.get("id") for t in plan["tracks"]]
        tracks.sort(key=lambda t: order.index(t) if t in order else len(order))
        out += ["", f"Given together on {ms['demo']} by the engineers of the {track_list(plan, tracks)} track{'s' if len(tracks) > 1 else ''}."]
    if cp and cp.get("joint_check"):
        out.append(f"The joint check for that date, {cp['name']}: {cp['joint_check']}")
    return "\n".join(out)


def readme_composition(plan):
    """Body of "How this plan was composed": the ten rules, the order per track, the milestones."""
    out = [GENERATED_NOTE, "",
           "The plan follows ten rules. The reasons below are written in `plan.yaml`, so a reviewer can argue with each one against the dates in the schedule.", ""]
    out += [f"{n}. {r}" for n, r in enumerate(L.PLANNING_RULES, 1)]
    rows = []
    for t in plan["tracks"]:
        its = sorted((it for it in plan["items"] if it.get("track") == t.get("id")), key=lambda it: (it["complete_by"], it["id"]))
        if its:
            rows.append([t.get("label") or t.get("id"), ", ".join(L.tag(plan, it["id"]) for it in its), t.get("order_rationale") or "Not written yet."])
    out += ["", "### Order of work per track", "", md_table(["Track", "Items in date order", "Why this order"], rows) if rows else "No items yet."]
    rows = []
    for m in plan["milestones"]:
        covered = [t for t, _ in L.milestone_tracks(plan, m)]
        why = m.get("rationale") or "Not written yet."
        if m.get("single_track_reason"):
            why += f" Why one track: {m['single_track_reason']}"
        rows.append([f"{m['number']}, {m['name']}", (track_list(plan, covered) + (" only" if len(covered) == 1 else "")) if covered else "No items yet",
                     why, m.get("joint_demonstration") or "Not written yet."])
    out += ["", "### Milestones", "", md_table(["Milestone", "Tracks", "Why these items", "Joint demonstration"], rows)]
    return "\n".join(out)


def external_section(plan):
    items = plan["external"]["items"]
    if not items:
        return ""
    rows = [[L.tag(plan, p["id"]), p["label"], p.get("note", "")] for p in items]
    return (
        "## Work outside the plan\n\n"
        "Some items depend on inputs from outside the team, such as pilot teams, approvals and reviews. "
        "Those are marked \"external input\" in the item files. The work that provides them is owned outside the team, "
        "so the plan does not schedule it. Its ids are left as gaps in the numbering on purpose, and it is not tracked as issues in this plan.\n\n"
        + md_table(["Id", "External item", "Note"], rows) + "\n\n"
    )


def source_table(plan):
    sources = plan.get("sources") or [{"name": "Ground truth", "path": plan["project"]["ground_truth"], "use": "Full specification. Section numbers in the work item files refer to it."}]
    rows = [[s.get("name", ""), f"`{s.get('path', '')}`", s.get("use", "")] for s in sources]
    return md_table(["Document", "Path", "Use"], rows)


def build_readme(plan):
    proj = plan["project"]
    vals = {
        "project_name": proj["name"],
        "ground_truth": proj["ground_truth"],
        "dev_skill_path": proj.get("dev_skill_path", ""),
        "branch": proj["branch"],
        "source_table": source_table(plan),
        "conventions": conventions_text(plan),
        "schedule_table": schedule_table(plan),
        "milestone_table": milestone_table(plan),
        "checkpoint_table": checkpoint_table(plan),
        "closing_comment": L.read_template("closing-comment.md").rstrip().replace("{{tag}}", f"{proj['id_prefix']}-NN").replace("{{label}}", "<label>"),
        "checkpoint_comment": L.read_template("checkpoint-comment.md").rstrip().replace("{{date}}", "<date>").replace("{{name}}", "<name>"),
        "external_section": external_section(plan),
        "index": index_text(plan),
        "composition": readme_composition(plan),
    }
    return L.fill(L.read_template("spec-README.md"), vals)


def build_milestone(plan, ms):
    its = [L.tag(plan, it["id"]) for it in plan["items"] if it["milestone"] == ms["number"]]
    vals = {
        "number": ms["number"], "name": ms["name"], "project_name": plan["project"]["name"],
        "start": ms["start"], "end": ms["end"], "folder": ms["folder"], "gate": ms["gate"],
        "demo": ms["demo"], "ids": ", ".join(its),
        "work_table": work_table(plan, ms),
        "composition": composition_text(plan, ms),
        "joint_demonstration": joint_demonstration_text(plan, ms),
        "references": "\n".join(
            [f"- `{L.tag(plan, it['id']).lower()}-{it['slug']}.md`" for it in plan["items"] if it["milestone"] == ms["number"]]
            + [f"- The ground truth, `{plan['project']['ground_truth']}`", "- The schedule and checkpoint tables in `../README.md`"]
        ),
    }
    return L.fill(L.read_template("milestone.md"), vals)


def build_stub(plan, it):
    return L.fill(L.read_template("spec.md"), {"tag": L.tag(plan, it["id"]), "label": it["label"], "header": L.header_markdown(plan, it)})


def replace_first_table(text, new_table):
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith("|")), None)
    if start is None:
        return text
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return "\n".join(lines[:start] + new_table.split("\n") + lines[end:])


def replace_section_table(text, heading, new_table):
    m = re.search(rf"(?m)^## {re.escape(heading)}\n", text)
    if not m:
        return text
    head, tail = text[: m.end()], text[m.end():]
    lines = tail.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith("|")), None)
    if start is None:
        return text
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return head + "\n".join(lines[:start] + new_table.split("\n") + lines[end:])


PLACEHOLDERS = (
    ("project.name", '"Your project name"', "the project name, or pass --name"),
    ("project.slug", "your-project", "lowercase words joined by hyphens, derived from --name"),
    ("project.repo", "your-org/your-repo", "the GitHub repository for issues, as owner/name"),
    ("project.dev_skill", "your-project-dev", "the name of the generated engineers' skill"),
)


def init_plan(root, a, git_top):
    """Write a starter plan.yaml from the template, with the project name filled in."""
    target = L.find_plan(root, a.plan) if a.plan else root / "docs/spec/plan.yaml"
    target = L.inside(root, target, "plan.yaml")
    text = L.read_template("plan.yaml")
    if a.name:
        slug = L.slugify(a.name) or "your-project"
        q = lambda v: json.dumps(v, ensure_ascii=False)   # a JSON string is a valid YAML double-quoted value
        text = text.replace('name: "Your project name"', f"name: {q(a.name)}", 1)
        text = text.replace('project_title: "Your project plan"', f"project_title: {q(a.name + ' plan')}", 1)
        text = text.replace('epic_title: "Your project, development plan"', f"epic_title: {q(a.name + ', development plan')}", 1)
        text = text.replace("your-project-dev", f"{slug}-dev")
        text = re.sub(r"(?m)^(  slug: )your-project\b", lambda m: m.group(1) + slug, text)
    if target.exists() and not a.force:
        print(f"plan.yaml already exists at {target}. Use --force to replace it.")
        return 1
    rel = target.relative_to(root)
    if (git_top is not None and git_top != root) or root.name == "docs":
        where = f"the top folder of its git repository is {git_top}" if git_top else "it is named docs"
        print(f"warning: this writes {rel} under {root}, but {where}. If {root} is not the project folder "
              f"(a docs folder would end up with docs/docs/spec), run from the project folder or pass --root.", file=sys.stderr)
    print(f"{'writing' if a.apply else 'would write'} {rel}")
    if a.apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    todo = []
    for key, value, what in PLACEHOLDERS:
        if re.search(rf"(?m)^  {key.split('.')[1]}: {re.escape(value)}(\s|$)", text):
            todo.append(f"  {key} is still {value}: {what}")
    if a.name:
        dev = re.search(r"(?m)^  dev_skill: (\S+)", text).group(1)
        todo.append(f"  project.dev_skill is {dev}, derived from the name. Change it, and dev_skill_path with it, if the engineers' skill needs another name")
    print("Placeholders still to fill in plan.yaml:")
    for t in todo:
        print(t)
    print("The people, milestones, checkpoints and items in the file are examples to replace.")
    if a.apply:
        print("Fill in plan.yaml, then run this script again without --init.")
    return 0


def is_placeholder(value):
    return not value.strip() or "to be " in value.lower() or "TODO" in value


def refreshed_header(plan, it, old):
    """The header table of a work item file, from plan.yaml, keeping what a person filled in.

    The plan decides the rows it holds values for. A Size or Ground truth row a person filled in
    stays when the plan has no value for it, and rows the template does not have stay at the end."""
    have = dict(L.table_rows(old))
    rows = []
    for name, value in L.expected_header(plan, it):
        if name in ("Size", "Ground truth") and is_placeholder(value) and not is_placeholder(have.get(name, "")):
            value = have[name]
        rows.append((name, value))
    known = {n for n, _ in rows}
    rows += [(n, v) for n, v in L.table_rows(old) if n not in known]
    return "\n".join(L.HEADER_LINES + [f"| {n} | {v} |" for n, v in rows])


def template_demonstration(plan, ms):
    """The Demonstration row of the milestone template, filled in for ms."""
    for n, v in L.table_rows(L.read_template("milestone.md").split("## ", 1)[0]):
        if n == "Demonstration":
            return L.fill(v, {"demo": ms["demo"], "number": ms["number"], "name": ms["name"]})
    return ms["demo"]


def refreshed_milestone_header(plan, ms, old):
    """Due, Exit gate and Work items come from plan.yaml. The Demonstration row keeps its wording
    and only takes the new date. Other rows a person added stay."""
    have = L.table_rows(old)
    its = ", ".join(L.tag(plan, it["id"]) for it in plan["items"] if it["milestone"] == ms["number"])
    demo = dict(have).get("Demonstration")
    if demo is None:
        demo = template_demonstration(plan, ms)
    elif re.match(r"^\d{4}-\d\d-\d\d", demo):
        demo = ms["demo"] + demo[10:]
    else:
        demo = f"{ms['demo']}, {demo}"
    rows = [("Due", ms["end"]), ("Exit gate", ms["gate"]), ("Work items", its), ("Demonstration", demo)]
    known = {n for n, _ in rows}
    rows += [(n, v) for n, v in have if n not in known]
    return "\n".join(L.HEADER_LINES + [f"| {n} | {v} |" for n, v in rows])


def heading_spans(lines):
    """{heading text: (start, end)} of the level-two sections outside code fences. A section runs
    from its heading line to the next level-two heading or the end of the file."""
    heads = []
    fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence and line.startswith("## "):
            heads.append((i, line[3:].strip()))
    spans = {}
    for k, (i, name) in enumerate(heads):
        spans.setdefault(name, (i, heads[k + 1][0] if k + 1 < len(heads) else len(lines)))
    return spans


def put_section(text, heading, body, before=()):
    """Replace the body of the section `## heading` with body. When the section is missing, insert
    it before the first section in `before` that exists, or at the end. Other lines stay as they are."""
    lines = text.split("\n")
    block = [f"## {heading}", ""] + body.split("\n") + [""]
    spans = heading_spans(lines)
    if heading in spans:
        i, j = spans[heading]
        if j == len(lines) and lines and lines[-1] == "":
            j -= 1   # keep the final newline of the file
        lines[i:j] = block
    else:
        at = next((spans[b][0] for b in before if b in spans), None)
        if at is None:
            if lines and lines[-1] == "":
                lines.pop()
            lines += [""] + block
        else:
            lines[at:at] = block
    return "\n".join(lines)


MILESTONE_SECTIONS = (
    ("Why these items form this milestone", composition_text, ("Expected outcomes", "Acceptance criteria", "Joint demonstration", "Demonstration expectations", "Work items")),
    ("Joint demonstration", joint_demonstration_text, ("Demonstration expectations", "Work items", "References")),
)


README_TABLES = ("| Work unit | Dates | Gate |", "| Sub-epic |", "| Date | Checkpoint | Items due | Joint check |",
                 "| Id | Work item | Track | Complete by |", "| Id | External item | Note |")
# Older headers of the same tables, so a README written before a rename is still refreshed.
README_TABLE_ALIASES = {"| Id | External item | Note |": ("| Id | Outside item | Note |", "| Id | Program item | Note |")}


def tables_of(lines):
    """[(start, end, header line)] of the tables outside code fences."""
    out = []
    fence = False
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("```"):
            fence = not fence
        if not fence and lines[i].startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append((i, j, lines[i]))
            i = j
            continue
        i += 1
    return out


def refreshed_readme(plan, old):
    """Refresh the generated tables of the specification README (schedule, sub-epics, checkpoints,
    index, external items) and leave every other line alone. Return (text, kinds not refreshed)."""
    lines = old.split("\n")
    fresh = build_readme(plan).split("\n")
    have, want = tables_of(lines), tables_of(fresh)
    swaps, skipped = [], []
    for head in README_TABLES:
        o = [t for t in have if t[2].startswith((head,) + README_TABLE_ALIASES.get(head, ()))]
        f = [t for t in want if t[2].startswith(head)]
        if len(o) != len(f):
            skipped.append(head.strip("| ").split(" |")[0])
            continue
        swaps += list(zip(o, f))
    for (s0, e0, _), (s1, e1, _) in sorted(swaps, key=lambda x: -x[0][0]):
        lines[s0:e0] = fresh[s1:e1]
    text = put_section("\n".join(lines), "How this plan was composed", readme_composition(plan), ("Schedule", "Index"))
    return text, skipped


def refresh(plan, root, a, actions):
    def put(path, old, new, kind, what="refresh header"):
        if new != old:
            actions.append((what, path, kind))
            if a.apply:
                L.inside(root, path, kind).write_text(new, encoding="utf-8")
    for it in plan["items"]:
        p = L.spec_path(plan, root, it)
        if p.exists():
            old = L.read_text(p)
            put(p, old, replace_first_table(old, refreshed_header(plan, it, old)), "spec")
    for ms in plan["milestones"]:
        p = L.milestone_path(plan, root, ms)
        if p.exists():
            old = L.read_text(p)
            new = replace_first_table(old, refreshed_milestone_header(plan, ms, old))
            new = replace_section_table(new, "Work items", work_table(plan, ms))
            for heading, body, before in MILESTONE_SECTIONS:
                new = put_section(new, heading, body(plan, ms), before)
            put(p, old, new, "milestone")
    p = root / plan["project"]["spec_dir"] / "README.md"
    if p.exists():
        old = L.read_text(p)
        new, skipped = refreshed_readme(plan, old)
        put(p, old, new, "README", "refresh tables")
        for kind in skipped:
            print(f"note: README.md: the {kind} tables do not match the plan's shape, so they were left alone. Edit them by hand.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scaffold the specification folder from plan.yaml. Dry run unless --apply is given.",
        epilog="Existing files are never overwritten unless --force is given. --refresh-headers touches only header tables and the sections written from plan.yaml.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--init", action="store_true", help="write a starter plan.yaml from the annotated template and stop")
    ap.add_argument("--name", help="project name for --init")
    ap.add_argument("--stubs", action="store_true", help="also write one stub specification per work item")
    ap.add_argument("--refresh-headers", action="store_true", help="rewrite header tables of existing specs and milestone files, and the sections written from the plan's rationale, to match plan.yaml")
    ap.add_argument("--ci", action="store_true", help="also write .github/workflows/check-specs.yml and copy the checker to tools/carrydown/ so the checker runs in continuous integration")
    ap.add_argument("--force", action="store_true", help="overwrite existing files (README, milestone.md, stubs)")
    ap.add_argument("--apply", action="store_true", help="write files. Without it this is a dry run")
    ap.add_argument("--allow-no-git", action="store_true", help="write even when the project folder is not inside a git repository (not recommended)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    actions = []
    # the same check for a dry run as for --apply, so a dry run never promises what --apply refuses
    git_top = next((d for d in [root, *root.parents] if (d / ".git").exists()), None)
    if git_top is None and not a.allow_no_git:
        print(f"error: {root} is not inside a git repository, so nothing {'was' if a.apply else 'would be'} written.\n"
              "The plan, the specifications and every later change belong in git, so that each change is reviewed and can be undone.\n"
              "Run `git init` in the project folder (or ask your agent to), then run this command again.", file=sys.stderr)
        return 2
    if a.init:
        return init_plan(root, a, git_top)

    plan_path = L.find_plan(root, a.plan)
    if not plan_path.exists():
        print(f"error: no plan at {plan_path}. Run with --init first.", file=sys.stderr)
        return 2
    plan, problems = L.load_plan(plan_path)
    if problems:
        print("plan.yaml has problems. Fix them first:")
        for p in problems:
            print("  - " + p)
        return 1
    spec_dir = L.inside(root, root / plan["project"]["spec_dir"], "project.spec_dir")

    def plan_write(path, content, kind):
        path = L.inside(root, path, kind)
        exists = path.exists()
        if exists and not a.force:
            actions.append(("skip (exists)", path, kind))
            return
        actions.append(("overwrite" if exists else "create", path, kind))
        if a.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    plan_write(spec_dir / "README.md", build_readme(plan), "README")
    for ms in plan["milestones"]:
        plan_write(L.milestone_path(plan, root, ms), build_milestone(plan, ms), "milestone")
        if a.stubs:
            for it in plan["items"]:
                if it["milestone"] == ms["number"]:
                    plan_write(L.spec_path(plan, root, it), build_stub(plan, it), "stub")
        elif a.apply:
            L.inside(root, spec_dir / ms["folder"], "milestone folder").mkdir(parents=True, exist_ok=True)
    if a.ci:
        gt_dir = str(Path(plan["project"]["ground_truth"]).parent)
        wf = L.fill(L.read_template("check-specs-workflow.yml"), {"spec_dir": plan["project"]["spec_dir"], "ground_truth_dir": gt_dir, "branch": plan["project"]["branch"]})
        plan_write(root / ".github/workflows/check-specs.yml", wf, "ci workflow")
        for name in ("check_specs.py", "carrydown_lib.py"):
            plan_write(root / "tools/carrydown" / name, (Path(__file__).resolve().parent / name).read_text(encoding="utf-8"), "checker copy")
    if a.refresh_headers:
        refresh(plan, root, a, actions)
    verb = "" if a.apply else "would "
    for what, path, kind in actions:
        print(f"{verb}{what}: {path.relative_to(root)}  [{kind}]")
    missing = [it for it in plan["items"] if not L.spec_path(plan, root, it).exists()]
    if missing and not a.stubs:
        print(f"{len(missing)} specification stub(s) do not exist yet. Add --stubs to {'write' if a.apply else 'include'} them.")
    created = sum(1 for w, _, _ in actions if w in ("create", "overwrite", "refresh header", "refresh tables"))
    print(f"{len(actions)} action(s), {created} file(s) {'written' if a.apply else 'would be written'}." + ("" if a.apply else " Dry run. Add --apply to write."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
