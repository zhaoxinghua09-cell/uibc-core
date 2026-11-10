#!/usr/bin/env python3
"""Runner for the uibc-agent-evidence test vectors (v1).

Verifies every shipped case in the modes that are reproducible from the
shipped bytes (open mode for all cases; pinned mode for the Ed25519
sample) and compares the outcome with each case's expected.json.

Requires uibc-core (the reference verifier) on the PYTHONPATH, e.g.:

    git clone https://github.com/zhaoxinghua09-cell/uibc-core
    PYTHONPATH=uibc-core python3 run_vectors.py .

Exit code 0 means every shipped case reproduced its expected outcome.
The strict / attacker-key cells of the full expectation matrix are NOT
reproduced from these bytes (fixture keys are ephemeral by design);
they are reproduced by the fixture generator gate in uibc-core:

    python3 fixtures/generate_fixtures.py   # enforces all 24 cells
"""
import json
import os
import sys


def main(suite_dir):
    sys.path.insert(0, os.environ.get("UIBC_CORE_PATH", ""))
    try:
        from uibc_core.verify import verify
    except ImportError:
        print("uibc_core not importable; set PYTHONPATH to a uibc-core checkout")
        return 2

    v1 = os.path.join(suite_dir, "v1")
    failures = 0
    for case in sorted(os.listdir(v1)):
        cdir = os.path.join(v1, case)
        exp_path = os.path.join(cdir, "expected.json")
        if not os.path.isfile(exp_path):
            continue
        exp = json.load(open(exp_path))
        pkg = os.path.join(cdir, "package")
        for mode, want in exp["modes"].items():
            if mode == "pinned":
                pub = bytes.fromhex(open(os.path.join(cdir, "owner.pub")).read().strip())
                rep = verify(pkg, pubkey=pub)
            else:
                rep = verify(pkg)
            got = {"result": rep["result"],
                   "checks": {c["id"]: c["result"] for c in rep["checks"]}}
            ok = got["result"] == want["result"] and got["checks"] == want["checks"]
            print(f"{case:20s} {mode:7s} expected={want['result']:13s} got={got['result']:13s} {'OK' if ok else 'MISMATCH'}")
            failures += 0 if ok else 1
    print("ALL OK" if failures == 0 else f"{failures} MISMATCHES")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
