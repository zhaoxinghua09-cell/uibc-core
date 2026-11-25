"""The board has to be a board, not a screenshot.

Contracts:

1. it exists and is one file with no external reference at all;
2. the numbers it shows are archived inside it, and match the snapshot;
3. it recomputes its own numbers on open and says so;
4. the recomputation actually runs - a headless pass through the page's own
   script, so a broken escape or a missing field fails the test, not the reader.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(ROOT, "docs", "parity-board.html")
SNAPSHOT = os.path.join(ROOT, "docs", "competitor-parity.json")
CHECK_JS = os.path.join(ROOT, "tools", "board_check.js")


@pytest.fixture(scope="module")
def html():
    return open(BOARD, encoding="utf-8").read()


@pytest.fixture(scope="module")
def snap():
    return json.load(open(SNAPSHOT, encoding="utf-8"))


def test_board_is_a_single_file_with_no_outside_reference(html):
    assert "http://" not in html and "https://" not in html
    assert not re.search(r"(?:src|href)\s*=", html)
    assert "<script id=\"snap\"" in html and "<script>" in html


def test_board_numbers_are_archived_and_match_the_snapshot(html, snap):
    blob = json.loads(re.search(r"<script id=\"snap\"[^>]*>([\s\S]*?)</script>", html).group(1))
    repos = [r for r in snap["repos"] if "error" not in r]
    assert blob["summary_repos"] == len(repos)
    assert blob["summary_best"] == max(sum(r["dims"].values()) for r in repos)
    assert blob["summary_ours"] == sum(snap["ours"]["dims"].values())
    assert {r["repo"] for r in blob["repos"]} == {r["repo"] for r in repos}


def test_board_says_it_recomputes(html):
    assert "打开自检" in html
    assert "SELF-CHECK" in html
    assert "__SNAP__" not in html, "placeholder was not substituted"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_board_passes_its_own_self_check_in_a_runtime():
    rc = subprocess.run(["node", CHECK_JS, BOARD], capture_output=True, text=True, timeout=60)
    out = rc.stdout + rc.stderr
    assert rc.returncode == 0, out
    assert "SELF-CHECK PASS" in out
    assert "rows=" in out
