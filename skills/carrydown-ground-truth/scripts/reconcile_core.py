#!/usr/bin/env python3
"""Pure comparison and accounting helpers for project reconciliation. Standard library only.

This is the library half of the update path of carrydown-ground-truth (specification
specs/reconciliation-design.md, sections 7, 8 and 12). scripts/reconcile.py calls it. The
independent tests call it too. Every function takes plain data (strings, dicts, lists) and returns
plain data.

What it does
  compare_sections       step 2: split two renderings of one source into numbered sections and
                         classify each changed block (added, modified, removed, moved, renumbered,
                         precedence, unreadable). A uniquely identical section at a new number is
                         proposed as a mapping. An ambiguous mapping is reported with a candidates
                         list and is never mapped silently. A change that only touches whitespace or
                         emphasis markers carries formatting_only.
  build_impact_index     section 7: one structured row per work item, global conventions once, word
                         budgets with omitted-word counts, exact bytes and words and an approximate
                         token count. Restricted work items stay out of a public index.
  find_direct_consumers  step 3: the work items that cite a changed section, and the explicit
                         relationships (contract, scheduling dependency, integration counterpart).
  validate_dispositions  step 5: every changed block has exactly one disposition with the fields
                         that disposition needs.
  check_input_digests    step 8: which recorded input digests still match the current files.
  sha256_text, normalize_block   small helpers the other scripts and the tests reuse.

What it never does
  It writes no file, starts no process, reads no file, opens no connection and calls no model. It reads
  no token. It imports only carrydown_lib and compile_bundles, which hold no network or token code.
  Text it is given is data. Nothing in a rendering or a specification is executed or followed.
  It never turns a missing result into a clean one: a block without a disposition, an ambiguous
  mapping, a truncated excerpt and a changed digest are all reported.

Data shapes
  A changed block is a dict. The fields are ref (a stable reference such as "architecture/3.5>3.5"),
  kind, source, previous_number, previous_heading, previous_digest, current_number, current_heading,
  current_digest, exact_move, formatting_only, ambiguous, candidates, mapping_basis, heading_changed,
  text_changed and reason. A number or heading that does not exist on one side is None. A digest is the
  SHA-256 of the normalized own text of the section (its text up to the next numbered heading).
  A problem returned by validate_dispositions is a dict with code, block and message.
  Malformed input raises ReconcileError with a one-line message. Content problems that a person can
  fix are returned as data instead.

How to run the tests
  python3 -m unittest tests.test_reconcile_core -v
  python3 -m unittest discover -s tests

This module is imported by other scripts. Run with --help to see this text.
"""
import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402
import compile_bundles as CB  # noqa: E402

KINDS = ("added", "modified", "removed", "moved", "renumbered", "precedence", "unreadable")
DISPOSITIONS = ("update", "add", "assess-completed", "no-impact", "defer", "unresolved")
# The fields each disposition needs (specification section 8, step 5). A value is a non-blank
# string, or for "affected" a non-empty list or a non-blank string. "item" is a work item number,
# a work item id such as WI-03 or a non-blank string.
REQUIRED_FIELDS = {
    "update": ("item", "patch"),
    "add": ("scope", "decision"),
    "assess-completed": ("evidence", "follow_up"),
    "no-impact": ("reason", "context"),
    "defer": ("consequence", "affected", "remaining"),
    "unresolved": ("missing",),
}
RELATIONSHIPS = ("citation", "shared-obligation", "contract", "dependency", "integration")
CONTENT_RELATIONSHIPS = ("citation", "shared-obligation", "contract")

INDEX_PROCEDURE_VERSION = 1
DEFAULT_BUDGETS = {"scope": 60, "acceptance": 100, "decisions": 60}
INTEGRATION_WORDS = 40          # the crosses-the-boundary excerpt, an addition to the three budgets of section 7.2
MAX_BUDGET_WORDS = 5000
MAX_TEXT_CHARS = 5_000_000      # the largest rendering or specification this module reads
MAX_LISTED = 20                 # contract headings and files listed per row
APPROX_BYTES_PER_TOKEN = 4

SCOPE_SECTIONS = ("Why this work item exists", "Why this exists")
ACCEPTANCE_SECTIONS = ("Acceptance criteria",)
CONTRACT_SECTIONS = ("Contract", "Protocol")
INTEGRATION_SECTION = "Integration points"
DECISIONS_SECTION = "Decisions recorded"

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
_FENCE_OPEN = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_LIST_MARK = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
_SEP_CELL = re.compile(r"^:?-+:?$")
_HR = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")


class ReconcileError(ValueError):
    """The input is malformed. The message is one line and holds no document text."""


# ---------------------------------------------------------------------------
# Input checks
# ---------------------------------------------------------------------------

def _need_text(value, name):
    if not isinstance(value, str):
        raise ReconcileError(f"{name} must be text, got {type(value).__name__}")
    if "\x00" in value:
        raise ReconcileError(f"{name} contains a NUL character, so it is not text")
    if len(value) > MAX_TEXT_CHARS:
        raise ReconcileError(f"{name} is longer than {MAX_TEXT_CHARS} characters")
    return value


def _need_dict(value, name):
    if not isinstance(value, dict):
        raise ReconcileError(f"{name} must be a mapping, got {type(value).__name__}")
    return value


def _need_list(value, name):
    if not isinstance(value, list):
        raise ReconcileError(f"{name} must be a list, got {type(value).__name__}")
    return value


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _blank(value):
    return not isinstance(value, str) or not value.strip()


def _need_plan(plan):
    """The plan must be a mapping with a project id prefix and a list of items that have unique
    integer ids. Everything else is read defensively."""
    _need_dict(plan, "plan")
    project = plan.get("project")
    if not isinstance(project, dict) or _blank(project.get("id_prefix")):
        raise ReconcileError("plan.project.id_prefix is missing")
    items = plan.get("items")
    if not isinstance(items, list):
        raise ReconcileError("plan.items must be a list")
    seen = set()
    for number, item in enumerate(items, 1):
        if not isinstance(item, dict) or not _is_int(item.get("id")):
            raise ReconcileError(f"plan.items entry {number} has no integer id")
        if item["id"] in seen:
            raise ReconcileError(f"plan.items has the id {item['id']} twice")
        seen.add(item["id"])
    return plan


def sha256_text(text):
    """The lowercase hex SHA-256 of text, encoded as UTF-8. The same value as carrydown_lib.sha256_text."""
    _need_text(text, "text")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _inline_code_spans(s):
    """[(start, end)] of the inline code spans of one line."""
    return [m.span() for m in re.finditer(r"(`+)(?!`).+?(?<!`)\1(?!`)", s)]


def _strip_emphasis(s):
    """Remove Markdown emphasis markers from the prose of one line. Inline code is left alone, and so are
    underscores inside words, a bullet marker and a multiplication sign. Strikethrough is kept, because
    it marks deleted text."""
    out, pos = [], 0

    def prose(part):
        part = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", part)
        part = re.sub(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])", r"\1", part)
        part = re.sub(r"(?<![\w_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w_])", r"\1", part)
        return part

    for start, end in _inline_code_spans(s):
        out.append(prose(s[pos:start]))
        out.append(s[start:end])
        pos = end
    out.append(prose(s[pos:]))
    return "".join(out)


def _table_row(line):
    """A table row with one space inside each cell and a plain separator row."""
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    cells = []
    for cell in re.split(r"(?<!\\)\|", inner):
        cell = " ".join(cell.split())
        if _SEP_CELL.match(cell):
            cell = (":" if cell.startswith(":") else "") + "---" + (":" if cell.endswith(":") else "")
        else:
            cell = _strip_emphasis(cell)
        cells.append(cell)
    return "| " + " | ".join(cells) + " |"


def _classify(line):
    """plain, list, table, heading or other, for a line outside a code fence."""
    s = line.strip()
    if s.startswith("|"):
        return "table"
    if re.match(r"^#{1,6}\s", s):
        return "heading"
    if _LIST_MARK.match(line) and not _HR.match(line):
        return "list"
    if s.startswith((">", "<")) or _HR.match(line) or s.startswith("[") and "]:" in s[:80]:
        return "other"
    return "plain"


def normalize_block(text):
    """The text of a block as change detection compares it.

    It keeps every word, number, quantity, unit, condition, exception and negation (not, never, unless,
    except, only, must, must not, at most, at least), every code fence (verbatim, apart from trailing blanks
    and line endings), every table cell and every inline code span. It ignores line endings, trailing
    blanks, runs of white space, the way a paragraph is wrapped across lines, Markdown emphasis markers
    around words, the choice among -, * and + as a bullet, the padding of table cells and runs of blank
    lines. Letter case is kept. The result ends with one newline, or is "" when nothing is left."""
    _need_text(text, "text")
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " "))
    entries = []          # ("code", text) | ("blank", "") | (kind, indent, text)
    fence = None
    for line in text.split("\n"):
        if fence is not None:
            entries.append(("code", line.rstrip()))
            m = re.match(r"^\s{0,3}(`{3,}|~{3,})\s*$", line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        m = _FENCE_OPEN.match(line)
        if m:
            fence = m.group(1)
            entries.append(("code", line.strip()))
            continue
        if not line.strip():
            entries.append(("blank", ""))
            continue
        expanded = line.expandtabs(4).rstrip()
        indent = len(expanded) - len(expanded.lstrip(" "))
        entries.append((_classify(expanded), indent, expanded.strip(), expanded))
    out = []
    prev_kind = None      # the kind of the previous output line when a join is possible
    for entry in entries:
        kind = entry[0]
        if kind == "code":
            out.append(entry[1])
            prev_kind = None
            continue
        if kind == "blank":
            if out and out[-1] != "":
                out.append("")
            prev_kind = None
            continue
        _, indent, body, expanded = entry
        if kind == "plain" and indent >= 4 and prev_kind is None:
            out.append(expanded)          # an indented code block: kept as written
            continue
        if kind == "table":
            out.append(_table_row(body))
            prev_kind = "table"
            continue
        if kind == "heading":
            out.append(_strip_emphasis(" ".join(re.sub(r"\s+#+\s*$", "", body).split())))
            prev_kind = "heading"
            continue
        body = " ".join(body.split())
        if kind == "list":
            body = re.sub(r"^([-*+]) ", "- ", body)
            body = _strip_emphasis(body)
            out.append(" " * indent + body)
            prev_kind = "list"
            continue
        body = _strip_emphasis(body)
        if kind == "plain" and prev_kind in ("plain", "list") and out and out[-1] != "":
            out[-1] = out[-1] + " " + body
            continue
        out.append(body)
        prev_kind = "plain" if kind == "plain" else "other"
    while out and out[-1] == "":
        out.pop()
    while out and out[0] == "":
        out.pop(0)
    return ("\n".join(out) + "\n") if out else ""


def _norm_heading(heading):
    return _strip_emphasis(" ".join(str(heading).split()))


def _raw_body(lines):
    """The lines of a section as they are, with line endings and trailing blanks removed and the blank
    lines around the text dropped."""
    body = [l.rstrip() for l in lines]
    while body and not body[0]:
        body.pop(0)
    while body and not body[-1]:
        body.pop()
    return "\n".join(body)


# ---------------------------------------------------------------------------
# Splitting a rendering into sections
# ---------------------------------------------------------------------------

def _drop_generated(lines):
    """A rendering without its generated header comment and its generated section index."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("<!-- Generated from"):
            i += 1
            continue
        if line.strip() == "**Section index**":
            i += 1
            while i < len(lines) and (not lines[i].strip() or re.match(r"^\s*- \[", lines[i])):
                i += 1
            continue
        out.append(line)
        i += 1
    return out


def split_sections(rendering_text):
    """The numbered sections of a rendering, as (sections, duplicates).

    sections maps a section number to a dict with number, heading, level, line, raw and normalized text
    and digest. The text of a section is its own text: it runs from its heading to the next numbered
    heading, or to the next heading of the same or a higher level, so a subsection is a section of
    its own and a change in it is not a change of its parent. A heading without a number inside a
    section stays in that section. The title, the subtitle, the header comment and the section index
    before the first numbered heading belong to no section. Headings in code fences are not headings.
    duplicates lists (number, heading) of a number that a later heading repeats. Only the first
    heading with a number is a section."""
    _need_text(rendering_text, "rendering")
    lines = rendering_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    heads = L.collect_headings(lines)
    numbered = []
    for line_no, level, title in heads:
        m = _NUMBERED.match(re.sub(r"[`*_]", "", title).strip())
        numbered.append((line_no, level, title, m.group(1) if m else None))
    sections, duplicates = {}, []
    for pos, (line_no, level, title, number) in enumerate(numbered):
        if number is None:
            continue
        end = len(lines)
        for later_line, later_level, _, later_number in numbered[pos + 1:]:
            if later_number is not None or later_level <= level:
                end = later_line - 1
                break
        heading = _NUMBERED.match(re.sub(r"[`*_]", "", title).strip()).group(2).strip()
        if number in sections:
            duplicates.append((number, heading))
            continue
        raw = _raw_body(lines[line_no:end])
        normalized = normalize_block(raw)
        sections[number] = {"number": number, "heading": heading, "level": level, "line": line_no, "raw": raw,
                            "normalized": normalized, "digest": sha256_text(normalized)}
    return sections, duplicates


def _whole_document(rendering_text):
    """The whole rendering as one section, for a rendering that has no numbered headings."""
    lines = _drop_generated(rendering_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    raw = _raw_body(lines)
    normalized = normalize_block(raw)
    title = next((t for _, level, t in L.collect_headings(lines) if level == 1), "") or ""
    return {"number": CB.WHOLE, "heading": re.sub(r"[`*_]", "", title).strip() or CB.WHOLE, "level": 1, "line": 1,
            "raw": raw, "normalized": normalized, "digest": sha256_text(normalized)}


# ---------------------------------------------------------------------------
# Step 2: compare two renderings
# ---------------------------------------------------------------------------

def _ref(source, previous, current, suffix=None):
    base = f"{previous if previous is not None else 'none'}>{current if current is not None else 'none'}"
    if previous is not None and previous == current:
        base = previous
    if suffix:
        base = suffix
    return f"{source}/{base}" if source else base


def _block(kind, source, previous=None, current=None, **extra):
    block = {
        "ref": _ref(source, previous["number"] if previous else None, current["number"] if current else None,
                    extra.pop("ref_suffix", None)),
        "kind": kind,
        "source": source,
        "previous_number": previous["number"] if previous else None,
        "previous_heading": previous["heading"] if previous else None,
        "previous_digest": previous["digest"] if previous else None,
        "current_number": current["number"] if current else None,
        "current_heading": current["heading"] if current else None,
        "current_digest": current["digest"] if current else None,
        "exact_move": False,
        "formatting_only": False,
        "ambiguous": False,
        "candidates": [],
        "mapping_basis": None,
        "heading_changed": False,
        "text_changed": False,
        "reason": "",
    }
    block.update(extra)
    return block


def _parent(number):
    return number.rpartition(".")[0]


def _sort_key(block):
    number = block["current_number"] if block["current_number"] is not None else block["previous_number"]
    try:
        first = CB.section_key(number) if number is not None else (-2,)
    except ValueError:
        first = (-3,)
    previous = block["previous_number"]
    try:
        second = CB.section_key(previous) if previous is not None else (-2,)
    except ValueError:
        second = (-3,)
    return (first, second, KINDS.index(block["kind"]), block["ref"])


def _same_number_block(source, p, c):
    """The block for a number that exists on both sides, or None when nothing changed."""
    if p["raw"] == c["raw"] and p["heading"] == c["heading"] and p["level"] == c["level"]:
        return None
    heading_changed = _norm_heading(p["heading"]) != _norm_heading(c["heading"])
    text_changed = p["digest"] != c["digest"]
    return _block("modified", source, p, c, heading_changed=heading_changed, text_changed=text_changed,
                  formatting_only=not heading_changed and not text_changed)


def _pair_block(source, p, c, basis):
    """A removed section and an added section that stand for the same content, as a moved or renumbered block."""
    kind = "renumbered" if _parent(p["number"]) == _parent(c["number"]) else "moved"
    heading_changed = _norm_heading(p["heading"]) != _norm_heading(c["heading"])
    text_changed = p["digest"] != c["digest"]
    exact = basis == "exact-body"
    return _block(kind, source, p, c, exact_move=exact, mapping_basis=basis, heading_changed=heading_changed,
                  text_changed=text_changed,
                  formatting_only=exact and not heading_changed and p["raw"] != c["raw"])


def _group(sections, numbers, key):
    groups = {}
    for number in numbers:
        value = key(sections[number])
        if value:
            groups.setdefault(value, []).append(number)
    return groups


def precedence_blocks(previous_order, current_order, source_id=None):
    """Blocks of kind precedence for sources whose rank changed between two precedence lists (source ids,
    highest precedence first). A source that is in only one list is reported with None as its other rank.
    With source_id only that source is reported."""
    _need_list(previous_order, "previous precedence")
    _need_list(current_order, "current precedence")
    for name, order in (("previous", previous_order), ("current", current_order)):
        if not all(isinstance(s, str) and s.strip() for s in order) or len(set(order)) != len(order):
            raise ReconcileError(f"the {name} precedence must be a list of distinct, non-blank source ids")
    blocks = []
    for sid in sorted(set(previous_order) | set(current_order)):
        if source_id is not None and sid != source_id:
            continue
        before = previous_order.index(sid) + 1 if sid in previous_order else None
        after = current_order.index(sid) + 1 if sid in current_order else None
        if before == after:
            continue
        b = _block("precedence", sid, ref_suffix="precedence", reason=f"precedence rank changed from {before} to {after}")
        b["previous_rank"], b["current_rank"] = before, after
        blocks.append(b)
    return blocks


def compare_sections(previous_rendering_text, current_rendering_text, source_id=None,
                     previous_precedence=None, current_precedence=None):
    """Compare two renderings of one source and list the changed blocks (specification 8, step 2).

    Returns a list of block dicts (see the module text), sorted by section number. Each block's kind is:
      modified     the number exists on both sides and the heading or the text changed. formatting_only is
                   true when only white space, emphasis markers or a heading level changed.
      added        a number that exists only now.
      removed      a number that existed only before.
      moved        a uniquely identical section (same normalized text) now has a number under another
                   parent. exact_move is true, and previous_number and current_number are the proposed
                   mapping.
      renumbered   the same, with the same parent: the section only shifted.
      precedence   the rank of the source changed (given previous_precedence and current_precedence).
      unreadable   a repeated section number, or a rendering that has numbered headings on one side only.
    An empty section is never mapped by its text. When the text matches more than one section, or the
    same text sits under two numbers, the blocks are kind removed and added with ambiguous true and a
    candidates list, and nothing is mapped. When only the heading matches, uniquely, the pair is reported
    as moved or renumbered with exact_move false and mapping_basis "heading", for a person to confirm.
    A rendering without numbered headings on either side is compared as one whole document."""
    _need_text(previous_rendering_text, "previous rendering")
    _need_text(current_rendering_text, "current rendering")
    if source_id is not None and (not isinstance(source_id, str) or not source_id.strip()):
        raise ReconcileError("source_id must be a non-blank string")
    if (previous_precedence is None) != (current_precedence is None):
        raise ReconcileError("give both precedence lists or neither")
    prev, prev_dups = split_sections(previous_rendering_text)
    cur, cur_dups = split_sections(current_rendering_text)
    blocks = []
    if previous_precedence is not None:
        if source_id is None:
            raise ReconcileError("source_id is required with precedence lists")
        blocks += precedence_blocks(previous_precedence, current_precedence, source_id)
    if not prev and not cur:
        p, c = _whole_document(previous_rendering_text), _whole_document(current_rendering_text)
        change = _same_number_block(source_id, p, c)
        return blocks + ([change] if change else [])
    if not prev or not cur:
        side = "previous" if not prev else "current"
        blocks.append(_block("unreadable", source_id, ref_suffix="rendering",
                             reason=f"the {side} rendering has no numbered headings, so the sections cannot be compared"))
        return blocks
    for side, dups, sections in (("previous", prev_dups, prev), ("current", cur_dups, cur)):
        for number, heading in dups:
            first = sections[number]
            stub = dict(first, heading=heading)
            args = (stub, None) if side == "previous" else (None, stub)
            blocks.append(_block("unreadable", source_id, *args, ref_suffix=f"{side}-duplicate-{number}",
                                 reason=f"the {side} rendering repeats the section number {number}"))
    same = {}
    for number in prev:
        if number in cur:
            change = _same_number_block(source_id, prev[number], cur[number])
            if change:
                same[number] = change
                blocks.append(change)
    removed = [n for n in prev if n not in cur]
    added = [n for n in cur if n not in prev]
    # A section whose own text changed at its number has given up its old text. A section that holds text
    # the previous rendering had under another number has taken it up. Both are looked at with the removed
    # and the added sections, so an inserted section that shifts its neighbors is found as a renumbering.
    changed_here = [n for n in same if same[n]["text_changed"]]
    paired_removed, paired_added = set(), set()
    body_removed = _group(prev, removed + changed_here, lambda s: s["normalized"].strip() and s["digest"])
    body_added = _group(cur, added + changed_here, lambda s: s["normalized"].strip() and s["digest"])
    ambiguous = {}
    for digest, rs in body_removed.items():
        as_ = body_added.get(digest, [])
        if not as_:
            continue
        if len(rs) == 1 and len(as_) == 1:
            blocks.append(_pair_block(source_id, prev[rs[0]], cur[as_[0]], "exact-body"))
            paired_removed.add(rs[0])
            paired_added.add(as_[0])
        else:
            for number in rs:
                ambiguous[("p", number)] = list(as_)
            for number in as_:
                ambiguous[("c", number)] = list(rs)
    for number, change in same.items():
        found = set(ambiguous.get(("p", number), [])) | set(ambiguous.get(("c", number), []))
        if found:
            change["candidates"] = sorted(found, key=CB.section_key)
            change["ambiguous"] = True
            change["reason"] = "the text of this section may have moved, and more than one section could hold it"
    left_removed = [n for n in removed if n not in paired_removed and ("p", n) not in ambiguous]
    left_added = [n for n in added if n not in paired_added and ("c", n) not in ambiguous]
    heading_removed = _group(prev, left_removed, lambda s: _norm_heading(s["heading"]).casefold())
    heading_added = _group(cur, left_added, lambda s: _norm_heading(s["heading"]).casefold())
    heading_candidates = {}
    for key, rs in heading_removed.items():
        as_ = heading_added.get(key, [])
        if not as_:
            continue
        if len(rs) == 1 and len(as_) == 1:
            blocks.append(_pair_block(source_id, prev[rs[0]], cur[as_[0]], "heading"))
            paired_removed.add(rs[0])
            paired_added.add(as_[0])
        else:
            for number in rs:
                heading_candidates[("p", number)] = list(as_)
            for number in as_:
                heading_candidates[("c", number)] = list(rs)
    for number in removed:
        if number in paired_removed:
            continue
        found = ambiguous.get(("p", number)) or heading_candidates.get(("p", number)) or []
        blocks.append(_block("removed", source_id, prev[number], None, candidates=sorted(found, key=CB.section_key),
                             ambiguous=bool(found), text_changed=True,
                             reason="more than one section could be its new place" if found else ""))
    for number in added:
        if number in paired_added:
            continue
        found = ambiguous.get(("c", number)) or heading_candidates.get(("c", number)) or []
        blocks.append(_block("added", source_id, None, cur[number], candidates=sorted(found, key=CB.section_key),
                             ambiguous=bool(found), text_changed=True,
                             reason="more than one section could be its old place" if found else ""))
    return sorted(blocks, key=_sort_key)


def _check_blocks(changed_blocks, name="changed_blocks"):
    _need_list(changed_blocks, name)
    seen = set()
    for n, block in enumerate(changed_blocks, 1):
        if not isinstance(block, dict):
            raise ReconcileError(f"{name} entry {n} is not a mapping")
        for key in ("ref", "kind", "previous_number", "current_number"):
            if key not in block:
                raise ReconcileError(f"{name} entry {n} has no {key}")
        if _blank(block["ref"]):
            raise ReconcileError(f"{name} entry {n} has a blank ref")
        if block["kind"] not in KINDS:
            raise ReconcileError(f"{name} entry {n} has an unknown kind")
        for key in ("previous_number", "current_number"):
            if block[key] is not None and not isinstance(block[key], str):
                raise ReconcileError(f"{name} entry {n} has a {key} that is not text")
        if block["ref"] in seen:
            raise ReconcileError(f"{name} repeats the ref {block['ref']}")
        seen.add(block["ref"])
    return changed_blocks


# ---------------------------------------------------------------------------
# Reading a specification
# ---------------------------------------------------------------------------

def _spec_sections(text):
    """{heading: body} of the level 2 headings of a specification. The first heading of a name wins."""
    lines = text.replace("\r\n", "\n").split("\n")
    heads = [(n, lvl, t) for n, lvl, t in L.collect_headings(lines)]
    out = {}
    for pos, (line_no, level, title) in enumerate(heads):
        if level != 2:
            continue
        end = len(lines)
        for later_line, later_level, _ in heads[pos + 1:]:
            if later_level <= 2:
                end = later_line - 1
                break
        out.setdefault(title.strip(), "\n".join(lines[line_no:end]).strip("\n"))
    return out


def _first_section(sections, names):
    for name in names:
        if name in sections:
            return name, sections[name]
    return None, ""


def _excerpt(text, limit):
    """(excerpt, omitted words): the first limit words of text with white space folded."""
    words = text.split()
    if len(words) <= limit:
        return " ".join(words), 0
    return " ".join(words[:limit]), len(words) - limit


def _specs(plan, specs_by_item):
    """{id: {"text", "path"}} for the specifications given. Values are text, or a mapping with text and
    an optional path. A key that is not a work item of the plan is an error."""
    _need_dict(specs_by_item, "specs_by_item")
    ids = {it["id"] for it in plan["items"]}
    items = {it["id"]: it for it in plan["items"]}
    out = {}
    for key, value in specs_by_item.items():
        if not _is_int(key):
            raise ReconcileError("specs_by_item keys must be work item numbers")
        if key not in ids:
            raise ReconcileError(f"specs_by_item names work item {key}, which is not in the plan")
        path = None
        if isinstance(value, dict):
            path = value.get("path")
            value = value.get("text")
        _need_text(value, f"specification of work item {key}")
        if path is not None and not isinstance(path, str):
            raise ReconcileError(f"the path of the specification of work item {key} must be text")
        if path is None:
            try:
                path = Path(L.spec_path(plan, "", items[key])).as_posix()
            except (KeyError, TypeError, ValueError):
                path = ""
        out[key] = {"text": value, "path": path}
    return out


def _tag(plan, number):
    return L.tag(plan, number)


def _item_tags(plan, text, own=None):
    """The ids of the work items that text names, such as WI-03, in order, without repeats."""
    prefix = re.escape(str(plan["project"]["id_prefix"]))
    ids = {it["id"] for it in plan["items"]}
    found = []
    for m in re.finditer(r"(?<![\w-])" + prefix + r"-0*(\d+)(?![\w-])", text):
        number = int(m.group(1))
        if number in ids and number != own and number not in found:
            found.append(number)
    return found


def _criteria(body):
    """The acceptance criteria of a specification as one-line strings."""
    items, current = [], None
    for line in body.split("\n"):
        m = re.match(r"^\s{0,3}[-*]\s+(?:\[[ xX]\]\s+)?(.*)$", line)
        if m:
            if current is not None:
                items.append(current)
            current = m.group(1).strip()
        elif line.strip() and current is not None and line.startswith((" ", "\t")):
            current += " " + line.strip()
        elif not line.strip() and current is not None:
            items.append(current)
            current = None
    if current is not None:
        items.append(current)
    items = [" ".join(i.split()) for i in items if i.strip()]
    if not items and body.strip():
        items = [" ".join(body.split())]
    return items


def _decision_entries(body):
    text = body.strip()
    if not text or text.rstrip(".").strip().casefold() == "none yet":
        return []
    entries, current = [], None
    for line in text.split("\n"):
        if re.match(r"^\s{0,3}[-*]\s+\S", line):
            if current is not None:
                entries.append(current)
            current = re.sub(r"^\s*[-*]\s+", "", line).strip()
        elif line.strip() and current is not None:
            current += " " + line.strip()
        elif line.strip():
            current = line.strip()
        elif current is not None:
            entries.append(current)
            current = None
    if current is not None:
        entries.append(current)
    return [" ".join(e.split()) for e in entries if e.strip()]


def _contract_info(name, body):
    """The headings, lead labels and file names of the contract or protocol section of a specification."""
    if name is None:
        return {"section": None, "headings": [], "files": [], "omitted_entries": 0}
    headings = [t.strip() for _, lvl, t in L.collect_headings(body.split("\n")) if lvl >= 3]
    for paragraph in re.split(r"\n\s*\n", body):
        flat = " ".join(paragraph.split())
        m = re.match(r"^From sections? (\d+(?:\.\d+)*)\.", flat)
        if m:
            headings.append(f"section {m.group(1)}")
            continue
        m = re.match(r"^([A-Z][^.\n]{1,60}?),? sections? (\d+(?:\.\d+)*)\.", flat)
        if m:
            headings.append(f"{m.group(1).strip()} (section {m.group(2)})")
    files = []
    for m in re.finditer(r"`([A-Za-z0-9_./-]+\.(?:ya?ml|json|proto|graphql|sql|md|schema))`", body):
        if m.group(1) not in files:
            files.append(m.group(1))
    headings = list(dict.fromkeys(headings))
    omitted = max(0, len(headings) - MAX_LISTED) + max(0, len(files) - MAX_LISTED)
    return {"section": name, "headings": headings[:MAX_LISTED], "files": files[:MAX_LISTED], "omitted_entries": omitted}


def _source_ids(plan):
    return [s["id"] for s in L.ground_truth_sources(plan) if isinstance(s, dict) and s.get("id")]


def _spec_keys(plan, text, rendering_sections=None):
    """[(source id, section)] that the specification cites in References and by link."""
    ids = set(_source_ids(plan))
    lookup = (lambda sid: (rendering_sections or {}).get(sid))
    return CB.spec_cited_keys(text, ids, lookup)


def _plan_keys(plan, item):
    try:
        return CB.item_obligation_keys(plan, item)
    except (KeyError, TypeError, ValueError) as error:
        raise ReconcileError(f"the source references of work item {item.get('id')} are malformed: {error}") from None


# ---------------------------------------------------------------------------
# Section 7: the compact impact index
# ---------------------------------------------------------------------------

def _budgets(budgets):
    out = dict(DEFAULT_BUDGETS)
    if budgets is None:
        return out
    _need_dict(budgets, "budgets")
    for key, value in budgets.items():
        if key not in DEFAULT_BUDGETS and key != "integration":
            raise ReconcileError(f"budgets has an unknown key {str(key)[:30]!r}")
        if not _is_int(value) or value < 1 or value > MAX_BUDGET_WORDS:
            raise ReconcileError(f"budgets.{key} must be a whole number of words from 1 to {MAX_BUDGET_WORDS}")
        out[key] = value
    return out


def _text_list(value, name, item_id):
    if value is None:
        return None
    if isinstance(value, str):
        return _decision_entries(value) if value.strip() else []
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return [" ".join(v.split()) for v in value if v.strip()]
    raise ReconcileError(f"{name} for work item {item_id} must be text or a list of text")


def _completion(plan_item, given, item_id):
    if given is not None:
        if isinstance(given, str) and given.strip():
            return {"state": " ".join(given.split()), "source": "provided"}
        if isinstance(given, dict) and given:
            return dict(given)
        raise ReconcileError(f"completion for work item {item_id} must be non-blank text or a non-empty mapping")
    state = plan_item.get("state")
    if isinstance(state, str) and state.strip():
        return {"state": state.strip(), "source": "plan"}
    return "unknown"


def measure_index(index, excluded_rows=0):
    """Exact bytes and words of an index, and an approximate token count.

    The serialization is compact JSON with sorted keys and no escaping of non-ASCII text, encoded as
    UTF-8. bytes is its exact length. words is the number of white-space separated words in the string
    values of the index (keys and numbers are not words). approx_tokens is APPROX_BYTES_PER_TOKEN bytes
    per token, rounded up. It is an estimate, and is labeled so in its key. excluded_rows says how many
    restricted rows a public index left out. It is for the owner. Never put it in a public report."""
    _need_dict(index, "index")
    encoded = json.dumps(index, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    words = 0
    omitted = 0
    truncated = 0
    stack = [index]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "omitted_words" and _is_int(value) and value > 0:
                    omitted += value
                    truncated += 1
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, str):
            words += len(node.split())
    rows = index.get("rows") if isinstance(index.get("rows"), list) else []
    return {
        "serialization": "compact JSON, sorted keys, UTF-8",
        "bytes": len(encoded),
        "words": words,
        "approx_tokens": int(math.ceil(len(encoded) / APPROX_BYTES_PER_TOKEN)),
        "approx_tokens_method": f"ceil(bytes / {APPROX_BYTES_PER_TOKEN}), an estimate and not a count",
        "rows": len(rows),
        "excluded_rows": int(excluded_rows),
        "truncated_fields": truncated,
        "omitted_words": omitted,
        "missing_specifications": sum(1 for r in rows if not r.get("specification", {}).get("present")),
    }


def build_impact_index(plan, specs_by_item, conventions_text=None, decisions_by_item=None, completion_by_item=None,
                       budgets=None, public=False, rendering_sections=None):
    """The compact project-wide impact index (specification 7.1 and 7.2), as (index, measure).

    plan             a loaded plan (carrydown_lib.load_plan).
    specs_by_item    {work item number: specification text}, or {number: {"text": ..., "path": ...}}.
    conventions_text the applicable conventions, once. None reads them from plan["conventions"] when it has any.
    decisions_by_item   {number: text or list of entries} recorded elsewhere. Without an entry for an item
                     the "Decisions recorded" section of its specification is read.
    completion_by_item  {number: non-blank text or mapping}. Without one the plan state is used, else "unknown".
    budgets          words per field: scope 60, acceptance 100, decisions 60 by default (and integration 40).
    public           true leaves restricted work items out, as the released plan does (carrydown_lib.withheld_view),
                     and counts them only in measure["excluded_rows"]. false keeps them, for the owner.
    rendering_sections  {source id: {number: section}} to resolve links into renderings, optional.

    One row per work item sorted by id. A truncated field holds omitted_words and full_specification. The
    index is a search aid. An excerpt is not evidence of no impact when omitted words could matter."""
    _need_plan(plan)
    budget = _budgets(budgets)
    specs = _specs(plan, specs_by_item)
    if conventions_text is not None:
        _need_text(conventions_text, "conventions_text")
    elif isinstance(plan.get("conventions"), dict):
        conventions_text = L.conventions_text(plan)
    decisions_by_item = _need_dict(decisions_by_item, "decisions_by_item") if decisions_by_item is not None else {}
    completion_by_item = _need_dict(completion_by_item, "completion_by_item") if completion_by_item is not None else {}
    for name, mapping in (("decisions_by_item", decisions_by_item), ("completion_by_item", completion_by_item)):
        for key in mapping:
            if not _is_int(key):
                raise ReconcileError(f"{name} keys must be work item numbers")
    excluded = 0
    shown_plan = plan
    if public:
        excluded = sum(1 for it in plan["items"] if L.restricted_item(it))
        shown_plan = L.withheld_view(plan)
    conventions = None
    conventions_id = None
    if conventions_text is not None and conventions_text.strip():
        conventions_id = "conv-" + sha256_text(conventions_text)[:8]
        conventions = {"id": conventions_id, "text": conventions_text.strip("\n")}
    derived = {}
    for it in shown_plan["items"]:
        for dep in it.get("depends") or []:
            derived.setdefault(dep, []).append(it["id"])
    rows = []
    for it in sorted(shown_plan["items"], key=lambda i: i["id"]):
        rows.append(_index_row(shown_plan, it, specs.get(it["id"]), derived, budget, conventions_id,
                               decisions_by_item.get(it["id"]), completion_by_item.get(it["id"]), rendering_sections))
    index = {"format": "impact-index", "procedure_version": INDEX_PROCEDURE_VERSION, "budgets": budget,
             "conventions": conventions, "rows": rows}
    return index, measure_index(index, excluded)


def _field(excerpt, omitted, path, **more):
    out = {"excerpt": excerpt, "omitted_words": omitted}
    out.update(more)
    if omitted:
        out["full_specification"] = path
    return out


def _index_row(plan, it, spec, derived, budget, conventions_id, decisions, completion, rendering_sections):
    number = it["id"]
    path = spec["path"] if spec else ""
    if not path:
        try:
            path = Path(L.spec_path(plan, "", it)).as_posix()
        except (KeyError, TypeError, ValueError):
            path = ""
    depends = [d for d in it.get("depends") or [] if _is_int(d)]
    unblocks = sorted(set([u for u in it.get("unblocks") or [] if _is_int(u)] + derived.get(number, [])))
    row = {
        "id": number,
        "tag": _tag(plan, number),
        "title": " ".join(str(it.get("label") or "").split()),
        "milestone": it.get("milestone"),
        "specification": {"path": path, "present": spec is not None},
        "conventions": conventions_id,
        "completion": _completion(it, completion, number),
    }
    sections = _spec_sections(spec["text"]) if spec else {}
    _, scope_body = _first_section(sections, SCOPE_SECTIONS)
    text, omitted = _excerpt(scope_body, budget["scope"])
    row["scope"] = _field(text, omitted, path)
    _, accept_body = _first_section(sections, ACCEPTANCE_SECTIONS)
    criteria = _criteria(accept_body)
    shown, left = [], budget["acceptance"]
    for criterion in criteria:
        if left <= 0:
            break
        text, _ = _excerpt(criterion, left)
        shown.append(text)
        left -= len(text.split())
    total_words = sum(len(c.split()) for c in criteria)
    omitted = total_words - sum(len(s.split()) for s in shown)
    row["acceptance"] = _field(shown, omitted, path, criteria_total=len(criteria), criteria_shown=len(shown))
    plan_keys = _plan_keys(plan, it)
    spec_keys = _spec_keys(plan, spec["text"], rendering_sections) if spec else []
    grouped = {}
    for sid, sec in plan_keys + [k for k in spec_keys if k not in plan_keys]:
        grouped.setdefault(sid, []).append(sec)
    order = {s: n for n, s in enumerate(_source_ids(plan))}
    row["sources"] = [
        {"source": sid,
         "sections": sorted(secs, key=CB.section_key),
         "only_in_plan": sorted([s for (a, s) in plan_keys if a == sid and (a, s) not in spec_keys], key=CB.section_key),
         "only_in_specification": sorted([s for (a, s) in spec_keys if a == sid and (a, s) not in plan_keys], key=CB.section_key)}
        for sid, secs in sorted(grouped.items(), key=lambda kv: (order.get(kv[0], len(order)), kv[0]))]
    cname, cbody = _first_section(sections, CONTRACT_SECTIONS)
    row["contracts"] = _contract_info(cname, cbody)
    _, integration_body = _first_section(sections, (INTEGRATION_SECTION,))
    crosses = ""
    m = re.search(r"Crosses the boundary\.\s*(.*?)(?=\n\s*[-*]\s|\n\s*\n|\Z)", integration_body, re.S)
    if m:
        crosses = " ".join(m.group(1).split())
    text, omitted = _excerpt(crosses, budget.get("integration", INTEGRATION_WORDS))
    row["dependencies"] = {
        "depends_on": [_tag(plan, d) for d in sorted(depends)],
        "unblocks": [_tag(plan, u) for u in unblocks],
        "external_input": " ".join(str(it.get("external_input") or "").split()),
        "integration": _field(text, omitted, path, counterparts=[_tag(plan, n) for n in sorted(_item_tags(plan, integration_body, number))]),
    }
    entries = _text_list(decisions, "decisions_by_item", number)
    if entries is None:
        _, body = _first_section(sections, (DECISIONS_SECTION,))
        entries = _decision_entries(body)
    shown, left = [], budget["decisions"]
    for entry in reversed(entries):
        if left <= 0:
            break
        text, _ = _excerpt(entry, left)
        shown.insert(0, text)
        left -= len(text.split())
    omitted = sum(len(e.split()) for e in entries) - sum(len(s.split()) for s in shown)
    row["decisions"] = {"excerpt": True, "entries": shown, "entry_count": len(entries), "omitted_words": omitted}
    if omitted:
        row["decisions"]["full_specification"] = path
    return row


# ---------------------------------------------------------------------------
# Step 3: direct consumers
# ---------------------------------------------------------------------------

def _covers(cited, number):
    """True when a citation of cited includes the section number: the same section, or a parent of it."""
    return cited == number or number.startswith(cited + ".")


def find_direct_consumers(plan, specs_by_item, changed_blocks, source_id, public=False, rendering_sections=None):
    """The work items that cite each changed block of one source (specification 8, step 3).

    Returns one dict per changed block, in the order given, with
      block            the ref of the block
      consumers        content consumers: {"item", "tag", "relationship", "cited", "matched", "matched_on", "via"}.
                       relationship is citation (the item cites the section itself), shared-obligation (it cites a
                       parent section or the whole document, so its approved text includes the block) or contract (its
                       Contract or Protocol section names the section but its citations do not). matched_on is
                       "previous" or "current": a citation matches the previous number of the block and, for a block
                       that was moved or paired by heading, and for an added block, the current number. via lists plan
                       and specification.
      related          explicit relationships that are not content consumers: dependency (a scheduling link, either
                       direction) and integration (a counterpart named in an Integration points section), with
                       "of", the consumer item they relate to, and "direction". A dependency alone does not need
                       a rewrite of the other specification.
      uncited_candidates  an empty list. The agent fills it after reading the index.
    With public true restricted work items are left out of every list."""
    _need_plan(plan)
    if not isinstance(source_id, str) or not source_id.strip():
        raise ReconcileError("source_id must be a non-blank string")
    if source_id not in _source_ids(plan):
        raise ReconcileError("source_id is not a source of the plan")
    _check_blocks(changed_blocks)
    for block in changed_blocks:
        if block.get("source") not in (None, source_id):
            raise ReconcileError("changed_blocks holds a block of another source")
    specs = _specs(plan, specs_by_item)
    items = {it["id"]: it for it in plan["items"] if not (public and L.restricted_item(it))}
    sources = L.source_by_id(plan)
    ids = _source_ids(plan)
    cites = {}
    contracts = {}
    integration = {}
    for number, it in items.items():
        spec = specs.get(number)
        keys = {}
        for sid, sec in _plan_keys(plan, it):
            if sid == source_id:
                keys.setdefault(sec, set()).add("plan")
        if spec:
            for sid, sec in _spec_keys(plan, spec["text"], rendering_sections):
                if sid == source_id:
                    keys.setdefault(sec, set()).add("specification")
            sections = _spec_sections(spec["text"])
            contracts[number] = _first_section(sections, CONTRACT_SECTIONS)[1]
            integration[number] = _item_tags(plan, _first_section(sections, (INTEGRATION_SECTION,))[1], number)
        cites[number] = keys
    results = []
    for block in changed_blocks:
        numbers = []
        if block["previous_number"] is not None:
            numbers.append((block["previous_number"], "previous"))
        mapped = block["kind"] in ("moved", "renumbered") or block["kind"] == "added"
        if block["current_number"] is not None and block["current_number"] != block["previous_number"] and mapped:
            numbers.append((block["current_number"], "current"))
        consumers, seen = [], set()
        for number, it in sorted(items.items()):
            hit = None
            for matched, side in numbers:
                for cited, via in sorted(cites[number].items(), key=lambda kv: CB.section_key(kv[0])):
                    if cited == CB.WHOLE:
                        kind = "shared-obligation"
                    elif cited == matched:
                        kind = "citation"
                    elif _covers(cited, matched):
                        kind = "shared-obligation"
                    else:
                        continue
                    if hit is None or (kind == "citation" and hit["relationship"] != "citation"):
                        hit = {"item": number, "tag": _tag(plan, number), "relationship": kind, "cited": cited,
                               "matched": matched, "matched_on": side, "via": sorted(via)}
            if hit:
                consumers.append(hit)
                seen.add(number)
        for number, it in sorted(items.items()):
            if number in seen or not contracts.get(number):
                continue
            for matched, side in numbers:
                heading = (block["previous_heading"] if side == "previous" else block["current_heading"]) or ""
                obligation = [{"source": source_id, "section": matched, "heading": heading}]
                if CB.named_obligations(contracts[number], obligation, sources):
                    consumers.append({"item": number, "tag": _tag(plan, number), "relationship": "contract", "cited": None,
                                      "matched": matched, "matched_on": side, "via": ["specification"]})
                    seen.add(number)
                    break
        consumers.sort(key=lambda c: (c["item"], RELATIONSHIPS.index(c["relationship"])))
        related, related_seen = [], set()
        for consumer in consumers:
            cnum = consumer["item"]
            it = items[cnum]
            for other in sorted(items):
                if other in seen:
                    continue
                o = items[other]
                links = []
                if other in (it.get("depends") or []):
                    links.append(("dependency", "prerequisite-of-consumer"))
                if cnum in (o.get("depends") or []) or other in (it.get("unblocks") or []):
                    links.append(("dependency", "waits-on-consumer"))
                if other in integration.get(cnum, []) or cnum in integration.get(other, []):
                    links.append(("integration", "counterpart"))
                for relationship, direction in links:
                    key = (other, relationship, direction, cnum)
                    if key in related_seen:
                        continue
                    related_seen.add(key)
                    related.append({"item": other, "tag": _tag(plan, other), "relationship": relationship, "of": cnum,
                                    "direction": direction, "content_consumer": False})
        related.sort(key=lambda r: (r["item"], r["relationship"], r["direction"], r["of"]))
        results.append({"block": block["ref"], "source": source_id, "consumers": consumers, "related": related,
                        "uncited_candidates": []})
    return results


# ---------------------------------------------------------------------------
# Step 5: dispositions
# ---------------------------------------------------------------------------

def _problem(code, block, message):
    return {"code": code, "block": block, "message": message}


def _field_ok(name, value):
    if name == "item":
        return _is_int(value) or not _blank(value)
    if name == "affected":
        return (isinstance(value, list) and len(value) > 0 and all(_is_int(v) or not _blank(v) for v in value)) or not _blank(value)
    return not _blank(value)


def validate_dispositions(changed_blocks, dispositions, formatting_only_auto=False):
    """The problems that keep a set of dispositions from covering a set of changed blocks (specification 8,
    step 5). An empty list means every block has exactly one valid disposition.

    A disposition is a dict with block (the ref of a changed block), disposition (one of DISPOSITIONS) and
    the fields REQUIRED_FIELDS names for it. A field is non-blank text (for "affected" also a non-empty list;
    for "item" also a work item number). Each problem is {"code", "block", "message"}. The codes are
    missing-disposition, duplicate-disposition, unknown-block, unknown-disposition, missing-field,
    malformed-record and patch-without-disposition. A proposed patch is not a disposition: "no proposed
    patch" is never "no impact". With formatting_only_auto a block with formatting_only true needs none."""
    _check_blocks(changed_blocks)
    _need_list(dispositions, "dispositions")
    refs = {b["ref"]: b for b in changed_blocks}
    problems = []
    seen = {}
    for number, record in enumerate(dispositions, 1):
        if not isinstance(record, dict):
            problems.append(_problem("malformed-record", None, f"disposition {number} is not a mapping"))
            continue
        ref = record.get("block")
        kind = record.get("disposition")
        if _blank(ref):
            problems.append(_problem("malformed-record", None, f"disposition {number} names no block"))
            continue
        if ref not in refs:
            problems.append(_problem("unknown-block", ref, f"disposition {number} names a block that is not in the change list"))
            continue
        seen.setdefault(ref, []).append(number)
        if _blank(kind):
            has_patch = not _blank(record.get("patch")) if isinstance(record.get("patch"), str) else bool(record.get("patch"))
            code = "patch-without-disposition" if has_patch else "malformed-record"
            problems.append(_problem(code, ref, "a proposed patch needs a disposition of update" if has_patch
                                     else f"disposition {number} for {ref} has no disposition value"))
            continue
        if kind not in DISPOSITIONS:
            problems.append(_problem("unknown-disposition", ref, f"{ref}: the disposition {str(kind)[:30]!r} is not one of {', '.join(DISPOSITIONS)}"))
            continue
        for name in REQUIRED_FIELDS[kind]:
            if not _field_ok(name, record.get(name)):
                problems.append(_problem("missing-field", ref, f"{ref}: {kind} needs {name}"))
        if kind == "no-impact" and record.get("patch"):
            problems.append(_problem("malformed-record", ref, f"{ref}: no-impact cannot carry a patch. Use update"))
    for ref, numbers in seen.items():
        if len(numbers) > 1:
            problems.append(_problem("duplicate-disposition", ref, f"{ref} has {len(numbers)} dispositions. Each block needs exactly one"))
    for block in changed_blocks:
        if block["ref"] in seen:
            continue
        if formatting_only_auto and block.get("formatting_only"):
            continue
        problems.append(_problem("missing-disposition", block["ref"], f"{block['ref']} has no disposition. No proposed patch is not no impact"))
    return problems


# ---------------------------------------------------------------------------
# Step 8: input digests
# ---------------------------------------------------------------------------

def _digest_map(value, name):
    _need_dict(value, name)
    out = {}
    for path, digest in value.items():
        if not isinstance(path, str) or not path.strip() or "\x00" in path or "\\" in path:
            raise ReconcileError(f"{name} holds a path that is blank or not a plain relative path")
        parts = path.split("/")
        if path.startswith("/") or ".." in parts or "" in parts:
            raise ReconcileError(f"{name} holds a path that is absolute or leaves the project")
        if not isinstance(digest, str) or not _HEX.match(digest):
            raise ReconcileError(f"{name} holds a digest that is not 64 lowercase hex digits")
        out[path] = digest
    return out


def check_input_digests(recorded, current):
    """Compare the input digests recorded with a proposal to the digests of the files now (specification
    8, step 8, and correctness rule 4). Both map a relative path to a SHA-256 in lowercase hex.

    Returns {"changed": [...], "missing": [...], "added": [...], "fresh": bool}. changed paths are in both with
    different digests. missing paths were recorded and are not in current. added paths are in current only.
    Each list is sorted. fresh is true only when all three are empty. An empty record is an error: a proposal
    that recorded no input cannot be called fresh."""
    before = _digest_map(recorded, "recorded")
    after = _digest_map(current, "current")
    if not before:
        raise ReconcileError("recorded holds no digests, so freshness cannot be checked")
    changed = sorted(p for p in before if p in after and before[p] != after[p])
    missing = sorted(p for p in before if p not in after)
    added = sorted(p for p in after if p not in before)
    return {"changed": changed, "missing": missing, "added": added, "fresh": not (changed or missing or added)}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Pure comparison and accounting helpers for project reconciliation. A library: import it, do not "
                    "run it. scripts/reconcile.py uses it.")
    ap.parse_args(argv)
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
