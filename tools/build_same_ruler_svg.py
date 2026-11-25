#!/usr/bin/env python3
"""Draw docs/CORPUS-REPLAYABILITY-SAME-RULER.svg from two receipts.

The competitor picture (`build_corpus_sweep_svg.py`) answers "how much of their
corpus can a stranger replay". That number only becomes a comparison when the same
ruler is turned on ours, so this second picture carries both bars on one axis:

    docs/upstream-package/competitor-defects/corpus-sweep-39daf704.json  (their 171)
    docs/upstream-package/measurements/own-corpus-replay.json               (our 63)

Every pixel of every bar is read from those two files; nothing is typed in here.
Regenerate with --write, refuse staleness with --check (CI-able).

    python3 tools/build_same_ruler_svg.py --write
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEIRS = os.path.join(HERE, "docs", "upstream-package", "competitor-defects",
                      "corpus-sweep-39daf704.json")
OURS = os.path.join(HERE, "docs", "upstream-package", "measurements",
                    "own-corpus-replay.json")
SVG = os.path.join(HERE, "docs", "CORPUS-REPLAYABILITY-SAME-RULER.svg")

W, H = 1040, 470
LABEL_X = 24
BAR_X = 300
BAR_MAX = 640
FILLED = "#1f5fa8"
TOTAL = "#c9cdd3"
TRUST = "#e4b363"


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bar(y, total, replayable, n_max, label, sub):
    width = BAR_MAX * total / n_max
    filled = BAR_MAX * replayable / n_max
    return [
        '<text x="%d" y="%d" font-size="15" fill="#222">%s</text>' % (LABEL_X, y + 18, _esc(label)),
        '<text x="%d" y="%d" font-size="12" fill="#666">%s</text>' % (LABEL_X, y + 36, _esc(sub)),
        '<rect x="%d" y="%d" width="%.1f" height="28" fill="%s" rx="3"/>'
        % (BAR_X, y + 2, width, TOTAL),
        '<rect x="%d" y="%d" width="%.1f" height="28" fill="%s" rx="3"/>'
        % (BAR_X, y + 2, filled, FILLED),
        '<text x="%.1f" y="%d" font-size="14" fill="#333">%d / %d (%.0f%%)</text>'
        % (BAR_X + width + 14, y + 22, replayable, total, 100.0 * replayable / max(1, total)),
    ]


def render(theirs, ours):
    t_up = theirs["totals"]
    t_own = ours["totals"]
    n_max = max(t_up["vectors"], t_own["vectors"])

    up_fams = []
    for kind in ("inclusion", "consistency", "canonical", "token", "chain"):
        c = theirs["categories"][kind]["counts"]
        up_fams.append("%s %d/%d" % (kind, c["replayable"], c["vectors"]))
    own_fams = []
    for kind in ("inclusion", "consistency"):
        c = ours["categories"][kind]["counts"]
        own_fams.append("%s %d/%d" % (kind, c["replayable"], c["vectors"]))

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="DejaVu Sans, Helvetica, sans-serif">' % (W, H, W, H),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="44" font-size="21" font-weight="600" fill="#111">'
        'One ruler, two corpora</text>',
        '<text x="24" y="70" font-size="14" fill="#444">'
        'same fold functions, same classification rule &#183; '
        'a ratio is only a comparison when both sides are measured</text>',
        '<rect x="24" y="96" width="14" height="14" fill="%s"/>' % FILLED,
        '<text x="46" y="108" font-size="13" fill="#333">'
        'replayable from the file\'s own numbers</text>',
        '<rect x="%d" y="96" width="14" height="14" fill="%s"/>' % (300, TOTAL),
        '<text x="322" y="108" font-size="13" fill="#333">'
        'published, but not replayable without their code</text>',
    ]
    out.extend(_bar(150, t_up["vectors"], t_up["n_replayable"], n_max,
                    "their corpus: probityai/agent-evidence-vectors",
                    "%s &#183; %s" % (theirs.get("head", ""), ", ".join(up_fams))))
    out.extend(_bar(250, t_own["vectors"], t_own["n_replayable"], n_max,
                    "our corpus: scitt-rfc9162 " + str(ours.get("version", "")),
                    "every vector also judged by pymerkle / Sigstore / Go &#183; "
                    + ", ".join(own_fams)))
    out.append(
        '<text x="24" y="%d" font-size="14" fill="#111">'
        '%d of %d replayable here, %d of %d there &#183; '
        '%d contradictions on either side.</text>'
        % (H - 92, t_own["n_replayable"], t_own["vectors"],
           t_up["n_replayable"], t_up["vectors"],
           t_own["inconsistent"] + t_up["inconsistent"]))
    out.append(
        '<text x="24" y="%d" font-size="12" fill="#666">'
        'receipts: docs/upstream-package/competitor-defects/corpus-sweep-39daf704.json '
        'and docs/upstream-package/measurements/own-corpus-replay.json &#183; '
        'regenerate with tools/build_same_ruler_svg.py --write</text>' % (H - 64))
    out.append(
        '<text x="24" y="%d" font-size="12" fill="#666">'
        '4 of our 63 say VALID_BUT_SIZE_UNAUTHENTICATED - the root authenticates '
        'the leaves, not the declared size - and stay counted as such.</text>'
        % (H - 44))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main(argv):
    with open(THEIRS, encoding="utf-8") as f:
        theirs = json.load(f)
    with open(OURS, encoding="utf-8") as f:
        ours = json.load(f)
    text = render(theirs, ours)
    if "--write" in argv:
        with open(SVG, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("written:", SVG)
        return 0
    if "--check" in argv:
        with open(SVG, encoding="utf-8") as f:
            stored = f.read()
        if stored != text:
            print("stale: %s does not match a fresh build from the two receipts"
                  % os.path.basename(SVG))
            return 1
        print("current:", SVG)
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

