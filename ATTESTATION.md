# ATTRIBUTION · ATTESTATION

**Project**: uibc-core 0.3.0  ·  **Licence**: Apache-2.0  ·  **Author**: Steven Zhao (Xinghua Zhao)
**Canonical repository**: https://github.com/zhaoxinghua09-cell/uibc-core
**Branch / commit**: `release/v1.1-precheck` / `b4ea732c801a18fca0c2c65d96185e9c6913a2b7`
**Generated (UTC)**: 2026-11-17T09:17:26Z

---

## What this file is

This is the **attribution five-piece set** for this repository as published:

| Piece | Where it is |
|---|---|
| 1. Inner anchor (author + repo + version, inside the artifact) | this paragraph, and `manifest.json → anchors.internal` |
| 2. Outer anchor (an identifier outside this repo) | commit `b4ea732c801a18fca0c2c65d96185e9c6913a2b7` on `release/v1.1-precheck`; DOI: none assigned |
| 3. Hash | `manifest.json → files[*].sha256` for 347 tracked files; manifest digest `sha256:8c032a35145177d18122118f3a5292e49727730a830fe1d16986ac38bf695108` |
| 4. Timestamp | `2026-11-17T09:17:26Z` (UTC), recorded both here and in `manifest.json` |
| 5. Licence + notice | Apache-2.0; disclaimer below |

## How to check it yourself, offline

```bash
git clone https://github.com/zhaoxinghua09-cell/uibc-core
cd uibc-core
python tools/attest.py            # regenerates manifest.json from the tracked files
git diff --stat manifest.json     # digests for unchanged files must match
```

The only fields that may legitimately differ on regeneration are `generated_at` and
`source.branch` / `source.commit` if you are on a different revision. If a **file digest**
differs, the published bytes are not the bytes this attestation describes.

## Disclaimer

This attestation records provenance only. It is not a certification, not a regulatory clearance, not an audit opinion, and not a claim that the software is fit for any particular use. A uibc PASS means: within the observed evidence boundary, no violation was detected. It does not claim the agent was correct, safe, or wise; that the recorded inputs were true or complete; or that any real-world outcome followed.

Not affiliated with, endorsed by, or representing any organisation. Views are the
author's own, in an individual expert capacity.
