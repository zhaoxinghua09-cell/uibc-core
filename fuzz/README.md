# Fuzzing

One harness, one target: the RFC 8785 JCS canonicaliser in `uibc_core/canonical.py`.
It is the single function whose output every digest, seal and receipt in this
repository is computed over, so a defect there is not a bug in a feature, it is a
bug in the evidence chain.

`fuzz_jcs.py` asserts three properties:

1. **Total.** Any input `json.loads` accepts must either canonicalise or be
   refused with `ValueError`/`TypeError`. No other exception, no hang.
2. **Fixpoint.** `canonicalize(json.loads(canonicalize(x))) == canonicalize(x)`.
   A canonical form that canonicalises to something else is not a canonical form.
3. **Order-independent.** The same document with keys inserted in a different
   order canonicalises to identical bytes. Two verifiers must not be able to
   disagree about one record because of how the producer built the dict.

## Running it

```bash
pip install . atheris
python fuzz/fuzz_jcs.py -max_total_time=30     # 30 s, as in CI
python fuzz/fuzz_jcs.py -max_total_time=600    # 10 min, before a release
```

CI runs it for 30 seconds on every push (`fuzz-smoke` in `ci.yml`). libFuzzer
exits 0 when the time budget runs out, so a red job means a counterexample was
found and written to the corpus directory printed in the log.

## What is deliberately not fuzzed here

Signature verification, COSE parsing and the DID resolver are not in this
harness. They need structured inputs rather than arbitrary bytes, and they are
covered by the vectors in `tests/`. Feeding random bytes to an Ed25519 verify
path only measures how fast it rejects garbage.
