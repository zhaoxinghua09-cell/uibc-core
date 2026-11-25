"""Codec tests: the encoder is the decoder's inverse, and every inference is a switch.

These tests are written so that a reader who believes RFC-011 settles something
this module treats as an assumption can flip the corresponding parameter here and
watch the expectation move - rather than take the module's word for it.
"""

import random
import struct

import pytest

from uibc_core.bid_binary import (
    ACSNS_SPELLINGS,
    ASSUMPTIONS,
    FLAG_ORDER_CHOICES,
    Header,
    Unit,
    build_header,
    build_unit,
    decode_document,
    decode_message,
    encode_document,
    encode_message,
    encode_units,
    parse_header,
    parse_units,
)


def _doc_fields(units, widths=None):
    return decode_document(units, integer_widths=widths).as_dict()


# ---------------------------------------------------------------- header

def test_header_roundtrips_byte_for_byte():
    raw = build_header(transaction_id=0x01020304, message_length=12, opcode=2,
                       reply_code=6, message_id=1, flags={"qr": 1, "ct": 1}, version=2) + b"\x00" * 12
    header = parse_header(raw)
    rebuilt = build_header(transaction_id=header.transaction_id,
                           message_length=header.message_length, opcode=header.opcode,
                           reply_code=header.reply_code, message_id=header.message_id,
                           flags=header.flags, version=header.version)
    assert rebuilt == raw[:16]
    assert header.version == 2 and header.opcode == 2 and header.reply_code == 6


def test_header_option_padding_is_carried_verbatim():
    raw = encode_message([], 1, option_bytes=b"\x01\x00\x00\x00")  # one option type, padded to 4 bytes
    header = parse_header(raw)
    assert header.header_length == 20
    assert header.option_bytes == b"\x01\x00\x00\x00"


def test_flag_bit_order_is_a_real_switch_not_a_comment():
    """Flip the assumption and the same bytes must read differently."""
    raw = build_header(7, 0, flags={"qr": 1}, flag_bit_order="msb")
    assert parse_header(raw, flag_bit_order="msb").flags["qr"] == 1
    assert parse_header(raw, flag_bit_order="lsb").flags != parse_header(raw, flag_bit_order="msb").flags
    assert parse_header(raw, flag_bit_order="lsb").flags["qr"] == 0


def test_unknown_flag_bit_order_is_rejected():
    with pytest.raises(ValueError, match="flag_bit_order"):
        parse_header(build_header(1, 0), flag_bit_order="middle")


# ---------------------------------------------------------------- unit layer

def test_unit_layer_roundtrips_byte_for_byte():
    units = [Unit(0x2100, build_unit(0x2101, b"1.0.0")), Unit(0x2102, b"did:bid:ef00")]
    raw = encode_units(units)
    assert parse_units(raw) == units
    assert encode_units(parse_units(raw)) == raw


def test_unit_layer_preserves_non_ascending_order():
    """Order is information at this layer; the codec must not sort it away."""
    units = [Unit(0x2102, b"b"), Unit(0x2101, b"a")]
    raw = encode_units(units)
    assert parse_units(raw) == units
    assert encode_units(parse_units(raw)) == raw


def test_unit_layer_rejects_a_wide_id():
    with pytest.raises(ValueError, match="2 bytes"):
        encode_units([Unit(0x10000, b"")])


def test_unit_layer_random_roundtrip():
    rng = random.Random(20261125)
    for _ in range(200):
        units = [Unit(rng.randrange(0x10000), bytes(rng.randrange(0, 40))) for _ in range(rng.randrange(0, 6))]
        raw = encode_units(units)
        assert parse_units(raw) == units
        assert encode_units(parse_units(raw)) == raw


# ---------------------------------------------------------------- message layer

def test_message_roundtrips_through_decode_message():
    units = [Unit(0x2100, build_unit(0x2101, b"1.0.0"))]
    raw = encode_message(units, transaction_id=9, reply_code=1, message_id=1)
    header, doc = decode_message(raw)
    assert header.transaction_id == 9
    assert doc.fields["version"] == "1.0.0"
    assert encode_message(units, transaction_id=9) == raw


def test_message_length_field_matches_the_body_it_encodes():
    units = [Unit(0x2102, b"did:bid:ef" + b"0" * 20)]
    raw = encode_message(units, transaction_id=1)
    assert struct.unpack(">I", raw[12:16])[0] == len(encode_units(units))


def test_header_length_counts_the_option_bytes():
    raw = encode_message([], 5, option_bytes=b"\x02\x00\x00\x00")
    header = parse_header(raw)
    assert header.header_length == 20


def test_unaligned_option_bytes_are_rejected():
    with pytest.raises(ValueError, match="multiple of 4"):
        encode_message([], 1, option_bytes=b"\x01")


# ---------------------------------------------------------------- document layer

def test_document_layer_is_idempotent_under_decode_encode():
    units = [Unit(0x2100, build_unit(0x2101, b"1.0.0") + build_unit(0x2102, b"did:bid:ef00"))]
    once = _doc_fields(units)
    again = _doc_fields(encode_document(once))
    assert again == once
    # and canonically stable from then on
    assert encode_units(encode_document(again)) == encode_units(encode_document(once))


def test_repeated_leaf_becomes_a_list_and_survives_the_roundtrip():
    units = [Unit(0x2111, b"k1"), Unit(0x2111, b"k2")]
    fields = _doc_fields(units)
    assert fields["publicKey"]["id"] == ["k1", "k2"]
    back = _doc_fields(encode_document(fields))
    assert back["publicKey"]["id"] == ["k1", "k2"]


def test_nested_container_roundtrip():
    inner = build_unit(0x3510, b"k") + build_unit(0x3520, b"d")
    units = [Unit(0x3000, build_unit(0x3500, inner))]
    fields = _doc_fields(units)
    assert fields["extension"]["attributes"] == {"key": "k", "desc": "d"}
    assert _doc_fields(encode_document(fields)) == fields


def test_proof_is_encoded_as_top_level_not_as_extension_child():
    """`proof` exists at 0x2140 and at 0x3560; a name-keyed map would confuse them."""
    units = [Unit(0x2140, build_unit(0x2141, b"did:bid:ef00#key-1"))]
    assert encode_units(encode_document(_doc_fields(units))) == encode_units(units)
    nested = [Unit(0x3000, build_unit(0x3500, build_unit(0x3560, build_unit(0x3561, b"c"))))]
    assert _doc_fields(nested)["extension"]["attributes"]["proof"]["creator"] == "c"
    assert encode_units(encode_document(_doc_fields(nested))) == encode_units(nested)


def test_authentication_key_id_list_uses_the_colliding_container_id():
    units = [Unit(0x2100, b"did:bid:ef00#key-1"), Unit(0x2100, b"did:bid:ef00#key-2")]
    fields = _doc_fields(units)
    assert fields["authentication"] == ["did:bid:ef00#key-1", "did:bid:ef00#key-2"]
    assert _doc_fields(encode_document(fields)) == fields


def test_recovery_string_container_roundtrip():
    units = [Unit(0x3100, b"did:bid:ef00#recovery")]
    fields = _doc_fields(units)
    assert fields["recovery"] == "did:bid:ef00#recovery"
    assert encode_units(encode_document(fields)) == encode_units(units)


def test_acsns_spelling_is_selectable_and_both_decode_alike():
    """§5.2.1.1.2 says 0x3610/0x3620, §5.2.1.4.2 says 0x3601/0x3602. Encode picks one."""
    a = encode_document({"extension": {"acsns": {"acsn": "x", "acsnAddress": "y"}}},
                        acsns_spelling="3610")
    b = encode_document({"extension": {"acsns": {"acsn": "x", "acsnAddress": "y"}}},
                        acsns_spelling="3601")
    assert a != b
    assert _doc_fields(a) == _doc_fields(b) == {"extension": {"acsns": {"acsn": "x", "acsnAddress": "y"}}}
    with pytest.raises(ValueError, match="acsns_spelling"):
        encode_document({}, acsns_spelling="9999")


def test_unknown_unit_is_reported_not_dropped_and_survives_as_opaque():
    units = [Unit(0x2F00, b"\xde\xad\xbe\xef")]
    fields = _doc_fields(units)
    assert fields["_unknown"][0]["id"] == "0x2f00"
    assert fields["_unknown"][0]["hex"] == "deadbeef"


# ---------------------------------------------------------------- deferred integers

def test_integer_without_a_declared_width_is_deferred_with_its_raw_bytes():
    units = [Unit(0x3200, b"\x00\x00\x00\x05")]
    doc = decode_document(units)
    assert "extension.ttl" in doc.deferred
    assert doc.deferred["extension.ttl"].endswith("raw=00000005")


def test_integer_width_supplied_by_the_caller_decodes():
    units = [Unit(0x3200, b"\x00\x00\x00\x05"), Unit(0x2137, b"\x1f\x90")]
    doc = decode_document(units, integer_widths={"long": 4, "int": 2})
    assert doc.integers["extension.ttl"] == 5
    assert doc.integers["service.port"] == 8080
    assert not doc.deferred


def test_wrong_width_fails_loudly_instead_of_misreading():
    with pytest.raises(ValueError, match="declared long=8 bytes but carries 4"):
        decode_document([Unit(0x3200, b"\x00\x00\x00\x05")], integer_widths={"long": 8})


def test_encoding_an_integer_without_a_width_says_which_parameter_to_pass():
    with pytest.raises(ValueError, match="integer_widths"):
        encode_document({"extension": {"ttl": 5}})


def test_integer_encode_decode_roundtrip():
    widths = {"int": 2, "long": 4}
    fields = {"extension": {"ttl": 3600, "type": 2, "acsns": {"acsn": "a"}}}
    units = encode_document(fields, integer_widths=widths)
    doc = decode_document(units, integer_widths=widths)
    assert doc.integers["extension.ttl"] == 3600
    assert doc.integers["extension.type"] == 2
    assert _doc_fields(encode_document(doc.as_dict(), integer_widths=widths), widths) == doc.as_dict()


def test_negative_or_oversized_integer_is_rejected():
    with pytest.raises(ValueError, match="unsigned"):
        encode_document({"extension": {"ttl": -1}}, integer_widths={"long": 4})
    with pytest.raises(ValueError, match="unsigned"):
        encode_document({"extension": {"ttl": 1 << 32}}, integer_widths={"long": 4})


# ---------------------------------------------------------------- hostility

def test_unknown_field_path_cannot_be_invented_into_a_unit():
    with pytest.raises(ValueError, match="no RFC-011 unit ID"):
        encode_document({"publicKey": {"madeUp": "x"}})


def test_random_bytes_never_crash_the_decoder():
    """A network-facing decoder must fail as ValueError, never as a bare crash."""
    rng = random.Random(42)
    for _ in range(2000):
        data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 64)))
        try:
            decode_message(data)
        except ValueError:
            pass


def test_random_byte_strings_that_parse_are_stable_under_re_encode():
    """Property: for any byte string that decodes, decode(encode(decode(b))) == decode(b)."""
    rng = random.Random(7)
    widths = {"int": 2, "long": 4}
    checked = 0
    ids = [0x2101, 0x2102, 0x2111, 0x2137, 0x3200]
    for _ in range(500):
        units = [Unit(uid, bytes(rng.randrange(32) for _ in range(
            widths["int"] if uid == 0x2137 else widths["long"] if uid == 0x3200
            else rng.randrange(0, 8))))
                 for uid in [rng.choice(ids) for _ in range(rng.randrange(0, 5))]]
        units = [u for u in units
                 if not (u.id in (0x2101, 0x2102, 0x2111) and _is_bad_utf8(u.payload))]
        try:
            first = _doc_fields(units, widths)
        except ValueError:
            continue
        assert _doc_fields(encode_document(first, integer_widths=widths), widths) == first
        checked += 1
    assert checked > 50


def _is_bad_utf8(payload: bytes) -> bool:
    try:
        payload.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


# ---------------------------------------------------------------- the registry itself

def test_every_assumption_names_its_parameter_and_is_either_flippable_or_marked():
    allowed = {"flippable", "caller-supplied", "heuristic", "not-implemented"}
    assert set(ASSUMPTIONS) == {
        "flag_bit_order", "integer_widths", "acsns_spelling",
        "bid_document_collision", "fragment_reassembly", "signature_unit_ids",
    }
    for name, item in ASSUMPTIONS.items():
        assert item["status"] in allowed, name
        assert item["gap"] and item["choice"], name


def test_the_two_flippable_assumptions_change_observable_output():
    # flag order
    raw = build_header(1, 0, flags={"qr": 1}, flag_bit_order="msb")
    assert parse_header(raw, flag_bit_order="lsb").flags != parse_header(raw, flag_bit_order="msb").flags
    # acsns spelling
    fields = {"extension": {"acsns": {"acsn": "x"}}}
    assert encode_units(encode_document(fields, acsns_spelling="3610")) != \
           encode_units(encode_document(fields, acsns_spelling="3601"))
    assert set(FLAG_ORDER_CHOICES) == {"msb", "lsb"}
    assert set(ACSNS_SPELLINGS) == {"3610", "3601"}
