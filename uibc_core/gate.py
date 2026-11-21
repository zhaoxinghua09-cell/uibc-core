"""Gate (archive: LGD third principle - Gates). verify CHECKS, gate DECIDES.

Decision rules (docs/governance.md section 7, v0.1 PROPOSAL):

  revocation valid            -> DENY            (exit 2)   [R2]
  verify FAIL                 -> DENY            (exit 2)
  anything unverifiable       -> HOLD            (exit 3)
  verify PASS + valid dispute -> ALLOW_DISPUTED  (exit 0, flagged)
  verify PASS clean           -> ALLOW           (exit 0)

Boundary (Dispute vs Revocation, governance section 3):
  Dispute    = third party says "I object"  -> flag, never blocks
  Revocation = owner says "this is void"    -> must verify, then blocks

Honest scope:
  - With HMAC (v0.2) only the owner key holder can verify a revocation.
    Without the key a revocation is INCONCLUSIVE -> HOLD, never silently
    ignored and never trusted.
  - gate() never mutates the package. Read-only, like verify().
"""

import base64
import hashlib
import hmac
import json
import os

from . import ed25519 as _ed
from .canonical import hash_file  # noqa: F401  (re-exported for tools)
from .signing import (ALGORITHM, ALGORITHM_ED25519, ed_key_id, key_id)  # noqa: F401
from .verify import verify


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _canonical_sig_payload(body: dict) -> bytes:
    core = {k: v for k, v in body.items() if k != "signature"}
    return json.dumps(core, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def revocation_body_sha256(body: dict) -> str:
    """sha256 over the canonical revocation body (everything except `signature`).

    One implementation, called by the signer, the gate and the receipt
    recomputation. Two copies of this canonicalization is exactly how a valid
    signature stops verifying (measured, #319): the signer signed four fields
    while the verifier canonicalized six.
    """
    return hashlib.sha256(_canonical_sig_payload(body)).hexdigest()


def _check_revocation(rev: dict, manifest: dict, key, pubkey=None) -> tuple:
    """Return (status, detail). status in {"REVOKED", "MISMATCH", "UNVERIFIABLE", "MALFORMED"}.

    Two signature algorithms are accepted, and which one is used has to be
    stated in the file rather than guessed:

      * ``HMAC-SHA256`` (v0.2) - symmetric, needs ``--key``. Only the owner can
        verify, so a third party cannot check a revocation at all.
      * ``Ed25519`` (v0.3) - asymmetric, needs the signer's ``--pubkey``. This
        is the one that lets somebody who never held the owner's secret check
        that the owner really revoked the package.

    Anything else - unknown algorithm, missing key material, signature that
    does not verify - is UNVERIFIABLE, which HOLDs. It is never treated as
    "no revocation present".
    """
    for field in ("revocation_id", "target_root", "signature", "revoked_at"):
        if not rev.get(field):
            return "MALFORMED", f"revocation missing field {field!r}"
    if rev.get("target_root") != manifest.get("evidence_root"):
        return "MISMATCH", ("revocation targets a different evidence_root: "
                            f"{rev.get('target_root')!r} != {manifest.get('evidence_root')!r}")
    algorithm = rev.get("algorithm", ALGORITHM)
    if algorithm == ALGORITHM:
        if key is None:
            return "UNVERIFIABLE", ("revocation present but no --key provided: "
                                    "cannot verify (HOLD, never silently trusted)")
        if not _verify_body(key, rev):
            return "UNVERIFIABLE", "revocation signature invalid for supplied key"
        return "REVOKED", f"valid revocation by key_id {rev.get('key_id', '?')}"
    if algorithm == ALGORITHM_ED25519:
        if pubkey is None:
            return "UNVERIFIABLE", ("Ed25519-signed revocation present but no --pubkey "
                                    "provided: cannot verify (HOLD, never silently trusted)")
        if rev.get("key_id") and rev["key_id"] != ed_key_id(pubkey):
            return "UNVERIFIABLE", ("revocation key_id does not match the pinned public "
                                    f"key ({rev.get('key_id', '?')})")
        try:
            sig = base64.b64decode(rev.get("signature", ""), validate=True)
        except Exception:
            return "UNVERIFIABLE", "revocation signature is not valid base64"
        if not _ed.verify(pubkey, _canonical_sig_payload(rev), sig):
            return "UNVERIFIABLE", "revocation signature invalid for the pinned public key"
        return "REVOKED", ("valid Ed25519 revocation by key_id "
                           f"{rev.get('key_id', ed_key_id(pubkey))}")
    return "UNVERIFIABLE", f"unknown revocation algorithm {algorithm!r}"



def _verify_body(key, rev: dict) -> bool:
    """HMAC over the canonical revocation body (without 'signature')."""
    try:
        sig = rev.get("signature", "")
        mac = hmac.new(key, _canonical_sig_payload(rev),
                       __import__("hashlib").sha256).digest()
        import base64
        return hmac.compare_digest(mac, base64.b64decode(sig))
    except Exception:
        return False


def _check_dispute(disp: dict, manifest: dict) -> tuple:
    """Return (status, detail). status in {"DISPUTED", "MISMATCH", "MALFORMED"}."""
    for field in ("dispute_id", "target_root", "reason_code", "disputer"):
        if not disp.get(field):
            return "MALFORMED", f"dispute missing field {field!r}"
    if disp.get("target_root") != manifest.get("evidence_root"):
        return "MISMATCH", ("dispute targets a different evidence_root: "
                            f"{disp.get('target_root')!r}")
    return "DISPUTED", f"dispute {disp.get('dispute_id')} ({disp.get('reason_code')})"


def gate(package_dir: str, key: bytes = None,
         revocation_path: str = None, dispute_path: str = None,
         pubkey: bytes = None, require_revocation_coverage: bool = False) -> dict:
    """Run verify, then apply governance overlays. Returns a gate report.

    Exit-code contract (CLI layer):
        ALLOW           -> 0
        DENY            -> 2   (blocking: mirrors poka-yoke hook semantics)
        HOLD            -> 3   (INCONCLUSIVE: human decision required)

    ``require_revocation_coverage`` is the fail-closed form of "I have no
    revocation overlay": without it, a caller with no overlay gets ALLOW,
    because the gate cannot see a revocation it was never given. With it, an
    absent overlay is HOLD (exit 3) instead of ALLOW - absence is never read as
    "nothing was revoked". It does not make the absence *verified*; it only
    stops the absence from being silently treated as a clean state.
    """
    report = verify(package_dir, key=key, pubkey=pubkey)
    manifest = _load_json(os.path.join(package_dir, "manifest.json")) \
        if os.path.isfile(os.path.join(package_dir, "manifest.json")) else {}

    revocation = {"status": "NONE", "detail": "no revocation supplied"}
    if revocation_path:
        try:
            revocation = dict(zip(("status", "detail"),
                                  _check_revocation(_load_json(revocation_path), manifest,
                                                    key, pubkey)))
        except (OSError, ValueError):
            revocation = {"status": "MALFORMED", "detail": "revocation file unreadable/invalid JSON"}

    dispute = {"status": "NONE", "detail": "no dispute supplied"}
    if dispute_path:
        try:
            dispute = dict(zip(("status", "detail"),
                               _check_dispute(_load_json(dispute_path), manifest)))
        except (OSError, ValueError):
            dispute = {"status": "MALFORMED", "detail": "dispute file unreadable/invalid JSON"}

    # decision cascade - order is normative (governance section 7)
    if revocation["status"] == "REVOKED":
        decision, reason = "DENY", "package is revoked by valid owner revocation"
    elif report["result"] == "FAIL":
        decision, reason = "DENY", "verifier FAIL: " + \
            "; ".join(c["id"] for c in report["checks"] if c["result"] == "FAIL")
    elif revocation["status"] in ("MALFORMED", "MISMATCH", "UNVERIFIABLE"):
        decision, reason = "HOLD", f"revocation {revocation['status']}: {revocation['detail']}"
    elif revocation["status"] == "NONE" and require_revocation_coverage:
        decision = "HOLD"
        reason = ("revocation coverage absent: caller demanded coverage and no "
                  "revocation overlay was supplied (HOLD, never read as "
                  "'nothing was revoked')")
    elif dispute["status"] in ("MALFORMED", "MISMATCH"):
        decision, reason = "HOLD", f"dispute {dispute['status']}: {dispute['detail']}"
    elif report["result"] == "INCONCLUSIVE" or \
            any(c["result"] == "INCONCLUSIVE" for c in report["checks"]) or \
            dispute["status"] == "DISPUTED":
        # disputed packages are not auto-denied, but a human must look
        decision = "HOLD" if report["result"] != "PASS" else "ALLOW_DISPUTED"
        reason = ("dispute registered: " + dispute["detail"]) if dispute["status"] == "DISPUTED" \
            else "verifier INCONCLUSIVE components present"
    else:
        decision, reason = "ALLOW", "verify PASS, no revocation, no dispute"

    return {
        "gate_version": "0.1.0",
        "decision": decision,
        "reason": reason,
        "verify_result": report["result"],
        "revocation": revocation,
        "dispute": dispute,
        "exit_code": {"ALLOW": 0, "ALLOW_DISPUTED": 0, "DENY": 2, "HOLD": 3}[decision],
        "verify_report": report,
        "scope": "Same evidence boundary as verify(), plus revocation/dispute "
                 "overlays explicitly supplied on the command line. gate() does "
                 "not discover governance files on its own - an operator must "
                 "name them, so the decision input is always explicit.",
        "limitations": report["limitations"] + [
            "gate() is a decision layer, not an enforcement layer: it returns "
            "exit codes, it cannot stop a determined caller from ignoring them.",
        ],
    }
