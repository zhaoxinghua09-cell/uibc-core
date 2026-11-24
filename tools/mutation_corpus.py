#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""500 例篡改语料（mutation corpus）。

为什么要有它：`mutation_benchmark.py` 是每档 21 例，一个用例就能让假接受率跳动
4.8 个百分点，那个数字撑不起任何"我们更严"的说法。这里把同一批篡改族扩成
**500 例**，族内参数逐个变（字节位置、字段、时间、序号、攻击者密钥、回滚深度、
截断长度），再按 open / pinned / head-pinned 三档统计。

所有参数由索引决定，不用随机数：同一条命令在任何机器上生成同一批用例。

用法： python tools/mutation_corpus.py [--out <path>]
输出： 默认 tools/out/mutation_corpus.json；--out 可写到仓库内（如
      benchmarks/corpus/mutation-corpus-500.json），供外人逐例比对。
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
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mutation_benchmark as mb  # noqa: E402
from uibc_core import signing as us  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

OUT = mb.OUT
BASE = mb.BASE
WORK = os.path.join(OUT, "_mc")
A = mb._a
_j = mb._j
_w = mb._w


def _flip(path, offset):
    with open(path, "rb") as f:
        b = bytearray(f.read())
    if not b:
        return
    b[offset % len(b)] ^= 0x01
    with open(path, "wb") as f:
        f.write(bytes(b))


def _set(path, key, value):
    o = _j(path)
    o[key] = value
    _w(path, o)


def _del(path, key):
    o = _j(path)
    o.pop(key, None)
    _w(path, o)


def _blob_files(d):
    p = os.path.join(d, "evidence", "index.json")
    o = _j(p)
    out = []
    for e in o.get("entries", []):
        rel = os.path.join("evidence", e.get("path", ""))
        f = os.path.join(d, rel)
        if os.path.isfile(f):
            out.append(f)
    return out


MANIFEST_FIELDS = ["agent_id", "agent_version", "status", "evidence_root",
                   "checkpoint_head", "lifecycle_head", "evidence_count",
                   "evidence_index_digest", "min_verifier_version", "created_at",
                   "schema", "agent_id"]  # 最后一个重复出现，索引仍然唯一
MANIFEST_VALUES = ["evil", 999999, "0" * 64, "PASSED", "", None]
# Fields the v1.1 narrow index digest never covered (conformance vector D-002).
# F18 mutates them; before S20 existed every one of these passed the suite.
FULL_META_FIELDS = ["evidence_id", "media_type", "created_at"]


def mut_manifest_scalar(field, value):
    def f(d):
        p = os.path.join(d, "manifest.json")
        if value is None:
            _del(p, field)
        else:
            _set(p, field, value)
    return f


def mut_identity_scalar(field, value):
    def f(d):
        _set(os.path.join(d, "identity.json"), field, value)
    return f


def mut_ts(value, index):
    def f(d):
        p = os.path.join(d, "lifecycle.json")
        o = _j(p)
        if o.get("events"):
            o["events"][min(index, len(o["events"]) - 1)]["timestamp"] = value
        _w(p, o)
    return f


def mut_actor(value, index):
    def f(d):
        p = os.path.join(d, "lifecycle.json")
        o = _j(p)
        if o.get("events"):
            o["events"][min(index, len(o["events"]) - 1)]["actor"] = value
        _w(p, o)
    return f


def mut_drop_events(n):
    def f(d):
        p = os.path.join(d, "lifecycle.json")
        o = _j(p)
        o["events"] = o.get("events", [])[n:]
        _w(p, o)
    return f


def mut_insert_event(kind, ts):
    def f(d):
        p = os.path.join(d, "lifecycle.json")
        o = _j(p)
        evs = o.get("events", [])
        if evs:
            clone = dict(evs[-1])
            clone["event_id"] = "inserted-%s-%s" % (kind, ts)
            clone["event_type"] = kind
            clone["previous_event"] = evs[-1]["event_id"]
            clone["timestamp"] = ts
            evs.append(clone)
        _w(p, o)
    return f


def mut_drop_index(fix_count=False, fix_digest=False, delete_index=False,
                   resign=False, drop=1):
    """Remove `drop` entries from the index, optionally repairing the two fields
    that make the removal self-consistent (count, metadata digest) and optionally
    re-sealing with an attacker key. A variant that repairs nothing is what a
    careless attacker does; a variant that repairs everything is what a careful
    one does. The first is caught by S12, the second only by S6/S19."""
    def f(d):
        ip = os.path.join(d, "evidence", "index.json")
        if delete_index:
            os.remove(ip)
            return
        o = _j(ip)
        o["entries"] = o.get("entries", [])[:-drop]
        _w(ip, o)
        mp = os.path.join(d, "manifest.json")
        m = _j(mp)
        if fix_count:
            m["evidence_count"] = len(o["entries"])
        if fix_digest:
            from uibc_core.canonical import index_metadata_digest as imd
            m["evidence_index_digest"] = imd(o)
        _w(mp, m)
        if resign:
            attacker = bytes([0xC5] * 32)
            ident = _j(os.path.join(d, "identity.json"))
            lc = _j(os.path.join(d, "lifecycle.json"))
            sig_b64, pub_b64 = us.ed_seal_sign(attacker, ident, m, lc)
            sp = os.path.join(d, "signatures", "seal.json")
            so = _j(sp)
            so["public_key"] = pub_b64
            so["signature"] = sig_b64
            so["key_id"] = hashlib.sha256(us.ed_public_key(attacker)).hexdigest()
            _w(sp, so)
    return f


def mut_add_entry(tag, etype):
    def f(d):
        p = os.path.join(d, "evidence", "files", "inject-%s.txt" % tag)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("2026-11-17T00:04:00Z %s injected-%s\n" % (etype, tag))
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        idx = os.path.join(d, "evidence", "index.json")
        o = _j(idx)
        o.setdefault("entries", []).append(
            {"path": "inject-%s.txt" % tag, "sha256": h, "type": etype, "note": "injected"})
        _w(idx, o)
    return f


def mut_index_meta(etype, note):
    def f(d):
        p = os.path.join(d, "evidence", "index.json")
        o = _j(p)
        for e in o.get("entries", []):
            e["type"] = etype
            e["note"] = note
        _w(p, o)
    return f


def mut_index_full_meta(field, value):
    """D-002 closed: rewrite a metadata field that the NARROW digest never covered.

    Before 0.6.0 none of evidence_id / media_type / created_at was inside any
    sealed commitment, so these mutations passed the whole suite. The attack is
    kept as its own family because a fix that is not attacked is a fix nobody
    has tested.
    """
    def f(d):
        p = os.path.join(d, "evidence", "index.json")
        o = _j(p)
        for e in o.get("entries", []):
            e[field] = value
        _w(p, o)
    return f


def mut_keyswap(seed_byte):
    def f(d):
        attacker = bytes([seed_byte] * 32)
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
    return f


def mut_extra_file(name):
    def f(d):
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write("# added after submission\n")
    return f


def mut_sig_byte(offset):
    def f(d):
        p = os.path.join(d, "signatures", "seal.json")
        o = _j(p)
        sig = bytearray(base64.b64decode(o["signature"]))
        sig[offset % len(sig)] ^= 0x01
        o["signature"] = base64.b64encode(bytes(sig)).decode()
        _w(p, o)
    return f


def mut_blob_byte(which, offset):
    def f(d):
        files = _blob_files(d)
        if not files:
            return
        _flip(files[which % len(files)], offset)
    return f


def mut_manifest_extra(key):
    def f(d):
        _set(os.path.join(d, "manifest.json"), key, "granted")
    return f


def build_cases():
    cases = []  # (id, family, desc, fn, expect_head)

    for i in range(64):
        cases.append(("F1-%02d" % i, "sig-byte", "封签第 %d 字节翻转" % i,
                      mut_sig_byte(i), None))

    for i in range(98):
        cases.append(("F2-%02d" % i, "blob-byte",
                      "证据文件 %d 第 %d 字节翻转" % (i % 2, i * 7),
                      mut_blob_byte(i % 2, i * 7), None))

    for i, field in enumerate([f for f in MANIFEST_FIELDS if f != "agent_id"][:12]):
        for value in MANIFEST_VALUES[:4]:
            cases.append(("F3-%02d-%02d" % (i, MANIFEST_VALUES.index(value)),
                          "manifest-scalar", "manifest.%s ← %r" % (field, value),
                          mut_manifest_scalar(field, value), None))

    for i, (field, value) in enumerate([("owner", "evil-owner"),
                                       ("agent_type", "autonomous-agent"),
                                       ("owner", ""),
                                       ("agent_type", "human")]):
        for j in range(3):
            cases.append(("F4-%d-%d" % (i, j), "identity-scalar",
                          "identity.%s ← %r (%d)" % (field, value, j),
                          mut_identity_scalar(field, value), None))

    for i in range(30):
        cases.append(("F5-%02d" % i, "lifecycle-ts", "事件时间改成 2030+%d 天" % i,
                      mut_ts("2030-01-%02dT00:00:00Z" % (1 + i % 28), i), None))

    for i in range(16):
        cases.append(("F6-%02d" % i, "lifecycle-actor", "actor 改成 attacker-%d" % i,
                      mut_actor("attacker-%d" % i, i % 2), None))

    for n in range(1, 7):
        cases.append(("F7-%02d" % n, "lifecycle-drop", "删掉前 %d 条事件" % n,
                      mut_drop_events(n), None))

    kinds = ["ACTIVATE", "SUSPEND", "RESUME", "RETIRE"]
    for i in range(24):
        cases.append(("F8-%02d" % i, "lifecycle-insert",
                      "追加伪造 %s 事件（%d）" % (kinds[i % 4], i),
                      mut_insert_event(kinds[i % 4], "2026-11-17T00:%02d:00Z" % (i % 60)), None))

    # 删索引条目：只有"真的删掉"才算攻击。若只留的条数 ≥ 原条数，改动是空操作，
    # 那不是在测验证器，是在给自己记一个假缺口（本轮真踩过这个坑）。
    drop_variants = [
        ("F9-00", "删 1 条，什么都不修"),
        ("F9-01", "删 1 条，顺手改 evidence_count"),
        ("F9-02", "删 1 条，顺手改 evidence_index_digest"),
        ("F9-03", "删 1 条，两个字段都修"),
        ("F9-04", "删 1 条，两个字段都修 + 攻击者重签"),
        ("F9-05", "整个删掉 evidence/index.json"),
    ]
    for cid, desc in drop_variants:
        args = {
            "F9-00": {},
            "F9-01": {"fix_count": True},
            "F9-02": {"fix_digest": True},
            "F9-03": {"fix_count": True, "fix_digest": True},
            "F9-04": {"fix_count": True, "fix_digest": True, "resign": True},
            "F9-05": {"delete_index": True},
        }[cid]
        cases.append((cid, "evidence-drop", desc, mut_drop_index(**args), None))

    for i in range(24):
        cases.append(("F10-%02d" % i, "evidence-add",
                      "追加自洽条目 %d（%s）" % (i, kinds[i % 4]),
                      mut_add_entry(str(i), kinds[i % 4]), None))

    types = ["ACTION", "EVALUATION", "OUTPUT", "INCIDENT"]
    for i in range(24):
        cases.append(("F11-%02d" % i, "index-metadata",
                      "索引 type←%s note←approved-%d" % (types[i % 4], i),
                      mut_index_meta(types[i % 4], "approved-%d" % i), None))

    for i in range(40):
        cases.append(("F12-%02d" % i, "keyswap",
                      "攻击者第 %d 号密钥重签" % i,
                      mut_keyswap(1 + i), None))

    for i in range(24):
        cases.append(("F18-%02d" % i, "index-full-metadata",
                      "索引 %s←backdated-%d（窄摘要看不见的字段）"
                      % (FULL_META_FIELDS[i % 3], i),
                      mut_index_full_meta(FULL_META_FIELDS[i % 3],
                                          "backdated-%d" % i), None))

    for i in range(24):
        cases.append(("F13-%02d" % i, "root-extra", "根目录加 notes-%d.md" % i,
                      mut_extra_file("notes-%d.md" % i), None))

    for i in range(24):
        cases.append(("F16-%02d" % i, "manifest-extra",
                      "manifest 增字段 human_approval_%d" % i,
                      mut_manifest_extra("human_approval_%d" % i), None))

    for i, field in enumerate(["evidence_count", "lifecycle_head", "schema", "status",
                               "evidence_root", "min_verifier_version", "created_at",
                               "evidence_index_digest"]):
        cases.append(("F17-%02d" % i, "manifest-delete", "删掉 manifest.%s" % field,
                      mut_manifest_scalar(field, None), None))

    return cases


def build_newer(k):
    """造一个比 BASE 更新 k 条事件的包，返回它的 checkpoint_head。"""
    d = os.path.join(WORK, "newer_%02d" % k)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(BASE, d)
    for j in range(k):
        f = os.path.join(WORK, "extra_%02d_%02d.log" % (k, j))
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("2026-11-17T00:0%d:00Z INCIDENT tail %d\n" % (j % 10, j))
        mb.ucli.cmd_evidence(A(path=d, type="INCIDENT", file=f,
                               media_type="text/plain", note="mc"))
    mb.ucli.cmd_submit(A(path=d, key=os.path.join(OUT, "_mb", "owner.key")))
    return _j(os.path.join(d, "manifest.json"))["checkpoint_head"]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out_path = os.path.join(OUT, "mutation_corpus.json")
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 >= len(argv):
            print("--out needs a path", file=sys.stderr)
            return 2
        out_path = argv[i + 1]
    os.makedirs(WORK, exist_ok=True)
    mb.build_base()
    pub = us.ed_public_key(mb.DEMO_SEED)

    def run(d, mode):
        kw = {}
        if mode in ("pinned", "head-pinned"):
            kw["pubkey"] = pub
        if mode == "head-pinned":
            kw["expect_head"] = d["_expect_head"]
        r = verify(d if isinstance(d, str) else d["_dir"], **kw)
        checks = {c["id"]: c["result"] for c in r["checks"]}
        return r["result"], [k for k, v in checks.items() if v == "FAIL"]

    base_open = verify(BASE)
    if base_open["result"] not in ("PASS", "INCONCLUSIVE"):
        print("!! 基线不是 PASS/INCONCLUSIVE，先修基线：%s" % base_open["result"])
        return 1

    # ---- 回滚族：先造 20 个"更新"的包，取它们的 head 当期望值
    rollback = []
    for k in range(1, 21):
        head = build_newer(k)
        rollback.append(("F14-%02d" % k, "rollback",
                         "装上旧包，验证器已接受过更深的第 %d 版" % k, head))

    # ---- 截断族：40 例（封签/未封签 × 调整 manifest/不调整 × 截断 1..10）
    trunc = []
    newest_head = build_newer(3)
    for drop in range(1, 11):
        for signed in (False, True):
            for adjust in (False, True):
                trunc.append((drop, signed, adjust))

    cases = build_cases()
    rows = []

    def do_case(cid, family, desc, fn, expect_head=None, extra_modes=()):
        d = os.path.join(WORK, "c_" + cid)
        if os.path.exists(d):
            shutil.rmtree(d)
        shutil.copytree(BASE, d)
        rec = {"id": cid, "family": family, "mutation": desc, "modes": {}}
        try:
            fn(d)
        except Exception as e:
            rec["error"] = str(e)[:80]
            rows.append(rec)
            return
        modes = ("open", "pinned") + tuple(extra_modes)
        for mode in modes:
            kw = {}
            if mode in ("pinned", "head-pinned"):
                kw["pubkey"] = pub
            if mode == "head-pinned":
                kw["expect_head"] = expect_head
            try:
                r = verify(d, **kw)
                checks = {c["id"]: c["result"] for c in r["checks"]}
                rec["modes"][mode] = {"verdict": r["result"],
                                      "failed_checks": [k for k, v in checks.items() if v == "FAIL"],
                                      "accepted": r["result"] == "PASS"}
            except Exception as e:
                rec["modes"][mode] = {"verdict": "ERROR", "failed_checks": [],
                                      "accepted": False, "error": str(e)[:80]}
        rows.append(rec)

    for cid, family, desc, fn, head in cases:
        do_case(cid, family, desc, fn)

    for cid, family, desc, head in rollback:
        do_case(cid, family, desc, lambda d: None, head, extra_modes=("head-pinned",))

    n = 0
    for drop, signed, adjust in trunc:
        cid = "F15-%02d" % n
        n += 1

        def mk(d, drop=drop, signed=signed, adjust=adjust):
            p = os.path.join(d, "lifecycle.json")
            o = _j(p)
            o["events"] = o.get("events", [])[:-drop]
            _w(p, o)
            if not signed:
                sigdir = os.path.join(d, "signatures")
                if os.path.isdir(sigdir):
                    shutil.rmtree(sigdir)
            if adjust:
                mp = os.path.join(d, "manifest.json")
                m = _j(mp)
                if o.get("events"):
                    m["lifecycle_head"] = o["events"][-1]["event_id"]
                _w(mp, m)

        do_case(cid, "truncation",
                "截断尾部 %d 条（%s，manifest %s）"
                % (drop, "已封签" if signed else "未封签",
                   "已调整" if adjust else "未调整"),
                mk, newest_head, extra_modes=("head-pinned",))

    summary = {}
    for mode in ("open", "pinned", "head-pinned"):
        sub = [r for r in rows if mode in r.get("modes", {})]
        acc = sum(1 for r in sub if r["modes"][mode].get("accepted"))
        summary[mode] = {"accepted": acc, "total": len(sub),
                         "false_accept_rate": round(acc / len(sub) * 100, 1) if sub else 0.0}

    fam = {}
    for r in rows:
        f = fam.setdefault(r["family"], {"n": 0, "accepted_open": 0, "accepted_pinned": 0,
                                         "caught_by": {}})
        f["n"] += 1
        if r.get("modes", {}).get("open", {}).get("accepted"):
            f["accepted_open"] += 1
        if r.get("modes", {}).get("pinned", {}).get("accepted"):
            f["accepted_pinned"] += 1
        for cid in r.get("modes", {}).get("pinned", {}).get("failed_checks", []):
            f["caught_by"][cid] = f["caught_by"].get(cid, 0) + 1

    out = {"meta": {"generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "cases": len(rows),
                    "verifier": "uibc-core verify()",
                    "deterministic": True,
                    "note": "参数由索引决定，不用随机数；PASS 即视为被接受"},
           "summary": summary, "families": fam,
           "rows": rows}
    p = out_path
    os.makedirs(os.path.dirname(os.path.abspath(p)) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("cases=%d" % len(rows))
    for mode in ("open", "pinned", "head-pinned"):
        s = summary[mode]
        print("%-12s accepted %d/%d = %.1f%%" % (mode, s["accepted"], s["total"],
                                                 s["false_accept_rate"]))
    print("\n按族：")
    for k, v in sorted(fam.items()):
        print("  %-18s n=%-4d open_acc=%-3d pinned_acc=%-3d caught=%s"
              % (k, v["n"], v["accepted_open"], v["accepted_pinned"],
                 sorted(v["caught_by"].items(), key=lambda x: -x[1])[:6]))
    print("RESULT_JSON=" + p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

