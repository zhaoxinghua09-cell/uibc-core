"""Three ways to obtain this project. Three different verifiers.

Someone can get the archive (DOI), the package (`pip install`), or the
repository. Each holds a different set of checks, and only one of them is what
this repository's tests describe. This tool puts the three side by side so a
claim can be aimed at the right one.

    python3 tools/check_release_parity.py
    python3 tools/check_release_parity.py --json

It reads the two recorded baselines (docs/ARCHIVE-BASELINE.json and
docs/PUBLISHED-BASELINE.json) and the current tree. The baselines are
measurements made on 2026-11-18 and are not refreshed automatically: a release
is an outbound act, so its record changes when a release happens, not when
someone remembers to bump a number.
"""

import json
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_TOOLS = os.path.join(_REPO, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)


def _tree_version():
    """Read the version without tomllib: this project supports Python 3.10, and
    tomllib only arrived in 3.11. The gate on CI is `test (3.10)`, so a 3.11-only
    import is a real failure, not a local quirk."""
    import re
    with open(os.path.join(_REPO, "pyproject.toml"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise RuntimeError("no version line in pyproject.toml")
    return m.group(1)


def _load(name):
    with open(os.path.join(_REPO, "docs", name), encoding="utf-8") as f:
        return json.load(f)


def build():
    import build_evidence_index as bei
    archive = _load("ARCHIVE-BASELINE.json")
    published = _load("PUBLISHED-BASELINE.json")
    current = bei.checks_declared()
    order = lambda ids: sorted(ids, key=lambda c: int(c[1:]))

    channels = {
        "archive (DOI)": {"version": archive["version_declared"],
                          "checks": archive["checks"],
                          "source": archive["source_revision"][:8]},
        "package (pip)": {"version": published["version"],
                          "checks": published["checks"],
                          "source": "PyPI sdist"},
        "repository": {"version": _tree_version() + "（未发布）",
                       "checks": list(current),
                       "source": "main"},
    }
    for name, ch in channels.items():
        ch["checks"] = order(ch["checks"])

    only_repo = [c for c in order(current)
                 if c not in archive["checks"] and c not in published["checks"]]
    return {
        "channels": channels,
        "counts": {k: len(v["checks"]) for k, v in channels.items()},
        "only_the_repository_has": only_repo,
        "the_package_has_more_than_the_archive": order(
            [c for c in published["checks"] if c not in archive["checks"]]),
    }


def render(r):
    lines = ["| 获取方式 | 版本 | 检查项 | 项数 |", "|---|---|---|---|"]
    for name, ch in r["channels"].items():
        lines.append("| %s | %s | %s | %d |"
                     % (name, ch["version"], ", ".join(ch["checks"]),
                        len(ch["checks"])))
    lines.append("")
    lines.append("**只有仓库里有的检查**：%s" % ", ".join(
        r["only_the_repository_has"]))
    lines.append("")
    lines.append("所以一句话该挂在哪一边，取决于它说了什么：")
    lines.append("- 说 S1-S6 / S11 / S12 的行为 → 归档和 pip 都能背书；")
    lines.append("- 说上面那批之外任何一项 → **只有仓库能背书**，写成"
                 "「仓库状态，未发布」；")
    lines.append("- 说审计器、套件、端点、跨实现导出 → 同上，且这些从未进入任何发布件。")
    lines.append("")
    lines.append("这不是版本号问题：`pip install` 拿到的东西里没有那 10 项，"
                 "读者不必怀疑我们，数一遍就够了。")
    return "\n".join(lines) + "\n"


def main():
    r = build()
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render(r))
    # a channel claiming a check the repository does not have would mean the
    # baseline is stale in the dangerous direction
    bad = [c for ch in r["channels"].values() for c in ch["checks"]
           if c not in r["channels"]["repository"]["checks"]]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
