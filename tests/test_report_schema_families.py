"""The report shapes added for the peer's corpus readers must hold up.

Two things are pinned here, and they are different jobs:

1. lines this repository actually emits satisfy the schema and the linter;
2. a line that is not a report is refused, with the reason named. A rule set
   that only accepts well-formed lines proves nothing, so every shape gets a
   negative case that the linter must bite on.

The positive lines are built with the same functions the CLI uses
(`_mcp_authz_line`, `_revocation_list_line`, `_key_revocation_list_line`,
`_agent_card_receipt_line`), not copied by hand: a copy drifts silently the
first time a field is renamed.
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "tools", "report_lint.py")
SCHEMAS = {
    name: os.path.join(ROOT, "interop", name)
    for name in ("mcp-authz-report.schema.json", "revocation-list-report.schema.json",
                 "key-revocation-list-report.schema.json",
                 "agent-card-receipt-report.schema.json",
                 "revocation-delta-report.schema.json")
}

pytestmark = pytest.mark.skipif(
    not (os.path.exists(LINT) and all(os.path.exists(p) for p in SCHEMAS.values())),
    reason="interop/ and tools/ are repository material, not sdist payload; "
           "run this from a checkout")

sys.path.insert(0, ROOT)
from uibc_core import cli  # noqa: E402


def _lint(lines):
    tmp = tempfile.mkdtemp(prefix="lint-fam-")
    path = os.path.join(tmp, "r.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
    return subprocess.run([sys.executable, LINT, path], capture_output=True,
                          text=True, timeout=120)


def _ours():
    """One line of each of the fifteen shapes the five emitters can produce."""
    digest = "a" * 64
    head = "sha256:" + "b" * 64
    return [
        cli._mcp_authz_line("case-1", "valid", [], 0),
        cli._mcp_authz_line("case-2", "invalid", ["prm-absent", "ath-mismatch"], 1),
        cli._mcp_authz_line("case-3", None, [], 3, error="not JSON"),
        cli._revocation_list_line("case-1", "valid", None, None, 0),
        cli._revocation_list_line("case-2", "invalid", "revocation_list_rollback", 2, 1),
        cli._revocation_list_line("case-3", None, None, None, 3, error="not JSON"),
        cli._key_revocation_list_line("case-1", "revoked", "revoked_in_list",
                                      {"rule": "in_list", "index": 1}, 0),
        cli._key_revocation_list_line("case-2", "rejected", "signer_not_trusted",
                                      {"rule": "shape", "refusal": "list_unsigned"}, 3),
        cli._key_revocation_list_line("case-3", None, None, None, 3, error="not JSON"),
        cli._agent_card_receipt_line("case-1", "accept", "receipt_current", digest, 0),
        cli._agent_card_receipt_line("case-2", "reject", "revocation_list_absent",
                                     None, 1),
        cli._agent_card_receipt_line("case-3", None, None, None, 3, error="not JSON"),
        cli._revocation_delta_line("RL01", "accept", "in_force", None, 0, head=head, seq=1),
        cli._revocation_delta_line("RL07", "reject", "revocation_entry_repeated", 1, 1),
        cli._revocation_delta_line("RL01", None, None, None, 3, error="not readable"),
    ]


def test_our_own_lines_pass_the_linter():
    proc = _lint(_ours())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "REPORT LINT OK: 15 line(s)" in proc.stdout


def test_the_linter_names_every_format_it_can_judge():
    proc = _lint(_ours())
    for name in SCHEMAS:
        assert os.path.basename(SCHEMAS[name]) in proc.stdout


def test_a_refusal_that_exits_zero_is_refused():
    line = cli._key_revocation_list_line("c", "rejected", "signer_not_trusted",
                                         {"rule": "shape"}, 3)
    line["exit"] = 0
    proc = _lint([line])
    assert proc.returncode == 1
    assert "decision 'rejected' exits 3" in proc.stdout


def test_no_statement_filed_as_a_failure_is_refused():
    line = cli._key_revocation_list_line("c", "not_revoked", "covered_no_entry",
                                         {"rule": "absent"}, 1)
    line["decision"] = "no_statement"
    line["result"] = "FAIL"
    proc = _lint([line])
    assert proc.returncode == 1
    assert "cannot be filed as FAIL" in proc.stdout


def test_a_reached_decision_without_its_rule_is_refused():
    line = cli._key_revocation_list_line("c", "revoked", "revoked_in_list",
                                         {"rule": "in_list"}, 0)
    line["basis"] = None
    proc = _lint([line])
    assert proc.returncode == 1
    assert "must name the rule that produced it" in proc.stdout


def test_an_invalid_observation_with_no_finding_is_refused():
    line = cli._mcp_authz_line("c", "invalid", ["prm-absent"], 1)
    line["codes"] = []
    proc = _lint([line])
    assert proc.returncode == 1
    assert "refusal with no code" in proc.stdout


def test_a_valid_chain_that_names_a_position_is_refused():
    line = cli._revocation_list_line("c", "valid", None, None, 0)
    line["index"] = 3
    proc = _lint([line])
    assert proc.returncode == 1
    assert "a valid chain names no position" in proc.stdout


def test_an_error_line_that_carries_a_verdict_is_refused():
    line = cli._revocation_list_line("c", None, None, None, 3, error="not JSON")
    line["verdict"] = "invalid"
    proc = _lint([line])
    assert proc.returncode == 1
    assert "an ERROR line carries null verdict" in proc.stdout


def test_an_unknown_reason_token_is_refused():
    line = cli._revocation_list_line("c", "invalid", "revocation_list_shape", None, 1)
    line["reason"] = "shape"
    proc = _lint([line])
    assert proc.returncode == 1
    assert "not one of the ten revocation_list_* tokens" in proc.stdout


def test_an_unknown_key_is_refused_in_the_new_shapes():
    line = cli._mcp_authz_line("c", "valid", [], 0)
    line["score"] = 0.99
    proc = _lint([line])
    assert proc.returncode == 1
    assert "unknown key 'score'" in proc.stdout


def test_a_pass_line_that_carries_a_refusing_reason_is_refused():
    """`accept` has one reason; a PASS line wearing another is a smuggled refusal."""
    line = cli._agent_card_receipt_line("c", "accept", "receipt_current", "a" * 64, 0)
    line["reason"] = "revocation_list_absent"
    proc = _lint([line])
    assert proc.returncode == 1
    assert "accept/receipt_current" in proc.stdout


def test_a_rejection_named_receipt_current_is_refused():
    line = cli._agent_card_receipt_line("c", "reject", "receipt_current", "a" * 64, 1)
    proc = _lint([line])
    assert proc.returncode == 1
    assert "must name a refusing reason" in proc.stdout


def test_a_receipt_refusal_that_exits_zero_is_refused():
    line = cli._agent_card_receipt_line("c", "reject", "receipt_expired", "a" * 64, 1)
    line["exit"] = 0
    proc = _lint([line])
    assert proc.returncode == 1
    assert "result 'FAIL' exits 1" in proc.stdout


def test_an_error_line_that_carries_a_digest_is_refused():
    line = cli._agent_card_receipt_line("c", None, None, None, 3, error="not JSON")
    line["subject_digest"] = "b" * 64
    proc = _lint([line])
    assert proc.returncode == 1
    assert "null decision, reason and subject_digest" in proc.stdout


def test_a_digest_that_is_not_lowercase_hex_is_refused():
    line = cli._agent_card_receipt_line("c", "accept", "receipt_current", "A" * 64, 0)
    proc = _lint([line])
    assert proc.returncode == 1
    assert "subject_digest must be 64 lowercase hex" in proc.stdout


def test_an_acceptance_without_the_head_it_holds_is_refused():
    """A PASS that names no head cannot be carried forward by a reader."""
    line = cli._revocation_delta_line("RL01", "accept", "in_force", None, 0,
                                      head="sha256:" + "b" * 64, seq=1)
    line["head"] = None
    proc = _lint([line])
    assert proc.returncode == 1
    assert "must carry the head and seq it holds" in proc.stdout


def test_a_refusal_that_carries_a_head_is_refused():
    """A head on a refusal names a list that was never installed."""
    line = cli._revocation_delta_line("RL07", "reject", "revocation_entry_repeated", 1, 1)
    line["head"] = "sha256:" + "b" * 64
    proc = _lint([line])
    assert proc.returncode == 1
    assert "carries null head and seq" in proc.stdout


def test_a_refusal_wearing_in_force_is_refused():
    line = cli._revocation_delta_line("RL07", "reject", "revocation_entry_repeated", 1, 1)
    line["reason"] = "in_force"
    proc = _lint([line])
    assert proc.returncode == 1
    assert "must name one of the ten suite tokens" in proc.stdout


def test_a_head_that_is_not_a_list_digest_is_refused():
    line = cli._revocation_delta_line("RL01", "accept", "in_force", None, 0,
                                      head="sha256:" + "B" * 64, seq=1)
    proc = _lint([line])
    assert proc.returncode == 1
    assert "head must be 'sha256:' plus 64 lowercase hex" in proc.stdout


def test_each_new_schema_is_a_file_a_stranger_can_read_and_is_valid():
    js = pytest.importorskip("jsonschema")
    for name, path in SCHEMAS.items():
        with open(path, encoding="utf-8") as fh:
            schema = json.load(fh)
        assert schema["$schema"].startswith("https://json-schema.org/draft/2020-12")
        assert schema["additionalProperties"] is False
        js.Draft202012Validator.check_schema(schema)
        validator = js.Draft202012Validator(schema)
        for line in _ours():
            if line["format"] == schema["properties"]["format"]["const"]:
                assert not list(validator.iter_errors(line)), (name, line)
