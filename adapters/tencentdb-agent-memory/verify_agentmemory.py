#!/usr/bin/env python3
"""UIBC adapter: preservation verifier for TencentDB Agent Memory migrations.

Verifies that memory records survive a migration (SQLite -> TCVDB export)
byte-for-byte across four preservation domains (UIBC-MEM semantics):

  M2_fact        content body did not change
  M3_attribution session origin (who said it) is intact
  M4_citation    timestamps / metadata citation intact
  M5_version     created/updated version fields not shifted

Pure standard library. Read-only on source data.

CLI:
  python verify_agentmemory.py extract --sqlite <db> --out manifest.json
  python verify_agentmemory.py compare --before a.json --after b.json [--report r.md]
  python verify_agentmemory.py root --manifest a.json
  python verify_agentmemory.py selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys

DOMAINS: dict[str, list[str]] = {
    "M2_fact": ["content", "type", "priority", "scene_name"],
    "M3_attribution": ["session_key", "session_id"],
    "M4_citation": ["timestamp_str", "timestamp_start", "timestamp_end", "metadata_json"],
    "M5_version": ["created_time", "updated_time"],
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract(sqlite_path: str, table: str = "l1_records") -> dict:
    """Read a read-only snapshot of fingerprints, one entry per record."""
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in cur.description]
        manifest: dict[str, dict[str, str]] = {}
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            rid = str(rec["record_id"])
            manifest[rid] = {
                dom: _sha("|".join(str(rec.get(f, "")) for f in fields))
                for dom, fields in DOMAINS.items()
            }
        return manifest
    finally:
        conn.close()


def compute_root(manifest: dict) -> str:
    """Order-independent aggregate root over all record fingerprints."""
    h = hashlib.sha256()
    for rid in sorted(manifest):
        h.update(rid.encode("utf-8"))
        for dom in sorted(manifest[rid]):
            h.update(dom.encode("utf-8"))
            h.update(manifest[rid][dom].encode("utf-8"))
    return h.hexdigest()


def compare(before: dict, after: dict) -> list[str]:
    """Return precise failure lines; empty list means PASS."""
    fails: list[str] = []
    for rid in sorted(set(before) | set(after)):
        b, a = before.get(rid), after.get(rid)
        if b is None:
            fails.append(f"FAIL {rid}: record appeared after migration (not in before)")
            continue
        if a is None:
            fails.append(f"FAIL {rid}: record lost in migration (all domains)")
            continue
        for dom in DOMAINS:
            if b[dom] != a[dom]:
                fails.append(f"FAIL {rid}: {dom} changed")
    return fails


def selftest() -> int:
    """Build a fixture SQLite, verify PASS, then tamper one field -> precise FAIL."""
    import os
    import tempfile

    tmp = tempfile.mkdtemp(prefix="uiba-")
    db = os.path.join(tmp, "mem.sqlite")
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE l1_records (record_id TEXT PRIMARY KEY, content TEXT NOT NULL,"
        " type TEXT DEFAULT '', priority INTEGER DEFAULT 50, scene_name TEXT DEFAULT '',"
        " session_key TEXT DEFAULT '', session_id TEXT DEFAULT '', timestamp_str TEXT DEFAULT '',"
        " timestamp_start TEXT DEFAULT '', timestamp_end TEXT DEFAULT '',"
        " created_time TEXT DEFAULT '', updated_time TEXT DEFAULT '', metadata_json TEXT DEFAULT '{}')"
    )
    recs = [
        ("mem-001", "患者术后需要冷敷48小时", "fact", 70, "recovery", "s-a", "s-a", "2026-09-01T10:00", "", "", "2026-09-01T10:00", "2026-09-01T10:00", "{}"),
        ("mem-002", "钛合金螺钉扭矩上限2.5Nm", "constraint", 90, "surgery", "s-b", "s-b", "2026-09-02T09:00", "", "", "2026-09-02T09:00", "2026-09-03T08:00", '{"src":"IFU-7"}'),
    ]
    conn.executemany("INSERT INTO l1_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", recs)
    conn.commit()
    conn.close()

    before = extract(db)
    r1 = compute_root(before)
    assert r1 == compute_root(dict(reversed(list(before.items())))), "root must be order-independent"

    # simulate a clean migration: copy file
    db2 = os.path.join(tmp, "mem2.sqlite")
    with open(db, "rb") as f, open(db2, "wb") as g:
        g.write(f.read())
    fails = compare(before, extract(db2))
    assert not fails, f"clean copy must PASS, got {fails}"

    # tamper: change content of one record (M2) and updated_time of another (M5)
    conn = sqlite3.connect(db2)
    conn.execute("UPDATE l1_records SET content='患者术后需要冷敷72小时' WHERE record_id='mem-001'")
    conn.execute("UPDATE l1_records SET updated_time='2026-09-05T00:00' WHERE record_id='mem-002'")
    conn.commit()
    conn.close()
    fails = compare(before, extract(db2))
    assert fails == ["FAIL mem-001: M2_fact changed", "FAIL mem-002: M5_version changed"], fails
    assert compute_root(extract(db2)) != r1, "root must change after tamper"
    print("SELFTEST PASS (clean copy PASS; tamper -> precise per-field FAIL; root order-independent)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="UIBC preservation verifier for TencentDB Agent Memory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("extract")
    p1.add_argument("--sqlite", required=True)
    p1.add_argument("--out", required=True)
    p1.add_argument("--table", default="l1_records")
    p2 = sub.add_parser("compare")
    p2.add_argument("--before", required=True)
    p2.add_argument("--after", required=True)
    p2.add_argument("--report")
    p3 = sub.add_parser("root")
    p3.add_argument("--manifest", required=True)
    sub.add_parser("selftest")
    args = ap.parse_args()

    if args.cmd == "extract":
        m = extract(args.sqlite, args.table)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"records": m, "root": compute_root(m), "count": len(m)}, f, ensure_ascii=False, indent=1)
        print(f"extracted {len(m)} records -> {args.out} (root {compute_root(m)[:16]}...)")
        return 0
    if args.cmd == "compare":
        with open(args.before, encoding="utf-8") as f:
            before = json.load(f)["records"]
        with open(args.after, encoding="utf-8") as f:
            after = json.load(f)["records"]
        fails = compare(before, after)
        if fails:
            print("\n".join(fails))
            if args.report:
                with open(args.report, "w", encoding="utf-8") as f:
                    f.write("# Preservation report: FAIL\n\n```\n" + "\n".join(fails) + "\n```\n")
            return 2
        print(f"PASS: {len(before)} records, all 4 preservation domains intact")
        if args.report:
            with open(args.report, "w", encoding="utf-8") as f:
                f.write(f"# Preservation report: PASS\n\n{len(before)} records verified (M2/M3/M4/M5).\n")
        return 0
    if args.cmd == "root":
        with open(args.manifest, encoding="utf-8") as f:
            print(compute_root(json.load(f)["records"]))
        return 0
    if args.cmd == "selftest":
        return selftest()
    return 1


if __name__ == "__main__":
    sys.exit(main())
