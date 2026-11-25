#!/usr/bin/env python
"""Draw the RFC-011 message layout *from the module's constants*, not by hand.

    python tools/render_bid_binary_layout.py            # write docs/BID-BINARY-LAYOUT.svg
    python tools/render_bid_binary_layout.py --stdout    # print the SVG

Why a generator instead of a picture: a diagram that is drawn once and then edited
by hand stops being evidence - it drifts from the code and nobody notices. Here the
byte spans, the flag names, the bit numbers, the unit structure and the six
assumptions are all read out of ``uibc_core.bid_binary``. If the module changes,
the SVG changes, and the test that compares them goes red until it is regenerated.

Deterministic: no timestamps, no random ids. Same tree in, same bytes out.
"""
from __future__ import annotations

import hashlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import bid_binary as BB

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "BID-BINARY-LAYOUT.svg")

CELL = 34          # one bit cell, px
CELL_BYTE = 96     # one byte cell for the span rows: 34 is too narrow for a label
PAD = 18
FONT = "font-family='DejaVu Sans, Segoe UI, sans-serif'"

CANVAS_H = 700

# byte spans after the first four bytes, as RFC-011 §5.1.2.1 names them
TAIL_SPANS = [
    ("unUsed", 1, "reserved"),
    ("replyCode", 2, "answer type"),
    ("messageID", 2, "fragment id"),
    ("transactionID", 4, "correlation id"),
    ("messageLength", 4, "body length"),
]


def _esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _bit_ruler(x0, y0, bits, labels, numbers=None):
    """One horizontal row of bit cells, labels = list of (start_bit, nbits, text)."""
    parts = []
    for i in range(bits):
        parts.append("<rect x='%d' y='%d' width='%d' height='%d' fill='%s' stroke='#94a3b8'/>"
                     % (x0 + i * CELL, y0, CELL, CELL,
                        "#e2e8f0" if i % 8 < 4 else "#eef2f7"))
    for start, span, text in labels:
        w = span * CELL
        parts.append("<rect x='%d' y='%d' width='%d' height='%d' fill='%s' fill-opacity='0.55' stroke='#475569'/>"
                     % (x0 + start * CELL, y0, w, CELL, "#93c5fd"))
        parts.append("<text x='%d' y='%d' %s font-size='%d' fill='#0f172a' text-anchor='middle'>%s</text>"
                     % (x0 + start * CELL + w // 2, y0 + CELL // 2 + 5, FONT, 12, _esc(text)))
    if numbers is None:
        numbers = list(range(bits))
    for i, number in enumerate(numbers):
        parts.append("<text x='%d' y='%d' %s font-size='8' fill='#64748b' text-anchor='middle'>%d</text>"
                     % (x0 + i * CELL + CELL // 2, y0 + CELL + 11, FONT, number))
    return parts


SPAN_H = 44


def _span_row(x0, y0, spans):
    parts = []
    x = x0
    for name, nbytes, note in spans:
        w = nbytes * CELL_BYTE
        parts.append("<rect x='%d' y='%d' width='%d' height='%d' fill='#fde68a' stroke='#92400e'/>"
                     % (x, y0, w - 2, SPAN_H))
        parts.append("<text x='%d' y='%d' %s font-size='12' fill='#111827'>%s</text>"
                     % (x + 7, y0 + 17, FONT, _esc(name)))
        parts.append("<text x='%d' y='%d' %s font-size='9' fill='#78350f'>%s</text>"
                     % (x + 7, y0 + 31, FONT, _esc(note)))
        parts.append("<text x='%d' y='%d' %s font-size='9' fill='#64748b' text-anchor='end'>%dB</text>"
                     % (x + w - 8, y0 + SPAN_H - 5, FONT, nbytes))
        x += w
    return parts, x


def render():
    flags = BB._FLAG_BITS                     # (name, msb_bit) in listed order
    shifts = BB._OPCODE_SHIFT

    # the layout must add up to the header size the module enforces
    first_bits = 4 + 4
    flag_bits = 16
    tail_bytes = sum(n for _n, n, _note in TAIL_SPANS)
    assert (first_bits + flag_bits) // 8 + tail_bytes == BB.HEADER_MIN, \
        "the diagram's spans disagree with HEADER_MIN=%d" % BB.HEADER_MIN

    width = max(16 * CELL + 2 * PAD, 13 * CELL_BYTE + 2 * PAD, 900)
    parts = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' viewBox='0 0 %d %d'>"
             % (width, CANVAS_H, width, CANVAS_H),
             "<rect width='100%' height='100%' fill='#ffffff'/>",
             "<text x='%d' y='36' %s font-size='20' font-weight='600' fill='#0f172a'>"
             "RFC-011 message layout (generated from uibc_core.bid_binary constants)</text>"
             % (PAD, FONT),
             "<text x='%d' y='58' %s font-size='11' fill='#475569'>"
             "header %d bytes, headerLength counted in %d-byte units, unit = ID 2B + length 2B + payload"
             "</text>" % (PAD, FONT, BB.HEADER_MIN, BB.HEADER_UNIT)]

    y = 84
    parts.append("<text x='%d' y='%d' %s font-size='12' fill='#334155'>byte 0 — version | headerLength</text>"
                 % (PAD, y, FONT))
    parts += _bit_ruler(PAD, y + 8, 8, [(0, 4, "version"), (4, 4, "hdrLen/4B")],
                        numbers=list(range(7, -1, -1)))

    y += 70
    parts.append("<text x='%d' y='%d' %s font-size='12' fill='#334155'>"
                 "bytes 1–2 — flag: listed order, no bit numbers in the RFC</text>" % (PAD, y, FONT))
    labels = [(15 - bit, 1, name) for name, bit in flags] + [(shifts, 4, "opCode")]
    parts += _bit_ruler(PAD, y + 8, 16, labels, numbers=list(range(15, -1, -1)))
    parts.append("<text x='%d' y='%d' %s font-size='9' fill='#b91c1c'>"
                 "bit numbers shown are the msb-first assumption (flag_bit_order='msb'); 'lsb' flips them"
                 "</text>" % (PAD, y + 62, FONT))

    y += 92
    parts.append("<text x='%d' y='%d' %s font-size='12' fill='#334155'>bytes 3–15 — the rest of the header</text>"
                 % (PAD, y, FONT))
    row, _x = _span_row(PAD, y + 8, TAIL_SPANS)
    parts += row

    y += 88
    parts.append("<text x='%d' y='%d' %s font-size='12' fill='#334155'>"
                 "body — unit tree (payload may itself be units; that is the whole nesting rule)"
                 "</text>" % (PAD, y, FONT))
    row, _x = _span_row(PAD, y + 8, [("unitID", 2, "field id"), ("length", 2, "payload bytes"),
                                     ("payload / child units", 6, "same structure, nested")])
    parts += row

    y += 78
    parts.append("<text x='%d' y='%d' %s font-size='12' fill='#334155'>"
                 "the six assumptions — each is a parameter in the module, not a comment</text>" % (PAD, y, FONT))
    y += 8
    for name, item in BB.ASSUMPTIONS.items():
        fill = {"flippable": "#dcfce7", "caller-supplied": "#dbeafe",
                "heuristic": "#fef3c7", "not-implemented": "#fee2e2"}.get(item["status"], "#e5e7eb")
        parts.append("<rect x='%d' y='%d' width='%d' height='26' fill='%s' stroke='#cbd5e1'/>"
                     % (PAD, y, width - 2 * PAD, fill))
        parts.append("<text x='%d' y='%d' %s font-size='10' fill='#111827'>%s [%s] %s</text>"
                     % (PAD + 6, y + 17, FONT, _esc(name), _esc(item["status"]), _esc(item["choice"])))
        y += 30

    parts.append("<text x='%d' y='%d' %s font-size='9' fill='#64748b'>"
                 "regenerate: python tools/render_bid_binary_layout.py — the file is checked by "
                 "tests/test_bid_binary_layout.py</text>" % (PAD, y + 8, FONT))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    svg = render()
    if "--stdout" in sys.argv:
        sys.stdout.buffer.write(svg.encode("utf-8"))
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(svg)
    print("written: %s (%d bytes, sha256 %s)"
          % (OUT, len(svg.encode("utf-8")), hashlib.sha256(svg.encode("utf-8")).hexdigest()[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
