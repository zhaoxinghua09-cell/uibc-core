"""uibc-core stress tests. Stdlib unittest + time.perf_counter only.

Scenarios:
  a) hash_file() on 10MB / 50MB temp files          -> time + MB/s
  b) evidence_root() with 1k / 10k / 100k hashes    -> time
  c) validate_lifecycle() chains of 10k / 100k      -> time + rate per 10k events
  d) verify() on 500-entry package (PASS + FAIL)    -> time
  e) subprocess CLI full chain (50 evidence files)  -> wall time
  f) tracemalloc on 100k-event chain validation     -> approx memory delta

Does NOT modify uibc_core source or existing unit tests.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.canonical import evidence_root, hash_file
from uibc_core.lifecycle import validate_lifecycle
from uibc_core.verify import verify
from uibc_core import cli as ucli

RESULTS = []  # (scenario, scale, seconds, throughput, extra)


def _record(scenario, scale, seconds, throughput="", extra=""):
    RESULTS.append((scenario, scale, seconds, throughput, extra))


def _chain(n):
    """Valid chain: first REGISTER, then n-1 UPDATEs, each chained to previous."""
    events, prev = [], None
    for i in range(n):
        eid = f"e{i}"
        events.append({
            "event_id": eid,
            "event_type": "REGISTER" if i == 0 else "UPDATE",
            "agent_id": "a",
            "timestamp": "2026-01-01T00:00:00Z",
            "actor": "o",
            "payload_hash": None,
            "previous_event": prev,
            "signature": None,
        })
        prev = eid
    return events


class StressTest(unittest.TestCase):
    maxDiff = None

    # a) large evidence file hashing ------------------------------------
    def test_a_hash_file_throughput(self):
        for mb in (10, 50):
            with self.subTest(size_mb=mb):
                d = tempfile.mkdtemp()
                try:
                    p = os.path.join(d, f"big_{mb}.bin")
                    chunk = b"x" * (1 << 20)
                    with open(p, "wb") as f:
                        for _ in range(mb):
                            f.write(chunk)
                    t0 = time.perf_counter()
                    h = hash_file(p)
                    dt = time.perf_counter() - t0
                    self.assertEqual(len(h), 64)
                    throughput = f"{mb / dt:.1f} MB/s"
                    _record("a) hash_file", f"{mb} MB", dt, throughput)
                    os.remove(p)  # delete temp file immediately
                finally:
                    shutil.rmtree(d, ignore_errors=True)

    # b) evidence_root scale ---------------------------------------------
    def test_b_evidence_root_scale(self):
        hashes = [hash_file(__file__)] * 1
        base = [f"{i:064x}" for i in range(100)]
        for n in (1000, 10000, 100000):
            with self.subTest(n=n):
                items = (base * (n // len(base)))[:n]
                t0 = time.perf_counter()
                r = evidence_root(items)
                dt = time.perf_counter() - t0
                self.assertEqual(len(r), 64)
                _record("b) evidence_root", f"{n} hashes", dt,
                        f"{n / dt:,.0f} hashes/s")

    # c) lifecycle long chains -------------------------------------------
    def test_c_validate_lifecycle_long_chains(self):
        for n in (10000, 100000):
            with self.subTest(events=n):
                chain = _chain(n)
                self.assertEqual(validate_lifecycle(chain), [])
                t0 = time.perf_counter()
                errs = validate_lifecycle(chain)
                dt = time.perf_counter() - t0
                self.assertEqual(errs, [])
                per10k = dt / n * 10000
                _record("c) validate_lifecycle", f"{n:,} events", dt,
                        f"{per10k:.3f}s / 10k events ({n / dt:,.0f} events/s)")

    # d) verify() on 500-entry package -----------------------------------
    def test_d_verify_large_package_pass_and_fail(self):
        tmp = tempfile.mkdtemp()
        try:
            pkg = os.path.join(tmp, "big.uibc")
            ucli.cmd_init(type("A", (), {"path": pkg})())
            ucli.cmd_register(type("A", (), {
                "path": pkg, "agent_id": "stress-agent", "owner": "stress",
                "agent_type": "software-agent", "version": "1"})())
            src = os.path.join(tmp, "ev_src.txt")
            with open(src, "w", encoding="utf-8") as f:
                f.write("stress evidence payload\n")
            t0 = time.perf_counter()
            for i in range(500):
                ucli.cmd_evidence(type("A", (), {
                    "path": pkg, "type": "ACTION", "file": src,
                    "media_type": "text/plain", "note": f"entry {i}"})())
            ucli.cmd_submit(type("A", (), {"path": pkg})())
            build_time = time.perf_counter() - t0

            t0 = time.perf_counter()
            report = verify(pkg)
            pass_time = time.perf_counter() - t0
            self.assertEqual(report["result"], "PASS")
            _record("d) verify 500 entries PASS", "500 evidence",
                    pass_time, f"package build {build_time:.2f}s")

            # tamper one evidence file -> FAIL path
            target = os.path.join(pkg, "evidence", "files", "ev_src.txt")
            with open(target, "a", encoding="utf-8") as f:
                f.write("TAMPERED\n")
            t0 = time.perf_counter()
            report2 = verify(pkg)
            fail_time = time.perf_counter() - t0
            self.assertEqual(report2["result"], "FAIL")
            checks = {c["id"]: c["result"] for c in report2["checks"]}
            self.assertEqual(checks["S4"], "FAIL")
            _record("d) verify 500 entries FAIL", "500 evidence (1 tampered)",
                    fail_time)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # e) CLI full chain via subprocess ------------------------------------
    def test_e_cli_full_chain_subprocess(self):
        tmp = tempfile.mkdtemp()
        try:
            py = sys.executable
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env = dict(os.environ, PYTHONPATH=root, PYTHONIOENCODING="utf-8")

            def run(*a):
                return subprocess.run([py, "-m", "uibc_core.cli", *a],
                                      capture_output=True, text=True, env=env)

            pkg = os.path.join(tmp, "cli.uibc")
            files = []
            for i in range(50):
                fp = os.path.join(tmp, f"f{i:02d}.txt")
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(f"evidence {i}\n")
                files.append(fp)

            t0 = time.perf_counter()
            self.assertEqual(run("init", pkg).returncode, 0)
            self.assertEqual(run("register", pkg, "--agent-id", "cli-stress",
                                 "--owner", "stress").returncode, 0)
            for fp in files:
                self.assertEqual(run("evidence", pkg, "--type", "OUTPUT",
                                     "--file", fp).returncode, 0)
            self.assertEqual(run("submit", pkg).returncode, 0)
            r = run("verify", pkg)
            total = time.perf_counter() - t0
            self.assertEqual(r.returncode, 0)
            self.assertIn('"result": "PASS"', r.stdout)
            _record("e) CLI full chain (subprocess)",
                    "init+register+50x evidence+submit+verify", total)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # f) memory friendliness ----------------------------------------------
    def test_f_tracemalloc_100k_chain(self):
        chain = _chain(100000)
        validate_lifecycle(chain)  # warm-up
        tracemalloc.start()
        t0 = time.perf_counter()
        errs = validate_lifecycle(chain)
        dt = time.perf_counter() - t0
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(errs, [])
        _record("f) tracemalloc 100k chain", "100,000 events", dt,
                f"peak {peak / 1e6:.1f} MB, net {current / 1e6:+.2f} MB")


def tearDownModule():
    if RESULTS:
        print("\n=== STRESS RESULTS ===")
        for sc, scale, dt, thr, extra in RESULTS:
            line = f"{sc} | {scale} | {dt:.4f}s | {thr}"
            if extra:
                line += f" | {extra}"
            print(line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
