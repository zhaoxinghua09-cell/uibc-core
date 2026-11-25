#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布就绪门禁：一个 tag 必须只指向一份自己讲得通的字节。

为什么要有它：2026-11-24/25 连续三次 lab bundle 失败，真错误是
`no archive at .../conformance/uibc-conformance-0.5.3.zip` —— tag 切在代码
与归档之前。版本闸查了版本串，却没查"这个 tag 自己的归档在不在"。于是同类
失败一路走到发布步才暴露。本脚本把这一条补成第一步的硬失败。

检查项（任一不满足即 exit 1，且逐条打印原因）：
  1. pyproject.toml / uibc_core/__init__.py 的 __version__ / server.json 的
     version 与 packages[].version 全部等于被检查的版本；
  2. conformance/uibc-conformance-<版本>.zip 存在且非空；
  3. 该 zip 的名字与其内部记录的版本一致（能读到的话）。
  4. 给了 --tag 时，tag 必须等于 v<版本>。

用法：
    python tools/check_release_readiness.py --version 0.5.4 --tag v0.5.4
    python tools/check_release_readiness.py --version 0.5.3        # 本地自查
退出码：0 就绪；1 不就绪（逐条列出）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _ver_from_pyproject() -> str:
    txt = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
    return m.group(1) if m else ""


def _ver_from_init() -> str:
    txt = (ROOT / "uibc_core" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', txt, re.M)
    return m.group(1) if m else ""


def _server_versions() -> list[tuple[str, str]]:
    p = ROOT / "server.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out = [("server.json version", str(d.get("version", "")))]
    for pkg in d.get("packages", []) or []:
        out.append(("server.json packages[%s].version" % pkg.get("name", "?"),
                    str(pkg.get("version", ""))))
    return out


def check(version: str, tag: str | None) -> list[str]:
    v = version.lstrip("v")
    problems: list[str] = []

    if _ver_from_pyproject() != v:
        problems.append("pyproject.toml version = %r, expected %r"
                        % (_ver_from_pyproject(), v))
    if _ver_from_init() != v:
        problems.append("uibc_core/__init__.py __version__ = %r, expected %r"
                        % (_ver_from_init(), v))
    for name, got in _server_versions():
        if got != v:
            problems.append("%s = %r, expected %r" % (name, got, v))

    archive = ROOT / "conformance" / ("uibc-conformance-%s.zip" % v)
    if not archive.is_file():
        problems.append(
            "no archive at %s — a tag must carry the bytes it names; build it with "
            "tools/build_conformance_bundle.py %s and commit it in the same commit as "
            "the version bump" % (archive.relative_to(ROOT), v))
    elif archive.stat().st_size == 0:
        problems.append("%s is empty" % archive.relative_to(ROOT))
    else:
        try:
            with zipfile.ZipFile(archive) as z:
                manifest = [n for n in z.namelist() if n.endswith("MANIFEST.json")]
                got = ""
                if manifest:
                    data = json.loads(z.read(manifest[0]).decode("utf-8"))
                    got = str(data.get("version") or data.get("package_version") or "")
            if got and got != v:
                problems.append("%s records version %r, expected %r"
                                % (archive.name, got, v))
        except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as e:
            problems.append("%s is not a readable zip: %s" % (archive.name, e))

    if tag and tag != "v" + v:
        problems.append("tag %r does not name version %r (expected v%s)" % (tag, v, v))

    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True, help="version under test, e.g. 0.5.4 or v0.5.4")
    ap.add_argument("--tag", default=None, help="tag being published, e.g. v0.5.4")
    a = ap.parse_args(argv)

    problems = check(a.version, a.tag)
    if problems:
        print("NOT READY TO TAG %s" % a.version)
        for p in problems:
            print("  - %s" % p)
        return 1
    print("READY: %s — version strings agree, archive present, tag matches" % a.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
