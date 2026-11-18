#!/usr/bin/env python3
"""Render docs/SCALE.json as a bar chart, one row per implementation.

Rows are normalised within themselves (each row scaled to its own largest
value), because the two implementations differ by an order of magnitude once
process start-up is included and a shared axis makes the small bars invisible.
The numbers stay in docs/SCALE.json; this file only draws them.

    python3 tools/build_scale_svg.py > docs/SCALE.svg
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "..", "docs", "SCALE.json")

W, H = 1040, 360
LEFT, RIGHT = 190, 80
ROW_H = 92


def main():
    d = json.load(open(_DATA, encoding="utf-8"))
    rows = [
        ("verify() · Python", d["python"], "#2f6fd0"),
        ("verify.mjs · JavaScript", d["javascript"], "#e08a2e"),
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{LEFT}" y="34" font-family="Helvetica,Arial" font-size="15" fill="#111">'
        "Verification time by package size (lower is better)</text>",
    ]
    plot_w = W - LEFT - RIGHT
    for i, (label, pts, color) in enumerate(rows):
        y0 = 70 + i * ROW_H
        mx = max(p["secs"] for p in pts)
        out.append(
            f'<text x="16" y="{y0 + 18}" font-family="Helvetica,Arial" font-size="13" fill="#333">{label}</text>'
        )
        for j, p in enumerate(sorted(pts, key=lambda x: x["n"])):
            bw = max(3.0, plot_w * p["secs"] / mx * 0.82)
            yy = y0 + j * 22
            out.append(
                f'<rect x="{LEFT}" y="{yy}" width="{bw:.1f}" height="14" fill="{color}" rx="2"/>'
            )
            out.append(
                f'<text x="{LEFT + bw + 8:.1f}" y="{yy + 11}" font-family="Helvetica,Arial" '
                f'font-size="11" fill="#444">{p["n"]:,} evidence · {p["secs"]:.3f} s · {p["rss_mib"]:.1f} MiB</text>'
            )
    out.append(
        f'<text x="16" y="{H - 18}" font-family="Helvetica,Arial" font-size="11" fill="#777">'
        "Synthetic packages, unsigned (INCONCLUSIVE by design). JavaScript bars include Node start-up. "
        "Source: docs/SCALE.json</text>"
    )
    out.append("</svg>")
    print("\n".join(out))


if __name__ == "__main__":
    main()
