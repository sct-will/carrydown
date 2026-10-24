#!/usr/bin/env python3
"""Copy the scripts and templates each skill needs into its own folder.

Installers such as `npx skills add` copy only a skill's folder, not the whole repository.
So every skill carries the scripts and templates it runs. The canonical copies are in
scripts/ and templates/ at the top of the repository. This script refreshes the copies.

Usage
  python3 scripts/sync_skill_assets.py            copy files (dry run: shows what would change)
  python3 scripts/sync_skill_assets.py --apply    write the copies
  python3 scripts/sync_skill_assets.py --check    exit 1 if any copy is out of date
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

NEEDS = {
    "carrydown-ground-truth": {
        "scripts": ["render_ground_truth.py", "scaffold_spec.py", "check_specs.py"],
        "templates": ["plan.yaml", "spec.md", "milestone.md", "spec-README.md", "closing-comment.md", "checkpoint-comment.md", "check-specs-workflow.yml"],
    },
    "carrydown-plan-to-github": {
        "scripts": ["github_token.py", "github_sync.py", "github_project.py", "check_specs.py"],
        "templates": ["issue-body.md", "closing-comment.md", "checkpoint-comment.md"],
    },
    "carrydown-dev-skill": {
        "scripts": ["generate_dev_skill.py", "scaffold_spec.py", "render_ground_truth.py"],
        "templates": ["dev-skill/SKILL.md", "dev-skill/README.md"],
    },
}


def closure(names):
    seen = set()
    todo = list(names) + ["carrydown_lib.py"]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        src = (REPO / "scripts" / n).read_text(encoding="utf-8")
        for m in re.finditer(r"(?m)^\s*import (\w+)(?: as \w+)?", src):
            cand = f"{m.group(1)}.py"
            if (REPO / "scripts" / cand).exists() and cand != "sync_skill_assets.py":
                todo.append(cand)
    return sorted(seen)


def plan():
    out = []
    for skill, need in NEEDS.items():
        for n in closure(need["scripts"]):
            out.append((REPO / "scripts" / n, REPO / "skills" / skill / "scripts" / n))
        for t in need["templates"]:
            out.append((REPO / "templates" / t, REPO / "skills" / skill / "templates" / t))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Copy the scripts and templates each skill needs into its own folder.")
    ap.add_argument("--apply", action="store_true", help="write the copies")
    ap.add_argument("--check", action="store_true", help="exit 1 if a copy is missing or differs")
    a = ap.parse_args(argv)
    stale = 0
    for src, dst in plan():
        same = dst.exists() and dst.read_bytes() == src.read_bytes()
        if same:
            continue
        stale += 1
        rel = dst.relative_to(REPO)
        if a.check:
            print(f"out of date: {rel}")
        elif a.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            print(f"copied: {rel}")
        else:
            print(f"would copy: {rel}")
    if a.check:
        print("copies are current" if not stale else f"{stale} copy(ies) out of date. Run: python3 scripts/sync_skill_assets.py --apply")
        return 1 if stale else 0
    print(f"{stale} file(s) {'copied' if a.apply else 'would be copied'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
