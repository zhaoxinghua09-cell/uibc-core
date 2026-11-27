"""Guards for the profile draft.

The point of the profile is that it leans on published standards instead of
proposing a parallel format. That is a property a script can check: the normative
reference line must not name any Internet-Draft, the registered value must have
exactly the four members the text describes, and the "what a pass establishes"
sentence must be present verbatim-ish, because that sentence is the deliverable.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.join(ROOT, "drafts", "draft-zhao-uibc-scitt-profile-00.md")


def read():
    return open(PROFILE, encoding="utf-8").read()


def test_normative_references_are_published_only():
    text = read()
    line = [l for l in text.splitlines() if l.startswith("Normative:")][0]
    assert "draft-" not in line, line
    for ref in ("RFC9942", "RFC9943"):
        assert ref in line, ref


def test_registered_value_members_are_the_ones_described():
    text = read()
    block = re.search(r"\{\n(.*?)\n\}", text, re.S).group(1)
    members = re.findall(r'"([a-z_]+)":', block)
    assert members == ["profile", "root", "count", "agent_id"], members


def test_the_one_sentence_is_present():
    text = read()
    assert "A passing check establishes that the holder's package reproduces" in text
    assert "It does not establish that the evidence is true" in text


def test_step_one_is_readable_without_the_companion_document():
    text = read()
    assert "the three facts it needs are restated here" in text
    for fact in ("`evidence/index.json` lists", "sorted content hashes",
                 "entry count taken from the index"):
        assert fact in text, fact


def test_it_claims_no_adoption():
    text = " ".join(read().split())
    assert "not submitted, not adopted" in text
    for word in ("adopted by", "accepted by the working group", "standard-track"):
        if word == "adopted by":
            assert "not adopted by any working group" in text
            continue
        assert word not in text
