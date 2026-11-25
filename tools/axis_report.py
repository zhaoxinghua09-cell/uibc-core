"""Full-corpus per-axis report: expected vs measured, for every oracle case.

Axis model borrowed from draft-gruszka-scitt-statement-identification-02, which
reports each case on four independent axes instead of one aggregate score.
Here the axes are UIBC's own:

    structure : S11 S1 S2 S3 S4 S12 S14 S7 S5 S8
    seal      : S6
    anchor    : S15 S16
    freshness : S9 S19

An axis whose checks are conditional and not triggered is reported N/A, not
PASS. A missing input never becomes a pass.

Usage:
    python tools/axis_report.py --out out/axis_report [--verbose]

Exit codes: 0 every case matches its expectation (verdict and first failing
check); 1 a divergence; 2 harness error.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

AXES = {
    "structure": ["S11", "S1", "S2", "S3", "S4", "S12", "S14", "S7", "S5", "S8"],
    "seal": ["S6"],
    "anchor": ["S15", "S16"],
    "freshness": ["S9", "S19"],
}


def axis_of(checks):
    """checks: list of (id, result). Returns dict axis->state."""
    by_id = dict(checks)
    out = {}
    for axis, ids in AXES.items():
        states = [by_id.get(i, "ABSENT") for i in ids]
        if any(s == "FAIL" for s in states):
            out[axis] = "FAIL"
        elif any(s == "INCONCLUSIVE" for s in states):
            out[axis] = "INCONCLUSIVE"
        elif any(s == "PASS" for s in states) or "NOT_APPLICABLE" in states:
            out[axis] = "PASS" if "PASS" in states else "N/A"
        else:
            out[axis] = "N/A"
    return out


def first_fail(checks):
    """Lowest check number that fails, not the first FAIL line in the report.

    The report is not printed in S order (S11, S1, S2, S3, S4, S12, S7, S8, S5, S6
    on a duplicated package), so "first" is undefined until the ordering rule is
    fixed. This tool fixes it the same way `tools/oracle_check.py:first_fail` does,
    because otherwise the same package has two defensible answers and neither is
    reproducible.
    """
    def num(cid):
        digits = "".join(ch for ch in str(cid) if ch.isdigit())
        return int(digits) if digits else 10 ** 6

    failing = [cid for cid, res in checks if res == "FAIL"]
    return min(failing, key=num) if failing else None


def failing_set(checks):
    return [cid for cid, res in checks if res == "FAIL"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/axis_report")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    oracle = os.path.join(root, "conformance", "oracle")
    expected = json.load(open(os.path.join(oracle, "expected.json"), encoding="utf-8"))["cases"]
    keys = json.load(open(os.path.join(oracle, "keys.json"), encoding="utf-8"))["keys"]

    tmp = tempfile.mkdtemp(prefix="uibc-axiskeys-")
    keyfiles = {}
    for name, hx in keys.items():
        p = os.path.join(tmp, name + ".key")
        with open(p, "w", encoding="utf-8") as f:
            f.write(hx)
        keyfiles[name] = p

    rows = []
    for case in expected:
        name = case["case"]
        path = os.path.join(oracle, "cases", name)
        cmd = [sys.executable, "-m", "uibc_core.cli", "verify", path]
        # `mode` decides whether a key is supplied, exactly as the corpus README
        # instructs: strict cases are verified against the owner key, open cases are
        # verified with no key because they were sealed and then mutated on purpose. 
        # Passing a key to an open case is not "stricter": it turns S6 into a FAIL
        # that outranks the check the case was written for (measured: S6 became the
        # first fail on six open cases when this tool did that).
        if case.get("mode") == "strict":
            cmd += ["--key", keyfiles[name]]
        # The corpus "mode" field records how the case was authored, not a CLI
        # switch: passing --strict here would trip S1 on the committed
        # evidence/.lock marker of the accept cases and misreport them as FAIL.
        if case.get("expect_head"):
            cmd += ["--expect-head", case["expect_head"]]
        if case.get("state"):
            sp = os.path.join(tmp, name + ".state.json")
            with open(sp, "w", encoding="utf-8") as f:
                json.dump(case["state"], f, ensure_ascii=False)
            cmd += ["--state-file", sp]
        p = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8")
        try:
            doc = json.loads(p.stdout)
        except json.JSONDecodeError:
            rows.append({"case": name, "error": "verifier did not return JSON", "stderr": p.stderr[-300:]})
            continue
        checks = [(c.get("id"), c.get("result")) for c in doc.get("checks", [])]
        rows.append({
            "case": name,
            "expected": case.get("expected_verdict"),
            "measured": doc.get("result"),
            "verdict_ok": doc.get("result") == case.get("expected_verdict"),
            "expected_first_fail": case.get("expected_first_fail"),
            "measured_first_fail": first_fail(checks),
            "first_fail_ok": first_fail(checks) == case.get("expected_first_fail"),
            "expected_failed_checks": case.get("expected_failed_checks"),
            "failed_set_ok": (set(failing_set(checks)) == set(case["expected_failed_checks"])
                              if case.get("expected_failed_checks") else None),
            "axes": axis_of(checks),
            "checks": dict(checks),
        })
        if a.verbose:
            print(f"{name}: {doc.get('result')} (expected {case.get('expected_verdict')})")

    ok = [r for r in rows if r.get("verdict_ok") and r.get("first_fail_ok", True)
          and r.get("failed_set_ok") in (True, None) and "error" not in r]
    bad = [r for r in rows if r not in ok]

    os.makedirs(a.out, exist_ok=True)
    payload = {
        "spec": "uibc/conformance-axis-report/1",
        "corpus": {"cases": len(expected), "source": "conformance/oracle/expected.json"},
        "verifier": {"id": "uibc-core-verifier", "version": doc.get("verifier_version") if rows and "axes" in rows[-1] else None},
        "totals": {"cases": len(expected), "consistent": len(ok), "divergent": len(bad)},
        "rows": rows,
    }
    with open(os.path.join(a.out, "axis_report.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = ["| case | expected | measured | structure | seal | anchor | freshness | first fail (exp/obs) | ok |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['case']} | — | ERROR | — | — | — | — | — | ✗ |")
            continue
        ax = r["axes"]
        lines.append("| {c} | {e} | {m} | {s} | {se} | {a} | {f} | {ef}/{mf} | {ok} |".format(
            c=r["case"], e=r["expected"], m=r["measured"], s=ax["structure"], se=ax["seal"],
            a=ax["anchor"], f=ax["freshness"], ef=r["expected_first_fail"] or "—",
            mf=r["measured_first_fail"] or "—", ok="✓" if (r["verdict_ok"] and r["first_fail_ok"]) else "✗"))
    summary = f"\n合计 {payload['totals']['cases']} 例，一致 {payload['totals']['consistent']}，分歧 {payload['totals']['divergent']}。\n"
    with open(os.path.join(a.out, "axis_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + summary)

    print(summary.strip())
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
