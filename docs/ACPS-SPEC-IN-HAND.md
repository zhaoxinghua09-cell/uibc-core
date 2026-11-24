# The AIC text, in hand (2026-11-24)

## Where it is

| | |
|---|---|
| Document | `ACPs-spec-AIC-v02.02`, "智能体身份码定义" |
| Repository | `aip-pub/ACPs-community`, path `acps-specs/02-ACPs-spec-AIC/ACPs-spec-AIC.md` |
| Host | AtomGit — https://atomgit.com/aip-pub/ACPs-community |
| Fetch used | contents API, base64 payload: `https://atomgit.com/api/v5/repos/aip-pub/ACPs-community/contents/acps-specs/02-ACPs-spec-AIC/ACPs-spec-AIC.md` |
| Copy kept | `sha256:38242a01e79b26b7a56e4c0579a9a175f10a40d704c26e5c89ce9b80816623ab`, 8,043 bytes |
| Authors | 李珂、禹可、刘军、宋昊哲、郭小练、李胤铭、胡晓峰、马镝、陈科良（北京邮电大学）、高歌（中国电子技术标准化研究院） |

Two things to note about how it was found, because both are easy to get wrong:

- **`git/tree` listing returns nothing for these repositories; `contents` does not.** An early probe concluded "the ACPs repositories are empty" from the tree endpoint. That was the API, not the project. The root listing via `contents` shows `acps-specs/`, `acps-docs/`, `acps-sdk/`, `acps-cli/` and the servers.
- **The version moved.** The `aipmc-basic` crate declares alignment to `v02.01`; the text published now is **`v02.02`**. So "we implement v02.01" would have been quoting a crate's belief rather than the document.

## What the document actually says (quoted, not paraphrased)

Arcs, from §3:

1. `1` ISO · `2` country member · `156` China · `4` the agent-interconnection node assigned by the national OID registry
5. version, `1`～`Z`
6. ARSP serial, `1`～`ZZZZZZ`
7. vendor serial, `1`～`ZZZZZZ`
8. ontology serial, `1`～`ZZZZZZZZZ`
9. entity serial, `0`～`ZZZZZZZZZ` — all zeros when the object registered is the ontology
10. checksum, `0000`～`1EKF`

Checksum, §4.1 — this is the part that was previously unverifiable for us:

- CRC-16/CCITT-FALSE, poly `0x1021`, init `0xFFFF`, no reflection, `xorout=0x0000`
- input: ASCII of arcs 1-9 (dots included), letters upper-cased, **plus the ARSP's salt**, "长度不少于 2 字节"
- output: the 16-bit value in Base36, zero-padded to four characters

The document's own worked example, step by step:

```
body   1.2.156.3088.1.1.34C2.478BDF.3GF546
salt   0x12 0x34
crc    0x646C
arc10  0JU4
code   1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4
```

`0xFFFF` → `1EKF` also matches the stated upper bound of arc 10, so the range in §3 and the algorithm in §4 are consistent with each other.

## What changed in this repository because of it

- `uibc_core/acps_identity_code.py` — spec references corrected from v02.01 to **v02.02**, and the module now has a salt-taking path:
  `verify_acps_code(code, salt)` returns `VERIFIED` / `INVALID` / `INCONCLUSIVE`.
  Without a salt it still refuses to judge arc 10 and says the checksum was **not checked**.
  `VERIFIED` carries a reproducible evidence entry (`sha256` over the exact bytes hashed).
- `read_acps_code()` is unchanged in spirit: shape only, `INCONCLUSIVE`, and it now points at
  `verify_acps_code()` instead of saying the checksum is unknowable.
- `tests/test_acps_spec_conformance.py` — 20 tests built only from the document's own
  example, its stated range, and deliberate mutations of stated rules.
- `tests/test_acps_cross_implementation.py` — 16 pinned expectations taken from a third
  implementation, so agreement is a test and not a sentence.

## How this was tested without a real ARSP account

Three layers, cheapest first. The first two run in CI; the third is recorded here.

1. **The document's worked example** (`tests/test_acps_spec_conformance.py`). If our
   arithmetic drifts, this fails. It also fixes the upper bound via `0xFFFF → 1EKF`.
2. **A third implementation as oracle** (`tests/test_acps_cross_implementation.py`).
   `aipub-protocols` 0.0.3 (crates.io, lib name `protocols`) was compiled unpatched on a
   Linux VM (cargo 1.100.0) and asked for checksums over a boundary set: lowercase input,
   salt lengths 2 → 16 bytes, both ends of every segment-length range, ontology form,
   foreign prefixes. Its answers are pasted into the test verbatim. Sixteen of sixteen
   agree. The program is not vendored because it is Rust; the expectations are.
3. **Round-trip self-consistency at scale** (parametrized in the same file): 180 random
   bodies and salts produce a four-character Base36 trailer that verifies back. This
   proves the two directions of our own arithmetic agree; it does not prove conformance,
   which is layer 1's job.

What none of this can do: decide whether a given code was actually **issued**. That needs
the ARSP's registry, not its salt. Every `VERIFIED` here says so in `scope`.

## What is still missing, stated plainly

- **A real code from a real ARSP.** Everything above is the document's example plus
  constructed codes. A genuine issued AIC would test the one thing we cannot: whether the
  issuer's salt and serial allocation match what a third party can recompute.
- **The salt of any ARSP.** Not published, by design. Any holder of one can use
  `verify_acps_code(code, salt)` directly; we cannot obtain it for them.
- **`acps-docs/`** (the reference documentation directory exists in the repository) was
  not read for this change — out of scope, and worth a separate pass if the AIC text leaves
  a question open.
- The repository's `ACPs-community` tree listing via `git/tree` stays broken for anonymous
  callers; `contents` works. Recorded so the next person does not re-diagnose it as an
  empty project.
