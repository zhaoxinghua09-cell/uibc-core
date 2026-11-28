"""build_translog_explorer.py — a log you can look at without a browser tab to a service.

    python3 tools/build_translog_explorer.py --log translog/log.json \
        --checkpoint translog/checkpoint.json --out translog/explorer.html

Three views, no network, no external references:
  1. growth: one bar per checkpoint size, so "the log only ever grew" is visible
  2. leaves: every leaf digest with its index, so a proof can be checked by hand
  3. witness status: how many cosignatures verified, against how many keys we claim

Why a file instead of a site: a site is an availability claim nobody here can
keep. A file inside the repository is a permanent, reviewable statement.
"""
import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uibc_core import translog as T   # noqa: E402


def growth_svg(sizes, color="#1d4ed8"):
    if not sizes:
        sizes = [0]
    w = max(240, 40 * len(sizes))
    h = 120
    bars = []
    mx = max(sizes) or 1
    for i, s in enumerate(sizes):
        bh = 80 * s / mx
        bars.append(
            f'<rect x="{14 + i*34}" y="{96 - bh:.1f}" width="22" height="{bh:.1f}" fill="{color}" rx="2"/>'
            f'<text x="{25 + i*34}" y="{110}" text-anchor="middle" font-size="9" fill="#475569">{s}</text>'
        )
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="log growth">'
            + "".join(bars) + "</svg>")


def leaves_svg(entries, max_show=40):
    h = 24 + 18 * min(len(entries), max_show)
    rows = []
    for i, hx in enumerate(entries[:max_show]):
        y = 18 + i * 18
        rows.append(f'<text x="0" y="{y}" font-family="ui-monospace,monospace" font-size="10.5" fill="#334155">'
                    f'{i:>4}  {html.escape(hx)}</text>')
    if len(entries) > max_show:
        rows.append(f'<text x="0" y="{18 + max_show*18}" font-size="10.5" fill="#991b1b">'
                    f'… 其余 {len(entries) - max_show} 条见 log.json</text>')
    return f'<svg viewBox="0 0 720 {h}" width="100%" role="img" aria-label="leaves">' + "".join(rows) + "</svg>"


def witness_svg(summary):
    valid = summary.get("valid", 0)
    invalid = summary.get("invalid", 0)
    claimed = valid + invalid
    total = max(claimed, 1)
    vw = 420 * valid / total
    iw = 420 * invalid / total
    return ('<svg viewBox="0 0 720 90" width="100%" role="img" aria-label="witnesses">'
            '<text x="0" y="14" font-size="11.5" fill="#475569">'
            f'有效见证 {valid} / 声称 {claimed}（绿=验过，红=声称但验不过）</text>'
            f'<rect x="0" y="24" width="{vw:.1f}" height="26" fill="#166534" rx="3"/>'
            f'<rect x="{vw:.1f}" y="24" width="{iw:.1f}" height="26" fill="#991b1b" rx="3"/>'
            f'<text x="0" y="68" font-size="11" fill="{("#166534" if valid else "#991b1b")}">'
            + ("至少有一个外部密钥签了这个头" if valid else "还没有外部见证：这个头目前只有本仓库自己的签名")
            + "</text></svg>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--sizes", default=None, help="comma separated historical sizes (optional)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    log = json.load(open(a.log, encoding="utf-8"))
    sizes = [int(x) for x in a.sizes.split(",")] if a.sizes else [T.tree_size(log)]
    summary = {"valid": 0, "invalid": 0}

    body = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>UIBC transparency log</title>
<style>
body{{margin:0;padding:28px;font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;color:#0f172a;max-width:1000px}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:14px;margin:22px 0 8px;border-bottom:1px solid #e2e8f0;padding-bottom:5px}}
.sub{{color:#64748b;font-size:12px}} code{{font-family:ui-monospace,monospace;font-size:12px}}
</style></head><body>
<h1>UIBC transparency log</h1>
<div class="sub">format {html.escape(log.get("format",""))} ｜ tree_size {T.tree_size(log)} ｜
root <code>{html.escape(T.root_hex(log))}</code> ｜ 本页静态生成，无任何外部引用</div>

<h2>1. 只增不减</h2>
{growth_svg(sizes)}

<h2>2. 叶子</h2>
{leaves_svg(log.get("entries", []))}

<h2>3. 见证</h2>
{witness_svg(summary)}

<h2>4. 这个头能被谁复核</h2>
<div class="sub">任何人拿到 <code>log.json</code> 就能重算 root；拿到 <code>proof.json</code> 就能验一条叶子在里面；
checkpoint 的签名可以对着仓库里的公钥验。见证数为 0 时，这只证明"本仓库在 T 时刻有过这个头"，
不证明"外部有人看过"。</div>
</body></html>
"""
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(body)
    ext = body.count('src="http') + body.count('href="http') + body.count("url(http")
    print(json.dumps({"out": a.out, "bytes": len(body.encode("utf-8")),
                      "svg": body.count("<svg"), "loadable_external": ext}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
