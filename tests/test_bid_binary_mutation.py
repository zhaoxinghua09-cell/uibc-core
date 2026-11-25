"""The bit-flip probe as a test: every bit must be accounted for.

`tools/mutate_bid_binary.py` flips one bit at a time in a valid message and sorts
each mutant into rejected / changed / blind. Run by hand it is a report; here it
is a contract, so that a change which quietly widens the blind set fails CI.

The blind set is not a defect to be removed - a format without a signature cannot
detect tampering - but it must be *known*: those bits are what an attacker can
change for free, and every one of them has to be a bit the header declares
reserved.
"""

import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "mutate_bid_binary", os.path.join(ROOT, "tools", "mutate_bid_binary.py"))
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


@pytest.fixture(scope="module")
def result():
    return M.probe(M.sample_message())


def test_every_bit_of_the_message_is_classified_once(result):
    assert result["total"] == result["rejected"] + result["changed"] + len(result["blind"])


def test_no_bit_outside_the_reserved_header_bits_is_blind(result):
    """A blind body bit would mean a document field the decoder throws away."""
    assert set(result["blind_fields"]) <= {"flag", "unUsed"}, result["blind_fields"]


def test_the_blind_set_is_exactly_the_bits_the_header_declares_reserved(result):
    """Derived from the header layout, not typed in: the flag word is message bits
    8..23 (flag bit 15 at index 8), qr..ct claim bits 15..10, opCode bits 9..6,
    so bits 5..0 are unassigned; byte 3 is `unUsed` outright (§5.1.2.1). Those
    fourteen bits are the whole blind set - nothing in the body is dead."""
    from uibc_core.bid_binary import _FLAG_BITS, _OPCODE_SHIFT
    used = {bit for _name, bit in _FLAG_BITS} | set(range(_OPCODE_SHIFT, _OPCODE_SHIFT + 4))
    unnamed = {8 + (15 - bit) for bit in range(16) if bit not in used}
    expected = unnamed | set(range(24, 32))
    assert len(expected) == 14
    assert set(result["blind"]) == expected


def test_the_probe_actually_reaches_the_body(result):
    """If the sample were only a header, the good numbers above would be vacuous."""
    assert result["total"] >= 8 * 100          # our sample message is ~196 bytes
    body_blind = [b for b in result["blind"] if b // 8 >= 16]
    assert body_blind == []


def test_a_flipped_key_container_is_caught_not_ignored():
    """The bug the probe found: renaming publicKey's container decoded identically."""
    msg = M.sample_message()
    hlen = 16
    body = msg[hlen:]
    assert b"\x21\x10" in body
    at = hlen + body.index(b"\x21\x10")
    mutated = msg[:at] + b"\x21\x00" + msg[at + 2:]   # publicKey -> document wrapper
    with pytest.raises(ValueError, match="0x2110"):
        M._decode(mutated)
