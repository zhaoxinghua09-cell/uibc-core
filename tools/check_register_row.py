#!/usr/bin/env python3
"""Check a row in REPRODUCTION-REGISTER.md against the register's own rules.

REPRODUCTION-REGISTER.md states five rules. Rule 4 is the load-bearing one:

    A row must be reproducible from what it states — commit, tool version, command,
    and the receipt hash. A row that cannot be re-run is gossip.

Nothing enforced that. A row could claim `ALL COMPARISONS MATCH` with a hash that
is 40 characters, or a commit that does not exist, or an affiliation field left
blank, and the file would look equally authoritative.

This tool makes rule 4 checkable, and rule 5 (affiliation declared) too.

Two modes:

  --register PATH
      Validate every row in the table. Used as a CI step so the register cannot
      drift into unverifiable rows.

  --receipt PATH.json --claim-commit <sha> --claim-sha256 <hex>
      Cross-check a submitted receipt file against what the row claims: the file's
      real sha256 must equal the claimed hash, and the receipt's own subject commit
      must equal the claimed commit. This is the part a maintainer otherwise has to
      do by eye, which is exactly how a false row gets in.

Design notes worth keeping:

  * A disagreement is NOT a failure. Rule 1 says disagreements are kept and marked.
    The checker accepts a row that lists mismatches; it rejects a row that lists
    nothing and claims a match it cannot support.
  * A "pre-tool" row (run before reproduce_gate.py existed) is accepted, because
    deleting it would break rule 1's spirit, but it must say so.
  * Nothing here decides whether a runner is independent. Rule 5 only requires the
    affiliation be *declared*; judging it is a human act and this tool does not
    pretend to do it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys

REQUIRED_COLUMNS = [
    "date",
    "who",
    "affiliation",
    "subject (commit)",
    "result",
    "receipt sha256",
    "notes",
]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# Hex, not \d: a commit prefix such as "a1b2c3d" is mostly letters. The first
# version of this pattern used \d and rejected every real commit — the self-test
# cases caught it, which is the only reason it is written this way now.
SHA_ANY_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

# Phrases that mean "I ran it and the numbers matched". Anything else in the
# result column is treated as a disagreement list, which is allowed.
MATCH_PHRASES = {"ALL COMPARISONS MATCH", "all comparisons match", "all agree"}

# Words that mean the row explicitly declares it predates the tool.
PRE_TOOL_MARKERS = ("pre-tool", "predates", "before the tool", "not this script")


class RowError(Exception):
    pass


def split_md_row(line: str) -> list[str]:
    """Split a markdown table row on unescaped pipes, dropping the outer empties."""
    cells, cur, i = [], "", 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "|":
            cells.append(cur)
            cur = ""
            i += 1
            continue
        cur += ch
        i += 1
    cells.append(cur)
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def parse_register(text: str) -> tuple[list[str], list[tuple[int, list[str]]]]:
    """Return (header cells, [(line_number, cells)]) for the register table.

    Picks the table whose header matches REQUIRED_COLUMNS, not simply the first
    table in the file: REPRODUCTION-REGISTER.md contains a "field | meaning"
    explanation table before the register itself, and taking the first table
    validated the wrong thing.
    """
    header = None
    rows: list[tuple[int, list[str]]] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            if header is not None and rows:
                break
            continue
        cells = split_md_row(line)
        if header is None:
            header = cells if cells == REQUIRED_COLUMNS else None
            if header is None:
                continue
        if cells == REQUIRED_COLUMNS:
            continue  # the header row itself, not a data row
        if set("".join(cells)) <= {"-", ":", " "} and cells:
            continue  # separator row
        rows.append((n, cells))
    return (header or []), rows


def check_row_shape(cells: list[str], header: list[str], where: str) -> list[str]:
    """Return a list of problems with one row. Empty means the row is well-formed."""
    problems: list[str] = []
    if len(cells) != len(header):
        return [f"{where}: {len(cells)} cells but the header has {len(header)}"]

    def get(name: str) -> str:
        return cells[header.index(name)]

    if not DATE_RE.match(get("date")):
        problems.append(f"{where}: date is {get('date')!r}, expected YYYY-MM-DD")

    if not get("who"):
        problems.append(f"{where}: 'who' is empty — a row without a name is gossip")

    if not get("affiliation"):
        problems.append(
            f"{where}: 'affiliation' is empty — rule 5 wants it declared; "
            "write 'none' rather than leaving it blank"
        )

    subject = get("subject (commit)")
    if not subject:
        problems.append(f"{where}: 'subject (commit)' is empty")
    elif not (SHA_ANY_RE.match(subject) or "v0." in subject or "fixture" in subject):
        problems.append(
            f"{where}: 'subject (commit)' is {subject!r}; expected a commit prefix "
            "or something that names a version explicitly"
        )

    result = get("result")
    notes = get("notes")
    sha = get("receipt sha256")
    pre_tool = any(m in notes.lower() for m in PRE_TOOL_MARKERS)

    is_match = result.strip() in MATCH_PHRASES
    has_disagreement = bool(re.search(r"[0-9]", result)) and not is_match

    if not is_match and not has_disagreement:
        problems.append(
            f"{where}: 'result' is {result!r}; expected 'ALL COMPARISONS MATCH' "
            "or an explicit list of disagreements"
        )

    if pre_tool:
        if sha and SHA256_RE.match(sha):
            problems.append(
                f"{where}: a pre-tool row carries a tool receipt hash; "
                "either it is not pre-tool, or the hash did not come from the tool"
            )
    else:
        if not SHA256_RE.match(sha):
            problems.append(
                f"{where}: 'receipt sha256' is {sha!r}; a row that cannot be "
                "matched to a receipt file is gossip (rule 4)"
            )

    if is_match and not pre_tool and "command" not in notes.lower() and not any(
        w in notes.lower() for w in ("one command", "reproduce_gate", "ran:", "cmd")
    ):
        problems.append(
            f"{where}: claims a match but the notes never name the command that produced it"
        )

    return problems


def check_receipt(receipt_path: str, claim_commit: str, claim_sha256: str) -> list[str]:
    """Cross-check a receipt file against a row's claims."""
    problems: list[str] = []
    try:
        raw = open(receipt_path, "rb").read()
    except OSError as exc:
        return [f"cannot read receipt: {exc}"]

    actual = hashlib.sha256(raw).hexdigest()
    if not SHA256_RE.match(claim_sha256 or ""):
        problems.append(f"claimed sha256 is not 64 lowercase hex: {claim_sha256!r}")
    elif actual != claim_sha256:
        problems.append(
            f"receipt hash mismatch: file hashes to {actual}, row claims {claim_sha256}"
        )

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return problems + [f"receipt is not valid JSON: {exc}"]

    subject = data.get("subject")
    if isinstance(subject, dict):
        subject_commit = subject.get("git_head") or subject.get("commit") or ""
    else:
        # In receipts written by reproduce_gate.py, `subject` is a bare commit
        # string. The first version of this checker assumed an object and
        # crashed on its own receipt — parsing what you wish the file said,
        # rather than what it says, is the same failure this whole file exists
        # to catch.
        subject_commit = str(subject or "")
    if claim_commit and subject_commit and not subject_commit.startswith(claim_commit[:7]):
        problems.append(
            f"commit mismatch: receipt ran against {subject_commit[:12]}, "
            f"row claims {claim_commit}"
        )

    mism = data.get("mismatches")
    if mism is None:
        problems.append("receipt has no 'mismatches' field; cannot tell what was compared")
    return problems


# ---------------------------------------------------------------- self-test

GOOD_ROWS = [
    # A modern row: full hash, names the command, commit prefix, affiliation declared.
    "| 2026-11-21 | A. Runner | none | a1b2c3d | ALL COMPARISONS MATCH | "
    + "9f" * 32
    + " | ran: python tools/reproduce_gate.py --repo . --uibc uibc --profile docs/assurance/far-profile.json |",
    # A disagreement row is allowed and must not be rejected.
    "| 2026-11-22 | B. Skeptic | employed by a competitor | deadbee | 3 of 24 comparisons differ: fixture open/pinned rollback | "
    + "ab" * 32
    + " | fixture row differs under strict reading; see attached receipt |",
]

BAD_ROWS = [
    # Missing full hash: the classic "looks fine, cannot be checked" row.
    (
        "row with a short hash",
        "| 2026-11-21 | C. Stranger | none | a1b2c3d | ALL COMPARISONS MATCH | abc123 | one command |",
    ),
    (
        "blank affiliation",
        "| 2026-11-21 | D. Someone |  | a1b2c3d | ALL COMPARISONS MATCH | "
        + "cd" * 32
        + " | ran: reproduce_gate |",
    ),
    (
        "vague result",
        "| 2026-11-21 | E. Someone | none | a1b2c3d | mostly fine | "
        + "ef" * 32
        + " | ran: reproduce_gate |",
    ),
    (
        "bad date",
        "| 21/11/2026 | F. Someone | none | a1b2c3d | ALL COMPARISONS MATCH | "
        + "12" * 32
        + " | ran: reproduce_gate |",
    ),
    (
        "match with no command named",
        "| 2026-11-21 | G. Someone | none | a1b2c3d | ALL COMPARISONS MATCH | "
        + "34" * 32
        + " | looks good |",
    ),
]


def self_test() -> int:
    header = REQUIRED_COLUMNS
    failures = 0
    for i, row in enumerate(GOOD_ROWS, start=1):
        problems = check_row_shape(split_md_row(row), header, f"good#{i}")
        if problems:
            failures += 1
            print(f"FAIL good#{i}: should have passed, got {problems}")
        else:
            print(f"ok   good#{i}")
    for label, row in BAD_ROWS:
        problems = check_row_shape(split_md_row(row), header, label)
        if not problems:
            failures += 1
            print(f"FAIL {label}: should have been rejected, passed instead")
        else:
            print(f"ok   rejected {label}: {problems[0]}")

    # The register's real first row must still pass: rules must not retroactively
    # invalidate history that was honestly written.
    real = (
        "| 2026-11-12 | Takao Sato (Poke-nushi) | none declared | v0.3.0 fixture set, 18 S4/S5/S6 comparisons "
        "| all agree | n/a (pre-tool run, 2026-11-12) | Ran a reading, not this script: 22 conditions, "
        "66 comparisons, reseal with and without expected key. |"
    )
    problems = check_row_shape(split_md_row(real), header, "real-row-1")
    if problems:
        failures += 1
        print(f"FAIL real row rejected: {problems}")
    else:
        print("ok   real row still accepted")

    print("\nSELF-TEST", "PASS" if failures == 0 else f"FAIL ({failures})")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--register", help="validate every row in this register file")
    ap.add_argument("--receipt", help="receipt JSON to cross-check")
    ap.add_argument("--claim-commit", default="")
    ap.add_argument("--claim-sha256", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if args.register:
        text = open(args.register, encoding="utf-8").read()
        header, rows = parse_register(text)
        if not header:
            print("no table found")
            return 2
        if header != REQUIRED_COLUMNS:
            print(f"header is {header}")
            print(f"expected  {REQUIRED_COLUMNS}")
            return 2
        all_problems: list[str] = []
        for line_no, cells in rows:
            all_problems += check_row_shape(cells, header, f"line {line_no}")
        for p in all_problems:
            print(f"PROBLEM {p}")
        print(f"\n{len(rows)} rows, {len(all_problems)} problems")
        return 0 if not all_problems else 1

    if args.receipt:
        problems = check_receipt(args.receipt, args.claim_commit, args.claim_sha256)
        for p in problems:
            print(f"PROBLEM {p}")
        print("\nRECEIPT", "ACCEPTABLE" if not problems else "NOT ACCEPTABLE")
        return 0 if not problems else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
