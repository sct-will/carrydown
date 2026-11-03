#!/usr/bin/env python3
"""A re-runnable proof of the work package 13 claims (the Python preflight). Standard library only.

Run it from the repository root, with no token and no network:

  python3 tests/proof_wp13.py

It runs scripts/check_python.py as a real process and reads the output. For each claim it prints PASS or
FAIL, then the line it observed. It exits 0 only when every claim passes. It claims:

  1. check_python.py exits 0 under the Python that runs this proof and under Python 3.9.21: the path in the
     environment variable CARRYDOWN_PY39, else .pyenv/versions/3.9.21/bin/python3 under the home folder of
     the account that runs the proof, read from the account database so that an emptied HOME does not hide
     it. When neither exists the claim is skipped with its reason, printed as SKIP, and is not counted.
  2. under a stub that pretends to be Python 3.6 it exits 2 and prints the link of the system it
     detected and no link of any other system, for macOS, Windows 64-bit, Windows ARM64 and Linux
  3. a stub that is not a real Python (no executable) exits 2 and prints the same single-system answer
  4. the preflight page is in both skills and in a freshly generated engineers' skill, and each copy is
     the canonical templates/preflight.md, byte for byte; so is check_python.py in all three places
  5. both installed skills start with the preflight step; the engineers' skill starts with one command,
     check_context.py, and sends the agent to the preflight only when that command cannot run
  6. no Markdown, template or skill file shows the macOS and Linux command form and the Windows command
     form on one line
  7. the six official links are present verbatim in check_python.py, in the preflight page and in
     docs/setup.md
  8. the first skill and the generated engineers' skill carry no network code
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
PYENV_39 = Path(".pyenv") / "versions" / "3.9.21" / "bin" / "python3"
RESULTS = []
SKIPPED = []


class Skip(Exception):
    """A claim that cannot run here, with the reason. It is printed as SKIP and not counted."""


def account_home():
    """The home folder of the account that runs the proof, from the account database (not from HOME), or None."""
    try:
        import pwd
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError, AttributeError, OSError):
        return None


def python39():
    """(path, where it came from) of the Python 3.9 to test, or (None, why there is none)."""
    named = os.environ.get("CARRYDOWN_PY39")
    if named:
        return named, "CARRYDOWN_PY39"
    home = account_home()
    if home is not None and (home / PYENV_39).is_file():
        return str(home / PYENV_39), "the account's home folder"
    where = f"{home / PYENV_39}" if home is not None else "the account's home folder (no account database on this system)"
    return None, f"CARRYDOWN_PY39 is not set and there is no Python 3.9.21 at {where}"

MACOS_PKG = "https://www.python.org/ftp/python/3.15.2/python-3.15.2-macos11.pkg"
WIN_AMD64 = "https://www.python.org/ftp/python/3.15.2/python-3.15.2-amd64.exe"
WIN_ARM64 = "https://www.python.org/ftp/python/3.15.2/python-3.15.2-arm64.exe"
RELEASE = "https://www.python.org/downloads/release/python-3152/"
MAC_LANDING = "https://www.python.org/downloads/macos/"
WIN_LANDING = "https://www.python.org/downloads/windows/"
SIX = (MACOS_PKG, WIN_AMD64, WIN_ARM64, RELEASE, MAC_LANDING, WIN_LANDING)
NETWORK_MODULES = {"urllib", "http", "socket", "ssl", "ftplib", "smtplib", "requests", "xmlrpc"}

# A stub that behaves as an old interpreter on a chosen system: it patches the version, the platform and the
# processor, then runs the real script. argv: system (darwin, win32, linux), processor, version or "none".
STUB = '''
import argparse, gettext, os, platform, runpy, shutil, sys   # imported before sys.platform changes
system, machine, version = sys.argv[1:4]
sys.argv = [sys.argv[4]] + sys.argv[5:]
sys.platform = system
platform.machine = lambda: machine
if version == "none":
    sys.executable = ""
else:
    sys.version_info = tuple(int(x) for x in version.split(".")) + ("final", 0)
runpy.run_path(sys.argv[0], run_name="__main__")
'''


def claim(text):
    def wrap(fn):
        try:
            observed = fn()
            RESULTS.append(True)
            print(f"PASS {text}")
            print(f"     observed: {observed}")
        except Skip as e:
            SKIPPED.append(text)
            print(f"SKIP {text}")
            print(f"     reason: {e}")
        except Exception as e:     # a failed claim is reported, and the rest still run
            RESULTS.append(False)
            print(f"FAIL {text}")
            print(f"     observed: {type(e).__name__}: {e}")
        return fn
    return wrap


def run(argv, cwd=ROOT):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env.update(PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([str(a) for a in argv], cwd=str(cwd), capture_output=True, text=True, env=env, timeout=180)


def first_line(text):
    return (text.strip().splitlines() or [""])[0]


def pretend(tmp, system, machine, version):
    stub = Path(tmp) / "fake_python.py"
    stub.write_text(STUB, encoding="utf-8")
    return run([PY, stub, system, machine, version, ROOT / "scripts" / "check_python.py"])


def repo_text_files():
    out = []
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "specs", "__pycache__", "node_modules")]
        for f in files:
            if f.endswith((".md", ".tmpl")):
                out.append(Path(dirpath) / f)
    return out


def generated_skill(tmp):
    """Generate the engineers' skill for a copy of the sample that has none yet. Returns the skill folder."""
    sys.path.insert(0, str(ROOT / "tests" / "mock"))
    from sample_tree import copy_sample
    project = copy_sample(Path(tmp) / "project", ignore=shutil.ignore_patterns("dev", "release"))
    done = run([PY, ROOT / "scripts" / "generate_dev_skill.py", "--root", project, "--apply"])
    if done.returncode != 0:
        raise AssertionError(done.stdout + done.stderr)
    return project / "docs" / "dev" / "skills" / "expense-approvals-dev"


@claim("check_python.py exits 0 under the Python that runs this proof")
def _():
    r = run([PY, ROOT / "scripts" / "check_python.py"])
    assert r.returncode == 0, r.stdout + r.stderr
    return first_line(r.stdout)


@claim("the Python 3.9 this proof tests is found the same way with HOME emptied: from CARRYDOWN_PY39 or the account database, never from HOME")
def _():
    saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
    with tempfile.TemporaryDirectory(prefix="carrydown-empty-home-") as empty:
        try:
            os.environ["HOME"] = os.environ["USERPROFILE"] = empty
            emptied = python39()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    normal = python39()
    assert emptied == normal, f"with HOME emptied: {emptied}; with HOME set: {normal}"
    assert emptied[0] is None or empty not in emptied[0], emptied
    return f"{emptied[0] or 'none'} from {emptied[1]}" if emptied[0] else f"none: {emptied[1]}"


@claim("check_python.py exits 0 under Python 3.9.21")
def _():
    path, source = python39()
    if path is None:
        raise Skip(source)
    assert Path(path).is_file(), f"{path} (from {source}) is not a file. Set CARRYDOWN_PY39 to a Python 3.9"
    r = run([path, ROOT / "scripts" / "check_python.py"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Python 3.9." in r.stdout, r.stdout
    return f"{first_line(r.stdout)} (interpreter from {source})"


@claim("an old interpreter exits 2 and prints the link of its own system only")
def _():
    cases = [("darwin", "arm64", "macOS", [MACOS_PKG, MAC_LANDING], [WIN_AMD64, WIN_ARM64, WIN_LANDING, "python.exe"]),
             ("win32", "AMD64", "Windows", [WIN_AMD64, WIN_LANDING], [MACOS_PKG, WIN_ARM64, MAC_LANDING, "xcode"]),
             ("win32", "ARM64", "Windows", [WIN_ARM64, WIN_LANDING], [MACOS_PKG, WIN_AMD64, MAC_LANDING, "xcode"]),
             ("linux", "x86_64", "Linux", [RELEASE], [MACOS_PKG, WIN_AMD64, WIN_ARM64, MAC_LANDING, WIN_LANDING])]
    seen = []
    with tempfile.TemporaryDirectory() as tmp:
        for system, machine, label, wants, forbids in cases:
            r = pretend(tmp, system, machine, "3.6.9")
            assert r.returncode == 2, f"{label}: exit {r.returncode}\n{r.stdout}{r.stderr}"
            assert f"This is Python 3.6.9 ({label})" in r.stdout, r.stdout
            for w in wants:
                assert w in r.stdout, f"{label}: {w} missing\n{r.stdout}"
            for f in forbids:
                assert f not in r.stdout, f"{label}: {f} must not be shown\n{r.stdout}"
            seen.append(f"{label}/{machine}: exit 2, {wants[0].rsplit('/', 1)[-1]}")
    return "; ".join(seen)


@claim("Python 3.8 is refused and Python 3.9.0 is accepted")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        old = pretend(tmp, "darwin", "arm64", "3.8.18")
        new = pretend(tmp, "darwin", "arm64", "3.9.0")
    assert old.returncode == 2 and new.returncode == 0, (old.returncode, new.returncode)
    return f"3.8.18 -> {old.returncode}; 3.9.0 -> {new.returncode}"


@claim("a stub that is not a real Python exits 2 and prints one system's link")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        r = pretend(tmp, "win32", "AMD64", "none")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "did not start a real Python (Windows)" in r.stdout and WIN_AMD64 in r.stdout and MACOS_PKG not in r.stdout, r.stdout
    return first_line(r.stdout)


@claim("the preflight page and check_python.py are in both skills and in a generated engineers' skill, identical to the canonical files")
def _():
    page = (ROOT / "templates" / "preflight.md").read_bytes()
    script = (ROOT / "scripts" / "check_python.py").read_bytes()
    places = []
    for skill in ("carrydown-ground-truth", "carrydown-plan-to-github"):
        base = ROOT / "skills" / skill
        assert (base / "references" / "preflight.md").read_bytes() == page, f"{skill}: references/preflight.md differs"
        assert (base / "scripts" / "check_python.py").read_bytes() == script, f"{skill}: scripts/check_python.py differs"
        places.append(f"skills/{skill}")
    with tempfile.TemporaryDirectory() as tmp:
        folder = generated_skill(tmp)
        assert (folder / "references" / "preflight.md").read_bytes() == page, "generated: references/preflight.md differs"
        assert (folder / "scripts" / "check_python.py").read_bytes() == script, "generated: scripts/check_python.py differs"
        r = run([PY, folder / "scripts" / "check_python.py"], cwd=tmp)
        assert r.returncode == 0, r.stdout + r.stderr
        places.append("generated engineers' skill (and it runs: " + first_line(r.stdout) + ")")
    return "; ".join(places)


@claim("both installed skills start with the preflight step; the engineers' skill starts with check_context.py and falls back to the preflight")
def _():
    seen = []
    with tempfile.TemporaryDirectory() as tmp:
        engineers = generated_skill(tmp) / "SKILL.md"
        files = [ROOT / "skills" / "carrydown-ground-truth" / "SKILL.md", ROOT / "skills" / "carrydown-plan-to-github" / "SKILL.md", engineers]
        for f in files:
            text = f.read_text(encoding="utf-8")
            assert "references/preflight.md" in text, f"{f}: does not name references/preflight.md"
            assert "check_python.py" in text, f"{f}: does not name check_python.py"
            assert "only that system's" in text, f"{f}: does not say to show only that system's commands"
            first_script = min(i for i in (text.find("scripts/check_specs.py"), text.find("scripts/check_context.py")) if i >= 0)
            if f == engineers:
                steps = text.split("## Orient on a work item", 1)[1].split("\n## ", 1)[0]
                numbered = re.findall(r"(?m)^(\d+)\. ", steps)
                assert numbered[0] == "1" and "0" not in numbered, f"engineers' steps: {numbered}"
                commands = re.findall(r"`((?:python3|find|grep|py) [^`]*)`", steps)
                assert commands and "scripts/check_context.py" in commands[0], f"the first command is {commands[:1]}"
                step2 = re.search(r"(?ms)^2\. (.*?)^3\. ", steps).group(1)
                assert step2.index("check_context.py") < step2.index("references/preflight.md"), "the preflight is not the fallback of the check"
                assert "If no line starts with `carrydown:`" in step2, "the fallback condition is missing"
                seen.append(f"engineers' skill: first command {commands[0]!r}, preflight only when no carrydown: line")
            else:
                assert text.index("references/preflight.md") < first_script, f
                seen.append(f.parent.name + ": preflight first")
    return "; ".join(seen)


@claim("no document shows both command forms on one line")
def _():
    unix, windows = re.compile(r"\bpython3\b"), re.compile(r"\bpy -3\b")
    files = repo_text_files()
    bad = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if unix.search(line) and windows.search(line):
                bad.append(f"{f.relative_to(ROOT)}:{n}")
    assert not bad, "both forms on one line at " + ", ".join(bad)
    page = (ROOT / "templates" / "preflight.md").read_text(encoding="utf-8")
    windows_part = page.split("\n## Windows\n")[1].split("\n## Linux\n")[0]
    mac_part = page.split("\n## macOS\n")[1].split("\n## Windows\n")[0]
    assert "py -3" in windows_part and "py -3" not in mac_part and "winget" not in mac_part and "brew" not in windows_part
    return f"{len(files)} files scanned, 0 lines with both forms; the page keeps them under separate headings"


@claim("the six official links are present verbatim")
def _():
    where = [ROOT / "scripts" / "check_python.py", ROOT / "templates" / "preflight.md", ROOT / "docs" / "setup.md"]
    for f in where:
        text = f.read_text(encoding="utf-8")
        missing = [u for u in SIX if u not in text]
        assert not missing, f"{f.relative_to(ROOT)} is missing {missing}"
    assert "verified 2026-11-03" in (ROOT / "scripts" / "check_python.py").read_text(encoding="utf-8")
    return "6 of 6 links in check_python.py, templates/preflight.md and docs/setup.md; verification date in the script"


@claim("the first skill and the generated engineers' skill carry no network code")
def _():
    def imported(path):
        names = set()
        for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        return names
    first = sorted((ROOT / "skills" / "carrydown-ground-truth" / "scripts").glob("*.py"))
    assert not (ROOT / "skills" / "carrydown-ground-truth" / "scripts" / "github_client.py").exists()
    for f in first:
        bad = imported(f) & NETWORK_MODULES
        assert not bad, f"{f.name} imports {sorted(bad)}"
    with tempfile.TemporaryDirectory() as tmp:
        folder = generated_skill(tmp)
        scripts = sorted((folder / "scripts").glob("*.py"))
        for f in scripts:
            bad = imported(f) & NETWORK_MODULES
            assert not bad, f"generated {f.name} imports {sorted(bad)}"
        assert "check_python.py" in [f.name for f in scripts]
    check = imported(ROOT / "scripts" / "check_python.py")
    assert not check & NETWORK_MODULES and not {m for m in check if m.startswith("github_") or m.startswith("carrydown")}, check
    return f"{len(first)} scripts of the first skill, {len(scripts)} of the engineers' skill; check_python.py imports {sorted(check)}"


if __name__ == "__main__":
    failed = RESULTS.count(False)
    if SKIPPED:
        print(f"\n{len(SKIPPED)} claim(s) skipped, see SKIP above")
    print(f"\n{RESULTS.count(True)} of {len(RESULTS)} claims passed")
    sys.exit(1 if failed else 0)
