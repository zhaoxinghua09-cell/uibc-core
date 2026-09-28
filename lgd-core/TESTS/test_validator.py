# -*- coding: utf-8 -*-
"""LGD Core Spec v0.1 — validator 单元测试（unittest 风格）。

运行（在 LGD-Core_v0.1 目录下）：
    python -m unittest discover -s TESTS -v

覆盖：
  - 夹具中两份合法 manifest 通过；
  - 夹具中两份非法 manifest 被拒；
  - 缺 identity（有籍）被拒；
  - evidence.required=true 而 items 为空（有证）被拒；
  - governance.gates 缺 audit（有门禁）被拒；
  - EXAMPLES/ 下非合规示例文件被判 FAIL。

本文件为代码，依本目录 LICENSE（Apache License 2.0）授权。
"""

import contextlib
import io
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "VALIDATOR"))

import validate_manifest as v  # noqa: E402

FIXTURES = ROOT / "TESTS" / "examples"
EXAMPLES = ROOT / "EXAMPLES"


def load(path):
    return v.load_manifest(str(path))


def base_manifest(**overrides):
    """返回一份可通过三律的基准 manifest；用 overrides 逐点破坏。"""
    data = {
        "lgd": {"version": "0.1"},
        "subject": {"type": "agent", "id": "agent.test.base"},
        "identity": {"owner": "test-owner", "version": "0.1.0"},
        "evidence": {"required": False, "items": []},
        "governance": {"gates": ["authorization", "audit"]},
        "audit": {"logging": True, "immutable": True},
    }
    for dotted, value in overrides.items():
        parts = dotted.split(".")
        cursor = data
        for part in parts[:-1]:
            cursor = cursor[part]
        cursor[parts[-1]] = value
    return data


class TestFixtures(unittest.TestCase):
    def test_valid_fixtures_pass(self):
        for name in ("valid-01.manifest.yaml", "valid-02.manifest.yaml"):
            with self.subTest(fixture=name):
                problems = v.validate(load(FIXTURES / name))
                self.assertEqual(problems, [], msg=f"{name} 应通过，实际: {problems}")

    def test_invalid_fixtures_fail(self):
        for name in (
            "invalid-01-no-identity.manifest.yaml",
            "invalid-02-evidence-empty.manifest.yaml",
        ):
            with self.subTest(fixture=name):
                problems = v.validate(load(FIXTURES / name))
                self.assertNotEqual(problems, [], msg=f"{name} 应被拒")


class TestThreeLaws(unittest.TestCase):
    def test_baseline_passes(self):
        self.assertEqual(v.validate(base_manifest()), [])

    def test_missing_identity_rejected(self):
        data = base_manifest()
        del data["identity"]["owner"]
        del data["identity"]["version"]
        problems = v.validate(data)
        self.assertTrue(any("LGD-I" in p for p in problems), msg=str(problems))

    def test_missing_subject_id_rejected(self):
        data = base_manifest()
        del data["subject"]["id"]
        problems = v.validate(data)
        self.assertTrue(any("LGD-I" in p for p in problems), msg=str(problems))

    def test_evidence_required_but_empty_rejected(self):
        data = base_manifest(**{"evidence.required": True, "evidence.items": []})
        problems = v.validate(data)
        self.assertTrue(any("LGD-II" in p for p in problems), msg=str(problems))

    def test_evidence_item_missing_date_rejected(self):
        data = base_manifest(
            **{
                "evidence.required": True,
                "evidence.items": [{"source": "placeholder:log"}],
            }
        )
        problems = v.validate(data)
        self.assertTrue(any("date" in p for p in problems), msg=str(problems))

    def test_gates_missing_audit_rejected(self):
        data = base_manifest(**{"governance.gates": ["authorization", "safety"]})
        problems = v.validate(data)
        self.assertTrue(any("audit" in p for p in problems), msg=str(problems))

    def test_audit_flags_must_be_true(self):
        data = base_manifest(**{"audit.logging": False, "audit.immutable": False})
        problems = v.validate(data)
        self.assertEqual(len([p for p in problems if "LGD-III" in p]), 2, msg=str(problems))

    def test_non_mapping_root_rejected(self):
        self.assertTrue(v.validate(["not", "a", "mapping"]))


class TestExamples(unittest.TestCase):
    def test_example_minimal_agent_passes(self):
        path = EXAMPLES / "example-minimal-agent.manifest.yaml"
        self.assertEqual(v.validate(load(path)), [])

    def test_example_medical_ai_agent_passes(self):
        path = EXAMPLES / "example-medical-ai-agent.manifest.yaml"
        data = load(path)
        self.assertEqual(v.validate(data), [])
        self.assertIn("medical", data)
        for field in (
            "data_source",
            "model_version",
            "evidence",
            "authorization",
            "clinical_risk_gates",
            "audit",
        ):
            self.assertIn(field, data["medical"], msg=f"medical 缺字段 {field}")

    def test_example_noncompliant_fails(self):
        path = EXAMPLES / "example-noncompliant.manifest.yaml"
        problems = v.validate(load(path))
        self.assertNotEqual(problems, [], msg="非合规示例应被判 FAIL")


class TestSchemaConsistency(unittest.TestCase):
    """schema 自身自洽 + 示例与 schema 一致（仅在装有 jsonschema 时运行）。"""

    def setUp(self):
        if not v._HAS_JSONSCHEMA:
            self.skipTest("环境未安装 jsonschema，跳过严格 schema 校验")

    def test_schema_itself_is_valid(self):
        from jsonschema import Draft202012Validator

        schema = json.loads((ROOT / "MANIFEST.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)

    def test_schema_accepts_valid_examples_rejects_noncompliant(self):
        schema = json.loads((ROOT / "MANIFEST.schema.json").read_text(encoding="utf-8"))
        from jsonschema import Draft202012Validator

        validator = Draft202012Validator(schema)
        self.assertEqual(
            list(validator.iter_errors(load(EXAMPLES / "example-minimal-agent.manifest.yaml"))),
            [],
        )
        self.assertEqual(
            list(validator.iter_errors(load(EXAMPLES / "example-medical-ai-agent.manifest.yaml"))),
            [],
        )
        self.assertNotEqual(
            list(validator.iter_errors(load(EXAMPLES / "example-noncompliant.manifest.yaml"))),
            [],
        )


class TestCli(unittest.TestCase):
    def test_cli_exit_codes(self):
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink):
            ok = v.main([str(EXAMPLES / "example-minimal-agent.manifest.yaml")])
            bad = v.main([str(EXAMPLES / "example-noncompliant.manifest.yaml")])
        self.assertEqual(ok, 0)
        self.assertEqual(bad, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
