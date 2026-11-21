#!/usr/bin/env python3
"""What each verifier tells you when it says no.

A verdict of FAIL is the cheapest thing a verifier can produce. The question a
person debugging an agent needs answered is *which* object failed and *what*
was expected there. This tool applies the same six kinds of damage to our
package and to a competing verifier's capsule, and prints what each one says.

The comparison is honest in both directions: it reports when a competitor is
more specific than we are, and it marks a stage "unavailable" rather than
scoring it, when their package cannot be imported.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

CLEAN = os.path.join(_REPO, "fixtures", "clean.uibc")


def _full_package():
    """A package with every feature populated, so that a check which needs a
    signature or an anchor actually runs instead of returning INCONCLUSIVE.
    Built through the audit tool's own builder, so both sides of this
    comparison see the same artifact the red-team suite uses."""
    sys.path.insert(0, os.path.join(_REPO, "tools"))
    try:
        import outsider_audit as oa
        for name in ("build_v11", "build_ext", "build_s16", "build_ckpt"):
            fn = getattr(oa, name, None)
            if fn is None:
                return CLEAN, "outsider_audit has no %s" % name
        tmp = tempfile.mkdtemp(prefix="full-")
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(CLEAN, pkg)
        for name in ("build_v11", "build_ext", "build_s16", "build_ckpt"):
            getattr(oa, name)(pkg)
        return pkg, None
    except Exception as e:  # noqa: BLE001
        return CLEAN, "%s: %s" % (type(e).__name__, e)


# ---------------------------------------------------------------- our side
def _uibc_cases(pkg):
    """Yield (attack, mutated pkg path) built from a copy of `pkg`."""
    from uibc_core.verify import verify

    def flip(path):
        f = os.path.join(path, "evidence", "files")
        victim = sorted(os.listdir(f))[0]
        p = os.path.join(f, victim)
        b = bytearray(open(p, "rb").read())
        b[0] = b[0] ^ 0xFF
        open(p, "wb").write(bytes(b))

    def delete(path):
        f = os.path.join(path, "evidence", "files")
        os.remove(os.path.join(f, sorted(os.listdir(f))[0]))

    def add(path):
        open(os.path.join(path, "evidence", "files", "extra.bin"), "wb").write(b"x")

    def impossible(path):
        p = os.path.join(path, "lifecycle.json")
        d = json.load(open(p, encoding="utf-8"))
        ev = d.get("events") or d.get("entries") or []
        if ev:
            ev[0]["timestamp"] = "2026-02-30T00:00:00Z"
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def metadata(path):
        p = os.path.join(path, "evidence", "index.json")
        d = json.load(open(p, encoding="utf-8"))
        items = d.get("files") or d.get("entries") or []
        if items:
            items[0]["note"] = "edited after the fact"
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def truncate(path):
        p = os.path.join(path, "evidence", "index.json")
        d = json.load(open(p, encoding="utf-8"))
        key = "files" if "files" in d else "entries"
        d[key] = d[key][:-1]
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    cases = [("flip one byte in evidence", flip),
             ("delete one evidence file", delete),
             ("add an undeclared file", add),
             ("impossible date (2026-02-30)", impossible),
             ("edit index metadata", metadata),
             ("drop the last index entry", truncate)]
    for name, fn in cases:
        tmp = tempfile.mkdtemp(prefix="cmp-")
        dst = os.path.join(tmp, "pkg")
        shutil.copytree(pkg, dst)
        try:
            fn(dst)
            r = verify(dst)
            failed = [(c["id"], c["detail"], c.get("basis") or {})
                      for c in r["checks"] if c["result"] == "FAIL"]
            cites = sorted({(b.get("citation") or "").strip()
                            for _, _, b in failed if b.get("citation")})
            yield {"attack": name, "verdict": r["result"],
                   "ids": [i for i, _, _ in failed],
                   "first": failed[0][1] if failed else r.get("statement", ""),
                   "n_reasons": len(failed), "citations": cites}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------- their side
def _aac_cases():
    try:
        sys.path.insert(0, "/tmp/cmpv/lib/python3.12/site-packages")
        import agent_action_capsule as a
        from agent_action_capsule import verify
        from agent_action_capsule.canonical import compute_capsule_id
    except Exception as e:  # noqa: BLE001
        return iter([]), "agent-action-capsule not importable (%s)" % type(e).__name__

    body = dict(spec_version=a.DEFAULT_SPEC_VERSION, format_version=a.DEFAULT_FORMAT_VERSION,
                action_id="act-1", action_type="fyi", operator="did:web:alice",
                developer="did:web:dev", timestamp="2026-11-18T00:00:00Z",
                domain="D1", canonicalization_id="jcs")
    good = {**body, "capsule_id": compute_capsule_id(body)}

    def flip(d):
        d["action_id"] = "act-2"

    def delete(d):
        """That format has no set of evidence files, so 'delete one' has no
        counterpart. Marking it n/a is more honest than inventing a
        lookalike."""
        raise _NotApplicable("该格式没有证据文件集，只有一个 capsule")

    def add(d):
        raise _NotApplicable("该格式没有可另加的成员集合，未声明字段即被 capsule_id 掩盖")

    def impossible(d):
        d["timestamp"] = "2026-02-30T00:00:00Z"

    def metadata(d):
        d["domain"] = "NOPE"

    def truncate(d):
        del d["operator"]

    cases = [("flip one byte in evidence", flip),
             ("delete one evidence file", delete),
             ("add an undeclared file", add),
             ("impossible date (2026-02-30)", impossible),
             ("edit index metadata", metadata),
             ("drop the last index entry", truncate)]
    return [(n, fn, good) for n, fn in cases], None


class _NotApplicable(Exception):
    pass


def _run_aac():
    cases, why = _aac_cases()
    if why:
        return [], why
    import agent_action_capsule as a
    from agent_action_capsule import verify
    out = []
    for name, fn, good in cases:
        d = dict(good)
        try:
            fn(d)
        except _NotApplicable as e:
            out.append({"attack": name, "verdict": "n/a", "ids": [],
                        "first": str(e), "n_reasons": 0})
            continue
        r = verify(d)
        errs = [f for f in r.findings if getattr(f, "severity", "") == "error"]
        out.append({"attack": name, "verdict": "FAIL" if not r.ok else "PASS",
                    "ids": [getattr(f, "code", "?") for f in errs],
                    "first": (getattr(errs[0], "code", "") + ": " +
                              getattr(errs[0], "detail", "")) if errs else "",
                    "n_reasons": len(errs)})
    return out, None


def build():
    pkg, why_pkg = _full_package()
    ours = list(_uibc_cases(pkg))
    theirs, why = _run_aac()
    return {"ours": {"name": "uibc-core (this repo)", "cases": ours,
                     "package_note": why_pkg},
            "theirs": {"name": "agent-action-capsule 0.17.0", "cases": theirs,
                       "unavailable": why},
            "dimensions": ["verdict", "machine-readable id", "first reason text",
                           "how many reasons"]}


def render(d):
    out = ["# 判定之外，它还说了什么", "",
           "同一批六种破坏，分别施加到本仓库的包与竞品的 capsule。"
           "比的是**同一个 FAIL 之后的信息量**：能不能说出哪一项、哪个对象、期望什么。", ""]
    out += ["| 攻击 | 我们：判定 | 我们：检查项 | 我们：依据 | 我们：一句原因 | 他们：判定 | 他们：错误码 | 他们：一句原因 |",
            "|---|---|---|---|---|---|---|---|"]
    theirs = {c["attack"]: c for c in d["theirs"]["cases"]}
    for c in d["ours"]["cases"]:
        t = theirs.get(c["attack"])
        cite = ", ".join(c.get("citations") or []) or "（自定，无依据可引）"
        row = ["%s | %s | %s | %s | %s" % (c["attack"], c["verdict"],
                 ", ".join(c["ids"]) or "—", cite,
                 (c["first"] or "").replace("|", "/")[:80])]
        if t and t["verdict"] == "n/a":
            row.append("n/a | — | %s" % (t["first"] or "")[:90])
        elif t:
            row.append("%s | %s | %s" % (t["verdict"], ", ".join(t["ids"]) or "—",
                                         (t["first"] or "").replace("|", "/")[:90]))
        else:
            row.append("不可用 | — | —")
        out.append("| " + " | ".join(row) + " |")
    out.append("")
    common = [c["attack"] for c in d["ours"]["cases"]
              if any(t["attack"] == c["attack"] and t["verdict"] != "n/a"
                     for t in d["theirs"]["cases"])]
    ours_n = sum(c["n_reasons"] for c in d["ours"]["cases"] if c["attack"] in common)
    if d["theirs"]["cases"]:
        theirs_n = sum(c["n_reasons"] for c in d["theirs"]["cases"]
                       if c["attack"] in common)
        out.append("在双方语义都成立的 %d 类攻击下，我们共报出 **%d** 条具体原因，"
                   "他们报出 **%d** 条。" % (len(common), ours_n, theirs_n))
    else:
        out.append("六种攻击下，我们共报出 **%d** 条具体原因；对方不可用（%s）。"
                   % (ours_n, d["theirs"].get("unavailable")))
    out.append("")
    out.append("## 这一轮试过、又撤回的改动\n")
    out.append("把「`evidence/` 下出现未声明文件即判 FAIL」写进 S1，跑测试时"
               "**十几个既有包全部失败**——因为这个格式自己就把锚定事件、策略件、"
               "收据链放在 `evidence/` 下。这说明它不是一处补丁，而是一次格式版本"
               "变更，已原样撤回。所以上表第二类攻击在这里是 `INCONCLUSIVE`，"
               "**这是我们已知的缺口，不是对比的胜利**。\n")
    out.append("## 这份对比不能说明什么\n")
    out.append("- 两种格式不同，六个攻击只是语义对齐，不是逐字节等价。")
    out.append("- 竞品在每一条 finding 里都写 `§5.1` 这样的条款号；我们现在每条"
               "失败原因也带 `basis`（`direct`/`related` 有引文，`none` 明确留空），"
               "但**只在结构化字段里**，人眼睛看到的那句话仍然没有条款号。这是"
               "还差的半步，写论文时照实写。")
    out.append("- 次数多不等于更好；一条能定位到字节的原因，胜过十条泛泛的拒绝。")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = build()
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else render(d))


if __name__ == "__main__":
    main()
