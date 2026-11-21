# anchors/001 — the first anchor published inside this repository

    seq            1
    key_id         75935681213e00a1…
    checkpoint_head sha256:2935c3f497b00949bffc84b0b6f8c5db6a41ce192864b11b089a3aa4607323ef
    anchor_digest  d01daa66232c69f42be52a393df38e63e0d673072039e6a4f0b5088140c9506d
    timestamp      none

Signed with a key generated for this publication and not committed anywhere.
`seq` is 1, so there is no predecessor to check; the next anchor will name
this digest.

## What it pins

The package in `./package` — the same demo package the repository's own
documentation describes. Its head is `sha256:2935c3f4…`, the same value the
demo pages print, because it is the same package; the difference from those
pages is the **key**: the demo seed is public, this one is not.

## Verify it, with three checks

```
python3 tools/anchor_check.py anchors/001            # VERDICT: ANCHORED
python3 tools/anchor_chain.py anchors/001 --expect-latest 1   # CHAIN OK
node tools/verify-js/anchor.mjs anchors/001         # CHAIN OK, no shared code
```

No network. No install. The JavaScript one is a second implementation written
from the prose, so agreement between the two is the claim being made.

## What this is, and what it is not

**Is**: the anchor mechanism running once inside the real repository, on a real
package, with a key that only this publication holds. A stranger who clones this
repository can run the three lines above and get the same three lines back.

**Is not**: a release, and not a claim of adoption. It pins a demo package —
not `dist/uibc-core-0.2.1.zip`, not a v0.4.0 build. Anyone can reproduce the
head, because the package is in this repository and its contents are fixed.
What they cannot reproduce is the signature, and that is the point of a key.

**Known weakness, stated rather than hidden**: the anchor and the package sit
in the *same* channel — this repository. A real anchor is supposed to travel
over a channel the package cannot reach (a release page, a DNS TXT record, a
mailing list), so that altering the package cannot alter the anchor. Publishing
both here demonstrates the mechanism; it does not yet demonstrate separation.
That needs one decision that is not mine to make: **which channel**.

## Withdrawing it

Deleting `anchors/001/` withdraws the anchor. The git history keeps the fact
that it existed, which is what withdrawal means for an anchor: it stops being
current, it does not stop having been published.
