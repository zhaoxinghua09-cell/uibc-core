"""The did:cn namespace the platform serves is not the one the README publishes.

Measured 2026-11-24: `agent.idfactory.cn` lists registered agents as
`did:cn:agent:<base58>`, while the CN DID Method Specification fixes
`2DIGIT.3*5DIGIT.1*128DIGIT`. Both statements are true; the adapter has to keep
them apart instead of picking whichever it likes.

`validate()` keeps refusing the live form — its job is the published ABNF, and
loosening it would silently stop checking the document it claims to check. The
live form gets `validate_live_agent_id()`, which labels itself as unpublished.
"""

import unittest

from uibc_core import did_cn
from uibc_core.did_cn import IdentifierError

LIVE = "did:cn:agent:sfKvhQocnYJJME4zGDdRqvWtes21Mi9c"
PUBLISHED = "did:cn:88.100.1"


class TestThePublishedFormIsStillChecked(unittest.TestCase):
    def test_the_readme_example_still_validates(self):
        method, support, details = did_cn.validate(PUBLISHED)
        self.assertEqual(method, "cn")
        self.assertEqual(support, "registry")
        self.assertEqual(details, {"issuer": "88", "industry": "100", "enterprise": "1"})

    def test_the_live_form_is_not_accepted_by_the_abnf_check(self):
        with self.assertRaises(IdentifierError) as ctx:
            did_cn.validate(LIVE)
        self.assertIn("2DIGIT.3*5DIGIT.1*128DIGIT", str(ctx.exception))


class TestTheLiveFormHasItsOwnEntryPoint(unittest.TestCase):
    def test_a_real_platform_identifier_is_recognised(self):
        details = did_cn.validate_live_agent_id(LIVE)
        self.assertEqual(details["namespace"], "agent")
        self.assertEqual(details["key_encoding"], "base58")
        self.assertEqual(details["key_length"], 32)

    def test_it_says_it_is_not_the_published_abnf(self):
        details = did_cn.validate_live_agent_id(LIVE)
        self.assertFalse(details["published_abnf"])
        self.assertIn("undocumented", details["note"])

    def test_the_published_form_is_refused_here(self):
        with self.assertRaises(IdentifierError):
            did_cn.validate_live_agent_id(PUBLISHED)

    def test_another_method_is_refused(self):
        with self.assertRaises(IdentifierError):
            did_cn.validate_live_agent_id("did:ioa:A1B2:z6MkhaXgBZDvotDkL5257faiztiGiC2Q")

    def test_a_bad_base58_character_is_refused(self):
        # "0" and "O" are not in the base58 alphabet.
        with self.assertRaises(IdentifierError):
            did_cn.validate_live_agent_id("did:cn:agent:sf0vhQocnYJJME4zGDdRqvWtes21Mi9c")

    def test_a_too_short_tail_is_refused(self):
        with self.assertRaises(IdentifierError):
            did_cn.validate_live_agent_id("did:cn:agent:sfKvhQ")

    def test_lowercase_base58_is_accepted_as_served(self):
        # Base58 is case-sensitive: the platform's tails mix case. A tail written
        # only in lowercase is still base58, so it must not be "normalised" away.
        tail = "abcdefghijkmnopqrstuvwxyz12345"
        details = did_cn.validate_live_agent_id("did:cn:agent:" + tail)
        self.assertEqual(details["key_length"], len(tail))


class TestNoVerdictShortcut(unittest.TestCase):
    def test_the_live_form_never_claims_allocation(self):
        details = did_cn.validate_live_agent_id(LIVE)
        self.assertNotIn("verified", " ".join(details).lower())
        self.assertIn("proves nothing about allocation", details["note"])


if __name__ == "__main__":
    unittest.main()
