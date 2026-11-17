#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AER-1 corpus -> our checks: a class-level crosswalk, counted.

Why class-level and not vector-level: AER-1 verifies a *receipt* schema (tool,
caller scope, output hash, anchor); uibc verifies a *package* schema (manifest,
lifecycle log, evidence index, seal). Running their .json vectors through our
verifier would just be a schema mismatch - 143 INCONCLUSIVEs, proving nothing.
What is honestly comparable is the CLASS of attack each vector encodes: is
"duplicate member name" something our verifier catches, or not?

So every vector class is mapped by hand to one of:
  COVERED    - a check we already run catches it
  TO-ADD     - our checks would miss it today (recorded as a gap, not a fix)
  N_A        - the class belongs to their receipt schema and has no counterpart
               in ours; claiming to "cover" it would be noise

The counts come from their published index (tools/out/aer1_corpus_index.json),
and the mapping is authored - the script never guesses.

    python tools/aer1_crosswalk.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
INDEX = os.path.join(OUT, "aer1_corpus_index.json")

# basis: the file names published in their index (kit v1.5.7). One row per class.
# "check" names our check that answers it, or the gap that would be needed.
MAPPING = [
    # --- encoding layer: what S11 now covers ---
    ("invalid/duplicate-member-name", "COVERED", "S11 duplicate member names"),
    ("invalid/non-utf8-bytes", "COVERED", "S11 strict UTF-8 decode"),
    ("invalid/provenance-control-char", "COVERED", "S11 raw control characters"),
    # --- digest layer ---
    ("invalid/hash-mismatch", "COVERED", "S4 per-file hash"),
    ("invalid/hash-bad-format", "COVERED", "S4 hash comparison fails on bad format"),
    ("invalid/input-hash-mismatch", "COVERED", "S4/S5 evidence root"),
    ("invalid/missing-output-hash", "COVERED", "S1/S4 required evidence entry"),
    ("invalid/version-downgrade", "COVERED", "S1 schema version is pinned"),
    ("invalid/tampered-provenance", "COVERED", "S2 identity consistency"),
    ("invalid/bad-provenance", "COVERED", "S2 identity consistency"),
    # --- encoding gaps we do not close yet ---
    ("invalid/base64-pad-bit", "TO-ADD", "S12 strict base64 (pad bits must be zero)"),
    ("invalid/base64-unpadded", "TO-ADD", "S12 strict base64 (padding required)"),
    ("invalid/ax-base64-unpadded", "TO-ADD", "S12 strict base64"),
    ("invalid/bytes-not-base64", "TO-ADD", "S12 strict base64"),
    ("invalid/uppercase-id", "TO-ADD", "S12 canonical id casing"),
    ("invalid/nil-uuid", "TO-ADD", "S12 non-nil identifier"),
    ("invalid/id-trailing-newline", "TO-ADD", "S12 exact identifier bytes"),
    ("invalid/provenance-trailing-newline", "TO-ADD", "S12 exact field bytes"),
    # --- time layer: a real gap, we validate plausibility not format ---
    ("invalid/timestamp-no-timezone", "TO-ADD", "S12 RFC 3339 requires an offset"),
    ("invalid/lowercase-timestamp", "TO-ADD", "S12 canonical 'T'/'Z' casing"),
    ("invalid/impossible-date", "TO-ADD", "S12 calendar validity"),
    ("invalid/bad-created-at", "TO-ADD", "S12 calendar validity"),
    ("invalid/leap-second-created-at", "TO-ADD", "S12 leap-second policy"),
    ("invalid/feb29-1900", "TO-ADD", "S12 calendar validity (1900 not a leap year)"),
    ("invalid/feb29-non-leap", "TO-ADD", "S12 calendar validity"),
    ("invalid/ax-feb29-1900", "TO-ADD", "S12 calendar validity"),
    ("invalid/ax-feb29-non-leap", "TO-ADD", "S12 calendar validity"),
    ("invalid/bad-offset-range", "TO-ADD", "S12 offset range"),
    ("invalid/ax-tool-empty-scope", "N_A", "receipt 'tool scope' has no uibc counterpart"),
    # --- receipt-schema classes with no uibc counterpart ---
    ("invalid/tool-not-object", "N_A", "receipt 'tool' object"),
    ("invalid/tool-empty-name", "N_A", "receipt 'tool' object"),
    ("invalid/payload-is-array", "N_A", "receipt payload shape"),
    ("invalid/payload-omits-issuer-claims", "N_A", "receipt payload shape"),
    ("invalid/bad-id", "N_A", "receipt id grammar"),
    ("invalid/bad-verification-status", "N_A", "receipt status field"),
    ("invalid/input-hash-key-order-20", "N_A", "receipt canonicalization detail"),
    # --- suites (counted from the index, mapped as a whole) ---
    ("base/chain-vectors.json", "COVERED", "S3 lifecycle chain + L8-L12"),
    ("base/chain-vectors-v07.json", "COVERED", "S3 lifecycle chain + L8-L12"),
    ("base/commitment-vectors.json", "COVERED", "S8 checkpoint head"),
    ("base/id-binding-vectors.json", "COVERED", "S2 identity binding"),
    ("base/anchor-vectors.json", "PARTIAL", "trust_level anchored + S9 out-of-band head; "
                                            "no anchor-event resolution"),
    ("base/merkle-vectors.json", "TO-ADD", "no Merkle tree or inclusion proof at all"),
]

VERDICT_ORDER = {"COVERED": 0, "PARTIAL": 1, "TO-ADD": 2, "N_A": 3}

# --- dynamic recompute (2026-11-17) -----------------------------------------
# The verdicts above were authored by hand, so they went stale the moment S11/S12
# landed: the file still said TO-ADD for classes we now reject. A static list that
# claims to describe code is a claim that rots. So each class that could plausibly
# be closed is tied to a PROBE - a real call into the verifier on the hostile
# input the class encodes. If the probe passes, the class is COVERED regardless of
# what the hand-written row said; if the code regresses, the class falls back to
# TO-ADD on its own. Nothing is asserted; everything is executed.
def _probes():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from uibc_core import encoding as enc, merkle as mk
    from uibc_core.verify import _semantic_problems as sem

    def rejects(doc):
        return bool(sem(doc))

    def merkle_ok():
        data = [b"a", b"b", b"c", b"d", b"e"]
        leaves = [mk.leaf_hash(d) for d in data]
        root = mk.root_hash(leaves)
        proof = [bytes.fromhex(h) for h in mk.build_proof(leaves, 2)]
        good = mk.verify_inclusion(leaves[2], 2, len(leaves), proof, root)
        bad_idx = mk.verify_inclusion(leaves[2], 3, len(leaves), proof, root)
        bad_leaf = mk.verify_inclusion(mk.leaf_hash(b"X"), 2, len(leaves), proof, root)
        return good and not bad_idx and not bad_leaf

    def anchor_ok():
        from uibc_core import anchor as an
        leaves = [mk.leaf_hash(("l%d" % i).encode()) for i in range(3)]
        root = mk.root_hash(leaves)

        def doc(index=1, **over):
            d = {"id": "a1", "version": 1, "leaf_hash": leaves[index].hex(),
                 "anchored_at": "2026-11-17T08:00:00Z", "root": root.hex(),
                 "size": len(leaves), "index": index,
                 "proof": mk.build_proof(leaves, index)}
            d.update(over)
            return d

        if not an.resolve(doc(), root=root, leaves=leaves)[0]:
            return False
        cases = [
            dict(doc(), proof=[]),                            # anchored-missing-proof
            dict(doc(), leaf_hash="XYZ"),                     # anchored-bad-leaf-hash
            dict(doc(), anchored_at="2026-11-17T08:00:00"),   # anchored-bad-timestamp
            dict(doc(), id=" ", version=0),                   # anchored-bad-id-version
            dict(doc(), root=(b"\x11" * 32).hex()),           # anchored-unresolvable
            dict(doc(), index=0),                             # right proof, wrong position
        ]
        return all(not an.resolve(c, root=root, leaves=leaves)[0] for c in cases)

    return {
        "anchor": anchor_ok,
        "base64_pad_bit": lambda: bool(enc.problems("AB==")),
        "base64_unpadded": lambda: bool(enc.problems("YWI")),
        "base64_not_base64": lambda: bool(enc.problems("YW Jj")),
        "id_uppercase": lambda: rejects({"agent_id": "ABCDEF01-2345-6789-ABCD-EF0123456789"}),
        "id_nil": lambda: rejects({"agent_id": "00000000-0000-0000-0000-000000000000"}),
        "id_trailing_newline": lambda: rejects({"agent_id": "mb-agent-001\n"}),
        "ts_no_zone": lambda: rejects({"created_at": "2026-11-17T05:59:59"}),
        "ts_lowercase": lambda: rejects({"created_at": "2026-11-17t05:59:59z"}),
        "ts_impossible_date": lambda: rejects({"created_at": "2026-02-30T00:00:00Z"}),
        "ts_feb29_1900": lambda: rejects({"created_at": "1900-02-29T00:00:00Z"}),
        "ts_feb29_nonleap": lambda: rejects({"created_at": "2026-02-29T00:00:00Z"}),
        "ts_leap_second": lambda: rejects({"created_at": "2026-06-30T23:59:60Z"}),
        "ts_offset_range": lambda: rejects({"created_at": "2026-11-17T05:59:59+15:00"}),
        "merkle": merkle_ok,
    }


CAP_FOR_CLASS = {
    "invalid/base64-pad-bit": "base64_pad_bit",
    "invalid/base64-unpadded": "base64_unpadded",
    "invalid/ax-base64-unpadded": "base64_unpadded",
    "invalid/bytes-not-base64": "base64_not_base64",
    "invalid/uppercase-id": "id_uppercase",
    "invalid/nil-uuid": "id_nil",
    "invalid/id-trailing-newline": "id_trailing_newline",
    "invalid/provenance-trailing-newline": "id_trailing_newline",
    "invalid/timestamp-no-timezone": "ts_no_zone",
    "invalid/lowercase-timestamp": "ts_lowercase",
    "invalid/impossible-date": "ts_impossible_date",
    "invalid/bad-created-at": "ts_impossible_date",
    "invalid/leap-second-created-at": "ts_leap_second",
    "invalid/feb29-1900": "ts_feb29_1900",
    "invalid/feb29-non-leap": "ts_feb29_nonleap",
    "invalid/ax-feb29-1900": "ts_feb29_1900",
    "invalid/ax-feb29-non-leap": "ts_feb29_nonleap",
    "invalid/bad-offset-range": "ts_offset_range",
    "base/merkle-vectors.json": "merkle",
    "base/anchor-vectors.json": "anchor",
}


def recompute(rows):
    """Flip TO-ADD/PARTIAL rows to COVERED when the probe actually rejects."""
    probes = _probes()
    out = []
    for r in rows:
        cap = CAP_FOR_CLASS.get(r["class"])
        if cap and r["verdict"] in ("TO-ADD", "PARTIAL"):
            ok = False
            try:
                ok = bool(probes[cap]())
            except Exception as e:                      # a probe that throws is not a pass
                r = dict(r)
                r["check"] = "%s [probe error: %s]" % (r["check"], e)
            if ok:
                r = dict(r)
                r["verdict"] = "COVERED"
                r["check"] = r["check"] + " [recomputed: probe rejects]"
                r["recomputed"] = True
        out.append(r)
    return out



def main():
    if not os.path.isfile(INDEX):
        print("missing %s - fetch it first: %s" % (INDEX,
              "https://zambo.dev/aer1/corpus.json"))
        return 2
    idx = json.load(open(INDEX, encoding="utf-8"))
    files = idx.get("files", [])
    counts = {}
    for f in files:
        p = f["path"]
        if p.startswith("base/test-vectors/") or p.startswith("base/test-vectors"):
            base = p.split("/")[-1]
            key = "invalid/" + base if "/invalid/" in p else (
                  "valid/" + base if "/valid/" in p else
                  "anchored/" + base if "/anchored/" in p else p)
        else:
            key = p
        counts[key] = (f.get("vectors", 0), f.get("checks", 0))

    rows, summary = [], {"COVERED": [0, 0], "PARTIAL": [0, 0], "TO-ADD": [0, 0],
                         "N_A": [0, 0]}
    mapped_keys = set()
    for key, verdict, note in MAPPING:
        vectors, checks = counts.get(key, (None, None))
        hit = key
        if vectors is None:
            # try suffix match for per-file vectors whose exact name differed
            for k, v in counts.items():
                if k.endswith(key.split("/")[-1]):
                    vectors, checks, hit = v[0], v[1], k
                    break
        mapped_keys.add(hit)
        rows.append({"class": key, "verdict": verdict, "check": note,
                     "vectors": vectors, "checks": checks})

    # verdicts are recomputed by probe before they are counted, so the summary
    # describes the code as it runs now rather than as it was authored.
    rows = recompute(rows)
    for r in rows:
        if r.get("vectors"):
            summary[r["verdict"]][0] += r["vectors"]
            summary[r["verdict"]][1] += r["checks"] or 0

    # Everything unmapped is a POSITIVE vector (valid/*): a receipt that must pass
    # their verifier. There is no uibc counterpart - our schema differs - so it is
    # counted separately instead of being folded into a flattering percentage.
    unmapped = [(k, v) for k, v in counts.items() if k not in mapped_keys]

    print("%-42s %-9s %s" % ("vector class", "verdict", "our check / gap"))
    for r in sorted(rows, key=lambda r: (VERDICT_ORDER[r["verdict"]], r["class"])):
        print("%-42s %-9s %s" % (r["class"][:42], r["verdict"], r["check"][:44]))

    total_vec = idx.get("vector_count")
    total_chk = idx.get("check_count")
    print("\n他们的总量：%s 向量 / %s 检查（kit %s）" % (total_vec, total_chk,
                                                idx.get("kit_version")))
    for k in ("COVERED", "PARTIAL", "TO-ADD", "N_A"):
        print("  %-9s %3d 类，已映射向量 %3d / 检查 %3d"
              % (k, sum(1 for r in rows if r["verdict"] == k),
                 summary[k][0], summary[k][1]))
    print("  未映射（无对应类别）：向量 %d"
          % (int(total_vec or 0) - sum(v[0] for v in summary.values())))
    un_vec = sum(v[0] for _, v in unmapped)
    print("  其中正向向量 %d 条（valid/*：他们的 schema 合法用例，我们无对应）"
          % un_vec)

    doc = {"meta": {
        "what": "AER-1 vector classes mapped to uibc checks",
        "why_class_level": "different receipt schema; running their files through our "
                           "verifier would produce schema mismatches, not findings",
        "corpus": {"kit_version": idx.get("kit_version"),
                   "vector_count": total_vec, "check_count": total_chk,
                   "evaluated_set_digest": idx.get("evaluated_set_digest")},
        "mapping_is_authored": True,
        "not_claimed": "vector-level execution. This is a class-level crosswalk: it says "
                       "which classes we catch, not that we produced their verdicts.",
    }, "summary": {k: {"classes": sum(1 for r in rows if r["verdict"] == k),
                      "vectors": summary[k][0], "checks": summary[k][1]}
                   for k in summary},
       "unmapped": {"vectors": un_vec,
                    "reason": "positive receipt vectors (valid/*): their schema's "
                              "must-pass cases, no uibc counterpart"},
       "rows": rows}
    path = os.path.join(OUT, "aer1_crosswalk.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("\nRESULT_JSON=" + path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
