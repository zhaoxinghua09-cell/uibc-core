#!/usr/bin/env python3
"""Record what a release holds, as a pin, from the release itself.

A pin has to be written by the process that published the bytes: a person
remembering a digest is not a record. This step runs right after the upload, reads
the page it has just published, and writes `uibc-release-pin.json` -- which is then
attached to the same release.

Why the pin cannot contain its own digest is the only thing worth explaining here:
the file lists every asset except itself, and it says so in the file, so a reader
knows the exclusion is stated rather than forgotten. A page that carries its own
record can only detect *accidental* rewrites; the strong form is the repository pin
(`anchors/pins/uibc-release-<tag>.json`), which lives somewhere the page cannot
rewrite. `check_release_pins.py` reports which kind of pin a tag has for exactly
that reason, and it is not a compliment.

    python tools/make_release_pin.py --tag v0.4.2 --out release/uibc-release-pin.json
"""
import argparse
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

REPO = "zhaoxinghua09-cell/uibc-core"
PIN_NAME = "uibc-release-pin.json"
KIND = "uibc-release-pin-v0"


def _gh_releases_url(tag):
    return "repos/%s/releases/tags/%s" % (REPO, tag)


def _asset_rows(tag):
    """[(name, size, digest)] straight from the API.

    Two queries, in this order, because a draft release is invisible to
    `/releases/tags/<tag>` — measured 2026-11-25 on run 45563463379 (v0.5.5, the
    release opened as a draft so an immutable page could still accept uploads):
    the tag endpoint answered HTTP 404 while `gh release view` saw the same
    release and the same nine assets. The pin step therefore failed with
    `cannot read v0.5.5: gh: Not Found` *after* the assets were already on the
    page, and the page was published without its self pin. Listing every release
    and matching on `tag_name` sees drafts; the tag endpoint stays first because
    it is exact.
    """
    gh = shutil.which("gh")
    if not gh:
        raise RuntimeError("gh is not on PATH; the pin must be read from the page")
    jq = r'.assets[] | "\(.name)\t\(.size)\t\(.digest // "-")"'
    queries = [
        (_gh_releases_url(tag), jq),
        ("repos/%s/releases?per_page=100" % REPO,
         r'.[] | select(.tag_name == "%s") | .assets[] | ' % tag + jq),
    ]
    last_err = ""
    for url, query in queries:
        proc = subprocess.run([gh, "api", url, "--jq", query],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            last_err = proc.stderr.strip()[:200]
            continue
        rows = []
        for line in (proc.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            rows.append((parts[0], int(parts[1]), "" if parts[2] == "-" else parts[2]))
        if rows:
            return rows
        last_err = "no assets found for %s" % tag
    raise RuntimeError("cannot read %s: %s" % (tag, last_err))


def _download_and_hash(tag, name, tmpdir):
    """Fallback for an asset whose digest the page does not report."""
    gh = shutil.which("gh")
    proc = subprocess.run([gh, "release", "download", tag, "-R", REPO,
                           "-p", name, "-D", tmpdir, "--clobber"],
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError("cannot download %s from %s: %s"
                           % (name, tag, proc.stderr.strip()[:200]))
    path = os.path.join(tmpdir, name)
    digest = hashlib.sha256()
    size = 0
    with io.open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def measure(tag, tmpdir):
    rows = _asset_rows(tag)
    assets = []
    for name, size, digest in rows:
        if name == PIN_NAME:
            continue
        if digest.startswith("sha256:"):
            assets.append({"name": name, "bytes": size, "sha256": digest.split(":", 1)[1]})
            continue
        # The page does not report the digest, so it has to be computed from the
        # bytes it serves. Slower, and the only honest option.
        got_size, got = _download_and_hash(tag, name, tmpdir)
        assets.append({"name": name, "bytes": got_size, "sha256": got})
        if got_size != size:
            raise RuntimeError("%s: API says %d bytes, the download is %d"
                               % (name, size, got_size))
    assets.sort(key=lambda a: a["name"])
    if not assets:
        raise RuntimeError("%s has no assets to pin" % tag)
    return assets


def build(tag, assets, late=False):
    blob = {
        "kind": KIND,
        "tag": tag,
        "recorded_at": datetime.datetime.now(datetime.timezone.utc)
                               .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "recorded_by": "the release workflow, reading the page it had just published",
        "excluded": [] if late else [PIN_NAME],
        "why_excluded": ("nothing is excluded: a human recorded this page, no pin asset "
                         "was present" if late else
                         "a file cannot carry its own digest; every other asset is listed"),
        "stronger_form": "anchors/pins/uibc-release-%s.json in the repository, which "
                         "the page cannot rewrite" % tag,
        "assets": assets,
    }
    if late:
        # Recording a page months after it was published is not the same act as
        # recording it at publication, and a reader has to be able to tell.
        blob["recorded_late"] = True
        blob["meaning"] = ("the page as it stands on recorded_at; this does not show "
                           "what it held when it was published, only what it holds now")
        blob["recorded_by"] = "a human, after the fact, not the publishing process"
    return blob


def write(path, blob):
    """Write, unless the file already exists with different content."""
    text = json.dumps(blob, indent=2, sort_keys=True) + "\n"
    if os.path.isfile(path):
        old = io.open(path, encoding="utf-8").read()
        if old == text:
            print("pin unchanged at %s" % path)
            return 0
        old_assets = {}
        try:
            old_assets = {a["name"]: a["sha256"] for a in json.loads(old)["assets"]}
        except Exception:
            pass
        new_assets = {a["name"]: a["sha256"] for a in blob["assets"]}
        diffs = [n for n in set(old_assets) | set(new_assets)
                 if old_assets.get(n) != new_assets.get(n)]
        print("REFUSED: %s already records a different page" % path)
        print("  recorded: %s" % ", ".join(sorted(diffs)[:6]) or "all")
        print("  this run: %s" % ", ".join(sorted(diffs)[:6]) or "all")
        print("  a pin is written once; re-pinning is a decision, not a retry")
        return 3
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    print("pin written to %s: %d assets" % (path, len(blob["assets"])))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tmpdir", default=None)
    ap.add_argument("--late", action="store_true",
                    help="declare that this page was published before it was recorded")
    args = ap.parse_args(argv)
    tmpdir = args.tmpdir or os.environ.get("TMPDIR") or "/tmp"
    try:
        assets = measure(args.tag, tmpdir)
    except Exception as exc:
        print("cannot pin %s: %s" % (args.tag, exc))
        return 3
    return write(args.out, build(args.tag, assets, late=args.late))


if __name__ == "__main__":
    sys.exit(main())
