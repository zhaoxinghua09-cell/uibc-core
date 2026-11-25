"""§4.3 binary resolution (RFC-011, URP): the envelope and the unit tree, decoded.

Why this module exists
----------------------
《星火·链网BID协议》 §4.3 says only: "binary resolution protocol: see
<https://github.com/caict-4iot-dev/bif-rfcs/tree/main/RFCs/3-ACCEPTED>". That
directory contains a single ``.gitkeep`` - the link has been dead since the
protocol document was written. The actual text is one folder over, in
``RFCs/4-ADOPTED/星火链网RFC-011：星火链网BID标识二进制解析协议.md`` (commit
pinned in ``docs/BINARY-PROTOCOL.md``). So "we cannot implement §4.3 because the
text is missing" was a misreading of the repository, not a property of the
protocol.

What is implemented here, and what deliberately is not
------------------------------------------------------
Implemented: the 16-byte header (version / headerLength / flag bits / opcode /
replyCode / messageID / transactionID / messageLength / optional option bytes),
the unit tree (2-byte ID + 2-byte length + payload, payload may itself be units),
and the *string* fields of the document answer plus the error answer.

Not implemented, because RFC-011 does not say enough to implement it without
guessing:

  * integer widths. Fields typed ``Int`` and ``Long`` (``ttl``, ``extension.type``,
    ``service.port``, ``acsns.acsn``...) have no byte width anywhere in the RFC.
    The one field whose width *is* given is a ``Short, 2 bytes`` inside a request
    payload. Rather than pick 4/8 and call it a spec, such units are kept as raw
    bytes and reported in ``deferred`` with the field path and the reason. A caller
    who knows the width can decode them; we will not assert a document equals its
    JSON form when part of it was guessed.
  * the message-signature unit IDs. §5.1.2.3 describes the signature as three
    units (``creator`` / ``digestAlgorithm`` / ``signatureValue``) and never gives
    their IDs, so a signature blob cannot be located inside a message. Messages
    that carry one are parsed structurally, and ``signature_units_detectable`` is
    False.
  * §4.3's transport is UDP with fragmentation (§5.1.3): reassembly by ``messageID``
    is described but the first-packet index and the end condition are not stated.
    No reassembly here.

The module is a *codec*, not just a decoder: :func:`encode_units` and
:func:`encode_document` are the inverses of :func:`parse_units` and
:func:`decode_document`. The unit layer round-trips byte for byte; the document
layer round-trips semantically (field order is canonicalised, because the unit
model carries no ordering information a dict could keep). Every inference the
RFC does not settle is listed in ``ASSUMPTIONS`` and wired to a real parameter,
so a reader who disagrees flips the switch and reruns - nothing here has to be
taken on trust.

A leaf must sit in the container its field table path says it belongs to: decoding
checks the container prefix and refuses a mismatch. Without that check a mutated
container ID decodes to an identical document - the field paths are absolute, so
the nesting would be unobservable. That hole was found by flipping bits
(``tools/mutate_bid_binary.py``), not by reading the RFC.

Two ID collisions in the RFC itself are recorded in ``KNOWN_ID_COLLISIONS`` and
left visible rather than resolved: ``0x2100`` is ``bidDocument`` *and*
``bidDocument.authentication``; the AC-number children are ``0x3601/0x3602`` in
§5.2.1.4.2 and ``0x3610/0x3620`` in §5.2.1.1.2. The decoder resolves them by
context (container vs leaf position), which is a guess about the author's intent,
and says so here instead of hiding it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- header

HEADER_MIN = 16          # §5.1.2.1: "最小16个字节"
HEADER_UNIT = 4          # headerLength is counted in 4-byte units ("单位是4字节")

OPCODES = {0: "QUERY", 1: "REVERSE QUERY", 2: "BID UPDATE"}

# §5.1.2.1.2. Note this is NOT the §4.2.5 list: it has 1=success (not 0), adds 11,
# and uses 255 as "look in the option field". Two documents, two tables - both kept.
RCODES = {
    1: "success", 2: "error", 3: "server too busy", 4: "protocol error",
    5: "operation not supported", 6: "not found", 7: "server not response",
    8: "field not found", 9: "verify failed", 10: "nonexistent chain code info",
    11: "authentication required", 255: "rcode in extension option",
}

# Bit positions are NOT given by RFC-011: §5.1.2.1 lists the flag's fields in order
# (QR, TC, RD, DT, TR, CT, opCode) but never numbers them. This module assumes the
# list order maps to the most-significant bits first. An implementation that numbers
# them from the least-significant side would read the same bytes differently, and
# nothing in the RFC settles it - recorded here instead of presented as fact.
FLAG_BIT_ORDER_IS_AN_ASSUMPTION = True
_FLAG_BITS = (("qr", 15), ("tc", 14), ("rd", 13), ("dt", 12), ("tr", 11), ("ct", 10))
_OPCODE_SHIFT = 6


@dataclass(frozen=True)
class Header:
    version: int
    header_length: int          # bytes
    flags: Dict[str, int]
    opcode: int
    reply_code: int
    message_id: int
    transaction_id: int
    message_length: int
    option_bytes: bytes

    @property
    def opcode_name(self) -> str:
        return OPCODES.get(self.opcode, "unknown(%d)" % self.opcode)

    @property
    def reply_name(self) -> str:
        return RCODES.get(self.reply_code, "unknown(%d)" % self.reply_code)


def parse_header(data: bytes, *, flag_bit_order: str = "msb") -> Header:
    if len(data) < HEADER_MIN:
        raise ValueError("message shorter than the 16-byte minimum header: %d" % len(data))
    version = data[0] >> 4
    header_units = data[0] & 0x0F
    header_length = header_units * HEADER_UNIT
    if header_length < HEADER_MIN or header_length > len(data):
        raise ValueError("headerLength=%d units (%d bytes) is out of range for a %d-byte message"
                         % (header_units, header_length, len(data)))
    if flag_bit_order not in FLAG_ORDER_CHOICES:
        raise ValueError("flag_bit_order must be one of %r, got %r"
                         % (FLAG_ORDER_CHOICES, flag_bit_order))
    flag = struct.unpack(">H", data[1:3])[0]
    flags = _flag_bits_from(flag, flag_bit_order)
    opcode = (flag >> _OPCODE_SHIFT) & 0x0F
    # data[3] is unUsed (§5.1.2.1); deliberately not interpreted.
    reply_code, message_id = struct.unpack(">HH", data[4:8])
    transaction_id, message_length = struct.unpack(">II", data[8:16])
    options = data[HEADER_MIN:header_length]
    remaining = len(data) - header_length
    if message_length > remaining:
        raise ValueError("messageLength=%d but only %d bytes follow the header"
                         % (message_length, remaining))
    return Header(version=version, header_length=header_length, flags=flags, opcode=opcode,
                  reply_code=reply_code, message_id=message_id,
                  transaction_id=transaction_id, message_length=message_length,
                  option_bytes=options)


def build_header(transaction_id: int, message_length: int, opcode: int = 0,
                 reply_code: int = 1, message_id: int = 1, flags: Optional[Dict[str, int]] = None,
                 version: int = 1, *, flag_bit_order: str = "msb") -> bytes:
    """The inverse of :func:`parse_header`, used to build test vectors.

    Only a 16-byte header (no option field) is produced: the RFC gives no option
    type whose payload length it defines, so appending one would be invention.
    """
    if flag_bit_order not in FLAG_ORDER_CHOICES:
        raise ValueError("flag_bit_order must be one of %r, got %r"
                         % (FLAG_ORDER_CHOICES, flag_bit_order))
    flag = 0
    for index, (name, _msb_bit) in enumerate(_FLAG_BITS):
        if flags and flags.get(name):
            flag |= 1 << _flag_bit(index, flag_bit_order)
    flag |= (opcode & 0x0F) << _OPCODE_SHIFT
    first = ((version & 0x0F) << 4) | (HEADER_MIN // HEADER_UNIT)
    return struct.pack(">BHBHHII", first, flag, 0, reply_code, message_id,
                       transaction_id, message_length)


# ---------------------------------------------------------------- units

@dataclass
class Unit:
    id: int
    payload: bytes

    def children(self) -> List["Unit"]:
        return parse_units(self.payload)


def parse_units(data: bytes) -> List[Unit]:
    """Flat sequence of (ID 2B, length 2B, payload). Raises on any overrun."""
    units: List[Unit] = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 4:
            raise ValueError("trailing %d byte(s) cannot hold a unit header" % (len(data) - offset))
        uid, length = struct.unpack(">HH", data[offset:offset + 4])
        offset += 4
        if offset + length > len(data):
            raise ValueError("unit 0x%04x claims %d bytes, only %d left" % (uid, length, len(data) - offset))
        units.append(Unit(uid, data[offset:offset + length]))
        offset += length
    return units


def build_unit(uid: int, payload: bytes) -> bytes:
    return struct.pack(">HH", uid, len(payload)) + payload


# ---------------------------------------------------------------- document answer

STRING, INT, LONG, UNIT = "string", "int", "long", "unit"

# §5.2.1.1.2, with §5.2.1.4.2's AC-number children listed separately because the
# RFC gives two spellings for them (see KNOWN_ID_COLLISIONS).
FIELD_TABLE: Dict[int, Tuple[str, str]] = {
    0x2101: ("version", STRING),
    0x2102: ("id", STRING),
    0x2104: ("created", STRING),
    0x2105: ("updated", STRING),
    0x2111: ("publicKey.id", STRING),
    0x2112: ("publicKey.type", STRING),
    0x2113: ("publicKey.controller", STRING),
    0x2114: ("publicKey.publicKeyHex", STRING),
    0x2121: ("alsoKnownAs.type", INT),
    0x2122: ("alsoKnownAs.id", STRING),
    0x2131: ("service.id", STRING),
    0x2132: ("service.type", STRING),
    0x2133: ("service.version", STRING),
    0x2134: ("service.protocol", INT),
    0x2135: ("service.serverType", INT),
    0x2136: ("service.serviceEndpoint", STRING),
    0x2137: ("service.port", INT),
    0x2141: ("proof.creator", STRING),
    0x2142: ("proof.signatureValue", STRING),
    0x3200: ("extension.ttl", LONG),
    0x3310: ("extension.delegateSign.signer", STRING),
    0x3320: ("extension.delegateSign.signatureValue", STRING),
    0x3400: ("extension.type", INT),
    0x3510: ("extension.attributes.key", STRING),
    0x3520: ("extension.attributes.desc", STRING),
    0x3530: ("extension.attributes.encrypt", INT),
    0x3540: ("extension.attributes.format", STRING),
    0x3550: ("extension.attributes.value", STRING),
    0x3561: ("extension.attributes.proof.creator", STRING),
    0x3562: ("extension.attributes.proof.signatureValue", STRING),
    0x3610: ("extension.acsns.acsn", STRING),
    0x3620: ("extension.acsns.acsnAddress", STRING),
    0x3601: ("extension.acsns.acsn", STRING),        # §5.2.1.4.2 spelling
    0x3602: ("extension.acsns.acsnAddress", STRING),  # §5.2.1.4.2 spelling
    0x3710: ("extension.verifiableCredentials.id", STRING),
    0x3720: ("extension.verifiableCredentials.type", INT),
    0x2011: ("errResponse.msg", STRING),
}

# container IDs -> key under which their children are collected
CONTAINERS: Dict[int, str] = {
    0x2100: "bidDocument",          # also authentication, see collisions
    0x2110: "publicKey",
    0x2120: "alsoKnownAs",
    0x2130: "service",
    0x2140: "proof",
    0x2010: "errResponse",
    0x2200: "bidDocumentField",
    0x3000: "extension",
    0x3100: "recovery",
    0x3300: "delegateSign",
    0x3500: "attributes",
    0x3560: "proof",
    0x3600: "acsns",
    0x3700: "verifiableCredentials",
}

KNOWN_ID_COLLISIONS = {
    0x2100: "bidDocument (container) and bidDocument.authentication (list) share this ID",
    0x3601: "§5.2.1.4.2 spells the AC number 0x3601/0x3602; §5.2.1.1.2 spells 0x3610/0x3620",
}

# Int/Long fields whose byte width RFC-011 never states.
DEFERRED_TYPES = (INT, LONG)


@dataclass
class DecodedDocument:
    fields: Dict[str, Any] = field(default_factory=dict)
    deferred: Dict[str, str] = field(default_factory=dict)   # path -> reason
    integers: Dict[str, int] = field(default_factory=dict)   # only with integer_widths
    misplaced: Dict[str, str] = field(default_factory=dict)  # lenient mode only
    unknown: List[Dict[str, Any]] = field(default_factory=list)
    signature_units_detectable: bool = False

    def as_dict(self) -> Dict[str, Any]:
        out = dict(self.fields)
        out.update(self.integers)
        if self.deferred:
            out["_deferred"] = dict(self.deferred)
        if self.misplaced:
            out["_misplaced"] = dict(self.misplaced)
        if self.unknown:
            out["_unknown"] = list(self.unknown)
        return out


def _put(target: Dict[str, Any], path: str, value: Any):
    parts = path.split(".")
    node = target
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError("path %r collides with a scalar already decoded" % path)
    leaf = parts[-1]
    existing = node.get(leaf)
    if existing is None:
        node[leaf] = value
    elif isinstance(existing, list):
        existing.append(value)
    else:
        node[leaf] = [existing, value]


def decode_document(units: List[Unit], into: Optional[DecodedDocument] = None, *,
                    integer_widths: Optional[Dict[str, int]] = None,
                    prefix: str = "", container_id: Optional[int] = None,
                    depth: int = 0, strict_placement: bool = True) -> DecodedDocument:
    """Decode the unit tree of a document (or error) answer.

    ``FIELD_TABLE`` paths are absolute (``publicKey.id``), so containers need no
    prefix: they recurse into the same dict and the leaf writes its documented path.
    Multiplicity comes from repetition only - the unit model has no other way to say
    "many" - so a repeated leaf becomes a list. Repeated containers are merged
    field-wise (two ``publicKey`` containers produce ``publicKey.id`` as a list of
    two), because nothing in the RFC marks the boundary between two instances.
    """
    doc = into or DecodedDocument()
    for unit in units:
        key = CONTAINERS.get(unit.id)
        if key is not None and unit.id != 0x2100:
            # Most containers hold units, but `recovery` and `authentication` hold
            # plain key-id strings. A string does not parse as a unit sequence, so
            # a payload that fails to parse is decoded as one string at the
            # container's own path - and repetition turns it into a list.
            children = None
            if unit.payload:
                try:
                    children = unit.children()
                except ValueError:
                    children = None
            if children:
                # bidDocument (0x2100) is the document wrapper: its children are the
                # top-level fields, which have no path prefix. Every other container
                # holds one named subtree.
                expected = "" if unit.id == 0x2100 else CONTAINER_BY_ID.get(unit.id, "")
                decode_document(children, doc, integer_widths=integer_widths,
                                prefix=expected, container_id=unit.id, depth=depth + 1,
                                strict_placement=strict_placement)
            else:
                _put(doc.fields, key, unit.payload.decode("utf-8", "strict"))
            continue
        if unit.id == 0x2100:
            # Container by position (bidDocument) *and* `authentication` (a list of
            # key ids) - the RFC's own collision. Discriminator: a key-id string
            # does not parse as a unit sequence, so a payload that fails to parse
            # as units is decoded as one authentication string. A heuristic about
            # intent, stated rather than hidden.
            children = None
            if unit.payload:
                try:
                    children = unit.children()
                except ValueError:
                    children = None
            if children:
                # The document wrapper exists once, at the top. If one appears inside
                # another container, its leaves would be re-parented to the top level
                # and the document would come back identical - a real blind spot the
                # bit-flip probe found (publicKey 0x2110 flipped to 0x2100).
                if depth:
                    raise ValueError("nested bidDocument wrapper (0x2100) at depth %d: "
                                     "the document wrapper belongs at the top level only"
                                     % depth)
                decode_document(children, doc, integer_widths=integer_widths, prefix="",
                                container_id=unit.id, depth=depth + 1,
                                strict_placement=strict_placement)
            else:
                _put(doc.fields, "authentication", unit.payload.decode("utf-8", "strict"))
            continue
        _decode_leaf(unit, doc, integer_widths, prefix, container_id,
                     CONTAINER_EXTRA_PATHS.get(container_id, frozenset()),
                     strict_placement)
    return doc


def _decode_leaf(unit: Unit, doc: DecodedDocument,
                 integer_widths: Optional[Dict[str, int]] = None, prefix: str = "",
                 container_id: Optional[int] = None,
                 extra_paths: frozenset = frozenset(),
                 strict_placement: bool = True):
    entry = FIELD_TABLE.get(unit.id)
    if entry is None:
        doc.unknown.append({"id": "0x%04x" % unit.id, "len": len(unit.payload),
                            "hex": unit.payload[:32].hex()})
        return
    path, kind = entry
    wants = documented_parent(path)
    placed_right = (container_id == wants) or (wants is None and container_id in (None, 0x2100))
    if not placed_right and path not in extra_paths and not strict_placement:
        doc.misplaced[path] = ("unit 0x%04x is documented under 0x%s but sits in 0x%s"
                               % (unit.id, "----" if wants is None else "%04x" % wants,
                                  "----" if container_id is None else "%04x" % container_id))
    elif not placed_right and path not in extra_paths:
        raise ValueError("unit 0x%04x is documented as %r under 0x%s but sits in 0x%s; "
                         "the container ID is wrong or the unit was moved"
                         % (unit.id, path, "----" if wants is None else "%04x" % wants,
                            "----" if container_id is None else "%04x" % container_id))
    if kind == STRING:
        try:
            _put(doc.fields, path, unit.payload.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError("unit 0x%04x (%s) is declared string but is not valid UTF-8: %s"
                             % (unit.id, path, exc)) from exc
    else:
        width = (integer_widths or {}).get(kind)
        if width is None:
            doc.deferred[path] = ("RFC-011 gives no byte width for this %s field; raw=%s"
                                  % (kind, unit.payload.hex()))
        elif len(unit.payload) != width:
            # Loud, not lenient: a caller-supplied width that disagrees with the
            # bytes on the wire is exactly the signal that the width is wrong.
            raise ValueError("unit 0x%04x (%s) declared %s=%d bytes but carries %d bytes"
                             % (unit.id, path, kind, width, len(unit.payload)))
        else:
            doc.integers[path] = int.from_bytes(unit.payload, "big")


def decode_message(data: bytes, *, integer_widths: Optional[Dict[str, int]] = None,
                   flag_bit_order: str = "msb", strict_placement: bool = True
                   ) -> Tuple[Header, DecodedDocument]:
    """Header + body of a document answer, in one call.

    ``integer_widths`` and ``flag_bit_order`` are forwarded, because a caller who
    had to supply them to decode one layer should not have to supply them again to
    decode the layer above.
    """
    header = parse_header(data, flag_bit_order=flag_bit_order)
    body_start = header.header_length
    body = data[body_start:body_start + header.message_length]
    units = parse_units(body)
    doc = decode_document(units, integer_widths=integer_widths,
                          strict_placement=strict_placement)
    return header, doc

# ---------------------------------------------------------------- codec
#
# Everything below this line exists so the decoder can be checked against itself
# and against a stranger's bytes, without a reference implementation to lean on.

FLAG_ORDER_CHOICES = ("msb", "lsb")
"""RFC-011 lists the flag's fields in order and never numbers the bits. `msb`
maps the first listed field to bit 15; `lsb` maps it to bit 0. Both are offered
because the document does not choose; `msb` is only the default."""


def _flag_bit(index: int, order: str) -> int:
    if order == "msb":
        return 15 - index
    return index


def _flag_bits_from(flag: int, order: str) -> Dict[str, int]:
    return {name: (flag >> _flag_bit(index, order)) & 1
            for index, (name, _bit) in enumerate(_FLAG_BITS)}


# Absolute container path -> unit ID. Explicit rather than derived from
# CONTAINERS, because ``proof`` is a top-level container (0x2140) *and* a
# child of ``extension.attributes`` (0x3560): a name-keyed map would silently
# pick one and mis-encode the other.
CONTAINER_PATHS: Dict[str, int] = {
    "bidDocument": 0x2100,
    "publicKey": 0x2110,
    "alsoKnownAs": 0x2120,
    "service": 0x2130,
    "proof": 0x2140,
    "errResponse": 0x2010,
    "bidDocumentField": 0x2200,
    "extension": 0x3000,
    "recovery": 0x3100,
    "extension.delegateSign": 0x3300,
    "extension.attributes": 0x3500,
    "extension.attributes.proof": 0x3560,
    "extension.acsns": 0x3600,
    "extension.verifiableCredentials": 0x3700,
}

# Container ID -> the path it is allowed to hold. The decoder needs this to
# refuse a leaf that sits in the wrong container: without that check a mutated
# container ID decodes to exactly the same document, because field paths are
# absolute. The bit-flip probe in tools/mutate_bid_binary.py found that hole.
CONTAINER_BY_ID: Dict[int, str] = {uid: path for path, uid in CONTAINER_PATHS.items()}

# Containers that legitimately hold a leaf from outside their own subtree, with the
# section that says so. §5.2.2: errResponse (0x2010) carries two units -
# ``didDocument.id`` (0x2102) and ``Result.msg`` (0x2011) - so the document id is
# allowed inside it even though its field path is top-level ``id``.
CONTAINER_EXTRA_PATHS: Dict[int, frozenset] = {0x2010: frozenset({"id"})}


def documented_parent(path: str) -> Optional[int]:
    """The container a field path belongs to, taken from the longest matching prefix.

    ``publicKey.id`` -> 0x2110, ``extension.attributes.key`` -> 0x3500, ``id`` -> None
    (a top-level field). Used to reject a leaf that was moved to a different container:
    without it, renaming ``publicKey`` (0x2110) to the document wrapper (0x2100) left
    the document byte-identical, because the field paths are absolute.
    """
    best = None
    for prefix, uid in CONTAINER_PATHS.items():
        if path == prefix or path.startswith(prefix + "."):
            if best is None or len(prefix) > len(best[1]):
                best = (uid, prefix)
    return None if best is None else best[0]

# Containers whose payload is a bare string, not a unit sequence
# (``recovery`` holds a key id; ``authentication`` does too - see the 0x2100
# collision). Encoding needs this list or it would nest a string as units.
STRING_CONTAINERS = ("recovery",)

# Two spellings for the same AC-number leaf. Encoding must choose one; the
# decoder accepts both. `3610` is canonical because §5.2.1.1.2 is the field
# table, while §5.2.1.4.2 is an example.
ACSNS_SPELLINGS = {"3610": (0x3610, 0x3620), "3601": (0x3601, 0x3602)}
DEFAULT_ACSNS_SPELLING = "3610"


def encode_units(units: List[Unit]) -> bytes:
    """Inverse of :func:`parse_units`, byte for byte and order for order."""
    out = bytearray()
    for unit in units:
        if unit.id < 0 or unit.id > 0xFFFF:
            raise ValueError("unit id %r does not fit 2 bytes" % unit.id)
        out += build_unit(unit.id, unit.payload)
    return bytes(out)


def encode_message(units: List[Unit], transaction_id: int, *, opcode: int = 0,
                   reply_code: int = 1, message_id: int = 1,
                   flags: Optional[Dict[str, int]] = None, version: int = 1,
                   option_bytes: bytes = b"",
                   flag_bit_order: str = "msb") -> bytes:
    """Header + body, the inverse of :func:`decode_message`."""
    body = encode_units(units)
    if len(option_bytes) % HEADER_UNIT:
        raise ValueError("option field must pad to a multiple of %d bytes" % HEADER_UNIT)
    header_units = (HEADER_MIN + len(option_bytes)) // HEADER_UNIT
    if header_units > 0x0F:
        raise ValueError("header would be %d bytes, beyond the 4-bit headerLength"
                         % (HEADER_MIN + len(option_bytes)))
    first = ((version & 0x0F) << 4) | header_units
    if flag_bit_order not in FLAG_ORDER_CHOICES:
        raise ValueError("flag_bit_order must be one of %r" % (FLAG_ORDER_CHOICES,))
    flag = 0
    for index, (name, _bit) in enumerate(_FLAG_BITS):
        if flags and flags.get(name):
            flag |= 1 << _flag_bit(index, flag_bit_order)
    flag |= (opcode & 0x0F) << _OPCODE_SHIFT
    head = struct.pack(">BHBHHII", first, flag, 0, reply_code, message_id,
                       transaction_id, len(body))
    return head + option_bytes + body


def _reverse_field_table(acsns_spelling: str) -> Dict[str, Tuple[int, str]]:
    if acsns_spelling not in ACSNS_SPELLINGS:
        raise ValueError("acsns_spelling must be one of %r" % (sorted(ACSNS_SPELLINGS),))
    skip = {0x3601, 0x3602, 0x3610, 0x3620}
    table: Dict[str, Tuple[int, str]] = {}
    for uid, (path, kind) in FIELD_TABLE.items():
        if uid in skip:
            continue
        table[path] = (uid, kind)
    lo, hi = ACSNS_SPELLINGS[acsns_spelling]
    table["extension.acsns.acsn"] = (lo, STRING)
    table["extension.acsns.acsnAddress"] = (hi, STRING)
    return table


def encode_document(fields: Dict[str, Any], *, integer_widths: Optional[Dict[str, int]] = None,
                    acsns_spelling: str = DEFAULT_ACSNS_SPELLING) -> List[Unit]:
    """Inverse of :func:`decode_document`, into the canonical unit order.

    Canonical means ascending unit ID inside every container. The decoder keeps
    no ordering, so the inverse cannot reproduce an arbitrary writer's order -
    that is why the byte-exact round-trip is claimed at the unit layer
    (:func:`encode_units`), and semantic idempotence here.
    """
    table = _reverse_field_table(acsns_spelling)
    tree: Dict[str, Any] = {"_leaf": [], "_children": {}}

    def slot(path: str):
        parts = path.split(".")
        node = tree
        for i in range(len(parts) - 1):
            prefix = ".".join(parts[:i + 1])
            if prefix not in CONTAINER_PATHS:
                raise ValueError("field path %r has no container %r in RFC-011" % (path, prefix))
            node["_children"].setdefault(prefix, {"_leaf": [], "_children": {}})
            node = node["_children"][prefix]
        return node

    def add(path: str, value: Any):
        entry = table.get(path)
        if entry is None:
            raise ValueError("no RFC-011 unit ID for field path %r" % path)
        uid, kind = entry
        payload = _encode_leaf_payload(uid, path, kind, value, integer_widths)
        slot(path)["_leaf"].append((uid, payload))

    def walk(node: Dict[str, Any], prefix: str = ""):
        for name, value in node.items():
            if name.startswith("_"):
                continue   # _deferred / _unknown are report buckets, not fields
            path = (prefix + "." + name) if prefix else name
            if path == "authentication":
                # 0x2100 is bidDocument *and* the authentication key-id list (the RFC's
                # own collision). A key id is a bare string, so it is emitted as a bare
                # 0x2100 leaf - wrapping it in another 0x2100 container would add a
                # nesting level that nothing in the document asks for.
                for item in (value if isinstance(value, list) else [value]):
                    tree["_leaf"].append((0x2100, _as_string(path, item).encode("utf-8")))
                continue
            if path == "recovery":
                holder = tree["_children"].setdefault("recovery",
                                                      {"_leaf": [], "_children": {}})
                holder["_leaf"].append((0x3100, _as_string(path, value).encode("utf-8")))
                continue
            if isinstance(value, dict):
                walk(value, path)
                continue
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        raise ValueError("%r holds objects; RFC-011 has no unit for that" % path)
                    add(path, item)
                continue
            add(path, value)

    walk(fields)

    return _emit(tree)

def _as_string(path: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("%r holds a key id, expected str not %s" % (path, type(value).__name__))
    return value

def _encode_leaf_payload(uid: int, path: str, kind: str, value: Any,
                         integer_widths: Optional[Dict[str, int]]) -> bytes:
    if kind == STRING:
        if not isinstance(value, str):
            raise ValueError("%r is a string field, got %s" % (path, type(value).__name__))
        return value.encode("utf-8")
    width = (integer_widths or {}).get(kind)
    if width is None:
        raise ValueError("%r is an RFC-011 %s field of unstated width; pass "
                         "integer_widths={%r: N} to encode it" % (path, kind, kind))
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("%r is an integer field, got %s" % (path, type(value).__name__))
    if value < 0 or value >= (1 << (8 * width)):
        raise ValueError("%r=%d does not fit %d unsigned bytes" % (path, value, width))
    return value.to_bytes(width, "big")

def _emit(node: Dict[str, Any]) -> List[Unit]:
    leaves = sorted(node["_leaf"], key=lambda pair: pair[0])
    children = [(CONTAINER_PATHS[prefix], prefix, sub) for prefix, sub in node["_children"].items()]
    children.sort(key=lambda triple: triple[0])
    units = [Unit(uid, payload) for uid, payload in leaves]
    for uid, prefix, sub in children:
        if prefix in STRING_CONTAINERS:
            payload = b"".join(payload for _uid, payload in sub["_leaf"])
            if sub["_children"]:
                raise ValueError("container %r holds a string and child units at once" % prefix)
            units.append(Unit(uid, payload))
            continue
        inner = _emit(sub)
        if not inner:
            raise ValueError("container %r would encode with an empty payload" % prefix)
        units.append(Unit(uid, encode_units(inner)))
    return units


# ---------------------------------------------------------------- assumptions
#
# The point of this table is not documentation; each entry names the parameter
# that changes it. tests/test_bid_binary_codec.py flips every flippable one.

ASSUMPTIONS: Dict[str, Dict[str, str]] = {
    "flag_bit_order": {
        "gap": "§5.1.2.1 lists qr/tc/rd/dt/tr/ct in order but assigns no bit numbers",
        "choice": "first listed field = bit 15 (parameter: flag_bit_order='msb'|'lsb')",
        "status": "flippable",
    },
    "integer_widths": {
        "gap": "RFC-011 types ttl/type/port/acsn as Int/Long and never gives a byte width",
        "choice": "no width is assumed; caller passes integer_widths={'int':N,'long':M}",
        "status": "caller-supplied",
    },
    "acsns_spelling": {
        "gap": "§5.2.1.1.2 uses 0x3610/0x3620, §5.2.1.4.2 uses 0x3601/0x3602 for the same pair",
        "choice": "encode 0x3610/0x3620 (parameter: acsns_spelling='3610'|'3601'); decode accepts both",
        "status": "flippable",
    },
    "bid_document_collision": {
        "gap": "0x2100 is bidDocument (container) and bidDocument.authentication (key-id list)",
        "choice": "payload that parses as units = container, otherwise = one key id",
        "status": "heuristic",
    },
    "fragment_reassembly": {
        "gap": "§5.1.3 says first fragment has messageID=1 and later ones +1, no end condition",
        "choice": "no reassembly; fragments are decoded one at a time",
        "status": "not-implemented",
    },
    "signature_unit_ids": {
        "gap": "§5.1.2.3 describes creator/digestAlgorithm/signatureValue units, never their IDs",
        "choice": "signature block is not located; signature_units_detectable is False",
        "status": "not-implemented",
    },
}


def assumption_report() -> str:
    lines = ["RFC-011 implementation assumptions (each is a parameter, not prose):"]
    for name, item in ASSUMPTIONS.items():
        lines.append("  %-22s [%s] %s -> %s" % (name, item["status"], item["gap"], item["choice"]))
    return "\n".join(lines)
