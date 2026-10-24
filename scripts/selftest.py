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

Usage
  python3 scripts/selftest.py
Exit status is 0 when every step passes and 1 otherwise.
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
ENV.pop("CARRYDOWN_GITHUB_TOKEN", None)
SAMPLE = "sample/expense-approvals"
results = []


def step(name, cmd, cwd=ROOT, expect=0, contains=()):
    p = subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    missing = [c for c in contains if c not in out]
    ok = p.returncode == expect and not missing
    results.append((ok, name))
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        print("      exit", p.returncode, ("missing in output: " + repr(missing)) if missing else "")
        for line in ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-12:]:
            print("      " + line)
    return ok


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
    scripts = sorted((ROOT / "scripts").glob("*.py"))
    for s in scripts:
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
        if s.name not in ("carrydown_lib.py", "selftest.py"):
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
        step("a missing target is rejected", chk + ["--plan", variant("notarget", plan_text.replace("target:\n  date: 2027-04-23\n", ""))], expect=1, contains=["target: the plan needs a target"])
        step("a target in weeks is accepted", chk + ["--report", "--plan", variant("weeks", plan_text.replace("  date: 2027-04-23\n", "  weeks: 11\n"))], contains=["11 working weeks plus 1 break week(s)", "meets the target"])
        step("over 100 percent of allocated capacity is flagged", chk + ["--plan", variant("overload", plan_text.replace("allocation: 60", "allocation: 10"))], expect=1, contains=["over 100 percent of allocated capacity"])
        step("a missed target is reported", chk + ["--report", "--plan", variant("late", plan_text.replace("  date: 2027-04-23\n", "  date: 2027-04-16\n"))], contains=["misses the target"])
        for skill, script in (("carrydown-ground-truth", "check_specs.py"), ("carrydown-plan-to-github", "github_sync.py"), ("carrydown-dev-skill", "generate_dev_skill.py")):
            dst = Path(tmp) / skill
            shutil.copytree(ROOT / "skills" / skill, dst)
            if script == "check_specs.py":
                step(f"installed copy of {skill} runs {script}", [PY, str(dst / "scripts" / script), "--root", str(ROOT / SAMPLE), "--quiet"])
            elif script == "github_sync.py":
                step(f"installed copy of {skill} runs {script}", [PY, str(dst / "scripts" / script), "--root", str(ROOT / SAMPLE), "--offline", "--show-body", "3"])
            else:
                step(f"installed copy of {skill} runs {script}", [PY, str(dst / "scripts" / script), "--root", str(ROOT / SAMPLE)])
    failed = [n for ok, n in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
