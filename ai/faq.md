# FAQ (quick start for agents & humans)

**What is this repo?**
A reference implementation of UIBC: verifiable evidence packages for
autonomous agents. Everything runs offline with Python 3.13 stdlib only.

**Try it in 3 steps:**

```
python -m uibc_core.cli init mypkg.uibc --agent alice
python -m uibc_core.cli evidence mypkg.uibc add report.txt
python -m uibc_core.cli submit mypkg.uibc
python -m uibc_core.cli verify mypkg.uibc          # open mode
python -m uibc_core.cli verify mypkg.uibc --key k  # strict mode
```

**Can I trust a package someone sent me?**
Run `verify`. Use `gate` for a decision with exit codes
(0=ALLOW, 2=DENY, 3=HOLD). Never skip strict mode when you hold the key.

**Can two implementations agree?**
Yes — that is the point. `independent_verifier/cross_check.py` compares
the reference verifier with a from-spec second implementation: 70/70.

**Is this production-ready?**
No. Everything is PROPOSAL. HMAC is a deliberate v0.2 stopgap;
Ed25519, revocation registries, and external timestamping are open work.

**Who is behind it?**
See `ai/sources.md`. It is a personal research project, not a corporate
standard body.
