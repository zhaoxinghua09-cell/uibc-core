"""`uibc-scitt/2`: the inclusion proof is read, so OK is reachable and bounded.

Three groups of assertions:

* **OK is reachable** - and only with a trusted issuer; an unasked issuer question
  is `PARTIAL_ISSUER_UNCHECKED`, a code `/2` adds rather than reusing the `/1`
  partial code, because "issuer" and "inclusion" are different questions.
* **A wrong proof is refused, not tolerated** - a genuine path under a wrong
  index, a leaf that is not in the tree, and a `tree_size` above `count` all fail;
  a five-element vdp is malformed, not "some extension we ignore".
* **`/1` and `/2` are not interchangeable** - a valid `/1` receipt offered to `/2`
  is `FAIL_MALFORMED`, because the registered value differs in the `profile`
  member and the flat root cannot produce an inclusion path.
"""

import json
import os
import subprocess
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from uibc_core import cose_min, ed25519, merkle, profile, profile2  # noqa: E402

BASE = os.path.join(_REPO, "examples", "demo.uibc")
THREE = os.path.join(_REPO, "conformance", "profile2", "packages", "three-files")
SEED = b"\x11" * 32
PUB = ed25519.publickey(SEED).hex()


class TestTree(unittest.TestCase):
    def test_root_is_an_rfc6962_tree_not_a_flat_hash(self):
        facts = profile2.package_facts(THREE)
        self.assertEqual(facts[1], 3)
        flat = profile.package_facts(THREE)
        self.assertNotEqual(facts[0], flat[0],
                            "a /2 root that equals the /1 flat root would mean the "
                            "inclusion proof has nothing to prove against")

    def test_ok_one_leaf(self):
        root, count, agent, hashes, problems = profile2.package_facts(BASE)
        self.assertEqual(problems, [])
        value = profile2.registered_value(root, count, agent)
        res = profile2.verify(BASE, profile2.make_receipt(
            value, SEED, vdp=profile2.vdp_for_hash(hashes, hashes[0])), trusted_issuers=[PUB])
        self.assertEqual(res["verdict"], profile2.OK)

    def test_middle_leaf_of_three_has_a_two_element_path(self):
        root, count, agent, hashes, problems = profile2.package_facts(THREE)
        ordered = sorted(hashes)
        vdp = profile2.vdp_for_hash(hashes, ordered[1])
        leaf, index, size, path, why = profile2.read_vdp(vdp)
        self.assertEqual(why, "")
        self.assertEqual((index, size, len(path)), (1, 3, 2))
        value = profile2.registered_value(root, count, agent)
        res = profile2.verify(THREE, profile2.make_receipt(value, SEED, vdp=vdp),
                              trusted_issuers=[PUB])
        self.assertEqual(res["verdict"], profile2.OK)


class TestRefusals(unittest.TestCase):
    def setUp(self):
        self.root, self.count, self.agent, self.hashes, _ = profile2.package_facts(THREE)
        self.ordered = sorted(self.hashes)
        self.vdp = profile2.vdp_for_hash(self.hashes, self.ordered[1])
        self.value = profile2.registered_value(self.root, self.count, self.agent)

    def _v(self, vdp, trust=(PUB,)):
        return profile2.verify(THREE, profile2.make_receipt(self.value, SEED, vdp=vdp),
                               trusted_issuers=list(trust))

    def test_wrong_index_is_fail_inclusion(self):
        leaf, _i, _s, path, _why = profile2.read_vdp(self.vdp)
        self.assertEqual(self._v(cose_min.encode([leaf, 2, 3, path]))["verdict"],
                         profile2.FAIL_INCLUSION)

    def test_leaf_outside_the_tree_is_fail_inclusion(self):
        leaf, _i, _s, path, _why = profile2.read_vdp(self.vdp)
        other = merkle.leaf_hash(b"\x01" * 32)
        self.assertNotIn(other, [merkle.leaf_hash(bytes.fromhex(h)) for h in self.hashes])
        self.assertEqual(self._v(cose_min.encode([other, 1, 3, path]))["verdict"],
                         profile2.FAIL_INCLUSION)

    def test_size_above_count_is_fail_inclusion(self):
        leaf, _i, _s, path, _why = profile2.read_vdp(self.vdp)
        self.assertEqual(self._v(cose_min.encode([leaf, 1, 4, path]))["verdict"],
                         profile2.FAIL_INCLUSION)

    def test_five_element_vdp_is_malformed_not_extended(self):
        leaf, _i, _s, path, _why = profile2.read_vdp(self.vdp)
        self.assertEqual(self._v(cose_min.encode([leaf, 1, 3, path, b"x"]))["verdict"],
                         profile2.FAIL_MALFORMED)

    def test_issuer_unasked_is_partial_not_ok(self):
        res = self._v(self.vdp, trust=())
        self.assertEqual(res["verdict"], profile2.PARTIAL_ISSUER_UNCHECKED)
        self.assertEqual(res["issuer"], "NOT_CHECKED")

    def test_profile_ids_are_not_interchangeable(self):
        v1 = profile.package_facts(BASE)
        v1_value = profile.registered_value(v1[0], v1[1], v1[2])
        res = profile2.verify(BASE, profile.make_receipt(v1_value, SEED), trusted_issuers=[PUB])
        self.assertEqual(res["verdict"], profile2.FAIL_MALFORMED)


class TestVectors(unittest.TestCase):
    def test_recorded_cases_match_a_fresh_build(self):
        out = subprocess.run([sys.executable,
                              os.path.join(_REPO, "tools", "build_profile2_vectors.py"),
                              "--check"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_every_case_replays(self):
        from tools import run_profile2_vectors as runner
        ok, doc, rows = runner.run()
        self.assertTrue(ok, [r for r in rows if not r["ok"]])
        self.assertEqual(len(rows), 16)

    def test_four_ok_cases_and_they_are_the_recorded_ones(self):
        doc = json.load(open(os.path.join(_REPO, "conformance", "profile2", "cases.json"),
                             encoding="utf-8"))
        oks = [c["id"] for c in doc["cases"] if c["expected"]["verdict"] == profile2.OK]
        self.assertEqual(oks, doc["ok_cases"])
        self.assertEqual(len(oks), 4)


class TestSecondLanguage(unittest.TestCase):
    def test_node_agrees_case_by_case(self):
        try:
            subprocess.run(["node", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            self.skipTest("node not on PATH: %s" % exc)
        out = subprocess.run(["node", os.path.join(_REPO, "tools", "verify-js", "profile2.mjs"),
                              "--vectors", os.path.join(_REPO, "conformance", "profile2", "cases.json")],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        body = out.stdout
        self.assertIn("python and node agree", body)
        self.assertNotIn("BAD", body)

    def test_node_cli_says_ok_on_a_good_receipt(self):
        try:
            subprocess.run(["node", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            self.skipTest("node not on PATH: %s" % exc)
        receipt = os.path.join(_REPO, "conformance", "profile2", "cases", "ok-three-middle.cose")
        out = subprocess.run(["node", os.path.join(_REPO, "tools", "verify-js", "profile2.mjs"),
                              THREE, "--receipt", receipt, "--trusted-issuer", PUB],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(json.loads(out.stdout)["verdict"], "OK")


if __name__ == "__main__":
    unittest.main()
