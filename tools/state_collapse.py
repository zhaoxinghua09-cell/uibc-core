#!/usr/bin/env python3
"""How much a verdict vocabulary can say, measured rather than argued.

Seven states exist in `uibc_core.interop_result`. Whether that is *better* than
a boolean is not a matter of taste: the states differ in what a recipient can
do next, and a vocabulary that merges them throws that away. This tool computes
the merge, using our seven states as the input set and two other published
shapes as the targets:

  boolean  -- `decision: true/false` (OpenID AuthZEN Authorization API 1.0)
  ladder   -- L1/L2/L3 with fail-closed demotion (DIF KYA-OS, Core ladder)

Both mappings are **our reading of their public documents, not their systems**.
Neither project is claimed to be unable to add states; this measures what each
published shape carries today.

    python3 tools/state_collapse.py            # table + receipt
    python3 tools/state_collapse.py --json     # machine-readable

Zero dependencies. Offline. Exit 0 always: this reports a measurement, not a
verdict about anyone.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from uibc_core import interop_result as ir  # noqa: E402 - repo boundary

# What a recipient usually needs to tell apart. Each pair differs in the *next
# action* available: retry elsewhere, ask for evidence, escalate to a human,
# stop trusting the issuer. A model that merges a pair cannot say which.
CRITICAL_PAIRS = [
    ("UNSUPPORTED", "REVOKED"),      # "we cannot read your method" vs "you were revoked"
    ("INCONCLUSIVE", "REVOKED"),     # "we could not decide" vs "you were revoked"
    ("UNRESOLVED", "UNSUPPORTED"),   # "we could not reach it" vs "we do not do this"
    ("EXPIRED", "INVALID"),          # "it aged out" vs "it is forged"
]

BOOLEAN = {s: ("permit" if s == "VERIFIED" else "deny") for s in ir.STATES}

# Fail-closed demotion: a verified artifact reaches the top rung; anything
# missing or unusable falls to L1; "could not decide" and "could not reach" sit
# at L2 because the artifact is present but unjudged.
LADDER = {
    "VERIFIED": "L3",
    "INCONCLUSIVE": "L2",
    "UNRESOLVED": "L2",
    "INVALID": "L1",
    "REVOKED": "L1",
    "EXPIRED": "L1",
    "UNSUPPORTED": "L1",
}


def _pairs(items):
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            yield items[i], items[j]


def measure(model):
    """Distinct outputs, pairs kept apart, and which critical pairs survive."""
    outputs = sorted({model[s] for s in ir.STATES})
    kept = sum(1 for a, b in _pairs(ir.STATES) if model[a] != model[b])
    total = sum(1 for _ in _pairs(ir.STATES))
    critical_kept = [list(p) for p in CRITICAL_PAIRS if model[p[0]] != model[p[1]]]
    critical_lost = [list(p) for p in CRITICAL_PAIRS if model[p[0]] == model[p[1]]]
    merged = {}
    for s in ir.STATES:
        merged.setdefault(model[s], []).append(s)
    return {
        "distinct_outputs": len(outputs),
        "pairs_total": total,
        "pairs_kept_apart": kept,
        "pairs_merged": total - kept,
        "critical_kept": critical_kept,
        "critical_lost": critical_lost,
        "outputs": {k: v for k, v in merged.items()},
    }


def build():
    seven = {s: s for s in ir.STATES}
    models = {"boolean": BOOLEAN, "ladder": LADDER, "seven": seven}
    measured = {name: measure(m) for name, m in models.items()}
    body = {
        "states": list(ir.STATES),
        "critical_pairs": [list(p) for p in CRITICAL_PAIRS],
        "measured": measured,
        "caveat": ("Mappings model the published shapes as read on 2026-11-24 "
                   "(AuthZEN decision true/false; KYA-OS Core L1-L3 with "
                   "fail-closed demotion). They are not the systems, and no "
                   "claim is made that either could not add states."),
    }
    receipt = hashlib.sha256(json.dumps(body, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    body["receipt_sha256"] = receipt
    return body


def render(body):
    lines = []
    lines.append("%-14s %-9s %-7s %-10s %s" %
                 ("state", "boolean", "ladder", "seven", "next action differs?"))
    lines.append("-" * 66)
    for s in body["states"]:
        lines.append("%-14s %-9s %-7s %-10s" %
                     (s, BOOLEAN[s], LADDER[s], s))
    lines.append("")
    lines.append("%-28s %-9s %-9s %s" % ("model", "distinct", "pairs kept", "critical"))
    lines.append("-" * 58)
    for name in ("boolean", "ladder", "seven"):
        m = body["measured"][name]
        lines.append("%-28s %-9d %-9s %d/%d" % (
            name, m["distinct_outputs"],
            "%d/%d" % (m["pairs_kept_apart"], m["pairs_total"]),
            len(m["critical_kept"]), len(body["critical_pairs"])))
    lines.append("")
    for name in ("boolean", "ladder"):
        lost = body["measured"][name]["critical_lost"]
        if lost:
            lines.append("%s merges: %s" % (name, "; ".join(
                "%s=%s" % tuple(p) for p in lost)))
    lines.append("")
    lines.append("receipt sha256: %s" % body["receipt_sha256"])
    return "\n".join(lines)


def main(argv):
    body = build()
    if "--json" in argv:
        print(json.dumps(body, indent=2, sort_keys=True))
    else:
        print(render(body))
        out = os.path.join(HERE, "docs", "VERDICT-VOCABULARY.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(body, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("written: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
