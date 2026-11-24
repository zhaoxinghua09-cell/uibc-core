"""Cross-implementation check: our CRC must equal a third-party implementation's CRC.

Oracle: `aipub-protocols` 0.0.3 (crates.io), the `protocols` library crate, via
`AicValidator::calculate_checksum`. Built and run 2026-11-24 on a Linux VM
(cargo 1.100.0, rustc 1.100.0), no patches, dependency pulled from crates.io.

The expectations below are that program's output, pasted verbatim. They are pinned here
so that agreement is a test rather than a sentence — and so that a future change to our
arithmetic fails loudly instead of quietly diverging from the ecosystem.

What this proves and what it does not: it proves the two implementations compute the
same arc 10 for the same body and salt, including lowercase input, arbitrary salt
lengths and both ends of the segment-length ranges. It does not prove either of them
matches the text — that is `tests/test_acps_spec_conformance.py`, against the document's
own worked example.
"""

import pytest

from uibc_core.acps_identity_code import acps_checksum

# (body of arcs 1-9, salt, checksum printed by aipub-protocols 0.0.3)
ORACLE = [
    ("1.2.156.3088.1.1.34C2.478BDF.3GF546", b"\x12\x34", "0JU4"),
    ("1.2.156.3088.1.1.34c2.478bdf.3gf546", b"\x12\x34", "0JU4"),
    ("1.2.156.3088.1.0", b"\x12\x34", "1D1B"),
    ("1.2.156.3088.1.1", b"\x12\x34", "14WF"),
    ("1.2.156.3088.1.1.1.1.1", b"\x12\x34", "0H91"),
    ("1.2.156.3088.1.1.1.1.0", b"\x12\x34", "0J1H"),
    ("1.2.156.3088.1.ZZZZZZ.ZZZZZZ.ZZZZZZZZZ.ZZZZZZZZZ", b"\x12\x34", "1DOK"),
    ("1.2.156.3088.1.1.34C2.478BDF.3GF546", bytes.fromhex("00ff"), "0KT6"),
    ("1.2.156.3088.1.1.34C2.478BDF.3GF546", bytes.fromhex("DEADBEEF"), "0CVT"),
    ("1.2.156.3088.1.1.34C2.478BDF.3GF546", bytes.fromhex("00112233445566778899AABBCCDDEEFF"), "02AL"),
    ("1.2.156.1234.1.1.34C2.478BDF.3GF546", b"\x12\x34", "1AAG"),
    ("1.2.156.9999.1.1.34C2.478BDF.3GF546", b"\x12\x34", "145G"),
    ("1.2.156.3088.2.1.34C2.478BDF.3GF546", b"\x12\x34", "0C4P"),
    ("1.2.156.3088.1.1.34C2.478BDF.000000000", b"\x12\x34", "04JM"),
    ("1.2.156.3088.1.1.34C2.478BDF.3GF54", b"\x12\x34", "0HFJ"),
    ("1.2.156.3088.1.1.34C2.478BDF.3GF5467", b"\x12\x34", "1CW3"),
]


@pytest.mark.parametrize("body,salt,expected", ORACLE)
def test_our_checksum_equals_the_third_party_checksum(body, salt, expected):
    assert acps_checksum(body, salt) == expected


def test_the_oracle_agrees_on_the_documents_own_example():
    # Same fixture the text works through in §4.1; a third implementation reaching the
    # same four characters is the reason we trust our own arithmetic here.
    body, salt, expected = ORACLE[0]
    assert body.endswith("3GF546") and salt == b"\x12\x34" and expected == "0JU4"
