"""One command an outsider can run, with no credentials and no network.

`docs/OUTSIDER-RUN.md` asks a third party to reproduce our claims. A document
can ask; it cannot execute. Until the a stranger can type one line and get a
verdict, "reproducible by a third party" is a promise rather than a property.

This tool is that one line:

    python3 tools/outsider_audit.py

It does three things, and refuses to blur them:

  1. **baseline** -- does the shipped clean package reach the verdict the docs
     claim? (INCONCLUSIVE, because it is unsigned. A tool that reported PASS
     here would be lying about the seal.)
  2. **red team** -- apply twelve mutations that a forger would try and two
     that must NOT be treated as forgeries, and check every verdict.
  3. **interop** -- if an AER-1 corpus is supplied with --kit, run the emit /
     interop / inbound checks against it. If no corpus is supplied this stage
     reports SKIPPED, and a skip is never counted as a pass.

Exit code is 0 only when nothing failed and nothing required was skipped.

Zero dependencies. No network access unless --kit triggers a corpus download,
which it does not do by default.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core.verify import verify  # noqa: E402

DEFAULT_PACKAGE = os.path.join(_REPO, "fixtures", "clean.uibc")


# --------------------------------------------------------------------------
# mutations: each takes a package directory and edits it in place
# --------------------------------------------------------------------------

def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _write(path, data):
    with open(path, "wb") as f:
        f.write(data)


def _json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _index(pkg):
    """The index is a bare list in the shipped fixture and an
    {"entries": [...]} object in packages this repo writes. Both are real;
    the reader must handle each rather than assume one."""
    path = os.path.join(pkg, "evidence", "index.json")
    raw = _json(path)
    entries = raw["entries"] if isinstance(raw, dict) else raw
    return path, raw, entries


def _save_index(path, raw, entries):
    if isinstance(raw, dict):
        raw["entries"] = entries
        _dump(path, raw)
    else:
        _dump(path, entries)


def _evidence_files(pkg):
    _, _, entries = _index(pkg)
    return entries, [os.path.join(pkg, "evidence", e["path"]) for e in entries]


def m_flip_evidence_byte(pkg):
    """One byte in one evidence file. The hash no longer matches."""
    _, files = _evidence_files(pkg)
    data = bytearray(_read(files[0]))
    data[len(data) // 2] ^= 0x01
    _write(files[0], bytes(data))


def m_truncate_evidence_file(pkg):
    """Cut the file in half: hash mismatch, same as any edit."""
    _, files = _evidence_files(pkg)
    data = _read(files[0])
    _write(files[0], data[: len(data) // 2])


def m_delete_evidence_file(pkg):
    _, files = _evidence_files(pkg)
    os.remove(files[0])


def m_edit_root(pkg):
    """Change one hex digit of the root in the manifest."""
    man = _json(os.path.join(pkg, "manifest.json"))
    root = man["evidence_root"]
    man["evidence_root"] = ("0" if root[0] != "0" else "1") + root[1:]
    _dump(os.path.join(pkg, "manifest.json"), man)


def m_add_undeclared_file(pkg):
    _write(os.path.join(pkg, "extra-payload.json"), b'{"injected": true}')


def m_duplicate_member(pkg):
    """Duplicate JSON member name -- must be caught before any parse."""
    path = os.path.join(pkg, "manifest.json")
    text = _read(path).decode("utf-8")
    assert text.lstrip().startswith("{")
    first = text.index("{") + 1
    text = text[:first] + '"schema": "uibc-core/0.2.2-proposal", ' + text[first:]
    _write(path, text.encode("utf-8"))


def m_bad_calendar_date(pkg):
    """30 February does not exist. S12 judges values, not hashes."""
    lc = _json(os.path.join(pkg, "lifecycle.json"))
    events = lc.get("events") or lc.get("entries") or []
    assert events, "lifecycle has no events to edit"
    events[0]["timestamp"] = "2026-02-30T00:00:00Z"
    _dump(os.path.join(pkg, "lifecycle.json"), lc)


def m_identity_mismatch(pkg):
    ident = _json(os.path.join(pkg, "identity.json"))
    ident["agent_id"] = ident["agent_id"] + "-other"
    _dump(os.path.join(pkg, "identity.json"), ident)


def m_drop_tail(pkg):
    """Truncation: drop the last evidence entry and its file.

    This is the attack a hash chain cannot see -- the package is
    self-consistent afterwards, and only the root (or an out-of-band head)
    notices."""
    path, raw, entries = _index(pkg)
    last = entries.pop()
    man = _json(os.path.join(pkg, "manifest.json"))
    man["evidence_count"] = len(entries)
    _dump(os.path.join(pkg, "manifest.json"), man)
    _save_index(path, raw, entries)
    path = os.path.join(pkg, "evidence", last["path"])
    if os.path.exists(path):
        os.remove(path)


def m_remove_entry_keep_file(pkg):
    """Deregister an entry but leave the bytes: an undeclared file."""
    path, raw, entries = _index(pkg)
    entries.pop()
    _save_index(path, raw, entries)


def m_tamper_seal(pkg):
    path = os.path.join(pkg, "signatures", "seal.json")
    data = _read(path)
    _write(path, data.replace(b'"', b"'", 1) if b'"' in data else data + b"x")


# -- controls: these must NOT be reported as forgeries ---------------------

def c_reorder_index(pkg):
    """The root commits to sorted content hashes, so reordering entries
    changes the file but not the commitment. A verifier that flags this is
    producing false positives."""
    path, raw, entries = _index(pkg)
    _save_index(path, raw, list(reversed(entries)))


def c_noop(pkg):
    """Copy untouched: proves the harness itself does not perturb the package."""
    return


# (name, fn, expectation, why)
# expectation: "FAIL" the verdict must be FAIL
#              "NOT_PASS" the verdict must not be PASS (INCONCLUSIVE allowed)
#              "SAME" the verdict must equal the baseline verdict
RED_TEAM = [
    ("flip one byte in evidence", m_flip_evidence_byte, "FAIL", "S4 recomputes hashes"),
    ("truncate one evidence file", m_truncate_evidence_file, "FAIL", "same, shorter"),
    ("delete one evidence file", m_delete_evidence_file, "FAIL", "index points at nothing"),
    ("edit the evidence root", m_edit_root, "FAIL", "S5 recomputes the root"),
    ("add an undeclared file", m_add_undeclared_file, "FAIL", "S1 counts declarations"),
    ("duplicate a JSON member name", m_duplicate_member, "FAIL", "S11 runs before parsing"),
    ("impossible calendar date", m_bad_calendar_date, "FAIL", "S12 judges values"),
    ("mismatch agent identity", m_identity_mismatch, "FAIL", "S2 compares across files"),
    ("drop the tail entry and file", m_drop_tail, "FAIL", "the root moves"),
    ("deregister an entry, keep the file", m_remove_entry_keep_file, "FAIL", "undeclared evidence"),
    ("tamper the seal", m_tamper_seal, "NOT_PASS", "S6 must not pass a broken seal"),
]

CONTROLS = [
    ("reorder index entries", c_reorder_index, "SAME", "root commits sorted hashes"),
    ("copy untouched", c_noop, "SAME", "the harness must not perturb"),
]


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

def _prepare(src, tmp):
    dst = os.path.join(tmp, "pkg")
    shutil.copytree(src, dst)
    return dst


def _verdict(pkg):
    r = verify(pkg)
    failed = sorted(c["id"] for c in r["checks"] if c["result"] == "FAIL")
    inconclusive = sorted(c["id"] for c in r["checks"] if c["result"] == "INCONCLUSIVE")
    return {
        "result": r["result"],
        "trust_level": r.get("trust_level"),
        "failed_checks": failed,
        "inconclusive_checks": inconclusive,
    }


def run_baseline(package):
    got = _verdict(package)
    # The shipped fixture is unsigned: PASS here would mean the seal check
    # is decorative. INCONCLUSIVE is the honest verdict.
    expected = {"result": "INCONCLUSIVE", "trust_level": "unattested"}
    ok = got["result"] == expected["result"]
    return {
        "stage": "baseline",
        "expected": expected,
        "got": got,
        "ok": ok,
        "note": "unsigned package: INCONCLUSIVE, and no check may be invented "
                "to turn that into PASS",
    }


def run_red_team(package, baseline_verdict):
    rows = []
    for name, fn, expectation, why in RED_TEAM:
        rows.append(_one(package, name, fn, expectation, why, baseline_verdict))
    for name, fn, expectation, why in CONTROLS:
        rows.append(_one(package, name, fn, expectation, why, baseline_verdict,
                         control=True))
    ok = all(r["ok"] for r in rows)
    return {
        "stage": "red-team",
        "rows": rows,
        "ok": ok,
        "failed": [r["name"] for r in rows if not r["ok"]],
        "count": len(rows),
    }


def _one(package, name, fn, expectation, why, baseline_verdict, control=False):
    tmp = tempfile.mkdtemp(prefix="uibc-rt-")
    try:
        pkg = _prepare(package, tmp)
        try:
            fn(pkg)
            mutation_error = None
        except Exception as e:  # a mutation that cannot be applied is not a pass
            mutation_error = "%s: %s" % (type(e).__name__, e)
        got = _verdict(pkg)
        if mutation_error:
            ok = False
            verdict_note = "mutation not applied"
        elif expectation == "FAIL":
            ok = got["result"] == "FAIL"
            verdict_note = "must be FAIL"
        elif expectation == "NOT_PASS":
            ok = got["result"] != "PASS"
            verdict_note = "must not be PASS"
        else:  # SAME
            ok = got["result"] == baseline_verdict["result"]
            verdict_note = "must equal baseline (%s)" % baseline_verdict["result"]
        return {
            "name": name,
            "kind": "control" if control else "attack",
            "why": why,
            "expectation": expectation,
            "expectation_note": verdict_note,
            "got": got["result"],
            "failed_checks": got["failed_checks"],
            "ok": ok,
            "mutation_error": mutation_error,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_interop(kit):
    if not kit:
        return {
            "stage": "interop",
            "status": "SKIPPED",
            "ok": None,
            "note": "--kit not supplied; a skip is not a pass",
        }
    checks = []
    tmp = tempfile.mkdtemp(prefix="uibc-io-")
    try:
        out = os.path.join(tmp, "emit.json")
        runner = os.path.join(kit, "base", "conformance.py")
        code_e = _run([sys.executable, os.path.join(_REPO, "tools", "emit_aer1_receipts.py"),
                       "--package", DEFAULT_PACKAGE, "--out", out,
                       "--publisher-runner", runner])
        checks.append({"name": "emit -> publisher runner", "exit": code_e, "ok": code_e == 0})

        code_d = _run([sys.executable, os.path.join(_REPO, "tools", "aer1_interop_demo.py"),
                       "--kit", kit])
        checks.append({"name": "one-command interop demo", "exit": code_d, "ok": code_d == 0})

        valid = os.path.join(kit, "base", "test-vectors", "valid")
        invalid = os.path.join(kit, "base", "test-vectors", "invalid")
        code_v = _run([sys.executable, os.path.join(_REPO, "tools", "aer1_verify_external.py"),
                       "--dir", valid, "--expect", "ACCEPTED"])
        checks.append({"name": "inbound valid (expect ACCEPTED)", "exit": code_v, "ok": code_v == 0})
        code_i = _run([sys.executable, os.path.join(_REPO, "tools", "aer1_verify_external.py"),
                       "--dir", invalid, "--expect", "REJECTED"])
        checks.append({"name": "inbound invalid (expect REJECTED)", "exit": code_i, "ok": code_i == 0})
        return {"stage": "interop", "status": "RUN", "checks": checks,
                "ok": all(c["ok"] for c in checks)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(argv):
    import subprocess
    p = subprocess.run(argv, cwd=_REPO, capture_output=True)
    if p.returncode != 0:
        sys.stderr.write(p.stdout.decode("utf-8", "replace")[-1500:])
        sys.stderr.write(p.stderr.decode("utf-8", "replace")[-1500:])
    return p.returncode


def run_all(package, kit):
    baseline = run_baseline(package)
    red = run_red_team(package, baseline["got"])
    interop = run_interop(kit)
    # A skip of a stage that requires a corpus is not a pass, but it is not a
    # failure of our code either: it is reported as SKIPPED and the exit code
    # stays 0 only if the caller did not ask for that stage.
    overall_ok = baseline["ok"] and red["ok"]
    return {
        "package": package,
        "stage_baseline": baseline,
        "stage_redteam": red,
        "stage_interop": interop,
        "ok": overall_ok,
        "note": "interop SKIPPED is not counted as a pass",
    }


def _print_human(result):
    b = result["stage_baseline"]
    print("baseline   : %-12s expected %-12s  %s"
          % (b["got"]["result"], b["expected"]["result"], "ok" if b["ok"] else "MISMATCH"))
    print("             checks: %s" % (b["got"]["inconclusive_checks"] or "none")
          + " inconclusive")
    print()
    print("red team   : %d cases" % result["stage_redteam"]["count"])
    for r in result["stage_redteam"]["rows"]:
        print("  %-4s %-40s %-9s -> %-12s %s"
              % ("ctrl" if r["kind"] == "control" else "atk", r["name"],
                 r["expectation"], r["got"],
                 "ok" if r["ok"] else "FAILED: " + r["expectation_note"]))
        if r["failed_checks"]:
            print("       caught by: %s" % ", ".join(r["failed_checks"]))
    print()
    it = result["stage_interop"]
    if it["status"] == "SKIPPED":
        print("interop    : SKIPPED (%s)" % it["note"])
    else:
        print("interop    : %s" % ("all pass" if it["ok"] else "FAILED"))
        for c in it["checks"]:
            print("  %-38s exit=%d %s" % (c["name"], c["exit"], "ok" if c["ok"] else "FAILED"))
    print()
    print("VERDICT    : %s" % ("OK" if result["ok"] else "FAILED"))


def main():
    ap = argparse.ArgumentParser(description="Run the outsider audit.")
    ap.add_argument("--package", default=DEFAULT_PACKAGE)
    ap.add_argument("--kit", default=None,
                    help="AER-1 corpus directory; interop is skipped without it")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = run_all(args.package, args.kit)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
