#!/usr/bin/env python3
"""Shared helpers for the carrydown scripts. Standard library only.

Contents
- A reader for the small YAML subset that plan.yaml uses (no PyYAML needed).
- The plan loader and validator.
- Helpers to read a specification file.

This module is imported by the other scripts. It is not run on its own.
"""
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# YAML subset reader
# ---------------------------------------------------------------------------
# Supported: block mappings, block sequences, nested to any depth, flow lists
# and flow maps on one line, quoted and plain scalars, comments, and the block
# scalars "|" and ">". Dates stay strings. Not supported: anchors, tags,
# multi-document files, multi-line flow collections. Write a value that holds
# a colon followed by a space in quotes.


class YamlError(ValueError):
    pass


def _cut_comment(s):
    out = []
    quote = None
    for i, ch in enumerate(s):
        if quote:
            out.append(ch)
            if ch == quote and (quote == "'" or s[i - 1] != "\\"):
                quote = None
            continue
        if ch in "\"'" and (i == 0 or s[i - 1] in " \t[{,:-"):
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_key(s):
    """Split 'key: value' or 'key:'. Return (key, rest) or None if not a mapping line."""
    if not s:
        return None
    if s[0] in "\"'":
        q = s[0]
        j = 1
        while j < len(s):
            if s[j] == q and (q == "'" or s[j - 1] != "\\"):
                break
            j += 1
        if j >= len(s):
            return None
        key = s[1:j]
        rest = s[j + 1:]
        if rest.startswith(":") and (len(rest) == 1 or rest[1] == " "):
            return key, rest[1:].strip()
        return None
    if s[0] in "[{":
        return None
    m = re.match(r"^([^\s:][^:]*?|[^\s:]):(?:\s+(.*)|$)", s)
    if not m:
        return None
    return m.group(1).strip(), (m.group(2) or "").strip()


def _scalar(s):
    s = s.strip()
    if s == "":
        return None
    if s[0] == '"':
        if len(s) < 2 or s[-1] != '"':
            raise YamlError(f"unterminated string: {s}")
        return json.loads(s) if "\\u" not in s else bytes(s[1:-1], "utf-8").decode("unicode_escape")
    if s[0] == "'":
        if len(s) < 2 or s[-1] != "'":
            raise YamlError(f"unterminated string: {s}")
        return s[1:-1].replace("''", "'")
    if s[0] == "[":
        return _flow(s)
    if s[0] == "{":
        return _flow(s)
    low = s.lower()
    if low in ("null", "~"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _flow(s):
    pos = [0]

    def ws():
        while pos[0] < len(s) and s[pos[0]] in " \t":
            pos[0] += 1

    def item(stop):
        ws()
        if pos[0] >= len(s):
            raise YamlError(f"bad flow collection: {s}")
        if s[pos[0]] == "[":
            return seq()
        if s[pos[0]] == "{":
            return mapping()
        if s[pos[0]] in "\"'":
            q = s[pos[0]]
            j = pos[0] + 1
            while j < len(s) and not (s[j] == q and (q == "'" or s[j - 1] != "\\")):
                j += 1
            tok = s[pos[0]:j + 1]
            pos[0] = j + 1
            return _scalar(tok)
        j = pos[0]
        while j < len(s) and s[j] not in stop:
            j += 1
        tok = s[pos[0]:j]
        pos[0] = j
        return _scalar(tok.strip())

    def seq():
        pos[0] += 1
        out = []
        ws()
        if s[pos[0]] == "]":
            pos[0] += 1
            return out
        while True:
            out.append(item(",]"))
            ws()
            if pos[0] >= len(s):
                raise YamlError(f"unterminated list: {s}")
            if s[pos[0]] == ",":
                pos[0] += 1
                continue
            if s[pos[0]] == "]":
                pos[0] += 1
                return out
            raise YamlError(f"bad list: {s}")

    def mapping():
        pos[0] += 1
        out = {}
        ws()
        if s[pos[0]] == "}":
            pos[0] += 1
            return out
        while True:
            k = item(":,}")
            ws()
            if pos[0] >= len(s) or s[pos[0]] != ":":
                raise YamlError(f"bad map: {s}")
            pos[0] += 1
            out[str(k)] = item(",}")
            ws()
            if pos[0] >= len(s):
                raise YamlError(f"unterminated map: {s}")
            if s[pos[0]] == ",":
                pos[0] += 1
                continue
            if s[pos[0]] == "}":
                pos[0] += 1
                return out
            raise YamlError(f"bad map: {s}")

    v = item("")
    ws()
    if pos[0] != len(s):
        raise YamlError(f"trailing text in flow collection: {s}")
    return v


class _Reader:
    def __init__(self, text):
        self.raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        self.i = 0

    def indent_of(self, line):
        return len(line) - len(line.lstrip(" "))

    def skip_blank(self):
        while self.i < len(self.raw):
            t = _cut_comment(self.raw[self.i]).strip()
            if t:
                return
            self.i += 1

    def peek(self):
        self.skip_blank()
        if self.i >= len(self.raw):
            return None
        line = self.raw[self.i]
        if "\t" in line[: self.indent_of(line)]:
            raise YamlError(f"line {self.i + 1}: tabs are not allowed for indentation")
        return self.indent_of(line), _cut_comment(line).strip()

    def block(self, min_indent):
        p = self.peek()
        if p is None or p[0] < min_indent:
            return None
        indent, content = p
        if content == "-" or content.startswith("- "):
            return self.sequence(indent)
        if _split_key(content):
            return self.mapping(indent)
        self.i += 1
        return _scalar(content)

    def block_scalar(self, style, parent_indent):
        lines = []
        block_indent = None
        while self.i < len(self.raw):
            line = self.raw[self.i]
            if line.strip() == "":
                lines.append("")
                self.i += 1
                continue
            ind = self.indent_of(line)
            if ind <= parent_indent:
                break
            if block_indent is None:
                block_indent = ind
            lines.append(line[block_indent:] if ind >= block_indent else line.strip())
            self.i += 1
        while lines and lines[-1] == "":
            lines.pop()
        if style.startswith(">"):
            paras, cur = [], []
            for ln in lines:
                if ln == "":
                    paras.append(" ".join(cur))
                    cur = []
                else:
                    cur.append(ln)
            paras.append(" ".join(cur))
            return "\n".join(paras)
        return "\n".join(lines)

    def value_after_key(self, rest, indent):
        if rest in ("|", ">", "|-", ">-", "|+", ">+"):
            return self.block_scalar(rest, indent)
        if rest == "":
            p = self.peek()
            if p is None:
                return None
            ind, content = p
            if ind > indent:
                return self.block(ind)
            if ind == indent and (content == "-" or content.startswith("- ")):
                return self.sequence(ind)
            return None
        return _scalar(rest)

    def mapping(self, indent):
        out = {}
        while True:
            p = self.peek()
            if p is None or p[0] != indent:
                if p is not None and p[0] > indent:
                    raise YamlError(f"line {self.i + 1}: unexpected indentation")
                return out
            content = p[1]
            kv = _split_key(content)
            if not kv:
                if content == "-" or content.startswith("- "):
                    return out
                raise YamlError(f"line {self.i + 1}: expected 'key: value', got {content!r}")
            key, rest = kv
            self.i += 1
            if key in out:
                raise YamlError(f"line {self.i}: duplicate key {key!r}")
            out[key] = self.value_after_key(rest, indent)

    def sequence(self, indent):
        out = []
        while True:
            p = self.peek()
            if p is None or p[0] != indent:
                return out
            content = p[1]
            if not (content == "-" or content.startswith("- ")):
                return out
            rest = content[1:].lstrip(" ")
            if rest == "":
                self.i += 1
                q = self.peek()
                out.append(self.block(q[0]) if q and q[0] > indent else None)
                continue
            offset = len(self.raw[self.i]) - len(self.raw[self.i].lstrip(" ")) + (len(content) - len(rest))
            if _split_key(rest) and rest[0] not in "[{\"'" or (rest[0] in "\"'" and _split_key(rest)):
                # a mapping that starts on the dash line
                self.raw[self.i] = " " * offset + self.raw[self.i].lstrip(" ")[len(content) - len(rest):]
                out.append(self.mapping(offset))
            else:
                self.i += 1
                out.append(_scalar(rest))


def loads(text):
    r = _Reader(text)
    v = r.block(0)
    r.skip_blank()
    if r.i < len(r.raw):
        raise YamlError(f"line {r.i + 1}: unexpected content")
    return v


def load_file(path):
    return loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Dates and ids
# ---------------------------------------------------------------------------

def parse_date(s):
    if isinstance(s, _dt.date):
        return s
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d\d-\d\d", s.strip()):
        raise ValueError(f"not a date (use YYYY-MM-DD): {s!r}")
    return _dt.date.fromisoformat(s.strip())


def fmt_date(d):
    return d.isoformat()


def tag(plan, n):
    return f"{plan['project']['id_prefix']}-{int(n):02d}"


def item_by_id(plan):
    return {it["id"]: it for it in plan["items"]}


def milestone_by_num(plan):
    return {m["number"]: m for m in plan["milestones"]}


def spec_path(plan, root, it):
    ms = milestone_by_num(plan)[it["milestone"]]
    name = f"{tag(plan, it['id']).lower()}-{it['slug']}.md"
    return Path(root) / plan["project"]["spec_dir"] / ms["folder"] / name


def milestone_path(plan, root, ms):
    return Path(root) / plan["project"]["spec_dir"] / ms["folder"] / "milestone.md"


# ---------------------------------------------------------------------------
# Plan loading and validation
# ---------------------------------------------------------------------------

DEFAULT_BANNED_WORDS = [r"sprints?", r"story points?", r"velocity"]
DEFAULT_BANNED_PHRASES = [r"open questions?", r"non-goals?"]
# The built-in vendor patterns are written with character classes so that this
# file does not itself spell the names it bans.
DEFAULT_BANNED_VENDORS = [
    r"open[a]i", r"chat[g]pt", r"\bg[p]t-?\d", r"anthrop[i]c", r"cl[a]ude", r"gem[i]ni",
    r"mistr[a]l", r"l[l]ama", r"deeps[e]ek", r"\bl[l]m\b", r"ai assistant",
]

PLAN_NAMES = ("plan.yaml", "docs/spec/plan.yaml")


def find_plan(root, explicit=None):
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = Path(root) / p if not p.exists() else p
        return p
    for cand in ("docs/spec/plan.yaml", "plan.yaml"):
        p = Path(root) / cand
        if p.exists():
            return p
    return Path(root) / "docs/spec/plan.yaml"


def load_plan(path):
    """Read plan.yaml and fill defaults. Returns (plan, problems)."""
    path = Path(path)
    try:
        raw = load_file(path)
    except (OSError, YamlError) as e:
        raise SystemExit(f"cannot read plan {path}: {e}")
    if not isinstance(raw, dict):
        raise SystemExit(f"plan {path} must be a mapping at the top level")
    plan = raw
    proj = plan.setdefault("project", {}) or {}
    plan["project"] = proj
    proj.setdefault("branch", "main")
    proj.setdefault("spec_dir", "docs/spec")
    proj.setdefault("subepic_prefix", "Milestone")
    proj.setdefault("title_format", "{id} {label}")
    proj.setdefault("epic", None)
    proj.setdefault("ground_truth", "docs/ground-truth/architecture.md")
    proj.setdefault("project_title", f"{proj.get('name', 'Plan')} plan")
    proj.setdefault("epic_title", f"{proj.get('name', 'Plan')}, development plan")
    for k in ("people", "advisors", "tracks", "milestones", "breaks", "checkpoints", "items"):
        if plan.get(k) is None:
            plan[k] = []
    for person in plan["people"]:
        if person.get("allocation") is None:
            person["allocation"] = 100
    plan["target"] = plan.get("target") or None
    plan["conventions"] = plan.get("conventions") or {}
    plan["limits"] = plan.get("limits") or {}
    plan["limits"].setdefault("spec_lines", [80, 340])
    plan["program"] = plan.get("program") or {}
    plan["program"].setdefault("items", [])
    plan["banned"] = plan.get("banned") or {}
    b = plan["banned"]
    b.setdefault("words", list(DEFAULT_BANNED_WORDS))
    b.setdefault("phrases", list(DEFAULT_BANNED_PHRASES))
    b["vendors"] = list(DEFAULT_BANNED_VENDORS) + [v for v in (b.get("vendors") or []) if v]
    b.setdefault("names", [])
    b.setdefault("dashes", True)
    for it in plan["items"]:
        it.setdefault("depends", [])
        it["depends"] = list(it["depends"] or [])
        it["unblocks"] = list(it.get("unblocks") or [])
        it.setdefault("program_input", "")
        it["program_input"] = it["program_input"] or ""
        it.setdefault("size", "")
        it.setdefault("ground_truth", "")
        it.setdefault("owner", "")
    # derived unblocks: inverse of depends
    derived = {it["id"]: [] for it in plan["items"] if isinstance(it.get("id"), int)}
    for it in plan["items"]:
        for d in it["depends"]:
            if d in derived:
                derived[d].append(it["id"])
    for it in plan["items"]:
        it["_derived_unblocks"] = sorted(derived.get(it["id"], []))
        if not it["unblocks"]:
            it["unblocks"] = it["_derived_unblocks"]
    # banned names: people and advisors, first names, github logins
    names = list(b["names"])
    for p in list(plan["people"]) + list(plan["advisors"]):
        if p.get("derived"):
            continue   # placeholder people such as "Engineer 1" are not real names
        if p.get("name"):
            names.append(p["name"])
            names.extend(part for part in re.split(r"\s+", p["name"]) if len(part) > 2)
        if p.get("github"):
            names.append(p["github"])
        if p.get("id") and len(str(p["id"])) >= 3:
            names.append(str(p["id"]))
    plan["_banned_names"] = sorted(set(n for n in names if n))
    plan["_path"] = str(path)
    return plan, validate_plan(plan)


def _is_date(s):
    try:
        parse_date(s)
        return True
    except ValueError:
        return False


def validate_plan(plan):
    P = []
    proj = plan["project"]
    for k in ("name", "slug", "id_prefix"):
        if not proj.get(k):
            P.append(f"project.{k} is required")
    if proj.get("repo") and not re.fullmatch(r"[\w.-]+/[\w.-]+", str(proj["repo"])):
        P.append(f"project.repo must look like owner/name, got {proj['repo']!r}")
    tracks = {t.get("id"): t for t in plan["tracks"]}
    if not tracks:
        P.append("tracks: at least one track is required")
    people = {p.get("id"): p for p in plan["people"]}
    for p in plan["people"]:
        if not p.get("id") or not p.get("name"):
            P.append(f"people: each person needs id and name ({p})")
        if p.get("track") not in tracks:
            P.append(f"people: {p.get('id')} has unknown track {p.get('track')!r}")
        for d in p.get("days_off") or []:
            if not _is_date(d):
                P.append(f"people: {p.get('id')} days_off has a bad date {d!r}")
    for t in plan["tracks"]:
        if not t.get("id") or not t.get("label"):
            P.append(f"tracks: each track needs id and label ({t})")
    for p in plan["people"]:
        al = p.get("allocation")
        if not isinstance(al, int) or isinstance(al, bool) or not (1 <= al <= 100):
            P.append(f"people: {p.get('id')} allocation must be a whole percent from 1 to 100, got {al!r}")
    for p in plan["people"]:
        if "derived" in p and not isinstance(p["derived"], bool):
            P.append(f"people: {p.get('id')} derived must be true or false")
    tg = plan.get("target")
    if tg is None:
        pass   # the target is optional. Without one, the plan's end date is derived from the critical path
    elif not isinstance(tg, dict) or not ("date" in tg or "weeks" in tg):
        P.append("target: write `target:` with `date: YYYY-MM-DD` or `weeks: N`, or leave the block out (breaks are listed under `breaks`)")
    else:
        if "derived" in tg and not isinstance(tg["derived"], bool):
            P.append("target: derived must be true or false")
        if tg.get("derived") and "date" not in tg:
            P.append("target: a derived target is written as a date")
        if "date" in tg and "weeks" in tg:
            P.append("target: give either date or weeks, not both")
        if "date" in tg and not _is_date(tg.get("date")):
            P.append(f"target: date is not a date: {tg.get('date')!r}")
        if "weeks" in tg and (not isinstance(tg["weeks"], int) or isinstance(tg["weeks"], bool) or tg["weeks"] < 1):
            P.append(f"target: weeks must be a whole number of working weeks, got {tg['weeks']!r}")
    ms_nums = []
    last_end = None
    for m in plan["milestones"]:
        n = m.get("number")
        ms_nums.append(n)
        for k in ("name", "folder", "start", "end", "demo", "gate"):
            if not m.get(k):
                P.append(f"milestone {n}: {k} is required")
        if all(_is_date(m.get(k)) for k in ("start", "end", "demo") if m.get(k)) and m.get("start") and m.get("end"):
            s, e = parse_date(m["start"]), parse_date(m["end"])
            if e < s:
                P.append(f"milestone {n}: end is before start")
            if last_end and s <= last_end:
                P.append(f"milestone {n}: starts on or before the previous milestone ends ({fmt_date(last_end)})")
            last_end = e
            if m.get("demo") and _is_date(m["demo"]):
                dm = parse_date(m["demo"])
                if dm < s or dm > e:
                    P.append(f"milestone {n}: demo {m['demo']} is outside {m['start']} to {m['end']}")
        else:
            for k in ("start", "end", "demo"):
                if m.get(k) and not _is_date(m[k]):
                    P.append(f"milestone {n}: {k} is not a date: {m[k]!r}")
    if ms_nums != list(range(1, len(ms_nums) + 1)):
        P.append(f"milestones must be numbered 1..N in order, got {ms_nums}")
    for br in plan["breaks"]:
        for k in ("name", "start", "end"):
            if not br.get(k):
                P.append(f"breaks: {k} is required")
        if br.get("start") and br.get("end") and _is_date(br["start"]) and _is_date(br["end"]):
            bs, be = parse_date(br["start"]), parse_date(br["end"])
            for m in plan["milestones"]:
                if m.get("start") and m.get("end") and _is_date(m["start"]) and _is_date(m["end"]):
                    if parse_date(m["start"]) <= be and bs <= parse_date(m["end"]):
                        P.append(f"break {br['name']!r} overlaps milestone {m['number']}")
    cps = {}
    for c in plan["checkpoints"]:
        if not c.get("date") or not _is_date(c.get("date")) or not c.get("name"):
            P.append(f"checkpoints: need date and name ({c})")
        else:
            cps[c["date"]] = c
    prog_ids = set()
    for pi in plan["program"]["items"]:
        if not isinstance(pi.get("id"), int) or not pi.get("label"):
            P.append(f"program.items: each needs integer id and label ({pi})")
        else:
            prog_ids.add(pi["id"])
    ids = []
    items = {}
    milestones = {m.get("number"): m for m in plan["milestones"]}
    for it in plan["items"]:
        iid = it.get("id")
        if not isinstance(iid, int):
            P.append(f"items: id must be an integer ({it.get('label')!r})")
            continue
        if iid in ids:
            P.append(f"item {iid}: duplicate id")
        ids.append(iid)
        items[iid] = it
        if iid in prog_ids:
            P.append(f"item {iid}: id is also a program item")
        for k in ("slug", "label", "milestone", "track", "complete_by", "checkpoint"):
            if it.get(k) in (None, ""):
                P.append(f"item {iid}: {k} is required")
        if it.get("slug") and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(it["slug"])):
            P.append(f"item {iid}: slug must be lowercase words joined by hyphens")
        if it.get("track") not in tracks:
            P.append(f"item {iid}: unknown track {it.get('track')!r}")
        if it.get("owner"):
            own = people.get(it["owner"])
            if not own:
                P.append(f"item {iid}: unknown owner {it['owner']!r}")
            elif own.get("track") != it.get("track"):
                P.append(f"item {iid}: owner {it['owner']} is on track {own.get('track')}, item is on {it.get('track')}")
        ms = milestones.get(it.get("milestone"))
        if not ms:
            P.append(f"item {iid}: unknown milestone {it.get('milestone')!r}")
        if it.get("complete_by") and not _is_date(it["complete_by"]):
            P.append(f"item {iid}: complete_by is not a date: {it['complete_by']!r}")
        elif it.get("complete_by") and ms and ms.get("start") and ms.get("end") and _is_date(ms["start"]) and _is_date(ms["end"]):
            d = parse_date(it["complete_by"])
            if not (parse_date(ms["start"]) <= d <= parse_date(ms["end"])):
                P.append(f"item {iid}: complete_by {it['complete_by']} is outside milestone {it['milestone']} ({ms['start']} to {ms['end']})")
            if d.weekday() >= 5:
                P.append(f"item {iid}: complete_by {it['complete_by']} is a weekend")
            own = people.get(it.get("owner"))
            if own and it["complete_by"] in [str(x) for x in (own.get("days_off") or [])]:
                P.append(f"item {iid}: complete_by {it['complete_by']} is a day off for {own['id']}")
        if it.get("checkpoint") and it["checkpoint"] not in cps:
            P.append(f"item {iid}: checkpoint {it['checkpoint']!r} is not in checkpoints")
        elif it.get("checkpoint") and it.get("complete_by") and _is_date(it["complete_by"]):
            if parse_date(it["checkpoint"]) < parse_date(it["complete_by"]):
                P.append(f"item {iid}: checkpoint {it['checkpoint']} is before complete_by {it['complete_by']}")
        if it.get("unblocks") != it.get("_derived_unblocks") and set(it["unblocks"]) != set(it["_derived_unblocks"]):
            P.append(f"item {iid}: unblocks {it['unblocks']} does not match the inverse of depends {it['_derived_unblocks']}")
    for it in plan["items"]:
        iid = it.get("id")
        for d in it["depends"]:
            if d not in items:
                P.append(f"item {iid}: depends on {d}, which is not an item (program ids are written in program_input, not depends)")
            elif d == iid:
                P.append(f"item {iid}: depends on itself")
            elif _is_date(items[d].get("complete_by", "")) and _is_date(it.get("complete_by", "")):
                if parse_date(items[d]["complete_by"]) > parse_date(it["complete_by"]):
                    P.append(f"item {iid}: completes {it['complete_by']} before its dependency {d} ({items[d]['complete_by']})")
    # cycle check
    state = {}

    def visit(n, stack):
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            P.append("dependency cycle: " + " -> ".join(str(x) for x in stack + [n]))
            return
        state[n] = 1
        for d in items.get(n, {}).get("depends", []):
            if d in items:
                visit(d, stack + [n])
        state[n] = 2

    for n in items:
        visit(n, [])
    return P


# ---------------------------------------------------------------------------
# Reading a specification file
# ---------------------------------------------------------------------------

def read_spec(path):
    text = Path(path).read_text(encoding="utf-8")
    lines = text.split("\n")
    rows = {}
    order = []
    for m in re.finditer(r"^\| (.+?) \| (.*?) \|$", text, re.M):
        name = m.group(1).strip()
        if name in ("", "---") or set(name) <= set("-: "):
            continue
        rows.setdefault(name, m.group(2).strip())
        order.append(name)
    sections = {}
    parts = re.split(r"(?m)^## (.+)$", text)
    # parts[0] is the preamble; then name, body pairs
    for i in range(1, len(parts), 2):
        sections[parts[i].strip()] = parts[i + 1]
    return {"text": text, "lines": lines, "rows": rows, "row_order": order, "sections": sections,
            "title": lines[0].strip() if lines else ""}


def section_text(spec, *names):
    for n in names:
        if n in spec["sections"]:
            return spec["sections"][n].strip("\n")
    return ""


def say(msg=""):
    print(msg, flush=True)


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def repo_parts(plan, override=None):
    repo = override or plan["project"].get("repo")
    if not repo or "/" not in repo:
        die("no repository. Set project.repo in plan.yaml or pass --repo owner/name")
    owner, name = repo.split("/", 1)
    return owner, name


# ---------------------------------------------------------------------------
# Expected values shared by the scaffold script and the checker
# ---------------------------------------------------------------------------

SECTIONS = [
    "Why this work item exists",
    "Outcome",
    "Context for the agent",
    ("Contract", "Protocol"),
    "Implementation guide",
    "Acceptance criteria",
    "Evidence of completion",
    "Integration points",
    "Out of scope",
    "Watch out for",
    "References",
    "Decisions recorded",
]
INTEGRATION_LEADS = ("Crosses the boundary.", "Joint check.", "Handoff on close.")
EVIDENCE_LEAD = "Demo."


def track_label(plan, track_id):
    for t in plan["tracks"]:
        if t.get("id") == track_id:
            return t.get("label") or track_id
    return track_id


def checkpoint_of(plan, it):
    for c in plan["checkpoints"]:
        if c.get("date") == it.get("checkpoint"):
            return c
    return None


def expected_header(plan, it):
    """Ordered (name, value) pairs for the header table of a work item specification."""
    ms = milestone_by_num(plan)[it["milestone"]]
    cp = checkpoint_of(plan, it) or {"date": it.get("checkpoint", ""), "name": ""}
    tags = ", ".join(tag(plan, d) for d in it["depends"]) or "None"
    if it["program_input"]:
        tags = (tags if tags != "None" else "").strip()
        tags = (tags + "; " if tags else "") + f"program input: {it['program_input']}"
    unb = ", ".join(tag(plan, u) for u in it["unblocks"]) or "None"
    rows = [
        ("Milestone", f"Milestone {ms['number']}, {ms['name']} (`{ms['folder']}`), work unit {ms['number']}"),
        ("Track", track_label(plan, it["track"])),
        ("Target", f"Complete by {it['complete_by']} (work unit {ms['number']}, {ms['name']}, {ms['start']} to {ms['end']})"),
        ("Checkpoint", f"{cp['date']}, {cp['name']}"),
        ("Demonstration", f"{ms['demo']}, milestone {ms['number']} demonstration (acceptance criteria in `milestone.md` in this folder)"),
        ("Size", it.get("size") or "To be sized"),
        ("Depends on", tags),
        ("Unblocks", unb),
        ("Ground truth", it.get("ground_truth") or "To be cited"),
    ]
    return rows


def header_markdown(plan, it):
    rows = expected_header(plan, it)
    w = max(len(k) for k, _ in rows)
    out = ["| | |", "| --- | --- |"]
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    return "\n".join(out)


def program_ids(plan):
    return {p["id"] for p in plan["program"]["items"] if isinstance(p.get("id"), int)}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def templates_dir():
    here = Path(__file__).resolve().parent
    for cand in (here.parent / "templates", here / "templates"):
        if cand.is_dir():
            return cand
    die("templates folder not found next to the scripts folder")


def read_template(*parts):
    return (templates_dir().joinpath(*parts)).read_text(encoding="utf-8")


def fill(template, values):
    """Replace {{key}} placeholders. Unknown keys are left in place so a miss is visible."""
    def sub(m):
        k = m.group(1).strip()
        return str(values[k]) if k in values else m.group(0)
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", sub, template)


def github_blob_url(plan, relpath, repo=None):
    owner, name = (repo or plan["project"]["repo"]).split("/", 1)
    return f"https://github.com/{owner}/{name}/blob/{plan['project']['branch']}/{relpath}"


def github_tree_url(plan, relpath, repo=None):
    owner, name = (repo or plan["project"]["repo"]).split("/", 1)
    return f"https://github.com/{owner}/{name}/tree/{plan['project']['branch']}/{relpath}"


def rel_spec(plan, root, it):
    return str(spec_path(plan, root, it).relative_to(Path(root).resolve())) if Path(root).resolve() in spec_path(plan, root, it).resolve().parents else str(spec_path(plan, root, it))


# ---------------------------------------------------------------------------
# Capacity and target
# ---------------------------------------------------------------------------

def working_days(start, end, days_off=()):
    """Monday to Friday days from start to end inclusive, minus the listed days off."""
    off = {str(d) for d in days_off}
    n = 0
    d = start
    while d <= end:
        if d.weekday() < 5 and fmt_date(d) not in off:
            n += 1
        d += _dt.timedelta(days=1)
    return n


def capacity_days(person, milestone):
    """Allocated working days a person has in a work unit: available days times allocation."""
    start = max(parse_date(milestone["start"]), parse_date(person["start"])) if person.get("start") else parse_date(milestone["start"])
    end = parse_date(milestone["end"])
    if end < start:
        return 0.0
    return working_days(start, end, person.get("days_off") or []) * person.get("allocation", 100) / 100.0


def sized_days(item):
    m = re.search(r"about (\d+(?:\.\d+)?)", item.get("size", "") or "")
    return float(m.group(1)) if m else 0.0


def load_rows(plan):
    """Per person and work unit: (person id, milestone number, sized days, capacity days, percent or None)."""
    rows = []
    for p in plan["people"]:
        for m in plan["milestones"]:
            sized = sum(sized_days(it) for it in plan["items"] if it.get("owner") == p["id"] and it["milestone"] == m["number"])
            cap = capacity_days(p, m)
            pct = (100.0 * sized / cap) if cap > 0 else (None if sized == 0 else float("inf"))
            rows.append((p["id"], m["number"], sized, cap, pct))
    return rows


def derived_summary(plan):
    """Text such as "2 people derived, target derived", or "" when nothing is derived."""
    n = sum(1 for p in plan["people"] if p.get("derived"))
    parts = []
    if n:
        parts.append(f"{n} {'person' if n == 1 else 'people'} derived")
    tg = plan.get("target")
    if isinstance(tg, dict) and tg.get("derived"):
        parts.append("target derived")
    return ", ".join(parts)


def target_is_constraint(plan):
    """A target constrains the plan only when it exists and is not derived."""
    tg = plan.get("target")
    return isinstance(tg, dict) and not tg.get("derived")


def target_date(plan):
    """Return (date, text). The date is None when the plan has no usable target.

    With `weeks`, the target is the last Friday of N working weeks plus the weeks the breaks take,
    counted from the start of the first work unit: start + 7 * (weeks + break weeks) - 3 days."""
    tg = plan.get("target")
    if not isinstance(tg, dict) or not plan["milestones"]:
        return None, "no target"
    if "date" in tg and _is_date(tg["date"]):
        return parse_date(tg["date"]), f"{tg['date']}"
    if isinstance(tg.get("weeks"), int):
        start = parse_date(plan["milestones"][0]["start"])
        break_days = sum((parse_date(b["end"]) - parse_date(b["start"])).days + 1 for b in plan["breaks"] if _is_date(b.get("start")) and _is_date(b.get("end")))
        break_weeks = -(-break_days // 7)
        d = start + _dt.timedelta(days=7 * (tg["weeks"] + break_weeks) - 3)
        return d, f"{tg['weeks']} working weeks plus {break_weeks} break week(s), which ends {fmt_date(d)}"
    return None, "no target"


if __name__ == "__main__":
    print(__doc__)
