#!/usr/bin/env python3
"""Build a lab bundle: what was run, on which bytes, with which controls, and
with what the runner already knew.

The point is not paperwork. A number from a run is only evidence if a reader can
recompute the bytes, see that a naive accept-everything checker fails, and know
whether the runner had already read the expected answers. Prose can claim all
three; a bundle has to carry them.

Usage:
    python tools/lab_manifest.py --dir run/ --archive uibc-conformance-0.4.1.zip \
        --question "Does 0.4.1 reject a flipped evidence byte?" \
        --claim "the corpus decides this" --runner "Your Name <you@example.org>" \
        --blind "did not read checks or expected reasons" --out lab_bundle.json

Files under --dir are digested, in sorted order, with sizes and a media type guessed
from the extension. Nothing is uploaded; the bundle is a local JSON file and the
bytes stay where they are.
"""
import argparse
import datetime
import hashlib
import json
import mimetypes
import os
import sys

KIND = "uibc-lab-bundle-v0"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_tree(root, archive=None):
    """One entry per regular file, sorted, with bytes and digest.

    The bundle itself and the archive are excluded only when they sit inside
    `root`: the archive is digested separately, and a bundle cannot digest
    itself. Everything else in the directory is evidence and is carried.
    """
    skip = {"lab_bundle.json"}
    if archive:
        skip.add(os.path.basename(archive))
    entries = []
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            if name in skip:
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root).replace("\\", "/")
            entries.append({
                "path": rel,
                "bytes": os.path.getsize(path),
                "sha256": _sha256(path),
                "media_type": mimetypes.guess_type(name)[0] or "application/octet-stream",
            })
    return entries


def build(args):
    if not os.path.isdir(args.dir):
        raise SystemExit("no such directory: %s" % args.dir)
    if not os.path.isfile(args.archive):
        raise SystemExit("no such archive: %s" % args.archive)
    for field in ("question", "claim", "runner", "blind"):
        if not str(getattr(args, field) or "").strip():
            raise SystemExit("--%s is required: a bundle with a blank field is not evidence" % field)

    bundle = {
        "kind": KIND,
        "question": args.question,
        "claim": args.claim,
        "built_utc": _now(),
        "archive": {
            "path": os.path.basename(args.archive),
            "bytes": os.path.getsize(args.archive),
            "sha256": _sha256(args.archive),
        },
        "roles": {
            "runner": args.runner,
            "operator": args.operator or "",
            "custodian": args.custodian or "",
        },
        "exposure": {
            "blind": args.blind,
            "read_before_run": args.read_before_run or "",
            "declared_by": args.runner,
            "declared_utc": _now(),
        },
        "run": {
            "command": args.command or "",
            "exit_code": args.exit_code,
            "python": args.python or "",
            "platform": args.platform or "",
            "stdout_tail": args.stdout_tail or "",
        },
        "controls": {
            "positive": {"what": args.positive_what or "", "result": args.positive_result or ""},
            "hostile": {"what": args.hostile_what or "", "result": args.hostile_result or "",
                        "cases_total": args.cases_total},
            "negative": {"what": args.negative_what or "", "result": args.negative_result or ""},
        },
        "limits": [s for s in (args.limits or "").split(";") if s.strip()],
        "bytes": digest_tree(args.dir, archive=args.archive),
    }
    out = args.out or os.path.join(args.dir, "lab_bundle.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(bundle, f, indent=2, sort_keys=False)
        f.write("\n")
    print("wrote %s — %d file(s) digested, archive %s…"
          % (out, len(bundle["bytes"]), bundle["archive"]["sha256"][:12]))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True, help="directory holding the run's bytes")
    ap.add_argument("--archive", required=True, help="the archive that was unzipped")
    ap.add_argument("--question", required=True)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--runner", required=True, help='Name <email>; the person who ran it')
    ap.add_argument("--blind", required=True, help="blind / directed, in the runner's words")
    ap.add_argument("--read-before-run", default="", help="what you had read when you started")
    ap.add_argument("--operator", default="")
    ap.add_argument("--custodian", default="")
    ap.add_argument("--command", default="")
    ap.add_argument("--exit-code", type=int, default=None)
    ap.add_argument("--python", default="")
    ap.add_argument("--platform", default="")
    ap.add_argument("--stdout-tail", default="")
    ap.add_argument("--positive-what", default="")
    ap.add_argument("--positive-result", default="")
    ap.add_argument("--hostile-what", default="")
    ap.add_argument("--hostile-result", default="")
    ap.add_argument("--cases-total", type=int, default=None)
    ap.add_argument("--negative-what", default="")
    ap.add_argument("--negative-result", default="")
    ap.add_argument("--limits", default="", help="semicolon-separated list of what this does not cover")
    ap.add_argument("--out", default=None)
    return build(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
