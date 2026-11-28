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

    print("VERDICT: PIN CONSISTENT (pin == Dockerfile == registry)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
