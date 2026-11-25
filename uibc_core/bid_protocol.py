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

  * SM2/SM3 is **not** implemented. Ed25519 is, because it can be verified
    from this repository alone. An SM2 document is parsed and reported as
    "algorithm not verifiable here" rather than silently accepted.
  * §4.3 (binary resolution) is not implemented. A binary payload is refused
    with code 5 (operation not supported) instead of being guessed at.
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

# BID public keys are carried as hex. Implementations in the wild prefix an
# Ed25519 key with the BIF algorithm byte 0xb0 (b06566... in the protocol's own
# §5.4.1 example is b0 + 32 bytes of key material), so both widths are legal.
_ED25519_HEX_LEN = {64, 66}


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
                "publicKey %s: Ed25519 key is %d hex chars, expected 64 (bare) or 66 (0xb0-prefixed)"
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

    for name in ("created", "updated"):
        value = doc.get(name)
        if value is None:
            continue
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
    if len(raw) == 33 and raw[0] == 0xB0:      # BIF algorithm-byte prefix
        raw = raw[1:]
    if len(raw) != 32:
        return False, "only Ed25519 (32-byte) keys are verifiable here, got %d bytes" % (len(raw),)
    try:
        sig = base58_decode(parsed.proof["signatureValue"])
    except BIDDocumentError as exc:
        return False, str(exc)
    if len(sig) != 64:
        return False, "signatureValue decodes to %d bytes, expected 64" % (len(sig),)
    if ed_verify(raw, signing_bytes(doc), sig):
        return True, "ok"
    return False, "signature does not verify over the JCS form of the document"


def generate_ed25519_pair() -> Tuple[bytes, str]:
    """A convenience for tests and fixtures: (seed, 0xb0-prefixed publicKeyHex)."""
    import os

    seed = os.urandom(32)
    return seed, "b0" + ed_public_key(seed).hex()


# --------------------------------------------------- resolution / §4.2.3 chain
def resolve_bid(endpoint: str, did: str, fetcher: Optional[Callable[..., Any]] = None,
                timeout: int = 10, retries: int = 2) -> BIDDocument:
    """One §4.2.1 read, with the documented transient codes retried.

    Codes 3 ("server too busy") and 7 ("server not response") are the only two
    a second attempt can fix; everything else is returned to the caller as-is.
    """
    import urllib.request

    if fetcher is None:
        def fetcher(url, timeout=10, method="GET", payload=None, headers=None):  # noqa: ARG001
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/json",
                         "User-Agent": "uibc-core-bid-protocol/0.1"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
                return json.loads(response.read().decode("utf-8"))

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


def refuse_binary_resolution(did: str) -> None:
    """§4.3 is not implemented here; say so with the protocol's own code 5."""
    raise BIDResponseError(5, "binary resolution (§4.3) is not implemented in uibc-core", did)
