#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clause-level conformance probes with declared gaps.

What this adds, measured against the tools that already do part of this job:

  tools/aer1_crosswalk.py counts a hand-authored mapping. It says so in its own
  docstring: "the mapping is authored - the script never guesses". Nothing runs,
  so a row that claims COVERED cannot be contradicted by the machine.

  Chef InSpec runs controls and has an impact/ref/tag vocabulary, but only two
  states survive: a control has a test, or it is N/A via only_applicable_if.
  A control without a test fails `inspec check`. There is no state for
  "applicable, we cover part of it, and we say which part".

  OSCAL / compliance-trestle carries the structure (catalog, mapping, assessment
  plan/results, detached signatures) and ships no executor - it hands results to
  Auditree or to a human reviewer.

  Medical-device traceability vendors (Ketryx, Matrix Req, Greenlight Guru) link
  GSPR rows to controlled documents and a person reviews the generated checklist.

This tool's one difference: a DECLARED GAP is a machine state that stays green
and is counted. A clause we claim to cover, and cannot demonstrate by running
something, turns the run red. That is what makes "we only claim what we can run"
a mechanism instead of a sentence.

States (one per clause):

  COVERED      strength=carried, probe declared, probe passed
  PARTIAL      strength=partial, reason given        (probe optional)
  GAP          strength=gap,     reason given        (no probe required)
  OVERCLAIM    strength=carried, but no probe, or probe failed        -> exit 1
  UNDECLARED   strength=gap/partial with an empty reason              -> exit 1
  UNRUN        --no-probe was passed; carried clauses are not executed

Exit code: 1 when any OVERCLAIM or UNDECLARED exists, else 0. Declared gaps
never fail the run - otherwise a medical-device crosswalk, where process and
organisational requirements legitimately outnumber the record-layer ones,
could never be green and the tool would be abandoned instead of trusted.

Usage:
    python tools/crosswalk_probe.py crosswalk/eu-mdr-2017-745.json
    python tools/crosswalk_probe.py crosswalk/eu-mdr-2017-745.json \\
        --json tools/out/crosswalk-eu-mdr.json --md docs/CROSSWALK-EU-MDR-ANNEX-I.md
    python tools/crosswalk_probe.py crosswalk/eu-mdr-2017-745.json --no-probe

Input schema (uibc-crosswalk/1), one clause per row:
    {
      "id": "MDR Annex I 17.2",
      "text": "quoted requirement text, verbatim",
      "url": "direct link to the text",
      "applies": true,
      "strength": "carried" | "partial" | "gap",
      "carrier": ["evidence type EVAL", "policy_hash"],
      "probe": {"cmd": "...", "expect": {"exit": 0, "stdout_contains": "..."}} | null,
      "reason": "required for partial and gap; states what is NOT covered"
    }

The manifest digest printed at the end is the identity of the mapped set (the
same shape Annex II 4(d) asks for when it demands "the precise identity of the
controlled documents offering evidence"). It changes when any clause text,
strength or reason changes, and it does not change when only a probe's timing
changes.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = "uibc-crosswalk/1"

OK_STATES = ("COVERED", "PARTIAL", "GAP", "UNRUN")
BAD_STATES = ("OVERCLAIM", "UNDECLARED")


def _normalize_cmd(cmd):
    """Point a documented 'python ...' probe at the interpreter running this."""
    cmd = (cmd or "").strip()
    if cmd.startswith("python "):
        return '"%s" %s' % (sys.executable, cmd[len("python "):])
    return cmd


def run_probe(probe, cwd=REPO, timeout=600):
    cmd = _normalize_cmd(probe.get("cmd"))
    expect = probe.get("expect") or {}
    t0 = time.time()
    try:
        p = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        code = p.returncode
        exit_ok = code == int(expect.get("exit", 0))
        rx = expect.get("stdout_contains")
        rx_ok = bool(re.search(rx, out)) if rx else True
        return {
            "cmd": cmd,
            "declared": probe.get("cmd"),
            "exit": code,
            "expect_exit": int(expect.get("exit", 0)),
            "stdout_contains": rx,
            "ok": bool(exit_ok and rx_ok),
            "duration_s": round(time.time() - t0, 2),
            "tail": [ln for ln in out.strip().splitlines()[-4:]],
        }
    except subprocess.TimeoutExpired:
        return {
            "cmd": cmd, "exit": None, "expect_exit": int(expect.get("exit", 0)),
            "ok": False, "duration_s": timeout, "tail": ["TIMEOUT"],
        }


def classify(strength, reason, probe_result, ran=True, verbatim=True):
    """Pure decision function. Kept separate so tests can drive it directly.

    verbatim=False means the clause text itself was not quoted from the source
    (paid standards, or a summary read instead of the standard). A row like that
    may be PARTIAL or GAP - it may not be carried, because "covered" a clause you
    never read is the cheapest form of overclaim there is.
    """
    reason = (reason or "").strip()
    if strength == "carried":
        if not ran:
            return "UNRUN", "no probe executed (--no-probe)"
        if not verbatim:
            return "OVERCLAIM", "carried but the clause text was not quoted verbatim - read the source or lower the strength"
        if probe_result is None:
            return "OVERCLAIM", "carried but the clause declares no probe"
        if not probe_result.get("ok"):
            return "OVERCLAIM", "carried but the probe did not pass"
        return "COVERED", ""
    if probe_result is not None and not probe_result.get("ok") and strength != "gap":
        # A partial row may declare a probe for the part it does carry. If that
        # probe fails, the carried part is no longer shown, and the row would
        # otherwise stay green on the strength of a probe that does not pass.
        return "OVERCLAIM", "declares a probe that did not pass (exit=%s) - the carried part is no longer shown" % (
            probe_result.get("exit"),)
    if strength == "partial":
        if not reason:
            return "UNDECLARED", "partial without a reason - say what is not covered"
        return "PARTIAL", ""
    if strength == "gap":
        if not reason:
            return "UNDECLARED", "gap without a reason - a bare gap is indistinguishable from a forgotten one"
        return "GAP", ""
    return "UNDECLARED", "unknown strength %r" % (strength,)


def manifest_digest(clauses):
    body = json.dumps(clauses, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def evaluate(doc, cwd=REPO, run=True):
    clauses = doc.get("clauses") or []
    rows = []
    diag = []
    for c in clauses:
        probe_result = None
        if run and c.get("probe"):
            probe_result = run_probe(c["probe"], cwd=cwd)
        state, note = classify(c.get("strength"), c.get("reason"), probe_result,
                               ran=run, verbatim=c.get("verbatim", True))
        # Only deterministic fields enter the result. Duration and output tails
        # are diagnostics: they differ between two runs of the same input, and
        # an artifact that differs between two runs of the same input cannot be
        # diffed in CI (oscal-evidence-pipeline, DriftLab and SPARC all make this
        # point; SLSA calls the property "reproducible").
        probe_record = None
        if probe_result:
            probe_record = {k: probe_result.get(k) for k in ("cmd", "declared", "exit", "ok")}
        if probe_result:
            diag.append({"id": c.get("id"), "duration_s": probe_result.get("duration_s"),
                          "tail": probe_result.get("tail")})
        rows.append({
            "id": c.get("id"),
            "applies": c.get("applies", True),
            "strength": c.get("strength"),
            "verbatim": c.get("verbatim", True),
            "state": state,
            "note": note,
            "reason": (c.get("reason") or "").strip(),
            "carrier": c.get("carrier") or [],
            "url": c.get("url"),
            "probe": probe_record,
        })
    counts = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    bad = sum(counts.get(s, 0) for s in BAD_STATES)
    # Identity of the verdict set, separate from the identity of the clause set:
    # it changes when a state changes and does not change when a probe runs
    # slower. This is what a CI drift check compares.
    verdict_body = [{"id": r["id"], "state": r["state"], "strength": r["strength"],
                     "verbatim": r["verbatim"],
                     "probe_exit": (r["probe"] or {}).get("exit")} for r in rows]
    result = {
        "schema": SCHEMA,
        "standard": doc.get("standard") or {},
        "manifest_sha256": manifest_digest(clauses),
        "verdict_sha256": hashlib.sha256(json.dumps(
            verdict_body, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest(),
        "clause_count": len(rows),
        "counts": counts,
        "bad": bad,
        "rows": rows,
        "verdict": "FAIL" if bad else ("PARTIAL-RUN" if counts.get("UNRUN") else "OK"),
    }
    result["_diag"] = diag
    return result


def dumps_result(result):
    """Deterministic serialisation: no dicts, no timings, one fixed format."""
    body = {k: v for k, v in result.items() if not k.startswith("_")}
    return json.dumps(body, ensure_ascii=False, indent=2) + "\n"


def render_md(result):
    std = result["standard"]
    rows = result["rows"]
    counts = result["counts"]
    ident = result["manifest_sha256"]
    lines = []
    lines.append("# Crosswalk: %s" % std.get("title", "(untitled)"))
    lines.append("")
    lines.append("> **Not a compliance statement.** This file is generated by "
                 "`tools/crosswalk_probe.py` from `%s`." % std.get("source", "the crosswalk JSON"))
    lines.append("> Each row is a clause, the part of the package that would carry it, "
                 "and either a probe that runs or a stated reason it cannot.")
    lines.append("> A PASS here means a check ran and returned what was expected - "
                 "not that a regulator, a notified body or a customer accepts anything.")
    lines.append("")
    if std.get("id"):
        lines.append("- Standard: **%s**" % std["id"])
    if std.get("url"):
        lines.append("- Source: %s" % std["url"])
    lines.append("- Clauses mapped: **%d**" % result["clause_count"])
    lines.append("- Manifest digest: `%s`" % ident)
    lines.append("- Verdict digest: `%s` (identity of the verdict set, not of the clause text)" % result["verdict_sha256"])
    lines.append("- Determinism: re-running on the same input yields byte-identical output; "
                 "`--check` exits 3 on any drift. Reproducible in the SLSA sense - "
                 "not verified-reproducible, which would need a second independent host.")
    lines.append("- Counts: " + ", ".join("%s=%d" % (k, counts[k]) for k in sorted(counts)))
    lines.append("")
    lines.append("| Clause | Strength | State | Carrier | Probe | What is not covered |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        probe = "-"
        if r["probe"]:
            shown = r["probe"].get("declared") or r["probe"]["cmd"]
            probe = "`%s` → exit %s" % (shown.replace("|", "\\|"), r["probe"]["exit"])
        reason = (r["reason"] or r["note"] or "-").replace("|", "\\|")
        carrier = ", ".join(r["carrier"]) if r["carrier"] else "-"
        lines.append("| %s | %s | **%s** | %s | %s | %s |" % (
            (r["id"] or "").replace("|", "\\|"),
            r["strength"] + ("" if r.get("verbatim", True) else " (titles only)"),
            r["state"],
            carrier.replace("|", "\\|"), probe, reason))
    lines.append("")
    lines.append("## How to re-run")
    lines.append("")
    lines.append("```")
    lines.append("python tools/crosswalk_probe.py %s" % std.get("source", "<crosswalk>.json"))
    lines.append("```")
    lines.append("")
    lines.append("Exit code 0 means: every clause claiming coverage ran a probe that passed, "
                 "and every clause not covered says why. It does not mean the gaps are acceptable - "
                 "it means the gaps are counted.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Clause-level conformance probes with declared gaps.")
    ap.add_argument("crosswalk", help="path to a uibc-crosswalk/1 JSON file")
    ap.add_argument("--json", dest="json_out", help="write the machine result here")
    ap.add_argument("--md", dest="md_out", help="write a generated markdown table here")
    ap.add_argument("--diag", dest="diag_out", help="write probe timings and output tails here (not deterministic)")
    ap.add_argument("--check", dest="check_against", metavar="COMMITTED_JSON",
                    help="compare this run's result to a committed file; exit 3 on any difference")
    ap.add_argument("--no-probe", action="store_true", help="static check only; carried clauses become UNRUN")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    path = args.crosswalk
    if not os.path.isabs(path):
        path = os.path.join(REPO, path)
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("schema") != SCHEMA:
        sys.stderr.write("refusing: schema is %r, expected %r\n" % (doc.get("schema"), SCHEMA))
        return 2

    doc.setdefault("standard", {})["source"] = os.path.relpath(path, REPO).replace("\\", "/")
    result = evaluate(doc, cwd=REPO, run=not args.no_probe)

    if args.check_against:
        committed_path = args.check_against
        if not os.path.isabs(committed_path):
            committed_path = os.path.join(REPO, committed_path)
        try:
            with open(committed_path, "r", encoding="utf-8") as f:
                committed = f.read()
        except FileNotFoundError:
            print("DRIFT: no committed result at %s - nothing to compare" % args.check_against)
            return 3
        fresh = dumps_result(result)
        if fresh != committed:
            print("DRIFT: %s no longer matches a fresh run\n"
                  "  committed bytes=%d, fresh bytes=%d\n"
                  "  re-run with --json to regenerate, then review the diff before committing"
                  % (args.check_against, len(committed), len(fresh)))
            return 3
        if not args.quiet:
            print("STABLE: %s matches a fresh run byte for byte" % args.check_against)

    if not args.quiet:
        for r in result["rows"]:
            print("%-13s %-32s %s" % (r["state"], r["id"], r["note"]))
        counts = result["counts"]
        print("\nclauses=%d  %s  manifest=%s  verdict=%s" % (
            result["clause_count"],
            "  ".join("%s=%d" % (k, counts[k]) for k in sorted(counts)),
            result["manifest_sha256"][:16],
            result["verdict_sha256"][:16]))
        print("verdict: %s" % result["verdict"])

    if args.json_out:
        out = args.json_out if os.path.isabs(args.json_out) else os.path.join(REPO, args.json_out)
        os.makedirs(os.path.dirname(out) or REPO, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(dumps_result(result))
    if args.diag_out:
        out = args.diag_out if os.path.isabs(args.diag_out) else os.path.join(REPO, args.diag_out)
        os.makedirs(os.path.dirname(out) or REPO, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(result.get("_diag") or [], f, ensure_ascii=False, indent=2)
            f.write("\n")
    if args.md_out:
        out = args.md_out if os.path.isabs(args.md_out) else os.path.join(REPO, args.md_out)
        os.makedirs(os.path.dirname(out) or REPO, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_md(result))
    return 1 if result["bad"] else 0


if __name__ == "__main__":
    sys.exit(main())
