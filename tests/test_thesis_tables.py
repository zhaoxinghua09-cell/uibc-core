"""The chapter tables must agree with the tools, or the chapter is fiction."""
import os
import re
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_thesis_tables as bt


class TestThesisTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = bt.build()
        cls.md = bt.md(cls.d)

    def test_table_5_1_lists_every_check_with_a_class(self):
        rows = self.d["checks"]
        self.assertEqual(len(rows), len(bt.basis.BASIS))
        for _cid, _note, cls, _cite in rows:
            self.assertIn(cls, bt.basis.CLASS_LABEL.values())

    def test_table_5_2_sums_to_the_check_count(self):
        self.assertEqual(sum(self.d["basis"].values()), len(bt.basis.BASIS))

    def test_table_5_3_matches_the_matrix(self):
        self.assertIn("| 受测攻击数 | %d |" % self.d["matrix"]["n_attacks"], self.md)
        self.assertIn("| 仅使一项检查 FAIL 的攻击数 | %d |" % len(self.d["matrix"]["isolated"]),
                      self.md)
        self.assertEqual(self.d["matrix"]["unreached"], [])

    def test_every_table_5_states_how_to_regenerate_it(self):
        for n in range(1, 7):
            block = self.md.split("## 表 5-%d" % n)
            self.assertEqual(len(block), 2, "表 5-%d missing" % n)
            self.assertIn("数据来源", block[1].split("## ")[0])

    def test_the_honest_boundary_section_survives(self):
        self.assertIn("未纳入本章的项", self.md)
        self.assertIn("外部第三方独立见证", self.md)

    def test_latency_is_read_not_invented(self):
        lat = self.d["lat"]["median"]
        self.assertRegex(lat, r"^\d+(\.\d+)?$")
        self.assertIn("中位延迟 | %s ms" % lat, self.md)

    def test_the_committed_chapter_is_what_the_tool_builds(self):
        """The chapter drifted once: 表 5-2 still summed to 19 after a twentieth
        check landed, so the prose contradicted the code it cites.

        Only 表 5-1 … 5-3 are compared: from 表 5-4 on, the numbers depend on
        which optional dependencies are installed, so an equality check over the
        whole file is an environment check wearing a drift check's clothes. That
        is how this guard first failed -- green locally, red in `test-with-extras`.
        """
        path = os.path.join(_REPO, "docs", "THESIS-CH5-TABLES.md")
        with open(path, encoding="utf-8") as fh:
            on_disk = fh.read().replace("\r\n", "\n")
        built = self.md.replace("\r\n", "\n")
        cut = built.index("## 表 5-4")
        self.assertEqual(on_disk[:cut].strip(), built[:cut].strip(),
                         "docs/THESIS-CH5-TABLES.md 表 5-1…5-3 are stale; regenerate with "
                         "`python tools/build_thesis_tables.py > docs/THESIS-CH5-TABLES.md`")


if __name__ == "__main__":
    unittest.main()
