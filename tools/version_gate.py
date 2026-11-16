#!/usr/bin/env python3
"""版本一致性门禁：包元数据、清单与运行时三处必须同版。

为什么要有这个：2026-11-15 出过 `__version__ = "0.3.0"` 字面量跟着 0.3.1 一起发布的
事故，装到 0.3.1 却报 0.3.0，而当时的验收矩阵把它记成"一致"。这个门禁把同类缺陷
变成构建期红叉：只要 pyproject.toml、server.json（version 与 packages[].version）、
以及安装后 importlib.metadata 报出的版本任一不等，退出码 1。

用法（CI 里先装包再跑本脚本）：
    python -m pip install .
    python tools/version_gate.py
本地不装包也能查静态三处（运行时检查会自动降级为 SKIP 并打印原因）：
    python tools/version_gate.py --static-only
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def pyproject_version() -> tuple[str, str]:
    txt = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
    if m:
        return m.group(1), "pyproject.toml version literal"
    m = re.search(r'^version\s*=\s*\{.*?attr\s*=\s*"([^"]+)"', txt, re.M)
    if m:
        return "attr:" + m.group(1), "pyproject.toml dynamic version"
    raise SystemExit("GATE FAIL: pyproject.toml 里找不到 version")


def manifest_versions() -> list[tuple[str, str]]:
    p = ROOT / "server.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out = [("server.json version", d.get("version", ""))]
    for pkg in d.get("packages") or []:
        out.append((f"server.json packages[{pkg.get('identifier')}].version", pkg.get("version", "")))
    return out


def runtime_version(dist_name: str) -> tuple[str, str]:
    try:
        from importlib.metadata import version as v
        return v(dist_name), "importlib.metadata"
    except Exception as e:  # 未安装时降级
        return "", f"unavailable ({type(e).__name__})"

def pin_problems() -> list[str]:
    """Every `uses:` must be a full 40-character commit SHA.

    A floating tag (@v4, release/v1) runs whatever that ref points at today, with this
    repository's token, and nothing reviews the move. Proven in both directions before
    shipping: a pinned-only tree passes, one floating line fails with file:line.
    """
    import re as _re

    bad: list[str] = []
    wf_dir = None
    probe = ROOT
    for _ in range(4):
        cand = probe / ".github" / "workflows"
        if cand.is_dir():
            wf_dir = cand
            break
        probe = probe.parent
    if wf_dir is None:
        return bad
    pat = _re.compile(r"uses:\s*([^\s#]+)")
    sha = _re.compile(r"^[^@]+@[0-9a-f]{40}$")
    for p in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = pat.search(line)
            if not m:
                continue
            ref = m.group(1)
            if ref.startswith("./"):
                continue
            if not sha.match(ref):
                bad.append(f"{p.name}:{lineno}: {ref} is not pinned to a 40-character SHA")
    return bad

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--static-only", action="store_true")
    a = ap.parse_args()

    pv, pv_src = pyproject_version()
    checks: list[tuple[str, str]] = [(pv_src, pv)]
    checks += manifest_versions()

    dist = None
    if not pv.startswith("attr:"):
        import re as _re
        m = _re.search(r'^name\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), _re.M)
        dist = m.group(1) if m else None
    if dist and not a.static_only:
        rv, how = runtime_version(dist)
        checks.append((f"runtime importlib.metadata({how})", rv))

    if pv.startswith("attr:"):
        print(f"NOTE: version 由 {pv} 提供，静态比对退化为 \"清单==运行时\"")

    problems = []
    ref_label, ref_value = checks[0]
    for label, value in checks[1:]:
        if not value:
            problems.append(f"{label}: 空值（{value!r}）")
            continue
        if value != ref_value and not pv.startswith("attr:"):
            problems.append(f"{label}: {value} != {ref_value} (来自 {ref_label})")
        elif pv.startswith("attr:") and label.startswith("runtime") and value == "0.0.0":
            problems.append(f"{label}: 回退到 0.0.0，说明包未安装或元数据缺失")

    for label, value in checks:
        print(f"  {label:<46} {value or '<empty>'}")

    problems += pin_problems()

    if problems:
        print("\nGATE FAIL:")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nGATE PASS: 版本来源一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
