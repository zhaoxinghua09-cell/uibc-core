# Anchor: what is frozen, what is only submitted

`ROOT-28a23ff.txt` is the root this repository's claims were frozen against on 2026-11-24,
and `ROOT-28a23ff.txt.ots` is the OpenTimestamps proof of that root.

## What the two files say

- Commit `28a23ff08ea02543042a65d3a457f5eeffd2627b`, tree `d4656d14d8301837ef387ef0e0f3618f60548bd7`.
- `sha256(ROOT-28a23ff.txt) = 20c8d31b07bd34a7617746508c1127d9c6d41ef4b29265c28bdfbeaa3015bf72`
- Submit time: 2026-11-24 18:30 +08:00, to four calendars (`a.pool.opentimestamps.org`,
  `b.pool.opentimestamps.org`, `a.pool.eternitywall.com`, `ots.btc.catallaxy.com`).

## What the proof does and does not establish

`ots info` on this file shows four calendar receipts and `verify PendingAttestation`.
`ots upgrade` reports, on all four:

```
Pending confirmation in Bitcoin blockchain
```

So: **the root existed no later than the submission time, as witnessed by four independent
calendars, and the Bitcoin attestation is not yet in hand.** Anyone can re-check with
`ots verify ROOT-28a23ff.txt.ots -f ROOT-28a23ff.txt`; the answer today is "pending", and
that is what this repository will keep saying until `ots upgrade` completes.

## What we did not get, and will not pretend we got

An RFC 3161 timestamp from a public TSA. Attempts against four endpoints on 2026-11-24:

| Endpoint | Result |
|---|---|
| `freetsa.org/tsr` | 404 |
| `timestamp.digicert.com` (http) | 400 |
| `timestamp.digicert.com` (https) | connection timed out |
| `timestamp.sectigo.com` | 404 |

None produced a `.tsr`. There is no TSA anchor for this root, and the standing registry
keeps `RFC3161 = rejection` rather than quietly dropping the row.

## Why the root is in the repository at all

GitHub itself is a weaker but real witness: the commit that carries this file is
content-addressed and publicly timestamped by a third party. Two independent witnesses —
one cryptographic-but-pending, one hosting-but-immediate — are better than one claim that
says "anchored" with nothing attached.
