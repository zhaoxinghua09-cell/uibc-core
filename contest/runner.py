# -*- coding: utf-8 -*-
"""UIBC contest runner — the automatic pipeline the 2026-09-18 pilot run
asked for (PILOT-RUN.md, open item: "工具间尚无自动管道 → RUNBOOK 化编排脚本").

One command takes a submission package through the whole intake chain:

  1. fingerprint  submission_sha256 (hash of the sorted file-hash manifest)
                  + a 64-bit SimHash over the package's text files
                  (PILOT-RUN.md open item: real fingerprinting instead of the
                  pilot's illustrative similarity score — this is a stdlib
                  SimHash; it FLAGS candidates, humans decide, per RUBRIC.md)
  2. duplicate    exact hash hit in experiments/log.jsonl  -> DUPLICATE
     check        SimHash similarity >= 0.85 vs any prior  -> SIMILARITY FLAG
  3. machine gate uibc_core.verify (three-valued) + uibc_core.gate
                  FAIL -> REJECTED · DENY -> REJECTED
                  INCONCLUSIVE / HOLD -> HUMAN CHANNEL (never auto-passed)
                  PASS + ALLOW -> ACCEPTED FOR REVIEW (humans still judge)
  4. archive      one append-only JSONL line in experiments/log.jsonl —
                  corrections are new entries, never rewrites (BENCHMARK.md)

Usage:
  python contest/runner.py <package_dir> --agent-id A --problem-id P-01 \
      [--pubkey owner.pub] [--season 0] [--log contest/experiments/log.jsonl]

Exit codes: 0 accepted for review · 2 rejected at the gate ·
            3 human channel · 4 exact duplicate (still logged)

Requires uibc-core:  pip install uibc-core   (or run inside the repo).
Stdlib only, apart from uibc_core itself.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

TEXT_EXTS = {".md", ".py", ".json", ".txt", ".rst"}
SIMILARITY_FLAG = 0.85


def iter_files(pkg):
    for root, dirs, files in os.walk(pkg):
        dirs.sort()
        for name in sorted(files):
            yield os.path.join(root, name)


def submission_hash(pkg):
    """SHA-256 over the sorted manifest of (relative path, file SHA-256)."""
    h = hashlib.sha256()
    for path in iter_files(pkg):
        rel = os.path.relpath(path, pkg).replace(os.sep, "/")
        with open(path, "rb") as f:
            fh = hashlib.sha256(f.read()).hexdigest()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(fh.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def simhash64(pkg):
    """64-bit SimHash over word tokens of the package's text files."""
    weights = [0] * 64
    seen = False
    for path in iter_files(pkg):
        if os.path.splitext(path)[1].lower() not in TEXT_EXTS:
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        for tok in re.findall(r"[A-Za-z0-9_]+|[一-鿿]", text.lower()):
            seen = True
            digest = hashlib.md5(tok.encode("utf-8")).digest()
            bits = int.from_bytes(digest[:8], "big")
            for i in range(64):
                weights[i] += 1 if (bits >> i) & 1 else -1
    if not seen:
        return 0
    out = 0
    for i in range(64):
        if weights[i] > 0:
            out |= 1 << i
    return out


def similarity(a, b):
    if a == 0 or b == 0:
        return 0.0
    return 1.0 - bin(a ^ b).count("1") / 64.0


def load_history(log_path):
    entries = []
    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return entries


def main():
    ap = argparse.ArgumentParser(description="UIBC contest intake runner")
    ap.add_argument("package")
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--problem-id", required=True)
    ap.add_argument("--pubkey", help="owner Ed25519 public key file (.pub) to pin")
    ap.add_argument("--season", default="0")
    ap.add_argument("--log", default=os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "experiments", "log.jsonl"))
    args = ap.parse_args()

    pkg = os.path.abspath(args.package)
    if not os.path.isdir(pkg):
        print(f"REJECTED: package directory not found: {pkg}")
        return 2

    try:
        from uibc_core.verify import verify
        from uibc_core.gate import gate
    except ImportError:
        print("ERROR: uibc_core not importable — run `pip install uibc-core` "
              "or execute inside the uibc-core repo.")
        return 2

    pubkey = None
    if args.pubkey:
        with open(args.pubkey, "rb") as f:
            raw = f.read().strip()
        try:
            pubkey = bytes.fromhex(raw.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            pubkey = raw if len(raw) == 32 else None
        if pubkey is None or len(pubkey) != 32:
            print("REJECTED: --pubkey must be a 32-byte Ed25519 key "
                  "(hex .pub file from `uibc keygen`).")
            return 2

    sub_hash = submission_hash(pkg)
    fp = simhash64(pkg)
    history = load_history(args.log)

    dup_exact = next((e for e in history
                      if e.get("submission_sha256") == sub_hash), None)
    best_sim, best_ref = 0.0, None
    for e in history:
        if e.get("submission_sha256") == sub_hash:
            continue
        s = similarity(fp, int(e.get("simhash", 0)))
        if s > best_sim:
            best_sim, best_ref = s, e

    # A hostile or malformed package must be rejected, never crash intake:
    # a verifier exception is recorded as a FAIL with the error as evidence.
    try:
        v = verify(pkg, pubkey=pubkey)
        verdict = v.get("result")
    except Exception as exc:  # noqa: BLE001 - intake must not crash
        v, verdict = {}, "FAIL"
        gate_reason_override = f"verifier error: {type(exc).__name__}: {exc}"
    try:
        g = gate(pkg, pubkey=pubkey)
        decision = g.get("decision")
    except Exception as exc:  # noqa: BLE001
        g, decision = {}, "DENY"
        gate_reason_override = f"gate error: {type(exc).__name__}: {exc}"

    if dup_exact:
        disposition, rc = "DUPLICATE_EXACT", 4
    elif verdict == "FAIL" or decision == "DENY":
        disposition, rc = "REJECTED_AT_GATE", 2
    elif verdict != "PASS" or decision in ("HOLD", None):
        disposition, rc = "HUMAN_CHANNEL", 3
    else:
        disposition, rc = "ACCEPTED_FOR_REVIEW", 0
    sim_flag = best_sim >= SIMILARITY_FLAG and not dup_exact

    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": str(args.season),
        "problem_id": args.problem_id,
        "agent_id": args.agent_id,
        "submission_sha256": sub_hash,
        "simhash": fp,
        "gate": {"verify": verdict, "gate": decision,
                 "gate_reason": locals().get("gate_reason_override")
                 or g.get("reason")},
        "duplicate": {
            "exact": bool(dup_exact),
            "best_similarity": round(best_sim, 4),
            "similarity_flag": sim_flag,
            "similar_to": (best_ref or {}).get("submission_sha256")
            if sim_flag else None,
        },
        "disposition": disposition,
        "runner": "contest/runner.py v0.3",
    }
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    with open(args.log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print("=== UIBC contest intake receipt ===")
    print(f"problem / agent : {args.problem_id} / {args.agent_id}")
    print(f"submission hash : {sub_hash}")
    print(f"verify / gate   : {verdict} / {decision} "
          f"({locals().get('gate_reason_override') or g.get('reason')})")
    print(f"duplicate check : exact={bool(dup_exact)} "
          f"best_similarity={best_sim:.2f} flag={sim_flag}")
    print(f"disposition     : {disposition}")
    print(f"archived        : {args.log}")
    print("Note: the machine gate admits or rejects; it never awards. "
          "Scoring is human, per RUBRIC.md.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
