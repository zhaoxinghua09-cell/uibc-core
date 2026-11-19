"""Only generated documents may be resolved by regenerating them.

A tool that "resolves" a conflict by picking one side is a tool that can silently
drop somebody's work. This one is allowed to touch exactly the files a generator
owns; anything else must stop and wait for a human. That limit is the test.
"""

import os
import subprocess
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(REPO, "tools")
for p in (REPO, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import resolve_generated as rg  # noqa: E402


class TestTheAllowList(unittest.TestCase):
    def test_only_known_generated_paths(self):
        allowed = {"docs/EVIDENCE-INDEX.md", "docs/EVIDENCE-DASHBOARD.svg"}
        self.assertEqual(set(rg.GENERATORS), allowed,
                         "a new path was added to the auto-resolve list; "
                         "justify it here or the tool could overwrite hand-written work")

    def test_every_generator_exists(self):
        for path, cmd in rg.GENERATORS.items():
            self.assertTrue(os.path.isfile(os.path.join(REPO, cmd[0]),
                                            ), "generator missing for %s: %s" % (path, cmd[0]))


class TestItRefusesOutsideARebase(unittest.TestCase):
    def test_outside_a_rebase_it_touches_nothing(self):
        before = {}
        for p in rg.GENERATORS:
            full = os.path.join(REPO, p)
            before[p] = os.path.getmtime(full) if os.path.exists(full) else None
        r = subprocess.run([sys.executable, os.path.join("tools", "resolve_generated.py")],
                           cwd=REPO, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("NOT IN A REBASE", r.stdout)
        for p, mtime in before.items():
            full = os.path.join(REPO, p)
            self.assertEqual(os.path.getmtime(full) if os.path.exists(full) else None, mtime,
                             "the tool modified %s outside a rebase" % p)


if __name__ == "__main__":
    unittest.main()
