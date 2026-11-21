# -*- coding: utf-8 -*-
"""版本一致性门禁 —— fixture 用例（正向 / 负向 / 边界）。"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_version_consistency import audit  # noqa: E402

RESULTS = []
TMP = Path(tempfile.mkdtemp(prefix="vg_"))


def make(name, pyproject_v="0.4.0", dunder_v="0.4.0",
         spec_v='uibc-core/0.4.0-proposal', with_pyproject=True):
    d = TMP / name
    (d / "uibc_core").mkdir(parents=True, exist_ok=True)
    if with_pyproject:
        (d / "pyproject.toml").write_text(
            f'[project]\nname = "uibc-core"\nversion = "{pyproject_v}"\n', encoding="utf-8")
    init = ""
    if dunder_v is not None:
        init += f'__version__ = "{dunder_v}"\n'
    if spec_v is not None:
        init += f'SPEC_VERSION = "{spec_v}"\n'
    (d / "uibc_core" / "__init__.py").write_text(init, encoding="utf-8")
    return d


def case(cid, desc, got, want):
    ok = got == want
    RESULTS.append({"id": cid, "desc": desc, "got": str(got), "want": str(want), "pass": ok})
    print(f"{'PASS' if ok else 'FAIL'}  {cid}  {desc}\n       got={got} want={want}")


def codes(r):
    return [f["code"] for f in r["findings"]]


# V01 完全一致
r = audit(make("ok", spec_v='uibc-core/0.4.0-proposal'), pypi="0.4.0", tag="v0.4.0")
case("V01", "五处全一致 → PASS", (r["ok"], codes(r)), (True, []))

# V02 pyproject 与 __version__ 不一致
r = audit(make("pj", pyproject_v="0.4.1"), pypi="0.4.0")
case("V02", "pyproject=0.4.1 / __version__=0.4.0 → FAIL", codes(r), ["package_version_mismatch"])

# V03 SPEC_VERSION 落后（真实仓库的现状）
r = audit(make("lag", spec_v='uibc-core/0.3.3-proposal'), pypi="0.4.0")
case("V03", "SPEC_VERSION 0.3.3 落后 0.4.0 → FAIL（核心回归）",
     codes(r), ["spec_version_lags_package"])

# V04 SPEC_VERSION 超前（同样不允许）
r = audit(make("ahead", spec_v='uibc-core/0.5.0-proposal'))
case("V04", "SPEC_VERSION 0.5.0 超前 → FAIL", codes(r), ["spec_version_lags_package"])

# V05 SPEC_VERSION 无可解析版本段
r = audit(make("noparse", spec_v='uibc-core/proposal'))
case("V05", "SPEC_VERSION 无版本段 → FAIL", codes(r), ["spec_version_unparseable"])

# V06 缺 SPEC_VERSION
r = audit(make("nospec", spec_v=None))
case("V06", "缺 SPEC_VERSION → FAIL", codes(r), ["spec_version_missing"])

# V07 缺 __version__
r = audit(make("nodunder", dunder_v=None))
case("V07", "缺 __version__ → FAIL", codes(r), ["dunder_version_missing"])

# V08 缺 pyproject
r = audit(make("nopj", with_pyproject=False))
case("V08", "缺 pyproject → FAIL", codes(r), ["pyproject_version_missing"])

# V09 git tag 不一致
r = audit(make("tag"), tag="v0.3.3")
case("V09", "tag=v0.3.3 / __version__=0.4.0 → FAIL", codes(r), ["git_tag_mismatch"])

# V10 PyPI 不一致
r = audit(make("pypi"), pypi="0.3.3")
case("V10", "PyPI=0.3.3 / __version__=0.4.0 → FAIL", codes(r), ["pypi_version_mismatch"])

# V11 PyPI 不可达 → 不计为不一致（避免误报）
r = audit(make("unreach"), pypi="__unreachable__")
case("V11", "PyPI 不可达 → 不算不一致，但记录 code",
     (r["ok"], codes(r)), (True, ["pypi_unreachable"]))

# V12 多处同时错 → 全部列出（不只报第一个）
r = audit(make("multi", pyproject_v="0.4.1", spec_v='uibc-core/0.3.3-proposal'),
          pypi="0.3.3", tag="v0.3.3")
case("V12", "四处同时错 → 一次列全",
     sorted(codes(r)),
     sorted(["package_version_mismatch", "spec_version_lags_package",
             "pypi_version_mismatch", "git_tag_mismatch"]))

# V13 带后缀的合法写法
r = audit(make("suffix", spec_v='uibc-core/0.4.0-proposal'))
case("V13", "SPEC_VERSION 带 -proposal 后缀 → 仍算一致", r["ok"], True)

n = sum(1 for x in RESULTS if x["pass"])
print(f"\n{'-'*50}\ncases={len(RESULTS)} pass={n} fail={len(RESULTS)-n}")
with open(Path(__file__).with_name("version_results.json"), "w", encoding="utf-8") as fh:
    json.dump({"total": len(RESULTS), "pass": n, "results": RESULTS}, fh, ensure_ascii=False, indent=2)
shutil.rmtree(TMP, ignore_errors=True)
raise SystemExit(0 if n == len(RESULTS) else 1)
