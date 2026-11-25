# -*- coding: utf-8 -*-
"""SM2 pinned to GM/T 0003.5-2012's worked example (Annex A), not to itself.

Every expected value below is copied from the standard: curve parameters, ZA, e,
the point kG, r, s. If our arithmetic differed from the standard anywhere - curve
equation, ZA layout, the (1+d)^-1 step, the mod-n reductions - one of these would
disagree. This is the vector problem for SM2 solved by quoting someone else's page.

Source: GM/T 0003.5-2012 / GB/T 32918.5-2017, Annex A.2.
"""
import pytest

from uibc_core import sm2

D = 0x3945208F7B2144B13F36E38AC6D39F95889393692860B51A42FB81EF4DF7C5B8
PX = 0x09F9DF311E5421A150DD7D161E4BC5C672179FAD1833FC076BB08FF356F35020
PY = 0xCCEA490CE26775A52DC6EA718CC1AA600AED05FBF35E084A6632F6072DA9AD13
MESSAGE = b"message digest"          # ASCII, as the annex states
ZA_HEX = "b2e14c5c79c6df5b85f4fe7ed8db7a262b9da7e07ccb0ea9f4747b8ccda8a4f3"
E_HEX = "f0b43e94ba45accaace692ed534382eb17e6ab5a19ce7b31f4486fdfc0d28640"
K = 0x59276E27D506861A16680F3AD9C02DCCEF3CC1FA3CDBE4CE6D54B80DEAC1BC21
KX_HEX = "04ebfc718e8d1798620432268e77feb6415e2ede0e073c0f4f640ecd2e149a73"
R = 0xF5A03B0648D2C4630EEAC513E1BB81A15944DA3827D5B74143AC7EACEEE720B3
S = 0xB1B6AA29DF212FD8763182BC0D421CA1BB9038FD1F7F42D4840B69C485BBC1AA


def test_curve_parameters_satisfy_the_curve_equation():
    assert sm2.is_on_curve(sm2.GX, sm2.GY)
    assert sm2.is_on_curve(PX, PY)


def test_public_key_from_the_private_key_matches_the_standard():
    assert sm2.public_key(D) == (PX, PY)


def test_za_matches_the_standard():
    """ZA is where most implementations silently differ: ENTL, ID, field order."""
    assert sm2.za(PX, PY).hex() == ZA_HEX


def test_e_matches_the_standard():
    assert sm2.digest(MESSAGE, PX, PY).to_bytes(32, "big").hex() == E_HEX


def test_k_times_g_matches_the_standard():
    assert sm2.mul(K, (sm2.GX, sm2.GY))[0].to_bytes(32, "big").hex() == KX_HEX


def test_signing_with_the_standard_k_reproduces_r_and_s():
    r, s = sm2.sign(D, MESSAGE, k=K, px=PX, py=PY)
    assert r == R and s == S


def test_verification_accepts_the_standard_signature():
    assert sm2.verify(PX, PY, MESSAGE, R, S) is True


def test_a_changed_message_is_rejected():
    assert sm2.verify(PX, PY, b"message digesT", R, S) is False


def test_a_changed_r_is_rejected():
    assert sm2.verify(PX, PY, MESSAGE, R ^ 1, S) is False


def test_out_of_range_r_or_s_is_an_answer_not_an_error():
    assert sm2.verify(PX, PY, MESSAGE, 0, S) is False
    assert sm2.verify(PX, PY, MESSAGE, R, sm2.N) is False


def test_round_trip_with_a_random_k():
    r, s = sm2.sign(D, b"another message")
    assert sm2.verify(PX, PY, b"another message", r, s) is True


def test_a_non_key_point_is_a_structural_error():
    with pytest.raises(sm2.SM2Error):
        sm2.verify(1, 1, MESSAGE, R, S)


def test_public_key_hex_reads_the_bif_prefix():
    body = PX.to_bytes(32, "big") + PY.to_bytes(32, "big")
    assert sm2.parse_public_key_hex("b06566" + body.hex()) == (PX, PY)
    assert sm2.parse_public_key_hex("b0" + body.hex()) == (PX, PY)
    assert sm2.parse_public_key_hex(body.hex()) == (PX, PY)


def test_signature_parsing_and_length():
    sig = R.to_bytes(32, "big") + S.to_bytes(32, "big")
    assert sm2.parse_signature(sig) == (R, S)
    with pytest.raises(sm2.SM2Error):
        sm2.parse_signature(sig[:63])


def test_a_different_id_changes_the_verdict():
    """ID is an input, not a decoration - proving it is used rather than assumed."""
    r, s = sm2.sign(D, MESSAGE, id_bytes=b"other-id-1234567")
    assert sm2.verify(PX, PY, MESSAGE, r, s, id_bytes=b"other-id-1234567") is True
    assert sm2.verify(PX, PY, MESSAGE, r, s) is False


# ------------------------------------------------- BID document level (§5 + SM2)
import json
import pathlib

from uibc_core import bid_protocol as B

SIGNED = json.loads((pathlib.Path(__file__).resolve().parent.parent
                     / "fixtures" / "bid" / "signed_document.json").read_text(encoding="utf-8"))


def sm2_document(private_key=D):
    """The signed fixture, re-keyed to SM2 and signed over the same JCS bytes."""
    doc = json.loads(json.dumps(SIGNED))
    body = PX.to_bytes(32, "big") + PY.to_bytes(32, "big")
    key_id = doc["authentication"][0]
    doc["publicKey"][0] = {"controller": doc["id"], "id": key_id,
                           "publicKeyHex": "b06566" + body.hex(), "type": "SM2"}
    unsigned = {k: v for k, v in doc.items() if k != "proof"}
    r, s = sm2.sign(private_key, B.signing_bytes(unsigned), px=PX, py=PY)
    doc["proof"] = {"creator": key_id,
                    "signatureValue": B.base58_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")),
                    "type": "SM2Signature"}
    return doc


def test_an_sm2_bid_document_verifies_and_says_which_id_was_used():
    ok, reason = B.verify_bid_document(sm2_document())
    assert ok, reason
    assert "SM2" in reason and "1234567812345678" in reason


def test_tampering_after_an_sm2_signature_is_caught():
    doc = sm2_document()
    doc["created"] = "2021-06-24T09:10:10Z"
    ok, reason = B.verify_bid_document(doc)
    assert not ok and "does not verify" in reason


def test_an_sm2_key_that_is_not_on_the_curve_is_rejected_not_accepted():
    doc = sm2_document()
    doc["publicKey"][0]["publicKeyHex"] = "b06566" + ("11" * 64)
    ok, reason = B.verify_bid_document(doc)
    assert not ok and "not a point on the curve" in reason
