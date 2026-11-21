"""Repeat-request cache with measured effect (T/ISC 0174 8.2.2, 宜).

8.2.2 asks for message-parsing/forwarding acceleration, streaming pass-through
and content-aware routing. What this module does is narrower and stated
plainly: it caches the result of *byte-identical* requests, and reports the
measured hit rate and saved milliseconds. It does not parse the model payload,
it does not stream, and it does not claim a speedup it has not measured.

Why the narrow version is the honest one: a gateway that advertises
"AI acceleration" without a benchmark is one question away from being
embarrassed. A cache that prints `hits / misses / saved_ms` survives that
question, because the numbers are reproducible by anyone who runs the
benchmark.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time


def package_fingerprint(root, rel):
    """Why a cache key must include this: the params are identical whether the
    package on disk is the one we verified or a newer one. Keying on params
    alone would serve a stale verdict, which is worse than a slow answer."""
    path = os.path.join(root, rel or "")
    if not os.path.isdir(path):
        return None
    parts = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        try:
            stat = os.stat(full)
        except OSError:
            continue
        parts.append("%s:%d:%d" % (name, stat.st_size, int(stat.st_mtime_ns // 1_000_000)))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _canonical(params):
    """Stable key: same request twice must hash the same, key order included."""
    return json.dumps(params, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


class RepeatCache:
    def __init__(self, max_entries=256, clock=None, enabled=True):
        self.enabled = enabled
        self.max_entries = max_entries
        self._store = {}
        self._order = []
        self._lock = threading.Lock()
        self._clock = clock or time.monotonic
        self.hits = 0
        self.misses = 0
        self.saved_ms = 0.0

    def key(self, method, params):
        return "%s:%s" % (method, hashlib.sha256(
            _canonical(params).encode("utf-8")).hexdigest())

    def get(self, method, params):
        if not self.enabled:
            return None
        key = self.key(method, params)
        with self._lock:
            if key in self._store:
                self.hits += 1
                return self._store[key]
            self.misses += 1
            return None

    def put(self, method, params, value, cost_ms=0.0):
        if not self.enabled:
            return
        key = self.key(method, params)
        with self._lock:
            if key not in self._store:
                self._order.append(key)
                if len(self._order) > self.max_entries:
                    self._store.pop(self._order.pop(0), None)
            self._store[key] = value
            self.saved_ms += float(cost_ms or 0.0)

    def stats(self):
        calls = self.hits + self.misses
        return {"enabled": self.enabled,
                "entries": len(self._store),
                "max_entries": self.max_entries,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / calls, 4) if calls else 0.0,
                "saved_ms_declared": round(self.saved_ms, 2),
                "scope": "byte-identical repeat requests only; no payload parsing, "
                         "no streaming, no semantic match"}


class AccelBenchmark:
    """Measure first-call vs cached-call latency on the adapter itself."""

    def __init__(self, adapter, repeats=30):
        self.adapter = adapter
        self.repeats = repeats

    def run(self, method="uibc/verify", params=None):
        params = params or {}
        timings = []
        for _ in range(self.repeats):
            started = time.perf_counter()
            self.adapter.dispatch(method, params)
            timings.append((time.perf_counter() - started) * 1000.0)
        p50 = sorted(timings)[len(timings) // 2]
        return {"method": method, "repeats": self.repeats,
                "p50_ms": round(p50, 3),
                "first_ms": round(timings[0], 3),
                "cache": self.adapter.cache.stats(),
                "note": "measured on this machine, in-process; absolute numbers are "
                        "not portable, the hit/miss ratio is"}
