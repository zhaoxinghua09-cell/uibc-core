#!/usr/bin/env python3
"""Carry SEP-2828 execution records into uibc evidence packages.

Why this exists. A receipt format that is meant to be checked by a stranger
invites one question the moment you meet its author: *can your chain hold my
records, and does anything in your stack judge them?* Until this file existed,
the honest answer for this repository was "we re-ran their corpus with their
runner -- that is all". This file closes the carriage gap and, just as
deliberately, refuses to close the semantics gap.

Two verdicts, kept apart on purpose
-----------------------------------
Every case produces two independent verdicts and they are never combined into
one claim:

  uibc_chain  -- do the package's own checks bind THESE bytes? Evidence hash,
                 index digest, evidence root, checkpoint head, seal.
  sep2828     -- do the record's own v0 rules hold, recomputed here from the
                 schema with only hashlib + re + json.

The independence is the point, and it is visible in the fixtures: a record whose
projectionDigest does not recompute is `uibc_chain=PASS` / `sep2828=NONCONFORMING`.
Carriage binds bytes; it does not judge meaning. Anyone reading a single merged
"CONSISTENT" would read it as the second thing, which it is not.

What the SEP-2828 side does NOT do
----------------------------------
`signature_hex` is a FORMAT check: hexadecimal, even length, plausible length
for the declared algorithm. The corpus ships no verification key, so this tool
never says "signature valid" and never says "signer authenticated". A record
edited by anyone can carry a fresh 128-hex string. Verifying the signature
needs the issuer's key; the corpus does not carry one, so neither do we pretend
to.

What uibc's side does NOT do
----------------------------
uibc's checks bind the record bytes as an evidence file (type OUTPUT). They say
nothing about SEP-2828 semantics: whether an unobserved call should have been
refused, whether a decision left an outcome, and so on. Those are the `sep2828`
verdict. There is no cross-walk that converts one into the other.

Non-equivalences (write these down once, so nobody has to rediscover them)
--------------------------------------------------------------------------
* `backLink{attestationDigest,attestationNonce}` is a backward pointer to an
  attestation the record does not ship. uibc has no such concept; the package
  treats the record as a leaf, not as a link in a chain.
* `receiptAsserted` / `issuerAsserted` are issuer-side assertions inside the
  record. uibc's identity.json is the package's own subject, a different object
  at a different layer. Neither substitutes for the other.
* `outcomeDerived.resultCommitment.projectionDigest` binds projection bytes
  that the record also carries. uibc binds the record file; it does not
  re-derive the projection. Our recomputation of projectionDigest lives in the
  sep2828 verdict, not in uibc's.
* uibc's `evidence_root` is over all evidence in a package. A SEP-2828 set is
  "all records for one call family", which is a notion this format does not
  have. For sets we carry one package per set, one evidence entry per record,
  and say so.

Usage
-----
    python tools/sep2828_carriage.py --corpus /path/to/sep2828 \
        --out tools/out/sep2828_carriage.json --html tools/out/sep2828_carriage.html

    # prove the carriage actually binds bytes: seal a case, then flip one byte
    python tools/sep2828_carriage.py --corpus /path/... --tamper

Exit 0 iff every case shows uibc_chain=PASS and sep2828 agrees with the
corpus's own expected.json. Exit 2 means the corpus could not be read at all
(no verdict is not a verdict).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

# Running this file directly puts tools/ on sys.path, not the repo root; the
# package under test lives at the root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VALID_ALGS = {"HS256", "ES256", "RS256"}
VALID_STATUSES = {"executed", "refused", "errored", "unobserved"}
VALID_VERDICTS = {"allow", "block", "escalate"}
ACTING_VERDICTS = {"allow", "escalate"}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
HEX_RE = re.compile(r"^[0-9a-f]+$")
SIG_HEX_LEN = {"HS256": 64, "ES256": 128}

ENVELOPE_FIELDS = ("alg", "iat", "iss", "nonce", "secretVersion", "sub")


# ---------------------------------------------------------------------------
# Our own SEP-2828 rules. Same rule IDs as the corpus's expected.json, because
# the whole point is to be comparable; written from the schema, not copied.
# ---------------------------------------------------------------------------


def _projection_ok(commitment, fails, advisories):
    """resultCommitment: projection bytes self-bind, or a ref + digest."""
    if not isinstance(commitment, dict):
        fails.append("result_commitment_shape")
        return
    if "projection" in commitment:
        proj = commitment.get("projection")
        want = commitment.get("projectionDigest")
        if not (isinstance(proj, str) and isinstance(want, str)):
            fails.append("result_commitment_shape")
            return
        if not DIGEST_RE.match(want):
            fails.append("result_commitment_digest_format")
        # encode explicitly: the record says these bytes are UTF-8 JSON text
        got = "sha256:" + hashlib.sha256(proj.encode("utf-8")).hexdigest()
        if got != want:
            fails.append("result_commitment_self_consistent")
    elif "ref" in commitment:
        if not (isinstance(commitment.get("ref"), str)
                and isinstance(commitment.get("digest"), str)):
            fails.append("result_commitment_shape")
        elif not DIGEST_RE.match(commitment["digest"]):
            fails.append("result_commitment_digest_format")
    else:
        fails.append("result_commitment_shape")


def record_conformance(doc):
    """Return {'conforms', 'requiredFailed', 'advisories'} for one record."""
    fails, advisories = [], []

    if not isinstance(doc, dict) or doc.get("_unparseable"):
        # A fixture that cannot be parsed is a non-object for this rule; the
        # corpus says so explicitly (neg_not_an_object), so do not guess further.
        return {"conforms": False, "requiredFailed": ["top_level_object"],
                "advisories": []}

    if doc.get("version") != 1:
        fails.append("version")

    alg = doc.get("alg")
    if alg not in VALID_ALGS:
        fails.append("alg_supported")

    sig = doc.get("signature")
    sig_is_hex = (isinstance(sig, str) and bool(HEX_RE.match(sig))
                  and len(sig) % 2 == 0)
    if not sig_is_hex:
        # Format only. See the module docstring: no key, no authenticity claim.
        fails.append("signature_hex")
    elif isinstance(alg, str) and alg in SIG_HEX_LEN:
        if len(sig) != SIG_HEX_LEN[alg]:
            advisories.append("signature_length")

    back = doc.get("backLink")
    if not isinstance(back, dict):
        fails.append("back_link_present")
    else:
        if not ("attestationDigest" in back and "attestationNonce" in back):
            fails.append("back_link_present")
        if not (isinstance(back.get("attestationDigest"), str)
                and DIGEST_RE.match(back["attestationDigest"])):
            fails.append("back_link_digest_format")
        if not isinstance(back.get("attestationNonce"), str):
            fails.append("back_link_nonce_type")

    asserted = doc.get("receiptAsserted")
    if not isinstance(asserted, dict):
        fails.append("receipt_asserted_present")
    else:
        if any(f not in asserted for f in ENVELOPE_FIELDS):
            fails.append("receipt_asserted_present")
        if asserted.get("alg") != alg:
            fails.append("receipt_asserted_alg_matches")

    derived = doc.get("outcomeDerived")
    if not isinstance(derived, dict):
        fails.append("outcome_present")
    else:
        if not ("status" in derived and "completedAt" in derived):
            fails.append("outcome_present")
        status = derived.get("status")
        if status not in VALID_STATUSES:
            fails.append("status_valid")
        if not isinstance(derived.get("completedAt"), str):
            fails.append("completed_at_type")
        if derived.get("resultCommitment") is not None:
            _projection_ok(derived["resultCommitment"], fails, advisories)
            if derived.get("status") == "refused":
                advisories.append("refused_has_no_result")
            if derived.get("status") == "unobserved":
                advisories.append("unobserved_has_no_result")
        dd = derived.get("decisionDigest")
        if dd is not None and not (isinstance(dd, str) and DIGEST_RE.match(dd)):
            fails.append("decision_digest_format")

    return {"conforms": not fails,
            "requiredFailed": sorted(fails),
            "advisories": sorted(advisories)}


def classify_record(doc):
    """decision / outcome / unknown, by which derived block is present."""
    if not isinstance(doc, dict):
        return "unknown"
    has_decision = isinstance(doc.get("decisionDerived"), dict)
    has_outcome = isinstance(doc.get("outcomeDerived"), dict)
    if has_decision and not has_outcome:
        return "decision"
    if has_outcome and not has_decision:
        return "outcome"
    return "unknown"


def _envelope_conforms(doc, asserted_key):
    if not isinstance(doc, dict) or doc.get("version") != 1:
        return False
    alg = doc.get("alg")
    if alg not in VALID_ALGS:
        return False
    sig = doc.get("signature")
    if not (isinstance(sig, str) and HEX_RE.match(sig) and len(sig) % 2 == 0):
        return False
    back = doc.get("backLink")
    if not isinstance(back, dict):
        return False
    if not (isinstance(back.get("attestationDigest"), str)
            and DIGEST_RE.match(back["attestationDigest"])):
        return False
    if not isinstance(back.get("attestationNonce"), str):
        return False
    asserted = doc.get(asserted_key)
    if not isinstance(asserted, dict):
        return False
    if any(f not in asserted for f in ENVELOPE_FIELDS):
        return False
    return asserted.get("alg") == alg


def outcome_conforms(doc):
    if not _envelope_conforms(doc, "receiptAsserted"):
        return False
    derived = doc["outcomeDerived"]
    if derived.get("status") not in VALID_STATUSES:
        return False
    if not isinstance(derived.get("completedAt"), str):
        return False
    commitment = derived.get("resultCommitment")
    if isinstance(commitment, dict) and "projection" in commitment:
        proj, want = commitment.get("projection"), commitment.get("projectionDigest")
        if not (isinstance(proj, str) and isinstance(want, str)):
            return False
        if "sha256:" + hashlib.sha256(proj.encode("utf-8")).hexdigest() != want:
            return False
    return True


def decision_conforms(doc):
    if not _envelope_conforms(doc, "issuerAsserted"):
        return False
    derived = doc["decisionDerived"]
    if derived.get("decision") not in VALID_VERDICTS:
        return False
    return isinstance(derived.get("decidedAt"), str)


def _call_key(doc):
    back = doc["backLink"]
    return (back["attestationDigest"], back["attestationNonce"])


def set_conformance(records):
    """Reproduce the set-level verdict from (name, doc) pairs."""
    decisions, outcomes = [], []
    for name, doc in records:
        kind = classify_record(doc)
        if kind == "decision" and decision_conforms(doc):
            decisions.append((name, doc))
        elif kind == "outcome" and outcome_conforms(doc):
            outcomes.append((name, doc))

    findings = []

    calls = {}
    for name, doc in outcomes:
        calls.setdefault(_call_key(doc), []).append(name)
    for names in calls.values():
        if len(names) > 1:
            findings.append({"id": "duplicate_call", "severity": "required",
                             "records": sorted(names)})

    if decisions and outcomes:
        decision_calls = {}
        for name, doc in decisions:
            decision_calls.setdefault(_call_key(doc), []).append(name)
        outcomes_by_call = {}
        for name, doc in outcomes:
            outcomes_by_call.setdefault(_call_key(doc), []).append(name)
        acting = {}
        for call, names in decision_calls.items():
            if any(d["decisionDerived"].get("decision") in ACTING_VERDICTS
                   for _n, d in decisions if _call_key(d) == call):
                acting[call] = names
        unanswered = sorted(n for call, names in acting.items()
                            if call not in outcomes_by_call for n in names)
        unattributed = sorted(n for call, names in outcomes_by_call.items()
                              if call not in decision_calls for n in names)
        if unanswered:
            findings.append({"id": "decision_without_outcome",
                             "severity": "advisory", "records": unanswered})
        if unattributed:
            findings.append({"id": "outcome_without_decision",
                             "severity": "advisory", "records": unattributed})

    gaps = sorted(n for n, d in outcomes
                  if d["outcomeDerived"].get("status") == "executed"
                  and d["outcomeDerived"].get("resultCommitment") is None)
    if gaps:
        findings.append({"id": "executed_without_result_commitment",
                         "severity": "advisory", "records": gaps})

    findings.sort(key=lambda f: (f["id"], f["records"]))

    status_counts, verdict_counts = {}, {}
    for _n, doc in outcomes:
        status = doc["outcomeDerived"]["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    for _n, doc in decisions:
        verdict = doc["decisionDerived"]["decision"]
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    conforming = len(decisions) + len(outcomes)
    conforms = conforming == len(records) and not any(
        f["severity"] == "required" for f in findings)

    return {"conforms": conforms, "total": len(records),
            "conforming": conforming,
            "statusCounts": dict(sorted(status_counts.items())),
            "verdictCounts": dict(sorted(verdict_counts.items())),
            "findings": findings}


# ---------------------------------------------------------------------------
# Carriage: build a real uibc package around the bytes, then verify it.
# ---------------------------------------------------------------------------


def carry(files, label, workdir):
    """Build + seal + verify a package holding `files` byte for byte."""
    from types import SimpleNamespace

    from uibc_core import cli
    from uibc_core.verify import verify as uibc_verify

    pkg = os.path.join(workdir, label)
    # A seal key, so the S6 verdict is a real one. An unsigned package is
    # INCONCLUSIVE at S6 by design (open mode), and "INCONCLUSIVE" for every
    # case would make the carriage look broken when it is only unsealed. The
    # key is generated per run into the temp dir and never leaves it; the
    # public half travels inside the package, which is what lets a stranger
    # verify the seal without holding any secret.
    keyfile = os.path.join(workdir, "carriage-seal.key")
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet):
        if not os.path.exists(keyfile):
            cli.cmd_keygen(SimpleNamespace(out=keyfile, ed25519=True))
        cli.cmd_init(SimpleNamespace(path=pkg))
        cli.cmd_register(SimpleNamespace(
            path=pkg, agent_id="sep2828-carriage:" + label,
            owner="uibc-core carriage", agent_type="data-pipeline",
            version="0.1.0", principal_type=None, logical_agent_id=None,
            run_id=None, key_custody=None))
        for f in files:
            cli.cmd_evidence(SimpleNamespace(
                path=pkg, file=f, type="OUTPUT", media_type="application/json",
                note="SEP-2828 record carried byte-for-byte, unmodified"))
        cli.cmd_submit(SimpleNamespace(path=pkg, policy_hash=None, key=keyfile))

    report = uibc_verify(pkg)
    failed = [c["id"] for c in report.get("checks", []) if c.get("result") == "FAIL"]
    incon = [c["id"] for c in report.get("checks", []) if c.get("result") == "INCONCLUSIVE"]
    return {"package": pkg,
            "uibc_chain": report.get("result"),
            "uibc_failed": failed,
            "uibc_inconclusive": incon,
            "evidence_count": len(files),
            "checkpoint_head": _manifest_head(pkg)}


def _manifest_head(pkg):
    try:
        with open(os.path.join(pkg, "manifest.json"), encoding="utf-8") as f:
            return json.load(f).get("checkpoint_head")
    except OSError:
        return None


def corpus_digest(root, suites):
    """sha256 over "<hex>  <relpath>" lines, the shape the corpus publishes.

    The published digest covers the suite directories only (not run.py,
    MANIFEST.json or VERSION), so the same scope is used here -- otherwise the
    two digests disagree for a reason that has nothing to do with the bytes
    under test.
    """
    digests = {}
    for suite in suites:
        for path in sorted((Path(root) / suite).rglob("*")):
            if (not path.is_file() or "__pycache__" in path.parts
                    or path.suffix == ".pyc"):
                continue
            digests[path.relative_to(root).as_posix()] = (
                hashlib.sha256(path.read_bytes()).hexdigest())
    # Sorted by the relative path STRING, not by walk order: "README.md" sorts
    # before "_check_independent.py" as text ('R' < '_'), and the walk order
    # Path gives disagrees with that on Windows. Mixing the two produces a
    # different digest over identical bytes -- which is exactly the kind of
    # unexplained mismatch this file exists to avoid.
    lines = [digests[k] + "  " + k for k in sorted(digests)]
    blob = ("\n".join(lines) + "\n").encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------
# Corpus drivers
# ---------------------------------------------------------------------------


def run_record_suite(root, workdir):
    suite = Path(root) / "record_conformance_v0"
    expected = json.loads((suite / "expected.json").read_text(encoding="utf-8"))
    cases = []
    for name in sorted(expected):
        path = suite / "records" / (name + ".json")
        raw = path.read_bytes()
        doc = _loads(raw)
        wrapped = carry([str(path)], "rec-" + name, workdir)
        cases.append({
            "suite": "record_conformance_v0",
            "case": name,
            "files": [path.name],
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "uibc_chain": wrapped["uibc_chain"],
            "uibc_failed": wrapped["uibc_failed"],
            "sep2828": record_conformance(doc),
            "expected": expected[name],
            "agreement": record_conformance(doc) == {
                "conforms": expected[name]["conforms"],
                "requiredFailed": expected[name]["requiredFailed"],
                "advisories": expected[name]["advisories"]},
            "checkpoint_head": wrapped["checkpoint_head"],
        })
    return cases


def run_set_suite(root, workdir):
    suite = Path(root) / "record_set_v0"
    expected = json.loads((suite / "expected.json").read_text(encoding="utf-8"))
    cases = []
    for name in sorted(expected):
        files = sorted((suite / "sets" / name).glob("*.json"))
        records = [(p.name, _loads(p.read_bytes())) for p in files]
        wrapped = carry([str(p) for p in files], "set-" + name, workdir)
        got = set_conformance(records)
        cases.append({
            "suite": "record_set_v0",
            "case": name,
            "files": [p.name for p in files],
            "bytes": sum(p.stat().st_size for p in files),
            "uibc_chain": wrapped["uibc_chain"],
            "uibc_failed": wrapped["uibc_failed"],
            "sep2828": got,
            "expected": expected[name],
            "agreement": got == expected[name],
            "checkpoint_head": wrapped["checkpoint_head"],
        })
    return cases


def _loads(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        # A non-object fixture is still a fixture (neg_not_an_object). Anything
        # that cannot be parsed at all is reported as unjudgeable, not guessed.
        return {"_unparseable": True}


def tamper_demo(root, workdir):
    """Seal a conforming case, flip one byte, verify again. Must turn FAIL."""
    from uibc_core.verify import verify as uibc_verify

    suite = Path(root) / "record_conformance_v0"
    name = "conforming_executed_projection"
    src = suite / "records" / (name + ".json")
    wrapped = carry([str(src)], "tamper-" + name, workdir)
    pkg = wrapped["package"]
    entry = _first_entry(pkg)
    target = os.path.join(pkg, "evidence", entry)
    with open(target, "rb") as f:
        raw = f.read()
    mutated = bytearray(raw)
    # flip a byte inside the signature hex: still parses as JSON, different bytes
    marker = b'"signature": "'
    at = mutated.find(marker)
    pos = at + len(marker)
    mutated[pos] = ord("0") if chr(mutated[pos]) != "0" else ord("1")
    with open(target, "wb") as f:
        f.write(bytes(mutated))
    after = uibc_verify(pkg)
    return {
        "case": name,
        "before": wrapped["uibc_chain"],
        "after": after.get("result"),
        "failed_checks": [c["id"] for c in after.get("checks", [])
                          if c.get("result") == "FAIL"],
        "bytes_changed": sum(1 for a, b in zip(raw, mutated) if a != b),
    }


def _first_entry(pkg):
    with open(os.path.join(pkg, "evidence", "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    entries = index["entries"] if isinstance(index, dict) else index
    return entries[0]["path"]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def summarize(cases, corpus, root):
    uibc_pass = sum(1 for c in cases if c["uibc_chain"] == "PASS")
    agree = sum(1 for c in cases if c["agreement"])
    suites = _suite_names(Path(root) / "MANIFEST.json")
    digest = corpus_digest(root, suites)
    published = _published_digest(Path(root) / "MANIFEST.json")
    return {
        "corpus": str(root),
        "corpus_version": _read_text(Path(root) / "VERSION"),
        "corpus_suites": suites,
        "corpus_digest": digest,
        "corpus_digest_as_published": published,
        "corpus_digest_matches": digest == published,
        "cases": len(cases),
        "uibc_chain_pass": uibc_pass,
        "sep2828_agreement": agree,
        "verdict": "CONSISTENT" if (uibc_pass == len(cases) and agree == len(cases))
        else "DIVERGENT",
        "per_suite": _by_suite(cases),
        "cases_detail": cases,
        "tamper": corpus.get("tamper"),
        "scope": ("Carriage binds the record bytes inside a uibc package "
                  "(evidence hash, index digest, evidence root, checkpoint head). "
                  "The sep2828 verdict recomputes the record's own v0 rules. "
                  "Neither verdict implies the other."),
        "not_claimed": [
            "signature authenticity: signature_hex is a format check, no key is "
            "shipped with the corpus, and we do not invent one",
            "semantic equivalence between SEP-2828 records and uibc packages",
            "that a conforming record describes what really happened",
        ],
    }


def _by_suite(cases):
    out = {}
    for c in cases:
        s = out.setdefault(c["suite"], {"cases": 0, "uibc_pass": 0, "agree": 0})
        s["cases"] += 1
        s["uibc_pass"] += 1 if c["uibc_chain"] == "PASS" else 0
        s["agree"] += 1 if c["agreement"] else 0
    return out


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _suite_names(manifest_path):
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))["suites"]
    except (OSError, KeyError, json.JSONDecodeError):
        # Falling back to the two suites this tool knows keeps it runnable
        # against a corpus whose manifest shape changed; the digest comparison
        # then simply reports a mismatch instead of crashing.
        return ["record_conformance_v0", "record_set_v0"]


def _published_digest(manifest_path):
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))["corpusDigest"]
    except (OSError, KeyError, json.JSONDecodeError):
        return None


def render_html(result):
    rows = []
    for c in result["cases_detail"]:
        ok_uibc = c["uibc_chain"] == "PASS"
        ok_agree = c["agreement"]
        conforms = c["sep2828"]["conforms"]
        rows.append(
            "<tr>"
            f"<td class=mono>{c['suite']}</td>"
            f"<td class=mono>{c['case']}</td>"
            f"<td class=num>{len(c['files'])}</td>"
            f"<td class=num>{c['bytes']}</td>"
            f"<td class='v {'ok' if ok_uibc else 'bad'}'>{c['uibc_chain']}</td>"
            f"<td class='v {'ok' if conforms else 'warn'}'>{'CONFORMS' if conforms else 'NONCONFORMING'}</td>"
            f"<td class='v {'ok' if ok_agree else 'bad'}'>{'MATCH' if ok_agree else 'MISMATCH'}</td>"
            f"<td class=mono>{', '.join(c['sep2828'].get('requiredFailed') or []) or '-'}</td>"
            "</tr>")

    tamper = result.get("tamper")
    tamper_block = ""
    if tamper:
        tamper_block = (
            "<section><h2>Carriage really binds the bytes</h2>"
            f"<p>Case <code>{tamper['case']}</code>: sealed at <b>{tamper['before']}</b>. "
            f"One byte of the evidence file was then changed inside the package "
            f"({tamper['bytes_changed']} byte), without touching the manifest. "
            f"Re-verification: <b>{tamper['after']}</b> "
            f"(failed: {', '.join(tamper['failed_checks']) or 'none'}).</p>"
            "<p class=note>If this had stayed PASS, carriage would be decorative.</p>"
            "</section>")

    suites = "".join(
        f"<span class=chip>{name}: {s['cases']} cases, uibc {s['uibc_pass']}/{s['cases']} PASS, "
        f"sep2828 {s['agree']}/{s['cases']} agree</span>"
        for name, s in result["per_suite"].items())

    return f"""<!doctype html>
<meta charset="utf-8">
<title>SEP-2828 carriage into uibc packages</title>
<style>
:root {{ color-scheme: dark }}
body {{ background:#0e1116; color:#d7dee8; font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Rodoto,sans-serif; margin:0; padding:40px 32px 64px }}
h1 {{ font-size:26px; margin:0 0 6px }}
h2 {{ font-size:16px; margin:32px 0 10px; color:#9fb0c7; font-weight:600; letter-spacing:.02em; text-transform:uppercase }}
.sum {{ font-size:34px; font-weight:700; letter-spacing:.04em }}
.sum.ok {{ color:#54d18c }} .sum.bad {{ color:#ff6b6b }}
.sub {{ color:#8b9bad; margin-top:4px }}
.chips {{ margin:18px 0 6px }}
.chip {{ display:inline-block; background:#171d26; border:1px solid #24303d; border-radius:999px; padding:5px 12px; margin:0 8px 8px 0; font-size:13px }}
table {{ border-collapse:collapse; width:100%; margin-top:14px; font-size:13.5px }}
th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #1d2530 }}
th {{ color:#8b9bad; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.03em }}
.mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:12.5px }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; color:#9fb0c7 }}
.v {{ font-weight:600 }}
.ok {{ color:#54d18c }} .bad {{ color:#ff6b6b }} .warn {{ color:#e6b450 }}
section {{ margin-top:26px }}
p {{ max-width:78ch }} .note {{ color:#8b9bad; font-size:13px }}
ul {{ max-width:78ch; color:#b9c6d6 }} li {{ margin:4px 0 }}
code {{ background:#171d26; padding:1px 5px; border-radius:4px }}
footer {{ margin-top:40px; color:#6d7c8f; font-size:12.5px; border-top:1px solid #1d2530; padding-top:14px }}
</style>
<h1>SEP-2828 records, carried into uibc packages</h1>
<p class=sub>Corpus <code>{result['corpus_version']}</code>,
digest <code>{result['corpus_digest']}</code>
({'matches the published MANIFEST' if result['corpus_digest_matches'] else 'DOES NOT match the published MANIFEST'}).
Every row is a real package: init, register, one evidence entry per record, seal, verify.</p>

<div class="sum {'ok' if result['verdict'] == 'CONSISTENT' else 'bad'}">{result['verdict']}</div>
<p class=sub>{result['uibc_chain_pass']}/{result['cases']} cases verify at uibc_chain PASS ·
{result['sep2828_agreement']}/{result['cases']} reproduce the corpus's own expected verdict</p>
<div class=chips>{suites}</div>

<h2>Two verdicts, never merged</h2>
<table>
<tr><th>suite</th><th>case</th><th>files</th><th>bytes</th><th>uibc chain</th><th>sep2828</th><th>vs expected</th><th>failed rules</th></tr>
{''.join(rows)}
</table>
<p class=note>Read the third row of negatives as the honest one: an edited projection digest
still passes <code>uibc_chain</code> (the bytes are exactly the bytes that were sealed) and fails
<code>sep2828</code> (the record's self-binding does not recompute). Carriage binds bytes; it does not judge meaning.</p>

{tamper_block}

<section>
<h2>What this does not claim</h2>
<ul>{''.join('<li>' + x + '</li>' for x in result['not_claimed'])}</ul>
<p class=note>{result['scope']}</p>
</section>

<footer>Generated by <code>tools/sep2828_carriage.py</code>; every number above is read from the run's own JSON,
never typed into the template. Re-running the command reproduces it.</footer>
"""


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", required=True,
                    help="path to the SEP-2828 conformance corpus root")
    ap.add_argument("--out", default="tools/out/sep2828_carriage.json")
    ap.add_argument("--html", default="tools/out/sep2828_carriage.html")
    ap.add_argument("--tamper", action="store_true",
                    help="also prove that sealed bytes are bound: flip one byte, re-verify")
    ap.add_argument("--keep", action="store_true", help="keep the built packages")
    args = ap.parse_args(argv[1:])

    root = Path(args.corpus)
    if not (root / "MANIFEST.json").is_file():
        print(f"cannot read corpus at {root}: no MANIFEST.json", file=sys.stderr)
        return 2

    workdir = tempfile.mkdtemp(prefix="sep2828-carriage-")
    try:
        cases = run_record_suite(root, workdir) + run_set_suite(root, workdir)
        extra = {"tamper": tamper_demo(root, workdir) if args.tamper else None}
        result = summarize(cases, extra, root)

        for path_attr, text in (("out", json.dumps(result, indent=2, ensure_ascii=False)),
                                ("html", render_html(result))):
            target = Path(getattr(args, path_attr))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"wrote {target}")

        print(f"\nuibc_chain   {result['uibc_chain_pass']}/{result['cases']} PASS")
        print(f"sep2828      {result['sep2828_agreement']}/{result['cases']} agree with expected")
        if result["tamper"]:
            print(f"tamper       {result['tamper']['before']} -> {result['tamper']['after']} "
                  f"after {result['tamper']['bytes_changed']} byte changed")
        print(f"verdict      {result['verdict']}")
        return 0 if result["verdict"] == "CONSISTENT" else 1
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            print(f"packages kept in {workdir}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
