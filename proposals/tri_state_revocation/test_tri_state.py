# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timedelta, timezone
from tri_state import Feed, classify

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
FRESH = Feed(issued_at=NOW - timedelta(minutes=10), entries={"agent:A": NOW - timedelta(hours=1)})
MAX = timedelta(hours=1)


class TriState(unittest.TestCase):
    def test_revoked_before_t(self):
        self.assertEqual(classify(FRESH, "agent:A", NOW, MAX).state, "revoked_at_t")

    def test_not_revoked_when_fresh_and_absent(self):
        self.assertEqual(classify(FRESH, "agent:B", NOW, MAX).state, "not_revoked_at_t")

    def test_stale_feed_is_undetermined(self):
        stale = Feed(issued_at=NOW - timedelta(days=2), entries={})
        self.assertEqual(classify(stale, "agent:B", NOW, MAX).state, "undetermined")

    def test_absent_feed_is_undetermined(self):
        self.assertEqual(classify(None, "agent:B", NOW, MAX).state, "undetermined")

    def test_revocation_after_t_is_undetermined(self):
        future = Feed(issued_at=NOW - timedelta(minutes=5),
                      entries={"agent:A": NOW + timedelta(hours=2)})
        self.assertEqual(classify(future, "agent:A", NOW, MAX).state, "undetermined")

    def test_clock_skew_is_undetermined(self):
        skewed = Feed(issued_at=NOW + timedelta(minutes=5), entries={})
        self.assertEqual(classify(skewed, "agent:B", NOW, MAX).state, "undetermined")

    def test_bad_signature_is_undetermined(self):
        bad = Feed(issued_at=NOW - timedelta(minutes=5), entries={}, signature_ok=False)
        self.assertEqual(classify(bad, "agent:B", NOW, MAX).state, "undetermined")


if __name__ == "__main__":
    unittest.main(verbosity=2)
