#!/usr/bin/env python3
"""Decide whether a lab bundle proves what it says it proves.

A bundle claims four things a reader cannot check by reading the prose: that the
bytes are the bytes, that a naive checker was tried and failed, that a broken
environment was told apart from a corpus failure, and that the runner declared
what they already knew. Each of those is checkable here, and each is refused
loudly when it is asserted rather than carried.

Usage:
    python tools/check_lab_bundle.py lab_bundle.json
    python tools/check_lab_bundle.py lab_bundle.json --dir run/ --archive file.zip

Exit 0 when acceptable, 1 when not. Every reason is printed separately.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

KIND = "uibc-lab-bundle-v0"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_time(value):
    try:
        datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except (TypeError, ValueError):
        return False


def check(bundle, root=None, archive=None):
    """Return the reasons this bundle cannot be used. Empty means acceptable."""
    reasons = []

    if not isinstance(bundle, dict):
        return ["the bundle is not a JSON object"]

    for key in ("kind", "question", "claim", "archive", "roles", "exposure", "run", "controls", "bytes", "limits"):
        if key not in bundle:
            reasons.append("missing key: %s" % key)
    if reasons:
        return reasons

    if bundle["kind"] != KIND:
        reasons.append("kind is %r, not %r" % (bundle["kind"], KIND))

    for name, value in (("question", bundle["question"]), ("claim", bundle["claim"])):
        if not str(value or "").strip():
            reasons.append("%s is blank: a bundle that does not state what it tested cannot be read" % name)

    arch = bundle["archive"]
    if not str(arch.get("sha256") or ""):
        reasons.append("archive.sha256 is blank")
    elif archive:
        if not os.path.isfile(archive):
            reasons.append("the archive named on disk does not exist")
        else:
            real = _sha256(archive)
            if real != arch["sha256"]:
                reasons.append("archive.sha256 is %s, the file is %s" % (arch["sha256"], real))
            if os.path.getsize(archive) != arch.get("bytes"):
                reasons.append("archive.bytes is %s, the file is %s bytes"
                               % (arch.get("bytes"), os.path.getsize(archive)))

    runner = (bundle["roles"] or {}).get("runner") or ""
    if not str(runner).strip():
        reasons.append("roles.runner is blank: an unattributed bundle cannot be a node report")

    exposure = bundle["exposure"] or {}
    if not str(exposure.get("blind") or "").strip():
        reasons.append("exposure.blind is blank: blind and directed are different evidence")
    if not str(exposure.get("declared_by") or "").strip():
        reasons.append("exposure.declared_by is blank: nobody attested to the exposure")
    if not _is_time(exposure.get("declared_utc") or ""):
        reasons.append("exposure.declared_utc is not YYYY-MM-DDTHH:MM:SSZ")

    run = bundle["run"] or {}
    if not str(run.get("command") or "").strip():
        reasons.append("run.command is blank")
    if not isinstance(run.get("exit_code"), int):
        reasons.append("run.exit_code is not an integer: an exit code is the one fact that tells "
                       "an environment failure from a corpus failure")
    if not str(run.get("stdout_tail") or "").strip():
        reasons.append("run.stdout_tail is blank: the table has to be carried, not summarised")

    controls = bundle["controls"] or {}
    pos = controls.get("positive") or {}
    if not str(pos.get("result") or "").strip():
        reasons.append("controls.positive.result is blank: a suite that cannot pass its own case is broken")
    hostile = controls.get("hostile") or {}
    if not str(hostile.get("result") or "").strip():
        reasons.append("controls.hostile.result is blank: without it 'a naive checker fails' is an assertion")
    else:
        total = hostile.get("cases_total")
        passed = _leading_count(hostile["result"])
        if isinstance(total, int) and passed is not None and passed >= total:
            reasons.append("the hostile control passed %d/%d — an accept-everything checker that scores "
                           "full marks means the corpus does not discriminate" % (passed, total))
    neg = controls.get("negative") or {}
    if not str(neg.get("result") or "").strip():
        reasons.append("controls.negative.result is blank: exit 3 with no receipt is a required outcome to show")

    limits = bundle["limits"]
    if not isinstance(limits, list) or not limits:
        reasons.append("limits is empty: a bundle with no stated boundary is read as claiming everything")

    reasons.extend(_bytes_reasons(bundle["bytes"], root))

    return reasons


def _leading_count(text):
    """'6/36' -> 6; anything else -> None."""
    head = str(text).strip().split("/")[0]
    try:
        return int(head)
    except ValueError:
        return None


def _bytes_reasons(entries, root):
    reasons = []
    if not isinstance(entries, list) or not entries:
        return ["bytes is empty: nothing was digested, so nothing can be recomputed"]
    if root is None:
        return reasons
    for entry in entries:
        path = os.path.join(root, entry.get("path", ""))
        if not entry.get("path"):
            reasons.append("a bytes entry has no path")
            continue
        if not os.path.isfile(path):
            reasons.append("bytes entry %s is not on disk" % entry["path"])
            continue
        real_size = os.path.getsize(path)
        if real_size != entry.get("bytes"):
            reasons.append("bytes entry %s is %d bytes, the file is %d"
                           % (entry["path"], entry.get("bytes") or 0, real_size))
        if _sha256(path) != entry.get("sha256"):
            reasons.append("bytes entry %s does not hash to its recorded digest" % entry["path"])
    return reasons


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("--dir", default=None, help="directory holding the bytes, to recompute them")
    ap.add_argument("--archive", default=None, help="the archive file, to recompute its digest")
    ap.add_argument("--allow-anonymous", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.bundle):
        print("no such file: %s" % args.bundle)
        return 1
    with open(args.bundle, encoding="utf-8") as f:
        bundle = json.load(f)

    if args.allow_anonymous and isinstance(bundle.get("roles"), dict):
        bundle["roles"]["runner"] = bundle["roles"].get("runner") or "anonymous"

    reasons = check(bundle, root=args.dir, archive=args.archive)
    if reasons:
        print("NOT ACCEPTABLE — %d reason(s):" % len(reasons))
        for r in reasons:
            print("  - " + r)
        return 1
    print("ACCEPTABLE — %d file(s) digested, archive %s…, controls present, limits stated"
          % (len(bundle["bytes"]), bundle["archive"]["sha256"][:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
