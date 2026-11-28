"""Judge an MCP authorization observation (``mcp-authz-observation/v1``).

The corpus this reads is somebody else's: `vectors-mcp-authz`, 11 recorded
observations of what an MCP server publishes about its OAuth protection, each
with the finding codes a verifier must return. The shape is deliberately not
ours - one JSON file per member, a ``server`` block describing what the server
claims and an ``observed`` block describing what it actually answered.

What this module does and does not do:

* It judges the *surfaces* that were recorded: Protected Resource Metadata
  (RFC 9728), Authorization Server metadata (RFC 8414), the Bearer challenge
  (RFC 6750), the server's own authorization settings, and four extension
  surfaces (DPoP RFC 9449, workload identity federation, an OAuth Client ID
  Metadata Document, and an identity assertion grant).
* It does not verify signatures. The corpus carries JWTs decoded and says so;
  a verifier that pretended to check a signature it was never given would be
  claiming more than the record holds.
* Every finding is a named code, and the verdict is derived from the codes:
  no code means valid, any code means invalid. A verdict without codes would be
  an opinion.

The codes are the corpus's vocabulary, not ours. Reusing them is the point:
a consumer comparing two verifiers can line up finding by finding instead of
trusting two unrelated totals.
"""

import base64
import hashlib
import json
import os
from urllib.parse import urlsplit

SCHEMA = "mcp-authz-observation/v1"
REPORT_FORMAT = "uibc-mcp-authz-report/1"

ASYMMETRIC_ALGS = {
    "ES256", "ES384", "ES512", "RS256", "RS384", "RS512",
    "PS256", "PS384", "PS512", "EdDSA",
}

AS_REQUIRED_FIELDS = ("authorization_endpoint", "token_endpoint", "issuer")


def _b64u(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _sha256_b64u(text):
    return _b64u(hashlib.sha256(text.encode("utf-8")).digest())


def jwk_thumbprint(jwk):
    """RFC 7638 thumbprint: only the required members, lexicographic, no spaces."""
    if not isinstance(jwk, dict):
        raise ValueError("jwk is not an object")
    kty = jwk.get("kty")
    if kty == "EC":
        members = {"crv": jwk.get("crv"), "kty": "EC", "x": jwk.get("x"), "y": jwk.get("y")}
    elif kty == "RSA":
        members = {"e": jwk.get("e"), "kty": "RSA", "n": jwk.get("n")}
    elif kty == "OKP":
        members = {"crv": jwk.get("crv"), "kty": "OKP", "x": jwk.get("x")}
    else:
        raise ValueError("unsupported kty: %r" % (kty,))
    if any(v is None for v in members.values()):
        raise ValueError("jwk is missing a required member")
    canonical = json.dumps(members, sort_keys=True, separators=(",", ":"))
    return _b64u(hashlib.sha256(canonical.encode("utf-8")).digest())


# --- surfaces -------------------------------------------------------------


def _check_prm(server, observed, add):
    prm = observed.get("prm")
    if not isinstance(prm, dict) or prm.get("status") is None:
        return                                   # never observed is not "missing"
    status = prm.get("status")
    body = prm.get("body") if isinstance(prm.get("body"), dict) else None
    if status != 200 or body is None:
        add("prm-not-served")
        return
    resource = body.get("resource")
    if not isinstance(resource, str) or resource != server.get("resource"):
        add("prm-resource-not-identical")
    servers = body.get("authorization_servers")
    if not isinstance(servers, list) or not servers:
        add("prm-authorization-servers-missing")
    methods = body.get("bearer_methods_supported")
    if not isinstance(methods, list) or "header" not in methods:
        add("prm-bearer-header-missing")
    scopes = body.get("scopes_supported")
    if isinstance(scopes, list) and "offline_access" in scopes:
        add("prm-scope-offline-access")


def _challenge_scheme(header_value):
    if not isinstance(header_value, str) or not header_value.strip():
        return None
    first = header_value.strip().split()[0]
    return first.split("=")[0].lower()


def _challenge_params(header_value):
    """The auth-params we care about, from one WWW-Authenticate value."""
    out = {}
    if not isinstance(header_value, str):
        return out
    for name in ("resource_metadata", "scope", "error"):
        marker = name + "="
        idx = header_value.find(marker)
        if idx < 0:
            continue
        rest = header_value[idx + len(marker):].lstrip()
        if rest[:1] == '"':
            end = rest.find('"', 1)
            out[name] = rest[1:end] if end > 0 else rest[1:]
        else:
            out[name] = rest.split(",")[0].strip()
    return out


def _check_challenge(observed, add):
    unauth = observed.get("unauthenticated") or {}
    under = observed.get("under_scoped") or {}
    wa = unauth.get("www_authenticate")
    scheme = _challenge_scheme(wa)
    if unauth.get("status") == 401 and scheme is None:
        add("challenge-missing")
    elif unauth.get("status") == 401 and scheme != "bearer":
        add("challenge-scheme-not-bearer")
    params = _challenge_params(wa)
    # Only a Bearer challenge carries the auth-params RFC 6750 defines. Reading
    # them out of a Basic header would invent findings the server never made.
    if unauth.get("status") == 401 and scheme == "bearer":
        if "resource_metadata" not in params:
            add("challenge-resource-metadata-missing")
        scope = params.get("scope") or ""
        if "offline_access" in scope.replace(",", " ").split():
            add("challenge-scope-offline-access")
    under_status = under.get("status")
    if under_status == 200:
        add("required-scope-not-enforced")
    elif under_status == 401:
        add("challenge-insufficient-scope-not-403")
    if unauth.get("status") in (200, 204, 206):
        add("unauthenticated-request-accepted")


def _check_as_metadata(server, observed, add):
    asm = observed.get("as_metadata") or {}
    body = asm.get("body")
    if asm.get("status") is None:
        return
    if not isinstance(body, dict):
        add("as-metadata-not-json")
        return
    for field in AS_REQUIRED_FIELDS:
        if not isinstance(body.get(field), str) or not body.get(field):
            add("as-required-field-missing")
            break
    issuer = body.get("issuer")
    if isinstance(issuer, str) and issuer != server.get("issuer"):
        add("as-issuer-mismatch")
    prm_body = (observed.get("prm") or {}).get("body")
    if isinstance(prm_body, dict):
        advertised = prm_body.get("authorization_servers")
        if isinstance(advertised, list) and isinstance(issuer, str) and issuer not in advertised:
            add("as-issuer-not-in-prm")
    if "S256" not in (body.get("code_challenge_methods_supported") or []):
        add("as-pkce-s256-missing")
    if "code" not in (body.get("response_types_supported") or []):
        add("as-response-type-code-missing")
    registration = (server.get("registration") or {})
    if registration.get("enabled") and not isinstance(body.get("registration_endpoint"), str):
        add("as-registration-endpoint-missing")


def _check_settings(server, observed, add):
    resource = server.get("resource")
    if not isinstance(resource, str) or not resource:
        add("config-resource-url-missing")
    required = set(server.get("required_scopes") or [])
    obtainable = set((server.get("registration") or {}).get("valid_scopes") or [])
    body = (observed.get("as_metadata") or {}).get("body")
    if isinstance(body, dict):
        obtainable |= set(body.get("scopes_supported") or [])
    if required - obtainable:
        add("config-scopes-not-obtainable")


def _check_dpop(observed, add, evaluated_at):
    dpop = observed.get("dpop")
    if not isinstance(dpop, dict):
        return
    proof = dpop.get("proof") or {}
    header = proof.get("header") or {}
    claims = proof.get("claims") or {}
    if header.get("typ") != "dpop+jwt":
        add("dpop-proof-typ-invalid")
    alg = header.get("alg")
    if isinstance(alg, str) and alg not in ASYMMETRIC_ALGS:
        add("dpop-proof-alg-not-asymmetric")
    jwk = header.get("jwk") if isinstance(header.get("jwk"), dict) else {}
    if "d" in jwk:
        add("dpop-proof-key-private")
    if claims.get("htu") != dpop.get("request_url"):
        add("dpop-htu-mismatch")
    if claims.get("htm") != dpop.get("request_method"):
        add("dpop-htm-mismatch")
    token = dpop.get("access_token")
    if isinstance(token, str) and claims.get("ath") != _sha256_b64u(token):
        add("dpop-ath-mismatch")
    cnf = ((dpop.get("token_claims") or {}).get("cnf") or {})
    jkt = cnf.get("jkt")
    if isinstance(jkt, str) and jwk:
        try:
            computed = jwk_thumbprint(jwk)
        except ValueError:
            computed = None
        if computed is not None and computed != jkt:
            add("dpop-key-binding-mismatch")
    jti = claims.get("jti")
    if isinstance(jti, str) and jti in (dpop.get("seen_jtis") or []):
        add("dpop-proof-replayed")


def _check_workload_federation(observed, add, evaluated_at):
    wif = observed.get("workload_federation")
    if not isinstance(wif, dict):
        return
    claims = (wif.get("subject_token") or {}).get("claims") or {}
    if claims.get("iss") not in (wif.get("trusted_issuers") or []):
        add("wif-issuer-untrusted")
    if claims.get("aud") != wif.get("expected_audience"):
        add("wif-audience-mismatch")
    exp = claims.get("exp")
    if isinstance(exp, (int, float)) and evaluated_at is not None and exp <= evaluated_at:
        add("wif-token-expired")
    sub = claims.get("sub")
    bindings = wif.get("bindings") or {}
    if isinstance(sub, str) and sub not in bindings:
        add("wif-subject-unbound")
    granted = set(wif.get("granted_scopes") or [])
    allowed = set(bindings.get(sub) or []) if isinstance(sub, str) else set()
    if granted and granted - allowed:
        add("wif-scope-widened")


def _clean_https_url(value):
    if not isinstance(value, str):
        return False
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.netloc:
        return False
    if parts.fragment or parts.query or parts.username or parts.password:
        return False
    if ".." in parts.path or parts.path.startswith("//"):
        return False
    return True


def _check_client_metadata(observed, add):
    cm = observed.get("client_metadata")
    if not isinstance(cm, dict):
        return
    client_id = cm.get("client_id")
    document = cm.get("document") if isinstance(cm.get("document"), dict) else {}
    if not _clean_https_url(client_id):
        add("cimd-client-id-not-a-clean-https-url")
    if document.get("client_id") != client_id:
        add("cimd-document-client-id-mismatch")
    redirect = cm.get("redirect_uri")
    if redirect is not None and redirect not in (document.get("redirect_uris") or []):
        add("cimd-redirect-uri-unregistered")
    as_extra = cm.get("as_metadata") if isinstance(cm.get("as_metadata"), dict) else {}
    if as_extra.get("client_id_metadata_document_supported") is not True:
        add("cimd-support-not-advertised")
    method = document.get("token_endpoint_auth_method")
    if "client_secret" in document or (method is not None and method != "none"):
        add("cimd-symmetric-authentication")


def _check_id_jag(observed, add, evaluated_at):
    ij = observed.get("id_jag")
    if not isinstance(ij, dict):
        return
    assertion = ij.get("assertion") or {}
    header = assertion.get("header") or {}
    claims = assertion.get("claims") or {}
    if header.get("typ") != "oauth-id-jag+jwt":
        add("id-jag-typ-invalid")
    if claims.get("aud") != ij.get("resource_as_issuer"):
        add("id-jag-audience-mismatch")
    if claims.get("client_id") != ij.get("requesting_client_id"):
        add("id-jag-client-mismatch")
    exp = claims.get("exp")
    if isinstance(exp, (int, float)) and evaluated_at is not None and exp <= evaluated_at:
        add("id-jag-expired")
    if not isinstance(claims.get("jti"), str) or not claims.get("jti"):
        add("id-jag-jti-missing")


# --- entry ----------------------------------------------------------------


def evaluate(observation):
    """Return ``(verdict, sorted codes)`` for one observation record."""
    if not isinstance(observation, dict):
        raise ValueError("observation is not an object")
    if observation.get("schema") != SCHEMA:
        raise ValueError("schema is %r, expected %r"
                         % (observation.get("schema"), SCHEMA))
    codes = set()

    def add(code):
        codes.add(code)

    server = observation.get("server") if isinstance(observation.get("server"), dict) else {}
    observed = observation.get("observed") if isinstance(observation.get("observed"), dict) else {}
    evaluated_at = observation.get("evaluated_at")

    _check_settings(server, observed, add)
    _check_prm(server, observed, add)
    _check_challenge(observed, add)
    _check_as_metadata(server, observed, add)
    _check_dpop(observed, add, evaluated_at)
    _check_workload_federation(observed, add, evaluated_at)
    _check_client_metadata(observed, add)
    _check_id_jag(observed, add, evaluated_at)

    verdict = "invalid" if codes else "valid"
    return verdict, sorted(codes)


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def evaluate_file(path):
    return evaluate(load(path))


def iter_members(corpus_dir):
    """Yield ``(member_id, path)`` for observation files named by a manifest."""
    manifest_path = os.path.join(corpus_dir, "MANIFEST.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        for member in manifest.get("vectors") or []:
            path = os.path.join(corpus_dir, member["file"])
            yield member["id"], path
        return
    for name in sorted(os.listdir(corpus_dir)):
        if name.endswith(".json") and name != "MANIFEST.json":
            yield os.path.splitext(name)[0], os.path.join(corpus_dir, name)
