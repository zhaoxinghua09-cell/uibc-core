#!/usr/bin/env python3
"""Produce the release lab bundle: one file a stranger can recompute, plus the
three controls measured rather than asserted.

A release that ships only the zip asks a reader to trust that the corpus
discriminates and that the numbers came from a working verifier. This script
measures those three things in throwaway directories and writes them into
`uibc-lab-bundle-<version>.json` next to a `CORPUS-DIGESTS.txt`.

    python tools/release_lab_bundle.py --version 0.4.1 --out release/

Scenario A: the archive as shipped, unzipped, `python run.py`, no install.
Scenario B: a verifier that answers PASS to everything — must score far below full.
Scenario C: no verifier available to the interpreter — must exit 3 and write no receipt.

If any control does not behave as specified the script fails instead of shipping a
bundle that describes a run nobody watched.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import lab_manifest  # noqa: E402
import check_lab_bundle  # noqa: E402

ARCHIVE_NAME = "uibc-conformance-%s.zip"

ACCEPT_ALL = """import json
# A verifier that answers PASS to everything. It exists so the corpus has to
# prove it discriminates; if this scores full marks, the corpus does not.
print(json.dumps({"result": "PASS", "checks": []}))
"""


def _run(cmd, cwd, env=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, env=env)


def _unzip(archive, dest):
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)


def _tail(text, n=3):
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return " / ".join(lines[-n:])


def measure(archive, version, workroot):
    """Run the three scenarios and return the bundle dict."""
    archive = os.path.abspath(archive)
    env_clean = dict(os.environ)
    env_clean.pop("PYTHONPATH", None)

    a = os.path.join(workroot, "a")
    os.makedirs(a)
    _unzip(archive, a)
    proc_a = _run([sys.executable, "run.py"], cwd=a, env=env_clean)
    receipt_a = os.path.join(a, "receipt.json")
    if not os.path.isfile(receipt_a):
        raise SystemExit("scenario A wrote no receipt (exit %d): %s"
                         % (proc_a.returncode, _tail(proc_a.stdout)))
    with open(receipt_a, encoding="utf-8") as f:
        rec = json.load(f)
    total, passed = rec.get("cases"), rec.get("passed")
    if not isinstance(total, int) or passed != total:
        raise SystemExit("scenario A did not pass its own corpus: %s/%s" % (passed, total))

    b = os.path.join(workroot, "b")
    os.makedirs(b)
    _unzip(archive, b)
    stub = os.path.join(b, "accept_all.py")
    with open(stub, "w", encoding="utf-8") as f:
        f.write(ACCEPT_ALL)
    proc_b = _run([sys.executable, "run.py", "--verify",
                   '"%s" "%s" verify {pkg}' % (sys.executable, stub)], cwd=b, env=env_clean)
    receipt_b = os.path.join(b, "receipt.json")
    if not os.path.isfile(receipt_b):
        raise SystemExit("scenario B wrote no receipt (exit %d): %s"
                         % (proc_b.returncode, _tail(proc_b.stdout)))
    with open(receipt_b, encoding="utf-8") as f:
        hostile = json.load(f)
    if hostile.get("passed") is None or hostile["passed"] >= total:
        raise SystemExit("the accept-all verifier scored %s/%s: the corpus does not discriminate"
                         % (hostile.get("passed"), total))

    c = os.path.join(workroot, "c")
    os.makedirs(c)
    _unzip(archive, c)
    pyz = os.path.join(c, "uibc_core.pyz")
    if os.path.isfile(pyz):
        os.remove(pyz)
    proc_c = _run([sys.executable, "run.py"], cwd=c, env=env_clean)
    if proc_c.returncode != 3:
        raise SystemExit("scenario C exited %d, not 3 — an environment failure was not told apart "
                         "from a corpus result" % proc_c.returncode)
    if os.path.isfile(os.path.join(c, "receipt.json")):
        raise SystemExit("scenario C wrote a receipt: 0/36 from a missing verifier is publishable "
                         "as 'the corpus fails everything'")

    shutil.copy2(receipt_a, os.path.join(workroot, "receipt.json"))

    return {
        "kind": lab_manifest.KIND,
        "question": "Does the %s corpus discriminate, and does the reference verifier pass it "
                    "without installing anything?" % version,
        "claim": "the archive carries its verifier; %d/%d cases pass with it and %d/%d with a "
                 "verifier that answers PASS to everything" % (total, total, hostile["passed"], total),
        "built_utc": lab_manifest._now(),
        "archive": {
            "path": os.path.basename(archive),
            "bytes": os.path.getsize(archive),
            "sha256": lab_manifest._sha256(archive),
        },
        "roles": {
            "runner": "release pipeline (repository maintainer)",
            "operator": "GitHub Actions",
            "custodian": "repository maintainer",
        },
        "exposure": {
            "blind": "directed — the pipeline is maintained by the corpus author",
            "read_before_run": "the checks and expected reasons are in this repository",
            "declared_by": "repository maintainer",
            "declared_utc": lab_manifest._now(),
        },
        "run": {
            "command": "python run.py",
            "exit_code": proc_a.returncode,
            "python": "%d.%d.%d" % sys.version_info[:3],
            "platform": sys.platform,
            "stdout_tail": _tail(proc_a.stdout),
        },
        "controls": {
            "positive": {"what": "the shipped corpus with the bundled verifier",
                         "result": "%d/%d" % (passed, total)},
            "hostile": {"what": "a verifier that answers PASS to everything",
                        "result": "%d/%d" % (hostile["passed"], total), "cases_total": total},
            "negative": {"what": "the bundled verifier removed, none installed",
                         "result": "exit %d, no receipt written" % proc_c.returncode},
        },
        "limits": [
            "one corpus for one version",
            "AEE predicate only; not a claim about other formats",
            "author-produced: this is not an external node",
            "no external timestamp of this bundle",
        ],
        "bytes": lab_manifest.digest_tree(workroot, archive=archive),
    }


def write_digests(path, files):
    lines = ["%s  %d  %s" % (lab_manifest._sha256(f), os.path.getsize(f), os.path.basename(f))
             for f in files]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", required=True, help="e.g. 0.4.1")
    ap.add_argument("--archive", default=None,
                    help="defaults to conformance/uibc-conformance-<version>.zip")
    ap.add_argument("--out", default="release")
    args = ap.parse_args(argv)

    archive = args.archive or os.path.join(
        os.path.dirname(_HERE), "conformance", ARCHIVE_NAME % args.version)
    if not os.path.isfile(archive):
        raise SystemExit("no archive at %s — build it first with "
                         "tools/build_conformance_bundle.py %s" % (archive, args.version))
    os.makedirs(args.out, exist_ok=True)

    work = tempfile.mkdtemp(prefix="relbundle_")
    try:
        bundle = measure(archive, args.version, work)
        bundle_path = os.path.join(args.out, "uibc-lab-bundle-%s.json" % args.version)
        with open(bundle_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(bundle, f, indent=2)
            f.write("\n")

        reasons = check_lab_bundle.check(bundle, root=work, archive=archive)
        if reasons:
            raise SystemExit("the bundle we just built is not acceptable:\n  - "
                             + "\n  - ".join(reasons))

        shutil.copy2(archive, os.path.join(args.out, os.path.basename(archive)))
        shutil.copy2(os.path.join(work, "receipt.json"), os.path.join(args.out, "receipt.json"))
        digests = os.path.join(args.out, "CORPUS-DIGESTS.txt")
        write_digests(digests, [os.path.join(args.out, os.path.basename(archive)),
                                bundle_path, os.path.join(args.out, "receipt.json")])

        print(json.dumps({
            "bundle": bundle_path,
            "archive_sha256": bundle["archive"]["sha256"],
            "positive": bundle["controls"]["positive"]["result"],
            "hostile": bundle["controls"]["hostile"]["result"],
            "negative": bundle["controls"]["negative"]["result"],
            "digests": digests,
        }, indent=2))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
