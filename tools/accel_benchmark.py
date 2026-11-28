"""Measure the 8.2.2 repeat cache on a real package, and print what it did.

    python tools/accel_benchmark.py --packages ./examples --package good.uibc \
        --agent did:web:verify.medxpert.cn --registry registry.json --repeats 30

The output is a measurement, not an advertisement: first call vs cached calls,
hit rate, and the scope statement that says this is byte-identical repeat
caching only. Run it on your own machine before quoting any number.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from adapters.a2a import accel as accel_mod            # noqa: E402
from adapters.a2a.server import A2AAdapter             # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--packages", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--agent", default=None)
    ap.add_argument("--card", default=os.path.join(REPO, "adapters", "a2a",
                                                   "agent-card.json"))
    ap.add_argument("--registry", default=None)
    ap.add_argument("--repeats", type=int, default=30)
    args = ap.parse_args(argv)

    adapter = A2AAdapter(args.packages, args.card, registry=args.registry)
    params = {"package": args.package}
    if args.agent:
        params["agent"] = args.agent
    bench = accel_mod.AccelBenchmark(adapter, repeats=args.repeats)
    result = bench.run("uibc/verify", params)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
