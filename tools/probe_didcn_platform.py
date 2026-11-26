"""Probe the public did:cn platform, and keep the probes re-runnable.

Why this exists: the letter we send to the standards body says four things
about their public endpoints. Saying them is a claim, and a claim about
somebody else's live service rots faster than anything else in this repository.
This tool makes the claim re-runnable by them and by us:

  --run     performs the read-only probes and rewrites docs/didcn-probe.json
  --check   offline: the recorded JSON and the generated page must agree

Read-only means exactly that: two GETs on the agents list and one POST per
string with nothing but the string in the body. No registration, no revocation,
no write of any kind.

The failure direction matters. If the platform starts rejecting invalid input
with 4xx, or stops returning `success: true` on a failed resolution, then the
finding in the letter is no longer true -- --run will say so and exit 1, so the
next letter cannot quietly repeat an obsolete complaint. Silence, a timeout or
a 503 is recorded as UNREACHABLE and does not count as evidence either way.

Usage:
  python tools/probe_didcn_platform.py --run     # network
  python tools/probe_didcn_platform.py --check   # offline
Exit 0 when the recorded observations hold, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://iaisp.teleinfo.cn"
UA = "uibc-platform-probe/0.5.5"
RESOLVE = "/api/public/ioa/did/resolve-verify"
AGENTS = "/api/public/ioa/agents"
AGENTS_UPPER = "/API/PUBLIC/IOA/AGENTS"

# 10 strings that are not resolvable DIDs, plus one that the platform is
# expected to reject outright. The empty string is kept separate on purpose:
# it is the one case where the platform does the right thing, and collapsing it
# into the others would overstate what is wrong.
INVALID = [
    ("not a did", "not-a-did"),
    ("pure digits", "1234567890"),
    ("4096 chars", "a" * 4096),
    ("did:web", "did:web:example.com"),
    ("did:key", "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"),
    ("did:example", "did:example:123"),
    ("quote", "did:bid:ef' OR 1=1--"),
    ("angle", "did:bid:ef<script>alert(1)</script>"),
    ("traversal", "../../etc/passwd"),
    ("well-formed but absent", "did:bid:efAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
]
REJECT = ("empty string", "")


def _post(did, timeout=30):
    body = json.dumps({"did": did}).encode("utf-8")
    req = urllib.request.Request(BASE + RESOLVE, data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(), exc.code
    except Exception as exc:                       # noqa: BLE001 - recorded, not swallowed
        return {"http": 0, "error": type(exc).__name__, "ms": int((time.time() - started) * 1000)}
    ms = int((time.time() - started) * 1000)
    try:
        j = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return {"http": status, "error": "not-json", "bytes": len(raw), "ms": ms}
    summary = ((j.get("data") or {}).get("summary") or {})
    return {"http": status, "success": j.get("success"), "code": j.get("code"),
            "resolution": summary.get("resolutionStatus"),
            "vc": summary.get("vcVerificationStatus"),
            "trust": summary.get("isTrustEstablished"), "ms": ms}


def _get(path, timeout=30):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, status, ctype = r.read(), r.status, r.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as exc:
        raw, status, ctype = exc.read(), exc.code, exc.headers.get("Content-Type") or ""
    except Exception as exc:                       # noqa: BLE001
        return {"http": 0, "error": type(exc).__name__, "ms": int((time.time() - started) * 1000)}
    ms = int((time.time() - started) * 1000)
    items = keys = None
    if "json" in ctype:
        try:
            j = json.loads(raw.decode("utf-8", "replace"))
            data = j.get("data")
            lst = data if isinstance(data, list) else (data or {}).get("list") if isinstance(data, dict) else None
            items = len(lst) if isinstance(lst, list) else None
            keys = sorted(lst[0]) if isinstance(lst, list) and lst else None
        except ValueError:
            ctype = ctype + "+unparsed"
    return {"http": status, "content_type": ctype, "bytes": len(raw), "items": items, "keys": keys, "ms": ms}


def collect():
    rows = [dict(case=name, did=("(4096 chars)" if name == "4096 chars" else did), **_post(did))
            for name, did in INVALID]
    rows.append(dict(case=REJECT[0], did="(empty)", **_post(REJECT[1])))
    return {"base": BASE, "endpoint": RESOLVE, "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "read_only": "two GETs (agents list, both casings) and one POST per string; no writes anywhere",
            "rows": rows, "agents_lower": _get(AGENTS), "agents_upper": _get(AGENTS_UPPER)}


def verdict(rec):
    """What the observations say, in the form the letter needs."""
    bad = [r for r in rec["rows"] if r["case"] != REJECT[0]]
    unreachable = [r for r in bad if r.get("http") in (0, None)]
    accepted = [r for r in bad if r.get("http") == 200 and r.get("success") is True and r.get("code") == 0]
    skipped = [r for r in bad if r.get("vc") == "SKIPPED"]
    rej = [r for r in rec["rows"] if r["case"] == REJECT[0]][0]
    low, up = rec["agents_lower"], rec["agents_upper"]
    return {
        "invalid_cases": len(bad),
        "unreachable": len(unreachable),
        "accepted_as_success": len(accepted),
        "resolved_failed": sum(1 for r in accepted if r.get("resolution") == "FAILED"),
        "vc_skipped": len(skipped),
        "empty_rejected": rej.get("http") == 400 and rej.get("success") is False,
        "agents_items": low.get("items"),
        "agents_fields": low.get("keys"),
        "upper_is_html": up.get("http") == 200 and "html" in (up.get("content_type") or ""),
        "holds": bool(len(unreachable) == 0 and len(accepted) == len(bad)
                      and len(skipped) == len(bad) and rej.get("http") == 400
                      and low.get("http") == 200 and low.get("keys") == ["did", "name"]
                      and up.get("http") == 200 and "html" in (up.get("content_type") or "")),
    }


def check(rec):
    """Offline: the record must be internally consistent and quotable."""
    problems = []
    v = verdict(rec)
    if v["unreachable"]:
        problems.append("%d case(s) were never observed (timeout / 503): no evidence either way" % v["unreachable"])
    if v["accepted_as_success"] != v["invalid_cases"]:
        problems.append("invalid-input rows no longer all show 200 + success:true + code:0 (%d of %d); "
                        "the claim in the letter is no longer true" % (v["accepted_as_success"], v["invalid_cases"]))
    if v["vc_skipped"] != v["accepted_as_success"]:
        problems.append("vcVerificationStatus is not SKIPPED everywhere (%d of %d)" % (
            v["vc_skipped"], v["accepted_as_success"]))
    if not v["empty_rejected"]:
        problems.append("the empty string is no longer rejected with 400 + success:false")
    if not rec.get("read_only") or "no writes" not in rec["read_only"]:
        problems.append("the record does not state that the probe was read-only")
    if not rec.get("probed_at"):
        problems.append("no probed_at timestamp")
    if len({r["case"] for r in rec["rows"]}) != len(rec["rows"]):
        problems.append("duplicate case names")
    if v["accepted_as_success"] and v["resolved_failed"] != v["accepted_as_success"]:
        problems.append("a case counted as accepted did not carry resolutionStatus=FAILED")
    if not any(r["case"] == "quote" for r in rec["rows"]):
        problems.append("the quote case is missing")
    return problems, v


def page(rec, v):
    rows = ["| case | HTTP | success | code | resolutionStatus | vcVerificationStatus |", "|---|---|---|---|---|---|"]
    for r in rec["rows"]:
        rows.append("| %s | %s | %s | %s | %s | %s |" % (
            r["case"], r.get("http"), r.get("success"), r.get("code"),
            r.get("resolution") or "—", r.get("vc") or "—"))
    return "\n".join([
        "# did:cn public platform — read-only probe",
        "",
        "<!-- facts: current -->",
        "",
        "Generated by `tools/probe_didcn_platform.py --run` at %s. Read-only: %s." % (
            rec["probed_at"], rec["read_only"]),
        "",
        "Target: `%s` (resolution endpoint `%s`)." % (rec["base"], rec["endpoint"]),
        "",
        *rows,
        "",
        "Agents list, lowercase path: HTTP %s, %s, %s items, fields %s." % (
            rec["agents_lower"].get("http"), rec["agents_lower"].get("content_type"),
            rec["agents_lower"].get("items"), rec["agents_lower"].get("keys")),
        "",
        "Agents list, uppercase path: HTTP %s, %s (a client that mistypes the case gets a page, not an error)." % (
            rec["agents_upper"].get("http"), rec["agents_upper"].get("content_type")),
        "",
        "## What this supports, and what it does not",
        "",
        "*%d of %d* invalid strings come back `200 + success:true + code:0`, with the failure only visible in "
        "`resolutionStatus=FAILED`; `vcVerificationStatus` is `SKIPPED` in *%d of %d*; the empty string is rejected "
        "with HTTP %s. A caller that branches on `success` or `code` records a failed resolution as a success." % (
            v["accepted_as_success"], v["invalid_cases"], v["vc_skipped"], v["invalid_cases"],
            rec["rows"][-1].get("http")),
        "",
        "It does **not** show the platform verifies signatures, and it does not show that any of this is wrong "
        "behaviour -- the platform may define `success` as \"the request was understood\". It shows only that the "
        "word a caller is most likely to branch on does not carry the verdict. Re-run it before quoting it: a "
        "service can change, and `--run` fails loudly when the observation no longer holds.",
    ])


def uniqueness(rec, sample=3, timeout=30):
    """GB/Z 185.2 clause 6 d): one identity code, one agent.

    The standard requires a 1:1 mapping. That is the only clause in it an
    outsider can check from outside, and only weakly:

      1. the published list must not contain the same code twice;
      2. resolving one code twice must return the same identifier.

    Both are necessary, neither is sufficient: the platform could still hand
    two agents the same code without publishing both. So the verdict says
    "holds as far as an outsider can see", not "conforms".
    """
    dids = rec.get("agent_dids") or []
    dupes = sorted({d for d in dids if dids.count(d) > 1})
    picks = [d for d in dids if d not in dupes][:sample]
    twice = []
    for d in picks:
        a, b = _post(d, timeout), _post(d, timeout)
        same = (a.get("http") == b.get("http") and a.get("resolution") == b.get("resolution")
                and a.get("vc") == b.get("vc"))
        twice.append({"did": d, "first": a, "second": b, "same": same})
    return {"checked_list": len(dids), "duplicates": dupes,
            "repeat": twice,
            "holds": not dupes and all(t["same"] for t in twice) and bool(picks)}


def check_uniqueness(rec):
    u = rec.get("uniqueness") or rec
    problems = []
    if not u.get("checked_list"):
        problems.append("the agent list was never read: no evidence either way")
    if u.get("duplicates"):
        problems.append("%d code(s) appear twice in the published list: %s" % (
            len(u["duplicates"]), ", ".join(u["duplicates"][:3])))
    for t in u.get("repeat") or []:
        if not t["same"]:
            problems.append("resolving %s twice gave different answers" % t["did"])
    if not (u.get("repeat") or []):
        problems.append("no code was resolved twice, so 1:1 was never pressed")
    if "clause" not in u.get("note", ""):
        problems.append("the note does not name the clause it is checking (GB/Z 185.2 6 d)")
    return problems, u


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="probe the live platform (network) and rewrite the record")
    ap.add_argument("--check", action="store_true", help="offline: check the recorded observations and the page")
    ap.add_argument("--uniqueness", action="store_true",
                    help="network: check GB/Z 185.2 6 d) -- one code, one agent -- as far as an outsider can")
    ap.add_argument("--check-uniqueness", action="store_true", help="offline: check the uniqueness record")
    ap.add_argument("--json", default=os.path.join("docs", "didcn-probe.json"))
    ap.add_argument("--page", default=os.path.join("docs", "DIDCN-PROBE.md"))
    ap.add_argument("--uniq-json", default=os.path.join("docs", "didcn-uniqueness.json"))
    args = ap.parse_args(argv)
    if args.uniqueness:
        rec = json.load(open(args.json, encoding="utf-8")) if os.path.exists(args.json) else {}
        listing = _get(AGENTS)
        req = urllib.request.Request(BASE + AGENTS, headers={"User-Agent": UA})
        raw = urllib.request.urlopen(req, timeout=30).read()
        data = (json.loads(raw.decode("utf-8", "replace")).get("data") or {})
        dids = [x.get("did") for x in (data if isinstance(data, list) else data.get("list") or []) if x.get("did")]
        u = uniqueness({"agent_dids": dids})
        u["note"] = "GB/Z 185.2-2026 clause 6 d): one identity code may correspond to one agent only. " \
                    "Checked as far as an outsider can: list uniqueness + repeat resolution."
        u["probed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        u["listing_http"] = listing.get("http")
        os.makedirs(os.path.dirname(args.uniq_json), exist_ok=True)
        with open(args.uniq_json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(u, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print("list=%s duplicates=%d repeat=%d holds=%s" % (
            u["checked_list"], len(u["duplicates"]), len(u["repeat"]), u["holds"]))
        print("UNIQUENESS OK (as far as an outsider can see)" if u["holds"] else "UNIQUENESS FAILED")
        return 0 if u["holds"] else 1
    if args.check_uniqueness:
        rec = json.load(open(args.uniq_json, encoding="utf-8"))
        problems, u = check_uniqueness(rec)
        for p in problems:
            print("PROBLEM:", p)
        print("list=%s duplicates=%d repeat=%d" % (u.get("checked_list"), len(u.get("duplicates") or []),
                                                   len(u.get("repeat") or [])))
        print("UNIQUENESS CHECK OK" if not problems else "UNIQUENESS CHECK FAILED")
        return 0 if not problems else 1
    if args.run:
        rec = collect()
        os.makedirs(os.path.dirname(args.json), exist_ok=True)
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        v = verdict(rec)
        with open(args.page, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(page(rec, v) + "\n")
        print("recorded %d cases at %s" % (len(rec["rows"]), rec["probed_at"]))
        print("accepted_as_success=%d vc_skipped=%d empty_rejected=%s agents=%s upper_html=%s" % (
            v["accepted_as_success"], v["vc_skipped"], v["empty_rejected"], v["agents_items"], v["upper_is_html"]))
        if not v["holds"]:
            print("PROBE CHANGED: the finding in the letter no longer holds as recorded -- fix the letter, "
                  "not the probe")
            return 1
        print("PROBE OK")
        return 0
    rec = json.load(open(args.json, encoding="utf-8"))
    problems, v = check(rec)
    if not os.path.exists(args.page):
        problems.append("page %s is missing" % args.page)
    else:
        text = open(args.page, encoding="utf-8").read()
        if "%d of %d" % (v["accepted_as_success"], v["invalid_cases"]) not in text:
            problems.append("the page does not quote the recorded count %d of %d" % (
                v["accepted_as_success"], v["invalid_cases"]))
        if rec["probed_at"] not in text:
            problems.append("the page does not carry the probed_at timestamp")
        if "facts: current" not in text:
            problems.append("the page is not marked facts: current, so doc-fact checking will skip it")
    for p in problems:
        print("PROBLEM:", p)
    print("cases=%d accepted=%d vc=%d agents=%s" % (len(rec["rows"]), v["accepted_as_success"],
                                                   v["vc_skipped"], v["agents_items"]))
    print("PROBE CHECK OK" if not problems else "PROBE CHECK FAILED")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
