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
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
CONF = os.path.join(REPO, "conformance")
FIXED = (1980, 1, 1, 0, 0, 0)

USAGE = """usage: build_conformance_bundle.py [VERSION] [--replace]

VERSION must be digits and dots, like 0.4.2. With no argument it builds 0.4.1.

A pinned archive is never overwritten with different bytes: if a pin exists for
VERSION and the new build differs from what is on disk, the build is refused.
`--replace` only overwrites an archive that has no pin; a pin always wins.
"""


def parse_args(argv):
    """Validate before anything is written.

    Measured 2026-11-20: `--help` was read as a version and produced
    `uibc-conformance---help.zip` (229,084 bytes, 294 files) inside the repository,
    because the version was taken from argv with no check at all.
    """
    if any(a in ("-h", "--help") for a in argv):
        return None, False
    positional = [a for a in argv if not a.startswith("--")]
    unknown = [a for a in argv if a.startswith("--") and a != "--replace"]
    if unknown:
        raise SystemExit("unknown option %s\n\n%s" % (unknown[0], USAGE))
    version = positional[0] if positional else "0.4.1"
    if len(positional) > 1:
        raise SystemExit("expected at most one version\n\n%s" % USAGE)
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(
            "'%s' is not a version. It must look like 0.4.2, and nothing is built "
            "from a value this does not validate.\n\n%s" % (version, USAGE))
    return version, "--replace" in argv


def pin_path(version):
    return os.path.join(REPO, "anchors", "pins", "uibc-conformance-%s.sha256" % version)


def read_cases():
    """The cases are files under `conformance/cases`, written by the exporter.

    They used to live only inside `uibc-conformance-0.4.0.zip`, which made the
    exporter the writer of a published asset (measured 2026-11-20). With the files
    committed, the archive is a build product of a directory, and nothing has to
    overwrite a release to refresh them. The zip is still read as a fallback so an
    old tree can build.
    """
    cases_dir = os.path.join(CONF, "cases")
    if os.path.isdir(cases_dir):
        out = {}
        for root, dirs, files in os.walk(cases_dir):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, CONF).replace("\\", "/")
                with io.open(full, "rb") as handle:
                    out[rel] = handle.read()
        return out
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
    version, replace = parse_args(sys.argv[1:])
    if version is None:
        print(USAGE)
        return 0
    out = os.path.join(CONF, "uibc-conformance-%s.zip" % version)
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

    # Build beside the target and decide before replacing anything: a pinned archive
    # whose bytes would change is refused, because every published hash, receipt and
    # invitation cites it.
    tmp_out = out + ".tmp"
    with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(cases):
            add(z, name, cases[name])
        add(z, "manifest.json", manifest_raw)
        add(z, "expected.json",
            json.dumps(expected, ensure_ascii=False, indent=2).encode("utf-8"))
        add(z, "run.py", runner)
        add(z, "README.md", readme)
        add(z, "uibc_core.pyz", build_pyz())

    digest = hashlib.sha256(read(tmp_out)).hexdigest()
    if os.path.isfile(out):
        old = hashlib.sha256(read(out)).hexdigest()
        pinned = os.path.isfile(pin_path(version))
        # A pin wins over --replace. Measured 2026-11-20: this condition used to read
        # `and not replace`, so passing the flag overwrote the pinned 0.4.1 archive --
        # 711fa82c... (228,000 bytes) became 37afab99... (231,280 bytes) in one command,
        # while the docstring promised `--replace` only touches an archive with no pin.
        # Every receipt, token and invitation quotes that old hash.
        if old != digest and pinned:
            os.unlink(tmp_out)
            print("refused: %s is pinned and this build has different bytes" % out)
            print("  on disk %s" % old)
            print("  this run %s" % digest)
            print("A pinned version names one set of bytes. Build a new version instead,")
            print("or delete the pin deliberately if the old hash was never published.")
            return 3
        if old == digest:
            os.unlink(tmp_out)
            print("identical: rebuilding %s produced the same bytes (%s)" % (version, digest))
            return 0
        if not pinned and not replace:
            os.unlink(tmp_out)
            print("refused: %s exists and has no pin; pass --replace to overwrite it" % out)
            return 3
    os.replace(tmp_out, out)
    print("wrote %s" % out)
    print("cases: %d  size: %d  sha256: %s"
          % (len(cases), os.path.getsize(out), digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
