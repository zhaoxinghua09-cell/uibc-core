"""Per-call permission check (T/ISC 0174 9.2.1 a)).

The registry already declares `authorization.scopes` per agent. Declaring a
scope and then answering every call regardless is the difference between a
policy and a comment. This module turns the declaration into a decision:

    caller scope  ⊆  scopes granted to the agent being called

Accepted scope spellings (all seen in the wild, all cheap to match):
    "verify"        bare permission
    "uibc/verify"   method-style
    "uibc:verify"   urn-style
    "*" / "uibc/*"  whole gateway

A call is refused when the caller names a scope the record does not grant,
when the caller names no scope at all, or when the record has no scopes
(because then nothing is granted).
"""

from __future__ import annotations

CLAUSE = "9.2.1 a)"

# method -> permission the method requires
_METHOD_PERMISSION = {
    "uibc/verify": "verify",
    "uibc/gate": "gate",
    "uibc/inspect": "inspect",
}

# A narrower grant may still cover a wider read: gate is a decision over the
# same evidence as verify, inspect shows the same identity fields. Anything
# wider than the grant (e.g. only "gate" asking for "inspect") is still denied.
_ALIASES = {
    "verify": {"verify"},
    "gate": {"gate", "verify"},
    "inspect": {"inspect", "verify"},
}


def permission_for(method):
    return _METHOD_PERMISSION.get(method)


def _normalise(token):
    token = str(token).strip().lower()
    for sep in (":", "/"):
        token = token.replace(sep + "*", "*")
    return token


def granted(record):
    auth = (record or {}).get("authorization") or {}
    scopes = auth.get("scopes") if isinstance(auth.get("scopes"), list) else []
    return {_normalise(s) for s in scopes}


def allows(scope_tokens, method):
    """True when the declared scope tokens cover this method's permission."""
    perm = permission_for(method)
    if perm is None:
        return True
    tokens = {_normalise(t) for t in (scope_tokens or [])}
    if not tokens:
        return False
    if tokens & {"*", "uibc/*", "uibc:*"}:
        return True
    acceptable = _ALIASES.get(perm, {perm})
    candidates = set()
    for name in acceptable:
        candidates |= {name, "uibc/" + name, "uibc:" + name}
    return bool(tokens & candidates)


def _record_for(adapter, agent):
    for record in (adapter.registry_report or {}).get("agents", []):
        if record.get("id") == agent:
            return record
    return None


class ScopeDenied(Exception):
    clause = CLAUSE

    def __init__(self, agent, method, granted_scopes, declared):
        self.agent = agent
        self.method = method
        self.granted = sorted(granted_scopes)
        self.declared = list(declared or [])
        super().__init__("9.2.1 a) scope not granted: agent=%s method=%s granted=%s"
                         % (agent, method, self.granted or "none"))


def enforce(adapter, method, params, caller_scopes=None):
    """Raise ScopeDenied, or return the decision that was made (for the journal).

    Two checks, in this order:
      1. the agent's own record must grant the permission;
      2. when the caller states its scopes, those must cover it as well.
    A caller that states nothing is accepted only on check 1, and the decision
    says so (`basis: "transport-peer"`) rather than pretending it authenticated
    anyone: peer identity is the reverse proxy's job (deploy/nginx-gateway.conf).
    """
    perm = permission_for(method)
    if perm is None:
        return {"enforced": False, "reason": "no permission bound to %s" % method}
    agent = (params or {}).get("agent")
    record = _record_for(adapter, agent)
    if record is None:
        raise ScopeDenied(agent, method, [], caller_scopes)
    grants = granted(record)
    declared = caller_scopes
    if declared is None:
        declared = (params or {}).get("caller_scope") or (params or {}).get("caller_scopes")
        if isinstance(declared, str):
            declared = [declared]
    if declared and not allows(declared, method):
        raise ScopeDenied(agent, method, grants, declared)
    if not allows(grants, method):
        raise ScopeDenied(agent, method, grants, declared)
    return {"enforced": True, "permission": perm, "agent": agent,
            "declared": list(declared or []),
            "basis": "caller-scope" if declared else "transport-peer",
            "granted": sorted(grants)}
