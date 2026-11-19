# The first anchor that lives in this repository

    anchors/001/anchor.json
      seq            1
      key_id         75935681213e00a1…
      checkpoint_head sha256:2935c3f497b00949bffc84b0b6f8c5db6a41ce192864b11b089a3aa4607323ef
      anchor_digest  d01daa66232c69f42be52a393df38e63e0d673072039e6a4f0b5088140c9506d
      timestamp      none

Until now every anchor this project described lived in a diagram. There is now
one in the tree, signed by a key generated for it, and CI verifies it on every
push (`tests/test_published_anchor.py`, five checks, 0.37 s, offline).

## Three verdicts, two implementations

```
$ python3 tools/anchor_check.py anchors/001
seq: 1
VERDICT: ANCHORED
trust_level: anchored   result: PASS

$ python3 tools/anchor_chain.py anchors/001 --expect-latest 1
VERDICT: CHAIN OK    anchors: 1 (seq 1..1)

$ node tools/verify-js/chain.mjs anchors/001 --expect-latest 1
VERDICT: CHAIN OK    implementation: verify-js (independent of uibc-core)
```

## It also has to fail when it should

One byte appended to `package/evidence/files/run-summary.txt`:

```
result: FAIL
  - S4 evidence integrity: hash mismatch on 'files/run-summary.txt'
  - S8 package checkpoint head: state does not match the sealed checkpoint_head
  - S9 head pinned out-of-band: package checkpoint does not match the pinned head
```

Three independent checks fire, which is why the tamper probe is a test rather
than a paragraph: a verifier that only ever says PASS is indistinguishable from
one that always says PASS.

## What it is not

The pinned package is the demo package, not `dist/uibc-core-0.2.1.zip` and not a
v0.4.0 build. The key is new — the demo seed is public and must never sign a
publication — but the package is the fixture, so the head is the number the demo
pages already print.

And the anchor sits in the same channel as the package. A real anchor travels
over a channel the package cannot reach, so that replacing the package cannot
replace the anchor. Publishing both in one repository proves the mechanism; it
does not prove separation. That separation is a decision, not a commit: **which
channel** — a release page, a DNS TXT record, a mailing list, or a second
repository that mirrors nothing but anchors.

## Withdrawing

`git rm -r anchors/001` withdraws it. The history keeps the fact that it
existed: withdrawal stops an anchor being current, it does not stop it having
been published.
