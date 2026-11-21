#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M3: build an eQMS-shaped export, then judge it. The seam, demonstrated.

Why this exists: three QMS/PLM vendors already ship "PCCP change management" and
"PCCP envelope monitoring" (Modern Requirements' Agents4DevOps, Cloudtheapp,
ComplianceQuest). Competing there is pointless. What none of them hand over is a
verdict a third party can recompute offline. This sample shows the handover:

    QMS export (their field names)  ->  uibc.eqms-records/1  ->  verdict

The field mapping below is authored by us from vendors' public documentation; it
is NOT an official integration with any of them, and nothing here was validated
against a real tenant. Say that plainly wherever this is shown.

    python tools/eqms_sample.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from uibc_core.canonical import hash_obj  # noqa: E402
from eqms_contract import run as judge, SCHEMA_IN  # noqa: E402

OUT = os.path.join(ROOT, "docs", "samples")


def qms_change_record(rev, at, category, dataset, perf, impact, approver):
    """A change record shaped like a QMS change-control row.

    Fields chosen to mirror what Cloudtheapp and Modern Requirements both expose
    publicly: modification category, validation dataset reference, performance
    data, impact assessment, approval. Their names differ; the shape does not.
    """
    return {
        "change_id": "CC-%s" % rev,
        "modification_category": category,
        "validation_dataset_ref": dataset,
        "performance_data": perf,
        "impact_assessment": impact,
        "approved_by": approver,
        "approved_at": at,
        "device_version": rev,
    }


def main():
    os.makedirs(OUT, exist_ok=True)

    # Two revisions of the same device, as a QMS would export them.
    rev_a = qms_change_record(
        "1.0.0", "2026-10-02T09:14:00Z", "initial-release",
        "dataset:ds-2026-09", {"sensitivity": 0.941, "specificity": 0.887},
        "no new hazard identified", "qa-lead@example")
    rev_b = qms_change_record(
        "1.1.0", "2026-11-14T08:02:00Z", "ai-model-retrain",
        "dataset:ds-2026-11", {"sensitivity": 0.948, "specificity": 0.891},
        "threshold unchanged; labelling unchanged", "qa-lead@example")

    export = {
        "system": "example-eqms (field names modelled on public vendor docs, "
                  "not an integration)",
        "subject": "agent:medxpert-assist",
        "records": [
            {"origin": "eqms:rev-1.0.0", "kind": "change_record",
             "subject": "agent:medxpert-assist", "at": rev_a["approved_at"],
             "seq": 1, "payload": rev_a, "refs": []},
            {"origin": "eqms:rev-1.1.0", "kind": "change_record",
             "subject": "agent:medxpert-assist", "at": rev_b["approved_at"],
             "seq": 2, "payload": rev_b,
             "refs": ["sha256:" + hash_obj(rev_a)]},
        ],
    }

    sample_path = os.path.join(OUT, "eqms-sample-1.json")
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump({"schema": SCHEMA_IN, **export}, f, ensure_ascii=False, indent=2)

    verdict = judge({"schema": SCHEMA_IN, **export})
    verdict_path = os.path.join(OUT, "eqms-verdict-1.json")
    with open(verdict_path, "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=2)

    print("%s records=%d origins=%d codes=%s"
          % (verdict["verdict"], verdict["counts"]["records"],
             verdict["counts"]["origins"],
             ",".join(sorted({x["code"] for x in verdict["findings"]})) or "-"))
    print("SAMPLE=" + sample_path)
    print("VERDICT=" + verdict_path)
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
