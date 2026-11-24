#!/usr/bin/env python3
"""Run any UIBC verifier against the 9 hostile packages in this kit.

    python run_matrix.py --label mine -- python -m uibc_core.cli verify
    python run_matrix.py --label mine -- python ivcli.py

Rules checked (see EXPECTED.json):
  1. must_answer  - a crash is not a verdict
  2. must_refuse  - no case may come out PASS
Exit: 0 both rules hold; 1 a rule broke; 3 the kit could not run.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = sorted(os.listdir(os.path.join(HERE, "cases")))


def classify(p):
    if "Traceback (most recent call last)" in (p.stderr or ""):
        return "CRASH", (p.stderr.strip().splitlines() or [""])[-1][:80]
    if p.returncode != 0 and not p.stdout.strip():
        return "CRASH", "silent exit %d" % p.returncode
    try:
        d = json.loads(p.stdout)
        return str(d.get("result") or d.get("decision") or "JSON?"), ""
    except Exception:
        first = (p.stdout.strip().splitlines() or [""])[0]
        return "TEXT", first[:80]


def main():
    ap = argparse.ArgumentParser()
    argv = sys.argv[1:]
    label, as_json, cmd, pin = "sut", False, [], None
    i = 0
    while i < len(argv):
        if argv[i] == "--label" and i + 1 < len(argv):
            label = argv[i + 1]; i += 2
        elif argv[i] == "--json":
            as_json = True; i += 1
        elif argv[i] == "--pin" and i + 1 < len(argv):
            pin = argv[i + 1]; i += 2
        elif argv[i] == "--":
            cmd = argv[i + 1:]; break
        else:
            i += 1
    if not cmd:
        sys.stderr.write("give the SUT command after --\n")
        return 3
    rows, crashes, passes = [], 0, 0
    for case in CASES:
        pkg = os.path.join(HERE, "cases", case)
        p = subprocess.run(cmd + [pkg], capture_output=True, text=True, timeout=180)
        verdict, note = classify(p)
        if verdict == "CRASH":
            crashes += 1
        if verdict == "PASS":
            passes += 1
        nchecks = 0
        try:
            j = json.loads(p.stdout)
            c = j.get("checks")
            nchecks = len(c) if isinstance(c, (list, dict)) else 0
        except Exception:
            nchecks = 0
        structured = nchecks >= 8 or verdict.startswith("UNREADABLE")
        rows.append({"case": case, "verdict": verdict, "exit": p.returncode, "note": note,
                     "stdout_is_json": p.stdout.strip().startswith("{"),
                     "nchecks": nchecks, "structured": structured})
    thin = sum(1 for r in rows if not r["structured"])
    # positive case: only judged when a pin key is supplied, because a
    # correct verifier is INCONCLUSIVE without one (seal present, nothing to check it against).
    accept = None
    if pin:
        p = subprocess.run(cmd + [os.path.join(HERE, "positive", "clean"), "--pubkey", pin],
                           capture_output=True, text=True, timeout=180)
        v, _ = classify(p)
        accept = (v == "PASS")
    doc = {"label": label, "must_accept": accept, "sut": " ".join(cmd), "rules": {"must_answer": crashes == 0,
           "must_refuse": passes == 0, "must_structure": thin == 0},
           "thin_reports": thin, "crashes": crashes, "passes": passes, "rows": rows}
    if as_json:
        print(json.dumps(doc, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print("%-22s %-14s exit=%-3s %s" % (r["case"], r["verdict"], r["exit"], r["note"]))
        print("\nmust_answer=%s  must_refuse=%s  must_structure=%s"
              % (doc["rules"]["must_answer"], doc["rules"]["must_refuse"],
                 doc["rules"]["must_structure"]))
    # must_structure stays advisory on purpose: the reference implementation
    # legitimately reports <8 checks when serialization fails early (measured),
    # so promoting it to a gate would accuse a correct verifier.
    ok = crashes == 0 and passes == 0 and (accept is None or accept)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
