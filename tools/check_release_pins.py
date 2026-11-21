#!/usr/bin/env python3
"""Does every release carry a record of what it holds?

`check_release_anchors.py` compares one tag against the pin recorded for it. This
one asks the prior question for every tag at once: is there a pin at all? A release
published without one cannot be told apart from a release that was quietly rewritten
afterwards, and no check would say so -- which is how v0.4.1 was rewritten three times
on 2026-11-20 with everything green.

Two kinds of pin, deliberately ranked:

  repo pin   anchors/pins/uibc-release-<tag>.json -- somewhere the page cannot rewrite
  self pin   uibc-release-pin.json on the release itself -- written by the publisher,
             but it travels with the page, so it only catches accidental rewrites

Unpinned is a failure, not a note: the point of the job is to be loud about a release
nobody can check later.

    python tools/check_release_pins.py            # 0 ok / 1 unpinned or drift / 3 no gh
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_release_anchors as cra  # noqa: E402

REPO = "zhaoxinghua09-cell/uibc-core"
PIN_NAME = "uibc-release-pin.json"


def tags():
    gh = shutil.which("gh")
    if not gh:
        return None
    proc = subprocess.run([gh, "api", "repos/%s/releases" % REPO,
                           "--jq", ".[].tag_name"], capture_output=True, text=True,
                          timeout=60)
    if proc.returncode != 0:
        return None
    return [t for t in (proc.stdout or "").splitlines() if t.strip()]


def repo_pin_path(tag):
    return os.path.join(cra.ROOT, "anchors", "pins", "uibc-release-%s.json" % tag)


def self_pin(tag, tmpdir):
    """The pin a release carries about itself, or None."""
    gh = shutil.which("gh")
    if not gh:
        return None
    proc = subprocess.run([gh, "api", "repos/%s/releases/tags/%s" % (REPO, tag),
                           "--jq", '.assets[] | select(.name=="%s") | .id' % PIN_NAME],
                          capture_output=True, text=True, timeout=60)
    asset_id = (proc.stdout or "").strip()
    if proc.returncode != 0 or not asset_id:
        return None
    os.makedirs(tmpdir, exist_ok=True)
    out = os.path.join(tmpdir, "%s-self-pin.json" % tag.replace("/", "_"))
    with open(out, "wb") as fh:
        got = subprocess.run([gh, "api", "repos/%s/releases/assets/%s" % (REPO, asset_id),
                              "-H", "Accept: application/octet-stream"],
                             stdout=fh, timeout=60)
    if got.returncode != 0:
        return None
    try:
        return json.load(io.open(out, encoding="utf-8"))
    except Exception:
        return None


def compare(blob, live, skip, resolve=None):
    """[(name, recorded, served)] for assets that differ, plus missing/unpinned.

    Assets whose digest the page does not report are not assumed to match: they go
    through `resolve` (hash the served bytes) or are returned as unsure, so a caller
    can say "not measured" instead of "fine".
    """
    recorded = {a["name"]: a["sha256"] for a in blob.get("assets", [])}
    bad, unsure = [], []
    for name, digest in sorted(recorded.items()):
        if name in skip:
            continue
        if name not in live:
            bad.append((name, digest, None))
            continue
        served = live[name]
        if not served:
            if resolve is None:
                unsure.append((name, "the page reports no digest"))
                continue
            try:
                served = resolve(name)
            except Exception as exc:
                unsure.append((name, str(exc)))
                continue
        if served != digest:
            bad.append((name, digest, served))
    for name in sorted(live):
        if name in skip or name in recorded:
            continue
        if not live[name]:
            unsure.append((name, "not in the pin, and the page reports no digest"))
            continue
        bad.append((name, None, live[name]))
    return bad, unsure


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tmpdir", default=None)
    args = ap.parse_args(argv)
    tmpdir = args.tmpdir or os.environ.get("TMPDIR") or "/tmp"

    names = tags()
    if names is None:
        print("cannot enumerate releases: gh unavailable or unauthenticated")
        return 3
    if not names:
        print("no releases found")
        return 3

    report, code = {}, 0
    for tag in sorted(names):
        live = cra._live_manifest(tag)
        if live is None:
            print("%-12s cannot read the page" % tag)
            report[tag] = {"state": "unreadable"}
            code = max(code, 3)
            continue
        if not live:
            # Nothing was ever published under this tag. There is nothing to rewrite,
            # and saying so is different from saying it is unpinned.
            print("%-12s empty: no assets published under this tag" % tag)
            report[tag] = {"state": "empty"}
            continue

        path = repo_pin_path(tag)
        if os.path.isfile(path):
            blob = json.load(io.open(path, encoding="utf-8"))
            kind = "repo_pin"
            skip = set(blob.get("excluded", []))
        else:
            blob = self_pin(tag, tmpdir)
            if blob is None:
                print("%-12s unpinned: no repository pin and no pin on the release" % tag)
                report[tag] = {"state": "unpinned"}
                code = max(code, 1)
                continue
            kind = "self_pin"
            skip = set(blob.get("excluded", [])) | {PIN_NAME}
        bad, unsure = compare(blob, live, skip,
                              resolve=lambda name: cra._download_sha256(tag, name))
        if unsure:
            for name, why in unsure[:6]:
                print("%-12s UNMEASURED %s: %s" % (tag, name, why))
            code = max(code, 3)
            report[tag] = {"state": "unmeasured", "assets": [u[0] for u in unsure]}
        if bad:
            for name, recorded, served in bad[:6]:
                why = ("missing from the page" if served is None
                       else "not recorded in the pin" if recorded is None
                       else "served digest differs from the recorded one")
                print("%-12s DRIFT %s: %s" % (tag, name, why))
            code = max(code, 1)
            report[tag] = {"state": "drift", "assets": [b[0] for b in bad]}
        else:
            note = "" if kind == "repo_pin" else " (self pin: catches accidents, not forgeries)"
            print("%-12s pinned by %s, %d assets match%s"
                  % (tag, "the repository" if kind == "repo_pin" else "itself",
                     len([a for a in blob.get("assets", []) if a["name"] not in skip]),
                     note))
            report[tag] = {"state": "ok", "kind": kind,
                           "assets": len([a for a in blob.get("assets", [])
                                          if a["name"] not in skip])}

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    print("VERDICT %s" % {0: "every release is pinned and unchanged",
                          1: "a release is unpinned or has drifted",
                          3: "could not measure every release"}[code])
    return code


if __name__ == "__main__":
    sys.exit(main())
