#!/usr/bin/env python3
"""Preview identity and provenance repairs. Write the canonical plan only with --apply."""
import argparse
import copy
import difflib
import json
import re
import sys
from pathlib import Path

import carrydown_lib as L


def dump(value, indent=0):
    """Emit the repository's portable YAML subset without an optional dependency."""
    pad = " " * indent
    lines = []
    if isinstance(value, dict):
        for key, val in value.items():
            if isinstance(val, (dict, list)) and val:
                lines.append(pad + str(key) + ":\n" + dump(val, indent + 2))
            else:
                lines.append(pad + str(key) + ": " + json.dumps(val, ensure_ascii=False))
    elif isinstance(value, list):
        for val in value:
            if isinstance(val, dict) and val:
                block = dump(val, indent + 2).splitlines()
                lines.append(pad + "- " + block[0][indent + 2:])
                lines.extend(block[1:])
            else:
                lines.append(pad + "- " + json.dumps(val, ensure_ascii=False))
    return "\n".join(lines)


def unique(base, used):
    stem = L.slugify(str(base)) or "identity"
    candidate, n = stem, 2
    while candidate in used:
        candidate, n = f"{stem}-{n}", n + 1
    used.add(candidate)
    return candidate


def recover(raw, root, decisions=None):
    """Return proposed data, complete actions and concrete unresolved choices. Never writes."""
    plan, actions, questions = copy.deepcopy(raw), [], []
    decisions = decisions or {}
    if "external" not in plan and "program" in plan:
        plan["external"] = plan.pop("program")
        actions.append("program: preserve legacy external items under external")

    def choose(path, options, explanation):
        if path in decisions and decisions[path] in options:
            actions.append(f"{path}: confirmed {decisions[path]!r}")
            return decisions[path]
        questions.append({"path": path, "question": explanation, "options": options})
        return None

    groups = [(key, plan.setdefault(key, [])) for key in ("tracks", "people", "checkpoints")]
    groups.append(("external.items", plan.setdefault("external", {}).setdefault("items", [])))
    for key, rows in groups:
        kept = []
        for i, row in enumerate(rows):
            if row in kept:
                actions.append(f"{key}[{i}]: collapse exactly identical record {row!r}")
            else:
                kept.append(row)
        rows[:] = kept

    # Preserve every work-item ID and reserve every existing external ID.
    used = {i.get("id") for i in plan.get("items", []) + plan["external"]["items"] if isinstance(i.get("id"), int)}
    seen = {i.get("id") for i in plan.get("items", [])}
    for i, row in enumerate(plan["external"]["items"]):
        if row.get("id") in seen:
            old = row["id"]
            new = max(used or {0}) + 1
            used.add(new)
            row["id"] = new
            actions.append(f"external.items[{i}].id: {old!r} -> {new}; work-item IDs preserved")
            # External references are prose. Only exact unique labels establish identity.
            for it in plan.get("items", []):
                text = it.get("external_input", "")
                if text and re.search(r"\b" + re.escape(str(old)) + r"\b", text):
                    if row.get("label") and row["label"] in text:
                        it["external_input"] = re.sub(r"\b" + re.escape(str(old)) + r"\b", str(new), text)
                        actions.append(f"items[{it['id']}].external_input: {text!r} -> {it['external_input']!r}")
                    else:
                        selected = choose(f"items.{it['id']}.external_input", [text, re.sub(r"\b" + re.escape(str(old)) + r"\b", str(new), text)], "Which external item does this text reference?")
                        if selected is not None:
                            it["external_input"] = selected
        seen.add(row.get("id"))

    # Resolve track identity before person identity so track evidence remains usable.
    for group, name in (("tracks", "label"), ("people", "name")):
        rows = plan[group]
        buckets = {}
        for row in rows:
            buckets.setdefault(row.get("id"), []).append(row)
        used = {row.get("id") for row in rows}
        for old, candidates in buckets.items():
            if len(candidates) < 2:
                continue
            for row in candidates:
                row["id"] = unique(row.get(name, group), used)
                actions.append(f"{group}: {old!r} -> {row['id']!r} for {row.get(name)!r}")
            refs = [(f"items.{it.get('id')}.{ 'track' if group == 'tracks' else 'owner'}", it,
                     "track" if group == "tracks" else "owner") for it in plan.get("items", [])]
            if group == "tracks":
                refs += [(f"people.{p.get('id')}.track", p, "track") for p in plan["people"]]
            for path, ref, key in refs:
                if ref.get(key) != old:
                    continue
                matches = []
                if group == "people":
                    matches = [p for p in candidates if p.get("track") == ref.get("track")]
                else:
                    explicit = ref.get("track_label")
                    matches = [t for t in candidates if explicit and t.get("label") == explicit]
                    if not matches and key == "track" and ref in plan.get("items", []):
                        owners = [p for p in plan["people"] if p.get("id") == ref.get("owner")]
                        if len(owners) == 1:
                            matches = [t for t in candidates if owners[0].get("track_label") == t.get("label")]
                val = matches[0]["id"] if len(matches) == 1 else choose(path, [r["id"] for r in candidates], f"Which {group[:-1]} does {path} reference?")
                actions.append(f"{path}: {old!r} -> {val!r}; candidates {[r['id'] for r in candidates]}")
                if val:
                    ref[key] = val
    labels = {}
    for row in plan["tracks"]:
        labels.setdefault(str(row.get("label", "")).casefold(), []).append(row)
    used_labels = {str(t.get("label", "")).casefold() for t in plan["tracks"]}
    for rows in labels.values():
        if len(rows) > 1:
            for row in rows:
                old = row["label"]
                base = f"{old} ({row['id']})"
                candidate, suffix = base, 2
                while candidate.casefold() in used_labels:
                    candidate, suffix = f"{base} {suffix}", suffix + 1
                row["label"] = candidate
                used_labels.add(candidate.casefold())
                actions.append(f"tracks.{row['id']}.label: {old!r} -> {row['label']!r}")
    checkpoints = {}
    for row in plan["checkpoints"]:
        checkpoints.setdefault(row.get("date"), []).append(row)
    for date, rows in checkpoints.items():
        if len(rows) > 1:
            combined = {"date": date, "name": "; ".join(r["name"] for r in rows),
                        "joint_check": "\n".join(r.get("joint_check", "") for r in rows)}
            # Extra properties cannot be discarded by a merge.
            if any(set(r) - set(combined) for r in rows):
                choose(f"checkpoints.{date}", [rows], "Combine these checkpoints manually while preserving all properties")
            elif choose(f"checkpoints.{date}", [combined], "Confirm the combined checkpoint on the same date"):
                merged = []
                for row in plan["checkpoints"]:
                    if row not in rows:
                        merged.append(row)
                    elif not any(r.get("date") == date for r in merged):
                        merged.append(combined)
                plan["checkpoints"] = merged
                actions.append(f"checkpoints.{date}: {rows!r} -> {combined!r}; affected item checkpoint references keep the same date")

    sources = plan.get("sources") or L.ground_truth_sources(plan)
    reviewed = [s for s in sources if s.get("status", "reviewed") == "reviewed"]
    source_map = {s.get("id"): s for s in reviewed}
    for it in plan.get("items", []):
        path = f"items.{it['id']}.source_refs"
        refs = it.get("source_refs") or []
        if not refs:
            cite = it.get("ground_truth") or ""
            if not cite:
                try:
                    # A specification can supply evidence, but never substitutes for plan data.
                    normalized, _ = L.load_plan(Path(root) / "docs/spec/plan.yaml", root)
                    cite = L.read_spec(L.spec_path(normalized, root, it))["rows"].get("Ground truth", "")
                except (SystemExit, OSError, ValueError, KeyError):
                    cite = ""
            matches = [s for s in reviewed if any(str(v).casefold() in cite.casefold() for v in (s.get("id"), s.get("name"), s.get("path")) if v)]
            if not matches and it.get("ground_truth"):
                matches = [s for s in reviewed if s.get("path") == plan["project"].get("ground_truth")]
            sections = L.explicit_sections(cite)
            if len(matches) == 1 and sections:
                source = matches[0]
                try:
                    headings = L.collect_headings(L.read_text(Path(root) / source["path"]).splitlines())
                    known = {re.match(r"(\d+(?:\.\d+)*)\b", h[2]).group(1) for h in headings if re.match(r"(\d+(?:\.\d+)*)\b", h[2])}
                except (SystemExit, OSError):
                    known = set()
                if set(sections) <= known:
                    refs = [{"source": source["id"], "sections": ", ".join(dict.fromkeys(sections))}]
            if not refs:
                options = [[{"source": s["id"], "sections": "whole document"}] for s in reviewed]
                refs = choose(path, options, "Which reviewed source and coverage apply? Whole-document coverage requires plan-owner confirmation; provide explicit sections in the plan when available")
        elif any(r.get("source") not in source_map or not str(r.get("sections", "")).strip() or
                 (str(r.get("sections", "")).strip().casefold() != "whole document" and
                  not re.search(r"\b\d+(?:\.\d+)*\b", r.get("sections", ""))) for r in refs):
            refs = choose(path, [[{"source": s["id"], "sections": "whole document"}] for s in reviewed], "Replace unknown, unreadable or empty references with confirmed source coverage")
        else:
            merged = {}
            for ref in refs:
                merged.setdefault(ref["source"], [])
                if ref["sections"] not in merged[ref["source"]]:
                    merged[ref["source"]].append(ref["sections"])
            refs = [{"source": sid, "sections": ", ".join(vals)} for sid, vals in merged.items()]
        if refs and refs != it.get("source_refs"):
            if not plan.get("sources"):
                plan["sources"] = copy.deepcopy(sources)
                actions.append("sources: persist the explicitly configured legacy primary source")
            it["source_refs"] = refs
            actions.append(f"{path}: {refs!r}; refresh specification header and generated material after canonical plan")
    return plan, actions, questions


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--plan")
    ap.add_argument("--decisions", help="JSON file mapping the preview's decision paths to selected concrete values")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    root = L.project_root(a.root)
    path = L.find_plan(root, a.plan)
    L.inside(root, path, "plan")
    raw = L.load_file(path)
    shape = L.type_problems(raw)
    if shape:
        L.die("; ".join(shape), 1)
    decisions = json.loads(L.read_text(a.decisions)) if a.decisions else {}
    proposed, actions, questions = recover(raw, root, decisions)
    for action in actions:
        L.say("  " + action)
    for question in questions:
        L.say(json.dumps(question, ensure_ascii=False))
    before, after = L.read_text(path), dump(proposed) + "\n"
    if proposed == raw:
        after = before
    L.say("\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile="current plan", tofile="proposed plan")))
    if questions:
        L.say("One decision: confirm the listed identity and source choices in --decisions, then preview again. No files written.")
        return 1
    if not a.apply:
        L.say(f"{len(actions)} repair action(s). Dry run; use --apply after review.")
        return 0
    if proposed != raw:
        L.write_text(path, after)
    _, problems = L.load_plan(path, root)
    if problems:
        for problem in problems:
            L.say("  validation: " + problem)
        return 1
    # Refresh generated headers only after canonical plan data is persisted.
    import scaffold_spec
    rc = scaffold_spec.main(["--root", str(root), "--plan", str(path), "--refresh-headers", "--apply"])
    if rc:
        return rc
    dev_path = proposed.get("project", {}).get("dev_skill_path")
    if dev_path and (root / dev_path / "SKILL.md").is_file():
        import generate_dev_skill
        rc = generate_dev_skill.main(["--root", str(root), "--plan", str(path), "--only", "references", "--apply"])
        if rc:
            return rc
    import check_specs
    return check_specs.main(["--root", str(root), "--plan", str(path)])


if __name__ == "__main__":
    raise SystemExit(main())
