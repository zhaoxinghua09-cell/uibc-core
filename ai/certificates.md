# Certificates

A certificate is a signed attestation: *"package with evidence_root X
passed verification under checks C1–C7 at time T, issued by key_id K."*

- Issue: `python -m uibc_core.cli cert-issue <pkg> --key <keyfile> -o cert.json`
- Verify: `python -m uibc_core.cli cert-verify <pkg> --cert cert.json --key <keyfile>`

Checks C1–C7: signature validity, issuer binding, expiry (deterministic
time-travel testable), package binding via evidence_root, algorithm
pinning.

Honest scope (v0.1):

- Symmetric (HMAC) only — certificates prove issuance to **key holders**;
  third-party-verifiable certificates require Ed25519 (v0.3).
- Certificate **revocation list** is a v0.2 target; registry skeleton at
  `registry/` (JSONL, append-only).
- "XLGD Certified" branding / trust-mark program: explicitly out of scope.
