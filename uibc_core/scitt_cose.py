#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read a SCITT/COSE Transparent Statement under the aee-scitt-cose/v0.1 profile.

Why this exists
---------------
`cose_min.py` verifies the COSE_Sign1 shape this repository emits: deterministic
CBOR, one algorithm, EdDSA(-8), the key carried in the protected kid, no tags.
That is enough to check our own seals and not enough to read someone else's.

The strongest public corpus in this space (`probityai/agent-evidence-vectors`,
`corpora/vectors-scitt-cose`, 27 members) ships tagged COSE_Sign1 messages that
carry CWT claims, an observer position at a private-use label, and RFC 9942
receipts with inclusion proofs. Our verifier answered every one of those 27 with
"unreadable", which their external rail scored as `external-output-absent`. An
unreadable input is not a verdict, and a verifier that cannot read the format an
international profile names has no interop story to tell.

So this module is a reader, not a writer. It is deliberately independent: it
re-derives the inclusion root with its own RFC 9162 walk instead of importing
`merkle.py` or the corpus' own tree code, because a verifier that shares
arithmetic with the routine that built the inputs cannot disagree with them.

What it enforces, in the order the profile's Section 6 gives:

  1. tagged COSE_Sign1 (tag 18), protected header in RFC 8949 Section 4.2.1
     deterministic form (shortest-form arguments, map keys in bytewise order,
     no duplicate key);
  2. `crit` names only protected labels, only labels this profile defines, and
     includes -70001 whenever the observer position is present;
  3. `alg` is -19; -8 and -7 are refused by identifier before the signature is
     touched;
  4. kid resolves to exactly one trusted key; the signature verifies over the
     payload reattached from out of band where the wire form detaches it;
  5. CWT claims appear once across both buckets, carry iss and sub, `sub` is the
     digest the in-toto subject carries, `iss` is the identity bound to the key
     that verified;
  6. exp / nbf against the statement's fixed verification time;
  7. the entry is the statement with label 394 removed; each receipt must
     declare vds 1, carry an inclusion proof, and verify over the root
     recomputed from that proof;
  8. at least one receipt completed stage 7.

Every refusal carries a code, so a caller can say *what* was wrong instead of
"invalid". The codes follow the corpus' vocabulary where the check is the same
check in both implementations; where ours differs, the code says so plainly.

This module is not a general CBOR library. It reads what the profile puts on
the wire and refuses the rest with a reason. No third-party imports.
"""

import hashlib
import json

from . import ed25519

# --- COSE / CWT / receipt labels (RFC 9052, RFC 9597, RFC 9942) -------------
LBL_ALG = 1
LBL_CRIT = 2
LBL_CONTENT_TYPE = 3
LBL_KID = 4
LBL_CWT_CLAIMS = 15
LBL_TYP = 16
LBL_RECEIPTS = 394
LBL_VDS = 395
LBL_VDP = 396
LBL_OBSERVER_POSITION = -70001

CWT_ISS = 1
CWT_SUB = 2
CWT_EXP = 4
CWT_NBF = 5

PROOF_INCLUSION = -1
ALG_ED25519 = -19
ALG_EDDSA_DEPRECATED = -8
ALG_ES256_DEPRECATED = -7
VDS_RFC9162_SHA256 = 1
COSE_SIGN1_TAG = 18
CONTENT_TYPE = "application/x.aee-scitt-cose-statement+cose"
TYP = "aee-scitt-cose/v0.1"
PROFILE = "aee-scitt-cose/v0.1"


class CborError(ValueError):
    """Input outside what this reader accepts. Always a refusal, never a guess."""


# --------------------------------------------------------------------------
# A span-carrying CBOR reader
# --------------------------------------------------------------------------
# The bytes matter here: the entry a receipt proves inclusion of is rebuilt
# byte-for-byte from the parsed spans, and the deterministic-encoding check
# compares raw key encodings rather than decoded values. A value-only decoder
# throws away exactly what this profile requires a verifier to look at.


class Node:
    """One decoded CBOR item, with the byte range it occupied."""

    __slots__ = ("major", "value", "start", "end", "items", "pairs", "tag", "_raw")

    def __init__(self, major, value, start, end, items=None, pairs=None, tag=None):
        self.major = major
        self.value = value        # scalar: int/bytes/str/bool/None
        self.start = start
        self.end = end
        self.items = items        # array members
        self.pairs = pairs        # map [(key_node, value_node)]
        self.tag = tag            # tag number when major == 6


def _head(data, pos):
    if pos >= len(data):
        raise CborError("truncated head")
    b = data[pos]
    major = b >> 5
    ai = b & 0x1F
    pos += 1
    if ai < 24:
        return major, ai, pos
    if ai == 24:
        if pos + 1 > len(data):
            raise CborError("truncated uint8 argument")
        return major, data[pos], pos + 1
    if ai == 25:
        if pos + 2 > len(data):
            raise CborError("truncated uint16 argument")
        return major, int.from_bytes(data[pos:pos + 2], "big"), pos + 2
    if ai == 26:
        if pos + 4 > len(data):
            raise CborError("truncated uint32 argument")
        return major, int.from_bytes(data[pos:pos + 4], "big"), pos + 4
    if ai == 27:
        if pos + 8 > len(data):
            raise CborError("truncated uint64 argument")
        return major, int.from_bytes(data[pos:pos + 8], "big"), pos + 8
    raise CborError("indefinite length or reserved additional-info %d is out of "
                    "scope for this reader" % ai)


def parse(data, pos=0):
    """Decode one item; return (Node, next_pos)."""
    start = pos
    major, val, pos = _head(data, pos)
    if major == 0:
        return Node(major, val, start, pos), pos
    if major == 1:
        return Node(major, -1 - val, start, pos), pos
    if major == 2:
        end = pos + val
        if end > len(data):
            raise CborError("truncated byte string")
        return Node(major, data[pos:end], start, end), end
    if major == 3:
        end = pos + val
        if end > len(data):
            raise CborError("truncated text string")
        try:
            text = data[pos:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CborError("text string is not valid utf-8: %s" % exc)
        return Node(major, text, start, end), end
    if major == 4:
        items = []
        for _ in range(val):
            item, pos = parse(data, pos)
            items.append(item)
        return Node(major, None, start, pos, items=items), pos
    if major == 5:
        pairs = []
        for _ in range(val):
            k, pos = parse(data, pos)
            v, pos = parse(data, pos)
            pairs.append((k, v))
        return Node(major, None, start, pos, pairs=pairs), pos
    if major == 6:
        inner, pos = parse(data, pos)
        return Node(major, None, start, pos, items=[inner], tag=val), pos
    if major == 7:
        if val == 20:
            return Node(major, False, start, pos), pos
        if val == 21:
            return Node(major, True, start, pos), pos
        if val == 22:
            return Node(major, None, start, pos), pos
        raise CborError("unsupported simple value %d (floats not supported)" % val)
    raise CborError("unsupported major type %d" % major)


def loads(data):
    node, end = parse(data, 0)
    if end != len(data):
        raise CborError("trailing bytes after the object: %d" % (len(data) - end))
    return node


def to_python(node):
    """Turn a Node into plain Python values (dicts, lists, scalars)."""
    if node.major == 0 or node.major == 1:
        return node.value
    if node.major in (2, 3):
        return node.value
    if node.major == 4:
        return [to_python(n) for n in node.items]
    if node.major == 5:
        out = {}
        for k, v in node.pairs:
            key = to_python(k)
            if isinstance(key, (list, dict)):
                raise CborError("unhashable map key")
            out[key] = to_python(v)
        return out
    if node.major == 6:
        # A tag inside the payload is data, not structure; keep it visible.
        return {"__cbor_tag__": node.tag, "value": to_python(node.items[0])}
    return node.value


def _shortest(ai_value, arg) -> bool:
    """True when the argument uses the shortest form RFC 8949 4.2.1 requires."""
    if ai_value < 24:
        return True
    if arg < 24:
        return False
    if arg < 1 << 8:
        return ai_value == 24
    if arg < 1 << 16:
        return ai_value == 25
    if arg < 1 << 32:
        return ai_value == 26
    return ai_value == 27


def _scan_deterministic(data, node):
    """Check RFC 8949 Section 4.2.1 over this subtree.

    Shortest-form arguments at every head, and each map's keys in bytewise
    order of their encoded bytes with no key repeated. Returns a reason string,
    or "" when the subtree conforms.
    """
    if node.major in (0, 1, 2, 3, 4, 5, 6):
        major = node.major
        # re-read the head of this item to compare the form it used
        b = data[node.start]
        ai = b & 0x1F
        if major in (0, 1):
            arg = node.value if major == 0 else -1 - node.value
            if arg < 0:
                return "negative integer encoded as its own magnitude"
            if not _shortest(ai, arg):
                return "integer %d is not encoded in shortest form" % arg
        else:
            arg = None
            if major == 2:
                arg = len(node.value)
            elif major == 3:
                arg = len(node.value.encode("utf-8"))
            elif major == 4:
                arg = len(node.items)
            elif major == 5:
                arg = len(node.pairs)
            elif major == 6:
                arg = None
            if arg is not None and not _shortest(ai, arg):
                return "container length %d is not encoded in shortest form" % arg
        if major == 4:
            for item in node.items:
                why = _scan_deterministic(data, item)
                if why:
                    return why
        if major == 5:
            prev_key_bytes = None
            seen = set()
            for k, v in node.pairs:
                kb = data[k.start:k.end]
                if prev_key_bytes is not None and kb < prev_key_bytes:
                    return "map keys are not in bytewise order (RFC 8949 4.2.1)"
                if kb in seen:
                    return "a map key occurs twice (RFC 8949 4.2.1)"
                seen.add(kb)
                prev_key_bytes = kb
                why = _scan_deterministic(data, k) or _scan_deterministic(data, v)
                if why:
                    return why
        if major == 6:
            why = _scan_deterministic(data, node.items[0])
            if why:
                return why
    return ""


# --------------------------------------------------------------------------
# COSE_Sign1 with spans
# --------------------------------------------------------------------------

class Sign1:
    """A tagged COSE_Sign1 whose parts keep their original bytes."""

    def __init__(self, data, node):
        self.data = data
        self.node = node
        if node.major != 6 or node.tag != COSE_SIGN1_TAG:
            raise CborError("not a tagged COSE_Sign1 (CBOR tag 18)")
        body = node.items[0]
        if body.major != 4 or len(body.items) != 4:
            raise CborError("COSE_Sign1 body is not a four-element array")
        self.protected_node, self.uhdr_node, self.payload_node, self.sig_node = body.items
        if self.protected_node.major != 2:
            raise CborError("protected header must be a byte string")
        self.protected_bytes = self.protected_node.value
        if self.uhdr_node.major != 5:
            raise CborError("unprotected header must be a map")
        # An empty protected bucket is legal COSE and carries no claims; the
        # profile requires seven labels there, so an empty map simply fails the
        # label checks below rather than raising here.
        self.protected = to_python(loads(self.protected_bytes)) if self.protected_bytes else {}
        if not isinstance(self.protected, dict):
            raise CborError("protected header is not a map")
        self.uhdr = to_python(self.uhdr_node)
        self.payload = None if self.payload_node.major == 7 and self.payload_node.value is None \
            else (self.payload_node.value if self.payload_node.major == 2 else None)
        if self.payload_node.major not in (2, 7):
            raise CborError("payload must be a byte string or nil")
        if self.sig_node.major != 2:
            raise CborError("signature must be a byte string")
        self.signature = self.sig_node.value

    # -- helpers ---------------------------------------------------------
    def entry_bytes(self) -> bytes:
        """The registered entry: this object with label 394 removed.

        Rebuilt from the original spans, not re-encoded from values: any
        re-encoding risk (map order, string forms) would silently change the
        bytes a receipt's inclusion proof is over.
        """
        keep = [(k, v) for k, v in self.uhdr_node.pairs
                if not (k.major in (0, 1) and k.value == LBL_RECEIPTS)]
        if len(keep) == len(self.uhdr_node.pairs):
            return self.data[self.node.start:self.node.end]
        out = bytearray()
        # tag head: the tag we parsed is deterministic by construction
        out += b"\xd2" if COSE_SIGN1_TAG == 18 else b""
        out += b"\x84"                                   # array of 4, shortest form
        out += self.data[self.protected_node.start:self.protected_node.end]
        out += _map_bytes_from_pairs(keep)
        out += self.data[self.payload_node.start:self.payload_node.end]
        out += self.data[self.sig_node.start:self.sig_node.end]
        return bytes(out)


def _map_bytes_from_pairs(pairs) -> bytes:
    """A map header in shortest form plus each pair's original bytes."""
    n = len(pairs)
    if n < 24:
        head = bytes([0xA0 | n])
    elif n < 256:
        head = b"\xb8" + n.to_bytes(1, "big")
    else:
        head = b"\xb9" + n.to_bytes(2, "big")
    return head + b"".join(k._raw + v._raw for k, v in pairs)


def _attach_raw(sign1):
    """Give every node its own raw bytes once, for byte-exact reassembly."""
    def walk(node, data):
        node._raw = data[node.start:node.end]
        if node.items:
            for it in node.items:
                walk(it, data)
        if node.pairs:
            for k, v in node.pairs:
                walk(k, data)
                walk(v, data)
    walk(sign1.node, sign1.data)


def sign1_from_bytes(data: bytes) -> Sign1:
    node = loads(data)
    obj = Sign1(data, node)
    _attach_raw(obj)
    return obj


# --------------------------------------------------------------------------
# RFC 9162 Section 2.1 Merkle inclusion proof, independently implemented
# --------------------------------------------------------------------------

def leaf_hash(entry: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + entry).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def inclusion_root(entry: bytes, tree_size: int, leaf_index: int, path) -> bytes | None:
    """Recompute the root, or None where the proof cannot be applied.

    Follows RFC 9162 Section 2.1.3.2 literally: an index-only walk with parity
    tests is wrong on the right edge of trees whose size is not a power of two
    (it fails closed there, so a suite of reject-only members would never show
    it). Both indices are carried and shifted together.
    """
    if not isinstance(tree_size, int) or not isinstance(leaf_index, int):
        return None
    if tree_size <= 0 or leaf_index < 0 or leaf_index >= tree_size:
        return None
    fn, sn = leaf_index, tree_size - 1
    node = leaf_hash(entry)
    for sibling in path:
        if not isinstance(sibling, bytes):
            return None
        if sn == 0:
            return None
        if (fn & 1) or (fn == sn):
            node = node_hash(sibling, node)
            while (fn & 1) == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            node = node_hash(node, sibling)
        fn >>= 1
        sn >>= 1
    return node if sn == 0 else None


# --------------------------------------------------------------------------
# The verifier
# --------------------------------------------------------------------------

class Refusal(Exception):
    """A statement this profile says a verifier must refuse, with a code."""

    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _sig_structure(protected: bytes, payload: bytes) -> bytes:
    from . import cose_min
    return cose_min.encode(["Signature1", protected, b"", payload])


def _ed25519_key(spec) -> bytes:
    x = spec.get("x")
    if not isinstance(x, str):
        raise Refusal("trust-input-malformed", "trust key has no hex 'x' member")
    raw = bytes.fromhex(x)
    if len(raw) != 32:
        raise Refusal("trust-input-malformed", "trust key 'x' is not 32 bytes")
    return raw


def _receipt_root_and_header(receipt_raw: bytes, entry: bytes):
    """(root | None, status, protected header dict) for one receipt."""
    r = sign1_from_bytes(receipt_raw)
    header = r.protected
    if LBL_VDP not in r.uhdr:
        return None, "no-vdp", header
    proofs = r.uhdr[LBL_VDP]
    if not isinstance(proofs, dict) or PROOF_INCLUSION not in proofs:
        return None, "no-inclusion-proof-type", header
    proof_list = proofs[PROOF_INCLUSION]
    if not isinstance(proof_list, list) or not proof_list:
        return None, "inclusion-proof-malformed", header
    first = proof_list[0]
    if not isinstance(first, bytes):
        return None, "inclusion-proof-malformed", header
    try:
        parsed = to_python(loads(first))
    except CborError as exc:
        return None, "inclusion-proof-malformed: %s" % exc, header
    if not isinstance(parsed, list) or len(parsed) != 3:
        return None, "inclusion-proof-malformed", header
    tree_size, leaf_index, path = parsed
    if not isinstance(path, list):
        return None, "inclusion-proof-malformed", header
    root = inclusion_root(entry, tree_size, leaf_index, path)
    return (None, "proof-unapplicable", header) if root is None else (root, "applied", header)


def verify_transparent_statement(vector: dict, now: int = None):
    """Read one vector file and return our verdict.

    `vector` is the object a corpus ships: the wire bytes plus the trust inputs
    and a fixed verification time. `now` is the instant exp and nbf are judged
    against - pass it explicitly to make a run reproducible; by default the
    vector's own `verificationTime` is used, and the wall clock only when the
    vector carries none. Returns a dict with `verdict` ("valid" or "invalid"),
    `codes` (ordered list of refusal codes), and `notes` (facts a relying party
    needs, such as the observer position).

    Never raises for a bad statement: an unreadable statement is `invalid` with
    `unreadable` code, because a reader that crashes is a reader that reported
    nothing.
    """
    codes = []
    notes = []
    try:
        raw = bytes.fromhex(vector["transparentStatement"])
        detached = (bytes.fromhex(vector["detachedPayload"])
                    if vector.get("detachedPayload") is not None else None)
        statement = sign1_from_bytes(raw)
    except (KeyError, TypeError, ValueError, CborError) as exc:
        return {"verdict": "invalid", "codes": ["unreadable"], "notes": [str(exc)]}

    # Stage 1 - deterministic protected header
    why = _scan_deterministic(statement.protected_bytes, loads(statement.protected_bytes))
    if why:
        codes.append("protected-header-not-deterministic")
        notes.append(why)

    header = statement.protected
    payload = statement.payload if statement.payload is not None else detached
    if statement.payload is None and detached is None:
        codes.append("payload-absent")
        notes.append("the wire form detaches the payload and none was supplied")

    # Stage 2 - crit
    crit = header.get(LBL_CRIT)
    if crit is not None:
        if not isinstance(crit, list) or not crit:
            codes.append("critical-parameter-malformed")
            notes.append("crit is not a non-empty array (RFC 9052 3.1)")
        else:
            for label in crit:
                if label not in header:
                    codes.append("critical-parameter-unprotected")
                    notes.append("crit names %r which is not in the protected bucket" % (label,))
                elif label != LBL_OBSERVER_POSITION:
                    codes.append("critical-parameter-unprocessable")
                    notes.append("crit names %r, a label this profile does not define" % (label,))
    if LBL_OBSERVER_POSITION in header and LBL_OBSERVER_POSITION not in (crit or []):
        codes.append("observer-position-not-critical")
        notes.append("the observer position is present and crit does not name it")

    # Stage 3 - algorithm by identifier
    declared_alg = header.get(LBL_ALG)
    if declared_alg is not None and declared_alg != ALG_ED25519:
        if declared_alg == ALG_EDDSA_DEPRECATED:
            codes.append("algorithm-deprecated")
            notes.append("alg -8 is Recommended: Deprecated (RFC 9864 4.2.2)")
        elif declared_alg == ALG_ES256_DEPRECATED:
            # -7 is refused by identifier like -8, and separately it is the
            # confusion case: the bytes are a good Ed25519 signature and the
            # header names an ECDSA algorithm, so a verifier that dispatches on
            # the key type would accept a statement that says what it does not do.
            codes.append("algorithm-mismatch")
            notes.append("alg -7 is ES256 while the signature is Ed25519 "
                         "(and -7 is also Recommended: Deprecated)")
        else:
            codes.append("algorithm-mismatch")
            notes.append("alg %r is neither -19 nor a profile algorithm" % (declared_alg,))

    # Stage 4 - kid resolution and signature
    issuer_key = None
    issuer_identity = None
    kid = header.get(LBL_KID)
    trust = vector.get("trust") or {}
    matched = [issuer for issuer in (trust.get("issuers") or [])
               if isinstance(issuer, dict) and _kid_matches(issuer.get("kid"), kid)]
    if len(matched) > 1:
        matching = [i for i in matched if payload is not None and
                    ed25519.verify(_ed25519_key(i.get("key") or {}),
                                   _sig_structure(statement.protected_bytes, payload),
                                   statement.signature)]
        if len(matching) == 1:
            matched = matching
        else:
            codes.append("issuer-key-ambiguous")
            notes.append("%d trusted keys share this kid and %d verify"
                         % (len(matched), len(matching)))
    elif len(matched) == 1:
        issuer = matched[0]
        try:
            key = _ed25519_key(issuer.get("key") or {})
        except Refusal as exc:
            codes.append(exc.code)
            notes.append(exc.detail)
            key = None
        if key is not None and payload is not None:
            if ed25519.verify(key, _sig_structure(statement.protected_bytes, payload),
                              statement.signature):
                issuer_key, issuer_identity = key, issuer.get("iss")
            else:
                codes.append("signature-invalid")
                notes.append("the issuer signature does not verify under the trusted key")
    elif kid is not None:
        codes.append("issuer-key-unknown")
        notes.append("kid %r resolves to no trusted key" % (kid,))

    # Stage 5 - CWT claims, once, with both claims and both bindings
    if LBL_CWT_CLAIMS not in header:
        codes.append("cwt-claims-absent")
        notes.append("the protected header carries no CWT Claims (label 15)")
    elif LBL_CWT_CLAIMS in statement.uhdr:
        codes.append("cwt-claims-duplicated")
        notes.append("label 15 is in both buckets; RFC 9597 2 requires exactly one")
    else:
        claims = header.get(LBL_CWT_CLAIMS)
        if not isinstance(claims, dict):
            codes.append("cwt-claims-malformed")
            notes.append("CWT Claims is not a map")
        else:
            if CWT_ISS not in claims or CWT_SUB not in claims:
                codes.append("cwt-claims-incomplete")
                notes.append("CWT Claims lack iss or sub (RFC 9943 6)")
            if payload is not None:
                want_sub = _subject_claim(payload)
                if want_sub is None:
                    codes.append("subject-unreadable")
                    notes.append("the payload has no subject[0].digest.sha256 to bind sub to")
                elif claims.get(CWT_SUB) != want_sub:
                    codes.append("subject-digest-mismatch")
                    notes.append("sub is %r and the payload's subject digest is %r"
                                 % (claims.get(CWT_SUB), want_sub))
            if issuer_identity is not None and claims.get(CWT_ISS) != issuer_identity:
                codes.append("issuer-identity-mismatch")
                notes.append("iss is %r, and the key that verified belongs to %r"
                             % (claims.get(CWT_ISS), issuer_identity))
            # Stage 6 - validity window against the statement's fixed time
            if now is None:
                # A corpus may carry the instant as an epoch integer or as an
                # RFC 3339 string. `_epoch` only understands the string form, so
                # passing an integer through it returned None and the window was
                # skipped silently - a statement judged "valid" at every instant.
                fixed = vector.get("verificationTime")
                if isinstance(fixed, int) and not isinstance(fixed, bool):
                    now = fixed
                else:
                    now = _epoch(fixed)
            if now is not None:
                if CWT_EXP in claims and isinstance(claims[CWT_EXP], int) and claims[CWT_EXP] < now:
                    codes.append("statement-expired")
                    notes.append("exp %d is before the verification time %d"
                                 % (claims[CWT_EXP], now))
                if CWT_NBF in claims and isinstance(claims[CWT_NBF], int) and claims[CWT_NBF] > now:
                    codes.append("statement-not-yet-valid")
                    notes.append("nbf %d is after the verification time %d"
                                 % (claims[CWT_NBF], now))

    # Stage 7/8 - receipts and the entry
    receipts = statement.uhdr.get(LBL_RECEIPTS)
    if not isinstance(receipts, list) or not receipts:
        codes.append("receipts-absent")
        notes.append("no receipts in the unprotected header (label 394)")
    else:
        entry = statement.entry_bytes()
        verified = 0
        for receipt_raw in receipts:
            try:
                root, status, receipt_header = _receipt_root_and_header(receipt_raw, entry)
            except (CborError, ValueError) as exc:
                codes.append("receipt-unreadable")
                notes.append("a receipt does not decode: %s" % exc)
                continue
            if LBL_VDS not in receipt_header:
                codes.append("receipt-vds-absent")
                notes.append("a receipt's protected header carries no vds (label 395)")
                continue
            if receipt_header.get(LBL_VDS) != VDS_RFC9162_SHA256:
                codes.append("receipt-vds-unregistered")
                notes.append("vds %r is not 1, RFC9162_SHA256"
                             % (receipt_header.get(LBL_VDS),))
                continue
            receipt_alg = receipt_header.get(LBL_ALG)
            if receipt_alg not in (ALG_ED25519, ALG_EDDSA_DEPRECATED):
                codes.append("receipt-algorithm-mismatch")
                notes.append("a receipt declares alg %r" % (receipt_alg,))
                continue
            if root is None:
                codes.append("inclusion-proof-absent" if status == "no-vdp"
                             or status == "no-inclusion-proof-type"
                             else "inclusion-proof-unapplicable")
                notes.append("a receipt yields no root (%s)" % status)
                continue
            key = _transparency_key(trust, receipt_header.get(LBL_KID))
            if key is None:
                codes.append("receipt-key-unknown")
                notes.append("a receipt's kid resolves to no trusted transparency service")
                continue
            if ed25519.verify(key, _sig_structure(receipt_header_bytes(receipt_raw),
                                                 root), receipt_signature(receipt_raw)):
                verified += 1
            else:
                codes.append("receipt-subject-mismatch")
                notes.append("a receipt does not verify over the root its own proof "
                             "yields for this entry, so it was issued about another one")
        if verified == 0 and not codes:
            codes.append("no-receipt-verified")
            notes.append("no receipt completed stage 7")

    # Stage 8 - the observer position is read, not dropped
    position = header.get(LBL_OBSERVER_POSITION)
    if isinstance(position, dict):
        notes.append("vantage=%r observedFrom=%r reachableByObserved=%r"
                     % (position.get("vantage"), position.get("observedFrom"),
                        position.get("reachableByObserved")))
        if position.get("reachableByObserved") is True:
            notes.append("reachableByObserved is true: a self-report, not an outside observation")

    return {"verdict": "valid" if not codes else "invalid",
            "codes": sorted(set(codes)),
            "notes": notes}


def receipt_header_bytes(receipt_raw: bytes) -> bytes:
    return sign1_from_bytes(receipt_raw).protected_bytes


def receipt_signature(receipt_raw: bytes) -> bytes:
    return sign1_from_bytes(receipt_raw).signature


def _kid_matches(issuer_kid, kid) -> bool:
    if not isinstance(issuer_kid, str) or kid is None:
        return False
    try:
        return bytes.fromhex(issuer_kid) == kid
    except ValueError:
        return False


def _transparency_key(trust, kid):
    for candidate in trust.get("transparencyServices") or []:
        if _kid_matches(candidate.get("kid"), kid):
            try:
                return _ed25519_key(candidate.get("key") or {})
            except Refusal:
                return None
    return None


def _subject_claim(payload: bytes):
    try:
        statement = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    try:
        digest = statement["subject"][0]["digest"]["sha256"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(digest, str):
        return None
    return "sha256:" + digest.lower()


def _epoch(iso: str):
    """Seconds since the epoch for an RFC 3339 UTC timestamp, or None."""
    if not isinstance(iso, str):
        return None
    import datetime
    try:
        stamp = iso.replace("Z", "+00:00")
        return int(datetime.datetime.fromisoformat(stamp).timestamp())
    except ValueError:
        return None