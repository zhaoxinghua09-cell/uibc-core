#!/usr/bin/env python3
"""Is the base image in the Dockerfile the digest the pin names?

Three claims are checked, and each of them is the kind a reader cannot make
without reading three files at once:

1. docker/base-image.pin holds exactly one reference, of the form
   `repo:tag@sha256:<digest>`, and the digest is a full 64-hex manifest-list
   digest.
2. docker/Dockerfile's `ARG PYTHON_IMAGE=...` quotes that same reference. A
   Dockerfile that says `python:3.13-slim-bookworm` (a tag) builds a different
   machine tomorrow, and nothing else in the repository would notice.
3. with `--registry`, the digest can still be resolved: the repository asks the
   registry for the manifest by digest (which must succeed even if the tag has
   since moved), and separately reports where the *tag* now points. A tag that
   moved is not a failure - the pin is doing its job - but it is printed, because
   the next person deciding whether to bump should see how far it has drifted.

A fourth claim covers the second interpreter. docker/node.pin, when it exists,
names a Node tarball by URL *and* by the sha256 of its bytes, and the Dockerfile
must quote both as ARGs; the URL must point at the version the pin names. A tree
without the file is not failed for lacking one - but a tree with it cannot pass
on a version string alone. That is the same rule as the base image, applied to a
file rather than to a registry reference, because that is how Node is distributed.

Exit codes: 0 = the three agree, 1 = they do not, 2 = the registry could not be
reached (the local claim still holds: the message says which half was checked).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARG_NAME = "PYTHON_IMAGE"
REF_RE = re.compile(r"^(?P<repo>[A-Za-z0-9._/-]+):(?P<tag>[A-Za-z0-9._-]+)@"
                    r"(?P<algo>sha256):(?P<digest>[0-9a-f]{64})$")
FROM_RE = re.compile(r"^\s*ARG\s+" + ARG_NAME + r"=(?P<ref>[^\s#]+)\s*$", re.M)
PIN_REL = os.path.join("docker", "base-image.pin")
DOCKERFILE_REL = os.path.join("docker", "Dockerfile")

# The second interpreter, pinned the same way: not by a version string but by the
# digest of the tarball that gets unpacked. A version string would let the file
# behind it change; the digest would not.
NODE_PIN_REL = os.path.join("docker", "node.pin")
NODE_URL_RE = re.compile(r"^https://nodejs\.org/dist/v(?P<ver>[0-9]+\.[0-9]+\.[0-9]+)/"
                         r"node-v(?P=ver)-linux-(?P<arch>x64|arm64)\.tar\.xz$")
NODE_SHA_RE = re.compile(r"^sha256 (?P<sha>[0-9a-f]{64})$")
ARG_RE = re.compile(r"^\s*ARG\s+(?P<name>[A-Z_][A-Z_0-9]*)=(?P<val>[^\s#]+)\s*$", re.M)
NODE_ARGS = ("NODE_TARBALL", "NODE_SHA256")


def read_pin(root=HERE):
    path = os.path.join(root, PIN_REL)
    if not os.path.exists(path):
        return None, f"{PIN_REL.replace(os.sep, '/')} is missing"
    lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]
    refs = [l for l in lines if not l.startswith("#")]
    if len(refs) != 1:
        return None, f"{PIN_REL.replace(os.sep, '/')} must hold exactly one reference, found {len(refs)}"
    m = REF_RE.match(refs[0])
    if not m:
        return None, (f"{PIN_REL.replace(os.sep, '/')} line {refs[0]!r} is not "
                      "`repo:tag@sha256:<64 hex>`; a tag alone does not pin anything")
    return refs[0], None


def read_dockerfile_ref(root=HERE):
    path = os.path.join(root, DOCKERFILE_REL)
    if not os.path.exists(path):
        return None, f"{DOCKERFILE_REL.replace(os.sep, '/')} is missing"
    text = open(path, encoding="utf-8").read()
    m = FROM_RE.search(text)
    if not m:
        return None, f"{DOCKERFILE_REL.replace(os.sep, '/')} has no `ARG {ARG_NAME}=<ref>` line"
    return m.group("ref"), None


def _token(repo):
    scope = f"repository:{repo}:pull"
    url = "https://auth.docker.io/token?service=registry.docker.io&scope=" + scope
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)["token"]


def resolve(repo, reference, accept="application/vnd.oci.image.index.v1+json,"
                                      "application/vnd.docker.distribution.manifest.list.v2+json,"
                                      "application/vnd.docker.distribution.manifest.v2+json"):
    """-> (digest the registry answers with, media type) or raises."""
    token = _token(repo)
    req = urllib.request.Request(
        f"https://registry-1.docker.io/v2/{repo}/manifests/{reference}",
        headers={"Authorization": f"Bearer {token}", "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.headers.get("docker-content-digest"), r.headers.get("content-type")


def resolve_with_retry(repo, reference, attempts=3):
    """-> (digest, media, None) or (None, None, reason).

    Anonymous pulls from Docker Hub are rate limited and, on some egress paths,
    answer 401 to a token that was just minted. That is a transport fact, not a
    fact about the pin, so it is retried with a fresh token rather than reported
    as a mismatch - and if the last attempt still fails, the reason is returned
    instead of an exception, because the caller decides what it means.
    """
    reason = None
    for i in range(attempts):
        try:
            d, media = resolve(repo, reference)
            return d, media, None
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = (e.read() or b"")[:200].decode("utf-8", "replace")
            except Exception:                                       # noqa: BLE001
                pass
            reason = f"HTTP {e.code}{': ' + body if body else ''}"
            if e.code not in (401, 408, 429, 500, 502, 503):
                return None, None, reason
        except Exception as e:                                      # noqa: BLE001
            reason = f"{type(e).__name__}: {e}"
        time.sleep(1 + i)
    return None, None, reason


def resolve_with_docker_cli(reference):
    """-> (True, note) when `docker manifest inspect` accepts the reference.

    The same question as the HTTP path, asked through the client every runner has,
    for the case where this host's egress is the thing that is broken. It only
    answers "resolvable", not "which digest", so it never stands in for the pin.
    """
    exe = shutil.which("docker")
    if not exe:
        return False, "no docker CLI here either"
    try:
        p = subprocess.run([exe, "manifest", "inspect", reference],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:                                          # noqa: BLE001
        return False, f"docker CLI could not run ({type(e).__name__}: {e})"
    if p.returncode == 0:
        return True, "verified through the docker CLI (manifest inspect)"
    tail = (p.stderr or p.stdout or "").strip().splitlines()
    return False, tail[-1] if tail else f"docker manifest inspect exited {p.returncode}"


def read_node_pin(root=HERE):
    """-> (url, sha256, None) or (None, None, reason); (None, None, None) if absent.

    Absent is allowed because a tree that never claimed a second interpreter
    should not be failed for not having one - but once the file exists, a
    version string without a digest, a short digest, two digests, or a URL whose
    version disagrees with the version line are all failures, not notes.
    """
    path = os.path.join(root, NODE_PIN_REL)
    if not os.path.exists(path):
        return None, None, None
    lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]
    refs = [l for l in lines if not l.startswith("#")]
    if len(refs) != 3:
        if len(refs) == 2 and NODE_URL_RE.match(refs[1]):
            return None, None, (f"{NODE_PIN_REL.replace(os.sep, '/')} has no `sha256 <64 hex>` line; "
                                "a version without a digest pins nothing")
        return None, None, (f"{NODE_PIN_REL.replace(os.sep, '/')} must hold a version, a URL and "
                            f"one `sha256 <64 hex>` line, found {len(refs)} reference lines")
    ver, url, sha_line = refs
    m = NODE_URL_RE.match(url)
    if not m:
        return None, None, (f"{NODE_PIN_REL.replace(os.sep, '/')} URL {url!r} is not "
                            "`https://nodejs.org/dist/v<ver>/node-v<ver>-linux-{x64,arm64}.tar.xz`")
    ver_norm = ver[1:] if ver.startswith("v") else ver
    if m.group("ver") != ver_norm:
        return None, None, (f"{NODE_PIN_REL.replace(os.sep, '/')} says version {ver!r} but the "
                            f"URL points at v{m.group('ver')}")
    s = NODE_SHA_RE.match(sha_line)
    if not s:
        return None, None, (f"{NODE_PIN_REL.replace(os.sep, '/')} line {sha_line!r} is not "
                            "`sha256 <64 hex>`; a version without a digest pins nothing")
    return url, s.group("sha"), None


def read_dockerfile_args(root=HERE, names=NODE_ARGS):
    """-> ({name: value}, None) or (None, reason)."""
    path = os.path.join(root, DOCKERFILE_REL)
    if not os.path.exists(path):
        return None, f"{DOCKERFILE_REL.replace(os.sep, '/')} is missing"
    found = {m.group("name"): m.group("val")
             for m in ARG_RE.finditer(open(path, encoding="utf-8").read())}
    missing = [n for n in names if n not in found]
    if missing:
        return None, f"{DOCKERFILE_REL.replace(os.sep, '/')} has no `ARG {missing[0]}=...` line"
    return {n: found[n] for n in names}, None


def node_url_reachable(url):
    """-> (ok_to_continue, note). A 404 is a failure; anything else is a note.

    Not a full download: the build re-checks the bytes anyway, and pulling 34 MB in
    a checker that runs on every PR would be a cost with no extra claim.
    """
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"HTTP {r.status}, {r.headers.get('Content-Length', '?')} bytes"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, f"HTTP 404: {url} no longer exists"
        return True, f"HTTP {e.code} on HEAD (the server answered; the pin is unaffected)"
    except Exception as e:                                          # noqa: BLE001
        return True, f"could not reach the URL ({type(e).__name__}); the pin is unaffected"


def main(argv=None, root=HERE):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", action="store_true",
                    help="also ask registry-1.docker.io whether the digest resolves")
    ap.add_argument("--root", default=None,
                    help="repository to inspect (default: the one this file lives in)")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root) if args.root else root

    ref, err = read_pin(root)
    if err:
        print("FAIL", err)
        return 1
    m = REF_RE.match(ref)
    repo, tag, digest = m.group("repo"), m.group("tag"), m.group("digest")
    print(f"PIN  {repo}:{tag}")
    print(f"     digest {digest}")

    df_ref, err = read_dockerfile_ref(root)
    if err:
        print("FAIL", err)
        return 1
    if df_ref != ref:
        print(f"FAIL Dockerfile ARG {ARG_NAME}={df_ref}")
        print(f"     disagrees with the pin {ref}")
        print("\nHOW TO FIX: one reference, one place. Either copy the pin into the ARG, or")
        print("change both in the same commit and say in the message why the base moved.")
        return 1
    print(f"OK   {DOCKERFILE_REL.replace(os.sep, '/')} quotes the pinned reference")

    # Second interpreter, same rule: the digest, not the version string.
    node_url, node_sha, node_err = read_node_pin(root)
    if node_err:
        print("FAIL", node_err)
        return 1
    if node_url is None:
        print("NOTE no docker/node.pin: this tree does not claim a second interpreter")
    else:
        df_args, err = read_dockerfile_args(root)
        if err:
            print("FAIL", err)
            print("     docker/node.pin exists, so the Dockerfile must quote it in "
                  "ARG NODE_TARBALL / ARG NODE_SHA256")
            return 1
        if df_args["NODE_TARBALL"] != node_url or df_args["NODE_SHA256"] != node_sha:
            print(f"FAIL Dockerfile ARG NODE_TARBALL={df_args['NODE_TARBALL']}")
            print(f"     ARG NODE_SHA256={df_args['NODE_SHA256']}")
            print(f"     disagrees with docker/node.pin ({node_url}, sha256 {node_sha})")
            print("\nHOW TO FIX: move the pin, not the tag. Bumping Node is an edit to "
                  "docker/node.pin\nand the two ARGs in the same commit, and the container job "
                  "has to run again.")
            return 1
        print(f"OK   Dockerfile quotes the pinned Node tarball ({node_url.rsplit('/', 1)[-1]}, "
              f"sha256 {node_sha[:12]}…)")

    if not args.registry:
        print("NOTE registry not checked (--registry asks whether this digest still resolves)")
        print("VERDICT: PIN CONSISTENT (local claim: pin == Dockerfile)")
        return 0

    by_digest, media, why = resolve_with_retry(repo, "sha256:" + digest)
    if by_digest is None:
        if why and "HTTP 404" in why:
            print(f"FAIL sha256:{digest} is not in {repo}: a pin nobody can pull is not a pin")
            print(f"     registry said: {why}")
            return 1
        print(f"NOTE HTTP path could not answer ({why}); asking the docker CLI")
        ok, note = resolve_with_docker_cli(f"{repo}:{tag}@sha256:{digest}")
        if ok:
            print(f"OK   {note}")
            print(f"OK   sha256:{digest} resolves (HTTP path was the thing that was broken)")
            print("VERDICT: PIN CONSISTENT (pin == Dockerfile; digest resolvable with the docker CLI)")
            return 0
        print(f"FAIL digest unresolvable by both paths ({note})")
        print("VERDICT: LOCAL CONSISTENT, REGISTRY UNCHECKED (pin == Dockerfile, origin unresolved)")
        return 2
    if by_digest != "sha256:" + digest:
        print(f"FAIL registry answered digest {by_digest} for a request by digest sha256:{digest}")
        return 1
    print(f"OK   registry resolves sha256:{digest} ({media})")

    by_tag, _, tag_why = resolve_with_retry(repo, tag, attempts=2)
    if by_tag is None:
        print(f"NOTE could not resolve the tag {tag} ({tag_why}); the pin is unaffected")
    elif by_tag == "sha256:" + digest:
        print(f"OK   the tag {tag} still points here")
    else:
        print(f"NOTE the tag {tag} now points at {by_tag}")
        print("     The build uses the pinned digest, not the tag, so nothing moved. Bumping the")
        print("     pin is a deliberate edit: change docker/base-image.pin and the Dockerfile ARG")
        print("     together, and re-run the container job to see the four steps again.")

    if node_url:
        ok, note = node_url_reachable(node_url)
        if not ok:
            print(f"FAIL {note}")
            print("     a pinned tarball nobody can download is not a pin: point docker/node.pin")
            print("     at a version that still exists, or mirror it and pin the mirror's digest.")
            return 1
        print(f"NOTE Node tarball: {note}")

    print("VERDICT: PIN CONSISTENT (pin == Dockerfile == registry)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
