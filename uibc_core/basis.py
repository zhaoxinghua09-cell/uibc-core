"""What each check is allowed to claim as its external basis.

A verifier that says "FAIL: hash mismatch" is useful. A verifier that says
"FAIL: hash mismatch, and this rule is ours alone" is honest. The difference
matters most where it is easiest to blur: a thesis appendix, a standards
submission, a comparison table.

Three classes, and they are not interchangeable:

    direct   a draft or RFC states this requirement, and the check implements it
    related  the mechanism is borrowed from a document, the check is ours
    none     nothing to point at; this project defines it

Only `direct` and `related` carry a citation, and the citation names an actual
document. `none` carries an empty string on purpose - there is no field to
leave blank and quietly fill in later.
"""

BASIS = {
    "S0": {"class": "none", "citation": "",
           "note": "异常时也必须给出判定，不得崩溃（本项目自定）"},
    "S1": {"class": "direct", "citation": "draft-noa-scitt-ai-agent-receipt-00",
           "note": "回执包的结构与成员"},
    "S2": {"class": "direct", "citation": "draft-noa-scitt-ai-agent-receipt-00",
           "note": "主体标识"},
    "S3": {"class": "related", "citation": "draft-maintainer-1f916-agent-record-01",
           "note": "状态机自定；事件类型集合参照该草案"},
    "S4": {"class": "none", "citation": "",
           "note": "内容哈希为通用做法；符号链接围栏为本项目自定的安全加固"},
    "S5": {"class": "related", "citation": "RFC 6962",
           "note": "Merkle 根的思想；本包的根构造自定"},
    "S6": {"class": "related", "citation": "RFC 8032",
           "note": "Ed25519 签名；「签名须覆盖当前内容」的组合检查自定"},
    "S7": {"class": "direct", "citation": "draft-sharif-agent-audit-trail-03",
           "note": "被审计对象的元数据"},
    "S8": {"class": "related", "citation": "draft-maintainer-1f916-agent-record-01",
           "note": "checkpoint 概念；整状态提交自定"},
    "S9": {"class": "related", "citation": "draft-bailey-scitt-agent-session-receipt",
           "note": "链头需在外部被观察；pin 机制自定"},
    "S10": {"class": "direct", "citation": "draft-sharif-agent-audit-trail-03 §13.6",
            "note": "证明闭包六成分"},
    "S11": {"class": "related", "citation": "RFC 8785",
            "note": "JCS 严格序列化；重复成员名拒收为加固"},
    "S12": {"class": "none", "citation": "",
            "note": "时间戳与标识符按不可能值拒收（本项目自定）"},
    "S13": {"class": "related", "citation": "RFC 6962",
            "note": "包含证明的构造；本包证明格式自定"},
    "S14": {"class": "related", "citation": "RFC 4648 §4",
            "note": "严格 base64：不得缺填充、不得混入杂字符"},
    "S15": {"class": "none", "citation": "",
            "note": "锚定事件解析与根重算（本项目自定）"},
    "S16": {"class": "direct", "citation": "RFC 3161",
            "note": "时间戳协议本体；「须覆盖本包链头」的判定自定"},
    "S17": {"class": "direct", "citation": "draft-marques-asqav-compliance-receipts-01",
            "note": "收据与摘要"},
    "S18": {"class": "direct", "citation": "draft-marques-asqav-compliance-receipts-01 §4.2.4",
            "note": "摘要须可解析"},
    "S19": {"class": "related", "citation": "draft-bailey-scitt-agent-session-receipt",
            "note": "新鲜度只能由外部状态判定，签名不蕴含时间顺序；"
                    "高水位记忆机制为本项目自定"},
}

CLASSES = ("direct", "related", "none")
CLASS_LABEL = {"direct": "草案明文规定", "related": "思想来源（非直接规定）",
               "none": "无"}


def for_check(cid):
    """The basis record for one check. An unknown id gets `none` rather than
    borrowing someone else's citation."""
    return dict(BASIS.get(cid, {"class": "none", "citation": "",
                                "note": "未登记依据；按自定处理"}))


def counts():
    out = {c: 0 for c in CLASSES}
    for rec in BASIS.values():
        out[rec["class"]] += 1
    return out
