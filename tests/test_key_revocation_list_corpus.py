"""The peer's own corpus, read by this reader, when a checkout is named.

Their 13 cases are not vendored into this repository: a neighbour editing a
fixture should not be able to turn our suite red. Set
``UIBC_KEY_REVOCATION_CORPUS`` to the corpus directory (the one holding
``MANIFEST.json``) to run it.
"""

from __future__ import annotations

import os

import pytest

from uibc_core import key_revocation_list as krl

CORPUS = os.environ.get("UIBC_KEY_REVOCATION_CORPUS")

needs_corpus = pytest.mark.skipif(
    not CORPUS or not os.path.isfile(os.path.join(CORPUS or "", "MANIFEST.json")),
    reason="set UIBC_KEY_REVOCATION_CORPUS to the corpus directory to read it",
)


@needs_corpus
def test_every_member_matches_the_answer_key():
    summary = krl.judge_corpus(CORPUS)
    wrong = [r for r in summary["records"] if not r["conforms"]]
    assert wrong == []
    assert summary["members"] == summary["conforming"]
    assert summary["members"] >= 13


@needs_corpus
def test_the_corpus_digest_recomputes_from_its_bytes():
    """The digest the corpus declares is the digest of the entries on disk."""
    import hashlib
    import json

    with open(os.path.join(CORPUS, "MANIFEST.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    entries = []
    for entry in manifest["vectors"]:
        directory = os.path.join(CORPUS, entry["path"])
        files = {
            name: hashlib.sha256(open(os.path.join(directory, name), "rb").read()).hexdigest()
            for name in entry["files"]
        }
        entries.append({**entry, "files": files})
    blob = json.dumps(entries, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    assert hashlib.sha256(blob.encode()).hexdigest() == manifest["corpusDigest"]
