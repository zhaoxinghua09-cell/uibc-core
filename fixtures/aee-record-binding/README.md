# Vendored AEE vector — record signature binding

`statement.json` is a verbatim copy of one AEE conformance vector, carried
here so the 21 CFR 11.70 probe runs offline: no optional package, no network.

- Upstream: `agent-evidence-vectors` 0.36.3, Apache-2.0
  (https://github.com/probityai/agent-evidence-vectors), author Sankalp Gilda.
- Corpus: suite `adversarial-execution-evidence-conformance`, suiteRevision 32.
- Upstream path: `corpora/vectors/statements/v0099f25838779fcc.json`.
- sha256 of this copy: `0099f25838779fcc05c807e7d1886ee584078f0ebc80c43ba6353c4539fddd34`.
- Content is unmodified.

The corpus is signed with deterministic test keys that anyone re-derives from
a published recipe, so no private key material is distributed upstream and
none is used here:

    seed(role) = SHA-256("in-toto-aee-test-key/<role>/v1")

This vector's records verify under the `substrate-observation-test` role, which
is the key a consumer pins out of band.

Why vendor 5 KB instead of depending on the package: `agent-evidence-vectors`
is only an optional extra (`conformance`), so a default install has no corpus.
A probe that needs an optional package either fails the gate on machines that
never installed it, or gets quietly skipped — both are worse than carrying the
test data with its licence notice.

The probe (`tools/probe_record_binding.py`) re-reads this file, and when the
optional package *is* installed it also compares the two copies, so a
conveniently edited fixture cannot pass as the upstream vector.
