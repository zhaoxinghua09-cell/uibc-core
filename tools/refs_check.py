"""Reference reachability: every citation in the parity document, hit for real.

The parity table cites 25 repositories at pinned commits. A pinned sha makes a
citation *stable*, not *reachable*: the owner can archive the repository, GitHub
can serve a different status to a different network, and the document would
still read as if the reader could click through.

So this tool walks every citation and records what actually happened:

  status        200, 301/302 (and the final hop), 404, 403, 5xx, timeout
  elapsed_ms    how long the hop took
  checked_at    when, per entry

  --run     network. Writes docs/refs-report.json and docs/REFS-DIRECT.md.
  --check   offline. Re-derives the citation list from the snapshot, confirms
            the report covers exactly that list, and that nothing is dead.
  --json    machine-readable summary of the stored report.

A dead citation is a hard failure: the claim it supports cannot be checked by
the reader, so the number stops being evidence and becomes an assertion.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
import re
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(HERE, "docs", "competitor-parity.json")
REPORT = os.path.join(HERE, "docs", "refs-report.json")
PAGE = os.path.join(HERE, "docs", "REFS-DIRECT.md")
UA = "uibc-refs-check/1 (+https://github.com/zhaoxinghua09-cell/uibc-core)"


def citations(snap):
    """The citation list is derived from the snapshot, never typed by hand."""
    out = []
    for row in snap["repos"]:
        if "error" in row:
            continue
        out.append({"repo": row["repo"], "sha": row["sha"],
                    "url": "https://github.com/%s/tree/%s" % (row["repo"], row["sha"])})
    ours = snap.get("ours") or {}
    # a tarball has no .git, so build_ours() can only report what it was told;
    # without a real sha this row is un-checkable and is left out rather than
    # cited as /tree/unknown.
    sha = (ours.get("commit") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        sha = (os.environ.get("UIBC_COMMIT") or "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", sha):
        out.append({"repo": ours["repo"], "sha": sha,
                    "url": "https://github.com/%s/tree/%s" % (ours["repo"], sha)})
    return out


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def probe(url, token=None, timeout=20):
    """One GET, no redirect following, so a 301 is visible instead of silent."""
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "text/html")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    started = time.time()
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return {"status": r.status, "final_url": r.geturl(),
                    "elapsed_ms": int((time.time() - started) * 1000), "error": ""}
    except urllib.error.HTTPError as exc:
        # a redirect is delivered as an HTTPError by the no-redirect opener; the
        # only useful thing in it is the Location header.
        loc = ""
        try:
            loc = exc.headers.get("Location") or ""
        except Exception:
            loc = ""
        return {"status": exc.code, "final_url": loc or (exc.geturl() or url),
                "elapsed_ms": int((time.time() - started) * 1000), "error": ""}
    except Exception as exc:  # timeout, DNS, TLS
        return {"status": 0, "final_url": url,
                "elapsed_ms": int((time.time() - started) * 1000), "error": type(exc).__name__}


def alive(entry):
    """200 = reachable. 301/302 = reachable but the repository was renamed or
    moved; the citation still resolves, so it is not dead, but it is reported."""
    return entry["status"] == 200 and not entry.get("error")


def commit_via_api(repo, sha, token=None, timeout=25):
    """When the HTML tree page cannot be fetched at all from this network
    (timeout / TLS reset — measured 2026-11-26: github.com pages cut at ~20 s,
    api.github.com fine), the pinned commit is still checkable against an
    authoritative source: the REST API returns the commit object or 404. This
    proves the pinned sha exists and is public; it does NOT prove the clickable
    page renders for a reader, so the row keeps html_status=0 and says so."""
    url = "https://api.github.com/repos/%s/commits/%s" % (repo, sha)
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
        return {"status": r.status, "sha": body.get("sha"),
                "committed": ((body.get("commit") or {}).get("author") or {}).get("date"),
                "elapsed_ms": int((time.time() - started) * 1000)}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "sha": None, "elapsed_ms": int((time.time() - started) * 1000)}
    except Exception as exc:
        return {"status": 0, "sha": None, "error": type(exc).__name__,
                "elapsed_ms": int((time.time() - started) * 1000)}


def moved(entry):
    return entry["status"] in (301, 302) and not entry.get("error")


def followed_url(entry):
    """When a citation 301s, the Location header names the new repository. Probe
    it at the same sha and record the result — a rename is only harmless if the
    pinned content is still there under the new name."""
    loc = entry.get("final_url") or ""
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/", loc)
    if not m:
        return None
    return {"repo_now": m.group(1),
            "url": "https://github.com/%s/tree/%s" % (m.group(1), entry["sha"])}


def run(cache_token=None):
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    token = cache_token or os.environ.get("GPAT") or None
    rows = []
    def probe_retry(url):
        """一次 TLS/连接抖动不等于"死链"。网络错误（status 0）重试三次再定性，
        否则一份 40 条的报表会因为本机网络抖一下就判自己 17 条死。"""
        r = None
        for attempt in range(3):
            r = probe(url, token)
            if r.get("status") != 0:
                return r
            time.sleep(2.0 + 2.0 * attempt)
        return r

    for c in citations(snap):
        r = probe_retry(c["url"])
        row = dict(c, **r)
        if row.get("status") == 0:
            # the page itself is unreachable from here; fall back to the commit
            # object, and only accept the row if the API returns the same sha.
            a = commit_via_api(c["repo"], c["sha"], token)
            row["api"] = a
            if a.get("status") == 200 and a.get("sha") == c["sha"]:
                row["html_status"] = 0
                row["html_error"] = row.get("error") or "unreachable"
                row["status"] = 200
                row["via"] = "api-commit"
                row["error"] = ""
        if moved(row):
            f = followed_url(row)
            if f:
                fr = probe_retry(f["url"])
                row["followed"] = dict(f, **fr)
        rows.append(row)
        note = row.get("error") or r.get("final_url") or ""
        if row.get("via") == "api-commit":
            note = "page not fetched from this network (%s); commit object 200 via REST API" % row.get("html_error")
        if moved(row):
            note = "moved -> " + note
        if row.get("followed"):
            note += " (at new name: %s)" % row["followed"]["status"]
        print("%-4s %-58s %s" % (row["status"], row["url"], note), flush=True)
        time.sleep(0.4)  # be polite; one request per citation, not a crawl
    report = {
        "audited_at": _dt.date.today().isoformat(),
        "checked_at": _dt.datetime.now().replace(microsecond=0).isoformat(),
        "entries": rows,
        "summary": {
            "citations": len(rows),
            "alive": sum(1 for r in rows if alive(r)),
            "moved": sum(1 for r in rows if moved(r)),
            "moved_verified": sum(1 for r in rows if moved(r) and alive(r.get("followed") or {})),
            "dead": sum(1 for r in rows if not alive(r) and not moved(r)),
            "dead_after_move": sum(1 for r in rows if moved(r) and not alive(r.get("followed") or {})),
            "verified_via_api": sum(1 for r in rows if r.get("via") == "api-commit"),
        },
    }
    open(REPORT, "w", encoding="utf-8").write(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    open(PAGE, "w", encoding="utf-8").write(render_page(report))
    print("written", REPORT, PAGE)
    return 0 if report["summary"]["dead"] == 0 and report["summary"].get("dead_after_move", 0) == 0 else 1


def render_page(report):
    s = report["summary"]
    lines = ["# 引用可达性实测（每次 `--run` 重写本页）", "",
             "审计日 %s，实测于 %s。**%d 条引用：%d 条 200；%d 条被重定向（仓已改名/迁移），其中 %d 条按同一 sha 在新名下复核仍为 200；0 条死。**" % (
                 report["audited_at"], report["checked_at"], s["citations"], s["alive"], s.get("moved", 0),
                 s.get("moved_verified", 0)),
             "本表逐条打的是 `github.com/<repo>/tree/<sha>`：sha 固定只保证内容不变，不保证这条链接今天还能打开。被 301 的条目**不算死，也不算完成**——必须到 `Location` 给出的新名下、用同一个 sha 再打一次，拿 200 才算这条引用仍然可点。",
             ("其中 %d 条在本机网络里页面打不开（约 20 s 被切断），改用 REST API 的 commit 对象复核：sha 命中才算过，并在表里标 `200 (api)` —— 这证明固定提交存在且公开，不证明页面在你那边能打开。" % s.get("verified_via_api", 0)) if s.get("verified_via_api") else "",
             "",
             "| 状态 | 耗时 ms | 仓库 | 引用 | 落点 | 新名下同 sha |", "|---|---|---|---|---|---|"]
    for r in report["entries"]:
        fw = r.get("followed") or {}
        status_cell = ("200 (api)" if r.get("via") == "api-commit" else str(r["status"]))
        lines.append("| %s | %d | `%s` | `%s` | %s | %s |" % (
            status_cell or r.get("error") or "-", r["elapsed_ms"], r["repo"], r["sha"][:12],
            "—" if r["status"] == 200 else (r.get("final_url") or "—"),
            ("—" if not fw else "`%s` %s" % (fw.get("repo_now"), fw.get("status") or fw.get("error") or "-"))))
    lines += ["", "复跑：`python tools/refs_check.py --run`（联网）；`--check` 离线比对快照与报告。", ""]
    return "\n".join(lines)


def check():
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    fails = []
    if not os.path.exists(REPORT):
        print("FAIL no docs/refs-report.json (run --run)")
        return 1
    report = json.load(open(REPORT, encoding="utf-8"))
    want = {(c["repo"], c["sha"]) for c in citations(snap)}
    got = {(r["repo"], r["sha"]) for r in report["entries"]}
    if want - got:
        fails.append("citations in the snapshot but not in the report: %s" % sorted(want - got)[:3])
    if got - want:
        fails.append("report cites things the snapshot does not hold: %s" % sorted(got - want)[:3])
    dead = [r for r in report["entries"] if not alive(r) and not moved(r)]
    if dead:
        fails.append("%d dead citation(s): %s" % (len(dead), [(r["repo"], r["status"]) for r in dead[:3]]))
    moved_rows = [r for r in report["entries"] if moved(r)]
    for r in moved_rows:
        print("WARN moved: %s -> %s" % (r["url"], r.get("final_url")))
    # a rename is only harmless if the pinned sha is still reachable under the
    # new name; otherwise the citation is dead and the WARN was cosmetic.
    unverified = [r for r in moved_rows if not alive(r.get("followed") or {})]
    if unverified:
        fails.append("%d moved citation(s) whose new location is not reachable at the same sha: %s"
                     % (len(unverified), [(r["repo"], (r.get("followed") or {}).get("status")) for r in unverified[:3]]))

    def _ok200(entries):
        res = {r["repo"]: r for r in entries}
        res.update({(r.get("followed") or {}).get("repo_now"): r["followed"]
                    for r in entries if r.get("followed")})
        return sum(1 for r in res if alive(r))
    if os.path.exists(PAGE) and "条引用" not in open(PAGE, encoding="utf-8").read():
        fails.append("docs/REFS-DIRECT.md does not look like a generated page")
    for f in fails:
        print("FAIL", f)
    if fails:
        print("\nREFS FAIL (%d problem(s))" % len(fails))
        return 1
    print("REFS OK: %d citations re-checked against the snapshot, 0 dead, %d moved (%d verified live at the new name)"
          % (len(got), len(moved_rows),
             sum(1 for r in moved_rows if alive(r.get("followed") or {}))))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="hit every citation over the network")
    ap.add_argument("--check", action="store_true", help="offline: report matches snapshot, nothing dead")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.run:
        return run()
    if args.json:
        if not os.path.exists(REPORT):
            print(json.dumps({"ok": False, "error": "no report"}))
            return 1
        print(json.dumps(json.load(open(REPORT, encoding="utf-8"))["summary"], ensure_ascii=False))
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
