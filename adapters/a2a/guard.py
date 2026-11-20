"""Inline injection / instruction-tampering detection (T/ISC 0174 9.1.3 b)).

Run inside the forwarding path so a suspicious payload never reaches the
handler. Deliberately rule-based: a small, printed rule set that an outside
reader can extend and re-run. Recall is bounded by the rules, and the code
says so rather than implying model-grade detection.

Two rules of hygiene:
  * the journal and the refusal carry a digest of the match, never the text,
    because the payload itself is what must not be copied around;
  * only high-confidence shapes are blocking. Ambiguous wording is reported
    as a warning so an operator can see it without the gateway crying wolf.
"""

from __future__ import annotations

import hashlib
import re

CLAUSE = "9.1.3 b)"
MAX_CHARS = 100_000  # a payload bigger than this is not scanned silently

_RULES = [
    # (category, severity, pattern)
    ("prompt-override", "block",
     r"(?i)\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier|system)\b"
     r"[^.\n]{0,20}\b(?:instruction|prompt|rule|message)s?\b"),
    ("prompt-override", "block",
     r"(?:忽略|无视|忘记|覆盖|跳过)[^。\n]{0,12}(?:之前|以上|上述|前面|系统)[^。\n]{0,10}"
     r"(?:指令|提示|要求|设定|规则)"),
    ("role-spoof", "block",
     r"(?m)^\s*(?:system|developer|assistant)\s*[:：]"),
    ("role-spoof", "block", r"(?i)<\s*/?\s*(?:system|sys_prompt|developer)\s*>"),
    ("role-spoof", "warn",
     r"(?i)\b(?:system|developer)\s+prompt\b"),
    ("tool-spoof", "block",
     r"(?i)\b(?:function_call|tool_call)\b|\"\s*tool_calls\s*\"\s*:"),
    ("tool-spoof", "warn",
     r"(?:请|立即|马上)?(?:调用|执行|运行)[^。\n]{0,10}(?:工具|函数|插件|tool)"),
    ("exfil", "block",
     r"(?i)\b(?:send|post|upload|forward|exfiltrate)\b[^.\n]{0,60}https?://"),
    ("exfil", "block",
     r"(?:把|将)[^。\n]{0,30}(?:上传|发送|转发|外发)[^。\n]{0,20}https?://"),
    ("delimiter-escape", "block", r"</?\s*script\b|__proto__|\$\s*where\b"),
    ("opaque-encoding", "warn",
     r"(?i)\b(?:base64|hex|rot13|decode)\b[^.\n]{0,20}[A-Za-z0-9+/=]{24,}"),
    ("invisible-text", "block", "[\u200b-\u200f\u202a-\u202e\u2060-\u2064]"),
]

_COMPILED = [(cat, sev, re.compile(pat)) for cat, sev, pat in _RULES]


def _digest(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def scan_text(text):
    """Findings for one string. No payload text is copied into the result."""
    findings = []
    if not isinstance(text, str) or not text:
        return findings
    if len(text) > MAX_CHARS:
        findings.append({"category": "oversized", "severity": "warn",
                         "clause": CLAUSE, "evidence": _digest(text[:4096]),
                         "note": "payload over %d chars, only head inspected" % MAX_CHARS})
        text = text[:MAX_CHARS]
    for cat, sev, pattern in _COMPILED:
        match = pattern.search(text)
        if match:
            findings.append({"category": cat, "severity": sev, "clause": CLAUSE,
                             "evidence": _digest(match.group(0)),
                             "offset": match.start()})
    return findings


def scan_params(params, _depth=0):
    """Walk a JSON-RPC params tree and scan every string in it."""
    findings = []
    if _depth > 8:
        return findings
    if isinstance(params, str):
        return scan_text(params)
    if isinstance(params, dict):
        for key, value in params.items():
            # A key can smuggle a delimiter just as well as a value.
            if isinstance(key, str):
                findings.extend(scan_text(key)[:1])
            findings.extend(scan_params(value, _depth + 1))
    elif isinstance(params, (list, tuple)):
        for item in params:
            findings.extend(scan_params(item, _depth + 1))
    return findings


class GuardRefusal(Exception):
    """Raised instead of forwarding. Carries categories, never the payload."""

    clause = CLAUSE

    def __init__(self, findings):
        self.findings = findings
        blocking = [f for f in findings if f["severity"] == "block"] or findings
        self.categories = sorted({f["category"] for f in blocking})
        self.evidence = blocking[0].get("evidence") if blocking else None
        super().__init__("payload refused by 9.1.3 b) guard: %s"
                         % ", ".join(self.categories))


def inspect(params):
    """Return (blocking_findings, warnings). Blocking list empty means forward."""
    findings = scan_params(params)
    blocking = [f for f in findings if f["severity"] == "block"]
    warnings = [f for f in findings if f["severity"] != "block"]
    return blocking, warnings
