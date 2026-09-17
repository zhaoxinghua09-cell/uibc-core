"""UIBC-MEM v0.1 tests (task G4): verifiable memory migration.

Four Preservations (2026-09-17 route screenshots):
  M2 Fact / M3 Attribution / M4 Citation / M5 Version
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.memory import memory_root, verify_migration


def _entry(mid, content="the bone implant passed cleaning validation",
           attribution="lab-a", citation="report-2026-630.pdf#p3", version="v1"):
    return {"memory_id": mid, "content": content, "attribution": attribution,
            "citation": citation, "version": version}


def _faithful_target(source):
    """Simulate a migration that copies everything (possibly reordered)."""
    return [dict(e) for e in reversed(source)]  # order flipped on purpose


class MemoryMigrationTests(unittest.TestCase):

    def setUp(self):
        self.source = [_entry("m1"), _entry("m2", content="NiTi bends at 134C"),
                       _entry("m3", content="GMP 2025 effective 2026-11-01",
                              citation="gmp-draft.md#s2")]

    # 1. faithful migration (reordered) -> PASS all four
    def test_01_faithful_reordered_passes(self):
        r = verify_migration(self.source, _faithful_target(self.source))
        self.assertEqual(r["result"], "PASS")
        for cid in ("M1", "M2", "M3", "M4", "M5"):
            ids = {c["id"]: c["result"] for c in r["checks"]}
            self.assertEqual(ids[cid], "PASS", cid)

    # 2. content changed -> Fact Preservation FAIL only
    def test_02_fact_change_fails_m2(self):
        target = _faithful_target(self.source)
        target[0]["content"] += " (paraphrased)"
        r = verify_migration(self.source, target)
        ids = {c["id"]: c["result"] for c in r["checks"]}
        self.assertEqual(ids["M2"], "FAIL")
        self.assertEqual(ids["M3"], "PASS")  # others unaffected
        self.assertEqual(r["result"], "FAIL")

    # 3. attribution changed -> M3 FAIL
    def test_03_attribution_change_fails_m3(self):
        target = _faithful_target(self.source)
        target[1]["attribution"] = "lab-b"
        ids = {c["id"]: c["result"] for c in verify_migration(self.source, target)["checks"]}
        self.assertEqual(ids["M3"], "FAIL")

    # 4. citation changed -> M4 FAIL
    def test_04_citation_change_fails_m4(self):
        target = _faithful_target(self.source)
        target[2]["citation"] = "some-blog.example"
        ids = {c["id"]: c["result"] for c in verify_migration(self.source, target)["checks"]}
        self.assertEqual(ids["M4"], "FAIL")

    # 5. version changed -> M5 FAIL
    def test_05_version_change_fails_m5(self):
        target = _faithful_target(self.source)
        target[0]["version"] = "v2"
        ids = {c["id"]: c["result"] for c in verify_migration(self.source, target)["checks"]}
        self.assertEqual(ids["M5"], "FAIL")

    # 6. missing entry in target -> M1 FAIL
    def test_06_missing_entry_fails(self):
        target = _faithful_target(self.source)[:-1]
        r = verify_migration(self.source, target)
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("missing", r["checks"][0]["detail"])

    # 7. injected entry in target -> M1 FAIL (memory injection attack)
    def test_07_injected_entry_fails(self):
        target = _faithful_target(self.source) + [_entry("mX", content="malicious fact")]
        r = verify_migration(self.source, target)
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("injected", r["checks"][0]["detail"])

    # 8. duplicate memory_id in source -> MALFORMED_INPUT
    def test_08_duplicate_ids_malformed(self):
        src = self.source + [_entry("m1", content="dup")]
        r = verify_migration(src, _faithful_target(self.source))
        self.assertEqual(r["result_code"], "MALFORMED_INPUT")

    # 9. memory_root is order-independent
    def test_09_root_order_independent(self):
        self.assertEqual(memory_root(self.source), memory_root(list(reversed(self.source))))
        r = memory_root(self.source)
        self.assertEqual(len(r), 64)

    # 10. report discipline: scope states semantic drift NOT checked
    def test_10_scope_honest(self):
        r = verify_migration(self.source, _faithful_target(self.source))
        self.assertIn("semantic drift", r["scope"])
        self.assertIn("NOT checked", r["scope"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
