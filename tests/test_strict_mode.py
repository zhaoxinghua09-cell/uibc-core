"""The one gap the docs kept admitting, closed by a mode and then by a version.

Before this, a file dropped into evidence/ that the index never promised stayed
a note. The reason was real: the format itself puts the tree, the chain, the
anchors and the policy artefacts there, so failing every undeclared file broke
every existing package. --strict was the mode. Format v2 is the durable
fix (release 0.5.6; the tree still ships 0.5.5 until the artefacts exist):
the producer declares the version, and from v2 the default is FAIL, while
v1 packages keep being judged by the rules in force when they were sealed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import outsider_audit as oa
from uibc_core.verify import verify

CLEAN = os.path.join(_REPO, "fixtures", "clean.uibc")


def s1(report):
    return next(c for c in report["checks"] if c["id"] == "S1")


def set_format(pkg, value):
    """Edit manifest.format_version in place.

    The edit invalidates the seal (S6), which is not what these cases are about:
    S1 is a pure structure check and is resolved before the seal is read.
    """
    path = os.path.join(pkg, "manifest.json")
    with open(path, encoding="utf-8") as f:
        man = json.load(f)
    if value is None:
        man.pop("format_version", None)
    else:
        man["format_version"] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)


class TestStrictMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _extra(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        with open(os.path.join(pkg, "evidence", "extra.txt"), "w") as f:
            f.write("an uncommitted note\n")
        return pkg

    def test_lenient_mode_only_notes(self):
        pkg = self._extra()
        r = verify(pkg)
        self.assertEqual(s1(r)["result"], "PASS")
        self.assertIn("extra.txt", s1(r)["detail"])
        self.assertFalse(r["strict"])

    def test_lenient_pass_names_what_it_ignored(self):
        """A PASS that let a file through must say which file.

        ERM family M06 (measured 2026-11-27): an undeclared file under
        evidence/ passed all three tiers because the default is lenient. With
        no field naming it, a caller had to parse a detail string to find out
        that the verdict was narrower than it looked.
        """
        pkg = self._extra()
        r = verify(pkg)
        # The top-level verdict may still be INCONCLUSIVE for unrelated reasons
        # (an unanchored run cannot claim a witness); what matters here is S1.
        self.assertEqual(s1(r)["result"], "PASS")
        self.assertEqual(len(r["warnings"]), 1)
        self.assertEqual(r["warnings"][0]["code"], "S1_UNCOMMITTED_EVIDENCE")
        self.assertIn("extra.txt", r["warnings"][0]["detail"])

    def test_strict_mode_reports_no_uncommitted_warning(self):
        pkg = self._extra()
        r = verify(pkg, strict=True)
        self.assertEqual(r["warnings"], [], "strict already failed them; no warning to raise")

    def test_a_clean_package_carries_no_warnings(self):
        r = verify(CLEAN)
        self.assertEqual(r["warnings"], [])

    def test_strict_mode_fails_the_uncommitted_file(self):
        pkg = self._extra()
        r = verify(pkg, strict=True)
        self.assertEqual(s1(r)["result"], "FAIL")
        self.assertIn("uncommitted files under evidence/", s1(r)["detail"])
        self.assertEqual(r["result"], "FAIL")
        self.assertTrue(r["strict"])

    def test_structural_members_stay_exempt(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        oa.build_v11(pkg)          # adds evidence/merkle.json and chain.json
        r = verify(pkg, strict=True)
        self.assertEqual(s1(r)["result"], "PASS",
                         "the format's own structural files must not be called uncommitted")

    def test_a_clean_package_passes_in_both_modes(self):
        for strict in (False, True):
            r = verify(CLEAN, strict=strict)
            self.assertEqual(s1(r)["result"], "PASS")

    def test_cli_exposes_the_flag(self):
        pkg = self._extra()
        out = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify", pkg,
                              "--strict"], capture_output=True, text=True, cwd=_REPO)
        self.assertIn('"strict": true', out.stdout)
        self.assertEqual(out.returncode, 1)


class TestFormatV2(unittest.TestCase):
    """v2 turns the flag into the default, without a flag being passed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _extra(self, fmt):
        pkg = oa._prepare(CLEAN, self.tmp)
        set_format(pkg, fmt)
        with open(os.path.join(pkg, "evidence", "extra.txt"), "w") as f:
            f.write("an uncommitted note\n")
        return pkg

    def test_v2_fails_undeclared_evidence_without_the_flag(self):
        pkg = self._extra(2)
        r = verify(pkg)
        self.assertFalse(r["strict"], "the caller passed no flag; the format did this")
        self.assertEqual(r["format_version"], 2)
        self.assertEqual(s1(r)["result"], "FAIL")
        self.assertIn("uncommitted files under evidence/", s1(r)["detail"])
        self.assertEqual(r["warnings"], [],
                         "v2 fails them outright, so there is nothing left to warn about")

    def test_v2_clean_package_passes_s1(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        set_format(pkg, 2)
        self.assertEqual(s1(verify(pkg))["result"], "PASS")

    def test_v2_still_exempts_the_formats_own_members(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        oa.build_v11(pkg)
        set_format(pkg, 2)
        self.assertEqual(s1(verify(pkg))["result"], "PASS",
                         "v2 tightens undeclared files, not the tree and chain "
                         "the format itself places under evidence/")

    def test_v1_keeps_the_note_and_the_warning(self):
        """A package sealed before v2 is judged by the rules in force then."""
        pkg = self._extra(None)
        r = verify(pkg)
        self.assertEqual(r["format_version"], 1)
        self.assertEqual(s1(r)["result"], "PASS")
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("format v1", r["warnings"][0]["detail"])

    def test_an_unknown_format_version_is_not_judged_as_v1(self):
        """v3 is not v1 with a bigger number.

        Applying v1 rules to a package written to a format this verifier has
        never read would let it report PASS on rules that no longer apply - the
        same failure as certifying a min_verifier_version it is below.
        """
        pkg = self._extra(3)
        r = verify(pkg)
        self.assertEqual(s1(r)["result"], "INCONCLUSIVE")
        self.assertIn("format_version=3", s1(r)["detail"])

    def test_the_package_lock_is_not_evidence(self):
        """uibc_core/locking.py drops evidence/.lock next to the index.

        Under v2 that made every freshly sealed package FAIL - caught by this
        change before it shipped, not by a user. The exemption is by exact
        name, and the next test proves it did not become "any dotfile".
        """
        pkg = oa._prepare(CLEAN, self.tmp)
        set_format(pkg, 2)
        with open(os.path.join(pkg, "evidence", ".lock"), "wb") as f:
            f.write(b"\0")
        self.assertEqual(s1(verify(pkg))["result"], "PASS")

    def test_a_dotfile_cannot_hide_behind_the_lock_exemption(self):
        pkg = oa._prepare(CLEAN, self.tmp)
        set_format(pkg, 2)
        with open(os.path.join(pkg, "evidence", ".payload"), "w") as f:
            f.write("hidden\n")
        self.assertEqual(s1(verify(pkg))["result"], "FAIL")
        self.assertIn(".payload", s1(verify(pkg))["detail"])


if __name__ == "__main__":
    unittest.main()
