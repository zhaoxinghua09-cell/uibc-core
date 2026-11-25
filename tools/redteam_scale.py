#!/usr/bin/env python3
"""Extra red-team cases used to grow the shipped conformance suite.

Each mutator takes a *correct* package and breaks exactly one thing. The
exporter runs the verifier on every case and records the checks it actually
failed, so a mutator that produces no named refusal is skipped rather than
silently contributing a case that proves nothing. Expectations are measured,
never authored here.
"""
from __future__ import annotations

import os

import outsider_audit as oa


def _entries(pkg):
    return oa._index(pkg)


def _replace_index(pkg, fn):
    path, raw, entries = oa._index(pkg)
    new = fn(entries)
    oa._save_index(path, raw, new)


def _files(pkg):
    return oa._evidence_files(pkg)


def m_swap_file_contents(pkg):
    """Swap two evidence files' bytes but leave hashes pointing at their own paths."""
    _, files = _files(pkg)
    a, b = oa._read(files[0]), oa._read(files[1])
    oa._write(files[0], b)
    oa._write(files[1], a)


def m_append_one_newline(pkg):
    """One added byte is still a different hash."""
    _, files = _files(pkg)
    oa._write(files[0], oa._read(files[0]) + b"\n")


def m_duplicate_evidence_id(pkg):
    """Two entries claiming the same identity."""
    def f(entries):
        entries[1]["evidence_id"] = entries[0]["evidence_id"]
        return entries
    _replace_index(pkg, f)


def m_impossible_day(pkg):
    """The 31st of November does not exist."""
    def f(entries):
        entries[0]["created_at"] = "2026-11-31T00:00:00Z"
        return entries
    _replace_index(pkg, f)


def m_offset_form_timestamp(pkg):
    """A non-Z form where the schema only accepts one shape."""
    def f(entries):
        entries[1]["created_at"] = "2026-11-06T06:20:53"
        return entries
    _replace_index(pkg, f)


def m_declare_missing_file(pkg):
    """Declare a file that is not there: the index must not be trusted blindly."""
    def f(entries):
        entries.append({"evidence_id": "00000000-0000-4000-8000-000000000000",
                        "type": "ACTION", "path": "files/never-written.txt",
                        "content_hash": "0" * 64,
                        "created_at": "2026-11-06T06:20:53Z",
                        "media_type": "text/plain", "note": "declared, absent"})
        return entries
    _replace_index(pkg, f)


def m_path_escapes_evidence(pkg):
    """A path that leaves the evidence tree."""
    def f(entries):
        entries[0]["path"] = "../manifest.json"
        return entries
    _replace_index(pkg, f)


def m_evidence_count_lies(pkg):
    """The manifest counts fewer members than the index declares."""
    man_path = os.path.join(pkg, "manifest.json")
    man = oa._json(man_path)
    man["evidence_count"] = man["evidence_count"] - 1
    oa._dump(man_path, man)


def m_agent_id_drift(pkg):
    """identity.json and manifest.json disagree about who acted."""
    ident_path = os.path.join(pkg, "identity.json")
    ident = oa._json(ident_path)
    for key in ("agent_id", "subject", "id"):
        if key in ident:
            ident[key] = "fx-agent-999"
            break
    oa._dump(ident_path, ident)


def m_unknown_status_token(pkg):
    """A status outside the vocabulary must not be read as success."""
    man_path = os.path.join(pkg, "manifest.json")
    man = oa._json(man_path)
    man["status"] = "APPROVED-BY-ITSELF"
    oa._dump(man_path, man)


def m_lifecycle_backwards(pkg):
    """An event that predates the package it belongs to."""
    lc_path = os.path.join(pkg, "lifecycle.json")
    lc = oa._json(lc_path)
    lc["events"] = [{"type": "CREATED", "at": "2026-11-06T06:20:53Z"},
                    {"type": "SUBMITTED", "at": "2026-11-05T06:20:53Z"}]
    oa._dump(lc_path, lc)


def m_hex_case_change(pkg):
    """Upper-case a hash: the same bytes, a different string."""
    def f(entries):
        entries[0]["content_hash"] = entries[0]["content_hash"].upper()
        return entries
    _replace_index(pkg, f)


def m_short_hash(pkg):
    """A truncated digest is not a digest."""
    def f(entries):
        entries[1]["content_hash"] = entries[1]["content_hash"][:16]
        return entries
    _replace_index(pkg, f)


def m_reorder_entries(pkg):
    """Reorder the index: a root computed in order no longer matches."""
    def f(entries):
        return list(reversed(entries))
    _replace_index(pkg, f)


def m_remove_seal(pkg):
    """A package with no seal at all is not a signed package."""
    seal = os.path.join(pkg, "signatures", "seal.json")
    if os.path.exists(seal):
        os.remove(seal)


def m_seal_bytes_short(pkg):
    """Cut the seal signature in half: it cannot verify."""
    seal = os.path.join(pkg, "signatures", "seal.json")
    if os.path.exists(seal):
        obj = oa._json(seal)
        sig = obj.get("signature")
        if isinstance(sig, str) and len(sig) > 8:
            obj["signature"] = sig[: len(sig) // 2]
            oa._dump(seal, obj)


def m_two_entries_same_path(pkg):
    """Two declarations pointing at one file: a double count is not a count."""
    def f(entries):
        dup = dict(entries[0])
        dup["evidence_id"] = "11111111-1111-4111-8111-111111111111"
        return entries + [dup]
    _replace_index(pkg, f)


def m_empty_evidence_file(pkg):
    """Zero bytes is a different file, whatever the index says."""
    _, files = _files(pkg)
    oa._write(files[0], b"")


def m_schema_string_tampered(pkg):
    """An unknown schema string must be rejected, not guessed at."""
    man_path = os.path.join(pkg, "manifest.json")
    man = oa._json(man_path)
    man["schema"] = "uibc-core/0.2.2-proposal-typo"
    oa._dump(man_path, man)


def m_index_media_type_swap(pkg):
    """Claiming a media type the bytes are not."""
    def f(entries):
        entries[0]["media_type"] = "application/octet-stream"
        return entries
    _replace_index(pkg, f)


# --- second-member variants: the same break applied to the other file ---------
# One case per file is not padding: an implementation that only checks the first
# declared member passes the first case and fails these.

def m_flip_second_file(pkg):
    _, files = _files(pkg)
    data = bytearray(oa._read(files[1]))
    data[0] ^= 0x80
    oa._write(files[1], bytes(data))


def m_truncate_second_file(pkg):
    _, files = _files(pkg)
    data = oa._read(files[1])
    oa._write(files[1], data[: max(1, len(data) // 3)])


def m_second_impossible_day(pkg):
    def f(entries):
        entries[1]["created_at"] = "2026-02-30T00:00:00Z"
        return entries
    _replace_index(pkg, f)


def m_second_hash_short(pkg):
    def f(entries):
        entries[1]["content_hash"] = entries[1]["content_hash"][:40]
        return entries
    _replace_index(pkg, f)


# --- tree / chain variants (the package carries both) -------------------------

@oa._needs_v11
def m_proof_index_shift(pkg):
    """Shift every proof index by one: inclusion proofs no longer address the leaves."""
    doc = oa._json(os.path.join(pkg, "evidence", "merkle.json"))
    for p in doc.get("proofs", []):
        p["index"] = p["index"] + 1
    oa._dump(os.path.join(pkg, "evidence", "merkle.json"), doc)


@oa._needs_v11
def m_proof_truncated(pkg):
    """Cut one proof step: a shorter path proves nothing."""
    doc = oa._json(os.path.join(pkg, "evidence", "merkle.json"))
    if doc.get("proofs") and doc["proofs"][0].get("proof"):
        doc["proofs"][0]["proof"] = doc["proofs"][0]["proof"][:-1]
    oa._dump(os.path.join(pkg, "evidence", "merkle.json"), doc)


@oa._needs_v11
def m_chain_link_zeroed(pkg):
    """Zero the back-link of the second receipt: the chain stops being a chain."""
    doc = oa._json(os.path.join(pkg, "evidence", "chain.json"))
    doc["receipts"][1]["previous_receipt_hash"] = "0" * 64
    oa._dump(os.path.join(pkg, "evidence", "chain.json"), doc)


@oa._needs_v11
def m_chain_reordered(pkg):
    """Swap the receipts: order is the claim."""
    doc = oa._json(os.path.join(pkg, "evidence", "chain.json"))
    doc["receipts"] = list(reversed(doc["receipts"]))
    oa._dump(os.path.join(pkg, "evidence", "chain.json"), doc)


EXTRA_RED_TEAM = [
    ("swap the bytes of two evidence files", m_swap_file_contents, "FAIL",
     "S4 hashes are per-path, so a swap cannot pass"),
    ("append one newline to an evidence file", m_append_one_newline, "FAIL",
     "one byte is enough for S4"),
    ("give two entries the same evidence_id", m_duplicate_evidence_id, "FAIL",
     "S12 judges identifier values"),
    ("set an evidence date to November 31", m_impossible_day, "FAIL",
     "S12 rejects impossible calendar values"),
    ("write a timestamp without the Z form", m_offset_form_timestamp, "FAIL",
     "S12 rejects a shape the schema does not allow"),
    ("declare an evidence file that does not exist", m_declare_missing_file, "FAIL",
     "the declaration must resolve to bytes"),
    ("let an index path leave the evidence tree", m_path_escapes_evidence, "FAIL",
     "path confinement is part of the shape"),
    ("count one file fewer than declared", m_evidence_count_lies, "FAIL",
     "S2 compares counts across files"),
    ("change the agent id in identity.json only", m_agent_id_drift, "FAIL",
     "S2 compares identity across files"),
    ("use a status token outside the vocabulary", m_unknown_status_token, "FAIL",
     "an unknown status must not read as success"),
    ("record a lifecycle event before creation", m_lifecycle_backwards, "FAIL",
     "ordering is a checkable claim, not a comment"),
    ("upper-case one stored hash", m_hex_case_change, "FAIL",
     "hash comparison is octet comparison, not case-insensitive text"),
    ("truncate one stored hash to 16 characters", m_short_hash, "FAIL",
     "S12 judges digest length"),
    ("reverse the order of the evidence index", m_reorder_entries, "FAIL",
     "S5 recomputes the root in declaration order"),
    ("delete the seal", m_remove_seal, "NOT_PASS",
     "a package with no seal is not signed"),
    ("cut the seal signature in half", m_seal_bytes_short, "NOT_PASS",
     "S6 must not pass a malformed signature"),
    ("declare the same file twice", m_two_entries_same_path, "FAIL",
     "a double count is not a count"),
    ("truncate an evidence file to zero bytes", m_empty_evidence_file, "FAIL",
     "S4 compares bytes, not intentions"),
    ("misspell the manifest schema string", m_schema_string_tampered, "FAIL",
     "an unknown schema is refused, not guessed at"),
    ("relabel an evidence file's media type", m_index_media_type_swap, "FAIL",
     "a declared type the bytes are not"),
    ("flip one byte in the second evidence file", m_flip_second_file, "FAIL",
     "S4 is per member, not first member only"),
    ("truncate the second evidence file", m_truncate_second_file, "FAIL",
     "same, second member"),
    ("set the second entry to February 30", m_second_impossible_day, "FAIL",
     "S12 judges every date, not the first"),
    ("truncate the second stored hash to 40 characters", m_second_hash_short, "FAIL",
     "S12 judges every digest, not the first"),
    ("shift every Merkle proof index by one", m_proof_index_shift, "FAIL",
     "S13 resolves the leaf the proof names"),
    ("cut one Merkle proof step", m_proof_truncated, "FAIL",
     "a shorter path proves nothing"),
    ("zero the back-link of the second receipt", m_chain_link_zeroed, "FAIL",
     "S17 recomputes the link"),
    ("swap the order of the receipt chain", m_chain_reordered, "FAIL",
     "order is the claim, not a comment"),
]
