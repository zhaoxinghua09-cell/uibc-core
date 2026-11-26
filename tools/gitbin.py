"""Run git from Python on Windows, including where git is a .cmd shim.

Why this exists: on Windows, `subprocess.run(["git", ...])` raises
`FileNotFoundError: [WinError 2]` when the `git` on PATH is a launcher
(`.cmd`/`.bat`) rather than `git.exe`, because CreateProcess cannot execute a
batch file. PowerShell hides this by resolving the shim itself, so the tools
looked fine by hand and failed under pytest.

This module is the one place that knows the difference. Every tool that shells
out to git should route through `run()` / `check_output()` here.
"""

import shutil
import subprocess

SHIM_SUFFIXES = (".cmd", ".bat")


def _argv(args):
    """Return (cmd, needs_shell) for git plus the given arguments."""
    exe = shutil.which("git") or "git"
    if exe.lower().endswith(SHIM_SUFFIXES):
        return subprocess.list2cmdline([exe] + list(args)), True
    return [exe] + list(args), False


def run(args, **kwargs):
    cmd, shell = _argv(args)
    return subprocess.run(cmd, shell=shell, **kwargs)


def check_output(args, **kwargs):
    cmd, shell = _argv(args)
    return subprocess.check_output(cmd, shell=shell, **kwargs)
