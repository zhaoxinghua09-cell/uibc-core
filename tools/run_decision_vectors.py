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


def _strip_absent(tokens, overlay, anchor):
    """Drop the flags for files this case does not have.

    The convention is the ordinary one: `--flag {value}` (the flag token is
    removed together with its value) or `--flag={value}` (that one token is
    removed). Anything else - a value the command needs but the case cannot
    supply - is refused rather than guessed, because scoring a command that
    silently lost an argument would invent a result.
    """
    out = []
    for tok in tokens:
        missing = ("{overlay}" in tok and overlay is None) or \
                  ("{anchor}" in tok and anchor is None)
        if missing:
            if tok.strip() in ("{overlay}", "{anchor}"):
                if out and out[-1].startswith("-") and "{" not in out[-1]:
                    out.pop()
                continue
            continue    # --flag={value} form: drop this token only
        out.append(tok)
    return out


def external_gate(template, plain_template=None):
    """Run somebody else's gate.

    Flags for files a case does not carry are dropped by `_strip_absent`, so
    one command serves all seven cases even when the overlay and the anchor are
    optional flags. `plain_template` stays as an escape hatch for implementations
    whose interface does not follow `--flag value`.
    """
    def run(pkg, overlay=None, anchor=None):
        cmd = template
        if (overlay is None and anchor is None) and plain_template:
            cmd = plain_template
        cmd = cmd.replace("{pkg}", pkg)
        if overlay is not None:
            cmd = cmd.replace("{overlay}", overlay)
        if anchor is not None:
            cmd = cmd.replace("{anchor}", anchor)
        tokens = _strip_absent(cmd.split(), overlay, anchor)
        if any("{" in t for t in tokens):
            return {"decision": None, "exit_code": None,
                    "error": "could not fill every placeholder: %s" % " ".join(tokens)}
        proc = subprocess.run(tokens, capture_output=True, text=True, timeout=120)
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
    ap.add_argument("--gate-plain", default=None,
                    help="the same command for cases with no overlay and no anchor, "
                         "e.g. \"python3 my_gate.py {pkg}\".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not os.path.isdir(SUITE):
        print("SUITE MISSING: %s (run tools/build_decision_vectors.py)" % SUITE,
              file=sys.stderr)
        return 2
    manifest = load_manifest()
    runner = external_gate(a.gate, a.gate_plain) if a.gate else our_gate
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
