"""Build the committed sample package in examples/sample-package/.

Deterministic identity, deliberately INSECURE demo key: the seed is the
byte sequence 00 01 02 ... 1f, published here on purpose so anyone can
rebuild, re-seal, and re-verify the exact sample and get the same
public key. Never use a published seed for anything real.

Run from the repository root:  python examples/build_example.py
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import uibc_core.cli as ucli  # noqa: E402

DEMO_SEED = bytes(range(32))  # DEMO ONLY - published, worthless, by design
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "sample-package")
KEY = os.path.join(HERE, "sample-owner.key")
PUB = os.path.join(HERE, "sample-owner.pub")


def _a(**kw):
    return type("A", (), kw)()


def main():
    if os.path.isdir(PKG):
        shutil.rmtree(PKG)
    for p in (KEY, PUB):
        if os.path.exists(p):
            os.remove(p)
    with open(KEY, "w", encoding="ascii") as f:
        f.write("ed25519:" + DEMO_SEED.hex())
    from uibc_core.signing import ed_public_key
    with open(PUB, "w", encoding="ascii") as f:
        f.write(ed_public_key(DEMO_SEED).hex())

    ucli.cmd_init(_a(path=PKG))
    ucli.cmd_register(_a(path=PKG, agent_id="sample-support-agent",
                         owner="sample-owner", agent_type="software-agent",
                         version="1.0.0"))
    ucli.cmd_event(_a(path=PKG, type="ACTIVATE", actor="sample-owner"))
    log = os.path.join(HERE, "_log.txt")
    with open(log, "w", encoding="utf-8", newline="\n") as f:
        f.write("2026-11-10T08:00:00Z ACTION triage ticket #1042: "
                "classified as billing, routed to queue B\n")
        f.write("2026-11-10T08:04:00Z ACTION reply drafted; "
                "human approval recorded before send\n")
    ucli.cmd_evidence(_a(path=PKG, type="ACTION", file=log,
                         media_type="text/plain",
                         note="sample action log (fictional)"))
    note = os.path.join(HERE, "_eval.txt")
    with open(note, "w", encoding="utf-8", newline="\n") as f:
        f.write("Sample evaluation note (fictional): 20 sampled replies, "
                "20 matched the approved template; 0 sent without approval.\n")
    ucli.cmd_evidence(_a(path=PKG, type="EVALUATION", file=note,
                         media_type="text/plain",
                         note="sample evaluation (fictional)"))
    os.remove(log)
    os.remove(note)
    ucli.cmd_submit(_a(path=PKG, key=KEY))

    from uibc_core.verify import verify
    r = verify(PKG)
    print(f"sample package built at {PKG}")
    print(f"stranger verification (no key): {r['result']} "
          f"(assurance: {r['assurance']})")
    assert r["result"] == "PASS", "sample package must verify PASS publicly"


if __name__ == "__main__":
    main()
