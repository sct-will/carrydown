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
  after you change a date, an owner or a dependency. The rest of each file is left alone.

Usage
  python3 scripts/scaffold_spec.py --root . --init --name "My project"   write a starter plan.yaml
  python3 scripts/scaffold_spec.py --root .                              dry run
  python3 scripts/scaffold_spec.py --root . --apply --stubs              write the folder and the stubs
  python3 scripts/scaffold_spec.py --root . --apply --ci                 add the continuous integration workflow and the checker copy
  python3 scripts/scaffold_spec.py --root . --apply --refresh-headers    sync headers with the plan
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)


def conventions_text(plan):
    c = plan["conventions"]
    lines = []
    if c.get("feature_flag"):
        lines.append(f"- Feature flag. `{c['feature_flag']}` gates the new behaviour. Off by default until the release. With the flag off, nothing existing changes.")
    if c.get("test_command"):
        lines.append(f"- Tests. Run `{c['test_command']}`. New suites accompany each work item.")
    if c.get("lint_command"):
        lines.append(f"- Lint and format. `{c['lint_command']}` passes on every pull request.")
    for extra in c.get("extra") or []:
        lines.append(f"- {extra}")
    lines.append("- Documentation style in this folder. Sentence-case headings, short sentences, no em dashes or en dashes, no names of people. Owners and dates live in the GitHub issues.")
    lines.append("- Existing behaviour is not changed by a work item unless its file says so.")
    return "\n".join(lines)


def schedule_table(plan):
    rows = []
    entries = []
    for m in plan["milestones"]:
        entries.append((m["start"], f"{m['number']}, {m['name']}", f"{m['start']} to {m['end']}", m["gate"]))
    for br in plan["breaks"]:
        entries.append((br["start"], br["name"], f"{br['start']} to {br['end']}", "None committed."))
    for _, a, b, c in sorted(entries):
        rows.append([a, b, c])
    return md_table(["Work unit", "Dates", "Gate"], rows)


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


def program_section(plan):
    items = plan["program"]["items"]
    if not items:
        return ""
    rows = [[L.tag(plan, p["id"]), p["label"], p.get("note", "")] for p in items]
    return (
        "## Program-owned items\n\n"
        "Some items depend on inputs the program provides outside this plan, such as pilot teams, approvals and reviews. "
        "Those are marked \"program input\" in the item files. Their ids are left as gaps in the numbering on purpose. "
        "They are tracked by the program, not as issues in this plan.\n\n"
        + md_table(["Id", "Program item", "Note"], rows) + "\n\n"
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
        "program_section": program_section(plan),
        "index": index_text(plan),
    }
    return L.fill(L.read_template("spec-README.md"), vals)


def build_milestone(plan, ms):
    its = [L.tag(plan, it["id"]) for it in plan["items"] if it["milestone"] == ms["number"]]
    vals = {
        "number": ms["number"], "name": ms["name"], "project_name": plan["project"]["name"],
        "start": ms["start"], "end": ms["end"], "folder": ms["folder"], "gate": ms["gate"],
        "demo": ms["demo"], "ids": ", ".join(its),
        "work_table": work_table(plan, ms),
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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scaffold the specification folder from plan.yaml. Dry run unless --apply is given.",
        epilog="Existing files are never overwritten unless --force is given. --refresh-headers touches only header tables.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--init", action="store_true", help="write a starter plan.yaml from the annotated template and stop")
    ap.add_argument("--name", help="project name for --init")
    ap.add_argument("--stubs", action="store_true", help="also write one stub specification per work item")
    ap.add_argument("--refresh-headers", action="store_true", help="rewrite header tables of existing specs and milestone files to match plan.yaml")
    ap.add_argument("--ci", action="store_true", help="also write .github/workflows/check-specs.yml and copy the checker to tools/carrydown/ so the checker runs in continuous integration")
    ap.add_argument("--force", action="store_true", help="overwrite existing files (README, milestone.md, stubs)")
    ap.add_argument("--apply", action="store_true", help="write files. Without it this is a dry run")
    ap.add_argument("--allow-no-git", action="store_true", help="write even when the project folder is not inside a git repository (not recommended)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    actions = []
    if a.apply and not a.allow_no_git and not any((d / ".git").exists() for d in [root, *root.parents]):
        print(f"error: {root} is not inside a git repository, so nothing was written.\n"
              "The plan, the specifications and every later change belong in git, so that each change is reviewed and can be undone.\n"
              "Run `git init` in the project folder (or ask your agent to), then run this command again.", file=sys.stderr)
        return 2

    if a.init:
        target = L.find_plan(root, a.plan)
        if not a.plan:
            target = root / "docs/spec/plan.yaml"
        text = L.read_template("plan.yaml")
        if a.name:
            text = text.replace('name: "Your project name"', f'name: "{a.name}"')
            text = text.replace('project_title: "Your project plan"', f'project_title: "{a.name} plan"')
            text = text.replace('epic_title: "Your project, development plan"', f'epic_title: "{a.name}, development plan"')
        if target.exists() and not a.force:
            print(f"plan.yaml already exists at {target}. Use --force to replace it.")
            return 1
        print(f"{'writing' if a.apply else 'would write'} {target.relative_to(root)}")
        if a.apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print("Fill in plan.yaml, then run this script again without --init.")
        return 0

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
    spec_dir = root / plan["project"]["spec_dir"]

    def plan_write(path, content, kind):
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
            (spec_dir / ms["folder"]).mkdir(parents=True, exist_ok=True)
    if a.ci:
        gt_dir = str(Path(plan["project"]["ground_truth"]).parent)
        wf = L.fill(L.read_template("check-specs-workflow.yml"), {"spec_dir": plan["project"]["spec_dir"], "ground_truth_dir": gt_dir, "branch": plan["project"]["branch"]})
        plan_write(root / ".github/workflows/check-specs.yml", wf, "ci workflow")
        for name in ("check_specs.py", "carrydown_lib.py"):
            plan_write(root / "tools/carrydown" / name, (Path(__file__).resolve().parent / name).read_text(encoding="utf-8"), "checker copy")
    if a.refresh_headers:
        for it in plan["items"]:
            p = L.spec_path(plan, root, it)
            if p.exists():
                old = p.read_text(encoding="utf-8")
                new = replace_first_table(old, L.header_markdown(plan, it))
                if new != old:
                    actions.append(("refresh header", p, "spec"))
                    if a.apply:
                        p.write_text(new, encoding="utf-8")
        for ms in plan["milestones"]:
            p = L.milestone_path(plan, root, ms)
            if p.exists():
                old = p.read_text(encoding="utf-8")
                its = ", ".join(L.tag(plan, it["id"]) for it in plan["items"] if it["milestone"] == ms["number"])
                table = "\n".join([
                    "| | |", "| --- | --- |", f"| Due | {ms['end']} |", f"| Exit gate | {ms['gate']} |", f"| Work items | {its} |",
                    f"| Demonstration | {ms['demo']}, both people, in a meeting session with the program. |",
                ])
                new = replace_section_table(replace_first_table(old, table), "Work items", work_table(plan, ms))
                if new != old:
                    actions.append(("refresh header", p, "milestone"))
                    if a.apply:
                        p.write_text(new, encoding="utf-8")
    verb = "" if a.apply else "would "
    for what, path, kind in actions:
        print(f"{verb}{what}: {path.relative_to(root)}  [{kind}]")
    created = sum(1 for w, _, _ in actions if w in ("create", "overwrite"))
    print(f"{len(actions)} action(s), {created} file(s) {'written' if a.apply else 'would be written'}." + ("" if a.apply else " Dry run. Add --apply to write."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
