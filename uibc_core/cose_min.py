#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal CBOR + COSE_Sign1 (EdDSA), stdlib only.

Why this exists
---------------
`tools/cose_sign1_interop.py` already bridges our S6 seal to SCITT-style
COSE_Sign1, but it needs `pycose` + `cbor2`. That makes the one interop path we
have the one path a fresh machine cannot run without installing something, which
weakens the "no third-party dependency" property everywhere else in this repo.

This module is the smallest honest answer: deterministic CBOR (RFC 8949 section
4.2 subset) plus COSE_Sign1 signing and verification over Ed25519 (RFC 9052).
It is a *subset*, deliberately:

  * integers of any size we need, but no tags, floats, or indefinite lengths;
  * text and byte strings, arrays, maps (sorted keys, shortest form);
  * one algorithm: EdDSA (-8), and a verifier that refuses anything else.

Scope warning that belongs in the docstring, not in a footnote: this is a
verifier-compatible subset, not a general CBOR library. Anything outside the
subset raises `CborError` instead of being silently approximated. If a future
SCITT profile needs floats or tags, this module should grow or be replaced -
it should not start guessing.
"""

import struct

from . import ed25519

# COSE algorithm identifier for EdDSA (RFC 9053).
ALG_EDDSA = -8


class CborError(ValueError):
    """Raised when input is outside this module's supported CBOR subset."""


# --------------------------------------------------------------------------
# encoding (deterministic: RFC 8949 section 4.2.1 subset)
# --------------------------------------------------------------------------

def _enc_head(major: int, value: int) -> bytes:
    if value < 0:
        raise CborError("negative length")
    if value < 24:
        return bytes([(major << 5) | value])
    if value < 1 << 8:
        return bytes([(major << 5) | 24]) + struct.pack(">B", value)
    if value < 1 << 16:
        return bytes([(major << 5) | 25]) + struct.pack(">H", value)
    if value < 1 << 32:
        return bytes([(major << 5) | 26]) + struct.pack(">I", value)
    return bytes([(major << 5) | 27]) + struct.pack(">Q", value)


def encode(obj) -> bytes:
    """Encode one supported object to deterministic CBOR."""
    if obj is True:
        return b"\xf5"
    if obj is False:
        return b"\xf4"
    if obj is None:
        return b"\xf6"
    if isinstance(obj, int):
        if obj >= 0:
            return _enc_head(0, obj)
        return _enc_head(1, -1 - obj)
    if isinstance(obj, bytes):
        return _enc_head(2, len(obj)) + obj
    if isinstance(obj, str):
        raw = obj.encode("utf-8")
        return _enc_head(3, len(raw)) + raw
    if isinstance(obj, (list, tuple)):
        return _enc_head(4, len(obj)) + b"".join(encode(v) for v in obj)
    if isinstance(obj, dict):
        pairs = []
        for k, v in obj.items():
            kb = encode(k)
            pairs.append((len(kb), kb, encode(v)))
        # deterministic order: shorter key encoding first, then bytewise
        pairs.sort(key=lambda t: (t[0], t[1]))
        body = b"".join(kb + vb for _, kb, vb in pairs)
        return _enc_head(5, len(pairs)) + body
    raise CborError("unsupported type: %r" % (type(obj),))


# --------------------------------------------------------------------------
# decoding (same subset; anything else raises)
# --------------------------------------------------------------------------

def _dec_head(data: bytes, pos: int):
    if pos >= len(data):
        raise CborError("truncated head")
    b = data[pos]
    major = b >> 5
    ai = b & 0x1F
    pos += 1
    if ai < 24:
        return major, ai, pos
    if ai == 24:
        return major, struct.unpack(">B", data[pos:pos + 1])[0], pos + 1
    if ai == 25:
        return major, struct.unpack(">H", data[pos:pos + 2])[0], pos + 2
    if ai == 26:
        return major, struct.unpack(">I", data[pos:pos + 4])[0], pos + 4
    if ai == 27:
        return major, struct.unpack(">Q", data[pos:pos + 8])[0], pos + 8
    raise CborError("unsupported additional-info %d (tags/indefinite not supported)" % ai)


def decode(data: bytes):
    """Decode one object; reject trailing bytes."""
    value, pos = _decode_at(data, 0)
    if pos != len(data):
        raise CborError("trailing bytes after object: %d" % (len(data) - pos))
    return value


def _decode_at(data: bytes, pos: int):
    major, val, pos = _dec_head(data, pos)
    if major == 0:
        return val, pos
    if major == 1:
        return -1 - val, pos
    if major == 2:
        end = pos + val
        if end > len(data):
            raise CborError("truncated bytes")
        return data[pos:end], end
    if major == 3:
        end = pos + val
        if end > len(data):
            raise CborError("truncated text")
        try:
            return data[pos:end].decode("utf-8"), end
        except UnicodeDecodeError as exc:
            raise CborError("bad utf-8: %s" % exc)
    if major == 4:
        out = []
        for _ in range(val):
            item, pos = _decode_at(data, pos)
            out.append(item)
        return out, pos
    if major == 5:
        out = {}
        for _ in range(val):
            k, pos = _decode_at(data, pos)
            if isinstance(k, (list, dict)):
                raise CborError("unhashable map key")
            v, pos = _decode_at(data, pos)
            out[k] = v
        return out, pos
    if major == 7:
        # only the three simple values we encode ourselves; no floats
        if val == 20:
            return False, pos
        if val == 21:
            return True, pos
        if val == 22:
            return None, pos
        raise CborError("unsupported simple value %d (floats not supported)" % val)
    # major 6 (tags) is out of scope on purpose
    raise CborError("unsupported major type %d" % major)


# --------------------------------------------------------------------------
# COSE_Sign1 (RFC 9052 section 4.2), EdDSA only
# --------------------------------------------------------------------------

def _sig_structure(protected: bytes, payload: bytes) -> bytes:
    # RFC 9052 4.4: ["Signature1", body_protected, external_aad, payload]
    # external_aad is the empty bstr for this profile.
    return encode(["Signature1", protected, b"", payload])


def sign1_encode(payload: bytes, seed: bytes, content_type: str = "application/uibc",
                 detached: bool = False) -> bytes:
    """Build a COSE_Sign1 over `payload`.

    detached=True produces a message whose payload field is nil; the caller
    keeps the payload out of band. The signature always covers the real payload.
    """
    pub = ed25519.publickey(seed)
    hdr = {1: ALG_EDDSA}
    if content_type:
        hdr[3] = content_type
    hdr[4] = pub                      # kid: carry the public key, as our bridge does
    protected = encode(hdr)
    body = _sig_structure(protected, payload)
    sig = ed25519.sign(seed, body)
    payload_field = None if detached else payload
    return encode([protected, {}, payload_field, sig])


def sign1_verify(cose_bytes: bytes, public_key: bytes = None, payload: bytes = None):
    """Verify a COSE_Sign1. Returns (ok: bool, payload: bytes|None, reason: str).

    `public_key` is optional when the message carries it in the protected kid
    (field 4). `payload` is required only for detached messages.
    Never raises on a well-formed message that simply fails to verify; it
    returns ok=False with a reason, so callers cannot mistake an exception-free
    path for a pass.
    """
    try:
        msg = decode(cose_bytes)
    except CborError as exc:
        return False, None, "cbor: %s" % exc
    if not isinstance(msg, list) or len(msg) != 4:
        return False, None, "not a COSE_Sign1 4-element array"
    protected, _unprotected, payload_field, sig = msg
    if not isinstance(protected, bytes) or not isinstance(sig, bytes):
        return False, None, "protected/signature must be bstr"
    try:
        hdr = decode(protected)
    except CborError as exc:
        return False, None, "protected header: %s" % exc
    if not isinstance(hdr, dict):
        return False, None, "protected header is not a map"
    alg = hdr.get(1)
    if alg != ALG_EDDSA:
        return False, None, "algorithm %r is not EdDSA(-8); refusing rather than guessing" % (alg,)
    kid = hdr.get(4)
    if public_key is None:
        if not isinstance(kid, bytes) or len(kid) != 32:
            return False, None, "no public key supplied and kid is not a 32-byte key"
        public_key = kid
    if payload_field is None:
        if payload is None:
            return False, None, "detached message needs the payload supplied separately"
        payload_field = payload
    if not isinstance(payload_field, bytes):
        return False, None, "payload must be bstr"
    if not ed25519.verify(public_key, _sig_structure(protected, payload_field), sig):
        return False, None, "signature does not verify"
    return True, payload_field, "ok"
