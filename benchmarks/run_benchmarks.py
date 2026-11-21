#!/usr/bin/env python3
"""Run the published robustness benchmark and emit a submission file.

Deterministic inputs, deterministic output shape. No network, no key material.

    python benchmarks/run_benchmarks.py                      # just score this checkout
    python benchmarks/run_benchmarks.py --out benchmarks/submissions/mine.json \
        --submitter "org/team" --implementation "my-verifier"

The two suites this drives live in tools/: mutation_benchmark.py (21 mutations
against a sealed package, three key modes) and redteam_suite.py (15 hostile-input
cases against a registered agent). Both already write their own result JSON; this
script only merges them into one stable record, so nobody has to trust a number
that was retyped by hand.
"""
from __future__ import annotations

import argparse, datetime, json, os, platform, subprocess, sys

SCHEMA = "uibc-bench/1"

BOUNDARY = (
    "A uibc PASS means: within the observed evidence boundary, no violation was detected. "
    "It does not claim the agent was correct, safe, or wise; that the recorded inputs were true "
    "or complete; or that any real-world outcome followed."
)
NOT_CLAIMED = [
    "that a low false-accept rate under these 21 mutations generalises to unseen mutations",
    "that refusal of these 15 hostile inputs implies refusal of unlisted ones",
    "that the suite sizes are comparable across implementations that ship different suites",
    "any ranking claim against an implementation that has not submitted a file here",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="where to write the submission record")
    ap.add_argument("--submitter", default="unspecified")
    ap.add_argument("--implementation", default="uibc-core")
    ap.add_argument("--commit", default="")
    args = ap.parse_args()

    commit = args.commit
    if not commit:
        code, out = run(["git", "rev-parse", "--short", "HEAD"])
        commit = out.strip() if code == 0 else "unknown"

    mb_rc, mb_log = run([sys.executable, os.path.join("tools", "mutation_benchmark.py")])
    rt_rc, rt_log = run([sys.executable, os.path.join("tools", "redteam_suite.py")])
    if mb_rc != 0 or rt_rc != 0:
        sys.stderr.write("a suite failed to run; refusing to emit a score\n")
        sys.stderr.write(mb_log[-800:] + "\n" + rt_log[-800:] + "\n")
        return 2

    mb = load(os.path.join(ROOT, "tools", "out", "mutation_benchmark.json"))
    rt = load(os.path.join(ROOT, "tools", "out", "redteam_result.json"))

    modes = mb["summary"]
    rt_cases = rt["cases"]
    refused = sum(1 for c in rt_cases if str(c.get("result", "")).upper() == "FAIL")
    by_design = sum(1 for c in rt_cases if str(c.get("result", "")).upper() == "PASS")
    skipped = sum(1 for c in rt_cases if str(c.get("result", "")).upper() == "SKIP")

    record = {
        "schema": SCHEMA,
        "submitter": args.submitter,
        "implementation": args.implementation,
        "commit": commit,
        "run_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "machine": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "machine_arch": platform.machine(),
        },
        "suites": {
            "mutation": {
                "total": modes.get("open", {}).get("total"),
                "modes": {
                    "open": modes.get("open"),
                    "pinned": modes.get("pinned"),
                    "head-pinned": modes.get("head-pinned"),
                },
                "cases": mb["rows"],
            },
            "redteam": {
                "total": len(rt_cases),
                "refused_as_expected": refused,
                "passed_by_design": by_design,
                "skipped": skipped,
                "cases": rt_cases,
            },
        },
        "claim": {"boundary_sentence": BOUNDARY, "not_claimed": NOT_CLAIMED},
        "notes": [
            "both suites are driven from this checkout; the commit above is the one measured",
            "a SKIP is counted separately and never folded into a pass",
            "false-accept rates are per mode; open mode is the weakest and is reported first because of it",
        ],
    }

    text = json.dumps(record, ensure_ascii=False, indent=1, sort_keys=False)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        print("written", args.out)
    else:
        print(text)

    print(
        "mutation {o}/{t} open, {p}/{t} pinned, {h}/{t} head-pinned | redteam refused {r}/{n}"
        " (by design {b}, skipped {s})".format(
            o=modes.get("open", {}).get("accepted"), t=modes.get("open", {}).get("total"),
            p=modes.get("pinned", {}).get("accepted"),
            h=modes.get("head-pinned", {}).get("accepted"),
            r=refused, n=len(rt_cases), b=by_design, s=skipped,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
