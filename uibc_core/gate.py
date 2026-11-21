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

# Reason codes a revocation may carry (governance section 3). A closed set:
# a new reason has to enter the spec before a file can claim it, otherwise
# "reason_code" becomes free text that nobody can act on.
#
# SUPERSEDED and KEY_COMPROMISED are the two that were missing. Neither adds a
# gate disposition: a superseded package is void (DENY) and the successor is
# named so a caller can follow it; a compromised key voids what it signed.
REVOCATION_REASONS = ("OWNER_REQUEST", "EVIDENCE_INVALID",
                      "KEY_COMPROMISED", "SUPERSEDED")


def _timestamp_ok(value) -> bool:
    """ISO-8601 with a timezone. Naive timestamps are rejected: a revocation
    time without an offset cannot be compared with another revocation time."""
    if not isinstance(value, str) or not value:
        return False
    try:
        from datetime import datetime
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _check_revocation_reason(rev: dict):
    """Validate the reason vocabulary. Returns (status, detail) or None.

    Why this is a separate step with its own return: a reason code is what a
    human acts on after the gate says DENY. A file that says SUPERSEDED
    without naming the successor is a revocation that tells the caller to stop
    using this package and then leaves them with nowhere to go.
    """
    rc = rev.get("reason_code")
    if rc is None:
        return None  # legacy revocations predate the vocabulary; not an error
    if not isinstance(rc, str) or rc not in REVOCATION_REASONS:
        return "MALFORMED", (
            "unknown reason_code %r; known: %s" % (rc, ", ".join(REVOCATION_REASONS)))
    if rc == "SUPERSEDED":
        successor = rev.get("superseded_by")
        if not successor:
            return "MALFORMED", "reason_code SUPERSEDED requires superseded_by"
        if successor == rev.get("target_root"):
            return "MALFORMED", "a package cannot supersede itself"
    if "compromised_at" in rev and not _timestamp_ok(rev.get("compromised_at")):
        return "MALFORMED", "compromised_at is not ISO-8601 with a timezone"
    return None



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
    bad_reason = _check_revocation_reason(rev)
    if bad_reason:
        return bad_reason
    reason = rev.get("reason_code") or "UNSPECIFIED"
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
        return "REVOKED", (f"valid revocation by key_id {rev.get('key_id', '?')} "
                           f"(reason_code {reason})")
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
                           f"{rev.get('key_id', ed_key_id(pubkey))} (reason_code {reason})")
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
         pubkey: bytes = None) -> dict:
    """Run verify, then apply governance overlays. Returns a gate report.

    Exit-code contract (CLI layer):
        ALLOW           -> 0
        DENY            -> 2   (blocking: mirrors poka-yoke hook semantics)
        HOLD            -> 3   (INCONCLUSIVE: human decision required)
    """
    report = verify(package_dir, key=key, pubkey=pubkey)
    manifest = _load_json(os.path.join(package_dir, "manifest.json")) \
        if os.path.isfile(os.path.join(package_dir, "manifest.json")) else {}

    revocation = {"status": "NONE", "detail": "no revocation supplied"}
    if revocation_path:
        try:
            rev = _load_json(revocation_path)
            status, detail = _check_revocation(rev, manifest, key, pubkey)
            revocation = {"status": status, "detail": detail}
            for field in ("reason_code", "superseded_by", "compromised_at"):
                if rev.get(field) not in (None, ""):
                    revocation[field] = rev[field]
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
        if revocation.get("reason_code"):
            reason += " (reason_code %s)" % revocation["reason_code"]
        if revocation.get("superseded_by"):
            reason += ", successor %s" % revocation["superseded_by"]
    elif report["result"] == "FAIL":
        decision, reason = "DENY", "verifier FAIL: " + \
            "; ".join(c["id"] for c in report["checks"] if c["result"] == "FAIL")
    elif revocation["status"] in ("MALFORMED", "MISMATCH", "UNVERIFIABLE"):
        decision, reason = "HOLD", f"revocation {revocation['status']}: {revocation['detail']}"
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
            # A key-compromise revocation without a time bound still denies the
            # package, but it says nothing about what the key signed before -
            # so it cannot be used to bound the damage, only to stop this one.
        ] + ([] if revocation.get("reason_code") != "KEY_COMPROMISED"
              or revocation.get("compromised_at") else [
            "key compromise is declared without compromised_at: the time bound "
            "is unstated, so only this package is void, not what the key signed earlier."]),
    }
