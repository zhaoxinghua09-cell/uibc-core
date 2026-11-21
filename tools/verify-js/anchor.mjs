// The publisher's anchor, judged by the second implementation.
//
// `anchor_check.py` answers one question: is this the package that publisher
// signed, in that state? Two things decide it - the seal verifies under the key
// the anchor names, and the package checkpoint equals the head the anchor pins.
//
// This file reaches the same verdict with a different toolchain: node:crypto
// for the signature, verify.mjs for the package structure. A stranger who has
// node but not Python can now redo the publisher check, and two independent
// implementations agreeing is the only reason to believe either.
//
// What it does NOT do: judge the optional RFC 3161 block. Ranking a timestamp
// needs the JCS digest of four pinned values and a CA chain check; the Python
// checker does that. Here it is reported as "not judged", because a verdict
// borrowed from another implementation is not a second opinion.
//
// Usage:  node tools/verify-js/anchor.mjs <bundle-dir> [--anchor <path>]
// Exit:   0 ANCHORED   1 NOT ANCHORED   2 FAILED   3 usage

import { createHash, createPublicKey, verify as cryptoVerify } from "node:crypto";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));

// --- RFC 8785 (JCS): sorted keys, no whitespace, ECMAScript number form -----
function jcs(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(jcs).join(",") + "]";
  const keys = Object.keys(value).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + jcs(value[k])).join(",") + "}";
}

const canonicalBytes = (doc) => Buffer.from(jcs(doc), "utf8");

function main() {
  const argv = process.argv.slice(2);
  let bundle = null;
  let anchorPath = null;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--anchor") { anchorPath = argv[i + 1] ?? null; i += 1; }
    else if (bundle === null) bundle = argv[i];
  }
  if (bundle === null) {
    console.error("usage: node tools/verify-js/anchor.mjs <bundle-dir> [--anchor <path>]");
    return 3;
  }

  const pkg = existsSync(join(bundle, "package")) && statSync(join(bundle, "package")).isDirectory()
    ? join(bundle, "package") : bundle;
  if (anchorPath === null) anchorPath = join(bundle, "anchor.json");
  if (!existsSync(anchorPath)) {
    console.error("no anchor at " + anchorPath + " - an anchor read out of the bundle " +
                  "alone would prove what the bundle already claims");
    return 2;
  }

  const anchor = readJson(anchorPath);
  const problems = [];

  // ---- 1. the anchor's key, and that it is the key the package was sealed with
  const pubB64 = anchor.pubkey_b64;
  const head = anchor.checkpoint_head;
  if (!pubB64 || !head) {
    console.error("FAILED: anchor carries no pubkey_b64 and/or checkpoint_head");
    return 2;
  }
  const pub = Buffer.from(String(pubB64), "base64");
  if (pub.length !== 32) {
    console.error("FAILED: anchor pubkey is not a 32-byte Ed25519 key");
    return 2;
  }

  let sealOk = false;
  try {
    const seal = readJson(join(pkg, "signatures", "seal.json"));
    if (seal.algorithm !== "Ed25519") {
      problems.push("seal uses " + seal.algorithm + "; an HMAC seal cannot be checked without the owner's key");
    } else if (String(seal.public_key) !== String(pubB64)) {
      problems.push("the package was sealed with key " + String(seal.public_key).slice(0, 16) +
                    "... but the anchor pins " + String(pubB64).slice(0, 16) +
                    "... - a key substitution, or the wrong anchor");
    } else {
      const identity = readJson(join(pkg, "identity.json"));
      const manifest = readJson(join(pkg, "manifest.json"));
      const signed = String(seal.signed || "");
      const doc = { identity, manifest };
      if (signed.includes("lifecycle")) doc.lifecycle = readJson(join(pkg, "lifecycle.json"));
      const key = createPublicKey({ key: { kty: "OKP", crv: "Ed25519",
                                           x: pub.toString("base64url") }, format: "jwk" });
      sealOk = cryptoVerify(null, canonicalBytes(doc), key,
                            Buffer.from(String(seal.signature), "base64"));
      if (!sealOk) problems.push("the seal does not verify under the key the anchor pins");
    }
  } catch (err) {
    problems.push("seal is not readable: " + err.message);
  }

  // ---- 2. the state the anchor pins, judged by verify.mjs
  const r = spawnSync(process.execPath,
                      [join(HERE, "verify.mjs"), pkg, "--expect-head", String(head)],
                      { encoding: "utf8" });
  let structural = null;
  try { structural = JSON.parse(r.stdout); } catch (e) {
    problems.push("verify.mjs produced no readable verdict" + (r.stderr ? ": " + r.stderr.trim().slice(0, 120) : ""));
  }
  let headOk = false;
  if (structural) {
    const fails = (structural.checks || []).filter((c) => c.result === "FAIL");
    const s9 = (structural.checks || []).find((c) => c.id === "S9");
    headOk = s9 !== undefined && s9.result === "PASS";
    for (const c of fails.slice(0, 4)) problems.push(c.id + " " + c.name + ": " + (c.detail || ""));
    if (!headOk) {
      problems.push("S9 head pinned out-of-band: " + ((s9 && s9.detail) ||
                    "the package state could not be recomputed, so the pin was not compared"));
    }
  }

  // ---- 3. the timestamp, left to the implementation that implements it
  const tsaNote = anchor.tsa ? "not judged here (see anchor_check.py)" : "none";

  const anchored = problems.length === 0 && sealOk && headOk;
  const verdict = anchored ? "ANCHORED" : (sealOk === false || !headOk ? "FAILED" : "NOT ANCHORED");

  console.log("VERDICT: " + verdict);
  console.log("anchor   : key " + String(anchor.key_id || "").slice(0, 16) + "… head " +
              String(head).replace("sha256:", "").slice(0, 16) + "…");
    console.log("seal     : " + (sealOk ? "verifies under the pinned key" : "does not verify"));
  console.log("head     : " + (headOk ? "package checkpoint equals the pinned head" : "does not match"));
  console.log("timestamp: " + tsaNote);
  for (const p of problems) console.log("  - " + p);
  console.log("implementation: verify-js (independent of uibc-core)");
  return anchored ? 0 : 2;
}

process.exit(main());
