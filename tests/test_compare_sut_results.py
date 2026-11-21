"""The comparison engine has to refuse more often than it agrees.

A tool that compares two result files is only worth having if it refuses the
comparisons that cannot support a claim: different corpora, different
expectations, the same label twice. Those refusals are the tests below.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(HERE, "tools")

RUNNER = os.path.join(TOOLS, "run_decision_vectors.py")
COMPARE = os.path.join(TOOLS, "compare_sut_results.py")


def _sut(tmp, name, label, gate=None):
    out = os.path.join(tmp, name)
    cmd = [sys.executable, RUNNER, "--sut-result", out, "--sut-label", label]
    if gate:
        cmd += ["--gate", gate]
    subprocess.run(cmd, capture_output=True, text=True)
    with open(out, encoding="utf-8") as f:
        return out, json.load(f)


def _write(tmp, name, doc):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f)
    return path


def _run(*paths):
    return subprocess.run([sys.executable, COMPARE] + list(paths) + ["--json"],
                          capture_output=True, text=True)


class CompareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="cmp_")
        cls.mine, cls.doc_mine = _sut(cls.tmp, "mine.json", "ours (in-process)")
        cls.cli, cls.doc_cli = _sut(
            cls.tmp, "cli.json", "ours (cli)",
            gate="%s -m uibc_core.cli gate {pkg} --revocation {overlay} --pubkey {anchor}"
                 % sys.executable)

    def test_two_runs_against_the_same_corpus_agree(self):
        proc = _run(self.mine, self.cli)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["implementations"], ["ours (in-process)", "ours (cli)"])
        self.assertEqual(out["diverging"], [])
        self.assertEqual(len(out["agreeing"]), out["cases"])
        self.assertEqual(out["corpus_digest"], self.doc_mine["corpus"]["digest"])
        self.assertIn("not a defect in either side", out["scope"])

    def test_a_divergence_is_reported_by_case_and_never_scored(self):
        stub = os.path.join(self.tmp, "deny.py")
        with open(stub, "w", encoding="utf-8", newline="\n") as f:
            f.write("print('{\"decision\": \"DENY\", \"exit_code\": 2}')\n")
        stub_sut, _ = _sut(self.tmp, "deny.json", "deny-all stub",
                           gate="%s %s {pkg}" % (sys.executable, stub))
        proc = _run(self.mine, stub_sut)
        self.assertEqual(proc.returncode, 1, "a divergence is not an error")
        out = json.loads(proc.stdout)
        self.assertEqual(out["diverging"], ["01", "03", "04", "05"])
        self.assertEqual(out["cases"], 7)
        self.assertEqual(len(out["agreeing"]) + len(out["diverging"]), 7)

    def test_different_corpora_is_a_refusal_not_a_finding(self):
        doc = dict(self.doc_cli)
        doc["corpus"] = dict(doc["corpus"])
        doc["corpus"]["digest"] = "0" * 64
        other = _write(self.tmp, "other_corpus.json", doc)
        proc = _run(self.mine, other)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("NOT COMPARABLE", proc.stderr)
        self.assertIn("different corpus bytes", proc.stderr)

    def test_two_opinions_about_what_was_expected_is_a_corpus_defect(self):
        doc = json.loads(json.dumps(self.doc_cli))
        doc["cases"][0]["expected"] = {"decision": "DENY", "exit": 2}
        doctored = _write(self.tmp, "different_expectation.json", doc)
        proc = _run(self.mine, doctored)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("corpus problem", proc.stderr)

    def test_the_same_label_twice_is_refused(self):
        proc = _run(self.mine, self.mine)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("distinct --sut-label", proc.stderr)

    def test_a_file_that_is_not_a_sut_result_is_refused(self):
        junk = os.path.join(self.tmp, "junk.json")
        with open(junk, "w", encoding="utf-8", newline="\n") as f:
            f.write('{"passed": 7, "total": 7}\n')
        proc = _run(self.mine, junk)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not a sut-result file", proc.stderr)

    def test_one_file_alone_is_refused(self):
        proc = _run(self.mine)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("disagreeing with yourself", proc.stderr)


if __name__ == "__main__":
    unittest.main()
