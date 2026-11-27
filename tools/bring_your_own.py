#!/usr/bin/env python3
"""Test someone else's packages with this project's verifier, without our corpus.

A case is one directory that is itself an evidence package (identity.json,
lifecycle.json, manifest.json, evidence/ ...) plus one expectation. Nothing in
this runner needs our case names, our corpus, or our archive: you point it at
your directories, write down what you expect, and it runs the bundled verifier
against each one and judges the answer.

    python tools/bring_your_own.py --cases my-cases --expect my-expected.json \
        --pyz conformance/uibc-conformance-0.5.8.zip:uibc_core.pyz --out receipt.json

    # or, to check the runner against the shipped kit itself:
    python tools/bring_your_own.py --from-kit <unpacked kit dir> --out receipt.json

Judging follows the kit's own rules rather than the process exit code, because a
verifier that exits 0 while refusing everything would otherwise look successful:

    accept -> ok when the verdict is not FAIL and no check reports FAIL
    reject -> ok when the verdict is FAIL or INCONCLUSIVE and at least one of the
              checks you named actually reports FAIL

Exit codes: 0 every case as expected, 1 some case did not, 3 setup problem
(missing case directory, unreadable table, absent verifier). A setup problem out
ranks a verdict: the receipt is not written when the run cannot be set up.

`--run-by` is recorded verbatim in the receipt and defaults to unset, so a receipt
written by the author and a receipt written by a stranger are distinguishable
without asking.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

NOTICE = ("One person, one machine, one run. This is a receipt of what happened, "
          "not a certification, not an audit, and not a statement about the corpus.")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_pyz(spec, workdir):
    """Accept a path to a .pyz, or '<zip>:<member>' to pull the verifier out of an
    archive. The second form exists so a reader can point this at the published
    conformance archive instead of at a checkout."""
    if spec.endswith(".pyz") and ":" in spec and spec.rsplit(":", 1)[0].lower().endswith(".zip"):
        zpath, member = spec.rsplit(":", 1)
        if not os.path.isfile(zpath):
            return None, "archive absent: %s" % zpath
        out = os.path.join(workdir, os.path.basename(member))
        with zipfile.ZipFile(zpath) as z:
            with z.open(member) as src, open(out, "wb") as dst:
                dst.write(src.read())
        return out, ""
    if not os.path.isfile(spec):
        return None, "verifier absent: %s" % spec
    return spec, ""


def run_one(pyz, pkg, timeout=180):
    proc = subprocess.run([sys.executable, pyz, "verify", pkg],
                          capture_output=True, text=True, timeout=timeout)
    try:
        got = json.loads(proc.stdout)
    except Exception:
        return {"unparsed": True, "result": "", "checks": [], "rc": proc.returncode,
                "stderr": (proc.stderr or "")[-300:]}
    got["rc"] = proc.returncode
    got.setdefault("checks", [])
    got["stderr"] = (proc.stderr or "")[-300:]
    return got


def reported(got):
    return {c.get("id") for c in got.get("checks", [])
            if str(c.get("result", "")).upper() == "FAIL"}


def judge(case, got):
    verdict = (got.get("result") or "").upper()
    if case.get("expect") == "accept":
        ok = verdict != "FAIL" and not reported(got)
        note = "" if ok else "refused a package the expectation calls correct"
    else:
        rep = reported(got)
        named = bool(rep & set(case.get("expected_checks") or []))
        refused = verdict in ("FAIL", "INCONCLUSIVE")
        ok = refused and named
        note = "" if ok else ("refused without naming any expected check" if refused
                              else "did not refuse a package the expectation calls broken")
    return {"id": case["id"], "expect": case.get("expect"), "verdict": verdict,
            "rc": got.get("rc"), "reported": sorted(reported(got)), "ok": ok,
            "note": note, "parsed": not got.get("unparsed", False)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=None, help="directory holding one subdirectory per case")
    ap.add_argument("--expect", default=None, help="expected.json naming what each case must produce")
    ap.add_argument("--from-kit", default=None, help="unpacked conformance kit: uses its cases/ and expected.json")
    ap.add_argument("--pyz", default=None, help="path to uibc_core.pyz, or '<archive.zip>:uibc_core.pyz'")
    ap.add_argument("--out", default=None)
    ap.add_argument("--run-by", default=None)
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args(argv)

    if a.from_kit:
        a.cases = a.cases or os.path.join(a.from_kit, "cases")
        a.expect = a.expect or os.path.join(a.from_kit, "expected.json")
        a.pyz = a.pyz or os.path.join(a.from_kit, "uibc_core.pyz")
    if not (a.cases and a.expect and a.pyz):
        print("setup problem: --cases, --expect and --pyz are required "
              "(or --from-kit)", file=sys.stderr)
        return 3

    import tempfile
    with tempfile.TemporaryDirectory() as work:
        pyz, err = resolve_pyz(a.pyz, work)
        if not pyz:
            print("setup problem: %s" % err, file=sys.stderr)
            return 3
        if not os.path.isdir(a.cases):
            print("setup problem: case directory absent: %s" % a.cases, file=sys.stderr)
            return 3
        try:
            table = json.load(open(a.expect, encoding="utf-8"))["cases"]
        except Exception as exc:
            print("setup problem: cannot read %s: %s" % (a.expect, exc), file=sys.stderr)
            return 3

        absent = [c["id"] for c in table
                  if not os.path.isdir(os.path.join(a.cases, os.path.basename(str(c["path"]).rstrip("/"))))]
        if absent:
            print("setup problem: %d case dir(s) absent: %s"
                  % (len(absent), ", ".join(absent[:5])), file=sys.stderr)
            return 3

        rows = []
        for c in table:
            pkg = os.path.join(a.cases, os.path.basename(str(c["path"]).rstrip("/")))
            rows.append(judge(c, run_one(pyz, pkg, timeout=a.timeout)))

        passed = sum(1 for r in rows if r["ok"])
        receipt = {
            "kind": "uibc-bring-your-own-receipt",
            "notice": NOTICE,
            "run_by": a.run_by,
            "when_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "expect_sha256": sha256(a.expect),
            "verifier_sha256": sha256(pyz),
            "cases": len(rows), "passed": passed,
            "rows": rows,
        }
        if a.out:
            with open(a.out, "w", encoding="utf-8", newline="\n") as f:
                json.dump(receipt, f, ensure_ascii=False, indent=2)
                f.write("\n")
        print("%d/%d cases as expected (verifier %s)" % (passed, len(rows),
                                                         receipt["verifier_sha256"][:12]))
        return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
