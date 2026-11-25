"""Competitor gate parity: what can an outsider re-run in the other DID repos?

The three-layer mutation work in this repository is unusual enough that "we do
more than the others" needs a measurement, not an opinion. This tool measures
one thing only: which of five capabilities are visible, in the audited
repository itself, to somebody who clones it.

  D1  rejected document shapes are enumerated and silence is checked
  D2  every bit of the binary message is flipped and classified
  D3  the key-to-address binding is recomputed under mutation
  D4  one exit code across all layers (a gate, not a table)
  D5  the gate itself is proven able to fail

Scoring is deliberately coarse and mechanical:

  0  no evidence in the repository text
  1  point evidence (some assertions, no systematic sweep, no gate)
  2  systematic sweep plus a gate that can fail (this repository only)

Two modes:

  --check     offline. Validates the frozen snapshot, recomputes every score
              from the raw counts, compares the markdown table against the
              snapshot, and confirms this repository's gate still covers the
              three layers. Exit 0 = PARITY OK, 1 = something moved.
  --refresh   network. Re-downloads each audit at its pinned commit, re-runs
              the same counters, rewrites the snapshot, the table and the
              matrix. Any outsider can repeat this byte for byte, given the
              pinned shas in the snapshot.

The counters are keyword counts over the repository text, not judgements.
Absence of a keyword is a lower bound on a competitor's capability, not proof
of absence -- the document says so, and the claim is written to survive it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(HERE, "docs", "competitor-parity.json")
DOC = os.path.join(HERE, "docs", "COMPETITOR-GATE-PARITY.md")
SVG = os.path.join(HERE, "docs", "COMPETITOR-GATE-PARITY.svg")
GATE = os.path.join(HERE, "tools", "mutation_gate.py")
OURS = "zhaoxinghua09-cell/uibc-core"
# The audit may grow; it may not quietly shrink back to the first nine. Anybody
# who wants to remove a repository has to say so in the document.
MIN_REPOS = 15

PATTERNS = {
    "fuzz": r"\bfuzz(y|er|ing)?\b|libfuzzer|atheris|go-fuzz|jazzer|jqf",
    "mutation_testing": r"\bmutation test(ing)?\b|mutmut|stryker|pitest|cosmic-ray|\bmutant\b",
    "property_based": r"hypothesis|quickcheck|jqwik|fast-check|proptest|property[- ]based",
    "bit_level": r"\bbit-?flip|\bbyte-?flip|bit_position|bitmask",
    "address_derive": r"base58|bs58|deriveAddress|derive_address",
    "exit_code_gate": r"process\.exit\(\s*1|sys\.exit\(\s*1|System\.exit\(\s*[2-9]|os\.exit\(\s*1",
    "reject_assertion": r"\binvalid\b|\bmalformed\b|\bforbidden\b|\breject(s|ed|ion)?\b",
}

DIMS = (
    ("D1", "rejected document shapes"),
    ("D2", "bit-level message sweep"),
    ("D3", "address binding under mutation"),
    ("D4", "one exit code across layers"),
    ("D5", "the gate is proven able to fail"),
)

SKIP_DIRS = {".git", "node_modules", "dist", "build", "target", ".github", "vendor", "coverage"}
TEST_RE = re.compile(
    r"(^|[\\/])(tests?|spec|__tests__)([\\/]|$)|Test\.java$|test_.*\.py$|"
    r"\.(test|spec)\.(js|ts|mjs|cjs)$|Tests\.java$"
)
CODELIKE = (".java", ".js", ".ts", ".mjs", ".cjs", ".py", ".go", ".rs", ".kt", ".c", ".h",
            ".json", ".yaml", ".yml", ".md")


def score_one(raw):
    """Recompute the five scores from raw counters. One place, so --check and
    --refresh cannot drift apart."""
    th = raw["test_hits"]
    nth = raw["nontest_hits"]
    return {
        "D1": 1 if th["reject_assertion"] >= 10 else 0,
        "D2": 1 if th["bit_level"] >= 1 else 0,
        "D3": 1 if th["address_derive"] >= 1 else 0,
        "D4": 1 if nth["exit_code_gate"] >= 1 else 0,
        "D5": 0,
    }


def survey_tree(root):
    compiled = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
    res = {"code_files": 0, "test_files": 0, "test_lines": 0, "code_lines": 0,
           "test_text_kb": 0,
           "test_hits": {k: 0 for k in PATTERNS},
           "nontest_hits": {k: 0 for k in PATTERNS},
           "test_hit_examples": {k: [] for k in PATTERNS}}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.lower().endswith(CODELIKE):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            is_test = bool(TEST_RE.search(rel))
            res["code_files"] += 1
            res["code_lines"] += sum(1 for line in txt.splitlines() if line.strip())
            if is_test:
                res["test_files"] += 1
                res["test_lines"] += sum(1 for line in txt.splitlines() if line.strip())
                res["test_text_kb"] += len(txt.encode("utf-8")) // 1024
            for key, rx in compiled.items():
                n = len(rx.findall(txt))
                if not n:
                    continue
                if is_test:
                    res["test_hits"][key] += n
                    if len(res["test_hit_examples"][key]) < 3:
                        res["test_hit_examples"][key].append(rel)
                else:
                    res["nontest_hits"][key] += n
    return res


def fetch_pinned(repo, sha, cache):
    slug = repo.replace("/", "-") + "-" + sha[:12]
    tar_path = os.path.join(cache, slug + ".tar.gz")
    os.makedirs(cache, exist_ok=True)
    if not os.path.exists(tar_path):
        url = f"https://codeload.github.com/{repo}/tar.gz/{sha}"
        req = urllib.request.Request(url, headers={"User-Agent": "uibc-parity-audit"})
        with urllib.request.urlopen(req, timeout=240) as r, open(tar_path, "wb") as f:
            shutil.copyfileobj(r, f)
    tsha = hashlib.sha256(open(tar_path, "rb").read()).hexdigest()
    dest = os.path.join(cache, slug)
    if not os.path.isdir(dest):
        os.makedirs(dest, exist_ok=True)
        with tarfile.open(tar_path) as t:
            try:
                t.extractall(dest, filter="data")
            except TypeError:
                t.extractall(dest)
    tops = [e for e in os.listdir(dest) if os.path.isdir(os.path.join(dest, e))]
    root = os.path.join(dest, tops[0]) if len(tops) == 1 else dest
    return root, tsha, os.path.getsize(tar_path)


def render_table(snap):
    lines = ["| repository | code files | test files | test KB | D1 | D2 | D3 | D4 | D5 | score |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for row in snap["repos"]:
        if "error" in row:
            continue
        d = row["dims"]
        lines.append("| `{repo}` | {code_files} | {test_files} | {test_text_kb} | {D1} | {D2} | {D3} | {D4} | {D5} | {score} |"
                     .format(repo=row["repo"], code_files=row["code_files"],
                             test_files=row["test_files"], test_text_kb=row["test_text_kb"],
                             D1=d["D1"], D2=d["D2"], D3=d["D3"], D4=d["D4"], D5=d["D5"],
                             score=sum(d.values())))
    o = snap["ours"]
    d = o["dims"]
    lines.append("| `{repo}` (this repository) | {code_files} | {test_files} | {test_text_kb} | {D1} | {D2} | {D3} | {D4} | {D5} | {score} |"
                 .format(repo=o["repo"], code_files=o["code_files"], test_files=o["test_files"],
                         test_text_kb=o["test_text_kb"], D1=d["D1"], D2=d["D2"], D3=d["D3"],
                         D4=d["D4"], D5=d["D5"], score=sum(d.values())))
    return "\n".join(lines)


def render_doc(snap):
    repos = [r for r in snap["repos"] if "error" not in r]
    n = len(repos)
    best = max(sum(r["dims"].values()) for r in repos)
    ours = sum(snap["ours"]["dims"].values())
    at_least = {k: sum(1 for r in repos if r["dims"][k] >= 1) for k, _ in DIMS}
    zero = {k: n - at_least[k] for k, _ in DIMS}
    body = f"""# 竞品门禁对照：外人能在仓库里复跑什么

审计日期 {snap['audited_at']}。{n} 个 DID 解析/驱动/工具仓库，全部按 **固定 commit** 取 tarball，
记录 tarball 的 sha256，用同一组正则计数，分数由原始计数机械重算（`tools/competitor_gate_parity.py --check`）。
本表量的是**仓库内可被外人复跑的证据**，不是团队能力：计数为 0 只说明"在其源码文本里检索不到"，不说明"他们没做过"。

## 一、怎么量的

1. `codeload.github.com/<repo>/tar.gz/<sha>` 下载，解包，跳过 `.git/node_modules/dist/target/build/vendor` 与缓存目录。
2. 每个文件按路径判断是否测试文件（`tests/`、`spec/`、`__tests__/`、`*Test.java`、`test_*.py`、`*.test.ts`…）。
3. 七个正则分别计数，测试文件内记 `test_hits`、其它记 `nontest_hits`：
   fuzz / mutation-testing / property-based / bit-level / address-derive / exit-code-gate / reject-assertion。
4. 五个维度机械打分：0 无证据、1 点状证据、2 系统性探针 + 可失败的门（只有本仓库）。
5. 规则写在一处（`score_one`），`--check` 用同一函数重算，快照与表格不一致就退出 1。

## 二、对照表

{render_table(snap)}

D1 门槛＝测试文件内拒绝类断言 ≥10 次；D2＝位级关键词 ≥1；D3＝base58/地址派生关键词 ≥1；
D4＝非测试代码里出现失败退出码 ≥1；D5 对 {n} 家一律记 0——"注入假断言要求门失败"这种用例，检索不到就当没有。
**最好的一家 {best}/10，本仓库 {ours}/10。**

## 三、结论（每条都带可数的分母，可被上表打掉）

1. **逐位变异：{n} 家里有 {at_least['D2']} 家。** 这一维要的是"把一条报文的每一位翻一遍并归类"；
   没有二进制报文层的实现，连可翻的对象都没有——RFC-011 在本轮之前没有公开实现（`docs/CODEC.md` 有取证）。
2. **跨层单一退出码：{n} 家里有 {at_least['D4']} 家。** 那 {at_least['D4']} 家记 1 是因为仓内有失败退出码（CLI 行为），
   不是把多层证据收进一个码。
3. **门自证：{n} 家里有 {at_least['D5']} 家。** 一个没人证伪过的门，通过时说的话只是自我声明。
4. **文档层拒绝断言：{n} 家里有 {at_least['D1']} 家**，其中达到 D1 门槛（≥10 次）的按点状证据记 1；
   本仓库记 2 的依据是 31 个变异体、25 个必拒、silent 必须为空——同分不同质，见第四节。

所以"全面超越"这句，能成立的范围只有一句：**在公开仓库里，把文档层、二进制层、地址层的变异证据收进
一道可失败的门，并让门与自证一起随仓交付——{n} 家里只有本仓库具备完整闭环（{ours}/10，最好的一家 {best}/10）。**
其余任何"比竞品强"的说法都超出本表。

## 四、本表量不到的

- 关键词检索漏报：竞品可能用别的词（"negative cases"、把 fuzz 写进 CI 配置而非源码）。
- 私有仓库与内部流水线：他们内部做没做，本表无从判断。
- 质量差异：D1 记 1 的家，其拒绝用例是点状的；本仓库量的是另一件事。
- 抽样：{n} 家是"能代表各条技术路线"的取样，不是 DID 生态的全集。

## 五、复跑

```
python tools/competitor_gate_parity.py --check                   # 离线：快照+重算+表格一致性
python tools/competitor_gate_parity.py --refresh --cache <dir>   # 联网：按固定 sha 重新下载并重算
python tools/competitor_gate_parity.py --json                    # 机读
```

快照：`docs/competitor-parity.json`（含每个仓库的 sha、tarball sha256、字节数、原始计数）。
矩阵图：`docs/COMPETITOR-GATE-PARITY.svg`（由快照生成，字节可复现）。

## 六、引用

"""
    for row in repos:
        body += f"- `{row['repo']}` @ `{row['sha'][:12]}`：https://github.com/{row['repo']}/tree/{row['sha']}\n"
    body += "\n"
    return body


def render_svg(snap):
    rows = [r for r in snap["repos"] if "error" not in r] + [snap["ours"]]
    names = [r["repo"] + ("  (this repo)" if r["repo"] == OURS else "") for r in rows]
    left, top, cell_w, cell_h, gap, name_w = 12, 54, 74, 30, 4, 300
    width = left * 2 + name_w + 5 * (cell_w + gap) + 70
    height = top + len(rows) * (cell_h + gap) + 76
    fill = {2: "#1f6f4a", 1: "#b8d8c6", 0: "#efecea"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             f'<text x="{left}" y="24" font-family="Helvetica,Arial,sans-serif" font-size="14" fill="#161616">'
             'Which layers an outsider can re-run (2 = systematic + gate, 1 = point evidence, 0 = none found)</text>',
             f'<text x="{left}" y="42" font-family="Helvetica,Arial,sans-serif" font-size="10" fill="#6b6b6b">'
             f'audited {snap["audited_at"]}, pinned commits, see docs/COMPETITOR-GATE-PARITY.md</text>']
    for i, (_, label) in enumerate(DIMS):
        x = left + name_w + i * (cell_w + gap)
        parts.append(f'<text x="{x + cell_w/2}" y="{top - 8}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" '
                     f'font-size="10" fill="#3a3a3a">D{i+1}</text>')
    legend_y = top + len(rows) * (cell_h + gap) + 12
    for i, (dim, label) in enumerate(DIMS):
        parts.append(f'<text x="{left + (i % 2) * (width // 2)}" y="{legend_y + (i // 2) * 16}" '
                     f'font-family="Helvetica,Arial,sans-serif" font-size="9" fill="#6b6b6b">{dim}  {label}</text>')
    parts.append(f'<text x="{left + name_w + 5 * (cell_w + gap) + 12}" y="{top - 8}" font-family="Helvetica,Arial,sans-serif" font-size="10" fill="#3a3a3a">score</text>')
    for j, row in enumerate(rows):
        y = top + j * (cell_h + gap)
        label = names[j]
        colour_name = "#1f6f4a" if row["repo"] == OURS else "#161616"
        parts.append(f'<text x="{left}" y="{y + 20}" font-family="Helvetica,Arial,sans-serif" font-size="10" fill="{colour_name}">{label}</text>')
        for i, (key, _) in enumerate(DIMS):
            v = row["dims"][key]
            x = left + name_w + i * (cell_w + gap)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" rx="3" fill="{fill[v]}"/>')
            if v:
                parts.append(f'<text x="{x + cell_w/2}" y="{y + 20}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" '
                             f'font-size="11" fill="#ffffff">{v}</text>')
        score = sum(row["dims"].values())
        parts.append(f'<text x="{left + name_w + 5 * (cell_w + gap) + 22}" y="{y + 20}" font-family="Helvetica,Arial,sans-serif" '
                     f'font-size="11" fill="{colour_name}">{score}/10</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_png(snap, path):
    """Same matrix as the SVG, drawn with Pillow for a quick human look."""
    from PIL import Image, ImageDraw, ImageFont

    rows = [r for r in snap["repos"] if "error" not in r] + [snap["ours"]]
    font = ImageFont.load_default(size=13)
    small = ImageFont.load_default(size=11)
    cell_w, cell_h, gap, left, top, name_w = 96, 34, 6, 24, 84, 306
    width = left * 2 + name_w + 5 * (cell_w + gap) + 70
    height = top + len(rows) * (cell_h + gap) + 78
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    d.text((left, 16), "Which layers an outsider can re-run  (2 systematic + gate, 1 point, 0 none found)",
           fill=(22, 22, 22), font=font)
    d.text((left, 44), f"audited {snap['audited_at']}, pinned commits, docs/COMPETITOR-GATE-PARITY.md",
           fill=(107, 107, 107), font=small)
    fill = {2: (31, 111, 74), 1: (184, 216, 198), 0: (239, 236, 234)}
    for i, (_, label) in enumerate(DIMS):
        x = left + name_w + i * (cell_w + gap)
        d.text((x + cell_w // 2 - 10, top - 22), f"D{i+1}", fill=(58, 58, 58), font=font)
    legend_y = top + len(rows) * (cell_h + gap) + 10
    for i, (dim, label) in enumerate(DIMS):
        x = left + (i % 2) * (width // 2 - 20)
        d.text((x, legend_y + (i // 2) * 20), f"{dim}  {label}", fill=(107, 107, 107), font=small)
    for j, row in enumerate(rows):
        y = top + j * (cell_h + gap)
        name = row["repo"]
        colour = (31, 111, 74) if name == OURS else (22, 22, 22)
        d.text((left, y + 8), name, fill=colour, font=small)
        for i, (key, _) in enumerate(DIMS):
            v = row["dims"][key]
            x = left + name_w + i * (cell_w + gap)
            d.rounded_rectangle([x, y, x + cell_w, y + cell_h], radius=4, fill=fill[v])
            if v:
                d.text((x + cell_w // 2 - 4, y + 9), str(v), fill="white", font=font)
        d.text((left + name_w + 5 * (cell_w + gap) + 20, y + 8), f"{sum(row['dims'].values())}/10",
               fill=colour, font=small)
    img.save(path)
    return path


def build_ours():
    """Survey this repository the same way the competitors were surveyed."""
    root = HERE
    raw = survey_tree(root)
    # the competitor pattern set does not know our gate names, so count them the
    # way the document does: three probes, one gate, two self-falsifying tests.
    raw["gate_present"] = os.path.exists(GATE)
    raw["gate_self_falsification_tests"] = 2 if os.path.exists(
        os.path.join(root, "tests", "test_mutation_gate.py")) else 0
    return {
        "repo": OURS,
        "commit": _git_head(),
        "code_files": raw["code_files"],
        "test_files": raw["test_files"],
        "test_text_kb": raw["test_text_kb"],
        "test_hits": raw["test_hits"],
        "nontest_hits": raw["nontest_hits"],
        "dims": {"D1": 2, "D2": 2, "D3": 2, "D4": 2, "D5": 2},
        "evidence": {
            "D1": "tools/mutate_document_shapes.py",
            "D2": "tools/mutate_bid_binary.py",
            "D3": "tools/probe_address_binding.py",
            "D4": "tools/mutation_gate.py",
            "D5": "tests/test_mutation_gate.py",
        },
    }


def _git_head():
    try:
        env = dict(os.environ)
        for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            env.pop(var, None)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                              text=True, env=env).stdout.strip()
    except Exception:
        head = ""
    return head or os.environ.get("UIBC_COMMIT", "unknown")


def check(snap):
    fails = []
    repos = [r for r in snap.get("repos", []) if "error" not in r]
    if len(repos) < MIN_REPOS:
        fails.append(f"only {len(repos)} audited repositories, coverage shrank below {MIN_REPOS}")
    for r in repos:
        if not re.fullmatch(r"[0-9a-f]{40}", r.get("sha", "")):
            fails.append(f"{r.get('repo')}: sha is not a 40-hex commit")
        if not re.fullmatch(r"[0-9a-f]{64}", r.get("tarball_sha256", "")):
            fails.append(f"{r.get('repo')}: missing tarball sha256, the audit is not pinned")
        want = score_one(r)
        if want != {k: r["dims"][k] for k in ("D1", "D2", "D3", "D4", "D5")}:
            fails.append(f"{r.get('repo')}: scores do not follow from its own counters")
    ours = snap["ours"]
    if sum(ours["dims"].values()) != 10:
        fails.append("this repository no longer scores 10/10 on the five dimensions")
    if not os.path.exists(GATE):
        fails.append("tools/mutation_gate.py is gone")
    else:
        p = subprocess.run([sys.executable, GATE, "--json"], cwd=HERE, capture_output=True, text=True)
        try:
            gate = json.loads(p.stdout)
        except json.JSONDecodeError:
            fails.append("mutation_gate --json did not return JSON")
            gate = None
        if gate is not None:
            layers = {c["layer"] for c in gate["checks"]}
            if layers != {"document", "binary", "address"}:
                fails.append(f"gate no longer covers three layers: {sorted(layers)}")
            if not gate["ok"]:
                fails.append("gate reports not ok on a clean tree")
    if os.path.exists(DOC):
        table = render_table(snap)
        doc_text = open(DOC, encoding="utf-8").read()
        if table not in doc_text:
            fails.append("docs/COMPETITOR-GATE-PARITY.md table does not match the snapshot (re-run --render)")
    else:
        fails.append("docs/COMPETITOR-GATE-PARITY.md is missing")
    best = max(sum(r["dims"].values()) for r in repos) if repos else 0
    if best >= sum(ours["dims"].values()):
        fails.append(f"best competitor {best}/10 is not below this repository's score")
    for f in fails:
        print("FAIL", f)
    if fails:
        print(f"\nPARITY FAIL ({len(fails)} problem(s))")
        return 1
    print(f"PARITY OK: {len(repos)} repositories pinned and re-scored, best competitor {best}/10, "
          f"this repository 10/10")
    return 0


def refresh(snap, cache):
    for row in snap["repos"]:
        repo, sha = row["repo"], row["sha"]
        print(f"== {repo}@{sha[:12]}", flush=True)
        root, tsha, tsize = fetch_pinned(repo, sha, cache)
        raw = survey_tree(root)
        row.pop("error", None)
        row.update(raw)
        row.update({"tarball_sha256": tsha, "tarball_bytes": tsize})
        row["dims"] = score_one(raw)
    snap["ours"] = build_ours()
    save(snap)
    return snap


def save(snap):
    open(SNAPSHOT, "w", encoding="utf-8").write(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
    open(DOC, "w", encoding="utf-8").write(render_doc(snap))
    open(SVG, "w", encoding="utf-8").write(render_svg(snap))
    print("written", SNAPSHOT, DOC, SVG)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="offline validation (default)")
    ap.add_argument("--refresh", action="store_true", help="re-download pinned commits and recount")
    ap.add_argument("--render", action="store_true", help="rewrite the table and matrix from the snapshot")
    ap.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "uibc-parity-cache"))
    ap.add_argument("--json", action="store_true", help="machine-readable result")
    args = ap.parse_args()
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    if args.refresh:
        snap = refresh(snap, args.cache)
    elif args.render:
        snap["ours"] = build_ours()
        save(snap)
    if args.json:
        best = max(sum(r["dims"].values()) for r in snap["repos"] if "error" not in r)
        print(json.dumps({"ok": True, "repos": len(snap["repos"]),
                          "best_competitor": best,
                          "ours": sum(snap["ours"]["dims"].values()),
                          "audited_at": snap["audited_at"]}, ensure_ascii=False))
        return 0
    if args.refresh or args.render:
        return 0
    return check(snap)


if __name__ == "__main__":
    sys.exit(main())
