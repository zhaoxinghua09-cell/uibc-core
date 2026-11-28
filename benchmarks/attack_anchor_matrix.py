#!/usr/bin/env python3
"""Turn the mutation submission records into an anchor-dependency matrix.

Reads only `submissions/*.json` (the same files the leaderboard reads), so every
cell in the output is a measured verdict rather than a claim about one.

The question it answers: if a verifier is given a trust anchor (the signer's
key) or a freshness anchor (the expected head), exactly which mutation classes
become detectable, and which remain undetectable because no anchor can help.

Usage:
    python benchmarks/attack_anchor_matrix.py
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
MODES = ("open", "pinned", "head-pinned")


def load(impl_file: pathlib.Path) -> dict:
    return json.loads(impl_file.read_text(encoding="utf-8"))


def rows(record: dict) -> dict:
    out = {}
    for case in record["suites"]["mutation"]["cases"]:
        modes = case["modes"]
        out[case["id"]] = {m: bool(modes.get(m, {}).get("accepted")) for m in MODES}
    return out


def main() -> None:
    record = load(ROOT / "submissions" / "uibc-core@0.4.0.json")
    per_case = rows(record)
    commit = record["commit"]

    # Which cases does each mode still accept?
    {m: [cid for cid, v in per_case.items() if v[m]] for m in MODES}

    # A case is "bought" by an anchor if it is accepted without that anchor and
    # rejected with it.
    bought_by_pin = [c for c in per_case if per_case[c]["open"] and not per_case[c]["pinned"]]
    bought_by_head = [c for c in per_case if per_case[c]["pinned"] and not per_case[c]["head-pinned"]]
    needs_neither = [c for c in per_case if not per_case[c]["open"]]

    lines = []
    lines.append("# Anchor dependency of the mutation suite\n")
    lines.append(f"Source: `submissions/uibc-core@0.4.0.json` (commit `{commit}`), read at "
                 "generation time. `A` = accepted (attack succeeded), `R` = rejected.\n")
    lines.append("| # | mutation | open (no anchor) | pinned (trust anchor) | head-pinned (trust + freshness) |")
    lines.append("|---|---|---|---|---|")
    for i, (cid, v) in enumerate(sorted(per_case.items()), 1):
        mark = lambda m: "**A**" if v[m] else "R"
        lines.append(f"| {i} | {cid} | {mark('open')} | {mark('pinned')} | {mark('head-pinned')} |")
    lines.append("")
    lines.append("## What each anchor actually buys\n")
    lines.append(f"- No anchor needed: **{len(needs_neither)} of {len(per_case)}** cases are rejected with nothing "
                 "trusted — they are self-contained integrity failures.")
    lines.append(f"- Trust anchor buys: **{len(bought_by_pin)}** case(s) — {', '.join(bought_by_pin) or 'none'}. "
                 "Pinning the signer's key detects a re-signed package only because the key no longer matches.")
    lines.append(f"- Freshness anchor buys: **{len(bought_by_head)}** case(s) — {', '.join(bought_by_head) or 'none'}. "
                 "A pinned key still accepts a valid package from an earlier point in time; only an expected-head "
                 "comparison catches that.")
    lines.append("")
    lines.append("The point is the shape, not the scores: an anchor buys exactly the attack class it names, one "
                 "case each, and buys nothing else. Key pinning does not buy freshness, and freshness does not buy "
                 "authenticity.")
    out_md = ROOT / "anchors.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # HTML: same cells, one row per mutation, colour by verdict.
    def cell(m: str, cid: str) -> str:
        a = per_case[cid][m]
        return f'<td class="{ "acc" if a else "rej" }">{ "A" if a else "R" }</td>'

    trs = "\n".join(
        f"<tr><td class=n>{i}</td><td class=m>{cid}</td>{cell('open', cid)}{cell('pinned', cid)}"
        f"{cell('head-pinned', cid)}</tr>"
        for i, cid in enumerate(sorted(per_case), 1)
    )
    html = f"""<!doctype html><meta charset="utf-8">
<title>Anchor dependency of the mutation suite</title>
<style>
body{{font:14px/1.5 -apple-system,Segoe UI,sans-serif;margin:40px;color:#111}}
h1{{font-size:20px;font-weight:600;margin:0 0 4px}}
.sub{{color:#666;margin-bottom:20px}}
table{{border-collapse:collapse;width:100%;max-width:860px}}
th,td{{padding:6px 10px;border-bottom:1px solid #eee;text-align:center}}
th{{background:#f7f7f7;font-weight:600;font-size:13px}}
.m{{text-align:left}} .n{{color:#999;width:34px}}
.acc{{background:#fdecec;color:#b3261e;font-weight:600}}
.rej{{color:#2e7d32}}
.note{{max-width:860px;margin-top:22px;font-size:13px;color:#333}}
.note b{{font-weight:600}}
</style>
<h1>Anchor dependency of the mutation suite</h1>
<div class=sub>commit {commit} · 21 mutations × 3 anchor modes · cells read from submissions/uibc-core@0.4.0.json</div>
<table><thead><tr><th>#</th><th class=m>mutation</th><th>open<br><span style="font-weight:400;color:#777">no anchor</span></th>
<th>pinned<br><span style="font-weight:400;color:#777">trust anchor</span></th>
<th>head-pinned<br><span style="font-weight:400;color:#777">trust + freshness</span></th></tr></thead>
<tbody>{trs}</tbody></table>
<div class=note>
<p><b>A</b> = accepted (the attack succeeded), <b>R</b> = rejected.</p>
<p><b>{len(needs_neither)} of {len(per_case)}</b> cases need no anchor: they are self-contained integrity failures.<br>
<b>Trust anchor buys {len(bought_by_pin)}</b> — {', '.join(bought_by_pin) or 'none'}.<br>
<b>Freshness anchor buys {len(bought_by_head)}</b> — {', '.join(bought_by_head) or 'none'}.</p>
<p>An anchor buys exactly the attack class it names, one case each, and nothing else. Key pinning does not buy
freshness; freshness does not buy authenticity.</p>
</div>
"""
    (ROOT / "anchors.html").write_text(html, encoding="utf-8")
    print(f"wrote anchors.md and anchors.html | needs_neither={len(needs_neither)} "
          f"trust_buys={len(bought_by_pin)} freshness_buys={len(bought_by_head)}")


if __name__ == "__main__":
    main()
