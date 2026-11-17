#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LGD-Eval：第二实现交叉验证（不是组织级独立评测）。

为什么要有这一步：同一个作者写的验证器和被测物，本质上是一份意见的两次复述。
所以这里用 `independent_verifier/iverify.py`（不导入 uibc_core.verify 的任何逻辑，
自带 JCS 与 Ed25519 实现）对同一批包独立出裁决，逐包比对。

**边界声明（必须与结论一起引用）**：两套实现出自同一仓库、同一作者，
只做到"代码路径不共用"，做不到"利益隔离"。真正的独立评测需要第三方持钥复跑，
本脚本不声称替代它。因此本脚本的输出只能证明"实现间一致"，不能证明"结论正确"。

用法： python tools/lgd_eval.py
产出： tools/out/lgd_eval_result.json
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "independent_verifier"))
sys.path.insert(0, ROOT)

from iverify import independent_verify              # noqa: E402
from uibc_core.verify import verify                 # noqa: E402

OUT = os.path.join(ROOT, "tools", "out")


def packages(base):
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "manifest.json")):
            yield name, d


def main():
    fx = os.path.join(ROOT, "fixtures")
    rows = []
    for name, d in packages(fx):
        a = verify(d)
        b = independent_verify(d)
        ra, rb = a.get("result"), b.get("result")
        rows.append({"package": name, "uibc_core": ra, "independent": rb,
                     "agree": ra == rb,
                     "a_detail": [c["id"] + ":" + c["result"] for c in a.get("checks", [])
                                  if c["result"] != "PASS"][:6],
                     "b_detail": [k + ":" + str(v) for k, v in (b.get("checks") or {}).items()
                                  if str(v) != "PASS"][:6]})

    total = len(rows)
    agree = sum(1 for r in rows if r["agree"])
    doc = {
        "meta": {
            "what_this_is": "two-implementation cross-check, NOT an organization-level "
                            "independent evaluation",
            "boundary": "both implementations live in the same repository and share an "
                        "author; only the code paths are separate.利益隔离未成立。",
            "packages": total, "agree": agree,
            "agreement_rate": round(agree / total, 3) if total else None,
        },
        "rows": rows,
    }
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "lgd_eval_result.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    for r in rows:
        mark = "==" if r["agree"] else "!!"
        print("%-28s %-14s %-14s %s" % (r["package"], r["uibc_core"], r["independent"], mark))
    print("\n一致 %d/%d" % (agree, total))
    print("RESULT_JSON=" + p)


if __name__ == "__main__":
    main()
