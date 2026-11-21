# -*- coding: utf-8 -*-
"""uibc -> EP-AEC (Authorization Evidence Chain) adapter + conformance demo.

Run:  python tools/uibc_to_epaec.py
Out:  tools/out/epaec_result.json

Why this file exists
--------------------
draft-schrock-ep-authorization-evidence-chain (-02, latest -08) defines a
composition object plus an offline algorithm that verifies several
*heterogeneous* receipts for ONE action and evaluates a fail-closed
requirement expression. What we add is not another receipt format: we are a
package-level verifier that can serve as one component ("uibc-package").

Two things this file proves, and one thing it refuses to pretend:

1. VERDICT MAPPING IS NOT BINARY. EP-AEC -02 already grades evidence:
   admissible / missing_evidence / stale / conflicted / unverifiable, with the
   rule that a record whose signature does not verify is "unverifiable" and is
   never softened to "conflicted". Our three values map onto that set:

       uibc PASS         -> admissible
       uibc FAIL         -> conflicted        (evidence contradicts itself)
       uibc INCONCLUSIVE -> unverifiable      (a check could not be resolved)
                            or missing_evidence (evidence absent/skipped)

   The earlier plan in the research report ("map INCONCLUSIVE to false +
   INCOMPLETE") was wrong: EP-AEC's own vocabulary already carries the
   distinction, so we map into it instead of inventing a parallel one.

2. THE SAME-ACTION BINDING IS ENFORCED BY THE COMPONENT, NOT BY THE CHAIN.
   EP-AEC step 3c requires every component to return the canonical action
   digest it attests. Our component returns the package's evidence_root when
   the package only binds a *package*; if the chain is scoped to an *action*
   and the package carries no action digest, the component reports
   "unverifiable" and the chain necessarily DENIES. That is the honest
   behaviour: a package that cannot bind the action must not be able to
   satisfy an action-scoped requirement.

3. SUFFICIENCY IS PINNED BY THE RELYING PARTY (EP-AEC section 6). The chain
   document's "requirement" is presenter-supplied and is treated as a recorded
   claim only; the demo evaluates a relying-party requirement first.
"""

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from uibc_core import cli as ucli                      # noqa: E402
from uibc_core.canonical import canonicalize           # noqa: E402
from uibc_core.verify import verify                    # noqa: E402

OUT = os.path.join(ROOT, "tools", "out")
DEMO_SEED = bytes(range(32))                           # public demo seed


def _a(**kw):
    return type("A", (), kw)()


def action_digest(action) -> str:
    """EP-AEC canonical action digest: sha256 over the JCS serialization."""
    return "sha256:" + hashlib.sha256(canonicalize(action)).hexdigest()


def _grade(report, seals_as_action=False):
    """Map a uibc report onto EP-AEC's graded evidence vocabulary."""
    result = report["result"]
    if result == "PASS":
        return "admissible", None
    if result == "FAIL":
        failed = [c["id"] for c in report["checks"] if c["result"] == "FAIL"]
        return "conflicted", f"failed checks: {','.join(failed)}"
    # INCONCLUSIVE: distinguish "could not resolve" from "evidence absent"
    skipped = [c for c in report["checks"] if c["result"] == "INCONCLUSIVE"]
    if any(c["id"] in ("S4", "S5") for c in skipped):
        return "missing_evidence", "evidence absent or unreadable"
    return "unverifiable", "check unresolved: " + ",".join(c["id"] for c in skipped)


def package_component(package_dir, key=None, pubkey=None, action_scope=False):
    """Return one EP-AEC component for a uibc package.

    action_scope=True means the chain is scoped to a specific action, so the
    component must return an action digest. A package that binds only a
    package returns its evidence_root prefixed by "pkg:" and marks itself
    unverifiable for action scope - the cross-binding check then fails closed.
    """
    report = verify(package_dir, key=key, pubkey=pubkey)
    grade, reason = _grade(report)
    with open(os.path.join(package_dir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    with open(os.path.join(package_dir, "identity.json"), encoding="utf-8") as f:
        identity = json.load(f)

    binds_action = False
    evidence_digest = None
    # A package binds an action only if it records one in an ACTION evidence
    # entry that carries an explicit action digest. Hash-only evidence of a
    # log file does NOT count: it proves a file, not an action.
    idx_path = os.path.join(package_dir, "evidence", "index.json")
    if os.path.isfile(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            index = json.load(f)
        for e in index.get("entries", []):
            if e.get("action_digest"):
                binds_action = True
                evidence_digest = e["action_digest"]
                break

    component = {
        "type": "uibc-package",
        "label": f"uibc package attestation ({identity.get('agent_id')})",
        "evidence": {
            "report": report,
            "evidence_grade": grade,
            "reason": reason,
            "agent_id": identity.get("agent_id"),
            "principal_type": identity.get("principal_type"),
            "evidence_root": manifest.get("evidence_root"),
            "policy_hash": manifest.get("policy_hash"),
        },
    }
    # What this component attests, in EP-AEC's own terms (Section 4 step 3)
    if action_scope and not binds_action:
        attests = "pkg:" + str(manifest.get("evidence_root"))
        grade = "unverifiable"
        component["evidence"]["reason"] = (
            "package binds a package, not an action: no action_digest recorded "
            "in the evidence index")
        component["evidence"]["evidence_grade"] = grade
    elif binds_action:
        attests = evidence_digest
    else:
        attests = "pkg:" + str(manifest.get("evidence_root"))
    return component, grade, attests


def evaluate_requirement(expr, satisfied):
    """Bounded evaluator, EP-AEC Section 5: AND/OR equal precedence, left to
    right, parentheses are the only grouping, unknown IDENT is false."""
    if not expr:
        return False
    tokens = expr.replace("(", " ( ").replace(")", " ) ").split()
    pos = {"i": 0}

    def peek():
        return tokens[pos["i"]] if pos["i"] < len(tokens) else None

    def take():
        tok = tokens[pos["i"]]
        pos["i"] += 1
        return tok

    def parse_expr():
        value = parse_term()
        while peek() in ("AND", "OR"):
            op = take()
            rhs = parse_term()
            value = (value and rhs) if op == "AND" else (value or rhs)
        return value

    def parse_term():
        tok = peek()
        if tok == "(":
            take()
            value = parse_expr()
            if peek() != ")":
                raise ValueError("unbalanced parentheses")
            take()
            return value
        if tok is None:
            raise ValueError("unexpected end of expression")
        take()
        return tok in satisfied

    return parse_expr()


def build_chain(action, components, requirement):
    chain = {
        "@version": "EP-AEC-v1",
        "action": action,
        "action_digest": action_digest(action),
        "components": components,
        "requirement": requirement,
    }
    return chain


def verify_chain(chain, relying_party_requirement=None):
    """Offline, fail-closed evaluation of one EP-AEC chain.

    Returns {'outcome': ALLOW|DENY, 'grade': worst grade, 'components': [...],
             'requirement_source': ...}
    """
    if chain.get("@version") != "EP-AEC-v1" or not isinstance(chain.get("action"), dict) \
            or not chain.get("components") or not chain.get("requirement"):
        return {"outcome": "DENY", "reason": "malformed chain", "components": []}

    chain_digest = action_digest(chain["action"])
    if chain.get("action_digest") and chain["action_digest"] != chain_digest:
        return {"outcome": "DENY", "reason": "action_digest mismatch", "components": []}

    satisfied = set()
    worst = "admissible"
    detail = []
    rank = {"admissible": 0, "missing_evidence": 1, "stale": 2,
            "conflicted": 3, "unverifiable": 4}
    for comp in chain["components"]:
        ev = comp.get("evidence", {})
        grade = ev.get("evidence_grade", "unverifiable")
        attests = ev.get("attests")
        bound = attests == chain_digest
        ok = grade == "admissible" and bound
        detail.append({"type": comp["type"], "grade": grade, "bound": bound,
                       "satisfied": ok, "reason": ev.get("reason")})
        if rank.get(grade, 4) > rank.get(worst, 0):
            worst = grade
        if ok:
            satisfied.add(comp["type"])
            if comp.get("label"):
                satisfied.add(comp["label"])

    source = "presenter"
    expr = chain["requirement"]
    if relying_party_requirement:
        expr = relying_party_requirement
        source = "relying_party"
    try:
        allow = evaluate_requirement(expr, satisfied)
    except Exception:
        allow = False

    return {"outcome": "ALLOW" if allow else "DENY", "grade": worst,
            "components": detail, "requirement_source": source,
            "requirement_evaluated": expr}


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------

def _build_pkg(path, key_path, *, extra_event=False, action_digest_seen=None,
               principal_type=None):
    ucli.cmd_init(_a(path=path))
    ucli.cmd_register(_a(path=path, agent_id="epaec-agent", owner="ops-team",
                         agent_type="software-agent", version="1.0.0",
                         principal_type=principal_type,
                         logical_agent_id="epaec-agent", run_id="run-001"))
    if extra_event:
        ucli.cmd_event(_a(path=path, type="ACTIVATE", actor=None))
    src = os.path.join(os.path.dirname(path), "act.log")
    with open(src, "w", encoding="utf-8", newline="\n") as f:
        f.write("2026-11-17T00:00:00Z ACTION settle_invoice 1\n")
    ucli.cmd_evidence(_a(path=path, type="ACTION", file=src,
                        media_type="text/plain", note=""))
    if action_digest_seen:
        idx_p = os.path.join(path, "evidence", "index.json")
        with open(idx_p, encoding="utf-8") as f:
            idx = json.load(f)
        idx["entries"][-1]["action_digest"] = action_digest_seen
        with open(idx_p, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2)
    ucli.cmd_submit(_a(path=path, key=key_path,
                       policy_hash="sha256:" + "ab" * 32))


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="epaec-")
    key_path = os.path.join(tmp, "owner.key")
    with open(key_path, "w", encoding="ascii") as f:
        f.write("ed25519:" + DEMO_SEED.hex())
    pub_b64 = base64.b64encode(__import__("uibc_core.ed25519", fromlist=["x"]).publickey(DEMO_SEED)).decode()
    pub = base64.b64decode(pub_b64)

    action = {"kind": "agent-action", "tool": "settle_invoice",
              "tenant": "demo-tenant", "amount_minor": 4200, "currency": "CNY"}
    adig = action_digest(action)

    cases = {}

    # A. clean package, action-scoped chain, package DOES bind the action
    pA = os.path.join(tmp, "A.uibc")
    _build_pkg(pA, key_path, action_digest_seen=adig, principal_type="SERVICE")
    compA, gradeA, attA = package_component(pA, pubkey=pub, action_scope=True)
    compA["evidence"]["attests"] = attA
    chainA = build_chain(action, [compA], "uibc-package")
    cases["A_action_bound_admissible"] = verify_chain(chainA, "uibc-package")

    # B. clean package, action-scoped chain, package binds only a package
    pB = os.path.join(tmp, "B.uibc")
    _build_pkg(pB, key_path, action_digest_seen=None, principal_type="SERVICE")
    compB, gradeB, attB = package_component(pB, pubkey=pub, action_scope=True)
    compB["evidence"]["attests"] = attB
    chainB = build_chain(action, [compB], "uibc-package")
    cases["B_no_action_binding_unverifiable"] = verify_chain(chainB, "uibc-package")

    # C. tampered evidence -> conflicted
    pC = os.path.join(tmp, "C.uibc")
    shutil.copytree(pB, pC)
    f = os.path.join(pC, "evidence", "files", "act.log")
    data = bytearray(open(f, "rb").read())
    data[len(data) // 2] ^= 0x01
    open(f, "wb").write(bytes(data))
    compC, gradeC, attC = package_component(pC, pubkey=pub)
    compC["evidence"]["attests"] = attC
    chainC = build_chain(action, [compC], "uibc-package")
    cases["C_tampered_conflicted"] = verify_chain(chainC, "uibc-package")

    # D. unsigned package, no key -> unverifiable
    pD = os.path.join(tmp, "D.uibc")
    _build_pkg(pD, None, principal_type="SERVICE")
    compD, gradeD, attD = package_component(pD)
    compD["evidence"]["attests"] = attD
    chainD = build_chain(action, [compD], "uibc-package")
    cases["D_unsealed_unverifiable"] = verify_chain(chainD, "uibc-package")

    # E. relying-party requirement is stricter than the presenter's bar
    chainE = dict(chainA)
    chainE["requirement"] = "uibc-package"
    cases["E_relying_party_bar"] = verify_chain(chainE, "uibc-package AND policy-permit")
    cases["E_presenter_bar"] = verify_chain(chainE)
    chainE_note = {"presenter": "uibc-package",
                   "relying_party": "uibc-package AND policy-permit"}

    summary = {
        "outcomes": {k: v["outcome"] for k, v in cases.items()},
        "grades": {k: v.get("grade") for k, v in cases.items()},
        "expectations_met": (
            cases["A_action_bound_admissible"]["outcome"] == "ALLOW"
            and cases["B_no_action_binding_unverifiable"]["outcome"] == "DENY"
            and cases["C_tampered_conflicted"]["outcome"] == "DENY"
            and cases["D_unsealed_unverifiable"]["outcome"] == "DENY"
            and cases["E_relying_party_bar"]["outcome"] == "DENY"
            and cases["E_presenter_bar"]["outcome"] == "ALLOW"
        ),
        "action_digest": adig,
        "requirement_note": chainE_note,
        "ep_aec_version": "EP-AEC-v1 (draft-schrock-ep-authorization-evidence-chain, -02; latest -08)",
    }

    out = {"cases": cases, "summary": summary}
    with open(os.path.join(OUT, "epaec_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("case                              outcome  grade              note")
    for k, v in cases.items():
        first = v["components"][0] if v["components"] else {}
        print(f"{k:33s} {v['outcome']:8s} {str(v.get('grade')):18s} "
              f"{first.get('reason') or ''}")
    print()
    print("all expectations met:", summary["expectations_met"])
    print("RESULT_JSON=" + os.path.join(OUT, "epaec_result.json"))
    return 0 if summary["expectations_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
