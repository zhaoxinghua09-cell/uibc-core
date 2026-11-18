"""The auditor's own trust root, tested by trying to hijack it.

A verdict is only worth what the code that produced it. If an outsider runs
our one command with a `uibc_core` on PYTHONPATH that answers PASS to
everything, the verdict must still come from this repo -- or the tool must
refuse to run rather than report someone else's opinion.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "outsider_audit.py")

FAKE_VERIFY = '''
# A verifier that agrees with everyone. If this one is ever imported, every
# attack below will be reported as passing.
def verify(package_dir):
    return {"result": "PASS", "checks": [], "package": package_dir,
            "sealed": True, "signature": "trust me"}
'''


def _evil(root):
    pkg = os.path.join(root, "uibc_core")
    os.makedirs(pkg, exist_ok=True)
    with open(os.path.join(pkg, "__init__.py"), "w", encoding="utf-8") as f:
        f.write("__version__ = 'evil'\n")
    with open(os.path.join(pkg, "verify.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_VERIFY)
    return root


class AuditorTrustTests(unittest.TestCase):
    def test_pythonpath_cannot_supply_the_verifier(self):
        """The repo's own verifier wins even when PYTHONPATH offers a liar."""
        with tempfile.TemporaryDirectory() as tmp:
            evil = _evil(tmp)
            env = dict(os.environ, PYTHONPATH=evil)
            proc = subprocess.run([sys.executable, TOOL, "--json"],
                                  cwd=REPO, env=env, capture_output=True,
                                  text=True, timeout=180)
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            out = json.loads(proc.stdout)
            self.assertTrue(out["trust"]["in_repo"],
                            "judged with %s" % out["trust"])
            self.assertNotIn("evil", out["trust"]["path"])
            # and the verdict is a real one, not the fake PASS
            self.assertEqual(out["stage_baseline"]["got"]["result"],
                             "INCONCLUSIVE")

    def test_norm_normalizes_platform_separators(self):
        """A repo-internal path must match the repo prefix on Windows too.

        Earlier `_norm` only collapsed doubled backslashes, so a single-separator
        Windows path never matched the forward-slash repo prefix and the trust
        root refused to run code that was actually inside the repo.
        """
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import outsider_audit as oa
        inside = oa._norm(os.path.join(REPO, "uibc_core", "verify.py"))
        root = oa._norm(REPO)
        self.assertNotIn("\\", inside)
        self.assertTrue(inside.startswith(root + "/"), "%s not under %s" % (inside, root))

    def test_a_borrowed_auditor_refuses_to_run(self):
        """Tool plus a same-directory liar: a path check would be satisfied,
        so the behaviour self-test has to be what stops it."""
        with tempfile.TemporaryDirectory() as tmp:
            tools = os.path.join(tmp, "tools")
            os.makedirs(tools)
            shutil.copy(TOOL, os.path.join(tools, "outsider_audit.py"))
            evil = _evil(tmp)
            env = dict(os.environ, PYTHONPATH=evil)
            proc = subprocess.run(
                [sys.executable, os.path.join(tools, "outsider_audit.py")],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=180)
            self.assertEqual(proc.returncode, 2, proc.stdout[-2000:])
            self.assertIn("refusing to run", proc.stderr)
            self.assertIn("self-test", proc.stderr)


if __name__ == "__main__":
    unittest.main()
