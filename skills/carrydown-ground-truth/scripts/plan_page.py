#!/usr/bin/env python3
"""Write the plan page: one private HTML file the plan owner opens in a browser to review a draft plan.

The page is organized around the owner's decisions, not the YAML. It has five sections: the project
overview, people and feasibility, milestone details, work item details and review findings. When a saved
update proposal exists, the page leads with what changed and what needs a decision, before the five sections.

Every fact and every calculation on the page comes from the data and the code the checker uses: the plan
loaded by carrydown_lib, the load table, the critical path, the target sentence, the planning review and the
findings of check_specs. The page adds no summary of its own.

The page shows names from the people overlay and source locations, so it is private. It is written only into
the owner's private workspace, at <workspace>/review/plan-page.html, with owner-only permissions. There is no
option to write it anywhere else, and it is never written into the project. Corrections stay in the chat with
the agent: the page has no script, no form and no external resource, and it works offline from a file.

The workspace is found through the pointer .carrydown/local.yaml under --root. On the private path the agent
runs plan commands with --root <workspace>/drafts, where there is no pointer: when --root is a folder named
drafts beside a workspace.yaml, its parent is the workspace, and its people.yaml is the people overlay unless
--people names one.

Usage
  python3 scripts/plan_page.py --root .                write the page and print its path
  python3 scripts/plan_page.py --root . --dry-run      build the page and print where it would go; write nothing
  python3 scripts/plan_page.py --root . --proposal ID  lead with this saved update proposal instead of the newest open one
Exit status is 0 when the page was written, 1 when the plan has problems that stop the page (a page that shows
them is still written), and 2 for a wrong argument, a plan that cannot be read or a missing workspace.
The script calls no model, reads no token and opens no connection.
"""
import argparse
import datetime
import html
import os
import re
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402
import check_specs as CS  # noqa: E402
import reconcile as R  # noqa: E402

PAGE_DIR = "review"
PAGE_NAME = "plan-page.html"
DECISION_KINDS = {
    "pending": "pending: no decision recorded yet",
    "unresolved": "unresolved: information is missing",
    "defer": "deferred",
    "assess-completed": "touches completed work",
    "completed-work": "touches completed work",
    "conflict": "conflict",
}
NOTE = ("This page is written from the plan, the specifications and the checker. To change anything, ask your agent. "
        "Approving the schedule does not approve every specification, so read the work items and their sources.")
SECTIONS = (("overview", "Project overview"), ("people", "People and feasibility"), ("milestones", "Milestone details"),
            ("work-items", "Work item details"), ("review-findings", "Review findings"))

e = html.escape


class Usage(Exception):
    """A usage error: a fixed code and one sentence. Exit status 2."""

    def __init__(self, code, text):
        super().__init__(text)
        self.code = code
        self.text = text


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def inline(text):
    """Escaped text with `code` spans as <code>."""
    out = []
    for part in re.split(r"(`[^`\n]+`)", str(text)):
        if len(part) > 1 and part.startswith("`") and part.endswith("`"):
            out.append(f"<code>{e(part[1:-1])}</code>")
        else:
            out.append(e(part))
    return "".join(out)


LIST_LINE = re.compile(r"^( {0,3})([-*+]|\d+[.)])\s+(.*)$")
CHECK_LINE = re.compile(r"^\[( |x|X)\]\s+(.*)$")
FENCE_LINE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def markdown(text):
    """The Markdown subset the specifications use: paragraphs, bullet and numbered lists, task list items and
    inline code. Fenced blocks stay as escaped preformatted text, and everything else as escaped text."""
    out, para, fence = [], [], None
    lst = None   # [tag, [[text, state]]]

    def flush_para():
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    def flush_list():
        nonlocal lst
        if lst:
            checks = any(state is not None for _, state in lst[1])
            out.append(f"<{lst[0]}" + (' class="checks"' if checks else "") + ">")
            for body, state in lst[1]:
                mark = badge("Done") + " " if state else ""
                out.append(f"<li>{mark}{inline(body)}</li>")
            out.append(f"</{lst[0]}>")
        lst = None

    for line in str(text).split("\n"):
        if fence is not None:
            if FENCE_LINE.match(line):
                out.append(f"<pre>{e(chr(10).join(fence))}</pre>")
                fence = None
            else:
                fence.append(line)
            continue
        if FENCE_LINE.match(line):
            flush_para()
            flush_list()
            fence = []
            continue
        if not line.strip():
            flush_para()
            flush_list()
            continue
        m = LIST_LINE.match(line)
        if m:
            flush_para()
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            if lst and lst[0] != tag:
                flush_list()
            if lst is None:
                lst = [tag, []]
            body, state = m.group(3), None
            c = CHECK_LINE.match(body)
            if c:
                body, state = c.group(2), c.group(1).lower() == "x"
            lst[1].append([body, state])
        elif lst and line[:1] in (" ", "\t"):
            lst[1][-1][0] += " " + line.strip()
        else:
            flush_list()
            para.append(line.strip())
    if fence is not None:
        out.append(f"<pre>{e(chr(10).join(fence))}</pre>")
    flush_para()
    flush_list()
    return "\n".join(out)


ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z)?\b")


def timed(markup):
    """Markup with each ISO date outside a tag wrapped in <time>, so a date never breaks across lines."""
    parts = re.split(r"(<[^>]+>)", markup)
    return "".join(p if p.startswith("<") else ISO_DATE.sub(lambda m: f'<time datetime="{m.group(0)}">{m.group(0)}</time>', p) for p in parts)


def md_section(text, title):
    """The text under a level 2 heading of a Markdown file, or None."""
    m = re.search(r"(?m)^## " + re.escape(title) + r"[ \t]*$", text)
    if not m:
        return None
    rest = text[m.end():]
    n = re.search(r"(?m)^## ", rest)
    return rest[:n.start()] if n else rest


def quote(text):
    """Percent-encode a link fragment, keeping ASCII letters, digits and -_.~ as they are."""
    return "".join(c if c.isascii() and (c.isalnum() or c in "-_.~") else "".join(f"%{b:02X}" for b in c.encode("utf-8")) for c in text)


def file_uri(path, anchor=None):
    uri = Path(path).resolve().as_uri()
    return uri + ("#" + quote(anchor) if anchor else "")


def link(path, text, anchor=None):
    """A link to a local file when it exists, else the text alone."""
    if path is not None and L.exists(Path(path)):
        return f'<a href="{e(file_uri(path, anchor))}">{text}</a>'
    return text


def shown_path(path, root):
    p = Path(path)
    try:
        return str(p.resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(p.resolve())


def badge(text):
    return f'<strong class="badge">{e(text)}</strong>'


class Tables:
    """Accessible tables: a caption with an id, a keyboard reachable scroll region and header cells."""

    def __init__(self):
        self.n = 0

    def __call__(self, caption, head, rows, row_header=True):
        self.n += 1
        cid = f"table-{self.n}"
        out = [f'<div class="table-wrap" role="region" tabindex="0" aria-labelledby="{cid}">', "<table>",
               f'<caption id="{cid}">{e(caption)}</caption>', "<thead><tr>"]
        out += [f'<th scope="col">{e(h)}</th>' for h in head]
        out.append("</tr></thead><tbody>")
        for r in rows:
            cells = []
            for i, c in enumerate(r):
                cells.append(f'<th scope="row">{timed(c)}</th>' if i == 0 and row_header else f"<td>{timed(c)}</td>")
            out.append("<tr>" + "".join(cells) + "</tr>")
        out.append("</tbody></table></div>")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Workspace, plan and proposal
# ---------------------------------------------------------------------------

def find_workspace(root):
    """(workspace, drafts root). The pointer under root first; on the private path a drafts folder beside a
    workspace.yaml is inside the workspace, so its parent is the workspace."""
    ws, why = L.workspace_root(root)
    if ws is not None:
        return Path(ws), False
    if root.name == "drafts" and (root.parent / "workspace.yaml").is_file():
        return Path(os.path.realpath(str(root.parent))), True
    if why == "workspace-inside-repository":
        raise Usage(why, "the private workspace named by .carrydown/local.yaml is inside the repository, so the page is not "
                         "written there. Move the workspace outside the repository with workspace.py, then run this again.")
    raise Usage("workspace-unavailable", "no private workspace was found for this project, and the page is written only "
                                         "there. Run workspace.py init first, then run this again.")


def plan_view_text(plan, ws):
    if CS.view_of(plan) == "released":
        return "released"
    try:
        Path(plan["_path"]).resolve().relative_to(Path(ws).resolve())
        return "draft in the private workspace"
    except (ValueError, KeyError, TypeError):
        return "draft in the project"


def find_proposal(ws, wanted):
    """The saved update proposal to lead with, or None. wanted names one by id; else the newest open one,
    in the order the update path uses."""
    found = R.list_proposals(types.SimpleNamespace(ws=Path(ws)))
    if wanted is not None:
        hit = [p for p in found if p["id"] == wanted.strip().lower()]
        if not hit:
            raise Usage("proposal-not-found", "no saved update proposal has that id. Leave out --proposal to use the newest open one.")
        return hit[0]
    live = [p for p in found if p["state"] not in ("applied", "nothing-to-apply")]
    return sorted(live, key=R.proposal_order)[-1] if live else None


def read_proposal(proposal):
    """(blocks, consumers, dispositions by block, created) of a saved proposal, or None when it cannot be read."""
    folder = proposal["folder"]
    try:
        blocks = R.read_json_file(folder / "blocks.json")["blocks"]
        consumers = R.read_json_file(folder / "consumers.json")["consumers"]
        dispositions = R.read_json_file(folder / "dispositions.json")["dispositions"]
    except (ValueError, TypeError, KeyError):
        return None
    if not all(isinstance(x, list) for x in (blocks, consumers, dispositions)):
        return None
    by_block = {}
    for d in dispositions:
        if isinstance(d, dict) and isinstance(d.get("block"), str):
            by_block.setdefault(d["block"], []).append(d)
    return [b for b in blocks if isinstance(b, dict)], [c for c in consumers if isinstance(c, dict)], by_block, proposal.get("created") or ""


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

CSS = """
:root{--paper:#ffffff;--cream:#f6f3ec;--ink:#1f2a44;--muted:#5b6472;--line:#e4dfd2;--teal:#205757;--amber:#8f5a08;--amber-bg:#fbebd0}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;font-size:1rem;line-height:1.6;overflow-wrap:break-word}
a{color:var(--teal);text-decoration-thickness:1px;text-underline-offset:.15em}
a:hover{text-decoration-thickness:2px}
a:focus-visible,.table-wrap:focus-visible{outline:3px solid var(--teal);outline-offset:2px;border-radius:2px}
.skip{position:absolute;left:1rem;top:-10rem;background:var(--ink);color:#ffffff;padding:.5rem 1rem;z-index:2}
.skip:focus{top:1rem;color:#ffffff}
.wrap{max-width:60rem;margin:0 auto;padding:0 1rem}
header.top{background:var(--cream);border-bottom:1px solid var(--line);padding:2.5rem 0 2rem}
.kicker{margin:0;color:var(--muted);font-size:.8125rem;letter-spacing:.08em;text-transform:uppercase;font-weight:600}
h1{font-size:2.25rem;line-height:1.2;margin:.25rem 0 1.25rem;font-weight:650;letter-spacing:-.01em}
h2{font-size:1.5rem;line-height:1.3;margin:3.5rem 0 1rem;padding-top:1.25rem;border-top:1px solid var(--line)}
h3{font-size:1.1875rem;line-height:1.35;margin:2.25rem 0 .75rem}
h4{font-size:1rem;margin:1.5rem 0 .5rem}
p,li,dd{max-width:72ch}
.meta{display:grid;grid-template-columns:minmax(8rem,max-content) 1fr;gap:.35rem 1.25rem;margin:0}
.meta dt{color:var(--muted);font-weight:600}
.meta dd{margin:0;overflow-wrap:anywhere}
.facts{display:grid;grid-template-columns:minmax(8rem,max-content) 1fr;gap:.3rem 1.25rem;margin:0 0 1rem}
.facts dt{color:var(--muted);font-weight:600}
.facts dd{margin:0}
.note{margin:1.75rem 0 0;padding:1rem 1.25rem;background:var(--paper);border:1px solid var(--line);border-left:4px solid var(--amber);border-radius:4px}
.note p{margin:0}
nav.toc{margin:1.5rem 0 0}
.toc-label{margin:0 0 .25rem;font-weight:600;color:var(--muted);font-size:.875rem}
nav.toc ol{margin:0;padding-left:1.5rem}
main{padding-bottom:3rem}
.table-wrap{overflow-x:auto;margin:1rem 0 1.5rem;border:1px solid var(--line);border-radius:4px}
table{border-collapse:collapse;width:100%;font-size:.9375rem}
caption{text-align:left;font-weight:600;padding:.75rem .75rem .5rem;background:var(--cream);border-bottom:1px solid var(--line)}
th,td{text-align:left;vertical-align:top;padding:.5rem .75rem;border-bottom:1px solid var(--line)}
thead th{color:var(--muted);font-size:.8125rem;font-weight:600}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
tbody th{font-weight:600}
.badge{display:inline-block;background:var(--amber-bg);color:var(--amber);font-weight:650;font-size:.8125rem;padding:0 .4em;border-radius:3px;letter-spacing:.02em}
time,a[href^="#item-"]{white-space:nowrap}
td .tags,th .tags{white-space:nowrap}
ul.checks li{margin:.25rem 0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.875em;background:var(--cream);padding:.05em .3em;border-radius:3px;overflow-wrap:anywhere}
pre{background:var(--cream);padding:.75rem;overflow-x:auto;font-size:.875rem;white-space:pre-wrap}
.muted{color:var(--muted)}
.item{border-top:1px solid var(--line)}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.875rem;padding:1.5rem 0 3rem}
@media (max-width:40rem){h1{font-size:1.75rem}.meta,.facts{grid-template-columns:1fr}.meta dd,.facts dd{margin-bottom:.5rem}}
@media print{.skip,nav.toc{display:none}header.top{background:none}.table-wrap{overflow:visible;border:0}a{color:var(--ink)}h2,h3{break-after:avoid}}
"""


class Page:
    def __init__(self, plan, root, ws, a, written):
        self.plan, self.root, self.ws, self.a, self.written = plan, root, ws, a, written
        self.table = Tables()
        self.staffed = L.staffing_loaded(plan)
        self.people = {p["id"]: p for p in plan["people"]}
        self.items = L.item_by_id(plan)

    # -- names and links

    def who(self, pid):
        if not pid:
            return "no owner"
        name = self.people.get(pid, {}).get("name") if self.staffed else None
        return f"{e(str(pid))} ({e(str(name))})" if name else e(str(pid))

    def item_ref(self, n):
        it = self.items.get(n)
        tag = L.tag(self.plan, n)
        if it is None:
            return e(tag)
        return f'<a href="#item-{tag.lower()}">{e(tag)}</a>'

    def item_refs(self, ids):
        return '<span class="tags">' + ", ".join(self.item_ref(n) for n in ids) + "</span>" if ids else "None"

    def source_refs(self, it):
        """One line per cited section, linked to the heading of the rendering when the rendering exists."""
        sources = L.source_by_id(self.plan)
        lines = []
        for ref in L.item_source_refs(self.plan, it):
            source = sources.get(ref.get("source"))
            name = (source or {}).get("name") or ref.get("source") or "Source"
            path = CS.rendering_file(source, self.root, self.ws) if source else None
            numbers = CS.citation_numbers(str(ref.get("sections") or ""))
            if path is None or not L.exists(path):
                lines.append(f"{e(name)}: Sections {e(str(ref.get('sections') or ''))} <span class=\"muted\">(rendering not available)</span>")
                continue
            try:
                text = L.read_text(path)
            except L.TextError:
                lines.append(f"{e(name)}: Sections {e(str(ref.get('sections') or ''))} <span class=\"muted\">(rendering not readable)</span>")
                continue
            heads = L.collect_headings(text.split("\n"))
            anchors = L.anchors_for(heads)
            for num in numbers or [""]:
                hit = None
                for (_, _, head), anchor in zip(heads, anchors):
                    plain = re.sub(r"[`*_]", "", head)
                    if num and (plain.startswith(num + " ") or plain.startswith(num + ". ")):
                        hit = (plain, anchor)
                        break
                if hit:
                    lines.append(f"{e(name)}, section {link(path, e(hit[0]), hit[1])}")
                elif num:
                    lines.append(f"{e(name)}, section {e(num)} <span class=\"muted\">(not found in the rendering)</span>")
                else:
                    lines.append(link(path, e(name)))
        return lines

    # -- sections

    def header(self, checks, plan_rel, proposal_shown):
        plan = self.plan
        results, ok, n_items = checks["results"], checks["ok"], checks["n_items"]
        out = ['<header class="top"><div class="wrap">', '<p class="kicker">Plan page</p>',
               f"<h1>{e(str(plan['project']['name']))}</h1>", '<dl class="meta">',
               f"<dt>Written</dt><dd>{e(self.written)}</dd>",
               f"<dt>Plan file</dt><dd><code>{e(plan_rel)}</code></dd>",
               f"<dt>Plan view</dt><dd>{e(plan_view_text(plan, self.ws))}</dd>",
               "<dt>People overlay</dt><dd>" + ("loaded" if self.staffed else e(CS.OVERLAY_NOTE)) + "</dd>"]
        if checks["computed"]:
            out.append(f"<dt>Checker</dt><dd>{e(CS.summary_line(plan, results, ok, n_items))}</dd>")
            target = CS.target_lines(plan)
            if target:
                shown = [target[0][len("Target: "):] if target[0].startswith("Target: ") else target[0]] + target[1:]
                out.append("<dt>Target</dt><dd>" + "<br>".join(e(t) for t in shown) + "</dd>")
        else:
            out.append(f"<dt>Checker</dt><dd>plan.yaml: {len(checks['problems'])} problem(s). The rest could not be computed.</dd>")
        out.append("</dl>")
        out.append(f'<div class="note"><p>{e(NOTE)}</p></div>')
        out.append('<nav class="toc" aria-label="Sections"><p class="toc-label">On this page</p><ol>')
        if proposal_shown:
            out.append('<li><a href="#what-changed">What changed</a></li>')
        for sid, title in (SECTIONS if checks["computed"] else SECTIONS[-1:]):
            out.append(f'<li><a href="#{sid}">{e(title)}</a></li>')
        out.append("</ol></nav></div></header>")
        return "\n".join(out)

    def what_changed(self, proposal):
        out = ['<section aria-labelledby="what-changed"><h2 id="what-changed">What changed</h2>']
        data = read_proposal(proposal) if proposal["state"] != "unreadable" else None
        if data is None:
            out.append("<p>A saved update proposal exists, but it cannot be read. Ask your agent to compare the sources again.</p></section>")
            return "\n".join(out)
        blocks, consumers, by_block, created = data
        sources = sorted({b.get("source") for b in blocks if b.get("source")})
        direct = R.distinct_consumers(consumers)
        state = {"applied": "applied", "nothing-to-apply": "nothing to apply"}.get(proposal["state"], "open")
        out.append(f"<p>{len(blocks)} changed block(s) in {len(sources)} source(s); {len(direct)} direct consumer(s). "
                   f"The update was prepared {timed(e(created)) if created else 'at an unknown time'} and is {state}. The complete revised plan follows this section.</p>")

        def heads(b):
            parts = []
            if b.get("previous_heading"):
                parts.append(f"was {b.get('previous_number') or ''} {b['previous_heading']}".replace("  ", " "))
            if b.get("current_heading"):
                parts.append(f"now {b.get('current_number') or ''} {b['current_heading']}".replace("  ", " "))
            return "; ".join(parts) or (b.get("reason") or "no heading")

        def disposition(ref):
            recs = by_block.get(ref) or []
            if not recs:
                return "none recorded"
            words = []
            for d in recs:
                kind = str(d.get("disposition") or "none recorded")
                words.append(kind + (" (automatic)" if d.get("automatic") else "") + (", conflict recorded" if d.get("conflict_resolution") else ""))
            return "; ".join(words)

        rows = []
        for b in blocks:
            disp = disposition(b.get("ref"))
            shown = badge(disp) if any(k in disp for k in ("pending", "unresolved", "defer", "assess-completed", "conflict")) else e(disp)
            rows.append([e(str(b.get("ref"))), e(str(b.get("kind"))), e(heads(b)), "yes" if b.get("formatting_only") else "no", shown])
        if rows:
            out.append(self.table("Changed blocks", ["Block", "Kind", "Headings", "Formatting only", "Disposition"], rows))
        crow = []
        for r in consumers:
            for c in r.get("consumers") or []:
                n = c.get("item")
                label = self.items.get(n, {}).get("label", "")
                crow.append([e(str(r.get("block"))), self.item_ref(n) + (f" {e(label)}" if label else ""), e(str(c.get("relationship"))),
                             e(str(c.get("cited"))) if c.get("cited") else "no"])
        if crow:
            out.append(self.table("Direct consumers: the work items that use a changed block", ["Block", "Work item", "Relationship", "Cited"], crow))
        else:
            out.append("<p>No work item cites a changed block.</p>")
        out.append("<h3>Decisions needed</h3>")
        need = []
        for b in blocks:
            ref = b.get("ref")
            for d in by_block.get(ref) or [{"disposition": "pending"}]:
                kind = str(d.get("disposition"))
                why = DECISION_KINDS.get(kind)
                if d.get("conflict_resolution"):
                    why = (why + ", " if why else "") + "rewrites a decision an engineer recorded (resolution recorded)"
                if why:
                    head = b.get("current_heading") or b.get("previous_heading") or ""
                    num = b.get("current_number") or b.get("previous_number") or ""
                    need.append(f"<li>{e(str(ref))}" + (f", {e((num + ' ' + head).strip())}" if head else "") + f": {badge(why)}</li>")
        out.append("<ul>" + "".join(need) + "</ul>" if need else "<p>No changed block waits for a decision.</p>")
        out.append("</section>")
        return "\n".join(out)

    def overview(self, checks):
        plan = self.plan
        out = ['<section aria-labelledby="overview"><h2 id="overview">Project overview</h2>']
        rows = [[str(i), e(str(s.get("name") or s.get("id"))), e(str(s.get("version") or "not given")), e(str(s.get("status") or "reviewed"))]
                for i, s in enumerate(L.ground_truth_sources(plan), 1)]
        out.append(self.table("Sources, highest precedence first", ["Precedence", "Source", "Version", "Status"], rows))
        out.append("<h3>Target</h3>")
        out.append("<p>" + ("<br>".join(e(t) for t in CS.target_lines(plan)) or "No work item yet, so there is no critical path.") + "</p>")
        rows = [[e(str(m["number"])), e(str(m["name"])), e(str(m["start"])), e(str(m["end"])), e(str(m["demo"])), e(str(m.get("gate") or ""))]
                for m in plan["milestones"]]
        out.append(self.table("Milestones", ["Number", "Name", "Start", "End", "Demonstration", "Gate"], rows))
        out.append("<h3>Breaks and external items</h3>")
        out.append("<ul>" + "".join(f"<li>Break, {e(str(b['name']))}: {e(str(b['start']))} to {e(str(b['end']))}</li>" for b in plan["breaks"]) + "</ul>"
                   if plan["breaks"] else "<p>No breaks.</p>")
        ext = plan["external"]["items"]
        out.append("<p>External items, outside the development plan and referenced only as external input:</p><ul>"
                   + "".join(f"<li>{e(L.tag(plan, x['id']))} {e(str(x.get('label') or ''))}</li>" for x in ext) + "</ul>"
                   if ext else "<p>No external items.</p>")
        ds = L.derived_summary(plan)
        out.append("<h3>Derived inputs</h3>")
        out.append(f"<p>Derived inputs: {e(ds)}. Replace the placeholders when you know the real values.</p>" if ds else "<p>No input is derived.</p>")
        out.append("<h3>Decisions that need you</h3><ul>")
        if ds:
            out.append(f"<li>Derived inputs: {e(ds)}. Replace the placeholders when you know the real values.</li>")
        for it in plan["items"]:
            if it.get("external_input"):
                out.append(f"<li>{self.item_ref(it['id'])} waits for external input: {e(str(it['external_input']))}</li>")
        n = sum(len(v) for v in checks["results"].values())
        said = f'reports {n} finding(s) in {len(checks["results"])} file(s) or group(s)' if n else "reports no findings"
        out.append(f'<li>The checker {said}. See <a href="#review-findings">Review findings</a>.</li>')
        review = Path(self.root) / plan["project"]["spec_dir"] / "plan-review.md"
        if L.exists(review):
            out.append(f"<li>A second-pass review report exists: {link(review, e(shown_path(review, self.root)))}.</li>")
        out.append("</ul></section>")
        return "\n".join(out)

    def people_section(self):
        plan = self.plan
        out = ['<section aria-labelledby="people"><h2 id="people">People and feasibility</h2>', "<h3>Assignments</h3>"]
        if not self.staffed:
            out.append(f"<p>{e(CS.OVERLAY_NOTE)}. Not shown: names, allocation, start dates and days off are in the private people file.</p>")
        head = ["Person"] + (["Name"] if self.staffed else []) + ["Track"] + (["Allocation", "Start", "Days off"] if self.staffed else []) + ["Items owned"]
        rows = []
        for p in plan["people"]:
            owned = [it["id"] for it in plan["items"] if it.get("owner") == p["id"]]
            row = [e(str(p["id"]))]
            if self.staffed:
                row.append(e(str(p.get("name") or "not given")))
            row.append(e(str(L.track_label(plan, p.get("track")))) + (" (placeholder)" if p.get("derived") else ""))
            if self.staffed:
                row += [e(f"{p.get('allocation', 100)}%"), e(str(p.get("start") or "not given")), str(len(p.get("days_off") or []))]
            row.append(self.item_refs(owned))
            rows.append(row)
        out.append(self.table("People, their tracks and the items they own", head, rows) if rows else
                   "<p>No people in the plan yet. Add them under <code>people</code>, or let the planning step propose a team marked derived.</p>")

        out.append("<h3>Load</h3>")
        if not self.staffed:
            out.append("<p>Not shown: allocation, start dates and days off are in the private people file.</p>")
        else:
            lhead, lrows, sentences, over = CS.load_table(plan)
            out.append("<p>Capacity is the working days a person has in the work unit, minus days off, times their percent allocation.</p>")
            cells = []
            for r in lrows:
                row = []
                for c in r:
                    text = " ".join(str(c).split())
                    row.append(e(text[:-len(" OVER")]) + " " + badge("OVER") if text.endswith(" OVER") else e(text))
                cells.append(row)
            if cells:
                out.append(self.table("Load: sized days of work against allocated capacity, per person and work unit", lhead, cells))
                out.append("<p>The same values in words:</p><ul>" + "".join(f"<li>{e(s)}</li>" for s in sentences) + "</ul>")
            if over:
                out.append("<p>Over 100 percent of allocated capacity:</p><ul>")
                for pid, mnum, sized, cap, pct in over:
                    out.append(f"<li>{badge('OVER')} {e(str(pid))} in work unit {mnum}: {sized:g} sized days against {cap:.1f} allocated days"
                               + (f" ({pct:.0f}%)" if pct not in (None, float("inf")) else "") + "</li>")
                out.append("</ul>")
            else:
                out.append("<p>No person is over 100 percent of allocated capacity in any work unit.</p>")

        out.append("<h3>Fit of each item in its window</h3>")
        fits = L.fit_findings(plan) if self.staffed else []
        if not self.staffed:
            out.append("<p>Not checked: the windows depend on allocation and days off in the private people file.</p>")
        elif not any(L.sized_days(it) for it in plan["items"]):
            out.append("<p>No item is sized yet. Write sizes as \"about N days\" to check the windows.</p>")
        elif fits:
            out.append("<ul>" + "".join(f"<li>{badge('Finding')} {e(f)}</li>" for f in fits) + "</ul>")
        else:
            out.append("<p>Every sized item fits between its last dependency and its complete_by date.</p>")

        times, chain = L.earliest_finish(plan) if self.staffed else ({}, [])
        if chain:
            out.append("<h3>Earliest finish</h3>")
            out.append(f"<p>Forward pass over the dependencies, from sizes and allocation: {' to '.join(self.item_ref(n) for n in chain)}, "
                       f"ends {e(L.fmt_date(times[chain[-1]][1]))}. Owners are not serialized in this pass.</p>")
            rows = [[self.item_ref(n), e(L.fmt_date(times[n][0])), e(L.fmt_date(times[n][1])), e(f"about {L.needed_days(plan, self.items[n]):.1f}")]
                    for n in chain]
            out.append(self.table("Earliest finish chain", ["Item", "Earliest start", "Earliest finish", "Working days"], rows))

        if self.items:
            days, path = L.critical_path(plan)
            out.append("<h3>Critical path</h3>")
            out.append(f"<p>The longest dependency chain to the last item: {' to '.join(self.item_ref(n) for n in path)}, {days} calendar days.</p>")
            rows = [[self.item_ref(n), e(str(self.items[n]["label"])), e(str(self.items[n]["complete_by"])), self.who(self.items[n].get("owner"))] for n in path]
            out.append(self.table("Critical path items and owners", ["Item", "Label", "Complete by", "Owner"], rows))

        out.append("<h3>Dependencies that threaten delivery</h3><ul>")
        threats = 0
        for it in plan["items"]:
            if L.slack_days(plan, it) == 0:
                threats += 1
                out.append(f"<li>{self.item_ref(it['id'])} has no working day of slack before its checkpoint {e(str(it['checkpoint']))}.</li>")
        for f in fits:
            threats += 1
            out.append(f"<li>{e(f)}</li>")
        for it in plan["items"]:
            if it.get("external_input"):
                threats += 1
                out.append(f"<li>{self.item_ref(it['id'])} waits for external input: {e(str(it['external_input']))}</li>")
        if not threats:
            out.append("<li>No item has zero slack, a window that is too short or a wait for external input.</li>")
        for line in self.review_group("Critical path owners"):
            out.append(f"<li>{e(line)}</li>")
        out.append("</ul></section>")
        return "\n".join(out)

    def review_group(self, lead):
        """The lines of one block of the checker's planning review, without the indentation."""
        _, lines = CS.planning_review(self.plan)
        found, inside = [], False
        for line in lines:
            if line.startswith("  ") and not line.startswith("    "):
                inside = line.strip().startswith(lead)
                continue
            if inside:
                found.append(line.strip())
        return found

    def milestones(self):
        plan = self.plan
        out = ['<section aria-labelledby="milestones"><h2 id="milestones">Milestone details</h2>']
        for ms in plan["milestones"]:
            out.append(f'<h3 id="milestone-{e(str(ms["number"]))}">Milestone {e(str(ms["number"]))}, {e(str(ms["name"]))}</h3><dl class="facts">')
            out.append(f"<dt>Dates</dt><dd>{e(str(ms['start']))} to {e(str(ms['end']))}</dd>")
            out.append(f"<dt>Demonstration</dt><dd>{e(str(ms['demo']))}</dd>")
            out.append(f"<dt>Exit gate</dt><dd>{e(str(ms.get('gate') or 'not given'))}</dd>")
            out.append(f"<dt>Why these items</dt><dd>{e(str(ms.get('rationale') or 'not given'))}</dd>")
            out.append(f"<dt>What stakeholders see</dt><dd>{e(str(ms.get('joint_demonstration') or 'not given'))}</dd>")
            if ms.get("single_track_reason"):
                out.append(f"<dt>One track, because</dt><dd>{e(str(ms['single_track_reason']))}</dd>")
            covered = L.milestone_tracks(plan, ms)
            out.append("<dt>Tracks</dt><dd>" + ("; ".join(f"{e(str(L.track_label(plan, t)))} ({self.item_refs([it['id'] for it in its])})"
                                                             for t, its in covered) or "no items yet") + "</dd>")
            cp = L.demo_checkpoint(plan, ms)
            out.append("<dt>Joint check</dt><dd>" + (f"{e(str(cp.get('date')))}, {e(str(cp.get('name') or ''))}: {e(str(cp.get('joint_check') or ''))}"
                                                    if cp else f"No checkpoint on the demonstration date {e(str(ms['demo']))}.") + "</dd>")
            mpath = L.milestone_path(plan, self.root, ms)
            out.append("<dt>Milestone file</dt><dd>" + (link(mpath, f"<code>{e(shown_path(mpath, self.root))}</code>") if L.exists(mpath)
                                                        else f"missing: <code>{e(shown_path(mpath, self.root))}</code>") + "</dd></dl>")
            its = [it for it in plan["items"] if it.get("milestone") == ms["number"]]
            if its:
                rows = [[self.item_ref(it["id"]), e(str(it["label"])), self.who(it.get("owner")), e(str(it["complete_by"])),
                         e(str(it.get("size") or "To be sized")), self.item_refs(it["depends"])] for it in its]
                out.append(self.table(f"Milestone {ms['number']} work items", ["Item", "Label", "Owner", "Complete by", "Size", "Depends on"], rows))
        out.append("</section>")
        return "\n".join(out)

    def work_items(self):
        plan = self.plan
        out = ['<section aria-labelledby="work-items"><h2 id="work-items">Work item details</h2>']
        mss = L.milestone_by_num(plan)
        for it in plan["items"]:
            tag = L.tag(plan, it["id"])
            ms = mss.get(it["milestone"], {})
            cp = L.checkpoint_of(plan, it)
            out.append(f'<div class="item"><h3 id="item-{e(tag.lower())}">{e(tag)} {e(str(it["label"]))}</h3><dl class="facts">')
            facts = [("Milestone", f'<a href="#milestone-{e(str(it["milestone"]))}">Milestone {e(str(it["milestone"]))}, {e(str(ms.get("name", "")))}</a>'),
                     ("Track", e(str(L.track_label(plan, it.get("track"))))),
                     ("Owner", self.who(it.get("owner"))),
                     ("Complete by", e(str(it["complete_by"]))),
                     ("Checkpoint", e(str(it.get("checkpoint"))) + (f", {e(str(cp.get('name') or ''))}" if cp else "")),
                     ("Size", e(str(it.get("size") or "To be sized"))),
                     ("Depends on", self.item_refs(it["depends"])),
                     ("Unblocks", self.item_refs(it["unblocks"]))]
            if it.get("external_input"):
                facts.append(("External input", e(str(it["external_input"]))))
            if it.get("theme"):
                facts.append(("Theme", e(str(it["theme"]))))
            out += [f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts]
            out.append("</dl>")
            refs = self.source_refs(it)
            out.append("<h4>Sources</h4>" + ("<ul>" + "".join(f"<li>{r}</li>" for r in refs) + "</ul>" if refs else "<p>No source is cited yet.</p>"))
            path = L.spec_path(plan, self.root, it)
            spec = None
            if L.exists(path):
                try:
                    spec = L.read_spec(path)
                except L.TextError:
                    spec = None
            if spec is None:
                out.append(f"<p>The specification file is missing or cannot be read: <code>{e(shown_path(path, self.root))}</code>.</p></div>")
                continue
            for title in ("Why this work item exists", "Acceptance criteria", "Watch out for", "Decisions recorded"):
                body = L.section_text(spec, title).strip()
                if title == "Decisions recorded" and (not body or body == "None yet."):
                    continue
                out.append(f"<h4>{e(title)}</h4>" + (markdown(body) if body else "<p>Not written yet.</p>"))
            out.append(f"<p>Specification file: {link(path, '<code>' + e(shown_path(path, self.root)) + '</code>')}</p></div>")
        out.append("</section>")
        return "\n".join(out)

    def findings(self, checks):
        plan = self.plan
        out = ['<section aria-labelledby="review-findings"><h2 id="review-findings">Review findings</h2>', "<h3>Checker findings</h3>"]
        results = checks["results"]
        if checks["computed"]:
            out.append(f"<p>{e(CS.summary_line(plan, results, checks['ok'], checks['n_items']))}</p>")
        if results:
            out.append("<ul>")
            for k, v in results.items():
                out.append(f"<li><strong>{e(str(k))}</strong><ul>" + "".join(f"<li>{badge('Finding')} {e(str(i))}</li>" for i in v) + "</ul></li>")
            out.append("</ul>")
        else:
            out.append("<p>No findings.</p>")
        if checks["notes"]:
            out.append("<p>Notes from the checker:</p><ul>" + "".join(f"<li>{e(n)}</li>" for n in checks["notes"]) + "</ul>")
        if not checks["computed"]:
            out.append("<p>The rest of the page could not be computed. Fix the plan problems above first, then write the page again.</p></section>")
            return "\n".join(out)

        out.append("<h3>Planning review</h3>")
        findings, lines = CS.planning_review(plan)
        groups = []
        for line in lines:
            depth = len(line) - len(line.lstrip(" "))
            text = line.strip()
            if depth <= 2 or not groups:
                groups.append([text, []])
            elif depth <= 4 or not groups[-1][1]:
                groups[-1][1].append([text, []])
            else:
                groups[-1][1][-1][1].append(text)

        def shown(t):
            return f"{badge('Finding')} {e(t[len('finding: '):])}" if t.startswith("finding: ") else e(t)
        for title, entries in groups:
            out.append(f"<h4>{e(title)}</h4><ul>")
            for text, subs in entries:
                out.append(f"<li>{shown(text)}" + ("<ul>" + "".join(f"<li>{shown(s)}</li>" for s in subs) + "</ul>" if subs else "") + "</li>")
            out.append("</ul>")
        out.append(f"<p>{len(findings)} planning review finding(s).</p>" if findings else "<p>No planning review finding.</p>")

        out.append("<h3>Second-pass review</h3>")
        review = Path(self.root) / plan["project"]["spec_dir"] / "plan-review.md"
        text = None
        if L.exists(review):
            try:
                text = L.read_text(review)
            except L.TextError:
                text = None
        if text is None:
            out.append("<p>No second-pass review report exists yet.</p>")
        else:
            out.append(f"<p>Report: {link(review, '<code>' + e(shown_path(review, self.root)) + '</code>')}</p>")
            for title in ("Findings and risk", "Decisions, repairs and verification"):
                body = md_section(text, title)
                rows = L.table_rows(body) if body else []
                cells = [[r[0]] + [c.strip() for c in r[1].split(" | ")] for r in rows]
                if len(cells) > 1:
                    width = len(cells[0])
                    out.append(self.table(title, cells[0], [[inline(c) for c in (r + [""] * width)[:width]] for r in cells[1:]]))
                else:
                    out.append(f"<p>{e(title)}: no rows yet.</p>")

        out.append("<h3>Assumptions to confirm</h3>")
        flagged = []
        for it in plan["items"]:
            path = L.spec_path(plan, self.root, it)
            try:
                if L.exists(path) and "verify at implementation" in L.read_text(path).lower():
                    flagged.append(it)
            except L.TextError:
                pass
        if flagged:
            out.append("<p>These specifications say to verify a fact at implementation:</p><ul>"
                       + "".join(f"<li>{self.item_ref(it['id'])} {e(str(it['label']))}</li>" for it in flagged) + "</ul>")
        else:
            out.append("<p>No specification asks to verify a fact at implementation.</p>")
        out.append("</section>")
        return "\n".join(out)

    def render(self, checks, plan_rel, proposal):
        title = f"{self.plan['project']['name']}: plan page"
        body = [self.header(checks, plan_rel, proposal is not None), '<main id="main" class="wrap" tabindex="-1">']
        if proposal is not None:
            body.append(self.what_changed(proposal))
        if checks["computed"]:
            body += [self.overview(checks), self.people_section(), self.milestones(), self.work_items()]
        body.append(self.findings(checks))
        body.append("</main>")
        body = [re.sub(r"(<dd>)(.*?)(</dd>)", lambda m: m.group(1) + timed(m.group(2)) + m.group(3), b, flags=re.S) for b in body]
        body.append(f'<footer><div class="wrap"><p>Written {e(self.written)} from <code>{e(plan_rel)}</code>. '
                    "This page is private to your workspace: it names people and source locations, so do not share it.</p></div></footer>")
        return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                f"<title>{e(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
                '<a class="skip" href="#main">Skip to main content</a>\n' + "\n".join(body) + "\n</body>\n</html>\n")


def write_private(path, text):
    """Write the page with owner-only permissions: the folder 0o700, the file 0o600, replaced atomically."""
    folder = path.parent
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        raise Usage("review-folder-unusable", f"{folder} is not a plain folder, so the page was not written.")
    folder.mkdir(mode=0o700, exist_ok=True)
    os.chmod(str(folder), 0o700)
    if path.is_symlink():
        raise Usage("review-folder-unusable", f"{path} is a link, so the page was not written.")
    tmp = folder / f".{PAGE_NAME}.{os.getpid()}.tmp"
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.chmod(str(tmp), 0o600)
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()
    os.chmod(str(path), 0o600)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Write the plan page: one private HTML file for the plan owner to review the plan in a browser. "
                    "It is written only into the private workspace, at <workspace>/review/plan-page.html.",
        epilog="Exit status 0 when the page was written, 1 when plan problems stop the page, 2 for a wrong argument, "
               "a plan that cannot be read or a missing workspace.")
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: the owner's working plan, as the checker finds it)")
    ap.add_argument("--people", help="path to people.yaml, the staffing overlay. Default: people.yaml in the private workspace")
    ap.add_argument("--proposal", metavar="ID", help="the saved update proposal to lead with. Default: the newest open one")
    ap.add_argument("--dry-run", action="store_true", help="build the page and print where it would go. Write nothing")
    a = ap.parse_args(argv)

    def usage_error(code, msg):
        print(f"error: {code}: {msg}", file=sys.stderr)
        return 2

    why = L.root_problem(a.root)
    if why:
        return usage_error("root", why)
    root = Path(a.root).expanduser().resolve()
    try:
        ws, from_drafts = find_workspace(root)
    except Usage as u:
        return usage_error(u.code, u.text)
    people = a.people
    if people is None and from_drafts and (ws / "people.yaml").is_file():
        people = str(ws / "people.yaml")
    try:
        plan_path = L.owner_plan(root, a.plan)
    except L.PlanError as err:
        return usage_error("plan", err.msg)
    if not L.exists(plan_path):
        return usage_error("plan", f"plan not found at {plan_path}. Run from the project root or pass --root")
    why = L.regular_file_problem(plan_path)
    if why:
        return usage_error("plan", f"the plan path {why}" if why.startswith(str(plan_path)) else why)
    try:
        plan, plan_problems = L.load_plan_with_people(plan_path, root, people_path=people)
    except L.PlanError as err:
        return usage_error("plan", err.msg)
    try:
        proposal = find_proposal(ws, a.proposal)
    except Usage as u:
        return usage_error(u.code, u.text)

    written = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z").strip()
    plan_rel = shown_path(plan_path, root)
    stopped = False
    try:
        page = Page(plan, root, ws, a, written)
        results, ok, _n_files, n_items, _unfinished, notes = CS.run_checks(plan, root, types.SimpleNamespace(item=None, check_originals=False))
        if plan_problems:
            results = {"plan.yaml": plan_problems, **results}
        checks = {"computed": True, "results": results, "ok": ok, "n_items": n_items, "notes": notes, "problems": plan_problems}
        text = page.render(checks, plan_rel, proposal)
    except CS.PLAN_ERRORS as err:
        if not plan_problems:
            if isinstance(err, OSError):
                return usage_error("read", f"cannot read a file of the project: {err.strerror or err}" + (f" ({err.filename})" if err.filename else ""))
            raise
        stopped = True
        checks = {"computed": False, "results": {"plan.yaml": plan_problems}, "ok": 0, "n_items": 0, "notes": [], "problems": plan_problems}
        try:
            text = Page(plan, root, ws, a, written).render(checks, plan_rel, None)
        except CS.PLAN_ERRORS:
            bare = {"project": {"name": "Plan"}, "people": [], "items": []}
            text = Page(bare, root, ws, a, written).render(checks, plan_rel, None)
    if plan_problems:
        CS.print_plan_problems(plan_problems)
        if stopped:
            print("The plan page needs the problems above fixed first. It shows them and leaves out the rest.")
    target = ws / PAGE_DIR / PAGE_NAME
    if not a.dry_run:
        try:
            write_private(target, text)
        except Usage as u:
            return usage_error(u.code, u.text)
        except OSError as err:
            return usage_error("write-failed", f"the page could not be written: {err.strerror or err}")
    print(f"plan page: {target}")
    if a.dry_run:
        print("Dry run: nothing was written.")
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
