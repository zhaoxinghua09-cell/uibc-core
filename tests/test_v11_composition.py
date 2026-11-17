"""Composition verdicts: one case, many origins, and the failure modes named by code.

Every test here is about the ONE question composition verification may answer -
is this assembly self-consistent? - and never about whether the agent behaved
well. The negative cases matter most: an edited record, a gap, a dangling
cross-origin reference, and a set that is stacked rather than composed.
"""
import unittest

from uibc_core.canonical import hash_obj
from uibc_core.composition import compose_case


def rec(origin, kind, subject, at, seq, payload, parent=None, refs=None):
    return {"origin": origin, "kind": kind, "subject": subject, "at": at, "seq": seq,
            "digest": "sha256:" + hash_obj(payload), "payload": payload,
            "parent": parent, "refs": refs or []}


def clean():
    g1 = rec("gate-A", "verdict", "agent:42", "2026-11-17T06:00:00Z", 1,
             {"decision": "ALLOW"})
    g2 = rec("gate-A", "verdict", "agent:42", "2026-11-17T06:01:00Z", 2,
             {"decision": "DENY"}, parent=g1["digest"])
    lg = rec("scitt-log", "receipt", "agent:42", "2026-11-17T06:00:30Z", 1,
             {"leaf": g1["digest"]}, refs=[g1["digest"]])
    hr = rec("reviewer-B", "note", "agent:42", "2026-11-17T06:30:00Z", 1,
             {"conclusion": "escalate"}, refs=[g2["digest"], lg["digest"]])
    return [g1, g2, lg, hr]


def codes(rep):
    return {f["code"] for f in rep["findings"]}


class TestComposition(unittest.TestCase):
    def test_clean_case_passes(self):
        rep = compose_case(clean())
        self.assertEqual(rep["verdict"], "PASS", rep["findings"])
        self.assertEqual(rep["origins"], ["gate-A", "reviewer-B", "scitt-log"])

    def test_edited_payload_is_caught(self):
        rs = clean()
        rs[1] = dict(rs[1], payload={"decision": "ALLOW"})
        rep = compose_case(rs)
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertIn("K1", codes(rep))

    def test_sequence_gap_is_caught(self):
        rs = clean()
        rs[1] = dict(rs[1], seq=9)
        rep = compose_case(rs)
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertIn("K3", codes(rep))

    def test_dangling_ref_is_caught(self):
        rs = clean()
        rs[3] = dict(rs[3], refs=["sha256:" + "de" * 32])
        rep = compose_case(rs)
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertIn("K5", codes(rep))

    def test_single_origin_is_inconclusive_not_pass(self):
        rep = compose_case([clean()[0]])
        self.assertEqual(rep["verdict"], "INCONCLUSIVE")
        self.assertIn("K7", codes(rep))

    def test_stacked_islands_are_inconclusive(self):
        g1, g2, _, _ = clean()
        other = rec("other-C", "note", "agent:42", "2026-11-17T07:00:00Z", 1,
                    {"conclusion": "unrelated"})
        rep = compose_case([g1, g2, other])
        self.assertEqual(rep["verdict"], "INCONCLUSIVE")
        self.assertIn("K7", codes(rep))

    def test_ordering_contradiction_is_caught(self):
        rs = clean()
        rs[0] = dict(rs[0], at="2026-11-17T06:45:00Z")  # cited by a record dated earlier
        rep = compose_case(rs)
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertIn("K4", codes(rep))

    def test_scope_never_widens(self):
        rep = compose_case(clean())
        self.assertIn("does not judge behaviour", rep["scope"])
        self.assertEqual(rep["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
