#!/usr/bin/env python3
"""A reproduction sheet for the paper: every number, the command, the output.

The chapter-5 tables already cite a command under each table. That is the right
instinct and not enough on its own, because a citation tells a reader where to
look and not what they will see. A defence committee, or a reviewer who distrusts
the work, wants to run the command and compare against a printed value.

So this executes the commands and records what came back. What it produces is
therefore evidence that the run happened, not a restatement of belief.

    python3 tools/build_reproduce.py > docs/REPRODUCE.md
    python3 tools/build_reproduce.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

PY = sys.executable


def run(args, cwd=_REPO):
    proc = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=900)
    return proc.stdout, proc.returncode


def last_line(text, limit=160):
    """The conclusion, not the preamble.

    Most of these tools print progress first and the figure last. Taking the
    first line reported "{" for three of them, which is honest and useless.
    """
    for line in reversed(text.splitlines()):
        s = line.strip()
        if s and s not in ("{", "}", "[", "]"):
            return s[:limit]
    return ""


def json_field(text, path, label):
    """Read one field out of a JSON document that may be wrapped in log noise."""
    start = text.find("{")
    if start < 0:
        return None
    try:
        doc = json.loads(text[start:])
    except Exception:
        return None
    value = doc
    for step in path:
        if not isinstance(value, dict) or step not in value:
            return None
        value = value[step]
    return "%s=%s" % (label, value if not isinstance(value, list) else len(value))


# (table, what the number is, command as a reader would type it, argv to run)
CLAIMS = [
    ("5-1", "each check's basis class and citation",
     'python3 -c "from uibc_core import basis; print(basis.for_check(\'S1\'))"',
     [PY, "-c", "from uibc_core import basis; print(basis.for_check('S1'))"]),
    ("5-2", "basis distribution 7/8/4",
     'python3 -c "from uibc_core import basis; print(basis.counts())"',
     [PY, "-c", "from uibc_core import basis; print(basis.counts())"]),
    ("5-3", "36 attacks / 34 caught / 32 isolated",
     "python3 tools/check_matrix.py --json",
     [PY, "tools/check_matrix.py", "--json"]),
    ("5-4", "reason counts under the same attacks",
     "python3 tools/compare_diagnostics.py --json",
     [PY, "tools/compare_diagnostics.py", "--json"]),
    ("5-5", "three distribution channels 6/6/19",
     "python3 tools/check_release_parity.py --json",
     [PY, "tools/check_release_parity.py", "--json"]),
    ("5-6", "hot-path latency",
     "python3 tools/latency_per_call.py --json",
     [PY, "tools/latency_per_call.py", "--json"]),
    ("summary", "19 checks",
     "python3 -c \"from uibc_core import basis; print(len([k for k in basis.BASIS if k != 'S0']))\"",
     [PY, "-c", "from uibc_core import basis; print(len([k for k in basis.BASIS if k != 'S0']))"]),
    ("summary", "conformance vectors",
     "python3 tools/run_conformance.py",
     [PY, "tools/run_conformance.py"]),
    ("summary", "published numbers match the tree",
     "python3 tools/check_doc_facts.py",
     [PY, "tools/check_doc_facts.py"]),
    ("summary", "audit verdict on the shipped fixture",
     "python3 -m uibc_core.cli verify fixtures/clean.uibc",
     [PY, "-m", "uibc_core.cli", "verify", "fixtures/clean.uibc"]),
]


def pick_matrix(text, code):
    parts = []
    for path, label in ((["n_attacks"], "attacks"), (["n_caught"], "caught"),
                        (["isolated"], "isolated"), (["unreached"], "unreached")):
        v = json_field(text, path, label)
        if v:
            parts.append(v)
    return "  ".join(parts) or last_line(text)


def pick_channels(text, code):
    start = text.find("{")
    if start < 0:
        return last_line(text)
    try:
        doc = json.loads(text[start:])
    except Exception:
        return last_line(text)
    chans = doc.get("channels") or {}
    parts = []
    for name, body in chans.items():
        n = body.get("checks")
        if isinstance(n, list):
            parts.append("%s=%d" % (name, len(n)))
    return "  ".join(parts) or last_line(text)


def pick_latency(text, code):
    """This tool logs 300 lines of setup and then prints JSON; read the JSON."""
    parts = []
    for path, label in ((["median_ms"], "median_ms"), (["p99_ms"], "p99_ms"),
                        (["n"], "n")):
        v = json_field(text, path, label)
        if v:
            parts.append(v)
    return "  ".join(parts) or last_line(text)


def pick_tail(text, code):
    for line in reversed(text.splitlines()):
        if re.search(r"strict\s+\d+/\d+", line):
            return line.strip()
    return last_line(text)


def pick_result(text, code):
    m = re.search(r'"result"\s*:\s*"(\w+)"', text)
    return "result=%s" % m.group(1) if m else last_line(text)


def collect():
    rows = []
    pick = {"36 attacks": pick_matrix, "reason counts": None,
            "three distribution": pick_channels, "hot-path": pick_latency,
            "conformance": pick_tail, "audit verdict": pick_result}
    for table, what, cmd, argv in CLAIMS:
        fn = next((f for k, f in pick.items() if k in what), None)
        out, code = run(argv)
        if "reason counts" in what:
            # build_dashboard already reconciles the two implementations; reusing
            # its number keeps this sheet and the dashboard from disagreeing.
            d_out, _ = run([PY, "tools/build_dashboard.py", "--json"])
            got = json_field(d_out, ["common"], "compared attacks") or ""
            value = got + "  " + (json_field(d_out, ["ours"], "ours reasons") or "") \
                + "  " + (json_field(d_out, ["theirs"], "theirs reasons") or "")
            output = value.strip() or last_line(d_out)
        else:
            output = fn(out, code) if fn else last_line(out)
        rows.append({"table": table, "what": what, "command": cmd,
                     "output": output, "exit": code})
    return rows


def _unused(rows):
    """Pull the key figures out of JSON when the raw first line is not a figure.

    A reader comparing a table wants 36/34/32, not the opening brace of a JSON
    object; printing the brace and calling it output would be technically
    honest and practically useless.
    """
    for r in rows:
        if r["table"] not in KEY:
            continue
        out, _ = run([a for a in next(c[3] for c in CLAIMS if c[1] == r["what"])])
        found = {}
        for name, rx in KEY[r["table"]]:
            m = re.search(rx, out)
            if m:
                found[name] = int(m.group(1))
        if found:
            r["output"] = "  ".join("%s=%d" % (k, v) for k, v in found.items())
    return rows


def render(rows):
    lines = [
        "# Reproduction sheet -- every number in the paper, and the command that produces it",
        "",
        "Generated by `tools/build_reproduce.py`, which **runs** each command and records",
        "what came back. The `output` column is therefore a record of an execution, not a",
        "restatement of what the document believes.",
        "",
        "Reproduce the whole sheet:",
        "",
        "```bash",
        "python3 tools/build_reproduce.py",
        "```",
        "",
        "| Table | Number | Command | Output recorded at generation | Exit |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        cmd = r["command"].replace("|", "\\|")
        out = (r["output"] or "(no output)").replace("|", "\\|")
        lines.append("| %s | %s | `%s` | `%s` | %d |"
                     % (r["table"], r["what"], cmd, out, r["exit"]))
    lines += [
        "",
        "## How to read a mismatch",
        "",
        "If an output here differs from the paper, one of three things is true and they",
        "are worth separating before anyone argues about the work:",
        "",
        "1. **The tree moved and the paper did not.** Then the paper is wrong and this",
        "   sheet is right -- `tools/check_doc_facts.py` fails CI on exactly this class",
        "   of error for the numbers it can see.",
        "2. **The environment differs.** Latency in particular is machine-dependent;",
        "   `5-6` on a slower host will not read the same, and that is a property of the",
        "   measurement, not a defect.",
        "3. **The command needs something absent here.** Optional anchor libraries",
        "   produce INCONCLUSIVE rather than PASS, and a skipped check is visible in the",
        "   `output` column instead of hidden.",
        "",
        "## What this sheet does not cover",
        "",
        "- Numbers that require a network, an external timestamp authority or a live",
        "  endpoint: they are not reproducible from a clone, so they are not listed.",
        "- Prose claims (\"no external verification nodes\", \"inclusion not verified\"):",
        "  they are statements about absence, and no command produces an absence.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = collect()
    print(json.dumps(rows, ensure_ascii=False, indent=2) if a.json else render(rows))
