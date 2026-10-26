#!/usr/bin/env python3
"""Self test for the carrydown skills. No GitHub token and no network are needed.

It does the following.
  1. Parses every script (a syntax check that leaves no cache files).
  2. Checks that the copies inside each skill folder match the canonical files.
  3. Runs the specification checker on the sample.
  4. Runs every script with --help.
  5. Runs the dry run of every script against the sample. Nothing is written.
  6. Copies each skill folder to a temporary folder and runs a script from the copy,
     to prove that an installed skill is self-contained.
  7. Runs the GitHub scripts against a local mock of the GitHub API (tests/mock/, on
     127.0.0.1 only): a 502 after a create, a crash then a rerun, --verify on an unlinked
     id, single sign-on, a timeout, a public repository, issues and comments that are not
     the plan's, renamed issues, the token file, and the token
     check reading CARRYDOWN_GITHUB_TOKEN. It also runs the dry runs without a token.

Every step runs with HOME set to an empty temporary folder and with no
CARRYDOWN_GITHUB_TOKEN, so no stored token is ever read.
  8. Builds small Word documents with tests/fixtures/make_numbered_docx.py and renders them,
     and runs the scripts on broken variants of the sample to prove they fail with a message,
     not a traceback.
  9. Runs the planning review on variants of the sample: a milestone on one track without a
     reason, missing rationale, an item with no slack, theme switches, a critical path owned by
     one person and a load ratio above two to one.
 10. Keeps the defects of the code-path release test fixed: a self-dependency or a duplicate id
     (with a timeout, so a hang fails the step), files that are not UTF-8, plan values of the
     wrong type, flag combinations, the renderer's path checks and the checker's --item and
     --json. The token rules, the redirect guard and the project board run against the mock.
 11. Keeps the defects of the second round fixed: a list or map cut short at the end of a line,
     an item with no id, a bad title format, names and paths too long for the file system,
     named pipes and devices given as files, empty flags, and item ids in other digits. The mock
     adds 401, 429, the secondary rate limit, a 502 before a write and paged lists.

Every step has a time limit. A step that runs past it fails as a hang.

Usage
  python3 scripts/selftest.py
Exit status is 0 when every step passes, 1 otherwise, and 2 for an unknown argument.
"""
import argparse
import ast
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
HOME = tempfile.mkdtemp(prefix="carrydown-selftest-home-")
atexit.register(shutil.rmtree, HOME, True)
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HOME": HOME, "USERPROFILE": HOME}
ENV.pop("CARRYDOWN_GITHUB_TOKEN", None)
SAMPLE = "sample/expense-approvals"
results = []


class _Hung:
    returncode = "hang"
    stdout = ""

    def __init__(self, limit):
        self.stderr = f"no answer within {limit} seconds: the command hung and was stopped"


def step(name, cmd, cwd=ROOT, expect=0, contains=(), absent=("Traceback",), env=None, files=None, order=(), stdin="", timeout=180, json_out=False):
    """Run cmd and check the exit status, text that must appear, text that must not appear, and,
    with files, {path: [text, ...]} that must appear in files the command wrote. expect="nonzero"
    accepts any failing exit status. With json_out, standard output must be one JSON object. A
    command that runs longer than timeout seconds is stopped and the step fails."""
    run_env = dict(ENV, **(env or {}))
    try:
        p = subprocess.run(cmd, cwd=cwd, env=run_env, capture_output=True, text=True, encoding="utf-8", errors="replace", input=stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        p = _Hung(timeout)
    out = (p.stdout or "") + (p.stderr or "")
    missing = [c for c in contains if c not in out]
    present = [c for c in absent if c in out]
    at = [out.find(o) for o in order]
    if order and (-1 in at or at != sorted(at)):
        missing.append("in this order: " + " < ".join(order))
    for path, wants in (files or {}).items():
        body = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
        missing += [f"{Path(path).name}: {w}" for w in wants if w not in body]
    if json_out:
        try:
            if not isinstance(json.loads(p.stdout or ""), dict):
                missing.append("standard output is a JSON object")
        except ValueError:
            missing.append("standard output is valid JSON")
    status_ok = (p.returncode not in (0, "hang")) if expect == "nonzero" else p.returncode == expect
    ok = status_ok and not missing and not present
    results.append((ok, name))
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        print("      exit", p.returncode, ("missing: " + repr(missing)) if missing else "", ("unexpected: " + repr(present)) if present else "")
        for line in ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-12:]:
            print("      " + line)
    return ok


def fixtures(tmp):
    """Word documents built on the fly, so no binary file is kept in the repository."""
    make = [PY, "tests/fixtures/make_numbered_docx.py"]
    render = [PY, "scripts/render_ground_truth.py"]
    fx = tmp / "fixtures"
    (fx / "out").mkdir(parents=True)
    for mode in ("paragraph", "style", "doctype"):
        subprocess.run(make + [str(fx / f"{mode}.docx"), mode], cwd=ROOT, env=ENV, check=True)
    out = fx / "out" / "docs/ground-truth"
    step("docx: heading numbers set on the paragraphs are rendered", render + [str(fx / "paragraph.docx"), "--root", str(fx / "out"), "--version", "1"],
         contains=["footnote 1 was not rendered: The footnote text", "3 of 7 headings have no number; specifications cite sections by number"],
         files={out / "paragraph.md": ["## 1 Overview\n", "### 1.1 Scope\n", "## 2 Architecture\n", "## 3.4 Typed numbered heading\n",
                                       "## \u00dcberblick\n", "## Outline level heading\n", "Section-ref-in-field and SmartTagText and MovedText",
                                       "Text inside a block content control", "Inline control text", "Kept INSERTED", "1. first numbered\n   - nested bullet\n1. second numbered"]})
    step("docx: deleted and moved-away text is left out", [PY, "-c", "import sys; t = open(sys.argv[1], encoding='utf-8').read(); sys.exit(1 if ('DELETED' in t or 'OldPlace' in t) else 0)", str(out / "paragraph.md")])
    step("docx: heading numbers that come from the heading styles are rendered", render + [str(fx / "style.docx"), "--root", str(fx / "out"), "--version", "1"],
         contains=["1 of 7 headings have no number"],
         files={out / "style.md": ["## 1 Overview\n", "### 1.1 Scope\n", "### 1.2 Goals\n", "## 2 Architecture\n", "### 2.1 Data\n", "#### 2.1.1 Interfaces\n", "## Appendix\n"]})
    step("docx: a part with a DOCTYPE is refused", render + [str(fx / "doctype.docx"), "--root", str(fx / "out"), "--dry-run"], expect=2, contains=["DOCTYPE declaration"])
    md = fx / "plain.md"
    md.write_text("# Plain\n\n## Purpose\n\nText.\n\n## 1. Scope\n\nText.\n", encoding="utf-8")
    step("markdown: unnumbered headings are reported", render + [str(md), "--root", str(fx / "out"), "--dry-run"], contains=["1 of 2 headings have no number; specifications cite sections by number ('Purpose')"])
    step("markdown: the sample renders with every heading numbered", [PY, "scripts/render_ground_truth.py", f"{SAMPLE}/ground-truth/architecture.md", "--root", SAMPLE, "--version", "0.3", "--dry-run"], absent=("Traceback", "have no number"))
    plain = fx / "company-rules.txt"
    plain.write_text("Never log a secret.\nRetain audit records for seven years.\n", encoding="utf-8")
    step("plain text: content is rendered as one numbered source section", render + [str(plain), "--root", str(fx / "out"), "--version", "1"],
         files={out / "company-rules.md": ["## 1 Source text", "Never log a secret.", "Retain audit records for seven years."]})
    extracted = fx / "extracted.md"
    extracted.write_text("# Policy image\n\n## 1 Rule\n\nUse the approved control.\n", encoding="utf-8")
    step("reviewed extraction: generated header records the original source", render + [str(extracted), "--root", str(fx / "out"), "--name", "policy-image", "--source-label", "docs/source/policy.png", "--version", "2"],
         files={out / "policy-image.md": ['Generated from "docs/source/policy.png" version 2']})


def citations(tmp):
    """The checker checks section citations, and says so when it cannot."""
    proj = tmp / "citations"
    shutil.copytree(ROOT / SAMPLE, proj)
    spec = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("| Ground truth | Sections 3.1, 3.2, 5.1, 7.1 |", "| Ground truth | Sections 3.1, 9.9 |"), encoding="utf-8")
    chk = [PY, "scripts/check_specs.py", "--root", str(proj)]
    step("a specification citing a section that does not exist fails", chk, expect=1, contains=["Ground truth cites section 9.9, which is not a heading in the rendered document"])
    gt = proj / "docs/ground-truth/architecture.md"
    import re
    gt.write_text(re.sub(r"(?m)^(#{2,6}) \d+(?:\.\d+)*\.? ", r"\1 ", gt.read_text(encoding="utf-8")), encoding="utf-8")
    step("an unnumbered ground truth is reported, not passed", chk, expect=1, contains=["ground truth citations not checked: the rendered document has no numbered headings"])
    gt.unlink()
    step("a missing ground truth is reported, not passed", chk, expect=1, contains=["ground truth citations not checked: the rendered document docs/ground-truth/architecture.md was not found"])

    multi = tmp / "multiple-sources"
    shutil.copytree(ROOT / SAMPLE, multi)
    gov = multi / "docs/ground-truth/governance.md"
    gov.write_text("# Company governance\n\n## 1 Security\n\nNever log secrets.\n\n## 2 Accessibility\n\nMeet the company standard.\n", encoding="utf-8")
    (multi / "docs/source").mkdir()
    (multi / "docs/source/governance.pdf").write_bytes(b"reviewed fixture")
    (gov.parent / "governance.index.txt").write_text("3:## 1 Security\n7:## 2 Accessibility\n", encoding="utf-8")
    plan = multi / "docs/spec/plan.yaml"
    body = plan.read_text(encoding="utf-8")
    body = body.replace('    use: "Full specification. Section numbers in the work item files refer to it."',
                        '    use: "Full specification. Section numbers in the work item files refer to it."\n'
                        '  - id: governance\n    name: "Company governance"\n    source_path: docs/source/governance.pdf\n'
                        '    path: docs/ground-truth/governance.md\n    version: "1"\n    status: reviewed\n    limit: ""\n'
                        '    use: "Company rules."')
    body = body.replace('    ground_truth: "Sections 3.1, 3.2, 5.1, 7.1"',
                        '    source_refs:\n      - source: architecture\n        sections: "3.1, 3.2, 5.1, 7.1"\n'
                        '      - source: governance\n        sections: "1, 2"')
    plan.write_text(body, encoding="utf-8")
    step("multiple sources: refresh writes source-specific citations", [PY, "scripts/scaffold_spec.py", "--root", str(multi), "--refresh-headers", "--apply", "--allow-no-git"],
         files={multi / "docs/spec/m1-submit-report/wi-01-service-scaffold.md": ["Architecture document: Sections 3.1, 3.2, 5.1, 7.1; Company governance: Sections 1, 2"]})
    step("multiple sources: citations validate against their named rendering", [PY, "scripts/check_specs.py", "--root", str(multi)], contains=["15 files clean, 0 with findings"])
    bad = plan.read_text(encoding="utf-8").replace('        sections: "1, 2"', '        sections: "1, 9.9"')
    plan.write_text(bad, encoding="utf-8")
    spec = multi / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("Company governance: Sections 1, 2", "Company governance: Sections 1, 9.9"), encoding="utf-8")
    step("multiple sources: a citation is checked only against its named source", [PY, "scripts/check_specs.py", "--root", str(multi)], expect=1,
         contains=["Ground truth cites Company governance section 9.9, which is not a heading in docs/ground-truth/governance.md"])

    partial = tmp / "partial-sources"
    shutil.copytree(ROOT / SAMPLE, partial)
    pplan = partial / "docs/spec/plan.yaml"
    (partial / "docs/source").mkdir()
    (partial / "docs/source/regional.png").write_bytes(b"unreadable fixture")
    pbody = pplan.read_text(encoding="utf-8").replace('    use: "Full specification. Section numbers in the work item files refer to it."',
        '    use: "Full specification. Section numbers in the work item files refer to it."\n'
        '  - id: regional-addendum\n    name: "Regional addendum"\n    source_path: docs/source/regional.png\n'
        '    version: "unknown"\n    status: unreadable\n    limit: "Image text could not be read reliably."\n    use: "Regional exceptions."')
    pplan.write_text(pbody, encoding="utf-8")
    step("an unreadable source is recorded while readable sources continue", [PY, "scripts/check_specs.py", "--root", str(partial)], contains=["15 files clean, 0 with findings"])

    none = tmp / "no-readable-sources"
    shutil.copytree(partial, none)
    nplan = none / "docs/spec/plan.yaml"
    nbody = nplan.read_text(encoding="utf-8").replace("    status: reviewed", "    status: unreadable", 1)
    nbody = nbody.replace('    limit: ""', '    limit: "The source could not be processed."', 1)
    nplan.write_text(nbody, encoding="utf-8")
    step("processing stops when no ground-truth source is readable", [PY, "scripts/check_specs.py", "--root", str(none)], expect=1,
         contains=["sources must include at least one reviewed entry. Continue with every readable source, but stop when none can be processed"])


def error_paths(tmp, plan_text):
    """Common mistakes give one line each and never a traceback (every step checks for "Traceback")."""
    d = tmp / "errors"
    d.mkdir()

    def variant(name, text, bom=False):
        path = d / f"{name}.yaml"
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
        return str(path)
    chk = [PY, "scripts/check_specs.py", "--root", SAMPLE]
    bad = {
        "unknown milestone": (plan_text.replace("    milestone: 5\n", "    milestone: 7\n"), "item 11: unknown milestone 7"),
        "non-ISO date": (plan_text.replace("complete_by: 2027-02-19", "complete_by: 24 Feb 2027"), "complete_by is not a date: '24 Feb 2027'"),
        "short date": (plan_text.replace("complete_by: 2027-02-19", "complete_by: 2027-2-24"), "complete_by is not a date: '2027-2-24'"),
        "impossible date": (plan_text.replace("complete_by: 2027-02-19", "complete_by: 2027-02-30"), "complete_by is not a date: '2027-02-30'"),
        "allocation 60%": (plan_text.replace("allocation: 60", 'allocation: "60%"'), "idris allocation must be a whole percent from 1 to 100, got '60%'"),
        "allocation full": (plan_text.replace("allocation: 60", "allocation: full"), "idris allocation must be a whole percent from 1 to 100, got 'full'"),
        "weekend start": (plan_text.replace("    start: 2027-02-01\n    days_off: [2027-02-22]", "    start: 2027-01-31\n    days_off: [2027-02-22]"), "tamsin start 2027-01-31 is a weekend"),
        "weekend day off": (plan_text.replace("days_off: [2027-03-08]", "days_off: [2027-03-06]"), "idris day off 2027-03-06 is a weekend"),
        "quote inside a quoted value": (plan_text.replace('name: "Expense approvals"', 'name: "Expense "approvals""'), "bad double-quoted value"),
    }
    for label, (text, want) in bad.items():
        v = variant(label.replace(" ", "-").replace("%", "pct"), text)
        unreadable = label.startswith("quote")   # a plan that cannot be read is a plan error, exit 2
        step(f"plan with {label}: one line, no traceback", chk + ["--plan", v], expect=2 if unreadable else 1, contains=[want])
        step(f"plan with {label}: --report says so first", chk + ["--plan", v, "--report"], expect=2 if unreadable else 1,
             contains=[want] if unreadable else ["plan.yaml has problems:", want])
    step("plan with a byte order mark is read", chk + ["--plan", variant("bom", plan_text, bom=True)], contains=["0 with findings"])
    named = plan_text.replace('name: "Expense approvals"', 'name: "Expense approvals \u2264 \u2192 \u4e2d"')
    step("a console that cannot show a character does not crash (cp1252)", chk + ["--plan", variant("enc", named), "--report"],
         env={"PYTHONIOENCODING": "cp1252"}, contains=["Plan: Expense approvals"], absent=("Traceback", "UnicodeEncodeError"))
    # --init with a quoted name, in a folder outside git
    proj = d / "fresh"
    proj.mkdir()
    in_git = any((x / ".git").exists() for x in [proj.resolve(), *proj.resolve().parents])
    scaffold = [PY, "scripts/scaffold_spec.py", "--root", str(proj)]
    if not in_git:
        step("dry run outside git refuses like --apply", scaffold + ["--init", "--name", "X"], expect=2, contains=["not inside a git repository, so nothing would be written"])
    step("--init quotes the name and lists the placeholders", scaffold + ["--init", "--name", 'Acme "Pay": phase 2 #core', "--apply", "--allow-no-git"],
         contains=["Placeholders still to fill in plan.yaml:", "project.repo is still your-org/your-repo", "project.dev_skill is acme-pay-phase-2-core-dev"],
         files={proj / "docs/spec/plan.yaml": ['name: "Acme \\"Pay\\": phase 2 #core"', "slug: acme-pay-phase-2-core", "dev_skill_path: docs/dev/skills/acme-pay-phase-2-core-dev"]})
    step("the plan written by --init reads back", [PY, "scripts/check_specs.py", "--root", str(proj), "--report"], contains=['Plan: Acme "Pay": phase 2 #core'])
    step("the dry run counts the stubs --stubs would add", scaffold + ["--allow-no-git"], contains=["2 specification stub(s) do not exist yet. Add --stubs to include them."])
    step("scaffold writes stubs", scaffold + ["--allow-no-git", "--apply", "--stubs"], contains=["file(s) written"])
    plan_path = proj / "docs/spec/plan.yaml"
    plan_path.write_text(plan_path.read_text(encoding="utf-8").replace("complete_by: 2027-01-06", "complete_by: 2027-01-09"), encoding="utf-8")
    step("plan findings come before unfinished stubs, one line per stub", [PY, "scripts/check_specs.py", "--root", str(proj)], expect=1,
         contains=["file(s) still hold template text (TODO)", "other finding(s) that usually go when the template text is replaced"],
         order=["plan.yaml:", "complete_by 2027-01-09 is a weekend", "unfinished template text (TODO)"])


def maintenance(tmp):
    """--refresh-headers follows plan.yaml and keeps what a person wrote."""
    proj = tmp / "maintenance"
    shutil.copytree(ROOT / SAMPLE, proj)
    plan = proj / "docs/spec/plan.yaml"
    text = plan.read_text(encoding="utf-8")
    text = text.replace('    size: "Medium, about 3 days"\n    depends: []\n', "    depends: []\n")      # WI-01 loses its size in the plan
    text = text.replace("complete_by: 2027-02-19", "complete_by: 2027-02-18")                               # WI-03 moves a day
    plan.write_text(text, encoding="utf-8")
    ms3 = proj / "docs/spec/m3-enforce-policy/milestone.md"
    custom = "| Demonstration | 2027-03-19, the engineers with the finance advisor, in the review room. |"
    t = ms3.read_text(encoding="utf-8")
    import re
    ms3.write_text(re.sub(r"(?m)^\| Demonstration \|.*$", custom, t), encoding="utf-8")
    wi1 = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
    wi1.write_text(re.sub(r"(?m)^(\| Ground truth \|.*)$", r"\1\n| Reviewer | Security review booked |", wi1.read_text(encoding="utf-8")), encoding="utf-8")
    run = [PY, "scripts/scaffold_spec.py", "--root", str(proj), "--refresh-headers", "--apply", "--allow-no-git"]
    step("--refresh-headers follows the plan and counts what it wrote", run, contains=["refresh header: docs/spec/m2-route-to-approvers/wi-03-routing-engine.md",
         "refresh header: docs/spec/m2-route-to-approvers/milestone.md", "refresh tables: docs/spec/README.md", "3 file(s) written"],
         files={proj / "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md": ["Complete by 2027-02-18"],
                proj / "docs/spec/README.md": ["| 2027-02-18 |"]})
    step("--refresh-headers keeps a filled Size row, an added row and a custom demonstration", [PY, "scripts/check_specs.py", "--root", str(proj), "--quiet"],
         files={wi1: ["| Size | Medium, about 3 days |", "| Reviewer | Security review booked |"], ms3: [custom]})
    step("--refresh-headers is stable on a second run", run, contains=["0 file(s) written"])
    legacy = tmp / "legacy-header"
    shutil.copytree(ROOT / SAMPLE, legacy)
    wi3 = legacy / "docs/spec/m2-route-to-approvers/wi-03-routing-engine.md"
    wi3.write_text(wi3.read_text(encoding="utf-8").replace("| Field | Value |\n", "| | |\n", 1), encoding="utf-8")
    step("a header table with the older blank header row passes the checker", [PY, "scripts/check_specs.py", "--root", str(legacy)], contains=["0 with findings"])
    step("--refresh-headers gives the older header table its Field and Value header row",
         [PY, "scripts/scaffold_spec.py", "--root", str(legacy), "--refresh-headers", "--apply", "--allow-no-git"], contains=["1 file(s) written"],
         files={wi3: ["# WI-03 Approval routing engine\n\n| Field | Value |\n| --- | --- |\n| Milestone |"]})


def composition(tmp, plan_text):
    """The sections written from the plan's rationale follow plan.yaml and leave hand edits alone."""
    proj = tmp / "composition"
    shutil.copytree(ROOT / SAMPLE, proj)
    plan = proj / "docs/spec/plan.yaml"
    old = 'rationale: "Routing and the inbox are the two halves of one capability'
    plan.write_text(plan_text.replace(old, 'rationale: "Changed reason for milestone two. Routing and the inbox are the two halves of one capability'), encoding="utf-8")
    import re
    ms2 = proj / "docs/spec/m2-route-to-approvers/milestone.md"
    ms2.write_text(ms2.read_text(encoding="utf-8").replace("## Expected outcomes\n", "## Expected outcomes\n\n- A line a person added by hand.\n", 1), encoding="utf-8")
    ms3 = proj / "docs/spec/m3-enforce-policy/milestone.md"
    t = ms3.read_text(encoding="utf-8")
    for head in ("Why these items form this milestone", "Joint demonstration"):
        t = re.sub(r"(?ms)^## " + head + r"\n.*?(?=^## )", "", t)
    ms3.write_text(t, encoding="utf-8")
    readme = proj / "docs/spec/README.md"
    r = readme.read_text(encoding="utf-8")
    readme.write_text(re.sub(r"(?ms)^## How this plan was composed\n.*?(?=^## )", "", r), encoding="utf-8")
    run = [PY, "scripts/scaffold_spec.py", "--root", str(proj), "--refresh-headers", "--apply", "--allow-no-git"]
    step("--refresh-headers rewrites the rationale sections and adds missing ones", run,
         contains=["refresh header: docs/spec/m2-route-to-approvers/milestone.md", "refresh header: docs/spec/m3-enforce-policy/milestone.md", "refresh tables: docs/spec/README.md", "3 file(s) written"],
         files={ms2: ["Changed reason for milestone two.", "- A line a person added by hand."],
                ms3: ["## Why these items form this milestone\n", "## Joint demonstration\n", "- Workflow: WI-06 (expense service), WI-07 (expense service)."],
                readme: ["## How this plan was composed\n", "Changed reason for milestone two.", "| Workflow | WI-01, WI-03, WI-06, WI-07, WI-09 |"]})
    order = ("import sys; t = open(sys.argv[1], encoding='utf-8').read(); "
             "o = [t.index(h) for h in ('## Purpose', '## Why these items', '## Expected outcomes', '## Joint demonstration', '## Demonstration expectations')]; "
             "r = open(sys.argv[2], encoding='utf-8').read(); sys.exit(0 if o == sorted(o) and r.index('## How this plan') < r.index('## Schedule') else 1)")
    step("the added sections sit in the template order", [PY, "-c", order, str(ms3), str(readme)])
    step("the refreshed sample still checks clean", [PY, "scripts/check_specs.py", "--root", str(proj), "--quiet"])
    step("the rationale refresh is stable on a second run", run, contains=["0 file(s) written"])


def planning_review(chk, variant, plan_text):
    """The planning review in the checker and in --report."""
    import re
    step("the sample's planning review is clean and shows each part", chk + ["--report"],
         contains=["Planning review", "Milestone 1, Submit an expense report: Workflow (WI-01), Experience (WI-02).", "The joint check on 2027-02-12 names Workflow and Experience.",
                   "Milestone 4, Pilot with one team: Workflow (WI-09) only.", "tamsin: 1 switch, 0 inside a milestone.", "WI-07 (expense service) to WI-09 (export job), across milestones 3 and 4.",
                   "Every item completes before its checkpoint.", "WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11: tamsin (WI-01), idris (WI-02, WI-04, WI-08, WI-11).",
                   "Highest to lowest is 1.3 to 1", "0 finding(s)."])
    one_track = re.sub(r"(?m)^    single_track_reason: .*Pilot.*\n|^    single_track_reason: \"The pilot.*\n", "", plan_text, count=1)
    step("a milestone covering one track without a reason fails", chk + ["--plan", variant("onetrack", one_track)], expect=1,
         contains=["planning review:", "milestone 4 covers one track (Workflow) and has no single_track_reason"])
    no_why = re.sub(r"(?m)^    rationale: \"Routing and the inbox.*\n", "", plan_text)
    no_why = re.sub(r"(?m)^    order_rationale: \"The scaffold.*\n", "", no_why)
    no_why = re.sub(r"(?m)^    joint_demonstration: \"The Experience engineer walks.*\n", "", no_why)
    step("missing rationale, joint demonstration and order rationale fail", chk + ["--plan", variant("nowhy", no_why)], expect=1,
         contains=["milestone 2 has no rationale", "milestone 4 has no joint_demonstration", "track workflow has no order_rationale"])
    step("the report marks the same lines as findings and still exits 0", chk + ["--report", "--plan", variant("nowhyreport", no_why)],
         contains=["finding: milestone 2 has no rationale", "3 finding(s). Run the checker without --report to fail on them."])
    late = plan_text.replace("    complete_by: 2027-02-10\n", "    complete_by: 2027-02-12\n")
    step("a zero-slack item is reported", chk + ["--report", "--plan", variant("noslack", late)],
         contains=["WI-02 completes on its checkpoint date 2027-02-12: no slack."], absent=("Traceback", "Every item completes before its checkpoint."))
    step("a zero-slack item is advice, not a finding", chk + ["--plan", variant("noslackcheck", late)], expect=1,
         contains=["Target row is"], absent=("Traceback", "planning review:"))   # the only finding is the stale header of WI-02
    themed = plan_text.replace('    slug: limits-and-duties\n', '    slug: limits-and-duties\n', 1)
    i = themed.index("    slug: limits-and-duties\n")
    themed = themed[:i] + themed[i:].replace('    theme: "expense service"\n', '    theme: "rules module"\n', 1)
    step("theme switches are counted per owner", chk + ["--report", "--plan", variant("themes", themed)],
         contains=["tamsin: 3 switches, 1 inside a milestone.", "WI-06 (rules module) to WI-07 (expense service), inside milestone 3."])
    no_themes = re.sub(r"(?m)^    theme: .*\n", "", plan_text)
    step("without themes the report says how to add them", chk + ["--report", "--plan", variant("nothemes", no_themes)],
         contains=["No item has a theme. Add theme to the items to count the switches."])
    solo = plan_text.replace("    track: experience\n    owner: idris\n", "    track: workflow\n    owner: tamsin\n")
    step("a critical path owned by one person is reported", chk + ["--report", "--plan", variant("solo", solo)],
         contains=["The critical path runs through one person, tamsin, on the Workflow track.", "idris has no sized work, so the ratio is not defined."])
    step("a load ratio above two to one is reported", chk + ["--report", "--plan", variant("ratio", plan_text.replace("allocation: 60", "allocation: 20"))],
         contains=["Highest to lowest is 3.9 to 1 (idris to tamsin). Above two to one"])
    step("a joint check that does not name a track is reported", chk + ["--report", "--plan", variant("unnamed", plan_text.replace(" Experience drives the form and Workflow shows the database.", ""))],
         contains=["The joint check on 2027-02-12 does not name Workflow or Experience."])
    step("a rationale that is not text is a plan problem", chk + ["--plan", variant("notext", plan_text.replace('    theme: "release"\n', "    theme: [release]\n"))], expect=1,
         contains=["item 11: theme must be text"])


def frontmatter(tmp, plan_text):
    """The generated SKILL.md frontmatter parses whatever the project is called."""
    proj = tmp / "frontmatter"
    shutil.copytree(ROOT / SAMPLE, proj, ignore=shutil.ignore_patterns("dev"))
    plan = proj / "docs/spec/plan.yaml"
    gen = [PY, "scripts/generate_dev_skill.py", "--root", str(proj)]
    plan.write_text(plan_text.replace('name: "Expense approvals"', 'name: "Payments: phase 2 #core"'), encoding="utf-8")
    step("a project name with ': ' and ' #' gives a quoted description", gen + ["--apply"], contains=["description length: 254 characters"])
    code = ("import json, re, sys; t = open(sys.argv[1], encoding='utf-8').read(); "
            "m = re.search(r'(?m)^description: (.*)$', t); d = json.loads(m.group(1)); "
            "assert d.startswith('Orients on one Payments: phase 2 #core work item'), d; "
            "assert 'a work item id such as WI-01,' in d and 'WI-11' not in d and 'wi-01-service-scaffold' in d and 'docs/spec/' in d, d; print('parsed', len(d))")
    step("the description is a valid quoted scalar", [PY, "-c", code, str(proj / "docs/dev/skills/expense-approvals-dev/SKILL.md")], contains=["parsed 254"])
    skill = proj / "docs/dev/skills/expense-approvals-dev"
    step("generated text names the engineers, not developers", [PY, "-c", "print('ok')"],
         files={skill / "SKILL.md": ["the engineer checks and posts it"], skill / "references/work-items.md": ["not by the engineers"]})
    once = ("import sys; t = open(sys.argv[1], encoding='utf-8').read(); "
            "n = {k: t.count(k) for k in ('`npm test`', '`npm run lint`', '`EXPENSE_APPROVALS_ENABLED`', 'npm run test:contract')}; "
            "print(n); sys.exit(0 if set(n.values()) == {1} and 'developers' not in t else 1)")
    step("the generated skill states each command and the flag once", [PY, "-c", once, str(skill / "SKILL.md")])
    plan.write_text(plan_text.replace("dev_skill_path: docs/dev/skills/expense-approvals-dev", "dev_skill_path: docs/dev/skills/other-name"), encoding="utf-8")
    step("the skill folder must match the skill name", gen, expect=2, contains=["must equal project.dev_skill"])
    long_name = "a" + "-b" * 40
    plan.write_text(plan_text.replace("expense-approvals-dev", long_name), encoding="utf-8")
    step("a skill name over 64 characters is refused", gen, expect=2, contains=["at most 64"])
    plan.write_text(plan_text.replace('name: "Expense approvals"', 'name: "' + "Very long project name " * 4 + '"'), encoding="utf-8")
    step("a description over 300 characters is flagged", gen, contains=["warning: the description is over 300 characters"])


def path_safety(tmp, plan_text):
    """Nothing is copied or written outside the folders it belongs in."""
    d = tmp / "paths"
    (d / "doc/img").mkdir(parents=True)
    (d / "secret.txt").write_text("not for the repository", encoding="utf-8")
    (d / "doc/img/ok.png").write_bytes(b"\x89PNG\r\n")
    (d / "doc/notes.txt").write_text("text", encoding="utf-8")
    md = d / "doc/design.md"
    md.write_text("# Design\n\n## 1. Figures\n\n![ok](img/ok.png)\n\n![up](../secret.txt)\n\n"
                  f"![abs]({(d / 'secret.txt').resolve()})\n\n![text](notes.txt)\n", encoding="utf-8")
    out = d / "out"
    out.mkdir()
    step("images outside the document folder, or not images, are not copied",
         [PY, "scripts/render_ground_truth.py", str(md), "--root", str(out)],
         contains=["not copied (outside the document folder or not an image): ../secret.txt", "not copied (outside the document folder or not an image): notes.txt", "1 figures"])
    figs = sorted(x.name for x in (out / "docs/ground-truth/figures/design").iterdir())
    ok = figs == ["ok.png"]
    results.append((ok, "only the image inside the document folder was copied"))
    print(("PASS " if ok else "FAIL ") + "only the image inside the document folder was copied" + ("" if ok else f" (found {figs})"))
    step("--out-dir outside the project is refused", [PY, "scripts/render_ground_truth.py", str(md), "--root", str(out), "--out-dir", "../elsewhere"], expect=2, contains=["outside the project folder"])
    gt = d / "gt"
    (gt / "docs/ground-truth").mkdir(parents=True)
    kept = gt / "docs/ground-truth/architecture.md"
    shutil.copy(ROOT / SAMPLE / "ground-truth/architecture.md", kept)
    before = kept.read_bytes()
    step("a source inside docs/ground-truth is refused and left as it was",
         [PY, "scripts/render_ground_truth.py", str(kept), "--root", str(gt), "--version", "1"], expect=2,
         contains=["would overwrite the source", "Keep the source in docs/source/", "Nothing was written."])
    ok = kept.read_bytes() == before and not (gt / "docs/ground-truth/architecture.index.txt").exists()
    results.append((ok, "the refused source is unchanged and no index was written"))
    print(("PASS " if ok else "FAIL ") + "the refused source is unchanged and no index was written")
    proj = d / "proj"
    shutil.copytree(ROOT / SAMPLE, proj)
    plan = proj / "docs/spec/plan.yaml"
    plan.write_text(plan_text.replace("folder: m4-pilot", "folder: ../../../m4-pilot"), encoding="utf-8")
    step("a milestone folder outside the project is refused", [PY, "scripts/scaffold_spec.py", "--root", str(proj), "--allow-no-git"], expect=2, contains=["outside the project folder"])
    plan.write_text(plan_text.replace("dev_skill_path: docs/dev/skills/expense-approvals-dev", "dev_skill_path: ../../expense-approvals-dev"), encoding="utf-8")
    step("the engineers' skill path outside the project is refused", [PY, "scripts/generate_dev_skill.py", "--root", str(proj)], expect=2, contains=["outside the project folder"])
    leaked = [x for x in (d.parent.iterdir()) if x.name in ("m4-pilot", "expense-approvals-dev", "elsewhere")]
    results.append((not leaked, "nothing was written outside the project"))
    print(("PASS " if not leaked else "FAIL ") + "nothing was written outside the project")


def names(tmp, plan_text):
    """Names come from the plan; ordinary words that happen to be names are not findings."""
    proj = tmp / "names"
    shutil.copytree(ROOT / SAMPLE, proj)
    plan = proj / "docs/spec/plan.yaml"
    plan.write_text(plan_text.replace("Tamsin Hale", "Will Long").replace("tamsin", "will"), encoding="utf-8")
    chk = [PY, "scripts/check_specs.py", "--root", str(proj)]
    step("a person named Will Long does not flag the words will and long", chk, contains=["0 with findings"])
    spec = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nLong reviewed this with idris.\n", encoding="utf-8")
    step("a capitalized name part and a handle are still flagged", chk, expect=1,
         contains=["person name or handle from the plan at line", "Long reviewed this with idris."])


def lint_spelling(tmp):
    """The prose lint flags British spellings and leaves real words that end in -ise alone. The words are built
    from parts so that this file does not spell them."""
    d = tmp / "lint"
    d.mkdir()
    bad, good = d / "british.md", d / "us.md"
    bad.write_text("The organi" + "sation changed its behavio" + "ur. We author" + "ise it and label" + "led it. Restart it afterward" + "s.\n", encoding="utf-8")
    good.write_text("The organization changed its behavior. We authorize it and labeled it. Restart it afterward. Advise, promise, exercise, enterprise, otherwise.\n", encoding="utf-8")
    lint = [PY, "scripts/lint_prose.py"]
    step("lint: British spellings are flagged", lint + [str(bad)], expect=1, contains=["British spelling, use US English (organi" + "sation)", "(behavio" + "ur)", "(author" + "ise)", "(label" + "led)", "(afterward" + "s)"])
    step("lint: US spellings and real -ise words are clean", lint + [str(good)], contains=["0 findings"])


def regressions(tmp, plan_text):
    """The defects found by the code-path release test stay fixed. Every step checks that no
    traceback appears, and every step has a time limit, so a hang fails."""
    d = tmp / "regressions"
    d.mkdir()
    chk, gen = [PY, "scripts/check_specs.py"], [PY, "scripts/generate_dev_skill.py"]
    scaffold, sync, board = [PY, "scripts/scaffold_spec.py"], [PY, "scripts/github_sync.py"], [PY, "scripts/github_project.py"]
    render = [PY, "scripts/render_ground_truth.py"]

    def project(name, plan=None):
        proj = d / name
        shutil.copytree(ROOT / SAMPLE, proj)
        if plan is not None:
            (proj / "docs/spec/plan.yaml").write_text(plan, encoding="utf-8")
        return proj

    def every_script(label, proj, want, expect="nonzero", extra=()):
        want = [want] if isinstance(want, str) else list(want)
        root = ["--root", str(proj)] + list(extra)
        step(f"{label}: check_specs", chk + root, expect=expect, contains=want, timeout=60)
        step(f"{label}: check_specs --report", chk + root + ["--report"], expect=expect, contains=want, timeout=60)
        step(f"{label}: check_specs --json", chk + root + ["--json"], expect=expect, contains=want, timeout=60, json_out=True)
        step(f"{label}: scaffold_spec", scaffold + root + ["--allow-no-git"], expect="nonzero", contains=want, timeout=60)
        step(f"{label}: generate_dev_skill", gen + root, expect="nonzero", contains=want, timeout=60)
        step(f"{label}: github_sync --offline", sync + root + ["--offline"], expect="nonzero", contains=want, timeout=60)
        step(f"{label}: github_project --offline", board + root + ["--offline"], expect="nonzero", contains=want, timeout=60)
    regressions.every_script = every_script
    regressions.project = project

    # an item that depends on itself, and a duplicate id, used to loop forever in the checker
    every_script("an item that depends on itself", project("selfdep", plan_text.replace(
        "    depends: [1]\n    checkpoint: 2027-02-26", "    depends: [1, 3]\n    checkpoint: 2027-02-26")), "item 3: depends on itself", expect=1)
    every_script("a duplicate item id", project("dupid", plan_text.replace("  - id: 4\n", "  - id: 3\n")), "item 3: duplicate id", expect=1)

    # plan values of the wrong type stop every script with one line
    wrong = [
        ("a track given as a list", "    track: workflow\n    owner: tamsin\n", "    track: [workflow]\n    owner: tamsin\n", "track must be text"),
        ("days_off given as a number", "days_off: [2027-02-22]", "days_off: 5", "days_off must be a list of dates"),
        ("an advisor given as plain text", '  - name: "Noor Castellan"\n    note: "Finance policy advisor. Reviews the rules and the export format."\n',
         '  - "Noor Castellan"\n', "advisors: entry 1 must be a mapping"),
        ("an item id that is a word", "  - id: 4\n", "  - id: four\n", "id must be a whole number"),
        ("depends given as a number", "    depends: [2, 3]\n", "    depends: 5\n", "depends must be a list of item ids"),
        ("a label given as a mapping", 'label: "Audit log and retention"', "label: {a: b}", "label must be text"),
        ("tracks given as text", "tracks:\n  - id: workflow", "tracks: workflow\nold_tracks:\n  - id: workflow", "tracks must be a list"),
        ("a banned pattern that is not a pattern", "limits:\n", 'banned:\n  words: ["(sprint"]\nlimits:\n', "is not a valid pattern"),
        ("an empty spec_dir", "  spec_dir: docs/spec\n", '  spec_dir: ""\n', "project.spec_dir is empty"),
        ("a spec_dir outside the project", "  spec_dir: docs/spec\n", "  spec_dir: ../outside\n", "must be a path inside the project"),
        ("a target of 99999999 weeks", "  date: 2027-04-23\n", "  weeks: 99999999\n", "weeks must be a whole number of working weeks"),
        ("a size of 99999999 days", 'size: "Large, about 5 days"', 'size: "Large, about 99999999 days"', "Split the item"),
        ("spec_lines given as text", "spec_lines: [80, 340]", "spec_lines: many", "limits.spec_lines must be two whole numbers"),
        ("an item without an id", "  - id: 2\n", "  - id:\n", "items: id must be an integer"),
        ("a break start that is not a date", "    start: 2027-03-22\n", "    start: zzz\n", "start is not a date (use YYYY-MM-DD): 'zzz'"),
    ]
    for i, (label, old, new, want) in enumerate(wrong):
        assert old in plan_text, label
        every_script(f"plan with {label}", project(f"wrong{i}", plan_text.replace(old, new, 1)), want)

    # files that are not UTF-8 give one line, and the checker reports them as findings
    latin = project("latin")
    spec = latin / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
    spec.write_bytes(spec.read_bytes().replace(b"Service scaffold", b"Service caf\xe9 scaffold", 1))
    root = ["--root", str(latin)]
    step("a specification that is not UTF-8 is a finding", chk + root, expect=1, contains=["cannot read:", "is not UTF-8 text"], timeout=60)
    step("a specification that is not UTF-8: --json stays JSON", chk + root + ["--json", "--item", "1"], expect=1, contains=["is not UTF-8 text"], json_out=True, timeout=60)
    step("a specification that is not UTF-8: --show-body is one line", sync + root + ["--offline", "--show-body", "1"], expect=1, contains=["error:", "is not UTF-8 text"])
    step("a specification that is not UTF-8: the skill generator is one line", gen + root, expect=1, contains=["error:", "is not UTF-8 text"])
    step("a specification that is not UTF-8: --refresh-headers is one line", scaffold + root + ["--refresh-headers", "--allow-no-git"], expect=1, contains=["error:", "is not UTF-8 text"])
    gt = project("latin-gt")
    (gt / "docs/ground-truth/architecture.md").write_bytes(b"# Archi\xe9\n")
    step("a ground truth that is not UTF-8 is reported by the checker", chk + ["--root", str(gt)], expect=1, contains=["ground truth citations not checked:", "is not UTF-8 text"])
    step("a ground truth that is not UTF-8: the skill generator is one line", gen + ["--root", str(gt)], expect=1, contains=["error:", "is not UTF-8 text"])
    bad_plan = project("latin-plan")
    (bad_plan / "docs/spec/plan.yaml").write_bytes(plan_text.encode("utf-8").replace(b"Expense approvals", b"Expense approv\xe9ls", 1))
    step("a plan that is not UTF-8: --json is JSON and exit 2", chk + ["--root", str(bad_plan), "--json"], expect=2, contains=["is not UTF-8 text"], json_out=True)
    for name, cmd in (("scaffold_spec", scaffold + ["--allow-no-git"]), ("generate_dev_skill", gen), ("github_sync --offline", sync + ["--offline"]), ("github_project --offline", board + ["--offline"])):
        step(f"a plan that is not UTF-8: {name} is one line", cmd + ["--root", str(bad_plan)], expect="nonzero", contains=["cannot read plan", "is not UTF-8 text"])
    src = d / "latin.md"
    src.write_bytes(b"# Caf\xe9\n")
    step("a Markdown source that is not UTF-8 is one line", render + [str(src), "--root", str(d), "--dry-run"], expect=2, contains=["is not UTF-8 text"])

    # check_specs: --item takes the tag, unknown and external ids are errors, --json is always JSON
    s = ["--root", SAMPLE]
    step("--item accepts 3, WI-03 and wi-3", chk + s + ["--item", "3", "--item", "WI-03", "--item", "wi-3"], contains=["1 files clean, 0 with findings (1 work items"])
    step("--item for an unknown id is an error", chk + s + ["--item", "99"], expect=2, contains=["there is no item 99 in the plan"])
    step("--item for an external item is an error", chk + s + ["--item", "WI-05", "--json"], expect=2, contains=["is an external item"], json_out=True)
    step("--report with --json is an error, as JSON", chk + s + ["--report", "--json"], expect=2, json_out=True)
    step("--json without a plan is JSON and exit 2", chk + ["--root", str(d), "--json"], expect=2, contains=["plan not found"], json_out=True)
    empty = d / "empty-plan.yaml"
    empty.write_text("", encoding="utf-8")
    step("--json with an empty plan is JSON and exit 2", chk + s + ["--plan", str(empty), "--json"], expect=2, json_out=True)
    cited = project("plan-cite", plan_text.replace('ground_truth: "Sections 3.1, 3.2, 5.1, 7.1"', 'ground_truth: "Sections 3.1, 9.9"'))
    step("a plan.yaml citation of a missing section is a finding", chk + ["--root", str(cited)], expect=1,
         contains=["plan.yaml ground_truth of this item cites section 9.9"])
    named = project("named")
    spec = named / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nReviewed by Tamsin Hale.\n", encoding="utf-8")
    code = ("import subprocess, sys; o = subprocess.run(sys.argv[1:], capture_output=True, text=True).stdout; "
            "n = o.count('person name or handle from the plan'); print('findings', n); sys.exit(0 if n == 1 else 1)")
    step("a full name in a specification is one finding, not one per part", [PY, "-c", code] + chk + ["--root", str(named)], contains=["findings 1"])

    # flags that cannot go together
    for script, cmd in (("github_sync", sync), ("github_project", board)):
        for flag in ("--apply", "--verify"):
            step(f"{script} --offline {flag} is refused", cmd + s + ["--offline", flag], expect=2, contains=["--offline cannot be combined with " + flag])
    step("github_sync --apply --verify is refused", sync + s + ["--apply", "--verify"], expect=2, contains=["separate runs"])
    step("github_project --apply --verify is refused", board + s + ["--apply", "--verify"], expect=2, contains=["separate runs"])
    step("an empty --name for --init is refused", scaffold + ["--root", str(d), "--init", "--name", " ", "--allow-no-git"], expect=2, contains=["--name is empty"])
    step("a --root that does not exist is refused", scaffold + ["--root", str(d / "nowhere")], expect=2, contains=["is not a folder"])
    ro = project("readonly")
    (ro / "docs/spec/README.md").unlink()
    (ro / "docs/spec").chmod(0o500)
    step("a folder that cannot be written gives one line", scaffold + ["--root", str(ro), "--apply", "--allow-no-git"], expect=2, contains=["error: cannot write"])
    (ro / "docs/spec").chmod(0o700)
    step("lint_prose on a path that does not exist is an error", [PY, "scripts/lint_prose.py", str(d / "nowhere.md")], expect=2, contains=["not a file"])
    step("the self test refuses an unknown argument", [PY, "scripts/selftest.py", "--bogus"], expect=2, contains=["unrecognized arguments"])

    # the renderer checks every output path before it writes anything
    doc = d / "render"
    (doc / "a").mkdir(parents=True)
    (doc / "b").mkdir()
    (doc / "img/i").mkdir(parents=True)
    (doc / "img/j").mkdir()
    (doc / "img/i/x.png").write_bytes(b"\x89PNG first")
    (doc / "img/j/x.png").write_bytes(b"\x89PNG second")
    page = doc / "img/page.md"
    page.write_text("# Page\n\n## 1. Figures\n\n![one](i/x.png)\n\n![two](j/x.png)\n", encoding="utf-8")
    for x in ("a", "b"):
        (doc / x / "notes.md").write_text("# Notes\n\n## 1. Part\n", encoding="utf-8")
    out = d / "render-out"
    out.mkdir()
    r = ["--root", str(out)]
    step("--name with a folder is refused before anything is written", render + [str(page)] + r + ["--name", "../evil"], expect=2, contains=["must be a plain file name"])
    step("--name a/b is refused", render + [str(page)] + r + ["--name", "a/b"], expect=2, contains=["must be a plain file name"])
    nothing = not (out / "docs").exists() and not (d / "evil").exists()
    results.append((nothing, "a refused --name wrote nothing"))
    print(("PASS " if nothing else "FAIL ") + "a refused --name wrote nothing")
    step("two inputs with the same name are refused", render + [str(doc / "a/notes.md"), str(doc / "b/notes.md")] + r, expect=2, contains=["would both render to notes.md"])
    step("two figures with the same file name are both kept", render + [str(page)] + r, contains=["2 figures"],
         files={out / "docs/ground-truth/page.md": ["(figures/page/x.png)", "(figures/page/x-2.png)"]})
    both = [(out / "docs/ground-truth/figures/page" / n).read_bytes() for n in ("x.png", "x-2.png") if (out / "docs/ground-truth/figures/page" / n).exists()]
    results.append((both == [b"\x89PNG first", b"\x89PNG second"], "each figure keeps its own image"))
    print(("PASS " if both == [b"\x89PNG first", b"\x89PNG second"] else "FAIL ") + "each figure keeps its own image")
    step("a --root that does not exist is refused, not created", render + [str(page), "--root", str(d / "missing-root")], expect=2, contains=["does not exist"])
    results.append((not (d / "missing-root").exists(), "the missing --root was not created"))
    print(("PASS " if not (d / "missing-root").exists() else "FAIL ") + "the missing --root was not created")
    step("an --out-dir that is a file is refused", render + [str(page)] + r + ["--out-dir", "docs/ground-truth/page.md"], expect=2, contains=["is a file, not a folder"])
    step("a folder as input is refused", render + [str(doc / "a")] + r, expect=2, contains=["is a folder, not a file"])
    step("a --date that is not a date is refused", render + [str(page)] + r + ["--date", "2026-13-45"], expect=2, contains=["is not a date"])
    step("--version with --> cannot end the header comment", render + [str(page)] + r + ["--version=-->x", "--name", "comment"],
         files={out / "docs/ground-truth/comment.md": ['version - ->x on']})
    fx = d / "docx"
    fx.mkdir()
    make = [PY, "tests/fixtures/make_numbered_docx.py"]
    for mode, want in (("malformed", "is not well-formed XML"), ("doctype-late", "contains a DOCTYPE declaration"),
                       ("doctype-utf16", "contains a DOCTYPE declaration"), ("entity-styles", "contains an ENTITY declaration")):
        subprocess.run(make + [str(fx / f"{mode}.docx"), mode], cwd=ROOT, env=ENV, check=True)
        step(f"docx: {mode} is refused with one line", render + [str(fx / f"{mode}.docx")] + r, expect=2, contains=[want, "Nothing was written."])
    subprocess.run(make + [str(fx / "nomedia.docx"), "nomedia"], cwd=ROOT, env=ENV, check=True)
    step("docx: a figure whose image part is missing is a note", render + [str(fx / "nomedia.docx")] + r + ["--dry-run"],
         contains=["figure 1 was not rendered: the document has no image part"])
    subprocess.run(make + [str(fx / "dupfigures.docx"), "dupfigures"], cwd=ROOT, env=ENV, check=True)
    step("docx: two figures with the same caption number keep both images", render + [str(fx / "dupfigures.docx")] + r,
         files={out / "docs/ground-truth/dupfigures.md": ["(figures/dupfigures/figure-1.png)", "(figures/dupfigures/figure-1-2.png)"]})


def round_two(tmp, plan_text):
    """The defects found in the second round of the code-path release test stay fixed."""
    d = tmp / "round2"
    d.mkdir()
    every_script, project = regressions.every_script, regressions.project
    chk, gen = [PY, "scripts/check_specs.py"], [PY, "scripts/generate_dev_skill.py"]
    scaffold, sync, board = [PY, "scripts/scaffold_spec.py"], [PY, "scripts/github_sync.py"], [PY, "scripts/github_project.py"]
    render, token = [PY, "scripts/render_ground_truth.py"], [PY, "scripts/github_token.py"]
    s = ["--root", SAMPLE]

    # the plan reader: a flow value cut short is a plan error with its line, an item with no id a plan problem
    for i, (label, old, new, want) in enumerate([
        ("a list cut short at the end of a line", "    depends: [1]\n    checkpoint: 2027-02-12", "    depends: [\n    checkpoint: 2027-02-12", ("cannot read plan", "unterminated list")),
        ("a map cut short at the end of a line", '    label: "Report form and receipt upload"', "    label: {", ("cannot read plan", "unterminated map")),
        ("a list cut short after a comma", "    depends: [1]\n    checkpoint: 2027-02-12", "    depends: [1,\n    checkpoint: 2027-02-12", ("cannot read plan", "bad flow collection")),
        ("an item with no id", "  - id: 2\n    slug: report-form", "  - slug: report-form", "items: id must be an integer"),
        ("a title format with an unknown field", 'title_format: "{id} {label}"', 'title_format: "{id} {nope}"', "project.title_format '{id} {nope}' uses {nope}"),
        ("a title format with a lone brace", 'title_format: "{id} {label}"', 'title_format: "{id"', "is not a valid title format"),
        ("a title format without the id", 'title_format: "{id} {label}"', 'title_format: "{label}"', "must hold {id} or {lower}"),
        ("a slug too long for a file name", "    slug: report-form\n", "    slug: " + "a" * 300 + "\n", "item 2: slug makes the file or folder name"),
        ("a milestone folder too long for a path", "    folder: m1-submit-report\n", "    folder: " + "/".join(["f" * 200] * 25) + "\n", "milestone 1: folder makes the path"),
        ("a number of 5000 digits", "    allocation: 60\n", "    allocation: " + "9" * 5000 + "\n", "allocation must be a whole percent"),
        ("an Epic number in other digits", "  epic: null\n", "  epic: \"\uff10\uff13\"\n", "project.epic must be an issue number"),
        ("a date in the year 9999", "    complete_by: 2027-02-10\n", "    complete_by: 9999-12-31\n", "complete_by is not a date"),
        ("a project slug with a comma", "  slug: expense-approvals\n", '  slug: "expense,approvals"\n', "project.slug must be lowercase words joined by hyphens"),
        ("a label with a line break", '    label: "Report form and receipt upload"', '    label: "Report form\\nand receipt upload"', "item 2: label must be one line"),
    ]):
        assert old in plan_text, label
        every_script(f"plan with {label}", project(f"r2-{i}", plan_text.replace(old, new, 1)), want)

    # files the scripts read must be regular files: a named pipe would wait, /dev/zero never ends
    if hasattr(os, "mkfifo"):
        fifo = d / "plan-fifo.yaml"
        os.mkfifo(str(fifo))
        for name, path in (("a named pipe", str(fifo)), ("/dev/zero", "/dev/zero"), ("/dev/null", "/dev/null")):
            if not Path(path).exists():
                continue
            p = ["--plan", path]
            step(f"--plan {name}: check_specs is one line", chk + s + p, expect=2, contains=["is not a regular file"], timeout=30)
            step(f"--plan {name}: check_specs --json is JSON", chk + s + p + ["--json"], expect=2, contains=["is not a regular file"], json_out=True, timeout=30)
            for label, cmd in (("scaffold_spec", scaffold + ["--allow-no-git"]), ("generate_dev_skill", gen), ("github_sync --offline", sync + ["--offline"]), ("github_project --offline", board + ["--offline"])):
                step(f"--plan {name}: {label} is one line", cmd + s + p, expect="nonzero", contains=["is not a regular file"], timeout=30)
        piped = project("r2-fifo-spec")
        spec = piped / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        spec.unlink()
        os.mkfifo(str(spec))
        root = ["--root", str(piped)]
        step("a specification that is a named pipe is a finding", chk + root, expect=1, contains=["cannot read:", "is not a regular file"], timeout=30)
        step("a specification that is a named pipe: --show-body is one line", sync + root + ["--offline", "--show-body", "1"], expect="nonzero", contains=["is not a regular file"], timeout=30)
        step("a specification that is a named pipe: the skill generator is one line", gen + root, expect="nonzero", contains=["is not a regular file"], timeout=30)
        step("a specification that is a named pipe: --refresh-headers is one line", scaffold + root + ["--refresh-headers", "--allow-no-git"], expect="nonzero", contains=["is not a regular file"], timeout=30)
        readme = piped / "docs/spec/README.md"
        readme.unlink()
        os.mkfifo(str(readme))
        step("--apply --force never writes into a named pipe", scaffold + root + ["--allow-no-git", "--apply", "--force"], expect="nonzero", contains=["is not a regular file"], timeout=30)
        gt = project("r2-fifo-gt")
        (gt / "docs/ground-truth/architecture.md").unlink()
        os.mkfifo(str(gt / "docs/ground-truth/architecture.md"))
        step("a ground truth that is a named pipe is reported by the checker", chk + ["--root", str(gt)], expect=1, contains=["ground truth citations not checked:", "is not a regular file"], timeout=30)
        src = d / "doc-fifo.md"
        os.mkfifo(str(src))
        out = d / "render-out"
        out.mkdir()
        step("a named pipe as a renderer input is one line", render + [str(src), "--root", str(out), "--dry-run"], expect=2, contains=["is not a regular file"], timeout=30)
        md = d / "doc.md"
        md.write_text("# Doc\n\n## 1. Part\n", encoding="utf-8")
        (out / "docs/ground-truth").mkdir(parents=True)
        os.mkfifo(str(out / "docs/ground-truth/doc.md"))
        step("a named pipe where the rendering goes is in the way", render + [str(md), "--root", str(out)], expect=2, contains=["is in the way", "pipe, socket or device"], timeout=30)
        step("--from-file with a named pipe is one line", token + ["--from-file", str(fifo)], expect=2, contains=["is not a regular file"], timeout=30)
        if Path("/dev/zero").exists():
            feed = "import subprocess, sys; sys.exit(subprocess.run(sys.argv[1:], stdin=open('/dev/zero', 'rb')).returncode)"
            step("--stdin from /dev/zero stops after a token's length", [PY, "-c", feed] + token + ["--stdin", "--token-file", str(d / "tok")], expect=2,
                 contains=["more than a token"], timeout=30)
    bad = d / "badnumbers.docx"
    subprocess.run([PY, "tests/fixtures/make_numbered_docx.py", str(bad), "badnumbers"], cwd=ROOT, env=ENV, check=True)
    step("docx: level numbers that are not ASCII digits do not stop the renderer", render + [str(bad), "--root", str(d), "--dry-run"],
         contains=["1 document(s) checked"], timeout=60)
    md = d / "plain.md"
    md.write_text("# Plain\n\n## 1. Part\n", encoding="utf-8")
    step("a --name too long for the file system is refused before anything is written", render + [str(md), "--root", str(d), "--name", "n" * 300], expect=2,
         contains=["longer than the"], timeout=30)
    step("an empty --out-dir is refused", render + [str(md), "--root", str(d), "--out-dir", ""], expect=2, contains=["--out-dir is empty"])
    step("an empty --root is refused by the renderer", render + [str(md), "--root", ""], expect=2, contains=["--root is empty"])

    # empty flags are errors, never a fall back to a default
    for label, cmd, want in (
        ("github_sync --repo ''", sync + s + ["--offline", "--repo", ""], "--repo is empty"),
        ("github_project --repo ''", board + s + ["--offline", "--repo", ""], "--repo is empty"),
        ("github_sync --show-body ''", sync + s + ["--offline", "--show-body", ""], "--show-body is empty"),
        ("github_sync --plan ''", sync + s + ["--offline", "--plan", ""], "--plan is empty"),
        ("github_sync --token-file ''", sync + s + ["--token-file", ""], "--token-file is empty"),
        ("github_sync --issue-type ''", sync + s + ["--offline", "--issue-type", ""], "--issue-type is empty"),
        ("github_project --owner ''", board + s + ["--offline", "--owner", ""], "--owner is empty"),
        ("github_project --title ''", board + s + ["--offline", "--title", ""], "--title is empty"),
        ("github_project --owner with a slash", board + s + ["--offline", "--owner", "a/b"], "is not a GitHub user or organization name"),
        ("scaffold_spec --root ''", scaffold + ["--root", ""], "--root is empty"),
        ("generate_dev_skill --plan ''", gen + s + ["--plan", ""], "--plan is empty"),
        ("github_token --from-file ''", token + ["--from-file", ""], "--from-file is empty"),
        ("github_token --repo ''", token + ["--check", "--repo", ""], "--repo is empty"),
        ("github_token --token-file ''", token + ["--check", "--token-file", ""], "--token-file is empty"),
        ("github_token --repo with ..", token + ["--check", "--repo", "../x"], "must look like owner/name"),
    ):
        step(f"{label} is an error", cmd, expect="nonzero", contains=[want], timeout=60)
    norepo = project("r2-norepo", plan_text.replace("  repo: sct-will/carrydown-sample\n", ""))
    step("--show-body without a repository says how to give one", sync + ["--root", str(norepo), "--offline", "--show-body", "3"], expect=2,
         contains=["--show-body needs the repository"])
    step("--show-body with --repo and no project.repo prints the body", sync + ["--root", str(norepo), "--offline", "--show-body", "M1", "--repo", "o/r"],
         contains=["https://github.com/o/r/blob/main/docs/spec/m1-submit-report/milestone.md"])
    # the path is checked before the token is read, so this text, which is not a token, is never looked at
    step("a --token-file name too long for the file system is one line", token + ["--stdin", "--token-file", str(d / ("t" * 300))], expect=2,
         stdin="not-a-token\n", contains=["cannot be used"])
    step("check_specs --plan '' is an error, as JSON", chk + s + ["--plan", "", "--json"], expect=2, contains=["--plan is empty"], json_out=True)
    step("check_specs --root '' is an error, as JSON", chk + ["--root", "", "--json"], expect=2, contains=["--root is empty"], json_out=True)

    # --show-body takes the same ids as --item; negative numbers and other digits are not ids
    for w in ("WI-03", "wi-3", "03", "3"):
        step(f"--show-body {w} prints item 3", sync + s + ["--offline", "--show-body", w], contains=["### Work item", "<!-- carrydown:WI-03 -->"])
    for w in ("-1", "\uff10\uff13", "WI-x"):
        step(f"--show-body {w!r} is an error", sync + s + ["--offline", "--show-body", w], expect=2, contains=["no item with id"])
    step("--item with full-width digits is an error", chk + s + ["--item", "\uff10\uff13"], expect=2, contains=["is not an item id"])

    # the generator refuses references without a skill, and the checker's exit codes match its help
    fresh = project("r2-only")
    shutil.rmtree(fresh / "docs/dev")
    step("--only references --apply without SKILL.md is refused", gen + ["--root", str(fresh), "--only", "references", "--apply"], expect=2,
         contains=["Run this script without --only first"])
    results.append((not (fresh / "docs/dev").exists(), "the refused --only references wrote nothing"))
    print(("PASS " if not (fresh / "docs/dev").exists() else "FAIL ") + "the refused --only references wrote nothing")
    step("check_specs --help states the exit codes it uses", chk + ["--help"], contains=["1 when there are findings (problems with plan.yaml", "2 when the plan cannot be read"])

    # messages of a script copy name only files that ship in its own skill
    for skill, want, other in (("carrydown-ground-truth", "the rules are in references/planning.md", "How this plan was composed"),
                               ("carrydown-plan-to-github", "under How this plan was composed", "references/planning.md")):
        copy = d / ("copy-" + skill)
        shutil.copytree(ROOT / "skills" / skill, copy)
        step(f"the {skill} checker points at text that ships with it", [PY, str(copy / "scripts/check_specs.py"), "--root", str(ROOT / SAMPLE), "--report"],
             contains=[want], absent=("Traceback", other))
        nogt = project("r2-nogt-" + skill)
        (nogt / "docs/ground-truth/architecture.md").unlink()
        hint = "render_ground_truth.py" if skill == "carrydown-ground-truth" else "Render it with the carrydown-ground-truth skill"
        step(f"the {skill} checker's render hint names what ships with it", [PY, str(copy / "scripts/check_specs.py"), "--root", str(nogt)], expect=1, contains=[hint])


def main():
    ap = argparse.ArgumentParser(description="Self test for the carrydown skills. No token and no network.")
    ap.parse_args()
    scripts = sorted((ROOT / "scripts").glob("*.py"))
    for s in scripts + sorted((ROOT / "tests").rglob("*.py")):
        try:
            ast.parse(s.read_text(encoding="utf-8"))
            ok = True
        except SyntaxError as e:
            ok = False
            print(f"      {s.name}: {e}")
        results.append((ok, f"syntax {s.name}"))
        print(("PASS " if ok else "FAIL ") + f"syntax {s.name}")
    step("skill copies are current", [PY, "scripts/sync_skill_assets.py", "--check"])
    step("checker on the sample", [PY, "scripts/check_specs.py", "--root", SAMPLE])
    step("checker report on the sample", [PY, "scripts/check_specs.py", "--root", SAMPLE, "--report"])
    for s in scripts:
        if s.name not in ("carrydown_lib.py", "github_client.py", "selftest.py"):
            step(f"--help {s.name}", [PY, f"scripts/{s.name}", "--help"])
    step("dry run: render_ground_truth", [PY, "scripts/render_ground_truth.py", f"{SAMPLE}/ground-truth/architecture.md", "--root", SAMPLE, "--version", "0.3", "--dry-run"])
    step("dry run: scaffold_spec", [PY, "scripts/scaffold_spec.py", "--root", SAMPLE, "--stubs"])
    step("dry run: github_sync (offline)", [PY, "scripts/github_sync.py", "--root", SAMPLE, "--offline"])
    step("show one issue body", [PY, "scripts/github_sync.py", "--root", SAMPLE, "--offline", "--show-body", "WI-07"])
    pipe = ("import subprocess, sys; p = subprocess.Popen(sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE); "
            "p.stdout.readline(); p.stdout.close(); err = p.stderr.read().decode(); p.wait(); print(err); print('reader stopped early')")
    talk = "import sys; sys.path.insert(0, 'scripts'); import carrydown_lib as L; [L.say('x' * 999) for _ in range(2000)]"
    step("output to a reader that stops early, as | head does, ends without a traceback", [PY, "-c", pipe, PY, "-c", talk],
         contains=["reader stopped early"], absent=("Traceback", "Exception ignored", "BrokenPipeError"))
    step("dry run: github_project (offline)", [PY, "scripts/github_project.py", "--root", SAMPLE, "--offline"])
    step("dry run: github_repair (offline)", [PY, "scripts/github_repair.py", "--root", SAMPLE, "--offline"],
         contains=["offline: nothing read from GitHub; no files written"])
    step("dry run: generate_dev_skill", [PY, "scripts/generate_dev_skill.py", "--root", SAMPLE])
    step("dry run: github_token", [PY, "scripts/github_token.py", "--dry-run"])
    plan_text = (ROOT / SAMPLE / "docs/spec/plan.yaml").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        def variant(name, text):
            path = Path(tmp) / f"{name}.yaml"
            path.write_text(text, encoding="utf-8")
            return str(path)
        chk = [PY, "scripts/check_specs.py", "--root", SAMPLE]
        step("report shows allocation, capacity and the target", chk + ["--report"], contains=["Alloc", "60%", "of 6d", "meets the target"])
        step("supplied skills and preferences are advisory and reported", chk + ["--report"],
             contains=["Staffing context (advisory)", "Track workflow needs: Service APIs, Workflow rules, Relational data",
                       "tamsin on workflow: skills Python services, PostgreSQL, Workflow design; preferences Service contracts, Policy enforcement",
                       "They do not make the checker pass or fail"])
        optional_staffing = ("skill_needs:", "skills:", "preferences:", "assignment_rationale:")
        no_staffing = "\n".join(line for line in plan_text.splitlines() if not line.strip().startswith(optional_staffing)) + "\n"
        step("missing skills and preferences use default assignment and never fail", chk + ["--report", "--plan", variant("nostaffing", no_staffing)],
             contains=["No skills or work preferences were supplied. The plan uses the default track, capacity, dependency and context-switching rules.",
                       "0 finding(s)."])
        scalar_staffing = plan_text.replace('skills: ["Python services", "PostgreSQL", "Workflow design"]', 'skills: "Python services and PostgreSQL"', 1)
        step("staffing context can be plain text without failing", chk + ["--report", "--plan", variant("scalarstaffing", scalar_staffing)],
             contains=["tamsin on workflow: skills Python services and PostgreSQL;"])
        step("allocation is optional and defaults to 100", chk + ["--report", "--plan", variant("noalloc", plan_text.replace("    allocation: 100\n", "").replace("    allocation: 60\n", ""))], contains=["100%"])
        step("allocation 0 is rejected", chk + ["--plan", variant("alloc0", plan_text.replace("allocation: 60", "allocation: 0"))], expect=1, contains=["allocation must be a whole percent from 1 to 100"])
        step("allocation 101 is rejected", chk + ["--plan", variant("alloc101", plan_text.replace("allocation: 100", "allocation: 101"))], expect=1, contains=["allocation must be a whole percent"])
        no_target = plan_text.replace("target:\n  date: 2027-04-23\n\n", "")
        step("no target is accepted and the end date is derived", chk + ["--report", "--plan", variant("notarget", no_target)], contains=["derived from the critical path", "There is no target in plan.yaml"])
        step("a derived target that matches the critical path passes", chk + ["--plan", variant("derivedok", plan_text.replace("  date: 2027-04-23\n", "  date: 2027-04-21\n  derived: true\n"))], contains=["0 with findings", "target derived"])
        step("a stale derived target is reported", chk + ["--plan", variant("derivedstale", plan_text.replace("  date: 2027-04-23\n", "  date: 2027-04-23\n  derived: true\n"))], expect=1, contains=["derived target 2027-04-23 is out of date"])
        derived_people = plan_text.replace("Tamsin Hale", "Engineer 1").replace("Idris Okoye", "Engineer 2").replace("tamsin", "eng1").replace("idris", "eng2").replace("    allocation: 100\n", "    allocation: 100\n    derived: true\n").replace("    allocation: 60\n", "    allocation: 60\n    derived: true\n").replace("  date: 2027-04-23\n", "  date: 2027-04-21\n  derived: true\n")
        step("derived people and a derived target are summarized", chk + ["--plan", variant("derivedboth", derived_people)], contains=["2 people derived, target derived"])
        i0 = plan_text.index("people:\n"); i1 = plan_text.index("advisors:")
        nobody = plan_text[:i0] + "people: []\n\n" + plan_text[i1:]
        nobody = nobody.replace("    owner: tamsin\n", "").replace("    owner: idris\n", "")
        step("a plan without people passes and says so", chk + ["--report", "--plan", variant("nobody", nobody)], contains=["No people in the plan yet"])
        sync = [PY, "scripts/github_sync.py", "--root", SAMPLE, "--offline"]
        step("dry run prints the constraints, target given", sync, contains=["Target delivery: 2027-04-23 (given)", "Track Workflow: 1 person, 100 percent allocated", "Track Experience: 1 person, 60 percent allocated"])
        step("dry run prints a derived target", sync + ["--plan", variant("syncnotarget", no_target)], contains=["Target delivery: 2027-04-21 (derived from the critical path)"])
        step("dry run marks placeholder people", sync + ["--plan", variant("syncderived", derived_people)], contains=["(placeholder)"])
        step("dry run says people are to be assigned", sync + ["--plan", variant("syncnobody", nobody)], contains=["People: to be assigned (derived capacity: 2)"])
        code = ("import sys; sys.path.insert(0, 'scripts'); import carrydown_lib as L, github_sync as S; "
                "plan, _ = L.load_plan(sys.argv[1]); "
                "print(S.build_rollup(plan, {}, 1)); print(S.build_subepic_body(plan, sys.argv[2], plan['milestones'][0]))")
        step("the Epic comment and a sub-epic body carry the constraints", [PY, "-c", code, str(ROOT / SAMPLE / "docs/spec/plan.yaml"), str(ROOT / SAMPLE)],
             contains=["**Constraints**", "- Target delivery: 2027-04-23 (given)", "Target delivery for the plan: 2027-04-23 (given)"])
        code = ("import sys; sys.path.insert(0, 'scripts'); import carrydown_lib as L, github_sync as S; "
                "plan, _ = L.load_plan(sys.argv[1]); "
                "b = S.build_subepic_body(plan, sys.argv[2], [m for m in plan['milestones'] if m['number'] == 2][0]); print(b); "
                "i = [b.index(h) for h in ('Target delivery for the plan:', '### Why these items form this milestone', '### Joint demonstration', '### Acceptance criteria')]; "
                "sys.exit(0 if i == sorted(i) and '<!--' not in b.rstrip().rsplit(chr(10), 1)[0] and b.rstrip().rsplit(chr(10), 1)[1].startswith('<!-- carrydown:') else 1)")
        step("the sub-epic body carries the milestone rationale and joint demonstration", [PY, "-c", code, str(ROOT / SAMPLE / "docs/spec/plan.yaml"), str(ROOT / SAMPLE)],
             contains=["### Why these items form this milestone", "Routing and the inbox are the two halves of one capability",
                       "### Joint demonstration", "The Experience engineer approves one report as two approvers in turn from the inbox",
                       "Target delivery for the plan: 2027-04-23 (given)"])
        step("--show-body prints a sub-epic body", sync + ["--show-body", "M2"], contains=["### Joint demonstration", "Target delivery for the plan: 2027-04-23 (given)"])
        step("a target in weeks is accepted", chk + ["--report", "--plan", variant("weeks", plan_text.replace("  date: 2027-04-23\n", "  weeks: 11\n"))], contains=["11 working weeks plus 1 break week(s)", "meets the target"])
        step("over 100 percent of allocated capacity is flagged", chk + ["--plan", variant("overload", plan_text.replace("allocation: 60", "allocation: 10"))], expect=1, contains=["over 100 percent of allocated capacity"])
        step("a missed target is reported", chk + ["--report", "--plan", variant("late", plan_text.replace("  date: 2027-04-23\n", "  date: 2027-04-16\n"))], contains=["misses the target"])
        step("the report checks every window against size and allocation", chk + ["--report"], contains=["Every sized item fits between its last dependency and its complete_by date.", "Earliest finish", "ends 2027-03-10"])
        squeezed = plan_text.replace("complete_by: 2027-03-17\n    size: \"Medium, about 4 days\"", "complete_by: 2027-03-16\n    size: \"Medium, about 4 days\"")
        step("an item whose window is too short for its size is flagged", chk + ["--plan", variant("squeezed", squeezed)], expect=1,
             contains=["WI-08 needs about 6.7 working days (4 days at 60 percent) but has 6 from 2027-03-09, the day after WI-06 completes, to its complete_by 2027-03-16"])
        step("an earliest finish after the target is flagged", chk + ["--plan", variant("tooearly", plan_text.replace("  date: 2027-04-23\n", "  date: 2027-03-05\n"))], expect=1,
             contains=["from sizes and allocation the earliest finish is 2027-03-10, after the target 2027-03-05"])
        step("a size without a number of days is flagged", chk + ["--plan", variant("nosize", plan_text.replace('size: "Large, about 5 days"', 'size: "Large"'))], expect=1,
             contains=["size must say how many days"])
        planning_review(chk, variant, plan_text)
        for skill, script in (("carrydown-ground-truth", "check_specs.py"), ("carrydown-plan-to-github", "github_sync.py")):
            dst = Path(tmp) / skill
            shutil.copytree(ROOT / "skills" / skill, dst)
            if script == "check_specs.py":
                step(f"installed copy of {skill} runs {script}", [PY, str(dst / "scripts" / script), "--root", str(ROOT / SAMPLE), "--quiet"])
            elif script == "github_sync.py":
                step(f"installed copy of {skill} runs {script}", [PY, str(dst / "scripts" / script), "--root", str(ROOT / SAMPLE), "--offline", "--show-body", "3"])
            else:
                step(f"installed copy of {skill} runs {script}", [PY, str(dst / "scripts" / script), "--root", str(ROOT / SAMPLE)])
            for other in sorted((dst / "scripts").glob("*.py")):
                if other.name != "carrydown_lib.py":
                    step(f"installed copy of {skill} runs {other.name} --help", [PY, str(other), "--help"])
            if (dst / "scripts/scaffold_spec.py").exists():
                step(f"installed copy of {skill} runs the header refresh", [PY, str(dst / "scripts/scaffold_spec.py"), "--root", str(ROOT / SAMPLE), "--refresh-headers"])
        gh = Path(tmp) / "carrydown-plan-to-github"
        step("installed copy of carrydown-plan-to-github generates the engineers' skill", [PY, str(gh / "scripts/generate_dev_skill.py"), "--root", str(ROOT / SAMPLE)],
             contains=["engineers' skill: expense-approvals-dev"])
        step("installed copy of carrydown-plan-to-github refreshes only the references", [PY, str(gh / "scripts/generate_dev_skill.py"), "--root", str(ROOT / SAMPLE), "--only", "references"],
             contains=["would write: references/work-items.md", "would write: references/ground-truth-map.md"], absent=("Traceback", "SKILL.md"))
        ships = ("generate_dev_skill.py", "check_specs.py", "carrydown_lib.py", "github_client.py", "github_project.py", "github_repair.py", "github_sync.py", "github_token.py")
        extra = sorted(x.name for x in (gh / "scripts").glob("*.py") if x.name not in ships)
        results.append((not extra, "carrydown-plan-to-github ships only the scripts it runs"))
        print(("PASS " if not extra else "FAIL ") + "carrydown-plan-to-github ships only the scripts it runs" + (f" (remove {', '.join(extra)})" if extra else ""))
        fixtures(Path(tmp))
        citations(Path(tmp))
        error_paths(Path(tmp), plan_text)
        maintenance(Path(tmp))
        composition(Path(tmp), plan_text)
        frontmatter(Path(tmp), plan_text)
        path_safety(Path(tmp), plan_text)
        names(Path(tmp), plan_text)
        lint_spelling(Path(tmp))
        regressions(Path(tmp), plan_text)
        round_two(Path(tmp), plan_text)
    step("dry run without a token says nothing was checked against GitHub", [PY, "scripts/github_sync.py", "--root", SAMPLE],
         contains=["not checked against GitHub (no token)", f"python3 {ROOT / 'scripts' / 'github_token.py'}"], absent=["Already on GitHub: the rest"])
    step("board dry run without a token says nothing was checked against GitHub", [PY, "scripts/github_project.py", "--root", SAMPLE],
         contains=["not checked against GitHub (no token)"])
    step("apply without a token names the token script by its full path", [PY, "scripts/github_sync.py", "--root", SAMPLE, "--apply"],
         expect=1, contains=[f"No GitHub token found. Run: python3 {ROOT / 'scripts' / 'github_token.py'}"])
    step("text that is not a token is refused before anything is sent", [PY, "scripts/github_token.py", "--stdin", "--token-file", str(Path(HOME) / "t")],
         stdin="password-not-a-token-1234\n", expect=2, contains=["that is not a GitHub personal access token (it starts with ghp_ or github_pat_). Nothing was sent."])
    mock = [
        ("retry502", "mock: a 502 after a create makes no duplicate"),
        ("partial", "mock: a rerun after a crash repairs the links"),
        ("unlinked", "mock: --verify fails on an unlinked id"),
        ("sso", "mock: single sign-on gives a one-line message with the fix"),
        ("timeout", "mock: a timeout gives a one-line message"),
        ("public", "mock: --apply to a public repository needs --allow-public"),
        ("ownership", "mock: only labeled issues and own comments count"),
        ("project", "mock: renamed issues are found by their marker"),
        ("tokenfile", "mock: the token file is kept and checked before sending"),
        ("tokenenv", "mock: the token check reads CARRYDOWN_GITHUB_TOKEN like the GitHub scripts"),
        ("tokenrules", "mock: a token file others can read, a bad token and a missing --token-file are refused"),
        ("redirect", "mock: a redirect to another host never receives the token"),
        ("repos", "mock: owner and repository names with - and ., a missing repository, --issue-type"),
        ("board", "mock: the project board is built, a rerun changes nothing, iterations are reconfigured"),
        ("boardverify", "mock: project verification rejects missing or incorrect board data"),
        ("projectnumber", "mock: --project-number for a missing project creates nothing"),
        ("errors", "mock: 401, 429, the secondary rate limit and a 502 before a write"),
        ("paging", "mock: lists longer than one page are read to the end by the Link header"),
        ("verifyskip", "mock: --verify --skip-comment passes without the roll-up comment"),
        ("titleformat", "mock: a bad title_format stops --apply before anything is sent"),
        ("tokenloose", "mock: --from-file with a source others can read stores and warns once"),
    ]
    for scenario, name in mock:
        step(name, [PY, "tests/mock/scenarios.py", scenario], contains=[f"{scenario}: all checks passed"], timeout=120)
    step("isolated issue metadata repairs preserve history and recover safely", [PY, "tests/test_github_repair.py"], contains=["OK"], timeout=120)
    failed = [n for ok, n in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
