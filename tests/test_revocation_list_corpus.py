"""Judge the peer's shipped revocation-list corpus, when a checkout is named.

The corpus is third-party material and is not vendored here: point
``UIBC_REVOCATION_CORPUS`` at a checkout of
``corpora/vectors-revocation-list`` to run this. Every member must conform on
all five recorded fields: decision, refused index, reason (code:detail), the
digests of the lists up to the refused one, and the list in force at the verdict.
"""

import os

import pytest

from uibc_core import revocation_list as rl

CORPUS = os.environ.get("UIBC_REVOCATION_CORPUS")


@pytest.mark.skipif(
    not CORPUS or not os.path.isfile(os.path.join(CORPUS, "MANIFEST.json")),
    reason="set UIBC_REVOCATION_CORPUS to a checkout of corpora/vectors-revocation-list",
)
def test_every_member_conforms_to_the_shipped_answer_key():
    summary = rl.judge_corpus(CORPUS)
    assert summary["members"] > 0
    assert summary["conforming"] == summary["members"], [
        r for r in summary["records"] if not r["conforms"]
    ]
