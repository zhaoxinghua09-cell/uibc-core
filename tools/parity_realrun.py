"""Real runs: we installed two of the audited repositories and ran *their own*
test suites, and recorded what came back.

Why this is separate from the parity table: the table measures "does the
repository carry mutation evidence an outsider can re-run". A green test suite
says the repository's build is healthy - it says nothing about bit-level or
address-level mutation. So a real run may never move a score, and this tool
fails if a record claims otherwise.

    python tools/parity_realrun.py --run     # (not implemented here: runs were
                                             #  performed by hand, see the record)
    python tools/parity_realrun.py --check   # offline: record is internally
                                             #  consistent and consistent with
                                             #  the pinned snapshot

The record is `docs/competitor-realrun.json`; the page is generated from it, so
there is exactly one place a number can be typed.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(HERE, "docs", "competitor-parity.json")
RECORD = os.path.join(HERE, "docs", "competitor-realrun.json")
PAGE = os.path.join(HERE, "docs", "COMPETITOR-REALRUN.md")


def load():
    rec = json.load(open(RECORD, encoding="utf-8"))
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    return rec, snap


def render(rec):
    lines = [
        "# 真装真跑：两家竞品的测试套件跑出了什么（每次重写本页）",
        "",
        "审计日 %s。主机 %s。" % (rec["audited_at"], rec["host"]),
        "",
        "**这不是加分项，也不是减分项。** %s" % rec["what_this_is"],
        "",
        "| 仓库 | 固定 commit | 用例 | 过 | 红 | 跳过 | 耗时 s | 退出码 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rec["records"]:
        lines.append("| `%s` | `%s` | %d | %d | %d | %d | %.2f | %d |" % (
            r["repo"], r["sha"][:12], r["tests"], r["passed"], r["failed"],
            r["skipped"], r["seconds"], r["exit_code"]))
    for r in rec["records"]:
        lines += ["", "## `%s`" % r["repo"], "",
                  "- 安装：%s" % r["install"],
                  "- 套件：`%s` → %d 文件 / %d 用例 / %d 红 / %d 跳过 / %.2f s / exit %d" % (
                      r["suite"], r["files"], r["tests"], r["failed"], r["skipped"],
                      r["seconds"], r["exit_code"])]
        if r.get("as_written_failed"):
            lines.append("- 按原样跑不动的部分：%s" % r["as_written_failed"])
        for f in r.get("failures", []):
            lines.append("- 红的那条：`%s` —— %s 读法：%s" % (f["test"], f["kind"], f["read_as"]))
        if r.get("extra_probe"):
            p = r["extra_probe"]
            lines.append("- 额外探针：%s → exit %d。%s 读法：%s" % (
                p["name"], p["exit_code"], p["cause"], p["read_as"]))
        lines.append("- 结论：%s" % r["verdict"])
    lines += ["", "## 为什么这些数字不进表", "",
              "%s" % rec["score_impact"]["why"],
              "", "改分条数：**%d**。" % rec["score_impact"]["changed_scores"], "",
              "复跑：`python tools/parity_realrun.py --check`（离线比对记录与快照）。真跑本身是可复现的人工步骤，"
              "命令与踩到的坑都写在记录里，不假装是一条命令能复现的流水线。", ""]
    return "\n".join(lines)


def check():
    rec, snap = load()
    fails = []
    by_repo = {r["repo"]: r for r in snap["repos"] if "error" not in r}
    if not rec["records"]:
        fails.append("the record holds no real runs")
    for r in rec["records"]:
        s = by_repo.get(r["repo"])
        if not s:
            fails.append("%s is not in the pinned snapshot" % r["repo"])
            continue
        if s["sha"] != r["sha"]:
            fails.append("%s runs at %s but the table pins %s" % (r["repo"], r["sha"][:12], s["sha"][:12]))
        if r["passed"] + r["failed"] + r["skipped"] != r["tests"]:
            fails.append("%s counts do not add up (%d+%d+%d != %d)" % (
                r["repo"], r["passed"], r["failed"], r["skipped"], r["tests"]))
        if (r["exit_code"] == 0) != (r["failed"] == 0):
            fails.append("%s exit code disagrees with its failure count" % r["repo"])
        if r.get("affects_score"):
            fails.append("%s claims to affect the score - a real run never does" % r["repo"])
        if not r.get("verdict"):
            fails.append("%s has no verdict, so a reader cannot tell what the number means" % r["repo"])
    if rec["score_impact"]["changed_scores"] != 0:
        fails.append("score_impact says %d scores changed" % rec["score_impact"]["changed_scores"])
    page = open(PAGE, encoding="utf-8").read() if os.path.exists(PAGE) else ""
    if "不改" not in page and "不是加分项" not in page:
        fails.append("page does not say the real runs leave the table alone")
    for r in rec["records"]:
        if "`%s`" % r["repo"] not in page:
            fails.append("page does not list %s" % r["repo"])
    if fails:
        for f in fails[:6]:
            print("FAIL", f)
        print("\nREALRUN FAIL (%d problem(s))" % len(fails))
        return 1
    tot = sum(r["tests"] for r in rec["records"])
    red = sum(r["failed"] for r in rec["records"])
    print("REALRUN OK: %d repositories installed and run for real, %d tests, %d red, 0 score change"
          % (len(rec["records"]), tot, red))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="runs are performed by hand; see the record")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write-page", action="store_true")
    args = ap.parse_args()
    if args.write_page:
        rec, _ = load()
        with open(PAGE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(rec))
        print("written", PAGE)
        return 0
    if args.run:
        print("real runs are manual (npm/pnpm install + their own test script); "
              "record what came back in docs/competitor-realrun.json")
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
