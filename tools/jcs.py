"""RFC 8785 (JCS) canonicalisation, written here so a digest can be recomputed
without anybody's library.

Scope, stated rather than implied
---------------------------------
This implements the parts the JSON Canonicalization Scheme actually specifies for
the values a conformance vector carries: strings escaped per RFC 8785 §3.2.2.2
(quote, backslash, the five short escapes, `\\u00xx` for the remaining C0 controls),
object keys ordered by UTF-16 code units, no insignificant whitespace, and
integers written as integers. Non-integer numbers are written with Python's
`repr` of the float, which is *not* ECMAScript's shortest round-trip form in
every case (1e21, -0, exponent style). Callers that hand it a float get a
`NonIntegral` error instead of a plausible-looking wrong digest; a vector that
needs float formatting has to be judged by somebody who reimplements ECMAScript's
number rules, and this module says so instead of pretending.
"""
import json


class NonIntegral(ValueError):
    """The value carries a number this module will not pretend to canonicalise."""


def _utf16(key):
    return key.encode("utf-16-be", "surrogatepass")


def _escape(s):
    out = []
    short = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f",
             "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for ch in s:
        if ch in short:
            out.append(short[ch])
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _number(v):
    if isinstance(v, bool):
        raise TypeError("bool is not a number")
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise NonIntegral("NaN and infinities are not JSON")
        if v == int(v) and abs(v) < 2 ** 53:
            return str(int(v))
        raise NonIntegral("non-integer number: this module does not do ECMAScript number formatting")
    raise TypeError(type(v))


def canonicalise(value):
    """The JCS text of a parsed JSON value."""
    if isinstance(value, dict):
        items = []
        for k in sorted(value, key=_utf16):
            if not isinstance(k, str):
                raise TypeError("object keys must be strings")
            items.append(_escape(k) + ":" + canonicalise(value[k]))
        return "{" + ",".join(items) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonicalise(x) for x in value) + "]"
    if isinstance(value, str):
        return _escape(value)
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return _number(value)


def canonicalise_text(text):
    """Parse a JSON document and return its JCS form, UTF-8 bytes and length."""
    data = json.loads(text)
    out = canonicalise(data)
    raw = out.encode("utf-8")
    return data, out, raw
