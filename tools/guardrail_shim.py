#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁 shim PoC：一次工具调用 -> 一个证据包 -> 一个准入决定。

为什么不是"又一个 MCP 网关"：
  2026-10~11 已经出现一批 MCP 侧门禁（AgentGuard / Warden / McpVanguard /
  ScopeGate / agentgateway），它们都在做"每次调用记一条不可篡改日志 + 按策略
  放行"。差别不在拦截，而在**事后怎么被第三方独立复判**：它们给出的是网关自己
  的日志，我们给出的是一个能被陌生人离线验证、且把"没查清"与"查清了不通过"
  分开记录的包。本 PoC 只验证后半段是否真的能驱动一次准入决定。

锚定规则（draft-maintainer-1f916-agent-record-01 §3.6）：
  "一次验证运行只有在该次运行中至少有一个密钥来自被测物无法控制的通道时，
  才算 ANCHORED。" 因此本 PoC 的策略不是 `result == PASS` 就放行，而是
  `result == PASS and trust_level == anchored`——unattested/unanchored 一律 HOLD。
  这把 mutation benchmark 里 M17 的"open 模式 PASS"从"假接受"改判成"必须人工介入"。

用法： python tools/guardrail_shim.py
结果： tools/out/guardrail_result.json
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from uibc_core import cli as ucli  # noqa: E402
from uibc_core import ed25519  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

OUT = os.path.join(ROOT, "tools", "out")
DEMO_SEED = bytes(range(32))
POLICY = {
    "name": "guardrail-v1",
    "allow_when": {"result": "PASS", "trust_level": "anchored"},
    "hold_when": {"result": "PASS", "trust_level": ["unanchored", "unattested"]},
    "deny_when": {"result": ["FAIL", "INCONCLUSIVE"]},
}


def _a(**kw):
    return type("A", (), kw)()


def build_pkg(path, key_path=None, *, tamper=False, extra_event_gap=False,
              custody="hsm"):
    ucli.cmd_init(_a(path=path))
    ucli.cmd_register(_a(path=path, agent_id="shim-agent", owner="ops",
                         agent_type="software-agent", version="1.0.0",
                         principal_type="SERVICE",
                         logical_agent_id="shim-agent", run_id="run-1",
                         key_custody=custody))
    src = os.path.join(os.path.dirname(path), "tool_call.log")
    with open(src, "w", encoding="utf-8", newline="\n") as f:
        f.write("2026-11-17T00:00:00Z TOOL refund_order order=8842 amount=120.00\n")
    if extra_event_gap:
        # a gap in the lifecycle sequence is GAR-08's suppression indicator
        ev = {"type": "ACTIVATE", "sequence_number": 5,
              "at": "2026-11-17T00:00:01Z", "actor": "ops"}
        lp = os.path.join(path, "lifecycle.json")
        with open(lp, encoding="utf-8") as f:
            lc = json.load(f)
        lc["events"].append(ev)
        with open(lp, "w", encoding="utf-8") as f:
            json.dump(lc, f, indent=2)
    ucli.cmd_evidence(_a(path=path, type="ACTION", file=src,
                        media_type="text/plain", note=""))
    if tamper:
        ev_dir = os.path.join(path, "evidence", "files")
        target = os.path.join(ev_dir, sorted(os.listdir(ev_dir))[0])
        with open(target, "a", encoding="utf-8") as f:
            f.write("refund 9999.00\n")
    ucli.cmd_submit(_a(path=path, key=key_path))
    return path


def decide(report):
    """Policy evaluation. Deliberately NOT 'PASS means allow'."""
    result, trust = report["result"], report["trust_level"]
    if result in POLICY["deny_when"]["result"]:
        failed = [c["id"] for c in report["checks"] if c["result"] != "PASS"]
        return "DENY", f"{result} at {','.join(failed) or 'no check'}"
    if result == "PASS" and trust == "anchored":
        return "ALLOW", "PASS + anchored (key reached verifier out-of-band)"
    return "HOLD", (f"{result} but {trust}: internal consistency only, "
                    f"require an out-of-band key or human review")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(OUT, "guardrail_result.json"))
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="shim-")
    key_path = os.path.join(tmp, "owner.key")
    with open(key_path, "w", encoding="ascii") as f:
        f.write("ed25519:" + DEMO_SEED.hex())
    pub = ed25519.publickey(DEMO_SEED)

    cases = []

    def run(name, expect, pkg, *, pinned):
        rep = verify(pkg, pubkey=pub if pinned else None)
        action, why = decide(rep)
        got = {"result": rep["result"], "trust_level": rep["trust_level"], "action": action}
        ok = got["action"] == expect
        cases.append({"case": name, "expect": expect, **got, "ok": ok,
                      "why": why, "checks_failed": [c["id"] for c in rep["checks"]
                                                    if c["result"] != "PASS"]})
        print(("  [OK] " if ok else "  [XX] ") + f"{name}: {got['action']} "
              f"({got['result']}/{got['trust_level']}) — {why}")

    p1 = build_pkg(os.path.join(tmp, "1.uibc"), key_path)
    run("clean + pinned key", "ALLOW", p1, pinned=True)
    run("clean, key read from package", "HOLD", p1, pinned=False)

    p2 = build_pkg(os.path.join(tmp, "2.uibc"), key_path, tamper=True)
    run("evidence tampered after seal", "DENY", p2, pinned=True)

    p3 = build_pkg(os.path.join(tmp, "3.uibc"), None)
    run("unsigned / unattested", "DENY", p3, pinned=True)

    p4 = build_pkg(os.path.join(tmp, "4.uibc"), key_path, extra_event_gap=True)
    run("lifecycle sequence gap", "DENY", p4, pinned=True)

    summary = {"total": len(cases), "ok": sum(1 for c in cases if c["ok"]),
               "policy": POLICY,
               "anchor_rule": "draft-maintainer-1f916-agent-record-01 S3.6"}
    doc = {"meta": {"probe": "guardrail-shim", "uibc_core": ROOT,
                    "generated_at_utc": __import__("time").strftime(
                        "%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())},
           "policy": POLICY, "cases": cases, "summary": summary}
    with open(a.json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"\n{summary['ok']}/{summary['total']} 符合策略预期")
    print("RESULT_JSON=" + a.json)
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if summary["ok"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
