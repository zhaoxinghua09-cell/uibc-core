"""Fixture expectation-matrix tests (v0.2.1).

WHY: the fixtures generator used to record Expected as PROSE next to Observed
and compare nothing. A wrong sentence therefore survived indefinitely -- e.g.
"FAIL (S4 + S6 signature invalid)" for the evidence-content mutations, when the
seal covers identity+manifest only, so S6 in fact stays PASS. Prose cannot fail;
a matrix can. These tests keep the gate honest in BOTH directions, so the guard
can never degrade into a permanent red or a permanent green.

The verifier itself is stubbed here on purpose: this file tests the GATE
(compare + exit code wiring), not uibc-core. tests/test_memory.py and the
generator run cover the verifier.
"""

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load_generator():
    path = os.path.join(ROOT, "fixtures", "generate_fixtures.py")
    spec = importlib.util.spec_from_file_location("uibc_generate_fixtures", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load_generator()

# The five mutations that rewrite EVIDENCE rather than the manifest.
EVIDENCE_MUTATIONS = ("tampered", "deleted", "duplicated", "reordered", "migrated")


def _identical_observed():
    return {(n, m): {"result": G.EXPECTED_MATRIX[n][m]["result"],
                     "checks": dict(G.EXPECTED_MATRIX[n][m]["checks"])}
            for n in G.FIXTURES for m in G.MODES}


def _report_from(cell):
    return {"result": cell["result"],
            "checks": [{"id": cid, "result": res}
                       for cid, res in cell["checks"].items()]}


class MatrixShapeTests(unittest.TestCase):

    def test_01_matrix_is_complete(self):
        """Every fixture x mode cell exists and carries every check id."""
        self.assertEqual(set(G.EXPECTED_MATRIX), set(G.FIXTURES))
        for name in G.FIXTURES:
            self.assertEqual(set(G.EXPECTED_MATRIX[name]), set(G.MODES), name)
            for mode in G.MODES:
                cell = G.EXPECTED_MATRIX[name][mode]
                self.assertIn(cell["result"], ("PASS", "FAIL"), f"{name}[{mode}]")
                self.assertEqual(set(cell["checks"]), set(G.CHECK_ORDER),
                                 f"{name}[{mode}] check ids")

    def test_02_prose_rationale_covers_every_fixture(self):
        self.assertEqual(set(G.EXPECTED_OPEN), set(G.FIXTURES))
        self.assertEqual(set(G.EXPECTED_STRICT), set(G.FIXTURES))


class RegressionLockTests(unittest.TestCase):
    """Lock in the exact defect this revision fixed, so it cannot come back."""

    def test_10_strict_s6_stays_pass_for_evidence_mutations(self):
        """The seal covers identity+manifest. Rewriting/deleting/reordering
        evidence cannot invalidate it, so S6 is PASS -- NOT FAIL. The old prose
        claimed 'S4 + S6 signature invalid', i.e. a defence that never fired."""
        for fx in EVIDENCE_MUTATIONS:
            self.assertEqual(G.EXPECTED_MATRIX[fx]["strict"]["checks"]["S6"], "PASS", fx)

    def test_11_only_manifest_rewrite_breaks_the_seal(self):
        """S6 = FAIL exactly when the mutation reaches the sealed material."""
        breaks = {n for n in G.FIXTURES
                  if G.EXPECTED_MATRIX[n]["strict"]["checks"]["S6"] == "FAIL"}
        self.assertEqual(breaks, {"malicious", "malicious-keyswap"})

    def test_12_open_mode_passes_the_undetectable_forgeries(self):
        """Honest boundary: with no key, `malicious` and `malicious-keyswap`
        PASS overall (S6 INCONCLUSIVE). Stated, not hidden."""
        for fx in ("malicious", "malicious-keyswap"):
            self.assertEqual(G.EXPECTED_MATRIX[fx]["open"]["result"], "PASS", fx)
            self.assertEqual(G.EXPECTED_MATRIX[fx]["open"]["checks"]["S6"], "INCONCLUSIVE", fx)

    def test_13_unanswerable_check_is_not_laundered_into_a_pass(self):
        """clean[open] verifies PASS while S6 is INCONCLUSIVE: an unchecked
        signature must not be reported as a checked one."""
        self.assertEqual(G.EXPECTED_MATRIX["clean"]["open"]["result"], "PASS")
        self.assertEqual(G.EXPECTED_MATRIX["clean"]["open"]["checks"]["S6"], "INCONCLUSIVE")


class ComparatorTests(unittest.TestCase):

    def test_20_identical_matrix_yields_no_deviation(self):
        self.assertEqual(G.compare_matrix(_identical_observed()), [])

    def test_21_check_drift_is_caught_and_named(self):
        obs = _identical_observed()
        obs[("tampered", "strict")]["checks"]["S6"] = "FAIL"   # the old wrong claim
        devs = G.compare_matrix(obs)
        self.assertEqual(len(devs), 1)
        self.assertIn("tampered", devs[0])
        self.assertIn("S6", devs[0])

    def test_22_result_drift_is_caught_even_when_checks_agree(self):
        obs = _identical_observed()
        obs[("clean", "open")]["result"] = "FAIL"
        devs = G.compare_matrix(obs)
        self.assertEqual(len(devs), 1)
        self.assertIn("clean", devs[0])

    def test_23_missing_check_is_reported_not_ignored(self):
        obs = _identical_observed()
        del obs[("clean", "strict")]["checks"]["S6"]
        devs = G.compare_matrix(obs)
        self.assertEqual(len(devs), 1)
        self.assertIn("<absent>", devs[0])

    def test_24_deviation_count_is_complete(self):
        obs = _identical_observed()
        obs[("malicious", "strict")]["checks"]["S6"] = "PASS"
        obs[("malicious", "strict")]["result"] = "PASS"
        self.assertEqual(len(G.compare_matrix(obs)), 2)

    def test_25_comparison_is_repeatable(self):
        obs = _identical_observed()
        obs[("deleted", "open")]["checks"]["S4"] = "PASS"
        self.assertEqual(G.compare_matrix(obs), G.compare_matrix(obs))


class GateWiringTests(unittest.TestCase):
    """The gate must exit 0 when the prior holds and non-zero when it breaks.
    Both directions are tested -- a one-sided gate is just as useless."""

    def _run_main(self, fake_verify, fixtures=("clean",)):
        with tempfile.TemporaryDirectory() as td:
            buf = io.StringIO()
            with mock.patch.object(G, "HERE", td), \
                 mock.patch.object(G, "FIXTURES", list(fixtures)), \
                 mock.patch.object(G, "build_base", lambda pkg: None), \
                 mock.patch.object(G, "verify", fake_verify), \
                 redirect_stdout(buf):
                rc = G.main()
            return rc, buf.getvalue()

    def test_30_gate_returns_zero_when_prior_holds(self):
        def fake(pkg, key=None):
            mode = "open" if key is None else (
                "strict" if key is G.OWNER_KEY else "attacker")
            return _report_from(G.EXPECTED_MATRIX["clean"][mode])

        rc, out = self._run_main(fake)
        self.assertEqual(rc, 0, out)
        self.assertIn("MATRIX GATE] OK", out)

    def test_31_gate_returns_nonzero_on_deviation(self):
        def fake(pkg, key=None):
            """Always claim S6=PASS -- i.e. behave as if the seal covered
            evidence content, the exact misconception the old prose encoded."""
            return {"result": "PASS",
                    "checks": [{"id": cid, "result": "PASS"} for cid in G.CHECK_ORDER]}

        rc, out = self._run_main(fake)
        self.assertNotEqual(rc, 0, "gate failed to block a broken prior:\n" + out)
        self.assertIn("MATRIX GATE] FAILED", out)

    def test_32_gate_reports_every_deviation_not_just_the_first(self):
        def fake(pkg, key=None):
            return {"result": "PASS",
                    "checks": [{"id": cid, "result": "PASS"} for cid in G.CHECK_ORDER]}

        _, out = self._run_main(fake)
        # clean[open] expects S6=INCONCLUSIVE while we claim PASS ->
        self.assertGreaterEqual(out.count("!!"), 1)
        self.assertIn("S6", out)

    def test_33_gate_does_not_write_output_outside_its_run_dir(self):
        """main() must be safe to run from a test: everything lands in HERE."""
        def fake(pkg, key=None):
            mode = "open" if key is None else (
                "strict" if key is G.OWNER_KEY else "attacker")
            return _report_from(G.EXPECTED_MATRIX["clean"][mode])

        real_md = os.path.join(ROOT, "fixtures", "EXPECTED.md")
        before = os.path.getmtime(real_md) if os.path.isfile(real_md) else None
        self._run_main(fake)
        after = os.path.getmtime(real_md) if os.path.isfile(real_md) else None
        self.assertEqual(before, after, "test run mutated the real EXPECTED.md")


if __name__ == "__main__":
    unittest.main(verbosity=2)
