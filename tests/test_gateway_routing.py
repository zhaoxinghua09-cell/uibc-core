"""Routing version/rollback, explainable routing, metrics and the journal.

Clauses: 8.1.1 a/b (versioned + static routes), 8.1.2 a/b (matching + the numbers
in the answer), 8.2.1 a/b (budget and live counters), 9.1.1 a-d (journal), and
6.1.1 c (metadata edit under review).
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.a2a import journal as jr
from adapters.a2a import metrics as mt
from adapters.a2a import registry as reg
from adapters.a2a import router as rt
from adapters.a2a.server import A2AAdapter

AGENT = "did:web:verify.medxpert.cn"


def _record(**over):
    record = {
        "name": "uibc-verifier",
        "id": AGENT,
        "capabilities": [{"name": "uibc/verify",
                          "description": "verify a UIBC package S1-S6"}],
        "protocols": ["a2a/1.0", "jsonrpc-2.0"],
        "endpoint": "https://verify.medxpert.cn/a2a/",
        "organization": {"name": "MedXpert", "identifier": "did:web:medxpert.cn"},
        "state": "enabled",
        "vc": {"issuer": "did:web:medxpert.cn", "status": "active",
               "valid_until": "2030-01-01T00:00:00Z"},
        "authorization": {"scopes": ["uibc/verify"]},
    }
    record.update(over)
    return record


class RouteTableTests(unittest.TestCase):
    def test_01_initial_version(self):
        table = rt.RouteTable(routes=[{"agent": AGENT, "match": {"service": "uibc"}}])
        self.assertEqual(table.current_version, 1)
        self.assertEqual(len(table.current_routes()), 1)

    def test_02_add_version_moves_pointer(self):
        table = rt.RouteTable(routes=[{"agent": "a"}])
        self.assertEqual(table.add_version([{"agent": "b"}], note="second"), 2)
        self.assertEqual(table.current_version, 2)
        self.assertEqual(table.current_routes()[0]["agent"], "b")

    def test_03_rollback_restores_history(self):
        table = rt.RouteTable(routes=[{"agent": "a"}])
        table.add_version([{"agent": "b"}])
        self.assertEqual(table.rollback(1), 1)
        self.assertEqual(table.current_routes()[0]["agent"], "a")
        # history is kept, not rewritten
        self.assertEqual([v["version"] for v in table.versions()], [1, 2])

    def test_04_rollback_to_unknown_version_rejected(self):
        table = rt.RouteTable(routes=[{"agent": "a"}])
        with self.assertRaises(ValueError):
            table.rollback(99)

    def test_05_static_match_by_service(self):
        table = rt.RouteTable(routes=[{"agent": AGENT, "match": {"service": "uibc"}}])
        hit = table.match(service="uibc")
        self.assertEqual(hit["agent"], AGENT)
        self.assertEqual(hit["version"], 1)
        self.assertIsNone(table.match(service="other"))

    def test_06_static_match_by_api_prefix(self):
        table = rt.RouteTable(routes=[{"agent": AGENT, "match": {"api": "/a2a/"}}])
        self.assertIsNotNone(table.match(api="/a2a/rpc"))
        self.assertIsNone(table.match(api="/other"))

    def test_07_rollback_is_logged(self):
        table = rt.RouteTable(routes=[{"agent": "a"}])
        table.add_version([{"agent": "b"}])
        table.rollback(1)
        actions = [e["action"] for e in table.log]
        self.assertEqual(actions, ["add", "add", "rollback"])

    def test_08_persists_and_reloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "routes.json")
            table = rt.RouteTable(routes=[{"agent": "a"}], path=path)
            table.add_version([{"agent": "b"}])
            with open(path, encoding="utf-8") as handle:
                stored = json.load(handle)
            self.assertEqual(stored["current"], 2)
            self.assertEqual(len(stored["versions"]), 2)


class SemanticRouteTests(unittest.TestCase):
    """8.1.2 b) 可解释性：阈值、候选集、得分、依据，一个都不能少."""

    def _records(self):
        return reg.validate({"agents": [_record()]})["agents"]

    def test_20_match_returns_numbers(self):
        out = rt.semantic_route("verify a uibc package", self._records(), threshold=0.2)
        self.assertEqual(out["decision"], AGENT)
        self.assertIn("threshold", out)
        self.assertIn("candidates", out)
        self.assertIn("basis", out)
        self.assertGreater(out["score"], 0.0)
        self.assertIn("jaccard", out["basis"])

    def test_21_below_threshold_holds(self):
        out = rt.semantic_route("明天的天气如何", self._records(), threshold=0.9)
        self.assertIsNone(out["decision"])
        self.assertIn("below threshold", out["reason"])

    def test_22_decision_is_logged(self):
        log = []
        rt.semantic_route("verify uibc", self._records(), log=log)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["decision"], AGENT)

    def test_23_candidates_are_bounded(self):
        out = rt.semantic_route("verify", self._records(), top_k=10)
        self.assertLessEqual(len(out["candidates"]), 10)


class MetricsTests(unittest.TestCase):
    def test_30_snapshot_reports_budget_and_quantiles(self):
        metrics = mt.Metrics(latency_budget_ms=100.0)
        for value in (10, 20, 30, 400):
            metrics.observe("uibc/verify", value, result="PASS")
        snap = metrics.snapshot()
        self.assertEqual(snap["requests_total"], 4)
        self.assertEqual(snap["latency_ms"]["over_budget"], 1)
        self.assertAlmostEqual(snap["latency_ms"]["p50"], 20.0)
        self.assertEqual(snap["latency_ms"]["budget"], 100.0)

    def test_31_errors_and_blocked_are_separate(self):
        metrics = mt.Metrics()
        metrics.observe("uibc/verify", 5, error=True, result="ERROR")
        metrics.observe("uibc/verify", 5, blocked=True, result="BLOCKED")
        snap = metrics.snapshot()
        self.assertEqual(snap["errors_total"], 1)
        self.assertEqual(snap["blocked_total"], 1)
        self.assertAlmostEqual(snap["error_rate"], 0.5)

    def test_32_prometheus_exposition(self):
        metrics = mt.Metrics()
        metrics.observe("uibc/verify", 12, result="PASS")
        text = metrics.render_prometheus()
        self.assertIn("uibc_gateway_requests_total 1", text)
        self.assertIn('method="uibc/verify"', text)


class JournalTests(unittest.TestCase):
    def test_40_append_and_query_by_trace(self):
        journal = jr.Journal()
        journal.record({"trace": "t-1", "method": "uibc/verify", "result": "PASS"})
        journal.record({"trace": "t-2", "method": "uibc/gate", "result": "ALLOW"})
        out = journal.query(trace="t-1")
        self.assertEqual(out["total"], 1)
        self.assertEqual(out["entries"][0]["result"], "PASS")

    def test_41_query_by_agent_and_method(self):
        journal = jr.Journal()
        journal.record({"agent": "a", "method": "uibc/verify"})
        journal.record({"agent": "a", "method": "uibc/gate"})
        journal.record({"agent": "b", "method": "uibc/verify"})
        self.assertEqual(journal.query(agent="a", method="uibc/verify")["total"], 1)

    def test_42_limit_and_tail(self):
        journal = jr.Journal()
        for index in range(5):
            journal.record({"trace": "t-%d" % index})
        self.assertEqual(journal.query(limit=2)["returned"], 2)
        self.assertEqual(journal.tail(2)[-1]["trace"], "t-4")

    def test_43_file_backed_and_survives_a_new_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "journal.jsonl")
            journal = jr.Journal(path)
            journal.record({"trace": "t-1", "method": "uibc/verify", "result": "PASS"})
            other = jr.Journal(path)
            self.assertEqual(other.query(trace="t-1")["total"], 1)

    def test_44_no_payload_bodies_are_stored(self):
        """The journal records who/what/how long - never the message content."""
        journal = jr.Journal()
        journal.record({"trace": "t-1", "method": "uibc/verify",
                        "agent": AGENT, "result": "PASS"})
        entry = journal.query(trace="t-1")["entries"][0]
        self.assertNotIn("payload", entry)
        self.assertNotIn("evidence", entry)


class MetadataEditTests(unittest.TestCase):
    """6.1.1 c) 在线修改需经过审核：没 approve 就不能落地."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="edit-")
        self.card = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "adapters", "a2a", "agent-card.json")
        self.report = reg.validate({"agents": [_record()]})
        # The fixture record already declares state=enabled, so the store starts
        # in enabled; no extra enable() call (that would be an illegal transition).
        self.adapter = A2AAdapter(self.tmp, self.card, registry=self.report)

    def test_50_change_without_approval_is_pending(self):
        out = self.adapter.dispatch("gateway/registry/update", {
            "agent": AGENT, "patch": {"name": "renamed"}, "actor": "ops",
            "reason": "rename"})
        self.assertTrue(out["pending_review"])
        self.assertFalse(out["applied"])
        self.assertEqual(self.adapter.registry_report["agents"][0]["name"],
                         "uibc-verifier")

    def test_51_approved_change_applies(self):
        out = self.adapter.dispatch("gateway/registry/update", {
            "agent": AGENT, "patch": {"name": "renamed"}, "approve": True})
        self.assertTrue(out["applied"])
        self.assertEqual(self.adapter.registry_report["agents"][0]["name"],
                         "renamed")
        self.assertEqual(out["diff"]["before"]["name"], "uibc-verifier")

    def test_52_invalid_change_is_rejected_before_apply(self):
        out = self.adapter.dispatch("gateway/registry/update", {
            "agent": AGENT, "patch": {"endpoint": ""}, "approve": True})
        self.assertFalse(out["ok"])
        self.assertFalse(out["applied"])
        self.assertEqual(out["errors"][0]["code"], "R1")
        self.assertEqual(self.adapter.registry_report["agents"][0]["endpoint"],
                         "https://verify.medxpert.cn/a2a/")

    def test_53_unknown_agent_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter.dispatch("gateway/registry/update", {
                "agent": "did:web:nobody.example", "patch": {"name": "x"}})

    def test_54_edit_events_land_in_the_journal(self):
        self.adapter.dispatch("gateway/registry/update", {
            "agent": AGENT, "patch": {"name": "renamed"}})
        types = [e["type"] for e in self.adapter.journal.query()["entries"]]
        self.assertIn("metadata-change-pending", types)

    def test_55_templates_are_exposed_and_validated(self):
        listing = self.adapter.dispatch("gateway/templates", {})
        self.assertIn("medical-device", listing["templates"])
        one = self.adapter.dispatch("gateway/templates", {"id": "medical-device"})
        self.assertTrue(one["validation"]["ok"])

    def test_56_route_rpc_reports_version_and_numbers(self):
        out = self.adapter.dispatch("gateway/route", {"text": "verify uibc package"})
        self.assertIn("route_version", out)
        self.assertIn("threshold", out)
        self.assertEqual(out["decision"], AGENT)

    def test_57_routes_rpc_add_and_rollback(self):
        added = self.adapter.dispatch("gateway/routes", {
            "op": "add", "routes": [{"agent": AGENT, "match": {"service": "uibc"}}]})
        self.assertEqual(added["current"], 2)
        back = self.adapter.dispatch("gateway/routes", {"op": "rollback", "version": 1})
        self.assertEqual(back["current"], 1)

    def test_58_transform_rpc_refuses_unsupported_format(self):
        with self.assertRaises(ValueError):
            self.adapter.dispatch("gateway/transform", {"payload": {"a": 1},
                                                        "target": "yaml"})

    def test_59_transform_rpc_converts_with_roundtrip_proof(self):
        out = self.adapter.dispatch("gateway/transform", {"payload": {"a": [1, 2]},
                                                          "target": "xml"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["roundtrip"], "ok")


if __name__ == "__main__":
    unittest.main()
