"""One screen for a stranger: the receipt's numbers, the ten gates, no links.

The parity board did this for the competitor comparison. This does it for the
outsider question: what exactly does a stranger get, and what can they check
before believing any of it?

What the page is:
  * one HTML file, no stylesheets, no scripts from anywhere else, no URLs at
    all - so it opens offline and nobody has to trust a CDN;
  * the receipt's numbers (three digests, file count, delivery, the four steps)
    written in as a JSON snapshot, with a `--check` that fails when the page
    says a number the receipt no longer says;
  * the ten gate names, read out of `stranger_own_check.py` rather than
    retyped here, so a gate cannot be dropped from the page by forgetting it;
  * the page recomputes its own verdict in JavaScript when opened: every digest
    must be 64 lowercase hex characters, the file count must be positive, every
    step must be ok, and the gate count must be ten. If any of that fails it
    prints SELF-CHECK FAIL in the last line, not in a toast the reader can miss.

What it is not: proof. It is a stranger-readable index to the proofs, and it
says so in its own footer.

Usage:
  python tools/render_outsider_board.py --write
  python tools/render_outsider_board.py --check
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPT = os.path.join(HERE, "docs", "outsider-rerun-receipt.json")
PARITY = os.path.join(HERE, "docs", "competitor-parity.json")
BOARD = os.path.join(HERE, "docs", "OUTSIDER-BOARD.html")
GATES_TOOL = os.path.join(HERE, "tools", "stranger_own_check.py")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def parity_snapshot():
    """The one number that answers "超越在哪": same ten dimensions, everyone scored.

    The receipt's own `parity` step prints this tail, but a stranger reading
    one page should not have to open a second file to find it.
    """
    if not os.path.exists(PARITY):
        return None
    data = json.load(open(PARITY, encoding="utf-8"))
    def total(entry):
        return sum(int(v) for v in entry.get("dims", {}).values())
    repos = data.get("repos", [])
    scored = [(total(r), r.get("repo", "?")) for r in repos]
    best_score, best_repo = max(scored) if scored else (0, "?")
    return {
        "repos": len(repos),
        "best_repo": best_repo,
        "best_score": best_score,
        "ours": total(data.get("ours", {})),
        "zero_repos": sum(1 for sc, _ in scored if sc == 0),
        "dimensions": len(data.get("ours", {}).get("dims", {})),
    }


def gate_names():
    """The gates, read out of the tool that runs them - never retyped here."""
    spec = importlib.util.spec_from_file_location("stranger_own_check", GATES_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = []
    for entry in getattr(mod, "CHECKS"):
        name, cmd = entry[0], entry[1]
        out.append((name, " ".join(str(c) for c in cmd)))
    return out


def snapshot():
    receipt = json.load(open(RECEIPT, encoding="utf-8"))
    return {
        "generated_at": receipt["generated_at"],
        "tree_sha256": receipt["tree_sha256"],
        "content_sha256": receipt["content_sha256"],
        "content_lf_sha256": receipt.get("content_lf_sha256"),
        "delivery": receipt.get("delivery"),
        "files_hashed": receipt["files_hashed"],
        "steps": [{"step": s["step"], "ok": bool(s["ok"]), "rc": s["rc"]} for s in receipt["steps"]],
        "gates": [{"name": n, "what": w} for n, w in gate_names()],
        "receipt_ok": bool(receipt.get("ok")),
        "parity": parity_snapshot(),
    }


def render(snap):
    body = json.dumps(snap, indent=1, ensure_ascii=False)
    rows = "".join(
        f"<tr><td><code>{g['name']}</code></td><td>{g['what']}</td></tr>" for g in snap["gates"]
    )
    steps = "".join(
        f"<tr><td><code>{s['step']}</code></td><td>{s['rc']}</td><td>{'ok' if s['ok'] else 'FAILED'}</td></tr>"
        for s in snap["steps"]
    )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>UIBC outsider board</title>
<style>
body{{font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.4rem;margin:0 0 .2rem}}
.sub{{color:#555;margin:0 0 1.4rem}}
table{{border-collapse:collapse;width:100%;margin:.6rem 0 1.4rem}}
th,td{{border-bottom:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}}
code{{font-family:ui-monospace,monospace;font-size:.92em}}
td.num{{font-family:ui-monospace,monospace;word-break:break-all}}
.hint{{color:#555;font-size:.9em}}
#verdict{{font-family:ui-monospace,monospace;font-weight:600;padding:.6rem;border:1px solid #111}}
</style>
<h1>What a stranger gets</h1>
<p class="sub">One page, no links, no network. The numbers below are the outsider
receipt of this tree; the gates are the ten checks that a stranger can run.</p>

<h2>The receipt</h3>
<table>
<tr><th>what</th><th>value</th></tr>
<tr><td>generated (UTC)</td><td class="num" id="v-at"></td></tr>
<tr><td>delivery</td><td class="num" id="v-delivery"></td></tr>
<tr><td>files hashed</td><td class="num" id="v-files"></td></tr>
<tr><td>tree_sha256 (path + content)</td><td class="num" id="v-tree"></td></tr>
<tr><td>content_sha256 (content only)</td><td class="num" id="v-content"></td></tr>
<tr><td>content_lf_sha256 (content, CRLF folded)</td><td class="num" id="v-lf"></td></tr>
</table>
<p class="hint">Three digests, because one number cannot say why it moved: a mangled
name, a different delivery channel, or a real edit. The count above is the one the
receipt recorded on the channel that wrote it; a checkout of the same commit can
name one or two files fewer when an archive turns a symlink into a plain file, which
is why <code>--check</code> trusts the digest and only asks the count as a second
opinion.</p>

<h2>The four steps it reruns</h3>
<table><tr><th>step</th><th>exit</th><th>result</th></tr>{steps}</table>

<h2>The ten gates</h3>
<table><tr><th>gate</th><th>what it holds</th></tr>{rows}</table>
<h2>The same ten dimensions, everyone scored</h3>
<p class="hint">Same ruler, applied to every repository we could read: five dimensions,
two points each. This is the receipt's <code>parity</code> step, on the page.</p>
<table>
<tr><th>what</th><th>value</th></tr>
<tr><td>repositories pinned and re-scored</td><td class="num" id="v-repos"></td></tr>
<tr><td>dimensions</td><td class="num" id="v-dims"></td></tr>
<tr><td>best competitor</td><td class="num" id="v-best"></td></tr>
<tr><td>this repository</td><td class="num" id="v-ours"></td></tr>
<tr><td>repositories scoring zero</td><td class="num" id="v-zero"></td></tr>
</table>

<p class="hint">Run all ten with <code>python tools/stranger_own_check.py</code>.
A gate that cannot run is counted as skipped, never as passed.</p>

<p id="verdict">computing…</p>
<p class="hint">This page proves nothing by itself. It is an index into proofs that
run: the receipt <code>--check</code>, the gate above it, and the corpus that
ships in the repository.</p>

<script id="snap" type="application/json">
{body}
</script>
<script>
(function () {{
  var s = JSON.parse(document.getElementById("snap").textContent);
  var hex = /^[0-9a-f]{{64}}$/;
  document.getElementById("v-at").textContent = s.generated_at;
  document.getElementById("v-delivery").textContent = s.delivery;
  document.getElementById("v-files").textContent = s.files_hashed;
  document.getElementById("v-tree").textContent = s.tree_sha256;
  document.getElementById("v-content").textContent = s.content_sha256;
  document.getElementById("v-lf").textContent = s.content_lf_sha256 || "(absent)";
  var par = s.parity;
  if (par) {{
    document.getElementById("v-repos").textContent = par.repos;
    document.getElementById("v-dims").textContent = par.dimensions;
    document.getElementById("v-best").textContent = par.best_repo + " " + par.best_score + "/" + (par.dimensions * 2);
    document.getElementById("v-ours").textContent = par.ours + "/" + (par.dimensions * 2);
    document.getElementById("v-zero").textContent = par.zero_repos;
  }}
  var bad = [];
  ["tree_sha256", "content_sha256", "content_lf_sha256"].forEach(function (k) {{
    if (!hex.test(String(s[k] || ""))) bad.push(k + " is not 64 hex characters");
  }});
  if (!(s.files_hashed > 0)) bad.push("file count is not positive");
  if (!s.receipt_ok) bad.push("the receipt itself says one of its steps failed");
  s.steps.forEach(function (st) {{ if (!st.ok || st.rc !== 0) bad.push("step " + st.step + " did not pass"); }});
  if (s.gates.length !== 10) bad.push("expected ten gates, the page carries " + s.gates.length);
  if (s.parity) {{
    if (s.parity.ours !== s.parity.dimensions * 2) bad.push("this repository does not score full marks on its own ruler");
    if (s.parity.best_score > s.parity.ours) bad.push("a competitor outscores this repository on this page");
  }}
  var v = document.getElementById("verdict");
  v.textContent = bad.length
    ? "SELF-CHECK FAIL: " + bad.join("; ")
    : "SELF-CHECK PASS: three digests, " + s.files_hashed + " files, " +
      s.steps.length + " steps, " + s.gates.length + " gates";
}})();
</script>
</html>
"""


def check():
    if not os.path.exists(BOARD):
        print("FAIL no board; run --write first")
        return 1
    text = open(BOARD, encoding="utf-8").read()
    m = re.search(r'<script id="snap" type="application/json">\s*(.*?)\s*</script>', text, re.S)
    if not m:
        print("FAIL the board carries no snapshot")
        return 1
    try:
        embedded = json.loads(m.group(1))
    except ValueError as exc:
        print(f"FAIL the snapshot is not JSON: {exc}")
        return 1
    fresh = snapshot()
    bad = []
    for key in ("tree_sha256", "content_sha256", "content_lf_sha256", "delivery",
                "files_hashed", "receipt_ok"):
        if embedded.get(key) != fresh[key]:
            bad.append(f"{key}: page says {str(embedded.get(key))[:16]}, receipt says {str(fresh[key])[:16]}")
    if [g["name"] for g in embedded.get("gates", [])] != [g["name"] for g in fresh["gates"]]:
        bad.append("the page lists a different set of gates than stranger_own_check.py")
    if [s["step"] for s in embedded.get("steps", [])] != [s["step"] for s in fresh["steps"]]:
        bad.append("the page lists a different set of steps than the receipt")
    if embedded.get("parity") != fresh["parity"]:
        bad.append("the parity numbers on the page are not the ones docs/competitor-parity.json holds now")
    for url in re.findall(r"https?://[^\"' )]+", text):
        bad.append(f"the page links out: {url}")
    for b in bad:
        print("FAIL", b)
    if bad:
        print(f"\nBOARD FAIL ({len(bad)} problem(s))")
        return 1
    print(f"BOARD OK: page matches the receipt ({fresh['files_hashed']} files, "
          f"{fresh['tree_sha256'][:12]}, {len(fresh['gates'])} gates), no outbound links")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="regenerate docs/OUTSIDER-BOARD.html")
    ap.add_argument("--check", action="store_true", help="verify the page against the receipt (default)")
    args = ap.parse_args()
    if args.write:
        snap = snapshot()
        open(BOARD, "w", encoding="utf-8", newline="").write(render(snap))
        print(f"written: {BOARD} ({os.path.getsize(BOARD)} bytes)")
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
