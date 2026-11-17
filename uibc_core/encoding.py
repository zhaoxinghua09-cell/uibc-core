"""Strict base64: the three ways a decoder silently accepts what is not base64.

The AER-1 corpus marks four classes must-fail that Python's base64 module
happily accepts:

  * pad bits set       - "AB==" decodes, but the last 4 bits are non-zero, so
                         two different byte strings share one encoding. Standard
                         decoders ignore the bits; a strict reader must not.
  * missing padding    - "AB" (length % 4 != 0) is accepted by urlsafe_b64decode
                         after padding, so "unpadded input" has no single form.
  * not base64 at all  - a stray "-" or "\\n" inside, or a character outside the
                         alphabet, is dropped by permissive decoders.

None of these is a signature problem - they are encoding problems - so the
check belongs with S11 (bytes) and not with S6 (seals). "Signature verifies"
plus "two decoders disagree about the bytes" can be true at the same time.
"""

import base64
import binascii

STD_ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                   "abcdefghijklmnopqrstuvwxyz"
                   "0123456789+/=")
URL_ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                   "abcdefghijklmnopqrstuvwxyz"
                   "0123456789-_=")


def problems(value, urlsafe=False):
    """Return a list of strictness problems; empty means canonical base64."""
    out = []
    if not isinstance(value, str):
        return ["not a string"]
    if value == "":
        return ["empty"]
    alphabet = URL_ALPHABET if urlsafe else STD_ALPHABET

    for ch in value:
        if ch not in alphabet:
            out.append("character %r is outside the base64 alphabet" % ch)
            return out
    if "\n" in value or "\r" in value or " " in value:
        out.append("whitespace inside base64")
        return out

    padded = value.endswith("=")
    core = value.rstrip("=")
    if len(core) % 4 in (1,):
        out.append("length %d cannot be base64 (4n or 4n+2,4n+3)" % len(value))
        return out
    if padded:
        if len(value) % 4 != 0:
            out.append("padded length is not a multiple of 4")
            return out
        if value.endswith("==") is False and value.endswith("=") is False:
            out.append("malformed padding")
            return out
    else:
        if len(value) % 4 != 0:
            out.append("unpadded input (length mod 4 = %d); canonical base64 "
                       "requires padding" % (len(value) % 4))
            return out

    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as e:
        out.append("decoder rejected it (%s)" % e)
        return out

    # pad-bit test: re-encoding the decoded bytes must give back exactly this
    # string. If it does not, the input carried bits the decode threw away.
    canonical = base64.b64encode(raw).decode("ascii")
    if value.endswith("=") and canonical != value:
        out.append("non-canonical: re-encode gives %r (pad bits are not zero)" % canonical)
    if value.replace("-", "+").replace("_", "/") != value and not urlsafe:
        out.append("urlsafe characters in standard base64")
    return out


def is_strict(value, urlsafe=False):
    return not problems(value, urlsafe=urlsafe)
