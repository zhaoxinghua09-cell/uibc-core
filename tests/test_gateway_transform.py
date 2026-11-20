"""Conversion, header mapping and template tests (7.2.2 a/b/e, 7.3.1 c, 6.1.1 d).

The clause worth testing hardest is 7.2.2 b): "semantic preservation". A converter
that turns 1, "1", true and null all into the string "1" passes any smoke test and
fails the clause, so the type cases are written as tests rather than assumed.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.a2a import registry as reg
from adapters.a2a import templates as tpl
from adapters.a2a import transform as tf


class RoundTripTests(unittest.TestCase):
    def test_01_nested_structure_survives(self):
        payload = {"agent": "did:web:verify.medxpert.cn",
                   "package": "good.uibc",
                   "layers": [{"id": "L1", "ok": True},
                              {"id": "L2", "ok": False}]}
        ok, back, diff = tf.check_roundtrip(payload)
        self.assertTrue(ok, diff)
        self.assertEqual(back, payload)

    def test_02_scalar_types_do_not_collapse(self):
        payload = {"int": 1, "str": "1", "bool": True, "none": None,
                   "float": 1.5}
        ok, back, diff = tf.check_roundtrip(payload)
        self.assertTrue(ok, diff)
        self.assertIsInstance(back["int"], int)
        self.assertIsInstance(back["str"], str)
        self.assertIs(back["bool"], True)
        self.assertIsNone(back["none"])
        self.assertIsInstance(back["float"], float)

    def test_03_empty_containers_survive(self):
        payload = {"empty_map": {}, "empty_list": []}
        ok, back, _ = tf.check_roundtrip(payload)
        self.assertTrue(ok)
        self.assertEqual(back["empty_map"], {})
        self.assertEqual(back["empty_list"], [])

    def test_04_awkward_keys_survive(self):
        payload = {"agent id": "x", "1st": 2}
        ok, back, diff = tf.check_roundtrip(payload)
        self.assertTrue(ok, diff)
        self.assertEqual(back, payload)

    def test_05_drift_is_detectable(self):
        """A deliberately corrupted XML must fail the comparison, not slip through."""
        xml = tf.json_to_xml({"count": 1})
        corrupted = xml.replace('json-type="int"', 'json-type="str"')
        self.assertNotEqual(tf.xml_to_json(corrupted), {"count": 1})


class ConvertTests(unittest.TestCase):
    def test_10_json_to_xml_and_back(self):
        payload = {"a": [1, 2], "b": {"c": "d"}}
        out = tf.convert(payload, "xml")
        self.assertEqual(out["target"], "xml")
        self.assertEqual(out["roundtrip"], "ok")
        self.assertIn("<a2a-message", out["payload"])

    def test_11_xml_to_json(self):
        xml = tf.json_to_xml({"n": 3})
        out = tf.convert(xml, "json")
        self.assertEqual(json.loads(out["payload"]), {"n": 3})

    def test_12_same_format_is_not_converted(self):
        out = tf.convert({"x": 1}, "json")
        self.assertEqual(out["roundtrip"], "not-needed")

    def test_13_unknown_target_rejected(self):
        with self.assertRaises(ValueError):
            tf.convert({"x": 1}, "yaml")

    def test_14_format_detection(self):
        self.assertEqual(tf.detect_format({"x": 1}), "json")
        self.assertEqual(tf.detect_format("<root/>"), "xml")
        self.assertEqual(tf.detect_format('{"x":1}'), "json")
        with self.assertRaises(ValueError):
            tf.detect_format("plain text")


class HeaderMapTests(unittest.TestCase):
    """7.3.1 c) 跨协议扩展头映射."""

    def _headers(self):
        return {"X-AUIB-Trace-Id": "t-1", "X-AUIB-Source": "gw-a",
                "X-AUIB-Target": "gw-b", "X-AUIB-Protocol-Version": "a2a/1.0",
                "X-AUIB-Timestamp": "2026-11-20T00:00:00Z"}

    def test_20_a2a_pass_through_keeps_every_slot(self):
        out = tpl.map_headers(self._headers(), "a2a")
        self.assertEqual(out["unmappable"], [])
        self.assertEqual(out["headers"]["X-AUIB-Trace-Id"], "t-1")

    def test_21_mcp_map_and_declares_the_slot_it_cannot_fill(self):
        out = tpl.map_headers(self._headers(), "mcp")
        self.assertEqual(out["headers"]["X-MCP-Trace-Id"], "t-1")
        self.assertEqual([u["slot"] for u in out["unmappable"]], ["timestamp"])

    def test_22_unknown_protocol_rejected(self):
        with self.assertRaises(ValueError):
            tpl.map_headers(self._headers(), "grpc")

    def test_23_absent_headers_are_not_invented(self):
        out = tpl.map_headers({"X-AUIB-Source": "gw-a"}, "a2a")
        self.assertEqual(list(out["headers"].keys()), ["X-AUIB-Source"])


class TemplateTests(unittest.TestCase):
    """6.1.1 d) 元数据模板化：模板必须能被真校验器接受，否则就是装饰品."""

    def test_30_two_templates_available(self):
        self.assertIn("medical-device", tpl.available())
        self.assertIn("government-service", tpl.available())

    def test_31_every_template_passes_the_real_validator(self):
        for template_id in tpl.available():
            candidate = tpl.build(template_id)
            verdict = reg.validate({"agents": [candidate]})
            self.assertTrue(verdict["ok"],
                            "%s template does not validate: %s"
                            % (template_id, verdict["errors"]))

    def test_32_overrides_replace_fields(self):
        candidate = tpl.build("medical-device", {"name": "another-verifier"})
        self.assertEqual(candidate["name"], "another-verifier")
        self.assertEqual(candidate["id"], "did:web:verify.medxpert.cn")

    def test_33_unknown_template(self):
        with self.assertRaises(ValueError):
            tpl.get("nope")


if __name__ == "__main__":
    unittest.main()
