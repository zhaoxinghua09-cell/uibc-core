"""Agent identity code: GB/Z 185.2—2026, read strictly.

What this module is
-------------------
A parser and a shape checker for the national agent identity code, nothing more.
It answers one question — *is this string a well-formed identity code under
GB/Z 185.2—2026?* — and it refuses to answer the other question, *is this code
real?*, because answering that requires two things we do not have:

  * an issuer (the standard hands allocation to an "agent identity registration
    service provider", never to a verifier), and
  * a resolution endpoint (the standard defines none).

So the highest state this module can ever return is `INCONCLUSIVE`. There is no
path from here to `VERIFIED`, by construction: `_verdict` has no branch that
produces it. A verifier that returned `VERIFIED` on a code it merely parsed
would be reporting "this identity is real" on the strength of "this string is
shaped correctly", which is exactly the failure mode this repository exists to
refuse.

The standard, clause by clause, as implemented
----------------------------------------------
5.1  Structure: five parts, dot separated — OID prefix, version, registration
     service provider, registration requester, custom serial number. Each part
     uses 0-9 and A-Z; letters are case-insensitive; no spaces. So the wire form
     has eight OID arcs: four for the prefix plus one per part.
5.2  Prefix is fixed at `1.2.156.3088` (1 = ISO, 2 = member body, 156 = China,
     3088 = agent node).
5.3  Version: exactly one character, range `1`..`Z` (35 values). The current
     document fixes the version at `1`. Anything else is reserved, not invalid —
     it is a version this build has no rule for, hence `UNSUPPORTED`.
5.4  Registration service provider: 1..6 characters.
5.5  Registration requester: 1..6 characters.
5.6  Custom serial number: defined by the provider; the standard recommends at
     most 9 characters for the ontology serial and at most 10 for the instance
     serial. The published structure keeps both inside *one* part, so the part
     is bounded at 9 + 10 = 19 characters. That bound is a derivation, and it is
     marked as one — it is not a number the standard prints.
6    Management: (a) retired provider codes are never reallocated, (b) a
     core-function change should trigger a new ontology serial, (c) concurrent
     versions get different serials, (d) one code maps to one agent, (e) the
     provider owns its serial space. Only (d) is checkable from outside, and
     this module exposes it as `duplicates()`, which reports but never decides.

What this module deliberately does not do
-----------------------------------------
* It does not issue, mint, or allocate codes. Allocation belongs to a
  registration service provider (5.3 / 5.4), full stop.
* It does not verify a checksum. A public third-party implementation
  (`aipmc-basic`, MIT, Rust, crates.io) reads the code as **ten** arcs with a
  four-character Base36 CRC-16/CCITT-FALSE trailer. Neither the extra arc nor the
  CRC appears in GB/Z 185.2—2026 as published, and that crate's salt is not
  public, so the checksum is not reproducible by us. We therefore *recognise*
  that profile (see `detect_profile`) and say so plainly, but we never treat its
  CRC as a fact about the code's validity.
* It does not resolve the code to an endpoint. No clause defines one.
"""

from __future__ import annotations

import re

from .interop_result import result

__all__ = [
    "PREFIX",
    "CURRENT_VERSION",
    "SPEC",
    "parse_agent_code",
    "detect_profile",
    "duplicates",
]

PREFIX = "1.2.156.3088"
PREFIX_ARCS = ("1", "2", "156", "3088")
CURRENT_VERSION = "1"

# 5.3: range 1..Z, i.e. 35 one-character versions, letters case-insensitive.
_VERSIONS = set("123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")

PROVIDER_MAX = 6        # 5.4
REQUESTER_MAX = 6       # 5.5
ONTOLOGY_SERIAL_MAX = 9   # 5.6 b, recommended
INSTANCE_SERIAL_MAX = 10  # 5.6 c, recommended
SEQUENCE_MAX = ONTOLOGY_SERIAL_MAX + INSTANCE_SERIAL_MAX  # 19, derived (see docstring)

ARC = re.compile(r"^[0-9A-Z]+$")

SPEC = {
    "standard": "GB/Z 185.2-2026",
    "title": "Artificial intelligence - Agent interconnection - Part 2: Identity code",
    "prefix": PREFIX,
    "arcs": 8,
    "version_chars": 1,
    "provider_chars": (1, PROVIDER_MAX),
    "requester_chars": (1, REQUESTER_MAX),
    "sequence_chars": (1, SEQUENCE_MAX),
    "case": "insensitive, normalised to upper",
    "issuer": "agent identity registration service provider (not a verifier)",
    "max_state": "INCONCLUSIVE",
}


def _normalise(raw):
    """Strip, then uppercase. 5.1 says letters are case-insensitive."""
    return raw.strip().upper()


def _bad(detail, subject):
    """INVALID, with a subject that is always non-empty.

    `result()` refuses to build a document that names nothing, so an empty or
    non-string input is named by what was there rather than by what was not:
    `<empty>`, or `<NoneType>`.
    """
    return result("INVALID", subject or "<empty>", method=_METHOD, detail=detail,
                  scope="shape only (GB/Z 185.2-2026 5.1-5.6)")


_METHOD = "GB/Z 185.2-2026 agent identity code"


def _verdict():
    """The one state a shape check may legitimately reach."""
    return "INCONCLUSIVE"


def detect_profile(code):
    """Which reading of the arcs a string is written in, or None.

    `gbz185.2`  eight arcs: prefix + version + provider + requester + sequence.
    `aip-acps`  ten arcs: the same five, then separate ontology and instance
                serials, then a four-character checksum — a third-party reading
                (aipmc-basic) that adds a CRC the national standard does not
                define. Recognised so we can say what we are looking at; not
                endorsed, and its checksum is not verifiable by us.
    """
    if not isinstance(code, str):
        return None
    parts = _normalise(code).split(".")
    if len(parts) == 8:
        return "gbz185.2"
    if len(parts) == 10:
        return "aip-acps"
    return None


def parse_agent_code(code):
    """Check the shape of one identity code and return a seven-state result.

    Never returns VERIFIED: see the module docstring. `detail` always says why
    the state is what it is, in a sentence another implementation can compare
    against.
    """
    if not isinstance(code, str):
        return _bad("not a string: %r" % (type(code).__name__,),
                    "<%s>" % type(code).__name__)
    norm = _normalise(code)
    if not norm:
        return _bad("empty string: no identity code supplied", "<empty>")

    profile = detect_profile(norm)
    if profile == "aip-acps":
        # Ten arcs is a third-party profile. We can still judge it as eight arcs
        # plus a trailer, but we will not silently accept the trailer.
        parts = norm.split(".")
        trailer = parts[9]
        return result(
            "INVALID", norm, method=_METHOD,
            detail=("ten arcs: this is the aip-acps reading (separate ontology and "
                    "instance serials plus a four-character checksum). The checksum and "
                    "the extra arc are not in GB/Z 185.2-2026 as published, and its salt "
                    "is not public, so we neither verify nor accept it."),
            scope="shape only (GB/Z 185.2-2026 5.1-5.6); trailer %r unverified" % trailer,
        )

    parts = norm.split(".")
    if len(parts) != 8:
        return result(
            "INVALID", norm, method=_METHOD,
            detail=("%d arcs; GB/Z 185.2-2026 5.1 gives five dot-separated parts over a "
                    "four-arc prefix, i.e. eight arcs" % len(parts)),
            scope="shape only (GB/Z 185.2-2026 5.1-5.6)",
        )

    if tuple(parts[:4]) != PREFIX_ARCS:
        return result(
            "INVALID", norm, method=_METHOD,
            detail=("prefix %r is not %s (5.2 fixes it)" % (".".join(parts[:4]), PREFIX)),
            scope="shape only (GB/Z 185.2-2026 5.1-5.6)",
        )

    for name, part in (("version", parts[4]), ("provider", parts[5]),
                       ("requester", parts[6]), ("sequence", parts[7])):
        if not ARC.match(part):
            return result(
                "INVALID", norm, method=_METHOD,
                detail=("%s arc %r contains something other than 0-9/A-Z (5.1)" % (name, part)),
                scope="shape only (GB/Z 185.2-2026 5.1-5.6)",
            )

    version = parts[4]
    if len(version) != 1:
        return result(
            "INVALID", norm, method=_METHOD,
            detail=("version arc %r is %d characters; 5.3 allows exactly one"
                    % (version, len(version))),
            scope="shape only (GB/Z 185.2-2026 5.1-5.6)",
        )
    if version not in _VERSIONS:
        # Unreachable given the charset rule above, kept so the range is explicit.
        return result("INVALID", norm, method=_METHOD,
                      detail="version %r outside 1..Z (5.3)" % version,
                      scope="shape only (GB/Z 185.2-2026 5.1-5.6)")
    if version != CURRENT_VERSION:
        return result(
            "UNSUPPORTED", norm, method=_METHOD,
            detail=("version %r is inside the 5.3 range but reserved; this document fixes "
                    "version %s, and this build has no rule for another version"
                    % (version, CURRENT_VERSION)),
            scope="shape only (GB/Z 185.2-2026 5.1-5.6)",
        )

    if len(parts[5]) > PROVIDER_MAX:
        return result("INVALID", norm, method=_METHOD,
                      detail=("provider arc %r is %d characters; 5.4 allows 1..%d"
                              % (parts[5], len(parts[5]), PROVIDER_MAX)),
                      scope="shape only (GB/Z 185.2-2026 5.1-5.6)")
    if len(parts[6]) > REQUESTER_MAX:
        return result("INVALID", norm, method=_METHOD,
                      detail=("requester arc %r is %d characters; 5.5 allows 1..%d"
                              % (parts[6], len(parts[6]), REQUESTER_MAX)),
                      scope="shape only (GB/Z 185.2-2026 5.1-5.6)")
    if len(parts[7]) > SEQUENCE_MAX:
        return result("INVALID", norm, method=_METHOD,
                      detail=("sequence arc is %d characters; 5.6 recommends at most %d "
                              "ontology + %d instance characters inside one part, so this "
                              "build bounds it at %d (a derivation, not a printed number)"
                              % (len(parts[7]), ONTOLOGY_SERIAL_MAX, INSTANCE_SERIAL_MAX,
                                 SEQUENCE_MAX)),
                      scope="shape only (GB/Z 185.2-2026 5.1-5.6)")

    return result(
        _verdict(), norm, method=_METHOD,
        detail=("shape matches GB/Z 185.2-2026 5.1-5.6 (version 1, provider %s, requester %s, "
                "sequence %d chars). Not verified: the issuer is a registration service "
                "provider and the standard defines no resolution endpoint, so nothing here "
                "can say the code was ever allocated."
                % (parts[5], parts[6], len(parts[7]))),
        scope="shape only (GB/Z 185.2-2026 5.1-5.6); allocation unverified",
    )


def duplicates(codes):
    """Report codes that appear more than once (management requirement 6d).

    One code must map to one agent, so a repeat is a contradiction. This reports;
    it does not decide, because two identical strings may legitimately appear in
    two different evidence bundles for the same agent.
    """
    seen = {}
    dups = {}
    for c in codes:
        if not isinstance(c, str):
            continue
        n = _normalise(c)
        seen[n] = seen.get(n, 0) + 1
    for n, k in seen.items():
        if k > 1:
            dups[n] = k
    return dups
