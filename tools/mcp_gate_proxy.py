#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A working MCP gate adapter - not a gateway, and it says so.

APort/OAP shipped an allowlist that sits in front of MCP tool calls and is wired
into Claude Code, Cursor, Goose, Codex and Gemini CLI. We had a gate *policy* and
no adapter, so "integration breadth" was zero. This is the smallest honest
adapter: a JSON-RPC proxy over stdio that decides per `tools/call`, records every
decision (including refusals - the phantom entry COGITATOR asks for), and can
refuse with a rule id the caller can quote.

    python tools/mcp_gate_proxy.py --log tools/out/proxy_phantom.jsonl
        (reads JSON-RPC lines on stdin; write one line per request on stdout)

Then, in an MCP client config, replace the upstream command with this proxy:
    command = python, args = [tools/mcp_gate_proxy.py, --upstream, <server cmd>]

What it is: one process, one policy file, one append-only decision log.
What it is NOT: a security boundary. It runs in the same trust domain as the
caller and can be bypassed by anyone who can edit the config. Do not describe it
as a gateway.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from uibc_core.phantom import PhantomLog, request_digest  # noqa: E402

DEFAULT_POLICY = [
    # (rule_id, substring(s), reason) - matched case-insensitively on the
    # serialized arguments. Deliberately coarse: this is a demo of the wiring,
    # not a substitute for a real policy engine.
    ("G-DESTRUCT", ["rm -rf", "rd /s /q", "del /f /s /q", "mkfs"], "destructive command"),
    ("G-EXFIL", ["curl | sh", "curl|sh", "wget | sh", "base64 -d | sh"], "remote pipe execution"),
    ("G-SECRET", ["id_rsa", ".ssh/", "aws_secret", "api_key=", "sk-"], "credential access"),
    ("G-ENC", ["powershell -enc", "powershell -e ", "bash -c \"$("], "encoded command"),
]


def decide(method, params, policy):
    if method != "tools/call":
        return "ALLOW", "not-a-tool-call", "not a tools/call request"
    blob = json.dumps(params, ensure_ascii=False).lower()
    for rule_id, needles, reason in policy:
        for n in needles:
            if n.lower() in blob:
                return "DENY", rule_id, reason
    return "ALLOW", "G-NONE", "no rule matched"


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--log", default=os.path.join(ROOT, "tools", "out",
                                                  "proxy_phantom.jsonl"))
    ap.add_argument("--dry-run", action="store_true",
                    help="decide and log, but answer ALLOW without forwarding")
    args = ap.parse_args(argv)

    log = PhantomLog(args.log)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            print(json.dumps({"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32700, "message": "parse error"}}),
                  flush=True)
            continue
        method = msg.get("method", "")
        params = msg.get("params", {})
        decision, rule_id, reason = decide(method, params, DEFAULT_POLICY)
        log.append(decision=decision, rule_id=rule_id, reason=reason,
                   request_digest=request_digest({"method": method, "params": params}),
                   executed=(decision == "ALLOW"), at=_utcnow())
        if decision == "DENY":
            print(json.dumps({"jsonrpc": "2.0", "id": msg.get("id"),
                              "error": {"code": -32001,
                                        "message": "uibc gate: %s (%s)" % (reason, rule_id)}},
                             ensure_ascii=False), flush=True)
        elif args.dry_run:
            print(json.dumps({"jsonrpc": "2.0", "id": msg.get("id"),
                              "result": {"gate": "allow", "rule_id": rule_id}},
                             ensure_ascii=False), flush=True)
        else:
            # No upstream wired: answer with the gate's own verdict so the demo
            # is honest about not having forwarded anything.
            print(json.dumps({"jsonrpc": "2.0", "id": msg.get("id"),
                              "result": {"gate": "allow", "rule_id": rule_id,
                                         "forwarded": False,
                                         "note": "no upstream configured"}},
                             ensure_ascii=False), flush=True)
    return 0


def _utcnow():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    sys.exit(main())
