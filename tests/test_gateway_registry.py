"""Registration metadata tests (T/ISC 0174-2026 6.1.1 a/b).

Each test names the clause it defends. The point of this file is not "the parser
works" but "the gateway cannot start on a record it should not forward for".
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.a2a import registry as reg


def _record(**over):
    record = {
        "name": "uibc-verifier",
        "id": "did:web:verify.medxpert.cn",
        "capabilities": [{"name": "uibc/verify",
                          "description": "verify a UIBC package (S1-S6)"}],
        "protocols": ["a2a/1.0", "jsonrpc-2.0"],
        "endpoint": "https://verify.medxpert.cn/a2a/",
        "organization": {"name": "MedXpert", "identifier": "did:web:medxpert.cn"},
        "state": "enabled",
        "vc": {"issuer": "did:web:medxpert.cn", "status": "active",
               "valid_until": "2030-01-01T00:00:00Z"},
        "authorization": {"scopes": ["uibc/verify"]},
    }
    record.update(over)
    return record


def _doc(records):
    return {"schema": "uibc-a2a-registry/1", "agents": records}


class RegistryValidationTests(unittest.TestCase):
    def test_01_complete_record_passes(self):
        report = reg.validate(_doc([_record()]))
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["agents"][0]["state"], "enabled")

    def test_02_missing_name_is_error(self):
        report = reg.validate(_doc([_record(name="")]))
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"][0]["code"], "R1")
        self.assertEqual(report["errors"][0]["clause"], "6.1.1a")

    def test_03_non_did_identifier_is_error(self):
        report = reg.validate(_doc([_record(id="agent-0001")]))
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"][0]["code"], "R2")

    def test_04_opaque_did_method_needs_opt_in(self):
        record = _record(id="did:cn:agent:sfZD8WUaMvz7kE2Z797nzDf7oqMmVu3r")
        strict = reg.validate(_doc([record]))
        self.assertFalse(strict["ok"])
        self.assertEqual(strict["errors"][0]["code"], "R3")
        loose = reg.validate(_doc([record]), allow_opaque_id=True)
        self.assertTrue(loose["ok"])
        self.assertEqual(loose["warnings"][0]["code"], "W0")

    def test_05_endpoint_scheme_and_credentials(self):
        bad_scheme = reg.validate(_doc([_record(endpoint="ftp://x/a2a/")]))
        self.assertEqual(bad_scheme["errors"][0]["code"], "R4")
        creds = reg.validate(_doc([_record(endpoint="https://u:p@x/a2a/")]))
        self.assertEqual(creds["errors"][0]["code"], "R4")

    def test_06_capability_without_name(self):
        report = reg.validate(_doc([_record(capabilities=[{"description": "x"}])]))
        self.assertEqual(report["errors"][0]["code"], "R5")
        self.assertEqual(report["errors"][0]["field"], "capabilities")

    def test_07_unknown_protocol_warns_but_does_not_reject(self):
        report = reg.validate(_doc([_record(protocols=["acp"])]))
        self.assertTrue(report["ok"])
        self.assertEqual(report["warnings"][0]["code"], "W4")

    def test_08_organization_identifier_absent_is_warning(self):
        report = reg.validate(_doc([_record(organization={"name": "MedXpert"})]))
        self.assertTrue(report["ok"])
        self.assertEqual(report["warnings"][0]["code"], "W1")
        self.assertEqual(report["warnings"][0]["clause"], "6.1.1b")

    def test_09_duplicate_identifier_rejected(self):
        report = reg.validate(_doc([_record(), _record(name="second")]))
        self.assertFalse(report["ok"])
        self.assertTrue(any(e["code"] == "R8" for e in report["errors"]))

    def test_10_unknown_state_rejected(self):
        report = reg.validate(_doc([_record(state="maybe")]))
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"][0]["code"], "R9")
        self.assertEqual(report["errors"][0]["clause"], "6.1.3a")

    def test_11_empty_registry_is_error(self):
        report = reg.validate({"agents": []})
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"][0]["code"], "R0")


class BindingTests(unittest.TestCase):
    """6.1.1 b) 身份标识与所属组织、服务端点及可验证凭据的绑定."""

    def _record(self):
        return reg.validate(_doc([_record()]))["agents"][0]

    def test_20_all_bindings_ok(self):
        checks = reg.binding_report(self._record())
        codes = {c["code"]: c["ok"] for c in checks}
        self.assertTrue(codes["B1"])
        self.assertTrue(codes["B2"])
        self.assertTrue(codes["B4"])
        self.assertTrue(codes["B5"])
        self.assertTrue(codes["B7"])

    def test_21_did_web_host_must_match_endpoint_host(self):
        record = reg.validate(_doc([_record(
            endpoint="https://elsewhere.example/a2a/")]))["agents"][0]
        checks = {c["code"]: c for c in reg.binding_report(record)}
        self.assertFalse(checks["B2"]["ok"])

    def test_22_expired_credential_fails(self):
        record = reg.validate(_doc([_record(
            vc={"issuer": "did:web:medxpert.cn", "status": "active",
                "valid_until": "2020-01-01T00:00:00Z"})]))["agents"][0]
        checks = {c["code"]: c for c in reg.binding_report(record)}
        self.assertFalse(checks["B6"]["ok"])

    def test_23_absent_credential_is_unknown_not_pass(self):
        record = reg.validate(_doc([_record(vc=None)]))["agents"][0]
        checks = {c["code"]: c for c in reg.binding_report(record)}
        self.assertIsNone(checks["B3"]["ok"])

    def test_24_absent_authorization_fails_scope_check(self):
        record = reg.validate(_doc([_record(authorization=None)]))["agents"][0]
        checks = {c["code"]: c for c in reg.binding_report(record)}
        self.assertFalse(checks["B7"]["ok"])


class RegistryLoadTests(unittest.TestCase):
    def test_30_load_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "registry.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(_doc([_record()]), handle)
            report = reg.load(path)
            self.assertTrue(report["ok"])
            self.assertEqual(report["path"], os.path.abspath(path))

    def test_31_load_invalid_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "registry.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(_doc([_record(endpoint="")]), handle)
            with self.assertRaises(ValueError) as ctx:
                reg.load(path)
            self.assertIn("R1", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
