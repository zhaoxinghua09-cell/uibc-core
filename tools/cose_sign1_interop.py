#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SCITT 信封互验：把 uibc-core 的 S6 seal 包进 COSE_Sign1(EdDSA)，再用"只持公钥"的
第三方路径解包验签，并回收原始规范字节做逐字节比对；最后验证篡改必被拒。

为什么这件事重要（2026-11 生态实测）：
  SCITT 架构已成 RFC 9943；Agent 专用 profile（thaha-02 / emirdag-00）都把记录定义为
  COSE_Sign1 载荷。uibc 只给自定义 JSON 包，就会被问"为什么不是 COSE_Sign1 + Receipt"。
  本脚本给出可复跑的最小桥：uibc canonical payload <-> COSE_Sign1 <-> 只持公钥的验签方。

三个必须写进结论的坑（都是实测踩到的）：
  1. pycose 1.1.0 的 verify_signature() 返回 bool，**不抛异常**。不取返回值就会把
     "验签失败"当成"验签通过"——这会直接制造假接受。2026-11-13 的 eco_result.json
     里 COSE 一项的 PASS/FAIL 判定因此不可靠（它只 try/except，没看返回值）。
  2. pycose 1.1.0 + cbor2 的 decode() 期望 list，而本环境 cbor2 把 array 解成 tuple、
     map 解成 frozendict → 抛 "Bytes cannot be decoded as COSE message"。
     绕法：cbor2.loads -> 递归还原为 list/dict -> Sign1Message.from_cose_obj()。
  3. detached 载荷模式下 payload 必须为 None，否则 encode() 抛
     "Detached payload must be None when payload is set"。

用法： python tools/cose_sign1_interop.py [--json out.json]
"""
import argparse
import hashlib
import json
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from uibc_core import signing as us  # noqa: E402

try:
    from cbor2 import CBORTag
except Exception:  # pragma: no cover
    CBORTag = None
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey, )


def ed25519_sign(seed: bytes, msg: bytes) -> bytes:
    """Raw Ed25519 sign with a 32-byte seed, no COSE library in the way."""
    return Ed25519PrivateKey.from_private_bytes(seed).sign(msg)


def ed25519_verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
        return True
    except Exception:
        return False


RESULTS = {"meta": {"generated_at_utc": None, "uibc_core": ROOT, "probe": "scitt-cose-sign1"},
           "tests": []}


def rec(name, ok, detail, extra=None):
    RESULTS["tests"].append({"name": name, "pass": bool(ok), "detail": detail, **(extra or {})})
    print(("[PASS] " if ok else "[FAIL] ") + name + " :: " + detail)


def _thaw(o):
    """cbor2 在本环境把 map 解成 frozendict、把 array 解成 tuple；pycose 只吃
    dict/list。递归还原，不改值语义。"""
    if isinstance(o, (tuple, list)):
        return [_thaw(x) for x in o]
    if hasattr(o, "items") and not isinstance(o, (bytes, str)):
        return {k: _thaw(v) for k, v in o.items()}
    return o


def _decode(cose_bytes, Sign1Message, cbor2):
    return Sign1Message.from_cose_obj(_thaw(cbor2.loads(cose_bytes).value), True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(ROOT, "tools", "out", "cose_sign1_result.json"))
    a = ap.parse_args()

    import cbor2
    from pycose.keys.curves import Ed25519
    from pycose.keys.okp import OKPKey
    from pycose.messages import Sign1Message

    identity = {"agent_id": "scitt-bridge-agent", "owner": "medxpert", "agent_type": "software-agent"}
    manifest = {"evidence_root": hashlib.sha256(b"scitt-bridge-evidence").hexdigest(),
                "type": "seal", "version": "0.3"}

    seed = us.ed_generate_seed()
    pub = us.ed_public_key(seed)
    payload = us.seal_payload(identity, manifest)
    sig_b64, _pub_b64 = us.ed_seal_sign(seed, identity, manifest)

    rec("S0_UIBC_SEAL", us.ed_seal_verify(pub, identity, manifest, sig_b64),
        "uibc S6 seal 先自验（这是要被包进 COSE 的东西）")

    # --- 1) 构造 COSE_Sign1（EdDSA），payload = uibc 规范字节 -------------------
    t0 = time.perf_counter()
    signer = OKPKey(crv=Ed25519, x=pub, d=seed)
    msg = Sign1Message(phdr={1: -8, 4: pub, 3: "application/uibc"}, payload=payload, key=signer)
    cose_bytes = msg.encode()
    sign_ms = (time.perf_counter() - t0) * 1000
    rec("C1_COSE_SIGN", True,
        "COSE_Sign1(alg=-8 EdDSA) 封装完成 envelope=%dB sign=%.2fms" % (len(cose_bytes), sign_ms),
        {"envelope_len": len(cose_bytes), "sign_ms": round(sign_ms, 3), "alg": -8})

    # --- 2) 第三方路径：只有公钥 + bytes --------------------------------------
    try:
        parsed = _decode(cose_bytes, Sign1Message, cbor2)
        rec("C2_DECODE", True, "解包成功（tag=18；已绕过 list/tuple 与 frozendict 差异）")
    except Exception as e:
        rec("C2_DECODE", False, "解包失败: %s" % e)
        traceback.print_exc()
        _dump(a.json)
        return 1

    try:
        parsed.key = OKPKey(crv=Ed25519, x=pub)      # 只给公钥，不给私钥
        t0 = time.perf_counter()
        rv = parsed.verify_signature()
        verify_ms = (time.perf_counter() - t0) * 1000
        if rv is not True:
            raise ValueError("verify_signature 返回 %r（该函数返回布尔值，不抛异常）" % (rv,))
        rec("C3_THIRD_PARTY_VERIFY", True,
            "第三方仅持公钥验签 = True，verify=%.3fms" % verify_ms, {"verify_ms": round(verify_ms, 3)})
    except Exception as e:
        rec("C3_THIRD_PARTY_VERIFY", False, "验签失败: %s" % e)

    recovered = bytes(parsed.payload)
    rec("C4_PAYLOAD_ROUNDTRIP", recovered == payload,
        "COSE 载荷与 uibc 规范字节逐字节一致（%d B）" % len(recovered),
        {"payload_len": len(recovered), "payload_sha256": hashlib.sha256(recovered).hexdigest()})

    # --- 3) 篡改检测：改签名最后一字节，第三方必须得到非 True -------------------
    try:
        bad = bytearray(cose_bytes)
        bad[-1] ^= 0x01
        p2 = _decode(bytes(bad), Sign1Message, cbor2)
        p2.key = OKPKey(crv=Ed25519, x=pub)
        rv2 = p2.verify_signature()
        rec("C5_TAMPER_REJECTED", rv2 is not True,
            "篡改 1 字节后 verify_signature=%r（必须非 True）" % (rv2,))
    except Exception as e:
        rec("C5_TAMPER_REJECTED", True, "篡改后被拒（抛异常）：%s" % type(e).__name__)

    # --- 4) SCITT 风格 statement 可承载 --------------------------------------
    statement = {"iss": "medxpert", "sub": "scitt-bridge-agent",
                 "iat": "2026-11-17T00:00:00Z", "uibc_evidence_root": manifest["evidence_root"]}
    st_bytes = us.seal_payload(statement, {"type": "scitt-statement", "version": "0.3"})
    m2 = Sign1Message(phdr={1: -8, 4: pub}, payload=st_bytes, key=OKPKey(crv=Ed25519, x=pub, d=seed))
    b2 = m2.encode()
    p3 = _decode(b2, Sign1Message, cbor2)
    p3.key = OKPKey(crv=Ed25519, x=pub)
    try:
        if p3.verify_signature() is not True:
            raise ValueError("statement envelope 验签非 True")
        rec("C6_STATEMENT_ENVELOPE", True,
            "SCITT 风格 statement（iss/sub/iat/evidence_root）可封装+离线验签，%dB" % len(b2),
            {"statement_len": len(b2)})
    except Exception as e:
        rec("C6_STATEMENT_ENVELOPE", False, "statement 封装/验签失败: %s" % e)

    # --- 5) alg=-19 (RFC 9864)：规范要求它，主流库还没有它 -------------------
    # noa-00/01 require alg -19 (fully-specified Ed25519) and SHOULD refuse the
    # polymorphic -8. pycose 1.1.0 registers only -8 (EdDSA), so build and verify
    # a -19 envelope by hand: COSE is a thin container and the Sig_structure is
    # three lines. This shows the requirement is MET by our code without
    # pretending the ecosystem supports it.
    try:
        protected = cbor2.dumps({1: -19, 3: "application/uibc", 4: pub})
        sig_structure = cbor2.dumps(["Signature1", protected, b"", payload])
        sig19 = ed25519_sign(seed, sig_structure)
        env19 = cbor2.dumps(CBORTag(18, [protected, {4: pub}, payload, sig19]))
        hdr19 = cbor2.loads(protected)
        ok19 = (ed25519_verify(pub, sig_structure, sig19)
                and hdr19[1] == -19
                and cbor2.loads(env19).value[2] == payload)
        rec("C8_ALG_19_MANUAL", bool(ok19),
            "alg=-19（RFC 9864）信封手工构造 + 只持公钥验签通过，envelope=%dB" % len(env19),
            {"envelope_len": len(env19), "alg": -19})
    except Exception as e:
        rec("C8_ALG_19_MANUAL", False, "alg=-19 构造/验签失败: %s" % e)
        env19 = None

    # The honest half: the reference Python COSE library cannot decode -19 even
    # after you register the attribute, which is exactly why "aligned to -19"
    # is a claim about our code, not about the ecosystem's readiness.
    if env19 is not None:
        try:
            _decode(env19, Sign1Message, cbor2)
            rec("C9_LIB_GAP", False,
                "pycose 竟然解开了 -19：本用例的前提失效，需更新结论")
        except Exception as e:
            rec("C9_LIB_GAP", True,
                "pycose 1.1.0 拒绝 alg=-19（%s）→ -19 仍走在库配套之前：对外只能说"
                "“我们的信封支持 -19”，不能宣称“生态已通用 -19”" % type(e).__name__)

    _dump(a.json)
    n_pass = sum(1 for t in RESULTS["tests"] if t["pass"])
    print("\n=== %d/%d PASS ===" % (n_pass, len(RESULTS["tests"])))
    return 0 if n_pass == len(RESULTS["tests"]) else 1


def _dump(path):
    RESULTS["meta"]["generated_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    RESULTS["summary"] = {"pass": sum(1 for t in RESULTS["tests"] if t["pass"]),
                          "total": len(RESULTS["tests"])}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    print("RESULT_JSON=" + path)


if __name__ == "__main__":
    sys.exit(main())
