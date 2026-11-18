# A second implementation, in a second language

`tools/verify-js/verify.mjs` checks a UIBC package with nothing but Node's
standard library. It imports no `uibc-core`, runs no Python, and installs no
npm package: RFC 8785 canonical JSON, SHA-256, and the package's own layout.

The point is not that a second implementation exists. The point is that it can
**disagree**, and that when it does, the disagreement is a finding rather than
an inconvenience.

## What it decides

Eighteen of the nineteen checks: S1 structure, S2 identity, **S3 the lifecycle
state machine** (L1-L7) **and its semantic layer** (L8-L12: timestamps that
parse and do not run backwards, actors that are principals of this agent,
ACTIVATE once, a contiguous sequence_number), S4 evidence integrity,
S5 evidence root, S6 the seal (for Ed25519, where the public key is in the
package; an HMAC seal is INCONCLUSIVE because it needs the owner's key), S7
index metadata (shape **and** the digest carried in the manifest), S8 the
package checkpoint, **S9 the out-of-band pin** (supplied as `--expect-head`, never
read from the package), S10 the closure declaration, S11 strict serialization,
S12 timestamps and counts, S13 Merkle inclusion proofs (RFC 6962, recomputed
from the files), S14 strict base64, S15 anchor resolution, **S16 external
timestamps** (RFC 3161, verified with Node's own crypto - no npm package, no
shared code), S17 the receipt chain and S18 policy artefacts.

The one check not here is S0, which is not a check of the package but of the
verifier: it appears only when something throws, so a sound package has no S0
line to compare.

It therefore **never returns PASS** for a sound unsigned package: INCONCLUSIVE,
because nothing was found wrong and nothing was proven either.

### This is now enforced, not asserted

Until `tools/assert_second_impl.py` existed, "seventeen of nineteen" was a
sentence in a document. Nothing stopped it from becoming false the moment
somebody edited `uibc_core/verify.py` without touching
`tools/verify-js/verify.mjs`. The CI job `second-implementation` now runs that
script on every push and pull request, and it fails the build when:

* a package the suite expects to accept is rejected by the second
  implementation (a verifier that cries wolf teaches people to ignore it);
* a package expected to be refused fails for a reason none of its expected
  checks name (coincidence is not coverage);
* a package expects a check the second implementation does not claim to
  cover -- a check the Python side gained and the JavaScript side never carried.

It deliberately does **not** require the identical FAIL set. The two
implementations legitimately differ: on a corrupted evidence file JavaScript
reports S5 as well as S4, and both are true about that package. Demanding
set equality would force one of them to under-report in order to match the
other, which is the opposite of what a cross-check is for. Five of the
thirty-six packages currently differ this way, listed as measured rows in
`tools/cross_impl_check.py --json`.

The script was verified the only way that counts: by breaking the second
implementation on purpose. With S15's verdict forced to pass, it reports the
four anchor packages by name and exits 1; with S15 removed from the covered
set, it reports the same four as out of scope and exits 1. Both restored runs
print `36/36` and exit 0.

## Measured

```
strict 36/36   refused 30/36
```

| | value |
|---|---|
| packages in scope | 36 of 36 (6 correct + 30 whose expected check is among the fifteen) |
| out of scope | 0 |
| identical FAIL set to Python | 36 |
| named the same expected check | 30 (+6 positives) |

Two implementations written from the specification, sharing no code, agreeing
on which packages are broken and for which reason — that is the difference
between "we have tests" and "anyone can check".

## Four bugs the exercise found in its own work

1. **A mislabelled case.** The "one more declared evidence file" package wrote
   its declaration under the wrong member name, so the file was undeclared
   while the case name said otherwise. The JS verifier refused it, which is how
   it came to light. The case now grows the package through the shipped CLI.
2. **A silent catch hiding a defect.** The metadata-digest comparison caught an
   exception (an `undefined` member is not JSON) and the `catch` made a tampered
   note look fine. Fixed by mapping absent members to `null`, which is what the
   Python side writes.

3. **One root cause scored twice.** This verifier computed the evidence root
   from hashes it had just shown to be wrong and reported S5 as a second
   failure. The Python one skipped S5 when S4 failed, which is the right
   semantics: the second statement is not a second finding, it is the same
   finding. S5 now reports INCONCLUSIVE in that case, on both sides.
4. **A hole in the first implementation.** The Python verifier never compared
   `manifest.evidence_count` with the number of index entries, so a package
   claiming two entries and shipping one passed it. The JavaScript one did
   compare them, the disagreement showed up in the cross-check, and the fix
   went into Python - a hole found by the implementation that was built to
   check it, which is precisely what a second implementation is for.

All four were hypothetical until they were measured, and all four came from
running a second implementation against the same corpus. That is the only way
this kind of defect surfaces.

## What it is not

- Not a replacement: this is one implementation, not a standard. One check
  (S0) has no second opinion, and agreement between our two implementations is
  convergence, not corroboration by an outsider.
- Not a ratification: agreeing with ourselves is not third-party witnessing.
  The external witness count is still zero, and this document does not change it.
