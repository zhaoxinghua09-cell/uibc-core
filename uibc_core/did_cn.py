"""China-registry DID methods, supported at the level each specification allows.

Six DID methods whose specifications are published by Chinese registry operators
and which are listed in the W3C DID Extensions registry (`w3c/did-extensions`,
`methods/<name>.json`; 282 entries on the day this was written):

  cn        CAICT / Astron    github.com/caict-4iot-dev/CN-DID-Method-Specification
  ioa       teleinfo CAICT    github.com/ReciterKim/ioa  (doc/en IOA Protocol Specification)
  cndid     teleinfo CAICT    github.com/teleinfo-bif/cndid (doc/en CNDID Protocol Specification)
  ctid      anicert           github.com/617640999/ctid-did-register (anicert-ctid-did-en.md)
  oan       OpenAgenet        github.com/OpenAgenet/oan-public-docs (did-oan-specs/doc)
  cndomain  CNNIC             cndomain-dev.github.io/did-method-cndomain (draft 2026-05-07)

Two levels, and both are refusals where they matter:

  registry         the method definition lives in a registry (chain or HTTP
                   service). We validate the identifier and hand resolution to an
                   endpoint the CALLER must supply. We never default one: a wrong
                   guess produces an answer that looks authoritative.
  identifier_only  grammar and document shape are published, the resolution
                   channel is proprietary or unpublished, so we validate the
                   identifier and stop. `did:ctid` documents are signed with SM2
                   through a vendor SDK; `did:oan` defines no HTTP read API.

There is no "offline" level here on purpose. See `derivable_document()` for the
arithmetic that makes it impossible for `did:ioa`/`did:cndid`: the suffix is
capped at 42 characters, so the key body is at most 40 characters, while a 32-byte
Ed25519 key needs 43-44 characters in base58. The published examples confirm it
(30-character bodies decoding to about 22 bytes).

Adding a method means adding its ABNF below and its line in
`docs/spec-sources/did-cn-specs.md` -- not loosening a regex that "kind of works".
"""

import base64
import json
import re
import urllib.request

from . import did as _did

__all__ = [
    "METHODS",
    "SPECS",
    "DIDCNError",
    "IdentifierError",
    "RegistryEndpointRequired",
    "validate",
    "validate_live_agent_id",
    "level",
    "derivable_document",
    "resolve",
    "matrix",
]

#: method -> (owner, specification url, support level)
SPECS = {
    "cn": ("China Academy of Information and Communications Technology (CAICT) / Astron",
           "https://github.com/caict-4iot-dev/CN-DID-Method-Specification",
           "registry"),
    "ioa": ("teleinfo CAICT / TChain",
            "https://github.com/ReciterKim/ioa/blob/main/doc/en/IOA%20Protocol%20Specification.md",
            "registry"),
    "cndid": ("teleinfo CAICT / TChain",
              "https://github.com/teleinfo-bif/cndid/blob/main/doc/en/CNDID%20Protocol%20Specification.md",
              "registry"),
    "ctid": ("Beijing Zhongdun Anxin Science and Technology Development Co., Ltd",
             "https://github.com/617640999/ctid-did-register/blob/main/anicert-ctid-did-en.md",
             "identifier_only"),
    "oan": ("OpenAgenet",
            "https://github.com/OpenAgenet/oan-public-docs/blob/main/did-oan-specs/doc/OAN%20DID%20Method%20Specification.md",
            "identifier_only"),
    "cndomain": ("CNNIC / did-method-cndomain working draft",
                 "https://cndomain-dev.github.io/did-method-cndomain/did-cndomain-method-specification-draft.html",
                 "registry"),
}

METHODS = tuple(SPECS)

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# cn: cn-specific-idstring = issuer "." industry "." enterprise
#     issuer = 2DIGIT ; industry = 3*5DIGIT ; enterprise = 1*128DIGIT
_CN_RE = re.compile(r"^(\d{2})\.(\d{3,5})\.(\d{1,128})$")
# The namespace the live platform actually serves. It is **not** in the
# published ABNF: the platform hands out `did:cn:agent:<base58>`, where the
# second segment is the literal word "agent" and the tail is base58, while the
# README fixes `2DIGIT.3*5DIGIT.1*128DIGIT`. Measured 2026-11-24 against
# agent.idfactory.cn, whose registered agents all read `did:cn:agent:sf...`.
# Recognised, labelled, and never passed off as the published form.
_CN_LIVE_AGENT_RE = re.compile(r"^agent:(?P<key>[%s]{22,44})$" % _B58)
# ctid: method-specific-id = <hexdigit>{64} ; hexdigit = [0-9A-F]
_CTID_RE = re.compile(r"^[0-9A-F]{64}$")
# ioa / cndid: 0*1(acsn ":") suffix / acsn ":" 0*1(suffix)
#   acsn = 4(ALPHA / DIGIT) ; suffix = (22,42)(ALPHA / DIGIT)
_ACSN_RE = re.compile(r"^[A-Za-z0-9]{4}$")
_SUFFIX_RE = re.compile(r"^[A-Za-z0-9]{22,42}$")
# oan: did:oan:routing-code ":" suffix-code ; 5 + 32 base58 chars
_OAN_RE = re.compile("^(?:[%s]{5}):(?:[%s]{32})$" % (_B58, _B58))
# cndomain: "did:cndomain:" domain [ ":" object-type ":" object-name ] ; domain ends ".cn"
_CD_LABEL = "[a-z0-9]|[a-z0-9][a-z0-9-]*[a-z0-9]"
_CD_RE = re.compile(r"^(?:%s\.)+cn(?::[a-z0-9-]+:[a-z0-9-]+)?$" % _CD_LABEL)

# ioa/cndid suffix prefixes: algorithm then encoding (both from the spec tables)
_CRYPTO = {"z": "SM2", "e": "Ed25519", "s": "secp256k1"}
_ENCODING = {"f": "base58", "s": "base64", "t": "base32"}


class DIDCNError(_did.DIDError):
    """Base class for the China-registry methods."""


class IdentifierError(DIDCNError):
    """The method-specific identifier does not satisfy the published ABNF."""


class RegistryEndpointRequired(DIDCNError):
    """This method resolves through a registry the caller has to name."""


# --------------------------------------------------------------------------- #
# encodings (standard library only)
# --------------------------------------------------------------------------- #
def _b58decode(text):
    number = 0
    for char in text:
        index = _B58.find(char)
        if index < 0:
            raise IdentifierError("not a base58 character: %r" % (char,))
        number = number * 58 + index
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\x00" * (len(text) - len(text.lstrip("1"))) + raw


def _decode_by(encoding, body):
    if encoding == "base58":
        return _b58decode(body)
    if encoding == "base32":
        padded = body.upper() + "=" * (-len(body) % 8)
        try:
            return base64.b32decode(padded)
        except Exception as exc:
            raise IdentifierError("base32 body does not decode: %s" % (exc,)) from None
    if encoding == "base64":
        padded = body + "=" * (-len(body) % 4)
        try:
            return base64.b64decode(padded, validate=True)
        except Exception as exc:
            raise IdentifierError("base64 body does not decode: %s" % (exc,)) from None
    raise IdentifierError("unknown encoding prefix: %r" % (encoding,))


# --------------------------------------------------------------------------- #
# identifier rules
# --------------------------------------------------------------------------- #
def _check_ioa_cndid(method, ident):
    """Return (crypto label, encoding, key bytes or None) for did:ioa / did:cndid."""
    suffix = ident
    if ":" in ident:
        head, _, tail = ident.partition(":")
        if not _ACSN_RE.match(head):
            raise IdentifierError("%s: acsn segment %r must be 4 alphanumerics"
                                  % (method, head))
        suffix = tail
        if not suffix:
            # did:ioa:tele / did:cndid:tele : resolver-only DID, no key material
            return None, None, None
    elif _ACSN_RE.match(ident):
        # the specs also allow the acsn without its separating colon, e.g.
        # did:ioa:tele (spec 3.1) -- acsn-only, no key material
        return None, None, None
    if not _SUFFIX_RE.match(suffix):
        raise IdentifierError(
            "%s: suffix must be 22-42 alphanumerics, got %d (%r)"
            % (method, len(suffix), suffix))
    crypto, encoding = suffix[0], suffix[1]
    if crypto not in _CRYPTO:
        raise IdentifierError("%s: suffix must start with one of %s (algorithm), got %r"
                              % (method, "/".join(sorted(_CRYPTO)), crypto))
    if encoding not in _ENCODING:
        raise IdentifierError("%s: second suffix character must be one of %s (encoding), got %r"
                              % (method, "/".join(sorted(_ENCODING)), encoding))
    body = suffix[2:]
    if not body:
        raise IdentifierError("%s: suffix carries no key material after two prefix letters"
                              % (method,))
    raw = _decode_by(_ENCODING[encoding], body)
    # The specs say the suffix is "derived from the encoded public key" but never
    # fix how many bytes survive. Both published examples carry 30-character
    # bodies (about 22 bytes), so the decoded length is recorded, never asserted:
    # asserting it would be our rule, not theirs.
    label = _CRYPTO[crypto]
    if crypto == "e" and len(raw) != 32:
        label = "Ed25519(derivation not byte-exact: %d bytes)" % len(raw)
    return label, _ENCODING[encoding], raw


def validate(did):
    """Validate the published ABNF for one of the six methods.

    Returns (method, support_level, details). `details` carries what the
    identifier itself proves, e.g. {"crypto": "Ed25519", "key": b"..."}.
    Raises IdentifierError -- never returns a "close enough" answer.
    """
    if not isinstance(did, str):
        raise IdentifierError("DID must be a string")
    method, ident = _did.parse(did)
    if method not in SPECS:
        raise IdentifierError("did:%s is not one of the China-registry methods here: %s"
                              % (method, ", ".join(METHODS)))
    details = {}
    if method == "cn":
        m = _CN_RE.match(ident)
        if not m:
            raise IdentifierError(
                'did:cn expects issuer"."industry"."enterprise (2DIGIT.3*5DIGIT.1*128DIGIT), got %r'
                % (ident,))
        details.update(issuer=m.group(1), industry=m.group(2), enterprise=m.group(3))
    elif method == "ctid":
        if not _CTID_RE.match(ident):
            raise IdentifierError(
                "did:ctid expects the SM3 hash as 64 UPPERCASE hex characters "
                "(spec: hexdigit = [0-9A-F]), got %r" % (ident,))
    elif method in ("ioa", "cndid"):
        crypto, encoding, key = _check_ioa_cndid(method, ident)
        details.update(crypto=crypto, encoding=encoding, key=key)
    elif method == "oan":
        if not _OAN_RE.match(ident):
            raise IdentifierError(
                "did:oan expects did:oan:<5 base58>:<32 base58> (canonical length 46), got %r"
                % (did,))
        routing, _, suffix = ident.partition(":")
        details.update(routing_code=routing, suffix_code=suffix)
    elif method == "cndomain":
        if not _CD_RE.match(ident):
            raise IdentifierError(
                "did:cndomain expects lowercase <label.>+.cn[:<object-type>:<object-name>], got %r"
                % (ident,))
        details.update(domain=ident.split(":")[0])
    return method, SPECS[method][2], details


def validate_live_agent_id(did):
    """Recognise the live `did:cn:agent:<base58>` form the platform really serves.

    This form is **not** in the published ABNF (README fixes
    `2DIGIT.3*5DIGIT.1*128DIGIT`), and `validate()` therefore refuses it — which
    is correct, because accepting it there would mean the adapter no longer
    checks the document it claims to check. But refusing it silently leaves
    every registered agent unresolvable: the platform's own listing is 77 agents
    and all of them read `did:cn:agent:sf...` (measured 2026-11-24).

    So it gets its own entry point, with its own label. Returns a dict on
    success and raises `IdentifierError` otherwise. The dict always says
    `published_abnf: False`, so no caller can accidentally treat this as the
    documented namespace, and nothing here can reach `VERIFIED`: the segment
    proves only that the string is shaped like the platform's output.
    """
    if not isinstance(did, str):
        raise IdentifierError("DID must be a string")
    method, ident = _did.parse(did)
    if method != "cn":
        raise IdentifierError("this is the did:cn live form only, got did:%s" % (method,))
    m = _CN_LIVE_AGENT_RE.match(ident)
    if not m:
        raise IdentifierError(
            "not the live did:cn agent form: expected 'agent:<22-44 base58>', got %r "
            "(the published ABNF form '2DIGIT.3*5DIGIT.1*128DIGIT' is handled by "
            "validate(), not here)" % (ident,))
    return {
        "method": "cn",
        "namespace": "agent",
        "key_encoding": "base58",
        "key_length": len(m.group("key")),
        "published_abnf": False,
        "note": ("undocumented live form: the published ABNF has no 'agent' segment; "
                 "shape alone proves nothing about allocation"),
    }


def level(did):
    """Support level for an identifier, without validating its grammar."""
    return SPECS.get(_did.parse(did)[0], (None, None, "unsupported"))[2]


# --------------------------------------------------------------------------- #
# offline document derivation: possible, then ruled out by arithmetic
# --------------------------------------------------------------------------- #
def derivable_document(did):
    """Rebuild a DID document from the identifier alone, or return None.

    This exists so the refusal is checkable rather than asserted. For
    `did:ioa`/`did:cndid` it returns None even when the suffix decodes to a
    whole 32-byte key -- and the ABNF makes that case unreachable anyway:
    42-character suffix means a 40-character body, and 32 bytes need 43-44
    characters in base58 (43 in base64, 52 in base32). The single exception is
    a decoder that produces exactly 32 bytes from a <=40-character body, which
    we honour rather than reject, because nothing in the spec forbids it.
    """
    method, _, details = validate(did)
    if method not in ("ioa", "cndid"):
        return None
    if details.get("crypto") != "Ed25519" or not details.get("key"):
        return None
    public_key = details["key"]
    key_id = did + "#" + did.rsplit(":", 1)[-1]
    return {
        "@context": ["https://www.w3.org/ns/did/v1",
                     "https://w3id.org/security/suites/ed25519-2020/v1"],
        "id": did,
        "verificationMethod": [{
            "id": key_id,
            "type": "Ed25519VerificationKey2020",
            "controller": did,
            "publicKeyMultibase": "z" + _did._b58encode(_did._ED25519_MULTICODEC + public_key),
        }],
        "authentication": [key_id],
        "assertionMethod": [key_id],
    }


# --------------------------------------------------------------------------- #
# resolution
# --------------------------------------------------------------------------- #
def _fetch_json(url, timeout, fetcher=None, method="GET", payload=None):
    if fetcher is not None:
        return fetcher(url, timeout)
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={
        "Accept": "application/did+ld+json, application/json",
        "Content-Type": "application/json",
        "User-Agent": "uibc-core-did-cn/0.1",
    }, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        body = response.read()
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DIDCNError("document at %s is not JSON: %s" % (url, exc)) from None


def resolve(did, endpoint=None, timeout=10, fetcher=None):
    """Resolve a China-registry DID.

    `endpoint` is the registry base URL; mandatory for every method whose level
    is "registry". Passing None is an explicit refusal, not an invitation to
    default: the specifications name registries, not public resolution URLs.
    """
    method, lvl, details = validate(did)
    doc = derivable_document(did)
    if doc is not None:
        return doc
    if lvl == "identifier_only":
        raise DIDCNError(
            "%s: identifier validated, but this method publishes no resolution channel we can "
            "re-run (see SPECS[%r]); refusing to invent one" % (did, method))
    if not endpoint:
        raise RegistryEndpointRequired(
            "%s: did:%s resolves through a registry; pass endpoint=<registry base url> "
            "(spec: %s)" % (did, method, SPECS[method][1]))
    endpoint = endpoint.rstrip("/")
    if method == "cn":
        # spec 3.2: GET /did/resolve/<did> with Accept: application/did+json
        doc = _fetch_json("%s/did/resolve/%s" % (endpoint, did), timeout, fetcher)
    elif method in ("ioa", "cndid"):
        # spec 5.2: send operation "read" to a registration node, document in data.didDocument
        envelope = _fetch_json(endpoint, timeout, fetcher, method="POST",
                               payload={"operation": "read", "did": did})
        data = envelope.get("data") if isinstance(envelope, dict) else None
        doc = data.get("didDocument") if isinstance(data, dict) else envelope
    elif method == "cndomain":
        doc = _fetch_json("%s/%s" % (endpoint, did), timeout, fetcher)
    else:
        raise DIDCNError("%s: no read shape implemented for did:%s" % (did, method))
    if not isinstance(doc, dict):
        raise DIDCNError("%s: registry returned a non-object document" % (did,))
    if doc.get("id") != did:
        raise DIDCNError("%s: document id %r does not match %r"
                         % (did, doc.get("id"), did))
    return doc


def matrix():
    """One row per method: what we validate, what we refuse, and where the text is."""
    rows = []
    for method in METHODS:
        owner, spec, lvl = SPECS[method]
        rows.append({
            "method": "did:" + method,
            "owner": owner,
            "level": lvl,
            "identifier_rule": "published ABNF enforced",
            # a capability of the rule, unreachable for today's identifiers -- see
            # derivable_document() for the character-count arithmetic
            "offline_document_when_key_is_byte_exact": method in ("ioa", "cndid"),
            "resolution": ("endpoint required" if lvl == "registry" else "none published; refused"),
            "specification": spec,
        })
    return rows
