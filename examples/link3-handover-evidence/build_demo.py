"""Build the fictional OEM->receiver handover demo packages.

Fictional throughout: "Meridian Medical" and the "CardioPatch CP-2" do not
exist. Demo keys use published seeds on purpose so anyone can rebuild the
exact packages and reproduce every verdict in RUN-TRANSCRIPT.txt.
DEMO ONLY - never use a published seed for anything real.

Run:  python3 build_demo.py     (uses the installed uibc-core; set UIBC_ROOT to a checkout to override)
"""

import os
import shutil
import subprocess
import sys

UIBC_ROOT = os.environ.get("UIBC_ROOT", "")  # empty = use the installed uibc-core
if UIBC_ROOT:
    sys.path.insert(0, UIBC_ROOT)

import uibc_core.cli as ucli  # noqa: E402
from uibc_core.signing import ed_public_key  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PKGS = os.path.join(HERE, "packages")
SRC = os.path.join(HERE, "_src")

OWNER_SEED = bytes([7] * 32)     # DEMO ONLY - published, worthless, by design
ATTACKER_SEED = bytes([9] * 32)  # DEMO ONLY - the substitute-key signer

REPORT_C = """DESIGN VERIFICATION REPORT - CardioPatch CP-2 (FICTIONAL)
Document: DVR-CP2-004  Revision: C  Status: APPROVED
Device: CardioPatch CP-2 ambulatory ECG monitor (fictional)
Result: all 42 verification cases passed; 0 deviations open.
Approved by: Design Review Board, 2026-09-18.
"""

REPORT_B = """DESIGN VERIFICATION REPORT - CardioPatch CP-2 (FICTIONAL)
Document: DVR-CP2-004  Revision: B  Status: SUPERSEDED
Device: CardioPatch CP-2 ambulatory ECG monitor (fictional)
Result: 39 of 42 verification cases passed; 3 deviations open.
Superseded by Revision C, 2026-09-18.
"""

OTHERS = {
    "software-test-summary.txt": """SOFTWARE TEST SUMMARY - CardioPatch CP-2 (FICTIONAL)
Document: STS-CP2-011  Revision: 2  Status: APPROVED
Unit + integration: 318 cases, 318 passed. Static analysis: 0 critical.
""",
    "risk-analysis-summary.txt": """RISK ANALYSIS SUMMARY - CardioPatch CP-2 (FICTIONAL)
Document: RAS-CP2-002  Revision: 3  Status: APPROVED
Hazards: 17 identified; residual risk acceptable per ISO 14971 process.
""",
    "electrical-safety-summary.txt": """ELECTRICAL SAFETY SUMMARY - CardioPatch CP-2 (FICTIONAL)
Document: ESS-CP2-007  Revision: 1  Status: APPROVED
IEC 60601-1 test programme: all applicable clauses passed.
""",
}


def _a(**kw):
    return type("A", (), kw)()


def write_key(seed, key_path, pub_path=None):
    with open(key_path, "w", encoding="ascii") as f:
        f.write("ed25519:" + seed.hex())
    if pub_path:
        with open(pub_path, "w", encoding="ascii") as f:
            f.write(ed_public_key(seed).hex())


def build_package(dest, report_text, key_path):
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(SRC, exist_ok=True)
    files = {"design-verification-report.txt": report_text}
    files.update(OTHERS)
    paths = {}
    for name, text in files.items():
        p = os.path.join(SRC, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        paths[name] = p
    ucli.cmd_init(_a(path=dest))
    ucli.cmd_register(_a(path=dest, agent_id="cardiopatch-cp2-evidence-set",
                         owner="meridian-medical",
                         agent_type="evidence-package", version="1.0.0"))
    ucli.cmd_event(_a(path=dest, type="ACTIVATE", actor="meridian-medical"))
    for name, p in paths.items():
        ucli.cmd_evidence(_a(path=dest, type="VERIFICATION", file=p,
                             media_type="text/plain",
                             note="fictional handover evidence"))
    ucli.cmd_submit(_a(path=dest, key=key_path))


def run_verify(args):
    cmd = [sys.executable, "-m", "uibc_core.cli", "verify"] + args
    env = dict(os.environ)
    if UIBC_ROOT:
        env["PYTHONPATH"] = UIBC_ROOT
    r = subprocess.run(cmd, capture_output=True, text=True, env=env,
                       cwd=UIBC_ROOT or HERE)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    if os.path.isdir(PKGS):
        shutil.rmtree(PKGS)
    os.makedirs(PKGS)
    owner_key = os.path.join(HERE, "meridian-owner.key")
    owner_pub = os.path.join(HERE, "meridian-owner.pub")
    attacker_key = os.path.join(HERE, "attacker.key")
    write_key(OWNER_SEED, owner_key, owner_pub)
    write_key(ATTACKER_SEED, attacker_key)

    approved = os.path.join(PKGS, "approved")
    build_package(approved, REPORT_C, owner_key)

    swapped = os.path.join(PKGS, "received-swapped")
    shutil.copytree(approved, swapped)
    target = os.path.join(swapped, "evidence", "files",
                          "design-verification-report.txt")
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(REPORT_B)

    resealed = os.path.join(PKGS, "received-resealed")
    build_package(resealed, REPORT_B, attacker_key)

    lines = []
    lines.append("HANDOVER DEMO - verification transcript (fictional data)")
    lines.append("=" * 62)
    cases = [
        ("1. Approved package, open verification",
         [approved]),
        ("2. Approved package, receiver pins the OEM public key",
         ["--pubkey", owner_pub, approved]),
        ("3. Received package: report silently replaced by Rev B",
         [swapped]),
        ("4. Rebuilt package (Rev B) sealed with a substitute key, "
         "open verification", [resealed]),
        ("5. Same rebuilt package, receiver pins the OEM public key",
         ["--pubkey", owner_pub, resealed]),
    ]
    for title, args in cases:
        code, out = run_verify(args)
        lines.append("")
        lines.append(title)
        lines.append(f"  $ uibc verify {' '.join(args).replace(PKGS + '/', '')}")
        for ln in out.splitlines():
            lines.append("  " + ln)
        lines.append(f"  exit code: {code}")
    transcript = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "RUN-TRANSCRIPT.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(transcript)
    print(transcript)


if __name__ == "__main__":
    main()
