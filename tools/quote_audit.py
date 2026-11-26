"""Quote audit: check whether an outside review actually read the material.

An external AI review is only worth something if its per-claim evidence can be
traced back to text that the reviewer was given. Two failure modes we hit while
building this repository's Phase 28 pack show why that has to be checked by a
machine, not by reading the answer:

  * F1 -- the reviewer is handed URLs only, and returns "checkable" because a
    link exists. Nobody verified anything.
  * F2 -- the reviewer is handed the assertion list *and* the material in the
    same prompt, and returns a quote that is verbatim text from the assertion
    list. Whole-prompt substring search reports 13/13 hits; restricted to the
    material section it collapses to 1/13. "All green" that is only a restated
    exam question.

So this tool splits the prompt into material and assertion regions, requires
the quote to land in the material region, and separately flags quotes that
merely echo an assertion.

Usage:

    python tools/quote_audit.py --receipt review.json --material docs/evidence/x/
    python tools/quote_audit.py --receipt review.json --material prompt.md \
        --material-from "MATERIAL" --assertions claims.md --check --write out.json

Verdicts per claim:

    BACKED     verdict is "checkable" and the quote is found in the material
    RESTATED   quote is found, but it is a substring of one of the assertions
    UNBACKED   verdict is "checkable" and the quote is found nowhere in the material
    ABSENT     verdict is "checkable" and no quote was given at all
    UNCLEAR    verdict is not "checkable" (nothing to audit, counted, not scored)

`--check` exits 1 if any claim is UNBACKED or ABSENT -- that is the level where
a review is claiming something it did not read. RESTATED exits 1 as well, since
the whole point of F2 is that it looks perfect. `--lenient` turns RESTATED into
a warning if the caller wants the two separated.

No network, no third-party imports, no state: give it the same two files and it
gives the same answer on any machine.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


CHECKABLE = {"checkable", "可核", "verified", "pass"}

_WS = re.compile(r"[\s\u3000\u00a0]+")
_QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
                         "\uff02": '"', "\uff07": "'", "`": "", '"': "", "'": ""})


def normalise(text: str) -> str:
    """Fold away everything that is typography rather than content."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_QUOTES)
    text = _WS.sub(" ", text)
    return text.strip()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_material(paths, marker: str | None, exclude=()):
    """Concatenate material, optionally from the last occurrence of `marker`.

    `exclude` keeps the receipt itself (and the audit output) out of the corpus.
    Without it, a receipt sitting inside the evidence directory matches its own
    quotes and every claim comes back BACKED -- the tool grading its own paper.
    """
    skip = {Path(p).resolve() for p in exclude if p}
    chunks = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in {".json", ".md", ".txt", ".py", ".html"}:
                    if f.resolve() in skip:
                        continue
                    chunks.append((str(f), f.read_text(encoding="utf-8", errors="replace")))
        else:
            if p.resolve() in skip:
                continue
            chunks.append((str(p), p.read_text(encoding="utf-8", errors="replace")))
    if marker:
        # keep only the region after the marker, per file
        sliced = []
        for name, text in chunks:
            idx = text.rfind(marker)
            sliced.append((name, text[idx + len(marker):] if idx >= 0 else ""))
        chunks = sliced
    return [(name, normalise(text)) for name, text in chunks]


def split_quote(quote: str):
    """Allow `file::verbatim text` -- the prefix names which file to look in."""
    if "::" in quote:
        head, tail = quote.split("::", 1)
        return head.strip(), tail.strip()
    return None, quote.strip()


def audit(receipt, material, assertions, min_quote=10, lenient=False):
    claims = receipt.get("claims") or receipt.get("claim_verdicts") or []
    norm_claims = [normalise(a) for a in assertions]

    rows = []
    for c in claims:
        cid = c.get("id", "?")
        verdict = str(c.get("verdict", "")).strip()
        quote = (c.get("quote") or "").strip()
        file_hint, body = split_quote(quote)
        state, where = None, None

        if normalise(verdict) not in CHECKABLE and verdict not in CHECKABLE:
            state = "UNCLEAR"
        elif not body:
            state = "ABSENT"
        elif len(normalise(body)) < min_quote:
            state = "UNBACKED"  # too short to be evidence of anything
        else:
            nb = normalise(body)
            for name, text in material:
                if file_hint and Path(name).name != file_hint and file_hint not in name:
                    continue
                if nb in text:
                    state, where = "BACKED", name
                    break
            if state is None:
                state = "UNBACKED"

        if state == "BACKED":
            nb = normalise(body)
            if any(nb and nb in a for a in norm_claims):
                state = "RESTATED"

        rows.append({"id": cid, "verdict": verdict, "state": state,
                     "quote": body[:160], "found_in": where})

    scored = [r for r in rows if r["state"] != "UNCLEAR"]
    backed = sum(1 for r in rows if r["state"] == "BACKED")
    restated = sum(1 for r in rows if r["state"] == "RESTATED")
    unbacked = sum(1 for r in rows if r["state"] == "UNBACKED")
    absent = sum(1 for r in rows if r["state"] == "ABSENT")
    checkable = sum(1 for r in rows if r["state"] != "UNCLEAR")

    bad = unbacked + absent + (0 if lenient else restated)
    return {
        "claims": len(rows),
        "checkable": checkable,
        "backed": backed,
        "restated": restated,
        "unbacked": unbacked,
        "absent": absent,
        "backed_rate": round(backed / checkable, 4) if checkable else 0.0,
        "lenient": lenient,
        "verdict": "QUOTE OK" if bad == 0 else f"QUOTE DEFECT({bad})",
        "rows": rows,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit quote traceability of an outside review.")
    ap.add_argument("--receipt", required=True, help="review receipt JSON")
    ap.add_argument("--material", nargs="+", required=True, help="files or directories given to the reviewer")
    ap.add_argument("--material-from", default=None,
                    help="only material after this marker counts (splits assertion region from material region)")
    ap.add_argument("--assertions", nargs="*", default=None,
                    help="assertion text files, used to detect quotes that merely restate a claim")
    ap.add_argument("--min-quote", type=int, default=10)
    ap.add_argument("--lenient", action="store_true", help="do not fail on RESTATED")
    ap.add_argument("--check", action="store_true", help="exit 1 on any defect")
    ap.add_argument("--write", default=None, help="write the audit JSON here")
    args = ap.parse_args(argv)

    receipt = load_json(Path(args.receipt))
    material = read_material(args.material, args.material_from,
                             exclude=(args.receipt, args.write))
    assertions = []
    for a in (args.assertions or []):
        assertions.append(Path(a).read_text(encoding="utf-8", errors="replace"))

    result = audit(receipt, material, assertions, args.min_quote, args.lenient)

    for r in result["rows"]:
        print(f"  {r['id']:<5} {r['state']:<9} {r['quote'][:60]}")
    print(f"claims={result['claims']} checkable={result['checkable']} "
          f"backed={result['backed']} restated={result['restated']} "
          f"unbacked={result['unbacked']} absent={result['absent']}")
    print(f"backed_rate={result['backed_rate']:.2%}  {result['verdict']}")

    if args.write:
        Path(args.write).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
        print(f"written: {args.write}")

    return 1 if (args.check and result["verdict"] != "QUOTE OK") else 0


if __name__ == "__main__":
    sys.exit(main())
