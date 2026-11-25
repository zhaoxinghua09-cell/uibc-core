"""Outsider rerun: prove the claims hold in a copy nobody has touched.

Every receipt in this repository so far was produced by the machine that wrote
the code. That is the weakest possible witness. This tool makes the witness
mechanical:

  1. copy the tree to a fresh temporary directory, without `.git`, without
     caches, without any of this machine's state;
  2. run the four public entry points there with a stripped environment (no
     tokens, no extra variables), from that directory as the working directory;
  3. hash the tree, record every exit code and the tail of every output, and
     write `docs/outsider-rerun-receipt.json`;
  4. `--check` recomputes the tree digest and fails if the receipt no longer
     describes this tree, or if any step is not a clean pass.

The digest excludes the two files it produces (`docs/outsider-rerun-receipt.json`
and `docs/OUTSIDER-RERUN.md`) - otherwise it would have to contain itself. Both
producer and checker skip the same two paths, so the exclusion is symmetric and
the receipt cannot be quietly freshened without the tree actually matching.

If a stranger can run this, they do not have to take anyone's word for the gate,
the parity table or the demo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPT = os.path.join(HERE, "docs", "outsider-rerun-receipt.json")
PAGE = os.path.join(HERE, "docs", "OUTSIDER-RERUN.md")
GENERATED = {"docs/outsider-rerun-receipt.json", "docs/OUTSIDER-RERUN.md"}

IGNORE = (".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
          "node_modules", ".venv", "venv", "dist", "build", "*.pyc", "*.pyo")

STEPS = (
    ("gate", [sys.executable, "tools/mutation_gate.py"], "GATE OK"),
    ("parity", [sys.executable, "tools/competitor_gate_parity.py"], "PARITY OK"),
    ("demo", [sys.executable, "tools/demo_bid_binary.py"], "ALL OK"),
    ("tests", [sys.executable, "-m", "pytest", "tests/test_mutation_gate.py",
               "tests/test_competitor_parity.py", "-q"], "passed"),
)

ENV_KEEP = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "HOME",
            "USERPROFILE", "LANG", "LC_ALL", "PYTHONUTF8", "PYTHONIOENCODING")


def tree_digest(root):
    """sha256 over every file path and its content digest, in path order."""
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in
                             {".git", "__pycache__", ".pytest_cache", ".mypy_cache",
                              ".ruff_cache", "node_modules", ".venv", "venv", "dist", "build"})
        for fn in sorted(filenames):
            if fn.endswith((".pyc", ".pyo")):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if rel in GENERATED:
                continue
            try:
                with open(p, "rb") as f:
                    entries.append(rel + ":" + hashlib.sha256(f.read()).hexdigest())
            except OSError:
                entries.append(rel + ":unreadable")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest(), len(entries)


def clean_env():
    return {k: os.environ[k] for k in ENV_KEEP if k in os.environ} | {"PYTHONUTF8": "1"}


def copy_tree(dest):
    shutil.copytree(HERE, dest, ignore=shutil.ignore_patterns(*IGNORE))


def run(steps_only=None):
    digest, count = tree_digest(HERE)
    tmp = tempfile.mkdtemp(prefix="uibc-outsider-")
    work = os.path.join(tmp, "repo")
    copy_tree(work)
    env = clean_env()
    results = []
    for name, cmd, expect in STEPS:
        if steps_only and name not in steps_only:
            continue
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, timeout=900)
            out, err, rc = proc.stdout or "", proc.stderr or "", proc.returncode
        except Exception as exc:                                     # noqa: BLE001
            out, err, rc = "", f"{type(exc).__name__}: {exc}", 124
        tail = (out.strip().splitlines() or [""])[-1][:160]
        ok = rc == 0 and expect in out
        results.append({"step": name, "cmd": " ".join(cmd[1:]), "rc": rc,
                        "expect": expect, "ok": ok, "seconds": round(time.time() - t0, 1),
                        "tail": tail or err.strip().splitlines()[-1][:160]})
        print(f"{'PASS' if ok else 'FAIL'} {name:6s} rc={rc} {round(time.time() - t0, 1)}s :: {tail}")
    shutil.rmtree(tmp, ignore_errors=True)
    return {"digest": digest, "files": count, "results": results}


def write_receipt(digest, files, results):
    receipt = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tree_sha256": digest,
        "files_hashed": files,
        "digest_excludes": sorted(GENERATED),
        "runner": {"python": platform.python_version(), "machine": platform.machine(),
                   "system": platform.system()},
        "environment": {"variables_kept": list(ENV_KEEP),
                        "note": "no tokens, no cloud credentials, nothing from the author's shell"},
        "steps": results,
        "ok": all(r["ok"] for r in results) and len(results) == len(STEPS),
    }
    open(RECEIPT, "w", encoding="utf-8").write(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    page = ["# 外人重跑：换一个目录、换一套环境，还成不成立", "",
            f"生成时间 {receipt['generated_at']}，运行环境 Python {receipt['runner']['python']} / "
            f"{receipt['runner']['system']}。", "",
            "做法：把仓库整棵拷到临时目录（不含 `.git`、不含任何缓存），用只保留白名单变量的干净环境，"
            "在该目录下跑四个公开入口；每一步记录退出码与输出末行；整棵树的 sha256 一并记下。", "",
            "| 步骤 | 命令 | 退出码 | 结果 | 耗时 |", "|---|---|---|---|---|"]
    for r in results:
        page.append("| {step} | `{cmd}` | {rc} | {ok} | {seconds}s |".format(
            step=r["step"], cmd=r["cmd"], rc=r["rc"], ok="PASS" if r["ok"] else "FAIL",
            seconds=r["seconds"]))
    page += ["", f"**树摘要 `{receipt['tree_sha256'][:16]}…`（{files} 个文件，排除本页与 receipt 自身）**。",
             "", "复核：`python tools/outsider_rerun.py --check`（重算摘要＋逐步判定），或 `--run` 重新跑一遍。"]
    open(PAGE, "w", encoding="utf-8").write("\n".join(page) + "\n")
    print("OUTSIDER OK" if receipt["ok"] else "OUTSIDER FAIL",
          f"tree={digest[:12]} steps={len(results)}")
    return 0 if receipt["ok"] else 1


def check():
    if not os.path.exists(RECEIPT):
        print("FAIL no receipt; run --run first")
        return 1
    receipt = json.load(open(RECEIPT, encoding="utf-8"))
    fails = []
    digest, count = tree_digest(HERE)
    if receipt.get("tree_sha256") != digest:
        fails.append(f"receipt describes tree {str(receipt.get('tree_sha256'))[:12]} but this tree hashes to {digest[:12]}")
    if receipt.get("files_hashed") != count:
        fails.append(f"file count moved: receipt {receipt.get('files_hashed')}, tree {count}")
    steps = receipt.get("steps", [])
    if len(steps) != len(STEPS):
        fails.append(f"receipt has {len(steps)} steps, expected {len(STEPS)}")
    for s in steps:
        if not s.get("ok") or s.get("rc") != 0:
            fails.append(f"step {s.get('step')} did not pass in the recorded run")
        if s.get("expect") and s["expect"] not in (s.get("tail") or ""):
            fails.append(f"step {s.get('step')} tail does not carry its marker {s['expect']!r}")
    if sorted(receipt.get("digest_excludes", [])) != sorted(GENERATED):
        fails.append("receipt excludes a different set of files than the checker")
    for f in fails:
        print("FAIL", f)
    if fails:
        print(f"\nOUTSIDER FAIL ({len(fails)} problem(s))")
        return 1
    print(f"OUTSIDER OK: receipt matches this tree ({count} files, {digest[:12]}), {len(steps)} steps passed")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="copy the tree and rerun every entry point")
    ap.add_argument("--check", action="store_true", help="verify the receipt against this tree (default)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.run:
        out = run()
        rc = write_receipt(out["digest"], out["files"], out["results"])
    else:
        rc = check()
    if args.json:
        print(json.dumps({"ok": rc == 0}, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
