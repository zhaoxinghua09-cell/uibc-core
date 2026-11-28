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
import redteam_scale as rscale  # noqa: E402
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


# --- Promoted from `skipped` (2026-11-28 own-corpus probe) -------------------
# The manifest used to carry six attacks under "no check fired; not exportable
# as a vector". Re-running each one against the shipped verifier showed that
# three of them DO fail: the reason recorded in 2026-11-24 was simply wrong.
# These three become vectors; the ones that really do not fire stay in `skipped`,
# and each of those is registered as a defect rather than quietly dropped.
def halve_seal_signature(pkg):
    _seal_with_ed25519(pkg)
    path = os.path.join(pkg, "signatures", "seal.json")
    with open(path, encoding="utf-8") as fh:
        seal = json.load(fh)
    sig = seal["signature"]
    seal["signature"] = sig[: max(1, len(sig) // 2)]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(seal, fh, ensure_ascii=False, indent=2)


def misspell_manifest_schema(pkg):
    _seal_with_ed25519(pkg)
    path = os.path.join(pkg, "manifest.json")
    with open(path, encoding="utf-8") as fh:
        m = json.load(fh)
    m["schema"] = str(m.get("schema")) + "-typo"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=2)


def relabel_media_type(pkg):
    _seal_with_ed25519(pkg)
    path = os.path.join(pkg, "evidence", "index.json")
    with open(path, encoding="utf-8") as fh:
        idx = json.load(fh)
    idx["entries"][0]["media_type"] = "application/x-bogus-media"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, ensure_ascii=False, indent=2)


PROMOTED = (
    ("halve the signature of a publicly verifiable seal", halve_seal_signature, "FAIL",
     "a truncated signature is not a signature; S6 must refuse it"),
    ("misspell the schema string after a public seal", misspell_manifest_schema, "FAIL",
     "an unknown schema identifier cannot be judged, and the seal no longer "
     "covers the manifest; S6 must refuse it"),
    ("relabel media_type on a publicly sealed package", relabel_media_type, "FAIL",
     "S20: a declared media type outside the accepted vocabulary is an unbound "
     "label - the bytes are still bound by S4, the description is not"),
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
GROUPS = GROUPS + SEAL_GROUP + (("scale", rscale.EXTRA_RED_TEAM),)
GROUPS = GROUPS + (("promoted", PROMOTED),)


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


# The cases are built by running `uibc_core.cli`, which stamps `created_at` from the
# wall clock unless `SOURCE_DATE_EPOCH` is set (the reproducible-builds convention it
# already honours, uibc_core/cli.py). Without it, two exports of the same tree differ
# in a handful of case files -- measured 2026-11-20: 6 of 294 files changed while
# nothing about the corpus had. The value below is the moment the published 0.4.1
# corpus was exported, so a rebuild reproduces those stamps byte for byte.
# Measured 2026-11-28: three of the six "no check fired" attacks really do fire
# once the package carries a PUBLIC seal, and are now vectors in the `promoted`
# group. Their originals below stay in `skipped`, because on the unsigned / HMAC
# base the audit used they cannot fire - an absent seal or an unverifiable
# symmetric signature is INCONCLUSIVE, not FAIL. The note says so, so the
# manifest no longer reads as "this attack is undetectable".
SKIP_REASON = {
    "use a status token outside the vocabulary": (
        "still no dedicated check: the seal catches this mutation (S6) only "
        "because the sealed manifest is covered; the status vocabulary itself is "
        "ungated - registered as a defect, not a vector"),
    "reverse the order of the evidence index": (
        "by design: index_metadata_digest sorts by path, so reordering is "
        "harmless and must not be a vector"),
    "delete the seal": (
        "on the unsigned base this is S6 INCONCLUSIVE, not FAIL; it cannot be a "
        "FAIL vector. A sealed package that loses its seal cannot reach PASS"),
    "cut the seal signature in half": (
        "on the HMAC base this is INCONCLUSIVE without the owner key; the "
        "publicly sealed version is case 59"),
    "misspell the manifest schema string": (
        "the HMAC base cannot be checked without the key; the publicly sealed "
        "version is case 60"),
    "relabel an evidence file's media type": (
        "the audit mutated `type` (covered by S7), not `media_type`; the "
        "media_type relabel is case 61"),
}

BUILD_EPOCH = "1795008087"


def export():
    os.environ.setdefault("SOURCE_DATE_EPOCH", BUILD_EPOCH)
    # Evidence ids are uuid4 unless `UIBC_REPRO_SEED` is set (uibc_core/cli.py). Two
    # exports of one tree differed in the ids that end up in `evidence/index.json` and
    # then in every digest above them -- measured 2026-11-20, same 6 files as above.
    os.environ.setdefault("UIBC_REPRO_SEED", "uibc-conformance-cases")
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
    for row in skipped:
        note = SKIP_REASON.get(row["attack"])
        if note:
            row["reason"] = note
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
            # Measured 2026-11-24: an independent reviewer (SiliconFlow, blind, 36/36)
            # refused case 05, hedged on 29 and then on 06. Each time the suite was at
            # fault, not the reviewer: the rules did not say that declared growth is
            # legitimate, that an unrecomputable root is a refusal, or that a shipped
            # public key makes an asymmetric seal verifiable.
            "A package may append evidence after sealing, provided every new file is "
            "declared in the evidence index: that is growth, not tampering, and must "
            "not be refused.",
            "A package whose anchor points at a root this verifier cannot recompute "
            "MUST be refused: 'cannot recompute' is a refusal condition, not an "
            "unknown.",
            "A package sealed with an asymmetric key whose public key ships inside the "
            "package (and whose signature verifies against it) must not be refused: "
            "'no key available' applies only when no public key is shipped.",
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
    # No archive field: a reader who needs the bytes is pointed at the tool that
    # builds them (tools/build_conformance_bundle.py). Measured 2026-11-20: this
    # key held a path and the export rewrote that published file.
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    m = export()
    print(json.dumps({"cases": len(m["cases"]), "skipped": m["skipped"]},
                     ensure_ascii=False, indent=2) if a.json
          else "exported %d cases, skipped %d" % (len(m["cases"]), len(m["skipped"])))

