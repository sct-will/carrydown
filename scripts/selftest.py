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
     the plan's, renamed issues, and the token file. It also runs the dry runs without a token.

Every step runs with HOME set to an empty temporary folder and with no
CARRYDOWN_GITHUB_TOKEN, so no stored token is ever read.
  8. Builds small Word documents with tests/fixtures/make_numbered_docx.py and renders them,
     and runs the scripts on broken variants of the sample to prove they fail with a message,
     not a traceback.
  9. Runs the planning review on variants of the sample: a milestone on one track without a
     reason, missing rationale, an item with no slack, theme switches, a critical path owned by
     one person and a load ratio above two to one.

Usage
  python3 scripts/selftest.py
Exit status is 0 when every step passes and 1 otherwise.
"""
import ast
import atexit
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


def step(name, cmd, cwd=ROOT, expect=0, contains=(), absent=("Traceback",), env=None, files=None, order=(), stdin=""):
    """Run cmd and check the exit status, text that must appear, text that must not appear, and,
    with files, {path: [text, ...]} that must appear in files the command wrote."""
    run_env = dict(ENV, **(env or {}))
    p = subprocess.run(cmd, cwd=cwd, env=run_env, capture_output=True, text=True, encoding="utf-8", errors="replace", input=stdin)
    out = (p.stdout or "") + (p.stderr or "")
    missing = [c for c in contains if c not in out]
    present = [c for c in absent if c in out]
    at = [out.find(o) for o in order]
    if order and (-1 in at or at != sorted(at)):
        missing.append("in this order: " + " < ".join(order))
    for path, wants in (files or {}).items():
        body = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
        missing += [f"{Path(path).name}: {w}" for w in wants if w not in body]
    ok = p.returncode == expect and not missing and not present
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
    fx.mkdir()
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
        unreadable = label.startswith("quote")
        step(f"plan with {label}: one line, no traceback", chk + ["--plan", v], expect=1, contains=[want])
        step(f"plan with {label}: --report says so first", chk + ["--plan", v, "--report"], expect=1,
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
    step("a project name with ': ' and ' #' gives a quoted description", gen + ["--apply"], contains=["description length: 240 characters"])
    code = ("import json, re, sys; t = open(sys.argv[1], encoding='utf-8').read(); "
            "m = re.search(r'(?m)^description: (.*)$', t); d = json.loads(m.group(1)); "
            "assert d.startswith('Orients on one Payments: phase 2 #core work item'), d; "
            "assert 'WI-01 to WI-11' in d and 'wi-01-service-scaffold' in d and 'docs/spec/' in d, d; print('parsed', len(d))")
    step("the description is a valid quoted scalar", [PY, "-c", code, str(proj / "docs/dev/skills/expense-approvals-dev/SKILL.md")], contains=["parsed 240"])
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
    step("images outside the document folder, or not images, are not copied",
         [PY, "scripts/render_ground_truth.py", str(md), "--root", str(out)],
         contains=["not copied (outside the document folder or not an image): ../secret.txt", "not copied (outside the document folder or not an image): notes.txt", "1 figures"])
    figs = sorted(x.name for x in (out / "docs/ground-truth/figures/design").iterdir())
    ok = figs == ["ok.png"]
    results.append((ok, "only the image inside the document folder was copied"))
    print(("PASS " if ok else "FAIL ") + "only the image inside the document folder was copied" + ("" if ok else f" (found {figs})"))
    step("--out-dir outside the project is refused", [PY, "scripts/render_ground_truth.py", str(md), "--root", str(out), "--out-dir", "../elsewhere"], expect=2, contains=["outside the project folder"])
    proj = d / "proj"
    shutil.copytree(ROOT / SAMPLE, proj)
    plan = proj / "docs/spec/plan.yaml"
    plan.write_text(plan_text.replace("folder: m4-pilot", "folder: ../../../m4-pilot"), encoding="utf-8")
    step("a milestone folder outside the project is refused", [PY, "scripts/scaffold_spec.py", "--root", str(proj), "--allow-no-git"], expect=2, contains=["outside the project folder"])
    plan.write_text(plan_text.replace("dev_skill_path: docs/dev/skills/expense-approvals-dev", "dev_skill_path: ../../expense-approvals-dev"), encoding="utf-8")
    step("a developer skill path outside the project is refused", [PY, "scripts/generate_dev_skill.py", "--root", str(proj)], expect=2, contains=["outside the project folder"])
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
    step("a capitalised name part and a handle are still flagged", chk, expect=1,
         contains=["person name or handle from the plan at line", "Long reviewed this with idris."])


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
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
    step("dry run: github_project (offline)", [PY, "scripts/github_project.py", "--root", SAMPLE, "--offline"])
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
        step("allocation is optional and defaults to 100", chk + ["--report", "--plan", variant("noalloc", plan_text.replace("    allocation: 100\n", "").replace("    allocation: 60\n", ""))], contains=["100%"])
        step("allocation 0 is rejected", chk + ["--plan", variant("alloc0", plan_text.replace("allocation: 60", "allocation: 0"))], expect=1, contains=["allocation must be a whole percent from 1 to 100"])
        step("allocation 101 is rejected", chk + ["--plan", variant("alloc101", plan_text.replace("allocation: 100", "allocation: 101"))], expect=1, contains=["allocation must be a whole percent"])
        no_target = plan_text.replace("target:\n  date: 2027-04-23\n\n", "")
        step("no target is accepted and the end date is derived", chk + ["--report", "--plan", variant("notarget", no_target)], contains=["derived from the critical path", "There is no target in plan.yaml"])
        step("a derived target that matches the critical path passes", chk + ["--plan", variant("derivedok", plan_text.replace("  date: 2027-04-23\n", "  date: 2027-04-21\n  derived: true\n"))], contains=["0 with findings", "target derived"])
        step("a stale derived target is reported", chk + ["--plan", variant("derivedstale", plan_text.replace("  date: 2027-04-23\n", "  date: 2027-04-23\n  derived: true\n"))], expect=1, contains=["derived target 2027-04-23 is out of date"])
        derived_people = plan_text.replace("Tamsin Hale", "Engineer 1").replace("Idris Okoye", "Engineer 2").replace("tamsin", "eng1").replace("idris", "eng2").replace("    allocation: 100\n", "    allocation: 100\n    derived: true\n").replace("    allocation: 60\n", "    allocation: 60\n    derived: true\n").replace("  date: 2027-04-23\n", "  date: 2027-04-21\n  derived: true\n")
        step("derived people and a derived target are summarised", chk + ["--plan", variant("derivedboth", derived_people)], contains=["2 people derived, target derived"])
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
        for skill, script in (("carrydown-ground-truth", "check_specs.py"), ("carrydown-plan-to-github", "github_sync.py"), ("carrydown-dev-skill", "generate_dev_skill.py")):
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
        dev = Path(tmp) / "carrydown-dev-skill"
        step("installed copy of carrydown-dev-skill refreshes only the references", [PY, str(dev / "scripts/generate_dev_skill.py"), "--root", str(ROOT / SAMPLE), "--only", "references"],
             contains=["would write: references/work-items.md", "would write: references/ground-truth-map.md"], absent=("Traceback", "SKILL.md"))
        extra = sorted(x.name for x in (dev / "scripts").glob("*.py") if x.name not in ("generate_dev_skill.py", "check_specs.py", "carrydown_lib.py"))
        results.append((not extra, "carrydown-dev-skill ships only the scripts it runs"))
        print(("PASS " if not extra else "FAIL ") + "carrydown-dev-skill ships only the scripts it runs" + (f" (remove {', '.join(extra)})" if extra else ""))
        fixtures(Path(tmp))
        citations(Path(tmp))
        error_paths(Path(tmp), plan_text)
        maintenance(Path(tmp))
        composition(Path(tmp), plan_text)
        frontmatter(Path(tmp), plan_text)
        path_safety(Path(tmp), plan_text)
        names(Path(tmp), plan_text)
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
        ("ownership", "mock: only labelled issues and own comments count"),
        ("project", "mock: renamed issues are found by their marker"),
        ("tokenfile", "mock: the token file is kept and checked before sending"),
    ]
    for scenario, name in mock:
        step(name, [PY, "tests/mock/scenarios.py", scenario], contains=[f"{scenario}: all checks passed"])
    failed = [n for ok, n in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
