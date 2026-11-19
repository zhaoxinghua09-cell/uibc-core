"""The channel split is a claim about where the anchor lives; this checks its shape.

Offline on purpose - the live cross-channel check needs the release to be
reachable, and a third party's outage is not our CI's problem. What is worth
pinning here is that the repository copy and the published copy are named in
exactly one place each, so a mismatch is loud rather than silent.
"""

import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(REPO, *p), encoding="utf-8") as fh:
        return fh.read()


class TestChannel(unittest.TestCase):
    def test_the_release_url_points_at_the_published_anchor(self):
        src = _read("tools", "check_channel.py")
        self.assertIn("releases/download/anchor-001/anchor.json", src)

    def test_the_local_anchor_is_present_to_compare_against(self):
        self.assertTrue(os.path.isfile(os.path.join(REPO, "anchors", "001", "anchor.json")))

    def test_the_doc_names_the_channel_it_did_not_take(self):
        doc = _read("docs", "ANCHOR-CHANNEL.md")
        for alternative in ("DNS TXT", "邮件列表存档"):
            self.assertIn(alternative, doc, "the doc stopped saying which channels were declined")


if __name__ == "__main__":
    unittest.main()
