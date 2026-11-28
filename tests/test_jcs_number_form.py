"""ECMAScript Number::toString pins for the JCS number rule (RFC 8785 S 4.2.4).

Why this file exists: on 2026-11-20 our Python canonicaliser and our own
JavaScript canonicaliser (`tools/verify-js`) disagreed on two shapes, and
both were in Python's favour of being wrong:

    value    our Python          our JavaScript   ECMAScript (and so JCS)
    1e-7     1e-07               1e-7             1e-7
    1e-6     1e-06               0.000001         0.000001

Both differences change the bytes, hence the hash, of a document containing
such a number, so a counterparty using a JCS implementation from another
language would compute a different digest for the same document. These pins
lock the ECMAScript forms in; if a future refactor goes back to `json.dumps`
for numbers, this file goes red.

The expected strings below are what `JSON.stringify` produces in Node for the
same values - that is the definition JCS points at, not a preference of ours.
"""
import sys
import unittest

sys.path.insert(0, ".")

from uibc_core.canonical import canonicalize  # noqa: E402


class TestECMAScriptNumberForm(unittest.TestCase):
    CASES = [
        # (value, expected serialised form)
        (1e-7, "1e-7"),
        (1.5e-7, "1.5e-7"),
        (1e-6, "0.000001"),
        (1e-5, "0.00001"),
        (0.002, "0.002"),
        (0.1, "0.1"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (1e30, "1e+30"),
        (1e-27, "1e-27"),
        (333333333.3333333, "333333333.3333333"),
        (-0.0, "0"),
        (1.0, "1"),
        (9007199254740991, "9007199254740991"),
    ]

    def test_shapes(self):
        for value, want in self.CASES:
            got = canonicalize({"x": value}).decode("utf-8")
            self.assertEqual(got, '{"x":%s}' % want, "value %r" % (value,))

    def test_no_zero_padded_exponent(self):
        """A zero-padded exponent ('1e-07') is the exact regression."""
        self.assertNotIn("e-0", canonicalize({"x": 1e-7}).decode("utf-8"))

    def test_number_inside_a_package_stays_a_fixed_point(self):
        doc = {"a": [1e-6, 1e21], "b": {"c": 1e-7}}
        once = canonicalize(doc)
        twice = canonicalize(__import__("json").loads(once.decode("utf-8")))
        self.assertEqual(once, twice)


class TestBeyondSafeRangeIsNotBeyondTheDouble(unittest.TestCase):
    """The gate is about precision, not size (2026-11-28).

    Atheris found the old behaviour in its first twenty-second run: `1e20`
    canonicalised to 21 digits, and re-reading those digits produced an `int`
    that the same gate then refused. The canonical form was not a fixpoint of
    the library that produced it. The gate now refuses only integers that no
    double equals - `2**53 + 1` among them - and serialises the rest the way
    ECMAScript serialises the double they equal.
    """

    CASES = [
        (1e17, "100000000000000000"),
        (1e20, "100000000000000000000"),
        (2 ** 60, "1152921504606846976"),
        (-1e20, "-100000000000000000000"),
        (2 ** 70, "1.1805916207174113e+21"),
    ]

    def test_forms(self):
        for value, want in self.CASES:
            self.assertEqual(canonicalize({"x": value}).decode("utf-8"),
                             '{"x":%s}' % want, "value %r" % (value,))

    def test_fixpoint(self):
        import json

        for value, _ in self.CASES:
            once = canonicalize({"x": value})
            twice = canonicalize(json.loads(once.decode("utf-8")))
            self.assertEqual(once, twice, "value %r" % (value,))

    def test_an_integer_no_double_equals_is_still_refused(self):
        for value in (2 ** 53 + 1, -(2 ** 53) - 1, 2 ** 53 + 3):
            with self.assertRaises(ValueError):
                canonicalize({"x": value})


if __name__ == "__main__":
    unittest.main()
