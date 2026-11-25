"""GitHub API calls that survive a repository move, without leaking the token.

Why this exists. `FG-TIDA/use-cases` was renamed to `fg-tida-wg0/use-cases`; the
old path answers 307 to `api.github.com/repositories/<id>/...`. A client that
follows that redirect while dropping `Authorization` sends the write anonymously
and gets back `401 Requires authentication` -- which reads like a permissions
problem and cost two days of the wrong investigation (issue #71, 2026-11-23..25).

The rule this module enforces:

* 307 / 308 keep the method, the body and the credential -- but only while the
  host stays the same. GitHub's own redirects rewrite the path on
  `api.github.com`, never move to another host.
* A redirect to a different host raises, rather than quietly forwarding a bearer
  token to whoever the first response named. Silence is how credentials leak.

Anything that is not a redirect is returned as `(status, body)` so callers can
look at the code themselves.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

REDIRECT_CODES = (307, 308)


class _RefuseToAutoFollow(urllib.request.HTTPRedirectHandler):
    """Turn urllib's automatic redirect into an HTTPError we handle ourselves.

    urllib follows 307 on its own and happens to keep the header on the same
    host, which would hide the cross-host case behind library behaviour. Making
    it raise means every hop passes through `request`, where the host is checked.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_RefuseToAutoFollow)


class CrossHostRedirect(Exception):
    """A redirect pointing at a different host than the one we sent to."""

    def __init__(self, url, location):
        self.url = url
        self.location = location
        super().__init__("refusing to forward a credential from %s to %s"
                         % (url, location))


def _same_host(a, b):
    return urllib.parse.urlsplit(a).netloc.lower() == urllib.parse.urlsplit(b).netloc.lower()


def request(url, token=None, method="GET", payload=None, timeout=60, max_hops=5):
    """Return (status, parsed_body). Follows 307/308 on the same host only."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    for _ in range(max_hops):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "uibc-core"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with _OPENER.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                return resp.status, (json.loads(body) if body.strip() else {})
        except urllib.error.HTTPError as e:
            if e.code in REDIRECT_CODES:
                location = e.headers.get("Location")
                if not location:
                    raise
                target = urllib.parse.urljoin(url, location)
                if not _same_host(url, target):
                    raise CrossHostRedirect(url, target)
                url = target
                continue
            body = e.read().decode("utf-8", "replace")
            return e.code, (json.loads(body) if body.strip() else {})
    raise RuntimeError("more than %d redirects, still not at the resource" % max_hops)
