#!/usr/bin/env python3
"""Regenerate leaderboard.md from benchmarks/submissions/*.json.

Numbers are read from the files, never typed. Each row carries its own
not_claimed line so a reader sees what the score does not support.
"""
from __future__ import annotations

import glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SUBS = os.path.join(HERE, "submissions")
OUT = os.path.join(HERE, "leaderboard.md")

HEADER = """# Leaderboard

Generated from `benchmarks/submissions/*.json` by `benchmarks/build_leaderboard.py`.
Re-run `python benchmarks/run_benchmarks.py` to reproduce a row; the record carries the
measured commit and machine so a reader can tell whether two rows are even comparable.

**Suite runs**

`disclosure` is the only column that is not a measurement: it says whether the submitter
publishes a CDP-1 coverage ledger (`coverage/`). A row marked `UNDISCLOSED` is still shown,
with its numbers, but it is **not ranked** — a rate without a statement of what was not
tested cannot be compared to one that has it.

| implementation | commit | mutation open (false accepts) | pinned | head-pinned | redteam refused | skipped | disclosure | machine |
|---|---|---|---|---|---|---|---|---|
"""

EXTERNAL_HEADER = """
**External verifiers measured by `benchmarks/run_external.py`** (same mutant bytes, submitted
command, exit 0 = accept)

| implementation | commit | false accepts | base accepted | verifier command |
|---|---|---|---|---|
"""

FOOTER = """
`false accepts` counts mutations the verifier accepted, i.e. it believed a mutated package was
intact. `refused` counts hostile inputs rejected as expected. `skipped` counts cases that could
not be constructed on that machine — a gap, not a pass.

A row is a measurement of a named commit on a named machine, not a claim of superiority:
implementations that ship different suites are not comparable, which is why the totals above
are shown beside every rate.

Rows whose `disclosure` column starts with `UNDISCLOSED` are listed for measurement only and
are **not ranked**: a false-accept rate says what a verifier accepted, not what it never tested.
CDP-1 (see `coverage/README.md`) is the file that states the second half, and a submitter who
does not publish it has not made a comparable claim.
"""


def disclosure(impl: str) -> str:
    """CDP-1 status for a submitter.

    Read, not assumed: a ledger must exist, parse, and be well-formed under the
    three rules (every entry has a status; EXERCISED has a test; gaps are named).
    Anything else is UNDISCLOSED, and the row is then listed but not ranked.
    """
    cand = [
        os.path.join(HERE, "..", "coverage", f"ledger.{impl}.json"),
        os.path.join(HERE, "..", "coverage", "ledger.uibc-core.json"),
    ]
    if impl != "uibc-core":
        cand = [c for c in cand if impl in os.path.basename(c)]
    for path in cand:
        if not os.path.exists(path):
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            return "UNDISCLOSED (ledger unreadable)"
        if d.get("schema") != "cdp-1":
            return "UNDISCLOSED (not cdp-1)"
        bad = [e for e in d.get("entries", []) if e.get("status") not in
               ("EXERCISED", "UNTESTED", "EXEMPT", "NOT_PUBLIC")]
        if bad:
            return "UNDISCLOSED (entry without status)"
        s = d.get("summary", {})
        return f"cdp-1 {s.get('exercised', '?')}/{s.get('total', '?')}"
    return "UNDISCLOSED (no ledger)"


def main() -> int:
    rows, ext = [], []
    for path in sorted(glob.glob(os.path.join(SUBS, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("kind") == "external-verifier":
            m = d["mutations"]
            ext.append(
                "| {impl} | `{commit}` | {a}/{t} ({r}%) | {base} | `{cmd}` |".format(
                    impl=d.get("implementation", "?"), commit=d.get("commit", "?"),
                    a=m.get("accepted"), t=m.get("total"), r=m.get("false_accept_rate"),
                    base=d.get("base_accepted"), cmd=d.get("verifier_command", "?"),
                )
            )
            continue
        m = d["suites"]["mutation"]
        r = d["suites"]["redteam"]
        mo = m["modes"]["open"]
        rows.append(
            "| {impl} | `{commit}` | {ao}/{at} ({ar}%) | {po}/{pt} ({pr}%) | {ho}/{ht} | {ref}/{rt} | {sk} | {disc} | {os} py{python} |".format(
                impl=d.get("implementation", "?"),
                commit=d.get("commit", "?"),
                disc=disclosure(d.get("implementation", "?")),
                ao=mo.get("accepted"), at=mo.get("total"), ar=mo.get("false_accept_rate"),
                po=m["modes"]["pinned"].get("accepted"), pt=m["modes"]["pinned"].get("total"),
                pr=m["modes"]["pinned"].get("false_accept_rate"),
                ho=m["modes"]["head-pinned"].get("accepted"), ht=m["modes"]["head-pinned"].get("total"),
                ref=r.get("refused_as_expected"), rt=r.get("total"), sk=r.get("skipped"),
                os=d.get("machine", {}).get("system", "?"), python=d.get("machine", {}).get("python", "?"),
            )
        )
    text = HEADER + "\n".join(rows) + "\n" + FOOTER
    if ext:
        text = HEADER + "\n".join(rows) + "\n" + EXTERNAL_HEADER + "\n".join(ext) + "\n" + FOOTER
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote", OUT, "suite rows:", len(rows), "external rows:", len(ext))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
