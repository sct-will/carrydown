#!/usr/bin/env python3
"""The runner for the acceptance run on real GitHub. Standard library only.

docs/organization-setup.md ends with a runbook, "Acceptance on real GitHub", and an empty record table.
This program turns that runbook, and the organization setup above it, into 17 steps that the plan owner runs
once against a throwaway GitHub organization. It does the steps that a program can do, stops for the steps
that need a person, checks the result of every step against GitHub, and appends one record per step to a
file. The records fill the table.

  python3 tests/acceptance/live_github_run.py doctor --org NAME
  python3 tests/acceptance/live_github_run.py plan
  python3 tests/acceptance/live_github_run.py run --org NAME --throwaway --record run.jsonl --apply
  python3 tests/acceptance/live_github_run.py render --record run.jsonl

Commands
  plan     The default. Prints the 17 steps, which are automatic and which need a person, and the inputs.
           It needs no gh and touches nothing.
  doctor   The preconditions, as a table of verified and not verified. It never prints a token.
  run      Executes the steps in order. Without --apply it performs only reads and prints what each step would
           do. With --apply it writes to GitHub. It needs --throwaway, which says that the organization exists
           only for this run. It records nothing in a dry run.
  render   Prints the table of docs/organization-setup.md from the records, in the same rows and the same order. A row with
           no record stays "Not yet performed".

How it touches GitHub
  Only through the gh command line tool, called with an argument array (never a shell string), and through the
  repository's own scripts (scripts/release.py, scripts/workspace.py, verifier/verify_release.py), which read
  the owner's token themselves. This program never reads, prints or logs a token. Every output of gh and of
  the scripts passes through a redaction filter before it is shown or stored. It never deletes a resource: a
  call that names a delete is refused before gh runs. It never forces a push.

The records
  One JSON object per line: {step, started, finished, state, evidence, sanitized}.
  state is one of
    done      the step created its result
    skipped   the result already existed, so the step created nothing
    human     a person did part of the step, and the program checked the result afterward
    failed    the step stopped. The reason code is in evidence.reason_codes. The next run retries it.
  evidence holds ids, URLs, logins of the fictional actors, settings values and reason codes. Never a token,
  never private text.
  A step with a record in state done, skipped or human is not repeated. --from STEP starts at that step.
  --to STEP stops after it. To repeat a finished step, remove its line from the record file yourself.

The program writes no file into the repository. Its working folder is next to the record file.
"""
import argparse
import base64
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CARRYDOWN = HERE.parent.parent

STAGING_CHECK = "carrydown-staging-verifier"
ENGINEERING_CHECK = "carrydown-release-verifier"
TOOLING_NAME = "carrydown-tooling"
ENGINEERING_NAME = "expense-approvals"
STAGING_NAME = "expense-approvals-releases"
VERIFY_WORKFLOW = "carrydown-release-verify.yml"
REQUEST_WORKFLOW = "open-release-request.yml"
RULESET_NAME = "carrydown release"
TOOLING_RULESET_NAME = "carrydown tooling"
ACTIONS_LOGIN = "github-actions[bot]"
PIN_MESSAGE = "Pin the carrydown verifier code"
ENROLL_MESSAGE = "Enroll expense-approvals"
APP_PERMISSIONS = {"contents": "read", "pull_requests": "read", "checks": "write", "metadata": "read"}
REDIRECT = "http://127.0.0.1:8765/"
HEALTH_SECONDS = 900
POLL_SECONDS = 180
POLL_INTERVAL = 15
CHECK_TIMEOUT = 900
ATTEST_DAYS = 30
WITHDRAW_REASON = "no-longer-needed"

# The gh scopes the run needs. Checked by doctor.
GH_SCOPES = ("repo", "workflow", "admin:org")
INSTALL_LINES = (
    "  macOS:    brew install gh",
    "  Windows:  winget install --id GitHub.cli",
    "  Linux:    sudo apt install gh   (Debian and Ubuntu; other systems: https://github.com/cli/cli#installation)",
    "  Then sign in:  gh auth login",
    "  Then add the scopes the run needs:  gh auth refresh -s repo,workflow,admin:org",
)

# ---------------------------------------------------------------------------
# The 17 steps. The text is what plan prints and what the record table is built from.
# ---------------------------------------------------------------------------

AUTO, HUMAN, MIXED, FALLBACK = "AUTOMATIC", "HUMAN", "AUTOMATIC + HUMAN", "AUTOMATIC (human only if refused)"

STEPS = [
    {"id": "S1", "runbook": "Organization setup, step 1", "mode": AUTO,
     "title": "Create the tooling repository and pin the verifier code",
     "does": "Creates the private repository carrydown-tooling. Commits scripts/, verifier/ and the verifier workflow from the carrydown "
             "checkout as one commit, which later becomes verifier_sha. The default branch is protected in step S5, after the last direct commit.",
     "human": ""},
    {"id": "S2", "runbook": "Organization setup, step 2", "mode": HUMAN,
     "title": "Create the verifier App through the manifest flow",
     "does": "Writes the App manifest and a local page that submits it. After you finish in the browser, checks the App, its permissions, "
             "its installation on the tooling repository and the secret names, then stores CARRYDOWN_APP_ID.",
     "human": "Open the page, create the App, pipe its private key into the tooling repository secret, install the App. The program "
              "prints the exact commands. It never sees the key."},
    {"id": "S3", "runbook": "Organization setup, step 3", "mode": FALLBACK,
     "title": "Create the engineering and staging repositories and their rules",
     "does": "Creates both private repositories, allows merge commits only on staging, commits the request workflow and the policy pointer, "
             "turns on Actions pull requests, adds the App to both repositories, and imports both rulesets printed by verify_release.py.",
     "human": "Only if GitHub refuses to add the App to a repository by API: add it in the browser."},
    {"id": "S4", "runbook": "Organization setup, step 4", "mode": AUTO,
     "title": "Enroll the project",
     "does": "Builds the enrollment entry, fills both digests with verify_release.py digests, commits enrollment.yaml after the verifier commit, "
             "and checks the policy pointer in the engineering repository.",
     "human": ""},
    {"id": "S5", "runbook": "Organization setup, step 5", "mode": HUMAN,
     "title": "Attest what the plan owner cannot inspect, then protect the tooling repository",
     "does": "Re-reads the facts it can read, writes the scoped attestations into enrollment.yaml, and creates the tooling ruleset.",
     "human": "As the organization administrator, read the facts printed and type vouch."},
    {"id": "S6", "runbook": "Organization setup, step 6", "mode": AUTO,
     "title": "Run the live doctor",
     "does": "Creates the local candidate project and its private workspace, waits for a complete verifier scan, runs release.py doctor "
             "and requires every mandatory component to be verified.",
     "human": ""},
    {"id": "S7", "runbook": "Organization setup, step 7", "mode": AUTO,
     "title": "Run the owner's preview and prepare",
     "does": "Runs release.py preview and prepare --apply on the fictional candidate. Records the release id and the request id.",
     "human": ""},
    {"id": "A1", "runbook": "Acceptance, step 1", "mode": AUTO,
     "title": "Run the live doctor on the finished installation",
     "does": "Runs the live doctor again, records every component status, and records the platform and plan of the organization.",
     "human": ""},
    {"id": "A2", "runbook": "Acceptance, step 2", "mode": AUTO,
     "title": "Upload the candidate and check who opened the request pull request",
     "does": "Runs release.py approve --github --apply, waits for the pull request, and confirms that the Actions identity, not the owner, "
             "opened it. Records the staging check on the unreviewed head.",
     "human": ""},
    {"id": "A3", "runbook": "Acceptance, step 3", "mode": HUMAN,
     "title": "Approve the final head, dismiss the approval by a push, approve again",
     "does": "Waits for your approval of the final head, pushes an empty commit to the request branch, confirms GitHub dismissed the "
             "approval as stale, and waits for your approval of the new head.",
     "human": "Approve the pull request as the owner, twice, in the browser."},
    {"id": "A4", "runbook": "Acceptance, step 4", "mode": AUTO,
     "title": "Confirm the last-push approval setting is off",
     "does": "Reads the staging ruleset and confirms that require_last_push_approval is false and that the owner, who pushed the branch, "
             "holds an approving review.",
     "human": ""},
    {"id": "A5", "runbook": "Acceptance, step 5", "mode": AUTO,
     "title": "Confirm the staging check fails before the review and passes after it",
     "does": "Reads the check runs of the verifier App on the first head and on the final head.",
     "human": ""},
    {"id": "A6", "runbook": "Acceptance, step 6", "mode": FALLBACK,
     "title": "Merge with a merge commit and confirm activation",
     "does": "Merges the pull request with a merge commit, confirms the merge has two parents, and confirms that release.py export accepts "
             "the request (a dry run).",
     "human": "Only if the merge is refused: click Create a merge commit."},
    {"id": "A7", "runbook": "Acceptance, step 7", "mode": MIXED,
     "title": "Export, open the engineering pull request, check, change one byte",
     "does": "Exports, publishes the branch through the API, opens the engineering pull request, waits for the engineering check, changes "
             "one byte of an exported file and expects the check to fail, then restores it.",
     "human": "Approve and merge the engineering pull request with a second account. GitHub does not let an author approve their own pull request."},
    {"id": "A8", "runbook": "Acceptance, step 8", "mode": MIXED,
     "title": "Prepare, approve and merge a replacement",
     "does": "Prepares a new request, uploads it, waits for your approval, merges it, exports it and confirms that the first request's "
             "receipt is regenerated as superseded in the same branch. Opens the engineering pull request and waits for its check.",
     "human": "Approve the staging pull request as the owner. Approve and merge the engineering pull request with the second account."},
    {"id": "A9", "runbook": "Acceptance, step 9", "mode": MIXED,
     "title": "Withdraw the active request",
     "does": "Runs release.py withdraw, waits for your approval, merges the state change, exports the receipt-only branch, opens its "
             "pull request, waits for the check, and confirms that a content export of the withdrawn request is refused.",
     "human": "Approve the staging pull request as the owner. Approve and merge the receipt-only pull request with the second account."},
    {"id": "A10", "runbook": "Acceptance, step 10", "mode": AUTO,
     "title": "Stop the scheduled workflow and read the scan health",
     "does": "Disables the verifier workflow, waits past check_health_max_age_seconds, runs the doctor and expects scan-health not verified, "
             "then enables the workflow again and waits for a healthy scan.",
     "human": ""},
]
STEP_IDS = [s["id"] for s in STEPS]
STEP_BY_ID = {s["id"]: s for s in STEPS}

# The rows of the table in docs/organization-setup.md, in order. The first column is copied from the document.
TABLE_ROWS = [
    ("Date of the run", None),
    ("Platform and plan", ["A1"]),
    ("Repository ids (tooling, engineering, staging)", ["S1", "S3"]),
    ("App id and permissions", ["S2"]),
    ("Ruleset ids and the settings they hold", ["S3", "S5"]),
    ("Request opened by the Actions identity (step 2)", ["A2"]),
    ("Owner approval and stale-review dismissal (step 3)", ["A3"]),
    ("Last-pusher setting off (step 4)", ["A4"]),
    ("Staging check outcomes (step 5)", ["A5"]),
    ("Merge activation (step 6)", ["A6"]),
    ("Engineering check outcomes (step 7)", ["A7"]),
    ("Replacement (step 8)", ["A8"]),
    ("Receipt-only withdrawal (step 9)", ["A9"]),
    ("Scan health and scheduler behavior (step 10)", ["A10"]),
    ("Sanitized check outcomes (ids and reason codes only)", None),
]
NOT_YET = "Not yet performed"
# Ids made by a step that then failed. A retry must reuse them: prepare --new-request would otherwise make a third request.
KEEP_ON_FAILURE = ("replacement_request_id", "withdrawal_event_id")


# ---------------------------------------------------------------------------
# Output, time, redaction
# ---------------------------------------------------------------------------

def say(text=""):
    print(text, flush=True)


def ask(prompt):
    return input(prompt)


def sleep(seconds):
    time.sleep(seconds)


def now_text():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


TOKEN_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S),
)
BEARER = re.compile(r"(?i)((?:authorization|x-github-token)\s*[:=]\s*(?:bearer|token)?\s*)[^\s'\"]+")
KEY_DENY = re.compile(r"(?i)token|passw|private_key|privatekey|credential|api_?key|\bpem\b")


def redact(text):
    """The text with every token shape, private key block and authorization value replaced. Applied to everything
    that comes back from gh or from a script, and to everything written to the record."""
    text = "" if text is None else str(text)
    for pattern in TOKEN_PATTERNS:
        text = pattern.sub("<redacted>", text)
    return BEARER.sub(lambda m: m.group(1) + "<redacted>", text)


def sanitize(value, depth=0):
    """A copy of value that holds only plain data: redacted short strings, numbers, booleans, lists and dicts.
    Keys that name a credential are dropped."""
    if depth > 8:
        return None
    if isinstance(value, dict):
        return {str(k): sanitize(v, depth + 1) for k, v in value.items() if not KEY_DENY.search(str(k))}
    if isinstance(value, (list, tuple, set)):
        return [sanitize(v, depth + 1) for v in (sorted(value, key=str) if isinstance(value, set) else value)]
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return value
    return redact(value)[:300]


# ---------------------------------------------------------------------------
# gh, called with argument arrays
# ---------------------------------------------------------------------------

class Refused(Exception):
    """The program refuses to do this. Nothing was run."""


class DryRunStop(Exception):
    """A write was reached in a dry run. The text says what would be done."""


class GhError(Exception):
    def __init__(self, status, text, args=None):
        super().__init__(text)
        self.status = status
        self.text = text
        self.args_shown = args or []


class StepFailed(Exception):
    def __init__(self, code, text=""):
        super().__init__(text or code)
        self.code = code
        self.text = text or code


FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}
METHOD_FLAGS = {"-X", "--method"}
READ_ONLY_COMMANDS = {("auth", "status"), ("repo", "view"), ("repo", "clone"), ("secret", "list"), ("workflow", "view"),
                      ("workflow", "list"), ("pr", "view"), ("pr", "list"), ("run", "view"), ("run", "list")}
DELETE_WORDS = {"delete", "remove", "rm", "destroy"}


def api_method(args):
    """(method, has body) of a gh api argument array."""
    method, body = None, False
    i = 0
    while i < len(args):
        a = args[i]
        if a in METHOD_FLAGS and i + 1 < len(args):
            method = args[i + 1].upper()
            i += 1
        elif a.startswith("--method="):
            method = a.split("=", 1)[1].upper()
        elif a.startswith("-X") and len(a) > 2:
            method = a[2:].upper()
        elif a in FIELD_FLAGS or any(a.startswith(f + "=") for f in ("--field", "--raw-field", "--input")):
            body = True
            if a in FIELD_FLAGS:
                i += 1
        i += 1
    return method, body


def is_read_only(args):
    """True when the gh call can change nothing on GitHub."""
    if not args:
        return False
    if args[0] == "api":
        method, body = api_method(args[1:])
        return (method in (None, "GET")) and not body
    return tuple(args[:2]) in READ_ONLY_COMMANDS


def refuse_delete(args):
    """The program never deletes. A delete method or a delete subcommand is refused before gh runs."""
    method, _ = api_method(args[1:]) if args and args[0] == "api" else (None, False)
    words = {str(a).lower() for a in args[:3] if not str(a).startswith("-")}
    if method == "DELETE" or (args and args[0] != "api" and words & DELETE_WORDS):
        raise Refused("this program never deletes a resource, so it refused: " + " ".join(str(a) for a in args[:3]))


class GhResult:
    def __init__(self, code, out, err):
        self.code, self.out, self.err = code, redact(out), redact(err)


class Gh:
    """The one place that starts gh. It refuses a delete, refuses a write unless apply is set, and redacts the output."""

    def __init__(self, apply=False):
        self.apply = apply

    @staticmethod
    def available():
        return shutil.which("gh") is not None

    def run(self, args, stdin=None, timeout=300):
        args = [str(a) for a in args]
        refuse_delete(args)
        if not self.apply and not is_read_only(args):
            raise DryRunStop(describe(args))
        env = dict(os.environ, GH_PROMPT_DISABLED="1", NO_COLOR="1", GH_NO_UPDATE_NOTIFIER="1", GH_SPINNER_DISABLED="1")
        try:
            extra = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
            proc = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=timeout, env=env, **extra)
        except FileNotFoundError:
            raise StepFailed("gh-missing", "the gh command line tool is not installed")
        except subprocess.TimeoutExpired:
            raise GhError(None, "gh did not answer in time", args)
        return GhResult(proc.returncode, proc.stdout, proc.stderr)

    def api(self, path, method=None, body=None, optional=False):
        """The parsed JSON of a gh api call. A 404 gives None when optional. Any other failure raises GhError."""
        args = ["api", path.lstrip("/")]
        if method and method.upper() != "GET":
            args = ["api", "-X", method.upper(), path.lstrip("/")]
        stdin = None
        if body is not None:
            args += ["--input", "-"]
            stdin = json.dumps(body)
        result = self.run(args, stdin=stdin)
        if result.code != 0:
            status = None
            found = re.search(r"HTTP (\d{3})", result.err + result.out)
            if found:
                status = int(found.group(1))
            if optional and status == 404:
                return None
            raise GhError(status, (result.err or result.out).strip()[:300], args[:3])
        text = result.out.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            raise GhError(None, "gh returned text that is not JSON", args[:3])


def describe(args):
    if args and args[0] == "api":
        method, _ = api_method(args[1:])
        paths = [a for a in args[1:] if not a.startswith("-") and a.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE")]
        return f"{method or 'POST'} {paths[0] if paths else ''}".strip()
    return "gh " + " ".join(args[:3])


# ---------------------------------------------------------------------------
# The record file
# ---------------------------------------------------------------------------

def load_records(path):
    out = []
    p = Path(path)
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("step") in STEP_BY_ID:
            out.append(row)
    return out


def append_record(path, record):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = sanitize(dict(record, sanitized=True))
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


COMPLETE = ("done", "skipped", "human")


def latest_by_step(records):
    out = {}
    for row in records:
        out[row["step"]] = row
    return out


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------

def git_blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def b64(data):
    return base64.b64encode(data).decode("ascii")


def sha256_text(data):
    return hashlib.sha256(data).hexdigest()


def slug_of(name):
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")


def app_name_for(org):
    return f"carrydown-verifier-{org}"[:34].rstrip("-")


def check_codes(text):
    """The fixed reason codes in a check title: kebab-case words."""
    return sorted(set(re.findall(r"\b[a-z]+(?:-[a-z]+)+\b", text or "")))


def scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_./-]*", s) and s.lower() not in ("true", "false", "null", "yes", "no", "on", "off"):
        return s
    return json.dumps(s)


def flow(v):
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {flow(x)}" for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(flow(x) for x in v) + "]"
    return scalar(v)


def enrollment_text(host, tooling_id, entry):
    """enrollment.yaml in the block style the verifier's launcher needs: one key per line, verifier_sha on a line of its
    own with the full commit id. Nested values are written in flow style, as in verifier/enrollment.schema.md."""
    lines = ["format: 1", f"host: {host}", f"tooling_repository_id: {tooling_id}", "repositories:"]
    first = True
    for key, value in entry.items():
        lead = "  - " if first else "    "
        first = False
        if key == "verifier_sha":
            lines.append(f"{lead}{key}: {value}")
        elif key == "attestations":
            if not value:
                lines.append(f"{lead}{key}: []")
                continue
            lines.append(f"{lead}{key}:")
            for att in value:
                inner = list(att.items())
                lines.append(f"      - {inner[0][0]}: {flow(inner[0][1])}")
                for k, v in inner[1:]:
                    lines.append(f"        {k}: {json.dumps(v) if isinstance(v, str) and k in ('at', 'expires_at', 'note') else flow(v)}")
        elif key == "governed_paths":
            lines.append(f"{lead}{key}: [{', '.join(json.dumps(p) for p in value)}]")
        elif key == "engineer_edits":
            lines.append(f"{lead}{key}: {{{', '.join(f'{k}: {v}' for k, v in value.items())}}}")
        else:
            lines.append(f"{lead}{key}: {flow(value)}")
    return "\n".join(lines) + "\n"


def pointer_text(tooling_full, enrollment_id):
    return f"format: 1\ntooling_repository: {tooling_full}\nenrollment_id: {enrollment_id}\n"


def working_plan_text(sample_plan, org, owner_login):
    """The owner's working plan of the sample, made the plan of a project that answered no to the one question: the repository
    is in the throwaway organization and the owner is the approver."""
    for old in ("repo: sct-will/carrydown-sample", "repo_audience_approved: true", "approvers: []"):
        if old not in sample_plan:
            raise StepFailed("sample-plan-changed", f"the sample's working plan no longer holds the line {old!r}")
    text = sample_plan.replace("repo: sct-will/carrydown-sample", f"repo: {org}/{ENGINEERING_NAME}", 1)
    text = text.replace("repo_audience_approved: true", "repo_audience_approved: false", 1)
    return text.replace("approvers: []", f'approvers: ["{owner_login}"]', 1)


def ruleset_problem(existing, wanted):
    """None when the ruleset on GitHub holds what wanted holds, else a short reason."""
    for key in ("name", "target", "enforcement"):
        if existing.get(key) != wanted.get(key):
            return f"{key} differs"
    if existing.get("bypass_actors"):
        return "a bypass actor is set"
    if (existing.get("conditions") or {}).get("ref_name", {}).get("include") != wanted["conditions"]["ref_name"]["include"]:
        return "the branch condition differs"
    have = {r.get("type"): r.get("parameters") or {} for r in existing.get("rules") or []}
    want = {r["type"]: r.get("parameters") or {} for r in wanted["rules"]}
    if set(have) != set(want):
        return "the rule types differ"
    for kind, params in want.items():
        for k, v in params.items():
            if kind == "required_status_checks" and k == "required_status_checks":
                got = sorted((c.get("context"), c.get("integration_id")) for c in have[kind].get(k) or [])
                if got != sorted((c["context"], c["integration_id"]) for c in v):
                    return "the required checks differ"
            elif have[kind].get(k) != v:
                return f"{kind}.{k} differs"
    return None


def ruleset_settings(ruleset):
    """The settings of a ruleset that the record table shows, as plain values."""
    out = {"enforcement": ruleset.get("enforcement"), "bypass_actors": len(ruleset.get("bypass_actors") or [])}
    for rule in ruleset.get("rules") or []:
        p = rule.get("parameters") or {}
        if rule["type"] == "pull_request":
            for k in ("required_approving_review_count", "dismiss_stale_reviews_on_push", "require_last_push_approval", "allowed_merge_methods"):
                if k in p:
                    out[k] = p[k]
        elif rule["type"] == "required_status_checks":
            out["strict_required_status_checks_policy"] = p.get("strict_required_status_checks_policy")
            out["required_checks"] = [f"{c.get('context')}@{c.get('integration_id')}" for c in p.get("required_status_checks") or []]
        else:
            out[rule["type"]] = True
    return out


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def cmd_plan(a):
    say("Acceptance on real GitHub: the plan")
    say("")
    say("Nothing is run by this command. It needs no gh and touches no network.")
    say("")
    say("Inputs that run needs")
    say("  --org NAME            a GitHub organization created only for this run, and --throwaway to say so")
    say("  --record PATH         where the run appends its records (JSON lines). Keep it. render reads it")
    say(f"  --carrydown PATH      a checkout of the carrydown repository to copy scripts/ and verifier/ from (default: {DEFAULT_CARRYDOWN})")
    say("  the candidate         a fictional project: a copy of sample/expense-approvals with the owner workspace fixture")
    say("                        (tests/fixtures/sample-workspace/drafts/plan.yaml), wired as tests/rebuild_sample_release.py wires it")
    say("  one human owner       the person who runs this, an owner of the organization, signed in with gh")
    say("  a second account      a fictional reviewer with write access to the engineering repository, for steps A7 to A9 (GitHub does")
    say("                        not let the author of a pull request approve it)")
    say("")
    say("The steps (the tag says who acts)")
    for s in STEPS:
        say(f"{s['id']:<4}[{s['mode']}] {s['title']}  ({s['runbook']})")
        say(f"        does: {s['does']}")
        if s["human"]:
            say(f"        you:  {s['human']}")
    humans = [s["id"] for s in STEPS if s["mode"] in (HUMAN, MIXED)]
    say("")
    say(f"{len(STEPS)} steps. A person acts in {', '.join(humans)}. The program pauses there, prints exactly what to do and what to confirm,")
    say("waits for you to press enter, and checks the result through gh api before it goes on.")
    say("")
    say("Commands, in order")
    say("  python3 tests/acceptance/live_github_run.py doctor --org NAME")
    say("  python3 tests/acceptance/live_github_run.py plan")
    say("  python3 tests/acceptance/live_github_run.py run --org NAME --throwaway --record run.jsonl --apply")
    say("  python3 tests/acceptance/live_github_run.py render --record run.jsonl")
    say("")
    say("Rules the run keeps: no resource is ever deleted, no push is forced, a step that finished is not repeated, and no token is read,")
    say("printed or stored. Without --apply it only reads. The plan owner authorizes the run explicitly before --apply.")
    return 0


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def print_install(say_):
    say_("The gh command line tool is not installed. Installing software is your decision. When you are ready:")
    for line in INSTALL_LINES:
        say_(line)


def fallback_client(carrydown):
    """A read-only GitHub client from the repository's own scripts, using the token that scripts/github_token.py stored. Only doctor
    reads use it, and only when --api-fallback is given. Returns None when no token is stored."""
    scripts = str(Path(carrydown) / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        import github_client as G
        token = G.read_token(None, required=False)
    except (ImportError, SystemExit):
        return None
    return G.GitHub(token) if token else None


def table(rows):
    width = max([len(r[0]) for r in rows] + [5])
    say(f"{'check':<{width}}  {'status':<12}  detail")
    for name, status, detail in rows:
        say(f"{name:<{width}}  {status:<12}  {detail}")


def identity_value(key):
    """One value of the commit identity, or an empty string when it is not set or the commit tool is not installed."""
    try:
        return subprocess.run(["git", "config", key], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        return ""


def cmd_doctor(a):
    rows = []
    gh_ok = Gh.available()
    carry = Path(a.carrydown).resolve()
    rows.append(("gh is installed", "verified" if gh_ok else "not verified", shutil.which("gh") or "not found on PATH"))
    py_ok = sys.version_info >= (3, 9)
    rows.append(("Python 3.9 or later", "verified" if py_ok else "not verified", sys.version.split()[0]))
    name, email = identity_value("user.name"), identity_value("user.email")
    rows.append(("git identity", "verified" if name and email else "not verified",
                 "user.name and user.email are set" if name and email else "run git config --global user.name and user.email"))
    needed = [carry / "scripts" / "release.py", carry / "scripts" / "workspace.py", carry / "verifier" / "verify_release.py",
              carry / "templates" / "staging" / "open-release-request.yml", carry / "tests" / "rebuild_sample_release.py"]
    missing = [str(p.relative_to(carry)) for p in needed if not p.is_file()]
    rows.append(("carrydown checkout", "verified" if not missing else "not verified", str(carry) if not missing else "missing: " + ", ".join(missing)))
    if not gh_ok:
        for label in ("gh is signed in", "gh token scopes", "signed-in login", "organization exists", "role in the organization",
                      "candidate builds a release locally"):
            rows.append((label, "not verified", "needs gh"))
        if a.api_fallback:
            fallback_rows(a, carry, rows)
        table(rows)
        say("")
        print_install(say)
        return 1
    gh = Gh(apply=False)
    status = gh.run(["auth", "status"])
    signed = status.code == 0
    rows.append(("gh is signed in", "verified" if signed else "not verified",
                 " ".join(redact(status.out + status.err).split())[:160] if signed else "run: gh auth login"))
    login = None
    if signed:
        scopes = re.search(r"Token scopes:\s*(.*)", status.out + status.err)
        have = {s.strip(" '\"*") for s in (scopes.group(1).split(",") if scopes else [])}
        lacking = [s for s in GH_SCOPES if s not in have]
        rows.append(("gh token scopes", "verified" if scopes and not lacking else "not verified",
                     "repo, workflow, admin:org present" if scopes and not lacking else
                     ("scopes not shown by gh" if not scopes else "missing " + ", ".join(lacking)) + ". Fix: gh auth refresh -s " + ",".join(GH_SCOPES)))
        try:
            me = gh.api("user")
            login = me.get("login")
            rows.append(("signed-in login", "verified", login))
        except GhError as e:
            rows.append(("signed-in login", "not verified", f"HTTP {e.status}"))
    else:
        for label in ("gh token scopes", "signed-in login"):
            rows.append((label, "not verified", "gh is not signed in"))
        if a.api_fallback:
            fallback_rows(a, carry, rows)
    if a.org and signed:
        try:
            org = gh.api(f"orgs/{a.org}", optional=True)
        except GhError as e:
            org = False
            rows.append(("organization exists", "not verified", f"HTTP {e.status}"))
        if org is None:
            rows.append(("organization exists", "not verified", f"{a.org} was not found, or this login cannot see it"))
        elif org:
            plan = ((org.get("plan") or {}).get("name")) or ""
            rows.append(("organization exists", "verified", f"{a.org}, plan {plan or 'not shown'}"))
            rows.append(("plan holds rulesets on private repositories", "verified" if plan and plan.lower() != "free" else "not verified",
                         f"plan {plan or 'not shown'}" + ("" if plan and plan.lower() != "free" else ". The free plan does not enforce rulesets on private repositories")))
            try:
                member = gh.api(f"user/memberships/orgs/{a.org}", optional=True)
                role = (member or {}).get("role")
                rows.append(("role in the organization", "verified" if role == "admin" else "not verified",
                             f"{login or 'this login'} is {role or 'not a member'}" + ("" if role == "admin" else ". The run needs an owner")))
            except GhError as e:
                rows.append(("role in the organization", "not verified", f"HTTP {e.status}"))
    elif not a.org:
        rows.append(("organization exists", "not verified", "no --org given"))
        rows.append(("role in the organization", "not verified", "no --org given"))
    if not missing:
        built = subprocess.run([sys.executable, str(carry / "tests" / "rebuild_sample_release.py"), "--check"], capture_output=True, text=True,
                               cwd=str(carry), env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        rows.append(("candidate builds a release locally", "verified" if built.returncode == 0 else "not verified",
                     (redact(built.stdout).strip().splitlines() or ["no output"])[0][:160]))
    else:
        rows.append(("candidate builds a release locally", "not verified", "the checkout is incomplete"))
    table(rows)
    ok = all(r[1] == "verified" for r in rows)
    say("")
    say("Ready for the run." if ok else "Not ready. Fix the rows marked not verified, then run doctor again.")
    return 0 if ok else 1


def fallback_rows(a, carry, rows):
    """Read-only lookups through the repository's own github_client and the stored token. Doctor reads only."""
    client = fallback_client(carry)
    if client is None:
        rows.append(("fallback: stored token", "not verified", "no token is stored. Run scripts/github_token.py"))
        return
    try:
        status, me = client.rest_status("GET", "/user")
        rows.append(("fallback: signed-in login", "verified" if status == 200 else "not verified",
                     (me or {}).get("login", "") if status == 200 else f"HTTP {status}"))
        if a.org:
            status, org = client.rest_status("GET", f"/orgs/{a.org}")
            rows.append(("fallback: organization exists", "verified" if status == 200 else "not verified",
                         a.org if status == 200 else f"HTTP {status}"))
            status, member = client.rest_status("GET", f"/user/memberships/orgs/{a.org}")
            role = (member or {}).get("role") if status == 200 else None
            rows.append(("fallback: role in the organization", "verified" if role == "admin" else "not verified", role or f"HTTP {status}"))
    except Exception as e:      # a refusal text from github_client is already redacted by that module
        rows.append(("fallback: read", "not verified", redact(str(e))[:160]))


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

class Runner:
    def __init__(self, a):
        self.a = a
        self.org = a.org
        self.apply = bool(a.apply) and not a.dry_run
        self.record_path = Path(a.record)
        self.carry = Path(a.carrydown).resolve()
        self.work = Path(a.workdir) if a.workdir else self.record_path.parent / (self.record_path.stem + ".work")
        self.gh = Gh(apply=self.apply)
        self.ctx = {}
        self.used_human = False
        self.owner = None
        self.poll = a.poll_seconds

    # --- names ---
    def full(self, name):
        return f"{self.org}/{name}"

    @property
    def project(self):
        return self.work / "project"

    @property
    def workspace(self):
        return self.work / "workspace"

    # --- the loop ---
    def run(self):
        records = load_records(self.record_path)
        done = {k for k, r in latest_by_step(records).items() if r["state"] in COMPLETE}
        for row in records:
            self.ctx.update((row.get("evidence") or {}).get("ids") or {})
        order = STEP_IDS
        start = order.index(self.a.from_step) if self.a.from_step else 0
        stop = order.index(self.a.to_step) if self.a.to_step else len(order) - 1
        if stop < start:
            say("error: --to comes before --from")
            return 2
        if not self.apply:
            say("DRY RUN: only reads. Nothing is written to GitHub, to the working folder or to the record file. Add --apply to run.")
        skipped_earlier = [s for s in order[:start] if s not in done]
        if skipped_earlier and self.apply:
            say(f"note: {', '.join(skipped_earlier)} have no finished record. Their results are read from GitHub when a later step needs them.")
        failed = False
        for sid in order[start:stop + 1]:
            step = STEP_BY_ID[sid]
            if sid in done:
                say(f"[{sid}] already recorded as finished. Not repeated.")
                continue
            say("")
            say(f"[{sid}] {step['title']}  [{step['mode']}]")
            started = now_text()
            self.used_human = False
            try:
                state, evidence = getattr(self, "step_" + sid)()
            except DryRunStop as e:
                say(f"  would act: {e}")
                continue
            except StepFailed as e:
                if not self.apply:
                    say(f"  cannot be checked yet ({e.code}). It depends on an earlier step: {redact(e.text)[:120]}")
                    continue
                state = "failed"
                evidence = dict(getattr(e, "evidence", None) or {})
                evidence["reason_codes"] = [e.code]
                evidence["notes"] = [e.text]
                evidence.setdefault("ids", {}).update({k: self.ctx[k] for k in KEEP_ON_FAILURE if self.ctx.get(k)})
                say(f"  FAILED: {e.code}. {redact(e.text)}")
            except GhError as e:
                if not self.apply:
                    say(f"  cannot be checked yet (HTTP {e.status}). It depends on an earlier step or on access: {redact(e.text)[:120]}")
                    continue
                state = "failed"
                evidence = {"reason_codes": [f"gh-http-{e.status}" if e.status else "gh-error"], "notes": [e.text],
                            "urls": [" ".join(e.args_shown)], "ids": {k: self.ctx[k] for k in KEEP_ON_FAILURE if self.ctx.get(k)}}
                say(f"  FAILED: gh {' '.join(e.args_shown)}: {redact(e.text)}")
            except Refused as e:
                state, evidence = "failed", {"reason_codes": ["refused"], "notes": [str(e)]}
                say(f"  REFUSED: {e}")
            if not self.apply:
                say(f"  {state}: already in place" if state in COMPLETE else f"  {state}")
                continue
            append_record(self.record_path, {"step": sid, "started": started, "finished": now_text(), "state": state, "evidence": evidence})
            self.ctx.update(sanitize((evidence or {}).get("ids") or {}))
            say(f"  {state}" + (f": {', '.join((evidence or {}).get('reason_codes') or [])}" if state == "failed" else ""))
            if state == "failed":
                failed = True
                break
        if self.apply:
            say("")
            say(("The run stopped at a failed step. Fix the cause and run the same command again: finished steps are not repeated."
                 if failed else "Done. Render the table with: render --record " + str(self.record_path)))
        return 1 if failed else 0

    # --- helpers: owner, repositories, files ---
    def need_owner(self):
        if self.owner is None:
            me = self.gh.api("user")
            self.owner = {"login": me["login"], "id": me["id"]}
        return self.owner

    def get_repo(self, name):
        return self.gh.api(f"repos/{self.full(name)}", optional=True)

    def ensure_repo(self, name, description):
        info = self.get_repo(name)
        if info:
            if info.get("private") is not True:
                raise StepFailed("repository-not-private", f"{self.full(name)} exists and is not private")
            return info, False
        created = self.gh.api(f"orgs/{self.org}/repos", "POST", {"name": name, "private": True, "auto_init": True, "description": description,
                                                                   "has_issues": False, "has_wiki": False, "has_projects": False})
        return created, True

    def ref_sha(self, repo, branch):
        ref = self.gh.api(f"repos/{repo}/git/ref/heads/{branch}", optional=True)
        return ((ref or {}).get("object") or {}).get("sha")

    def tree_of(self, repo, commit_sha):
        commit = self.gh.api(f"repos/{repo}/git/commits/{commit_sha}")
        tree = self.gh.api(f"repos/{repo}/git/trees/{commit['tree']['sha']}?recursive=1")
        if tree.get("truncated"):
            raise StepFailed("tree-truncated", "the repository tree is too large to compare")
        return commit["tree"]["sha"], {t["path"]: (t["sha"], t["mode"]) for t in tree.get("tree", []) if t.get("type") == "blob"}

    def commit_files(self, repo, branch, files, message):
        """One commit on branch with files ({path: (mode, bytes)}), through the Git data API. Returns the commit id, or None when
        every file is already there with the same bytes and mode."""
        head = self.ref_sha(repo, branch)
        for _ in range(5):
            if head:
                break
            sleep(2)        # a repository created with auto_init may not show its first commit at once
            head = self.ref_sha(repo, branch)
        if not head:
            raise StepFailed("branch-missing", f"{repo} has no branch {branch}")
        base_tree, have = self.tree_of(repo, head)
        todo = {p: (m, b) for p, (m, b) in files.items() if have.get(p) != (git_blob_sha(b), m)}
        if not todo:
            return None
        entries = []
        for path, (mode, data) in sorted(todo.items()):
            blob = self.gh.api(f"repos/{repo}/git/blobs", "POST", {"content": b64(data), "encoding": "base64"})
            entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        tree = self.gh.api(f"repos/{repo}/git/trees", "POST", {"base_tree": base_tree, "tree": entries})
        commit = self.gh.api(f"repos/{repo}/git/commits", "POST", {"message": message, "tree": tree["sha"], "parents": [head]})
        self.gh.api(f"repos/{repo}/git/refs/heads/{branch}", "PATCH", {"sha": commit["sha"], "force": False})
        return commit["sha"]

    def file_bytes(self, repo, path, ref=None):
        """The bytes of a file at ref (the default branch when ref is None), or None when it is not there."""
        got = self.gh.api(f"repos/{repo}/contents/{path}" + (f"?ref={ref}" if ref else ""), optional=True)
        if not got or got.get("encoding") != "base64":
            return None
        return base64.b64decode(got["content"])

    def find_commit(self, repo, branch, prefix):
        rows = self.gh.api(f"repos/{repo}/commits?sha={branch}&per_page=100") or []
        for row in rows:
            if (row.get("commit") or {}).get("message", "").startswith(prefix):
                return row["sha"]
        return None

    def ensure_ruleset(self, repo, wanted):
        """The id and settings of the ruleset named wanted["name"], created when missing. A ruleset that differs is never changed."""
        rows = self.gh.api(f"repos/{repo}/rulesets") or []
        found = [r for r in rows if r.get("name") == wanted["name"]]
        if found:
            full = self.gh.api(f"repos/{repo}/rulesets/{found[0]['id']}")
            problem = ruleset_problem(full, wanted)
            if problem:
                raise StepFailed("ruleset-differs", f"{repo} has a ruleset named {wanted['name']} that differs: {problem}. It was not changed")
            return full["id"], ruleset_settings(full), False
        created = self.gh.api(f"repos/{repo}/rulesets", "POST", wanted)
        full = self.gh.api(f"repos/{repo}/rulesets/{created['id']}")
        problem = ruleset_problem(full, wanted)
        if problem:
            raise StepFailed("ruleset-differs", f"the ruleset GitHub stored differs from the one sent: {problem}")
        return full["id"], ruleset_settings(full), True

    def script(self, name, args, writes=False, folder="scripts", cwd=None, timeout=900):
        """Run one of the repository's own scripts from the carrydown checkout. Never a shell string. Output is redacted."""
        if writes and not self.apply:
            raise DryRunStop(f"{name} {' '.join(str(x) for x in args[:2])}")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if getattr(self.a, "token_file", None):
            args = list(args) + ["--token-file", self.a.token_file] if name in ("release.py",) else list(args)
        try:
            proc = subprocess.run([sys.executable, str(self.carry / folder / name)] + [str(x) for x in args], capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL, cwd=str(cwd) if cwd else None, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise StepFailed("script-timeout", f"{name} did not finish in time")
        return GhResult(proc.returncode, proc.stdout, proc.stderr)

    def local_git(self, args, cwd=None, binary=False):
        proc = subprocess.run(["git"] + [str(x) for x in args], cwd=str(cwd or self.project), capture_output=True, text=not binary,
                              stdin=subprocess.DEVNULL)
        if proc.returncode != 0:
            raise StepFailed("local-git-failed", "git " + " ".join(str(x) for x in args[:2]) + ": " + redact(proc.stderr if not binary else "")[:160])
        return proc.stdout

    # --- helpers: human steps ---
    def human(self, title, lines, confirm, verify, attempts=5):
        """Ask a person to do something, then check it. verify() returns (ok, evidence, message). A result that is already true is
        accepted without a pause."""
        ok, evidence, message = verify()
        if ok:
            return evidence
        if not self.apply:
            raise DryRunStop("a person does this: " + title)
        self.used_human = True
        for _ in range(attempts):
            say("")
            say(f"  >>> HUMAN STEP: {title}")
            for line in lines:
                say(f"      {line}")
            say(f"      Confirm that: {confirm}")
            if message:
                say(f"      Not yet verified: {message}")
            try:
                answer = ask("      Press enter when done (type quit to stop the run): ")
            except EOFError:
                raise StepFailed("no-operator", "the run needs a person at the keyboard for this step. It stopped without changing anything")
            if answer.strip().lower() == "quit":
                raise StepFailed("operator-stopped", "the operator stopped the run at a human step")
            ok, evidence, message = verify()
            if ok:
                return evidence
        raise StepFailed("human-action-not-verified", message or title)

    # --- helpers: checks, workflows, pull requests ---
    def dispatch(self, repo, workflow):
        branch = (self.get_repo(repo.split("/", 1)[1]) or {}).get("default_branch", "main")
        self.gh.api(f"repos/{repo}/actions/workflows/{workflow}/dispatches", "POST", {"ref": branch})

    def pr_for_branch(self, repo, branch):
        rows = self.gh.api(f"repos/{repo}/pulls?state=all&head={self.org}:{branch}&per_page=10") or []
        rows = [r for r in rows if (r.get("head") or {}).get("ref") == branch]
        return rows[0] if rows else None

    def wait_pr(self, repo, branch, workflow=None):
        deadline = time.time() + max(self.poll, 1)
        dispatched = False
        while True:
            pr = self.pr_for_branch(repo, branch)
            if pr:
                return pr
            if time.time() >= deadline:
                raise StepFailed("request-pull-request-pending", f"no pull request for {branch} yet. Run the same command again later")
            if workflow and not dispatched:
                try:
                    self.dispatch(repo, workflow)
                except GhError:
                    pass
                dispatched = True
            sleep(POLL_INTERVAL)

    def check_run(self, repo, head, name):
        rows = (self.gh.api(f"repos/{repo}/commits/{head}/check-runs?per_page=100") or {}).get("check_runs") or []
        rows = sorted((r for r in rows if r.get("name") == name), key=lambda r: r.get("id") or 0)
        if not rows:
            return None
        r = rows[-1]
        title = (r.get("output") or {}).get("title") or ""
        return {"id": r.get("id"), "status": r.get("status"), "conclusion": r.get("conclusion"), "app_id": (r.get("app") or {}).get("id"),
                "title": title[:100], "reason_codes": check_codes(title)}

    def wait_check(self, repo, head, name, want=None, timeout=CHECK_TIMEOUT):
        """The check run of the verifier App on head, once it has completed (and, with want, once its conclusion is want or the
        wait ends). The verifier runs on a schedule, so the tooling workflow is dispatched now and again while waiting."""
        tooling = self.full(TOOLING_NAME)
        deadline = time.time() + timeout
        last = 0.0
        while True:
            run = self.check_run(repo, head, name)
            if run and run["status"] == "completed" and (want is None or run["conclusion"] == want):
                return run
            if time.time() >= deadline:
                return run
            if time.time() - last >= 120:
                try:
                    self.dispatch(tooling, VERIFY_WORKFLOW)
                except GhError:
                    pass
                last = time.time()
            sleep(POLL_INTERVAL)

    def project_ready(self):
        return (self.project / ".git").exists() and (self.workspace / "workspace.yaml").is_file()

    def need(self, key):
        """A value an earlier step recorded, or, for ids that GitHub can tell, the value read from GitHub now."""
        value = self.ctx.get(key) or self.discover(key)
        if not value:
            raise StepFailed("earlier-step-missing", f"{key} is not known. Run the earlier steps first")
        self.ctx[key] = value
        return value

    def discover(self, key):
        names = {"tooling_repository_id": TOOLING_NAME, "engineering_repository_id": ENGINEERING_NAME, "staging_repository_id": STAGING_NAME}
        if key in names:
            info = self.get_repo(names[key])
            return info["id"] if info else None
        if key in ("app_id", "app_slug", "installation_id"):
            inst = self.installation()
            return {"app_id": inst["app_id"], "app_slug": inst["app_slug"], "installation_id": inst["id"]}[key] if inst else None
        if key == "verifier_sha":
            tooling, branch = self.tooling_head()
            return self.find_commit(tooling, branch, PIN_MESSAGE)
        if key == "staging_ruleset_id":
            rows = self.gh.api(f"repos/{self.full(STAGING_NAME)}/rulesets") or []
            return next((r["id"] for r in rows if r.get("name") == RULESET_NAME), None)
        if key == "staging_workflow_sha256":
            data = self.file_bytes(self.full(STAGING_NAME), ".github/workflows/" + REQUEST_WORKFLOW)
            return sha256_text(data) if data is not None else None
        return None

    def reader_ids(self):
        """The accounts that can read the staging repository, plus the owner."""
        if self.ctx.get("staging_reader_ids"):
            return list(self.ctx["staging_reader_ids"])
        people = self.gh.api(f"repos/{self.full(STAGING_NAME)}/collaborators?affiliation=all&per_page=100") or []
        return sorted({p["id"] for p in people} | {self.need_owner()["id"]})

    # =======================================================================
    # Organization setup
    # =======================================================================

    def step_S1(self):
        owner = self.need_owner()
        repo_name = TOOLING_NAME
        info, created = self.ensure_repo(repo_name, "Carrydown verifier and enrollment for the acceptance run")
        full = self.full(repo_name)
        files = {}
        for folder in ("scripts", "verifier"):
            for path in sorted((self.carry / folder).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and path.name != ".DS_Store":
                    mode = "100755" if os.access(path, os.X_OK) else "100644"
                    files[path.relative_to(self.carry).as_posix()] = (mode, path.read_bytes())
        files[".github/workflows/" + VERIFY_WORKFLOW] = ("100644", (self.carry / "verifier" / VERIFY_WORKFLOW).read_bytes())
        branch = info.get("default_branch", "main")
        sha = self.commit_files(full, branch, files, PIN_MESSAGE)
        pinned = sha or self.find_commit(full, branch, PIN_MESSAGE)
        if not pinned:
            raise StepFailed("verifier-commit-not-found", "the files are present but no commit named " + PIN_MESSAGE + " was found")
        ids = {"tooling_repository_id": info["id"], "verifier_sha": pinned, "owner_login": owner["login"], "owner_id": owner["id"]}
        evidence = {"ids": ids, "urls": [f"https://github.com/{full}"], "settings": {"private": True, "files_committed": len(files)}}
        return ("done" if created or sha else "skipped"), evidence

    def app_slug(self):
        return self.a.app_slug or slug_of(app_name_for(self.org))

    def installation(self):
        slug = self.app_slug()
        rows = (self.gh.api(f"orgs/{self.org}/installations?per_page=100") or {}).get("installations") or []
        for row in rows:
            if row.get("app_slug") == slug:
                return row
        return None

    def secret_names(self, repo):
        got = self.gh.api(f"repos/{repo}/actions/secrets?per_page=100", optional=True)
        return sorted(s["name"] for s in (got or {}).get("secrets") or [])

    def app_state(self):
        """(ok, evidence, message) for the App: it exists, carries exactly the permissions, is installed on the tooling repository, and
        the private key is stored as a secret of that repository only."""
        inst = self.installation()
        if not inst:
            return False, None, f"no installation of the App {self.app_slug()} was found in {self.org}"
        perms = {k: v for k, v in (inst.get("permissions") or {}).items()}
        if perms != APP_PERMISSIONS:
            return False, None, "the App permissions are " + json.dumps(perms, sort_keys=True) + ", not " + json.dumps(APP_PERMISSIONS, sort_keys=True)
        if inst.get("repository_selection") != "selected":
            return False, None, "the App is installed on all repositories. Choose only selected repositories"
        tooling = self.full(TOOLING_NAME)
        repos = (self.gh.api(f"user/installations/{inst['id']}/repositories?per_page=100", optional=True) or {}).get("repositories") or []
        if TOOLING_NAME not in [r.get("name") for r in repos]:
            return False, None, f"the App is not installed on {tooling}"
        names = self.secret_names(tooling)
        if "CARRYDOWN_APP_PRIVATE_KEY" not in names:
            return False, None, "the secret CARRYDOWN_APP_PRIVATE_KEY is not stored in " + tooling
        org_names = [s["name"] for s in (self.gh.api(f"orgs/{self.org}/actions/secrets?per_page=100", optional=True) or {}).get("secrets") or []]
        if any(n.startswith("CARRYDOWN_") for n in org_names):
            return False, None, "an organization secret named CARRYDOWN_ exists. Remove it yourself: the verifier credential belongs to the tooling repository only"
        evidence = {"ids": {"app_id": inst["app_id"], "app_slug": inst["app_slug"], "installation_id": inst["id"]},
                    "settings": {"permissions": perms, "repository_selection": "selected", "webhook": "not readable without an App token"}}
        return True, evidence, ""

    def step_S2(self):
        self.need_owner()
        name = app_name_for(self.org)
        tooling = self.full(TOOLING_NAME)
        manifest = {"name": name, "url": f"https://github.com/{tooling}", "redirect_url": REDIRECT, "public": False,
                    "default_permissions": dict(APP_PERMISSIONS)}
        page = self.work / "app-manifest.html"
        slug = self.app_slug()
        ok, evidence, message = self.app_state()
        if not ok:
            if not self.apply:
                raise DryRunStop("write the App manifest page " + str(page))
            self.work.mkdir(parents=True, exist_ok=True)
            (self.work / "app-manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
            page.write_bytes(("<!doctype html>\n<meta charset=\"utf-8\"><title>Create the carrydown verifier App</title>\n"
                f"<h1>Create the verifier App for {html.escape(self.org)}</h1>\n"
                "<p>The button sends the manifest to GitHub. GitHub asks you to confirm the name.</p>\n"
                f"<form method=\"post\" action=\"https://github.com/organizations/{html.escape(self.org)}/settings/apps/new\">\n"
                f"<input type=\"hidden\" name=\"manifest\" value=\"{html.escape(json.dumps(manifest), quote=True)}\">\n"
                "<button type=\"submit\">Create the GitHub App</button>\n</form>\n").encode("utf-8"))
        lines = [
            f"1. Open this page in a browser where you are signed in to GitHub as an owner of {self.org}: file://{page}",
            "2. Click Create the GitHub App, then confirm the name on GitHub. The App has webhooks off and four permissions: "
            "Contents read, Pull requests read, Checks write, Metadata read.",
            f"3. GitHub then sends the browser to {REDIRECT}, which does not load. Copy the value after code= in the address bar. It works once.",
            "4. In a terminal run this, with that value in place of CODE. The key goes through the pipe into the secret and is never shown or saved:",
            f"     gh api -X POST app-manifests/CODE/conversions --jq .pem | gh secret set CARRYDOWN_APP_PRIVATE_KEY --repo {tooling}",
            f"5. Install the App: https://github.com/apps/{slug}/installations/new . Choose {self.org}, Only select repositories, and select {TOOLING_NAME}.",
        ]
        evidence = self.human("create the verifier App", lines,
                              "the App exists with those permissions, its key is the secret CARRYDOWN_APP_PRIVATE_KEY of the tooling repository, "
                              "and it is installed on the tooling repository only", self.app_state)
        app_id = evidence["ids"]["app_id"]
        names = self.secret_names(tooling)
        stored = False
        if "CARRYDOWN_APP_ID" not in names:
            result = self.gh.run(["secret", "set", "CARRYDOWN_APP_ID", "--repo", tooling, "--body", str(app_id)])
            if result.code != 0:
                raise StepFailed("secret-not-stored", "gh secret set failed for CARRYDOWN_APP_ID: " + result.err.strip()[:160])
            stored = True
        evidence["settings"]["names_stored"] = sorted(set(self.secret_names(tooling)))
        return ("human" if self.used_human else ("done" if stored else "skipped")), evidence

    def step_S3(self):
        owner = self.need_owner()
        app_id = self.need("app_id")
        inst_id = self.need("installation_id")
        tooling_id = self.need("tooling_repository_id")
        eng, eng_new = self.ensure_repo(ENGINEERING_NAME, "Fictional engineering repository for the acceptance run")
        stg, stg_new = self.ensure_repo(STAGING_NAME, "Fictional staging repository for the acceptance run")
        changed = eng_new or stg_new
        # merge commits only on staging
        want = {"allow_merge_commit": True, "allow_squash_merge": False, "allow_rebase_merge": False}
        if any(stg.get(k) != v for k, v in want.items()):
            self.gh.api(f"repos/{self.full(STAGING_NAME)}", "PATCH", want)
            changed = True
        # the App on both repositories
        installed = [r.get("name") for r in (self.gh.api(f"user/installations/{inst_id}/repositories?per_page=100") or {}).get("repositories") or []]
        for name, info in ((ENGINEERING_NAME, eng), (STAGING_NAME, stg)):
            if name in installed:
                continue
            try:
                self.gh.api(f"user/installations/{inst_id}/repositories/{info['id']}", "PUT")
                changed = True
            except GhError:
                self.human(f"add the App to {self.full(name)}",
                           [f"Open https://github.com/organizations/{self.org}/settings/installations/{inst_id} and add {self.full(name)} to the selected repositories."],
                           f"the App is installed on {self.full(name)}", lambda n=name: self.installed_on(inst_id, n))
        # the request-opening workflow, then the pointer, before the rulesets forbid direct commits
        workflow = (self.carry / "templates" / "staging" / REQUEST_WORKFLOW).read_bytes()
        stg_branch = stg.get("default_branch", "main")
        if self.commit_files(self.full(STAGING_NAME), stg_branch, {".github/workflows/" + REQUEST_WORKFLOW: ("100644", workflow)}, "Add the request-opening workflow"):
            changed = True
        enrollment_id = self.enrollment_id(eng["id"], tooling_id)
        eng_branch = eng.get("default_branch", "main")
        pointer = {".carrydown/release-policy.yaml": ("100644", pointer_text(self.full(TOOLING_NAME), enrollment_id).encode("utf-8")),
                   ".gitignore": ("100644", b".carrydown/local.yaml\n")}
        if self.commit_files(self.full(ENGINEERING_NAME), eng_branch, pointer, "Add the carrydown policy pointer"):
            changed = True
        # Actions may open pull requests in staging
        perms = self.gh.api(f"repos/{self.full(STAGING_NAME)}/actions/permissions/workflow")
        if not perms.get("can_approve_pull_request_reviews") or perms.get("default_workflow_permissions") != "read":
            self.gh.api(f"repos/{self.full(STAGING_NAME)}/actions/permissions/workflow", "PUT",
                        {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": True})
            perms = self.gh.api(f"repos/{self.full(STAGING_NAME)}/actions/permissions/workflow")
            changed = True
        if not perms.get("can_approve_pull_request_reviews"):
            raise StepFailed("actions-cannot-open-pull-requests", "the organization setting blocks Actions from creating pull requests in staging")
        # the rulesets, from the repository's own printer
        ids, settings = {}, {}
        for kind, name in (("staging", STAGING_NAME), ("engineering", ENGINEERING_NAME)):
            printed = self.script("verify_release.py", ["ruleset", "--kind", kind, "--app-id", app_id], folder="verifier")
            if printed.code != 0:
                raise StepFailed("ruleset-not-printed", f"verify_release.py ruleset --kind {kind} failed")
            rid, shown, new = self.ensure_ruleset(self.full(name), json.loads(printed.out))
            ids[f"{kind}_ruleset_id"] = rid
            settings[f"{kind}_ruleset"] = shown
            changed = changed or new
        # who can read the staging repository (read only; the doctor judges it)
        people = self.gh.api(f"repos/{self.full(STAGING_NAME)}/collaborators?affiliation=all&per_page=100") or []
        teams = self.gh.api(f"repos/{self.full(STAGING_NAME)}/teams") or []
        keys = self.gh.api(f"repos/{self.full(STAGING_NAME)}/keys") or []
        reader_ids = sorted({p["id"] for p in people} | {owner["id"]})
        ids.update({"engineering_repository_id": eng["id"], "staging_repository_id": stg["id"], "enrollment_id": enrollment_id,
                    "staging_workflow_sha256": sha256_text(workflow), "staging_reader_ids": reader_ids})
        settings.update({"merge_methods": {k: v for k, v in want.items()}, "actions_can_create_pull_requests": True,
                         "staging_teams": len(teams), "staging_deploy_keys": len(keys)})
        evidence = {"ids": ids, "urls": [f"https://github.com/{self.full(ENGINEERING_NAME)}", f"https://github.com/{self.full(STAGING_NAME)}"],
                    "settings": settings, "logins": [p["login"] for p in people]}
        return ("done" if changed else "skipped"), evidence

    def installed_on(self, inst_id, name):
        repos = [r.get("name") for r in (self.gh.api(f"user/installations/{inst_id}/repositories?per_page=100") or {}).get("repositories") or []]
        return (name in repos), {}, f"the App is not yet installed on {name}"

    def enrollment_id(self, repo_id, tooling_id):
        """The stable enrollment id, from the repository's own digests command. A file with one entry that carries only a repository id."""
        with tempfile.TemporaryDirectory(prefix="carrydown-acc-") as tmp:
            f = Path(tmp) / "enrollment.yaml"
            f.write_bytes((f"format: 1\nhost: github.com\ntooling_repository_id: {tooling_id}\nrepositories:\n  - repository_id: {repo_id}\n").encode("utf-8"))
            out = self.script("verify_release.py", ["digests", "--policy-file", f], folder="verifier")
        found = re.search(r"enrollment_id ([0-9a-f]{64})", out.out)
        if not found:
            raise StepFailed("digests-unreadable", "verify_release.py digests printed no enrollment_id")
        return found.group(1)

    def digests(self, text):
        """(enrollment_id, policy_sha256, matches) of the single entry in text, from the repository's own digests command."""
        with tempfile.TemporaryDirectory(prefix="carrydown-acc-") as tmp:
            f = Path(tmp) / "enrollment.yaml"
            f.write_bytes((text).encode("utf-8"))
            out = self.script("verify_release.py", ["digests", "--policy-file", f], folder="verifier")
        found = re.search(r"enrollment_id ([0-9a-f]{64}), policy_sha256 ([0-9a-f]{64}) \((matches|differs from) the file\)", out.out)
        if not found:
            raise StepFailed("digests-unreadable", "verify_release.py digests could not read the enrollment file")
        return found.group(1), found.group(2), found.group(3) == "matches"

    def entry(self, attestations):
        owner = self.need_owner()
        entry = {
            "repository": self.full(ENGINEERING_NAME), "repository_id": self.need("engineering_repository_id"),
            "enrollment_id": "", "policy_sha256": "",
            "staging_repository": self.full(STAGING_NAME), "staging_repository_id": self.need("staging_repository_id"),
            "staging_workflow_sha256": self.need("staging_workflow_sha256"),
            "staging_readers": {"user_ids": sorted(set(self.reader_ids()) | {owner["id"]}),
                                "approved_service_ids": [self.need("app_slug")]},
            "approvers": [{"id": owner["id"], "login": owner["login"]}],
            "administrators": [{"id": owner["id"], "login": owner["login"]}],
            "allowed_targets": {"engineering": {"host": "github.com", "repository_id": self.need("engineering_repository_id"),
                                                "repository": self.full(ENGINEERING_NAME)}},
            "governed_paths": ["docs/spec/**", "docs/context/**", "docs/release/**", "docs/dev/skills/**", "docs/ground-truth/**"],
            "engineer_edits": {"docs/spec/**": "request-only"}, "reuse_unchanged_preview": False, "offline_grace_days": 7,
            "verifier_sha": self.need("verifier_sha"), "verifier_app_id": self.need("app_id"),
            "check_health_max_age_seconds": HEALTH_SECONDS, "attestations": attestations,
        }
        return entry

    def finish_enrollment(self, attestations):
        """The text of enrollment.yaml with both digests filled in, checked against verify_release.py digests."""
        tooling_id = self.need("tooling_repository_id")
        entry = self.entry(attestations)
        enrollment_id, policy, _ = self.digests(enrollment_text("github.com", tooling_id, entry))
        entry["enrollment_id"] = enrollment_id
        entry["policy_sha256"] = ""
        enrollment_id, policy, _ = self.digests(enrollment_text("github.com", tooling_id, entry))
        entry["enrollment_id"], entry["policy_sha256"] = enrollment_id, policy
        text = enrollment_text("github.com", tooling_id, entry)
        _, _, same = self.digests(text)
        if not same:
            raise StepFailed("digests-differ", "the enrollment file does not match its own digests")
        return text, enrollment_id, policy

    def tooling_head(self):
        tooling = self.full(TOOLING_NAME)
        branch = (self.get_repo(TOOLING_NAME) or {}).get("default_branch", "main")
        return tooling, branch

    def step_S4(self):
        self.need("verifier_sha")
        tooling, branch = self.tooling_head()
        current = self.file_bytes(tooling, "enrollment.yaml", branch)
        sha = None
        if current is None:
            text, enrollment_id, policy = self.finish_enrollment([])
            sha = self.commit_files(tooling, branch, {"enrollment.yaml": ("100644", text.encode("utf-8"))}, ENROLL_MESSAGE)
        else:
            enrollment_id, policy, same = self.digests(current.decode("utf-8", "replace"))
            if not same:
                raise StepFailed("digests-differ", "enrollment.yaml in the tooling repository does not match its own digests")
        policy_commit = self.ref_sha(tooling, branch)
        pointer = self.file_bytes(self.full(ENGINEERING_NAME), ".carrydown/release-policy.yaml")
        if pointer is None or enrollment_id not in pointer.decode("utf-8", "replace"):
            raise StepFailed("policy-pointer-mismatch", "the engineering repository has no policy pointer that names this enrollment")
        if self.need("verifier_sha") == policy_commit:
            raise StepFailed("verifier-commit-is-policy-commit", "the policy commit must be later than the verifier commit")
        evidence = {"ids": {"policy_commit_sha": policy_commit, "enrollment_id": enrollment_id, "policy_sha256": policy},
                    "urls": [f"https://github.com/{tooling}/blob/{branch}/enrollment.yaml"],
                    "settings": {"pointer_checked": True, "verifier_sha_earlier_than_policy": True, "targets": ["engineering"]}}
        return ("done" if sha else "skipped"), evidence

    def attestations(self):
        owner = self.need_owner()
        now = dt.datetime.now(dt.timezone.utc)
        at = (now - dt.timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
        until = (now + dt.timedelta(days=ATTEST_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        eng, stg = self.need("engineering_repository_id"), self.need("staging_repository_id")
        readers = sorted(set(self.reader_ids()) | {owner["id"]})
        base = {"by_id": owner["id"], "at": at, "expires_at": until}
        return [
            dict(component="staging-readers", **base, subject={"repository_id": stg, "reader_ids": readers, "service_ids": [self.need("app_slug")]},
                 note="Throwaway run: the owner is the only reader. The App is the only installed service"),
            dict(component="runtime-isolation", **base, subject={"repository_id": eng, "environment_id": "throwaway-run-no-agents"},
                 note="Throwaway run: no engineering agent environment exists"),
            dict(component="verifier-isolation", **base, subject={"repository_id": eng, "staging_repository_id": stg},
                 note="Neither repository holds the verifier workflow or its secrets, read by the owner at attestation time"),
        ]

    def isolation_facts(self):
        """(ok, message): the facts of the attestations that can be read, read now."""
        for name in (ENGINEERING_NAME, STAGING_NAME):
            repo = self.full(name)
            if any(n.upper().startswith("CARRYDOWN_APP") for n in self.secret_names(repo)):
                return False, f"{repo} holds a verifier secret"
            if self.file_bytes(repo, ".github/workflows/" + VERIFY_WORKFLOW) is not None:
                return False, f"{repo} holds the verifier workflow"
        stg = self.full(STAGING_NAME)
        teams = self.gh.api(f"repos/{stg}/teams") or []
        keys = self.gh.api(f"repos/{stg}/keys") or []
        if teams or keys:
            return False, f"{stg} has {len(teams)} team(s) and {len(keys)} deploy key(s). Remove them in the browser, then continue"
        return True, ""

    def step_S5(self):
        tooling, branch = self.tooling_head()
        current = self.file_bytes(tooling, "enrollment.yaml", branch) or b""
        have = {c for c in ("staging-readers", "runtime-isolation", "verifier-isolation") if f"component: {c}" in current.decode("utf-8", "replace")}
        proposed = self.attestations()
        evidence = {"ids": {}, "settings": {"attested": [p["component"] for p in proposed]}}
        wrote = None
        if len(have) < 3:
            ok, message = self.isolation_facts()
            if not ok:
                raise StepFailed("attested-fact-false", message)
            if not self.apply:
                raise DryRunStop("a person vouches for the attestations, then enrollment.yaml is updated")
            lines = [f"You are vouching, as the administrator of {self.org}, for these facts. Read them, then type vouch at the prompt:"]
            lines += [f"  - {p['component']}: {p['note']}" for p in proposed]
            lines.append("They are written into enrollment.yaml of the tooling repository with your numeric id, valid for "
                         f"{ATTEST_DAYS} days. The tooling default branch is protected right after, so this is the last direct commit.")
            self.used_human = True
            say("")
            say("  >>> HUMAN STEP: vouch for the attestations")
            for line in lines:
                say(f"      {line}")
            try:
                answer = ask("      Type vouch to confirm, or quit to stop the run: ")
            except EOFError:
                raise StepFailed("no-operator", "the run needs a person at the keyboard for this step")
            if answer.strip().lower() != "vouch":
                raise StepFailed("operator-stopped", "the administrator did not vouch")
            text, enrollment_id, policy = self.finish_enrollment(proposed)
            wrote = self.commit_files(tooling, branch, {"enrollment.yaml": ("100644", text.encode("utf-8"))}, "Add the scoped attestations")
            evidence["ids"].update({"enrollment_id": enrollment_id, "policy_sha256": policy, "policy_commit_sha": self.ref_sha(tooling, branch)})
            evidence["settings"]["expires_in_days"] = ATTEST_DAYS
        body = {"name": TOOLING_RULESET_NAME, "target": "branch", "enforcement": "active",
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}, "bypass_actors": [],
                "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
                          {"type": "pull_request", "parameters": {"required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
                                                                  "require_code_owner_review": False, "require_last_push_approval": False,
                                                                  "required_review_thread_resolution": False}}]}
        rid, shown, new = self.ensure_ruleset(tooling, body)
        evidence["ids"]["tooling_ruleset_id"] = rid
        evidence["settings"]["tooling_ruleset"] = shown
        evidence["reason_codes"] = ["runtime-isolation-attested-only"]
        evidence["ids"]["policy_commit_sha"] = evidence["ids"].get("policy_commit_sha") or self.ref_sha(tooling, branch)
        return ("human" if self.used_human else ("done" if (new or wrote) else "skipped")), evidence

    # --- the local candidate project ---
    def ensure_project(self):
        """The fictional candidate: a clone of the engineering repository, a private workspace, and the sample's owner working plan,
        wired as tests/rebuild_sample_release.py wires the sample. Idempotent."""
        if self.project_ready():
            return False
        if not self.apply:
            raise DryRunStop("create the candidate project in " + str(self.work))
        owner = self.need_owner()
        self.work.mkdir(parents=True, exist_ok=True)
        if not (self.project / ".git").exists():
            got = self.gh.run(["repo", "clone", self.full(ENGINEERING_NAME), str(self.project)])
            if got.code != 0:
                raise StepFailed("clone-failed", "gh repo clone failed: " + got.err.strip()[:160])
        init = self.script("workspace.py", ["init", "--root", self.project, "--slug", "expense-approvals", "--workspace", self.workspace,
                                            "--answer", "no", "--staging-repository", self.full(STAGING_NAME), "--apply"], writes=True, cwd=self.project)
        if init.code != 0:
            raise StepFailed("workspace-init-failed", "workspace.py init refused: " + init.err.strip()[:160])
        write_candidate(self.carry, self.workspace, self.org, owner["login"])
        return True

    def doctor_lines(self):
        out = self.script("release.py", ["doctor", "--root", self.project], cwd=self.project)
        statuses = {}
        for line in out.out.splitlines():
            m = re.match(r"\s{2}(verified|not verifiable|missing)\s+([a-z-]+):", line)
            if m:
                statuses[m.group(2)] = m.group(1)
        needed = re.findall(r"needed: ([a-z-]+)", out.out)
        upload = re.search(r"private upload to the staging repository: (\S+)", out.out)
        export = re.search(r"export and publication: (\S+)", out.out)
        return out, statuses, sorted(set(needed)), (upload.group(1) if upload else None), (export.group(1) if export else None)

    def wait_scan(self):
        """A complete, successful verifier run that captured the current policy commit. Dispatches the tooling workflow when needed."""
        tooling = self.full(TOOLING_NAME)
        tip = self.ref_sha(tooling, self.tooling_head()[1])
        deadline = time.time() + CHECK_TIMEOUT
        dispatched = False
        while True:
            runs = (self.gh.api(f"repos/{tooling}/actions/workflows/{VERIFY_WORKFLOW}/runs?status=completed&per_page=1") or {}).get("workflow_runs") or []
            if runs and runs[0].get("conclusion") == "success" and runs[0].get("head_sha") == tip:
                return {"run_id": runs[0]["id"], "conclusion": "success", "head_sha": tip}
            if time.time() >= deadline:
                raise StepFailed("verifier-scan-not-complete", "no complete successful verifier run for the current policy commit")
            if not dispatched:
                self.dispatch(tooling, VERIFY_WORKFLOW)
                dispatched = True
            sleep(POLL_INTERVAL)

    def run_doctor(self):
        """(created, evidence, ok): the local project, a complete scan, then release.py doctor."""
        created = self.ensure_project()
        scan = self.wait_scan()
        out, statuses, needed, upload, export = self.doctor_lines()
        evidence = {"ids": {"scan_run_id": scan["run_id"]},
                    "settings": {"components": statuses, "private_upload": upload, "export_and_publication": export, "doctor_exit": out.code},
                    "reason_codes": needed}
        ok = out.code == 0 and upload == "allowed" and export == "allowed"
        return created, evidence, ok

    def step_S6(self):
        created, evidence, ok = self.run_doctor()
        for name, status in sorted(evidence["settings"]["components"].items()):
            say(f"    {status:<14} {name}")
        if not ok:
            e = StepFailed("doctor-not-verified", "release.py doctor: not every component is verified: " + ", ".join(evidence["reason_codes"] or ["see the table"]))
            e.evidence = evidence
            raise e
        return "done", evidence

    def step_S7(self):
        self.ensure_project()
        repo_id = str(self.need("engineering_repository_id"))
        preview = self.script("release.py", ["preview", "--root", self.project], cwd=self.project)
        if preview.code != 0:
            raise StepFailed("preview-refused", "release.py preview refused: " + (preview.err or preview.out).strip()[-160:])
        prepared = self.script("release.py", ["prepare", "--root", self.project, "--repository-id", repo_id, "--no-github", "--apply"], writes=True,
                               cwd=self.project)
        if prepared.code != 0:
            raise StepFailed("prepare-refused", "release.py prepare refused: " + (prepared.err or prepared.out).strip()[-160:])
        rid = re.search(r"request id \(permission\):\s*([0-9a-f]{64})", prepared.out)
        rel = re.search(r"release id \(content\):\s*([0-9a-f]{64})", prepared.out)
        if not rid:
            raise StepFailed("prepare-no-request-id", "release.py prepare printed no request id")
        evidence = {"ids": {"request_id": rid.group(1), "release_id": rel.group(1) if rel else ""},
                    "settings": {"github_payloads": "left out with --no-github", "audience": "repo-readers"}}
        return "done", evidence

    # =======================================================================
    # Acceptance
    # =======================================================================

    def step_A1(self):
        self.ensure_project()
        out, statuses, needed, upload, export = self.doctor_lines()
        if out.code != 0 or upload != "allowed" or export != "allowed":
            e = StepFailed("doctor-not-verified", "not every component is verified: " + ", ".join(needed or ["see release.py doctor"]))
            e.evidence = {"settings": {"components": statuses}, "reason_codes": needed}
            raise e
        org = self.gh.api(f"orgs/{self.org}")
        plan = (org.get("plan") or {}).get("name") or "not shown to this login"
        evidence = {"ids": {}, "settings": {"platform": "github.com", "organization_plan": plan, "components": statuses,
                                            "verified_components": sum(1 for s in statuses.values() if s == "verified"), "components_total": len(statuses)},
                    "reason_codes": needed}
        return "done", evidence

    def request_branch_pr(self, rid):
        return self.pr_for_branch(self.full(STAGING_NAME), f"request/{rid}")

    def upload(self, rid):
        """release.py approve --github, then the pull request of the request branch."""
        stg = self.full(STAGING_NAME)
        pr = self.request_branch_pr(rid)
        if pr is None:
            out = self.script("release.py", ["approve", "--root", self.project, "--request", rid, "--github", "--apply", "--poll-seconds", self.poll],
                              writes=True, cwd=self.project)
            if out.code != 0:
                raise StepFailed("approve-refused", "release.py approve refused: " + (out.err or out.out).strip()[-200:])
            pr = self.wait_pr(stg, f"request/{rid}", REQUEST_WORKFLOW)
        return pr

    def step_A2(self):
        self.ensure_project()
        rid = self.need("request_id")
        owner = self.need_owner()
        pr = self.upload(rid)
        author = pr.get("user") or {}
        head = pr["head"]["sha"]
        stg = self.full(STAGING_NAME)
        before = self.wait_check(stg, head, STAGING_CHECK)
        evidence = {"ids": {"staging_pull_request": pr["number"], "request_head_sha": head, "request_id": rid},
                    "urls": [pr.get("html_url", "")], "logins": [author.get("login", ""), owner["login"]],
                    "settings": {"opened_by": author.get("login"), "opened_by_type": author.get("type"), "owner_login": owner["login"],
                                 "check_before_review": before or {"conclusion": "not posted"}}}
        if author.get("login") == owner["login"] or author.get("login") != ACTIONS_LOGIN:
            raise_ = StepFailed("request-not-opened-by-actions", f"the pull request was opened by {author.get('login')}, not by {ACTIONS_LOGIN}")
            raise_.evidence = evidence
            raise raise_
        return "done", evidence

    def reviews(self, number):
        return self.gh.api(f"repos/{self.full(STAGING_NAME)}/pulls/{number}/reviews?per_page=100") or []

    def approved_at(self, number, head, who):
        return [r for r in self.reviews(number) if r.get("state") == "APPROVED" and r.get("commit_id") == head and (r.get("user") or {}).get("login") == who]

    def approve_head(self, number, who, label):
        """Wait for the owner's approval of the current head of the pull request."""
        stg = self.full(STAGING_NAME)

        def verify():
            pr = self.gh.api(f"repos/{stg}/pulls/{number}")
            head = pr["head"]["sha"]
            got = self.approved_at(number, head, who)
            return (bool(got)), {"review_id": got[0]["id"] if got else None, "head": head}, f"no approving review by {who} on head {head[:12]} yet"
        pr = self.gh.api(f"repos/{stg}/pulls/{number}")
        head = pr["head"]["sha"]
        return self.human(f"approve the {label} head of staging pull request #{number}",
                          [f"1. Open {pr.get('html_url')}", "2. Open Files changed and read what the request carries.",
                           f"3. Review changes, choose Approve, submit. The head is {head[:12]}. Approve as {who}, the owner."],
                          f"you approved head {head[:12]} as {who}", verify)

    def step_A3(self):
        owner = self.need_owner()
        number = self.need("staging_pull_request")
        stg = self.full(STAGING_NAME)
        who = owner["login"]
        dismissed = [r for r in self.reviews(number) if r.get("state") == "DISMISSED" and (r.get("user") or {}).get("login") == who]
        first = self.approve_head(number, who, "final")
        old_head = first["head"]
        new_head = old_head
        if not dismissed:
            pr = self.gh.api(f"repos/{stg}/pulls/{number}")
            branch = pr["head"]["ref"]
            commit = self.gh.api(f"repos/{stg}/git/commits/{old_head}")
            new = self.gh.api(f"repos/{stg}/git/commits", "POST", {"message": "Empty commit for the acceptance run: dismiss the stale approval",
                                                                    "tree": commit["tree"]["sha"], "parents": [old_head]})
            self.gh.api(f"repos/{stg}/git/refs/heads/{branch}", "PATCH", {"sha": new["sha"], "force": False})
            new_head = new["sha"]
            for _ in range(20):
                dismissed = [r for r in self.reviews(number) if r.get("state") == "DISMISSED" and (r.get("user") or {}).get("login") == who]
                if dismissed:
                    break
                sleep(3)
            if not dismissed:
                raise StepFailed("stale-approval-not-dismissed", "GitHub did not dismiss the approval after a new commit")
        second = self.approve_head(number, who, "new")
        if second["head"] == old_head and not dismissed:
            raise StepFailed("head-unchanged", "the head did not change")
        evidence = {"ids": {"staging_pull_request": number, "approved_head_sha": second["head"], "first_review_id": first["review_id"],
                            "dismissed_review_ids": [r["id"] for r in dismissed], "final_review_id": second["review_id"], "final_head_sha": second["head"]},
                    "settings": {"first_approval_dismissed": bool(dismissed), "approver": who, "empty_commit_pushed": new_head != old_head or bool(dismissed)}}
        return ("human" if self.used_human else ("done" if new_head != old_head else "skipped")), evidence

    def step_A4(self):
        owner = self.need_owner()
        number = self.need("staging_pull_request")
        stg = self.full(STAGING_NAME)
        rid = self.need("staging_ruleset_id")
        ruleset = self.gh.api(f"repos/{stg}/rulesets/{rid}")
        settings = ruleset_settings(ruleset)
        if settings.get("require_last_push_approval") is not False:
            raise StepFailed("last-push-approval-on", "require_last_push_approval is not false in the staging ruleset")
        head = self.need("final_head_sha")
        got = self.approved_at(number, head, owner["login"])
        commit = self.gh.api(f"repos/{stg}/commits/{head}")
        pusher = (commit.get("committer") or {}).get("login") or (commit.get("author") or {}).get("login")
        if not got:
            raise StepFailed("owner-approval-missing", "the owner has no approving review on the final head")
        evidence = {"ids": {"staging_ruleset_id": rid, "review_id": got[0]["id"], "final_head_sha": head},
                    "settings": {"require_last_push_approval": False, "head_pushed_by": pusher, "approved_by": owner["login"],
                                 "pusher_is_approver": pusher == owner["login"]}}
        return "done", evidence

    def step_A5(self):
        number = self.need("staging_pull_request")
        stg = self.full(STAGING_NAME)
        first = self.gh.api(f"repos/{stg}/pulls/{number}")
        head = first["head"]["sha"]
        after = self.wait_check(stg, head, STAGING_CHECK, want="success")
        app_id = self.need("app_id")
        evidence = {"ids": {"final_head_sha": head, "check_run_id": (after or {}).get("id")},
                    "settings": {"after_review": after or {"conclusion": "not posted"}, "check_app_id": (after or {}).get("app_id"), "verifier_app_id": app_id},
                    "reason_codes": (after or {}).get("reason_codes") or []}
        record = latest_by_step(load_records(self.record_path)).get("A2")
        before = ((record or {}).get("evidence") or {}).get("settings", {}).get("check_before_review") or {"conclusion": "not recorded"}
        evidence["settings"]["before_review"] = before
        if not after or after.get("conclusion") != "success":
            raise_ = StepFailed("staging-check-not-success-after-review", "the staging check did not pass on the reviewed final head")
            raise_.evidence = evidence
            raise raise_
        if after.get("app_id") != app_id:
            raise StepFailed("check-from-wrong-app", "the staging check was not posted by the verifier App")
        if before.get("conclusion") == "success":
            raise StepFailed("staging-check-passed-before-review", "the staging check already passed before the review")
        return "done", evidence

    def step_A6(self):
        number = self.need("staging_pull_request")
        rid = self.need("request_id")
        stg = self.full(STAGING_NAME)
        pr = self.gh.api(f"repos/{stg}/pulls/{number}")
        merged_now = False
        if not pr.get("merged"):
            try:
                self.gh.api(f"repos/{stg}/pulls/{number}/merge", "PUT", {"merge_method": "merge", "sha": pr["head"]["sha"]})
                merged_now = True
            except GhError as e:
                self.human("merge the staging pull request with a merge commit",
                           [f"GitHub refused the merge by API ({redact(e.text)[:100]}).", f"Open {pr.get('html_url')} and click Create a merge commit, then confirm."],
                           "the pull request is merged with a merge commit",
                           lambda: (bool(self.gh.api(f"repos/{stg}/pulls/{number}").get("merged")), {}, "the pull request is not merged yet"))
            pr = self.gh.api(f"repos/{stg}/pulls/{number}")
        sha = pr.get("merge_commit_sha")
        commit = self.gh.api(f"repos/{stg}/commits/{sha}")
        parents = len(commit.get("parents") or [])
        if parents != 2:
            raise StepFailed("not-a-merge-commit", f"the merge commit has {parents} parent(s)")
        dry = self.script("release.py", ["export", "--root", self.project, "--request", rid], cwd=self.project)
        if dry.code != 0:
            raise StepFailed("export-refused-after-merge", "release.py export does not accept the request: " + dry.err.strip()[-160:])
        evidence = {"ids": {"merge_commit_sha": sha, "staging_pull_request": number},
                    "settings": {"merge_commit_parents": parents, "export_dry_run_exit": dry.code, "request_active": True}}
        return ("human" if self.used_human else ("done" if merged_now else "skipped")), evidence

    # --- publishing an export branch to the engineering repository through the API ---
    def publish_branch(self, branch):
        """The local branch of the project, as one commit on top of the engineering default branch, through the Git data API. Returns
        (created, branch head sha). A remote branch that exists is compared and never changed."""
        eng = self.full(ENGINEERING_NAME)
        base = (self.get_repo(ENGINEERING_NAME) or {}).get("default_branch", "main")
        base_sha = self.ref_sha(eng, base)
        listing = self.local_git(["ls-tree", "-r", "-z", branch]).split("\0")
        local = {}
        for row in listing:
            if not row:
                continue
            meta, path = row.split("\t", 1)
            mode, kind, sha = meta.split()
            if kind == "blob":
                local[path] = (sha, mode)
        existing = self.ref_sha(eng, branch)
        base_tree, have = self.tree_of(eng, base_sha)
        if existing:
            _, there = self.tree_of(eng, existing)
            if there != local:
                raise StepFailed("branch-differs", f"{eng} already has a branch {branch} with other content. It was not changed")
            return False, existing
        entries = []
        for path, (sha, mode) in sorted(local.items()):
            if have.get(path) == (sha, mode):
                continue
            data = self.local_git(["cat-file", "blob", sha], binary=True)
            blob = self.gh.api(f"repos/{eng}/git/blobs", "POST", {"content": b64(data), "encoding": "base64"})
            entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        message = self.local_git(["log", "-1", "--format=%B", branch]).strip() or f"Release {branch}"
        tree = self.gh.api(f"repos/{eng}/git/trees", "POST", {"base_tree": base_tree, "tree": entries})
        commit = self.gh.api(f"repos/{eng}/git/commits", "POST", {"message": message, "tree": tree["sha"], "parents": [base_sha]})
        self.gh.api(f"repos/{eng}/git/refs", "POST", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
        return True, commit["sha"]

    def engineering_pr(self, branch, title, body):
        eng = self.full(ENGINEERING_NAME)
        pr = self.pr_for_branch(eng, branch)
        if pr is None:
            base = (self.get_repo(ENGINEERING_NAME) or {}).get("default_branch", "main")
            pr = self.gh.api(f"repos/{eng}/pulls", "POST", {"title": title, "head": branch, "base": base, "body": body})
        return pr

    def merge_engineering(self, number, label):
        """A person other than the author approves the final head and merges it with a merge commit."""
        eng = self.full(ENGINEERING_NAME)
        author = (self.gh.api(f"repos/{eng}/pulls/{number}").get("user") or {}).get("login")

        def verify():
            pr = self.gh.api(f"repos/{eng}/pulls/{number}")
            if not pr.get("merged"):
                return False, None, f"pull request #{number} is not merged yet"
            approvers = sorted({(r.get("user") or {}).get("login") for r in self.gh.api(f"repos/{eng}/pulls/{number}/reviews?per_page=100") or []
                                if r.get("state") == "APPROVED"} - {author})
            commit = self.gh.api(f"repos/{eng}/commits/{pr['merge_commit_sha']}")
            if not approvers:
                return False, None, "no account other than the author approved it"
            if self.a.reviewer_login and self.a.reviewer_login not in approvers:
                return False, None, f"{self.a.reviewer_login} did not approve it"
            if len(commit.get("parents") or []) != 2:
                return False, None, "it was not merged with a merge commit"
            return True, {"merge_commit_sha": pr["merge_commit_sha"], "approvers": approvers}, ""
        pr = self.gh.api(f"repos/{eng}/pulls/{number}")
        return self.human(f"approve and merge engineering pull request #{number} ({label}) with a second account",
                          [f"The author is {author}. GitHub does not let the author approve it, so use the second account.",
                           f"1. Open {pr.get('html_url')} signed in as the second account.",
                           "2. Check that carrydown-release-verifier passed. Review changes, Approve, submit.",
                           "3. Click Create a merge commit."], "the pull request is approved by another account and merged with a merge commit", verify)

    def step_A7(self):
        rid = self.need("request_id")
        eng = self.full(ENGINEERING_NAME)
        exported = self.script("release.py", ["export", "--root", self.project, "--request", rid, "--apply"], writes=True, cwd=self.project)
        if exported.code != 0:
            raise StepFailed("export-failed", "release.py export refused: " + (exported.err or exported.out).strip()[-160:])
        branch = f"carrydown/request-{rid}"
        pr = self.pr_for_branch(eng, branch)
        if pr is None:
            self.publish_branch(branch)
            pr = self.engineering_pr(branch, f"Release {rid[:12]}", f"Approved context. Request {rid}.")
        number = pr["number"]
        pr = self.gh.api(f"repos/{eng}/pulls/{number}")
        evidence = {"ids": {"engineering_pull_request": number, "engineering_head_sha": pr["head"]["sha"]}, "urls": [pr.get("html_url", "")], "settings": {}}
        if pr.get("merged"):
            return "skipped", evidence
        target, original = self.tamper_target(branch)
        self.restore_if_changed(eng, pr["head"]["ref"], target, original)      # a retry after a stop between the change and its restore
        pr = self.gh.api(f"repos/{eng}/pulls/{number}")
        check = self.wait_check(eng, pr["head"]["sha"], ENGINEERING_CHECK, want="success")
        evidence["settings"]["check_on_exported_head"] = check or {"conclusion": "not posted"}
        if not check or check.get("conclusion") != "success":
            raise_ = StepFailed("engineering-check-not-success", "the engineering check did not pass on the exported head")
            raise_.evidence = evidence
            raise raise_
        tampered = self.tamper(eng, pr["head"]["ref"], target, original)
        evidence["settings"]["check_after_one_byte_change"] = tampered
        evidence["reason_codes"] = tampered.get("reason_codes") or []
        merged = self.merge_engineering(number, "the first release")
        evidence["ids"].update(merged)
        evidence["settings"]["merged_with_second_account"] = True
        return ("human" if self.used_human else "done"), evidence

    def tamper_target(self, local_branch):
        """(path, bytes) of the exported file whose byte the run changes: the first Markdown file under docs/spec/ of the export."""
        base = (self.get_repo(ENGINEERING_NAME) or {}).get("default_branch", "main")
        names = self.local_git(["diff", "--name-only", f"origin/{base}", local_branch]).split()
        target = next((n for n in names if n.startswith("docs/spec/") and n.endswith(".md")), None)
        if not target:
            raise StepFailed("no-exported-file-to-change", "the export holds no Markdown file under docs/spec/")
        return target, self.local_git(["show", f"{local_branch}:{target}"], binary=True)

    def restore_if_changed(self, eng, head_ref, target, original):
        got = self.gh.api(f"repos/{eng}/contents/{target}?ref={head_ref}")
        if base64.b64decode(got["content"]) == original:
            return None
        put = self.gh.api(f"repos/{eng}/contents/{target}", "PUT", {"message": "Acceptance run: restore the byte", "content": b64(original),
                                                                    "sha": got["sha"], "branch": head_ref})
        return put["commit"]["sha"]

    def tamper(self, eng, head_ref, target, original):
        """Change one byte of an exported file, expect the engineering check to fail, then restore the file."""
        got = self.gh.api(f"repos/{eng}/contents/{target}?ref={head_ref}")
        index = next((i for i, c in enumerate(original) if 97 <= c <= 122), None)
        if index is None:
            raise StepFailed("no-letter-to-change", f"{target} holds no lowercase letter to change")
        changed = original[:index] + bytes([original[index] ^ 0x20]) + original[index + 1:]
        put = self.gh.api(f"repos/{eng}/contents/{target}", "PUT", {"message": "Acceptance run: change one byte", "content": b64(changed),
                                                                    "sha": got["sha"], "branch": head_ref})
        bad_head = put["commit"]["sha"]
        result = self.wait_check(eng, bad_head, ENGINEERING_CHECK)
        restored = self.restore_if_changed(eng, head_ref, target, original)
        if restored:
            self.wait_check(eng, restored, ENGINEERING_CHECK, want="success")
        if not result or result.get("conclusion") == "success":
            raise StepFailed("changed-file-passed", f"the engineering check did not fail after one byte of {target} changed")
        out = dict(result)
        out.update({"file": target, "byte_offset": index})
        return out

    def step_A8(self):
        self.ensure_project()
        first = self.need("request_id")
        stg = self.full(STAGING_NAME)
        replacement = self.ctx.get("replacement_request_id")
        if not replacement:
            prepared = self.script("release.py", ["prepare", "--root", self.project, "--repository-id", str(self.need("engineering_repository_id")),
                                                  "--no-github", "--new-request", "--apply"], writes=True, cwd=self.project)
            found = re.search(r"request id \(permission\):\s*([0-9a-f]{64})", prepared.out)
            if prepared.code != 0 or not found:
                raise StepFailed("prepare-replacement-refused", "release.py prepare refused: " + (prepared.err or prepared.out).strip()[-160:])
            replacement = found.group(1)
            self.ctx["replacement_request_id"] = replacement
        if replacement == first:
            raise StepFailed("replacement-is-the-first-request", "prepare returned the first request id")
        pr = self.upload(replacement)
        number = pr["number"]
        owner = self.need_owner()
        self.approve_head(number, owner["login"], "final")
        merged = self.gh.api(f"repos/{stg}/pulls/{number}")
        if not merged.get("merged"):
            head = merged["head"]["sha"]
            self.wait_check(stg, head, STAGING_CHECK, want="success")
            try:
                self.gh.api(f"repos/{stg}/pulls/{number}/merge", "PUT", {"merge_method": "merge", "sha": head})
            except GhError:
                self.human("merge the replacement pull request with a merge commit", [f"Open {merged.get('html_url')} and click Create a merge commit."],
                           "the pull request is merged", lambda: (bool(self.gh.api(f"repos/{stg}/pulls/{number}").get("merged")), {}, "not merged yet"))
        exported = self.script("release.py", ["export", "--root", self.project, "--request", replacement, "--apply"], writes=True, cwd=self.project)
        if exported.code != 0:
            raise StepFailed("export-failed", "release.py export refused: " + (exported.err or exported.out).strip()[-160:])
        branch = f"carrydown/request-{replacement}"
        old_receipt = self.local_git(["show", f"{branch}:docs/release/{first}.receipt.json"])
        new_receipt = self.local_git(["show", f"{branch}:docs/release/{replacement}.receipt.json"])
        old_state = json.loads(old_receipt).get("state")
        new_state = json.loads(new_receipt).get("state")
        if old_state != "superseded":
            raise StepFailed("first-request-not-superseded", f"the first request's receipt in the same branch says {old_state}")
        self.publish_branch(branch)
        eng_pr = self.engineering_pr(branch, f"Release {replacement[:12]}", f"Replacement. Request {replacement}.")
        eng = self.full(ENGINEERING_NAME)
        eng_pr = self.gh.api(f"repos/{eng}/pulls/{eng_pr['number']}")
        evidence = {"ids": {"replacement_request_id": replacement, "replacement_staging_pull_request": number,
                            "replacement_engineering_pull_request": eng_pr["number"]},
                    "urls": [eng_pr.get("html_url", "")],
                    "settings": {"first_receipt_state": old_state, "replacement_receipt_state": new_state, "receipts_in_one_branch": True}}
        if not eng_pr.get("merged"):
            check = self.wait_check(eng, eng_pr["head"]["sha"], ENGINEERING_CHECK, want="success")
            evidence["settings"]["engineering_check"] = check or {"conclusion": "not posted"}
            if not check or check.get("conclusion") != "success":
                raise_ = StepFailed("engineering-check-not-success", "the engineering check did not pass on the replacement export")
                raise_.evidence = evidence
                raise raise_
            evidence["ids"].update(self.merge_engineering(eng_pr["number"], "the replacement"))
        return ("human" if self.used_human else "done"), evidence

    def step_A9(self):
        self.ensure_project()
        rid = self.ctx.get("replacement_request_id") or self.need("request_id")
        stg = self.full(STAGING_NAME)
        eng = self.full(ENGINEERING_NAME)
        event = self.ctx.get("withdrawal_event_id")
        if not event:
            out = self.script("release.py", ["withdraw", "--root", self.project, "--request", rid, "--reason", WITHDRAW_REASON, "--apply",
                                             "--poll-seconds", self.poll], writes=True, cwd=self.project)
            found = re.search(r"is the event ([0-9a-f]{64})", out.out)
            if out.code != 0 or not found:
                raise StepFailed("withdraw-refused", "release.py withdraw refused: " + (out.err or out.out).strip()[-160:])
            event = found.group(1)
            self.ctx["withdrawal_event_id"] = event
        pr = self.wait_pr(stg, f"state/{event}", REQUEST_WORKFLOW)
        number = pr["number"]
        owner = self.need_owner()
        self.approve_head(number, owner["login"], "final")
        current = self.gh.api(f"repos/{stg}/pulls/{number}")
        if not current.get("merged"):
            head = current["head"]["sha"]
            self.wait_check(stg, head, STAGING_CHECK, want="success")
            try:
                self.gh.api(f"repos/{stg}/pulls/{number}/merge", "PUT", {"merge_method": "merge", "sha": head})
            except GhError:
                self.human("merge the state pull request with a merge commit", [f"Open {current.get('html_url')} and click Create a merge commit."],
                           "the pull request is merged", lambda: (bool(self.gh.api(f"repos/{stg}/pulls/{number}").get("merged")), {}, "not merged yet"))
        exported = self.script("release.py", ["export-state", "--root", self.project, "--request", rid, "--apply"], writes=True, cwd=self.project)
        if exported.code != 0:
            raise StepFailed("export-state-failed", "release.py export-state refused: " + (exported.err or exported.out).strip()[-160:])
        branch = f"carrydown/state-{rid}"
        self.publish_branch(branch)
        eng_pr = self.engineering_pr(branch, f"Receipt update {rid[:12]}", f"Receipt only. Request {rid} withdrawn.")
        eng_pr = self.gh.api(f"repos/{eng}/pulls/{eng_pr['number']}")
        files = [f["filename"] for f in self.gh.api(f"repos/{eng}/pulls/{eng_pr['number']}/files?per_page=100") or []]
        receipt_only = bool(files) and all(f.startswith("docs/release/") and f.endswith(".receipt.json") for f in files)
        evidence = {"ids": {"withdrawal_event_id": event, "state_staging_pull_request": number, "state_engineering_pull_request": eng_pr["number"]},
                    "urls": [eng_pr.get("html_url", "")], "settings": {"receipt_only": receipt_only, "files_changed": len(files)}}
        if not receipt_only:
            raise_ = StepFailed("pull-request-not-receipt-only", "the withdrawal pull request changes more than receipts")
            raise_.evidence = evidence
            raise raise_
        if not eng_pr.get("merged"):
            check = self.wait_check(eng, eng_pr["head"]["sha"], ENGINEERING_CHECK, want="success")
            evidence["settings"]["engineering_check"] = check or {"conclusion": "not posted"}
            if not check or check.get("conclusion") != "success":
                raise_ = StepFailed("engineering-check-not-success", "the receipt-only pull request did not pass")
                raise_.evidence = evidence
                raise raise_
            evidence["ids"].update(self.merge_engineering(eng_pr["number"], "receipt only"))
        refused = self.script("release.py", ["export", "--root", self.project, "--request", rid], cwd=self.project)
        codes = sorted(set(re.findall(r"\b(withdrawn|superseded|not-approved|expired|state-history-invalid|approval-not-found)\b", refused.out + refused.err)))
        evidence["settings"]["content_export_exit"] = refused.code
        evidence["reason_codes"] = codes
        if refused.code == 0:
            raise_ = StepFailed("content-publication-allowed", "release.py export accepted a withdrawn request")
            raise_.evidence = evidence
            raise raise_
        return ("human" if self.used_human else "done"), evidence

    def step_A10(self):
        tooling = self.full(TOOLING_NAME)
        wf = self.gh.api(f"repos/{tooling}/actions/workflows/{VERIFY_WORKFLOW}")
        if not self.apply:
            raise DryRunStop("disable the verifier workflow, wait past the health limit, run the doctor, enable the workflow")
        self.gh.api(f"repos/{tooling}/actions/workflows/{wf['id']}/disable", "PUT")
        statuses, stopped_at = {}, now_text()
        try:
            wait = HEALTH_SECONDS + 120
            say(f"  The workflow is disabled. Waiting {wait} seconds so that the last scan is older than the {HEALTH_SECONDS} second health limit.")
            end = time.time() + wait
            while time.time() < end:
                sleep(min(30, max(1, end - time.time())))
            out, statuses, needed, upload, export = self.doctor_lines()
            health = statuses.get("scan-health")
        finally:
            self.gh.api(f"repos/{tooling}/actions/workflows/{wf['id']}/enable", "PUT")
        restarted = "not checked"
        try:
            self.dispatch(tooling, VERIFY_WORKFLOW)
            scan = self.wait_scan()
            out2, statuses2, _, _, _ = self.doctor_lines()
            restarted = statuses2.get("scan-health", "unknown")
        except StepFailed:
            restarted = "no complete scan yet"
        evidence = {"ids": {"workflow_id": wf["id"]},
                    "settings": {"disabled_at": stopped_at, "waited_seconds": HEALTH_SECONDS + 120, "scan_health_while_stopped": health,
                                 "scan_health_after_restart": restarted, "workflow_enabled_again": True},
                    "reason_codes": ["verifier-unhealthy"] if health != "verified" else []}
        if health == "verified":
            raise_ = StepFailed("scan-health-still-verified", "the doctor still reported the scan health as verified after the wait")
            raise_.evidence = evidence
            raise raise_
        return "done", evidence


def write_candidate(carry, workspace, org, owner_login):
    """Put the sample's owner working files into the private workspace, the way tests/mock/release_fixture.py does for the
    confidential fixture: the working plan, the specifications under drafts/docs/spec and the renderings."""
    sample = Path(carry) / "sample" / "expense-approvals"
    plan = Path(carry) / "tests" / "fixtures" / "sample-workspace" / "drafts" / "plan.yaml"
    (Path(workspace) / "drafts").mkdir(parents=True, exist_ok=True)
    (Path(workspace) / "drafts" / "plan.yaml").write_bytes((working_plan_text(plan.read_text(encoding="utf-8"), org, owner_login)).encode("utf-8"))
    spec = Path(workspace) / "drafts" / "docs" / "spec"
    if spec.exists():
        shutil.rmtree(spec)
    shutil.copytree(sample / "docs" / "spec", spec, ignore=shutil.ignore_patterns("plan.yaml", "__pycache__"))
    shutil.copytree(sample / "docs" / "ground-truth", Path(workspace) / "renderings", dirs_exist_ok=True)


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def cell(text):
    return " ".join(str(text).replace("|", "/").split())


def short_settings(value, limit=420):
    text = json.dumps(sanitize(value), sort_keys=True, separators=(", ", ": "))
    return text if len(text) <= limit else text[:limit - 3] + "..."


def row_text(row):
    ev = row.get("evidence") or {}
    parts = [f"{row['state']} {row.get('finished', '')}".strip()]
    if ev.get("ids"):
        parts.append("ids " + short_settings(ev["ids"]))
    if ev.get("settings"):
        parts.append("settings " + short_settings(ev["settings"]))
    if ev.get("logins"):
        parts.append("logins " + ", ".join(sorted({str(x) for x in ev["logins"] if x})))
    if ev.get("reason_codes"):
        parts.append("reason codes " + ", ".join(ev["reason_codes"]))
    if ev.get("urls"):
        parts.append("urls " + " ".join(u for u in ev["urls"] if u))
    return "; ".join(parts)


def render_table(records):
    """The Markdown table of docs/organization-setup.md, from the records: the same rows in the same order."""
    last = latest_by_step(records)
    lines = ["| Item | Record |", "| --- | --- |"]
    for label, steps in TABLE_ROWS:
        if label == "Date of the run":
            times = sorted(r["started"] for r in records if r.get("started"))
            text = (f"{times[0][:10]} (first step {times[0]}, last record {max(r.get('finished', '') for r in records)})" if times else NOT_YET)
        elif label.startswith("Sanitized check outcomes"):
            codes = {}
            for sid in STEP_IDS:
                row = last.get(sid)
                if row and (row.get("evidence") or {}).get("reason_codes"):
                    codes[sid] = ", ".join(row["evidence"]["reason_codes"])
            text = "; ".join(f"{sid}: {c}" for sid, c in codes.items()) if codes else (NOT_YET if not records else "no reason codes recorded")
        else:
            rows = [last[s] for s in steps if s in last]
            text = " / ".join(f"{r['step']}: {row_text(r)}" for r in rows) if rows else NOT_YET
        lines.append(f"| {label} | {cell(text)} |")
    return "\n".join(lines)


def cmd_render(a):
    path = Path(a.record)
    if not path.is_file():
        say(f"error: the record file {path} does not exist")
        return 2
    say(render_table(load_records(path)))
    return 0


# ---------------------------------------------------------------------------
# run (entry) and the command line
# ---------------------------------------------------------------------------

ORG_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def cmd_run(a):
    if not a.throwaway:
        say("error: --throwaway is required. Say that the organization exists only for this run. "
            "The run creates repositories, rulesets and a GitHub App in it and never deletes any of them.")
        return 2
    if not ORG_RE.match(a.org or ""):
        say("error: --org is not a valid GitHub organization name")
        return 2
    if a.from_step and a.from_step not in STEP_BY_ID:
        say(f"error: --from must be one of {', '.join(STEP_IDS)}")
        return 2
    if a.to_step and a.to_step not in STEP_BY_ID:
        say(f"error: --to must be one of {', '.join(STEP_IDS)}")
        return 2
    if not Gh.available():
        print_install(say)
        return 1
    if not (Path(a.carrydown) / "scripts" / "release.py").is_file():
        say(f"error: {a.carrydown} is not a carrydown checkout (no scripts/release.py)")
        return 2
    return Runner(a).run()


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")
    p = sub.add_parser("plan", help="print the 17 steps and the inputs (the default)")
    p.add_argument("--org")
    p.add_argument("--carrydown", default=str(DEFAULT_CARRYDOWN))
    p.add_argument("--record")
    p = sub.add_parser("doctor", help="check the preconditions and print a table of verified and not verified")
    p.add_argument("--org", help="the throwaway organization to look up")
    p.add_argument("--carrydown", default=str(DEFAULT_CARRYDOWN), help="the carrydown checkout")
    p.add_argument("--api-fallback", action="store_true",
                   help="also read the login, the organization and the role through scripts/github_client.py and the token that scripts/github_token.py stored. Reads only")
    p = sub.add_parser("run", help="execute the steps in order, with records")
    p.add_argument("--org", required=True)
    p.add_argument("--throwaway", action="store_true", help="the organization exists only for this run")
    p.add_argument("--record", required=True, help="the record file (JSON lines)")
    p.add_argument("--carrydown", default=str(DEFAULT_CARRYDOWN), help="the carrydown checkout to copy scripts/ and verifier/ from")
    p.add_argument("--workdir", help="the working folder for the candidate project (default: next to the record file)")
    p.add_argument("--apply", action="store_true", help="write to GitHub. Without it the run only reads")
    p.add_argument("--dry-run", action="store_true", help="only reads, even with --apply")
    p.add_argument("--from", dest="from_step", metavar="STEP", help="start at this step, such as S3 or A5")
    p.add_argument("--to", dest="to_step", metavar="STEP", help="stop after this step")
    p.add_argument("--app-slug", help="the slug of the verifier App when it is not the default name")
    p.add_argument("--reviewer-login", help="the login of the second account that approves the engineering pull requests")
    p.add_argument("--token-file", help="passed to release.py, which reads the owner's token itself")
    p.add_argument("--poll-seconds", type=int, default=POLL_SECONDS, help="how long to wait for a pull request to appear")
    p = sub.add_parser("render", help="print the record table of docs/organization-setup.md from the records")
    p.add_argument("--record", required=True)
    return ap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in ("plan", "doctor", "run", "render", "-h", "--help")):
        argv = ["plan"] + argv
    a = build_parser().parse_args(argv)
    try:
        return {"plan": cmd_plan, "doctor": cmd_doctor, "run": cmd_run, "render": cmd_render}[a.command](a)
    except Refused as e:
        say(f"error: {e}")
        return 1
    except KeyboardInterrupt:
        say("")
        say("stopped by the operator. Run the same command again to resume.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
