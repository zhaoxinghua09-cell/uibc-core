#!/usr/bin/env python3
"""The defect an outsider found stays fixed, or this fails.

External node 001 (Wang Guigui, Debian 13, unprivileged, no pip install) ran
`independent_verifier/cross_check.py` on `8a95747` and got exit 1:

    fixture:duplicated   S4   V4   FAIL           PASS   MISMATCH
    fixture:duplicated   S5   V5   INCONCLUSIVE   FAIL   MISMATCH

Both implementations disagreed on a package with a duplicated `evidence_id`:
one answered it with a structural check, the other with the identifier rule.
He found it from outside, on another OS, without being told where to look.

The fix landed in #186. This check keeps it landed: it runs the same comparison
and requires the two implementations to agree on those two rows. If the
divergence ever returns, this says so - and a fail here is a fail in
`run_all_evidence.py`, which is the number this project publishes.

    python3 tools/external_node_regression.py          # human
    python3 tools/external_node_regression.py --json   # machine

Exit 0 only when the duplicated-evidence_id rows agree.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = "fixture:duplicated"


def run_cross_check():
    r = subprocess.run([sys.executable, os.path.join("independent_verifier", "cross_check.py")],
                       cwd=REPO, capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def rows_for(out, fixture=FIXTURE):
    """Lines this comparison printed for one fixture, as token lists."""
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0] == fixture:
            rows.append(parts)
    return rows


def main():
    rc, out = run_cross_check()
    rows = rows_for(out)
    disagreements = [r for r in rows if "MISMATCH" in r]
    if "--json" in sys.argv:
        print(json.dumps({"cross_check_rc": rc, "rows": rows,
                          "disagreements": disagreements}, ensure_ascii=False, indent=2))
    # The rows are the evidence; the exit code of cross_check is not, because on
    # the fix it is 0 and on the bug it was 1, and this check must accept the
    # former and refuse the latter.
    if not rows:
        print("VERDICT: NO ROWS - the fixture the outsider used is no longer compared")
        print("This check cannot vouch for the fix; treat as a failure, not a pass.")
        return 1
    for r in rows:
        print("  " + "  ".join(r))
    if disagreements:
        print("VERDICT: REGRESSED - the two implementations disagree again on %s" % FIXTURE)
        print("External node 001 found exactly this. It is not a flaky test; find the spec.")
        return 1
    print("")
    print("%d row(s) on %s, %d disagreement(s)" % (len(rows), FIXTURE, len(disagreements)))
    print("VERDICT: STILL FIXED - both implementations answer a duplicated evidence_id the same way")
    print("Note: this establishes that the defect the outsider found has not returned. "
          "It does not establish that his run is reproducible today; that needs a re-run by him.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
