# The accept / refuse boundary, as the reference verifier actually draws it

This page exists because a third-party reader — human or model — can lose four cases out of 58
by applying a rule the verifier does not enforce. It states the boundary from the shipped code,
not from intent, and it names the one rule that readers most often invent.

Sources: `uibc_core/verify.py` in `uibc_core.pyz` (the `S1`…`S19` checks, and the undeclared-file
block at lines 455–540), and `run.py` in the conformance archive (`judge()`, lines 134–152).

## 1. What "accept" means in the corpus

`run.py` does not require `PASS`. A case is accepted when **the verifier does not return `FAIL`
and does not report any check as `FAIL`**:

```python
if case["expect"] == "accept":
    ok = verdict != "FAIL" and not reported_failures(got)
```

A case is refused when the verifier returns `FAIL` or `INCONCLUSIVE` **and** names at least one
check the manifest expects. So `INCONCLUSIVE` can be an accept (untouched package) or a refusal
(the broken-package cases), depending on which case it is: what separates them is whether a
check was reported as `FAIL` and whether it named an expected check.

## 2. Failure conditions

The checks, by id and name, are the ones the verifier prints: `S1` package structure, `S2`
identity consistency, `S3` lifecycle state machine, `S4` evidence integrity, `S5` evidence root,
`S6` seal signature, `S7` evidence index metadata, `S8` package checkpoint head, `S9` head pinned
out-of-band, `S10` attestation closure declared, `S11` strict serialization, `S12` timestamp and
identifier strictness, `S13` merkle inclusion proofs, `S14` strict base64, `S15` anchor event
resolution, `S16` external timestamp (RFC 3161), `S17` linear receipt chain, `S18` policy artefact
resolution, `S19` freshness state. `S0` means the verifier itself could not run.

A package fails when a check's own invariants break: a declared file missing or hashing to a
different value, a rewritten index, a Merkle root or proof that does not recompute, a seal that
does not verify, a timestamp that is not a real calendar date in `Z` form, unpadded base64, a
lifecycle event before creation, an identity that disagrees with the manifest, a receipt chain
whose back-links do not close, a policy digest pointing at nothing.

## 3. Declaration rules — and what does **not** need declaring

The manifest declares files and binds their sha256; declared files must exist and match. Beyond
that, three exemptions apply, and they are the ones readers miss:

- **Structural members of the format** need no declaration even when the index does not list
  them: `evidence/merkle.json`, `evidence/chain.json`, `evidence/anchors.json`,
  `evidence/policies.json`, `evidence/external_anchor.json`.
- **The advisory lock** `evidence/.lock` is not evidence and is exempt by exact name (not by
  "any dotfile", so a file renamed to `.payload` does not ride the same exemption).
- **Policy artefacts** under `evidence/policies/` are resolved by `S18`, not by declaration.

Files the format places elsewhere in `evidence/` and that nobody promised are *reported*, not
failed, in `format_version` 1: the verifier lists them as uncommitted in its warnings and still
returns a non-failing verdict. That is deliberate — tightening v1 retroactively failed packages
that were correct when they were sealed.

## 4. `format_version` changes the answer

- absent or `1`: an undeclared file under `evidence/` is a **warning**, not a refusal;
- `2`: "declared by the index, or structural by the format" is the only legal content of
  `evidence/`, so an undeclared file there is a **refusal**;
- an unknown version is not judged with v1 rules — the verifier refuses to claim the package has
  no undeclared evidence, because applying yesterday's rules to tomorrow's package is how a
  verifier ends up passing fields it never read.

## 5. A stray file at the package root is structural

A file at the package root that is neither declared nor a known artefact fails `S1`. Auxiliary
files in sub-directories outside `evidence/` are reported as not covered by the evidence root,
not failed.

## 6. The rule readers invent (do not use it)

> "Every file under `evidence/` must be declared in the manifest with a matching sha256."

The reference verifier does not enforce this, for the three exemptions in §3 and for the
`format_version` distinction in §4. A judge that applies it refuses accept cases that carry
appended structural members and returns a clean-looking, wrong answer. This exact rule was
carried by an internal external-AI harness and produced four false refusals out of 58; the
corpus was correct and the harness was not.

When you write a prompt for a third-party judge, copy the boundary from this page. Do not
restate it from memory, and do not add rules "for safety": every added rule moves the answer
away from what the bytes say.

## 7. What a pass here does not mean

A pass means: on this machine, with this corpus, the verifier refused each broken package naming
an expected check and accepted the ones marked accept. It is not a certification, not an audit,
and not evidence of independent implementation — the corpus, the manifest and the runner are
written by the project. Publish `receipt.json` if you want the run to be citable, and say which
archive hash you ran.

## 8. Before you run: carry the pin, and carry the head

Two measured facts argue that a bare "verify the package and report the verdict" is not the
intended usage. Both come from `benchmarks/corpus/mutation-corpus-500.json` — 500 mutants across
17 families, generated by `tools/mutation_corpus.py`, whose parameters are chosen by index and
never by a random seed, so anyone can regenerate the same 500 cases and get the same table.

**Fact 1 — how you call it decides the false-accept rate.** The same 500 mutants, three ways:

| call | mutants reported as acceptable |
|---|---|
| open — the package alone | **60 / 500 (12.0%)** |
| pinned — plus the anchor the manifest names | **20 / 500 (4.0%)** |
| head-pinned — plus the chain head from out of band | **0 / 60 (0.0%)** |

This is a property of the call, not of the corpus: nothing about the bytes changed between the
three columns.

**Fact 2 — two families tell you which way to call it.**

- **Key substitution (40 mutants):** 40 of 40 are reported acceptable when nothing is pinned, and
  all 40 fail `S6` once a pin is supplied. A verifier used in the open mode therefore reports a
  forged package as fine. That is not a corpus defect and not a verifier defect; it is the usage.
- **Rollback (20 mutants):** 20 of 20 are reported acceptable in *both* the open and the pinned
  mode. Only the chain head catches them. Rollback — presenting an old state as the current one
  — is the one family a pin does not stop, and it is the one you would most want stopped.

**The precondition, stated as a rule:** name the mode and what you passed in, in the same breath
as the verdict. "This package verifies" without a mode is not a claim; "this package verifies in
the open mode" is a claim that a forged seal can also satisfy; "this package refuses in the
pinned mode, with pin *X*" is the one that carries information. If you publish a verdict, publish
the invocation that produced it.

None of this makes the open mode useless — it is the right mode when nothing out of band is
available, and reporting `INCONCLUSIVE` instead of clearing a package is the honest form of that.
It becomes a problem only when the mode is left implicit and the number is quoted without it.
