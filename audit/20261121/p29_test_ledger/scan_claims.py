# -*- coding: utf-8 -*-
"""文档声称数 vs 实测台账 —— 漂移扫描器。

用途：把 README / EVIDENCE-INDEX / CHANGELOG 等文档里"多少项通过"的数字抽出来，
与 gen_test_ledger.py 产出的真实台账对齐，输出漂移清单。

不做的事：不改文档。只报告。
"""
import argparse
import json
import re
from pathlib import Path

PATTERNS = [
    (r"(\d{2,4})\s*项通过", "项通过"),
    (r"(\d{2,4})\s*(?:tests?\s*)?(?:pass|passed)", "tests passed"),
    (r"(\d{2,4})\s*OK\b", "N OK"),
    (r"(\d{2,4})\s*个?\s*(?:test|测试)", "N tests"),
    (r"(\d{2,4})\s*/\s*(\d{2,4})", "N/M"),
]


def scan(root: Path, glob="*.md"):
    rows = []
    for path in sorted(root.glob(glob)):
        if path.name.startswith("_"):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for pat, label in PATTERNS:
                for m in re.finditer(pat, line, re.I):
                    rows.append({
                        "file": path.name,
                        "line": lineno,
                        "kind": label,
                        "numbers": list(m.groups()),
                        "text": line.strip()[:160],
                    })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ledger", default="")
    ap.add_argument("--out", default="claims.json")
    a = ap.parse_args()

    root = Path(a.repo).resolve()
    claims = scan(root)

    actual = None
    if a.ledger and Path(a.ledger).exists():
        ledger = json.loads(Path(a.ledger).read_text(encoding="utf-8"))
        actual = {"collected": ledger["totals"]["collected"],
                  "passed": ledger["totals"]["passed"],
                  "skipped": ledger["totals"]["skipped"],
                  "commit": ledger["git"]["commit"]}

    drift = []
    if actual:
        for c in claims:
            for n in c["numbers"]:
                if not n.isdigit():
                    continue
                v = int(n)
                if v in (actual["collected"], actual["passed"], actual["passed"] - actual["skipped"]):
                    continue
                if v < 100:      # 小的 N/M 之类不参与漂移判定
                    continue
                drift.append({**c, "claimed": v})

    payload = {"repo": str(root), "claim_count": len(claims),
               "actual": actual, "drift": drift, "claims": claims}
    Path(a.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"claims={len(claims)}  actual={actual}")
    if drift:
        print(f"\n漂移（{len(drift)} 条）:")
        for d in drift:
            print(f"  {d['file']}:{d['line']}  声称 {d['claimed']}  |  {d['text'][:90]}")
    else:
        print("无漂移")
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
