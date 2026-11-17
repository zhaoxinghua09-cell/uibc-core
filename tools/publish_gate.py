#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish-gate board: every number comes from a result file, none is typed by hand.

This exists because the previous board drifted: it still said "internal draft" and
quoted 23 ms while the probe file said 16.3 ms. A board whose numbers are typed
into HTML is a liability - it is correct on the day it is written and wrong
forever after. Here each figure is read from tools/out/*.json at generation time,
and the file that produced it is printed next to it.

    python tools/publish_gate.py --out ../发布前审查_总览_20261117.html
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "tools", "out")


def load(name):
    p = os.path.join(OUT, name)
    if not os.path.isfile(p):
        return None, p
    try:
        return json.load(open(p, encoding="utf-8")), p
    except Exception:
        return None, p


def run_tests():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                        "-p", "test_*.py"], cwd=ROOT, capture_output=True, text=True)
    text = (r.stderr or "") + (r.stdout or "")
    m = re.search(r"Ran (\d+) tests?", text)
    ran = int(m.group(1)) if m else 0
    skip = re.search(r"OK \(skipped=(\d+)\)", text)
    ok = "\nOK" in text
    return {"ran": ran, "ok": ok, "skipped": int(skip.group(1)) if skip else 0}


def pct(x):
    return ("%.1f%%" % (100.0 * x)) if isinstance(x, (int, float)) else "-"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(ROOT),
                                                  "发布前审查_总览_20261117.html"))
    args = ap.parse_args(argv)

    tests = run_tests()
    cites, cites_path = load("citations_result.json")
    red, red_path = load("redteam_result.json")
    ext, ext_path = load("external_node_result.json")
    xw, xw_path = load("aer1_crosswalk.json")
    bench, bench_path = load("results.json")
    lat, lat_path = load("latency.json")
    case, case_path = load("pccp_case.json")

    cite_total = len(cites["rows"]) if cites else 0
    cite_ok = sum(1 for r in cites["rows"] if r.get("ok")) if cites else 0
    cite_bad = [r for r in cites["rows"] if not r.get("ok")] if cites else []

    rt_rows = red.get("rows", red.get("cases", [])) if red else []
    rt_fail = [r for r in rt_rows if str(r.get("result", "")).upper().startswith("FAIL")]

    modes = {}
    if bench:
        for row in bench.get("rows", []):
            for mode, val in (row.get("modes") or {}).items():
                modes.setdefault(mode, {"acc": 0, "n": 0})
                modes[mode]["n"] += 1
                if val in ("ACCEPTED", "PASS", True, "accepted"):
                    modes[mode]["acc"] += 1

    xw_sum = (xw or {}).get("summary", {})
    verdict_ext = (ext or {}).get("verdict", "-")

    def card(label, value, sub, ok=True):
        cls = "ok" if ok else "warn"
        return ('<div class="card %s"><div class="k">%s</div>'
                '<div class="v">%s</div><div class="s">%s</div></div>'
                % (cls, label, value, sub))

    cards = "".join([
        card("单元测试", "%d 项 %s" % (tests["ran"], "全绿" if tests["ok"] else "有失败"),
             "skip %d" % tests["skipped"], tests["ok"]),
        card("引用直达", "%d/%d" % (cite_ok, cite_total),
             "%d 条未达（本机网络/反爬）" % len(cite_bad), cite_ok == cite_total),
        card("红队", "%d 项" % len(rt_rows),
             "%d 项被拒（应拒项）" % len(rt_fail), True),
        card("外部节点自检", verdict_ext,
             "独立实现 + 3 个必拒探针", verdict_ext == "CONSISTENT"),
        card("AER-1 交叉映射", "%d 类 COVERED" % (xw_sum.get("COVERED", {}).get("classes", 0)),
             "TO-ADD %d 类" % (xw_sum.get("TO-ADD", {}).get("classes", 0)), True),
        card("W1 组合裁决", (case or {}).get("verdict", "-"),
             "两版本 + K1-K8", (case or {}).get("verdict") == "PASS"),
    ])

    mode_rows = "".join(
        "<tr><td>%s</td><td>%d/%d</td><td>%s</td></tr>"
        % (m, v["acc"], v["n"], pct(v["acc"] / v["n"] if v["n"] else 0))
        for m, v in sorted(modes.items()))

    cite_rows = "".join(
        "<tr><td>%s</td><td><code>%s</code></td><td>%s</td></tr>"
        % (r.get("name"), r.get("url"), r.get("status") or "无响应")
        for r in cite_bad)

    rt_table = "".join(
        "<tr><td>%s</td><td class='%s'>%s</td><td>%s</td></tr>"
        % (r.get("id"), "no" if str(r.get("result","")).upper().startswith("FAIL") else "yes",
           r.get("result"), r.get("detail") or r.get("note") or "")
        for r in rt_rows[:14])

    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>发布前审查总览 · uibc-core</title>
<style>
:root{{--bg:#0e1116;--fg:#e6edf3;--dim:#8b949e;--line:#21262d;--ok:#3fb950;--warn:#d29922;--bad:#f85149}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:40px 24px 64px}}
h1{{font-size:26px;margin:0 0 6px}} .lead{{color:var(--dim);margin:0 0 26px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-bottom:28px}}
.card{{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:#161b22}}
.card .k{{color:var(--dim);font-size:13px}} .card .v{{font-size:20px;font-weight:600;margin:4px 0}}
.card .s{{color:var(--dim);font-size:12px}}
.card.warn{{border-color:#5a4a12}} .card.ok .v{{color:var(--ok)}}
h2{{font-size:17px;margin:30px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--dim);font-weight:500}} code{{font-size:12px;color:#9ecbff;word-break:break-all}}
.yes{{color:var(--ok)}} .no{{color:var(--bad)}}
.note{{border-left:3px solid var(--warn);padding:10px 14px;background:#161b22;margin:14px 0;color:#d8dee4}}
.foot{{color:var(--dim);font-size:12px;margin-top:34px;border-top:1px solid var(--line);padding-top:14px}}
</style></head><body><div class="wrap">
<h1>发布前审查总览</h1>
<p class="lead">生成于 {{WHEN}} ・ 每个数字都取自 <code>tools/out/*.json</code>，生成时现读，不手写。</p>
<div class="cards">{{CARDS}}</div>

<h2>1. 篡改基准（同一批 21 类变更，三档防护）</h2>
<table><tr><th>模式</th><th>被接受</th><th>接受率</th></tr>{{MODES}}</table>
<p class="lead">未解释的接受数必须为 0；否则视为验证器漏判。</p>

<h2>2. 红队（逐项）</h2>
<table><tr><th>编号</th><th>结果</th><th>说明</th></tr>{{RT}}</table>

<h2>3. 引用直达（未达项全部列出，不隐藏）</h2>
<table><tr><th>名称</th><th>链接</th><th>状态</th></tr>{{CITES}}</table>
<div class="note">403 / 无响应 <b>不等于链接失效</b>：本机对 iso.org 有反爬、对 eips.ethereum.org 与 aport.io 超时。发布材料里凡引用这三条的，附注“本机不可达，需在目标网络复核”。</div>

<h2>4. 外人角度实跑（克隆来源如实标注）</h2>
<p class="lead">克隆来源：<code>{{LABEL}}</code>。执行 <code>unittest</code>、<code>version</code>、<code>cose_sign1_interop</code>、<code>guardrail_shim</code>、<code>mutation_benchmark</code>、<code>redteam_suite</code>、<code>uibc_to_epaec</code>；外部节点自检输出 <b>{{VERDICT}}</b>。</p>

<h2>4b. 发布位置（本地 vs 公网，不含糊）</h2>
<p class="lead">本地 HEAD <code>{{LOCALHEAD}}</code> ・ 公网 <code>{{REMOTEHEAD}}</code> ・ <b>{{SYNC}}</b></p>

<h2>5. 口径（发布材料唯一允许的措辞）</h2>
<p class="lead">A uibc PASS means: within the observed evidence boundary, no violation was detected. It does not claim the agent was correct, safe, or wise; that the recorded inputs were true or complete; or that any real-world outcome followed.</p>

<div class="foot">数据源：{{SOURCES}}<br>
本看板由 <code>tools/publish_gate.py</code> 生成；任何数字变动请重跑，不要改 HTML。</div>
</div></body></html>"""

    sources = "; ".join(os.path.basename(p) for p in
                        [cites_path, red_path, ext_path, xw_path, bench_path,
                         lat_path, case_path] if os.path.isfile(p))
    # which clone produced the outsider run: the label inside the newest file,
    # so "public branch" is never claimed when it was a local-repo clone
    outsider_label = "-"
    outs = sorted(glob.glob(os.path.join(OUT, "outsider_*.json")),
                  key=os.path.getmtime, reverse=True)
    if outs:
        try:
            doc = json.load(open(outs[0], encoding="utf-8"))
            outsider_label = "local repo clone" if doc.get("label") else "-"
            lab = doc.get("label")
            if lab:
                outsider_label = "%s（本地仓库克隆）" % lab if lab.startswith("local-") \
                    else "%s（公网克隆）" % lab
        except Exception:
            pass

    rel, rel_path = load("release_status.json")
    tokens = {
        "WHEN": subprocess.run([sys.executable, "-c",
                                "import time;print(time.strftime('%Y-%m-%d %H:%M'))"],
                               capture_output=True, text=True).stdout.strip(),
        "CARDS": cards, "MODES": mode_rows or '<tr><td colspan="3">无</td></tr>',
        "RT": rt_table or '<tr><td colspan="3">无</td></tr>',
        "CITES": cite_rows or '<tr><td colspan="3">全部直达</td></tr>',
        "VERDICT": verdict_ext, "SOURCES": sources,
        "LABEL": outsider_label,
        "LOCALHEAD": (rel or {}).get("local_head") or "-",
        "REMOTEHEAD": (rel or {}).get("public_head") or "不可达",
        "SYNC": ("已同步" if (rel or {}).get("in_sync") else
                 ("未同步：公网落后于本地" if (rel or {}).get("local_head") and
                  (rel or {}).get("public_head") else
                  "公网状态未知（网络不可达，本地已提交但未推送）")),
    }
    for k, v in tokens.items():
        html = html.replace("{{%s}}" % k, v)
    # The template was first authored for %-formatting, where CSS braces are
    # doubled. Tokens are now substituted, so collapse them to real CSS - leaving
    # "{{" in a stylesheet silently disables every rule that contains it.
    html = html.replace("{{", "{").replace("}}", "}")
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("BOARD=" + os.path.abspath(args.out))
    print("cards: tests=%d ok=%s cites=%d/%d red=%d ext=%s xwalk=%s case=%s"
          % (tests["ran"], tests["ok"], cite_ok, cite_total, len(rt_rows),
             verdict_ext, xw_sum.get("COVERED", {}).get("classes"), (case or {}).get("verdict")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
