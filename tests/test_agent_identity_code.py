"""GB/Z 185.2-2026 identity code: shape checks, and the absence of a verdict.

The tests below are deliberately mostly refusals. A parser for a national
standard earns its keep by rejecting the strings that almost look right, and by
never claiming more than the standard lets it claim.
"""

import unittest

from uibc_core.agent_identity_code import (
    PREFIX,
    SEQUENCE_MAX,
    SPEC,
    detect_profile,
    duplicates,
    parse_agent_code,
)

# Constructed, not issued. Shaped like the example a public third-party crate
# uses; nothing here asserts that such a code was ever allocated to anyone.
GOOD = "1.2.156.3088.1.A1B2C3.D4E5F6.ABC123456"
GOOD_8 = "1.2.156.3088.1.1.1.1"


class TestPrefix(unittest.TestCase):
    def test_the_prefix_is_the_one_the_standard_fixes(self):
        self.assertEqual(PREFIX, "1.2.156.3088")
        self.assertEqual(SPEC["prefix"], PREFIX)

    def test_a_neighbouring_prefix_is_refused(self):
        doc = parse_agent_code("1.2.156.3089.1.1.1.1")
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("prefix", doc["detail"])

    def test_a_different_root_is_refused(self):
        doc = parse_agent_code("1.3.6.1.4.1.1.1.1")
        self.assertEqual(doc["state"], "INVALID")


class TestArcCount(unittest.TestCase):
    def test_eight_arcs_is_the_wire_form(self):
        self.assertEqual(parse_agent_code(GOOD)["state"], "INCONCLUSIVE")

    def test_only_the_prefix_is_refused(self):
        doc = parse_agent_code("1.2.156.3088")
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("4 arcs", doc["detail"])

    def test_six_arcs_is_refused(self):
        doc = parse_agent_code("1.2.156.3088.1.1.1")
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("7 arcs", doc["detail"])

    def test_nine_arcs_is_refused(self):
        doc = parse_agent_code("1.2.156.3088.1.1.1.1.1")
        self.assertEqual(doc["state"], "INVALID")


class TestVersion(unittest.TestCase):
    def test_version_one_is_the_current_rule(self):
        self.assertEqual(parse_agent_code(GOOD)["state"], "INCONCLUSIVE")

    def test_a_two_character_version_is_refused(self):
        doc = parse_agent_code("1.2.156.3088.11.1.1.1")
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("exactly one", doc["detail"])

    def test_a_reserved_version_is_unsupported_not_invalid(self):
        # 5.3 gives a range of 35 versions but this document fixes version 1.
        # A reserved version is not malformed; it is a rule we do not have.
        doc = parse_agent_code("1.2.156.3088.2.1.1.1")
        self.assertEqual(doc["state"], "UNSUPPORTED")
        self.assertIn("reserved", doc["detail"])

    def test_version_zero_is_outside_the_range(self):
        doc = parse_agent_code("1.2.156.3088.0.1.1.1")
        self.assertEqual(doc["state"], "INVALID")


class TestLengthBounds(unittest.TestCase):
    def test_provider_capped_at_six(self):
        doc = parse_agent_code("1.2.156.3088.1.ABCDEFG.1.1")
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("5.4", doc["detail"])

    def test_requester_capped_at_six(self):
        doc = parse_agent_code("1.2.156.3088.1.1.ABCDEFG.1")
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("5.5", doc["detail"])

    def test_sequence_bound_is_declared_as_a_derivation(self):
        doc = parse_agent_code("1.2.156.3088.1.1.1." + "A" * (SEQUENCE_MAX + 1))
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("derivation", doc["detail"])

    def test_sequence_at_the_bound_is_accepted(self):
        doc = parse_agent_code("1.2.156.3088.1.1.1." + "A" * SEQUENCE_MAX)
        self.assertEqual(doc["state"], "INCONCLUSIVE")


class TestCharset(unittest.TestCase):
    def test_lowercase_is_the_same_code(self):
        self.assertEqual(parse_agent_code(GOOD.lower())["subject"],
                         parse_agent_code(GOOD)["subject"])

    def test_a_space_inside_is_refused(self):
        doc = parse_agent_code("1.2.156.3088.1.A1 B2.1.1")
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("0-9/A-Z", doc["detail"])

    def test_an_hyphen_is_refused(self):
        doc = parse_agent_code("1.2.156.3088.1.A-1.1.1")
        self.assertEqual(doc["state"], "INVALID")

    def test_surrounding_whitespace_is_stripped_not_rejected(self):
        self.assertEqual(parse_agent_code("  %s  " % GOOD)["state"], "INCONCLUSIVE")

    def test_empty_and_non_string_are_refused(self):
        self.assertEqual(parse_agent_code("")["state"], "INVALID")
        self.assertEqual(parse_agent_code(None)["state"], "INVALID")
        self.assertEqual(parse_agent_code(12345)["state"], "INVALID")


class TestNeverVerified(unittest.TestCase):
    """The whole point: a shape check cannot produce VERIFIED."""

    def test_no_input_reaches_verified(self):
        samples = [GOOD, GOOD_8, GOOD.lower(), "  %s  " % GOOD,
                   "1.2.156.3089.1.1.1.1", "1.2.156.3088.2.1.1.1",
                   "1.2.156.3088.1.ABCDEFG.1.1", "", None,
                   "1.2.156.3088.1.A1B2C3.D4E5F6.ABC123456.000001.176F"]
        for s in samples:
            doc = parse_agent_code(s)
            self.assertNotEqual(doc["state"], "VERIFIED", s)
            self.assertIn("scope", doc)
            self.assertIn("shape only", doc["scope"])
            self.assertFalse(doc.get("evidence"))

    def test_the_documented_ceiling_matches_the_code(self):
        self.assertEqual(SPEC["max_state"], "INCONCLUSIVE")


class TestThirdPartyProfile(unittest.TestCase):
    """aipmc-basic reads ten arcs with a CRC the national standard lacks."""

    TEN = "1.2.156.3088.1.0001.00001.ABC123.000001.176F"

    def test_ten_arcs_are_recognised_as_a_profile(self):
        self.assertEqual(detect_profile(self.TEN), "aip-acps")
        self.assertEqual(detect_profile(GOOD), "gbz185.2")
        self.assertIsNone(detect_profile("1.2.156.3088"))

    def test_ten_arcs_are_refused_rather_than_silently_accepted(self):
        doc = parse_agent_code(self.TEN)
        self.assertEqual(doc["state"], "INVALID")
        self.assertIn("aip-acps", doc["detail"])
        self.assertIn("salt", doc["detail"])


class TestDuplicates(unittest.TestCase):
    def test_a_repeated_code_is_reported(self):
        dups = duplicates([GOOD, GOOD.lower(), GOOD_8])
        self.assertEqual(dups, {GOOD: 2})

    def test_distinct_codes_report_nothing(self):
        self.assertEqual(duplicates([GOOD, GOOD_8]), {})

    def test_non_strings_are_ignored(self):
        self.assertEqual(duplicates([None, 42]), {})


if __name__ == "__main__":
    unittest.main()
