#!/usr/bin/env python3
"""Prepare a field run of the update path: a fresh agent, the two installed skills and a revised document.

The coordinator runs the update path the way a real plan owner would. The owner's agent is a fresh coding
agent that has only the two installed skills and one sentence. This script builds the folder that run needs,
so that nothing from the repository leaks into it. The folder holds:

  install/               the two skills, copied whole, as an installer places them. Nothing else from the
                         repository. The agent reads the skills here and runs their scripts from here.
  project/               a released project (a git repository with a local bare origin), with the owner's
                         private workspace under the folder's own home folder.
  home/                  the HOME of the run. The workspace is home/.carrydown/workspaces/<slug>/.
  origin.git/            the local bare repository that is the project's origin (no network).
  revision/              the revised source document, the one thing the owner brings.
  persona.md             the owner's answers to every question the skill may ask during an update.
  OWNER_AGENT_BRIEF.md   the instructions the coordinator gives the fresh agent.
  OBSERVER_BRIEF.md      what the coordinator watches, and how to measure the run afterward.
  run_logged.py          a small helper that runs a command and appends it to the command log.
  transcript/            where the agent writes questions, owner messages, commands and notes.
  field-run.json         the facts measure_field_run.py compares the run with. The agent does not need it.

Default (the sample): the sample project and tests/fixtures/sample-workspace, wired as
tests/rebuild_sample_release.py wires them, with a committed history, a local bare origin, one engineer
decision entry planted in the WI-03 specification (and released with it), and a realistic revision of
sample/expense-approvals/ground-truth/architecture.md saved as architecture.md and architecture.docx.

  python3 tests/field_run/prepare_field_run.py --out DIR

With --scenario request-trace the revision changes only the logging rule (section 4.2 item 6) and the version line,
and the planted entry is a staged test decision in the WI-09 specification, committed and not yet released. The
release and the publication are left to tests/field_run/update_validation/driver.py.

Real project (the coordinator's own):

  python3 tests/field_run/prepare_field_run.py --out DIR --project PATH --workspace PATH --revised-doc PATH

The project and the workspace are COPIED into DIR. The originals are never changed, and the copy's origin is
a local bare clone, so the run cannot reach the real remote. Add --establish-checkpoint to record the
project's current renderings as the reviewed baseline in the copy, when it has none yet.

Standard library only. Python 3.9 or later. No token and no network. Nothing is pushed.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SAMPLE = ROOT / "sample" / "expense-approvals"
FIXTURE = ROOT / "tests" / "fixtures" / "sample-workspace"
SKILLS = ("carrydown-ground-truth", "carrydown-plan-to-github")
IDENTITY = ("Sample Owner", "sample.owner@example.com")
SLUG = "expense-approvals"
REPOSITORY_ID = "4200"
BOARD = ["--board-owner-id", "4400", "--board-project-id", "PVT_sample"]
WI03 = "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md"
ENTRY = ("- 2027-02-22. Reminders go out after 3 business days, the number in section 3.5. The number is read from "
         "one setting, so the plan owner can change it later (pull request 12).")
FOLDER_FORMAT = 1
OWNER_SENTENCE = "This changed: the revised {name} document is at revision/{file}"

sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_numbered_docx as DOCX  # noqa: E402  (the Word writer helpers of this repository's fixtures)

# ---------------------------------------------------------------------------
# The revision of the sample's architecture document
# ---------------------------------------------------------------------------

# Each edit is (old text, new text). The old text must occur exactly once. Nothing is renumbered.
REVISION_EDITS = [
    # a quantity in a section WI-03 cites (3.5): the reminder interval
    ("3. A reminder goes to the current approver after 3 business days without a decision.",
     "3. A reminder goes to the current approver after 2 business days without a decision."),
    # the delegated approval rule (4.1 item 4), which WI-04 cites
    ("4. A delegate may act only for dates inside the delegate record, and never on a report that the delegator submitted.\n",
     "4. A delegate may act only for dates inside the delegate record, and never on a report that the delegator submitted. "
     "A delegate's approval counts only for a base total up to 5,000.00, whatever the delegator's own limit is.\n"),
    # the edge case that asked for the number to be settled (6.2 item 6)
    ("6. Finance asked for a reminder after 2 business days (BA-6). Section 3.5 says 3. The architecture document is the "
     "ground truth, so work items use 3. The next version of this document should settle the number.",
     "6. Finance asked for a reminder after 2 business days (BA-6). Section 3.5 now says 2, so work items use 2."),
    # one new subsection nobody cites: a rule about audit logging. It is added after 4.2, so no section is renumbered.
    ("## 5. Development standard",
     "### 4.3 GOV-3 Audit of delegated decisions\n\n"
     "Owner: internal audit. Applies to every decision made by a delegate.\n\n"
     "1. A decision made by a delegate writes one audit_event of type delegate.decision, in the same database transaction as the decision.\n"
     "2. The event records the delegate and the approver the delegate replaced, as identifiers. It never holds names or comments.\n"
     "3. A delegated decision that the rules module refuses is also recorded, with the number of the rule that refused it.\n\n"
     "## 5. Development standard"),
]


# The request-trace scenario (specs/sample-before-and-after-demo.md, section 4): one changed logging rule and the
# version line, nothing else. The staged decision goes into the ledger export specification (WI-09) and the
# release, approval and publication are left to the caller (tests/field_run/update_validation/driver.py).
TRACE_EDITS = [
    ("*Fictional sample. Version 0.3.", "*Fictional sample. Version 0.4."),
    ("6. Log lines carry report identifiers and event types. They never carry amounts, comments or receipt contents.",
     "6. Log lines carry report identifiers, event types and an identifier for the request or scheduled job run. "
     "They never carry amounts, comments or receipt contents."),
]
WI09 = "docs/spec/m4-pilot/wi-09-ledger-export.md"
TRACE_ENTRY = ("- 2026-11-22. Test scenario decision: export tests will write files to a temporary folder instead of the finance "
               "drop folder. Synthetic review reference https://example.invalid/test-scenario/pull/1, not a real pull request.")
TRACE_SENTENCE = ("This changed: the logging rule now requires each entry to identify its request or scheduled job run. "
                  "The revised architecture document is at revision/{file}")


def revise_architecture(text, edits=None):
    """The revised Markdown of the sample's architecture document. Raises ValueError when an edit does not apply."""
    for old, new in (REVISION_EDITS if edits is None else edits):
        if text.count(old) != 1:
            raise ValueError("the sample's architecture document changed: this text is not found once: " + old[:70])
        text = text.replace(old, new)
    return text


# ---------------------------------------------------------------------------
# Markdown to a numbered Word document (standard library only)
# ---------------------------------------------------------------------------

W_NS = DOCX.W
MONO = '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>'


def xml_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def runs(text, italic=False):
    """Word runs for one line of Markdown prose: inline code in a monospaced font, the rest plain."""
    out = []
    for i, part in enumerate(re.split(r"`", text)):
        if not part:
            continue
        props = ""
        if i % 2 == 1:
            props = MONO
        elif italic:
            props = "<w:i/>"
        out.append(f'<w:r>{"<w:rPr>" + props + "</w:rPr>" if props else ""}<w:t xml:space="preserve">{xml_escape(part)}</w:t></w:r>')
    return "".join(out)


def para(text, style=None, italic=False):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}{runs(text, italic)}</w:p>"


def code_para(line):
    return (f'<w:p><w:r><w:rPr>{MONO}</w:rPr><w:t xml:space="preserve">{xml_escape(line)}</w:t></w:r></w:p>')


def table(rows):
    width = max(len(r) for r in rows)
    grid = "<w:tblGrid>" + '<w:gridCol w:w="2400"/>' * width + "</w:tblGrid>"
    body = []
    for row in rows:
        cells = "".join(f"<w:tc>{para(cell)}</w:tc>" for cell in row)
        body.append(f"<w:tr>{cells}</w:tr>")
    return '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>' + grid + "".join(body) + "</w:tbl>"


def split_row(line):
    inner = line.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", inner)]


def list_paragraph(lines):
    """Typed list items kept in one paragraph, with a soft line break after each (Shift+Enter in Word). The
    renderer then writes them on consecutive lines, as the Markdown source has them."""
    out = []
    for i, line in enumerate(lines):
        out.append(runs(line))
        if i + 1 < len(lines):
            out.append("<w:r><w:br/></w:r>")
    return "<w:p>" + "".join(out) + "</w:p>"


def markdown_body(md):
    """Word body XML for a Markdown document. Headings use the Heading1 and Heading2 styles, which number
    themselves (1. then 1.1), so a typed number in the Markdown heading is dropped."""
    lines = md.replace("\r\n", "\n").split("\n")
    body, i = [], 0
    typed = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
        elif stripped.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(code_para(lines[i]))
                i += 1
            i += 1
        elif line.startswith("# "):
            body.append(para(line[2:].strip(), "Title"))
            i += 1
        elif line.startswith("## ") or line.startswith("### "):
            level = 1 if line.startswith("## ") else 2
            text = typed.sub("", line.lstrip("#").strip())
            body.append(para(text, f"Heading{level}"))
            i += 1
        elif stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            body.append(table(rows))
        elif re.match(r"^\d+\.\s", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i]):
                items.append(lines[i].strip())
                i += 1
            body.append(list_paragraph(items))
        elif re.fullmatch(r"\*[^*].*\*", stripped):
            body.append(para(stripped[1:-1], "Subtitle", italic=True))
            i += 1
        else:
            body.append(para(stripped))
            i += 1
    return "".join(body)


def build_docx(md, out):
    """Write md as a Word document at out. The headings are numbered by their styles, the most common layout."""
    body = markdown_body(md)
    doc = f"{DOCX.DECL}<w:document {W_NS}><w:body>{body}</w:body></w:document>"
    styles = "".join([
        DOCX.style("Normal", "Normal"),
        DOCX.style("Title", "Title", "Normal"),
        DOCX.style("Subtitle", "Subtitle", "Normal"),
        DOCX.style("Heading1", "heading 1", "Normal", numid=7, ilvl=0, outline=0),
        DOCX.style("Heading2", "heading 2", "Normal", numid=7, ilvl=1, outline=1),
    ])
    numbering = (
        '<w:abstractNum w:abstractNumId="4">'
        '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading1"/><w:lvlText w:val="%1."/></w:lvl>'
        '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading2"/><w:lvlText w:val="%1.%2"/></w:lvl>'
        '</w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="4"/></w:num>'
    )
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rIdN" Type="{rel}/numbering" Target="numbering.xml"/></Relationships>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    parts = [
        ("[Content_Types].xml", ct),
        ("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        f'<Relationship Id="r1" Type="{rel}/officeDocument" Target="word/document.xml"/></Relationships>'),
        ("word/document.xml", doc),
        ("word/styles.xml", f"{DOCX.DECL}<w:styles {W_NS}>{styles}</w:styles>"),
        ("word/numbering.xml", f"{DOCX.DECL}<w:numbering {W_NS}>{numbering}</w:numbering>"),
        ("word/_rels/document.xml.rels", rels),
    ]
    DOCX.write_zip(str(out), parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class PrepareError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_env(home):
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(Path(home) / "xdg"),
               GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1")
    for name in ("CARRYDOWN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GIT_CONFIG_GLOBAL", "GIT_DIR", "GIT_WORK_TREE"):
        env.pop(name, None)
    return env


def run(args, cwd, env, ok=(0,)):
    out = subprocess.run([str(a) for a in args], cwd=str(cwd), capture_output=True, text=True, env=env)
    if out.returncode not in ok:
        raise PrepareError(f"command failed (exit {out.returncode}): {' '.join(str(a) for a in args[:5])}\n{out.stdout}{out.stderr}")
    return out.stdout


def git(project, env, *args, ok=(0,)):
    return run(["git"] + list(args), project, env, ok)


def copy_skills(dest):
    dest.mkdir(parents=True)
    for name in SKILLS:
        src = ROOT / "skills" / name
        if not (src / "SKILL.md").is_file():
            raise PrepareError(f"the repository has no skill at {src}")
        shutil.copytree(str(src), str(dest / name), ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))


def proposal_id(text):
    m = re.search(r"^proposal: ([0-9a-f]{64})$", text, re.M)
    if not m:
        raise PrepareError("no proposal id in the output of reconcile.py prepare")
    return m.group(1)


def active_release(skill, project, env):
    out = run([sys.executable, skill / "scripts" / "reconcile.py", "status", "--root", ".", "--json"], project, env)
    info = json.loads(out).get("active_release") or {}
    if not info.get("release_id") or not info.get("request_id"):
        raise PrepareError("the project has no active release to bind a checkpoint to")
    return info


def workspace_of(project):
    pointer = Path(project) / ".carrydown" / "local.yaml"
    for line in pointer.read_text(encoding="utf-8").splitlines():
        if line.startswith("workspace:"):
            return Path(line.split(":", 1)[1].strip().strip('"'))
    raise PrepareError("the project has no workspace pointer")


def write_publication_journal(workspace, release_id, request_id):
    manifest = json.loads((workspace / "releases" / release_id / "content-manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("files", manifest) if isinstance(manifest, dict) else manifest
    paths = [e["path"] if isinstance(e, dict) else e for e in entries]
    targets = {p[len("payloads/"):-5]: {"state": "completed"} for p in paths if p.startswith("payloads/") and p.endswith(".json")}
    folder = workspace / "publication"
    folder.mkdir(exist_ok=True)
    (folder / f"{request_id}.journal.json").write_bytes((json.dumps({"journal_format": 1, "request_id": request_id, "targets": targets})).encode("utf-8"))


def establish_checkpoint(gt_skill, project, env):
    """Record the project's current renderings as the reviewed source checkpoint, through the real commands."""
    out = run([sys.executable, gt_skill / "scripts" / "reconcile.py", "prepare", "--root", ".", "--apply"], project, env)
    pid = proposal_id(out)
    workspace = workspace_of(project)
    descriptor = workspace / "drafts" / "proposals" / pid / "descriptor.json"
    made = run([sys.executable, gt_skill / "scripts" / "workspace.py", "checkpoint", "prepare", "--root", ".", "--descriptor",
                descriptor, "--rendering-dir", "docs/ground-truth", "--apply"], project, env)
    m = re.search(r"checkpoint ([0-9a-f]{64})", made)
    if not m:
        raise PrepareError("no checkpoint id in the output of workspace.py checkpoint prepare")
    cid = m.group(1)
    run([sys.executable, gt_skill / "scripts" / "workspace.py", "checkpoint", "commit", "--root", ".", "--id", cid, "--apply"], project, env)
    try:
        info = active_release(gt_skill, project, env)
    except PrepareError:
        return cid
    run([sys.executable, gt_skill / "scripts" / "workspace.py", "checkpoint", "bind", "--root", ".", "--id", cid,
         "--release-id", info["release_id"], "--request-id", info["request_id"], "--apply"], project, env)
    return cid


# ---------------------------------------------------------------------------
# The two projects
# ---------------------------------------------------------------------------

def make_origin(out, project, env):
    origin = out / "origin.git"
    git(project, env, "clone", "-q", "--bare", str(project), str(origin))
    remotes = git(project, env, "remote").split()
    if "origin" in remotes:
        git(project, env, "remote", "set-url", "origin", str(origin))
    else:
        git(project, env, "remote", "add", "origin", str(origin))
    git(project, env, "fetch", "-q", "origin")
    branch = git(project, env, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch != "HEAD":
        git(project, env, "branch", "-q", "--set-upstream-to", f"origin/{branch}", branch, ok=(0, 128))
    return origin


def build_sample(out, env, gt_skill, pub_skill, trace=False):
    """The released sample, with an owner workspace, a history, a local origin and one planted engineer entry.
    With trace, the entry is the staged WI-09 decision, committed but not released, and the reviewed checkpoint is
    recorded before any new release: the caller runs the release, the approval and the publication."""
    home = Path(env["HOME"])
    project = out / "project"
    shutil.copytree(str(SAMPLE), str(project), ignore=shutil.ignore_patterns("__pycache__"))
    git(project, env, "init", "-q", "-b", "main")
    git(project, env, "config", "user.name", IDENTITY[0])
    git(project, env, "config", "user.email", IDENTITY[1])
    run([sys.executable, gt_skill / "scripts" / "workspace.py", "init", "--root", ".", "--slug", SLUG, "--answer", "yes", "--apply"],
        project, env)
    workspace = workspace_of(project)
    shutil.copyfile(str(FIXTURE / "drafts" / "plan.yaml"), str(workspace / "drafts" / "plan.yaml"))
    # the staffing overlay of the sample, so the checker finds every person the plan names (init writes a starter file)
    shutil.copyfile(str(SAMPLE / "people.yaml"), str(workspace / "people.yaml"))
    for sub in ("releases", "requests", "events"):
        shutil.rmtree(str(workspace / sub), ignore_errors=True)
        shutil.copytree(str(FIXTURE / sub), str(workspace / sub))
    git(project, env, "add", "-A")
    git(project, env, "commit", "-q", "-m", "Release the plan")
    make_origin(out, project, env)
    git(project, env, "push", "-q", "-u", "origin", "main")
    # an engineer's decision entry, merged and then released with the plan, so it is approved text
    rel, entry, name = (WI09, TRACE_ENTRY, "WI-09") if trace else (WI03, ENTRY, "WI-03")
    spec = project / rel
    text = spec.read_text(encoding="utf-8")
    if "## Decisions recorded\n\nNone yet.\n" not in text:
        raise PrepareError(f"the {name} specification of the sample has changed: its Decisions recorded section is not empty")
    spec.write_bytes((text.replace("## Decisions recorded\n\nNone yet.\n", "## Decisions recorded\n\n" + entry + "\n")).encode("utf-8"))
    if trace:
        git(project, env, "commit", "-q", "-am", "Stage a test scenario decision in WI-09")
        establish_checkpoint(gt_skill, project, env)
        return project, workspace
    git(project, env, "commit", "-q", "-am", "Record a decision in WI-03 (pull request 12)")
    release = [sys.executable, pub_skill / "scripts" / "release.py"]
    made = run(release + ["prepare", "--root", ".", "--repository-id", REPOSITORY_ID, "--apply"] + BOARD, project, env)
    request = next((ln.split(":", 1)[1].split()[0] for ln in made.splitlines() if ln.startswith("request id (permission):")), None)
    if not request:
        raise PrepareError("no request id in the output of release.py prepare")
    run(release + ["approve", "--root", ".", "--request", request, "--local", "--preview-shown", "--apply"], project, env)
    run(release + ["export", "--root", ".", "--request", request, "--apply"], project, env)
    git(project, env, "add", "-A")
    git(project, env, "commit", "-q", "-m", "Release the plan with the engineer's decision")
    git(project, env, "push", "-q", "origin", "main")
    info = active_release(gt_skill, project, env)
    write_publication_journal(workspace, info["release_id"], info["request_id"])
    establish_checkpoint(gt_skill, project, env)
    return project, workspace


def build_real(out, env, gt_skill, project_src, workspace_src, checkpoint):
    """Copies of the coordinator's own project and workspace, with the origin of the copy made local."""
    home = Path(env["HOME"])
    if not (project_src / ".git").exists():
        raise PrepareError(f"{project_src} is not a git repository: the engineers' check and the update path need one")
    if not (workspace_src / "workspace.yaml").is_file():
        raise PrepareError(f"{workspace_src} is not a carrydown workspace (no workspace.yaml)")
    project = out / "project"
    workspace = home / ".carrydown" / "workspaces" / workspace_src.name
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(project_src), str(project), symlinks=True)
    shutil.copytree(str(workspace_src), str(workspace), symlinks=True)
    os.chmod(str(workspace), 0o700)
    pointer = project / ".carrydown" / "local.yaml"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_bytes((f"workspace: {workspace}\n").encode("utf-8"))
    # the workspace names its engineering folder: in the copy that is the copied project
    record = workspace / "workspace.yaml"
    old = (str(project_src), os.path.realpath(str(project_src)))
    text = record.read_text(encoding="utf-8")
    for form in old:
        text = text.replace(f'path: "{form}"', f'path: "{project}"')
    record.write_bytes((text).encode("utf-8"))
    name = git(project, env, "config", "user.name", ok=(0, 1)).strip()
    email = git(project, env, "config", "user.email", ok=(0, 1)).strip()
    if not name or not email:
        git(project, env, "config", "user.name", IDENTITY[0])
        git(project, env, "config", "user.email", IDENTITY[1])
    dirty = bool(git(project, env, "status", "--porcelain").strip())
    make_origin(out, project, env)
    if checkpoint:
        establish_checkpoint(gt_skill, project, env)
    return project, workspace, dirty


# ---------------------------------------------------------------------------
# The documents of the run
# ---------------------------------------------------------------------------

PERSONA = """# The plan owner's answers

This file is the plan owner in this field run. The agent reads the answer here instead of asking a person.
Each entry has an id (P1 to P5). The agent writes the id in `transcript/questions.md` next to the question.

How to use it.

- Do not open this file until you have something to ask the owner. Then find the entry that fits your question.
- Ask the owner only what the skill says to ask. When the skill needs an answer that is listed here, write
  the question in `transcript/questions.md`, copy the answer from this file and go on.
- If you want to ask something that is not listed here, the observer records it as an unnecessary question
  and answers with the shortest truthful answer. In this run you do both: write the question in
  `transcript/questions.md` with `Persona entry: none`, answer it yourself with the shortest truthful answer
  that this file and the project state allow, and go on. Do not stop to wait.
- The owner answers only after the agent has asked. The owner does not volunteer commands, file names or
  identifiers, and does not read any file. The owner knows what they changed and what they decided, and no more.

## What the owner knows

{knowledge}

## The answers

### P1. Which project is this?

{p1}

### P2. Is this the source that changed, and is it the one to compare?

{p2}

### P3. Do you accept the review?

Yes. Accept the proposed updates and the "no change needed" reasons as they are written, apart from the decision in P4.
If something in the review is wrong or missing, the owner would not know. Do not ask the owner to check it again.

### P4. The agent shows a conflict between something an engineer recorded and the revised document, and asks which wins.

The revised document wins, for the text of the specification. Leave the engineer's dated note in the record as it is:
do not edit it and do not delete it. An engineer wrote it and the owner does not rewrite it.

### P5. Do you approve applying the accepted updates?

Yes, approve. Apply the accepted updates to the working drafts and record the accepted source checkpoint.
Do not release or publish anything. The owner will say "Put the plan on GitHub." later, in a separate step.
P3 and P5 may be one interaction when the review ends with the approval question.

## Everything else

The owner does not answer questions about Python, git, where drafts are kept, which sources exist, staffing, owners, dates,
budgets or GitHub. If you ask any of them, that is an unnecessary question: the skill and the project already say.
"""

SAMPLE_KNOWLEDGE = """The owner of the fictional expense approvals project. The finance policy team revised the architecture document.
The revised document is at `revision/architecture.docx`. It replaces the earlier version. Nothing else changed.
The owner does not list the edits section by section. Finding them is the agent's job. The project is the folder `project/`.
The owner has no other project and keeps no other source elsewhere."""

TRACE_KNOWLEDGE = """The owner of the fictional expense approvals project. Internal audit revised the logging rule of the architecture
document (version 0.4). The revised document is at `revision/architecture.docx`. It replaces the earlier version. Nothing else
changed. The reason is that support must connect the log entries of one request or of one nightly export run. The owner does not
list the edits section by section. Finding them is the agent's job. The project is the folder `project/`. The owner has no other
project and keeps no other source elsewhere."""

TRACE_P6 = """### P6. Which identifier is meant, and where does it come from?

For a request, the identifier the API gateway assigns to each request. For a nightly job, the scheduler's run identifier.
Both are opaque strings, carried in every log line of that operation. The revised document is version 0.4.

"""

REAL_KNOWLEDGE = """The owner of this project. The owner revised the source document named in the first sentence. It replaces the earlier version
of the same source. The project is the folder `project/`. The coordinator edits this file before the run to add what the
owner knows about the change, and to add answers for questions this project may raise. Entries P1 to P5 are the defaults."""

OWNER_BRIEF = """# Brief for the owner's agent

You are the plan owner's coding agent. You have two skills installed in `{install}`:
`carrydown-ground-truth` and `carrydown-plan-to-github`. The plan owner has a released project and has revised a
source document. You do what the skills instruct, as an agent that has only those skills and the owner's sentence.

The folder for this run is `{out}`. Everything you need is under it. Do not read anything outside it. In particular do
not read any file of the carrydown repository, any specification, any test, or `field-run.json`.

## The owner's first and only sentence

> {sentence}

That is all the owner says. The owner will not repeat it or add to it. Everything else you need comes from the skills,
the project and `persona.md`.

## Rules for this run

1. Start by reading `{install}/carrydown-ground-truth/SKILL.md`. Act only as the skill files instruct. Read a reference
   or a template when the skill points to it, and not before. If the skill and this brief disagree, follow this brief and
   write the disagreement in `transcript/notes.md`.
2. Run every command from `{project}` (the project folder). Use the HOME of this folder: `{home}`. The helper
   `{helper}` does this for you and writes the command log: put it in front of every command, as
   `python3 {helper} -- <command and arguments>`. It sets HOME, runs the command in the current folder, appends one line
   to `transcript/commands.log` with the time and the exit code, and passes the output through. If you run a command
   without it, append the same kind of line yourself: `[<UTC time>] exit=<code> $ <command>`. Every command is logged,
   including reads such as `cat`, `ls` and `git status`. `python3 {helper} --now` prints the UTC time.
3. The owner is a person, not a terminal. Write every question you would ask the owner in `transcript/questions.md`,
   and read the answer from `persona.md`, which you open only when you have a question to ask. Each question is one block:

   ```
   ## Q<number> <UTC time>
   Persona entry: <P1 to P5, several joined by +, or none>
   Question: <exactly what you would say to the owner>
   Answer: <the answer, copied from persona.md, or your shortest truthful answer when the entry is none>
   ```

   Ask a question only when the skill says the answer is ambiguous and changes the result. A question that repeats what
   the project or the skill already tells you is an unnecessary question, so do not ask it. If you ask one anyway, use
   `Persona entry: none`.
4. Write every message you would show the owner in `transcript/to_owner.md`, in the words you would use with the owner,
   one block each:

   ```
   ## M<number> <UTC time>
   <the message>
   ```

   This includes the consolidated review, the words of every question you record in `questions.md` (the owner sees
   each question), the question that asks for the final approval, and the final report of the states. The review follows `templates/reconcile-review.md` of the skill. A message the owner sees must follow the
   skill's rule for owner-facing text: no command, no flag and no internal identifier. Work item ids and section numbers
   are fine. Put nothing technical in `to_owner.md`. Keep that in the command log and in your own working notes.
5. When you hesitate, are unsure what the skill wants, find the skill unclear or wrong, work around something, or do
   anything the skill does not say, append one line to `transcript/notes.md`: `[<UTC time>] <what, and why>`.
   Record each such place as it happens. These notes are the main result of the run.
6. You may write the proposal's `dispositions.json` and the patches the way the skill describes. You may use other
   commands to read files, to compute a digest or to compare text. Log them like every other command.
7. Do not touch GitHub. Do not run `release.py`, `scaffold_spec.py` or any `github_` script. Do not run a raw `git push`,
   `git commit`, `git reset` or any other git command that changes history or the working files. Do not read a token or any environment variable that holds
   one. Do not install software. Do not create a replacement project.

## Where to stop

Do the update path as the skill describes it, through these points, in this order:

1. route by project state (the skill's status command),
2. render the revised document,
3. compare and save the proposal,
4. assess the impact and write the dispositions and the patches,
5. run the independent review pass the skill describes, then the check,
6. present the one consolidated review to the owner, and get the answers and the final approval from `persona.md`,
7. apply the accepted patches to the working drafts (the skill's apply step, the preview first), and record the
   accepted source checkpoint the way the skill's step 8 says,
8. tell the owner the next action and report the states the skill lists.

Stop there. Do not release, do not publish and do not run the other skill's commands. When you stop, write
`DONE` as the last line of `transcript/notes.md`, then reply with a short list of what you did and what you could not do.
"""

OBSERVER_BRIEF = """# Brief for the observer

The observer is the coordinator. The aim of the run is to measure the owner's experience of an update against the
targets of `specs/reconciliation-design.md`, section 3.6, and to record every place the agent hesitated, asked,
deviated from the skill or produced a wrong patch. The folder is built for a fresh agent that has only the two installed
skills.

## Before the run

1. Check that the folder is complete: `install/` holds exactly two skills, `project/` is a git repository with the
   remote `origin` (a local bare repository), `revision/` holds the revised document, `persona.md` and
   `OWNER_AGENT_BRIEF.md` exist, and `transcript/` holds only empty files.
2. Edit `persona.md` only before the run, and only to add what the owner would know. Do not edit it during the run.
3. Do not coach the agent. Do not answer its questions yourself. The persona answers them.

## Starting the run

Start a fresh coding agent (no memory of this repository, no access to the repository folder if you can help it) with
the contents of `OWNER_AGENT_BRIEF.md` as its instructions, and the folder `{out}` as its working folder.
Use a model that a plan owner would have. Record the model name in `transcript/observer.md`.

The run is finished when the last line of `transcript/notes.md` is `DONE`, or when you stop it. Stop it if the agent
runs `release.py` or any `github_` script, pushes, or leaves the folder.

## What to record during the run

In `transcript/observer.md`, one line each, with the time:

- every point where the agent seemed to hesitate or went back,
- every question it put to the owner that the persona did not list (the measure script also counts these),
- every time it did something the skill does not say,
- anything the owner would have found confusing in `transcript/to_owner.md`.

## Measuring

```
python3 tests/field_run/measure_field_run.py --dir {out}
```

It reads the transcript and the project state, prints the report and writes `report.md` in the folder. It computes:

| Target (section 3.6) | How it is measured |
| --- | --- |
| One initiating sentence | The first sentence is the only owner input. Everything after it is a counted interaction. |
| One compact review | A message in `to_owner.md` that has the lead sentence of counts and the review headings of the template. |
| One final approval | The number of questions in `questions.md`. The target is two at most: the review with its decisions, and the approval. |
| No owner-entered commands or identifiers | `to_owner.md` is searched for commands, flags, script names, digests, proposal ids and block references. |
| No repeated questions | A persona entry asked twice, and every question with `Persona entry: none`, are counted as unnecessary. |
| Explicit state and next action | The last owner message names the states and the next action. |
| Every changed block has a disposition | `reconcile.py check` on the saved proposal exits 0. |
| Engineer decision kept | The planted entry is still in the WI-03 specification word for word (the sample only). |
| New uncited rule reached WI-07 | The disposition of the new block, or an owner message, names WI-07 (the sample only). |
| Applied patches match the proposal | The digest of each patched file equals the digest of the patch text. |
| Elapsed time | From the first logged command to the approval question. A measured value, not a promise. |
| Deviations | `commands.log` compared with the expected command sequence of the skill. |

The measure script reports facts. Read the transcript yourself for the rest: whether the patches are right, whether
the review was understandable and what the agent wrote in `notes.md`. `report.md` lists the patches so you can read them.

## After the run

Keep the folder. Do not change `project/` or the workspace before the report is written. To run the update path again
from the same starting point, prepare a new folder.
"""


def write_helper(out):
    shutil.copyfile(str(HERE / "run_logged.py"), str(out / "run_logged.py"))


def write_documents(out, manifest, real):
    install = out / "install"
    params = {"out": str(out), "install": str(install), "project": str(out / "project"), "home": str(out / "home"),
              "helper": str(out / "run_logged.py"), "sentence": manifest["owner_sentence"]}
    (out / "OWNER_AGENT_BRIEF.md").write_bytes((OWNER_BRIEF.format(**params)).encode("utf-8"))
    (out / "OBSERVER_BRIEF.md").write_bytes((OBSERVER_BRIEF.format(**params)).encode("utf-8"))
    name, file = manifest["source_name"], manifest["revised_file"]
    if real:
        knowledge = REAL_KNOWLEDGE
        p2 = (f"Yes. The document at `revision/{file}` is the new version of the source `{name}`. It replaces the earlier one. "
              "Nothing else changed, and no source is kept anywhere else.")
    else:
        knowledge = TRACE_KNOWLEDGE if manifest.get("scenario") == "request-trace" else SAMPLE_KNOWLEDGE
        p2 = (f"Yes. The document at `revision/{file}` is the new version of the architecture document. It replaces the earlier one. "
              "It is the only source that changed, and no source is kept anywhere else.")
    p1 = "This one. The project is the folder you are working in, `project/`. The owner has no other project."
    persona = PERSONA.format(knowledge=knowledge, p1=p1, p2=p2)
    if manifest.get("scenario") == "request-trace":
        persona = persona.replace("## Everything else\n", TRACE_P6 + "## Everything else\n", 1)
    (out / "persona.md").write_bytes(persona.encode("utf-8"))
    transcript = out / "transcript"
    transcript.mkdir(exist_ok=True)
    for f in ("questions.md", "to_owner.md", "commands.log", "notes.md", "observer.md"):
        (transcript / f).write_bytes(("").encode("utf-8"))


PERSONA_IDS = ["P1", "P2", "P3", "P4", "P5"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="the field-run folder to create. It must not exist or must be empty")
    ap.add_argument("--project", help="a real project to copy into the run (a git repository). Needs --workspace and --revised-doc")
    ap.add_argument("--workspace", help="the owner's private workspace of that project, copied into the run's home folder")
    ap.add_argument("--revised-doc", help="the revised source document (.docx, .md or .txt), copied to revision/")
    ap.add_argument("--scenario", choices=("stock", "request-trace"), default="stock",
                    help="the sample's revision: stock (the default) or request-trace, the logging rule of section 4.2 and a staged WI-09 "
                         "decision, left unreleased for the update validation driver")
    ap.add_argument("--establish-checkpoint", action="store_true",
                    help="record the copy's current renderings as the reviewed baseline (a real project that has no checkpoint yet)")
    a = ap.parse_args(argv)
    real = any([a.project, a.workspace, a.revised_doc])
    if real and not all([a.project, a.workspace, a.revised_doc]):
        ap.error("--project, --workspace and --revised-doc go together")
    if real and a.scenario != "stock":
        ap.error("--scenario is for the sample")
    if a.establish_checkpoint and not real:
        ap.error("--establish-checkpoint is for a real project. The sample run always starts from a reviewed baseline")
    out = Path(a.out).expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        print(f"error: {out} is not empty. Choose a new folder", file=sys.stderr)
        return 2
    if shutil.which("git") is None:
        print("error: git is needed", file=sys.stderr)
        return 2
    try:
        return build(out, a, real)
    except PrepareError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def build(out, a, real):
    out.mkdir(parents=True, exist_ok=True)
    home = out / "home"
    home.mkdir()
    os.chmod(str(home), 0o700)
    name, email = IDENTITY
    (home / ".gitconfig").write_bytes((f"[user]\n\tname = {name}\n\temail = {email}\n[init]\n\tdefaultBranch = main\n").encode("utf-8"))
    env = run_env(home)
    copy_skills(out / "install")
    gt_skill = out / "install" / SKILLS[0]
    pub_skill = out / "install" / SKILLS[1]
    revision = out / "revision"
    revision.mkdir()
    manifest = {"format": FOLDER_FORMAT, "created": now(), "mode": "project" if real else "sample", "install": "install",
                "project": "project", "home": "home", "persona_ids": PERSONA_IDS, "planted_entry": None, "uncited": None,
                "probes": [], "dirty_project": False}
    if real:
        src = Path(a.revised_doc).expanduser().resolve()
        if not src.is_file():
            raise PrepareError(f"{src} is not a file")
        shutil.copyfile(str(src), str(revision / src.name))
        project, workspace, dirty = build_real(out, env, gt_skill, Path(a.project).expanduser().resolve(),
                                               Path(a.workspace).expanduser().resolve(), a.establish_checkpoint)
        manifest["dirty_project"] = dirty
        manifest["source_name"] = src.stem
        manifest["revised_file"] = src.name
        manifest["checkpoint_established"] = bool(a.establish_checkpoint)
    elif a.scenario == "request-trace":
        original = (SAMPLE / "ground-truth" / "architecture.md").read_text(encoding="utf-8")
        revised = revise_architecture(original, TRACE_EDITS)
        (revision / "architecture.md").write_bytes(revised.encode("utf-8"))
        build_docx(revised, revision / "architecture.docx")
        project, workspace = build_sample(out, env, gt_skill, pub_skill, trace=True)
        manifest.update(scenario="request-trace", source_name="architecture", revised_file="architecture.docx",
                        planted_entry={"path": WI09, "text": TRACE_ENTRY}, persona_ids=PERSONA_IDS + ["P6"], released=False)
    else:
        original = (SAMPLE / "ground-truth" / "architecture.md").read_text(encoding="utf-8")
        revised = revise_architecture(original)
        (revision / "architecture.md").write_bytes((revised).encode("utf-8"))
        build_docx(revised, revision / "architecture.docx")
        project, workspace = build_sample(out, env, gt_skill, pub_skill)
        manifest["source_name"] = "architecture"
        manifest["revised_file"] = "architecture.docx"
        manifest["planted_entry"] = {"path": WI03, "text": ENTRY}
        manifest["uncited"] = {"section": "4.3", "expected_candidate": "WI-07",
                               "why": "GOV-3 is a new audit logging rule that no specification cites. WI-07 owns the audit writer."}
        wi06 = "docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md"
        wi07 = "docs/spec/m3-enforce-policy/wi-07-audit-log.md"
        wi08 = "docs/spec/m3-enforce-policy/wi-08-notifications-delegates.md"
        delegate = "A delegate's approval counts only for a base total up to 5,000.00"
        manifest["probes"] = [
            {"name": "WI-03 takes the revised reminder interval (section 3.5)", "path": WI03, "must_contain": ["after 2 business days"],
             "must_not_contain_outside_entry": ["after 3 business days", "Use 3."]},
            {"name": "WI-08 takes the revised reminder interval (it cites 3.5)", "path": wi08, "must_contain": ["after 2 business days"],
             "must_not_contain": ["after 3 business days"]},
            {"name": "WI-06 states the revised delegated approval rule (4.1 item 4)", "path": wi06, "must_contain": [delegate]},
            {"name": "WI-08 quotes the revised delegated approval rule (4.1 item 4)", "path": wi08, "must_contain": [delegate]},
            {"name": "WI-07 takes the new audit rule (4.3, cited by nothing)", "path": wi07, "must_contain": ["delegate.decision"]},
        ]
    sentence = TRACE_SENTENCE if manifest.get("scenario") == "request-trace" else OWNER_SENTENCE
    manifest["owner_sentence"] = sentence.format(name=manifest["source_name"], file=manifest["revised_file"])
    manifest["workspace"] = os.path.relpath(str(workspace), str(out))
    manifest["baseline_commit"] = git(project, env, "rev-parse", "HEAD").strip()
    write_helper(out)
    write_documents(out, manifest, real)
    (out / "field-run.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    print(f"field run folder: {out}")
    print(f"  install/   {', '.join(SKILLS)}")
    print(f"  project/   {'copy of ' + a.project if real else 'the released sample'}, origin {out / 'origin.git'}")
    print(f"  workspace  {workspace}")
    print(f"  owner sentence: {manifest['owner_sentence']}")
    print("Give OWNER_AGENT_BRIEF.md to a fresh agent. Measure afterward with: "
          f"python3 tests/field_run/measure_field_run.py --dir {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
