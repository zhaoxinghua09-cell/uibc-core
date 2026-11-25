"""Render out/cross_impl.json into one self-contained HTML page.

Single file, no external links, JSON embedded — the same rule the review kanban
follows, so this page can be opened offline and audited without network access.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UIBC 双实现一致性矩阵 2026-11-25</title>
<style>
:root{--bg:#0f1115;--fg:#e8eaed;--dim:#9aa0a6;--ok:#34a853;--bad:#ea4335;--warn:#fbbc04;--card:#171a21}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--dim);margin-bottom:24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:28px}
.card{background:var(--card);border-radius:10px;padding:14px 16px}
.k{color:var(--dim);font-size:12px}
.v{font-size:24px;font-weight:600;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #23262e;font-size:13px}
th{color:var(--dim);font-weight:500}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.legend{color:var(--dim);margin:18px 0 8px;font-size:12px}
.note{background:var(--card);border-left:3px solid var(--warn);padding:12px 16px;border-radius:6px;margin:26px 0}
code{background:#20242c;padding:1px 5px;border-radius:4px}
</style></head><body><div class="wrap">
<h1>双实现一致性矩阵</h1>
<div class="sub">同一批磁盘字节喂两个验证器 · 语料 30 例 · as of 2026-11-25 · 数据内嵌，可离线打开</div>
<div class="cards" id="cards"></div>
<div class="legend">判定：<span class="ok">✓</span> 两实现一致；<span class="warn">▣</span> 覆盖缺口（该读者没有这项检查）；<span class="bad">✗</span> 同号不同力度或接受类分歧。</div>
<table><thead><tr><th>案例</th><th>模式</th><th>期望</th><th>参考</th><th>独立</th><th>首失败 参考/独立</th><th>分类</th></tr></thead>
<tbody id="rows"></tbody></table>
<div class="note">独立读者只有 V1–V10，覆盖 10/19 项检查；未覆盖 S9 S11 S13 S14 S15 S16 S17 S18 S19。两例真矛盾（S12 只重复条目、S10 闭包）说明“同号不同力度”比“缺检查”更难发现——所以本页不放行“跨实现验证”这个说法。</div>
</div>
<script>
const D = __DATA__;
const c = D.summary;
const cards = [
 ["案例", c.cases, ""], ["判定一致", c.verdict_agree + "/" + c.compared, c.verdict_agree === c.compared ? "ok" : "warn"],
 ["失败集一致", c.set_agree, c.set_agree === c.compared ? "ok" : "warn"],
 ["覆盖缺口", c.coverage_gap, "warn"], ["真矛盾", c.contradiction, c.contradiction ? "bad" : "ok"],
 ["接受类分歧", c.accept_divergence, c.accept_divergence ? "bad" : "ok"],
 ["覆盖检查", c.covered_checks + "/19", c.covered_checks === 19 ? "ok" : "bad"]
];
document.getElementById("cards").innerHTML = cards.map(([k,v,cls]) =>
 `<div class="card"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`).join("");
const kindMap = {agree:["ok","✓ 一致"], "coverage-gap":["warn","▣ 覆盖缺口"],
 "contradiction":["bad","✗ 同号不同力度"], "accept-divergence":["bad","✗ 接受类分歧"]};
document.getElementById("rows").innerHTML = D.rows.map(r => r.error
 ? `<tr><td>${r.case}</td><td colspan="6" class="bad">${r.error}</td></tr>`
 : `<tr><td>${r.case}</td><td>${r.mode||"—"}</td><td>${r.expected}</td><td>${r.ref}</td><td>${r.ind}</td>
    <td>${r.ref_first||"—"} / ${r.ind_first||"—"}</td>
    <td class="${kindMap[r.kind][0]}">${kindMap[r.kind][1]}</td></tr>`).join("");
</script></body></html>
"""


def main():
    data = json.load(open(os.path.join(REPO, "out", "cross_impl.json"), encoding="utf-8"))
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    out = os.path.join(REPO, "out", "cross_impl.html")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("wrote", out, len(html), "bytes; external refs:",
          sum(html.count(s) for s in ("http://", "https://")))


if __name__ == "__main__":
    main()
