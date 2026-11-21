#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Muse 终审（硅基流动 SiliconFlow）：把"我们声称的"与"实际跑出来的"一起交出去。

原则（与 LGD-Eval 一致）：给评审方的是**可核验的事实包**，不是我们的结论。
- 声明：只放 README 级窄声明 + 本轮实测数字；
- 证据：五套脚本的机器可读结果摘要 + 红队用例（条数由结果 JSON 现算）+ 引用可达性 + 外人实跑；
- 缺陷：把我们自己承认的阻断项原样列出，不美化。

key 只在内存里，不打印、不落盘；路径可用环境变量 `MUSE_KEY_FILE` 覆盖。
用法： python tools/muse_review.py
产出： <session>/发布前审查_Muse终审_20261117.md
"""
import json
import os
import sys
import time
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "tools", "out")
KEY_PATH = os.environ.get("MUSE_KEY_FILE", r"D:\标准\新建文本文档.txt")
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "deepseek-ai/DeepSeek-V3"
RECEIPT = (r"C:\Users\SZYL\Doubao\chats\2026-11-17\new-chat-7"
           r"\发布前审查_Muse终审_20261117.md")


def _load(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def build_packet():
    bench = _load("mutation_benchmark.json") or {}
    rt = _load("redteam_result.json") or {}
    cit = _load("citations_result.json") or {}
    pub = _load("outsider_github_public.json") or {}
    loc = _load("outsider_local_v14.json") or {}
    epaec = _load("epaec_result.json") or {}
    cose = _load("cose_sign1_result.json") or {}
    guard = _load("guardrail_result.json") or {}

    summary = bench.get("summary", {})
    rt_rows = rt.get("cases", [])
    cit_meta = cit.get("meta", {})
    pub_runs = {r["name"]: r["rc"] for r in pub.get("runs", [])}
    loc_runs = {r["name"]: r["rc"] for r in loc.get("runs", [])}

    lines = []
    lines.append("## A. 被评审对象（uibc-core，PROPOSAL，Apache-2.0，非标准）")
    lines.append("一句话：给自治 agent 的一份**离线可验的证据包** + 三值裁决"
                 "（PASS / FAIL / INCONCLUSIVE，fail-closed）+ 生命周期状态机。")
    lines.append("窄声明（对外只允许这样讲）：A uibc PASS means: within the observed "
                 "evidence boundary, no violation was detected. It does NOT claim the "
                 "agent was correct, safe or wise; that recorded inputs were true or "
                 "complete; or that any real-world outcome followed.")
    lines.append("")
    lines.append("## B. 实测事实（脚本可复跑，结果 JSON 一并给出摘要）")
    lines.append("- 单点篡改基准：%d 类 × 3 模式；open 假接受率 %s%%，pinned %s%%，"
                 "head-pinned %s%%。" % (
                     summary.get("open", {}).get("total", 0),
                     summary.get("open", {}).get("false_accept_rate"),
                     summary.get("pinned", {}).get("false_accept_rate"),
                     summary.get("head-pinned", {}).get("false_accept_rate")))
    lines.append("- COSE_Sign1 互验：%s/%s PASS（含 alg=-19 手工路径；主流库 pycose "
                 "拒绝 -19）" % (cose.get("summary", {}).get("pass"),
                                 cose.get("summary", {}).get("total")))
    lines.append("- 红队 %d 条（外部攻击视角；数字由 redteam_result.json 现算，不写死）："
                 % len(rt_rows))
    for r in rt_rows:
        lines.append("  - %s %s → %s%s" % (
            r["id"], r["case"], r["result"],
            (" [" + ",".join(r["failed_checks"]) + "]" if r["failed_checks"] else "")))
    lines.append("- 引用直达性：%s/%s 条现场取回（非 200 的 %s 条为站点反爬、%s 条为超时；"
                 "超时项在另一网络可回 200，链接本身未变）。" % (
                     cit_meta.get("reachable"), cit_meta.get("checked"),
                     cit_meta.get("blocked"), cit_meta.get("unreachable")))
    lines.append("- EP-AEC 组链适配：%s" % (epaec.get("summary", {})))
    lines.append("- 门禁 PoC：%s" % (guard.get("summary", {}).get("ok")))
    lines.append("- 外人实跑（干净 venv，只给仓库）：本地树 %s；GitHub 公开仓 %s"
                 % (loc_runs, pub_runs))
    lines.append("")
    lines.append("## C. 我们自己承认的阻断项（不美化）")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wanted = ["tools/redteam_suite.py", "tools/mutation_benchmark.py",
              "tools/cose_sign1_interop.py", "tools/guardrail_shim.py",
              "tools/uibc_to_epaec.py", "tools/external_node_check.py",
              "tools/check_citations.py", "docs/KNOWN-LIMITS.md"]
    present = [w for w in wanted if os.path.exists(os.path.join(root, w))]
    missing = [w for w in wanted if w not in present]
    snap = []
    for name in ("redteam_result.json", "citations_result.json",
                 "mutation_benchmark.json", "external_node_result.json"):
        p = os.path.join(OUT, name)
        if os.path.exists(p):
            import hashlib
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]
            snap.append("%s(%d B, sha256:%s)" % (name, os.path.getsize(p), h))
    lines.append("1. 公开仓库内的可复跑件：%d/%d 在库（%s）；缺：%s。评审看到的数字全部"
                 "取自库内已提交的结果快照：%s —— 快照若未随套件刷新，读者看到的就是旧数字，"
                 "这一点本身也是缺陷。" % (
                     len(present), len(wanted), "、".join(present),
                     "、".join(missing) if missing else "无", "；".join(snap)))
    lines.append("2. 从干净 clone 读 SPEC_VERSION 得到 `uibc-core/0.0.0-proposal`"
                 "（版本号依赖已安装的 dist 元数据）；")
    lines.append("3. 无独立见证人/透明日志联署，最强的锚定也只到 anchored，"
                 "达不到 1F916 的 witnessed；与 EP-AEC-02 的链式见证差距见 "
                 "`docs/SPEC-PROPOSAL-v0.1.md` §5。")
    lines.append("4. 整包回滚只有带外 head 才查得到（S9），包内无法自证；")
    lines.append("5. Windows 下未测符号链接逃逸（权限受限，记为未测而非通过）；"
                 "Windows 干净克隆另有 2 例测试平台相关异常，名字见 `docs/KNOWN-LIMITS.md`。")
    lines.append("6. 只改行尾（CRLF）会被判 FAIL —— 哈希敏感的硬化代价，"
                 "对「无害重排版」是误报；已列入 `docs/KNOWN-LIMITS.md` 第 1 条，"
                 "处置是「不改判据、只标注」，不是「已修复」。")
    lines.append("")
    lines.append("## D. 要你回答的四件事")
    lines.append("1) 以 IETF/国际组织审阅者的眼光：以上 B 的事实，是否足以支撑 C 里"
                 "那三条窄声明？若有任何一条超出证据，请指出是哪一条；")
    lines.append("2) 你会把哪一条当作**必须先修**的阻断项（最多 3 条，按严重度排序）；")
    lines.append("3) 有没有「看起来是创新、其实已被 raskar-00 / 1F916-01 / GAR-08 / "
                 "EP-AEC-02 覆盖」的表述？指出重复造词处；")
    lines.append("4) 结论用三档：BLOCK / CONDITIONAL（列出条件）/ PASS，并给出一句"
                 "可以对外复述的理由。")
    return "\n".join(lines)


def main():
    try:
        with open(KEY_PATH, "r", encoding="utf-8") as f:
            api_key = f.read().strip()
    except Exception as e:
        print("KEY_READ_ERROR: %s" % e)
        return 2
    if not (api_key.startswith("sk-") and len(api_key) > 20):
        print("KEY_SHAPE_INVALID")
        return 3

    packet = build_packet()
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content":
             "You are Muse, an adversarial standards reviewer for an international "
             "standards body. You are paid to find overclaiming, not to be kind. "
             "Answer in Chinese, structured, no praise."},
            {"role": "user", "content": packet},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("API_ERROR: %s: %s" % (type(e).__name__, str(e)[:200]))
        return 4

    content = resp["choices"][0]["message"]["content"]
    usage = resp.get("usage", {})
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc = ["# 发布前审查 · Muse 终审回执（硅基流动）", "",
           "- 时间（UTC）：%s ｜ 模型：%s ｜ 用时：%.1fs" % (stamp, MODEL, time.time() - t0),
           "- token：prompt %s / completion %s" % (usage.get("prompt_tokens"),
                                                   usage.get("completion_tokens")),
           "- 说明：本回执为第三方模型原样输出，未经我方润色；key 未落盘。",
           "", "---", "", content, "", "---", "",
           "## 附：送审事实包（原文，供复核）", "", "```", packet, "```", ""]
    with open(RECEIPT, "w", encoding="utf-8") as f:
        f.write("\n".join(doc))
    print(content[:1200])
    print("\nRECEIPT=" + RECEIPT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
