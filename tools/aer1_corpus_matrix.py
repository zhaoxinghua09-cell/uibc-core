#!/usr/bin/env python3
"""Run the external verifier over AER-1's published receipt corpus, four directories.

Why this exists: `tools/aer1_vector_replay.py` already replays their base
vectors (merkle, unicode, chain, chain-v07) and reports 49/49. Those are
algorithm vectors. This one is different: it points our verifier at the
receipts *they* call valid, invalid, invalid-profile and anchored, and records
whether we reach the same decision they do.

Their harness is two-tiered (`EXPECTED` in cross_verify.py): `invalid-profile`
is expected to PASS the core check and fail only the profile check. Our
verifier returns a single verdict that folds file, structural and binding
levels together, so that one directory is where the two designs part company —
and the report says so instead of hiding it inside an aggregate.

Usage:
    python tools/aer1_corpus_matrix.py --kit DIR [--json] [--json-out PATH]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aer1_verify_external as external  # noqa: E402

# What AER-1's own harness expects per directory (cross_verify.py: EXPECTED).
THEIR_EXPECTATION = {
    "valid": "pass",
    "invalid": "fail",
    "invalid-profile": "pass",  # core passes, profile fails
    "anchored": "pass",
}

# Their pass/fail as our ACCEPTED/REJECTED vocabulary, for the coarse table.
THEIR_AS_OURS = {"pass": "ACCEPTED", "fail": "REJECTED"}


def receipts(directory):
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        yield os.path.join(directory, name)


def run(kit):
    base = os.path.join(kit, "base", "test-vectors")
    result = {"schema": "uibc-aer1-corpus/1", "kit": os.path.abspath(kit),
              "directories": {}, "agreement": {}, "notes": []}

    for dirname, expected in THEIR_EXPECTATION.items():
        src = os.path.join(base, dirname)
        if not os.path.isdir(src):
            result["notes"].append("directory missing: %s" % dirname)
            continue
        rows = []
        for path in receipts(src):
            rep = external.judge(path)
            rows.append({
                "file": os.path.basename(path),
                "our_verdict": rep["verdict"],
                "our_id_verdict": rep["id_verdict"],
                "blocking": {
                    "file_checks": rep["file_checks"],
                    "structural": rep["structural"],
                    "binding": rep["binding"],
                },
                "profile_findings": rep["reference_profile"],
                "anchor_outcome": (rep.get("anchors") or {}).get("outcome"),
            })
        accepted = sum(1 for r in rows if r["our_verdict"] == "ACCEPTED")
        rejected = len(rows) - accepted
        theirs = THEIR_AS_OURS[expected]
        result["directories"][dirname] = {
            "files": len(rows),
            "accepted": accepted,
            "rejected": rejected,
            "their_expectation_core": expected,
            "their_expectation_in_our_words": theirs,
            "agree": (accepted if theirs == "ACCEPTED" else rejected) == len(rows),
            "rows": rows,
        }

    # The one cell where the designs differ by construction, not by outcome.
    prof = result["directories"].get("invalid-profile")
    if prof and prof["files"]:
        blocking = sum(1 for r in prof["rows"] if r["our_verdict"] == "REJECTED")
        result["notes"].append(
            "invalid-profile: AER-1 expects CORE pass with the profile check failing "
            "separately. We answered ACCEPTED on %d of %d and recorded the profile "
            "findings without letting them block - agreement at the core level, "
            "divergence only in whether a profile fault blocks. Same bytes, different "
            "granularity, not a disagreement about validity."
            % (prof["files"] - blocking, prof["files"])
        )

    result["agreement"] = {
        d: v["agree"] for d, v in result["directories"].items()
    }
    result["directories_agree"] = sum(1 for v in result["agreement"].values() if v)
    result["directories_total"] = len(result["agreement"])
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True, help="corpus dir (contains base/test-vectors)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--json-out")
    args = ap.parse_args(argv)

    result = run(args.kit)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for d, v in result["directories"].items():
            print("%-16s files=%2d accepted=%2d rejected=%2d theirs=%-4s agree=%s"
                  % (d, v["files"], v["accepted"], v["rejected"],
                     v["their_expectation_core"], v["agree"]))
        for n in result["notes"]:
            print("note: %s" % n)
    return 0 if result["directories_agree"] == result["directories_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
