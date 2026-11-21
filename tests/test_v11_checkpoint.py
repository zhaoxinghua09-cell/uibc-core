"""S8 / S9: the checkpoint head, and what it can and cannot prove.

The distinction under test (draft-bailey-scitt-agent-session-receipt:
head commitment; draft-maintainer-1f916-agent-record-01 S3.6: an
observation made outside the store):
  * inside one package, a shortened log is caught by the committed head (S8);
  * a whole package replaced by an older, fully self-consistent one is
    invisible to anything inside it, and needs an out-of-band head (S9).
"""

import json
import os
import shutil
import tempfile
import unittest

from uibc_core import cli as ucli
from uibc_core.signing import ed_generate_seed
from uibc_core.verify import verify


def _a(**kw):
    return type("A", (), kw)()


class CheckpointCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ckpt-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        self.seed = ed_generate_seed()
        self.key = os.path.join(self.tmp, "k.edkey")
        with open(self.key, "w", encoding="ascii") as f:
            f.write("ed25519:" + self.seed.hex())
        self._build(self.pkg, seal=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, path, seal=True):
        ucli.cmd_init(_a(path=path))
        ucli.cmd_register(_a(path=path, agent_id="a1", owner="o",
                             agent_type="software-agent", version="1"))
        ucli.cmd_event(_a(path=path, type="ACTIVATE", actor=None))
        src = os.path.join(os.path.dirname(path), "ev.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("e1\n")
        ucli.cmd_evidence(_a(path=path, type="ACTION", file=src,
                             media_type="text/plain", note=""))
        ucli.cmd_submit(_a(path=path, key=self.key if seal else None))

    def _head(self, path):
        with open(os.path.join(path, "manifest.json"), encoding="utf-8") as f:
            return json.load(f)["checkpoint_head"]

    def test_head_is_sealed_and_present(self):
        with open(os.path.join(self.pkg, "manifest.json"), encoding="utf-8") as f:
            man = json.load(f)
        self.assertIn("checkpoint_head", man)
        self.assertIn("lifecycle_head", man)
        r = verify(self.pkg, pubkey=__import__("uibc_core.ed25519",
                                               fromlist=["x"]).publickey(self.seed))
        checks = {c["id"]: c["result"] for c in r["checks"]}
        self.assertEqual(checks["S8"], "PASS")
        self.assertEqual(r["result"], "PASS")

    def test_truncated_unsigned_log_fails_s8(self):
        p = os.path.join(self.tmp, "u.uibc")
        self._build(p, seal=False)
        lc = json.load(open(os.path.join(p, "lifecycle.json"), encoding="utf-8"))
        lc["events"] = lc["events"][:-1]
        json.dump(lc, open(os.path.join(p, "lifecycle.json"), "w",
                           encoding="utf-8"))
        r = verify(p)
        checks = {c["id"]: c["result"] for c in r["checks"]}
        self.assertEqual(checks["S8"], "FAIL")
        self.assertEqual(r["result"], "FAIL")

    def test_rollback_is_invisible_without_a_pin_and_caught_with_one(self):
        newer = os.path.join(self.tmp, "newer.uibc")
        shutil.copytree(self.pkg, newer)
        src = os.path.join(self.tmp, "ev2.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("e2\n")
        ucli.cmd_evidence(_a(path=newer, type="INCIDENT", file=src,
                             media_type="text/plain", note=""))
        ucli.cmd_submit(_a(path=newer, key=self.key))
        newest_head = self._head(newer)

        # the older package as delivered: entirely valid on its own
        self.assertEqual(verify(self.pkg)["result"], "PASS")
        # only an out-of-band observation of the head can see the rollback
        r = verify(self.pkg, expect_head=newest_head)
        checks = {c["id"]: c["result"] for c in r["checks"]}
        self.assertEqual(checks["S9"], "FAIL")
        self.assertEqual(r["result"], "FAIL")

    def test_matching_pin_passes(self):
        r = verify(self.pkg, expect_head=self._head(self.pkg))
        checks = {c["id"]: c["result"] for c in r["checks"]}
        self.assertEqual(checks["S9"], "PASS")
        self.assertEqual(r["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
