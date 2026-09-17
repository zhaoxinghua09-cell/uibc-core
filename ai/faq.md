# FAQ (quick start for agents & humans)

**What is this repo?**
A reference implementation of UIBC: verifiable evidence packages for
autonomous agents. Everything runs offline with Python 3.9+ stdlib only —
no third-party dependencies, no install required.

**Try it end-to-end (every command verified verbatim):**

In a hurry? `python -m uibc_core.cli demo` runs the whole story in one
command: build -> seal -> verify PASS -> tamper -> FAIL caught.

```
# 0. create a package skeleton (a directory, not a file)
python -m uibc_core.cli init mypkg

# 1. register the agent (identity + REGISTER event) — submit refuses
#    unregistered packages
python -m uibc_core.cli register mypkg --agent-id alice-agent-001 --owner alice

# 2. add a lifecycle event (optional but typical)
python -m uibc_core.cli event mypkg --type ACTIVATE

# 3. add evidence (hash recorded; --type and --file are required)
echo "agent action log line 1" > report.txt
python -m uibc_core.cli evidence mypkg --type ACTION --file report.txt

# 4. seal the package (computes evidence_root into manifest)
python -m uibc_core.cli submit mypkg

# 5. verify — open mode (integrity only)
python -m uibc_core.cli verify mypkg

# 6. strict mode: generate a key, re-seal with it, verify with it
python -m uibc_core.cli keygen --out alice.key
python -m uibc_core.cli submit mypkg --key alice.key
python -m uibc_core.cli verify mypkg --key alice.key
```

All commands are also available as `uibc <subcommand>` after
`pip install -e .`, but the module form above works from a plain clone.

**Can I trust a package someone sent me?**
Run `verify`. Use `gate` for a decision with exit codes
(0=ALLOW, 2=DENY, 3=HOLD). Never skip strict mode when you hold the key.
Open mode on a *signed* package reports S6 INCONCLUSIVE, on an *unsigned*
package S6 SKIP — both mean honesty, not failure: you have no key to
check the seal with.

**Can two implementations agree?**
Yes — that is the point. `independent_verifier/cross_check.py` compares
the reference verifier with a from-spec second implementation: 70/70.

**How do I run the full test suite?**

```
python -m unittest discover tests           # 115 tests (incl. 11 MCP / 9 registry / 15 A2A / 9 runtime)
python -m unittest tests.stress_test        # 7 stress scenarios
python independent_verifier/cross_check.py  # 70 checks, 0 mismatches
python fixtures/generate_fixtures.py        # regenerate + re-verify fixtures
```

**Is this production-ready?**
No. Everything is PROPOSAL. HMAC is a deliberate v0.2 stopgap;
Ed25519, revocation registries, and external timestamping are open work.

**Who is behind it?**
See `ai/sources.md`. It is a personal research project, not a corporate
standard body.
