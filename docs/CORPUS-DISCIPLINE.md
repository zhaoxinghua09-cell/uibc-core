<!-- SPDX-License-Identifier: Apache-2.0 -->
# Six rules a test-vector set has to meet before anyone should trust it

This page exists because our own vector set failed four of these six rules on
2026-11-20 and 2026-11-21, and none of the failures were visible from the outside. If you are
building a conformance corpus — RFC 9162, SCITT, JOSE, anything — you can adopt
these rules directly, and you can mark us against them with the commands named
under each one.

The framing is deliberate: a rule is worth stating only if **violating it is
observable**. Each rule below names the defect that violating it produced here,
so you can judge whether the same defect is plausible in your set.

---

## Rule 1 — The corpus must be the output of one script, byte for byte

**What it means.** Every vector file, the manifest, and the checksums are
produced by a single builder. Running the builder must reproduce the committed
tree exactly. Nothing in the corpus may be "added by hand afterwards".

**What we violated.** Our `CASES` table knew about five vectors while the
committed manifest listed six: one vector had been appended to the manifest by
hand. Our `--check` mode read only the manifest, so it could never see the gap.
A single `build` run would have deleted that vector from the manifest and left
its directory orphaned — the corpus would have *quietly shrunk* while every
check stayed green.

**How to test a set for it.** Rebuild into a separate directory and compare
bytes in both directions:

```
python tools/build_scitt_vector_package.py --check-drift
```

The check is two-directional on purpose. One direction alone is not enough: a
committed file the builder never produces (our defect) is invisible if you only
compare files the builder emits.

**And:** make the count assertion derive, not assert. Ours used to say "there are
six". It now says "count equals the number of cases the builder knows, and it may
not fall below a floor" — a literal count hides exactly the drift it should catch.

---

## Rule 2 — Bytes must not depend on the platform that produced them

**What it means.** A corpus that claims to be reproducible everywhere cannot have
platform-dependent bytes: not line endings, not key order, not float formatting.

**What we violated.** The builder wrote files through Python text mode without
`newline="\n"`, so the same script produced CRLF on Windows and LF on Linux. The
committed blob happened to be CRLF, which means **the drift check passed on the
author's Windows machine and failed on every Linux CI runner**. The package
README said "reproducible on any platform" while that was false.

**How to test a set for it.** Run the drift check on a second platform, or assert
it directly:

```
grep -rlI $'\r' docs/upstream-package/scitt-rfc9162 | wc -l    # expect 0
```

We now also keep a test that walks every file in the package and fails on a single
`\r`. A rule that only holds on the machine of the person who wrote it is not a rule.

---

## Rule 3 — If two conforming readings of the text disagree, do not score the input

**What it means.** A vector is a claim that *any* conforming implementation
reproduces the recorded result. When the text does not decide an input, two
conforming readings produce two answers, and publishing a vector for it forces
everyone else to fail a case the specification never settled.

**What we violated.** We carried `tree_size=0` with a `leaf_index` asserted as a
fail vector. Our verifier refuses to fold (no fold is defined, root left empty); a
literal reading of RFC 9162 keeps folding and returns a root, because nothing in
the text forbids size zero. Both readings are defensible. The input is a gap in
the text, not a vector.

**How to test a set for it.** Have two independently written verifiers, and treat
any disagreement about *how to interpret* an input — not about a computed value —
as a gap. We caught this with a checker that imports nothing from this project:
`tools/check_scitt_vectors_standalone.py`. If both verifiers live in the same
repository, this rule will not catch anything.

**What to do with the input instead.** Declare it, and say what each reading does:

```json
"underspecified_inputs": [
  { "input": "...", "our_behaviour": "...", "independent_behaviour": "...",
    "why_not_a_vector": "..." }
]
```

Declaring it is strictly better than deleting it silently. A deleted gap teaches
nobody; a declared gap tells the working group what to fix in the text — which is
the actual contribution.

**But read the text before you declare.** This rule has a failure mode, and we
hit it. A disagreement between two verifiers is only a gap if the text really
leaves the question open. On 2026-11-20 we declared `tree_size = 0` with a
`leaf_index` asserted to be such a gap, because our standalone checker folded it
and our builder refused it. The text is not open: RFC 9162 §2.1 fixes
`MTH({}) = SHA-256()`, and §2.1.1 defines `PATH(m, D[n])` only for `0 <= m < n`,
so a leaf cannot sit in an empty tree and a refusal is the only conforming
verdict. One of the two verifiers was simply wrong. That input is now a scored
vector (`v1/fail-empty-tree`) and the false gap is recorded in
`manifest.retired_underspecified_inputs` with the reason it was retired.

So the checklist is: disagreement → **open RFC 9162 and find the sentence** →
gap only if no sentence decides it. Declaring a gap that the text does not
support is worse than deleting the test, because it makes a corpus look
rigorous while leaving a constant unscored — every second implementation then
fails a case it could have passed.

---

## Rule 4 — Counts must be computed, not typed

**What it means.** How many vectors exist, how many of each kind, how many tests
run — these are outputs of a measurement, never literals in prose.

**What we violated, twice.** Class counts in prose went stale after every append,
and the test asserting "six vectors" hid the shrink from Rule 1.

**How to test a set for it.** Ask where the number comes from. If the answer is
"a sentence", it is already wrong somewhere. Our manifest now carries
`class_counts` produced by tallying the vectors themselves, and documentation
that states the suite size is regenerated by a script rather than retyped.

---

## Rule 5 — Score only what your own verifier does not agree with the text about

**What it means.** Every vector should exist because a specific fold branch or a
specific failure is being pinned — not to reach a round number. And the expected
result must be **computed from the input**, not asserted after the fact.

**What we violated.** We wrote a `fail-*` case for "declared `tree_size` one
larger than the path assumes" on the assumption that it must fail. It does not:
the fold reads no additional node, the root comes out identical, so that input is
an instance of the size ambiguity, not an invalid size. Our own verifier reported
"root equal" and the case was relocated to the `ambiguous-*` class. The asymmetry
is now written into the manifest so the next person does not re-derive it.

The same lesson produced this: four ambiguity instances were found by exhaustive
search over sizes 1..19 and every index. **Three of the four candidates a human
would guess first do not exhibit the property.** Guessing cost us three rewrites;
searching cost one pass.

## Rule 6 — Calibrate the checker before you score anything with it

**What it means.** A corpus is only as good as the verifier that decides which
vectors pass. That verifier has to be shown wrong before it is trusted to say
what is right — otherwise "our vectors are consistent" means "our code agrees
with our code".

**What we violated.** When the consistency half was added on 2026-11-21, the
first verifier written from the text was an iterative loop that seeded both
roots from `old_root`. On non-power-of-two old sizes that is wrong, and the
checker scored **20 of 23** known-good consistency cases borrowed from another
project's corpus. A second iterative variant scored 20 of 23 as well. Only the
recursive form written from `SUBPROOF` scored **23 of 23**. Had those 23 cases
not existed, the broken verifier would have generated a corpus that looked
perfectly consistent and failed every honest implementer on `3→7`, `6→9` and
`7→8`.

**How to test a set for it.** Before scoring, run the checker against cases
somebody else produced and whose answers are already known, and write down the
score honestly:

```
# known-good external cases first, our own vectors second
python judge_our_consistency_vectors.py     # 13/13, by two unrelated checkers
python tools/check_scitt_vectors_standalone.py --self-test   # 7 mutations caught
```

Two things must hold: the checker must reach the published verdicts on foreign
data, and its own `--self-test` must catch every mutation. A checker that has
only ever been run on the corpus it generated has no evidence at all.

**What we got from it.** The array order of consistency proofs turned out to be
a scored property rather than a convention: reading the same nodes in reverse
scores 18 of the 23 external cases. That is now stated in the package README,
because an implementer who reverses the array will disagree with us on real
data, and it is better to say so than to find out in review.

---

## What adopting these gets you

Not a bigger corpus — a corpus whose size you can *state* without caveats, because
every number in it is derived and every claim in it is reproducible by someone who
does not trust you. That is the only kind of "bigger" that survives review.

If you want to mark us against these six rules, run:

```
python tools/build_scitt_vector_package.py --check-drift
python tools/check_scitt_vectors_standalone.py
```

and report a mismatch as an issue. **Agreement on rejection counts as much as
agreement on acceptance**, and a gap in the text you can show us is worth more than
a vector you can add.

---

## What this page does not claim

It does not claim our corpus is larger than anyone else's, that our implementation
is conformant to anything, or that these rules are original. Rules 1–5 are a
description of the defects we actually shipped, in the order we found them. If your
set already meets all five, say so publicly and we will cite you rather than
ourselves — that is the outcome this page is trying to make possible.
