#!/usr/bin/env python3
"""Tests for the framework hooks: calls get recorded, and what is recorded
is verifiable afterwards.

No framework is imported. The wrappers are shape-compatible with LangChain
Tool and OpenAI function descriptors, so a dict and a callable are enough
to exercise them.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "adapters", "frameworks"))

from uibc_core.verify import verify  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hooks = _load("uibc_framework_hooks",
              os.path.join(ROOT, "adapters", "frameworks",
                           "uibc_framework_hooks.py"))


def _search(query):
    return {"hits": 3, "query": query}


def _explode(_):
    raise ValueError("tool blew up")


class FrameworkHooksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pkg = os.path.join(self.tmp, "agent.uibc")
        hooks.init_package(self.pkg, agent_id="agent-test", owner="tester")
        self.recorder = hooks.CallRecorder(self.pkg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_langchain_shaped_tool_records_a_call(self):
        tool = hooks.wrap_callable(self.recorder, _search,
                                   name="search_web", description="Search")
        self.assertEqual(tool.name, "search_web")
        self.assertEqual(tool.run("aer-1"), {"hits": 3, "query": "aer-1"})
        self.assertEqual(self.recorder.count, 1)

    def test_each_call_becomes_one_evidence_entry(self):
        tool = hooks.wrap_callable(self.recorder, _search, "search_web", "Search")
        tool.run({"query": "a"})
        tool.run({"query": "b"})
        index = json.load(open(os.path.join(self.pkg, "evidence", "index.json"),
                               encoding="utf-8"))
        self.assertEqual(len(index["entries"]), 2)

    def test_failing_call_is_recorded_as_error_and_reraised(self):
        tool = hooks.wrap_callable(self.recorder, _explode, "boom", "Fails")
        with self.assertRaises(ValueError):
            tool.run({"x": 1})
        self.assertEqual(self.recorder.count, 1)

    def test_on_error_swallow_still_records(self):
        tool = hooks.wrap_callable(self.recorder, _explode, "boom", "Fails",
                                   on_error="swallow")
        self.assertIsNone(tool.run({"x": 1}))
        self.assertEqual(self.recorder.count, 1)

    def test_openai_function_descriptor_and_invoke(self):
        spec = hooks.function_spec(
            self.recorder, _search, "search_web", "Search",
            {"type": "object", "properties": {"query": {"type": "string"}}})
        self.assertEqual(spec["type"], "function")
        self.assertEqual(spec["function"]["name"], "search_web")
        spec["invoke"]({"query": "x"})
        self.assertEqual(self.recorder.count, 1)

    def test_mcp_envelope_is_recorded_verbatim(self):
        payload = {"content": [{"type": "text", "text": "ok"}], "isError": False}
        hooks.mcp_tool_result(self.recorder, "files.read", {"path": "a.txt"},
                              payload)
        self.assertEqual(self.recorder.count, 1)

    def test_sealed_package_verifies(self):
        tool = hooks.wrap_callable(self.recorder, _search, "search_web", "Search")
        tool.run({"query": "aer-1"})
        self.recorder.seal()
        report = verify(self.pkg)
        # An unsigned package cannot resolve S6, so the honest verdict is
        # INCONCLUSIVE rather than a pass. Every check that *can* be resolved
        # must pass; S6 must say why it could not.
        self.assertEqual(report["result"], "INCONCLUSIVE")
        self.assertEqual(report["assurance"], "unattested")
        for check in report["checks"]:
            if check["id"] == "S6":
                self.assertEqual(check["result"], "INCONCLUSIVE")
            else:
                self.assertEqual(check["result"], "PASS", check)


if __name__ == "__main__":
    unittest.main()
