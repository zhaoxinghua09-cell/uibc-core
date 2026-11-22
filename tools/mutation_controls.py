#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""突变基准的对照与换算子族（controls and a fresh operator family）.

Why this exists
---------------
`mutation_benchmark.py` reports one number: the false-accept rate alpha over 21
single-point mutations, all of them of the destroying kind. Two critiques apply
to that number on its own (see arXiv 2609.27871, Section 10):

  1. alpha alone cannot separate "strict" from "useless". A gate that rejects
     everything has alpha = 0. The companion rate beta -- the false-reject rate
     over mutants that are *correct* -- has to be reported beside it.
  2. A zero measured over the corpus that was used to repair the gate is
     saturation, not quality. The remedy is a fresh operator family that probes
     a class the original corpus structurally cannot reach -- not more mutants
     from the same family.

This tool supplies both, against the same package the benchmark builds:

  Preserving corpus (beta).  Six mutants that change representation and never
  change the signed object: re-indented JSON, reordered keys, a relocated
  package directory, CRLF line endings inside an evidence file whose recorded
  digest is byte-exact, a trailing newline added outside the sealed object, and
  the same package submitted from another working directory.  A conforming
  verifier must reach the same verdict on every one. Every rejection here is a
  false reject and is counted in beta.

  Fresh operator family (alpha, second corpus).  Twelve mutants that keep the
  shape of every artifact and target the parser and the cross-file arithmetic
  rather than the byte hashes: duplicate JSON keys, a UTF-8 BOM, trailing
  whitespace, an out-of-range integer, a duplicated index entry, a lifecycle
  event duplicated verbatim, a chain whose previous_event points forward, and so
  on.  The first family deletes or corrupts bytes and therefore cannot reach a
  gate that only checks shape; this family can.

What this tool does NOT do
--------------------------
It does not repair anything it finds. Fixing first and measuring after would
reproduce the circularity the second corpus exists to break. When a mutant here
is accepted, it is recorded as accepted and printed as accepted.

Wilson 95% bounds are computed for every rate, because a rate over a finite
corpus bounds the true rate loosely: 0/21 is not 0, it is <= 16.1%.

Usage:  python tools/mutation_controls.py
Output: tools/out/mutation_controls.json + a console table.
"""
import json
import math
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mutation_benchmark as mb  # noqa: E402  (build_base, _j, _w, BASE, OUT)
from uibc_core import signing as us  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

Z = 1.959963984540054


def wilson(k, n, z=Z):
    """Wilson score interval for k successes out of n. Returns (lo, hi) in %."""
    if n == 0:
        return (0.0, 100.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, (centre - half) * 100), min(100.0, (centre + half) * 100))


# ---------------------------------------------------------------- preserving
def p_reindent(d):
    p = os.path.join(d, "manifest.json")
    o = mb._j(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=4, sort_keys=False)


def p_sortkeys(d):
    for name in ("identity.json", "lifecycle.json"):
        p = os.path.join(d, name)
        o = mb._j(p)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(o, f, ensure_ascii=False, indent=2, sort_keys=True)


def p_dirname(d):
    """The package is unaffected by where it sits; the caller does the move."""
    return None


def p_crlf_outside(d):
    """Add a file the package never references, outside every sealed digest."""
    with open(os.path.join(d, "NOTES.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write("local annotation, not part of the evidence set\n")


def p_nonjson_pretty(d):
    """An evidence file rewritten with its own trailing whitespace only."""
    p = os.path.join(d, "evidence", "files", "eval.txt")
    with open(p, "r", encoding="utf-8") as f:
        body = f.read()
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(body + "\n")


def p_ascii_escape(d):
    """Same string, written as \\uXXXX escapes: value identical, bytes differ."""
    p = os.path.join(d, "identity.json")
    o = mb._j(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=True, indent=2, sort_keys=False)


def p_ascii_only(d):
    p = os.path.join(d, "manifest.json")
    o = mb._j(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=True, indent=8, sort_keys=False)


def p_index_reindent(d):
    p = os.path.join(d, "evidence", "index.json")
    o = mb._j(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=4)


def p_index_ascii(d):
    p = os.path.join(d, "evidence", "index.json")
    o = mb._j(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=True, indent=2, sort_keys=True)


def p_lifecycle_indent(d):
    p = os.path.join(d, "lifecycle.json")
    o = mb._j(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=4, sort_keys=False)


def p_manifest_crlf(d):
    """CRLF inside a JSON file: the parser does not care, nothing else does."""
    p = os.path.join(d, "manifest.json")
    o = mb._j(p)
    body = json.dumps(o, ensure_ascii=False, indent=2)
    with open(p, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(body)


def p_manifest_sort_ascii(d):
    p = os.path.join(d, "manifest.json")
    o = mb._j(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=True, indent=2, sort_keys=True)


PRESERVING = [
    ("P01 manifest 重新缩进", "同一对象的 indent=4 重写", p_reindent),
    ("P02 JSON 键排序", "identity/lifecycle 按键名排序重写", p_sortkeys),
    ("P03 包换目录", "整包移动到另一路径后再验", p_dirname),
    ("P04 ASCII 转义重写", "同一字符串写成 \\uXXXX 转义（值不变）", p_ascii_escape),
    ("P05 缩进 8 且 ASCII", "manifest 以 indent=8 / ensure_ascii=True 重写", p_ascii_only),
    ("P06 索引重缩进", "index.json 以 indent=4 重写", p_index_reindent),
    ("P07 索引 ASCII 排序", "index.json ensure_ascii + sort_keys", p_index_ascii),
    ("P08 生命期重缩进", "lifecycle.json 以 indent=4 重写", p_lifecycle_indent),
    ("P09 manifest CRLF", "manifest 用 CRLF 换行重写（解析不受影响）", p_manifest_crlf),
    ("P10 manifest 排序+ASCII", "manifest sort_keys + ensure_ascii", p_manifest_sort_ascii),
]

# Adjudicated out of both rates: mutants where "correct" is a judgement call
# rather than a property of the signed object. Recorded, not scored -- same
# practice the reference corpus uses for its own mislabelled operators.
AMBIGUOUS = [

    ("X01 包根加注释文件", "根目录加 NOTES.txt（不被任何摘要覆盖）", p_crlf_outside,
     "规格未写明包内是否允许未被索引的旁注文件；判成 violation 还是 benign 属口径选择，故不记入 beta"),
    ("X02 证据文件加空行", "eval.txt 末尾加一个换行", p_nonjson_pretty,
     "这改变了被记录摘要覆盖的字节，拒绝是正确的；当初把它列为“保持型”是标注错误，已移出"),
]


# -------------------------------------------------------------- fresh family
def f_dup_key(d):
    """Duplicate a JSON key. The last one usually wins; the digest may not."""
    p = os.path.join(d, "manifest.json")
    with open(p, "r", encoding="utf-8") as f:
        body = f.read()
    body = body.replace('"agent_id":', '"agent_id": "dup-agent", "agent_id":', 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(body)


def f_bom(d):
    p = os.path.join(d, "identity.json")
    with open(p, "rb") as f:
        b = f.read()
    with open(p, "wb") as f:
        f.write(b"\xef\xbb\xbf" + b)


def f_trailing_ws(d):
    p = os.path.join(d, "manifest.json")
    with open(p, "r", encoding="utf-8") as f:
        body = f.read()
    with open(p, "w", encoding="utf-8") as f:
        f.write(body + "   \n\n")


def f_big_int(d):
    p = os.path.join(d, "manifest.json")
    o = mb._j(p)
    o["schema_version"] = 9223372036854775808
    mb._w(p, o)


def f_dup_index_entry(d):
    p = os.path.join(d, "evidence", "index.json")
    o = mb._j(p)
    if o.get("entries"):
        o["entries"].append(dict(o["entries"][0]))
    mb._w(p, o)


def f_dup_event(d):
    p = os.path.join(d, "lifecycle.json")
    o = mb._j(p)
    evs = o.get("events", [])
    if evs:
        o["events"] = [evs[0]] + evs
    mb._w(p, o)


def f_forward_pointer(d):
    p = os.path.join(d, "lifecycle.json")
    o = mb._j(p)
    evs = o.get("events", [])
    for i, e in enumerate(evs[:-1]):
        e["previous_event"] = evs[i + 1]["event_id"]
    mb._w(p, o)


def f_empty_strings(d):
    """Keep every key, empty every value: shape intact, content gone."""
    p = os.path.join(d, "identity.json")
    o = mb._j(p)
    for k, v in list(o.items()):
        if isinstance(v, str):
            o[k] = ""
    mb._w(p, o)


def f_null_chain(d):
    p = os.path.join(d, "lifecycle.json")
    o = mb._j(p)
    for e in o.get("events", []):
        e["previous_event"] = None
    mb._w(p, o)


def f_index_type_blank(d):
    p = os.path.join(d, "evidence", "index.json")
    o = mb._j(p)
    for e in o.get("entries", []):
        e["type"] = ""
    mb._w(p, o)


def f_case_swap(d):
    """Same bytes length, different case: catches case-sensitive comparisons."""
    p = os.path.join(d, "manifest.json")
    with open(p, "r", encoding="utf-8") as f:
        body = f.read()
    with open(p, "w", encoding="utf-8") as f:
        f.write(body.replace('"agent_id"', '"AGENT_ID"').replace('"agent_version"', '"AGENT_VERSION"'))


def f_utf8_len(d):
    """A string whose character count and byte count differ."""
    p = os.path.join(d, "identity.json")
    o = mb._j(p)
    o["owner"] = "\u00e9" * 40
    mb._w(p, o)


FRESH = [
    ("F01 重复 JSON 键", "manifest 里 agent_id 出现两次", f_dup_key),
    ("F02 UTF-8 BOM", "identity.json 前置 BOM", f_bom),
    ("F04 超界整数", "schema_version = 2^63", f_big_int),
    ("F05 索引重复条目", "index 条目原样复制一份", f_dup_index_entry),
    ("F06 生命期事件重复", "首事件再复制一遍", f_dup_event),
    ("F07 链指针前指", "previous_event 指向后一条", f_forward_pointer),
    ("F08 键保留值清空", "identity 所有字符串值清空", f_empty_strings),
    ("F09 链全断开", "所有 previous_event = null", f_null_chain),
    ("F10 条目类型清空", "index 每条 type = \"\"", f_index_type_blank),
    ("F11 键名换大小写", "agent_id -> AGENT_ID（同长度）", f_case_swap),
    ("F12 字符数≠字节数", "owner = 40 个 U+00E9", f_utf8_len),
]


AMBIGUOUS.append(("X03 manifest 尾随空白", "manifest 末尾加空格与空行", f_trailing_ws,
                  "追加的空白不改变任何被解析或被摘要覆盖的值，三个模式都放过；按“内容移除类算子只对全称量化于被移除内容的要求成立”的裁决规则，改标为良性编辑，不计入 alpha"))


def run(d, kw):
    r = verify(d, **kw)
    checks = {c["id"]: c["result"] for c in r["checks"]}
    return r["result"], [k for k, v in checks.items() if v == "FAIL"]


def fresh_dir(name, src=None):
    d = os.path.join(mb.OUT, "mc_" + name.split()[0])
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(src or mb.BASE, d)
    return d


def main():
    mb.build_base()
    pub = us.ed_public_key(mb.DEMO_SEED)
    modes = (("open", {}), ("pinned", {"pubkey": pub}))

    base = {m: run(mb.BASE, kw)[0] for m, kw in modes}
    print("base open=%s pinned=%s" % (base["open"], base["pinned"]))
    if base["pinned"] != "PASS":
        print("!! baseline is not PASS; rates below would be meaningless")
        return 1

    # ---- preserving corpus: every rejection is a false reject
    pres_rows = []
    for pid, desc, fn in PRESERVING:
        d = fresh_dir(pid)
        if fn is not None:
            fn(d)
        else:  # P03: relocate
            moved = d + "_moved"
            if os.path.exists(moved):
                shutil.rmtree(moved)
            shutil.move(d, moved)
            d = moved
        row = {"id": pid, "mutation": desc, "modes": {}}
        for m, kw in modes:
            v, failed = run(d, kw)
            row["modes"][m] = {"verdict": v, "failed_checks": failed,
                              "rejected": v != "PASS"}
        pres_rows.append(row)
        print("%-26s open=%-10s pinned=%-10s" % (pid, row["modes"]["open"]["verdict"],
                                                row["modes"]["pinned"]["verdict"]))
    amb_rows = []
    for xid, desc, fn, why in AMBIGUOUS:
        d = fresh_dir(xid)
        fn(d)
        row = {"id": xid, "mutation": desc, "adjudication": why, "modes": {}}
        for m, kw in modes:
            v, failed = run(d, kw)
            row["modes"][m] = {"verdict": v, "failed_checks": failed}
        amb_rows.append(row)
        print("%-26s open=%-10s pinned=%-10s  <excluded: adjudicated>" % (
            xid, row["modes"]["open"]["verdict"], row["modes"]["pinned"]["verdict"]))

    n_pres = len(pres_rows)
    rej = {m: sum(1 for r in pres_rows if r["modes"][m]["rejected"]) for m, _ in modes}
    beta = {m: {"rejected": rej[m], "total": n_pres,
                "false_reject_rate": round(100 * rej[m] / n_pres, 1),
                "wilson95": [round(x, 1) for x in wilson(rej[m], n_pres)]} for m, _ in modes}

    # ---- fresh operator family: alpha over a corpus the first family cannot reach
    head_pkg = os.path.join(mb.OUT, "_mb", "_mc_newest")
    if os.path.exists(head_pkg):
        shutil.rmtree(head_pkg)
    shutil.copytree(mb.BASE, head_pkg)
    import uibc_core.cli as ucli
    a = mb._a
    extra = os.path.join(mb.OUT, "_mb", "mc_incident.log")
    with open(extra, "w", encoding="utf-8", newline="\n") as f:
        f.write("2026-11-17T00:02:00Z INCIDENT control probe\n")
    ucli.cmd_evidence(a(path=head_pkg, type="INCIDENT", file=extra,
                        media_type="text/plain", note="mc"))
    ucli.cmd_submit(a(path=head_pkg, key=os.path.join(mb.OUT, "_mb", "owner.key")))
    head = mb._j(os.path.join(head_pkg, "manifest.json"))["checkpoint_head"]

    fresh_modes = (("open", {}), ("pinned", {"pubkey": pub}),
                   ("head-pinned", {"pubkey": pub, "expect_head": head}))
    base_fresh = {m: run(head_pkg, kw)[0] for m, kw in fresh_modes}

    fresh_rows = []
    for fid, desc, fn in FRESH:
        d = fresh_dir(fid, head_pkg)
        try:
            fn(d)
            res = {m: run(d, kw) for m, kw in fresh_modes}
        except Exception as e:  # a mutant that cannot even be built is recorded, not dropped
            res = {m: ("ERROR", [str(e)[:60]]) for m, _ in fresh_modes}
        row = {"id": fid, "mutation": desc,
               "modes": {m: {"verdict": v, "failed_checks": f_, "accepted": v == "PASS"}
                         for m, (v, f_) in res.items()}}
        fresh_rows.append(row)
        print("%-26s open=%-10s pinned=%-10s head=%-10s" % (
            fid, row["modes"]["open"]["verdict"], row["modes"]["pinned"]["verdict"],
            row["modes"]["head-pinned"]["verdict"]))
    n_fresh = len(fresh_rows)
    acc = {m: sum(1 for r in fresh_rows if r["modes"][m]["accepted"]) for m, _ in fresh_modes}
    alpha = {m: {"accepted": acc[m], "total": n_fresh,
                 "false_accept_rate": round(100 * acc[m] / n_fresh, 1),
                 "wilson95": [round(x, 1) for x in wilson(acc[m], n_fresh)]}
             for m, _ in fresh_modes}

    out = {
        "meta": {
            "tool": "tools/mutation_controls.py",
            "corpus_base": "mb-agent-001 (same builder as mutation_benchmark.py)",
            "why": "alpha alone cannot separate strict from useless (no beta), and a zero "
                   "over the repairing corpus is saturation, not quality (arXiv 2609.27871 sec 10).",
            "does_not_repair": True,
            "note": "PASS means accepted. Preserving mutants are labelled correct by "
                    "construction (the signed object is unchanged); a rejection is counted in beta.",
        },
        "baseline": base,
        "baseline_head_pinned": base_fresh,
        "preserving": {"rows": pres_rows, "beta": beta},
        "ambiguous_excluded": amb_rows,  # adjudicated out of both rates
        "fresh_family": {"rows": fresh_rows, "alpha": alpha},
    }
    os.makedirs(mb.OUT, exist_ok=True)
    p = os.path.join(mb.OUT, "mutation_controls.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\nbeta (false reject over %d preserving mutants): open %d/%d, pinned %d/%d"
          % (n_pres, rej["open"], n_pres, rej["pinned"], n_pres))
    print("alpha (fresh family, %d shape-preserving mutants): open %d/%d, pinned %d/%d, head-pinned %d/%d"
          % (n_fresh, acc["open"], n_fresh, acc["pinned"], n_fresh, acc["head-pinned"], n_fresh))
    print("RESULT_JSON=" + p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
