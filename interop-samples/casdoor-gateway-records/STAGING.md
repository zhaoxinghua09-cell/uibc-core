# Staging note

This branch carries the Casdoor-style gateway × uibc-core interoperability
sample described in README.md, staged publicly so anyone can clone and
re-run the five verifications.

- `interop-flow.png.b64` is the base64 of the flowchart card (binary
  staged as text; decode with `base64 -d interop-flow.png.b64 > interop-flow.png`).
- Demo key files are not staged: the seeds are published inside
  `build_demo.py`, which regenerates `operator.key` / `attacker.key`
  and all three packages byte-for-byte.
- Fictional data throughout. Not an official Casdoor integration.
