# External anchor (RFC 3161) — what we now have, and what it does not prove

## Why this layer existed at all

`S13` proves a leaf is inside a tree **we built**. `S9` proves a head was pinned
**somewhere else of ours**. Neither proves the tree existed at time T, because we
are the only witness to our own clock.

A public transparency log (Sigstore Rekor, which arkforge reports using at
https://arkforge.tech/en/blog/mcp-client-verification-receipts/) covers the "did
anyone else see this" half. We make no claim to have matched it: our entry
exists, its inclusion proof is not verified here, and the table below says so.
What we do have is a time witness, via RFC 3161.

We now have a time witness of our own, via RFC 3161 - not an equivalent of a
public log, just the "when" half.

## A real token, not a mock

```
$ python tools/anchor_tsa.py --head-file tools/out/release_status.json --tsa freetsa
status                = anchored
digest (messageImprint)= 4ad23d9153c33c77253b23e1f5938249cb6877de93eb7593dea26fa5f7fd6e98
genTime               = 2026-11-17T08:11:35+00:00
TSA                   = Free TSA (Organisation), www.freetsa.org, Wuerzburg DE
serial                = 169204872
signature_verified    = true
tsr_sha256            = ecb6a2961b8341108935c9e4818ab93ccf74533da2c23e514e700418ad134f95
```

The token itself is committed at `tests/fixtures/anchor/freetsa.tsr` with the CA
bundle and the anchored file, so `tests/test_v13_anchor_tsa.py` verifies bytes
**we did not generate**. That is the whole point: a mock token would only prove
the mock agrees with itself.

## Where the CA comes from (so the bundle is not just ours)

The token is checked against `tests/fixtures/anchor/freetsa_ca.pem`, a 5,107-byte bundle
we ship. A reviewer should not have to trust that file: fetch the same material from the
TSA and compare.

| item | value |
|---|---|
| published by Free TSA | `https://freetsa.org/files/tsa.crt` and `https://freetsa.org/files/cacert.pem` |
| bundle we ship | `freetsa_ca.pem`, SHA-256 `b8201c19ae46a882ceb83ce58251662fa0e47b0ebff40d6bc025f3e4626ab51e` |

```bash
# reproduce the bundle from the TSA's own endpoints and compare
curl -s https://freetsa.org/files/tsa.crt https://freetsa.org/files/cacert.pem > /tmp/ca.pem
sha256sum /tmp/ca.pem   # compare with the value above
```

If the hashes differ, the bundle is stale or substituted - and then every "verified"
verdict in this file is worth nothing until it is re-fetched. That dependency is real
and is stated rather than hidden.

## What it proves

- The SHA-256 digest `4ad23d91…` existed at `2026-11-17T08:11:35Z`.
- An independent party (Free TSA) signed that statement with a key we do not hold.
- The signature chains to the CA we ship, and verifies **offline**.

## What it does not prove

- Not that the *evidence* is true — only that a digest existed then.
- Not that the token is still the newest one (a later token would supersede it).
- Not a signature by a regulator or a notified body. It is a time witness, nothing more.
- Rekor anchoring is **not** implemented: that needs a signed entry and a log
  inclusion proof, plus submission of our public key to a public log. Recorded as
  open, not as done.

## Fail-closed behaviour

| Situation | Exit | Recorded as |
|---|---|---|
| TSA unreachable | 2 | `unanchored` + reason |
| TSA refuses (`status != granted`) | 2/3 | `unanchored` + fail_info |
| No CA bundle available | 3 | `unanchored` (signature cannot be judged) |
| Token about another digest | 3 | `unanchored` + "messageImprint is not the digest we asked about" |
| Everything verified | 0 | `anchored` |

A package is never called anchored because we tried. "Could not check" stays
"could not check".

## Reproduce

```bash
python tools/anchor_tsa.py --head-file tools/out/release_status.json --tsa freetsa
python tools/anchor_tsa.py --verify tools/out/anchor_freetsa.tsr \
       --data tools/out/release_status.json --cabundle tools/out/anchor_freetsa_ca.pem
```

## Package-level check (S16)

`verify.py` now judges an external token as a check of its own, so a package can
carry its own time witness instead of relying on this tool being run at release
time. Opt in by shipping `evidence/external_anchor.json`:

```json
{
  "scheme": "rfc3161",
  "tsa": "Free TSA",
  "tsr": "evidence/tsa/freetsa.tsr",
  "cabundle": "evidence/tsa/ca.pem",
  "digest_of": "manifest.json",
  "tsr_sha256": "<sha256 of the .tsr bytes, optional but recommended>"
}
```

| Situation | S16 |
|---|---|
| token dates `digest_of`, signature chains to the shipped CA | **PASS** |
| token dates a different digest | **FAIL** |
| token bytes differ from declared `tsr_sha256` | **FAIL** |
| token or CA bundle missing | **FAIL** |
| verifier has no `asn1crypto` (cannot judge) | **INCONCLUSIVE**, never PASS |
| no `external_anchor.json` in the package | check not run |

Verified from a public anonymous clone of `fb8b17b`: `248 tests OK` and
`S16 = PASS` with the real freetsa token, offline.

## Rekor (public transparency log)

`tools/anchor_rekor.py` submits a signed `hashedrekord` entry to
`https://rekor.sigstore.dev`. It is the mechanism arkforge reports using; we
anchor one entry for one artifact, not an ecosystem, and we do not claim parity.

Real entry, 2026-11-17:

| field | value |
|---|---|
| log index | `3944456508` |
| log id | `c0d23d6a…91801d` |
| integrated time | `1794903738` |
| tree size | `3822552250` |
| body digest | `4ad23d91…6e98` (same head as the TSA token) |

### What this tool checks, and what it refuses to claim

| check | verdict |
|---|---|
| entry body hashes the artifact we hold | verified |
| signature over the artifact verifies with the public key in the entry | verified |
| the log's own signature over the entry (`signedEntryTimestamp`) verifies with `https://rekor.sigstore.dev/api/v1/log/publicKey` | **verified** |
| the log's tree checkpoint signature | **not verified** - its key is not the one published at `/api/v1/log/publicKey`; note encodings tried (body, body+newline, body+blank line, prefix included; SHA-256/384/512) all reject |
| the digest really is in the log's tree (inclusion proof) | **not verified** - 20 siblings for a 3.8e9-leaf tree does not verify as a full RFC 6962 path in either order |

Rekor's `inclusionProof` is a Trillian-side partial proof (20 siblings for a
3.8e9-leaf tree) and does not verify as a full RFC 6962 path from the leaf with
our own walker, in either sibling order (tested 2026-11-17). Judging it properly
needs the log's signed checkpoint. Until that is implemented, the tool reports
`inclusion.verified = false` and the test suite asserts that it stays false:
"we submitted an entry" is not "the entry is provably in the tree".



### Third-party cross-check of the inclusion proof (2026-11-17)

| attempt | result |
|---|---|
| our own RFC 6962 walker, both sibling orders | root mismatch |
| `pip install rekor_log_verifier` (independent PyPI implementation of Rekor log verification), called with the entry's own `logIndex` / `treeSize` / `rootHash` / `hashes` | `RootMismatchError`, and its own computed root (`4576ba40…2c5d`) differs from the published root |

Two independent implementations, using the documented RFC 6962 conventions, both
fail on the same proof. That is evidence about the *proof format* (20 siblings for
a 3.8e9-leaf tree, leaf/step conventions not documented on the pages we found),
not about one implementation's arithmetic. Independent inclusion verification
therefore stays **blocked**, and no claim of it appears anywhere in the release.

### OpenTimestamps: the second anchor type (2026-11-17, proof rebuilt 2026-11-25, block attestation 2026-11-26)

The ASQAV compliance profile wants "RFC 3161, OpenTimestamps, or both". Both
anchors cover **one digest**, `4ad23d91…` - the sha256 of the head file - rather
than two unrelated claims:

| item | value |
|---|---|
| file | `tests/fixtures/anchor/anchored_head.json`, sha256 `4ad23d9153c3…7fd6e98` |
| RFC 3161 | Free TSA token, `genTime=2026-11-17T08:11:35Z`, signature verified offline |
| OpenTimestamps | three public calendars (`alice.btc`, `bob.btc`, `finney.calendar.eternitywall`), proof `tests/fixtures/anchor/ots_head.ots`, 3536 bytes (635 before the 2026-11-26 upgrade), stamped 2026-11-25 |
| what the OTS proof says today | **three Bitcoin block attestations, one per calendar, all naming block 977449**, with the three pending calendar attestations still listed beside them. The block header is now cross-checked against two chain sources (below), but chain work, confirmation depth and sequence are still not checked, so what is asserted is `bitcoin_attested` plus "this header hashes to this block and carries this root" - not "this block is the most-work chain" |

That is the honest status: a calendar attestation says the calendar had this
digest at submission time, which is weaker than a block attestation. The
upgrade path (`tools/anchor_ots.py --upgrade`) asks each calendar the proof
names; it needs hours to days, and the Bitcoin block header is not
cross-checked here because that requires a chain source. A block attestation had to *appear in the proof* before this row could change, and on 2026-11-26 it did: both proofs were upgraded and now carry `BitcoinBlockHeaderAttestation` at height 977449 from each of the three calendars.

**2026-11-26, the upgrade landed.** `tools/anchor_ots.py --upgrade` was run against both proofs (`tests/fixtures/anchor/ots_head.ots`, 635 B before the upgrade, and `tools/out/release_status.json.ots`); re-verifying both now lists three `BitcoinBlockHeaderAttestation` entries at **height 977449** and still lists the three pending calendar attestations. Read straight from the proof with the official library (the CLI's `--verify` reports the attestation but prints a blank height -- a gap in the reporter, not in the proof). Nothing in that step claims the header was checked against Bitcoin: that needs a chain source, and this repository fetched none until 2026-11-26 - the cross-check is the block just below.

**2026-11-26, the block header is checked, not just named.** Carrying a block
attestation only says the calendars returned one; `tools/ots_block_crosscheck.py`
now finishes the step with arithmetic anyone can repeat from the committed
receipt `docs/anchor-ots-block-977449.json`:

| item | value |
|---|---|
| block | height 977449, hash `00000000000000000001b9b568f25bb0dbb631c3084632a22135c3bfcb0f11a7` |
| header | 80 bytes, `sha256d` recomputed from the receipt's own `header_hex` equals that hash |
| Merkle root | `4729e14ae4fdbc63766eab797e18be2da2150c24f8421c25cccb0485eba01bde`, byte-for-byte equal to the digest the attestation commits to |
| sources asked | blockstream.info and blockchain.info; **both agree** on hash and root, disagreement would be reported, never averaged |
| depth | tip heights read from both operators (both 977609); **160 confirmations** at fetch time, well past the 6 the CTS draft recommends as a floor - a dated snapshot, it grows every ten minutes |
| verdict | `HEADER_MATCHES_ATTESTATION`; `--check` re-derives header hash, root and depth arithmetic offline with no network |

What this buys and what it does not: the header bytes hash to the block hash, and
the root inside those bytes is the attestation's message, so "the proof names a
block that exists with that root" is now arithmetic rather than a sentence.

**2026-11-26, one command for the whole chain.** Three tools were three stops
on the same road, and a reader had to take on faith that their outputs joined.
`python tools/ots_full_verify.py --file <head> --proof <proof>` now runs them and
compares the seams byte by byte:

| seam | comparison |
|---|---|
| file -> proof | the digest the proof commits to equals the file's sha256 (`bound`) |
| proof -> header | the attestation's message equals the Merkle root inside the 80 header bytes |
| header -> block | `sha256d(header)` equals the block hash two operators agreed on |
| block -> segment | the segment starts one block above the attested height and links back to it |

Verdict `FULL_CHAIN_OF_EVIDENCE_VERIFIED` only when all four hold; otherwise it
stops at the seam that broke (`STOPPED_AT_PROOF` / `_HEADER` / `_CHAIN`). It runs
offline against the two committed receipts unless `--refresh` is asked for, and
it always prints what it did **not** check - starting with the global most-work
question, which stays unanswered until a node is supplied, and which comes **off**
that list the moment a receipt carries a node's answer instead of being left there
as decoration.

The node branch itself is not dead code: it is exercised against a JSON-RPC stub in
`tests/test_ots_node_evidence.py` - agreeing, disagreeing, and unreachable nodes
each get their own case. That proves the **wiring** (method names, auth shape, field
names, failure paths), not the node's honesty; the four lines a real Bitcoin Core
answers are still the missing witness, and saying they are not would be the exact
dishonesty this anchor exists to prevent.

**And both anchor types answer in that same verdict.** `--tsa-token` judges the
RFC 3161 token offline against the CA bundle shipped beside it, and the command
then says whether the *two* witnesses - a TSA that signs time, a Bitcoin block
that signs existence - cover the *same* digest:

| field | value |
|---|---|
| token | `tests/fixtures/anchor/freetsa.tsr`, Free TSA (`www.freetsa.org`) |
| genTime | `2026-11-17T08:11:35+00:00` |
| digest in token | `4ad23d91…7fd6e98` - byte-equal to the head, so it is the same digest OTS anchored |
| signature | verified against `freetsa_ca.pem`; a token that does not chain to that bundle stops the run (`STOPPED_AT_TSA`) |

A detail worth recording, because it changes how the test has to be written: a
single flipped byte in a `.tsr` does **not** necessarily invalidate it - most of
the file is certificate and unsigned attribute material. The test therefore
breaks the seam that cannot pass by luck: the trust anchor.

**And a third witness, with its limits printed in the same verdict.** `--rekor-entry`
judges the Sigstore entry offline: the body hashes this file, the embedded
signature verifies against the key in the entry, and the log's own
`signedEntryTimestamp` verifies against the published log key (log index
`3944456508`). It also carries forward the two things that entry does **not**
prove - the checkpoint signature and the inclusion proof - so a green verdict
never reads as more than it is.

**2026-11-26, the segment above the block is walked, not assumed.** Depth alone
is a number two servers told us. `--chain` walks *prev-hashes* from the tip they
reported down to the attested block and checks every header it passes
(`docs/anchor-ots-chain-977449.json`, 160 headers, 977450..977609):

| check | result |
|---|---|
| linkage | every header's prev-hash equals the next header's `sha256d` id - no gap, no substituted block |
| ids | each 80 bytes hashes to the id it was fetched as |
| proof of work | each header's digest is at or below the target its own `bits` field demands (little-endian, 0x17021673 at this height) |
| work above the block | `0x4ca3bff8b1fe1a4bd5c780` expected hashes - the floor a displacing chain must redo |
| verdict | `CHAIN_SEGMENT_VERIFIED`; `--chain-check` re-derives linkage, ids, targets and the work sum offline |

What is left, stated plainly: this proves the attested block is the ancestor of
the tip **the two operators exposed**, with 160 valid headers on top. It does not
enumerate competing branches, so "most work chain" in the global sense is still
not established - that needs a node that follows every branch, and no explorer
API does that. Anyone re-running later will get a longer segment; the receipt is
a dated snapshot, not a standing guarantee.

It still does **not** prove this block sits on the chain with the most work in the
global sense: the segment above it is verified header by header (see below), but no
competing branch is enumerated and no reorganisation risk is modelled. The servers
are trusted for *delivering bytes* only - never for deciding, because a wrong byte
fails a hash. That last gap needs a node, not another API.

Two corrections this section has to keep telling, both found on 2026-11-25:

1. The original table paired `tools/out/release_status.json` with the digest
   `4ad23d91…`. That digest belongs to `anchored_head.json`; the status file's
   own sha256 is `d805faa9…`. The pairing said "one digest" while anchoring
   two different files, so it is fixed above.
2. The 2026-11-17 proof (207 bytes) was a **bare timestamp tree, no magic
   header**. The official client answered "not a timestamp file", and our old
   reader - which fed the proof's own first 32 bytes back in as the digest -
   listed a pending attestation for `f0087497…`, a digest no committed file
   has. A proof nobody else can read is not an anchor. The bytes are kept, as
   a record of the defect, in `tests/fixtures/anchor/ots_head_20261117_invalid.ots`
   (sha256 `9c22be24…`), and a test asserts it is reported unreadable.

The rebuilt proof is a standard detached timestamp file: `ots info` prints
`File sha256 hash: 4ad23d91…` and `ots --no-bitcoin verify -f <head> <proof>`
reports pending confirmation for each calendar (`--no-bitcoin` deliberately hides the block attestation that the upgrade added). `tools/anchor_ots.py --verify`
now compares the digest the proof commits to with the digest of the file
(`bound`), and `tests/test_v14_ots_anchor.py` asserts: standard container,
digest equals `4ad23d91…`, at least two distinct calendars, and **no** block
attestation - so the claim cannot drift into "Bitcoin-anchored" by accident.
The test is skipped when the `opentimestamps` library is absent: the verifier
stays dependency-free.

### Checkpoint key: what was tried (2026-11-17, all negative)

| attempt | result |
|---|---|
| `GET /api/v1/log/publicKey` + note text with trailing newline / without / double newline / prefix line included | `InvalidSignature` |
| same key, SHA-256 / SHA-384 / SHA-512 | `InvalidSignature` |
| brute over note bodies (1-4 lines, 3 newline forms) | no match |
| `https://tuf-repo-cdn.sigstore.dev/targets/trusted_root.json` as the authoritative key source | HTTP 404 |

Sigstore's own guidance is that verifiers take log keys from a TrustedRoot
distribution (blog.sigstore.dev/rekor-v2-ga), and the key published at
`/api/v1/log/publicKey` verifies the entry SET but not this checkpoint. Until the
correct key and note format are established, independent inclusion verification
stays **blocked**, and this repository does not claim it.

### Key type

ECDSA P-256, key at `tools/out/rekor_ec_key.pem` (git-ignored, never commit).
Ed25519 was rejected twice by Rekor (`"SHA-256" not in [SHA-512]`, then
`invalid signature` after switching to SHA-512), so P-256 is the working path.
