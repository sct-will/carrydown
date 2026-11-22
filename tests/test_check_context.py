"""The engineers' check (work package 5): templates/dev-skill/scripts/check_context.py.

They cover local validity (bundle bytes, sidecar, the specification's citations, an active receipt),
the six messages and their exit codes, the receipt-based check of the specification and the shared
files (exit 14 and 15), the decision overlay and the approved delta, freshness against a fake origin
(a bare git repository on disk), offline grace and its record, expiry, the replacement and withdrawal
of a release, and that no message holds withheld text, a private path or a name. Tests tagged [G4] are negative tests of the
specification (Part G): the consumer side of the expired, withdrawn and superseded behavior and of the offline
grace rule. tests/test_negative_release.py collects them into the G4 group. A synthetic receipt is built with the
release_schema helpers. No token and no network are used: the only fetch is from a folder on disk.
Run from the repository root: python -m unittest discover -s tests -v
"""
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import carrydown_lib as L  # noqa: E402
import compile_bundles as CB  # noqa: E402
import decision_overlay as DO  # noqa: E402
import release_schema as RS  # noqa: E402

TEMPLATE = ROOT / "templates" / "dev-skill" / "scripts" / "check_context.py"
FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
SAMPLE = ROOT / "sample" / "expense-approvals"
GENERATED = SAMPLE / "docs" / "dev" / "skills" / "expense-approvals-dev" / "scripts" / "check_context.py"
HAS_GIT = shutil.which("git") is not None

spec = importlib.util.spec_from_file_location("check_context_under_test", str(TEMPLATE))
CC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CC)
SKILL_REL = "docs/dev/skills/expense-approvals-dev"
CC.SKILL_PATH = SKILL_REL      # a generated copy has this filled in. The template alone does not know it

UTC = dt.timezone.utc
NOW = dt.datetime(2027, 2, 1, 12, 0, 0, tzinfo=UTC)
TIME = "2027-01-20T14:03:00Z"
FIRST = "carrydown: no approved context for WI-06"
STALE = "carrydown: the approved context for WI-06 is stale"


def H_FILE(path):
    return hashlib.sha256(PROJECT[path]).hexdigest()


def reason_line(code, policy=None):
    """The second line of a stale message: the plain words, then the fixed code. The words of body-changed follow the
    edit policy, the generated one unless policy names another."""
    with mock.patch.object(CC, "ENGINEER_EDITS", policy or CC.ENGINEER_EDITS):
        return f"reason: {CC.reason_text(code)} ({code})"
CITES = "carrydown: WI-06 cites an obligation that is not in its approved context"
RESTRICTED = "carrydown: WI-06 has a restricted destination that this project does not publish"
SPEC_MISMATCH = "carrydown: the specification for WI-06 does not match its approved release"
MIXED = "carrydown: the approved inputs for WI-06 come from more than one release"
OFFLINE_WARNING = "freshness not confirmed; within offline grace"
KIND_LINE = {code: first.format(id="<ID>") for code, first, _ in CC.KINDS.values()}
SPEC_FILE = "docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md"


def H(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def compile_fixture():
    plan, problems = L.load_plan(FIXTURE / "docs" / "spec" / "plan.yaml", FIXTURE)
    assert problems == [], problems
    return CB.compile_bundles(plan, FIXTURE / "docs" / "ground-truth", FIXTURE / "docs" / "spec")


BUNDLES = compile_fixture()


def project_files():
    """Every approved file of the fixture project that a release lists: the bundles, the released plan, the
    specifications, the specification README and the skill's two Markdown files (stand-ins)."""
    out = dict(BUNDLES)
    for path in sorted((FIXTURE / "docs" / "spec").rglob("*")):
        if path.is_file():
            out[path.relative_to(FIXTURE).as_posix()] = path.read_bytes()
    out[f"{SKILL_REL}/SKILL.md"] = b"# Skill\n\nOrient on a work item.\n"
    out[f"{SKILL_REL}/README.md"] = b"# Engineers' skill\n\nInstall it.\n"
    return out


PROJECT = project_files()
GIT_HOME = tempfile.mkdtemp(prefix="carrydown-check-context-home-")


def run_git(cwd, *args):
    """git with a clean user configuration, so nothing in the developer's own settings changes a test."""
    env = dict(os.environ, HOME=GIT_HOME, USERPROFILE=GIT_HOME, XDG_CONFIG_HOME=GIT_HOME, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    run = subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"] + [str(a) for a in args],
                         cwd=str(cwd), capture_output=True, text=True, env=env)
    if run.returncode != 0:
        raise AssertionError(f"git {' '.join(str(a) for a in args)}: {run.stderr}")
    return run.stdout.strip()


def write_receipt_file(root, rid, data):
    path = Path(root) / "docs" / "release" / f"{rid}.receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_project_files(root, files, receipts=()):
    """docs/spec from the fixture, docs/context from files, and the receipts given as (id, bytes)."""
    shutil.copytree(FIXTURE / "docs" / "spec", Path(root) / "docs" / "spec", dirs_exist_ok=True)
    for rel, data in files.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for rid, data in receipts:
        write_receipt_file(root, rid, data)


def build_receipt(files, state="active", grace=7, expires_at=None, supersedes=None, superseded_by=None, nonce="a1" * 16, created=TIME):
    """(request id, receipt bytes) for a synthetic release of files ({path: bytes} under docs/context)."""
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp)
        for rel, data in files.items():
            path = snapshot / "repo" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        manifest, release_id = RS.hash_manifest(snapshot)
    artifacts = [dict(e, path=e["path"][len("repo/"):]) for e in json.loads(manifest) if e["path"].startswith("repo/")]
    template = {
        "receipt_format": 1, "content_manifest_sha256": release_id, "created": created, "expires_at": expires_at,
        "audience": "repo-readers", "destinations": ["engineering-repo", "engineers-skill"],
        "targets": [{"id": "engineering", "host": "github.com", "repository_id": 4200, "repository": "acme/expense-approvals"}],
        "sources": [{"id": "architecture", "version": "0.3"}, {"id": "company-governance", "version": "2027.1"}],
        "artifacts": artifacts, "downstream": {"assignees": False, "capacity_summary": False, "evidence": "synthetic-only"},
        "offline_grace_days": grace, "enrollment_id": H("enrollment"),
    }
    request = {
        "request_format": 1, "release_id": release_id, "request_nonce": nonce, "created": created,
        "policy_commit_sha": "8b" * 20, "policy_sha256": H("policy"), "enrollment_id": H("enrollment"), "activate": True,
        "supersedes_request_id": supersedes, "receipt_template": template,
        "preview": {"what": "Bundles", "with_whom": "Repository readers", "where": "The engineering repository", "remains_private": "Staffing records"},
        "detector_exceptions": [],
    }
    request["request_sha256"] = RS.hash_request(request)
    rid = request["request_sha256"]
    verified = RS.RequestState(rid, state, H("event " + rid + state), superseded_by, supersedes)
    return rid, RS.project_receipt(request, manifest, verified, RS.VerifiedApproval(rid, "local-owner", False))


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-check-context-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        patch = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home), "GIT_TERMINAL_PROMPT": "0"})
        patch.start()
        self.addCleanup(patch.stop)
        self.files = dict(PROJECT)

    def git(self, cwd, *args):
        return run_git(cwd, *args)

    def write_project(self, root, files=None, receipts=()):
        write_project_files(root, files or self.files, receipts)

    def write_receipt(self, root, rid, data):
        write_receipt_file(root, rid, data)

    def run_check(self, root, argument="WI-06", now=NOW, refresh=True):
        return CC.check(Path(root), argument, now=now, refresh_allowed=refresh)


class LocalProject(Base):
    """A checkout with no git: only the local checks and --no-refresh behavior."""

    def setUp(self):
        super().setUp()
        self.root = self.base / "project"
        self.rid, self.receipt = build_receipt(self.files)
        self.write_project(self.root, receipts=[(self.rid, self.receipt)])


class LocalValidityTests(LocalProject):
    def test_no_bundle_prints_the_first_message_and_nothing_from_another_bundle(self):
        (self.root / "docs/context/wi-03.md").unlink()
        (self.root / "docs/context/wi-03.bundle.json").unlink()
        code, lines = self.run_check(self.root, "WI-03")
        self.assertEqual((code, lines[0]), (10, "carrydown: no approved context for WI-03"))
        self.assertEqual(lines[1:], ["Ask the plan owner to release the item."])
        text = "\n".join(lines)
        for other in ("Routing", "Approval limits", "WI-06", "docs/context", str(self.root)):
            self.assertNotIn(other, text)

    def test_an_unknown_or_unreadable_id_gets_the_first_message(self):
        for arg, shown in (("WI-99", "WI-99"), ("99", "WI-99"), ("../etc/passwd", "..etcpasswd"), ("WI-03; rm -rf x", "WI-03rm-rfx"), ("", "(no id)")):
            code, lines = self.run_check(self.root, arg)
            self.assertEqual((code, lines[0]), (10, f"carrydown: no approved context for {shown}"), arg)

    def test_id_forms(self):
        for arg in ("WI-06", "wi-06", "6", "06", "WI6", "wi-6", "  WI-06  "):
            self.assertEqual(CC.item_number(arg), 6, arg)
            self.assertEqual(CC.shown_id(arg, 6), "WI-06")
        for arg in ("WI-", "-6", "WI-06-1", "x6", "0x6", "٦"):
            self.assertIsNone(CC.item_number(arg), arg)

    def test_a_changed_bundle_byte_fails_integrity(self):
        md = self.root / "docs/context/wi-06.md"
        md.write_bytes(md.read_bytes().replace(b"25,000.00", b"26,000.00", 1))
        code, lines = self.run_check(self.root)
        self.assertEqual((code, lines[0]), (10, FIRST))

    def test_a_changed_sidecar_fails_integrity(self):
        path = self.root / "docs/context/wi-06.bundle.json"
        side = json.loads(path.read_text(encoding="utf-8"))
        side["content_sha256"] = "0" * 64
        path.write_bytes(RS.canonical_json(side))
        self.assertEqual(self.run_check(self.root)[0], 10)

    def test_a_sidecar_that_is_not_one_fails_integrity(self):
        path = self.root / "docs/context/wi-06.bundle.json"
        good = json.loads(path.read_text(encoding="utf-8"))
        for bad in (b"not json", b"[]", b'{"bundle_format":1,"bundle_format":1}', b"\xff\xfe",
                    RS.canonical_json(dict(good, work_item="WI-03")), RS.canonical_json(dict(good, bundle_format=2)),
                    RS.canonical_json(dict(good, bundle_format=True)), RS.canonical_json(dict(good, content_sha256="abc")),
                    RS.canonical_json(dict(good, obligations=[{"source": 1, "section": "3.5"}])),
                    RS.canonical_json(dict(good, restricted_destination="yes"))):
            path.write_bytes(bad)
            self.assertEqual(self.run_check(self.root)[0], 10, bad[:40])

    def test_a_bundle_that_is_a_link_is_refused(self):
        if os.name != "posix":
            self.skipTest("symbolic links need a POSIX file system")
        md = self.root / "docs/context/wi-06.md"
        elsewhere = self.base / "elsewhere.md"
        elsewhere.write_bytes(md.read_bytes())
        md.unlink()
        md.symlink_to(elsewhere)
        self.assertEqual(self.run_check(self.root)[0], 10)

    def test_a_bundle_without_a_receipt_has_no_approved_context(self):
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        self.assertEqual(self.run_check(self.root)[0], 10)

    def test_a_receipt_that_lists_other_bytes_does_not_cover_the_bundle(self):
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        other = dict(self.files)
        other["docs/context/wi-06.md"] = other["docs/context/wi-06.md"] + b"\n"
        rid, data = build_receipt(other)
        self.write_receipt(self.root, rid, data)
        self.assertEqual(self.run_check(self.root)[0], 10)

    def test_a_receipt_with_the_wrong_name_or_shape_is_ignored(self):
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        (self.root / "docs/release" / f"{'f' * 64}.receipt.json").write_bytes(self.receipt)     # name is not its request id
        (self.root / "docs/release" / "notes.receipt.json").write_bytes(self.receipt)
        self.assertEqual(self.run_check(self.root)[0], 10)

    def test_a_locally_superseded_or_withdrawn_receipt_is_stale(self):
        for state, reason in (("superseded", "superseded"), ("withdrawn", "withdrawn")):
            rid, data = build_receipt(self.files, state=state, superseded_by=H("next") if state == "superseded" else None)
            self.assertEqual(rid, self.rid)
            self.write_receipt(self.root, rid, data)
            code, lines = self.run_check(self.root)
            self.assertEqual((code, lines[0], lines[1]), (11, STALE, reason_line(reason)), state)

    def test_the_spec_citing_a_section_the_bundle_lacks_is_the_third_message(self):
        spec_path = self.root / SPEC_FILE
        text = spec_path.read_text(encoding="utf-8")
        for line in ("- architecture section 9.9, Missing", "- other-source section 1.1",
                     "- [Company governance policy, section 3.1, Records](../../ground-truth/company-governance.md#31-retention)"):
            spec_path.write_bytes((text.replace("## References\n", "## References\n\n" + line + "\n", 1)).encode("utf-8"))
            code, lines = self.run_check(self.root)
            self.assertEqual((code, lines[0]), (12, CITES), line)
            self.assertEqual(lines[1:], ["Ask the plan owner. Do not guess the rule."])

    def test_a_citation_the_bundle_holds_passes_in_either_form(self):
        spec_path = self.root / SPEC_FILE
        text = spec_path.read_text(encoding="utf-8")
        cited = CC.spec_citations(self.root, "WI-06", {"architecture", "company-governance"})
        self.assertEqual(cited, [("architecture", "3.5"), ("architecture", "4.1"), ("architecture", "4.2"), ("architecture", "7.1"),
                                 ("company-governance", "1.5"), ("company-governance", "2.3")])
        spec_path.write_bytes((text.replace("## References\n", "## References\n\n- company-governance section 2.3, Approval limits\n- architecture section 3.5\n", 1)).encode("utf-8"))
        self.assertIn(("company-governance", "2.3"), CC.spec_citations(self.root, "WI-06", set()))
        # a link whose file name is not a source of the bundle cannot be read as a citation, so it is not a finding
        spec_path.write_bytes((text.replace("## References\n", "## References\n\n- [Section 1.1](../../ground-truth/unrelated.md#x)\n", 1)).encode("utf-8"))
        self.assertEqual(CC.spec_citations(self.root, "WI-06", {"architecture"})[0:1], [("architecture", "3.5")])
        self.assertNotIn("1.1", [n for _, n in CC.spec_citations(self.root, "WI-06", {"architecture"})])

    def test_without_a_fetch_and_without_a_record_the_context_is_stale(self):
        code, lines = self.run_check(self.root, refresh=False)
        self.assertEqual((code, lines[0], lines[1]), (11, STALE, reason_line("could-not-refresh")))
        self.assertEqual(lines[2:], ["Ask the plan owner to re-release, or connect and refresh."])
        self.assertFalse((self.root / ".carrydown").exists(), "a refused check records nothing")

    def test_a_placeholder_for_a_restricted_destination_prints_the_fourth_message_once_it_is_current(self):
        side = json.loads(self.files["docs/context/wi-06.bundle.json"])
        side["restricted_destination"] = True
        files = dict(self.files, **{"docs/context/wi-06.bundle.json": RS.canonical_json(side)})
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt(files)
        self.write_project(self.root, files=files, receipts=[(rid, data)])
        # not current: with no fetch and no record it is stale, not a placeholder message
        self.assertEqual(self.run_check(self.root, refresh=False)[1][0], STALE)
        with mock.patch.object(CC, "refresh", return_value=("fresh", CC.parse_receipt(data), "a" * 40)):
            code, lines = self.run_check(self.root)
        self.assertEqual((code, lines[0]), (13, RESTRICTED))
        self.assertEqual(lines[1:], ["The owner's approved instruction is in docs/context/wi-06.md.", "Follow the owner's approved instruction."])
        # another id is not confirmed to exist
        self.assertEqual(self.run_check(self.root, "WI-99")[1][0], "carrydown: no approved context for WI-99")


class JudgeTests(unittest.TestCase):
    """The pure decision on the receipts of a fetched commit."""

    def setUp(self):
        self.files = {p: (hashlib.sha256(d).hexdigest(), len(d)) for p, d in BUNDLES.items() if p.startswith("docs/context/wi-06")}

    def receipt(self, **kw):
        rid, data = build_receipt({p: BUNDLES[p] for p in self.files}, **kw)
        return CC.parse_receipt(data)

    def test_an_active_receipt_that_lists_the_files_is_fresh(self):
        r = self.receipt()
        self.assertEqual(CC.judge_fetched({}, {r["request_id"]: r}, self.files), ("fresh", r))

    def test_an_older_local_active_receipt_never_replaces_a_newer_terminal_one(self):
        active = self.receipt()
        ended = self.receipt(state="withdrawn")
        self.assertEqual(active["request_id"], ended["request_id"])
        merged = CC.merge({active["request_id"]: ended}, {active["request_id"]: active})
        self.assertEqual(merged[ended["request_id"]]["state"], "withdrawn")
        # the fetched commit still says active, the checkout says withdrawn: the checkout's terminal state stands
        self.assertEqual(CC.judge_fetched({ended["request_id"]: ended}, {active["request_id"]: active}, self.files), ("stale", "withdrawn"))
        # the other way round, a terminal state fetched replaces the active receipt in the checkout
        self.assertEqual(CC.judge_fetched({active["request_id"]: active}, {ended["request_id"]: ended}, self.files), ("stale", "withdrawn"))

    def test_a_replacement_that_lists_the_same_bytes_keeps_the_context_fresh(self):
        old = self.receipt(state="superseded", superseded_by=H("new"))
        new = self.receipt(nonce="b2" * 16, supersedes=old["request_id"])
        # the replacement's request id is what supersedes names; build it consistently
        old = self.receipt(state="superseded", superseded_by=new["request_id"])
        fetched = {old["request_id"]: old, new["request_id"]: new}
        verdict, got = CC.judge_fetched({old["request_id"]: self.receipt()}, fetched, self.files)
        self.assertEqual((verdict, got["request_id"]), ("fresh", new["request_id"]))

    def test_a_replacement_with_other_bytes_makes_the_old_bytes_stale(self):
        changed = {p: BUNDLES[p] for p in self.files}
        changed["docs/context/wi-06.md"] += b"\nNew rule.\n"
        _, data = build_receipt(changed, nonce="b2" * 16)
        new = CC.parse_receipt(data)
        old = self.receipt(state="superseded", superseded_by=new["request_id"])
        self.assertEqual(CC.judge_fetched({}, {old["request_id"]: old, new["request_id"]: new}, self.files), ("stale", "superseded"))

    def test_active_receipts_for_other_bytes_are_a_digest_mismatch_and_no_receipt_is_not_found(self):
        changed = {p: BUNDLES[p] for p in self.files}
        changed["docs/context/wi-06.md"] += b"\nNew rule.\n"
        _, data = build_receipt(changed)
        other = CC.parse_receipt(data)
        self.assertEqual(CC.judge_fetched({}, {other["request_id"]: other}, self.files), ("stale", "sha256-mismatch"))
        self.assertEqual(CC.judge_fetched({}, {}, self.files), ("stale", "approval-not-found"))


@unittest.skipUnless(HAS_GIT, "git is needed for the fake origin")
class OriginTests(Base):
    """A bare repository on disk stands in for origin; the engineer's checkout is a clone of it."""

    @classmethod
    def setUpClass(cls):
        cls.world = Path(tempfile.mkdtemp(prefix="carrydown-check-context-world-")).resolve()
        origin = cls.world / "origin.git"
        run_git(cls.world, "init", "--bare", "-q", origin)
        run_git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
        pub = cls.world / "publisher"
        run_git(cls.world, "clone", "-q", origin, pub)
        run_git(pub, "checkout", "-q", "-b", "main")
        cls.rid, cls.receipt = build_receipt(PROJECT)
        write_project_files(pub, PROJECT, [(cls.rid, cls.receipt)])
        run_git(pub, "add", "-A")
        run_git(pub, "commit", "-q", "-m", "first release")
        run_git(pub, "push", "-q", "origin", "HEAD:main")
        run_git(cls.world, "clone", "-q", origin, cls.world / "engineer")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.world, ignore_errors=True)

    def setUp(self):
        super().setUp()
        shutil.copytree(self.world, self.base / "world", symlinks=True)
        self.origin = self.base / "world" / "origin.git"
        self.pub = self.base / "world" / "publisher"
        self.eng = self.base / "world" / "engineer"
        for clone in (self.pub, self.eng):
            self.git(clone, "remote", "set-url", "origin", self.origin)
        self.rid, self.receipt = self.__class__.rid, self.__class__.receipt

    def publish(self, message="change", branch="main"):
        self.git(self.pub, "add", "-A")
        self.git(self.pub, "commit", "-q", "-m", message)
        self.git(self.pub, "push", "-q", "origin", f"HEAD:{branch}")

    def origin_head(self):
        return self.git(self.origin, "rev-parse", "refs/heads/main")

    def cache(self):
        return json.loads((self.eng / ".carrydown" / "cache" / "last-refresh").read_text(encoding="utf-8"))

    def take_origin_away(self):
        shutil.move(str(self.origin), str(self.base / "origin-gone.git"))

    def refresh_once(self, now=NOW):
        code, lines = self.run_check(self.eng, now=now)
        self.assertEqual(code, 0, lines)

    def assert_clean(self, lines):
        text = "\n".join(lines)
        for forbidden in (str(self.base), str(self.eng), "Sole approver", "Routing", "example-approver", "Harbor", "company-governance", "ground-truth/architecture"):
            self.assertNotIn(forbidden, text)


class FreshnessTests(OriginTests):
    def test_a_good_fetch_is_fresh_and_is_recorded(self):
        code, lines = self.run_check(self.eng)
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], "carrydown: approved context for WI-06 is ready")
        self.assertEqual(lines[1], "Read docs/context/wi-06.md. Do not open docs/ground-truth/ or any source.")
        self.assertEqual(lines[2], f"baseline: request {self.rid}, specification {H_FILE(SPEC_FILE)}")
        self.assertEqual(len(lines), 3, "the first check of an item has no previous baseline, so no delta")
        cache = self.cache()
        item = cache.pop("items")["WI-06"]
        self.assertEqual(cache, {"cache_format": 1, "repository": CC.origin_identity(self.eng), "commit": self.origin_head(),
                                 "request_id": self.rid, "time": "2027-02-01T12:00:00Z"})
        self.assertEqual((item["request_id"], item["overlay_sha256"], item["overlays"]), (self.rid, None, {}))
        self.assertEqual(item["files"][SPEC_FILE], H_FILE(SPEC_FILE))
        self.assertIn("docs/context/wi-06.md", item["files"])
        self.assertIn(f"{SKILL_REL}/SKILL.md", item["files"])
        self.assertTrue(CC.origin_identity(self.eng).endswith("origin.git") or "origin" in CC.origin_identity(self.eng))

    def test_a_superseded_release_on_the_default_branch_is_stale_after_the_refresh(self):
        """[G4] A superseded release is refused by the engineers' check after a refresh of the default branch."""
        rid, data = build_receipt(self.files, state="superseded", superseded_by=H("replacement"))
        self.assertEqual(rid, self.rid)
        self.write_receipt(self.pub, rid, data)
        self.publish("supersede")
        code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[0], lines[1]), (11, STALE, reason_line("superseded")))
        self.assert_clean(lines)
        self.assertFalse((self.eng / ".carrydown").exists(), "no refresh is recorded for a stale result")

    def test_a_withdrawn_release_on_the_default_branch_is_stale(self):
        """[G4] A withdrawn release is refused by the engineers' check after a refresh."""
        _, data = build_receipt(self.files, state="withdrawn")
        self.write_receipt(self.pub, self.rid, data)
        self.publish("withdraw")
        code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[0], lines[1]), (11, STALE, reason_line("withdrawn")))

    def test_a_replacement_that_lists_the_same_bytes_is_fresh_and_the_record_names_the_new_request(self):
        new_rid, new_data = build_receipt(self.files, nonce="b2" * 16, supersedes=self.rid)
        _, old_data = build_receipt(self.files, state="superseded", superseded_by=new_rid)
        self.write_receipt(self.pub, self.rid, old_data)
        self.write_receipt(self.pub, new_rid, new_data)
        self.publish("replace")
        code, lines = self.run_check(self.eng)
        self.assertEqual(code, 0, lines)
        self.assertEqual(self.cache()["request_id"], new_rid)

    def test_a_replacement_with_changed_bytes_makes_the_checkout_stale(self):
        """[G4] A replacement with other bytes supersedes the release the checkout holds, which is then stale."""
        changed = dict(self.files)
        changed["docs/context/wi-06.md"] += b"\nA new rule.\n"
        new_rid, new_data = build_receipt(changed, nonce="b2" * 16, supersedes=self.rid)
        _, old_data = build_receipt(self.files, state="superseded", superseded_by=new_rid)
        self.write_receipt(self.pub, self.rid, old_data)
        self.write_receipt(self.pub, new_rid, new_data)
        self.publish("replace with new text")
        self.assertEqual(self.run_check(self.eng)[1][:2], [STALE, reason_line("superseded")])

    def test_the_default_branch_listing_other_bytes_is_a_digest_mismatch(self):
        changed = dict(self.files)
        changed["docs/context/wi-06.md"] += b"\nA new rule.\n"
        new_rid, new_data = build_receipt(changed, nonce="b2" * 16)
        (self.pub / "docs" / "release" / f"{self.rid}.receipt.json").unlink()
        self.write_receipt(self.pub, new_rid, new_data)
        self.publish("other bytes")
        self.assertEqual(self.run_check(self.eng)[1][:2], [STALE, reason_line("sha256-mismatch")])

    def test_fetching_another_branch_is_not_freshness(self):
        self.git(self.pub, "checkout", "-q", "-b", "feature")
        self.git(self.pub, "push", "-q", "origin", "feature")                  # feature still holds the receipt
        self.git(self.pub, "checkout", "-q", "main")
        (self.pub / "docs" / "release" / f"{self.rid}.receipt.json").unlink()
        self.publish("main drops the receipt")
        code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[0], lines[1]), (11, STALE, reason_line("approval-not-found")))

    def test_the_default_branch_is_found_when_origin_head_is_not_set_locally(self):
        self.git(self.eng, "remote", "set-head", "origin", "-d")
        self.assertEqual(CC.default_branch(self.eng), "main")
        self.assertEqual(self.run_check(self.eng)[0], 0)

    def test_a_branch_name_that_could_be_an_option_is_refused(self):
        with mock.patch.object(CC, "git", return_value=(0, b"refs/remotes/origin/--upload-pack=x\n")):
            self.assertIsNone(CC.default_branch(self.eng))

    def test_an_expired_release_is_stale_on_the_local_clock(self):
        """[G4] Local expiry: the check refuses an expired release on the local clock."""
        rid, data = build_receipt(self.files, expires_at="2027-02-01T12:00:00Z", nonce="c3" * 16)
        (self.pub / "docs" / "release" / f"{self.rid}.receipt.json").unlink()
        self.write_receipt(self.pub, rid, data)
        self.publish("expiring release")
        self.git(self.eng, "pull", "-q")
        before = NOW - dt.timedelta(seconds=1)
        self.assertEqual(self.run_check(self.eng, now=before)[0], 0)
        code, lines = self.run_check(self.eng, now=NOW)
        self.assertEqual((code, lines[0], lines[1]), (11, STALE, reason_line("expired")))
        code, lines = self.run_check(self.eng, now=NOW + dt.timedelta(days=30))
        self.assertEqual(lines[1], reason_line("expired"))

    def test_the_check_writes_only_the_cache(self):
        before = {p: p.read_bytes() for p in self.eng.rglob("*") if p.is_file() and ".git" not in p.parts}
        self.refresh_once()
        after = {p: p.read_bytes() for p in self.eng.rglob("*") if p.is_file() and ".git" not in p.parts}
        self.assertEqual(sorted(set(after) - set(before)), [self.eng / ".carrydown" / "cache" / "last-refresh"])
        self.assertEqual({p: d for p, d in before.items()}, {p: after[p] for p in before})


class OfflineGraceTests(OriginTests):
    def test_origin_unreachable_inside_the_grace_period_passes_with_a_warning(self):
        """[G4] Offline grace: with the origin unreachable inside the declared grace period, the check passes with a warning."""
        self.refresh_once()
        self.take_origin_away()
        for days in (0, 3, 7):
            code, lines = self.run_check(self.eng, now=NOW + dt.timedelta(days=days))
            self.assertEqual(code, 0, (days, lines))
            self.assertEqual(lines[0], "carrydown: approved context for WI-06 is ready")
            self.assertIn("warning: " + OFFLINE_WARNING, lines)

    def test_origin_unreachable_outside_the_grace_period_is_stale_with_could_not_refresh(self):
        """[G4] Offline grace: outside the declared grace period the check is stale with could-not-refresh."""
        self.refresh_once()
        self.take_origin_away()
        code, lines = self.run_check(self.eng, now=NOW + dt.timedelta(days=7, seconds=1))
        self.assertEqual((code, lines[0], lines[1]), (11, STALE, reason_line("could-not-refresh")))
        self.assert_clean(lines)

    def test_a_refusal_after_the_grace_period_does_not_extend_it(self):
        self.refresh_once()
        self.take_origin_away()
        self.run_check(self.eng, now=NOW + dt.timedelta(days=8))
        self.assertEqual(self.cache()["time"], "2027-02-01T12:00:00Z")

    def test_the_grace_period_is_the_one_in_the_receipt(self):
        (self.pub / "docs" / "release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt(self.files, grace=2, nonce="d4" * 16)
        self.write_receipt(self.pub, rid, data)
        self.publish("short grace")
        self.git(self.eng, "pull", "-q")
        self.refresh_once()
        self.take_origin_away()
        self.assertEqual(self.run_check(self.eng, now=NOW + dt.timedelta(days=2))[0], 0)
        self.assertEqual(self.run_check(self.eng, now=NOW + dt.timedelta(days=2, seconds=1))[0], 11)

    def test_a_grace_of_zero_days_never_allows_an_unconfirmed_check(self):
        (self.pub / "docs" / "release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt(self.files, grace=0, nonce="e5" * 16)
        self.write_receipt(self.pub, rid, data)
        self.publish("no grace")
        self.git(self.eng, "pull", "-q")
        self.refresh_once()
        self.take_origin_away()
        self.assertEqual(self.run_check(self.eng)[0], 11)

    def test_first_use_with_no_record_does_not_get_grace(self):
        """[G4] Offline grace: a first use with no refresh record gets no grace."""
        self.take_origin_away()
        code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[1]), (11, reason_line("could-not-refresh")))

    def test_a_missing_malformed_future_or_mismatched_record_grants_no_grace(self):
        self.refresh_once()
        good = self.cache()
        path = self.eng / ".carrydown" / "cache" / "last-refresh"
        self.take_origin_away()
        bad_records = {
            "not json": "not json\n",
            "a list": "[]\n",
            "missing field": json.dumps({k: v for k, v in good.items() if k != "commit"}),
            "extra field": json.dumps(dict(good, extra=1)),
            "future time": json.dumps(dict(good, time="2027-02-02T12:00:00Z")),
            "bad time": json.dumps(dict(good, time="yesterday")),
            "other repository": json.dumps(dict(good, repository="example.invalid/other/repo")),
            "other request": json.dumps(dict(good, request_id="f" * 64)),
            "commit not in this clone": json.dumps(dict(good, commit="9" * 40)),
            "commit not a sha": json.dumps(dict(good, commit="main")),
            "format 2": json.dumps(dict(good, cache_format=2)),
        }
        for name, text in bad_records.items():
            path.write_bytes((text).encode("utf-8"))
            code, lines = self.run_check(self.eng)
            self.assertEqual((code, lines[1]), (11, reason_line("could-not-refresh")), name)
        path.unlink()
        self.assertEqual(self.run_check(self.eng)[0], 11)
        path.write_bytes((json.dumps(good)).encode("utf-8"))
        self.assertEqual(self.run_check(self.eng)[0], 0)

    def test_a_failed_first_fetch_records_nothing(self):
        self.take_origin_away()
        self.run_check(self.eng)
        self.assertFalse((self.eng / ".carrydown").exists())

    def test_no_refresh_follows_the_grace_rule_without_a_fetch(self):
        self.refresh_once()
        code, lines = self.run_check(self.eng, now=NOW + dt.timedelta(days=1), refresh=False)
        self.assertEqual(code, 0)
        self.assertIn("warning: " + OFFLINE_WARNING, lines)
        self.assertEqual(self.run_check(self.eng, now=NOW + dt.timedelta(days=9), refresh=False)[0], 11)

    def test_an_expired_release_is_stale_even_inside_the_grace_period(self):
        """[G4] Expiry and offline grace are checked separately: an expired release is stale inside the grace period."""
        (self.pub / "docs" / "release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt(self.files, expires_at="2027-02-02T12:00:00Z", nonce="c3" * 16)
        self.write_receipt(self.pub, rid, data)
        self.publish("expiring release")
        self.git(self.eng, "pull", "-q")
        self.refresh_once()
        self.take_origin_away()
        self.assertEqual(self.run_check(self.eng, now=NOW + dt.timedelta(days=1, seconds=-1))[0], 0)
        code, lines = self.run_check(self.eng, now=NOW + dt.timedelta(days=1))
        self.assertEqual((code, lines[1]), (11, reason_line("expired")))

    def test_a_checkout_with_no_origin_at_all_is_unreachable(self):
        self.git(self.eng, "remote", "remove", "origin")
        self.assertEqual(self.run_check(self.eng)[1][1], reason_line("could-not-refresh"))


class ApprovedInputsLocalTests(LocalProject):
    """The specification and the shared files against one active receipt, without git (exit 14 and 15)."""

    def assert_spec_block(self, code_lines, reason, where=None):
        code, lines = code_lines
        self.assertEqual((code, lines[0]), (14, SPEC_MISMATCH), lines)
        self.assertEqual(lines[1], reason_line(reason))
        if where is not None:
            self.assertEqual(lines[2], f"file: {where}")
        self.assertIn("Restore the approved file", lines[-1])
        self.assertLessEqual(len(lines), 4)
        text = "\n".join(lines)
        for forbidden in (str(self.base), "Sole approver", "Routing", "Harbor", "company-governance"):
            self.assertNotIn(forbidden, text)

    def passes(self, root=None, receipt=None):
        receipt = receipt or CC.parse_receipt(self.receipt)
        with mock.patch.object(CC, "refresh", return_value=("fresh", receipt, "a" * 40)):
            return self.run_check(root or self.root)

    def test_every_approved_file_matching_one_receipt_is_ready_and_names_the_baseline(self):
        code, lines = self.passes()
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[:3], ["carrydown: approved context for WI-06 is ready",
                                     "Read docs/context/wi-06.md. Do not open docs/ground-truth/ or any source.",
                                     f"baseline: request {self.rid}, specification {H_FILE(SPEC_FILE)}"])

    def test_the_specification_changed_outside_the_overlay_is_exit_14_in_a_request_only_project(self):
        path = self.root / SPEC_FILE
        for edit in (path.read_bytes().replace(b"## Outcome\n", b"## Outcome\n\nA changed promise.\n", 1),
                     path.read_bytes().replace(b"None yet.", b"- 2027-02-10. Used cents (pull request 12)."),
                     path.read_bytes() + b"\n"):
            path.write_bytes(edit)
            self.assert_spec_block(self.run_check(self.root, refresh=False), "body-changed", SPEC_FILE)

    def test_the_wrong_specification_never_reaches_the_freshness_step(self):
        (self.root / SPEC_FILE).write_bytes(PROJECT[SPEC_FILE] + b"x")
        with mock.patch.object(CC, "refresh") as fetch:
            self.assertEqual(self.run_check(self.root)[0], 14)
        fetch.assert_not_called()

    def test_a_missing_specification_is_exit_14(self):
        (self.root / SPEC_FILE).unlink()
        self.assert_spec_block(self.run_check(self.root), "spec-missing")

    def test_two_specifications_for_one_item_are_ambiguous(self):
        twin = self.root / "docs/spec/m3-enforce-policy/wi-06-copy.md"
        twin.write_bytes(PROJECT[SPEC_FILE])
        self.assert_spec_block(self.run_check(self.root), "spec-ambiguous")

    def test_a_specification_that_is_a_link_is_not_a_specification(self):
        if os.name != "posix":
            self.skipTest("symbolic links need a POSIX file system")
        path = self.root / SPEC_FILE
        elsewhere = self.base / "elsewhere.md"
        elsewhere.write_bytes(PROJECT[SPEC_FILE])
        path.unlink()
        path.symlink_to(elsewhere)
        self.assert_spec_block(self.run_check(self.root), "spec-missing")

    def test_each_shared_file_is_an_input(self):
        shared = ["docs/spec/plan.yaml", "docs/spec/README.md", f"{SKILL_REL}/SKILL.md", f"{SKILL_REL}/README.md"]
        for rel in shared:
            path = self.root / rel
            good = path.read_bytes()
            path.write_bytes(good + b"\nchanged\n")
            self.assert_spec_block(self.run_check(self.root), "input-changed", rel)
            path.unlink()
            self.assert_spec_block(self.run_check(self.root), "input-missing", rel)
            path.write_bytes(good)
        self.assertEqual(self.passes()[0], 0)

    def test_a_shared_specification_named_in_integration_points_is_an_input(self):
        text = PROJECT[SPEC_FILE].decode("utf-8")
        stems = CC.neighbor_stems(text, "WI-06")
        self.assertTrue(stems, "the fixture's specification names other work items")
        neighbor = next(p for p in sorted(PROJECT) if p.startswith("docs/spec/") and p.rsplit("/", 1)[-1].startswith(stems[0] + "-"))
        (self.root / neighbor).write_bytes(PROJECT[neighbor] + b"\nchanged\n")
        self.assert_spec_block(self.run_check(self.root), "body-changed", neighbor)
        (self.root / neighbor).write_bytes(PROJECT[neighbor])
        self.assertEqual(self.passes()[0], 0)

    def test_a_work_item_the_receipt_does_not_list_is_not_a_required_input(self):
        text = PROJECT[SPEC_FILE].decode("utf-8").replace("## Integration points\n", "## Integration points\n\nThe counterpart is WI-12, which has no file.\n", 1)
        (self.root / SPEC_FILE).write_bytes(text.encode())
        files = dict(self.files, **{SPEC_FILE: text.encode()})
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt(files)
        self.write_receipt(self.root, rid, data)
        self.assertEqual(self.passes(receipt=CC.parse_receipt(data))[0], 0)

    def test_a_receipt_that_does_not_list_the_specification_is_exit_14(self):
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt({p: d for p, d in self.files.items() if p != SPEC_FILE})
        self.write_receipt(self.root, rid, data)
        self.assert_spec_block(self.run_check(self.root), "not-in-release", SPEC_FILE)

    def test_a_receipt_that_does_not_list_the_skill_instructions_is_exit_14(self):
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt({p: d for p, d in self.files.items() if p != f"{SKILL_REL}/SKILL.md"})
        self.write_receipt(self.root, rid, data)
        self.assert_spec_block(self.run_check(self.root), "not-in-release", f"{SKILL_REL}/SKILL.md")

    def test_the_context_alone_in_a_receipt_is_no_longer_enough(self):
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt(BUNDLES)
        self.write_receipt(self.root, rid, data)
        self.assertEqual(self.run_check(self.root)[0], 14)

    def test_files_that_match_different_active_receipts_are_exit_15(self):
        """Two active receipts, each covering a different part of what the checkout holds."""
        readme = "docs/spec/README.md"
        other = dict(self.files, **{readme: PROJECT[readme] + b"\nNewer conventions.\n"})
        spec_b = dict(other, **{SPEC_FILE: PROJECT[SPEC_FILE].replace(b"## Outcome\n", b"## Outcome\n\nSecond release.\n", 1)})
        rid_b, data_b = build_receipt(spec_b, nonce="b2" * 16)
        self.write_receipt(self.root, rid_b, data_b)
        (self.root / readme).write_bytes(other[readme])            # matches release B only
        # the specification still holds release A's bytes, which release B does not list
        code, lines = self.run_check(self.root)
        self.assertEqual((code, lines[0]), (15, MIXED), lines)
        self.assertEqual(lines[1], reason_line("inputs-from-different-releases"))
        self.assertIn("Pull the default branch", lines[-1])
        self.assertLessEqual(len(lines), 4)

    def test_two_active_receipts_that_list_the_same_bytes_are_not_ambiguous(self):
        rid, data = build_receipt(self.files, nonce="b2" * 16)
        self.write_receipt(self.root, rid, data)
        self.assertEqual(self.passes(receipt=CC.parse_receipt(data))[0], 0)

    def assert_two_active(self, code_lines, where):
        code, lines = code_lines
        self.assertEqual((code, lines[0]), (15, MIXED), lines)
        self.assertEqual(lines[1], reason_line("two-active-releases"))
        self.assertIn("The plan owner must supersede or withdraw one of them", lines[1])
        self.assertEqual(lines[2], f"file: {where}")
        self.assertLessEqual(len(lines), 4)
        text = "\n".join(lines)
        for forbidden in (str(self.base), "Sole approver", "Routing", "Harbor", "company-governance"):
            self.assertNotIn(forbidden, text)

    def test_two_active_receipts_that_disagree_on_one_input_are_exit_15(self):
        """Design 10.1: two unlinked active releases that disagree are ambiguous, even when the files match one of them."""
        readme = "docs/spec/README.md"
        # a copy of the active receipt under another request id, with one digest altered and nothing else
        copy = json.loads(self.receipt)
        copy["request_id"] = "a" * 64
        for entry in copy["artifacts"]:
            if entry["path"] == readme:
                entry["sha256"] = "c" * 64
        self.write_receipt(self.root, copy["request_id"], json.dumps(copy).encode("utf-8"))
        self.assertIsNotNone(CC.parse_receipt((self.root / "docs/release" / f"{'a' * 64}.receipt.json").read_bytes()))
        with mock.patch.object(CC, "refresh") as fetch:
            self.assert_two_active(self.run_check(self.root), readme)
        fetch.assert_not_called()
        # a real second release with other bytes for one shared file, the checkout holding the first
        (self.root / "docs/release" / f"{'a' * 64}.receipt.json").unlink()
        rid_b, data_b = build_receipt(dict(self.files, **{readme: PROJECT[readme] + b"\nNewer conventions.\n"}), nonce="b2" * 16)
        self.write_receipt(self.root, rid_b, data_b)
        self.assert_two_active(self.run_check(self.root, refresh=False), readme)
        # the same when the checkout holds the second release's file instead
        (self.root / readme).write_bytes(PROJECT[readme] + b"\nNewer conventions.\n")
        self.assert_two_active(self.run_check(self.root, refresh=False), readme)

    def test_a_second_active_receipt_for_other_context_bytes_is_exit_15(self):
        """An active release that lists this item's context with other bytes is a second release in force for it."""
        ctx = "docs/context/wi-06.md"
        rid_b, data_b = build_receipt(dict(self.files, **{ctx: self.files[ctx] + b"\nA newer rule.\n"}), nonce="b2" * 16)
        self.write_receipt(self.root, rid_b, data_b)
        self.assert_two_active(self.run_check(self.root, refresh=False), ctx)

    def test_two_active_receipts_that_agree_on_every_input_use_the_newest(self):
        rid_b, data_b = build_receipt(self.files, nonce="b2" * 16, created="2027-01-25T09:00:00Z")
        self.assertNotEqual(rid_b, self.rid)
        self.write_receipt(self.root, rid_b, data_b)
        code, lines = self.passes(receipt=CC.parse_receipt(data_b))
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[2], f"baseline: request {rid_b}, specification {H_FILE(SPEC_FILE)}")
        local = CC.local_receipts(self.root)
        md, js = (self.root / "docs/context/wi-06.md").read_bytes(), (self.root / "docs/context/wi-06.bundle.json").read_bytes()
        ctx = {"docs/context/wi-06.md": (CC.sha256(md), len(md)), "docs/context/wi-06.bundle.json": (CC.sha256(js), len(js))}
        chosen, _ = CC.choose(self.root, local, ctx, "WI-06", False)
        self.assertEqual(chosen["request_id"], rid_b)

    def test_an_ended_receipt_that_disagrees_is_not_a_second_active_release(self):
        """[G4] Supersession and withdrawal are unchanged: only active receipts can make the release ambiguous."""
        readme = "docs/spec/README.md"
        changed = dict(self.files, **{readme: PROJECT[readme] + b"\nOlder conventions.\n"})
        for state, kw in (("superseded", {"superseded_by": self.rid}), ("withdrawn", {})):
            rid_old, data_old = build_receipt(changed, state=state, nonce="c3" * 16, created="2027-01-10T09:00:00Z", **kw)
            self.write_receipt(self.root, rid_old, data_old)
            code, lines = self.passes()
            self.assertEqual(code, 0, (state, lines))
            self.assertEqual(lines[2], f"baseline: request {self.rid}, specification {H_FILE(SPEC_FILE)}")
            (self.root / "docs/release" / f"{rid_old}.receipt.json").unlink()
        # and the checkout holding the ended release's file is still told that file changed, as before
        rid_old, data_old = build_receipt(changed, state="superseded", superseded_by=self.rid, nonce="c3" * 16)
        self.write_receipt(self.root, rid_old, data_old)
        (self.root / readme).write_bytes(changed[readme])
        self.assert_spec_block(self.run_check(self.root, refresh=False), "input-changed", readme)

    def test_an_ended_release_is_stale_before_any_file_is_judged(self):
        rid, data = build_receipt(self.files, state="withdrawn")
        self.write_receipt(self.root, rid, data)
        (self.root / SPEC_FILE).write_bytes(PROJECT[SPEC_FILE] + b"x")
        code, lines = self.run_check(self.root)
        self.assertEqual((code, lines[0], lines[1]), (11, STALE, reason_line("withdrawn")))

    def test_a_placeholder_item_needs_no_specification(self):
        side = json.loads(self.files["docs/context/wi-06.bundle.json"])
        side["restricted_destination"] = True
        files = dict(self.files, **{"docs/context/wi-06.bundle.json": RS.canonical_json(side)})
        (self.root / "docs/release" / f"{self.rid}.receipt.json").unlink()
        rid, data = build_receipt({p: d for p, d in files.items() if not p.startswith("docs/spec/")})
        self.write_project(self.root, files=files, receipts=[(rid, data)])
        (self.root / SPEC_FILE).unlink()
        with mock.patch.object(CC, "refresh", return_value=("fresh", CC.parse_receipt(data), "a" * 40)):
            self.assertEqual(self.run_check(self.root)[1][0], RESTRICTED)

    def test_an_unfilled_or_odd_policy_is_the_strict_one(self):
        for value in ("{{engineer_edits}}", "whatever", ""):
            with mock.patch.object(CC, "ENGINEER_EDITS", value):
                self.assertEqual(CC.edit_policy(), "request-only", value)
        with mock.patch.object(CC, "ENGINEER_EDITS", "allowed"):
            self.assertEqual(CC.edit_policy(), "allowed")
        with mock.patch.object(CC, "SKILL_PATH", "{{skill_path}}"):
            self.assertIsNone(CC.skill_dir())
        with mock.patch.object(CC, "SKILL_PATH", "../outside"):
            self.assertIsNone(CC.skill_dir())


@unittest.skipUnless(HAS_GIT, "git is needed for the fake origin")
class DecisionOverlayCheckTests(OriginTests):
    """The decision overlay in the engineer's check: the approved bytes come from git, the receipt verifies them."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(CC, "ENGINEER_EDITS", "allowed")
        patch.start()
        self.addCleanup(patch.stop)
        self.spec = self.eng / SPEC_FILE

    def append(self, entry, root=None):
        path = (root or self.eng) / SPEC_FILE
        path.write_bytes(path.read_bytes().replace(b"None yet.", entry.encode()))

    def cache_item(self):
        return self.cache()["items"]["WI-06"]

    def test_a_valid_first_entry_passes_and_records_the_overlay_digest(self):
        entry = "- 2027-02-10. Used integer cents (pull request 12)."
        self.append(entry)
        code, lines = self.run_check(self.eng)
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[2], f"baseline: request {self.rid}, specification {H_FILE(SPEC_FILE)}",
                         "the baseline is the approved digest, not the digest of the edited file")
        self.assertIn("note: 1 new note(s) under Decisions recorded in your copy of the specification. They are not an approval. The plan owner reviews them", lines)
        expected = hashlib.sha256(entry.encode()).hexdigest()
        item = self.cache_item()
        self.assertEqual(item["overlay_sha256"], expected)
        self.assertEqual(item["overlays"], {SPEC_FILE: expected})
        self.assertEqual(item["files"][SPEC_FILE], H_FILE(SPEC_FILE))
        self.assertEqual(DO.validate_overlay(PROJECT[SPEC_FILE], self.spec.read_bytes(), "allowed").overlay_sha256, expected)

    def test_an_entry_committed_on_a_branch_is_still_judged_against_the_approved_text(self):
        self.append("- 2027-02-10. Used integer cents (pull request 12).")
        self.git(self.eng, "checkout", "-q", "-b", "feature")
        self.git(self.eng, "commit", "-q", "-am", "decision note")
        self.assertEqual(self.run_check(self.eng)[0], 0)
        # the note was committed, but the receipt lists the first approved version: a later edit of the note is still an overlay of that
        self.spec.write_bytes(self.spec.read_bytes().replace(b"Used integer cents (pull request 12)", b"Used floats (pull request 12)"))
        self.assertEqual(self.run_check(self.eng)[0], 0)

    def test_the_placeholder_kept_beside_an_entry_is_exit_14(self):
        self.spec.write_bytes(self.spec.read_bytes() + b"\n- 2027-02-10. Used cents (pull request 12).\n")
        code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[0], lines[1]), (14, SPEC_MISMATCH, reason_line("placeholder-kept")))

    def test_an_undated_note_is_exit_14(self):
        self.append("- Used integer cents.")
        code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[1]), (14, reason_line("entry-undated")))

    def test_a_change_outside_the_section_is_exit_14_even_with_a_valid_entry(self):
        self.append("- 2027-02-10. Used integer cents (pull request 12).")
        self.spec.write_bytes(self.spec.read_bytes().replace(b"## Outcome\n", b"## Outcome\n\nA changed promise.\n", 1))
        code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[1], lines[2]), (14, reason_line("body-changed"), f"file: {SPEC_FILE}"))
        self.assertFalse((self.eng / ".carrydown").exists(), "a refused check records nothing")

    def test_an_edited_old_entry_is_exit_14(self):
        approved = dict(self.files, **{SPEC_FILE: PROJECT[SPEC_FILE].replace(b"None yet.", b"- 2027-02-01. Used integer cents (pull request 3).")})
        rid, data = build_receipt(approved, nonce="b2" * 16)
        (self.pub / "docs" / "release" / f"{self.rid}.receipt.json").unlink()
        write_project_files(self.pub, approved, [(rid, data)])
        self.publish("release with a decision note")
        self.git(self.eng, "pull", "-q")
        self.assertEqual(self.run_check(self.eng)[0], 0)
        self.spec.write_bytes(self.spec.read_bytes().replace(b"Used integer cents (pull request 3)", b"Used floats (pull request 3)"))
        code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[0], lines[1]), (14, SPEC_MISMATCH, reason_line("entry-edited")))
        # a new entry after the approved one is fine
        self.spec.write_bytes(self.git(self.eng, "show", f"HEAD:{SPEC_FILE}").encode() + b"\n- 2027-02-10. Then a retry (PR #14).\n")
        self.assertEqual(self.run_check(self.eng)[0], 0)

    def test_a_removed_old_entry_is_exit_14(self):
        approved = dict(self.files, **{SPEC_FILE: PROJECT[SPEC_FILE].replace(b"None yet.", b"- 2027-02-01. Used integer cents (pull request 3).")})
        rid, data = build_receipt(approved, nonce="b2" * 16)
        (self.pub / "docs" / "release" / f"{self.rid}.receipt.json").unlink()
        write_project_files(self.pub, approved, [(rid, data)])
        self.publish("release with a decision note")
        self.git(self.eng, "pull", "-q")
        self.spec.write_bytes(PROJECT[SPEC_FILE])
        self.assertEqual(self.run_check(self.eng)[1][1], reason_line("entry-edited"))

    def test_without_the_approved_text_in_git_the_specification_is_unverified(self):
        self.append("- 2027-02-10. Used integer cents (pull request 12).")
        with mock.patch.object(CC, "approved_copy", return_value=None):
            code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[0], lines[1]), (14, SPEC_MISMATCH, reason_line("approved-copy-unavailable")))
        self.assertIn("unverified", lines[1])

    def test_only_a_version_whose_digest_matches_the_receipt_counts_as_approved(self):
        """A history that holds a different version of the file under the same name is not an approved copy."""
        other = PROJECT[SPEC_FILE].replace(b"None yet.", b"- 2027-01-01. Another note (PR 1).")
        self.assertIsNone(CC.approved_copy(self.eng, SPEC_FILE, hashlib.sha256(other).hexdigest()))
        self.assertEqual(CC.approved_copy(self.eng, SPEC_FILE, H_FILE(SPEC_FILE)), PROJECT[SPEC_FILE])

    def test_a_request_only_project_refuses_even_a_valid_entry(self):
        with mock.patch.object(CC, "ENGINEER_EDITS", "request-only"):
            self.append("- 2027-02-10. Used integer cents (pull request 12).")
            code, lines = self.run_check(self.eng)
        self.assertEqual((code, lines[0], lines[1]), (14, SPEC_MISMATCH, reason_line("body-changed", "request-only")))
        self.assertIn("does not let engineers edit specifications", lines[1])

    def test_the_body_changed_reason_names_what_an_allowed_project_permits(self):
        self.spec.write_bytes(self.spec.read_bytes().replace(b"## Outcome\n", b"## Outcome\n\nA changed promise.\n", 1))
        code, lines = self.run_check(self.eng)
        self.assertEqual(code, 14)
        self.assertEqual(lines[1], f"reason: {CC.BODY_CHANGED_ALLOWED} (body-changed)")
        self.assertIn("Only new dated decision entries may be added", lines[1])
        self.assertNotIn("does not let engineers edit", lines[1])

    def test_a_neighbor_specification_may_carry_a_valid_overlay_too(self):
        stems = CC.neighbor_stems(PROJECT[SPEC_FILE].decode("utf-8"), "WI-06")
        neighbor = next(p for p in sorted(PROJECT) if p.startswith("docs/spec/") and p.rsplit("/", 1)[-1].startswith(stems[0] + "-"))
        path = self.eng / neighbor
        path.write_bytes(path.read_bytes().replace(b"None yet.", b"- 2027-02-10. Their note (pull request 5)."))
        self.assertEqual(self.run_check(self.eng)[0], 0)
        self.assertIn(neighbor, self.cache_item()["overlays"])
        self.assertIsNone(self.cache_item()["overlay_sha256"], "the item's own specification has no overlay")


@unittest.skipUnless(HAS_GIT, "git is needed for the fake origin")
class ApprovedDeltaTests(OriginTests):
    """After a refresh, the approved inputs are compared with the ones recorded at the last check (design 10.3)."""

    def release(self, changes, nonce="b2" * 16, supersede=True):
        """Publish a replacement release with the files changed ({path: bytes}); the old receipt becomes superseded."""
        files = dict(self.files, **changes)
        new_rid, new_data = build_receipt(files, nonce=nonce, supersedes=self.rid)
        _, old_data = build_receipt(self.files, state="superseded", superseded_by=new_rid)
        write_project_files(self.pub, files, [(self.rid, old_data), (new_rid, new_data)])
        self.publish("replacement release")
        return new_rid, files

    def pull(self):
        self.git(self.eng, "pull", "-q", "--ff-only")

    def delta(self, lines):
        return [ln for ln in lines if ln.startswith("carrydown: approved inputs changed")]

    def test_the_first_check_and_an_unchanged_check_print_no_delta(self):
        self.assertEqual(len(self.run_check(self.eng)[1]), 3)
        self.assertEqual(len(self.run_check(self.eng)[1]), 3)

    def test_a_changed_specification_prints_the_changed_passages_and_the_reassessment_instruction(self):
        self.refresh_once()
        text = PROJECT[SPEC_FILE].decode("utf-8")
        changed = text.replace("## Outcome\n", "## Outcome\n\nApprovals above 30,000.00 need the chief finance officer.\n", 1)
        new_rid, files = self.release({SPEC_FILE: changed.encode()})
        self.pull()
        code, lines = self.run_check(self.eng)
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[0], "carrydown: approved context for WI-06 is ready")
        self.assertEqual(lines[2], f"baseline: request {new_rid}, specification {hashlib.sha256(changed.encode()).hexdigest()}")
        self.assertEqual(self.delta(lines), [CC.DELTA_HEADLINE.format(id="WI-06")])
        block = lines[lines.index(CC.DELTA_HEADLINE.format(id="WI-06")):]
        self.assertEqual(block[1], f"changed: {SPEC_FILE} (specification)")
        self.assertNotIn("changed: docs/context/wi-06.md (approved context)", block, "unchanged files are not listed")
        self.assertIn(f"--- {SPEC_FILE} (previous)", block)
        self.assertIn(f"+++ {SPEC_FILE} (current)", block)
        self.assertIn("+Approvals above 30,000.00 need the chief finance officer.", block)
        self.assertEqual(block[-1], CC.REASSESS)
        self.assertEqual(CC.REASSESS, "Reassess your implementation plan against the current approved inputs before you write more code. Do not continue on the old plan.")
        context_lines = [ln for ln in block if ln.startswith(("+", "-", " ", "@@")) and "Approvals above" not in ln]
        self.assertTrue(all(len(ln) <= 300 for ln in block))
        self.assertLessEqual(len(context_lines), 12, "a short delta: the changed lines and two lines of context each side")
        # the record moved to the new baseline, so the next check is quiet
        self.assertEqual(len(self.run_check(self.eng)[1]), 3)
        self.assertEqual(self.cache()["items"]["WI-06"]["request_id"], new_rid)

    def test_a_changed_context_and_a_changed_convention_are_listed_with_their_labels(self):
        self.refresh_once()
        readme, context = "docs/spec/README.md", "docs/context/wi-06.md"
        side = json.loads(PROJECT["docs/context/wi-06.bundle.json"])
        new_context = PROJECT[context] + b"\nA new approved rule.\n"
        side["content_sha256"] = hashlib.sha256(new_context).hexdigest()
        self.release({readme: PROJECT[readme] + b"\nA new convention.\n", context: new_context, "docs/context/wi-06.bundle.json": RS.canonical_json(side),
                      "docs/spec/plan.yaml": PROJECT["docs/spec/plan.yaml"] + b"# note\n"})
        self.pull()
        code, lines = self.run_check(self.eng)
        self.assertEqual(code, 0, lines)
        block = lines[lines.index(CC.DELTA_HEADLINE.format(id="WI-06")):]
        for row in (f"changed: {context} (approved context)", "changed: docs/context/wi-06.bundle.json (context sidecar)",
                    f"changed: {readme} (specification folder README)", "changed: docs/spec/plan.yaml (released plan)"):
            self.assertIn(row, block)
        self.assertIn("+A new approved rule.", block)
        self.assertIn("+A new convention.", block)
        self.assertNotIn("+# note", block, "the released plan is listed, its lines are not shown")

    def test_a_missing_previous_version_says_so_and_still_asks_for_reassessment(self):
        self.refresh_once()
        record = self.cache()
        record["items"]["WI-06"]["files"][SPEC_FILE] = "9" * 64            # a version no history holds
        (self.eng / ".carrydown/cache/last-refresh").write_bytes((json.dumps(record)).encode("utf-8"))
        code, lines = self.run_check(self.eng)
        self.assertEqual(code, 0, lines)
        self.assertIn(CC.DELTA_HEADLINE.format(id="WI-06"), lines)
        self.assertIn(f"changed: {SPEC_FILE} (specification)", lines)
        self.assertIn(f"{SPEC_FILE}: previous version unavailable locally; load the current approved inputs", lines)
        self.assertEqual(lines[-1], CC.REASSESS)
        self.assertEqual(CC.NO_PREVIOUS, "previous version unavailable locally; load the current approved inputs")

    def test_a_newer_release_with_the_same_bytes_is_a_provenance_refresh_not_a_delta(self):
        self.refresh_once()
        new_rid, _ = self.release({})
        self.pull()
        code, lines = self.run_check(self.eng)
        self.assertEqual(code, 0, lines)
        self.assertEqual(self.delta(lines), [])
        self.assertEqual(lines[3], "note: a newer release covers the same approved inputs for WI-06. Only its provenance changed, so nothing in your plan needs to change")
        self.assertNotIn(CC.REASSESS, lines)
        self.assertEqual(self.cache()["items"]["WI-06"]["request_id"], new_rid)

    def test_the_baseline_of_another_item_is_kept_and_not_confused(self):
        self.refresh_once()
        code, lines = self.run_check(self.eng, "WI-03")
        self.assertEqual(code, 0, lines)
        self.assertEqual(len(lines), 3, "WI-03 has no baseline of its own yet")
        self.assertEqual(sorted(self.cache()["items"]), ["WI-03", "WI-06"])

    def test_the_check_never_changes_the_working_tree_or_the_branch(self):
        self.refresh_once()
        new_rid, _ = self.release({SPEC_FILE: PROJECT[SPEC_FILE].replace(b"## Outcome\n", b"## Outcome\n\nA changed promise.\n", 1)})
        before_head = self.git(self.eng, "rev-parse", "HEAD")
        before_status = self.git(self.eng, "status", "--porcelain")
        code, lines = self.run_check(self.eng)
        # the clone has not pulled: the local release is stale next to the fetched one, and nothing was merged
        self.assertEqual((code, lines[0]), (11, STALE))
        self.assertEqual(self.git(self.eng, "rev-parse", "HEAD"), before_head)
        self.assertEqual(self.git(self.eng, "status", "--porcelain"), before_status)
        self.assertEqual((self.eng / SPEC_FILE).read_bytes(), PROJECT[SPEC_FILE])

    def test_the_delta_is_labeled_text_and_holds_no_color(self):
        self.refresh_once()
        self.release({SPEC_FILE: PROJECT[SPEC_FILE].replace(b"## Outcome\n", b"## Outcome\n\nA changed promise.\n", 1)})
        self.pull()
        text = "\n".join(self.run_check(self.eng)[1])
        self.assertNotIn("\x1b", text)
        self.assertIn("changed: ", text)

    def test_the_command_line_prints_the_delta_after_the_ready_line(self):
        self.refresh_once()
        self.release({SPEC_FILE: PROJECT[SPEC_FILE].replace(b"## Outcome\n", b"## Outcome\n\nA changed promise.\n", 1)})
        self.pull()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HOME=str(self.home))
        run = subprocess.run([sys.executable, str(TEMPLATE), "WI-06"], cwd=str(self.eng), env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        lines = run.stdout.splitlines()
        self.assertEqual(lines[0], "carrydown: approved context for WI-06 is ready")
        self.assertIn(CC.DELTA_HEADLINE.format(id="WI-06"), lines)
        self.assertEqual(lines[-1], CC.REASSESS)


@unittest.skipUnless(HAS_GIT, "git is needed for the fake origin")
class MessageHygieneTests(OriginTests):
    def test_no_blocked_run_prints_withheld_text_a_heading_a_private_path_or_a_name(self):
        outputs = []
        outputs.append(self.run_check(self.eng, "WI-99")[1])
        (self.eng / "docs/context/wi-03.md").write_bytes(b"changed")
        outputs.append(self.run_check(self.eng, "WI-03")[1])
        spec_path = self.eng / SPEC_FILE
        spec_path.write_bytes((spec_path.read_text(encoding="utf-8").replace("## References\n", "## References\n\n- architecture section 9.9, Sole approver\n", 1)).encode("utf-8"))
        outputs.append(self.run_check(self.eng)[1])
        self.git(self.eng, "checkout", "--", SPEC_FILE)
        _, data = build_receipt(self.files, state="withdrawn")
        self.write_receipt(self.pub, self.rid, data)
        self.publish("withdraw")
        outputs.append(self.run_check(self.eng)[1])
        self.take_origin_away()
        outputs.append(self.run_check(self.eng)[1])
        for lines in outputs:
            self.assertTrue(lines[0].startswith("carrydown: "), lines)
            self.assert_clean(lines)
            self.assertLessEqual(len(lines), 4)


@unittest.skipUnless(HAS_GIT, "git is needed for the fake origin")
class CommandLineTests(OriginTests):
    def run_script(self, *args, cwd=None, script=TEMPLATE):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HOME=str(self.home))
        return subprocess.run([sys.executable, str(script)] + list(args), cwd=str(cwd or self.eng), env=env,
                              capture_output=True, text=True, timeout=120)

    def test_exit_zero_and_the_root_is_found_from_a_subfolder(self):
        run = self.run_script("WI-06", cwd=self.eng / "docs" / "spec")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue(run.stdout.startswith("carrydown: approved context for WI-06 is ready"))

    def test_the_exit_codes(self):
        self.assertEqual(self.run_script("WI-99").returncode, 10)
        spec_path = self.eng / SPEC_FILE
        spec_path.write_bytes((spec_path.read_text(encoding="utf-8").replace("## References\n", "## References\n\n- architecture section 9.9\n", 1)).encode("utf-8"))
        run = self.run_script("WI-06")
        self.assertEqual((run.returncode, run.stdout.splitlines()[0]), (12, CITES))
        self.git(self.eng, "checkout", "--", SPEC_FILE)
        spec_path.write_bytes((spec_path.read_text(encoding="utf-8").replace("## Outcome\n", "## Outcome\n\nA changed promise.\n", 1)).encode("utf-8"))
        run = self.run_script("WI-06")
        self.assertEqual((run.returncode, run.stdout.splitlines()[0]), (14, SPEC_MISMATCH))
        self.git(self.eng, "checkout", "--", SPEC_FILE)
        self.take_origin_away()
        run = self.run_script("WI-06")
        self.assertEqual((run.returncode, run.stdout.splitlines()[0]), (11, STALE))

    def test_help_and_a_wrong_argument(self):
        run = self.run_script("--help")
        self.assertEqual(run.returncode, 0)
        self.assertIn("not a security control", run.stdout)
        # each of the six messages of the module docstring is in --help beside its exit code
        documented = re.findall(r"^  (1[0-5])  (carrydown: .+)$", CC.__doc__, re.M)
        self.assertEqual([code for code, _ in documented], ["10", "11", "12", "13", "14", "15"])
        for code, text in documented:
            self.assertIn(f"  {code}  {text}", run.stdout.splitlines())
            self.assertEqual(KIND_LINE[int(code)], text)
        self.assertRegex(run.stdout, r"(?m)^  2   a wrong argument")
        self.assertRegex(run.stdout, r"(?m)^  3   the Python that runs it is older than 3\.9")
        self.assertFalse(any(line.startswith("carrydown:") for line in run.stdout.splitlines()))
        self.assertEqual(self.run_script().returncode, 2)
        self.assertEqual(self.run_script("WI-06", "--root", str(self.base / "nowhere")).returncode, 2)

    def test_an_older_python_prints_no_carrydown_line_and_names_the_preflight(self):
        """The skill's first command is this check; the preflight is its fallback when no line starts with carrydown:."""
        code = ("import runpy, sys; sys.version_info = (3, 8, 18, 'final', 0); sys.argv = sys.argv[1:]; "
                "runpy.run_path(sys.argv[0], run_name='__main__')")
        run = subprocess.run([sys.executable, "-c", code, str(GENERATED), "WI-06"], cwd=str(self.eng), capture_output=True, text=True, timeout=120,
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HOME=str(self.home)))
        self.assertEqual(run.returncode, 3, run.stdout + run.stderr)
        self.assertNotIn("carrydown:", run.stdout + run.stderr)
        self.assertEqual(run.stderr.strip(), "error: this check needs Python 3.9 or newer. Follow references/preflight.md in the skill folder")
        self.assertFalse((self.eng / ".carrydown").exists(), "the check ran past the version guard")

    def test_the_skill_runs_this_check_first_and_the_preflight_only_as_its_fallback(self):
        text = (GENERATED.parent.parent / "SKILL.md").read_text(encoding="utf-8")
        steps = text.split("## Orient on a work item", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(re.findall(r"(?m)^(\d+)\. ", steps), [str(n) for n in range(1, 9)])
        commands = re.findall(r"`((?:python3|find|grep|py) [^`]*)`", steps)
        self.assertEqual(commands[0], "python3 <skill folder>/scripts/check_context.py <ID>")
        step2 = re.search(r"(?ms)^2\. (.*?)^3\. ", steps).group(1)
        self.assertIn("This is the first command for every work item.", step2)
        self.assertIn("If no line starts with `carrydown:`", step2)
        self.assertLess(step2.index("check_context.py"), step2.index("references/preflight.md"))
        self.assertNotIn("references/preflight.md", text.split("## Orient on a work item", 1)[0])

    def test_the_generated_copy_in_the_sample_is_the_template_with_four_constants_filled(self):
        """The sample's copy is regenerated from the template after a template change: until then this fails."""
        fill = (("id_prefix", "WI"), ("spec_dir", "docs/spec"), ("skill_path", SKILL_REL), ("engineer_edits", "allowed"))
        expected = TEMPLATE.read_text(encoding="utf-8")
        shipped = (ROOT / "skills/carrydown-plan-to-github/templates/dev-skill/scripts/check_context.py").read_text(encoding="utf-8")
        for name, value in fill:
            expected = expected.replace("{{" + name + "}}", value)
            shipped = shipped.replace("{{" + name + "}}", value)
        self.assertEqual(GENERATED.read_text(encoding="utf-8"), expected)
        self.assertEqual(GENERATED.read_text(encoding="utf-8"), shipped)

    def test_the_generated_copy_runs_in_a_checkout(self):
        run = self.run_script("WI-06", script=GENERATED)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_run_from_the_top_of_the_carrydown_repository_the_sample_has_no_context(self):
        run = self.run_script("WI-06", cwd=SAMPLE, script=GENERATED)
        self.assertEqual((run.returncode, run.stdout.splitlines()[0]), (10, FIRST))
        self.assertFalse((SAMPLE / ".carrydown").exists())

    def test_the_template_is_standard_library_only_and_names_no_token(self):
        import ast
        tree = ast.parse(TEMPLATE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertEqual(imported, {"argparse", "datetime", "difflib", "hashlib", "json", "os", "re", "subprocess", "sys", "pathlib", "typing"})
        text = TEMPLATE.read_text(encoding="utf-8")
        for word in ("urllib", "socket", "ssl", "GITHUB_TOKEN", "CARRYDOWN_GITHUB_TOKEN", "Authorization"):
            self.assertNotIn(word, text, word)


if __name__ == "__main__":
    unittest.main()
