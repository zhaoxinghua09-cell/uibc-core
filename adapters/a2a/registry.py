"""Agent registration metadata for the A2A gateway adapter.

Clause anchor: T/ISC 0174-2026 section 6.1.1 (智能体注册).

    6.1.1 a) 应支持智能体在接入网关时提交完整的元数据注册信息，包含智能体名称、
            唯一标识、能力描述、支持协议、通信端点、所属组织等字段；
    6.1.1 b) 应支持元数据的校验机制，确保注册信息的规范性、完整性与真实性，
            宜支持身份标识与所属组织、服务端点及可验证凭据的绑定与校验；

This module answers exactly two questions a gateway must answer before it
forwards anything: is a registration record complete (a), and does it hold
together (b)?

Three design decisions, each with the failure it prevents:

  * Fail closed. If any R-code error is present the record set is not loaded at
    all. A gateway that forwards on a half-valid registry is worse than one that
    refuses to start, because the refusal is visible and the forwarding is not.

  * Unknown is not false. What we cannot check (an organization identifier we
    have no registry for, a credential format we do not parse) yields a W-code
    warning, and the conformance report prints PARTIAL rather than PASS.
    Upgrading "unknown" to "pass" is exactly how conformance claims rot.

  * No fabricated resolution. did:cn:agent / did:ioa / did:wba have no published
    resolution rule in this build, so they are accepted as identifiers only when
    allow_opaque_id is on, and every such record carries a W-code saying so.
"""

import json
import os
from urllib.parse import urlparse

try:
    from uibc_core.did import DIDError, SUPPORTED_METHODS, parse as _did_parse
except Exception:  # pragma: no cover - adapter run from a flat directory
    DIDError = ValueError
    SUPPORTED_METHODS = ("key", "web")

    def _did_parse(_did):
        raise DIDError("did parser unavailable")


CLAUSE_META = "6.1.1a"
CLAUSE_BIND = "6.1.1b"
CLAUSE_LIFE = "6.1.3a"

REQUIRED_FIELDS = ("name", "id", "capabilities", "protocols",
                   "endpoint", "organization")
STATES = ("registered", "enabled", "suspended", "revoked")
KNOWN_PROTOCOLS = ("a2a", "a2a/1.0", "a2a-1.0", "jsonrpc-2.0", "json-rpc-2.0",
                   "mcp", "http", "https", "sse", "websocket", "grpc")


def _issue(code, clause, agent, field, message):
    return {"code": code, "clause": clause, "agent": agent,
            "field": field, "message": message}


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _iso(value):
    """Parse an ISO-8601 timestamp; return None when it is not one."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        import datetime as _dt
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_agent(agent, allow_opaque_id=False, now=None):
    """Validate one registration record. Returns (errors, warnings, record)."""
    errors, warnings = [], []
    label = None
    if not isinstance(agent, dict):
        return ([_issue("R1", CLAUSE_META, None, None,
                        "each agent entry must be a JSON object")], [], None)

    label = _text(agent.get("name")) or _text(agent.get("id")) or "?"

    for field in REQUIRED_FIELDS:
        raw = agent.get(field)
        empty = (raw is None or (isinstance(raw, str) and not raw.strip())
                 or (isinstance(raw, (list, dict)) and not raw))
        if empty:
            errors.append(_issue("R1", CLAUSE_META, label, field,
                                 "required registration field is missing or empty: %s" % field))

    # 6.1.1 a) 唯一标识 -----------------------------------------------------
    did_value = _text(agent.get("id"))
    if did_value:
        if not did_value.startswith("did:"):
            errors.append(_issue("R2", CLAUSE_META, label, "id",
                                 "unique identifier must be a DID, got %r" % did_value[:40]))
        else:
            try:
                parsed_did = _did_parse(did_value)
                # did.parse returns (method, method_specific_id).
                method = parsed_did[0] if isinstance(parsed_did, (tuple, list)) else parsed_did
                if method not in SUPPORTED_METHODS and not allow_opaque_id:
                    errors.append(_issue(
                        "R3", CLAUSE_META, label, "id",
                        "did:%s has no published resolution rule in this build "
                        "(supported: %s); pass allow_opaque_id to register it as an "
                        "opaque identifier" % (method, ", ".join(SUPPORTED_METHODS))))
                elif method not in SUPPORTED_METHODS:
                    warnings.append(_issue(
                        "W0", CLAUSE_META, label, "id",
                        "did:%s registered as opaque: identifier accepted, key "
                        "resolution unverifiable" % method))
            except DIDError as exc:
                errors.append(_issue("R2", CLAUSE_META, label, "id",
                                     "unparsable DID: %s" % exc))

    # 6.1.1 a) 通信端点 ------------------------------------------------------
    endpoint = _text(agent.get("endpoint"))
    if endpoint:
        parsed = urlparse(endpoint)
        if parsed.scheme not in ("http", "https"):
            errors.append(_issue("R4", CLAUSE_META, label, "endpoint",
                                 "endpoint must be http(s), got scheme %r"
                                 % (parsed.scheme or "")))
        elif not parsed.hostname:
            errors.append(_issue("R4", CLAUSE_META, label, "endpoint",
                                 "endpoint has no host"))
        elif parsed.username or parsed.password:
            errors.append(_issue("R4", CLAUSE_META, label, "endpoint",
                                 "endpoint must not embed credentials"))
        elif parsed.fragment:
            errors.append(_issue("R4", CLAUSE_META, label, "endpoint",
                                 "endpoint must not carry a fragment"))
        elif parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            warnings.append(_issue("W6", CLAUSE_META, label, "endpoint",
                                   "plain http on a routable host: 9.1.4 a) wants TLS"))

    # 6.1.1 a) 能力描述 ------------------------------------------------------
    caps = agent.get("capabilities")
    if isinstance(caps, list) and caps:
        for cap in caps:
            if not isinstance(cap, dict) or not _text(cap.get("name")):
                errors.append(_issue("R5", CLAUSE_META, label, "capabilities",
                                     "each capability needs a name"))
                break
            if not _text(cap.get("description")):
                warnings.append(_issue("W5", CLAUSE_META, label, "capabilities",
                                       "capability %r has no description: callers "
                                       "cannot rank it semantically (8.1.2 a)"
                                       % _text(cap.get("name"))))
    elif caps is not None and not isinstance(caps, list):
        errors.append(_issue("R5", CLAUSE_META, label, "capabilities",
                             "capabilities must be a list"))

    # 6.1.1 a) 支持协议 ------------------------------------------------------
    protocols = agent.get("protocols")
    if isinstance(protocols, list) and protocols:
        for proto in protocols:
            if not _text(proto):
                errors.append(_issue("R6", CLAUSE_META, label, "protocols",
                                     "protocol entries must be non-empty strings"))
                break
            if _text(proto).lower() not in KNOWN_PROTOCOLS:
                warnings.append(_issue("W4", CLAUSE_META, label, "protocols",
                                       "protocol %r is not in the adapter's known set; "
                                       "forwarding will be attempted without adapter "
                                       "logic" % _text(proto)))
    elif protocols is not None and not isinstance(protocols, list):
        errors.append(_issue("R6", CLAUSE_META, label, "protocols",
                             "protocols must be a list"))

    # 6.1.1 a) 所属组织 ------------------------------------------------------
    org = agent.get("organization")
    if isinstance(org, dict):
        if not _text(org.get("name")):
            errors.append(_issue("R7", CLAUSE_META, label, "organization",
                                 "organization.name is required"))
        elif not _text(org.get("identifier")):
            warnings.append(_issue("W1", CLAUSE_BIND, label, "organization",
                                   "organization has no identifier: identity-to-"
                                   "organization binding cannot be checked (6.1.1 b)"))
    elif org is not None:
        errors.append(_issue("R7", CLAUSE_META, label, "organization",
                             "organization must be an object with a name"))

    # 6.1.3 a) 生命周期字段 --------------------------------------------------
    state = _text(agent.get("state")) or "registered"
    if state not in STATES:
        errors.append(_issue("R9", CLAUSE_LIFE, label, "state",
                             "state %r is not one of %s"
                             % (state, ", ".join(STATES))))

    record = {
        "name": _text(agent.get("name")),
        "id": did_value,
        "capabilities": caps if isinstance(caps, list) else [],
        "protocols": [_text(p) for p in protocols] if isinstance(protocols, list) else [],
        "endpoint": endpoint,
        "organization": org if isinstance(org, dict) else {},
        "state": state,
        "vc": agent.get("vc") if isinstance(agent.get("vc"), dict) else None,
        "authorization": agent.get("authorization") if isinstance(agent.get("authorization"), dict) else None,
        "updated_at": agent.get("updated_at"),
        "meta": agent.get("meta") if isinstance(agent.get("meta"), dict) else {},
    }
    return errors, warnings, record


def binding_report(record, now=None):
    """6.1.1 b) identity-to-{organization, endpoint, credential} binding.

    Returns a list of {"code","ok","clause","detail"}. ``ok=False`` is a real
    violation; ``ok=None`` means the field is absent and the binding is
    therefore unverifiable - which the caller must not render as a pass.
    """
    out = []
    org = record.get("organization") or {}
    vc = record.get("vc")
    endpoint = record.get("endpoint") or ""
    did_value = record.get("id") or ""

    # B1 organization identifier present
    org_id = _text(org.get("identifier"))
    out.append({"code": "B1", "clause": CLAUSE_BIND,
                "ok": bool(org_id),
                "detail": "organization identifier %s" % (org_id or "absent")})

    # B2 did:web host must equal endpoint host
    if did_value.startswith("did:web:"):
        # did:web:<host>[:path...] - the host segment is the authority.
        segments = did_value.split(":")[2:]
        expected = (segments[0] if segments else "").lower()
        host = (urlparse(endpoint).hostname or "").lower()
        out.append({"code": "B2", "clause": CLAUSE_BIND,
                    "ok": bool(host) and host == expected,
                    "detail": "did:web host %r vs endpoint host %r" % (expected, host)})

    # B3 credential present
    if not isinstance(vc, dict):
        out.append({"code": "B3", "clause": CLAUSE_BIND, "ok": None,
                    "detail": "no verifiable credential supplied: binding unverifiable"})
    else:
        issuer = _text(vc.get("issuer"))
        out.append({"code": "B4", "clause": CLAUSE_BIND,
                    "ok": bool(issuer) and issuer.startswith("did:"),
                    "detail": "vc issuer %s" % (issuer or "absent")})
        out.append({"code": "B5", "clause": CLAUSE_BIND,
                    "ok": _text(vc.get("status") or "active").lower() == "active",
                    "detail": "vc status %s" % (vc.get("status") or "active")})
        expires = _iso(vc.get("valid_until"))
        if expires is None:
            out.append({"code": "B6", "clause": CLAUSE_BIND, "ok": None,
                        "detail": "vc has no parseable valid_until: expiry unverifiable"})
        else:
            import datetime as _dt
            current = now or _dt.datetime.now(_dt.timezone.utc)
            if current.tzinfo is None:
                current = current.replace(tzinfo=_dt.timezone.utc)
            out.append({"code": "B6", "clause": CLAUSE_BIND,
                        "ok": expires >= current,
                        "detail": "vc valid_until %s vs now %s"
                        % (expires.isoformat(), current.isoformat())})

    # B7 authorization scope present (feeds 9.2.1 a / 6.1.3 b resume)
    auth = record.get("authorization") or {}
    scopes = auth.get("scopes") if isinstance(auth.get("scopes"), list) else []
    out.append({"code": "B7", "clause": CLAUSE_BIND,
                "ok": bool(scopes),
                "detail": "authorization scopes %s" % (scopes or "absent")})
    return out


def validate(doc, allow_opaque_id=False, now=None):
    """Validate a whole registry document.

    Returns {"ok", "errors", "warnings", "agents"}; ``ok`` is False when any
    error exists, so callers can adopt a single fail-closed rule.
    """
    errors, warnings, agents = [], [], []
    if not isinstance(doc, dict):
        return {"ok": False, "schema": None, "errors": [
            _issue("R0", CLAUSE_META, None, None, "registry must be a JSON object")],
            "warnings": [], "agents": []}

    raw_agents = doc.get("agents")
    if not isinstance(raw_agents, list) or not raw_agents:
        errors.append(_issue("R0", CLAUSE_META, None, "agents",
                             "registry must contain a non-empty agents list"))
        return {"ok": False, "schema": doc.get("schema"), "errors": errors,
                "warnings": warnings, "agents": []}

    seen_ids, seen_names = {}, {}
    for index, raw in enumerate(raw_agents):
        errs, warns, record = validate_agent(raw, allow_opaque_id=allow_opaque_id, now=now)
        errors.extend(errs)
        warnings.extend(warns)
        if record is None:
            continue
        label = record["name"] or record["id"] or "#%d" % index
        if record["id"]:
            if record["id"] in seen_ids:
                errors.append(_issue("R8", CLAUSE_META, label, "id",
                                     "duplicate identifier also used by %r"
                                     % seen_ids[record["id"]]))
            else:
                seen_ids[record["id"]] = label
        if record["name"]:
            if record["name"] in seen_names:
                errors.append(_issue("R8", CLAUSE_META, label, "name",
                                     "duplicate name also used by %r"
                                     % seen_names[record["name"]]))
            else:
                seen_names[record["name"]] = label
        agents.append(record)

    return {"ok": not errors, "schema": doc.get("schema"), "errors": errors,
            "warnings": warnings, "agents": agents}


def load(path, allow_opaque_id=False, now=None):
    """Read and validate a registry file. Raises ValueError when it is invalid."""
    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    report = validate(doc, allow_opaque_id=allow_opaque_id, now=now)
    report["path"] = os.path.abspath(path)
    if not report["ok"]:
        raise ValueError("invalid gateway registry %s: %s" % (
            path, "; ".join("%s(%s): %s" % (e["code"], e["field"] or "-", e["message"])
                            for e in report["errors"][:6])))
    return report
