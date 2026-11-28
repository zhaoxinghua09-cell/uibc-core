"""The two-run freshness vectors: bytes on disk, both readers, both directions.

S19 cannot be pinned by a single package, which is why this corpus is pairs
(state file + package overlay + required verdict). These tests hold four
things: the generator reproduces the files on disk, both readers reach the
recorded verdict on all of them, all four outcomes actually occur (a corpus
where everything says FAIL tests nothing about PASS), and the recorded head is
the one the sealed package computes to rather than a constant.
"""
import json
import os
import subprocess
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_freshness_vectors as gen  # noqa: E402
import run_freshness_vectors as replay  # noqa: E402


class TestFreshnessVectors(unittest.TestCase):
    def test_the_generator_reproduces_the_files_on_disk(self):
        out = subprocess.run([sys.executable, os.path.join(_REPO, "tools",
                                                           "build_freshness_vectors.py"),
                              "--check"], cwd=_REPO, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_the_corpus_is_pairs_not_single_packages(self):
        doc = gen.load() if hasattr(gen, "load") else json.load(
            open(os.path.join(_REPO, "conformance", "freshness", "cases.json"), encoding="utf-8"))
        self.assertEqual(doc["schema"], "uibc-freshness-vectors/1")
        # At least one case must carry the state that produces its verdict, or it
        # is a single-package vector wearing a pair's clothes.
        with_state = [c for c in doc["cases"] if c.get("state")]
        self.assertGreaterEqual(len(with_state), 5)

    def test_every_case_reaches_the_recorded_verdict_in_both_readers(self):
        rs = replay.replay(use_node=True)
        bad = [r for r in rs if not r["ok"]]
        self.assertEqual(bad, [], json.dumps(bad, ensure_ascii=False, indent=1))

    def test_all_four_outcomes_occur(self):
        doc = json.load(open(os.path.join(_REPO, "conformance", "freshness", "cases.json"),
                             encoding="utf-8"))
        verdicts = {c["expect"] for c in doc["cases"]}
        self.assertEqual(verdicts, {"INCONCLUSIVE", "PASS", "FAIL", "ABSENT"},
                         "a corpus with one verdict proves nothing about the others")

    def test_absent_means_no_line_not_a_pass(self):
        doc = json.load(open(os.path.join(_REPO, "conformance", "freshness", "cases.json"),
                             encoding="utf-8"))
        absent = [c for c in doc["cases"] if c["expect"] == "ABSENT"]
        self.assertTrue(absent)
        for c in absent:
            self.assertIsNone(c.get("state"))

    def test_the_recorded_head_is_the_one_the_package_computes(self):
        doc = json.load(open(os.path.join(_REPO, "conformance", "freshness", "cases.json"),
                             encoding="utf-8"))
        self.assertEqual(doc["head"], gen.demo_head())


if __name__ == "__main__":
    unittest.main()
