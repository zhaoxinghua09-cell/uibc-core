"""BID (``did:bid``) protocol layer: document semantics, response codes, signing.

Why this module exists
----------------------
`did_cn.py` already implements the *read* call of 《星火·链网BID协议》 §4.2.1
(`GET http://${url}/${bid}` -> `errorCode` + `data.didDocument`). That is the
transport. What it does not do - and what the specification actually spends its
pages on - is read the document it gets back:

  * §4.2.5 defines **eleven** response codes (0..10). Collapsing all non-zero
    codes into one exception throws away the difference between "not found"
    (retry never helps), "server too busy" (retry helps), and "verify failed"
    (a security event, not a fetch error);
  * §4.2.1's document is **not** a DID Core document: it carries `publicKey`
    (with `publicKeyHex`), `authentication`, `alsoKnownAs` (with an integer
    type from appendix 1), `extension` (ttl / type / attributes / acsns /
    delegateSign), `service`, and `proof` {creator, signatureValue}. None of
    those are understood by the DID Core path;
  * §5 defines how a document is signed: strip `proof`, canonicalize exactly
    like RFC 8785 (JCS), sign the bytes, and Base58-encode the signature.

Everything here is checked against the protocol text, and every rule is
pinned by a test in ``tests/test_bid_protocol.py``. Nothing here guesses a
registry URL: the caller passes the endpoint, as §4.2.1 requires (``${url}``
is the resolver's address, which the protocol never fixes).

Deliberate limits (stated so nobody mistakes absence for oversight):

  * SM2 is verified (``uibc_core/sm2.py``) against GM/T 0003.5 Annex A's own
    worked example; the distinguisher ID and key encoding it assumes are named
    in the success reason rather than left implicit.
  * Address derivation lives in ``uibc_core/bid_address.py`` (50/50 against the
    official SDK's samples). Consistency check only - any address the ABNF
    accepts is still accepted, because derivation is not an admission rule.
  * §4.3 (binary resolution) is readable via ``uibc_core/bid_binary.py``: the
    envelope and unit tree are decoded; integer widths and signature-unit IDs
    are deferred because RFC-011 never states them. This module still refuses to
    *answer* binary requests with code 5 - we are not a binary resolver.
"""

from __future__ import annotations

import binascii
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .canonical import canonicalize
from .ed25519 import publickey as ed_public_key, sign as ed_sign, verify as ed_verify


# --------------------------------------------------------------------------
# §4.2.5 response codes
# --------------------------------------------------------------------------
#
# code -> (protocol name, handling class)
#
# The handling class is the whole point: it lets a caller decide whether to
# retry, whether to say "no such identity", or whether to treat the answer as a
# security signal. The protocol names are verbatim from §4.2.5.
BID_RESPONSE_CODES: Dict[int, Tuple[str, str]] = {
    0: ("success", "ok"),
    1: ("without permission", "refused"),
    2: ("error", "protocol"),
    3: ("server too busy", "transient"),
    4: ("protocol error", "protocol"),
    5: ("operation not supported", "protocol"),
    6: ("not found", "not_found"),
    7: ("server not response", "transient"),
    8: ("field not found", "not_found"),
    9: ("verify failed", "security"),
    10: ("nonexistent chain code info", "not_found"),
}

RETRYABLE = frozenset({"transient"})
NOT_FOUND = frozenset({"not_found"})


class BIDProtocolError(Exception):
    """Base class for everything raised by this module."""


class BIDResponseError(BIDProtocolError):
    """A registry answered with a documented (or unknown) response code.

    Carrying the number *and* the protocol's own name matters: an operator
    reading a log needs to know that "6" means "not found" rather than
    "something went wrong", and code 9 means a signature failed to verify -
    which is a security event, not a retryable transport hiccup.
    """

    def __init__(self, code: int, message: str = "", did: Optional[str] = None):
        self.code = code
        self.message = message
        self.did = did
        name, kind = BID_RESPONSE_CODES.get(code, ("undocumented code", "protocol"))
        self.name = name
        self.kind = kind
        super().__init__(
            "%s: registry answered errorCode=%d (%s)%s"
            % (did or "did:bid", code, name, (": " + str(message)) if message else "")
        )

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE

    @property
    def not_found(self) -> bool:
        return self.kind in NOT_FOUND


class BIDDocumentError(BIDProtocolError):
    """The document does not satisfy §4.2.1's field table."""


# --------------------------------------------------------------------------
# Appendix 1 type codes
# --------------------------------------------------------------------------
AKA_TYPES = {101: "BID", 102: "other DID", 103: "domain", 104: "Zid", 105: "handle"}
ATTRIBUTE_TYPES = {
    101: "person", 102: "enterprise", 103: "node", 104: "smart device",
    105: "smart contract", 201: "image", 202: "video", 203: "document",
    204: "resource data", 205: "credential", 206: "AC code", 999: "other",
}
CREDENTIAL_TYPES = {201: "trusted authentication", 202: "education", 203: "qualification", 204: "authorization"}
SERVICE_TYPES = {"DIDDecrypt", "DIDStorage", "DIDRevocation", "DIDResolver", "DIDSubResolver"}
# appendix 1, section 5: resolution transport protocol code -> name
RESOLUTION_PROTOCOLS = {0: "UDP", 1: "TCP", 2: "HTTP", 3: "HTTPS"}

_HEX_RE = re.compile(r"^[0-9a-fA-F]*$")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")

# BID public keys are carried as hex with a BIF algorithm prefix. Three widths
# occur in the wild, and the widest one is the normal case:
#
#   * 35 bytes `b0 65 66 || key` - what the official SDK emits and what the
#     protocol's own §5.4.1 example shows (`b06566f76733ae...`). The trailing
#     bytes 0x65/0x66 are the BID's own "ef" marker, not key material.
#   * 33 bytes `b0 || key` - Ed25519 with just the algorithm byte.
#   * 32 bytes `key`      - bare key material.
#
# The 35-byte form was found by asking the official SDK (`bid-sdk-nodejs` 1.0.1)
# to derive a key from a fixed seed: it answered `b06566` + the same 32 bytes we
# derived ourselves. Before that we only knew the 1-byte prefix, and would have
# refused every real document. See tests/test_bid_address_rule.py.
_KEY_PREFIXES = (b"\xb0\x65\x66", b"\xb0")
_ED25519_HEX_LEN = {64, 66, 70}


def strip_key_prefix(hexed: str):
    """(key material 32 bytes, the prefix that was removed as text)."""
    raw = bytes.fromhex(hexed)
    for prefix in _KEY_PREFIXES:
        if raw.startswith(prefix):
            return raw[len(prefix):], prefix.hex()
    return raw, ""


def _is_hex(value: str) -> bool:
    return bool(value) and _HEX_RE.match(value) is not None and len(value) % 2 == 0


# --------------------------------------------------------------------- Base58
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_encode(raw: bytes) -> str:
    """Bitcoin-alphabet Base58 (the alphabet §5.2 means by "Base58")."""
    n = int.from_bytes(raw, "big")
    out = []
    while n > 0:
        n, rem = divmod(n, 58)
        out.append(_B58_ALPHABET[rem])
    out.extend("1" for _ in range(len(raw) - len(raw.lstrip(b"\x00"))))
    return "".join(reversed(out))


def base58_decode(text: str) -> bytes:
    n = 0
    for ch in text:
        try:
            n = n * 58 + _B58_ALPHABET.index(ch)
        except ValueError:
            raise BIDDocumentError("not Base58: %r contains %r" % (text[:16], ch)) from None
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(text) - len(text.lstrip("1"))
    return b"\x00" * pad + body


# ------------------------------------------------------------ §4.2.1 envelope
def parse_bid_envelope(payload: Any, did: str) -> Dict[str, Any]:
    """Unwrap a §4.2.1 answer into the BID document, or raise with the real code.

    Accepted shapes, both seen in deployments:

        {"errorCode": 0, "data": {"didDocument": {...}}}
        {"errorCode": 0, "didDocument": {...}}
        {...document...}                     # some gateways return it bare

    A non-zero `errorCode` is raised as `BIDResponseError` carrying that number.
    An `errorCode` that is not the integer 0 (e.g. "0", or True) is rejected
    rather than coerced: the protocol defines an Int.
    """
    if not isinstance(payload, dict):
        raise BIDDocumentError("%s: registry answered with %s, not an object"
                               % (did, type(payload).__name__))
    code = payload.get("errorCode", 0)
    if isinstance(code, bool) or not isinstance(code, int):
        raise BIDResponseError(-1, "errorCode is not an integer: %r" % (code,), did)
    if code != 0:
        raise BIDResponseError(code, payload.get("message", ""), did)
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("didDocument"), dict):
        return data["didDocument"]
    if isinstance(payload.get("didDocument"), dict):
        return payload["didDocument"]
    if "id" in payload:
        return payload
    raise BIDDocumentError("%s: no didDocument in the answer" % (did,))


# ------------------------------------------------------- §4.2.1 document model
@dataclass
class BIDDocument:
    """The §4.2.1 document, parsed and validated. Fields keep their wire names."""

    id: str
    public_key: List[Dict[str, Any]] = field(default_factory=list)
    authentication: List[str] = field(default_factory=list)
    also_known_as: List[Dict[str, Any]] = field(default_factory=list)
    service: List[Dict[str, Any]] = field(default_factory=list)
    extension: Dict[str, Any] = field(default_factory=dict)
    created: Optional[str] = None
    updated: Optional[str] = None
    proof: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    # ---- helpers ---------------------------------------------------------
    @property
    def ac_code(self) -> Optional[str]:
        """The sub-chain AC code of this BID, or None on the main chain."""
        body = self.id.split("did:bid:", 1)[-1]
        if ":" in body:
            head, _, suffix = body.partition(":")
            if len(head) == 4 and suffix:
                return head
        return None

    @property
    def recovery_keys(self) -> List[str]:
        return list(self.extension.get("recovery") or [])

    @property
    def ttl(self) -> Optional[int]:
        ttl = self.extension.get("ttl")
        return ttl if isinstance(ttl, int) and not isinstance(ttl, bool) else None

    def sub_chain_service(self) -> Optional[Dict[str, Any]]:
        """§4.2.2: the service entry that points at a sub-chain resolver."""
        for entry in self.service:
            if entry.get("type") == "DIDSubResolver":
                return entry
        return None

    def key_by_id(self, key_id: str) -> Optional[Dict[str, Any]]:
        for entry in self.public_key:
            if entry.get("id") == key_id:
                return entry
        return None

    def verification_key(self, key_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """The key a proof claims, checked against `authentication`."""
        if key_id is None:
            if not self.authentication:
                return None
            key_id = self.authentication[0]
        entry = self.key_by_id(key_id)
        if entry is None:
            return None
        if self.authentication and key_id not in self.authentication:
            # keys may legitimately exist without being authorised to authenticate;
            # the proof has to name an authorised one.
            return None
        return entry

    # ---- projection ------------------------------------------------------
    def to_did_core(self) -> Dict[str, Any]:
        """Project onto a DID Core 1.0 document (one-way; the BID fields are kept
        in `extension` so nothing is lost)."""
        doc: Dict[str, Any] = {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": self.id,
        }
        if self.public_key:
            doc["verificationMethod"] = [
                {
                    "id": key["id"],
                    "type": _key_type(key.get("type")),
                    "controller": key.get("controller", self.id),
                    "publicKeyHex": key.get("publicKeyHex"),
                }
                for key in self.public_key
            ]
        if self.authentication:
            doc["authentication"] = list(self.authentication)
        if self.also_known_as:
            doc["alsoKnownAs"] = [entry.get("id") for entry in self.also_known_as]
        if self.service:
            doc["service"] = [dict(entry) for entry in self.service]
        if self.created:
            doc["created"] = self.created
        if self.updated:
            doc["updated"] = self.updated
        if self.extension:
            doc["extension"] = dict(self.extension)
        if self.proof:
            doc["proof"] = dict(self.proof)
        return doc


def _key_type(bid_type: Any) -> str:
    """BID `type` (a free-form string) -> the DID Core type we can act on."""
    text = str(bid_type or "").upper()
    if "ED25519" in text:
        return "Ed25519VerificationKey2020"
    if "SM2" in text:
        return "SM2VerificationKey"
    return str(bid_type or "UnknownVerificationKey")


def parse_bid_document(doc: Any, did: str) -> BIDDocument:
    """Validate a §4.2.1 document. Raises `BIDDocumentError` on a real violation."""
    if not isinstance(doc, dict):
        raise BIDDocumentError("%s: document is not an object" % (did,))
    if doc.get("id") != did:
        raise BIDDocumentError("%s: document id %r does not match the request"
                               % (did, doc.get("id")))

    parsed = BIDDocument(id=did, raw=doc)

    # publicKey: array of objects, ids unique, controllers are BIDs, hex payloads
    keys = doc.get("publicKey", [])
    if not isinstance(keys, list):
        raise BIDDocumentError("%s: publicKey must be an array" % (did,))
    seen = set()
    for entry in keys:
        if not isinstance(entry, dict):
            raise BIDDocumentError("%s: publicKey entry is not an object" % (did,))
        key_id = entry.get("id")
        if not isinstance(key_id, str) or "#" not in key_id:
            raise BIDDocumentError("%s: publicKey.id must be a #key id, got %r" % (did, key_id))
        if key_id in seen:
            raise BIDDocumentError("%s: duplicate publicKey.id %r" % (did, key_id))
        seen.add(key_id)
        controller = entry.get("controller")
        if controller is not None and not str(controller).startswith("did:bid:"):
            raise BIDDocumentError("%s: publicKey.controller %r is not a BID" % (did, controller))
        hexed = entry.get("publicKeyHex")
        if hexed is None:
            parsed.warnings.append("publicKey %s carries no publicKeyHex" % (key_id,))
        elif not _is_hex(str(hexed)):
            raise BIDDocumentError("%s: publicKeyHex is not hex: %r" % (did, str(hexed)[:16]))
        elif len(str(hexed)) not in _ED25519_HEX_LEN and str(entry.get("type", "")).upper() == "ED25519":
            parsed.warnings.append(
                "publicKey %s: Ed25519 key is %d hex chars; the real forms are 64 (bare), 66 (b0-prefixed) or 70 (b06566-prefixed)"
                % (key_id, len(str(hexed))))
    parsed.public_key = keys

    auth = doc.get("authentication", [])
    if not isinstance(auth, list):
        raise BIDDocumentError("%s: authentication must be an array" % (did,))
    for ref in auth:
        if not isinstance(ref, str):
            raise BIDDocumentError("%s: authentication entry %r is not a string" % (did, ref))
        if ref not in seen:
            raise BIDDocumentError("%s: authentication names %r, which no publicKey defines"
                                   % (did, ref))
    parsed.authentication = auth

    aka = doc.get("alsoKnownAs", [])
    if not isinstance(aka, list):
        raise BIDDocumentError("%s: alsoKnownAs must be an array" % (did,))
    for entry in aka:
        if not isinstance(entry, dict):
            raise BIDDocumentError("%s: alsoKnownAs entry is not an object" % (did,))
        kind = entry.get("type")
        if not isinstance(kind, int) or isinstance(kind, bool):
            raise BIDDocumentError("%s: alsoKnownAs.type must be an Int (appendix 1), got %r"
                                   % (did, kind))
        if kind not in AKA_TYPES:
            parsed.warnings.append("alsoKnownAs.type %r is not in appendix 1 (extensible)" % (kind,))
    parsed.also_known_as = aka

    svc = doc.get("service", [])
    if not isinstance(svc, list):
        raise BIDDocumentError("%s: service must be an array" % (did,))
    for entry in svc:
        if not isinstance(entry, dict):
            raise BIDDocumentError("%s: service entry is not an object" % (did,))
        if not entry.get("id") or not entry.get("type"):
            raise BIDDocumentError("%s: service entry needs id and type" % (did,))
        if entry.get("type") not in SERVICE_TYPES:
            parsed.warnings.append("service type %r is not in appendix 1 (extensible)" % (entry.get("type"),))
        if entry.get("type") == "DIDSubResolver":
            # §4.2.2: the sub-chain entry is the one with address *and* transport
            if not entry.get("serviceEndpoint"):
                raise BIDDocumentError("%s: DIDSubResolver entry has no serviceEndpoint" % (did,))
            proto = entry.get("protocol")
            if proto is not None and proto not in RESOLUTION_PROTOCOLS:
                raise BIDDocumentError("%s: service.protocol %r is not 0..3 (appendix 1)"
                                       % (did, proto))
    parsed.service = svc

    ext = doc.get("extension", {})
    if not isinstance(ext, dict):
        raise BIDDocumentError("%s: extension must be an object" % (did,))
    ttl = ext.get("ttl")
    if ttl is not None and (not isinstance(ttl, int) or isinstance(ttl, bool) or ttl < 0):
        raise BIDDocumentError("%s: extension.ttl must be a non-negative Int, got %r" % (did, ttl))
    kind = ext.get("type")
    if kind is not None and not isinstance(kind, int):
        raise BIDDocumentError("%s: extension.type must be an Int (appendix 1), got %r" % (did, kind))
    if isinstance(kind, int) and kind not in ATTRIBUTE_TYPES:
        parsed.warnings.append("extension.type %r is not in appendix 1 (extensible)" % (kind,))
    for attr in ext.get("attributes") or []:
        if not isinstance(attr, dict) or "key" not in attr or "value" not in attr:
            raise BIDDocumentError("%s: attribute entries need key and value" % (did,))
        enc = attr.get("encrypt", 0)
        if enc not in (0, 1):
            raise BIDDocumentError("%s: attribute.encrypt must be 0 or 1, got %r" % (did, enc))
    for vc in ext.get("verifiableCredentials") or []:
        if not isinstance(vc, dict) or "id" not in vc:
            raise BIDDocumentError("%s: verifiableCredential entries need id" % (did,))
        cred_type = vc.get("type")
        if cred_type is not None and cred_type not in CREDENTIAL_TYPES:
            parsed.warnings.append("credential type %r is not in appendix 1 (extensible)" % (cred_type,))
    parsed.extension = ext

    # §4.2.1 items 9.created / 10.updated are "必填字段" in the text, so absence
    # is a violation, not a missing optional - the probe found this by deleting
    # the field and watching the document parse cleanly.
    for name, item in (("created", "9.created"), ("updated", "10.updated")):
        value = doc.get(name)
        if value is None:
            raise BIDDocumentError("%s: §4.2.1 %s is 必填 (required); %r is absent"
                                   % (did, item, name))
        if not isinstance(value, str) or not _ISO_RE.match(value):
            raise BIDDocumentError("%s: %s is not an ISO-8601 timestamp: %r" % (did, name, value))
        setattr(parsed, name, value)

    proof = doc.get("proof")
    if proof is not None:
        if not isinstance(proof, dict):
            raise BIDDocumentError("%s: proof must be an object" % (did,))
        for part in ("creator", "signatureValue"):
            if not isinstance(proof.get(part), str) or not proof.get(part):
                raise BIDDocumentError("%s: proof.%s is missing" % (did, part))
        try:
            base58_decode(proof["signatureValue"])
        except BIDDocumentError:
            raise BIDDocumentError("%s: proof.signatureValue is not Base58" % (did,)) from None
        if proof["creator"] not in seen:
            raise BIDDocumentError("%s: proof.creator %r is not a publicKey in this document"
                                   % (did, proof["creator"]))
        parsed.proof = proof

    return parsed


# ------------------------------------------------------------------ §5 signing
def signing_bytes(doc: Dict[str, Any]) -> bytes:
    """§5.3 steps 1-2: drop `proof`, canonicalize, compress to bytes.

    The protocol's ordering rule ("UTF-16 code units, per-key, recursive") *is*
    RFC 8785 JCS, which `canonical.canonicalize` implements and pins against a
    JavaScript implementation - so a third party can re-derive this byte string
    with any JCS tool.
    """
    stripped = {k: v for k, v in doc.items() if k != "proof"}
    return canonicalize(stripped)


def sign_bid_document(doc: Dict[str, Any], seed: bytes, key_id: str) -> Dict[str, Any]:
    """§5.3 steps 1-5 for Ed25519. Returns a copy of `doc` carrying `proof`."""
    if not isinstance(seed, (bytes, bytearray)) or len(seed) != 32:
        raise BIDDocumentError("Ed25519 seed must be 32 bytes")
    signed = dict(doc)
    signed.pop("proof", None)
    signature = ed_sign(bytes(seed), signing_bytes(signed))
    signed["proof"] = {
        "creator": key_id,
        "signatureValue": base58_encode(signature),
        "type": "Ed25519Signature2018",
    }
    return signed


def verify_bid_document(doc: Any, did: Optional[str] = None) -> Tuple[bool, str]:
    """§5 verification. Returns (ok, reason) - never raises on a bad signature.

    Structural problems raise `BIDDocumentError`; a genuine "signature does not
    match" is a False, because that is an answer, not an exception.
    """
    parsed = parse_bid_document(doc, did or (doc.get("id") if isinstance(doc, dict) else None))
    if parsed.proof is None:
        raise BIDDocumentError("%s: no proof to verify" % (parsed.id,))
    key = parsed.verification_key(parsed.proof["creator"])
    if key is None:
        return False, "proof.creator %r is not an authentication key of this document" % (
            parsed.proof["creator"],)
    hexed = key.get("publicKeyHex")
    if not hexed:
        return False, "publicKey %r has no publicKeyHex to verify against" % (key.get("id"),)
    raw = bytes.fromhex(hexed)
    if "SM2" in str(key.get("type") or "").upper():
        return _verify_sm2_key(key, doc, parsed)
    key_material, prefix = strip_key_prefix(hexed)
    if len(key_material) != 32:
        return False, ("only Ed25519 (32-byte) keys are verifiable here, got %d bytes after a %r prefix"
                       % (len(key_material), prefix))
    try:
        sig = base58_decode(parsed.proof["signatureValue"])
    except BIDDocumentError as exc:
        return False, str(exc)
    if len(sig) != 64:
        return False, "signatureValue decodes to %d bytes, expected 64" % (len(sig),)
    if ed_verify(key_material, signing_bytes(doc), sig):
        return True, "ok"
    return False, "signature does not verify over the JCS form of the document"


def _verify_sm2_key(key, doc, parsed) -> Tuple[bool, str]:
    """§5 with SM2: signature over the same JCS bytes, verified on the national curve.

    Two things BID does not specify, and this does not invent silently:
      * the distinguisher ID: GM/T's default "1234567812345678" is used, and the
        success reason says so - a chain that signs under another ID will simply
        fail here rather than be reported as verified;
      * the key encoding: 64-byte x||y, with the same optional b0 / b06566 head
        Ed25519 keys carry.
    """
    from . import sm2 as _sm2

    try:
        px, py = _sm2.parse_public_key_hex(key.get("publicKeyHex"))
    except _sm2.SM2Error as exc:
        return False, str(exc)
    try:
        r, s = _sm2.parse_signature(base58_decode(parsed.proof["signatureValue"]))
    except (BIDDocumentError, _sm2.SM2Error) as exc:
        return False, str(exc)
    try:
        ok = _sm2.verify(px, py, signing_bytes(doc), r, s)
    except _sm2.SM2Error as exc:
        return False, str(exc)
    if ok:
        return True, "ok (SM2; distinguisher ID = GM/T default 1234567812345678)"
    return False, "SM2 signature does not verify over the JCS form of the document"


def generate_ed25519_pair() -> Tuple[bytes, str]:
    """A convenience for tests and fixtures: (seed, 0xb0-prefixed publicKeyHex)."""
    import os

    seed = os.urandom(32)
    return seed, "b0" + ed_public_key(seed).hex()


# --------------------------------------------------- resolution / §4.2.3 chain
def default_fetcher(url, timeout=10):
    """Minimal GET as JSON. Callers that need auth or proxies inject their own."""
    import urllib.request

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "uibc-core-bid-protocol/0.1"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def resolve_bid(endpoint: str, did: str, fetcher: Optional[Callable[..., Any]] = None,
                timeout: int = 10, retries: int = 2) -> BIDDocument:
    """One §4.2.1 read, with the documented transient codes retried.

    Codes 3 ("server too busy") and 7 ("server not response") are the only two
    a second attempt can fix; everything else is returned to the caller as-is.
    """
    fetcher = fetcher or default_fetcher

    url = "%s/%s" % (endpoint.rstrip("/"), did)
    attempt = 0
    while True:
        try:
            payload = fetcher(url, timeout=timeout)
        except Exception as exc:  # network-level failure: same class as code 7
            if attempt >= retries:
                raise BIDResponseError(7, str(exc), did) from None
            attempt += 1
            continue
        try:
            return parse_bid_document(parse_bid_envelope(payload, did), did)
        except BIDResponseError as exc:
            if exc.retryable and attempt < retries:
                attempt += 1
                continue
            raise


def resolve_bid_chain(endpoint: str, did: str, fetcher: Optional[Callable[..., Any]] = None,
                      max_hops: int = 3) -> BIDDocument:
    """§4.2.3 recursion: main-chain document -> DIDSubResolver -> sub-chain document.

    Guards that a naive implementation misses: a hop budget (a chain of
    resolvers must terminate), and a visited set (a document that points back
    at an address already used is a cycle, not an answer).
    """
    hops = 0
    seen_endpoints = {endpoint.rstrip("/")}
    current_doc = resolve_bid(endpoint, did, fetcher=fetcher)
    while True:
        sub = current_doc.sub_chain_service()
        if sub is None:
            return current_doc
        if hops >= max_hops:
            raise BIDProtocolError("%s: sub-chain recursion exceeded %d hops (%r)"
                                   % (did, max_hops, sub.get("serviceEndpoint")))
        target = str(sub.get("serviceEndpoint") or "")
        proto = sub.get("protocol")
        if proto == 3 and target.startswith("http://"):
            target = "https://" + target[len("http://"):]
        if not target.startswith(("http://", "https://")):
            raise BIDProtocolError("%s: sub-chain endpoint %r is not an HTTP(S) address"
                                   % (did, target))
        if target.rstrip("/") in seen_endpoints:
            raise BIDProtocolError("%s: sub-chain resolution cycles back to %r" % (did, target))
        seen_endpoints.add(target.rstrip("/"))
        hops += 1
        current_doc = resolve_bid(target, did, fetcher=fetcher)


# --------------------------------------------- §4.2.2 field-level resolution
#
# The protocol gives five field endpoints under the same document. Each answers
# with `data.version` ("1.0.0" in this version), `data.id` (the BID asked about),
# and one field. Two of them change shape depending on whether you asked for all
# of something or one of it - `public-keys` returns an array, and
# `public-keys/{id}` returns a single object. That asymmetry is the protocol's,
# not a mistake here; a caller that assumes "always a list" gets it wrong.
PROTOCOL_VERSION = "1.0.0"


def _field_answer(url: str, did: str, fetcher, timeout: int, retries: int) -> Dict[str, Any]:
    """GET a §4.2.2 endpoint, apply the §4.2.5 codes, return the `data` object."""
    attempt = 0
    while True:
        try:
            payload = fetcher(url, timeout=timeout)
        except Exception as exc:
            if attempt >= retries:
                raise BIDResponseError(7, str(exc), did) from None
            attempt += 1
            continue
        if not isinstance(payload, dict):
            raise BIDDocumentError("%s: field answer is %s, not an object"
                                   % (did, type(payload).__name__))
        code = payload.get("errorCode", 0)
        if isinstance(code, bool) or not isinstance(code, int):
            raise BIDResponseError(-1, "errorCode is not an integer: %r" % (code,), did)
        if code != 0:
            if BID_RESPONSE_CODES.get(code, ("", ""))[1] == "transient" and attempt < retries:
                attempt += 1
                continue
            raise BIDResponseError(code, payload.get("message", ""), did)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise BIDDocumentError("%s: field answer carries no data object" % (did,))
        if data.get("id") != did:
            raise BIDDocumentError("%s: field answer is about %r" % (did, data.get("id")))
        version = data.get("version")
        if version is not None and not isinstance(version, str):
            raise BIDDocumentError("%s: data.version is not a string: %r" % (did, version))
        return data


def _validate_public_key(entry: Any, did: str) -> Dict[str, Any]:
    """One §3 publicKey entry, same rules whether it arrived in a document or alone."""
    if not isinstance(entry, dict):
        raise BIDDocumentError("%s: publicKey entry is not an object" % (did,))
    key_id = entry.get("id")
    if not isinstance(key_id, str) or "#" not in key_id:
        raise BIDDocumentError("%s: publicKey.id must be a #key id, got %r" % (did, key_id))
    if not key_id.startswith(did + "#"):
        raise BIDDocumentError("%s: publicKey.id %r does not belong to this BID" % (did, key_id))
    controller = entry.get("controller")
    if controller is not None and not str(controller).startswith("did:bid:"):
        raise BIDDocumentError("%s: publicKey.controller %r is not a BID" % (did, controller))
    hexed = entry.get("publicKeyHex")
    if hexed is not None and not _is_hex(str(hexed)):
        raise BIDDocumentError("%s: publicKeyHex is not hex: %r" % (did, str(hexed)[:16]))
    return entry


def resolve_public_keys(endpoint: str, did: str, key_id: Optional[str] = None,
                        fetcher: Optional[Callable[..., Any]] = None,
                        timeout: int = 10, retries: int = 2):
    """§4.2.2.1: all keys (a list) or one key (an object)."""
    from urllib.parse import quote

    fetcher = fetcher or default_fetcher
    if key_id is None:
        data = _field_answer("%s/%s/public-keys" % (endpoint.rstrip("/"), did),
                             did, fetcher, timeout, retries)
        keys = data.get("publicKey")
        if not isinstance(keys, list):
            raise BIDDocumentError("%s: public-keys answer should be a list, got %s"
                                   % (did, type(keys).__name__))
        return [_validate_public_key(entry, did) for entry in keys]
    data = _field_answer("%s/%s/public-keys/%s" % (endpoint.rstrip("/"), did, quote(key_id, safe="")),
                         did, fetcher, timeout, retries)
    key = data.get("publicKey")
    if isinstance(key, list):
        raise BIDDocumentError("%s: single-key answer should be an object, got a list" % (did,))
    return _validate_public_key(key, did)


def resolve_attributes(endpoint: str, did: str, fetcher: Optional[Callable[..., Any]] = None,
                       timeout: int = 10, retries: int = 2) -> List[Dict[str, Any]]:
    """§4.2.2.2: the attribute list."""
    fetcher = fetcher or default_fetcher
    data = _field_answer("%s/%s/attributes" % (endpoint.rstrip("/"), did), did, fetcher, timeout, retries)
    attrs = data.get("attributes")
    if not isinstance(attrs, list):
        raise BIDDocumentError("%s: attributes answer should be a list" % (did,))
    for attr in attrs:
        if not isinstance(attr, dict) or "key" not in attr:
            raise BIDDocumentError("%s: attribute entries need key" % (did,))
        if attr.get("encrypt", 0) not in (0, 1):
            raise BIDDocumentError("%s: attribute.encrypt must be 0 or 1" % (did,))
    return attrs


def resolve_acsns(endpoint: str, did: str, fetcher: Optional[Callable[..., Any]] = None,
                  timeout: int = 10, retries: int = 2) -> List[str]:
    """§4.2.2.3: AC codes. The protocol says a main-chain resolver must offer this."""
    fetcher = fetcher or default_fetcher
    data = _field_answer("%s/%s/acsns" % (endpoint.rstrip("/"), did), did, fetcher, timeout, retries)
    codes = data.get("acsns")
    if not isinstance(codes, list):
        raise BIDDocumentError("%s: acsns answer should be a list" % (did,))
    for code in codes:
        if not isinstance(code, str) or len(code) != 4:
            raise BIDDocumentError("%s: AC code %r is not four characters" % (did, code))
    return codes


def resolve_credentials(endpoint: str, did: str, fetcher: Optional[Callable[..., Any]] = None,
                        timeout: int = 10, retries: int = 2) -> List[Dict[str, Any]]:
    """§4.2.2.4: the credential list."""
    fetcher = fetcher or default_fetcher
    data = _field_answer("%s/%s/verifiableCredentials" % (endpoint.rstrip("/"), did),
                         did, fetcher, timeout, retries)
    creds = data.get("verifiableCredentials")
    if not isinstance(creds, list):
        raise BIDDocumentError("%s: verifiableCredentials answer should be a list" % (did,))
    for cred in creds:
        if not isinstance(cred, dict) or not isinstance(cred.get("id"), str):
            raise BIDDocumentError("%s: credential entries need a string id" % (did,))
    return creds


def resolve_service(endpoint: str, did: str, service_id: str,
                    fetcher: Optional[Callable[..., Any]] = None,
                    timeout: int = 10, retries: int = 2) -> Dict[str, Any]:
    """§4.2.2.5: one service address by id.

    The document prints the query with a full-width "？"; the wire form is a
    normal "?", which is what is sent here.
    """
    from urllib.parse import quote

    fetcher = fetcher or default_fetcher
    data = _field_answer("%s/%s/services?id=%s" % (endpoint.rstrip("/"), did, quote(service_id, safe="")),
                         did, fetcher, timeout, retries)
    service = data.get("service")
    if not isinstance(service, dict):
        raise BIDDocumentError("%s: services answer should be one object, got %s"
                               % (did, type(service).__name__))
    if service.get("id") != service_id:
        raise BIDDocumentError("%s: asked for service %r, got %r" % (did, service_id, service.get("id")))
    if service.get("type") not in SERVICE_TYPES:
        raise BIDDocumentError("%s: service type %r is not in appendix 1" % (did, service.get("type")))
    if not service.get("serviceEndpoint"):
        raise BIDDocumentError("%s: service %r has no serviceEndpoint" % (did, service_id))
    return service


# ------------------------------------------------------- §4.2.4 trusted resolution
@dataclass
class TrustedResolution:
    """§4.2.4 answer, with the server's claim kept separate from what we checked.

    The protocol says trusted resolution verifies "the public key and signature
    content" of the document so that every resolver in the chain is trustworthy.
    A resolver that only forwards `data.verify` would be trusting the very party
    it is supposed to check - so this object carries three independent bits:

      server_verify   what the resolver asserted (a Bool literal, not "true")
      signature_ok    our own re-verification of the document's §5 proof
      delegate_state  "absent" / "verified" / "invalid" / "unchecked"

    `trusted` needs the server's assertion AND our own signature check.
    `fully_trusted` additionally needs the delegateSign attestation resolved -
    and when the caller supplies no way to fetch the signer's key, the state is
    "unchecked" rather than a guessed yes.
    """

    did: str
    document: BIDDocument
    server_verify: bool
    signature_ok: Optional[bool]
    delegate_state: str
    delegate_signer: Optional[str] = None
    reason: str = ""

    @property
    def trusted(self) -> bool:
        return bool(self.server_verify) and self.signature_ok is True and self.delegate_state != "invalid"

    @property
    def fully_trusted(self) -> bool:
        return self.trusted and self.delegate_state in ("absent", "verified")


def delegate_signing_bytes(doc: Any) -> bytes:
    """The bytes `extension.delegateSign.signatureValue` signs: the `publicKey` field.

    §4.2.1 says the attestation is "第三方对publicKey的签名" and nothing about
    ordering; §5.2 already fixes ordering for everything signed in this protocol,
    so the array is canonicalized the same way. A signer that used another encoding
    will simply fail to verify here - which is the honest outcome, not a fallback.
    """
    if not isinstance(doc, dict) or "publicKey" not in doc:
        raise BIDDocumentError("delegateSign needs a document with a publicKey field")
    return canonicalize(doc["publicKey"])


def verify_delegate_sign(doc: Any, signer_public_key_hex: str) -> Tuple[bool, str]:
    """Check `extension.delegateSign` against the signer's key. Never raises on a bad sig."""
    if not isinstance(doc, dict):
        raise BIDDocumentError("document is not an object")
    ext = doc.get("extension")
    ds = ext.get("delegateSign") if isinstance(ext, dict) else None
    if not isinstance(ds, dict):
        raise BIDDocumentError("no extension.delegateSign to verify")
    signer = ds.get("signer")
    if not isinstance(signer, str) or "#" not in signer or not signer.startswith("did:bid:"):
        raise BIDDocumentError("delegateSign.signer must be a BID key id, got %r" % (signer,))
    material, prefix = strip_key_prefix(signer_public_key_hex)
    if len(material) != 32:
        return False, "delegate signer key is %d bytes after a %r prefix; only Ed25519 is verifiable here" % (
            len(material), prefix)
    try:
        sig = base58_decode(ds.get("signatureValue") or "")
    except BIDDocumentError as exc:
        return False, str(exc)
    if len(sig) != 64:
        return False, "delegateSign.signatureValue decodes to %d bytes, expected 64" % (len(sig),)
    if ed_verify(material, delegate_signing_bytes(doc), sig):
        return True, "ok"
    return False, "delegateSign does not verify over the JCS form of publicKey"


def resolve_bid_trusted(endpoint: str, did: str, fetcher: Optional[Callable[..., Any]] = None,
                        delegate_key_resolver: Optional[Callable[[str], str]] = None,
                        timeout: int = 10, retries: int = 2) -> TrustedResolution:
    """One §4.2.4 read: `GET {url}/{bid}?verify=true`, then check the answer ourselves.

    `delegate_key_resolver(signer_id) -> publicKeyHex` is how a caller supplies the
    attestation signer's key (typically by resolving the signer's own BID). Without
    it the delegate attestation is reported "unchecked" - visibly, not silently.
    """
    fetcher = fetcher or default_fetcher
    url = "%s/%s?verify=true" % (endpoint.rstrip("/"), did)

    attempt = 0
    while True:
        try:
            payload = fetcher(url, timeout=timeout)
        except Exception as exc:
            if attempt >= retries:
                raise BIDResponseError(7, str(exc), did) from None
            attempt += 1
            continue
        try:
            server_verify, doc = _trusted_envelope(payload, did)
            break
        except BIDResponseError as exc:
            if exc.retryable and attempt < retries:
                attempt += 1
                continue
            raise

    parsed = parse_bid_document(doc, did)
    try:
        signature_ok, sig_reason = verify_bid_document(doc, did)
    except BIDDocumentError as exc:  # no proof at all is an answer, not a crash
        signature_ok, sig_reason = False, str(exc)

    state, signer, delegate_reason = "absent", None, ""
    ds = parsed.extension.get("delegateSign") if isinstance(parsed.extension, dict) else None
    if ds is not None:
        if not isinstance(ds, dict):
            state, delegate_reason = "invalid", "extension.delegateSign is not an object"
        else:
            signer = ds.get("signer")
            if delegate_key_resolver is None:
                state = "unchecked"
                delegate_reason = ("delegateSign present but no delegate_key_resolver was supplied; "
                                   "the attestation is NOT verified")
            else:
                if not isinstance(signer, str) or "#" not in signer:
                    state, delegate_reason = "invalid", "delegateSign.signer must be a BID key id"
                elif not isinstance(ds.get("signatureValue"), str) or not ds.get("signatureValue"):
                    state, delegate_reason = "invalid", "delegateSign.signatureValue missing"
                else:
                    try:
                        key_hex = delegate_key_resolver(signer)
                        ok, delegate_reason = verify_delegate_sign(doc, key_hex)
                        state = "verified" if ok else "invalid"
                    except Exception as exc:  # signer unresolvable is not a forged signature
                        state = "unchecked"
                        delegate_reason = "delegate signer %r could not be resolved: %s" % (signer, exc)

    reason = sig_reason
    if signature_ok and delegate_reason:
        reason = delegate_reason
    if not server_verify:
        reason = "resolver returned verify=%r; §4.2.4 requires the literal true" % (server_verify,)
    return TrustedResolution(did=did, document=parsed, server_verify=server_verify,
                             signature_ok=signature_ok, delegate_state=state,
                             delegate_signer=signer if isinstance(signer, str) else None,
                             reason=reason)


def _trusted_envelope(payload: Any, did: str) -> Tuple[bool, Dict[str, Any]]:
    """`data.verify` must be the Bool true; the document is the rest of §4.2.1."""
    doc = parse_bid_envelope(payload, did)
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and "verify" in data:
        raw = data["verify"]
    elif "verify" in doc:
        raw = doc["verify"]
        doc = {k: v for k, v in doc.items() if k != "verify"}
    else:
        raise BIDDocumentError("%s: trusted answer carries no data.verify field" % (did,))
    if raw is True:
        return True, doc
    if isinstance(raw, bool):
        return False, doc
    raise BIDDocumentError("%s: data.verify must be a Bool, got %r" % (did, raw))


def refuse_binary_resolution(did: str) -> None:
    """§4.3 is not implemented here; say so with the protocol's own code 5."""
    raise BIDResponseError(5, "binary resolution (§4.3) is not implemented in uibc-core", did)
