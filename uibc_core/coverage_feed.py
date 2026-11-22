"""Revocation-coverage distribution channel (HTTP pull).

The gate can check a coverage statement it is *handed*. This adds the
"handed over the wire" half and one number that can be measured: how long
after the publisher replaces the feed a polling verifier actually sees it.

What this deliberately is not
-----------------------------
There is no push notification, no third-party attestation, and no proof that
the publisher's feed is complete. Detection latency is bounded by the polling
interval plus the feed's own ``issued_at`` freshness window - not by the
publisher's intent. A verifier that polls every T seconds can be blind for up
to T seconds after a revocation lands, and that is exactly what the measured
number means.
"""

import json
import time
import urllib.error
import urllib.request

DEFAULT_TIMEOUT_S = 10.0
MAX_BODY_BYTES = 1 << 20   # a coverage statement is a few hundred bytes


class ChannelError(RuntimeError):
    """The feed could not be read, or what came back is not a coverage object."""


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT_S) -> dict:
    """GET one coverage statement from ``url``. Raises ChannelError on any doubt."""
    if not url:
        raise ChannelError("empty feed url")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "uibc-coverage-feed/0.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(MAX_BODY_BYTES)
    except urllib.error.HTTPError as exc:
        raise ChannelError(f"feed returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ChannelError(f"feed unreachable: {exc.reason}") from exc
    except OSError as exc:                     # socket timeouts land here too
        raise ChannelError(f"feed unreadable: {exc}") from exc

    try:
        cov = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ChannelError(f"feed body is not JSON: {exc}") from exc
    if not isinstance(cov, dict):
        raise ChannelError("feed body is not a JSON object")
    return cov


def poll(url: str, accept, timeout_s: float = 30.0, interval_s: float = 0.25,
         request_timeout: float = 5.0, sleep=time.sleep,
         clock=time.monotonic) -> dict:
    """Poll until ``accept(cov)`` is true or the deadline passes.

    Returns a dict with the last statement seen, the elapsed seconds, how many
    GETs were issued, and the last channel error (if any). The caller decides
    what a timeout means; this function never invents a verdict.
    """
    started = clock()
    polls = 0
    last_cov = None
    last_error = None
    while True:
        polls += 1
        try:
            cov = fetch(url, timeout=request_timeout)
            last_cov = cov
            last_error = None
            if accept(cov):
                return {"ok": True, "cov": cov, "latency_s": clock() - started,
                        "polls": polls, "last_error": None}
        except ChannelError as exc:
            last_error = str(exc)
        if clock() - started >= timeout_s:
            return {"ok": False, "cov": last_cov, "latency_s": clock() - started,
                    "polls": polls, "last_error": last_error}
        sleep(interval_s)
