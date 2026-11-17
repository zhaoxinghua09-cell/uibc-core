"""External verifier ("rail") for the Adversarial Execution Evidence (AEE)
predicate, in-toto attestation type
``https://in-toto.io/attestation/adversarial-execution-evidence/v0.7``.

Why this exists: the ``agent-evidence-vectors`` conformance corpus (Sankalp
Gilda / Probity AI) ships 288 vectors for this predicate and drives third-party
verifiers through a fixed contract -- ``<cmd> <vector-file>``, exit 0 = valid,
last stdout line one JSON object ``{"verdict", "codes", "result", "tiers"}``.
This module is uibc-core's rail for that contract, so the corpus can run
against an implementation that shares no code with the corpus's own
reference verifier. It is a verifier only: it produces no AEE statements and
signs nothing.

What it checks, in the spec's own staging (all byte-pure except the last):

  GATE 0  statement well-formedness -- strict I-JSON over the raw bytes
          (duplicate members, non-scalar strings, noncharacters, nesting
          depth), statement/predicate type, result vocabulary, the
          ``issuedAt`` timestamp profile, environment completeness, the
          closed posture vocabulary, vocabulary canonicality and digest,
          corpus manifest digest / floor / duplicates / expectedPayloads
          shape, coverage partition and coverage integrity, per-row member
          typing, subject cardinality, binding-input digest form, and the
          statement-level record checks (signature-entry count, undecodable
          payloads, batch root, duplicate records).
  GATE 1  byte-checkable coverage validity for every ``basis: substrate``
          row: references resolve, referenced payloads are canonical
          ``+json`` carrying the reserved members and the derived run
          binding, class match per kind, kind constraints (arming / sealed
          / examination), and the ``aeeMethod`` cap.
  0.7 commitments -- the statement-level coverage rules (clean row never
          resolving an interception, no orphaned interception, the seal's
          ``aeeObservedSet`` recompute, a satisfying ``sealed`` record
          present, every carried covering-kind record satisfying its kind,
          ``aeeObservedAttacks`` obliging caught rows, the
          ``aeeAssessedAttacks`` subset rule, and the ``attribution:
          pinned`` binding check).
  Recompute -- ``result`` as the minimum of the three independent
          conditions (fail / degraded / pass_indirect), a pure function of
          the carried rows and coverage maps.
  GATE 2  the per-row evidence tier against consumer key policy: the
          substrate observation keys a consumer pins out of band (never
          inferred from the predicate -- no pinned key means every
          substrate row is ``unattested``). The tier never alters
          ``result`` and never alters the verdict.

Consumer key policy travels in the environment variable
``AEE_SUBSTRATE_KEYS``, a path to
``{"substrateObservationKeys": [{"keyid": ..., "publicKeyHex": ...}]}`` --
the corpus contract's spelling. A record's ``keyid`` is an unauthenticated
lookup hint and is never the check; signatures are verified against every
pinned key.

Profile notes (where this rail deliberately does NOT reuse a sibling
module, because the AEE profile pins a different acceptance set):

  * Canonicalization is RFC 8785 JCS under the predicate's integers-only
    I-JSON profile: any JSON integer serializes as itself, an integral
    float serializes as its integer, and a non-integral or out-of-safe-
    range number is an error. ``uibc_core.canonical`` implements the full
    ECMAScript number serialization instead, which would derive different
    bytes (or none) on exactly the inputs this profile refuses.
  * Ed25519 verification uses the strict point decoder the tier requires
    (non-canonical ``y >= p``, rootless encodings, and ``x == 0`` with the
    sign bit set are rejected before the group equation is consulted);
    ``uibc_core.ed25519`` is the seal verifier and accepts some of those
    encodings. The group arithmetic is the same RFC 8032 mathematics.
  * Base64 is the DSSE-canonical rule (alphabet-validated decode plus a
    re-encode round-trip), under which the empty string decodes to empty
    bytes; ``uibc_core.encoding`` scores a package-oriented profile that
    additionally refuses empty and unpadded spellings.
  * The batch root DOES reuse ``uibc_core.merkle`` unchanged: its leaf
    hash ``H(0x00 || data)``, node hash ``H(0x01 || l || r)`` and
    largest-power-of-two recursive split are exactly the RFC 6962
    construction the predicate pins.

Stdlib only, like the rest of ``uibc_core``. Fail-closed throughout: any
internal error on hostile input is reported as an invalid statement, never
raised to the caller and never silently passed.
"""

from __future__ import annotations

import base64
import binascii
import decimal
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta

from . import merkle
from .canonical import sha256_hex

__all__ = ["verify_statement", "verify_file", "main", "AEE_PREDICATE_TYPE"]

AEE_PREDICATE_TYPE = "https://in-toto.io/attestation/adversarial-execution-evidence/v0.7"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
BINDING_VERSION = "2"

SAFE_INT_LIMIT = 2 ** 53
MAX_PARSE_DEPTH = 128
MAX_PARSE_BYTES = 20 << 20  # 20 MiB, the payload/statement strict-pass bound

RESULT_ORDER = {"fail": 0, "degraded": 1, "pass_indirect": 2, "pass": 3}
METHOD_ORDER = {"reconstructed": 0, "intercepted": 1}
EGRESS_POSTURES = frozenset(
    {"no_network", "allowlist", "sinkhole", "unsafe_bypass_egress"}
)
COVERING_KINDS = ("interception", "arming", "sealed", "examination")
REGISTERED_NONCOVERING = {
    "moat-drop": "moat-drop-covers-nothing",
    "uncommitted-observation": "uncommitted-observation-covers-nothing",
}
RESERVED_MEMBERS = ("aeeRunBinding", "aeeKind", "aeeMethod")
CHAIN_SCOPE_VOCAB = frozenset({"subject", "corpus", "networkPosture"})

RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

KEY_POLICY_ENV = "AEE_SUBSTRATE_KEYS"


# ---------------------------------------------------------------------------
# RFC 8785 JCS under the AEE integers-only I-JSON profile
# ---------------------------------------------------------------------------


class _JcsError(ValueError):
    pass


def _utf16_sort_key(s: str) -> bytes:
    """UTF-16 code-unit sort key (RFC 8785 section 3.2.3)."""
    return s.encode("utf-16-be")


def _all_bmp(strings) -> bool:
    return all(ord(ch) <= 0xFFFF for s in strings for ch in s)


def _member_names_bmp(v) -> bool:
    if isinstance(v, dict):
        return all(_all_bmp([k]) and _member_names_bmp(x) for k, x in v.items())
    if isinstance(v, list):
        return all(_member_names_bmp(x) for x in v)
    return True


_JCS_CTRL = {0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r"}


def _jcs_string(s: str) -> str:
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o < 0x20:
            out.append(_JCS_CTRL.get(o, "\\u%04x" % o))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _jcs_float(v: float) -> str:
    """An integral float serializes as its integer; anything else is outside
    the integers-only profile (fractional, non-finite, or beyond the safe
    range) and refuses canonicalization."""
    if not v.is_integer():
        raise _JcsError("non-integer number outside the I-JSON profile")
    if abs(v) >= SAFE_INT_LIMIT:
        raise _JcsError("integer outside safe range")
    return str(int(v))


def _jcs_dumps(obj) -> bytes:
    def ser(v) -> str:
        if v is None:
            return "null"
        if v is True:
            return "true"
        if v is False:
            return "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return _jcs_float(v)
        if isinstance(v, str):
            return _jcs_string(v)
        if isinstance(v, list):
            return "[" + ",".join(ser(x) for x in v) + "]"
        if isinstance(v, dict):
            keys = sorted(v.keys(), key=_utf16_sort_key)
            return "{" + ",".join(_jcs_string(k) + ":" + ser(v[k]) for k in keys) + "}"
        raise _JcsError("unsupported type: %r" % (type(v),))

    return ser(obj).encode("utf-8")


def _jcs_dumps_safe(obj) -> bytes:
    try:
        return _jcs_dumps(obj)
    except Exception:
        return repr(obj).encode("utf-8")


def _digest_of(obj):
    if isinstance(obj, dict):
        d = obj.get("digest")
        if isinstance(d, dict):
            return d.get("sha256")
    return None


def _is_hex64_lower(v) -> bool:
    return isinstance(v, str) and bool(HEX64_RE.match(v))


# ---------------------------------------------------------------------------
# Byte-level string-scalar scan (RFC 7493): applied to raw bytes before any
# decoded string is read, because lenient decoders substitute U+FFFD or lone
# surrogates and every downstream check would read a string never written.
# ---------------------------------------------------------------------------


class _StringNotScalarError(ValueError):
    pass


def _hex4(b: bytes):
    if len(b) < 4:
        return None
    v = 0
    for c in b[:4]:
        if 0x30 <= c <= 0x39:
            v = v << 4 | (c - 0x30)
        elif 0x61 <= c <= 0x66:
            v = v << 4 | (c - 0x61 + 10)
        elif 0x41 <= c <= 0x46:
            v = v << 4 | (c - 0x41 + 10)
        else:
            return None
    return v


def _is_noncharacter(cp: int) -> bool:
    return cp & 0xFFFE == 0xFFFE or 0xFDD0 <= cp <= 0xFDEF


def _check_surrogate_pair(b: bytes, hi: int) -> int:
    if len(b) < 12 or b[6:8] != b"\\u":
        raise _StringNotScalarError("unpaired high surrogate \\u%04X" % hi)
    lo = _hex4(b[8:])
    if lo is None:
        raise _StringNotScalarError("malformed \\u escape after high surrogate")
    if not 0xDC00 <= lo < 0xE000:
        raise _StringNotScalarError("high surrogate not followed by a low surrogate")
    cp = 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
    if _is_noncharacter(cp):
        raise _StringNotScalarError("noncharacter U+%04X in string" % cp)
    return 12


def _check_escape(b: bytes) -> int:
    if len(b) < 2:
        raise _StringNotScalarError("unterminated escape sequence")
    if b[1:2] != b"u":
        return 2
    hi = _hex4(b[2:])
    if hi is None:
        raise _StringNotScalarError("malformed \\u escape")
    if 0xD800 <= hi < 0xDC00:
        return _check_surrogate_pair(b, hi)
    if 0xDC00 <= hi < 0xE000:
        raise _StringNotScalarError("unpaired low surrogate \\u%04X" % hi)
    if _is_noncharacter(hi):
        raise _StringNotScalarError("noncharacter U+%04X in string" % hi)
    return 6


def _utf8_seq_len(lead: int) -> int:
    if 0xC2 <= lead <= 0xDF:
        return 2
    if 0xE0 <= lead <= 0xEF:
        return 3
    if 0xF0 <= lead <= 0xF4:
        return 4
    return 0


def _check_string_literal(b: bytes) -> int:
    i = 1
    while i < len(b):
        c = b[i]
        if c == 0x22:  # '"'
            return i + 1
        if c == 0x5C:  # '\'
            i += _check_escape(b[i:])
        elif c < 0x20:
            raise _StringNotScalarError("raw control character U+%04X in string" % c)
        elif c < 0x80:
            i += 1
        else:
            size = _utf8_seq_len(c)
            if size == 0 or i + size > len(b):
                raise _StringNotScalarError("invalid UTF-8 in string")
            try:
                ch = b[i : i + size].decode("utf-8")
            except UnicodeDecodeError:
                raise _StringNotScalarError("invalid UTF-8 in string") from None
            if _is_noncharacter(ord(ch)):
                raise _StringNotScalarError("noncharacter U+%04X in string" % ord(ch))
            i += size
    raise _StringNotScalarError("unterminated string literal")


def _check_string_scalars(raw: bytes) -> None:
    """Validate every string literal in a syntactically valid JSON text."""
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] != 0x22:  # '"'
            i += 1
            continue
        i += _check_string_literal(raw[i:])


def _max_json_depth(text: str) -> int:
    depth = maxd = 0
    in_str = esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > maxd:
                maxd = depth
        elif ch in "]}":
            depth -= 1
    return maxd


def _statement_strict_fault(raw: bytes) -> bool:
    """Whole-statement strict I-JSON pass: size bound, UTF-8, nesting bound,
    duplicate members at any depth, and string scalar well-formedness -- the
    faults a decoded value can no longer show. A statement that is not
    parseable JSON at all is a fault here too."""
    if len(raw) > MAX_PARSE_BYTES:
        return True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return True
    if _max_json_depth(text) > MAX_PARSE_DEPTH:
        return True

    found = False

    def hook(pairs):
        nonlocal found
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            found = True
        return dict(pairs)

    try:
        json.loads(text, object_pairs_hook=hook)
    except (ValueError, RecursionError):
        return True
    if found:
        return True
    try:
        _check_string_scalars(raw)
    except _StringNotScalarError:
        return True
    return False


# ---------------------------------------------------------------------------
# RFC 7493 strict payload parse for observation records
# ---------------------------------------------------------------------------


class _IJsonError(ValueError):
    def __init__(self, code: str, msg: str):
        super().__init__(msg)
        self.code = code


def _safe_integer_literal(s: str) -> int:
    """A float-syntax literal is admitted only when its VALUE is an integer
    inside the safe range (``1e2`` denotes 100); Decimal keeps the exponent
    so a hostile ``1e1000000000`` never materializes its digits."""
    d = decimal.Decimal(s)
    if d != d.to_integral_value():
        raise _IJsonError("payload-not-ijson", "non-integer number %r" % s)
    if not -SAFE_INT_LIMIT < d < SAFE_INT_LIMIT:
        raise _IJsonError("payload-not-ijson", "integer outside safe range")
    return int(d)


def _reject_dup_pairs(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise _IJsonError("payload-not-ijson", "duplicate member %r" % k)
        d[k] = v
    return d


def _walk_check_ints(v) -> None:
    if isinstance(v, bool):
        return
    if isinstance(v, int):
        if abs(v) >= SAFE_INT_LIMIT:
            raise _IJsonError("payload-not-ijson", "integer outside safe range")
    elif isinstance(v, float):
        raise _IJsonError("payload-not-ijson", "non-integer number")
    elif isinstance(v, list):
        for x in v:
            _walk_check_ints(x)
    elif isinstance(v, dict):
        for x in v.values():
            _walk_check_ints(x)


def _parse_json_value(raw: bytes):
    """Parse payload bytes under the I-JSON profile; every failure is
    payload-not-ijson (a payload that is not a parseable I-JSON value at
    all is one covers-nothing class)."""
    if len(raw) > MAX_PARSE_BYTES:
        raise _IJsonError("payload-not-ijson", "payload exceeds the maximum size")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _IJsonError("payload-not-ijson", "payload is not UTF-8") from None
    if _max_json_depth(text) > MAX_PARSE_DEPTH:
        raise _IJsonError("payload-not-ijson", "payload nesting exceeds the maximum depth")
    try:
        obj = json.loads(
            text,
            object_pairs_hook=_reject_dup_pairs,
            parse_float=_safe_integer_literal,
        )
    except _IJsonError:
        raise
    except (ValueError, RecursionError):
        raise _IJsonError("payload-not-ijson", "payload does not parse as JSON") from None
    try:
        _check_string_scalars(raw)
    except _StringNotScalarError as e:
        raise _IJsonError("payload-not-ijson", "payload string is not scalar: %s" % e) from None
    return obj


def _strict_payload_parse(raw: bytes) -> dict:
    """Parse record payload bytes and require RFC 8785 canonical form."""
    obj = _parse_json_value(raw)
    if not isinstance(obj, dict):
        raise _IJsonError("payload-not-canonical", "payload is not a JSON object")
    if not _member_names_bmp(obj):
        raise _IJsonError("payload-not-canonical", "supplementary-plane object member name")
    _walk_check_ints(obj)
    try:
        canon = _jcs_dumps(obj)
    except _JcsError:
        raise _IJsonError("payload-not-ijson", "payload not canonicalizable") from None
    if canon != raw:
        raise _IJsonError("payload-not-canonical", "payload bytes are not RFC 8785 canonical")
    return obj


def _b64decode_strict(s: str) -> bytes:
    """Canonical base64: alphabet-validated decode plus a re-encode
    round-trip, so encodings with set pad bits or non-standard padding are
    refused rather than decoded differently by different readers."""
    raw = base64.b64decode(s, validate=True)
    if base64.b64encode(raw).decode("ascii") != s:
        raise ValueError("non-canonical base64 (fails re-encode round-trip)")
    return raw


# ---------------------------------------------------------------------------
# DSSE PAEv1 + timestamps + array shape rules
# ---------------------------------------------------------------------------


def _pae(payload_type: str, payload: bytes) -> bytes:
    pt = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d " % (len(pt), pt, len(payload)) + payload


def _rfc3339_key(v: str):
    s = v.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _timestamp_ok(v) -> bool:
    """The predicate's Timestamp profile: RFC 3339 with uppercase
    designators (the pattern) and a zero zone offset (Z / +00:00 / -00:00),
    read off the parsed offset rather than the literal suffix."""
    if not isinstance(v, str) or not RFC3339_RE.match(v):
        return False
    key = _rfc3339_key(v)
    return key is not None and key.utcoffset() == timedelta(0)


def _sorted_no_dupes(values) -> bool:
    keys = [_utf16_sort_key(v) for v in values]
    return all(a < b for a, b in zip(keys, keys[1:]))


def _attack_id_array_ok(values, declared: set) -> bool:
    """Shape rule for aeeAssessedAttacks / aeeObservedAttacks: duplicate-free,
    UTF-16 sorted, every entry a manifest-declared attack identifier. The
    empty array satisfies it (the honest no-correspondence value)."""
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        return False
    if not _sorted_no_dupes(values):
        return False
    return all(v in declared for v in values)


def _commitment_array_ok(values) -> bool:
    """Shape rule for aeePayloadCommitment: duplicate-free, UTF-16 sorted,
    non-empty, every entry lowercase 64-hex."""
    if not isinstance(values, list) or not values:
        return False
    if not all(_is_hex64_lower(v) for v in values):
        return False
    return _sorted_no_dupes(values)


def _expected_payloads_ok(expected, declared: set) -> bool:
    """Shape rule for corpus.manifest.expectedPayloads: every key a declared
    attack identifier, every array a well-formed commitment array."""
    if not isinstance(expected, dict):
        return False
    for attack, values in expected.items():
        if not isinstance(attack, str) or attack not in declared:
            return False
        if not _commitment_array_ok(values):
            return False
    return True


# ---------------------------------------------------------------------------
# Ed25519 (RFC 8032) with the strict point decoder the evidence tier pins.
# Points are extended homogeneous coordinates (X, Y, Z, T).
# ---------------------------------------------------------------------------

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _pt_add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = t1 * 2 * _D * t2 % _P
    d = z1 * 2 * z2 % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _pt_mul(s: int, p):
    q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            q = _pt_add(q, p)
        p = _pt_add(p, p)
        s >>= 1
    return q


def _pt_eq(p, q) -> bool:
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = x * _I % _P
    if x % 2 != 0:
        x = _P - x
    return x


_BY = 4 * pow(5, _P - 2, _P) % _P
_BX = _xrecover(_BY)
_B = (_BX, _BY, 1, _BX * _BY % _P)


def _pt_decompress(s: bytes):
    """Strict RFC 8032 decoding: rejects y >= p, encodings with no curve
    point, and x == 0 carrying the sign bit -- the encodings a lenient
    decoder would silently map onto a different (or no) point."""
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= _P:
        return None
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = x * _I % _P
    if (x * x - xx) % _P != 0:
        return None
    if x == 0 and sign:
        return None
    if x & 1 != sign:
        x = _P - x
    return (x, y, 1, x * y % _P)


def _ed25519_verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(sig) != 64:
        return False
    a = _pt_decompress(pub)
    if a is None:
        return False
    rp = _pt_decompress(sig[:32])
    if rp is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L:
        return False
    k = int.from_bytes(_sha512(sig[:32] + pub + msg), "little") % _L
    return _pt_eq(_pt_mul(s, _B), _pt_add(rp, _pt_mul(k, a)))


# ---------------------------------------------------------------------------
# Decoded observation records and the derived values GATE 1 reads
# ---------------------------------------------------------------------------


class _Outcome:
    """Ordered, duplicate-free failure-code accumulator. The verdict is
    derived, never stored: any code at all means invalid."""

    def __init__(self) -> None:
        self.codes: list = []
        self._seen: set = set()

    def add(self, code: str) -> None:
        if code not in self._seen:
            self._seen.add(code)
            self.codes.append(code)

    @property
    def invalid(self) -> bool:
        return bool(self.codes)


class _RecordView:
    """One carried observation record, decoded once.

    ``pae`` is the DSSE pre-authentication encoding of the payload (present
    only when the payload strict-base64-decodes and the payload type is a
    string); ``payload`` is the strict-parsed payload object, or None with
    ``payload_error`` naming why it is unreadable. ``signature_count`` is a
    pure count of DSSE signature entries -- it proves nothing about any of
    them, which is why verification lives at the tier, not here.
    """

    def __init__(self, idx: int, rec) -> None:
        self.idx = idx
        self.raw = rec
        self.payload_type = rec.get("payloadType") if isinstance(rec, dict) else None
        self.payload_bytes = None
        self.pae = None
        self.payload = None
        self.payload_error = None
        self.decode_err = False
        if isinstance(rec, dict) and isinstance(rec.get("payload"), str):
            try:
                self.payload_bytes = _b64decode_strict(rec["payload"])
            except (binascii.Error, ValueError):
                self.payload_bytes = None
                self.decode_err = True
        if self.payload_bytes is not None and isinstance(self.payload_type, str):
            self.pae = _pae(self.payload_type, self.payload_bytes)
        if self.payload_bytes is not None:
            try:
                self.payload = _strict_payload_parse(self.payload_bytes)
            except _IJsonError as e:
                self.payload_error = e.code
        self.media_ok = isinstance(self.payload_type, str) and self.payload_type.endswith("+json")
        sigs = rec.get("signatures") if isinstance(rec, dict) else None
        self.signature_count = len(sigs) if isinstance(sigs, list) else 0

    @property
    def kind(self):
        return self.payload.get("aeeKind") if self.payload else None

    @property
    def method(self):
        return self.payload.get("aeeMethod") if self.payload else None


def _observed_set_digest(views) -> str:
    """The value a seal's ``aeeObservedSet`` commits to: SHA-256 over the
    JCS form of the sorted, duplicate-free leaf hashes (``H(0x00 || PAE)``)
    of every interception and examination record. A record whose payload
    cannot be read contributes nothing -- its kind is unknowable."""
    leaves = sorted(
        {
            hashlib.sha256(b"\x00" + rv.pae).hexdigest()
            for rv in views
            if rv.pae is not None and rv.kind in ("interception", "examination")
        }
    )
    return sha256_hex(_jcs_dumps(leaves))


def _posture_object_digest(env: dict) -> str:
    """Binding-version-2 posture input: the JCS digest of the whole carried
    ``networkPosture`` object (never of its own digest member, which would
    leave the posture string itself unsigned). A non-object or
    uncanonicalizable value contributes the empty string; those statements
    already fail on their own codes."""
    raw = env.get("networkPosture")
    if not isinstance(raw, dict):
        return ""
    try:
        return sha256_hex(_jcs_dumps(raw))
    except Exception:
        return ""


def _derive_run_binding(env: dict, subject_sha):
    """The version-2 run binding: SHA-256 over the JCS form of the
    eight-member pre-image, or None when any verbatim input is absent (in
    which case every payload binding comparison is skipped)."""
    try:
        preimage = {
            "aeeBindingVersion": BINDING_VERSION,
            "catchPolicy": env["catchPolicy"]["digest"]["sha256"],
            "corpus": env["corpus"]["digest"]["sha256"],
            "networkPosture": _posture_object_digest(env),
            "observationVocabulary": env["observationVocabulary"]["digest"]["sha256"],
            "runEntropy": env["runEntropy"]["digest"]["sha256"],
            "subject": subject_sha,
            "substrate": env["substrate"]["digest"]["sha256"],
        }
    except (KeyError, IndexError, TypeError):
        return None
    if not all(isinstance(v, str) for v in preimage.values()):
        return None
    try:
        return sha256_hex(_jcs_dumps(preimage))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-kind payload validity (GATE 1 building blocks)
# ---------------------------------------------------------------------------


def _arming_chain_ok(p: dict) -> bool:
    """Syntax of the optional run-chaining members on an arming payload:
    ``aeeRunSeq`` a positive integer; ``aeeChainScope`` required with it, a
    duplicate-free UTF-16-sorted array over the closed scope vocabulary;
    ``aeePrevRunBinding`` present exactly when the sequence exceeds 1, as
    lowercase 64-hex. A chain member without a sequence is refused."""
    has_seq = "aeeRunSeq" in p
    has_prev = "aeePrevRunBinding" in p
    has_scope = "aeeChainScope" in p
    if not has_seq:
        return not has_prev and not has_scope
    seq = p.get("aeeRunSeq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        return False
    scope = p.get("aeeChainScope")
    if not isinstance(scope, list):
        return False
    if any(not isinstance(tok, str) or tok not in CHAIN_SCOPE_VOCAB for tok in scope):
        return False
    if sorted(scope, key=_utf16_sort_key) != scope or len(set(scope)) != len(scope):
        return False
    if seq == 1:
        return not has_prev
    return _is_hex64_lower(p.get("aeePrevRunBinding"))


def _arming_ok(rv: _RecordView, pinned_posture, issued_at, declared_attacks: set) -> bool:
    p = rv.payload or {}
    armed = p.get("armedAt")
    if not _timestamp_ok(armed):
        return False
    if _timestamp_ok(issued_at):
        a = _rfc3339_key(armed) if isinstance(armed, str) else None
        b = _rfc3339_key(issued_at) if isinstance(issued_at, str) else None
        if a is not None and b is not None and a > b:
            return False
    if p.get("aeePostureDigest") != pinned_posture:
        return False
    if p.get("aeeMethod") != "intercepted":
        return False
    bv = p.get("aeeBindingVersion")
    if bv is not None and bv != BINDING_VERSION:
        return False
    if not _arming_chain_ok(p):
        return False
    return _attack_id_array_ok(p.get("aeeAssessedAttacks"), declared_attacks)


def _sealed_commitments_ok(p: dict, declared_attacks: set) -> bool:
    """Shape half of the sealed kind: both 0.7 members present and
    well-formed. (Their statement-level equalities are checked by the
    commitment rules, not here.)"""
    if not _is_hex64_lower(p.get("aeeObservedSet")):
        return False
    return _attack_id_array_ok(p.get("aeeObservedAttacks"), declared_attacks)


def _sealed_ok(rv: _RecordView, pinned_posture, arming_postures, declared_attacks: set) -> bool:
    p = rv.payload or {}
    if p.get("aeeStillArmed") is not True:
        return False
    drops = p.get("aeeDropCount")
    if not isinstance(drops, int) or isinstance(drops, bool) or drops < 0:
        return False
    if drops > 0:
        bound = p.get("aeeDropBound")
        if not isinstance(bound, int) or isinstance(bound, bool):
            return False
        if drops > bound:
            return False
    posture = p.get("aeePostureDigest")
    if posture != pinned_posture:
        return False
    # Jointly enforced: the seal's posture must also equal every arming
    # posture claim in scope, not only the pinned environment digest.
    for arming_posture in arming_postures:
        if posture != arming_posture:
            return False
    if p.get("aeeMethod") != "intercepted":
        return False
    return _sealed_commitments_ok(p, declared_attacks)


def _examination_ok(rv: _RecordView) -> bool:
    return (rv.payload or {}).get("aeeMethod") == "reconstructed"


def _record_verifies(rv: _RecordView, pinned_pubs) -> bool:
    """True when some signature entry on the record strict-decodes and
    Ed25519-verifies over the record's PAE against some pinned key. The
    carried ``keyid`` is never consulted: it is a hint, not the check."""
    if rv.pae is None or not isinstance(rv.raw, dict):
        return False
    sigs = rv.raw.get("signatures")
    if not isinstance(sigs, list):
        return False
    for sig in sigs:
        if not isinstance(sig, dict) or not isinstance(sig.get("sig"), str):
            continue
        try:
            sig_bytes = _b64decode_strict(sig["sig"])
        except (binascii.Error, ValueError):
            continue
        for pub in pinned_pubs:
            if _ed25519_verify(pub, rv.pae, sig_bytes):
                return True
    return False


# ---------------------------------------------------------------------------
# The verifier proper: GATE 0 -> GATE 1 -> commitments -> recompute -> GATE 2
# ---------------------------------------------------------------------------


class _State:
    """Working values shared across the ordered checks of one statement."""

    def __init__(self, stmt) -> None:
        self.stmt = stmt
        self.pred: dict = {}
        self.result = None
        self.issued_at = None
        self.env: dict = {}
        self.vocab = None
        self.labels = None
        self.caught = None
        self.corpus = None
        self.manifest_classes = None
        self.rows: list = []
        self.has_substrate = False
        self.coverage = None
        self.fail_closed: set = set()
        self.has_records = False
        self.views: list = []
        self.derived = None
        self.pinned_posture = None
        self.row_covering: dict = {}
        self.declared_attacks: set = set()
        self.expected_payloads = None


def _check_statement_type(st: _State, out: _Outcome) -> bool:
    """Returns True when verification must stop (no readable predicate)."""
    stmt = st.stmt
    if not isinstance(stmt, dict):
        out.add("statement-type-unsupported")
        return True
    if stmt.get("_type") != STATEMENT_TYPE:
        out.add("statement-type-unsupported")
    if stmt.get("predicateType") != AEE_PREDICATE_TYPE:
        out.add("predicate-type-unsupported")
    # Absent, null and {} are one input: the empty predicate.
    pred = stmt.get("predicate")
    if pred is None:
        pred = {}
    if not isinstance(pred, dict):
        out.add("predicate-type-unsupported")
        return True
    st.pred = pred
    return False


def _check_wellformed(st: _State, out: _Outcome) -> None:
    pred = st.pred
    if "does_not_assert" in pred:
        out.add("member-spelling")
    result = pred.get("result")
    if not isinstance(result, str) or result not in RESULT_ORDER:
        out.add("result-vocabulary")
    st.result = result
    issued_at = pred.get("issuedAt")
    if issued_at is None:
        out.add("issued-at-missing")
    elif not _timestamp_ok(issued_at):
        out.add("issued-at-malformed")
    st.issued_at = issued_at
    env = pred.get("observationEnvironment")
    env = env if isinstance(env, dict) else {}
    for member in ("substrate", "corpus", "catchPolicy", "networkPosture"):
        if member not in env:
            out.add("environment-incomplete")
    st.env = env
    vocab = env.get("observationVocabulary")
    if not isinstance(vocab, dict):
        out.add("vocabulary-missing")
        vocab = None
    st.vocab = vocab
    # Closed posture registry; checked only when the member is carried, so
    # an absent networkPosture reports environment-incomplete alone.
    posture = env.get("networkPosture")
    if isinstance(posture, dict):
        declared = posture.get("posture")
        if not isinstance(declared, str) or declared not in EGRESS_POSTURES:
            out.add("posture-vocabulary")


def _vocab_shape_ok(labels, caught) -> bool:
    for arr in (labels, caught):
        if not isinstance(arr, list) or not all(isinstance(x, str) for x in arr):
            return False
        if sorted(arr, key=_utf16_sort_key) != arr or len(set(arr)) != len(arr):
            return False
        if not _all_bmp(arr):
            return False
    return True


def _check_vocabulary(st: _State, out: _Outcome) -> None:
    labels = caught = None
    if st.vocab is not None:
        raw_labels = st.vocab.get("labels")
        raw_caught = st.vocab.get("caught")
        if not _vocab_shape_ok(raw_labels, raw_caught):
            out.add("vocabulary-not-canonical")
        if isinstance(raw_labels, list) and isinstance(raw_caught, list):
            labels, caught = raw_labels, raw_caught
            try:
                if not set(caught) <= set(labels):
                    out.add("vocabulary-caught-not-subset")
            except TypeError:
                out.add("vocabulary-caught-not-subset")
            try:
                expect = sha256_hex(_jcs_dumps({"caught": caught, "labels": labels}))
                if _digest_of(st.vocab) != expect:
                    out.add("vocabulary-digest-mismatch")
            except Exception:
                out.add("vocabulary-digest-mismatch")
    st.labels = labels
    st.caught = caught


def _check_corpus(st: _State, out: _Outcome) -> None:
    corpus = st.env.get("corpus")
    st.corpus = corpus
    if not isinstance(corpus, dict):
        return
    manifest = corpus.get("manifest")
    classes = manifest.get("classes") if isinstance(manifest, dict) else None
    if manifest is None:
        out.add("environment-incomplete")
    if isinstance(manifest, dict):
        try:
            expect = sha256_hex(_jcs_dumps(manifest))
            if _digest_of(corpus) != expect:
                out.add("corpus-digest-mismatch")
        except Exception:
            out.add("corpus-digest-mismatch")
        declared = 0
        if isinstance(classes, dict):
            for ids in classes.values():
                declared += len(ids) if isinstance(ids, list) else 0
        if declared == 0:
            out.add("corpus-manifest-no-attacks")
    if isinstance(classes, dict):
        st.manifest_classes = classes
        seen: set = set()
        for ids in classes.values():
            for aid in ids if isinstance(ids, list) else []:
                try:
                    if aid in seen:
                        out.add("manifest-duplicate-attack")
                    seen.add(aid)
                except TypeError:
                    continue
        st.declared_attacks = {
            aid
            for ids in classes.values()
            if isinstance(ids, list)
            for aid in ids
            if isinstance(aid, str)
        }
    if isinstance(manifest, dict) and "expectedPayloads" in manifest:
        expected = manifest["expectedPayloads"]
        if _expected_payloads_ok(expected, st.declared_attacks):
            st.expected_payloads = expected
        else:
            out.add("manifest-expected-payloads-malformed")


def _check_rows_setup(st: _State, out: _Outcome) -> None:
    if "attackResults" not in st.pred:
        out.add("statement-malformed")
    rows = st.pred.get("attackResults")
    rows = rows if isinstance(rows, list) else []
    st.rows = [r for r in rows if isinstance(r, dict)]
    st.has_substrate = any(r.get("basis") == "substrate" for r in st.rows)


def _check_subject_cardinality(st: _State, out: _Outcome) -> None:
    subject = st.stmt.get("subject")
    subject = subject if isinstance(subject, list) else []
    if len(subject) != 1:
        out.add("subject-cardinality")


def _coverage_partition_ok(manifest_classes: dict, assessed, oos: dict, routed: dict) -> bool:
    try:
        acct: dict = {}
        for c in assessed:
            acct[c] = acct.get(c, 0) + 1
        for c in oos:
            acct[c] = acct.get(c, 0) + 1
        for c in routed:
            acct[c] = acct.get(c, 0) + 1
    except TypeError:
        return False
    return all(n == 1 and c in manifest_classes for c, n in acct.items()) and all(
        acct.get(c, 0) == 1 for c in manifest_classes
    )


def _check_coverage(st: _State, out: _Outcome) -> None:
    coverage = st.pred.get("coverage")
    st.coverage = coverage
    if not isinstance(coverage, dict):
        out.add("coverage-missing")
        return
    manifest_classes = st.manifest_classes
    if manifest_classes is None:
        return
    assessed = coverage.get("assessedClasses")
    assessed = assessed if isinstance(assessed, list) else []
    oos = coverage.get("outOfScope")
    oos = oos if isinstance(oos, dict) else {}
    routed = coverage.get("routedElsewhere")
    routed = routed if isinstance(routed, dict) else {}
    if not _coverage_partition_ok(manifest_classes, assessed, oos, routed):
        out.add("coverage-incomplete")
    attack_class: dict = {}
    for cls, ids in manifest_classes.items():
        for aid in ids if isinstance(ids, list) else []:
            try:
                attack_class.setdefault(aid, cls)
            except TypeError:
                continue
    expected_ids: set = set()
    for cls in assessed:
        try:
            ids = manifest_classes.get(cls)
        except TypeError:
            ids = None
        for aid in ids if isinstance(ids, list) else []:
            try:
                expected_ids.add(aid)
            except TypeError:
                continue
    row_ids: set = set()
    known_row_ids: set = set()
    for r in st.rows:
        aid = r.get("attackId")
        try:
            duplicate = aid in row_ids
            row_ids.add(aid)
        except TypeError:
            duplicate = False
        if duplicate:
            out.add("statement-malformed")
        try:
            known = aid in attack_class
        except TypeError:
            known = False
        if not known:
            out.add("row-attack-unknown")
        else:
            known_row_ids.add(aid)
            if attack_class[aid] not in assessed:
                out.add("coverage-incomplete")
    if expected_ids - known_row_ids:
        out.add("coverage-incomplete")


def _check_per_row(st: _State, out: _Outcome) -> None:
    for r in st.rows:
        for member in ("attackId", "containmentObserved", "basis", "method", "actualLayer"):
            if member in r and not isinstance(r[member], str):
                out.add("statement-malformed")
    for r in st.rows:
        if "actualLayer" not in r:
            out.add("malformed-missing-actual-layer")
    if st.labels is not None and st.caught is not None:
        for r in st.rows:
            lab = r.get("containmentObserved")
            if (
                lab in st.labels
                and lab not in st.caught
                and "actualLayer" in r
                and r.get("actualLayer") != "none"
            ):
                out.add("clean-row-layer-not-none")


def _check_binding_inputs(st: _State, out: _Outcome) -> None:
    if not st.has_substrate:
        return
    subject = st.stmt.get("subject")
    subject = subject if isinstance(subject, list) else []
    subj_digest = _digest_of(subject[0]) if subject else None
    if subject and subj_digest is None:
        out.add("subject-sha256-missing")
    if "runEntropy" not in st.env:
        out.add("run-entropy-missing")
    for val in (
        subj_digest,
        _digest_of(st.env.get("substrate")),
        _digest_of(st.env.get("corpus")),
        _digest_of(st.env.get("catchPolicy")),
        _digest_of(st.env.get("networkPosture")),
        _digest_of(st.env.get("runEntropy")),
    ):
        if val is not None and not _is_hex64_lower(val):
            out.add("digest-not-canonical")


def _check_fail_closed(st: _State, out: _Outcome) -> None:
    for i, r in enumerate(st.rows):
        lab_bad = st.labels is not None and r.get("containmentObserved") not in st.labels
        basis_bad = r.get("basis") not in ("substrate", "artifact")
        method_bad = r.get("method") not in ("intercepted", "reconstructed")
        attribution_bad = r.get("attribution") not in ("pinned", "paired")
        if lab_bad or basis_bad or method_bad or attribution_bad:
            st.fail_closed.add(i)
            if r.get("basis") == "substrate":
                out.add("fail-closed-substrate-row")


def _check_records(st: _State, out: _Outcome) -> None:
    records = st.pred.get("observationRecords")
    st.has_records = isinstance(records, list) and len(records) > 0
    views: list = []
    if isinstance(records, list) and records:
        views = [_RecordView(i, rec) for i, rec in enumerate(records)]
        if any(v.signature_count == 0 for v in views):
            out.add("record-signatures-empty")
        if any(v.decode_err for v in views):
            # An undecodable record contributes no leaf, so the batch-root
            # check is skipped; the duplicate scan is not.
            out.add("record-undecodable")
        else:
            root = st.pred.get("batchRoot")
            if root is None:
                out.add("batch-root-missing")
            elif all(v.pae is not None for v in views):
                if merkle.root_from_data([v.pae for v in views]) != root:
                    out.add("batch-root-mismatch")
            else:
                out.add("batch-root-mismatch")
        seen: set = set()
        for v in views:
            if v.decode_err:
                continue
            key = v.pae if v.pae is not None else _jcs_dumps_safe(v.raw)
            if key in seen:
                out.add("duplicate-record")
            seen.add(key)
    elif st.pred.get("batchRoot") is not None:
        out.add("batch-root-orphaned")
    st.views = views


def _check_run_binding(st: _State, out: _Outcome) -> None:
    derived = None
    if st.has_substrate:
        try:
            subject_sha = st.stmt["subject"][0]["digest"]["sha256"]
        except (KeyError, IndexError, TypeError):
            subject_sha = None
            derived = None
        else:
            derived = _derive_run_binding(st.env, subject_sha)
    st.derived = derived


def _covers_nothing_code(usable):
    """The covers-nothing code of the first resolved record whose kind
    covers nothing: a registered non-covering kind under its own name, any
    other kind as unknown. Reference order; no ranking between them."""
    for rv in usable:
        registered = REGISTERED_NONCOVERING.get(rv.kind or "")
        if registered is not None:
            return registered
        if rv.kind not in COVERING_KINDS:
            return "record-kind-unknown-covers-nothing"
    return None


def _check_payload(out: _Outcome, rv: _RecordView, derived) -> None:
    if not rv.media_ok:
        out.add("payload-media-type")
    if rv.payload_error is not None:
        out.add(rv.payload_error)
        return
    if rv.payload is None:
        out.add("payload-not-canonical")
        return
    if any(m not in rv.payload for m in RESERVED_MEMBERS):
        out.add("payload-missing-reserved")
    if (
        derived is not None
        and "aeeRunBinding" in rv.payload
        and rv.payload["aeeRunBinding"] != derived
    ):
        out.add("run-binding-mismatch")


def _class_match(st: _State, out: _Outcome, row: dict, usable, pinned_posture):
    covers_nothing = _covers_nothing_code(usable)
    fallback = covers_nothing  # None when every kind covers

    def uncovered(specific: str) -> str:
        return fallback if fallback is not None else specific

    lab = row.get("containmentObserved")
    method = row.get("method")
    if method == "reconstructed":
        exams = [rv for rv in usable if rv.kind == "examination"]
        good = [rv for rv in exams if _examination_ok(rv)]
        if not exams:
            out.add(uncovered("reconstructed-row-uncovered"))
        elif not good:
            out.add("examination-covers-nothing")
        return good
    if st.caught is not None and lab in st.caught:
        inters = [rv for rv in usable if rv.kind == "interception"]
        if not inters:
            out.add(uncovered("caught-row-uncovered"))
            return inters
        good = []
        for rv in inters:
            values = (rv.payload or {}).get("aeePayloadCommitment")
            if values is None:
                out.add("payload-missing-reserved")
            elif not _commitment_array_ok(values):
                out.add("payload-commitment-malformed")
            else:
                good.append(rv)
        return good
    # Clean row: needs a valid arming AND a valid sealed record.
    armings = [rv for rv in usable if rv.kind == "arming"]
    good_arm = [
        rv for rv in armings if _arming_ok(rv, pinned_posture, st.issued_at, st.declared_attacks)
    ]
    if not armings:
        out.add(uncovered("clean-row-uncovered"))
    elif not good_arm:
        out.add("arming-covers-nothing")
    sealeds = [rv for rv in usable if rv.kind == "sealed"]
    arming_postures = [
        posture
        for rv in usable
        if rv.kind == "arming"
        for posture in [(rv.payload or {}).get("aeePostureDigest")]
        if isinstance(posture, str)
    ]
    good_seal = [
        rv
        for rv in sealeds
        if _sealed_ok(rv, pinned_posture, arming_postures, st.declared_attacks)
    ]
    if not sealeds:
        out.add(uncovered("clean-row-uncovered"))
    elif not good_seal:
        out.add("sealed-covers-nothing")
    return good_arm + good_seal


def _gate1_row(st: _State, out: _Outcome, i: int, row: dict, pinned_posture) -> None:
    if row.get("basis") != "substrate" or i in st.fail_closed:
        return
    if not st.has_records:
        out.add("records-absent")
        return
    refs = row.get("observationRefs")
    if not isinstance(refs, list) or len(refs) == 0:
        out.add("refs-empty")
        lab = row.get("containmentObserved")
        if st.caught is not None and lab in st.caught:
            out.add("caught-row-uncovered")
        return
    ref_views = []
    refs_ok = True
    for ref in refs:
        if isinstance(ref, bool) or not isinstance(ref, int) or ref < 0:
            out.add("ref-malformed")
            refs_ok = False
        elif ref >= len(st.views):
            out.add("ref-out-of-range")
            refs_ok = False
        else:
            ref_views.append(st.views[ref])
    if not refs_ok and not ref_views:
        return
    for rv in ref_views:
        _check_payload(out, rv, st.derived)
    usable = [rv for rv in ref_views if rv.payload is not None and rv.media_ok]
    covering = _class_match(st, out, row, usable, pinned_posture)
    st.row_covering[i] = covering
    if covering:
        methods = [METHOD_ORDER[rv.method] for rv in covering if rv.method in METHOD_ORDER]
        method = row.get("method")
        if methods and method in METHOD_ORDER and METHOD_ORDER[method] > min(methods):
            out.add("method-cap-exceeded")


def _check_gate1(st: _State, out: _Outcome) -> None:
    st.pinned_posture = _digest_of(st.env.get("networkPosture"))
    if st.has_records:
        n = len(st.views)
        for r in st.rows:
            refs = r.get("observationRefs")
            if not isinstance(refs, list):
                continue
            hit = False
            for ref in refs:
                if isinstance(ref, bool) or not isinstance(ref, int):
                    continue
                if ref >= n:
                    out.add("ref-out-of-range")
                    hit = True
                    break
            if hit:
                break
    for i, r in enumerate(st.rows):
        _gate1_row(st, out, i, r, st.pinned_posture)


def _resolved_views(st: _State, row: dict):
    refs = row.get("observationRefs")
    if not isinstance(refs, list):
        return []
    return [
        st.views[ref]
        for ref in refs
        if not isinstance(ref, bool) and isinstance(ref, int) and 0 <= ref < len(st.views)
    ]


def _check_commitments(st: _State, out: _Outcome) -> None:
    # Clean row resolving an interception (every row, any basis).
    if st.labels is not None and st.caught is not None:
        for r in st.rows:
            lab = r.get("containmentObserved")
            if lab not in st.labels or lab in st.caught:
                continue
            if any(rv.kind == "interception" for rv in _resolved_views(st, r)):
                out.add("clean-row-contradicted")
                break
    # Every carried interception resolved by some caught row.
    if st.caught is not None and st.has_records:
        resolved = set()
        for r in st.rows:
            if r.get("containmentObserved") not in st.caught:
                continue
            resolved.update(rv.idx for rv in _resolved_views(st, r))
        for rv in st.views:
            if rv.kind == "interception" and rv.idx not in resolved:
                out.add("interception-record-orphaned")
                break
    _commit_attribution(st, out)
    if not st.has_substrate or not st.has_records:
        return
    _commit_observed_set(st, out)
    _commit_sealed_present(st, out)
    _commit_carried_cover(st, out)
    _commit_seal_attacks(st, out)
    _commit_assessed_subset(st, out)


def _commit_attribution(st: _State, out: _Outcome) -> None:
    expected_map = st.expected_payloads if isinstance(st.expected_payloads, dict) else {}
    for r in st.rows:
        if r.get("attribution") != "pinned":
            continue
        inters = [rv for rv in _resolved_views(st, r) if rv.kind == "interception"]
        if not inters:
            out.add("attribution-pinned-recordless")
            return
        try:
            expected = expected_map.get(r.get("attackId"))
        except TypeError:
            expected = None
        if not isinstance(expected, list) or not expected:
            out.add("attribution-unpinnable")
            return
        for rv in inters:
            values = (rv.payload or {}).get("aeePayloadCommitment")
            if not isinstance(values, list):
                continue
            if not any(v in expected for v in values):
                out.add("attribution-pin-unmatched")
                return


def _commit_observed_set(st: _State, out: _Outcome) -> None:
    want = None
    for rv in st.views:
        if rv.kind != "sealed" or not isinstance(rv.payload, dict):
            continue
        if rv.payload.get("aeeRunBinding") != st.derived:
            continue
        got = rv.payload.get("aeeObservedSet")
        if not _is_hex64_lower(got):
            continue
        if want is None:
            want = _observed_set_digest(st.views)
        if got != want:
            out.add("observed-set-mismatch")
            return


def _commit_sealed_present(st: _State, out: _Outcome) -> None:
    arming_postures = [
        posture
        for rv in st.views
        if rv.kind == "arming"
        for posture in [(rv.payload or {}).get("aeePostureDigest")]
        if isinstance(posture, str)
    ]
    for rv in st.views:
        if rv.kind != "sealed" or not isinstance(rv.payload, dict) or not rv.media_ok:
            continue
        if rv.payload.get("aeeRunBinding") != st.derived:
            continue
        if _sealed_ok(rv, st.pinned_posture, arming_postures, st.declared_attacks):
            return
    out.add("sealed-record-absent")


def _carried_fault(rv: _RecordView, st: _State):
    if rv.kind == "sealed":
        return None if _sealed_ok(rv, st.pinned_posture, [], st.declared_attacks) else "sealed-covers-nothing"
    if rv.kind == "arming":
        ok = _arming_ok(rv, st.pinned_posture, st.issued_at, st.declared_attacks)
        return None if ok else "arming-covers-nothing"
    if rv.kind == "examination":
        return None if _examination_ok(rv) else "examination-covers-nothing"
    payload = rv.payload or {}
    if "aeePayloadCommitment" in payload and not _commitment_array_ok(payload["aeePayloadCommitment"]):
        return "payload-commitment-malformed"
    if rv.method not in METHOD_ORDER or "aeePayloadCommitment" not in payload:
        return "payload-missing-reserved"
    return None


def _commit_carried_cover(st: _State, out: _Outcome) -> None:
    for rv in st.views:
        if not isinstance(rv.payload, dict) or not rv.media_ok:
            continue
        if any(m not in rv.payload for m in RESERVED_MEMBERS):
            continue
        if rv.payload.get("aeeRunBinding") != st.derived:
            continue
        if rv.kind not in COVERING_KINDS:
            continue
        code = _carried_fault(rv, st)
        if code is not None:
            out.add(code)


def _commit_seal_attacks(st: _State, out: _Outcome) -> None:
    if st.caught is None:
        return
    caught_ids = set()
    for r in st.rows:
        if r.get("containmentObserved") in st.caught:
            try:
                caught_ids.add(r.get("attackId"))
            except TypeError:
                continue
    for rv in st.views:
        if rv.kind != "sealed" or not isinstance(rv.payload, dict):
            continue
        if rv.payload.get("aeeRunBinding") != st.derived:
            continue
        attacks = rv.payload.get("aeeObservedAttacks")
        if not _attack_id_array_ok(attacks, st.declared_attacks):
            continue
        if any(a not in caught_ids for a in attacks):
            out.add("observed-attack-uncaught")
            return


def _commit_assessed_subset(st: _State, out: _Outcome) -> None:
    cov = st.coverage if isinstance(st.coverage, dict) else {}
    assessed_classes = cov.get("assessedClasses")
    if not isinstance(assessed_classes, list) or not isinstance(st.manifest_classes, dict):
        return
    assessed: set = set()
    for cls in assessed_classes:
        try:
            ids = st.manifest_classes.get(cls)
        except TypeError:
            ids = None
        if isinstance(ids, list):
            assessed.update(a for a in ids if isinstance(a, str))
    for rv in st.views:
        if rv.kind != "arming" or not isinstance(rv.payload, dict):
            continue
        if rv.payload.get("aeeRunBinding") != st.derived:
            continue
        declared = rv.payload.get("aeeAssessedAttacks")
        if not _attack_id_array_ok(declared, st.declared_attacks):
            continue
        if not assessed <= set(declared):
            out.add("assessed-set-exceeds-declaration")
            return


def _recompute(rows, labels, caught, coverage) -> str:
    """``result`` as a pure function of the carried rows and coverage: the
    minimum of the fail / degraded / pass_indirect conditions."""
    forces_fail = False
    indirect = False
    for r in rows:
        lab = r.get("containmentObserved")
        if lab not in labels or lab in caught:
            forces_fail = True
        elif r.get("basis") not in ("substrate", "artifact"):
            forces_fail = True
        elif r.get("method") not in ("intercepted", "reconstructed"):
            forces_fail = True
        elif r.get("attribution") not in ("pinned", "paired"):
            forces_fail = True
        elif r.get("basis") != "substrate" or r.get("method") != "intercepted":
            indirect = True
    cov = coverage if isinstance(coverage, dict) else {}
    candidates = [
        "fail" if forces_fail else "pass",
        "degraded" if (cov.get("outOfScope") or cov.get("routedElsewhere")) else "pass",
        "pass_indirect" if indirect else "pass",
    ]
    return min(candidates, key=RESULT_ORDER.__getitem__)


def _check_recompute(st: _State, out: _Outcome) -> None:
    # Total function, compared only when a result member is carried at all
    # (its absence is already result-vocabulary's fault to name).
    if "result" not in st.pred:
        return
    recomputed = _recompute(
        st.rows,
        st.labels if st.labels is not None else [],
        st.caught if st.caught is not None else [],
        st.coverage,
    )
    if not isinstance(st.result, str) or st.result not in RESULT_ORDER or recomputed != st.result:
        out.add("result-recompute-mismatch")


def _derive_tiers(st: _State, pinned_pubs):
    tiers = []
    for i, r in enumerate(st.rows):
        if r.get("basis") == "artifact":
            tiers.append("declared")
            continue
        if not pinned_pubs:
            tiers.append("unattested")
            continue
        covering = st.row_covering.get(i, [])
        if covering and all(_record_verifies(rv, pinned_pubs) for rv in covering):
            tiers.append("attested")
        else:
            tiers.append("unattested")
    return tiers


# ---------------------------------------------------------------------------
# Contract surface: statement / file entry points and the CLI
# ---------------------------------------------------------------------------


def _run_pipeline(stmt, pinned_pubs):
    """Run every gate over a decoded statement; returns (outcome, state)."""
    out = _Outcome()
    st = _State(stmt)
    try:
        if _check_statement_type(st, out):
            return out, st
        _check_wellformed(st, out)
        _check_vocabulary(st, out)
        _check_corpus(st, out)
        _check_rows_setup(st, out)
        _check_subject_cardinality(st, out)
        _check_coverage(st, out)
        _check_per_row(st, out)
        _check_binding_inputs(st, out)
        _check_fail_closed(st, out)
        _check_records(st, out)
        _check_run_binding(st, out)
        _check_gate1(st, out)
        _check_commitments(st, out)
        _check_recompute(st, out)
    except Exception:
        # Fail-closed: hostile input that breaks a check mid-flight is an
        # invalid statement carrying whatever codes were already earned.
        if not out.codes:
            out.add("statement-malformed")
    return out, st


def _report(out: _Outcome, st: _State, pinned_pubs) -> dict:
    if out.invalid:
        return {"verdict": "invalid", "codes": list(out.codes)}
    return {
        "verdict": "valid",
        "codes": [],
        "result": st.result,
        "tiers": _derive_tiers(st, pinned_pubs),
    }


def verify_statement(stmt, raw: bytes | None = None, pinned_pubs=()) -> dict:
    """Verify one decoded statement (optionally with its raw bytes, which
    the strict pass needs) and return the rail report dict."""
    if raw is not None and _statement_strict_fault(raw):
        return {"verdict": "invalid", "codes": ["statement-malformed"]}
    out, st = _run_pipeline(stmt, list(pinned_pubs))
    return _report(out, st, list(pinned_pubs))


def _load_pinned_pubs() -> list:
    """Consumer key policy from ``AEE_SUBSTRATE_KEYS``: a path to
    ``{"substrateObservationKeys": [{"keyid", "publicKeyHex"}]}``. Absent
    or unreadable policy means no pinned keys (every substrate row is
    unattested); the carried keyid is never consulted."""
    path = os.environ.get(KEY_POLICY_ENV)
    if not path:
        return []
    try:
        with open(path, "rb") as f:
            data = json.loads(f.read().decode("utf-8"))
    except Exception:
        return []
    entries = data.get("substrateObservationKeys") if isinstance(data, dict) else None
    pubs = []
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            hexkey = entry.get("publicKeyHex")
            if not isinstance(hexkey, str):
                continue
            try:
                pubs.append(bytes.fromhex(hexkey))
            except ValueError:
                continue
    return pubs


def verify_file(path: str) -> dict:
    """Verify one statement file and return the rail report dict."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return {"verdict": "invalid", "codes": ["statement-malformed"]}
    pubs = _load_pinned_pubs()
    if _statement_strict_fault(raw):
        return {"verdict": "invalid", "codes": ["statement-malformed"]}
    try:
        stmt = json.loads(raw.decode("utf-8"))
    except Exception:
        return {"verdict": "invalid", "codes": ["statement-malformed"]}
    out, st = _run_pipeline(stmt, pubs)
    return _report(out, st, pubs)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(json.dumps({"verdict": "invalid", "codes": ["statement-malformed"]}))
        return 1
    try:
        report = verify_file(args[0])
    except Exception:
        report = {"verdict": "invalid", "codes": ["statement-malformed"]}
    print(json.dumps(report))
    return 0 if report.get("verdict") == "valid" else 1


if __name__ == "__main__":
    sys.exit(main())
