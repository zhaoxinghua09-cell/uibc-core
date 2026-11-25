"""An external run that can be checked, not just believed.

`stranger_competitor_check.py --receipt out.json` writes a receipt of what the
runner's machine actually computed. This reads it back and recomputes every
number on *this* machine, so a pasted receipt is evidence rather than a claim:

  * the tool's own sha256 must match the file being run here (a receipt from a
    different version is not a receipt of this code);
  * the receipt must carry its own integrity digest, otherwise one number can be
    edited without trace;
  * every count, the verdict and the exit code must equal what this machine
    recomputes from the same corpus.

What it deliberately does not do: it does not tell you *who* ran it. A self-run
receipt has no identity in it, so this verifier can confirm the numbers and
cannot confirm the person. That is why the external-run record in
docs/EXTERNAL-RUNS.json stays at zero until a receipt arrives from someone we did
not run it for.

Usage
-----
  python tools/verify_external_run_receipt.py --receipt out.json --dir <corpus>
  python tools/verify_external_run_receipt.py --receipt out.json --selftest
"""

import argparse
import hashlib
import json
import os
import platform
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stranger_competitor_check as stranger  # noqa: E402

FORMAT = "uibc-external-run/1"
HERE = os.path.dirname(os.path.abspath(__file__))


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def canonical(body):
    """Sorted, fixed separators: the same bytes on every machine."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def build_receipt(out, tool_path=None):
    """The receipt body plus its own digest. Callers do not need to know the layout."""
    tool_path = tool_path or os.path.join(HERE, "stranger_competitor_check.py")
    body = {
        "format": FORMAT,
        "tool_sha256": _sha256_file(tool_path),
        "upstream": out["upstream"],
        "source": out["source"],
        "bytes": {"checked": out["bytes"]["checked"],
                  "match": out["bytes"]["match"]},
        "sweep": out["sweep"],
        "control": out["control"],
        "ledger": out["ledger"],
        "ledger_skipped": out.get("ledger_skipped"),
        "sigstore_inclusion": out["sigstore_inclusion"],
        "diffs": out["diffs"],
        "verdict": out["verdict"],
        "code": out["code"],
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "cryptography": bool(_have_crypto()),
        },
    }
    body["receipt_sha256"] = hashlib.sha256(canonical(body)).hexdigest()
    return body


def _have_crypto():
    try:
        import cryptography  # noqa: F401
        return True
    except Exception:
        return False


TERMS = ("bytes", "sweep", "control", "ledger", "ledger_skipped",
         "sigstore_inclusion", "verdict", "code")


def check(receipt, out, tool_path=None):
    """Every disagreement, named by field. Empty list means verified."""
    bad = []
    if receipt.get("format") != FORMAT:
        return ["format: %r is not %s" % (receipt.get("format"), FORMAT)]
    stated = receipt.get("receipt_sha256")
    if not stated:
        bad.append("receipt_sha256: absent, so any number could have been edited")
    else:
        body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        if hashlib.sha256(canonical(body)).hexdigest() != stated:
            bad.append("receipt_sha256: the receipt's own digest does not cover "
                       "its contents (edited after it was written)")

    # The field-by-field comparison runs even when the digest is broken, so a
    # reader learns *which* number moved, not only that something did.
    tool_path = tool_path or os.path.join(HERE, "stranger_competitor_check.py")
    if receipt.get("tool_sha256") != _sha256_file(tool_path):
        bad.append("tool_sha256: receipt was written by a different copy of the "
                   "tool than the one being run here")
    fresh = build_receipt(out, tool_path)
    for term in TERMS:
        if receipt.get(term) != fresh[term]:
            bad.append("%s: receipt says %r, this machine recomputes %r"
                       % (term, receipt.get(term), fresh[term]))
    return bad


def selftest():
    """A faithful receipt verifies; an edited number and an edited digest do not."""
    out = {"upstream": {"repo": "x", "commit": "y"}, "source": "local",
           "bytes": {"checked": 1, "match": 1},
           "sweep": {"vectors": 1, "n_replayable": 1, "consistent": 1,
                     "inconsistent": 0},
           "control": {"applied": 1, "detected": 1, "ambiguous": 0,
                       "unexplained": 0},
           "ledger": {"verdict": 1, "signature-only": 0, "nothing": 0,
                      "signature_verified": 1},
           "sigstore_inclusion": {"compared": 0, "agree_with_published": 0,
                                  "skipped_no_empty_root": 0, "unusable": 0},
           "diffs": [], "verdict": "REPRODUCED", "code": 0}
    r = build_receipt(out)
    assert check(r, out) == [], check(r, out)
    # A number moved by one.
    r2 = json.loads(json.dumps(r))
    r2["sweep"]["n_replayable"] = 2
    assert check(r2, out), "an edited count passed"
    # A verdict flipped without touching the digest.
    r3 = json.loads(json.dumps(r))
    r3["verdict"] = "DID NOT MATCH"
    assert check(r3, out), "an edited verdict passed"
    # The digest removed.
    r4 = {k: v for k, v in r.items() if k != "receipt_sha256"}
    assert check(r4, out), "a receipt without its digest passed"
    # A different tool version.
    r5 = json.loads(json.dumps(r))
    r5["tool_sha256"] = "0" * 64
    r5["receipt_sha256"] = hashlib.sha256(canonical(
        {k: v for k, v in r5.items() if k != "receipt_sha256"})).hexdigest()
    assert check(r5, out), "a receipt from another tool version passed"
    print("selftest: a faithful receipt verifies; edits, a missing digest and "
          "another version do not")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", help="the JSON a runner produced")
    ap.add_argument("--dir", help="the corpus to recompute against")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.receipt:
        ap.error("--receipt is required unless --selftest is given")
    with open(a.receipt, encoding="utf-8") as f:
        receipt = json.load(f)
    out = stranger.run(a.dir, verbose=False)
    bad = check(receipt, out)
    if bad:
        for line in bad:
            print("DIFF %s" % line)
        print("VERDICT: NOT VERIFIED")
        return 1
    rt = receipt.get("runtime", {})
    print("runtime: python %s on %s, cryptography %s"
          % (rt.get("python"), rt.get("platform"), rt.get("cryptography")))
    print("the receipt's %d checks, verdict %r and code %r are what this machine "
          "recomputes" % (len(TERMS), receipt.get("verdict"), receipt.get("code")))
    print("VERDICT: VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
