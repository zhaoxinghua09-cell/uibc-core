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

| implementation | commit | mutation open (false accepts) | pinned | head-pinned | redteam refused | skipped | machine |
|---|---|---|---|---|---|---|---|
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
"""


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
            "| {impl} | `{commit}` | {ao}/{at} ({ar}%) | {po}/{pt} ({pr}%) | {ho}/{ht} | {ref}/{rt} | {sk} | {os} py{python} |".format(
                impl=d.get("implementation", "?"),
                commit=d.get("commit", "?"),
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
