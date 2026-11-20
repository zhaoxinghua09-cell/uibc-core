#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convention crosswalk: the only part of a gate that can be compared across vendors.

Every published false-accept number is a ratio whose numerator depends on what counts
as "accepted". Three defensible conventions exist, and they do not agree:

  strict   any non-FAIL verdict counts as an acceptance  (INCONCLUSIVE = accepted)
  lenient  only PASS counts as an acceptance            (INCONCLUSIVE = not accepted)
  excluded NA and INCONCLUSIVE leave the denominator    (the case is not judged)

arXiv 2604.17125 reports the same pipeline at 11.70% or 1.51% false positives depending
purely on which of these a caller used. That means two vendors' FPR numbers are not
comparable until both say which convention produced them. This tool takes per-case
verdicts plus ground truth and emits all three, so a number can be compared or exposed
as incomparable.

What this is NOT: it cannot judge a format. The artifact-layer checks (is the seal valid,
is the index complete) are vendor-specific and stay out of this file. This module takes
verdicts that someone else already produced and asks a single question: under which
convention, and with which denominator, does that number mean what the publisher claims.

Input (JSON):
  {
    "subject": "any string",
    "convention_claimed": "strict|lenient|excluded|unknown",
    "cases": [{"id": "...", "truth": "harmful|benign|unknown", "verdict": "PASS|FAIL|INCONCLUSIVE|NA"}]
  }

Output: a table of rates per convention, plus a disclosure block that a publisher can paste
next to their number, plus warnings where the claim and the arithmetic disagree.

Usage:
  python convention_crosswalk.py --input cases.json [--json out.json]
  python convention_crosswalk.py --self-test
"""
import argparse
import json
import sys

VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE", "NA")
TRUTHS = ("harmful", "benign", "unknown")


def accepts(verdict, convention):
    """Does this verdict count as 'the gate let it through' under this convention?"""
    if convention == "strict":
        return verdict in ("PASS", "INCONCLUSIVE")
    if convention == "lenient":
        return verdict == "PASS"
    if convention == "excluded":
        return verdict == "PASS"      # NA/INCONCLUSIVE leave the denominator entirely
    raise ValueError("convention must be strict|lenient|excluded")


def in_denominator(verdict, convention):
    if convention == "excluded":
        return verdict not in ("NA", "INCONCLUSIVE")
    return True


def rate(cases, convention):
    num = den = 0
    accepted_ids = []
    for c in cases:
        if c.get("truth") != "harmful":
            continue
        if not in_denominator(c["verdict"], convention):
            continue
        den += 1
        if accepts(c["verdict"], convention):
            num += 1
            accepted_ids.append(c["id"])
    fpr_num = fpr_den = 0   # benign cases wrongly rejected, for the mirror number
    for c in cases:
        if c.get("truth") != "benign":
            continue
        if not in_denominator(c["verdict"], convention):
            continue
        fpr_den += 1
        if c["verdict"] in ("FAIL", "INCONCLUSIVE") if convention == "strict" else c["verdict"] == "FAIL":
            fpr_num += 1
    return {
        "false_accept": num, "denominator": den,
        "rate": (num / den) if den else None,
        "accepted_ids": accepted_ids,
        "false_reject": fpr_num, "benign_denominator": fpr_den,
        "false_reject_rate": (fpr_num / fpr_den) if fpr_den else None,
    }


def audit(doc, label=""):
    cases = doc.get("cases") or []
    bad = [c for c in cases if c.get("verdict") not in VERDICTS or c.get("truth") not in TRUTHS]
    unknown_truth = [c for c in cases if c.get("truth") == "unknown"]
    warn = []
    if bad:
        warn.append("%d case(s) with unrecognised verdict/truth; excluded from arithmetic" % len(bad))
    if unknown_truth:
        warn.append("%d case(s) with truth=unknown carry no information about correctness "
                    "and are excluded — count them only as coverage" % len(unknown_truth))
    usable = [c for c in cases if c.get("verdict") in VERDICTS and c.get("truth") in ("harmful", "benign")]
    rows = {}
    for conv in ("strict", "lenient", "excluded"):
        rows[conv] = rate(usable, conv)
    claimed = (doc.get("convention_claimed") or "unknown").lower()
    if claimed not in ("strict", "lenient", "excluded", "unknown"):
        warn.append("convention_claimed=%r is not one of strict|lenient|excluded" % claimed)
    rates = [r["rate"] for r in rows.values() if r["rate"] is not None]
    spread = (max(rates) - min(rates)) if len(rates) >= 2 else 0.0
    return {"label": label, "subject": doc.get("subject", ""), "claimed": claimed,
            "rows": rows, "spread": spread, "warnings": warn,
            "usable_cases": len(usable)}


def report(a, indent=""):
    out = []
    out.append("%ssubject: %s" % (indent, a["subject"] or "(unnamed)"))
    out.append("%sclaimed convention: %s" % (indent, a["claimed"]))
    out.append("")
    out.append("%s| convention | false accepts | denominator | rate | wrong rejects (benign) |" % indent)
    out.append("%s|---|---|---|---|---|" % indent)
    for conv in ("strict", "lenient", "excluded"):
        r = a["rows"][conv]
        rt = "n/a" if r["rate"] is None else "%.1f%%" % (100 * r["rate"])
        fr = "n/a" if r["false_reject_rate"] is None else "%.1f%% (%d/%d)" % (
            100 * r["false_reject_rate"], r["false_reject"], r["benign_denominator"])
        out.append("%s| %s | %d | %d | %s | %s |" % (indent, conv, r["false_accept"], r["denominator"], rt, fr))
    out.append("")
    rates = [r["rate"] for r in a["rows"].values() if r["rate"] is not None]
    if rates:
        lo, hi = min(rates), max(rates)
        tail = ""
        if lo > 1e-9:
            tail = " — a factor of %.1f" % (hi / lo)
        out.append("%s**Convention spread: %.1f%% to %.1f%%%s.** The same cases, three defensible "
                   "readings." % (indent, 100 * lo, 100 * hi, tail))
    if a["claimed"] != "unknown":
        r = a["rows"].get(a["claimed"])
        if r:
            shown = "n/a" if r["rate"] is None else "%.1f%%" % (100 * r["rate"])
            out.append("%sPublisher claims `%s`: that is %d/%d = %s. Quote that number only with "
                       "the convention and denominator attached."
                       % (indent, a["claimed"], r["false_accept"], r["denominator"], shown))
    for w in a["warnings"]:
        out.append("%s! %s" % (indent, w))
    return "\n".join(l for l in out if l.strip())


def self_test():
    """Synthetic cases with a known answer. A tool like this must fail loudly if it drifts."""
    ok = True
    def check(name, got, want):
        nonlocal ok
        if got != want:
            print("FAIL %s: got %r want %r" % (name, got, want))
            ok = False

    # 10 harmful: 4 PASS, 3 INCONCLUSIVE, 2 FAIL, 1 NA.
    cases = ([{"id": "h%d" % i, "truth": "harmful",
               "verdict": ("PASS" if i < 4 else "INCONCLUSIVE" if i < 7 else "FAIL" if i < 9 else "NA")}
              for i in range(10)]
             + [{"id": "b%d" % i, "truth": "benign",
                 "verdict": "FAIL" if i == 0 else "INCONCLUSIVE" if i == 1 else "PASS"} for i in range(5)])
    a = audit({"subject": "synthetic", "convention_claimed": "lenient", "cases": cases})
    check("lenient numerator", a["rows"]["lenient"]["false_accept"], 4)
    check("lenient denominator", a["rows"]["lenient"]["denominator"], 10)
    check("strict numerator", a["rows"]["strict"]["false_accept"], 7)
    check("excluded numerator", a["rows"]["excluded"]["false_accept"], 4)
    check("excluded denominator", a["rows"]["excluded"]["denominator"], 6)
    check("lenient benign rejects", a["rows"]["lenient"]["false_reject"], 1)
    check("strict benign rejects", a["rows"]["strict"]["false_reject"], 2)
    check("spread exists", round(a["spread"], 4), round(0.7 - 0.4, 4))

    # Truth=unknown must not enter arithmetic at all.
    b = audit({"cases": [{"id": "u", "truth": "unknown", "verdict": "PASS"}]})
    check("unknown truth excluded", b["rows"]["lenient"]["denominator"], 0)
    check("unknown truth warns", any("truth=unknown" in w for w in b["warnings"]), True)

    # Bad verdict must be excluded rather than silently counted.
    c = audit({"cases": [{"id": "x", "truth": "harmful", "verdict": "MAYBE"}]})
    check("bad verdict excluded", c["rows"]["lenient"]["denominator"], 0)
    check("bad verdict warns", any("unrecognised" in w for w in c["warnings"]), True)
    print("SELF-TEST %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input")
    ap.add_argument("--json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.input:
        ap.print_help()
        return 2
    doc = json.load(open(a.input, encoding="utf-8"))
    res = audit(doc)
    print(report(res))
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), indent=2)
        print("\nwritten: %s" % a.json)
    # Exit 1 when a publisher's claimed convention does not reproduce any number, because
    # that is the one condition under which their published figure is unusable.
    if res["claimed"] not in ("unknown",) and not res["rows"].get(res["claimed"], {}).get("denominator"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
