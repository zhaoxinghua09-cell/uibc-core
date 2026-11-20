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


if __name__ == "__main__":
    unittest.main()
