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
   NOT covered by the seal. The lifecycle LOG as a whole IS covered as of
   v1.1 when the sealer passes it in (``signed`` reads
   "identity+manifest+lifecycle"); seals created before v1.1 cover
   identity+manifest only and are reported as "legacy" by the verifier.
"""

import base64
import hashlib
import hmac
import os

from . import ed25519 as _ed
from .canonical import canonicalize

ALGORITHM = "HMAC-SHA256"
ALGORITHM_ED25519 = "Ed25519"


def generate_key() -> bytes:
    """Generate a fresh 256-bit seal key (owner secret, NEVER store in package)."""
    return os.urandom(32)


def key_id(key: bytes) -> str:
    """Public identifier of a key: SHA-256 hex. Safe to record in the package;
    does not reveal the key."""
    return hashlib.sha256(key).hexdigest()


def seal_payload(identity: dict, manifest: dict, lifecycle: dict = None) -> bytes:
    """RFC 8785 (JCS) canonical bytes covering identity (who) + manifest,
    and - when ``lifecycle`` is given - the lifecycle event log too.

    Using JCS means any third party with a standard JCS tool - e.g. a W3C VC
    eddsa-jcs-2022 verifier - can re-derive these exact bytes and verify the
    Ed25519 seal with zero UIBC-specific code.

    v1.1 (mutation-benchmark fix F1): the lifecycle log is folded into the
    signed payload. Without it, an attacker can rewrite event timestamps,
    actors, or append events and every check still passes - measured as 4 of
    the 18 single-point mutations being accepted (see tools/mutation_benchmark.py).
    ``lifecycle=None`` reproduces the legacy v0.3 payload exactly, so packages
    sealed before this change keep verifying.
    """
    doc = {"identity": identity, "manifest": manifest}
    if lifecycle is not None:
        doc["lifecycle"] = lifecycle
    return canonicalize(doc)


def seal_sign(key: bytes, identity: dict, manifest: dict,
              lifecycle: dict = None) -> str:
    """Return base64 HMAC-SHA256 signature over the seal payload."""
    mac = hmac.new(key, seal_payload(identity, manifest, lifecycle), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode("ascii")


def seal_verify(key: bytes, identity: dict, manifest: dict, sig_b64: str,
                lifecycle: dict = None) -> bool:
    """Constant-time verify. Returns False on any malformed input."""
    if not isinstance(sig_b64, str):
        return False
    try:
        sig = base64.b64decode(sig_b64.encode("ascii"), validate=True)
    except Exception:
        return False
    mac = hmac.new(key, seal_payload(identity, manifest, lifecycle),
                   hashlib.sha256).digest()
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


def ed_seal_sign(seed: bytes, identity: dict, manifest: dict,
                 lifecycle: dict = None):
    """Return (signature_b64, public_key_b64) over the seal payload."""
    pub = _ed.publickey(seed)
    sig = _ed.sign(seed, seal_payload(identity, manifest, lifecycle))
    return base64.b64encode(sig).decode("ascii"), \
        base64.b64encode(pub).decode("ascii")


def ed_seal_verify(public_key: bytes, identity: dict, manifest: dict,
                   sig_b64: str, lifecycle: dict = None) -> bool:
    """Verify an Ed25519 seal signature. Returns False on malformed input."""
    if not isinstance(sig_b64, str) or not isinstance(public_key, (bytes, bytearray)):
        return False
    try:
        sig = base64.b64decode(sig_b64.encode("ascii"), validate=True)
    except Exception:
        return False
    return _ed.verify(bytes(public_key), seal_payload(identity, manifest, lifecycle), sig)


def ed_seal_verify_scoped(public_key: bytes, identity: dict, manifest: dict,
                          lifecycle: dict, sig_b64: str):
    """Verify an Ed25519 seal and report WHAT it covers.

    Returns one of:
      "lifecycle-bound" - signature covers identity+manifest+lifecycle (v1.1)
      "legacy"          - signature covers identity+manifest only (v0.3)
      None              - signature is invalid for both payload shapes

    The distinction matters: a legacy seal cannot detect lifecycle tampering,
    so the verifier must rely on semantic checks alone for those packages and
    must say so in the report.
    """
    if lifecycle is not None and ed_seal_verify(public_key, identity, manifest,
                                                sig_b64, lifecycle):
        return "lifecycle-bound"
    if ed_seal_verify(public_key, identity, manifest, sig_b64):
        return "legacy"
    return None


def b64decode_strict(text):
    """base64-decode a recorded field; return None on any malformation."""
    if not isinstance(text, str):
        return None
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception:
        return None


def context_sign(seed: bytes, seal_signature: str, context: dict) -> str:
    """v0.7: sign {"seal_signature", "context"} - binds a use-case context to the
    exact seal it accompanies. Tampering purpose/nonce/verifier breaks it."""
    return base64.b64encode(
        _ed.sign(seed, canonicalize({"seal_signature": seal_signature,
                                     "context": context}))).decode("ascii")


def context_verify(public_key: bytes, seal_signature: str, context: dict,
                   sig_b64: str) -> bool:
    if not isinstance(sig_b64, str):
        return False
    try:
        sig = base64.b64decode(sig_b64.encode("ascii"), validate=True)
        payload = canonicalize({"seal_signature": seal_signature, "context": context})
    except Exception:
        return False
    try:
        return _ed.verify(bytes(public_key), payload, sig)
    except Exception:
        return False

