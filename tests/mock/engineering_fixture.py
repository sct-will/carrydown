"""An enrolled engineering repository with a real exported release, for the verifier tests. Standard library only.

Exported(base) runs the whole "no" path once against the fictional organization of fake_evidence: prepare,
approve in the staging repository, merge, export. It keeps the exported files and the organization.
Case(exported) is one test's copy: a deep copy of the organization with the engineering repository
holding only its policy pointer, and helpers that open pull requests against it.

  exported = Exported(tmp)         about four seconds; build it once per test class
  case = Case(exported)            a fresh organization and engineering repository
  n = case.open()                  the export as a pull request
  n = case.open(edit={path: new})  the export with some files replaced or added (None deletes)
  case.enrollment()                the current captured policy
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "mock"))
import fake_evidence as FE  # noqa: E402
import release_fixture as F  # noqa: E402
import release_schema as RS  # noqa: E402

POINTER = ".carrydown/release-policy.yaml"


class Exported:
    def __init__(self, base, expires=None, world=None):
        self.np = F.NoProject(base, world=world).start()
        extra = ["--expires", expires] if expires else []
        code, out, err = self.np.prepare(*extra)
        assert code == 0, out + err
        code, out, err = self.np.approve()
        assert code == 0, out + err
        self.np.land()
        code, out, err = self.np.export()
        assert code == 0, out + err
        self.world = self.np.world
        self.rid = self.np.request_id
        self.files = self._tree(f"carrydown/request-{self.rid}")
        self.pointer = self.files.pop(POINTER)[1]
        for plain in ("README.md", ".gitignore"):
            self.files.pop(plain, None)
        self.np.stop()

    def _tree(self, branch):
        listing = F.sh(["git", "ls-tree", "-r", "-z", branch], self.np.root).stdout
        out = {}
        for row in filter(None, listing.split("\0")):
            meta, path = row.split("\t", 1)
            mode, kind, sha = meta.split()
            out[path] = (mode, _blob_bytes(self.np.root, sha))
        return out

    @property
    def receipt_path(self):
        return f"docs/release/{self.rid}.receipt.json"


def _blob_bytes(root, sha):
    import subprocess
    return subprocess.run(["git", "-C", str(root), "cat-file", "blob", sha], capture_output=True, check=True).stdout


class Case:
    """A fresh copy of the organization with the exported release available as a pull request."""

    def __init__(self, exported):
        self.exported = exported
        self.world = copy.deepcopy(exported.world)
        self.reader = self.world.reader
        self.reader.set_file(FE.ENGINEERING_ID, "README.md", b"engineering repository\n")
        self.reader.set_file(FE.ENGINEERING_ID, POINTER, exported.pointer)
        self.rid = exported.rid
        self.files = dict(exported.files)

    def enrollment(self):
        return self.world.enrollment()

    def open(self, edit=None, drop=(), branch=None, user=FE.OWNER, base_sha=None, only=None):
        """The export as a pull request. edit replaces or adds files (a path to bytes or to (mode, bytes)); None
        deletes the path from the branch. drop leaves an exported file out. only replaces the export with
        exactly these files."""
        files = dict(self.files if only is None else {})
        for path in drop:
            files.pop(path, None)
        for path, value in dict(only or {}, **(edit or {})).items():
            if value is None or isinstance(value, tuple):
                files[path] = value
            else:
                files[path] = ("100644", value)
        name = branch or f"carrydown/request-{self.rid}-{len(self.reader.repos[FE.ENGINEERING_ID]['prs'])}"
        return self.reader.open_pr(FE.ENGINEERING_ID, name, files, user=user, base_sha=base_sha)

    def merge(self, number):
        return self.reader.merge(FE.ENGINEERING_ID, number)

    def content_of(self, path):
        return self.files[path][1]

    def withdraw(self, approve=True):
        """Withdraw the active request through a reviewed state branch in the staging repository."""
        import release_build as B
        import release_verify as V
        enrollment = self.enrollment()
        history = V.replay_staging(self.reader, enrollment)
        event = B.withdrawal_event(self.rid, enrollment, history.replay.tip, "error-found", created=self.reader.tick(), nonce=B.new_nonce())
        return self.world.land(B.state_branch_files(event), f"state/{event['event_id']}", approve=approve)

    def candidate(self, **kw):
        """A replacement candidate for the same organization (supersedes the exported request)."""
        return FE.make_candidate(self.world, supersedes=self.rid, **kw)
