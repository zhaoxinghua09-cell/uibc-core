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
import subprocess
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

# --- Ed25519 sealing -------------------------------------------------------
# The suite's own seals are HMAC, which no one without the owner's key can
# check. An asymmetric seal is the one a stranger can verify -- so one case
# seals with Ed25519 using a fixed seed (reproducible), and one flips a bit in
# that signature.
_ED_SEED = "5f" * 32


def _seal_with_ed25519(pkg, tmp=None):
    seed_path = tmp or os.path.join(tempfile.mkdtemp(prefix="uibc-seed-"), "ed.seed")
    with open(seed_path, "w", encoding="ascii") as fh:
        fh.write("ed25519:" + _ED_SEED)
    subprocess.run([sys.executable, "-m", "uibc_core.cli", "submit", pkg,
                    "--key", seed_path], check=True, cwd=_REPO, capture_output=True)


def seal_ed25519(pkg):
    _seal_with_ed25519(pkg)


def flip_ed25519_signature(pkg):
    _seal_with_ed25519(pkg)
    path = os.path.join(pkg, "signatures", "seal.json")
    with open(path, encoding="utf-8") as fh:
        seal = json.load(fh)
    sig = seal["signature"]
    seal["signature"] = ("A" if sig[0] != "A" else "B") + sig[1:]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(seal, fh, ensure_ascii=False, indent=2)


SEAL_GROUP = (
    ("seal", [("flip one bit in an Ed25519 signature", flip_ed25519_signature,
               "FAIL", "S6 verifies against the recorded public key")]),
)

POSITIVE = (
    ("the shipped package, untouched", None,
     "no mutation at all: refusing this means the verifier rejects a correct package"),
    ("a package with its tree and chain appended", oa.build_v11,
     "tree and chain added correctly; S13 and S17 must pass"),
    ("a package with extended evidence appended", oa.build_ext,
     "base64, anchors and policies added correctly; S14, S15 and S18 must pass"),
    ("a package with a checkpoint appended", oa.build_ckpt,
     "checkpoint head added correctly; S8 must pass"),
    ("a package with one more declared evidence file", None,
     "the extra file is added AND declared in the index, so S1 must not fail"),
    ("a package sealed with Ed25519", seal_ed25519,
     "an asymmetric seal a stranger can verify with no secret at all"),
)


GROUPS = (
    ("core", oa.RED_TEAM),
    ("tree-and-chain", oa.V11_RED_TEAM),
    ("extended", oa.EXT_RED_TEAM),
    ("checkpoint", oa.CKPT_RED_TEAM),
)
GROUPS = GROUPS + SEAL_GROUP


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


def build_positive(name, fn, why, index):
    """A package that must not be refused, with the verdict it really produced."""
    tmp = tempfile.mkdtemp(prefix="uibc-cc-pos-")
    try:
        pkg = oa._prepare(CLEAN, tmp)
        if fn:
            fn(pkg)
        if name.endswith("declared evidence file"):
            # Added through the shipped CLI, not by hand: the case is "grow the
            # package the way an owner would", and hand-writing the index got
            # the member name wrong once already.
            body = os.path.join(tmp, "extra-declared.txt")
            with open(body, "w", encoding="utf-8") as fh:
                fh.write("declared, therefore legitimate\n")
            subprocess.run([sys.executable, "-m", "uibc_core.cli", "evidence", pkg,
                            "--type", "ACTION", "--file", body],
                           check=True, cwd=_REPO, capture_output=True)
            subprocess.run([sys.executable, "-m", "uibc_core.cli", "submit", pkg],
                           check=True, cwd=_REPO, capture_output=True)
        rep = oa._verdict(pkg)
        if "FAIL" in rep["result"] or rep["failed_checks"]:
            return None, "a package meant to be accepted was refused: %s" % rep
        dest = os.path.join(OUT, "cases", "%02d-%s" % (index, slug(name)))
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(pkg, dest)
        return {"id": "%02d" % index, "group": "positive", "attack": name,
                "why": why, "expectation": "must be accepted", "expect": "accept",
                "expected_result": rep["result"], "expected_checks": [],
                "path": "cases/%02d-%s" % (index, slug(name)),
                "sha256": digest(dest)}, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
    for name, fn, why in POSITIVE:
        index += 1
        rec, why_not = build_positive(name, fn, why, index)
        if rec:
            cases.append(rec)
        else:
            index -= 1
            skipped.append({"attack": name, "reason": why_not})
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
            "A case with \"expect\": \"accept\" must not be refused; a verifier "
            "that refuses everything fails those.",
            "Every mutated case started from a correct package and then broke "
            "exactly one thing.",
        ],
        "cases": cases,
        "skipped": skipped,
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    # No archive is written here. Measured 2026-11-20: this block wrote
    # `uibc-conformance-0.4.0.zip` unconditionally -- it removed the file first -- and
    # 0.4.0 is a *published* release asset with a pin (`9a1ca72f...`, 114,576 bytes).
    # Running the exporter to rebuild the corpus therefore rewrote published bytes,
    # silently, and the late pin then described a page that no longer existed. The
    # cases are repository files; `build_conformance_bundle.py` now reads them from
    # `conformance/cases/` and nothing has to be packed twice.
    manifest["archive"] = "built by tools/build_conformance_bundle.py, not here"
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
