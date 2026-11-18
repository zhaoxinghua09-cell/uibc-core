# A forgery that agrees with itself

Nineteen checks are measured, and every one of them has an artefact that makes it fail. Fourteen mutations cancel nowhere in 455 combinations. **None of that answers the question an attacker actually asks:** can I rewrite the evidence and repair every internal consistency the rewrite breaks?

Repairing is arithmetic. The content hash, the evidence root, the index digest and the checkpoint head are all public functions of bytes the attacker owns. So the real question is not whether a package can be made self-consistent - it can - but **which check still has something to say after it is**.

```
$ python3 tools/composed_forgery.py
```

| # | attack | verdict | trust level | what speaks |
|---|---|---|---|---|
| A | rewrite one evidence file, touch no declaration | FAIL | unattested | S4 - the rewrite contradicts a declaration nobody updated |
| B | rewrite it and repair hash, root, index digest, checkpoint head | INCONCLUSIVE | unattested | S6 - the owner's seal cannot be checked, so nothing is asserted |
| C | B, then re-sign with the attacker's own fresh key | PASS | unanchored | **nothing** - the package is self-consistent and signed |
| D | C, and the verifier pins the publisher's public key | FAIL | unattested | S6 - the signature is not from the pinned publisher |
| E | C, and the verifier pins a head published elsewhere | FAIL | unanchored | S9 - the state is not the one that was published |
| F | B, and the attacker simply deletes the seal | INCONCLUSIVE | unattested | S6 - losing a signature cannot improve a package's standing |

## The line that matters

**Row C: `PASS`, `unanchored`.** A stranger who never held the publisher's key rewrites the evidence, repairs every declaration, signs with a key of their own, and the verifier says the package is clean.

That is not a defect in the verifier - the signature really is valid. It is the definition of what a signature proves: **these bytes carry that key's signature**. It does not prove the publisher wrote them, and no check that reads only the package can make it prove that. That is why the verdict carries `unanchored` beside `PASS`, and why row D and row E exist: pinning a key or a head from somewhere the artifact does not control is the only thing that turns the sentence around.

## Why this is worth publishing against ourselves

A verifier that only reports what it catches looks strongest exactly where it is weakest. The five rows above are the alternative: show the attack that works, name the coordinate at which it stops working, and let a reader check both. `tests/test_composed_forgery.py` freezes all six outcomes, including row C.

## What would actually close row C

1. Publish the signing public key where the artifact cannot reach it (this repository's release page, a DNS record, a transparency log), then verify with `--pubkey`. That is row D, and it works today.
2. Publish the checkpoint head at submission time and verify with `--expect-head` (row E). A self-consistent forgery cannot reproduce a head it did not write.
3. Anchor the head to an external timestamp (S16) or receipt (S17) so the head itself has a witness.

Until at least one of these is done for a given package, the honest reading of a PASS is exactly what the verdict says: internally consistent, unanchored. `docs/IMPLEMENTATION-STATUS.md` counts how many packages in the wild have done it (currently zero).
