"""Build the decision-vector suite: packages plus overlays with expected verdicts.

The 36-case conformance suite answers "does your verifier refuse a broken
package?" It says nothing about the layer above — ALLOW / DENY / HOLD, and what
the overlay does to that verdict. That layer is where a revocation can be
silently ignored, so a second implementer needs fixed inputs and fixed
expectations there too.

Every case is a real package on disk (no invented JSON), so a runner can point
any implementation at it. Keys are generated once per build and only the public
half is written into the suite; the seeds are discarded, which means the suite
is reproducible only in shape, not byte-for-byte — stated here rather than
pretended otherwise.

Run:  python tools/build_decision_vectors.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "conformance", "decisions")
PY = sys.executable


def cli(*args, cwd=None):
    proc = subprocess.run([PY, "-m", "uibc_core.cli", *args],
                          capture_output=True, text=True, cwd=REPO)
    if proc.returncode != 0:
        raise SystemExit("cli failed: %s\n%s\n%s" % (args, proc.stdout, proc.stderr))
    return proc.stdout


def keygen(path):
    cli("keygen", "--out", path, "--ed25519")
    return path, path + ".pub"


def base_package(work, name):
    """A small, correct package sealed with an Ed25519 owner key."""
    seed, pub = keygen(os.path.join(work, name + ".key"))
    pkg = os.path.join(work, name)
    cli("init", pkg)
    cli("register", pkg, "--agent-id", name, "--owner", "alice")
    for fname, body in (("a.txt", "alpha\n"), ("b.txt", "beta\n")):
        p = os.path.join(work, fname)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        cli("evidence", pkg, "--file", p, "--type", "ACTION", "--media-type", "text/plain")
    cli("submit", pkg, "--key", seed)
    return pkg, seed, pub


def revoke(pkg, seed, out, reason="OWNER_REQUEST"):
    cli("revoke", pkg, "--key", seed, "--out", out, "--reason-code", reason)
    return out


def copy_case(work, case_id, pkg, overlay=None, anchor=None):
    """Copy the case's files into the suite and return its manifest fields."""
    dest = os.path.join(OUT, "cases", case_id)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    shutil.copytree(pkg, os.path.join(dest, "pkg"))
    fields = {"pkg": "cases/%s/pkg" % case_id}
    if overlay:
        shutil.copyfile(overlay, os.path.join(dest, "revocation.json"))
        fields["overlay"] = "cases/%s/revocation.json" % case_id
    if anchor:
        shutil.copyfile(anchor, os.path.join(dest, "owner.pub"))
        fields["anchor"] = "cases/%s/owner.pub" % case_id
    return fields


def main():
    work = tempfile.mkdtemp(prefix="dvectors_")
    os.makedirs(os.path.join(OUT, "cases"), exist_ok=True)

    pkg_a, seed_a, pub_a = base_package(work, "clean-a")
    pkg_b, seed_b, pub_b = base_package(work, "clean-b")
    foreign_seed, foreign_pub = keygen(os.path.join(work, "foreign.key"))

    rev_a = revoke(pkg_a, seed_a, os.path.join(work, "rev-a.json"))
    rev_foreign = revoke(pkg_a, foreign_seed, os.path.join(work, "rev-foreign.json"))
    # A revocation that really belongs to another package: correctly signed,
    # but its target_root is not this package's evidence_root. The gate must
    # notice that before it looks at the signature (MISMATCH, not REVOKED).
    rev_other = revoke(pkg_b, seed_b, os.path.join(work, "rev-other.json"))

    cases = []

    cases.append(dict(
        id="01",
        what="correct package, no overlay",
        why="baseline: nothing is wrong, so the decision must not be a refusal",
        expect={"decision": "ALLOW", "exit": 0},
        **copy_case(work, "01", pkg_a)))

    cases.append(dict(
        id="02",
        what="correct package + valid owner revocation",
        why="the overlay is the only reason to refuse here; verify itself still PASSes",
        expect={"decision": "DENY", "exit": 2},
        **copy_case(work, "02", pkg_a, overlay=rev_a, anchor=pub_a)))

    cases.append(dict(
        id="03",
        what="correct package + revocation, verifier given no anchor",
        why="unverifiable revocation must HOLD: 'cannot check' is not 'not revoked'",
        expect={"decision": "HOLD", "exit": 3},
        **copy_case(work, "03", pkg_a, overlay=rev_a)))

    cases.append(dict(
        id="04",
        what="correct package + revocation signed by a different key",
        why="a stranger's revocation is refused, and never counted as absent",
        expect={"decision": "HOLD", "exit": 3},
        **copy_case(work, "04", pkg_a, overlay=rev_foreign, anchor=pub_a)))

    cases.append(dict(
        id="05",
        what="correct package + a revocation belonging to another package",
        why="target_root mismatch is checked before the signature and HOLDs",
        expect={"decision": "HOLD", "exit": 3},
        **copy_case(work, "05", pkg_a, overlay=rev_other, anchor=pub_a)))

    tampered = os.path.join(work, "tampered")
    shutil.copytree(pkg_a, tampered)
    victim = None
    for root, _dirs, files in os.walk(os.path.join(tampered, "evidence")):
        for f in files:
            if f.endswith(".txt"):
                victim = os.path.join(root, f)
                break
        if victim:
            break
    if not victim:
        raise SystemExit("no evidence file to tamper with")
    with open(victim, "ab") as f:
        f.write(b"x")
    cases.append(dict(
        id="06",
        what="one byte appended to an evidence file, no overlay",
        why="S4 must fire; a verifier that misses this is useless for admission",
        expect={"decision": "DENY", "exit": 2},
        **copy_case(work, "06", tampered, anchor=pub_a)))

    # 07: revocation wins over a broken package — the cascade order is normative.
    cases.append(dict(
        id="07",
        what="tampered package + valid owner revocation",
        why="the documented order puts REVOKED first; two refusals must not flip the decision",
        expect={"decision": "DENY", "exit": 2},
        **copy_case(work, "07", tampered, overlay=rev_a, anchor=pub_a)))

    manifest = {
        "format": "uibc-core/decisions/1",
        "generated_by": "tools/build_decision_vectors.py",
        "about": "Fixed inputs and fixed expectations for the decision layer "
                 "(ALLOW/DENY/HOLD and the revocation overlay). The 36-case "
                 "conformance suite covers verify(); this covers what a gate "
                 "must answer on top of it.",
        "rules": [
            "A case passes when the decision and its exit code both match.",
            "HOLD is never a pass for a DENY case: 'cannot verify' is not 'not revoked'.",
            "Both halves matter: case 01 must be accepted, the rest must be refused.",
            "Seeds are not shipped. Rebuilding produces the same cases in shape, "
            "with different keys and therefore different bytes.",
            "Placeholders for an external runner: {pkg} {overlay} {anchor}; a case "
            "without an overlay or anchor simply omits the argument.",
        ],
        "cases": cases,
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print("wrote %d cases to %s" % (len(cases), OUT))


if __name__ == "__main__":
    main()
