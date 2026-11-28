"""Ed25519 verify must reject signatures that were produced without any secret.

Measured 2026-11-27 against the pre-fix module: a public key of the identity point
with R = identity and S = 0 verified *every* message, because both sides of
[S]B == R + [h]A collapse to the identity. That signature costs no private key, so
"signature valid" could not be read as "the signer held one". These cases pin the
two rejections that restore the reading: small-order points and non-canonical y.
"""

from uibc_core import ed25519

# RFC 8032 section 7.1, the three vectors the module was already pinned by.
VECTORS = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc"
     "61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e4"
     "58f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
]

IDENTITY = b"\x01" + b"\x00" * 31


def test_rfc8032_vectors_still_verify():
    for seed, pub, msg, sig in VECTORS:
        s, p, m, g = bytes.fromhex(seed), bytes.fromhex(pub), bytes.fromhex(msg), bytes.fromhex(sig)
        assert ed25519.publickey(s) == p
        assert ed25519.sign(s, m) == g
        assert ed25519.verify(p, m, g) is True


def test_identity_key_forgery_is_rejected():
    forged = IDENTITY + b"\x00" * 32
    assert ed25519.verify(IDENTITY, b"any message at all", forged) is False
    assert ed25519.verify(IDENTITY, b"", forged) is False


def test_tampered_signature_is_rejected():
    seed = bytes.fromhex(VECTORS[0][0])
    pub = ed25519.publickey(seed)
    sig = bytearray(ed25519.sign(seed, b"hello"))
    sig[10] ^= 0x01
    assert ed25519.verify(pub, b"hello", bytes(sig)) is False


def test_signature_scalar_above_group_order_is_rejected():
    seed = bytes.fromhex(VECTORS[0][0])
    pub = ed25519.publickey(seed)
    sig = bytearray(ed25519.sign(seed, b"hello"))
    sig[32:] = ed25519._L.to_bytes(32, "little")
    assert ed25519.verify(pub, b"hello", bytes(sig)) is False


def test_non_canonical_y_is_rejected():
    # y = q encodes the same point as y = 0 in a second byte string
    data = bytearray(32)
    data[31] = 0x7F
    data[:31] = (ed25519._Q & ((1 << 248) - 1)).to_bytes(31, "little")
    assert ed25519._canonical_y(bytes(data)) is False
    assert ed25519._canonical_y(IDENTITY) is True
