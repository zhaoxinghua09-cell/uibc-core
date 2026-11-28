"""AITB open evaluation entry: score one submitted did:cn agent, reproducibly.

What this is
------------
An outsider sends a DID. This tool makes the same read-only call anyone can make,
checks the answer against rules that are written down here, and prints a report
card that names every assertion it made and every thing it did NOT test.

What this is not
----------------
It is not a certification. It does not judge conformance to any standard, it does
not verify verifiable credentials (the platform itself reports
`vcVerificationStatus: SKIPPED`), and it cannot tell you whether the operator
really owns the code -- only whether the operator said so.

Three gates
-----------
G1  reachable & registered   the platform answers, and says SUCCESS or FAILED
G2  self-consistent document the returned fields agree with each other and with
                             the published value ranges (hex length vs key type, etc.)
G3  operator acknowledgement the submitter points at a public statement by the
                             operator; absent counts as MISSING, never as PASS

Verdicts
--------
Not every submitted identifier can be scored. Saying "FAIL" for a method whose
specification never publishes a host would blame the wrong party, and saying
nothing would hide that the gap exists. So a card states one of:

    PASS                   every check that ran passed
    FAIL                   at least one check that ran failed
    NO_PUBLIC_ENDPOINT     we know of no public endpoint to call, so no check ran
    METHOD_NOT_SUPPORTED   this method is not in our table at all

NO_PUBLIC_ENDPOINT is a finding about the ecosystem, not about the submitter,
and it is recorded with the reason, so a reader can disagree with it.

Usage
-----
    python tools/aitb_evaluate.py --run --did did:cn:agent:xxxx --out reports
    python tools/aitb_evaluate.py --run --did did:ctid:anicert --out reports
    python tools/aitb_evaluate.py --check --report reports/<slug>.json
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.request

BASE = "https://iaisp.teleinfo.cn"
RESOLVE = "/api/public/ioa/did/resolve-verify"
UA = "aitb-open-eval/1.1 (+read-only)"

# What an outsider can actually call, per method. Written down so that a missing
# endpoint is reported as missing instead of guessed, probed, or blamed on the
# submitter. Every entry needs a citation in docs/AITB-OPEN.md.
METHODS = {
    "cn": {
        "endpoint": BASE + RESOLVE,
        "note": "public resolve-verify endpoint, POST JSON {\"did\": ...}",
        "probe": True,
    },
    "bid": {
        "endpoint": None,
        "note": "only a documented test chain exists (test.bifcore.bitfactory.cn); "
                "no public production endpoint, and the test chain answered 503 "
                "maintenance on 2026-11-26",
        "probe": False,
    },
    "ctid": {
        "endpoint": None,
        "note": "specification publishes relative paths only (/didservice/v1/did/get); "
                "access is through a vendor SDK plus an institution certificate "
                "(github.com/617640999/ctid-did-register); its platform was declared "
                "offline 2026-06-30",
        "probe": False,
    },
}

# key types we have seen on this platform, with the hex length each must have
KEY_HEX = {
    "EcdsaSecp256k1VerificationKey2019": 66,   # compressed point, 33 bytes
    "Ed25519VerificationKey2018": 64,          # 32 bytes
    "SM2": 130,                                # uncompressed, 65 bytes
}
STATUS_OK = {"RUNNING", "STOPPED", "SUSPENDED", "DISABLED"}


def did_slug(did):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", did)[:80]


def resolve(did, timeout=30):
    body = json.dumps({"did": did}).encode()
    req = urllib.request.Request(BASE + RESOLVE, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read()
        code = 200
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    try:
        return {"http": code, "doc": json.loads(raw.decode("utf-8", "replace"))}
    except Exception:
        return {"http": code, "doc": {"_unparsed_head": raw[:80].decode("utf-8", "replace")}}


def gate1(resp):
    """Reachable and registered: the platform answers at all, and says which."""
    doc = resp["doc"] if isinstance(resp.get("doc"), dict) else {}
    summary = ((doc.get("data") or {}).get("summary") or {}) if isinstance(doc.get("data"), dict) else {}
    checks = [
        {"id": "G1.http", "ok": resp["http"] == 200, "detail": "HTTP %s" % resp["http"]},
        {"id": "G1.envelope", "ok": doc.get("success") is True and doc.get("code") == 0,
         "detail": "success=%r code=%r" % (doc.get("success"), doc.get("code"))},
        {"id": "G1.status", "ok": summary.get("resolutionStatus") in ("SUCCESS", "FAILED"),
         "detail": "resolutionStatus=%r (in data.summary)" % summary.get("resolutionStatus")},
    ]
    return checks


def gate2(resp, queried):
    """Self-consistency: every rule here is recomputable from the response alone."""
    doc = resp["doc"] if isinstance(resp.get("doc"), dict) else {}
    data = doc.get("data") if isinstance(doc.get("data"), dict) else {}
    ident = data.get("identity") or {}
    caps = data.get("capabilities") or {}
    reg = data.get("registration") or {}
    summary = data.get("summary") or {}
    pkt = ident.get("publicKeyType")
    pkh = ident.get("publicKey") or ""
    checks = [
        {"id": "G2.id_echo", "ok": ident.get("id") == queried,
         "detail": "identity.id %r vs queried %r" % (ident.get("id"), queried)},
        {"id": "G2.controller", "ok": isinstance(ident.get("controller"), str) and ident["controller"].startswith("did:"),
         "detail": "controller=%r" % (ident.get("controller"),)},
        {"id": "G2.key_type_known", "ok": pkt in KEY_HEX, "detail": "publicKeyType=%r" % (pkt,)},
        {"id": "G2.key_hex_len", "ok": pkt in KEY_HEX and len(pkh) == KEY_HEX.get(pkt),
         "detail": "%s needs %s hex chars, got %d" % (pkt, KEY_HEX.get(pkt), len(pkh))},
        {"id": "G2.key_hex_chars", "ok": bool(re.fullmatch(r"[0-9a-f]+", pkh or "")),
         "detail": "lowercase hex only"},
        {"id": "G2.agent_status", "ok": ident.get("agentStatus") in STATUS_OK,
         "detail": "agentStatus=%r" % (ident.get("agentStatus"),)},
        {"id": "G2.endpoints", "ok": all(isinstance(u, str) and u.startswith("https://")
                                         for u in (caps.get("serviceEndpoint") or [])) and bool(caps.get("serviceEndpoint")),
         "detail": "serviceEndpoint=%r" % (caps.get("serviceEndpoint"),)},
        {"id": "G2.registration_node", "ok": str(reg.get("registrationNodeDid") or "").startswith("did:bid:agentnode:"),
         "detail": "registrationNodeDid=%r" % (reg.get("registrationNodeDid"),)},
        {"id": "G2.trust_matches_status", "ok": (summary.get("isTrustEstablished") is True)
         == (summary.get("resolutionStatus") == "SUCCESS"),
         "detail": "isTrustEstablished=%r with resolutionStatus=%r" % (
             summary.get("isTrustEstablished"), summary.get("resolutionStatus"))},
    ]
    return checks


def gate3(operator_statement):
    """Operator acknowledgement: we record the pointer, we do not adjudicate truth."""
    if not operator_statement:
        return [{"id": "G3.operator_statement", "ok": None, "detail": "MISSING: submitter supplied no public operator statement"}]
    return [{"id": "G3.operator_statement", "ok": True,
             "detail": "declared: %s (recorded, not verified)" % operator_statement}]


NOT_TESTED = [
    "verifiable credential verification (the platform reports vcVerificationStatus=SKIPPED)",
    "whether the operator really controls the private key",
    "whether the code maps to a GB/Z 185.2 OID path (no public mapping rule exists)",
    "liveness of the declared serviceEndpoint (no request is sent to it)",
    "anything about agents not published in the platform's own list",
]


def method_of(did):
    parts = (did or "").split(":")
    return parts[1].lower() if len(parts) > 2 and parts[0] == "did" else ""


def not_applicable(method, note):
    """A card for an identifier we cannot call: say so, run no check, blame nobody."""
    return {
        "did": None,
        "method": method,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": "NO_PUBLIC_ENDPOINT",
        "gates": [{"id": "G0.public_endpoint", "ok": None, "detail": "none published: " + note}],
        "counts": {"ran": 0, "passed": 0, "failed": 0, "missing": 1},
        "resolution": None,
        "operator_statement": None,
        "not_tested": ["everything: no endpoint was called"] + NOT_TESTED,
        "reading": "no public endpoint: nothing was called, so nothing is claimed",
    }


def evaluate(did, operator_statement=None):
    method = method_of(did)
    if method not in METHODS:
        rep = not_applicable(method, "method %r is not in our table" % method)
        rep["did"] = did
        rep["verdict"] = "METHOD_NOT_SUPPORTED"
        rep["reading"] = "method not in our table: nothing was called, so nothing is claimed"
        return rep
    if not METHODS[method]["probe"]:
        rep = not_applicable(method, METHODS[method]["note"])
        rep["did"] = did
        return rep

    resp = resolve(did)
    checks = gate1(resp) + gate2(resp, did) + gate3(operator_statement)
    ran = [c for c in checks if c["ok"] is not None]
    passed = [c for c in ran if c["ok"]]
    missing = [c for c in checks if c["ok"] is None]
    failed = [c for c in ran if not c["ok"]]
    data = (resp["doc"].get("data") or {}) if isinstance(resp["doc"].get("data"), dict) else {}
    return {
        "did": did,
        "method": method,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": "FAIL" if failed else "PASS",
        "gates": checks,
        "counts": {"ran": len(ran), "passed": len(passed), "failed": len(failed), "missing": len(missing)},
        "resolution": (data.get("summary") or {}).get("resolutionStatus"),
        "operator_statement": operator_statement or None,
        "not_tested": NOT_TESTED,
        "reading": ("holds as far as an outsider can see: %d of %d checks passed" % (len(passed), len(ran)))
                   if not failed else ("failed: %s" % ", ".join(c["id"] for c in failed)),
    }


def render_html(report):
    """Zero outbound links on purpose: the card must be readable offline."""
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            c["id"], {True: "PASS", False: "FAIL", None: "MISSING"}[c["ok"]], c["detail"])
        for c in report["gates"])
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<title>AITB report card</title>
<style>body{font:14px/1.6 -apple-system,Segoe UI,sans-serif;max-width:860px;margin:32px auto;padding:0 16px}
table{border-collapse:collapse;width:100%%}td,th{border:1px solid #ddd;padding:6px 8px;vertical-align:top}
th{background:#f6f6f6;text-align:left}code{background:#f4f4f4;padding:1px 4px}</style>
<h1>AITB report card</h1>
<p><code>%s</code><br>method <code>did:%s</code> · evaluated at %s · verdict <b>%s</b></p>
<p><b>%s</b></p>
<table><tr><th>check</th><th>verdict</th><th>what was observed</th></tr>%s</table>
<h2>Not tested</h2><ul>%s</ul>
<p>This card is not a certification. It records what an outsider could observe at the
timestamp above, and names what it did not test. Re-run:
<code>python tools/aitb_evaluate.py --run --did %s</code></p>
</html>""" % (report["did"], report.get("method", ""), report["evaluated_at"],
            report["verdict"], report["reading"], rows,
            "".join("<li>%s</li>" % x for x in report["not_tested"]), report["did"])


def check_report(path):
    rep = json.load(open(path, encoding="utf-8"))
    problems = []
    if not rep.get("did"):
        problems.append("no did recorded")
    if rep.get("verdict") not in ("PASS", "FAIL", "NO_PUBLIC_ENDPOINT", "METHOD_NOT_SUPPORTED"):
        problems.append("verdict %r is not one of the four named states" % (rep.get("verdict"),))
    if rep["counts"]["ran"] + rep["counts"]["missing"] != len(rep["gates"]):
        problems.append("check counts do not add up")
    if rep["counts"]["passed"] + rep["counts"]["failed"] != rep["counts"]["ran"]:
        problems.append("pass/fail counts do not add up")
    if rep.get("verdict") == "NO_PUBLIC_ENDPOINT" and rep["counts"]["ran"] != 0:
        problems.append("claims no endpoint but ran %d checks" % rep["counts"]["ran"])
    if rep.get("verdict") == "PASS" and rep["counts"]["failed"] != 0:
        problems.append("verdict PASS with %d failed checks" % rep["counts"]["failed"])
    if not rep.get("not_tested"):
        problems.append("the card does not say what was not tested")
    if "certif" not in rep["reading"].lower() and "not a certification" not in open(
            os.path.join(os.path.dirname(path), os.path.basename(path).replace(".json", ".html")),
            encoding="utf-8").read().lower():
        problems.append("the card does not disclaim certification")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--did", help="the identifier to evaluate")
    ap.add_argument("--operator-statement", help="URL or citation of a public operator statement")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", help="report json to re-check")
    a = ap.parse_args(argv)

    if a.run:
        if not a.did:
            print("need --did"); return 2
        rep = evaluate(a.did, a.operator_statement)
        os.makedirs(a.out, exist_ok=True)
        slug = did_slug(a.did)
        jp = os.path.join(a.out, slug + ".json")
        hp = os.path.join(a.out, slug + ".html")
        open(jp, "w", encoding="utf-8", newline="\n").write(
            json.dumps(rep, ensure_ascii=False, indent=1) + "\n")
        open(hp, "w", encoding="utf-8", newline="\n").write(render_html(rep))
        print("verdict %s -- %s  (%d/%d passed, %d missing)" % (
            rep["verdict"], rep["reading"], rep["counts"]["passed"],
            rep["counts"]["ran"], rep["counts"]["missing"]))
        print("written:", jp, hp)
        return 0 if rep["verdict"] in ("PASS", "NO_PUBLIC_ENDPOINT", "METHOD_NOT_SUPPORTED") else 1

    if a.check:
        if not a.report:
            print("need --report"); return 2
        problems = check_report(a.report)
        for p in problems:
            print("PROBLEM:", p)
        print("REPORT CHECK OK" if not problems else "REPORT CHECK FAILED")
        return 0 if not problems else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
