#!/usr/bin/env python3
"""Render the local markdown draft into an Internet-Draft-shaped plain text file.

Why this exists rather than a pandoc call: the submission format is not
"markdown rendered nicely". It is a specific artefact - ASCII only, 72 columns,
58 lines per page, a page header and footer with the page number, and a fixed
set of front-matter sections (Status of This Memo, Copyright Notice) that must
be present before anything of ours appears. Getting one of those wrong is the
difference between a file the datatracker accepts and one a reviewer rejects.

The output stays labelled as not submitted: this renders the format, it does
not claim a standards status.

    python build_ietf_txt.py            # writes the .txt and runs the checks
    python build_ietf_txt.py --check    # only checks an existing .txt
"""

import argparse
import datetime
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "..", "drafts", "draft-zhao-uibc-evidence-chain-00.md")
OUT = os.path.join(HERE, "..", "drafts", "draft-zhao-uibc-evidence-chain-00.txt")

DOC = "draft-zhao-uibc-evidence-chain-00"
AUTHOR = "X. Zhao"
AFFIL = "Independent"
TITLE = "Agent Lifecycle Evidence Chain (UIBC)"
SUBTITLE = "Package Structure, Verification, and External Anchoring"
TODAY = datetime.date(2026, 11, 21)
EXPIRES = TODAY + datetime.timedelta(days=185)

WIDTH = 72
BODY_LINES = 58

# Non-ASCII is not permitted in a draft. Map the punctuation we actually use
# rather than letting a replace-with-? silently corrupt a sentence.
ASCII_MAP = {
    "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00a7": "S",
    "\u00b7": ".", "\u00d7": "x", "\u2192": "->", "\u2265": ">=",
    "\u2264": "<=", "\u00a0": " ",
}


def _ascii(s):
    for bad, good in ASCII_MAP.items():
        s = s.replace(bad, good)
    out = s.encode("ascii", "replace").decode("ascii")
    return out


def _fmt_date(d):
    return d.strftime("%d %B %Y").lstrip("0")


def _header(page):
    left = "Internet-Draft"
    right = _fmt_date(TODAY)
    middle = TITLE if len(TITLE) <= 41 else TITLE[:41]
    line = left.ljust(15) + middle.center(41) + right.rjust(16)
    return [line.rstrip(), ""]


def _footer(page):
    return [
        "",
        "%s   Expires %s   [Page %d]" % (AUTHOR, _fmt_date(EXPIRES), page),
    ]


def _wrap(text, first="   ", rest=None, width=WIDTH):
    rest = rest if rest is not None else " " * len(first)
    return textwrap.wrap(text, width=width, initial_indent=first,
                         subsequent_indent=rest, break_long_words=False,
                         break_on_hyphens=False)


def _render_table(block):
    rows = []
    for line in block:
        if re.match(r"^\s*\|[\s:|-]+\|\s*$", line):
            continue  # markdown separator row
        cells = [_strip_inline(c.strip()) for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return []
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    # Width follows how much text each column actually carries, not an equal
    # share: an equal-share split turns a two-column table with one long
    # column into a tall ribbon that is hard to read.
    want = [max(len(r[i]) for r in rows) for i in range(ncol)]
    # A column is not allowed below its longest word: breaking "index.json"
    # into "index.j" + "son" makes a table that has to be reassembled in the
    # reader's head.
    floor = []
    for i in range(ncol):
        longest_word = max((len(w) for r in rows for w in r[i].split()), default=0)
        floor.append(min(want[i], max(longest_word, 6)))
    budget = WIDTH - 2 - 3 * (ncol - 1)
    widths = list(want)
    total = sum(widths)
    if total > budget:
        # shrink the widest column that still has room above its floor, then
        # as a last resort the widest overall
        while sum(widths) > budget:
            reducible = [i for i in range(ncol) if widths[i] > floor[i]]
            if reducible:
                i = max(reducible, key=lambda k: widths[k])
            else:
                i = max(range(ncol), key=lambda k: widths[k])
            if widths[i] <= 6:
                break
            widths[i] -= 1
    else:
        widths[widths.index(max(widths))] += budget - total
    out = []
    for idx, row in enumerate(rows):
        wrapped = [textwrap.wrap(c, width=w, break_long_words=True,
                                 break_on_hyphens=False) or [""] for c, w in zip(row, widths)]
        height = max(len(w) for w in wrapped)
        for k in range(height):
            parts = [(w[k] if k < len(w) else "").ljust(widths[i])
                     for i, w in enumerate(wrapped)]
            out.append("  " + " | ".join(parts).rstrip())
        if idx == 0:
            out.append("  " + "-+-".join("-" * w for w in widths))
    return out


def _strip_inline(s):
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", s)
    return s


def _join_bullets(lines):
    """A bullet that wraps in the source continues at a deeper indent.

    Joining before rendering is the cheap way to keep a bullet one paragraph:
    otherwise the continuation lands in the paragraph path and a blank line
    appears in the middle of the item.
    """
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            joined = line
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    break
                if re.match(r"^[-*]\s+", nxt) or re.match(r"^\d+\.\s+", nxt):
                    break
                if not nxt.startswith("  "):
                    break
                if nxt.lstrip().startswith(("|", "#", "```", ">")):
                    break
                joined = joined.rstrip() + " " + nxt.strip()
                j += 1
            out.append(joined)
            i = j
            continue
        out.append(line)
        i += 1
    return out


def _flow(md_text):
    """Markdown -> a list of already-wrapped physical lines."""
    lines = _join_bullets([_ascii(l) for l in md_text.splitlines()])
    out = []
    in_code = False
    table = []
    para = []
    started = False

    def flush_para():
        nonlocal para
        if para:
            text = _strip_inline(" ".join(p.strip() for p in para).strip())
            out.append("")
            out.extend(_wrap(text))
            para = []

    def flush_table():
        nonlocal table
        if table:
            out.append("")
            out.extend(_render_table(table))
            table = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            flush_para()
            flush_table()
            in_code = not in_code
            out.append("")
            continue
        if in_code:
            # One formula in the source is 83 columns; break it at the margin
            # rather than shipping a line idnits will flag.
            while len(line) > WIDTH:
                out.append("   " + line[:WIDTH - 3])
                line = line[WIDTH - 3:]
            out.append("   " + line)
            continue
        if re.match(r"^\s*\|", line):
            flush_para()
            table.append(line)
            continue
        flush_table()
        if not line.strip():
            flush_para()
            continue
        if re.match(r"^#\s", line):
            continue  # the title block is front matter, not body
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            flush_para()
            head = _strip_inline(m.group(1))
            if not started:
                started = True
                continue  # subtitle handled in front matter
            out.append("")
            out.append(head)
            out.append("")
            continue
        m = re.match(r"^###\s+(.*)$", line)
        if m:
            flush_para()
            out.append("")
            out.append(_strip_inline(m.group(1)))
            out.append("")
            continue
        if re.match(r"^(-|\*|\d+\.)\s+", line):
            flush_para()
            m = re.match(r"^(-|\*|\d+\.)\s+(.*)$", line)
            out.extend(_wrap(_strip_inline(m.group(2)), first="o  ",
                             rest="   "))
            continue
        if line.startswith("---"):
            flush_para()
            continue
        if line.startswith("> "):
            flush_para()
            out.extend(_wrap(_strip_inline(line[2:]), first="   ", rest="   "))
            continue
        para.append(line)
    flush_para()
    flush_table()
    return out


FRONT_PARAS = (
    ("Abstract", None),
    ("Note to Readers",
     "This document is a local draft. It is written in Internet-Draft shape so "
     "that it can be reviewed and, if a decision is ever made to do so, "
     "submitted unchanged. It has not been posted to the IETF datatracker and "
     "it claims no standards status."),
    ("Status of This Memo",
     "This Internet-Draft is submitted in full conformance with the provisions "
     "of BCP 78 and BCP 79."),
    (None,
     "Internet-Drafts are working documents of the Internet Engineering Task "
     "Force (IETF). Note that other groups may also distribute working "
     "documents as Internet-Drafts. The list of current Internet-Drafts is at "
     "https://datatracker.ietf.org/drafts/current/."),
    (None,
     "Internet-Drafts are draft documents valid for a maximum of six months "
     "and may be updated, replaced, or obsoleted by other documents at any "
     "time. It is inappropriate to use Internet-Drafts as reference material "
     "or to cite them other than as \"work in progress.\""),
    (None, "This Internet-Draft will expire on {expires}."),
    ("Copyright Notice",
     "Copyright (c) 2026 IETF Trust and the persons identified as the "
     "document authors. All rights reserved."),
    (None,
     "This document is subject to BCP 78 and the IETF Trust's Legal Provisions "
     "Relating to IETF Documents (https://trustee.ietf.org/license-info) in "
     "effect on the date of publication of this document. Please review these "
     "documents carefully, as they describe your rights and restrictions with "
     "respect to this document."),
)

TAIL = """
Authors' Addresses

   X. Zhao
   Independent
   URI:   https://github.com/zhaoxinghua09-cell/uibc-core
"""


def _front_lines(abstract):
    out = [TITLE.center(WIDTH).rstrip(), SUBTITLE.center(WIDTH).rstrip(), ""]
    for heading, para in FRONT_PARAS:
        if heading:
            out.append(heading)
            out.append("")
        if para is None:
            body = abstract
        else:
            body = para.format(expires=_fmt_date(EXPIRES))
        out.extend(_wrap(body))
        out.append("")
    return out


def build():
    with open(MD, "r", encoding="utf-8") as f:
        md = f.read()
    # The md's Abstract section supplies the abstract paragraph.
    m = re.search(r"^## Abstract\s*\n(.*?)^## ", md, re.S | re.M)
    abstract = " ".join(_strip_inline(x).strip()
                        for x in (m.group(1).splitlines() if m else [])).strip()
    abstract = re.sub(r"\s+", " ", _ascii(abstract))
    body = _front_lines(abstract) + _flow(md) + TAIL.splitlines()
    body = [l.rstrip() for l in body]
    # collapse runs of blank lines to one
    squeezed = []
    for line in body:
        if not line.strip() and squeezed and not squeezed[-1].strip():
            continue
        squeezed.append(line)
    body = squeezed

    pages = []
    page = []
    for line in body:
        page.append(line)
        if len(page) >= BODY_LINES:
            pages.append(page)
            page = []
    if page:
        pages.append(page)

    rendered = []
    for i, p in enumerate(pages, 1):
        rendered.append("\f" if i > 1 else "")
        rendered.append(_header(i)[0])
        rendered.extend(p)
        rendered.extend(_footer(i))
        rendered.append("")
    text = "\n".join(rendered).lstrip("\n")
    text = text.replace("\n\n", "\n\n")
    return text


REQUIRED = ("Abstract", "Status of This Memo", "Copyright Notice",
            "Security Considerations", "IANA Considerations",
            "Authors' Addresses")


def check(path, quiet=False):
    problems = []
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if not text.isascii():
        problems.append("non-ASCII bytes present")
    if "\t" in text:
        problems.append("tab characters present")
    pages = text.split("\f")
    for n, page in enumerate(pages, 1):
        for ln, line in enumerate(page.splitlines(), 1):
            if len(line) > WIDTH:
                problems.append("page %d line %d is %d columns"
                                % (n, ln, len(line)))
            if line and line != line.rstrip():
                problems.append("page %d line %d has trailing space" % (n, ln))
        if "[Page %d]" % n not in page:
            problems.append("page %d has no page-number footer" % n)
    for heading in REQUIRED:
        if heading not in text:
            problems.append("missing required section: %s" % heading)
    if DOC not in text:
        problems.append("document name never appears in the page headers")
    if not quiet:
        print("pages    : %d" % len(pages))
        print("columns  : max %d" % max(len(l) for l in text.splitlines()))
        print("ascii    : %s" % ("yes" if text.isascii() else "no"))
        print("bytes    : %d" % len(text.encode("ascii", "replace")))
        if problems:
            print("problems : %d" % len(problems))
            for p in problems[:20]:
                print("  - %s" % p)
        else:
            print("problems : 0")
    return 0 if not problems else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check(OUT)
    text = build()
    with open(OUT, "w", encoding="ascii", newline="\n") as f:
        f.write(text)
    print("wrote %s" % OUT)
    return check(OUT)


if __name__ == "__main__":
    sys.exit(main())

