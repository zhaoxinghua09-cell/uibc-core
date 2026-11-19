import json
import os
import shutil
import tempfile
import unittest

from uibc_core.verify import verify

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(_REPO, "fixtures", "clean.uibc")


class TestIdentifiersMayContainSpaces(unittest.TestCase):
    """Found 2026-11-19 while running the M1 migration vector by hand.

    S12 treated any character below 0x21 as a control character, which includes
    the space (0x20). An owner recorded as "Xinghua Zhao" therefore failed S12 -
    a false FAIL on a correct package. Refusing a valid package is the mirror
    image of the silent PASS defect: a verifier that rejects correct input
    teaches its users to mistrust it, and then they ignore it when it is right.
    """

    def _package_with_owner(self, owner):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        path = os.path.join(pkg, "identity.json")
        doc = json.load(open(path, encoding="utf-8"))
        doc["owner"] = owner
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        return pkg

    def _s12(self, pkg):
        return {c["id"]: c for c in verify(pkg)["checks"]}["S12"]

    def test_an_owner_name_with_an_internal_space_is_accepted(self):
        for owner in ("Xinghua Zhao", "MedXpert Inc", "Zhejiang University"):
            with self.subTest(owner=owner):
                detail = self._s12(self._package_with_owner(owner))
                self.assertEqual(detail["result"], "PASS", detail["detail"])

    def test_a_trailing_space_is_still_rejected(self):
        detail = self._s12(self._package_with_owner("Xinghua Zhao "))
        self.assertEqual(detail["result"], "FAIL", detail["detail"])

    def test_a_leading_space_is_still_rejected(self):
        detail = self._s12(self._package_with_owner(" Xinghua Zhao"))
        self.assertEqual(detail["result"], "FAIL", detail["detail"])

    def test_a_control_character_is_still_rejected(self):
        for bad in ("Xinghua\tZhao", "Xinghua\x00Zhao", "Xinghua\x7fZhao"):
            with self.subTest(owner=bad):
                detail = self._s12(self._package_with_owner(bad))
                self.assertEqual(detail["result"], "FAIL", detail["detail"])


if __name__ == "__main__":
    unittest.main()
