"""A missing trustlist must be a sentence, not a traceback.

`--trustlist` pointed at a path that does not exist used to raise
FileNotFoundError from bundle.trust_ladder, so the first thing an outsider
following the reproduction record saw was a Python stack. The command now fails
closed with exit 2 and one line on stderr, which is what a gate should look
like: it says what is missing and stops.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_missing_trustlist_is_a_sentence():
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    res = subprocess.run(
        [sys.executable, "-m", "uibc_core.cli", "verify",
         str(ROOT / "fixtures" / "clean.uibc"),
         "--trustlist", str(ROOT / "no-such-trustlist.json")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(ROOT))
    assert res.returncode == 2
    assert "trustlist file not found" in (res.stderr or "")
    assert "Traceback" not in (res.stderr or "")
