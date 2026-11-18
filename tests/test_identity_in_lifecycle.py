import json
import os
import shutil
import tempfile
import unittest

from uibc_core.verify import verify

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(_REPO, "fixtures", "clean.uibc")


class TestIdentityIsEverywhereItIsClaimed(unittest.TestCase):
    """Found 2026-11-19: a lifecycle event could name another agent, and the
    package still verified as INCONCLUSIVE with S2 and S3 both PASS. S2 compared
    identity.json with manifest.json and never read the events' own agent_id."""

    def _package_with(self, mutate):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        mutate(pkg)
        return pkg

    def test_an_event_for_another_agent_fails_identity(self):
        def mutate(pkg):
            path = os.path.join(pkg, "lifecycle.json")
            doc = json.load(open(path, encoding="utf-8"))
            doc["events"][0]["agent_id"] = "fx-agent-002"
            json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)

        checks = {c["id"]: c for c in verify(self._package_with(mutate))["checks"]}
        self.assertEqual(checks["S2"]["result"], "FAIL", checks["S2"]["detail"])
        self.assertIn("fx-agent-002", checks["S2"]["detail"])
        # and it must be S2 that fails: a wrong diagnosis is its own defect
        self.assertEqual(checks["S3"]["result"], "PASS", checks["S3"]["detail"])

    def test_the_honest_package_still_passes_identity(self):
        checks = {c["id"]: c for c in verify(BASE)["checks"]}
        self.assertEqual(checks["S2"]["result"], "PASS", checks["S2"]["detail"])


if __name__ == "__main__":
    unittest.main()
