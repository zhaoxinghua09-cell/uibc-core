# -*- coding: utf-8 -*-
"""Render docs/GROUNDS.md: every must-reject case, and what it rests on.

The numbers in the prose are counted from the data, not typed in, so the page
cannot quietly disagree with `grounds.json`. `tests/test_grounds_page.py`
re-renders this and compares.
"""
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO, "conformance", "oracle")

KIND_TEXT = {
    "draft_mandated": "the draft states the requirement",
    "borrowed_idea": "the mechanism is borrowed, the check is ours",
    "own_choice": "nothing to point at: this project defines it",
}


def _load():
    with io.open(os.path.join(CORPUS, "grounds.json"), encoding="utf-8") as f:
        grounds = json.load(f)["cases"]
    with io.open(os.path.join(CORPUS, "expected.json"), encoding="utf-8") as f:
        expected = json.load(f)["cases"]
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from uibc_core.basis import BASIS
    return grounds, expected, BASIS


def _check_number(cid):
    digits = "".join(ch for ch in cid if ch.isdigit())
    return int(digits) if digits else 10 ** 6


def render(grounds=None, expected=None, basis=None):
    if grounds is None:
        grounds, expected, basis = _load()
    rows = sorted(grounds, key=lambda r: (_check_number(r["check"]), r["case"]))
    n_cases = len(expected)
    n_accept = sum(1 for c in expected if c["kind"] == "accept")
    n_reject = sum(1 for c in expected if c["expected_verdict"] == "FAIL")
    control = [c["case"] for c in expected
               if c["expected_verdict"] != "FAIL" and c["kind"] != "accept"]
    quoted = [r for r in rows if r.get("clause_quote")]
    by_kind = {}
    for r in rows:
        by_kind[r["basis"]] = by_kind.get(r["basis"], 0) + 1

    out = []
    out.append("# What each must-reject case rests on")
    out.append("")
    out.append("Generated from `conformance/oracle/grounds.json`, which is derived from the")
    out.append("basis table the verifier ships (`uibc_core/basis.py`). Do not edit this page;")
    out.append("edit the data. `tools/build_grounds_page.py > docs/GROUNDS.md`.")
    out.append("")
    out.append("The corpus is **%d cases**: %d must-reject, %d must-accept, %d control"
               % (n_cases, n_reject, n_accept, len(control)))
    out.append("(`%s`). Every one of the %d must-reject cases names what it rests on;"
               % (", ".join(control) or "none", n_reject))
    out.append("**%d of them quote the sentence** and `tools/check_grounds.py` re-finds that"
               % len(quoted))
    out.append("sentence in the vendored draft after collapsing whitespace. The rest say what")
    out.append("the requirement is and which document owns it, without claiming a sentence.")
    out.append("")
    out.append("Three kinds, and they are not interchangeable:")
    out.append("")
    out.append("| kind | what it means | cases |")
    out.append("|---|---|---|")
    for kind in ("draft_mandated", "borrowed_idea", "own_choice"):
        out.append("| `%s` | %s | %d |" % (kind, KIND_TEXT[kind], by_kind.get(kind, 0)))
    out.append("")
    out.append("## The table")
    out.append("")
    out.append("| case | check | kind | points at | the sentence, if there is one |")
    out.append("|---|---|---|---|---|")
    for r in rows:
        if r["basis"] == "own_choice":
            at = "this project"
            sentence = "—"
        else:
            if r.get("clause_source"):
                at = "`%s`" % r["clause_source"].split("/")[-1]
                if r.get("clause_section"):
                    at += " " + r["clause_section"].split(" (")[0]
            else:
                # grounds.json only stores a document for the checks whose
                # sentence is quoted; the rest carry their citation in the
                # shipped basis table, so read it there rather than printing "?".
                at = "`%s`" % ((basis or {}).get(r["check"], {}).get("citation") or "?")
            if r.get("clause_quote"):
                sentence = "> " + r["clause_quote"].replace("|", "\\|").replace("\n", " ")
            else:
                sentence = "no sentence quoted"
        out.append("| `%s` | %s | `%s` | %s | %s |"
                   % (r["case"], r["check"], r["basis"], at, sentence))
    out.append("")
    out.append("## How to check this page")
    out.append("")
    out.append("```")
    out.append("python tools/check_grounds.py      # every quoted sentence, re-found in the draft")
    out.append("python -m unittest tests.test_grounds tests.test_grounds_page")
    out.append("```")
    out.append("")
    out.append("`tests/test_grounds.py` also refuses a `clause_absent` row: a check that claims")
    out.append("a draft without a locatable clause has to be reclassified in `uibc_core/basis.py`,")
    out.append("not shipped as an absence.")
    out.append("")
    out.append("## What this page does not prove")
    out.append("")
    out.append("- Quoting a sentence shows the requirement exists in the document. It does not")
    out.append("  show that this project reads the sentence the way its author intended, nor")
    out.append("  that the check implements all of it.")
    out.append("- A basis is not a defence of the verdict: `own_choice` rows are decisions, and")
    out.append("  a decision can be wrong. What the page buys is that a reader can see which")
    out.append("  kind each case is before arguing with it.")
    out.append("- Nothing here speaks for a third party. The quotations are checked against")
    out.append("  our own copy of the drafts in `docs/spec-sources/`.")
    out.append("")
    return "\n".join(out)


def main():
    sys.stdout.write(render())


if __name__ == "__main__":
    main()
