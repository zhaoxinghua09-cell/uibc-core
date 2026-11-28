#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ERM 三族并进自测（外部尺子 → 本仓自己的语料）。

三个族不是这里的猜测，是 2026-11-27 用外部变异尺子（ERM）打本仓时
真跑出来的三个攻击面，此前 500 例语料里都没有：

  E1  seal-encoding   封签/公钥的 base64 换一种等价写法（去 padding、
                      urlsafe 字符、插入换行）。同一个字节串，不同写法；
                      验证器若"解码宽松"，就等于接受了未规范化输入。
  E2  merkle-double   删掉 Merkle 两个叶子的证明（size-2，root 不动；
                      或 root 也重算成剩下那批）。树与索引条数对不上。
  E3  trunc-recompute 截断尾部事件后，把 lifecycle_head **和**
                      checkpoint_head 都按剩余事件重算（自洽缩短，未封签）；
                      另加 E4 点文件：未声明文件改成点开头，验证 v2 对
                      `evidence/.lock` 的豁免是按名、不是按"点开头"。

E3 我原本预期**存活**（"包内没有东西能证明曾经更长"），实测**三例全被 S8 拦**：
S8 复算 checkpoint 用的字段比 manifest 记的更多，自洽缩短仍对不上。这一条已
按实测改写——预测错了就改预测，不留一句"预期存活"骗下一轮。回滚（换成更旧的
自洽包）才是真正只能靠外部钉 head 的那一类。

单独成文件、不并进 500 例：500 例的条数与族名被十来处断言与文档钉住，
重编号会让"同一批用例"失去可比性。这里另立一份 ERM 语料，逐例可比。

用法： python tools/corpus_erm.py [--out <path>]
默认输出 benchmarks/corpus/mutation-corpus-erm.json
"""
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mutation_benchmark as mb  # noqa: E402
from uibc_core import merkle as mk  # noqa: E402
from uibc_core import signing as us  # noqa: E402
from uibc_core.canonical import checkpoint_head  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

OUT = mb.OUT
BASE = mb.BASE
WORK = os.path.join(OUT, "_erm")
_j = mb._j
_w = mb._w


# ---------------------------------------------------------------- E1 encoding
def _b64_rewrite(path, field, how):
    o = _j(path)
    v = o.get(field)
    if not isinstance(v, str) or not v:
        raise ValueError("%s missing" % field)
    if how == "unpadded":
        v2 = v.rstrip("=")
    elif how == "urlsafe":
        v2 = v.replace("+", "-").replace("/", "_").rstrip("=")
    elif how == "wrapped":
        v2 = "\n".join(v[i:i + 16] for i in range(0, len(v), 16))
    elif how == "padded_extra":
        v2 = v + "==" if len(v) % 4 == 0 else v
    else:
        raise ValueError(how)
    if v2 == v:
        raise ValueError("alias is identical to the original (%s)" % how)
    o[field] = v2
    _w(path, o)


def mut_seal_encoding(field, how):
    def f(d):
        _b64_rewrite(os.path.join(d, "signatures", "seal.json"), field, how)
    return f


# ---------------------------------------------------------------- E2 merkle
def _index(d):
    """(path, raw, entries) of evidence/index.json, like outsider_audit._index."""
    p = os.path.join(d, "evidence", "index.json")
    with open(p, "rb") as f:
        raw = f.read()
    return p, raw, json.loads(raw.decode("utf-8")).get("entries", [])


def _build_merkle(d):
    path, raw, entries = _index(d)
    order = sorted(entries, key=lambda e: e.get("path", ""))
    leaves = []
    for e in order:
        fp = os.path.join(d, "evidence", e["path"])
        with open(fp, "rb") as fh:
            leaves.append(mk.leaf_hash(fh.read()))
    root = mk.root_hash(leaves)
    proofs = [{"index": i, "path": e["path"],
               "proof": list(mk.build_proof(leaves, i))}
              for i, e in enumerate(order)]
    _w(os.path.join(d, "evidence", "merkle.json"),
       {"algorithm": "rfc6962-sha256", "size": len(leaves),
        "root": root.hex(), "proofs": proofs})
    return leaves, root


def mut_merkle_double_delete(variant):
    def f(d):
        leaves, root = _build_merkle(d)
        mp = os.path.join(d, "evidence", "merkle.json")
        o = _j(mp)
        # drop two proofs, keep everything else as it was
        o["proofs"] = o["proofs"][:-2]
        if variant == "recompute":
            keep = leaves[:-2]
            o["size"] = len(keep)
            o["root"] = mk.root_hash(keep).hex()
        elif variant == "shrink-size-only":
            o["size"] = len(leaves) - 2
        elif variant in ("keep-all", "root-untouched"):
            pass  # only the proofs go; size and root still describe the full tree
        else:
            raise ValueError(variant)
        _w(mp, o)
    return f


# ------------------------------------------------------- E3 truncate+recompute
def mut_trunc_recompute(drop):
    def f(d):
        p = os.path.join(d, "lifecycle.json")
        o = _j(p)
        o["events"] = o.get("events", [])[:-drop]
        _w(p, o)
        sigdir = os.path.join(d, "signatures")
        if os.path.isdir(sigdir):
            shutil.rmtree(sigdir)
        mp = os.path.join(d, "manifest.json")
        m = _j(mp)
        if o.get("events"):
            m["lifecycle_head"] = o["events"][-1]["event_id"]
        # recompute the checkpoint the same way the builder does, from what is
        # left: a shortened package that is consistent with itself
        lc_head = o["events"][-1]["event_id"] if o.get("events") else None
        _p, _raw, entries = _index(d)
        m["checkpoint_head"] = checkpoint_head(
            lc_head, m.get("evidence_root"), m.get("evidence_index_digest"),
            len(entries))
        _w(mp, m)
    return f


def mut_dotfile(name):
    """A file the index never promised, hidden behind a dot.

    v2 exempts exactly `evidence/.lock` (the builder's advisory lock) by name.
    Dotfiles in general stay judged: a file renamed to .payload must not inherit
    that exemption. This family is the negative control for that exemption.
    """
    def f(d):
        with open(os.path.join(d, "evidence", name), "w", encoding="utf-8") as fh:
            fh.write("not evidence, just hidden\n")
    return f


def cases():
    out = []
    for field in ("signature", "public_key", "key_id"):
        if field == "key_id":
            continue  # key_id 不是 base64，换写法不是"等价别名"
        for how in ("unpadded", "urlsafe", "wrapped"):
            out.append(("E1-%s-%s" % (field, how), "seal-encoding",
                        "seal.%s 换成 %s 写法" % (field, how),
                        mut_seal_encoding(field, how)))
    for variant in ("root-untouched", "shrink-size-only", "recompute"):
        out.append(("E2-%s" % variant, "merkle-double",
                    "删两个叶子证明（%s）" % variant,
                    mut_merkle_double_delete(variant)))
    for drop in (1, 3, 5):
        out.append(("E3-drop%d" % drop, "trunc-recompute",
                    "截断 %d 条并把 lifecycle/checkpoint 都重算自洽" % drop,
                    mut_trunc_recompute(drop)))
    for name in (".payload", ".hidden.txt", "..conf"):
        out.append(("E4-%s" % name.replace(".", "dot").replace("_", ""),
                    "evidence-dotfile",
                    "evidence/%s（未声明，点开头）" % name,
                    mut_dotfile(name)))
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out_path = os.path.join(ROOT, "benchmarks", "corpus", "mutation-corpus-erm.json")
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]
    os.makedirs(WORK, exist_ok=True)
    mb.build_base()
    pub = us.ed_public_key(mb.DEMO_SEED)

    base = verify(BASE)
    if base["result"] not in ("PASS", "INCONCLUSIVE"):
        print("!! base package is %s; nothing below would mean anything"
              % base["result"], file=sys.stderr)
        return 1

    rows = []
    for cid, family, desc, fn in cases():
        d = os.path.join(WORK, "c_" + cid)
        if os.path.exists(d):
            shutil.rmtree(d)
        shutil.copytree(BASE, d)
        rec = {"id": cid, "family": family, "mutation": desc, "modes": {}}
        try:
            fn(d)
        except Exception as e:
            rec["error"] = str(e)[:120]
            rows.append(rec)
            continue
        for mode in ("open", "pinned"):
            kw = {"pubkey": pub} if mode == "pinned" else {}
            r = verify(d, **kw)
            checks = {c["id"]: c["result"] for c in r["checks"]}
            rec["modes"][mode] = {
                "verdict": r["result"],
                "failed_checks": [k for k, v in checks.items() if v == "FAIL"],
                "accepted": r["result"] == "PASS"}
        rows.append(rec)

    fam = {}
    for r in rows:
        f = fam.setdefault(r["family"], {"n": 0, "accepted_open": 0,
                                         "accepted_pinned": 0, "caught_by": {}})
        f["n"] += 1
        if r.get("modes", {}).get("open", {}).get("accepted"):
            f["accepted_open"] += 1
        if r.get("modes", {}).get("pinned", {}).get("accepted"):
            f["accepted_pinned"] += 1
        for cid in r.get("modes", {}).get("pinned", {}).get("failed_checks", []):
            f["caught_by"][cid] = f["caught_by"].get(cid, 0) + 1

    doc = {
        "meta": {"generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "cases": len(rows), "verifier": "uibc-core verify()",
                 "origin": "ERM (Escape-Rate Matrix) measured 2026-11-27",
                 "note": "three ERM families the 500-case corpus did not carry, "
                         "plus a dotfile negative control for the .lock exemption"},
        "families": fam, "rows": rows}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("cases=%d" % len(rows))
    for k, v in sorted(fam.items()):
        print("  %-16s n=%-3d open_acc=%-2d pinned_acc=%-2d caught=%s"
              % (k, v["n"], v["accepted_open"], v["accepted_pinned"],
                 sorted(v["caught_by"].items(), key=lambda x: -x[1])[:5]))
    print("RESULT_JSON=" + out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
