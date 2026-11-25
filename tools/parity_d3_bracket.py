"""D3 is bracketed, not a single number.

Our D3 rule counts any `base58` mention inside a test file as "address binding"
evidence. Reading the cited lines showed that line is sometimes nothing more than
`publicKeyBase58: '...'` - a literal, not a derivation. Tightening the rule to
`deriveAddress|addressFrom|publicKeyToAddress` drops nine repositories and takes
the best competitor from 3 to 2.

Tightening alone would be its own bias: a repository can bind addresses without
ever writing the word `deriveAddress`. So the honest output is a bracket - the
number under a broad rule and the number under a strict one - and the page says
which is which.

    python tools/parity_d3_bracket.py --run --cache <tarball cache>
    python tools/parity_d3_bracket.py --check
"""

import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(HERE, "docs", "competitor-parity.json")
RECORD = os.path.join(HERE, "docs", "parity-d3-bracket.json")
PAGE = os.path.join(HERE, "docs", "D3-BRACKET.md")
TOOL = os.path.join(HERE, "tools", "competitor_gate_parity.py")

STRICT_RE = r"deriveAddress|derive_address|addressFrom(PublicKey|Key)?|publicKeyToAddress|toChecksumAddress"


def _cgp():
    spec = importlib.util.spec_from_file_location("uibc_parity", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def strict_hits(cgp, root):
    rx = re.compile(STRICT_RE, re.I)
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in cgp.SKIP_DIRS]
        for fn in filenames:
            if not fn.lower().endswith(cgp.CODELIKE):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if not cgp.TEST_RE.search(rel):
                continue
            try:
                for line in open(p, encoding="utf-8", errors="ignore").read().splitlines():
                    if rx.search(line):
                        n += 1
            except OSError:
                continue
    return n


def measure(cache):
    cgp = _cgp()
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    rows = []
    for r in snap["repos"]:
        if "error" in r:
            continue
        root, _sha, _size = cgp.fetch_pinned(r["repo"], r["sha"], cache)
        hits = strict_hits(cgp, root)
        d3_strict = 1 if (hits >= 1 and r.get("assertion_lines", 0) >= cgp.ASSERT_FLOOR) else 0
        s_broad = sum(r["dims"].values())
        s_strict = s_broad - r["dims"]["D3"] + d3_strict
        rows.append({"repo": r["repo"], "D3_broad": r["dims"]["D3"], "D3_strict": d3_strict,
                     "strict_hits": hits, "score_broad": s_broad, "score_strict": s_strict})
    rec = {
        "audited_at": snap.get("audited_at"),
        "strict_rule": STRICT_RE,
        "broad_rule": cgp.PATTERNS["address_derive"],
        "rows": rows,
        "changed": [r["repo"] for r in rows if r["D3_broad"] != r["D3_strict"]],
        "best_broad": max(r["score_broad"] for r in rows),
        "best_strict": max(r["score_strict"] for r in rows),
        # 本仓的分不吃这两个规则：它的 D3 来自可执行的地址探针（翻键/替换各一次），
        # 不是关键词命中，所以宽严两端同分。这里把它现算出来，而不是写死 10。
        "ours_broad": sum(cgp.score_ours().values()),
        "ours_strict": sum(cgp.score_ours().values()),
        "ours_reason": "本仓 D3 来自可执行的地址探针（256 翻键 0 相撞 / 1710 次替换 0 通过），"
                       "不依赖关键词，所以宽规则与严规则下同分",
    }
    open(RECORD, "w", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
    write_page(rec)
    print("changed %d of %d; best %d (broad) vs %d (strict)"
          % (len(rec["changed"]), len(rows), rec["best_broad"], rec["best_strict"]))
    return rec


def write_page(rec):
    lines = [
        "# D3 是个区间，不是一个数（每次 `--run` 重写本页）", "",
        "审计日 %s。**最好竞品：宽规则 %d/10，严规则 %d/10；本仓 %d/10 与 %d/10 两种规则下不变。**"
        % (rec["audited_at"], rec["best_broad"], rec["best_strict"],
           rec.get("ours_broad", 10), rec.get("ours_strict", 10)), "",
        "本仓为什么两端同分：%s。" % rec.get("ours_reason", ""), "",
        "- 宽规则（表现行）：test 文件里出现 `%s` 即记 1 分。" % rec["broad_rule"],
        "- 严规则：只认 `%s`。" % rec["strict_rule"], "",
        "为什么两个都要给：宽规则会把 `publicKeyBase58: '...'` 这种字面量当成\"地址派生\"证据（证据行见 "
        "`docs/COMPETITOR-EVIDENCE-LINES.md`）；严规则又可能漏掉\"绑定了地址但没写 derive\"的仓。"
        "单一数字在这里一定是偏的，所以给区间，并标明区间两端各自的规则。", "",
        "| 仓库 | D3 宽 | D3 严 | 得分 宽 → 严 |", "|---|---|---|---|",
    ]
    for r in sorted(rec["rows"], key=lambda x: -x["score_broad"]):
        mark = " **← 变了**" if r["D3_broad"] != r["D3_strict"] else ""
        lines.append("| `%s` | %d | %d | %d → %d%s |" % (
            r["repo"], r["D3_broad"], r["D3_strict"], r["score_broad"], r["score_strict"], mark))
    lines += ["", "变了 %d 家，全部是宽规则下多给的分（严规则不会加分）。" % len(rec["changed"]), "",
              "结论口径：对外只能说\"**在宽规则下最好 %d/10、严规则下 %d/10**\"，不能说\"最好就是 2 或 3\"。"
              % (rec["best_broad"], rec["best_strict"]), ""]
    open(PAGE, "w", encoding="utf-8").write("\n".join(lines))


def check():
    rec = json.load(open(RECORD, encoding="utf-8"))
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    want = {r["repo"] for r in snap["repos"] if "error" not in r}
    got = {r["repo"] for r in rec["rows"]}
    fails = []
    if want != got:
        fails.append("record covers %d repos, snapshot has %d" % (len(got), len(want)))
    if rec["best_strict"] > rec["best_broad"]:
        fails.append("the stricter rule scores a rival higher than the broad one - impossible, fix the rules")
    for r in rec["rows"]:
        if r["D3_strict"] > r["D3_broad"]:
            fails.append("strict scores higher than broad for %s" % r["repo"])
    # 本仓的行必须与快照现算一致；否则"两端同分"就成了写在页面上的断言。
    if "ours_broad" in rec and rec["ours_broad"] != sum(snap["ours"]["dims"].values()):
        fails.append("ours row in the bracket record disagrees with the snapshot")
    page = open(PAGE, encoding="utf-8").read() if os.path.exists(PAGE) else ""
    if "区间" not in page:
        fails.append("page does not state that D3 is a bracket")
    if fails:
        for f in fails[:6]:
            print("FAIL", f)
        print("D3-BRACKET FAIL (%d problem(s))" % len(fails))
        return 1
    print("D3-BRACKET OK: %d repositories, best %d/10 broad vs %d/10 strict, %d changed"
          % (len(got), rec["best_broad"], rec["best_strict"], len(rec["changed"])))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--cache", default=os.path.join(os.environ.get("TEMP", "/tmp"), "uibc-parity-cache"))
    args = ap.parse_args()
    if args.run:
        measure(args.cache)
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
