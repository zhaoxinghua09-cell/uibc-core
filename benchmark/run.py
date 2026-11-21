#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Public re-runner for the 21-class mutation benchmark.

    python benchmark/run.py

What it does: builds the base package, applies all 21 mutations, verifies each
in three observation modes, then compares the outcome with `expected.json` and
reports two DIFFERENT numbers:

    acceptance rate            - how many mutations were accepted, period
    undocumented acceptance    - those NOT explained by a channel the mode lacks

Only the second is a defect. Publishing a single rate lets a reader mistake a
documented design boundary (a key that lives inside the package) for a bug; and
publishing only the second lets a reader think nothing was accepted at all.

Exit code: 0 if every acceptance is documented or expected, 1 otherwise.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXPECTED = os.path.join(HERE, "expected.json")
RESULTS = os.path.join(ROOT, "tools", "out", "mutation_benchmark.json")
OUT = os.path.join(HERE, "results.json")
MODES = ["open", "pinned", "head-pinned"]


def main():
    if not os.path.exists(RESULTS) or "--rerun" in sys.argv:
        print("running tools/mutation_benchmark.py ...")
        rc = subprocess.call([sys.executable,
                              os.path.join(ROOT, "tools", "mutation_benchmark.py")],
                             cwd=ROOT)
        if rc != 0:
            print("benchmark run failed (rc=%d)" % rc)
            return 2

    exp = json.load(open(EXPECTED, encoding="utf-8"))
    by_id = {c["id"]: c for c in exp["cases"]}
    by_design = {m: set(exp["by_design_accept"].get(m, [])) for m in MODES}
    observed = json.load(open(RESULTS, encoding="utf-8"))

    rows, defects = [], []
    for row in observed["rows"]:
        mid = row["id"].split()[0]
        entry = {"id": mid, "mutation": row.get("mutation", ""), "modes": {}}
        for mode in MODES:
            m = row["modes"].get(mode)
            if not m:
                continue
            accepted = bool(m.get("accepted"))
            documented = mid in by_design[mode]
            entry["modes"][mode] = {
                "verdict": m.get("verdict"),
                "accepted": accepted,
                "failed_checks": m.get("failed_checks", []),
                "documented_by_design": documented,
            }
            if accepted and not documented:
                defects.append({"id": mid, "mode": mode, "mutation": entry["mutation"]})
        rows.append(entry)

    summary = {}
    for mode in MODES:
        s = observed["summary"].get(mode, {})
        acc = s.get("accepted", 0)
        undoc = sum(1 for d in defects if d["mode"] == mode)
        summary[mode] = {
            "accepted": acc,
            "total": s.get("total", len(rows)),
            "acceptance_rate_pct": s.get("false_accept_rate"),
            "documented_accepts": sorted(by_design[mode] & {r["id"] for r in rows
                                                            if r["modes"].get(mode, {}).get("accepted")}),
            "undocumented_accepts": undoc,
            "undocumented_accept_rate_pct": round(100.0 * undoc / max(len(rows), 1), 1),
        }

    # The anchor that stops a refuse-everything verifier scoring well: the
    # unmutated package is in the corpus and must PASS. Without it a verifier
    # that rejects all 21 mutations reports a perfect acceptance rate while
    # being useless. The verdict comes from the benchmark run, not from this
    # file, so it cannot be asserted here.
    anchor = {"base_open": observed.get("meta", {}).get("base_open"),
              "base_pinned": observed.get("meta", {}).get("base_pinned"),
              "base_must_be": "PASS",
              "anchor_ok": observed.get("meta", {}).get("base_pinned") == "PASS"}

    doc = {"meta": {"generated_at_utc": __import__("time").strftime(
                "%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
            "source": "tools/out/mutation_benchmark.json",
            "expected": "benchmark/expected.json",
            "spec_id": _spec_id(),
            "corpus_anchor": anchor},
           "summary": summary, "rows": rows,
           "corpus_anchor": anchor, "defects": defects}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print("\n%-6s %-34s %-12s %-12s %-12s" % ("id", "mutation", "open", "pinned", "head-pinned"))
    for r in rows:
        cells = []
        for mode in MODES:
            m = r["modes"].get(mode)
            if not m:
                cells.append("-")
            elif not m["accepted"]:
                cells.append("rejected")
            elif m["documented_by_design"]:
                cells.append("accepted*")
            else:
                cells.append("ACCEPTED!")
        print("%-6s %-34s %-12s %-12s %-12s" % (r["id"], r["mutation"][:34], *cells))

    print("\n* accepted by design: the mode lacks the observation channel that "
          "case needs (key outside the package / head outside the package)")
    print("corpus anchor: base(open)=%s base(pinned)=%s (must be PASS; "
          "a verifier that refuses everything scores 0/22, not 22/22)"
          % (anchor["base_open"], anchor["base_pinned"]))
    for mode in MODES:
        s = summary[mode]
        print("%-12s accepted %d/%d (%.1f%%) | documented %s | UNDOCUMENTED %d"
              % (mode, s["accepted"], s["total"], s["acceptance_rate_pct"],
                 s["documented_accepts"], s["undocumented_accepts"]))
    print("\nRESULT_JSON=" + OUT)
    if not anchor["anchor_ok"]:
        print("!! 基线未 PASS：接受率数字不可引用，先修基线")
        return 1
    return 0 if not defects else 1


def _spec_id():
    try:
        sys.path.insert(0, ROOT)
        import uibc_core
        return uibc_core.spec_id()
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
