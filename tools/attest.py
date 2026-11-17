#!/usr/bin/env python3
"""Generate ATTESTATION.md + manifest.json (attribution five-piece set).

Five pieces, per the participation pipeline's S9:
  1. inner anchor  : author signature + canonical repo URL + version, inside the artifact
  2. outer anchor  : commit SHA (and DOI if one exists)
  3. hash          : SHA-256 of every tracked file + SHA-256 of the manifest itself
  4. timestamp     : UTC generation timestamp recorded in both files
  5. licence/notice: copyright, Apache-2.0, explicit non-certification disclaimer

Nothing here is a signature by a third party. It records what was produced, when,
by whom, and what the bytes were - so a stranger can re-derive the same digests.
"""

import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/zhaoxinghua09-cell/uibc-core"
AUTHOR = "Steven Zhao (Xinghua Zhao)"
VERSION_FILE = "uibc_core/__init__.py"

DISCLAIMER = (
    "This attestation records provenance only. It is not a certification, not a "
    "regulatory clearance, not an audit opinion, and not a claim that the software "
    "is fit for any particular use. A uibc PASS means: within the observed evidence "
    "boundary, no violation was detected. It does not claim the agent was correct, "
    "safe, or wise; that the recorded inputs were true or complete; or that any "
    "real-world outcome followed."
)


def sh(*args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          check=False).stdout.strip()


def version():
    p = ROOT / VERSION_FILE
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip('"\'')
    return "unknown"


def main():
    files = []
    for rel in sh("git", "ls-files").splitlines():
        if rel in ("ATTESTATION.md", "manifest.json"):
            continue
        p = ROOT / rel
        if not p.is_file():
            continue
        data = p.read_bytes()
        files.append({
            "path": rel,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        })

    commit = sh("git", "rev-parse", "HEAD") or "unknown"
    branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ver = version()

    manifest = {
        "schema": "uibc.attestation/1",
        "project": "uibc-core",
        "version": ver,
        "author": AUTHOR,
        "licence": "Apache-2.0",
        "generated_at": now,
        "source": {"repo": REPO_URL, "branch": branch, "commit": commit},
        "anchors": {
            "internal": {"author": AUTHOR, "repo": REPO_URL, "version": ver},
            "external": {"commit": commit, "doi": None},
        },
        "file_count": len(files),
        "files": files,
        "disclaimer": DISCLAIMER,
        "reproduce": "python tools/attest.py  (then compare manifest digests)",
    }

    body = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    (ROOT / "manifest.json").write_text(body, encoding="utf-8")
    manifest_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()

    md = f"""# ATTRIBUTION · ATTESTATION

**Project**: uibc-core {ver}  ·  **Licence**: Apache-2.0  ·  **Author**: {AUTHOR}
**Canonical repository**: {REPO_URL}
**Branch / commit**: `{branch}` / `{commit}`
**Generated (UTC)**: {now}

---

## What this file is

This is the **attribution five-piece set** for this repository as published:

| Piece | Where it is |
|---|---|
| 1. Inner anchor (author + repo + version, inside the artifact) | this paragraph, and `manifest.json → anchors.internal` |
| 2. Outer anchor (an identifier outside this repo) | commit `{commit}` on `{branch}`; Zenodo concept DOI `10.5281/zenodo.22456647` covers the LGD doctrine, **not this package** — a DOI for the 0.3.0 deposit is **not yet assigned**, so it must not be cited as this package's DOI |
| 3. Hash | `manifest.json → files[*].sha256` for {len(files)} tracked files; manifest digest `sha256:{manifest_digest}` |
| 4. Timestamp | `{now}` (UTC), recorded both here and in `manifest.json` |
| 5. Licence + notice | Apache-2.0; disclaimer below |

## How to check it yourself, offline

```bash
git clone {REPO_URL}
cd uibc-core
python tools/attest.py            # regenerates manifest.json from the tracked files
git diff --stat manifest.json     # digests for unchanged files must match
```

The only fields that may legitimately differ on regeneration are `generated_at` and
`source.branch` / `source.commit` if you are on a different revision. If a **file digest**
differs, the published bytes are not the bytes this attestation describes.

## Disclaimer

{DISCLAIMER}

Not affiliated with, endorsed by, or representing any organisation. Views are the
author's own, in an individual expert capacity.
"""

    (ROOT / "ATTESTATION.md").write_text(md, encoding="utf-8")

    print("files_hashed=%d" % len(files))
    print("manifest_sha256=%s" % manifest_digest)
    print("commit=%s branch=%s version=%s" % (commit, branch, ver))
    return 0


if __name__ == "__main__":
    sys.exit(main())
