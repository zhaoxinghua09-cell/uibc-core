#!/usr/bin/env python3
"""Build the self-contained conformance archive.

Before this existed, `uibc-conformance-*.zip` contained cases only: someone
who downloaded it still had to clone the repository to find a runner. That
made "run the corpus" a repository skill, not a published artefact. This
builder packs the cases, the manifest, the runner and a README into one
archive that runs with `python run.py`.

Output is deterministic (fixed timestamps, sorted entries) so the same
inputs produce the same bytes and the sha256 can be published.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
CONF = os.path.join(REPO, "conformance")

VERSION = sys.argv[1] if len(sys.argv) > 1 else "0.4.1"
OUT = os.path.join(CONF, "uibc-conformance-%s.zip" % VERSION)
FIXED = (1980, 1, 1, 0, 0, 0)


def read_cases():
    """Cases live inside the previous archive in the repo; read them from there."""
    src_zip = os.path.join(CONF, "uibc-conformance-0.4.0.zip")
    out = {}
    with zipfile.ZipFile(src_zip) as z:
        for name in sorted(z.namelist()):
            if name.startswith("cases/"):
                out[name] = z.read(name)
    return out


def read(path):
    with io.open(path, "rb") as f:
        return f.read()


def build_pyz():
    """A single-file verifier, so the archive needs no pip and no network.

    zipapp.create_archive() stamps real times into the entries, which would make
    the archive hash change on every build. Assembled here with the same FIXED
    date as everything else, sorted, no __pycache__: same inputs, same bytes.
    """
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="uibc-pyz-")
    shutil.copytree(os.path.join(REPO, "uibc_core"),
                    os.path.join(tmp, "uibc_core"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    with io.open(os.path.join(tmp, "__main__.py"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write("import sys\nfrom uibc_core.cli import main\n"
                "if __name__ == '__main__':\n    sys.exit(main())\n")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(tmp):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, tmp).replace("\\", "/")
                info = zipfile.ZipInfo(rel, date_time=FIXED)
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                with io.open(full, "rb") as f:
                    z.writestr(info, f.read())
    shutil.rmtree(tmp, ignore_errors=True)
    return buf.getvalue()


def add(z, name, data):
    info = zipfile.ZipInfo(name, date_time=FIXED)
    info.external_attr = 0o644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(info, data)


def main():
    manifest_raw = read(os.path.join(CONF, "manifest.json"))
    manifest = json.loads(manifest_raw.decode("utf-8"))
    cases = read_cases()
    runner = read(os.path.join(HERE, "conformance_bundle_run.py"))
    readme = read(os.path.join(HERE, "conformance_bundle_README.md"))

    expected = {
        "format": "uibc-core/conformance/expected/1",
        "note": ("What each case must produce. 'accept' means the package is "
                 "correct and must not be refused. Otherwise the verifier must "
                 "refuse it AND report at least one of expected_checks. "
                 "The source manifest is inconsistent on this field: the 6 "
                 "accept cases carry 'expect', the 30 refuse cases carry only "
                 "'expectation'. It is normalised here from expected_checks so "
                 "a reader does not have to discover that by KeyError."),
        "cases": [{"id": c["id"], "path": c["path"],
                   "attack": c["attack"],
                   "expect": c.get("expect")
                             or ("accept" if not c.get("expected_checks") else "refuse"),
                   "expected_checks": c.get("expected_checks", [])}
                  for c in manifest["cases"]],
    }

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(cases):
            add(z, name, cases[name])
        add(z, "manifest.json", manifest_raw)
        add(z, "expected.json",
            json.dumps(expected, ensure_ascii=False, indent=2).encode("utf-8"))
        add(z, "run.py", runner)
        add(z, "README.md", readme)
        add(z, "uibc_core.pyz", build_pyz())

    digest = hashlib.sha256(read(OUT)).hexdigest()
    print("wrote %s" % OUT)
    print("cases: %d  size: %d  sha256: %s"
          % (len(cases), os.path.getsize(OUT), digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
