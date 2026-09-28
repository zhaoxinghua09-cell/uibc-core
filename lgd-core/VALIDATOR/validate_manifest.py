#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LGD Core Specification v0.1 — manifest validator.

按《LGD Core Spec v0.1》三律逐项校验一份 LGD Manifest：

  LGD-I  有籍   (identity)  : subject.id / identity.owner / identity.version 三字段齐全且非空
  LGD-II 有证   (evidence)  : evidence.required=true 时 items 非空，且每条含 source 与 date
  LGD-III有门禁 (governance): governance.gates 非空且含 audit；audit.logging 与 audit.immutable 均为 true

输出：每条问题一行（带律别前缀）＋ RESULT: PASS / FAIL；正确退出码 0（PASS）/ 1（FAIL）。

依赖：
  - 仅用 Python 3 标准库（argparse / json / sys / pathlib）。
  - 解析 YAML 优先用 PyYAML；若环境无 PyYAML，回退到内置极简 YAML 子集解析器。
  - --schema 严格 JSON Schema 校验仅在环境安装 jsonschema 时启用，否则自动跳过并提示。

本文件为代码，依本目录 LICENSE（Apache License 2.0）授权。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:  # 优先 PyYAML
    import yaml  # type: ignore

    _HAS_YAML = True
except Exception:  # pragma: no cover - 环境相关
    _HAS_YAML = False

try:  # 可选：严格 JSON Schema 校验
    from jsonschema import Draft202012Validator  # type: ignore

    _HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover - 环境相关
    _HAS_JSONSCHEMA = False


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "MANIFEST.schema.json"

# LGD-I「有籍」三字段（最小判据；subject.type 由 schema 层保证）
IDENTITY_FIELDS = ("subject.id", "identity.owner", "identity.version")


# --------------------------------------------------------------------------- #
# 极简 YAML 子集解析（仅在无 PyYAML 时启用）
# 支持：缩进映射 / "- " 序列 / 行内流式列表 [a, b] / 引号字符串 / 布尔 / 数字 / 注释
# --------------------------------------------------------------------------- #
def _split_flow(text: str) -> list:
    parts, buf, in_s, in_d = [], [], False, False
    for ch in text:
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        if ch == "," and not in_s and not in_d:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts]


def _scalar(text: str):
    s = text.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [] if not inner else [_scalar(x) for x in _split_flow(inner)]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _minimal_yaml_load(text: str):
    lines = []
    for raw in text.splitlines():
        out, in_s, in_d = [], False, False
        for ch in raw:
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            if ch == "#" and not in_s and not in_d:
                break
            out.append(ch)
        s = "".join(out).rstrip()
        if not s.strip():
            continue
        lines.append((len(s) - len(s.lstrip(" ")), s.strip()))

    pos = 0

    def parse_block(indent):
        nonlocal pos
        if pos >= len(lines):
            return None
        seq = lines[pos][1].startswith("- ")
        if seq:
            result = []
            while (
                pos < len(lines)
                and lines[pos][0] == indent
                and lines[pos][1].startswith("- ")
            ):
                item = lines[pos][1][2:].strip()
                pos += 1
                if item == "":
                    result.append(
                        parse_block(lines[pos][0])
                        if pos < len(lines) and lines[pos][0] > indent
                        else None
                    )
                elif ":" in item and not item.startswith(("'", '"', "[")):
                    key, _, rest = item.partition(":")
                    node = {}
                    if rest.strip():
                        node[key.strip()] = _scalar(rest)
                    while pos < len(lines) and lines[pos][0] > indent:
                        sub = parse_block(lines[pos][0])
                        if isinstance(sub, dict):
                            node.update(sub)
                        break
                    result.append(node)
                else:
                    result.append(_scalar(item))
            return result

        mapping = {}
        while (
            pos < len(lines)
            and lines[pos][0] == indent
            and not lines[pos][1].startswith("- ")
        ):
            key, _, rest = lines[pos][1].partition(":")
            key = key.strip().strip("'\"")
            rest = rest.strip()
            pos += 1
            if rest == "":
                if pos < len(lines) and lines[pos][0] > indent:
                    mapping[key] = parse_block(lines[pos][0])
                else:
                    mapping[key] = None
            else:
                mapping[key] = _scalar(rest)
        return mapping

    return parse_block(lines[0][0]) if lines else None


# --------------------------------------------------------------------------- #
# 载入
# --------------------------------------------------------------------------- #
def load_manifest(path):
    """读入 manifest 文件（.yaml/.yml/.json），返回 Python 对象。"""
    text = Path(path).read_text(encoding="utf-8")
    if str(path).lower().endswith(".json"):
        return json.loads(text)
    if _HAS_YAML:
        return yaml.safe_load(text)
    return _minimal_yaml_load(text)


def _get(data, dotted):
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


# --------------------------------------------------------------------------- #
# 三律校验
# --------------------------------------------------------------------------- #
def validate(data) -> list:
    """按三律逐项校验，返回问题清单（空列表 = PASS）。"""
    problems: list = []
    if not isinstance(data, dict):
        return ["[结构] manifest 根节点必须是映射（mapping）"]

    # ---- LGD-I 有籍 ----
    for field in IDENTITY_FIELDS:
        if _blank(_get(data, field)):
            problems.append(f"[LGD-I 有籍] 必填字段缺失或为空: {field}")

    # ---- LGD-II 有证 ----
    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        problems.append("[LGD-II 有证] 缺失 evidence 段")
    else:
        required = evidence.get("required")
        if not isinstance(required, bool):
            problems.append("[LGD-II 有证] evidence.required 必须为布尔值")
        items = evidence.get("items")
        if required is True:
            if not isinstance(items, list) or len(items) == 0:
                problems.append(
                    "[LGD-II 有证] evidence.required=true 时 items 必须为非空数组"
                )
            else:
                for i, item in enumerate(items):
                    if not isinstance(item, dict):
                        problems.append(
                            f"[LGD-II 有证] evidence.items[{i}] 必须是映射"
                        )
                        continue
                    if _blank(item.get("source")):
                        problems.append(
                            f"[LGD-II 有证] evidence.items[{i}].source 缺失或为空"
                        )
                    if _blank(item.get("date")):
                        problems.append(
                            f"[LGD-II 有证] evidence.items[{i}].date 缺失或为空"
                        )
        if items is not None and not isinstance(items, list):
            problems.append("[LGD-II 有证] evidence.items 必须是数组")

    # ---- LGD-III 有门禁 ----
    governance = data.get("governance")
    if not isinstance(governance, dict):
        problems.append("[LGD-III 有门禁] 缺失 governance 段")
    else:
        gates = governance.get("gates")
        if not isinstance(gates, list) or len(gates) == 0:
            problems.append("[LGD-III 有门禁] governance.gates 必须为非空数组")
        elif "audit" not in gates:
            problems.append("[LGD-III 有门禁] governance.gates 必须包含 'audit'")

    audit = data.get("audit")
    if not isinstance(audit, dict):
        problems.append("[LGD-III 有门禁] 缺失 audit 段")
    else:
        if audit.get("logging") is not True:
            problems.append("[LGD-III 有门禁] audit.logging 必须为 true")
        if audit.get("immutable") is not True:
            problems.append("[LGD-III 有门禁] audit.immutable 必须为 true")

    return problems


# --------------------------------------------------------------------------- #
# 可选：严格 JSON Schema 校验
# --------------------------------------------------------------------------- #
def schema_problems(data) -> list:
    """用 MANIFEST.schema.json 做严格校验；未装 jsonschema 时返回空并提示。"""
    if not _HAS_JSONSCHEMA:
        return ["[schema] 环境未安装 jsonschema，已跳过严格 schema 校验"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    out = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = "/".join(str(x) for x in err.path) or "<root>"
        out.append(f"[schema] {loc}: {err.message}")
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _report(path, data, use_schema) -> list:
    problems = validate(data)
    if use_schema:
        problems = problems + schema_problems(data)
    print(f"== {path} ==")
    if problems:
        print("RESULT: FAIL")
        for line in problems:
            print(f"  - {line}")
    else:
        print("RESULT: PASS")
        print("  - LGD-I 有籍 / LGD-II 有证 / LGD-III 有门禁：全部通过")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_manifest.py",
        description="LGD Core Spec v0.1 — 按三律校验 LGD Manifest",
    )
    parser.add_argument("manifests", nargs="+", help="manifest 文件路径（可多个）")
    parser.add_argument(
        "--schema",
        action="store_true",
        help="额外用 MANIFEST.schema.json 做严格 JSON Schema 校验（需 jsonschema）",
    )
    args = parser.parse_args(argv)

    exit_code = 0
    for path in args.manifests:
        try:
            data = load_manifest(path)
        except Exception as exc:  # 解析失败即 FAIL
            print(f"== {path} ==")
            print("RESULT: FAIL")
            print(f"  - [结构] 无法解析 manifest: {exc}")
            exit_code = 1
            continue
        if _report(path, data, args.schema):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
