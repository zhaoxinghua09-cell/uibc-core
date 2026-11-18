"""Concurrency and package construction: two bugs found by measuring.

Bug 1 -- 200 concurrent records left 28 entries and a package that no longer
verified. `cmd_evidence` read the index, copied the file and rewrote the
index with no lock and no atomic replace.

Bug 2 -- `uibc register` printed "registered agent" and wrote identity and
lifecycle but not the manifest, so a freshly built package verified
S2=FAIL, S5=FAIL. Every earlier test used a finished fixture and never saw it.

Both assertions below exist so neither can come back quietly.
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from adapters.frameworks.uibc_framework_hooks import CallRecorder, init_package  # noqa: E402
from uibc_core.verify import verify  # noqa: E402
from uibc_core.runtime import seal  # noqa: E402


def _entries(pkg):
    with open(os.path.join(pkg, "evidence", "index.json"), encoding="utf-8") as f:
        raw = json.load(f)
    return raw["entries"] if isinstance(raw, dict) else raw


def _checks(pkg):
    return {c["id"]: c["result"] for c in verify(pkg)["checks"]}


class TestFreshPackage(unittest.TestCase):

    def test_register_writes_the_manifest(self):
        """init + register must produce a package whose S2 and S5 pass.

        The manifest is what those two checks read. Writing identity alone is
        not enough, however convincingly the CLI says 'registered'.
        """
        tmp = tempfile.mkdtemp(prefix="uibc-build-")
        try:
            pkg = os.path.join(tmp, "pkg")
            init_package(pkg, agent_id="agent.build", owner="x.zhao")
            with open(os.path.join(pkg, "manifest.json"), encoding="utf-8") as f:
                man = json.load(f)
            self.assertEqual(man["agent_id"], "agent.build")
            self.assertEqual(man["evidence_count"], 0)
            self.assertEqual(len(man["evidence_root"]), 64)
            self.assertNotIn("_note", man, "skeleton manifest was never replaced")

            by_id = _checks(pkg)
            self.assertEqual(by_id["S2"], "PASS")
            self.assertNotEqual(by_id["S5"], "FAIL")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestConcurrentWrites(unittest.TestCase):

    THREADS = 8
    PER_THREAD = 25

    def test_no_record_is_lost_and_the_package_still_verifies(self):
        tmp = tempfile.mkdtemp(prefix="uibc-conc-")
        try:
            pkg = os.path.join(tmp, "pkg")
            init_package(pkg)
            errors = []

            def worker(t):
                rec = CallRecorder(pkg)
                for i in range(self.PER_THREAD):
                    try:
                        rec.record("t%d.tool" % t, {"i": i}, {"ok": i})
                    except Exception as exc:  # recorded, then asserted on
                        errors.append("%s: %s" % (type(exc).__name__, exc))

            threads = [threading.Thread(target=worker, args=(t,))
                       for t in range(self.THREADS)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            expected = self.THREADS * self.PER_THREAD
            self.assertEqual(errors, [], "concurrent writers raised")
            entries = _entries(pkg)
            self.assertEqual(len(entries), expected,
                             "lost %d of %d records" % (expected - len(entries), expected))

            paths = [e["path"] for e in entries]
            self.assertEqual(len(set(paths)), len(paths), "duplicate evidence path")

            files = os.listdir(os.path.join(pkg, "evidence", "files"))
            self.assertEqual(len(files), expected, "orphan or missing evidence files")

            leftovers = [f for f in os.listdir(os.path.join(pkg, "evidence"))
                         if ".tmp-" in f]
            self.assertEqual(leftovers, [], "atomic write left temp files behind")

            seal(pkg)
            by_id = _checks(pkg)
            for cid in ("S1", "S2", "S3", "S4", "S5", "S11", "S12"):
                self.assertEqual(by_id[cid], "PASS",
                                 "%s failed after concurrent writes then seal" % cid)
            self.assertEqual(by_id["S6"], "INCONCLUSIVE",
                             "an unsigned package must stay unattested")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
