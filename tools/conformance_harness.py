#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the RFC 9162 vector set against *someone else's* verifier.

Why this exists
---------------
`docs/INVITE-ONE-PAGE.md` asks an outside implementer to run our corpus and send
back five lines. That is a request for labour: they have to write glue code to
turn `expected.json` into calls into their verifier, then eyeball thirty verdicts.

This harness removes that labour. An implementation supplies **one executable**
speaking a two-line JSON protocol (see `conformance/ADAPTER-PROTOCOL.md`), and the
harness does the rest: it feeds every vector — inclusion and consistency — compares
what came back, and writes a receipt that names the adapter, the environment and
the command. The receipt is what gets filed, not the adapter author's prose.

The one design decision worth arguing about
-------------------------------------------
The harness compares **two things separately**:

  * `root_agreement` - did their fold produce the same root as ours? This is
    language-neutral: a SHA-256 tree root is a byte string, and either it matches
    or it does not.
  * `verdict_agreement` - did their verdict *word* match our verdict word? This is
    implementation-specific. One verifier says `INVALID_INCLUSION_PATH`, another
    says `E_PROOF_MISMATCH`; both may be right.

Most conformance runners compare the verdict string and call a wording difference
a failure. That makes the report useless to the implementer, because it cannot
tell "your algorithm is wrong" from "your error vocabulary is different". This
harness reports both numbers so the reader can see which one is which, and it
refuses to call a verdict-wording difference a conformance failure.

Usage
-----
    python tools/conformance_harness.py --adapter "python3 conformance/adapters/reference_python.py"
    python tools/conformance_harness.py --adapter "node my-verifier-adapter.mjs" --out receipt.json
    python tools/conformance_harness.py --adapter "./broken" --expect-disagreement   # negative control

Exit codes: 0 root agreement is total (verdict wording may differ), 1 otherwise,
2 the adapter could not be started or spoke malformed JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(REPO, "docs", "upstream-package", "scitt-rfc9162")


def load_vectors(pkg=PKG):
    with open(os.path.join(pkg, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    out = []
    for v in manifest["vectors"]:
        with open(os.path.join(pkg, v["dir"], "expected.json"), encoding="utf-8") as fh:
            exp = json.load(fh)
        if exp.get("kind") == "consistency":
            out.append({
                "id": v["id"],
                "kind": "consistency",
                "request": {
                    "kind": "consistency",
                    "old_size": exp["old_size"],
                    "new_size": exp["new_size"],
                    "old_root": exp["old_root"],
                    "new_root": exp["new_root"],
                    "consistency_path": exp["consistency_path"],
                },
                "expected_result": exp["result"],
                "expected_reconstructed": {
                    "old": exp["reconstructed_old_root"],
                    "new": exp["reconstructed_new_root"],
                },
                "expected_root_true": {"old": exp["old_root"], "new": exp["new_root"]},
            })
            continue
        out.append({
            "kind": "inclusion",
            "id": v["id"],
            "request": {
                "leaf_input_hex": exp["leaf_entry"]["leaf_input_hex"],
                "leaf_index": exp["leaf_index"],
                "tree_size": exp["tree_size"],
                "inclusion_path": exp["inclusion_path"],
                "root_true": exp["root_true"],
            },
            "expected_result": exp["result"],
            "expected_reconstructed": exp["reconstructed_root"],
            "expected_root_true": exp["root_true"],
        })
    return out


def parse_adapter(spec):
    """Turn `--adapter` into an argv list without mangling Windows paths.

    `shlex.split` applies POSIX quoting rules, which treat backslash as an escape:
    a Windows path `D:\\tmp\\adapter.py` comes back as `D:tmpadapter.py`. That is not
    a theoretical concern - it silently turned every Windows run into 30
    adapter-errors on 2026-11-20, and the negative control still "passed" because
    "no answers at all" counts as a disagreement. Hence this function, and hence the
    separate `--expect-disagreement` contract below that demands *answers* too.
    """
    if os.path.isfile(spec):
        # Launching a .py directly depends on a file association, which Windows does
        # not guarantee: on 2026-11-22 that produced `[WinError 193] %1 is not a valid
        # Win32 application` for every vector, i.e. the documented one-command path
        # failed on the platform this package is mostly developed on.
        if spec.lower().endswith(".py"):
            return [sys.executable, spec]
        return [spec]
    if os.name == "nt":
        # posix=False keeps backslashes; it may leave quotes on the tokens.
        parts = shlex.split(spec, posix=False)
        return [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p
                for p in parts]
    return shlex.split(spec)


def call_adapter(cmd, request, timeout=30):
    """Start the adapter once per vector and exchange one JSON line each way."""
    payload = json.dumps(request, ensure_ascii=False) + "\n"
    proc = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError("adapter exited %d: %s" % (proc.returncode, proc.stderr.strip()[:400]))
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        raise RuntimeError("adapter printed nothing on stdout (stderr: %s)"
                          % proc.stderr.strip()[:200])
    try:
        return json.loads(line[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("adapter's last stdout line is not JSON: %r (%s)" % (line[-1][:200], exc))


def run(cmd, vectors=None):
    vectors = vectors if vectors is not None else load_vectors()
    rows = []
    for v in vectors:
        try:
            answer = call_adapter(cmd, v["request"])
        except Exception as exc:  # noqa: BLE001 - the report must survive any adapter
            rows.append({"id": v["id"], "status": "adapter-error", "detail": str(exc)})
            continue
        got_verdict = answer.get("result")
        if v.get("kind") == "consistency":
            got_old = answer.get("reconstructed_old_root")
            got_new = answer.get("reconstructed_new_root")
            root_ok = (got_old == v["expected_reconstructed"]["old"]
                       and got_new == v["expected_reconstructed"]["new"])
            verdict_ok = (got_verdict == v["expected_result"])
            rows.append({
                "id": v["id"],
                "kind": "consistency",
                "status": "answered",
                "their_reconstructed_old_root": got_old,
                "their_reconstructed_new_root": got_new,
                "their_verdict": got_verdict,
                "root_agreement": root_ok,
                "verdict_agreement": verdict_ok,
                "their_extra": {k: val for k, val in answer.items()
                                if k not in ("reconstructed_old_root",
                                             "reconstructed_new_root", "result")},
            })
            continue
        got_root = answer.get("reconstructed_root")
        root_ok = (got_root == v["expected_reconstructed"])
        verdict_ok = (got_verdict == v["expected_result"])
        rows.append({
            "id": v["id"],
            "kind": "inclusion",
            "status": "answered",
            "their_reconstructed_root": got_root,
            "their_verdict": got_verdict,
            "root_agreement": root_ok,
            "verdict_agreement": verdict_ok,
            "their_extra": {k: val for k, val in answer.items()
                            if k not in ("reconstructed_root", "result")},
        })
    answered = [r for r in rows if r["status"] == "answered"]
    errored = [r for r in rows if r["status"] == "adapter-error"]
    receipt = {
        "schema": "conformance-receipt/1",
        "adapter_command": cmd if isinstance(cmd, str) else " ".join(cmd),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cwd": os.getcwd(),
            "utc_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "vectors": len(rows),
        "kinds": {k: sum(1 for r in rows if r.get("kind") == k)
                      for k in ("inclusion", "consistency")},
        "answered": len(answered),
        "adapter_errors": len(errored),
        "root_agreement": sum(1 for r in answered if r["root_agreement"]),
        "verdict_agreement": sum(1 for r in answered if r["verdict_agreement"]),
        "root_mismatches": [r["id"] for r in answered if not r["root_agreement"]],
        "verdict_wording_only": [r["id"] for r in answered
                                 if r["root_agreement"] and not r["verdict_agreement"]],
        "adapter_errors_detail": errored,
        "rows": rows,
        "how_to_read": {
            "root_agreement": ("Language-neutral. Their fold produced the same root as the "
                               "committed vector. A mismatch here is an algorithmic difference "
                               "and worth a report."),
            "verdict_agreement": ("Implementation-specific wording. A mismatch here with root_agreement=True "
                                  "means both computed the same root and named the outcome "
                                  "differently - that is a vocabulary difference, not a failure."),
        },
    }
    return receipt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter", required=True, help="command speaking the adapter protocol")
    ap.add_argument("--out", default=None, help="write the receipt JSON here (default: stdout)")
    ap.add_argument("--only", action="append", default=None, help="restrict to these vector ids")
    ap.add_argument("--expect-disagreement", action="store_true",
                    help="negative control: pass only if at least one root mismatch is reported")
    a = ap.parse_args(argv)

    vectors = load_vectors()
    if a.only:
        vectors = [v for v in vectors if v["id"] in set(a.only)]
    if not vectors:
        print("[FATAL] no vectors selected")
        return 2

    try:
        cmd = parse_adapter(a.adapter)
    except ValueError as exc:
        print("[FATAL] cannot parse --adapter: %s" % exc)
        return 2

    try:
        receipt = run(cmd, vectors)
    except Exception as exc:  # noqa: BLE001 - a broken adapter is a finding, not a crash
        print("[FATAL] harness could not run: %s" % exc)
        return 2

    text = json.dumps(receipt, ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")

    print("=" * 78)
    print("conformance receipt")
    print("adapter : %s" % receipt["adapter_command"])
    print("vectors : %d (inclusion %d / consistency %d)   answered: %d   adapter errors: %d"
          % (receipt["vectors"], receipt["kinds"]["inclusion"], receipt["kinds"]["consistency"],
             receipt["answered"], receipt["adapter_errors"]))
    print("root agreement    : %d/%d" % (receipt["root_agreement"], receipt["answered"]))
    print("verdict agreement : %d/%d" % (receipt["verdict_agreement"], receipt["answered"]))
    if receipt["root_mismatches"]:
        print("root mismatches   : %s" % ", ".join(receipt["root_mismatches"]))
    if receipt["verdict_wording_only"]:
        print("wording only      : %s" % ", ".join(receipt["verdict_wording_only"]))
    print("=" * 78)

    if a.expect_disagreement:
        # A control that disagrees because the adapter never answered proves nothing:
        # that is the trap a broken adapter path fell into on 2026-11-20 (30
        # adapter-errors counted as "caught a disagreement"). Demand answers first.
        if receipt["adapter_errors"]:
            print("VERDICT: CONTROL-VACUOUS - the adapter never answered; fix the command")
            return 2
        if receipt["root_mismatches"]:
            print("VERDICT: CONTROL-OK - the harness caught a computed disagreement")
            return 0
        print("VERDICT: CONTROL-FAILED - an adapter that must disagree agreed with everything")
        return 1

    if receipt["adapter_errors"]:
        print("VERDICT: ADAPTER-BROKEN - %d vector(s) produced no answer" % receipt["adapter_errors"])
        return 1
    if receipt["root_agreement"] == receipt["answered"]:
        print("VERDICT: ROOTS-AGREE - every root matches%s"
              % (" (verdict wording differs on some vectors; that is not a conformance failure)"
                 if receipt["verdict_agreement"] < receipt["answered"] else ""))
        return 0
    print("VERDICT: ROOT-DISAGREEMENT - report it; the vector or their fold is wrong")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
