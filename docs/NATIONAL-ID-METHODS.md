---
facts: current
---

# National identity codes in the DID registry: what is actually there

This page exists because "how many national DID methods are registered, and can we
reach them" kept being answered in prose. The answer is now a snapshot file plus a
checker, so a reader can tell registry drift from prose drift.

- Snapshot: `docs/NATIONAL-ID-METHODS.json` (8 national-related entries out of 282
  registry methods, as of the 2026-11-17 registry)
- Refresh (network): `python tools/national_methods_snapshot.py --write`
- Verify (offline): `python tools/national_methods_snapshot.py --check`

## The eight entries the registry records as state-related

| method | registry contact | verifiable data registry | spec hosted by | account type |
|---|---|---|---|---|
| `cn` | China Academy of Information and Communications Technology (CAICT) | Astron | `caict-4iot-dev` | organization |
| `bid` | teleinfo caict | bif | `teleinfo-bif` | **user account** |
| `cndid` | teleinfo caict | TChain | `teleinfo-bif` | **user account** |
| `ioa` | teleinfo caict | TChain | `ReciterKim` | **user account** |
| `ctid` | Beijing Zhongdun Anxin Science and Technology Development Co., Ltd | *(empty)* | `617640999` | **user account** |
| `kr` | Ministry of the Interior and Safety, korea | Korea Mobile Identity System | `identify202020` | **user account** |
| `andorra` | David García Beatove | Andorra National Registry (NRTAD) | `davidgarciavargroupiberia` | **user account** |
| `pki` | Eduardo Chongkan | National PKI Trust Registries (X.509) | `Attestto-com` | organization |

Two observations that only became visible once the field was recorded:

1. **Six of the eight specifications are hosted on GitHub user accounts**, including
   `teleinfo-bif` — an account whose name reads like an organisation but whose API
   type is `User`. A state-related claim therefore often rests on a personal
   repository. That is not an accusation; it is a fact a reviewer needs before
   citing the spec as authoritative.
2. **`ctid` records an empty verifiable data registry**, and its platform was
   declared offline on 2026-06-30. An empty VDR means the registry itself never
   said who keeps the ledger.

## What "can we connect" means, and what the answer is

"Connecting" has to pass four questions; failing any one of them means we are not
connected, whatever the code says:

| question | why it matters |
|---|---|
| Q1 is the identifier a DID at all | no DID, no resolution — only login/verification APIs |
| Q2 is there a **public** endpoint | SDKs and private gateways cannot be re-run by an outsider |
| Q3 does access need qualification, contract, or certificate | that is an admission problem, not a technical one |
| Q4 is the credential a VC, or SAML / OIDC / JWT / X.509 | different verifiers, no shared code path |

Current tally, stated as three separate claims rather than one:

- **Observable**: 4 methods we can actually call (1.4% of 282) — `did:cn`, our own
  `did:key` (Ed25519 only) and `did:web`, plus the four-state card for everything
  else. Of the national subset, only `did:cn` has a public endpoint.
- **Verifiable**: 0 foreign national schemes. The domestic 网号/网证 service
  requires an institutional access application that has not been filed.
- **Interoperable**: 0. The two routes (become an overseas registration service
  provider, or bilateral recognition with the `1.2.156.3088` node) are documented
  but not started.

## What this page deliberately does not cover

National schemes that are not DIDs at all — EUDI Wallet / eIDAS, Singpass, Aadhaar
and DigiLocker, JPKI, Korea mobile ID, Brazil gov.br, UAE Pass, Nafath, GOV.UK One
Login, Login.gov and mDL, and the domestic 网号/网证 service. They are login and
verification infrastructures with their own admission rules, and none of them
becomes reachable by writing a resolver. A separate page tracks them; this one is
strictly the registry census.

## Reading the number correctly

`8 of 282` is a subset of registry entries whose contact or VDR claims a state
body. It is **not** a count of national identity systems in the world, and it is
**not** a count of systems we can reach. Three numbers, three different questions.
