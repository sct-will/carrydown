#!/usr/bin/env python3
"""Assemble the files of a release from the owner's plan. Offline. Standard library only.

assemble() reads the workspace plan, the specifications, the renderings and the staffing overlay, and
returns everything a release would put in its snapshot, in memory, without writing anywhere:

  repo/docs/spec/plan.yaml     the released plan, projected from the workspace plan (E1)
  repo/<spec folder>/...       the Markdown specifications, milestones and README
  repo/docs/context/...        one approved context bundle per work item (compile_bundles.py)
  repo/<engineers' skill>/...  the engineers' skill folder (generate_dev_skill.py)
  payloads/<destination>/...   one payload per GitHub target (release_payloads.py)

release.py preview, prepare and diff share it, so what the owner previews is what prepare snapshots.
The owner's drafting location decides where each input is read from: the private workspace
(drafts/ and renderings/) when it holds the draft, the project otherwise.

This module is imported by the other scripts. Run with --help to see this text.
"""
import argparse
import sys
from pathlib import Path
from typing import NamedTuple, Optional

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import compile_bundles as CB  # noqa: E402
import detectors as D  # noqa: E402
import generate_dev_skill as GD  # noqa: E402
import release_payloads as RP  # noqa: E402
import release_schema as RS  # noqa: E402

SKIPPED_SPEC_FILES = ("plan-review.md",)
HAND_EDITED = ("SKILL.md", "README.md")
GITHUB_DESTINATIONS = ("issue", "subepic", "epic", "epic-comment", "label", "board")


class Assembly(NamedTuple):
    root: Path
    workspace: Optional[Path]
    plan_path: Optional[Path]
    plan: Optional[dict]
    staffed: Optional[dict]
    mode: str                  # "yes" or "no"
    spec_base: Optional[Path]
    files: dict                # snapshot path -> bytes
    rows: list                 # (item tag, label, present, total) from the bundle compile
    sources: list              # [{"id", "version"}]
    destinations: list         # in canonical order
    flags: dict                # downstream flags
    findings: list             # detector findings after recorded exceptions
    resolution: object         # detectors.Resolution of the raw findings
    problems: list             # one-line messages; the release cannot be prepared while any exist
    notes: list                # limitations the preview shows
    restricted_items: int
    payload_paths: tuple       # the payload paths among files


def _empty(root, workspace, problems):
    return Assembly(Path(root), workspace, None, None, None, "yes", None, {}, [], [], [], {}, [], None, list(problems), [], 0, ())


def drafting_base(plan, root, workspace):
    """The folder that holds the specification: the workspace drafts folder when it has the draft."""
    rel = plan["project"]["spec_dir"]
    if workspace is not None and (Path(workspace) / "drafts" / rel).is_dir():
        return Path(workspace) / "drafts"
    return Path(root)


def spec_files(plan, spec_base):
    """{repository path: bytes} of the Markdown files of the specification folder, except the plan
    review and the specifications of restricted items."""
    rel = plan["project"]["spec_dir"]
    folder = Path(spec_base) / rel
    skip = set()
    for it in plan["items"]:
        if L.restricted_item(it):
            skip.add(L.spec_path(plan, spec_base, it).resolve())
    out = {}
    if not folder.is_dir():
        return out
    for path in sorted(folder.rglob("*.md")):
        if path.is_symlink() or not path.is_file() or path.name in SKIPPED_SPEC_FILES or path.resolve() in skip:
            continue
        out[f"{rel}/{path.relative_to(folder).as_posix()}"] = path.read_bytes()
    return out


def assemble(root, *, plan_path=None, with_github=True, with_board=True, exceptions=(), flag_overrides=None,
             destinations=None, skip_detectors=False):
    """The Assembly for the project at root. Never writes. A problem is a line in problems; the other
    fields are filled as far as the inputs allow."""
    root = Path(root).resolve()
    workspace, why = L.workspace_root(root)
    problems, notes = [], []
    plan_path = CB.locate_plan(root, workspace, plan_path)
    if not L.exists(plan_path):
        return _empty(root, workspace, [f"no plan at {plan_path.name}"])
    try:
        plan, plan_problems = L.load_plan(plan_path, root)
    except L.PlanError as e:
        return _empty(root, workspace, [e.msg.split("\n")[0][:200]])
    if plan_problems:
        return _empty(root, workspace, ["the plan has problems. Run check_specs.py and fix them first"] + [f"  - {p}" for p in plan_problems[:5]])
    if plan.get("_view") == "released":
        return _empty(root, workspace, ["this is a released plan: it has no source paths. Prepare from the workspace plan (schema-view-mismatch)"])
    if not plan.get("_modern"):
        return _empty(root, workspace, ["this is a legacy project with no handling policy, so there is nothing to release yet (no-handling-policy). "
                                        "Run step 0 of the ground-truth skill first"])
    handling = plan["project"].get("handling") or {}
    mode = "yes" if handling.get("repo_audience_approved") is True else "no"
    merged = None
    try:
        merged, _ = L.load_plan_with_people(plan_path, root)
    except L.PlanError:
        merged = None
    staffed = merged if merged is not None and merged.get("_people_overlay") else None
    base = drafting_base(plan, root, workspace)
    renderings, bad = CB.locate_renderings(plan, root, workspace, why, None)
    if renderings is None:
        return _empty(root, workspace, [bad])
    spec_dir = CB.locate_spec_dir(plan, root, workspace, None)
    result = CB.compile_report(plan, renderings, spec_dir)
    problems += list(result.problems)
    files = {}
    if not result.problems:
        for path, data in result.files.items():
            files["repo/" + path] = data
    for path, data in spec_files(plan, base).items():
        files["repo/" + path] = data
    live = [it for it in plan["items"] if not L.restricted_item(it)]
    for it in live:
        sp = L.spec_path(plan, base, it)
        if not sp.is_file():
            problems.append(f"the specification of {L.tag(plan, it['id'])} does not exist yet. Run scaffold_spec.py --stubs and write it")
    if not (Path(base) / plan["project"]["spec_dir"] / "README.md").is_file():
        problems.append(f"{plan['project']['spec_dir']}/README.md does not exist yet. Run scaffold_spec.py --apply")
    try:
        files["repo/" + plan["project"]["spec_dir"] + "/plan.yaml"] = L.released_plan_bytes(plan)
    except (L.PlanViewError, L.PlanError) as e:
        problems.append(str(e)[:200])
    flags = dict(L.downstream_flags(plan))
    down = handling.get("downstream") if isinstance(handling.get("downstream"), dict) else {}
    flags["evidence"] = down.get("evidence") if down.get("evidence") in RS.EVIDENCE else "synthetic-only"
    for k, v in (flag_overrides or {}).items():
        if v is not None:
            flags[k] = v
    skill_prefix = plan["project"].get("dev_skill_path")
    if skill_prefix and live and not result.problems:
        try:
            for rel, text in GD.skill_files(plan, base, bundles=result.files).items():
                data = text.encode("utf-8")
                kept = Path(base) / skill_prefix / rel
                if rel in HAND_EDITED and kept.is_file() and not kept.is_symlink():
                    data = kept.read_bytes()       # SKILL.md and README.md keep the owner's edits
                files["repo/" + skill_prefix + "/" + rel] = data
        except SystemExit as e:
            problems.append(str(e)[:200] or "the engineers' skill cannot be generated")
    payload_paths = ()
    if with_github and plan["project"].get("repo") and live and not result.problems:
        view = dict(plan, items=live)
        staffed_view = dict(staffed, items=[it for it in staffed["items"] if not L.restricted_item(it)]) if staffed else None
        try:
            payloads = RP.build_payloads(view, base, staffed=staffed_view, flags=flags, with_board=with_board)
        except (L.TextError, KeyError, ValueError) as e:
            problems.append(f"the GitHub payloads cannot be built: {str(e)[:120]}")
            payloads = {}
        files.update(payloads)
        payload_paths = tuple(sorted(payloads))
    elif with_github and not plan["project"].get("repo"):
        notes.append("project.repo is not set in the plan, so no GitHub payload was built and the release has no GitHub destination")
    available = ["engineering-repo"]
    if skill_prefix and any(p.startswith("repo/" + skill_prefix + "/") for p in files):
        available.append("engineers-skill")
    kinds = {p.split("/")[1] for p in payload_paths}
    available += [k for k in GITHUB_DESTINATIONS if k in kinds]
    chosen = [d for d in RS.DESTINATIONS if d in (destinations if destinations else available) or d == "engineering-repo"]
    unknown = sorted(set(destinations or []) - set(available))
    if unknown:
        problems.append("this release has no files for the destination(s): " + ", ".join(unknown))
    # drop the files of a destination the owner left out, so a payload that is not approved is not in the snapshot
    for kind in GITHUB_DESTINATIONS:
        if kind not in chosen:
            for p in [p for p in files if p.startswith(f"payloads/{kind}/")]:
                del files[p]
    if "engineers-skill" not in chosen and skill_prefix:
        for p in [p for p in files if p.startswith("repo/" + skill_prefix + "/")]:
            del files[p]
    findings, resolution = [], None
    if not skip_detectors and not result.problems:
        raw = D.find_all(root, workspace, {p: data for p, data in files.items()}, plan_path=plan_path)
        resolution = D.resolve(raw, exceptions)
        findings = list(resolution.unresolved)
        for index, code, _ in resolution.refused:
            findings.append(D.Finding("exceptions", code, f"detector_exceptions:{index}"))
    sources = [{"id": s["id"], "version": str(s.get("version") or "unversioned")} for s in plan["sources"]]
    return Assembly(root, workspace, plan_path, plan, staffed, mode, base, files, result.rows, sources, chosen, flags,
                    findings, resolution, problems, notes, sum(1 for it in plan["items"] if L.restricted_item(it)),
                    tuple(p for p in payload_paths if p in files))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Assemble the files of a release from the owner's plan, in memory. A library: import it, do not run it. "
                    "release.py preview, prepare and diff use it.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
