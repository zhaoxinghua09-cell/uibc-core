"""The tree digest has a second implementation, and the two must agree.

`tools/outsider_rerun.py` produces `tree_sha256` and `content_sha256`; the receipt
that the gate leans on carries both. This script recomputes them with
`tools/verify-js/tree-digest.mjs` - Node's standard library only, no Python, no
npm, no import of the thing it is checking - and compares.

  python tools/tree_digest_second_impl.py            # compare, long form
  python tools/tree_digest_second_impl.py --json     # machine readable
  python tools/tree_digest_second_impl.py --check    # exit 1 unless TREE OK

Membership is handed over, not re-derived: the Python side passes its own file
list (NUL separated) so the two implementations cannot pass by agreeing on a
different set of files. The listing is already covered by the receipt itself;
what this adds is that the *number* is not one program's private convention.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE_SCRIPT = os.path.join(HERE, "tools", "verify-js", "tree-digest.mjs")


def _load_rerun():
    spec = importlib.util.spec_from_file_location(
        "outsider_rerun", os.path.join(HERE, "tools", "outsider_rerun.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def node_binary():
    return os.environ.get("NODE") or shutil.which("node")


def files_here(rerun, root):
    out = []
    for rel in rerun.tracked_files(root):
        if rel in rerun.GENERATED:
            continue
        out.append(rel)
    return out


def second_impl(root, files, node=None):
    """Ask Node for both digests over exactly this file list."""
    node = node or node_binary()
    if not node:
        raise RuntimeError("no node binary: set NODE or put node on PATH")
    fd, listfile = tempfile.mkstemp(prefix="uibc-tree-files-", suffix=".nul")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write("\0".join(files))
        proc = subprocess.run([node, NODE_SCRIPT, "--root", root, "--files-from", listfile],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=900)
    finally:
        os.unlink(listfile)
    if proc.returncode != 0:
        raise RuntimeError("node failed: " + (proc.stderr or proc.stdout).strip()[:300])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def compare(root=HERE, files=None):
    rerun = _load_rerun()
    files = files if files is not None else files_here(rerun, root)
    tree, count = rerun.tree_digest(root, files)
    content, ccount = rerun.content_digest(root, files)
    other = second_impl(root, files)
    rows = [
        ("files", count, other.get("files")),
        ("tree_sha256", tree, other.get("tree_sha256")),
        ("content_sha256", content, other.get("content_sha256")),
    ]
    if ccount != count:
        rows.append(("content_files", ccount, other.get("files")))
    bad = [(name, py, js) for name, py, js in rows if py != js]
    return {"ok": not bad, "rows": rows, "disagreements": [
        {"field": n, "python": p, "node": j} for n, p, j in bad]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true", help="exit 1 unless the two agree")
    args = ap.parse_args()
    out = compare()
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for name, py, js in out["rows"]:
            print(f"{'OK  ' if py == js else 'DIFF'} {name}: python {str(py)[:16]} / node {str(js)[:16]}")
        print("VERDICT: TREE OK" if out["ok"] else
              "VERDICT: TREE DISAGREE (" + ", ".join(d["field"] for d in out["disagreements"]) + ")")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
