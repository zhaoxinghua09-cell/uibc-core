# ATTRIBUTION · ATTESTATION

**Project**: uibc-core 0.3.0  ·  **Licence**: Apache-2.0  ·  **Author**: Steven Zhao (Xinghua Zhao)
**Canonical repository**: https://github.com/zhaoxinghua09-cell/uibc-core
**Branch / commit**: `release/v1.1-precheck` / `67330de8e2d90e3c49bd267954bd7abe8f668b45`
**Generated (UTC)**: 2026-11-17T10:23:57Z

---

## What this file is

This is the **attribution five-piece set** for this repository as published:

| Piece | Where it is |
|---|---|
| 1. Inner anchor (author + repo + version, inside the artifact) | this paragraph, and `manifest.json → anchors.internal` |
| 2. Outer anchor (an identifier outside this repo) | commit `67330de8e2d90e3c49bd267954bd7abe8f668b45` on `release/v1.1-precheck`; Zenodo concept DOI `10.5281/zenodo.22456647` covers the LGD doctrine, **not this package** — a DOI for the 0.3.0 deposit is **not yet assigned**, so it must not be cited as this package's DOI |
| 3. Hash | `manifest.json → files[*].sha256` for 369 tracked files; manifest digest `sha256:e6d86142ca53db03b783f98f62d5a9c49a3e6b136d389d23db100a8890083730` |
| 4. Timestamp | `2026-11-17T10:23:57Z` (UTC), recorded both here and in `manifest.json` |
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
