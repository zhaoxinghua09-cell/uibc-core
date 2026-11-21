"""The decision-vector suite has to be passable by us and unpassable by a stub.

Two negative controls, because a suite without them is decoration:

* a gate that answers `ALLOW` to everything must score 1/7 (only case 01);
* a gate that answers `DENY` to everything must score 3/7 — and, crucially,
  it must be *wrong* on the two HOLD cases. "Cannot verify" is not "not revoked".
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(HERE, "tools")
sys.path.insert(0, TOOLS)

import run_decision_vectors as rv  # noqa: E402


def _run(tmp, stub_body):
    stub = os.path.join(tmp, "stub_gate.py")
    with open(stub, "w", encoding="utf-8", newline="\n") as f:
        f.write(stub_body)
    return subprocess.run([sys.executable, os.path.join(TOOLS, "run_decision_vectors.py"),
                           "--gate", "%s %s {pkg}" % (sys.executable, stub), "--json"],
                          capture_output=True, text=True)


class DecisionVectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="dvec_")
        cls.manifest = rv.load_manifest()

    def test_the_suite_has_both_halves(self):
        cases = self.manifest["cases"]
        self.assertGreaterEqual(len(cases), 6)
        accepts = [c for c in cases if c["expect"]["decision"] == "ALLOW"]
        holds = [c for c in cases if c["expect"]["decision"] == "HOLD"]
        denies = [c for c in cases if c["expect"]["decision"] == "DENY"]
        self.assertEqual(len(accepts), 1, "exactly one case must be accepted")
        self.assertGreaterEqual(len(holds), 2,
                                "HOLD needs coverage: it is the case a lazy gate gets wrong")
        self.assertGreaterEqual(len(denies), 2)

    def test_our_gate_matches_every_case(self):
        proc = subprocess.run([sys.executable,
                               os.path.join(TOOLS, "run_decision_vectors.py"), "--json"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["passed"], out["total"])
        self.assertEqual(out["total"], len(self.manifest["cases"]))

    def test_a_permissive_gate_does_not_pass(self):
        proc = _run(self.tmp, "print('{\"decision\": \"ALLOW\", \"exit_code\": 0}')\n")
        out = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(out["passed"], 1,
                         "answering ALLOW to everything passed more than the baseline")

    def test_a_refuse_everything_gate_does_not_pass(self):
        proc = _run(self.tmp, "print('{\"decision\": \"DENY\", \"exit_code\": 2}')\n")
        out = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(out["passed"], 3,
                         "refusing everything must fail both HOLD cases, not pass the suite")
        red = [r["id"] for r in out["rows"] if not r["ok"]]
        self.assertIn("01", red, "a correct package must not be refused")
        self.assertIn("03", red)
        self.assertIn("05", red)

    def test_external_mode_through_the_cli_scores_seven_of_seven(self):
        # The runner's external path is what a stranger uses. Pointing it at our
        # own CLI caught a defect in the *runner*: one template with both
        # `--revocation` and `--pubkey` could not serve a case that carries only
        # one of them, so two cases scored as errors and the run read 5/7 —
        # which looks exactly like a broken gate. The flags of absent files are
        # now dropped, and this test pins that.
        tmpl = "%s -m uibc_core.cli gate {pkg} --revocation {overlay} --pubkey {anchor}"
        proc = subprocess.run([sys.executable,
                               os.path.join(TOOLS, "run_decision_vectors.py"),
                               "--gate", tmpl % sys.executable, "--json"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["passed"], out["total"])


class SutResultTest(unittest.TestCase):
    """The result file is what a third party consumes, so it has to carry
    enough to be compared without reading our prose, and it has to make
    disagreement visible rather than summarising it away."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="sut_")
        cls.out = os.path.join(cls.tmp, "sut.json")
        proc = subprocess.run([sys.executable,
                               os.path.join(TOOLS, "run_decision_vectors.py"),
                               "--sut-result", cls.out, "--sut-label", "ours", "--json"],
                              capture_output=True, text=True)
        cls.proc = proc
        cls.doc = json.loads(open(cls.out, encoding="utf-8").read())

    def test_the_file_has_the_four_things_a_comparer_needs(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        for key in ("implementation", "corpus", "cases", "summary"):
            self.assertIn(key, self.doc)
        self.assertEqual(self.doc["implementation"], "ours")
        self.assertTrue(self.doc["corpus"]["digest"])
        self.assertEqual(self.doc["summary"]["total"], len(self.doc["cases"]))
        for row in self.doc["cases"]:
            self.assertEqual(set(row), {"id", "what", "expected", "observed",
                                        "verdict", "error"})
            self.assertEqual(set(row["expected"]), {"decision", "exit"})
            self.assertEqual(set(row["observed"]), {"decision", "exit"})

    def test_the_scope_line_travels_with_the_data(self):
        self.assertIn("not an audit", self.doc["scope"])
        self.assertIn("vouches for nobody", self.doc["scope"])

    def test_the_digest_is_the_suite_bytes_and_cannot_drift(self):
        self.assertEqual(self.doc["corpus"]["digest"], rv.corpus_digest(rv.SUITE))
        # A second process must land on the same value: a digest that depends on
        # hash seed, file mtime or walk order is not a digest anyone can agree on.
        proc = subprocess.run([sys.executable, "-c",
                               "import sys;sys.path.insert(0,'tools');"
                               "import run_decision_vectors as rv;"
                               "print(rv.corpus_digest(rv.SUITE))"],
                              capture_output=True, text=True)
        self.assertEqual(proc.stdout.strip(), self.doc["corpus"]["digest"])

    def test_one_byte_of_a_case_moves_the_digest(self):
        import shutil
        copy = os.path.join(self.tmp, "suite_copy")
        shutil.copytree(rv.SUITE, copy)
        victim = None
        for root, _dirs, files in os.walk(copy):
            for name in sorted(files):
                if name == "manifest.json":
                    continue
                victim = os.path.join(root, name)
                break
            if victim:
                break
        self.assertIsNotNone(victim, "no file in the suite to perturb")
        before = rv.corpus_digest(copy)
        with open(victim, "ab") as f:
            f.write(b"\0")
        after = rv.corpus_digest(copy)
        self.assertNotEqual(before, after,
                            "a corpus digest that ignores a changed package is decorative")

    def test_a_disagreeing_gate_is_recorded_case_by_case(self):
        stub = os.path.join(self.tmp, "deny_all.py")
        with open(stub, "w", encoding="utf-8", newline="\n") as f:
            f.write("print('{\"decision\": \"DENY\", \"exit_code\": 2}')\n")
        out = os.path.join(self.tmp, "deny.json")
        proc = subprocess.run([sys.executable,
                               os.path.join(TOOLS, "run_decision_vectors.py"),
                               "--gate", "%s %s {pkg}" % (sys.executable, stub),
                               "--sut-result", out, "--sut-label", "deny-all stub",
                               "--json"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        doc = json.loads(open(out, encoding="utf-8").read())
        red = [c["id"] for c in doc["cases"] if c["verdict"] == "MISMATCH"]
        self.assertEqual(red, ["01", "03", "04", "05"],
                         "the three HOLD cases (03 wrong anchor-less, 04 another key, "
                         "05 somebody else's package) must be the ones a "
                         "refuse-everything gate gets wrong; a file that only carried "
                         "a score would hide which cases and how")
        self.assertEqual(doc["summary"]["matched"], 3)
        self.assertEqual(doc["cases"][3]["observed"],
                         {"decision": "DENY", "exit": 2})


if __name__ == "__main__":
    unittest.main()
