# Delegation: who was allowed to run this, and until when

A run receipt (`docs/RECEIPT-FORMAT.md`) says a run happened and who ran it. It does
not say that the runner was permitted to. A stranger replaying our corpus under their
own name is a fine thing; a stranger replaying it *on behalf of a lab whose name they
borrowed* is not, and nothing in the receipt distinguishes the two.

`tools/check_delegation.py` reads one record that does, and refuses the five ways
such a record is usually worthless.

## The record

```json
{
  "kind": "uibc-delegation-v0",
  "delegator": {"name": "…", "id": "…"},
  "delegatee": {"name": "…", "id": "…"},
  "scope": {"corpus_sha256": "<64 hex>", "cases": "all", "cases_total": 294,
            "max_runs": 1, "directed": false},
  "window": {"not_before": "2026-11-20T00:00:00Z", "not_after": "2026-12-20T00:00:00Z"},
  "nonce": "…16+ chars…",
  "chain": {"depth": 1},
  "signature": {"alg": "ed25519", "key_id": "…", "public_key_b64": "…", "signature_b64": "…"}
}
```

The signature covers the canonical JSON of the record with `signature` removed — the
same canonicaliser the receipts use, so the signed bytes are recomputable by anyone.

## What it refuses, and why each one matters

| refusal | what it catches |
|---|---|
| delegator id == delegatee id | self-authorization: the only signature that always exists |
| same name, different id | a borrowed lab name with no shared identity |
| window longer than 90 days, or already closed | a permission that outlives the project it was granted for |
| `cases` beyond `cases_total`, or listed twice | a scope that quietly covers more than the corpus it names |
| `chain.depth` ≠ 1, or any `parent` / `issued_by` field | re-delegation: one hop, and the second hop is where accountability dissolves |
| signature does not verify | a record that was typed, not signed |

Plus two that are cheap because they were paid for earlier: `scope.corpus_name` is
refused (names drift, only the digest is checked), and `scope.directed` must be
present — a directed run that does not say it is directed is a blind run wearing the
wrong label.

With `--receipt receipt.json` the record is also checked against the run it claims to
authorize: same corpus digest, and the runner is the delegatee rather than anyone else.

## The hole this check found in itself

The first version verified the signature against the public key **carried inside the
record**. That proves the record was signed by whoever wrote it, and nothing about
who that is: anyone can generate a key, delegate to themselves under a borrowed name,
and produce a record that verifies. The checker now says so out loud —

```
ACCEPTABLE WITH A CAVEAT
 ! identity unbound: the public key travels inside the record … pass the delegator's
   public key to bind it
```

— and only drops the caveat when given the delegator's key out of band
(`--delegator-key <hex>`). A signature that verifies against a key the record supplies
is a checksum, not an authorization; the doc keeps that sentence so the next reader
does not have to rediscover it.

## What this version is not

Stated as limits, not as future work:

- **one signature, not a threshold.** There is no m-of-n quorum and no group signature.
  A single compromised key produces a valid record.
- **no revocation registry.** A wrong delegation is undone by not accepting the record;
  there is no published list of withdrawn ones, and the checker cannot see a revocation.
- **`id` is a string, not a credential.** Nothing binds it to a key except the signature
  over the record itself; two parties can both call themselves `lab-x` with different ids
  and only the digest discipline keeps them apart.
- **no anonymity.** The record names both sides in the clear, by design.

Peers in this space run threshold authorization and multi-signature custody; those are
the three lines above, and they stay recorded as differences rather than as parity.

## Measured, 2026-11-20, against the real corpus digest

One record issued for corpus `711fa82c…` (the 0.4.1 archive), window 20 Nov – 20 Dec:

```
$ python tools/check_delegation.py delegation.json --at 2026-11-25T00:00:00Z
ACCEPTABLE WITH A CAVEAT — Lab A -> Node B, corpus 711fa82c9f18…, cases all 294, 1 run(s),
  window 2026-11-20T00:00:00Z to 2026-12-20T00:00:00Z, key 56475aa75463474c
 ! identity unbound: … pass the delegator's public key to bind it

$ … --delegator-key <hex>
ACCEPTABLE — … key 56475aa75463474c

$ … --at 2027-01-05T00:00:00Z
NOT ACCEPTABLE
 - the window closed at 2026-12-20T00:00:00Z
```

Three runs, three different verdicts, from the same bytes — which is the point: the
verdict is a function of the record and the moment, not of a sentence someone wrote.

## What has actually been run

`tests/test_delegation.py` issues records with a throwaway key and then breaks them one
field at a time: each of the five refusals, a one-byte change to the signed body, a
record signed by a different key judged with and without the known key, a receipt from
the wrong runner, and a record whose window is judged at three different times (before,
inside, after). Measured locally on 2026-11-20: **16 passed**.

There is **no delegation record in this repository yet** — no external node has asked
for one. An empty set of records means no one has been delegated anything, not that
delegation works.
