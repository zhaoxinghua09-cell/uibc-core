#!/usr/bin/env python3
"""One-command conformance run for someone who did not clone this repository.

This file ships *inside* the conformance zip. It needs nothing from the
repository: stdlib only, and it calls whatever verifier you point it at.

    python run.py                          # reference verifier, if installed
    python run.py --verify "uibc verify {pkg}"
    python run.py --json                   # machine-readable

Exit code 0 only when every case behaved as the manifest requires.

What a pass means, and what it does not:
  - it means your verifier refused each broken package and named at least one
    check the manifest expects, and accepted the correct ones;
  - it does NOT mean the verifier is secure, independent or audited. The
    manifest is ours, the corpus is ours, and this runner is ours.
  - a receipt written here is only evidence that this command ran, on this
    machine, at this time, and produced this table. It is not a certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "manifest.json")
CASES = os.path.join(HERE, "cases")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _split(command):
    """Split a command template into argv, respecting quotes.

    str.split() breaks `--verify '"C:/Program Files/Python/python.exe" uibc_core.pyz
    verify {pkg}'` at every space, so a bundled single-file verifier on a path with
    spaces could never be run. shlex in posix mode eats Windows backslashes, so it
    is used non-posix and the quote characters are trimmed from the tokens.
    """
    try:
        toks = shlex.split(command, posix=False)
    except ValueError:
        toks = command.split()
    out = []
    for t in toks:
        if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
            t = t[1:-1]
        out.append(t)
    return out


def verifier_version(command):
    """Version of the reference implementation, only when it is what was run.

    Probing `import uibc_core` regardless of the command would label someone
    else's verifier with our version number, which is the kind of receipt
    detail that turns into a false claim later.
    """
    if "uibc_core" not in command and "uibc " not in command:
        return "not the reference verifier (version not probed)"
    try:
        # a bundled .pyz reports its own version via --version; an installed
        # package reports through import. Neither is assumed.
        pyz = [t for t in _split(command.replace("{pkg}", "")) if t.endswith(".pyz")]
        if pyz:
            out = subprocess.run([sys.executable, pyz[0], "--version"],
                                 capture_output=True, text=True, timeout=30)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
            return "unknown"
        out = subprocess.run([sys.executable, "-c",
                              "import uibc_core;print(uibc_core.__version__)"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def call_verifier(command, pkg):
    argv = _split(command.replace("{pkg}", pkg))
    # A command that cannot be started is an environment fact, not a verdict. Without
    # this catch, `--verify "uibc verify {pkg}"` on a machine without uibc raised
    # FileNotFoundError and the runner died with a traceback and exit 1 - measured
    # 2026-11-20 against the shipped 0.4.1 archive, which promised exit 3 for a
    # verifier that is not installed. Reported as unparsed so the preflight below
    # turns it into exit 3 with no receipt.
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=180)
    except OSError as exc:
        return {"result": "FAIL", "checks": [], "unparsed": True,
                "verifier_unstartable": True, "returncode": None,
                "stderr": "verifier could not be started: %s: %s"
                          % (type(exc).__name__, exc)}
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        # No JSON at all is a DIFFERENT event from "JSON said FAIL". Recording
        # both as FAIL once produced a 0/36 receipt on a machine where the
        # verifier was simply not installed - a stranger could publish that as
        # "their corpus fails everything". Keep the evidence needed to tell them
        # apart.
        return {"result": "FAIL" if proc.returncode else "PASS", "checks": [],
                "unparsed": True, "raw": proc.stdout[-400:],
                "stderr": proc.stderr[-400:], "returncode": proc.returncode}
    checks = out.get("checks")
    if isinstance(checks, list) and checks and isinstance(checks[0], dict):
        return {"result": out.get("result"), "checks": checks, "unparsed": False}
    return {"result": out.get("result"), "checks": [], "unparsed": False}


def reported_failures(got):
    return {c.get("id") for c in got.get("checks", [])
            if str(c.get("result", "")).upper() == "FAIL"}


def judge(case, got, strict=False, all_checks=False):
    """Score one case.

    Two modes, and the difference matters:
      refusal-only (default, unchanged): an accept case passes when the verdict is
        anything but FAIL. A verifier that answers INCONCLUSIVE to everything
        therefore clears every accept case, and scores the same as one that answers
        PASS to everything. Measured 2026-11-27: always-PASS, always-INCONCLUSIVE
        and roots-only all score 6/58 = 10.3%.
      strict (`--strict-verdict`): the verdict must equal the `expected_result` this
        repository declares for the case. That number is already in the manifest and
        was never used for scoring; an accept case that says INCONCLUSIVE where the
        repo says PASS now fails, which is the whole point of having a declared
        expectation.
      all_checks (`--require-all-checks`): a refusal must cover every expected check
        rather than intersect one of them. Measured 2026-11-27 on the 200-case
        corpus: name-one let a three-line 'FAIL + [S4]' script score 42.0% (S4 occurs
        in 71 of the 142 refusal cases); name-all puts every single-code liar at
        <=13.5% and leaves the reference implementation at 200/200, because a real
        verifier reports the whole failure set and is not penalised by the tighter
        rule.
    """
    verdict = (got.get("result") or "").upper()
    parsed = not got.get("unparsed", False)
    expected = (case.get("expected_result") or "").upper()
    if case.get("expect") == "accept":
        if strict and expected:
            ok = verdict == expected and not reported_failures(got)
            note = "" if ok else "verdict %s, expected %s on a correct package" % (
                verdict or "none", expected)
        else:
            ok = verdict != "FAIL" and not reported_failures(got)
            note = "" if ok else "refused a package that is correct"
        return {"id": case["id"], "attack": case["attack"], "ok": ok,
                "verdict": verdict, "reported": [], "expected": [],
                "note": note,
                "verifier_parsed": parsed,
                "verifier_stderr": got.get("stderr", "")}
    reported = reported_failures(got)
    required = set(case["expected_checks"])
    named = required <= reported if all_checks else bool(reported & required)
    refused = verdict in ("FAIL", "INCONCLUSIVE")
    verdict_matches = (not strict) or (not expected) or verdict == expected
    return {"id": case["id"], "attack": case["attack"],
            "ok": refused and named and verdict_matches, "verdict": verdict,
            "reported": sorted(reported), "expected": case["expected_checks"],
            "note": ("" if refused and named and verdict_matches else
                     "verdict %s, expected %s on a broken package" % (verdict or "none", expected)
                     if refused and named and not verdict_matches else
                     "refused but did not name an expected check" if refused
                     else "did not refuse a package that is broken"),
            "verifier_parsed": parsed,
            "verifier_stderr": got.get("stderr", "")}


def run_all(command, strict=False, all_checks=False):
    with open(MANIFEST, encoding="utf-8") as f:
        man = json.load(f)
    tmp = tempfile.mkdtemp(prefix="uibc-conf-")
    rows = []
    try:
        for case in man["cases"]:
            # manifest paths already start with "cases/", and are relative to the
            # archive root, not to cases/
            src = os.path.join(HERE, case["path"])
            pkg = os.path.join(tmp, case["id"])
            shutil.copytree(src, pkg)
            rows.append(judge(case, call_verifier(command, pkg), strict=strict,
                              all_checks=all_checks))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def _public(rows):
    return [{k: v for k, v in r.items() if not k.startswith("verifier_")} for r in rows]


def main():
    ap = argparse.ArgumentParser()
    pyz = os.path.join(HERE, "uibc_core.pyz")
    bundled = os.path.isfile(pyz)
    default_verify = ('"%s" "%s" verify {pkg}' % (sys.executable, pyz)
                      if bundled
                      else sys.executable + " -m uibc_core.cli verify {pkg}")
    ap.add_argument("--verify", default=default_verify)
    ap.add_argument("--allow-installed", action="store_true",
                    help="accept a verifier installed in this Python when the archive "
                         "carries none; without it that case is a setup failure (exit 3)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict-verdict", action="store_true",
                    help="also require the verdict to equal the case's declared "
                         "expected_result; without it an accept case passes on any "
                         "verdict that is not FAIL")
    ap.add_argument("--require-all-checks", action="store_true",
                    help="a refusal must name every expected check, not just one. "
                         "Measured 2026-11-27 on the 200-case corpus: with name-one a "
                         "blanket 'FAIL + [S4]' scores 42.0% and 'FAIL + [S12]' 32.5%; "
                         "with name-all the same liars score 13.5% and 9.5%, while the "
                         "reference implementation stays at 200/200")
    ap.add_argument("--receipt", default="receipt.json",
                    help="where to write the run receipt; '' to skip")
    ap.add_argument("--run-by", default="",
                    help="name to record as the person who ran this (leave blank if none)")
    a = ap.parse_args()

    if not os.path.isdir(CASES):
        sys.exit("error: cases/ not found next to this script; unzip the archive first")

    # Red team A9 (measured 2026-11-27): appending 64 bytes to uibc_core.pyz still
    # ran 58/58, because nothing bound the archive to the verifier it carries. The
    # seal writes uibc_core.sha256 beside the pyz; a mismatch is a setup failure,
    # not a verdict about the corpus.
    side = os.path.join(HERE, "uibc_core.sha256")
    if bundled and os.path.isfile(side):
        with open(side, encoding="ascii") as f:
            want = f.read().split()[0].strip().lower()
        with open(pyz, "rb") as f:
            got = hashlib.sha256(f.read()).hexdigest()
        if got != want:
            sys.stderr.write(
                "\nThis archive's verifier does not match the hash it ships with.\n"
                "  declared %s\n  found    %s\n"
                "That is a setup problem, not a verdict about the corpus: refusing to "
                "write a receipt that would read as conformance results.\n" % (want, got))
            sys.exit(3)

    # Red team A7 (measured 2026-11-27): expected.json is a second copy of the same
    # truth and run.py used to read only manifest.json, so an edit to expected.json
    # changed nothing and said nothing. Two carriers must agree before a run starts.
    exp_path = os.path.join(HERE, "expected.json")
    if os.path.isfile(exp_path):
        with open(exp_path, encoding="utf-8") as f:
            exp = json.load(f)
        with open(MANIFEST, encoding="utf-8") as f:
            man = json.load(f)
        m_exp = {c["id"]: (c.get("expect") or
                          ("accept" if not c.get("expected_checks") else "refuse"))
                 for c in man["cases"]}
        e_exp = {c["id"]: c.get("expect") for c in exp.get("cases", [])}
        drift = sorted(k for k in set(m_exp) | set(e_exp) if m_exp.get(k) != e_exp.get(k))
        if drift:
            sys.stderr.write(
                "\nexpected.json and manifest.json disagree on %d case(s): %s\n"
                "Two copies of one truth: refusing to run rather than pick one.\n"
                "Re-seal the archive, or delete expected.json if the manifest is the "
                "only table you intend to ship.\n" % (len(drift), ", ".join(drift[:5])))
            sys.exit(1)

    # Measured 2026-11-20: the archive's own control ("a machine without the verifier
    # must exit 3") went green on a runner that had `uibc-core` pip-installed, because
    # this script fell back to `python -m uibc_core.cli`. The fallback made "the archive
    # carries its verifier" true only on machines that did not need it. So the fallback
    # is no longer silent: with no bundled verifier, running this script as-is is a
    # setup failure, not a conformance result.
    if not bundled and not a.allow_installed and a.verify == default_verify:
        sys.stderr.write(
            "\nThis archive carries no verifier of its own (uibc_core.pyz is absent), so "
            "there is nothing here to run.\n"
            "That is a setup problem, not a verdict about the corpus: refusing to write a "
            "receipt that would read as failures.\n\n"
            "Either point this runner at a verifier you have:\n"
            "    python run.py --verify \"uibc verify {pkg}\"\n"
            "or say out loud that you accept one installed in %s:\n"
            "    python run.py --allow-installed\n"
            % sys.executable)
        sys.exit(3)

    rows = run_all(a.verify, strict=a.strict_verdict, all_checks=a.require_all_checks)
    passed = sum(1 for r in rows if r["ok"])

    # Preflight, in effect: if not one case produced JSON, the verifier did not
    # run. That is a setup problem, not a verdict about the corpus, so refuse to
    # write a receipt that would read as "36 failures".
    if not any(r["verifier_parsed"] for r in rows):
        first = rows[0] if rows else {}
        unstartable = first.get("verifier_unstartable")
        sys.stderr.write(
            "\nNo verifier output was parseable in any case, so this is not a "
            "conformance result.\n"
            + ("The verifier command could not be started at all: %s\n"
               % first.get("verifier_stderr", "") if unstartable else "")
            + "Command run: %s\n" % a.verify
            + ("stderr (last 400 chars):\n%s\n" % first.get("verifier_stderr", "")
               if first.get("verifier_stderr") else "")
            + "The reference verifier is probably not installed for this Python "
              "(%s).\nTry:\n    %s -m pip install uibc-core==0.4.1\n"
              % (sys.executable, sys.executable)
            + "No receipt was written, because a receipt saying 0/%d would be "
              "misleading.\n" % len(rows))
        sys.exit(3)

    if not a.json:
        for r in rows:
            print("%-4s %-6s %s" % (r["id"], "ok" if r["ok"] else "FAIL",
                                    r["attack"][:44]
                                    + ("  " + r["note"] if r["note"] else "")))
        print("\nstrict %d/%d" % (passed, len(rows)))
        if passed != len(rows):
            print("\nIf every row failed at once, the verifier probably crashed or "
                  "printed no JSON. Install the reference one with:\n"
                  "    pip install uibc-core==0.4.1")

    if a.receipt:
        # diagnostic keys stay out of the receipt: it is a published artefact,
        # and a stranger's receipt should have the same shape as ours.
        public_rows = [{k: v for k, v in r.items() if not k.startswith("verifier_")}
                       for r in rows]
        receipt = {
            "kind": "uibc-conformance-run-receipt",
            "notice": ("This records that a command ran on a machine and produced "
                       "this table. It is not a certification, and it is not an "
                       "independent audit: the corpus, the manifest and this runner "
                       "are all authored by the project."),
            "run_by": a.run_by or None,
            # A receipt is normally stamped with the clock. When the caller fixes
            # SOURCE_DATE_EPOCH -- as the release workflow does, so one tag means one
            # set of bytes -- the stamp follows it. Measured 2026-11-20: this one field
            # made a re-run of the same tag produce a different receipt, and therefore
            # a different CORPUS-DIGESTS.txt.
            "when_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                      time.gmtime(int(os.environ["SOURCE_DATE_EPOCH"])
                                                  if os.environ.get("SOURCE_DATE_EPOCH")
                                                  else None)),
            "command": a.verify,
            # Whether the thing that judged the cases came out of this archive or out
            # of the machine's site-packages. A reader who cares about "no install
            # needed" needs to see which it was.
            "verifier_kind": "bundled" if bundled else "installed",
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "verifier_version": verifier_version(a.verify),
            # Which verifier answered: the one inside this archive, or one this
            # machine happened to have. The two are not the same evidence.
            "verifier_source": ("bundled with the archive" if bundled
                                else "installed in the Python that ran this"),
            "manifest_sha256": sha256(MANIFEST) if os.path.isfile(MANIFEST) else None,
            "scoring": ("strict-verdict" if a.strict_verdict else "refusal-only") + ("+all-checks" if a.require_all_checks else ""),
            "cases": len(public_rows), "passed": passed,
            "rows": public_rows,
        }
        with open(a.receipt, "w", encoding="utf-8", newline="\n") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
            f.write("\n")
        if not a.json:
            print("\nreceipt written to %s" % a.receipt)

    if a.json:
        print(json.dumps({"cases": len(rows), "passed": passed,
                          "scoring": ("strict-verdict" if a.strict_verdict else "refusal-only") + ("+all-checks" if a.require_all_checks else ""),
                          "rows": _public(rows)},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if passed == len(rows) else 1)


if __name__ == "__main__":
    main()
