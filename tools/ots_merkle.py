"""Recompute a Bitcoin-anchored OpenTimestamps proof, without the OTS library.

Until now the checker printed the block height because a record said so, and the
proof was walked by code this repository wrote for itself. This walks the proof
directly: the file's digest, every append/prepend/sha256 in the tree, and the
merkle root at the leaf carrying a Bitcoin header attestation -- then compares
it with the block the record names. Standard library only, so a stranger can run
it where `opentimestamps` has never been installed.

Byte order: the leaf message is the block's merkle root in internal order, while
explorers print it reversed. Both are tried and the output says which matched,
so a mismatch can never be an artefact of formatting.

Exit codes: 0 ACCEPTABLE, 1 NOT ACCEPTABLE, 3 NOT MEASURED.
"""

import hashlib
import json
import sys

MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
BITCOIN_TAG = bytes.fromhex("0588960d73d71901")
LITECOIN_TAG = bytes.fromhex("06869a0d73d71b45")

OPS_WITH_ARG = (0xF0, 0xF1)  # append, prepend
OPS_UNARY = {0x02: "sha1", 0x03: "ripemd160", 0x08: "sha256"}
OP_NAMES = {0xF0: "append", 0xF1: "prepend", 0xF2: "reverse"}
OP_NAMES.update({tag: name for tag, name in OPS_UNARY.items()})


class NotReadable(Exception):
    """The proof cannot be parsed as a standard container."""


class _Ctx(object):
    def __init__(self, blob):
        self.blob = blob
        self.pos = 0

    def take(self, count):
        if self.pos + count > len(self.blob):
            raise NotReadable("truncated at byte %d" % self.pos)
        out = self.blob[self.pos:self.pos + count]
        self.pos += count
        return out

    def byte(self):
        return self.take(1)[0]

    def varuint(self):
        value, shift = 0, 0
        while True:
            raw = self.byte()
            value |= (raw & 0x7F) << shift
            if not raw & 0x80:
                return value
            shift += 7
            if shift > 70:
                raise NotReadable("varuint too long")

    def varbytes(self):
        return self.take(self.varuint())


def _digest_of(name, message):
    if name == "ripemd160" and "ripemd160" not in hashlib.algorithms_available:
        raise NotReadable("this build has no ripemd160; that operation is not walked")
    return hashlib.new(name, message).digest()


def _apply(tag, arg, message):
    if tag == 0xF0:
        return message + arg
    if tag == 0xF1:
        return arg + message
    if tag == 0xF2:
        return message[::-1]
    if tag in OPS_UNARY:
        return _digest_of(OPS_UNARY[tag], message)
    raise NotReadable("unknown operation tag 0x%02x" % tag)


def _attestation(ctx):
    tag = ctx.take(8)
    payload = _Ctx(ctx.varbytes())
    if tag == BITCOIN_TAG:
        return ("bitcoin", payload.varuint())
    if tag == LITECOIN_TAG:
        return ("litecoin", payload.varuint())
    return ("other:" + tag.hex(), None)


def _timestamp(ctx, message, depth=0):
    """One list holds both kinds of item: 0xff means another item follows, 0x00
    means this is the last item and it is an attestation."""
    if depth > 256:
        raise NotReadable("proof nests deeper than 256 operations")
    node = {"message": message, "attestations": [], "ops": []}
    while True:
        marker = ctx.byte()
        final = marker != 0xFF
        if not final:
            tag = ctx.byte()
            if tag == 0x00:
                node["attestations"].append(_attestation(ctx))
                continue
        elif marker == 0x00:
            node["attestations"].append(_attestation(ctx))
            return node
        else:
            tag = marker
        arg = ctx.varbytes() if tag in OPS_WITH_ARG else None
        child = _timestamp(ctx, _apply(tag, arg, message), depth + 1)
        node["ops"].append((tag, child))
        if final:
            return node


def parse(blob):
    """(file digest, root node). Raises NotReadable rather than guessing."""
    ctx = _Ctx(blob)
    if ctx.take(len(MAGIC)) != MAGIC:
        raise NotReadable("no DetachedTimestampFile header: a bare tree, which the official "
                          "client refuses; wrap it with ots_container first")
    if ctx.byte() != 1:
        raise NotReadable("not a version 1 container")
    hash_op = ctx.byte()
    if hash_op != 0x08:
        raise NotReadable("file hash op 0x%02x is not sha256; not walked here" % hash_op)
    digest = ctx.take(32)
    root = _timestamp(ctx, digest)
    if ctx.pos != len(blob):
        raise NotReadable("%d trailing bytes after the proof" % (len(blob) - ctx.pos))
    return digest, root


def leaves(node, out=None, path=()):
    out = [] if out is None else out
    if node["attestations"]:
        out.append((path, node))
    for tag, child in node["ops"]:
        leaves(child, out, path + (tag,))
    return out


def path_names(path):
    return "/".join(OP_NAMES.get(tag, "0x%02x" % tag) for tag in path) or "digest"


def _digest_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.digest()


def verify(proof_path, data_path=None, record=None):
    """Everything a caller should print, as a dict. Never raises for bad input."""
    result = {"proof": proof_path, "data": data_path, "exit": 3, "lines": [], "blocks": []}
    try:
        with open(proof_path, "rb") as handle:
            blob = handle.read()
    except OSError as exc:
        result["lines"].append("unreadable proof: %s" % exc)
        return result
    try:
        digest, root = parse(blob)
    except NotReadable as exc:
        result["lines"].append("not read: %s" % exc)
        return result

    result["digest"] = digest.hex()
    result["exit"] = 0
    result["lines"].append("digest       " + digest.hex())
    if data_path:
        on_disk = _digest_file(data_path)
        bound = on_disk == digest
        result["bound"] = bound
        result["lines"].append("bound to %s %s" % (data_path.split("\\")[-1].split("/")[-1],
                                                  "yes" if bound else "NO"))
        if not bound:
            result["exit"] = 1

    found = []
    for path, node in leaves(root):
        for kind, height in node["attestations"]:
            if kind in ("bitcoin", "litecoin"):
                found.append({"chain": kind, "height": height, "root": node["message"].hex(),
                              "path": path_names(path)})
    result["blocks"] = found
    if not found:
        result["lines"].append("blocks       the proof carries no block header attestation")
        result["exit"] = max(result["exit"], 3)
        return result

    recorded = (record or {}).get("merkle_root")
    for item in found:
        result["lines"].append("chain        %s, height %d, merkle root %s (via %d operations)"
                               % (item["chain"], item["height"], item["root"],
                                  len(item["path"].split("/"))))
        if recorded:
            reversed_hex = bytes.fromhex(item["root"])[::-1].hex()
            if item["root"] == str(recorded).lower():
                item["order"] = "internal"
            elif reversed_hex == str(recorded).lower():
                item["order"] = "reversed (as explorers print it)"
            else:
                result["exit"] = max(result["exit"], 1)
                result["lines"].append("             the recomputed root is not the recorded root")
                continue
            result["lines"].append("             recomputed from %s, agrees with the recorded root "
                                   "in %s byte order" % (result["digest"][:12] + "...", item["order"]))
        else:
            result["lines"].append("             no block recorded, so nothing to compare it with")
            result["exit"] = max(result["exit"], 3)
    return result


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    proof = data = None
    record_path = None
    as_json = False
    while argv:
        word = argv.pop(0)
        if word == "--json":
            as_json = True
        elif word == "--data":
            data = argv.pop(0)
        elif word == "--block-json":
            record_path = argv.pop(0)
        elif word.startswith("-"):
            print("unknown option %s" % word, file=sys.stderr)
            return 3
        else:
            proof = word
    if not proof:
        print("usage: ots_merkle.py PROOF [--data FILE] [--block-json BITCOIN-ATTESTATION.json]",
              file=sys.stderr)
        return 3
    record = None
    if record_path:
        try:
            with open(record_path, encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError) as exc:
            print("NOT MEASURED - cannot read the block record: %s" % exc)
            return 3
        record = record.get("bitcoin") or {}
    result = verify(proof, data, record)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        for line in result["lines"]:
            print(line)
    print({0: "ACCEPTABLE", 1: "NOT ACCEPTABLE", 3: "NOT MEASURED"}[result["exit"]])
    return result["exit"]


if __name__ == "__main__":
    raise SystemExit(main())
