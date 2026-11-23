#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一覆盖账本：把分散的披露语义（自方检查 + 字段覆盖 + 已知限制 + 同尺对手）合成一份可 diff 的 JSON。

为什么要有这个文件：
  FIELD-COVERAGE.md 与 KNOWN-LIMITS.md 写得诚实，但它们是散文；散文不能被 diff、不能被 CI 拦。
  这里把它们与 coverage/ 下的 CDP-1 账本合成一份结构化的账本，并让数字全部从源材料解析后重算比对。

用法：
  python tools/build_coverage_ledger.py --build   # 生成 docs/coverage-ledger.json 并校验
  python tools/build_coverage_ledger.py --check   # 只校验已提交的那份（CI 用这个）
退出码：0 = 通过；1 = 校验失败（逐条打印）
"""
import json, os, re, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "coverage-ledger.json")
OWN = os.path.join(ROOT, "coverage", "ledger.uibc-core.json")
FIELD_DOC = os.path.join(ROOT, "docs", "FIELD-COVERAGE.md")
LIMITS_DOC = os.path.join(ROOT, "docs", "KNOWN-LIMITS.md")

STATUSES = {"EXERCISED", "UNTESTED", "EXEMPT", "NOT_PUBLIC"}
PEERS = ["aac", "eqr", "asqav"]


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_field_coverage():
    """数字从文档解析，不写死；缺一个就报错，避免文档改了而账本没跟上。"""
    txt = open(FIELD_DOC, encoding="utf-8").read()
    keys = ("fields probed", "alterations that moved at least one check", "alterations that moved nothing")
    nums = {}
    for k in keys:
        m = re.search(r"\|\s*" + re.escape(k) + r"\s*\|\s*(\d+)\s*\|", txt)
        if m:
            nums[k] = int(m.group(1))
    return {
        "probed": nums.get("fields probed"),
        "moved": nums.get("alterations that moved at least one check"),
        "silent": nums.get("alterations that moved nothing"),
        "source": "docs/FIELD-COVERAGE.md",
    }


def parse_known_limits():
    rows = []
    txt = open(LIMITS_DOC, encoding="utf-8").read()
    for line in txt.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        rows.append({
            "id": f"KL-{cells[0]}",
            "limitation": re.sub(r"^\*\*|\*\*$", "", cells[1]),
            "why": cells[2],
            "disposition": cells[3],
            "source": "docs/KNOWN-LIMITS.md",
        })
    return rows


def build():
    own = _load(OWN)
    peers = {p: _load(os.path.join(ROOT, "coverage", "peers", f"{p}.cdp.json")) for p in PEERS}
    ledger = {
        "schema": "coverage-ledger/1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "subject": own.get("subject", {}),
        "provenance": {
            "checks": "coverage/ledger.uibc-core.json",
            "field_coverage": "docs/FIELD-COVERAGE.md",
            "known_limits": "docs/KNOWN-LIMITS.md",
            "peers": [f"coverage/peers/{p}.cdp.json" for p in PEERS],
        },
        "checks": own.get("entries", []),
        "field_probes": parse_field_coverage(),
        "known_limits": parse_known_limits(),
        "peers": [
            {"name": p, "subject": peers[p].get("subject", {}),
             "entries": peers[p].get("entries", []), "summary": peers[p].get("summary", {})}
            for p in PEERS
        ],
    }
    ledger["summary"] = summarize(ledger)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return ledger


def summarize(ledger):
    checks = ledger["checks"]
    counts = {s: 0 for s in STATUSES}
    for e in checks:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    total = len(checks)
    peer_counts = []
    for p in ledger["peers"]:
        c = {}
        for e in p["entries"]:
            c[e["status"]] = c.get(e["status"], 0) + 1
        peer_counts.append({"name": p["name"], "total": len(p["entries"]), "by_status": c})
    fp = ledger["field_probes"]
    return {
        "checks_total": total,
        "checks_by_status": counts,
        "disclosure_ratio": round(counts.get("EXERCISED", 0) / total, 4) if total else None,
        "distinct_statuses_present": len([k for k, v in counts.items() if v]),
        "field_probes": fp,
        "known_limits": len(ledger["known_limits"]),
        "peers": peer_counts,
        "peer_disclosure": {
            "self": round(counts.get("EXERCISED", 0) / total, 4) if total else None,
            **{pc["name"]: round(pc["by_status"].get("EXERCISED", 0) / pc["total"], 4) if pc["total"] else None
               for pc in peer_counts},
        },
    }


def validate(ledger):
    """五条硬规则。任何一条不满足就返回错误列表，调用方据此退出非 0。"""
    errs = []
    if ledger.get("schema") != "coverage-ledger/1":
        errs.append("schema 应为 coverage-ledger/1")
    ids = set()
    for e in ledger.get("checks", []):
        if e.get("id") in ids:
            errs.append(f"重复 id: {e.get('id')}")
        ids.add(e.get("id"))
        if e.get("status") not in STATUSES:
            errs.append(f"{e.get('id')}: 非法状态 {e.get('status')}")
        if e.get("status") == "UNTESTED" and not (e.get("owner") and e.get("review_by")):
            errs.append(f"{e.get('id')}: UNTESTED 缺 owner 或 review_by")
        if e.get("status") == "EXEMPT" and not e.get("reason"):
            errs.append(f"{e.get('id')}: EXEMPT 缺 reason")
    if not ledger.get("checks"):
        errs.append("checks 为空")
    fp = ledger.get("field_probes", {})
    if None in (fp.get("probed"), fp.get("moved"), fp.get("silent")):
        errs.append(f"field_probes 解析不全: {fp}")
    elif fp["probed"] != fp["moved"] + fp["silent"]:
        errs.append(f"field_probes 不自洽: {fp['probed']} != {fp['moved']}+{fp['silent']}")
    kl = ledger.get("known_limits", [])
    if len(kl) < 8:
        errs.append(f"known_limits 少于 8 条（实际 {len(kl)}）")
    for r in kl:
        if not r.get("disposition"):
            errs.append(f"{r.get('id')}: 缺处置")
    if len(ledger.get("peers", [])) != len(PEERS):
        errs.append("peers 数量不为 3")
    for p in ledger.get("peers", []):
        if not p.get("entries"):
            errs.append(f"peer {p.get('name')} 无条目")
        for e in p.get("entries", []):
            if e.get("status") not in STATUSES:
                errs.append(f"peer {p.get('name')}/{e.get('id')}: 非法状态 {e.get('status')}")
    recomputed = summarize(ledger)
    for k in ("checks_total", "disclosure_ratio", "known_limits"):
        if ledger.get("summary", {}).get(k) != recomputed.get(k):
            errs.append(f"summary.{k} 与重算不一致: {ledger.get('summary', {}).get(k)} vs {recomputed.get(k)}")
    return errs, recomputed


def main():
    if "--build" in sys.argv:
        ledger = build()
    else:
        if not os.path.exists(OUT):
            print("FAIL 找不到 docs/coverage-ledger.json，先跑 --build")
            return 1
        ledger = _load(OUT)
    errs, s = validate(ledger)
    for e in errs:
        print(f"FAIL {e}")
    print(
        "OK cdl checks={t} exercised={ex} untested={un} exempt={x} not_public={np} "
        "disclosure={d} fields={fp}/{fpv} known_limits={kl} peers={pe} peer_disclosure={pd}".format(
            t=s["checks_total"], ex=s["checks_by_status"].get("EXERCISED", 0),
            un=s["checks_by_status"].get("UNTESTED", 0), x=s["checks_by_status"].get("EXEMPT", 0),
            np=s["checks_by_status"].get("NOT_PUBLIC", 0), d=s["disclosure_ratio"],
            fp=s["field_probes"].get("moved"), fpv=s["field_probes"].get("probed"),
            kl=s["known_limits"], pe=len(s["peers"]), pd=s["peer_disclosure"],
        )
    )
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
