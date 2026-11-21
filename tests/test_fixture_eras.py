"""The two fixture sets must not be confusable, and the README must not drift.

The failure this prevents, found on 2026-11-20: `fixtures/EXPECTED.md` printed
`clean -> PASS`, and a stranger following the README ran
`uibc verify fixtures/clean.uibc` on the shipped 0.4.1 verifier and got
`INCONCLUSIVE`. The artifact was right and the document was wrong — a verifier
that cannot check a v0.3.0 HMAC seal has nothing to say about it. Nothing in the
repo noticed, because `test_archive_carries_verifier.py` only asserted the result
was one of PASS/INCONCLUSIVE, which is the shape of a test that cannot fail.

Now the claim is reinforced in three places (README banner, EXPECTED.md banner,
this file) and the README's observed table is re-derived on every run.
"""
import os
import re
import unittest

from uibc_core.verify import verify

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
README = os.path.join(_REPO, "README.md")
EXPECTED = os.path.join(_REPO, "fixtures", "EXPECTED.md")
Fixtures = os.path.join(_REPO, "fixtures")

# What the archived set actually reads on a current verifier. These are not
# expectations invented here: they are the measurement, and the test fails the
# moment an artifact or the README stops agreeing with the other.
OBSERVED = {
    "clean": "INCONCLUSIVE",
    "tampered": "FAIL",
    "deleted": "FAIL",
    "duplicated": "FAIL",
    "reordered": "FAIL",
    "migrated": "FAIL",
    "malicious": "INCONCLUSIVE",
    "malicious-keyswap": "INCONCLUSIVE",
}


def _table_rows(text):
    r"""Parse `| `a` / `b` | VERDICT |` rows into {case: verdict}."""
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*`?([a-z\-` /]+)`?\s*\|\s*(INCONCLUSIVE|PASS|FAIL)\s*\|", line)
        if not m:
            continue
        for case in m.group(1).replace("`", "").split("/"):
            case = case.strip()
            if case:
                rows[case] = m.group(2)
    return rows


class TestFixtureEras(unittest.TestCase):
    def test_the_readme_observed_table_matches_the_artifacts(self):
        with open(README, encoding="utf-8") as f:
            claimed = _table_rows(f.read())
        missing = set(OBSERVED) - set(claimed)
        self.assertFalse(missing, "README table no longer covers %s" % sorted(missing))
        for case, verdict in OBSERVED.items():
            got = verify(os.path.join(Fixtures, case + ".uibc"))["result"]
            self.assertEqual(got, verdict,
                             "%s.uibc now reads %s; the README says %s"
                             % (case, got, verdict))
            self.assertEqual(claimed[case], got,
                             "README claims %s for %s, artifact reads %s"
                             % (claimed[case], case, got))

    def test_the_archive_banner_says_what_it_is(self):
        with open(EXPECTED, encoding="utf-8") as f:
            head = f.read(1200)
        self.assertIn("ARCHIVE", head)
        self.assertIn("v0.3.0", head)
        self.assertIn("fixtures-v041", head,
                      "the archive must point at the set that is current")

    def test_the_readme_names_both_sets_and_the_third_verdict(self):
        with open(README, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("fixtures-v041/   current", text)
        self.assertIn("fixtures/        archive", text)
        self.assertIn("INCONCLUSIVE", text)

    def test_a_stranger_reading_the_archive_gets_ignorance_not_leniency(self):
        # FAIL on genuine mutation and INCONCLUSIVE on an unverifiable seal are
        # different answers. A verifier that returned PASS for `clean` would be
        # the dangerous one; one that returned FAIL would be dishonest.
        results = {c: verify(os.path.join(Fixtures, c + ".uibc"))["result"]
                   for c in ("clean", "malicious", "tampered")}
        self.assertEqual(results["clean"], "INCONCLUSIVE")
        self.assertEqual(results["malicious"], "INCONCLUSIVE")
        self.assertEqual(results["tampered"], "FAIL")


if __name__ == "__main__":
    unittest.main()
