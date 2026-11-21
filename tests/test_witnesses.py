"""The witness constants are copied from three files; drift between them is the bug.

No network here - this checks that what we cite and what the tool asks for are
the same string, which is the part a regex in a hurry gets wrong.
"""

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as fh:
        return fh.read()


class TestWitnessConstants(unittest.TestCase):
    def test_zenodo_ids_match_citation(self):
        src = _read("tools", "check_witnesses.py")
        cite = _read("CITATION.cff")
        for n in ("22821834", "22821835"):
            self.assertIn(n, src)
            self.assertIn("10.5281/zenodo." + n, cite)

    def test_swh_origin_matches_citation(self):
        src = _read("tools", "check_witnesses.py")
        cite = _read("CITATION.cff")
        m = re.search(r'"([0-9a-f]{40})"', src.split("SWH_ORIGIN =")[1].split("\n")[0])
        self.assertIsNotNone(m, "SWH_ORIGIN is not a bare 40-hex id")
        self.assertIn("swh:1:ori:" + m.group(1), cite)

    def test_rekor_index_matches_the_timestamps_readme(self):
        src = _read("tools", "check_witnesses.py")
        idx = re.search(r"REKOR_INDEX = (\d+)", src).group(1)
        self.assertIn(idx, _read("timestamps", "README.md"))

    def test_the_script_ships_in_the_sdist(self):
        # MANIFEST.in grafts whole directories; `graft tools` is what covers it,
        # and dist/ is pruned - so the witness script travels and its output does not.
        manifest = _read("MANIFEST.in")
        self.assertIn("graft tools", manifest)
        self.assertIn("prune dist", manifest)


if __name__ == "__main__":
    unittest.main()
