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
    """Field-by-field comparison against the sealed package. Returns (rows, ok)."""
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
    all_ok = all(r[3] for r in rows if r[3] is not None)
    return rows, all_ok


def compare_artifact(artifact, receipt):
    """Check the receipt against the artifact alone — what a stranger holds.

    Somebody who downloaded a wheel has the file and (maybe) our published
    receipt; they do not have the sealed package we built around it. Four
    fields are still checkable from the file: its name, its bytes, its sha256
    and the member count. The rest require the package, and this function
    marks them NOT CHECKABLE rather than guessing.
    """
    rows = []
    ok, computed = receipt_integrity(receipt)
    rows.append(("receipt_sha256", receipt.get("receipt_sha256"), computed, ok))
    kind, digest, size, members = ap.inventory(artifact)
    subject = receipt.get("subject") or {}
    rows.append(("subject.sha256", subject.get("sha256"), digest,
                 subject.get("sha256") == digest))
    rows.append(("subject.bytes", subject.get("bytes"), size,
                 subject.get("bytes") == size))
    rows.append(("subject.members", subject.get("members"), len(members),
                 subject.get("members") == len(members)))
    rows.append(("subject.name", subject.get("name"), os.path.basename(artifact),
                 # A renamed file is the same artifact: a download called
                 # "pkg (1).whl" must not fail the check. The name is recorded
                 # as a note, and the bytes decide.
                 "note" if subject.get("name") != os.path.basename(artifact) else True))
    for f in ("package_root",) + FIELDS:
        rows.append((f, receipt.get(f), "needs the sealed package", None))
    all_ok = all(r[3] for r in rows if r[3] in (True, False))
    return rows, all_ok


def _fmt(v):
    if v is None:
        return "not checked"
    s = json.dumps(v, sort_keys=True, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= 72 else s[:69] + "..."


def _verdict(good):
    return {True: "MATCH", False: "MISMATCH", None: "NOT CHECKABLE",
            "note": "NOTE"}[good]


def render(rows, ok, receipt_path, subject_path, subject_label):
    lines = ["# Decision recomputation", ""]
    lines.append("| field | receipt says | this machine says | result |")
    lines.append("|---|---|---|---|")
    for name, want, got, good in rows:
        lines.append("| %s | `%s` | `%s` | **%s** |"
                     % (name, _fmt(want), _fmt(got), _verdict(good)))
    lines.append("")
    lines.append("receipt: `%s`" % receipt_path)
    lines.append("%s: `%s`" % (subject_label, subject_path))

    lines.append("")
    unchecked = [r[0] for r in rows if r[3] is None]
    notes = [r[0] for r in rows if r[3] == "note"]
    if ok and notes:
        lines.append("A NOTE, not a failure: %s differs. A renamed download is the same "
                     "artifact — the bytes are what the receipt pins." % ", ".join(notes))
    if ok and unchecked:
        lines.append("**MATCH on every checkable field** — %d field(s) could not be checked without "
                     "the sealed package: %s. What is proven here is narrower than the full "
                     "recomputation, and the report says so instead of printing a bare MATCH."
                     % (len(unchecked), ", ".join(unchecked)))
    elif ok:
        lines.append("**MATCH** — every field recomputed on these bytes. This says the receipt "
                     "describes what the gate says now; it does not say the original ALLOW/DENY "
                     "was correct, and it does not say the artifact is good.")
    else:
        bad = [r[0] for r in rows if r[3] is False]
        lines.append("**MISMATCH** — these fields differ: %s" % ", ".join(bad))
        if "receipt_sha256" in bad:
            lines.append("")
            lines.append("The receipt's own hash does not cover its contents: it was edited after "
                         "it was written. Nothing else in it can be trusted until that is resolved.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="recompute a published admission decision")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--package", help="the sealed package the decision was made on")
    g.add_argument("--artifact", help="just the artifact (wheel/zip/tar/file): the stranger's case")
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
    if a.artifact:
        if not os.path.exists(a.artifact):
            print("RECEIPT ERROR: artifact not found: %s" % a.artifact, file=sys.stderr)
            return 2
        rows, ok = compare_artifact(a.artifact, receipt)
        label, subject = "artifact", a.artifact
    else:
        if not os.path.isdir(a.package):
            print("RECEIPT ERROR: package directory not found: %s" % a.package, file=sys.stderr)
            return 2
        rows, ok = compare(a.package, receipt, a.python, a.pubkey)
        label, subject = "package", a.package
    if a.json:
        print(json.dumps({"ok": ok, "mode": label,
                          "fields": [{"field": n, "receipt": w, "live": g, "match": o}
                                     for n, w, g, o in rows]},
                         indent=2, sort_keys=True, ensure_ascii=False, default=str))
    else:
        print(render(rows, ok, a.receipt, subject, label))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
