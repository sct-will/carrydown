#!/usr/bin/env python3
"""Create and check the plan owner's private workspace. Offline. Standard library only.

The private workspace is an owner-only, git-initialized folder outside the engineering repository,
on the owner's machine. It always holds the staffing records (people.yaml). When some documents are
not approved for everyone who can read the repository, it also holds the sources, their renderings
and the drafts. It is never copied anywhere by default.

  ~/.carrydown/workspaces/<slug>/
    workspace.yaml   slug, the engineering repository, the staging repository (if any), state
    people.yaml      names, logins, skills, preferences, rationale, days off, allocation
    retention.yaml   what is kept, for how long, and what deletion can and cannot do
    sources/ renderings/ drafts/ releases/ requests/ events/ publication/
    renderings/reviewed/ and renderings/history/, and drafts/checkpoints/: the reviewed source checkpoints

The engineering repository gets one pointer, .carrydown/local.yaml, with the line `workspace: <path>`.
It is untracked: init appends it to .gitignore. Scripts the owner runs read the pointer. No tracked
file ever names the workspace.

Commands (every one reads files only; init writes only with --apply)
  python3 scripts/workspace.py init --root . --slug my-project               dry run: shows what would be created
  python3 scripts/workspace.py init --root . --slug my-project --apply       create the workspace and the pointer
  python3 scripts/workspace.py init --root . --slug my-project --answer no --apply
                                                                              also print the staging repository commands
  python3 scripts/workspace.py status --root .                               paths and state, no names
  python3 scripts/workspace.py doctor --root .                               permissions, path separation, ignore rules, plan schema,
                                                                              and the remote components, labeled not verifiable (offline)
  python3 scripts/workspace.py checkpoint prepare --root . --descriptor FILE --rendering FILE ...   maintainers: dry run, copies the reviewed renderings
  python3 scripts/workspace.py checkpoint commit --root . --id ID --apply    commit the prepared checkpoint in the workspace's git, read it back, record it
  python3 scripts/workspace.py checkpoint bind --root . --id ID --release-id R --request-id Q --apply
                                                                              record which release and request a checkpoint belongs to
  python3 scripts/workspace.py checkpoint list --root .                      count, latest id and whether the latest commit verifies

--answer is your answer to the one question of the interview: "Can everyone who can read this
repository see all of these documents and your staffing notes?" On no, init prints the commands
that create the private staging repository. It does not run them.

Reviewed source checkpoints (reconciliation). A checkpoint is the reviewed rendering of each source, a minimal
descriptor and a small record, committed in the workspace's own git repository on the ref
refs/carrydown/checkpoints through an isolated index, so the normal index, people.yaml, sources/ and every
other file stay out. It is recorded in workspace.yaml only after the commit is read back and every digest
matches. Nothing is pushed, mirrored or uploaded, and nothing goes under releases/ or into the project.
The checkpoint commands are for maintainers and agents. The owner never types them.

Permissions. On macOS, Linux and other POSIX systems the folder is created with mode 0o700 (owner
only) and the mode is read back; if it is not 0o700, or the folder is not yours, init stops. On
Windows the workspace is %USERPROFILE%\\.carrydown\\workspaces\\<slug>\\ and init applies an access
control list that names the current user only, with
  icacls <folder> /inheritance:r /grant:r "<DOMAIN\\user>:(OI)(CI)F"
then reads it back with `icacls <folder>`. The system account (NT AUTHORITY\\SYSTEM), BUILTIN\\Administrators
and OWNER RIGHTS may stay on the list, as they do on a profile folder. Any other principal stops init. The folder is
refused when its path is inside the engineering repository (workspace-inside-repository).

HOME (USERPROFILE on Windows) decides where ~ is, so a test can point it at a temporary folder.
Exit status is 0 when the command succeeded and the workspace is fine, 1 when a check fails, and 2
for a wrong argument or a refused path. No file is written outside the workspace and the project's
.carrydown/local.yaml and .gitignore, and nothing is sent anywhere.
"""
import argparse
import json
import os
import re
import stat as _stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402
import release_gate as RG  # noqa: E402

WORKSPACE_FORMAT = 1
POINTER = ".carrydown/local.yaml"
ANSWER_QUESTION = "Can everyone who can read this repository see all of these documents and your staffing notes?"
SUBFOLDERS = ("sources", "renderings", "drafts", "releases", "requests", "events", "publication")
RETENTION_HISTORY = ("Reconciliation keeps earlier reviewed renderings privately in this workspace. "
                     "Deleting raw inputs does not erase rendering history, backups or earlier copies.")
RETENTION_LIMITS = ("Deleting files from this workspace does not remove them from any backup, remote or copy made earlier. "
                    "Carrydown records what it deleted and when. " + RETENTION_HISTORY)
# Lines the project's .gitignore should hold. The first is required: it keeps the pointer out of git.
# The others are added by the scaffold and checked here as advice.
IGNORE_REQUIRED = (POINTER,)
IGNORE_ADVISED = ("docs/source/", "people.yaml", ".carrydown/cache/")
PEOPLE_STARTER = """# Staffing records for this project. Private: this file stays in your workspace.
# Each person has the same id as in plan.yaml. Fields: id, name, github (login for assignment),
# track, skills, preferences, assignment_rationale, allocation (percent), start, days_off.
# The sample in the carrydown repository (sample/expense-approvals/people.yaml) shows the shape.
people: []
advisors: []
"""


# ---------------------------------------------------------------------------
# Where things are
# ---------------------------------------------------------------------------

def home_dir():
    """The folder that ~ means: HOME on POSIX systems, USERPROFILE on Windows, the other as a fallback."""
    names = ("USERPROFILE", "HOME") if os.name == "nt" else ("HOME", "USERPROFILE")
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return Path(value)
    return Path.home()


def workspaces_base():
    return home_dir() / ".carrydown" / "workspaces"


def slug_problem(slug):
    if not slug or not L.SLUG_RE.fullmatch(slug) or len(slug) > L.MAX_LABEL:
        return (f"--slug {str(slug)[:40]!r} must be lowercase words joined by hyphens, at most {L.MAX_LABEL} characters, "
                "such as expense-approvals")
    return None


def clean_remote(url):
    """A remote URL with any user name or password removed, and any query or fragment, so a token in it is
    never kept or shown."""
    url = re.sub(r"^([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]*@", r"\1", url.strip())
    return re.sub(r"[?#].*\Z", "", url) if "://" in url else url


def engineering_remote(root):
    """The origin URL of the engineering repository, cleaned, or "" when there is none."""
    try:
        out = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return clean_remote(out.stdout) if out.returncode == 0 else ""


def remote_owner(remote):
    """The owner part of a GitHub remote such as git@github.com:acme/app.git or https://github.com/acme/app, or ""."""
    m = re.search(r"github\.com[:/]([A-Za-z0-9_.-]+)/[A-Za-z0-9_.-]+?(?:\.git)?/?$", remote or "")
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Permissions: owner only, verified by reading them back
# ---------------------------------------------------------------------------

def posix_permission_problem(path):
    """Why the folder is not owner-only, or None. The mode is read back from the file system, and the
    folder must belong to the current user."""
    try:
        st = os.stat(str(path))
    except OSError as e:
        return f"cannot read the permissions of the workspace: {e.strerror or e}"
    mode = _stat.S_IMODE(st.st_mode)
    if mode != 0o700:
        return f"the workspace has mode {mode:04o}, not 0700 (owner only)"
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        return "the workspace belongs to another user"
    return None


def parse_icacls(output, path):
    """The principals named in the output of `icacls <folder>`, in order. The first line starts with
    the folder path; later lines are indented. The summary line is ignored."""
    principals = []
    prefix = str(path)
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("successfully processed"):
            continue
        if line.startswith(prefix):
            line = line[len(prefix):].strip()
        m = re.match(r"^(.*?):\(", line)
        if m and m.group(1).strip():
            principals.append(m.group(1).strip())
    return principals


WINDOWS_OWN = ("nt authority\\system", "builtin\\administrators", "owner rights")   # beside the user on a profile folder


def windows_acl_problem(principals, user):
    """Why an access control list is not current-user-only, or None. principals is parse_icacls output,
    user is DOMAIN\\name (or just the name). The system account, the administrators group and the owner
    rights entry may stay, as they do on a Windows profile folder."""
    if not principals:
        return "the access control list could not be read back"
    wanted = {user.casefold(), user.casefold().split("\\")[-1]}
    others = sorted({p for p in principals if p.casefold() not in wanted and p.casefold().split("\\")[-1] not in wanted
                     and p.casefold() not in WINDOWS_OWN})
    if others:
        return f"{len(others)} other principal(s) can open the workspace ({', '.join(others)}). Only the current user may"
    return None


def windows_user():
    """The current user as DOMAIN\\name, from `whoami`, else from the environment."""
    try:
        out = subprocess.run(["whoami"], capture_output=True, text=True, timeout=20)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    domain, name = os.environ.get("USERDOMAIN", ""), os.environ.get("USERNAME", "")
    return f"{domain}\\{name}" if domain and name else name


def windows_permission_problem(path):
    """Read the access control list back with icacls and compare it with the current user."""
    try:
        out = subprocess.run(["icacls", str(path)], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return f"icacls could not be run: {e}"
    if out.returncode != 0:
        return "icacls could not read the access control list"
    return windows_acl_problem(parse_icacls(out.stdout, path), windows_user())


def permission_problem(path):
    return windows_permission_problem(path) if os.name == "nt" else posix_permission_problem(path)


def restrict_folder(path):
    """Make the folder owner-only: chmod 0700 on POSIX systems, icacls on Windows. Returns None when
    done, or the reason it could not be done. The result is not trusted: permission_problem reads it back."""
    if os.name == "nt":
        user = windows_user()
        try:
            out = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"],
                                 capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            return f"icacls could not be run: {e}"
        return None if out.returncode == 0 else "icacls refused to set the access control list"
    try:
        os.chmod(str(path), 0o700)
    except OSError as e:
        return f"cannot set the permissions: {e.strerror or e}"
    return None


# ---------------------------------------------------------------------------
# Small file helpers
# ---------------------------------------------------------------------------

def gitignore_has(text, entry):
    """True when a line of a .gitignore is exactly entry (a leading slash and trailing blanks ignored)."""
    wanted = entry.strip("/").strip()
    return any(line.strip().strip("/").strip() == wanted for line in text.splitlines() if not line.strip().startswith("#"))


def with_gitignore_entry(text, entry):
    """text with entry appended on its own line."""
    if text and not text.endswith("\n"):
        text += "\n"
    return text + entry + "\n"


def yaml_text(value):
    """A double-quoted YAML scalar. Forward slashes keep a Windows path readable and portable."""
    return json.dumps(str(value), ensure_ascii=False)


def workspace_yaml_text(slug, root, remote, staging, answer="yes"):
    """workspace.yaml. repo_audience_approved records the owner's answer to the one question, so that the
    release gate knows a "no" project from its first write, before any plan carries the handling block."""
    lines = [f"format: {WORKSPACE_FORMAT}", f"slug: {slug}", "engineering_repo:",
             f"  path: {yaml_text(Path(root).as_posix())}", f"  remote: {yaml_text(remote)}",
             f"repo_audience_approved: {'false' if answer == 'no' else 'true'}"]
    if staging:
        lines.append(f"staging_repository: {staging}")
    lines += ["policy_version: 1", "state: drafting"]
    return "\n".join(lines) + "\n"


def retention_yaml_text(raw_inputs):
    return f"raw_inputs: {raw_inputs}\nhistory: keep\nlimits: {yaml_text(RETENTION_LIMITS)}\n"


# ---------------------------------------------------------------------------
# Retention: raw_inputs: delete-after-release
# ---------------------------------------------------------------------------

RETENTION_LOG = "retention-log.jsonl"


def retention_choice(ws):
    """keep or delete-after-release, from the workspace's retention.yaml. Anything missing, unreadable or
    unknown is keep: nothing is deleted on a guess."""
    path = Path(ws) / "retention.yaml"
    if not path.is_file() or path.is_symlink():
        return "keep"
    try:
        data = L.load_file(path)
    except (L.YamlError, L.TextError, OSError):
        return "keep"
    value = data.get("raw_inputs") if isinstance(data, dict) else None
    return value if value == "delete-after-release" else "keep"


def raw_inputs(ws):
    """The raw inputs in <workspace>/sources/, as sorted relative paths, without following any link. A
    link is listed as itself: deleting it removes the link, never what it points to. A sources folder
    that is itself a link, or that is missing, holds nothing to delete."""
    base = Path(ws) / "sources"
    if base.is_symlink() or not base.is_dir():
        return []
    out = []
    for folder, dirs, files in os.walk(str(base), followlinks=False):
        here = Path(folder)
        for name in list(dirs):
            if (here / name).is_symlink():
                out.append((here / name).relative_to(base).as_posix())
                dirs.remove(name)
        for name in files:
            out.append((here / name).relative_to(base).as_posix())
    return sorted(out)


def apply_retention(ws, request_id, apply, when=None):
    """Carry out raw_inputs: delete-after-release once a release is active and exported (specification E2).
    Returns the lines to print, none when the owner chose keep or nothing is left to delete.

    With apply, every regular file and link under <workspace>/sources/ is removed (a link itself, never
    its target), the emptied folders under it go too, and one line is appended to
    <workspace>/retention-log.jsonl: the time, the request id, and each deleted path with its size and
    SHA-256 (never its content). Without apply nothing changes and the lines say what would go. Deleting
    here does not remove a copy in a backup, a remote, the workspace's own git history or an earlier clone,
    and the lines say so."""
    if retention_choice(ws) != "delete-after-release":
        return []
    base = Path(ws) / "sources"
    paths = raw_inputs(ws)
    if not paths:
        return []
    limits = ("Copies in backups, remotes, the workspace's git history or earlier clones are not removed. "
              f"The record is {RETENTION_LOG} in the private workspace. " + RETENTION_HISTORY)
    if not apply:
        return [f"retention: with --apply, {len(paths)} raw input file(s) in the private workspace's sources/ folder would be deleted, "
                "as the owner chose (delete-after-release). " + limits]
    deleted = []
    for rel in paths:
        target = base / rel
        entry = {"path": rel}
        try:
            if target.is_symlink():
                entry["link"] = True
            else:
                entry["bytes"] = target.stat().st_size
                entry["sha256"] = L.sha256_file(target)
            target.unlink()
        except OSError:
            continue
        deleted.append(entry)
    for folder, dirs, _ in os.walk(str(base), topdown=False, followlinks=False):
        for name in dirs:
            try:
                (Path(folder) / name).rmdir()
            except OSError:
                pass
    stamp = when or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record = {"time": stamp, "request_id": request_id, "rule": "delete-after-release", "deleted": deleted}
    with open(str(Path(ws) / RETENTION_LOG), "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    lines = [f"retention: deleted {len(deleted)} raw input file(s) from the private workspace's sources/ folder, as the owner chose "
             "(delete-after-release). " + limits]
    if len(deleted) != len(paths):
        lines.append(f"retention: {len(paths) - len(deleted)} file(s) could not be deleted and are still there; the record lists only what went")
    return lines


def gate_or_die(write_class, rel, text, root):
    """Ask the release gate before a write into the engineering repository, as every such write does."""
    decision = RG.check(write_class, rel, L.sha256_text(text), "engineering", str(root))
    if not decision.allowed:
        L.die(f"{decision.code}: the release gate refused the write of {rel}. Nothing was changed")


def staging_commands(staging):
    """The commands that create the private staging repository, as lines of text. They are printed and
    never run. Paths are those of the installed templates."""
    owner_name = staging if staging else "OWNER/NAME"
    name = owner_name.split("/", 1)[1]
    tpl = L.templates_dir() / "staging"
    workflow = tpl / "open-release-request.yml"
    ruleset = tpl / "ruleset.json"
    win = os.name == "nt"
    lines = ["Staging repository. Private, and only for the \"no\" answer. Carrydown does not run these commands.",
             "Run them yourself, or ask an organization administrator. Creating a repository on GitHub is an external write, so it needs your own say-so.",
             "  1. Create the private repository:",
             f"       gh repo create {owner_name} --private --description \"Carrydown release candidates. Private.\"",
             "  2. Add the workflow that opens a pull request for each release request, so you are not its author:"]
    if win:
        lines += [f"       gh repo clone {owner_name}",
                  f"       New-Item -ItemType Directory -Force {name}\\.github\\workflows",
                  f"       Copy-Item \"{workflow}\" \"{name}\\.github\\workflows\\open-release-request.yml\""]
    else:
        lines += [f"       gh repo clone {owner_name}",
                  f"       mkdir -p {name}/.github/workflows",
                  f"       cp \"{workflow}\" \"{name}/.github/workflows/open-release-request.yml\""]
    lines += [f"       git -C {name} add .github/workflows/open-release-request.yml",
              f"       git -C {name} commit -m \"Add the release request workflow\"",
              f"       git -C {name} push",
              "  3. Let Actions open pull requests, with read-only repository permissions:",
              f"       gh api -X PUT repos/{owner_name}/actions/permissions/workflow -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true"]
    if ruleset.is_file():
        lines += ["  4. Protect the default branch with the ruleset:",
                  f"       gh api -X POST repos/{owner_name}/rulesets --input \"{ruleset}\""]
    else:
        lines += ["  4. The branch ruleset ships with the release commands. Do not upload a release candidate before it is applied."]
    lines += ["Only you, the approvers and administrators you name may read this repository. Check that before the first upload."]
    return lines


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def plan_hint(root):
    """(slug, repo, repo_audience_approved, retain_raw_inputs) from the project's plan.yaml when it has
    one, else Nones. A plan that cannot be read is simply not a hint."""
    path = L.find_plan(root, None)
    if not L.exists(path):
        return None, None, None, None
    try:
        plan, _ = L.load_plan(path, root)
    except L.PlanError:
        return None, None, None, None
    proj = plan["project"]
    handling = proj.get("handling") if isinstance(proj.get("handling"), dict) else {}
    return proj.get("slug"), proj.get("repo"), handling.get("repo_audience_approved"), handling.get("retain_raw_inputs")


def cmd_init(a):
    root = L.project_root(a.root)
    hint_slug, hint_repo, hint_approved, hint_retain = plan_hint(root)
    slug = a.slug if a.slug is not None else (hint_slug or L.slugify(root.name))
    why = slug_problem(slug)
    if why:
        L.die(why)
    if a.workspace is not None and not str(a.workspace).strip():
        L.die("--workspace is empty. Give a folder outside the project, or leave it out to use ~/.carrydown/workspaces/<slug>")
    ws = Path(a.workspace).expanduser() if a.workspace else workspaces_base() / slug
    ws = Path(os.path.realpath(str(ws)))
    if L.path_inside_repository(root, ws):
        L.die(f"workspace-inside-repository: {ws} is inside the engineering repository, where every reader of the repository could "
              "see it. Choose a folder outside it (leave out --workspace to use ~/.carrydown/workspaces/<slug>). Nothing was written")
    answer = a.answer
    if answer is None:
        answer = "no" if hint_approved is False else "yes"
    retain = a.retain or (hint_retain if hint_retain in ("keep", "delete-after-release") else "keep")
    remote = engineering_remote(root)
    staging = None
    if answer == "no":
        if a.staging_repository is not None and not L.repo_ok(a.staging_repository):
            L.die(f"--staging-repository must look like owner/name, got {a.staging_repository!r}")
        owner = remote_owner(remote) or (str(hint_repo).split("/", 1)[0] if hint_repo and "/" in str(hint_repo) else "")
        staging = a.staging_repository or (f"{owner}/{slug}-releases" if owner else None)
    existing = ws / "workspace.yaml"
    reuse = False
    if L.exists(ws):
        if not ws.is_dir():
            L.die(f"{ws} exists and is not a folder, so nothing was written")
        if existing.is_file():
            try:
                data = L.load_file(existing)
            except (L.YamlError, L.TextError):
                data = None
            repo_path = (data or {}).get("engineering_repo", {}) if isinstance(data, dict) else {}
            same = isinstance(repo_path, dict) and isinstance(data, dict) and data.get("slug") == slug and \
                os.path.realpath(str(repo_path.get("path", ""))) == os.path.realpath(str(root))
            if not same:
                L.die(f"{ws} is already a workspace for another project. Nothing was written. Choose another --slug or --workspace")
            reuse = True
        elif any(ws.iterdir()):
            L.die(f"{ws} exists and is not empty, and it is not a carrydown workspace. Nothing was written. Choose another --slug or --workspace")
    pointer = root / ".carrydown" / "local.yaml"
    pointer_text = (f"# Local pointer to the private workspace. Untracked: never commit it. Written by workspace.py.\n"
                    f"workspace: {yaml_text(ws.as_posix())}\n")
    pointer_ok = False
    if pointer.is_file():
        try:
            data = L.load_file(pointer)
            value = data.get("workspace") if isinstance(data, dict) else None
        except (L.YamlError, L.TextError):
            value = None
        if isinstance(value, str) and value.strip() and \
                os.path.realpath(str(root / Path(value.strip()).expanduser())) == os.path.realpath(str(ws)):
            pointer_ok = True
        else:
            L.die(f"{POINTER} already points to another workspace. Nothing was written. Remove that file if you mean to move the project's workspace")
    ignore_path = root / ".gitignore"
    ignore_old = L.read_text(ignore_path) if ignore_path.is_file() else ""
    ignore_new = ignore_old if gitignore_has(ignore_old, POINTER) else with_gitignore_entry(ignore_old, POINTER)

    if not a.apply:
        L.say("carrydown workspace init  DRY RUN (nothing will be written)")
        L.say(f"workspace: {ws}  (outside the engineering repository)")
        L.say(("would reuse the existing workspace and check its permissions" if reuse else
               "would create the folder with owner-only permissions" + (" (mode 0700)" if os.name != "nt" else " (icacls, current user only)")
               + f", read them back, run git init, and write workspace.yaml, retention.yaml and a starter people.yaml, plus {', '.join(SUBFOLDERS)}"))
        L.say(("pointer " + POINTER + " is already in place") if pointer_ok else f"would write {POINTER} in {root} (untracked)")
        L.say(f"would append {POINTER} to .gitignore" if ignore_new != ignore_old else f".gitignore already ignores {POINTER}")
        if answer == "no":
            L.say("")
            for line in staging_commands(staging):
                L.say(line)
        L.say("\nDry run complete. Add --apply to create the workspace.")
        return 0

    created = []
    base = workspaces_base()
    try:
        if not ws.exists():
            if a.workspace is None:
                for folder in (base.parent, base):
                    if not folder.exists():
                        folder.mkdir(mode=0o700)
                        created.append(folder)
                        problem = restrict_folder(folder)
                        if problem:
                            raise OSError(problem)
            else:
                ws.parent.mkdir(parents=True, exist_ok=True)
            ws.mkdir(mode=0o700)
            created.append(ws)
        problem = restrict_folder(ws) or permission_problem(ws)
    except OSError as e:
        problem = e.strerror or str(e)
    if problem:
        for folder in reversed(created):
            try:
                folder.rmdir()
            except OSError:
                pass
        L.die(f"the workspace permissions could not be verified ({problem}). Nothing was written into it")
    gitdir = ws / ".git"
    if not gitdir.exists():
        try:
            run = subprocess.run(["git", "init", "-q"], cwd=str(ws), capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            L.die(f"git could not be run ({e}). Install git, then run this again. The folder {ws} is empty and may be removed")
        if run.returncode != 0:
            L.die("git init failed in the workspace. Check that git works, then run this again")
    for sub in SUBFOLDERS:
        (ws / sub).mkdir(exist_ok=True)
    if not reuse:
        L.write_text(ws / "workspace.yaml", workspace_yaml_text(slug, root, remote, staging, answer))
        L.write_text(ws / "retention.yaml", retention_yaml_text(retain))
    if not (ws / "people.yaml").exists():
        L.write_text(ws / "people.yaml", PEOPLE_STARTER)
    if not pointer_ok:
        gate_or_die("draft", POINTER, pointer_text, root)
        L.write_text(pointer, pointer_text)
    if ignore_new != ignore_old:
        gate_or_die("draft", ".gitignore", ignore_new, root)
        L.write_text(ignore_path, ignore_new)
    back, why_not = L.workspace_root(root)
    if back is None:
        L.die(f"the pointer was written but cannot be read back ({why_not}). Check {POINTER}")
    L.say(f"carrydown: private workspace ready at {ws} (owner only, git initialized)")
    if answer == "no":
        L.say("")
        for line in staging_commands(staging):
            L.say(line)
    return 0


# ---------------------------------------------------------------------------
# Reviewed source checkpoints (specification 6.1 to 6.3)
#
# A checkpoint is the reviewed rendering of every source in the set, a minimal descriptor and a small
# record, committed in the workspace's own git repository and then recorded in workspace.yaml. It lives
# only under renderings/reviewed/ and drafts/checkpoints/. It never goes into the project, into
# releases/ or into any snapshot, and nothing here pushes or adds a remote.
# ---------------------------------------------------------------------------

CHECKPOINT_FORMAT = 1
CHECKPOINT_REF = "refs/carrydown/checkpoints"
REVIEWED_DIR = "renderings/reviewed"
HISTORY_DIR = "renderings/history"
CHECKPOINT_DIR = "drafts/checkpoints"
CHECKPOINT_PREFIXES = (REVIEWED_DIR + "/", CHECKPOINT_DIR + "/")
# The exact words of specification 6.2, for a caller that finds no checkpoint to compare with.
CHECKPOINT_UNAVAILABLE = ("A previous complete source checkpoint is unavailable. Review the current sources to establish one. "
                          "Earlier uncited changes cannot be assessed automatically.")
MAX_RENDERING_BYTES = 16 * 1024 * 1024
MAX_RECORD_BYTES = 1024 * 1024
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.(?:md|index\.txt)\Z")
_LABEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
DESCRIPTOR_KEYS = ("plan_sha256", "sources")
DESCRIPTOR_SOURCE_KEYS = ("id", "version", "rendering", "content_sha256", "rendering_sha256", "precedence",
                          "applicability", "classification", "extraction_limits")
CLASSIFICATIONS = ("public", "repo-readers", "restricted")


class CheckpointProblem(Exception):
    """A checkpoint step that cannot go ahead. code is a fixed word (checkpoint-missing, checkpoint-mismatch,
    checkpoint-invalid, checkpoint-staged-changes, checkpoint-identity-missing, checkpoint-path-refused,
    checkpoint-git-failed, checkpoint-gate-refused). message says what to do next in plain words and never
    holds source content."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def checkpoint_id_of(entries):
    """The checkpoint id: the SHA-256 of the sorted (path, digest) list. entries are (path, sha256) pairs:
    each reviewed rendering by its workspace-relative path, and the descriptor as ("descriptor.json", digest)."""
    pairs = sorted((str(p), str(d)) for p, d in entries)
    return L.sha256_text(json.dumps(pairs, separators=(",", ":"), ensure_ascii=True))


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_bytes(data):
    return RG.RS.sha256_bytes(data)


def _git_env(extra=None):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    if extra:
        env.update(extra)
    return env


def _git(ws, *args, env=None, data=None):
    """Run git in the workspace. Returns the completed process with bytes in stdout and stderr. A git that
    cannot be run is a checkpoint-git-failed problem."""
    if not (Path(ws) / ".git").exists():
        raise CheckpointProblem("checkpoint-git-failed", "the private workspace is not a git repository. Run workspace.py init --apply, then try again")
    try:
        return subprocess.run(["git", "-C", str(ws), "-c", "commit.gpgsign=false"] + list(args), capture_output=True, timeout=120,
                              env=_git_env(env), input=data)
    except (OSError, subprocess.SubprocessError) as e:
        raise CheckpointProblem("checkpoint-git-failed", f"git could not be run ({e}). Install git, then try again")


def _git_ok(ws, *args, env=None, data=None):
    run = _git(ws, *args, env=env, data=data)
    if run.returncode != 0:
        raise CheckpointProblem("checkpoint-git-failed", "a git command failed in the private workspace. Run workspace.py doctor, then try again")
    return run.stdout


def _gate_candidate(root, rel, data, apply):
    """Ask the release gate about a write into the private workspace, as every such write does. A caller
    without a project root skips the question: the write is inside the workspace either way."""
    if root is None:
        return
    decision = RG.check("candidate", rel, _sha256_bytes(data), "workspace", str(root), dry_run=not apply)
    if not decision.allowed:
        raise CheckpointProblem("checkpoint-gate-refused", f"{decision.code}: the release gate refused the write of workspace:{rel}. Nothing was written")


def _text_value(value, where, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or _CONTROL.search(value):
        raise CheckpointProblem("checkpoint-invalid", f"{where} must be a short line of text")
    return value


def _scalar_value(value, where):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    return _text_value(value, where)


def project_descriptor(sources, plan_sha256):
    """The minimal source descriptor from plan.yaml style source entries: only the allowlisted keys, with
    precedence set from the order of the list (1 is the highest). A name, a path of an original, staffing
    or any other key is dropped here and refused by checkpoint_prepare if it is passed in directly."""
    out = []
    for index, source in enumerate(sources or [], start=1):
        if not isinstance(source, dict):
            continue
        item = {k: source[k] for k in DESCRIPTOR_SOURCE_KEYS if k in source and source[k] is not None}
        item.setdefault("precedence", index)
        out.append(item)
    return {"plan_sha256": plan_sha256, "sources": out}


def _clean_descriptor(descriptor):
    """The descriptor, checked and normalized, or a checkpoint-invalid problem. Strict: any key outside the
    allowlist is refused, so staffing or a path of an original can never ride along."""
    if not isinstance(descriptor, dict):
        raise CheckpointProblem("checkpoint-invalid", "the source descriptor must be a mapping")
    extra = sorted(str(k) for k in descriptor if k not in DESCRIPTOR_KEYS)
    if extra:
        raise CheckpointProblem("checkpoint-invalid", f"the source descriptor may hold only {', '.join(DESCRIPTOR_KEYS)}. Remove: {', '.join(extra)[:80]}")
    plan_sha = descriptor.get("plan_sha256")
    if not isinstance(plan_sha, str) or not _HEX64.match(plan_sha):
        raise CheckpointProblem("checkpoint-invalid", "plan_sha256 in the source descriptor must be 64 lowercase hex digits")
    sources = descriptor.get("sources")
    if not isinstance(sources, list) or not sources or len(sources) > 200:
        raise CheckpointProblem("checkpoint-invalid", "the source descriptor needs a list of sources")
    cleaned, seen = [], set()
    for number, source in enumerate(sources, start=1):
        where = f"source {number} of the source descriptor"
        if not isinstance(source, dict):
            raise CheckpointProblem("checkpoint-invalid", f"{where} must be a mapping")
        extra = sorted(str(k) for k in source if k not in DESCRIPTOR_SOURCE_KEYS)
        if extra:
            raise CheckpointProblem("checkpoint-invalid", f"{where} may hold only {', '.join(DESCRIPTOR_SOURCE_KEYS)}. Remove: {', '.join(extra)[:80]}")
        sid = source.get("id")
        if not isinstance(sid, str) or not _SOURCE_ID.match(sid) or sid in (".", ".."):
            raise CheckpointProblem("checkpoint-invalid", f"{where} needs an id of letters, digits, dots, underscores and hyphens")
        if sid in seen:
            raise CheckpointProblem("checkpoint-invalid", f"source id {sid} appears twice in the source descriptor")
        seen.add(sid)
        item = {"id": sid}
        version = source.get("version")
        if isinstance(version, (int, float)) and not isinstance(version, bool):
            version = str(version)
        item["version"] = _text_value(version, f"the version of source {sid}", 80)
        if source.get("rendering") is not None:
            name = _text_value(source["rendering"], f"the rendering name of source {sid}", 100)
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
                raise CheckpointProblem("checkpoint-invalid", f"the rendering name of source {sid} must be a plain file name without an extension")
            item["rendering"] = name
        for key in ("content_sha256", "rendering_sha256"):
            if source.get(key) is not None:
                if not isinstance(source[key], str) or not _HEX64.match(source[key]):
                    raise CheckpointProblem("checkpoint-invalid", f"{key} of source {sid} must be 64 lowercase hex digits")
                item[key] = source[key]
        if source.get("precedence") is not None:
            if type(source["precedence"]) is not int or source["precedence"] < 1:
                raise CheckpointProblem("checkpoint-invalid", f"precedence of source {sid} must be a whole number from 1")
            item["precedence"] = source["precedence"]
        if source.get("classification") is not None:
            if source["classification"] not in CLASSIFICATIONS:
                raise CheckpointProblem("checkpoint-invalid", f"classification of source {sid} must be public, repo-readers or restricted")
            item["classification"] = source["classification"]
        for key in ("applicability", "extraction_limits"):
            value = source.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                if len(value) > 50:
                    raise CheckpointProblem("checkpoint-invalid", f"{key} of source {sid} holds too many entries")
                item[key] = [_scalar_value(v, f"{key} of source {sid}") for v in value]
            elif isinstance(value, dict) and key == "extraction_limits":
                if len(value) > 50:
                    raise CheckpointProblem("checkpoint-invalid", f"{key} of source {sid} holds too many entries")
                item[key] = {_text_value(str(k), f"a key of {key} of source {sid}", 80): _scalar_value(v, f"{key} of source {sid}") for k, v in value.items()}
            else:
                item[key] = _scalar_value(value, f"{key} of source {sid}")
        cleaned.append(item)
    return {"plan_sha256": plan_sha, "sources": cleaned}


def _read_regular(path, limit=MAX_RENDERING_BYTES):
    """The bytes of a regular file that is not a link, read within a size limit, or None."""
    try:
        st = os.lstat(str(path))
    except OSError:
        return None
    if not _stat.S_ISREG(st.st_mode) or st.st_size > limit:
        return None
    try:
        with open(str(path), "rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    return data if len(data) <= limit else None


def _path_has_link(ws, rel):
    """True when any existing part of workspace/rel, below the workspace folder, is a symbolic link."""
    here = Path(ws)
    for part in Path(rel).parts:
        here = here / part
        if here.is_symlink():
            return True
    return False


def _write_private(path, data):
    """Write bytes to a file in the workspace through a temporary file, so a stop never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(str(temp), str(path))
    except OSError as e:
        try:
            temp.unlink()
        except OSError:
            pass
        raise CheckpointProblem("checkpoint-path-refused", f"cannot write in the private workspace: {e.strerror or e}")


def _rendering_entries(renderings, sources, ws, root):
    """The renderings as (source id, file name, bytes, origin label), checked. An entry is a path, or a
    (source id, path) pair, or a mapping with source_id and path. A bare path is matched to the source whose
    rendering name or id is the file name without .md or .index.txt."""
    by_stem = {}
    for s in sources:
        by_stem.setdefault(s.get("rendering", s["id"]), s["id"])
        by_stem.setdefault(s["id"], s["id"])
    ids = {s["id"] for s in sources}
    out, seen = [], set()
    forbidden = [Path(os.path.realpath(str(Path(ws) / "sources")))]
    if root is not None:
        forbidden.append(Path(os.path.realpath(str(Path(root) / "docs" / "source"))))
    for entry in list(renderings or []):
        sid = None
        if isinstance(entry, dict):
            sid, entry = entry.get("source_id"), entry.get("path")
        elif isinstance(entry, (tuple, list)) and len(entry) == 2:
            sid, entry = entry
        path = Path(str(entry))
        name = path.name
        if not _FILE_NAME.match(name):
            raise CheckpointProblem("checkpoint-invalid", f"{name[:60]} is not a rendering file. A rendering is <name>.md or <name>.index.txt")
        if sid is None:
            stem = name[:-len(".index.txt")] if name.endswith(".index.txt") else name[:-len(".md")]
            sid = by_stem.get(stem)
            if sid is None:
                raise CheckpointProblem("checkpoint-invalid", f"{name[:60]} matches no source in the descriptor. Pass it with its source id")
        if sid not in ids:
            raise CheckpointProblem("checkpoint-invalid", f"{name[:60]} is for a source that is not in the descriptor")
        real = Path(os.path.realpath(str(path)))
        for bad in forbidden:
            if real == bad or bad in real.parents:
                raise CheckpointProblem("checkpoint-invalid", f"{name[:60]} is in a folder of original documents. A checkpoint holds renderings only, never originals")
        data = _read_regular(path)
        if data is None:
            raise CheckpointProblem("checkpoint-invalid", f"{name[:60]} cannot be read as a regular file of a reasonable size")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise CheckpointProblem("checkpoint-invalid", f"{name[:60]} is not UTF-8 text")
        if name.endswith(".md") and not text.startswith("<!-- Generated from "):
            raise CheckpointProblem("checkpoint-invalid", f"{name[:60]} does not carry the generated header of a rendering, so it may be an original. A checkpoint holds renderings only")
        kind = "md" if name.endswith(".md") else "index"
        if (sid, kind) in seen:
            raise CheckpointProblem("checkpoint-invalid", f"source {sid} has more than one {'rendering' if kind == 'md' else 'section index'} in the list")
        seen.add((sid, kind))
        out.append((sid, name, data, str(path)))
    have = {sid for sid, name, _, _ in out if name.endswith(".md")}
    missing = sorted(ids - have)
    if missing:
        raise CheckpointProblem("checkpoint-invalid", f"no rendering was given for source {', '.join(missing)[:80]}. Every source in the set needs its .md rendering")
    return sorted(out, key=lambda e: (e[0], e[1]))


def checkpoint_prepare(root, workspace, renderings, descriptor, apply=False):
    """Prepare a source checkpoint (specification 6.1). Copies the renderings of the set into
    <workspace>/renderings/reviewed/<source id>/ and writes the descriptor and checkpoint.json under
    <workspace>/drafts/checkpoints/<checkpoint id>/. The copies are private: a rendering is read from the
    project (the "yes" path) or from <workspace>/renderings/ (the "no" path), never an original. Writes only
    with apply=True. Returns a dict: id, apply, created, plan_sha256, sources, files (path, sha256, bytes,
    action write or unchanged), checkpoint_path. The checkpoint id is the SHA-256 of the sorted (path,
    digest) list of the renderings and the descriptor."""
    ws = Path(workspace)
    clean = _clean_descriptor(descriptor)
    entries = _rendering_entries(renderings, clean["sources"], ws, root)
    files = []
    for sid, name, data, _origin in entries:
        rel = f"{REVIEWED_DIR}/{sid}/{name}"
        files.append({"path": rel, "sha256": _sha256_bytes(data), "bytes": len(data), "_data": data})
    descriptor_bytes = _json_bytes({"format": CHECKPOINT_FORMAT, **clean})
    descriptor_sha = _sha256_bytes(descriptor_bytes)
    cid = checkpoint_id_of([(f["path"], f["sha256"]) for f in files] + [("descriptor.json", descriptor_sha)])
    folder = f"{CHECKPOINT_DIR}/{cid}"
    by_source = {}
    for f in files:
        if f["path"].endswith(".md"):
            by_source[f["path"].split("/")[2]] = f["sha256"]
    created = _now()
    existing = _read_regular(ws / f"{folder}/checkpoint.json")
    if existing is not None:
        try:
            previous = json.loads(existing.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            previous = None
        if isinstance(previous, dict) and previous.get("id") == cid and isinstance(previous.get("created"), str):
            created = previous["created"]      # a repeat of the same checkpoint keeps its first creation time
    meta = {"format": CHECKPOINT_FORMAT, "id": cid, "created": created, "plan_sha256": clean["plan_sha256"],
            "sources": [{"id": s["id"], "version": s["version"], "sha256": by_source[s["id"]]} for s in clean["sources"]],
            "files": [{"path": f["path"], "sha256": f["sha256"]} for f in files],
            "descriptor_sha256": descriptor_sha}
    meta_bytes = _json_bytes(meta)
    writes = [(f["path"], f["_data"]) for f in files] + [(f"{folder}/descriptor.json", descriptor_bytes), (f"{folder}/checkpoint.json", meta_bytes)]
    result_files = []
    for rel, data in writes:
        if not rel.startswith(CHECKPOINT_PREFIXES) or ".." in Path(rel).parts or _path_has_link(ws, rel):
            raise CheckpointProblem("checkpoint-path-refused", f"workspace:{rel} is not a place a checkpoint may write")
        _gate_candidate(root, rel, data, apply)
        current = _read_regular(ws / rel)
        result_files.append({"path": rel, "sha256": _sha256_bytes(data), "bytes": len(data),
                             "action": "unchanged" if current == data else "write"})
    if apply:
        for rel, data in writes:
            if _read_regular(ws / rel) != data:
                _write_private(ws / rel, data)
    return {"id": cid, "apply": bool(apply), "created": created, "plan_sha256": clean["plan_sha256"], "sources": meta["sources"],
            "files": result_files, "checkpoint_path": f"{folder}/checkpoint.json"}


def _identity_problem(ws):
    """Why git has no author or committer for the workspace, or None. Resolved the way git resolves them:
    the environment first, then the author.* and committer.* settings, then user.name and user.email, all
    read from one listing of git's configuration. Nothing is invented."""
    run = _git(ws, "config", "-z", "--list")
    settings = {}
    if run.returncode == 0:
        for item in run.stdout.decode("utf-8", "replace").split("\x00"):
            key, _, value = item.partition("\n")
            if key:
                settings[key.lower()] = value.strip()           # a later setting overrides an earlier one
    for role in ("AUTHOR", "COMMITTER"):
        low = role.lower()
        name = os.environ.get(f"GIT_{role}_NAME", "").strip() or settings.get(f"{low}.name") or settings.get("user.name")
        email = os.environ.get(f"GIT_{role}_EMAIL", "").strip() or settings.get(f"{low}.email") or settings.get("user.email")
        if not name or not email:
            return ("No git name and email are set for the private workspace, so no author can be recorded and nothing was committed. "
                    "Set them once, for example: git config --global user.name \"Your Name\" and git config --global user.email \"you@example.com\". "
                    "Then run this again")
    return None


def _staged_count(ws):
    run = _git(ws, "diff", "--cached", "--name-only", "-z")
    if run.returncode != 0:
        raise CheckpointProblem("checkpoint-git-failed", "the staged changes of the private workspace could not be read. Run workspace.py doctor, then try again")
    return len([p for p in run.stdout.split(b"\x00") if p])


def _load_checkpoint_meta(data, checkpoint_id):
    """checkpoint.json bytes as a checked dict, or a checkpoint-mismatch problem."""
    try:
        meta = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise CheckpointProblem("checkpoint-mismatch", "checkpoint.json is not valid. Review the current sources to establish a new checkpoint")
    ok = isinstance(meta, dict) and meta.get("format") == CHECKPOINT_FORMAT and meta.get("id") == checkpoint_id \
        and isinstance(meta.get("files"), list) and isinstance(meta.get("sources"), list) \
        and isinstance(meta.get("descriptor_sha256"), str) and _HEX64.match(meta["descriptor_sha256"]) \
        and isinstance(meta.get("plan_sha256"), str)
    if not ok:
        raise CheckpointProblem("checkpoint-mismatch", "checkpoint.json does not match the checkpoint it belongs to")
    entries = []
    for f in meta["files"]:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str) or not isinstance(f.get("sha256"), str) or not _HEX64.match(f["sha256"]):
            raise CheckpointProblem("checkpoint-mismatch", "checkpoint.json lists a file that is not valid")
        path = f["path"]
        if not path.startswith(REVIEWED_DIR + "/") or ".." in Path(path).parts or "\\" in path:
            raise CheckpointProblem("checkpoint-path-refused", "checkpoint.json lists a file outside renderings/reviewed/, so nothing is committed or read from it")
        entries.append((path, f["sha256"]))
    if checkpoint_id_of(entries + [("descriptor.json", meta["descriptor_sha256"])]) != checkpoint_id:
        raise CheckpointProblem("checkpoint-mismatch", "the files listed in checkpoint.json do not add up to its id")
    return meta, entries


def _checkpoint_working_files(ws, checkpoint_id):
    """(meta, {path: digest} including the descriptor, [(path, bytes)] of every file to commit) read from the
    working tree and verified, or a problem."""
    folder = f"{CHECKPOINT_DIR}/{checkpoint_id}"
    if not _HEX64.match(checkpoint_id or ""):
        raise CheckpointProblem("checkpoint-invalid", "a checkpoint id is 64 lowercase hex digits")
    raw = _read_regular(Path(ws) / folder / "checkpoint.json", MAX_RECORD_BYTES)
    if raw is None:
        raise CheckpointProblem("checkpoint-missing", "that checkpoint was not prepared in this workspace. Prepare it first")
    meta, entries = _load_checkpoint_meta(raw, checkpoint_id)
    out = []
    for path, digest in entries + [(f"{folder}/descriptor.json", meta["descriptor_sha256"])]:
        if not path.startswith(CHECKPOINT_PREFIXES) or _path_has_link(ws, path):
            raise CheckpointProblem("checkpoint-path-refused", f"workspace:{path} is not a place a checkpoint may read or write")
        data = _read_regular(Path(ws) / path)
        if data is None:
            raise CheckpointProblem("checkpoint-mismatch", f"{path.rsplit('/', 1)[-1]} of the prepared checkpoint is missing. Prepare the checkpoint again")
        if _sha256_bytes(data) != digest:
            raise CheckpointProblem("checkpoint-mismatch", f"{path.rsplit('/', 1)[-1]} changed after the checkpoint was prepared. Prepare the checkpoint again")
        out.append((path, data))
    out.append((f"{folder}/checkpoint.json", raw))
    return meta, out


# -- the record in workspace.yaml ------------------------------------------------------------------

def _yaml_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return yaml_text(value)


def checkpoints_yaml_text(records):
    """The `checkpoints:` block of workspace.yaml for a list of records, in the block layout carrydown_lib reads."""
    if not records:
        return "checkpoints: []\n"
    lines = ["checkpoints:"]
    for r in records:
        lines.append(f"  - id: {_yaml_scalar(r['id'])}")
        for key in ("commit", "created"):
            lines.append(f"    {key}: {_yaml_scalar(r[key])}")
        lines.append("    sources:")
        for s in r["sources"]:
            lines.append(f"      - id: {_yaml_scalar(s['id'])}")
            lines.append(f"        version: {_yaml_scalar(s['version'])}")
            lines.append(f"        sha256: {_yaml_scalar(s['sha256'])}")
        for key in ("plan_sha256", "release_id", "request_id"):
            lines.append(f"    {key}: {_yaml_scalar(r.get(key))}")
        history = r.get("history") or []
        if not history:
            lines.append("    history: []")
        else:
            lines.append("    history:")
            for h in history:
                lines.append(f"      - release_id: {_yaml_scalar(h.get('release_id'))}")
                lines.append(f"        request_id: {_yaml_scalar(h.get('request_id'))}")
                lines.append(f"        replaced: {_yaml_scalar(h.get('replaced'))}")
    return "\n".join(lines) + "\n"


def _without_checkpoints(text):
    """workspace.yaml text without its top-level checkpoints block."""
    out, skipping = [], False
    for line in text.split("\n"):
        if re.match(r"checkpoints:", line):
            skipping = True
            continue
        if skipping and (line.strip() == "" or line[:1] in (" ", "\t", "-")):
            continue
        skipping = False
        out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


def checkpoint_records(workspace):
    """The checkpoint records of workspace.yaml, oldest first, as a list of dicts. An empty list when there are none."""
    data = read_workspace_yaml(workspace)
    if data is None:
        raise CheckpointProblem("checkpoint-mismatch", "workspace.yaml is missing or unreadable. Run workspace.py doctor")
    records = data.get("checkpoints")
    if records is None:
        return []
    if not isinstance(records, list):
        raise CheckpointProblem("checkpoint-mismatch", "the checkpoints list in workspace.yaml is not valid. Run workspace.py doctor")
    out = []
    for r in records:
        ok = isinstance(r, dict) and isinstance(r.get("id"), str) and _HEX64.match(r["id"]) and isinstance(r.get("commit"), str) \
            and _GIT_ID.match(r["commit"]) and isinstance(r.get("sources"), list) and \
            all(isinstance(s, dict) and isinstance(s.get("id"), str) and isinstance(s.get("sha256"), str) for s in r["sources"])
        if not ok:
            raise CheckpointProblem("checkpoint-mismatch", "a checkpoint record in workspace.yaml is not valid. Run workspace.py doctor")
        r = dict(r)
        if not isinstance(r.get("history"), list):
            r["history"] = []
        out.append(r)
    return out


def _store_records(workspace, records, root=None):
    path = Path(workspace) / "workspace.yaml"
    old = L.read_text(path) if path.is_file() else ""
    new = _without_checkpoints(old) + checkpoints_yaml_text(records)
    data = new.encode("utf-8")
    _gate_candidate(root, "workspace.yaml", data, True)
    _write_private(path, data)
    back = checkpoint_records(workspace)
    if [r["id"] for r in back] != [r["id"] for r in records]:
        raise CheckpointProblem("checkpoint-mismatch", "the checkpoint record could not be read back from workspace.yaml")


def _find_record(workspace, checkpoint_id):
    for r in checkpoint_records(workspace):
        if r["id"] == checkpoint_id:
            return r
    raise CheckpointProblem("checkpoint-missing", "no checkpoint with that id is recorded in this workspace")


def latest_checkpoint(workspace):
    """The newest recorded checkpoint as a dict (id, commit, created, sources, plan_sha256, release_id,
    request_id, history), or None when there is none. This reads the record only. checkpoint_read verifies
    it against git. A caller that gets None says CHECKPOINT_UNAVAILABLE."""
    records = checkpoint_records(workspace)
    return records[-1] if records else None


def checkpoint_for_sources(workspace, source_ids):
    """The newest recorded checkpoint that holds every one of source_ids, or None."""
    wanted = set(source_ids)
    for r in reversed(checkpoint_records(workspace)):
        if wanted <= {s["id"] for s in r["sources"]}:
            return r
    return None


def recorded_digests(workspace):
    """Every digest inside a recorded checkpoint: the rendering digests in workspace.yaml and, read from git,
    the digest of each file of each checkpoint. A checkpoint that cannot be read from git still contributes
    the digests in its record. Returns a set. Used before a rendering is replaced."""
    return set(recorded_digest_checkpoints(workspace))


def recorded_digest_checkpoints(workspace):
    """{digest: checkpoint id} for every digest recorded_digests finds. A digest in several checkpoints names the
    newest one. The renderer names that checkpoint when it does not copy a rendering a checkpoint already holds."""
    out = {}
    try:
        records = checkpoint_records(workspace)
    except CheckpointProblem:
        return out
    for r in records:
        found = {s["sha256"] for s in r["sources"]}
        try:
            run = _git(workspace, "show", f"{r['commit']}:{CHECKPOINT_DIR}/{r['id']}/checkpoint.json")
            if run.returncode == 0:
                meta = json.loads(run.stdout.decode("utf-8"))
                found |= {f["sha256"] for f in meta.get("files", []) if isinstance(f, dict) and isinstance(f.get("sha256"), str)}
        except (CheckpointProblem, ValueError, UnicodeDecodeError):
            pass
        for digest in found:
            out[digest] = r["id"]
    return out


# -- commit, read back, bind -----------------------------------------------------------------------

def _ls_tree(ws, commit):
    """{path: (mode, type, object id)} of a commit's whole tree."""
    run = _git(ws, "ls-tree", "-r", "-z", "--full-tree", commit)
    if run.returncode != 0:
        raise CheckpointProblem("checkpoint-missing", "the commit of that checkpoint is no longer in the private workspace's git repository. "
                              "Review the current sources to establish a new checkpoint")
    tree = {}
    for item in run.stdout.split(b"\x00"):
        if not item:
            continue
        head, _, path = item.partition(b"\t")
        parts = head.decode("ascii", "replace").split()
        if len(parts) != 3:
            raise CheckpointProblem("checkpoint-mismatch", "the commit of that checkpoint could not be read")
        tree[path.decode("utf-8", "replace")] = (parts[0], parts[1], parts[2])
    return tree


def _blobs(ws, oids):
    """{object id: bytes} for the blobs in oids, read with one git call."""
    wanted = sorted(set(oids))
    if not wanted:
        return {}
    run = _git(ws, "cat-file", "--batch", data=("\n".join(wanted) + "\n").encode("ascii"))
    if run.returncode != 0:
        raise CheckpointProblem("checkpoint-mismatch", "a file of that checkpoint could not be read from git")
    out, data, pos = {}, run.stdout, 0
    for oid in wanted:
        end = data.find(b"\n", pos)
        head = data[pos:end].split() if end != -1 else []
        if len(head) != 3 or head[1] != b"blob" or not head[2].isdigit():
            raise CheckpointProblem("checkpoint-mismatch", "a file of that checkpoint could not be read from git")
        size = int(head[2])
        out[head[0].decode("ascii")] = data[end + 1:end + 1 + size]
        pos = end + 1 + size + 1
    return out


def entries_paths(entries):
    return [p for p, _ in entries]


def checkpoint_read(workspace, checkpoint_id, check_working=False):
    """Read a recorded checkpoint back and verify it. The commit must still exist, its tree must hold exactly
    the files checkpoint.json lists with their recorded digests, the id must add up, and the record in
    workspace.yaml must agree with it. Returns a dict: id, commit, created, release_id, request_id, history,
    plan_sha256, descriptor (as recorded), sources, renderings ({"<source id>/<file name>": text}) and
    working_copy_differs (reviewed paths whose file in the workspace no longer matches). The texts come from
    git, never from the working files. A later checkpoint may replace a reviewed file, so a differing working
    copy is reported and is a problem only when check_working is true.
    Raises CheckpointProblem with code checkpoint-missing or checkpoint-mismatch."""
    ws = Path(workspace)
    record = _find_record(ws, checkpoint_id)
    commit = record["commit"]
    tree = _ls_tree(ws, commit)
    folder = f"{CHECKPOINT_DIR}/{checkpoint_id}"
    meta_entry = tree.get(f"{folder}/checkpoint.json")
    if meta_entry is None:
        raise CheckpointProblem("checkpoint-mismatch", "the commit does not hold checkpoint.json for that checkpoint")
    blobs = _blobs(ws, [entry[2] for entry in tree.values()])
    meta, entries = _load_checkpoint_meta(blobs.get(meta_entry[2], b""), checkpoint_id)
    expected = dict(entries)
    expected[f"{folder}/descriptor.json"] = meta["descriptor_sha256"]
    if set(tree) != set(expected) | {f"{folder}/checkpoint.json"}:
        raise CheckpointProblem("checkpoint-mismatch", "the commit holds files that are not the checkpoint's files, or lacks some of them")
    texts = {}
    for path, digest in expected.items():
        mode, kind, oid = tree[path]
        data = blobs.get(oid)
        if kind != "blob" or data is None or _sha256_bytes(data) != digest:
            raise CheckpointProblem("checkpoint-mismatch", f"{path.rsplit('/', 1)[-1]} in the commit does not match its recorded digest")
        texts[path] = data
    recorded = [(s["id"], s.get("version"), s["sha256"]) for s in record["sources"]]
    from_meta = [(s.get("id"), s.get("version"), s.get("sha256")) for s in meta["sources"]]
    if [(a, str(b), c) for a, b, c in recorded] != [(a, str(b), c) for a, b, c in from_meta] or record.get("plan_sha256") != meta["plan_sha256"]:
        raise CheckpointProblem("checkpoint-mismatch", "the record in workspace.yaml does not agree with the checkpoint in git")
    try:
        descriptor = json.loads(texts[f"{folder}/descriptor.json"].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise CheckpointProblem("checkpoint-mismatch", "the descriptor of that checkpoint is not valid")
    differs = sorted(p for p in entries_paths(entries) if _read_regular(ws / p) != texts[p])
    if check_working and differs:
        raise CheckpointProblem("checkpoint-mismatch", f"{len(differs)} reviewed file(s) in the workspace changed after the checkpoint was committed")
    renderings = {p[len(REVIEWED_DIR) + 1:]: texts[p].decode("utf-8") for p in entries_paths(entries)}
    return {"id": checkpoint_id, "commit": commit, "created": record.get("created"), "release_id": record.get("release_id"),
            "request_id": record.get("request_id"), "history": record["history"], "plan_sha256": meta["plan_sha256"],
            "descriptor": descriptor, "sources": meta["sources"], "renderings": renderings, "working_copy_differs": differs}


def checkpoint_verify(workspace, checkpoint_id, check_working=False):
    """None when the checkpoint reads back and verifies, else the problem code (checkpoint-missing or checkpoint-mismatch)."""
    try:
        checkpoint_read(workspace, checkpoint_id, check_working)
    except CheckpointProblem as e:
        return e.code
    return None


def checkpoint_commit(workspace, checkpoint_id, apply=False, root=None):
    """Commit a prepared checkpoint in the workspace's git repository, read it back, and only then record it
    in workspace.yaml (specification 6.1). Exactly the checkpoint's files are committed, through an isolated
    index inside the workspace's .git, on the ref refs/carrydown/checkpoints, so the normal index, the
    current branch and people.yaml, sources/, retention.yaml and every other file are never touched.
    Refused: staged changes in the normal index, a file outside renderings/reviewed/ or drafts/checkpoints/,
    and a missing git name or email (no author is ever invented). Returns a dict: id, apply, status
    (would-commit, committed or already-recorded), files, commit. Dry run without apply."""
    ws = Path(workspace)
    meta, files = _checkpoint_working_files(ws, checkpoint_id)
    for path, _ in files:
        if not path.startswith(CHECKPOINT_PREFIXES):
            raise CheckpointProblem("checkpoint-path-refused", f"workspace:{path} is not a place a checkpoint may commit from")
    staged = _staged_count(ws)
    if staged:
        raise CheckpointProblem("checkpoint-staged-changes",
                                f"The private workspace's git index already has {staged} staged change(s) that are not part of this checkpoint. "
                                "Nothing was committed. Commit or unstage them yourself, then run this again")
    why = _identity_problem(ws)
    if why:
        raise CheckpointProblem("checkpoint-identity-missing", why)
    listed = [p for p, _ in files]
    existing = [r for r in checkpoint_records(ws) if r["id"] == checkpoint_id]
    if existing and checkpoint_verify(ws, checkpoint_id) is None:
        return {"id": checkpoint_id, "apply": bool(apply), "status": "already-recorded", "files": listed, "commit": existing[0]["commit"]}
    if not apply:
        return {"id": checkpoint_id, "apply": False, "status": "would-commit", "files": listed, "commit": None}
    gitdir = ws / ".git"
    if not gitdir.is_dir():
        gitdir = Path(_git_ok(ws, "rev-parse", "--absolute-git-dir").decode("utf-8").strip())
    index = gitdir / f"carrydown-checkpoint-{os.getpid()}-{os.urandom(4).hex()}.index"
    env = {"GIT_INDEX_FILE": str(index)}
    try:
        for path, data in files:
            if _read_regular(ws / path) != data:
                raise CheckpointProblem("checkpoint-mismatch", f"{path.rsplit('/', 1)[-1]} changed while the checkpoint was being committed. Nothing was recorded")
        # write each file's bytes as an object, then put exactly those paths in the empty isolated index
        oids = _git_ok(ws, "hash-object", "-w", "--no-filters", "--stdin-paths", env=env,
                       data=("\n".join(str(ws / path) for path, _ in files) + "\n").encode("utf-8")).decode("ascii").split()
        if len(oids) != len(files):
            raise CheckpointProblem("checkpoint-git-failed", "git did not store every file of the checkpoint. Nothing was recorded")
        _git_ok(ws, "update-index", "--add", "--index-info", env=env,
                data="".join(f"100644 {oid}\t{path}\n" for oid, (path, _) in zip(oids, files)).encode("utf-8"))
        tree = _git_ok(ws, "write-tree", env=env).decode("ascii").strip()
        parent_run = _git(ws, "rev-parse", "--verify", "-q", f"{CHECKPOINT_REF}^{{commit}}")
        parent = parent_run.stdout.decode("ascii").strip() if parent_run.returncode == 0 else ""
        args = ["commit-tree", tree, "-m", f"Record reviewed source checkpoint {checkpoint_id[:12]}"]
        if parent:
            args[2:2] = ["-p", parent]
        commit = _git_ok(ws, *args).decode("ascii").strip()
        # read it back before anything points at it or records it
        tree_back = _ls_tree(ws, commit)
        want = {p: _sha256_bytes(d) for p, d in files}
        if set(tree_back) != set(want):
            raise CheckpointProblem("checkpoint-mismatch", "the commit does not hold exactly the checkpoint's files. Nothing was recorded")
        back = _blobs(ws, [entry[2] for entry in tree_back.values()])
        for path, digest in want.items():
            data = back.get(tree_back[path][2])
            if tree_back[path][0] != "100644" or data is None or _sha256_bytes(data) != digest:
                raise CheckpointProblem("checkpoint-mismatch", f"{path.rsplit('/', 1)[-1]} in the commit does not match its digest. Nothing was recorded")
        _git_ok(ws, "update-ref", "-m", f"carrydown checkpoint {checkpoint_id[:12]}", CHECKPOINT_REF, commit, parent)
    finally:
        try:
            index.unlink()
        except OSError:
            pass
    record = {"id": checkpoint_id, "commit": commit, "created": _now(), "sources": [dict(s) for s in meta["sources"]],
              "plan_sha256": meta["plan_sha256"], "release_id": None, "request_id": None, "history": []}
    others = [r for r in checkpoint_records(ws) if r["id"] != checkpoint_id]
    if existing:
        record.update(release_id=existing[0].get("release_id"), request_id=existing[0].get("request_id"),
                      history=list(existing[0].get("history") or []))
    _store_records(ws, others + [record], root)
    return {"id": checkpoint_id, "apply": True, "status": "committed", "files": listed, "commit": commit}


def checkpoint_bind(workspace, checkpoint_id, release_id, request_id, apply=False, root=None, when=None):
    """Record that a checkpoint belongs to an existing release and approval request (specification 6.2).
    Local bookkeeping only: it approves nothing and publishes nothing. An earlier association is kept in the
    record's history list (appended, never overwritten). Binding the same pair again changes nothing.
    Returns a dict: id, apply, status (would-bind, bound or unchanged), release_id, request_id, history."""
    for label, value in (("release id", release_id), ("request id", request_id)):
        if not isinstance(value, str) or not _LABEL_ID.match(value):
            raise CheckpointProblem("checkpoint-invalid", f"the {label} must be a short identifier")
    records = checkpoint_records(workspace)
    record = next((r for r in records if r["id"] == checkpoint_id), None)
    if record is None:
        raise CheckpointProblem("checkpoint-missing", "no checkpoint with that id is recorded in this workspace")
    problem = checkpoint_verify(workspace, checkpoint_id)
    if problem:
        raise CheckpointProblem(problem, "that checkpoint no longer verifies against git, so it is not bound. Run workspace.py doctor")
    history = list(record["history"])
    if record.get("release_id") == release_id and record.get("request_id") == request_id:
        return {"id": checkpoint_id, "apply": bool(apply), "status": "unchanged", "release_id": release_id, "request_id": request_id, "history": history}
    if record.get("release_id") is not None or record.get("request_id") is not None:
        history.append({"release_id": record.get("release_id"), "request_id": record.get("request_id"), "replaced": when or _now()})
    result = {"id": checkpoint_id, "apply": bool(apply), "status": "bound" if apply else "would-bind", "release_id": release_id,
              "request_id": request_id, "history": history}
    if apply:
        updated = dict(record, release_id=release_id, request_id=request_id, history=history)
        _store_records(workspace, [updated if r["id"] == checkpoint_id else r for r in records], root)
    return result


def checkpoint_summary(workspace):
    """(count, latest id or None, problem code or None, note). The latest checkpoint is read back from git and the
    problem is the code that read raised. The note says why the records could not be read. No source content,
    heading or path of an original is ever returned."""
    try:
        records = checkpoint_records(workspace)
    except CheckpointProblem as e:
        return 0, None, e.code, e.message
    if not records:
        return 0, None, None, ""
    latest = records[-1]["id"]
    return len(records), latest, checkpoint_verify(workspace, latest), ""


def _print_prepare(result):
    L.say(f"checkpoint {result['id']}" + ("" if result["apply"] else "  DRY RUN (nothing was written)"))
    for f in result["files"]:
        L.say(f"  {'would write' if not result['apply'] and f['action'] == 'write' else 'wrote' if f['action'] == 'write' else 'unchanged'} workspace:{f['path']}")
    if not result["apply"]:
        L.say("Add --apply to write these files. Then commit the checkpoint with: workspace.py checkpoint commit --id " + result["id"] + " --apply")


def _checkpoint_workspace(a):
    root = L.project_root(a.root)
    ws, why = L.workspace_root(root)
    if ws is None:
        L.die(f"{why}: no private workspace is usable for this project. Create it with workspace.py init, then run this again")
    return root, ws


def cmd_checkpoint(a):
    root, ws = _checkpoint_workspace(a)
    try:
        if a.action == "prepare":
            try:
                raw = L.read_text(a.descriptor)
                descriptor = json.loads(raw) if raw.lstrip().startswith("{") else L.loads(raw)
            except (ValueError, L.YamlError) as e:
                L.die(f"--descriptor cannot be read: {str(e)[:100]}")
            files = [Path(p) for p in (a.rendering or [])]
            if a.rendering_dir:
                base = Path(a.rendering_dir)
                sources = descriptor.get("sources") if isinstance(descriptor, dict) else None
                for s in sources if isinstance(sources, list) else []:
                    stem = s.get("rendering", s.get("id")) if isinstance(s, dict) else None
                    if isinstance(stem, str):
                        for suffix in (".md", ".index.txt"):
                            if (base / (stem + suffix)).is_file():
                                files.append((s["id"], base / (stem + suffix)))
            _print_prepare(checkpoint_prepare(root, ws, files, descriptor, apply=a.apply))
        elif a.action == "commit":
            result = checkpoint_commit(ws, a.id, apply=a.apply, root=root)
            if result["status"] == "already-recorded":
                L.say(f"checkpoint {a.id} is already committed and verified")
            elif result["status"] == "would-commit":
                L.say(f"checkpoint {a.id}  DRY RUN (nothing was committed)")
                L.say(f"would commit {len(result['files'])} file(s) from renderings/reviewed/ and drafts/checkpoints/ through an isolated index, then read the commit back and record it in workspace.yaml")
                L.say("Add --apply to commit.")
            else:
                L.say(f"checkpoint {a.id} committed and read back. Recorded in workspace.yaml")
        elif a.action == "bind":
            result = checkpoint_bind(ws, a.id, a.release_id, a.request_id, apply=a.apply, root=root)
            if result["status"] == "unchanged":
                L.say(f"checkpoint {a.id} is already bound to that release and request")
            elif result["status"] == "would-bind":
                L.say(f"checkpoint {a.id}  DRY RUN: would record the release and request in workspace.yaml (local bookkeeping, not an approval)")
                L.say("Add --apply to record it.")
            else:
                L.say(f"checkpoint {a.id} bound to the release and request in workspace.yaml (local bookkeeping, not an approval). "
                      f"Earlier associations kept: {len(result['history'])}")
        else:
            count, latest, problem, note = checkpoint_summary(ws)
            L.say(f"source checkpoints: {count}")
            if latest:
                L.say(f"latest checkpoint: {latest} ({'commit verifies' if problem is None else 'commit does NOT verify: ' + problem})")
            elif problem:
                L.say(f"checkpoint records: {problem} ({note})")
            else:
                L.say("latest checkpoint: none. " + CHECKPOINT_UNAVAILABLE)
            return 1 if problem else 0
    except CheckpointProblem as e:
        L.die(f"{e.code}: {e.message}", 1 if e.code in ("checkpoint-mismatch", "checkpoint-missing") else 2)
    return 0


# ---------------------------------------------------------------------------
# status and doctor
# ---------------------------------------------------------------------------

def read_workspace_yaml(ws):
    path = Path(ws) / "workspace.yaml"
    if not path.is_file():
        return None
    try:
        data = L.load_file(path)
    except (L.YamlError, L.TextError):
        return None
    return data if isinstance(data, dict) else None


def count_people(ws):
    """(people, advisors) in people.yaml, or None when it is missing or unreadable. Counts only."""
    path = Path(ws) / "people.yaml"
    if not path.is_file():
        return None
    try:
        doc, _ = L.load_people_file(path)
    except L.PlanError:
        return None
    return len(doc["people"]), len(doc["advisors"])


def cmd_status(a):
    root = L.project_root(a.root)
    ws, why = L.workspace_root(root)
    L.say("carrydown workspace status")
    L.say(f"engineering repository: {root}")
    if ws is None:
        L.say(f"workspace: unavailable ({why})")
        L.say(f"Create it: python3 {Path(__file__).resolve()} init --root . --slug <slug> --apply")
        return 1
    L.say(f"workspace: {ws}")
    data = read_workspace_yaml(ws)
    L.say(f"state: {data.get('state', 'unknown') if data else 'workspace.yaml is missing or unreadable'}")
    bad = permission_problem(ws)
    L.say("permissions: " + ("owner only" if bad is None else f"NOT owner only ({bad})"))
    counts = count_people(ws)
    L.say("people.yaml: " + (f"{counts[0]} people, {counts[1]} advisors" if counts else "missing or unreadable"))
    if data and data.get("staging_repository"):
        L.say(f"staging repository: {data['staging_repository']} (named here; not checked offline)")
    done = {sub: sum(1 for _ in (ws / sub).iterdir()) if (ws / sub).is_dir() else 0 for sub in ("releases", "requests", "events")}
    L.say(f"releases: {done['releases']}, requests: {done['requests']}, events: {done['events']}")
    count, latest, problem, note = checkpoint_summary(ws)
    L.say(f"source checkpoints: {count}")
    if latest:
        L.say(f"latest checkpoint: {latest} (" + ("commit verifies" if problem is None else f"commit does NOT verify: {problem}") + ")")
    elif problem:
        L.say(f"latest checkpoint: unreadable ({problem})")
    return 0 if bad is None and data else 1


def git_output(root, *args):
    try:
        run = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return run


def doctor_rows(root):
    """The offline checks as (level, name, detail). level is ok, warn or FAIL. Details name ids,
    counts and fixed codes, never the content of a file."""
    rows = []

    def add(level, name, detail):
        rows.append((level, name, detail))

    ws, why = L.workspace_root(root)
    if ws is None:
        add("FAIL", "pointer", f"{POINTER} does not lead to a workspace ({why})")
        if why == "workspace-inside-repository":
            add("FAIL", "path separation", "the workspace is inside the engineering repository, where every reader could see it")
    else:
        add("ok", "pointer", f"{POINTER} leads to {ws}")
        add("ok", "path separation", "the workspace is outside the engineering repository")
        bad = permission_problem(ws)
        add("FAIL" if bad else "ok", "permissions", bad or ("owner only (mode 0700)" if os.name != "nt" else "access control list names the current user only"))
        data = read_workspace_yaml(ws)
        if data is None:
            add("FAIL", "workspace.yaml", "missing or unreadable")
        elif type(data.get("format")) is not int or data.get("format") != WORKSPACE_FORMAT:
            add("FAIL", "workspace.yaml", f"format {data.get('format')!r} is not {WORKSPACE_FORMAT}")
        else:
            repo = data.get("engineering_repo")
            same = isinstance(repo, dict) and os.path.realpath(str(repo.get("path", ""))) == os.path.realpath(str(root))
            add("ok" if same else "warn", "workspace.yaml", "format 1" + ("" if same else ", and it names another engineering folder"))
        add("ok" if (ws / "retention.yaml").is_file() else "warn", "retention.yaml", "present" if (ws / "retention.yaml").is_file() else "missing")
        add("ok" if (ws / ".git").exists() else "warn", "git", "the workspace is a git repository" if (ws / ".git").exists() else "the workspace is not a git repository")
        if (ws / ".git").exists() and data is not None:
            count, latest, problem, note = checkpoint_summary(ws)
            if problem and latest is None:
                add("FAIL", "checkpoints", f"the checkpoint records cannot be read ({problem})")
            elif not count:
                add("ok", "checkpoints", "none recorded yet. A checkpoint is made when a source review is accepted")
            elif problem:
                add("FAIL", "checkpoints", f"{count} recorded. The latest ({latest[:12]}) does not verify ({problem}). Review the current sources to establish a new one")
            else:
                add("ok", "checkpoints", f"{count} recorded. The latest ({latest[:12]}) verifies against its commit")
        if (ws / "people.yaml").is_file():
            try:
                doc, problems = L.load_people_file(ws / "people.yaml")
                add("FAIL" if problems else "ok", "people.yaml", f"{len(doc['people'])} people, {len(doc['advisors'])} advisors" + (f", {len(problems)} problem(s). Run check_specs.py --report" if problems else ""))
            except L.PlanError as e:
                add("FAIL", "people.yaml", e.msg.split(":", 1)[-1].strip()[:80] if ":" in e.msg else "unreadable")
        else:
            add("warn", "people.yaml", "not created yet. The interview writes it after the workspace exists")
    ignore = root / ".gitignore"
    text = L.read_text(ignore) if ignore.is_file() else ""
    for entry in IGNORE_REQUIRED:
        add("ok" if gitignore_has(text, entry) else "FAIL", "ignore rule", f"{entry} " + ("is ignored" if gitignore_has(text, entry) else "is not in .gitignore. Run workspace.py init --apply, or add the line"))
    for entry in IGNORE_ADVISED:
        add("ok" if gitignore_has(text, entry) else "warn", "ignore rule", f"{entry} " + ("is ignored" if gitignore_has(text, entry) else "is not in .gitignore (the scaffold adds it)"))
    tracked = git_output(root, "ls-files", "--error-unmatch", "--", POINTER)
    if tracked is not None and tracked.returncode == 0:
        add("FAIL", "tracked pointer", f"{POINTER} is tracked by git. Run: git rm --cached {POINTER}")
    plan_path = L.find_plan(root, None)
    if L.exists(plan_path):
        try:
            plan, problems = L.load_plan(plan_path, root)
            kind = f"plan_format {plan.get('plan_format')}, {plan['_view']} view, handling {((plan['project'].get('handling') or {}).get('state') or 'none')}" if plan["_modern"] else "legacy layout (no project.handling)"
            add("FAIL" if problems else "ok", "plan schema", f"{kind}; " + (f"{len(problems)} problem(s). Run check_specs.py to list them" if problems else "valid"))
        except L.PlanError:
            add("FAIL", "plan schema", "plan.yaml cannot be read. Run check_specs.py")
    else:
        add("warn", "plan schema", "no plan.yaml yet")
    if ws is not None and (ws / "drafts" / "plan.yaml").is_file():
        try:
            plan, problems = L.load_plan(ws / "drafts" / "plan.yaml", root)
            add("FAIL" if problems else "ok", "draft plan schema", f"{len(problems)} problem(s)" if problems else "valid")
        except L.PlanError:
            add("FAIL", "draft plan schema", "drafts/plan.yaml cannot be read")
    return rows


# The components that live on GitHub and in the tooling repository. The offline doctor cannot read them
# and says so; release.py doctor reads them with the owner's token (release_verify.EXPORT_COMPONENTS).
REMOTE_COMPONENTS = ("enrollment", "staging-identity", "staging-readers", "staging-workflow", "staging-ruleset", "verifier-code",
                     "engineering-ruleset", "approvers", "scan-health", "runtime-isolation", "destinations")


def remote_rows(root):
    """(level, name, detail) for the remote components. The level is info: an offline check never turns
    a fact it cannot read into a pass or a failure. A project that names no staging or tooling repository
    and has no policy pointer is on the "yes" path, where none of them applies."""
    ws, _ = L.workspace_root(root)
    data = read_workspace_yaml(ws) if ws is not None else None
    named = bool(data and (data.get("staging_repository") or data.get("tooling_repository")))
    pointer = (Path(root) / ".carrydown" / "release-policy.yaml").is_file()
    if not (named or pointer):
        return [("info", "remote components", "none apply. The \"yes\" path needs no staging repository, verifier or enrollment")]
    return [("info", name, "not verifiable offline. Run release.py doctor with your token to check it live") for name in REMOTE_COMPONENTS]


def cmd_doctor(a):
    root = L.project_root(a.root)
    rows = doctor_rows(root)
    remote = remote_rows(root)
    L.say("carrydown workspace doctor (offline: nothing is sent, nothing is changed)")
    width = max(len(r[1]) for r in rows)
    for level, name, detail in rows:
        L.say(f"  {level:<4}  {name.ljust(width)}  {detail}")
    wide = max(len(r[1]) for r in remote)
    for level, name, detail in remote:
        L.say(f"  {level:<4}  {name.ljust(wide)}  {detail}")
    failed = sum(1 for r in rows if r[0] == "FAIL")
    warned = sum(1 for r in rows if r[0] == "warn")
    L.say(f"{len(rows) - failed - warned} ok, {warned} warning(s), {failed} failure(s)")
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Windows: the folder is %USERPROFILE%\\.carrydown\\workspaces\\<slug>\\ and its access control list is set with "
               "icacls <folder> /inheritance:r /grant:r \"<DOMAIN\\user>:(OI)(CI)F\", then read back with icacls <folder>. "
               "Exit status 0 when fine, 1 when a check fails, 2 for a wrong argument or a refused path.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, text in (("init", "create the workspace and the pointer (dry run unless --apply)"),
                       ("status", "print the workspace path, state and counts, never names"),
                       ("doctor", "check permissions, path separation, ignore rules and the plan schema, offline")):
        p = sub.add_parser(name, help=text, description=text)
        p.add_argument("--root", default=".", help="the engineering repository (default: current directory)")
        if name == "init":
            p.add_argument("--slug", help="short name of the project, lowercase words joined by hyphens (default: the plan's slug, else the folder name)")
            p.add_argument("--workspace", help="a folder for the workspace instead of ~/.carrydown/workspaces/<slug>. It must be outside the engineering repository")
            p.add_argument("--answer", choices=("yes", "no"),
                           help=f"your answer to: {ANSWER_QUESTION} On no, the staging repository commands are printed (default: from plan.yaml, else yes)")
            p.add_argument("--staging-repository", metavar="OWNER/NAME", help="name of the private staging repository on the no answer (default: <owner>/<slug>-releases)")
            p.add_argument("--retain", choices=("keep", "delete-after-release"), help="whether raw inputs are kept after release (default: from plan.yaml, else keep)")
            p.add_argument("--apply", action="store_true", help="create the workspace. Without it nothing is written")
    ck = sub.add_parser("checkpoint", help="maintainers: prepare, commit, bind or list reviewed source checkpoints (dry run unless --apply)",
                        description="Reviewed source checkpoints in the private workspace's git repository. For maintainers and agents. "
                                    "prepare copies the reviewed renderings and writes the descriptor, commit commits exactly those files "
                                    "through an isolated index and records the commit after reading it back, bind records the release and "
                                    "request a checkpoint belongs to, list shows the count and whether the latest commit verifies. "
                                    "Every command that writes is a dry run without --apply. Nothing is pushed.")
    cks = ck.add_subparsers(dest="action", required=True)
    for action, text in (("prepare", "copy the reviewed renderings and write the descriptor and checkpoint.json"),
                         ("commit", "commit a prepared checkpoint, read it back, then record it in workspace.yaml"),
                         ("bind", "record the release and request a checkpoint belongs to (local bookkeeping, not an approval)"),
                         ("list", "print the checkpoint count and whether the latest commit verifies")):
        p = cks.add_parser(action, help=text, description=text)
        p.add_argument("--root", default=".", help="the engineering repository (default: current directory)")
        if action == "prepare":
            p.add_argument("--descriptor", required=True, metavar="FILE", help="JSON or YAML file: plan_sha256 and sources (id, version, digests, precedence, applicability, classification, extraction_limits)")
            p.add_argument("--rendering", action="append", metavar="FILE", help="a rendering (.md or .index.txt) of a source. Repeat for each file. Matched to a source by its name")
            p.add_argument("--rendering-dir", metavar="DIR", help="a folder holding <name>.md and <name>.index.txt for each source in the descriptor")
        if action in ("commit", "bind"):
            p.add_argument("--id", required=True, help="the checkpoint id printed by prepare")
        if action == "bind":
            p.add_argument("--release-id", required=True, help="the id of an existing release")
            p.add_argument("--request-id", required=True, help="the id of the approval request of that release")
        if action != "list":
            p.add_argument("--apply", action="store_true", help="write. Without it nothing is written")
    a = ap.parse_args(argv)
    return {"init": cmd_init, "status": cmd_status, "doctor": cmd_doctor, "checkpoint": cmd_checkpoint}[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
