# Research posture

UIBC Core is an engineering-first research artifact. Claims are kept
verifiable and falsifiable:

- **Spec determinism** is not asserted, it is measured: a second,
  independent implementation (`independent_verifier/`, zero imports from
  the main package) re-derives all verdicts from the written spec; a
  cross-check harness compares every verdict. Current agreement: 70/70.
- **Attack research** is preserved as executable evidence: eight Golden
  Fixture classes (clean / tampered / deleted / duplicated / reordered /
  migrated / malicious / malicious-keyswap). The malicious class encodes a
  real historical blind spot (fully self-consistent forgery undetected in
  v0.1), closed by strict-mode S6 in v0.2.
- **Known open problems**: key-swap by the legitimate holder is only
  detectable via external key pinning; revocation registries are skeletons;
  asymmetric signatures and external timestamping (OTS) are future work.

Reproduce everything from a clean clone:

```
python -m unittest discover tests          # 71 tests
python -m unittest tests.stress_test       # 7 stress scenarios
python independent_verifier/cross_check.py # 70 checks, 0 mismatches
```
