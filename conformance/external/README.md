# External implementations

**Records: 0.**

This directory is where verification runs performed by someone other than the
maintainer would be recorded. It is empty on purpose. Creating the empty
schema before there is anything to put in it is the point: the place exists,
the field names are fixed, and so the first entry cannot be invented to look
stronger than it was.

## Why a pin file rather than a paragraph

A sentence like "an external party verified this" is worth nothing. A pinned
record is checkable: which implementation, by whom, at which commit, built with
which toolchain, against which corpus, and which hashes.

The schema below is borrowed from
`draft-schrock-ep-authorization-receipts-13`'s
`EP-EXTERNAL-IMPLEMENTATION-PIN-v1` record, because it already solves the
problem we have — and because the same record shows how to do it honestly:

```json
{
  "@version": "uibc-external-implementation-pin-v1",
  "implementation": {
    "implementation_id": "<who>-<language>-<what>",
    "organization": "<independent party, not the maintainer>",
    "language": "<lang>",
    "version": "<their version>",
    "license_spdx": "<SPDX>"
  },
  "source": {
    "repository": "<repo url>",
    "commit": "<40-hex>",
    "tree_path": "<path to the verifier inside it>",
    "tree_oid": "<git tree oid>"
  },
  "build": {
    "toolchain": "<exact toolchain string>",
    "lockfile_committed": true,
    "entrypoint": "<how it is invoked>"
  },
  "conformance": {
    "archive_sha256": "711fa82c9f183066cfae6441a4fe3fc27fcc516b25f2a976cad5e0dd61b5135f",
    "cases": 36,
    "passed": 0,
    "status": "not_run",
    "receipt": "<their receipt.json, committed verbatim>"
  },
  "honesty": {
    "third_party_attestation": false,
    "strict_clean_room_acceptance": false,
    "notes": "<what this record does NOT establish>"
  }
}
```

Two rules, both learned from the draft that produced this shape:

1. **The two booleans in `honesty` default to `false` and are the author's own
   statement, not the maintainer's.** Even a real external implementation is not
   automatically a third-party attestation; the draft that supplied this schema
   records a genuine external Rust verifier and still sets both flags to
   `false`, with a note that its signed statement predates the commit it would
   otherwise attest. If they will not claim it, we certainly will not.
2. **The archive hash is the conformance archive as published**
   (`conformance/uibc-conformance-0.4.1.zip`). A run against different bytes is
   a different result and gets its own record.

## What the first record will still not mean

- It will not mean the verifier is secure, complete, or correct — only that it
  behaved as 36 cases required.
- It will not mean an audit, a certification or an endorsement.
- It will not mean the design is any good. A stranger refusing all 35 broken
  packages says their tool works on this corpus, nothing more.

Until someone runs it, the number at the top of this file stays 0, and
`docs/AUDIT-KIT.md` says so in the same words.
