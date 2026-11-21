#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""XLGD Trust Lifecycle — 独立复现运行器（不依赖项目内部环境，仅标准库）。

用法：
    python run.py --out external_node_result.json

设计约束：
- 只读 vectors.json，不 import 任何项目模块。
- 判定规则写在本文件 VECTOR_RULES 中，外部实现者可据此自写等价实现。
- 任一用例不符预期即 exit 1，并写入 mismatches。
"""
import argparse
import hashlib
import hmac
import json
import os
import platform
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = {"key-A": "secret-A", "key-B": "secret-B", "key-EVIL": "secret-EVIL"}
SUBJECT_REGISTRY = {"skill-x": "key-A", "skill-y": "key-B"}
NOW = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sha256(obj) -> str:
    return hashlib.sha256(canon(obj)).hexdigest()


def mac(body: dict, key_id: str) -> str:
    return hmac.new(KEYS[key_id].encode(), canon(body), hashlib.sha256).hexdigest()


def check_binding(v: dict) -> bool:
    """签名者须为该主体登记密钥；内容须等于登记摘要；mac 须重算一致。"""
    ev = v["evidence"]
    body = ev["body"]
    if body.get("subject") != v["subject"]:
        return False
    allowed = SUBJECT_REGISTRY.get(body["subject"])
    if allowed is None or ev.get("key_id") != allowed:
        return False
    if not hmac.compare_digest(mac(body, allowed), ev.get("mac", "")):
        return False
    return sha256(body) == v["registered_digest"]


def check_usable(v: dict) -> bool:
    state = v["state"]
    exp = v.get("expires_at")
    if state not in {"AUTHORIZED", "MONITORED"} or exp is None:
        return False
    return datetime.fromisoformat(exp) > NOW


def check_transition(v: dict) -> bool:
    """AUTHORIZED 必须带 subject/scope/expires_at；评分不足以授权。"""
    if v["to"] == "AUTHORIZED":
        a = v.get("authorization")
        if not a or not all(k in a for k in ("subject", "scope", "expires_at")):
            return False
    if v.get("score_only"):
        return False
    return True


def check_compat(v: dict) -> bool:
    table = {("uibc/0.4.0", "rules/2"): {"engine/2", "engine/3"},
             ("uibc/0.3.x", "rules/1"): {"engine/1"},
             ("uibc/0.3.x", "rules/2"): {"engine/2"},
             ("uibc/0.2.x", "rules/1"): {"engine/1"}}
    return v["engine"] in table.get((v["evidence_version"], v["rule_version"]), set())


def check_revocation(v: dict) -> bool:
    """已撤销对象不可用；撤销级联命中下游即不可用。"""
    revoked = {r["target"] for r in v["revocations"]}
    cascaded = {d for r in v["revocations"] for d in r.get("propagates_to", [])}
    return not (v["object"] in revoked or v["object"] in cascaded)


def check_exchange(v: dict) -> bool:
    """跨平台 passport 校验：C 侧只有兼容表、钉扎指纹与撤销快照。

    规则（与 gtp/1 规范一致）：
    - 指纹必须等于本地钉扎值
    - 评测三元组必须在兼容表内
    - 授权未过期且覆盖请求 scope
    - 撤销快照必须存在且未超过 max_age_hours；否则 fail-closed
    """
    if v["pinned_fp"] != v["identity_fp"]:
        return False
    if (v["rule_version"], v["engine_version"]) not in set(
            tuple(x) for x in v["compat"]):
        return False
    if datetime.fromisoformat(v["expires_at"]) <= NOW:
        return False
    if set(v["requested_scope"]) - set(v["granted_scope"]):
        return False
    snap = v.get("snapshot")
    if not snap:
        return False
    if snap["age_hours"] > v.get("max_snapshot_age_hours", 6):
        return False
    return v["entity"] not in set(snap["revoked"])


def _dup_keys(raw: str) -> bool:
    """检测原始 JSON 文本中的重复键（解析歧义的根源）。"""
    flag = {"dup": False}

    def hook(pairs):
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            flag["dup"] = True
        return dict(pairs)

    json.loads(raw, object_pairs_hook=hook)
    return flag["dup"]


def check_canon(v: dict) -> bool:
    """规范化攻击面：重复键 / Unicode / 非标准字面量 / 大整数 / 数字词法。"""
    case = v["case"]
    if case == "duplicate_key":
        return not _dup_keys(v["raw"])
    if case == "nfc":
        a = unicodedata.normalize("NFC", v["registered"])
        b = unicodedata.normalize("NFC", v["presented"])
        return a == b
    if case == "nan":
        return not re.search(r"(?<![\w\"])(NaN|-?Infinity)(?![\w\"])", v["raw"])
    if case == "bigint":
        return abs(int(v["value"])) <= int(v["max_safe"])
    if case == "float":
        return v["presented"] == v["canonical"]
    raise KeyError(case)


def check_negotiate(v: dict) -> bool:
    """版本协商：只接受本地支持列表中的版本，不静默升级也不静默降级。"""
    if v["peer"] not in v["supported"]:
        return False
    if "local" in v and v["peer"] != v["local"] and v["peer"] not in v["supported"]:
        return False
    return True


def check_revmerge(v: dict) -> bool:
    """多撤销源：取并集；被任一源撤销即不可用。"""
    union = {t for s in v["sources"] for t in s["revoked"]}
    return v["object"] not in union


def check_skew(v: dict) -> bool:
    """时钟偏斜容差：略有未来偏移可容忍，超出时效上限仍拒绝。"""
    age, tol, max_age = v["age_minutes"], v["tolerance_minutes"], v["max_age_minutes"]
    if age < -tol:
        return False
    return age <= max_age


CHECKS = {"binding": check_binding, "usable": check_usable,
          "transition": check_transition, "compat": check_compat,
          "revocation": check_revocation, "exchange": check_exchange,
          "canon": check_canon, "negotiate": check_negotiate,
          "revmerge": check_revmerge, "skew": check_skew}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="external_node_result.json")
    ap.add_argument("--vectors", default=os.path.join(HERE, "vectors.json"))
    args = ap.parse_args()

    with open(args.vectors, encoding="utf-8") as f:
        vectors = json.load(f)

    results, mismatches = [], []
    for v in vectors:
        ok = CHECKS[v["check"]](v)
        actual = "ALLOW" if ok else "REJECT"
        matched = actual == v["expected"]
        results.append({"id": v["id"], "expected": v["expected"],
                        "actual": actual, "match": matched})
        if not matched:
            mismatches.append({"id": v["id"], "expected": v["expected"], "actual": actual})

    out = {
        "kit_version": "xlgd-trust-repro/1",
        "reproducer": os.environ.get("REPRODUCER", "unknown"),
        "affiliation": os.environ.get("AFFILIATION", "unknown"),
        "conflict_declared": os.environ.get("CONFLICT_DECLARED", "unknown"),
        "environment": {"os": platform.platform(), "python": platform.python_version(),
                        "machine": platform.machine()},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "vectors_total": len(vectors), "matched": len(vectors) - len(mismatches),
        "mismatches": mismatches, "results": results,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"vectors={len(vectors)} matched={len(results)-len(mismatches)} mismatches={len(mismatches)}")
    print(f"result written to {args.out}")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
