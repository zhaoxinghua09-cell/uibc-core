"""Replay conformance/profile/cases.json and compare with its recorded verdicts.

This is the tier's outsider entry point: it needs nothing but the repository (no
transparency service, no key, no network). Exit code is 0 only when every case
matches its recorded verdict and issuer state.

    python tools/run_profile_vectors.py [--json]
"""

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import profile  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "conformance", "profile", "cases.json")


def run():
    doc = json.load(io.open(CASES, encoding="utf-8"))
    rows = []
    ok_all = True
    for c in doc["cases"]:
        receipt = open(os.path.join(ROOT, "conformance", "profile", c["receipt"]), "rb").read()
        res = profile.verify(os.path.join(ROOT, c["package"]), receipt,
                             trusted_size=c.get("trusted_size"),
                             trusted_issuers=c.get("trusted_issuers"))
        got = {"verdict": res["verdict"], "issuer": res["issuer"]}
        ok = got == c["expected"]
        ok_all = ok_all and ok
        rows.append({"id": c["id"], "expected": c["expected"], "got": got,
                     "ok": ok, "change": c["change"]})
    return ok_all, doc, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ok_all, doc, rows = run()
    if a.json:
        print(json.dumps({"profile": doc["profile"], "ok": ok_all, "cases": rows},
                         ensure_ascii=False, indent=1))
        return 0 if ok_all else 1
    print("profile %s, %d cases" % (doc["profile"], len(rows)))
    for r in rows:
        mark = "ok " if r["ok"] else "BAD"
        print("  %s %-15s %-28s issuer %-12s %s" % (
            mark, r["id"], r["expected"]["verdict"], r["expected"]["issuer"], r["change"]))
    print("RESULT:", "all cases match" if ok_all else "MISMATCH")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
