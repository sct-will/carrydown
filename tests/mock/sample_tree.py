"""Copies of the sample project, in the two states a test can need.

The committed sample (sample/expense-approvals) is a project after its release. Its docs/spec/plan.yaml
is the released plan, with no source path, no classification and no digest, and with ids and tracks for
the people. That is what a clean clone holds.

Most tests exercise the owner's side: they prepare releases, publish, repair or refresh a project the owner
is still drafting. For those the project must look as it did while the owner drafted, so copy_sample puts the
owner's working plan (the workspace view, kept in tests/fixtures/sample-workspace/drafts/plan.yaml) in
place of the released plan. Pass working=False for the project exactly as it is committed.

The working plan is the input of the sample's release (tests/rebuild_sample_release.py), and the released plan
is its exact projection, so the two always agree on every schedule fact.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE = ROOT / "sample" / "expense-approvals"
WORKING_PLAN = ROOT / "tests" / "fixtures" / "sample-workspace" / "drafts" / "plan.yaml"


def copy_sample(dst, working=True, ignore=None, source=None):
    """Copy the sample project to dst and return dst.

    working=True (the default) replaces docs/spec/plan.yaml with the owner's working plan, so the copy is the
    project as the owner drafted it. working=False keeps the released plan, as committed. source overrides
    the sample folder, for a test that starts from another copy."""
    src = Path(source) if source is not None else SAMPLE
    shutil.copytree(str(src), str(dst), ignore=ignore)
    if working:
        shutil.copyfile(str(WORKING_PLAN), str(Path(dst) / "docs" / "spec" / "plan.yaml"))
    return dst
