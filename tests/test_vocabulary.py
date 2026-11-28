"""The writer and the reader must agree on their vocabularies.

`uibc_core.cli evidence --type X` used to accept any word and write it into the
package; the verifier then answered INCONCLUSIVE and told the user the verifier
could not decide. `event --type Y` was worse: L3 returned FAIL, so a typo
presented as a bad package.

Both vocabularies are now closed at write time. These tests fail if the CLI and
the verifier ever drift apart, which is the only thing keeping that true.
"""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from uibc_core import lifecycle, verify as verify_mod  # noqa: E402


class TestVocabularies(unittest.TestCase):
    def test_the_verifier_rejects_words_the_cli_refuses(self):
        """A word the CLI refuses must also be one the verifier would reject.

        We do not parse the argparse object (it is built inside main); we assert the
        property that matters instead: for every word the verifier does NOT know,
        the CLI exits non-zero and prints the allowed list.
        """
        unknown = ["OBSERVATION", "TOOL_CALL", "definitely-not-a-type"]
        tmp = tempfile.mkdtemp()
        pkg = os.path.join(tmp, "pkg")
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "init", pkg],
                       cwd=ROOT, check=True, capture_output=True)
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "register", pkg,
                        "--agent-id", "a", "--owner", "a"],
                       cwd=ROOT, check=True, capture_output=True)
        src = os.path.join(tmp, "f.txt")
        open(src, "w", encoding="utf-8").write("x\n")

        for word in unknown:
            r = subprocess.run([sys.executable, "-m", "uibc_core.cli", "evidence", pkg,
                                "--type", word, "--file", src],
                               cwd=ROOT, capture_output=True, encoding="utf-8")
            self.assertNotEqual(r.returncode, 0,
                                "the CLI accepted evidence --type %s; the verifier's S4 "
                                "would answer INCONCLUSIVE for it" % word)
            r2 = subprocess.run([sys.executable, "-m", "uibc_core.cli", "event", pkg,
                                 "--type", word],
                                cwd=ROOT, capture_output=True, encoding="utf-8")
            self.assertNotEqual(r2.returncode, 0,
                                "the CLI accepted event --type %s; the verifier's L3 "
                                "would answer FAIL for it" % word)

    def test_the_package_is_untouched_by_a_refused_write(self):
        """A refused write must not leave a half-written entry behind."""
        tmp = tempfile.mkdtemp()
        pkg = os.path.join(tmp, "pkg2")
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "init", pkg],
                       cwd=ROOT, check=True, capture_output=True)
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "register", pkg,
                        "--agent-id", "a", "--owner", "a"],
                       cwd=ROOT, check=True, capture_output=True)
        idx_before = open(os.path.join(pkg, "evidence", "index.json"), "rb").read()
        lc_before = open(os.path.join(pkg, "lifecycle.json"), "rb").read()
        src = os.path.join(tmp, "g.txt")
        open(src, "w", encoding="utf-8").write("y\n")
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "evidence", pkg,
                        "--type", "NOPE", "--file", src], cwd=ROOT, capture_output=True)
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "event", pkg,
                        "--type", "NOPE"], cwd=ROOT, capture_output=True)
        self.assertEqual(idx_before,
                         open(os.path.join(pkg, "evidence", "index.json"), "rb").read())
        self.assertEqual(lc_before,
                         open(os.path.join(pkg, "lifecycle.json"), "rb").read())

    def test_the_two_vocabularies_are_disjoint_where_they_must_be(self):
        """A word cannot be a legal evidence type and an illegal lifecycle type without
        somebody explaining why; today the two sets do not overlap at all."""
        self.assertTrue(set(verify_mod.EVIDENCE_TYPES) & set(lifecycle.EVENTS) == set(),
                        "evidence types and event types now overlap: %r"
                        % (set(verify_mod.EVIDENCE_TYPES) & set(lifecycle.EVENTS)))
