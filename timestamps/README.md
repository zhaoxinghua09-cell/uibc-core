# timestamps/ — 时间锚留档（Historical archive）

> ⛔ **本目录不得作为"已验证存证"对外引用。**
> 下方 `.ots` 文件经四判据复核（**无 OTS magic、不内嵌工件摘要**），**不构成有效的 OpenTimestamps 时间锚**，仅作**历史留档**保留。
> 本仓**有效**存证锚：Sigstore Rekor 透明日志 `logIndex 2883389783`（见 `dist/*.cosign.bundle`）· Zenodo DOI（见 `CITATION.cff`）。
> 下方原文保留原貌以便复核，**但请勿据此把它当作有效锚**。

---

# timestamps/ — external time anchoring (OpenTimestamps) [原文留档]

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
