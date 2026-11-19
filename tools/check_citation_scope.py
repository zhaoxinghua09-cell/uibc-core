"""Does the archived artifact support what we are about to claim?

The DOI in CITATION.cff points at a 0.2.1 snapshot; the repository has moved a
long way since. A citation is a promise that whoever follows it will find the
thing described. This tool compares the archived verifier's checks against the
current ones and says, per check, whether a claim about it can be carried by
the DOI or only by the repository.

    python3 tools/check_citation_scope.py
    python3 tools/check_citation_scope.py --json

Exit code 1 means the baseline file disagrees with the current tree in a way
that a reader would notice, so CI fails rather than letting the gap widen
silently.
"""

import json
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BASELINE = os.path.join(_REPO, "docs", "ARCHIVE-BASELINE.json")


def baselines():
    """Every measured baseline in docs/, oldest first. More than one archive
    can exist at a time: an old version stays valid for its own snapshot while
    a newer one carries the current checks."""
    import glob
    found = sorted(glob.glob(os.path.join(_REPO, "docs", "ARCHIVE-BASELINE*.json")))
    return found


def archived_checks(path=None):
    with open(path or _BASELINE, encoding="utf-8") as f:
        return json.load(f)


def current_checks():
    tools = os.path.join(_REPO, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import build_evidence_index as bei
    declared = bei.checks_declared()
    return sorted(declared, key=lambda c: int(c[1:]))


def build(path=None):
    base = archived_checks(path)
    now = current_checks()
    only_now = [c for c in now if c not in base["checks"]]
    only_then = [c for c in base["checks"] if c not in now]
    return {
        "archived_revision": base["source_revision"],
        "baseline_file": os.path.basename(path or _BASELINE),
        "archived_version": base["version_declared"],
        "archived_checks": base["checks"],
        "current_checks": now,
        "supported_by_the_doi": [c for c in now if c in base["checks"]],
        "not_supported_by_the_doi": only_now,
        "checks_that_vanished": only_then,
        "counts": {"archived": len(base["checks"]), "current": len(now),
                   "unsupported": len(only_now)},
    }


def render(r):
    lines = []
    lines.append("归档版本 %s（%s）实际包含 %d 项检查：%s"
                 % (r["archived_version"], r["archived_revision"][:8],
                    r["counts"]["archived"], ", ".join(r["archived_checks"])))
    lines.append("当前仓库包含 %d 项检查。" % r["counts"]["current"])
    lines.append("基线文件：%s（docs/ 下另有 %d 份历史基线，各自只对自己的快照负责）"
                 % (r["baseline_file"], max(0, len(baselines()) - 1)))
    lines.append("")
    lines.append("**挂 DOI 可以说哪些**：")
    lines.append("  " + ", ".join(r["supported_by_the_doi"]))
    lines.append("")
    lines.append("**挂 DOI 不能说、只能挂仓库状态的**：")
    lines.append("  " + (", ".join(r["not_supported_by_the_doi"]) or "（无）"))
    lines.append("")
    lines.append("一份引用若声称这些检查存在，而读者照 DOI 下载，拿到的东西里没有它们。"
                 "这不是版本号不一致，是引用本身会误导人。")
    if r["checks_that_vanished"]:
        lines.append("")
        lines.append("**归档里有、现在没有的检查**（说明能力被削弱）：%s"
                     % ", ".join(r["checks_that_vanished"]))
    return "\n".join(lines) + "\n"


def main():
    path = None
    for i, a in enumerate(sys.argv):
        if a == "--baseline" and i + 1 < len(sys.argv):
            path = sys.argv[i + 1]
    r = build(path)
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if not r["checks_that_vanished"] else 1
    sys.stdout.write(render(r))
    return 0 if not r["checks_that_vanished"] else 1


if __name__ == "__main__":
    sys.exit(main())
