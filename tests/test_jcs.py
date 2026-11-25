"""tools/jcs.py against the cases RFC 8785 actually pins down for these values."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import jcs  # noqa: E402


def test_key_order_is_utf16_code_units():
    # A surrogate pair's first unit (0xD83D) sorts below U+FF61, and above U+007A;
    # code-point order would have put the astral key last.
    text = json.dumps({"😀": 1, "\uff61": 2, "z": 3})
    assert jcs.canonicalise(json.loads(text)) == '{"z":3,"😀":1,"｡":2}'


def test_no_insignificant_whitespace():
    assert jcs.canonicalise_text('{ "b" : 1 , "a" : [ 1 , 2 ] }')[2] == b'{"a":[1,2],"b":1}'


def test_short_escapes_and_c0_controls():
    out = jcs.canonicalise({"s": 'a"b\\c\nd\x01'})
    assert out == '{"s":"a\\"b\\\\c\\nd\\u0001"}'


def test_lone_surrogate_is_carried_not_mangled():
    # JCS writes a lone surrogate through; it does not substitute U+FFFD.
    src = json.loads('"\\ud800"')
    assert jcs.canonicalise(src) == '"\ud800"'


def test_integers_and_beyond_2_53():
    assert jcs.canonicalise({"n": 1234567890123456789}) == '{"n":1234567890123456789}'


def test_non_integral_numbers_are_refused_rather_than_guessed():
    for bad in (1.5, 1e30, -0.25):
        try:
            jcs.canonicalise({"n": bad})
        except jcs.NonIntegral:
            continue
        raise AssertionError("canonicalised %r without saying it cannot" % (bad,))


def test_the_smallest_vector_from_the_competitor_corpus():
    # CAN-P-astral-values carries this text and canonical_len 17.
    text = '{\n "k": "\U0001f5dd \U0001f600"\n}\n'
    _data, out, raw = jcs.canonicalise_text(text)
    assert out == '{"k":"\U0001f5dd \U0001f600"}'
    assert len(raw) == 17
