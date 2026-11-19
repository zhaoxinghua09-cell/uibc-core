"""Every claim this project makes, checked by one command, timed.

A repository that asserts six things in prose and checks them in six places will
drift: someone runs three of the six, quotes them all. This runs the six and
prints one table, so the answer to "does it still hold" is one exit code.

    python3 tools/run_all_evidence.py              # offline checks only
    python3 tools/run_all_evidence.py --online     # plus three network checks
    python3 tools/run_all_evidence.py --svg out.svg

Offline by default: the network checks talk to Zenodo, PyPI, GitHub and Software
Heritage, and a third party's bad afternoon is not evidence about this repository.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (label, command, string that must appear, what it establishes, needs network)
CHECKS = [
    ("anchor 001 verifies", ["tools/anchor_check.py", "anchors/001"], "ANCHORED",
     "the anchor in the tree still pins the package in the tree", False),
    ("chain of one", ["tools/anchor_chain.py", "anchors/001", "--expect-latest", "1"], "CHAIN OK",
     "the same verdict from the Python chain reader", False),
    ("the tamper probe fails", ["-m", "pytest", "tests/test_published_anchor.py", "-q"], "passed",
     "an edited evidence file is caught by S4/S8/S9", False),
    ("conformance, both implementations", ["tools/assert_second_impl.py"], "agrees on",
     "every accepted package is accepted by both, every refusal names a check", False),
    ("witnesses still there", ["tools/check_witnesses.py"], "VERDICT: OK",
     "Zenodo, Software Heritage and Rekor still hold what we cite", True),
    ("anchor channel", ["tools/check_channel.py"], "VERDICT: OK",
     "the release copy and the repository copy are the same anchor", True),
    ("release pins", ["tools/check_pins.py"], "VERDICT: OK",
     "pin, index and download agree for 0.4.0", True),
    ("crypto cross-checked", ["tools/external_crypto_check.py"], "VERDICT: CONSISTENT",
     "OpenSSL verifies the same Ed25519 seals we do, and refuses a one-byte edit", False),
    ("outsider's find stays fixed", ["tools/external_node_regression.py"], "VERDICT: STILL FIXED",
     "the duplicated-evidence_id divergence external node 001 found is still repaired", False),
]


def run(cmd):
    t0 = time.time()
    r = subprocess.run([sys.executable] + cmd, cwd=REPO, capture_output=True, text=True, timeout=900)
    return r, time.time() - t0


def main():
    online = "--online" in sys.argv
    rows = []
    for label, cmd, needle, establishes, needs_net in CHECKS:
        if needs_net and not online:
            rows.append({"label": label, "state": "skipped", "seconds": 0.0,
                         "establishes": establishes, "why": "network check, run with --online"})
            continue
        entry = cmd[2] if cmd[0] == "-m" else cmd[0]
        if not os.path.exists(os.path.join(REPO, entry)):
            rows.append({"label": label, "state": "absent", "seconds": 0.0,
                         "establishes": establishes, "why": "%s is not in this tree" % cmd[0]})
            continue
        r, dt = run(cmd)
        out = r.stdout + r.stderr
        if "SKIPPED:" in out:
            rows.append({"label": label, "state": "skipped", "seconds": round(dt, 3),
                         "establishes": establishes,
                         "why": out.strip().splitlines()[-1][:120]})
            continue
        ok = needle in out
        rows.append({"label": label, "state": "ok" if ok else "FAILED",
                     "seconds": round(dt, 3), "establishes": establishes,
                     "why": "" if ok else "expected %r, got %r" % (needle, (r.stdout + r.stderr)[-160:])})

    print("%-32s %-8s %7s  %s" % ("check", "state", "sec", "what it establishes"))
    for r in rows:
        print("%-32s %-8s %7.3f  %s" % (r["label"], r["state"], r["seconds"], r["establishes"]))
    bad = [r for r in rows if r["state"] in ("FAILED", "absent")]
    skipped = [r for r in rows if r["state"] == "skipped"]
    total = round(sum(r["seconds"] for r in rows), 3)
    print("")
    print("%d ok, %d failed, %d skipped, %.3f s total" % (len(rows) - len(bad) - len(skipped), len(bad), len(skipped), total))
    print("VERDICT: %s" % ("OK" if not bad else "FAILED"))

    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
    for i, a in enumerate(sys.argv):
        if a == "--svg" and i + 1 < len(sys.argv):
            with open(sys.argv[i + 1], "w", encoding="utf-8") as fh:
                fh.write(svg(rows))
    return 0 if not bad else 3


COL = {"ok": "#1f7a4d", "skipped": "#8a8a8a", "absent": "#8a8a8a", "FAILED": "#b3261e"}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(rows):
    W, RH, TOP = 900, 52, 128
    H = TOP + RH * len(rows) + 74
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
           'font-family="Helvetica,Arial,sans-serif">' % (W, H, W, H),
           '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
           '<text x="40" y="52" font-size="23" font-weight="700" fill="#111">'
           'Seven checks, one command, one exit code</text>',
           '<text x="40" y="78" font-size="12.5" fill="#555">'
           'Each row is what a stranger can re-run; a claim in prose without a row here is a claim '
           'this repository does not make.</text>',
           '<text x="40" y="100" font-size="11.5" fill="#777">'
           'python3 tools/run_all_evidence.py --online   (offline rows run by default)</text>']
    for i, r in enumerate(rows):
        y = TOP + i * RH
        c = COL.get(r["state"], "#333")
        out.append('<circle cx="52" cy="%d" r="6" fill="%s"/>' % (y + 14, c))
        out.append('<text x="74" y="%d" font-size="14" font-weight="600" fill="#111">%s</text>'
                   % (y + 19, esc(r["label"])))
        out.append('<text x="74" y="%d" font-size="11" fill="#666">%s</text>'
                   % (y + 37, esc(r["establishes"])))
        t = ("%.2f s" % r["seconds"]) if r["state"] != "skipped" else "network"
        out.append('<text x="%d" y="%d" font-size="12" fill="%s" text-anchor="end">%s</text>'
                   % (W - 40, y + 19, c, esc(r["state"])))
        out.append('<text x="%d" y="%d" font-size="11" fill="#888" text-anchor="end">%s</text>'
                   % (W - 40, y + 37, esc(t)))
        out.append('<line x1="40" y1="%d" x2="%d" y2="%d" stroke="#eee"/>' % (y + RH - 6, W - 40, y + RH - 6))
    ok = len([r for r in rows if r["state"] == "ok"])
    skipped = len([r for r in rows if r["state"] == "skipped"])
    tail = ("%d of %d ran; %d need the network" % (ok, len(rows), skipped)) if skipped \
        else ("%d of %d ran, including the three network checks" % (ok, len(rows)))
    out.append('<text x="40" y="%d" font-size="12" fill="#444">%s</text>' % (H - 30, tail))
    out.append('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
