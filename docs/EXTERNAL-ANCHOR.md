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

### OpenTimestamps: the second anchor type (2026-11-17)

The ASQAV compliance profile wants "RFC 3161, OpenTimestamps, or both". We
submitted a head digest to a public OTS calendar. Read back on 2026-11-21, that
digest is **not** the one the TSA token covers, so the two anchors did not cover
one digest, and this paragraph said they did until it was corrected. On the same
day a second proof was taken on the TSA head itself, which is what makes the
claim true:

| item | value |
|---|---|
| RFC 3161 head | `tests/fixtures/anchor/anchored_head.json` (the released status bytes), digest `4ad23d9153c3…7fd6e98` |
| RFC 3161 | Free TSA token, `genTime=2026-11-17T08:11:35Z`, signature verified offline |
| OTS 2026-11-17 | `alice.btc.calendar.opentimestamps.org`, proof `tests/fixtures/anchor/ots_head.ots` (207 bytes) |
| what that proof anchors | its own first message, `f0087497…b808f120` — **not** `4ad23d91…6fd6e98`, and not the hash of any committed `tools/out/release_status.json` |
| its container | a bare serialized tree with no standard header, so the official `ots` client refuses it ("is not a timestamp file") |
| OTS 2026-11-21 (re-stamp) | `tests/fixtures/anchor/anchored_head.json.ots`: taken on the TSA head digest itself, in the standard container, so it binds and the official client can read it. Re-stamped again on 2026-11-25 (740 bytes) so that **all three** public calendars that answered sit in one proof; the earlier 237-byte single-calendar version is in git history, not in the tree |
| what either proof says today | **pending calendar attestations, zero Bitcoin block attestations** (the 2026-11-25 proof carries three, one per calendar) |

That is the honest status: a calendar attestation says the calendar had this
digest at submission time, which is weaker than a block attestation. The
upgrade path (`tools/anchor_ots.py --upgrade`) needs hours to days, and the
Bitcoin block header is not cross-checked here because that requires a chain
source. `tests/test_v14_ots_anchor.py` asserts the proof contains **no**
block attestation, so the claim cannot drift into "Bitcoin-anchored" by
accident. The test is skipped when the `opentimestamps` library is absent: the
verifier stays dependency-free.

The 2026-11-21 assertions make the difference mechanical: the older bare proof
is checked to carry `f0087497…`, to differ from the TSA head, and to bind to
nothing; the re-stamp is checked to be a standard container that binds to the
TSA head; and both are checked to carry no block attestation.
`tools/anchor_ots.py --verify FILE --proof P` refuses a proof that does not
answer for `FILE` (`the proof answers for another digest, not for FILE`).

What would upgrade either proof: `--upgrade` until a Bitcoin block attestation
arrives, which needs hours to days, and then a block-header cross-check against
a chain source - neither of which this repository can honestly claim today.

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
