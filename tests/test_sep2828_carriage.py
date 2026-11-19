"""SEP-2828 carriage: the two verdicts stay apart.

The property these tests protect is not "the adapter passes". It is that a
reader of the output cannot mistake one verdict for the other: a record whose
own self-binding does not recompute still produces `uibc_chain=PASS` (the bytes
are the bytes that were sealed), and a byte changed after sealing still produces
`FAIL` even though the record parses.

If someone later "improves" this by folding the two into one boolean, these
tests are what fails.
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import sep2828_carriage as sc  # noqa: E402

SIG = "ab" * 64  # 128 hex characters, the ES256 length


def conforming_record(projection='{"deleted":true,"path":"/archive/2024-Q3.md"}'):
    return {
        "alg": "ES256",
        "backLink": {
            "attestationDigest": "sha256:" + "79" * 32,
            "attestationNonce": "fixed-attestation-nonce-000",
        },
        "outcomeDerived": {
            "completedAt": "2026-05-29T10:00:00Z",
            "resultCommitment": {
                "projection": projection,
                "projectionDigest": "sha256:" + hashlib.sha256(
                    projection.encode("utf-8")).hexdigest(),
            },
            "status": "executed",
        },
        "receiptAsserted": {
            "alg": "ES256", "iat": "2026-05-29T10:00:00Z", "iss": "issuer://test",
            "nonce": "fixed-receipt-nonce-0001", "secretVersion": "v1",
            "sub": "agent:archiver",
        },
        "signature": SIG,
        "version": 1,
    }


def write_record(tmpdir, name, doc):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


class TestRecordRules(unittest.TestCase):
    def test_conforming_record_conforms(self):
        got = sc.record_conformance(conforming_record())
        self.assertTrue(got["conforms"])
        self.assertEqual(got["requiredFailed"], [])

    def test_edited_projection_digest_is_caught_by_the_self_binding(self):
        doc = conforming_record()
        doc["outcomeDerived"]["resultCommitment"]["projectionDigest"] = "sha256:" + "00" * 32
        got = sc.record_conformance(doc)
        self.assertFalse(got["conforms"])
        self.assertEqual(got["requiredFailed"], ["result_commitment_self_consistent"])

    def test_non_object_is_top_level_object(self):
        self.assertEqual(sc.record_conformance([])["requiredFailed"],
                         ["top_level_object"])

    def test_signature_is_a_format_check_not_a_verification(self):
        doc = conforming_record()
        doc["signature"] = "zz" * 64  # not hex
        self.assertIn("signature_hex", sc.record_conformance(doc)["requiredFailed"])
        doc["signature"] = "ab"  # hex, wrong length for ES256
        got = sc.record_conformance(doc)
        self.assertTrue(got["conforms"])          # still conforms: length is advisory
        self.assertEqual(got["advisories"], ["signature_length"])

    def test_alg_mismatch_between_asserted_and_envelope(self):
        doc = conforming_record()
        doc["receiptAsserted"]["alg"] = "HS256"
        self.assertEqual(sc.record_conformance(doc)["requiredFailed"],
                         ["receipt_asserted_alg_matches"])


class TestSetRules(unittest.TestCase):
    def _make_outcome(self, call, status="executed", commitment=True):
        doc = conforming_record()
        doc["backLink"]["attestationDigest"] = "sha256:" + call * 32
        doc["outcomeDerived"]["status"] = status
        if not commitment:
            doc["outcomeDerived"].pop("resultCommitment", None)
        return doc

    def test_two_outcomes_for_one_call_is_a_required_duplicate(self):
        call = "aa"
        got = sc.set_conformance([("r1.json", self._make_outcome(call)),
                                  ("r2.json", self._make_outcome(call))])
        self.assertFalse(got["conforms"])
        self.assertEqual(got["findings"], [{"id": "duplicate_call",
                                            "severity": "required",
                                            "records": ["r1.json", "r2.json"]}])

    def test_executed_without_commitment_is_advisory_not_required(self):
        got = sc.set_conformance([("r1.json", self._make_outcome("bb", commitment=False))])
        self.assertTrue(got["conforms"])
        self.assertEqual(got["findings"][0]["id"],
                         "executed_without_result_commitment")
        self.assertEqual(got["findings"][0]["severity"], "advisory")


class TestCarriage(unittest.TestCase):
    def test_carriage_binds_bytes_and_does_not_judge_meaning(self):
        """The load-bearing test: two verdicts, opposite directions, one run."""
        with tempfile.TemporaryDirectory() as tmp:
            doc = conforming_record()
            doc["outcomeDerived"]["resultCommitment"]["projectionDigest"] = "sha256:" + "00" * 32
            path = write_record(tmp, "edited.json", doc)
            work = os.path.join(tmp, "work")
            os.makedirs(work)
            wrapped = sc.carry([path], "case", work)
            self.assertEqual(wrapped["uibc_chain"], "PASS")
            self.assertFalse(sc.record_conformance(doc)["conforms"],
                             "the same bytes must fail the sep2828 verdict")

    def test_one_byte_after_sealing_turns_the_chain_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_record(tmp, "ok.json", conforming_record())
            work = os.path.join(tmp, "work")
            os.makedirs(work)
            wrapped = sc.carry([path], "case", work)
            self.assertEqual(wrapped["uibc_chain"], "PASS")

            entry = sc._first_entry(wrapped["package"])
            target = os.path.join(wrapped["package"], "evidence", entry)
            with open(target, "rb") as f:
                raw = f.read()
            marker = b'"signature": "'
            pos = raw.find(marker) + len(marker)
            flipped = bytearray(raw)
            flipped[pos] = ord("0") if chr(flipped[pos]) != "0" else ord("1")
            with open(target, "wb") as f:
                f.write(bytes(flipped))

            from uibc_core.verify import verify
            after = verify(wrapped["package"])
            self.assertEqual(after["result"], "FAIL")
            self.assertIn("S4", [c["id"] for c in after["checks"]
                                 if c["result"] == "FAIL"])

    def test_checkpoint_head_is_recorded_so_a_rollback_can_be_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_record(tmp, "ok.json", conforming_record())
            work = os.path.join(tmp, "work")
            os.makedirs(work)
            wrapped = sc.carry([path], "case", work)
            head = wrapped["checkpoint_head"] or ""
            self.assertTrue(head.startswith("sha256:"), head)
            self.assertEqual(len(head.split(":", 1)[1]), 64)


class TestDemo(unittest.TestCase):
    def test_demo_runs_without_any_corpus(self):
        """A stranger with no clone must still see both verdicts."""
        with tempfile.TemporaryDirectory() as tmp:
            result = sc.run_demo(tmp)
            self.assertEqual(result["cases"], 4)
            self.assertEqual(result["verdict"], "CONSISTENT")
            self.assertEqual(result["uibc_chain_pass"], 4)
            self.assertEqual(result["tamper"]["after"], "FAIL")

    def test_demo_shows_the_verdicts_pointing_opposite_ways(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = sc.run_demo(tmp)
            edited = [c for c in result["cases_detail"]
                      if c["case"] == "edited_projection_digest"][0]
            self.assertEqual(edited["uibc_chain"], "PASS")
            self.assertFalse(edited["sep2828"]["conforms"])


if __name__ == "__main__":
    unittest.main()
