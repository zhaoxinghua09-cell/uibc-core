# China-registry DID methods: what the specifications actually say

Fetched 2026-11-24, from the specification URLs recorded in the W3C DID Extensions
registry (`w3c/did-extensions`, `methods/<name>.json` — 282 entries: 279
registered, 3 deprecated, counted by cloning the repository and listing the JSON
files). Byte counts below are the sizes of the files we read, so a later reader
can tell whether the text moved.

| method | operator (registry entry) | specification file | bytes |
|---|---|---|---|
| `did:cn` | CAICT / Astron | `caict-4iot-dev/CN-DID-Method-Specification` → `README.md` | 6,536 |
| `did:ioa` | teleinfo CAICT (TChain) | `ReciterKim/ioa` → `doc/en/IOA Protocol Specification.md` | 30,306 |
| `did:cndid` | teleinfo CAICT (TChain) | `teleinfo-bif/cndid` → `doc/en/CNDID Protocol Specification.md` | 42,450 |
| `did:ctid` | Beijing Zhongdun Anxin (anicert) | `617640999/ctid-did-register` → `anicert-ctid-did-en.md` | 12,230 |
| `did:oan` | OpenAgenet | `OpenAgenet/oan-public-docs` → `did-oan-specs/doc/OAN DID Method Specification.md` | 79,958 |
| `did:cndomain` | CNNIC (working draft, 2026-05-07) | `cndomain-dev.github.io/.../did-cndomain-method-specification-draft.html` | 126,546 chars of extracted text |

`did:cn`'s specification link resolves to a repository containing only this
README; there is no separate grammar document. That is the whole published text,
which is why `did:cn` is supported at the narrowest level here.

## Identifier rules as published

- `did:cn` — `issuer "." industry "." enterprise`; `issuer = 2DIGIT`,
  `industry = 3*5DIGIT`, `enterprise = 1*128DIGIT`. Example `did:cn:88.100.1`.
- `did:ioa`, `did:cndid` — optional 4-character `acsn` + `:` + a `suffix` of 22–42
  alphanumerics; the first two suffix characters name algorithm (`z` SM2,
  `e` Ed25519, `s` secp256k1) and encoding (`f` base58, `s` base64, `t` base32).
  `did:ioa:tele` / `did:cndid:tele` are resolver-only DIDs with no key material.
- `did:ctid` — 64 **uppercase** hex characters (SM3 hash of the identity attributes),
  e.g. `did:ctid:16D44117484372A2D010BDAA56703E723FB4C5C06CA44105F0C9C5B8020A7073`.
- `did:oan` — `did:oan:<5 base58>:<32 base58>`, canonical length 46, case-sensitive.
- `did:cndomain` — lowercase `<label.>+.cn`, optional `:<object-type>:<object-name>`,
  every segment `[a-z0-9-]`.

## What each method lets a stranger check

| method | identifier ABNF | offline document | resolution |
|---|---|---|---|
| `did:cn` | enforced | no | registry HTTP `GET /did/resolve/<did>` (spec §3.2); the caller must supply the base URL |
| `did:ioa` | enforced | no | chain `operation: "read"` to a registration node (spec §5.2); caller must supply it |
| `did:cndid` | enforced | no | same read shape as `did:ioa` |
| `did:ctid` | enforced | no | none published (vendor SDK, SM2 keys) — refused |
| `did:oan` | enforced | no | none published (no HTTP read API in the spec) — refused |
| `did:cndomain` | enforced | no | HTTPS publication; caller must supply the base URL |

## The finding that rules out an offline-verification claim

For `did:ioa` / `did:cndid` we tried to rebuild a DID document from the identifier
alone, the way `did:key` allows. It is **structurally impossible** for these methods:

- the suffix is capped at 42 characters, so the key body after the two prefix
  letters is at most 40 characters;
- a 32-byte Ed25519 key is 43–44 characters in base58 (43 in base64, 52 in base32);
- so no permitted encoding can carry a whole 32-byte key in the published grammar.

Both published examples confirm it: 30-character bodies decode to about 22 bytes.
`uibc_core.did_cn` therefore records the decoded length but never asserts a key
size, and returns no offline document for these methods. A resolver that pretended
otherwise would produce an authoritative-looking, wrong answer.

## Scope note

`did_cn.py` is standard-library only, has no network default, and refuses any method
whose published text fixes no resolution channel. Adding a method means adding its
ABNF to `did_cn.py` and its line to this file — not loosening a regex that
"kind of works". `did:wba` (AgentNetworkProtocol) also has a public specification
whose resolution rule is HTTPS `did.json`, i.e. structurally the same as `did:web`;
it is deliberately left out of this change and continues to raise
`UnsupportedMethod` until a resolver branch and its tests are added.

## Defect this replaced

`uibc_core/did.py` carried, until 2026-11-24, the sentence "as of 2026-11-20 none of
them has a published specification — 11 candidate document paths returned 401/404".
That was true of the platform paths we had tried and false as a statement about
specifications: all six methods above have public text, and so does `did:wba`. The
sentence is removed rather than softened, because a stale negative is still a false
claim.
