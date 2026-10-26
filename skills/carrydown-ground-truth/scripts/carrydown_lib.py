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
import stat as _stat
import string
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
    # ASCII digits only. A run of more than 30 digits stays text: no id, count or percent is that
    # long, and int() of thousands of digits is refused by Python. The validator reports it.
    if re.fullmatch(r"-?[0-9]{1,30}", s):
        return int(s)
    if re.fullmatch(r"-?[0-9]{1,30}\.[0-9]{1,30}", s):
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
        if pos[0] >= len(s):
            raise YamlError(f"unterminated list, a [ with no ]: {s}")
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
        if pos[0] >= len(s):
            raise YamlError(f"unterminated map, a {{ with no }}: {s}")
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
    try:
        v = r.block(0)
    except YamlError as e:
        # a value on one line, such as a flow list cut short, is reported with the line it is on:
        # the reader has just moved past that line, so r.i is its line number
        if str(e).startswith("line "):
            raise
        raise YamlError(f"line {max(r.i, 1)}: {e}")
    except RecursionError:
        raise YamlError(f"line {max(r.i, 1)}: lists or maps nested too deeply")
    r.skip_blank()
    if r.i < len(r.raw):
        raise YamlError(f"line {r.i + 1}: unexpected content")
    return v


class TextError(SystemExit):
    """A file that cannot be read as UTF-8 text. It is a SystemExit, so a script that does not
    catch it stops with its one-line message and no traceback. str(e) is the message."""

    def __init__(self, msg):
        super().__init__(f"error: {msg}")
        self.msg = msg

    def __str__(self):
        return self.msg


def regular_file_problem(path):
    """Why path cannot be read as a file, or None when it is a regular file. A folder, a named
    pipe or a device such as /dev/zero is refused before it is opened: reading a pipe waits for
    a writer, and reading /dev/zero never ends. A path that does not exist returns None, so the
    caller reports it in its own words."""
    try:
        mode = os.stat(str(path)).st_mode
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        return f"cannot read {path}: {getattr(e, 'strerror', None) or e}"
    if _stat.S_ISDIR(mode):
        return f"{path} is a folder, not a file"
    if not _stat.S_ISREG(mode):
        return f"{path} is not a regular file (it is a named pipe, a socket or a device). Name a text file"
    return None


def read_text(path):
    """Read a text file as UTF-8, with or without a byte order mark (Notepad and PowerShell write one).
    A file that is not UTF-8, or a path that is a folder, a pipe or a device, raises TextError with
    a one-line message."""
    p = Path(path)
    why = regular_file_problem(p)
    if why:
        raise TextError(why)
    try:
        return p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise TextError(f"{p} is not UTF-8 text (byte 0x{e.object[e.start]:02x} at offset {e.start}). "
                        "Save it as UTF-8, then run this again")
    except IsADirectoryError:
        raise TextError(f"{p} is a folder, not a file")
    except OSError as e:
        raise TextError(f"cannot read {p}: {e.strerror or e}")


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


def write_text(path, text):
    """Write a UTF-8 text file, creating its folder. A path that cannot be written stops the script
    with a one-line message instead of a traceback."""
    path = Path(path)
    try:
        if path.exists() and not path.is_file():
            # opening a named pipe for writing waits for a reader, so it is refused, as is a folder
            die(f"cannot write {path}: it is {'a folder' if path.is_dir() else 'not a regular file'}. Move it out of the way, then run this again")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as e:
        die(f"cannot write {path}: {e.strerror or e}. Check that the folder exists and that you may write to it")


def root_problem(value):
    """Why value cannot be the project folder, or None. Shared by every script's --root."""
    if not str(value).strip():
        return "--root is empty. Pass the project folder, for example --root ."
    try:
        root = Path(value).expanduser().resolve()
        if root.is_dir():
            return None
        return f"--root {value} is not a folder" + ("" if root.exists() else ", it does not exist") + ". Pass the project folder"
    except (OSError, ValueError, RuntimeError) as e:
        return f"--root {value} cannot be used: {getattr(e, 'strerror', None) or e}. Pass the project folder"


def project_root(value):
    """The --root folder, resolved. A path that does not exist or is not a folder stops the script."""
    why = root_problem(value)
    if why:
        die(why)
    return Path(value).expanduser().resolve()


def exists(path):
    """Path.exists() that answers False instead of raising, for a name too long for the file
    system or a path the user may not search. Python 3.9 raises on both."""
    try:
        return Path(path).exists()
    except (OSError, ValueError):
        return False


def slugify(text):
    """Lowercase words joined by hyphens, ASCII only: "Acme Pay, phase 2" becomes "acme-pay-phase-2"."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


# ---------------------------------------------------------------------------
# Dates and ids
# ---------------------------------------------------------------------------

def parse_date(s):
    """A YYYY-MM-DD date from 1900 to 2999. A year outside that range is a typing error, and date
    arithmetic near the year 9999 would overflow."""
    if isinstance(s, _dt.date):
        return s
    if not isinstance(s, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", s.strip()):
        raise ValueError(f"not a date (use YYYY-MM-DD): {s!r}")
    if not 1900 <= int(s.strip()[:4]) <= 2999:
        raise ValueError(f"not a date from 1900 to 2999: {s!r}")
    return _dt.date.fromisoformat(s.strip())


def fmt_date(d):
    return d.isoformat()


def tag(plan, n):
    return f"{plan['project']['id_prefix']}-{int(n):02d}"


def item_number(plan, text):
    """The item number in an id written 3, 03, WI-03, wi-3 or WI03, or None. ASCII digits only,
    so a negative number or a full-width digit is not an id."""
    prefix = str(plan["project"].get("id_prefix") or "")
    pat = (r"\s*(?:" + re.escape(prefix) + r"-?)?0*([0-9]+)\s*") if prefix else r"\s*0*([0-9]+)\s*"
    m = re.fullmatch(pat, str(text), re.I)
    return int(m.group(1)) if m else None


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
    """The plan path: --plan when given, else docs/spec/plan.yaml or plan.yaml under root. An
    empty --plan raises PlanError, so it never falls back to the default plan."""
    if explicit is not None and not str(explicit).strip():
        raise PlanError("--plan is empty. Leave it out to use docs/spec/plan.yaml, or give the path of the plan")
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = Path(root) / p if not exists(p) else p
        return p
    for cand in ("docs/spec/plan.yaml", "plan.yaml"):
        p = Path(root) / cand
        if exists(p):
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


class PlanError(SystemExit):
    """plan.yaml cannot be read, or a value in it has the wrong type, so no script can use it.
    It is a SystemExit, so a script that does not catch it stops with its message and no
    traceback. e.msg is the message without the "error: " prefix."""

    def __init__(self, msg):
        super().__init__(f"error: {msg}")
        self.msg = msg

    def __str__(self):
        return self.msg


def _kind(v):
    return {dict: "a mapping", list: "a list", bool: "true or false", type(None): "empty"}.get(type(v), "text" if isinstance(v, str) else "a number")


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


# Fields read as text, per list of the plan. A number given for one of them is taken as text,
# so `label: 2027` works. None means the field is empty and is treated as left out.
_TEXT_FIELDS = {
    "tracks": ("id", "label", "color"),
    "people": ("id", "name", "github", "track", "start"),
    "advisors": ("id", "name", "github", "note"),
    "milestones": ("name", "folder", "start", "end", "demo", "gate"),
    "breaks": ("name", "start", "end"),
    "checkpoints": ("date", "name", "joint_check"),
    "items": ("slug", "label", "track", "owner", "complete_by", "size", "checkpoint", "ground_truth", "external_input", "program_input"),
    "external.items": ("label", "note"),
    "sources": ("id", "name", "source_path", "path", "use", "version", "status", "limit"),
}
_INT_FIELDS = {"milestones": ("number",), "items": ("id", "milestone"), "external.items": ("id",)}
_PROJECT_TEXT = ("name", "slug", "id_prefix", "repo", "branch", "epic_title", "subepic_prefix", "title_format",
                 "spec_dir", "ground_truth", "project_title", "dev_skill", "dev_skill_path")


def _as_text(row, key, where, P):
    """Keep a text field as text: a number becomes text, empty means left out, anything else is a problem."""
    if key not in row:
        return
    v = row[key]
    if v is None:
        del row[key]
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        row[key] = str(v)
    elif not isinstance(v, str):
        P.append(f"{where}.{key} must be text, got {_kind(v)}. Write it on one line, in quotes if it holds a colon and a space")


def type_problems(plan):
    """Problems with the shape of plan.yaml: a list where a mapping belongs, a mapping where text
    belongs, an id that is not a whole number. Any of them stops every script, because the plan
    cannot be read as a plan. Returns a list of one-line problems. Fixes harmless shapes in place:
    numbers in text fields become text, and empty values count as left out."""
    P = []
    for key, want in (("project", dict), ("conventions", dict), ("external", dict), ("program", dict), ("limits", dict),
                      ("banned", dict), ("tracks", list), ("people", list), ("advisors", list), ("milestones", list),
                      ("breaks", list), ("checkpoints", list), ("items", list), ("sources", list)):
        if plan.get(key) is not None and not isinstance(plan[key], want):
            P.append(f"{key} must be {'a mapping of keys' if want is dict else 'a list of entries starting with -'}, got {_kind(plan[key])}")
    if P:
        return P
    proj = plan.get("project") or {}
    for k in _PROJECT_TEXT:
        _as_text(proj, k, "project", P)
    ep = proj.get("epic")
    if ep is not None and not _is_int(ep) and not (isinstance(ep, str) and re.fullmatch(r"[0-9]{1,18}", ep.strip())):
        P.append(f"project.epic must be an issue number or null, got {ep!r}")
    elif isinstance(ep, str):
        proj["epic"] = int(ep.strip())   # the number goes into API paths, so it is kept as ASCII digits only
    if _is_int(proj.get("epic")) and proj["epic"] < 0:
        P.append(f"project.epic must be an issue number or null, got {proj['epic']!r}")
    rows = dict((k, plan.get(k) or []) for k in ("tracks", "people", "advisors", "milestones", "breaks", "checkpoints", "items", "sources"))
    ext = plan.get("external") if plan.get("external") is not None else plan.get("program")
    if isinstance(ext, dict):
        if ext.get("items") is not None and not isinstance(ext["items"], list):
            P.append(f"external.items must be a list of entries starting with -, got {_kind(ext['items'])}")
        else:
            rows["external.items"] = ext.get("items") or []
    for group, lst in rows.items():
        for n, row in enumerate(lst, 1):
            if not isinstance(row, dict):
                P.append(f"{group}: entry {n} must be a mapping such as `- id: ...`, got {_kind(row)} {row!r}"[:200])
                continue
            where = f"{group} entry {n}"
            for k in _TEXT_FIELDS.get(group, ()):
                _as_text(row, k, where, P)
            for k in _INT_FIELDS.get(group, ()):
                if row.get(k) is not None and not _is_int(row[k]):
                    P.append(f"{where}.{k} must be a whole number, got {row[k]!r}")
            for k in ("depends", "unblocks") if group == "items" else ():
                v = row.get(k)
                if v is None:
                    continue
                if not isinstance(v, list) or not all(_is_int(d) for d in v):
                    P.append(f"{where}.{k} must be a list of item ids, such as [1, 3], got {v!r}")
            if group == "people" and row.get("days_off") is not None:
                v = row["days_off"]
                if not isinstance(v, list) or not all(isinstance(d, (str, int)) and not isinstance(d, bool) for d in v):
                    P.append(f"{where}.days_off must be a list of dates, such as [2027-02-22], got {v!r}")
            if group == "items" and row.get("source_refs") is not None:
                refs = row["source_refs"]
                if not isinstance(refs, list):
                    P.append(f"{where}.source_refs must be a list of source and sections entries")
                else:
                    for rnum, ref in enumerate(refs, 1):
                        rwhere = f"{where}.source_refs entry {rnum}"
                        if not isinstance(ref, dict):
                            P.append(f"{rwhere} must be a mapping such as `- source: architecture`, got {_kind(ref)}")
                            continue
                        _as_text(ref, "source", rwhere, P)
                        _as_text(ref, "sections", rwhere, P)
    conv = plan.get("conventions") or {}
    for k in ("test_command", "lint_command", "feature_flag"):
        _as_text(conv, k, "conventions", P)
    if conv.get("extra") is not None and (not isinstance(conv["extra"], list) or not all(isinstance(x, str) for x in conv["extra"])):
        P.append("conventions.extra must be a list of text lines")
    lim = plan.get("limits") or {}
    sl = lim.get("spec_lines")
    if sl is not None and not (isinstance(sl, list) and len(sl) == 2 and all(_is_int(x) and x >= 0 for x in sl) and sl[0] <= sl[1]):
        P.append(f"limits.spec_lines must be two whole numbers, low then high, such as [80, 340], got {sl!r}")
    b = plan.get("banned") or {}
    for k in ("words", "phrases", "vendors", "names"):
        v = b.get(k)
        if v is None:
            continue
        if not isinstance(v, list) or not all(isinstance(x, (str, int)) and not isinstance(x, bool) for x in v):
            P.append(f"banned.{k} must be a list of text, got {_kind(v)}")
            continue
        if k != "names":
            for pat in v:
                try:
                    re.compile(str(pat))
                except re.error as e:
                    P.append(f"banned.{k}: {str(pat)!r} is not a valid pattern ({e})")
    for k in ("dashes", "skip_code_blocks"):
        if k in b and not isinstance(b[k], bool):
            P.append(f"banned.{k} must be true or false, got {b[k]!r}")
    tg = plan.get("target")
    if isinstance(tg, dict):
        _as_text(tg, "date", "target", P)
    return P


def load_plan(path, root=None):
    """Read plan.yaml and fill defaults. Returns (plan, problems).

    A plan that cannot be read, or whose values have the wrong shape, raises PlanError: no script
    can work from it. Other problems are returned, so the checker can list them all. root is the
    project folder the paths in the plan are relative to; it is used to check their length."""
    path = Path(path)
    try:
        raw = load_file(path)
    except TextError as e:
        msg = "it" + e.msg[len(str(path)):] if e.msg.startswith(str(path) + " ") else e.msg
        raise PlanError(f"cannot read plan {path}: {msg}")
    except (OSError, ValueError, RecursionError) as e:   # YamlError and JSON errors are ValueErrors
        raise PlanError(f"cannot read plan {path}: {e}")
    if not isinstance(raw, dict):
        raise PlanError(f"plan {path} must be a mapping at the top level, such as `project:` followed by its keys")
    shape = type_problems(raw)
    if shape:
        shown = "; ".join(shape[:3]) + (f"; and {len(shape) - 3} more" if len(shape) > 3 else "")
        raise PlanError(f"plan {path} cannot be used: {shown}")
    plan = raw
    proj = plan.get("project") or {}
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
    if plan["limits"].get("spec_lines") is None:
        plan["limits"]["spec_lines"] = [80, 340]
    if "external" not in plan and "program" in plan:   # plans written before the rename keep working
        plan["external"] = plan.pop("program")
    plan["external"] = plan.get("external") or {}
    plan["external"]["items"] = plan["external"].get("items") or []
    plan["banned"] = plan.get("banned") or {}
    b = plan["banned"]
    if b.get("words") is None:
        b["words"] = list(DEFAULT_BANNED_WORDS)
    if b.get("phrases") is None:
        b["phrases"] = list(DEFAULT_BANNED_PHRASES)
    b["words"] = [str(w) for w in b["words"] if w not in (None, "")]
    b["phrases"] = [str(w) for w in b["phrases"] if w not in (None, "")]
    b["vendors"] = list(DEFAULT_BANNED_VENDORS) + [str(v) for v in (b.get("vendors") or []) if v]
    b["names"] = b.get("names") or []
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
        it["source_refs"] = it.get("source_refs") or []
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
            if d in derived and _is_int(it.get("id")):   # an item without an integer id is reported by validate_plan
                derived[d].append(it["id"])
    for it in plan["items"]:
        it["_derived_unblocks"] = sorted(derived.get(it.get("id"), []))
        if not it["unblocks"]:
            it["unblocks"] = it["_derived_unblocks"]
    # banned names come only from the plan: the people and advisors in it, and banned.names.
    # Full names match in any case. A single part of a name ("Will", "Long") matches only as a
    # capitalized word, and handles and ids only as written, so the words "will" and "long" in
    # ordinary prose are not findings. A capitalized name part at the start of a sentence still is.
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
    plan["_root"] = str(root) if root is not None else None
    return plan, validate_plan(plan)


MAX_WEEKS = 520           # ten years of working weeks: a larger target is a typing error
MAX_SIZE_DAYS = 260       # a year of working days for one item


def repo_ok(repo):
    """True for owner/name with GitHub's characters, and neither part "." or ".."."""
    m = re.fullmatch(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", str(repo))
    return bool(m) and not {m.group(1), m.group(2)} & {".", ".."}


def relative_inside(path):
    """True when path is relative and does not climb out of the folder it is relative to."""
    s = str(path).replace("\\", "/")
    if s.startswith("/") or re.match(r"^[A-Za-z]:", s) or s.startswith("~"):
        return False
    depth = 0
    for part in s.split("/"):
        if part == "..":
            depth -= 1
            if depth < 0:
                return False
        elif part not in ("", "."):
            depth += 1
    return True


def _is_date(s):
    try:
        parse_date(s)
        return True
    except ValueError:
        return False


def _is_weekend(s):
    return parse_date(s).weekday() >= 5


TITLE_FIELDS = ("id", "label", "lower")   # the fields item_title in github_sync.py supplies
MAX_TITLE = 256       # GitHub refuses a longer issue title
MAX_LABEL = 50        # GitHub refuses a longer label name
SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
ID_PREFIX_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(-[A-Za-z0-9_]+)*")


def format_title(fmt, tag_text, label):
    """An issue title from project.title_format. Only {id}, {label} and {lower} are filled in,
    and only after title_format_problem found nothing wrong with fmt."""
    return fmt.format(id=tag_text, label=label, lower=tag_text.lower())


def title_format_problem(fmt):
    """Why project.title_format cannot make issue titles, or None. It may hold the fields {id},
    {label} and {lower}, with no conversion and no format spec, and literal braces doubled. It
    must hold {id} or {lower}, so no two work items get the same title."""
    if not isinstance(fmt, str):
        return None   # reported by type_problems
    head = f"project.title_format {fmt!r}"
    try:
        parts = list(string.Formatter().parse(fmt))
    except ValueError as e:
        return f"{head} is not a valid title format ({e}). Use {{id}}, {{label}} and {{lower}}, and write a literal brace as {{{{ or }}}}"
    fields = []
    for _, name, spec, conv in parts:
        if name is None:
            continue
        if name not in TITLE_FIELDS or spec or conv:
            shown = "{" + name + ("!" + conv if conv else "") + (":" + spec if spec else "") + "}"
            return f"{head} uses {shown}. Only {{id}}, {{label}} and {{lower}} can be used, as written, and a literal brace is written {{{{ or }}}}"
        fields.append(name)
    if not {"id", "lower"} & set(fields):
        return f"{head} must hold {{id}} or {{lower}}, so that every work item issue gets its own title"
    return None


def _one_line(value):
    """True when a text value has no line break and no other control character."""
    return not isinstance(value, str) or not any(ord(c) < 32 or c == "\x7f" for c in value)


def _limits():
    """(longest name, longest path) in bytes that the file system takes."""
    if os.name == "nt":
        return 255, 260
    try:
        return os.pathconf("/", "PC_NAME_MAX"), os.pathconf("/", "PC_PATH_MAX")
    except (AttributeError, ValueError, OSError):
        return 255, 1024


def path_problems(plan):
    """Plan values that make a file or folder name, or a whole path, longer than the file system
    allows. A script would otherwise stop on "File name too long" halfway through its work."""
    name_max, path_max = _limits()
    proj = plan["project"]
    base = plan.get("_root") or (str(Path(plan["_path"]).resolve().parent) if plan.get("_path") else os.getcwd())
    cands = []   # (what, relative path)
    spec_dir = proj.get("spec_dir")
    if isinstance(spec_dir, str) and spec_dir.strip():
        cands.append(("project.spec_dir", f"{spec_dir}/README.md"))
        by_num = {m.get("number"): m for m in plan["milestones"]}
        for m in plan["milestones"]:
            if isinstance(m.get("folder"), str) and m["folder"]:
                cands.append((f"milestone {m.get('number')}: folder", f"{spec_dir}/{m['folder']}/milestone.md"))
        for it in plan["items"]:
            ms = by_num.get(it.get("milestone"))
            if _is_int(it.get("id")) and isinstance(it.get("slug"), str) and ms and isinstance(ms.get("folder"), str) and isinstance(proj.get("id_prefix"), str):
                name = f"{proj['id_prefix']}-{it['id']:02d}".lower() + f"-{it['slug']}.md"
                cands.append((f"item {it['id']}: slug", f"{spec_dir}/{ms['folder']}/{name}"))
    gt = proj.get("ground_truth")
    if isinstance(gt, str) and gt.strip():
        cands.append(("project.ground_truth", re.sub(r"\.md$", ".index.txt", gt) if gt.endswith(".md") else gt))
    for num, source in enumerate(plan.get("sources") or [], 1):
        if not isinstance(source, dict):
            continue
        for field in ("source_path", "path"):
            sp = source.get(field)
            if isinstance(sp, str) and sp.strip():
                rendered = re.sub(r"\.md$", ".index.txt", sp) if field == "path" and sp.endswith(".md") else sp
                cands.append((f"sources entry {num}.{field}", rendered))
    dsp = proj.get("dev_skill_path")
    if isinstance(dsp, str) and dsp.strip():
        cands.append(("project.dev_skill_path", f"{dsp}/references/ground-truth-map.md"))
    out, seen = [], set()
    for what, rel in cands:
        for part in rel.replace("\\", "/").split("/"):
            n = len(part.encode("utf-8", "replace"))
            if n > name_max and (what, part) not in seen:
                seen.add((what, part))
                out.append(f"{what} makes the file or folder name {part[:40]!r}... {n} bytes long, more than the {name_max} the file system allows. Shorten it")
        n = len((base.rstrip("/\\") + "/" + rel).encode("utf-8", "replace"))
        if n >= path_max and what not in seen:
            seen.add(what)
            out.append(f"{what} makes the path {rel[:40]!r}... {n} bytes long with the project folder, more than the {path_max} the file system allows. Shorten it")
    return out


def validate_plan(plan):
    P = []
    proj = plan["project"]
    for k in ("name", "slug", "id_prefix"):
        if not proj.get(k):
            P.append(f"project.{k} is required")
    if proj.get("slug") and not (SLUG_RE.fullmatch(proj["slug"]) and len(proj["slug"]) <= MAX_LABEL):
        P.append(f"project.slug must be lowercase words joined by hyphens, at most {MAX_LABEL} characters (it is the GitHub label of every issue), got {proj['slug'][:80]!r}")
    if proj.get("id_prefix") and not (ID_PREFIX_RE.fullmatch(proj["id_prefix"]) and len(proj["id_prefix"]) <= 20):
        P.append(f"project.id_prefix must be letters and digits that start with a letter, at most 20, such as WI, got {proj['id_prefix'][:40]!r}")
    for k in _PROJECT_TEXT:
        if not _one_line(proj.get(k)):
            P.append(f"project.{k} must be one line, with no line break or control character")
    tf = title_format_problem(proj.get("title_format"))
    if tf:
        P.append(tf)
    P += path_problems(plan)
    if proj.get("repo") and not repo_ok(proj["repo"]):
        P.append(f"project.repo must look like owner/name, got {proj['repo']!r}")
    for k, example in (("spec_dir", "docs/spec"), ("ground_truth", "docs/ground-truth/architecture.md")):
        v = str(proj.get(k) or "")
        if not v.strip():
            P.append(f"project.{k} is empty. Leave the line out for the default {example}, or give a path")
        elif not relative_inside(v):
            P.append(f"project.{k} must be a path inside the project, such as {example}, got {v!r}")
    source_ids = set()
    for num, source in enumerate(plan.get("sources") or [], 1):
        sid, path, source_path = source.get("id", ""), source.get("path", ""), source.get("source_path", "")
        if not sid:
            P.append(f"sources entry {num}: id is required, such as architecture or governance")
        elif not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", sid):
            P.append(f"sources entry {num}: id must be lowercase words joined by hyphens, got {sid!r}")
        elif sid in source_ids:
            P.append(f"sources entry {num}: duplicate id {sid!r}")
        source_ids.add(sid)
        if not source.get("name"):
            P.append(f"sources entry {num}: name is required")
        status = source.get("status") or "reviewed"
        if status not in ("reviewed", "unreadable"):
            P.append(f"sources entry {num}: status must be reviewed or unreadable, got {status!r}")
        if status == "reviewed" and not path:
            P.append(f"sources entry {num}: path is required when status is reviewed")
        elif path and not relative_inside(path):
            P.append(f"sources entry {num}.path must be inside the project, got {path!r}")
        if status == "unreadable" and not source.get("limit"):
            P.append(f"sources entry {num}: limit is required when status is unreadable")
        if source_path and not relative_inside(source_path):
            P.append(f"sources entry {num}.source_path must be inside the project, got {source_path!r}")
    reviewed_paths = {s.get("path") for s in plan.get("sources") or [] if (s.get("status") or "reviewed") == "reviewed"}
    if plan.get("sources") and not reviewed_paths:
        P.append("sources must include at least one reviewed entry. Continue with every readable source, but stop when none can be processed")
    elif plan.get("sources") and proj.get("ground_truth") not in reviewed_paths:
        P.append("project.ground_truth must match the path of one reviewed sources entry")
    for it in plan["items"]:
        refs = it.get("source_refs") or []
        seen_refs = set()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            sid = ref.get("source", "")
            if not sid:
                P.append(f"item {it.get('id')}: each source_refs entry needs source")
            elif sid not in source_ids:
                P.append(f"item {it.get('id')}: source_refs names unknown source {sid!r}")
            elif next((s for s in plan.get("sources") or [] if s.get("id") == sid and (s.get("status") or "reviewed") == "unreadable"), None):
                P.append(f"item {it.get('id')}: source_refs cannot cite unreadable source {sid!r}")
            elif sid in seen_refs:
                P.append(f"item {it.get('id')}: source_refs repeats source {sid!r}")
            seen_refs.add(sid)
            if not ref.get("sections"):
                P.append(f"item {it.get('id')}: source_refs for {sid or 'an unnamed source'} needs sections")
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
            P.append(f"tracks: each track needs id and label ({t})"[:300])
        elif len(t["id"]) > MAX_LABEL or not _one_line(t["id"]) or "," in t["id"]:
            P.append(f"tracks: id {t['id'][:60]!r} is a GitHub label, so it is one line with no comma, at most {MAX_LABEL} characters")
        if not _one_line(t.get("label")):
            P.append(f"tracks: {t.get('id')} label must be one line")
    for p in plan["people"]:
        al = p.get("allocation")
        if not isinstance(al, int) or isinstance(al, bool) or not (1 <= al <= 100):
            P.append(f"people: {p.get('id')} allocation must be a whole percent from 1 to 100, got {al!r}")
    for p in plan["people"]:
        if "derived" in p and not isinstance(p["derived"], bool):
            P.append(f"people: {p.get('id')} derived must be true or false")
    if isinstance(proj.get("epic_title"), str) and len(proj["epic_title"]) > MAX_TITLE:
        P.append(f"project.epic_title is {len(proj['epic_title'])} characters. GitHub takes at most {MAX_TITLE}")
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
        if "weeks" in tg and (not isinstance(tg["weeks"], int) or isinstance(tg["weeks"], bool) or not 1 <= tg["weeks"] <= MAX_WEEKS):
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
        for k in ("name", "folder"):
            if not _one_line(m.get(k)):
                P.append(f"milestone {n}: {k} must be one line, with no line break or control character")
        if isinstance(m.get("name"), str) and isinstance(proj.get("subepic_prefix"), str):
            title = f"{proj['subepic_prefix']} {n}, {m['name']}"
            if len(title) > MAX_TITLE:
                P.append(f"milestone {n}: the sub-epic title is {len(title)} characters. GitHub takes at most {MAX_TITLE}. Shorten the name")
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
        for k in ("start", "end"):
            if br.get(k) and not _is_date(br[k]):
                P.append(f"break {br.get('name')!r}: {k} is not a date (use YYYY-MM-DD): {br[k]!r}")
        if br.get("start") and br.get("end") and _is_date(br["start"]) and _is_date(br["end"]):
            bs, be = parse_date(br["start"]), parse_date(br["end"])
            if be < bs:
                P.append(f"break {br.get('name')!r}: end is before start")
            for m in plan["milestones"]:
                if m.get("start") and m.get("end") and _is_date(m["start"]) and _is_date(m["end"]):
                    if parse_date(m["start"]) <= be and bs <= parse_date(m["end"]):
                        P.append(f"break {br.get('name')!r} overlaps milestone {m.get('number')}")
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
        if not _one_line(it.get("label")):
            P.append(f"item {iid}: label must be one line, with no line break or control character")
        elif it.get("label") and isinstance(proj.get("id_prefix"), str) and not tf and isinstance(proj.get("title_format"), str):
            title = format_title(proj["title_format"], f"{proj['id_prefix']}-{iid:02d}", it["label"])
            if len(title) > MAX_TITLE:
                P.append(f"item {iid}: the issue title is {len(title)} characters. GitHub takes at most {MAX_TITLE}. Shorten the label")
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
        elif sized_days(it) > MAX_SIZE_DAYS:
            P.append(f"item {iid}: size of {sized_days(it):g} days is more than {MAX_SIZE_DAYS} working days. Split the item")
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
    try:
        print(msg, flush=True)
    except BrokenPipeError:
        # The reader closed the pipe, as `| head` does. Stop quietly: send the rest of the
        # output to the null device so the exit flush raises nothing, then exit.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        raise SystemExit(1)


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def repo_parts(plan, override=None):
    if override is not None and not str(override).strip():
        die("--repo is empty. Give the repository as owner/name, or leave out --repo to use project.repo in plan.yaml")
    repo = override if override is not None else plan["project"].get("repo")
    if not repo:
        die("no repository. Set project.repo in plan.yaml or pass --repo owner/name")
    if not repo_ok(repo):
        die(f"the repository must look like owner/name, such as my-org/my-repo, got {repo!r}")
    owner, name = str(repo).split("/", 1)
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


def ground_truth_sources(plan):
    """The rendered source documents in precedence order, highest first.

    Plans written before multiple sources were supported keep using project.ground_truth.
    """
    sources = plan.get("sources") or []
    if sources:
        return sources
    return [{
        "id": "ground-truth",
        "name": "Ground truth",
        "source_path": plan["project"]["ground_truth"],
        "path": plan["project"]["ground_truth"],
        "use": "Full specification. Section numbers in the work item files refer to it.",
        "status": "reviewed",
    }]


def rendered_sources(plan):
    return [source for source in ground_truth_sources(plan) if (source.get("status") or "reviewed") == "reviewed"]


def source_by_id(plan):
    return {source["id"]: source for source in ground_truth_sources(plan)}


def item_source_refs(plan, it):
    """Structured source references, with a legacy reference to project.ground_truth as fallback."""
    if it.get("source_refs"):
        return it["source_refs"]
    cite = it.get("ground_truth") or ""
    if not cite:
        return []
    reviewed = rendered_sources(plan)
    if not reviewed:
        return []
    primary = next((s for s in reviewed if s.get("path") == plan["project"]["ground_truth"]), reviewed[0])
    return [{"source": primary["id"], "sections": cite}]


def ground_truth_citation(plan, it):
    """Human-readable source citations for specification headers and GitHub issues."""
    refs = item_source_refs(plan, it)
    if not refs:
        return ""
    if not it.get("source_refs"):
        return it.get("ground_truth") or ""
    sources = source_by_id(plan)
    parts = []
    for ref in refs:
        source = sources.get(ref.get("source"), {})
        parts.append(f"{source.get('name', ref.get('source', 'Source'))}: Sections {ref.get('sections', '')}")
    return "; ".join(parts)


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
        ("Ground truth", ground_truth_citation(plan, it) or "To be cited"),
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
    "The first proves the whole path with the least behavior, and the last proves the project can be released and run.",
    "A milestone holds items from every track the capability crosses, and the tracks meet at a named joint check before the demonstration. "
    "A milestone that stays inside one track says why.",
    "The exit gate is one sentence the stakeholders can check live. The engineers whose tracks meet give the demonstration together, and the plan says what they show.",
    "Inside a milestone the shared contract comes first, so both tracks can start without waiting. The first week leaves nobody idle.",
    "Each engineer's consecutive items stay in one part of the system, a theme. Related items for the same person sit in adjacent days to cut context switching.",
    "Size in days divided by allocation gives calendar working days: four days at 60 percent is nearly seven working days. "
    "Nobody is planned past 100 percent of allocated capacity in a work unit, aim for about 80, and days off and breaks are real.",
    "Slack sits before every checkpoint and demonstration. An item that completes on its checkpoint date has none.",
    "The critical path is checked for who owns each item on it, because one absent owner there would move the end date. If it runs through one person, the plan says so and offers an alternative.",
    "Work outside the plan, owned outside the team, keeps its ids as gaps in the numbering.",
    "The plan records its rationale where anyone can argue with it: for each milestone, why these items form it and what the joint demonstration proves, "
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
        lines.append(f"- Feature flag. `{c['feature_flag']}` gates the new behavior. Off by default until the release. With the flag off, nothing existing changes.")
    if c.get("test_command"):
        lines.append(f"- Tests. Run `{c['test_command']}`. New suites accompany each work item.")
    if c.get("lint_command"):
        lines.append(f"- Lint and format. `{c['lint_command']}` passes on every pull request.")
    for extra in c.get("extra") or []:
        lines.append(f"- {extra}")
    lines.append("- Documentation style in this folder. Sentence-case headings, short sentences, no em dashes or en dashes, no names of people. Owners and dates live in the GitHub issues.")
    lines.append("- Existing behavior is not changed by a work item unless its file says so.")
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
    serialized here: the load table covers that."""
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
            if d in items and d != n and d not in stack:   # a self-dependency or a cycle is reported by validate_plan
                fin = visit(d, stack + (n,))[1] + _dt.timedelta(days=1)
                if fin > start:
                    start, prev = fin, d
        while not _is_working(start, off):
            start += _dt.timedelta(days=1)
        need = needed_days(plan, it)
        finish, done = start, 0.0
        while (finish - start).days < 40000:   # a bound for a size the validator rejects
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
    while n is not None and n not in chain:
        chain.append(n)
        n = via.get(n)
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
    if _is_int(tg.get("weeks")) and 1 <= tg["weeks"] <= MAX_WEEKS:
        start = parse_date(plan["milestones"][0]["start"])
        break_days = sum((parse_date(b["end"]) - parse_date(b["start"])).days + 1 for b in plan["breaks"] if _is_date(b.get("start")) and _is_date(b.get("end")))
        break_weeks = -(-break_days // 7)
        d = start + _dt.timedelta(days=7 * (tg["weeks"] + break_weeks) - 3)
        return d, f"{tg['weeks']} working weeks plus {break_weeks} break week(s), which ends {fmt_date(d)}"
    return None, "no target"


if __name__ == "__main__":
    print(__doc__)
