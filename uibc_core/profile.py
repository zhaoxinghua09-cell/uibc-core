"""The profile, executable.

`drafts/draft-zhao-uibc-scitt-profile-00.md` fixes four registered members and six
verification steps. Prose that no one can run is the failure mode this repository
keeps finding, so the steps live here in code, and this module is what the profile's
Appendix B tells a reader to run.

Two limits are stated in the return value rather than smoothed over:

* the inclusion proof (`vdp`) is **not evaluated**: this module has no hash-tree
  implementation, so a receipt that passes here is marked `PARTIAL_INCLUSION_UNCHECKED`
  and never `OK`. A verdict of `OK` is reserved for the day the proof is checked.
* the `vds` values that mean what are still `TBD` in the IANA registry, so the accepted
  set is passed in by the caller. An unknown `vds` is an unsupported scheme, which is
  a refusal, not a finding that the evidence is false.

Nothing here talks to a transparency service. It consumes bytes a service produced.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

from . import canonical, cose_min, ed25519

PROFILE_ID = "uibc-scitt/1"

#: COSE header labels from RFC 9942.
LBL_VDS = 395
LBL_VDP = 396

#: Verdict codes. `OK` is unreachable until an inclusion-proof check exists.
OK = "OK"
PARTIAL_INCLUSION_UNCHECKED = "PARTIAL_INCLUSION_UNCHECKED"
FAIL_VALUE_MISMATCH = "FAIL_VALUE_MISMATCH"
FAIL_SIGNATURE = "FAIL_SIGNATURE"
FAIL_PACKAGE = "FAIL_PACKAGE"
FAIL_MALFORMED = "FAIL_MALFORMED"
UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"


def registered_value(root_hex: str, count: int, agent_id: str,
                     profile: str = PROFILE_ID) -> bytes:
    """The exact bytes a service is asked to register (Section 4.2).

    Four members, RFC 8785 serialization, nothing else: no timestamp, no version of
    the package format, no signature. Anything more would make the registered value
    depend on data the receipt does not cover.
    """
    if not isinstance(count, int) or isinstance(count, bool):
        raise TypeValue("count must be an int")
    if not isinstance(root_hex, str) or len(root_hex) != 64:
        raise TypeValue("root must be 64 lowercase hex characters")
    obj = {"profile": profile, "root": root_hex, "count": count, "agent_id": agent_id}
    return canonical.canonicalize(obj)


class TypeValue(ValueError):
    """Raised when a registered-value input is the wrong type or shape."""


def package_facts(pkg_dir: str) -> Tuple[str, int, str, List[str]]:
    """(root_hex, count, agent_id, problems) recomputed from the package.

    The root is recomputed from the evidence bytes, never read out of
    `manifest.json`: that field is what is being checked, so trusting it would make
    step 1 a no-op. A missing declared file or an undeclared file under `evidence/`
    is a package problem, reported rather than raised.
    """
    problems: List[str] = []
    idx_path = os.path.join(pkg_dir, "evidence", "index.json")
    man_path = os.path.join(pkg_dir, "manifest.json")
    try:
        idx = json.load(open(idx_path, encoding="utf-8"))
        entries = idx["entries"]
    except Exception as exc:
        return "", 0, "", ["index unreadable: %s" % exc]
    try:
        agent_id = json.load(open(man_path, encoding="utf-8"))["agent_id"]
    except Exception as exc:
        return "", 0, "", ["manifest unreadable: %s" % exc]

    hashes: List[str] = []
    declared = set()
    for e in entries:
        rel = e.get("path")
        ch = e.get("content_hash")
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
        return "", 0, agent_id, problems
    return canonical.evidence_root(hashes), len(hashes), agent_id, []


def _decode_receipt(receipt: bytes) -> Tuple[Optional[dict], Optional[bytes], str]:
    """(protected header, payload field, reason) from a COSE_Sign1."""
    try:
        msg = cose_min.decode(receipt)
    except cose_min.CborError as exc:
        return None, None, "cbor: %s" % exc
    if not isinstance(msg, list) or len(msg) != 4:
        return None, None, "not a COSE_Sign1 4-element array"
    protected, _unprot, payload, _sig = msg
    if not isinstance(protected, bytes):
        return None, None, "protected header must be a bstr"
    try:
        hdr = cose_min.decode(protected)
    except cose_min.CborError as exc:
        return None, None, "protected header: %s" % exc
    if not isinstance(hdr, dict):
        return None, None, "protected header is not a map"
    return hdr, payload, ""


def verify(pkg_dir: str, receipt: bytes, supported_vds: Optional[Dict[int, str]] = None,
           trusted_size: Optional[int] = None) -> dict:
    """Run the profile's steps 1-5 against a package and one receipt.

    Returns a dict with `verdict`, `steps` (each with a name and outcome), and
    `notes`. Steps 5 and 6 of the document need inputs a stranger will not have
    (a previous trusted size, a second receipt); they are reported as skipped unless
    those are supplied, so a caller cannot read their absence as success.
    """
    supported_vds = {1: "rfc9162-sha256"} if supported_vds is None else supported_vds
    steps: List[dict] = []
    notes: List[str] = []

    root_hex, count, agent_id, problems = package_facts(pkg_dir)
    if problems:
        steps.append({"step": 1, "name": "recompute root", "outcome": FAIL_PACKAGE,
                      "detail": problems[:6]})
        return {"verdict": FAIL_PACKAGE, "steps": steps, "notes": notes}

    steps.append({"step": 1, "name": "recompute root", "outcome": "ok",
                  "detail": "root=%s count=%d agent_id=%s" % (root_hex[:16], count, agent_id)})

    hdr, payload, why = _decode_receipt(receipt)
    if hdr is None:
        steps.append({"step": 2, "name": "rebuild registered value", "outcome": FAIL_MALFORMED,
                      "detail": why})
        return {"verdict": FAIL_MALFORMED, "steps": steps, "notes": notes}

    want = registered_value(root_hex, count, agent_id)
    # Detached receipt: the payload field is nil and the value is supplied by the
    # holder. An attached receipt carries it; both are compared as bytes.
    got = payload if payload is not None else want
    if payload is not None and got != want:
        steps.append({"step": 2, "name": "rebuild registered value", "outcome": FAIL_VALUE_MISMATCH,
                      "detail": "receipt payload differs from rebuilt value "
                                "(receipt %s, rebuilt %s)" % (len(got), len(want))})
        return {"verdict": FAIL_VALUE_MISMATCH, "steps": steps, "notes": notes}
    steps.append({"step": 2, "name": "rebuild registered value", "outcome": "ok",
                  "detail": "bytes equal (%d B)" % len(want)})

    vds = hdr.get(LBL_VDS)
    if vds not in supported_vds:
        steps.append({"step": 3, "name": "check receipt", "outcome": UNSUPPORTED_SCHEME,
                      "detail": "vds=%r not in supported set %r" % (vds, sorted(supported_vds))})
        notes.append("an unsupported tree is a refusal, not evidence that the package is false")
        return {"verdict": UNSUPPORTED_SCHEME, "steps": steps, "notes": notes}
    if LBL_VDP not in hdr:
        steps.append({"step": 3, "name": "check receipt", "outcome": FAIL_MALFORMED,
                      "detail": "no vdp (inclusion proof) in the protected header"})
        return {"verdict": FAIL_MALFORMED, "steps": steps, "notes": notes}

    ok, _pl, reason = cose_min.sign1_verify(receipt, payload=want)
    if not ok:
        # A detached receipt does not carry the value: the payload field is nil and
        # the holder supplies it. So a signature that fails over the rebuilt value
        # means either the receipt covers different bytes or it was signed by a key
        # this verifier does not hold. Those are indistinguishable without an issuer
        # key registry, and reporting the first as the second would make an unknown
        # issuer look like a corrupted package.
        outcome = FAIL_VALUE_MISMATCH if payload is None else FAIL_SIGNATURE
        detail = reason
        if payload is None:
            detail = ("detached receipt does not verify over the rebuilt value "
                      "(covers different bytes, or signed by a key not held here): " + reason)
        steps.append({"step": 3, "name": "check receipt", "outcome": outcome, "detail": detail})
        return {"verdict": outcome, "steps": steps, "notes": notes}
    steps.append({"step": 3, "name": "check receipt", "outcome": PARTIAL_INCLUSION_UNCHECKED,
                  "detail": "signature over %s ok; inclusion proof not evaluated (no tree implementation)"
                            % supported_vds[vds]})

    if trusted_size is not None:
        if trusted_size < count:
            steps.append({"step": 5, "name": "tree size", "outcome": FAIL_VALUE_MISMATCH,
                          "detail": "count %d exceeds trusted size %d" % (count, trusted_size)})
            return {"verdict": FAIL_VALUE_MISMATCH, "steps": steps, "notes": notes}
        steps.append({"step": 5, "name": "tree size", "outcome": "ok",
                      "detail": "count %d <= trusted size %d" % (count, trusted_size)})
    else:
        steps.append({"step": 5, "name": "tree size", "outcome": "skipped",
                      "detail": "no trusted size supplied; nothing invented"})

    steps.append({"step": 6, "name": "monotonicity", "outcome": "skipped",
                  "detail": "needs a previous receipt for the same producer"})

    notes.append("a pass here means the package reproduces the registered value and the "
                 "receipt's signature covers it; it does not mean the evidence is true")
    return {"verdict": PARTIAL_INCLUSION_UNCHECKED, "steps": steps, "notes": notes}


def make_receipt(root_or_value: bytes, seed: bytes, vds: int = 1,
                 vdp: Optional[bytes] = b"\x00") -> bytes:
    """Build a test receipt shaped like RFC 9942: detached payload, vds, vdp.

    This exists so the profile's negative cases can be produced deterministically.
    It is not a transparency service: `vdp` here is a placeholder, which is why
    `verify` refuses to report `OK`. `vdp=None` omits the proof label entirely,
    which is how the "receipt with no proof" case is produced.
    """
    pub = ed25519.publickey(seed)
    hdr = {1: cose_min.ALG_EDDSA, 4: pub, LBL_VDS: vds}
    if vdp is not None:
        hdr[LBL_VDP] = vdp
    protected = cose_min.encode(hdr)
    body = cose_min._sig_structure(protected, root_or_value)
    sig = ed25519.sign(seed, body)
    return cose_min.encode([protected, {}, None, sig])
