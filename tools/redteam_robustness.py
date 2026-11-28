#!/usr/bin/env python3
"""Hostile-input red team: does the verifier return a verdict, or does it die?

A verifier has two failure modes and only one of them is visible in a
conformance suite. The suite asks "does it refuse the packages we thought of".
This asks "does it survive the packages we did not".

Every case below is bytes that a careless reader will happily accept and a
strict one must refuse. The rule is the same for both implementations:

  * never traceback, never hang, never exit without a report;
  * never answer INCONCLUSIVE to bytes that were never judged, unless the
    correct answer really is "could not tell";
  * say which check caught it, when a check can.

Exit code 0 when every case is answered by both implementations, 1 otherwise.
Run: python3 tools/redteam_robustness.py [--json]
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(REPO, "fixtures", "clean.uibc")
JS = os.path.join(REPO, "tools", "verify-js", "verify.mjs")


def run_js(pkg):
    p = subprocess.run(["node", JS, pkg], capture_output=True, text=True, timeout=120)
    return p


def run_py(pkg):
    code = ("import sys, json\nsys.path.insert(0, %r)\n"
            "from uibc_core.verify import verify\n"
            "r = verify(%r)\n"
            "print(json.dumps({'result': r.get('result'), "
            "'failed': [c['id'] for c in r.get('checks', []) if c.get('result') == 'FAIL']}))\n"
            % (REPO, pkg))
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)


def verdict(proc):
    """Return (verdict_string, crashed)."""
    if proc.returncode != 0 and not proc.stdout.strip():
        tail = (proc.stderr.strip().splitlines() or ["exit %d" % proc.returncode])[-1]
        return "CRASHED: " + tail[-60:], True
    try:
        d = json.loads(proc.stdout)
    except ValueError:
        return "NO JSON", True
    if "checks" in d:
        fails = [c["id"] for c in d["checks"] if c["result"] == "FAIL"]
    else:
        fails = d.get("failed", [])
    return "%s %s" % (d.get("result"), ",".join(fails[:4])), False


class CaseSkipped(Exception):
    """A case whose hostile condition cannot be constructed on this platform.

    Raised instead of silently returning. A mutation that did nothing and a
    mutation that the verifier refused look identical from the outside, and
    reporting the first as the second's failure blames the implementations
    for a property of the host (e.g. SeCreateSymbolicLinkPrivilege on
    Windows, which raises WinError 1314).
    """


def build(tmp):
    """Create one directory per hostile input and return a list of cases."""
    cases = []

    def fresh(name):
        d = os.path.join(tmp, name)
        shutil.copytree(BASE, d)
        return d

    def add(name, mutate, expect_fail=True, why=""):
        d = fresh(name)
        skipped = None
        try:
            mutate(d)
        except CaseSkipped as e:
            skipped = str(e)
        cases.append({"name": name, "path": d, "expect_fail": expect_fail,
                      "why": why, "skipped": skipped})

    add("not-json", lambda d: open(os.path.join(d, "manifest.json"), "w").write("{oops"),
        why="bytes that are not JSON must be refused, not crashed on")
    add("manifest-is-array",
        lambda d: open(os.path.join(d, "manifest.json"), "w").write("[1,2,3]"),
        why="the wrong top-level type is a structural refusal")
    add("duplicate-member",
        lambda d: open(os.path.join(d, "manifest.json"), "w").write(
            open(os.path.join(BASE, "manifest.json")).read().rstrip()[:-1] +
            ',"agent_version":"x","agent_version":"y"}'),
        why="two readers, two answers - the check exists for this")
    add("nan-literal",
        lambda d: open(os.path.join(d, "manifest.json"), "w").write(
            open(os.path.join(BASE, "manifest.json")).read().rstrip()[:-1] + ',"remark":NaN}'),
        why="RFC 8259 has no NaN; a permissive parser must still refuse it")
    add("deep-nesting",
        lambda d: open(os.path.join(d, "manifest.json"), "w").write("[" * 4000 + "]" * 4000),
        why="a recursive reader dies here; the verifier must not")
    add("invalid-utf8",
        lambda d: open(os.path.join(d, "identity.json"), "wb").write(b'{"agent_id":"\xff\xfe"}'),
        why="the format is UTF-8 or it is nothing")
    add("path-escape",
        lambda d: _escape(d),
        why="an evidence path must not resolve outside the package")
    add("symlink-out",
        lambda d: _symlink(d),
        why="a symlink is how a package reads a file it did not ship")
    add("empty-dir", lambda d: _empty(d), why="nothing at all is still something to say")
    add("huge-manifest", lambda d: open(os.path.join(d, "manifest.json"), "w").write(
        '{"agent_version":"%s"}' % ("x" * (8 << 20))),
        why="a reader must not be defeated by size alone")
    return cases


def _escape(d):
    p = os.path.join(d, "evidence", "index.json")
    idx = json.load(open(p))
    idx["entries"][0]["path"] = "../../etc/passwd"
    json.dump(idx, open(p, "w"), indent=2)


def _symlink(d):
    p = os.path.join(d, "evidence", "index.json")
    idx = json.load(open(p))
    target = os.path.join(d, "evidence", "files", "escaped.txt")
    try:
        os.symlink("/etc/hostname", target)
    except (OSError, NotImplementedError) as e:
        raise CaseSkipped("symlink could not be created on this host (%s); "
                          "the case cannot be judged here"
                          % (getattr(e, "winerror", None) or getattr(e, "errno", "?")))
    idx["entries"].append({"evidence_id": "11111111-1111-4111-8111-111111111111",
                           "type": "OUTPUT", "path": "files/escaped.txt",
                           "content_hash": hashlib.sha256(b"x").hexdigest(),
                           "created_at": "2026-11-17T00:00:00Z"})
    json.dump(idx, open(p, "w"), indent=2)


def _empty(d):
    for name in os.listdir(d):
        p = os.path.join(d, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="uibc-hostile-")
    cases = build(tmp)
    rows, bad, skipped = [], 0, 0
    for c in cases:
        if c["skipped"]:
            skipped += 1
            rows.append({"case": c["name"], "js": "SKIPPED", "py": "SKIPPED",
                         "ok": True, "skipped": c["skipped"], "why": c["why"]})
            if not args.json:
                print("%-18s SKIPPED (%s)" % (c["name"], c["skipped"]))
            continue
        jv, jcrashed = verdict(run_js(c["path"]))
        pv, pcrashed = verdict(run_py(c["path"]))
        answered = not (jcrashed or pcrashed)
        refused = jv.startswith("FAIL") and pv.startswith("FAIL")
        ok = answered and (refused or not c["expect_fail"])
        if not ok:
            bad += 1
        rows.append({"case": c["name"], "js": jv, "py": pv, "ok": ok, "why": c["why"]})
        if not args.json:
            print("%-18s JS=%-24s PY=%-24s %s" % (c["name"], jv, pv, "ok" if ok else "PROBLEM"))

    if args.json:
        print(json.dumps({"cases": rows, "problems": bad, "skipped": skipped}, indent=2))
    else:
        print("\n%d of %d hostile inputs answered by both implementations and refused"
              % (len(rows) - bad - skipped, len(rows) - skipped))
        if skipped:
            print("%d case(s) skipped on this platform - not counted as a pass" % skipped)
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("kept:", tmp)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
