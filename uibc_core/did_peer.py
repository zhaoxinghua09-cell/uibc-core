# -*- coding: utf-8 -*-
"""did:peer — the peer-to-peer DID method (DIF Peer DID Method Specification).

Why this method is worth supporting when the rest of this module fetches
documents from registries or the web: a ``did:peer`` document is **derived from
the identifier itself**. No endpoint, no registry, no network. That makes it the
one DID method whose resolution can be reproduced entirely offline, by anyone,
years later — which is exactly the property the rest of this project claims to
care about.

Scope, stated rather than implied (Peer DID spec, "Method Specific Identifier"
ABNF plus the Method 0/2 generation rules):

* **numalgo 0** — supported. ``did:peer:0z<multibase ed25519 key>``; genesis doc
  is empty and every privilege belongs to that key.
* **numalgo 2** — supported. ``did:peer:2`` followed by ``.<purpose><z-multibase>``
  key elements and ``.S<base64url>`` service elements.
* **numalgo 1** — not resolvable alone: its numeric basis is the SHA-256 of a
  genesis document that the DID does not carry. Returns ``NotSelfResolving``.
* **numalgo 3** — not resolvable alone: it hashes a numalgo-2 DID that the
  caller is expected to have received earlier. Returns ``NotSelfResolving``.
* **numalgo 4** — short form hashes the long form; this build does not decode
  the long form (the exact bytes hashed are underspecified across the several
  revisions of the text), so it returns ``NotSelfResolving`` with that reason
  rather than a guess.

A deliberate omission in the numalgo 0 document: **no ``keyAgreement`` entry**.
Deriving the X25519 key from an Ed25519 *public* key requires the birational
map ourselves; emitting a plausible-looking but wrong key agreement key would
be worse than not emitting one. The signing relationships are exact, and that
is what this module's callers verify.
"""
import base64
import json

from .did import (DIDError, NotSelfResolving, _ED25519_MULTICODEC,
                  _X25519_MULTICODEC, _b58decode)

METHOD = "peer"

METHODS = (METHOD,)

# Verification relationship for each purpose code (spec, "Purpose Codes").
_PURPOSE_RELATIONSHIP = {
    "A": "assertionMethod",
    "E": "keyAgreement",
    "V": "authentication",
    "I": "capabilityInvocation",
    "D": "capabilityDelegation",
}

# Service common-string abbreviations (spec, "Common String Abbreviations").
_SERVICE_KEYS = {"t": "type", "s": "serviceEndpoint", "r": "routingKeys", "a": "accept"}
_SERVICE_TYPES = {"dm": "DIDCommMessaging"}

_CONTEXT = ["https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/multikey/v1"]


def _split_ident(identifier):
    """Return (numalgo, rest) or raise DIDError if the prefix is not peer."""
    prefix = "did:peer:"
    if not isinstance(identifier, str) or not identifier.startswith(prefix):
        raise DIDError("not a did:peer identifier: %r" % (identifier,))
    rest = identifier[len(prefix):]
    if not rest:
        raise DIDError("did:peer needs a method-specific identifier")
    return rest[0], rest[1:]


def _decode_key(multibase, did, element):
    if not multibase.startswith("z"):
        raise DIDError("%s: key material must be z-base58btc, got %r"
                       % (did, multibase[:1]))
    try:
        raw = _b58decode(multibase[1:])
    except DIDError as exc:
        raise DIDError("%s: %s" % (did, exc)) from None
    if len(raw) < 2:
        raise DIDError("%s: %s carries no multicodec prefix" % (did, element))
    return raw[:2], raw[2:]


def _umbrella_document(did, key_multibase):
    key_id = did + "#key-1"
    return {
        "@context": _CONTEXT,
        "id": did,
        "verificationMethod": [{
            "id": key_id,
            "type": "Multikey",
            "controller": did,
            "publicKeyMultibase": key_multibase,
        }],
        "authentication": [key_id],
        "assertionMethod": [key_id],
        "capabilityInvocation": [key_id],
        "capabilityDelegation": [key_id],
    }


def _numalgo_0(did, rest):
    if not rest.startswith("z"):
        raise DIDError("%s: numalgo 0 requires a z-base58btc numeric basis" % did)
    multibase = rest
    prefix, raw = _decode_key(multibase, did, "numalgo 0")
    if prefix != _ED25519_MULTICODEC:
        raise DIDError("%s: numalgo 0 supports ed25519-pub only, got multicodec %s"
                       % (did, prefix.hex()))
    if len(raw) != 32:
        raise DIDError("%s: ed25519 key must be 32 bytes, got %d" % (did, len(raw)))
    # The spec makes this DID functionally equivalent to the did:key value for
    # the same key, so the two documents should agree on the key material.
    return _umbrella_document(did, multibase)


def _decode_service(did, blob, index):
    if not blob:
        raise DIDError("%s: empty service element" % did)
    padding = "=" * (-len(blob) % 4)
    try:
        raw = base64.urlsafe_b64decode(blob + padding)
    except (ValueError, TypeError) as exc:
        raise DIDError("%s: service element %d is not base64url: %s"
                       % (did, index, exc)) from None
    try:
        service = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise DIDError("%s: service element %d is not JSON: %s"
                       % (did, index, exc)) from None
    if not isinstance(service, dict):
        raise DIDError("%s: service element %d must be a JSON object" % (did, index))
    return _unabbreviate(service)


def _unabbreviate(value):
    """Expand the spec's abbreviations back to DID Core service names."""
    if isinstance(value, list):
        return [_unabbreviate(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            name = _SERVICE_KEYS.get(k, k)
            if name == "type" and isinstance(v, str):
                v = _SERVICE_TYPES.get(v, v)
            out[name] = _unabbreviate(v)
        return out
    return value


def _numalgo_2(did, rest):
    if not rest.startswith("."):
        raise DIDError("%s: numalgo 2 requires '.'-separated elements" % did)
    elements = rest.split(".")[1:]
    document = {"@context": _CONTEXT, "id": did, "verificationMethod": []}
    key_count = 0
    service_count = 0
    for element in elements:
        if not element:
            raise DIDError("%s: empty element in numalgo 2 identifier" % did)
        purpose, body = element[0], element[1:]
        if purpose == "S":
            service_count += 1
            service = _decode_service(did, body, service_count)
            if "id" not in service:
                service["id"] = "#service" if service_count == 1 else "#service-%d" % (service_count - 1)
            document.setdefault("service", []).append(service)
            continue
        relationship = _PURPOSE_RELATIONSHIP.get(purpose)
        if relationship is None:
            raise DIDError("%s: purpose code %r is not in A/E/V/I/D/S" % (did, purpose))
        prefix, raw = _decode_key(body, did, "purpose %s" % purpose)
        if purpose == "E" and prefix != _X25519_MULTICODEC:
            raise DIDError("%s: encryption element must be x25519-pub, got %s"
                           % (did, prefix.hex()))
        key_count += 1
        key_id = "%s#key-%d" % (did, key_count)
        document["verificationMethod"].append({
            "id": key_id,
            "type": "Multikey",
            "controller": did,
            "publicKeyMultibase": body,
        })
        document.setdefault(relationship, []).append(key_id)
    if not key_count:
        raise DIDError("%s: numalgo 2 needs at least one key element" % did)
    return document


def resolve(identifier):
    """Resolve a did:peer to a DID document. Offline, no fetcher, no endpoint."""
    numalgo, rest = _split_ident(identifier)
    if numalgo == "0":
        return _numalgo_0(identifier, rest)
    if numalgo == "2":
        return _numalgo_2(identifier, rest)
    if numalgo == "1":
        raise NotSelfResolving(
            "%s: numalgo 1 is the SHA-256 of a genesis document the DID does not "
            "carry; resolution requires that document from the DID's creator" % identifier)
    if numalgo == "3":
        raise NotSelfResolving(
            "%s: numalgo 3 hashes a numalgo-2 DID exchanged earlier; it cannot be "
            "resolved on its own (the peer must supply the long form)" % identifier)
    if numalgo == "4":
        raise NotSelfResolving(
            "%s: numalgo 4 short form is a hash over a long form; this build does "
            "not decode the long form, so the document is unavailable here" % identifier)
    raise DIDError("%s: numalgo %r is not defined by the peer DID specification"
                   % (identifier, numalgo))


def matrix():
    """Capability table for docs and tests (kept next to the code it describes)."""
    return {
        "peer": {
            "0": "supported: ed25519 inception key, offline",
            "1": "not self-resolving: numeric basis is a hash of a genesis doc",
            "2": "supported: A/E/V/I/D key elements plus S services, offline",
            "3": "not self-resolving: hash of a numalgo-2 DID",
            "4": "not self-resolving here: long form decode not implemented",
        },
    }
