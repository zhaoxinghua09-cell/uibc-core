# timestamps/ — external time anchoring (OpenTimestamps)

- `uibc-core-0.2.1.zip.sha256` — SHA256 of the v0.2.1 release artifact
  (59cc1c917ff766af8f6528ceadfea522b8627a2c591e57334aa4afd2a07959f4)
- `uibc-core-0.2.1.zip.ots` — OpenTimestamps proof. Two calendars received
  the digest (a.pool.opentimestamps.org, ots.btc.catallaxy.com); the proof
  upgrades to a Bitcoin-block attestation within ~24h, making the artifact's
  existence provable at/before that block time — without trusting us.

Verify (anyone, free):
    ots verify uibc-core-0.2.1.zip.ots -f uibc-core-0.2.1.zip
    # or upload both files at https://opentimestamps.org/

The artifact itself is tagged `v0.2.1-roadmap+` on GitHub releases / the
dist/ folder of this repo's history.
