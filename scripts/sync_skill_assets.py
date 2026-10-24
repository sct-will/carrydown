#!/usr/bin/env python3
"""Copy the scripts and templates each skill needs into its own folder.

Installers such as `npx skills add` copy only a skill's folder, not the whole repository.
So every skill carries the scripts and templates it runs. The canonical copies are in
scripts/ and templates/ at the top of the repository. This script refreshes the copies.

The GitHub client (github_client.py, the only module with network or token code) ships only
with carrydown-plan-to-github. The check fails if it, or any other script that is not in a
skill's list, turns up in another skill, and if any copy of carrydown_lib.py under skills/
differs from scripts/carrydown_lib.py.

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
        "scripts": ["github_token.py", "github_sync.py", "github_project.py", "github_client.py", "check_specs.py"],
        "templates": ["issue-body.md", "closing-comment.md", "checkpoint-comment.md"],
    },
    "carrydown-dev-skill": {
        "scripts": ["generate_dev_skill.py", "scaffold_spec.py", "render_ground_truth.py", "check_specs.py"],
        "templates": ["dev-skill/SKILL.md", "dev-skill/README.md"],
    },
}

# Modules that may ship with one skill only, because they hold network or token code.
ONLY_IN = {"github_client.py": "carrydown-plan-to-github"}


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


def problems():
    """Copies that must not exist or must match, beyond the plan: a module outside the skill
    that may ship it, a script no skill lists, and any carrydown_lib.py under skills/ that
    differs from the canonical one (the listed copies are compared in main)."""
    out = []
    wanted = {dst for _, dst in plan()}
    for skill, need in NEEDS.items():
        names = closure(need["scripts"])
        for mod, owner in ONLY_IN.items():
            if mod in names and skill != owner:
                out.append(f"{mod} is in the script list of {skill}, but it may ship only with {owner}")
    for f in sorted((REPO / "skills").glob("*/scripts/*.py")):
        if f not in wanted:
            out.append(f"not expected: {f.relative_to(REPO)}. Remove it by hand")
    canonical = (REPO / "scripts" / "carrydown_lib.py").read_bytes()
    for f in sorted((REPO / "skills").rglob("carrydown_lib.py")):
        if f not in wanted and f.read_bytes() != canonical:
            out.append(f"differs from scripts/carrydown_lib.py: {f.relative_to(REPO)}")
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
    extra = problems()
    for p in extra:
        print(p)
    if a.check:
        if not stale and not extra:
            print("copies are current")
        elif stale:
            print(f"{stale} copy(ies) out of date. Run: python3 scripts/sync_skill_assets.py --apply")
        return 1 if stale or extra else 0
    print(f"{stale} file(s) {'copied' if a.apply else 'would be copied'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
