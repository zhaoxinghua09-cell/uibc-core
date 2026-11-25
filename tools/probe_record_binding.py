"""Probe: are record signatures bound to their own record, or portable?

21 CFR 11.70 asks that an electronic signature be linked to its record so that
it "cannot be excised, copied, or otherwise transferred to falsify an
electronic record by ordinary means". This probe answers that question on an
AEE observation-record set.

The record set is a vendored copy of an upstream conformance vector (Apache-2.0,
`agent-evidence-vectors` 0.36.3, suiteRevision 32; see the fixture README). Its
signatures are real Ed25519 signatures made with deterministic test keys that
anyone re-derives:

    seed(role) = SHA-256("in-toto-aee-test-key/<role>/v1")

Experiments, all on the same set:

1. clean      - every record verifies under the pinned substrate key.
2. transplant - record 0's signature list is copied wholesale onto record 1;
                record 1 must stop verifying.
3. excise     - record 1's signatures are deleted; record 1 must stop verifying.
4. control    - record 0, untouched, still verifies after record 1 was stripped.

Exit 0 only when all four hold. If the optional upstream package is installed,
the vendored copy is also compared with it, so an edited fixture cannot pass.
"""
import copy
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from uibc_core import records
from uibc_core.ed25519 import publickey

ROLE = "substrate-observation-test"
SEED = hashlib.sha256(("in-toto-aee-test-key/%s/v1" % ROLE).encode("ascii")).digest()
PINNED = publickey(SEED)

FIXTURE = os.path.join(REPO, "fixtures", "aee-record-binding", "statement.json")
UPSTREAM_NAME = "v0099f25838779fcc.json"


def upstream_path():
    try:
        import agent_evidence_vectors
    except Exception:
        return None
    base = os.path.join(os.path.dirname(os.path.abspath(agent_evidence_vectors.__file__)),
                        "corpora", "vectors", "statements")
    p = os.path.join(base, UPSTREAM_NAME)
    return p if os.path.isfile(p) else None


def load():
    with open(FIXTURE, "r", encoding="utf-8") as f:
        stmt = json.load(f)
    up = upstream_path()
    if up:
        with open(up, "r", encoding="utf-8") as f:
            if json.load(f) != stmt:
                return None, "the vendored fixture differs from the installed upstream vector"
    return stmt, None


def flags(stmt):
    return [records.record_verified(r, [PINNED]) for r in records.records_of(stmt)]


def main():
    stmt, err = load()
    if err:
        print("REFUSING: %s" % err)
        return 2
    recs = records.records_of(stmt)
    if len(recs) < 2:
        print("REFUSING: the fixture carries %d records, need 2" % len(recs))
        return 2

    f0 = flags(stmt)
    print("fixture=%s records=%d verified=%d" % (UPSTREAM_NAME, len(recs), sum(f0)))
    if not all(f0):
        print("FAIL clean: a record of the vendored accept vector does not verify")
        return 1

    raw = stmt["predicate"]["observationRecords"]
    a_sigs = copy.deepcopy(raw[0].get("signatures") or [])

    transplanted = copy.deepcopy(stmt)
    transplanted["predicate"]["observationRecords"][1]["signatures"] = copy.deepcopy(a_sigs)
    after_t = flags(transplanted)
    ok_transplant = after_t[1] is False
    print("transplant: rec0.sig -> rec1, rec1 verifies=%s (want False)" % after_t[1])

    excised = copy.deepcopy(stmt)
    excised["predicate"]["observationRecords"][1].pop("signatures", None)
    after_e = flags(excised)
    ok_excise = after_e[1] is False
    print("excise: rec1.signatures removed, rec1 verifies=%s (want False)" % after_e[1])

    ok_control = after_e[0] is True
    print("control: rec0 untouched still verifies=%s (want True)" % after_e[0])

    if ok_transplant and ok_excise and ok_control:
        print("OK record signatures are bound to their records (%d records)" % len(recs))
        return 0
    print("FAIL: a record signature survived transplant or excision")
    return 1


if __name__ == "__main__":
    sys.exit(main())
