"""Certificates (route step 10) - v0.1 PROPOSAL, pure stdlib.

A certificate is a SIGNED STATEMENT that a package passed verification:
it carries the evidence_root, the signer key_id, an optional expiry, and an
optional binding to a subject package. It is Evidence-with-signature, NOT
Trust (archive discipline: Fact != Evidence != ... != Trust).

v0.1 honest scope:
1. HMAC-SHA256 (symmetric) - same boundary as v0.2 seals: only key holders
   can issue AND verify. Third-party verifiable certs are the Ed25519/v0.3
   target. Do NOT represent this as "publicly verifiable certification".
2. "XLGD Certified" branding is explicitly OUT OF SCOPE (route note 17:
   certification must be cautious). This module issues machine-checkable
   attestation objects, not brand endorsements.
3. Certificate revocation is NOT in v0.1 (revocation overlay at the gate
   layer covers packages; cert revocation list is a v0.2 target).
4. Expiry uses the local clock - timestamps are not independently anchored
   (same limitation as the verifier report).
"""

import base64
import datetime
import hashlib
import hmac
import json
import os
import uuid

from .signing import ALGORITHM, key_id
from . import SPEC_VERSION

CERT_SCHEMA = "uibc-certificate/0.1"


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sign(key: bytes, body: dict) -> str:
    return base64.b64encode(
        hmac.new(key, _canonical(body), hashlib.sha256).digest()).decode("ascii")


def issue_certificate(key: bytes, identity: dict, manifest: dict,
                      expires_at: str = None, statement: str = None,
                      cert_id: str = None) -> dict:
    """Issue a certificate binding agent identity to an evidence root."""
    body = {
        "schema": CERT_SCHEMA,
        "spec_version": SPEC_VERSION,
        "certificate_id": cert_id or f"c-{uuid.uuid4()}",
        "algorithm": ALGORITHM,
        "key_id": key_id(key),
        "subject_agent": identity.get("agent_id"),
        "owner": identity.get("owner"),
        "evidence_root": manifest.get("evidence_root"),
        "issued_at": datetime.datetime.now(datetime.timezone.utc)
                               .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires_at,
        "statement": statement or ("package with this evidence_root passed "
                                   "verification at issue time"),
    }
    body["signature"] = _sign(key, body)
    return body


def verify_certificate(key: bytes, cert: dict,
                       package_dir: str = None, now_utc: str = None) -> dict:
    """Verify a certificate. Returns a scoped report (never a trust claim).

    package_dir: if given, additionally checks the cert is bound to that
                 package (evidence_root equality).
    now_utc:     override 'now' for expiry check (ISO8601 Z); tests use this
                 to travel in time deterministically.
    """
    checks = []

    def record(cid, name, passed, detail=""):
        checks.append({"id": cid, "name": name,
                       "result": "PASS" if passed else "FAIL", "detail": detail})
        return passed

    ok = True
    for field in ("schema", "certificate_id", "algorithm", "key_id",
                  "subject_agent", "evidence_root", "issued_at", "signature"):
        if not record("C1", "required fields", bool(cert.get(field)),
                      f"missing field {field!r}" if not cert.get(field) else "present"):
            ok = False
            break

    if ok:
        ok &= record("C2", "schema", cert["schema"] == CERT_SCHEMA,
                     f"{cert['schema']!r}")
        ok &= record("C3", "algorithm", cert["algorithm"] == ALGORITHM,
                     f"{cert['algorithm']!r}")
        kid = key_id(key)
        ok &= record("C4", "signer key", cert["key_id"] == kid,
                     "signer key mismatch: not issued by this key")
        body = {k: v for k, v in cert.items() if k != "signature"}
        try:
            mac = base64.b64decode(cert["signature"], validate=True)
            valid = hmac.compare_digest(
                hmac.new(key, _canonical(body), hashlib.sha256).digest(), mac)
        except Exception:
            valid = False
        ok &= record("C5", "signature", valid,
                     "signature invalid: certificate body was modified")

    if ok and cert.get("expires_at"):
        now = now_utc or datetime.datetime.now(datetime.timezone.utc)\
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        expired = now > cert["expires_at"]
        ok &= record("C6", "expiry", not expired,
                     f"expired at {cert['expires_at']}" if expired
                     else f"valid until {cert['expires_at']}")

    if ok and package_dir is not None:
        with open(os.path.join(package_dir, "manifest.json"),
                  "r", encoding="utf-8") as f:
            root = json.load(f).get("evidence_root")
        ok &= record("C7", "package binding", root == cert.get("evidence_root"),
                     f"cert root {cert.get('evidence_root')!r} vs package root {root!r}")

    return {
        "result": "PASS" if ok else "FAIL",
        "certificate_id": cert.get("certificate_id"),
        "subject_agent": cert.get("subject_agent"),
        "checks": checks,
        "scope": "Certificate signature and (optionally) expiry and package "
                 "binding. NOT checked: certificate revocation (v0.2 target), "
                 "independent timestamp anchoring, behavioral quality.",
        "statement_bound": cert.get("statement"),
    }
