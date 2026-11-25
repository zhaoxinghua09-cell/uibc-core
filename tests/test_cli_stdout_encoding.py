"""A cp1252 console must not turn `verify` into a traceback.

The Windows runner sets stdout to cp1252. `verify` prints JSON with
`ensure_ascii=False`, so the first non-ASCII detail raised UnicodeEncodeError
and the command printed nothing - the package it was describing became
unreadable on the one platform where a regulator is most likely to be sitting.

This runs the same command with the same encoding on any platform, because
cp1252 is a Python codec, not an OS feature.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_prints_json_under_cp1252():
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=str(ROOT))
    res = subprocess.run(
        [sys.executable, "-m", "uibc_core.cli", "verify", str(ROOT / "fixtures" / "clean.uibc")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(ROOT))
    assert res.stdout.strip(), "no stdout under cp1252; stderr tail: %r" % res.stderr[-600:]
    data = json.loads(res.stdout)
    assert data.get("result"), data
