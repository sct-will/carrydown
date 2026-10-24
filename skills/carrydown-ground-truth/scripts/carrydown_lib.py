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


def safe_console():
    """Never crash on a character the console cannot show. A Windows console or a pipe read by an
    agent may use a code page such as cp1252; such characters are printed as escapes instead."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass


safe_console()


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
        try:
            return json.loads(s)
        except ValueError as e:
            raise YamlError(f"bad double-quoted value {s}: {getattr(e, 'msg', e)}. "
                            "Inside double quotes write \\\" for a quote, or use single quotes")
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


def read_text(path):
    """Read a text file as UTF-8, with or without a byte order mark (Notepad and PowerShell write one)."""
    return Path(path).read_text(encoding="utf-8-sig")


def load_file(path):
    return loads(read_text(path))


# ---------------------------------------------------------------------------
# Paths and names
# ---------------------------------------------------------------------------

def inside(root, path, what="output"):
    """Return path, resolved, when it lies inside root. Otherwise stop with a message.

    Every write target that comes from plan.yaml or the command line goes through this, so a
    value such as "../../somewhere" can never make a script write outside the project folder."""
    base = Path(root).resolve()
    target = Path(path)
    target = (target if target.is_absolute() else base / target).resolve()
    if target != base and base not in target.parents:
        die(f"the {what} path {path} is outside the project folder {base}, so nothing was written")
    return target


def slugify(text):
    """Lowercase words joined by hyphens, ASCII only: "Acme Pay, phase 2" becomes "acme-pay-phase-2"."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


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


RATIONALE_MILESTONE_KEYS = ("rationale", "joint_demonstration", "single_track_reason")


def _text(value):
    """A rationale field as one line of text. None becomes "". Anything that is not text is kept
    as it is, so validate_plan can report it."""
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def load_plan(path):
    """Read plan.yaml and fill defaults. Returns (plan, problems)."""
    path = Path(path)
    try:
        raw = load_file(path)
    except (OSError, ValueError) as e:   # YamlError, UnicodeDecodeError and JSON errors are ValueErrors
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
    if "external" not in plan and "program" in plan:   # plans written before the rename keep working
        plan["external"] = plan.pop("program")
    plan["external"] = plan.get("external") or {}
    plan["external"].setdefault("items", [])
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
        if "external_input" not in it and "program_input" in it:
            it["external_input"] = it.pop("program_input")
        it["external_input"] = it.get("external_input") or ""
        it.setdefault("size", "")
        it.setdefault("ground_truth", "")
        it.setdefault("owner", "")
        it["theme"] = _text(it.get("theme"))
    # the planning rationale: why each milestone holds its items, what the joint demonstration
    # shows, and why each track's items are in their order. Text, folded to one line.
    for m in plan["milestones"]:
        if isinstance(m, dict):
            for k in RATIONALE_MILESTONE_KEYS:
                m[k] = _text(m.get(k))
    for t in plan["tracks"]:
        if isinstance(t, dict):
            t["order_rationale"] = _text(t.get("order_rationale"))
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
    # banned names come only from the plan: the people and advisors in it, and banned.names.
    # Full names match in any case. A single part of a name ("Will", "Long") matches only as a
    # capitalised word, and handles and ids only as written, so the words "will" and "long" in
    # ordinary prose are not findings. A capitalised name part at the start of a sentence still is.
    names = [str(n) for n in b["names"] if n]
    exact = []
    for p in list(plan["people"]) + list(plan["advisors"]):
        if p.get("derived"):
            continue   # placeholder people such as "Engineer 1" are not real names
        parts = []
        if p.get("name"):
            names.append(str(p["name"]))
            parts = [part for part in re.split(r"\s+", str(p["name"])) if len(part) > 2]
            exact.extend(part[0].upper() + part[1:] for part in parts)
        lowered = {part.lower() for part in parts}
        for handle in (p.get("github"), p.get("id")):
            if handle and len(str(handle)) >= 3 and str(handle).lower() not in lowered:
                exact.append(str(handle))
    plan["_banned_names"] = sorted(set(n for n in names if n))
    plan["_banned_exact"] = sorted(set(exact))
    plan["_path"] = str(path)
    return plan, validate_plan(plan)


def _is_date(s):
    try:
        parse_date(s)
        return True
    except ValueError:
        return False


def _is_weekend(s):
    return parse_date(s).weekday() >= 5


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
        if p.get("start") is not None:
            if not _is_date(p["start"]):
                P.append(f"people: {p.get('id')} start is not a date (use YYYY-MM-DD): {p['start']!r}")
            elif _is_weekend(p["start"]):
                P.append(f"people: {p.get('id')} start {p['start']} is a weekend")
        if p.get("days_off") is not None and not isinstance(p.get("days_off"), list):
            P.append(f"people: {p.get('id')} days_off must be a list of dates, such as [2027-02-22]")
        for d in (p.get("days_off") if isinstance(p.get("days_off"), list) else []):
            if not _is_date(d):
                P.append(f"people: {p.get('id')} days_off has a bad date {d!r}")
            elif _is_weekend(d):
                P.append(f"people: {p.get('id')} day off {d} is a weekend")
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
    for m in plan["milestones"]:
        for k in RATIONALE_MILESTONE_KEYS:
            if not isinstance(m.get(k, ""), str):
                P.append(f"milestone {m.get('number')}: {k} must be text, in quotes if it holds a colon and a space")
    for t in plan["tracks"]:
        if not isinstance(t.get("order_rationale", ""), str):
            P.append(f"tracks: {t.get('id')} order_rationale must be text, in quotes if it holds a colon and a space")
    for it in plan["items"]:
        if not isinstance(it.get("theme", ""), str):
            P.append(f"item {it.get('id')}: theme must be text, such as \"web client\"")
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
            for k in ("start", "end", "demo"):
                if m.get(k) and _is_date(m[k]) and _is_weekend(m[k]):
                    P.append(f"milestone {n}: {k} {m[k]} is a weekend")
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
            if _is_weekend(c["date"]):
                P.append(f"checkpoint {c['date']} is a weekend")
    ext_ids = set()
    for pi in plan["external"]["items"]:
        if not isinstance(pi.get("id"), int) or not pi.get("label"):
            P.append(f"external.items: each needs integer id and label ({pi})")
        else:
            ext_ids.add(pi["id"])
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
        if iid in ext_ids:
            P.append(f"item {iid}: id is also an external item")
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
        if it.get("size") and not re.search(r"about \d+(?:\.\d+)?", str(it["size"])):
            P.append(f"item {iid}: size must say how many days, as in \"Medium, about 4 days\", got {it['size']!r}")
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
                P.append(f"item {iid}: depends on {d}, which is not an item (external item ids are written in external_input, not depends)")
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
    text = read_text(path)
    lines = text.split("\n")
    rows = {}
    order = []
    for m in re.finditer(r"^\| (.+?) \| (.*?) \|$", text, re.M):
        name = m.group(1).strip()
        if name in ("", "---") or set(name) <= set("-: ") or (name, m.group(2).strip()) == HEADER_HEAD:
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
    if it["external_input"]:
        tags = (tags if tags != "None" else "").strip()
        tags = (tags + "; " if tags else "") + f"external input: {it['external_input']}"
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


HEADER_HEAD = ("Field", "Value")
HEADER_LINES = [f"| {HEADER_HEAD[0]} | {HEADER_HEAD[1]} |", "| --- | --- |"]


def header_markdown(plan, it):
    rows = expected_header(plan, it)
    out = list(HEADER_LINES)
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Planning rigor: the rules a plan is composed by, and the helpers that read them
# ---------------------------------------------------------------------------

PLANNING_RULES = (
    "A milestone is the thinnest vertical slice that proves one user-visible capability end to end, named for what a user can do after it. "
    "The first proves the whole path with the least behaviour, and the last proves the project can be released and run.",
    "A milestone holds items from every track the capability crosses, and the tracks meet at a named joint check before the demonstration. "
    "A milestone that stays inside one track says why.",
    "The exit gate is one sentence the people accountable for the outcome can check live. The engineers whose tracks meet give the demonstration together, and the plan says what they show.",
    "Inside a milestone the shared contract comes first, so both tracks can start without waiting. The first week leaves nobody idle.",
    "Each engineer's consecutive items stay in one part of the system, a theme. Related items for the same person sit in adjacent days to cut context switching.",
    "Size in days divided by allocation gives calendar working days: four days at 60 percent is nearly seven working days. "
    "Nobody is planned past 100 percent of allocated capacity in a work unit, aim for about 80, and days off and breaks are real.",
    "Slack sits before every checkpoint and demonstration. An item that completes on its checkpoint date has none.",
    "The critical path is read for single points of failure. If it runs through one person, the plan says so and offers an alternative.",
    "Work outside the plan, owned outside the team, keeps its ids as gaps in the numbering.",
    "The plan records its rationale where a reviewer can argue with it: for each milestone, why these items form it and what the joint demonstration proves, "
    "and for each track, why its items are in this order. The plan owner reads the plan week by week, adversarially, before anything is scaffolded.",
)


def milestone_tracks(plan, ms):
    """[(track id, [items])] for the tracks a milestone's items are on, in the plan's track order."""
    its = [it for it in plan["items"] if it.get("milestone") == ms.get("number")]
    order = [t.get("id") for t in plan["tracks"]]
    seen = [t for t in order if any(it.get("track") == t for it in its)]
    seen += sorted({it.get("track") for it in its if it.get("track") not in order}, key=str)
    return [(t, [it for it in its if it.get("track") == t]) for t in seen]


def demo_checkpoint(plan, ms):
    """The checkpoint held on the milestone's demonstration date, or None."""
    for c in plan["checkpoints"]:
        if c.get("date") == ms.get("demo"):
            return c
    return None


def tracks_named(plan, text):
    """Track ids whose label or id appears in text as a whole word, in the plan's track order."""
    out = []
    for t in plan["tracks"]:
        for word in {str(t.get("label") or ""), str(t.get("id") or "")} - {""}:
            if re.search(r"(?i)(?<![\w-])" + re.escape(word) + r"(?![\w-])", text or ""):
                out.append(t.get("id"))
                break
    return out


def critical_path(plan):
    """(calendar days, [ids]) of the longest dependency chain to the last item, or (0, []).

    The length of a chain is the calendar days from the start of the first item's work unit to
    the last item's complete_by, following the dependencies. Chains that start in the same work
    unit often tie on days. A tie goes to the chain with more items, so the path keeps the
    dependency it starts from, such as the shared contract."""
    items = item_by_id(plan)
    if not items:
        return 0, []
    mss = milestone_by_num(plan)
    best = {}

    def longest(n):
        if n in best:
            return best[n]
        it = items[n]
        done = parse_date(it["complete_by"])
        start = parse_date(mss[it["milestone"]]["start"])
        best[n] = (max((done - start).days, 0), [n])   # a guard against a cycle, replaced below
        cand = best[n]
        for d in it["depends"]:
            if d in items and d != n:
                dd, path = longest(d)
                gap = (done - parse_date(items[d]["complete_by"])).days
                if (dd + gap, len(path) + 1) > (cand[0], len(cand[1])) and n not in path:
                    cand = (dd + gap, path + [n])
        best[n] = cand
        return cand

    end = max(items, key=lambda n: (parse_date(items[n]["complete_by"]), longest(n)[0]))
    return longest(end)


def slack_days(plan, item):
    """Working days between an item's complete_by and its checkpoint, the checkpoint day counted.
    0 when the item completes on its checkpoint date. Weekends, breaks and the owner's days off
    are not counted."""
    done, cp = parse_date(item["complete_by"]), parse_date(item["checkpoint"])
    off = _off_days(plan, item)
    n, d = 0, done + _dt.timedelta(days=1)
    while d <= cp:
        n += _is_working(d, off)
        d += _dt.timedelta(days=1)
    return n


def external_ids(plan):
    return {p["id"] for p in plan["external"]["items"] if isinstance(p.get("id"), int)}


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
    return read_text(templates_dir().joinpath(*parts))


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
# Markdown helpers shared by the scaffold, the renderer and the skill generator
# ---------------------------------------------------------------------------

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


def anchor_slug(text):
    """GitHub heading anchor: lowercase, drop punctuation, spaces to hyphens."""
    s = text.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def collect_headings(lines):
    """Return [(line_no, level, text)] for ATX headings outside code fences."""
    out = []
    fence = None
    for i, line in enumerate(lines, 1):
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if m:
            tok = m.group(1)
            if fence is None:
                fence = tok[0]
            elif tok[0] == fence:
                fence = None
            continue
        if fence:
            continue
        h = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if h:
            out.append((i, len(h.group(1)), h.group(2).strip()))
    return out


def anchors_for(headings):
    counts = {}
    result = []
    for _, _, text in headings:
        plain = re.sub(r"[`*_]", "", text)
        base = anchor_slug(plain)
        n = counts.get(base, 0)
        counts[base] = n + 1
        result.append(base if n == 0 else f"{base}-{n}")
    return result


def table_rows(text):
    """Rows of the first Markdown table in text as an ordered list of (name, value)."""
    rows = []
    started = False
    for line in text.split("\n"):
        if line.startswith("|"):
            started = True
            m = re.match(r"^\| (.+?) \| (.*?) \|$", line)
            if m and not set(m.group(1).strip()) <= set("-: ") and (m.group(1).strip(), m.group(2).strip()) != HEADER_HEAD:
                rows.append((m.group(1).strip(), m.group(2).strip()))
        elif started:
            break
    return rows


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


def allocation_of(plan, item):
    """Percent of working time the item's owner gives the plan, 100 when there is no owner."""
    for p in plan["people"]:
        if p.get("id") == item.get("owner"):
            al = p.get("allocation", 100)
            # an invalid allocation is reported by validate_plan; count it as 100 here
            return al if isinstance(al, int) and not isinstance(al, bool) and 1 <= al <= 100 else 100
    return 100


def needed_days(plan, item):
    """Working days an item takes on the calendar: its size in days over its owner's allocation.
    "about 4 days" at 60 percent is 4 / 0.6, about 6.7 working days."""
    return sized_days(item) * 100.0 / allocation_of(plan, item)


def _off_days(plan, item):
    off = set()
    for p in plan["people"]:
        if p.get("id") == item.get("owner"):
            off |= {str(d) for d in (p.get("days_off") or [])}
    for br in plan["breaks"]:
        if _is_date(br.get("start")) and _is_date(br.get("end")):
            d, e = parse_date(br["start"]), parse_date(br["end"])
            while d <= e:
                off.add(fmt_date(d))
                d += _dt.timedelta(days=1)
    return off


def _is_working(d, off):
    return d.weekday() < 5 and fmt_date(d) not in off


def _owner_start(plan, item):
    for p in plan["people"]:
        if p.get("id") == item.get("owner") and p.get("start"):
            return parse_date(p["start"])
    return None


def item_window(plan, item):
    """(first day, working days) an item has: from the day after its latest dependency completes,
    or from the start of its work unit when it has no dependency, to its complete_by date,
    without weekends, breaks and its owner's days off."""
    items = item_by_id(plan)
    deps = [items[d] for d in item["depends"] if d in items]
    if deps:
        start = max(parse_date(d["complete_by"]) for d in deps) + _dt.timedelta(days=1)
    else:
        start = parse_date(milestone_by_num(plan)[item["milestone"]]["start"])
    own = _owner_start(plan, item)
    if own and own > start:
        start = own
    end = parse_date(item["complete_by"])
    off = _off_days(plan, item)
    n, d = 0, start
    while d <= end:
        n += _is_working(d, off)
        d += _dt.timedelta(days=1)
    return start, n


def fit_findings(plan):
    """Items whose window is shorter than the working days their size and allocation need."""
    out = []
    items = item_by_id(plan)
    for it in plan["items"]:
        need = needed_days(plan, it)
        if need <= 0:
            continue
        start, have = item_window(plan, it)
        if have + 1e-9 < need:
            deps = [d for d in it["depends"] if d in items]
            last = max(deps, key=lambda d: parse_date(items[d]["complete_by"])) if deps else None
            frm = (f"from {fmt_date(start)}, the day after {tag(plan, last)} completes," if last
                   else f"from {fmt_date(start)}, the start of work unit {it['milestone']},")
            out.append(f"{tag(plan, it['id'])} needs about {need:.1f} working days ({sized_days(it):g} days at {allocation_of(plan, it)} percent) "
                       f"but has {have} {frm} to its complete_by {it['complete_by']}")
    return out


def earliest_finish(plan):
    """Forward pass over the dependencies with durations from size and allocation.

    Returns ({id: (earliest start, earliest finish)}, chain of ids to the latest finish), or
    ({}, []) when no item is sized. An item starts no earlier than the first work unit and its
    owner's start, and the working day after its last dependency finishes. Owners are not
    serialised here: the load table covers that."""
    if not plan["items"] or not any(sized_days(it) for it in plan["items"]):
        return {}, []
    items = item_by_id(plan)
    first = parse_date(plan["milestones"][0]["start"]) if plan["milestones"] else min(parse_date(it["complete_by"]) for it in plan["items"])
    memo, via = {}, {}

    def visit(n, stack=()):
        if n in memo:
            return memo[n]
        it = items[n]
        off = _off_days(plan, it)
        start, prev = first, None
        own = _owner_start(plan, it)
        if own and own > start:
            start = own
        for d in it["depends"]:
            if d in items and d not in stack:
                fin = visit(d, stack + (n,))[1] + _dt.timedelta(days=1)
                if fin > start:
                    start, prev = fin, d
        while not _is_working(start, off):
            start += _dt.timedelta(days=1)
        need = needed_days(plan, it)
        finish, done = start, 0.0
        while True:
            if _is_working(finish, off):
                done += 1
                if done + 1e-9 >= need:
                    break
            finish += _dt.timedelta(days=1)
        memo[n], via[n] = (start, finish), prev
        return memo[n]

    for n in items:
        visit(n)
    end = max(memo, key=lambda n: (memo[n][1], n))
    chain, n = [], end
    while n is not None:
        chain.append(n)
        n = via[n]
    return memo, chain[::-1]


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
