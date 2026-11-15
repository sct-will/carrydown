#!/usr/bin/env python3
"""Measure a field run of the update path against the targets of specification 3.6.

  python3 tests/field_run/measure_field_run.py --dir DIR

DIR is a folder made by prepare_field_run.py, after a run. The script reads the transcript folder
(questions.md, to_owner.md, commands.log, notes.md, observer.md) and the project state, prints a report and
writes report.md in DIR. It changes nothing else. It reports facts. It does not judge whether a patch is wise.

What it computes (each one is a function, so a test can call it on a synthetic transcript):

  interactions        the question blocks of transcript/questions.md: what the agent put to the owner
  unnecessary         a question whose "Persona entry" is none, missing or not listed in persona.md, and a
                      persona entry asked more than once
  owner_text          commands, flags, script names, digests, proposal ids and block references that the owner
                      messages (transcript/to_owner.md) show
  review              owner messages that have the review headings of templates/reconcile-review.md and a lead
                      sentence of counts
  states              whether the last owner message names the six states and the next action
  dispositions        whether every changed block has exactly one finished disposition (reconcile.py check, and
                      the same test run on the saved proposal when the update is already applied)
  preservation        whether the engineer entry planted in the WI-03 specification is still there word for word
  candidate           whether the uncited rule reached WI-07, in a disposition or in an owner message
  patches             for each patch: its file, the lines it changed, and whether the file now holds exactly the
                      patch text and the digest the apply journal recorded
  probes              the sample's expectations of the working drafts (a stale number left in a consumer, a
                      missing consumer), as facts for the observer to read
  elapsed             from the first logged command to the approval question, and the machine time
  deviations          commands.log compared with the update path of the skill: the expected sequence

Markers in the transcript files are documented in OWNER_AGENT_BRIEF.md. Standard library only. Python 3.9 or
later. No network. Exit 0 whenever the report was written, 2 for a folder that is not a field run.
"""
import argparse
import datetime as dt
import difflib
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

PERSONA_IDS = ["P1", "P2", "P3", "P4", "P5"]
REVIEW_HEADINGS = ["Proposed updates", "Reviewed and unchanged", "Decisions needed", "Disclosure effects", "Next action"]
STATE_LABELS = ["Draft reconciliation", "Release", "Engineering repository", "Issue updates", "Board updates", "Engineer action"]
NUMBER_WORDS = r"(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|No|\d+)"
LEAD = re.compile(r"^\W*" + NUMBER_WORDS + r"\s+(?:\w+\s+){0,5}?(?:needs?|conflicts?|follow-up|updates?|changes?)\b", re.I)
TARGET_INTERACTIONS = 2          # the review with its decisions, and the final approval

# what the owner must not see (specification 3.5 and 3.6)
FLAG = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")
SCRIPT = re.compile(r"\b[\w.-]+\.py\b|\bpython3?\b|\breconcile\b|\bdispositions?\.json\b|\bdescriptor\.json\b|\bproposal\.json\b|\binputs\.json\b", re.I)
HEX = re.compile(r"\b[0-9a-f]{12,}\b")
BLOCK_REF = re.compile(r"\b[a-z][a-z0-9-]*/(?:none>)?\d+(?:\.\d+)*(?:>\S+)?")
SHELL = re.compile(r"(?:^|\s|`)(?:\$ |cd |git (?:push|commit|add|checkout|reset|clone|fetch|status|diff|log) |cat |ls |sh |bash )")
SOFT = re.compile(r"\b(?:digest|sha-?256|checkpoint id|proposal id|change id)\b", re.I)

QUIET_EXIT_1 = {"diff", "grep", "egrep", "fgrep", "rg", "cmp", "test", "["}
FORBIDDEN_SCRIPTS = re.compile(r"^(?:release(?:_\w+)?|github_\w+|scaffold_spec|generate_dev_skill)\.py$")
NETWORK = {"curl", "wget", "gh", "ssh", "scp", "nc", "ncat"}
GIT_WRITE = {"push", "commit", "add", "checkout", "switch", "reset", "restore", "stash", "rm", "mv", "clean", "merge", "rebase",
             "tag", "cherry-pick", "revert", "pull", "apply", "am", "init", "clone"}
GIT_READ = {"status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "remote", "config", "branch", "blame", "grep", "cat-file",
            "describe", "fetch"}

COMMAND_LINE = re.compile(r"^\[(?P<time>[^\]]+)\]\s+exit=(?P<code>-?\d+)\s+\$\s?(?P<cmd>.*)$")
BLOCK_HEADER = re.compile(r"^#{2,3}\s*(?P<kind>[QMqm])\s*(?P<num>\d+)?\b[\s:.-]*(?P<rest>.*)$")
TIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?")


class MeasureError(Exception):
    pass


# ---------------------------------------------------------------------------
# Reading the transcript
# ---------------------------------------------------------------------------

def parse_time(text):
    """A datetime in UTC from the first time-like text in text, or None."""
    m = TIME.search(text or "")
    if not m:
        return None
    s = m.group(0).replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if not re.search(r"[+-]\d{2}:?\d{2}$", s):
        s += "+00:00"
    if re.search(r"T\d{2}:\d{2}[+-]", s):
        s = re.sub(r"T(\d{2}:\d{2})([+-])", r"T\1:00\2", s)
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    try:
        return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def blocks_of(text, kind):
    """The blocks of one kind ("Q" or "M") of a transcript file: [{"number", "time", "text", "fields"}]."""
    out, current = [], None
    for line in text.replace("\r\n", "\n").split("\n"):
        m = BLOCK_HEADER.match(line)
        if m:
            current = {"number": int(m.group("num")) if m.group("num") else len(out) + 1, "time": parse_time(m.group("rest")),
                       "kind": m.group("kind").upper(), "lines": [], "header": line}
            out.append(current)
            continue
        if current is not None:
            current["lines"].append(line)
    result = []
    for b in out:
        if b["kind"] != kind:
            continue
        body = "\n".join(b["lines"]).strip()
        fields = {}
        for line in b["lines"]:
            f = re.match(r"^\s*(Persona entry|Question|Answer)\s*:\s*(.*)$", line, re.I)
            if f:
                fields[f.group(1).lower()] = f.group(2).strip()
        result.append({"number": b["number"], "time": b["time"], "text": body, "fields": fields})
    return result


def questions(folder):
    return blocks_of(read(Path(folder) / "transcript" / "questions.md"), "Q")


def owner_messages(folder):
    return blocks_of(read(Path(folder) / "transcript" / "to_owner.md"), "M")


def parse_commands(text):
    """[{"time", "code", "raw", "tokens"}] from commands.log, and the number of lines that belong to no command.

    A line that does not start a log entry continues the entry before it, so a multi-line command (a python -c
    program, a here-document) is one command. Only text before the first entry is counted as not understood."""
    entries, unparsed = [], 0
    for line in text.replace("\r\n", "\n").split("\n"):
        m = COMMAND_LINE.match(line)
        if m:
            entries.append([m.group("time"), m.group("code"), [m.group("cmd")]])
        elif line.strip():
            if entries:
                entries[-1][2].append(line)
            else:
                unparsed += 1
    out = []
    for time, code, parts in entries:
        raw = "\n".join(parts).strip()
        try:
            tokens = shlex.split(raw)
        except ValueError:
            tokens = raw.split()
        out.append({"time": parse_time(time), "code": int(code), "raw": raw, "tokens": strip_wrapper(tokens)})
    return out, unparsed


def is_python(token):
    return bool(re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?|py", os.path.basename(token or ""), re.I))


def strip_wrapper(tokens):
    """The command without the run_logged.py helper in front of it."""
    if len(tokens) >= 2 and is_python(tokens[0]) and os.path.basename(tokens[1]) == "run_logged.py":
        rest = tokens[2:]
        return rest[1:] if rest and rest[0] == "--" else rest
    return tokens


def classify(tokens):
    """A dict describing one command: program, script (when a python script), args, skill folder, step name."""
    info = {"program": None, "script": None, "args": [], "skill": None, "step": None}
    if not tokens:
        return info
    if is_python(tokens[0]) and len(tokens) > 1 and tokens[1].endswith(".py"):
        info["program"] = "python"
        info["script"] = os.path.basename(tokens[1])
        info["args"] = tokens[2:]
        for name in ("carrydown-ground-truth", "carrydown-plan-to-github"):
            if name in tokens[1]:
                info["skill"] = name
    else:
        info["program"] = os.path.basename(tokens[0])
        info["args"] = tokens[1:]
    script, args = info["script"], info["args"]
    apply_flag = "--apply" in args
    if script == "check_python.py":
        info["step"] = "preflight"
    elif script == "reconcile.py" and args:
        sub = args[0]
        info["step"] = {"status": "status", "check": "check"}.get(sub)
        if sub == "prepare":
            info["step"] = "prepare-save" if apply_flag else "prepare-preview"
        if sub == "apply":
            info["step"] = "apply-write" if apply_flag else "apply-preview"
    elif script == "render_ground_truth.py":
        info["step"] = "render-preview" if "--dry-run" in args else "render"
    elif script == "workspace.py" and args[:1] == ["checkpoint"] and len(args) > 1:
        sub = args[1]
        if sub in ("prepare", "commit"):
            info["step"] = f"checkpoint-{sub}-" + ("write" if apply_flag else "preview")
        elif sub == "bind":
            info["step"] = "checkpoint-bind-write" if apply_flag else "checkpoint-bind-preview"
        else:
            info["step"] = "checkpoint-read"
    elif script == "workspace.py":
        info["step"] = "workspace-" + (args[0] if args else "other")
    return info


# ---------------------------------------------------------------------------
# Owner interactions, questions and owner-facing text
# ---------------------------------------------------------------------------

def persona_ids(entry):
    return [i.upper() if i.upper().startswith("P") else "none" for i in re.findall(r"\bP\d+\b|\bnone\b", entry or "", re.I)]


def measure_interactions(qs, listed=None):
    listed = set(listed or PERSONA_IDS)
    unnecessary, repeated, seen = [], [], {}
    for q in qs:
        ids = persona_ids(q["fields"].get("persona entry"))
        valid = [i for i in ids if i in listed]
        if not valid or "none" in ids:
            unnecessary.append({"number": q["number"], "question": q["fields"].get("question") or q["text"][:120],
                                "why": "marked as not listed (none)" if "none" in ids else "the persona does not list it"})
        for i in valid:
            seen.setdefault(i, []).append(q["number"])
    for i, nums in sorted(seen.items()):
        if len(nums) > 1:
            repeated.append({"entry": i, "questions": nums})
    approval = [q for q in qs if "P5" in persona_ids(q["fields"].get("persona entry"))]
    return {"count": len(qs), "target": TARGET_INTERACTIONS, "unnecessary": unnecessary, "repeated": repeated,
            "approval_question": approval[-1]["number"] if approval else None,
            "approval_time": (approval[-1]["time"] if approval else (qs[-1]["time"] if qs else None)),
            "has_approval": bool(approval)}


def measure_owner_text(messages):
    """Hard findings (a command, a flag, a script or file name, a digest, a block reference) and soft ones
    (the words digest or checkpoint id) in the owner messages."""
    hard, soft = [], []
    for m in messages:
        for lineno, line in enumerate(m["text"].split("\n"), 1):
            kinds = []
            if FLAG.search(line):
                kinds.append("flag")
            if SCRIPT.search(line):
                kinds.append("script or file name")
            if HEX.search(line):
                kinds.append("digest or identifier")
            if BLOCK_REF.search(line):
                kinds.append("block reference")
            if SHELL.search(line):
                kinds.append("shell command")
            if re.match(r"^#{1,4}\s*technical record\b", line.strip(), re.I):
                kinds.append("technical record")
            if kinds:
                hard.append({"message": m["number"], "line": lineno, "kinds": kinds, "text": line.strip()[:140]})
            elif SOFT.search(line):
                soft.append({"message": m["number"], "line": lineno, "text": line.strip()[:140]})
    return {"hard": hard, "soft": soft, "messages": len(messages)}


def heading_present(text, heading):
    return bool(re.search(r"^[#>*\s\-_]*" + re.escape(heading) + r"\b", text, re.I | re.M))


def lead_sentence(text):
    lines = [re.sub(r"^[#>*\s\-_]+", "", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln and not re.fullmatch(r"(?i)lead sentence\.?", ln)]
    for ln in lines[:6]:
        if LEAD.match(ln):
            return ln
    return None


def measure_review(messages):
    reviews = []
    for m in messages:
        found = [h for h in REVIEW_HEADINGS if heading_present(m["text"], h)]
        if len(found) >= 3:
            reviews.append({"message": m["number"], "headings": found, "lead_sentence": lead_sentence(m["text"])})
    return {"reviews": reviews, "count": len(reviews), "with_lead": sum(1 for r in reviews if r["lead_sentence"])}


def measure_states(messages):
    if not messages:
        return {"measured": False, "missing": STATE_LABELS, "next_action": False}
    tail = "\n".join(m["text"] for m in messages[-2:])
    missing = [s for s in STATE_LABELS if not re.search(re.escape(s), tail, re.I)]
    return {"measured": True, "missing": missing, "next_action": bool(re.search(r"Put the plan on GitHub", tail, re.I)),
            "pending_or_done": bool(re.search(r"\b(pending|done|accepted|verified|not yet)\b", tail, re.I))}


# ---------------------------------------------------------------------------
# Project state
# ---------------------------------------------------------------------------

def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


class Run:
    """The paths of one field-run folder."""

    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        manifest = self.folder / "field-run.json"
        if not manifest.is_file():
            raise MeasureError(f"{self.folder} is not a field run folder (no field-run.json)")
        try:
            self.manifest = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise MeasureError(f"field-run.json cannot be read: {e}")
        self.project = self.folder / self.manifest.get("project", "project")
        self.home = self.folder / self.manifest.get("home", "home")
        self.install = self.folder / self.manifest.get("install", "install")
        self.workspace = (self.folder / self.manifest["workspace"]).resolve() if self.manifest.get("workspace") else None
        self.proposals = (self.workspace / "drafts" / "proposals") if self.workspace else None

    def env(self):
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), PYTHONDONTWRITEBYTECODE="1")
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        for name in ("CARRYDOWN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
            env.pop(name, None)
        return env

    def resolve(self, rel):
        """The file a patch or a probe path names, or None. A path is relative to the drafting folder, or starts
        with project/ or workspace/."""
        if rel.startswith("project/"):
            candidates = [self.project / rel[len("project/"):]]
        elif rel.startswith("workspace/") and self.workspace:
            candidates = [self.workspace / rel[len("workspace/"):]]
        else:
            candidates = [self.project / rel] + ([self.workspace / "drafts" / rel] if self.workspace else [])
        for c in candidates:
            if c.is_file():
                return c
        return candidates[0]


def proposal_from_commands(commands):
    for c in reversed(commands):
        args = c["tokens"]
        if "--proposal" in args:
            i = args.index("--proposal")
            if i + 1 < len(args) and re.fullmatch(r"[0-9a-f]{64}", args[i + 1]):
                return args[i + 1]
    return None


def find_proposal(run, commands):
    """The id of the proposal the run worked on: the last one a command named, else the newest that has finished
    dispositions or blocks."""
    if not run.proposals or not run.proposals.is_dir():
        return None
    named = proposal_from_commands(commands)
    if named and (run.proposals / named).is_dir():
        return named
    candidates = []
    for d in run.proposals.iterdir():
        blocks = read(d / "blocks.json")
        try:
            n = len(json.loads(blocks).get("blocks", [])) if blocks else 0
        except ValueError:
            n = 0
        if n:
            candidates.append((d.stat().st_mtime, d.name))
    return max(candidates)[1] if candidates else None


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_core(run):
    path = run.install / "carrydown-ground-truth" / "scripts" / "reconcile_core.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("field_run_reconcile_core", str(path))
    mod = importlib.util.module_from_spec(spec)
    try:
        sys.modules["field_run_reconcile_core"] = mod
        spec.loader.exec_module(mod)
    except Exception:  # noqa: BLE001 - a damaged install is reported, never raised
        return None
    return mod


def measure_dispositions(run, proposal):
    """Does every changed block have one finished disposition. Runs reconcile.py check, and the same test on the
    saved proposal, because check does not look at the dispositions of a proposal that is already applied."""
    out = {"proposal": proposal, "blocks": None, "problems": [], "check_exit": None, "check_text": "", "complete": None}
    if not proposal:
        return out
    folder = run.proposals / proposal
    blocks_doc = load_json(folder / "blocks.json") or {}
    disp_doc = load_json(folder / "dispositions.json") or {}
    blocks = blocks_doc.get("blocks") or []
    records = disp_doc.get("dispositions") or []
    out["blocks"] = len(blocks)
    core = load_core(run)
    if core is not None:
        pending = {r.get("block") for r in records if isinstance(r, dict) and r.get("disposition") == "pending"}
        finished = []
        for r in records:
            if isinstance(r, dict) and r.get("disposition") == "pending":
                continue
            if isinstance(r, dict) and r.get("disposition") == "update" and isinstance(r.get("patch"), (dict, list)):
                r = dict(r)
                r["patch"] = json.dumps(r["patch"], sort_keys=True)
            finished.append(r)
        try:
            for p in core.validate_dispositions(blocks, finished):
                if p["code"] == "missing-disposition" and p["block"] in pending:
                    continue
                out["problems"].append(f"{p['code']}: {p['message']}")
        except Exception as e:  # noqa: BLE001
            out["problems"].append(f"the proposal could not be validated: {e}")
        for ref in sorted(x for x in pending if x):
            out["problems"].append(f"pending-disposition: {ref} still has a pending disposition")
    script = run.install / "carrydown-ground-truth" / "scripts" / "reconcile.py"
    if script.is_file() and run.project.is_dir():
        res = subprocess.run([sys.executable, str(script), "check", "--root", ".", "--proposal", proposal], cwd=str(run.project),
                             capture_output=True, text=True, env=run.env())
        out["check_exit"] = res.returncode
        out["check_text"] = (res.stdout + res.stderr).strip()
    out["complete"] = not out["problems"] and bool(blocks)
    return out


def patches_of(records):
    out = []
    for r in records:
        if not isinstance(r, dict) or r.get("disposition") != "update":
            continue
        p = r.get("patch")
        for one in (p if isinstance(p, list) else [p]):
            if isinstance(one, dict):
                out.append(dict(one, block=r.get("block")))
    return out


def split_entry(text, entry):
    return text.replace(entry, "") if entry else text


def baseline_text(run, rel):
    """The file as it was when the run was prepared, from the project's own history, or None."""
    commit = run.manifest.get("baseline_commit")
    if not commit or not (run.project / ".git").exists() or rel.startswith(("workspace/",)):
        return None
    path = rel[len("project/"):] if rel.startswith("project/") else rel
    res = subprocess.run(["git", "-C", str(run.project), "show", f"{commit}:{path}"], capture_output=True, text=True, env=run.env())
    return res.stdout if res.returncode == 0 else None


def measure_patches(run, proposal):
    folder = run.proposals / proposal if proposal else None
    records = (load_json(folder / "dispositions.json") or {}).get("dispositions", []) if folder else []
    journal = (load_json(folder / "journal.json") or {}) if folder else {}
    applied = (load_json(folder / "applied.json") or {}) if folder else {}
    journal_after = {}
    for e in journal.get("entries", []) if isinstance(journal, dict) else []:
        if isinstance(e, dict) and e.get("path"):
            journal_after[e["path"]] = e
    rows = []
    for p in patches_of(records):
        rel = p.get("path", "")
        target = run.resolve(rel)
        want = sha(p.get("after_text", "")) if isinstance(p.get("after_text"), str) else None
        have = sha_file(target)
        before = baseline_text(run, rel)
        added = removed = 0
        if before is not None and isinstance(p.get("after_text"), str):
            for line in difflib.unified_diff(before.splitlines(), p["after_text"].splitlines(), lineterm="", n=0):
                if line.startswith("+") and not line.startswith("+++"):
                    added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed += 1
        total = len((before or "").splitlines()) or None
        jrow = None
        for key, e in journal_after.items():
            if key.endswith(rel) or rel.endswith(key):
                jrow = e
        rows.append({"item": p.get("item"), "path": rel, "block": p.get("block"), "added": added, "removed": removed,
                     "file_lines": total, "large": bool(total and (added + removed) > max(40, total * 0.4)) if before is not None else None,
                     "allowed_path": bool(re.match(r"^(?:project/)?docs/spec/.*\.md$|^(?:project/|workspace/drafts/)?(?:docs/spec/)?plan\.yaml$", rel)),
                     "file_matches_patch": (have == want) if (have and want) else None,
                     "journal_matches": (jrow.get("after_sha256") == want and jrow.get("state") in ("verified", "written")) if jrow else None,
                     "changed_from_baseline": (before is not None and isinstance(p.get("after_text"), str) and before != p["after_text"]) if before is not None else None})
    return {"patches": rows, "applied_state": applied.get("state"), "journal_entries": len(journal_after)}


def measure_preservation(run):
    planted = run.manifest.get("planted_entry")
    if not planted:
        return {"applicable": False}
    target = run.resolve(planted["path"])
    text = read(target)
    after_heading = text.split("## Decisions recorded", 1)[-1] if "## Decisions recorded" in text else ""
    return {"applicable": True, "path": planted["path"], "survived": planted["text"] in text,
            "under_decisions_recorded": planted["text"] in after_heading, "file_found": bool(text)}


def measure_candidate(run, proposal, messages):
    spec = run.manifest.get("uncited")
    if not spec:
        return {"applicable": False}
    folder = run.proposals / proposal if proposal else None
    blocks = (load_json(folder / "blocks.json") or {}).get("blocks", []) if folder else []
    records = (load_json(folder / "dispositions.json") or {}).get("dispositions", []) if folder else []
    refs = [b["ref"] for b in blocks if b.get("kind") == "added" and (b.get("current_number") == spec["section"])]
    want = spec["expected_candidate"]
    in_disposition = any(isinstance(r, dict) and r.get("block") in refs and want in json.dumps(r) for r in records)
    in_message = any(want in m["text"] and re.search(r"\b" + re.escape(spec["section"]) + r"\b|GOV-3|audit", m["text"], re.I) for m in messages)
    return {"applicable": True, "section": spec["section"], "candidate": want, "blocks": refs, "block_found": bool(refs),
            "in_disposition": in_disposition, "in_owner_message": in_message, "named": in_disposition or in_message}


def measure_probes(run):
    entry = (run.manifest.get("planted_entry") or {}).get("text", "")
    rows = []
    for pr in run.manifest.get("probes", []):
        target = run.resolve(pr["path"])
        text = read(target)
        body = split_entry(text, entry)
        problems = [f"missing: {s}" for s in pr.get("must_contain", []) if s not in text]
        problems += [f"still present: {s}" for s in pr.get("must_not_contain", []) if s in text]
        problems += [f"still present outside the engineer entry: {s}" for s in pr.get("must_not_contain_outside_entry", []) if s in body]
        rows.append({"name": pr["name"], "path": pr["path"], "ok": bool(text) and not problems, "problems": problems or ([] if text else ["file not found"])})
    return rows


def fmt_seconds(seconds):
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    return f"{seconds // 60} min {seconds % 60:02d} s"


def measure_elapsed(commands, approval_time):
    times = [c["time"] for c in commands if c["time"]]
    out = {"first_command": times[0] if times else None, "last_command": times[-1] if times else None, "approval": approval_time}
    out["to_approval"] = (approval_time - times[0]).total_seconds() if times and approval_time else None
    out["machine"] = (times[-1] - times[0]).total_seconds() if len(times) > 1 else None
    return out


# ---------------------------------------------------------------------------
# Deviations from the skill
# ---------------------------------------------------------------------------

EXPECTED = [
    ("preflight", "the Python preflight (check_python.py), step 0 of the skill"),
    ("status", "route by project state: reconcile.py status, before any work"),
    ("render", "render the revised source with a new --version"),
    ("prepare-preview", "preview the comparison: reconcile.py prepare"),
    ("prepare-save", "save the proposal: reconcile.py prepare --apply"),
    ("check", "check the proposal: reconcile.py check"),
    ("apply-preview", "preview the writes: reconcile.py apply"),
    ("apply-write", "write the accepted patches: reconcile.py apply --apply"),
    ("checkpoint-prepare-preview", "preview the checkpoint copy: workspace.py checkpoint prepare"),
    ("checkpoint-prepare-write", "write the checkpoint copy: workspace.py checkpoint prepare --apply"),
    ("checkpoint-commit-preview", "preview the checkpoint commit: workspace.py checkpoint commit"),
    ("checkpoint-commit-write", "commit the checkpoint: workspace.py checkpoint commit --apply"),
]


def measure_deviations(commands, run=None, approval_time=None, owner_transcript=True):
    """Compare commands.log with the update path of the skill. Returns {"deviations": [...], "notes": [...], "sequence": [...]}."""
    dev, notes = [], []
    infos = [(c, classify(c["tokens"])) for c in commands]
    first = {}
    for i, (c, info) in enumerate(infos):
        if info["step"] and c["code"] == 0:
            first.setdefault(info["step"], i)

    def add(level, code, message, cmd=None):
        (dev if level in ("stop", "deviation") else notes).append({"level": level, "code": code, "message": message,
                                                                    "command": " ".join(cmd["raw"].split())[:160] if cmd else None})

    for i, (c, info) in enumerate(infos):
        script, prog, args = info["script"], info["program"], info["args"]
        if script and FORBIDDEN_SCRIPTS.match(script):
            add("stop", "forbidden-script", f"ran {script}. The run stops before any release, scaffold or GitHub script", c)
        elif script == "workspace.py" and args[:1] == ["init"]:
            add("stop", "replacement-workspace", "ran workspace.py init. An update never creates a replacement workspace", c)
        elif info["skill"] == "carrydown-plan-to-github":
            add("deviation", "other-skill", f"ran {script} from the publishing skill. The update path uses the planning skill's scripts and stops before release", c)
        if prog in NETWORK:
            add("stop", "network", f"ran {prog}. The run uses no network", c)
        if prog == "git" and args:
            sub = next((a for a in args if not a.startswith("-") and a not in ("-C",)), "")
            if args[:1] == ["-C"] and len(args) > 2:
                sub = next((a for a in args[2:] if not a.startswith("-")), "")
            if sub in GIT_WRITE:
                add("stop", "git-write", f"ran git {sub}. The agent never changes git history or the working tree by hand", c)
        if c["code"] == 1 and prog in QUIET_EXIT_1:
            continue        # diff, grep and cmp exit 1 for "found a difference" or "no match", not for a failure
        if c["code"] != 0:
            if info["step"] == "check":
                add("note", "check-findings", "reconcile.py check reported findings (exit %d). That is the normal fix loop" % c["code"], c)
            else:
                add("deviation", "command-failed", f"a command failed with exit {c['code']}", c)
    for step, text in EXPECTED:
        if step not in first:
            level = "note" if step == "preflight" else "deviation"
            add(level, "missing-step", f"no successful {step} command: {text}")
    order = [s for s, _ in EXPECTED]
    seen = [(first[s], s) for s in order if s in first]
    for (i1, s1), (i2, s2) in zip(seen, seen[1:]):
        if i1 > i2:
            add("deviation", "out-of-order", f"{s2} ran before {s1}. The skill's order is: " + ", ".join(order))
    # a write needs its preview first
    for write, preview in (("prepare-save", "prepare-preview"), ("apply-write", "apply-preview"), ("checkpoint-prepare-write", "checkpoint-prepare-preview"),
                           ("checkpoint-commit-write", "checkpoint-commit-preview"), ("render", "render-preview")):
        if write in first and (preview not in first or first[preview] > first[write]):
            add("deviation" if write != "render" else "note", "no-preview", f"{write} ran without its preview ({preview}) first. The skill says: preview, read it, then write")
    if "apply-write" in first:
        checks = [i for i, (c, info) in enumerate(infos) if info["step"] == "check" and i < first["apply-write"]]
        if not checks or infos[checks[-1]][0]["code"] != 0:
            add("deviation", "apply-without-check", "apply --apply ran without a passing check just before it")
    if "status" in first and "render" in first and first["render"] < first["status"]:
        add("deviation", "status-not-first", "the revised source was rendered before the project state was checked")
    if "prepare-save" in first and "render" in first and first["prepare-save"] < first["render"]:
        add("deviation", "compared-before-render", "the proposal was saved before the revised source was rendered, so it compared the old text")
    # approval before write
    if owner_transcript and "apply-write" in first and approval_time is not None:
        when = infos[first["apply-write"]][0]["time"]
        if when is not None and when < approval_time:
            add("deviation", "apply-before-approval", "the patches were written before the owner's approval question was recorded")
    if owner_transcript and "apply-write" in first and approval_time is None:
        add("deviation", "no-approval-recorded", "the patches were written and no approval question is recorded in questions.md")
    # render input
    for c, info in infos:
        if info["step"] == "render":
            if "--version" not in info["args"]:
                add("note", "render-without-version", "render ran without --version. The skill says to use a new version", c)
            if run is not None:
                want = run.manifest.get("revised_file")
                if want and not any(a.endswith(want) for a in info["args"]):
                    add("deviation", "render-other-file", f"render did not read the revised document {want} from revision/", c)
    # commands that are not part of the path, for the observer to read
    extra = [" ".join(c["raw"].split())[:120] for c, info in infos if not info["step"] and not (info["script"] and FORBIDDEN_SCRIPTS.match(info["script"]))]
    return {"deviations": dev, "notes": notes, "sequence": [i["step"] or (i["script"] or i["program"]) for _, i in infos],
            "other_commands": extra}


# ---------------------------------------------------------------------------
# The whole measurement
# ---------------------------------------------------------------------------

def verdict(value, ok_text="met", bad_text="not met"):
    if value is None:
        return "not measured"
    return ok_text if value else bad_text


def measure(folder):
    run = Run(folder)
    t = run.folder / "transcript"
    qs, msgs = questions(run.folder), owner_messages(run.folder)
    commands, unparsed = parse_commands(read(t / "commands.log"))
    owner_transcript = bool(qs or msgs)
    inter = measure_interactions(qs, run.manifest.get("persona_ids"))
    proposal = find_proposal(run, commands)
    res = {"folder": str(run.folder), "mode": run.manifest.get("mode"), "created": run.manifest.get("created"),
           "owner_sentence": run.manifest.get("owner_sentence"), "proposal": proposal, "commands": len(commands), "unparsed_log_lines": unparsed,
           "interactions": inter, "owner_text": measure_owner_text(msgs), "review": measure_review(msgs), "states": measure_states(msgs),
           "dispositions": measure_dispositions(run, proposal), "patches": measure_patches(run, proposal),
           "preservation": measure_preservation(run), "candidate": measure_candidate(run, proposal, msgs),
           "probes": measure_probes(run), "elapsed": measure_elapsed(commands, inter["approval_time"]),
           "deviations": measure_deviations(commands, run, inter["approval_time"], owner_transcript),
           "notes": read(t / "notes.md").strip(), "observer": read(t / "observer.md").strip(), "owner_transcript": owner_transcript}
    res["targets"] = targets(res)
    return res


def targets(r):
    """The section 3.6 targets and the checks that go with them, each as (name, verdict, evidence)."""
    rows = []
    has = r["owner_transcript"]
    inter, review, text, states = r["interactions"], r["review"], r["owner_text"], r["states"]
    rows.append(("One initiating owner sentence", "met" if has else "not measured",
                 "the owner's only input is the first sentence" if has else "no owner transcript: no agent ran"))
    rows.append(("One compact review", ("met" if review["count"] == 1 and review["with_lead"] == 1 else "not met") if has else "not measured",
                 f"{review['count']} review message(s), {review['with_lead']} with the lead sentence"))
    ok = has and inter["count"] <= inter["target"] and inter["has_approval"]
    rows.append(("One final approval interaction", ("met" if ok else "not met") if has else "not measured",
                 f"{inter['count']} owner interaction(s), target at most {inter['target']}; approval question: "
                 + ("yes" if inter["has_approval"] else "none recorded")))
    rows.append(("No owner-entered commands or identifiers", ("met" if not text["hard"] else "not met") if text["messages"] else "not measured",
                 f"{len(text['hard'])} hard finding(s), {len(text['soft'])} soft in {text['messages']} owner message(s)"))
    rows.append(("No repeated or unnecessary questions", ("met" if not inter["unnecessary"] and not inter["repeated"] else "not met") if has else "not measured",
                 f"{len(inter['unnecessary'])} unnecessary, {len(inter['repeated'])} repeated persona entr(ies)"))
    if states["measured"]:
        good = not states["missing"] and states["next_action"]
        rows.append(("Explicit state and next action", "met" if good else "not met",
                     ("all six states and the next action named" if good else "missing: " + ", ".join(states["missing"] + ([] if states["next_action"] else ["the next action"]))))
                    )
    else:
        rows.append(("Explicit state and next action", "not measured", "no owner messages"))
    d = r["dispositions"]
    rows.append(("Every changed block has a disposition", verdict(d["complete"]),
                 (f"{d['blocks']} block(s); check exit {d['check_exit']}; " + ("no problems" if d["complete"] else f"{len(d['problems'])} problem(s)")) if d["proposal"] else "no proposal was saved"))
    pres = r["preservation"]
    if pres["applicable"]:
        rows.append(("Engineer decision entry kept (WI-03)", verdict(pres["survived"] and pres["under_decisions_recorded"]),
                     "the planted entry is " + ("still there word for word" if pres["survived"] else "missing or changed")))
    cand = r["candidate"]
    if cand["applicable"]:
        rows.append(("New uncited rule reached WI-07", verdict(cand["named"] if cand["block_found"] else None),
                     ("named in the disposition" if cand["in_disposition"] else "") + (" and in an owner message" if cand["in_owner_message"] else "")
                     if cand["named"] else ("the new block was not found in the proposal" if not cand["block_found"] else "WI-07 is not named for the new rule")))
    p = r["patches"]["patches"]
    if p:
        match = all(x["file_matches_patch"] and x["journal_matches"] is not False for x in p)
        rows.append(("Applied patches match the proposal", verdict(match),
                     f"{len(p)} patch(es); " + ", ".join(x["path"].rsplit("/", 1)[-1] + (" ok" if x["file_matches_patch"] else " DIFFERS") for x in p)))
    else:
        rows.append(("Applied patches match the proposal", "not measured", "the proposal has no update patch"))
    dev = r["deviations"]["deviations"]
    rows.append(("Deviations from the skill's steps", "none" if not dev else f"{len(dev)} found", "; ".join(x["code"] for x in dev) or "the command log follows the skill"))
    return rows


def render_report(r):
    out = ["# Field run report", ""]
    out += [f"- Folder: `{r['folder']}`", f"- Mode: {r['mode']}, prepared {r['created']}",
            f"- Owner sentence: {r['owner_sentence']}", f"- Proposal: {(r['proposal'] or 'none saved')[:12]}",
            f"- Commands logged: {r['commands']} ({r['unparsed_log_lines']} log line(s) not understood)"]
    if not r["owner_transcript"]:
        out += ["", "No owner transcript was written (questions.md and to_owner.md are empty). This is the shape of a run with no agent.",
                "The owner-facing measurements are not measured. The state, patch and command measurements below still apply."]
    out += ["", "## Targets of specification 3.6", "", "| Target | Result | Evidence |", "| --- | --- | --- |"]
    for name, v, ev in r["targets"]:
        out.append(f"| {name} | {v} | {ev} |")
    i = r["interactions"]
    out += ["", "## Owner interactions", "", f"- Questions put to the owner: {i['count']} (target at most {i['target']}: the review with its decisions, and the approval)",
            f"- Unnecessary questions: {len(i['unnecessary'])}"]
    out += [f"  - Q{q['number']}: {q['question']} ({q['why']})" for q in i["unnecessary"]]
    out += [f"- Persona entries asked more than once: {', '.join(x['entry'] + ' (Q' + ', Q'.join(str(n) for n in x['questions']) + ')' for x in i['repeated']) or 'none'}"]
    t = r["owner_text"]
    out += ["", "## Owner-facing text", "", f"- Owner messages: {t['messages']}; hard findings: {len(t['hard'])}; soft findings: {len(t['soft'])}"]
    out += [f"  - M{h['message']} line {h['line']} ({', '.join(h['kinds'])}): {h['text']}" for h in t["hard"]]
    out += [f"  - soft, M{h['message']} line {h['line']}: {h['text']}" for h in t["soft"]]
    rv = r["review"]
    out += ["", "## Review", "", f"- Review messages: {rv['count']}; with the lead sentence: {rv['with_lead']}"]
    out += [f"  - M{x['message']}: headings {', '.join(x['headings'])}; lead: {x['lead_sentence'] or 'none'}" for x in rv["reviews"]]
    st = r["states"]
    out += ["", "## States at the end", ""]
    out += ["- Not measured: no owner messages."] if not st["measured"] else [
        f"- States missing from the last owner messages: {', '.join(st['missing']) or 'none'}", f"- Next action (Put the plan on GitHub) named: {'yes' if st['next_action'] else 'no'}"]
    d = r["dispositions"]
    out += ["", "## Dispositions", "", f"- Proposal {(d['proposal'] or 'none')[:12]}: {d['blocks']} changed block(s); reconcile.py check exit {d['check_exit']}"]
    if d["check_text"]:
        out += [f"  - check said: {d['check_text'].splitlines()[-1][:160]}"]
    out += [f"  - problem: {p}" for p in d["problems"]]
    pa = r["patches"]
    out += ["", "## Patches", "", f"- Apply state: {pa['applied_state'] or 'not applied'}; journal entries: {pa['journal_entries']}"]
    for x in pa["patches"]:
        flags = []
        if x["large"]:
            flags.append("LARGE: check that it did not rewrite the whole file")
        if not x["allowed_path"]:
            flags.append("PATH not in the allowed draft paths")
        if x["file_matches_patch"] is False:
            flags.append("the file DIFFERS from the patch text")
        if x["changed_from_baseline"] is False:
            flags.append("the patch changes nothing")
        out.append(f"  - {x['item']} {x['path']} (block {x['block']}): +{x['added']} -{x['removed']} lines of {x['file_lines']}; "
                   f"file matches patch: {x['file_matches_patch']}; journal matches: {x['journal_matches']}" + (" [" + "; ".join(flags) + "]" if flags else ""))
    pr = r["preservation"]
    out += ["", "## Preservation and candidates", ""]
    out += ["- Engineer entry: not applicable to this run."] if not pr["applicable"] else [
        f"- Engineer entry in {pr['path']}: {'kept word for word' if pr['survived'] else 'MISSING OR CHANGED'}"]
    c = r["candidate"]
    out += ["- Uncited rule: not applicable to this run."] if not c["applicable"] else [
        f"- Section {c['section']} (new, cited by nothing): blocks {', '.join(c['blocks']) or 'not found'}; {c['candidate']} named in the disposition: {c['in_disposition']}; in an owner message: {c['in_owner_message']}"]
    out += ["", "## Probes of the working drafts", "", "These are the sample's expectations, stated as facts. A failed probe is a stale text, a missed consumer, a deferral or a wrong patch. Read the disposition."]
    out += [f"- {'ok' if x['ok'] else 'NOT MET'}: {x['name']} ({x['path'].rsplit('/', 1)[-1]})" + ("" if x["ok"] else " - " + "; ".join(x["problems"])) for x in r["probes"]] or ["- none for this run."]
    e = r["elapsed"]
    out += ["", "## Time", "", "Owner attention, machine processing and propagation are separate. None of them is a promise.",
            f"- Machine processing, first to last logged command: {fmt_seconds(e['machine']) if e['machine'] is not None else 'not measured'}",
            f"- First command to the approval question: {fmt_seconds(e['to_approval']) if e['to_approval'] is not None else 'not measured (no approval time recorded)'}",
            "- Owner attention: not measured. The persona answers at once, so a person's reading time is not in this run. Measure it with a person.",
            "- Propagation to GitHub and to engineers: not measured. Nothing was released."]
    dv = r["deviations"]
    out += ["", "## Deviations from the skill's steps", ""]
    out += [f"- {x['level'].upper()} {x['code']}: {x['message']}" + (f" (`{x['command']}`)" if x["command"] else "") for x in dv["deviations"]] or ["- none"]
    if dv["notes"]:
        out += ["", "Notes on the command log:", ""] + [f"- {x['code']}: {x['message']}" + (f" (`{x['command']}`)" if x["command"] else "") for x in dv["notes"]]
    if dv["other_commands"]:
        out += ["", "Commands that are not steps of the path (read them):", ""] + [f"- `{c}`" for c in dv["other_commands"]]
    out += ["", "Sequence: " + " > ".join(dv["sequence"]) if dv["sequence"] else "Sequence: no commands logged"]
    out += ["", "## What the agent wrote in notes.md (hesitations, deviations, unclear places)", "", r["notes"] or "(empty)"]
    out += ["", "## What the observer wrote in observer.md", "", r["observer"] or "(empty)", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="the field-run folder made by prepare_field_run.py")
    ap.add_argument("--json", action="store_true", help="print the measurements as one JSON object instead of the report")
    ap.add_argument("--no-write", action="store_true", help="do not write report.md")
    a = ap.parse_args(argv)
    try:
        result = measure(a.dir)
    except MeasureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    text = render_report(result)
    if not a.no_write:
        (Path(a.dir).resolve() / "report.md").write_text(text, encoding="utf-8")
    if a.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(text)
        if not a.no_write:
            print(f"wrote {Path(a.dir).resolve() / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
