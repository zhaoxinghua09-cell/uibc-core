"""Pre-push account gate: the parsing half is testable without a network.

The live check calls api.github.com; these tests only pin the part that decides
which owner a remote URL claims, because a wrong parse silently turns the gate
into a no-op - the worst failure mode for a safety check.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from pre_push_gate import remote_owner  # noqa: E402


class TestRemoteOwner(unittest.TestCase):
    def test_https(self):
        self.assertEqual(remote_owner("https://github.com/zhaoxinghua09-cell/uibc-core.git"),
                         "zhaoxinghua09-cell")

    def test_ssh_scp_style(self):
        self.assertEqual(remote_owner("git@github.com:stevenzhao07/repo.git"), "stevenzhao07")

    def test_case_is_normalised(self):
        self.assertEqual(remote_owner("https://github.com/ZhaoXing/Repo.git"), "zhaoxing")

    def test_non_github_is_rejected(self):
        # fail closed: a non-GitHub remote must not silently pass as "no owner"
        self.assertIsNone(remote_owner("https://gitlab.com/owner/repo.git"))
        self.assertIsNone(remote_owner(None))


if __name__ == "__main__":
    unittest.main()
