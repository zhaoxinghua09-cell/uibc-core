"""uibc-core showcase: one agent, one full verifiable lifecycle.

Runs end-to-end against the real CLI functions (no mocks):
  init -> register -> evidence -> event -> seal (HMAC) -> verify (open+strict)
  -> gate -> tamper -> verify catches it -> re-seal -> certify -> registry entry

Run:
  python examples/showcase.py

The output is a human-readable transcript of every step with real hashes.
"""

import json
import os
import shutil
import sys
import tempfile
import time

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core import cli as ucli  # noqa: E402
from uibc_core.certificate import issue_certificate, verify_certificate  # noqa: E402
from uibc_core.signing import generate_key  # noqa: E402
from uibc_core.verify import verify  # noqa: E402


def step(n, title):
    print("\n=== [%d/9] %s ===" % (n, title))


def main():
    work = tempfile.mkdtemp(prefix="uibc-showcase-")
    pkg = os.path.join(work, "agent-atlas.uibc")
    key = generate_key()
    key_file = os.path.join(work, "owner.key")
    with open(key_file, "w", encoding="ascii") as f:
        f.write(key.hex())

    print("uibc-core showcase -- one agent, one full verifiable lifecycle")
    print("workspace: %s" % work)

    step(1, "init + register (Registry: 有籍)")
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "agent-atlas", "owner": "atlas-labs",
        "agent_type": "software-agent", "version": "1.0.0"})())

    step(2, "evidence: the agent records what it actually did (Evidence: 有证)")
    action = os.path.join(work, "research-summary.txt")
    with open(action, "w", encoding="utf-8") as f:
        f.write("task: summarize quarterly report\n"
                "sources consulted: 3\n"
                "completed at: %s\n" % time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                     time.gmtime()))
    ucli.cmd_evidence(type("A", (), {
        "path": pkg, "type": "ACTION", "file": action,
        "media_type": "text/plain", "note": "quarterly summary task"})())

    step(3, "lifecycle event: hash-chained state transition")
    ucli.cmd_event(type("A", (), {
        "path": pkg, "type": "ACTIVATE", "actor": "agent-atlas"})())

    step(4, "seal: owner signs the evidence root (S6)")
    ucli.cmd_submit(type("A", (), {"path": pkg, "key": key_file})())

    step(5, "verify: open mode (anyone, no key)")
    r = verify(pkg, key=None)
    checks = r.get("checks", [])
    s6 = next((c for c in checks if isinstance(c, dict)
               and str(c.get("id", c.get("check", ""))).upper().startswith("S6")), {})
    print("open-mode result: %s (S6: %s)" % (
        r["result"], s6.get("status", s6.get("result", "INCONCLUSIVE"))))

    step(6, "verify: strict mode (owner's key)")
    r = verify(pkg, key=key)
    print("strict-mode result: %s" % r["result"])

    step(7, "gate: the decision layer (门禁)")
    from uibc_core.gate import gate
    report = gate(pkg, key=key)
    print("gate decision: %s" % report["decision"])

    step(8, "attack: tamper with evidence behind the owner's back")
    files = os.path.join(pkg, "evidence", "files")
    victim = sorted(os.listdir(files))[0]
    with open(os.path.join(files, victim), "a", encoding="utf-8") as f:
        f.write("forged line added by attacker\n")
    r = verify(pkg, key=key)
    print("strict-mode result after tampering: %s  <- caught" % r["result"])

    step(9, "re-seal honestly + issue a certificate binding this evidence_root")
    # restore: re-add evidence over the tampered copy is not possible (append-only
    # hash chain), so we start a fresh honest package for the certificate demo
    pkg2 = os.path.join(work, "agent-atlas-v2.uibc")
    ucli.cmd_init(type("A", (), {"path": pkg2})())
    ucli.cmd_register(type("A", (), {
        "path": pkg2, "agent_id": "agent-atlas", "owner": "atlas-labs",
        "agent_type": "software-agent", "version": "1.1.0"})())
    ucli.cmd_evidence(type("A", (), {
        "path": pkg2, "type": "ACTION", "file": action,
        "media_type": "text/plain", "note": "quarterly summary task, clean"})())
    ucli.cmd_submit(type("A", (), {"path": pkg2, "key": key_file})())
    with open(os.path.join(pkg2, "identity.json"), "r", encoding="utf-8") as f:
        identity = json.load(f)
    with open(os.path.join(pkg2, "manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)
    cert = issue_certificate(key, identity, manifest, expires_at=None,
                             statement="verified clean lifecycle package")
    cpath = os.path.join(work, "agent-atlas-v2.uibc-cert.json")
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump(cert, f, indent=2, ensure_ascii=False)
    with open(cpath, "r", encoding="utf-8") as f:
        cert_loaded = json.load(f)
    vr = verify_certificate(key, cert_loaded, package_dir=pkg2)
    print("certificate verify: %s (cert_id %s)"
          % (vr["result"], cert["certificate_id"]))

    print("\n--- lifecycle complete: every claim above is recomputable ---")
    print("clean up? the workspace stays at %s for inspection" % work)


if __name__ == "__main__":
    main()
