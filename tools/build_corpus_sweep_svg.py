#!/usr/bin/env python3
"""Draw docs/COMPETITOR-CORPUS-COVERAGE.svg from the sweep receipt.

Every number in the picture is read from
docs/upstream-package/competitor-defects/corpus-sweep-39daf704.json, so the
picture cannot outlive the measurement: regenerate with --write, check with
--check (CI-able), and the test in tests/test_competitor_corpus_sweep.py fails if
the SVG no longer matches the receipt.

The picture exists for one reason: "171 vectors" reads as a scoreboard, and the
shape that matters is that 111 of them cannot be judged by an outsider at all.

    python3 tools/build_corpus_sweep_svg.py --write
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPT = os.path.join(HERE, "docs", "upstream-package", "competitor-defects",
                       "corpus-sweep-39daf704.json")
SVG = os.path.join(HERE, "docs", "COMPETITOR-CORPUS-COVERAGE.svg")

W, H = 1040, 560
LEFT = 190
BAR_X = 210
BAR_MAX = 620
ROW_H = 56
TOP = 170
OURS = "#1f5fa8"
THEIRS = "#c9cdd3"


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(receipt):
    cats = receipt["categories"]
    t = receipt["totals"]
    order = ["inclusion", "consistency", "token", "chain", "canonical"]
    n_max = max(c["counts"]["vectors"] for c in cats.values())
    rows = []
    y = TOP
    for kind in order:
        c = cats[kind]["counts"]
        n = c["vectors"]
        bar = BAR_MAX * n / n_max
        rep = BAR_MAX * c["replayable"] / n_max
        rows.append(
            '<text x="%d" y="%d" font-size="15" fill="#222">%s</text>'
            % (LEFT - 12, y + 22, _esc(kind)))
        rows.append('<rect x="%d" y="%d" width="%.1f" height="26" fill="%s" rx="3"/>'
                    % (BAR_X, y + 4, bar, THEIRS))
        rows.append('<rect x="%d" y="%d" width="%.1f" height="26" fill="%s" rx="3"/>'
                    % (BAR_X, y + 4, rep, OURS))
        rows.append('<text x="%.1f" y="%d" font-size="13" fill="#444">%d / %d replayable</text>'
                    % (BAR_X + bar + 12, y + 22, c["replayable"], n))
        y += ROW_H

    legend_y = 96
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="DejaVu Sans, Helvetica, sans-serif">' % (W, H, W, H),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="40" font-size="20" font-weight="600" fill="#111">'
        'How much of a competitor\'s corpus a stranger can replay</text>',
        '<text x="24" y="66" font-size="14" fill="#444">'
        'probityai/agent-evidence-vectors, commit 39daf704, 2026-11-25 &#183; '
        'arithmetic only, no upstream code</text>',
        '<rect x="%d" y="%d" width="14" height="14" fill="%s"/>' % (24, legend_y, OURS),
        '<text x="44" y="%d" font-size="13" fill="#333">replayable from the file\'s own numbers</text>'
        % (legend_y + 12),
        '<rect x="%d" y="%d" width="14" height="14" fill="%s"/>' % (24, legend_y + 24, THEIRS),
        '<text x="44" y="%d" font-size="13" fill="#333">'
        'needs a signature, a chain or a canonicaliser</text>' % (legend_y + 36),
    ]
    out.extend(rows)
    out.append(
        '<text x="24" y="%d" font-size="15" fill="#111">%d of %d vectors (%.0f%%) replayable; '
        '%d agree with their published verdict; %d contradict it.</text>'
        % (H - 26, t["n_replayable"], t["vectors"],
           100.0 * t["n_replayable"] / t["vectors"], t["consistent"], t["inconsistent"]))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main(argv):
    with open(RECEIPT, encoding="utf-8") as f:
        receipt = json.load(f)
    text = render(receipt)
    if "--write" in argv:
        with open(SVG, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("written:", SVG)
        return 0
    if "--check" in argv:
        with open(SVG, encoding="utf-8") as f:
            stored = f.read()
        if stored != text:
            print("stale: %s does not match a fresh build from %s"
                  % (os.path.basename(SVG), os.path.basename(RECEIPT)))
            return 1
        print("current:", SVG)
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
