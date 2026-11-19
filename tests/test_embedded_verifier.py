"""The package may carry the verifier that judges it - and its hash is bound.

Parity with draft-stone-aivs-01, which ships `verify.py` inside the bundle so a
bundle can be checked with nothing but Python. Before this, checking a package
required cloning this repository: a repository skill, not an artefact.

The risk this test guards: an embedded verifier that always answers PASS would
make every package carrying it look verified. So `submit --embed-verifier`
records path + sha256 in the manifest, and check S1 fails on a mismatch.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from uibc_core.verify import verify

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(_REPO, "fixtures", "clean.uibc")
_BUILT = []


def _standalone():
    """Build the single-file verifier the way a reader would, into a temp dir.

    Not read from build/: that is a generated artefact, and committing it would
    let it drift from its generator without anything noticing.
    """
    if _BUILT:
        return _BUILT[0]
    out = os.path.join(tempfile.mkdtemp(), "uibc_verify.py")
    sub = subprocess.run(
        [sys.executable, os.path.join(_REPO, "tools", "build_standalone_verifier.py"),
         "--out", out],
        capture_output=True, text=True, timeout=120)
    assert sub.returncode == 0, sub.stderr[-400:]
    _BUILT.append(out)
    return out


def _copy_base():
    tmp = tempfile.mkdtemp()
    pkg = os.path.join(tmp, "pkg")
    shutil.copytree(BASE, pkg)
    return tmp, pkg


def _embed(pkg, source):
    """Do what `uibc submit --embed-verifier` does, without the CLI's I/O."""
    import hashlib
    os.makedirs(os.path.join(pkg, "verify"), exist_ok=True)
    dst = os.path.join(pkg, "verify", "uibc_verify.py")
    shutil.copyfile(source, dst)
    with open(dst, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    path = os.path.join(pkg, "manifest.json")
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["embedded_verifier"] = {
        "path": "verify/uibc_verify.py",
        "sha256": digest,
        "built_by_verifier_version": "test",
        "note": "outside the evidence root; hash-bound by check S1",
    }
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    return dst


class TestEmbeddedVerifier(unittest.TestCase):
    def test_declared_embedded_verifier_passes_structure(self):
        tmp, pkg = _copy_base()
        self.addCleanup(shutil.rmtree, tmp, True)
        _embed(pkg, _standalone())
        report = verify(pkg)
        s1 = [c for c in report["checks"] if c["id"] == "S1"][0]
        self.assertEqual(s1["result"], "PASS", s1["detail"])
        # and it is not reported as an uncovered extra either
        self.assertNotIn("not covered by the evidence root", s1["detail"])

    def test_a_swapped_embedded_verifier_fails(self):
        tmp, pkg = _copy_base()
        self.addCleanup(shutil.rmtree, tmp, True)
        dst = _embed(pkg, _standalone())
        with open(dst, "a", encoding="utf-8") as f:
            f.write("\n# tampered: always PASS\n")
        report = verify(pkg)
        s1 = [c for c in report["checks"] if c["id"] == "S1"][0]
        self.assertEqual(s1["result"], "FAIL")
        self.assertIn("embedded verifier hash mismatch", s1["detail"])
        self.assertEqual(report["result"], "FAIL")

    def test_the_embedded_script_is_runnable_and_reports_honestly(self):
        """fixtures/clean.uibc is unsigned, so INCONCLUSIVE is the correct verdict.

        Asserting PASS here would bake in the wrong expectation: an unsigned
        package's chain is internally consistent but its provenance is unattested
        (S6). The point of this test is that the embedded script runs with no
        repository and no installed package, and that its exit code matches its
        verdict.
        """
        tmp, pkg = _copy_base()
        self.addCleanup(shutil.rmtree, tmp, True)
        dst = _embed(pkg, _standalone())
        proc = subprocess.run([sys.executable, dst, pkg],
                              capture_output=True, text=True, timeout=120)
        self.assertNotIn("No module named", proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["result"], "INCONCLUSIVE", proc.stdout[-500:])
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(out["checks"])
        # its vocabulary is deliberately different from S1-S18
        self.assertEqual(out["check_vocabulary"], "V1-V9")


if __name__ == "__main__":
    unittest.main()
