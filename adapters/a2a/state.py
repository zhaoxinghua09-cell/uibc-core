"""Identity lifecycle gate for the A2A gateway adapter.

Clause anchor: T/ISC 0174-2026 section 6.1.3 (生命周期管理).

    6.1.3 a) 应支持智能体身份全生命周期闭环管理，覆盖注册、启用、停用、注销等核心阶段；
    6.1.3 b) 应支持身份状态变更在本网关内即时生效，如停用后立即阻断该智能体所有通信，
            恢复后重新校验身份状态、凭据有效性及当前授权策略，校验通过后恢复相应通信权限。

The operational reading of 6.1.3 b) is the whole point of this module:

  * 停用 must block *communication*, not merely hide the agent from a list. That
    is why the adapter asks this store on every dispatch (require_active) instead
    of trusting a metadata field that a caller could have cached.
  * 恢复 must re-run the checks, not flip one flag. resume() therefore re-validates
    identity state, credential validity and the authorization policy, and refuses
    when any of them is unknown - a gateway that resumes on "probably fine" is the
    exact failure the clause is written against.
  * The state must survive a restart, so transitions are persisted when a path is
    given; an in-memory-only suspend would silently un-block on restart.

Terminality: 注销 (revoked) admits no later transition. There is no "unsuspend
after revoke" path, and saying so in code is cheaper than arguing about it later.
"""

import datetime as _dt
import json
import os
import threading

from adapters.a2a.registry import binding_report

REGISTERED = "registered"
ENABLED = "enabled"
SUSPENDED = "suspended"
REVOKED = "revoked"

STATES = (REGISTERED, ENABLED, SUSPENDED, REVOKED)
TRANSITIONS = {
    REGISTERED: (ENABLED, REVOKED),
    ENABLED: (SUSPENDED, REVOKED),
    SUSPENDED: (ENABLED, REVOKED),   # ENABLED only through resume()
    REVOKED: (),
}
_ACTION_STATE = {"enable": ENABLED, "suspend": SUSPENDED,
                 "resume": ENABLED, "revoke": REVOKED}

CLAUSE = "6.1.3b"


class LifecycleError(ValueError):
    """Illegal transition request (caller error, not a policy decision)."""


class UnknownAgent(LifecycleError):
    pass


class AgentBlocked(Exception):
    """Communication refused because of identity state (6.1.3 b).

    Carries the state so the adapter can answer with a reason a human can act on
    instead of a generic 403.
    """

    def __init__(self, agent, state, clause=CLAUSE):
        Exception.__init__(self, "agent %s is %s: communication blocked" % (agent, state))
        self.agent = agent
        self.state = state
        self.clause = clause


class LifecycleStore:
    def __init__(self, records=None, path=None, now=None):
        self._lock = threading.RLock()
        self._records = {}
        self._states = {}
        self._audit = []
        self.path = os.path.abspath(path) if path else None
        self._clock = now or (lambda: _dt.datetime.now(_dt.timezone.utc))
        for record in records or []:
            self.register(record, actor="registry")

    # -- helpers -----------------------------------------------------------
    def _ts(self):
        return self._clock().isoformat()

    def _log(self, agent, action, from_state, to_state, reason, actor):
        self._audit.append({"ts": self._ts(), "agent": agent, "action": action,
                            "from": from_state, "to": to_state,
                            "reason": reason or "", "actor": actor or ""})

    def _require(self, agent_id):
        if agent_id not in self._states:
            raise UnknownAgent("unknown agent: %r" % (agent_id,))
        return self._states[agent_id]

    def _apply(self, agent_id, action, reason=None, actor=None):
        current = self._require(agent_id)
        target = _ACTION_STATE[action]
        if action != "resume" and target not in TRANSITIONS[current]:
            raise LifecycleError("illegal transition for %s: %s -> %s (%s)"
                                 % (agent_id, current, target, action))
        self._states[agent_id] = target
        self._log(agent_id, action, current, target, reason, actor)
        self._persist()
        return target

    def _persist(self):
        if not self.path:
            return
        payload = {"schema": "uibc-gateway-lifecycle/1",
                   "updated_at": self._ts(),
                   "states": dict(self._states),
                   "audit": self._audit[-200:]}
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            # Persistence is a durability aid, not the security boundary: never
            # let a disk error resurrect a suspended agent *in memory* either.
            pass

    # -- transitions -------------------------------------------------------
    def register(self, record, actor="operator"):
        agent_id = record.get("id") or record.get("name")
        if not agent_id:
            raise LifecycleError("record has neither id nor name")
        with self._lock:
            self._records[agent_id] = record
            declared = record.get("state") or REGISTERED
            self._states[agent_id] = declared if declared in STATES else REGISTERED
            self._log(agent_id, "register", None, self._states[agent_id], "", actor)
            self._persist()
        return self._states[agent_id]

    def enable(self, agent_id, actor="operator"):
        with self._lock:
            return self._apply(agent_id, "enable", "", actor)

    def suspend(self, agent_id, reason="", actor="operator"):
        with self._lock:
            return self._apply(agent_id, "suspend", reason, actor)

    def revoke(self, agent_id, reason="", actor="operator"):
        with self._lock:
            return self._apply(agent_id, "revoke", reason, actor)

    def resume(self, agent_id, now=None, actor="operator"):
        """Re-validate before un-blocking (6.1.3 b).

        Returns (ok, violations). ok is False whenever *any* check is not a
        positive yes - a missing credential is a refusal, not a pass.
        """
        with self._lock:
            current = self._require(agent_id)
            if current != SUSPENDED:
                raise LifecycleError("resume only applies to a suspended agent, %s is %s"
                                     % (agent_id, current))
            record = self._records.get(agent_id) or {}
            checks = binding_report(record, now=now)
            violations = [{"code": c["code"], "detail": c["detail"]}
                          for c in checks if c["ok"] is not True]
            if not checks:
                violations = [{"code": "B0", "detail": "no binding checks available"}]
            if violations:
                self._log(agent_id, "resume-refused", current, current,
                          json.dumps(violations, ensure_ascii=False), actor)
                self._persist()
                return False, violations
            self._states[agent_id] = ENABLED
            self._log(agent_id, "resume", current, ENABLED, "", actor)
            self._persist()
            return True, []

    # -- enforcement -------------------------------------------------------
    def state(self, agent_id):
        with self._lock:
            return self._require(agent_id)

    def require_active(self, agent_id):
        """Raise AgentBlocked unless the agent is enabled *right now*."""
        state = self.state(agent_id)
        if state != ENABLED:
            raise AgentBlocked(agent_id, state)

    def is_enabled(self, agent_id):
        with self._lock:
            return self._states.get(agent_id) == ENABLED

    def agents(self):
        with self._lock:
            return sorted(self._states.keys())

    def audit(self):
        with self._lock:
            return list(self._audit)

    def snapshot(self):
        with self._lock:
            return {"schema": "uibc-gateway-lifecycle/1",
                    "updated_at": self._ts(),
                    "states": dict(self._states),
                    "audit_entries": len(self._audit)}


def load_states(path):
    """Read previously persisted states, for restart durability."""
    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    return doc.get("states") or {}
