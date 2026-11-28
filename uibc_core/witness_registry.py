"""witness_registry.py (v0.8 draft) - k-of-n witness policy.

A policy is a named list of witnesses (id + Ed25519 public key) plus a quorum.
Validation: every cosignature must come from a *listed* key, ids must be
distinct, no witness may be the package seal key, and at least `quorum`
distinct witnesses must cosign.
"""
from . import witness


def load_policy(doc: dict) -> dict:
    if doc.get("schema") != "uibc-witness-policy/0.1":
        raise ValueError("unexpected policy schema")
    ids = [w["id"] for w in doc["witnesses"]]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate witness id in policy")
    if not 0 < doc.get("quorum", 0) <= len(doc["witnesses"]):
        raise ValueError("quorum out of range")
    return doc


def verify_quorum(policy: dict, cosignatures: list, checkpoint_head: str,
                  seal_public_key_b64: str) -> tuple[bool, dict]:
    listed = {w["public_key"]: w["id"] for w in policy["witnesses"]}
    seen, good, rejected = set(), [], []
    for cos in cosignatures:
        pk = cos.get("public_key")
        if pk not in listed:
            rejected.append({"id": cos.get("witness_id"), "reason": "key not in policy"})
            continue
        if listed[pk] in seen:
            rejected.append({"id": listed[pk], "reason": "duplicate witness"})
            continue
        if pk == seal_public_key_b64:
            rejected.append({"id": listed[pk], "reason": "witness is the seal key"})
            continue
        if not witness.verify_cosignature(cos, checkpoint_head, seal_public_key_b64):
            rejected.append({"id": listed[pk], "reason": "cosignature invalid"})
            continue
        seen.add(listed[pk]); good.append(listed[pk])
    ok = len(good) >= policy["quorum"]
    return ok, {"quorum": policy["quorum"], "valid": good, "rejected": rejected,
                "satisfied": ok}
