"""The register's rule 4 is only a rule if something fails when it is broken."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "check_register_row.py")
REGISTER = os.path.join(REPO, "REPRODUCTION-REGISTER.md")

HEADER = [
    "date",
    "who",
    "affiliation",
    "subject (commit)",
    "result",
    "receipt sha256",
    "notes",
]


def load_tool(name="check_register_row"):
    spec = importlib.util.spec_from_file_location(name, TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(*args):
    return subprocess.run(
        [sys.executable, TOOL, *args],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def test_self_test_passes():
    r = run("--self-test")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELF-TEST PASS" in r.stdout


def test_the_register_as_shipped_is_well_formed():
    r = run("--register", REGISTER)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 problems" in r.stdout


def test_a_row_without_a_full_hash_is_rejected():
    # The failure mode this whole tool exists for: a row that looks like
    # evidence and cannot be matched to any receipt file.
    mod = load_tool()
    bad = (
        "| 2026-11-21 | Anon | none | a1b2c3d | ALL COMPARISONS MATCH | abc123 "
        "| ran: reproduce_gate |"
    )
    problems = mod.check_row_shape(mod.split_md_row(bad), HEADER, "test")
    assert problems, "a short hash must be rejected"
    assert any("receipt sha256" in p for p in problems)


def test_a_disagreement_row_is_accepted():
    # Rule 1: disagreements are kept. A checker that rejects them would push
    # the file toward only agreeing rows, which is the opposite of its purpose.
    mod = load_tool("check_register_row_2")
    row = (
        "| 2026-11-22 | B. Skeptic | employed by a competitor | deadbee | "
        "3 of 24 comparisons differ | " + "ab" * 32 + " | see attached receipt |"
    )
    problems = mod.check_row_shape(mod.split_md_row(row), HEADER, "test")
    assert not problems, problems
