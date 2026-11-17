#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引用直达性核验：报告里每一条外链，现场重新取一次，记录状态码与最终 URL。

"引用要能直达"不是排版问题：在 IETF/W3C/监管场合，一个 404 或需要登录的
中间页就等于没有引用。本脚本只做三件事——GET、跟随跳转、记录结果。

用法： python tools/check_citations.py
结果： tools/out/citations_result.json
"""
import json
import os
import ssl
import time
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "tools", "out")

URLS = [
    ("RFC 9943 (SCITT architecture)", "https://www.rfc-editor.org/rfc/rfc9943.html"),
    ("noa AI-agent receipt -01", "https://www.ietf.org/archive/id/draft-noa-scitt-ai-agent-receipt-01.html"),
    ("noa AI-agent receipt -00 页面", "https://datatracker.ietf.org/doc/draft-noa-scitt-ai-agent-receipt/"),
    ("GAR-08", "https://datatracker.ietf.org/doc/html/draft-sato-soos-gar-08"),
    ("EP-AEC-02", "https://datatracker.ietf.org/doc/html/draft-schrock-ep-authorization-evidence-chain-02"),
    ("raskar package provenance -00", "https://datatracker.ietf.org/doc/html/draft-raskar-scitt-agent-provenance-00"),
    ("1F916 agent record -01", "https://www.ietf.org/archive/id/draft-maintainer-1f916-agent-record-01.txt"),
    ("mih action capsule -04", "https://www.ietf.org/archive/id/draft-mih-scitt-agent-action-capsule-04.txt"),
    ("bailey session receipt", "https://datatracker.ietf.org/doc/draft-bailey-scitt-agent-session-receipt/"),
    ("emirdag execution profile -00", "https://www.ietf.org/archive/id/draft-emirdag-scitt-ai-agent-execution-00.html"),
    ("wilder PSER -04", "https://www.ietf.org/archive/id/draft-wilder-scitt-physical-site-engage-receipt-04.html"),
    ("RFC 9864 (COSE alg Ed25519?)", "https://www.rfc-editor.org/rfc/rfc9864.html"),
    ("RFC 8785 JCS", "https://www.rfc-editor.org/rfc/rfc8785.html"),
    ("RFC 6962 CT", "https://www.rfc-editor.org/rfc/rfc6962.html"),
    ("Entra Agent ID what's new", "https://learn.microsoft.com/entra/agent-id/whats-new-agent-id"),
    ("ERC-8004 EIP", "https://eips.ethereum.org/EIPS/eip-8004"),
    ("GLEIF", "https://www.gleif.org/"),
    ("Hound Tag whitepaper", "https://www.houndtag.xyz/whitepaper"),
    ("Portable Agent Memory paper", "https://arxiv.org/pdf/2605.11032.pdf"),
    ("ERC-8004 empirical study", "https://arxiv.org/pdf/2606.26028"),
    ("Assay Labs whitepaper", "https://www.assaylabs.xyz/Assay_Whitepaper.pdf"),
    ("AgentGuard", "https://agentguard.lictorate.com/"),
    ("ScopeGate", "https://scopegate.dev/"),
    ("McpVanguard (PyPI)", "https://pypi.org/project/mcp-vanguard/"),
    ("agentgateway", "https://agentgateway.dev/"),
    ("uibc-core 公开仓", "https://github.com/zhaoxinghua09-cell/uibc-core"),
    # --- 第五轮（2026-11-17 下午）新增 ---
    ("AAT 审计轨迹 -03", "https://www.ietf.org/archive/id/draft-sharif-agent-audit-trail-03.txt"),
    ("AIVS -01", "https://www.ietf.org/archive/id/draft-stone-aivs-01.html"),
    ("AUDIT 架构 -00", "https://www.ietf.org/archive/id/draft-kuehlewind-audit-architecture-00.html"),
    ("一致性判定 -00", "https://www.ietf.org/archive/id/draft-mih-agent-accountability-conformance-00.txt"),
    ("COGITATOR -00", "https://www.ietf.org/archive/id/draft-noctem-cogitator-witness-protocol-00.txt"),
    ("NHE 审计链 -00", "https://datatracker.ietf.org/doc/draft-ruvalcaba-nhe-audit/"),
    ("APort 平台", "https://aport.io/about/"),
    ("21 CFR 892.2055", "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-892/subpart-B/section-892.2055"),
]


def check(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; citation-check/1.0)",
        "Accept": "*/*"})
    ctx = ssl.create_default_context()
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            code, final = r.status, r.geturl()
            ctype = r.headers.get("Content-Type", "")
            n = len(r.read(4096))
        return {"status": code, "final_url": final, "content_type": ctype,
                "bytes_probed": n, "secs": round(time.perf_counter() - t0, 2),
                "ok": 200 <= code < 300}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final_url": url, "error": "HTTPError",
                "secs": round(time.perf_counter() - t0, 2),
                "ok": 200 <= e.code < 300}
    except Exception as e:
        return {"status": None, "final_url": url,
                "error": f"{type(e).__name__}: {str(e)[:80]}",
                "secs": round(time.perf_counter() - t0, 2), "ok": False}


def main():
    rows = []
    for name, url in URLS:
        r = check(url)
        rows.append({"name": name, "url": url, **r})
        print("%-34s %-5s %s" % (name, r["status"], r.get("error", "")))
    ok = sum(1 for r in rows if r["ok"])
    doc = {"meta": {"generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                     time.gmtime()),
                    "checked": len(rows), "reachable": ok},
           "rows": rows}
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "citations_result.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("\n%d/%d 直达" % (ok, len(rows)))
    print("RESULT_JSON=" + p)


if __name__ == "__main__":
    main()
