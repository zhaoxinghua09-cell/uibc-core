#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify latency probe: how long does one offline verification actually take?

Why: `draft-wang-ccs-runtime-verification-00` sells sub-millisecond per-invocation
receipts. We do not make a per-invocation claim - our unit is a package - but a
number is still owed, because "offline verification" sounds slow until measured.

    python tools/latency_probe.py

Reports median / p95 / max over N repeats on the benchmark base package, plus a
separate figure for a 50 MB evidence file so the cost of hashing dominates at
some size. Results land in tools/out/latency.json.
"""
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from uibc_core.verify import verify  # noqa: E402

OUT = os.path.join(ROOT, "tools", "out")
BASE = os.path.join(ROOT, "benchmark", "corpus", "base")
N = 50


def probe(pkg, n=N):
    times = []
    result = None
    for _ in range(n):
        t0 = time.perf_counter()
        result = verify(pkg)["result"]
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    return {"package": os.path.basename(pkg), "result": result, "repeats": n,
            "median_ms": round(statistics.median(times), 2),
            "p95_ms": round(times[int(0.95 * (n - 1))], 2),
            "max_ms": round(times[-1], 2)}


def main():
    if not os.path.isdir(BASE):
        print("no corpus base: run `python benchmark/corpus.py` first")
        return 2
    rows = [probe(BASE)]
    # one big-evidence case, taken from the mutation run if present
    big = os.path.join(OUT, "_mb", "m_M12")
    if os.path.isdir(big):
        rows.append(probe(big, 10))
    doc = {"meta": {"generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                      time.gmtime()),
                    "unit": "one offline verification of one package",
                    "not_claimed": "per-invocation receipt latency (see CCS); "
                                   "our unit is the package, not the call"},
           "rows": rows}
    with open(os.path.join(OUT, "latency.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    for r in rows:
        print("%-10s %-6s median %6.2f ms | p95 %6.2f ms | max %6.2f ms (%d repeats)"
              % (r["package"], r["result"], r["median_ms"], r["p95_ms"],
                 r["max_ms"], r["repeats"]))
    print("RESULT_JSON=" + os.path.join(OUT, "latency.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
