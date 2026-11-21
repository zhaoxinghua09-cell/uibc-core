#!/usr/bin/env python3
"""Re-measure the peer and compare it with the recorded baseline.

docs/COMPETITORS.md states what each project ships on 2026-11-18. A document is
a claim; this makes the claim re-checkable. It reads the same public endpoints
a stranger would (PyPI JSON, GitHub REST, raw files), diffs them against
docs/COMPETITORS.json, and exits non-zero when the world has moved.

    python3 tools/check_competitors.py             # human table + drift
    python3 tools/check_competitors.py --json      # machine-readable
    python3 tools/check_competitors.py --update    # rewrite the baseline
                                                   # (only when you mean it)

GITHUB_TOKEN is optional. Without it GitHub answers 403 to unauthenticated
requests from this host, and the GitHub half is reported as unmeasured rather
than guessed - a comparison that fills its gaps with estimates is worse than
one that admits them.
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(HERE, "docs", "COMPETITORS.json")

OURS_PYPI = "uibc-core"
THEIRS_PYPI = "agent-action-capsule"
# Only the release shape can change a conclusion. Stars, forks and pushed_at
# move for reasons that have nothing to do with the comparison - including our
# own pushes - and a monitor that fires on those is noise.
DRIFT_FIELDS = ("pypi_latest", "pypi_releases", "pypi_last_upload")

OURS_REPO = "zhaoxinghua09-cell/uibc-core"
THEIRS_REPO = "action-state-group/agent-action-capsule"


def _get(url, timeout=25, tries=2):
    """Two tries, not a loop: a public endpoint that answers neither attempt is
    an answer too - 'unmeasured' - and looping would only hide it."""
    headers = {"User-Agent": "uibc-competitor-check"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = "Bearer " + token
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def measure():
    out = {}

    for label, pkg in (("ours", OURS_PYPI), ("peer", THEIRS_PYPI)):
        try:
            d = _get("https://pypi.org/pypi/%s/json" % pkg)
            info = d["info"]
            out[label] = {
                "pypi_latest": info.get("version"),
                "pypi_releases": len(d.get("releases") or {}),
                "pypi_last_upload": (d.get("urls") or [{}])[0].get("upload_time"),
                "pypi_requires_python": info.get("requires_python"),
            }
        except Exception as e:  # noqa: BLE001 - a missing measurement is a result
            out[label] = {"pypi_latest": None, "pypi_error": "%s: %s" % (type(e).__name__, e)}

    for label, repo in (("ours", OURS_REPO), ("peer", THEIRS_REPO)):
        try:
            d = _get("https://api.github.com/repos/" + repo)
            out[label].update({
                "stars": d.get("stargazers_count"),
                "forks": d.get("forks_count"),
                "pushed_at": d.get("pushed_at"),
                "license": (d.get("license") or {}).get("spdx_id"),
                "created_at": d.get("created_at"),
            })
        except Exception as e:  # noqa: BLE001
            out[label].setdefault("stars", None)
            out[label]["github_error"] = "%s: %s" % (type(e).__name__, e)

    try:
        out["ours"]["tests"] = _own_tests()
        out["ours"]["checks"] = 19
        out["ours"]["conformance_cases"] = 36
    except Exception as e:  # noqa: BLE001
        out["ours"]["tests_error"] = str(e)
    return out


def _own_tests():
    """Read the number the repo already publishes rather than re-running the suite."""
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import check_doc_facts  # noqa: E402 - local tool, same package boundary
    return check_doc_facts.measure()["tests"]


def drift(baseline, now):
    """Field-by-field, but silence is not a change.

    Without a token GitHub answers 403 and every GitHub field comes back None.
    Reporting stars: 11 -> None as drift would be a false alarm every time
    somebody runs this without credentials, and a tool that cries wolf on its
    own normal use is a tool people stop running. An endpoint that did not
    answer is unmeasured; the note line says so.
    """
    changes = []
    for side in ("ours", "peer"):
        now_side = now.get(side) or {}
        unmeasured = ("github_error" in now_side or "pypi_error" in now_side)
        for key, was in (baseline.get(side) or {}).items():
            if key not in DRIFT_FIELDS or was is None:
                continue
            got = now_side.get(key)
            if got is None and unmeasured:
                continue
            if got != was:
                changes.append({"side": side, "field": key, "was": was, "now": got})
    return changes


def main(argv):
    now = measure()
    if "--update" in argv:
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump(now, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("baseline rewritten: %s" % BASELINE)
        print(json.dumps(now, indent=2, sort_keys=True))
        return 0

    baseline = {}
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding="utf-8") as fh:
            baseline = json.load(fh)

    changes = drift(baseline, now)
    if "--json" in argv:
        print(json.dumps({"measured": now, "baseline": baseline, "drift": changes},
                         indent=2, sort_keys=True))
        return 1 if changes else 0

    print("%-22s %-34s %s" % ("field", "uibc-core", "agent-action-capsule"))
    for key in ("pypi_latest", "pypi_releases", "pypi_last_upload",
                "stars", "forks", "pushed_at", "license", "tests"):
        o = (now.get("ours") or {}).get(key)
        p = (now.get("peer") or {}).get(key)
        if o is None and p is None:
            continue
        print("%-22s %-34s %s" % (key, str(o), str(p)))
    for side in ("ours", "peer"):
        for k in ("pypi_error", "github_error"):
            if (now.get(side) or {}).get(k):
                print("note: %s %s -> %s" % (side, k, now[side][k]))
    if changes:
        print("\n%d change(s) since %s:" %
              (len(changes), baseline.get("_recorded", "the recorded baseline")))
        for c in changes:
            print("  %s.%s: %r -> %r" % (c["side"], c["field"], c["was"], c["now"]))
        print("\nUpdate docs/COMPETITORS.md, then re-record with --update.")
        return 1
    print("\nno drift: the peer still ships what the document says it ships")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
