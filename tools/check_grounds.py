"""Verify that every recorded clause is actually present in the vendored draft.

A quote that nobody checks is a quotation mark with a claim attached. This reads
`conformance/oracle/grounds.json`, finds each clause in `docs/spec-sources/<file>`
after collapsing whitespace (the drafts are hard-wrapped, so a sentence never sits
on one line), and reports what is grounded and what is not.
"""
import io, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    corpus = os.path.join(REPO, "conformance", "oracle")
    grounds = json.load(io.open(os.path.join(corpus, "grounds.json"), encoding="utf-8"))
    rows = grounds["cases"]

    missing, verified, absent = [], [], []
    for row in rows:
        if not row.get("clause_quote"):
            if row["basis"] == "draft_mandated":
                absent.append((row["case"], row["check"]))
            continue
        path = os.path.join(REPO, row["clause_source"])
        if not os.path.isfile(path):
            missing.append((row["case"], row["check"], "source file not in repo"))
            continue
        body = squash(io.open(path, encoding="utf-8", errors="replace").read())
        # The drafts wrap lines mid-sentence, so the quote is matched on collapsed
        # whitespace and with the asterisk emphasis removed on both sides.
        body = body.replace("*", "")
        quote = squash(row["clause_quote"]).replace("*", "")
        if quote in body:
            verified.append((row["case"], row["check"], row["clause_source"]))
        else:
            missing.append((row["case"], row["check"], "clause not found verbatim"))

    print("reject cases in grounds: %d" % len(rows))
    print("clauses verified verbatim against the vendored draft: %d" % len(verified))
    print("draft-mandated checks with no clause recorded: %d (%s)"
          % (len(absent), ", ".join("%s/%s" % (c, s) for c, s in absent) or "-"))
    for case, check, why in missing:
        print("  NOT VERIFIED: %s (%s) - %s" % (case, check, why))
    by_basis = {}
    for row in rows:
        by_basis[row["basis"]] = by_basis.get(row["basis"], 0) + 1
    print("by basis: %s" % ", ".join("%s %d" % (k, v) for k, v in sorted(by_basis.items())))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
