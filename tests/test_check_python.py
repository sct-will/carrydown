"""The Python preflight (work package 13): scripts/check_python.py and the shared preflight page.

check_python.py is tested in process, with the version, the platform and the processor faked, so no other
Python and no other system is needed. The preflight page is checked for the install order the specification
gives for each system and for the rule that one section never shows another system's commands.
No token and no network are used. Run from the repository root:
python -m unittest tests.test_check_python -v
"""
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_python as CP  # noqa: E402

PAGE = (ROOT / "templates" / "preflight.md").read_text(encoding="utf-8")


def check(version=(3, 12, 1), platform="darwin", machine="arm64", executable=None, argv=()):
    """Run main() with a faked interpreter. Returns (exit status, output)."""
    out = io.StringIO()
    exe = sys.executable if executable is None else executable
    with mock.patch.object(sys, "version_info", tuple(version) + ("final", 0)), mock.patch.object(sys, "platform", platform), \
            mock.patch.object(CP.platform, "machine", lambda: machine), mock.patch.object(sys, "executable", exe), \
            contextlib.redirect_stdout(out):
        status = CP.main(list(argv))
    return status, out.getvalue()


class CheckPythonTests(unittest.TestCase):
    def test_3_9_and_newer_pass(self):
        for version in ((3, 9, 0), (3, 9, 21), (3, 12, 1), (3, 15, 2)):
            with self.subTest(version=version):
                status, out = check(version)
                self.assertEqual(status, 0, out)
                self.assertIn("is ready", out)
                self.assertNotIn("https://", out)

    def test_older_versions_fail_with_the_link_of_the_detected_system_only(self):
        cases = [("darwin", "arm64", "macOS", CP.MACOS_PKG, (CP.WINDOWS_AMD64, CP.WINDOWS_ARM64, CP.WINDOWS_LANDING)),
                 ("win32", "AMD64", "Windows", CP.WINDOWS_AMD64, (CP.MACOS_PKG, CP.WINDOWS_ARM64, CP.MACOS_LANDING)),
                 ("win32", "ARM64", "Windows", CP.WINDOWS_ARM64, (CP.MACOS_PKG, CP.WINDOWS_AMD64, CP.MACOS_LANDING))]
        for platform, machine, label, link, others in cases:
            for version in ((3, 8, 18), (3, 6, 9)):
                with self.subTest(system=label, machine=machine, version=version):
                    status, out = check(version, platform, machine)
                    self.assertEqual(status, 2, out)
                    self.assertIn(f"({label})", out)
                    self.assertIn(link, out)
                    for other in others:
                        self.assertNotIn(other, out)

    def test_linux_gets_the_package_manager_and_no_other_systems_link(self):
        status, out = check((3, 6, 9), "linux", "x86_64")
        self.assertEqual(status, 2)
        self.assertIn("package manager", out)
        for link in (CP.MACOS_PKG, CP.WINDOWS_AMD64, CP.WINDOWS_ARM64, CP.MACOS_LANDING, CP.WINDOWS_LANDING):
            self.assertNotIn(link, out)

    def test_the_windows_instructions_say_to_tick_add_to_path(self):
        self.assertIn("Add python.exe to PATH", check((3, 6, 9), "win32", "AMD64")[1])
        self.assertNotIn("Add python.exe to PATH", check((3, 6, 9), "darwin", "arm64")[1])

    def test_an_interpreter_that_is_not_real_python_fails(self):
        for exe, why in (("", "did not start a real Python"), ("/no/such/python", "not installed")):
            with self.subTest(executable=exe):
                out = io.StringIO()
                with mock.patch.object(sys, "executable", exe), mock.patch.object(sys, "platform", "win32"), \
                        mock.patch.object(CP.platform, "machine", lambda: "AMD64"), contextlib.redirect_stdout(out):
                    status = CP.main([])
                self.assertEqual(status, 2, out.getvalue())
                self.assertIn(why, out.getvalue())
                self.assertIn(CP.WINDOWS_AMD64, out.getvalue())
                self.assertNotIn(CP.MACOS_PKG, out.getvalue())

    def test_the_system_flag_picks_the_link_of_a_failing_check(self):
        status, out = check((3, 6, 9), "darwin", "arm64", argv=["--system", "windows", "--machine", "arm64"])
        self.assertEqual(status, 2)
        self.assertIn(CP.WINDOWS_ARM64, out)
        self.assertNotIn(CP.MACOS_PKG, out)

    def test_the_six_links_are_the_verified_ones(self):
        self.assertEqual(CP.MACOS_PKG, "https://www.python.org/ftp/python/3.15.2/python-3.15.2-macos11.pkg")
        self.assertEqual(CP.WINDOWS_AMD64, "https://www.python.org/ftp/python/3.15.2/python-3.15.2-amd64.exe")
        self.assertEqual(CP.WINDOWS_ARM64, "https://www.python.org/ftp/python/3.15.2/python-3.15.2-arm64.exe")
        self.assertEqual(CP.RELEASE_PAGE, "https://www.python.org/downloads/release/python-3152/")
        self.assertEqual(CP.MACOS_LANDING, "https://www.python.org/downloads/macos/")
        self.assertEqual(CP.WINDOWS_LANDING, "https://www.python.org/downloads/windows/")
        for link in (CP.MACOS_PKG, CP.WINDOWS_AMD64, CP.WINDOWS_ARM64, CP.RELEASE_PAGE, CP.MACOS_LANDING, CP.WINDOWS_LANDING):
            self.assertIn(link, PAGE)

    def test_the_script_uses_no_syntax_that_an_old_python_3_rejects(self):
        text = (ROOT / "scripts" / "check_python.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r'(?<![\w"])f"', text), "an f-string stops Python 3.5 and older before the version check")


def section(name):
    return PAGE.split(f"\n## {name}\n")[1].split("\n## ")[0]


class PreflightPageTests(unittest.TestCase):
    def test_each_system_has_its_own_heading(self):
        for name in ("macOS", "Windows", "Linux"):
            self.assertIn(f"\n## {name}\n", PAGE)

    def test_windows_runs_the_check_with_py_then_python(self):
        win = section("Windows")
        self.assertLess(win.index("py -3 <skill>/scripts/check_python.py"), win.index("python <skill>/scripts/check_python.py"))
        self.assertIn("Microsoft Store", win)

    def test_macos_and_linux_run_the_check_with_python3(self):
        for name in ("macOS", "Linux"):
            self.assertIn("python3 <skill>/scripts/check_python.py", section(name))

    def test_windows_install_order_is_winget_installer_administrator(self):
        win = section("Windows")
        order = [win.index(t) for t in ("winget install --id Python.Python.3.12 -e --source winget", "Add python.exe to PATH", "Send this link to your administrator")]
        self.assertEqual(order, sorted(order))

    def test_macos_install_order_is_homebrew_package_developer_tools(self):
        mac = section("macOS")
        order = [mac.index(t) for t in ("brew install python", "double-click the file", "xcode-select --install")]
        self.assertEqual(order, sorted(order))
        self.assertIn("the password you use to unlock the computer", mac)

    def test_the_question_is_asked_once_in_the_agreed_words_for_every_system(self):
        for name in ("macOS", "Windows", "Linux"):
            self.assertIn("Python is needed to run the carrydown scripts. Install it now?", section(name))

    def test_a_section_shows_no_command_of_another_system(self):
        self.assertNotIn("winget", section("macOS") + section("Linux"))
        self.assertNotIn("brew", section("Windows") + section("Linux"))
        self.assertNotIn("xcode-select", section("Windows") + section("Linux"))
        self.assertNotIn("py -3", section("macOS") + section("Linux"))

    def test_nothing_is_piped_from_a_download_into_a_shell(self):
        self.assertNotRegex(PAGE, r"(curl|wget|iwr|Invoke-WebRequest)[^\n]*\|")
        self.assertIn("never pipe a download into a shell", PAGE.lower())


class ProofHomeTests(unittest.TestCase):
    """tests/proof_wp13.py finds Python 3.9 from CARRYDOWN_PY39 or from the account's home folder, never from HOME,
    so the empty HOME the testers use does not fail it."""

    def proof(self, **extra):
        with tempfile.TemporaryDirectory(prefix="carrydown-empty-home-") as home:
            env = {k: v for k, v in os.environ.items() if k != "CARRYDOWN_PY39"}
            env.update(HOME=home, USERPROFILE=home, **extra)
            run = subprocess.run([sys.executable, str(ROOT / "tests" / "proof_wp13.py")], cwd=str(ROOT), env=env,
                                 capture_output=True, text=True, timeout=300)
        return run.returncode, run.stdout + run.stderr

    def test_an_empty_home_does_not_fail_the_python_3_9_claim(self):
        code, out = self.proof()
        lines = out.splitlines()
        self.assertEqual(code, 0, out[-600:])
        self.assertFalse([x for x in lines if x.startswith("FAIL ")], out[-600:])
        row = next(x for x in lines if x.endswith("check_python.py exits 0 under Python 3.9.21"))
        if row.startswith("SKIP "):        # a machine with no Python 3.9.21 in the account's home folder: the reason is printed
            self.assertIn("CARRYDOWN_PY39 is not set", out)
        else:
            self.assertTrue(row.startswith("PASS "), row)
            self.assertIn("(interpreter from the account's home folder)", out)
        self.assertRegex(lines[-1], r"^(\d+) of \1 claims passed$")

    def test_a_wrong_carrydown_py39_fails_the_claim_instead_of_skipping_it(self):
        code, out = self.proof(CARRYDOWN_PY39=str(ROOT / "no-such-python"))
        self.assertEqual(code, 1, out[-600:])
        self.assertIn("FAIL check_python.py exits 0 under Python 3.9.21", out)


if __name__ == "__main__":
    unittest.main()
