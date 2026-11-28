"""Emit and verify a receipt in the draft's wire shape (additive, no migration).

Why this module exists rather than a package-format change: the two remaining
gaps in `docs/CROSSWALK-ASQAV-COMPLIANCE.md` (rows 1 and 3) are wire-format
gaps - `signatureObject`, `action_ref`, `previousReceiptHash`, an `anchors`
array. Closing them by changing the package format would move every existing
digest in the repository, i.e. break every package already handed to anyone.
So this is an *adapter*: the package stays as it is, and a receipt in the draft's
shape is derived from it, signed, and verified on its own terms.

What is real here and what is not, stated up front:

* the signature is Ed25519 over DSSE pre-authentication encoding (PAE) of the
  JCS payload, which is what ACTA-RECEIPTS builds on - so this is the draft's
  shape, not a private one;
* the key id is derived from the public key, and verification can be pinned to a
  known public key, so `verify_receipt` never has to trust the key inside the
  envelope (draft section 8, mandatory check 2);
* an RFC 3161 anchor is carried only if the caller supplies a real token; this
  module does not fabricate one and does not mark an anchor "valid" on
  presence;
* this module does not make a uibc package "a Compliance Receipt". It produces
  a receipt whose fields are the draft's, and says so.
"""

import base64

from .canonical import canonicalize, hash_obj
from .ed25519 import publickey, sign, verify

RECEIPT_PAYLOAD_TYPE = "application/vnd.uibc.action-receipt+json"

# Fields the draft marks REQUIRED for a Compliance Receipt (section 4).
REQUIRED_FIELDS = ("type", "issued_at", "issuer_id", "action_ref",
                   "policy_digest", "payload_digest", "previousReceiptHash")

GENESIS = "0" * 64


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE pre-authentication encoding: `DSSEv1 SP len SP type SP len SP body`."""
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + \
        str(len(payload)).encode() + b" " + payload


def canonical_action(action: dict) -> str:
    """`sha256:<hex>` over the JCS encoding - the draft's action_ref."""
    return "sha256:" + hash_obj(action)


def build_receipt(action: dict, *, issued_at: str, issuer_id: str,
                  policy_digest: str, payload_digest: str,
                  previous_receipt_hash: str = GENESIS,
                  risk_class: str = None) -> dict:
    """Assemble an unsigned receipt body in the draft's shape."""
    receipt = {
        "type": "protectmcp:decision",
        "issued_at": issued_at,
        "issuer_id": issuer_id,
        "action_ref": canonical_action(action),
        "policy_digest": policy_digest,
        "payload_digest": payload_digest,
        "previousReceiptHash": previous_receipt_hash,
    }
    if risk_class:
        receipt["risk_class"] = risk_class
    return receipt


def sign_receipt(receipt: dict, seed: bytes) -> dict:
    """Return a copy of `receipt` carrying `signatureObject` (Ed25519 over PAE)."""
    payload = canonicalize(receipt)
    sig = sign(seed, pae(RECEIPT_PAYLOAD_TYPE, payload))
    signed = dict(receipt)
    signed["signatureObject"] = {
        "alg": "Ed25519",
        "kid": "ed25519:" + publickey(seed).hex()[:16],
        "sig": base64.b64encode(sig).decode("ascii"),
    }
    return signed


def receipt_digest(receipt: dict) -> str:
    """Chain digest: SHA-256 over JCS of the receipt *without* signatureObject/anchors."""
    body = {k: v for k, v in receipt.items()
            if k not in ("signatureObject", "signature", "anchors")}
    return hash_obj(body)


def verify_receipt(receipt: dict, pinned_pubkey: bytes = None,
                   future_skew_s: int = 300, now=None) -> tuple:
    """Verify one receipt. Returns (problems, digest).

    Checks, in the draft's order (section 8, mandatory list):
      1. signature over PAE verifies with the declared alg;
      2. the key is taken from `pinned_pubkey`, never from the envelope;
      3. every REQUIRED field is present and well formed;
      6. `issued_at` is not more than `future_skew_s` ahead of the caller's clock.
    Items 4, 5 and 7 (chain link, anchor, policy resolution) belong to the chain
    and package layers and are checked there.
    """
    problems = []

    for field in REQUIRED_FIELDS:
        if field not in receipt:
            problems.append("REQUIRED field %r is missing" % field)
    if problems:
        return (problems, None)

    if receipt.get("type") not in ("protectmcp:decision", "protectmcp:restraint",
                                   "protectmcp:lifecycle"):
        problems.append("type %r is outside the profile namespace"
                        % (receipt.get("type"),))

    for field, prefix in (("action_ref", "sha256:"), ("payload_digest", "sha256:")):
        value = receipt.get(field)
        if not isinstance(value, str) or not value.startswith(prefix) or \
                len(value) != len(prefix) + 64:
            problems.append("%s is not %s<64 hex>" % (field, prefix))

    prev = receipt.get("previousReceiptHash")
    if not isinstance(prev, str) or len(prev) != 64 or \
            any(c not in "0123456789abcdef" for c in prev):
        problems.append("previousReceiptHash is not 64 lowercase hex")

    if now is not None:
        from datetime import datetime
        try:
            ts = datetime.fromisoformat(str(receipt["issued_at"]).replace("Z", "+00:00"))
        except ValueError:
            problems.append("issued_at is not an ISO 8601 timestamp")
            ts = None
        if ts is not None and getattr(ts, "tzinfo", None) is not None:
            ahead = (ts - now).total_seconds()
            if ahead > future_skew_s:
                problems.append("issued_at is %.0f s in the future (bound %d s)"
                                % (ahead, future_skew_s))

    sig_obj = receipt.get("signatureObject") or {}
    if sig_obj.get("alg") != "Ed25519":
        problems.append("signatureObject.alg is %r, expected 'Ed25519'"
                        % (sig_obj.get("alg"),))
    if pinned_pubkey is None:
        problems.append("no pinned public key supplied; the envelope's own key "
                        "is not a trust anchor (draft section 8)")
    elif sig_obj.get("alg") == "Ed25519":
        body = {k: v for k, v in receipt.items()
                if k not in ("signatureObject", "signature", "anchors")}
        try:
            sig = base64.b64decode(sig_obj.get("sig") or "")
            ok = verify(pinned_pubkey, pae(RECEIPT_PAYLOAD_TYPE, canonicalize(body)), sig)
        except Exception:  # noqa: BLE001 - hostile bytes
            ok = False
        if not ok:
            problems.append("signature does not verify with the pinned key")
        elif sig_obj.get("kid") and not str(sig_obj["kid"]).endswith(
                pinned_pubkey.hex()[:16]):
            problems.append("signatureObject.kid does not match the pinned key")

    return (problems, receipt_digest(receipt))


def verify_chain(receipts: list, pinned_pubkey: bytes = None,
                 future_skew_s: int = 300, now=None) -> tuple:
    """Verify a list of receipts as one linear chain.

    Returns (problems, checked). An empty list is a problem, not a pass: a
    chain of nothing proves nothing.
    """
    problems = []
    if not receipts:
        return (["chain carries no receipts"], 0)

    checked = 0
    prev = None
    for i, receipt in enumerate(receipts):
        if not isinstance(receipt, dict):
            problems.append("receipt %d is not an object" % i)
            continue
        r_problems, digest = verify_receipt(receipt, pinned_pubkey=pinned_pubkey,
                                            future_skew_s=future_skew_s, now=now)
        for p in r_problems:
            problems.append("receipt %d: %s" % (i, p))
        if digest is None:
            continue
        expected = GENESIS if i == 0 else prev
        if expected and receipt.get("previousReceiptHash") != expected:
            problems.append(
                "receipt %d: previousReceiptHash does not match the predecessor "
                "(%s... vs %s...)" % (i, str(receipt.get("previousReceiptHash"))[:12],
                                      expected[:12]))
        prev = digest
        checked += 1

    return (problems, checked)
