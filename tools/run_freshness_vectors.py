"""Replay the two-run freshness vectors against both readers.

Each case is run as its own process-level scenario: build a temporary copy of
`examples/demo.uibc`, apply the overlay, point the reader at the state file (or
point it at nothing), then read the S19 line. Python and Node must both reach
the verdict `cases.json` records; a disagreement is a failure of this script,
not a note.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from uibc_core.verify import verify as python_verify  # noqa: E402

VEC = os.path.join(REPO, "conformance", "freshness")
NODE = shutil.which("node")


def load():
    with open(os.path.join(VEC, "cases.json"), encoding="utf-8") as fh:
        return json.load(fh)


def make_package(tmp, case, head):
    dst = os.path.join(tmp, "pkg")
    shutil.copytree(os.path.join(REPO, "examples", "demo.uibc"), dst)
    overlay = case.get("overlay")
    if overlay:
        mp = os.path.join(dst, "manifest.json")
        manifest = json.load(open(mp, encoding="utf-8"))
        fh = dict(overlay.get("freshness_head") or {})
        if fh.get("prev_head") == "HEAD_BEFORE":
            fh["prev_head"] = head
        if fh:
            manifest["freshness_head"] = fh
        open(mp, "w", encoding="utf-8").write(json.dumps(manifest, indent=1) + "\n")
    return dst


def pristine_state(tmp, case, tag):
    """One copy of the state per reader.

    A passing run records the observation, so the two readers must not share a
    file: the second would read the head the first just wrote and call a first
    observation a pass. That is exactly what the first replay of this vector did.
    """
    rel = case.get("state")
    if not rel:
        return None
    dst = os.path.join(tmp, "state-%s.json" % tag)
    shutil.copyfile(os.path.join(VEC, rel), dst)
    return dst


def python_verdict(pkg, state):
    rep = python_verify(pkg, state_file=state)
    rows = [c for c in rep["checks"] if c["id"] == "S19"]
    return (rows[0]["result"] if rows else "ABSENT"), (rows[0]["detail"] if rows else "")


def node_verdict(pkg, state):
    cmd = ["node", os.path.join(REPO, "tools", "verify-js", "verify.mjs"), pkg]
    if state:
        cmd += ["--freshness", state]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        rep = json.loads(out.stdout)
    except json.JSONDecodeError:
        return "UNPARSABLE", out.stdout[:80]
    rows = [c for c in rep["checks"] if c["id"] == "S19"]
    return (rows[0]["result"] if rows else "ABSENT"), (rows[0]["detail"] if rows else "")


def replay(use_node=True):
    doc = load()
    results = []
    for case in doc["cases"]:
        tmp = tempfile.mkdtemp(prefix="uibc-fresh-replay-")
        try:
            pkg = make_package(tmp, case, doc["head"])
            py_v, py_d = python_verdict(pkg, pristine_state(tmp, case, "py"))
            if use_node:
                nd_v, nd_d = node_verdict(pkg, pristine_state(tmp, case, "node"))
            else:
                nd_v, nd_d = "SKIPPED", ""
            ok = (py_v == case["expect"]) and (not use_node or nd_v == case["expect"])
            results.append({"id": case["id"], "expect": case["expect"],
                            "python": py_v, "node": nd_v, "ok": ok,
                            "python_detail": py_d, "node_detail": nd_d})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return results


def main():
    use_node = "--no-node" not in sys.argv
    rs = replay(use_node)
    as_json = "--json" in sys.argv
    bad = [r for r in rs if not r["ok"]]
    if as_json:
        print(json.dumps({"cases": rs, "ok": not bad}, ensure_ascii=False, indent=1))
    else:
        for r in rs:
            print("%-26s expect %-12s python %-12s node %-12s %s" % (
                r["id"], r["expect"], r["python"],
                r["node"] if use_node else "(skipped)", "ok" if r["ok"] else "MISMATCH"))
        print("%d case(s), %d mismatch(es)" % (len(rs), len(bad)))
        if bad:
            for r in bad:
                print("  %s: python=%s node=%s" % (r["id"], r["python_detail"][:80], r["node_detail"][:80]))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
