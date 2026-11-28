"""`uibc-scitt/2`: the same six steps, with the inclusion proof actually fixed.

Why a second profile id and not an edit to `/1`: `/1` registers a *flat* evidence
root (SHA-256 over the JCS list of content hashes, `canonical.evidence_root`).
No inclusion proof can exist for that construction - the root is not a tree - so
`/1` can never say `OK`, by design, and changing the root's meaning under the same
identifier would silently invalidate every receipt already issued against `/1`.
A verifiable profile needs a version number, so it gets one.

What `/2` fixes, normatively:

* **root** - RFC 6962 MTH (Section 2.1) over leaves derived from the package's
  content hashes, taken in ascending order of the 32-byte digest. The digest is
  hashed as bytes, not as its hex text: `leaf = SHA-256(0x00 || digest)`. An
  empty package is refused earlier (`count >= 1`), so the empty-tree convention
  never decides a verdict here.
* **vdp** (COSE label 396) - a CBOR array of exactly four elements:

      0: leaf hash   bstr, 32 bytes (the RFC 6962 leaf hash, not the raw digest)
      1: index       uint, 0-based leaf position
      2: tree_size   uint, must equal the registered `count`
      3: path        array of bstr(32), bottom-up sibling hashes

  Four elements, no extension points, no optional members: a reader that sees
  anything else refuses the receipt rather than guessing what an extra field
  might mean.

`OK` is reachable, and only under all four of: root reproduced, registered value
byte-equal, signature verified, inclusion proof verified - and the issuer trusted
from a key list supplied out of band. Inclusion verified but issuer unasked is
`PARTIAL_ISSUER_UNCHECKED`, because proof of membership is not proof of who
registered it.

What `OK` still does *not* mean: that the evidence is true, or that the service
will keep the tree. It means this package contains this file, the file is inside
a tree of size N whose root the receipt signs, and the key that signed is one the
verifier was told to trust.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

from . import canonical, cose_min, ed25519, merkle

PROFILE_ID = "uibc-scitt/1"
PROFILE_ID_2 = "uibc-scitt/2"

LBL_VDS = 395
LBL_VDP = 396

OK = "OK"
PARTIAL_ISSUER_UNCHECKED = "PARTIAL_ISSUER_UNCHECKED"
FAIL_INCLUSION = "FAIL_INCLUSION"
FAIL_VALUE_MISMATCH = "FAIL_VALUE_MISMATCH"
FAIL_SIGNATURE = "FAIL_SIGNATURE"
FAIL_PACKAGE = "FAIL_PACKAGE"
FAIL_MALFORMED = "FAIL_MALFORMED"
UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
FAIL_UNTRUSTED_ISSUER = "FAIL_UNTRUSTED_ISSUER"

#: vds 1 = "rfc9162-sha256" in the draft's registry request. `/2` fixes the tree
#: construction as RFC 6962, so this is the only scheme it accepts.
SUPPORTED_VDS = {1: "rfc9162-sha256"}


def _leaves(hashes: List[str]) -> List[bytes]:
    """RFC 6962 leaves over ascending content-hash digests."""
    ordered = sorted(bytes.fromhex(h) for h in hashes)
    return [merkle.leaf_hash(d) for d in ordered]


def merkle_root_hex(hashes: List[str]) -> str:
    return merkle.root_hash(_leaves(hashes)).hex()


def registered_value(root_hex: str, count: int, agent_id: str,
                     profile: str = PROFILE_ID_2) -> bytes:
    """Bytes a service registers under `/2`: three members and the root."""
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("count must be a positive int")
    if not isinstance(root_hex, str) or len(root_hex) != 64:
        raise ValueError("root must be 64 lowercase hex characters")
    obj = {"profile": profile, "root": root_hex, "count": count, "agent_id": agent_id}
    return canonical.canonicalize(obj)


def package_facts(pkg_dir: str) -> Tuple[str, int, str, List[str], List[str]]:
    """(root_hex, count, agent_id, content_hashes, problems) recomputed from disk."""
    problems: List[str] = []
    try:
        entries = json.load(open(os.path.join(pkg_dir, "evidence", "index.json"),
                                 encoding="utf-8"))["entries"]
        agent_id = json.load(open(os.path.join(pkg_dir, "manifest.json"),
                                  encoding="utf-8"))["agent_id"]
    except Exception as exc:
        return "", 0, "", [], ["package unreadable: %s" % exc]

    hashes: List[str] = []
    declared = set()
    for e in entries:
        rel, ch = e.get("path"), e.get("content_hash")
        if not rel or not ch:
            problems.append("entry without path or content_hash: %r" % (e,))
            continue
        declared.add(os.path.normpath(rel))
        full = os.path.join(pkg_dir, "evidence", rel)
        if not os.path.exists(full):
            problems.append("declared file missing: %s" % rel)
            continue
        actual = canonical.hash_file(full)
        if actual != ch:
            problems.append("content changed: %s (%s != %s)" % (rel, actual[:8], ch[:8]))
            continue
        hashes.append(actual)

    ev_dir = os.path.join(pkg_dir, "evidence")
    for root, _dirs, files in os.walk(ev_dir):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), ev_dir)
            if os.path.normpath(rel) == "index.json":
                continue
            if os.path.normpath(rel) not in declared:
                problems.append("undeclared file under evidence/: %s" % rel)

    if problems:
        return "", 0, agent_id, [], problems
    return merkle_root_hex(hashes), len(hashes), agent_id, hashes, []


def vdp_bytes(hashes: List[str], index: int) -> bytes:
    """The four-element vdp for one leaf of this package's tree."""
    leaves = _leaves(hashes)
    if not 0 <= index < len(leaves):
        raise IndexError("leaf index out of range")
    return cose_min.encode([leaves[index], index, len(leaves),
                            merkle.audit_path(leaves, index)])


def vdp_for_hash(hashes: List[str], content_hash_hex: str) -> bytes:
    ordered = sorted(bytes.fromhex(h) for h in hashes)
    return vdp_bytes(hashes, ordered.index(bytes.fromhex(content_hash_hex)))


def read_vdp(vdp) -> Tuple[Optional[bytes], Optional[int], Optional[int], Optional[list], str]:
    """(leaf, index, size, path, reason) from the header's vdp; reason non-empty = bad."""
    try:
        item = cose_min.decode(vdp) if isinstance(vdp, (bytes, bytearray)) else vdp
    except cose_min.CborError as exc:
        return None, None, None, None, "vdp is not CBOR: %s" % exc
    if not isinstance(item, list) or len(item) != 4:
        return None, None, None, None, "vdp must be a 4-element array, got %r" % (
            None if not isinstance(item, list) else len(item),)
    leaf, index, size, path = item
    if not isinstance(leaf, bytes) or len(leaf) != 32:
        return None, None, None, None, "vdp[0] (leaf) must be a 32-byte bstr"
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        return None, None, None, None, "vdp[1] (index) must be a non-negative int"
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        return None, None, None, None, "vdp[2] (tree_size) must be a positive int"
    if not isinstance(path, list) or not all(
            isinstance(p, bytes) and len(p) == 32 for p in path):
            return None, None, None, None, "vdp[3] (path) must be a list of 32-byte bstr"
    return leaf, index, size, path, ""


def _decode_receipt(receipt: bytes) -> Tuple[Optional[dict], Optional[bytes], str]:
    try:
        msg = cose_min.decode(receipt)
    except cose_min.CborError as exc:
        return None, None, "cbor: %s" % exc
    if not isinstance(msg, list) or len(msg) != 4:
        return None, None, "not a COSE_Sign1 4-element array"
    protected, _u, payload, _s = msg
    if not isinstance(protected, bytes):
        return None, None, "protected header must be a bstr"
    try:
        hdr = cose_min.decode(protected)
    except cose_min.CborError as exc:
        return None, None, "protected header: %s" % exc
    if not isinstance(hdr, dict):
        return None, None, "protected header is not a map"
    return hdr, payload, ""


def verify(pkg_dir: str, receipt: bytes,
           trusted_issuers: Optional[List] = None,
           trusted_size: Optional[int] = None) -> dict:
    """Steps 1-6 of the profile under `/2`, with the inclusion proof read."""
    steps: List[dict] = []
    notes: List[str] = []
    issuer = "NOT_CHECKED"

    def _ret(verdict: str) -> dict:
        return {"verdict": verdict, "steps": steps, "notes": notes, "issuer": issuer}

    root_hex, count, agent_id, hashes, problems = package_facts(pkg_dir)
    if problems:
        steps.append({"step": 1, "name": "recompute root", "outcome": FAIL_PACKAGE,
                      "detail": problems[:6]})
        return _ret(FAIL_PACKAGE)
    steps.append({"step": 1, "name": "recompute root", "outcome": "ok",
                  "detail": "rfc6962 root=%s count=%d agent_id=%s"
                            % (root_hex[:16], count, agent_id)})

    hdr, payload, why = _decode_receipt(receipt)
    if hdr is None:
        steps.append({"step": 2, "name": "rebuild registered value",
                      "outcome": FAIL_MALFORMED, "detail": why})
        return _ret(FAIL_MALFORMED)

    want = registered_value(root_hex, count, agent_id)
    got = payload if payload is not None else want
    if payload is not None and got != want:
        steps.append({"step": 2, "name": "rebuild registered value",
                      "outcome": FAIL_VALUE_MISMATCH,
                      "detail": "receipt payload differs from rebuilt value (%d vs %d bytes)"
                                % (len(got), len(want))})
        return _ret(FAIL_VALUE_MISMATCH)
    steps.append({"step": 2, "name": "rebuild registered value", "outcome": "ok",
                  "detail": "bytes equal (%d B)" % len(want)})

    vds = hdr.get(LBL_VDS)
    if vds not in SUPPORTED_VDS:
        steps.append({"step": 3, "name": "check receipt", "outcome": UNSUPPORTED_SCHEME,
                      "detail": "vds=%r not in %r" % (vds, sorted(SUPPORTED_VDS))})
        notes.append("an unsupported tree is a refusal, not evidence that the package is false")
        return _ret(UNSUPPORTED_SCHEME)
    if LBL_VDP not in hdr:
        steps.append({"step": 3, "name": "check receipt", "outcome": FAIL_MALFORMED,
                      "detail": "no vdp (COSE label 396) in the protected header"})
        return _ret(FAIL_MALFORMED)

    leaf, index, size, path, why = read_vdp(hdr[LBL_VDP])
    if leaf is None:
        steps.append({"step": 3, "name": "inclusion proof", "outcome": FAIL_MALFORMED,
                      "detail": why})
        return _ret(FAIL_MALFORMED)
    if size != count:
        steps.append({"step": 3, "name": "inclusion proof", "outcome": FAIL_INCLUSION,
                      "detail": "vdp tree_size %d != registered count %d" % (size, count)})
        return _ret(FAIL_INCLUSION)
    if not merkle.verify_inclusion(leaf, index, size, path,
                                   bytes.fromhex(root_hex), merkle.PROFILE_RFC6962):
        steps.append({"step": 3, "name": "inclusion proof", "outcome": FAIL_INCLUSION,
                      "detail": "path does not reconstruct the registered root "
                                "(index %d of %d)" % (index, size)})
        return _ret(FAIL_INCLUSION)
    steps.append({"step": 3, "name": "inclusion proof", "outcome": "ok",
                  "detail": "leaf %s at index %d of %d, %d sibling(s)"
                            % (leaf.hex()[:16], index, size, len(path))})

    ok, _pl, reason = cose_min.sign1_verify(receipt, payload=want)
    if not ok:
        outcome = FAIL_VALUE_MISMATCH if payload is None else FAIL_SIGNATURE
        steps.append({"step": 3, "name": "check receipt", "outcome": outcome,
                      "detail": reason})
        return _ret(outcome)
    steps.append({"step": 3, "name": "check receipt", "outcome": "ok",
                  "detail": "signature over %s ok" % SUPPORTED_VDS[vds]})

    issuer_key = hdr.get(4)
    if isinstance(issuer_key, bytes) and trusted_issuers:
        allowed = {k.lower().removeprefix("0x") if isinstance(k, str) else bytes(k).hex()
                   for k in trusted_issuers}
        if issuer_key.hex() not in allowed:
            issuer = "UNTRUSTED"
            steps.append({"step": 3, "name": "issuer trust", "outcome": FAIL_UNTRUSTED_ISSUER,
                          "detail": "receipt key %s... is not among the trusted issuers (%d given)"
                                    % (issuer_key.hex()[:16], len(allowed))})
            notes.append("a self-consistent receipt from an unknown key proves the bytes "
                         "agree with themselves, not that a service registered them")
            return _ret(FAIL_UNTRUSTED_ISSUER)
        issuer = "TRUSTED"
        steps.append({"step": 3, "name": "issuer trust", "outcome": "ok",
                      "detail": "receipt key %s... is a trusted issuer"
                                % issuer_key.hex()[:16]})
    else:
        steps.append({"step": 3, "name": "issuer trust", "outcome": "NOT_CHECKED",
                      "detail": "no trusted issuer list supplied; self-consistency only"})
        notes.append("issuer trust NOT checked: pass trusted_issuers to ask it")

    if trusted_size is not None:
        if trusted_size < count:
            steps.append({"step": 5, "name": "tree size", "outcome": FAIL_VALUE_MISMATCH,
                          "detail": "count %d exceeds trusted size %d" % (count, trusted_size)})
            return _ret(FAIL_VALUE_MISMATCH)
        steps.append({"step": 5, "name": "tree size", "outcome": "ok",
                      "detail": "count %d <= trusted size %d" % (count, trusted_size)})
    else:
        steps.append({"step": 5, "name": "tree size", "outcome": "skipped",
                      "detail": "no trusted size supplied; nothing invented"})

    steps.append({"step": 6, "name": "monotonicity", "outcome": "skipped",
                  "detail": "needs a previous receipt for the same producer"})

    if issuer == "TRUSTED":
        notes.append("OK here means: this file is inside a size-%d tree whose root the "
                     "receipt signs, and the signing key is one you were given. It does "
                     "not mean the evidence is true" % count)
        return _ret(OK)
    notes.append("inclusion verified, but the issuer question was not asked; that is "
                 "PARTIAL, not OK")
    return _ret(PARTIAL_ISSUER_UNCHECKED)


def make_receipt(value: bytes, seed: bytes, vdp: Optional[bytes] = b"\x00",
                 vds: int = 1) -> bytes:
    """Detached receipt shaped like RFC 9942, for producing test bytes deterministically."""
    pub = ed25519.publickey(seed)
    hdr = {1: cose_min.ALG_EDDSA, 4: pub, LBL_VDS: vds}
    if vdp is not None:
        hdr[LBL_VDP] = vdp
    protected = cose_min.encode(hdr)
    body = cose_min._sig_structure(protected, value)
    return cose_min.encode([protected, {}, None, ed25519.sign(seed, body)])
