#!/usr/bin/env python3
"""render_passport_matrix.py — 由 docs/PASSPORT-MATRIX.json 生成 MD 与看板

单一真源是 JSON：--run 重写 JSON，--write 重渲 MD/BOARD，--check 只校验三者一致。
  python tools/render_passport_matrix.py --write
  python tools/render_passport_matrix.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
J_PATH = DOCS / "PASSPORT-MATRIX.json"
MD_PATH = DOCS / "PASSPORT-MATRIX.md"
HTML_PATH = DOCS / "PASSPORT-MATRIX-BOARD.html"

SHORT = {
    "APS (IETF draft-pidlisnyi-aps)": "APS（IETF）",
    "APIS v2.1 (Passport Alliance)": "APIS v2.1",
    "AIP (IETF draft-singla) did:aip": "AIP·singla",
    "AIP (IETF draft-prakash) aip:web": "AIP·prakash",
    "AIAgentMark v1.0 (个人自持)": "AIAgentMark",
}
MARK = {"PASS": "●", "JUDGE": "◐", "UNKNOWN": "○", "FAIL": "✕"}
COLOR = {"PASS": "#3fb950", "JUDGE": "#d29922", "UNKNOWN": "#98a4b3", "FAIL": "#f85149"}
BG = {"PASS": "background:#122117;color:#3fb950;border:1px solid #2a4a2f",
      "JUDGE": "background:#1f1a10;color:#d29922;border:1px solid #4a3a1a",
      "UNKNOWN": "background:#171d25;color:#98a4b3;border:1px solid #2a323d",
      "FAIL": "background:#1f1315;color:#f85149;border:1px solid #4a2a2a"}


def load():
    j = json.loads(J_PATH.read_text(encoding="utf-8"))
    j["json_sha256_16"] = hashlib.sha256(
        json.dumps({k: v for k, v in j.items() if k != "json_sha256_16"},
                   ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    return j


def render_md(j) -> str:
    t = j["totals"]
    hdr = "| 体系 | " + " | ".join(f"C{i+1}" for i in range(len(j["checks"]))) + " |"
    sep = "|---|" + "---|" * len(j["checks"])
    rows = []
    for s in j["systems"]:
        cells = []
        for c in j["checks"]:
            r = next((x for x in j["results"] if x["system"] == s and x["check"] == c), None)
            cells.append(MARK[r["verdict"]] if r else "—")
        rows.append(f"| {SHORT[s]} | " + " | ".join(cells) + " |")
    env = j.get("env", {})
    lines = [
        "# 五方护照对照：实测表", "",
        f"生成时间：{j['generated_at']}　·　JSON sha256[:16] `{j['json_sha256_16']}`", "",
        "**这张表此前没有人做过。** 原因是五套规范里只有一家提供可安装的第三方实现。", "",
        "## 一、总表", "", hdr, sep, *rows, "",
        f"合计 **{t['PASS']} ● / {t['JUDGE']} ◐ / {t['UNKNOWN']} ○ / {t['FAIL']} ✕**，"
        f"共 {len(j['results'])} 项判读。", "",
        "**图例**：● 实测通过　◐ 依规范可判、未能实测　○ 规范内无解析入口 / 不可判定　✕ 缺该功能", "",
        "## 二、六项检查是什么意思", "",
        "- **C1 签名可离线验**：拿凭证 + 签发公钥，不联网能否验通。",
        "- **C2 内容绑定**：改一个字段，验签是否必然失败。",
        "- **C3 规范化确定**：键序打乱后规范串是否一致（JCS 是否写死）。",
        "- **C4 标识可解析**：只给标识串，无上下文能否解析出文档。",
        "- **C5 吊销可追**：吊销是否是一条第三方可验的证据，而非后台数据库里的记录。",
        "- **C6 第三方可跑**：有没有别人能装、能跑的东西（有实现≠有测试，但没实现一定没第三方测试）。", "",
        "## 三、逐条判读", "",
        "| 体系 | 检查 | 判读 | 依据 |", "|---|---|---|---|",
    ]
    for r in j["results"]:
        lines.append(f"| {SHORT[r['system']]} | {r['check']} | {MARK[r['verdict']]} | "
                     f"{r['detail'].replace('|', '/')} |")
    lines += ["", "## 四、自限（不藏）", "",
              f"1. {len(j['results'])} 项里只有 {t['PASS']} 项是实测，其余因对象无公开实现而无法实测；",
              "2. 只做 `example.com` 的 `.well-known` 试探，未扫任何私有端点；",
              "3. AIAgentMark 的 ● 为本仓库按白皮书 conformance 条款复现，非厂商实现，字段命名可能有细微出入；",
              "4. 未复核厂商自述的测试数字（APS 1,634 例、APIS 初始基线），只记“自发布”。", "",
              f"复跑：`python tools/passport_matrix.py --check`（离线）　"
              f"`--run`（联网重读，需 `pip install agent-passport-system`）", "",
              "环境：" + f"Python {env.get('python','?')} / agent-passport-system "
              f"{env.get('agent_passport_system','?')} / cryptography {env.get('cryptography','?')}", ""]
    return "\n".join(lines)


def render_html(j) -> str:
    t = j["totals"]
    head = "".join(f'<th style="text-align:center">C{i+1}</th>' for i in range(len(j["checks"])))
    body = ""
    for s in j["systems"]:
        tds = ""
        for c in j["checks"]:
            r = next((x for x in j["results"] if x["system"] == s and x["check"] == c), None)
            tds += (f'<td style="text-align:center;{BG[r["verdict"]]}">'
                    f'<span style="font-size:16px">{MARK[r["verdict"]]}</span></td>') if r else "<td>—</td>"
        body += f"<tr><td><b>{SHORT[s]}</b></td>{tds}</tr>\n"
    det = ""
    for r in j["results"]:
        det += (f'<tr><td>{SHORT[r["system"]]}</td>'
                f'<td style="color:{COLOR[r["verdict"]]}">{MARK[r["verdict"]]} '
                f'{r["check"].split("（")[0]}</td>'
                f'<td style="color:#98a4b3;font-size:12.5px">{r["detail"]}</td></tr>\n')
    legend = "".join(f'<span style="color:{COLOR[v]}">{MARK[v]} {n}</span>' for v, n in t.items())
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>五方护照对照 · 实测表</title><style>
body{{margin:0;background:#0e1116;color:#e6edf3;font:15px/1.6 -apple-system,"Segoe UI","PingFang SC",sans-serif}}
.wrap{{max-width:1040px;margin:0 auto;padding:32px 24px 60px}}
h1{{font-size:24px;margin:0 0 6px}} .sub{{color:#98a4b3;font-size:13px;margin-bottom:24px}}
h2{{font-size:17px;margin:32px 0 12px;padding-left:11px;border-left:3px solid #58a6ff}}
table{{width:100%;border-collapse:collapse;font-size:13.5px;background:#151a22;border:1px solid #232b36;margin:8px 0}}
th,td{{padding:8px 10px;border:1px solid #232b36;vertical-align:top}}
th{{background:#1b222c;font-size:12.5px;color:#c9d4e0}}
.legend{{display:flex;gap:18px;font-size:13px;margin:10px 0 0;flex-wrap:wrap}}
.note{{color:#98a4b3;font-size:13px;margin:10px 0}}
.hl{{background:#141d16;border:1px solid #2a4a2f;border-radius:10px;padding:16px 18px;margin:14px 0}}
code{{background:#1b222c;padding:1px 5px;border-radius:4px;font-size:12.5px}}
</style></head><body><div class="wrap">
<h1>五方护照对照 · 实测表</h1>
<div class="sub">{j['generated_at']} · {len(j['results'])} 条判读 · JSON sha256[:16] <code>{j['json_sha256_16']}</code></div>
<div class="hl"><b>这张表此前没有人做过</b>——五套规范里只有一家（APS）提供可安装的第三方实现。
<br>同时也要看清：<b>{t['PASS']} 个 ● 只说明"这一项我们真的跑通了"，不能外推成"这家整体合格"。</b></div>
<h2>一、矩阵</h2>
<table><tr><th style="width:22%">体系</th>{head}</tr>
{body}</table>
<div class="legend">{legend}</div>
<h2>二、逐条判读（含依据）</h2>
<table><tr><th style="width:15%">体系</th><th style="width:14%">检查</th><th>判读依据</th></tr>
{det}</table>
<h2>三、自限</h2>
<div class="note">
1. 只有 {t['PASS']} 项是实测，其余因对象无公开实现而无法实测；<br>
2. 只做 <code>example.com</code> 的 <code>.well-known</code> 试探，未扫私有端点；<br>
3. AIAgentMark 的 ● 为本仓库按白皮书复现，非厂商实现；<br>
4. 未复核厂商自述测试数字，只记"自发布"。<br>
复跑：<code>python tools/passport_matrix.py --check</code>（离线） / <code>--run</code>（联网）。
</div>
</div></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if not J_PATH.exists():
        print("MISSING docs/PASSPORT-MATRIX.json")
        return 2
    j = load()
    md, html = render_md(j), render_html(j)

    if a.write:
        MD_PATH.write_text(md, encoding="utf-8", newline="\n")
        HTML_PATH.write_text(html, encoding="utf-8", newline="\n")
        print(f"WROTE {MD_PATH.name} ({len(md.encode())} B), {HTML_PATH.name} ({len(html.encode())} B), "
              f"json sha {j['json_sha256_16']}")
        return 0

    fails = []
    if not MD_PATH.exists() or MD_PATH.read_text(encoding="utf-8") != md:
        fails.append("PASSPORT-MATRIX.md 与 JSON 生成的版本不一致")
    if not HTML_PATH.exists() or HTML_PATH.read_text(encoding="utf-8") != html:
        fails.append("PASSPORT-MATRIX-BOARD.html 与 JSON 生成的版本不一致")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("OK passport matrix docs match the JSON")
    return 0


if __name__ == "__main__":
    sys.exit(main())
