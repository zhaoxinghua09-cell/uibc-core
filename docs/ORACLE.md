# A written oracle: all nineteen checks now have a case that must fail

`cross_check.py` asks whether two implementations agree. That question cannot rule out
both implementations misreading the specification the same way: agreement is evidence
of determinism, not of correctness.

`tools/oracle_check.py` asks a different question. The expected verdict and the expected
first failing check are written into the tool **before** it runs, from `fixtures/EXPECTED.md`,
the `duplicated` line in `benchmarks.md`, and the committed incidence table in
`docs/CHECK-MATRIX.md`. Each implementation is then judged against that table, not against
the other. A shared misreading fails here even when the two agree.

Run: `python tools/oracle_check.py` — exit 0 means every scored cell matched.

## Measured 2026-11-19, Windows, Python 3.13

**30 cases, 0 cells disagreeing with the oracle, `ORACLE: PASS`, exit 0.**
**21 cases predict a failure; 9 predict an acceptance.**

Tranche five took the accept side past plain packages, into the machinery the reject side
mutates: evidence types, lifecycle events, and a package carrying a resolvable anchor and
a resolvable policy artefact. **Three more accepting cases, and two defects found by doing
it** — both described below.

A table of cases that must fail says nothing about false alarms — a verifier that failed
everything would satisfy all twenty-one of them. So the tool also carries nine packages
with nothing wrong, built through the ordinary CLI path:

| case | shape | expected | both verifiers |
|---|---|---|---|
| accept-one-file | one evidence item | PASS | PASS |
| accept-many-files | five items | PASS | PASS |
| accept-unicode-names | Chinese and accented filenames, UTF-8 content | PASS | PASS |
| accept-binary | PNG-magic bytes and raw octets | PASS | PASS |
| accept-large-text | 200 KB single file | PASS | PASS |
| accept-resubmitted | sealed, then sealed again | PASS | PASS |
| accept-typed-evidence | three evidence entries with types ACTION / INPUT / OUTPUT | PASS | PASS |
| accept-lifecycle-events | three lifecycle events (UPDATE, DELEGATE, UPDATE) by the owner | PASS | PASS |
| accept-anchored-policy | two items, plus a resolvable anchor and a resolvable policy artefact | PASS | PASS |

**Measured false-alarm rate on this sample: 0 of 9.** That is nine shapes, not a
population — it says these nine are not rejected, not that false alarms do not happen.

## Two defects found by building the accept side

Writing a *legal* package is how these surfaced. Neither was visible from the reject
side, because the reject side only ever asks "is this caught".

**1. Closed vocabularies that the writer did not enforce.** `evidence --type X` accepted
any word and wrote it into the index; the verifier's S4 then answered **INCONCLUSIVE** —
"an unknown evidence type, not counted as checked". `event --type Y` was worse: L3
returned **FAIL**, so a typo in a field name was reported to the user as a bad package.
Two closed vocabularies existed and only the reader knew them.

Both are now `choices` in `uibc_core/cli.py` — the writer refuses the word and prints the
allowed list before anything is written — and `tests/test_vocabulary.py` fails if the CLI
and the verifier ever drift apart again, or if a refused write leaves a half-written
entry behind. The accepting cases `accept-typed-evidence` and `accept-lifecycle-events`
exercise the legal members of both vocabularies.

**2. An anchor over a single evidence item cannot resolve.** The anchor document carries a
Merkle proof, and a one-leaf tree has an empty proof, which `uibc_core.anchor` treats as
`proof is missing or empty` — so S15 answered FAIL for a package that was internally
consistent. This is a restriction, not a bug: a proof of inclusion in a one-element tree
is vacuous. It is recorded here because a user hitting it would have no way to tell that
from a broken package, and the accepting case therefore uses two items.

If either of these reads as a small thing: the whole point of the oracle is that the
accept side is where "the tool told me my package was bad" and "the tool and I disagreed
about a word" get told apart. Both defects were of the second kind.
Nothing here varies the policy, anchor or token artefacts, so the accept side is
thinner than the reject side and is reported as such.


| case | what is broken | expected | first failure |
|---|---|---|---|
| oracle-clean | nothing | PASS | — |
| oracle-tampered | bytes appended to an evidence file | FAIL | S4 |
| oracle-deleted | evidence file removed | FAIL | S4 |
| oracle-duplicated | index entry duplicated | FAIL | S5 |
| oracle-unsealed | `signatures/seal.json` removed | FAIL | S6 |
| oracle-s12-id-only | duplicate id, re-sealed, root repaired | FAIL | S12 |
| oracle-s01-undeclared-file | file added under `evidence/` | FAIL | S1 |
| oracle-s02-identity | `agent_id` does not match the index | FAIL | S2 |
| oracle-s03-calendar | 30 February in the lifecycle log | FAIL | S3 |
| oracle-s07-index-metadata | index metadata rewritten, content untouched | FAIL | S7 |
| oracle-s08-log-truncated | lifecycle log truncated under a checkpoint | FAIL | S8 |
| oracle-s09-rollback-pin | self-consistent package judged against another package's head | FAIL | S9 |
| oracle-s10-closure | `engine_build` dropped from the closure | FAIL | S10 |
| oracle-s11-duplicate-member | duplicate JSON member name | FAIL | S11 |
| oracle-s13-merkle-root | Merkle root replaced | FAIL | S13 |
| oracle-s14-base64-padding | base64 padding stripped | FAIL | S14 |
| oracle-s15-anchor-time | anchor dated 30 February | FAIL | S15 |
| oracle-s16-token-byte | one byte flipped in the RFC 3161 token | FAIL | S16 |
| oracle-s17-receipt-body | first receipt body edited | FAIL | S17 |
| oracle-s18-policy-artefact | policy artefact edited after sealing | FAIL | S18 |
| oracle-s19-regressed | sequence 3 presented against a remembered 5, both validly sealed | FAIL | S19 |

## The three cases that needed more than a mutation

- **S12** could not be reached by duplicating an index entry alone: repairing the root
  breaks the seal, so S6 answered first and the identifier rule was never exercised. The
  case re-seals after the edit. A case that "covers S12" while S6 does the failing proves
  nothing.
- **S9** cannot be triggered from inside one package. It needs an observation made
  elsewhere: the case builds a second, self-consistent package and pins the first one to
  its head.
- **S19** needs state carried across two runs, and the presented package must be
  **validly sealed both before and after** its sequence goes backwards — otherwise the
  interesting question ("is a properly signed package from earlier accepted now?") is
  replaced by a seal failure.

## The ordering rule is part of the oracle

The report is not printed in check order. On a duplicated package the reference verifier
returned `S11, S1, S2, S3, S4, S12, S7, S8, S5, S6` in that sequence. So "the first check
that failed" is undefined until the ordering is fixed, and a claimed first-failure code
with no stated ordering rule cannot be checked by anyone else. This tool fixes it:
**lowest check number that fails**.

The first draft took report order and duly reported a disagreement that did not exist.
Recorded here rather than quietly fixed.

## What the second implementation actually sees — a finding, not a footnote

The independent verifier implements V1–V6. Every case whose expected first failure is
above S6 is outside its sight, and the tool records that as `n/a` rather than scoring it.
`oracle-s12-id-only` shows what that means: the reference verifier returns `FAIL` at S12
while the independent one returns **`PASS`**. It is not lying. It does not implement the
identifier rule, so on a package that breaks only that rule it has nothing to object to.

Restating a qualitative note in `INDEPENDENCE.md` as a number: agreement covers
**6 of 19 checks**; 13 checks have one implementation only.

**These numbers are printed by the tool, not written in this document.** Each run ends
with four lines:

```
checks evaluated by the reference across these cases: 19 (S1, ..., S19)
rules the independent implementation emits: 9 (V1, ..., V9)
exact id-mapped pairs (CHECK_MAP): 6 of 19 (S1->V1, ..., S6->V6)
unmapped independent rules: V7, V8, V9
```

Two corrections are baked into that shape, both against earlier text here:

1. **`19` is not the number declared in the source.** It is the number that produced output
   on at least one of the thirty packages. A declared check that no package ever reaches
   looks exactly like a check that does not exist; this count is what tells them apart.
2. **The second implementation is not "V1–V6".** It emits nine rules: V7 (undeclared root
   files), V8 (index metadata digest) and V9 (checkpoint head) were added for parity
   against S1, S7 and S8 after the benchmark corpus showed them missing. They pair with
   *parts* of those checks rather than whole checks, so nine rules is not "nine checks
   covered" — but the earlier sentence in this document, which said the second
   implementation stops at V6 and that thirteen checks have one implementation only, was
   wrong, and it was wrong in this repository's own favour for the direction that
   mattered least.

Where a case's first failure lands on an unmapped rule, the verdict is still scored and the
code is printed as `V7 (unmapped)` rather than being counted as a disagreement: the two
numbers are answering different questions. `tools/oracle_check.py` prints all four lines
and `tests/test_oracle.py` fails if any of them changes without this document changing
with it.

## What the extra rules actually are — measured, not reasoned

The sentence above, "they pair with parts of S1/S7/S8", was another one I wrote. Each probe
now breaks exactly one thing and then **re-seals**, so the seal stays valid and S6 cannot
answer first. Whatever each side reports is then the rule itself:

```
measured: V7 fires alone -> reference FAIL S1;     independent FAIL V7
measured: V8 fires alone -> reference FAIL S7,S8;  independent FAIL V8,V9
measured: V9 fires alone -> reference FAIL S8;     independent FAIL V9
```

V7 ↔ S1, V8 ↔ S7 (S8 also fires), V9 ↔ S8, each measured on a package whose seal is valid.
Stronger than the wording it replaces, and repeatable by anyone.

## The finding a coverage percentage cannot express

```
measured: where the reference has a rule and the second does not
          (closure dropped, S10), reference says FAIL and the second says PASS
```

**The second implementation returns `PASS` on a package whose closure is incomplete**, because
it has no rule for the closure at all. Its `INCONCLUSIVE` discipline — which it does apply
to V6/V8/V9 when a judgement is impossible — covers only rules it possesses. Where it has
none, the overall three-valued verdict comes back green.

That is worse than being blind: blindness is `n/a`, this is an affirmative "no violation was
detected" about a package that violates a check.

**Fixed the same way it was found — by measuring the whole corpus instead of the one case.**
Across the 18 hostile packages the reference rejects, the second implementation used to say
`PASS` on **9** of them. Not nine demonstrations of a missing rule: nine greens a user could
act on.

The fix is a **scope guard**, not a rule. Before returning any verdict the second
implementation now lists the artefacts it has no rule for — attestation closure, anchor
resolution, external timestamp, receipt chain, policy artefacts, strict base64, duplicate
`evidence_id`, duplicate JSON member names — and if any is present it returns
`INCONCLUSIVE` naming them.

```
measured: of 18 hostile packages the reference rejects, the second
          implementation says PASS on 0 and declines to judge 9
```

**The guard lowers every number in this document rather than raising one.** It does not add
a check to the second implementation; it removes nine endorsements it was not entitled to
make. The accept side pays for it too: `accept-anchored-policy` now comes back
`INCONCLUSIVE` from the second implementation instead of `PASS`, because that package carries
anchors it cannot resolve. On the accept side the oracle therefore scores "no false alarm"
as **not FAIL** — declining to judge is allowed, rejecting is not — and records which it did.

## Per-check decidability — what "6 of 19 exactly paired" was hiding

The pair count is about identifiers. The question a reader actually has is behavioural: on a
package where the reference fails check S, does the second implementation ever reach `FAIL`?

```
measured: of 17 checks the hostile corpus exercises, the second implementation
          reaches 9 by rule (S1,S2,S3,S4,S5,S6,S7,S8,S12)
          and can never reach 8 (S10,S11,S13,S14,S15,S16,S17,S18)
```

S9 and S19 do not appear because the corpus contains no package that fails them — they are
exercised by separate blocks with bespoke construction, and a check that no case reaches is
indistinguishable from one that does not exist (which is the same lesson as the `19` count
above).

So the honest description of the second implementation is: **it can decide nine of the
seventeen checks this corpus exercises, and on the other eight it now says `INCONCLUSIVE`
instead of `PASS`.** Before the scope guard that same sentence ended with "and on the other
eight it said PASS", which is why the guard mattered more than any new rule would have.

`S6` and `S12` are partial rather than clean: S6 is detected on one package and declined on
another (that one also carried an unjudgeable artefact, so the guard answered first), S12 on
two of three. A per-check number that only counted "ever detected" would call both of them
covered; the table keeps the split.

## Two verdicts that say what they did not do

A verdict is read as broader than its evidence unless the report says otherwise. So the
second implementation now emits the same disclosure shape the reference does — `scope`,
`limitations`, `checked`, `not_checked`, `statement` — alongside its `unjudged` guard list.

```
measured: things each implementation declares it did NOT check - reference 5, second 11;
          7 of the second's are absent from the reference's list
          (base64,closure,duplicate evidence,duplicate json,merkle,policy,receipt),
          and the reference names 1 the second does not (lifecycle event signature)
```

Two things worth noticing in that line:

- **The reference's list is a constant.** It names the same five things on every package,
  because they are standing non-goals of the spec. It does not say what *this run* failed to
  evaluate. The second implementation's list is built per run: standing non-goals plus
  whatever the guard found in the package handed to it.
- **The asymmetry runs both ways.** Seven things only the second implementation admits it
  skips, and one thing only the reference admits (`lifecycle event signatures`, which the
  second implementation genuinely does not verify). Declaring more is not the same as being
  more thorough; it is the same as being more legible.

Neither list makes a verdict stronger. They make it narrower, which is the only honest
direction for a list of non-claims.

## The corpus is data now, not a program

Every measurement above runs inside one process, on packages that exist only for the
duration of a test. That is useful and it is not consumable: an outsider cannot run our
tooling to check our answers.

`python tools/oracle_check.py --emit conformance/oracle` writes 28 packages, their
throwaway keys and their expected verdicts to disk — 239 files, 287 KB. Then it
re-verifies the **written copies**, not the in-memory ones, and refuses to report
success if the bytes on disk no longer produce the declared answers.

```
emitted 28 cases to conformance/oracle; round-trip mismatches: 0
```

It lands in a subdirectory of `conformance/` on purpose: that directory already holds
a released archive (`uibc-conformance-0.4.0.zip` and its `manifest.json`), which is a
packaging artifact, not this corpus. Putting the two in one folder invited exactly the
mistake I made while writing this — overwriting the release to make room for the cases.

`tests/test_conformance_corpus.py` runs the same comparison on every CI run, so the
committed answers cannot drift away from the committed bytes. A corpus whose answers can
drift is worse than no corpus, because it certifies something it never checked.

**Two of the thirty oracle cases are not in the corpus.** The S9 and S19 blocks build
their packages with bespoke steps rather than through the shared builder; they stay
code-only, and the corpus README says the corpus has 28, not 30.

The README also states what the corpus does not prove, in its own words: these packages
were produced by this project, pass them and you have shown conformance to this reading
of the spec — not to a regulator's requirement. Anything a verifier does that is not in
here is unmeasured, not impossible.

## What this is not

- **Not independent judgement.** Expectations were drawn from documents this project
  wrote, and the S7–S18 rows come from `docs/CHECK-MATRIX.md`, which shares provenance
  with the mutation functions in `tools/outsider_audit.py`. These rows lock verdicts
  and first-failure codes against regressions; they do not constitute an outside opinion.
- **Not exhaustive.** One mutation per case, one host, one Python version. A mutation
  that breaks several things at once has no single expected first failure, so none is
  claimed.
- **Predicted failures, not predicted passes.** Coverage on the reject side means "each
  check can be made to fail on purpose and its first-failure code is written down". The
  accept side is nine ordinary shapes with zero rejections; that is a floor for the
  false-alarm rate, not a rate.

Adding a case means writing the expected verdict and first failure down **first**. Editing
the table after seeing an output is the failure mode this tool exists to prevent.
