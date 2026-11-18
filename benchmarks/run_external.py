#!/usr/bin/env python3
"""Measure any verifier against the same mutated packages.

The point: a benchmark that can only score its own implementation is a
self-report. This runner feeds the mutants produced by
`tools/mutation_benchmark.py` to an arbitrary command and reports that
command's false-accept rate, so two implementations can be compared on
identical bytes.

Contract for the verifier under test (deliberately minimal):
    <your-command> <package-dir>
  exit 0            -> the verifier ACCEPTS the package
  any other exit    -> the verifier refuses it (FAIL, INCONCLUSIVE, crash, missing)

  An accept on a mutated package is a false accept. Refusing the clean
  base package is a false reject, reported separately because a verifier
  that refuses everything scores 0% false accepts and is useless.

Usage:
    python tools/mutation_benchmark.py                     # refresh the mutants
    python benchmarks/run_external.py \
        --verifier "python ivcli.py {pkg}" \
        --implementation "uibc-iverify" \
        --out benchmarks/submissions/external.json
"""
from __future__ import annotations

import argparse, json, os, subprocess, sys, datetime, platform

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MB = os.path.join(ROOT, "tools", "out", "_mb")


def check(command: str, pkg: str) -> tuple[bool, str]:
    argv = [a.replace("{pkg}", pkg) for a in command.split()]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0, "exit=%d" % p.returncode
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError as exc:
        return False, "not-found: %s" % exc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", required=True, help='command template; use {pkg} for the package path')
    ap.add_argument("--implementation", default="unspecified")
    ap.add_argument("--submitter", default="unspecified")
    ap.add_argument("--out", required=True)
    ap.add_argument("--commit", default="unknown")
    args = ap.parse_args()

    base = os.path.join(MB, "base")
    if not os.path.isdir(base):
        sys.stderr.write("no mutants on disk - run tools/mutation_benchmark.py first\n")
        return 2

    cases = sorted(d for d in os.listdir(MB)
                   if d.startswith("m_") and os.path.isdir(os.path.join(MB, d)))
    if not cases:
        sys.stderr.write("mutant directory empty - run tools/mutation_benchmark.py first\n")
        return 2

    base_ok, base_note = check(args.verifier, base)
    rows = []
    for name in cases:
        ok, note = check(args.verifier, os.path.join(MB, name))
        rows.append({"id": name, "accepted": ok, "detail": note})

    accepted = sum(1 for r in rows if r["accepted"])
    total = len(rows)
    record = {
        "schema": "uibc-bench/1",
        "kind": "external-verifier",
        "implementation": args.implementation,
        "submitter": args.submitter,
        "commit": args.commit,
        "run_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "machine": {"system": platform.system(), "release": platform.release(),
                    "python": platform.python_version()},
        "verifier_command": args.verifier,
        "base_accepted": base_ok,
        "base_detail": base_note,
        "mutations": {"total": total, "accepted": accepted,
                      "false_accept_rate": round(accepted / total * 100, 1),
                      "cases": rows},
        "notes": [
            "exit 0 means the verifier accepted the package; a false accept is an accept of a mutated package",
            "base_accepted=false means the verifier refuses the clean baseline too, so its rate is not meaningful",
            "mutants are the same bytes every implementation is given: produced by tools/mutation_benchmark.py",
        ],
        "claim": {
            "boundary_sentence": (
                "A uibc PASS means: within the observed evidence boundary, no violation was detected. "
                "It does not claim the agent was correct, safe, or wise; that the recorded inputs were true "
                "or complete; or that any real-world outcome followed."
            ),
            "not_claimed": [
                "that acceptance by exit code reflects the same decision the verifier's API would return",
                "that these 21 mutations cover the ways a package can be altered",
                "that a low rate makes an implementation better than one that scored differently",
            ],
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    print("base accepted=%s (%s)" % (base_ok, base_note))
    print("%s: %d/%d accepted (%.1f%% false accepts) -> %s"
          % (args.implementation, accepted, total, accepted / total * 100, args.out))
    return 0 if base_ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
