#!/usr/bin/env python3
"""Compile one approved-context bundle for each work item. Offline. Standard library only.

A bundle is what an engineer's coding agent reads instead of the ground truth. For one work item
it holds the verbatim text of every source section the item cites (its obligations), the
decisions that settle a conflict between cited sections, the other work items that cite the same
sections, and what the approved text may be used for downstream. The compiler writes two files per
item, named for the item id in lower case:

  docs/context/wi-06.md            Markdown for the agent
  docs/context/wi-06.bundle.json   the sidecar: obligations with their digests, conflicts, uses

The identity of a bundle is the SHA-256 of its Markdown file (content_sha256 in the sidecar). It
never holds a release id: the release id is the digest of a manifest that lists the bundle, so the
bundle cannot name it.

Where things are read from
  plan       the plan the owner works from: <workspace>/drafts/plan.yaml when it exists, else the
             project's plan.yaml (--plan overrides both)
  renderings <workspace>/renderings/ when the owner answered no to the one question, else
             docs/ground-truth/ (--renderings overrides both)
  specs      the folder named by project.spec_dir, under <workspace>/drafts/ when that exists, else
             the project (--spec-dir overrides both)

What a work item cites. Its bundle holds every section named in its source_refs, in the References lines of
its specification (`- <source id> section <n.n>, <heading>`) and in relative links from the specification
into a rendering (docs/ground-truth/<source id>.md#<anchor>). A whole-document reference becomes one
obligation with the section "whole document", whose text is the whole rendering without its generated
header comment. The version of an obligation is the version of the source in the plan.

Restricted items. A work item marked restricted in the workspace plan gets no bundle and appears in no
other bundle. When the owner also wrote a restricted_placeholder for it, it gets a placeholder bundle
instead: no source section, only its id, the owner's restricted_summary and the owner's instruction, and
`"restricted_destination": true` in the sidecar. That is what makes the engineers' check print the fourth
message. An item without a placeholder is unknown to the engineers' check, which says "no approved context".

Completeness. The compiler stops if a section a work item cites is not in the rendering of its
source, and says `obligation not found: <source id> <n>`. It prints for each item "obligations
present: n of n". Presence is checked by the machine. Whether the text is enough to do the work is
for the plan owner to judge, and the release preview says so.

Commands (a dry run unless --apply)
  python3 scripts/compile_bundles.py --root .                  dry run: the table, nothing written
  python3 scripts/compile_bundles.py --root . --apply          write under <workspace>/candidate/snapshot/repo/
  python3 scripts/compile_bundles.py --root . --out DIR --apply   write DIR/docs/context/... instead

Exit status is 0 when every obligation is present, 1 when one is missing or the plan has problems,
and 2 for a wrong argument or a refused path. Nothing is sent anywhere.

Library use. `compile_bundles(plan, renderings_dir, spec_dir, defaults)` returns a dict that maps
`docs/context/<id>.md` and `docs/context/<id>.bundle.json` to their bytes and writes nothing, so
the release command can build a snapshot in memory. `compile_report` also returns the table rows
and the problems, without raising.
"""
import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402
import release_gate as RG  # noqa: E402

BUNDLE_FORMAT = 1
CONTEXT_DIR = "docs/context"
DEFAULT_DOWNSTREAM = {"code": True, "tests": True, "issues": False, "evidence": "synthetic-only"}
DOWNSTREAM_FLAGS = ("code", "tests", "issues")
EVIDENCE_VALUES = ("synthetic-only", "approved")
CANDIDATE_SUBDIR = ("candidate", "snapshot", "repo")
UNVERSIONED = "unversioned"

# Plan item keys that are not free text about the work. Any other text key of an item (a key the
# owner added, such as decisions) is read for conflict notes.
_STRUCTURAL_ITEM_KEYS = frozenset("""id slug label milestone track owner theme complete_by size depends unblocks
checkpoint external_input source_refs ground_truth skill_needs state downstream restricted restricted_summary
restricted_placeholder restricted_evidence program_input""".split())

_NUMBER = r"\d+(?:\.\d+)*"
_HEADING_NUMBER = re.compile(r"^(" + _NUMBER + r")\.?\s+(\S.*)$")
_HEADER_VERSION = re.compile(r"<!-- Generated from .*? version (.+?) on \d{4}-\d\d-\d\d\.")
_DATE = re.compile(r"\b\d{4}-\d\d-\d\d\b")
_IDENT = re.compile(r"\b[A-Z][A-Z0-9]*-\d+(?:\.\d+)*\b")
_STRUCTURE = ("## Obligations", "## Conflict resolution that applies", "## Shared obligations")
WHOLE = "whole document"
_CITATION_LINE = re.compile(r"^\s*[-*]\s+([a-z0-9]+(?:-[a-z0-9]+)*)\s+[Ss]ection\s+(" + _NUMBER + r")\s*(?:,\s*(.*?))?\s*$")
_LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_FENCE = re.compile(r"(?ms)^(`{3,}|~{3,}).*?^\1[ \t]*$")


class CompileError(ValueError):
    """The bundles cannot be compiled. problems holds one-line messages with ids, never text."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


class Section(NamedTuple):
    number: str
    heading: str
    text: str


class Result(NamedTuple):
    files: dict      # path -> bytes. Empty when there are problems
    rows: list       # (item tag, label, present, total) in plan order
    problems: list   # one-line messages


def section_key(number):
    """Sort key of a section number. The whole document sorts before every numbered section."""
    return (-1,) if number == WHOLE else tuple(int(part) for part in number.split("."))


def parse_rendering(text):
    """The numbered sections of a rendering as {number: Section}. A section runs from its heading
    to the next heading of the same or a higher level, so it holds its subsections. Its text is
    normalized and leaves out the heading line and the blank lines around it. The first heading with
    a given number wins. Headings inside code fences are not headings."""
    lines = text.replace("\r\n", "\n").split("\n")
    heads = L.collect_headings(lines)
    found = {}
    for pos, (line_no, level, title) in enumerate(heads):
        m = _HEADING_NUMBER.match(re.sub(r"[`*_]", "", title).strip())
        if not m or m.group(1) in found:
            continue
        end = len(lines)
        for later_line, later_level, _ in heads[pos + 1:]:
            if later_level <= level:
                end = later_line - 1
                break
        body = "\n".join(lines[line_no:end]).strip("\n")
        found[m.group(1)] = Section(m.group(1), m.group(2).strip(), L.normalize_section_text(body) if body.strip() else "\n")
    return found


def whole_document(text, fallback_title):
    """The Section that stands for a whole rendering: its text without the generated header comment,
    normalized, headed by the title of the document."""
    body = "\n".join(l for l in text.replace("\r\n", "\n").split("\n") if not l.startswith("<!-- Generated from")).strip("\n")
    title = next((t for _, level, t in L.collect_headings(body.split("\n")) if level == 1), "") or fallback_title
    return Section(WHOLE, re.sub(r"[`*_]", "", title).strip() or fallback_title, L.normalize_section_text(body) if body.strip() else "\n")


def rendering_version(text):
    """The version the renderer recorded in the header comment, or "" when there is none."""
    m = _HEADER_VERSION.search(text)
    version = m.group(1).strip() if m else ""
    return "" if version == UNVERSIONED else version


def cited_sections(ref):
    """The section numbers of one source_refs entry, in the order written, without repeats. The text
    "whole document" yields ["whole document"]: one obligation that holds the whole rendering."""
    sections = str(ref.get("sections") or "")
    numbers = list(dict.fromkeys(re.findall(r"\b" + _NUMBER + r"\b", sections)))
    if not numbers and sections.strip().casefold() == WHOLE:
        return [WHOLE]
    return numbers


def spec_cited_keys(text, sources, sections_of):
    """[(source id, section)] that a specification cites beyond its header: the lines of its References
    section written `- <source id> section <n.n>, <heading>`, and relative links into a rendering
    (.../ground-truth/<source id>.md#<anchor>), where the anchor names a heading of that rendering. A
    link to a heading the rendering does not have cites nothing. Code blocks are not read.
    sections_of(source id) returns the {number: Section} of its rendering, or None."""
    keys = []
    marker = "\n## References\n"
    start = text.find(marker)
    if start >= 0:
        for line in text[start + len(marker):].split("\n"):
            if line.startswith("## "):
                break
            m = _CITATION_LINE.match(line)
            if m and (m.group(1), m.group(2)) not in keys:
                keys.append((m.group(1), m.group(2)))
    for m in _LINK.finditer(_FENCE.sub("", text)):
        path, _, anchor = m.group(1).partition("#")
        parts = Path(path).parts
        if not anchor or not path.endswith(".md") or len(parts) < 2 or parts[-2] != "ground-truth" or Path(path).stem not in sources:
            continue
        sid = Path(path).stem
        sections = sections_of(sid) or {}
        for number, section in sections.items():
            if number != WHOLE and L.anchor_slug(f"{number} {section.heading}") == anchor and (sid, number) not in keys:
                keys.append((sid, number))
    return keys


def item_obligation_keys(plan, item, extra=()):
    """[(source id, section number)] that item cites in its source_refs, plus extra (what its specification
    cites), sorted by source precedence and section."""
    order = {s["id"]: n for n, s in enumerate(L.ground_truth_sources(plan))}
    keys = []
    for ref in L.item_source_refs(plan, item):
        sid = ref.get("source")
        for number in cited_sections(ref):
            if (sid, number) not in keys:
                keys.append((sid, number))
    keys += [k for k in extra if k not in keys]
    return sorted(keys, key=lambda k: (order.get(k[0], len(order)), section_key(k[1])))


def downstream_for(plan, item, defaults):
    """(downstream flags, problems) for one item: the defaults, then the owner's per-item override in
    items[].downstream of the workspace plan."""
    flags = dict(DEFAULT_DOWNSTREAM)
    flags.update(defaults or {})
    handling = (plan.get("project") or {}).get("handling")
    plan_down = handling.get("downstream") if isinstance(handling, dict) else None
    if "evidence" not in (defaults or {}) and isinstance(plan_down, dict) and plan_down.get("evidence") in EVIDENCE_VALUES:
        flags["evidence"] = plan_down["evidence"]
    problems = []
    override = item.get("downstream")
    tag = L.tag(plan, item["id"])
    if override is None:
        return flags, problems
    if not isinstance(override, dict):
        return flags, [f"{tag}: downstream must be a mapping of code, tests, issues and evidence"]
    for key, value in override.items():
        if key in DOWNSTREAM_FLAGS and isinstance(value, bool):
            flags[key] = value
        elif key == "evidence" and value in EVIDENCE_VALUES:
            flags[key] = value
        elif key in DOWNSTREAM_FLAGS or key == "evidence":
            problems.append(f"{tag}: downstream.{key} has an unsupported value")
        else:
            problems.append(f"{tag}: downstream has an unknown key {str(key)[:30]!r}")
    return flags, problems


def downstream_sentence(flags):
    if flags["code"] and flags["tests"]:
        use = "approved for implementation in this repository's code and tests"
    elif flags["code"]:
        use = "approved for implementation in this repository's code, not in tests"
    elif flags["tests"]:
        use = "approved for this repository's tests, not for code"
    else:
        use = "not approved for use in this repository's code or tests"
    issues = "May be quoted in issue text." if flags["issues"] else "Not for quoting in issue text."
    evidence = ("Evidence may include response bodies with synthetic data only." if flags["evidence"] == "synthetic-only"
                else "Evidence may include real data that the plan owner approved.")
    return f"Downstream use: {use}. {issues} {evidence}"


def watch_out_notes(spec_text):
    """The bullets of the "Watch out for" section of a specification as one-line strings."""
    m = re.search(r"(?ms)^## Watch out for\s*\n(.*?)(?=^## |\Z)", spec_text)
    if not m:
        return []
    notes, current = [], None
    for line in m.group(1).split("\n"):
        if re.match(r"^\s{0,3}[-*]\s+", line):
            if current is not None:
                notes.append(current)
            current = re.sub(r"^\s*[-*]\s+", "", line).strip()
        elif line.strip() and current is not None and line.startswith((" ", "\t")):
            current += " " + line.strip()
        elif not line.strip() and current is not None:
            notes.append(current)
            current = None
    if current is not None:
        notes.append(current)
    return [" ".join(n.split()) for n in notes if n.strip()]


def plan_notes(item):
    """Text the owner kept in extra fields of a plan item (a key that is not part of the plan schema)."""
    notes = []
    for key, value in item.items():
        if key in _STRUCTURAL_ITEM_KEYS or str(key).startswith("_"):
            continue
        values = [value] if isinstance(value, str) else [v for v in value if isinstance(v, str)] if isinstance(value, list) else []
        notes += [" ".join(v.split()) for v in values if v.strip()]
    return notes


def _alternatives(source):
    return [a for a in (source.get("id"), source.get("name")) if isinstance(a, str) and a.strip()]


def named_obligations(text, obligations, sources):
    """The obligations (dicts with source, section and heading) that text names. It names one when
    it says "section n.n" and the number is a cited section, when n.n stands beside the id or the
    name of the cited source, or when it uses an identifier from the heading of a cited section
    (such as GOV-1 or GOV-1.5 for a heading "4.1 GOV-1 Approval limits")."""
    folded = text.casefold()
    hits = []

    def add(ob):
        if ob not in hits:
            hits.append(ob)

    for number in L.explicit_sections(text):
        candidates = [ob for ob in obligations if ob["section"] == number]
        if len(candidates) > 1:
            named = [ob for ob in candidates
                     if any(a.casefold() in folded for a in _alternatives(sources.get(ob["source"], {"id": ob["source"]})))]
            candidates = named or candidates
        for ob in candidates:
            add(ob)
    for ob in obligations:
        alts = _alternatives(sources.get(ob["source"], {"id": ob["source"]}))
        for alt in alts:
            a, n = re.escape(alt), re.escape(ob["section"])
            if re.search(rf"(?i)(?<![\w-]){a}(?![\w-])\W{{0,4}}(?:sections?\s+)?{n}(?![\d.]*\d)", text) or \
               re.search(rf"(?i)(?<![\d.]){n}(?![\d.]*\d)\s+(?:of|in)\s+(?:the\s+)?{a}(?![\w-])", text):
                add(ob)
        for ident in _IDENT.findall(ob["heading"]):
            if re.search(rf"(?<![\w-]){re.escape(ident)}(?:\.\d+)*(?![\w-])", text):
                add(ob)
    return sorted(hits, key=obligations.index)


def _obligation_label(ob):
    return f"{ob['source']} {ob['section']}"


def _bundle_markdown(tag, item, obligations, flags, source_versions, sources, conflicts, shared):
    used = []
    for ob in obligations:
        if ob["source"] not in used:
            used.append(ob["source"])
    status = lambda sid: str(sources.get(sid, {}).get("status") or "reviewed")
    source_line = ", ".join(f"{sid} {source_versions[sid]} ({status(sid)})" for sid in used) or "none"
    out = [f"# Approved context for {tag}, {item['label']}", "",
           f"Bundle format {BUNDLE_FORMAT}. Sources: {source_line}.",
           downstream_sentence(flags), "", "## Obligations", ""]
    if not obligations:
        out += ["This work item cites no source sections.", ""]
    for ob in obligations:
        out += [f"### {_obligation_label(ob)} {ob['heading']}", "", ob["_text"].rstrip("\n"), ""]
    out += ["## Conflict resolution that applies", ""]
    out += [f"- {c['decision']}" for c in conflicts] or ["None recorded."]
    out += ["", "## Shared obligations", ""]
    out += [f"- {_obligation_label(ob)} {ob['heading']}, also cited by {', '.join(shared[(ob['source'], ob['section'])])}."
            for ob in obligations if shared.get((ob["source"], ob["section"]))] or ["None."]
    return "\n".join(out).rstrip("\n") + "\n"


def placeholder_files(plan, item, defaults=None):
    """{path: bytes} of the bundle of a restricted item that has a published placeholder (WP9). It holds
    no source section: only the item's id, the owner's restricted_summary and the owner's
    restricted_placeholder instruction, plus fixed words. The sidecar says restricted_destination, which
    makes the engineers' check print the fourth message. Nothing else of the item is used."""
    tag = L.tag(plan, item["id"])
    flags = dict(DEFAULT_DOWNSTREAM)
    flags.update(defaults or {})
    handling = (plan.get("project") or {}).get("handling")
    plan_down = handling.get("downstream") if isinstance(handling, dict) else None
    if "evidence" not in (defaults or {}) and isinstance(plan_down, dict) and plan_down.get("evidence") in EVIDENCE_VALUES:
        flags["evidence"] = plan_down["evidence"]
    flags.update({"code": False, "tests": False, "issues": False})
    out = [f"# Approved context for {tag}, {L.restricted_summary(item)}", "",
           f"Bundle format {BUNDLE_FORMAT}. Sources: none.",
           "Downstream use: none. This work item has a restricted destination that this project does not publish.", "",
           "## Obligations", "", "This work item cites no source sections.", "",
           "## Conflict resolution that applies", "", "None recorded.", "",
           "## Shared obligations", "", "None.", "",
           "## Instruction from the plan owner", "", L.restricted_placeholder(item), ""]
    markdown = "\n".join(out).rstrip("\n") + "\n"
    sidecar = {"bundle_format": BUNDLE_FORMAT, "work_item": tag, "obligations": [], "conflicts": [], "shared_with": [],
               "downstream": flags, "content_sha256": L.sha256_text(markdown), "extensions": {}, "restricted_destination": True}
    base = f"{CONTEXT_DIR}/{tag.lower()}"
    return {base + ".md": markdown.encode("utf-8"), base + ".bundle.json": L.canonical_json(sidecar)}


def compile_report(plan, renderings_dir, spec_dir, defaults=None):
    """Compile every work item of plan. Returns a Result(files, rows, problems). files is empty when
    there are problems. Nothing is written. plan is the loaded workspace plan; renderings_dir holds
    one rendering per source (the file name of source.path); spec_dir is the folder named by
    project.spec_dir, the one that holds the milestone folders. A specification that is not there
    contributes no conflict notes."""
    sources = L.source_by_id(plan)
    ordered = L.ground_truth_sources(plan)
    problems = []
    rendered = {}                 # source id -> ({number: Section}, version) or None when missing
    items = [it for it in plan["items"] if not L.restricted_item(it)]

    def load(sid):
        if sid in rendered:
            return rendered[sid]
        source = sources.get(sid)
        rendered[sid] = None
        if source is None:
            return None
        name = Path(str(source.get("path") or f"{sid}.md")).name
        path = Path(renderings_dir) / name
        if not L.exists(path):
            return None
        try:
            text = L.read_text(path)
        except L.TextError:
            problems.append(f"the rendering of source {sid} cannot be read as UTF-8 text")
            return None
        version = str(source.get("version") or "").strip() or rendering_version(text) or UNVERSIONED
        found = parse_rendering(text)
        found[WHOLE] = whole_document(text, str(source.get("name") or sid))
        rendered[sid] = (found, version)
        return rendered[sid]

    def sections_of(sid):
        got = load(sid)
        return got[0] if got else None

    def spec_file_of(it):
        folder = next((m["folder"] for m in plan["milestones"] if m["number"] == it["milestone"]), "")
        return Path(spec_dir) / folder / f"{L.tag(plan, it['id']).lower()}-{it['slug']}.md"

    spec_text = {}               # item id -> text of its specification, when there is one
    for it in items:
        spec_file = spec_file_of(it)
        if L.exists(spec_file):
            try:
                spec_text[it["id"]] = L.read_text(spec_file)
            except L.TextError:
                problems.append(f"the specification of {L.tag(plan, it['id'])} cannot be read as UTF-8 text")
    keys_of = {it["id"]: item_obligation_keys(plan, it, spec_cited_keys(spec_text.get(it["id"], ""), sources, sections_of)) for it in items}
    cited_by = {}
    for it in items:
        for key in keys_of[it["id"]]:
            cited_by.setdefault(key, []).append(it["id"])

    built = {}                   # item id -> (obligations, flags, conflicts)
    rows = []
    for it in items:
        tag = L.tag(plan, it["id"])
        obligations = []
        for sid, number in keys_of[it["id"]]:
            got = load(sid)
            section = got[0].get(number) if got else None
            if section is None:
                problems.append(f"obligation not found: {sid} {number} (cited by {tag})")
                continue
            if any(line in _STRUCTURE for line in section.text.split("\n")):
                problems.append(f"obligation text collides with the bundle layout: {sid} {number} (cited by {tag})")
                continue
            obligations.append({"source": sid, "section": number, "heading": section.heading,
                                "_text": section.text, "_version": got[1]})
        rows.append((tag, it["label"], len(obligations), len(keys_of[it["id"]])))
        flags, down_problems = downstream_for(plan, it, defaults)
        problems += down_problems
        notes = watch_out_notes(spec_text[it["id"]]) if it["id"] in spec_text else []
        notes += plan_notes(it)
        conflicts, seen = [], set()
        for note in notes:
            hits = named_obligations(note, obligations, sources)
            if not hits or note in seen:
                continue
            seen.add(note)
            date = _DATE.search(note)
            conflicts.append({"between": [_obligation_label(ob) for ob in hits], "decision": note,
                              "recorded": date.group(0) if date else None})
        built[it["id"]] = (obligations, flags, conflicts)
    if problems:
        return Result({}, rows, problems)

    order = {i["id"]: n for n, i in enumerate(items)}
    files = {}
    for it in items:
        tag = L.tag(plan, it["id"])
        obligations, flags, conflicts = built[it["id"]]
        shared = {}
        for ob in obligations:
            others = sorted((i for i in cited_by[(ob["source"], ob["section"])] if i != it["id"]), key=lambda i: order[i])
            if others:
                shared[(ob["source"], ob["section"])] = [L.tag(plan, i) for i in others]
        versions = {ob["source"]: ob["_version"] for ob in obligations}
        markdown = _bundle_markdown(tag, it, obligations, flags, versions, sources, conflicts, shared).encode("utf-8")
        shared_with = sorted({t for tags in shared.values() for t in tags}, key=lambda t: int(t.rsplit("-", 1)[1]))
        sidecar = {
            "bundle_format": BUNDLE_FORMAT,
            "work_item": tag,
            "obligations": [{"source": ob["source"], "version": ob["_version"], "section": ob["section"],
                             "heading": ob["heading"], "sha256": L.sha256_text(ob["_text"])} for ob in obligations],
            "conflicts": conflicts,
            "shared_with": shared_with,
            "downstream": flags,
            "content_sha256": L.sha256_text(markdown.decode("utf-8")),
            "extensions": {},
        }
        base = f"{CONTEXT_DIR}/{tag.lower()}"
        files[base + ".md"] = markdown
        files[base + ".bundle.json"] = L.canonical_json(sidecar)
    for it in plan["items"]:
        if L.restricted_placeholder(it):
            files.update(placeholder_files(plan, it, defaults))
    return Result(files, rows, [])


def compile_bundles(plan, renderings_dir, spec_dir, defaults=None):
    """The bundles of every work item as {path: bytes}, written nowhere. Raises CompileError, with
    problems like `obligation not found: <source id> <n>`, when a cited section is missing."""
    result = compile_report(plan, renderings_dir, spec_dir, defaults)
    if result.problems:
        raise CompileError(result.problems)
    return result.files


def parse_obligations(markdown):
    """The obligation blocks of a bundle's Markdown as [(source, section, heading, text)], with the
    text normalized. Used to check a bundle against its sidecar digests."""
    text = markdown.decode("utf-8") if isinstance(markdown, (bytes, bytearray)) else markdown
    m = re.search(r"(?ms)^## Obligations\n\n(.*?)(?=^## Conflict resolution that applies\n)", text)
    if not m:
        return []
    heads = list(re.finditer(rf"(?m)^### (\S+) ({_NUMBER}|{WHOLE}) (.+)$", m.group(1)))
    out = []
    for n, h in enumerate(heads):
        end = heads[n + 1].start() if n + 1 < len(heads) else len(m.group(1))
        out.append((h.group(1), h.group(2), h.group(3), L.normalize_section_text(m.group(1)[h.end():end].strip("\n"))))
    return out


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _within(path, folder):
    """True when path is folder or lies under it, after links are resolved."""
    p, f = Path(path).resolve(), Path(folder).resolve()
    return p == f or f in p.parents


def _shown(path, root):
    """A folder as the owner sees it: relative to the project when it is inside it."""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return "the folder given with --renderings"


def locate_plan(root, workspace, explicit):
    """The plan path: --plan, else the workspace plan (drafts/plan.yaml), else the project's."""
    if explicit:
        return Path(explicit)
    if workspace is not None and L.exists(Path(workspace) / "drafts" / "plan.yaml"):
        return Path(workspace) / "drafts" / "plan.yaml"
    return L.find_plan(root)


def locate_spec_dir(plan, root, workspace, explicit):
    rel = plan["project"]["spec_dir"]
    if explicit:
        return Path(explicit)
    if workspace is not None and (Path(workspace) / "drafts" / rel).is_dir():
        return Path(workspace) / "drafts" / rel
    return Path(root) / rel


def locate_renderings(plan, root, workspace, why, explicit):
    """(folder, None) where the renderings are, or (None, message)."""
    if explicit:
        return Path(explicit), None
    handling = (plan.get("project") or {}).get("handling")
    approved = handling.get("repo_audience_approved") if isinstance(handling, dict) else None
    if approved is False:
        if workspace is None:
            return None, f"{why}: the documents of this project are private, so the renderings are in the private workspace, and none is usable"
        return Path(workspace) / "renderings", None
    return Path(root) / "docs" / "ground-truth", None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Compile one approved-context bundle per work item (docs/context/<id>.md and <id>.bundle.json) "
                    "from the cited source sections of the renderings. Dry run unless --apply.")
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to the plan (default: the workspace plan, else <root>/docs/spec/plan.yaml)")
    ap.add_argument("--spec-dir", help="the specification folder, the one that holds the milestone folders")
    ap.add_argument("--renderings", help="the folder that holds the renderings (default: the private workspace on the no path, else docs/ground-truth)")
    ap.add_argument("--out", help="write <out>/docs/context/... (default: <workspace>/candidate/snapshot/repo/). Relative to --root")
    ap.add_argument("--apply", action="store_true", help="write the files. Without it this is a dry run")
    a = ap.parse_args(argv)
    root = L.project_root(a.root)
    workspace, why = L.workspace_root(root)
    plan_path = locate_plan(root, workspace, a.plan)
    if not L.exists(plan_path):
        L.die(f"no plan at {plan_path}")
    plan, plan_problems = L.load_plan(plan_path, root)
    if plan.get("_view") == "released":
        L.die("this is a released plan: it has no source paths. Compile from the workspace plan (schema-view-mismatch)")
    if plan_problems:
        L.say("the plan has problems:")
        for p in plan_problems:
            L.say("  - " + p)
        return 1
    renderings, bad = locate_renderings(plan, root, workspace, why, a.renderings)
    if renderings is None:
        L.die(bad)
    spec_dir = locate_spec_dir(plan, root, workspace, a.spec_dir)
    if a.out:
        out = Path(a.out)
        out = out if out.is_absolute() else root / out
    elif workspace is not None:
        out = Path(workspace).joinpath(*CANDIDATE_SUBDIR)
    else:
        out = None
        if a.apply:
            L.die(f"{why}: there is no private workspace to hold the candidate. Create one with workspace.py init, or give --out")
    result = compile_report(plan, renderings, spec_dir)
    in_workspace = workspace is not None and _within(renderings, workspace)
    L.say(f"bundles: {len(result.rows)} work item(s), renderings from {'the private workspace' if in_workspace else _shown(renderings, root)}")
    width = max([len(r[0]) for r in result.rows] or [5])
    for tag, label, present, total in result.rows:
        L.say(f"  {tag.ljust(width)}  obligations present: {present} of {total}   {label}")
    L.say("Presence is checked here. Whether each bundle is enough to do the work is your review.")
    for p in result.problems:
        L.say("  " + p)
    if result.problems:
        L.say(f"{len(result.problems)} problem(s). No bundle was compiled.")
        return 1
    if out is None:
        L.say(f"{len(result.files)} file(s) would be written. Dry run, and there is no private workspace: give --out or create one.")
        return 0
    inside_project = L.path_inside_repository(root, out)
    write_class = "candidate" if workspace is not None and _within(out, workspace) or not inside_project else "draft"
    for rel in sorted(result.files):
        decision = RG.check(write_class, rel, L.sha256_text(result.files[rel].decode("utf-8")), "workspace" if write_class == "candidate" else "engineering", str(root))
        if not decision.allowed:
            L.die(f"{decision.code}: the release gate refused the write of {rel}. Nothing was written")
    stale = []
    context = out / CONTEXT_DIR
    if context.is_dir():
        stale = sorted(p.name for p in context.iterdir() if p.is_file() and p.name.endswith((".md", ".bundle.json"))
                       and f"{CONTEXT_DIR}/{p.name}" not in result.files)
    target = "the project" if inside_project else "the candidate folder"
    L.say(f"{len(result.files)} file(s) {'written' if a.apply else 'would be written'} under {CONTEXT_DIR}/ in {target}." + ("" if a.apply else " Dry run. Add --apply to write."))
    for name in stale:
        L.say(f"  not in this compile and left in place: {CONTEXT_DIR}/{name}")
    if a.apply:
        for rel, data in sorted(result.files.items()):
            path = out / rel
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            except OSError as e:
                L.die(f"cannot write {rel}: {e.strerror or e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
