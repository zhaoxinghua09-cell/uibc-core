"""The semantics freeze is a document, and this test is what makes it one.

If the seven states or the result schema change, the hashes recorded in
`docs/SEMANTICS-FREEZE.md` no longer match and this test fails. That is the point:
a freeze nobody enforces is a paragraph.

Fixing it means one of two deliberate acts -- update the freeze document and the
line-format version, or revert the semantic change. Both are visible in a diff.
"""

import hashlib
import json
import os
import re

import pytest

from uibc_core import interop_result as ir

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREEZE = os.path.join(REPO, "docs", "SEMANTICS-FREEZE.md")

_STATES_RE = re.compile(r"states-sha256:\s*([0-9a-f]{64})")
_SCHEMA_RE = re.compile(r"schema-sha256:\s*([0-9a-f]{64})")


def _frozen():
    with open(FREEZE, encoding="utf-8") as fh:
        text = fh.read()
    states = _STATES_RE.search(text)
    schema = _SCHEMA_RE.search(text)
    assert states and schema, "docs/SEMANTICS-FREEZE.md lost its hash lines"
    return states.group(1), schema.group(1)


def _actual():
    states = hashlib.sha256("|".join(ir.STATES).encode()).hexdigest()
    schema = hashlib.sha256(json.dumps(ir.states_document(), sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    return states, schema


def test_state_vocabulary_is_frozen():
    frozen, _ = _frozen()
    actual, _ = _actual()
    assert actual == frozen, (
        "the seven-state vocabulary changed. Either revert it, or update "
        "docs/SEMANTICS-FREEZE.md and bump the line-format version -- a semantic "
        "change that leaves the freeze intact is the failure this test exists for.")


def test_result_schema_is_frozen():
    _, frozen = _frozen()
    _, actual = _actual()
    assert actual == frozen, (
        "the published result schema changed. Same rule as above: update the freeze "
        "document deliberately, or revert.")


def test_freeze_does_not_cover_what_it_says_it_does_not():
    """A freeze page that quietly widens its own scope is worse than none."""
    with open(FREEZE, encoding="utf-8") as fh:
        text = fh.read()
    for claim in ("不覆盖检查集 S1–S19", "不是事实上的行业标准", "撤回"):
        assert claim in text, "the freeze page must keep stating its own limits"


def test_evidence_precondition_survives_any_schema_edit():
    """The one rule that must not be reachable by a schema-only change."""
    with pytest.raises(ir.ResultError):
        ir.result("VERIFIED", "did:key:z6Mksubject", evidence=[])
    schema = ir.states_document()
    assert schema["allOf"][0]["then"]["properties"]["evidence"]["minItems"] == 1
