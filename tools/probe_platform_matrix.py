"""Does the probe command itself run on more than one platform?

TC-4 states the problem: probe strings are handed to the platform shell, and
quoting and path rules differ between POSIX sh and cmd.exe. Saying "handled"
requires a place where the same string is actually executed under both, not an
argument that it probably works.

Three checks, all offline, each able to fail:

  1. two-families  ci.yml defines jobs on at least two distinct runner families
  2. same-command  tools/recheck.py is a step of a job in each of those families
  3. not-echoed    the step runs it, rather than printing it for a human to run

Reads the workflow file only. It cannot exercise macOS or a third shell, and it
says so in its own output instead of implying more.

Usage: python tools/probe_platform_matrix.py [--workflow PATH]
Exit 0 when all three hold, 1 otherwise.
"""
from __future__ import annotations

import argparse
import re
import sys

WORKFLOW = ".github/workflows/ci.yml"
COMMAND = "tools/recheck.py"


def parse(text):
    """Return {family: {"jobs": [...], "runs_command": bool, "echoes": bool}}."""
    families = {}
    job = None
    family = None
    for line in text.splitlines():
        m = re.match(r"^\s{2}([A-Za-z0-9_.-]+):\s*$", line)
        if m:
            job = m.group(1)
            family = None
            continue
        m = re.match(r"^\s+runs-on:\s*(\S+)", line)
        if m and job:
            family = m.group(1).strip("'\"")
            families.setdefault(family, {"jobs": [], "runs_command": False, "echoes": False})
            families[family]["jobs"].append(job)
            continue
        if family and COMMAND in line:
            stripped = line.strip()
            if stripped.startswith("echo") or stripped.startswith("- run: echo"):
                families[family]["echoes"] = True
            elif stripped.startswith("run:") or stripped.startswith("- run:"):
                families[family]["runs_command"] = True
            elif stripped.startswith("- ") and "run:" in stripped:
                families[family]["runs_command"] = True
    return families


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", default=WORKFLOW)
    args = ap.parse_args(argv)

    try:
        text = open(args.workflow, encoding="utf-8").read()
    except OSError as exc:
        print("cannot read %s: %s" % (args.workflow, exc))
        return 1

    fams = parse(text)
    linux = [f for f in fams if f.startswith("ubuntu")]
    win = [f for f in fams if f.startswith("windows")]
    ok = {"two-families": bool(linux and win),
          "same-command": any(fams[f]["runs_command"] for f in linux) and
                          any(fams[f]["runs_command"] for f in win),
          "not-echoed": not any(fams[f]["echoes"] for f in fams)}

    for k, v in ok.items():
        print("%s: %s" % (k, "PASS" if v else "FAIL"))
    print("families: %s" % ", ".join(sorted(fams)))
    print("not exercised here: macOS, and any shell that is neither posix-sh nor cmd.exe")
    return 0 if all(ok.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
