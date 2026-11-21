"""Build the fictional Link-1 change-evidence (PCCP-side) demo packages.

Fictional throughout: "Meridian Medical" and the "CardioPatch CP-2" do not
exist. Demo keys use a published seed on purpose so anyone can rebuild the
exact packages and reproduce every verdict in RUN-TRANSCRIPT.txt.
DEMO ONLY - never use a published seed for anything real.

Part of the uibc-core repo: examples/link1-change-evidence/.
Run:  python3 build_demo.py     (uses the installed uibc-core; set UIBC_ROOT to a checkout to override)
"""

import json
import os
import shutil
import subprocess
import sys

UIBC_ROOT = os.environ.get("UIBC_ROOT", "")  # empty = use the installed uibc-core
if UIBC_ROOT:
    sys.path.insert(0, UIBC_ROOT)

import uibc_core.cli as ucli  # noqa: E402
from uibc_core.signing import ed_public_key  # noqa: E402
from uibc_core.verify import verify as verify_pkg  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PKGS = os.path.join(HERE, "packages")
SRC = os.path.join(HERE, "_src")

OWNER_SEED = bytes([3] * 32)  # DEMO ONLY - published, worthless, by design

EVIDENCE = [
    ("change-description.md", "INPUT"),
    ("evaluation-report.md", "EVALUATION"),
    ("approval-record.md", "HUMAN_DECISION"),
    ("previous-version-manifest.md", "RETIREMENT"),
]


def _a(**kw):
    return type("A", (), kw)()


def write_key(seed, key_path, pub_path=None):
    with open(key_path, "w", encoding="ascii") as f:
        f.write("ed25519:" + seed.hex())
    if pub_path:
        with open(pub_path, "w", encoding="ascii") as f:
            f.write(ed_public_key(seed).hex())


def build_package(dest, key_path):
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    ucli.cmd_init(_a(path=dest))
    ucli.cmd_register(_a(path=dest, agent_id="cardiopatch-cp2-change-evidence",
                         owner="meridian-medical-rd",
                         agent_type="evidence-package", version="1.2.0"))
    ucli.cmd_event(_a(path=dest, type="ACTIVATE", actor="meridian-medical-rd"))
    for name, etype in EVIDENCE:
        ucli.cmd_evidence(_a(path=dest, type=etype,
                             file=os.path.join(SRC, name),
                             media_type="text/markdown",
                             note="fictional change evidence"))
    # submit always finalizes the manifest; the seal is added only when a
    # key is given. key=None is the faithful "handed over unsealed" case:
    # a complete submission whose provenance is unattested.
    ucli.cmd_submit(_a(path=dest, key=key_path))


def run_cli(args):
    cmd = [sys.executable, "-m", "uibc_core.cli"] + args
    env = dict(os.environ)
    if UIBC_ROOT:
        env["PYTHONPATH"] = UIBC_ROOT
    r = subprocess.run(cmd, capture_output=True, text=True, env=env,
                       cwd=UIBC_ROOT)
    return r.returncode, (r.stdout + r.stderr).strip()


def check_detail(report, cid):
    for c in report["checks"]:
        if c["id"] == cid:
            return c["result"], c["detail"]
    return None, None


def main():
    if os.path.isdir(PKGS):
        shutil.rmtree(PKGS)
    os.makedirs(PKGS)
    owner_key = os.path.join(HERE, "meridian-rd.key")
    owner_pub = os.path.join(HERE, "meridian-rd.pub")
    write_key(OWNER_SEED, owner_key, owner_pub)

    approved = os.path.join(PKGS, "change-approved")
    build_package(approved, owner_key)

    swapped = os.path.join(PKGS, "change-swapped")
    shutil.copytree(approved, swapped)
    target = os.path.join(swapped, "evidence", "files", "evaluation-report.md")
    with open(os.path.join(SRC, "evaluation-report-swapped.md"),
              encoding="utf-8") as f:
        swapped_text = f.read()
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(swapped_text)

    unsigned = os.path.join(PKGS, "change-unsigned")
    build_package(unsigned, None)

    lines = []
    lines.append("CHANGE-EVIDENCE DEMO (Link 1) - verification transcript")
    lines.append("Fictional data throughout: Meridian Medical / CardioPatch CP-2")
    import uibc_core
    lines.append("Spec: spec-link1-change-package.md (2026-11-10); run 2026-11-18")
    lines.append(f"Built and verified with uibc-core {uibc_core.__version__} "
                 f"from {UIBC_ROOT or 'the installed package'}")
    lines.append("=" * 66)

    results = {}

    def record(label, path, pubkey=None):
        rep = verify_pkg(path, pubkey=None if not pubkey else
                         bytes.fromhex(open(pubkey).read().strip()))
        results[label] = rep["result"]
        lines.append("")
        lines.append(f"--- {label}")
        lines.append(f"    overall result: {rep['result']}  "
                     f"trust_level: {rep.get('trust_level', '(field absent in this version)')}")
        for cid in ("S4", "S6"):
            res, det = check_detail(rep, cid)
            if res:
                lines.append(f"    {cid}: {res} - {det}")
        return rep

    record("1. change-approved, open verification", approved)
    record("2. change-approved, receiver pins the R&D public key",
           approved, owner_pub)
    record("3. change-swapped (evaluation report replaced after sealing)",
           swapped)
    record("4. change-unsigned (same files, never sealed)", unsigned)

    lines.append("")
    lines.append("--- gate decisions (uibc gate)")
    gates = {}
    for label, args in [
        ("change-approved (pinned)", ["gate", "--pubkey", owner_pub, approved]),
        ("change-swapped", ["gate", swapped]),
        ("change-unsigned", ["gate", unsigned]),
    ]:
        rc, out = run_cli(args)
        try:
            g = json.loads(out)
            summary = f"decision={g['decision']} reason={g['reason']}"
        except Exception:
            summary = "unparsable output: " + out[:120]
        gates[label] = summary
        lines.append(f"    {label}: exit={rc} :: {summary}")

    lines.append("")
    lines.append("--- reproducibility: full verify set, second run")
    again = {}
    again["approved"] = verify_pkg(approved)["result"]
    again["swapped"] = verify_pkg(swapped)["result"]
    again["unsigned"] = verify_pkg(unsigned)["result"]
    lines.append(f"    approved={again['approved']} swapped={again['swapped']} "
                 f"unsigned={again['unsigned']}")

    lines.append("")
    lines.append("--- spec expectations vs actual")
    exp = [
        ("approved open", "PASS", results["1. change-approved, open verification"]),
        ("approved pinned", "PASS",
         results["2. change-approved, receiver pins the R&D public key"]),
        ("swapped", "FAIL",
         results["3. change-swapped (evaluation report replaced after sealing)"]),
        ("unsigned", "INCONCLUSIVE",
         results["4. change-unsigned (same files, never sealed)"]),
    ]
    ok = True
    for name, want, got in exp:
        match = "MATCH" if want == got else "MISMATCH"
        ok = ok and want == got
        lines.append(f"    {name:18} expected {want:13} got {got:13} {match}")
    lines.append(f"    verdicts reproduced on second run: "
                 f"{again['approved'] == exp[0][2] and again['swapped'] == exp[2][2] and again['unsigned'] == exp[3][2]}")
    lines.append(f"    ALL SPEC EXPECTATIONS MET: {ok}")

    text = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "RUN-TRANSCRIPT.txt"), "w",
              encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
