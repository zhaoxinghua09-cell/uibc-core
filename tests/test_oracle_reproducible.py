"""The published corpus has to be rebuildable, byte for byte.

Not "consistent": any verifier can be run against the committed files. This
rebuilds them from the tool and compares the bytes, which is the only form of
the claim a stranger can check without trusting the committed copy.
"""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_CORPUS = os.path.join(_REPO, "conformance", "oracle")
_EPOCH = "1794700800"
# Written by a different tool (`tools/check_grounds.py` reads it; it is derived
# from `uibc_core.basis`), so `--emit` is not the thing that produces it.
_NOT_BY_EMIT = {"grounds.json"}

if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


def _tree(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            with open(p, "rb") as f:
                out[rel] = hashlib.sha256(f.read()).hexdigest()
    return out


class TestCorpusReproducible(unittest.TestCase):
    def test_the_committed_corpus_is_rebuilt_from_the_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "corpus")
            env = dict(os.environ)
            env["SOURCE_DATE_EPOCH"] = _EPOCH
            r = subprocess.run([sys.executable, os.path.join("tools", "oracle_check.py"),
                                "--emit", dest],
                               cwd=_REPO, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-400:])
            rebuilt = _tree(dest)
            committed = _tree(_CORPUS)
            for k in _NOT_BY_EMIT:
                committed.pop(k, None)
            missing = sorted(set(committed) - set(rebuilt))
            extra = sorted(set(rebuilt) - set(committed))
            self.assertEqual(missing, [])
            self.assertEqual(extra, [])
            differing = sorted(k for k in committed if committed[k] != rebuilt[k])
            self.assertEqual(differing, [], "rebuilt bytes differ: %s" % differing[:5])

    def test_a_different_epoch_gives_different_bytes(self):
        """The comparison above would pass trivially if the clock were ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "corpus")
            env = dict(os.environ)
            env["SOURCE_DATE_EPOCH"] = "1"  # 1970-01-01T00:00:01Z
            r = subprocess.run([sys.executable, os.path.join("tools", "oracle_check.py"),
                                "--emit", dest],
                               cwd=_REPO, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-400:])
            rebuilt = _tree(dest)
            committed = _tree(_CORPUS)
            for k in _NOT_BY_EMIT:
                committed.pop(k, None)
            differing = [k for k in committed if committed.get(k) != rebuilt.get(k)]
            self.assertGreater(len(differing), 0, "the epoch was ignored")


if __name__ == "__main__":
    unittest.main()
