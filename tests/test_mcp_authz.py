"""Judge an MCP authorization observation, and say why.

The corpus these shapes come from is somebody else's (`vectors-mcp-authz`,
11 members with an answer key). Those files are not vendored here - a test that
reads a neighbour's fixtures goes red when the neighbour edits them, which
teaches nothing about this code. What is tested here is the rule set: each
case below is built inline, and each one is a single surface saying one wrong
thing, so a failure names the surface rather than a diff.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from uibc_core import mcp_authz  # noqa: E402

SERVER = {
    "issuer": "https://auth.example.test",
    "registration": {"enabled": True, "valid_scopes": ["mcp:read", "mcp:write"]},
    "required_scopes": ["mcp:read"],
    "resource": "https://mcp.example.test/mcp",
}

AS_BODY = {
    "authorization_endpoint": "https://auth.example.test/authorize",
    "token_endpoint": "https://auth.example.test/token",
    "issuer": "https://auth.example.test",
    "registration_endpoint": "https://auth.example.test/register",
    "code_challenge_methods_supported": ["S256"],
    "response_types_supported": ["code"],
    "scopes_supported": ["mcp:read", "mcp:write"],
}

PRM_BODY = {
    "resource": "https://mcp.example.test/mcp",
    "authorization_servers": ["https://auth.example.test"],
    "bearer_methods_supported": ["header"],
    "scopes_supported": ["mcp:read", "mcp:write"],
}

GOOD_CHALLENGE = ('Bearer resource_metadata='
                  '"https://mcp.example.test/.well-known/oauth-protected-resource/mcp", '
                  'scope="mcp:read"')

JWK = {"crv": "P-256", "kty": "EC", "x": "x-value", "y": "y-value"}
TOKEN = "synthetic-access-token-0001"


def observation(**observed):
    base = {
        "schema": mcp_authz.SCHEMA,
        "evaluated_at": 1790000000,
        "server": dict(SERVER),
        "observed": {
            "prm": {"status": 200, "body": dict(PRM_BODY)},
            "as_metadata": {"status": 200, "body": dict(AS_BODY)},
            "unauthenticated": {"status": 401, "www_authenticate": GOOD_CHALLENGE},
            "under_scoped": {"status": 403, "www_authenticate": 'Bearer error="insufficient_scope"'},
        },
    }
    for key, value in observed.items():
        base["observed"][key] = value
    return base


class TestCleanSurface(unittest.TestCase):
    def test_every_surface_agreeing_is_valid_with_no_codes(self):
        verdict, codes = mcp_authz.evaluate(observation())
        self.assertEqual(verdict, "valid")
        self.assertEqual(codes, [])

    def test_a_code_makes_the_verdict_invalid(self):
        verdict, codes = mcp_authz.evaluate(
            observation(prm={"status": 404}))
        self.assertEqual(verdict, "invalid")
        self.assertIn("prm-not-served", codes)


class TestProtectedResourceMetadata(unittest.TestCase):
    def test_trailing_slash_is_a_different_resource(self):
        body = dict(PRM_BODY, resource=PRM_BODY["resource"] + "/")
        _, codes = mcp_authz.evaluate(observation(prm={"status": 200, "body": body}))
        self.assertIn("prm-resource-not-identical", codes)

    def test_an_empty_server_list_names_nobody(self):
        body = dict(PRM_BODY, authorization_servers=[])
        _, codes = mcp_authz.evaluate(observation(prm={"status": 200, "body": body}))
        self.assertIn("prm-authorization-servers-missing", codes)

    def test_body_as_a_bearer_method_is_not_the_header(self):
        body = dict(PRM_BODY, bearer_methods_supported=["body"])
        _, codes = mcp_authz.evaluate(observation(prm={"status": 200, "body": body}))
        self.assertIn("prm-bearer-header-missing", codes)

    def test_offline_access_in_the_protected_resource_scopes(self):
        body = dict(PRM_BODY, scopes_supported=["mcp:read", "offline_access"])
        _, codes = mcp_authz.evaluate(observation(prm={"status": 200, "body": body}))
        self.assertIn("prm-scope-offline-access", codes)

    def test_never_observed_is_not_the_same_as_missing(self):
        obs = observation()
        del obs["observed"]["prm"]
        _, codes = mcp_authz.evaluate(obs)
        self.assertNotIn("prm-not-served", codes)


class TestChallenge(unittest.TestCase):
    def test_a_401_without_a_challenge(self):
        _, codes = mcp_authz.evaluate(
            observation(unauthenticated={"status": 401, "www_authenticate": ""}))
        self.assertIn("challenge-missing", codes)

    def test_a_basic_challenge_is_named_as_such(self):
        _, codes = mcp_authz.evaluate(
            observation(unauthenticated={"status": 401, "www_authenticate": 'Basic realm="mcp"'}))
        self.assertIn("challenge-scheme-not-bearer", codes)
        self.assertNotIn("challenge-resource-metadata-missing", codes,
                         "auth-params read out of a Basic header are invented findings")

    def test_serving_a_request_with_no_token(self):
        _, codes = mcp_authz.evaluate(observation(unauthenticated={"status": 200}))
        self.assertIn("unauthenticated-request-accepted", codes)

    def test_answering_an_under_scoped_token_401_instead_of_403(self):
        _, codes = mcp_authz.evaluate(
            observation(under_scoped={"status": 401, "www_authenticate": 'Bearer error="invalid_token"'}))
        self.assertIn("challenge-insufficient-scope-not-403", codes)

    def test_a_scope_the_server_cannot_grant(self):
        server = dict(SERVER, required_scopes=["mcp:read", "mcp:write"],
                      registration={"enabled": True, "valid_scopes": ["mcp:read"]})
        obs = observation()
        obs["server"] = server
        obs["observed"]["as_metadata"]["body"] = dict(AS_BODY, scopes_supported=["mcp:read"])
        _, codes = mcp_authz.evaluate(obs)
        self.assertIn("config-scopes-not-obtainable", codes)


class TestAuthorizationServerMetadata(unittest.TestCase):
    def test_a_body_that_is_not_json(self):
        _, codes = mcp_authz.evaluate(observation(as_metadata={"status": 200, "body": "not json"}))
        self.assertIn("as-metadata-not-json", codes)

    def test_pkce_without_s256_and_no_code_response_type(self):
        body = dict(AS_BODY, code_challenge_methods_supported=["plain"],
                    response_types_supported=["token"])
        _, codes = mcp_authz.evaluate(observation(as_metadata={"status": 200, "body": body}))
        self.assertIn("as-pkce-s256-missing", codes)
        self.assertIn("as-response-type-code-missing", codes)

    def test_an_issuer_the_protected_resource_does_not_name(self):
        body = dict(AS_BODY, issuer="https://other.example.test")
        _, codes = mcp_authz.evaluate(observation(as_metadata={"status": 200, "body": body}))
        self.assertIn("as-issuer-mismatch", codes)
        self.assertIn("as-issuer-not-in-prm", codes)


class TestDpop(unittest.TestCase):
    def _dpop(self, **kwargs):
        dpop = {
            "access_token": TOKEN,
            "request_method": "POST",
            "request_url": "https://mcp.example.test/mcp",
            "proof": {
                "header": {"alg": "ES256", "typ": "dpop+jwt", "jwk": dict(JWK)},
                "claims": {"htm": "POST", "htu": "https://mcp.example.test/mcp",
                           "ath": mcp_authz._sha256_b64u(TOKEN), "jti": "jti-1"},
            },
            "seen_jtis": [],
            "token_claims": {"cnf": {"jkt": mcp_authz.jwk_thumbprint(JWK)}},
        }
        dpop.update(kwargs)
        return dpop

    def test_a_bound_proof_is_clean(self):
        _, codes = mcp_authz.evaluate(observation(dpop=self._dpop()))
        self.assertEqual(codes, [])

    def test_wrong_type_symmetric_alg_and_a_private_key(self):
        dpop = self._dpop()
        dpop["proof"]["header"] = {"alg": "HS256", "typ": "JWT",
                                   "jwk": dict(JWK, d="private-material")}
        _, codes = mcp_authz.evaluate(observation(dpop=dpop))
        self.assertIn("dpop-proof-typ-invalid", codes)
        self.assertIn("dpop-proof-alg-not-asymmetric", codes)
        self.assertIn("dpop-proof-key-private", codes)

    def test_wrong_method_url_and_token_hash(self):
        dpop = self._dpop()
        dpop["proof"]["claims"] = {"htm": "GET", "htu": "https://mcp.example.test/other",
                                   "ath": "not-the-token-hash", "jti": "jti-1"}
        _, codes = mcp_authz.evaluate(observation(dpop=dpop))
        self.assertIn("dpop-htm-mismatch", codes)
        self.assertIn("dpop-htu-mismatch", codes)
        self.assertIn("dpop-ath-mismatch", codes)

    def test_a_key_the_token_is_not_bound_to(self):
        dpop = self._dpop(token_claims={"cnf": {"jkt": "some-other-thumbprint"}})
        _, codes = mcp_authz.evaluate(observation(dpop=dpop))
        self.assertIn("dpop-key-binding-mismatch", codes)

    def test_a_replayed_proof(self):
        dpop = self._dpop(seen_jtis=["jti-1"])
        _, codes = mcp_authz.evaluate(observation(dpop=dpop))
        self.assertIn("dpop-proof-replayed", codes)


class TestWorkloadFederation(unittest.TestCase):
    def _wif(self, **kwargs):
        wif = {
            "trusted_issuers": ["https://workload-idp.example.test"],
            "expected_audience": "https://auth.example.test",
            "bindings": {"system:serviceaccount:agents:runner": ["mcp:read"]},
            "granted_scopes": ["mcp:read"],
            "subject_token": {"claims": {"iss": "https://workload-idp.example.test",
                                         "aud": "https://auth.example.test",
                                         "exp": 1790003600,
                                         "sub": "system:serviceaccount:agents:runner"}},
        }
        wif.update(kwargs)
        return wif

    def test_a_bound_trusted_token_is_clean(self):
        _, codes = mcp_authz.evaluate(observation(workload_federation=self._wif()))
        self.assertEqual(codes, [])

    def test_untrusted_issuer_other_audience_expired_unbound_and_widened(self):
        wif = self._wif(granted_scopes=["mcp:read", "mcp:write"])
        wif["subject_token"] = {"claims": {"iss": "https://other-idp.example.test",
                                           "aud": "https://elsewhere.example.test",
                                           "exp": 1789999940,
                                           "sub": "system:serviceaccount:other:runner"}}
        _, codes = mcp_authz.evaluate(observation(workload_federation=wif))
        for code in ("wif-issuer-untrusted", "wif-audience-mismatch", "wif-token-expired",
                     "wif-subject-unbound", "wif-scope-widened"):
            self.assertIn(code, codes)


class TestClientIdMetadataDocument(unittest.TestCase):
    def _cm(self, **kwargs):
        cm = {
            "as_metadata": {"client_id_metadata_document_supported": True},
            "client_id": "https://client.example.test/oauth/client.json",
            "document": {"client_id": "https://client.example.test/oauth/client.json",
                         "redirect_uris": ["https://client.example.test/callback"],
                         "token_endpoint_auth_method": "none"},
            "redirect_uri": "https://client.example.test/callback",
        }
        cm.update(kwargs)
        return cm

    def test_a_clean_document_is_clean(self):
        _, codes = mcp_authz.evaluate(observation(client_metadata=self._cm()))
        self.assertEqual(codes, [])

    def test_an_identifier_that_is_not_a_clean_https_url(self):
        _, codes = mcp_authz.evaluate(observation(
            client_metadata=self._cm(client_id="http://client.example.test/a/../client.json#frag")))
        self.assertIn("cimd-client-id-not-a-clean-https-url", codes)

    def test_a_document_for_another_client_with_a_shared_secret(self):
        cm = self._cm()
        cm["document"] = {"client_id": "https://client.example.test/oauth/other.json",
                          "client_secret": "synthetic-not-a-secret",
                          "redirect_uris": ["https://client.example.test/callback"],
                          "token_endpoint_auth_method": "client_secret_basic"}
        _, codes = mcp_authz.evaluate(observation(client_metadata=cm))
        self.assertIn("cimd-document-client-id-mismatch", codes)
        self.assertIn("cimd-symmetric-authentication", codes)

    def test_an_unregistered_redirect_and_unadvertised_support(self):
        cm = self._cm(as_metadata={"client_id_metadata_document_supported": False},
                      redirect_uri="https://client.example.test/elsewhere")
        _, codes = mcp_authz.evaluate(observation(client_metadata=cm))
        self.assertIn("cimd-redirect-uri-unregistered", codes)
        self.assertIn("cimd-support-not-advertised", codes)


class TestIdentityAssertionGrant(unittest.TestCase):
    def _ij(self, **kwargs):
        ij = {
            "resource_as_issuer": "https://auth.example.test",
            "requesting_client_id": "client-0001",
            "assertion": {"header": {"alg": "ES256", "typ": "oauth-id-jag+jwt"},
                          "claims": {"aud": "https://auth.example.test",
                                     "client_id": "client-0001", "exp": 1790000300,
                                     "jti": "id-jag-jti-0001"}},
        }
        ij.update(kwargs)
        return ij

    def test_a_clean_assertion_is_clean(self):
        _, codes = mcp_authz.evaluate(observation(id_jag=self._ij()))
        self.assertEqual(codes, [])

    def test_wrong_type_audience_client_expiry_and_no_identifier(self):
        ij = self._ij(assertion={"header": {"alg": "ES256", "typ": "JWT"},
                                 "claims": {"aud": "https://elsewhere.example.test",
                                            "client_id": "client-9999", "exp": 1789999999}})
        _, codes = mcp_authz.evaluate(observation(id_jag=ij))
        for code in ("id-jag-typ-invalid", "id-jag-audience-mismatch",
                     "id-jag-client-mismatch", "id-jag-expired", "id-jag-jti-missing"):
            self.assertIn(code, codes)


class TestSchemaGate(unittest.TestCase):
    def test_an_unknown_schema_is_refused_rather_than_guessed(self):
        obs = observation()
        obs["schema"] = "something-else/v1"
        with self.assertRaises(ValueError):
            mcp_authz.evaluate(obs)


class TestTheCliSpeaksTheHarnessContract(unittest.TestCase):
    def test_last_stdout_line_is_the_object_the_corpus_reads(self):
        work = tempfile.mkdtemp(prefix="mcp-")
        path = os.path.join(work, "member.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(observation(), handle)
        proc = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify-mcp-authz",
                               "--file", path], cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        last = [line for line in proc.stdout.splitlines() if line.strip()][-1]
        payload = json.loads(last)
        self.assertEqual(payload, {"verdict": "valid", "codes": []})

    def test_an_invalid_member_exits_one_and_names_its_codes(self):
        work = tempfile.mkdtemp(prefix="mcp-")
        path = os.path.join(work, "member.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(observation(prm={"status": 404}), handle)
        proc = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify-mcp-authz",
                               "--file", path], cwd=REPO, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stderr[-400:])
        payload = json.loads([line for line in proc.stdout.splitlines() if line.strip()][-1])
        self.assertEqual(payload["verdict"], "invalid")
        self.assertIn("prm-not-served", payload["codes"])


if __name__ == "__main__":
    unittest.main()
