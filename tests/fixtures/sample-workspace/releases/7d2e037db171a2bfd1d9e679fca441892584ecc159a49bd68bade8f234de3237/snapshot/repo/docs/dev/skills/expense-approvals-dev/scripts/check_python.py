#!/usr/bin/env python3
"""Check that this Python is 3.9 or newer, then say so or point to the official download.

Run it with the Python command you want to check, before any other carrydown script:
  python3 check_python.py

It prints one line and exits 0 when this interpreter is Python 3.9 or newer. Otherwise it exits 2
and prints the system it detected and the official download link for that system, and nothing
for the other systems. It also exits 2 when the interpreter is not a real Python, for example a
stub that points to a missing program. A stub that never starts Python cannot run this script at
all: the agent reads that as "Python is missing" (see references/preflight.md).

Standard library only. No network: the links are printed, never opened. The script avoids newer
syntax on purpose, so an old Python 3 still reaches the version check and prints the link.
  --system macos|windows|linux   show the download link of that system when the check fails
  --machine arm64|amd64          pick the Windows installer for that processor (default: detected)
"""
import argparse
import os
import platform
import sys

MINIMUM = (3, 9)

# Official links, verified 2026-11-03. Keep them in step with templates/preflight.md.
MACOS_PKG = "https://www.python.org/ftp/python/3.15.2/python-3.15.2-macos11.pkg"
WINDOWS_AMD64 = "https://www.python.org/ftp/python/3.15.2/python-3.15.2-amd64.exe"
WINDOWS_ARM64 = "https://www.python.org/ftp/python/3.15.2/python-3.15.2-arm64.exe"
RELEASE_PAGE = "https://www.python.org/downloads/release/python-3152/"
MACOS_LANDING = "https://www.python.org/downloads/macos/"
WINDOWS_LANDING = "https://www.python.org/downloads/windows/"

NAMES = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}


def detect_system(platform_name=None):
    """macos, windows or linux, from sys.platform. Anything else is treated as linux."""
    p = (platform_name or sys.platform).lower()
    if p.startswith("darwin"):
        return "macos"
    if p.startswith(("win", "cygwin", "msys")):
        return "windows"
    return "linux"


def detect_machine():
    """arm64 or amd64. Only the Windows installer differs by processor."""
    m = (platform.machine() or "").lower()
    return "arm64" if m in ("arm64", "aarch64") else "amd64"


def not_real_python(executable=None):
    """Why this interpreter is not a real Python, or an empty string when it looks real."""
    exe = sys.executable if executable is None else executable
    if not exe:
        return "this command did not start a real Python"
    if not os.path.exists(exe):
        return "this command points to a Python that is not installed"
    return ""


def download_lines(system, machine="amd64"):
    """The lines that tell a person where to get Python, for one system only."""
    if system == "macos":
        return ["Download the installer for macOS: " + MACOS_PKG,
                "Newest version: " + MACOS_LANDING]
    if system == "windows":
        link = WINDOWS_ARM64 if machine == "arm64" else WINDOWS_AMD64
        return ["Download the installer for Windows ({}): {}".format("ARM64" if machine == "arm64" else "64-bit", link),
                "When it opens, tick \"Add python.exe to PATH\" before you click Install.",
                "Newest version: " + WINDOWS_LANDING]
    return ["Install python3 with your system's package manager, or ask your administrator.",
            "Release page: " + RELEASE_PAGE]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check that this Python is 3.9 or newer. Exit 0 when it is, 2 when it is not.")
    ap.add_argument("--system", choices=sorted(NAMES), help="show the download link of this system when the check fails (default: the detected one)")
    ap.add_argument("--machine", choices=["amd64", "arm64"], help="processor for the Windows installer (default: detected)")
    a = ap.parse_args(argv)
    system = a.system or detect_system()
    machine = a.machine or detect_machine()
    version = ".".join(str(x) for x in tuple(sys.version_info)[:3])
    why = not_real_python()
    if why:
        print("carrydown: {} ({}). Python {}.{} or newer is needed.".format(why, NAMES[system], MINIMUM[0], MINIMUM[1]))
    elif tuple(sys.version_info)[:2] < MINIMUM:
        print("carrydown: Python {}.{} or newer is needed. This is Python {} ({}).".format(MINIMUM[0], MINIMUM[1], version, NAMES[system]))
    else:
        print("carrydown: Python {} is ready ({}).".format(version, NAMES[detect_system()]))
        return 0
    for line in download_lines(system, machine):
        print(line)
    return 2


if __name__ == "__main__":
    sys.exit(main())
