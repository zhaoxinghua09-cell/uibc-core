"""S11 strict serialization: the encoding layer, where a parse can disagree with a reader.

These cases are taken from the AER-1 conformance corpus's must-fail set - duplicate
member name, raw control character, non-UTF-8 bytes - because "we can do what they
did, but stricter" has to mean something measurable. A plain json.load() accepts all
three here: Python keeps the LAST duplicate, an editor hides the control char, and a
non-UTF-8 file raises only if you happen to decode strictly. Each test below is
therefore both a regression guard and a claim about the boundary.
"""
import json
import os
import shutil
import tempfile
import unittest

from uibc_core.verify import verify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "benchmark", "corpus", "base")


def _ids(rep):
    return {c["id"]: c["result"] for c in rep["checks"]}


class TestStrictSerialization(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s11-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        shutil.copytree(BASE, self.pkg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _path(self, rel="manifest.json"):
        return os.path.join(self.pkg, rel)

    def test_clean_package_passes_s11(self):
        rep = verify(self.pkg)
        self.assertEqual(_ids(rep).get("S11"), "PASS", rep["checks"])

    def test_duplicate_member_name_fails(self):
        p = self._path()
        text = open(p, encoding="utf-8").read()
        # insert a second "spec_version" member: json.load keeps the last one
        marker = '"agent_id"'
        self.assertIn(marker, text)
        text = text.replace(marker, '"agent_id": "decoy", ' + marker, 1)
        open(p, "w", encoding="utf-8").write(text)
        rep = verify(self.pkg)
        self.assertEqual(_ids(rep).get("S11"), "FAIL")
        self.assertEqual(rep["result"], "FAIL")

    def test_raw_control_character_fails(self):
        p = self._path()
        text = open(p, encoding="utf-8").read()
        text = text.replace("{", "{\u0007", 1)
        open(p, "w", encoding="utf-8").write(text)
        rep = verify(self.pkg)
        self.assertEqual(_ids(rep).get("S11"), "FAIL")

    def test_non_utf8_bytes_fail(self):
        p = self._path()
        raw = open(p, "rb").read()
        open(p, "wb").write(raw.replace(b'"', b"\xff", 1))
        rep = verify(self.pkg)
        self.assertEqual(_ids(rep).get("S11"), "FAIL")
        self.assertEqual(rep["result"], "FAIL")

    def test_tabs_and_newlines_are_not_control_violations(self):
        # Pretty-printed JSON is full of \t and \n; flagging those would reject
        # every human-readable package.
        p = self._path()
        obj = json.load(open(p, encoding="utf-8"))
        open(p, "w", encoding="utf-8").write(json.dumps(obj, indent="\t"))
        rep = verify(self.pkg)
        self.assertEqual(_ids(rep).get("S11"), "PASS")


if __name__ == "__main__":
    unittest.main()
