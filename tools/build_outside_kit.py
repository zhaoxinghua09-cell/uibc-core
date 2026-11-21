"""Build the archive an outsider actually receives.

`docs/OUTSIDER-RUN.md` asks someone to clone a repository. Most people who
might check our claims will not do that: clone, virtualenv, install, discover.
The distance between "you could reproduce this" and "here, run this" is the
whole difference between a claim and a deliverable.

So this builds one archive: the auditor, the verifier it judges with, the
fixtures it attacks, and a checksum list. Unzip, run one command, read a
verdict.

    python3 tools/build_outside_kit.py --out dist/

What goes in is a whitelist, not the repository. Every file is listed with its
sha256 in SHA256SUMS and in kit-manifest.json, so a recipient can tell whether
they got what we published -- and so can we.

This tool performs no outbound action. It writes a file.
"""

import argparse
import hashlib
import json
import os
import sys
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT_IN_ZIP = "uibc-audit-kit"

README = """# uibc-audit-kit

One command, no credentials, no network.

    python3 tools/outsider_audit.py

Exit code 0 means nothing failed and nothing required was skipped. Any other
code means it did not pass, which is the answer we want you to be able to
get without trusting us.

## What is in here

| path | why |
|---|---|
| `tools/outsider_audit.py` | the auditor: baseline, four red-team stages, interop |
| `uibc_core/` | the verifier the auditor judges with |
| `fixtures/clean.uibc/` | the package under test |
| `tests/fixtures/anchor/` | a real FreeTSA timestamp, used to exercise S16 |
| `SHA256SUMS` | every file above, so you can tell if this archive was altered |

## What it will and will not tell you

It will tell you whether a package is structurally sound, whether eleven
mutations of it are caught, whether a real third-party token is judged
correctly, and whether the auditor itself is judging with our code.

It will NOT tell you that anyone outside has witnessed our package. That
number is zero, and the tool prints it as zero.

## Requirements

Python 3.10+. Nothing else. `asn1crypto` is optional and only affects the
S16 stage: without it that stage reports the dependency instead of a verdict,
which is a skip, not a pass.
"""


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect():
    """The whitelist. Anything not named here is not shipped."""
    files = []
    core = os.path.join(_REPO, "uibc_core")
    for name in sorted(os.listdir(core)):
        if name.endswith(".py"):
            files.append(("uibc_core/" + name, os.path.join(core, name)))
    files.append(("tools/outsider_audit.py",
                  os.path.join(_REPO, "tools", "outsider_audit.py")))
    # The outsider needs to be able to say what it can do, not only to run our
    # audit. Without this the kit ships the verdict but not the vocabulary the
    # verdict is expressed in, and a second implementation cannot be compared
    # with it from inside the kit.
    files.append(("tools/capabilities_check.py",
                  os.path.join(_REPO, "tools", "capabilities_check.py")))
    for rel_root in (os.path.join("fixtures", "clean.uibc"),
                     os.path.join("tests", "fixtures", "anchor")):
        base = os.path.join(_REPO, rel_root)
        for root, _dirs, names in os.walk(base):
            for name in sorted(names):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, _REPO).replace("\\", "/")
                files.append((rel, full))
    lic = os.path.join(_REPO, "LICENSE")
    if os.path.isfile(lic):
        files.append(("LICENSE", lic))
    return files


def build(out_dir, version=None):
    files = _collect()
    if version is None:
        version = _version()
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, "uibc-audit-kit-%s.zip" % version)

    digests = []
    total = 0
    for rel, full in files:
        digest = _sha256(full)
        total += os.path.getsize(full)
        digests.append((rel, digest))

    sums = "".join("%s  %s\n" % (d, rel) for rel, d in digests)
    global_digest = hashlib.sha256(
        "\n".join("%s %s" % (d, r) for r, d in digests).encode()).hexdigest()

    manifest = {
        "name": "uibc-audit-kit",
        "version": version,
        "root": ROOT_IN_ZIP,
        "entry": "python3 tools/outsider_audit.py",
        "python": ">=3.10",
        "file_count": len(files) + 3,
        "payload_bytes": total,
        "set_sha256": global_digest,
        "files": [{"path": r, "sha256": d} for r, d in digests],
        "not_included_on_purpose": [
            "tests/ (the full suite) -- the auditor's stages are self-checking",
            "docs/ -- claims belong in the repo, not in the thing you run",
            "any network code -- the auditor does not reach out",
        ],
        "claims_this_does_not_support": [
            "that a third party has timestamped this package (count is 0)",
            "that the interop stage ran (it is SKIPPED without --kit)",
        ],
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, full in files:
            zf.write(full, ROOT_IN_ZIP + "/" + rel)
        zf.writestr(ROOT_IN_ZIP + "/README.md", README)
        zf.writestr(ROOT_IN_ZIP + "/SHA256SUMS", sums)
        zf.writestr(ROOT_IN_ZIP + "/kit-manifest.json",
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    size = os.path.getsize(zip_path)
    return {
        "zip": zip_path,
        "version": version,
        "file_count": manifest["file_count"],
        "payload_bytes": total,
        "zip_bytes": size,
        "set_sha256": global_digest,
    }


def _version():
    init = os.path.join(_REPO, "uibc_core", "__init__.py")
    try:
        with open(init, encoding="utf-8") as f:
            for line in f:
                if line.startswith("__version__"):
                    return line.split("=")[1].strip().strip("'\"")
    except OSError:
        pass
    return "0.0.0"


def verify_kit(zip_path):
    """Check an archive against its own SHA256SUMS. Returns (ok, problems)."""
    problems = []
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        sums_name = ROOT_IN_ZIP + "/SHA256SUMS"
        if sums_name not in names:
            return False, ["no SHA256SUMS in archive"]
        sums = {}
        for line in zf.read(sums_name).decode().splitlines():
            if not line.strip():
                continue
            digest, rel = line.split("  ", 1)
            sums[rel] = digest
        for rel, digest in sums.items():
            full = ROOT_IN_ZIP + "/" + rel
            if full not in names:
                problems.append("%s: listed but missing" % rel)
                continue
            data = zf.read(full)
            if hashlib.sha256(data).hexdigest() != digest:
                problems.append("%s: digest differs" % rel)
        for name in names:
            rel = name[len(ROOT_IN_ZIP) + 1:]
            if rel in ("SHA256SUMS", "kit-manifest.json", "README.md"):
                continue
            if rel not in sums:
                problems.append("%s: shipped but not listed" % rel)
    return (not problems), problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(_REPO, "dist"))
    ap.add_argument("--version", default=None)
    ap.add_argument("--verify", default=None,
                    help="check an existing archive instead of building one")
    args = ap.parse_args()
    if args.verify:
        ok, problems = verify_kit(args.verify)
        for p in problems:
            print("  - %s" % p)
        print("VERDICT: %s" % ("OK" if ok else "FAILED"))
        return 0 if ok else 1
    info = build(args.out, args.version)
    print("built    : %s" % info["zip"])
    print("version  : %s" % info["version"])
    print("files    : %d" % info["file_count"])
    print("payload  : %d bytes" % info["payload_bytes"])
    print("zip      : %d bytes" % info["zip_bytes"])
    print("set sha  : %s" % info["set_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
