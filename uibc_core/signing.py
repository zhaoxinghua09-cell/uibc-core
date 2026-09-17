"""Seal signatures (archive SS10/SS19) - v0.2 PROVISIONAL.

v0.2 decision (B5, PROPOSAL status): HMAC-SHA256 over the canonical
serialization of {"identity": ..., "manifest": ...}. Pure stdlib, zero
dependencies.

Honest scope (archive SS17 discipline - read before relying on this):

1. HMAC is SYMMETRIC. Only the key holder can sign AND verify. This closes
   the v0.1 'malicious' blind spot (an attacker cannot recompute the seal
   without the key) but does NOT yet provide third-party verification.
2. Key substitution is detectable ONLY with out-of-band key pinning: an
   attacker may re-sign a whole package with their own key. Verifying with
   the OWNER key (``uibc verify --key owner.key``) compares the recorded
   key_id against SHA-256(owner key) - substitution then fails S6. Without
   the owner key, substitution is UNDETECTED. Recorded as a known boundary.
3. Ed25519 (asymmetric, third-party verifiable) is the v0.3 target, pending
   the ``cryptography`` dependency decision (archive SS10 B5).
4. Lifecycle event signatures (event.signature) remain unratified and are
   NOT covered by the seal.
"""

import base64
import hashlib
import hmac
import json
import os

ALGORITHM = "HMAC-SHA256"


def generate_key() -> bytes:
    """Generate a fresh 256-bit seal key (owner secret, NEVER store in package)."""
    return os.urandom(32)


def key_id(key: bytes) -> str:
    """Public identifier of a key: SHA-256 hex. Safe to record in the package;
    does not reveal the key."""
    return hashlib.sha256(key).hexdigest()


def seal_payload(identity: dict, manifest: dict) -> bytes:
    """Canonical bytes covering identity (who) + manifest (the seal).

    Uses the same provisional canonical JSON as evidence hashing, so the
    RFC 8785 caveat from canonical.py applies here too.
    """
    return json.dumps(
        {"identity": identity, "manifest": manifest},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def seal_sign(key: bytes, identity: dict, manifest: dict) -> str:
    """Return base64 HMAC-SHA256 signature over the seal payload."""
    mac = hmac.new(key, seal_payload(identity, manifest), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode("ascii")


def seal_verify(key: bytes, identity: dict, manifest: dict, sig_b64: str) -> bool:
    """Constant-time verify. Returns False on any malformed input."""
    if not isinstance(sig_b64, str):
        return False
    try:
        sig = base64.b64decode(sig_b64.encode("ascii"), validate=True)
    except Exception:
        return False
    mac = hmac.new(key, seal_payload(identity, manifest), hashlib.sha256).digest()
    return hmac.compare_digest(mac, sig)
