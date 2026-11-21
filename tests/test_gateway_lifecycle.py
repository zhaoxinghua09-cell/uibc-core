"""Identity lifecycle tests (T/ISC 0174-2026 6.1.3 a/b) + gateway enforcement.

The clause has two halves and both are tested behaviourally, not by inspection:

  a) closed loop over 注册/启用/停用/注销 with no illegal transition;
  b) the change takes effect *immediately in this gateway* - suspend blocks the
     next call with 403, and resume re-runs the checks instead of flipping a flag.
"""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import cli as ucli
from uibc_core.signing import ed_generate_seed
from adapters.a2a import registry as reg
from adapters.a2a import state as st
from adapters.a2a.server import A2AAdapter, make_handler


def _record(**over):
    record = {
        "name": "uibc-verifier",
        "id": "did:web:verify.medxpert.cn",
        "capabilities": [{"name": "uibc/verify",
                          "description": "verify a UIBC package (S1-S6)"}],
        "protocols": ["a2a/1.0", "jsonrpc-2.0"],
        "endpoint": "https://verify.medxpert.cn/a2a/",
        "organization": {"name": "MedXpert", "identifier": "did:web:medxpert.cn"},
        "state": "registered",
        "vc": {"issuer": "did:web:medxpert.cn", "status": "active",
               "valid_until": "2030-01-01T00:00:00Z"},
        "authorization": {"scopes": ["uibc/verify"]},
    }
    record.update(over)
    return record


def _make_pkg(tmp, name):
    pkg = os.path.join(tmp, name)
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "gw-agent", "owner": "gw-owner",
        "agent_type": "software-agent", "version": "1"})())
    src = os.path.join(tmp, "ev.txt")
    with open(src, "w", encoding="utf-8") as handle:
        handle.write("gateway evidence\n")
    ucli.cmd_evidence(type("A", (), {
        "path": pkg, "type": "ACTION", "file": src,
        "media_type": "text/plain", "note": "n"})())
    key_path = os.path.join(tmp, name + ".edkey")
    with open(key_path, "w", encoding="ascii") as handle:
        handle.write("ed25519:" + ed_generate_seed().hex())
    ucli.cmd_submit(type("A", (), {"path": pkg, "key": key_path})())
    return pkg


class LifecycleStoreTests(unittest.TestCase):
    def setUp(self):
        self.record = reg.validate({"agents": [_record()]},
                                   allow_opaque_id=True)["agents"][0]
        self.store = st.LifecycleStore([self.record])

    def test_01_registered_is_not_forwardable(self):
        self.assertEqual(self.store.state(self.record["id"]), st.REGISTERED)
        with self.assertRaises(st.AgentBlocked):
            self.store.require_active(self.record["id"])

    def test_02_enable_allows_forwarding(self):
        self.store.enable(self.record["id"])
        self.store.require_active(self.record["id"])

    def test_03_suspend_blocks_next_call_immediately(self):
        self.store.enable(self.record["id"])
        self.store.suspend(self.record["id"], reason="credential incident")
        with self.assertRaises(st.AgentBlocked) as ctx:
            self.store.require_active(self.record["id"])
        self.assertEqual(ctx.exception.state, st.SUSPENDED)
        self.assertEqual(ctx.exception.clause, "6.1.3b")

    def test_04_illegal_transition_rejected(self):
        with self.assertRaises(st.LifecycleError):
            self.store.suspend(self.record["id"])
        self.store.enable(self.record["id"])
        self.store.revoke(self.record["id"], reason="left the network")
        with self.assertRaises(st.LifecycleError):
            self.store.enable(self.record["id"])

    def test_05_revoke_is_terminal(self):
        self.store.enable(self.record["id"])
        self.store.revoke(self.record["id"])
        for action in (self.store.enable, self.store.suspend):
            with self.assertRaises(st.LifecycleError):
                action(self.record["id"])
        with self.assertRaises(st.AgentBlocked):
            self.store.require_active(self.record["id"])

    def test_06_resume_after_suspend_checks_and_enables(self):
        self.store.enable(self.record["id"])
        self.store.suspend(self.record["id"])
        ok, violations = self.store.resume(self.record["id"])
        self.assertTrue(ok, violations)
        self.store.require_active(self.record["id"])

    def test_07_resume_refused_on_expired_credential(self):
        record = reg.validate({"agents": [_record(vc={
            "issuer": "did:web:medxpert.cn", "status": "active",
            "valid_until": "2020-01-01T00:00:00Z"})]})["agents"][0]
        store = st.LifecycleStore([record])
        store.enable(record["id"])
        store.suspend(record["id"])
        ok, violations = store.resume(record["id"])
        self.assertFalse(ok)
        self.assertTrue(any(v["code"] == "B6" for v in violations))
        self.assertEqual(store.state(record["id"]), st.SUSPENDED)

    def test_08_resume_refused_when_authorization_absent(self):
        record = reg.validate({"agents": [_record(authorization=None)]})["agents"][0]
        store = st.LifecycleStore([record])
        store.enable(record["id"])
        store.suspend(record["id"])
        ok, violations = store.resume(record["id"])
        self.assertFalse(ok)
        self.assertTrue(any(v["code"] == "B7" for v in violations))

    def test_09_resume_only_applies_to_suspended(self):
        self.store.enable(self.record["id"])
        with self.assertRaises(st.LifecycleError):
            self.store.resume(self.record["id"])

    def test_10_unknown_agent_rejected(self):
        with self.assertRaises(st.UnknownAgent):
            self.store.state("did:web:nobody.example")

    def test_11_audit_trail_records_transitions(self):
        self.store.enable(self.record["id"], actor="ops")
        self.store.suspend(self.record["id"], reason="probe", actor="ops")
        actions = [e["action"] for e in self.store.audit()]
        self.assertIn("register", actions)
        self.assertIn("enable", actions)
        self.assertIn("suspend", actions)

    def test_12_suspend_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lifecycle.json")
            store = st.LifecycleStore([self.record], path=path)
            store.enable(self.record["id"])
            store.suspend(self.record["id"], reason="restart test")
            reloaded = st.load_states(path)
            self.assertEqual(reloaded[self.record["id"]], st.SUSPENDED)
            # A fresh store seeded with that persisted state must still block.
            store2 = st.LifecycleStore([self.record])
            store2._states.update(reloaded)
            with self.assertRaises(st.AgentBlocked):
                store2.require_active(self.record["id"])


class GatewayEnforcementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="gw-")
        _make_pkg(cls.tmp, "good.uibc")
        cls.report = reg.validate({"agents": [_record()]}, allow_opaque_id=True)
        cls.card = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "adapters", "a2a", "agent-card.json")
        cls.agent_id = cls.report["agents"][0]["id"]
        cls.adapter = A2AAdapter(cls.tmp, cls.card, registry=cls.report)
        cls.adapter.lifecycle.enable(cls.agent_id)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.adapter))
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def _post(self, method, params, trace=None):
        body = json.dumps({"jsonrpc": "2.0", "id": 7, "method": method,
                           "params": params}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if trace:
            headers["X-AUIB-Trace-Id"] = trace
        req = urllib.request.Request("http://127.0.0.1:%d/rpc" % self.port,
                                     data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8")), exc.headers

    def test_20_call_with_agent_verified(self):
        status, payload, _ = self._post("uibc/verify", {
            "package": "good.uibc", "agent": self.agent_id})
        self.assertEqual(status, 200)
        self.assertEqual(payload["result"]["result"], "PASS")

    def test_21_call_without_agent_refused(self):
        status, payload, _ = self._post("uibc/verify", {"package": "good.uibc"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertIn("params.agent", payload["error"]["message"])

    def test_22_suspended_agent_gets_403_before_verification(self):
        self.adapter.lifecycle.suspend(self.agent_id, reason="test suspend")
        status, payload, _ = self._post("uibc/verify", {
            "package": "good.uibc", "agent": self.agent_id})
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["code"], -32001)
        self.assertEqual(payload["error"]["data"]["state"], st.SUSPENDED)
        self.assertEqual(payload["error"]["data"]["clause"], "6.1.3b")
        ok, _ = self.adapter.lifecycle.resume(self.agent_id)
        self.assertTrue(ok)

    def test_23_trace_id_inherited_from_upstream(self):
        status, payload, headers = self._post(
            "uibc/verify", {"package": "good.uibc", "agent": self.agent_id},
            trace="trace-from-upstream-0001")
        self.assertEqual(payload["traceId"], "trace-from-upstream-0001")
        self.assertEqual(headers.get("X-AUIB-Trace-Id"), "trace-from-upstream-0001")

    def test_24_trace_id_generated_when_absent(self):
        _status, payload, _headers = self._post(
            "uibc/verify", {"package": "good.uibc", "agent": self.agent_id})
        self.assertEqual(len(payload["traceId"]), 32)
        self.assertEqual(payload["traceId"], payload["traceId"].lower())

    def test_25_discover_returns_only_enabled_agents(self):
        self.adapter.lifecycle.suspend(self.agent_id, reason="hidden")
        payload = self.adapter.dispatch("gateway/discover", {"q": "verify"})
        self.assertEqual(payload["total"], 0)
        self.adapter.lifecycle.resume(self.agent_id)
        payload = self.adapter.dispatch("gateway/discover", {"q": "verify"})
        self.assertEqual(payload["total"], 1)
        self.assertGreater(payload["results"][0]["score"], 0)
        self.assertIn("ranking", payload)

    def test_26_registry_report_is_exposed(self):
        payload = self.adapter.dispatch("gateway/registry", {})
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["agents"]), 1)

    def test_27_access_log_records_forwarded_call(self):
        self._post("uibc/verify", {"package": "good.uibc", "agent": self.agent_id},
                   trace="log-me-1")
        entries = [e for e in self.adapter.access_log if e["trace"] == "log-me-1"]
        self.assertTrue(entries)
        self.assertEqual(entries[0]["result"], "PASS")

    def test_28_invalid_registry_refuses_start(self):
        bad = reg.validate({"agents": [_record(endpoint="")]})
        with self.assertRaises(ValueError):
            A2AAdapter(self.tmp, self.card, registry=bad)


if __name__ == "__main__":
    unittest.main()
