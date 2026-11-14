#!/usr/bin/env python3
"""The decision overlay: what an engineer may append to an approved specification, and nothing more.

Where a project lets engineers record decisions (engineer_edits "allowed"), a specification file may
differ from its approved bytes in one place only: new dated entries at the end of the section
"Decisions recorded". Where a project takes changes as requests ("request-only"), the bytes must be
identical. Standard library only. The functions read nothing from disk and write nothing.

The three places that judge a specification agree on this one contract (section 10 of the design):
  - scripts/release_engineering.py, the independent verifier of pull requests, imports this module;
  - templates/dev-skill/scripts/check_context.py, the engineer's check, carries a copy of the code
    below, because the generated skill ships that script alone;
  - the generated skill tells the engineer the entry form (scripts/generate_dev_skill.py).
The copy in check_context.py must stay source-identical to this file. tests/test_decision_overlay.py
parses both files and fails when any function or constant below differs from its copy.

The rules (validate_overlay)
  request-only   the proposed bytes must equal the approved bytes.
  allowed        1. the file has exactly one heading `## Decisions recorded`, outside code fences, with no
                    other heading of that text at another level, in both versions;
                 2. everything before that heading line and everything from the next heading of level 1
                    or 2 on matches byte for byte;
                 3. inside the section every approved line is kept, in order, unchanged;
                 4. what follows is new entries only. An entry starts a line with `- YYYY-MM-DD.` (a real
                    calendar date). Lines after it, up to the next entry, belong to it. Blank lines may
                    separate entries. Any other text, an undated bullet or an invalid date is rejected;
                 5. the exact initial line `None yet.` is replaced, not kept, when the first entry is
                    appended, and it is never removed without an entry;
                 6. with require_pr_reference, every new entry names a pull request: `#12`, `PR 12`,
                    `pull request 12` or a `/pull/12` link.
The result carries a reason code, the new entries and overlay_sha256, the digest of the new entries
(each without trailing white space, joined by one line feed). The digest is evidence for the owner's
review. It is not an approval.

Reason codes: identical, entries-appended (both ok), body-changed, boundary-malformed, entry-edited,
entry-undated, placeholder-kept, placeholder-removed, pr-reference-missing, encoding-invalid,
policy-unknown, not-bytes.

Run with --help to see this text.
"""
import argparse
import datetime as dt
import hashlib
import re
import sys
from typing import NamedTuple, Optional

# --- begin shared overlay code: keep identical to the copy in templates/dev-skill/scripts/check_context.py ---
OVERLAY_HEADING = b"## Decisions recorded"
OVERLAY_PLACEHOLDER = b"None yet."
OVERLAY_POLICIES = ("allowed", "request-only")
_OVERLAY_ANY_HEADING = re.compile(rb"#{1,6}[ \t]+Decisions[ \t]+recorded[ \t]*#*[ \t]*\Z", re.I)
_OVERLAY_TOP_HEADING = re.compile(rb"#{1,2}[ \t]")
_OVERLAY_FENCE = re.compile(rb"[ \t]{0,3}(```|~~~)")
_OVERLAY_ENTRY = re.compile(rb"- (\d{4})-(\d{2})-(\d{2})\.(?:[ \t]|\Z)")
_OVERLAY_BULLET = re.compile(rb"(?:[-*+]|\d+[.)])[ \t]")
_OVERLAY_PR = re.compile(rb"(?:#\d+\b|/pull/\d+\b|\b(?:PR|pull request)[ \t]+#?\d+\b)", re.I)


class OverlayResult(NamedTuple):
    """ok is True for identical bytes and for a valid overlay. reason is a plain machine code. entries are
    the new entries (text), overlay_sha256 the digest of their text, None when there are none."""
    ok: bool
    reason: str
    entries: tuple
    overlay_sha256: Optional[str]


def _overlay_fail(reason):
    return OverlayResult(False, reason, (), None)


def _overlay_lines(data):
    """The lines of data with their endings. Only a line feed ends a line."""
    return re.findall(rb"[^\n]*\n|[^\n]+", data)


def _overlay_blank(line):
    return not line.strip()


def _overlay_bounds(lines):
    """(heading line index, index of the first line after the section), or None when the section boundary
    is missing, repeated, at another level or cut by an open code fence. Headings inside code fences do
    not count. The section ends at the next heading of level 1 or 2."""
    fence = None
    exact, odd, tops = [], 0, []
    for index, line in enumerate(lines):
        bare = line.rstrip(b"\r\n")
        mark = _OVERLAY_FENCE.match(bare)
        if mark:
            if fence is None:
                fence = mark.group(1)
            elif fence == mark.group(1):
                fence = None
            continue
        if fence is not None:
            continue
        if bare == OVERLAY_HEADING:
            exact.append(index)
        elif _OVERLAY_ANY_HEADING.match(bare):
            odd += 1
        if _OVERLAY_TOP_HEADING.match(bare):
            tops.append(index)
    if fence is not None or len(exact) != 1 or odd:
        return None
    start = exact[0]
    after = [i for i in tops if i > start]
    return start, (after[0] if after else len(lines))


def _overlay_split_blank(lines):
    """(lines up to the last one that holds text, the blank lines after it)."""
    end = len(lines)
    while end and _overlay_blank(lines[end - 1]):
        end -= 1
    return lines[:end], lines[end:]


def _overlay_entries(lines):
    """The new entries in lines as a list of bytes, or the reason code when the lines are not entries only."""
    entries = []
    for line in lines:
        bare = line.rstrip(b"\r\n")
        start = _OVERLAY_ENTRY.match(bare)
        if start:
            try:
                dt.date(int(start.group(1)), int(start.group(2)), int(start.group(3)))
            except ValueError:
                return "entry-undated"
            entries.append([line])
        elif not entries:
            if bare.strip():
                return "entry-undated"
        elif _OVERLAY_BULLET.match(bare):
            return "entry-undated"
        else:
            entries[-1].append(line)
    return [b"".join(parts).rstrip() for parts in entries]


def validate_overlay(approved_bytes, proposed_bytes, policy, require_pr_reference=False):
    """Judge proposed_bytes (the specification in the working tree or the pull request) against
    approved_bytes (the version a verified receipt lists) under policy, allowed or request-only. Returns an
    OverlayResult. Both arguments are bytes. Nothing is read or written."""
    try:
        approved, proposed = bytes(approved_bytes), bytes(proposed_bytes)
    except (TypeError, ValueError):
        return _overlay_fail("not-bytes")
    if policy not in OVERLAY_POLICIES:
        return _overlay_fail("policy-unknown")
    if approved == proposed:
        return OverlayResult(True, "identical", (), None)
    if policy == "request-only":
        return _overlay_fail("body-changed")
    old_lines, new_lines = _overlay_lines(approved), _overlay_lines(proposed)
    old_bounds, new_bounds = _overlay_bounds(old_lines), _overlay_bounds(new_lines)
    if old_bounds is None or new_bounds is None:
        return _overlay_fail("boundary-malformed")
    (old_start, old_end), (new_start, new_end) = old_bounds, new_bounds
    if old_lines[:old_start + 1] != new_lines[:new_start + 1] or old_lines[old_end:] != new_lines[new_end:]:
        return _overlay_fail("body-changed")
    old_core, old_blank = _overlay_split_blank(old_lines[old_start + 1:old_end])
    new_core, new_blank = _overlay_split_blank(new_lines[new_start + 1:new_end])
    lead = 0
    while lead < len(old_core) and _overlay_blank(old_core[lead]):
        lead += 1
    placeholder = len(old_core) == lead + 1 and old_core[lead].rstrip(b"\r\n") == OVERLAY_PLACEHOLDER
    if placeholder:
        if not new_core:
            return _overlay_fail("placeholder-removed")
        if new_core[:lead] != old_core[:lead]:
            return _overlay_fail("entry-edited")
        added = new_core[lead:]
        if added and added[0].rstrip(b"\r\n") == OVERLAY_PLACEHOLDER:
            return _overlay_fail("placeholder-kept" if len(added) > 1 else "body-changed")
    else:
        keep = len(old_core)
        if len(new_core) < keep:
            return _overlay_fail("entry-edited")
        if keep:
            last = old_core[-1]
            if new_core[:keep - 1] != old_core[:keep - 1] or (new_core[keep - 1] != last and new_core[keep - 1].rstrip(b"\r\n") != last):
                return _overlay_fail("entry-edited")
        added = new_core[keep:]
        if not added:
            return _overlay_fail("body-changed")
    found = _overlay_entries(added)
    if isinstance(found, str):
        return _overlay_fail(found)
    if not found:
        return _overlay_fail("entry-undated")
    if require_pr_reference and not all(_OVERLAY_PR.search(entry) for entry in found):
        return _overlay_fail("pr-reference-missing")
    try:
        entries = tuple(entry.decode("utf-8").replace("\r\n", "\n") for entry in found)
    except UnicodeDecodeError:
        return _overlay_fail("encoding-invalid")
    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return OverlayResult(True, "entries-appended", entries, digest)
# --- end shared overlay code ---


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
