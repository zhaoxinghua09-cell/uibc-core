"""Exercised inside a real LangChain stack, not against a look-alike.

These tests are skipped when ``langchain-core`` is absent, and that is the
only acceptable skip here: the point of the file is to prove the adapter
works when the framework is actually installed. Run them in a venv with
``pip install langchain-core`` and nothing is skipped.

Verified against langchain-core 1.8.2 on 2026-11-18.
"""

import json
import os
import shutil
import tempfile
import unittest

from adapters.frameworks.langchain_callback import HAVE_LANGCHAIN
from adapters.frameworks.uibc_framework_hooks import init_package

try:
    from langchain_core.tools import tool as lc_tool
except Exception:  # pragma: no cover
    lc_tool = None


def _entries(package):
    with open(os.path.join(package, "evidence", "index.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def _payload(package, entry):
    with open(os.path.join(package, "evidence", entry["path"]), encoding="utf-8") as f:
        return json.load(f)


@unittest.skipUnless(HAVE_LANGCHAIN and lc_tool is not None,
                     "langchain-core not installed")
class TestRealLangChainStack(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uibc-lc-")
        self.pkg = os.path.join(self.tmp, "pkg")
        init_package(self.pkg, agent_id="agent.lc", owner="x.zhao")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _handler(self):
        from adapters.frameworks.langchain_callback import UibcCallbackHandler
        return UibcCallbackHandler(self.pkg)

    def test_a_real_tool_call_lands_in_the_package(self):
        """The framework calls the handler; we never touch the tool."""
        @lc_tool
        def add_two(a: int, b: int) -> int:
            """Add two integers."""
            return a + b

        h = self._handler()
        before = len(_entries(self.pkg))
        self.assertEqual(add_two.invoke({"a": 2, "b": 3},
                                        config={"callbacks": [h]}), 5)

        entries = _entries(self.pkg)
        self.assertEqual(len(entries), before + 1)
        entry = entries[-1]
        self.assertEqual(entry["type"], "ACTION")
        self.assertEqual(entry["note"], "tool call: add_two")

        # The recorded arguments and result are the ones the framework passed
        # and the tool returned -- not a summary we invented afterwards.
        payload = _payload(self.pkg, entry)
        self.assertEqual(payload["arguments"], {"a": 2, "b": 3})
        self.assertEqual(payload["result"], 5)
        self.assertEqual(payload["tool"], "add_two")
        self.assertEqual(payload["status"], "OK")

    def test_two_calls_two_entries_and_hashes_differ(self):
        @lc_tool
        def echo(text: str) -> str:
            """Echo the text."""
            return text

        h = self._handler()
        before = len(_entries(self.pkg))
        echo.invoke({"text": "alpha"}, config={"callbacks": [h]})
        echo.invoke({"text": "beta"}, config={"callbacks": [h]})
        entries = _entries(self.pkg)
        self.assertEqual(len(entries), before + 2)
        self.assertNotEqual(entries[-1]["content_hash"],
                            entries[-2]["content_hash"])

    def test_a_raising_tool_is_recorded_as_error_not_as_absence(self):
        @lc_tool
        def explode(n: int) -> int:
            """Always raises."""
            raise ValueError("boom %d" % n)

        h = self._handler()
        before = len(_entries(self.pkg))
        with self.assertRaises(Exception):
            explode.invoke({"n": 7}, config={"callbacks": [h]})

        entries = _entries(self.pkg)
        self.assertEqual(len(entries), before + 1,
                         "a failed call must still leave evidence")
        payload = _payload(self.pkg, entries[-1])
        self.assertEqual(payload["status"], "ERROR")
        self.assertIn("boom 7", json.dumps(payload))

    def test_recorder_stays_verifiable_after_framework_traffic(self):
        """The package LangChain wrote is a package we can still verify --
        after sealing. Recording moves the root; sealing publishes the new
        one, and S5 is what notices when nobody did."""
        from uibc_core.verify import verify

        @lc_tool
        def noop(x: str) -> str:
            """Do nothing."""
            return x

        h = self._handler()
        noop.invoke({"x": "1"}, config={"callbacks": [h]})
        h.recorder.seal()

        report = verify(self.pkg)
        by_id = {c["id"]: c["result"] for c in report["checks"]}
        self.assertEqual(by_id["S4"], "PASS")
        self.assertEqual(by_id["S5"], "PASS")
        self.assertEqual(by_id["S6"], "INCONCLUSIVE",
                         "an unsigned package must not report PASS at the seal")

    def test_forgetting_to_seal_is_caught_by_S5(self):
        """Record without sealing and the root stops matching the manifest.
        A verifier that let this pass would be decorative."""
        from uibc_core.verify import verify

        @lc_tool
        def noop2(x: str) -> str:
            """Do nothing."""
            return x

        h = self._handler()
        noop2.invoke({"x": "1"}, config={"callbacks": [h]})

        report = verify(self.pkg)
        by_id = {c["id"]: c["result"] for c in report["checks"]}
        self.assertEqual(by_id["S5"], "FAIL")
        self.assertEqual(report["result"], "FAIL")

    def test_handler_without_langchain_fails_loudly(self):
        """A handler that cannot record must not pretend it did."""
        from adapters.frameworks import langchain_callback as lc
        if lc.HAVE_LANGCHAIN:
            self.skipTest("langchain-core is present; covered in a bare env")
        with self.assertRaises(RuntimeError):
            lc.UibcCallbackHandler(self.pkg)


if __name__ == "__main__":
    unittest.main()
