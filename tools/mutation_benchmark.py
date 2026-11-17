#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""假接受率基准（false-accept benchmark）——对标 AgentAuth / Vaara 的公开口径。

问题：我们对外只说"验过了 PASS"，没说"篡改多少后仍会被放过"。没有这个数字，
      PASS 在外部评审眼里等于"作者自述"。

做法：用 uibc-core CLI 现场构建一个干净包（Ed25519 封签，种子公开仅为可复跑），
      再对每一类字段做单点篡改，跑两种验证模式：
        open   —— 陌生人只拿到包（公钥随包走，无预置信任）
        pinned —— 依赖方另行持有公钥，验证时 pin 住预期公钥
      统计"篡改后仍判 PASS"的比例 = 假接受率。这是唯一诚实的强度口径。

输出：tools/out/mutation_benchmark.json + 控制台 markdown 表。

用法： python tools/mutation_benchmark.py
"""
import base64
import hashlib
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import uibc_core.cli as ucli  # noqa: E402
from uibc_core import signing as us  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

DEMO_SEED = bytes(range(32))            # 公开种子：只为可复跑，任何人可重建同包
OUT = os.path.join(ROOT, "tools", "out")
BASE = os.path.join(OUT, "_mb", "base")
PKG_NAME = "mb-agent-001"


def _a(**kw):
    return type("A", (), kw)()


def build_base():
    for p in (BASE, os.path.join(OUT, "_mb", "key")):
        if os.path.exists(p):
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    key_path = os.path.join(OUT, "_mb", "owner.key")
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, "w", encoding="ascii") as f:
        f.write("ed25519:" + DEMO_SEED.hex())

    ucli.cmd_init(_a(path=BASE))
    ucli.cmd_register(_a(path=BASE, agent_id=PKG_NAME, owner="mb-owner",
                         agent_type="software-agent", version="1.0.0"))
    ucli.cmd_event(_a(path=BASE, type="ACTIVATE", actor="mb-owner"))
    log = os.path.join(OUT, "_mb", "action.log")
    with open(log, "w", encoding="utf-8", newline="\n") as f:
        f.write("2026-11-17T00:00:00Z ACTION triage ticket #1 routed\n")
    ucli.cmd_evidence(_a(path=BASE, type="ACTION", file=log, media_type="text/plain", note="mb"))
    note = os.path.join(OUT, "_mb", "eval.txt")
    with open(note, "w", encoding="utf-8", newline="\n") as f:
        f.write("2026-11-17T00:01:00Z EVALUATION 20/20 matched template\n")
    ucli.cmd_evidence(_a(path=BASE, type="EVALUATION", file=note, media_type="text/plain", note="mb"))
    ucli.cmd_submit(_a(path=BASE, key=key_path))
    return BASE


# --------------------------------------------------------------------------
# 篡改器：每个函数接收包目录，就地做单点修改
# --------------------------------------------------------------------------
def _j(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _w(p, o):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=2)


def m_manifest_agent_id(d):
    o = _j(os.path.join(d, "manifest.json")); o["agent_id"] = "evil-agent"; _w(os.path.join(d, "manifest.json"), o)


def m_manifest_root(d):
    o = _j(os.path.join(d, "manifest.json")); o["evidence_root"] = "0" * 64; _w(os.path.join(d, "manifest.json"), o)


def m_manifest_version(d):
    o = _j(os.path.join(d, "manifest.json")); o["agent_version"] = "9.9.9"; _w(os.path.join(d, "manifest.json"), o)


def m_manifest_status(d):
    o = _j(os.path.join(d, "manifest.json")); o["status"] = "APPROVED"; _w(os.path.join(d, "manifest.json"), o)


def m_manifest_extra(d):
    o = _j(os.path.join(d, "manifest.json")); o["human_approval"] = "granted"; _w(os.path.join(d, "manifest.json"), o)


def m_identity_owner(d):
    p = os.path.join(d, "identity.json"); o = _j(p); o["owner"] = "evil-owner"; _w(p, o)


def m_identity_type(d):
    p = os.path.join(d, "identity.json"); o = _j(p); o["agent_type"] = "autonomous-agent"; _w(p, o)


def m_lifecycle_timestamp(d):
    p = os.path.join(d, "lifecycle.json"); o = _j(p)
    if o.get("events"):
        o["events"][1]["timestamp"] = "2030-01-01T00:00:00Z"
    _w(p, o)


def m_lifecycle_actor(d):
    p = os.path.join(d, "lifecycle.json"); o = _j(p)
    if o.get("events"):
        o["events"][0]["actor"] = "attacker"
    _w(p, o)


def m_lifecycle_drop_first(d):
    p = os.path.join(d, "lifecycle.json"); o = _j(p)
    o["events"] = o.get("events", [])[1:]
    _w(p, o)


def m_lifecycle_insert(d):
    p = os.path.join(d, "lifecycle.json"); o = _j(p)
    evs = o.get("events", [])
    if evs:
        clone = dict(evs[-1])
        clone["event_id"] = "inserted-event"
        clone["event_type"] = "ACTIVATE"
        clone["previous_event"] = evs[-1]["event_id"]
        clone["timestamp"] = "2026-11-17T00:02:00Z"
        evs.append(clone)
    _w(p, o)


def m_evidence_byte(d):
    p = os.path.join(d, "evidence", "files", "action.log")
    with open(p, "rb") as f:
        b = bytearray(f.read())
    b[len(b) // 2] ^= 0x01
    with open(p, "wb") as f:
        f.write(bytes(b))


def m_evidence_add_entry(d):
    """追加一个真实文件 + 与之一致的条目：看 verifier 是否接受"扩表"。"""
    p = os.path.join(d, "evidence", "files", "extra.txt")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("2026-11-17T00:03:00Z ACTION unreviewed extra action\n")
    idx_p = os.path.join(d, "evidence", "index.json")
    o = _j(idx_p)
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    o.setdefault("entries", []).append({"path": "extra.txt", "sha256": h, "type": "ACTION", "note": "injected"})
    _w(idx_p, o)


def m_evidence_drop_entry(d):
    idx_p = os.path.join(d, "evidence", "index.json")
    o = _j(idx_p)
    if o.get("entries"):
        o["entries"] = o["entries"][:-1]
    _w(idx_p, o)


def m_evidence_delete_file(d):
    for f in ("run-summary.txt", "eval.txt"):
        p = os.path.join(d, "evidence", "files", f)
        if os.path.exists(p):
            os.remove(p)


def m_seal_sig(d):
    p = os.path.join(d, "signatures", "seal.json"); o = _j(p)
    sig = base64.b64decode(o["signature"])
    sig = sig[:-1] + bytes([sig[-1] ^ 0x01])
    o["signature"] = base64.b64encode(sig).decode()
    _w(p, o)


def m_seal_keyswap(d):
    """教科书式伪造：换成攻击者公钥，并用攻击者私钥重新封签。"""
    attacker = bytes(range(1, 33))
    apub = us.ed_public_key(attacker)
    ident = _j(os.path.join(d, "identity.json"))
    man = _j(os.path.join(d, "manifest.json"))
    lc = _j(os.path.join(d, "lifecycle.json"))
    sig_b64, pub_b64 = us.ed_seal_sign(attacker, ident, man, lc)
    p = os.path.join(d, "signatures", "seal.json")
    o = _j(p)
    o["public_key"] = pub_b64
    o["signature"] = sig_b64
    o["key_id"] = hashlib.sha256(apub).hexdigest()
    _w(p, o)


def m_root_extra_file(d):
    with open(os.path.join(d, "notes.md"), "w", encoding="utf-8") as f:
        f.write("# added after submission\n")


def m_index_metadata(d):
    """只改 index 条目的元数据，不动文件、不动哈希。

    这一条是本轮做 EP-AEC 适配器时才发现漏测的：证据内容哈希与证据根都等于
    原值，旧 S1-S6 全部通过，于是"这条证据是什么类型、附了什么说明"可以被任意
    改写而不被发现。修法是 manifest 携带 evidence_index_digest 并由封签覆盖（S7）。
    """
    idx_p = os.path.join(d, "evidence", "index.json")
    o = _j(idx_p)
    if o.get("entries"):
        e = o["entries"][0]
        e["type"] = "OUTPUT"                 # 仍是合法类型，S4 不会报错
        e["note"] = "reviewed and approved"  # 伪造一条对自己有利的说明
    _w(idx_p, o)


MUTATIONS = [
    ("M01 manifest.agent_id", "替换 agent_id 为 evil-agent", m_manifest_agent_id),
    ("M02 manifest.evidence_root", "把证据根换成全 0", m_manifest_root),
    ("M03 manifest.agent_version", "改版本号", m_manifest_version),
    ("M04 manifest.status", "自封 APPROVED", m_manifest_status),
    ("M05 manifest 增字段", "伪造 human_approval=granted", m_manifest_extra),
    ("M06 identity.owner", "换所有者", m_identity_owner),
    ("M07 identity.agent_type", "改代理类型", m_identity_type),
    ("M08 lifecycle 时间戳", "把 ACTIVATE 时间改到 2030", m_lifecycle_timestamp),
    ("M09 lifecycle actor", "把 REGISTER 的 actor 改成 attacker", m_lifecycle_actor),
    ("M10 lifecycle 删首事件", "删 REGISTER（断链）", m_lifecycle_drop_first),
    ("M11 lifecycle 插入事件", "追加非法 ACTIVATE", m_lifecycle_insert),
    ("M12 证据内容改 1 字节", "改 action.log 中间字节", m_evidence_byte),
    ("M13 证据扩表", "追加文件+条��（哈希自洽）", m_evidence_add_entry),
    ("M14 证据删条", "从 index 删掉一条", m_evidence_drop_entry),
    ("M15 证据删文件", "删掉 run-summary.txt / eval.txt", m_evidence_delete_file),
    ("M16 封签改 1 字节", "签名末字节翻转", m_seal_sig),
    ("M17 换钥重签（keyswap）", "攻击者公钥+攻击者私钥重签", m_seal_keyswap),
    ("M18 包内外挂文件", "根目录加 notes.md", m_root_extra_file),
    ("M19 索引元数据", "改 index 条目的 type/note（不动文件）", m_index_metadata),
]


def main():
    build_base()
    pub = us.ed_public_key(DEMO_SEED)

    def run(d, pin):
        r = verify(d, pubkey=pub) if pin else verify(d)
        checks = {c["id"]: c["result"] for c in r["checks"]}
        return r["result"], checks

    base_open = run(BASE, False)
    base_pin = run(BASE, True)
    print("base(open)=%s  base(pinned)=%s" % (base_open[0], base_pin[0]))
    if base_pin[0] != "PASS":
        print("!! 基线不是 PASS，后面的数字没有意义，先修基线")
        return 1

    rows = []
    for mid, desc, fn in MUTATIONS:
        row = {"id": mid, "mutation": desc, "modes": {}}
        for mode, pin in (("open", False), ("pinned", True)):
            d = os.path.join(OUT, "_mb", "m_" + mid.split()[0])
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(BASE, d)
            try:
                fn(d)
                verdict, checks = run(d, pin)
            except Exception as e:
                verdict, checks = "ERROR", {"error": str(e)[:80]}
            failed = [k for k, v in checks.items() if v == "FAIL"]
            row["modes"][mode] = {"verdict": verdict, "failed_checks": failed,
                                  "accepted": verdict == "PASS"}
        rows.append(row)
        print("%-30s open=%-12s pinned=%-12s accepted=%s/%s"
              % (mid, row["modes"]["open"]["verdict"], row["modes"]["pinned"]["verdict"],
                 int(row["modes"]["open"]["accepted"]), int(row["modes"]["pinned"]["accepted"])))

    # ---------------------------------------------------------------- head
    # Two extra cases that a hash chain alone cannot answer.
    #   M20 rollback: the attacker installs an OLDER package. Everything in it
    #       is self-consistent and correctly signed, so open and pinned both
    #       say PASS. Only a head observed outside the package catches it.
    #   M21 truncation on an UNSIGNED package: the log loses its last event and
    #       the manifest still describes the longer log. With no seal there is
    #       nothing but the head commitment to notice.
    newest = os.path.join(OUT, "_mb", "_newest")
    if os.path.exists(newest):
        shutil.rmtree(newest)
    shutil.copytree(BASE, newest)
    extra = os.path.join(OUT, "_mb", "incident.log")
    with open(extra, "w", encoding="utf-8", newline="\n") as f:
        f.write("2026-11-17T00:02:00Z INCIDENT scope drift detected\n")
    ucli.cmd_evidence(_a(path=newest, type="INCIDENT", file=extra,
                         media_type="text/plain", note="mb"))
    ucli.cmd_submit(_a(path=newest, key=os.path.join(OUT, "_mb", "owner.key")))
    newest_head = _j(os.path.join(newest, "manifest.json"))["checkpoint_head"]

    d = os.path.join(OUT, "_mb", "m_M20")
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(BASE, d)          # BASE *is* the older, fully consistent one
    row = {"id": "M20 整包回滚（装在旧包）", "mutation": "用旧的自洽包替换当前状态",
           "modes": {}}
    for mode, kw in (("open", {}), ("pinned", {"pubkey": pub}),
                     ("head-pinned", {"pubkey": pub, "expect_head": newest_head})):
        r = verify(d, **kw)
        checks = {c["id"]: c["result"] for c in r["checks"]}
        failed = [k for k, v in checks.items() if v == "FAIL"]
        row["modes"][mode] = {"verdict": r["result"], "failed_checks": failed,
                              "accepted": r["result"] == "PASS"}
    rows.append(row)
    print("%-30s open=%-12s pinned=%-12s head-pinned=%-12s"
          % (row["id"], row["modes"]["open"]["verdict"],
             row["modes"]["pinned"]["verdict"], row["modes"]["head-pinned"]["verdict"]))

    unsigned = os.path.join(OUT, "_mb", "m_M21")
    if os.path.exists(unsigned):
        shutil.rmtree(unsigned)
    shutil.copytree(BASE, unsigned)
    sigdir = os.path.join(unsigned, "signatures")
    if os.path.isdir(sigdir):
        shutil.rmtree(sigdir)                     # unsigned: no seal at all
    lc = _j(os.path.join(unsigned, "lifecycle.json"))
    lc["events"] = lc["events"][:-1]             # drop the last event
    _w(os.path.join(unsigned, "lifecycle.json"), lc)
    row = {"id": "M21 未封签包截断尾部", "mutation": "删掉最后一条事件，manifest 仍写长链",
           "modes": {}}
    for mode, kw in (("open", {}), ("head-pinned", {"expect_head": newest_head})):
        r = verify(unsigned, **kw)
        checks = {c["id"]: c["result"] for c in r["checks"]}
        failed = [k for k, v in checks.items() if v == "FAIL"]
        row["modes"][mode] = {"verdict": r["result"], "failed_checks": failed,
                              "accepted": r["result"] == "PASS"}
    row["modes"]["pinned"] = row["modes"]["open"]
    rows.append(row)
    print("%-30s open=%-12s head-pinned=%-12s"
          % (row["id"], row["modes"]["open"]["verdict"],
             row["modes"]["head-pinned"]["verdict"]))

    summary = {}
    for mode in ("open", "pinned", "head-pinned"):
        acc = sum(1 for r in rows if r["modes"].get(mode, {}).get("accepted"))
        summary[mode] = {"accepted": acc, "total": len(rows),
                         "false_accept_rate": round(acc / len(rows) * 100, 1)}

    out = {"meta": {"generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "verifier": "uibc-core verify()", "package": "mb-agent-001",
                    "base_open": base_open[0], "base_pinned": base_pin[0],
                    "note": "PASS 在 open 模式即视为'被接受'；INCONCLUSIVE / FAIL 均记未接受"},
           "summary": summary, "rows": rows}
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "mutation_benchmark.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    md = ["| 篡改 | open 模式 | pinned 模式 | 捕获的检查 |", "|---|---|---|---|"]
    for r in rows:
        md.append("| %s | %s | %s | %s |" % (
            r["id"], r["modes"]["open"]["verdict"], r["modes"]["pinned"]["verdict"],
            ",".join(r["modes"]["pinned"]["failed_checks"]) or "—"))
    print("\n" + "\n".join(md))
    print("\n假接受率 open=%.1f%%  pinned=%.1f%%" % (
        summary["open"]["false_accept_rate"], summary["pinned"]["false_accept_rate"]))
    print("RESULT_JSON=" + p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
