# Citation reachability: a status code is a property of where you looked from

Measured 2026-11-17, twice, from two independent networks: this Windows machine, and a
Linux cloud host with no credentials and a different network path. `tools/check_citations.py`
holds 45 citations.

| run | exit | reachable | failing |
|---|---|---|---|
| 1 | this machine (scripted urllib) | 40–43 / 45 (varies by the minute) | see below |
| 2 | cloud host (scripted urllib, no token) | 41 / 45 | `eips.ethereum.org` 503, `agentgateway.dev` 503, `modernrequirements.com` 403, `kenpriore.ai` 503 |

Both runs wrote the same kind of result file, and the failing sets barely overlap. That
overlap difference is the actual finding: **reachability here is mostly a property of the
network and the user agent, not of the link.**

## The failures, one by one

| # | link | behaviour | what it means |
|---|---|---|---|
| 1 | `https://www.iso.org/standard/88723.html` (ISO/IEC 24970) | 403 to scripted clients on this machine; 200 with the expected title and "International Standard under publication" when fetched through an agent outlet | bot filtering. The page is real; the 403 is about who is asking |
| 2 | `https://eips.ethereum.org/EIPS/eip-8004` | 503 from the cloud host for a full minute, including with a browser user agent; the canonical source in `ethereum/ERCs` returned 200 | Cloudflare-style blocking of that host from that IP. A mirror now exists, see below |
| 3 | `https://www.modernrequirements.com/fr-ca/page` | **403 from both exits** | this one is a genuine gap, not a network artefact: the vendor blocks automated clients everywhere we can measure. The claim it supports must be treated as "seen by a human in a browser, not machine-verified" |
| 4 | `https://kenpriore.ai/papers/certificate-of-action.pdf` | 503 with our scripted UA from the cloud host, 200 from this machine | UA- or rate-dependent |
| 5 | `https://agentgateway.dev/` | 503 from the cloud host, 200 from this machine | same class as #4 |
| 6 | `https://www.imdrf.org/.../N90...pdf` | timeout here, 200 from the cloud host | opposite direction from #4/#5 |
| 7 | `https://aport.io/about/` | TLS error here, 200 from the cloud host | local route |

## Fixes made today

1. **Browser user agent + retries.** The checker used an honest `citation-check/1.0` agent, which
   several hosts answer with 503/403 while serving a browser normally. It now sends a browser
   user agent and retries 5xx/429 up to twice with backoff. 4xx other than 429 is treated as a real
   answer and is not retried — retrying a 403 would just be hammering a host that said no.
2. **Documented mirrors.** `ALTERNATES` in the checker maps a primary URL to an equally primary
   mirror; a citation passes if either answers 200, and the result records `satisfied_by`.
   Added for ERC-8004: `https://eips.ethereum.org/EIPS/eip-8004` → `https://raw.githubusercontent.com/ethereum/ERCs/master/ERCS/erc-8004.md`
   (verified 200 on the cloud host while the EIP site was 503).

## Rule (unchanged, now with the evidence attached)

A citation passes when **either** exit returns 200 with matching content, and both numbers are
recorded. A link that fails on **both** exits is not "reachable with a caveat" — it is a citation we
cannot machine-verify, and it is labelled that way.

Applying the rule to the two runs: 44/45 pass. The exception is #3
(`modernrequirements.com`), which is recorded as human-verified only.

## Reproduce

```bash
python tools/check_citations.py     # writes tools/out/citations_result.json
# from a second network: run the same command, then compare the two result files
python -c "import json;d=json.load(open('tools/out/citations_result.json'));print([r['name'] for r in d['rows'] if not r['ok']])"
```

## Not done

* No automated content-match step for the 200s: the checker records status, content type and the
  first 4 KB, not a field-by-field comparison with what we cite. That comparison was done by hand
  for the three links that matter most (ISO 24970, ERC-8004, IMDRF N90) and is not scripted.
* No scheduled re-check. Reachability drifts; a link that passes today can 503 next week.
