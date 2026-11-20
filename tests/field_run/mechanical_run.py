#!/usr/bin/env python3
"""Run the expected command sequence of the update path by hand, with no agent, on a prepared sample field run.

It is the proof that the prepared starting point works end to end, and the reference the measure script compares
an agent's command log with. Every command goes through run_logged.py, so transcript/commands.log has the same
lines an agent's run has. No question is asked and no owner message is written, so measure_field_run.py reports
zero owner interactions for this run. That is expected.

  python3 tests/field_run/mechanical_run.py --dir DIR

DIR is a folder made by prepare_field_run.py for the sample. The script renders the revised document, runs
status, prepare (preview and save), fills dispositions.json from the blocks prepare reports, runs check, runs
apply (preview and write) and records the accepted checkpoint (each command a preview first). It never
releases, never pushes and never calls GitHub. Standard library only.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REMINDER_OLD = ("Reminders. The business analyst note asks for 2 business days (section 6.1 and 6.2 item 6). Section 3.5 says 3. "
                "Use 3. The next version of the document should settle the number.")
REMINDER_NEW = ("Reminders. The business analyst note asked for 2 business days (section 6.1 and 6.2 item 6), and section 3.5 now says 2. "
                "Use 2.")
DELEGATE_OLD = "A delegate may act only for dates inside the delegate record, and never on a report that the delegator submitted."
DELEGATE_NEW = (DELEGATE_OLD + " A delegate's approval counts only for a base total up to 5,000.00, whatever the delegator's own limit is.")
WATCH = "## Watch out for\n\n"
GOV3 = ("- GOV-3, section 4.3, adds an event type. A decision made by a delegate writes one audit_event of type `delegate.decision` in the "
        "same transaction, with the delegate and the replaced approver as identifiers and no name or comment. A refused delegated "
        "decision is recorded with the number of the rule that refused it.\n")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Runner:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.project = self.folder / "project"
        self.helper = self.folder / "run_logged.py"
        self.gt = self.folder / "install" / "carrydown-ground-truth" / "scripts"
        self.log = []

    def run(self, *args, expect=(0,)):
        cmd = [sys.executable, str(self.helper), "--", "python3"] + [str(a) for a in args]
        out = subprocess.run(cmd, cwd=str(self.project), capture_output=True, text=True)
        self.log.append((args, out.returncode))
        if out.returncode not in expect:
            raise SystemExit(f"unexpected exit {out.returncode}: {' '.join(str(a) for a in args[:4])}\n{out.stdout}{out.stderr}")
        return out.stdout

    def script(self, name, *args, **more):
        return self.run(self.gt / name, *args, **more)


def patch(item, path, before, after):
    return {"item": item, "path": path, "before_sha256": sha(before), "after_text": after}


def split_decisions(text):
    marker = "\n## Decisions recorded\n"
    head, sep, tail = text.partition(marker)
    return head, sep + tail


def build_dispositions(project, doc, manifest):
    """One disposition for every block of the proposal, with the patches the sample's revision calls for."""
    spec = project / "docs" / "spec"
    wi03 = spec / "m2-route-to-approvers" / "wi-03-routing-engine.md"
    wi06 = spec / "m3-enforce-policy" / "wi-06-limits-and-duties.md"
    wi07 = spec / "m3-enforce-policy" / "wi-07-audit-log.md"
    wi08 = spec / "m3-enforce-policy" / "wi-08-notifications-delegates.md"
    rel = lambda p: p.relative_to(project).as_posix()  # noqa: E731
    texts = {p: p.read_text(encoding="utf-8") for p in (wi03, wi06, wi07, wi08)}

    def edit(path, *pairs):
        head, tail = split_decisions(texts[path])       # an engineer's entry is never part of an edit
        for old, new in pairs:
            if old not in head:
                raise SystemExit(f"the text this run edits is not in {rel(path)}: {old[:60]}")
            head = head.replace(old, new)
        return head + tail

    reminder = [("after 3 business days", "after 2 business days"), (REMINDER_OLD, REMINDER_NEW)]
    p03 = patch("WI-03", rel(wi03), texts[wi03], edit(wi03, *reminder))
    # WI-08 changes for two blocks, and one file takes one patch: the 3.5 record carries it, and says so
    both08 = edit(wi08, ("after 3 business days", "after 2 business days"), (DELEGATE_OLD, DELEGATE_NEW))
    p08 = patch("WI-08", rel(wi08), texts[wi08], both08)
    p06 = patch("WI-06", rel(wi06), texts[wi06], edit(wi06, (DELEGATE_OLD, DELEGATE_NEW)))
    p07 = patch("WI-07", rel(wi07), texts[wi07], edit(wi07, (WATCH, WATCH + GOV3)))
    out = []
    for rec in doc["dispositions"]:
        block = rec["block"]
        if rec.get("disposition") != "pending":
            out.append(rec)
        elif block == "architecture/3.5":
            out.append({"block": block, "disposition": "update", "item": "WI-03", "patch": [p03, p08],
                        "note": "The reminder is due after 2 business days (WI-03, WI-08). The WI-08 patch also carries the delegate sentence of 4.1, "
                                "because one file takes one patch. The engineer's recorded entry in WI-03 is kept as written."})
        elif block == "architecture/4.1":
            out.append({"block": block, "disposition": "update", "item": "WI-06", "patch": p06,
                        "note": "WI-06 states GOV-1.4 and its limits. WI-08 quotes GOV-1.4 and is patched with the 3.5 record."})
        elif block.startswith("architecture/none>4.3"):
            out.append({"block": block, "disposition": "update", "item": "WI-07", "patch": p07,
                        "note": "Nothing cites section 4.3. WI-07 owns the audit writer and its event types, so it names the new event type."})
        else:
            out.append({"block": block, "disposition": "no-impact",
                        "reason": "The edge case only restates the 3.5 change, which is handled in the WI-03 patch.",
                        "context": "WI-03, WI-02 and WI-08 cite section 6.2. WI-03 says to use the number 3.5 gives."})
    return {"format": 1, "dispositions": out}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="the field-run folder made by prepare_field_run.py for the sample")
    a = ap.parse_args(argv)
    r = Runner(a.dir)
    manifest = json.loads((r.folder / "field-run.json").read_text(encoding="utf-8"))
    if manifest.get("mode") != "sample":
        print("error: this script knows the sample's revision only", file=sys.stderr)
        return 2
    workspace = (r.folder / manifest["workspace"]).resolve()
    r.run(r.gt / "check_python.py")
    r.script("reconcile.py", "status", "--root", ".")
    r.script("render_ground_truth.py", f"../revision/{manifest['revised_file']}", "--root", ".", "--version", "0.4", "--dry-run")
    r.script("render_ground_truth.py", f"../revision/{manifest['revised_file']}", "--root", ".", "--version", "0.4")
    r.script("reconcile.py", "status", "--root", ".")
    r.script("reconcile.py", "prepare", "--root", ".")
    made = r.script("reconcile.py", "prepare", "--root", ".", "--apply")
    pid = re.search(r"^proposal: ([0-9a-f]{64})$", made, re.M).group(1)
    folder = workspace / "drafts" / "proposals" / pid
    doc = json.loads((folder / "dispositions.json").read_text(encoding="utf-8"))
    doc = build_dispositions(r.project, doc, manifest)
    (folder / "dispositions.json").write_bytes((json.dumps(doc, indent=2) + "\n").encode("utf-8"))
    r.script("reconcile.py", "check", "--root", ".", "--proposal", pid)
    r.script("reconcile.py", "apply", "--root", ".", "--proposal", pid)
    r.script("reconcile.py", "apply", "--root", ".", "--proposal", pid, "--apply")
    descriptor = folder / "descriptor.json"
    prep = ["checkpoint", "prepare", "--root", ".", "--descriptor", descriptor, "--rendering-dir", "docs/ground-truth"]
    r.script("workspace.py", *prep)
    out = r.script("workspace.py", *prep, "--apply")
    cid = re.search(r"checkpoint ([0-9a-f]{64})", out).group(1)
    r.script("workspace.py", "checkpoint", "commit", "--root", ".", "--id", cid)
    r.script("workspace.py", "checkpoint", "commit", "--root", ".", "--id", cid, "--apply")
    r.script("reconcile.py", "status", "--root", ".")
    print(f"mechanical run finished: {len(r.log)} commands, proposal {pid[:12]}, all exit codes as expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
