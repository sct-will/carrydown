#!/usr/bin/env python3
"""Update an existing project: report its state, compare changed sources, check and apply accepted changes.

This is the agent-facing half of the update path of carrydown-ground-truth (specification
specs/reconciliation-design.md, sections 3.2, 7, 8, 12 and 13). The plan owner never types these commands.
The agent runs them and explains the result in plain words. Standard library only. The script calls no
model, reads no token and opens no connection. Text in a source, a specification or a request is data.
Nothing in it is followed or executed.

Commands (every one that writes is a dry run unless you pass --apply)
  status  --root .                         the observed project state, the next action and what could not be observed
  prepare --root . [--apply]               compare the current renderings with the reviewed checkpoint, list the changed
                                           blocks and their direct consumers, build the impact index and, with --apply, save
                                           a proposal in the private workspace (drafts/proposals/<id>/)
  check   --root . --proposal ID           is the proposal fresh, does every changed block have one valid disposition,
                                           and is every patch inside the allowed draft paths
  patch   --root . --proposal ID --block REF --item WI-03 --path PATH --from FILE [--also-block REF] [--apply]
                                           record one patch in dispositions.json: the whole new text of PATH is read from
                                           FILE, and before_sha256 is the digest of PATH as it is now
  apply   --root . --proposal ID [--apply] preview, then write the accepted patches to the working drafts with a lock, a
                                           journal and a read back

Every command takes --json for machine output. status exits 0 for every readable project. prepare exits 0, check
exits 1 when it has findings, patch exits 1 when it refuses, apply exits 1 when it stops. All exit 2 for a wrong argument or an unreadable project.

Where things are read from and written to
  The working plan and the specifications are read where the owner drafts them: the private workspace
  (drafts/) when it holds the draft, the project otherwise. On the yes answer the released plan in the project
  (docs/spec/plan.yaml after a release) is never patched. The current renderings are read from docs/ground-truth/
  in the project (yes) or from the private workspace (no). The reviewed renderings come from the source checkpoint
  that workspace.py committed. The originals in docs/source/ are never read.
  A proposal is a folder: inputs.json (the SHA-256 digest of every input read), blocks.json, consumers.json, index.json
  (owner only), dispositions.json, proposal.json and descriptor.json (for workspace.py checkpoint prepare). The proposal id
  is the SHA-256 digest of inputs.json, so the same inputs give the same id and a changed input gives a new one.
  Writes outside the private workspace go through the release gate as draft writes. A patch never reaches
  docs/context/, docs/release/, docs/ground-truth/, a receipt, a bundle or a release snapshot.

Dispositions and patches (dispositions.json)
  {"format": 1, "dispositions": [{"block": REF, "disposition": KIND, ...}]}. KIND and its fields are the ones of
  reconcile_core.REQUIRED_FIELDS. A placeholder "pending" is a finding until the agent replaces it. An update
  disposition carries "patch": {"item": WI-03, "path": PATH, "before_sha256": DIGEST, "after_text": TEXT} (or a list of
  these). PATH is relative to the drafting folder, or starts with project/ or workspace/. A patch that rewrites a recorded
  decision needs "conflict_resolution" on its disposition.

Run with --help after a command to see its flags. Run the tests with: python3 -m unittest tests.test_reconcile -v
"""
import argparse
import calendar
import hashlib
import json
import os
import re
import stat as _stat
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402
import compile_bundles as CB  # noqa: E402
import decision_overlay as DO  # noqa: E402
import reconcile_core as RC  # noqa: E402
import release_gate as RG  # noqa: E402
import workspace as W  # noqa: E402

FORMAT = 1
PROPOSALS_DIR = "drafts/proposals"
CACHE_DIR = "drafts/index-cache"
CLARIFICATIONS = "events/clarifications.json"
PROPOSAL_FILES = ("inputs.json", "blocks.json", "consumers.json", "index.json", "dispositions.json", "proposal.json", "descriptor.json")
MAX_BYTES = 8 * 1024 * 1024
MAX_PATCH_TEXT = 2 * 1024 * 1024
MAX_SPEC_FILES = 2000
MAX_DISPOSITION_BYTES = 16 * 1024 * 1024
LOCK_STALE_SECONDS = 3600
BLOCKING_DESCRIPTOR_KEYS = ("classification", "applicability", "extraction_limits")

NO_WORKSPACE = ("No private workspace was found for this project, so reviewed source checkpoints, unfinished updates and "
                "publication records were not observed.")
OUTSTANDING_NOT_OBSERVED = "Outstanding engineer requests were not observed: the publishing skill's authorized read has not run."
ELSEWHERE = ("Sources kept elsewhere were not observed. Only the renderings held in this project or in the private workspace "
             "were checked.")
STALE_SENTENCE = "Inputs changed since this proposal was prepared. Run prepare again."
STALE_WARNING = ("warning: an unfinished project update has stale inputs. Run the update path again or discard it. "
                 "The release continues.")

STATES = {
    "no-plan": ("No plan", "Start the planning interview with carrydown-ground-truth (step 0). There is no plan to update."),
    "unapproved-draft": ("Unapproved draft", "Continue reviewing the existing draft with the owner. Nothing has been released yet."),
    "changed-sources": ("Existing project with changed sources or a correction",
                        "Use the update path in carrydown-ground-truth. Compare the sources with: reconcile.py prepare --root ."),
    "unfinished-update": ("Unfinished update", "Resume the saved proposal (the owner says: Resume the project update). Check it, then finish it."),
    "drafts-awaiting-release": ("Accepted drafts awaiting release",
                                "Continue with carrydown-plan-to-github. The owner says: Put the plan on GitHub."),
    "release-awaiting-publication": ("Approved release awaiting publication",
                                     "Resume the existing publication with carrydown-plan-to-github."),
    "inputs-unchanged": ("Observable inputs unchanged",
                         "Nothing to update in what this project holds. If the owner named a revised document, it is not rendered yet: "
                         "render it first, then run status again. Otherwise tell the owner what was checked and what was not observed."),
    "ambiguous": ("Ambiguous project or baseline", "Ask the owner which one they mean before you do anything else."),
}


class Stopped(Exception):
    """A command stops with a fixed code and one plain line. Nothing was changed."""

    def __init__(self, code, text):
        super().__init__(text)
        self.code = code
        self.text = text


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def say(text=""):
    L.say(text)


def now_text():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def emit_json(value):
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False), flush=True)


def read_regular(path, limit=MAX_BYTES):
    """The bytes of a regular file that is not a link, within limit, or None."""
    try:
        st = os.lstat(str(path))
    except (OSError, ValueError):
        return None
    if not _stat.S_ISREG(st.st_mode) or st.st_size > limit:
        return None
    try:
        with open(str(path), "rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    return data if len(data) <= limit else None


def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("a key appears twice")
        out[key] = value
    return out


def _no_constants(name):
    raise ValueError("not a JSON number")


def strict_json(data):
    """JSON from bytes with duplicate keys and NaN refused. Raises ValueError."""
    if data is None:
        raise ValueError("missing")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("not UTF-8")
    return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constants)


def decode_text(data):
    """Text from UTF-8 bytes, without a byte order mark. Raises UnicodeDecodeError."""
    return data.decode("utf-8").lstrip("\ufeff")


def short(digest):
    return digest[:12] if isinstance(digest, str) else "none"


def first_line(text):
    return str(text).strip().splitlines()[0][:200] if str(text).strip() else ""


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def age_text(iso, now=None):
    """'3 day(s)' since an ISO time like 2027-01-20T14:03:00Z, or None when it cannot be read."""
    try:
        then = calendar.timegm(time.strptime(str(iso), "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return None
    seconds = int((now if now is not None else time.time()) - then)
    if seconds < 0:
        return "less than a day"
    days = seconds // 86400
    return "less than a day" if days == 0 else plural(days, "day")


# ---------------------------------------------------------------------------
# The project
# ---------------------------------------------------------------------------

class Project:
    """What every command needs to know about the project, read once."""

    def __init__(self, root_arg):
        self.root = L.project_root(root_arg)
        self.ws, self.ws_why = L.workspace_root(self.root)
        self.real_root = Path(os.path.realpath(str(self.root)))
        self.real_ws = Path(os.path.realpath(str(self.ws))) if self.ws is not None else None
        self.plan_path = CB.locate_plan(self.root, self.ws, None)
        self.plan_candidates = [p for p in (self.root / "docs" / "spec" / "plan.yaml", self.root / "plan.yaml") if L.exists(p)]
        self.has_plan = L.exists(self.plan_path)
        self.plan = None
        self.plan_problems = []
        self.plan_error = None
        if self.has_plan:
            try:
                self.plan, self.plan_problems = L.load_plan(self.plan_path, self.root)
            except L.PlanError as e:
                self.plan_error = first_line(e.msg)
        if self.plan is not None:
            project = self.plan.get("project") or {}
            handling = project.get("handling") if isinstance(project.get("handling"), dict) else {}
            self.released_only = self.plan.get("_view") == "released"
            self.mode = "no" if handling.get("repo_audience_approved") is False else "yes"
            self.spec_rel = str(project.get("spec_dir") or "docs/spec")
            self.spec_base = (self.ws / "drafts") if self.ws is not None and (self.ws / "drafts" / self.spec_rel).is_dir() else self.root
            self.spec_dir = self.spec_base / self.spec_rel
            self.renderings_dir, self.rendering_problem = CB.locate_renderings(self.plan, self.root, self.ws, self.ws_why, None)
            self.sources = L.rendered_sources(self.plan)
        else:
            self.released_only = True
            self.mode = "yes"
            self.spec_rel, self.spec_base, self.spec_dir = "docs/spec", self.root, self.root / "docs" / "spec"
            self.renderings_dir, self.rendering_problem = self.root / "docs" / "ground-truth", None
            self.sources = []

    def need_workspace(self):
        if self.ws is None:
            raise Stopped("workspace-unavailable", "there is no private workspace for this project, so nothing can be saved. "
                                                   "Create it with workspace.py init --root . --apply, then run this again")
        return self.ws

    def key_of(self, path):
        """The input key of a file: workspace/<path> or project/<path>."""
        real = Path(os.path.realpath(str(path)))
        for tag, base in (("workspace", self.real_ws), ("project", self.real_root)):
            if base is not None and (real == base or base in real.parents):
                return tag + "/" + real.relative_to(base).as_posix()
        raise Stopped("path-outside", "a file is outside the project and its private workspace")

    def proposals_dir(self):
        return self.need_workspace() / PROPOSALS_DIR

    def proposal_dir(self, change_id):
        if not re.fullmatch(r"[0-9a-f]{64}", str(change_id or "")):
            raise Stopped("proposal-not-found", "--proposal must be the 64 character id that prepare printed")
        return self.proposals_dir() / change_id

    def working_plan_writable(self):
        """True when plan_path is the owner's working plan, not the released copy."""
        return self.plan is not None and not self.released_only


def rendering_file(source):
    return Path(str(source.get("path") or f"{source['id']}.md")).name


def read_sources(project):
    """The current renderings of the reviewed sources: a list of dicts with id, name, path, digest, text and problem."""
    out = []
    for source in project.sources:
        entry = {"id": source["id"], "name": rendering_file(source), "path": None, "digest": None, "text": None, "problem": None,
                 "source": source}
        if project.renderings_dir is None:
            entry["problem"] = project.rendering_problem or "the renderings are not available"
        else:
            path = Path(project.renderings_dir) / entry["name"]
            entry["path"] = path
            data = read_regular(path)
            if data is None:
                entry["problem"] = "the current rendering cannot be read (missing, too large or not a regular file)"
            else:
                entry["digest"] = sha256_bytes(data)
                try:
                    entry["text"] = decode_text(data)
                except UnicodeDecodeError:
                    entry["problem"] = "the current rendering is not UTF-8 text"
        out.append(entry)
    return out


def clean_line(value, limit=200):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value)).strip()
    return text[:limit].strip()


def build_descriptor(project, sources, plan_bytes):
    """The source descriptor projection (workspace.project_descriptor) of the current set. The digest of a
    rendering is the digest of the file now."""
    entries = []
    for entry in sources:
        source = entry["source"]
        item = {"id": entry["id"]}
        version = str(source.get("version") or "").strip()
        if not version and entry["text"]:
            version = CB.rendering_version(entry["text"])
        item["version"] = clean_line(version or CB.UNVERSIONED, 80) or CB.UNVERSIONED
        stem = entry["name"][:-3] if entry["name"].endswith(".md") else entry["name"]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", stem):
            item["rendering"] = stem
        if source.get("content_sha256"):
            item["content_sha256"] = source["content_sha256"]
        if entry["digest"]:
            item["rendering_sha256"] = entry["digest"]
        if source.get("classification") in W.CLASSIFICATIONS:
            item["classification"] = source["classification"]
        if clean_line(source.get("use") or ""):
            item["applicability"] = [clean_line(source["use"])]
        if clean_line(source.get("limit") or ""):
            item["extraction_limits"] = [clean_line(source["limit"])]
        entries.append(item)
    return W.project_descriptor(entries, sha256_bytes(plan_bytes))


# ---------------------------------------------------------------------------
# Clarification requests (the file the publishing skill's authorized read writes)
# ---------------------------------------------------------------------------

REQUEST_STATES = ("pending", "accepted", "declined", "deferred")


def read_clarifications(project):
    """(data or None, raw bytes or None, problem or None). None data with no problem means the file does not exist."""
    if project.ws is None:
        return None, None, None
    path = project.ws / CLARIFICATIONS
    if not os.path.lexists(str(path)):
        return None, None, None
    raw = read_regular(path, 1024 * 1024)
    if raw is None:
        return None, None, "could not be read"
    try:
        data = strict_json(raw)
    except ValueError:
        return None, raw, "could not be read"
    ok = isinstance(data, dict) and data.get("format") == 1 and isinstance(data.get("observed"), str) \
        and isinstance(data.get("repository"), str) and isinstance(data.get("requests"), list)
    if ok:
        for r in data["requests"]:
            if not (isinstance(r, dict) and isinstance(r.get("issue"), int) and not isinstance(r.get("issue"), bool)
                    and isinstance(r.get("item"), str) and r.get("state") in REQUEST_STATES and isinstance(r.get("url"), str)
                    and (r.get("decided_url") is None or isinstance(r.get("decided_url"), str))
                    and (r.get("created_at") is None or (isinstance(r.get("created_at"), str)
                                                         and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", r["created_at"])))):
                ok = False
                break
    if not ok:
        return None, raw, "could not be read"
    return data, raw, None


def recorded_request_issues(project):
    """Issue numbers of accepted requests that an applied proposal already carried as engineer-correction blocks."""
    done = set()
    if project.ws is None:
        return done
    base = project.ws / PROPOSALS_DIR
    if not base.is_dir():
        return done
    for folder in sorted(base.iterdir()):
        if not (folder / "applied.json").is_file():
            continue
        try:
            blocks = strict_json(read_regular(folder / "blocks.json"))
        except ValueError:
            continue
        for b in blocks.get("blocks", []) if isinstance(blocks, dict) else []:
            ref = b.get("ref") if isinstance(b, dict) else None
            m = re.fullmatch(r"request/(\d+)", ref) if isinstance(ref, str) else None
            if m:
                done.add(int(m.group(1)))
    return done


def accepted_requests(project, data):
    if not data:
        return []
    done = recorded_request_issues(project)
    return [r for r in data["requests"] if r["state"] == "accepted" and r.get("decided_url") and r["issue"] not in done]


# ---------------------------------------------------------------------------
# Gathering the inputs
# ---------------------------------------------------------------------------

class Gathered:
    """Everything prepare and check read, once: the current renderings, the descriptor, the checkpoint choice, the
    clarification file and the digest of every input."""

    def __init__(self, project):
        self.project = project
        self.sources = read_sources(project)
        self.plan_bytes = read_regular(project.plan_path) if project.has_plan else None
        self.descriptor = build_descriptor(project, self.sources, self.plan_bytes or b"")
        self.descriptor_bytes = json_bytes(self.descriptor)
        self.record, self.checkpoint_problem = None, None
        if project.ws is not None:
            try:
                ids = [s["id"] for s in self.sources]
                self.record = W.checkpoint_for_sources(project.ws, ids) or W.latest_checkpoint(project.ws)
            except W.CheckpointProblem as e:
                self.checkpoint_problem = e
        self.checkpoint_id = self.record["id"] if self.record else None
        self.clarifications, self.clarification_raw, self.clarification_problem = read_clarifications(project)
        self.inputs = self.collect()

    def collect(self):
        project = self.project
        inputs = {}

        def add(path):
            data = read_regular(path)
            if data is not None:
                inputs[project.key_of(path)] = sha256_bytes(data)

        if project.has_plan:
            add(project.plan_path)
        for path in project.plan_candidates:
            add(path)
        for entry in self.sources:
            if entry["path"] is not None:
                add(entry["path"])
        if project.spec_dir.is_dir():
            count = 0
            for path in sorted(project.spec_dir.rglob("*.md")):
                if path.is_symlink() or not path.is_file():
                    continue
                count += 1
                if count > MAX_SPEC_FILES:
                    break
                add(path)
        receipts = project.root / "docs" / "release"
        if receipts.is_dir():
            for path in sorted(receipts.glob("*.receipt.json")):
                add(path)
        if self.clarification_raw is not None:
            inputs["workspace/" + CLARIFICATIONS] = sha256_bytes(self.clarification_raw)
        inputs["derived/descriptor"] = sha256_bytes(self.descriptor_bytes)
        inputs["derived/checkpoint"] = sha256_bytes((self.checkpoint_id or "none").encode("ascii"))
        return dict(sorted(inputs.items()))

    def inputs_document(self):
        return {"format": FORMAT, "checkpoint": self.checkpoint_id, "index_procedure_version": RC.INDEX_PROCEDURE_VERSION,
                "inputs": self.inputs}


def change_id_of(document_bytes):
    return sha256_bytes(document_bytes)


# ---------------------------------------------------------------------------
# Reading specifications and building the impact index
# ---------------------------------------------------------------------------

def read_specs(project):
    """({item number: text}, {item number: digest}, [problems]) of the specifications in the drafting folder."""
    plan = project.plan
    texts, digests, problems = {}, {}, []
    if plan is None:
        return texts, digests, problems
    for item in plan["items"]:
        path = L.spec_path(plan, project.spec_base, item)
        if not os.path.lexists(str(path)):
            continue
        data = read_regular(path)
        if data is None:
            problems.append(f"the specification of {L.tag(plan, item['id'])} cannot be read (too large or not a regular file)")
            continue
        try:
            texts[item["id"]] = decode_text(data)
        except UnicodeDecodeError:
            problems.append(f"the specification of {L.tag(plan, item['id'])} is not UTF-8 text")
            continue
        digests[item["id"]] = sha256_bytes(data)
    return texts, digests, problems


def rendering_sections_of(sources):
    out = {}
    for entry in sources:
        if entry["text"] is not None:
            out[entry["id"]] = CB.parse_rendering(entry["text"])
    return out


def index_cache_key(plan_digest, spec_digests, rendering_digests):
    material = {"plan": plan_digest, "specs": {str(k): v for k, v in sorted(spec_digests.items())},
                "renderings": dict(sorted(rendering_digests.items())), "procedure": RC.INDEX_PROCEDURE_VERSION,
                "budgets": RC.DEFAULT_BUDGETS}
    return sha256_bytes(json.dumps(material, sort_keys=True).encode("utf-8"))


def build_index(project, gathered, specs, spec_digests, use_cache=True):
    """(index, measure, cache state) for the working drafts. The cache lives in the private workspace and is keyed by
    every contributing digest and the procedure version. A miss, or a cache that is not valid, rebuilds."""
    sections = rendering_sections_of(gathered.sources) if gathered else None
    key = index_cache_key(sha256_bytes(gathered.plan_bytes or b"") if gathered else "", spec_digests,
                          {e["id"]: e["digest"] or "" for e in gathered.sources} if gathered else {})
    cache = project.ws / CACHE_DIR / f"{key}.json" if project.ws is not None else None
    if use_cache and cache is not None:
        data = read_regular(cache)
        if data is not None:
            try:
                doc = strict_json(data)
                if isinstance(doc, dict) and doc.get("key") == key and isinstance(doc.get("index"), dict) \
                        and doc["index"].get("procedure_version") == RC.INDEX_PROCEDURE_VERSION and isinstance(doc.get("measure"), dict):
                    return doc["index"], doc["measure"], "reused", key
            except ValueError:
                pass
    index, measure = RC.build_impact_index(project.plan, specs, rendering_sections=sections)
    return index, measure, "built", key


def measure_sentence(measure):
    return f"index: {measure['bytes']} bytes, {measure['words']} words, about {measure['approx_tokens']} tokens (approximate)"


def impact_index_lines(plan, spec_base, renderings_dir=None):
    """Lines for release preparation: the size of the impact index of the plan being released (specification 7.1).
    Prints to the screen only. Raises nothing the caller must handle except the plain errors it reports."""
    texts = {}
    for item in plan["items"]:
        data = read_regular(L.spec_path(plan, spec_base, item))
        if data is None:
            continue
        try:
            texts[item["id"]] = decode_text(data)
        except UnicodeDecodeError:
            continue
    sections = {}
    if renderings_dir is not None:
        for source in L.rendered_sources(plan):
            data = read_regular(Path(renderings_dir) / rendering_file(source))
            if data is not None:
                try:
                    sections[source["id"]] = CB.parse_rendering(decode_text(data))
                except UnicodeDecodeError:
                    continue
    _, measure = RC.build_impact_index(plan, texts, rendering_sections=sections or None)
    return [f"impact index of this release: {plural(measure['rows'], 'row')}, {measure_sentence(measure)[len('index: '):]}"]


UNASSESSED_WARNING = ("warning: a source changed since the reviewed checkpoint and no project update has assessed it. "
                      "Run the update path first, or release knowing the change is not assessed. The release continues.")


def unassessed_change_warning(root):
    """UNASSESSED_WARNING when a source (or an accepted engineer request) changed since the reviewed checkpoint and no
    applied or saved update covers it, else None. Reads only."""
    try:
        project = Project(root)
        if project.ws is None or project.plan is None:
            return None
        out = observe(project)
        live = [p for p in out["proposals"] if p["state"] in ("prepared", "unreadable") or p["partially_applied"]]
        if out.get("unassessed_changes") and not live:
            return UNASSESSED_WARNING
    except (Stopped, RC.ReconcileError, SystemExit, OSError, ValueError, W.CheckpointProblem):
        return None
    return None


def stale_update_warning(root):
    """STALE_WARNING when a saved, unfinished proposal no longer matches its inputs, else None. Reads only."""
    try:
        project = Project(root)
        if project.ws is None or project.plan is None:
            return None
        proposals = list_proposals(project)
        if not [p for p in proposals if p["state"] not in ("applied", "nothing-to-apply")]:
            return None
        unfinished, _ = unfinished_proposals(proposals, Gathered(project))
        if any(p["stale"] or p["state"] == "unreadable" for p in unfinished):
            return STALE_WARNING
    except (Stopped, RC.ReconcileError, SystemExit, OSError, ValueError):
        return None
    return None


# ---------------------------------------------------------------------------
# Comparing the sources
# ---------------------------------------------------------------------------

def extra_block(kind, ref, source, reason, **more):
    block = {"ref": ref, "kind": kind, "source": source, "previous_number": None, "previous_heading": None, "previous_digest": None,
             "current_number": None, "current_heading": None, "current_digest": None, "exact_move": False, "formatting_only": False,
             "ambiguous": False, "candidates": [], "mapping_basis": None, "heading_changed": False, "text_changed": False,
             "reason": reason}
    block.update(more)
    return block


def checkpoint_text(cp, sid, name):
    """The reviewed rendering text of a source from a verified checkpoint, or None."""
    renderings = cp["renderings"]
    if f"{sid}/{name}" in renderings:
        return renderings[f"{sid}/{name}"].lstrip("\ufeff")
    mine = [k for k in renderings if k.startswith(sid + "/") and k.endswith(".md")]
    return renderings[mine[0]].lstrip("\ufeff") if len(mine) == 1 else None


def descriptor_sources(descriptor):
    out = {}
    for s in (descriptor or {}).get("sources", []) if isinstance(descriptor, dict) else []:
        if isinstance(s, dict) and isinstance(s.get("id"), str):
            out[s["id"]] = s
    return out


def previous_order(descriptor):
    items = [s for s in (descriptor or {}).get("sources", []) if isinstance(s, dict) and isinstance(s.get("id"), str)]
    ranked = sorted(enumerate(items), key=lambda p: (p[1].get("precedence") if isinstance(p[1].get("precedence"), int) else 10 ** 6, p[0]))
    return [s["id"] for _, s in ranked]


def compare(project, gathered):
    """Step 2 of the update path. Returns a dict: state (compared, unavailable), checkpoint (verified record or None),
    blocks, unassessable ([{source, sections}]), descriptor_changes and notes."""
    result = {"state": "unavailable", "checkpoint": None, "blocks": [], "unassessable": [], "descriptor_changes": [], "notes": [],
              "limits": []}
    cp = None
    if gathered.checkpoint_problem is not None:
        result["limits"].append(f"The reviewed checkpoint could not be read ({gathered.checkpoint_problem.code}). Run workspace.py doctor.")
    elif gathered.record is not None:
        try:
            cp = W.checkpoint_read(project.ws, gathered.record["id"])
        except W.CheckpointProblem as e:
            result["limits"].append(f"The reviewed checkpoint could not be read back ({e.code}). Run workspace.py doctor.")
    for entry in gathered.sources:
        if entry["problem"]:
            result["blocks"].append(extra_block("unreadable", f"{entry['id']}/rendering", entry["id"], entry["problem"]))
    if cp is None:
        result["limits"].insert(0, W.CHECKPOINT_UNAVAILABLE)
        for entry in gathered.sources:
            if entry["text"] is not None:
                sections, _duplicates = RC.split_sections(entry["text"])
                numbers = sorted(sections, key=CB.section_key)
                result["unassessable"].append({"source": entry["id"], "sections": numbers})
        return result
    result["state"] = "compared"
    result["checkpoint"] = cp
    prev_desc = descriptor_sources(cp["descriptor"])
    prev_ids = previous_order(cp["descriptor"])
    cur_ids = [e["id"] for e in gathered.sources]
    common = [i for i in prev_ids if i in cur_ids]
    prev_rank_list, cur_rank_list = common, [i for i in cur_ids if i in common]
    cur_desc = descriptor_sources(gathered.descriptor)
    for entry in gathered.sources:
        sid = entry["id"]
        if sid not in prev_desc:
            result["blocks"].append(extra_block("added", f"{sid}/source", sid, "this source is new in the set, so every section of it is new"))
            continue
        before = checkpoint_text(cp, sid, entry["name"])
        if entry["text"] is not None and before is not None:
            try:
                blocks = RC.compare_sections(before, entry["text"], source_id=sid, previous_precedence=prev_rank_list,
                                             current_precedence=cur_rank_list)
            except RC.ReconcileError as e:
                result["blocks"].append(extra_block("unreadable", f"{sid}/rendering", sid, first_line(e)))
                continue
            result["blocks"].extend(blocks)
        elif entry["text"] is not None and before is None:
            result["blocks"].append(extra_block("unreadable", f"{sid}/rendering", sid, "the reviewed rendering of this source is not in the checkpoint"))
        a, b = prev_desc.get(sid, {}), cur_desc.get(sid, {})
        keys = [k for k in ("version", "rendering", "classification", "applicability", "extraction_limits") if a.get(k) != b.get(k)]
        if keys:
            blocking = [k for k in keys if k in BLOCKING_DESCRIPTOR_KEYS]
            result["descriptor_changes"].append({"source": sid, "changed": keys, "blocking": bool(blocking)})
            if blocking:
                result["blocks"].append(extra_block("descriptor", f"{sid}/descriptor", sid,
                                                    "the source descriptor changed: " + ", ".join(blocking)))
    for sid in prev_ids:
        if sid not in cur_ids:
            result["blocks"].append(extra_block("removed", f"{sid}/source", sid, "this source is no longer in the set, so every section of it is removed"))
    for request in accepted_requests(project, gathered.clarifications):
        result["blocks"].append(extra_block("engineer-correction", f"request/{request['issue']}", None,
                                            "an accepted engineer request is a changed input", item=request["item"],
                                            issue=request["issue"], url=request["url"], decided_url=request["decided_url"]))
    return result


def compare_with_requests(project, gathered):
    """compare(), and accepted requests as engineer-correction blocks even when the sources cannot be compared."""
    result = compare(project, gathered)
    if result["state"] != "compared":
        for request in accepted_requests(project, gathered.clarifications):
            result["blocks"].append(extra_block("engineer-correction", f"request/{request['issue']}", None,
                                                "an accepted engineer request is a changed input", item=request["item"],
                                                issue=request["issue"], url=request["url"], decided_url=request["decided_url"]))
    return result


def formatting_dispositions(blocks):
    out = []
    for b in blocks:
        if b.get("formatting_only"):
            out.append({"block": b["ref"], "disposition": "no-impact", "reason": "formatting only",
                        "context": "only white space, emphasis marks or a heading level changed, so no engineering content changed",
                        "automatic": True})
    return out


def find_consumers(project, gathered, blocks, specs):
    """The direct consumers of every changed block, as a list of find_direct_consumers results, plus request consumers."""
    plan = project.plan
    sections = rendering_sections_of(gathered.sources)
    by_source = {}
    for b in blocks:
        if b.get("source"):
            by_source.setdefault(b["source"], []).append(b)
    plan_ids = {s["id"] for s in L.ground_truth_sources(plan)}
    results = []
    for sid in sorted(by_source):
        if sid not in plan_ids:
            for b in by_source[sid]:
                results.append({"block": b["ref"], "source": sid, "consumers": [], "related": [], "uncited_candidates": [],
                                "note": "the source is not in the plan, so its citations cannot be searched"})
            continue
        results.extend(RC.find_direct_consumers(plan, specs, by_source[sid], sid, rendering_sections=sections))
    for b in blocks:
        if b["kind"] == "engineer-correction":
            number = L.item_number(plan, b.get("item"))
            known = number is not None and any(it["id"] == number for it in plan["items"])
            consumers = [{"item": number, "tag": L.tag(plan, number), "relationship": "request", "cited": None, "matched": None,
                          "matched_on": None, "via": ["request"]}] if known else []
            results.append({"block": b["ref"], "source": None, "consumers": consumers, "related": [], "uncited_candidates": []})
    notes = {"descriptor": "a changed descriptor can reach every item that cites the source. Read the index rows that cite it",
             "added": "a new source can reach any item. Read the whole index for obligations it creates",
             "removed": "a removed source can leave citations without a target. Read the index rows that cite it",
             "unreadable": "the comparison of this source could not run. Review the current rendering with the owner"}
    for b in blocks:
        if b["kind"] in notes and not b.get("current_number") and not b.get("previous_number"):
            hit = next((r for r in results if r["block"] == b["ref"]), None)
            if hit is None:
                hit = {"block": b["ref"], "source": b["source"], "consumers": [], "related": [], "uncited_candidates": []}
                results.append(hit)
            hit["note"] = notes[b["kind"]]
    return results


def release_manifest(project):
    """(request id, {manifest path: digest}, problem) of the active release, or (None, {}, None). A problem means the
    records could not be read."""
    if project.ws is None:
        return None, {}, None
    try:
        rid, manifest = RG._active_release(RG.project_state(project.root))
        return rid, manifest, None
    except Exception as e:      # a broken record must not stop a status report
        return None, {}, f"the release records could not be read ({type(e).__name__})"


def active_release_ids(project, rid):
    """{"request_id", "release_id"} of the active release for machine output (workspace.py checkpoint bind takes them), or
    None. Read from the owner's own request record."""
    if rid is None or project.ws is None:
        return None
    try:
        request = strict_json(read_regular(project.ws / "requests" / rid / "approval-request.json"))
        release_id = request.get("release_id") if isinstance(request, dict) else None
    except ValueError:
        release_id = None
    return {"request_id": rid, "release_id": release_id if isinstance(release_id, str) else None}


def annotate_working_copies(project, consumers):
    """Mark whether each consumer's working specification differs from the released copy: a cue for the three-version step."""
    _, manifest, _ = release_manifest(project)
    plan = project.plan
    for result in consumers:
        for c in result["consumers"]:
            if not manifest:
                c["working_differs_from_release"] = None
                continue
            item = next((it for it in plan["items"] if it["id"] == c["item"]), None)
            rel = Path(L.spec_path(plan, "", item)).as_posix() if item else None
            released = manifest.get("repo/" + rel) if rel else None
            data = read_regular(L.spec_path(plan, project.spec_base, item)) if item else None
            c["working_differs_from_release"] = None if released is None or data is None else sha256_bytes(data) != released
            c["specification"] = project.key_of(L.spec_path(plan, project.spec_base, item)) if item else None


# ---------------------------------------------------------------------------
# Writing: every write goes through the release gate
# ---------------------------------------------------------------------------

def gate(project, write_class, rel, data, destination, apply, proposal=None):
    """Ask the release gate. proposal names the checked update proposal of a draft patch: the gate reads that proposal
    itself and lets a reviewed patch replace a released file that already differs from its approved bytes."""
    extra = {"update_proposal": proposal} if proposal is not None and write_class == "draft" else {}
    decision = RG.check(write_class, rel, sha256_bytes(data), destination, project.root, dry_run=not apply, **extra)
    if not decision.allowed:
        raise Stopped(decision.code or "gate-refused", f"{decision.code}: the release gate refused the write of {rel}. Nothing was changed")


def workspace_write(project, rel, data, apply=True):
    """Write a file in the private workspace through the gate and a temporary file."""
    ws = project.need_workspace()
    gate(project, "candidate", rel, data, "workspace", apply)
    if not apply:
        return
    path = ws / rel
    here = Path(ws)
    for part in Path(rel).parts:
        here = here / part
        if here.is_symlink():
            raise Stopped("unsafe-path", f"workspace:{rel} passes through a symbolic link, so nothing was written")
    write_atomic(path, data)


def write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        if path.exists():
            try:
                os.chmod(str(temp), _stat.S_IMODE(os.stat(str(path)).st_mode))
            except OSError:
                pass
        os.replace(str(temp), str(path))
    except OSError as e:
        try:
            temp.unlink()
        except OSError:
            pass
        raise Stopped("write-failed", f"cannot write {path.name}: {e.strerror or e}")


# ---------------------------------------------------------------------------
# Proposals on disk
# ---------------------------------------------------------------------------

def read_json_file(path):
    return strict_json(read_regular(path, MAX_DISPOSITION_BYTES))


def list_proposals(project):
    """[{id, state (prepared, applied, unreadable), partial, inputs, folder}] of the saved proposals, oldest name first."""
    out = []
    if project.ws is None:
        return out
    base = project.ws / PROPOSALS_DIR
    if not base.is_dir():
        return out
    for folder in sorted(base.iterdir()):
        if not folder.is_dir() or not re.fullmatch(r"[0-9a-f]{64}", folder.name):
            continue
        entry = {"id": folder.name, "folder": folder, "state": "prepared", "partial": (folder / "journal.json").is_file(), "inputs": None,
                 "created": ""}
        try:
            made = read_json_file(folder / "proposal.json")
            entry["created"] = made.get("created") if isinstance(made, dict) and isinstance(made.get("created"), str) else ""
        except (ValueError, TypeError):
            pass
        try:
            doc = read_json_file(folder / "inputs.json")
            entry["inputs"] = doc["inputs"] if isinstance(doc, dict) and isinstance(doc.get("inputs"), dict) else None
            if entry["inputs"] is None or sha256_bytes(read_regular(folder / "inputs.json")) != folder.name:
                entry["state"] = "unreadable"
        except (ValueError, TypeError):
            entry["state"] = "unreadable"
        if entry["state"] != "unreadable" and (folder / "applied.json").is_file():
            entry["state"] = "applied"
        elif entry["state"] == "prepared" and not entry["partial"] and proposal_is_empty(folder):
            entry["state"] = "nothing-to-apply"
        out.append(entry)
    return out


def proposal_is_empty(folder):
    """True when a saved proposal has no changed block and no disposition: nothing waits for the owner and nothing can be
    applied. The first comparison of a project with no reviewed checkpoint saves one, only to carry the descriptor for
    the first checkpoint."""
    try:
        blocks = read_json_file(folder / "blocks.json")
        dispositions = read_json_file(folder / "dispositions.json")
    except (ValueError, TypeError):
        return False
    return isinstance(blocks, dict) and blocks.get("blocks") == [] and isinstance(dispositions, dict) and dispositions.get("dispositions") == []


def proposal_staleness(proposal, gathered):
    """True when the inputs of a saved proposal no longer match the inputs now, None when they cannot be read."""
    if not proposal["inputs"]:
        return None
    try:
        return not RC.check_input_digests(proposal["inputs"], gathered.inputs)["fresh"]
    except RC.ReconcileError:
        return True


def proposal_order(proposal):
    """Sort key by creation time, with the modification time of proposal.json as the tie break."""
    try:
        tick = os.stat(str(proposal["folder"] / "proposal.json")).st_mtime_ns
    except OSError:
        tick = 0
    return (proposal["created"], tick, proposal["id"])


def unfinished_proposals(proposals, gathered):
    """(unfinished, superseded). A proposal is unfinished when it has no applied record and something in it waits: a
    proposal with nothing to apply never counts. A partly applied or a fresh one always counts. A stale one counts only
    when it is the newest proposal of all, because a later prepare or a later applied update replaced it."""
    open_ones = [p for p in proposals if p["state"] not in ("applied", "nothing-to-apply")]
    for p in open_ones:
        p["stale"] = proposal_staleness(p, gathered) if p["state"] == "prepared" else None
    if not open_ones:
        return [], []
    newest = sorted(proposals, key=proposal_order)[-1]
    live = [p for p in open_ones if p["partial"] or p["stale"] is False or p["state"] == "unreadable" or p is newest]
    return live, [p for p in open_ones if p not in live]


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def drafts_differences(project, manifest):
    """Paths of the specification files and the plan that differ between the working drafts and the active release."""
    differing = []
    plan = project.plan
    if plan is None or not manifest:
        return differing
    prefix = f"repo/{project.spec_rel}/"
    restricted = any(L.restricted_item(it) for it in plan["items"])
    for path, digest in sorted(manifest.items()):
        if not path.startswith(prefix):
            continue
        rel = path[len("repo/"):]
        if rel == f"{project.spec_rel}/plan.yaml":
            try:
                if project.released_only:
                    data = read_regular(project.plan_path)
                else:
                    data = L.released_plan_bytes(plan)
            except Exception:
                data = None
            if data is None or sha256_bytes(data) != digest:
                differing.append(rel)
            continue
        if restricted and rel.rsplit("/", 1)[-1] in ("README.md", "milestone.md"):
            continue
        data = read_regular(project.spec_base / rel)
        if data is None or sha256_bytes(data) != digest:
            differing.append(rel)
    return differing


def publication_pending(project, rid, manifest):
    """(pending count, total) of the GitHub targets of the active release that its journal does not show as completed."""
    expected = sorted(p[len("payloads/"):-len(".json")] for p in manifest if p.startswith("payloads/") and p.endswith(".json"))
    if not expected:
        return 0, 0
    done = set()
    data = read_regular(project.ws / "publication" / f"{rid}.journal.json")
    if data is not None:
        try:
            journal = strict_json(data)
            for key, entry in (journal.get("targets") or {}).items():
                if isinstance(entry, dict) and entry.get("state") == "completed":
                    done.add(key)
        except (ValueError, AttributeError):
            pass
    return len([k for k in expected if k not in done]), len(expected)


def has_any_release(project):
    if project.ws is not None:
        folder = project.ws / "releases"
        if folder.is_dir() and any(p.is_dir() for p in folder.iterdir()):
            return True
    receipts = project.root / "docs" / "release"
    return receipts.is_dir() and any(receipts.glob("*.receipt.json"))


def observe(project):
    """The project state for status: a dict with state, reasons, checked, limits, notes, proposals, requests."""
    out = {"state": None, "reasons": [], "checked": [], "limits": [], "notes": [], "proposals": [], "requests": None,
           "workspace": project.ws is not None, "candidates": [], "active_release": None}
    if project.ws is None:
        out["limits"].append(NO_WORKSPACE)
    if project.plan_error:
        raise Stopped("plan-unreadable", f"the plan cannot be read: {project.plan_error}")
    if not project.has_plan:
        out["state"] = "no-plan"
        out["reasons"].append("There is no plan.yaml in this project or in its private workspace.")
        out["checked"].append("the project folder for a plan")
        finish_requests(project, out)
        out["limits"].append(ELSEWHERE)
        return out
    out["checked"].append("the working plan")
    if project.plan_problems:
        out["notes"].append(f"The plan has {plural(len(project.plan_problems), 'problem')}. Run check_specs.py to see them.")
    # ambiguity: two different plans in the project, several unfinished updates, several publications waiting
    if len(project.plan_candidates) == 2:
        a, b = (read_regular(p) for p in project.plan_candidates)
        if a != b:
            out["candidates"] += ["docs/spec/plan.yaml", "plan.yaml"]
            out["reasons"].append("The project holds two different plans, docs/spec/plan.yaml and plan.yaml.")
    gathered = Gathered(project)
    out["checked"].append("the current renderings of the reviewed sources" if gathered.sources else "the source list of the plan")
    proposals = list_proposals(project)
    unfinished, superseded = unfinished_proposals(proposals, gathered)
    for p in proposals:
        out["proposals"].append({"id": p["id"], "state": "superseded" if p in superseded else p["state"], "partially_applied": p["partial"] and p["state"] != "applied",
                                 "stale": p.get("stale")})
    if len(unfinished) > 1:
        out["candidates"] += [f"saved update {short(p['id'])}" for p in unfinished]
        out["reasons"].append(f"There are {len(unfinished)} unfinished updates saved in the private workspace.")
    rid, manifest, release_problem = release_manifest(project)
    if release_problem:
        out["limits"].append(release_problem.capitalize() + ".")
    out["active_release"] = active_release_ids(project, rid)
    if project.ws is not None:
        out["checked"].append("the private workspace: reviewed checkpoints, saved updates, release and publication records")
    pending_publications = []
    if rid is not None:
        pend, total = publication_pending(project, rid, manifest)
        if pend:
            pending_publications.append((rid, pend, total))
    # engineer requests
    finish_requests(project, out, gathered)
    # changed sources against the reviewed checkpoint
    changed = []
    cp_problem = None
    if gathered.checkpoint_problem is not None:
        cp_problem = f"The reviewed checkpoint could not be read ({gathered.checkpoint_problem.code}). Run workspace.py doctor."
    elif gathered.record is None:
        out["limits"].append(W.CHECKPOINT_UNAVAILABLE)
    else:
        recorded = {s["id"]: s["sha256"] for s in gathered.record["sources"]}
        for e in gathered.sources:
            if e["problem"]:
                changed.append(f"{e['id']} (the current rendering cannot be read)")
            elif e["id"] not in recorded:
                changed.append(f"{e['id']} (new in the set)")
            elif recorded[e["id"]] != e["digest"]:
                changed.append(f"{e['id']} (rendering differs)")
        for sid in recorded:
            if sid not in [e["id"] for e in gathered.sources]:
                changed.append(f"{sid} (no longer in the set)")
        try:
            cp = W.checkpoint_read(project.ws, gathered.record["id"])
            prev, cur = descriptor_sources(cp["descriptor"]), descriptor_sources(gathered.descriptor)
            for sid in cur:
                if sid in prev and any(prev[sid].get(k) != cur[sid].get(k) for k in BLOCKING_DESCRIPTOR_KEYS):
                    changed.append(f"{sid} (descriptor differs)")
            common = [i for i in previous_order(cp["descriptor"]) if i in cur]
            if common != [e["id"] for e in gathered.sources if e["id"] in common]:
                changed.append("the order of the sources (precedence)")
        except W.CheckpointProblem as e:
            cp_problem = f"The reviewed checkpoint could not be read back ({e.code}). Run workspace.py doctor."
    if cp_problem:
        out["limits"].append(cp_problem)
    out["changed_sources"] = changed
    accepted = accepted_requests(project, gathered.clarifications)
    out["accepted_requests"] = [{"issue": r["issue"], "item": r["item"]} for r in accepted]
    # an applied update whose checkpoint is not recorded yet
    applied = [p for p in proposals if p["state"] == "applied"]
    covered = False
    if changed and applied:
        for p in applied:
            try:
                before = {k: v for k, v in p["inputs"].items() if k.startswith(("workspace/renderings/", "project/docs/ground-truth/"))}
                now = {k: v for k, v in gathered.inputs.items() if k in before}
                if before and before == now:
                    covered = True
                    out["notes"].append("An applied update covers these source changes, but the accepted source checkpoint is not recorded yet. "
                                        "Record it with workspace.py checkpoint prepare and commit (preview first).")
                    break
            except AttributeError:
                continue
    # a change that no applied update assessed comes before a release of the drafts: release them first and the change
    # is published unassessed
    out["unassessed_changes"] = bool((changed and not covered) or accepted)
    # the state
    differing = drafts_differences(project, manifest) if rid is not None else []
    out["drafts_differ"] = len(differing)
    if out["candidates"]:
        out["state"] = "ambiguous"
    elif unfinished:
        out["state"] = "unfinished-update"
        p = unfinished[0]
        if p["state"] == "unreadable":
            out["reasons"].append("A saved update in the private workspace cannot be read. Prepare the comparison again.")
        else:
            out["reasons"].append("A saved update has not been applied" + (" and was partly applied." if p["partial"] else ".")
                                  + (" Its inputs changed since it was prepared, so prepare the comparison again." if p.get("stale") else ""))
    elif rid is None and not has_any_release(project):
        out["state"] = "unapproved-draft"
        out["reasons"].append("A working plan exists and no release has been approved.")
    elif pending_publications:
        rid0, pend, total = pending_publications[0]
        out["state"] = "release-awaiting-publication"
        out["reasons"].append(f"The approved release has {plural(pend, 'GitHub target')} of {total} not yet shown as published.")
    elif differing and not out["unassessed_changes"]:
        out["state"] = "drafts-awaiting-release"
        out["reasons"].append(f"{plural(len(differing), 'file')} of the working drafts {'differs' if len(differing) == 1 else 'differ'} from the active release.")
    elif changed or accepted:
        out["state"] = "changed-sources"
        if differing:
            out["notes"].append(f"{plural(len(differing), 'file')} of the working drafts also {'differs' if len(differing) == 1 else 'differ'} from the active release. "
                                "Assess the source change first, so the next release carries both.")
        if changed:
            out["reasons"].append("Since the reviewed checkpoint these changed: " + "; ".join(changed) + ".")
        if accepted:
            out["reasons"].append(plural(len(accepted), "accepted engineer request") + " not yet carried into an update: "
                                  + ", ".join(f"issue {r['issue']} ({r['item']})" for r in accepted) + ".")
    else:
        out["state"] = "inputs-unchanged"
        if gathered.record is not None:
            out["reasons"].append("Every current rendering matches the reviewed checkpoint, the working drafts match the active release "
                                  "and no update is waiting.")
        else:
            out["reasons"].append("No change can be observed against a reviewed checkpoint, because none is recorded.")
    out["limits"].append(ELSEWHERE)
    return out


def finish_requests(project, out, gathered=None):
    data, raw, problem = (gathered.clarifications, gathered.clarification_raw, gathered.clarification_problem) if gathered else read_clarifications(project)
    if problem:
        out["requests"] = {"observed": False, "reason": problem}
        out["limits"].append(f"Outstanding engineer requests were not observed: events/clarifications.json {problem}.")
        return
    if data is None:
        out["requests"] = {"observed": False, "reason": "not-read"}
        out["limits"].append(OUTSTANDING_NOT_OBSERVED)
        return
    rows = []
    for r in data["requests"]:
        created = r.get("created_at")
        age = age_text(created) if created else None
        rows.append({"issue": r["issue"], "item": r["item"], "state": r["state"], "url": r["url"], "decided_url": r.get("decided_url"),
                     "age": age})
    out["requests"] = {"observed": True, "observed_at": data["observed"], "repository": data["repository"], "requests": rows,
                       "observed_age": age_text(data["observed"])}


def cmd_status(a):
    project = Project(a.root)
    try:
        out = observe(project)
    except Stopped as e:
        L.die(e.text, 2)
    label, action = STATES[out["state"]]
    out["label"], out["next_action"] = label, action
    if a.json:
        emit_json({"command": "status", **{k: v for k, v in out.items()}})
        return 0
    say("carrydown project status")
    say(f"State: {label}")
    for line in out["reasons"]:
        say(line)
    for line in out["notes"]:
        say(line)
    if out["state"] == "ambiguous":
        say("Which one do you mean? " + "; ".join(out["candidates"]) + ".")
    say(f"Next: {action}")
    req = out["requests"]
    if req and req["observed"]:
        rows = req["requests"]
        outstanding = [r for r in rows if r["state"] in ("pending", "deferred") or (r["state"] == "accepted" and r.get("decided_url"))]
        say("")
        age = f", {req['observed_age']} ago" if req.get("observed_age") else ""
        say(f"Engineer requests (observed {req['observed_at']}{age}):" if rows else f"No engineer requests were found (observed {req['observed_at']}{age}).")
        for r in outstanding:
            waited = f", waiting {r['age']}" if r["age"] else ", waiting time not recorded"
            say(f"  {r['item']} issue {r['issue']}: {r['state']}{waited} {r['url']}")
    say("")
    say("What was checked: " + "; ".join(out["checked"]) + "." if out["checked"] else "What was checked: nothing yet.")
    say("What was not observed:")
    for line in out["limits"]:
        say("  " + line)
    return 0


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------

def assess(project, gathered):
    """The whole comparison for prepare: blocks, consumers, index and the files of the proposal."""
    if project.plan is None:
        raise Stopped("no-plan", "there is no plan to compare. Start the planning interview first")
    result = compare_with_requests(project, gathered)
    specs, spec_digests, spec_problems = read_specs(project)
    ordered = []
    seen = set()
    for b in result["blocks"]:
        if b["ref"] not in seen:
            ordered.append(b)
            seen.add(b["ref"])
    blocks = ordered
    consumers = find_consumers(project, gathered, blocks, specs)
    annotate_working_copies(project, consumers)
    index, measure, cache_state, cache_key = build_index(project, gathered, specs, spec_digests)
    return {"compare": result, "blocks": blocks, "consumers": consumers, "index": index, "measure": measure, "cache": cache_state,
            "cache_key": cache_key, "spec_problems": spec_problems, "specs_read": len(specs)}


def proposal_documents(project, gathered, assessment, created):
    inputs_doc = gathered.inputs_document()
    inputs_bytes = json_bytes(inputs_doc)
    change_id = change_id_of(inputs_bytes)
    compare_result = assessment["compare"]
    blocks_doc = {"format": FORMAT, "comparison": compare_result["state"], "blocks": assessment["blocks"],
                  "unassessable": compare_result["unassessable"], "descriptor_changes": compare_result["descriptor_changes"],
                  "limits": compare_result["limits"]}
    dispositions = formatting_dispositions(assessment["blocks"])
    done = {d["block"] for d in dispositions}
    for b in assessment["blocks"]:
        if b["ref"] not in done:
            dispositions.append({"block": b["ref"], "disposition": "pending"})
    docs = {
        "inputs.json": inputs_bytes,
        "blocks.json": json_bytes(blocks_doc),
        "consumers.json": json_bytes({"format": FORMAT, "consumers": assessment["consumers"]}),
        "index.json": json_bytes({"format": FORMAT, "owner_only": True, "index": assessment["index"], "measure": assessment["measure"]}),
        "dispositions.json": json_bytes({"format": FORMAT, "dispositions": dispositions}),
        "proposal.json": json_bytes({"format": FORMAT, "change_id": change_id, "state": "prepared", "created": created,
                                     "plan_sha256": sha256_bytes(gathered.plan_bytes or b""), "checkpoint": gathered.checkpoint_id,
                                     "comparison": compare_result["state"], "blocks": len(assessment["blocks"])}),
        "descriptor.json": gathered.descriptor_bytes,
    }
    return change_id, docs


def distinct_consumers(consumers):
    return sorted({c["item"] for r in consumers for c in r["consumers"] if c["relationship"] in RC.CONTENT_RELATIONSHIPS + ("request",)})


def print_prepare(project, assessment, change_id, apply, reused, state_note):
    blocks, compare_result = assessment["blocks"], assessment["compare"]
    sources_changed = sorted({b["source"] for b in blocks if b["source"]})
    items = distinct_consumers(assessment["consumers"])
    say("carrydown update: compare changed sources" + ("" if apply else "  DRY RUN (nothing will be written)"))
    if project.ws is None:
        say(NO_WORKSPACE)
    for line in compare_result["limits"]:
        say(line)
    if compare_result["state"] == "unavailable" and compare_result["unassessable"]:
        for u in compare_result["unassessable"]:
            say(f"{u['source']}: {plural(len(u['sections']), 'section')} cannot be compared, because there is no earlier checkpoint. "
                "Treat each as unassessable history and review the current source with the owner.")
    say(f"{len(blocks)} changed block(s) in {len(sources_changed)} source(s); {len(items)} direct consumer(s); "
        + measure_sentence(assessment["measure"]))
    measure = assessment["measure"]
    if measure.get("truncated_fields"):
        say(f"{plural(measure['truncated_fields'], 'field')} of the index {'is a truncated excerpt' if measure['truncated_fields'] == 1 else 'are truncated excerpts'} "
            f"({plural(measure.get('omitted_words', 0), 'word')} left out). Read the full specification before you conclude no impact for such a row.")
    for b in blocks:
        heads = []
        same = (b.get("previous_heading") and b.get("previous_number") == b.get("current_number")
                and b.get("previous_heading") == b.get("current_heading"))
        if same:
            heads.append(f"\"{b['current_number']} {b['current_heading']}\" (heading unchanged)")
        else:
            if b.get("previous_heading"):
                heads.append(f"was \"{b['previous_number']} {b['previous_heading']}\"")
            if b.get("current_heading"):
                heads.append(f"now \"{b['current_number']} {b['current_heading']}\"")
        extra = f" ({b['reason']})" if b.get("reason") and not heads else ""
        say(f"  {b['ref']}  {b['kind']}  {', '.join(heads) if heads else '-'}{extra}  formatting only: {'yes' if b.get('formatting_only') else 'no'}")
    for c in compare_result["descriptor_changes"]:
        if not c["blocking"]:
            say(f"  descriptor of {c['source']}: {', '.join(c['changed'])} changed (recorded, no disposition needed)")
    rows = [(r["block"], c) for r in assessment["consumers"] for c in r["consumers"]]
    if rows:
        say("")
        say("Direct consumers (who cites a changed block):")
        say(f"  {'block':<28} {'work item':<9} {'relationship':<18} {'cites':<9} working copy")
        for ref, c in rows:
            changed = {True: "differs from the released copy", False: "matches the released copy", None: "release copy not compared"}[c.get("working_differs_from_release")]
            say(f"  {ref:<28} {c['tag']:<9} {c['relationship']:<18} {str(c.get('cited') or '-'):<9} {changed}")
    for r in assessment["consumers"]:
        grouped = {}
        for rel in r["related"]:
            grouped.setdefault(rel["tag"], set()).add(rel["relationship"])
        if grouped:
            say(f"  {r['block']} also touches, without citing it (a scheduling or integration link alone needs no rewrite): "
                + ", ".join(f"{tag} ({', '.join(sorted(kinds))})" for tag, kinds in sorted(grouped.items())))
        if r.get("note"):
            say(f"  {r['block']}: {r['note']}")
    if assessment["spec_problems"]:
        for p in assessment["spec_problems"]:
            say(f"note: {p}")
    if assessment["measure"].get("missing_specifications"):
        say(f"note: {plural(assessment['measure']['missing_specifications'], 'work item')} has no specification yet.")
    say("")
    if apply:
        say(f"The full record is in the private workspace, folder {PROPOSALS_DIR}/{change_id}/ (inputs, blocks, consumers, the index, dispositions).")
        if state_note:
            say(state_note)
        say("When the owner accepts the sources, descriptor.json in that folder is the descriptor for workspace.py checkpoint prepare.")
    else:
        say("Nothing was written. Add --apply to save the proposal in the private workspace.")
    say(f"proposal: {change_id}")


def cmd_prepare(a):
    project = Project(a.root)
    if project.plan_error:
        L.die(f"the plan cannot be read: {project.plan_error}", 2)
    if not project.has_plan:
        L.die("there is no plan in this project or in its private workspace, so there is nothing to compare. Start the planning interview first", 2)
    try:
        if a.apply:
            project.need_workspace()
        gathered = Gathered(project)
        assessment = assess(project, gathered)
        change_id, docs = proposal_documents(project, gathered, assessment, now_text())
        folder_rel = f"{PROPOSALS_DIR}/{change_id}"
        existing = project.ws is not None and (project.ws / folder_rel).is_dir()
        state_note = ""
        if existing:
            applied = (project.ws / folder_rel / "applied.json").is_file()
            state_note = ("This proposal was already prepared with the same inputs, and it was applied. Nothing was written."
                          if applied else "This proposal was already prepared with the same inputs. It is reused, so your dispositions are kept.")
        if a.json:
            emit_json({"command": "prepare", "apply": bool(a.apply), "proposal": change_id, "reused": bool(existing),
                       "comparison": assessment["compare"]["state"], "limits": assessment["compare"]["limits"],
                       "counts": {"blocks": len(assessment["blocks"]), "sources": len({b["source"] for b in assessment["blocks"] if b["source"]}),
                                  "direct_consumers": len(distinct_consumers(assessment["consumers"]))},
                       "measure": {k: v for k, v in assessment["measure"].items() if k != "excluded_rows"},
                       "blocks": assessment["blocks"], "consumers": assessment["consumers"],
                       "unassessable": assessment["compare"]["unassessable"], "index_cache": assessment["cache"]})
        else:
            print_prepare(project, assessment, change_id, a.apply, existing, state_note)
        if a.apply:
            write_proposal(project, change_id, docs, assessment)
        else:
            if project.ws is not None:
                for name, data in docs.items():        # ask the gate about every write, so a refusal shows in the dry run
                    gate(project, "candidate", f"{folder_rel}/{name}", data, "workspace", False)
    except Stopped as e:
        L.die(e.text, 1)
    except RC.ReconcileError as e:
        L.die(f"the comparison could not run: {first_line(e)}. Run check_specs.py to find the problem in the plan or a specification", 1)
    return 0


def write_proposal(project, change_id, docs, assessment):
    folder_rel = f"{PROPOSALS_DIR}/{change_id}"
    folder = project.ws / folder_rel
    for name, data in docs.items():
        rel = f"{folder_rel}/{name}"
        if name in ("dispositions.json", "proposal.json") and (folder / name).is_file():
            continue                                  # the owner's decisions and the first created time are kept
        if read_regular(folder / name) == data:
            continue
        workspace_write(project, rel, data, True)
    cache = project.ws / CACHE_DIR / f"{assessment['cache_key']}.json"
    if assessment["cache"] == "built":
        workspace_write(project, f"{CACHE_DIR}/{assessment['cache_key']}.json",
                        json_bytes({"key": assessment["cache_key"], "index": assessment["index"], "measure": assessment["measure"]}), True)
    back = read_regular(folder / "inputs.json")
    if back is None or sha256_bytes(back) != change_id:
        raise Stopped("write-failed", "the saved inputs could not be read back, so the proposal was not saved")


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def finding(code, block, message, **more):
    out = {"code": code, "block": block, "message": message}
    out.update(more)
    return out


def load_proposal(project, change_id):
    folder = project.proposal_dir(change_id)
    if not folder.is_dir():
        raise Stopped("proposal-not-found", "no saved proposal has that id. Run prepare --apply, or use the id it printed")
    raw = read_regular(folder / "inputs.json")
    if raw is None or sha256_bytes(raw) != change_id:
        raise Stopped("proposal-unreadable", "the saved inputs of this proposal are missing or were changed. Prepare the comparison again")
    try:
        inputs_doc = strict_json(raw)
        blocks_doc = read_json_file(folder / "blocks.json")
        dispositions_doc = read_json_file(folder / "dispositions.json")
    except ValueError:
        raise Stopped("proposal-unreadable", "a file of this proposal cannot be read. Prepare the comparison again")
    ok = isinstance(inputs_doc, dict) and inputs_doc.get("format") == FORMAT and isinstance(inputs_doc.get("inputs"), dict) \
        and isinstance(blocks_doc, dict) and blocks_doc.get("format") == FORMAT and isinstance(blocks_doc.get("blocks"), list) \
        and isinstance(dispositions_doc, dict) and dispositions_doc.get("format") == FORMAT \
        and isinstance(dispositions_doc.get("dispositions"), list)
    if not ok:
        raise Stopped("proposal-format", "this proposal has an unsupported format or a malformed file. Prepare the comparison again")
    return {"id": change_id, "folder": folder, "inputs": inputs_doc["inputs"], "blocks": blocks_doc["blocks"],
            "blocks_doc": blocks_doc, "dispositions": dispositions_doc["dispositions"],
            "applied": (folder / "applied.json").is_file(), "journal": load_journal(folder)}


def load_journal(folder):
    data = read_regular(folder / "journal.json")
    if data is None:
        return None
    try:
        doc = strict_json(data)
    except ValueError:
        return {"unreadable": True}
    if not (isinstance(doc, dict) and doc.get("format") == FORMAT and isinstance(doc.get("entries"), list)):
        return {"unreadable": True}
    return doc


FORBIDDEN_PARTS = ("docs/context/", "docs/release/", "docs/ground-truth/", "docs/source/")
FORBIDDEN_WORKSPACE = ("releases/", "requests/", "renderings/", "events/", "publication/", "sources/", "drafts/proposals/", "drafts/checkpoints/")


def resolve_patch_path(project, text):
    """(absolute path, input key) for a patch path, or raises ValueError with a plain message."""
    if not isinstance(text, str) or not text.strip() or "\x00" in text or "\\" in text or re.search(r"[\x00-\x1f]", text):
        raise ValueError("the patch path is blank or not a plain relative path")
    if text.startswith("workspace/"):
        if project.ws is None:
            raise ValueError("the patch path is in the private workspace, and there is none")
        base, rel, tag = project.ws, text[len("workspace/"):], "workspace"
    elif text.startswith("project/"):
        base, rel, tag = project.root, text[len("project/"):], "project"
    else:
        base = project.spec_base
        rel = text
        tag = "workspace" if (project.ws is not None and project.spec_base == project.ws / "drafts") else "project"
    parts = rel.split("/")
    if rel.startswith("/") or ".." in parts or "" in parts or "." in parts:
        raise ValueError("the patch path leaves the project or is not a plain relative path")
    path = base / rel
    key = project.key_of(path)
    return path, key


def path_allowed(project, path, key):
    """None when path may be patched, else the plain reason."""
    rel = key.split("/", 1)[1] if "/" in key else key
    if key.startswith("project/") and any(rel.startswith(p) for p in FORBIDDEN_PARTS):
        return "that file is generated or approved content. It is never patched by hand"
    if key.startswith("workspace/") and any(rel.startswith(p) for p in FORBIDDEN_WORKSPACE):
        return "that is private workspace history, not a working draft"
    if "snapshot" in Path(rel).parts:
        return "a release snapshot is never patched"
    real = Path(os.path.realpath(str(path)))
    if path.is_symlink():
        return "that file is a symbolic link"
    if project.working_plan_writable() and real == Path(os.path.realpath(str(project.plan_path))):
        return None
    if real == Path(os.path.realpath(str(project.root / "docs" / "spec" / "plan.yaml"))) or real.name == "plan.yaml":
        return "that is the released plan or a plan that is not the working draft. Patch the working plan only"
    spec_real = Path(os.path.realpath(str(project.spec_dir)))
    if spec_real in real.parents and real.suffix == ".md":
        return None
    return "that file is outside the working plan and the specification folder"


def decisions_rewritten(current, after):
    """None when the recorded decision entries of a specification survive a patch, else the reason code. A
    specification with no recorded entry has nothing to rewrite."""
    old_lines, new_lines = DO._overlay_lines(current), DO._overlay_lines(after)
    old_bounds = DO._overlay_bounds(old_lines)
    if old_bounds is None:
        return None
    core, _ = DO._overlay_split_blank(old_lines[old_bounds[0] + 1:old_bounds[1]])
    if not any(DO._OVERLAY_ENTRY.match(line.rstrip(b"\r\n")) for line in core):
        return None
    new_bounds = DO._overlay_bounds(new_lines)
    if new_bounds is None:
        return "boundary-malformed"
    probe = b"".join(old_lines[:old_bounds[0] + 1] + new_lines[new_bounds[0] + 1:new_bounds[1]] + old_lines[old_bounds[1]:])
    result = DO.validate_overlay(current, probe, "allowed")
    if result.ok:
        return None
    return result.reason if result.reason in ("entry-edited", "boundary-malformed") else None


def patch_records(record):
    """The list of patch dicts of an update disposition, or raises ValueError."""
    patch = record.get("patch")
    if isinstance(patch, str):
        try:
            patch = strict_json(patch.encode("utf-8"))
        except ValueError:
            raise ValueError("the patch is not a JSON record")
    if isinstance(patch, dict):
        patch = [patch]
    if not isinstance(patch, list) or not patch or not all(isinstance(p, dict) for p in patch):
        raise ValueError("the patch must be a JSON record or a list of records")
    return patch


PATCH_KEYS = ("item", "path", "before_sha256", "after_text")


def plan_patches(project, proposal, journal=None):
    """(patches, findings) for every update disposition. A patch is a dict with block, item, key, path, before, after, after_bytes,
    write_class, destination and gate_rel."""
    patches, findings, seen = [], [], {}
    states = {}
    if journal and not journal.get("unreadable"):
        states = {e.get("path"): e for e in journal["entries"] if isinstance(e, dict)}
    for record in proposal["dispositions"]:
        if not isinstance(record, dict) or record.get("disposition") != "update":
            continue
        block = record.get("block")
        try:
            records = patch_records(record)
        except ValueError as e:
            findings.append(finding("patch-malformed", block, f"{block}: {e}"))
            continue
        for number, p in enumerate(records, 1):
            label = f"{block} patch {number}"
            if set(p) != set(PATCH_KEYS):
                findings.append(finding("patch-malformed", block, f"{label} must have exactly these fields: {', '.join(PATCH_KEYS)}"))
                continue
            if not (isinstance(p["before_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", p["before_sha256"])) or not isinstance(p["after_text"], str) \
                    or RC._blank(p["item"] if not RC._is_int(p["item"]) else "x"):
                findings.append(finding("patch-malformed", block, f"{label} has a missing item, a bad before_sha256 or no after_text"))
                continue
            if len(p["after_text"].encode("utf-8")) > MAX_PATCH_TEXT or "\x00" in p["after_text"]:
                findings.append(finding("patch-malformed", block, f"{label} is too large or holds a NUL character"))
                continue
            try:
                path, key = resolve_patch_path(project, p["path"])
            except (ValueError, Stopped) as e:
                findings.append(finding("patch-path", block, f"{label}: {getattr(e, 'text', None) or e}"))
                continue
            why = path_allowed(project, path, key)
            if why:
                findings.append(finding("patch-path", block, f"{label} is outside the allowed draft paths ({key}): {why}"))
                continue
            current = read_regular(path)
            if current is None:
                findings.append(finding("patch-path", block, f"{label}: {key} does not exist or cannot be read"))
                continue
            after = p["after_text"].encode("utf-8")
            entry = states.get(key)
            state = None
            if sha256_bytes(current) == p["before_sha256"]:
                state = "planned"
            elif entry and sha256_bytes(current) == entry.get("after_sha256") == sha256_bytes(after):
                state = "written"
            else:
                findings.append(finding("patch-stale", block, f"{label}: {key} changed since the patch was written. "
                                                              "Write the patch again from the current file", path=key))
                continue
            if state == "planned" and after == current:
                findings.append(finding("patch-unchanged", block, f"{label} does not change {key}"))
                continue
            if key in seen:
                findings.append(finding("patch-duplicate", block, f"{key} is changed by two patches ({seen[key]} and {block}). "
                                                                  "Combine them into one patch, because a second patch would start from stale content"))
                continue
            seen[key] = block
            if state == "planned" and key.endswith(".md") and not key.endswith("/plan.yaml"):
                reason = decisions_rewritten(current, after)
                if reason and RC._blank(record.get("conflict_resolution")):
                    findings.append(finding("decision-conflict", block, f"{label} rewrites a decision an engineer recorded in {key}. "
                                                                        "Resolve the conflict with the owner and record it as conflict_resolution on the disposition"))
                    continue
            in_workspace = key.startswith("workspace/")
            rel = key.split("/", 1)[1]
            patches.append({"block": block, "item": p["item"], "key": key, "path": path, "before": p["before_sha256"],
                            "after": sha256_bytes(after), "after_bytes": after, "state": state,
                            "write_class": "candidate" if in_workspace else "draft",
                            "destination": "workspace" if in_workspace else "engineering-repo", "gate_rel": rel})
    return patches, findings


def citation_findings(project, proposal, patches):
    """citation-missing findings: a specification patch filed under block B names B's section or an identifier from its
    heading, but the item's citations after the proposal (its sections in the working plan, with the plan patch of the
    proposal applied, and the References of the patched specification) do not include B. The release compiler builds
    approved context only from those citations, so the context would omit the changed section."""
    plan = project.plan
    if plan is None or not patches:
        return []
    blocks = {b.get("ref"): b for b in (proposal.get("blocks") or []) if isinstance(b, dict)}
    try:
        plan_key = project.key_of(project.plan_path)
    except Stopped:
        plan_key = None
    for p in patches:
        if p["key"] == plan_key:
            try:
                plan, _ = L.plan_from_data(L.loads(p["after_bytes"].decode("utf-8")), project.plan_path, project.root)
            except (L.PlanError, ValueError, UnicodeDecodeError, RecursionError):
                return []     # the plan patch itself is broken; the checker of the plan reports it
    sources = {s["id"]: s for s in L.ground_truth_sources(plan) if isinstance(s, dict) and s.get("id")}
    sections = {e["id"]: CB.parse_rendering(e["text"]) for e in read_sources(project) if e.get("text") is not None}
    spec_items = {}
    for it in plan.get("items") or []:
        try:
            spec_items[project.key_of(L.spec_path(plan, project.spec_base, it))] = it
        except (Stopped, KeyError):
            continue
    out = []
    for p in patches:
        it = spec_items.get(p["key"])
        block = blocks.get(p["block"])
        if it is None or block is None or not p["key"].endswith(".md"):
            continue
        sid, number = block.get("source"), block.get("current_number") or block.get("previous_number")
        if not sid or not number or sid not in sources:
            continue
        heading = block.get("current_heading") or block.get("previous_heading") or ""
        text = p["after_bytes"].decode("utf-8", "replace")
        if not CB.named_obligations(text, [{"source": sid, "section": number, "heading": heading}], sources):
            continue
        cited = CB.item_obligation_keys(plan, it, CB.spec_cited_keys(text, sources, sections.get))
        if (sid, number) in cited:
            continue
        tag = L.tag(plan, it["id"])
        out.append(finding("citation-missing", p["block"],
                           f"{p['block']}: the patch of {tag} relies on {sid} section {number}, which {tag} does not cite. Add {number} to its "
                           f"sections in the working plan, its Ground truth row and its References in this proposal, because the approved "
                           f"context holds only the sections an item cites", item=tag, path=p["key"]))
    return out


def run_check(project, proposal):
    """(findings, details) of one proposal. details: fresh, changed (paths), patches."""
    findings = []
    gathered = Gathered(project)
    journal = proposal["journal"]
    try:
        verdict = RC.check_input_digests(proposal["inputs"], gathered.inputs)
    except RC.ReconcileError:
        verdict = {"changed": [], "missing": sorted(proposal["inputs"]), "added": [], "fresh": False}
    tolerated = set()
    if journal and not journal.get("unreadable"):
        for e in journal["entries"]:
            if isinstance(e, dict) and e.get("state") in ("written", "verified") and gathered.inputs.get(e.get("path")) == e.get("after_sha256"):
                tolerated.add(e.get("path"))
    changed = sorted(set(verdict["changed"]) - tolerated)
    stale = bool(changed or verdict["missing"] or verdict["added"])
    if stale:
        findings.append(finding("inputs-changed", None, STALE_SENTENCE))
    # dispositions
    blocks = proposal["blocks"]
    try:
        core_blocks = blocks
        records, pending = [], set()
        for r in proposal["dispositions"]:
            if isinstance(r, dict) and r.get("disposition") == "pending":
                pending.add(r.get("block"))
                continue
            if isinstance(r, dict) and r.get("disposition") == "update" and isinstance(r.get("patch"), (dict, list)):
                r = dict(r)
                r["patch"] = json.dumps(r["patch"], sort_keys=True)
            records.append(r)
        for ref in sorted(x for x in pending if x):
            findings.append(finding("pending-disposition", ref, f"{ref} still has a pending disposition. Decide it with the owner before applying"))
        for problem in RC.validate_dispositions(core_blocks, records):
            if problem["code"] == "missing-disposition" and problem["block"] in pending:
                continue
            findings.append(finding(problem["code"], problem["block"], problem["message"]))
    except RC.ReconcileError as e:
        findings.append(finding("proposal-format", None, f"the proposal's blocks or dispositions are malformed: {first_line(e)}"))
    patches, patch_findings = plan_patches(project, proposal, journal)
    findings.extend(patch_findings)
    findings.extend(citation_findings(project, proposal, patches))
    if journal and journal.get("unreadable"):
        findings.append(finding("journal-unreadable", None, "the journal of a partly applied update cannot be read, so nothing further can be applied safely"))
    return findings, {"fresh": not stale, "changed": changed + verdict["missing"] + verdict["added"], "patches": patches,
                      "comparison": proposal["blocks_doc"].get("comparison"), "limits": proposal["blocks_doc"].get("limits") or []}


def cmd_check(a):
    project = Project(a.root)
    if project.plan_error:
        L.die(f"the plan cannot be read: {project.plan_error}", 2)
    try:
        proposal = load_proposal(project, a.proposal)
    except Stopped as e:
        L.die(e.text, 2)
    if proposal["applied"]:
        if a.json:
            emit_json({"command": "check", "proposal": a.proposal, "applied": True, "findings": [], "count": 0})
        else:
            say(f"carrydown: proposal {a.proposal} was already applied. Nothing more to check.")
            say(f"carrydown: proposal {a.proposal} has 0 finding(s)")
        return 0
    findings, details = run_check(project, proposal)
    if a.json:
        emit_json({"command": "check", "proposal": a.proposal, "applied": False, "fresh": details["fresh"], "changed_inputs": details["changed"],
                   "comparison": details["comparison"], "findings": findings, "count": len(findings)})
        return 1 if findings else 0
    say("carrydown update: check")
    if not details["fresh"]:
        say(STALE_SENTENCE)
        for path in details["changed"][:20]:
            say(f"  changed input: {path}")
    for f in findings:
        if f["code"] != "inputs-changed":
            say(f"  - {f['code']}: {f['message']}")
    if details["comparison"] == "unavailable":
        for line in details["limits"][:1]:
            say(f"limit: {line} A passing check does not mean the sources were compared.")
    say(f"carrydown: proposal {a.proposal} has {len(findings)} finding(s)")
    return 1 if findings else 0


# ---------------------------------------------------------------------------
# patch
# ---------------------------------------------------------------------------

def line_counts(before, after):
    """(lines added, lines removed) between two texts, by a line diff."""
    import difflib
    added = removed = 0
    for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


def add_item(value, item):
    """The item field of an update disposition with item added once: "WI-03" and "WI-11" give "WI-03, WI-11"."""
    names = [n.strip() for n in str(value or "").split(",") if n.strip()]
    if item not in names:
        names.append(item)
    return ", ".join(names)


def record_patch(project, proposal, block, item, path_text, after_text, also=()):
    """The new dispositions document with one patch recorded, and a summary. Raises Stopped with a plain reason."""
    if block not in {b.get("ref") for b in proposal["blocks"] if isinstance(b, dict)}:
        raise Stopped("unknown-block", f"{block} is not a changed block of this proposal. Use a block reference that prepare printed")
    for ref in also:
        if ref == block or ref not in {b.get("ref") for b in proposal["blocks"] if isinstance(b, dict)}:
            raise Stopped("unknown-block", f"--also-block {ref} is not another changed block of this proposal")
    if not re.fullmatch(r"WI-\d+", item or ""):
        raise Stopped("bad-item", "--item must be a work item number such as WI-03")
    try:
        path, key = resolve_patch_path(project, path_text)
    except ValueError as e:
        raise Stopped("patch-path", f"{path_text}: {e}")
    why = path_allowed(project, path, key)
    if why:
        raise Stopped("patch-path", f"{key} cannot be patched: {why}")
    current = read_regular(path)
    if current is None:
        raise Stopped("patch-path", f"{key} does not exist or cannot be read")
    if len(after_text.encode("utf-8")) > MAX_PATCH_TEXT or "\x00" in after_text:
        raise Stopped("patch-malformed", "the new text is too large or holds a NUL character")
    if after_text.encode("utf-8") == current:
        raise Stopped("patch-unchanged", f"the new text is the same as {key}. Nothing to record")
    try:
        current_text = decode_text(current)
    except UnicodeDecodeError:
        raise Stopped("patch-path", f"{key} is not UTF-8 text")
    doc = {"format": FORMAT, "dispositions": [dict(r) if isinstance(r, dict) else r for r in proposal["dispositions"]]}
    target = None
    for r in doc["dispositions"]:
        if not isinstance(r, dict):
            continue
        if r.get("block") == block:
            if target is not None:
                raise Stopped("duplicate-disposition", f"{block} has two dispositions. Keep one, then run this again")
            target = r
            continue
        if r.get("disposition") == "update":
            try:
                others = patch_records(r)
            except ValueError:
                continue
            for o in others:
                try:
                    _, other_key = resolve_patch_path(project, o.get("path"))
                except (ValueError, Stopped):
                    continue
                if other_key == key:
                    raise Stopped("patch-duplicate", f"{key} already has a patch under {r.get('block')}. One file takes one patch: write the combined "
                                                     f"text with --block {r.get('block')} --also-block {block}")
    record = {"item": item, "path": path_text, "before_sha256": sha256_bytes(current), "after_text": after_text}
    if target is None:
        target = {"block": block}
        doc["dispositions"].append(target)
    kind = target.get("disposition")
    if kind in (None, "pending"):
        for name in list(target):
            if name != "block":
                del target[name]
        target.update({"disposition": "update", "item": item, "patch": [record]})
        replaced = False
    elif kind == "update":
        try:
            existing = patch_records(target)
        except ValueError:
            raise Stopped("patch-malformed", f"the patch of {block} cannot be read. Fix or remove it in dispositions.json, then run this again")
        replaced = False
        kept = []
        for o in existing:
            try:
                same = resolve_patch_path(project, o.get("path"))[1] == key
            except (ValueError, Stopped):
                same = False
            if same:
                replaced = True
                continue
            kept.append(o)
        target["patch"] = kept + [record]
        target["item"] = add_item(target.get("item"), item)
    else:
        raise Stopped("not-an-update", f"{block} already has the disposition {kind}. Only an update carries a patch. "
                                       "Change it to pending in dispositions.json if the block needs a patch")
    if also:
        context = str(target.get("context") or "").strip()
        missing = [ref for ref in also if ref not in context]
        if missing:
            line = "This patch also carries the changes of " + ", ".join(missing) + "."
            target["context"] = (context + " " + line).strip() if context else line
    added, removed = line_counts(current_text, after_text)
    summary = {"block": block, "item": item, "path": key, "before_sha256": record["before_sha256"],
               "after_sha256": sha256_bytes(after_text.encode("utf-8")), "added": added, "removed": removed, "replaced": replaced,
               "decision_conflict": bool(key.endswith(".md") and decisions_rewritten(current, after_text.encode("utf-8")))}
    return doc, summary


def cmd_patch(a):
    project = Project(a.root)
    if project.plan_error:
        L.die(f"the plan cannot be read: {project.plan_error}", 2)
    try:
        proposal = load_proposal(project, a.proposal)
    except Stopped as e:
        L.die(e.text, 2)
    if proposal["applied"] or proposal["journal"]:
        L.die("this proposal was already applied, or an apply started. Its patches cannot change now. Prepare the comparison again", 1)
    source = Path(a.from_file)
    data = read_regular(source, MAX_PATCH_TEXT)
    if data is None:
        L.die(f"--from {a.from_file} is not a readable file of at most {MAX_PATCH_TEXT} bytes", 2)
    try:
        after_text = data.decode("utf-8")
    except UnicodeDecodeError:
        L.die(f"--from {a.from_file} is not UTF-8 text", 2)
    try:
        doc, summary = record_patch(project, proposal, a.block, a.item, a.path, after_text, tuple(a.also_block or ()))
        workspace_write(project, f"{PROPOSALS_DIR}/{a.proposal}/dispositions.json", json_bytes(doc), a.apply)
    except Stopped as e:
        L.die(e.text, 1)
    if a.json:
        emit_json({"command": "patch", "proposal": a.proposal, "apply": bool(a.apply), **summary})
        return 0
    verb = ("replaced" if summary["replaced"] else "recorded") if a.apply else ("would replace" if summary["replaced"] else "would record")
    say(f"carrydown update: patch{'' if a.apply else '  DRY RUN (nothing will be written)'}")
    say(f"{verb} the patch of {summary['path']} under {summary['block']} for {summary['item']}: "
        f"{plural(summary['added'], 'line')} added, {plural(summary['removed'], 'line')} removed, "
        f"from {short(summary['before_sha256'])} to {short(summary['after_sha256'])}")
    if summary["decision_conflict"]:
        say("note: this patch rewrites a decision an engineer recorded. Ask the owner, then record conflict_resolution on the disposition")
    if not a.apply:
        say("Nothing was written. Add --apply to record it in dispositions.json.")
    else:
        say("Nothing in the drafts changed. Run check, then apply after the owner approves.")
    say(f"proposal: {a.proposal}")
    return 0


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def pid_alive(pid, lock_path):
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == "nt":
        try:
            return time.time() - os.stat(str(lock_path)).st_mtime < LOCK_STALE_SECONDS
        except OSError:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class Lock:
    """A process lock on one proposal: a file created exclusively, holding the process id and time."""

    def __init__(self, project, change_id):
        self.project = project
        self.rel = f"{PROPOSALS_DIR}/{change_id}/lock"
        self.path = project.ws / self.rel
        self.mine = False

    def __enter__(self):
        data = json_bytes({"pid": os.getpid(), "time": now_text()})
        gate(self.project, "candidate", self.rel, data, "workspace", True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in (1, 2):
            try:
                fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                if attempt == 1 and not os.path.lexists(str(self.path)):
                    continue                          # the other run finished between the two calls
                try:
                    holder = strict_json(read_regular(self.path, 4096))
                except ValueError:
                    holder = None
                pid = holder.get("pid") if isinstance(holder, dict) else None
                if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                    raise Stopped("lock-unreadable", "the lock file for this proposal is unreadable; remove it by hand if no other run "
                                                     f"is active (workspace:{self.rel}). Nothing was written")
                if attempt == 1 and not pid_alive(pid, self.path):
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                raise Stopped("lock-held", "another run is applying this proposal right now. Wait for it to finish, then run this again. "
                                           "Nothing was written")
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            self.mine = True
            return self
        raise Stopped("lock-held", "the lock of this proposal cannot be taken. Nothing was written")

    def __exit__(self, *exc):
        if self.mine:
            try:
                self.path.unlink()
            except OSError:
                pass
        return False


def journal_document(change_id, patches, started, previous=None):
    states = {e["path"]: e["state"] for e in (previous or {}).get("entries", []) if isinstance(e, dict)}
    entries = [{"path": p["key"], "before_sha256": p["before"], "after_sha256": p["after"],
                "state": states.get(p["key"], "planned")} for p in patches]
    return {"format": FORMAT, "change_id": change_id, "started": started, "entries": entries}


def save_journal(project, change_id, doc):
    workspace_write(project, f"{PROPOSALS_DIR}/{change_id}/journal.json", json_bytes(doc), True)


def cmd_apply(a):
    project = Project(a.root)
    if project.plan_error:
        L.die(f"the plan cannot be read: {project.plan_error}", 2)
    try:
        proposal = load_proposal(project, a.proposal)
    except Stopped as e:
        L.die(e.text, 2)
    change_id = a.proposal
    if proposal["applied"]:
        if a.json:
            emit_json({"command": "apply", "proposal": change_id, "already_applied": True, "written": 0})
        else:
            say("This proposal was already applied. Nothing was written.")
            say("Next: record the accepted source checkpoint with workspace.py checkpoint (preview first), then say: Put the plan on GitHub.")
            say(f"proposal: {change_id}")
        return 0
    findings, details = run_check(project, proposal)
    if findings:
        if a.json:
            emit_json({"command": "apply", "proposal": change_id, "applied": False, "findings": findings, "count": len(findings)})
        else:
            say("carrydown update: apply stopped. Nothing was written.")
            if not details["fresh"]:
                say(STALE_SENTENCE)
            for f in findings:
                if f["code"] != "inputs-changed":
                    say(f"  - {f['code']}: {f['message']}")
            for f in findings:
                if f["code"] == "patch-stale":
                    say(f"Stopped: unexpected content at {f['path']}; nothing further was written.")
            say(f"carrydown: proposal {change_id} has {len(findings)} finding(s)")
        return 1
    patches = details["patches"]
    journal = proposal["journal"]
    out_rows = []
    for p in patches:
        out_rows.append({"path": p["key"], "before_sha256": p["before"], "after_sha256": p["after"], "bytes": len(p["after_bytes"]), "state": p["state"]})
        if p["state"] == "written":
            continue                                  # already holds the after bytes: nothing is written again
        try:
            gate(project, p["write_class"], p["gate_rel"], p["after_bytes"], p["destination"], False, proposal=change_id)
        except Stopped as e:
            L.die(e.text, 1)
    if not a.apply:
        if a.json:
            emit_json({"command": "apply", "proposal": change_id, "apply": False, "writes": out_rows})
            return 0
        say("carrydown update: apply  DRY RUN (nothing will be written)")
        if journal:
            done = [p for p in patches if p["state"] == "written"]
            say(f"An earlier run was interrupted. {plural(len(done), 'patch', 'patches')} already written and will be verified. "
                f"{plural(len(patches) - len(done), 'patch', 'patches')} remaining.")
        if not patches:
            say("No working draft needs a change. Applying records the update as applied.")
        for p in patches:
            verb = "already written" if p["state"] == "written" else "would change"
            say(f"  {verb} {p['key']}  ({short(p['before'])} to {short(p['after'])}, {len(p['after_bytes'])} bytes)")
        say("Nothing was written. Add --apply to write these changes.")
        say(f"proposal: {change_id}")
        return 0
    try:
        with Lock(project, change_id):
            result = apply_patches(project, change_id, proposal, patches)
    except Stopped as e:
        L.die(e.text, 1)
    if a.json:
        emit_json({"command": "apply", "proposal": change_id, "apply": True, **result})
        return 0 if result["applied"] else 1
    return report_apply(change_id, result)


def apply_patches(project, change_id, proposal, patches):
    """Write the patches with a journal and a read back. Returns a dict with applied, written, verified and a stopped path."""
    started = (proposal["journal"] or {}).get("started") or now_text()
    doc = journal_document(change_id, patches, started, proposal["journal"] if proposal["journal"] and not proposal["journal"].get("unreadable") else None)
    save_journal(project, change_id, doc)
    entries = {e["path"]: e for e in doc["entries"]}
    result = {"applied": False, "written": 0, "verified": 0, "resumed": [p["key"] for p in patches if entries[p["key"]]["state"] != "planned"],
              "stopped": None, "patches": len(patches)}
    for p in patches:
        entry = entries[p["key"]]
        current = read_regular(p["path"])
        digest = sha256_bytes(current) if current is not None else None
        if digest == p["after"]:
            if entry["state"] != "verified":
                entry["state"] = "verified"
                save_journal(project, change_id, doc)
            result["verified"] += 1
            continue
        if digest != p["before"] or entry["state"] != "planned":
            result["stopped"] = p["key"]
            return result
        gate(project, p["write_class"], p["gate_rel"], p["after_bytes"], p["destination"], True, proposal=change_id)
        write_atomic(p["path"], p["after_bytes"])
        entry["state"] = "written"
        save_journal(project, change_id, doc)
        result["written"] += 1
        back = read_regular(p["path"])
        if back is None or sha256_bytes(back) != p["after"]:
            result["stopped"] = p["key"]
            return result
        entry["state"] = "verified"
        save_journal(project, change_id, doc)
        result["verified"] += 1
    applied = json_bytes({"format": FORMAT, "change_id": change_id, "state": "applied", "time": now_text(), "patches": len(patches)})
    workspace_write(project, f"{PROPOSALS_DIR}/{change_id}/applied.json", applied, True)
    result["applied"] = True
    return result


def report_apply(change_id, result):
    if result["stopped"]:
        say(f"Stopped: unexpected content at {result['stopped']}; nothing further was written.")
        say(f"{plural(result['written'], 'patch', 'patches')} written before it stopped. The journal in the private workspace shows which. "
            "Look at that file, then prepare the comparison again.")
        say(f"proposal: {change_id}")
        return 1
    if result["resumed"]:
        say("An earlier run was interrupted. These patches were already written and now read back correctly: " + ", ".join(result["resumed"]) + ".")
    say(f"carrydown update: applied {plural(result['written'], 'patch', 'patches')} now and checked {plural(result['verified'], 'patch', 'patches')} by reading it back.")
    say("The working drafts are changed. The released copy is not. Nothing is published.")
    say("Next: record the accepted source checkpoint with workspace.py checkpoint (preview first), then say: Put the plan on GitHub.")
    say(f"proposal: {change_id}")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def add_common(p):
    p.add_argument("--root", default=".", help="the project folder (default: the current folder)")
    p.add_argument("--json", action="store_true", help="print machine output as one JSON object")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", metavar="{status,prepare,check,patch,apply}")
    p = sub.add_parser("status", help="report the observed project state, the next action and what could not be observed",
                       description="Read the project and its private workspace and print the observed state as one row of the routing table, with the "
                                   "next action. Writes nothing. Exit 0 for every readable project.")
    add_common(p)
    p = sub.add_parser("prepare", help="compare the current sources with the reviewed checkpoint and save a proposal",
                       description="Compare the current renderings with the reviewed source checkpoint, list the changed blocks and their direct "
                                   "consumers, and build the impact index. A dry run unless --apply. With --apply, save the proposal in the private "
                                   "workspace under drafts/proposals/. The last line is: proposal: <id>.")
    add_common(p)
    p.add_argument("--apply", action="store_true", help="save the proposal. Without it this is a dry run")
    p = sub.add_parser("check", help="check a proposal: freshness, dispositions and patches",
                       description="Recompute every input digest, validate the dispositions and every update patch. Exit 0 only with 0 findings.")
    add_common(p)
    p.add_argument("--proposal", required=True, help="the proposal id that prepare printed")
    p = sub.add_parser("patch", help="record one patch in the proposal's dispositions, with the current digest of the file",
                       description="Read the whole new text of one working draft from --from and record it as a patch of the update disposition "
                                   "of --block, with before_sha256 set to the digest of the file as it is now. A pending block becomes an update. "
                                   "One file takes one patch, so a second run for the same file replaces its patch. A dry run unless --apply. "
                                   "The working drafts are never written: apply does that after the owner approves.")
    add_common(p)
    p.add_argument("--proposal", required=True, help="the proposal id that prepare printed")
    p.add_argument("--block", required=True, help="the changed block the patch answers, as prepare printed it, such as architecture/3.5")
    p.add_argument("--item", required=True, help="the work item the file belongs to, such as WI-03")
    p.add_argument("--path", required=True, help="the file to patch, relative to the drafting folder, or starting with project/ or workspace/")
    p.add_argument("--from", dest="from_file", required=True, help="a file that holds the whole new text of --path")
    p.add_argument("--also-block", action="append", metavar="REF",
                   help="another changed block whose change this patch also carries. Named in the disposition's context. Repeat for more")
    p.add_argument("--apply", action="store_true", help="record the patch. Without it this is a dry run")
    p = sub.add_parser("apply", help="apply the accepted patches to the working drafts",
                       description="Run check first and stop on any finding. Preview each write. With --apply, take a lock, write a journal, write "
                                   "each patch through the release gate when the file still holds the expected bytes, read it back, and record "
                                   "the update as applied. A repeat on an applied proposal writes nothing.")
    add_common(p)
    p.add_argument("--proposal", required=True, help="the proposal id that prepare printed")
    p.add_argument("--apply", action="store_true", help="write the changes. Without it this is a dry run")
    a = ap.parse_args(argv)
    if not a.command:
        ap.print_help()
        return 0
    return {"status": cmd_status, "prepare": cmd_prepare, "check": cmd_check, "patch": cmd_patch, "apply": cmd_apply}[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
