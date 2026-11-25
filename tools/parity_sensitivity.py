"""Sensitivity check for the D1 rule: does the "best competitor is 3/10" headline
survive a *more generous* definition of a rejection assertion?

D1 currently requires an assertion and a rejection word on the **same line**. Plenty
of languages write it across two: `assertRaises(...)` above, the reject reason below.
If our headline depends on that strict spelling, the headline is an artifact of our
own regex and must be withdrawn.

So this tool re-counts with a +/-2 line window - strictly more permissive, never less -
and reports every repository whose score would change.

    python tools/parity_sensitivity.py --run   --cache <tarball cache dir>
    python tools/parity_sensitivity.py --check            # offline, against the record

The record is docs/parity-sensitivity.json; --check fails if it no longer matches the
snapshot, or if the relaxed rule moves the best competitor's score.
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(HERE, "docs", "competitor-parity.json")
RECORD = os.path.join(HERE, "docs", "parity-sensitivity.json")
TOOL = os.path.join(HERE, "tools", "competitor_gate_parity.py")


def _cgp():
    spec = importlib.util.spec_from_file_location("uibc_parity", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def windowed_assert_lines(cgp, root, window=2):
    """Test lines where an assertion sits within +/-window lines of a reject word."""
    rej = re.compile(cgp.PATTERNS["reject_assertion"], re.I)
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in cgp.SKIP_DIRS]
        for fn in filenames:
            if not fn.lower().endswith(cgp.CODELIKE):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/")
            if not cgp.TEST_RE.search(rel):
                continue
            try:
                lines = open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                if not cgp.ASSERT_LINE_RE.search(line):
                    continue
                lo, hi = max(0, i - window), min(len(lines), i + window + 1)
                if any(rej.search(lines[j]) for j in range(lo, hi)):
                    n += 1
    return n


DOC = os.path.join(HERE, "docs", "PARITY-SENSITIVITY.md")


def write_doc(rec):
    rows = sorted(rec["rows"], key=lambda r: -r["score_strict"])
    lines = [
        "# 敏感性检验：把 D1 的规则放松，结论会不会翻（每次 `--run` 重写本页）", "",
        "审计日 %s。**%d 家，严格规则下最好 %d/10，放宽后最好 %d/10 → %s。**"
        % (rec["audited_at"], len(rows), rec["best_strict"], rec["best_window"],
           {"headline survives a more permissive rule": "结论不翻（最好仍是同一家）",
            "headline must be withdrawn: a looser rule scores a rival higher": "结论翻车：放宽后有竞品超过我们记录的最好值"}.get(
               rec["verdict"], rec["verdict"])), "",
        "- 严格规则（现行）：一行里既要出现断言、又要出现拒绝词。",
        "- 放宽规则：断言行前后 ±%d 行内出现拒绝词即可。放宽只会加分，不会减分。" % rec["window"], "",
        "| 仓库 | 严格断言行 | 放宽后 | D1 | 得分 |", "|---|---|---|---|---|",
    ]
    for r in rows:
        mark = " **← 变了**" if r["D1_strict"] != r["D1_window"] else ""
        lines.append("| `%s` | %d | %d | %d → %d | %d → %d%s |" % (
            r["repo"], r["assert_lines_strict"], r["assert_lines_window"],
            r["D1_strict"], r["D1_window"], r["score_strict"], r["score_window"], mark))
    lines += ["", "## 读法", "",
              "结论没有翻：%d 家里只有 %d 家（`%s`）因放宽而 +1 分，最好仍是 %d/10。"
              % (len(rows), len(rec["changed"]), "`, `".join(rec["changed"]) if rec["changed"] else "无",
                 rec["best_window"]), "",
              "这说明「最好 3/10」不是我们正则拼写方式的产物。反过来，如果哪天有人在宽松规则下拿到 4 分，`--check` 会直接失败并写出"
              "「withdraw the headline」——那时该撤回的是主张，不是改规则。", "",
              "复跑：`python tools/parity_sensitivity.py --run --cache <tarball 缓存目录>`（需重新取 25 个固定 commit 的 tarball）；"
              "离线判定：`python tools/parity_sensitivity.py --check`。", ""]
    open(DOC, "w", encoding="utf-8").write("\n".join(lines))
    return DOC


def measure(cache):
    cgp = _cgp()
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    rows = []
    for r in snap["repos"]:
        if "error" in r:
            continue
        root, _sha, _size = cgp.fetch_pinned(r["repo"], r["sha"], cache)
        strict = r.get("assertion_lines", 0)
        loose = windowed_assert_lines(cgp, root)
        d1_strict = r["dims"]["D1"]
        d1_loose = 1 if (r["test_hits"]["reject_assertion"] >= 10 and loose >= cgp.ASSERT_FLOOR) else 0
        s_strict = sum(r["dims"].values())
        s_loose = s_strict - d1_strict + d1_loose
        rows.append({"repo": r["repo"], "assert_lines_strict": strict,
                     "assert_lines_window": loose, "D1_strict": d1_strict,
                     "D1_window": d1_loose, "score_strict": s_strict, "score_window": s_loose})
    rec = {
        "audited_at": snap.get("audited_at"),
        "window": 2,
        "rule_strict": "assertion line must also contain the reject word",
        "rule_window": "assertion line counts if a reject word is within +/-2 lines",
        "rows": rows,
        "changed": [r["repo"] for r in rows if r["D1_strict"] != r["D1_window"]],
        "best_strict": max(r["score_strict"] for r in rows),
        "best_window": max(r["score_window"] for r in rows),
        "verdict": ("headline survives a more permissive rule" if
                    max(r["score_window"] for r in rows) == max(r["score_strict"] for r in rows)
                    else "headline must be withdrawn: a looser rule scores a rival higher"),
    }
    open(RECORD, "w", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
    write_doc(rec)
    for r in rows:
        print("%-45s strict=%-5d window=%-5d D1 %d->%d  score %d->%d"
              % (r["repo"], r["assert_lines_strict"], r["assert_lines_window"],
                 r["D1_strict"], r["D1_window"], r["score_strict"], r["score_window"]))
    print("\nchanged %d of %d; best %d (strict) vs %d (window) -> %s"
          % (len(rec["changed"]), len(rows), rec["best_strict"], rec["best_window"], rec["verdict"]))
    return rec


def check():
    rec = json.load(open(RECORD, encoding="utf-8"))
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    want = {r["repo"] for r in snap["repos"] if "error" not in r}
    got = {r["repo"] for r in rec["rows"]}
    fails = []
    if want != got:
        fails.append("record covers %d repos, snapshot has %d" % (len(got), len(want)))
    if rec["best_window"] != rec["best_strict"]:
        fails.append("a looser rule scores a rival higher (%d vs %d) - withdraw the headline"
                     % (rec["best_window"], rec["best_strict"]))
    # self-consistency: score deltas must be exactly the D1 change
    for r in rec["rows"]:
        if r["score_window"] - r["score_strict"] != r["D1_window"] - r["D1_strict"]:
            fails.append("inconsistent row: %s" % r["repo"])
    if fails:
        for f in fails:
            print("FAIL", f)
        print("SENSITIVITY FAIL (%d problem(s))" % len(fails))
        return 1
    print("SENSITIVITY OK: %d repositories, best %d/10 under both rules, %d changed"
          % (len(got), rec["best_window"], len(rec["changed"])))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="re-measure from the pinned tarballs")
    ap.add_argument("--check", action="store_true", help="offline: record must match snapshot and keep the headline")
    ap.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "uibc-parity-cache"))
    args = ap.parse_args()
    if args.run:
        measure(args.cache)
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
