#!/usr/bin/env python3
"""check_phrases.py — 对外材料措辞门禁检查 v1.0

用法:
    python check_phrases.py <文件或目录> [--rules banned_phrases.txt]

行为:
    - 递归扫描 .md / .txt / .html
    - 命中 banned_phrases.txt 中任一正则即报告 文件:行号:命中:替代写法
    - 退出码 0 = 无命中；1 = 有命中（可直接用于 CI）

设计说明:
    禁令写在文档里三个月就失效；做成可执行脚本才能长期生效。
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from pathlib import Path

DEFAULT_RULES = Path(__file__).with_name("banned_phrases.txt")
SUFFIXES = {".md", ".txt", ".html", ".htm"}
# 自身与规则文件不检查，避免自命中
SKIP_NAMES = {"check_phrases.py", "banned_phrases.txt"}
# 行内豁免标记：同一行出现该标记即跳过。
# 用于两类合法场景：(a) 正在列举禁用表述的规则表；(b) 主体不是我们自己的评估（如 W3C 员工）。
ALLOW_MARKER = "phrase-ok"


def load_rules(path: Path) -> list[tuple[re.Pattern[str], str]]:
    rules: list[tuple[re.Pattern[str], str]] = []
    if not path.exists():
        print(f"[rules] 规则文件不存在: {path}", file=sys.stderr)
        return rules
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pattern, _, hint = line.partition("|||")
        try:
            rules.append((re.compile(pattern, re.IGNORECASE), hint.strip()))
        except re.error as exc:
            print(f"[rules] 正则无效，跳过: {pattern!r} ({exc})", file=sys.stderr)
    return rules


def iter_files(target: Path, excludes: list[str]):
    if target.is_file():
        yield target
        return
    for p in sorted(target.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SUFFIXES:
            continue
        if p.name in SKIP_NAMES:
            continue
        rel = p.relative_to(target).as_posix()
        if any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(p.name, pat) for pat in excludes):
            continue
        yield p


def scan(target: Path, rules, excludes: list[str]) -> int:
    hits = 0
    skipped = 0
    for fp in iter_files(target, excludes):
        try:
            lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            print(f"[skip] 无法读取 {fp}: {exc}", file=sys.stderr)
            continue
        for no, text in enumerate(lines, 1):
            if ALLOW_MARKER in text:
                skipped += 1
                continue
            for rx, hint in rules:
                m = rx.search(text)
                if m:
                    hits += 1
                    print(f"{fp}:{no}: 命中「{m.group(0)}」 → {hint}")
    if skipped:
        print(f"[info] 行内豁免（{ALLOW_MARKER}）跳过 {skipped} 行", file=sys.stderr)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="对外材料措辞门禁检查")
    ap.add_argument("target", help="待检查的文件或目录")
    ap.add_argument("--rules", default=str(DEFAULT_RULES), help="规则文件路径")
    ap.add_argument("--exclude", action="append", default=[],
                    help="排除路径 glob，可重复，如 --exclude 'FG-TIDA*'")
    ap.add_argument("--quiet", action="store_true", help="仅输出统计")
    args = ap.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"[error] 目标不存在: {target}", file=sys.stderr)
        return 2

    rules = load_rules(Path(args.rules))
    if not rules:
        print("[warn] 未加载到任何规则，检查不生效", file=sys.stderr)
        return 2

    hits = scan(target, rules, args.exclude)
    if args.quiet:
        print(f"规则 {len(rules)} 条，命中 {hits} 处")
    else:
        print(f"\n=== 规则 {len(rules)} 条，命中 {hits} 处 ===")

    return 0 if hits == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
