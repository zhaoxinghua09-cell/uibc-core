"""Versioned routing and explainable semantic routing.

Clause anchor: T/ISC 0174-2026 section 8.1.

    8.1.1 a) 应支持路由规则的版本管理与回滚，可快速恢复历史配置；
    8.1.1 b) 宜支持基于智能体或模型标识、服务名称、API 路径等静态信息的基础路由转发；
    8.1.2 a) 应支持将自然语言请求解析并匹配至相应的智能体或模型；
    8.1.2 b) 应支持语义路由决策过程的可解释性，输出路由选择依据与匹配度量化指标
            （如匹配得分、候选集、阈值、决策日志等）。

8.1.1 a) is a rollback clause, so versions are immutable snapshots plus a current
pointer - rolling back does not rewrite history, it moves the pointer, which is
what makes "restore the previous configuration" a one-step, auditable act.

8.1.2 b) is a disclosure clause. Whatever scoring this uses must be printed in
the response: threshold, candidate set, per-candidate score, and the basis that
produced them. A router that answers "I picked agent A" without those numbers
fails the clause no matter how good its pick was. The score here is a token
overlap (Jaccard) - honest about being lexical, not a claim of embedding search.
"""

import datetime as _dt
import json
import os
import re
import threading

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{1,3}", re.IGNORECASE)


def _tokens(text):
    if not isinstance(text, str):
        return set()
    return set(t.lower() for t in _TOKEN_RE.findall(text))


def semantic_route(text, records, threshold=0.25, top_k=3, log=None, now=None):
    """Score every candidate, then decide - with the numbers in the answer."""
    query = _tokens(text or "")
    candidates = []
    for record in records:
        corpus = " ".join([
            record.get("name") or "",
            " ".join("%s %s" % (c.get("name", ""), c.get("description", ""))
                     for c in record.get("capabilities") or []),
            (record.get("organization") or {}).get("name") or "",
        ])
        haystack = _tokens(corpus)
        if query and haystack:
            union = query | haystack
            score = len(query & haystack) / float(len(union))
        else:
            score = 0.0
        candidates.append({"agent": record.get("id"), "name": record.get("name"),
                           "score": round(score, 4),
                           "matched": sorted(query & haystack)[:8]})
    candidates.sort(key=lambda c: (-c["score"], c["agent"] or ""))
    try:
        top_k = max(1, min(int(top_k), 10))
    except (TypeError, ValueError):
        top_k = 3
    top = candidates[:top_k]
    winner = top[0] if top and top[0]["score"] >= float(threshold) else None
    entry = {
        "ts": (now() if callable(now) else
               now or _dt.datetime.now(_dt.timezone.utc)).isoformat(),
        "query": (text or "")[:120],
        "threshold": float(threshold),
        "candidates": [{"agent": c["agent"], "score": c["score"]} for c in top],
        "decision": winner["agent"] if winner else None,
        "reason": ("score %.3f >= threshold %.3f" % (winner["score"], float(threshold))
                   if winner else
                   "best score below threshold %.3f" % float(threshold)),
    }
    if log is not None:
        log.append(entry)
    return {"decision": winner["agent"] if winner else None,
            "decision_name": winner["name"] if winner else None,
            "score": winner["score"] if winner else (top[0]["score"] if top else 0.0),
            "threshold": float(threshold),
            "candidates": top,
            "basis": "jaccard token overlap v1 (lexical, not embedding)",
            "reason": entry["reason"],
            "log_entry": entry}


class RouteTable:
    """8.1.1 a) immutable versions + current pointer, so rollback is one step."""

    def __init__(self, routes=None, path=None, now=None):
        self._lock = threading.RLock()
        self._clock = now or (lambda: _dt.datetime.now(_dt.timezone.utc))
        self.path = os.path.abspath(path) if path else None
        self._versions = []
        self._current = None
        self.log = []
        self.add_version(routes or [], note="initial")

    # -- versions ----------------------------------------------------------
    def add_version(self, routes, note=""):
        with self._lock:
            version = len(self._versions) + 1
            snapshot = {"version": version,
                        "created_at": self._clock().isoformat(),
                        "note": note or "",
                        "routes": [dict(r) for r in routes]}
            self._versions.append(snapshot)
            self._current = version
            self.log.append({"ts": snapshot["created_at"], "action": "add",
                             "version": version, "note": note or ""})
            self._persist()
            return version

    def rollback(self, version):
        with self._lock:
            if not any(v["version"] == version for v in self._versions):
                raise ValueError("no such route version: %r (known: %s)"
                                 % (version, [v["version"] for v in self._versions]))
            self._current = version
            self.log.append({"ts": self._clock().isoformat(), "action": "rollback",
                             "version": version, "note": ""})
            self._persist()
            return version

    @property
    def current_version(self):
        with self._lock:
            return self._current

    def current_routes(self):
        with self._lock:
            for version in self._versions:
                if version["version"] == self._current:
                    return [dict(r) for r in version["routes"]]
            return []

    def versions(self):
        with self._lock:
            return [{"version": v["version"], "note": v["note"],
                     "created_at": v["created_at"], "routes": len(v["routes"])}
                    for v in self._versions]

    # -- static routing (8.1.1 b) -----------------------------------------
    def match(self, agent=None, service=None, api=None):
        for route in self.current_routes():
            target = route.get("agent")
            match = route.get("match") or {}
            if agent and match.get("agent") and match["agent"] != agent:
                continue
            if service and match.get("service") and match["service"] != service:
                continue
            if api and match.get("api") and not api.startswith(match["api"]):
                continue
            if any([agent, service, api]):
                return {"agent": target, "matched": match,
                        "version": self.current_version}
        return None

    def _persist(self):
        if not self.path:
            return
        payload = {"schema": "uibc-gateway-routes/1",
                   "current": self._current,
                   "versions": self._versions,
                   "updated_at": self._clock().isoformat()}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
