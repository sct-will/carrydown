#!/usr/bin/env python3
"""The migration inventory of a project (specification WP8, item 6). Offline. Standard library only.

`release.py inventory --root .` calls inventory() and prints its lines. It reads the working tree and
the git history of the engineering repository and writes nothing: no file, no commit, no branch. It
reports, for the owner of a project that was set up before releases existed

  tracked originals     files of the project's sources that git tracks (the source_path of each source,
                        and the docs/source/ folder)
  tracked renderings    the numbered Markdown made from them (the path of each source, and the folder
                        that holds them)
  staffing fields       fields of people in tracked files, as people:<id>:<field>, never a value, and
                        whether a people.yaml is tracked
  generated references  the reference files of the engineers' skill, which earlier versions filled with
                        original file names and coverage notes
  history               whether any of those paths, or staffing fields in the plan, appear in git history
                        (git log --all --diff-filter=A), including files removed since

Carrydown cannot rewrite git history. Removing a file from the tree does not remove it from earlier
commits, from clones or from forks. The report says so and links GitHub's own guidance. Running this
command is the first step of migrating a legacy project: the owner then answers the one question in step
0 of the ground-truth skill.

This module is imported by release.py. Run with --help to see this text.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402

GUIDANCE_URL = "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository"
STAFFING_GREP = "^[[:space:]]+(name|github|skills|preferences|assignment_rationale|days_off|allocation|start):"
SOURCE_FOLDER = "docs/source"
RENDERING_FOLDER = "docs/ground-truth"


def git(root, *args, timeout=60):
    """(status, stdout text). A missing git or a timeout is status 127."""
    try:
        done = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return done.returncode, done.stdout.decode("utf-8", "replace")


def tracked_files(root):
    status, out = git(root, "ls-files", "-z")
    if status != 0:
        return None
    return [p for p in out.split("\0") if p]


def _under(path, folder):
    return path == folder or path.startswith(folder.rstrip("/") + "/")


def first_added(root, pathspecs):
    """{path: short sha of the oldest commit that added it} for every file ever added under the pathspecs,
    on any branch, including files removed since."""
    if not pathspecs:
        return {}
    status, out = git(root, "log", "--all", "--relative", "--diff-filter=A", "--name-only", "--pretty=format:@%h", "--", *pathspecs, timeout=120)
    if status != 0:
        return {}
    found, current = {}, None
    for line in out.splitlines():
        if line.startswith("@"):
            current = line[1:]
        elif line.strip() and current:
            found[line.strip()] = current       # git lists newest first, so the last one seen is the oldest
    return found


def staffing_commits(root, plan_rel):
    """Short shas of the commits that touched a staffing field of the plan file, on any branch."""
    status, out = git(root, "log", "--all", "--relative", "--extended-regexp", "--pretty=format:%h", "-G" + STAFFING_GREP, "--", plan_rel, timeout=120)
    return [x for x in out.split() if x] if status == 0 else []


def staffing_locations(plan):
    """people:<id>:<field> for each staffing field of a person in the plan, and advisors when present."""
    out = []
    for n, p in enumerate(plan.get("people") or [], 1):
        if not isinstance(p, dict):
            continue
        who = p.get("id") if isinstance(p.get("id"), str) and p.get("id") else f"#{n}"
        out += [f"people:{who}:{k}" for k in L.STAFFING_KEYS if k in p]
    if plan.get("advisors"):
        out.append("advisors")
    return out


def inventory(root):
    """The lines of the report, in order. Writes nothing."""
    root = Path(root)
    lines = ["carrydown release inventory (reads the working tree and the git history; writes nothing)"]
    files = tracked_files(root)
    if files is None:
        lines += ["This folder is not inside a git repository, so there are no tracked files and no history to inventory.",
                  "Nothing was changed."]
        return lines
    plan, plan_rel = None, None
    plan_path = L.find_plan(root)
    if L.exists(plan_path):
        try:
            plan, _problems = L.load_plan(plan_path, root)
            plan_rel = plan_path.relative_to(root.resolve()).as_posix() if root.resolve() in plan_path.resolve().parents else None
        except L.PlanError:
            plan = None
    sources = (plan or {}).get("sources") or []
    originals = {s.get("source_path") for s in sources if s.get("source_path")}
    renderings = {s.get("path") for s in sources if s.get("path")}
    render_dirs = {str(Path(p).parent).replace("\\", "/") for p in renderings} or {RENDERING_FOLDER}
    skill = ((plan or {}).get("project") or {}).get("dev_skill_path")
    tracked = set(files)
    found_originals = sorted(p for p in tracked if p in originals or _under(p, SOURCE_FOLDER))
    found_renderings = sorted(p for p in tracked if p in renderings or (any(_under(p, d) for d in render_dirs) and p.endswith(".md")))
    found_references = sorted(p for p in tracked if skill and _under(p, skill.rstrip("/") + "/references"))
    staffing_files = sorted(p for p in tracked if Path(p).name == "people.yaml")
    plan_tracked = bool(plan_rel and plan_rel in tracked)
    locations = staffing_locations(plan) if plan and plan_tracked else []

    state = "unknown (no readable plan)"
    if plan is not None:
        handling = (plan.get("project") or {}).get("handling")
        state = "migrated (has a handling policy)" if isinstance(handling, dict) and handling else "legacy (no handling policy)"
    if (root / ".carrydown" / "release-policy.yaml").is_file():
        state += "; has a release policy pointer"
    lines.append(f"Project state: {state}")

    specs = list(found_originals) + list(found_renderings) + list(found_references) + staffing_files
    folders = sorted(set([SOURCE_FOLDER, *render_dirs] + ([skill.rstrip("/") + "/references"] if skill else [])))
    history = first_added(root, folders + sorted(originals | renderings) + ["people.yaml", ":(glob)**/people.yaml"])
    history_hits = sorted(p for p in history if (p in originals or p in renderings or _under(p, SOURCE_FOLDER)
                                                  or any(_under(p, d) for d in folders) or Path(p).name == "people.yaml"))
    staff_commits = staffing_commits(root, plan_rel) if plan_rel else []

    def block(title, rows):
        lines.append("")
        lines.append(f"{title}: {len(rows)}")
        for p in rows:
            note = ""
            if p in history:
                note = f"   in history, first added in commit {history[p]}"
            lines.append(f"  {p}{note}")

    block("Tracked originals", found_originals)
    block("Tracked renderings", found_renderings)
    lines.append("")
    lines.append(f"Staffing fields in tracked files: {len(locations) + len(staffing_files)}")
    for p in staffing_files:
        lines.append(f"  {p} is tracked" + (f"   in history, first added in commit {history[p]}" if p in history else ""))
    for loc in locations[:60]:
        lines.append(f"  {loc} in {plan_rel}")
    if len(locations) > 60:
        lines.append(f"  ... and {len(locations) - 60} more")
    block("Generated references of the engineers' skill", found_references)
    gone = sorted(p for p in history_hits if p not in tracked)
    lines.append("")
    lines.append("Git history (all branches)")
    lines.append(f"  {len([p for p in history_hits if p in tracked])} of the tracked paths above appear in history, and {len(gone)} more were removed from the tree since but are still in history.")
    for p in gone[:40]:
        lines.append(f"  removed since, still in history: {p}   first added in commit {history[p]}")
    if len(gone) > 40:
        lines.append(f"  ... and {len(gone) - 40} more")
    if staff_commits:
        lines.append(f"  staffing fields of {plan_rel} appear in {len(staff_commits)} commit(s); the newest is {staff_commits[0]}")
    lines.append("")
    if not (specs or locations or history_hits or staff_commits):
        lines.append("Nothing private was found in tracked files or in history.")
    else:
        lines.append("Carrydown cannot rewrite git history. Removing a file from the tree does not remove it from earlier commits, from clones or from forks.")
        lines.append(f"GitHub's guidance on removing sensitive data from a repository: {GUIDANCE_URL}")
    lines.append("Nothing was changed. This is the first step of migrating a legacy project. Next, answer the one question in step 0 of the ground-truth skill; "
                 "private staffing records and restricted sources then move to the private workspace.")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description="The migration inventory: tracked originals, renderings, staffing fields and generated references, "
                                             "and whether they are in git history. A library: release.py inventory calls it. Writes nothing.")
    ap.add_argument("--root", default=".", help="the engineering repository (default: current directory)")
    a = ap.parse_args(argv)
    for line in inventory(L.project_root(a.root)):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
