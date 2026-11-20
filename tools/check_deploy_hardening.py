"""Lint the deploy-side config that carries 9.1.4 and 9.1.5.

The adapter cannot prove a network ACL from inside Python, so the claim is
scoped to what is checkable: the shipped configuration contains every
directive those clauses need, and a lint fails loudly when one is removed.
That is a weaker claim than "the network is protected", and it is one an
outside reviewer can reproduce in a second.

    python tools/check_deploy_hardening.py [--path deploy/nginx-gateway.conf]
Exit code 0 when every required directive is present.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

REQUIRED = [
    # clause, directive pattern, why it is required
    ("9.1.4 a)", r"ssl_protocols\s+.*TLSv1\.2", "TLS 1.2 floor for confidentiality"),
    ("9.1.4 a)", r"ssl_certificate\s+\S+", "server certificate"),
    ("9.1.4 b)", r"ssl_verify_client\s+on", "mutual authentication"),
    ("9.1.4 b)", r"ssl_client_certificate\s+\S+", "peer CA used for the check"),
    ("9.1.4 b)", r"ssl_verify_depth\s+\d+", "chain depth bounded"),
    ("9.1.5 a)", r"geo\s+\$gw_acl", "ACL source map"),
    ("9.1.5 a)", r"if\s*\(\s*\$gw_acl\s*=\s*0\s*\)", "ACL actually applied"),
    ("9.1.5 b)", r"limit_req_zone\s+\S+\s+zone=", "rate limit zone"),
    ("9.1.5 b)", r"limit_conn_zone\s+\S+\s+zone=", "connection cap zone"),
    ("9.1.5 b)", r"limit_req\s+zone=", "rate limit applied on the route"),
    ("9.1.5 c)", r"location\s*=\s*/metrics", "admin surface on its own location"),
    ("9.1.5 c)", r"allow\s+127\.0\.0\.1", "admin surface restricted"),
]

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "deploy", "nginx-gateway.conf")


def check(text):
    lines = text.splitlines()
    results = []
    for clause, pattern, why in REQUIRED:
        rx = re.compile(pattern)
        found = [(i + 1) for i, line in enumerate(lines) if rx.search(line)]
        results.append({"clause": clause, "directive": pattern,
                        "why": why, "ok": bool(found), "lines": found})
    missing = [r for r in results if not r["ok"]]
    return {"ok": not missing, "checked": len(results),
            "missing": [r["directive"] for r in missing], "results": results}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=DEFAULT_PATH)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with open(args.path, "r", encoding="utf-8") as f:
        report = check(f.read())
    report["path"] = args.path
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("deploy hardening: %s (%d directives)" % (
            "PASS" if report["ok"] else "FAIL", report["checked"]))
        for row in report["results"]:
            print("  [%s] %-10s %s" % ("x" if row["ok"] else " ", row["clause"],
                                      row["directive"]))
        if report["missing"]:
            print("  missing: %s" % report["missing"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
