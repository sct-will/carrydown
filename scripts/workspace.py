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

--answer is your answer to the one question of the interview: "Can everyone who can read this
repository see all of these documents and your staffing notes?" On no, init prints the commands
that create the private staging repository. It does not run them.

Permissions. On macOS, Linux and other POSIX systems the folder is created with mode 0o700 (owner
only) and the mode is read back; if it is not 0o700, or the folder is not yours, init stops. On
Windows the workspace is %USERPROFILE%\\.carrydown\\workspaces\\<slug>\\ and init applies an access
control list that names the current user only, with
  icacls <folder> /inheritance:r /grant:r "<DOMAIN\\user>:(OI)(CI)F"
then reads it back with `icacls <folder>`. Any other principal in the list stops init. The folder is
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carrydown_lib as L  # noqa: E402
import release_gate as RG  # noqa: E402

WORKSPACE_FORMAT = 1
POINTER = ".carrydown/local.yaml"
ANSWER_QUESTION = "Can everyone who can read this repository see all of these documents and your staffing notes?"
SUBFOLDERS = ("sources", "renderings", "drafts", "releases", "requests", "events", "publication")
RETENTION_LIMITS = ("Deleting files from this workspace does not remove them from any backup, remote or copy made earlier. "
                    "Carrydown records what it deleted and when.")
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
    """A remote URL with any user name or password removed, so a token in it is never kept or shown."""
    return re.sub(r"^([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]*@", r"\1", url.strip())


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


def windows_acl_problem(principals, user):
    """Why an access control list is not current-user-only, or None. principals is parse_icacls output,
    user is DOMAIN\\name (or just the name)."""
    if not principals:
        return "the access control list could not be read back"
    wanted = {user.casefold(), user.casefold().split("\\")[-1]}
    others = sorted({p for p in principals if p.casefold() not in wanted and p.casefold().split("\\")[-1] not in wanted})
    if others:
        return f"{len(others)} other principal(s) can open the workspace. Only the current user may"
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


def workspace_yaml_text(slug, root, remote, staging):
    lines = [f"format: {WORKSPACE_FORMAT}", f"slug: {slug}", "engineering_repo:",
             f"  path: {yaml_text(Path(root).as_posix())}", f"  remote: {yaml_text(remote)}"]
    if staging:
        lines.append(f"staging_repository: {staging}")
    lines += ["policy_version: 1", "state: drafting"]
    return "\n".join(lines) + "\n"


def retention_yaml_text(raw_inputs):
    return f"raw_inputs: {raw_inputs}\nhistory: keep\nlimits: {yaml_text(RETENTION_LIMITS)}\n"


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
        L.write_text(ws / "workspace.yaml", workspace_yaml_text(slug, root, remote, staging))
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
        elif data.get("format") != WORKSPACE_FORMAT:
            add("FAIL", "workspace.yaml", f"format {data.get('format')!r} is not {WORKSPACE_FORMAT}")
        else:
            repo = data.get("engineering_repo")
            same = isinstance(repo, dict) and os.path.realpath(str(repo.get("path", ""))) == os.path.realpath(str(root))
            add("ok" if same else "warn", "workspace.yaml", "format 1" + ("" if same else ", and it names another engineering folder"))
        add("ok" if (ws / "retention.yaml").is_file() else "warn", "retention.yaml", "present" if (ws / "retention.yaml").is_file() else "missing")
        add("ok" if (ws / ".git").exists() else "warn", "git", "the workspace is a git repository" if (ws / ".git").exists() else "the workspace is not a git repository")
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
    a = ap.parse_args(argv)
    return {"init": cmd_init, "status": cmd_status, "doctor": cmd_doctor}[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
