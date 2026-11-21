#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify a SHA-256 manifest bundle.

Contract (states the narrow claim, not a broader one):
  PASS means: every listed file exists, its recomputed SHA-256 equals the listed
  digest, and no unlisted file is present when allow_extra is false.
  PASS says nothing about whether the files are correct, complete, or produced by
  any particular party: it means the current bytes on disk match the digests in the
  manifest, regardless of origin or intended purpose.

Exit codes: 0 PASS, 1 MISMATCH, 2 MISSING, 3 EXTRA, 4 ERROR (the manifest file was
unreadable, or contained no usable entries), 5 the negative control did not fail.
Negative control: when --negative-control true, the script mutates one byte of a
listed file in a temporary copy and requires the check to fail. A control that
cannot fail is the failure mode this tool exists to catch.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path):
    """Accept JSON {"files":[{path,sha256}]} or GNU sha256sum text."""
    raw = open(path, "r", encoding="utf-8", errors="replace").read()
    stripped = raw.lstrip()
    if stripped.startswith("{"):
        doc = json.loads(raw)
        entries = doc.get("files") or doc.get("entries") or []
        out = []
        for e in entries:
            p = e.get("path") or e.get("name")
            d = (e.get("sha256") or e.get("digest") or "").lower().strip()
            if p and d:
                out.append((p, d))
        return out, "json"
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 64:
            out.append((parts[1].lstrip("*"), parts[0].lower()))
    return out, "sha256sum"


def verify(manifest_entries, root, allow_extra, manifest_path=None):
    checked = 0
    skip = os.path.normpath(manifest_path) if manifest_path else None
    mismatch, missing = [], []
    listed = set()
    for rel, want in manifest_entries:
        p = os.path.join(root, rel)
        listed.add(os.path.normpath(p))
        if not os.path.exists(p):
            missing.append(rel)
            continue
        got = sha256_file(p)
        checked += 1
        if got != want:
            mismatch.append({"path": rel, "want": want[:16], "got": got[:16]})
    extra = []
    if not allow_extra:
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                p = os.path.normpath(os.path.join(dirpath, f))
                if p in listed or (skip and p == skip):
                    continue
                extra.append(os.path.relpath(p, root))
    if mismatch:
        return "MISMATCH", checked, mismatch, missing, extra
    if missing:
        return "MISSING", checked, mismatch, missing, extra
    if extra:
        return "EXTRA", checked, mismatch, missing, extra
    return "PASS", checked, mismatch, missing, extra


def negative_control(manifest_entries, root):
    """Mutate one byte in a temp copy; the check MUST then fail."""
    tmp = tempfile.mkdtemp(prefix="negctl_")
    try:
        for rel, _ in manifest_entries:
            src = os.path.join(root, rel)
            if os.path.exists(src):
                os.makedirs(os.path.dirname(os.path.join(tmp, rel)) or tmp, exist_ok=True)
                shutil.copy2(src, os.path.join(tmp, rel))
        target = None
        for rel, _ in manifest_entries:
            if os.path.exists(os.path.join(tmp, rel)):
                target = os.path.join(tmp, rel)
                break
        if target is None:
            return "SKIPPED", "no listed file exists to mutate"
        with open(target, "rb") as fh:
            data = bytearray(fh.read())
        if not data:
            data = bytearray(b"x")
        else:
            data[0] ^= 0x01
        with open(target, "wb") as fh:
            fh.write(bytes(data))
        verdict, _, _, _, _ = verify(manifest_entries, tmp, True)
        if verdict == "MISMATCH":
            return "CONTROL_OK", "mutated byte was caught"
        return "CONTROL_FAILED", "mutated byte was NOT caught (verdict=%s)" % verdict
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--allow-extra", default="false")
    ap.add_argument("--negative-control", default="true")
    a = ap.parse_args()

    if not os.path.isfile(a.manifest):
        print("ERROR manifest not found: %s" % a.manifest)
        return 4
    try:
        entries, fmt = load_manifest(a.manifest)
    except Exception as e:
        print("ERROR manifest unreadable: %s" % e)
        return 4
    if not entries:
        print("ERROR manifest contained no usable entries")
        return 4

    allow_extra = str(a.allow_extra).lower() in ("1", "true", "yes")
    verdict, checked, mismatch, missing, extra = verify(entries, a.root, allow_extra, a.manifest)

    print("manifest       : %s (%s)" % (a.manifest, fmt))
    print("root           : %s" % a.root)
    print("entries        : %d" % len(entries))
    print("files checked  : %d" % checked)
    if mismatch:
        print("MISMATCH (%d): %s" % (len(mismatch), json.dumps(mismatch[:10], ensure_ascii=False)))
    if missing:
        print("MISSING  (%d): %s" % (len(missing), missing[:10]))
    if extra:
        print("EXTRA    (%d): %s" % (len(extra), extra[:10]))

    if str(a.negative_control).lower() in ("1", "true", "yes"):
        rc_verdict, rc_note = negative_control(entries, a.root)
        print("neg-control    : %s - %s" % (rc_verdict, rc_note))
        if rc_verdict == "CONTROL_FAILED":
            print("STATUS: FAIL (negative control did not fail)")
            _emit(verdict, checked)
            return 5

    print("STATUS: %s" % verdict)
    _emit(verdict, checked)
    return {"PASS": 0, "MISMATCH": 1, "MISSING": 2, "EXTRA": 3}.get(verdict, 1)


def _emit(verdict, checked):
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write("verdict=%s\nchecked=%d\n" % (verdict, checked))


if __name__ == "__main__":
    sys.exit(main())
