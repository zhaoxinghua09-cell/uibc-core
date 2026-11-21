#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Six scenarios for the composition verifier - the demo a reviewer can re-run.

    python tools/compose_demo.py

Each scenario is a case file built in code (no hand-written JSON to trust), run
through uibc_core.composition, and written to tools/out/composition_result.json.
The point is not that our cases pass; it is that a case assembled from records of
DIFFERENT origins gets one deterministic verdict, and that the failure modes are
named by code (K1..K8) rather than by prose.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from uibc_core.canonical import hash_obj  # noqa: E402
from uibc_core.composition import compose_case  # noqa: E402

OUT = os.path.join(ROOT, "tools", "out")


def rec(origin, kind, subject, at, seq, payload, parent=None, refs=None):
    return {"origin": origin, "kind": kind, "subject": subject, "at": at, "seq": seq,
            "digest": "sha256:" + hash_obj(payload), "payload": payload,
            "parent": parent, "refs": refs or []}


def clean_case():
    """Three origins, one agent: a gate decision, a log receipt, a human review."""
    gate = rec("gate-A", "verdict", "agent:42", "2026-11-17T06:00:00Z", 1,
               {"decision": "ALLOW", "rule_id": "G-NONE"})
    gate2 = rec("gate-A", "verdict", "agent:42", "2026-11-17T06:01:00Z", 2,
                {"decision": "DENY", "rule_id": "G-DESTRUCT"}, parent=gate["digest"])
    log = rec("scitt-log", "receipt", "agent:42", "2026-11-17T06:00:30Z", 1,
              {"tree_size": 12, "leaf": gate["digest"]}, refs=[gate["digest"]])
    human = rec("reviewer-B", "note", "agent:42", "2026-11-17T06:30:00Z", 1,
                {"conclusion": "escalate"}, refs=[gate2["digest"], log["digest"]])
    return [gate, gate2, log, human]


def scenarios():
    base = clean_case()

    edited = [dict(r) for r in base]
    edited[1] = dict(edited[1])
    edited[1]["payload"] = {"decision": "ALLOW", "rule_id": "G-DESTRUCT"}  # digest untouched

    gapped = [dict(r) for r in base]
    gapped[1] = dict(gapped[1])
    gapped[1]["seq"] = 5  # seq 3,4 never existed and no parent link to seq 2

    dangling = [dict(r) for r in base]
    dangling[3] = dict(dangling[3])
    dangling[3]["refs"] = ["sha256:" + "de" * 32]

    islands = [base[0], base[1],
               rec("other-C", "note", "agent:42", "2026-11-17T07:00:00Z", 1,
                   {"conclusion": "unrelated"})]

    time_travel = [dict(r) for r in base]
    time_travel[0] = dict(time_travel[0])
    time_travel[0]["at"] = "2026-11-17T06:45:00Z"  # relies on nothing, but log cites it

    single = [base[0]]

    return {
        "A_clean_three_origins": base,
        "B_payload_edited_digest_untouched": edited,
        "C_sequence_gap": gapped,
        "D_dangling_cross_origin_ref": dangling,
        "E_stacked_not_composed": islands,
        "F_ordering_contradiction": time_travel,
        "G_single_origin": single,
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for name, records in scenarios().items():
        rep = compose_case(records)
        rows.append({"scenario": name, "records": len(records),
                     "verdict": rep["verdict"],
                     "codes": sorted({f["code"] for f in rep["findings"]}),
                     "detail": [f["detail"] for f in rep["findings"]]})
        print("%-36s %-14s %-14s %s" % (name, rep["verdict"],
                                        ",".join(sorted({f["code"] for f in rep["findings"]})) or "-",
                                        (rep["findings"][0]["detail"][:52]
                                         if rep["findings"] else "no finding")))
    doc = {"meta": {"what": "one case, many origins, one deterministic verdict",
                    "checks": "K1 self-digest, K2 subject, K3 chain continuity, "
                              "K4 cross-origin ordering, K5 reference closure, "
                              "K6 duplicate identity, K7 assembly actually composed, "
                              "K8 timestamps present",
                    "boundary": "structural self-consistency only; no behaviour, "
                                "truthfulness or completeness claim"},
           "scenarios": rows}
    with open(os.path.join(OUT, "composition_result.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("\nRESULT_JSON=" + os.path.join(OUT, "composition_result.json"))
    # A demo must fail loudly if its own clean case stops passing.
    bad = [r for r in rows if r["scenario"].startswith("A_") and r["verdict"] != "PASS"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
