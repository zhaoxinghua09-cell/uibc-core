"""Access journal: the durable half of 9.1.1.

Clause anchor: T/ISC 0174-2026 section 9.1.1.

    9.1.1 a) 应支持对智能体间通信的访问日志及异常事件日志记录；
    9.1.1 b) 可提供日志集中存储与检索能力；
    9.1.1 c) 可支持按时间范围、操作类型等维度组合查询日志；
    9.1.1 d) 可支持日志数据的关联分析，辅助运维人员快速识别问题源头。

The previous build kept `access_log` in a list, which meant a restart erased the
only record of what the gateway had forwarded - fine for a demo, useless for an
audit. This module appends JSONL and queries it back by the dimensions 9.1.1 c)
names (time range, operation, and the trace id that ties a chain together).

Two deliberate choices:

  * No payload bodies. The journal records who/what/result - never the message
    content - so the log itself cannot become the leak that 6.3.3 warns about.
  * Query is a filter over the file, not an index. At this scale that is honest;
    claiming "centralized log search" beyond filtering would be over-claiming.
"""

import datetime as _dt
import json
import os
import threading


class Journal:
    def __init__(self, path=None, memory_limit=500):
        self.path = os.path.abspath(path) if path else None
        self._lock = threading.RLock()
        self._memory = []
        self._memory_limit = memory_limit
        if self.path and not os.path.exists(self.path):
            parent = os.path.dirname(self.path)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            open(self.path, "a", encoding="utf-8").close()

    # -- write -------------------------------------------------------------
    def record(self, entry, now=None):
        item = dict(entry)
        item.setdefault("ts", (now or _dt.datetime.now(_dt.timezone.utc)).isoformat())
        with self._lock:
            self._memory.append(item)
            if len(self._memory) > self._memory_limit:
                del self._memory[0]
            if self.path:
                with open(self.path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(item, ensure_ascii=False,
                                            sort_keys=True) + "\n")
        return item

    # -- read --------------------------------------------------------------
    def _all(self):
        if not self.path:
            with self._lock:
                return list(self._memory)
        out = []
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        # A corrupt line is not a reason to hide the rest.
                        out.append({"ts": None, "corrupt": line[:120]})
        return out

    def query(self, trace=None, agent=None, method=None, since=None,
              until=None, limit=100):
        """9.1.1 c) combined dimensions. Unknown dims simply do not filter."""
        rows = self._all()
        selected = []
        for row in rows:
            if trace and row.get("trace") != trace:
                continue
            if agent and row.get("agent") != agent:
                continue
            if method and row.get("method") != method:
                continue
            stamp = row.get("ts") or ""
            if since and stamp < since:
                continue
            if until and stamp > until:
                continue
            selected.append(row)
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = 100
        return {"total": len(selected), "returned": min(len(selected), limit),
                "entries": selected[-limit:]}

    def tail(self, count=10):
        return self.query(limit=count)["entries"]

    def summary(self):
        rows = self._all()
        by_method, by_result = {}, {}
        for row in rows:
            by_method[row.get("method")] = by_method.get(row.get("method"), 0) + 1
            by_result[row.get("result")] = by_result.get(row.get("result"), 0) + 1
        return {"entries": len(rows), "by_method": by_method,
                "by_result": by_result, "path": self.path}
