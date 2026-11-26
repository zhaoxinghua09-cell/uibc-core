---
facts: current
---

# AITB open evaluation: how to submit, what you get, what we will not claim

AITB is Assurance Instrument Test Bench (short form: 试真台). This page is the
entry. It exists because every certificate we looked at in this space says a
"technical test" happened and none of them says what was tested. So the test is
published as a command, and the card names what it did not test.

## How to submit

1. Open an issue with the **AITB evaluation request** template. You give us the
   identifier (one `did:cn` / `did:bid` / any DID you want looked at), and, if you
   have one, a link to a public statement by the operator that the identifier is
   theirs.
2. We run the read-only call ourselves and publish the card in that issue.
3. You re-run it. If your card disagrees with ours at the same timestamp, ours is
   wrong and we say so.

No account is needed for the submitter. The evaluation makes no request to your
systems, only to the public resolver, and stores no personal data.

## What the card contains

Three gates, each check naming the exact observation behind it:

| gate | question | example checks |
|---|---|---|
| G1 reachable | does the resolver answer, and does it say which state | `G1.http`, `G1.envelope`, `G1.status` |
| G2 self-consistent | do the returned fields agree with each other and with the published ranges | key type known, hex length matches the type, controller is a DID, endpoints are `https://`, registration node is a `did:bid:agentnode:` |
| G3 operator acknowledgement | did the operator publicly say this code is theirs | `MISSING` when the submitter supplies nothing — never silently `PASS` |

Plus a **Not tested** list, which is part of the card, not a footnote.

## Which methods we can actually call

A submission for a method we cannot reach is answered with a named state, not a
guess and not a silent failure. The table is the whole truth about our reach:

| method | what an outsider can call | card verdict |
|---|---|---|
| `did:cn` | `POST https://iaisp.teleinfo.cn/api/public/ioa/did/resolve-verify` | `PASS` / `FAIL` |
| `did:bid` | only a test chain (`test.bifcore.bitfactory.cn`), which answered 503 maintenance on 2026-11-26; no public production endpoint | `NO_PUBLIC_ENDPOINT` |
| `did:ctid` | nothing: the registered specification publishes relative paths only (`/didservice/v1/did/get`), access is through a vendor SDK plus an institution certificate, and the operator declared its platform offline on 2026-06-30 | `NO_PUBLIC_ENDPOINT` |
| anything else | nothing | `METHOD_NOT_SUPPORTED` |

`NO_PUBLIC_ENDPOINT` is a finding about the ecosystem, recorded with its reason so
that a reader can disagree with it. It never blames the submitter, and it runs
zero checks — the card says so.

Two example cards ship with the repository: `docs/aitb-example-report.{json,html}`
(`did:cn`, 12 of 12 passed, G3 missing) and
`docs/aitb-example-no-endpoint.{json,html}` (`did:ctid:anicert`, zero calls made).

```powershell
python tools/aitb_evaluate.py --run --did did:cn:agent:xxxx --out reports
python tools/aitb_evaluate.py --run --did did:ctid:anicert --out reports
python tools/aitb_evaluate.py --check --report reports/did_cn_agent_xxxx.json
```

## What we will not claim

- **Not a certification.** The card is a record of observations at a timestamp.
- **Not a conformance verdict.** `G2` checks internal consistency against ranges
  quoted from observed values, not against any standard clause.
- **Not a VC verification.** The platform itself reports
  `vcVerificationStatus: SKIPPED`; we repeat that rather than pretend otherwise.
- **Not a GB/Z 185.2 OID check.** No public mapping rule from a DID to the
  `1.2.156.3088` path exists, so we do not invent one.
- **Not a score against competitors.** A competitive table is published
  separately and no real run has ever changed it.

## Data handling

Read-only `POST /api/public/ioa/did/resolve-verify` and `GET /api/public/ioa/agents`
on `iaisp.teleinfo.cn`. Nothing is written to the platform. Cards contain only
what the platform itself already publishes publicly (agent name, company name,
endpoints). No submitter identity is stored beyond what the issue already shows.

## Fee and limits

Free while the tool is read-only and the volume is small. If a submission needs a
bespoke probe, we say so and quote before doing it, rather than half-doing it for
free. We will refuse a submission that asks us to certify, to rank, or to attest
on behalf of a third party.
