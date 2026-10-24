#!/usr/bin/env python3
"""Lint the prose of the repository. Read only. Standard library only.

Rules
  1. No em dashes, en dashes or Unicode line separators anywhere.
  2. No credit lines for tools, and no co-author trailers.
  3. No AI vendor or model names, except in the files that hold the install
     instructions (the agent list). The patterns are written with character
     classes so that this file does not spell the names it bans.
  4. No names of the design system this repository was modelled on, and no company name outside
     the agent lists.
  5. One retired word, which is written with a character class in the pattern below.

Usage
  python3 scripts/lint_prose.py            lint the whole repository
  python3 scripts/lint_prose.py README.md  lint named files
Exit status is 0 when clean and 1 when there are findings.
"""
import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS = {".md", ".yml", ".yaml", ".py", ".txt", ".json", ".tmpl"}
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
SKIP_FILES = {"LICENSE"}

ALWAYS = [
    (re.compile("[" + chr(0x2014) + chr(0x2013) + chr(0x2028) + chr(0x2029) + "]"), "em dash, en dash or line separator"),
    (re.compile(r"(?i)gener" + r"ated\s+by|co-auth" + r"ored-by"), "credit line"),
    (re.compile(r"(?i)\bc[a]rbon\b"), "design system name that must not appear"),
    (re.compile(r"(?i)copyright\s+(?:\(c\)\s*)?(?:19|20)\d\d"), "copyright line. Use an attribution line instead"),
    (re.compile(r"(?i)\bk[i]t\b"), "retired word. Say the carrydown skills, the two skills or the repository"),
]
VENDORS = re.compile(
    r"(?i)cl[a]ude|anthrop[i]c|open[a]i|chat[g]pt|\bg[p]t-?\d|gem[i]ni|\bc[o]pilot\b|\bc[o]dex\b|\bcurs[o]r\b|mistr[a]l|\bl[l]ama\b|deeps[e]ek|\bI[B]M\b"
)
# Files that hold the install instructions and so may name the agents.
VENDOR_OK = [
    "README.md", "START-HERE.md",
    "templates/dev-skill/README.md.tmpl",
    "skills/*/templates/dev-skill/README.md.tmpl",
    "skills/carrydown-plan-to-github/references/engineers-skill-install.md",
    "sample/*/docs/dev/skills/*/README.md",
]


def files(args):
    if args:
        for a in args:
            yield Path(a).resolve()
        return
    for r, d, fs in os.walk(ROOT):
        d[:] = [x for x in d if x not in SKIP_DIRS]
        for f in fs:
            p = Path(r) / f
            if p.suffix in EXTENSIONS and p.name not in SKIP_FILES:
                yield p


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint the prose of the repository: dashes, credit lines, vendor names outside the install list.")
    ap.add_argument("paths", nargs="*", help="files to lint (default: the whole repository)")
    a = ap.parse_args(argv)
    findings = []
    n = 0
    for p in files(a.paths):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        n += 1
        rel = p.relative_to(ROOT).as_posix() if ROOT in p.parents else str(p)
        vendor_ok = any(fnmatch.fnmatch(rel, pat) for pat in VENDOR_OK)
        rules = list(ALWAYS) + ([] if vendor_ok else [(VENDORS, "AI vendor or tool name outside the install instructions")])
        for pat, why in rules:
            for m in pat.finditer(text):
                ln = text.count("\n", 0, m.start()) + 1
                findings.append(f"{rel}:{ln}: {why}: {text.splitlines()[ln - 1].strip()[:80]}")
    print(f"{n} files linted, {len(findings)} findings")
    for f in findings:
        print("  " + f)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
