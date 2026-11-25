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


def parse_header(data: bytes) -> Header:
    if len(data) < HEADER_MIN:
        raise ValueError("message shorter than the 16-byte minimum header: %d" % len(data))
    version = data[0] >> 4
    header_units = data[0] & 0x0F
    header_length = header_units * HEADER_UNIT
    if header_length < HEADER_MIN or header_length > len(data):
        raise ValueError("headerLength=%d units (%d bytes) is out of range for a %d-byte message"
                         % (header_units, header_length, len(data)))
    flag = struct.unpack(">H", data[1:3])[0]
    flags = {name: (flag >> bit) & 1 for name, bit in _FLAG_BITS}
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
                 version: int = 1) -> bytes:
    """The inverse of :func:`parse_header`, used to build test vectors.

    Only a 16-byte header (no option field) is produced: the RFC gives no option
    type whose payload length it defines, so appending one would be invention.
    """
    flag = 0
    for name, bit in _FLAG_BITS:
        if flags and flags.get(name):
            flag |= 1 << bit
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
    unknown: List[Dict[str, Any]] = field(default_factory=list)
    signature_units_detectable: bool = False

    def as_dict(self) -> Dict[str, Any]:
        out = dict(self.fields)
        if self.deferred:
            out["_deferred"] = dict(self.deferred)
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


def decode_document(units: List[Unit], into: Optional[DecodedDocument] = None) -> DecodedDocument:
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
                decode_document(children, doc)
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
                decode_document(children, doc)
            else:
                _put(doc.fields, "authentication", unit.payload.decode("utf-8", "strict"))
            continue
        _decode_leaf(unit, doc)
    return doc


def _decode_leaf(unit: Unit, doc: DecodedDocument):
    entry = FIELD_TABLE.get(unit.id)
    if entry is None:
        doc.unknown.append({"id": "0x%04x" % unit.id, "len": len(unit.payload),
                            "hex": unit.payload[:32].hex()})
        return
    path, kind = entry
    if kind == STRING:
        try:
            _put(doc.fields, path, unit.payload.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError("unit 0x%04x (%s) is declared string but is not valid UTF-8: %s"
                             % (unit.id, path, exc)) from exc
    else:
        doc.deferred[path] = ("RFC-011 gives no byte width for this %s field; raw=%s"
                              % (kind, unit.payload.hex()))


def decode_message(data: bytes) -> Tuple[Header, DecodedDocument]:
    """Header + body of a document answer, in one call."""
    header = parse_header(data)
    body_start = header.header_length
    body = data[body_start:body_start + header.message_length]
    units = parse_units(body)
    doc = decode_document(units)
    return header, doc
