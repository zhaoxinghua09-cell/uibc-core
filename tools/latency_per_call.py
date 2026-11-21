"""Per-call latency: the number the comparison table was missing.

The existing benchmark measures 23 ms per *package* (median, 50 runs), which
is the right unit for "verify this bundle" and the wrong unit for "add one
record while an agent is running". Those are different questions; answering
one with the other's number is how a comparison table becomes dishonest.

This tool measures the hot path: one `CallRecorder.record()` including the
index rewrite and the evidence file write. Median and p95, same method as the
package benchmark so the two numbers sit side by side.

    python3 tools/latency_per_call.py --n 300 --json
"""

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
import shutil

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from adapters.frameworks.uibc_framework_hooks import CallRecorder, init_package


def measure(n=300, warmup=20):
    tmp = tempfile.mkdtemp(prefix="uibc-lat-")
    pkg = os.path.join(tmp, "pkg")
    init_package(pkg, agent_id="agent.bench", owner="bench")
    rec = CallRecorder(pkg, action_type="ACTION")
    samples = []
    try:
        for i in range(warmup + n):
            t0 = time.perf_counter()
            rec.record("bench.tool", {"i": i}, {"ok": i})
            dt = (time.perf_counter() - t0) * 1000.0
            if i >= warmup:
                samples.append(dt)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    samples.sort()

    def pct(p):
        if not samples:
            return None
        k = min(len(samples) - 1, int(round(p * (len(samples) - 1))))
        return round(samples[k], 3)

    return {
        "unit": "per record() call (index rewrite + evidence file write)",
        "n": len(samples),
        "median_ms": round(statistics.median(samples), 3),
        "mean_ms": round(statistics.mean(samples), 3),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
        "min_ms": round(samples[0], 3),
        "max_ms": round(samples[-1], 3),
        "environment": {
            "python": "%d.%d" % sys.version_info[:2],
            "platform": sys.platform,
        },
        "note": "not comparable to a per-call figure quoted by a system that "
                "does not fsync or does not rewrite an index",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = measure(args.n)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("per-call record(): n=%d  median=%s ms  mean=%s ms  p95=%s ms  p99=%s ms"
              % (out["n"], out["median_ms"], out["mean_ms"], out["p95_ms"],
                 out["p99_ms"]))
        print("(index rewrite + evidence file write, included)")


if __name__ == "__main__":
    main()
