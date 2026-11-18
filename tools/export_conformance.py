#!/usr/bin/env python3
"""Export the audit's attacks as a conformance suite someone else can run.

The point is not to publish more of our own results. It is to give a second
implementer a set of packages that are *already broken in a known way*, each
with the checks it must report. If their verifier passes one of these, that is
a finding about their verifier, and they can reproduce it without asking us
anything.

Expectations are taken from the audit's measured `failed_checks`, not from a
theory of what should break -- so the suite and the report cannot disagree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = os.path.join(_REPO, "tools")
for p in (_REPO, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import outsider_audit as oa  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

CLEAN = os.path.join(_REPO, "fixtures", "clean.uibc")
OUT = os.path.join(_REPO, "conformance")

GROUPS = (
    ("core", oa.RED_TEAM),
    ("tree-and-chain", oa.V11_RED_TEAM),
    ("extended", oa.EXT_RED_TEAM),
    ("checkpoint", oa.CKPT_RED_TEAM),
)


def slug(name):
    keep = "".join(c if c.isalnum() else "-" for c in name.lower())
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep.strip("-")[:48]


def digest(pkg):
    h = hashlib.sha256()
    for root, dirs, files in os.walk(pkg):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, pkg).replace("\\", "/")
            h.update(rel.encode())
            h.update(b"\0")
            with open(full, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def build_case(name, fn, expectation, why, group, index):
    tmp = tempfile.mkdtemp(prefix="uibc-cc-")
    try:
        pkg = oa._prepare(CLEAN, tmp)
        fn(pkg)
        rep = oa._verdict(pkg)
        failed = sorted(set(rep.get("failed_checks") or []))
        if not failed:
            return None, "no check fired; not exportable as a vector"
        dest = os.path.join(OUT, "cases", "%02d-%s" % (index, slug(name)))
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(pkg, dest)
        return {
            "id": "%02d" % index,
            "group": group,
            "attack": name,
            "why": why,
            "expectation": expectation,
            "expected_result": rep["result"],
            "expected_checks": failed,
            "path": "cases/%02d-%s" % (index, slug(name)),
            "sha256": digest(dest),
        }, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def export():
    # The README lives here too and must survive a rebuild.
    os.makedirs(OUT, exist_ok=True)
    if os.path.isdir(os.path.join(OUT, "cases")):
        shutil.rmtree(os.path.join(OUT, "cases"))
    os.makedirs(os.path.join(OUT, "cases"))
    cases, skipped, index = [], [], 0
    for group, table in GROUPS:
        for name, fn, expectation, why in table:
            index += 1
            rec, why_not = build_case(name, fn, expectation, why, group, index)
            if rec:
                cases.append(rec)
            else:
                index -= 1
                skipped.append({"attack": name, "reason": why_not})
    manifest = {
        "format": "uibc-core/conformance/1",
        "generated_by": "tools/export_conformance.py",
        "base": "fixtures/clean.uibc (unsigned, so a correct copy is INCONCLUSIVE)",
        "how_to_run": "python3 tools/run_conformance.py --verify \"<your verifier command>\"",
        "rules": [
            "A verifier passes a case only if it reports FAIL and names at least "
            "one of expected_checks.",
            "Reporting FAIL for a case in this suite is the requirement; the "
            "exact reason strings are not testable across implementations.",
            "Every case started from a correct package and then broke exactly "
            "one thing.",
        ],
        "cases": cases,
        "skipped": skipped,
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    # One archive rather than 200 loose files: the cases are regenerable, and a
    # reader who wants them can unpack in one step.
    zpath = os.path.join(OUT, "uibc-conformance-0.4.0.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for case in manifest["cases"]:
            root = os.path.join(OUT, case["path"])
            for r, _d, files in os.walk(root):
                for name in files:
                    full = os.path.join(r, name)
                    rel = os.path.relpath(full, root)
                    z.write(full, os.path.join("cases", os.path.basename(case["path"]), rel))
    manifest["archive"] = "uibc-conformance-0.4.0.zip"
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    m = export()
    print(json.dumps({"cases": len(m["cases"]), "skipped": m["skipped"]},
                     ensure_ascii=False, indent=2) if a.json
          else "exported %d cases, skipped %d" % (len(m["cases"]), len(m["skipped"])))
