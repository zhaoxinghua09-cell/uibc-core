"""A reference sheet for the eighteen checks, generated from the verifier.

A thesis appendix cannot say "the verifier performs eighteen checks" and stop
there: a reader needs, for each one, what question it answers, what makes it
fail, and whether any external document says it should exist at all. The
verifier source holds the ids and the failure messages; the one-line questions
below are written by hand because they are meaning, not text that can be
recovered mechanically.

    python3 tools/build_checks_reference.py > docs/CHECKS-REFERENCE.md
"""

import os
import re
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# The question each check answers, in one line. Hand-written on purpose: this
# is the part of the table a reader has to be able to argue with.
QUESTIONS = {
    "S0": "包根本无法处理时，验证器是崩溃还是给出判定？",
    "S1": "声明的每个文件都在，且没有多出不该有的文件？",
    "S2": "包自称的 agent 身份与生命周期事件里的一致？",
    "S3": "生命周期事件序列合法（类型、顺序、时间），不是伪造的转场？",
    "S4": "每个证据文件的字节未被改动，且没有指向证据目录之外的符号链接？",
    "S5": "所有证据的根承诺与清单声明一致（含整条尾部被删除）？",
    "S6": "封条签名有效，且签名覆盖的是当前这份内容？",
    "S7": "索引自身的元数据（类型、备注）未被改写（内容哈希看不到这层）？",
    "S8": "整包状态与封存的检查点一致（能看见被截短的日志）？",
    "S9": "包与外部钉住的链头一致（能看见回滚到旧的自洽包）？",
    "S10": "六个证明闭包成分都被声明并给了摘要（只声明，不验内容）？",
    "S11": "序列化严格（重复成员名、非 ECMAScript 数值都会被拒）？",
    "S12": "时间戳与标识符严格（例如 2 月 30 日这样的日期不可能通过）？",
    "S13": "merkle 包含证明可复算，且证明与被证明项对应？",
    "S14": "base64 严格（缺填充、混入杂字符都不接受）？",
    "S15": "锚定事件可解析，锚覆盖的根可由包内内容重算出来？",
    "S16": "存在真实的第三方时间戳（RFC 3161），且它覆盖的是本包的链头？",
    "S17": "收据链线性、无分叉、无伪造的创世前驱？",
    "S18": "策略产物存在，且其摘要与收据引用的摘要一致？",
}


# The nearest draft mention within 30 lines is a heuristic, not a mapping. These
# are the human judgements used instead, in three classes that must not be
# mixed in a thesis: a draft that says the thing, a document the mechanism is
# borrowed from, and nothing at all.
OVERRIDES = {
    "S1": ("direct", "draft-noa-scitt-ai-agent-receipt-00（回执包的结构与成员）"),
    "S2": ("direct", "draft-noa-scitt-ai-agent-receipt-00（主体标识）"),
    "S3": ("related", "生命周期状态机为本项目自定；事件类型集合参照 "
                      "draft-maintainer-1f916-agent-record-01"),
    "S4": ("none", "内容哈希是通用做法，无可指的具体草案；符号链接围栏"
                    "（不得指向证据目录外）为本项目自定的安全加固"),
    "S5": ("related", "Merkle 根的思想参照 RFC 6962；本包的根构造为本项目自定"),
    "S6": ("related", "Ed25519 签名本身见 RFC 8032；「签名必须覆盖当前内容」"
                      "的组合检查为本项目自定"),
    "S7": ("direct", "draft-sharif-agent-audit-trail-03（被审计对象的元数据）"),
    "S8": ("related", "checkpoint 概念参照 draft-maintainer-1f916-agent-record-01；"
                      "本包的整状态提交为本项目自定"),
    "S9": ("related", "链头需在外部被观察，参照 "
                      "draft-bailey-scitt-agent-session-receipt；具体 pin 机制自定"),
    "S10": ("direct", "draft-sharif-agent-audit-trail-03 §13.6（证明闭包六成分）"),
    "S11": ("related", "严格序列化参照 RFC 8785（JCS）；重复成员名拒收为本项目加固"),
    "S12": ("none", "本项目自定（时间戳与标识符的都按不可能值拒收）"),
    "S13": ("related", "包含证明的构造参照 RFC 6962；本包的证明格式自定"),
    "S14": ("related", "严格 base64 见 RFC 4648 §4（不得缺填充、不得混入杂字符）"),
    "S15": ("none", "本项目自定（锚定事件的解析与根重算）"),
    "S16": ("direct", "RFC 3161（时间戳协议）；「第三方时间戳必须覆盖本包链头」"
                      "的判定为本项目自定"),
    "S17": ("direct", "draft-marques-asqav-compliance-receipts-01（收据与摘要）"),
    "S18": ("direct", "draft-marques-asqav-compliance-receipts-01 §4.2.4（摘要须可解析）"),
    "S0": ("none", "本项目自定（异常时也必须给出判定，不得崩溃）"),
}
CLASS_LABEL = {"direct": "草案明文规定", "related": "思想来源（非直接规定）",
               "none": "无"}


_ID_RE = re.compile(r'"id":\s*"(S\d+)"\s*,\s*"name":\s*"([^"]+)"')
_RECORD_RE = re.compile(r'record\(\s*"(S\d+)"\s*,\s*"([^"]+)"')
_DETAIL_RE = re.compile(r'"detail":\s*(["\'])(.*?)\1', re.S)
_DRAFT_RE = re.compile(r"draft-[a-z0-9-]+")


def _source():
    path = os.path.join(_REPO, "uibc_core", "verify.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


def build():
    src = _source()
    lines = src.splitlines()
    found = {}
    matches = list(_ID_RE.finditer(src)) + list(_RECORD_RE.finditer(src))
    for m in sorted(matches, key=lambda m: m.start()):
        cid, name = m.group(1), m.group(2)
        if cid in found:
            continue
        line_no = src[:m.start()].count("\n") + 1
        # the first detail within the next 40 lines is this check's failure text
        detail = ""
        for chunk in lines[line_no - 1:line_no + 40]:
            dm = _DETAIL_RE.search(chunk)
            if dm:
                detail = " ".join(dm.group(2).split())[:160]
                break
        # the nearest draft reference above or below, and only if close: a
        # draft mentioned 60 lines away is not this check's basis
        drafts = []
        for off in range(1, 31):
            for idx in (line_no - 1 - off, line_no - 1 + off):
                if 0 <= idx < len(lines):
                    drafts.extend(_DRAFT_RE.findall(lines[idx]))
            if drafts:
                break
        found[cid] = {
            "id": cid,
            "name": name,
            "line": line_no,
            "question": QUESTIONS.get(cid, ""),
            "basis": sorted(set(drafts)) or [],
            "basis_class": OVERRIDES.get(cid, ("none", ""))[0],
            "basis_note": OVERRIDES.get(cid, ("none", ""))[1],
            "first_failure_text": detail,
        }
    return [found[k] for k in sorted(found, key=lambda c: int(c[1:]))]


def render(rows):
    out = ["# 检查项参考手册（`tools/build_checks_reference.py` 生成）\n",
           "十八项检查各自回答一个问题。**最后两列是给评审看的**：有没有外部规范"
           "说要这么做，以及失败时它说什么。\n",
           "| 检查 | 名称 | 回答的问题 | 依据类别 | 依据说明 | 源码行 |",
           "|---|---|---|---|---|---|"]
    no_basis = []
    for r in rows:
        cls = CLASS_LABEL[r["basis_class"]]
        note = r["basis_note"] or "—"
        if r["basis_class"] == "none":
            no_basis.append(r["id"])
        out.append("| %s | %s | %s | %s | %s | %d |"
                   % (r["id"], r["name"], r["question"], cls, note, r["line"]))
    out.append("")
    out.append("## 关于「外部依据」这一列\n")
    counts = {}
    for r in rows:
        counts[r["basis_class"]] = counts.get(r["basis_class"], 0) + 1
    out.append("草案明文规定 %d 项；思想来源 %d 项；完全自定 %d 项（%s）。"
               % (counts.get("direct", 0), counts.get("related", 0),
                  counts.get("none", 0), ", ".join(no_basis) or "无"))
    out.append("")
    out.append("三类的区别不是措辞，是责任：第一类写「按某草案要求」，第二类只能写"
               "「借鉴某处思想」，第三类必须写「本项目自定」。**混写会被抓住。**")
    if no_basis:
        out.append("")
        out.append("这不是缺陷，但**必须照实写**：论文里不能说「依据国际标准规定」"
                   "——只能说「参照若干 IETF 草案，其余为本项目自定」。评审一旦发现"
                   "把自定项说成标准项，整篇的可信度都会受影响。")
    out.append("")
    out.append("## 每项失败时它说什么（源码原话，可用于复现时的比对）\n")
    for r in rows:
        if r["first_failure_text"]:
            out.append("- **%s**：%s" % (r["id"], r["first_failure_text"]))
    return "\n".join(out) + "\n"


def main():
    rows = build()
    sys.stdout.write(render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
