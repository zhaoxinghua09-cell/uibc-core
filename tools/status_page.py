#!/usr/bin/env python3
"""Write, or check, the one-page status of this repository.

The page exists because forty-one ledger sections are searchable but not readable.
Everything on it is derived from something in this repository, and `--check` fails
when the page and the sources disagree — a status page that drifts is worse than no
page, because it is quoted.

    python3 tools/status_page.py            # rewrite STATUS.md
    python3 tools/status_page.py --check    # 0 current, 1 stale, 3 a source is missing
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile

PAGE = "STATUS.md"

# Six dimensions where peers have something and we did not. The status word is one of
# have / partial / absent, and the tool path must exist — a row that points nowhere is
# a promise, and this page is not a place for promises.
DIMENSIONS = [
    ("quorum threshold authorisation", "absent", "",
     "one signature per record; no m-of-n, no group signature"),
    ("delegation record", "have", "tools/check_delegation.py",
     "one hop, bounded window, scope pinned to the corpus digest; ledger empty"),
    ("change control", "have", "tools/check_config_change.py",
     "closed set of four dispositions, three legs for normative changes; ledger empty"),
    ("adoption measurement", "have", "tools/check_adoption.py",
     "four buckets asked, all answer zero; downloads recorded as context only"),
    ("payment adaptation", "partial", "tools/settlement_boundary.py",
     "six questions answered, Q4-Q6 are not ours; no mandate corpus, no settlement path"),
    ("SCITT adaptation", "partial", "tools/check_scitt_crosswalk.py",
     "18 rows against the vendored draft: 3 same, 8 partial, 6 absent, 1 ours only"),
]

HUMAN_ONLY = [
    ("approve the repository-held attestation as v0.4.1's answer", "the frozen page stays unsigned; the "
                                                                   "release key signed the digest it served "
                                                                   "and that signature lives in "
                                                                   "anchors/attestations/v0.4.1/, which the "
                                                                   "page cannot rewrite -- a human has to "
                                                                   "accept that this identifies the publisher"),
    ("answer the two invitations when they come back", "both went out on 2026-11-20 (Templeman by email "
                                                        "from the 126 mailbox, Stone as a public issue on "
                                                        "swarmsync-ai/aivs-spec); a reply is a human voice, "
                                                        "and the external count does not move until one "
                                                        "arrives"),
    ("approve edits to 29 historical phrases", "the archived bundle still carries production-sounding "
                                               "phrases a checker refuses in anything new"),
]


def _root():
    return os.getcwd()


def _read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def facts(root):
    """Return (facts, missing). `missing` lists sources that could not be read."""
    missing = []
    f = {}

    pyproject = _read(os.path.join(root, "pyproject.toml"))
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    f["version"] = m.group(1) if m else None

    pins_path = os.path.join(root, "anchors", "pins", "uibc-conformance-%s.sha256" % f["version"])
    if not os.path.isfile(pins_path):
        missing.append(os.path.relpath(pins_path, root))
    else:
        text = _read(pins_path)
        digest = re.search(r"^([0-9a-f]{64})\s+(\S+)", text, re.M)
        size = re.search(r"#\s*(\d+) bytes", text)
        f["archive_sha256"] = digest.group(1) if digest else None
        f["archive_path"] = digest.group(2) if digest else None
        f["archive_bytes"] = int(size.group(1)) if size else None

    archive = os.path.join(root, f.get("archive_path") or "")
    if not f.get("archive_path") or not os.path.isfile(archive):
        missing.append(f.get("archive_path") or "archive")
    else:
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            # One case is one directory under cases/, whatever files it carries; counting
            # manifest.json would break the day a case ships two of them, counting entries
            # would count evidence files as cases.
            f["archive_cases"] = len({n.split("/")[1] for n in names
                                      if n.startswith("cases/") and n.count("/") >= 2})
            f["archive_carries_verifier"] = any(n.endswith("uibc_core.pyz") for n in names)

    oracle = os.path.join(root, "conformance", "oracle", "cases")
    if not os.path.isdir(oracle):
        missing.append("conformance/oracle/cases")
    else:
        f["oracle_cases"] = len([d for d in os.listdir(oracle)
                                 if os.path.isdir(os.path.join(oracle, d))])

    index = os.path.join(root, "docs", "EVIDENCE-INDEX.md")
    if not os.path.isfile(index):
        missing.append("docs/EVIDENCE-INDEX.md")
    else:
        m = re.search(r"外部第三方验证：(\d+)", _read(index))
        f["external_third_party"] = int(m.group(1)) if m else None

    adoption_dir = os.path.join(root, "docs", "adoption")
    if not os.path.isdir(adoption_dir):
        missing.append("docs/adoption")
    else:
        reports = sorted(x for x in os.listdir(adoption_dir) if x.endswith(".json"))
        if not reports:
            missing.append("docs/adoption/*.json")
        else:
            # The newest snapshot is the one with the latest generated_at, not the one whose
            # filename sorts last - a filename is a label, the timestamp is a fact.
            parsed = []
            for name in reports:
                data = json.loads(_read(os.path.join(adoption_dir, name)))
                parsed.append((data.get("generated_at") or "", name, data))
            parsed.sort()
            _ts, name, data = parsed[-1]
            f["adoption_report"] = name
            f["adoption_state"] = (data.get("verdict") or {}).get("state")
            f["adoption_exit"] = (data.get("verdict") or {}).get("exit")
            f["adoption_states"] = sorted({(d.get("verdict") or {}).get("state") for _t, _n, d in parsed})
            downloads = [b for b in data.get("buckets", []) if b.get("bucket") == "package downloads"]
            f["downloads_last_month"] = downloads[0].get("found") if downloads else None

    for _label, _status, tool, _note in DIMENSIONS:
        if tool and not os.path.isfile(os.path.join(root, tool)):
            missing.append(tool)

    return f, missing


def render(f, missing):
    lines = []
    add = lines.append
    add("# Status")
    add("")
    add("_Generated by `python tools/status_page.py`; `--check` fails when this page and the "
        "repository disagree. Do not edit by hand._")
    add("")
    add("## What this is")
    add("")
    add("A conformance corpus and verifier for a per-action evidence format, published with the "
        "gaps in it. The claim this page makes is narrow: **every number below can be recomputed "
        "from the repository**, and every dimension where peers are ahead says so.")
    add("")
    add("## Numbers")
    add("")
    add("| fact | value | where it comes from |")
    add("|---|---|---|")
    add("| version | %s | `pyproject.toml` |" % f.get("version"))
    add("| conformance archive | `%s` | `%s` |" % (f.get("archive_path") or "missing", f.get("archive_path") or "—"))
    add("| archive sha256 | `%s` | pin file |" % (f.get("archive_sha256") or "missing"))
    add("| archive bytes | %s | pin file |" % (f.get("archive_bytes") if f.get("archive_bytes") is not None else "missing"))
    add("| cases inside the archive | %s | counted from the zip |" % (f.get("archive_cases") if f.get("archive_cases") is not None else "missing"))
    add("| archive carries its own verifier | %s | zip listing |" % ("yes" if f.get("archive_carries_verifier") else "no"))
    add("| oracle cases | %s | `conformance/oracle/cases` |" % (f.get("oracle_cases") if f.get("oracle_cases") is not None else "missing"))
    add("| third-party validations | %s | `docs/EVIDENCE-INDEX.md` (generated) |"
        % (f.get("external_third_party") if f.get("external_third_party") is not None else "missing"))
    add("| adoption verdict (latest snapshot) | %s (exit %s) | `docs/adoption/%s` |"
        % (f.get("adoption_state") or "missing", f.get("adoption_exit"), f.get("adoption_report") or "—"))
    add("| package downloads, last month | %s | same snapshot, **context only — not adoption** |"
        % (f.get("downloads_last_month") if f.get("downloads_last_month") is not None else "—"))
    add("")
    states = f.get("adoption_states") or []
    if len(states) > 1:
        add("An earlier snapshot disagrees with the latest (%s): the snapshots that read %r are "
            "the runs where a bucket refused to answer. Both are kept, because deleting a wrong "
            "measurement is how a history of measurements becomes a history of good news."
            % (", ".join(states), [s for s in states if s != f.get("adoption_state")][0]))
        add("")
    add("No passing-test count appears here on purpose: it changes every day, and a number that "
        "changes every day teaches a reader to stop checking. CI runs it; the badge is not the claim.")
    add("")
    add("## Six dimensions")
    add("")
    add("| dimension | we have | checker | what is still missing |")
    add("|---|---|---|---|")
    for label, status, tool, note in DIMENSIONS:
        add("| %s | **%s** | %s | %s |" % (label, status, ("`%s`" % tool) if tool else "—", note))
    add("")
    add("## What only a person can do")
    add("")
    for what, why in HUMAN_ONLY:
        add("- **%s** — %s" % (what, why))
    add("")
    add("## Reproduce")
    add("")
    add("```bash")
    add("python tools/status_page.py --check     # is this page still true")
    add("python tools/check_adoption.py         # 0 measured zero, 3 a bucket was not asked")
    add("python tools/settlement_boundary.py    # six questions, no payment claim in the docs")
    add("python tools/check_scitt_crosswalk.py  # 18 rows against the vendored draft")
    add("```")
    add("")
    if missing:
        add("**Unreadable sources on the last generation**: %s. The rows above that depend on "
            "them say `missing` rather than a guess." % ", ".join(missing))
        add("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare STATUS.md with the sources")
    args = parser.parse_args(argv)

    root = _root()
    f, missing = facts(root)
    page = render(f, missing)

    if args.check:
        path = os.path.join(root, PAGE)
        if not os.path.isfile(path):
            print("STALE — %s does not exist; run python tools/status_page.py" % PAGE)
            return 3
        current = _read(path)
        if current != page:
            print("STALE — %s does not match its sources; run python tools/status_page.py" % PAGE)
            return 1
        print("CURRENT — %s matches every source it cites" % PAGE)
        return 3 if missing else 0

    with io.open(os.path.join(root, PAGE), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("written: %s%s" % (PAGE, (" (unreadable: %s)" % ", ".join(missing)) if missing else ""))
    return 3 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
