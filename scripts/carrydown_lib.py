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


# ---------------------------------------------------------------------------
# Release helpers: thin wrappers over release_schema.py, which holds the real code so the
# independent verifier can carry it unchanged. release_schema is imported when a wrapper runs, so
# a copy of this file that sits without it (the checker copy in a project) still loads.
# ---------------------------------------------------------------------------

def _schema():
    try:
        import release_schema as module
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import release_schema as module
    return module


def normalize_section_text(text):
    """A source section as the compiler and the verifier compare it: CRLF to LF, trailing blanks
    removed from each line, exactly one trailing newline."""
    return _schema().normalize_section_text(text)


def sha256_text(text):
    """The lowercase hex SHA-256 of text, encoded as UTF-8."""
    return _schema().sha256_text(text)


def sha256_file(path):
    """The lowercase hex SHA-256 of a regular file. A folder, a pipe, a device or a file that
    cannot be read stops with a one-line TextError message."""
    why = regular_file_problem(path)
    if why:
        raise TextError(why)
    try:
        return _schema().sha256_file(path)
    except FileNotFoundError:
        raise TextError(f"{path} does not exist")
    except OSError as e:
        raise TextError(f"cannot read {path}: {e.strerror or e}")


def canonical_json(value):
    """Canonical JSON bytes: sorted keys, no insignificant whitespace, UTF-8, one trailing LF.
    Duplicate keys in bytes input, non-finite numbers and unknown values raise SchemaError."""
    return _schema().canonical_json(value)


def _repository_top(root):
    """The folder of the engineering repository that holds root: the nearest folder at or above
    root with a .git entry, or root itself when there is none."""
    base = Path(os.path.realpath(str(root)))
    for folder in [base] + list(base.parents):
        if (folder / ".git").exists():
            return folder
    return base


def path_inside_repository(root, candidate):
    """True when candidate lies inside the project folder root or inside the engineering repository
    that holds root. Symbolic links are resolved first, so a link cannot hide the location."""
    base = Path(root).expanduser().resolve()
    target = Path(os.path.realpath(str(candidate)))
    for repo in {base, _repository_top(base)}:
        if target == repo or repo in target.parents:
            return True
    return False


def workspace_root(root):
    """The owner's private workspace for the project at root, as (path, None), or (None, reason).

    The path is the `workspace:` line of .carrydown/local.yaml under root. That file is untracked
    and read only by scripts the owner runs, never from plan.yaml or any tracked file. The reason is
    a fixed code: workspace-unavailable when the file, the line or the folder is missing or unusable,
    and workspace-inside-repository when the path resolves inside the engineering repository."""
    if root_problem(root):
        return None, "workspace-unavailable"
    base = Path(root).expanduser().resolve()
    pointer = base / ".carrydown" / "local.yaml"
    if regular_file_problem(pointer) or not pointer.exists():
        return None, "workspace-unavailable"
    try:
        data = load_file(pointer)
    except (YamlError, TextError):
        return None, "workspace-unavailable"
    value = data.get("workspace") if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        return None, "workspace-unavailable"
    try:
        candidate = Path(os.path.realpath(str((base / Path(value.strip()).expanduser()))))
    except (OSError, ValueError, RuntimeError):
        return None, "workspace-unavailable"
    if path_inside_repository(base, candidate):
        return None, "workspace-inside-repository"
    if root_problem(candidate):
        return None, "workspace-unavailable"
    return candidate, None


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


# The plan layouts. A plan written before the confidential ground truth work has no plan_format and
# no project.handling block: it is legacy and keeps its old rules. A plan with plan_format 2 is
# validated in one of two views. The workspace view is the owner's working plan. The released view
# is the exported plan that the engineering repository holds and the independent verifier checks.
PLAN_FORMAT = 2
PLAN_VIEWS = ("workspace", "released")
CLASSIFICATIONS = ("repo-readers", "restricted", "public")
RETAIN_VALUES = ("keep", "delete-after-release")
HANDLING_STATES = ("legacy", "migrated")
ENGINEER_EDITS = ("allowed", "request-only")
HANDLING_KEYS = ("policy_version", "repo_audience_approved", "approvers", "retain_raw_inputs", "state",
                 "downstream", "offline_grace_days", "engineer_edits")
RELEASED_HANDLING_KEYS = ("policy_version", "repo_audience_approved", "state", "offline_grace_days", "engineer_edits")
DOWNSTREAM_FLAGS = ("assignees", "capacity_summary", "evidence")
# Personal facts. They live in people.yaml in the private workspace and never in a plan.yaml of a
# migrated project (E1 of the specification). Schema locations are reported as people:<id>:<field>.
STAFFING_KEYS = ("name", "github", "skills", "preferences", "assignment_rationale", "days_off", "allocation", "start")
PRIVATE_SOURCE_KEYS = ("path", "source_path", "classification", "content_sha256", "rendering_sha256")
_LOGIN_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\Z")
_HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")


class PlanViewError(ValueError):
    """A plan was given to a function that needs another view, or a merged staffing view was given
    where only the stored plan may go. The fixed reason code is schema-view-mismatch."""

    code = "schema-view-mismatch"


def is_modern(plan):
    """True for a plan in the plan_format 2 layout: it declares plan_format or plan_view, or its
    project.handling block says state: migrated. Everything else is a legacy plan."""
    if not isinstance(plan, dict):
        return False
    if plan.get("plan_format") is not None or plan.get("plan_view") is not None:
        return True
    proj = plan.get("project")
    handling = proj.get("handling") if isinstance(proj, dict) else None
    return isinstance(handling, dict) and handling.get("state") == "migrated"


def plan_mode(plan, view=None):
    """legacy, workspace or released: the rules validate_plan applies. view is the view the caller
    requires (None to accept the one the plan declares). A legacy plan is checked by the legacy
    rules unless a view is required."""
    if view is not None and view not in PLAN_VIEWS:
        raise ValueError(f"unknown plan view {view!r}. Use one of: {', '.join(PLAN_VIEWS)}")
    if view is not None:
        return view
    if not is_modern(plan):
        return "legacy"
    declared = plan.get("plan_view")
    return declared if declared in PLAN_VIEWS else "workspace"


def staffing_loaded(plan):
    """True when the people facts that capacity, dates and names checks need are in the plan: a
    legacy plan holds them itself, and a migrated plan holds them only after people.yaml is merged."""
    return not plan.get("_modern") or plan.get("_people_overlay") is not None


# Fields read as text, per list of the plan. A number given for one of them is taken as text,
# so `label: 2027` works. None means the field is empty and is treated as left out.
_TEXT_FIELDS = {
    "tracks": ("id", "label", "color"),
    "people": ("id", "name", "github", "track", "start", "assignment_rationale"),
    "advisors": ("id", "name", "github", "note"),
    "milestones": ("name", "folder", "start", "end", "demo", "gate"),
    "breaks": ("name", "start", "end"),
    "checkpoints": ("date", "name", "joint_check"),
    "items": ("slug", "label", "track", "owner", "complete_by", "size", "checkpoint", "ground_truth", "external_input", "program_input"),
    "external.items": ("label", "note"),
    "sources": ("id", "name", "source_path", "path", "use", "version", "status", "limit", "classification",
                "content_sha256", "rendering_sha256"),
}
_TEXT_LIST_FIELDS = {
    "tracks": ("skill_needs",),
    "people": ("skills", "preferences"),
    "items": ("skill_needs",),
}
_INT_FIELDS = {"milestones": ("number",), "items": ("id", "milestone"), "external.items": ("id",)}
_PROJECT_TEXT = ("name", "slug", "id_prefix", "repo", "branch", "epic_title", "subepic_prefix", "title_format",
                 "spec_dir", "ground_truth", "project_title", "dev_skill", "dev_skill_path")


def _as_text(row, key, where, P, person=False):
    """Keep a text field as text: a number becomes text, empty means left out, anything else is a problem.
    person=True names the person and the key and says nothing else: a record of a person is never echoed."""
    if key not in row:
        return
    v = row[key]
    if v is None:
        del row[key]
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        row[key] = str(v)
    elif not isinstance(v, str):
        if person:
            P.append(f"{where}: {key} has the wrong type")
        else:
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
    reserved = sorted(k for k in plan if isinstance(k, str) and k.startswith("_"))
    if reserved:
        P.append(f"plan keys that start with an underscore are reserved for the scripts: {', '.join(reserved[:5])}")
    if P:
        return P
    modern = is_modern(plan)   # a migrated plan's staffing keys are reported by validate_plan, so they are left as written
    proj = plan.get("project") or {}
    for k in _PROJECT_TEXT:
        _as_text(proj, k, "project", P)
    handling = proj.get("handling")
    if handling is not None and not isinstance(handling, dict):
        P.append(f"project.handling must be a mapping of keys, got {_kind(handling)}")
    elif isinstance(handling, dict) and handling.get("downstream") is not None and not isinstance(handling["downstream"], dict):
        P.append(f"project.handling.downstream must be a mapping of keys, got {_kind(handling['downstream'])}")
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
                P.append(f"{group}: entry {n} must be a mapping such as `- id: ...`, got {_kind(row)}")   # the entry itself is never echoed
                continue
            where = f"{group} entry {n}"
            kept = modern and group in ("people", "advisors")   # reported by key, never converted or echoed
            is_person = group in ("people", "advisors")
            if is_person:   # a person is named by id, or by position when the id is missing or not text
                who = row.get("id") if isinstance(row.get("id"), str) and row.get("id") else f"#{n}"
                where = f"{'person' if group == 'people' else 'advisor'} {who}"
            for k in _TEXT_FIELDS.get(group, ()):
                if kept and (group == "advisors" or k in STAFFING_KEYS):
                    continue
                _as_text(row, k, where, P, person=is_person)
            for k in _TEXT_LIST_FIELDS.get(group, ()):
                if kept:
                    continue
                v = row.get(k)
                if v is None:
                    continue
                if isinstance(v, str):
                    row[k] = [v] if v.strip() else []
                elif not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                    if is_person:
                        P.append(f"{where}: {k} has the wrong type")
                    else:
                        P.append(f"{where}.{k} must be text or a list of text, got {_kind(v)}")
            for k in _INT_FIELDS.get(group, ()):
                if row.get(k) is not None and not _is_int(row[k]):
                    P.append(f"{where}.{k} must be a whole number, got {row[k]!r}")
            for k in ("depends", "unblocks") if group == "items" else ():
                v = row.get(k)
                if v is None:
                    continue
                if not isinstance(v, list) or not all(_is_int(d) for d in v):
                    P.append(f"{where}.{k} must be a list of item ids, such as [1, 3], got {v!r}")
            if group == "people" and not kept and row.get("days_off") is not None:
                v = row["days_off"]
                if not isinstance(v, list) or not all(isinstance(d, (str, int)) and not isinstance(d, bool) for d in v):
                    P.append(f"{where}: days_off has the wrong type")
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


def load_plan(path, root=None, view=None):
    """Read plan.yaml and fill defaults. Returns (plan, problems).

    A plan that cannot be read, or whose values have the wrong shape, raises PlanError: no script
    can work from it. Other problems are returned, so the checker can list them all. root is the
    project folder the paths in the plan are relative to; it is used to check their length.

    view is the layout the caller requires: workspace, released, or None to accept the one the plan
    declares (a plan with no plan_format is legacy). The stored plan is validated in that view. The
    returned plan holds no staffing facts when it is migrated: it names people by id only. Use
    load_plan_with_people for the owner-side calculations that need names, allocation and days off."""
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
    return plan_from_data(raw, path, root, view)


def plan_from_data(raw, path="plan.yaml", root=None, view=None):
    """The part of load_plan that follows reading the file: check the shape, fill the defaults and
    validate in the view. raw is changed in place, so pass a copy to keep the original. Returns
    (plan, problems). Used on a projected plan before it is written, so the same rules apply."""
    shape = type_problems(raw)
    if shape:
        shown = "; ".join(shape[:3]) + (f"; and {len(shape) - 3} more" if len(shape) > 3 else "")
        raise PlanError(f"plan {path} cannot be used: {shown}")
    plan = raw
    modern = is_modern(plan)
    mode = plan_mode(plan, view)
    proj = plan.get("project") or {}
    plan["project"] = proj
    proj.setdefault("branch", "main")
    proj.setdefault("spec_dir", "docs/spec")
    proj.setdefault("subepic_prefix", "Milestone")
    proj.setdefault("title_format", "{id} {label}")
    proj.setdefault("epic", None)
    if mode != "released":
        proj.setdefault("ground_truth", "docs/ground-truth/architecture.md")   # a released plan invents no path
    proj.setdefault("project_title", f"{proj.get('name', 'Plan')} plan")
    proj.setdefault("epic_title", f"{proj.get('name', 'Plan')}, development plan")
    # A migrated plan has no advisors list. A key that is there is reported by validate_plan.
    for k in ("people", "tracks", "milestones", "breaks", "checkpoints", "items") + (() if modern else ("advisors",)):
        if plan.get(k) is None:
            plan[k] = []
    for person in plan["people"]:
        if modern:
            continue   # no staffing defaults: allocation, skills and the rest come from people.yaml
        if person.get("allocation") is None:
            person["allocation"] = 100
        person["skills"] = list(person.get("skills") or [])
        person["preferences"] = list(person.get("preferences") or [])
        person["assignment_rationale"] = _text(person.get("assignment_rationale"))
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
        it["skill_needs"] = list(it.get("skill_needs") or [])
    # the planning rationale: why each milestone holds its items, what the joint demonstration
    # shows, and why each track's items are in their order. Text, folded to one line.
    for m in plan["milestones"]:
        if isinstance(m, dict):
            for k in RATIONALE_MILESTONE_KEYS:
                m[k] = _text(m.get(k))
    for t in plan["tracks"]:
        if isinstance(t, dict):
            t["order_rationale"] = _text(t.get("order_rationale"))
            t["skill_needs"] = list(t.get("skill_needs") or [])
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
    _banned_names(plan)
    plan["_path"] = str(path)
    plan["_root"] = str(root) if root is not None else None
    plan["_modern"] = modern
    plan["_view"] = mode
    plan["_people_overlay"] = None   # set by load_plan_with_people on the merged copy only
    problems = validate_plan(plan, view)
    if root is not None and not modern and (Path(root) / ".carrydown" / "release-policy.yaml").is_file():
        # An enrolled repository can never be legacy: deleting project.handling cannot downgrade it.
        problems.append("project.handling is missing, but this repository has .carrydown/release-policy.yaml "
                        "(enrolled-project-missing-handling). Restore the handling block")
    return plan, problems


def _banned_names(plan):
    """Fill plan["_banned_names"] and plan["_banned_exact"], the names the specifications must not hold.

    They come only from the plan: banned.names, and the people and advisors in it. Full names match in
    any case. A single part of a name ("Will", "Long") matches only as a capitalized word, and handles
    and ids only as written, so the words "will" and "long" in ordinary prose are not findings. A
    capitalized name part at the start of a sentence still is. A migrated plan holds ids only, so
    before people.yaml is merged the check is built from the ids and says so (staffing_loaded)."""
    names = [str(n) for n in plan["banned"]["names"] if n]
    exact = []
    for p in list(plan.get("people") or []) + list(plan.get("advisors") or []):
        if not isinstance(p, dict) or p.get("derived"):
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


# ---------------------------------------------------------------------------
# Staffing: people.yaml in the private workspace, merged for the owner's calculations only
# ---------------------------------------------------------------------------

def _yaml_error_text(error):
    """A YAML error as the line it names and nothing else: the reader's own messages quote the text
    of the line, and in people.yaml that text is a personal fact."""
    m = re.match(r"line (\d+):", str(error))
    return f"syntax error near line {m.group(1)}" if m else "syntax error"


def people_file_problem(path):
    """Why path cannot be the people file, or None. The message holds no content of the file."""
    why = regular_file_problem(path)
    if why:
        return why
    if not exists(path):
        return f"people file {path} does not exist"
    return None


def load_people_file(path):
    """Read people.yaml. Returns (doc, problems): doc is {"people": [...], "advisors": [...]} with
    the text fields as text and the lists as lists. A file that cannot be read raises PlanError with
    a message that quotes none of its text. Problems name a person by id and a field by key, and
    never print a value."""
    why = people_file_problem(path)
    if why:
        raise PlanError(why)
    try:
        raw = load_file(path)
    except TextError as e:
        raise PlanError(f"cannot read people file {path}: {e.msg[len(str(path)) + 1:] if e.msg.startswith(str(path) + ' ') else 'it is not UTF-8 text'}")
    except YamlError as e:
        raise PlanError(f"cannot read people file {path}: {_yaml_error_text(e)}")
    except (OSError, ValueError, RecursionError):
        raise PlanError(f"cannot read people file {path}")
    P = []
    if not isinstance(raw, dict):
        raise PlanError(f"people file {path} must be a mapping at the top level, such as `people:` followed by its entries")
    for k in raw:
        if k not in ("people", "advisors"):
            P.append(f"people.yaml: unknown key {str(k)[:40]!r}. Use people and advisors")
    out = {"people": [], "advisors": []}
    for group in ("people", "advisors"):
        rows = raw.get(group)
        if rows is None:
            continue
        if not isinstance(rows, list):
            P.append(f"people.yaml: {group} must be a list of entries starting with -")
            continue
        for n, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                P.append(f"people.yaml: {group} entry {n} must be a mapping such as `- id: ...`")
                continue
            who = row.get("id") if isinstance(row.get("id"), str) and row.get("id") else f"#{n}"
            clean = {}
            for k, v in row.items():
                if v is None:
                    continue
                if k in ("id", "name", "github", "track", "assignment_rationale", "start", "role", "note"):
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        v = str(v)
                    if not isinstance(v, str):
                        P.append(f"people.yaml {'person' if group == 'people' else 'advisor'} {who}: {k} has the wrong type")
                        continue
                elif k in ("skills", "preferences"):
                    if isinstance(v, str):
                        v = [v] if v.strip() else []
                    elif not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                        P.append(f"people.yaml person {who}: {k} has the wrong type")
                        continue
                elif k == "days_off":
                    if not isinstance(v, list) or not all(isinstance(x, (str, int)) and not isinstance(x, bool) for x in v):
                        P.append(f"people.yaml person {who}: days_off has the wrong type")
                        continue
                    v = [str(x) for x in v]
                # allocation stays as written: staffing_problems checks it
                clean[k] = v
            if group == "people" and not clean.get("id"):
                P.append(f"people.yaml: people entry {n} has no id. Each person needs the id used in plan.yaml")
            out[group].append(clean)
    return out, P


def resolve_people_path(root, people_path=None):
    """Where the staffing overlay is, as (path, reason). An explicit people_path is used as given. Without
    one the file is people.yaml in the private workspace of the project at root. There is no other
    place to look, and never a tracked file of the project: reason is then workspace-unavailable or
    workspace-inside-repository, and path is None."""
    if people_path is not None:
        if not str(people_path).strip():
            raise PlanError("--people is empty. Give the path of people.yaml, or leave it out to use the private workspace")
        return Path(people_path).expanduser(), None
    if root is None:
        return None, "workspace-unavailable"
    ws, why = workspace_root(root)
    if ws is None:
        return None, why
    candidate = ws / "people.yaml"
    if candidate.is_file():
        return candidate, None
    return None, "workspace-unavailable"


def merge_people(plan, people_path):
    """Merge people.yaml into a copy of a stored plan, by person id. Returns (merged, problems).

    The merged copy is the calculation view: names, allocation, start dates, days off, skills and the
    rest, for capacity, dates and names checks on the owner's machine. The stored plan is not
    changed. The copy is marked with _staffing_merged, and project_released_plan refuses it, so it
    can never be projected or dumped into a release. merged["_people_overlay"] is the path of the file."""
    import copy
    doc, problems = load_people_file(people_path)
    merged = copy.deepcopy(plan)
    by_id = {}
    for entry in doc["people"]:
        pid = entry.get("id")
        if pid in by_id:
            problems.append(f"people.yaml: person {pid} appears more than once")
        by_id[pid] = entry
    plan_ids = {p.get("id") for p in merged["people"]}
    for pid in by_id:
        if pid and pid not in plan_ids:
            problems.append(f"people.yaml: person {pid} is not a person in plan.yaml")
    tracks = {t.get("id"): t for t in merged["tracks"]}
    for p in merged["people"]:
        entry = by_id.get(p.get("id"))
        if entry is None:
            if not p.get("derived"):
                problems.append(f"people.yaml has no entry for person {p.get('id')}")
        else:
            for k in STAFFING_KEYS:
                if k in entry:
                    p[k] = entry[k]
            track = entry.get("track")
            wanted = tracks.get(p.get("track")) or {}
            if track and str(track).casefold() not in {str(p.get("track")).casefold(), str(wanted.get("label") or "").casefold()}:
                problems.append(f"people.yaml: the track of person {p.get('id')} does not match plan.yaml")
        if p.get("allocation") is None:
            p["allocation"] = 100
        p["skills"] = list(p.get("skills") or [])
        p["preferences"] = list(p.get("preferences") or [])
        p["assignment_rationale"] = _text(p.get("assignment_rationale"))
    merged["advisors"] = doc["advisors"]
    merged["_people_overlay"] = str(people_path)
    merged["_staffing_merged"] = True
    _banned_names(merged)
    problems += staffing_problems(merged, show_values=False)
    return merged, problems


def load_plan_with_people(path, root=None, people_path=None, view=None):
    """load_plan, then the staffing overlay merged in for the owner's calculations. Returns
    (plan, problems). The stored plan is validated first, in its view. When there is no overlay, or
    the plan is a legacy plan that holds its own staffing, the stored plan comes back unmerged:
    check plan["_people_overlay"] and staffing_loaded(plan) to know whether capacity, dates and
    names can be checked. The overlay is people_path when given, else people.yaml in the private
    workspace of the project at root. A tracked people.yaml is never a fallback."""
    plan, problems = load_plan(path, root, view)
    if not plan["_modern"] and people_path is None:
        return plan, problems
    found, _ = resolve_people_path(root, people_path)
    if found is None:
        return plan, problems
    merged, more = merge_people(plan, found)
    return merged, problems + more


def downstream_flags(plan):
    """What may flow downstream from this plan, as {"assignees": bool, "capacity_summary": bool}.

    They are read from project.handling.downstream until the release request carries them (the
    release work package moves them there). A legacy plan keeps today's behavior: both are true. A
    migrated plan defaults to false for both, so a number of people or a login reaches GitHub only
    when the owner said so."""
    handling = (plan.get("project") or {}).get("handling")
    down = handling.get("downstream") if isinstance(handling, dict) else None
    legacy = not plan.get("_modern", is_modern(plan))
    out = {}
    for k in ("assignees", "capacity_summary"):
        v = down.get(k) if isinstance(down, dict) else None
        out[k] = v if isinstance(v, bool) else legacy
    return out


def assignee_login(plan, item):
    """The GitHub login of the owner of item, or "". It is read from the plan's own people only: a
    legacy plan holds the login, and a migrated plan never does, so the GitHub scripts resolve no
    login for it. Logins for a migrated project are approved values in the release payloads, which
    the release work package builds from people.yaml."""
    if not item:
        return ""
    for p in plan.get("people") or []:
        if p.get("id") == item.get("owner"):
            return str(p.get("github") or "")
    return ""


def payload_assignees(staffed_plan, item):
    """Logins that may go into an issue payload for item: [] unless the plan's downstream.assignees is
    true and the staffing overlay is merged. The release work package calls this at prepare."""
    if not staffed_plan.get("_people_overlay") and staffed_plan.get("_modern"):
        return []
    if not downstream_flags(staffed_plan)["assignees"]:
        return []
    login = assignee_login(staffed_plan, item)
    return [login] if login else []


# ---------------------------------------------------------------------------
# The released plan: an allowlist projection of the workspace plan
# ---------------------------------------------------------------------------

RELEASED_PROJECT_KEYS = ("name", "slug", "id_prefix", "repo", "branch", "epic", "epic_title", "subepic_prefix",
                         "title_format", "spec_dir", "project_title", "dev_skill", "dev_skill_path")
RELEASED_SOURCE_KEYS = ("id", "name", "version")
RELEASED_PERSON_KEYS = ("id", "track", "derived")
RELEASED_ITEM_KEYS = ("id", "slug", "label", "milestone", "track", "owner", "theme", "complete_by", "size", "depends",
                      "unblocks", "checkpoint", "external_input", "source_refs", "skill_needs", "state", "ground_truth")


def restricted_item(item):
    """True for a work item the owner marked restricted. It is left out of the released plan."""
    return isinstance(item, dict) and item.get("restricted") is True


def _restricted_hook(workspace_plan, projected, omitted):
    """The extension point for restricted items. omitted holds the ids of the items left out of
    projected. A later work package replaces each omitted item that another item depends on with an
    external item whose only text is the owner's restricted_summary. Today an item that depends on
    an omitted one makes the released validation report it, which is the safe failure."""
    return projected


def _released_item(plan, item, omitted=()):
    """One work item of the released plan. A citation written as text (the older ground_truth line) is
    resolved here, against the workspace plan's sources, into structured source_refs, because the
    released plan is checked against the approved bundle of each item and has no source paths to read."""
    import copy
    out = {k: copy.deepcopy(item[k]) for k in RELEASED_ITEM_KEYS if k in item}
    if out.get("unblocks"):
        out["unblocks"] = [u for u in out["unblocks"] if u not in omitted]   # no trace of an omitted item
    refs = item_source_refs(plan, item)
    if refs and not item.get("source_refs"):
        out["source_refs"] = copy.deepcopy(refs)
        out.pop("ground_truth", None)
    return out


def project_released_plan(workspace_plan):
    """The released plan for a validated workspace plan: a new object built from an allowlist.

    Only the keys named in the RELEASED_ tuples, and the milestones, tracks, checkpoints and the
    like, are copied (deeply), so a key added to the workspace plan later is private until someone
    adds it here. People are reduced to id, track and derived; there is no advisors list; sources
    to id, name and version; the handling block to the answer to the one question and the policy
    version; banned.names is left out. Items marked restricted are omitted (restricted_item).

    The input is not changed. The staffing-merged view (load_plan_with_people) is refused: it holds
    personal facts and must never be serialized for a release. Validate the result with
    released_plan_problems before writing it into a snapshot."""
    import copy
    plan = workspace_plan
    if plan.get("_staffing_merged") or plan.get("_people_overlay"):
        raise PlanViewError("the staffing-merged plan cannot be projected. Project the stored workspace plan (schema-view-mismatch)")
    if not is_modern(plan):
        raise PlanViewError("only a migrated workspace plan can be projected. Run step 0 of the ground-truth skill first (schema-view-mismatch)")
    declared = plan.get("_view") or plan.get("plan_view")
    if declared != "workspace":
        raise PlanViewError("only a workspace plan can be projected (schema-view-mismatch)")
    proj = plan["project"]
    out_project = {k: copy.deepcopy(proj[k]) for k in RELEASED_PROJECT_KEYS if k in proj}
    handling = proj.get("handling") or {}
    out_project["handling"] = {k: copy.deepcopy(handling[k]) for k in RELEASED_HANDLING_KEYS if k in handling}
    banned = plan.get("banned") or {}
    out_banned = {}
    if banned.get("words") is not None and list(banned["words"]) != DEFAULT_BANNED_WORDS:
        out_banned["words"] = list(banned["words"])
    if banned.get("phrases") is not None and list(banned["phrases"]) != DEFAULT_BANNED_PHRASES:
        out_banned["phrases"] = list(banned["phrases"])
    custom = [v for v in (banned.get("vendors") or []) if v not in DEFAULT_BANNED_VENDORS]
    if custom:
        out_banned["vendors"] = custom
    for k in ("dashes", "skip_code_blocks"):
        if k in banned:
            out_banned[k] = banned[k]
    omitted = [it.get("id") for it in plan.get("items") or [] if restricted_item(it)]
    out = {
        "plan_format": PLAN_FORMAT,
        "plan_view": "released",
        "project": out_project,
        "sources": [{k: copy.deepcopy(s[k]) for k in RELEASED_SOURCE_KEYS if k in s} for s in plan.get("sources") or []],
        "conventions": copy.deepcopy(plan.get("conventions") or {}),
        "tracks": copy.deepcopy(plan.get("tracks") or []),
        "people": [{k: copy.deepcopy(p[k]) for k in RELEASED_PERSON_KEYS if k in p} for p in plan.get("people") or []],
        "milestones": copy.deepcopy(plan.get("milestones") or []),
        "breaks": copy.deepcopy(plan.get("breaks") or []),
        "checkpoints": copy.deepcopy(plan.get("checkpoints") or []),
        "items": [_released_item(plan, it, omitted) for it in plan.get("items") or [] if not restricted_item(it)],
        "external": copy.deepcopy(plan.get("external") or {"items": []}),
        "limits": copy.deepcopy(plan.get("limits") or {}),
    }
    if plan.get("target"):
        out["target"] = copy.deepcopy(plan["target"])
    if out_banned:
        out["banned"] = out_banned
    return _restricted_hook(plan, out, omitted)


def released_plan_problems(projected):
    """Problems with a projected plan, checked in the released view as the verifier checks it. The
    projection is copied first. Returns a list of one-line messages, empty when it is valid."""
    import copy
    _, problems = plan_from_data(copy.deepcopy(projected), "released plan", None, "released")
    return problems


MAX_WEEKS = 520          # ten years of working weeks: a larger target is a typing error
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


def _view_problems(plan, view):
    """Problems with the declared layout: plan_format, plan_view and the handling block's state,
    against the view the caller requires. A mismatch carries the reason code schema-view-mismatch."""
    P = []
    modern = is_modern(plan)
    if not modern:
        if view is not None:
            P.append(f"plan_format: {PLAN_FORMAT} and plan_view: {view} are required for the {view} view, and project.handling "
                     "must say state: migrated (schema-view-mismatch). Run step 0 of the ground-truth skill to migrate the plan")
        return P
    fmt = plan.get("plan_format")
    if fmt is None:
        P.append(f"plan_format: {PLAN_FORMAT} is required (a migrated plan declares its layout)")
    elif not _is_int(fmt) or fmt != PLAN_FORMAT:
        P.append(f"plan_format must be {PLAN_FORMAT}, got {fmt!r}. This script does not know that layout")
    declared = plan.get("plan_view")
    if declared is None:
        P.append("plan_view is required: workspace or released")
    elif declared not in PLAN_VIEWS:
        P.append(f"plan_view must be workspace or released, got {declared!r}")
    elif view is not None and declared != view:
        P.append(f"plan_view is {declared}, but this check needs the {view} view (schema-view-mismatch)")
    return P


def _handling_problems(plan, mode):
    """Problems with project.handling, the owner's answer to the one question. Values are never
    echoed except the fixed vocabulary words."""
    P = []
    proj = plan["project"]
    h = proj.get("handling")
    modern = is_modern(plan)
    if h is None:
        if modern:
            P.append("project.handling is required in a migrated plan: policy_version, repo_audience_approved and state")
        return P
    if not isinstance(h, dict):
        return P   # reported by type_problems
    allowed = RELEASED_HANDLING_KEYS if mode == "released" else HANDLING_KEYS
    for k in h:
        if k in HANDLING_KEYS and k not in allowed:
            P.append(f"project.handling.{k} is not allowed in a released plan. It stays in the private workspace plan")
        elif k not in HANDLING_KEYS:
            P.append(f"project.handling: unknown key {str(k)[:40]!r}")
    if "policy_version" not in h:
        P.append("project.handling.policy_version is required")
    elif not _is_int(h["policy_version"]) or h["policy_version"] != 1:
        P.append("project.handling.policy_version must be 1")
    approved = h.get("repo_audience_approved")
    if "repo_audience_approved" not in h:
        P.append("project.handling.repo_audience_approved is required: true when everyone who can read the repository may see all the documents and staffing notes, else false")
    elif not isinstance(approved, bool):
        P.append("project.handling.repo_audience_approved must be true or false")
    state = h.get("state")
    if state is None:
        P.append("project.handling.state is required: migrated")
    elif state not in HANDLING_STATES:
        P.append("project.handling.state must be legacy or migrated")
    elif modern and state != "migrated":
        P.append("project.handling.state must be migrated in a plan_format 2 plan")
    elif not modern and state == "migrated":
        P.append(f"plan_format: {PLAN_FORMAT} and plan_view are required when project.handling.state is migrated")
    if mode != "released":
        approvers = h.get("approvers")
        if approvers is not None:
            if not isinstance(approvers, list) or not all(isinstance(x, str) and _LOGIN_RE.match(x) for x in approvers):
                P.append("project.handling.approvers must be a list of GitHub logins")
        if approved is False and not approvers:
            P.append("project.handling.approvers needs at least one GitHub login when repo_audience_approved is false")
        retain = h.get("retain_raw_inputs")
        if retain is not None and retain not in RETAIN_VALUES:
            P.append("project.handling.retain_raw_inputs must be keep or delete-after-release")
        down = h.get("downstream")
        if isinstance(down, dict):
            for k, v in down.items():
                if k not in DOWNSTREAM_FLAGS:
                    P.append(f"project.handling.downstream: unknown key {str(k)[:40]!r}")
                elif k == "evidence":
                    if v not in ("synthetic-only", "approved"):
                        P.append("project.handling.downstream.evidence must be synthetic-only or approved")
                elif not isinstance(v, bool):
                    P.append(f"project.handling.downstream.{k} must be true or false")
    grace = h.get("offline_grace_days")
    if grace is not None and (not _is_int(grace) or not 0 <= grace <= 365):
        P.append("project.handling.offline_grace_days must be a whole number of days from 0 to 365")
    edits = h.get("engineer_edits")
    if edits is not None and edits not in ENGINEER_EDITS:
        P.append("project.handling.engineer_edits must be allowed or request-only")
    return P


def _people_key_problems(plan):
    """Staffing keys that a migrated plan must not hold: people[] fields and a top-level advisors
    list. Locations are people:<id>:<field>, never a value."""
    P = []
    for n, p in enumerate(plan.get("people") or [], 1):
        if not isinstance(p, dict):
            continue
        who = p.get("id") if isinstance(p.get("id"), str) and p.get("id") else f"#{n}"
        for k in STAFFING_KEYS:
            if k in p:
                P.append(f"people:{who}:{k} is a staffing field. Keep it in people.yaml in the private workspace, not in plan.yaml")
    if "advisors" in plan:
        P.append("advisors is a staffing field. Keep advisors in people.yaml in the private workspace, not in plan.yaml")
    return P


def staffing_problems(plan, show_values=True):
    """Problems with the facts that describe availability: start dates, days off and allocation, and
    an item due on its owner's day off. A legacy plan holds them itself. A migrated plan holds them
    in people.yaml, so this runs on the merged view. show_values False keeps the values out of the
    messages, for people.yaml."""
    P = []

    def got(v):
        return f", got {v!r}" if show_values else ""

    for p in plan["people"]:
        if p.get("start") is not None:
            if not _is_date(p["start"]):
                P.append(f"people: {p.get('id')} start is not a date (use YYYY-MM-DD)" + (f": {p['start']!r}" if show_values else ""))
            elif _is_weekend(p["start"]):
                P.append(f"people: {p.get('id')} start " + (f"{p['start']} " if show_values else "") + "is a weekend")
        if p.get("days_off") is not None and not isinstance(p.get("days_off"), list):
            P.append(f"people: {p.get('id')} days_off must be a list of dates, such as [2027-02-22]")
        for d in (p.get("days_off") if isinstance(p.get("days_off"), list) else []):
            if not _is_date(d):
                P.append(f"people: {p.get('id')} days_off has a bad date" + (f" {d!r}" if show_values else ""))
            elif _is_weekend(d):
                P.append(f"people: {p.get('id')} day off " + (f"{d} " if show_values else "") + "is a weekend")
    for p in plan["people"]:
        al = p.get("allocation")
        if not isinstance(al, int) or isinstance(al, bool) or not (1 <= al <= 100):
            P.append(f"people: {p.get('id')} allocation must be a whole percent from 1 to 100" + got(al))
    people = {p.get("id"): p for p in plan["people"]}
    for it in plan["items"]:
        own = people.get(it.get("owner"))
        if own and it.get("complete_by") and _is_date(it["complete_by"]) and it["complete_by"] in [str(x) for x in (own.get("days_off") or [])]:
            P.append(f"item {it.get('id')}: complete_by " + (f"{it['complete_by']} " if show_values else "") + f"is a day off for {own['id']}")
    return P


def validate_plan(plan, view=None):
    """Problems with a loaded plan, as a list of one-line messages.

    view selects the rules. workspace is the owner's working plan. released is the exported plan: it
    rejects personal staffing, private source metadata and original or rendering paths, and it needs
    none of them. None keeps the legacy rules for a plan that has not been migrated, and follows the
    plan's own plan_view for a migrated one. A migrated plan never carries staffing facts, so
    capacity and day-off checks run on the merged view, through staffing_problems."""
    P = []
    mode = plan_mode(plan, view)
    modern = is_modern(plan)
    released = mode == "released"
    P += _view_problems(plan, view)
    if modern:
        P += _people_key_problems(plan)
    # Detect collisions before any dictionary below can hide a record.
    for group, rows, key in (("tracks", plan["tracks"], "id"),
                              ("track labels", plan["tracks"], "label"),
                              ("people", plan["people"], "id"),
                              ("external.items", plan["external"]["items"], "id"),
                              ("checkpoints", plan["checkpoints"], "date")):
        seen = set()
        for row in rows:
            value = row.get(key)
            identity = value.casefold() if group == "track labels" and isinstance(value, str) else value
            if identity in seen:
                P.append(f"{group}: duplicate {key} {value!r}. Preview recovery with plan_repair.py --root .")
            seen.add(identity)
    work_ids = {it.get("id") for it in plan["items"]}
    for row in plan["external"]["items"]:
        if row.get("id") in work_ids:
            P.append(f"external.items: id {row.get('id')} conflicts with a work item. Preview plan_repair.py")
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
    P += _handling_problems(plan, mode)
    if proj.get("repo") and not repo_ok(proj["repo"]):
        P.append(f"project.repo must look like owner/name, got {proj['repo']!r}")
    # A released plan needs no original and no rendering: project.ground_truth is optional there and
    # is never an input to citation checks, so no default path is invented for it.
    for k, example in (("spec_dir", "docs/spec"), ("ground_truth", "docs/ground-truth/architecture.md")):
        v = str(proj.get(k) or "")
        if released and k == "ground_truth" and k not in proj:
            continue
        if not v.strip():
            P.append(f"project.{k} is empty. Leave the line out for the default {example}, or give a path")
        elif not relative_inside(v):
            P.append(f"project.{k} must be a path inside the project, such as {example}, got {v!r}")
    handling = proj.get("handling") if isinstance(proj.get("handling"), dict) else {}
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
        label = sid if isinstance(sid, str) and sid else f"#{num}"
        if released:
            # Only the id, the owner's display name and the version are exported. Where the original
            # or the rendering lives, how the owner classified it and its digests stay private.
            for k in PRIVATE_SOURCE_KEYS:
                if k in source:
                    P.append(f"sources:{label}:{k} is not allowed in a released plan. It stays in the private workspace plan")
            if not str(source.get("version") or "").strip():
                P.append(f"sources:{label}:version is required in a released plan")
            continue
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
        if modern:
            cls = source.get("classification")
            if cls is None:
                P.append(f"sources:{label}:classification is required: repo-readers, restricted or public")
            elif cls not in CLASSIFICATIONS:
                P.append(f"sources:{label}:classification must be repo-readers, restricted or public, got {str(cls)[:40]!r}")
            elif cls == "restricted" and handling.get("repo_audience_approved") is True:
                P.append(f"sources:{label}: classification is restricted, but project.handling.repo_audience_approved is true. "
                         "Change the answer to the one question, or classify the source repo-readers")
            for k in ("content_sha256", "rendering_sha256"):
                if source.get(k) is not None and not (isinstance(source[k], str) and _HEX64_RE.match(source[k])):
                    P.append(f"sources:{label}:{k} must be 64 lowercase hexadecimal characters")
    reviewed_paths = {s.get("path") for s in plan.get("sources") or [] if (s.get("status") or "reviewed") == "reviewed"}
    if released:
        pass   # source paths are not exported, so there is nothing to match project.ground_truth against
    elif plan.get("sources") and not reviewed_paths:
        P.append("sources must include at least one reviewed entry. Continue with every readable source, but stop when none can be processed")
    elif plan.get("sources") and proj.get("ground_truth") not in reviewed_paths:
        P.append("project.ground_truth must match the path of one reviewed sources entry")
    for it in plan["items"]:
        refs = it.get("source_refs") or []
        if it.get("state") is not None and it["state"] not in ("open", "closed"):
            P.append(f"item {it.get('id')}: state must be open or closed when explicitly planned")
        if not refs and not item_source_refs(plan, it):
            P.append(f"item {it.get('id')}: plan-level source_refs is required. Preview plan_repair.py; select a reviewed source and explicit sections")
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
            if not str(ref.get("sections") or "").strip():
                P.append(f"item {it.get('id')}: source_refs for {sid or 'an unnamed source'} needs sections")
    tracks = {t.get("id"): t for t in plan["tracks"]}
    if not tracks:
        P.append("tracks: at least one track is required")
    people = {p.get("id"): p for p in plan["people"]}
    for n, p in enumerate(plan["people"], 1):
        # A migrated plan names a person by id only: the name is a staffing field kept in people.yaml.
        if not p.get("id") or (not modern and not p.get("name")):
            P.append(f"people: each person needs id{'' if modern else ' and name'} (entry {n})")
        if p.get("track") not in tracks:
            P.append(f"people: {p.get('id')} has unknown track {p.get('track')!r}")
    if not modern:
        P += staffing_problems(plan)
    for n, t in enumerate(plan["tracks"], 1):
        if not t.get("id") or not t.get("label"):
            P.append(f"tracks: each track needs id and label (track entry {n})")
        elif len(t["id"]) > MAX_LABEL or not _one_line(t["id"]) or "," in t["id"]:
            P.append(f"tracks: id {t['id'][:60]!r} is a GitHub label, so it is one line with no comma, at most {MAX_LABEL} characters")
        if not _one_line(t.get("label")):
            P.append(f"tracks: {t.get('id')} label must be one line")
    for p in plan["people"]:
        if "derived" in p and not isinstance(p["derived"], bool):
            P.append(f"people: {p.get('id')} derived must be true or false")
    if released and plan["banned"].get("names"):
        P.append("banned:names is not allowed in a released plan. Names to keep out of the specifications stay in people.yaml in the private workspace")
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
    for n, c in enumerate(plan["checkpoints"], 1):
        if not c.get("date") or not _is_date(c.get("date")) or not c.get("name"):
            P.append(f"checkpoints: need date and name (checkpoint entry {n})")
        else:
            cps[c["date"]] = c
            if _is_weekend(c["date"]):
                P.append(f"checkpoint {c['date']} is a weekend")
    ext_ids = set()
    for n, pi in enumerate(plan["external"]["items"], 1):
        if not isinstance(pi.get("id"), int) or not pi.get("label"):
            P.append(f"external.items: each needs integer id and label (external item entry {n})")
        else:
            ext_ids.add(pi["id"])
    ids = []
    items = {}
    milestones = {m.get("number"): m for m in plan["milestones"]}
    for it in plan["items"]:
        iid = it.get("id")
        if not isinstance(iid, int):
            P.append("items: id must be an integer (an item has none, or one that is not a whole number)")
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
        if modern and "restricted" in it:
            # Restricted items (a later work package) are omitted from the exported plan, so the flag
            # and the owner's summary are never exported. The summary is the owner's text for a placeholder.
            if released:
                P.append(f"items:{iid}:restricted is not allowed in a released plan. Restricted items are omitted from it")
            elif not isinstance(it["restricted"], bool):
                P.append(f"items:{iid}:restricted must be true or false")
            elif it["restricted"] and not str(it.get("restricted_summary") or "").strip():
                P.append(f"items:{iid}:restricted_summary is required when the item is restricted")
        if released and "restricted_summary" in it:
            P.append(f"items:{iid}:restricted_summary is not allowed in a released plan")
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
        "source_path": plan["project"].get("ground_truth", ""),
        "path": plan["project"].get("ground_truth", ""),
        "use": "Full specification. Section numbers in the work item files refer to it.",
        "status": "reviewed",
    }]


def rendered_sources(plan):
    return [source for source in ground_truth_sources(plan) if (source.get("status") or "reviewed") == "reviewed"]


def source_by_id(plan):
    return {source["id"]: source for source in ground_truth_sources(plan)}


def explicit_sections(citation):
    """Section numbers only after an explicit section label, never a file version or item ID."""
    found = []
    pattern = r"(?i)\bsections?\s+([0-9]+(?:\.[0-9]+)*(?:(?:\s*,\s*|\s+and\s+|\s*&\s*)[0-9]+(?:\.[0-9]+)*)*)"
    for match in re.finditer(pattern, citation or ""):
        found.extend(re.findall(r"\d+(?:\.\d+)*", match.group(1)))
    return list(dict.fromkeys(found))


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
    matches = [s for s in reviewed if any(str(v).casefold() in cite.casefold()
               for v in (s.get("id"), s.get("name"), s.get("path")) if v)]
    if len(matches) != 1:
        matches = [s for s in reviewed if s.get("path") == plan["project"].get("ground_truth")] if not matches else []
    if len(matches) != 1 or not explicit_sections(cite):
        return []
    primary = matches[0]
    return [{"source": primary["id"], "sections": ", ".join(explicit_sections(cite))}]


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
