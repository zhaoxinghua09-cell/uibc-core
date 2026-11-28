# interop

Two things live here: a machine-readable statement of what this project hands to
others and what it takes from them (`CONSUMERS.json`), and the entry point for
testing **your** packages with **our** verifier (`tools/bring_your_own.py`).

`CONSUMERS.json` is deliberately blunt. Each entry says whether the format is
consumed, produced, or neither, and where the measurement came from. The entries
listed as *not consumed* are real absences: the SCITT COSE vectors that this
verifier currently cannot read are named there with the numbers, rather than left
for a reader to discover.

## Test your own packages

A case is one directory that is itself an evidence package, plus one line saying
what you expect from it:

```json
{"cases": [
  {"id": "mine-ok",     "path": "mine-ok",     "expect": "accept"},
  {"id": "mine-broken", "path": "mine-broken", "expect": "reject", "expected_checks": ["S4"]}
]}
```

Then:

```bash
python tools/bring_your_own.py --cases ./my-cases --expect ./my-expected.json \
    --pyz uibc_core.pyz --out my-receipt.json --run-by "<your name or handle>"
```

Or point it straight at the published archive, without cloning anything else:

```bash
python tools/bring_your_own.py --cases ./my-cases --expect ./my-expected.json \
    --pyz conformance/uibc-conformance-0.5.8.zip:uibc_core.pyz --out my-receipt.json
```

Judging does not trust the exit code. A verifier that exits 0 while refusing
everything would look successful otherwise:

- `accept` is ok when the verdict is not `FAIL` **and** no check reports `FAIL`;
- `reject` is ok when the verdict is `FAIL` or `INCONCLUSIVE` **and** at least
  one of the checks you named actually reports `FAIL`.

Exit codes: `0` every case behaved as you said, `1` some case did not, `3` the
run could not be set up (a case directory missing, the table unreadable, the
verifier absent). A setup problem outranks a verdict, and no receipt is written
when the run cannot be set up.

The receipt records `run_by` verbatim. Leave it unset and it stays null, so a
receipt written by this project's author and one written by a stranger are
distinguishable without anybody having to ask.

## Read the results from another harness

A harness that wants to run this verifier over its own vectors needs one line
per vector, not one pretty JSON document per package:

```bash
python uibc_core.pyz verify ./one-package --report runs.jsonl --vector-id v-17
python uibc_core.pyz verify-dir ./my-vectors --report runs.jsonl
```

Each line is `{"format": "uibc-verify-report/1", "vector": ..., "result": ...,
"checks_failed": [...], "verifier_id": ..., "verifier_version": ..., "when_utc":
..., "exit": 0|1}`. `--report` appends, so a batch run accumulates in one file and
a failing package cannot erase the lines already written. A failing package still
gets a line — that is the case a harness most needs — and so does an input we cannot
read at all: hand it a single statement file instead of a package directory and the
line says `result: ERROR`, `exit: 3`, and the reason. `no line` would be indistinguishable
from `this vector was silently dropped`, which is precisely what a foreign rail reported
as `external-output-absent` when it handed us single statements. `verify-dir` exits non-zero
when any child is not PASS and prints `n/m packages PASS`; an empty directory exits
3 and writes nothing, because "nothing was judged" must not read as "all passed".

The shape is published as JSON Schema, so a consumer does not have to read
prose: `interop/verify-report.schema.json` (draft 2020-12). It pins the three
things a reader can get wrong - `FAIL` must name the failing check, `ERROR` must
carry a reason and exit 3, and `PASS`/`INCONCLUSIVE` must not carry failed
checks. `tools/report_lint.py <file.jsonl` checks any producer's file against
those rules without needing a third-party library, so the schema can be used
rather than merely quoted.

The line carries this project's verdict vocabulary and check ids. A consumer
mapping FAIL / INCONCLUSIVE onto its own scale is making its own claim, not ours.

## Read a SCITT/COSE Transparent Statement

`cose_min.py` verifies the shape this project emits. It is not a reader for
anyone else's wire form: a tagged COSE_Sign1 with CWT claims, an observer
position at a private-use label, and RFC 9942 receipts is outside that subset.
`uibc_core/scitt_cose.py` reads that shape under the `aee-scitt-cose/v0.1`
profile, in the order the profile's Section 6 gives:

```bash
# one statement, with its own trust inputs and verification time in the file
python uibc_core.pyz verify-cose --vector v11816a7dc863a687.json

# a corpus: every member judged, one line per member, plus a score
python uibc_core.pyz verify-cose --manifest MANIFEST.json --statements statements/ \
       --report runs.jsonl --json-out score.json
```

`--at <epoch>` fixes the instant `exp` and `nbf` are judged against. Without it
the vector's own `verificationTime` is used, and the wall clock only where the
file carries none — the choice is visible in the output rather than implicit in
the code.

A refusal carries a code, because "invalid" alone tells a relying party nothing:

| stage | codes |
| --- | --- |
| decode | `unreadable`, `payload-absent` |
| deterministic encoding | `protected-header-not-deterministic` |
| crit (RFC 9052 §3.1) | `critical-parameter-unprotected`, `critical-parameter-unprocessable`, `observer-position-not-critical` |
| algorithm (RFC 9864 §4.2) | `algorithm-deprecated` (-8), `algorithm-mismatch` (-7 and anything else) |
| key and signature | `issuer-key-unknown`, `issuer-key-ambiguous`, `signature-invalid` |
| CWT claims (RFC 9597) | `cwt-claims-absent`, `cwt-claims-duplicated`, `cwt-claims-incomplete`, `subject-digest-mismatch`, `issuer-identity-mismatch` |
| validity window | `statement-expired`, `statement-not-yet-valid` |
| receipt (RFC 9942) | `receipts-absent`, `receipt-vds-absent`, `receipt-vds-unregistered`, `receipt-algorithm-mismatch`, `inclusion-proof-absent`, `inclusion-proof-unapplicable`, `receipt-subject-mismatch`, `receipt-key-unknown` |

The root an inclusion proof is checked against is recomputed by this reader with
its own RFC 9162 Section 2.1.3.2 walk. It does not import `merkle.py` and it does
not read a root out of the file: a verifier that shares arithmetic with the code
that produced the inputs cannot disagree with them, which is the same rule the
profile itself asks of an implementer replaying its corpus.

Results come out as a second report shape, `uibc-scitt-cose-report/1`
(`interop/scitt-cose-report.schema.json`), rather than reusing the package
report: that report names failing checks as `S`-ids, and this profile refuses on
named faults no `S`-id describes. `tools/report_lint.py` validates either shape
and says which rules it applied.

Measured, 2026-11-27, against `probityai/agent-evidence-vectors`
(`corpora/vectors-scitt-cose`, 27 members, `corpusDigest 79d651d3…`): **27 of 27
answers conform** to the answers the corpus declares, judged at the instant its
own witnesses use (`1789041600` = 2026-09-10T12:00Z). Judged at each vector's own
`verificationTime` the count is **26 of 27**, and the member that differs is the
expiry one: its `exp` (1789038000) is after the `verificationTime` that file
carries (1788955200) and before the corpus' witness clock. That is the corpus'
clock question, not our reader's: the verdict is the same bytes answered
differently at a different instant, and both numbers are published rather than
the flattering one alone. 27/27 is our reading of their published corpus; their
rail has not been re-run against this build, so it is not their scoring.

## Produce a statement, not only read one

Reading another project's corpus is one direction. The other is handing back
something that project's reader can judge, and until `uibc emit-cose` existed
this repository could only read.

```
uibc emit-cose --out corpus/ --count 3 --at 1785000000 --exp 1790000000 \
    --nbf 1780000000 --seed-hex <64 hex> --ts-seed-hex <64 hex> \
    --kid-hex <hex> --ts-kid-hex <hex> --detached-index 2
```

It writes `statements/*.json` plus a `MANIFEST.json` that lists them, so the
same `verify-cose --manifest` path reads it back, and then it prints its own
read-back before exiting: **emitted 3, read back valid 3/3, tree root
052d3ad994eb059c…199d** on 2026-11-27 (one of the three carried a detached
payload). The keys are throwaway emit keys and have to be passed in; there is no
default seed, because a signing default is a key that later gets used for real.

Two things this does not establish. It does not establish that another
implementation accepts these statements - the peer's reader on the other side
has not been run against them, and there is no Go toolchain on this machine to
run it with. And the emitted corpus contains only statements that should come
back `valid`; refusals are covered by `tests/test_scitt_cose_emit.py`, which
builds each fault from bytes, not by a corpus of broken statements.

## Read an MCP authorization observation

The peer's `corpora/vectors-mcp-authz` does not ask whether a document parses.
It asks whether a server's whole authorization surface behaves: seven surfaces
of one observation, each judged, with the harness reading a single line.

```bash
# one observation: last stdout line is {"verdict": ..., "codes": [...]}
python uibc_core.pyz verify-mcp-authz --file observations/one.json

# the whole corpus: every member against the answer key in its MANIFEST.json
python uibc_core.pyz verify-mcp-authz --dir corpora/vectors-mcp-authz \
       --report runs.jsonl
```

Exit codes follow the corpus convention, not ours: `0` valid, `1` invalid, `3`
unreadable. `--dir` prints `n/m members conform to the corpus answer key` and
exits 1 when any member disagrees with what the corpus declares, so a reader
cannot pass by printing nothing.

The surfaces and their codes:

| surface | codes |
| --- | --- |
| protected resource metadata | `prm-not-served`, `prm-resource-not-identical`, `prm-authorization-servers-missing`, `prm-bearer-header-missing`, `prm-scope-offline-access` |
| 401 challenge | `challenge-missing`, `challenge-scheme-not-bearer`, `challenge-resource-metadata-missing`, `challenge-scope-offline-access`, `challenge-insufficient-scope-not-403`, `unauthenticated-request-accepted`, `required-scope-not-enforced` |
| authorization server metadata | `as-metadata-not-json`, `as-required-field-missing`, `as-issuer-mismatch`, `as-issuer-not-in-prm`, `as-pkce-s256-missing`, `as-response-type-code-missing`, `as-registration-endpoint-missing`, `config-resource-url-missing`, `config-scopes-not-obtainable` |
| DPoP | `dpop-proof-typ-invalid`, `dpop-proof-alg-not-asymmetric`, `dpop-proof-key-private`, `dpop-htm-mismatch`, `dpop-htu-mismatch`, `dpop-ath-mismatch`, `dpop-proof-replayed`, `dpop-key-binding-mismatch` |
| workload federation | `wif-issuer-untrusted`, `wif-audience-mismatch`, `wif-token-expired`, `wif-subject-unbound`, `wif-scope-widened` |
| client ID metadata document | `cimd-client-id-not-a-clean-https-url`, `cimd-document-client-id-mismatch`, `cimd-symmetric-authentication`, `cimd-redirect-uri-unregistered`, `cimd-support-not-advertised` |
| identity assertion grant | `id-jag-typ-invalid`, `id-jag-audience-mismatch`, `id-jag-client-mismatch`, `id-jag-expired`, `id-jag-jti-missing` |

Two rules this reader was built to keep. A surface that is **absent from
`observed`** is not judged: "we were not shown the metadata" and "the metadata
was missing" are different findings, and folding the first into the second is
how a verifier turns its own blind spot into someone else's failure. And the
auth-params of a challenge are only read when the scheme is Bearer, because
`resource_metadata` in a `Basic realm=` header is a field the server never
wrote.

Measured, 2026-11-28, against `corpora/vectors-mcp-authz` (11 members, 1 accept
/ 10 reject, head `08f16c3`): **11 of 11 conform to the corpus' convention** -
verdict matches, at least one declared code named, no declared code missed. Two
members carry one extra code each (`as-issuer-not-in-prm` on
`resource-metadata-defective`, `challenge-resource-metadata-missing` on
`settings-inconsistent`); they are reported because the conditions hold, and
the convention allows extra codes. The finding vocabulary is this project's, so
this is agreement on verdicts and on named faults, not a code-by-code identity
with the peer's verifier.

## Read a signed revocation list

`uibc_core/revocation_list.py` reads one signed, cumulative revocation list and
folds it into the state a verifier holds. A list is
`{"body": BODY, "sig": base64(Ed25519 over "probity-revocation-v1\0" || JCS(BODY))}`;
lists chain by sequence number and digest; an entry, once published, stays in
every later list byte for byte; roots are pinned out of band and never read from
a list. Canonicalisation and signature checking are the ones this package already
uses for the evidence tier, so the same bytes give the same verdict on both
sides.

Ten refusals, in the order they are checked, each with the detail that names the
thing refused:

| code | detail |
|---|---|
| `revocation_list_shape` | 27 named faults: `signed_list_unreadable`, `signed_list_members`, `body_members`, `type`, `list_id_form`, `seq_not_a_positive_exact_integer`, `previous_form`, `issuedAt_not_a_utc_second`, `issuedAt_not_a_calendar_instant`, `issuerKey_not_base64`, `issuerKey_not_an_ed25519_key`, `issuerKey_not_canonical_base64`, `entries_not_a_list`, `entry_not_an_object`, `entry_members`, `entry_kind_unknown`, `entry_id_form:<kind>`, `revokedAt_not_a_utc_second`, `revokedAt_not_a_calendar_instant`, `entry_reason_not_text`, `successor_on_non_key_entry`, `successor_not_base64`, `successor_not_an_ed25519_key`, `successor_not_canonical_base64`, `entries_not_strictly_ascending`, `entry_not_canonical`, `body_not_canonical` |
| `revocation_list_signer_not_a_root` | — |
| `revocation_list_signature_unverified` | — |
| `revocation_list_other_chain` | — |
| `revocation_list_rollback` | `SEQ<=HELD_SEQ` |
| `revocation_list_gap` | `SEQ>HELD_SEQ+1` |
| `revocation_list_previous_mismatch` | — |
| `revocation_list_time_reversed` | — |
| `revocation_entry_from_future` | — |
| `revocation_list_drops_entry` | `KIND:ID_TRUNCATED_12` |

A root that is revoked hands over to its successor in the same list: the
successor joins the pinned set before the revocation takes effect, and every
revoked key leaves it, so a successor revoked by the same list does not stay.

Measured, 2026-11-28, against `corpora/vectors-revocation-list` (87 members,
9 accept / 78 reject, head `1ab5db7`, `corpusDigest 87dfad7d...be95`): **87 of 87
members match the answer key on all five recorded fields** — the decision, the
refused list's index, the reason as `code:detail`, the digests of the lists up
to the refused one, and the list in force at the verdict. Reading is ours; their
harness was not re-run.

The corpus itself is not vendored: `tests/test_revocation_list_corpus.py` runs
only when `UIBC_REVOCATION_CORPUS` names a checkout, and the checked-in tests
build their own lists from fixtures signed once with fixed seeds.

## Read the delta form of the same list

`uibc_core/revocation_delta.py` reads `predicate/v2/revocation-list`, the form
the peer's records package has emitted since 0.10.0. Both types are live
upstream: a list already signed as v1 keeps its type, so a reader that knew only
one of them would refuse half the lists in circulation.

The framing is the v1 framing — `{"body": BODY, "sig": base64(Ed25519 over
"probity-revocation-v1\0" || JCS(BODY))}`, roots pinned out of band, the same
canonicaliser and the same Ed25519 verifier, imported rather than copied. What
changes is what a list *means*:

- **A list carries only what it newly revokes.** The revocations in force after
  list *n* are the union of lists 1 to *n*. An entry is published once and never
  again; a list naming a subject an earlier list of its chain revoked is refused
  (`revocation_entry_repeated`), so no list can quietly un-revoke.
- **An empty entry list is a freshness list**: a new sequence number and issue
  time, nothing newly revoked.
- **`seq` is an epoch, not a position.** It rises by one; `previous` is the
  digest of the prior body; roots rotate through `successor` on a `key` entry
  and can never be re-added after revocation.
- **Eight subject kinds, not seven.** The delta form adds `idp-key`, an
  identity provider's token-signing key named by its RFC 7638 JWWK thumbprint
  (SHA-256, base64url, no padding, 43 digits) rather than by this format's own
  hex key id. `grant`, `key` and `permit` stay 64 lowercase hex; the rest are
  1–512 printable ASCII characters.
- **The type is named under either host.** `https://probityai.github.io/...`
  and `https://probityai.org/...` name one type; the match is byte-exact on the
  scheme and the host, so `http://`, a port, an upper-case host or a trailing
  dot is not the type.

Ten refusals, checked in this order:

| code | detail |
|---|---|
| `revocation_list_shape` | the 22 shape faults of the v1 reader minus the cumulative-only ones, plus `entry_id_form:idp-key` and `type` |
| `revocation_list_signer_not_a_root` | — |
| `revocation_list_signature_unverified` | `signature_not_canonical_base64` when the signature is not the canonical base64 of 64 bytes |
| `revocation_list_other_chain` | — |
| `revocation_list_rollback` | `SEQ<=HELD_SEQ` |
| `revocation_list_gap` | `SEQ>HELD_SEQ+1` |
| `revocation_list_previous_mismatch` | — |
| `revocation_list_time_reversed` | — |
| `revocation_entry_from_future` | — |
| `revocation_entry_repeated` | `KIND:ID_TRUNCATED_12` |

A signature that is not the canonical base64 of 64 bytes is an *unverified*
signature, not a malformed list: the first thing a reader owes a caller is the
distinction between "your document is invalid" and "your document is spelled
wrong".

```bash
# one chain document: {"roots": [...], "lists": [{"body":..., "sig":...}, ...]}
python uibc_core.pyz verify-revocation-delta --chain chain.json

# the shared vectors, against the answer key the file carries
python uibc_core.pyz verify-revocation-delta --suite revocation.json --report runs.jsonl

# one case of that file
python uibc_core.pyz verify-revocation-delta --suite revocation.json --case RL25
```

Measured, 2026-11-28, against `vectors/shared/revocation.json` of
`probityai/probity` at `c86b20c` (52 cases, 7 accept / 45 reject, file sha256
`e9d4284d…ef00fc`): **52 of 52 members match the answer key** — the seven
acceptances on the whole folded state (head, issue time, list id, the eight
revoked sets, roots, sequence) and the forty-five refusals on the token and the
position. A reader that refused everything would score 45/52 and one that
accepted everything 7/52, so the two halves are reported separately in the
corpus test.

The suite is not vendored: `tests/test_revocation_delta_corpus.py` runs only
when `UIBC_REVOCATION_DELTA_CORPUS` names that file, and the checked-in tests
sign their own chains at test time from fixed seeds.

## Read a receipt over an A2A agent card

`uibc_core/agent_card_receipt.py` reads the suite's four files — the card as
served, the unsigned receipt statement, the check context (issuer key and clock)
and the issuer's signed revocation list — and answers one of two things:

```bash
# one case: last stdout line is {"decision": ..., "reason": ..., "exit": ...}
python uibc_core.pyz verify-agent-card-receipt --case cases/accept-card-without-signatures

# the whole corpus, against the answer key in its MANIFEST.json
python uibc_core.pyz verify-agent-card-receipt \
       --dir corpora/vectors-agent-card-receipt --report runs.jsonl
```

Exit codes: `0` accept, `1` reject, `3` a case that could not be read. The
corpus mode prints `n/m members conform to the corpus answer key`.

The hard part is the subject digest: SHA-256 over the RFC 8785 form of the card
**without its top-level `signatures`** (A2A 8.4.1 rules 2 and 3). Three details
decide whether two verifiers agree, and each of them is a case in the corpus:

- the exclusion is by the **parsed** member name, so `"signatur\u0065s"` is
  excluded like `"signatures"` and a raw-text comparison is wrong;
- it is **not recursive**, so a `signatures` inside an extension stays in the
  digested bytes;
- it excludes that one member only, so `additionalSignatures` is digested as
  served — and the default members a catalog leaves on are kept, never pruned.

The digest also needs numbers the integers-only canonicaliser in this package
refuses: `0.93` and `1e-06` are ordinary in a card, and RFC 8785 defines them by
ECMAScript's `Number::toString`. This module carries that form, and the test
suite checks it against RFC 8785 Appendix B's own table, from the raw bits.

The fifteen rules, in the order the first failure is reported (one accept,
fifteen refusals):

| rule | reason |
| --- | --- |
| all fifteen pass | `receipt_current` |
| statement parses (strict JSON), members exact | `statement_malformed` |
| `_type` | `statement_type_wrong` |
| `predicateType` | `predicate_type_wrong` |
| one subject, `sha256` lowercase hex | `subject_malformed` |
| predicate members, run, result, registry, instants, list URL, thumbprints | `predicate_malformed` |
| `issuedAt < validUntil` | `validity_window_inverted` |
| card parses, is an object, integers inside I-JSON | `card_malformed` |
| card digest equals the named subject digest | `card_digest_mismatch` |
| clock at or after `issuedAt` | `receipt_not_yet_valid` |
| clock before `validUntil` (half-open) | `receipt_expired` |
| a list was supplied | `revocation_list_absent` |
| DSSE envelope, payload members, canonical base64, sorted `revoked` | `revocation_list_malformed` |
| some signature verifies under the receipt signer's key | `revocation_list_signature` |
| clock inside `[issuedAt, nextUpdate)` | `revocation_list_stale` |
| this statement's bytes are not named by the list | `receipt_revoked` |

Three of those are the point of the whole suite, and this reader refuses in all
three: a list that is **absent**, **unreadable** or **signed by a foreign key**
leaves the verifier unable to read the revocation state, and "I could not read
it" is not "it is good". The stale case is the fourth in that family: a list
whose window excludes the check time describes some other moment.

The statement's digest, which the revoked set names, is over its **bytes as
delivered** — the same rule the third family uses — not over a canonical form.

Measured, 2026-11-28, against `corpora/vectors-agent-card-receipt` (49 members:
13 accept / 36 reject, `corpusDigest 4eab50c3...8e18`, head `08f16c3`):
**49 of 49 members match the answer key on decision and reason**, and the corpus
digest recomputed from the files matches the one it declares. Reading is ours;
their harness was not re-run against this build.

Two things this does not establish. The card digest follows the rule the corpus'
statements were signed under; it is not an A2A conformance result. And nothing
here says the graded result in a receipt is true — the reader checks that the
receipt is well formed, current and unrevoked, not that the agent deserves its
`pass`.

## Answer "is this key revoked at this time"

`uibc_core/key_revocation_list.py` reads one signed list of revoked keys, the
trust inputs a verifier holds (trusted list-signing thumbprints, the issue time
of the last accepted list, the revocations already seen), its clock, and one
question — and answers with one of five decisions, exiting 0/1/2/3/4 by them
because that is the contract the suite runs external verifiers under:

| decision | exit | meaning |
|---|---|---|
| `revoked` | 0 | the record, live when the list was served, revokes the key at the time asked |
| `not_revoked` | 1 | the list covers the key with no entry, or the entry takes effect later |
| `no_statement` | 2 | the list does not cover the key: silence is not a statement |
| `rejected` | 3 | the signer is untrusted, the signature fails, or the list is older than the last accepted one |
| `stale` | 4 | the verifier's clock is past the list's `nextUpdate` |

Four checks run in this order and the first failure is the answer:
trust (by the SHA-256 thumbprint **recomputed from the key the envelope
carries**, never the one it claims) → signature → not older than accepted →
not past `nextUpdate`. A list that passes is read together with what the
verifier already saw: a revocation once seen survives a later list that omits
it, and a key the list no longer covers is still revoked by the earlier record.

Two states the reference reader folds silently are refused here instead:
an instant spelled some way other than the single `YYYY-MM-DDTHH:MM:SSZ` form
this suite compares as text (`key_revocation_list_shape`), and two records for
one key that disagree about when the revocation takes effect
(`key_revocation_list_conflict`). A last-wins dictionary would answer either
without saying which record it answered from.

Measured, 2026-11-28, against `corpora/vectors-key-revocation-list` (13 members,
`corpusDigest f790ade4...e77`, head `08f16c3`): **13 of 13 match the answer key
on decision and reason**, and the two facts the manifest declares about each
list (claimed thumbprint honest, signature verifies under the carried key) hold
for every member. The corpus digest recomputed from the files themselves
matches the one it declares, so this is the same corpus version. Reading is
ours; their harness was not re-run.

## Every report shape has a schema, and one linter judges all seven

Seven JSON Lines shapes are produced by this repository, and since 2026-11-28
each has its own draft 2020-12 schema in this directory:

| format | schema | what one line says |
|---|---|---|
| `uibc-verify-report/1` | `verify-report.schema.json` | one package, per-check outcome |
| `uibc-scitt-cose-report/1` | `scitt-cose-report.schema.json` | one Transparent Statement, valid or refused with codes |
| `uibc-mcp-authz-report/1` | `mcp-authz-report.schema.json` | one authorization observation, verdict plus findings |
| `uibc-revocation-list-report/1` | `revocation-list-report.schema.json` | one signed chain, and the list it stopped on |
| `uibc-key-revocation-list-report/1` | `key-revocation-list-report.schema.json` | one question — is this key revoked now — decision, reason, rule |
| `uibc-agent-card-receipt-report/1` | `agent-card-receipt-report.schema.json` | one receipt over a card: decision, one of sixteen reasons, the digest computed |
| `uibc-revocation-delta-report/1` | `revocation-delta-report.schema.json` | one case of a delta suite: decision, one of ten suite tokens, and the `head`/`seq` an acceptance leaves in force |

`tools/report_lint.py` takes any producer's JSONL file and judges each line by
the rules its own `format` names, with no third-party dependency. It also runs
the cross-field rules a schema subset cannot express: a refusal that exits 0, a
`no_statement` filed as `not_revoked`, a reached decision with no rule behind
it, an `ERROR` line carrying a verdict, in the receipt shape an `accept`
wearing one of the fifteen refusing reasons, and in the delta shape an
acceptance with no head to carry forward or a head on a refusal. Each is
refused by name.

```
python tools/report_lint.py runs.jsonl
```

The linter is the fallback, not the only check: where `jsonschema` is installed
the test suite validates the published schemas themselves, so a schema that is
invalid JSON Schema cannot pass by looking fine to us.

## What this does not do

It does not import a foreign corpus wholesale. A corpus in someone else's layout
needs that corpus's own reader: which files form a package, what each vector
means, and which verdict counts as agreement. `tools/bring_your_own.py` takes the
layout you give it, one directory per case, and stops there. The
`scitt-cose-carriage-conformance` corpus used to be a concrete case of that gap;
since 2026-11-27 it has a reader in this repository, and `CONSUMERS.json` records
how far that reading goes instead of claiming it settles the question.

It also does not certify anything. One person, one machine, one run.
