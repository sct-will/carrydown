#!/usr/bin/env python3
"""Check that the approved context of one work item can be used, then say so or stop.

Run it from the repository, before you read anything for a work item:
  python3 check_context.py WI-03

It prints one line and exits 0 when the context is ready to read. Otherwise it prints one of four
messages and exits with the code beside it:
  10  carrydown: no approved context for <ID>
  11  carrydown: the approved context for <ID> is stale
  12  carrydown: <ID> cites an obligation that is not in its approved context
  13  carrydown: <ID> has a restricted destination that this project does not publish
A line `warning: freshness not confirmed; within offline grace` means the context passed but the
default branch could not be reached. The message never holds withheld text, a heading of a
restricted source, a private path or the name of an approver.

What it checks, in this order
  1. Local validity, offline. docs/context/<id>.md and <id>.bundle.json exist, the Markdown
     matches content_sha256 in the sidecar, every source section the specification cites is an
     obligation of the bundle, and a receipt in docs/release/ marked active lists both files with
     matching digests.
  2. Freshness. `git fetch origin <default branch>`, then the receipts of the fetched commit are
     read. The context is fresh only when an active receipt there lists both files with the same
     digests. A receipt that is superseded or withdrawn, here or there, makes the context stale:
     an older active receipt never replaces a newer terminal one. After a good fetch the check
     records the repository, the fetched commit, the request id and the time in
     .carrydown/cache/last-refresh (untracked).
  3. Offline grace. If the fetch fails, the check proceeds only when that record matches this
     repository and this request, is not dated in the future, and is no older than the receipt's
     offline_grace_days. With no valid record, or past the grace period, it is stale with the
     reason "could not refresh". Nothing is assumed about a release the clone has not seen.
  4. Expiry. The receipt's expires_at is compared with this computer's clock.

What this script is and is not. It lives in the engineer's checkout, so the engineer can edit it. It
is a convenience and an integrity check for the engineer. It is not a security control. The controls
are the release gate on the owner's side and the independent verifier on pull requests. It reads only
this repository, never a token, and its one network use is a `git fetch` with the credentials you
already have. It cannot recall text you already copied.

Options
  --root DIR      the repository (default: the top of the git repository you are in)
  --no-refresh    do not fetch; follow the offline grace rule

Exit status is 0, 10, 11, 12 or 13 as above, and 2 for a wrong argument.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ID_PREFIX = "{{id_prefix}}"
SPEC_DIR = "{{spec_dir}}"

CONTEXT_DIR = "docs/context"
RELEASE_DIR = "docs/release"
CACHE_FILE = ".carrydown/cache/last-refresh"
FETCH_TIMEOUT = 60
MAX_BYTES = 4 * 1024 * 1024
MAX_RECEIPTS = 500
STATES = ("active", "superseded", "withdrawn")

KINDS = {
    "missing": (10, "carrydown: no approved context for {id}", "Ask the plan owner to release the item."),
    "stale": (11, "carrydown: the approved context for {id} is stale", "Ask the plan owner to re-release, or connect and refresh."),
    "cites": (12, "carrydown: {id} cites an obligation that is not in its approved context", "Ask the plan owner. Do not guess the rule."),
    "restricted": (13, "carrydown: {id} has a restricted destination that this project does not publish", "Follow the owner's approved instruction."),
}

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,200}\Z")
_NUMBER = r"\d+(?:\.\d+)*"


class Block(Exception):
    """The context cannot be used. kind is a key of KINDS; reason is a fixed reason code."""

    def __init__(self, kind, reason=""):
        super().__init__(kind)
        self.kind = kind
        self.reason = reason


def prefix():
    return ID_PREFIX if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", ID_PREFIX) else "WI"


def spec_dir():
    value = SPEC_DIR if re.fullmatch(r"[A-Za-z0-9_./-]+", SPEC_DIR) and ".." not in SPEC_DIR.split("/") else "docs/spec"
    return value.strip("/") or "docs/spec"


def item_number(text):
    """The item number in an id written 3, 03, WI-03, wi-3 or WI03, or None."""
    m = re.fullmatch(r"\s*(?:" + re.escape(prefix()) + r"-?)?0*([0-9]+)\s*", str(text), re.I)
    return int(m.group(1)) if m else None


def shown_id(text, number):
    """The id as printed. A readable id is normalized to the project's form; anything else is cut
    down to safe characters, so an odd argument cannot put markup or a path into the message."""
    if number is not None:
        return f"{prefix()}-{number:02d}"
    return re.sub(r"[^A-Za-z0-9._-]", "", str(text))[:40] or "(no id)"


def message(kind, item_id, reason="", extra=()):
    code, first, action = KINDS[kind]
    lines = [first.format(id=item_id)]
    if reason:
        phrase = reason.replace("-", " ")
        lines.append("reason: " + (reason if phrase == reason else f"{phrase} ({reason})"))
    lines += list(extra)
    lines.append(action)
    return code, lines


# ---------------------------------------------------------------------------
# Reading files safely
# ---------------------------------------------------------------------------

def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


def _no_constant(name):
    raise ValueError("non-finite number")


def parse_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_constant=_no_constant)


def read_regular(path):
    """The bytes of a regular file that is not a link, or None."""
    try:
        if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_time(text):
    if not isinstance(text, str) or not _TIME.match(text):
        return None
    try:
        return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Local validity
# ---------------------------------------------------------------------------

def load_sidecar(raw, tag):
    """The parsed sidecar, or Block when it is not a sidecar of this item."""
    try:
        side = parse_json(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Block("missing")
    if not isinstance(side, dict) or not is_int(side.get("bundle_format")) or side["bundle_format"] != 1 \
            or side.get("work_item") != tag or not isinstance(side.get("obligations"), list) \
            or not isinstance(side.get("content_sha256"), str) or not _SHA256.match(side["content_sha256"]):
        raise Block("missing")
    if "restricted_destination" in side and not isinstance(side["restricted_destination"], bool):
        raise Block("missing")
    for ob in side["obligations"]:
        if not isinstance(ob, dict) or not isinstance(ob.get("source"), str) or not isinstance(ob.get("section"), str):
            raise Block("missing")
    return side


def spec_citations(root, tag, known_sources):
    """The (source id, section) pairs the specification of the item cites in its References section.
    The form is `- <source id> section <n.n>, <heading>`. A relative link into a rendering whose file
    name is a source id of the bundle, with "section n.n" in its label, counts too."""
    found = []
    base = Path(root) / spec_dir()
    try:
        files = sorted(p for p in base.rglob(f"{tag.lower()}-*.md") if p.is_file() and not p.is_symlink())[:5]
    except OSError:
        files = []
    for path in files:
        raw = read_regular(path)
        if raw is None:
            continue
        m = re.search(r"(?ms)^## References[ \t]*\n(.*?)(?=^## |\Z)", raw.decode("utf-8", "replace"))
        if not m:
            continue
        for line in m.group(1).split("\n"):
            new = re.match(r"^\s*[-*]\s+(\S+)\s+section\s+(" + _NUMBER + r")\b", line, re.I)
            if new:
                found.append((new.group(1), new.group(2)))
                continue
            for link in re.finditer(r"\[([^\]]*)\]\(([^)\s]+)\)", line):
                label = re.search(r"(?i)\bsections?\s+(" + _NUMBER + r")\b", link.group(1))
                stem = Path(link.group(2).split("#")[0]).stem
                if label and stem in known_sources:
                    found.append((stem, label.group(1)))
    return list(dict.fromkeys(found))


def parse_receipt(raw, name=None):
    """A receipt as a dict, or None when it is not shaped like one. This is a shape check for the
    convenience of the engineer. The verifier checks the whole schema."""
    try:
        r = parse_json(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    if not isinstance(r, dict) or r.get("receipt_format") != 1 or r.get("state") not in STATES:
        return None
    rid = r.get("request_id")
    if not isinstance(rid, str) or not _SHA256.match(rid) or (name is not None and name != rid + ".receipt.json"):
        return None
    arts = r.get("artifacts")
    if not isinstance(arts, list) or not all(isinstance(a, dict) and isinstance(a.get("path"), str)
                                             and isinstance(a.get("sha256"), str) and is_int(a.get("bytes")) for a in arts):
        return None
    if r.get("expires_at") is not None and parse_time(r["expires_at"]) is None:
        return None
    grace = r.get("offline_grace_days")
    if not is_int(grace) or grace < 0:
        return None
    if parse_time(r.get("created")) is None:
        return None
    return r


def local_receipts(root):
    out = {}
    folder = Path(root) / RELEASE_DIR
    try:
        names = sorted(p.name for p in folder.iterdir() if re.fullmatch(r"[0-9a-f]{64}\.receipt\.json", p.name))[:MAX_RECEIPTS]
    except OSError:
        return out
    for name in names:
        raw = read_regular(folder / name)
        r = parse_receipt(raw, name) if raw is not None else None
        if r is not None:
            out[r["request_id"]] = r
    return out


def lists(receipt, files):
    """True when the receipt lists every file (path -> (sha256, size)) with the same digest and length."""
    by_path = {a["path"]: a for a in receipt["artifacts"]}
    return all(p in by_path and by_path[p]["sha256"] == d and by_path[p]["bytes"] == n for p, (d, n) in files.items())


def terminal_reason(receipts):
    return "withdrawn" if any(r["state"] == "withdrawn" for r in receipts) else "superseded"


def newest(receipts):
    return sorted(receipts, key=lambda r: (r["created"], r["request_id"]))[-1]


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------

def git(root, *args, timeout=FETCH_TIMEOUT):
    """(exit status, stdout bytes). A missing git or a timeout is status 127."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    try:
        run = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError):
        return 127, b""
    return run.returncode, run.stdout


def default_branch(root):
    status, out = git(root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    if status == 0:
        ref = out.decode("utf-8", "replace").strip()
        branch = ref[len("refs/remotes/origin/"):] if ref.startswith("refs/remotes/origin/") else ""
    else:
        status, out = git(root, "ls-remote", "--symref", "origin", "HEAD")
        m = re.search(r"(?m)^ref: refs/heads/(\S+)\s+HEAD$", out.decode("utf-8", "replace")) if status == 0 else None
        branch = m.group(1) if m else ""
    return branch if _BRANCH.match(branch) else None


def fetched_receipts(root, commit):
    """{request id: receipt} read from docs/release/ of a fetched commit, or None when it cannot be read."""
    status, out = git(root, "ls-tree", "-r", "-z", "--name-only", commit, "--", RELEASE_DIR)
    if status != 0:
        return None
    names = [n for n in out.decode("utf-8", "replace").split("\0")
             if re.fullmatch(re.escape(RELEASE_DIR) + r"/[0-9a-f]{64}\.receipt\.json", n)]
    if len(names) > MAX_RECEIPTS:
        return None
    found = {}
    for name in names:
        status, blob = git(root, "cat-file", "blob", f"{commit}:{name}")
        if status != 0:
            return None
        r = parse_receipt(blob, name.rsplit("/", 1)[1]) if len(blob) <= MAX_BYTES else None
        if r is not None:
            found[r["request_id"]] = r
    return found


def merge(local, fetched):
    """Receipts by request id. A terminal state is never replaced by an active one."""
    out = dict(local)
    for rid, r in fetched.items():
        old = out.get(rid)
        if old is not None and old["state"] != "active" and r["state"] == "active":
            continue
        out[rid] = r
    return out


def judge_fetched(local, fetched, files):
    """("fresh", receipt) or ("stale", reason code) from the receipts of the fetched commit."""
    merged = merge(local, fetched)
    fresh = [merged[rid] for rid in fetched if merged[rid]["state"] == "active" and lists(merged[rid], files)]
    if fresh:
        return "fresh", newest(fresh)
    ended = [r for r in merged.values() if r["state"] != "active" and lists(r, files)]
    if ended:
        return "stale", terminal_reason(ended)
    paths = set(files)
    if any(r["state"] == "active" and paths & {a["path"] for a in r["artifacts"]} for r in fetched.values()):
        return "stale", "sha256-mismatch"
    return "stale", "approval-not-found"


def origin_identity(root):
    """The identity of this repository as the cache records it: the origin address without
    credentials, scheme or a trailing .git."""
    status, out = git(root, "config", "--get", "remote.origin.url")
    url = out.decode("utf-8", "replace").strip() if status == 0 else ""
    m = re.match(r"^(?:[A-Za-z][A-Za-z0-9+.-]*://)?(?:[^@/]*@)?([^/:]+)[:/](.+?)(?:\.git)?/?$", url)
    return (f"{m.group(1).lower()}/{m.group(2)}" if m else re.sub(r"\.git/?$", "", url)) or None


def refresh(root, files, local):
    """Fetch the default branch and judge its receipts. Returns ("fresh", receipt, commit),
    ("stale", reason, None) or ("unreachable", "could-not-refresh", None)."""
    branch = default_branch(root)
    if branch is None:
        return "unreachable", "could-not-refresh", None
    status, _ = git(root, "fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "origin", f"refs/heads/{branch}")
    if status != 0:
        return "unreachable", "could-not-refresh", None
    status, out = git(root, "rev-parse", "--verify", "--quiet", "FETCH_HEAD^{commit}")
    commit = out.decode("ascii", "replace").strip()
    if status != 0 or not _GIT_SHA.match(commit):
        return "unreachable", "could-not-refresh", None
    fetched = fetched_receipts(root, commit)
    if fetched is None:
        return "unreachable", "could-not-refresh", None
    verdict, detail = judge_fetched(local, fetched, files)
    if verdict == "stale":
        return "stale", detail, None
    return "fresh", detail, commit


def record_refresh(root, identity, commit, request_id, now):
    record = {"cache_format": 1, "repository": identity, "commit": commit, "request_id": request_id,
              "time": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    path = Path(root) / CACHE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(path))
    except OSError:
        pass


def grace_allows(root, identity, receipt, now):
    """True when the last good refresh matches this repository and this request and is within grace."""
    raw = read_regular(Path(root) / CACHE_FILE)
    try:
        record = parse_json(raw) if raw is not None else None
    except (ValueError, UnicodeDecodeError, RecursionError):
        return False
    if not isinstance(record, dict) or set(record) != {"cache_format", "repository", "commit", "request_id", "time"}:
        return False
    when = parse_time(record["time"])
    if record["cache_format"] != 1 or when is None or identity is None or record["repository"] != identity:
        return False
    if record["request_id"] != receipt["request_id"] or not isinstance(record["commit"], str) or not _GIT_SHA.match(record["commit"]):
        return False
    days = receipt["offline_grace_days"]
    if days == 0 or when > now or (now - when) > dt.timedelta(days=days):
        return False
    status, _ = git(root, "cat-file", "-e", record["commit"] + "^{commit}")
    return status == 0


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

def check(root, argument, now=None, refresh_allowed=True):
    """Run the check. Returns (exit status, lines to print)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    number = item_number(argument)
    tag = shown_id(argument, number)
    try:
        if number is None:
            raise Block("missing")
        stem = f"{tag.lower()}"
        md_rel, js_rel = f"{CONTEXT_DIR}/{stem}.md", f"{CONTEXT_DIR}/{stem}.bundle.json"
        md, js = read_regular(Path(root) / md_rel), read_regular(Path(root) / js_rel)
        if md is None or js is None:
            raise Block("missing")
        side = load_sidecar(js, tag)
        if sha256(md) != side["content_sha256"]:
            raise Block("missing")
        have = {(ob["source"], ob["section"]) for ob in side["obligations"]}
        for cited in spec_citations(root, tag, {s for s, _ in have}):
            if cited not in have:
                raise Block("cites")
        files = {md_rel: (sha256(md), len(md)), js_rel: (sha256(js), len(js))}
        local = local_receipts(root)
        matching = [r for r in local.values() if lists(r, files)]
        if not matching:
            raise Block("missing")
        active = [r for r in matching if r["state"] == "active"]
        if not active:
            raise Block("stale", terminal_reason(matching))
        receipt = newest(active)
        warnings = []
        identity = origin_identity(root)
        outcome, detail, commit = refresh(root, files, local) if refresh_allowed else ("unreachable", "could-not-refresh", None)
        if outcome == "stale":
            raise Block("stale", detail)
        if outcome == "fresh":
            receipt = detail
            record_refresh(root, identity, commit, receipt["request_id"], now)
        elif grace_allows(root, identity, receipt, now):
            warnings.append("warning: freshness not confirmed; within offline grace")
        else:
            raise Block("stale", "could-not-refresh")
        if receipt["expires_at"] is not None and now >= parse_time(receipt["expires_at"]):
            raise Block("stale", "expired")
        if side.get("restricted_destination") is True:
            raise Block("restricted")
    except Block as block:
        extra = [f"The owner's approved instruction is in {md_rel}."] if block.kind == "restricted" else []
        code, lines = message(block.kind, tag, block.reason, extra)
        return code, lines
    return 0, [f"carrydown: approved context for {tag} is ready", f"Read {md_rel}. Do not open docs/ground-truth/ or any source."] + warnings


def repository_top(start):
    status, out = git(start, "rev-parse", "--show-toplevel", timeout=15)
    top = out.decode("utf-8", "replace").strip() if status == 0 else ""
    return Path(top) if top and os.path.isdir(top) else Path(start)


def main(argv=None, now=None):
    ap = argparse.ArgumentParser(
        description="Check that the approved context of one work item can be used. Prints one line and exits 0, "
                    "or prints one of four carrydown messages and exits 10, 11, 12 or 13. "
                    "It is a convenience check for the engineer, not a security control.")
    ap.add_argument("id", help="the work item id, such as WI-03")
    ap.add_argument("--root", help="the repository (default: the top of the git repository you are in)")
    ap.add_argument("--no-refresh", action="store_true", help="do not run git fetch. Follow the offline grace rule")
    a = ap.parse_args(argv)
    root = Path(a.root).expanduser() if a.root else repository_top(os.getcwd())
    if not root.is_dir():
        print("error: --root is not a folder", file=sys.stderr)
        return 2
    code, lines = check(root.resolve(), a.id, now=now, refresh_allowed=not a.no_refresh)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
