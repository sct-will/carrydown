#!/usr/bin/env python3
"""Check the work item specifications against plan.yaml. Read only.

Checks, per work item
  the file exists at <spec_dir>/<milestone folder>/<id>-<slug>.md
  the title line is "# <ID> <label>"
  the header table carries the values the plan implies (milestone, track, target,
  checkpoint right after target, demonstration, size, depends on, unblocks, ground truth)
  the sections appear in the template order
  "Evidence of completion" and "Integration points" are present and not empty
  the file is within the length bounds
  banned vocabulary (dashes, people named in the plan, AI vendor names, sprint words,
  "open questions", "non-goals"; the lists are in plan.yaml under banned)
  no reference to a program-owned id, no reference to an unknown id
  no broken relative link
  ground truth sections cited in the header exist in the rendered document
Per milestone: milestone.md exists with the required parts and lists every item.
Per project: README.md in the spec folder lists every item.

Also checks the plan itself: dates, owners, dependencies, cycles, weekends, days off, breaks, the
percent allocation of each person (1 to 100), that nobody is over 100 percent of their allocated
capacity in a work unit, and, when a target exists, that the last work item meets it. People and the
target are optional. Without a target the report prints the critical path end date as derived.

Usage
  python3 scripts/check_specs.py --root .            check everything
  python3 scripts/check_specs.py --root . --report   print the schedule, load table and critical path
  python3 scripts/check_specs.py --root . --item 3   check one item
Exit status is 0 when clean and 1 when there are findings. The script never writes files.
"""
import argparse
import contextlib
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402

MILESTONE_PARTS = ["Purpose", "Expected outcomes", "Acceptance criteria", "Demonstration expectations", "Work items"]


def strip_code(text):
    return re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def banned_patterns(plan):
    b = plan["banned"]
    pats = []
    if b.get("dashes", True):
        pats.append((re.compile("[" + chr(0x2014) + chr(0x2013) + "]"), "em or en dash"))
    if plan["_banned_names"]:
        alt = "|".join(re.escape(n) for n in plan["_banned_names"])
        pats.append((re.compile(r"(?i)(?<![\w-])(" + alt + r")(?![\w-])"), "person name or handle from the plan"))
    if plan.get("_banned_exact"):
        alt = "|".join(re.escape(n) for n in plan["_banned_exact"])
        pats.append((re.compile(r"(?<![\w-])(" + alt + r")(?![\w-])"), "person name or handle from the plan"))
    for key, why in (("vendors", "AI vendor or model reference"), ("words", "banned word"), ("phrases", "banned phrase")):
        pats_list = b.get(key) or []
        if pats_list:
            pats.append((re.compile(r"(?i)(?:" + "|".join(f"\\b(?:{p})\\b" if not p.startswith("\\b") else p for p in pats_list) + ")"), why))
    return pats


def ground_truth_headings(plan, root):
    p = Path(root) / plan["project"].get("ground_truth", "")
    if not p.is_file():
        return None
    heads = []
    fence = False
    for line in L.read_text(p).split("\n"):
        if line.strip().startswith("```"):
            fence = not fence
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            heads.append(m.group(2).strip())
    return heads


def numbered_headings(gt_heads):
    return [h for h in (gt_heads or []) if re.match(r"^\d+(\.\d+)*\.?\s", h)]


def citation_findings(plan, gt_heads):
    """Say when the section citations could not be checked, instead of passing silently."""
    if not plan["items"]:
        return []
    if gt_heads is None:
        return [f"ground truth citations not checked: the rendered document {plan['project'].get('ground_truth')} was not found. Render it with render_ground_truth.py"]
    if not numbered_headings(gt_heads):
        return ["ground truth citations not checked: the rendered document has no numbered headings. "
                "Specifications cite sections by number, so number the headings in the source document and render it again"]
    return []


def check_item(plan, root, it, banned, gt_heads):
    issues = []
    path = L.spec_path(plan, root, it)
    tg = L.tag(plan, it["id"])
    rel = path.relative_to(root) if path.is_relative_to(root) else path
    if not path.exists():
        return [f"MISSING {rel}"], rel
    spec = L.read_spec(path)
    text, lines, rows = spec["text"], spec["lines"], spec["rows"]
    expected_title = f"# {tg} {it['label']}"
    if spec["title"] != expected_title:
        issues.append(f"title is {spec['title']!r}, expected {expected_title!r}")
    exp = L.expected_header(plan, it)
    for name, val in exp:
        got = rows.get(name)
        if got is None:
            issues.append(f"header lacks the {name} row")
            continue
        if name == "Depends on":
            for d in it["depends"]:
                if L.tag(plan, d) not in got:
                    issues.append(f"Depends on lacks {L.tag(plan, d)} (row: {got!r})")
            if it["program_input"] and "program input" not in got.lower():
                issues.append(f"Depends on lacks the program input note (row: {got!r})")
            if not it["program_input"] and "program input" in got.lower():
                issues.append(f"Depends on has a program input note the plan does not (row: {got!r})")
            if not it["depends"] and not it["program_input"] and got.strip().lower() not in ("none", "none."):
                issues.append(f"Depends on should say None (row: {got!r})")
        elif name == "Unblocks":
            for u in it["unblocks"]:
                if L.tag(plan, u) not in got:
                    issues.append(f"Unblocks lacks {L.tag(plan, u)} (row: {got!r})")
            extra = set(re.findall(rf"{re.escape(plan['project']['id_prefix'])}-\d+", got)) - {L.tag(plan, u) for u in it["unblocks"]}
            if extra:
                issues.append(f"Unblocks names items the plan does not: {sorted(extra)}")
        elif name in ("Size", "Ground truth"):
            if not got.strip() or "to be " in got.lower():
                issues.append(f"{name} row is not filled in (row: {got!r})")
        elif got != val:
            issues.append(f"{name} row is {got!r}, expected {val!r}")
    order = spec["row_order"]
    if "Target" in order and "Checkpoint" in order and order.index("Checkpoint") != order.index("Target") + 1:
        issues.append("Checkpoint row is not directly after Target")
    # sections in order
    pos = -1
    for sec in L.SECTIONS:
        cands = sec if isinstance(sec, tuple) else (sec,)
        found = [text.find("\n## " + c + "\n") for c in cands]
        found = [f for f in found if f >= 0]
        if not found:
            issues.append("section missing: " + " or ".join(cands))
            continue
        f = min(found)
        if f < pos:
            issues.append(f"section out of order: {cands[0]}")
        pos = f
    # evidence and integration
    for sec in ("Evidence of completion", "Integration points"):
        body = L.section_text(spec, sec)
        if body:
            n_body = len([l for l in body.split("\n") if l.strip()])
            if n_body < 4:
                issues.append(f"{sec} is too short ({n_body} non-empty lines)")
            if sec == "Evidence of completion" and L.EVIDENCE_LEAD not in body:
                issues.append(f"Evidence of completion lacks the {L.EVIDENCE_LEAD} lead")
            if sec == "Integration points":
                for lead in L.INTEGRATION_LEADS:
                    if lead not in body:
                        issues.append(f"Integration points lacks {lead}")
    for sec in ("Acceptance criteria",):
        body = L.section_text(spec, sec)
        if body and not re.search(r"(?m)^- \[ \] ", body):
            issues.append("Acceptance criteria has no checkbox items (- [ ] ...)")
    for m in re.finditer(r"\bTODO\b", strip_code(text)):
        issues.append(f"unfinished template text (TODO) at line {text.count(chr(10), 0, m.start()) + 1}")
        break
    tail = text.split("## Decisions recorded")[-1]
    if "None yet." not in tail and not re.search(r"(?m)^- \d{4}-\d\d-\d\d\.", tail):
        issues.append("Decisions recorded has neither 'None yet.' nor a dated entry")
    lo, hi = plan["limits"]["spec_lines"]
    n = len([l for l in lines])
    if n < lo or n > hi:
        issues.append(f"length {n} lines is outside {lo} to {hi}")
    scan_text = strip_code(text) if plan["banned"].get("skip_code_blocks") else text
    for pat, why in banned:
        for m in pat.finditer(scan_text):
            ln = scan_text.count("\n", 0, m.start()) + 1
            issues.append(f"{why} at line {ln}: {lines[ln - 1].strip()[:90]}")
    prefix = re.escape(plan["project"]["id_prefix"])
    pids = L.program_ids(plan)
    known = {it2["id"] for it2 in plan["items"]}
    for m in re.finditer(rf"\b{prefix}-(\d+)\b", text):
        num = int(m.group(1))
        ln = text.count("\n", 0, m.start()) + 1
        if num in pids:
            issues.append(f"reference to program id {m.group(0)} at line {ln}")
        elif num not in known:
            issues.append(f"reference to unknown id {m.group(0)} at line {ln}")
    prose = strip_code(text)
    for m in re.finditer(r"\]\(((?!https?://|mailto:|#)[^)\s]+)(?:\s+\"[^\"]*\")?\)", prose):
        target = m.group(1).split("#")[0]
        if target and not (path.parent / target).resolve().exists():
            issues.append(f"broken relative link {m.group(1)}")
    # ground truth citations
    cite = rows.get("Ground truth", "")
    numbered = numbered_headings(gt_heads)
    if numbered and cite and "to be " not in cite.lower():
        for num in re.findall(r"\b(\d+(?:\.\d+)*)\b", cite):
            if not any(h.startswith(num + " ") or h.startswith(num + ". ") for h in numbered):
                issues.append(f"Ground truth cites section {num}, which is not a heading in the rendered document")
    return issues, rel


def check_milestone(plan, root, ms):
    issues = []
    path = L.milestone_path(plan, root, ms)
    rel = path.relative_to(root) if path.is_relative_to(root) else path
    if not path.exists():
        return [f"MISSING {rel}"], rel
    text = L.read_text(path)
    first = text.split("\n", 1)[0].strip()
    expected = f"# Milestone {ms['number']}, {ms['name']}"
    if first != expected:
        issues.append(f"title is {first!r}, expected {expected!r}")
    spec = L.read_spec(path)
    for part in MILESTONE_PARTS:
        if part not in spec["sections"]:
            issues.append(f"section missing: {part}")
    for row, want in (("Due", ms["end"]), ("Exit gate", ms["gate"])):
        got = spec["rows"].get(row)
        if got is None:
            issues.append(f"header lacks the {row} row")
        elif got != want:
            issues.append(f"{row} row is {got!r}, expected {want!r}")
    demo = spec["rows"].get("Demonstration")
    if demo is None:
        issues.append("header lacks the Demonstration row")
    elif ms["demo"] not in demo:
        issues.append(f"Demonstration row does not carry the date {ms['demo']}")
    if re.search(r"\bTODO\b", text):
        issues.append("unfinished template text (TODO)")
    crit = L.section_text(spec, "Acceptance criteria")
    if len(re.findall(r"(?m)^- \[ \] ", crit)) < 3:
        issues.append("Acceptance criteria needs at least three checkbox items")
    outc = L.section_text(spec, "Expected outcomes")
    if len([l for l in outc.split("\n") if l.strip().startswith("- ")]) < 2:
        issues.append("Expected outcomes needs at least two bullet items")
    work = L.section_text(spec, "Work items")
    for it in plan["items"]:
        if it["milestone"] == ms["number"] and L.tag(plan, it["id"]) not in work:
            issues.append(f"Work items table lacks {L.tag(plan, it['id'])}")
    for m in re.finditer(rf"\b{re.escape(plan['project']['id_prefix'])}-(\d+)\b", text):
        if int(m.group(1)) in L.program_ids(plan):
            issues.append(f"reference to program id {m.group(0)}")
    for pat, why in banned_patterns(plan):
        for m in pat.finditer(text):
            ln = text.count("\n", 0, m.start()) + 1
            issues.append(f"{why} at line {ln}: {text.split(chr(10))[ln - 1].strip()[:90]}")
    for m in re.finditer(r"\]\(((?!https?://|mailto:|#)[^)\s]+)\)", strip_code(text)):
        if not (path.parent / m.group(1).split("#")[0]).resolve().exists():
            issues.append(f"broken relative link {m.group(1)}")
    return issues, rel


def check_readme(plan, root):
    issues = []
    path = Path(root) / plan["project"]["spec_dir"] / "README.md"
    rel = path.relative_to(root) if path.is_relative_to(root) else path
    if not path.exists():
        return [f"MISSING {rel}"], rel
    text = L.read_text(path)
    for it in plan["items"]:
        if L.tag(plan, it["id"]).lower() not in text.lower():
            issues.append(f"index lacks {L.tag(plan, it['id'])}")
    for h in ("Closing comment on an issue", "Checkpoint comment on the Epic", "Index"):
        if f"## {h}" not in text and f"### {h}" not in text:
            issues.append(f"section missing: {h}")
    for pat, why in banned_patterns(plan):
        for m in pat.finditer(text):
            ln = text.count("\n", 0, m.start()) + 1
            issues.append(f"{why} at line {ln}: {text.split(chr(10))[ln - 1].strip()[:90]}")
    return issues, rel


def orphan_files(plan, root):
    known = {L.spec_path(plan, root, it).resolve() for it in plan["items"]}
    out = []
    for ms in plan["milestones"]:
        folder = Path(root) / plan["project"]["spec_dir"] / ms["folder"]
        if folder.is_dir():
            for f in sorted(folder.glob("*.md")):
                if f.name != "milestone.md" and f.resolve() not in known:
                    out.append(str(f.relative_to(root)))
    return out


def fmt(d):
    return L.fmt_date(d)


def report(plan):
    people = {p["id"]: p for p in plan["people"]}
    print(f"Plan: {plan['project']['name']}")
    ds = L.derived_summary(plan)
    if ds:
        print(f"Derived inputs: {ds}. Replace the placeholders when you know the real values.")
    print("\nSchedule")
    for m in plan["milestones"]:
        print(f"  Work unit {m['number']}, {m['name']}: {m['start']} to {m['end']} (demonstration {m['demo']})")
    for br in plan["breaks"]:
        print(f"  Break, {br['name']}: {br['start']} to {br['end']}")
    print("\nLoad (sized days of work against allocated capacity, per person and work unit)")
    if not people:
        print("  No people in the plan yet. Add them under `people`, or let the planning step propose a team marked derived.")
    print("  Capacity is the working days a person has in the work unit, minus days off, times their percent allocation.")
    head = ["Person", "Alloc"] + [f"WU{m['number']}" for m in plan["milestones"]] + ["Total"]
    rows = []
    over = []
    by_person = {}
    for pid, mnum, sized, cap, pct in L.load_rows(plan):
        by_person.setdefault(pid, []).append((mnum, sized, cap, pct))
    for pid, p in people.items():
        cells, tot_sized, tot_cap = [], 0.0, 0.0
        for mnum, sized, cap, pct in by_person.get(pid, []):
            if sized == 0:
                cells.append(f"0 of {cap:.0f}d")
            else:
                flag = "  OVER" if (pct is not None and pct > 100) else ""
                cells.append(f"{sized:g} of {cap:.0f}d ({pct:.0f}%){flag}" if pct not in (None, float("inf")) else f"{sized:g} of 0d (no capacity){flag or '  OVER'}")
                if pct is None or pct > 100:
                    over.append((pid, mnum, sized, cap, pct))
            tot_sized += sized
            tot_cap += cap
        tot = f"{tot_sized:g} of {tot_cap:.0f}d" + (f" ({100 * tot_sized / tot_cap:.0f}%)" if tot_cap else "")
        rows.append([pid, f"{p.get('allocation', 100)}%"] + cells + [tot])
    widths = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(head, widths)))
    for r in rows:
        print("  " + "  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    if over:
        print("  Over 100 percent of allocated capacity:")
        for pid, mnum, sized, cap, pct in over:
            print(f"    {pid} in work unit {mnum}: {sized:g} sized days against {cap:.1f} allocated days" + (f" ({pct:.0f}%)" if pct not in (None, float("inf")) else ""))
    else:
        print("  No person is over 100 percent of allocated capacity in any work unit.")
    # critical path: longest chain by calendar days between completions
    items = L.item_by_id(plan)
    best = {}

    def longest(n):
        if n in best:
            return best[n]
        it = items[n]
        done = L.parse_date(it["complete_by"])
        ms = L.milestone_by_num(plan)[it["milestone"]]
        start = L.parse_date(ms["start"])
        cand = (max((done - start).days, 0), [n])
        for d in it["depends"]:
            if d in items:
                dd, path = longest(d)
                gap = (done - L.parse_date(items[d]["complete_by"])).days
                if dd + gap > cand[0]:
                    cand = (dd + gap, path + [n])
        best[n] = cand
        return cand

    if items:
        end = max(items, key=lambda n: (L.parse_date(items[n]["complete_by"]), longest(n)[0]))
        days, path = longest(end)
        print("\nCritical path (longest dependency chain to the last item)")
        print("  " + " -> ".join(L.tag(plan, n) for n in path) + f"  ({days} calendar days)")
        for n in path:
            print(f"    {L.tag(plan, n)} {items[n]['label']}, by {items[n]['complete_by']}, {people.get(items[n]['owner'], {}).get('id', items[n]['owner'])}")
        tdate, ttext = L.target_date(plan)
        end_date = L.parse_date(items[path[-1]]["complete_by"])
        print("\nTarget")
        if tdate and L.target_is_constraint(plan):
            gap = (tdate - end_date).days
            verdict = f"meets the target with {gap} day(s) to spare" if gap >= 0 else f"misses the target by {-gap} day(s)"
            print(f"  Target: {ttext}")
            print(f"  The critical path ends {fmt(end_date)}: it {verdict}.")
        else:
            why = "The target in plan.yaml is marked derived" if tdate else "There is no target in plan.yaml"
            print(f"  Critical path ends {fmt(end_date)} (derived from the critical path). {why}, so this is the derived target: the plan's end date, not a constraint.")
            if tdate and tdate != end_date:
                print(f"  The derived target in plan.yaml says {fmt(tdate)}. Update it to {fmt(end_date)}.")
    pitems = plan["program"]["items"]
    if pitems:
        print("\nProgram-owned items (outside the development plan; referenced only as program input)")
        for pi in pitems:
            print(f"  {L.tag(plan, pi['id'])} {pi['label']}")
    print("\nCheckpoints")
    for c in plan["checkpoints"]:
        due = [L.tag(plan, it["id"]) for it in plan["items"] if it["checkpoint"] == c["date"]]
        print(f"  {c['date']}  {c['name']}: {', '.join(due) or 'none closing'}")


PLAN_ERRORS = (KeyError, ValueError, TypeError, AttributeError, IndexError)


def print_plan_problems(problems):
    print("plan.yaml has problems:")
    for p in problems:
        print("  - " + p)


def collapse_unfinished(issues):
    """A file that still holds template text gets one line, not one per unfilled row."""
    todo = [i for i in issues if i.startswith("unfinished template text (TODO)")]
    if not todo or len(issues) == 1:
        return issues, bool(todo)
    others = len(issues) - 1
    return [f"{todo[0]}, and {others} other finding(s) that usually go when the template text is replaced"], True


def run_checks(plan, root, a):
    results = {}
    ok = 0
    unfinished = 0
    load_issues = []
    for pid, mnum, sized, cap, pct in L.load_rows(plan):
        if pct is not None and pct > 100:
            load_issues.append(f"{pid} is over 100 percent of allocated capacity in work unit {mnum}: {sized:g} sized days against {cap:.1f} allocated days")
    tdate, _ = L.target_date(plan)
    if tdate and plan["items"]:
        last = max(L.parse_date(it["complete_by"]) for it in plan["items"])
        if L.target_is_constraint(plan) and last > tdate:
            load_issues.append(f"the last work item completes {L.fmt_date(last)}, after the target {L.fmt_date(tdate)}")
        if not L.target_is_constraint(plan) and last != tdate:
            load_issues.append(f"the derived target {L.fmt_date(tdate)} is out of date. The last work item completes {L.fmt_date(last)}, so write that date under target")
    banned = banned_patterns(plan)
    gt_heads = ground_truth_headings(plan, root)
    if load_issues:
        results["load and target"] = load_issues
    cites = citation_findings(plan, gt_heads)
    if cites and not a.item:
        results["ground truth"] = cites
    items = [it for it in plan["items"] if not a.item or it["id"] in a.item]
    for it in items:
        issues, rel = check_item(plan, root, it, banned, gt_heads)
        issues, todo = collapse_unfinished(issues)
        unfinished += todo
        if issues:
            results[f"{L.tag(plan, it['id'])} {rel}"] = issues
        else:
            ok += 1
    if not a.item:
        for ms in plan["milestones"]:
            issues, rel = check_milestone(plan, root, ms)
            issues, todo = collapse_unfinished(issues)
            unfinished += todo
            if issues:
                results[f"milestone {ms['number']} {rel}"] = issues
            else:
                ok += 1
        issues, rel = check_readme(plan, root)
        if issues:
            results[str(rel)] = issues
        else:
            ok += 1
        orphans = orphan_files(plan, root)
        if orphans:
            results["orphan files"] = [f"{o} is not in plan.yaml" for o in orphans]
    n_files = len(items) + (0 if a.item else len(plan["milestones"]) + 1)
    return results, ok, n_files, len(items), unfinished


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check work item specifications against plan.yaml. Read only: this script never writes files.",
        epilog="Exit status 0 when clean, 1 when there are findings, 2 on a usage or plan error.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--item", type=int, action="append", help="check only this item id (repeatable)")
    ap.add_argument("--report", action="store_true", help="print the schedule, load table and critical path, then exit")
    ap.add_argument("--json", action="store_true", help="print the findings as JSON")
    ap.add_argument("--quiet", action="store_true", help="print only the summary line")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    plan_path = L.find_plan(root, a.plan)
    if not plan_path.exists():
        print(f"error: plan not found at {plan_path}. Run from the project root or pass --root; "
              "write a first plan with scaffold_spec.py --init", file=sys.stderr)
        return 2
    plan, plan_problems = L.load_plan(plan_path)
    if a.report:
        # plan problems first: the report is only as good as the plan it reads
        if plan_problems:
            print_plan_problems(plan_problems)
            print()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                report(plan)
        except PLAN_ERRORS:
            if not plan_problems:
                raise
            print("The report needs the problems above fixed first.")
            return 1
        sys.stdout.write(buf.getvalue())
        return 1 if plan_problems else 0
    try:
        results, ok, n_files, n_items, unfinished = run_checks(plan, root, a)
    except PLAN_ERRORS:
        if not plan_problems:
            raise
        if a.json:
            print(json.dumps({"clean": 0, "files": 0, "findings": {"plan.yaml": plan_problems}}, indent=2))
        else:
            print_plan_problems(plan_problems)
            print("The specifications were not checked: fix plan.yaml first.")
        return 1
    if plan_problems:
        results = {"plan.yaml": plan_problems, **results}
    if a.json:
        print(json.dumps({"clean": ok, "files": n_files, "findings": results}, indent=2))
    else:
        print(f"{ok} files clean, {len(results)} with findings ({n_items} work items, {0 if a.item else len(plan['milestones'])} milestones)")
        if plan_problems:
            print(f"plan.yaml: {len(plan_problems)} problem(s), listed first.")
        if unfinished:
            print(f"{unfinished} file(s) still hold template text (TODO). That is expected until the specifications are written.")
        if L.derived_summary(plan):
            print(f"Derived inputs: {L.derived_summary(plan)}.")
        if not a.quiet:
            for k, v in results.items():
                print(f"{k}:")
                for i in v:
                    print("  - " + i)
    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main())
