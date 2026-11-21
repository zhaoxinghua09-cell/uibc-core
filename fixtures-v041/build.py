#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build fixtures-v041: an Ed25519-era fixture set that v0.4.1 can actually verify.

Additive by design: writes only into <repo>/fixtures-v041/, never touches fixtures/.
Every package here is built through the real CLI path, so nothing is hand-forged
except the mutations, which is the point.

Outputs:
  fixtures-v041/owner.key.pub        publishable pin
  fixtures-v041/<case>.uibc/         eight packages
  fixtures-v041/RESULTS.json         the observed matrix (open / pinned-owner / pinned-attacker)
  fixtures-v041/README.md            what each case is and how to re-run it

Usage: python build_fixtures_v041.py <uibc-exe> <repo-root>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

CASES = ("clean", "tampered", "deleted", "duplicated", "reordered",
         "migrated", "malicious", "malicious-keyswap")


def run(exe, *args, cwd=None):
    p = subprocess.run([exe, *args], cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout


def verify(exe, pkg, pubkey=None):
    args = ["verify", pkg]
    if pubkey:
        args += ["--pubkey", pubkey]
    code, out = run(exe, *args)
    try:
        j = json.loads(out)
        bad = [c["id"] for c in j.get("checks", []) if c.get("result") != "PASS"]
        return code, j.get("result"), bad
    except Exception:
        return code, "UNPARSED", [out.strip()[:80]]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def build_clean(exe, work, out_dir, owner_key):
    pkg = os.path.join(out_dir, "clean.uibc")
    if os.path.exists(pkg):
        shutil.rmtree(pkg)
    run(exe, "init", pkg)
    sample = os.path.join(work, "report.txt")
    with open(sample, "w", encoding="utf-8") as f:
        f.write("fixture evidence: baseline\n")
    run(exe, "register", pkg, "--agent-id", "fx-v41", "--owner", "alice")
    run(exe, "evidence", pkg, "--file", sample, "--type", "ACTION")
    run(exe, "event", pkg, "--type", "ACTIVATE", "--actor", "alice")
    run(exe, "event", pkg, "--type", "UPDATE", "--actor", "alice")
    run(exe, "submit", pkg, "--key", owner_key)
    return pkg


def clone(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    exe, repo = sys.argv[1], sys.argv[2]
    out_dir = os.path.join(repo, "fixtures-v041")
    os.makedirs(out_dir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="fxv041_")

    owner_key = os.path.join(work, "owner.key")
    attacker_key = os.path.join(work, "attacker.key")
    run(exe, "keygen", "--ed25519", "--out", owner_key)
    run(exe, "keygen", "--ed25519", "--out", attacker_key)
    shutil.copy(owner_key + ".pub", os.path.join(out_dir, "owner.key.pub"))
    shutil.copy(attacker_key + ".pub", os.path.join(out_dir, "attacker.key.pub"))

    clean = build_clean(exe, work, out_dir, owner_key)

    # tampered: flip one byte of the evidence payload
    p = clone(clean, os.path.join(out_dir, "tampered.uibc"))
    f = os.path.join(p, "evidence", "files", "report.txt")
    with open(f, "a", encoding="utf-8") as fh:
        fh.write("!")

    # deleted: remove the evidence payload, leave the index entry
    p = clone(clean, os.path.join(out_dir, "deleted.uibc"))
    os.remove(os.path.join(p, "evidence", "files", "report.txt"))

    # duplicated: same entry twice in the index (S12/S5)
    p = clone(clean, os.path.join(out_dir, "duplicated.uibc"))
    idx = read_json(os.path.join(p, "evidence", "index.json"))
    idx["entries"] = idx["entries"] + [dict(idx["entries"][0])]
    write_json(os.path.join(p, "evidence", "index.json"), idx)

    # reordered: swap the sequence numbers of two lifecycle events (S3)
    p = clone(clean, os.path.join(out_dir, "reordered.uibc"))
    lc = read_json(os.path.join(p, "lifecycle.json"))
    ev = lc["events"]
    if len(ev) >= 3:
        ev[1]["sequence_number"], ev[2]["sequence_number"] = \
            ev[2]["sequence_number"], ev[1]["sequence_number"]
        write_json(os.path.join(p, "lifecycle.json"), lc)
    else:
        print("WARN reordered: fewer than 3 lifecycle events")

    # migrated: rewrite payload AND its index hash, so S4 passes but the
    # manifest's evidence_root no longer recomputes (S5)
    p = clone(clean, os.path.join(out_dir, "migrated.uibc"))
    f = os.path.join(p, "evidence", "files", "report.txt")
    with open(f, "a", encoding="utf-8") as fh:
        fh.write("migrated\n")
    import hashlib
    h = hashlib.sha256(open(f, "rb").read()).hexdigest()
    idx = read_json(os.path.join(p, "evidence", "index.json"))
    idx["entries"][0]["content_hash"] = h
    write_json(os.path.join(p, "evidence", "index.json"), idx)

    # malicious: attacker rewrites the manifest and re-seals with its own key
    p = clone(clean, os.path.join(out_dir, "malicious.uibc"))
    mf = read_json(os.path.join(p, "manifest.json"))
    mf["evidence_count"] = mf["evidence_count"] + 1
    write_json(os.path.join(p, "manifest.json"), mf)
    run(exe, "submit", p, "--key", attacker_key)

    # malicious-keyswap: whole package built by the attacker, same agent id
    p = os.path.join(out_dir, "malicious-keyswap.uibc")
    if os.path.exists(p):
        shutil.rmtree(p)
    run(exe, "init", p)
    run(exe, "register", p, "--agent-id", "fx-v41", "--owner", "alice")
    run(exe, "evidence", p, "--file", os.path.join(work, "report.txt"), "--type", "ACTION")
    run(exe, "submit", p, "--key", attacker_key)

    results = {}
    for case in CASES:
        pkg = os.path.join(out_dir, case + ".uibc")
        row = {}
        code, res, bad = verify(exe, pkg)
        row["open"] = {"exit": code, "result": res, "non_pass": bad}
        code, res, bad = verify(exe, pkg, os.path.join(out_dir, "owner.key.pub"))
        row["pinned-owner"] = {"exit": code, "result": res, "non_pass": bad}
        code, res, bad = verify(exe, pkg, os.path.join(out_dir, "attacker.key.pub"))
        row["pinned-attacker"] = {"exit": code, "result": res, "non_pass": bad}
        results[case] = row
        print("%-18s open=%-13s owner=%-13s attacker=%-13s" % (
            case, row["open"]["result"], row["pinned-owner"]["result"],
            row["pinned-attacker"]["result"]))

    write_json(os.path.join(out_dir, "RESULTS.json"), results)
    print("\nwrote", os.path.join(out_dir, "RESULTS.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
