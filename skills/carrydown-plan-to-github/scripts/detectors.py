#!/usr/bin/env python3
"""Mechanical leak detectors for the files a release would publish. Read only.

A detector looks for one kind of leak and says where, never what. Each finding is a detector name,
a fixed code and a location, the id of the file and the line number. The matched text is never
printed, and neither are private paths. The detectors are a safety net with known gaps: a clean run
prints "detectors: no findings (this does not prove safety)".

Detectors
  credentials         token prefixes, access keys, key blocks, key, secret or token assignments.
                      Never resolvable by an exception.
  private_paths       home folders, the private workspace path, the docs/source/ folder.
                      Never resolvable by an exception.
  prohibited_fields   staffing keys in the people list of a plan, an advisors list, structured files
                      that cannot be parsed. Never resolvable by an exception.
  org_phrases         lines of phrases.txt in the private workspace, found in any case. Owner side.
                      Resolvable by a recorded exception.
  copied_restricted   twelve-word runs of a restricted rendering found in a published file. Owner
                      side. Resolvable by a recorded exception that names the passage digest.

An exception has the shape the approval request records: type, passage_sha256, destinations and
reason. Only org_phrases and copied_restricted can be excepted. An exception for any other type is
refused with exception-not-permitted, and the finding stays.

Usage
  python3 scripts/detectors.py --root .                         scan the published files of the project
  python3 scripts/detectors.py --root . --request approval-request.json   apply the exceptions of a request
Exit status is 0 when there are no findings, 1 when there are, and 2 when an argument is wrong.
The script never writes files and never prints matched text.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402

DETECTORS = ("credentials", "private_paths", "prohibited_fields", "org_phrases", "copied_restricted")
EXCEPTABLE = ("org_phrases", "copied_restricted")
NOT_PERMITTED = "exception-not-permitted"
CLEAN_LINE = "detectors: no findings (this does not prove safety)"
SHINGLE = 12                                  # words in a copied-passage run
TEXT_SUFFIXES = (".md", ".txt", ".yaml", ".yml", ".json")
MAX_BYTES = 8 * 1024 * 1024                   # a larger file is read in part: the first 8 MiB
EXCEPTION_KEYS = ("type", "passage_sha256", "destinations", "reason")
DESTINATIONS = ("engineering-repo", "issue", "subepic", "epic", "epic-comment", "label", "board", "engineers-skill")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class Hit(tuple):
    """(code, location) with the digest of the passage, for the detectors that can be excepted."""
    def __new__(cls, code, location, passage_sha256=None):
        self = super().__new__(cls, (code, location))
        self.passage_sha256 = passage_sha256
        return self


class Finding(tuple):
    """(detector, code, location). It compares and unpacks as that triple. passage_sha256 is the
    normalized passage digest of an org_phrases or copied_restricted finding, else None."""
    def __new__(cls, detector, code, location, passage_sha256=None):
        self = super().__new__(cls, (detector, code, location))
        self.passage_sha256 = passage_sha256
        return self

    detector = property(lambda self: self[0])
    code = property(lambda self: self[1])
    location = property(lambda self: self[2])


def format_finding(finding):
    """detector:<detector>:<code> at <file id>:<line>. A passage finding adds its digest, which the
    owner needs to write the exception and which reveals nothing of the passage."""
    text = f"detector:{finding[0]}:{finding[1]} at {finding[2]}"
    if getattr(finding, "passage_sha256", None) and finding[0] in EXCEPTABLE:
        text += f" (passage_sha256 {finding.passage_sha256})"
    return text


def report_lines(findings):
    """The text a run prints: one line per finding, or the clean line."""
    return [format_finding(f) for f in findings] or [CLEAN_LINE]


# ---------------------------------------------------------------------------
# Reading the files
# ---------------------------------------------------------------------------

def is_text_file(file_id):
    return str(file_id).lower().endswith(TEXT_SUFFIXES)


def read_files(root, snapshot_files):
    """{file id: text}. snapshot_files is a mapping of file id to a path (or to the bytes themselves), or a
    list of file ids relative to root. Only text suffixes are read. A file that is missing or cannot be read is skipped here
    and listed by missing_files, so the caller can fail closed."""
    out = {}
    if isinstance(snapshot_files, dict):
        pairs = [(str(k), v if isinstance(v, (bytes, bytearray)) else Path(v)) for k, v in snapshot_files.items()]
    else:
        pairs = [(str(f).replace("\\", "/"), Path(root) / str(f)) for f in snapshot_files or []]
    for file_id, path in pairs:
        if not is_text_file(file_id):
            continue
        if isinstance(path, (bytes, bytearray)):
            data = bytes(path)[:MAX_BYTES]       # content given directly, as a release preview does
        else:
            try:
                with open(path, "rb") as handle:
                    data = handle.read(MAX_BYTES)
            except OSError:
                continue
        out[file_id] = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
    return out


def _line_of(text, offset):
    return text.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# credentials
# ---------------------------------------------------------------------------

CREDENTIAL_PATTERNS = (
    ("github-token", re.compile(r"(?<![A-Za-z0-9])(?:ghp_|github_pat_)[A-Za-z0-9_]+")),
    ("access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("key-block", re.compile(r"-----BEGIN")),
    ("secret-assignment", re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*\S{8,}")),
)


def credentials(files):
    """(code, location) for each line that holds a credential pattern. One finding per line."""
    out = []
    for file_id, text in files.items():
        for n, line in enumerate(text.split("\n"), 1):
            for code, pattern in CREDENTIAL_PATTERNS:
                if pattern.search(line):
                    out.append(Hit(code, f"{file_id}:{n}"))
                    break
    return out


# ---------------------------------------------------------------------------
# private_paths
# ---------------------------------------------------------------------------

HOME_PATHS = re.compile(
    r"(?<![A-Za-z0-9_.~-])/(?:Users|home)/[A-Za-z0-9._-]+/"          # /Users/name/ and /home/name/
    r"|[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"']+"                       # C:\Users\name
    r"|~/\.carrydown\b|%USERPROFILE%[\\/]+\.carrydown")              # the default workspace folder
SOURCE_FOLDER = re.compile(r"(?<![A-Za-z0-9_.-])docs[\\/]+source[\\/]")


def private_path_strings(root, workspace):
    """Exact path strings that name the private workspace: the folder passed in and the line of
    .carrydown/local.yaml. Both forms of separator, resolved and as written."""
    found = []
    candidates = [workspace]
    try:
        pointer = Path(root) / ".carrydown" / "local.yaml" if root is not None else None
        if pointer is not None and pointer.is_file():
            data = L.load_file(pointer)
            if isinstance(data, dict) and isinstance(data.get("workspace"), str):
                candidates.append(data["workspace"])
    except (L.YamlError, L.TextError, OSError, ValueError):
        pass
    for c in candidates:
        if not c:
            continue
        for text in {str(c), Path(str(c)).as_posix(), str(c).replace("/", "\\")}:
            try:
                text = text.rstrip("/\\")
            except AttributeError:
                continue
            if len(text) >= 4 and text not in found:
                found.append(text)
        try:
            resolved = os.path.realpath(str(c))
            if len(resolved) >= 4 and resolved not in found:
                found.append(resolved)
        except (OSError, ValueError):
            pass
    return found


def private_paths(files, workspace=None, root=None, allow_source_folder=()):
    """(code, location) for each line that holds a home path, the private workspace path or the
    docs/source/ folder. allow_source_folder lists file ids where the folder name is not a finding
    (the owner's own plan.yaml, which names the original by its path)."""
    out = []
    exact = private_path_strings(root, workspace) if (root is not None or workspace) else []
    fold = os.name == "nt"
    for file_id, text in files.items():
        for n, line in enumerate(text.split("\n"), 1):
            hay = line.casefold() if fold else line
            code = None
            if exact and any((p.casefold() if fold else p) in hay for p in exact):
                code = "workspace-path"
            elif HOME_PATHS.search(line):
                code = "home-path"
            elif file_id not in allow_source_folder and SOURCE_FOLDER.search(line):
                code = "source-folder"
            if code:
                out.append(Hit(code, f"{file_id}:{n}"))
    return out


# ---------------------------------------------------------------------------
# prohibited_fields
# ---------------------------------------------------------------------------

def _is_plan_file(file_id):
    return str(file_id).replace("\\", "/").rsplit("/", 1)[-1].lower() == "plan.yaml"


def _locate_people_keys(text):
    """[(line, key)] for each staffing key in the people list of a plan written in block style,
    and the line of the people key itself as a fallback."""
    lines = text.split("\n")
    out = []
    in_people = False
    people_line = 1
    for n, line in enumerate(lines, 1):
        if re.match(r"^people\s*:", line):
            in_people, people_line = True, n
            continue
        if in_people and line.strip() and not line.startswith((" ", "\t", "-", "#")):
            in_people = False
        if in_people:
            m = re.match(r"^\s*(?:-\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
            if m and m.group(1) in L.STAFFING_KEYS:
                out.append((n, m.group(1)))
            elif "{" in line:
                for key in L.STAFFING_KEYS:
                    if re.search(r"[{,]\s*" + key + r"\s*:", line):
                        out.append((n, key))
    return out, people_line


def prohibited_fields(files):
    """(code, location) for staffing keys in people[] of a plan, an advisors list, and structured
    files that cannot be parsed. The plan is read as a plan; other structured files must parse.
    A malformed file is a finding: there is no fallback to a text search. Source names, board
    fields called name and prose that mentions skills are not findings."""
    out = []
    for file_id, text in files.items():
        low = file_id.lower()
        if low.endswith(".json"):
            try:
                L._schema().loads_strict(text.encode("utf-8"))
            except Exception:   # any parse failure, including duplicate keys, fails closed
                out.append(Hit("malformed-structured-file", f"{file_id}:1"))
            continue
        if not low.endswith((".yaml", ".yml")):
            continue
        try:
            data = L.loads(text)
        except Exception:
            out.append(Hit("malformed-structured-file", f"{file_id}:1"))
            continue
        if not _is_plan_file(file_id):
            continue
        if not isinstance(data, dict):
            out.append(Hit("malformed-structured-file", f"{file_id}:1"))
            continue
        keys_by_line, people_line = _locate_people_keys(text)
        people = data.get("people")
        if isinstance(people, list):
            seen_lines = set()
            for entry in people:
                if isinstance(entry, dict) and any(k in entry for k in L.STAFFING_KEYS):
                    for n, key in keys_by_line:
                        if (n, key) not in seen_lines:
                            seen_lines.add((n, key))
                            out.append(Hit("staffing-field", f"{file_id}:{n}"))
                    if not keys_by_line:
                        out.append(Hit("staffing-field", f"{file_id}:{people_line}"))
                    break
        elif people is not None:
            out.append(Hit("malformed-structured-file", f"{file_id}:{people_line}"))
        if "advisors" in data:
            n = next((i for i, line in enumerate(text.split("\n"), 1) if re.match(r"^advisors\s*:", line)), 1)
            out.append(Hit("advisors-list", f"{file_id}:{n}"))
    return out


# ---------------------------------------------------------------------------
# org_phrases and copied_restricted
# ---------------------------------------------------------------------------

def read_phrases(workspace):
    """The phrases of <workspace>/phrases.txt: one per line, blank lines and # comments skipped."""
    if not workspace:
        return []
    path = Path(workspace) / "phrases.txt"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [line.strip() for line in text.split("\n") if line.strip() and not line.strip().startswith("#")]


def phrase_digest(phrase):
    return hashlib.sha256(" ".join(phrase.casefold().split()).encode("utf-8")).hexdigest()


def org_phrases(files, phrases):
    """(code, location) for each line that holds a phrase of the organization, in any case. The
    digest on the hit is that of the phrase (case folded, blanks collapsed), so an exception names
    the phrase and not the sentence around it."""
    out = []
    wanted = [(" ".join(p.casefold().split()), phrase_digest(p)) for p in phrases if p.strip()]
    for file_id, text in files.items():
        for n, line in enumerate(text.split("\n"), 1):
            folded = " ".join(line.casefold().split())
            for phrase, digest in wanted:
                if phrase and phrase in folded:
                    out.append(Hit("organization-phrase", f"{file_id}:{n}", digest))
    return out


_WORD = re.compile(r"[^\W_]+")


def words_of(text):
    """The words of text, lower case, as the copied-passage detector compares them: letters and
    digits only, so markup, punctuation and line breaks do not hide a copy."""
    return _WORD.findall(text.casefold())


def _words_with_lines(text):
    words, lines = [], []
    for n, line in enumerate(text.split("\n"), 1):
        for w in _WORD.findall(line.casefold()):
            words.append(w)
            lines.append(n)
    return words, lines


def _shingle_key(words):
    return hashlib.sha256(" ".join(words).encode("utf-8")).digest()[:12]


def shingle_set(texts):
    """The set of keys of every run of SHINGLE words in the given restricted texts."""
    keys = set()
    for text in texts:
        words = words_of(text)
        for i in range(len(words) - SHINGLE + 1):
            keys.add(_shingle_key(words[i:i + SHINGLE]))
    return keys


def passage_digest(words):
    """The normalized passage digest: SHA-256 of the passage's words, lower case, one space between."""
    return hashlib.sha256(" ".join(words).encode("utf-8")).hexdigest()


def copied_restricted(files, restricted_texts):
    """(code, location) for each run of at least twelve words of a restricted text found in a file.
    A run of overlapping twelve-word matches is one finding. Its location is the line of its first
    word, and the digest on the hit is passage_digest of the whole run."""
    keys = shingle_set(restricted_texts)
    out = []
    if not keys:
        return out
    for file_id, text in files.items():
        words, lines = _words_with_lines(text)
        i, last = 0, len(words) - SHINGLE
        while i <= last:
            if _shingle_key(words[i:i + SHINGLE]) in keys:
                j = i
                while j + 1 <= last and _shingle_key(words[j + 1:j + 1 + SHINGLE]) in keys:
                    j += 1
                out.append(Hit("copied-passage", f"{file_id}:{lines[i]}", passage_digest(words[i:j + SHINGLE])))
                i = j + SHINGLE
            else:
                i += 1
    return out


def restricted_renderings(root, workspace, plan_path=None):
    """The texts of the restricted renderings of the project: sources the workspace plan classifies
    restricted, read from <workspace>/renderings/ or, failing that, from the project. Returns a list
    of texts. A project with no plan, no classification or no workspace returns []."""
    candidates = []
    if workspace:
        candidates.append(Path(workspace) / "drafts" / "plan.yaml")
    candidates.append(Path(plan_path) if plan_path else Path(root) / "docs" / "spec" / "plan.yaml")
    plan = None
    for c in candidates:
        try:
            if c.is_file():
                data = L.load_file(c)
                if isinstance(data, dict) and isinstance(data.get("sources"), list):
                    plan = data
                    break
        except (L.YamlError, L.TextError, OSError, ValueError):
            continue
    if plan is None:
        return []
    texts = []
    for source in plan["sources"]:
        if not isinstance(source, dict) or source.get("classification") != "restricted":
            continue
        rel = source.get("path")
        if not isinstance(rel, str) or not rel.strip():
            continue
        places = []
        if workspace:
            places.append(Path(workspace) / "renderings" / Path(rel).name)
        places.append(Path(root) / rel)
        for place in places:
            try:
                if place.is_file():
                    texts.append(place.read_text(encoding="utf-8", errors="replace"))
                    break
            except OSError:
                continue
    return texts


# ---------------------------------------------------------------------------
# Destinations, exceptions
# ---------------------------------------------------------------------------

def destination_of(file_id):
    """The destination a snapshot file goes to. repo/... and project files go to the engineering
    repository (the engineers' skill folder to engineers-skill), payloads/<kind>/... to <kind>."""
    parts = str(file_id).replace("\\", "/").split("/")
    if parts and parts[0] == "payloads" and len(parts) > 1:
        kind = {"issues": "issue", "subepics": "subepic"}.get(parts[1], parts[1])
        return kind if kind in DESTINATIONS else "engineering-repo"
    rel = "/".join(parts[1:] if parts and parts[0] == "repo" else parts)
    if "/dev/skills/" in "/" + rel:
        return "engineers-skill"
    return "engineering-repo"


def is_bundle_file(file_id):
    """An approved context bundle (docs/context/*.md). A bundle quotes the sections a work item
    must honor, so the two owner-content detectors do not read it."""
    rel = str(file_id).replace("\\", "/")
    rel = rel[len("repo/"):] if rel.startswith("repo/") else rel
    return rel.startswith("docs/context/") and rel.lower().endswith(".md")


def normalize_exception(ex):
    """(exception with destinations as a list, problem or None). Accepts destination as a single
    word, for the older spelling."""
    if not isinstance(ex, dict):
        return None, "exception is not an object"
    ex = dict(ex)
    if "destination" in ex and "destinations" not in ex:
        ex["destinations"] = [ex.pop("destination")]
    if set(ex) != set(EXCEPTION_KEYS):
        return None, "exception has missing or unknown fields"
    if not isinstance(ex["type"], str) or not re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", ex["type"]):
        return None, "exception type is not a word"
    if not isinstance(ex["passage_sha256"], str) or not _HEX64.match(ex["passage_sha256"]):
        return None, "exception passage_sha256 is not a digest"
    dests = ex["destinations"]
    if not isinstance(dests, list) or not dests or any(d not in DESTINATIONS for d in dests):
        return None, "exception destinations are not supported destinations"
    if not isinstance(ex["reason"], str) or not ex["reason"].strip():
        return None, "exception reason is empty"
    return ex, None


class Resolution:
    """What resolve found. unresolved: findings that stay. resolved: [(finding, exception)] that a
    recorded exception clears. refused: [(index, code, problem)] for each exception that cannot be
    used, code exception-not-permitted for a type that can never be excepted."""
    def __init__(self):
        self.unresolved, self.resolved, self.refused = [], [], []

    def __iter__(self):
        return iter(self.unresolved)


def resolve(findings, exceptions):
    """Apply recorded exceptions to findings. Returns a Resolution. An exception clears a finding
    when the type matches, the passage digest matches and the finding's destination is one of the
    exception's destinations. Credentials, private paths and prohibited fields are never cleared:
    an exception naming any type other than org_phrases or copied_restricted is refused with
    exception-not-permitted, and malformed exceptions are refused with schema-invalid."""
    res = Resolution()
    usable = []
    for i, raw in enumerate(exceptions or []):
        named = raw.get("type") if isinstance(raw, dict) else None
        if named in DETECTORS and named not in EXCEPTABLE:
            res.refused.append((i, NOT_PERMITTED, f"{named} findings cannot be excepted"))
            continue
        ex, problem = normalize_exception(raw)
        if ex is None:
            res.refused.append((i, "schema-invalid", problem))
        elif ex["type"] not in EXCEPTABLE:
            res.refused.append((i, NOT_PERMITTED, f"{ex['type']} findings cannot be excepted"))
        else:
            usable.append(ex)
    for f in findings:
        match = None
        if f[0] in EXCEPTABLE and getattr(f, "passage_sha256", None):
            dest = destination_of(f[2].rsplit(":", 1)[0])
            for ex in usable:
                if ex["type"] == f[0] and ex["passage_sha256"] == f.passage_sha256 and dest in ex["destinations"]:
                    match = ex
                    break
        if match is None:
            res.unresolved.append(f)
        else:
            res.resolved.append((f, match))
    return res


def exception_preview_lines(resolution):
    """The lines for the owner's preview, under "What will be shared": one per exception that is
    being granted. They carry the type, the destinations, the passage digest and the reason."""
    seen, lines = set(), []
    for finding, ex in resolution.resolved:
        key = (ex["type"], ex["passage_sha256"], tuple(ex["destinations"]))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"detector exception granted: {ex['type']} for {', '.join(ex['destinations'])}, "
                     f"passage {ex['passage_sha256']}, reason: {ex['reason']}")
    return lines


# ---------------------------------------------------------------------------
# Running everything
# ---------------------------------------------------------------------------

def find_all(root, workspace, snapshot_files, skip=(), phrases=None, restricted_texts=None,
             allow_source_folder=(), plan_path=None):
    """Every finding, before any exception. Returns a list of Finding. root is the folder the file
    ids are relative to. workspace is the private workspace folder or None: without it the two
    owner-side detectors do not run. snapshot_files is a list of file ids relative to root, or a
    mapping of file id to path. skip names detectors to leave out."""
    files = read_files(root, snapshot_files)
    found = []

    def add(detector, hits):
        for hit in hits:
            found.append(Finding(detector, hit[0], hit[1], getattr(hit, "passage_sha256", None)))

    if "credentials" not in skip:
        add("credentials", credentials(files))
    if "private_paths" not in skip:
        add("private_paths", private_paths(files, workspace, root, allow_source_folder))
    if "prohibited_fields" not in skip:
        add("prohibited_fields", prohibited_fields(files))
    owner_files = {k: v for k, v in files.items() if not is_bundle_file(k)}
    if "org_phrases" not in skip:
        words = phrases if phrases is not None else read_phrases(workspace)
        if words:
            add("org_phrases", org_phrases(owner_files, words))
    if "copied_restricted" not in skip and (workspace or restricted_texts):
        texts = restricted_texts if restricted_texts is not None else restricted_renderings(root, workspace, plan_path)
        if texts:
            add("copied_restricted", copied_restricted(owner_files, texts))
    return found


def run_all(root, workspace, snapshot_files, exceptions=None, **options):
    """The findings that remain after the recorded exceptions, as a list of (detector, code,
    location) triples (Finding). A refused exception adds a finding of the detector "exceptions"
    with the code exception-not-permitted (or schema-invalid), located at
    detector_exceptions:<index>, so a caller that reads only this list fails.
    Options: skip, phrases, restricted_texts, allow_source_folder, plan_path."""
    raw = find_all(root, workspace, snapshot_files, **options)
    res = resolve(raw, exceptions)
    out = list(res.unresolved)
    for index, code, _ in res.refused:
        out.append(Finding("exceptions", code, f"detector_exceptions:{index}"))
    return out


def project_scope(root, plan):
    """File ids, relative to root, of the project files a release would publish: the specification
    folder, docs/context, docs/release and the engineers' skill folder, text files only."""
    root = Path(root)
    folders = [str(plan["project"].get("spec_dir") or "docs/spec"), "docs/context", "docs/release"]
    skill = plan["project"].get("dev_skill_path")
    if isinstance(skill, str) and skill.strip():
        folders.append(skill)
    ids = []
    for folder in folders:
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.is_symlink() and is_text_file(path.name):
                ids.append(path.relative_to(root).as_posix())
    return sorted(set(ids))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scan the published files of a project for credentials, private paths, staffing fields, "
                    "organization phrases and copied restricted passages. Read only. Prints file ids and line "
                    "numbers, never the matched text.",
        epilog="Exit status 0 with no findings, 1 with findings, 2 for a wrong argument.")
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--request", help="path to an approval-request.json whose detector_exceptions are applied")
    a = ap.parse_args(argv)
    why = L.root_problem(a.root)
    if why:
        print(f"error: {why}", file=sys.stderr)
        return 2
    root = Path(a.root).expanduser().resolve()
    try:
        plan_path = L.find_plan(root, a.plan)
        plan, _ = L.load_plan(plan_path, root)
    except L.PlanError as e:
        print(f"error: {e.msg}", file=sys.stderr)
        return 2
    exceptions = []
    if a.request:
        try:
            data = json.loads(Path(a.request).read_text(encoding="utf-8"))
            exceptions = data.get("detector_exceptions") or []
        except (OSError, ValueError, AttributeError):
            print("error: the request file cannot be read as an approval request", file=sys.stderr)
            return 2
    workspace, _ = L.workspace_root(root)
    skip = ("prohibited_fields",) if not plan.get("_modern") else ()
    findings = run_all(root, workspace, project_scope(root, plan), exceptions, skip=skip, plan_path=plan_path)
    for line in report_lines(findings):
        print(line)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
