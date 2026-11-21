# -*- coding: utf-8 -*-
"""测试台账生成器：把"测试数字"从文档里搬进机器可核对的 JSON。

解决的问题（任务书 P1-1）：
  - EVIDENCE-INDEX 手工维护测试数量 → 必然漂移
  - 543 / 527 / 328 等历史数字找不到对应命令
  - skip 数量从不展开，只报一个总数

产出：一条可复算的记录
  {commit, branch, dirty, python, pytest, platform, deps, command,
   collected, passed, failed, errors, skipped, skipped_detail, duration}

用法：
  python tools/gen_test_ledger.py --repo . --out evidence/test-ledger.json
  python tools/gen_test_ledger.py --repo . --out ... --scope tests      # 只跑 tests/
  python tools/gen_test_ledger.py --repo . --out ... --unittest         # 另附 unittest 口径
"""
import argparse
import datetime
import hashlib
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def sh(cmd, cwd=None, timeout=600):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, shell=False)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", "command not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def _git_exe():
    """Windows 上 git 常是 git.CMD（批处理），subprocess 直调会 FileNotFoundError。"""
    import shutil
    for cand in ("git.exe", "git"):
        p = shutil.which(cand)
        if p:
            return p, False
    p = shutil.which("git")          # 可能是 .CMD / .BAT
    if p:
        return p, True
    return None, False


def git_meta(repo):
    git, needs_shell = _git_exe()
    if not git:
        return {"commit": None, "branch": None, "dirty": None, "git_exe": None}

    def run(args):
        try:
            r = subprocess.run([git] + args, capture_output=True, text=True,
                               timeout=30, shell=needs_shell)
            return r.returncode, r.stdout
        except Exception:
            return 1, ""

    rc, out = run(["-C", str(repo), "rev-parse", "HEAD"])
    head = out.strip() if rc == 0 else None
    rc2, out2 = run(["-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"])
    branch = out2.strip() if rc2 == 0 else None
    rc3, out3 = run(["-C", str(repo), "status", "--porcelain"])
    dirty = bool(out3.strip()) if rc3 == 0 else None
    return {"commit": head, "branch": branch, "dirty": dirty, "git_exe": git}


def deps_snapshot():
    rc, out, _ = sh([sys.executable, "-m", "pip", "freeze"])
    if rc != 0:
        return []
    keys = ("pytest", "cryptography", "jsonschema", "pydantic", "mcp", "fastmcp")
    return [ln for ln in out.splitlines()
            if any(ln.lower().startswith(k) for k in keys)]


def parse_junit(path):
    tree = ET.parse(path)
    suite = tree.getroot().find("testsuite") or tree.getroot()
    totals = {k: int(float(suite.get(k, 0))) for k in
              ("tests", "failures", "errors", "skipped", "time")}
    skipped, failed = [], []
    for tc in suite.iter("testcase"):
        for sk in tc.findall("skipped"):
            skipped.append({"test": f"{tc.get('classname')}::{tc.get('name')}",
                            "reason": (sk.get("message") or "").strip()[:200]})
        for f in list(tc.findall("failure")) + list(tc.findall("error")):
            failed.append({"test": f"{tc.get('classname')}::{tc.get('name')}",
                           "message": (f.get("message") or "").strip()[:200]})
    return totals, skipped, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="test-ledger.json")
    ap.add_argument("--scope", default="", help="限定的测试路径，如 tests")
    ap.add_argument("--unittest", action="store_true", help="额外跑 unittest 口径")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    xml = Path(a.out).with_suffix(".junit.xml")
    xml.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider",
           f"--junit-xml={xml}"]
    if a.scope:
        cmd.append(a.scope)
    started = datetime.datetime.now(datetime.timezone.utc)
    rc, out, err = sh(cmd, cwd=repo, timeout=1800)
    ended = datetime.datetime.now(datetime.timezone.utc)

    ledger = {
        "schema": "test-ledger/1",
        "generated_at": started.isoformat(),
        "finished_at": ended.isoformat(),
        "duration_seconds": round((ended - started).total_seconds(), 1),
        "scope": a.scope or "(whole repo)",
        "command": " ".join(cmd).replace(str(repo), ".").replace(str(xml), "…"),
        "git": git_meta(repo),
        "env": {
            "python": sys.version.split()[0],
            "pytest": _pytest_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "deps": deps_snapshot(),
        "exit_code": rc,
    }

    if xml.exists():
        totals, skipped, failed = parse_junit(xml)
        collected = totals["tests"]
        ledger["totals"] = {
            "collected": collected,
            "passed": collected - totals["failures"] - totals["errors"] - totals["skipped"],
            "failed": totals["failures"],
            "errors": totals["errors"],
            "skipped": totals["skipped"],
            "duration_seconds": totals["time"],
        }
        ledger["skipped_detail"] = skipped
        ledger["failed_detail"] = failed
    else:
        ledger["totals"] = None
        ledger["stderr_tail"] = err.strip().splitlines()[-5:]

    if a.unittest:
        rc_u, out_u, err_u = sh([sys.executable, "-m", "unittest", "discover",
                                 "-s", "tests", "-t", "."], cwd=repo, timeout=1800)
        tail = [ln.strip() for ln in (err_u or out_u).splitlines() if ln.strip()]
        ledger["unittest"] = {"exit_code": rc_u, "summary_tail": tail[-3:]}

    if ledger.get("totals"):
        # 台账自身摘要，用于比对是否被改过
        body = json.dumps({k: ledger[k] for k in ("totals", "git", "scope")},
                          sort_keys=True, ensure_ascii=False)
        ledger["ledger_digest"] = hashlib.sha256(body.encode()).hexdigest()

    Path(a.out).write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    t = ledger.get("totals") or {}
    print(f"scope={ledger['scope']}  commit={(ledger['git']['commit'] or '?')[:10]}"
          f"  dirty={ledger['git']['dirty']}")
    print(f"collected={t.get('collected')}  passed={t.get('passed')}  failed={t.get('failed')}"
          f"  errors={t.get('errors')}  skipped={t.get('skipped')}  ({ledger['duration_seconds']}s)")
    if ledger.get("skipped_detail"):
        print(f"skipped（{len(ledger['skipped_detail'])} 条）：")
        for s in ledger["skipped_detail"][:5]:
            print(f"  - {s['test']}  |  {s['reason'][:80]}")
    print(f"→ {a.out}")
    return 0


def _pytest_version():
    try:
        import pytest
        return pytest.__version__
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
