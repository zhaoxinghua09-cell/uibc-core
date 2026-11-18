"""LangChain callback handler: a real agent run records itself.

This is the load-bearing adapter. The other hooks in this directory are
*shape-compatible* -- they take an object that looks like a tool. This file
is different: it is a genuine ``BaseCallbackHandler`` subclass, so LangChain
itself pushes every tool call into the recorder. Nothing is wrapped, nothing
is intercepted; the framework calls us because we asked to be called.

That is the whole difference between "compatible shape" and "exercised inside
the framework", and it is the difference this repository is unwilling to blur.

Requires ``langchain-core``. Without it the module still imports (so CI on a
bare interpreter does not fail on an ImportError it cannot act on), but
constructing the handler raises, with the install line in the message. A
silent no-op handler would be worse than an error: it would record nothing and
report success.
"""

from __future__ import annotations

try:  # pragma: no cover - exercised by tests/test_langchain_live.py
    from langchain_core.callbacks import BaseCallbackHandler
    HAVE_LANGCHAIN = True
except Exception:  # pragma: no cover
    BaseCallbackHandler = object  # type: ignore
    HAVE_LANGCHAIN = False

from .uibc_framework_hooks import CallRecorder


def _json_safe(value):
    """Callbacks receive objects, not JSON. Never let serialisation decide
    whether evidence gets written."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    # LangChain wraps tool results in message objects.
    for attr in ("content", "text"):
        got = getattr(value, attr, None)
        if isinstance(got, (str, int, float, bool)):
            return got
    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump())
        except Exception:
            pass
    return repr(value)[:2000]


def _tool_name(serialized, kwargs):
    """LangChain passes a dict for tool runs, and a Runnable for some versions
    of the chain callback. Try the known shapes, then fall back."""
    name = None
    if isinstance(serialized, dict):
        name = serialized.get("name") or serialized.get("id")
    if name is None:
        name = getattr(serialized, "name", None)
    if name is None:
        name = kwargs.get("name")
    return str(name or "tool")


class UibcCallbackHandler(BaseCallbackHandler):
    """Records each tool call as one evidence entry in a UIBC package.

    ``on_tool_start`` / ``on_tool_end`` are called by LangChain around every
    tool invocation; the pair is correlated by ``run_id``, which is also
    written into the evidence so a call that started but never ended is
    visibly unfinished rather than silently absent.
    """

    def __init__(self, package, action_type="ACTION", raise_on_record_error=True):
        if not HAVE_LANGCHAIN:
            raise RuntimeError(
                "langchain-core is not installed. "
                "Install it (pip install langchain-core) or use "
                "adapters.frameworks.uibc_framework_hooks.wrap_callable, "
                "which needs no framework."
            )
        try:
            super().__init__()
        except TypeError:  # pragma: no cover - defensive
            pass
        self.recorder = CallRecorder(package, action_type=action_type)
        self._pending = {}
        self._raise = raise_on_record_error

    # -- tool lifecycle ---------------------------------------------------

    def on_tool_start(self, serialized=None, input_str=None, *,
                      run_id=None, parent_run_id=None, tags=None,
                      metadata=None, inputs=None, **kwargs):
        args = inputs
        if args is None:
            args = {"input": input_str} if input_str is not None else {}
        self._pending[str(run_id)] = {
            "tool": _tool_name(serialized, kwargs),
            "args": _json_safe(args),
        }

    def on_tool_end(self, output=None, *, run_id=None, **kwargs):
        entry = self._pending.pop(str(run_id), None)
        if entry is None:
            # LangChain can emit end without a matching start when a tool is
            # invoked directly rather than through an agent.
            return
        self._record(entry["tool"], entry["args"], output, "OK", None)

    def on_tool_error(self, error=None, *, run_id=None, **kwargs):
        entry = self._pending.pop(str(run_id), None)
        if entry is None:
            return
        self._record(entry["tool"], entry["args"], None, "ERROR",
                     "%s: %s" % (type(error).__name__, error))

    # -- internals --------------------------------------------------------

    def _record(self, tool, args, result, status, error):
        try:
            self.recorder.record(tool, args, _json_safe(result),
                                 status=status, error=error)
        except Exception:
            if self._raise:
                raise
