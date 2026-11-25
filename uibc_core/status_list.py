"""status_list.py (v0.7 draft) - bit-array status list with herd privacy.

Indices are allocated densely; a verifier learns only "this index is VALID/REVOKED"
plus the whole list, not which other subject each bit belongs to. Compare: the
current implementation uses a plaintext JSONL revocation record per package.
"""
import base64
from . import signing
from .canonical import canonicalize

VALID, REVOKED, SUSPENDED = 0x00, 0x01, 0x02


def empty(size: int = 1024) -> bytearray:
    assert size % 8 == 0
    return bytearray(size // 8)


def set_status(bits: bytearray, index: int, status: int) -> None:
    if status == VALID:
        return
    byte, bit = divmod(index, 8)
    bits[byte] |= 1 << (7 - bit)          # bit set == not VALID (v1: only REVOKED)


def get_status(bits: bytearray, index: int) -> int:
    byte, bit = divmod(index, 8)
    return REVOKED if bits[byte] & (1 << (7 - bit)) else VALID


def build_token(bits: bytearray, seed: bytes, issuer: str, issued_at: str) -> dict:
    size = len(bits) * 8
    body = {"schema": "uibc-status-list/0.1", "issuer": issuer,
            "issued_at": issued_at, "size": size,
            "bits": base64.b64encode(bytes(bits)).decode("ascii")}
    sig = signing._ed.sign(seed, canonicalize(body))   # noqa: SLF001
    body["public_key"] = base64.b64encode(signing.ed_public_key(seed)).decode("ascii")
    body["signature"] = base64.b64encode(sig).decode("ascii")
    return body


def verify_token(token: dict) -> tuple[bool, str]:
    try:
        body = {k: token[k] for k in ("schema", "issuer", "issued_at", "size", "bits")}
        pub = signing.b64decode_strict(token["public_key"])
        sig = base64.b64decode(token["signature"].encode("ascii"), validate=True)
        ok = signing._ed.verify(pub, canonicalize(body), sig)   # noqa: SLF001
        return ok, ("signature ok" if ok else "signature mismatch")
    except Exception as e:               # noqa: BLE001
        return False, f"malformed: {type(e).__name__}"


def bits_of(token: dict) -> bytearray:
    return bytearray(base64.b64decode(token["bits"]))
