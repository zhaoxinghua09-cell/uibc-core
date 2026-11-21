# -*- coding: utf-8 -*-
"""P1-3 整改方案：统一 anchor registry + 严格的展示口径。

三条纪律（对应任务书 4/5 条）：
  * OTS pending calendar 不得显示为 Bitcoin anchored；
  * Rekor inclusion proof 未验证不得显示完整 anchored；
  * entry signature / checkpoint signature / inclusion proof 必须分别记录。

registry 记录的最小字段：
  anchor_id, type(ots|rekor|rfc3161), artifact_digest, created_at, proof{file,sha256},
  components{entry_signature, checkpoint_signature, inclusion_proof},
  verification{verified, verifier, verifier_version, verified_at, reason},
  display_claim（由 compute_claim 生成，禁止手写自由文本）
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

ANCHOR_TYPES = ("ots", "rekor", "rfc3161")
VERTICAL_STATUS = ("anchored", "partial", "pending", "failed", "unanchored")

# 每个锚型必须具备的成分（缺一即不可声称 anchored）
REQUIRED_COMPONENTS = {
    "ots": ("bitcoin_block_header", "merkle_path"),
    "rekor": ("entry_signature", "checkpoint_signature", "inclusion_proof"),
    "rfc3161": ("tsa_signature", "tsa_chain"),
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_record(rec: dict, base_dir: str = None) -> list:
    """返回违规列表，元素为 {code, detail}。空列表 = 合格。"""
    v = []

    def add(code, detail):
        v.append({"code": code, "detail": detail})

    if rec.get("type") not in ANCHOR_TYPES:
        add("E_TYPE", f"未知锚型 {rec.get('type')!r}")

    if not rec.get("artifact_digest") or len(rec["artifact_digest"]) != 64:
        add("E_DIGEST", "artifact_digest 缺失或不是 sha256 hex")

    proof = rec.get("proof") or {}
    if not proof.get("file"):
        add("E_PROOF", "proof.file 缺失")
    else:
        if base_dir and os.path.exists(os.path.join(base_dir, proof["file"])):
            actual = sha256_file(os.path.join(base_dir, proof["file"]))
            if proof.get("sha256") != actual:
                add("E_PROOF_DIGEST", f"proof sha256 不符：记录 {proof.get('sha256')} 实际 {actual}")
        elif not proof.get("sha256"):
            add("E_PROOF", "无法校验 proof 摘要（既无文件也无 sha256）")

    comp = rec.get("components") or {}
    req = REQUIRED_COMPONENTS.get(rec.get("type"), ())
    missing = [c for c in req if c not in comp]
    if missing:
        add("E_COMPONENTS", f"缺成分 {missing}")
    for c in ("entry_signature", "checkpoint_signature", "inclusion_proof"):
        if c in comp and comp[c] not in (True, False, None):
            add("E_COMPONENTS_TYPE", f"{c} 必须是 bool/None，实际 {type(comp[c]).__name__}")

    ver = rec.get("verification") or {}
    if "verified" not in ver or not isinstance(ver["verified"], bool):
        add("E_VERIFICATION", "verification.verified 必须是显式 bool")
    if ver.get("verified") is False:
        reason = (ver.get("reason") or "").strip()
        if not reason:
            add("E_SILENT_FAIL", "验证失败但未给出原因（空括号即静默失败）")
        if not ver.get("verifier"):
            add("E_VERIFIER", "未记录验证者/工具版本")

    # 口径判定
    claim = compute_claim(rec)
    if claim["claim"] == "anchored" and claim["not_supported_by"]:
        add("E_CLAIM", f"声称 anchored 但成分/验证不足：{claim['not_supported_by']}")

    # OTS 特判
    if rec.get("type") == "ots":
        cal = (rec.get("calendar_status") or "").lower()
        if cal in ("pending", "", "unconfirmed") and claim["claim"] == "bitcoin_anchored":
            add("E_OTS_PENDING", "OTS 仍为 pending，不得显示 Bitcoin anchored")

    # Rekor 特判
    if rec.get("type") == "rekor":
        inc = (rec.get("components") or {}).get("inclusion_proof")
        if inc is not True and claim["claim"] in ("anchored", "inclusion_verified"):
            add("E_REKOR_INCLUSION", "inclusion proof 未验证通过，不得显示为完整 anchored")

    return v


def compute_claim(rec: dict) -> dict:
    """由已验证成分推导展示口径，禁止文档手写。"""
    t = rec.get("type")
    comp = rec.get("components") or {}
    ver = rec.get("verification") or {}
    verified = ver.get("verified") is True
    not_supported = []

    if verified and not (rec.get("proof") or {}).get("file"):
        return {"claim": "partial", "not_supported_by": ["proof_binding"],
                "reason": "无 proof 文件绑定，无法复算"}

    if not verified:
        base = "failed" if ver.get("verified") is False else "unanchored"
        return {"claim": base, "not_supported_by": [], "reason": ver.get("reason")}

    if t == "ots":
        cal = (rec.get("calendar_status") or "").lower()
        if cal in ("pending", "", "unconfirmed"):
            return {"claim": "timestamp_pending", "not_supported_by": ["bitcoin_calendar"],
                    "reason": "OTS 时间戳已存在但未进入 Bitcoin 区块"}
        if comp.get("bitcoin_block_header") is True and comp.get("merkle_path") is True:
            return {"claim": "bitcoin_anchored", "not_supported_by": [], "reason": None}
        return {"claim": "partial", "not_supported_by": ["bitcoin_block_header"], "reason": None}

    if t == "rekor":
        ok = comp.get("inclusion_proof") is True
        sig = comp.get("entry_signature") is True
        ck = comp.get("checkpoint_signature") is True
        if ok and sig and ck:
            return {"claim": "anchored", "not_supported_by": [], "reason": None}
        if not ok:
            not_supported.append("inclusion_proof")
        if not sig:
            not_supported.append("entry_signature")
        if not ck:
            not_supported.append("checkpoint_signature")
        return {"claim": "partial", "not_supported_by": not_supported, "reason": None}

    if t == "rfc3161":
        st = comp.get("tsa_signature") is True
        ch = comp.get("tsa_chain") is True
        if st and ch:
            return {"claim": "anchored", "not_supported_by": [], "reason": None}
        not_supported += [k for k, ok in (("tsa_signature", st), ("tsa_chain", ch)) if not ok]
        return {"claim": "partial", "not_supported_by": not_supported, "reason": None}

    return {"claim": "unanchored", "not_supported_by": [f"unknown_type:{t}"], "reason": None}


def validate_registry(reg: dict) -> dict:
    records = reg.get("records", [])
    problems = []
    seen = set()
    for r in records:
        aid = r.get("anchor_id")
        if not aid:
            problems.append({"anchor_id": None, "code": "E_ID", "detail": "缺 anchor_id"})
            continue
        if aid in seen:
            problems.append({"anchor_id": aid, "code": "E_DUP", "detail": "anchor_id 重复"})
        seen.add(aid)
        for p in validate_record(r):
            problems.append({"anchor_id": aid, **p})
    summary = {}
    for r in records:
        c = compute_claim(r)["claim"]
        summary[c] = summary.get(c, 0) + 1
    return {"records": len(records), "problems": problems, "claims": summary,
            "ok": not problems}


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    reg = json.load(open(path, encoding="utf-8"))
    print(json.dumps(validate_registry(reg), ensure_ascii=False, indent=2))
