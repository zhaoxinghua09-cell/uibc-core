# External baselines, measured 2026-11-19

Two things were run today against other people's public material. Both are
reproducible from the commands below; nothing here is a claim about quality.

## 1. WEXP Core-02: the comparison stops, and names the component

`WEXP-dev/wexp-check` claims that its driver exits non-zero when a case disagrees,
and that later checks are reported as not evaluated rather than silently passed.
That claim is testable in one edit.

Method: copy `WEXP-CORE-02-VECTORS-001`, flip one boolean in one expectation —
`cases[0].expected.asserted_claim_supported`, `true` → `false` — leave every other
byte untouched, then run the published driver with the repository's
`comparison.json` as `--baseline`:

```
PYTHONPATH=. python3 -B scripts/compare_corpora.py --baseline comparison.json . \
    /tmp/wexp-ref /tmp/out.json \
    /tmp/tamper/001/corpus.json \
    /tmp/wexp-vectors/vectors/WEXP-CORE-02-VECTORS-002/corpus.json
```

Result: exit status 1, and four `FAIL` lines covering three distinct layers:

| Layer | Line |
|---|---|
| integrity | `corpus.json sha256 566520ba…c0d0f differs from manifest expanded_corpus_sha256 d5d2c9d5…323f` |
| per-component | `case C01: check_equals_expected, ref_equals_expected (components ['asserted_claim_supported'])` |
| baseline drift | `case C01: differs from the baseline in check_equals_expected, ref_equals_expected` |

The second line is the useful one: the failure is attributed to the single
component that changed, not to the case as a whole. A driver that stopped at the
first disagreement and reported the rest as passed could not produce this output.

Limits: the tampering was done on a copy, on one machine, by one operator. This
reproduces their tail-control; it is not a review of their semantics, and it says
nothing about whether their expectations are the right ones.

## 2. `agent-evidence-vectors` 0.24.0: 288 of 288, on the reference rail

Package `agent-evidence-vectors==0.24.0` (PyPI; repository README points at
`probityai/agent-evidence-vectors`), 37 corpora selectable with `--list-corpora`,
default corpus `suiteRevision 32`.

```
uvx agent-evidence-vectors==0.24.0
```

```
totals: 288 vectors, 288 pass, 0 fail; report written to conformance-report.json
```

The report says what this is worth: `rail: reference`, `verifier: null`. The
package's own reference verifier ran its own vectors. It is a self-consistency
run, not an external conformance result, and it is not our result. Only
`rail: external` with `verifier.vectorsExecuted == totals.vectors` counts as an
external run by their own definition.

The package also publishes the interface for such a run:

```
uvx agent-evidence-vectors==0.24.0 --verifier "<your command> -validity-only -json"
```

### The published gap

```
uvx agent-evidence-vectors==0.24.0 --corpus vectors-scitt-cose
→ corpus 'scitt-cose-carriage-conformance' has no reader in this package:
  the reference rail implements 'adversarial-execution-evidence-conformance' only,
  so nothing was judged. Judge it with `aee-verify <path>`,
  or name a verifier with --verifier.
```

That corpus has no reference reader. An external verifier is required by
construction, not by preference.

## 3. What was deliberately not done

A `--verifier` adapter was **not** written, and projects neither PR nor issue was
opened on this repository. Reasons, in order:

1. The mapping is not a wiring job. Their unit is an agent-evidence record with a
   carriage contract and reason codes; ours is an RFC 9162 tree-layer verdict.
   Writing the adapter means asserting, in their vocabulary, what our verdict
   means — which is the same mistake this project avoids elsewhere.
2. It would become a maintenance contract. A published adapter that goes stale is
   worse than no adapter: it makes a claim we no longer test.
3. The gap is theirs to close or leave. Claiming it is a project decision, not a
   task decision, and it should not be taken on the strength of one six-second
   run.

## 4. What these two runs buy

| Statement | Supported |
|---|---|
| Their comparison driver stops and attributes a failure to one component | yes, reproduced here |
| Their package runs 288 of its own vectors cleanly | yes |
| Their vectors prove an external implementation conforms | no — `rail: reference` |
| Their SCITT corpus has no reference reader | yes, their own output says so |
| Our verifier is better, or theirs is worse | **nothing here bears on that** |

Neither run adds a line to any external record. The WEXP replay that did were
`reproductions/2026-11-10-lemonnier` and `2026-11-15-bu`, and our submission to
that repository is separate from this document.
