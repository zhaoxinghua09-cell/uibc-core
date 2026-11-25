# -*- coding: utf-8 -*-
"""Audit the official DIF Universal Resolver driver for did:bid - by its own bytes.

    python tools/audit_official_bid_driver.py                 # pinned commit, network
    python tools/audit_official_bid_driver.py --file local.java

Why this exists: "the reference implementation does not check §4.2.5 codes or
§4.2.4 trust" is a claim about someone else's code. Such claims rot, and a table
asserting them without a way to re-check is just an opinion. So this script
re-downloads the pinned file and re-derives every line number it reports.

Polarity matters: the script exits **non-zero if the driver has improved**. That
is the direction that keeps us honest - the day the official driver starts
mapping codes or verifying delegateSign, this goes red instead of staying a
comfortable sentence in our docs.

Pinned commit: 5a933656eb9631bc65ba535f4bb69aa893d79a79 (2022-11-09, Apache-2.0).
"""
import argparse
import hashlib
import re
import sys
import urllib.request

REPO = "caict-4iot-dev/uni-resolver-driver-did-bid"
COMMIT = "5a933656eb9631bc65ba535f4bb69aa893d79a79"
PATH = "src/main/java/uniresolver/driver/did/bid/DidBidDriver.java"
RAW = "https://raw.githubusercontent.com/%s/%s/%s" % (REPO, COMMIT, PATH)


def fetch(url, attempts=3):
    """raw.githubusercontent sometimes resets mid-handshake here; retry, then fall back
    to the contents API at the same pinned commit (base64, same bytes, different host)."""
    import base64
    import json
    import time

    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "uibc-core-audit/0.1"})
            with urllib.request.urlopen(req, timeout=45) as r:  # nosec B310 - public raw file
                return r.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001 - transport, not content
            last = exc
            time.sleep(1 + i)
    api = "https://api.github.com/repos/%s/contents/%s?ref=%s" % (REPO, PATH, COMMIT)
    try:
        req = urllib.request.Request(api, headers={"User-Agent": "uibc-core-audit/0.1",
                                                   "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=45) as r:  # nosec B310
            payload = json.loads(r.read().decode())
        return base64.b64decode(payload["content"]).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        raise SystemExit("could not fetch the pinned driver (%s); try --file with a local copy" % (last,))


def findings(source):
    """(label, ok, detail) - ok means "the driver still behaves as the claim says"."""
    lines = source.splitlines()
    out = []

    code_guard = [i for i, l in enumerate(lines, 1)
                  if re.search(r'errorCode"\)\.getAsInt\(\)\s*!=\s*0', l)]
    collapse = [i for i, l in enumerate(lines, 1) if "docuement not exist" in l]
    out.append(("非零 errorCode 一律坍缩成同一句",
                bool(code_guard and collapse),
                "guard@%s message@%s" % (code_guard[:2], collapse)))

    codes = re.findall(r"(?:case\s+(\d+)|errorCode\s*==\s*(\d+))", source)
    out.append(("源码中没有按码分档的分支", not codes, "code constants found: %s" % (codes[:5],)))

    verify_hits = [i for i, l in enumerate(lines, 1) if re.search(r"\bverify\b|verify=true", l, re.I)]
    out.append(("没有 §4.2.4 的 verify 处理", not verify_hits, "verify@%s" % (verify_hits[:5],)))

    ds_lines = [i for i, l in enumerate(lines, 1) if "delegateSign" in l]
    ds_verify = [i for i, l in enumerate(lines, 1)
                 if "delegateSign" in l and re.search(r"verify|check|validate", l, re.I)]
    out.append(("delegateSign 只被搬运、未被验签", bool(ds_lines) and not ds_verify,
                "delegateSign@%d lines, none verifying (verified@%s)" % (len(ds_lines), ds_verify[:3])))

    proof_lines = [i for i, l in enumerate(lines, 1) if re.search(r'put\("proof"', l)]
    out.append(("proof 直接塞进 metadata，不重算", bool(proof_lines),
                "proof copied@%s" % (proof_lines[:2],)))

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="use a local copy instead of downloading")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    source = open(args.file, encoding="utf-8").read() if args.file else fetch(RAW)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    print("driver: %s @ %s" % (REPO, COMMIT))
    print("file:   %s" % PATH)
    print("sha256: %s  (%d lines)\n" % (digest, source.count("\n") + 1))

    rows = findings(source)
    width = max(len(r[0]) for r in rows)
    for label, ok, detail in rows:
        print("  %-*s | %-8s | %s" % (width, label, "HOLDS" if ok else "CHANGED", detail))

    bad = [r[0] for r in rows if not r[1]]
    print()
    if bad:
        print("The official driver changed or this audit is wrong. Re-read the source before")
        print("repeating any \"they don't do X\" claim. Failing: %s" % ", ".join(bad))
        sys.exit(1)
    print("All %d claims still hold against the pinned bytes." % len(rows))
    print("Re-run to check: python tools/audit_official_bid_driver.py")
    print("License: Apache-2.0 (we cite, we do not vendor the file).")


if __name__ == "__main__":
    main()
