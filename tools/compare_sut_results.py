#!/usr/bin/env python3
"""Compare two or more `sut-result.json` files, case by case.

`tools/run_decision_vectors.py --sut-result` produces one file per implementation.
This tool is the other half: it takes those files and answers the only question an
interoperability matrix may answer honestly - *on the same corpus bytes, do two
implementations answer the same thing?*

Three rules, because a comparison engine that is generous with evidence is worse
than no comparison engine:

1. **Different corpora are not comparable.** If the digests differ, the tool stops
   and says so. Two files about different inputs can only produce a table that
   looks like a finding and is not one.
2. **A disagreement on what was *expected* is a corpus defect**, not an
   implementation defect. That stops the run too, naming the case.
3. **Divergence is printed, never scored.** Every case appears with what each
   implementation answered. Nothing is averaged, nothing is called "failed".

Exit codes: 0 every implementation answered identically on every case, 1 at least
one case diverged, 2 the files cannot be compared (different corpora, a schema
problem, or two files disagreeing on the expected value).
"""
from __future__ import annotations

import argparse
import json
import sys

REQUIRED_TOP = ("implementation", "corpus", "cases")
REQUIRED_CASE = ("id", "expected", "observed", "verdict")


class Uncomparable(Exception):
    """The files do not describe the same experiment."""


def load(paths):
    docs = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise Uncomparable("%s: cannot read a sut-result: %s" % (p, exc))
        for key in REQUIRED_TOP:
            if key not in doc:
                raise Uncomparable("%s: missing %r - not a sut-result file" % (p, key))
        if not isinstance(doc["corpus"], dict) or not doc["corpus"].get("digest"):
            raise Uncomparable("%s: corpus digest missing" % p)
        for case in doc["cases"]:
            for key in REQUIRED_CASE:
                if key not in case:
                    raise Uncomparable("%s: case %r missing %r"
                                       % (p, case.get("id"), key))
            for half in ("expected", "observed"):
                if set(case[half]) != {"decision", "exit"}:
                    raise Uncomparable("%s: case %r has no %s decision/exit pair"
                                       % (p, case["id"], half))
        doc["_path"] = p
        docs.append(doc)
    digests = {d["corpus"]["digest"] for d in docs}
    if len(digests) > 1:
        raise Uncomparable(
            "these files were produced on different corpus bytes, so a difference "
            "between them would be a difference about inputs, not implementations:\n"
            + "\n".join("  %s  %s" % (d["_path"], d["corpus"]["digest"]) for d in docs))
    ids = {d["_path"]: [c["id"] for c in d["cases"]] for d in docs}
    order = None
    for d in docs:
        if order is None:
            order = ids[d["_path"]]
        elif ids[d["_path"]] != order:
            raise Uncomparable("the files carry different case ids: %s vs %s"
                               % (d["_path"], docs[0]["_path"]))
    return docs, order


def compare(docs, order):
    names = [d["implementation"] for d in docs]
    if len(set(names)) != len(names):
        # Two files from the "same" implementation are either the same file twice
        # or an ambiguous label; either way the table would be unreadable.
        raise Uncomparable("two files share the label %r - give each run a distinct "
                           "--sut-label" % [n for n in names if names.count(n) > 1][0])
    per_case = {}
    for cid in order:
        rows = {}
        for d in docs:
            case = next(c for c in d["cases"] if c["id"] == cid)
            rows[d["implementation"]] = case
        expected = {json.dumps(r["expected"], sort_keys=True) for r in rows.values()}
        if len(expected) > 1:
            raise Uncomparable(
                "case %s: the files disagree on what was expected - that is a corpus "
                "problem, and comparing observations against two different expectations "
                "would produce a number nobody can defend: %s"
                % (cid, {k: v["expected"] for k, v in rows.items()}))
        observed = {json.dumps(r["observed"], sort_keys=True) for r in rows.values()}
        internally_off = any(r["verdict"] != "MATCH" for r in rows.values())
        per_case[cid] = {"expected": next(iter(rows.values()))["expected"],
                         "rows": rows,
                         "agreement": len(observed) == 1 and not internally_off,
                         "distinct_observed": len(observed)}
    return names, per_case


def render(names, per_case):
    agree = [cid for cid, c in per_case.items() if c["agreement"]]
    diff = [cid for cid, c in per_case.items() if not c["agreement"]]
    out = []
    out.append("# Comparison of %d implementations on one corpus" % len(names))
    out.append("")
    out.append("| case | expected | " + " | ".join(names) + " | verdict |")
    out.append("|---" + "|---" * (len(names) + 2) + "|")
    for cid, c in per_case.items():
        cells = []
        for n in names:
            o = c["rows"][n]["observed"]
            cells.append("`%s/%s`" % (o["decision"], o["exit"]))
        out.append("| %s | `%s/%s` | %s | %s |"
                   % (cid, c["expected"]["decision"], c["expected"]["exit"],
                      " | ".join(cells),
                      "agree" if c["agreement"] else "**diverge** (%d observations)"
                      % c["distinct_observed"]))
    out.append("")
    out.append("%d/%d cases agree." % (len(agree), len(per_case)))
    if diff:
        out.append("")
        out.append("Divergent cases: " + ", ".join(diff) + ".")
        out.append("")
        out.append("A divergence is a question about the specification, not a verdict "
                   "about either implementation. It belongs in the interoperability "
                   "matrix as a difference, with both answers quoted.")
    return "\n".join(out) + "\n", agree, diff


def main(argv=None):
    ap = argparse.ArgumentParser(description="compare sut-result files case by case")
    ap.add_argument("files", nargs="+", help="two or more sut-result.json files")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if len(a.files) < 2:
        print("give at least two files: disagreeing with yourself proves nothing",
              file=sys.stderr)
        return 2
    try:
        docs, order = load(a.files)
        names, per_case = compare(docs, order)
    except Uncomparable as exc:
        print("NOT COMPARABLE: %s" % exc, file=sys.stderr)
        return 2
    text, agree, diff = render(names, per_case)
    if a.json:
        print(json.dumps({
            "implementations": names,
            "corpus_digest": docs[0]["corpus"]["digest"],
            "cases": len(per_case),
            "agreeing": agree,
            "diverging": diff,
            "scope": ("Agreement is about these cases on these corpus bytes, nothing "
                      "more. A divergence is a difference to specify, not a defect in "
                      "either side, and one run is not an audit."),
        }, indent=2))
    else:
        print(text, end="")
    return 0 if not diff else 1


if __name__ == "__main__":
    sys.exit(main())
