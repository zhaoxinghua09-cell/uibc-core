#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""红队套件：外部攻击者视角，不按我们自己的基准出题。

mutation_benchmark.py 的 21 类是"单点改一个字段"，那是我们想到的攻击面。
这里换人出题：路径穿越、绝对路径、符号链接、算法混淆、签名降级、
重复键、NaN、超大文件、重复条目、行尾重排。每一条都写清楚"期望"和
"我们实际拿到什么"，包括我们**没挡住**的那些。

用法： python tools/redteam_suite.py
结果： tools/out/redteam_result.json
"""
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from uibc_core import cli as ucli  # noqa: E402
from uibc_core import signing as us  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

OUT = os.path.join(ROOT, "tools", "out")
SEED = bytes(range(32))


def _a(**kw):
    return type("A", (), kw)()


def build(path, key=None):
    ucli.cmd_init(_a(path=path))
    ucli.cmd_register(_a(path=path, agent_id="rt-agent", owner="rt-owner",
                         agent_type="software-agent", version="1.0.0"))
    src = os.path.join(os.path.dirname(path), "ev.txt")
    with open(src, "w", encoding="utf-8", newline="\n") as f:
        f.write("rt evidence\n")
    ucli.cmd_evidence(_a(path=path, type="ACTION", file=src,
                         media_type="text/plain", note="rt"))
    ucli.cmd_submit(_a(path=path, key=key))
    return path


def _checks(r):
    return {c["id"]: c["result"] for c in r["checks"]}


CASES = []


def case(cid, name, expect, fn):
    CASES.append((cid, name, expect, fn))


def _j(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _w(p, o):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=2)


# RT01 证据索引里的路径穿越 ------------------------------------------------
def rt01(d, key):
    idx = _j(os.path.join(d, "evidence", "index.json"))
    idx["entries"][0]["path"] = os.path.join("..", "..", "outside.txt")
    _w(os.path.join(d, "evidence", "index.json"), idx)
    return verify(d)


# RT02 绝对路径条目 --------------------------------------------------------
def rt02(d, key):
    idx = _j(os.path.join(d, "evidence", "index.json"))
    idx["entries"][0]["path"] = "C:\\Windows\\win.ini"
    _w(os.path.join(d, "evidence", "index.json"), idx)
    return verify(d)


# RT03 符号链接指向证据目录之外 -------------------------------------------
def rt03(d, key):
    outside = os.path.join(os.path.dirname(d), "outside.txt")
    with open(outside, "w", encoding="utf-8") as f:
        f.write("rt evidence\n")          # 与声明内容一致，看是否只靠哈希
    entry = _j(os.path.join(d, "evidence", "index.json"))["entries"][0]
    link = os.path.join(d, "evidence", entry["path"])
    os.remove(link)
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        return {"checks": [], "result": "SKIP", "assurance": "-"}
    return verify(d)


# RT04 算法混淆：声明 Ed25519，签名却是 HMAC ------------------------------
def rt04(d, key):
    seal = _j(os.path.join(d, "signatures", "seal.json"))
    seal["algorithm"] = "HMAC-SHA256"
    _w(os.path.join(d, "signatures", "seal.json"), seal)
    return verify(d)


# RT05 签名降级：删掉签名目录，manifest 仍是 SUBMITTED -------------------
def rt05(d, key):
    shutil.rmtree(os.path.join(d, "signatures"))
    return verify(d)


# RT06 manifest 里写 NaN（json 接受，JCS 必须拒绝）------------------------
def rt06(d, key):
    man = _j(os.path.join(d, "manifest.json"))
    man["confidence"] = float("nan")
    _w(os.path.join(d, "manifest.json"), man)
    return verify(d)


# RT07 索引里重复同一个 path 两次（哈希相同）-----------------------------
def rt07(d, key):
    idx = _j(os.path.join(d, "evidence", "index.json"))
    idx["entries"].append(dict(idx["entries"][0]))
    _w(os.path.join(d, "evidence", "index.json"), idx)
    return verify(d)


# RT08 超大证据文件（50MB，看是否线性爆炸）--------------------------------
def rt08(d, key):
    big = os.path.join(os.path.dirname(d), "big.bin")
    with open(big, "wb") as f:
        f.write(b"\0" * (50 * 1024 * 1024))
    ucli.cmd_evidence(_a(path=d, type="OUTPUT", file=big,
                         media_type="application/octet-stream", note="rt"))
    ucli.cmd_submit(_a(path=d, key=key))
    t0 = time.perf_counter()
    r = verify(d)
    r["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return r


# RT09 文本文件只改行尾（CRLF），内容语义不变 ----------------------------
def rt09(d, key):
    entry = _j(os.path.join(d, "evidence", "index.json"))["entries"][0]
    p = os.path.join(d, "evidence", entry["path"])
    data = open(p, "rb").read()
    open(p, "wb").write(data.replace(b"\n", b"\r\n"))
    return verify(d)


# RT10 攻击者自洽重签（换钥），open 模式是否仍 PASS ---------------------
def rt10(d, key):
    seed = us.ed_generate_seed()
    pub = us.ed_public_key(seed)
    ident = _j(os.path.join(d, "identity.json"))
    man = _j(os.path.join(d, "manifest.json"))
    lc = _j(os.path.join(d, "lifecycle.json"))
    sig, pub_b64 = us.ed_seal_sign(seed, ident, man, lc)
    _w(os.path.join(d, "signatures", "seal.json"), {
        "schema": "x", "algorithm": "Ed25519",
        "key_id": us.ed_key_id(pub), "public_key": pub_b64,
        "signed": "identity+manifest+lifecycle", "signature": sig,
        "created_at": "2026-11-17T00:00:00Z"})
    return verify(d)


# RT12 同一攻击，但验证方钉住了原公钥：暴露 RT10 的真缺口在 open 模式 ------
def rt12(d, key, pubkey=None):
    seed = us.ed_generate_seed()
    ident = _j(os.path.join(d, "identity.json"))
    man = _j(os.path.join(d, "manifest.json"))
    lc = _j(os.path.join(d, "lifecycle.json"))
    sig, pub_b64 = us.ed_seal_sign(seed, ident, man, lc)
    _w(os.path.join(d, "signatures", "seal.json"), {
        "schema": "x", "algorithm": "Ed25519",
        "key_id": us.ed_key_id(us.ed_public_key(seed)), "public_key": pub_b64,
        "signed": "identity+manifest+lifecycle", "signature": sig,
        "created_at": "2026-11-17T00:00:00Z"})
    # here the verifier pins the ORIGINAL key, which the attacker does not hold
    return verify(d, pubkey=us.ed_public_key(SEED))


# RT11 evidence 索引条目 type 改成合法但错误的值（M19 的变体：action→output）
def rt11(d, key):
    idx = _j(os.path.join(d, "evidence", "index.json"))
    idx["entries"][0]["type"] = "OUTPUT"
    _w(os.path.join(d, "evidence", "index.json"), idx)
    return verify(d)


# RT13 追加一条伪造回执：前驱链接填错，试图把编造记录接在真链尾巴上 -----
def rt13(d, key):
    env = {"type": "protectmcp:decision", "issued_at": "2026-11-17T09:00:00Z",
           "issuer_id": "did:web:attacker.eu"}
    _w(os.path.join(d, "evidence", "chain.json"), {
        "schema": "uibc-core/chain@1",
        "receipts": [
            {"envelope": env, "previous_receipt_hash": "0" * 64},
            {"envelope": {"type": "protectmcp:decision",
                          "issued_at": "2026-11-17T09:01:00Z",
                          "issuer_id": "did:web:attacker.eu"},
             "previous_receipt_hash": "c" * 64}]})
    return verify(d)


# RT14 策略制品被换掉但声明摘要不改（digest 与内容脱钩）---------------
def rt14(d, key):
    pol = os.path.join(d, "evidence", "policy")
    os.makedirs(pol, exist_ok=True)
    with open(os.path.join(pol, "p.json"), "w", encoding="utf-8") as f:
        json.dump({"action": "allow_all"}, f)
    _w(os.path.join(d, "evidence", "policies.json"),
       {"policies": [{"digest": "sha256:" + "d" * 64,
                      "path": "evidence/policy/p.json"}]})
    return verify(d)


# RT15 回填未来时间戳：manifest 时间写成未来，让"新鲜"由攻击者定义 --------
def rt15(d, key):
    from datetime import datetime, timedelta, timezone
    man = _j(os.path.join(d, "manifest.json"))
    future = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    for k in ("created_at", "updated_at", "timestamp", "issued_at"):
        if k in man:
            man[k] = future
            break
    _w(os.path.join(d, "manifest.json"), man)
    return verify(d)


case("RT01", "索引路径穿越 ../../outside.txt", "FAIL（路径必须落在证据根内）", rt01)
case("RT02", "索引绝对路径 C:\\Windows\\win.ini", "FAIL（不得读任意绝对路径）", rt02)
case("RT03", "证据文件换成指向外部的符号链接", "FAIL（或至少不得读穿）", rt03)
case("RT04", "算法混淆：声明 Ed25519 实为 HMAC", "FAIL（S6）", rt04)
case("RT05", "签名降级：删掉 seal.json", "不得 PASS（应为 INCONCLUSIVE）", rt05)
case("RT06", "manifest 注入 NaN", "FAIL 或干净报错（不得崩溃/放行）", rt06)
case("RT07", "索引重复同一 path 两次", "FAIL（重复条目应被拒）", rt07)
case("RT08", "50MB 证据文件", "PASS 且耗时线性可接受", rt08)
case("RT09", "只改行尾 CRLF（语义不变）", "FAIL（哈希敏感，属已知硬化代价）", rt09)
case("RT10", "攻击者自洽重签（换钥）", "open=PASS 但必须标 unanchored", rt10)
case("RT11", "索引 type: ACTION→OUTPUT（M19 变体）", "FAIL（S7）", rt11)
case("RT12", "换钥重签 + 验证方钉住原公钥", "FAIL（S6）", rt12)
case("RT13", "链尾追加伪造回执（前驱链接写错）", "FAIL（S17）", rt13)
case("RT14", "策略制品换掉、声明摘要不改", "FAIL（S18）", rt14)
case("RT15", "manifest 时间回填到 6 小时后", "FAIL（S12 未来偏斜）", rt15)


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="rt-")
    kp = os.path.join(tmp, "ok.key")
    with open(kp, "w", encoding="ascii") as f:
        f.write("ed25519:" + SEED.hex())
    base = build(os.path.join(tmp, "base.uibc"), kp)
    pub = us.ed_public_key(SEED)

    rows = []
    for cid, name, expect, fn in CASES:
        d = os.path.join(tmp, cid)
        shutil.copytree(base, d)
        try:
            r = fn(d, kp)
            res = r.get("result")
            ck = {c["id"]: c["result"] for c in r.get("checks", [])}
            failed = [k for k, v in ck.items() if v == "FAIL"]
            extra = ""
            if cid == "RT08":
                extra = " elapsed=%sms" % r.get("elapsed_ms")
            note = ("trust=" + str(r.get("trust_level"))) if r.get("trust_level") else ""
        except Exception as e:
            res, failed, note, extra = "EXCEPTION", [], type(e).__name__ + ": " + str(e)[:70], ""
        rows.append({"id": cid, "case": name, "expect": expect, "result": res,
                     "failed_checks": failed, "note": note + extra})
        print("%-5s %-42s -> %-14s %s %s" % (cid, name, res, ",".join(failed), note + extra))

    doc = {"meta": {"probe": "redteam", "generated_at_utc":
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
           "cases": rows}
    p = os.path.join(OUT, "redteam_result.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("RESULT_JSON=" + p)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
