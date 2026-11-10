"""Seal signatures (archive SS10/SS19) - v0.3.

v0.2 decision (B5, PROPOSAL status): HMAC-SHA256 over the canonical
serialization of {"identity": ..., "manifest": ...}. Pure stdlib, zero
dependencies.

v0.3 adds the asymmetric seal the v0.2 notes promised: Ed25519
(RFC 8032, implemented in pure Python in uibc_core/ed25519.py, still zero
dependencies). An Ed25519 seal records the signer's PUBLIC key in the
package, so ANY third party can verify provenance without any secret -
verification stops being a permissioned act.

Honest scope (archive SS17 discipline - read before relying on this):

1. HMAC is SYMMETRIC. Only the key holder can sign AND verify. This closes
   the v0.1 'malicious' blind spot (an attacker cannot recompute the seal
   without the key) but does NOT provide third-party verification.
2. Key substitution is detectable ONLY with out-of-band key pinning: an
   attacker may re-sign a whole package with their own key. For HMAC,
   verifying with the OWNER key (``uibc verify --key owner.key``) compares
   the recorded key_id against SHA-256(owner key) - substitution then
   fails S6. For Ed25519, pin the expected public key
   (``uibc verify --pubkey owner.pub``) - a substituted key then fails S6
   the same way. Without pinning, substitution is UNDETECTED for both.
   Recorded as a known boundary.
3. The pure-Python Ed25519 is not constant-time. It signs/verifies short
   seal payloads only; deployments that need side-channel resistance at
   volume should swap in a native implementation behind this interface.
4. Lifecycle event signatures (event.signature) remain unratified and are
   NOT covered by the seal.
"""

import base64
import hashlib
import hmac
import json
import os

from . import ed25519 as _ed

ALGORITHM = "HMAC-SHA256"
ALGORITHM_ED25519 = "Ed25519"


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


# ---------------------------------------------------------------------------
# Ed25519 seal (v0.3): asymmetric, third-party verifiable, zero dependencies.
# The key file holds the 32-byte SEED (secret). The public key is derived
# from the seed and recorded in the seal itself, so verifiers need nothing
# from the owner. key_id for an Ed25519 seal is SHA-256 of the PUBLIC key.
# ---------------------------------------------------------------------------

def ed_generate_seed() -> bytes:
    """Generate a fresh 32-byte Ed25519 seed (owner secret)."""
    return os.urandom(32)


def ed_public_key(seed: bytes) -> bytes:
    """Derive the 32-byte public key from a seed."""
    return _ed.publickey(seed)


def ed_key_id(public_key: bytes) -> str:
    """Public identifier of an Ed25519 key: SHA-256 hex of the public key."""
    return hashlib.sha256(public_key).hexdigest()


def ed_seal_sign(seed: bytes, identity: dict, manifest: dict):
    """Return (signature_b64, public_key_b64) over the seal payload."""
    pub = _ed.publickey(seed)
    sig = _ed.sign(seed, seal_payload(identity, manifest))
    return base64.b64encode(sig).decode("ascii"), \
        base64.b64encode(pub).decode("ascii")


def ed_seal_verify(public_key: bytes, identity: dict, manifest: dict,
                   sig_b64: str) -> bool:
    """Verify an Ed25519 seal signature. Returns False on malformed input."""
    if not isinstance(sig_b64, str) or not isinstance(public_key, (bytes, bytearray)):
        return False
    try:
        sig = base64.b64decode(sig_b64.encode("ascii"), validate=True)
    except Exception:
        return False
    return _ed.verify(bytes(public_key), seal_payload(identity, manifest), sig)


def b64decode_strict(text):
    """base64-decode a recorded field; return None on any malformation."""
    if not isinstance(text, str):
        return None
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception:
        return None
