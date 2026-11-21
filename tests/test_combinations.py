"""One defect is measured everywhere. Two at once is a different question.

The interesting failure mode is not "both are caught" but "the two explain each
other away": a second change that supplies the consistency the first one broke.
This test asks the verifier 14 single mutations, 91 pairs of them, and 364 triples,
and requires that every combination still fails somewhere.
"""
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from check_combinations import MUTATIONS, probe  # noqa: E402


class TestCombinations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.singles, cls.pairs, cls.triples = probe(triples=True)

    def test_every_single_mutation_is_caught_alone(self):
        silent = [s["id"] for s in self.singles if not s["fails"]]
        self.assertEqual(silent, [], "mutations nothing catches: " + ", ".join(silent))
        self.assertEqual(len(self.singles), len(MUTATIONS))

    def test_no_pair_cancels_the_other_half(self):
        cancelled = [p for p in self.pairs
                     if not p["fails"] and p["both_caught_alone"]]
        self.assertEqual(cancelled, [],
                         "pairs caught nowhere although both halves are caught: "
                         + ", ".join("+".join(p["pair"]) for p in cancelled))

    def test_no_pair_is_entirely_silent(self):
        silent = [p for p in self.pairs if not p["fails"]]
        self.assertEqual(silent, [],
                         "pairs the verifier says nothing about: "
                         + ", ".join("+".join(p["pair"]) for p in silent))

    def test_no_triple_cancels(self):
        silent = [t for t in self.triples if not t["fails"]]
        self.assertEqual(silent, [],
                         "triples caught nowhere: "
                         + ", ".join("+".join(t["triple"])
                                     for t in silent[:5]))


if __name__ == "__main__":
    unittest.main()
