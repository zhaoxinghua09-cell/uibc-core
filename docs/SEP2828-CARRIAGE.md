# Carrying SEP-2828 records into uibc packages

`tools/sep2828_carriage.py` puts a SEP-2828 execution record inside a real
uibc submission package, seals it, verifies it, and then judges the record on
its own rules. It exists because of one question that arrives the moment you
meet the author of a receipt format: *can your chain hold my records, and does
anything in your stack judge them?*

Before this file, the honest answer was: we re-ran their corpus with their
runner. That is a replay, not a carriage. This closes the carriage gap and
deliberately leaves the semantics gap open.

## Two verdicts, never merged

| Verdict | Question it answers | Where the rules come from |
|---|---|---|
| `uibc_chain` | do the package's checks bind **these** bytes? | `uibc_core.verify`: evidence hash, index digest, evidence root, checkpoint head, seal |
| `sep2828` | do the record's own v0 rules hold? | recomputed here from the schema, with `hashlib` + `re` + `json` only |

The independence is visible in the fixtures, and that is the point:

* a record whose `projectionDigest` does not recompute is
  **`uibc_chain=PASS` / `sep2828=NONCONFORMING`** — the bytes are exactly the
  bytes that were sealed, and the record's self-binding does not recompute;
* a byte changed **after** sealing is **`FAIL` (S4, S8)** — the seal no longer
  covers what is on disk.

A single merged "CONSISTENT" would read as the first thing when it means the
second. There is no merged verdict anywhere in the output.

## Result

`as of 2026-11-19`, corpus `1.0.1`, `corpusDigest sha256:5b46b5d51a024d6c9c7d6e48889091e561bad43e66730486c6a581ed9315bd08`
(matches the corpus's own `MANIFEST.json`), taken from
`vaaraio/vaara@7f70b48`, run on Windows 11 / Python 3.13:

```
uibc_chain   17/17 PASS
sep2828      17/17 agree with expected
tamper       PASS -> FAIL after 1 byte changed (S4, S8)
verdict      CONSISTENT
```

* `record_conformance_v0`: 10/10 cases — the case set includes three that
  conform, one that conforms with an advisory, and six negatives.
* `record_set_v0`: 7/7 sets — duplicate call, decision without outcome,
  outcome without decision, executed without a result commitment.

Every row is a package built from scratch: `init`, `register`, one evidence
entry per record (`type=OUTPUT`), `submit` with an Ed25519 seal, `verify`. The
seal key is generated into a temp directory per run and never leaves it; the
public half travels inside each package, which is what lets a stranger verify
the seal without holding a secret.

Reproduce (the corpus is a clone of the other project, not vendored here):

```bash
git clone https://github.com/vaaraio/vaara /tmp/vaara
cd /tmp/vaara && git checkout 7f70b48
python tools/sep2828_carriage.py \
    --corpus /tmp/vaara/conformance/sep2828 \
    --out tools/out/sep2828_carriage.json \
    --html tools/out/sep2828_carriage.html --tamper
```

Every number in the HTML board is read from that run's JSON; none is typed into
the template.

## What is *not* mapped, in plain words

| SEP-2828 | uibc | Why there is no cross-walk |
|---|---|---|
| `backLink{attestationDigest,attestationNonce}` | — | a backward pointer to an attestation the record does not ship. uibc treats the record as a leaf, not as a link in a chain |
| `receiptAsserted` / `issuerAsserted` | `identity.json` | an issuer-side assertion inside the record vs the package's own subject. Different objects, different layers; neither substitutes for the other |
| `outcomeDerived.resultCommitment.projectionDigest` | — | binds projection bytes the record also carries. Recomputed in the `sep2828` verdict, never inside uibc's checks |
| a directory of records for one call family | `evidence_root` | uibc's root covers all evidence in a package; "a set for one family" is a notion uibc does not have. For sets we carry one package per set, one entry per record |

## Signature: format, not authenticity

`signature_hex` checks hexadecimal, even length, and a length plausible for the
declared algorithm. The corpus ships **no** verification key, so this tool
never says "signature valid", never says "signer authenticated", and never
treats a well-formed hex string as evidence that anyone signed anything. A
record edited by anyone can carry a fresh 128-hex string. Verifying the
signature needs the issuer's key; the corpus does not carry one, so neither do
we pretend to.

## Tests

`tests/test_sep2828_carriage.py` pins the property that matters: the two
verdicts point in opposite directions on purpose. If someone later folds them
into one boolean, those tests fail.

```bash
python -m unittest tests.test_sep2828_carriage
```
