"""Reading an OpenTimestamps proof without the OpenTimestamps library.

Two questions this file exists to answer, and the reason it exists at all: the
published `.ots` for v0.4.1 was a bare serialized tree -- no header magic -- so the
official `ots` client refused it with "is not a timestamp file", and the only tool
that could read it was ours. That is backwards: the proof is for strangers.

So the container is handled here in plain Python:

  * `binds(blob, digest)` -- does this proof answer for *that* digest? The tree
    itself is not walked; only the header is read, which is enough to refuse a proof
    belonging to a different file. Our earlier verifier passed the proof's own first
    32 bytes as the initial message, so it never noticed if the proof was for
    another file at all.
  * `bare_to_standard(blob, digest)` -- wrap a bare tree in the standard container
    (magic + major version + file hash op + digest). The tree bytes are copied
    verbatim, so this changes the container and not the evidence.

Standard container layout, from opentimestamps.core.timestamp.DetachedTimestampFile:

    MAGIC(18) | major version (1) | file hash op tag (1) | digest (32) | tree
"""
import hashlib

MAGIC = (b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
         b"")
MAJOR_VERSION = 1
OP_SHA256 = b"\x08"
DIGEST_LEN = 32


def is_standard(blob):
    return bool(blob) and blob.startswith(MAGIC)


def _header_len(blob):
    if not is_standard(blob):
        return None
    if len(blob) < len(MAGIC) + 2 + DIGEST_LEN:
        return None
    return len(MAGIC)


def header(blob):
    """(major_version, hash_op_tag, digest) or None when there is no header."""
    off = _header_len(blob)
    if off is None:
        return None
    major = blob[off]
    op_tag = blob[off + 1:off + 2]
    digest = blob[off + 2:off + 2 + DIGEST_LEN]
    return major, op_tag, digest


def binds(blob, digest):
    """True when the proof is about the given digest.

    A bare tree has no digest of its own -- it is attached to one -- so a bare
    proof returns False here: it cannot be bound by inspection, which is exactly
    why the standard container matters.
    """
    got = header(blob)
    if got is None:
        return False
    major, op_tag, recorded = got
    return major == MAJOR_VERSION and op_tag == OP_SHA256 and recorded == digest


def bare_to_standard(blob, digest):
    """Wrap a bare tree. Raises if the input already has a header."""
    if is_standard(blob):
        raise ValueError("this proof already carries a standard header")
    if len(digest) != DIGEST_LEN:
        raise ValueError("digest must be %d bytes" % DIGEST_LEN)
    return MAGIC + bytes([MAJOR_VERSION]) + OP_SHA256 + digest + blob


def digest_of_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).digest()
