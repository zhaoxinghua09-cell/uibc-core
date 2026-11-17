# External anchor (RFC 3161) — what we now have, and what it does not prove

## Why this layer existed at all

`S13` proves a leaf is inside a tree **we built**. `S9` proves a head was pinned
**somewhere else of ours**. Neither proves the tree existed at time T, because we
are the only witness to our own clock. That is exactly the gap arkforge closes by
anchoring to Sigstore Rekor and calling it a "third independent witness".

We now have an equivalent witness for the timestamp question, via RFC 3161.

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
`https://rekor.sigstore.dev`. This is the layer arkforge uses; it closes the same
door, not a wider one.

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

### Key type

ECDSA P-256, key at `tools/out/rekor_ec_key.pem` (git-ignored, never commit).
Ed25519 was rejected twice by Rekor (`"SHA-256" not in [SHA-512]`, then
`invalid signature` after switching to SHA-512), so P-256 is the working path.
