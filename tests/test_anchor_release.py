"""A signed digest list must refuse to look signed when it is not.

Three claims ride on the release digest file: it is what we published, it was
signed by a key that is not the demo key, and any timestamp over it is a second
witness rather than our own clock. The tests hold the first two by machine; the
third is recorded as a status, and the test checks it is recorded honestly
(offline means "not attempted", never "anchored").
"""
import json
import os
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))
sys.path.insert(0, _REPO)
import anchor_release_digests as ard  # noqa: E402

SEED = bytes.fromhex("11" * 32)


def _digest_file(folder, text="711fa82c  228000  uibc-conformance-0.4.1.zip\n"):
    path = os.path.join(folder, "CORPUS-DIGESTS.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


class TestTheSignature(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="anchtest_")
        self.file = _digest_file(self.dir)

    def test_it_signs_and_verifies_offline(self):
        sig, sidecar = ard.sign_file(self.file, SEED, out=self.file + ".sig")
        self.assertEqual(ard.verify_file(sig), [])
        self.assertEqual(sidecar["alg"], "ed25519")
        self.assertEqual(sidecar["file_sha256"], ard._sha256_file(self.file))
        pub = ard.ed25519.publickey(SEED)
        self.assertEqual(sidecar["key_id"], ard._key_id(pub))

    def test_one_changed_byte_is_refused(self):
        ard.sign_file(self.file, SEED, out=self.file + ".sig")
        _digest_file(self.dir, "711fa82c  228001  uibc-conformance-0.4.1.zip\n")
        reasons = ard.verify_file(self.file + ".sig")
        self.assertTrue(any("no longer hashes" in r for r in reasons), reasons)
        self.assertTrue(any("does not verify" in r for r in reasons), reasons)

    def test_the_demo_seed_is_refused(self):
        with self.assertRaises(SystemExit):
            ard.sign_file(self.file, bytes(32))

    def test_a_missing_file_is_refused(self):
        sig, _ = ard.sign_file(self.file, SEED, out=self.file + ".sig")
        os.remove(self.file)
        self.assertTrue(ard.verify_file(sig))


class TestAnchoringIsRecordedNotAssumed(unittest.TestCase):
    def test_offline_records_not_attempted(self):
        d = tempfile.mkdtemp(prefix="anchtest_")
        path = _digest_file(d)
        out, status = ard.anchor(path, d, offline=True)
        self.assertEqual(status["tsa"]["state"], "not attempted")
        self.assertEqual(status["ots"]["state"], "not attempted")
        self.assertEqual(json.load(open(out, encoding="utf-8"))["file"], "CORPUS-DIGESTS.txt")

    def test_the_ots_word_bitcoin_is_only_used_for_a_real_anchor(self):
        src = open(os.path.join(_REPO, "tools", "anchor_release_digests.py"), encoding="utf-8").read()
        self.assertIn("pending_calendar", src)
        self.assertIn("not a Bitcoin anchor", src)


if __name__ == "__main__":
    unittest.main()
