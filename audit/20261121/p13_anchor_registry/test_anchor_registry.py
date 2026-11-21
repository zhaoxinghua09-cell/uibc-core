# -*- coding: utf-8 -*-
"""P1-3 测试：统一 anchor registry 的校验与展示口径。

正向：成分齐全且验证通过的记录 → 允许 anchored。
负向：Rekor inclusion 未验证 / RFC3161 静默失败 / proof 摘要不符 / 类型错误。
边界：OTS pending 必须只能声称 timestamp_pending，不能是 bitcoin_anchored。
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from anchor_registry import compute_claim, validate_record, validate_registry  # noqa

REG = json.load(open(os.path.join(HERE, "sample_registry.json"), encoding="utf-8"))
REPO = r"C:\Users\Administrator\AppData\Local\Temp\xlgd_audit\uibc-core"

cases = []


def case(name, rec, expect_codes, expect_claim=None):
    cases.append((name, rec, expect_codes, expect_claim))


good_rekor = {
    "anchor_id": "good-rekor", "type": "rekor", "artifact_digest": "a" * 64,
    "proof": {"file": "x", "sha256": "b" * 64},
    "components": {"entry_signature": True, "checkpoint_signature": True, "inclusion_proof": True},
    "verification": {"verified": True, "verifier": "rekor-cli", "verifier_version": "1.0",
                     "verified_at": "2026-11-19"},
}
case("正向 rekor 全验证", good_rekor, [], "anchored")

bad_rekor = copy.deepcopy(good_rekor)
bad_rekor["components"]["inclusion_proof"] = False
bad_rekor["verification"]["verified"] = False
bad_rekor["verification"]["reason"] = "inclusion proof does not verify"
case("负向 rekor inclusion 未验证", bad_rekor, [], "failed")

silent = copy.deepcopy(good_rekor)
silent["verification"] = {"verified": False, "verifier": "x", "verifier_version": "1",
                          "verified_at": "2026-11-19", "reason": "   "}
case("负向 验证失败但原因为空（静默失败）", silent, ["E_SILENT_FAIL"], "failed")

no_proof = copy.deepcopy(good_rekor)
no_proof["proof"] = {"file": None, "sha256": None}
case("负向 缺 proof 绑定", no_proof, ["E_PROOF"], None)

bad_type = copy.deepcopy(good_rekor)
bad_type["type"] = "pgp"
case("负向 未知锚型", bad_type, ["E_TYPE"], None)

good_tsa = {
    "anchor_id": "good-tsa", "type": "rfc3161", "artifact_digest": "c" * 64,
    "proof": {"file": "y", "sha256": "d" * 64},
    "components": {"tsa_signature": True, "tsa_chain": True},
    "verification": {"verified": True, "verifier": "openssl ts -verify", "verifier_version": "3.0",
                     "verified_at": "2026-11-19"},
}
case("正向 rfc3161 全验证", good_tsa, [], "anchored")

ots_pending = {
    "anchor_id": "ots-pending", "type": "ots", "artifact_digest": "e" * 64,
    "calendar_status": "pending",
    "proof": {"file": "z", "sha256": "f" * 64},
    "components": {"bitcoin_block_header": None, "merkle_path": None},
    "verification": {"verified": True, "verifier": "ots-verify", "verifier_version": "0.7",
                     "verified_at": "2026-11-19", "reason": "pending"},
}
case("边界 OTS pending 不得声称比特币锚定", ots_pending, [], "timestamp_pending")

ots_anchored = copy.deepcopy(ots_pending)
ots_anchored["calendar_status"] = "confirmed"
ots_anchored["components"] = {"bitcoin_block_header": True, "merkle_path": True}
case("正向 OTS 进入区块", ots_anchored, [], "bitcoin_anchored")

fail = 0
for name, rec, expect_codes, expect_claim in cases:
    v = validate_record(rec)
    codes = sorted({x["code"] for x in v if x["code"] != "E_COMPONENTS_TYPE"})
    claim = compute_claim(rec)["claim"]
    bad = []
    for c in expect_codes:
        if c not in codes:
            bad.append(f"缺少预期违规 {c}（实际 {codes}）")
    if expect_claim and claim != expect_claim:
        bad.append(f"claim 期望 {expect_claim} 实际 {claim}")
    if bad:
        fail += 1
        print(f"FAIL  {name}: " + "; ".join(bad))
    else:
        print(f"pass  {name}  codes={codes} claim={claim}")

# ---- 真实记录：三条都必须被判为"不可声称 anchored" ----
print("\n== 真实 registry 校验 ==")
res = validate_registry(REG)
print(json.dumps({"records": res["records"], "claims": res["claims"], "ok": res["ok"]}, ensure_ascii=False))
real_bad = 0
for rec in REG["records"]:
    claim = compute_claim(rec)["claim"]
    ok = claim in ("failed", "partial", "timestamp_pending", "unanchored")
    print(("pass  " if ok else "FAIL  ") + f"{rec['anchor_id']} claim={claim}")
    if not ok:
        real_bad += 1
if real_bad:
    fail += real_bad

print(f"\nTOTAL {len(cases) + len(REG['records']) - fail} passed / {fail} failed")
sys.exit(0 if fail == 0 else 1)
