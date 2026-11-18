#!/usr/bin/env python3
"""Draw docs/COMPETITORS.svg from the numbers the repo already states.

Every bar is a number in docs/COMPETITORS.md, and every number there has a
command. The picture exists because two of the six rows point the other way
from the other four, and a table that size is read as a scoreboard whereas a
bar chart of the same numbers is read as a shape.

    python3 tools/build_competitors_svg.py > docs/COMPETITORS.svg
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(HERE, "docs", "COMPETITORS.json")

# The numbers a public endpoint answers are read from the recorded baseline, so
# this picture cannot go stale on its own. The four that no endpoint publishes
# - test functions, modules, implementations, a submitted spec - are the ones
# measured by hand on 2026-11-18, and the date on the picture says so.

ROWS = [
    # label, ours, peer, note
    ("Published releases", 4, 23, ""),
    ("Test functions", 524, 1189, ""),
    ("Verifier modules", 25, 40, ""),
    ("Independent implementations", 2, 1, "one language can't find a misread spec"),
    ("Shippable conformance packages", 36, 0, "36 packages, its own zip"),
    ("Submitted specification", 0, 1, "their I-D; our draft is in this repo"),
]

W, H = 1040, 500
LEFT = 330          # label column
BAR_X = 350
BAR_MAX = 400       # px for the larger of the two values
ROW_H = 58
TOP = 92

OURS = "#1f5fa8"
PEER = "#c4622a"
GRID = "#dfe3e8"
INK = "#1b1b1b"
MUTED = "#6b7280"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _baseline():
    try:
        with open(BASELINE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _rows(baseline):
    rows = [list(r) for r in ROWS]
    ours = baseline.get("ours") or {}
    peer = baseline.get("peer") or {}
    if ours.get("pypi_releases") is not None:
        rows[0][1] = ours["pypi_releases"]
    if peer.get("pypi_releases") is not None:
        rows[0][2] = peer["pypi_releases"]
    if ours.get("tests") is not None:
        rows[1][1] = ours["tests"]
    if ours.get("conformance_cases") is not None:
        rows[4][1] = ours["conformance_cases"]
    return rows


def main():
    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
               'viewBox="0 0 %d %d" font-family="Helvetica,Arial,sans-serif">'
               % (W, H, W, H))
    out.append('<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H))
    out.append('<text x="40" y="46" font-size="22" font-weight="700" fill="%s">'
               'Two projects, same day, same inputs</text>' % INK)
    out.append('<text x="40" y="70" font-size="12.5" fill="%s">'
               'uibc-core (blue) vs agent-action-capsule 0.17.0 (orange), measured 2026-11-18. '
               'Every number is re-checkable: python3 tools/check_competitors.py</text>' % MUTED)

    # legend
    out.append('<rect x="%d" y="30" width="14" height="10" fill="%s"/>' % (W - 220, OURS))
    out.append('<text x="%d" y="39" font-size="12" fill="%s">uibc-core</text>' % (W - 200, INK))
    out.append('<rect x="%d" y="30" width="14" height="10" fill="%s"/>' % (W - 110, PEER))
    out.append('<text x="%d" y="39" font-size="12" fill="%s">peer</text>' % (W - 90, INK))

    rows = _rows(_baseline())
    for i, (label, ours, peer, note) in enumerate(rows):
        y = TOP + i * ROW_H
        out.append('<text x="40" y="%d" font-size="13.5" fill="%s">%s</text>'
                   % (y + 16, INK, esc(label)))
        if note:
            out.append('<text x="40" y="%d" font-size="10.5" fill="%s">%s</text>'
                       % (y + 31, MUTED, esc(note)))
        # Each row is scaled to its own larger value. A shared axis would make
        # the small counts - 4 releases against 23 - two-pixel slivers, and the
        # point of these rows is the ratio, not the absolute height.
        peak = max(ours, peer) or 1
        for j, (val, colour) in enumerate(((ours, OURS), (peer, PEER))):
            length = max(3, int(val / peak * BAR_MAX))
            by = y + 2 + j * 16
            out.append('<rect x="%d" y="%d" width="%d" height="13" fill="%s" rx="2"/>'
                       % (BAR_X, by, length, colour))
            out.append('<text x="%d" y="%d" font-size="12" font-weight="600" fill="%s">%d</text>'
                       % (BAR_X + length + 8, by + 11, INK, val))
        out.append('<line x1="40" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1"/>'
                   % (y + ROW_H - 6, W - 40, y + ROW_H - 6, GRID))

    foot_y = TOP + len(rows) * ROW_H + 30
    out.append('<text x="40" y="%d" font-size="12.5" fill="%s">'
               'Four rows point their way. Two point ours, and they are the two a test count cannot buy: '
               'a second implementation, and a suite a stranger can run.</text>' % (foot_y, INK))
    out.append('<text x="40" y="%d" font-size="11" fill="%s">'
               'What is still missing is not more tests. It is the I-D, the release, and one outside person '
               'running the 36 packages.</text>' % (foot_y + 20, MUTED))
    out.append('</svg>')
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
