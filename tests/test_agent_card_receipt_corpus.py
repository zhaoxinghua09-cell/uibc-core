"""The peer's own agent-card-receipt corpus, read by this reader.

Their 49 cases are not vendored into this repository: a neighbour editing a
fixture should not be able to turn our suite red, and a corpus copied into our
tree would stop being *theirs*. Set ``UIBC_AGENT_CARD_RECEIPT_CORPUS`` to the
corpus directory (the one holding ``MANIFEST.json``) to run it.

The digest check is not a courtesy: the corpus declares one digest over the
entries it lists, each entry carries a digest per file, and recomputing both
from the bytes on disk is what makes "we read their corpus" a claim about the
files rather than about a directory name.
"""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from uibc_core import agent_card_receipt as acr

CORPUS = os.environ.get("UIBC_AGENT_CARD_RECEIPT_CORPUS")

needs_corpus = pytest.mark.skipif(
    not CORPUS or not os.path.isfile(os.path.join(CORPUS or "", "MANIFEST.json")),
    reason="set UIBC_AGENT_CARD_RECEIPT_CORPUS to the corpus directory to read it",
)


@needs_corpus
def test_every_member_matches_the_answer_key():
    summary = acr.judge_corpus(CORPUS)
    wrong = [r for r in summary["records"] if not r["conforms"]]
    assert wrong == []
    assert summary["members"] == summary["conforming"]
    assert summary["members"] >= 49


@needs_corpus
def test_the_suite_is_the_one_we_read_about():
    with open(os.path.join(CORPUS, "MANIFEST.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["suite"] == acr.SUITE
    assert manifest["counts"] == {"accept": 13, "reject": 36}
    reasons = {entry["expected"]["reason"] for entry in manifest["vectors"]}
    assert reasons <= set(acr.REASONS)
    assert "receipt_current" in reasons


@needs_corpus
def test_the_corpus_digest_recomputes_from_its_bytes():
    with open(os.path.join(CORPUS, "MANIFEST.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    entries = []
    for entry in manifest["vectors"]:
        directory = os.path.join(CORPUS, entry["path"])
        files = {}
        for name in entry["files"]:
            with open(os.path.join(directory, name), "rb") as fh:
                files[name] = hashlib.sha256(fh.read()).hexdigest()
        entries.append({**entry, "files": files})
    blob = json.dumps(entries, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    assert hashlib.sha256(blob.encode()).hexdigest() == manifest["corpusDigest"]


@needs_corpus
def test_a_case_whose_list_is_absent_is_refused_rather_than_passed():
    """Rule 11, checked on their case: no list is not a clean receipt."""
    case = os.path.join(CORPUS, "cases", "revocation-list-absent")
    got = acr.judge_case(case)
    assert got["decision"] == "reject"
    assert got["reason"] == "revocation_list_absent"
    assert got["exit"] == 1
