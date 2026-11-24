"""The other document: the ten-arc agent identity code (`ACPs-spec-AIC-v02.01`).

Why this module exists
----------------------
GB/Z 185.2—2026 defines an eight-arc identity code with no checksum. `ACPs-spec-AIC-v02.01`,
the community specification the `aipmc-basic` crate declares alignment to, defines a
**ten-arc** code: the same OID prefix, then version, ARSP, vendor, ontology serial,
instance serial, and a four-character Base36 CRC-16/CCITT-FALSE trailer over arcs 1-9 plus
an ARSP-private salt.

The two documents are not variants of one another. Measured on 2026-11-24
(`docs/THIRD-PARTY-DIVERGENCE.md`): that implementation rejects the eight-arc shape, and
our GB/Z reader rejects the ten-arc shape. A parser that quietly accepted either as the
other would be inventing a crosswalk that neither document contains.

So this module reads the ten-arc form on **its own terms** and says what it cannot know.

What it can decide
------------------
Shape only: arc count, decimal arcs 1-4, Base36 on arcs 5-10, and the per-arc length
limits the specification states (version 1; ARSP 1-6; vendor 1-6; ontology 1-9;
instance 1-9; checksum exactly 4).

What it cannot decide
---------------------
* **The checksum.** The salt is per-ARSP and not published; the crate exposes only a
  default (`00 49 4F 41`) that its own specification example fails. A checksum we
  cannot recompute is not evidence about the code, so it is reported as
  `checksum: unverified (salt not published)` and never as a pass or a failure.
* **Allocation.** As with the national code, the highest state here is `INCONCLUSIVE`.

One consequence worth stating plainly: a code can carry a wrong checksum and still be
`INCONCLUSIVE` here, because we refuse to guess the salt. That is weaker than the
crate's `verify_checksum(salt)` call when the caller holds the salt, and we say so rather
than papering over it.
"""

from __future__ import annotations

import re

from .interop_result import result

__all__ = [
    "ACPS_SPEC",
    "ACPS_DEFAULT_PREFIX",
    "read_acps_code",
]

ACPS_DEFAULT_PREFIX = "1.2.156.3088"
ACPS_ALT_PREFIX_SEEN = "1.2.156.1234"  # the specification's own worked example

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

_METHOD = "ACPs-spec-AIC-v02.01 agent identity code (ten arcs)"
_SCOPE = "shape only (ACPs-spec-AIC-v02.01); checksum and allocation unverified"

ACPS_SPEC = {
    "spec": "ACPs-spec-AIC-v02.01",
    "arcs": ARCS,
    "default_prefix": ACPS_DEFAULT_PREFIX,
    "checksum": "CRC-16/CCITT-FALSE over arcs 1-9 ++ per-ARSP salt, Base36, four characters",
    "salt": "per-ARSP, not published (default example salt only)",
    "max_state": "INCONCLUSIVE",
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
            "%d arcs; ACPs-spec-AIC-v02.01 gives ten (four-arc OID prefix, then version, "
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
        prefix_note = "prefix %s is neither the default %s nor the specification example %s" % (
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
            "shape matches ACPs-spec-AIC-v02.01 (%s; %s; %s). This is not the national "
            "standard's eight-arc form and is not read as one. checksum: unverified "
            "(salt not published)."
            % (prefix_note, kind, "checksum arc present as %r" % parts[9])
        ),
        scope="shape only (ACPs-spec-AIC-v02.01); checksum unverified (salt not published); "
              "allocation unverified",
    )
