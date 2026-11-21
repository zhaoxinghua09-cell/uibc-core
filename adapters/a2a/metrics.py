"""Forwarding metrics: 8.2.1 a) latency and b) live visibility.

    8.2.1 a) 应满足约定的消息转发时延指标；
    8.2.1 b) 应提供吞吐量、延迟、错误率等核心性能指标的实时监控与可视化展示。

The honest version of a) is not "we are fast", it is "here is the measured
distribution and here is the budget we compare it against". So this keeps a
bounded latency sample plus a declared budget (`--latency-budget-ms`); exceeding
it is counted, not hidden. b) is served as both a text exposition (the format
every scraper understands) and JSON, so "visualization" does not depend on us
inventing a dashboard nobody can query.
"""

import threading


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    # Nearest-rank, floor-indexed: cheap, stable, and documented so a reader can
    # reproduce the number instead of trusting the label "p95".
    index = int(fraction * (len(ordered) - 1))
    return ordered[max(0, min(index, len(ordered) - 1))]


class Metrics:
    def __init__(self, sample_limit=2000, latency_budget_ms=250.0):
        self._lock = threading.RLock()
        self._sample_limit = sample_limit
        self.budget_ms = float(latency_budget_ms)
        self.durations = []
        self.total = 0
        self.errors = 0
        self.blocked = 0
        self.over_budget = 0
        self.by_method = {}
        self.by_result = {}

    def observe(self, method, duration_ms, error=False, blocked=False,
                result=None):
        with self._lock:
            self.total += 1
            if error:
                self.errors += 1
            if blocked:
                self.blocked += 1
            if duration_ms > self.budget_ms:
                self.over_budget += 1
            self.durations.append(float(duration_ms))
            if len(self.durations) > self._sample_limit:
                del self.durations[0]
            self.by_method[method] = self.by_method.get(method, 0) + 1
            key = result if result is not None else ("ERROR" if error else "OK")
            self.by_result[key] = self.by_result.get(key, 0) + 1

    def snapshot(self):
        with self._lock:
            durations = list(self.durations)
            total = self.total
            errors = self.errors
            return {
                "requests_total": total,
                "errors_total": errors,
                "blocked_total": self.blocked,
                "error_rate": (errors / total) if total else 0.0,
                "latency_ms": {
                    "count": len(durations),
                    "p50": _percentile(durations, 0.5),
                    "p95": _percentile(durations, 0.95),
                    "max": max(durations) if durations else None,
                    "budget": self.budget_ms,
                    "over_budget": self.over_budget,
                },
                "by_method": dict(self.by_method),
                "by_result": dict(self.by_result),
            }

    def render_prometheus(self):
        snap = self.snapshot()
        lat = snap["latency_ms"]
        lines = [
            "# TYPE uibc_gateway_requests_total counter",
            "uibc_gateway_requests_total %d" % snap["requests_total"],
            "# TYPE uibc_gateway_errors_total counter",
            "uibc_gateway_errors_total %d" % snap["errors_total"],
            "# TYPE uibc_gateway_blocked_total counter",
            "uibc_gateway_blocked_total %d" % snap["blocked_total"],
            "# TYPE uibc_gateway_latency_ms summary",
            "uibc_gateway_latency_ms{quantile=\"0.5\"} %s" % (lat["p50"] if lat["p50"] is not None else "NaN"),
            "uibc_gateway_latency_ms{quantile=\"0.95\"} %s" % (lat["p95"] if lat["p95"] is not None else "NaN"),
            "uibc_gateway_latency_budget_ms %s" % lat["budget"],
            "uibc_gateway_latency_over_budget_total %d" % lat["over_budget"],
        ]
        for method, count in sorted(snap["by_method"].items()):
            lines.append('uibc_gateway_requests_by_method{method="%s"} %d' % (method, count))
        return "\n".join(lines) + "\n"
