#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independently re-run the shipped 500-case corpus and compare it to the file in the repo.

Why this exists: the corpus file is only worth something if someone other than its author
can regenerate it and get the same per-case verdicts. This script does exactly that -
it runs `tools/mutation_corpus.py` into a temporary directory, then compares, row by row,
the committed `benchmarks/corpus/mutation-corpus-500.json` against the fresh run.

What is compared: for every case id - the family, and per mode the accepted flag plus the
set of failed check ids. What is NOT compared: `meta.generated_at_utc`, which is a timestamp
by design and differs on every run.

Usage:
    python tools/corpus_selfcheck.py
    python tools/corpus_selfcheck.py --receipt my-receipt.md

Exit code 0 means MATCH. Any other outcome means do not cite the numbers.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitbin  # noqa: E402  (git may be a .cmd shim on Windows)
SHIPPED = os.path.join(ROOT, "benchmarks", "corpus", "mutation-corpus-500.json")
MODES = ("open", "pinned", "head-pinned")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _rows_key(doc):
    """Canonical, timestamp-free view of the corpus, used for the hash."""
    rows = []
    for r in sorted(doc["rows"], key=lambda x: x["id"]):
        row = {"id": r["id"], "family": r["family"]}
        for m in MODES:
            v = r.get("modes", {}).get(m, {})
            row[m] = {"accepted": bool(v.get("accepted")),
                      "failed_checks": sorted(v.get("failed_checks", []))}
        rows.append(row)
    return rows


def _sha(rows):
    blob = json.dumps(rows, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _git_head():
    """Resolve the commit three ways, so a receipt never ships with a hole in it.

    1. ask git (works in a normal clone with git on PATH)
    2. read .git/HEAD and the ref it points at (works when git is absent)
    3. read a CI-provided commit variable (works in detached CI checkouts)
    Returns a 40-char hex sha, or "UNAVAILABLE" - never the ambiguous "unknown".
    """
    try:
        out = gitbin.check_output(["-C", ROOT, "rev-parse", "HEAD"],
                                  stderr=subprocess.DEVNULL).decode().strip()
        if len(out) == 40:
            return out
    except Exception:
        pass

    git_dir = os.path.join(ROOT, ".git")
    try:
        with open(os.path.join(git_dir, "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref:"):
            ref = head.split("ref:", 1)[1].strip()
            ref_path = os.path.join(git_dir, *ref.split("/"))
            if os.path.exists(ref_path):
                with open(ref_path, encoding="utf-8") as f:
                    sha = f.read().strip()
                if len(sha) == 40:
                    return sha
            packed = os.path.join(git_dir, "packed-refs")
            if os.path.exists(packed):
                with open(packed, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("#") or not line.strip():
                            continue
                        parts = line.split()
                        if len(parts) == 2 and parts[1] == ref and len(parts[0]) == 40:
                            return parts[0]
        elif len(head) == 40:
            return head
    except Exception:
        pass

    for var in ("GITHUB_SHA", "CI_COMMIT_SHA", "CI_COMMIT_ID", "BUILD_SOURCEVERSION"):
        sha = os.environ.get(var, "").strip()
        if len(sha) == 40:
            return sha
    return "UNAVAILABLE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", default=None, help="write a copy-pasteable receipt here")
    ap.add_argument("--keep", default=None, help="keep the fresh run's JSON at this path")
    args = ap.parse_args()

    if not os.path.exists(SHIPPED):
        print("MISSING: %s" % SHIPPED)
        return 2

    shipped = _load(SHIPPED)
    tmpdir = tempfile.mkdtemp(prefix="corpus_selfcheck_")
    fresh_path = args.keep or os.path.join(tmpdir, "fresh.json")
    started = time.time()
    cmd = [sys.executable, os.path.join(ROOT, "tools", "mutation_corpus.py"),
           "--out", fresh_path]
    proc = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        print("GENERATOR FAILED (exit %d); tail:" % proc.returncode)
        print("\n".join(proc.stdout.decode("utf-8", "replace").splitlines()[-12:]))
        return 3
    elapsed = time.time() - started
    fresh = _load(fresh_path)

    a, b = _rows_key(shipped), _rows_key(fresh)
    mismatch = []
    if len(a) != len(b):
        mismatch.append("row count %d vs %d" % (len(a), len(b)))
    by_id = {r["id"]: r for r in b}
    for r in a:
        other = by_id.get(r["id"])
        if other is None:
            mismatch.append("%s missing in fresh run" % r["id"])
            continue
        if other != r:
            delta = {m: (r[m], other[m]) for m in MODES if r[m] != other[m]}
            mismatch.append("%s differs: %s" % (r["id"], json.dumps(delta, ensure_ascii=False)))
    shipped_sum = shipped["summary"]
    fresh_sum = fresh["summary"]

    ok = not mismatch and shipped_sum == fresh_sum
    sha_shipped, sha_fresh = _sha(a), _sha(b)

    lines = []
    lines.append("VERDICT: %s" % ("MATCH" if ok else "MISMATCH"))
    lines.append("cases: shipped=%d fresh=%d" % (len(a), len(b)))
    for m in MODES:
        s = shipped_sum[m]
        lines.append("%-12s %d/%d = %.1f%%" % (m, s["accepted"], s["total"],
                                               s["false_accept_rate"]))
    lines.append("rows_sha256 shipped=%s fresh=%s" % (sha_shipped, sha_fresh))
    if mismatch:
        lines.append("first mismatches:")
        lines.extend("  " + x for x in mismatch[:10])

    receipt = []
    receipt.append("# Corpus self-check receipt")
    receipt.append("")
    head = _git_head()
    if head == "UNAVAILABLE":
        receipt.append("- provenance: **INCOMPLETE** - commit could not be resolved")
        receipt.append("  (git absent, no .git/HEAD, no CI commit variable). The verdict below")
        receipt.append("  still holds, but it cannot be pinned to a specific code state.")
    receipt.append("- verdict: **%s**" % ("MATCH" if ok else "MISMATCH"))
    receipt.append("- commit: `%s`" % head)
    receipt.append("- shipped file: `benchmarks/corpus/mutation-corpus-500.json`")
    receipt.append("- command: `python tools/corpus_selfcheck.py`")
    receipt.append("- started (UTC): %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    receipt.append("- wall clock: %.1f s" % elapsed)
    receipt.append("- python: %s %s" % (platform.python_version(), platform.platform()))
    receipt.append("- rows_sha256: `%s` (shipped) / `%s` (fresh)" % (sha_shipped, sha_fresh))
    receipt.append("")
    receipt.append("```")
    receipt.extend(lines)
    receipt.append("```")
    receipt.append("")
    receipt.append("This receipt says one thing only: the corpus in this repository can be")
    receipt.append("regenerated from the generator in this repository, and every per-case")
    receipt.append("verdict came out the same. It does not say the corpus is complete, that")
    receipt.append("the families were chosen fairly, or that the verifier is strong.")
    text = "\n".join(receipt)

    print(text)
    if args.receipt:
        with open(args.receipt, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\nreceipt written: %s" % args.receipt)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
