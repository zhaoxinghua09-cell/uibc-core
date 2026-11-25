#!/usr/bin/env python3
"""verify_corpus — 一条命令核对归档：总摘要=pin、cases=MANIFEST、顶层 kit=ARCHIVE 清单。
退出码 0 PASS / 2 FAIL / 3 INCONCLUSIVE"""
import argparse, hashlib, os, re, sys, zipfile

PIN = re.compile(r"^([0-9a-f]{64})\s+(\S+)\s*$")


def sha(b): return hashlib.sha256(b).hexdigest()


def read_pin(p):
    for line in open(p, encoding="utf-8"):
        m = PIN.match(line.strip())
        if m: return m.group(1)
    return None


def read_man(p):
    out = {}
    if not p or not os.path.exists(p): return out
    for line in open(p, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"): continue
        d, _, rel = line.partition("  ")
        if rel: out[rel.strip().lstrip("./")] = d.strip().lower()
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--archive", required=True)
ap.add_argument("--manifest", required=True)
ap.add_argument("--pin", required=True)
ap.add_argument("--archive-manifest", default=None)
a = ap.parse_args()

for p in (a.archive, a.manifest, a.pin):
    if not os.path.exists(p):
        print("INCONCLUSIVE  missing input: %s" % p); sys.exit(3)

man, pin, raw = read_man(a.manifest), read_pin(a.pin), open(a.archive, "rb").read()
actual = sha(raw); fails = []
print("  archive  %s (%d bytes)" % (os.path.basename(a.archive), len(raw)))
print("  pin/actual %s / %s" % ((pin or "none")[:12], actual[:12]))
if not pin: print("INCONCLUSIVE  pin file has no digest line"); sys.exit(3)
if pin != actual:
    # Stop here. A byte-level change already proves this is not the pinned archive,
    # and walking into a damaged zip only produces a traceback: measured 2026-11-25,
    # flipping one byte inside a member header made zipfile raise BadZipFile mid-run
    # and the tool printed no verdict at all.
    print("FAIL      archive digest does not match the pin")
    print("FAIL      1 problem(s)")
    sys.exit(2)
print("PASS      archive digest matches the pin")

try:
    zipfile.ZipFile(a.archive).close()
except (zipfile.BadZipFile, OSError) as e:
    print("INCONCLUSIVE  cannot read the archive as a zip: %s" % e)
    sys.exit(3)

with zipfile.ZipFile(a.archive) as z:
    names = [n for n in z.namelist() if not n.endswith("/")]
    cases = [n for n in names if n.startswith("cases/")]
    top = [n for n in names if not n.startswith("cases/")]
    ok = 0
    for n in cases:
        w = man.get(n)
        if w is None:
            fails.append("not in manifest: " + n); continue
        if sha(z.read(n)) != w: fails.append("digest mismatch: " + n)
        else: ok += 1
    print("  cases %d, verified %d" % (len(cases), ok))
    covered = [k for k in man if k.startswith("cases/")]
    miss = [k for k in covered if k not in cases]
    if miss: fails.append("manifest entries absent: %d" % len(miss)); print("FAIL      %d manifest entries absent from archive" % len(miss))
    else: print("PASS      every manifest entry under cases/ (%d) is present" % len(covered))
    kit = read_man(a.archive_manifest)
    if top:
        if not kit:
            fails.append("kit files without digest record: %d" % len(top))
            print("FAIL      %d kit file(s) at archive top level have no digest record: %s" % (len(top), ", ".join(sorted(top))))
        else:
            bad = 0
            for n in top:
                if kit.get(n) != sha(z.read(n)): bad += 1
            if bad: fails.append("kit digest problems: %d" % bad); print("FAIL      %d kit digest problem(s)" % bad)
            else: print("PASS      %d top-level kit file(s) match the archive manifest" % len(top))

if fails:
    print("FAIL      %d problem(s)" % len(fails)); sys.exit(2)
print("  → PASS"); sys.exit(0)
