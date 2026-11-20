"""Backup/restore and tool-descriptor validation.

Clauses: 6.3.1 a/c, 6.3.2 a/b (backup, incremental, corruption detect, restore)
and 7.1.1 b) (parse and validate a general model-interface definition).

The tests deliberately attack the backup: corrupt a copy, corrupt live state, and
restore from a tampered snapshot. A backup path that only ever runs over healthy
files proves nothing.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.a2a import backup as bk
from adapters.a2a import specs as sp
from adapters.a2a.server import A2AAdapter


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bk-")
        self.states = []
        for name in ("registry.json", "lifecycle.json"):
            path = os.path.join(self.tmp, name)
            _write(path, {"n": 1})
            self.states.append(path)
        self.store = bk.BackupStore(os.path.join(self.tmp, "backups"), self.states)

    def test_01_full_backup_creates_manifest(self):
        manifest = self.store.create()
        self.assertFalse(manifest["incremental"])
        self.assertEqual(len(manifest["files"]), 2)
        self.assertFalse(manifest["encrypted"])       # 6.3.1 b) not implemented
        self.assertIn("未实现", manifest["encryption_note"])

    def test_02_verify_clean_snapshot(self):
        self.store.create()
        report = self.store.verify()
        self.assertTrue(report["ok"])
        self.assertEqual(report["checked"], 2)

    def test_03_verify_catches_tampered_copy(self):
        self.store.create()
        victim = os.path.join(self.store.latest(), "registry.json")
        with open(victim, "a", encoding="utf-8") as handle:
            handle.write(" ")
        report = self.store.verify()
        self.assertFalse(report["ok"])
        self.assertEqual(report["mismatch"][0]["reason"], "sha256 mismatch")

    def test_04_incremental_skips_unchanged(self):
        self.store.create()
        _write(self.states[0], {"n": 2})               # one file changed
        manifest = self.store.create(incremental=True)
        self.assertTrue(manifest["incremental"])
        self.assertEqual(manifest["unchanged_carried_over"], 1)
        carried = [f for f in manifest["files"] if f["carried_over"]]
        self.assertEqual(len(carried), 1)

    def test_05_detect_corruption_reports_change_and_breakage(self):
        self.store.create()
        _write(self.states[0], {"n": 2})
        with open(self.states[1], "w", encoding="utf-8") as handle:
            handle.write("{not json")
        report = self.store.detect_corruption()
        reasons = [d["reason"] for d in report["drift"]]
        self.assertIn("changed since snapshot", reasons)
        self.assertIn("unparsable JSON", reasons)
        self.assertTrue(report["alert"])

    def test_06_restore_round_trips(self):
        self.store.create()
        _write(self.states[0], {"n": 999})
        out = self.store.restore()
        self.assertTrue(out["ok"])
        with open(self.states[0], encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"n": 1})

    def test_07_restore_refuses_unverified_backup(self):
        self.store.create()
        victim = os.path.join(self.store.latest(), "registry.json")
        with open(victim, "a", encoding="utf-8") as handle:
            handle.write(" ")
        with self.assertRaises(ValueError):
            self.store.restore()

    def test_08_restore_to_an_isolated_directory(self):
        self.store.create()
        target = os.path.join(self.tmp, "restored")
        out = self.store.restore(target_dir=target)
        self.assertTrue(all(path.startswith(target) for path in out["restored"]))


class SpecTests(unittest.TestCase):
    """7.1.1 b) 通用模型接口定义规范的解析与校验."""

    def test_10_example_descriptor_is_valid(self):
        self.assertEqual(sp.validate_tool_descriptor(sp.MCP_EXAMPLE), [])

    def test_11_missing_fields(self):
        problems = sp.validate_tool_descriptor({"name": "x"})
        codes = [p["code"] for p in problems]
        self.assertEqual(codes.count("D1"), 2)

    def test_12_whitespace_in_name_rejected(self):
        descriptor = dict(sp.MCP_EXAMPLE, name="uibc verify")
        self.assertEqual(sp.validate_tool_descriptor(descriptor)[0]["code"], "D2")

    def test_13_too_short_description(self):
        descriptor = dict(sp.MCP_EXAMPLE, description="verify")
        self.assertEqual(sp.validate_tool_descriptor(descriptor)[0]["code"], "D3")

    def test_14_schema_must_be_object(self):
        descriptor = dict(sp.MCP_EXAMPLE,
                          inputSchema={"type": "array", "properties": {}})
        self.assertEqual(sp.validate_tool_descriptor(descriptor)[0]["code"], "D4")

    def test_15_schema_without_properties_is_unactionable(self):
        descriptor = dict(sp.MCP_EXAMPLE, inputSchema={"type": "object"})
        self.assertEqual(sp.validate_tool_descriptor(descriptor)[0]["code"], "D5")

    def test_16_required_must_exist_in_properties(self):
        descriptor = dict(sp.MCP_EXAMPLE, inputSchema={
            "type": "object", "properties": {"a": {"type": "string"}},
            "required": ["b"]})
        self.assertEqual(sp.validate_tool_descriptor(descriptor)[0]["code"], "D6")

    def test_17_duplicate_tool_names(self):
        out = sp.validate_tool_descriptors([sp.MCP_EXAMPLE, dict(sp.MCP_EXAMPLE)])
        self.assertFalse(out["ok"])
        self.assertEqual(out["invalid"][0]["errors"][0]["code"], "D8")

    def test_18_list_validation_counts(self):
        out = sp.validate_tool_descriptors([sp.MCP_EXAMPLE])
        self.assertTrue(out["ok"])
        self.assertEqual(out["valid"], 1)


class AdapterSpecAndBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gw2-")
        self.registry_path = os.path.join(self.tmp, "registry.json")
        _write(self.registry_path, {"agents": []})   # not used, just a state file
        self.card = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "adapters", "a2a", "agent-card.json")
        self.adapter = A2AAdapter(self.tmp, self.card,
                                  journal_path=os.path.join(self.tmp, "journal.jsonl"),
                                  backup_root=os.path.join(self.tmp, "backups"))

    def test_20_specs_rpc(self):
        out = self.adapter.dispatch("gateway/specs", {"descriptor": sp.MCP_EXAMPLE})
        self.assertTrue(out["ok"])

    def test_21_backup_rpc_create_and_list(self):
        created = self.adapter.dispatch("gateway/backup", {"op": "create"})
        self.assertTrue(created["ok"])
        listed = self.adapter.dispatch("gateway/backup", {"op": "list"})
        self.assertTrue(listed["backups"])

    def test_22_backup_rpc_without_directory_refuses(self):
        adapter = A2AAdapter(self.tmp, self.card)
        with self.assertRaises(ValueError):
            adapter.dispatch("gateway/backup", {"op": "create"})


if __name__ == "__main__":
    unittest.main()
