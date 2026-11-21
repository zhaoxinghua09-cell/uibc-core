"""Revocation reason vocabulary: supersession and key compromise.

What is being tested is that a revocation says enough for a human to act, and
that a file which says too little is refused rather than accepted as an
annotation. "SUPERSEDED" without a successor tells a caller to stop using this
package and then leaves them with nowhere to go.
"""

import base64
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import unittest

from uibc_core import gate as gate_mod
from uibc_core.gate import REVOCATION_REASONS, gate
from uibc_core.signing import generate_key, key_id
from tests.test_gate import _canonical_sig_payload, _make_pkg, _read_manifest_root


def _sig(key, body):
    return base64.b64encode(
        hmac.new(key, _canonical_sig_payload(body), hashlib.sha256).digest()
    ).decode("ascii")


class RevocationReasonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.key = generate_key()
        self.pkg, _ = _make_pkg(self.tmp, sign_key=self.key)
        self.root = _read_manifest_root(self.pkg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _rev(self, **over):
        body = {
            "revocation_id": "r-reason-1",
            "target_root": self.root,
            "reason_code": "OWNER_REQUEST",
            "key_id": key_id(self.key),
            "algorithm": "HMAC-SHA256",
            "revoked_at": "2026-11-21T00:00:00Z",
        }
        body.update(over)
        body = {k: v for k, v in body.items() if v is not None}
        body["signature"] = _sig(self.key, body)
        path = os.path.join(self.tmp, "rev.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f)
        return path

    # --- vocabulary -------------------------------------------------------

    def test_vocabulary_contains_the_two_new_reasons(self):
        self.assertIn("SUPERSEDED", REVOCATION_REASONS)
        self.assertIn("KEY_COMPROMISED", REVOCATION_REASONS)

    def test_legacy_revocation_without_reason_still_verifies(self):
        body_path = os.path.join(self.tmp, "rev.json")
        body = {"revocation_id": "r-old", "target_root": self.root,
                "key_id": key_id(self.key), "algorithm": "HMAC-SHA256",
                "revoked_at": "2026-11-21T00:00:00Z"}
        body["signature"] = _sig(self.key, body)
        with open(body_path, "w", encoding="utf-8") as f:
            json.dump(body, f)
        r = gate(self.pkg, key=self.key, revocation_path=body_path)
        self.assertEqual(r["revocation"]["status"], "REVOKED")
        self.assertEqual(r["decision"], "DENY")

    def test_owner_request_still_denies(self):
        r = gate(self.pkg, key=self.key, revocation_path=self._rev())
        self.assertEqual(r["decision"], "DENY")
        self.assertEqual(r["revocation"]["status"], "REVOKED")

    # --- reason code is a closed set --------------------------------------

    def test_unknown_reason_code_is_malformed_not_ignored(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="OWNER_SAID_SO"))
        self.assertEqual(r["revocation"]["status"], "MALFORMED")
        self.assertEqual(r["decision"], "HOLD")
        self.assertIn("unknown reason_code", r["revocation"]["detail"])

    def test_non_string_reason_code_is_malformed(self):
        r = gate(self.pkg, key=self.key, revocation_path=self._rev(reason_code=7))
        self.assertEqual(r["revocation"]["status"], "MALFORMED")

    # --- supersession -----------------------------------------------------

    def test_superseded_denies_and_names_the_successor(self):
        successor = "b" * 64
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="SUPERSEDED",
                                           superseded_by=successor))
        self.assertEqual(r["decision"], "DENY")
        self.assertEqual(r["revocation"]["status"], "REVOKED")
        self.assertEqual(r["revocation"]["reason_code"], "SUPERSEDED")
        self.assertEqual(r["revocation"]["superseded_by"], successor)
        self.assertIn(successor, r["reason"])

    def test_superseded_without_successor_is_malformed(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="SUPERSEDED"))
        self.assertEqual(r["revocation"]["status"], "MALFORMED")
        self.assertEqual(r["decision"], "HOLD")
        self.assertIn("superseded_by", r["revocation"]["detail"])

    def test_a_package_cannot_supersede_itself(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="SUPERSEDED",
                                           superseded_by=self.root))
        self.assertEqual(r["revocation"]["status"], "MALFORMED")
        self.assertIn("itself", r["revocation"]["detail"])

    def test_superseding_does_not_add_a_gate_disposition(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="SUPERSEDED",
                                           superseded_by="b" * 64))
        self.assertIn(r["decision"], ("ALLOW", "ALLOW_DISPUTED", "HOLD", "DENY"))
        self.assertEqual(r["decision"], "DENY")
        self.assertEqual(r["exit_code"], 2)

    # --- key compromise ---------------------------------------------------

    def test_compromised_at_must_carry_a_timezone(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="KEY_COMPROMISED",
                                           compromised_at="2026-11-20T10:00:00"))
        self.assertEqual(r["revocation"]["status"], "MALFORMED")
        self.assertIn("timezone", r["revocation"]["detail"])

    def test_compromised_at_with_offset_is_accepted(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="KEY_COMPROMISED",
                                           compromised_at="2026-11-20T10:00:00+08:00"))
        self.assertEqual(r["revocation"]["status"], "REVOKED")
        self.assertEqual(r["revocation"]["compromised_at"], "2026-11-20T10:00:00+08:00")

    def test_compromise_without_a_time_bound_states_its_limit(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="KEY_COMPROMISED"))
        self.assertEqual(r["decision"], "DENY")
        joined = " ".join(r["limitations"])
        self.assertIn("compromised_at", joined)

    def test_compromise_with_a_time_bound_does_not_state_that_limit(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="KEY_COMPROMISED",
                                           compromised_at="2026-11-20T10:00:00Z"))
        joined = " ".join(r["limitations"])
        self.assertNotIn("only this package is void", joined)

    def test_reason_is_in_the_human_readable_detail(self):
        r = gate(self.pkg, key=self.key,
                 revocation_path=self._rev(reason_code="EVIDENCE_INVALID"))
        self.assertIn("reason_code EVIDENCE_INVALID", r["revocation"]["detail"])


if __name__ == "__main__":
    unittest.main()
