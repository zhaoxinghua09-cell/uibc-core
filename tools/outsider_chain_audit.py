"""One command a stranger can run: is this line sound, and is this the latest anchor?

Nobody should have to assemble five tools to answer that. This builds two
bundles, links them, and asks both implementations the same four questions in a
stripped environment (no PYTHONPATH, empty cwd), because a check that only works
on the machine that wrote it is not a check.

    python3 tools/outsider_chain_audit.py [--keep]

Four questions:
  1. is the line of anchors sound?              (python + node)
  2. is the second bundle the state its anchor pins?  (python + node)
  3. is the first bundle still acceptable?       - no, it is superseded
  4. does a stranger notice?                     - yes: the rollback comparison

Exit 0 only if every question got the answer it should.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
NODE = shutil.which("node") or shutil.which("nodejs")


def _env():
    e = dict(os.environ)
    e.pop("PYTHONPATH", None)
    return e


def run(cmd, cwd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=_env())
    lines = [l for l in r.stdout.splitlines() if l.startswith("VERDICT")]
    return (lines[0].split(":", 1)[1].strip() if lines else "NO-VERDICT"), r.returncode, r


def main():
    keep = "--keep" in sys.argv
    tmp = tempfile.mkdtemp(prefix="outsider-chain-")
    bundles = os.path.join(tmp, "bundles")
    os.makedirs(bundles)
    seeds = ["aa" * 32, "bb" * 32]
    paths, prev = [], None
    for i, seed in enumerate(seeds, start=1):
        out = os.path.join(bundles, "r%d" % i)
        cmd = [sys.executable, os.path.join(HERE, "make_release_bundle.py"),
               "--out", out, "--seed-hex", seed]
        if prev:
            cmd += ["--prev-anchor", prev]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp, env=_env())
        if r.returncode != 0:
            print("build failed: " + r.stderr[-200:])
            return 2
        prev = os.path.join(out, "anchor.json")
        paths.append(prev)

    anchors = os.path.join(tmp, "anchors")
    os.makedirs(anchors)
    for i, p in enumerate(paths, start=1):
        shutil.copy(p, os.path.join(anchors, "%03d.json" % i))

    rows = []
    ok_all = True

    def record(name, expect, py, js=None):
        nonlocal ok_all
        good = (py == expect) and (js == expect if js is not None else True)
        ok_all = ok_all and good
        rows.append((name, expect, py, js, good))

    # 1. the line, both implementations, from an empty directory
    a_py, rc_py, _ = run([sys.executable, os.path.join(HERE, "anchor_chain.py"), anchors], tmp)
    a_js, rc_js, _ = run([NODE, os.path.join(HERE, "verify-js", "chain.mjs"), anchors], tmp) if NODE else ("node-absent", 0, None)
    record("the line is sound", "CHAIN OK", a_py, a_js)

    # 2. the newest bundle against the anchor that pins it
    b2 = os.path.join(bundles, "r2")
    n_py, _, _ = run([sys.executable, os.path.join(HERE, "anchor_check.py"), b2], tmp)
    n_js, _, _ = run([NODE, os.path.join(HERE, "verify-js", "anchor.mjs"), b2], tmp) if NODE else ("node-absent", 0, None)
    record("newest bundle matches its anchor", "ANCHORED", n_py, n_js)

    # 3+4. the rollback: an old bundle, compared against the newer anchor
    b1 = os.path.join(bundles, "r1")
    o_py, _, _ = run([sys.executable, os.path.join(HERE, "anchor_check.py"), b1,
                      "--prev", paths[1]], tmp)
    record("superseded bundle is refused", "FAILED", o_py, None)

    # 5. withholding: the caller knows there should be a third anchor
    s_py, rc_s, _ = run([sys.executable, os.path.join(HERE, "anchor_chain.py"), anchors,
                         "--expect-latest", "3"], tmp)
    record("a withheld anchor is called stale", "STALE", s_py, None)

    print("VERDICT: %s" % ("OK" if ok_all else "MISMATCH"))
    for name, expect, py, js, good in rows:
        print("  %-38s expect %-10s python %-10s node %-10s %s"
              % (name, expect, py, js if js is not None else "-", "ok" if good else "MISMATCH"))
    print("bundles: %s" % (bundles if keep else "(removed)"))
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok_all else 3


if __name__ == "__main__":
    sys.exit(main())
