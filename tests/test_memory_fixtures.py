"""Memory-fixture gate tests (UIBC-MEM v0.1.1).

Two jobs:

1. REGRESSION LOCKS for the real defects the mutation corpus exposed, so they
   can never come back silently:
     - a duplicate memory_id in `target` used to be discarded by dict collapse,
       so an injected fake entry PASSED and the report said "no injections";
     - an empty-to-empty migration used to PASS all four Preservations.
2. GATE TESTS - the expectation matrix must fail in BOTH directions. A gate
   that is always green and a gate that is always red are equally worthless.
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


def _load():
    path = os.path.join(ROOT, "fixtures", "generate_memory_fixtures.py")
    spec = importlib.util.spec_from_file_location("uibc_generate_memory_fixtures", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load()


def _observed_from_prior():
    return {(n, "default"): {"result": M.EXPECTED_MATRIX[n]["default"]["result"],
                             "code": M.EXPECTED_MATRIX[n]["default"]["code"],
                             "checks": dict(M.EXPECTED_MATRIX[n]["default"]["checks"])}
            for n in M.CASE_NAMES}


def _run_one(case):
    source, target = M.CASES[case][0]()
    return M.verify_migration(source, target)


class CorpusShapeTests(unittest.TestCase):

    def test_01_every_case_has_a_prior(self):
        for name in M.CASE_NAMES:
            self.assertIn(name, M.EXPECTED_MATRIX, name)
            cell = M.EXPECTED_MATRIX[name]["default"]
            self.assertIn("result", cell, name)
            self.assertIn("code", cell, name)
            self.assertTrue(cell["checks"], name)

    def test_02_case_descriptions_are_present(self):
        for name in M.CASE_NAMES:
            fn, threat, target = M.CASES[name]
            self.assertTrue(callable(fn), name)
            self.assertTrue(threat and target, name)

    def test_03_corpus_covers_all_six_checks(self):
        """The corpus must exercise M0-M5, or a whole check could rot unseen."""
        seen = set()
        for name in M.CASE_NAMES:
            seen |= set(M.EXPECTED_MATRIX[name]["default"]["checks"])
        self.assertEqual(seen, set(M.CHECK_ORDER), sorted(seen))


class RegressionLockTests(unittest.TestCase):
    """The exact defects v0.1.1 fixed."""

    def test_10_duplicate_target_id_is_rejected_on_both_sides(self):
        """The silent memory-injection path: a fake entry sharing a real
        entry's memory_id, positioned so the dict collapse kept the real one."""
        for case in ("dup-target-fake-last", "dup-target-fake-first", "dup-target-triple"):
            r = _run_one(case)
            self.assertEqual(r["result"], "FAIL", case)
            self.assertEqual(r.get("result_code"), "MALFORMED_INPUT", case)
            self.assertIn("target has duplicate memory_id", r["checks"][0]["detail"], case)

    def test_11_fake_first_no_longer_reports_no_injections(self):
        """v0.1 said 'no injections' while a fake entry sat in the target."""
        r = _run_one("dup-target-fake-first")
        detail = " ".join(c.get("detail", "") for c in r["checks"])
        self.assertNotIn("no injections", detail)
        self.assertNotEqual(r["result"], "PASS")

    def test_12_vacuous_migration_is_not_a_pass(self):
        r = _run_one("vacuous-empty")
        self.assertNotEqual(r["result"], "PASS")
        self.assertEqual(r["result"], "INCONCLUSIVE")
        self.assertEqual(r.get("result_code"), "VACUOUS_INPUT")
        self.assertEqual(r["checks"][0]["result"], "INCONCLUSIVE")

    def test_13_empty_source_with_content_still_fails(self):
        """Only BOTH-empty is vacuous; an injection-only migration is a plain
        failure, not an 'inconclusive'."""
        r = _run_one("empty-source-only")
        self.assertEqual(r["result"], "FAIL")
        self.assertEqual(r.get("result_code"), "OK")
        self.assertEqual(r["checks"][0]["id"], "M1")

    def test_17_every_report_carries_the_verifier_version(self):
        """The rubric requires a score to cite which verify produced it, so the
        version must be in the report - not only in the source tree."""
        for case in ("faithful-identical", "dup-source", "vacuous-empty"):
            r = _run_one(case)
            self.assertEqual(r.get("verifier_version"), M.MEM_VERIFIER_VERSION, case)
        self.assertTrue(M.MEM_VERIFIER_VERSION)

    def test_14_empty_field_is_reported_as_empty_not_missing(self):
        r = _run_one("malformed-empty-field")
        self.assertEqual(r.get("result_code"), "MALFORMED_INPUT")
        self.assertIn("is empty", r["checks"][0]["detail"])
        self.assertNotIn("missing field", r["checks"][0]["detail"])

    def test_15_paraphrase_fails_because_equality_is_exact_text(self):
        """Guards against anyone 'improving' this into semantic comparison,
        which the scope statement explicitly disclaims."""
        r = _run_one("paraphrase-drift")
        self.assertEqual(r["result"], "FAIL")
        ids = {c["id"]: c["result"] for c in r["checks"]}
        self.assertEqual(ids["M2"], "FAIL")
        self.assertIn("semantic drift", r["scope"])

    def test_16_extra_field_boundary_is_recorded_and_passes(self):
        """Documented boundary, not an oversight: undeclared fields are outside
        the four Preservations, so this PASSes by scope."""
        self.assertEqual(_run_one("extra-field-undeclared")["result"], "PASS")


class ComparatorTests(unittest.TestCase):

    def test_20_identical_prior_yields_no_deviation(self):
        self.assertEqual(M.compare_memory(_observed_from_prior()), [])

    def test_21_result_drift_is_caught(self):
        obs = _observed_from_prior()
        obs[("dup-target-fake-first", "default")]["result"] = "PASS"
        devs = M.compare_memory(obs)
        self.assertEqual(len(devs), 1)
        self.assertIn("dup-target-fake-first", devs[0])

    def test_22_code_drift_is_caught(self):
        """result_code is pinned too - a verdict can be right while the reason
        code silently changes."""
        obs = _observed_from_prior()
        obs[("vacuous-empty", "default")]["code"] = "-"
        devs = M.compare_memory(obs)
        self.assertEqual(len(devs), 1)
        self.assertIn("code", devs[0])

    def test_23_check_drift_is_caught(self):
        obs = _observed_from_prior()
        obs[("fact-drift", "default")]["checks"]["M3"] = "FAIL"
        devs = M.compare_memory(obs)
        self.assertEqual(len(devs), 1)
        self.assertIn("M3", devs[0])

    def test_24_extra_check_in_observation_is_caught(self):
        """If memory.py grows a check, the corpus must acknowledge it."""
        obs = _observed_from_prior()
        obs[("faithful-identical", "default")]["checks"]["M9"] = "PASS"
        devs = M.compare_memory(obs)
        self.assertEqual(len(devs), 1)
        self.assertIn("unexpected extra checks", devs[0])

    def test_25_missing_check_is_caught(self):
        obs = _observed_from_prior()
        del obs[("fact-drift", "default")]["checks"]["M2"]
        devs = M.compare_memory(obs)
        self.assertEqual(len(devs), 1)
        self.assertIn("<absent>", devs[0])


class GateWiringTests(unittest.TestCase):

    def _run_main(self, fake_verify, cases=("faithful-identical",)):
        with tempfile.TemporaryDirectory() as td:
            fake_cases = {c: M.CASES[c] for c in cases}
            buf = io.StringIO()
            with mock.patch.object(M, "HERE", td), \
                 mock.patch.object(M, "CASE_NAMES", list(cases)), \
                 mock.patch.object(M, "CASES", fake_cases), \
                 mock.patch.object(M, "verify_migration", fake_verify), \
                 redirect_stdout(buf):
                rc = M.main()
            return rc, buf.getvalue()

    def _stub_returning(self, case):
        """A verifier stub that returns exactly what the prior predicts."""
        def fake(source, target):
            cell = M.EXPECTED_MATRIX[case]["default"]
            return {"result": cell["result"], "result_code": cell["code"],
                    "checks": [{"id": cid, "result": res}
                               for cid, res in cell["checks"].items()]}
        return fake

    def test_30_gate_returns_zero_when_prior_holds(self):
        rc, out = self._run_main(self._stub_returning("faithful-identical"))
        self.assertEqual(rc, 0, out)
        self.assertIn("MATRIX GATE] OK", out)

    def test_31_gate_returns_nonzero_on_deviation(self):
        def fake(source, target):
            """Claim a clean pass for everything - i.e. behave like v0.1, which
            let the injected duplicate and the vacuous migration through."""
            return {"result": "PASS",
                    "checks": [{"id": cid, "result": "PASS"}
                               for cid in ("M1", "M2", "M3", "M4", "M5")]}

        rc, out = self._run_main(fake, cases=("dup-target-fake-first",))
        self.assertNotEqual(rc, 0, "gate failed to block a broken prior:\n" + out)
        self.assertIn("MATRIX GATE] FAILED", out)
        self.assertIn("dup-target-fake-first", out)

    def test_32_gate_does_not_touch_the_real_report(self):
        real = os.path.join(ROOT, "fixtures", "MEMORY_EXPECTED.md")
        before = os.path.getmtime(real) if os.path.isfile(real) else None
        self._run_main(self._stub_returning("faithful-identical"))
        after = os.path.getmtime(real) if os.path.isfile(real) else None
        self.assertEqual(before, after, "test run mutated the real report")


if __name__ == "__main__":
    unittest.main(verbosity=2)
