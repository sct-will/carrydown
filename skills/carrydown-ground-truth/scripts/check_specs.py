#!/usr/bin/env python3
"""Check the work item specifications against plan.yaml. Read only.

This script behaves as a drift checker. It reads how far the specifications have drifted from
the plan and from the ground truth sections they cite, and it fails when they have. It never
corrects anything. The plan owner or the engineer makes the correction, with the agent, and the
check runs again. In continuous integration a failure blocks the merge.

Checks, per work item
  the file exists at <spec_dir>/<milestone folder>/<id>-<slug>.md
  the title line is "# <ID> <label>"
  the header table carries the values the plan implies (milestone, track, target,
  checkpoint right after target, demonstration, size, depends on, unblocks, ground truth)
  the sections appear in the template order
  "Evidence of completion" and "Integration points" are present and not empty
  the file is within the length bounds
  banned vocabulary (dashes, people named in the plan, AI vendor names, sprint words,
  "open questions", "non-goals"; the lists are in plan.yaml under banned)
  no reference to the id of an external item, no reference to an unknown id
  no broken relative link
  ground truth sections cited in the header exist in the named rendered sources
Per milestone: milestone.md exists with the required parts and lists every item.
Per project: README.md in the spec folder lists every item.

Also checks the plan itself: dates, owners, dependencies, cycles, weekends, days off, breaks, the
percent allocation of each person (1 to 100), that nobody is over 100 percent of their allocated
capacity in a work unit, and, when a target exists, that the last work item meets it. People and the
target are optional. Without a target the report prints the critical path end date as derived.

Views. The check follows the plan_view the plan declares. A plan with no plan_format is legacy and keeps the
original rules: every original and rendering named in the plan must be there. --view workspace or --view released
forces one. In the workspace view the cited sections must exist in the renderings (in the project or in the
renderings folder of the private workspace) and an original is optional unless you pass --check-originals. In the
released view there is no source, no rendering and no path to either: every section a work item cites, in source_refs
or in a line `- <source id> section <n.n>, <heading>` of its References section, must be listed in its approved
context, docs/context/<id>.bundle.json, whose content_sha256 equals the digest of docs/context/<id>.md and whose
two files an active receipt in docs/release/ lists with their digests. A missing or altered obligation fails. A
relative link into docs/ground-truth/ is not broken when the approved context holds the section it points to.

Owner side. Where .carrydown/local.yaml names the private workspace, the check also reports a restricted source
that the repository tracks (by source id, never by path). The detectors of detectors.py run over the specification
folder, docs/context, docs/release and the engineers' skill folder. Findings name a file and a line, never the text.

Log hygiene. A finding about a person's name, a header row or a malformed record never quotes the file. It names the
row, the file and the line, or the person's id and the key.

Staffing. A migrated plan (plan_format 2) names people by id and track only. Names, allocation, start
dates, days off, skills and preferences are in people.yaml in the private workspace, found through
.carrydown/local.yaml, or named with --people. With that file the capacity, dates and names checks run as
always. Without it they are skipped, and the output says so in one line: people overlay not loaded:
capacity, dates and names not checked. A people.yaml that is tracked in the project is never a fallback.

The planning review reads how the plan is composed. Findings: a milestone that covers one track with
no single_track_reason, and a milestone without a rationale or a joint_demonstration, or a track
with items and no order_rationale. Advisory lines in the report: the tracks each milestone covers and
whether the joint check at its demonstration names them, items that complete on their checkpoint
date, theme switches per owner, a critical path owned by one person, and the load ratio between people.

Usage
  python3 scripts/check_specs.py --root .            check everything
  python3 scripts/check_specs.py --root . --report   print the schedule, load table and critical path
  python3 scripts/check_specs.py --root . --people ~/.carrydown/workspaces/my-project/people.yaml   load the staffing overlay by path
  python3 scripts/check_specs.py --root . --item 3   check one item (3, WI-03 and wi-3 all work)
  python3 scripts/check_specs.py --root . --view released   check the exported plan against its approved context
Exit status is 0 when clean, and 1 when there are findings, including problems with the values in
plan.yaml, which are listed first. It is 2 when the plan cannot be read at all (a missing file, a
syntax error, a value of the wrong shape) or an argument is wrong. With --json the output on
standard output is always one JSON object, also on an error. The script never writes files.
"""
import argparse
import contextlib
import datetime
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import detectors as D  # noqa: E402
import release_schema as RS  # noqa: E402

HERE = Path(__file__).resolve().parent


def _ships(*rel):
    """True when a file this script's messages name ships next to it: in the same skill when the
    script is an installed copy, or in the ground-truth skill when it is the repository's master.
    A copy in another skill names the skill instead, so no message points at a missing file."""
    return any((d.joinpath(*rel)).is_file() for d in (HERE.parent, HERE.parent / "skills" / "carrydown-ground-truth"))


def _script_hint(name, what):
    """`name` when that script ships next to this one, else the skill that has it."""
    return f"{name} {what}".strip() if (HERE / name).is_file() else "the carrydown-ground-truth skill"


OVERLAY_NOTE = "people overlay not loaded: capacity, dates and names not checked"

MILESTONE_PARTS = ["Purpose", "Expected outcomes", "Acceptance criteria", "Demonstration expectations", "Work items"]


def strip_code(text):
    return re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def banned_patterns(plan):
    b = plan["banned"]
    pats = []
    if b.get("dashes", True):
        pats.append((re.compile("[" + chr(0x2014) + chr(0x2013) + "]"), "em or en dash"))
    if plan["_banned_names"]:
        alt = "|".join(re.escape(n) for n in plan["_banned_names"])
        pats.append((re.compile(r"(?i)(?<![\w-])(" + alt + r")(?![\w-])"), "person name or handle from the plan"))
    if plan.get("_banned_exact"):
        alt = "|".join(re.escape(n) for n in plan["_banned_exact"])
        pats.append((re.compile(r"(?<![\w-])(" + alt + r")(?![\w-])"), "person name or handle from the plan"))
    for key, why in (("vendors", "AI vendor or model reference"), ("words", "banned word"), ("phrases", "banned phrase")):
        pats_list = b.get(key) or []
        if pats_list:
            pats.append((re.compile(r"(?i)(?:" + "|".join(f"\\b(?:{p})\\b" if not p.startswith("\\b") else p for p in pats_list) + ")"), why))
    return pats


NAME_WHY = "person name or handle from the plan"


def banned_hits(pats, text):
    """(why, line number, line text) for each banned match. A match inside a longer match of the same
    kind is not counted again, so "Tamsin Hale" is one finding, not one for the full name and one
    for each part. The line text of a person's name or handle is empty: it is never carried, so it
    cannot be printed."""
    out, spans = [], []
    for pat, why in pats:
        for m in pat.finditer(text):
            if any(w == why and s <= m.start() and m.end() <= e for w, s, e in spans):
                continue
            spans.append((why, m.start(), m.end()))
            ln = text.count("\n", 0, m.start()) + 1
            out.append((why, ln, "" if why == NAME_WHY else text.split("\n")[ln - 1].strip()[:90]))
    return out


def banned_issue(why, rel, ln):
    """The finding for one banned match: what kind, the file and the line. Never the text of the line."""
    return f"{why} at {Path(str(rel)).as_posix()}:{ln}"


def citation_numbers(text):
    return re.findall(r"\b(\d+(?:\.\d+)*)\b", text or "")


def cited_missing(numbered, cite):
    """Section numbers in cite that are not a numbered heading of the rendering."""
    return [num for num in citation_numbers(cite)
            if not any(h.startswith(num + " ") or h.startswith(num + ". ") for h in numbered)]


def view_of(plan):
    """legacy, workspace or released: the view the plan was loaded in."""
    return plan.get("_view") or L.plan_mode(plan)


def rendering_file(source, root, workspace=None):
    """Where the rendering of a source is, or None. It is the path in the plan, under the project, or, when
    that file is not there, the same file name in the renderings folder of the private workspace, where the
    renderer puts the rendering of a source the repository must not hold."""
    rel = source.get("path")
    if not isinstance(rel, str) or not rel.strip():
        return None
    p = Path(root) / rel
    if L.exists(p):
        return p
    if workspace:
        alt = Path(workspace) / "renderings" / Path(rel).name
        if L.exists(alt):
            return alt
    return p


def ground_truth_headings(plan, root, workspace=None):
    """Headings by source id. None marks a rendered source that is missing."""
    found = {}
    for source in L.rendered_sources(plan):
        p = rendering_file(source, root, workspace)
        if p is None or not L.exists(p):
            found[source["id"]] = None
            continue
        heads = []
        fence = False
        for line in L.read_text(p).split("\n"):
            if line.strip().startswith("```"):
                fence = not fence
            if fence:
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", line)
            if m:
                heads.append(m.group(2).strip())
        found[source["id"]] = heads
    return found


def numbered_headings(gt_heads):
    return [h for h in (gt_heads or []) if re.match(r"^\d+(\.\d+)*\.?\s", h)]


def citation_findings(plan, root, gt_heads, view=None, check_originals=False):
    """Say when the section citations could not be checked, instead of passing silently.

    The view decides what is read. legacy keeps the original behavior: every original and every
    rendering named in the plan must be there. workspace checks the cited rendering sections, and an
    original only when the owner asks (check_originals): a retained rendering is enough to prepare.
    released reads no source and no rendering. Its citations are checked per work item against the
    approved context bundles and the receipts (see released_item_findings), so nothing is checked here
    and a missing original or full rendering is never a finding."""
    view = view or view_of(plan)
    if view == "released" or not plan["items"]:
        return []
    findings = []
    if view == "legacy" or check_originals:
        for source in L.ground_truth_sources(plan):
            original = source.get("source_path")
            if original and not L.exists(Path(root) / original):
                findings.append(f"ground truth source not found: {original} ({source['name']})")
    sources = L.rendered_sources(plan)
    for source in sources:
        heads = gt_heads.get(source["id"])
        label = "the rendered document" if len(sources) == 1 else f"the rendered source {source['name']}"
        if heads is None:
            findings.append(f"ground truth citations not checked: {label} {source.get('path') or source['id']} was not found. Render it with {_script_hint('render_ground_truth.py', '')}")
        elif not numbered_headings(heads):
            findings.append(f"ground truth citations not checked: {label} has no numbered headings. "
                            "Specifications cite sections by number, so number the headings in the source document and render it again")
    return findings


# ---------------------------------------------------------------------------
# Released view: citations are satisfied by the approved context bundle of the work item
# ---------------------------------------------------------------------------

CITATION_LINE = re.compile(r"^\s*[-*]\s+([a-z0-9]+(?:-[a-z0-9]+)*)\s+[Ss]ection\s+(\d+(?:\.\d+)*)\s*(?:,\s*(.*?))?\s*$")
WHOLE_DOCUMENT = "whole document"
_UTC = datetime.timezone.utc
BUNDLE_PROBLEM_LEADS = ("approved context", "bundle ", "no active receipt")


def reference_citations(text):
    """[(source id, section, line)] for each citation line of the ## References section of a
    specification: `- <source id> section <n.n>, <heading>`, the heading optional."""
    marker = "\n## References\n"
    start = text.find(marker)
    if start < 0:
        return []
    first = text.count("\n", 0, start) + 2
    out = []
    for offset, line in enumerate(text[start + len(marker):].split("\n")):
        if line.startswith("## "):
            break
        m = CITATION_LINE.match(line)
        if m:
            out.append((m.group(1), m.group(2), first + offset))
    return out


def needed_obligations(plan, it):
    """[(source id, section)] that the plan's source_refs of an item require, in order. A reference to
    the whole document needs a bundle obligation for the whole document."""
    out = []
    for ref in L.item_source_refs(plan, it):
        sid, sections = ref.get("source"), str(ref.get("sections") or "")
        nums = citation_numbers(sections)
        wanted = [(sid, n) for n in nums] if nums else ([(sid, WHOLE_DOCUMENT)] if sections.strip().casefold() == WHOLE_DOCUMENT else [])
        for pair in wanted:
            if pair not in out:
                out.append(pair)
    return out


class Release:
    """What the released view reads from the project: the receipts under docs/release/ that are valid,
    active and not expired, and the problems found in the others. Built once per run."""

    def __init__(self, root, now=None):
        self.root = Path(root)
        self.now = now or datetime.datetime.now(_UTC)
        self.receipts = []     # (file name, parsed receipt) of each active receipt
        self.problems = []
        folder = self.root / "docs" / "release"
        if not folder.is_dir():
            return
        for path in sorted(folder.glob("*.receipt.json")):
            name = f"docs/release/{path.name}"
            if L.regular_file_problem(path):
                self.problems.append(f"{name} cannot be read as a receipt")
                continue
            try:
                receipt = RS.validate_receipt(path.read_bytes())
            except RS.SchemaError as e:
                self.problems.append(f"{name} is not a valid receipt ({e.code})")
                continue
            except OSError:
                self.problems.append(f"{name} cannot be read as a receipt")
                continue
            if path.name != f"{receipt['request_id']}.receipt.json":
                self.problems.append(f"{name} is not named after its request id (receipt-projection-mismatch)")
                continue
            if receipt["state"] != "active":
                continue
            if receipt["expires_at"] and self._expired(receipt["expires_at"]):
                self.problems.append(f"{name} has expired")
                continue
            self.receipts.append((path.name, receipt))

    def _expired(self, stamp):
        try:
            when = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_UTC)
        except ValueError:
            return True
        return when <= self.now

    def covers(self, rel, data):
        """True when an active receipt lists the project file rel with the digest and length of data."""
        digest, size = RS.sha256_bytes(data), len(data)
        for _, receipt in self.receipts:
            for art in receipt["artifacts"]:
                if art["path"] == rel and art["sha256"] == digest and art["bytes"] == size:
                    return True
        return False


def _sidecar_problem(side, tag):
    """A fixed reason why a parsed sidecar is not a bundle sidecar, or None."""
    if not isinstance(side, dict):
        return "it is not an object"
    if type(side.get("bundle_format")) is not int or side.get("bundle_format") != 1:
        return "bundle_format is not 1"
    if side.get("work_item") != tag:
        return "work_item is not this work item"
    obligations = side.get("obligations")
    if not isinstance(obligations, list):
        return "obligations is not a list"
    keys = {"source", "version", "section", "heading", "sha256"}
    for o in obligations:
        if not isinstance(o, dict) or set(o) != keys or not all(isinstance(o[k], str) for k in keys):
            return "an obligation is malformed"
        if not re.fullmatch(r"[0-9a-f]{64}", o["sha256"]):
            return "an obligation digest is malformed"
    digest = side.get("content_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return "content_sha256 is malformed"
    return None


def bundle_coverage(plan, root, it, release):
    """What the approved context of a work item covers: (covered, problems). covered maps each
    (source id, section) pair that the item's bundle lists and that is intact to its heading: the sidecar parses,
    its content_sha256 equals the digest of the Markdown file, and an active receipt lists both files
    with the digests of the files as they are. A broken bundle covers nothing. problems are one-line
    findings and never carry bundle text."""
    tag = L.tag(plan, it["id"])
    low = tag.lower()
    md_rel, js_rel = f"docs/context/{low}.md", f"docs/context/{low}.bundle.json"
    problems = []
    data = {}
    for rel in (md_rel, js_rel):
        path = Path(root) / rel
        if L.regular_file_problem(path) or not path.is_file():
            problems.append(f"approved context missing: {rel}")
        else:
            try:
                data[rel] = path.read_bytes()
            except OSError:
                problems.append(f"approved context cannot be read: {rel}")
    if problems:
        return {}, problems
    try:
        side = RS.loads_strict(data[js_rel])
    except RS.SchemaError:
        return {}, [f"bundle {js_rel} is not strict JSON (duplicate keys and invalid JSON are refused)"]
    why = _sidecar_problem(side, tag)
    if why:
        return {}, [f"bundle {js_rel} is not a bundle sidecar: {why}"]
    if side["content_sha256"] != RS.sha256_bytes(data[md_rel]):
        return {}, [f"bundle {md_rel} does not match content_sha256 in {js_rel}"]
    missing = [rel for rel in (md_rel, js_rel) if not release.covers(rel, data[rel])]
    if missing:
        return {}, [f"no active receipt in docs/release/ lists {rel} with its current digest" for rel in missing]
    versions = {s.get("id"): str(s.get("version") or "") for s in plan.get("sources") or []}
    covered = {}
    for o in side["obligations"]:
        if versions.get(o["source"]) is not None and versions[o["source"]] != o["version"]:
            problems.append(f"obligation {o['source']} {o['section']} was approved for another version of the source than the plan names")
            continue
        covered[(o["source"], o["section"])] = o["heading"]
    return covered, problems


def released_item_findings(plan, root, it, text, release):
    """Findings for one work item in the released view, and the (source id, section) pairs its bundle
    covers. Every section the item cites, in its source_refs or in its References section, must be in
    its approved context. A missing or altered obligation is a failure, not a skipped check."""
    needed = needed_obligations(plan, it)
    cites = reference_citations(text)
    known = {s.get("id") for s in plan.get("sources") or []}
    issues = []
    for sid, sec, ln in cites:
        if sid not in known:
            issues.append(f"References cites unknown source {sid} at line {ln}")
    wanted = list(needed) + [(sid, sec) for sid, sec, _ in cites if sid in known and (sid, sec) not in needed]
    if not wanted:
        return issues, {}
    covered, problems = bundle_coverage(plan, root, it, release)
    issues += problems
    if not any(p.startswith(BUNDLE_PROBLEM_LEADS) for p in problems):
        for sid, sec in wanted:
            if (sid, sec) not in covered:
                issues.append(f"obligation not in the approved context: {sid} {sec}")
    return issues, covered


def reference_findings(plan, text, gt_heads):
    """Workspace and legacy views: a citation in the References section is satisfied when the rendering
    has that section, the same check as source_refs. Returns one-line findings."""
    out = []
    sources = L.source_by_id(plan)
    for sid, sec, ln in reference_citations(text):
        if sid not in sources:
            out.append(f"References cites unknown source {sid} at line {ln}")
            continue
        heads = numbered_headings(gt_heads.get(sid))
        if heads and cited_missing(heads, sec):
            out.append(f"References cites {sid} section {sec} at line {ln}, which is not a heading in the rendered source")
    return out


def link_is_satisfied(plan, root, target, anchor, covered, gt_heads, view):
    """True when a relative link that points into the renderings folder (docs/ground-truth/<source id>.md)
    cites a section the project can vouch for without the file. In the released view the section is in the
    item's approved context (covered, which maps (source id, section) to its heading). In the workspace and
    legacy views it is a heading of the rendering that the checker found in the private workspace. The
    anchor is the heading as GitHub makes it. A link to a section that is in neither is still broken."""
    try:
        rel = Path(target).relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return False
    if not rel.startswith("docs/ground-truth/") or not rel.endswith(".md") or not anchor:
        return False
    sid = Path(rel).stem
    if sid not in {s.get("id") for s in plan.get("sources") or []}:
        return False
    if view == "released":
        return any(source == sid and L.anchor_slug(f"{sec} {heading}") == anchor for (source, sec), heading in covered.items())
    return anchor in {L.anchor_slug(h) for h in (gt_heads.get(sid) or [])}


def plan_review_findings(plan, root, banned):
    """Banned-name patterns over docs/spec/plan-review.md, which the checker did not scan before.
    Returns (findings, relative path). No file is no finding."""
    path = Path(root) / plan["project"]["spec_dir"] / "plan-review.md"
    rel = path.relative_to(root) if path.is_relative_to(root) else path
    if not L.exists(path):
        return [], rel
    try:
        text = L.read_text(path)
    except L.TextError as e:
        return [f"cannot read: {e.msg}"], rel
    return [banned_issue(why, rel, ln) for why, ln, _ in banned_hits(banned, text)], rel


# ---------------------------------------------------------------------------
# Owner side: restricted sources that git tracks
# ---------------------------------------------------------------------------

NOT_PERFORMED = "tracked source check not performed"


def tracked_source_findings(workspace_plan, root):
    """Owner side. For each source the workspace plan classifies restricted, ask git whether the original
    or the rendering is tracked, and report `restricted source is tracked in git: <source id>`. The finding
    names the source by id and never by path. Only non-empty, known paths go into the command, and an empty
    list of paths means no command at all (an empty pathspec would list the whole project). When git is not
    installed, or the project is not in a git repository, the one line returned starts with
    `tracked source check not performed` and says why: nothing was verified."""
    pending = []
    for source in workspace_plan.get("sources") or []:
        if not isinstance(source, dict) or source.get("classification") != "restricted":
            continue
        paths = []
        for key in ("source_path", "path"):
            v = source.get(key)
            if isinstance(v, str) and v.strip():
                paths.append(v.strip())
                if key == "path" and v.strip().endswith(".md"):
                    paths.append(v.strip()[:-3] + ".index.txt")   # the rendering's index lists its headings
        if paths:
            pending.append((source.get("id") or "unnamed", paths))
    if not pending:
        return []
    if shutil.which("git") is None:
        return [f"{NOT_PERFORMED}: git is not available, so nothing was verified"]
    findings = []
    for sid, paths in pending:
        cmd = ["git", "-C", str(root), "ls-files", "-z", "--"] + [":(literal)" + p for p in paths]
        try:
            run = subprocess.run(cmd, capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return [f"{NOT_PERFORMED}: git could not be run, so nothing was verified"]
        if run.returncode != 0:
            return [f"{NOT_PERFORMED}: the project folder is not in a git repository, so nothing was verified"]
        if run.stdout.strip(b"\0"):
            findings.append(f"restricted source is tracked in git: {sid}")
    return findings


def check_item(plan, root, it, banned, gt_heads, release=None):
    """Findings for one work item, as (issues, relative path). A finding names the row, the line or the
    id and never quotes the file, so a log of the check holds no text of the specification. release is
    the Release of the project, needed in the released view."""
    issues = []
    path = L.spec_path(plan, root, it)
    tg = L.tag(plan, it["id"])
    rel = path.relative_to(root) if path.is_relative_to(root) else path
    view = view_of(plan)
    if not L.exists(path):
        return [f"MISSING {rel}"], rel
    try:
        spec = L.read_spec(path)
    except L.TextError as e:
        return [f"cannot read: {e.msg}"], rel
    text, lines, rows = spec["text"], spec["lines"], spec["rows"]
    expected_title = f"# {tg} {it['label']}"
    if spec["title"] != expected_title:
        issues.append("title line does not match the plan")
    exp = L.expected_header(plan, it)
    for name, val in exp:
        got = rows.get(name)
        if got is None:
            issues.append(f"header lacks the {name} row")
            continue
        if name == "Depends on":
            for d in it["depends"]:
                if L.tag(plan, d) not in got:
                    issues.append(f"Depends on lacks {L.tag(plan, d)}")
            if it["external_input"] and "external input" not in got.lower():
                issues.append("Depends on lacks the external input note")
            if not it["external_input"] and "external input" in got.lower():
                issues.append("Depends on has an external input note the plan does not")
            if not it["depends"] and not it["external_input"] and got.strip().lower() not in ("none", "none."):
                issues.append("Depends on should say None")
        elif name == "Unblocks":
            for u in it["unblocks"]:
                if L.tag(plan, u) not in got:
                    issues.append(f"Unblocks lacks {L.tag(plan, u)}")
            extra = set(re.findall(rf"{re.escape(plan['project']['id_prefix'])}-\d+", got)) - {L.tag(plan, u) for u in it["unblocks"]}
            if extra:
                issues.append(f"Unblocks names items the plan does not: {sorted(extra)}")
        elif name in ("Size", "Ground truth"):
            if not got.strip() or "to be " in got.lower():
                issues.append(f"{name} row is not filled in")
        elif got != val:
            issues.append(f"{name} row does not match plan.yaml")
    order = spec["row_order"]
    if "Target" in order and "Checkpoint" in order and order.index("Checkpoint") != order.index("Target") + 1:
        issues.append("Checkpoint row is not directly after Target")
    # sections in order
    pos = -1
    for sec in L.SECTIONS:
        cands = sec if isinstance(sec, tuple) else (sec,)
        found = [text.find("\n## " + c + "\n") for c in cands]
        found = [f for f in found if f >= 0]
        if not found:
            issues.append("section missing: " + " or ".join(cands))
            continue
        f = min(found)
        if f < pos:
            issues.append(f"section out of order: {cands[0]}")
        pos = f
    # evidence and integration
    for sec in ("Evidence of completion", "Integration points"):
        body = L.section_text(spec, sec)
        if body:
            n_body = len([l for l in body.split("\n") if l.strip()])
            if n_body < 4:
                issues.append(f"{sec} is too short ({n_body} non-empty lines)")
            if sec == "Evidence of completion" and L.EVIDENCE_LEAD not in body:
                issues.append(f"Evidence of completion lacks the {L.EVIDENCE_LEAD} lead")
            if sec == "Integration points":
                for lead in L.INTEGRATION_LEADS:
                    if lead not in body:
                        issues.append(f"Integration points lacks {lead}")
    for sec in ("Acceptance criteria",):
        body = L.section_text(spec, sec)
        if body and not re.search(r"(?m)^- \[ \] ", body):
            issues.append("Acceptance criteria has no checkbox items (- [ ] ...)")
    for m in re.finditer(r"\bTODO\b", strip_code(text)):
        issues.append(f"unfinished template text (TODO) at line {text.count(chr(10), 0, m.start()) + 1}")
        break
    tail = text.split("## Decisions recorded")[-1]
    if "None yet." not in tail and not re.search(r"(?m)^- \d{4}-\d\d-\d\d\.", tail):
        issues.append("Decisions recorded has neither 'None yet.' nor a dated entry")
    lo, hi = plan["limits"]["spec_lines"]
    n = len([l for l in lines])
    if n < lo or n > hi:
        issues.append(f"length {n} lines is outside {lo} to {hi}")
    scan_text = strip_code(text) if plan["banned"].get("skip_code_blocks") else text
    for why, ln, _ in banned_hits(banned, scan_text):
        issues.append(banned_issue(why, rel, ln))
    prefix = re.escape(plan["project"]["id_prefix"])
    pids = L.external_ids(plan)
    known = {it2["id"] for it2 in plan["items"]}
    for m in re.finditer(rf"\b{prefix}-(\d+)\b", text):
        num = int(m.group(1))
        ln = text.count("\n", 0, m.start()) + 1
        if num in pids:
            issues.append(f"reference to external item id {m.group(0)} at line {ln}")
        elif num not in known:
            issues.append(f"reference to unknown id {m.group(0)} at line {ln}")
    covered = {}
    if view == "released":
        # The released project holds no original and no rendering. Every section the item cites is
        # satisfied by its approved context bundle, which an active receipt covers.
        extra, covered = released_item_findings(plan, root, it, text, release or Release(root))
        issues += extra
    else:
        issues += reference_findings(plan, text, gt_heads)
    prose = strip_code(text)
    for m in re.finditer(r"\[([^\]]*)\]\(((?!https?://|mailto:|#)[^)\s]+)(?:\s+\"[^\"]*\")?\)", prose):
        target, _, anchor = m.group(2).partition("#")
        if target and not L.exists((path.parent / target).resolve()):
            if link_is_satisfied(plan, root, (path.parent / target).resolve(), anchor, covered, gt_heads, view):
                continue   # a link into the renderings folder whose section the approved context or the workspace holds
            issues.append(f"broken relative link {m.group(2)}")
    # ground truth citations
    cite = rows.get("Ground truth", "")
    refs = L.item_source_refs(plan, it)
    sources = L.source_by_id(plan)
    expected_cite = L.ground_truth_citation(plan, it)
    if cite and expected_cite and cite != expected_cite:
        issues.append("Ground truth row does not match plan.yaml")
    if not it.get("source_refs") and refs:
        primary_heads = numbered_headings(gt_heads.get(refs[0].get("source")))
        if primary_heads and cite and "to be " not in cite.lower():
            for num in cited_missing(primary_heads, cite):
                issues.append(f"Ground truth cites section {num}, which is not a heading in the rendered document")
    for ref in refs:
        sid, sections = ref.get("source"), ref.get("sections", "")
        source = sources.get(sid, {})
        numbered = numbered_headings(gt_heads.get(sid))
        if sections and str(sections).strip().casefold() != "whole document" and not citation_numbers(sections):
            issues.append(f"plan.yaml source_refs for {sid}: give numbered sections or plan-owner-confirmed whole document coverage. Preview plan_repair.py")
        if numbered and sections and "to be " not in sections.lower():
            for num in cited_missing(numbered, sections):
                if it.get("source_refs"):
                    issues.append(f"Ground truth cites {source.get('name', sid)} section {num}, which is not a heading in {source.get('path', 'the rendered source')}")
                else:
                    issues.append(f"plan.yaml ground_truth of this item cites section {num}, which is not a heading in the rendered document")
    return issues, rel


def check_milestone(plan, root, ms):
    issues = []
    path = L.milestone_path(plan, root, ms)
    rel = path.relative_to(root) if path.is_relative_to(root) else path
    if not L.exists(path):
        return [f"MISSING {rel}"], rel
    try:
        text = L.read_text(path)
    except L.TextError as e:
        return [f"cannot read: {e.msg}"], rel
    first = text.split("\n", 1)[0].strip()
    expected = f"# Milestone {ms['number']}, {ms['name']}"
    if first != expected:
        issues.append("title line does not match the plan")
    spec = L.read_spec(path)
    for part in MILESTONE_PARTS:
        if part not in spec["sections"]:
            issues.append(f"section missing: {part}")
    for row, want in (("Due", ms["end"]), ("Exit gate", ms["gate"])):
        got = spec["rows"].get(row)
        if got is None:
            issues.append(f"header lacks the {row} row")
        elif got != want:
            issues.append(f"{row} row does not match plan.yaml")
    demo = spec["rows"].get("Demonstration")
    if demo is None:
        issues.append("header lacks the Demonstration row")
    elif ms["demo"] not in demo:
        issues.append(f"Demonstration row does not carry the date {ms['demo']}")
    if re.search(r"\bTODO\b", text):
        issues.append("unfinished template text (TODO)")
    crit = L.section_text(spec, "Acceptance criteria")
    if len(re.findall(r"(?m)^- \[ \] ", crit)) < 3:
        issues.append("Acceptance criteria needs at least three checkbox items")
    outc = L.section_text(spec, "Expected outcomes")
    if len([l for l in outc.split("\n") if l.strip().startswith("- ")]) < 2:
        issues.append("Expected outcomes needs at least two bullet items")
    work = L.section_text(spec, "Work items")
    for it in plan["items"]:
        if it["milestone"] == ms["number"] and L.tag(plan, it["id"]) not in work:
            issues.append(f"Work items table lacks {L.tag(plan, it['id'])}")
    for m in re.finditer(rf"\b{re.escape(plan['project']['id_prefix'])}-(\d+)\b", text):
        if int(m.group(1)) in L.external_ids(plan):
            issues.append(f"reference to external item id {m.group(0)}")
    for why, ln, _ in banned_hits(banned_patterns(plan), text):
        issues.append(banned_issue(why, rel, ln))
    for m in re.finditer(r"\]\(((?!https?://|mailto:|#)[^)\s]+)\)", strip_code(text)):
        if not L.exists((path.parent / m.group(1).split("#")[0]).resolve()):
            issues.append(f"broken relative link {m.group(1)}")
    return issues, rel


def check_readme(plan, root):
    issues = []
    path = Path(root) / plan["project"]["spec_dir"] / "README.md"
    rel = path.relative_to(root) if path.is_relative_to(root) else path
    if not L.exists(path):
        return [f"MISSING {rel}"], rel
    try:
        text = L.read_text(path)
    except L.TextError as e:
        return [f"cannot read: {e.msg}"], rel
    for it in plan["items"]:
        if L.tag(plan, it["id"]).lower() not in text.lower():
            issues.append(f"index lacks {L.tag(plan, it['id'])}")
    for h in ("Closing comment on an issue", "Checkpoint comment on the Epic", "Index"):
        if f"## {h}" not in text and f"### {h}" not in text:
            issues.append(f"section missing: {h}")
    for why, ln, _ in banned_hits(banned_patterns(plan), text):
        issues.append(banned_issue(why, rel, ln))
    return issues, rel


def orphan_files(plan, root):
    known = {L.spec_path(plan, root, it).resolve() for it in plan["items"]}
    out = []
    for ms in plan["milestones"]:
        folder = Path(root) / plan["project"]["spec_dir"] / ms["folder"]
        if folder.is_dir():
            for f in sorted(folder.glob("*.md")):
                if f.name != "milestone.md" and f.resolve() not in known:
                    out.append(str(f.relative_to(root)))
    return out


def fmt(d):
    return L.fmt_date(d)


def planning_review(plan):
    """Read how the plan is composed. Returns (findings, lines).

    Findings fail the check. Lines are the advisory text of the report's planning review block,
    with each finding repeated in its place, marked "finding"."""
    findings, lines = [], []
    tl = lambda t: L.track_label(plan, t)
    tags = lambda its: ", ".join(L.tag(plan, it["id"]) for it in its)
    used = [t.get("id") for t in plan["tracks"] if any(it.get("track") == t.get("id") for it in plan["items"])]

    def finding(text):
        findings.append(text)
        lines.append("    finding: " + text)

    lines.append("  Milestone composition (rules 1 to 3)")
    for ms in plan["milestones"]:
        head = f"Milestone {ms['number']}, {ms['name']}"
        covered = L.milestone_tracks(plan, ms)
        if not covered:
            lines.append(f"    {head}: no items yet.")
            continue
        lines.append(f"    {head}: " + ", ".join(f"{tl(t)} ({tags(its)})" for t, its in covered) + ("" if len(covered) > 1 else " only") + ".")
        if len(covered) == 1 and len(used) > 1:
            if ms.get("single_track_reason"):
                lines.append(f"      One track, because: {ms['single_track_reason']}")
            else:
                finding(f"milestone {ms['number']} covers one track ({tl(covered[0][0])}) and has no single_track_reason. "
                        "Add an item from the other track the capability crosses, or say why it stays inside one track")
        cp = L.demo_checkpoint(plan, ms)
        if cp is None:
            lines.append(f"      No checkpoint on the demonstration date {ms['demo']}, so the tracks have no named joint check there.")
        else:
            named = L.tracks_named(plan, cp.get("joint_check", ""))
            want = [t for t, _ in covered] if len(covered) > 1 else used
            missing = [t for t in want if t not in named]
            if not missing:
                lines.append(f"      The joint check on {cp['date']} names " + " and ".join(tl(t) for t in want) + ".")
            else:
                lines.append(f"      The joint check on {cp['date']} does not name " + " or ".join(tl(t) for t in missing) + ". Name each track that meets there.")
        for k, what in (("rationale", "why these items form it"), ("joint_demonstration", "what the engineers show together")):
            if not ms.get(k):
                finding(f"milestone {ms['number']} has no {k}: write {what} in plan.yaml")

    lines.append("  Order of work per track (rules 4, 5 and 10)")
    for t in plan["tracks"]:
        its = sorted((it for it in plan["items"] if it.get("track") == t.get("id")), key=lambda it: (it["complete_by"], it["id"]))
        if not its:
            continue
        lines.append(f"    {tl(t.get('id'))}: {tags(its)}." + (" Order rationale given." if t.get("order_rationale") else ""))
        if not t.get("order_rationale"):
            finding(f"track {t.get('id')} has no order_rationale: say in plan.yaml why its items are in this order")

    lines.append("  Theme switches (consecutive items of one owner, by date)")
    if not any(it.get("theme") for it in plan["items"]):
        lines.append("    No item has a theme. Add theme to the items to count the switches.")
    else:
        owners = []
        for it in plan["items"]:
            if it.get("owner") and it["owner"] not in owners:
                owners.append(it["owner"])
        mss = L.milestone_by_num(plan)
        for who in owners:
            its = sorted((it for it in plan["items"] if it.get("owner") == who), key=lambda it: (it["complete_by"], it["id"]))
            pairs = []
            for a, b in zip(its, its[1:]):
                if (a.get("theme") or "no theme") != (b.get("theme") or "no theme"):
                    where = (f"inside milestone {a['milestone']}" if a["milestone"] == b["milestone"]
                             else f"across milestones {a['milestone']} and {b['milestone']}")
                    pairs.append((a, b, where, a["milestone"] == b["milestone"]))
            inside = sum(1 for p in pairs if p[3])
            lines.append(f"    {who}: {len(pairs)} switch{'' if len(pairs) == 1 else 'es'}, {inside} inside a milestone.")
            for a, b, where, _ in pairs:
                lines.append(f"      {L.tag(plan, a['id'])} ({a.get('theme') or 'no theme'}) to {L.tag(plan, b['id'])} ({b.get('theme') or 'no theme'}), {where}.")

    lines.append("  Slack before checkpoints (rule 7)")
    none = [it for it in plan["items"] if it.get("complete_by") == it.get("checkpoint")]
    for it in none:
        lines.append(f"    {L.tag(plan, it['id'])} completes on its checkpoint date {it['checkpoint']}: no slack.")
    if plan["items"] and not none:
        least = min(plan["items"], key=lambda it: (L.slack_days(plan, it), it["id"]))
        lines.append(f"    Every item completes before its checkpoint. The least slack is {L.slack_days(plan, least)} working day(s), "
                     f"{L.tag(plan, least['id'])} before {least['checkpoint']}.")

    lines.append("  Critical path owners (rule 8)")
    _, path = L.critical_path(plan)
    items = L.item_by_id(plan)
    if path:
        by = {}
        for n in path:
            by.setdefault(items[n].get("owner") or "no owner", []).append(L.tag(plan, n))
        lines.append("    " + " -> ".join(L.tag(plan, n) for n in path) + ": " + ", ".join(f"{w} ({', '.join(v)})" for w, v in by.items()) + ".")
        if len(by) == 1 and len(plan["people"]) > 1 and "no owner" not in by:
            who = next(iter(by))
            track = items[path[0]].get("track")
            said = [f"the {tl(t.get('id'))} order rationale" for t in plan["tracks"] if "critical path" in (t.get("order_rationale") or "").lower()]
            said += [f"the milestone {m['number']} rationale" for m in plan["milestones"] if "critical path" in (m.get("rationale") or "").lower()]
            lines.append(f"    The critical path runs through one person, {who}, on the {tl(track)} track. "
                         + (f"The plan speaks to it in {' and '.join(said)}." if said else "Say so in the plan and offer an alternative."))

    lines.append("  Load ratio (rule 6)")
    tot = {}
    for pid, _, sized, cap, _ in (L.load_rows(plan) if L.staffing_loaded(plan) else []):
        s_, c_ = tot.get(pid, (0.0, 0.0))
        tot[pid] = (s_ + sized, c_ + cap)
    if not L.staffing_loaded(plan):
        lines.append("    Capacity is not known without the people overlay, so there is no ratio.")
    elif len(tot) < 2:
        lines.append("    Fewer than two people in the plan, so there is no ratio.")
    else:
        share = {pid: (100.0 * s_ / c_ if c_ else 0.0) for pid, (s_, c_) in tot.items()}
        lines.append("    Share of allocated capacity over the plan: " + ", ".join(
            f"{pid} {tot[pid][0]:g} of {tot[pid][1]:.0f}d ({share[pid]:.0f}%)" for pid in tot) + ".")
        hi, lo = max(share, key=share.get), min(share, key=share.get)
        if share[lo] <= 0:
            lines.append(f"    {lo} has no sized work, so the ratio is not defined. Above two to one: move items across tracks where the skills allow.")
        else:
            r = share[hi] / share[lo]
            lines.append(f"    Highest to lowest is {r:.1f} to 1 ({hi} to {lo})." + (" Above two to one: move items across tracks where the skills allow, or stretch the date." if r > 2 else ""))
    return findings, lines


def report(plan):
    people = {p["id"]: p for p in plan["people"]}
    print(f"Plan: {plan['project']['name']}")
    ds = L.derived_summary(plan)
    if ds:
        print(f"Derived inputs: {ds}. Replace the placeholders when you know the real values.")
    print("\nSources (highest precedence first)")
    for n, source in enumerate(L.ground_truth_sources(plan), 1):
        status = source.get("status", "reviewed")
        rendered = source.get("path") or "not rendered"
        print(f"  {n}. {source['name']}: {status}; {source.get('source_path', rendered)} -> {rendered}")
        if source.get("limit"):
            print(f"     Coverage limit: {source['limit']}")
    staffed = L.staffing_loaded(plan)
    if not staffed:
        print(f"\n{OVERLAY_NOTE}")
    print("\nStaffing context (advisory)")
    has_staffing_context = any(t.get("skill_needs") for t in plan["tracks"]) or any(
        p.get("skills") or p.get("preferences") or p.get("assignment_rationale") for p in plan["people"]
    ) or any(it.get("skill_needs") for it in plan["items"])
    if not staffed:
        print("  Skills, preferences and names are in the private people file, which is not loaded. Track needs:")
        for track in plan["tracks"]:
            if track.get("skill_needs"):
                print(f"  Track {track['id']} needs: {', '.join(track['skill_needs'])}")
    elif not has_staffing_context:
        print("  No skills or work preferences were supplied. The plan uses the default track, capacity, dependency and context-switching rules.")
    else:
        for track in plan["tracks"]:
            if track.get("skill_needs"):
                print(f"  Track {track['id']} needs: {', '.join(track['skill_needs'])}")
        for person in plan["people"]:
            skills = ", ".join(person.get("skills") or []) or "not supplied"
            preferences = ", ".join(person.get("preferences") or []) or "not supplied"
            print(f"  {person['id']} on {person.get('track', 'unassigned')}: skills {skills}; preferences {preferences}")
            if person.get("assignment_rationale"):
                print(f"    Assignment rationale: {person['assignment_rationale']}")
        for item in plan["items"]:
            if item.get("skill_needs"):
                print(f"  {L.tag(plan, item['id'])} needs: {', '.join(item['skill_needs'])}")
        print("  Skills and preferences guide the agent's proposed match. They do not make the checker pass or fail; uncertain matches use the default assignment rules.")
    print("\nSchedule")
    for m in plan["milestones"]:
        print(f"  Work unit {m['number']}, {m['name']}: {m['start']} to {m['end']} (demonstration {m['demo']})")
    for br in plan["breaks"]:
        print(f"  Break, {br['name']}: {br['start']} to {br['end']}")
    print("\nLoad (sized days of work against allocated capacity, per person and work unit)")
    if not people:
        print("  No people in the plan yet. Add them under `people`, or let the planning step propose a team marked derived.")
    elif not staffed:
        print("  Not shown: allocation, start dates and days off are in the private people file.")
    if staffed:
        print("  Capacity is the working days a person has in the work unit, minus days off, times their percent allocation.")
    head = ["Person", "Alloc"] + [f"WU{m['number']}" for m in plan["milestones"]] + ["Total"]
    rows = []
    over = []
    by_person = {}
    for pid, mnum, sized, cap, pct in (L.load_rows(plan) if staffed else []):
        by_person.setdefault(pid, []).append((mnum, sized, cap, pct))
    for pid, p in (people.items() if staffed else []):
        cells, tot_sized, tot_cap = [], 0.0, 0.0
        for mnum, sized, cap, pct in by_person.get(pid, []):
            if sized == 0:
                cells.append(f"0 of {cap:.0f}d")
            else:
                flag = "  OVER" if (pct is not None and pct > 100) else ""
                cells.append(f"{sized:g} of {cap:.0f}d ({pct:.0f}%){flag}" if pct not in (None, float("inf")) else f"{sized:g} of 0d (no capacity){flag or '  OVER'}")
                if pct is None or pct > 100:
                    over.append((pid, mnum, sized, cap, pct))
            tot_sized += sized
            tot_cap += cap
        tot = f"{tot_sized:g} of {tot_cap:.0f}d" + (f" ({100 * tot_sized / tot_cap:.0f}%)" if tot_cap else "")
        rows.append([pid, f"{p.get('allocation', 100)}%"] + cells + [tot])
    widths = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    if staffed:
        print("  " + "  ".join(h.ljust(w) for h, w in zip(head, widths)))
        for r in rows:
            print("  " + "  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    if not staffed:
        pass
    elif over:
        print("  Over 100 percent of allocated capacity:")
        for pid, mnum, sized, cap, pct in over:
            print(f"    {pid} in work unit {mnum}: {sized:g} sized days against {cap:.1f} allocated days" + (f" ({pct:.0f}%)" if pct not in (None, float("inf")) else ""))
    else:
        print("  No person is over 100 percent of allocated capacity in any work unit.")
    # critical path: longest chain by calendar days between completions
    items = L.item_by_id(plan)
    if items:
        days, path = L.critical_path(plan)
        print("\nCritical path (longest dependency chain to the last item)")
        print("  " + " -> ".join(L.tag(plan, n) for n in path) + f"  ({days} calendar days)")
        for n in path:
            print(f"    {L.tag(plan, n)} {items[n]['label']}, by {items[n]['complete_by']}, {people.get(items[n]['owner'], {}).get('id', items[n]['owner'])}")
        tdate, ttext = L.target_date(plan)
        end_date = L.parse_date(items[path[-1]]["complete_by"])
        print("\nTarget")
        if tdate and L.target_is_constraint(plan):
            gap = (tdate - end_date).days
            verdict = f"meets the target with {gap} day(s) to spare" if gap >= 0 else f"misses the target by {-gap} day(s)"
            print(f"  Target: {ttext}")
            print(f"  The critical path ends {fmt(end_date)}: it {verdict}.")
        else:
            why = "The target in plan.yaml is marked derived" if tdate else "There is no target in plan.yaml"
            print(f"  Critical path ends {fmt(end_date)} (derived from the critical path). {why}, so this is the derived target: the plan's end date, not a constraint.")
            if tdate and tdate != end_date:
                print(f"  The derived target in plan.yaml says {fmt(tdate)}. Update it to {fmt(end_date)}.")
    print("\nFit (working days each item needs, from its size and its owner's allocation, against its window)")
    fits = L.fit_findings(plan) if staffed else []
    if not staffed:
        print("  Not checked: the windows depend on allocation and days off in the private people file.")
    elif not any(L.sized_days(it) for it in plan["items"]):
        print("  No item is sized yet. Write sizes as \"about N days\" to check the windows.")
    elif fits:
        for f in fits:
            print("  " + f)
    else:
        print("  Every sized item fits between its last dependency and its complete_by date.")
    times, chain = L.earliest_finish(plan) if staffed else ({}, [])
    if chain:
        fin = times[chain[-1]][1]
        print("\nEarliest finish (forward pass over the dependencies, from sizes and allocation)")
        print("  " + " -> ".join(L.tag(plan, n) for n in chain) + f"  ends {fmt(fin)}")
        for n in chain:
            st, en = times[n]
            print(f"    {L.tag(plan, n)} {fmt(st)} to {fmt(en)}, about {L.needed_days(plan, items[n]):.1f} working days")
        tdate, _ = L.target_date(plan)
        if tdate and L.target_is_constraint(plan):
            gap = (tdate - fin).days
            print(f"  " + (f"It meets the target {fmt(tdate)} with {gap} day(s) to spare. The planned dates add the slack between items."
                           if gap >= 0 else f"It misses the target {fmt(tdate)} by {-gap} day(s): no order of the dates can meet it with these sizes."))
        print("  Owners are not serialized in this pass. The load table above shows whether each person's work fits each work unit.")
    pitems = plan["external"]["items"]
    if pitems:
        print("\nExternal items (outside the development plan; referenced only as external input)")
        for pi in pitems:
            print(f"  {L.tag(plan, pi['id'])} {pi['label']}")
    print("\nCheckpoints")
    for c in plan["checkpoints"]:
        due = [L.tag(plan, it["id"]) for it in plan["items"] if it["checkpoint"] == c["date"]]
        print(f"  {c['date']}  {c['name']}: {', '.join(due) or 'none closing'}")
    findings, lines = planning_review(plan)
    where = ("references/planning.md" if _ships("references", "planning.md")
             else f"{plan['project']['spec_dir']}/README.md, under How this plan was composed")
    print(f"\nPlanning review (advisory, except lines marked finding; the rules are in {where})")
    for line in lines:
        print(line)
    print(f"  {len(findings)} finding(s)." + (" Run the checker without --report to fail on them." if findings else ""))


PLAN_ERRORS = (KeyError, ValueError, TypeError, AttributeError, IndexError, ZeroDivisionError, OverflowError, RecursionError, OSError)


def print_plan_problems(problems):
    print("plan.yaml has problems:")
    for p in problems:
        print("  - " + p)


def collapse_unfinished(issues):
    """A file that still holds template text gets one line, not one per unfilled row."""
    todo = [i for i in issues if i.startswith("unfinished template text (TODO)")]
    if not todo or len(issues) == 1:
        return issues, bool(todo)
    others = len(issues) - 1
    return [f"{todo[0]}, and {others} other finding(s) that usually go when the template text is replaced"], True


def detector_findings(plan, root, workspace, view):
    """Run the mechanical detectors over the files the project would publish. Returns lines. The
    organization-phrase and copied-passage detectors run only where the private workspace is. The
    staffing-field detector is left out: validate_plan already finds the same keys in the plan."""
    files = D.project_scope(root, plan)
    plan_rel = Path(plan.get("_path") or "").name
    allow = {f for f in files if Path(f).name == plan_rel and view != "released"}
    found = D.run_all(root, workspace, files, [], skip=("prohibited_fields",), allow_source_folder=allow,
                      plan_path=plan.get("_path"))
    return [D.format_finding(f) for f in found]


def run_checks(plan, root, a):
    """Run every check. Returns (results, clean files, files, items, unfinished, notes). notes are lines
    for the text output that are not findings."""
    results = {}
    notes = []
    ok = 0
    unfinished = 0
    load_issues = []
    view = view_of(plan)
    workspace, _ = L.workspace_root(root)   # the owner's private workspace, when this is the owner's machine
    staffed = L.staffing_loaded(plan)   # without the people overlay, capacity and dates are not checked
    for pid, mnum, sized, cap, pct in (L.load_rows(plan) if staffed else []):
        if pct is not None and pct > 100:
            load_issues.append(f"{pid} is over 100 percent of allocated capacity in work unit {mnum}: {sized:g} sized days against {cap:.1f} allocated days")
    tdate, _ = L.target_date(plan)
    if tdate and plan["items"]:
        last = max(L.parse_date(it["complete_by"]) for it in plan["items"])
        if L.target_is_constraint(plan) and last > tdate:
            load_issues.append(f"the last work item completes {L.fmt_date(last)}, after the target {L.fmt_date(tdate)}")
        if not L.target_is_constraint(plan) and last != tdate:
            load_issues.append(f"the derived target {L.fmt_date(tdate)} is out of date. The last work item completes {L.fmt_date(last)}, so write that date under target")
    if staffed:
        load_issues += L.fit_findings(plan)
    times, chain = L.earliest_finish(plan) if staffed else ({}, [])
    if chain and tdate and L.target_is_constraint(plan) and times[chain[-1]][1] > tdate:
        load_issues.append(f"from sizes and allocation the earliest finish is {L.fmt_date(times[chain[-1]][1])}, after the target {L.fmt_date(tdate)} "
                           f"(chain {' -> '.join(L.tag(plan, n) for n in chain)})")
    banned = banned_patterns(plan)
    release = Release(root) if view == "released" else None
    try:
        gt_heads, gt_error = ({}, None) if view == "released" else (ground_truth_headings(plan, root, workspace), None)
    except L.TextError as e:
        gt_heads, gt_error = {}, f"ground truth citations not checked: {e.msg}"
    if load_issues:
        results["load and target"] = load_issues
    review, _ = planning_review(plan) if not a.item else ([], [])
    if review:
        results["planning review"] = review
    cites = [gt_error] if gt_error else citation_findings(plan, root, gt_heads, view, getattr(a, "check_originals", False))
    if cites and not a.item:
        results["ground truth"] = cites
    if release is not None and release.problems and not a.item:
        results["release receipts"] = release.problems
    if view == "workspace" and workspace is not None and not a.item:
        tracked = tracked_source_findings(plan, root)
        notes += [t for t in tracked if t.startswith(NOT_PERFORMED)]
        tracked = [t for t in tracked if not t.startswith(NOT_PERFORMED)]
        if tracked:
            results["restricted sources"] = tracked
    items = [it for it in plan["items"] if not a.item or it["id"] in a.item]
    for it in items:
        issues, rel = check_item(plan, root, it, banned, gt_heads, release)
        issues, todo = collapse_unfinished(issues)
        unfinished += todo
        if issues:
            results[f"{L.tag(plan, it['id'])} {rel}"] = issues
        else:
            ok += 1
    if not a.item:
        for ms in plan["milestones"]:
            issues, rel = check_milestone(plan, root, ms)
            issues, todo = collapse_unfinished(issues)
            unfinished += todo
            if issues:
                results[f"milestone {ms['number']} {rel}"] = issues
            else:
                ok += 1
        issues, rel = check_readme(plan, root)
        if issues:
            results[str(rel)] = issues
        else:
            ok += 1
        orphans = orphan_files(plan, root)
        if orphans:
            results["orphan files"] = [f"{o} is not in plan.yaml" for o in orphans]
        issues, rel = plan_review_findings(plan, root, banned_patterns(plan))
        if issues:
            results[str(rel)] = issues
        found = detector_findings(plan, root, workspace, view)
        if found:
            results["detectors"] = found
        else:
            notes.append(D.CLEAN_LINE)
    n_files = len(items) + (0 if a.item else len(plan["milestones"]) + 1)
    return results, ok, n_files, len(items), unfinished, notes


def parse_items(plan, wanted):
    """Item ids from --item values such as 3, WI-03 or wi-3. Returns (ids, error)."""
    prefix = str(plan["project"].get("id_prefix") or "")
    known = {it["id"] for it in plan["items"] if isinstance(it.get("id"), int)}
    ext = L.external_ids(plan)
    out = []
    for w in wanted:
        n = L.item_number(plan, w)
        if n is None:
            return [], f"--item {w!r} is not an item id. Use the number or the tag, for example 3 or {prefix or 'WI'}-03"
        if n in ext:
            return [], f"--item {w}: {L.tag(plan, n)} is an external item, outside the plan, so it has no specification to check"
        if n not in known:
            return [], f"--item {w}: there is no item {n} in the plan. Items: {', '.join(L.tag(plan, k) for k in sorted(known)) or 'none yet'}"
        out.append(n)
    return out, None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check work item specifications against plan.yaml. Read only: this script never writes files.",
        epilog="Exit status 0 when clean, 1 when there are findings (problems with plan.yaml values included), "
               "2 when the plan cannot be read or an argument is wrong.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--item", action="append", help="check only this item: 3, WI-03 or wi-3 (repeatable)")
    ap.add_argument("--report", action="store_true", help="print the schedule, load table and critical path, then exit")
    ap.add_argument("--json", action="store_true", help="print the findings as JSON")
    ap.add_argument("--quiet", action="store_true", help="print only the summary line")
    ap.add_argument("--view", choices=L.PLAN_VIEWS,
                    help="check the plan in this view: workspace (the owner's working plan, which may hold originals and renderings) or released "
                         "(the exported plan, which holds neither and is checked against its approved context bundles and receipts). "
                         "Default: the plan_view the plan declares, and the original rules for a plan with no plan_format")
    ap.add_argument("--check-originals", action="store_true",
                    help="in the workspace view, also require every original named by source_path to be present. Without it a retained rendering is enough")
    ap.add_argument("--people", help="path to people.yaml: the staffing overlay (names, allocation, start dates, days off) for "
                                     "the capacity, dates and names checks. Default: people.yaml in the private workspace named by "
                                     ".carrydown/local.yaml. Without an overlay those checks are skipped, and the output says so")
    a = ap.parse_args(argv)

    def fail(msg):
        """A usage or plan error: one line on standard error, and with --json one JSON object on
        standard output. Exit status 2."""
        if a.json:
            print(json.dumps({"error": msg, "clean": 0, "files": 0, "findings": {}}, indent=2))
        print(f"error: {msg}", file=sys.stderr)
        return 2

    if a.report and a.json:
        return fail("--report prints text. Leave out --json, or leave out --report to get the findings as JSON")
    why = L.root_problem(a.root)
    if why:
        return fail(why)
    root = Path(a.root).expanduser().resolve()
    try:
        plan_path = L.find_plan(root, a.plan) if a.view == "released" else L.owner_plan(root, a.plan)
    except L.PlanError as e:
        return fail(e.msg)
    if not L.exists(plan_path):
        return fail(f"plan not found at {plan_path}. Run from the project root or pass --root; "
                    f"write a first plan with {_script_hint('scaffold_spec.py', '--init')}")
    why = L.regular_file_problem(plan_path)
    if why:
        return fail(f"the plan path {why}" if why.startswith(str(plan_path)) else why)
    try:
        plan, plan_problems = L.load_plan_with_people(plan_path, root, people_path=a.people, view=a.view)
    except L.PlanError as e:
        return fail(e.msg)
    if a.item:
        a.item, err = parse_items(plan, a.item)
        if err:
            return fail(err)
    if a.report:
        # plan problems first: the report is only as good as the plan it reads
        if plan_problems:
            print_plan_problems(plan_problems)
            print()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                report(plan)
        except PLAN_ERRORS as e:
            if not plan_problems:
                if isinstance(e, OSError):
                    return fail(f"cannot read a file of the project: {e.strerror or e}" + (f" ({e.filename})" if e.filename else ""))
                raise
            print("The report needs the problems above fixed first.")
            return 1
        sys.stdout.write(buf.getvalue())
        return 1 if plan_problems else 0
    try:
        results, ok, n_files, n_items, unfinished, notes = run_checks(plan, root, a)
    except PLAN_ERRORS as e:
        if not plan_problems:
            if isinstance(e, OSError):
                return fail(f"cannot read a file of the project: {e.strerror or e}" + (f" ({e.filename})" if e.filename else ""))
            raise
        if a.json:
            print(json.dumps({"clean": 0, "files": 0, "findings": {"plan.yaml": plan_problems}}, indent=2))
        else:
            print_plan_problems(plan_problems)
            print("The specifications were not checked: fix plan.yaml first.")
        return 1
    if plan_problems:
        results = {"plan.yaml": plan_problems, **results}
    if a.json:
        print(json.dumps({"clean": ok, "files": n_files, "findings": results, "notes": notes}, indent=2))
    else:
        print(f"{ok} files clean, {len(results)} with findings ({n_items} work items, {0 if a.item else len(plan['milestones'])} milestones)")
        if not L.staffing_loaded(plan):
            print(OVERLAY_NOTE)
        if plan_problems:
            print(f"plan.yaml: {len(plan_problems)} problem(s), listed first.")
        if unfinished:
            print(f"{unfinished} file(s) still hold template text (TODO). That is expected until the specifications are written.")
        if L.derived_summary(plan):
            print(f"Derived inputs: {L.derived_summary(plan)}.")
        if not a.quiet:
            for note in notes:
                print(note)
            for k, v in results.items():
                print(f"{k}:")
                for i in v:
                    print("  - " + i)
    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main())
