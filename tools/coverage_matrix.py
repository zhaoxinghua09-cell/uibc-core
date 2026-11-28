"""Which checks each reader actually runs -- read off the source, not off prose.

Every "N/19" claim in this repository used to be typed by hand, and one of them
was wrong (the Node reader was described as 10/19 while its source already ran
S3 and S9). This tool derives the sets from the files that execute, and can
render `docs/READER-COVERAGE.md` from them (`--write`).

  reference   uibc_core/verify.py        -- record("Sx", ...) and {"id": "Sx"}
  node        tools/verify-js/verify.mjs -- note("Sx", ...) in code, not comments
  independent independent_verifier/iverify.py -- via the V->S map in cross_impl

For the independent reader two numbers matter and they are not the same: how
many distinct S-checks its outcomes name, and how many outcomes (V1..V10) it
reports. Its value is that it is independent, so it is not "improved" here; the
gap is stated instead.
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(REPO, "docs", "READER-COVERAGE.md")

REASONS = {
    "S19": "needs a freshness state file the reader does not hold",
    "S16": "needs a timestamp token the reader does not hold",
    "S10": "closure declaration: the independent reader folds it into V7",
    "S13": "Merkle inclusion: the independent reader has no tree code",
    "S17": "receipt chain: outside the independent reader's scope",
    "S18": "policy artefact: outside the independent reader's scope",
}


def reference_ids():
    text = open(os.path.join(REPO, "uibc_core/verify.py"), encoding="utf-8").read()
    return ({int(m) for m in re.findall(r'record\(\s*"S(\d+)"', text)} |
            {int(m) for m in re.findall(r'"id":\s*"S(\d+)"', text)})


def node_ids():
    text = "".join(l for l in open(os.path.join(REPO, "tools/verify-js/verify.mjs"),
                                  encoding="utf-8") if not l.lstrip().startswith("//"))
    return ({int(m) for m in re.findall(r'note\(\s*"S(\d+)"', text)} |
            {int(m) for m in re.findall(r'inconclusive\(\s*"S(\d+)"', text)})


def independent():
    """Two numbers, both read off source, and they are not the same.

    `V_TO_S` in tools/cross_impl.py maps the independent reader's S-shaped
    check names onto the reference ids (it is written as name->name, 15 distinct
    S ids). The reader's own published outcomes are V1..V10, counted in
    independent_verifier/iverify.py. Reporting one number for both was how "10/19"
    and "15/19" ended up meaning different things in different files.
    """
    text = open(os.path.join(REPO, "tools/cross_impl.py"), encoding="utf-8").read()
    m = re.search(r"V_TO_S\s*=\s*\{([^}]*)\}", text)
    if not m:
        return set(), 0, "no V_TO_S map found in tools/cross_impl.py"
    s_ids = {int(x) for x in re.findall(r'"S(\d+)"', m.group(1))}
    iver = open(os.path.join(REPO, "independent_verifier/iverify.py"), encoding="utf-8").read()
    v_ids = len(set(re.findall(r'"V\d+"', iver)))
    return s_ids, v_ids, None


def rows():
    full = set(range(1, 20))
    out = []
    for name, fn, src in (("reference", reference_ids, "uibc_core/verify.py"),
                          ("node", node_ids, "tools/verify-js/verify.mjs")):
        got = fn()
        out.append({"reader": name, "source": src, "covered": len(got & full),
                    "total": 19, "missing": sorted(full - got),
                    "why": {str(m): REASONS.get("S%d" % m, "no reason recorded")
                            for m in sorted(full - got)}})
    s_ids, v_ids, note = independent()
    out.append({"reader": "independent", "source": "tools/cross_impl.py (V->S map)",
                "covered": len(s_ids & full), "total": 19, "outcomes": v_ids,
                "missing": sorted(full - s_ids),
                "why": {str(m): REASONS.get("S%d" % m, "no reason recorded")
                        for m in sorted(full - s_ids)},
                **({"note": note} if note else {})})
    return out


def render(rs):
    lines = ["# 读者覆盖面（现读，不是手写）", "",
             "由 `python tools/coverage_matrix.py --write` 生成。数字来自三个读者自己的源码：",
             "参考实现数 `record(\"Sx\")` 与 `{\"id\": \"Sx\"}`，Node 读者数代码里的 `note(\"Sx\")` 与 `inconclusive(\"Sx\")`（注释不计），",
             "独立读者取自 `tools/cross_impl.py` 的 V→S 映射。", "",
             "| 读者 | 源码 | 覆盖 | 缺 | 缺的原因 |",
             "|---|---|---|---|---|"]
    for r in rs:
        miss = ", ".join("S%d" % m for m in r["missing"]) or "—"
        why = "；".join("%s: %s" % (k, v) for k, v in r["why"].items()) or "—"
        cov = "%d/%d" % (r["covered"], r["total"])
        if "outcomes" in r:
            cov += "（%d 条自有结论）" % r["outcomes"]
        lines.append("| %s | `%s` | %s | %s | %s |" % (r["reader"], r["source"], cov, miss, why))
    lines += ["", "**读法**：Node 读者现在 19/19，但其中 S19 与参考实现的 S16/S19 都只能在**读者自己持有的外部输入**",
              "在场时才跑（`--freshness` 状态文件、RFC 3161 时间戳 token）；不传就不是「通过了」，是「根本没跑」——",
              "Node 实现里这两条在不传输入时连一行结果都不发，宁可缺席也不发一个无人核对过的 PASS。",
              "独立读者的价值在于它与参考实现不同源；它缺的四项不补，补齐就等于把它改成参考实现的副本。", ""]
    return "\n".join(lines)


def main():
    rs = rows()
    if "--write" in sys.argv:
        open(DOC, "w", encoding="utf-8", newline="\n").write(render(rs))
        print("written:", DOC)
        return 0
    print(json.dumps({"reference_total": 19, "readers": rs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
