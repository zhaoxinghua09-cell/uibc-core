#!/usr/bin/env python3
"""Run the decision vectors against any gate, ours or someone else's.

The 36-case conformance suite checks `verify()`. This checks the layer above:
does an implementation answer ALLOW / DENY / HOLD the same way, on the same
packages, with the same overlays? That is the layer where a revocation can be
silently ignored, so it is the layer a second implementer most needs vectors for.

Contract for an external gate command (placeholders are substituted):

    --gate "python3 my_gate.py {pkg} --revocation {overlay} --pubkey {anchor}"

It must print JSON containing `decision` (one of ALLOW, ALLOW_DISPUTED, DENY,
HOLD). `exit_code` is compared too when present; otherwise the process exit
code is used, so `exit 0/2/3` implementations are accepted as well.

Exit codes: 0 every case matched, 1 at least one case diverged, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, ".."))
for _p in (_REPO, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SUITE = os.path.join(_REPO, "conformance", "decisions")


def load_manifest():
    with open(os.path.join(SUITE, "manifest.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def our_gate(pkg, overlay=None, anchor=None):
    from uibc_core.gate import gate
    key = None
    pubkey = None
    if anchor:
        with open(anchor, "r", encoding="utf-8") as f:
            pubkey = bytes.fromhex(f.read().strip())
    report = gate(pkg, key=key, pubkey=pubkey, revocation_path=overlay)
    return {"decision": report["decision"], "exit_code": report["exit_code"]}


def external_gate(template):
    def run(pkg, overlay=None, anchor=None):
        cmd = template.replace("{pkg}", pkg)
        if "{overlay}" in cmd:
            if overlay is None:
                return {"decision": None, "exit_code": None,
                        "error": "case needs an overlay but the command wants one"}
            cmd = cmd.replace("{overlay}", overlay)
        if "{anchor}" in cmd:
            if anchor is None:
                return {"decision": None, "exit_code": None,
                        "error": "case needs an anchor but the command wants one"}
            cmd = cmd.replace("{anchor}", anchor)
        proc = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=120)
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"decision": None, "exit_code": proc.returncode,
                    "error": "output was not JSON: %s" % proc.stdout[-200:]}
        if "exit_code" not in out:
            out["exit_code"] = proc.returncode
        return out
    return run


def judge(case, got):
    want_d, want_x = case["expect"]["decision"], case["expect"]["exit"]
    got_d, got_x = got.get("decision"), got.get("exit_code")
    ok = (got_d == want_d) and (got_x == want_x)
    return {"id": case["id"], "what": case["what"], "ok": ok,
            "want": "%s/%s" % (want_d, want_x),
            "got": "%s/%s" % (got_d, got_x),
            "note": got.get("error", "")}


def main(argv=None):
    ap = argparse.ArgumentParser(description="run the decision vectors")
    ap.add_argument("--gate", default=None,
                    help='external gate command, e.g. "python3 my_gate.py {pkg} '
                         '--revocation {overlay} --pubkey {anchor}"; omit to test ours')
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.isdir(SUITE):
        print("SUITE MISSING: %s (run tools/build_decision_vectors.py)" % SUITE,
              file=sys.stderr)
        return 2
    manifest = load_manifest()
    runner = external_gate(a.gate) if a.gate else our_gate
    rows = []
    for case in manifest["cases"]:
        pkg = os.path.join(SUITE, case["pkg"])
        overlay = os.path.join(SUITE, case["overlay"]) if case.get("overlay") else None
        anchor = os.path.join(SUITE, case["anchor"]) if case.get("anchor") else None
        rows.append(judge(case, runner(pkg, overlay, anchor)))

    passed = sum(1 for r in rows if r["ok"])
    if a.json:
        print(json.dumps({"passed": passed, "total": len(rows), "rows": rows},
                         indent=2, ensure_ascii=False))
    else:
        print("# Decision vectors")
        print("")
        print("| case | what | expected | got | result |")
        print("|---|---|---|---|---|")
        for r in rows:
            print("| %s | %s | `%s` | `%s` | **%s** |"
                  % (r["id"], r["what"], r["want"], r["got"],
                     "MATCH" if r["ok"] else "MISMATCH"))
        print("")
        print("%d/%d cases matched" % (passed, len(rows)))
        if passed != len(rows):
            print("")
            print("A permissive gate cannot pass this suite: only case 01 expects "
                  "ALLOW, the other six must be refused, and two of those must be "
                  "HOLD rather than DENY — 'cannot verify' is not 'not revoked'.")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
