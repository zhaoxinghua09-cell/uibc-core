"""Two-run freshness vectors.

The profile vectors pinned a receipt to a verdict. Freshness (S19) cannot be
expressed as one package: the verdict depends on what the reader saw last time.
So the vector is a *pair*, and both halves are written down: the state file
before the run, the package overlay, and the verdict the reader must reach. A
single package with "expected: PASS" would be the exact overclaim this repo
refuses.

`--check` rebuilds everything and compares bytes without writing; plain run (or
`--write`) writes the files. Any edit to an expectation is made here, in code,
not in the JSON: the JSON is output.
"""
import hashlib
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from uibc_core.canonical import (checkpoint_head, evidence_root,  # noqa: E402
                                 index_metadata_digest, lifecycle_head)

DEMO = os.path.join(REPO, "examples", "demo.uibc")
OUT = os.path.join(REPO, "conformance", "freshness")
SUBJECT = "demo-agent-001"
AS_OF = "2026-11-29"


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def demo_head():
    """The checkpoint the sealed demo package computes to. Read, never invented."""
    idx = _json(os.path.join(DEMO, "evidence", "index.json"))
    entries = idx.get("entries", [])
    hashes = []
    for e in entries:
        with open(os.path.join(DEMO, "evidence", str(e["path"])), "rb") as fh:
            hashes.append(hashlib.sha256(fh.read()).hexdigest())
    lc = _json(os.path.join(DEMO, "lifecycle.json"))
    return checkpoint_head(lifecycle_head(lc.get("events", [])),
                           evidence_root(hashes),
                           index_metadata_digest(idx),
                           len(entries))


def state(subject, head, sequence=None):
    row = {"head": head}
    if sequence is not None:
        row["sequence"] = sequence
    return {"schema": "uibc-freshness/1", "subjects": {subject: row}}


def build():
    head = demo_head()
    states = {
        "empty.json": {"schema": "uibc-freshness/1", "subjects": {}},
        "after-first.json": state(SUBJECT, head),
        "seq-7.json": state(SUBJECT, head, 7),
        # A different head recorded at the same sequence number: the fork case.
        # It lives in the state file because the head is the thing being compared;
        # mutating the package instead only breaks S11 and the run stops early.
        "seq-7-other-head.json": state(SUBJECT, "sha256:" + "1" * 64, 7),
        "corrupt.json.txt": "{not json",
    }
    cases = [
        {"id": "01-first-observation", "state": "states/empty.json", "overlay": None,
         "expect": "INCONCLUSIVE",
         "why": "a first observation has nothing to compare against; a PASS here would "
                "assert the package is newer than something never seen"},
        {"id": "02-same-package-twice", "state": "states/after-first.json", "overlay": None,
         "expect": "PASS",
         "why": "same head as the recorded observation"},
        {"id": "03-no-state-no-line", "state": None, "overlay": None,
         "expect": "ABSENT",
         "why": "without a state file the check must not appear at all - an unearned PASS "
                "on an input nobody supplied is the failure mode this vector catches"},
        {"id": "04-regressed-sequence", "state": "states/seq-7.json",
         "overlay": {"freshness_head": {"sequence": 4}}, "expect": "FAIL",
         "why": "an older sequence presented as current is a rollback"},
        {"id": "05-fork-same-sequence", "state": "states/seq-7-other-head.json",
         "overlay": {"freshness_head": {"sequence": 7}},
         "expect": "FAIL",
         "why": "the state records one head at sequence 7 and the package presents another: "
                "a fork at the same number, which no later observation can resolve"},
        {"id": "06-prev-head-mismatch", "state": "states/seq-7.json",
         "overlay": {"freshness_head": {"sequence": 8, "prev_head": "sha256:" + "0" * 64}},
         "expect": "FAIL",
         "why": "claiming to descend from a head that was never recorded"},
        {"id": "07-advance-with-prev-head", "state": "states/seq-7.json",
         "overlay": {"freshness_head": {"sequence": 8, "prev_head": "HEAD_BEFORE"}},
         "expect": "PASS",
         "why": "a genuinely newer state that names the previous head"},
        {"id": "08-unreadable-state", "state": "states/corrupt.json.txt", "overlay": None,
         "expect": "FAIL",
         "why": "a state file that cannot be parsed is a failure to check, not a pass"},
    ]
    return {"schema": "uibc-freshness-vectors/1", "as_of": AS_OF,
            "package": "examples/demo.uibc", "subject": SUBJECT,
            "head": head, "cases": cases}, states


README = """# 新鲜度向量（两跑成对，不是单包）

由 `python tools/build_freshness_vectors.py --write` 生成；`--check` 只比对不写。
每个案例是「状态文件 + 包覆盖 + 必须得到的判定」三件：S19 的判定取决于读者上一次看见了什么，
单包向量表达不了。`HEAD_BEFORE` 由重放器替换成下面这个 head。

head = `{head}`

| 案例 | 状态 | 覆盖 | 期望 | 为什么 |
|---|---|---|---|---|
{rows}
"""


def render(doc, states):
    files = {"cases.json": json.dumps(doc, ensure_ascii=False, indent=1) + "\n"}
    for name, body in states.items():
        body_text = body if name.endswith(".txt") else json.dumps(body, indent=1) + "\n"
        files[os.path.join("states", name)] = body_text
    rows = "\n".join(
        "| %s | `%s` | `%s` | **%s** | %s |" % (
            c["id"], c["state"] or "—",
            json.dumps(c["overlay"], ensure_ascii=False) if c["overlay"] else "—",
            c["expect"], c["why"])
        for c in doc["cases"])
    files["README.md"] = README.format(head=doc["head"], rows=rows)
    return files


def main():
    doc, states = build()
    files = render(doc, states)
    check = "--check" in sys.argv
    drift = []
    for rel, body in files.items():
        path = os.path.join(OUT, rel)
        if check:
            if not os.path.exists(path):
                drift.append("%s missing" % rel)
                continue
            with open(path, encoding="utf-8") as fh:
                if fh.read() != body:
                    drift.append("%s differs" % rel)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
    if check:
        if drift:
            print("DRIFT: " + "; ".join(drift))
            return 1
        print("freshness vectors match the generator (%d files)" % len(files))
        return 0
    print("wrote %d file(s) under conformance/freshness" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
