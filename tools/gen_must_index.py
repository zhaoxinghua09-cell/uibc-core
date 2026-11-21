#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_must_index.py —— 把 uibc 文档里的规范性条款编成可审计索引。

为什么必须做：正式规范里有 24 处 MUST 却全部没有编号，于是"MUST ↔ 测试"无法对齐，
外部实现也就无法逐条自我评分（这是 Phase V §61 的最关键缺口）。

输出：docs/SPEC-MUST-INDEX.md（编号 + 文件 + 行号 + 原文 + 分类 + 检查映射占位）
跑法：python gen_must_index.py <repo_root>
"""
import io
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"D:\work_xlgd_20261121\uibc-core"
DOCS = os.path.join(ROOT, "docs")
OUT = os.path.join(DOCS, "SPEC-MUST-INDEX.md")

# 规范文件（排除 draft 与评审记录：draft 的措辞还不具备规范性）
SKIP = {"CHECK-MATRIX.md", "SPEC-MUST-INDEX.md", "EXIT-CODES.md"}


def main():
    entries = []
    files = sorted(f for f in os.listdir(DOCS) if f.endswith(".md") and f not in SKIP)
    for fn in files:
        path = os.path.join(DOCS, fn)
        with io.open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        in_code = False
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if not re.search(r"\bMUST\b", line):
                continue
            if line.strip().startswith(">"):        # 引用块多为解释，不算条款
                continue
            kind = "MUST NOT" if re.search(r"\bMUST\s+NOT\b", line) else "MUST"
            text = re.sub(r"^\s*[-*0-9.]+\s*", "", line).strip()
            text = text.replace("|", "\\|")
            # 区分「条款」与「对条款的引用/评论」：评论不算规范条目，不能占用编号。
            meta = ("也就是", "判定", "冲突", "标 **", "说明栏", "得先对齐",
                    "不是我们", "不是规范", "评审", "audit note")
            is_clause = (line.lstrip().startswith("|")
                         or (not any(m in line for m in meta) and len(line) < 220))
            entries.append({"file": fn, "line": i, "kind": kind, "text": text,
                            "clause": bool(is_clause)})

    lines_out = [
        "# SPEC-MUST-INDEX · 规范性条款索引（自动生成）",
        "",
        "> 生成器：`tools/gen_must_index.py`；来源：`docs/*.md` 中所有含 `MUST` 的行（跳过代码块与引用块）。",
        "> 本索引不改写原文，只做编号与对齐；编号一经发布不得复用。",
        "> `映射检查` 一列为人工填写（S1–S19 见 `docs/CHECK-MATRIX.md`）；留空的即 **untested**，",
        "> 按 `docs/CONFORMANCE.md` 的规定，untested 条款不得计入「已覆盖」。",
        "",
        "| 编号 | 级别 | 类别 | 文件 | 行 | 条款原文（截断 120 字） | 映射检查 |",
        "|---|---|---|---|---|---|---|",
    ]
    n_clause = 0
    for e in entries:
        t = e["text"]
        if len(t) > 120:
            t = t[:117] + "..."
        cat = "条款" if e["clause"] else "引用/评论"
        tag = "MUST-%02d" % n_clause if e["clause"] else "—"
        if e["clause"]:
            n_clause += 1
        lines_out.append("| %s | %s | %s | `%s` | %d | %s | _待填_ |"
                         % (tag, e["kind"], cat, e["file"], e["line"], t))
    lines_out += [
        "",
        "## 统计",
        "",
        "- 命中含 MUST 的行：**%d**" % len(entries),
        "- 其中可作条款（已编号）：**%d**；引用/评论（不编号）：%d"
        % (n_clause, len(entries) - n_clause),
        "- 已填映射：0（本轮只做编号，不改语义）",
        "",
        "## 已知问题（本轮记录，不做静默修改）",
        "",
        "1. **SHOULD / MAY 为 0**：规范把所有约束都写成 MUST，导致第三方无法分辨",
        "   「不做就不合规」与「建议做」。整改需要在原文处逐条降级，属于语义变更，须单独批准。",
        "2. **RFC 2119/8174 声明只存在于 draft**：正式规范首页缺少该声明，",
        "   外部读者无法确认 MUST 的规范效力。",
        "3. 本表未覆盖 `drafts/draft-zhao-uibc-evidence-chain-00.md`（草案阶段，措辞会变）。",
    ]
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")
    print("WROTE %s  (%d 条)" % (OUT, len(entries)))


if __name__ == "__main__":
    main()
