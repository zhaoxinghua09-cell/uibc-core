"""witness.py (v0.7 draft) - witness cosignature over a package checkpoint head.

A witness is an *independent* key holder that asserts "I saw this checkpoint".
Policy: at least one cosignature, from a key different from the package seal key.
No log, no network - the cosignature file travels with the disclosure bundle.
"""
import base64
from . import signing
from .canonical import canonicalize


def cosign(checkpoint_head: str, seed: bytes, witness_id: str) -> dict:
    pub = signing.ed_public_key(seed)
    stmt = canonicalize({"checkpoint_head": checkpoint_head, "witness_id": witness_id})
    sig = signing._ed.sign(seed, stmt)          # noqa: SLF001 - same module family
    return {"witness_id": witness_id,
            "public_key": base64.b64encode(pub).decode("ascii"),
            "signature": base64.b64encode(sig).decode("ascii"),
            "checkpoint_head": checkpoint_head}


def verify_cosignature(cos: dict, checkpoint_head: str, seal_public_key_b64: str) -> bool:
    try:
        if cos.get("checkpoint_head") != checkpoint_head:
            return False
        if cos.get("public_key") == seal_public_key_b64:
            return False                      # a witness may not be the signer itself
        pub = signing.b64decode_strict(cos["public_key"])
        stmt = canonicalize({"checkpoint_head": checkpoint_head,
                             "witness_id": cos["witness_id"]})
        sig = base64.b64decode(cos["signature"].encode("ascii"), validate=True)
        return signing._ed.verify(pub, stmt, sig)   # noqa: SLF001
    except Exception:
        return False
