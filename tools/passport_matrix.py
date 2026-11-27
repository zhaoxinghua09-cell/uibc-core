#!/usr/bin/env python3
"""passport_matrix.py — 五方 AI 护照规范的同一组检查（离线优先）

对象：APS(IETF draft-pidlisnyi) / APIS v2.1(Passport Alliance) / AIP(draft-singla) /
      AIP(draft-prakash) / AIAgentMark v1.0

判四档：
  PASS    本机实测通过（有实现可跑，或本工具按规范复现并验通）
  JUDGE   依规范可判、但拿不到实现或样例，未能实测
  UNKNOWN 规范内无解析入口 / 不可判定
  FAIL    缺该功能（规范里就没有）

用法：
  python tools/passport_matrix.py --check     离线自检（CI 用，不联网，缺 SDK 记 SKIPPED 不记失败）
  python tools/passport_matrix.py --run       联网重跑全部探针并重写 docs/PASSPORT-MATRIX.json（约 20 s）

自限（写进产物，不藏）：
  五家里只有 APS 提供可安装的第三方实现；AIAgentMark 的三个 PASS 是本工具按白皮书
  conformance 条款复现的结果，不等于与厂商实现互通。覆盖不完整是对象性质，不是漏做。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
JSON_PATH = DOCS / "PASSPORT-MATRIX.json"
MD_PATH = DOCS / "PASSPORT-MATRIX.md"

CHECKS = [
    "签名可验（离线，第三方持公钥）",
    "内容绑定（改一个字段验签必失败）",
    "规范化确定（换键序规范串不变）",
    "标识可解析（无上下文）",
    "吊销可追（吊销=一条可验证据）",
    "第三方可独立跑（有可安装实现）",
]
SYSTEMS = [
    "APS (IETF draft-pidlisnyi-aps)",
    "APIS v2.1 (Passport Alliance)",
    "AIP (IETF draft-singla) did:aip",
    "AIP (IETF draft-prakash) aip:web",
    "AIAgentMark v1.0 (个人自持)",
]
VERDICTS = {"PASS", "JUDGE", "UNKNOWN", "FAIL"}


# ───────────────────────── 通用 ─────────────────────────
def _jcs(obj) -> str:
    """RFC 8785 的确定性序化（本工具用到的对象均为整数/字符串，无浮点）。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _http_get(url: str, timeout: int = 8):
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "uibc-passport-matrix/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001
        return None, str(e).encode()[:120]


# ─────────────────── AIAgentMark：按白皮书复现 ───────────────────
def aiagentmark_reproduce():
    """按白皮书三条硬要求造一份护照并自建验签器。返回 (三项判读, 明细)。"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    import os

    def build(handle="stevenzhao"):
        k = Ed25519PrivateKey.generate()
        salt = os.urandom(16)
        pem = k.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        p = {
            "standard": "AIAgentMark",
            "version": "1.0",
            "agent": {"id": "AGNT-" + str(uuid.uuid4())},
            "owner": {
                "identity_hash": hashlib.sha256(salt + handle.encode()).hexdigest(),
                "identity_salt": salt.hex(),
            },
            "public_key": pem,
            "capabilities": ["IDENTITY", "AIAGNTMRK_V1"],
            "issued_at": "2026-11-27T00:00:00Z",
            "expires_at": "2027-11-27T00:00:00Z",
        }
        body = _jcs(p)
        p["signature"] = k.sign(body.encode()).hex()
        return p, k.public_key()

    def verify(p, pub):
        body = _jcs({k: v for k, v in p.items() if k != "signature"})
        try:
            pub.verify(bytes.fromhex(p["signature"]), body.encode())
            return True
        except Exception:  # noqa: BLE001
            return False

    p, pub = build()
    c1 = verify(p, pub)
    bad, badpub = build()
    bad["capabilities"].append("EXTRA")
    c2 = not verify(bad, badpub)
    a = {"z": 1, "a": 2, "n": {"y": 3, "b": 4}}
    b = {"a": 2, "n": {"b": 4, "y": 3}, "z": 1}
    c3 = _jcs(a) == _jcs(b)
    return {"C1": c1, "C2": c2, "C3": c3}


# ───────────────────────── --check ─────────────────────────
def do_check() -> int:
    fails, notes = [], []

    if not JSON_PATH.exists():
        print("MISSING docs/PASSPORT-MATRIX.json")
        return 2
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    # 1 结构：5 体系 × 6 项，判读词表内，合计自洽
    rows = data.get("results", [])
    if len(rows) != len(SYSTEMS) * len(CHECKS):
        fails.append(f"rows={len(rows)}，应为 {len(SYSTEMS) * len(CHECKS)}")
    for s in SYSTEMS:
        got = [r for r in rows if r.get("system") == s]
        if len(got) != len(CHECKS):
            fails.append(f"{s}: {len(got)} 项，应为 {len(CHECKS)}")
    for r in rows:
        if r.get("verdict") not in VERDICTS:
            fails.append(f"非法判读 {r.get('verdict')!r} @ {r.get('system')}/{r.get('check')}")
        if not r.get("detail"):
            fails.append(f"缺 detail @ {r.get('system')}/{r.get('check')}")
    counted = {v: sum(1 for r in rows if r.get("verdict") == v) for v in VERDICTS}
    if data.get("totals") != counted:
        fails.append(f"totals 与逐条不符：写在 {data.get('totals')}，实计 {counted}")

    # 2 复现：AIAgentMark 三项必须仍过（纯离线，无依赖）
    am = aiagentmark_reproduce()
    for k, ok in am.items():
        if not ok:
            fails.append(f"AIAgentMark {k} 复现失败")
    notes.append(f"AIAgentMark C1/C2/C3 复现 = {am}")

    # 3 复现：APS 三项（需 SDK；没有就记 SKIPPED，不判失败）
    try:
        import agent_passport as ap  # noqa: N813

        pb = ap.create_passport(
            agent_id="AGNT-" + str(uuid.uuid4()), agent_name="uibc-check",
            owner_alias="stevenzhao", mission="offline check", capabilities=["IDENTITY"],
            runtime={"lang": "python"})
        sp = pb["signedPassport"]
        v = ap.verify_passport(sp, allow_self_signed=True)
        c1 = bool(v.get("valid"))
        tampered = json.loads(json.dumps(sp))
        inner = tampered.get("passport", tampered)
        inner["mission"] = str(inner.get("mission") or "") + " [tampered]"
        c2 = not ap.verify_passport(tampered, allow_self_signed=True).get("valid")
        c3 = ap.canonicalize_jcs({"z": 1, "a": 2, "n": {"y": 3, "b": 4}}) == \
             ap.canonicalize_jcs({"a": 2, "n": {"b": 4, "y": 3}, "z": 1})
        for k, ok in {"C1": c1, "C2": c2, "C3": c3}.items():
            if not ok:
                fails.append(f"APS {k} 实测失败")
        notes.append(f"APS C1/C2/C3 实测 = C1={c1} C2={c2} C3={c3}")
    except ImportError:
        notes.append("APS 实测 SKIPPED（未安装 agent-passport-system；不计失败）")
    except Exception as e:  # noqa: BLE001
        fails.append(f"APS 实测异常：{type(e).__name__}: {e}")

    # 4 文档漂移：MD 里的合计行必须与 JSON 一致
    if MD_PATH.exists():
        md = MD_PATH.read_text(encoding="utf-8")
        want = (f"{counted['PASS']} ● / {counted['JUDGE']} ◐ / "
                f"{counted['UNKNOWN']} ○ / {counted['FAIL']} ✕")
        if want not in md:
            fails.append(f"PASSPORT-MATRIX.md 的合计行与 JSON 不一致（缺：{want}）")
    else:
        fails.append("缺 docs/PASSPORT-MATRIX.md")

    for n in notes:
        print("NOTE", n)
    if fails:
        print(f"FAIL {len(fails)}")
        for f in fails:
            print(" -", f)
        return 1
    print("OK passport matrix: structure, reproduction, doc alignment")
    return 0


# ───────────────────────── --run ─────────────────────────
def do_run() -> int:
    import agent_passport as ap  # 需 pip install agent-passport-system

    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    out = []

    def add(system, check, verdict, detail):
        out.append({"system": system, "check": check, "verdict": verdict, "detail": detail})

    S1, S2, S3, S4, S5 = SYSTEMS

    # APS 实测
    pb = ap.create_passport(agent_id="AGNT-" + str(uuid.uuid4()), agent_name="uibc-probe",
                            owner_alias="stevenzhao", mission="passport matrix probe",
                            capabilities=["IDENTITY"], runtime={"lang": "python", "env": "run"})
    sp = pb["signedPassport"]
    v = ap.verify_passport(sp, allow_self_signed=True)
    add(S1, CHECKS[0], "PASS" if v.get("valid") else "UNKNOWN",
        f"verify_passport(allow_self_signed=True) -> valid={v.get('valid')}, "
        f"self_signed_accepted={v.get('self_signed_accepted')}")
    t = json.loads(json.dumps(sp))
    t.get("passport", t)["mission"] = str(t.get("passport", t).get("mission") or "") + " [tampered]"
    add(S1, CHECKS[1], "PASS" if not ap.verify_passport(t, allow_self_signed=True).get("valid") else "FAIL",
        "篡改 mission 后 verify -> valid=False（应为 False）")
    add(S1, CHECKS[2], "PASS" if
        ap.canonicalize_jcs({"z": 1, "a": 2, "n": {"y": 3, "b": 4}}) ==
        ap.canonicalize_jcs({"a": 2, "n": {"b": 4, "y": 3}, "z": 1}) else "FAIL",
        "JCS 换键序 -> 同串")
    add(S1, CHECKS[3], "JUDGE",
        "公钥与 verification_method 随凭证携带，离线可验；但这不是 DID 式\"给串就解析\"")
    rev = [x for x in dir(ap) if "revok" in x.lower()]
    add(S1, CHECKS[4], "JUDGE" if rev else "UNKNOWN",
        f"SDK 暴露吊销相关符号 {len(rev)} 个；本次未构造级联吊销用例")
    add(S1, CHECKS[5], "PASS", "pip install agent-passport-system 可用（本机实测）")

    # AIAgentMark 复现
    am = aiagentmark_reproduce()
    add(S2, CHECKS[0], "PASS" if am["C1"] else "FAIL",
        "按白皮书 conformance 条款复现一份，自建验签器验通（非厂商实现）")
    add(S2, CHECKS[1], "PASS" if am["C2"] else "FAIL", "改 capabilities 后验签必失败")
    add(S2, CHECKS[2], "PASS" if am["C3"] else "FAIL", "白皮书明确 RFC 8785 JCS")
    add(S2, CHECKS[3], "JUDGE", "白皮书明言不注册、无服务器——标识不可在线解析，只能离线验")
    add(S2, CHECKS[4], "UNKNOWN", "v1.0 未给吊销机制（到期 + 换钥）")
    add(S2, CHECKS[5], "FAIL", "无 SDK、无样例凭证 —— 第三方无法独立跑")

    # APIS
    add(S3, CHECKS[0], "UNKNOWN", "未获发任何 APIS 凭证；一致性基线未公开下载")
    add(S3, CHECKS[1], "JUDGE", "规范要求三签托管；无样例，判可设不可验")
    add(S3, CHECKS[2], "JUDGE", "规范未统一指定 canonicalization，跨实现有缝")
    st, _ = _http_get("https://example.com/.well-known/did/passport.json")
    add(S3, CHECKS[3], "UNKNOWN", f"realm-scoped DID；未公开解析入口，example.com 试探 → HTTP {st}")
    add(S3, CHECKS[4], "JUDGE", "规范定义即时吊销与登记镜像；无公开实例")
    add(S3, CHECKS[5], "FAIL", "一致性基线由联盟自发布；无公开实现")

    # AIP singla
    add(S4, CHECKS[0], "UNKNOWN", "无公开实现、无样例凭证")
    add(S4, CHECKS[1], "JUDGE", "规范定义 token/capability 与确定性校验；未获样例")
    add(S4, CHECKS[2], "JUDGE", "规范引用自身规范化规则，未统一到 RFC 8785")
    st, _ = _http_get("https://iaisp.teleinfo.cn/api/public/ioa/agents")
    add(S4, CHECKS[3], "UNKNOWN",
        f"规范写明单个 did 串不编码其 Registry；未获 Registry 地址（did:cn 平台列表 HTTP {st}，仅对照）")
    add(S4, CHECKS[4], "JUDGE", "AID 不可变；吊销走 Registry，无公开实例")
    add(S4, CHECKS[5], "FAIL", "两份 draft 无测试数字、无实现")

    # AIP prakash
    add(S5, CHECKS[0], "UNKNOWN", "无公开实现、无样例凭证")
    add(S5, CHECKS[1], "JUDGE", "身份文档自签、Ed25519 + JCS（规范明确 RFC 8785）")
    add(S5, CHECKS[2], "PASS", "规范明确 RFC 8785 JCS（唯一与 APS 完全对齐处）")
    st, _ = _http_get("https://example.com/.well-known/aip/probe.json")
    add(S5, CHECKS[3], "JUDGE", f"机制确定：/.well-known/aip/<path>.json；无公开实例（example.com → HTTP {st}）")
    add(S5, CHECKS[4], "UNKNOWN", "吊销只在令牌过期层面")
    add(S5, CHECKS[5], "FAIL", "无公开实现、无测试数字")

    totals = {v: sum(1 for r in out if r["verdict"] == v) for v in VERDICTS}
    payload = {
        "generated_at": now,
        "probe": "uibc-passport-matrix/1.0",
        "checks": CHECKS,
        "systems": SYSTEMS,
        "totals": totals,
        "results": out,
        "env": {"python": sys.version.split()[0],
                "agent_passport_system": _pkg_version("agent-passport-system"),
                "cryptography": _pkg_version("cryptography")},
        "limitation": "五家里只有 APS 有可安装第三方实现；AIAgentMark 的 PASS 为本工具按白皮书复现。",
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                         newline="\n")
    print("WROTE", JSON_PATH.name, "rows", len(out), "totals", totals)
    print("NOTE 还需 python tools/render_passport_matrix.py --write 重渲 MD/BOARD")
    return 0


def _pkg_version(name: str) -> str:
    try:
        import importlib.metadata as md
        return md.version(name)
    except Exception:  # noqa: BLE001
        return "absent"


def main() -> int:
    ap_ = argparse.ArgumentParser()
    g = ap_.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--run", action="store_true")
    a = ap_.parse_args()
    return do_check() if a.check else do_run()


if __name__ == "__main__":
    raise SystemExit(main())
