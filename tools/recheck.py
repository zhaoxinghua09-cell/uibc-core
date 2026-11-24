#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-check every crosswalk with one command.

Why this exists: reproducing the counts in the documents used to need six
invocations of `crosswalk_probe.py` plus a shell loop plus a hand comparison.
A reader who has to write a loop is a reader who will not check. This runs the
same evaluation as `crosswalk_probe.py`, compares each fresh result with the
committed one byte for byte, and prints one table.

Exit codes, same vocabulary as the single-file tool:

  0  every crosswalk reproduces, no OVERCLAIM, no UNDECLARED
  1  at least one row is OVERCLAIM or UNDECLARED (a claim outran its evidence)
  2  a crosswalk could not be read, or its schema is not uibc-crosswalk/1
  3  at least one result does not reproduce the committed file (drift)
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import crosswalk_probe as cp  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Re-run every crosswalk under crosswalk/ and compare with tools/out/.")
    ap.add_argument("--no-probe", action="store_true",
                    help="static check only; carried rows become UNRUN and drift is not checked")
    ap.add_argument("--out-dir", default=str(REPO / "tools" / "out"),
                    help="where the committed results live (default: tools/out)")
    ap.add_argument("--json", dest="json_out", help="write the summary here")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    cross = REPO / "crosswalk"
    files = sorted(cross.glob("*.json"))
    if not files:
        sys.stderr.write("no crosswalks under %s\n" % cross)
        return 2

    out_dir = Path(args.out_dir)
    summary = []
    totals = {}
    worst = 0
    for f in files:
        name = f.stem
        try:
            with open(f, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError) as exc:
            sys.stderr.write("cannot read %s: %s\n" % (name, exc))
            return 2
        if doc.get("schema") != cp.SCHEMA:
            sys.stderr.write("refusing %s: schema is %r, expected %r\n"
                             % (name, doc.get("schema"), cp.SCHEMA))
            return 2
        # Same as the single-file tool: the source path is part of the result,
        # so a re-run elsewhere produces the same bytes as the committed file.
        doc.setdefault("standard", {})["source"] = os.path.relpath(f, REPO).replace("\\", "/")
        res = cp.evaluate(doc, cwd=REPO, run=not args.no_probe)

        committed = out_dir / ("crosswalk-%s.json" % name)
        drift = "unrun"
        old = None
        if not args.no_probe:
            fresh = cp.dumps_result(res)
            if not committed.exists():
                drift = "missing"
            else:
                try:
                    old = committed.read_text(encoding="utf-8")
                except OSError as exc:
                    sys.stderr.write("cannot read %s: %s\n" % (committed, exc))
                    return 2
                drift = "same" if old == fresh else "drift"
            if drift != "same":
                worst = max(worst, 3)
                if old is None:
                    # A source distribution does not ship tools/out, so this is a
                    # legitimate state rather than a defect: say so, and keep the
                    # exit code (nothing was compared, so nothing is proven).
                    print("  no committed result at %s - nothing to compare" % committed)
                else:
                    # Byte counts alone were not enough last time: the first failing
                    # run on Linux said only "6974 vs 6830", and the field that had
                    # moved was a path. Point at the first differing line.
                    a, b = old.splitlines(), fresh.splitlines()
                    for i, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            print("  first difference in %s at line %d:\n  - %s\n  + %s"
                                  % (name, i + 1, x.strip()[:160], y.strip()[:160]))
                            break
                    if len(a) != len(b):
                        print("  line counts differ: committed=%d fresh=%d" % (len(a), len(b)))
        if res["bad"]:
            worst = max(worst, 1)

        for k, v in res["counts"].items():
            totals[k] = totals.get(k, 0) + v
        summary.append({
            "crosswalk": name,
            "clauses": res["clause_count"],
            "counts": res["counts"],
            "bad": res["bad"],
            "verdict": res["verdict"],
            "drift": drift,
            "manifest_sha256": res["manifest_sha256"],
            "verdict_sha256": res["verdict_sha256"],
        })
        if not args.quiet:
            states = "  ".join("%s=%d" % (k, res["counts"][k]) for k in sorted(res["counts"]))
            print("%-26s n=%-3d %-40s bad=%d  %-8s %s"
                  % (name, res["clause_count"], states, res["bad"], res["verdict"], drift))

    if not args.quiet:
        print("\ntotal clauses=%d  %s  bad=%d"
              % (sum(s["clauses"] for s in summary),
                 "  ".join("%s=%d" % (k, totals[k]) for k in sorted(totals)),
                 sum(s["bad"] for s in summary)))
        print("note: the total includes tool-contract.json, which is a tool contract, "
              "not a regulation; the regulated total excludes it.")

    if args.json_out:
        payload = {"schema": "uibc-crosswalk-recheck/1",
                   "totals": totals, "crosswalks": summary, "exit": worst}
        out = args.json_out if os.path.isabs(args.json_out) else os.path.join(REPO, args.json_out)
        os.makedirs(os.path.dirname(out) or str(REPO), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return worst


if __name__ == "__main__":
    sys.exit(main())
