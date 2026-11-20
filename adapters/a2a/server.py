"""uibc-core A2A Adapter (PROPOSAL) - expose UIBC verification to Agent2Agent
(A2A-style) clients over JSON-RPC 2.0 / HTTP.

Zero dependencies (stdlib only). Read-only surface per docs/api-scope.md v1.0:
the adapter verifies packages that exist on the *server operator's* disk
(operator-trusted model) and returns verification verdicts; it never writes.

JSON-RPC methods (POST /a2a/):
  "card"             -> the agent-card.json content
  "uibc/verify"      -> params {package, agent?, key?|did?} -> verify report (S1-S6)
  "uibc/gate"        -> params {package, agent?, key?|did?} -> gate decision
  "uibc/inspect"     -> params {package}            -> human-readable summary fields
  "gateway/registry" -> validation report of the registration metadata (6.1.1)
  "gateway/state"    -> lifecycle state snapshot + audit count (6.1.3)
  "gateway/discover" -> params {q, limit?}         -> lookup + explicit ranking (6.2.1)
  "agent-record"     -> unified Agent Record merged from card + registry (7.2.1 b)

Discovery (GET):
  /agent-card.json, /.well-known/agent-card.json, /a2a/card -> the card, with
      `url` rewritten to whatever host the caller used, so the same card is
      correct behind a tunnel, a reverse proxy or a LAN address.
  /.well-known/did.json -> the operator's DID document, when started with
      --did or --did-doc (this is what makes did:web resolvable for us).
  /agent-record.json -> the unified Agent Record (7.2.1 b).
  /agents?q=&limit= -> registration lookup, only enabled agents (6.2.2 a).
  /healthz -> {"status":"ok"} and nothing else: reachability checks should
      not be able to lie about verification capability.

Gateway duties wired here rather than left to prose:

  * lifecycle (6.1.3 b). With --registry, every uibc/* call must name its target
    agent, and that agent must be `enabled` at the moment of the call; a
    suspended or revoked agent is refused with HTTP 403 before any verification
    work happens. "Immediate" means per-request, not per-restart.
  * registration metadata (6.1.1 a/b). The registry is validated at startup and
    the process refuses to start on a half-valid one. Fail closed.
  * extension headers (7.3.1 d) and trace continuity (9.1.2 a/d). Every call
    carries a gateway-unique trace id; an upstream X-AUIB-Trace-Id is inherited
    rather than replaced, so a chain across gateways stays one chain.

Note: {package} is a path relative to the operator's --packages root; ".."
traversal is rejected.

Run:
  python adapters/a2a/server.py --packages ./examples --port 8899 --host 0.0.0.0
  python adapters/a2a/server.py --packages ./examples --registry registry.json \
      --lifecycle-state lifecycle.json
"""

import argparse
import datetime as _dt
import json
import os
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core.verify import verify  # noqa: E402
from uibc_core.gate import gate  # noqa: E402
from uibc_core import did as did_mod  # noqa: E402

from adapters.a2a import registry as registry_mod  # noqa: E402
from adapters.a2a import state as state_mod  # noqa: E402
from adapters.a2a import journal as journal_mod  # noqa: E402
from adapters.a2a import metrics as metrics_mod  # noqa: E402
from adapters.a2a import router as router_mod  # noqa: E402
from adapters.a2a import templates as templates_mod  # noqa: E402
from adapters.a2a import transform as transform_mod  # noqa: E402
from adapters.a2a import backup as backup_mod  # noqa: E402
from adapters.a2a import specs as specs_mod  # noqa: E402

JSONRPC_VERSION = "2.0"
_METHODS = ("card", "uibc/verify", "uibc/gate", "uibc/inspect",
            "gateway/registry", "gateway/registry/update", "gateway/state",
            "gateway/discover", "gateway/route", "gateway/routes",
            "gateway/transform", "gateway/templates", "gateway/journal",
            "gateway/specs", "gateway/backup", "agent-record")

# 7.3.1 d) minimum common extension-header set for gateway-to-gateway hops.
TRACE_HEADERS = ("X-AUIB-Trace-Id", "X-AUIB-Source", "X-AUIB-Target",
                 "X-AUIB-Protocol-Version", "X-AUIB-Timestamp")
DEFAULT_PROTOCOL_VERSION = "a2a/1.0"
MAX_DISCOVER_LIMIT = 100


def _resolve_package(packages_root, rel):
    if not isinstance(rel, str) or not rel:
        raise ValueError("params.package must be a non-empty relative path")
    norm = os.path.normpath(rel)
    if os.path.isabs(norm) or norm.startswith(".."):
        raise ValueError("path traversal rejected")
    pkg = os.path.join(packages_root, norm)
    if not os.path.isdir(pkg):
        raise FileNotFoundError("package not found: %s" % rel)
    return pkg


def search_agents(records, query, limit=20):
    """6.2.1 a/b) lookup with an explicit, printable ranking.

    The ranking is deliberately dumb and stated in the response (weights, per-hit
    score, matched fields) instead of hidden inside a model: 8.1.2 b) asks for the
    basis and the numbers, and a score nobody can print is a score nobody can audit.
    """
    terms = [t for t in (query or "").lower().split() if t]
    hits = []
    for record in records:
        haystacks = [
            ("name", 3.0, (record.get("name") or "").lower()),
            ("capability", 2.0, " ".join(
                "%s %s" % (c.get("name", ""), c.get("description", ""))
                for c in record.get("capabilities") or []).lower()),
            ("organization", 1.0, (record.get("organization") or {}).get("name", "").lower()),
            ("protocol", 0.5, " ".join(record.get("protocols") or []).lower()),
        ]
        score = 0.0
        matched = []
        for field, weight, text in haystacks:
            for term in terms:
                if term and term in text:
                    score += weight
                    if field not in matched:
                        matched.append(field)
        if terms and score <= 0.0:
            continue
        if not terms:                      # empty query = whole visible catalogue
            score = 1.0
            matched = ["*"]
        hits.append({"record": record, "score": round(score, 3),
                     "matched_on": matched})
    hits.sort(key=lambda h: (-h["score"],
                             (h["record"].get("name") or "").lower(),
                             h["record"].get("id") or ""))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(limit, MAX_DISCOVER_LIMIT))
    return {"query": query or "", "total": len(hits), "limit": limit,
            "ranking": "field-weighted keyword (name 3.0, capability 2.0, "
                       "organization 1.0, protocol 0.5)",
            "results": hits[:limit]}


class A2AAdapter:
    """Method dispatch, separated from HTTP so tests can call it directly."""

    def __init__(self, packages_root, card_path, did_document=None,
                 registry=None, lifecycle_state=None, allow_opaque_id=False,
                 clock=None, journal_path=None, routes_path=None,
                 latency_budget_ms=250.0, backup_root=None):
        self.packages_root = os.path.abspath(packages_root)
        with open(card_path, "r", encoding="utf-8") as f:
            self.card = json.load(f)
        # Published DID document (optional). Serving it from /.well-known/ is
        # what turns our did:web from a string into something resolvable.
        self.did_document = did_document
        self.clock = clock or (lambda: _dt.datetime.now(_dt.timezone.utc))
        self.access_log = []
        self.journal = journal_mod.Journal(journal_path)
        self.metrics = metrics_mod.Metrics(latency_budget_ms=latency_budget_ms)
        self.routes = router_mod.RouteTable(path=routes_path, now=self.clock)
        self.allow_opaque_id = allow_opaque_id
        # 6.3.x operates on the gateway's own state files; nothing else is ours
        # to back up, and pretending otherwise would be a false coverage claim.
        self.backup_root = os.path.abspath(backup_root) if backup_root else None
        self.state_paths = [p for p in (registry if isinstance(registry, str) else None,
                                        lifecycle_state, routes_path, journal_path) if p]

        # Registration metadata: a path, a pre-validated report, or None.
        self.registry_report = None
        self.lifecycle = None
        if registry is not None:
            report = (registry_mod.load(registry, allow_opaque_id=allow_opaque_id)
                      if isinstance(registry, str) else registry)
            if not report.get("ok"):
                raise ValueError("refusing to start on an invalid registry: %s"
                                 % report.get("errors"))
            self.registry_report = report
            self.lifecycle = state_mod.LifecycleStore(report["agents"],
                                                      path=lifecycle_state,
                                                      now=self.clock)

    # -- discovery ---------------------------------------------------------
    def card_for(self, base_url):
        """Card with `url` rewritten to the host the caller actually used.

        A card that hard-codes 127.0.0.1 is wrong the moment the operator
        tunnels or proxies it, and a wrong service URL in a card is exactly
        how "integrated but unreachable" happens.
        """
        card = dict(self.card)
        card["url"] = base_url + "a2a/"
        interfaces = []
        for item in self.card.get("supportedInterfaces") or []:
            item = dict(item)
            item["url"] = base_url + "a2a/"
            interfaces.append(item)
        if interfaces:
            card["supportedInterfaces"] = interfaces
        return card

    def _visible_records(self):
        """6.2.2 a) only agents this gateway will actually forward to."""
        if not self.registry_report:
            return []
        return [r for r in self.registry_report["agents"]
                if self.lifecycle and self.lifecycle.is_enabled(r["id"])]

    def agent_record(self, base_url):
        """7.2.1 b) one record shape across Agent Card and registration metadata."""
        card = self.card
        first = (self.registry_report["agents"][0]
                 if self.registry_report and self.registry_report["agents"] else {})
        return {
            "schema": "uibc-agent-record/1",
            "name": card.get("name"),
            "description": card.get("description"),
            "id": first.get("id"),
            "organization": first.get("organization"),
            "endpoint": base_url + "a2a/",
            "protocols": ["a2a/1.0", "jsonrpc-2.0"],
            "capabilities": card.get("skills") or card.get("capabilities") or [],
            "agent_card": base_url + "agent-card.json",
            "did_document": (base_url + ".well-known/did.json"
                             if self.did_document is not None else None),
            "verification": {"package": "UIBC package", "methods": list(_METHODS)},
            "agents": [{"id": r["id"], "name": r["name"],
                        "state": self.lifecycle.state(r["id"]) if self.lifecycle else None}
                       for r in (self.registry_report["agents"] if self.registry_report else [])],
        }

    # -- dispatch ----------------------------------------------------------
    def dispatch(self, method, params, trace_id=None):
        params = params or {}
        if method == "card":
            return self.card
        if method == "gateway/registry":
            if not self.registry_report:
                raise ValueError("no registry loaded: start the adapter with --registry")
            return {"ok": self.registry_report["ok"],
                    "schema": self.registry_report.get("schema"),
                    "errors": self.registry_report["errors"],
                    "warnings": self.registry_report["warnings"],
                    "agents": [{"name": r["name"], "id": r["id"],
                                "state": (self.lifecycle.state(r["id"])
                                          if self.lifecycle else r["state"])}
                               for r in self.registry_report["agents"]]}
        if method == "gateway/state":
            if not self.lifecycle:
                raise ValueError("no lifecycle loaded: start the adapter with --registry")
            return self.lifecycle.snapshot()
        if method == "gateway/discover":
            query = params.get("q") or params.get("query") or ""
            return search_agents(self._visible_records(), query,
                                 limit=params.get("limit", 20))
        if method == "agent-record":
            return self.agent_record("http://127.0.0.1/")
        if method == "gateway/registry/update":
            return update_registration(self, params)
        if method == "gateway/route":
            return gateway_route(self, params)
        if method == "gateway/routes":
            return gateway_routes(self, params)
        if method == "gateway/transform":
            payload = params.get("payload")
            target = params.get("target") or "xml"
            try:
                converted = transform_mod.convert(payload, target,
                                                  source_format=params.get("source"))
            except transform_mod.SemanticDrift as drift:
                # 7.2.2 e) refuse to forward, record the security event.
                self.journal.record({"ts": self.clock().isoformat(),
                                     "type": "semantic-drift",
                                     "event": drift.event, "diff": drift.diff})
                return {"ok": False, "refused": True, "reason": str(drift),
                        "event": drift.event}
            result = {"ok": True, "refused": False}
            result.update(converted)
            return result
        if method == "gateway/templates":
            template_id = params.get("id")
            if not template_id:
                return {"templates": templates_mod.available(),
                        "available": templates_mod.available(),
                        "note": "6.1.1 d 场景模板，取其中一个再按 overrides 覆盖"}
            candidate = templates_mod.build(template_id, params.get("overrides"))
            verdict = registry_mod.validate({"agents": [candidate]})
            return {"template": templates_mod.get(template_id),
                    "candidate": candidate,
                    "validation": {"ok": verdict["ok"],
                                   "errors": verdict["errors"],
                                   "warnings": verdict["warnings"]}}
        if method == "gateway/journal":
            return self.journal.query(
                trace=params.get("trace"), agent=params.get("agent_filter"),
                method=params.get("method_filter"),
                since=params.get("since"), until=params.get("until"),
                limit=params.get("limit", 50))
        if method == "gateway/specs":
            if "descriptors" in params:
                return specs_mod.validate_tool_descriptors(params.get("descriptors"))
            problems = specs_mod.validate_tool_descriptor(params.get("descriptor"))
            return {"ok": not problems, "errors": problems,
                    "example": specs_mod.MCP_EXAMPLE}
        if method == "gateway/backup":
            return gateway_backup(self, params)

        # 6.1.3 b) enforce state *before* any work, whenever a registry exists.
        agent = params.get("agent")
        if self.lifecycle is not None:
            if not agent:
                raise ValueError("params.agent is required when the gateway runs "
                                 "with a registry (6.1.1 a): the gateway must know "
                                 "which registered agent a call is for")
            self.lifecycle.require_active(agent)

        pkg = _resolve_package(self.packages_root, params.get("package"))
        key = params.get("key")  # hex string, same format as .key files
        if key is not None:
            key = bytes.fromhex(key)
        # A caller may pin the key by DID instead of shipping the key itself.
        # That is the difference between "my verifier says PASS" and "any
        # verifier with the DID says PASS".
        pubkey = None
        did_value = params.get("did")
        if did_value:
            try:
                pubkey, _kid = did_mod.resolve_ed25519_key(did_value)
            except Exception as exc:
                raise ValueError("cannot resolve %s: %s" % (did_value, exc))
        if method == "uibc/verify":
            report = verify(pkg, key=key, pubkey=pubkey)
        elif method == "uibc/gate":
            report = gate(pkg, key=key, pubkey=pubkey)
            return {"decision": report.get("decision"),
                    "reason": report.get("reason",
                                         report.get("detail", "")),
                    "report": report}
        elif method == "uibc/inspect":
            with open(os.path.join(pkg, "identity.json"), "r",
                      encoding="utf-8") as f:
                identity = json.load(f)
            return {"identity": identity.get("agent_id", identity.get("id")),
                    "spec_version": identity.get("spec_version")}
        else:
            raise ValueError("unknown method: %s" % method)

        # 9.1.1 a) every forwarded call leaves an access record, trace id included.
        self.access_log.append({"ts": self.clock().isoformat(), "trace": trace_id,
                                "method": method, "agent": agent,
                                "package": params.get("package"),
                                "result": report.get("result")
                                if isinstance(report, dict) else None})
        return report


def update_registration(adapter, params):
    """6.1.1 c) metadata edit: validate first, then require review to apply."""
    if not adapter.registry_report:
        raise ValueError("no registry loaded: start the adapter with --registry")
    agent_id = params.get("agent")
    patch = params.get("patch")
    if not agent_id or not isinstance(patch, dict) or not patch:
        raise ValueError("params.agent and a non-empty params.patch are required")
    current = None
    for record in adapter.registry_report["agents"]:
        if record["id"] == agent_id or record["name"] == agent_id:
            current = record
            break
    if current is None:
        raise ValueError("unknown agent: %r" % (agent_id,))

    merged = {"name": current["name"], "id": current["id"],
              "capabilities": current["capabilities"],
              "protocols": current["protocols"],
              "endpoint": current["endpoint"],
              "organization": current["organization"],
              "state": (adapter.lifecycle.state(current["id"])
                        if adapter.lifecycle else current["state"]),
              "vc": current.get("vc"),
              "authorization": current.get("authorization")}
    merged.update(patch)
    errors, warnings, record = registry_mod.validate_agent(
        merged, allow_opaque_id=adapter.allow_opaque_id)
    diff = {"before": {k: current.get(k) for k in patch},
            "after": {k: patch[k] for k in patch}}
    event = {"ts": adapter.clock().isoformat(), "agent": agent_id,
             "approved": bool(params.get("approve")),
             "actor": params.get("actor"), "reason": params.get("reason", ""),
             "diff": diff, "errors": [e["code"] for e in errors]}

    if errors:
        adapter.journal.record(dict(event, type="metadata-change-rejected"))
        return {"ok": False, "applied": False, "errors": errors, "diff": diff}
    if not bool(params.get("approve")):
        adapter.journal.record(dict(event, type="metadata-change-pending"))
        return {"ok": True, "applied": False, "pending_review": True,
                "errors": [], "warnings": warnings, "diff": diff,
                "hint": "params.approve=true 才会落地（6.1.1 c 变更需经过审核）"}

    current.clear()
    current.update(record)
    adapter.journal.record(dict(event, type="metadata-change-applied"))
    return {"ok": True, "applied": True, "errors": [], "warnings": warnings,
            "diff": diff}


def gateway_route(adapter, params):
    """8.1.2 a/b: semantic route with the numbers in the answer, or static match."""
    version = adapter.routes.current_version
    text = params.get("text")
    if isinstance(text, str) and text.strip():
        result = router_mod.semantic_route(
            text, adapter._visible_records(),
            threshold=params.get("threshold", 0.25),
            top_k=params.get("top_k", 3),
            log=adapter.routes.log, now=adapter.clock)
        result["route_version"] = version
        return result
    static = adapter.routes.match(agent=params.get("agent_target"),
                                  service=params.get("service"),
                                  api=params.get("api"))
    return {"static": static, "route_version": version,
            "reason": ("no route matched" if static is None
                       else "matched on %s" % (static.get("matched"),))}


def gateway_routes(adapter, params):
    """8.1.1 a: add a version, list versions, or roll the pointer back."""
    op = params.get("op") or "versions"
    if op == "versions":
        return {"versions": adapter.routes.versions(),
                "current": adapter.routes.current_version}
    if op == "rollback":
        version = adapter.routes.rollback(int(params.get("version")))
        return {"current": version, "routes": adapter.routes.current_routes()}
    if op == "add":
        version = adapter.routes.add_version(params.get("routes") or [],
                                             note=params.get("note", ""))
        return {"current": version, "routes": adapter.routes.current_routes()}
    raise ValueError("unknown routes op %r (versions|rollback|add)" % (op,))


def gateway_backup(adapter, params):
    """6.3.1 / 6.3.2 over the gateway's own state files."""
    if not adapter.backup_root:
        raise ValueError("no backup directory configured: start with --backup-dir")
    store = backup_mod.BackupStore(adapter.backup_root, adapter.state_paths,
                                   now=adapter.clock)
    op = params.get("op") or "create"
    if op == "create":
        return {"ok": True,
                "manifest": store.create(incremental=bool(params.get("incremental")),
                                         label=params.get("label"))}
    if op == "list":
        return {"backups": store.backups(), "latest": store.latest()}
    if op == "verify":
        return store.verify(params.get("label"))
    if op == "detect":
        return store.detect_corruption(params.get("label"))
    if op == "restore":
        return store.restore(params.get("label"), target_dir=params.get("target_dir"))
    raise ValueError("unknown backup op %r (create|list|verify|detect|restore)" % (op,))


def make_handler(adapter):
    class A2AHandler(BaseHTTPRequestHandler):
        def _send_json(self, code, payload, trace_id=None):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if trace_id:
                # 9.1.2 a) hand the trace id back so the caller can correlate.
                self.send_header("X-AUIB-Trace-Id", trace_id)
            self.end_headers()
            self.wfile.write(body)

        def _rpc_error(self, rid, code, message, trace_id=None, data=None):
            error = {"code": code, "message": message}
            if data:
                error["data"] = data
            self._send_json(200, {"jsonrpc": JSONRPC_VERSION, "id": rid,
                                  "error": error, "traceId": trace_id}, trace_id)

        def _base_url(self):
            host = self.headers.get("Host")
            if not host:
                host = "127.0.0.1:%d" % self.server.server_port
            # Behind a tunnel or reverse proxy the Host header is right but
            # the scheme is not knowable from the socket, so honour the
            # de-facto X-Forwarded-Proto when it is present.
            scheme = (self.headers.get("X-Forwarded-Proto") or "http").split(",")[0].strip()
            return "%s://%s/" % (scheme or "http", host)

        def do_GET(self):
            raw_path, _, query = (self.path or "/").partition("?")
            path = raw_path.rstrip("/") or "/"
            if path == "/healthz":
                return self._send_json(200, {"status": "ok"})
            if path == "/metrics":
                # 8.2.1 b) real time counters in the format scrapers already read.
                payload = adapter.metrics.render_prometheus().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if path in ("/agent-card.json", "/.well-known/agent-card.json",
                        "/a2a/card", "/uibc-a2a/agent-card.json"):
                return self._send_json(200, adapter.card_for(self._base_url()))
            if path == "/agent-record.json":
                return self._send_json(200, adapter.agent_record(self._base_url()))
            if path == "/agents":
                params = {k: v[0] for k, v in parse_qs(query).items()}
                try:
                    payload = adapter.dispatch("gateway/discover", params)
                except ValueError as exc:
                    return self._send_json(400, {"error": str(exc)})
                return self._send_json(200, payload)
            if path == "/.well-known/did.json":
                if adapter.did_document is None:
                    return self._send_json(404, {
                        "error": "no DID document configured",
                        "hint": "start the adapter with --did or --did-doc",
                    })
                return self._send_json(200, adapter.did_document)
            return self._send_json(404, {"error": "not found", "path": path})

        def do_POST(self):
            # 7.3.1 d) / 9.1.2 a) one trace id per call, inherited when upstream
            # already assigned one so a multi-gateway chain stays one chain.
            trace_id = self.headers.get("X-AUIB-Trace-Id") or uuid.uuid4().hex
            started = _dt.datetime.now()
            forward_target = self.headers.get("X-AUIB-Forward-Protocol")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                return self._rpc_error(None, -32700, "parse error", trace_id)
            rid = req.get("id")
            method = req.get("method")
            if req.get("jsonrpc") != JSONRPC_VERSION:
                return self._rpc_error(rid, -32600, "invalid request: jsonrpc must be '2.0'",
                                       trace_id)
            if method not in _METHODS:
                return self._rpc_error(rid, -32601, "method not found: %s" % method, trace_id)
            try:
                result = adapter.dispatch(method, req.get("params"), trace_id=trace_id)
            except state_mod.AgentBlocked as exc:
                # 6.1.3 b) a state refusal is a policy answer, not a params error.
                duration = (_dt.datetime.now() - started).total_seconds() * 1000.0
                adapter.metrics.observe(method, duration, blocked=True,
                                        result="BLOCKED")
                adapter.journal.record({"trace": trace_id, "method": method,
                                        "type": "blocked", "agent": exc.agent,
                                        "state": exc.state,
                                        "duration_ms": round(duration, 2)})
                body = json.dumps({"jsonrpc": JSONRPC_VERSION, "id": rid,
                                   "error": {"code": -32001,
                                             "message": str(exc),
                                             "data": {"agent": exc.agent,
                                                      "state": exc.state,
                                                      "clause": exc.clause}},
                                   "traceId": trace_id}).encode("utf-8")
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-AUIB-Trace-Id", trace_id)
                self.end_headers()
                self.wfile.write(body)
                return
            except (ValueError, FileNotFoundError) as exc:
                duration = (_dt.datetime.now() - started).total_seconds() * 1000.0
                adapter.metrics.observe(method, duration, error=True, result="PARAMS")
                adapter.journal.record({"trace": trace_id, "method": method,
                                        "type": "rejected", "reason": str(exc)[:160],
                                        "duration_ms": round(duration, 2)})
                return self._rpc_error(rid, -32602, "invalid params: %s" % exc, trace_id)
            except Exception as exc:  # verify failures etc. are results, not errors
                duration = (_dt.datetime.now() - started).total_seconds() * 1000.0
                adapter.metrics.observe(method, duration, error=True, result="ERROR")
                adapter.journal.record({"trace": trace_id, "method": method,
                                        "type": "error", "reason": str(exc)[:160],
                                        "duration_ms": round(duration, 2)})
                return self._rpc_error(rid, -32000, "internal error: %s" % exc, trace_id)

            # 9.1.1 a)/8.2.1 a-b) one record per call: who, what, how long, and
            # which slot the headers were mapped into when forwarding onward.
            duration = (_dt.datetime.now() - started).total_seconds() * 1000.0
            label = "OK"
            if isinstance(result, dict):
                label = (result.get("result") or result.get("decision")
                         or ("REFUSED" if result.get("refused") else "OK"))
            mapped = (templates_mod.map_headers(dict(self.headers), forward_target)
                      if forward_target else None)
            adapter.journal.record({"trace": trace_id, "method": method,
                                    "agent": (req.get("params") or {}).get("agent"),
                                    "result": label,
                                    "duration_ms": round(duration, 2),
                                    "mapped_headers": mapped})
            adapter.metrics.observe(method, duration, result=str(label))
            self._send_json(200, {"jsonrpc": JSONRPC_VERSION, "id": rid,
                                  "result": result, "traceId": trace_id}, trace_id)

        def log_message(self, fmt, *args):
            pass

    return A2AHandler


def main(argv=None):
    ap = argparse.ArgumentParser(description="uibc-core A2A adapter (JSON-RPC 2.0 over HTTP)")
    ap.add_argument("--packages", required=True, help="root dir of verifiable packages")
    ap.add_argument("--card", default=os.path.join(os.path.dirname(__file__), "agent-card.json"))
    ap.add_argument("--port", type=int, default=8899)
    # Default stays loopback: binding 0.0.0.0 is a decision about who may poke
    # at this box, so it has to be typed on purpose.
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address (use 0.0.0.0 only where the operator intends "
                         "external reachability)")
    ap.add_argument("--did", default=None,
                    help="publish the DID document for this DID at /.well-known/did.json "
                         "(did:key or did:web)")
    ap.add_argument("--did-doc", default=None,
                    help="publish a DID document read from this JSON file")
    ap.add_argument("--registry", default=None,
                    help="registration metadata file (T/ISC 0174 6.1.1); once loaded "
                         "the gateway enforces 6.1.3 lifecycle on every call")
    ap.add_argument("--lifecycle-state", default=None,
                    help="persist identity states here so a suspend survives restart")
    ap.add_argument("--allow-opaque-id", action="store_true",
                    help="accept DID methods without a published resolution rule "
                         "(identifier unverifiable; recorded as a warning)")
    ap.add_argument("--journal", default=None,
                    help="append access/exception records to this JSONL file (9.1.1)")
    ap.add_argument("--routes", default=None,
                    help="persist versioned route table here (8.1.1 a)")
    ap.add_argument("--latency-budget-ms", type=float, default=250.0,
                    help="declared forwarding latency budget; exceeding it is "
                         "counted, not hidden (8.2.1 a)")
    ap.add_argument("--backup-dir", default=None,
                    help="state snapshot directory for 6.3.1/6.3.2 backup, "
                         "integrity check and restore")
    args = ap.parse_args(argv)

    did_document = None
    if args.did_doc:
        with open(args.did_doc, "r", encoding="utf-8") as f:
            did_document = json.load(f)
    elif args.did:
        try:
            did_document = did_mod.resolve(args.did)
        except Exception as exc:
            ap.error("cannot build the DID document for %s: %s" % (args.did, exc))

    try:
        adapter = A2AAdapter(args.packages, args.card, did_document=did_document,
                             registry=args.registry,
                             lifecycle_state=args.lifecycle_state,
                             allow_opaque_id=args.allow_opaque_id,
                             journal_path=args.journal,
                             routes_path=args.routes,
                             latency_budget_ms=args.latency_budget_ms,
                             backup_root=args.backup_dir)
    except ValueError as exc:
        ap.error(str(exc))
    srv = ThreadingHTTPServer((args.host, args.port), make_handler(adapter))
    print("uibc-core A2A adapter on http://%s:%d (methods: %s)"
          % (args.host, args.port, ", ".join(_METHODS)))
    print("  discovery: GET /agent-card.json  GET /.well-known/did.json  GET /healthz")
    if adapter.registry_report:
        print("  registry: %d agent(s), %d warning(s), state file: %s"
              % (len(adapter.registry_report["agents"]),
                 len(adapter.registry_report["warnings"]),
                 args.lifecycle_state or "(memory only)"))
    srv.serve_forever()


if __name__ == "__main__":
    main()
