# Running your own verify endpoint

The competitor's answer to "can I check this without installing anything?" is a URL. This repository's answer is a URL **you** can own: one container, no dependencies, no account.

```bash
docker build -f deploy/Dockerfile -t uibc-verify .
docker run -p 8770:8770 uibc-verify
curl -X POST --data-binary @package.zip http://127.0.0.1:8770/verify
```

That is the whole deployment. There is no database, no queue, no API key.

## What it accepts

`POST /verify` with a package **zip** as the body. Response:

```json
{
  "result": "PASS",
  "checks": [{"id": "S1", "result": "PASS", "detail": "…"}, "…"],
  "counts": {"PASS": 12, "INCONCLUSIVE": 1},
  "failed": [], "inconclusive": ["S6"],
  "note": "the endpoint reports what the package shows; it does not assert the package is valid, and it signs nothing"
}
```

`GET /health` returns the limits in force, so a caller can read the rules instead of discovering them by being refused.

## The limit is on

The image starts with `--rate 60 --burst 10` per caller. Sixty verification calls a minute is generous for a person and useless for a loop, which is the point: this process is CPU-bound, and an unlimited public endpoint is an invitation to make your bill someone else's amusement.

Turn it off for a local run (`--rate 0`), keep it on for anything reachable from outside.

## Measured, on one process, 16 concurrent clients

| | throughput | p50 | p95 | p99 |
|---|---|---|---|---|
| unlimited | 195 req/s | 30.5 ms | 218.4 ms | 1256.8 ms |
| `--rate 60 --burst 10` | — | 3.6 ms | 62.3 ms | 1060.8 ms |
| 320 calls under the limit | **11 succeeded, 309 refused 429** | | | |

The eleven is the arithmetic doing its job: burst 10 plus one token refilled. The p99 is honest about a single CPython process under sixteen clients — queueing, not slowness per call. If you need more, run more containers behind a proxy; the limiter is per process, so the effective limit multiplies.

Reproduce with:

```bash
python3 tools/stress_verify.py --workers 16 --requests 320
```

## What this endpoint deliberately does not do

- **It does not sign anything.** The response is a reading of a package, not an attestation by the operator. A verifier that must be trusted is not a verifier.
- **It does not read your filesystem.** The body is the package; there is no path parameter, so there is no path-traversal surface to protect.
- **It does not trust `X-Forwarded-For` by default.** A bucket keyed on a caller-controlled header is not a bucket. Pass `--trust-forwarded` only behind a proxy that overwrites the header — and note that doing so hands the limit's key to the proxy's honesty.

## What has not been verified

- **The image has not been built.** There is no Docker on the machine this was
  written on, so `docker build` has never run against this Dockerfile. What *was*
  verified is the command it starts: `python3 tools/serve_verify.py --host 0.0.0.0
  --port 8770 --rate 60 --burst 10` runs and `/health` answers with the limits
  shown above. Treat the Dockerfile as reviewed, not as tested.
- **No public deployment has been performed.** Nothing here is live; this is the
  path to a live endpoint, not a claim that one exists.

## Deploying to a PaaS

Any host that takes a Dockerfile works. Point it at `deploy/Dockerfile`, set the port to `8770`, and leave the default limit in place. The health check path is `/health`, so a platform that needs one can use it as-is.
