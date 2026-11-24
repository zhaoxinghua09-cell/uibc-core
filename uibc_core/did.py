"""DID support for uibc-core: `did:key` (offline) and `did:web` (HTTPS), plus
the six China-registry methods handled in `uibc_core.did_cn`.

Two groups, two rules
---------------------
`did:key` and `did:web` are resolved here: `did:key` needs no network at all,
`did:web` resolves to a document the controller publishes under their own
domain, so a third party can check our binding without trusting us.

The China-registry methods (`did:cn`, `did:ioa`, `did:cndid`, `did:ctid`,
`did:oan`, `did:cndomain`) live in `did_cn.py`. Their specifications are public
(see `docs/spec-sources/did-cn-specs.md` for URLs and byte counts, fetched
2026-11-24), which is why the earlier "no published specification" note in this
module is gone rather than softened -- a stale negative is still a false claim.
Each of them is supported at the level its own text allows: identifier ABNF
always, registry resolution only when the caller names the endpoint, and no
guessed default URL anywhere. `did:wba` also has a public specification but is
not wired here yet, so it still raises UnsupportedMethod.

Scope of this module
--------------------
Enough to (1) bind a UIBC agent identity to a DID and (2) verify an Ed25519
UIBC seal against the key the DID document publishes. It is not a general
DID resolver: no key rotation history, no deactivation, no JSON-LD
canonicalisation of arbitrary documents.
"""

import base64
import ipaddress
import json
import re
import socket
import urllib.parse
import urllib.request

from . import signing

__all__ = [
    "DIDError",
    "HostPolicyError",
    "DocumentTooLarge",
    "UnsupportedMethod",
    "parse",
    "did_web_url",
    "resolve",
    "did_key_document",
    "did_key_from_ed25519",
    "document_ed25519_key",
    "resolve_ed25519_key",
    "verify_seal_with_did",
    "SUPPORTED_METHODS",
]

SUPPORTED_METHODS = ("key", "web")

# did:method:specific-id  (specific-id is intentionally loose: each method has
# its own grammar and we validate per method below)
_DID_RE = re.compile(r"^did:([a-z0-9]+):([^:\s]+(?::[^:\s]+)*)$")

# multibase + multicodec prefix for an Ed25519 public key: 0xed 0x01
_ED25519_MULTICODEC = b"\xed\x01"
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class DIDError(ValueError):
    """Malformed DID or malformed DID document."""


class UnsupportedMethod(DIDError):
    """Method is well-formed but this module refuses to guess its rule."""


# --------------------------------------------------------------------------- #
# DID parsing
# --------------------------------------------------------------------------- #
def parse(did):
    """Split a DID into (method, method_specific_id) after validating its shape."""
    if not isinstance(did, str):
        raise DIDError("DID must be a string")
    m = _DID_RE.match(did)
    if not m:
        raise DIDError("not a DID: %r" % (did,))
    return m.group(1), m.group(2)


def did_web_url(did):
    """Return the HTTPS URL where a `did:web` document must be published.

    did:web:example.com          -> https://example.com/.well-known/did.json
    did:web:example.com:user:al  -> https://example.com/user/al/did.json
    did:web:example.com%3A8443   -> https://example.com:8443/.well-known/did.json
    """
    method, ident = parse(did)
    if method != "web":
        raise UnsupportedMethod("did_web_url() only accepts did:web, got did:%s" % method)
    segments = ident.split(":")
    host = segments[0].replace("%3A", ":").replace("%3a", ":")
    if not host:
        raise DIDError("did:web has an empty host")
    if len(segments) == 1:
        return "https://%s/.well-known/did.json" % host
    return "https://%s/%s/did.json" % (host, "/".join(segments[1:]))


# --------------------------------------------------------------------------- #
# Encoding helpers (stdlib only)
# --------------------------------------------------------------------------- #
def _b58decode(text):
    number = 0
    for char in text:
        index = _B58_ALPHABET.find(char)
        if index < 0:
            raise DIDError("invalid base58 character: %r" % (char,))
        number = number * 58 + index
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    # leading '1's are leading zero bytes
    pad = len(text) - len(text.lstrip("1"))
    return b"\x00" * pad + raw


def _b58encode(raw):
    number = int.from_bytes(raw, "big")
    out = ""
    while number:
        number, remainder = divmod(number, 58)
        out = _B58_ALPHABET[remainder] + out
    pad = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * pad + (out or "")


def _b64url_decode(text):
    if not isinstance(text, str) or not text:
        raise DIDError("empty base64url value")
    padding = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + padding)
    except (ValueError, TypeError) as exc:
        raise DIDError("invalid base64url value: %s" % (exc,)) from None


def _multibase_decode(value):
    """Decode a multibase string, returning (multicodec_prefix, raw_key)."""
    if not isinstance(value, str) or len(value) < 2:
        raise DIDError("invalid multibase value")
    prefix, body = value[0], value[1:]
    if prefix == "z":
        raw = _b58decode(body)
    elif prefix == "u":
        raw = _b64url_decode(body)
    else:
        raise DIDError("unsupported multibase prefix: %r" % (prefix,))
    return raw[:2], raw[2:]


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #
def did_key_from_ed25519(public_key):
    """Return the `did:key` DID for a 32-byte Ed25519 public key."""
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
        raise DIDError("Ed25519 public key must be 32 bytes")
    return "did:key:z" + _b58encode(_ED25519_MULTICODEC + bytes(public_key))


def did_key_document(public_key, did=None):
    """Build the W3C DID document for a did:key (Ed25519). Fully offline."""
    did = did or did_key_from_ed25519(public_key)
    key_id = did + "#" + did.split(":")[-1]
    return {
        "@context": ["https://www.w3.org/ns/did/v1",
                     "https://w3id.org/security/suites/ed25519-2020/v1"],
        "id": did,
        "verificationMethod": [{
            "id": key_id,
            "type": "Ed25519VerificationKey2020",
            "controller": did,
            "publicKeyMultibase": "z" + _b58encode(_ED25519_MULTICODEC
                                                  + bytes(public_key)),
        }],
        "authentication": [key_id],
        "assertionMethod": [key_id],
    }


# --------------------------------------------------------------------------- #
# Network guards for did:web
#
# Three defects were measured on 2026-11-23 and each one is a way to make a
# verifier do something other than verify:
#
#   * `did:web:127.0.0.1%3A8443` fetched a document from the verifier's own
#     machine; `did:web:169.254.169.254` reaches a cloud metadata service. The
#     method spec itself forbids an IP address in the method-specific id, and
#     "must resolve over https" says nothing about *where*.
#   * A 302 could point at plaintext http, and urllib follows it by default,
#     so the one https check applied to the first hop only.
#   * A 20 MB document was read in full (70 MB peak) before being rejected as
#     JSON -- an unbounded read is a memory exhaustion primitive.
#
# The guards sit in `_fetch_json`, which is the path a real resolver takes. A
# caller that injects `fetcher=` is deliberately outside them: the caller has
# already chosen the transport, and pretending otherwise would be theatre.
# --------------------------------------------------------------------------- #

DEFAULT_MAX_DOCUMENT_BYTES = 512 * 1024

_BLOCKED_HOSTS = frozenset({
    "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
    "metadata.google.internal", "instance-data", "metadata",
})
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain")


class HostPolicyError(DIDError):
    """The target host is not a public, routable name that did:web may use."""


class DocumentTooLarge(DIDError):
    """The response exceeded the read cap; the document was never parsed."""


def assert_public_host(host, resolve_dns=True):
    """Refuse anything that is not a public DNS name.

    Called before the request and again on the final URL, because a redirect is
    a second chance to break the rule. DNS rebinding is narrowed, not solved:
    the name is resolved here and the connection resolves it again, and a
    resolver hook would be needed to close that window. Saying so is cheaper
    than implying the guard is complete.
    """
    if not host:
        raise HostPolicyError("did:web has an empty host")
    host = host.strip().rstrip(".")
    if not host:
        raise HostPolicyError("did:web has an empty host")
    if "@" in host or "/" in host or "\\" in host or any(c.isspace() for c in host):
        raise HostPolicyError("did:web host is not a bare hostname: %r" % host)

    literal = host
    if literal.startswith("[") and literal.endswith("]"):
        literal = literal[1:-1]
    try:
        address = ipaddress.ip_address(literal)
    except ValueError:
        address = None
    if address is not None:
        # w3c-ccg did:web: "the method-specific identifier MUST NOT contain an
        # IP address". No exception for "it looked convenient in a test".
        raise HostPolicyError("did:web must not address an IP literal: %r" % host)

    lowered = host.lower()
    if lowered in _BLOCKED_HOSTS or lowered.endswith(_BLOCKED_SUFFIXES):
        raise HostPolicyError("did:web must not address a local name: %r" % host)
    if not resolve_dns:
        return

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise HostPolicyError("did:web host does not resolve: %r (%s)" % (host, exc)) from None
    if not infos:
        raise HostPolicyError("did:web host resolves to nothing: %r" % host)
    for info in infos:
        sockaddr = info[4]
        addr_text = sockaddr[0]
        try:
            addr = ipaddress.ip_address(addr_text.split("%")[0])
        except ValueError:
            raise HostPolicyError("did:web host resolved to %r" % addr_text) from None
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified
                or not addr.is_global):
            raise HostPolicyError(
                "did:web host %r resolves to a non-public address %s" % (host, addr))


class _NoDowngradeRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if it stays https and stays on a public host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        if parts.scheme != "https":
            raise HostPolicyError(
                "did:web redirect left https: %r -> %r"
                % (getattr(req, "full_url", "<unknown>"), newurl))
        assert_public_host(parts.hostname or "")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read_capped(response, limit):
    chunks = []
    total = 0
    while True:
        chunk = response.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise DocumentTooLarge(
                "document exceeded %d bytes and was abandoned unparsed" % limit)
        chunks.append(chunk)
    return b"".join(chunks)


def _fetch_json(url, timeout, max_bytes=DEFAULT_MAX_DOCUMENT_BYTES):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise DIDError("did:web must resolve over https")
    assert_public_host(parts.hostname or "")

    request = urllib.request.Request(url, headers={
        "Accept": "application/did+ld+json, application/json",
        "User-Agent": "uibc-core-did/0.1",
    })
    opener = urllib.request.build_opener(_NoDowngradeRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:  # nosec B310 - guarded above
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != "https":
                raise HostPolicyError(
                    "did:web document arrived over %r after redirects" % final.scheme)
            assert_public_host(final.hostname or "", resolve_dns=False)
            body = _read_capped(response, max_bytes)
    except urllib.error.HTTPError as exc:
        raise DIDError("document at %s returned HTTP %s" % (url, exc.code)) from None
    except urllib.error.URLError as exc:
        raise DIDError("document at %s was unreachable: %s" % (url, exc.reason)) from None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DIDError("document at %s is not JSON: %s" % (url, exc)) from None


def resolve(did, timeout=10, fetcher=None, endpoint=None):
    """Resolve a DID to a document.

    `fetcher(url, timeout)` is injectable for tests. `endpoint` is used only by
    the registry-resolved China methods, and is never defaulted.
    """
    method, ident = parse(did)
    if method == "key":
        prefix, raw = _multibase_decode(ident)
        if prefix != _ED25519_MULTICODEC:
            raise DIDError("only ed25519-pub did:key is supported, got prefix %s"
                           % prefix.hex())
        if len(raw) != 32:
            raise DIDError("ed25519 did:key must carry 32 bytes, got %d" % len(raw))
        return did_key_document(raw, did)
    if method == "web":
        url = did_web_url(did)
        if not url.startswith("https://"):
            raise DIDError("did:web must resolve over https")
        document = (fetcher or _fetch_json)(url, timeout)
        if not isinstance(document, dict):
            raise DIDError("did:web document must be a JSON object")
        if document.get("id") != did:
            raise DIDError("document id %r does not match %r"
                           % (document.get("id"), did))
        return document
    from . import did_cn  # local import: did_cn imports this module's helpers
    if method in did_cn.METHODS:
        return did_cn.resolve(did, endpoint=endpoint, timeout=timeout, fetcher=fetcher)
    raise UnsupportedMethod(
        "did:%s has no published resolution rule in this build; supported: %s"
        % (method, ", ".join("did:" + m for m in SUPPORTED_METHODS + did_cn.METHODS)))


def document_ed25519_key(document):
    """Return (public_key_bytes, verification_method_id) from a DID document."""
    if not isinstance(document, dict):
        raise DIDError("DID document must be an object")
    methods = document.get("verificationMethod")
    if isinstance(methods, dict):
        methods = [methods]
    if not isinstance(methods, list):
        raise DIDError("DID document has no verificationMethod array")
    for method in methods:
        if not isinstance(method, dict):
            continue
        kid = method.get("id")
        multibase = method.get("publicKeyMultibase")
        if multibase:
            prefix, raw = _multibase_decode(multibase)
            if prefix == _ED25519_MULTICODEC and len(raw) == 32:
                return raw, kid
            continue
        jwk = method.get("publicKeyJwk")
        if isinstance(jwk, dict) and jwk.get("kty") == "OKP" \
                and jwk.get("crv") == "Ed25519":
            raw = _b64url_decode(jwk.get("x"))
            if len(raw) == 32:
                return raw, kid
            continue
        hex_key = method.get("publicKeyHex")
        if isinstance(hex_key, str) and len(hex_key) == 64:
            try:
                return bytes.fromhex(hex_key), kid
            except ValueError:
                continue
    raise DIDError("no usable Ed25519 verification method in DID document")


def resolve_ed25519_key(did, timeout=10, fetcher=None, endpoint=None):
    """Resolve a DID and return its Ed25519 key as (public_key, kid)."""
    return document_ed25519_key(resolve(did, timeout=timeout, fetcher=fetcher,
                                        endpoint=endpoint))


def verify_seal_with_did(did, identity, manifest, sig_b64, lifecycle=None,
                         timeout=10, fetcher=None):
    """Verify a UIBC Ed25519 seal against the key published by `did`.

    Returns (ok, kid). `ok=False` also covers an unresolvable or keyless DID --
    callers that need to tell the cases apart should call
    resolve_ed25519_key() themselves first.
    """
    public_key, kid = resolve_ed25519_key(did, timeout=timeout, fetcher=fetcher)
    return signing.ed_seal_verify(public_key, identity, manifest, sig_b64,
                                  lifecycle=lifecycle), kid
