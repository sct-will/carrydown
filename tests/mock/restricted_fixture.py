"""A copy of the sample with one restricted work item, for the tests of work package 9. Standard library only.

  restricted_project(base, ...)   a release_fixture.YesProject whose plan marks work item 7 (Audit log and
                                  retention) restricted. Other files that named it by its label or its id are
                                  reworded, as an owner would have to do: the checker forbids a specification to
                                  name an external item, and the release refuses a file that holds the label.
                                  The drafts live in the private workspace (drafts/), as the preview advises
                                  for a project that has restricted work items, so the engineering repository
                                  holds nothing yet that a first release would overwrite.

The private fields of the restricted item can be changed with keyword arguments, which is how the tests show
that nothing of them reaches the release: label, slug, theme, size and the text of its specification. SUMMARY
and INSTRUCTION are what the owner writes for the summary and the placeholder.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import release_fixture as F  # noqa: E402

ITEM = 7                    # the work item that is restricted
LABEL = "Audit log and retention"
SUMMARY = "Retention rules are decided outside this project."
INSTRUCTION = "Ask the records office for the retention rule. Do not implement retention here."


def _item_block(text, item_id):
    start = text.index(f"  - id: {item_id}\n")
    end = text.find("\n  - id: ", start + 1)
    return start, (end + 1 if end != -1 else len(text))


def restricted_project(base, summary=SUMMARY, placeholder=None, label=LABEL, slug=None, theme=None, size=None, extra_spec_line=None,
                       board=False, private_drafts=True, restrict=True):
    """A YesProject whose work item 7 is restricted. placeholder is the owner's instruction, or None for no
    placeholder. The other keywords replace private fields of the restricted item. restrict=False leaves the
    item unrestricted (the same project, for comparison)."""
    yp = F.YesProject(base, board=board)
    root = yp.root
    plan_path = root / "docs" / "spec" / "plan.yaml"
    text = plan_path.read_text(encoding="utf-8")
    start, end = _item_block(text, ITEM)
    block = text[start:end]
    block = block.replace('label: "Audit log and retention"', f'label: "{label}"')
    if slug:
        block = re.sub(r"(?m)^    slug: .*$", f"    slug: {slug}", block)
    if theme:
        block = re.sub(r"(?m)^    theme: .*$", f'    theme: "{theme}"', block)
    if size:
        block = re.sub(r"(?m)^    size: .*$", f'    size: "{size}"', block)
    if restrict:
        extra = f'    restricted: true\n    restricted_summary: "{summary}"\n'
        if placeholder:
            extra += f'    restricted_placeholder: "{placeholder}"\n'
        marker = block.index("    complete_by")
        block = block[:marker] + extra + block[marker:]
    plan_path.write_text(text[:start] + block + text[end:], encoding="utf-8")
    spec_root = root / "docs" / "spec"
    if restrict:
        # the sample's other files name the item by its label and its id: reword them, as an owner would
        for path in sorted(spec_root.rglob("*.md")):
            if path.name.startswith("wi-07"):
                continue
            body = path.read_text(encoding="utf-8")
            new = re.sub(r"\[WI-07 Audit log and retention\]\([^)]*\)", "WI-07", body)
            new = re.sub(r"\[[^\]]*\]\((?:\.\./m3-enforce-policy/)?wi-07-audit-log\.md\)", "the retention work", new)
            new = re.sub(r"(?i)audit log and retention", "the retention work", new)
            new = re.sub(r"\bWI-07\b", "the retention work", new)
            if new != body:
                path.write_text(new, encoding="utf-8")
    spec = next(spec_root.rglob("wi-07-*.md"))
    if label != LABEL or extra_spec_line:
        body = spec.read_text(encoding="utf-8").replace(f"# WI-07 {LABEL}", f"# WI-07 {label}", 1)
        if extra_spec_line:
            body = body.rstrip("\n") + "\n\n" + extra_spec_line + "\n"
        spec.write_text(body, encoding="utf-8")
    if slug:
        spec.rename(spec.with_name(f"wi-07-{slug}.md"))
    for folder in ("context", "dev", "release"):
        shutil.rmtree(root / "docs" / folder, ignore_errors=True)
    if private_drafts:
        drafts = yp.workspace / "drafts"
        (drafts / "docs").mkdir(parents=True, exist_ok=True)
        shutil.move(str(plan_path), str(drafts / "plan.yaml"))
        shutil.move(str(spec_root), str(drafts / "docs" / "spec"))
    yp.drafts = (yp.workspace / "drafts") if private_drafts else root
    return yp
