// A second-language check of uibc-receipt-v1, written without importing any of our
// Python: node:crypto does Ed25519, the Merkle fold and the canonicality rule are
// re-implemented here from the published definition.
//
// What it checks: the inclusion proof folds to the checkpoint root, the operator
// signature verifies over CHECKPOINT_DOMAIN + canonical checkpoint, and the witness
// cosignature verifies over WITNESS_DOMAIN + the checkpoint hash (a separate domain).
//
// What it does NOT check: the statement binding (record shape -> leaf digest), which
// needs the record the log stored; Python covers that one.

import crypto from "node:crypto";
import fs from "node:fs";

const CHECKPOINT_DOMAIN = Buffer.from("uibc-translog-checkpoint-v1\u0000", "latin1");
const WITNESS_DOMAIN = Buffer.from("uibc-translog-witness-v1\u0000", "latin1");

const sha256 = (buf) => crypto.createHash("sha256").update(buf).digest();
const hexToBuf = (hex) => Buffer.from(hex, "hex");

// RFC 6962 leaf/node prefixes
const leafHash = (digestBuf) => sha256(Buffer.concat([Buffer.from([0x00]), digestBuf]));
const nodeHash = (l, r) => sha256(Buffer.concat([Buffer.from([0x01]), l, r]));

// RFC 6962 section 2.1.1 inclusion verification
function rootFromProof(index, size, leaf, proof) {
  if (index >= size) throw new Error("index out of range");
  let fn = index;
  let sn = size - 1;
  let r = leaf;
  for (const p of proof) {
    if ((fn & 1) === 1 || fn === sn) {
      r = nodeHash(p, r);
      while ((fn & 1) === 0 && fn !== 0) {
        fn >>= 1;
        sn >>= 1;
      }
    } else {
      r = nodeHash(r, p);
    }
    fn >>= 1;
    sn >>= 1;
  }
  return r;
}

// Canonical JSON: sorted keys, no whitespace, integers as-is. Enough for the two
// payloads this claim signs (a flat object of strings and small integers).
function canon(value) {
  if (Array.isArray(value)) return "[" + value.map(canon).join(",") + "]";
  if (value && typeof value === "object") {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + canon(value[k])).join(",") + "}";
  }
  return JSON.stringify(value);
}

function ed25519Key(pub32) {
  // raw 32-byte Ed25519 public key wrapped in a SPKI DER header
  const der = Buffer.concat([
    Buffer.from("302a300506032b6570032100", "hex"),
    pub32,
  ]);
  return crypto.createPublicKey({ key: der, format: "der", type: "spki" });
}

function verifyEd25519(pub32, msg, sigB64) {
  const sig = Buffer.from(sigB64, "base64");
  if (sig.length !== 64) return false;
  try {
    return crypto.verify(null, msg, ed25519Key(pub32), sig);
  } catch {
    return false;
  }
}

const file = process.argv[2];
const receipt = JSON.parse(fs.readFileSync(file, "utf8"));
const cp = receipt.log.checkpoint;
const cosig = receipt.log.cosignature;
const entry = receipt.entry;

const results = {};

// 1. inclusion proof
const root = rootFromProof(entry.index, cp.tree_size,
                           leafHash(hexToBuf(entry.leaf_digest)),
                           entry.inclusion_proof.map(hexToBuf));
results.inclusion_proof = root.toString("hex") === cp.root;

// 2. checkpoint signature: domain + canonical(checkpoint without sig)
const cpBody = { ...cp };
delete cpBody.sig;
const cpMsg = Buffer.concat([CHECKPOINT_DOMAIN, Buffer.from(canon(cpBody), "utf8")]);
results.checkpoint_signature =
  verifyEd25519(hexToBuf(receipt.log.operator_public_key), cpMsg, cp.sig);

// 3. witness cosignature: separate domain + sha256(canonical{format,tree_size,root})
const headHash = sha256(Buffer.from(canon({
  format: cp.format, tree_size: cp.tree_size, root: cp.root,
}), "utf8"));
const cosigMsg = Buffer.concat([WITNESS_DOMAIN, headHash]);
results.witness_cosignature =
  cosig.tree_size === cp.tree_size && cosig.root === cp.root &&
  verifyEd25519(hexToBuf(receipt.log.witness_public_key), cosigMsg, cosig.sig);

// 4. a cross-domain attack must fail: the operator signature checked under the
//    witness domain is not a cosignature
results.domain_separation_attack_rejected =
  verifyEd25519(hexToBuf(receipt.log.operator_public_key), cosigMsg, cosig.sig) === false;

// 5. a tampered proof must fail
const badProof = entry.inclusion_proof.slice();
badProof[0] = (badProof[0][0] === "0" ? "1" : "0") + badProof[0].slice(1);
const badRoot = rootFromProof(entry.index, cp.tree_size,
                              leafHash(hexToBuf(entry.leaf_digest)),
                              badProof.map(hexToBuf));
results.tampered_proof_rejected = badRoot.toString("hex") !== cp.root;

console.log(JSON.stringify({
  receipt: file,
  format: receipt.format,
  node: process.version,
  results,
  all: Object.values(results).every(Boolean),
}, null, 2));
