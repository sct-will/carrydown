#!/usr/bin/env python3
"""Check the relative links of Markdown files. Read only. Standard library only. No network.

A link counts as broken when its target file or folder does not exist, or when its #anchor is not a heading
of the target Markdown file. Web links (http, https), mail links and links that still hold a {{placeholder}}
are not checked. Links inside code fences and code spans are not links.

It runs in two contexts. In source context it checks the files of this repository as they are, so a link in
a guide, a skill reference or a template must resolve from where the file sits. In generated-output context
it checks a project that the scripts generated, such as a clean clone of the sample or a project that
scaffold_spec.py and generate_dev_skill.py wrote, so a link in a generated README must resolve inside that
project, with no private workspace and no original document.

  python3 tests/check_links.py                    source context, the whole repository
  python3 tests/check_links.py --root PATH        any folder, for example a generated project
  python3 tests/check_links.py README.md docs/    named files or folders (relative to --root)

Exit status is 0 when every link resolves and 1 when one does not.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "specs"}
# Folders of test data that copy documents of the repository. Their links are checked as part of the folder
# they copy (the sample), and a copy of a snapshot is data that carries its own context.
SKIP_PREFIXES = ("tests/fixtures/",)
SUFFIXES = (".md", ".md.tmpl")

FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"(?<!\!)\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
IMAGE = re.compile(r"!\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def slug(text):
    """The GitHub anchor of a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def prose_lines(text):
    """(line number, text without code spans) for the lines outside fenced code."""
    fence = False
    for n, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            fence = not fence
            continue
        if not fence:
            yield n, CODE_SPAN.sub("", line)


def anchors_of(path, cache={}):
    key = str(path)
    if key in cache:
        return cache[key]
    found, seen = set(), {}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        cache[key] = found
        return found
    for _, line in prose_lines(text):
        m = HEADING.match(line)
        if m:
            base = slug(m.group(2))
            n = seen.get(base, 0)
            seen[base] = n + 1
            found.add(base if n == 0 else f"{base}-{n}")
    for m in re.finditer(r'<a\s+(?:name|id)="([^"]+)"', text):
        found.add(m.group(1))
    cache[key] = found
    return found


def candidates(root, paths=None):
    """The Markdown files to check, as paths relative to root with forward slashes."""
    root = Path(root)
    chosen = []
    if paths:
        for p in paths:
            full = root / p
            if full.is_dir():
                chosen += [f for f in sorted(full.rglob("*")) if f.is_file()]
            else:
                chosen.append(full)
    else:
        listed = None
        if (root / ".git").exists():
            run = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True)
            if run.returncode == 0:
                listed = [root / n for n in run.stdout.decode("utf-8", "replace").split("\0") if n]
        if listed is None:
            listed = []
            for base, dirs, files in os.walk(root):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                listed += [Path(base) / f for f in sorted(files)]
        chosen = listed
    out = []
    for f in chosen:
        rel = f.relative_to(root).as_posix()
        if not f.is_file() or not rel.endswith(SUFFIXES):
            continue
        if any(part in SKIP_DIRS for part in rel.split("/")):
            continue
        if any(rel.startswith(p) for p in SKIP_PREFIXES):
            continue
        out.append(rel)
    return sorted(out)


def check_file(root, rel):
    """[(line, target, why)] for the links of one file that do not resolve."""
    root = Path(root)
    path = root / rel
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [(0, "", "cannot read the file")]
    template = rel.endswith(".tmpl")
    problems = []
    for n, line in prose_lines(text):
        for m in list(LINK.finditer(line)) + list(IMAGE.finditer(line)):
            target = m.group(1)
            if "{{" in target or re.match(r"(?i)(https?:|mailto:|tel:|data:)", target):
                continue
            part, _, anchor = target.partition("#")
            if part.startswith("/"):
                dest = root / part.lstrip("/")
            elif part == "":
                dest = path
            else:
                dest = (path.parent / part)
            dest = Path(os.path.normpath(str(dest)))
            if root.resolve() not in [dest.resolve(), *dest.resolve().parents]:
                problems.append((n, target, "points outside the folder"))
                continue
            if not dest.exists():
                problems.append((n, target, "target does not exist"))
                continue
            if anchor and not template and dest.is_file() and dest.name.endswith(".md"):
                if slug(anchor) not in anchors_of(dest) and anchor not in anchors_of(dest):
                    problems.append((n, target, "anchor is not a heading of the target"))
    return problems


def check(root, paths=None):
    """[(file, line, target, why)] for every broken link under root."""
    out = []
    for rel in candidates(root, paths):
        for n, target, why in check_file(root, rel):
            out.append((rel, n, target, why))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files or folders to check, relative to --root (default: every Markdown file)")
    ap.add_argument("--root", default=str(ROOT), help="the folder the links resolve in (default: this repository)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a folder", file=sys.stderr)
        return 2
    files = candidates(root, a.paths or None)
    broken = check(root, a.paths or None)
    for rel, n, target, why in broken:
        print(f"{rel}:{n}: {target}: {why}")
    print(f"{len(files)} file(s) checked, {len(broken)} broken link(s)")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
