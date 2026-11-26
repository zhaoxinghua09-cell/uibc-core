"""A state write that Windows refused must be retried, and then recorded.

`os.replace` on Windows raises PermissionError when a scanner or indexer holds the
target file open. `LifecycleStore._persist` used to swallow that on the first
attempt, so the suspension was real in memory and the file on disk was one
generation behind: a restart test reads "enabled" and reports a durability bug
that only appears under load.

The fix retries, and if every attempt fails it writes a `persist_failed` entry
into the audit trail - a silent swallow makes a restart that comes back enabled
unexplainable.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.a2a import state as st  # noqa: E402


RECORD = {"id": "agent-persist", "credential_ref": "vault://agent-persist"}


class PersistRetryTests(unittest.TestCase):
    def test_a_refused_replace_is_retried_not_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lifecycle.json")
            real_replace = os.replace
            calls = {"n": 0}

            def flaky(src, dst):
                calls["n"] += 1
                if calls["n"] < st.PERSIST_ATTEMPTS:
                    raise PermissionError(13, "held by a scanner", dst)
                return real_replace(src, dst)

            store = st.LifecycleStore([RECORD], path=path)
            with mock.patch.object(st.os, "replace", flaky):
                store.enable(RECORD["id"])
                store.suspend(RECORD["id"], reason="retry test")
            self.assertEqual(st.load_states(path)[RECORD["id"]], st.SUSPENDED)
            self.assertGreaterEqual(calls["n"], st.PERSIST_ATTEMPTS)

    def test_when_every_attempt_fails_the_audit_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lifecycle.json")

            def always(src, dst):
                raise PermissionError(13, "held by a scanner", dst)

            store = st.LifecycleStore([RECORD], path=path)
            with mock.patch.object(st.os, "replace", always):
                store.enable(RECORD["id"])
                store.suspend(RECORD["id"], reason="all attempts fail")
            # The security boundary is in memory: the agent is still blocked.
            with self.assertRaises(st.AgentBlocked):
                store.require_active(RECORD["id"])
            actions = [e.get("action") for e in store._audit]
            self.assertIn("persist_failed", actions)
            entry = [e for e in store._audit if e.get("action") == "persist_failed"][-1]
            self.assertIn("scanner", entry["reason"])


if __name__ == "__main__":
    unittest.main()
