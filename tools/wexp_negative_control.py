#!/usr/bin/env python3
"""Reproduce WEXP Core-02's tail control on one edited expectation.

They publish a claim that is testable in one edit: the comparison driver exits
non-zero when a case disagrees, and it attributes the disagreement instead of
letting later checks read as passing. This script makes that edit on a copy and
checks what the driver actually does.

It does not judge their semantics, their expectations, or their corpus. It only
records whether the published control fires and whether the output names the
component that was changed. The result is therefore about their driver, not
about any verifier's quality -- including ours.

Two trees must be available: a clone of `WEXP-dev/wexp-check` and clones of
`wexp-ref` and `wexp-vectors` at the pins the repository's REPRODUCE.md names.
They are inputs, not vendored copies; nothing from them is redistributed here.

Usage:
    python3 tools/wexp_negative_control.py \
        --check /tmp/wexp-check --ref /tmp/wexp-ref --vectors /tmp/wexp-vectors \
        --json

Exit status: 0 when the control reproduces (driver exits non-zero and names the
changed component), 1 when it does not, 2 when an input is missing.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

CORPUS = "WEXP-CORE-02-VECTORS-001"
OTHER = "WEXP-CORE-02-VECTORS-002"
CASE = "C01"
FIELD = "asserted_claim_supported"

#: Three markers, one per layer the driver is claimed to separate.
MARKERS = {
    "integrity": "differs from manifest expanded_corpus_sha256",
    "component": "components ['%s']" % FIELD,
    "baseline": "differs from the baseline",
}


def _err(msg):
    sys.stderr.write("error: %s\n" % msg)
    return 2


def load_corpus(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def flip(doc):
    """Invert one boolean in one case expectation; report what was flipped."""
    for case in doc.get("cases", []):
        if case.get("id") != CASE:
            continue
        expected = case.get("expected") or {}
        if FIELD not in expected:
            return None
        old = expected[FIELD]
        expected[FIELD] = not old
        return {"case": CASE, "field": FIELD, "from": old, "to": expected[FIELD]}
    return None


def edit_text(text):
    """Flip the same boolean in the raw text, so one word changes and nothing else.

    Re-serialising the parsed document would rewrite every escape sequence in a
    corpus that carries lone surrogates on purpose, and then the integrity
    failure would no longer be attributable to the one edit this script makes.
    """
    case_at = text.find('"id":"%s"' % CASE)
    if case_at < 0:
        case_at = text.find('"id": "%s"' % CASE)
    if case_at < 0:
        return None, None
    # The case's `expected` block sits just before its id; the `input` block
    # after it may carry an `asserted_claim` but not this field.
    field_at = text.rfind('"%s"' % FIELD, 0, case_at)
    if field_at < 0:
        return None, None
    for token in ("true", "false"):
        at = text.find(token, field_at, case_at)
        if at >= 0:
            new = "false" if token == "true" else "true"
            return text[:at] + new + text[at + len(token):], (token == "true")
    return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", default="/tmp/wexp-check", help="clone of wexp-check")
    ap.add_argument("--ref", default="/tmp/wexp-ref", help="clone of wexp-ref")
    ap.add_argument("--vectors", default="/tmp/wexp-vectors", help="clone of wexp-vectors")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of prose")
    args = ap.parse_args(argv)

    src = os.path.join(args.vectors, "vectors", CORPUS, "corpus.json")
    other = os.path.join(args.vectors, "vectors", OTHER, "corpus.json")
    driver = os.path.join(args.check, "scripts", "compare_corpora.py")
    for label, path in (("wexp-vectors corpus", src), ("wexp-vectors other corpus", other),
                        ("wexp-check driver", driver), ("wexp-ref", args.ref)):
        if not os.path.exists(path):
            print(_err("%s not found at %s" % (label, path)))
            return 2

    work = tempfile.mkdtemp(prefix="wexp-negctl-")
    try:
        tampered = os.path.join(work, CORPUS)
        os.makedirs(tampered, exist_ok=True)
        # Copy the whole corpus directory so the manifest travels with it.
        shutil.copytree(os.path.dirname(src), tampered, dirs_exist_ok=True)

        corpus_path = os.path.join(tampered, "corpus.json")
        doc = load_corpus(corpus_path)
        edit = flip(doc)
        if edit is None:
            print(_err("case %s has no %s to flip" % (CASE, FIELD)))
            return 2
        with open(corpus_path, encoding="utf-8") as fh:
            text = fh.read()
        new_text, _old_value = edit_text(text)
        if new_text is None:
            print(_err("could not locate the boolean in %s" % corpus_path))
            return 2
        with open(corpus_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_text)

        out_json = os.path.join(work, "out.json")
        env = dict(os.environ, PYTHONPATH=args.check)
        proc = subprocess.run(
            [sys.executable, "-B", driver, "--baseline", "comparison.json", ".",
             args.ref, out_json, os.path.join(tampered, "corpus.json"), other],
            cwd=args.check, env=env, capture_output=True, text=True, timeout=900)
        text = (proc.stdout or "") + (proc.stderr or "")

        markers = {k: (v in text) for k, v in MARKERS.items()}
        exit_nonzero = proc.returncode != 0
        reproduced = exit_nonzero and all(markers.values())
        falsified = [] if (exit_nonzero and markers["integrity"]) else [
            "driver exited 0 on an edited corpus" if not exit_nonzero
            else "driver failed without the integrity line"]

        result = {
            "corpus": CORPUS,
            "edited": edit,
            "driver_exit": proc.returncode,
            "layers_reported": markers,
            "reproduced": reproduced,
            "observed": "control fires and names the component" if reproduced
                        else "control did not behave as published",
            "not_established": [
                "their expectations are correct",
                "their semantics match any external standard",
                "any verifier is better than another",
            ],
            "fail_lines": [ln.strip() for ln in text.splitlines() if ln.startswith("FAIL")],
        }
        if falsified:
            result["falsified"] = falsified

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("corpus      : %s" % result["corpus"])
            print("edit        : %s.%s %s -> %s"
                  % (edit["case"], edit["field"], edit["from"], edit["to"]))
            print("driver exit : %s" % result["driver_exit"])
            for k, v in markers.items():
                print("  %-9s: %s" % (k, "reported" if v else "absent"))
            print("result      : %s" % result["observed"])
            for line in result["fail_lines"]:
                print("  " + line)
        return 0 if reproduced else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
