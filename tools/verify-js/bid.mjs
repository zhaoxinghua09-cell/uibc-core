// Independent re-check of a signed BID document (《星火·链网BID协议》 §5).
//
// This file shares no code with the Python implementation on purpose: the claim
// under test is "a third party, with a different language and a different
// canonicalizer, gets the same bytes and the same answer". Reusing our own JCS
// here would turn the check into a tautology.
//
// What it does:
//   1. reads a BID document (fixtures/bid/signed_document.json)
//   2. drops `proof`, canonicalizes per RFC 8785 (UTF-16 key order, no whitespace,
//      ECMAScript number form) - implemented below, in JS, from the RFC text
//   3. verifies the Ed25519 signature with node's crypto (OpenSSL), raw 32-byte
//      key, over those bytes
//   4. prints the sha256 of the canonical bytes so the Python side can compare
//
// Exit codes: 0 verified, 1 did not verify, 2 could not read the input.
//
// Usage: node tools/verify-js/bid.mjs [path-to-document.json]

import crypto from "node:crypto";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

function base58Decode(text) {
  let n = 0n;
  for (const ch of text) {
    const idx = B58.indexOf(ch);
    if (idx < 0) throw new Error(`not Base58: ${JSON.stringify(ch)}`);
    n = n * 58n + BigInt(idx);
  }
  let hex = n === 0n ? "" : n.toString(16);
  if (hex.length % 2) hex = "0" + hex;
  const leadingZeros = text.length - text.replace(/^1+/, "").length;
  return Buffer.concat([Buffer.alloc(leadingZeros), Buffer.from(hex, "hex")]);
}

// RFC 8785 §3.2.3: sort by UTF-16 code units.
function utf16Compare(a, b) {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const ca = a.charCodeAt(i);
    const cb = b.charCodeAt(i);
    if (ca !== cb) return ca - cb;
  }
  return a.length - b.length;
}

// RFC 8785 §3.2.2.3 via ECMAScript Number::toString, which is what String(n) is.
function jcsNumber(v) {
  if (!Number.isFinite(v)) throw new Error("non-finite number is not JSON");
  if (Object.is(v, -0)) return "0";
  return String(v);
}

function jcsString(s) {
  let out = '"';
  for (const ch of s) {
    const code = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (code === 0x08) out += "\\b";
    else if (code === 0x09) out += "\\t";
    else if (code === 0x0a) out += "\\n";
    else if (code === 0x0c) out += "\\f";
    else if (code === 0x0d) out += "\\r";
    else if (code < 0x20) out += "\\u" + code.toString(16).padStart(4, "0");
    else out += ch;
  }
  return out + '"';
}

function jcs(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return jcsNumber(value);
  if (typeof value === "string") return jcsString(value);
  if (Array.isArray(value)) return "[" + value.map(jcs).join(",") + "]";
  if (typeof value === "object") {
    const keys = Object.keys(value).sort(utf16Compare);
    return "{" + keys.map((k) => jcsString(k) + ":" + jcs(value[k])).join(",") + "}";
  }
  throw new Error(`unsupported type ${typeof value}`);
}

function main(argv) {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const repo = path.resolve(here, "..", "..");
  const target = argv[2] || path.join(repo, "fixtures", "bid", "signed_document.json");
  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(target, "utf8"));
  } catch (err) {
    console.error(`cannot read ${target}: ${err.message}`);
    return 2;
  }

  const proof = doc.proof;
  if (!proof || typeof proof.signatureValue !== "string") {
    console.error("document carries no proof.signatureValue");
    return 1;
  }
  const withoutProof = { ...doc };
  delete withoutProof.proof;

  const bytes = Buffer.from(jcs(withoutProof), "utf8");
  const digest = crypto.createHash("sha256").update(bytes).digest("hex");
  console.log(`signing-bytes-sha256 ${digest}`);

  // locate the key the proof names, and require it to be an authentication key
  const keyId = proof.creator;
  const key = (doc.publicKey || []).find((k) => k.id === keyId);
  if (!key) {
    console.error(`proof.creator ${keyId} is not a publicKey of this document`);
    return 1;
  }
  if ((doc.authentication || []).length && !doc.authentication.includes(keyId)) {
    console.error(`proof.creator ${keyId} is not in authentication`);
    return 1;
  }

  let raw = Buffer.from(key.publicKeyHex || "", "hex");
  if (raw.length === 33 && raw[0] === 0xb0) raw = raw.subarray(1); // BIF algorithm prefix
  if (raw.length !== 32) {
    console.error(`only 32-byte Ed25519 keys are checkable here, got ${raw.length}`);
    return 1;
  }

  // SPKI wrapper for a raw Ed25519 public key (RFC 8410): fixed 12-byte prefix
  const SPKI = Buffer.from("302a300506032b6570032100", "hex");
  const publicKey = crypto.createPublicKey({
    key: Buffer.concat([SPKI, raw]),
    format: "der",
    type: "spki",
  });

  let signature;
  try {
    signature = base58Decode(proof.signatureValue);
  } catch (err) {
    console.error(err.message);
    return 1;
  }
  if (signature.length !== 64) {
    console.error(`signature decodes to ${signature.length} bytes, expected 64`);
    return 1;
  }

  const ok = crypto.verify(null, bytes, publicKey, signature);
  console.log(`document-id ${doc.id}`);
  console.log(`key-id ${keyId}`);
  console.log(`signature-verified ${ok}`);
  return ok ? 0 : 1;
}

process.exit(main(process.argv));
