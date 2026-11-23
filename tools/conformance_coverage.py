#!/usr/bin/env python3
"""Which verification check does each conformance case exercise — and which
checks have no case at all.

The second half is the point. A coverage table that lists only what you test
invites a reader to assume the rest is covered; publishing the empty cells, with
a reason each, is the cheap way to stop that assumption. Three checks here have
no self-contained case by construction, and this tool names them rather than
quietly leaving them out.

    python tools/conformance_coverage.py            # write conformance/coverage.json
    python tools/conformance_coverage.py --print    # human summary
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
MANIFEST = os.path.join(ROOT, "conformance", "manifest.json")
INDEX = os.path.join(ROOT, "docs", "EVIDENCE-INDEX.md")
OUT = os.path.join(ROOT, "conformance", "coverage.json")

# Each uncovered check, and why no self-contained package case can state it.
# Kept in code, not in the JSON, so the JSON regenerates byte-for-byte.
EXCLUDED = {
    "S0": "不是检查项：验证器自身抛异常时的兜底条目，无可构造攻击（见 docs/EVIDENCE-INDEX.md 脚注）",
}

UNCOVERED_REASONS = {
    "S9": "需要带外参数（钉住的链头），不在包内，无法由包本身判定；由 head-pinned 模式的篡改基准 M20 与延迟/复跑脚本覆盖",
    "S16": "需要外部 RFC 3161 时间戳 token，不在包内；由 `tools/anchor_tsa.py --verify`（仓内已附 token 与 CA）覆盖",
    "S19": "需要跨包的新鲜度状态（重放/旧序号），单包无法自证；由红队 RT16 与 head-pinned 模式覆盖",
}


def index_rows(path: str):
    ids = []
    text = open(path, encoding="utf-8").read()
    for line in text.splitlines():
        m = re.match(r"\|\s*(S\d+)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            ids.append((m.group(1), m.group(2).strip()))
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="show", action="store_true")
    a = ap.parse_args()

    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    cases = manifest["cases"]
    checks = [(cid, title) for cid, title in index_rows(INDEX) if cid not in EXCLUDED]
    known = [cid for cid, _ in checks]

    by_check = {cid: [] for cid in known}
    unknown = []
    for c in cases:
        for ch in c.get("expected_checks", []):
            if ch in by_check:
                by_check[ch].append(c["id"])
            elif ch not in unknown:
                unknown.append(ch)

    covered = [cid for cid in known if by_check[cid]]
    uncovered = [cid for cid in known if not by_check[cid]]
    doc = {
        "format": "uibc-core/conformance-coverage/1",
        "generated_by": "tools/conformance_coverage.py",
        "source": {"manifest": "conformance/manifest.json", "checks": "docs/EVIDENCE-INDEX.md"},
        "totals": {"cases": len(cases), "checks": len(known),
                   "covered": len(covered), "uncovered": len(uncovered)},
        "checks": [{"id": cid, "title": title, "cases": by_check[cid]}
                   for cid, title in checks],
        "excluded": [{"id": cid, "reason": why} for cid, why in EXCLUDED.items()],
        "uncovered": [{"id": cid, "title": dict(checks)[cid],
                       "reason": UNCOVERED_REASONS.get(cid, "尚无用例，理由未登记——这是缺口，不是已覆盖")}
                      for cid in uncovered],
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("%s: %d cases, %d/%d checks covered, %d uncovered (%s)"
          % (OUT, len(cases), len(covered), len(known), len(uncovered), ", ".join(uncovered)))
    if a.show:
        for cid, title in checks:
            print("  %-4s %-38s %s" % (cid, title[:38], ", ".join(by_check[cid]) or "—"))
    if unknown:
        print("unknown check ids in manifest: %s" % unknown)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
