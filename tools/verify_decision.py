"""Recompute somebody else's admission decision and say MATCH or name the field.

A published decision is worth what a reader can independently redo. This tool
takes a UIBC package and a decision receipt, redoes the work — package root,
gate, overlays, disclosure row — and compares the two:

* receipt self-consistency first (`receipt_sha256` over canonical bytes),
* then `package_root` (the package you were handed is the package decided on),
* then the decision fields, one per line.

Exit codes: 0 all fields MATCH, 1 any MISMATCH, 2 usage or missing input.

What it does not do: it does not decide whether ALLOW was *correct*. It decides
whether the receipt describes what the gate says now, on these bytes. A receipt
that matches a DENY is as valid as one that matches an ALLOW — the point is that
the number and the bytes agree.

Usage:

    python tools/verify_decision.py --package /tmp/admit --receipt /tmp/admit.decision.json \
        --python .../python --pubkey owner.key.pub
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import admit_package as ap  # noqa: E402  (sibling module, same directory)


FIELDS = ("decision", "reason", "verify_result", "gate_version",
          "verifier_version", "revocation", "dispute")


class ReceiptError(Exception):
    pass


def load_receipt(path):
    with open(path, "r", encoding="utf-8") as f:
        r = json.load(f)
    if r.get("tool") != "decision_receipt/1.0":
        raise ReceiptError("not a decision_receipt/1.0 file: %r" % r.get("tool"))
    return r


def receipt_integrity(receipt):
    """Return (ok, computed) for the receipt's own hash."""
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    computed = hashlib.sha256(ap.canonical_bytes(body)).hexdigest()
    return computed == receipt.get("receipt_sha256"), computed


def recompute(pkg, py, pubkey=None):
    gate = ap._gate_dict(py, pkg, pubkey)
    return {
        "package_root": ap.package_root(pkg),
        "gate": gate,
    }


def compare(pkg, receipt, py, pubkey=None):
    """Field-by-field comparison. Returns (rows, ok)."""
    rows = []
    ok, computed = receipt_integrity(receipt)
    rows.append(("receipt_sha256", receipt.get("receipt_sha256"), computed, ok))
    live = recompute(pkg, py, pubkey)
    rows.append(("package_root", receipt.get("package_root"),
                 live["package_root"],
                 receipt.get("package_root") == live["package_root"]))
    gate = live["gate"]
    for f in FIELDS:
        want = receipt.get(f)
        got = gate.get(f)
        if f == "verifier_version":
            got = (gate.get("verify_report") or {}).get("verifier_version")
        rows.append((f, want, got, want == got))
    all_ok = all(r[3] for r in rows)
    return rows, all_ok


def _fmt(v):
    s = json.dumps(v, sort_keys=True, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= 72 else s[:69] + "..."


def render(rows, ok, receipt_path, pkg):
    lines = ["# Decision recomputation", ""]
    lines.append("| field | receipt says | this machine says | result |")
    lines.append("|---|---|---|---|")
    for name, want, got, good in rows:
        lines.append("| %s | `%s` | `%s` | **%s** |"
                     % (name, _fmt(want), _fmt(got), "MATCH" if good else "MISMATCH"))
    lines.append("")
    lines.append("receipt: `%s`" % receipt_path)
    lines.append("package: `%s`" % pkg)
    lines.append("")
    if ok:
        lines.append("**MATCH** — every field recomputed on these bytes. This says the receipt "
                     "describes what the gate says now; it does not say the original ALLOW/DENY "
                     "was correct, and it does not say the artifact is good.")
    else:
        bad = [r[0] for r in rows if not r[3]]
        lines.append("**MISMATCH** — these fields differ: %s" % ", ".join(bad))
        if "receipt_sha256" in bad:
            lines.append("")
            lines.append("The receipt's own hash does not cover its contents: it was edited after "
                         "it was written. Nothing else in it can be trusted until that is resolved.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="recompute a published admission decision")
    p.add_argument("--package", required=True)
    p.add_argument("--receipt", required=True)
    p.add_argument("--python", default=sys.executable,
                   help="interpreter that can import uibc_core")
    p.add_argument("--pubkey", default=None,
                   help="pinned public key; without it the gate verifies unanchored")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        receipt = load_receipt(a.receipt)
    except (OSError, ValueError, ReceiptError) as e:
        print("RECEIPT ERROR: %s" % e, file=sys.stderr)
        return 2
    if not os.path.isdir(a.package):
        print("RECEIPT ERROR: package directory not found: %s" % a.package, file=sys.stderr)
        return 2
    rows, ok = compare(a.package, receipt, a.python, a.pubkey)
    if a.json:
        print(json.dumps({"ok": ok,
                          "fields": [{"field": n, "receipt": w, "live": g, "match": o}
                                     for n, w, g, o in rows]},
                         indent=2, sort_keys=True, ensure_ascii=False, default=str))
    else:
        print(render(rows, ok, a.receipt, a.package))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
