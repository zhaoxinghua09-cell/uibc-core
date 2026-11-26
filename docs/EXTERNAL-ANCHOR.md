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
| OpenTimestamps | three public calendars (`alice.btc`, `bob.btc`, `finney.calendar.eternitywall`), proof `tests/fixtures/anchor/ots_head.ots`, 635 bytes, stamped 2026-11-25 |
| what the OTS proof says today | **three Bitcoin block attestations, one per calendar, all naming block 977449**, with the three pending calendar attestations still listed beside them. The block *header* is not fetched or checked against a chain source here, so what the proof says is `bitcoin_attested`; that its header matches Bitcoin is not asserted |

That is the honest status: a calendar attestation says the calendar had this
digest at submission time, which is weaker than a block attestation. The
upgrade path (`tools/anchor_ots.py --upgrade`) asks each calendar the proof
names; it needs hours to days, and the Bitcoin block header is not
cross-checked here because that requires a chain source. A block attestation had to *appear in the proof* before this row could change, and on 2026-11-26 it did: both proofs were upgraded and now carry `BitcoinBlockHeaderAttestation` at height 977449 from each of the three calendars.

**2026-11-26, the upgrade landed.** `tools/anchor_ots.py --upgrade` was run against both proofs (`tests/fixtures/anchor/ots_head.ots`, 635 B before the upgrade, and `tools/out/release_status.json.ots`); re-verifying both now lists three `BitcoinBlockHeaderAttestation` entries at **height 977449** and still lists the three pending calendar attestations. Read straight from the proof with the official library (the CLI's `--verify` reports the attestation but prints a blank height -- a gap in the reporter, not in the proof). Nothing here claims the header was checked against Bitcoin: that needs a chain source, and this repository still does not fetch one.

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
reports pending confirmation for each calendar. `tools/anchor_ots.py --verify`
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
