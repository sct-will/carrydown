"""The engineers' check (work package 5): templates/dev-skill/scripts/check_context.py.

They cover local validity (bundle bytes, sidecar, the specification's citations, an active receipt),
the four messages and their exit codes, freshness against a fake origin (a bare git repository on
disk), offline grace and its record, expiry, the replacement and withdrawal of a release, and that
no message holds withheld text, a private path or a name. Tests tagged [G4] are negative tests of the
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
import release_schema as RS  # noqa: E402

TEMPLATE = ROOT / "templates" / "dev-skill" / "scripts" / "check_context.py"
FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
SAMPLE = ROOT / "sample" / "expense-approvals"
GENERATED = SAMPLE / "docs" / "dev" / "skills" / "expense-approvals-dev" / "scripts" / "check_context.py"
HAS_GIT = shutil.which("git") is not None

spec = importlib.util.spec_from_file_location("check_context_under_test", str(TEMPLATE))
CC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CC)

UTC = dt.timezone.utc
NOW = dt.datetime(2027, 2, 1, 12, 0, 0, tzinfo=UTC)
TIME = "2027-01-20T14:03:00Z"
FIRST = "carrydown: no approved context for WI-06"
STALE = "carrydown: the approved context for WI-06 is stale"


def reason_line(code):
    """The second line of a stale message: the plain words, then the fixed code."""
    return f"reason: {CC.REASONS[code]} ({code})"
CITES = "carrydown: WI-06 cites an obligation that is not in its approved context"
RESTRICTED = "carrydown: WI-06 has a restricted destination that this project does not publish"
OFFLINE_WARNING = "freshness not confirmed; within offline grace"
SPEC_FILE = "docs/spec/m3-enforce-policy/wi-06-limits-and-duties.md"


def H(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def compile_fixture():
    plan, problems = L.load_plan(FIXTURE / "docs" / "spec" / "plan.yaml", FIXTURE)
    assert problems == [], problems
    return CB.compile_bundles(plan, FIXTURE / "docs" / "ground-truth", FIXTURE / "docs" / "spec")


BUNDLES = compile_fixture()
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
        self.files = dict(BUNDLES)

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
            spec_path.write_text(text.replace("## References\n", "## References\n\n" + line + "\n", 1), encoding="utf-8")
            code, lines = self.run_check(self.root)
            self.assertEqual((code, lines[0]), (12, CITES), line)
            self.assertEqual(lines[1:], ["Ask the plan owner. Do not guess the rule."])

    def test_a_citation_the_bundle_holds_passes_in_either_form(self):
        spec_path = self.root / SPEC_FILE
        text = spec_path.read_text(encoding="utf-8")
        cited = CC.spec_citations(self.root, "WI-06", {"architecture", "company-governance"})
        self.assertEqual(cited, [("architecture", "3.5"), ("architecture", "4.1"), ("architecture", "7.1"),
                                 ("company-governance", "1.5"), ("company-governance", "2.3")])
        spec_path.write_text(text.replace("## References\n", "## References\n\n- company-governance section 2.3, Approval limits\n- architecture section 3.5\n", 1), encoding="utf-8")
        self.assertIn(("company-governance", "2.3"), CC.spec_citations(self.root, "WI-06", set()))
        # a link whose file name is not a source of the bundle cannot be read as a citation, so it is not a finding
        spec_path.write_text(text.replace("## References\n", "## References\n\n- [Section 1.1](../../ground-truth/unrelated.md#x)\n", 1), encoding="utf-8")
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
        cls.rid, cls.receipt = build_receipt(BUNDLES)
        write_project_files(pub, BUNDLES, [(cls.rid, cls.receipt)])
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
        self.assertEqual(len(lines), 2)
        self.assertEqual(self.cache(), {"cache_format": 1, "repository": CC.origin_identity(self.eng), "commit": self.origin_head(),
                                        "request_id": self.rid, "time": "2027-02-01T12:00:00Z"})
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
            path.write_text(text, encoding="utf-8")
            code, lines = self.run_check(self.eng)
            self.assertEqual((code, lines[1]), (11, reason_line("could-not-refresh")), name)
        path.unlink()
        self.assertEqual(self.run_check(self.eng)[0], 11)
        path.write_text(json.dumps(good), encoding="utf-8")
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


@unittest.skipUnless(HAS_GIT, "git is needed for the fake origin")
class MessageHygieneTests(OriginTests):
    def test_no_blocked_run_prints_withheld_text_a_heading_a_private_path_or_a_name(self):
        outputs = []
        outputs.append(self.run_check(self.eng, "WI-99")[1])
        (self.eng / "docs/context/wi-03.md").write_bytes(b"changed")
        outputs.append(self.run_check(self.eng, "WI-03")[1])
        spec_path = self.eng / SPEC_FILE
        spec_path.write_text(spec_path.read_text(encoding="utf-8").replace("## References\n", "## References\n\n- architecture section 9.9, Sole approver\n", 1), encoding="utf-8")
        outputs.append(self.run_check(self.eng)[1])
        spec_path.write_text(spec_path.read_text(encoding="utf-8").replace("- architecture section 9.9, Sole approver\n", ""), encoding="utf-8")
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

    def test_the_four_exit_codes(self):
        self.assertEqual(self.run_script("WI-99").returncode, 10)
        spec_path = self.eng / SPEC_FILE
        spec_path.write_text(spec_path.read_text(encoding="utf-8").replace("## References\n", "## References\n\n- architecture section 9.9\n", 1), encoding="utf-8")
        run = self.run_script("WI-06")
        self.assertEqual((run.returncode, run.stdout.splitlines()[0]), (12, CITES))
        self.git(self.eng, "checkout", "--", SPEC_FILE)
        self.take_origin_away()
        run = self.run_script("WI-06")
        self.assertEqual((run.returncode, run.stdout.splitlines()[0]), (11, STALE))

    def test_help_and_a_wrong_argument(self):
        run = self.run_script("--help")
        self.assertEqual(run.returncode, 0)
        self.assertIn("not a security control", run.stdout)
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

    def test_the_generated_copy_in_the_sample_is_the_template_with_two_constants_filled(self):
        expected = TEMPLATE.read_text(encoding="utf-8").replace("{{id_prefix}}", "WI").replace("{{spec_dir}}", "docs/spec")
        self.assertEqual(GENERATED.read_text(encoding="utf-8"), expected)
        self.assertEqual(GENERATED.read_bytes(), (ROOT / "skills/carrydown-plan-to-github/templates/dev-skill/scripts/check_context.py").read_bytes().replace(b"{{id_prefix}}", b"WI").replace(b"{{spec_dir}}", b"docs/spec"))

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
        self.assertEqual(imported, {"argparse", "datetime", "hashlib", "json", "os", "re", "subprocess", "sys", "pathlib"})
        text = TEMPLATE.read_text(encoding="utf-8")
        for word in ("urllib", "socket", "ssl", "GITHUB_TOKEN", "CARRYDOWN_GITHUB_TOKEN", "Authorization"):
            self.assertNotIn(word, text, word)


if __name__ == "__main__":
    unittest.main()
