"""The agent id is an identifier before it is a string.

Measured 2026-11-24 (harness s07, G3): `uibc register` accepted the empty
string, a C0 control character and a right-to-left override as agent ids, and
each of them was then written into identity.json, manifest.json and the first
lifecycle event. Two of the three render as a *different* string, which is the
one thing an identifier must not do.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from uibc_core import cli


class PolicyTests(unittest.TestCase):
    def test_a_plain_id_is_accepted(self):
        for good in ("agent-1", "a", "A_9", "x" * cli.MAX_AGENT_ID_LENGTH, "\u6d4b\u8bd5-01"):
            with self.subTest(good=good):
                self.assertIsNone(cli.agent_id_error(good))

    def test_the_empty_string_is_refused(self):
        self.assertIn("empty", cli.agent_id_error(""))

    def test_control_characters_are_refused(self):
        for bad in ("a\x00", "a\nb", "a\tb", "a\x1bb", "a\x7fb", "a\x85b"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(cli.agent_id_error(bad))

    def test_bidi_controls_are_refused(self):
        # U+202E makes the rest of the string render backwards; U+200E is an
        # invisible direction mark; U+FEFF is a zero-width no-break space.
        for bad in ("abc\u202e\"evil", "a\u200eb", "\ufeffagent", "a\u2066b\u2069"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(cli.agent_id_error(bad))

    def test_overlong_ids_are_refused(self):
        self.assertIsNotNone(cli.agent_id_error("x" * (cli.MAX_AGENT_ID_LENGTH + 1)))

    def test_padding_spaces_are_refused(self):
        for bad in (" agent", "agent ", "two  spaces"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(cli.agent_id_error(bad))

    def test_a_non_string_is_refused(self):
        self.assertIsNotNone(cli.agent_id_error(None))
        self.assertIsNotNone(cli.agent_id_error(123))


class RegisterRefusalTests(unittest.TestCase):
    """The refusal has to happen at the command, not only in a helper."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uibc-agentid-")
        self.pkg = os.path.join(self.tmp, "pkg.uibc")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, agent_id):
        root = os.path.dirname(os.path.dirname(os.path.abspath(cli.__file__)))
        env = dict(os.environ)
        env["PYTHONPATH"] = root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        init = subprocess.run(
            [sys.executable, "-m", "uibc_core.cli", "init", self.pkg],
            capture_output=True, text=True, encoding="utf-8", env=env)
        register = subprocess.run(
            [sys.executable, "-m", "uibc_core.cli", "register", self.pkg,
             "--agent-id", agent_id, "--owner", "tester"],
            capture_output=True, text=True, encoding="utf-8", env=env)
        return init, register

    def test_an_unusable_id_writes_nothing(self):
        init, run = self._run("abc\u202e")
        self.assertEqual(init.returncode, 0, init.stderr)
        self.assertNotEqual(run.returncode, 0, run.stdout)
        self.assertIn("bidi", (run.stderr + run.stdout).lower())
        # `init` leaves a skeleton with a TODO note; a refused register must not
        # have replaced it with an identity carrying the rejected name.
        path = os.path.join(self.pkg, "identity.json")
        written = json.load(open(path, encoding="utf-8"))
        self.assertNotEqual(written.get("agent_id"), "abc\u202e",
                            "a refused id must not reach identity.json")
        self.assertIn("TODO", json.dumps(written, ensure_ascii=False))

    def test_a_usable_id_still_registers(self):
        init, run = self._run("agent-ok")
        self.assertEqual(init.returncode, 0, init.stderr)
        self.assertEqual(run.returncode, 0, run.stderr)
        ident = json.load(open(os.path.join(self.pkg, "identity.json"), encoding="utf-8"))
        self.assertEqual(ident["agent_id"], "agent-ok")


if __name__ == "__main__":
    unittest.main()
