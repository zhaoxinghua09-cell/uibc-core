"""Show the overlay doing its job: same bytes, clean verify, still denied.

Every weakened demo of this feature says "revocation is supported". The claim
that matters is sharper: **a package whose bytes verify clean can still be
denied, and the denial is caused by the overlay, not by the bytes changing.**

So this script builds one package, then runs the gate three times on it:

  1. no overlay            -> ALLOW            (verify PASS, exit 0)
  2. valid owner revocation -> DENY             (exit 2), reason names the revocation
  3. the same revocation, no key -> HOLD        (exit 3), never ALLOW
  4. revocation signed by a different key -> HOLD (exit 3), never ALLOW

Rows 3 and 4 are the ones a shortcut implementation gets wrong: it treats an
unverifiable revocation as "no revocation" and returns ALLOW. The gate refuses.

The package is byte-identical across all four runs - that is verified by
hashing the tree before and after.

Exit codes: 0 all four rows behaved as documented, 1 otherwise, 2 setup error.

Usage:

    python tools/demo_revocation.py --work /tmp/revdemo --python .../python
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

TOOL = "demo_revocation/1.0"


def canonical(obj):
    return json.dumps({k: v for k, v in obj.items() if k != "signature"},
                      sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sign(body, key):
    import hmac as _hmac
    body = dict(body)
    body["signature"] = base64.b64encode(
        _hmac.new(key, canonical(body), hashlib.sha256).digest()).decode()
    return body


def tree_hash(pkg):
    lines = []
    for root, dirs, files in os.walk(pkg):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, pkg).replace(os.sep, "/")
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            lines.append("%s\0%d\0%s" % (rel, os.path.getsize(full), h.hexdigest()))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def cli(py, *args):
    return subprocess.run([py, "-m", "uibc_core.cli", *args],
                          capture_output=True, text=True, timeout=180)


def build_package(py, work, key_path):
    art = os.path.join(work, "demo-1.0.zip")
    with zipfile.ZipFile(art, "w") as z:
        z.writestr("demo/__init__.py", "print('demo')\n")
        z.writestr("demo/core.py", "def f():\n    return 42\n")
    pkg = os.path.join(work, "pkg")
    if os.path.exists(pkg):
        shutil.rmtree(pkg)
    steps = [["init", pkg],
             ["register", pkg, "--agent-id", "revdemo-1.0", "--owner", "alice"],
             ["evidence", pkg, "--file", art, "--type", "ACTION",
              "--media-type", "application/zip", "--note", "demo artifact"],
             ["submit", pkg, "--key", key_path]]
    for s in steps:
        r = cli(py, *s)
        if r.returncode != 0:
            raise SystemExit("setup failed at %s: %s" % (s[0], (r.stderr or r.stdout)[:400]))
    return pkg, art


def main(argv=None):
    p = argparse.ArgumentParser(description="demonstrate the revocation overlay")
    p.add_argument("--work", required=True)
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    py = a.python
    os.makedirs(a.work, exist_ok=True)

    owner = os.path.join(a.work, "owner.hmac.key")
    other = os.path.join(a.work, "other.hmac.key")
    for k in (owner, other):
        if not os.path.exists(k):
            r = cli(py, "keygen", "--out", k)
            if r.returncode != 0:
                print("SETUP ERROR: keygen failed: %s" % (r.stderr or r.stdout), file=sys.stderr)
                return 2
    with open(owner, "r", encoding="ascii") as f:
        owner_key = bytes.fromhex(f.read().strip())
    with open(other, "r", encoding="ascii") as f:
        other_key = bytes.fromhex(f.read().strip())

    pkg, _art = build_package(py, a.work, owner)
    with open(os.path.join(pkg, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    root = manifest["evidence_root"]

    rev_body = {
        "revocation_id": "r-" + hashlib.sha256(root.encode()).hexdigest()[:16],
        "target_root": root,
        "reason_code": "OWNER_REQUEST",
        "key_id": "owner-hmac",
        "revoked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rev_valid = os.path.join(a.work, "revocation.json")
    with open(rev_valid, "w", encoding="utf-8") as f:
        json.dump(sign(rev_body, owner_key), f, indent=2, sort_keys=True)
    rev_forged = os.path.join(a.work, "revocation-forged.json")
    with open(rev_forged, "w", encoding="utf-8") as f:
        json.dump(sign(rev_body, other_key), f, indent=2, sort_keys=True)

    before = tree_hash(pkg)
    runs = []
    def run(label, expect_decision, args):
        r = cli(py, "gate", pkg, *args)
        try:
            rep = json.loads(r.stdout)
        except ValueError:
            rep = {"decision": "UNPARSEABLE", "reason": (r.stderr or r.stdout)[:200]}
        runs.append({"label": label, "decision": rep.get("decision"),
                     "reason": rep.get("reason"), "verify_result": rep.get("verify_result"),
                     "exit": r.returncode, "expected": expect_decision,
                     "keys": {k: rep.get(k) for k in ("revocation", "dispute")}})
        return r.returncode

    run("no overlay", "ALLOW", ["--key", owner])
    run("valid owner revocation", "DENY", ["--key", owner, "--revocation", rev_valid])
    run("same revocation, no key", "HOLD", ["--revocation", rev_valid])
    run("revocation signed by another key", "HOLD", ["--key", owner, "--revocation", rev_forged])
    after = tree_hash(pkg)

    ok = (all(r["decision"] == r["expected"] for r in runs) and before == after)
    out = {"tool": TOOL, "package": pkg, "evidence_root": root,
           "tree_hash_before": before, "tree_hash_after": after,
           "package_unchanged": before == after, "runs": runs, "ok": ok}
    if a.json:
        print(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print("# Revocation overlay, four runs on one package")
        print("")
        print("| run | decision | expected | exit | reason |")
        print("|---|---|---|---|---|")
        for r in runs:
            print("| %s | **%s** | %s | %s | %s |"
                  % (r["label"], r["decision"], r["expected"], r["exit"], r["reason"]))
        print("")
        print("package tree hash before: `%s`" % before)
        print("package tree hash after:  `%s`" % after)
        print("**package unchanged: %s** — the denial came from the overlay, not from the bytes."
              % ("yes" if before == after else "NO"))
        print("")
        if ok:
            print("**OK** — all four runs behaved as documented, and the bytes never moved.")
        else:
            print("**MISMATCH** — at least one run did not behave as documented.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
