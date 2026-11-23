#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前版本一致性门禁（UIBC 0.4.0 发布准备 / P1-1 配套）。

检查同一份代码里所有"对外可见的版本标签"是否互相自洽：
  1. pyproject.toml  [project].version
  2. uibc_core/__init__.py  __version__
  3. uibc_core/__init__.py  SPEC_VERSION（证据报告里携带的就是它）
  4. git 最新 tag（形如 v0.4.0，可选）
  5. PyPI 已发布最新版（可选，需网络）

规则：
  - 1 与 2 必须完全相等（任何差异都是灾难）
  - 3 里的版本段必须与 2 相等（允许 `-proposal` 之类后缀，不允许落后）
  - 4 若存在必须是 `v` + 2
  - 5 若提供必须等于 2

退出码：0 = 一致；1 = 不一致（并逐条打印差在哪）。
无第三方依赖；只在 stdlib 上跑。
"""
import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

CHECKED = [
    ("pyproject.version", "pyproject.toml [project].version"),
    ("dunder.version", "uibc_core/__init__.py __version__"),
    ("spec_version", "uibc_core/__init__.py SPEC_VERSION"),
    ("git.tag", "latest git tag"),
    ("pypi.version", "PyPI latest release"),
]


def read_pyproject(root):
    p = root / "pyproject.toml"
    if not p.exists():
        return None
    try:
        return tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_dunder(root):
    p = root / "uibc_core" / "__init__.py"
    if not p.exists():
        return None, None
    text = p.read_text(encoding="utf-8")
    v = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    s = re.search(r'^SPEC_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return (v.group(1) if v else None), (s.group(1) if s else None)


def spec_label_version(label):
    """从 `uibc-core/0.3.3-proposal` 提取 `0.3.3`。"""
    if not label:
        return None
    m = re.search(r"/(\d+\.\d+(?:\.\d+)?)", label)
    return m.group(1) if m else None


def git_tag(root):
    try:
        out = subprocess.run(["git", "-C", str(root), "describe", "--tags", "--abbrev=0"],
                             capture_output=True, text=True, timeout=20)
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except Exception:
        return None


def pypi_version(pkg):
    import urllib.request
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=15) as fh:
            return json.load(fh)["info"]["version"]
    except Exception:
        return "__unreachable__"


def audit(root, pypi=None, pkg="uibc-core", tag=None):
    findings = []
    pj = read_pyproject(root) or {}
    pj_v = (pj.get("project") or {}).get("version")
    dv, sv = read_dunder(root)
    tag = tag if tag is not None else git_tag(root)
    pv = pypi if pypi is not None else None

    vals = {"pyproject.version": pj_v, "dunder.version": dv,
            "spec_version": sv, "git.tag": tag, "pypi.version": pv}

    if pj_v is None:
        findings.append({"code": "pyproject_version_missing", "detail": "pyproject.toml 无 [project].version"})
    if dv is None:
        findings.append({"code": "dunder_version_missing", "detail": "__init__.py 无 __version__"})
    if pj_v and dv and pj_v != dv:
        findings.append({"code": "package_version_mismatch",
                         "detail": f"pyproject={pj_v} != __version__={dv}"})

    slv = spec_label_version(sv)
    if sv is None:
        findings.append({"code": "spec_version_missing", "detail": "__init__.py 无 SPEC_VERSION"})
    elif dv and slv and slv != dv:
        findings.append({"code": "spec_version_lags_package",
                         "detail": f"SPEC_VERSION 标签={slv} 落后包版本={dv}；"
                                   "证据报告携带 spec_id，会以旧标签指向新字节"})
    elif dv and slv is None:
        findings.append({"code": "spec_version_unparseable",
                         "detail": f"SPEC_VERSION={sv} 中找不到版本号段"})

    if tag and dv:
        t = tag.lstrip("v")
        if t != dv:
            findings.append({"code": "git_tag_mismatch",
                             "detail": f"最新 tag={tag} 与 __version__={dv} 不一致"})

    if pv and pv != "__unreachable__" and dv and pv != dv:
        findings.append({"code": "pypi_version_mismatch",
                         "detail": f"PyPI={pv} != 源码 __version__={dv}"})
    if pv == "__unreachable__":
        findings.append({"code": "pypi_unreachable", "detail": "无法访问 PyPI（未验证，不计为不一致）"})

    return {"root": str(root), "values": vals, "findings": findings,
            "ok": not [f for f in findings if not f["code"].endswith("unreachable")]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--pypi", default=None, help="显式传入 PyPI 版本，避免联网")
    ap.add_argument("--check-pypi", action="store_true", help="联网查询 PyPI")
    ap.add_argument("--tag", default=None, help="显式传入最新 tag（跳过 git 查询）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.repo).resolve()
    pv = a.pypi
    if a.check_pypi and pv is None:
        pv = pypi_version("uibc-core")
    r = audit(root, pypi=pv, tag=a.tag)

    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"repo: {r['root']}")
        for k, desc in CHECKED:
            print(f"  {desc:<45} {r['values'][k]}")
        if r["findings"]:
            print("\nVERSION CONSISTENCY: FAIL")
            for f in r["findings"]:
                print(f"  - [{f['code']}] {f['detail']}")
        else:
            print("\nVERSION CONSISTENCY: PASS")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
