"""v1.1 semantics: the anchor rule and key-custody disclosure.

Both come from draft-maintainer-1f916-agent-record-01:
  * Section 3.6 "anchor rule": a verification run is ANCHORED only when at
    least one key reached the verifier through a channel the artifact does
    not control. A key read out of the package under test proves internal
    consistency and nothing more.
  * Section 3.1: a signature proves exactly what its custody disclosure
    permits it to prove, and verifiers MUST surface custody alongside the
    signature result.

These tests exist because the mutation benchmark reported M17 (key
substitution) as an open-mode PASS. That PASS is correct ONLY if it is
labelled unanchored; reported as plain "PASS" it overstates what was proven.
"""

import json
import os
import shutil
import tempfile
import unittest

from uibc_core import cli as ucli
from uibc_core.signing import ed_generate_seed, ed_public_key
from uibc_core.verify import verify


def _a(**kw):
    return type("A", (), kw)()


class AnchorCustodyCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v11-anchor-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        ucli.cmd_init(_a(path=self.pkg))
        ucli.cmd_register(_a(path=self.pkg, agent_id="a1", owner="owner",
                             agent_type="software-agent", version="1",
                             principal_type="SERVICE",
                             logical_agent_id="a1", run_id="r1",
                             key_custody="hsm"))
        src = os.path.join(self.tmp, "ev.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("evidence v1\n")
        ucli.cmd_evidence(_a(path=self.pkg, type="ACTION", file=src,
                             media_type="text/plain", note=""))
        self.seed = ed_generate_seed()
        self.pub = ed_public_key(self.seed)
        self.key = os.path.join(self.tmp, "k.edkey")
        with open(self.key, "w", encoding="ascii") as f:
            f.write("ed25519:" + self.seed.hex())
        ucli.cmd_submit(_a(path=self.pkg, key=self.key))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_open_mode_is_unanchored_despite_pass(self):
        rep = verify(self.pkg)
        self.assertEqual(rep["result"], "PASS")
        self.assertEqual(rep["trust_level"], "unanchored")
        self.assertIn("Anchor rule", " ".join(rep["limitations"]))

    def test_pinned_pubkey_is_anchored(self):
        rep = verify(self.pkg, pubkey=self.pub)
        self.assertEqual(rep["result"], "PASS")
        self.assertEqual(rep["trust_level"], "anchored")

    def test_custody_is_surfaced(self):
        rep = verify(self.pkg)
        self.assertEqual(rep["key_custody"], "hsm")

    def test_bad_custody_fails_s2(self):
        path = os.path.join(self.pkg, "identity.json")
        ident = json.load(open(path, encoding="utf-8"))
        ident["key_custody"] = "not_a_real_value"
        json.dump(ident, open(path, "w", encoding="utf-8"))
        rep = verify(self.pkg)
        self.assertEqual(rep["result"], "FAIL")
        s2 = [c for c in rep["checks"] if c["id"] == "S2"][0]
        self.assertEqual(s2["result"], "FAIL")
        self.assertIn("key_custody", s2["detail"])


if __name__ == "__main__":
    unittest.main()
