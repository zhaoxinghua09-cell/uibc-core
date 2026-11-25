"""Every point in the competitor table must point at a line someone can read.

The table says "9 repositories assert rejections in their tests" and so on. Until
now that was a number; a reader could not see which line earned it, and could not
tell a real assertion from a comment that happens to contain the word. This tool
prints the first few matching lines per dimension, with path and line number, so
the table can be audited at the evidence level instead of trusted at the count
level.

    python tools/parity_evidence_lines.py --run --cache <tarball cache>
    python tools/parity_evidence_lines.py --check      # offline: every scored
                                                       # point must cite a line

Record: docs/competitor-evidence-lines.json
Page:   docs/COMPETITOR-EVIDENCE-LINES.md
"""

import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(HERE, "docs", "competitor-parity.json")
RECORD = os.path.join(HERE, "docs", "competitor-evidence-lines.json")
PAGE = os.path.join(HERE, "docs", "COMPETITOR-EVIDENCE-LINES.md")
TOOL = os.path.join(HERE, "tools", "competitor_gate_parity.py")

# which evidence pattern backs which dimension, and where it is allowed to live:
# D1-D3 are assertions, so they must be in test files; D4 is an exit code, which
# lives in the source a test would call, not in the test itself.
DIM_PATTERN = {"D1": "reject_assertion", "D2": "bit_level", "D3": "address_derive", "D4": "exit_code_gate"}
DIM_SCOPE = {"D1": "test", "D2": "test", "D3": "test", "D4": "code"}
PER_DIM = 3


def _cgp():
    spec = importlib.util.spec_from_file_location("uibc_parity", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def collect(cgp, root):
    """First PER_DIM matching test lines for each evidence pattern."""
    out = {}
    for dim, key in DIM_PATTERN.items():
        rx = re.compile(cgp.PATTERNS[key], re.I)
        scope = DIM_SCOPE[dim]
        found = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in cgp.SKIP_DIRS]
            for fn in filenames:
                if not fn.lower().endswith(cgp.CODELIKE):
                    continue
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, root).replace("\\", "/")
                is_test = bool(cgp.TEST_RE.search(rel))
                if scope == "test" and not is_test:
                    continue
                if scope == "code" and is_test:
                    continue
                try:
                    lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
                except OSError:
                    continue
                for n, line in enumerate(lines, 1):
                    if len(found) >= PER_DIM:
                        break
                    if rx.search(line):
                        found.append({"file": rel, "line": n, "text": line.strip()[:160]})
        out[dim] = found
    return out


def measure(cache):
    cgp = _cgp()
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    rows = []
    for r in snap["repos"]:
        if "error" in r:
            continue
        root, _sha, _size = cgp.fetch_pinned(r["repo"], r["sha"], cache)
        rows.append({"repo": r["repo"], "sha": r["sha"], "dims": r["dims"], "evidence": collect(cgp, root)})
        print("collected", r["repo"], flush=True)
    rec = {"audited_at": snap.get("audited_at"), "per_dim": PER_DIM, "rows": rows}
    open(RECORD, "w", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
    write_page(rec)
    return rec


def write_page(rec):
    lines = [
        "# 竞品表的每一分，指到哪一行（每次 `--run` 重写本页）", "",
        "审计日 %s。这张表此前只有计数；本页把计分维度的**原始命中行**贴出来（每维最多 %d 条），"
        "让你能直接判断那一分是断言还是注释里蹭到的词。" % (rec["audited_at"], rec["per_dim"]), "",
        "| 仓库 | 得分 | 计分明细 |", "|---|---|---|",
    ]
    for r in rec["rows"]:
        dims = [k for k, v in r["dims"].items() if v]
        lines.append("| `%s` | %d/10 | %s |" % (r["repo"], sum(r["dims"].values()), ", ".join(dims) or "—"))
    lines += ["", "## 逐家证据行", ""]
    for r in rec["rows"]:
        if not sum(r["dims"].values()):
            continue
        lines.append("### `%s` — %d/10（commit `%s`）" % (r["repo"], sum(r["dims"].values()), r["sha"][:12]))
        lines.append("")
        for dim, key in DIM_PATTERN.items():
            if not r["dims"].get(dim):
                continue
            lines.append("- **%s**（%s，%s 文件）" % (dim, key, "测试" if DIM_SCOPE[dim] == "test" else "源码"))
            for e in r["evidence"].get(dim, [])[:rec["per_dim"]]:
                lines.append("  - `%s:%d` — `%s`" % (e["file"], e["line"], e["text"]))
            if not r["evidence"].get(dim):
                lines.append("  - （无行可指——这一分就是错发的，必须撤销）")
        lines.append("")
    lines += ["## 怎么读", "",
              "本页只证一件事：**每个 1 分都能指到具体的 test 行**。它不证那一行写得好、也不证它跑过。",
              "如果某一分下面是注释或字符串，你看到的就是原样——请按 `docs/COMPETITOR-EVIDENCE-LINES.md` 的行号回仓核对，"
              "并在 Issue 里点名；`--check` 只能保证\"有行可指\"，判断\"这行算不算证据\"仍然是人做的事。", ""]
    open(PAGE, "w", encoding="utf-8").write("\n".join(lines))
    return PAGE


def check():
    rec = json.load(open(RECORD, encoding="utf-8"))
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    want = {r["repo"] for r in snap["repos"] if "error" not in r}
    got = {r["repo"] for r in rec["rows"]}
    fails = []
    if want != got:
        fails.append("record covers %d repos, snapshot has %d" % (len(got), len(want)))
    for r in rec["rows"]:
        for dim, key in DIM_PATTERN.items():
            scored = bool(r["dims"].get(dim))
            has = bool(r["evidence"].get(dim))
            if scored and not has:
                fails.append("%s scored %s but cites no line" % (r["repo"], dim))
            if not scored and has:
                # evidence exists but the threshold was not met - legal, but say so
                pass
    page = open(PAGE, encoding="utf-8").read() if os.path.exists(PAGE) else ""
    for r in rec["rows"]:
        if sum(r["dims"].values()) and ("`%s`" % r["repo"]) not in page:
            fails.append("page does not list %s" % r["repo"])
    if fails:
        for f in fails[:8]:
            print("FAIL", f)
        print("EVIDENCE-LINES FAIL (%d problem(s))" % len(fails))
        return 1
    scored = sum(1 for r in rec["rows"] for d in r["dims"].values() if d)
    print("EVIDENCE-LINES OK: %d repositories, %d scored points, every one cites a line"
          % (len(got), scored))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--render", action="store_true", help="rewrite the page from the record, no re-scan")
    ap.add_argument("--cache", default=os.path.join(os.environ.get("TEMP", "/tmp"), "uibc-parity-cache"))
    args = ap.parse_args()
    if args.run:
        measure(args.cache)
        return 0
    if args.render:
        write_page(json.load(open(RECORD, encoding="utf-8")))
        print("written", PAGE)
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
