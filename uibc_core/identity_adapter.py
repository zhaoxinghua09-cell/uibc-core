"""One interface for "who is this, and what does the proof hang on", per scheme.

The claim this project makes is that verification is identity-agnostic: the
judgement layer should not care whether the subject is a `did:key`, a corporate
directory entry, or an X.509 certificate. That claim is only worth something if
there is an interface, so here it is -- two implementations, one honest each.

What an adapter is allowed to say is deliberately narrow:

    VERIFIED       this identifier controls this key, per this document, and the
                   document digest is pinned in the returned evidence
    INCONCLUSIVE   the binding parsed but the surrounding trust was not evaluated
                   (no chain built, no anchor checked) -- the PKIX adapter stops here
    INVALID        the identifier is malformed under its own scheme's grammar
    UNSUPPORTED    this adapter does not do this scheme, or its dependency is absent
    UNRESOLVED     the scheme is supported and the identifier is well-formed, but
                   the document could not be fetched (no endpoint, network down)

Note what is *not* in that list: no adapter may return `REVOKED` or `EXPIRED`,
because resolving an identifier is not a statement about the subject's standing
over time. Those belong to the verification path, not the identity path.
"""
from dataclasses import dataclass, field, asdict
import hashlib
import json

from . import did
from . import did_cn
from . import interop_result as ir

try:  # read-only X.509 parsing; no chain building either way
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    _HAS_PKIX = True
except Exception:  # noqa: BLE001 - absence is a supported state, not a failure
    _HAS_PKIX = False

__all__ = [
    "AdapterUnavailable", "IdentityRecord", "IdentityAdapter", "DIDAdapter",
    "PKIXAdapter", "ADAPTERS", "check", "state_for",
]


class AdapterUnavailable(Exception):
    """The adapter cannot answer for this input: wrong scheme, or dependency absent."""


@dataclass
class IdentityRecord:
    identifier: str
    adapter: str
    state: str
    key_material: dict = field(default_factory=dict)
    document_sha256: str = ""
    notes: str = ""

    def as_evidence(self, issuer=None):
        """The only evidence an identity adapter can honestly offer: a pinned digest."""
        if not self.document_sha256:
            raise ir.ResultError("no document digest: nothing to pin")
        return {
            "id": "%s#document" % self.adapter,
            "type": "identity-document",
            "issuer": issuer or self.identifier,
            "digest": "sha256:" + self.document_sha256,
        }

    def as_dict(self):
        return asdict(self)


class IdentityAdapter:
    name = "abstract"
    schemes = ()

    def can_handle(self, identifier):
        return str(identifier).startswith(self.schemes)

    def check(self, identifier, **kwargs):  # pragma: no cover - interface
        raise NotImplementedError


class DIDAdapter(IdentityAdapter):
    name = "did"
    schemes = ("did:",)

    def check(self, identifier, timeout=5, fetcher=None, endpoint=None, **kwargs):
        try:
            document = did.resolve(identifier, timeout=timeout, fetcher=fetcher,
                                   endpoint=endpoint)
        except did.UnsupportedMethod as exc:
            return IdentityRecord(identifier, self.name, "UNSUPPORTED",
                                  notes=str(exc))
        except did_cn.RegistryEndpointRequired as exc:
            # Well-formed, supported, nothing to fetch from. This used to surface as
            # INVALID because it arrived as a DIDError subclass -- the adapter is
            # what caught the collapse, which is the reason the vocabulary exists.
            return IdentityRecord(identifier, self.name, "UNRESOLVED", notes=str(exc))
        except did_cn.IdentifierError as exc:
            # Same collapse, second instance (found 2026-11-24): the live platform
            # hands out `did:cn:agent:<base58>`, which is absent from the published
            # ABNF, so validate() refuses it and the adapter called it INVALID --
            # i.e. told a correctly-allocated agent that its identifier was wrong.
            # Shape is recognisable, allocation is not; so: UNRESOLVED, labelled.
            try:
                did_cn.validate_live_agent_id(identifier)
            except Exception:  # noqa: BLE001 - not the live form either
                return IdentityRecord(identifier, self.name, "INVALID", notes=str(exc))
            return IdentityRecord(
                identifier, self.name, "UNRESOLVED",
                notes=("live did:cn agent form (not in the published ABNF); "
                       "resolution needs the registry endpoint; %s" % exc))
        except did.NotSelfResolving as exc:
            # Third instance of the same collapse (after RegistryEndpointRequired and
            # the live did:cn form): well-formed but not derivable from the identifier
            # alone is not "the identifier is wrong".
            return IdentityRecord(identifier, self.name, "UNRESOLVED", notes=str(exc))
        except did.DIDError as exc:
            return IdentityRecord(identifier, self.name, "INVALID", notes=str(exc))
        except Exception as exc:  # noqa: BLE001 - network and endpoint problems
            return IdentityRecord(identifier, self.name, "UNRESOLVED",
                                  notes="%s: %s" % (type(exc).__name__, exc))
        digest = hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        key = {}
        try:
            key = did.document_ed25519_key(document) or {}
        except Exception as exc:  # noqa: BLE001
            return IdentityRecord(identifier, self.name, "INCONCLUSIVE",
                                  document_sha256=digest,
                                  notes="document resolved, key not extractable: %s" % exc)
        method = identifier.split(":", 2)[1] if ":" in identifier else ""
        note = ""
        if method in did_cn.METHODS:
            note = "resolved through the registry endpoint the caller supplied"
        return IdentityRecord(identifier, self.name, "VERIFIED",
                              key_material=key, document_sha256=digest, notes=note)


class PKIXAdapter(IdentityAdapter):
    name = "pkix"
    schemes = ("-----BEGIN CERTIFICATE",)

    def check(self, identifier, **kwargs):
        if not _HAS_PKIX:
            return IdentityRecord(identifier, self.name, "UNSUPPORTED",
                                  notes="cryptography not installed: parsing is unavailable")
        try:
            cert = x509.load_pem_x509_certificate(
                identifier.encode() if isinstance(identifier, str) else identifier)
        except Exception as exc:  # noqa: BLE001
            return IdentityRecord(identifier, self.name, "INVALID",
                                  notes="not a parseable PEM certificate: %s" % exc)
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat)
        spki = cert.public_key().public_bytes(
            encoding=Encoding.DER, format=PublicFormat.SubjectPublicKeyInfo)
        digest = hashlib.sha256(spki).hexdigest()
        return IdentityRecord(
            identifier.strip(), self.name, "INCONCLUSIVE",
            key_material={"type": type(cert.public_key()).__name__,
                          "spki_sha256": digest},
            document_sha256=digest,
            notes=("parsed only: no chain built, no trust anchor evaluated, no "
                   "revocation fetched -- so the binding is readable but not judged"))


ADAPTERS = (DIDAdapter(), PKIXAdapter())


def check(identifier, **kwargs):
    """Dispatch to the first adapter that claims the scheme."""
    for adapter in ADAPTERS:
        if adapter.can_handle(identifier):
            return adapter.check(identifier, **kwargs)
    raise AdapterUnavailable("no adapter handles this identifier: %r"
                             % (str(identifier)[:40],))


def state_for(exc):
    """The mapping an adapter failure earns. Kept in one place so it cannot drift."""
    if isinstance(exc, AdapterUnavailable):
        return "UNSUPPORTED"
    if isinstance(exc, ir.ResultError):
        return "INCONCLUSIVE"
    return "UNRESOLVED"
