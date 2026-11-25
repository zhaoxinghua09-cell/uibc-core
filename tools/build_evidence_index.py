"""Map every check to the things that can prove it exists and works.

After twenty-odd rounds the repository holds a lot of claims: eighteen checks,
four red-team stages, an auditor with its own self-test, cross-implementation
exports, a distributable kit. What it did not hold was one page that answers
"where do I look to see that this works?" -- a reviewer had to read a long
essay to find out.

This builds that page from the code rather than from memory, so it cannot
drift: check ids come off `verify.py`, the tests that mention each id come off
a scan of `tests/`, the red-team mentions come off `tools/outsider_audit.py`.

    python3 tools/build_evidence_index.py            # human table
    python3 tools/build_evidence_index.py --json     # machine-readable
    python3 tools/build_evidence_index.py --write     # update docs/EVIDENCE-INDEX.md

`--write` exists because the page was maintained by redirecting stdout, so adding a
single test left the committed count one behind and two tests failed on every round
that touched the suite (twice by 2026-11-22). The page is prose that no builder
regenerates, so it needs a writer that is a command, not a shell habit.

The last section is the honest one: what has NO evidence, and why.
"""

import json
import os
import re
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

CHECK_RE = re.compile(r'"id":\s*"(S\d+)"\s*,\s*"name":\s*"([^"]+)"')
RECORD_RE = re.compile(r'record\(\s*"(S\d+)"\s*,\s*"([^"]+)"')


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def checks_declared():
    """Every check the verifier can emit, with its name."""
    src = _read(os.path.join(_REPO, "uibc_core", "verify.py"))
    found = {}
    for cid, name in CHECK_RE.findall(src):
        found.setdefault(cid, name)
    for cid, name in RECORD_RE.findall(src):
        found.setdefault(cid, name)
    return found


def checks_reached():
    """Which checks the shipped package actually reaches, and why it stops."""
    from uibc_core.verify import verify
    pkg = os.path.join(_REPO, "fixtures", "clean.uibc")
    result = verify(pkg)
    ids = [c["id"] for c in result.get("checks", [])]
    return ids, result.get("result")


SELF = os.path.join("docs", "EVIDENCE-INDEX.md")


def mentions(cid, roots, pattern=None):
    """Files under the given roots that name this check id.

    The generated index is excluded: it names every check, so counting it would
    make each rebuild inflate the numbers it reports.
    """
    pat = re.compile(pattern or (r"\b%s\b" % cid))
    hits = []
    for root in roots:
        base = os.path.join(_REPO, root)
        if os.path.isfile(base):
            if os.path.relpath(base, _REPO).replace("\\", "/") == \
                    SELF.replace("\\", "/"):
                continue
            if pat.search(_read(base)):
                hits.append(os.path.relpath(base, _REPO).replace("\\", "/"))
            continue
        for dirpath, _dirs, names in os.walk(base):
            for name in names:
                if not name.endswith(".py") and not name.endswith(".md"):
                    continue
                full = os.path.join(dirpath, name)
                if os.path.relpath(full, _REPO).replace("\\", "/") == \
                        SELF.replace("\\", "/"):
                    continue
                try:
                    if pat.search(_read(full)):
                        hits.append(os.path.relpath(full, _REPO)
                                    .replace("\\", "/"))
                except OSError:
                    continue
    return sorted(hits)


def red_team_coverage():
    """Which check caught which attack, measured by running the audit.

    A textual mention of "S7" in the auditor proves nothing about whether an
    attack reached it -- the first version of this index made exactly that
    mistake and reported S3 as uncovered when the impossible-calendar-date case
    had been catching it all along.
    """
    try:
        tools_dir = os.path.join(_REPO, "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import outsider_audit as oa
        result = oa.run_all(os.path.join(_REPO, "fixtures", "clean.uibc"), None)
    except Exception as exc:                       # noqa: BLE001
        return {}, "unavailable: %s: %s" % (type(exc).__name__, exc)
    coverage = {}
    for stage in result.values():
        if not isinstance(stage, dict) or "rows" not in stage:
            continue
        for row in stage["rows"]:
            for cid in row.get("failed_checks") or []:
                coverage.setdefault(cid, []).append(row["name"])
    return coverage, None


def build():
    declared = checks_declared()
    reached, verdict = checks_reached()
    coverage, coverage_error = red_team_coverage()
    rows = []
    for cid in sorted(declared, key=lambda c: int(c[1:])):
        rows.append({
            "id": cid,
            "name": declared[cid],
            "reached_by_shipped_package": cid in reached,
            "tests": mentions(cid, ["tests"]),
            "red_team": coverage.get(cid, []),
            "docs": mentions(cid, ["docs"]),
        })
    gaps = [r["id"] for r in rows if not r["tests"]]
    unwitnessed = [r["id"] for r in rows if not r["red_team"]]
    return {
        "check_count": len(rows),
        "shipped_package_verdict": verdict,
        "shipped_package_reaches": reached,
        "rows": rows,
        "no_test": gaps,
        "no_red_team_mention": unwitnessed,
        "red_team_measurement_error": coverage_error,
        "note": "red_team is measured, not grepped: the audit is run and each "
                "row's failed_checks recorded",
    }


def render(index):
    lines = []
    lines.append("# 证据索引（由 `tools/build_evidence_index.py` 生成）\n")
    lines.append("每条检查对应到：验证器里的定义、覆盖它的测试、指向它的红队攻击、以及"
                 "提到它的文档。**重新生成即可复核**，不会随记忆漂移。\n")
    lines.append("**测试套件：%d 个用例**（静态计数：`tests/` 下 `def test_*` 的个数，跨平台一致；"
                 "这是**源码里有几个测试函数**，不等于运行期收集到的用例数——pytest 会把参数化展开成多条"
                 "（实跑更多），平台跳过又会少一些。别处只引用本页，不再抄写这个数字）。\n" % suite_size())
    lines.append("")
    lines.append("| 检查 | 名称 | 出厂包是否走到 | 测试 | 红队 | 文档 |")
    lines.append("|---|---|---|---|---|---|")
    for r in index["rows"]:
        reach = "是" if r["reached_by_shipped_package"] else "否"
        tests = len(r["tests"])
        rt = len(r["red_team"])
        docs = len(r["docs"])
        lines.append("| %s | %s | %s | %d | %d | %d |"
                     % (r["id"], r["name"], reach, tests, rt, docs))
    lines.append("")
    lines.append("出厂包判定：`%s`，走到 %d/%d 项（未签名的包停在 S6，后面不越过去）。"
                 % (index["shipped_package_verdict"],
                    len(index["shipped_package_reaches"]), index["check_count"]))
    lines.append("")
    if index["no_test"]:
        lines.append("**没有任何测试提到的检查**：%s" % ", ".join(index["no_test"]))
    else:
        lines.append("**每项检查都至少有一个测试文件提到**。")
    if index["no_red_team_mention"]:
        lines.append("\n**红队实测中从未被任何攻击抓到的检查**：%s"
                     % ", ".join(index["no_red_team_mention"]))
    for r in index["rows"]:
        if r["id"] == "S0":
            lines.append("（S0 不是检查：它是验证器自身异常时的兜底条目，"
                         "没有可构造的攻击，因此不计入缺口。）")
    lines.append("\n## 这份索引不能证明什么\n")
    for line in [
        "提到 ≠ 覆盖：一个测试文件里出现 `S4` 不代表它真的构造了越界符号链接。",
        "「出厂包是否走到」只反映未签名包的路径；后面的检查由红队阶段的合成包覆盖，不在这里。",
        "**外部第三方验证：2 次执行（不是利益独立）** —— 以 `docs/EXTERNAL-NODES.md` 为唯一真源；本索引其余各行都由我们自己产出。",
    ]:
        lines.append("- " + line)
    return "\n".join(lines) + "\n"


def suite_size():
    """How many test cases the suite contains — counted statically, not typed.

    Runtime discovery was the wrong instrument: the same commit counts 1157 on
    Linux and 1156 on Windows, so whatever number the page carried was stale on
    the other platform and two checks failed there. Static counting (def test_*
    under tests/) imports nothing and is identical everywhere.
    """
    import suite_count
    return suite_count.count_test_functions(_REPO)


def main():
    index = build()
    if "--json" in sys.argv:
        print(json.dumps(index, indent=2, ensure_ascii=False))
        return 0
    page = render(index)
    known = {"--json", "--write", "--check"}
    unknown = [a for a in sys.argv[1:] if a not in known]
    if unknown:
        # Until 2026-11-24 an unknown flag fell through to "print the page" and
        # exited 0, so `--check` looked like a passing check on a stale file.
        print("unknown argument(s): %s (known: --json --write --check)"
              % " ".join(unknown), file=sys.stderr)
        return 2
    path = os.path.join(_REPO, "docs", "EVIDENCE-INDEX.md")
    if "--write" in sys.argv:
        # LF on purpose: the page is one line of diff when a number changes, and a
        # CRLF blob turned that one line into forty-two on 2026-11-21.
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(page)
        print("written: %s (%d bytes)" % (path, len(page.encode("utf-8"))))
        return 0
    if "--check" in sys.argv:
        try:
            with open(path, encoding="utf-8") as fh:
                current = fh.read().replace("\r\n", "\n")
        except FileNotFoundError:
            print("missing: %s" % path, file=sys.stderr)
            return 1
        if current == page:
            print("current: %s" % path)
            return 0
        a, b = current.splitlines(), page.splitlines()
        for i, (was, now) in enumerate(zip(a, b), 1):
            if was != now:
                print("stale at line %d of %d:\n  in file: %s\n  fresh:   %s"
                      % (i, len(b), was[:200], now[:200]), file=sys.stderr)
                break
        else:
            print("stale: file has %d lines, a fresh build has %d"
                  % (len(a), len(b)), file=sys.stderr)
        return 1
    print(page, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
