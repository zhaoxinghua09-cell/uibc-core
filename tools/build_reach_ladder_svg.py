#!/usr/bin/env python3
"""Draw docs/UPSTREAM-REACH-LADDER.svg from the reach ledger receipt.

The sweep says "102 not replayable" and stops there. This picture splits that 102
into what the files themselves support, on one 171 scale:

    verdict          69   arithmetic on the file's own numbers decides the verdict
    signature-only   88   every carried signature verifies under the carried key;
                          a necessary condition, never a verdict
    nothing          14   unparsable text, no signature, or a signature that fails

and puts our own 63 beside it on the same ruler: every one of ours is at the
verdict level.

Every length is read from docs/upstream-package/competitor-defects/corpus-ledger-39daf704.json
and docs/upstream-package/measurements/own-corpus-replay.json; nothing is typed in.
Regenerate with --write, refuse staleness with --check (CI-able).

    python3 tools/build_reach_ladder_svg.py --write
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(HERE, "docs", "upstream-package", "competitor-defects",
                      "corpus-ledger-39daf704.json")
OURS = os.path.join(HERE, "docs", "upstream-package", "measurements",
                    "own-corpus-replay.json")
SVG = os.path.join(HERE, "docs", "UPSTREAM-REACH-LADDER.svg")

W, H = 1040, 470
LABEL_X = 24
BAR_X = 300
BAR_MAX = 640
VERDICT = "#1f5fa8"
SIGNED = "#8fb4dd"
NOTHING = "#d7d9dd"


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _stack(y, total, verdict, signed, nothing, n_max, label, sub):
    """Three stacked segments on one scale, with the total printed at the end."""
    out = [
        '<text x="%d" y="%d" font-size="15" fill="#222">%s</text>'
        % (LABEL_X, y + 18, _esc(label)),
        '<text x="%d" y="%d" font-size="12" fill="#666">%s</text>'
        % (LABEL_X, y + 36, _esc(sub)),
    ]
    x = BAR_X
    width_total = BAR_MAX * total / n_max
    for count, fill in ((verdict, VERDICT), (signed, SIGNED), (nothing, NOTHING)):
        if not count:
            continue
        w = BAR_MAX * count / n_max
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="28" fill="%s"/>'
                   % (x, y + 2, w, fill))
        if w >= 26:
            out.append('<text x="%.1f" y="%d" font-size="13" fill="%s" '
                       'text-anchor="middle">%d</text>'
                       % (x + w / 2, y + 21,
                          "#ffffff" if fill == VERDICT else "#333", count))
        x += w
    out.append('<text x="%.1f" y="%d" font-size="14" fill="#333">%d / %d</text>'
               % (BAR_X + width_total + 14, y + 22, verdict, total))
    out.append('<text x="%.1f" y="%d" font-size="12" fill="#666">(%.0f%%)</text>'
               % (BAR_X + width_total + 14, y + 38, 100.0 * verdict / max(1, total)))
    return out


def render(ledger, ours):
    t = ledger["totals"]
    own = ours["totals"]
    n_max = max(t["vectors"], own["vectors"])
    fam = ledger["families"]
    fam_text = " &#183; ".join(
        "%s %d/%d/%d" % (k, fam[k]["verdict"], fam[k]["signature-only"], fam[k]["nothing"])
        for k in ("inclusion", "consistency", "canonical", "token", "chain"))

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="DejaVu Sans, Helvetica, sans-serif">'
        % (W, H, W, H),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="44" font-size="21" font-weight="600" fill="#111">'
        'Where each vector stops</text>',
        '<text x="24" y="70" font-size="14" fill="#444">'
        'their 171 split by what the file itself supports &#183; '
        'our 63 on the same 171 ruler</text>',
        '<rect x="24" y="96" width="14" height="14" fill="%s"/>' % VERDICT,
        '<text x="46" y="108" font-size="13" fill="#333">'
        'verdict: arithmetic on the file\'s own numbers</text>',
        '<rect x="330" y="96" width="14" height="14" fill="%s"/>' % SIGNED,
        '<text x="352" y="108" font-size="13" fill="#333">'
        'signature-only: signed correctly, rule not shipped</text>',
        '<rect x="660" y="96" width="14" height="14" fill="%s"/>' % NOTHING,
        '<text x="682" y="108" font-size="13" fill="#333">'
        'nothing: no verdict, no signature</text>',
    ]
    out.extend(_stack(150, t["vectors"], t["verdict"], t["signature-only"],
                      t["nothing"], n_max,
                      "their corpus: probityai/agent-evidence-vectors",
                      "%s &#183; %s" % (ledger.get("corpus", ""), fam_text)))
    out.extend(_stack(250, own["vectors"], own["n_replayable"], 0,
                      own["vectors"] - own["n_replayable"], n_max,
                      "our corpus: scitt-rfc9162 " + str(ours.get("version", "")),
                      "every vector also judged by pymerkle / Sigstore / Go"))
    out.append(
        '<text x="24" y="%d" font-size="14" fill="#111">'
        '%d of %d at the verdict level there, %d of %d here &#183; '
        '%d contradictions.</text>'
        % (H - 92, t["verdict"], t["vectors"], own["n_replayable"], own["vectors"],
           0))
    out.append(
        '<text x="24" y="%d" font-size="12" fill="#666">'
        'a verifying signature is a necessary condition, not a verdict - the 88 are '
        'never added to the 69. receipts: '
        'docs/upstream-package/competitor-defects/corpus-ledger-39daf704.json + '
        'docs/upstream-package/measurements/own-corpus-replay.json</text>' % (H - 64))
    out.append(
        '<text x="24" y="%d" font-size="12" fill="#666">'
        'regenerate with tools/build_reach_ladder_svg.py --write &#183; '
        'the 14 include the one chain vector whose middle record has a flipped '
        'signature bit, and 13 token vectors with unparsable or unsigned text.</text>'
        % (H - 44))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main(argv):
    with open(LEDGER, encoding="utf-8") as f:
        ledger = json.load(f)
    with open(OURS, encoding="utf-8") as f:
        ours = json.load(f)
    text = render(ledger, ours)
    if "--write" in argv:
        with open(SVG, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("written:", SVG)
        return 0
    if "--check" in argv:
        if not os.path.exists(SVG):
            print("missing:", SVG)
            return 1
        with open(SVG, encoding="utf-8") as f:
            stored = f.read()
        if stored != text:
            print("stale: %s does not match a fresh build from the receipts"
                  % os.path.basename(SVG))
            return 1
        print("current:", SVG)
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
