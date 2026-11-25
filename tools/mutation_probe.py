"""Mutation probe: does the reference verifier actually catch one-field changes?

The corpus contains 30 *designed* failures. A corpus says nothing about the
mutations nobody thought to design. This tool takes the clean package and applies
single-field mutations of its own, then asks two questions per mutant:

  killed      — does the overall verdict change from PASS to FAIL?
  attributed  — is the check that was meant to catch it among the failing checks?

A survivor (not killed) is a blind spot in the reference verifier. A mutant that
is killed but not attributed is a check that fires for the wrong reason — the
verdict is right and the reason is wrong, which is how a corpus quietly stops
being useful.

Run: python tools/mutation_probe.py            (writes out/mutation_probe.json)
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from uibc_core.cli import verify as ref_verify          # noqa: E402
sys.path.insert(0, os.path.join(REPO, "tools"))
import oracle_check as oc                              # noqa: E402  (reseal only)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def dump(p, obj):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def flip_hex(s, pos=0):
    """Change one hex character to a different valid hex character."""
    if not s:
        return "0"
    old = s[pos]
    new = "1" if old != "1" else "0"
    return s[:pos] + new + s[pos + 1:]


# --- mutation catalogue: (name, intended check, description, fn(root)) --------
def m_evidence_byte(root):
    p = os.path.join(root, "evidence", "files")
    f = sorted(os.listdir(p))[0]
    fp = os.path.join(p, f)
    with open(fp, "rb") as fh:
        data = fh.read()
    with open(fp, "wb") as fh:
        fh.write(data[:-1] + (b"X" if data[-1:] != b"X" else b"Y"))


def m_index_hash(root):
    p = os.path.join(root, "evidence", "index.json")
    d = load(p)
    d["entries"][0]["content_hash"] = flip_hex(d["entries"][0]["content_hash"][7:], 0).join(["sha256:", ""])
    dump(p, d)


def m_index_type(root):
    p = os.path.join(root, "evidence", "index.json")
    d = load(p)
    d["entries"][0]["type"] = "unknown-type"
    dump(p, d)


def m_duplicate_entry(root):
    p = os.path.join(root, "evidence", "index.json")
    d = load(p)
    d["entries"].append(dict(d["entries"][0]))
    dump(p, d)


def m_counts(root):
    p = os.path.join(root, "manifest.json")
    d = load(p)
    for k in ("evidence_count", "n_evidence"):
        if k in d:
            d[k] = d[k] + 1
            dump(p, d)
            return
    d["evidence_counts"] = {"n": 99}
    dump(p, d)


def m_agent_id(root):
    p = os.path.join(root, "manifest.json")
    d = load(p)
    d["agent_id"] = "someone-else"
    dump(p, d)


def m_root(root):
    p = os.path.join(root, "manifest.json")
    d = load(p)
    d["evidence_root"] = flip_hex(d["evidence_root"][7:], 0).join(["sha256:", ""])
    dump(p, d)


def m_extra_root_file(root):
    with open(os.path.join(root, "stray.txt"), "w", encoding="utf-8") as f:
        f.write("undeclared\n")


def m_delete_evidence(root):
    p = os.path.join(root, "evidence", "files")
    f = sorted(os.listdir(p))[0]
    os.unlink(os.path.join(p, f))


def m_lifecycle_state(root):
    p = os.path.join(root, "lifecycle.json")
    d = load(p)
    ev = d.get("events", [])
    if ev:
        ev[0]["event_type"] = "NOT_A_REAL_EVENT"
    dump(p, d)


def m_lifecycle_drop(root):
    p = os.path.join(root, "lifecycle.json")
    d = load(p)
    d["events"] = [e for e in d.get("events", [])[:-1]]
    dump(p, d)


def m_index_metadata(root):
    """Add a top-level member the index schema never declared.

    This one has no "intended" check on purpose: the question it asks is whether
    anything in the 19 checks constrains members of evidence/index.json outside
    the sealed digest. If nothing does, an unsigned field can ride along in a
    package that verifies PASS, and any reader that trusts it is reading a value
    no one checked.
    """
    p = os.path.join(root, "evidence", "index.json")
    d = load(p)
    d["generated_at"] = "1970-01-01T00:00:00Z"
    dump(p, d)


CATALOGUE = [
    ("evidence-byte",   "S4",  "one byte of an evidence file changed",      m_evidence_byte),
    ("index-hash",      "S4",  "one hex char of an indexed content_hash",   m_index_hash),
    ("index-type",      "S4",  "an evidence type the format does not define", m_index_type),
    ("index-duplicate", "S12", "the same entry listed twice",               m_duplicate_entry),
    ("manifest-count",  "S5",  "the declared evidence count is wrong",      m_counts),
    ("manifest-agent",  "S2",  "manifest agent_id disagrees with identity", m_agent_id),
    ("manifest-root",   "S5",  "the declared evidence root is wrong",       m_root),
    ("extra-root-file", "S1",  "a file at the root the index never declared", m_extra_root_file),
    ("evidence-removed", "S4", "an indexed evidence file is gone",          m_delete_evidence),
    ("lifecycle-state", "S3",  "an event_type the state machine does not know", m_lifecycle_state),
    ("lifecycle-drop",  "S3",  "the closing lifecycle event is missing",    m_lifecycle_drop),
    ("index-extra-field", "（无检查声明此约束）", "an undeclared member added to evidence/index.json", m_index_metadata),
]


def run_one(name, check, fn, src, key):
    """Mutate, then re-seal with the owner key before verifying.

    Re-sealing is the whole point: if the seal is left broken, S6 answers first
    and every mutant looks caught. A mutation test that only measures "does the
    seal notice bytes changed" measures nothing about the checks. After re-sealing,
    the package is internally consistent except for the one mutated fact, so the
    check that fires is the one that was supposed to catch it.
    """
    tmp = tempfile.mkdtemp(prefix="mut-")
    pkg = os.path.join(tmp, "pkg")
    shutil.copytree(src, pkg)
    try:
        fn(pkg)
    except Exception as e:                                    # noqa: BLE001
        return {"mutation": name, "intended": check, "error": "setup: %s" % e}
    try:
        oc.reseal(pkg, key)
    except Exception as e:                                    # noqa: BLE001
        return {"mutation": name, "intended": check, "error": "reseal: %s" % e}
    try:
        rep = ref_verify(pkg, key=key)
    except Exception as e:                                    # noqa: BLE001
        return {"mutation": name, "intended": check, "error": "verify: %s" % e}
    failing = [c["id"] for c in rep["checks"] if c["result"] == "FAIL"]
    incon = [c["id"] for c in rep["checks"] if c["result"] == "INCONCLUSIVE"]
    return {
        "mutation": name, "intended": check, "verdict": rep["result"],
        "failing": failing, "inconclusive": incon,
        "killed": rep["result"] != "PASS",
        "attributed": check in failing,
        "caught_by": failing or incon,
        "unsupported": rep.get("unsupported", []),
    }


def main():
    src = os.path.join(REPO, "conformance", "oracle", "cases", "oracle-clean")
    keys = json.load(open(os.path.join(REPO, "conformance", "oracle", "keys.json"),
                          encoding="utf-8"))["keys"]
    key = bytes.fromhex(keys["oracle-clean"])
    rows = [run_one(n, c, f, src, key) for n, c, _d, f in CATALOGUE]
    ok = [r for r in rows if "error" not in r]
    summary = {
        "mutants": len(rows),
        "killed": sum(1 for r in ok if r["killed"]),
        "attributed": sum(1 for r in ok if r["attributed"]),
        "survivors": [r["mutation"] for r in ok if not r["killed"]],
        "misattributed": [r["mutation"] for r in ok if r["killed"] and not r["attributed"]],
        "errors": [r for r in rows if "error" in r],
        "as_of": "2026-11-25",
        "source": "conformance/oracle/cases/oracle-clean",
    }

    out_dir = os.path.join(REPO, "out")
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"summary": summary, "rows": rows},
              open(os.path.join(out_dir, "mutation_probe.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lines = ["# 变异探针（参考验证器单字段变异）", "",
             f"源包 `{summary['source']}`；变异 {summary['mutants']} 个，"
             f"杀掉 {summary['killed']}，归因正确 {summary['attributed']}。", "",
             "| 变异 | 目标检查 | verdict | 失败集 | killed | attributed |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['mutation']} | {r['intended']} | ERROR | {r['error'][:40]} | — | — |")
            continue
        lines.append("| {m} | {c} | {v} | {f} | {k} | {a} |".format(
            m=r["mutation"], c=r["intended"], v=r["verdict"],
            f=",".join(r["failing"]) or "—",
            k="是" if r["killed"] else "**否**", a="是" if r["attributed"] else "**否**"))
    with open(os.path.join(out_dir, "mutation_probe.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps({k: summary[k] for k in
                      ("mutants", "killed", "attributed", "survivors", "misattributed")},
                     ensure_ascii=False))
    return 0 if not summary["survivors"] else 1


if __name__ == "__main__":
    sys.exit(main())
