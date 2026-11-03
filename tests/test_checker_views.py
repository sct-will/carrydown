"""Tests for the checker's views, tracked-source check, log hygiene and the scaffold's ignore lines.

WP3 of the confidential ground truth work. The released view is tested on a project built in a
temporary folder from the confidential fixture: its released plan, its specifications, approved
context bundles written by hand in the E3 format and a receipt built with the release schema. That
project holds no original, no rendering, no overlay and no project.ground_truth. No token and no
network. Run from the repository root: python -m unittest discover -s tests -v
"""
import copy
import json
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
sys.path.insert(0, str(ROOT / "tests"))
import carrydown_lib as L  # noqa: E402
import check_specs as CS  # noqa: E402
import plan_repair as PR  # noqa: E402
import release_schema as RS  # noqa: E402
import test_release_schema as T  # noqa: E402  (its helpers build a manifest, a request and a receipt)

FIXTURE = ROOT / "tests" / "fixtures" / "confidential-project"
SAMPLE = ROOT / "sample" / "expense-approvals"
SCRIPT = ROOT / "scripts" / "check_specs.py"
SCAFFOLD = ROOT / "scripts" / "scaffold_spec.py"
GIT = shutil.which("git")


def run(script, *args, cwd=None):
    r = subprocess.run([sys.executable, str(script)] + [str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", cwd=cwd)
    return r.returncode, r.stdout + r.stderr


def check(*args):
    return run(SCRIPT, *args)


def rendering_section(text, number):
    """(heading, body) of the numbered section of a rendering, up to the next heading."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^#{1,6}\s+" + re.escape(number) + r"\.?\s+(.*)$", line)
        if m:
            body = []
            for nxt in lines[i + 1:]:
                if re.match(r"^#{1,6}\s", nxt):
                    break
                body.append(nxt)
            return m.group(1).strip(), "\n".join(body).strip("\n")
    raise AssertionError(f"section {number} not found")


def workspace_plan_text(public=False):
    text = (FIXTURE / "docs/spec/plan.yaml").read_text(encoding="utf-8")
    if public:
        text = text.replace("classification: restricted", "classification: public").replace("repo_audience_approved: false", "repo_audience_approved: true")
        text = re.sub(r"(?m)^    approvers: .*\n", "", text)
    return text


class Released:
    """A released project in a temporary folder, built from the fixture."""

    def __init__(self, base, public=False, drop=(), expires_at=None, keep_originals=False):
        self.root = Path(base) / "released"
        ignore = [".gitignore", "people.yaml", "__pycache__"] + ([] if keep_originals else ["ground-truth"])
        shutil.copytree(FIXTURE, self.root, ignore=shutil.ignore_patterns(*ignore))
        stored_path = Path(base) / "workspace-plan.yaml"
        stored_path.write_text(workspace_plan_text(public), encoding="utf-8")
        stored, problems = L.load_plan(stored_path, FIXTURE)
        assert not problems, problems
        released = L.project_released_plan(stored)
        self.plan_path = self.root / "docs/spec/plan.yaml"
        self.plan_path.write_text(PR.dump(released) + "\n", encoding="utf-8")
        self.plan, problems = L.load_plan(self.plan_path, self.root)
        assert not problems, problems
        assert self.plan["_view"] == "released"
        self.renderings = {s["id"]: (FIXTURE / "docs/ground-truth" / f"{s['id']}.md").read_text(encoding="utf-8") for s in self.plan["sources"]}
        self.versions = {s["id"]: str(s["version"]) for s in self.plan["sources"]}
        self.fix_headers()
        self.write_bundles(drop)
        self.write_receipt(expires_at)

    def fix_headers(self):
        """The Ground truth row of each specification, as the released plan states it."""
        for it in self.plan["items"]:
            path = L.spec_path(self.plan, self.root, it)
            want = dict(L.expected_header(self.plan, it))["Ground truth"]
            text = path.read_text(encoding="utf-8")
            path.write_text(re.sub(r"(?m)^\| Ground truth \| .* \|$", lambda m: f"| Ground truth | {want} |", text), encoding="utf-8")

    def bundle_paths(self, it):
        low = L.tag(self.plan, it["id"]).lower()
        return self.root / f"docs/context/{low}.md", self.root / f"docs/context/{low}.bundle.json"

    def linked_sections(self, it):
        """(source id, section) pairs that the specification of an item links to in the renderings. The
        released project holds no rendering, so the item's approved context has to hold what it links to."""
        text = L.spec_path(self.plan, self.root, it).read_text(encoding="utf-8")
        found = []
        for sid, anchor in re.findall(r"\]\((?:\.\./)+ground-truth/([a-z0-9-]+)\.md#([^)\s]+)\)", text):
            for line in self.renderings[sid].split("\n"):
                m = re.match(r"^#{1,6}\s+(\d+(?:\.\d+)*)\.?\s+(.*)$", line)
                if m and L.anchor_slug(f"{m.group(1)} {m.group(2)}") == anchor and (sid, m.group(1)) not in found:
                    found.append((sid, m.group(1)))
        return found

    def write_bundles(self, drop=()):
        for it in self.plan["items"]:
            tag = L.tag(self.plan, it["id"])
            obligations, blocks = [], []
            wanted = CS.needed_obligations(self.plan, it)
            wanted += [pair for pair in self.linked_sections(it) if pair not in wanted]
            for sid, sec in wanted:
                if (tag, sid, sec) in drop:
                    continue
                heading, body = rendering_section(self.renderings[sid], sec)
                text = RS.normalize_section_text(body)
                obligations.append({"source": sid, "version": self.versions[sid], "section": sec, "heading": heading, "sha256": RS.sha256_text(text)})
                blocks.append(f"### {sid} {sec} {heading}\n{text}")
            md_path, js_path = self.bundle_paths(it)
            md = f"# Approved context for {tag}, {it['label']}\n\nBundle format 1.\n\n## Obligations\n\n" + "\n".join(blocks)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_bytes(md.encode("utf-8"))
            side = {"bundle_format": 1, "work_item": tag, "obligations": obligations, "conflicts": [], "shared_with": [],
                    "downstream": {"code": True, "tests": True, "issues": False, "evidence": "synthetic-only"},
                    "content_sha256": RS.sha256_bytes(md.encode("utf-8")), "extensions": {}}
            js_path.write_bytes(RS.canonical_json(side))

    def write_receipt(self, expires_at=None, state="active"):
        snap = Path(self.root).parent / "snapshot"
        shutil.rmtree(snap, ignore_errors=True)
        for path in [self.plan_path] + sorted((self.root / "docs/context").glob("*")):
            dst = snap / "repo" / path.relative_to(self.root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dst)
        manifest, release_id = RS.hash_manifest(snap)
        request = T.make_request(manifest)
        request["receipt_template"]["expires_at"] = expires_at
        request["request_sha256"] = RS.hash_request(request)
        rid = request["request_sha256"]
        verified = RS.RequestState(rid, state, T.H("event"), T.H("next") if state == "superseded" else None, None)
        receipt = RS.project_receipt(request, manifest, verified, RS.VerifiedApproval(rid, "local-owner", False))
        folder = self.root / "docs/release"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        self.receipt_path = folder / f"{rid}.receipt.json"
        self.receipt_path.write_bytes(receipt)

    def check(self, *args):
        return check("--root", self.root, *args)


class WithTemp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="carrydown-views-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def folder(self, name):
        """A new empty folder inside the temporary one."""
        path = self.base / name
        path.mkdir()
        return path


class ReleasedViewTests(WithTemp):
    def test_the_clean_clone_passes_with_no_original_rendering_overlay_or_ground_truth_path(self):
        project = Released(self.base)
        self.assertFalse((project.root / "ground-truth").exists())
        self.assertFalse((project.root / "docs/ground-truth").exists())
        self.assertFalse(list(project.root.glob("**/people.yaml")))
        self.assertNotIn("ground_truth", project.plan["project"])
        self.assertFalse(any("path" in s or "source_path" in s or "classification" in s for s in project.plan["sources"]))
        code, out = project.check()
        self.assertEqual(code, 0, out)
        self.assertIn("0 with findings", out)
        self.assertIn("people overlay not loaded", out)

    def test_the_same_clean_clone_passes_when_the_owners_original_was_public(self):
        project = Released(self.base, public=True)
        code, out = project.check()
        self.assertEqual(code, 0, out)
        # an original that is public is optional too: the clone with the original in it also passes
        also = Released(self.folder("also"), public=True, keep_originals=True)
        self.assertEqual(also.check()[0], 0)

    def test_removing_a_cited_obligation_fails(self):
        project = Released(self.base, drop={("WI-06", "architecture", "3.5")})
        code, out = project.check()
        self.assertEqual(code, 1, out)
        self.assertIn("obligation not in the approved context: architecture 3.5", out)
        self.assertEqual(out.count("obligation not in the approved context"), 1)
        self.assertIn("WI-06", out)

    def test_changing_one_byte_of_a_bundle_fails(self):
        for which in (0, 1):
            with self.subTest(file=("md", "json")[which]):
                project = Released(self.folder(f"b{which}"))
                it = next(i for i in project.plan["items"] if i["id"] == 6)
                target = project.bundle_paths(it)[which]
                data = bytearray(target.read_bytes())
                data[len(data) // 2] ^= 0x01
                target.write_bytes(bytes(data))
                code, out = project.check()
                self.assertEqual(code, 1, out)
                self.assertIn("WI-06", out)
                self.assertTrue("does not match content_sha256" in out or "no active receipt" in out or "not strict JSON" in out, out)

    def test_a_bundle_that_is_missing_fails(self):
        project = Released(self.base)
        it = next(i for i in project.plan["items"] if i["id"] == 3)
        project.bundle_paths(it)[1].unlink()
        code, out = project.check()
        self.assertEqual(code, 1)
        self.assertIn("approved context missing: docs/context/wi-03.bundle.json", out)

    def test_a_sidecar_with_a_changed_digest_but_a_receipt_that_follows_it_still_fails_on_the_bundle(self):
        project = Released(self.base)
        it = next(i for i in project.plan["items"] if i["id"] == 6)
        md_path, js_path = project.bundle_paths(it)
        md_path.write_bytes(md_path.read_bytes() + b"An added line.\n")   # the bundle changed, the receipt is rebuilt to match
        project.write_receipt()
        code, out = project.check()
        self.assertEqual(code, 1)
        self.assertIn("does not match content_sha256 in docs/context/wi-06.bundle.json", out)

    def test_no_receipt_an_expired_one_or_a_replaced_one_fails(self):
        project = Released(self.base)
        project.receipt_path.unlink()
        code, out = project.check()
        self.assertEqual(code, 1)
        self.assertIn("no active receipt in docs/release/ lists docs/context/wi-01.md", out)
        for label, kwargs in (("expired", {"expires_at": "2020-01-01T00:00:00Z"}), ("superseded", {"state": "superseded"})):
            with self.subTest(label):
                project.write_receipt(**kwargs)
                code, out = project.check()
                self.assertEqual(code, 1, out)
                self.assertIn("no active receipt", out)
                if label == "expired":
                    self.assertIn("has expired", out)

    def test_a_receipt_that_is_not_canonical_or_not_named_after_its_request_fails_closed(self):
        project = Released(self.base)
        original = project.receipt_path.read_bytes()
        project.receipt_path.write_bytes(original.replace(b'"state":"active"', b'"state": "active"'))
        code, out = project.check()
        self.assertEqual(code, 1)
        self.assertRegex(out, r"docs/release/[0-9a-f]{64}\.receipt\.json is not a valid receipt \(")
        project.receipt_path.write_bytes(original)
        renamed = project.receipt_path.with_name("0" * 64 + ".receipt.json")
        project.receipt_path.rename(renamed)
        code, out = project.check()
        self.assertEqual(code, 1)
        self.assertIn("is not named after its request id", out)

    def test_a_receipt_that_lists_another_digest_for_a_bundle_does_not_cover_it(self):
        project = Released(self.base)
        receipt = json.loads(project.receipt_path.read_bytes())
        entry = next(a for a in receipt["artifacts"] if a["path"] == "docs/context/wi-06.md")
        entry["sha256"] = "0" * 64
        project.receipt_path.write_bytes(RS.canonical_json(receipt))
        code, out = project.check()
        self.assertEqual(code, 1)
        self.assertIn("no active receipt in docs/release/ lists docs/context/wi-06.md with its current digest", out)

    def test_links_into_the_renderings_are_not_broken_when_the_bundle_covers_the_section(self):
        project = Released(self.base)
        code, out = project.check()
        self.assertNotIn("broken relative link", out)
        spec = next(L.spec_path(project.plan, project.root, i) for i in project.plan["items"] if i["id"] == 6)
        self.assertIn("](../../ground-truth/architecture.md#35-routing)", spec.read_text(encoding="utf-8"))
        # a link to a section the bundle does not hold is still broken
        spec.write_text(spec.read_text(encoding="utf-8").replace("## Decisions recorded", "- [Section 9.9, Elsewhere](../../ground-truth/architecture.md#99-elsewhere)\n\n## Decisions recorded"), encoding="utf-8")
        code, out = project.check()
        self.assertEqual(code, 1)
        self.assertIn("broken relative link ../../ground-truth/architecture.md#99-elsewhere", out)

    def test_a_references_citation_is_satisfied_by_the_bundle_in_the_released_view(self):
        project = Released(self.base)
        it = next(i for i in project.plan["items"] if i["id"] == 6)
        spec = L.spec_path(project.plan, project.root, it)
        text = spec.read_text(encoding="utf-8")
        refs = text.split("## References\n", 1)[1].split("\n## ", 1)[0]
        text = text.replace(refs, "\n- architecture section 3.5, Routing\n- architecture section 4.1\n- company-governance section 2.3, Approval limits\n\n")
        spec.write_text(text, encoding="utf-8")
        code, out = project.check()
        self.assertEqual(code, 0, out)
        spec.write_text(text.replace("- architecture section 4.1\n", "- architecture section 4.1\n- architecture section 8.8, Not bundled\n"), encoding="utf-8")
        code, out = project.check()
        self.assertEqual(code, 1)
        self.assertIn("obligation not in the approved context: architecture 8.8", out)
        spec.write_text(text.replace("- architecture section 4.1\n", "- nowhere section 1.1\n"), encoding="utf-8")
        code, out = project.check()
        self.assertIn("References cites unknown source nowhere", out)

    def test_findings_name_ids_and_never_bundle_text(self):
        project = Released(self.base, drop={("WI-06", "company-governance", "2.3")})
        it = next(i for i in project.plan["items"] if i["id"] == 6)
        _, body = rendering_section(project.renderings["company-governance"], "2.3")
        code, out = project.check()
        self.assertEqual(code, 1)
        for line in body.split("\n"):
            if len(line.strip()) > 20:
                self.assertNotIn(line.strip(), out)
        code, out = project.check("--json")
        self.assertIn("company-governance 2.3", out)

    def test_forcing_a_view_that_the_plan_does_not_declare_is_a_finding(self):
        project = Released(self.base)
        code, out = project.check("--view", "workspace")
        self.assertEqual(code, 1)
        self.assertIn("schema-view-mismatch", out)
        code, out = check("--root", SAMPLE, "--view", "released")
        self.assertEqual(code, 1)
        self.assertIn("schema-view-mismatch", out)
        self.assertIn("no active receipt in docs/release/ lists docs/context/wi-01.md", out)   # the released rules ran: the sample has bundles and no receipt yet


class WorkspaceViewTests(WithTemp):
    def sample(self, name="sample"):
        proj = self.base / name
        shutil.copytree(SAMPLE, proj)
        return proj

    def test_the_sample_still_passes_with_no_findings(self):
        code, out = check("--root", SAMPLE)
        self.assertEqual(code, 0, out)
        self.assertIn("0 with findings", out)

    def test_an_original_is_not_required_unless_the_owner_asks(self):
        proj = self.sample()
        shutil.rmtree(proj / "ground-truth")
        code, out = check("--root", proj)
        self.assertEqual(code, 0, out)
        code, out = check("--root", proj, "--check-originals")
        self.assertEqual(code, 1)
        self.assertIn("ground truth source not found: ground-truth/architecture.md", out)

    def test_a_rendering_in_the_private_workspace_is_enough(self):
        proj = self.sample()
        ws = self.base / "ws"
        (ws / "renderings").mkdir(parents=True)
        shutil.move(str(proj / "docs/ground-truth/architecture.md"), str(ws / "renderings/architecture.md"))
        code, out = check("--root", proj)
        self.assertEqual(code, 1)
        self.assertIn("ground truth citations not checked", out)   # nothing to read, nothing claimed
        (proj / ".carrydown").mkdir()
        (proj / ".carrydown/local.yaml").write_text(f"workspace: {ws}\n", encoding="utf-8")
        code, out = check("--root", proj)
        self.assertEqual(code, 0, out)

    def test_a_references_citation_is_satisfied_by_the_rendering(self):
        proj = self.sample()
        spec = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        text = spec.read_text(encoding="utf-8")
        spec.write_text(text.replace("## Decisions recorded", "## Decisions recorded", 1), encoding="utf-8")
        refs = text.split("## References\n", 1)[1].split("\n## ", 1)[0]
        good = text.replace(refs, "\n- architecture section 3.1, Overview\n- architecture section 3.2\n\n")
        spec.write_text(good, encoding="utf-8")
        code, out = check("--root", proj)
        self.assertEqual(code, 0, out)
        spec.write_text(good.replace("- architecture section 3.2\n", "- architecture section 99.9, Nothing\n"), encoding="utf-8")
        code, out = check("--root", proj)
        self.assertEqual(code, 1)
        self.assertIn("References cites architecture section 99.9 at line", out)

    def test_the_legacy_rules_keep_requiring_the_original(self):
        plan, _ = L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)
        proj = self.sample()
        shutil.rmtree(proj / "ground-truth")
        heads = CS.ground_truth_headings(plan, proj)
        found = CS.citation_findings(plan, proj, heads, "legacy")
        self.assertTrue(any(f.startswith("ground truth source not found") for f in found), found)
        self.assertEqual(CS.citation_findings(plan, proj, heads, "workspace"), [])
        self.assertEqual(CS.citation_findings(plan, proj, {}, "released"), [])


@unittest.skipUnless(GIT, "git is not installed")
class TrackedSourceTests(WithTemp):
    def repo(self):
        proj = self.base / "repo"
        shutil.copytree(FIXTURE, proj, ignore=shutil.ignore_patterns("__pycache__"))
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
            subprocess.run(["git", "-C", str(proj)] + args, check=True, capture_output=True)
        plan, _ = L.load_plan(proj / "docs/spec/plan.yaml", proj)
        return proj, plan

    def add(self, proj, *paths):
        subprocess.run(["git", "-C", str(proj), "add", "--"] + list(paths), check=True, capture_output=True)

    def test_a_tracked_restricted_source_is_reported_by_id_and_never_by_path(self):
        proj, plan = self.repo()
        self.assertEqual(CS.tracked_source_findings(plan, proj), [])   # nothing is tracked yet
        self.add(proj, "ground-truth/company-governance.md")
        found = CS.tracked_source_findings(plan, proj)
        self.assertEqual(found, ["restricted source is tracked in git: company-governance"])
        for text in found:
            self.assertNotIn("ground-truth", text)
            self.assertNotIn(".md", text)

    def test_the_rendering_and_the_docs_source_folder_count_too(self):
        proj, plan = self.repo()
        text = (proj / "docs/spec/plan.yaml").read_text(encoding="utf-8")
        (proj / "docs/spec/plan.yaml").write_text(text.replace("source_path: ground-truth/company-governance.md", "source_path: docs/source/company-governance.docx"), encoding="utf-8")
        plan, _ = L.load_plan(proj / "docs/spec/plan.yaml", proj)
        (proj / "docs/source").mkdir()
        (proj / "docs/source/company-governance.docx").write_bytes(b"binary")
        self.add(proj, "docs/source/company-governance.docx")
        found = CS.tracked_source_findings(plan, proj)
        self.assertEqual(found, ["restricted source is tracked in git: company-governance"])
        self.assertNotIn("docs/source", found[0])
        subprocess.run(["git", "-C", str(proj), "rm", "-q", "--cached", "--", "docs/source/company-governance.docx"], check=True, capture_output=True)
        self.add(proj, "docs/ground-truth/company-governance.md")
        self.assertEqual(CS.tracked_source_findings(plan, proj), ["restricted source is tracked in git: company-governance"])

    def test_a_source_that_is_not_restricted_is_not_reported(self):
        proj, plan = self.repo()
        self.add(proj, "ground-truth/architecture.md", "docs/ground-truth/architecture.md")
        self.assertEqual(CS.tracked_source_findings(plan, proj), [])

    def test_only_non_empty_known_paths_reach_git(self):
        proj, plan = self.repo()
        calls = []

        def fake(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        pathless = copy.deepcopy(plan)
        for source in pathless["sources"]:
            source["source_path"] = ""
            source["path"] = "   "
        with mock.patch.object(subprocess, "run", fake):
            self.assertEqual(CS.tracked_source_findings(pathless, proj), [])
            self.assertEqual(calls, [])   # no known path: no command, never an empty pathspec
            CS.tracked_source_findings(plan, proj)
        self.assertEqual(len(calls), 1)
        pathspecs = calls[0][calls[0].index("--") + 1:]
        self.assertTrue(pathspecs and all(p.strip() and p != ":(literal)" for p in pathspecs), calls[0])
        self.assertEqual(calls[0][:5], ["git", "-C", str(proj), "ls-files", "-z"])

    def test_without_git_the_check_says_it_was_not_performed(self):
        proj, plan = self.repo()
        with mock.patch.object(shutil, "which", lambda name: None):
            found = CS.tracked_source_findings(plan, proj)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith(CS.NOT_PERFORMED), found)
        self.assertNotIn("verified: ", found[0])
        elsewhere = self.base / "plain"
        shutil.copytree(FIXTURE, elsewhere, ignore=shutil.ignore_patterns("__pycache__"))
        with mock.patch.dict("os.environ", {"GIT_CEILING_DIRECTORIES": str(self.base)}):
            found = CS.tracked_source_findings(plan, elsewhere)
        self.assertTrue(found and found[0].startswith(CS.NOT_PERFORMED), found)

    def test_the_checker_runs_the_check_only_where_the_private_workspace_is(self):
        proj, plan = self.repo()
        self.add(proj, "ground-truth/company-governance.md")
        code, out = check("--root", proj)
        self.assertEqual(code, 0, out)   # a clone has no workspace pointer, so this owner-side check does not run
        ws = self.base / "ws"
        ws.mkdir()
        (proj / ".carrydown").mkdir()
        (proj / ".carrydown/local.yaml").write_text(f"workspace: {ws}\n", encoding="utf-8")
        code, out = check("--root", proj)
        self.assertEqual(code, 1)
        self.assertIn("restricted source is tracked in git: company-governance", out)
        self.assertNotIn("ground-truth/company-governance", out.replace("rendered", ""))


class LogHygieneTests(WithTemp):
    def sample(self):
        proj = self.base / "sample"
        shutil.copytree(SAMPLE, proj)
        return proj

    def test_a_banned_name_prints_the_file_and_line_and_no_excerpt(self):
        proj = self.sample()
        spec = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\nQuestions go to tamsin before Friday.\n", encoding="utf-8")
        for flags in ([], ["--json"]):
            code, out = check("--root", proj, *flags)
            self.assertEqual(code, 1)
            self.assertRegex(out, r"person name or handle from the plan at docs/spec/m1-submit-report/wi-01-service-scaffold\.md:\d+")
            self.assertNotIn("tamsin before", out)
            self.assertNotIn("Questions go", out)
        pats = CS.banned_patterns(L.load_plan(SAMPLE / "docs/spec/plan.yaml", SAMPLE)[0])
        hits = CS.banned_hits(pats, "Ask tamsin.\n")
        self.assertEqual([(why, ln, text) for why, ln, text in hits], [("person name or handle from the plan", 1, "")])
        self.assertEqual(CS.banned_issue("person name or handle from the plan", Path("docs/a.md"), 4), "person name or handle from the plan at docs/a.md:4")

    def test_a_header_row_mismatch_prints_the_row_label_only(self):
        proj = self.sample()
        spec = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        text = spec.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^\| Target \| .* \|$", "| Target | SECRETVALUE-TARGET |", text)
        text = re.sub(r"(?m)^\| Depends on \| .* \|$", "| Depends on | SECRETVALUE-DEPENDS |", text)
        text = text.replace("# WI-01 ", "# WI-01 SECRETVALUE-TITLE ", 1)
        spec.write_text(text, encoding="utf-8")
        for flags in ([], ["--json"]):
            code, out = check("--root", proj, *flags)
            self.assertEqual(code, 1)
            self.assertIn("Target row does not match plan.yaml", out)
            self.assertIn("title line does not match the plan", out)
            self.assertNotIn("SECRETVALUE", out)

    def test_shape_errors_name_the_person_and_the_key_and_never_the_record(self):
        secret = "Secret Person Name"
        legacy = {"people": [{"id": "tamsin", "name": [secret], "track": "workflow", "skills": {"a": secret}, "days_off": {"b": secret}},
                             "Another " + secret, {"id": ["x" + secret], "name": "ok"}],
                  "advisors": [{"id": "noor", "name": {"c": secret}}, [secret]]}
        problems = L.type_problems(legacy)
        text = "\n".join(problems)
        self.assertNotIn(secret, text)
        self.assertNotIn("Another", text)
        self.assertIn("person tamsin: name has the wrong type", problems)
        self.assertIn("person tamsin: skills has the wrong type", problems)
        self.assertIn("person tamsin: days_off has the wrong type", problems)
        self.assertIn("person #3: id has the wrong type", problems)
        self.assertIn("advisor noor: name has the wrong type", problems)
        self.assertTrue(any(p.startswith("people: entry 2 must be a mapping") for p in problems), problems)
        self.assertTrue(any(p.startswith("advisors: entry 2 must be a mapping") for p in problems), problems)

    def test_validate_plan_does_not_dump_a_track_checkpoint_or_external_record(self):
        secret = "ZZ-secret-text"
        text = (SAMPLE / "docs/spec/plan.yaml").read_text(encoding="utf-8")
        proj = self.sample()
        plan_path = proj / "docs/spec/plan.yaml"
        broken = text.replace("  - id: workflow\n    label: Workflow\n", f"  - id: workflow\n    note: {secret}\n", 1)
        self.assertNotEqual(broken, text)
        plan_path.write_text(broken, encoding="utf-8")
        for flags in ([], ["--json"]):
            code, out = check("--root", proj, *flags)
            self.assertEqual(code, 1)
            self.assertIn("tracks: each track needs id and label (track entry 1)", out)
            self.assertNotIn(secret, out)
        checkpoints = text.replace("  - date: 2027-02-05\n    name: \"Contract freeze\"\n", f"  - date: 2027-02-05\n    note: {secret}\n", 1)
        self.assertNotEqual(checkpoints, text)
        plan_path.write_text(checkpoints, encoding="utf-8")
        code, out = check("--root", proj)
        self.assertIn("checkpoints: need date and name (checkpoint entry 1)", out)
        self.assertNotIn(secret, out)

    def test_the_plan_review_report_is_scanned_for_the_names_in_the_plan(self):
        proj = self.sample()
        code, out = check("--root", proj)
        self.assertEqual(code, 0, out)
        review = proj / "docs/spec/plan-review.md"
        review.write_text("# Plan review\n\nIdris should take the inbox. Ask tamsin about the rest.\n", encoding="utf-8")
        for flags in ([], ["--json"]):
            code, out = check("--root", proj, *flags)
            self.assertEqual(code, 1)
            self.assertRegex(out, r"person name or handle from the plan at docs/spec/plan-review\.md:3")
            self.assertNotIn("Ask tamsin", out)
        review.write_text("# Plan review\n\nThe plan reads well.\n", encoding="utf-8")
        self.assertEqual(check("--root", proj)[0], 0)

    def test_a_detector_finding_in_the_checker_gives_the_location_and_not_the_text(self):
        proj = self.sample()
        spec = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        token = "ghp_ABCDEFGHIJKLMNOP1234567890"
        spec.write_text(spec.read_text(encoding="utf-8") + f"\nUse {token} for it.\n", encoding="utf-8")
        for flags in ([], ["--json"]):
            code, out = check("--root", proj, *flags)
            self.assertEqual(code, 1)
            self.assertRegex(out, r"detector:credentials:github-token at docs/spec/m1-submit-report/wi-01-service-scaffold\.md:\d+")
            self.assertNotIn(token, out)
            self.assertNotIn("detectors: no findings", out)
        code, out = check("--root", SAMPLE)
        self.assertIn("detectors: no findings (this does not prove safety)", out)
        self.assertNotIn("detectors: no findings", check("--root", SAMPLE, "--quiet")[1])

    def test_the_owner_side_detectors_run_in_the_checker_where_the_workspace_is(self):
        proj = self.base / "fixture"
        shutil.copytree(FIXTURE, proj, ignore=shutil.ignore_patterns("__pycache__"))
        ws = self.base / "ws"
        ws.mkdir()
        (ws / "phrases.txt").write_text("Harbor Finance Group\n", encoding="utf-8")
        (proj / ".carrydown").mkdir()
        (proj / ".carrydown/local.yaml").write_text(f"workspace: {ws}\n", encoding="utf-8")
        text = (FIXTURE / "docs/ground-truth/company-governance.md").read_text(encoding="utf-8")
        passage = " ".join(text.split("### 2.3 Approval limits", 1)[1].split("###", 1)[0].split()[:20])
        spec = proj / "docs/spec/m3-enforce-policy/wi-07-audit-log.md"
        spec.write_text(spec.read_text(encoding="utf-8") + f"\n{passage}\n", encoding="utf-8")
        code, out = check("--root", proj)
        self.assertEqual(code, 1)
        self.assertRegex(out, r"detector:copied_restricted:copied-passage at docs/spec/m3-enforce-policy/wi-07-audit-log\.md:\d+ \(passage_sha256 [0-9a-f]{64}\)")
        self.assertNotIn(passage[:40], out)
        other = proj / "docs/spec/m1-submit-report/wi-01-service-scaffold.md"
        other.write_text(other.read_text(encoding="utf-8") + "\nWritten for HARBOR finance group staff.\n", encoding="utf-8")
        code, out = check("--root", proj)
        self.assertRegex(out, r"detector:org_phrases:organization-phrase at docs/spec/m1-submit-report/wi-01-service-scaffold\.md:\d+ \(passage_sha256 [0-9a-f]{64}\)")
        self.assertNotIn("HARBOR", out)
        other.write_text(other.read_text(encoding="utf-8").replace("Written for HARBOR finance group staff.", ""), encoding="utf-8")
        # the bundle of a work item may quote the restricted section it was approved for
        bundle = proj / "docs/context"
        bundle.mkdir()
        (bundle / "wi-06.md").write_text(f"# Approved context\n\n{passage}\n", encoding="utf-8")
        spec.write_text(spec.read_text(encoding="utf-8").replace(passage, ""), encoding="utf-8")
        code, out = check("--root", proj)
        self.assertNotIn("copied_restricted", out)

    def test_json_output_follows_the_same_rules(self):
        code, out = check("--root", SAMPLE, "--json")
        data = json.loads(out)
        self.assertEqual((code, data["findings"]), (0, {}))
        self.assertIn(CS.D.CLEAN_LINE, data["notes"])


class ScaffoldIgnoreTests(WithTemp):
    LINES = ["docs/source/", "people.yaml", ".carrydown/local.yaml", ".carrydown/cache/"]

    def init(self, proj, *flags):
        return run(SCAFFOLD, "--root", proj, "--init", "--name", "Test project", "--allow-no-git", *flags)

    def test_a_dry_run_says_would_append_and_writes_nothing(self):
        proj = self.base / "p"
        proj.mkdir()
        code, out = self.init(proj)
        self.assertEqual(code, 0, out)
        for line in self.LINES:
            self.assertIn(f"would append to .gitignore: {line}", out)
        self.assertFalse((proj / ".gitignore").exists())
        self.assertFalse((proj / "docs/spec/plan.yaml").exists())

    def test_apply_appends_each_line_once_and_prints_it(self):
        proj = self.base / "p"
        proj.mkdir()
        (proj / ".gitignore").write_text("__pycache__/\n*.pyc", encoding="utf-8")   # no trailing newline
        code, out = self.init(proj, "--apply")
        self.assertEqual(code, 0, out)
        for line in self.LINES:
            self.assertIn(f"appending to .gitignore: {line}", out)
        lines = (proj / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["__pycache__/", "*.pyc"] + self.LINES)
        code, out = self.init(proj, "--apply", "--force")
        self.assertNotIn("appending to", out)
        self.assertIn("already holds", out)
        self.assertEqual((proj / ".gitignore").read_text(encoding="utf-8").splitlines(), ["__pycache__/", "*.pyc"] + self.LINES)

    def test_the_pointer_line_that_workspace_init_wrote_is_not_added_twice(self):
        proj = self.base / "p"
        proj.mkdir()
        (proj / ".gitignore").write_text(".carrydown/local.yaml\n", encoding="utf-8")
        code, out = self.init(proj, "--apply")
        self.assertEqual(code, 0, out)
        self.assertNotIn(".gitignore: .carrydown/local.yaml", out)
        self.assertEqual((proj / ".gitignore").read_text(encoding="utf-8").splitlines().count(".carrydown/local.yaml"), 1)

    def test_a_plan_that_exists_is_left_alone_and_so_is_the_ignore_file(self):
        proj = self.base / "p"
        proj.mkdir()
        self.assertEqual(self.init(proj, "--apply")[0], 0)
        (proj / ".gitignore").write_text("", encoding="utf-8")
        code, out = self.init(proj, "--apply")
        self.assertEqual(code, 1)
        self.assertEqual((proj / ".gitignore").read_text(encoding="utf-8"), "")


class TemplateAndCopyTests(WithTemp):
    def test_the_workflow_watches_bundles_and_receipts_and_reads_only(self):
        text = (ROOT / "templates/check-specs-workflow.yml").read_text(encoding="utf-8")
        self.assertEqual(text.count('- "docs/context/**"'), 2)
        self.assertEqual(text.count('- "docs/release/**"'), 2)
        self.assertIn("contents: read", text)
        self.assertNotIn("write", text.split("permissions:", 1)[1].split("jobs:", 1)[0])

    def test_the_ci_copy_carries_every_module_the_checker_imports_and_runs(self):
        proj = self.base / "ci"
        shutil.copytree(SAMPLE, proj, ignore=shutil.ignore_patterns("tools", ".github"))
        code, out = run(SCAFFOLD, "--root", proj, "--apply", "--ci", "--allow-no-git")
        self.assertEqual(code, 0, out)
        copied = sorted(p.name for p in (proj / "tools/carrydown").glob("*.py"))
        self.assertEqual(copied, ["carrydown_lib.py", "check_specs.py", "detectors.py", "release_schema.py"])
        code, out = run(proj / "tools/carrydown/check_specs.py", "--root", proj, cwd=self.base)
        self.assertEqual(code, 0, out)
        self.assertIn("0 with findings", out)
        flow = (proj / ".github/workflows/check-specs.yml").read_text(encoding="utf-8")
        self.assertIn("docs/context/**", flow)

    def test_the_sample_copy_is_listed_for_the_sync(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import sync_skill_assets as SYNC
        sources = [src for src, _ in SYNC.SAMPLE_COPIES]
        for name in ("check_specs.py", "carrydown_lib.py", "release_schema.py", "detectors.py"):
            self.assertIn(f"scripts/{name}", sources)
        for _, dst in SYNC.SAMPLE_COPIES:
            self.assertTrue((ROOT / dst).is_file(), dst)
        self.assertEqual(SYNC.problems(), [])


if __name__ == "__main__":
    unittest.main()
