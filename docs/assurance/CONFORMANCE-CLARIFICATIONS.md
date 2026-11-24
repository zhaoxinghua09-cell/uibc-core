# Three conformance clarifications, stated outside the shipped archive

The 0.5.0 archive is published and pinned. Its bytes are what a stranger downloads and
checks; adding sentences to `conformance/manifest.json` inside the repository would
desynchronise the tree from the archive without changing a single downloadable byte —
a silent failure dressed up as a documentation fix. So these three readings are recorded
here instead, and belong to the next archive (0.5.1) rather than retrofitted into 0.5.0.

They exist because a blind review of the 36 shipped cases converged on them: an
independent reviewer, given only each case's `attack` and asked whether the package must
be refused, disagreed with the suite in exactly these three places until they were stated.

1. **Growth is not tampering.** A package may append evidence after sealing, provided every
   new file is declared in the evidence index. Declared growth must not be refused.
2. **"Cannot recompute" is a refusal condition.** A package whose anchor points at a root
   this verifier cannot recompute must be refused. Treating it as "unknown" is a pass in
   disguise.
3. **A shipped public key counts as available.** A package sealed with an asymmetric key
   whose public key ships inside the package, and whose signature verifies against it, must
   not be refused. "No key available" applies only when no public key is shipped.

None of the three changes an expected verdict on the shipped 36 cases; they remove the
ambiguity that let a reasonable reader land on the opposite answer. That is also why they
cannot be smuggled into 0.5.0: the cases would keep their verdicts while the archive claimed
to have always said so.
