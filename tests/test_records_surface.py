"""The public record-reading surface (`uibc_core.records`).

Why this file exists: callers that need a statement's carried records used to
reach into `aee` internals (`_RecordView`, `_record_verifies`). The point of
`uibc_core.records` is that the same information is readable without those
private names, and that nothing here decides validity, tier or admission --
the verifier's answers stay the verifier's.

So the tests below assert shape and refusal, not verdicts:

- the surface walks the records the statement actually carries, in order;
- an unsigned record verifies under no pinned key, however plausible its
  `keyid` looks;
- malformed input yields records with `payload is None` and a named error,
  never an exception;
- `verified_arming_instants` reports only what signature verification
  supports, so an empty pin set reports nothing.

A corpus spot-check is included when `agent_evidence_vectors` is installed;
the surface itself is stdlib-only and the rail never needs that package.
"""

import base64
import json
import os
import unittest

from uibc_core import records

try:
    import agent_evidence_vectors

    _VECTORS = os.path.join(os.path.dirname(os.path.abspath(agent_evidence_vectors.__file__)),
                            "corpora", "vectors")
    _HAVE_CORPUS = os.path.isfile(os.path.join(_VECTORS, "MANIFEST.json"))
except Exception:
    _VECTORS = ""
    _HAVE_CORPUS = False


def _b64(obj) -> str:
    """Canonical JSON: the rail refuses anything else, and rightly so."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return base64.b64encode(canonical.encode("utf-8")).decode("ascii")


def _statement(*records_):
    return {"predicate": {"observationRecords": list(records_)}}


def _arming(armed_at="2026-01-01T00:00:00Z", keyid="deadbeef", signed=False):
    rec = {
        "payloadType": "application/vnd.aee-record+json",
        "payload": _b64({"aeeKind": "arming", "aeeMethod": "entropyDraw",
                         "armedAt": armed_at}),
    }
    if signed:
        rec["signatures"] = [{"keyid": keyid, "sig": "AAAA"}]
    return rec


class TestTheSurfaceWalksWhatIsCarried(unittest.TestCase):
    def test_order_and_index_follow_the_statement(self):
        stmt = _statement(_arming("a"), _arming("b"), _arming("c"))
        got = records.records_of(stmt)
        self.assertEqual([r.index for r in got], [0, 1, 2])
        self.assertEqual([r.kind for r in got], ["arming"] * 3)
        self.assertEqual(records.iter_records(stmt).__class__.__name__, "generator")

    def test_an_empty_statement_is_empty_not_an_error(self):
        self.assertEqual(records.records_of(_statement()), [])

    def test_a_payload_is_decoded_once_and_carries_its_method(self):
        rec, = records.records_of(_statement(_arming()))
        self.assertEqual(rec.payload_type, "application/vnd.aee-record+json")
        self.assertEqual(rec.method, "entropyDraw")
        self.assertEqual(rec.payload["armedAt"], "2026-01-01T00:00:00Z")


class TestRefusalsAreReportedNotRaised(unittest.TestCase):
    def test_malformed_statements_yield_no_records(self):
        for bad in (None, [], "not-a-statement", {}, {"predicate": None},
                    {"predicate": {"observationRecords": None}}):
            self.assertEqual(records.records_of(bad), [], "input %r was not refused" % (bad,))

    def test_a_non_base64_payload_is_unreadable_not_fatal(self):
        rec, = records.records_of(_statement({"payloadType": "application/t", "payload": "!!!"}))
        self.assertIsNone(rec.payload)
        self.assertIsNone(rec.kind)

    def test_a_non_json_payload_names_its_error(self):
        rec, = records.records_of(_statement({
            "payloadType": "application/vnd.aee-record+json",
            "payload": base64.b64encode(b"{").decode("ascii")}))
        self.assertIsNone(rec.payload)
        self.assertIsNotNone(rec.payload_error)


class TestSignatureIsTheOnlyWitness(unittest.TestCase):
    def test_an_unsigned_record_verifies_under_no_key(self):
        rec, = records.records_of(_statement(_arming(keyid="looks-legit")))
        self.assertEqual(rec.signature_count, 0)
        self.assertFalse(records.record_verified(rec, [b"\x00" * 32]))

    def test_empty_pins_verify_nothing_even_with_signatures_present(self):
        stmt = _statement(_arming(signed=True), _arming(signed=True))
        for rec in records.records_of(stmt):
            self.assertEqual(rec.signature_count, 1)
            self.assertFalse(records.record_verified(rec, []))

    def test_arming_instants_report_only_verified_armings(self):
        stmt = _statement(_arming("2026-02-02T00:00:00Z", signed=True), _arming("2026-03-03T00:00:00Z"))
        self.assertEqual(records.verified_arming_instants(stmt, []), [])


@unittest.skipUnless(_HAVE_CORPUS, "agent_evidence_vectors corpus not installed")
class TestAgainstTheCorpus(unittest.TestCase):
    """The corpus statements are the same ones the rail verdicts on."""

    def _first_with_records(self):
        with open(os.path.join(_VECTORS, "MANIFEST.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        for entry in manifest["vectors"]:
            path = os.path.join(_VECTORS, entry["file"])
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as fh:
                stmt = json.load(fh)
            carried = ((stmt.get("predicate") or {}).get("observationRecords") or [])
            if carried:
                return stmt, carried
        return None, None

    def test_every_carried_record_is_visible_and_nothing_else_is(self):
        stmt, carried = self._first_with_records()
        if stmt is None:
            self.skipTest("no corpus statement carries records")
        got = records.records_of(stmt)
        self.assertEqual(len(got), len(carried))
        self.assertEqual([r.raw for r in got], carried)

    def test_the_surface_agrees_with_the_rails_private_view(self):
        from uibc_core import aee
        stmt, carried = self._first_with_records()
        if stmt is None:
            self.skipTest("no corpus statement carries records")
        got = records.records_of(stmt)
        for rec in got:
            view = aee._RecordView(rec.index, carried[rec.index])
            self.assertEqual(rec.kind, view.kind)
            self.assertEqual(rec.signature_count, view.signature_count)
            self.assertEqual(rec.pae, view.pae)


class TestTheSurfaceIsAllItClaimsToBe(unittest.TestCase):
    def test_public_names_are_exactly_what_the_module_advertises(self):
        for name in records.__all__:
            self.assertTrue(hasattr(records, name), "%s is advertised but missing" % name)

    def test_private_aee_helpers_are_not_re_exported(self):
        for name in ("_RecordView", "_record_verifies"):
            self.assertFalse(hasattr(records, name),
                             "%s leaked into the public surface" % name)


if __name__ == "__main__":
    unittest.main()
