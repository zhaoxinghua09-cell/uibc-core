#!/usr/bin/env python3
"""Tie the numbers in claims-register.md to the receipts they come from.

A claim row is prose. A receipt is JSON. Between them sat a person copying a
number, which is exactly where a page goes stale without anyone noticing: the
receipt gets regenerated, the sentence keeps its old figure, and every gate stays
green because each of them checked only its own half.

So each receipt-backed row carries one machine-readable annotation naming the
receipt and the fields it quotes:

    | A18 | ... | <!-- lock: docs/.../corpus-sweep-39daf704.json
                            totals.vectors,totals.n_replayable,... -->

Three checks, all mechanical:

  1. the annotation names a receipt that exists;
  2. every field it names resolves to an integer in that receipt;
  3. that integer appears as a standalone number in the row's own visible text,
     and the receipt's file name appears in the row as well.

A row with no annotation is reported as unlocked, not silently passed: the
coverage line says how many of the rows are actually held.

    python tools/audit_claims_receipts.py            # report and exit 0/1
    python tools/audit_claims_receipts.py --json
    python tools/audit_claims_receipts.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAIMS = os.path.join(HERE, "docs", "claims-register.md")

LOCK_RE = re.compile(r"<!--\s*lock:\s*([^ ]+)\s+([^>]+?)\s*-->")
ROW_RE = re.compile(r"^\|\s*(A\d+)\s*\|")


def _strip_annotation(line):
    return LOCK_RE.sub("", line)


def _resolve(receipt, root):
    return os.path.join(root, *receipt.split("/"))


def _field(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def audit(text, root=HERE):
    """Return (rows, problems, stats). rows: dict per claim id with its lock."""
    problems = []
    rows = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        claim = m.group(1)
        m_lock = LOCK_RE.search(line)
        visible = _strip_annotation(line)
        entry = {"claim": claim, "locked": bool(m_lock), "receipt": None,
                 "fields": [], "values": {}}
        if not m_lock:
            rows.append(entry)
            continue
        receipt, fields = m_lock.group(1), [f.strip() for f in m_lock.group(2).split(",")]
        entry["receipt"], entry["fields"] = receipt, fields
        path = _resolve(receipt, root)
        if not os.path.exists(path):
            problems.append("%s: receipt not found: %s" % (claim, receipt))
            rows.append(entry)
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        base = os.path.basename(receipt)
        if base not in visible:
            problems.append("%s: the row does not name %s" % (claim, base))
        for field in fields:
            value = _field(data, field)
            if not isinstance(value, int) or isinstance(value, bool):
                problems.append("%s: %s is not an integer in %s (got %r)"
                                % (claim, field, base, value))
                continue
            entry["values"][field] = value
            if not re.search(r"(?<!\d)%d(?!\d)" % value, visible):
                problems.append("%s: %s = %d does not appear in the row's text"
                                % (claim, field, value))
        rows.append(entry)
    locked = sum(1 for r in rows if r["locked"])
    return rows, problems, {"claims": len(rows), "locked": locked,
                            "unlocked": len(rows) - locked}


def _selftest():
    ok, fails = 0, []

    def check(label, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fails.append(label)

    import tempfile

    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "docs", "x"))
    receipt = {"totals": {"vectors": 171, "n_replayable": 69}}
    path = os.path.join(root, "docs", "x", "r.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(receipt, f)

    good = ("| A18 | 69 of 171 replayed, receipt docs/x/r.json | "
            "<!-- lock: docs/x/r.json totals.vectors,totals.n_replayable -->\n")
    rows, problems, stats = audit(good, root)
    check("a matching row passes", problems == [] and stats["locked"] == 1)

    stale = good.replace("69 of 171", "70 of 171")
    rows, problems, stats = audit(stale, root)
    check("a prose figure that moved is caught", len(problems) >= 1 and
          any("does not appear" in p for p in problems))

    moved = good
    receipt_bad = {"totals": {"vectors": 171, "n_replayable": 71}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(receipt_bad, f)
    rows, problems, stats = audit(moved, root)
    check("a receipt that moved is caught", any("does not appear" in p for p in problems))

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"totals": {"vectors": 171, "n_replayable": "69"}}, f)
    rows, problems, stats = audit(moved, root)
    check("a non-integer field is caught", any("not an integer" in p for p in problems))

    missing = good.replace("docs/x/r.json", "docs/x/nope.json")
    rows, problems, stats = audit(missing, root)
    check("a missing receipt is caught", any("not found" in p for p in problems))

    unlocked = "| A99 | nothing locked here |\n"
    rows, problems, stats = audit(unlocked, root)
    check("an unlocked row is counted, not passed",
          problems == [] and stats == {"claims": 1, "locked": 0, "unlocked": 1})

    if fails:
        print("SELFTEST FAILED: %s" % "; ".join(fails))
        return 1
    print("SELFTEST OK: %d checks" % ok)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return _selftest()

    with open(CLAIMS, encoding="utf-8") as f:
        text = f.read()
    rows, problems, stats = audit(text)
    if args.json:
        print(json.dumps({"rows": rows, "problems": problems, "stats": stats},
                         indent=2, ensure_ascii=False))
        return 0 if not problems else 1
    print("claims: %d rows, %d locked to a receipt, %d unlocked"
          % (stats["claims"], stats["locked"], stats["unlocked"]))
    for row in rows:
        if row["locked"]:
            print("  %-4s %s  %s" % (row["claim"], os.path.basename(row["receipt"]),
                                     ", ".join("%s=%d" % (k.split(".")[-1], v)
                                               for k, v in row["values"].items())))
    for problem in problems:
        print("PROBLEM %s" % problem)
    print("VERDICT: %s" % ("NUMBERS AGREE" if not problems else "NUMBERS DRIFTED"))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
