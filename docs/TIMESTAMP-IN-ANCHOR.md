# The anchor pins a key and a head. This adds a moment.

`docs/PUBLISHER-IDENTITY.md` closed the forgery envelope's row C: pin the key,
pin the head, and a stranger cannot substitute a package. What remained open is
smaller and stranger — **the anchor says nothing about when.**

A head is a digest. A digest has no date. Two packages with the same head are
indistinguishable, and a publisher can produce a self-consistent package today
and claim it existed last year. Every check in this repository reads bytes; none
of them reads a clock we do not also control.

So `anchor.json` gained one optional block:

```json
"tsa": {
  "covers": "anchor_digest",
  "token_b64": "…",
  "cabundle_b64": "…"
}
```

## Two modes, and the difference is reported, not blurred

| `covers` | what the token is over | what it proves | binding reported |
|---|---|---|---|
| `anchor_digest` | SHA-256 of JCS(`agent_id`, `key_id`, `pubkey_b64`, `checkpoint_head`) | **this claim existed at that time** | `anchor_digest` |
| `file` | whatever `data_sha256` names, e.g. a release-status file | some bytes existed; nothing about the claim | `unbound` |

`anchor_check.py` prints which one it got:

```
$ python3 tools/anchor_check.py bundle/
VERDICT: ANCHORED
trust_level: anchored   result: PASS
timestamp: valid (unbound) at 2026-11-17T08:11:35+00:00
```

`unbound` is the honest word for the second mode. A token over a release-status
file is worth having — it dates *a publication* — but it does not date the four
values that decide whether the package is the publisher's.

## Offline, and that is the whole point

The token is checked against the CA bundle carried **in the anchor**, so a later
network change cannot rewrite history. `uibc_core.tsa.verify_token` does the work;
`anchor_check.py` calls it and refuses when either half is missing:

- no token → the anchor reports `timestamp: none` and the verdict drops to
  `NOT ANCHORED` if nothing else anchored it;
- token but no CA bundle → **FAILED**, "an unchecked timestamp is not a timestamp";
- token over other bytes → **FAILED**;
- `covers: anchor_digest` with a token that covers something else → **FAILED**.

## What is actually verified here

`tests/test_anchor_check.py` runs a **real FreeTSA signature** — the token at
`tests/fixtures/anchor/freetsa.tsr`, issued 2026-11-17T08:11:35Z over
`anchored_head.json` — entirely offline, against the shipped CA bundle. So the
positive path is a TSA we do not control, on bytes we did not design.

That is also the limit of the fixture: it covers a release-status file, so it can
only exercise `covers: file`. The `anchor_digest` path has full negative coverage
and needs a live stamp for a positive one:

```
$ python3 tools/make_release_bundle.py --out dist/r1 --seed-hex $SEED
  anchor_digest  6ea89f63ad52830b4a33bf268e72481fb844d4a9dd519f662dbe81e8a5992374
$ # stamp that digest at a public TSA, then
$ python3 tools/make_release_bundle.py --out dist/r1 --seed-hex $SEED \
      --tsa-token anchor.tsr --tsa-cabundle tsa-ca.pem
```

A live stamp is a network call to a third party, which is why CI does not do it
and the repository does not carry a fresh one.

## Status

No published anchor carries a timestamp. `docs/IMPLEMENTATION-STATUS.md` still
reads zero. What changed is that the field can now be filled, checked offline,
and **fail loudly when it lies** — three properties that were previously only
designed.
