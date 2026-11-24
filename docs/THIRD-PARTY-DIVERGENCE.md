# A third-party implementation, run against our parser

`aipmc-basic` 0.0.2 (Rust, MIT, crates.io, 2026-10) is the only third-party identity-code implementation we can actually execute. This document records what happens when its own examples meet our parser, and what happens when a GB/Z 185.2-shaped code meets its parser. Both directions were run, not inferred.

## What it says it is

From its own module documentation (`src/aic.rs`): aligned to **`ACPs-spec-AIC-v02.01`**, not to GB/Z 185.2. Ten dot-separated arcs:

```
1-4  OID prefix (1.2.156.3088 by default; 1.2.156.1234 in its own spec example)
5    version         Base36, exactly 1
6    ARSP            Base36, 1-6
7    vendor          Base36, 1-6
8    ontology serial Base36, 1-9
9    instance serial Base36, 1-9  (all zeros = ontology AIC)
10   CRC             Base36, exactly 4
```

Checksum: `CRC-16/CCITT-FALSE(arcs 1-9 ++ ARSP salt)`, Base36, zero-padded to four. Default salt `00 49 4F 41`; each ARSP uses its own.

## Read as a different document, not as a wrong one

GB/Z 185.2-2026 as published has **eight** arcs (`1.2.156.3088.版本.服务方.请求方.序列号`) and no checksum. ACPs v02.01 has **ten** plus a checksum. A code valid under one is not valid under the other. Neither implementation is broken; they answer different papers.

Our earlier wording — "deviates from the national standard in three places" — was the wrong frame. Corrected: **it implements a community spec that splits the serial into two arcs and adds a checksum the national standard does not define.** The divergence is between documents, which makes it an interoperability question for the authors of both, not a bug report to this crate.

## Both directions, executed 2026-11-24

Harness (Linux, cargo 1.100.0, crate fetched from `static.crates.io`, unmodified):

```rust
use basic::aic::Aic;   // lib name is `basic`, package name is `aipmc-basic`
fn try_parse(label: &str, s: &str) {
    match Aic::parse_with_prefix(s, "") {
        Ok(a) => println!("{label}: ACCEPT checksum(default salt)={}", a.verify_checksum(b"\x00\x49\x4F\x41")),
        Err(e) => println!("{label}: REJECT {e:?}"),
    }
}
```

Its output:

```
10seg_acps_v0201: ACCEPT  checksum(default salt)=true
10seg_acps_spec:  ACCEPT  checksum(default salt)=false
8seg_gbz185:      REJECT  InvalidAic
10seg_bad_crc:    ACCEPT  checksum(default salt)=false
9seg:             REJECT  InvalidAic
```

Our parser on the same inputs (`uibc_core/agent_identity_code.py`, same day):

| Input | aipmc-basic | ours |
|---|---|---|
| `1.2.156.3088.1.0001.00001.ABC123.000001.176F` | ACCEPT, CRC ✓ | **INVALID**, profile `aip-acps` |
| `1.2.156.1234.1.1.34C2.478BDF.3GF546.0H9T` | ACCEPT, CRC ✗ under default salt | **INVALID**, profile `aip-acps` |
| `1.2.156.3088.1.360.360.000000001` | **REJECT** | **INCONCLUSIVE**, profile `gbz185.2` |

## Four findings that survive the correction

1. **The two families reject each other.** A standard-shaped code fails its parser; a ten-arc code fails ours. "AIC compatible" has to name the document.
2. **Its `parse` does not check the checksum.** `10seg_bad_crc` constructs successfully with a deliberately wrong CRC; verification is a separate `verify_checksum(salt)` call. Its docs say "构造即校验". A wrong-checksum code being constructible means that phrasing over-claims — recorded here as a documentation discrepancy, not a security defect.
3. **The salt is private.** Only the default salt is published, so a third party cannot verify checksums on codes issued by another ARSP. Its own spec example failing under the default salt is what makes this visible rather than theoretical.
4. **The prefix is not fixed in practice.** Default `1.2.156.3088`, spec example `1.2.156.1234`. A reader that pins one prefix cannot read both.

## What changes on our side

- Code: nothing. `parse_agent_code()` already refuses the ten-arc form with an explicit reason, and `detect_profile()` labels it `aip-acps` instead of guessing.
- `docs/COMPETITIVE-LANDSCAPE.md`: the row for `aipmc-basic` is rewritten from "diverges from the standard" to "implements a different document", with the interoperability question stated as a question.

## Reproduction

```
curl -sSL -o a.crate https://static.crates.io/crates/aipmc-basic/aipmc-basic-0.0.2.crate
tar xzf a.crate
# Cargo.toml: [dependencies] aipmc-basic = { path = "./aipmc-basic-0.0.2" }
# src/main.rs: use basic::aic::Aic;    // the lib name is `basic`
cargo run -q
```
