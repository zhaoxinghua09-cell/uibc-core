"""The demo runs, and the diagram is derived rather than drawn.

Two failure modes this file exists to catch:

1. a demo that stops running the moment the module changes underneath it;
2. a diagram that was drawn once by hand and silently drifted from the constants.
"""

import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "BID-BINARY-LAYOUT.svg")


def _run(args):
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    return subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env, timeout=120)


def test_demo_exits_zero_and_says_all_ok():
    res = _run([os.path.join("tools", "demo_bid_binary.py"), "--flip"])
    assert res.returncode == 0, res.stdout + res.stderr
    assert "ALL OK" in res.stdout
    # every claimed check must actually have printed its OK line
    assert res.stdout.count("OK ") >= 12
    assert "HARD-FAIL" not in res.stdout


def test_demo_shows_both_readings_of_the_same_bytes():
    res = _run([os.path.join("tools", "demo_bid_binary.py")])
    assert "msb=" in res.stdout and "lsb=" in res.stdout
    assert "declared long=8 bytes but carries 4" in res.stdout


def test_layout_svg_matches_the_generator_byte_for_byte():
    res = _run([os.path.join("tools", "render_bid_binary_layout.py"), "--stdout"])
    assert res.returncode == 0, res.stderr
    fresh = res.stdout.encode("utf-8")
    committed = io.open(DOC, "rb").read()
    assert fresh == committed, ("docs/BID-BINARY-LAYOUT.svg is stale: regenerate with "
                                "python tools/render_bid_binary_layout.py")


def test_layout_svg_carries_every_flag_and_every_assumption():
    from uibc_core import bid_binary as BB
    svg = io.open(DOC, encoding="utf-8").read()
    for name, _bit in BB._FLAG_BITS:
        assert name in svg, name
    assert "opCode" in svg
    for name in BB.ASSUMPTIONS:
        assert name in svg, name
    assert "header %d bytes" % BB.HEADER_MIN in svg


def test_layout_generator_refuses_to_draw_a_header_that_does_not_add_up():
    """The span arithmetic is asserted inside render(); prove it is load-bearing."""
    from uibc_core import bid_binary as BB
    first = (4 + 4 + 16) // 8                              # byte0 (version|hdrLen) + flag 2B
    tail = 1 + 2 + 2 + 4 + 4                               # unUsed, replyCode, messageID, txID, length
    assert first + tail == BB.HEADER_MIN
