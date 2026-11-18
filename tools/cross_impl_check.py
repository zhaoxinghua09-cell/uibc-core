#!/usr/bin/env python3
"""Compare the JavaScript structural verifier with the Python one, case by case.

The point is not to award a score but to state the boundary: which of the 34
conformance packages a second language can decide, which it cannot, and where
the two implementations disagree. Every number printed here is measured.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JS = os.path.join(REPO, "tools", "verify-js", "verify.mjs")
MANIFEST = os.path.join(REPO, "conformance", "manifest.json")

COVERED = ("S1", "S2", "S4", "S5", "S6", "S7", "S10", "S11", "S12", "S13", "S14")


def run_js(pkg):
    out = subprocess.run(["node", JS, pkg], capture_output=True, text=True)
    if out.returncode != 0 and not out.stdout:
        return None
    return json.loads(out.stdout)


def run_py(pkg):
    sys.path.insert(0, REPO)
    from uibc_core.verify import verify
    return verify(pkg)


def failed_ids(report):
    return {c["id"] for c in report.get("checks", [])
            if str(c.get("result", "")).upper() == "FAIL"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    man = json.load(open(MANIFEST, encoding="utf-8"))
    if not shutil.which("node"):
        print("node is not installed; nothing to compare")
        return 2

    rows = []
    for case in man["cases"]:
        pkg = os.path.join(REPO, "conformance", case["path"])
        js = run_js(pkg)
        py = run_py(pkg)
        js_fail = failed_ids(js) if js else set()
        py_fail = failed_ids(py)
        expected = set(case.get("expected_checks") or [])
        accept = case.get("expect") == "accept"
        covered = expected & set(COVERED) if not accept else set()
        rows.append({
            "id": case["id"],
            "attack": case["attack"],
            "expect": "accept" if accept else ("refuse:" + ",".join(sorted(expected))),
            "js_result": (js or {}).get("result"),
            "js_failed": sorted(js_fail),
            "py_failed": sorted(py_fail),
            "in_scope": bool(accept) or bool(covered),
            "agree": (js_fail == py_fail) if not accept else (js_fail == set()),
            "acceptable": sorted(set(js_fail) & expected) if expected else None,
        })

    in_scope = [r for r in rows if r["in_scope"]]
    inconclusive_by_scope = [r for r in rows if not r["in_scope"]]

    summary = {
        "cases": len(rows),
        "js_covered_checks": list(COVERED),
        "in_scope": len(in_scope),
        "out_of_scope": len(inconclusive_by_scope),
        "agree_with_python": sum(1 for r in rows if r["agree"]),
        "named_an_expected_check": sum(1 for r in rows if r["acceptable"]),
        "rows": rows,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print("cross-implementation check: %d cases, JS covers %d checks (%s)"
          % (len(rows), len(COVERED), ", ".join(COVERED)))
    print("  in scope for the JS verifier : %d" % summary["in_scope"])
    print("  out of scope (needs Ed25519 / RFC 3161 / v1.1 tree): %d"
          % summary["out_of_scope"])
    print("  same FAIL set as Python     : %d" % summary["agree_with_python"])
    print("  named an expected check     : %d" % summary["named_an_expected_check"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
