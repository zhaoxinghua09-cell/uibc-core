"""Does this anchor continue the line, or is it an old one replayed?

A single anchor answers "is this the package that publisher signed, in that
state?" It cannot answer "is this the *latest* state". An attacker who kept a
copy of yesterday's perfectly self-consistent bundle and its anchor can hand a
stranger both, and every check passes - the two agree with each other, because
they always did.

The fix is small and old: make each anchor name the one before it.

    seq                 1, 2, 3 ... never reused
    prev_anchor_digest  the anchor_digest of seq-1, null at seq 1

A verifier holding anchor N can then tell that anchor N-3 is stale even when
N-3 is internally perfect. Ordering is what a digest never had.

What this still cannot do: stop somebody from *withholding* the newer anchors.
Whoever controls the channel controls what you see. The countermeasure is
distribution - publish the anchors somewhere they cannot be quietly pruned -
not more mathematics here.

Usage:
    python3 tools/anchor_chain.py ANCHOR_DIR [--expect-latest N] [--json]
    python3 tools/anchor_chain.py ANCHOR_DIR --append-cmd   # hint for the next anchor

Exit: 0 OK   4 CHAIN BROKEN   5 STALE (older than what the caller already knows)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from anchor_check import anchor_digest  # noqa: E402


def load_chain(anchor_dir):
    """Every *.json under the directory that looks like an anchor, ordered."""
    out = []
    for path in sorted(glob.glob(os.path.join(anchor_dir, "*.json"))):
        try:
            a = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(a, dict) or "checkpoint_head" not in a:
            continue
        out.append((path, a))
    return out


def check_chain(entries):
    """Return (ok, problems, ordered list of (seq, path))."""
    problems = []
    if not entries:
        return False, ["no anchor files found"], []
    by_seq = {}
    for path, a in entries:
        seq = a.get("seq")
        if not isinstance(seq, int) or seq < 1:
            problems.append("%s: seq is missing or not a positive integer "
                            "(an anchor without a position cannot be ordered)"
                            % os.path.basename(path))
            continue
        if seq in by_seq:
            problems.append("seq %d appears twice: %s and %s - a replayed anchor"
                            % (seq, os.path.basename(by_seq[seq][0]),
                               os.path.basename(path)))
            continue
        by_seq[seq] = (path, a)

    ordered = sorted(by_seq.items())
    if problems:
        return False, problems, [(s, p) for s, (p, _) in ordered]

    expect = 1
    for seq, (path, a) in ordered:
        if seq != expect:
            problems.append("seq %d is missing: the chain has a gap between %d and %d"
                            % (expect, expect - 1, seq))
            return False, problems, [(s, p) for s, (p, _) in ordered]
        prev = a.get("prev_anchor_digest")
        if seq == 1:
            if prev is not None:
                problems.append("seq 1 declares prev_anchor_digest %r - the first "
                                "anchor has nothing before it" % (prev,))
                return False, problems, [(s, p) for s, (p, _) in ordered]
        else:
            prev_anchor = by_seq[seq - 1][1]
            if prev != anchor_digest(prev_anchor):
                problems.append(
                    "seq %d declares prev_anchor_digest %s but seq %d is %s - "
                    "the chain was rewritten, or an anchor was swapped in place"
                    % (seq, (str(prev) or "<null>")[:16], seq - 1,
                       anchor_digest(prev_anchor)[:16]))
                return False, problems, [(s, p) for s, (p, _) in ordered]
        expect += 1
    return True, problems, [(s, p) for s, (p, _) in ordered]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("anchor_dir")
    ap.add_argument("--expect-latest", type=int,
                    help="the newest seq the caller already knows about; "
                         "a shorter chain means anchors are being withheld")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    entries = load_chain(args.anchor_dir)
    ok, problems, ordered = check_chain(entries)
    latest = ordered[-1][0] if ordered else 0

    stale = False
    if ok and args.expect_latest is not None and latest < args.expect_latest:
        stale = True
        problems.append("chain stops at seq %d but the caller already knows of "
                        "seq %d - newer anchors are missing, not merely absent"
                        % (latest, args.expect_latest))

    verdict = ("CHAIN OK" if ok and not stale else
               ("STALE" if ok and stale else "CHAIN BROKEN"))
    if args.json:
        print(json.dumps({"verdict": verdict, "latest_seq": latest,
                          "anchors": [{"seq": s, "file": os.path.basename(p)}
                                      for s, p in ordered],
                          "problems": problems}, indent=2, ensure_ascii=False))
    else:
        print("VERDICT: %s" % verdict)
        print("anchors: %d (seq 1..%d)" % (len(ordered), latest))
        for s, p in ordered:
            print("  %2d  %s  head %s" % (s, os.path.basename(p),
                                         str(load_head(p))[:20]))
        for p in problems:
            print("  - %s" % p)
    return 0 if verdict == "CHAIN OK" else (5 if verdict == "STALE" else 4)


def load_head(path):
    try:
        return json.load(open(path, encoding="utf-8")).get("checkpoint_head", "")
    except Exception:
        return ""


if __name__ == "__main__":
    sys.exit(main())
