"""Hostile input is a verdict, not a traceback.

The conformance suite asks whether the verifier refuses the packages we
thought of. This asks whether it survives the bytes nobody thought of: not
JSON, a NaN literal, 4000 levels of nesting, invalid UTF-8, a path that climbs
out of the package, a symlink to the host, an empty directory, an 8 MB
manifest.

Two properties, and neither is negotiable:

  1. Both implementations answer. A crash is not a verdict, and a verifier
     that dies tells the caller nothing about the file it was given.
  2. Both refuse. "Could not tell" about bytes that were never judged is the
     one wrong answer that looks like an honest one.

The NaN case is the reason this file exists. Python's json module accepts
NaN, so before this check a manifest carrying a bare NaN literal reached the
later checks and the package came out INCONCLUSIVE - nothing found wrong,
about bytes that are not JSON.
"""
import json
import os
import subprocess
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_REPO, "tools", "redteam_robustness.py")


@unittest.skipUnless(os.path.isdir(os.path.join(_REPO, "fixtures", "clean.uibc")),
                     "the clean fixture is required")
class TestHostileInput(unittest.TestCase):
    def test_every_hostile_input_is_answered_and_refused(self):
        out = subprocess.run([sys.executable, _SCRIPT, "--json"],
                             capture_output=True, text=True, cwd=_REPO, timeout=300)
        self.assertEqual(out.returncode, 0,
                         "redteam_robustness reported problems: %s" % out.stdout[-2000:])
        report = json.loads(out.stdout)
        self.assertEqual(report["problems"], 0)

        rows = {r["case"]: r for r in report["cases"]}
        # Ten cases, all of them refused by both implementations.
        self.assertEqual(len(rows), 10)
        for name, row in rows.items():
            self.assertTrue(row["js"].startswith("FAIL"), name)
            self.assertTrue(row["py"].startswith("FAIL"), name)

    def test_a_bare_nan_is_not_json_to_either_implementation(self):
        """The specific hole: a parser more permissive than the format.

        RFC 8259 has no NaN. Python's json module accepts it; JavaScript's
        JSON.parse does not. Whichever language one is written in, the answer
        to a NaN literal has to be the same, and it has to be FAIL.
        """
        out = subprocess.run([sys.executable, _SCRIPT, "--json"],
                             capture_output=True, text=True, cwd=_REPO, timeout=300)
        rows = {r["case"]: r for r in json.loads(out.stdout)["cases"]}
        nan = rows["nan-literal"]
        self.assertNotIn("INCONCLUSIVE", nan["py"])
        self.assertNotIn("INCONCLUSIVE", nan["js"])
        self.assertIn("S11", nan["js"] + nan["py"])


if __name__ == "__main__":
    unittest.main()
