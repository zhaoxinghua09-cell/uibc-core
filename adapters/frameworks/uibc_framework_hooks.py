"""Framework hooks: record tool calls from an agent framework as evidence.

Zero dependencies, no framework imports. The wrappers below are
*shape-compatible* with the objects those frameworks pass around; they do
not claim to have been exercised inside a real framework stack.

Why duck-typing instead of an import: a hard dependency on LangChain or
the OpenAI Agents SDK would make this file unimportable in the environments
where it matters most (CI, air-gapped boxes, a reviewer's laptop). What
these wrappers need from those frameworks is a name, a description, and a
callable — all three are conventions, not classes.

What this records, and what it does not:

  - it records that a call happened, what was passed, what came back, and
    whether it raised;
  - it does NOT record the truth of the arguments or the result. A recorder
    cannot make a claim true; it can only make it citable later.

Usage:

    from adapters.frameworks.uibc_framework_hooks import CallRecorder

    rec = CallRecorder("agent.uibc")
    tool = rec.wrap_callable(search_web, name="search_web",
                             description="Search the web")
    tool.run({"query": "aer-1"})          # call is recorded, result returned
    rec.seal()                            # refresh the Evidence Root
"""

import json
import os
import tempfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

import sys
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core import runtime  # noqa: E402
from uibc_core import cli as ucli  # noqa: E402


class _Args(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


def init_package(path, agent_id="agent", owner="owner",
                 agent_type="assistant", version="0.1.0"):
    """Create a package skeleton and register it. Convenience for demos."""
    ucli.cmd_init(_Args(path=path))
    ucli.cmd_register(_Args(path=path, agent_id=agent_id, owner=owner,
                            agent_type=agent_type, version=version))
    return path


class CallRecorder(object):
    """Records each tool call as one evidence entry in a UIBC package."""

    def __init__(self, package, action_type="ACTION"):
        self.package = package
        self.action_type = action_type
        self.count = 0

    def record(self, tool, arguments, result, status="OK", error=None):
        """Write the call as JSON evidence. Returns the recorded path."""
        self.count += 1
        facts = {
            "tool": tool,
            "arguments": arguments,
            "result": result,
            "status": status,
        }
        if error is not None:
            facts["error"] = str(error)
        handle = tempfile.mkdtemp(prefix="uibc-call-")
        path = os.path.join(handle, "call-%04d.json" % self.count)
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(facts, stream, ensure_ascii=False, sort_keys=True, indent=1)
        runtime.record_action(self.package, path, action_type=self.action_type,
                              note="tool call: %s" % tool,
                              media_type="application/json")
        return path

    def seal(self, key_file=None):
        runtime.seal(self.package, key_file)


class _WrappedTool(object):
    """Shape-compatible with a LangChain Tool: name, description, run."""

    def __init__(self, recorder, fn, name, description, on_error="raise"):
        self.recorder = recorder
        self.fn = fn
        self.name = name
        self.description = description
        self.on_error = on_error

    def run(self, tool_input):
        try:
            result = self.fn(tool_input)
        except Exception as exc:  # noqa: BLE001 - recording is the point
            self.recorder.record(self.name, tool_input, None,
                                 status="ERROR", error=exc)
            if self.on_error == "raise":
                raise
            return None
        self.recorder.record(self.name, tool_input, result)
        return result

    def __call__(self, tool_input):
        return self.run(tool_input)

    # LangChain's Tool exposes .invoke and .func; alias them without
    # importing anything.
    invoke = run

    @property
    def func(self):
        return self.run


def wrap_callable(recorder, fn, name, description, on_error="raise"):
    """Wrap any callable into a LangChain-shaped Tool that records calls."""
    return _WrappedTool(recorder, fn, name, description, on_error=on_error)


def function_spec(recorder, fn, name, description, parameters,
                  on_error="raise"):
    """OpenAI-style function tool: a JSON schema descriptor plus an invoke.

    Chat Completions and the Agents SDK both consume `{"type": "function",
    "function": {...}}` descriptors; the descriptor alone cannot be called,
    so the returned dict carries an `invoke` member as well.
    """
    wrapped = wrap_callable(recorder, fn, name, description, on_error=on_error)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
        "invoke": wrapped.run,
    }


def mcp_tool_result(recorder, tool_name, arguments, payload, is_error=False):
    """Record the outcome of one MCP `tools/call` exchange.

    MCP returns `{"content": [...], "isError": bool}`; that envelope is the
    result we record, unmodified.
    """
    status = "ERROR" if is_error else "OK"
    return recorder.record(tool_name, arguments, payload, status=status)
