#!/usr/bin/env python3
"""The independent verifier of carrydown releases. It runs in the tooling repository's own Actions
environment, from a checkout pinned to the commit the enrollment names, with its own credential. Standard
library only (the one outside tool is openssl, which signs the App's short-lived token).

What it is
  A program the proposed change cannot modify. It imports only from the scripts folder of its own pinned
  checkout (the folder next to this one). It never imports, executes, renders or builds anything from
  an engineering or staging pull request. It reads pull request content only as API data, and it posts
  one check per pull request, with identifiers and fixed reason codes and nothing else.

Commands
  scan        the polling loop of D11 over every enrolled repository: list every open pull request, move
              the verifier's check to in_progress, evaluate, reread the inputs, post the result.
              Needs --policy-file and --policy-commit (the launcher's checkout of the tooling
              repository's protected default branch, passed as data) and, in the environment,
              CARRYDOWN_APP_ID and CARRYDOWN_APP_PRIVATE_KEY (secrets of the tooling repository only).
              Exit 0 when the scan was complete, 1 when it was not.
  check-pr    evaluate one pull request and print the verdict; posts nothing. For an administrator
              who wants to see why a check failed. Needs the same environment.
  ruleset     print the reference ruleset (engineering or staging) with the App's integration id filled in.
  digests     read an enrollment file and print, for each repository, the enrollment_id and policy_sha256 it
              should carry, and whether the file already holds them. Run it after every edit of an entry.
  code-sha    print the commit of the checkout this program runs from, after checking that the checkout
              is clean.

Policy and code are separate checkouts. The policy is the enrollment file at the head of the tooling
repository's protected default branch. The code is this checkout at the commit the policy pins as
verifier_sha. The verifier refuses a policy that is not that head (policy-revision-mismatch) and a
checkout that is not that commit or not clean (verifier-code-mismatch).

Examples
  python3 -I verifier/verify_release.py scan --policy-file policy/enrollment.yaml --policy-commit <sha>
  python3 verifier/verify_release.py ruleset --kind staging --app-id 123456
  python3 verifier/verify_release.py --help
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
# The scripts of this checkout come first and nothing else is searched for them. Under python -I the
# current folder is not on the path at all.
sys.path.insert(0, str(SCRIPTS))

import carrydown_lib as L  # noqa: E402
import github_client as G  # noqa: E402
import release_github as RGH  # noqa: E402
import release_scan as S  # noqa: E402
import release_schema as RS  # noqa: E402
import release_verify as V  # noqa: E402

PINNED_MODULES = (L, G, RGH, S, RS, V)
APP_PERMISSIONS = {"contents": "read", "pull_requests": "read", "checks": "write", "metadata": "read"}
RULESETS = {"engineering": "ruleset-engineering.json", "staging": "ruleset-staging.json"}


class VerifierError(Exception):
    """A refusal with a fixed reason code. The text names no value from the data."""

    def __init__(self, code, text):
        super().__init__(text)
        self.code = code
        self.text = text


def fail(code, text):
    raise VerifierError(code, text)


# ---------------------------------------------------------------------------
# The pinned code
# ---------------------------------------------------------------------------

def pinned_import_problem():
    """None when every carrydown module in use was loaded from the scripts folder next to this program,
    else a plain description. Guards against a module of the same name found elsewhere on the path."""
    here = os.path.realpath(str(SCRIPTS))
    for module in PINNED_MODULES:
        where = os.path.realpath(getattr(module, "__file__", "") or "")
        if os.path.dirname(where) != here:
            return f"{module.__name__} was not loaded from the pinned scripts folder"
    return None


def _git(args, folder, runner=subprocess.run):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return runner(["git", "-c", "core.fsmonitor=false", "-C", str(folder)] + list(args), capture_output=True, text=True, env=env, timeout=60)


def detect_code_sha(code_dir, runner=subprocess.run):
    """The commit of the code checkout, after proving the checkout is exactly that commit: no modified,
    deleted or untracked file. Raises verifier-code-mismatch otherwise."""
    try:
        head = _git(["rev-parse", "HEAD"], code_dir, runner)
        status = _git(["status", "--porcelain", "--untracked-files=all"], code_dir, runner)
    except (OSError, subprocess.SubprocessError):
        fail("verifier-code-mismatch", "the code checkout cannot be inspected")
    sha = (head.stdout or "").strip()
    if head.returncode != 0 or len(sha) not in (40, 64) or any(c not in "0123456789abcdef" for c in sha):
        fail("verifier-code-mismatch", "the code checkout has no readable commit")
    if status.returncode != 0 or (status.stdout or "").strip():
        fail("verifier-code-mismatch", "the code checkout differs from its commit")
    return sha


# ---------------------------------------------------------------------------
# The App credential
# ---------------------------------------------------------------------------

def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def openssl_sign(private_key_pem, data, runner=subprocess.run):
    """RS256 signature of data. The key goes to a private temporary file for the length of the call."""
    folder = tempfile.mkdtemp(prefix="carrydown-key-")
    path = os.path.join(folder, "key.pem")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(private_key_pem)
        done = runner(["openssl", "dgst", "-sha256", "-sign", path], input=data, capture_output=True, timeout=30)
        if done.returncode != 0 or not done.stdout:
            fail("evidence-unavailable", "the App key could not sign the token request")
        return done.stdout
    except (OSError, subprocess.SubprocessError):
        fail("evidence-unavailable", "the App key could not sign the token request")
    finally:
        try:
            os.remove(path)
            os.rmdir(folder)
        except OSError:
            pass


def app_jwt(app_id, private_key_pem, now=None, sign=openssl_sign):
    """The short-lived JSON Web Token that proves the App's identity: valid for ten minutes at most."""
    issued = int(time.time() if now is None else now)
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = _b64(json.dumps({"iat": issued - 60, "exp": issued + 540, "iss": str(app_id)}, separators=(",", ":")).encode())
    signing_input = f"{header}.{claims}".encode("ascii")
    return f"{header}.{claims}.{_b64(sign(private_key_pem, signing_input))}"


def mint_installation_token(api, app_id, private_key_pem, repositories, now=None, sign=openssl_sign, factory=G.GitHub):
    """A short-lived installation token for exactly these repositories (owner/name), with only the
    permissions the verifier needs. All must belong to one installation. Returns the token."""
    app = factory(app_jwt(app_id, private_key_pem, now, sign), api=api)
    installs = set()
    try:
        for name in repositories:
            installs.add(app.rest("GET", f"/repos/{name}/installation")["id"])
        if len(installs) != 1:
            fail("setup-not-verified", "the enrolled repositories belong to more than one App installation")
        made = app.rest("POST", f"/app/installations/{installs.pop()}/access_tokens",
                        {"repositories": sorted({n.split("/", 1)[1] for n in repositories}), "permissions": dict(APP_PERMISSIONS)})
    except G.GitHubError:
        fail("evidence-unavailable", "the App token could not be requested")
    return made["token"]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def read_policy(path, commit):
    if not commit or len(commit) not in (40, 64):
        fail("policy-revision-mismatch", "--policy-commit must be a full commit id")
    try:
        return Path(path).read_bytes()
    except OSError:
        fail("policy-pointer-mismatch", "the policy file cannot be read")


def run_scan(policy_bytes, policy_commit, tooling, code_sha, reader, publisher, host="github.com", clock=None):
    """The scan, with the reader and the publisher given. Returns the ScanReport. Refuses a code checkout
    that is the policy commit, or that no enrollment pins."""
    if code_sha == policy_commit:
        fail("verifier-code-mismatch", "the code checkout must be an earlier commit than the policy")
    enrollments = V.capture_enrollments(reader, tooling, policy_commit, policy_bytes, parse=L.loads, host=host)
    mine = [e for e in enrollments if e.entry["verifier_sha"] == code_sha]
    if enrollments and not mine:
        fail("verifier-code-mismatch", "no enrollment pins this verifier commit")
    return S.scan(reader, publisher, enrollments, code_sha=code_sha, clock=clock)


def _environment():
    app_id = os.environ.get("CARRYDOWN_APP_ID", "").strip()
    key = os.environ.get("CARRYDOWN_APP_PRIVATE_KEY", "")
    if not app_id.isdigit() or "PRIVATE KEY" not in key:
        fail("evidence-unavailable", "CARRYDOWN_APP_ID and CARRYDOWN_APP_PRIVATE_KEY are not set")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    from urllib.parse import urlparse
    return int(app_id), key, api, (urlparse(server).hostname or "github.com")


def _live(args, policy_bytes):
    """(reader, publisher, host, tooling) built from the environment and the policy file. The token is
    minted for the tooling repository and every repository the policy enrolls."""
    app_id, key, api, host = _environment()
    tooling = args.tooling or os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in tooling:
        fail("policy-pointer-mismatch", "--tooling must be owner/name")
    doc = L.loads(policy_bytes.decode("utf-8"))
    names = {tooling}
    for row in doc.get("repositories") or []:
        for field in ("repository", "staging_repository"):
            if isinstance(row, dict) and isinstance(row.get(field), str):
                names.add(row[field])
    token = mint_installation_token(api, app_id, key, sorted(names))
    gh = G.GitHub(token, api=api)
    return RGH.GitHubEvidenceReader(gh, host=host), RGH.GitHubCheckPublisher(gh, app_id), host, tooling


def cmd_scan(args):
    problem = pinned_import_problem()
    if problem:
        fail("verifier-code-mismatch", problem)
    code_sha = detect_code_sha(args.code_dir)
    policy = read_policy(args.policy_file, args.policy_commit)
    reader, publisher, host, tooling = _live(args, policy)
    report = run_scan(policy, args.policy_commit, tooling, code_sha, reader, publisher, host=host)
    for line in report_lines(report):
        print(line)
    if args.record_file:
        Path(args.record_file).write_text(json.dumps({"health": report.health_record(), "records": report.records}, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report.complete else 1


def report_lines(report):
    """The public lines of a scan: counts, ids and reason codes only."""
    lines = [f"carrydown verifier scan: policy {str(report.policy_commit_sha)[:12]}, "
             f"{len(report.checks)} check(s) posted, {report.superseded} superseded, {report.outstanding} outstanding"]
    for c in report.checks:
        lines.append(f"  {c['kind']} repository {c['repository_id']} pull request {c['pull_request']} head {c['head_sha'][:12]}: "
                     f"{c['conclusion']}{' (' + c['code'] + ')' if c['code'] else ''}")
    for e in report.errors:
        lines.append(f"  incomplete: {e}")
    lines.append("scan-health: " + json.dumps(report.health_record(), sort_keys=True))
    return lines


def cmd_check_pr(args):
    problem = pinned_import_problem()
    if problem:
        fail("verifier-code-mismatch", problem)
    code_sha = detect_code_sha(args.code_dir)
    policy = read_policy(args.policy_file, args.policy_commit)
    reader, _, host, tooling = _live(args, policy)
    enrollments = V.capture_enrollments(reader, tooling, args.policy_commit, policy, parse=L.loads, host=host)
    for e in enrollments:
        if e.entry["repository"].casefold() == args.repository.casefold():
            result = S.evaluate(reader, e, args.kind, args.pull, verifier_sha=code_sha)
            print(result.title)
            print(result.summary)
            return 0 if result.conclusion == "success" else 1
    fail("policy-pointer-mismatch", "the repository is not enrolled")


def cmd_ruleset(args):
    path = HERE / RULESETS[args.kind]
    data = json.loads(path.read_text(encoding="utf-8"))
    for rule in data["rules"]:
        if rule["type"] == "required_status_checks":
            for check in rule["parameters"]["required_status_checks"]:
                check["integration_id"] = args.app_id
    print(json.dumps(data, indent=2))
    return 0


def cmd_digests(args):
    """The identity and the policy digest each entry of an enrollment file should carry. Reads one file."""
    try:
        doc = L.loads(Path(args.policy_file).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, L.YamlError):
        fail("policy-pointer-mismatch", "the enrollment file cannot be read")
    if not isinstance(doc, dict) or not isinstance(doc.get("repositories"), list):
        fail("policy-pointer-mismatch", "enrollment.yaml has an unknown format")
    clean = True
    for row in doc["repositories"]:
        if not isinstance(row, dict) or not isinstance(row.get("repository_id"), int):
            fail("policy-pointer-mismatch", "an entry has no numeric repository_id")
        want_id = V.enrollment_id_of(doc.get("host"), doc.get("tooling_repository_id"), row["repository_id"])
        want_policy = V.policy_sha256_of(dict(row, enrollment_id=want_id))
        same = row.get("enrollment_id") == want_id and row.get("policy_sha256") == want_policy
        clean = clean and same
        print(f"repository {row['repository_id']}: enrollment_id {want_id}, policy_sha256 {want_policy} ({'matches the file' if same else 'differs from the file'})")
    return 0 if clean else 1


def cmd_code_sha(args):
    print(detect_code_sha(args.code_dir))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    def code_dir(p):
        p.add_argument("--code-dir", default=str(HERE.parent), help="the code checkout (default: the folder above this program)")

    def policy(p):
        p.add_argument("--policy-file", required=True, help="enrollment.yaml from the launcher's checkout of the protected default branch")
        p.add_argument("--policy-commit", required=True, help="the full commit id of that checkout, which must be the branch head")
        p.add_argument("--tooling", help="the tooling repository, owner/name (default: GITHUB_REPOSITORY)")
    p = sub.add_parser("scan", help="the polling loop: reevaluate every open pull request and post one check each")
    policy(p)
    code_dir(p)
    p.add_argument("--record-file", help="write the private input records and the scan health here as JSON")
    p = sub.add_parser("check-pr", help="evaluate one pull request and print the verdict. Posts nothing")
    policy(p)
    code_dir(p)
    p.add_argument("--repository", required=True, help="the enrolled repository, owner/name (the staging repository for --kind staging is found by number)")
    p.add_argument("--kind", choices=("engineering", "staging"), default="engineering")
    p.add_argument("--pull", type=int, required=True, help="the pull request number")
    p = sub.add_parser("ruleset", help="print a reference ruleset with the App's integration id filled in")
    p.add_argument("--kind", choices=sorted(RULESETS), required=True)
    p.add_argument("--app-id", type=int, required=True, help="the verifier App's numeric id (verifier_app_id in the enrollment)")
    p = sub.add_parser("digests", help="print the enrollment_id and policy_sha256 each entry of an enrollment file should carry")
    p.add_argument("--policy-file", required=True, help="the enrollment file to read")
    p = sub.add_parser("code-sha", help="print the commit of the code checkout, after checking that it is clean")
    code_dir(p)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    commands = {"scan": cmd_scan, "check-pr": cmd_check_pr, "ruleset": cmd_ruleset, "digests": cmd_digests, "code-sha": cmd_code_sha}
    try:
        return commands[args.command](args)
    except VerifierError as e:
        print(f"{e.code}: {e.text}", file=sys.stderr)
        return 1
    except RS.SchemaError as e:
        print(f"{e.code}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
