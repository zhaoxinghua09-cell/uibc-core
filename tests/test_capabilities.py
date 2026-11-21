"""Tests for capability declaration and attribution.

The property being tested is the one that makes cross-implementation
comparison trustworthy: a difference explained by a declaration must never
be reported as a defect, and a difference that is not so explained must never
be excused.
"""

import json
import unittest

from uibc_core import basis, capabilities


def _minimal(**kw):
    args = dict(checks=["S0", "S4", "S6"], dispositions=["PASS", "FAIL"],
                fields=["basis"], verifier="demo 0.3.0",
                spec_version=capabilities.SPEC_VERSION)
    args.update(kw)
    return capabilities.declaration(**args)


class DeclarationTest(unittest.TestCase):
    def test_declaration_measures_this_tree(self):
        decl = capabilities.declaration()
        self.assertEqual(sorted(decl["checks"]), sorted(basis.BASIS))

    def test_declaration_is_deterministic(self):
        a = json.dumps(capabilities.declaration(), sort_keys=True)
        b = json.dumps(capabilities.declaration(), sort_keys=True)
        self.assertEqual(a, b)

    def test_declaration_is_ascii_and_pathless(self):
        text = json.dumps(capabilities.declaration(), ensure_ascii=False)
        self.assertTrue(text.isascii(), "declaration must survive a cp936 pipe (F-010)")
        self.assertNotIn(":\\", text, "no absolute path may enter a machine report (F-011)")
        self.assertNotIn('"/', text)

    def test_digest_changes_when_a_check_is_added(self):
        one = _minimal(checks=["S0"])
        two = _minimal(checks=["S0", "S4"])
        self.assertNotEqual(one["digest"], two["digest"])

    def test_digest_covers_every_other_field(self):
        base = _minimal()
        for key, value in (("verifier", "other 1.0"), ("spec_version", "x/1"),
                           ("dispositions", ["PASS"]), ("fields", [])):
            changed = dict(base)
            changed[key] = value
            self.assertNotEqual(capabilities.digest(changed), base["digest"], key)

    def test_schema_check_rejects_missing_fields(self):
        problems = capabilities.check_declaration({"checks": ["S0"]})
        self.assertTrue(any(p["code"] == "MISSING_FIELD" for p in problems))

    def test_schema_check_rejects_unknown_disposition(self):
        bad = _minimal(dispositions=["PASS", "MAYBE"])
        problems = capabilities.check_declaration(bad)
        self.assertTrue(any(p["code"] == "UNKNOWN_DISPOSITION" for p in problems))


class CompareTest(unittest.TestCase):
    def test_identical_is_compatible(self):
        result = capabilities.compare(capabilities.declaration(), capabilities.declaration())
        self.assertTrue(result["compatible"])
        self.assertEqual(result["capability_gaps"], [])
        self.assertEqual(result["defects"], [])

    def test_missing_check_is_attributed_to_the_declaration(self):
        result = capabilities.compare(capabilities.declaration(), _minimal())
        self.assertTrue(result["comparable"])
        self.assertFalse(result["compatible"])
        self.assertEqual(result["defects"], [])
        self.assertIn("S11", result["only_in_a"])
        self.assertTrue(all(g["absent_from"] == "B" for g in result["capability_gaps"]))

    def test_missing_disposition_is_a_gap_with_a_name(self):
        result = capabilities.compare(capabilities.declaration(), _minimal())
        names = [g.get("name") for g in result["capability_gaps"] if g["kind"] == "DISPOSITION"]
        self.assertIn("INCONCLUSIVE", names)

    def test_missing_report_field_is_a_gap_with_a_name(self):
        result = capabilities.compare(capabilities.declaration(), _minimal())
        names = [g.get("name") for g in result["capability_gaps"] if g["kind"] == "FIELD"]
        self.assertIn("evidence", names)

    def test_vocabulary_neither_side_knows_is_a_defect(self):
        alien = _minimal(checks=["S0", "X99"], verifier="alien 1.0")
        result = capabilities.compare(capabilities.declaration(), alien)
        self.assertTrue(any(d["detail"]["code"] == "UNKNOWN_CHECK" for d in result["defects"]))
        self.assertFalse(result["compatible"])

    def test_tampered_digest_is_a_defect_not_a_gap(self):
        broken = _minimal()
        broken["digest"] = "sha256:" + "0" * 64
        result = capabilities.compare(capabilities.declaration(), broken)
        self.assertTrue(any(d["detail"]["code"] == "DIGEST_MISMATCH" for d in result["defects"]))

    def test_spec_version_difference_is_a_defect(self):
        other = _minimal(spec_version="uibc-core/0.3.0-proposal")
        result = capabilities.compare(capabilities.declaration(), other)
        self.assertTrue(any(d["detail"]["code"] == "SPEC_VERSION_DIFFERS" for d in result["defects"]))

    def test_unreadable_input_cannot_excuse_a_disagreement(self):
        result = capabilities.compare(capabilities.declaration(), {"checks": []})
        self.assertEqual(result["capability_gaps"], [])
        self.assertTrue(result["defects"])

    def test_gap_count_is_symmetric(self):
        a, b = capabilities.declaration(), _minimal()
        left = capabilities.compare(a, b)["capability_gaps"]
        right = capabilities.compare(b, a)["capability_gaps"]
        self.assertEqual(len(left), len(right))
        self.assertTrue(all(g["absent_from"] == "B" for g in left))
        self.assertTrue(all(g["absent_from"] == "A" for g in right))


class ClassifyTest(unittest.TestCase):
    def test_shared(self):
        decl = capabilities.declaration()
        self.assertEqual(capabilities.classify_check("S6", decl, decl), "SHARED")

    def test_gap_b_when_only_a_has_it(self):
        self.assertEqual(
            capabilities.classify_check("S11", capabilities.declaration(), _minimal()),
            "CAPABILITY_GAP_B")

    def test_gap_a_when_only_b_has_it(self):
        self.assertEqual(
            capabilities.classify_check("S11", _minimal(), capabilities.declaration()),
            "CAPABILITY_GAP_A")

    def test_unknown_when_neither_has_it(self):
        self.assertEqual(capabilities.classify_check("Z9", _minimal(), _minimal()), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
