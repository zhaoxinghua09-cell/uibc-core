"""UIBC-MEM v0.1 (route step 8): verifiable memory migration - PROPOSAL.

Scope discipline (2026-09-17 route review): v0.1 does ONLY verifiable
memory migration. No memory storage, no retrieval, no continuity claims
beyond the four Preservations:

    Fact Preservation       - the fact content is byte-identical
    Attribution Preservation- who produced/owns the fact is identical
    Citation Preservation   - the source locator is identical
    Version Preservation    - the version identifier is identical

A MemorySet is a list of entries:
    {"memory_id", "content", "attribution", "citation", "version"}

Migration verification compares source vs target BY memory_id (order
independent, like the fixtures 'reordered' discipline). Anything else
(missing/extra/injected entries, changed fields) FAILS with a scoped,
per-entry report.

Honest scope:
1. We verify PRESERVATION, not FAITHFULNESS of the migration process
   (how the target got the memories is out of scope; we check the result).
2. content equality is exact-text (hash), not semantic. Semantic drift is
   explicitly out of scope and must not be claimed.
3. No trust language: a PASS means "these four fields are identical",
   nothing more.

v0.1.1 corrections (2026-09-18, found by mutation fixtures - see
fixtures/generate_memory_fixtures.py):
4. Duplicate memory_id is now checked on BOTH sides. v0.1 checked `source`
   only, while `target` was collapsed with
   `{e["memory_id"]: e for e in target}` - a dict comprehension that silently
   keeps the LAST entry per id. An injected fake entry sharing a real entry's
   id was therefore discarded before comparison, and the report still claimed
   "no injections": a silent memory-injection path straight through the
   highest-weighted rubric dimension (M2 fact preservation, 0.30).
5. An empty source AND empty target is no longer a PASS. Comparing zero
   entries made every Preservation vacuously true, so a submission that
   migrated nothing scored full marks. It is now INCONCLUSIVE/VACUOUS_INPUT:
   nothing was verified, therefore nothing may be claimed.
6. An empty field value is reported as empty, not as missing (the old wording
   conflated `{"content": ""}` with `{}`).
7. Recorded boundary (unchanged, deliberate): undeclared extra fields on an
   entry are NOT inspected - the four Preservations are all that is claimed.
"""

import hashlib
import json

MEM_SCHEMA = "uibc-mem/0.1"

# Verifier version for THIS module, carried in every report so a rubric score
# can cite "which verify produced this" (archive SS31 'Verifier Version' field).
# v0.1 -> v0.1.1 because the duplicate-id and vacuous-input paths below change
# which verdict is produced - a breaking change by this project's own rule.
MEM_VERIFIER_VERSION = "0.1.1"

REQUIRED_FIELDS = ["memory_id", "content", "attribution", "citation", "version"]

PRESERVATIONS = ["fact", "attribution", "citation", "version"]


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _entry_hash(entry: dict) -> str:
    return hashlib.sha256(_canon(entry)).hexdigest()


def _validate_entry(entry, idx) -> list:
    errs = []
    if not isinstance(entry, dict):
        return [f"entry[{idx}] is not an object"]
    for f in REQUIRED_FIELDS:
        if f not in entry:
            errs.append(f"entry[{idx}] missing field {f!r}")
        elif not entry.get(f):
            errs.append(f"entry[{idx}] field {f!r} is empty (must be non-empty)")
    return errs


def memory_root(entries: list) -> str:
    """Order-independent root: sha256 over sorted per-entry hashes."""
    hashes = sorted(_entry_hash(e) for e in entries)
    return hashlib.sha256(_canon(hashes)).hexdigest()


def verify_migration(source: list, target: list) -> dict:
    """Compare two memory sets by memory_id. Returns a scoped report."""
    checks = []
    structural_errors = []
    for label, entries in (("source", source), ("target", target)):
        if not isinstance(entries, list):
            structural_errors.append(f"{label} is not a list")
            continue
        for i, e in enumerate(entries):
            structural_errors.extend(
                f"{label}: {msg}" for msg in _validate_entry(e, i))
    # Duplicate ids are checked on BOTH sides (v0.1.1). `target` is collapsed
    # into a dict a few lines below; that keeps only the LAST entry per id, so
    # an injected duplicate was previously discarded before comparison and the
    # report still said "no injections".
    for label, entries in (("source", source), ("target", target)):
        if not isinstance(entries, list):
            continue
        ids = [e.get("memory_id") for e in entries if isinstance(e, dict)]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            structural_errors.append(f"{label} has duplicate memory_id values: {dupes}")
    if structural_errors:
        return {
            "schema": MEM_SCHEMA, "result": "FAIL",
            "result_code": "MALFORMED_INPUT",
            "verifier_version": MEM_VERIFIER_VERSION,
            "checks": [{"id": "M0", "name": "input structure",
                        "result": "FAIL", "detail": "; ".join(structural_errors)}],
            "scope": "Structure only; preservation checks not run.",
        }

    # Vacuous input (v0.1.1): with zero entries every Preservation is trivially
    # true, so an empty-to-empty "migration" used to PASS and score full marks.
    # Nothing was verified, therefore nothing may be claimed - INCONCLUSIVE,
    # which is explicitly not a pass.
    if not source and not target:
        return {
            "schema": MEM_SCHEMA, "result": "INCONCLUSIVE",
            "result_code": "VACUOUS_INPUT",
            "verifier_version": MEM_VERIFIER_VERSION,
            "source_memory_root": memory_root(source),
            "target_memory_root": memory_root(target),
            "entries_compared": 0,
            "changed_entries": [],
            "checks": [{"id": "M0", "name": "input sufficiency",
                        "result": "INCONCLUSIVE",
                        "detail": "source and target are both empty: nothing to migrate, "
                                  "so the four Preservations cannot be evidenced. "
                                  "INCONCLUSIVE is NOT a pass."}],
            "scope": "No preservation check was run; an empty entry set cannot support "
                     "a fidelity claim.",
            "statement": "Nothing was verified (empty entry set).",
        }

    # Safe to collapse now: duplicates on both sides were rejected above.
    src = {e["memory_id"]: e for e in source}
    tgt = {e["memory_id"]: e for e in target}

    missing = sorted(set(src) - set(tgt))
    extra = sorted(set(tgt) - set(src))

    per_fields = {p: True for p in PRESERVATIONS}
    field_details = {p: [] for p in PRESERVATIONS}
    changed_entries = []

    for mid in sorted(set(src) & set(tgt)):
        s, t = src[mid], tgt[mid]
        pairs = [("fact", "content"), ("attribution", "attribution"),
                 ("citation", "citation"), ("version", "version")]
        for pres, field in pairs:
            if s.get(field) != t.get(field):
                per_fields[pres] = False
                field_details[pres].append(mid)
                changed_entries.append({"memory_id": mid, "field": field,
                                        "from": s.get(field), "to": t.get(field)})

    def add(cid, name, passed, detail):
        checks.append({"id": cid, "name": name,
                       "result": "PASS" if passed else "FAIL", "detail": detail})

    add("M1", "entry completeness", not missing and not extra,
        (f"missing in target: {missing}; " if missing else "")
        + (f"injected in target: {extra}" if extra else "")
        or f"all {len(src)} entries present, no injections")
    for cid, pres in (("M2", "fact"), ("M3", "attribution"),
                      ("M4", "citation"), ("M5", "version")):
        add(cid, f"{pres} preservation", per_fields[pres],
            f"identical in {len(src)} entries" if per_fields[pres]
            else f"changed in: {field_details[pres]}")

    ok = all(c["result"] == "PASS" for c in checks)
    return {
        "schema": MEM_SCHEMA,
        "result": "PASS" if ok else "FAIL",
        "result_code": "OK",
        "verifier_version": MEM_VERIFIER_VERSION,
        "source_memory_root": memory_root(source),
        "target_memory_root": memory_root(target),
        "entries_compared": len(set(src) & set(tgt)),
        "changed_entries": changed_entries,
        "checks": checks,
        "scope": "Exact-text preservation of content/attribution/citation/version "
                 "per memory_id. NOT checked: semantic drift, migration process, "
                 "retrieval fidelity, anything outside the four Preservations.",
        "statement": ("All four Preservations hold for every compared entry."
                      if ok else "Preservation violations detected (see checks)."),
    }
