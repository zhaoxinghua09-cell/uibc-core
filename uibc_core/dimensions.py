"""Five verdicts kept separate, per Section 7 of the draft.

The complaint this answers (jones-SCITT pain point E04, and round 9 of our own
external review) is that one composite "the package is fine" turns five
independent questions into one. They are not independent in evidence, so each
must be recorded on its own, and none may be inferred from another:

  signature  -- did the seal verify under the key the reader holds?
  authority  -- was the actor entitled to say this? (lifecycle actor allow-list)
  binding    -- is this the actor the package claims? (identity consistency)
  status     -- is this still the current state? (checkpoint, pin, anchor)
  evidence   -- do the bytes still hash to what the package commits?

`record()` never returns OK: it returns CHECKED_PASS only when every member
check of that dimension is PASS, REFUSED when any member is FAIL, and
NOT_CHECKED when a member was skipped or inconclusive. A missing dimension is
a refusal to export the decision, not a pass -- which is why aggregate()
returns EXPORT_REFUSED unless all five are CHECKED_PASS.

Nothing here is new cryptography. It is a total, documented partition of the
checks the verifier already runs, so that a reader cannot accidentally treat
"the seal verified" as "the actor was authorised".
"""

from typing import Dict, Iterable, List

# Every check id the reference verifier emits, assigned to exactly one dimension.
# tests/test_dimensions.py asserts this table is total over the ids the corpus
# actually produces, so adding a check without assigning it fails the suite.
DIMENSIONS: Dict[str, List[str]] = {
    "signature": ["S6", "S14"],          # seal signature, strict base64 that feeds it
    "authority": ["S3"],                 # lifecycle state machine, actors, once-only
    "binding": ["S2"],                   # agent identity consistent across the package
    "status": ["S8", "S9", "S15", "S17"],# checkpoint, out-of-band pin, anchor, receipts
    "evidence": ["S1", "S4", "S5", "S7", "S10", "S11", "S12", "S13", "S16", "S18", "S19"],
}

ORDER = ["signature", "authority", "binding", "status", "evidence"]

CHECKED_PASS = "CHECKED_PASS"
REFUSED = "REFUSED"
NOT_CHECKED = "NOT_CHECKED"
EXPORT_REFUSED = "EXPORT_REFUSED"


def record(checks: Iterable[dict]) -> Dict[str, dict]:
    """Group the verifier's checks into the five verdicts.

    `checks` is whatever the verifier emitted: dicts with `id` and `result`
    (PASS / FAIL / INCONCLUSIVE / SKIP). Unknown ids are reported under
    `_unassigned` rather than being silently dropped, because a check that
    belongs to no dimension is a defect in this table, not a pass.
    """
    by_id = {c["id"]: c for c in checks if c.get("id")}
    out: Dict[str, dict] = {}
    for dim in ORDER:
        members = [by_id[i] for i in DIMENSIONS[dim] if i in by_id]
        if not members:
            out[dim] = {"verdict": NOT_CHECKED, "why": "no member check ran",
                        "checks": []}
            continue
        fails = [m["id"] for m in members if m["result"] == "FAIL"]
        unrun = [m["id"] for m in members
                 if m["result"] not in ("PASS", "FAIL")]
        missing = [i for i in DIMENSIONS[dim] if i not in by_id]
        if fails:
            out[dim] = {"verdict": REFUSED, "why": "failed at " + ", ".join(fails),
                        "checks": [m["id"] for m in members]}
        elif unrun or missing:
            out[dim] = {"verdict": NOT_CHECKED,
                        "why": "not checked: " + ", ".join(unrun + missing),
                        "checks": [m["id"] for m in members]}
        else:
            out[dim] = {"verdict": CHECKED_PASS,
                        "why": "all of " + ", ".join(DIMENSIONS[dim]) + " passed",
                        "checks": [m["id"] for m in members]}
    assigned = {i for ids in DIMENSIONS.values() for i in ids}
    extra = [i for i in by_id if i not in assigned and i != "S0"]
    if extra:
        out["_unassigned"] = {"verdict": NOT_CHECKED,
                              "why": "check belongs to no dimension: " + ", ".join(sorted(extra)),
                              "checks": sorted(extra)}
    return out


def aggregate(dims: Dict[str, dict]) -> str:
    """One bit for "may this leave the building", derived from the five, never from a score."""
    if dims.get("_unassigned"):
        return EXPORT_REFUSED
    if any(dims[d]["verdict"] != CHECKED_PASS for d in ORDER):
        return EXPORT_REFUSED
    return "EXPORTABLE"
