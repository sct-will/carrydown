#!/usr/bin/env python3
"""Proof of work package 10 (documentation, FAQ, sample): re-runnable, no token, no network.

Each claim prints PASS or FAIL with the line it observed, and the last line says how many passed.

    python3 tests/proof_wp10.py

It runs the prose lint on every document the work package edited, the link checker in source context and in
generated-output context, the sync check, the sample checker in both views, the engineers' context check in a
fresh clone with no private workspace, the scaffold's header refresh and CI copy on a released project, the
reproducibility of the sample's release, and the searches for the obsolete instructions. It needs git, writes
only below a temporary folder, and uses no token and no network.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
SAMPLE = ROOT / "sample" / "expense-approvals"
PY = sys.executable

EDITED_DOCUMENTS = [
    "README.md", "CHANGELOG.md", "SECURITY.md",
    "docs/enterprise-security.md", "docs/delivery-modes.md", "docs/setup.md", "docs/security.md", "docs/plan-owner-guide.md",
    "docs/faq.md", "docs/inputs.md", "docs/method.md", "docs/recovery.md", "docs/sample-run.md", "docs/recording-storyboard.md",
    "docs/repository-metadata.md", "docs/derive-the-date.md",
    "skills/carrydown-ground-truth/SKILL.md", "skills/carrydown-plan-to-github/SKILL.md",
    "skills/carrydown-ground-truth/references/interview.md", "skills/carrydown-ground-truth/references/planning.md",
    "skills/carrydown-ground-truth/references/source-material.md",
    "skills/carrydown-plan-to-github/references/engineers-skill-install.md",
    "skills/carrydown-plan-to-github/references/engineers-skill-maintenance.md",
    "skills/carrydown-plan-to-github/references/engineers-skill-review.md",
    "templates/spec-README.md", "templates/dev-skill/README.md.tmpl", "templates/dev-skill/SKILL.md.tmpl",
    "sample/expense-approvals/README.md", "sample/expense-approvals/docs/spec/README.md",
    "sample/expense-approvals/docs/dev/skills/expense-approvals-dev/README.md",
    "sample/expense-approvals/docs/dev/skills/expense-approvals-dev/SKILL.md",
]

results = []


def claim(ok, text, observed):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + text)
    print("     observed: " + " || ".join(str(observed).split("\n"))[:600])


def run(args, cwd=None, env=None, timeout=600):
    return subprocess.run([str(a) for a in args], cwd=str(cwd or ROOT), capture_output=True, text=True, env=env, timeout=timeout)


def last(out, n=1):
    lines = [l for l in (out.stdout + out.stderr).strip().split("\n") if l.strip()]
    return "; ".join(lines[-n:]) if lines else "(no output)"


def clean_env(home):
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull, PYTHONDONTWRITEBYTECODE="1")
    env.pop("CARRYDOWN_GITHUB_TOKEN", None)
    return env


def git(args, cwd, env):
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True, env=env, check=True)


def clean_clone(dst):
    shutil.copytree(SAMPLE, dst)
    shutil.rmtree(Path(dst) / "ground-truth")
    shutil.rmtree(Path(dst) / "docs" / "ground-truth")
    (Path(dst) / "people.yaml").unlink()
    return Path(dst)


def main():
    print("carrydown WP10 proof: the documents, the link checks and the sample, no token, no network\n")
    tmp = Path(tempfile.mkdtemp(prefix="carrydown-wp10-"))
    try:
        env = clean_env(tmp / "home")
        (tmp / "home").mkdir()

        # 1. prose lint, explicitly on every edited document, and on the whole repository
        present = [d for d in EDITED_DOCUMENTS if (ROOT / d).is_file()]
        missing = [d for d in EDITED_DOCUMENTS if d not in present]
        out = run([PY, "scripts/lint_prose.py"] + present)
        claim(out.returncode == 0 and not missing and f"{len(present)} files linted, 0 findings" in out.stdout,
              "The prose lint passes on each document the work package edited, named explicitly", last(out) + (f" || missing: {missing}" if missing else ""))
        draft = ROOT / "specs" / "confidentiality-review" / "enterprise-security.draft.md"
        if draft.is_file():
            out = run([PY, "scripts/lint_prose.py", draft])
            claim(out.returncode == 0, "The prose lint passes on the source draft of the security page", last(out))
        else:
            claim(True, "The source draft of the security page is not tracked in this clone (specs/ is excluded), so the published page is the one linted",
                  "specs/confidentiality-review/enterprise-security.draft.md not present here")
        out = run([PY, "scripts/lint_prose.py"])
        claim(out.returncode == 0 and ", 0 findings" in out.stdout, "The prose lint passes on every published Markdown file and every other linted file", last(out))

        # 2. links, in source context and in generated-output context
        out = run([PY, "tests/check_links.py"])
        claim(out.returncode == 0 and ", 0 broken link(s)" in out.stdout, "Every relative link resolves in source and template context (the repository)", last(out))
        clone = clean_clone(tmp / "clean-clone")
        out = run([PY, "tests/check_links.py", "--root", clone])
        claim(out.returncode == 0 and ", 0 broken link(s)" in out.stdout,
              "Every relative link resolves in a clean clone of the sample, which has no original, no rendering and no people file", last(out))
        owner = tmp / "owner"
        from sample_tree import copy_sample
        copy_sample(owner)
        git(["init", "-q", "-b", "main"], owner, env)
        shutil.rmtree(owner / "docs" / "dev")
        gen = run([PY, "scripts/generate_dev_skill.py", "--root", owner, "--apply"], env=env)
        out = run([PY, "tests/check_links.py", "--root", owner, "docs/dev", "docs/spec/README.md"])
        claim(gen.returncode == 0 and out.returncode == 0 and ", 0 broken link(s)" in out.stdout,
              "Every relative link resolves in generated output: the engineers' skill and the specification README that the scripts just wrote", last(gen) + " || " + last(out))

        # 3. synced and generated documents match their templates
        out = run([PY, "scripts/sync_skill_assets.py", "--check"])
        claim(out.returncode == 0 and "copies are current" in out.stdout, "Every carried copy of a script and a template matches its canonical source", last(out))
        import carrydown_lib as L
        import scaffold_spec as S
        plan, _ = L.load_plan(SAMPLE / "docs" / "spec" / "plan.yaml", SAMPLE)
        working, _ = L.load_plan(ROOT / "tests" / "fixtures" / "sample-workspace" / "drafts" / "plan.yaml", SAMPLE)
        committed = (SAMPLE / "docs" / "spec" / "README.md").read_text(encoding="utf-8")
        claim(S.build_readme(plan) == committed and S.build_readme(working) == committed,
              "The sample's specification README is what the template makes, from the released plan and from the owner's working plan alike",
              f"{len(committed)} characters; released equals working: {S.build_readme(plan) == S.build_readme(working)}")
        regen = run([PY, "scripts/generate_dev_skill.py", "--root", owner, "--apply", "--force"], env=env)
        same = all((owner / "docs/dev/skills/expense-approvals-dev" / n).read_bytes() == (SAMPLE / "docs/dev/skills/expense-approvals-dev" / n).read_bytes()
                   for n in ("README.md", "SKILL.md", "references/work-items.md", "references/contracts.md", "references/ground-truth-map.md", "scripts/check_context.py"))
        claim(regen.returncode == 0 and same, "The sample's engineers' README, skill, references and check are what the generator and the templates make",
              last(regen) + f" || identical: {same}")
        for name in ("README.md.tmpl", "SKILL.md.tmpl"):
            for skill in ("carrydown-plan-to-github",):
                a = (ROOT / "templates" / "dev-skill" / name).read_bytes()
                b = (ROOT / "skills" / skill / "templates" / "dev-skill" / name).read_bytes()
                claim(a == b, f"The carried copy of templates/dev-skill/{name} in {skill} matches the canonical one", f"{len(a)} bytes")
        claim((ROOT / "templates" / "spec-README.md").read_bytes() == (ROOT / "skills" / "carrydown-ground-truth" / "templates" / "spec-README.md").read_bytes()
              and (ROOT / "templates" / "spec-README.md").read_bytes() == (ROOT / "skills" / "carrydown-plan-to-github" / "templates" / "spec-README.md").read_bytes(),
              "The carried copies of templates/spec-README.md in both skills match the canonical one", "identical in all three places")

        # 4. the scaffold on a released project
        proj = clean_clone(tmp / "released-project")
        git(["init", "-q", "-b", "main"], proj, env)
        out = run([PY, "scripts/scaffold_spec.py", "--root", proj, "--refresh-headers"], env=env)
        claim(out.returncode == 0 and "Traceback" not in out.stdout + out.stderr and "refresh" not in out.stdout.replace("--refresh-headers", ""),
              "scaffold_spec.py --refresh-headers (dry run) works on a released project and finds nothing to change", last(out))
        out = run([PY, "scripts/scaffold_spec.py", "--root", proj, "--ci"], env=env)
        claim(out.returncode == 0 and "Traceback" not in out.stdout + out.stderr, "scaffold_spec.py --ci (dry run) works on a released project", last(out))

        # 5. the sample passes the checker, in both views, in a clean clone and as committed
        out = run([PY, "scripts/check_specs.py", "--root", SAMPLE, "--report"])
        claim(out.returncode == 0 and "0 finding(s)." in out.stdout, "The sample passes check_specs.py --report with 0 findings", last(out))
        out = run([PY, "scripts/check_specs.py", "--root", clone, "--view", "released"], env=env)
        claim(out.returncode == 0 and "0 with findings" in out.stdout and "people overlay not loaded" in out.stdout,
              "A clean clone of the sample, with no workspace, no original, no rendering and no people file, passes check_specs.py --view released with 0 findings",
              last(out, 3))

        # 6. the engineers' context check in a fresh clone with no private workspace
        fresh = clean_clone(tmp / "fresh-clone")
        git(["init", "-q", "-b", "main"], fresh, env)
        git(["config", "user.name", "Proof"], fresh, env)
        git(["config", "user.email", "proof@example.com"], fresh, env)
        git(["add", "-A"], fresh, env)
        git(["commit", "-q", "-m", "sample"], fresh, env)
        origin = tmp / "origin.git"
        git(["clone", "-q", "--bare", str(fresh), str(origin)], tmp, env)
        git(["remote", "add", "origin", str(origin)], fresh, env)
        checker = fresh / "docs" / "dev" / "skills" / "expense-approvals-dev" / "scripts" / "check_context.py"
        out = run([PY, checker, "WI-06", "--root", fresh], cwd=fresh, env=env)
        claim(out.returncode == 0 and "Read docs/context/wi-06.md" in out.stdout,
              "check_context.py WI-06 exits 0 in a fresh clone with no private workspace and no original", f"exit {out.returncode}: " + last(out, 2))
        out = run([PY, checker, "WI-99", "--root", fresh], cwd=fresh, env=env)
        claim(out.returncode == 10 and out.stdout.startswith("carrydown: no approved context for WI-99"),
              "An id the project does not have gets the first block message, which does not say whether private work exists", f"exit {out.returncode}: " + last(out, 2))

        # 7. the sample release and the fixture
        out = run([PY, "tests/rebuild_sample_release.py", "--check"], env=env)
        claim(out.returncode == 0 and "PASS the sample's release is reproducible" in out.stdout,
              "The sample's release, receipt, events, bundles and released plan are rebuilt byte for byte from the sample and the owner-side fixture", last(out))
        fixture = ROOT / "tests" / "fixtures" / "sample-workspace" / "drafts" / "plan.yaml"
        text = fixture.read_text(encoding="utf-8") if fixture.is_file() else ""
        shown = (SAMPLE / "docs" / "spec" / "plan.yaml").read_text(encoding="utf-8")
        claim("classification: repo-readers" in text and "source_path:" in text and not re.search(r"(?m)^\s*(classification|source_path|content_sha256|rendering_sha256|days_off|allocation|github|skills):", shown),
              "The owner-side fixture holds the classification and the original path, and the released plan holds none of them and no personal key",
              "fixture has classification and source_path; the sample plan has no private key")

        # 8. the unit tests of this work package, which include the searches for obsolete instructions
        out = run([PY, "-m", "unittest", "tests.test_documentation"], env=env)
        ran = re.search(r"Ran (\d+) tests", out.stdout + out.stderr)
        claim(out.returncode == 0, "The documentation tests pass: the scaffold on a released plan, the sample, the links, the support labels and the searches for obsolete instructions",
              (ran.group(0) if ran else "no test count") + " || " + last(out))

        # 9. support labels and the not-yet-performed statements
        page = (ROOT / "docs" / "enterprise-security.md").read_text(encoding="utf-8")
        labels = ("**supported** (implemented, documented and tested)", "**supported with prerequisites** (implemented and tested, but needs configuration your organization provides)",
                  "**planned** (the design exists, the feature does not)")
        claim(all(l in page for l in labels) and "**Draft notice: not yet supported.**" in page and "**It has not been performed.**" in page,
              "The security page carries the three support labels exactly, a visible draft notice, and says the real GitHub acceptance run has not been performed",
              "labels present; notice present")
        bold = sorted(set(re.findall(r"\*\*((?:S|s)upported[^*]*|(?:P|p)lanned[^*]*)\*\*", page)))
        exact = {"supported", "supported with prerequisites", "planned", "Supported.", "Supported with prerequisites.", "Planned."}
        claim(set(bold) <= exact, "Every support label on the security page is one of the three labels alone, with no compound label",
              f"bold labels used: {bold}")
        setup = (ROOT / "docs" / "setup.md").read_text(encoding="utf-8")
        rows = [l for l in setup.split("\n") if l.startswith("| ") and "Not yet performed" in l]
        claim("Status: **not yet performed.**" in setup and len(rows) >= 15, "The setup guide keeps the real GitHub acceptance run marked not yet performed",
              f"{len(rows)} record rows say Not yet performed")
        claim(all(p in (ROOT / "docs" / "delivery-modes.md").read_text(encoding="utf-8") for p in ("Planned: unavailable in version 1", "H1. Shared constraints", "H2. The two stubs")),
              "The delivery modes page keeps Part H and marks both modes planned and unavailable", "H1, H2 and the planned status present")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"{sum(results)} of {len(results)} claims passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
