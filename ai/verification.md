# Verification

A verifier answers one question: *does this sealed package still prove
what it claims?*

Steps (reference implementation `uibc_core/verify.py`):

| Step | Check | Fail means |
|---|---|---|
| S1 | Structure: manifest, required fields | malformed package |
| S2 | Identity: agent registered, fields consistent | unregistered actor |
| S3 | Lifecycle: events ordered, no resurrection | broken lifecycle |
| S4 | Evidence: every file hash matches manifest | tampered/missing evidence |
| S5 | Evidence Root: recomputed root matches sealed root | package mutated |
| S6 | Signature: seal signed by claimed key (strict mode) | forgery / key swap |

Modes: **open** (no key — structural + hash checks) and **strict**
(`--key` — adds S6; unsigned or wrong-key packages FAIL).

The gate layer turns verdicts into decisions
(`uibc_core/gate.py`, CLI `gate`): exit 0 = ALLOW, exit 2 = DENY
(tampering, invalid revocation), exit 3 = HOLD (needs human/key).
Revocation blocks *after* its own signature is checked; disputes only
annotate, never silently block.

An independent second implementation lives in `independent_verifier/`
(no shared code); `cross_check.py` compares both on all fixtures —
current agreement 70/70.
