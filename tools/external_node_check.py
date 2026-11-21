#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1: the external-node check. One command, no install, one result file.

Purpose: turn "anyone can re-verify" from a claim into something a stranger
produces on their own machine. This script is deliberately stdlib-only for the
parts that matter; if the main verifier cannot be imported it still runs the
independent one and says so, instead of failing.

    python tools/external_node_check.py --out external_node_result.json

What it does:
  1. verifies a package with independent_verifier/iverify.py (pure stdlib, no
     deps, written from the spec rather than shared code);
  2. verifies the same package with uibc_core.verify (the reference side) and
     cross-checks that the two agree on the top-level result;
  3. runs three negative probes that MUST fail (strict serialization, value-level
     timestamp, identifier case) - so a passing run proves the checker is not
     simply returning PASS for everything;
  4. writes one JSON a reviewer can attach to a ticket, with version, platform,
     command line and timings.

The output is designed to be quotable: if you run it and send back the file, that
is an external verification node - the number this project is actually short of.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

BASE = os.path.join(ROOT, "benchmark", "corpus", "base")


def _run(cmd):
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=ROOT)
    return rc, round((time.time() - t0) * 1000)


def _independent(pkg):
    # Import the verifier rather than shelling out to iverify.py. The file had no
    # __main__ block, so `python iverify.py <pkg>` exited 0 unconditionally and every
    # caller that read the exit code recorded "independent=PASS" without any check
    # having run (measured 2026-11-21, on three value-level probes).
    try:
        from independent_verifier.iverify import independent_verify
    except Exception:
        return 2, 0
    t0 = time.time()
    rep = independent_verify(pkg)
    rc = {"PASS": 0, "FAIL": 1}.get(rep.get("result"), 2)
    return rc, round((time.time() - t0) * 1000)


def _reference(pkg):
    try:
        from uibc_core.verify import verify
    except Exception as exc:  # pragma: no cover - environment dependent
        return None, 0, "reference verifier unavailable: %s" % exc
    t0 = time.time()
    rep = verify(pkg)
    return rep["result"], round((time.time() - t0) * 1000), rep


def _mutate(pkg, rel, mutate):
    dst = pkg + "-probe"
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(pkg, dst)
    path = os.path.join(dst, rel)
    doc = json.load(open(path, encoding="utf-8"))
    mutate(doc)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return dst


def probes(pkg):
    """Three packages that must be rejected; each targets a different layer."""
    out = []
    cases = [
        ("value:timestamp-without-zone", "lifecycle.json",
         lambda d: d["events"][0].__setitem__("timestamp", "2026-11-17T05:59:59")),
        ("value:feb29-1900", "manifest.json",
         lambda d: d.__setitem__("created_at", "1900-02-29T00:00:00Z")),
        ("value:uppercase-uuid", "lifecycle.json",
         lambda d: d["events"][0].__setitem__(
             "event_id", "93E2FFBE-893A-4B13-9A34-5C36D9C8B138")),
    ]
    for name, rel, mutate in cases:
        p = _mutate(pkg, rel, mutate)
        res, ms, _ = _reference(p)
        ind_rc, ind_ms = _independent(p)
        out.append({"probe": name, "result": res, "ms": ms,
                    "expected": "FAIL",
                    "reference_rejected": res == "FAIL",
                    "independent_rejected": ind_rc == 1,
                    "independent_exit": ind_rc,
                    "ok": res == "FAIL" and ind_rc == 1})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", default=BASE)
    ap.add_argument("--out", default="external_node_result.json")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.pkg):
        if os.path.abspath(args.pkg) == os.path.abspath(BASE):
            print("corpus missing; building it (first run only, ~10s) ...")
            rc = subprocess.call([sys.executable,
                                  os.path.join(ROOT, "benchmark", "corpus.py")],
                                 cwd=ROOT)
            if rc != 0 or not os.path.isdir(args.pkg):
                print("could not build the corpus (rc=%d)" % rc)
                return 2
        else:
            print("package not found: %s" % args.pkg)
            return 2

    ind_result, ind_ms = _independent(args.pkg)
    ref_result, ref_ms, ref_detail = _reference(args.pkg)
    probe_rows = probes(args.pkg)

    agree = (ref_detail is None or not isinstance(ref_detail, dict) or
             ref_result == "PASS")
    report = {
        "schema": "uibc.external-node-result/1",
        "when_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "package": os.path.relpath(args.pkg, ROOT).replace("\\", "/"),
        "independent_verifier": {"exit_code": ind_result, "ms": ind_ms,
                                 "interpretation": "0 means PASS"},
        "reference_verifier": {"result": ref_result, "ms": ref_ms},
        "probes": probe_rows,
        "verdict": ("CONSISTENT" if (ind_result == 0 and ref_result == "PASS"
                                     and all(p["ok"] for p in probe_rows))
                    else "DISCREPANCY"),
        "note": ("A CONSISTENT result means: the two implementations agree, and "
                 "three packages that must be rejected were rejected. It does "
                 "NOT mean the evidence is true or complete."),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("independent=%s  reference=%s(%sms)  probes=%d/%d rejected  -> %s"
          % ("PASS" if ind_result == 0 else "FAIL", ref_result, ref_ms,
             sum(1 for p in probe_rows if p["ok"]), len(probe_rows),
             report["verdict"]))
    print("RESULT_JSON=%s" % os.path.abspath(args.out))
    return 0 if report["verdict"] == "CONSISTENT" else 1


if __name__ == "__main__":
    sys.exit(main())
