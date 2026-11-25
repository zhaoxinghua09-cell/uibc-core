"""Run the authority-age vectors and print a line per case.

    python tools/run_authority_age_vectors.py

Exit code 0 only when every case matches its expected state, so this can be
used as a check in CI or by an outside reviewer without reading our prose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uibc_core.authority_age import (
    commit_recheck,
    commit_recheck_from_history,
    decision_record,
)

CASES = Path(__file__).resolve().parent.parent / "vectors" / "authority-age" / "cases.json"


def main() -> int:
    doc = json.loads(CASES.read_text(encoding="utf-8"))
    failures = 0
    print("schema: %s   as_of: %s" % (doc["schema"], doc["as_of"]))
    for case in doc["cases"]:
        if case.get("kind") in ("commit", "history"):
            if case.get("kind") == "history":
                result = commit_recheck_from_history(
                    case["histories"], case["commit_at"], case["bounds"])
                rows = result["links"]
            else:
                result = commit_recheck(case["answers"], case["commit_at"], case["bounds"])
                rows = result["answer_checks"]
            got, want = result["state"], case["expect_state"]
            reasons = ",".join(result["reason_codes"]) or "-"
            detail = "outcome=%s/%s reasons=%s" % (result["outcome"], case["expect_outcome"], reasons)
            if result["outcome"] != case["expect_outcome"]:
                got = "%s/%s" % (got, "wrong-outcome")
            if case.get("expect_reason") and case["expect_reason"] not in result["reason_codes"]:
                got = "%s/%s" % (got, "missing-reason")
            ages = ", ".join(
                "%s=%s" % (row["link"], "n/a" if row.get("age_seconds") is None else "%ds" % row["age_seconds"])
                for row in rows
            )
        else:
            record = decision_record(
                case["validation_at"],
                case["decision_at"],
                case["answers"],
                case["bounds"],
                conditions_met=case.get("conditions_met"),
                recourse_relied_on=case.get("recourse_relied_on"),
            )
            got, want = record["state"], case["expect_state"]
            detail = ""
            ages = ", ".join(
                "%s=%s" % (row["link"], "n/a" if row["age_seconds"] is None else "%ds" % row["age_seconds"])
                for row in record["answer_checks"]
            )
        verdict = "ok" if got == want else "MISMATCH"
        if got != want:
            failures += 1
        print("%-6s %-12s want %-12s (%s) %s %s" % (case["id"], got, want, ages, detail, verdict))
        if got != want:
            print("       why: %s" % case["why"])
    print("\n%d case(s), %d mismatch(es)" % (len(doc["cases"]), failures))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
