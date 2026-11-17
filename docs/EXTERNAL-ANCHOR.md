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
