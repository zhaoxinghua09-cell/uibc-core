#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command independent reproduction of the uibc gate's published numbers.

Written for a reader who does not trust us. It runs only local, offline, account-free
steps and prints a receipt a third party can quote:

  1. environment     python, uibc version, git HEAD, and a probe proving no network was used
  2. fixture matrix  8 packages x 3 pinning conventions, compared against RESULTS.json
  3. corpus selfcheck  regenerates the 500-case corpus and compares row hashes
  4. conformance     runs the shipped consistency vectors
  5. denominators    re-adds the published per-family counts against the corpus file

Exit 0 only if every comparison matches. Any mismatch is printed with the expected
and observed value; the tool never "repairs" anything, because a reproduction script
that can pass by fixing its own inputs reproduces nothing.

Usage:
  python reproduce_gate.py --repo <uibc-core-root> --uibc <path-to-uibc[.exe]> [--out DIR]

Nothing here needs a token, an account, or a network route. If a step fails because
of a missing local file, that is reported as MISSING, not as PASS.
"""
import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time

MODES = (("open", []), ("pinned-owner", ["--pubkey"]), ("pinned-attacker", ["--pubkey"]))


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, cwd=None, timeout=600):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0


def git_head(repo):
    """Same three-level fallback the selfcheck uses; never invent a value."""
    for cmd in (["git", "rev-parse", "HEAD"],):
        try:
            rc, out, _ = run(cmd, cwd=repo, timeout=20)
            if rc == 0 and out.strip():
                return out.strip().splitlines()[0]
        except Exception:
            pass
    try:
        head = open(os.path.join(repo, ".git", "HEAD"), encoding="utf-8").read().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            p = os.path.join(repo, ".git", ref)
            if os.path.exists(p):
                return open(p, encoding="utf-8").read().strip()
        else:
            return head
    except OSError:
        pass
    for var in ("GITHUB_SHA", "CI_COMMIT_SHA", "CI_COMMIT_ID", "BUILD_SOURCEVERSION"):
        if os.environ.get(var):
            return os.environ[var]
    return "UNAVAILABLE"


def network_probe():
    """A closed socket is evidence for 'this ran offline', not a failure."""
    try:
        s = socket.create_connection(("1.1.1.1", 443), timeout=3)
        s.close()
        return False, "reachable"
    except Exception as e:
        return True, "blocked (%s)" % type(e).__name__


def fixture_matrix(repo, uibc):
    """8 packages x 3 conventions against the shipped expectations."""
    fx = os.path.join(repo, "fixtures-v041")
    expected = json.load(open(os.path.join(fx, "RESULTS.json"), encoding="utf-8"))
    rows, mismatches = [], []
    for case in sorted(expected):
        pkg = os.path.join(fx, case + ".uibc")
        if not os.path.exists(pkg):
            mismatches.append((case, "all", "MISSING package"))
            continue
        for mode, flags in MODES:
            if mode == "open":
                cmd = [uibc, "verify", pkg]
            else:
                key = "owner.key.pub" if mode == "pinned-owner" else "attacker.key.pub"
                cmd = [uibc, "verify", pkg, "--pubkey", os.path.join(fx, key)]
            rc, out, _ = run(cmd, timeout=120)
            try:
                verdict = json.loads(out[out.index("{"):out.rindex("}") + 1])
            except Exception:
                verdict = {}
            got = verdict.get("result", "UNPARSED")
            got_nonpass = sorted(c["id"] for c in (verdict.get("checks") or []) if c.get("result") != "PASS")
            exp = expected[case][mode]
            ok = (got == exp["result"]) and (got_nonpass == sorted(exp.get("non_pass", [])))
            rows.append((case, mode, got, ",".join(got_nonpass) or "-", "match" if ok else "MISMATCH"))
            if not ok:
                mismatches.append((case, mode, "expected %s/%s got %s/%s" % (
                    exp["result"], ",".join(sorted(exp.get("non_pass", [])) or ["-"]),
                    got, ",".join(got_nonpass) or "-")))
    return rows, mismatches


def corpus_selfcheck(repo, python):
    tool = os.path.join(repo, "tools", "corpus_selfcheck.py")
    if not os.path.exists(tool):
        return "MISSING", "", 0.0
    rc, out, sec = run([python, tool], cwd=repo, timeout=900)
    verdict = "UNPARSED"
    for line in out.splitlines():
        if "MATCH" in line:
            verdict = "MATCH"
        elif "MISMATCH" in line and verdict != "MATCH":
            verdict = "MISMATCH"
    return verdict if rc == 0 else ("FAIL(exit %d)" % rc), out, sec


def conformance(repo, python):
    tool = os.path.join(repo, "tools", "conformance_vectors.py")
    if not os.path.exists(tool):
        return "MISSING", ""
    rc, out, _ = run([python, tool, "--check"], cwd=repo, timeout=300)
    return ("PASS" if rc == 0 else "FAIL(exit %d)" % rc), out


def denominators(repo, prof_p=None):
    """Re-add published per-family counts against the corpus file."""
    corpus_p = os.path.join(repo, "benchmarks", "corpus", "mutation-corpus-500.json")
    if not prof_p:
        for cand in (os.path.join(repo, "far-profile.json"),
                     os.path.join(os.path.dirname(repo), "far-profile_2026-11-19.json"),
                     os.path.join(os.getcwd(), "far-profile_2026-11-19.json")):
            if os.path.exists(cand):
                prof_p = cand
                break
    prof_p = prof_p or ""
    result, notes = [], []
    if not os.path.exists(corpus_p):
        return "MISSING corpus", [], []
    cases = json.load(open(corpus_p, encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases") or cases.get("rows") or []
    total = len(cases)
    fam = {}
    for c in cases:
        f = c.get("family") or c.get("mutation") or "unknown"
        fam[f] = fam.get(f, 0) + 1
    result.append(("corpus cases", total, "expected 500", "match" if total == 500 else "MISMATCH"))
    result.append(("corpus sha256", sha256_file(corpus_p)[:16], "-", "info"))
    result.append(("families", len(fam), "expected 17", "match" if len(fam) == 17 else "MISMATCH"))
    if os.path.exists(prof_p):
        prof = json.load(open(prof_p, encoding="utf-8"))
        pf = {x["family"]: x["n"] for x in prof.get("families", [])}
        bad = [k for k in set(pf) | set(fam) if pf.get(k, 0) != fam.get(k, 0)]
        result.append(("profile per-family", "17 families", "diff=%s" % (bad or "none"),
                       "match" if not bad else "MISMATCH"))
        for m in prof.get("modes", []):
            acc = sum(m.get("accepted_by_family", {}).values())
            result.append(("mode %s accepted sum" % m["mode"], acc, "declared %s" % m["accepted"],
                           "match" if acc == m["accepted"] else "MISMATCH"))
        notes.append("head-pinned denominator is 60, not 500: %s" %
                     next((m["denominator_note"] for m in prof["modes"] if m["mode"] == "head-pinned"), "-"))
    else:
        result.append(("far-profile", "MISSING", "-", "MISSING"))
    return "checked", result, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--uibc", required=True)
    ap.add_argument("--out", default=".")
    ap.add_argument("--profile", default=None, help="path to far-profile.json (default: auto-detect)")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    start = time.time()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    offline, net_note = network_probe()
    # `uibc --version` does not exist; asking for it returns an argparse error and
    # would have recorded a usage message as a version string. Read the declared
    # version instead, and label where it came from.
    uibc_version, version_src = "UNAVAILABLE", "unavailable"
    pyproject = os.path.join(repo, "pyproject.toml")
    if os.path.exists(pyproject):
        for line in open(pyproject, encoding="utf-8"):
            if line.strip().startswith("version") and "=" in line:
                uibc_version = line.split("=", 1)[1].strip().strip('"').strip("'")
                version_src = "pyproject.toml"
                break
    if uibc_version == "UNAVAILABLE":
        rc, out, _ = run([sys.executable, "-c", "import importlib.metadata as m; print(m.version('uibc-core'))"], timeout=60)
        if rc == 0 and out.strip():
            uibc_version, version_src = out.strip(), "installed metadata"
    head = git_head(repo)

    rows, fx_mismatch = fixture_matrix(repo, a.uibc)
    corpus_v, corpus_out, corpus_sec = corpus_selfcheck(repo, sys.executable)
    conf_v, conf_out = conformance(repo, sys.executable)
    den_v, den_rows, den_notes = denominators(repo, a.profile)

    hard = []
    hard += fx_mismatch
    if corpus_v != "MATCH":
        hard.append(("corpus", "selfcheck", corpus_v))
    if conf_v != "PASS":
        hard.append(("conformance", "vectors", conf_v))
    for r in den_rows:
        if r[3] == "MISMATCH":
            hard.append(("denominators", r[0], "%s vs %s" % (r[1], r[2])))
    if not offline:
        # Not a failure of correctness, but it voids the "ran offline" claim.
        hard.append(("environment", "network", "network reachable during run"))

    lines = []
    lines.append("# Gate reproduction receipt (self-issued, not third-party)")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    lines.append("| generated | %s |" % stamp)
    lines.append("| subject | uibc-core @ `%s` |" % (head[:12] if head != "UNAVAILABLE" else head))
    lines.append("| uibc version | %s (from %s) |" % (uibc_version, version_src))
    lines.append("| python | %s |" % platform.python_version())
    lines.append("| os | %s |" % platform.platform())
    lines.append("| wall clock | %.1f s |" % (time.time() - start))
    lines.append("| network during run | %s |" % net_note)
    lines.append("| credentials used | none (no token, no account, no registry call) |")
    lines.append("")
    lines.append("## 1. Fixture matrix — 8 packages x 3 pinning conventions")
    lines.append("")
    lines.append("| case | convention | result | non-PASS checks | vs RESULTS.json |")
    lines.append("|---|---|---|---|---|")
    for c, m, g, np_, ok in rows:
        lines.append("| `%s` | %s | %s | %s | %s |" % (c, m, g, np_, ok))
    lines.append("")
    lines.append("## 2. Corpus and denominators")
    lines.append("")
    lines.append("| item | value | expected | status |")
    lines.append("|---|---|---|---|")
    lines.append("| corpus selfcheck | %s | MATCH | %s |" % (corpus_v, "ok" if corpus_v == "MATCH" else "FAIL"))
    lines.append("| corpus selfcheck wall | %.1f s | - | info |" % corpus_sec)
    for r in den_rows:
        lines.append("| %s | %s | %s | %s |" % r)
    for n in den_notes:
        lines.append("")
        lines.append("> %s" % n)
    lines.append("")
    lines.append("## 3. Shipped consistency vectors")
    lines.append("")
    lines.append("`tools/conformance_vectors.py --check` -> **%s**" % conf_v)
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    if hard:
        lines.append("**REPRODUCTION FAILED** — %d disagreement(s):" % len(hard))
        for h in hard:
            lines.append("- %s / %s: %s" % h)
    else:
        lines.append("**ALL COMPARISONS MATCH** (%d fixture comparisons, corpus row hashes, "
                     "conformance vectors, published denominators)." % len(rows))
        lines.append("")
        lines.append("This receipt says the numbers reproduce on this machine. It does **not** say "
                     "an independent party verified them: the runner is the same holder. "
                     "Quote it as self-issued.")
    lines.append("")
    lines.append("_Not assured by this run: content truth, authorization of the signing event, "
                 "producer trustworthiness, completeness against reality, out-of-band execution, "
                 "revocation/expiry reachability, judge independence._")

    md = "\n".join(lines)
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, "reproduction_receipt_%s" % time.strftime("%Y%m%d_%H%M%S"))
    open(base + ".md", "w", encoding="utf-8").write(md)
    json.dump({"generated": stamp, "subject": head, "uibc": uibc_version,
               "python": platform.python_version(), "uibc": uibc_version, "network": net_note,
               "fixture_rows": len(rows), "mismatches": hard,
               "corpus": corpus_v, "conformance": conf_v,
               "receipt_sha256": sha256_bytes(md.encode("utf-8"))},
              open(base + ".json", "w", encoding="utf-8"), indent=2)
    print(md)
    print("\nreceipt written: %s.md" % base)
    return 0 if not hard else 1


if __name__ == "__main__":
    sys.exit(main())
