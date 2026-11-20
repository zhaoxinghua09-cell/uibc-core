"""S19 freshness state: what a verifier may and may not conclude.

These tests pin the three answers that matter, and one that matters most:
a first observation is INCONCLUSIVE. A verifier that reports PASS on its first
look has verified its own memory, not the package.
"""
import json
import os
import tempfile
import unittest

from uibc_core import freshness


def state_with(head, sequence):
    return {"schema": freshness.SCHEMA, "subjects": {"a1": {"head": head, "sequence": sequence}}}


class TestEvaluate(unittest.TestCase):
    def test_first_observation_is_inconclusive_not_pass(self):
        result, detail = freshness.evaluate(freshness.empty(), "a1", "sha256:aa")
        self.assertEqual(result, "INCONCLUSIVE")
        self.assertIn("first observation", detail)

    def test_same_head_same_sequence_passes(self):
        self.assertEqual(freshness.evaluate(state_with("sha256:aa", 1), "a1", "sha256:aa", 1)[0], "PASS")

    def test_older_sequence_fails_as_regression(self):
        result, detail = freshness.evaluate(state_with("sha256:aa", 5), "a1", "sha256:zz", 4)
        self.assertEqual(result, "FAIL")
        self.assertIn("regressed", detail)

    def test_two_heads_at_one_sequence_is_a_fork(self):
        result, detail = freshness.evaluate(state_with("sha256:aa", 5), "a1", "sha256:bb", 5)
        self.assertEqual(result, "FAIL")
        self.assertIn("fork", detail)

    def test_advanced_sequence_with_wrong_prev_head_is_a_skipped_step(self):
        result, detail = freshness.evaluate(state_with("sha256:aa", 5), "a1", "sha256:cc", 7,
                                            prev_head="sha256:unrelated")
        self.assertEqual(result, "FAIL")
        self.assertIn("skipped step", detail)

    def test_advanced_sequence_with_matching_prev_head_passes(self):
        self.assertEqual(
            freshness.evaluate(state_with("sha256:aa", 5), "a1", "sha256:cc", 7,
                               prev_head="sha256:aa")[0], "PASS")

    def test_different_head_without_sequence_cannot_be_placed(self):
        result, detail = freshness.evaluate(state_with("sha256:aa", 5), "a1", "sha256:bb")
        self.assertEqual(result, "INCONCLUSIVE")
        self.assertIn("cannot be placed", detail)

    def test_subject_is_not_global(self):
        state = state_with("sha256:aa", 5)
        self.assertEqual(freshness.evaluate(state, "other", "sha256:aa", 5)[0], "INCONCLUSIVE")


class TestRecord(unittest.TestCase):
    def test_record_is_atomic_and_readable(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "state.json")
        freshness.record(p, "a1", "sha256:aa", sequence=3)
        with open(p, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk["subjects"]["a1"]["sequence"], 3)
        self.assertEqual(on_disk["schema"], freshness.SCHEMA)

    def test_record_overwrites_previous_observation(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "state.json")
        freshness.record(p, "a1", "sha256:aa", sequence=1)
        freshness.record(p, "a1", "sha256:bb", sequence=2)
        with open(p, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk["subjects"]["a1"]["head"], "sha256:bb")

    def test_broken_state_file_is_rejected_not_guessed(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "state.json")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write('["not", "an", "object"]')
        with self.assertRaises(ValueError):
            freshness.load(p)

    def test_second_writer_is_refused_not_silently_merged(self):
        # Two interleaved read-modify-writes lose one observation. The refusal
        # is the point: it says "not recorded" instead of returning a state file
        # that quietly lacks the other writer's observation.
        d = tempfile.mkdtemp()
        p = os.path.join(d, "state.json")
        with open(p + ".lock", "w", encoding="utf-8") as fh:
            fh.write("held")
        with self.assertRaises(freshness.Busy):
            freshness.record(p, "a1", "sha256:aa", sequence=1)
        self.assertFalse(os.path.exists(p), "nothing should be written when the lock is held")
        os.unlink(p + ".lock")
        freshness.record(p, "a1", "sha256:aa", sequence=1)
        self.assertTrue(os.path.exists(p))


class TestStateBytes(unittest.TestCase):
    """The same observation must produce the same bytes on every platform.

    A state file is handed to another verifier, sometimes on another machine. If
    Windows wrote CRLF where Linux writes LF, the two would differ for no reason
    and a byte-for-byte comparison of "the same memory" would report a difference
    that is only a line ending.
    """

    def test_recorded_state_uses_lf_only(self):
        p = os.path.join(tempfile.mkdtemp(), "state.json")
        freshness.record(p, "a1", "sha256:aa", sequence=3, accepted_at="2026-11-20T00:00:00Z")
        raw = open(p, "rb").read()
        self.assertNotIn(b"\r\n", raw, "state file carries CRLF")
        self.assertIn(b"\n", raw, "state file is not line-delimited at all")

    def test_two_identical_observations_are_byte_identical(self):
        d = tempfile.mkdtemp()
        a = os.path.join(d, "a.json")
        b = os.path.join(d, "b.json")
        for p in (a, b):
            freshness.record(p, "a1", "sha256:aa", sequence=3)
        self.assertEqual(open(a, "rb").read(), open(b, "rb").read())


class TestVerifierIntegration(unittest.TestCase):
    """The CLI path: first run bootstraps the watermark, second run compares."""

    def _demo_package(self):
        from uibc_core.cli import main
        import contextlib
        import io
        import sys

        buf = io.StringIO()
        old = sys.argv
        try:
            sys.argv = ["uibc", "demo"]
            with contextlib.redirect_stdout(buf):
                main()
        except SystemExit:
            pass
        finally:
            sys.argv = old
        text = buf.getvalue()
        marker = "verify "
        idx = text.rfind(marker)
        self.assertGreater(idx, 0, "demo did not print a package path: %r" % text[-200:])
        path = text[idx + len(marker):].strip().split(" ")[0]
        return path

    def test_first_run_inconclusive_then_pass(self):
        from uibc_core.verify import verify

        pkg = self._demo_package()
        self.assertTrue(os.path.isdir(pkg), pkg)
        state = os.path.join(tempfile.mkdtemp(), "s.json")

        first = verify(pkg, state_file=state)
        s10 = [c for c in first["checks"] if c["id"] == "S19"]
        self.assertEqual(len(s10), 1)
        self.assertEqual(s10[0]["result"], "INCONCLUSIVE")
        self.assertTrue(os.path.exists(state), "first observation should be remembered")

        second = verify(pkg, state_file=state)
        s10b = [c for c in second["checks"] if c["id"] == "S19"]
        self.assertEqual(s10b[0]["result"], "PASS")

    def test_no_state_file_leaves_verdict_untouched(self):
        from uibc_core.verify import verify

        pkg = self._demo_package()
        with_state_ids = {c["id"] for c in verify(pkg, state_file=os.path.join(tempfile.mkdtemp(), "s.json"))["checks"]}
        without = {c["id"] for c in verify(pkg)["checks"]}
        self.assertIn("S19", with_state_ids)
        self.assertNotIn("S19", without)


if __name__ == "__main__":
    unittest.main()
