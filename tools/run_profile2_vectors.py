"""Replay conformance/profile2/cases.json -- the `/2` tier's outsider entry point.

Needs the repository only: no service, no key, no network. Exit code 0 only when
every case matches its recorded verdict and issuer state.

    python tools/run_profile2_vectors.py [--json]
"""

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import profile2  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "conformance", "profile2", "cases.json")


def run():
    doc = json.load(io.open(CASES, encoding="utf-8"))
    rows = []
    ok_all = True
    for c in doc["cases"]:
        receipt = open(os.path.join(ROOT, "conformance", "profile2", c["receipt"]), "rb").read()
        res = profile2.verify(os.path.join(ROOT, c["package"]), receipt,
                              trusted_issuers=c.get("trusted_issuers"),
                              trusted_size=c.get("trusted_size"))
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
        print(json.dumps({"profile": doc["profile"], "ok": ok_all, "ok_cases": doc["ok_cases"],
                          "cases": rows}, ensure_ascii=False, indent=1))
        return 0 if ok_all else 1
    print("profile %s, %d cases, %d recorded OK" % (doc["profile"], len(rows), len(doc["ok_cases"])))
    for r in rows:
        print("  %s %-18s %-28s issuer %-12s %s" % (
            "ok " if r["ok"] else "BAD", r["id"], r["expected"]["verdict"],
            r["expected"]["issuer"], r["change"]))
    print("RESULT:", "all cases match" if ok_all else "MISMATCH")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
