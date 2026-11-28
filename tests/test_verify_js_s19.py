"""Node reader keeps the freshness check (S19), and the state file it writes is
the one the Python reader accepts -- and the other way round.

Why this is a test and not a note: S19 needs an input the reader does not
carry inside the package (a high-water mark), so a reader can "have" S19 and
still never run it. The only evidence that the two readers mean the same
thing by "the head" is that each accepts the file the other wrote.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core.verify import verify as python_verify  # noqa: E402

_JS = os.path.join(_REPO, "tools", "verify-js", "verify.mjs")
_DEMO = os.path.join(_REPO, "examples", "demo.uibc")
NODE = shutil.which("node")


def s19(report):
    rows = [c for c in report["checks"] if c["id"] == "S19"]
    assert len(rows) == 1, rows
    return rows[0]


def js(pkg, state=None):
    cmd = ["node", _JS, pkg] + (["--freshness", state] if state else [])
    out = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(out.stdout)


def copy_with_head(dst, sequence=None, prev_head=None, subject=None):
    shutil.copytree(_DEMO, dst)
    mp = os.path.join(dst, "manifest.json")
    manifest = json.load(open(mp, encoding="utf-8"))
    head = {}
    if sequence is not None:
        head["sequence"] = sequence
    if prev_head is not None:
        head["prev_head"] = prev_head
    if subject is not None:
        head["subject"] = subject
    manifest["freshness_head"] = head
    open(mp, "w", encoding="utf-8").write(json.dumps(manifest, indent=1) + "\n")
    return dst


@unittest.skipUnless(NODE, "node is not installed")
class TestNodeFreshness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uibc-s19-")
        self.state = os.path.join(self.tmp, "state.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_observation_is_inconclusive_not_pass(self):
        row = s19(js(_DEMO, self.state))
        self.assertEqual(row["result"], "INCONCLUSIVE")
        self.assertIn("first observation", row["detail"])
        self.assertTrue(os.path.exists(self.state), "the first observation must be remembered")

    def test_same_package_twice_passes(self):
        self.assertEqual(s19(js(_DEMO, self.state))["result"], "INCONCLUSIVE")
        self.assertEqual(s19(js(_DEMO, self.state))["result"], "PASS")

    def test_the_two_readers_write_identical_state(self):
        js(_DEMO, self.state)
        py_state = os.path.join(self.tmp, "py.json")
        python_verify(_DEMO, state_file=py_state)
        a = json.load(open(self.state, encoding="utf-8"))
        b = json.load(open(py_state, encoding="utf-8"))
        self.assertEqual(a["subjects"], b["subjects"],
                         "the two readers disagree on the head string, so neither "
                         "can accept the other's mark")

    def test_node_accepts_a_state_file_python_wrote(self):
        py_state = os.path.join(self.tmp, "py.json")
        python_verify(_DEMO, state_file=py_state)
        python_verify(_DEMO, state_file=py_state)
        self.assertEqual(s19(js(_DEMO, py_state))["result"], "PASS")

    def test_python_accepts_a_state_file_node_wrote(self):
        js(_DEMO, self.state)
        js(_DEMO, self.state)
        report = python_verify(_DEMO, state_file=self.state)
        self.assertEqual(s19(report)["result"], "PASS")

    def test_a_regressed_sequence_fails(self):
        js(_DEMO, self.state)
        state = json.load(open(self.state, encoding="utf-8"))
        for row in state["subjects"].values():
            row["sequence"] = 9
        json.dump(state, open(self.state, "w", encoding="utf-8"))
        pkg = copy_with_head(os.path.join(self.tmp, "pkg1"), sequence=4)
        row = s19(js(pkg, self.state))
        self.assertEqual(row["result"], "FAIL")
        self.assertIn("regressed", row["detail"])

    def test_two_heads_at_one_sequence_fail_as_fork(self):
        js(_DEMO, self.state)
        state = json.load(open(self.state, encoding="utf-8"))
        for row in state["subjects"].values():
            row["sequence"] = 7
        json.dump(state, open(self.state, "w", encoding="utf-8"))
        pkg = copy_with_head(os.path.join(self.tmp, "pkg2"), sequence=7)
        os.remove(os.path.join(pkg, "evidence", "index.json"))
        row = s19(js(pkg, self.state))
        self.assertEqual(row["result"], "FAIL")
        self.assertIn("fork", row["detail"])

    def test_prev_head_that_does_not_match_the_mark_fails(self):
        js(_DEMO, self.state)
        state = json.load(open(self.state, encoding="utf-8"))
        for row in state["subjects"].values():
            row["sequence"] = 7
        json.dump(state, open(self.state, "w", encoding="utf-8"))
        pkg = copy_with_head(os.path.join(self.tmp, "pkg3"), sequence=8,
                             prev_head="sha256:" + "0" * 64)
        row = s19(js(pkg, self.state))
        self.assertEqual(row["result"], "FAIL")
        self.assertIn("prev_head", row["detail"])

    def test_an_unreadable_state_file_fails_rather_than_guesses(self):
        open(self.state, "w", encoding="utf-8").write("{not json")
        row = s19(js(_DEMO, self.state))
        self.assertEqual(row["result"], "FAIL")
        self.assertIn("unreadable", row["detail"])

    def test_without_the_flag_the_check_does_not_run(self):
        report = js(_DEMO)
        self.assertEqual([c for c in report["checks"] if c["id"] == "S19"], [],
                         "S19 must stay absent when no state file is given, not "
                         "report PASS on an input nobody supplied")


if __name__ == "__main__":
    unittest.main()
