#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W1 harness: two package versions -> one version-history report + one verdict.

This is the engine behind "a real PCCP change, end to end". It takes the package
for revision N-1 and the package for revision N, verifies each offline, links
them (N supersedes N-1), optionally folds in the gate ledger as a third origin,
and writes:

    tools/out/pccp_case.json        the composed case (records + verdict)
    tools/out/pccp_report.md        the one-page version history a reviewer reads

    python tools/pccp_case.py --prev <dir> --curr <dir> [--phantom <jsonl>]

It does not judge compliance and does not claim the change was authorised - only
that the two states are self-consistent, linked, and that neither can be silently
edited or rolled back without this report showing it.
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from uibc_core.canonical import hash_obj  # noqa: E402
from uibc_core.composition import compose_case  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

OUT = os.path.join(ROOT, "tools", "out")


def pkg_record(path, seq, label):
    rep = verify(path)
    manifest = json.load(open(os.path.join(path, "manifest.json"), encoding="utf-8"))
    payload = {
        "label": label,
        "spec_id": rep.get("spec_id"),
        "checkpoint_head": manifest.get("checkpoint_head") or rep.get("checkpoint_head"),
        "evidence_root": manifest.get("evidence_root"),
        "evidence_count": manifest.get("evidence_count"),
        "agent_version": manifest.get("agent_version"),
        "verify_result": rep.get("result"),
        "trust_level": rep.get("trust_level"),
        "anchored_key_match": rep.get("anchored_key_match"),
    }
    return {
        "origin": label,
        "kind": "uibc_package",
        "subject": manifest.get("agent_id"),
        "at": manifest.get("created_at"),
        "seq": seq,
        "digest": "sha256:" + hash_obj(payload),
        "payload": payload,
        "refs": [],
    }, rep, manifest


def gate_records(path_for_log, subject):
    """Gate decisions, filtered to the case's subject and counted if dropped.

    A ledger that also covers other agents must not be pasted into this case: the
    composition check would (correctly) report K2 subject mismatch, and the honest
    fix is to keep the case single-subject and say how many records were excluded,
    not to merge them and explain the failure away.
    """
    out, excluded = [], 0
    if not path_for_log or not os.path.isfile(path_for_log):
        return out, 0
    for line in open(path_for_log, encoding="utf-8"):
        if not line.strip():
            continue
        e = json.loads(line)
        if subject and e.get("subject") != subject:
            excluded += 1
            continue
        payload = {"decision": e.get("decision"), "rule_id": e.get("rule_id"),
                   "phantom": e.get("phantom"), "request_digest": e.get("request_digest"),
                   "seq": e.get("seq"), "at": e.get("at")}
        out.append({
            "origin": "gate",
            "kind": "gate_decision",
            "subject": e.get("subject"),
            "at": e.get("at"),
            "seq": e.get("seq"),
            "digest": "sha256:" + hash_obj(payload),
            "payload": payload,
            "refs": [],
        })
    return out, excluded


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev", required=True)
    ap.add_argument("--curr", required=True)
    ap.add_argument("--phantom", default=None)
    ap.add_argument("--label-prev", default="rev-N-1")
    ap.add_argument("--label-curr", default="rev-N")
    args = ap.parse_args(argv)

    prev, rep_prev, man_prev = pkg_record(args.prev, 1, args.label_prev)
    curr, rep_curr, man_curr = pkg_record(args.curr, 2, args.label_curr)
    curr["refs"] = [prev["digest"]]
    gate, excluded = gate_records(args.phantom, man_curr.get("agent_id"))
    if gate:
        newest = max(gate, key=lambda r: r.get("seq") or 0)
        newest["refs"] = [curr["digest"]]

    case = compose_case([prev, curr] + gate)
    os.makedirs(OUT, exist_ok=True)
    case_doc = {"subject": man_curr.get("agent_id"), "verdict": case["verdict"],
                "records": 2 + len(gate),
                "excluded_other_subject": excluded,
                "findings": case["findings"], "scope": case["scope"]}
    with open(os.path.join(OUT, "pccp_case.json"), "w", encoding="utf-8") as f:
        json.dump(case_doc, f, ensure_ascii=False, indent=2)

    # the same records in the eQMS contract's input schema, so a QMS vendor's
    # export can be dropped in and re-judged by a third party
    with open(os.path.join(OUT, "pccp_records.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "uibc.eqms-records/1",
                   "subject": man_curr.get("agent_id"),
                   "records": [prev, curr] + gate}, f, ensure_ascii=False, indent=2)

    def row(man, rep, label):
        return "| %s | %s | %s | %s | %s | %s |" % (
            man.get("agent_version") or "-", man.get("created_at") or "-", label,
            (man.get("checkpoint_head") or "-")[:26] + "...",
            rep.get("result"), rep.get("trust_level"))

    lines = [
        "# 版本历史报告（PCCP 变更 N-1 → N）",
        "",
        "生成时间（UTC）：%s" % datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "",
        "## 1. 两个状态的独立验证",
        "",
        "| 版本号 | 创建时间 | 标识 | checkpoint head | 验证结论 | 信任等级 |",
        "|---|---|---|---|---|---|",
        row(man_prev, rep_prev, args.label_prev),
        row(man_curr, rep_curr, args.label_curr),
        "",
        "## 2. 组合裁决（多源一案）",
        "",
        "- 记录数：%d（来源：%s）" % (case_doc["records"],
                                   ", ".join(case["origins"])),
        "- **裁决：%s**" % case["verdict"],
        "- 判据代码：%s" % (", ".join(sorted({f["code"] for f in case["findings"]}))
                            or "无（K1-K8 全部通过）"),
        "",
        "## 3. 这份报告能证明什么",
        "",
        "1. 每个版本的证据根、索引与 checkpoint 在该包内自洽（S4/S5/S7/S8）。",
        "2. 版本 N 明确引用版本 N-1（`refs`），时间线不倒置（K4）。",
        "3. 若有人拿旧包顶替新包，用包外记录的 head 比对即可发现（S9）；"
        "仅靠包内信息无法发现整包回滚。",
        "",
        "## 4. 这份报告不证明什么",
        "",
        "- 不判断变更是否在已授权 PCCP 范围内（属合规判断）。",
        "- 不证明证据内容为真，只证明未被改动。",
        "- 不构成 FDA/公告机构的认可，也不替代 RA 复核。",
        "",
        "## 5. 复核方式（任何人可离线执行）",
        "",
        "```",
        "python -m uibc_core.cli verify <版本包> --expect-head <包外记录的 head>",
        "python tools/compose_demo.py          # K1-K8 的七个场景",
        "```",
    ]
    with open(os.path.join(OUT, "pccp_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("prev=%s(%s)  curr=%s(%s)  composition=%s"
          % (rep_prev["result"], rep_prev.get("trust_level"),
             rep_curr["result"], rep_curr.get("trust_level"), case["verdict"]))
    print("REPORT=" + os.path.join(OUT, "pccp_report.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
