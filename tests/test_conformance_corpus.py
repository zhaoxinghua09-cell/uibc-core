"""The committed oracle corpus must still produce the committed answers.

`conformance/oracle/` is data, not a build product: a third party can run their
verifier on these packages without installing anything of ours. It sits beside the
older `conformance/` archive, which is a released zip and a different thing.

That only holds if the bytes and the answers cannot drift apart, so this test
re-verifies every written package and compares against `expected.json`. If it fails,
the corpus is lying and must not be published.
"""

import json
import os
import tempfile
import unittest

from uibc_core.verify import verify

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(HERE, "conformance", "oracle")


def _first_fail(report):
    """Lowest check number that actually FAILs.

    Not the first line the report prints (the report is not in S order), and not any
    non-PASS result: in open mode the seal check reports INCONCLUSIVE rather than
    FAIL, and counting that would name the seal as the failure of a case built to
    reach S8.
    """
    def num(cid):
        digits = "".join(ch for ch in cid if ch.isdigit())
        return int(digits) if digits else 10 ** 6

    failing = [c["id"] for c in report["checks"] if c["result"] == "FAIL"]
    return min(failing, key=num) if failing else None


class TestCommittedCorpus(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(CORPUS, "expected.json"), encoding="utf-8") as f:
            self.expected = json.load(f)["cases"]
        with open(os.path.join(CORPUS, "keys.json"), encoding="utf-8") as f:
            self.keys = json.load(f)["keys"]

    def test_every_case_still_produces_the_declared_answer(self):
        self.assertTrue(self.expected, "corpus is empty")
        for row in self.expected:
            with self.subTest(case=row["case"]):
                case_dir = os.path.join(CORPUS, "cases", row["case"])
                self.assertTrue(os.path.isdir(case_dir), "missing case directory")
                key = (bytes.fromhex(self.keys[row["case"]])
                       if row.get("mode") == "strict" else None)
                # S9 and S19 are decided by input the package cannot carry; the
                # corpus ships it in expected.json so the case stays checkable
                # without the reader inventing a head or a memory.
                extra = {}
                state_tmp = None
                if row.get("expect_head"):
                    extra["expect_head"] = row["expect_head"]
                if row.get("state"):
                    fd, state_tmp = tempfile.mkstemp(prefix="state-", suffix=".json")
                    os.close(fd)
                    with open(state_tmp, "w", encoding="utf-8", newline="\n") as f:
                        json.dump(row["state"], f, indent=1, sort_keys=True)
                    extra["state_file"] = state_tmp
                try:
                    report = verify(case_dir, key=key, **extra)
                finally:
                    if state_tmp and os.path.exists(state_tmp):
                        os.remove(state_tmp)
                self.assertEqual(row["expected_verdict"], report["result"],
                                 "%s: verdict drifted" % row["case"])
                if row["kind"] == "reject":
                    self.assertEqual(row["expected_first_fail"], _first_fail(report),
                                     "%s: first failing check drifted" % row["case"])

    def test_both_halves_are_present(self):
        kinds = {row["kind"] for row in self.expected}
        self.assertIn("accept", kinds, "a corpus of only reject cases is passed by "
                                       "a verifier that rejects everything")
        self.assertIn("reject", kinds)
        accepts = [r for r in self.expected if r["kind"] == "accept"]
        self.assertGreaterEqual(len(accepts), 5)

    def test_the_readme_says_what_it_does_not_prove(self):
        with open(os.path.join(CORPUS, "README.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("does not prove", text)
        self.assertIn("unmeasured, not impossible", text)


if __name__ == "__main__":
    unittest.main()
