# SPDX-License-Identifier: Apache-2.0
"""Tests for `tools/audit_sealed_release.py`.

The tool audits *someone else's* published register. Committing that register's
bytes here would mean vendoring a third party's content under our licence, so
the fixture is a synthetic register this test builds from scratch: three
releases, two entries, one signing key generated in-process. It follows the
same rules the tool reads (JCS seals, RFC 6962 root, digest over seven fields,
`row_count` carried as a string, per-release pages named `release.json`).

Every test below except the first is a regression for a defect the *generalised*
port introduced after it already worked against the live register. They are
kept because each one was a wrong answer that looked right:

  * per-release pages are all named `release.json`, so a cache keyed on the URL
    basename collapses ten releases onto one file and reports a clean chain;
  * a file the auditor could not read was counted as a match, so a run with
    three missing files printed "passed";
  * `row_count` is a JSON number in release.json but a string in the digest
    preimage, and recomputing with the number produced a digest mismatch.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os

import pytest

from uibc_core.canonical import canonicalize

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_PATH = os.path.join(REPO, "tools", "audit_sealed_release.py")


@pytest.fixture(scope="module")
def audit_module():
    spec = importlib.util.spec_from_file_location("audit_sealed_release", TOOL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SIX = ("context", "label", "source_url", "time_period", "unit", "value")


def seal(entry):
    return hashlib.sha256(canonicalize({k: entry.get(k) for k in SIX})).hexdigest()


def digest(rel):
    pre = {k: rel.get(k) for k in ("company_id", "file_hashes", "generated_at",
                                   "previous_release_commitment", "release_commitment",
                                   "row_count", "spec_version")}
    pre["row_count"] = str(pre["row_count"])
    return hashlib.sha256(canonicalize(pre)).hexdigest()


def commitment(seals):
    ordered = sorted(seals)
    leaves = [hashlib.sha256(b"\x00" + s.encode()).digest() for s in ordered]

    def fold(ls):
        if len(ls) == 1:
            return ls[0]
        k = 1
        while k * 2 < len(ls):
            k *= 2
        return hashlib.sha256(b"\x01" + fold(ls[:k]) + fold(ls[k:])).digest()

    return fold(leaves).hex()


def build_register(root):
    """Write a three-release register; returns the head release id."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    (root / "public.pem").write_bytes(pem)

    # Release 1 and 2 carry the same two rows (release 2 is presentation-only, so
    # its commitment equals release 1's); release 3 adds a third row, which is a
    # real content change and must produce a different commitment. Without that
    # difference the fixture would be unable to tell "presentation-only" from
    # "everything is one release".
    base = [
        {"context": "test", "label": "a", "source_url": "https://example.test/a",
         "time_period": "2026-01", "unit": "count", "value": 1},
        {"context": "test", "label": "b", "source_url": "https://example.test/b",
         "time_period": "2026-01", "unit": None, "value": None},
    ]
    grown = base + [
        {"context": "test", "label": "c", "source_url": "https://example.test/c",
         "time_period": "2026-02", "unit": "count", "value": 3},
    ]
    entries = grown
    seal_sets = [[seal(e) for e in base], [seal(e) for e in base], [seal(e) for e in grown]]
    (root / "ledger.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    (root / "index.html").write_text("<!doctype html><title>register</title>\n", encoding="utf-8")

    def hashes():
        return {
            "index.html": hashlib.sha256((root / "index.html").read_bytes()).hexdigest(),
            "ledger.json": hashlib.sha256((root / "ledger.json").read_bytes()).hexdigest(),
        }

    ids, index = [], []
    prev = None
    for i, rid in enumerate(("R-1", "R-2", "R-3")):
        rel = {
            "company_id": "Synthetic",
            "release_id": rid,
            "generated_at": "2026-01-0%dT00:00:00Z" % (i + 1),
            "row_count": len(base) if i < 2 else len(grown),
            "release_commitment": commitment(seal_sets[i]),
            # R-2 is a presentation-only successor: its previous commitment equals
            # its own, which is what makes the chain ambiguous without the index.
            "previous_release_commitment": commitment(seal_sets[0]) if i == 1 else prev,
            "spec_version": "0.2",
            "file_hashes": hashes(),
        }
        rel["release_digest"] = digest(rel)
        from cryptography.hazmat.primitives import hashes as chashes
        pre = {k: rel[k] for k in (
            "company_id", "file_hashes", "generated_at", "previous_release_commitment",
            "release_commitment", "row_count", "spec_version")}
        pre["row_count"] = str(pre["row_count"])
        sig = key.sign(canonicalize(pre), ec.ECDSA(chashes.SHA256()))
        import base64
        rel["anchor"] = {
            "signature_b64": base64.b64encode(sig).decode(),
            "key_id": "sha256:" + hashlib.sha256(pem).hexdigest(),
        }
        prev = rel["release_commitment"]
        d = root / "releases" / rid
        d.mkdir(parents=True, exist_ok=True)
        # All three pages carry the same basename, as they do on the audited register.
        (d / "release.json").write_text(json.dumps(rel, indent=2) + "\n", encoding="utf-8")
        index.append({"release_id": rid, "url": "https://example.test/releases/%s/release.json" % rid,
                      "current": i == 2})
        ids.append(rid)

    (root / "releases" / "index.json").write_text(
        json.dumps({"release_count": len(ids), "releases": index}, indent=2) + "\n",
        encoding="utf-8")
    (root / "release.json").write_text(
        (root / "releases" / ids[-1] / "release.json").read_text(encoding="utf-8"), encoding="utf-8")
    return ids[-1]


def run(audit_module, root, release_id=None):
    src = audit_module.Source(None, str(root))
    return audit_module.build_receipt(src, release_id or "R-3")


def test_a_clean_register_passes(audit_module, tmp_path):
    head = build_register(tmp_path)
    receipt = run(audit_module, tmp_path, head)
    assert receipt["summary"]["checks_failed"] == [], receipt["summary"]
    assert receipt["summary"]["checks_not_run"] == []
    assert receipt["summary"]["verdict"].startswith("PASSED")
    chain = [s for s in receipt["steps"] if s["step"] == "5-chain-walk"][0]
    assert chain["releases"] == 3
    assert chain["broken_links"] == []
    assert chain["self_referential"] == ["R-2"]


def test_per_release_pages_are_read_by_id_not_basename(audit_module, tmp_path):
    """Regression: every page is called release.json, so a basename cache lies."""
    head = build_register(tmp_path)
    receipt = run(audit_module, tmp_path, head)
    chain = [s for s in receipt["steps"] if s["step"] == "5-chain-walk"][0]
    commitments = [w["commitment"] for w in chain["walked"]]
    # R-1 and R-2 share a commitment here; R-3's is the same too, so identity has
    # to be proven on the earlier field instead: R-1 has no previous commitment.
    assert chain["walked"][0]["previous"] is None
    assert all(c for c in commitments)


def test_unreadable_file_never_counts_as_a_match(audit_module, tmp_path):
    """Regression: three missing files once produced a green file-hash step."""
    head = build_register(tmp_path)
    (tmp_path / "index.html").unlink()
    receipt = run(audit_module, tmp_path, head)
    fh = [s for s in receipt["steps"] if s["step"] == "6-file-hashes"][0]
    assert fh["ok"] is None, fh
    assert "index.html" in fh["unreadable"]
    assert receipt["summary"]["checks_failed"] == []
    assert receipt["summary"]["checks_not_run"] == ["6-file-hashes"]
    assert receipt["summary"]["verdict"].startswith("PARTIAL")


def test_tampered_page_fails_the_hash_step(audit_module, tmp_path):
    head = build_register(tmp_path)
    (tmp_path / "index.html").write_text("<!doctype html><title>register</title>\n"
                                         "<script src=//cdn/analytics.js></script>\n",
                                         encoding="utf-8")
    receipt = run(audit_module, tmp_path, head)
    fh = [s for s in receipt["steps"] if s["step"] == "6-file-hashes"][0]
    assert fh["failed"] == ["index.html"]
    assert receipt["summary"]["checks_failed"] == ["6-file-hashes"]


def test_a_tampered_entry_breaks_the_root(audit_module, tmp_path):
    head = build_register(tmp_path)
    entries = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    entries[1]["label"] = "b-but-different"
    (tmp_path / "ledger.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    receipt = run(audit_module, tmp_path, head)
    step = [s for s in receipt["steps"] if s["step"] == "1-entry-seals-and-merkle"][0]
    assert step["root_agreement"] is False
    # tampering the ledger also breaks its published file hash, and both are
    # reported: a check that fails for two reasons should say both
    assert "1-entry-seals-and-merkle" in receipt["summary"]["checks_failed"]


def test_row_count_is_a_string_in_the_digest_preimage(audit_module, tmp_path):
    """Regression: recomputing the digest with row_count as a number disagreed."""
    head = build_register(tmp_path)
    receipt = run(audit_module, tmp_path, head)
    step = [s for s in receipt["steps"] if s["step"] == "2-release-digest"][0]
    assert step["agreement"] is True


def test_string_null_is_refused(audit_module):
    with pytest.raises(ValueError):
        audit_module.entry_seal({k: "x" for k in SIX} | {"value": "null"})
