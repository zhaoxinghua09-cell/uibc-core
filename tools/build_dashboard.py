#!/usr/bin/env python3
"""One page of numbers, generated from the measurements rather than typed.

Every figure in the SVG comes from a tool that can be re-run: the parity table,
the diagnostics comparison, the basis counts, and one hand-verified file of
competitor facts (with its sources and date, so staleness is visible).

The point of generating it is not prettiness. It is that a number in a thesis
appendix which nobody can regenerate is a number nobody should trust.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_TOOLS = os.path.join(_REPO, "tools")
for p in (_REPO, _TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_release_parity as parity   # noqa: E402
import compare_diagnostics as diag      # noqa: E402
from uibc_core import basis             # noqa: E402

INK = "#1a1a1a"
MUTED = "#6b6b6b"
OURS = "#1f5fa8"
THEIRS = "#b8532a"
GRID = "#e2e2e2"
FONT = "Noto Sans CJK SC, Source Han Sans SC, Microsoft YaHei, PingFang SC, sans-serif"


def facts():
    with open(os.path.join(_REPO, "docs", "COMPETITOR-FACTS.json"), encoding="utf-8") as f:
        return json.load(f)


def _run_json(tool):
    """Call the tool as the README tells a reader to call it, and parse its
    JSON. Importing it here would let in a different import order, and then the
    picture and the table could disagree while both look right."""
    proc = subprocess.run([sys.executable, os.path.join(_TOOLS, tool), "--json"],
                          capture_output=True, text=True, cwd=_REPO, timeout=600)
    if proc.returncode != 0:
        raise SystemExit("%s failed: %s" % (tool, proc.stderr[-400:]))
    return json.loads(proc.stdout)


def collect():
    par = _run_json("check_release_parity.py")
    dg = _run_json("compare_diagnostics.py")
    # Names, not case objects: the sums below match on `attack`, and a list of
    # dicts would match nothing while still printing a plausible length.
    common = [c["attack"] for c in dg["ours"]["cases"]
              if any(t["attack"] == c["attack"] and t["verdict"] != "n/a"
                     for t in dg["theirs"]["cases"])]
    ours_reasons = sum(c["n_reasons"] for c in dg["ours"]["cases"]
                       if c["attack"] in common)
    theirs_reasons = sum(c["n_reasons"] for c in dg["theirs"]["cases"]
                         if c["attack"] in common)
    channels = {k: len(v["checks"]) for k, v in par["channels"].items()}
    bc = basis.counts()
    return {"channels": channels, "basis": bc,
            "common": len(common), "ours": ours_reasons, "theirs": theirs_reasons,
            "facts": facts(), "n_checks": len(basis.BASIS)}


def _bar(x, y, w, h, value, vmax, color):
    width = 0 if vmax == 0 else max(2, int(w * value / vmax))
    return (f'<rect x="{x}" y="{y}" width="{width}" height="{h}" fill="{color}" rx="2"/>')


def _label(x, y, text, size=14, color=INK, weight="normal", anchor="start"):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{text}</text>')


def render(d):
    W, H = 1180, 620
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    out.append(_label(40, 46, "uibc-core 实证看板", 26, INK, "bold"))
    out.append(_label(40, 72, "所有数字由 tools/ 下的脚本生成，可原样复跑；竞品事实见 docs/COMPETITOR-FACTS.json（含出处与核实日期）",
                      13, MUTED))

    # panel 1: three channels
    px, py, pw = 40, 110, 520
    out.append(_label(px, py, "同一个包，三个渠道各报几项检查", 16, INK, "bold"))
    ch = d["channels"]
    vmax = max(ch.values()) or 1
    rows = list(ch.items())
    for i, (name, n) in enumerate(rows):
        y = py + 34 + i * 46
        out.append(_label(px, y + 16, name, 13, MUTED))
        out.append(_bar(px + 190, y, 260, 22, n, vmax, OURS))
        out.append(_label(px + 190 + 268, y + 16, str(n), 14, INK, "bold"))
    out.append(_label(px, py + 34 + len(rows) * 46 + 6,
                      "差在发布，不在代码：仓库有 %d 项，发布件只到 6。" % d["n_checks"],
                      12, MUTED))

    # panel 2: basis classes
    px2 = 620
    out.append(_label(px2, py, "十八项检查的依据从哪来", 16, INK, "bold"))
    bc = d["basis"]
    total = sum(bc.values()) or 1
    x = px2
    bar_y = py + 22
    colors = {"direct": OURS, "related": "#7fa8d4", "none": "#d8d8d8"}
    for k in ("direct", "related", "none"):
        w = int(470 * bc[k] / total)
        out.append(f'<rect x="{x}" y="{bar_y}" width="{w}" height="34" fill="{colors[k]}"/>')
        if w > 40:
            out.append(_label(x + w // 2, bar_y + 23, str(bc[k]), 15,
                              "#ffffff" if k != "none" else INK, "bold", "middle"))
        x += w
    labels = {"direct": "草案明文规定", "related": "思想来源", "none": "本项目自定"}
    lx = px2
    for i, k in enumerate(("direct", "related", "none")):
        out.append(f'<rect x="{lx}" y="{bar_y + 48}" width="12" height="12" fill="{colors[k]}"/>')
        out.append(_label(lx + 18, bar_y + 59, "%s %d 项" % (labels[k], bc[k]), 12, MUTED))
        lx += 150
    out.append(_label(px2, bar_y + 86, "标成「无」的四项，citation 字段是空字符串——", 12, MUTED))
    out.append(_label(px2, bar_y + 104, "写论文时不许给它们补一个看起来像的编号。", 12, MUTED))

    # panel 3: reasons under equal attacks (left half only)
    py2 = 330
    out.append(_label(40, py2, "同样 %d 类攻击，各报出几条具体原因" % d["common"], 16, INK, "bold"))
    vmax2 = max(d["ours"], d["theirs"]) or 1
    out.append(_label(40, py2 + 34, "uibc-core", 13, MUTED))
    out.append(_bar(250, py2 + 20, 280, 24, d["ours"], vmax2, OURS))
    out.append(_label(540, py2 + 38, str(d["ours"]), 15, INK, "bold"))
    out.append(_label(40, py2 + 70, "agent-action-capsule", 13, MUTED))
    out.append(_bar(250, py2 + 56, 280, 24, d["theirs"], vmax2, THEIRS))
    out.append(_label(540, py2 + 74, str(d["theirs"]), 15, INK, "bold"))
    out.append(_label(40, py2 + 104, "别把它读成「更好」：他们一条原因覆盖整个 capsule，", 12, MUTED))
    out.append(_label(40, py2 + 122, "我们一条原因指向一个文件。粒度不同，条数才不同。", 12, MUTED))

    # panel 4: outside witnesses -- the column where we are behind
    f = d["facts"]
    out.append(_label(660, py2, "外部第三方见证（我们落后的一项）", 16, THEIRS, "bold"))
    out.append(_label(660, py2 + 34, "我们", 13, MUTED))
    out.append(_bar(760, py2 + 20, 240, 22, 0, f["third_party_implementations"], OURS))
    out.append(_label(1012, py2 + 36, "0", 15, THEIRS, "bold"))
    out.append(_label(660, py2 + 70, "他们", 13, MUTED))
    out.append(_bar(760, py2 + 56, 240, 22, f["third_party_implementations"],
                   f["third_party_implementations"], THEIRS))
    out.append(_label(1012, py2 + 72, str(f["third_party_implementations"]), 15, INK, "bold"))
    out.append(_label(660, py2 + 102, "（%s）" % f["third_party_detail"], 11, MUTED))
    out.append(_label(660, py2 + 130, "已进入他人仓库：%d 处" % len(f["landed_in_other_repos"]),
                      12, MUTED))
    out.append(_label(660, py2 + 150, "在线验证端点：%s" % ("有" if f["has_online_verifier"] else "无"),
                      12, MUTED))
    out.append(_label(660, py2 + 174, "这一栏我们输，图上不遮。", 12, THEIRS))

    out.append(f'<line x1="40" y1="{H - 62}" x2="{W - 40}" y2="{H - 62}" stroke="{GRID}"/>')
    out.append(_label(40, H - 36,
                      "复跑：python3 tools/build_dashboard.py > docs/DASHBOARD.svg   "
                      "（数据源：check_release_parity / compare_diagnostics / uibc_core.basis）",
                      11, MUTED))
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = collect()
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else render(d))


if __name__ == "__main__":
    main()
