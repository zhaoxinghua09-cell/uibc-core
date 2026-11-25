"""TC-4's probe has to be able to fail, like every other one.

It reads the workflow, so the three ways it can be wrong are: one platform
family, a family that never runs the command, and a step that only prints it.
Each gets a test with a purpose-built workflow.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "probe_platform_matrix.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def run(workflow=None):
    args = [sys.executable, str(SCRIPT)]
    if workflow is not None:
        args += ["--workflow", str(workflow)]
    return subprocess.run(args, capture_output=True, text=True)


def write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_repository_workflow_proves_two_families():
    if not WORKFLOW.exists():
        # MANIFEST.in grafts the directories a test reads; .github/ is not one of
        # them, so inside an sdist there is no workflow to read. Skipping states
        # that rather than pretending the check ran.
        pytest.skip("the sdist does not graft .github/, so the repository workflow is absent")
    res = run()
    assert res.returncode == 0, res.stdout + res.stderr
    for check in ("two-families", "same-command", "not-echoed"):
        assert check + ": PASS" in res.stdout
    assert "windows-latest" in res.stdout


def test_single_family_turns_red(tmp_path):
    wf = write(tmp_path, "one.yml", """jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - run: python tools/recheck.py
""")
    res = run(wf)
    assert res.returncode == 1
    assert "two-families: FAIL" in res.stdout


def test_printed_not_run_turns_red(tmp_path):
    wf = write(tmp_path, "echo.yml", """jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - run: python tools/recheck.py

  probes:
    runs-on: windows-latest
    steps:
      - run: echo python tools/recheck.py
""")
    res = run(wf)
    assert res.returncode == 1
    assert "not-echoed: FAIL" in res.stdout


def test_family_without_the_command_turns_red(tmp_path):
    wf = write(tmp_path, "half.yml", """jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - run: python tools/recheck.py

  probes:
    runs-on: windows-latest
    steps:
      - run: python -m pytest -q
""")
    res = run(wf)
    assert res.returncode == 1
    assert "same-command: FAIL" in res.stdout

