#!/usr/bin/env python3
"""Lint the prose of the repository. Read only. Standard library only.

Rules
  1. No em dashes, en dashes or Unicode line separators anywhere.
  2. No credit lines for tools, and no co-author trailers.
  3. No AI vendor or model names, except in the files that hold the install
     instructions (the agent list). The patterns are written with character
     classes so that this file does not spell the names it bans. The full name of
     the compared project CCPM is allowed where its acronym is expanded.
  4. No names of the design system this repository was modeled on, and no company name outside
     the agent lists.
  5. One retired word, which is written with a character class in the pattern below.
  6. US English spelling. British forms are flagged: -isation and -ise verbs, -our nouns, -re
     nouns, doubled l before a suffix, and a short word list. Real words that only look British
     (advise, promise, exercise, enterprise and the like) are on the allowlist ISE_OK. The
     patterns hide one letter in a character class so that this file does not spell the words it bans.

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
    r"(?i)cl[a]ude(?!\s+c[o]de\s+pr[o]ject\s+m[a]nagement\b)|anthrop[i]c|open[a]i|chat[g]pt|\bg[p]t-?\d|gem[i]ni|\bc[o]pilot\b|\bc[o]dex\b|\bcurs[o]r\b|mistr[a]l|\bl[l]ama\b|deeps[e]ek|\bI[B]M\b"
)
# Files that hold the install instructions and so may name the agents.
VENDOR_OK = [
    "docs/setup.md",
    "templates/dev-skill/README.md.tmpl",
    "skills/*/templates/dev-skill/README.md.tmpl",
    "skills/carrydown-plan-to-github/references/engineers-skill-install.md",
    "sample/*/docs/dev/skills/*/README.md",
]


# US English. Each fragment hides one letter in a character class so this file does not match itself.
BRIT_STEMS = (
    "organi[s]|authori[s]|capitali[s]|summari[s]|recogni[s]|seriali[s]|normali[s]|initiali[s]|customi[s]|optimi[s]|"
    "prioriti[s]|minimi[s]|maximi[s]|standardi[s]|finali[s]|reali[s]|visuali[s]|categori[s]|characteri[s]|"
    "synchroni[s]|utili[s]|locali[s]|generali[s]|speciali[s]|memori[s]|saniti[s]|tokeni[s]|virtuali[s]|harmoni[s]|"
    "formali[s]|stabili[s]|randomi[s]|materiali[s]|centrali[s]|moderni[s]|personali[s]|rationali[s]|styli[s]|"
    "apologi[s]|emphasi[s]|digitali[s]|legali[s]|mobili[s]|neutrali[s]|populari[s]|scrutini[s]|symboli[s]|theori[s]|"
    "analy[s]|paraly[s]|cataly[s]"
)
BRIT_WORDS = (
    r"behavio[u]r\w*|colo[u]r\w*|favo[u]r\w*|hono[u]r\w*|rigo[u]r\w*|labo[u]r\w*|neighbo[u]r\w*|humo[u]r\w*|flavo[u]r\w*|"
    r"harbo[u]r\w*|rumo[u]r\w*|endeavo[u]r\w*|vapo[u]r\w*|savo[u]r\w*|armo[u]r\w*|"
    r"cent[r]e[sd]?|centr[i]ng|met[r]es?|lit[r]es?|fib[r]es?|theat[r]es?|calib[r]e|"
    r"(?:un|re|mis)?(?:label|model|travel|cancel|signal|level|fuel|channel|counsel|marshal|total|equal|quarrel|jewel)l(?:ed|ing|er|ers)|"
    r"licen[c]e[sd]?|progra[m]{2}e[s]?|judge[m]ent[s]?|toward[s]|afterward[s]|among[s]t|whil[s]t|catalog[u]e[s]?|"
    r"[g]rey|scepti[c]\w*|arte[f]act[s]?|defen[c]e|offen[c]e|pretenc[e]|a[g]eing|alumin[i]um|practi[s]e[ds]?|learn[t]|spel[t]|"
    r"cheq[u]e|ker[b]s?|t[y]res?|mo[u]ld\w*|plo[u]gh\w*|speciali[t]y|acknowledgem[e]nt|fulfi[l]\b|enro[l]\b|instal[m]ent|"
    r"skil[f]ul|wil[f]ul|sto[r]eys?|manoe[u]vre\w*|ana[e]mi\w*|pa[e]diatric\w*|sul[p]hur|ton[n]es?|dra[u]ght"
)
ISE_RE = re.compile(r"(?i)\b(?:(?:%s)(?:e|es|ed|ing|ation|ations|er|ers|able)|[a-z]{3,}isations?)\b" % BRIT_STEMS)
BRIT_RE = re.compile(r"(?i)\b(?:%s)\b" % BRIT_WORDS)
# Generic -ise verbs: flagged unless the root is a real word that ends in -ise in US English too.
ISE_GENERIC = re.compile(r"(?i)\b([a-z]{3,}is)(e|es|ed|ing)\b")
ISE_OK = set("""advis revis promis exercis enterpris otherwis precis surpris compromis expertis premis rais ris wis prais aris
supervis improvis devis franchis merchandis compris despis concis paradis treatis demis likewis clockwis televis excis incis
chastis apris repris pois cruis bruis disguis sunris uprais surmis liais tortois porpois turquois advertis disenfranchis
circumcis misadvis unwis prais mortis anis ris""".split())


def _brit(text):
    """Yield (offset, word) for British spellings, skipping real words that only end in -ise."""
    for m in ISE_RE.finditer(text):
        yield m.start(), m.group(0)
    for m in BRIT_RE.finditer(text):
        yield m.start(), m.group(0)
    for m in ISE_GENERIC.finditer(text):
        if m.group(1).lower() not in ISE_OK and not ISE_RE.fullmatch(m.group(0)):
            yield m.start(), m.group(0)


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
        seen = set()
        for off, word in _brit(text):
            if off in seen:
                continue
            seen.add(off)
            ln = text.count("\n", 0, off) + 1
            findings.append(f"{rel}:{ln}: British spelling, use US English ({word}): {text.splitlines()[ln - 1].strip()[:80]}")
    print(f"{n} files linted, {len(findings)} findings")
    for f in findings:
        print("  " + f)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
