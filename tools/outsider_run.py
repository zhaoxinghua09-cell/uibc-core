#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外人视角实跑：一个干净解释器 + 只有仓库本身，不给任何内部信息。

做法：在仓库外建 venv（--system-site-packages，不联网装依赖），用该解释器
在仓库目录里跑测试与工具，只信 README 里写的东西。输出一份可复现 JSON。

用法：
    python tools/outsider_run.py --repo <路径> --label <标签>
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "out")


def run(cmd, cwd, timeout=300):
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        return {"cmd": " ".join(cmd), "rc": p.returncode,
                "tail": out.strip().splitlines()[-3:],
                "secs": round(time.perf_counter() - t0, 1)}
    except Exception as e:
        return {"cmd": " ".join(cmd), "rc": -1, "tail": [f"{type(e).__name__}: {e}"],
                "secs": round(time.perf_counter() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--make-venv", action="store_true",
                    help="create a fresh venv outside the repo first")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    venv_py = sys.executable
    steps = []
    if a.make_venv:
        vdir = os.path.join(os.path.dirname(repo), "_outsider_venv")
        steps.append(run([sys.executable, "-m", "venv", "--system-site-packages", vdir],
                         os.path.dirname(repo)))
        venv_py = os.path.join(vdir, "Scripts", "python.exe")
        if not os.path.exists(venv_py):
            venv_py = os.path.join(vdir, "bin", "python")

    results = {"label": a.label, "repo": repo,
               "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "interpreter": venv_py, "steps": steps, "runs": []}

    # 1) 测试（README 声称的那句"一致性测试"）
    results["runs"].append(dict(name="unittest",
                                **run([venv_py, "-m", "unittest", "discover",
                                       "-s", "tests", "-p", "test_*.py"], repo)))
    # 2) 版本与规范号
    results["runs"].append(dict(name="version", **run(
        [venv_py, "-c", "import uibc_core as u; print(u.SPEC_VERSION)"], repo)))
    # 3) 工具清单（外人能看到的"可复跑证据"有多少）
    tools = sorted(os.listdir(os.path.join(repo, "tools"))) \
        if os.path.isdir(os.path.join(repo, "tools")) else []
    results["tools_present"] = [t for t in tools if t.endswith(".py")]
    # 4) 逐个跑工具（只跑没有网络/交互依赖的）
    for t in results["tools_present"]:
        if t.startswith(("cose_sign1_interop", "mutation_benchmark",
                         "uibc_to_epaec", "guardrail_shim", "redteam_suite")):
            results["runs"].append(dict(name=t, **run(
                [venv_py, os.path.join("tools", t)], repo, timeout=600)))

    p = os.path.join(OUT, "outsider_%s.json" % a.label)
    os.makedirs(OUT, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps({r["name"]: r["rc"] for r in results["runs"]},
                     ensure_ascii=False))
    print("RESULT_JSON=" + p)


if __name__ == "__main__":
    main()
