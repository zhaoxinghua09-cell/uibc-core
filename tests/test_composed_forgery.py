"""The strongest attack this project can answer: a forgery that agrees with itself.

Rewriting one evidence file is caught by S4 because a declaration still describes
the old bytes. Rewriting it *and* repairing every declaration is arithmetic -
hash, root, index digest, checkpoint head are all public functions of bytes the
attacker owns. So the question is what still has something to say afterwards.

These tests freeze the answer so it cannot quietly change: in open mode a package
re-signed by a stranger verifies as PASS, and the verdict must say "unanchored"
when it does. PASS there means *this key signed these bytes*. It does not mean the
publisher wrote them, and nothing inside a package can make it mean that.
"""
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))

from composed_forgery import _run  # noqa: E402


class TestComposedForgery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = {}
        for a in "ABCDEF":
            cls.v[a] = _run(a)

    def test_an_undeclared_rewrite_is_caught(self):
        verdict, fails, _, trust = self.v["A"]
        self.assertEqual(verdict, "FAIL")
        self.assertIn("S4", fails)
        self.assertEqual(trust, "unattested")

    def test_a_repair_lands_on_inconclusive_not_pass(self):
        # an HMAC seal nobody holds the key for cannot be resolved; "no violation
        # found" would be a stronger claim than the evidence supports.
        verdict, fails, inc, trust = self.v["B"]
        self.assertNotEqual(verdict, "PASS")
        self.assertEqual(verdict, "INCONCLUSIVE")
        self.assertIn("S6", inc)
        self.assertEqual(trust, "unattested")

    def test_a_stranger_who_re_signs_gets_pass_but_unanchored(self):
        # THE BOUNDARY. This is not a bug: the signature is valid. The verdict has
        # to carry the fact that the key came out of the package under test.
        verdict, fails, inc, trust = self.v["C"]
        self.assertEqual(verdict, "PASS")
        self.assertEqual(fails, [])
        self.assertEqual(trust, "unanchored")

    def test_pinning_the_publisher_key_catches_the_substitution(self):
        verdict, fails, _, _ = self.v["D"]
        self.assertEqual(verdict, "FAIL")
        self.assertIn("S6", fails)

    def test_pinning_a_head_published_elsewhere_catches_it(self):
        verdict, fails, _, _ = self.v["E"]
        self.assertEqual(verdict, "FAIL")
        self.assertIn("S9", fails)

    def test_dropping_the_seal_does_not_improve_standing(self):
        verdict, _, inc, trust = self.v["F"]
        self.assertNotEqual(verdict, "PASS")
        self.assertIn("S6", inc)
        self.assertEqual(trust, "unattested")


if __name__ == "__main__":
    unittest.main()
