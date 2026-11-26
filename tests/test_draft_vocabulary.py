"""The package must not re-use a name that a published standard has taken.

RFC 9942 and the CCF/MMR receipt profiles give `vds` (label 395) to the
verifiable-data-structure *algorithm* identifier: it fixes the hash and the node
value size, and an unsupported value MUST be rejected. This draft used `vds` for
"which verifier key signed". Those are two different objects on one name, and a
reader who has both documents open cannot tell them apart.

The guard is behavioural where it can be: the signed statement must not contain
the key `vds` at all.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import cosign_head  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "drafts", "draft-zhao-uibc-evidence-chain-01.md")


def test_signed_statement_does_not_use_the_reserved_name():
    body = json.loads(cosign_head.message("ab" * 32, "owner", 7, "sha256:" + "cd" * 32))
    assert "vds" not in body, body
    assert body["verifier_id"] == "sha256:" + "cd" * 32


def test_draft_says_why_the_name_is_not_reused():
    text = open(DRAFT, encoding="utf-8").read()
    assert "Not `vds`" in text
    assert "RFC 9942" in text
    assert "verifier_id" in text
