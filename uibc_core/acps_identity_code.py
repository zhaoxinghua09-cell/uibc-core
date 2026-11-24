"""The other document: the ten-arc agent identity code (`ACPs-spec-AIC-v02.02`).

Why this module exists
----------------------
GB/Z 185.2—2026 defines an eight-arc identity code with no checksum. `ACPs-spec-AIC-v02.02`,
the community specification (the `aipmc-basic` crate declares alignment to the earlier
v02.01; the text itself now publishes v02.02), defines a
**ten-arc** code: the same OID prefix, then version, ARSP, vendor, ontology serial,
instance serial, and a four-character Base36 CRC-16/CCITT-FALSE trailer over arcs 1-9 plus
an ARSP-private salt.

The two documents are not variants of one another. Measured on 2026-11-24
(`docs/THIRD-PARTY-DIVERGENCE.md`): that implementation rejects the eight-arc shape, and
our GB/Z reader rejects the ten-arc shape. A parser that quietly accepted either as the
other would be inventing a crosswalk that neither document contains.

So this module reads the ten-arc form on **its own terms** and says what it cannot know.

The text is now in hand, not inferred
------------------------------------
`ACPs-spec-AIC-v02.02` is public: `ACPs-community/acps-specs/02-ACPs-spec-AIC/ACPs-spec-AIC.md`
on AtomGit (`aip-pub`). It states the ten arcs, their per-arc value ranges, and the checksum
algorithm in full — including a worked example with a published salt:

    1.2.156.3088.1.1.34C2.478BDF.3GF546  +  SALT = 0x12 0x34
    → CRC-16/CCITT-FALSE = 0x646C → Base36 four chars = 0JU4
    → 1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4

Our implementation reproduces that example byte for byte, and `0xFFFF → "1EKF"` matches the
upper bound the document states for arc 10. So the checksum is **decidable** whenever the
caller holds the salt — and that is exactly the condition the document sets: the salt is
per-ARSP, at least two bytes, and not published.

What it can decide
------------------
* Shape: arc count, decimal arcs 1-4, Base36 on arcs 5-10, per-arc length limits
  (version 1; ARSP 1-6; vendor 1-6; ontology 1-9; instance 1-9; checksum exactly 4).
* The checksum, **only** through `verify_acps_code(code, salt)` with a salt the caller
  supplies. Without a salt the module reports `INCONCLUSIVE` and says why; it never
  guesses, and never reports a checksum as passing because it could not compute it.

What it still cannot decide
---------------------------
* **Allocation.** Whether an ARSP actually issued this code is a registry question, not
  a string question. `VERIFIED` here means "the checksum matches the salt you gave me",
  and the `scope` field says so.
"""

from __future__ import annotations

import hashlib
import re

from .interop_result import result

__all__ = [
    "ACPS_SPEC",
    "ACPS_DEFAULT_PREFIX",
    "MIN_SALT_BYTES",
    "acps_checksum",
    "base36_fixed",
    "crc16_ccitt_false",
    "read_acps_code",
    "verify_acps_code",
]

ACPS_DEFAULT_PREFIX = "1.2.156.3088"
ACPS_ALT_PREFIX_SEEN = "1.2.156.1234"  # seen in aipmc-basic docs, not in the specification text

ARCS = 10
_LENGTHS = {
    5: (1, 1),   # version
    6: (1, 6),   # ARSP
    7: (1, 6),   # vendor
    8: (1, 9),   # ontology serial
    9: (1, 9),   # instance serial
    10: (4, 4),  # checksum, exactly four
}
_NAMES = {
    5: "version",
    6: "ARSP",
    7: "vendor",
    8: "ontology serial",
    9: "instance serial",
    10: "checksum",
}

BASE36 = re.compile(r"^[0-9A-Z]+$")
DIGITS = re.compile(r"^[0-9]+$")

_METHOD = "ACPs-spec-AIC-v02.02 agent identity code (ten arcs)"
_SCOPE = "shape only (ACPs-spec-AIC-v02.02); checksum not checked (no salt supplied); allocation unverified"

ACPS_SPEC = {
    "spec": "ACPs-spec-AIC-v02.02",
    "arcs": ARCS,
    "default_prefix": ACPS_DEFAULT_PREFIX,
    "checksum": "CRC-16/CCITT-FALSE over arcs 1-9 ++ per-ARSP salt, Base36, four characters",
    "salt": "per-ARSP, >=2 bytes, not published; the document's worked example uses 0x1234",
    "max_state": "VERIFIED when a checksum is verified against a supplied salt; INCONCLUSIVE otherwise",
}


def _bad(detail, subject):
    return result("INVALID", subject or "<empty>", method=_METHOD, detail=detail,
                  scope=_SCOPE)


def read_acps_code(code):
    """Read one ten-arc code. Never returns VERIFIED, and never judges the checksum.

    Returns a seven-state `result()` document whose `detail` names the first
    violated rule, so another implementation can compare against it sentence by
    sentence instead of by score.
    """
    if not isinstance(code, str):
        return _bad("not a string: %r" % (type(code).__name__,),
                    "<%s>" % type(code).__name__)
    norm = code.strip().upper()
    if not norm:
        return _bad("empty string: no identity code supplied", "<empty>")

    parts = norm.split(".")
    if len(parts) != ARCS:
        return _bad(
            "%d arcs; ACPs-spec-AIC-v02.02 gives ten (four-arc OID prefix, then version, "
            "ARSP, vendor, ontology serial, instance serial, checksum). An eight-arc code is "
            "the GB/Z 185.2-2026 shape and belongs to a different reader." % len(parts),
            norm,
        )

    if len(parts) < 4 or not all(DIGITS.match(p) for p in parts[:4]):
        return _bad("arcs 1-4 must be decimal digits, got %r" % ".".join(parts[:4]), norm)

    prefix = ".".join(parts[:4])
    if prefix not in (ACPS_DEFAULT_PREFIX, ACPS_ALT_PREFIX_SEEN):
        # Not refused: the prefix is an OID branch, and other branches are legitimate.
        # Recorded so a reader pinning one prefix cannot quietly pass a foreign one.
        prefix_note = "prefix %s is neither the default %s nor the alternate %s" % (
            prefix, ACPS_DEFAULT_PREFIX, ACPS_ALT_PREFIX_SEEN)
    else:
        prefix_note = "prefix %s" % prefix

    for arc, (lo, hi) in sorted(_LENGTHS.items()):
        part = parts[arc - 1]
        if not BASE36.match(part):
            return _bad("%s arc %r is not Base36 (0-9/A-Z)" % (_NAMES[arc], part), norm)
        if not (lo <= len(part) <= hi):
            return _bad(
                "%s arc %r is %d characters; the specification allows %d..%d"
                % (_NAMES[arc], part, len(part), lo, hi),
                norm,
            )

    instance = parts[8]
    kind = "ontology AIC (instance serial all zeros)" if set(instance) == {"0"} else "entity AIC"

    return result(
        "INCONCLUSIVE", norm, method=_METHOD,
        detail=(
            "shape matches ACPs-spec-AIC-v02.02 (%s; %s; %s). This is not the national "
            "standard's eight-arc form and is not read as one. checksum: not checked here "
            "(call verify_acps_code with the ARSP's salt to decide it)."
            % (prefix_note, kind, "checksum arc present as %r" % parts[9])
        ),
        scope="shape only (ACPs-spec-AIC-v02.02); checksum not checked (no salt supplied); "
              "allocation unverified",
    )


# --- checksum: decidable only with the ARSP's salt -------------------------

BASE36_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MIN_SALT_BYTES = 2  # ACPs-spec-AIC-v02.02 §4.1 step (2): "长度不少于 2 字节"


def crc16_ccitt_false(data):
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, xorout 0.

    Kept as a plain loop rather than a table so the sixteen-bit arithmetic is
    auditable line by line against §4.1 steps (3)-(6) of the document.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def base36_fixed(value, width=4):
    """Base36 with left zero padding; the document fixes arc 10 at four characters."""
    if value < 0:
        raise ValueError("value must be non-negative")
    digits = []
    n = value
    while n:
        digits.append(BASE36_ALPHABET[n % 36])
        n //= 36
    out = "".join(reversed(digits)) or "0"
    return out.rjust(width, "0")


def acps_checksum(body_1_9, salt):
    """Recompute arc 10 for a body of arcs 1-9 and a salt of at least two bytes."""
    if not isinstance(salt, (bytes, bytearray)):
        raise TypeError("salt must be bytes, got %s" % type(salt).__name__)
    if len(salt) < MIN_SALT_BYTES:
        raise ValueError(
            "salt is %d bytes; ACPs-spec-AIC-v02.02 §4.1 requires at least %d"
            % (len(salt), MIN_SALT_BYTES)
        )
    normalized = body_1_9.strip().upper()
    return base36_fixed(crc16_ccitt_false(normalized.encode("ascii") + bytes(salt)), 4)


def verify_acps_code(code, salt=None):
    """Read a ten-arc code and, if a salt is supplied, decide the checksum.

    Three outcomes, and each says what it does *not* cover:

    * `VERIFIED`   — checksum matches the caller-supplied salt. Allocation unverified.
    * `INVALID`    — checksum mismatch under that salt, or the shape is broken.
    * `INCONCLUSIVE` — no salt supplied (or a salt the document forbids). We do not
      invent one and we do not call an uncomputed checksum a pass.

    The salt is the ARSP's, not ours: this function decides "does this code carry the
    checksum that this salt produces", not "did a registry issue this code".
    """
    read = read_acps_code(code)
    if read.get("state") != "INCONCLUSIVE":
        return read

    norm = code.strip().upper()
    parts = norm.split(".")
    body, carried = ".".join(parts[:9]), parts[9]

    if salt is None:
        return result(
            "INCONCLUSIVE", norm, method=_METHOD,
            detail=(
                "shape matches ACPs-spec-AIC-v02.02 and the checksum was NOT checked: no salt "
                "supplied. The document keeps the salt inside each ARSP (§4.1), so a reader "
                "without it cannot decide arc 10 — and will not pretend to."
            ),
            scope="shape only (ACPs-spec-AIC-v02.02); checksum not checked (no salt supplied); "
                  "allocation unverified",
        )

    try:
        expected = acps_checksum(body, salt)
    except (TypeError, ValueError) as exc:
        return result(
            "INCONCLUSIVE", norm, method=_METHOD,
            detail="checksum NOT checked: salt refused by the document's own rule (%s)" % exc,
            scope="shape only (ACPs-spec-AIC-v02.02); checksum not checked (salt refused); "
                  "allocation unverified",
        )

    if expected == carried:
        return result(
            "VERIFIED", norm, method=_METHOD,
            evidence=[{
                "id": "acps-arc10:%s" % expected,
                "type": "checksum-computation",
                "issuer": "caller-supplied salt (ACPs-spec-AIC-v02.02 §4.1)",
                "digest": "sha256:%s" % hashlib.sha256(
                    body.encode("ascii") + bytes(salt)).hexdigest(),
                "method": _METHOD,
                "scope": "arcs 1-9 ++ supplied salt -> CRC-16/CCITT-FALSE -> Base36",
            }],
            detail=(
                "checksum verified: arcs 1-9 with the supplied salt give %r, which is what "
                "arc 10 carries." % expected
            ),
            scope="checksum verified against caller-supplied salt; allocation unverified "
                  "(issuance is a registry question, not a string question)",
        )

    return result(
        "INVALID", norm, method=_METHOD,
        detail=(
            "checksum mismatch: arcs 1-9 with the supplied salt give %r, but arc 10 carries "
            "%r. Either the code is corrupt, or the salt belongs to a different ARSP."
            % (expected, carried)
        ),
        scope="checksum verified against caller-supplied salt; allocation unverified",
    )

