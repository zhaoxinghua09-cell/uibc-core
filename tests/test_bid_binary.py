"""RFC-011 (URP binary resolution): header, unit tree, and the parts the RFC leaves open.

Every test here either reproduces a stated rule or pins an *absence* - a field whose
byte width the RFC never gives, a bit order it never numbers, a signature unit it
never IDs. The absence tests exist so that the next reader cannot mistake "we decode
this" for "the RFC specifies this".
"""

import struct

import pytest

from uibc_core import bid_binary as BB


# ---------------------------------------------------------------- header

def test_header_round_trips_and_reports_names():
    body = b""
    header = BB.build_header(transaction_id=0x11223344, message_length=len(body))
    parsed = BB.parse_header(header)
    assert parsed.version == 1
    assert parsed.header_length == 16
    assert parsed.transaction_id == 0x11223344
    assert parsed.opcode == 0 and parsed.opcode_name == "QUERY"
    # §5.1.2.1.2: this table says 1 = success, unlike §4.2.5's 0 = success.
    assert parsed.reply_code == 1 and parsed.reply_name == "success"


def test_the_two_response_code_tables_are_kept_apart():
    assert BB.RCODES[1] == "success"
    assert BB.RCODES[11] == "authentication required"
    assert 11 not in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    with pytest.raises(KeyError):
        BB.RCODES[0]   # 0 exists in §4.2.5 and does not exist here


def test_flag_bits_follow_the_listed_order_and_that_is_an_assumption():
    assert BB.FLAG_BIT_ORDER_IS_AN_ASSUMPTION is True
    header = BB.build_header(transaction_id=1, message_length=0,
                             flags={"qr": 1, "ct": 1})
    parsed = BB.parse_header(header)
    assert parsed.flags["qr"] == 1 and parsed.flags["ct"] == 1
    assert parsed.flags["tc"] == 0


def test_opcode_is_four_bits_inside_the_flag_word():
    header = BB.build_header(transaction_id=1, message_length=0, opcode=2)
    parsed = BB.parse_header(header)
    assert parsed.opcode == 2 and parsed.opcode_name == "BID UPDATE"


def test_a_short_header_is_refused_and_a_lying_message_length_too():
    with pytest.raises(ValueError) as err:
        BB.parse_header(b"\x00" * 15)
    assert "16-byte" in str(err.value)

    header = BB.build_header(transaction_id=1, message_length=99)
    with pytest.raises(ValueError) as err:
        BB.parse_header(header)
    assert "messageLength=99" in str(err.value)


def test_header_length_is_counted_in_four_byte_units():
    # headerLength nibble 6 -> 24 bytes: 16 known + 8 option bytes.
    data = struct.pack(">BHBHHII", 0x16, 0, 0, 1, 1, 1, 0) + b"\xAA" * 8
    parsed = BB.parse_header(data)
    assert parsed.header_length == 24
    assert parsed.option_bytes == b"\xAA" * 8


# ---------------------------------------------------------------- units

def test_unit_tree_parses_nested_units_and_refuses_overruns():
    inner = BB.build_unit(0x2111, b"did:bid:efX#key-1") + BB.build_unit(0x2112, b"Ed25519")
    outer = BB.build_unit(0x2110, inner)
    units = BB.parse_units(outer)
    assert len(units) == 1
    kids = units[0].children()
    assert [k.id for k in kids] == [0x2111, 0x2112]

    with pytest.raises(ValueError) as err:
        BB.parse_units(struct.pack(">HH", 0x2111, 50) + b"abc")
    assert "claims 50 bytes" in str(err.value)

    with pytest.raises(ValueError) as err:
        BB.parse_units(b"\x21\x11")   # 2 bytes cannot even hold a unit header
    assert "unit header" in str(err.value)


# ---------------------------------------------------------------- document decode

def _doc_units():
    return (BB.build_unit(0x2101, b"1.1.0") +
            BB.build_unit(0x2102, b"did:bid:ef18F9AVK4SQLZPRrPkrVWwp9kbpdXHx") +
            BB.build_unit(0x2104, b"2021-06-24T09:10:09Z") +
            BB.build_unit(0x2110, BB.build_unit(0x2111, b"did:bid:efX#key-1") +
                                  BB.build_unit(0x2112, b"Ed25519") +
                                  BB.build_unit(0x2114, b"b06566" + b"11" * 32)) +
            BB.build_unit(0x2130, BB.build_unit(0x2131, b"#svc") +
                                  BB.build_unit(0x2132, b"DIDSubResolver") +
                                  BB.build_unit(0x2136, b"https://sub.example")) +
            BB.build_unit(0x3200, struct.pack(">I", 86400)))


def test_document_answer_decodes_into_the_json_shape():
    doc = BB.decode_document(BB.parse_units(_doc_units()))
    got = doc.fields
    assert got["version"] == "1.1.0"
    assert got["id"] == "did:bid:ef18F9AVK4SQLZPRrPkrVWwp9kbpdXHx"
    assert got["publicKey"]["type"] == "Ed25519"
    assert got["publicKey"]["id"] == "did:bid:efX#key-1"
    assert got["service"]["type"] == "DIDSubResolver"
    # ttl is Long and RFC-011 never says how wide a Long is: reported, not guessed.
    assert "extension.ttl" in doc.deferred
    assert "no byte width" in doc.deferred["extension.ttl"]
    assert "8600" not in repr(doc.fields)


def test_int_fields_are_deferred_with_their_raw_bytes_not_silently_decoded():
    units = BB.parse_units(BB.build_unit(0x3400, b"\x00\x00\x00\x69"))
    doc = BB.decode_document(units)
    assert "extension.type" in doc.deferred
    assert "00000069" in doc.deferred["extension.type"]


def test_unknown_units_are_listed_with_their_bytes_instead_of_dropped():
    units = BB.parse_units(BB.build_unit(0xBEEF, b"\x01\x02\x03"))
    doc = BB.decode_document(units)
    assert doc.unknown == [{"id": "0xbeef", "len": 3, "hex": "010203"}]
    assert doc.as_dict()["_unknown"][0]["id"] == "0xbeef"


def test_a_string_unit_that_is_not_utf8_is_an_error_not_a_replacement_char():
    units = BB.parse_units(BB.build_unit(0x2102, b"\xff\xfe"))
    with pytest.raises(ValueError) as err:
        BB.decode_document(units)
    assert "not valid UTF-8" in str(err.value)


def test_repeated_leaves_become_lists_which_is_the_only_multiplicity_signal():
    units = BB.parse_units(BB.build_unit(0x3100, b"did:bid:efA#k") +
                           BB.build_unit(0x3100, b"did:bid:efB#k"))
    doc = BB.decode_document(units)
    assert doc.fields["recovery"] == ["did:bid:efA#k", "did:bid:efB#k"]


def test_authentication_strings_are_disambiguated_from_the_document_container():
    # 0x2100 carries two meanings in the RFC. A payload that parses as units is a
    # container; a payload that does not is an authentication key id.
    doc = BB.decode_document(BB.parse_units(BB.build_unit(0x2100, b"did:bid:efX#key-1")))
    assert doc.fields["authentication"] == "did:bid:efX#key-1"
    container = BB.build_unit(0x2100, BB.build_unit(0x2101, b"1.1.0"))
    doc2 = BB.decode_document(BB.parse_units(container))
    assert doc2.fields["version"] == "1.1.0"


def test_the_colliding_ids_are_recorded_rather_than_resolved_silently():
    assert 0x2100 in BB.KNOWN_ID_COLLISIONS
    assert 0x3601 in BB.KNOWN_ID_COLLISIONS
    # same field, two spellings in two sections of the RFC
    assert BB.FIELD_TABLE[0x3610][0] == BB.FIELD_TABLE[0x3601][0] == "extension.acsns.acsn"


def test_error_answer_decodes_fully_because_both_its_fields_are_strings():
    units = BB.parse_units(BB.build_unit(0x2010,
                                         BB.build_unit(0x2102, b"did:bid:efX") +
                                         BB.build_unit(0x2011, "不存在".encode("utf-8"))))
    header, doc = BB.decode_message(BB.build_header(1, len(BB.build_unit(0x2010, units[0].payload)),
                                                    reply_code=6) +
                                    BB.build_unit(0x2010, units[0].payload))
    assert header.reply_name == "not found"
    assert doc.fields["errResponse"]["msg"] == "不存在"
    assert doc.deferred == {}


def test_full_message_round_trip_stops_at_the_signature_because_its_ids_are_unspecified():
    body = _doc_units()
    message = BB.build_header(7, len(body), reply_code=1) + body
    header, doc = BB.decode_message(message)
    assert header.message_length == len(body)
    assert doc.fields["version"] == "1.1.0"
    assert doc.signature_units_detectable is False   # §5.1.2.3 names but never numbers them

    # A signature block appended as units would land in `unknown`, not in a
    # "signature" key: that is the honest consequence of the missing IDs.
    signed_body = body + BB.build_unit(0x9001, b"\x00")
    signed = BB.build_header(7, len(signed_body), reply_code=1) + signed_body
    _, doc2 = BB.decode_message(signed)
    assert any(u["id"] == "0x9001" for u in doc2.unknown)
