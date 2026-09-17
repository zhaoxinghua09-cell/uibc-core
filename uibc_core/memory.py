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
"""

import hashlib
import json

MEM_SCHEMA = "uibc-mem/0.1"

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
        if not entry.get(f):
            errs.append(f"entry[{idx}] missing field {f!r}")
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
    ids_s = [e.get("memory_id") for e in source if isinstance(e, dict)]
    if len(ids_s) != len(set(ids_s)):
        structural_errors.append("source has duplicate memory_id values")
    if structural_errors:
        return {
            "schema": MEM_SCHEMA, "result": "FAIL",
            "result_code": "MALFORMED_INPUT",
            "checks": [{"id": "M0", "name": "input structure",
                        "result": "FAIL", "detail": "; ".join(structural_errors)}],
            "scope": "Structure only; preservation checks not run.",
        }

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
