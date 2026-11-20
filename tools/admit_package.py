"""Admit a foreign artifact: one command from "a file I downloaded" to a verdict.

`uibc verify` judges a *UIBC package* — a directory with manifest, identity,
lifecycle and evidence that somebody built with this CLI. That is the wrong
question for the artefact most people actually have: a wheel from PyPI, a zip
someone emailed, a skill folder cloned from a repo. None of those carry a seal,
so a verifier is right to say INCONCLUSIVE and it means nothing to the person
asking "is this safe to install".

This tool answers the question that can be answered honestly: *bind these exact
bytes, seal the binding with the caller's own key, and then let anyone verify
that the bytes they hold are the bytes that were admitted.*

It does not scan for malware, and it does not judge behaviour. Those are other
tools' claims. What it does is refuse to be vague: every verdict here is about
a sha256-pinned artifact and its full member inventory, and every refusal to
produce a rate (a single artifact has no false-accept rate) is printed as `n/a`
rather than filled with a number.

Usage:

    python tools/admit_package.py --artifact dist/pkg-1.0.whl --out /tmp/admit \
        --agent-id pkg-1.0 --owner "alice" --key owner.key --pinned owner.key.pub

Exit codes: 0 admitted and verified, 1 verdict not PASS, 2 usage/artifact error.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time
import zipfile

TOOL = "admit_package/1.0"
MAX_DIR_FILES = 50
DISCLOSURE_FIELDS = ("convention", "numerator", "denominator", "truth",
                    "corpus", "na_policy", "coverage")


class ArtifactError(Exception):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _zip_members(path):
    out = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            h = hashlib.sha256()
            with z.open(info) as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out.append({"path": info.filename, "bytes": info.file_size,
                        "sha256": h.hexdigest()})
    return out


def _tar_members(path):
    out = []
    with tarfile.open(path) as t:
        for m in t.getmembers():
            if not m.isfile():
                continue
            f = t.extractfile(m)
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
            out.append({"path": m.name, "bytes": m.size, "sha256": h.hexdigest()})
    return out


def _dir_members(path):
    out = []
    for root, _dirs, files in os.walk(path):
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, path).replace(os.sep, "/")
            out.append({"path": rel, "bytes": os.path.getsize(full),
                        "sha256": sha256_file(full)})
    return sorted(out, key=lambda m: m["path"])


def inventory(artifact):
    """Return (kind, digest, size, members) for a file or directory."""
    if os.path.isdir(artifact):
        return "directory", None, None, _dir_members(artifact)
    if not os.path.isfile(artifact):
        raise ArtifactError("not a file or directory: %s" % artifact)
    digest, size = sha256_file(artifact), os.path.getsize(artifact)
    if zipfile.is_zipfile(artifact):
        return "zip/wheel", digest, size, _zip_members(artifact)
    if tarfile.is_tarfile(artifact):
        return "tar", digest, size, _tar_members(artifact)
    # A bare file is still admissible: the artifact *is* the member.
    return "file", digest, size, [{"path": os.path.basename(artifact),
                                   "bytes": size, "sha256": digest}]


def build_inventory_doc(artifact, kind, digest, size, members):
    return {
        "tool": TOOL,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifact": {"name": os.path.basename(artifact), "kind": kind,
                     "sha256": digest, "bytes": size},
        "members": members,
        "member_count": len(members),
        # Stated because a reader will ask: what did this not look at?
        "not_covered": [
            "file contents beyond hashing (no malware scan, no heuristics)",
            "behaviour after install (no execution, no sandbox run)",
            "dependency graph and transitive packages",
        ],
    }


def _cli(py, *args, **kw):
    """Run the verifier CLI and return (exit, stdout, stderr)."""
    proc = subprocess.run([py, "-m", "uibc_core.cli", *args],
                          capture_output=True, text=True, timeout=120, **kw)
    return proc.returncode, proc.stdout, proc.stderr


def admit(artifact, out, agent_id, owner, py, key=None, pinned=None,
          media_type="application/octet-stream"):
    """Build a sealed UIBC package around the artifact and verify it.

    Returns a dict with the inventory, both verdicts (open and pinned) and the
    disclosure row. Nothing is assumed about the artifact's provenance: the
    only claim is that these bytes were sealed by this key at this time.
    """
    artifact = os.path.abspath(artifact)
    out = os.path.abspath(out)
    kind, digest, size, members = inventory(artifact)
    inv = build_inventory_doc(artifact, kind, digest, size, members)

    if os.path.exists(out):
        # Refuse rather than overwrite: a second admission into the same
        # directory would silently mix two artifacts' evidence.
        raise ArtifactError("output directory already exists: %s" % out)

    steps = []
    def step(args):
        code, so, se = _cli(py, *args)
        steps.append({"cmd": " ".join(args[:2]), "exit": code})
        if code != 0:
            raise ArtifactError("uibc %s failed (exit %s): %s"
                                % (args[0], code, (se or so).strip()[:400]))
        return so

    step(["init", out])
    step(["register", out, "--agent-id", agent_id, "--owner", owner])
    if kind == "directory":
        # A directory has no single byte sequence to point at. Rather than
        # invent an archive format and then claim "the bytes you hold", this
        # seals each member individually, up to a bound: fifty files is more
        # than a skill or a small package, and a tree that large should be
        # packaged by the owner (wheel/tar) so the claim stays one hash.
        if len(members) > MAX_DIR_FILES:
            raise ArtifactError(
                "%d files in the directory; seal a packaged artifact instead "
                "(wheel/zip/tar). This tool does not invent an archive format "
                "and then claim its bytes are yours." % len(members))
        for m in members:
            step(["evidence", out, "--file", os.path.join(artifact, *m["path"].split("/")),
                  "--type", "ACTION", "--media-type", media_type,
                  "--note", "member: %s" % m["path"]])
    else:
        step(["evidence", out, "--file", artifact, "--type", "ACTION",
              "--media-type", media_type, "--note", "admitted artifact"])
    # Written OUTSIDE the package: a file at the package root that the manifest
    # does not declare is exactly what S1 calls "undeclared files" (measured:
    # first run FAILed on S1 for this reason).
    inv_path = out + ".inventory.json"
    with open(inv_path, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2, sort_keys=True)
    step(["evidence", out, "--file", inv_path, "--type", "VERIFICATION",
          "--media-type", "application/json", "--note", "member inventory"])
    os.remove(inv_path)
    submit = ["submit", out]
    if key:
        submit += ["--key", key]
    step(submit)

    open_v = _verify_dict(py, out, None)
    verdicts = {"open": open_v["result"]}
    if pinned:
        verdicts["pinned"] = _verify_dict(py, out, pinned)["result"]

    row = disclosure_row(verdicts, kind, len(members))
    return {"inventory": inv, "steps": steps, "verdicts": verdicts,
            "checks": sorted({c["id"] for c in open_v.get("checks", [])
                              if c.get("result") != "PASS"}),
            "disclosure": row, "package": out}


def _verify(py, out, pinned):
    args = ["verify", out]
    if pinned:
        args += ["--pubkey", pinned]
    code, so, se = _cli(py, *args)
    if code not in (0, 1) or not so.strip():
        raise ArtifactError("verify produced no verdict: %s" % (se or so)[:300])
    return so


def _verify_dict(py, out, pinned):
    return json.loads(_verify(py, out, pinned))


def disclosure_row(verdicts, kind, member_count):
    """Seven-field row, with `n/a` where a number would be a lie.

    One artifact has no false-accept rate. The rule we audit other people with
    says n < 30 must not be reported as a percentage, so this prints `n/a` and
    says why — including in the same row, so the reason travels with the number.
    """
    return {
        "convention": "pinned (owner public key)" if "pinned" in verdicts
                      else "open (no pin; seal is self-asserted)",
        "numerator": "n/a",
        "denominator": "1 artifact",
        "truth": "bytes sealed by the admitting key at admission time",
        "corpus": "single artifact, %d members (%s)" % (member_count, kind),
        "na_policy": "INCONCLUSIVE kept as INCONCLUSIVE; no rate computed for n<30",
        "coverage": "artifact sha256 + full member inventory; no content analysis",
        "note": "n/a numerator: a single admission cannot express a rate",
        "verdicts": verdicts,
    }


def render(result):
    inv = result["inventory"]
    lines = []
    lines.append("# Admission record")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    lines.append("| artifact | `%s` (%s, %s bytes) |"
                 % (inv["artifact"]["name"], inv["artifact"]["kind"],
                    inv["artifact"]["bytes"]))
    lines.append("| artifact sha256 | `%s` |" % (inv["artifact"]["sha256"] or
                                                "n/a (directory)"))
    lines.append("| members | %d |" % inv["member_count"])
    lines.append("| package | `%s` |" % result["package"])
    for k, v in result["verdicts"].items():
        lines.append("| verdict (%s) | **%s** |" % (k, v))
    lines.append("")
    lines.append("## Disclosure row (seven fields)")
    lines.append("")
    lines.append("| " + " | ".join(DISCLOSURE_FIELDS) + " |")
    lines.append("|" + "---|" * len(DISCLOSURE_FIELDS))
    lines.append("| " + " | ".join(result["disclosure"][f] for f in DISCLOSURE_FIELDS) + " |")
    lines.append("")
    if result["checks"]:
        lines.append("Non-PASS checks: %s" % ", ".join(result["checks"]))
    else:
        lines.append("Non-PASS checks: none")
    lines.append("")
    lines.append("## What this does not say")
    lines.append("")
    for item in inv["not_covered"]:
        lines.append("- %s" % item)
    lines.append("")
    lines.append("A PASS here means: the bytes you hold are the bytes that were sealed.")
    lines.append("It does not mean the artifact is good. Two different claims.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="admit a foreign artifact into a sealed UIBC package")
    ap.add_argument("--artifact", required=True, help="wheel/zip/tar.gz/dir/single file")
    ap.add_argument("--out", required=True, help="directory for the new package (must not exist)")
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--key", default=None, help="key file for the seal (hex, or ed25519: form)")
    ap.add_argument("--pinned", default=None, help="public key to pin at verify time")
    ap.add_argument("--python", default=sys.executable, help="interpreter that can import uibc_core")
    ap.add_argument("--json", action="store_true", help="print the record as JSON")
    a = ap.parse_args(argv)
    try:
        result = admit(a.artifact, a.out, a.agent_id, a.owner, a.python,
                       key=a.key, pinned=a.pinned)
    except ArtifactError as e:
        print("ADMISSION ERROR: %s" % e, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(render(result))
    return 0 if result["verdicts"].get("pinned", result["verdicts"]["open"]) == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
