"""Cross-implementation agreement matrix.

The repo carries two verifiers: the reference (`uibc_core`) and an independent
reader written against the text (`independent_verifier/iverify.py`). The corpus
`oracle_check.py` compares them, but only inside its own emit path and only for
the cases it built in-process. This tool takes the *committed* corpus, runs both
readers over the bytes on disk, and reports where they agree.

Why this matters: a corpus that only one implementation passes is a
transcription of that implementation's behaviour, not a test of the text. The
number below is the honest size of that claim.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "independent_verifier"))

from uibc_core.cli import verify as ref_verify          # noqa: E402
import iverify                                          # noqa: E402

V_TO_S = {"S11": "S11", "S1": "S1", "S2": "S2", "S3": "S3", "S4": "S4",
          "S12": "S12", "S14": "S14", "S7": "S7", "S5": "S5", "S8": "S8",
          "S6": "S6", "S15": "S15", "S16": "S16", "S9": "S9", "S19": "S19"}

# What the in-repo independent reader actually covers, read off its source (the
# V1..V10 assignments in independent_verifier/iverify.py), NOT off any statement
# it makes about itself. Ten outcomes stand in for nineteen checks: the anchor,
# freshness, receipt and encoding checks are simply absent, so their outcome is
# necessarily INCONCLUSIVE. This map is the reason a bare "verdict agreement"
# number would overstate the disagreement as a contradiction.
COVERAGE = {
    "V1": ["S1"], "V2": ["S2"], "V3": ["S3"], "V4": ["S4"], "V5": ["S5"],
    "V6": ["S6"], "V7": ["S1", "S10"], "V8": ["S7"], "V9": ["S8"], "V10": ["S12"],
}
S_ALL = ["S%d" % i for i in range(1, 20)]
COVERED = sorted({s for v in COVERAGE.values() for s in v}, key=lambda c: int(c[1:]))
UNCOVERED = [s for s in S_ALL if s not in COVERED]


def num(cid):
    digits = "".join(ch for ch in str(cid) if ch.isdigit())
    return int(digits) if digits else 10 ** 6


def first_fail(pairs):
    failing = [c for c, r in pairs if r == "FAIL"]
    return min(failing, key=num) if failing else None


def failing_set(pairs):
    return sorted((c for c, r in pairs if r == "FAIL"), key=num)


def main():
    oracle = os.path.join(REPO, "conformance", "oracle")
    cases = json.load(open(os.path.join(oracle, "expected.json"), encoding="utf-8"))["cases"]
    keys = json.load(open(os.path.join(oracle, "keys.json"), encoding="utf-8"))["keys"]

    # iverify's ids are its own vocabulary; the map is from the corpus tool so the
    # comparison is not invented here.
    try:
        import oracle_check as oc
        v_to_s = getattr(oc, "V_TO_S", V_TO_S)
        keys_used = getattr(oc, "V_TO_S", V_TO_S)
    except Exception:
        v_to_s = V_TO_S

    rows = []
    for case in cases:
        name = case["case"]
        path = os.path.join(oracle, "cases", name)
        key = bytes.fromhex(keys[name]) if case.get("mode") == "strict" else None
        try:
            ref = ref_verify(path, key=key)
            ref_pairs = [(c["id"], c["result"]) for c in ref["checks"]]
            ref_verdict, ref_first = ref["result"], first_fail(ref_pairs)
        except Exception as e:                                  # noqa: BLE001
            rows.append({"case": name, "error": "ref: %s" % e})
            continue
        ind_verdict, ind_first = None, None
        try:
            ind = iverify.independent_verify(path, key=key)
            ind_pairs = [(v_to_s.get(k, k), v) for k, v in ind["checks"].items()]
            ind_verdict, ind_first = ind["result"], first_fail(ind_pairs)
        except Exception as e:                                  # noqa: BLE001
            rows.append({"case": name, "error": "ind: %s" % e})
            continue

        # A divergence whose designed check is one this reader does not implement
        # is a coverage gap, not two implementations reading the same text
        # differently. Both are recorded; only the second is a contradiction.
        want = case.get("expected_failed_checks") or [case.get("expected_first_fail")]
        designed_uncovered = [c for c in want if c in UNCOVERED]
        rows.append({
            "case": name,
            "mode": case.get("mode"),
            "expected": case["expected_verdict"],
            "ref": ref_verdict, "ind": ind_verdict,
            "verdict_agree": ref_verdict == ind_verdict,
            "ref_first": ref_first, "ind_first": ind_first,
            "first_agree": ref_first == ind_first,
            "ref_set": failing_set(ref_pairs), "ind_set": failing_set(ind_pairs),
            "set_agree": failing_set(ref_pairs) == failing_set(ind_pairs),
            "both_match_oracle": (ref_verdict == ind_verdict == case["expected_verdict"]),
            "designed_uncovered": designed_uncovered,
            "kind": ("agree" if ref_verdict == ind_verdict else
                     "coverage-gap" if designed_uncovered else
                     "accept-divergence" if case["expected_verdict"] == "PASS" else
                     "contradiction"),
        })

    ok = [r for r in rows if "error" not in r]
    summary = {
        "cases": len(rows),
        "compared": len(ok),
        "errors": len(rows) - len(ok),
        "verdict_agree": sum(1 for r in ok if r["verdict_agree"]),
        "first_agree": sum(1 for r in ok if r["first_agree"]),
        "set_agree": sum(1 for r in ok if r["set_agree"]),
        "both_match_oracle": sum(1 for r in ok if r["both_match_oracle"]),
        "coverage_gap": sum(1 for r in ok if r["kind"] == "coverage-gap"),
        "contradiction": sum(1 for r in ok if r["kind"] == "contradiction"),
        "accept_divergence": sum(1 for r in ok if r["kind"] == "accept-divergence"),
        "covered_checks": len(COVERED),
        "uncovered_checks": UNCOVERED,
        "as_of": "2026-11-25",
    }

    out_dir = os.path.join(REPO, "out")
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"summary": summary, "rows": rows},
              open(os.path.join(out_dir, "cross_impl.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lines = ["# 双实现一致性矩阵（参考验证器 vs 独立读者）", "",
             "语料 `conformance/oracle/`，两实现读同一批磁盘字节。", "",
             "| 指标 | 值 |", "|---|---|"]
    for k in ("cases", "compared", "verdict_agree", "first_agree", "set_agree",
              "both_match_oracle", "coverage_gap", "contradiction"):
        lines.append(f"| {k} | {summary[k]} |")
    lines += ["", f"独立读者覆盖 {summary['covered_checks']}/19 项检查；未覆盖："
              + ", ".join(summary["uncovered_checks"]) + "。", ""]
    lines += ["", "| case | mode | 期望 | 参考 | 独立 | 判定同 | 首失败(参考/独立) | 失败集同 |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['case']} | — | — | ERROR | ERROR | ✗ | {r['error'][:40]} | ✗ |")
            continue
        lines.append("| {c} | {m} | {e} | {r} | {i} | {v} | {rf}/{iff} | {s} |".format(
            c=r["case"], m=r["mode"], e=r["expected"], r=r["ref"], i=r["ind"],
            v="✓" if r["verdict_agree"] else "✗", rf=r["ref_first"] or "—",
            iff=r["ind_first"] or "—", s="✓" if r["set_agree"] else "✗"))
    with open(os.path.join(out_dir, "cross_impl.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["errors"] == 0 and summary["verdict_agree"] == summary["compared"] else 1


if __name__ == "__main__":
    sys.exit(main())
