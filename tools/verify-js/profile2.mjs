#!/usr/bin/env node
// `uibc-scitt/2`, in a second language: the same sixteen bytes the Python tier
// replays, read independently.
//
//   node tools/verify-js/profile2.mjs <package-dir> --receipt <file.cose> \
//        [--trusted-issuer <hex>] [--trusted-size <n>]
//   node tools/verify-js/profile2.mjs --vectors conformance/profile2/cases.json
//
// Differences from `profile.mjs` (which implements `/1`): the root is an RFC 6962
// Merkle tree over ascending content digests, and the inclusion proof in the
// COSE label 396 header is actually read and verified. That is what makes `OK`
// reachable here; `/1` stays exactly as it was, partial and never OK.
//
// Every hostile input (bad CBOR, wrong path, wrong leaf, size mismatch, extra
// vdp element) returns a verdict, never throws: a verifier that dies on one bad
// receipt can be switched off by one bad receipt.

import { createHash, createPublicKey, verify as cryptoVerify } from "node:crypto";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const LBL_VDS = 395;
const LBL_VDP = 396;
const PROFILE_ID_2 = "uibc-scitt/2";

const OK = "OK";
const PARTIAL_ISSUER_UNCHECKED = "PARTIAL_ISSUER_UNCHECKED";
const FAIL_INCLUSION = "FAIL_INCLUSION";
const FAIL_VALUE_MISMATCH = "FAIL_VALUE_MISMATCH";
const FAIL_SIGNATURE = "FAIL_SIGNATURE";
const FAIL_PACKAGE = "FAIL_PACKAGE";
const FAIL_MALFORMED = "FAIL_MALFORMED";
const UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME";
const FAIL_UNTRUSTED_ISSUER = "FAIL_UNTRUSTED_ISSUER";

const SUPPORTED_VDS = { 1: "rfc9162-sha256" };

const sha256buf = (buf) => createHash("sha256").update(buf).digest();
const sha256 = (buf) => sha256buf(buf).toString("hex");
const json = (path) => JSON.parse(readFileSync(path, "utf8"));

// --- RFC 6962, Section 2.1 ------------------------------------------------
const LEAF_PREFIX = Buffer.from([0x00]);
const NODE_PREFIX = Buffer.from([0x01]);
const leafHash = (digest) => sha256buf(Buffer.concat([LEAF_PREFIX, digest]));
const nodeHash = (l, r) => sha256buf(Buffer.concat([NODE_PREFIX, l, r]));

function largestPow2Below(n) {
  let k = 1;
  while (k * 2 < n) k *= 2;
  return k;
}

function mth(leaves) {
  if (leaves.length === 0) return sha256buf(Buffer.alloc(0));
  if (leaves.length === 1) return leaves[0];
  const k = largestPow2Below(leaves.length);
  return nodeHash(mth(leaves.slice(0, k)), mth(leaves.slice(k)));
}

function auditPath(leaves, index) {
  if (leaves.length === 1) return [];
  const k = largestPow2Below(leaves.length);
  if (index < k) {
    return [...auditPath(leaves.slice(0, k), index), mth(leaves.slice(k))];
  }
  return [...auditPath(leaves.slice(k), index - k), mth(leaves.slice(0, k))];
}

function verifyInclusion(leaf, index, size, path, root) {
  try {
    if (!Number.isInteger(size) || size <= 0) return false;
    if (!Number.isInteger(index) || index < 0 || index >= size) return false;
    if (!Buffer.isBuffer(leaf) || leaf.length !== 32) return false;
    if (!Array.isArray(path)) return false;
    for (const p of path) {
      if (!Buffer.isBuffer(p) || p.length !== 32) return false;
    }
    let fn = index;
    let sn = size - 1;
    let r = leaf;
    for (const sibling of path) {
      if (fn % 2 === 1 || fn === sn) {
        r = nodeHash(sibling, r);
        while (fn % 2 === 0 && fn !== 0) { fn = Math.floor(fn / 2); sn = Math.floor(sn / 2); }
      } else {
        r = nodeHash(r, sibling);
      }
      fn = Math.floor(fn / 2);
      sn = Math.floor(sn / 2);
    }
    return r.equals(root) && sn === 0;
  } catch {
    return false;
  }
}

// --- registered value and package facts -----------------------------------
function registeredValue(root, count, agentId) {
  if (!/^[0-9a-f]{64}$/.test(root)) throw new Error("root must be 64 lowercase hex");
  if (!Number.isInteger(count) || count < 1) throw new Error("count must be a positive int");
  return Buffer.from(
    '{"agent_id":' + JSON.stringify(agentId) + ',"count":' + count +
    ',"profile":' + JSON.stringify(PROFILE_ID_2) + ',"root":' + JSON.stringify(root) + "}",
    "utf8");
}

function packageFacts(pkgDir) {
  const problems = [];
  let entries = [];
  let agentId = "";
  try {
    entries = json(join(pkgDir, "evidence", "index.json")).entries || [];
    agentId = json(join(pkgDir, "manifest.json")).agent_id || "";
  } catch (err) {
    return { root: "", count: 0, agentId: "", hashes: [], problems: ["package unreadable: " + err.message] };
  }
  const declared = new Set();
  const hashes = [];
  for (const entry of entries) {
    const rel = entry.path;
    const ch = entry.content_hash;
    if (!rel || !ch) { problems.push("entry without path or content_hash"); continue; }
    declared.add(rel.split("/").join("\\"));
    const full = join(pkgDir, "evidence", rel);
    if (!existsSync(full) || !statSync(full).isFile()) {
      problems.push("declared file missing: " + rel);
      continue;
    }
    const actual = sha256(readFileSync(full));
    if (actual !== ch) {
      problems.push("content changed: " + rel + " (" + actual.slice(0, 8) + " != " + ch.slice(0, 8) + ")");
      continue;
    }
    hashes.push(actual);
  }
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const full = join(dir, name);
      if (statSync(full).isDirectory()) { walk(full); continue; }
      const rel = relative(join(pkgDir, "evidence"), full);
      if (rel === "index.json") continue;
      if (!declared.has(rel)) problems.push("undeclared file under evidence/: " + rel);
    }
  };
  walk(join(pkgDir, "evidence"));
  if (problems.length) return { root: "", count: 0, agentId, hashes: [], problems };
  const leaves = hashes.map((h) => Buffer.from(h, "hex")).sort(Buffer.compare).map(leafHash);
  return { root: mth(leaves).toString("hex"), count: hashes.length, agentId, hashes, problems: [] };
}

// --- minimal CBOR ----------------------------------------------------------
class CborError extends Error {}

function decodeCbor(buf, pos = 0) {
  const read = (n) => {
    if (pos + n > buf.length) throw new CborError("truncated at " + pos);
    let v = 0;
    for (let i = 0; i < n; i += 1) v = v * 256 + buf[pos + i];
    pos += n;
    return v;
  };
  const first = read(1);
  const major = first >> 5;
  const info = first & 31;
  let size;
  if (info < 24) size = info;
  else if (info === 24) size = read(1);
  else if (info === 25) size = read(2);
  else if (info === 26) size = read(4);
  else throw new CborError("unsupported length encoding " + info);
  switch (major) {
    case 0: return [size, pos];
    case 1: return [-1 - size, pos];
    case 2: {
      const bytes = buf.subarray(pos, pos + size);
      if (bytes.length !== size) throw new CborError("truncated bstr");
      return [bytes, pos + size];
    }
    case 3: return [buf.subarray(pos, pos + size).toString("utf8"), pos + size];
    case 4: {
      const arr = [];
      for (let i = 0; i < size; i += 1) { const [v, p] = decodeCbor(buf, pos); arr.push(v); pos = p; }
      return [arr, pos];
    }
    case 5: {
      const obj = {};
      for (let i = 0; i < size; i += 1) {
        const [k, p1] = decodeCbor(buf, pos);
        const [v, p2] = decodeCbor(buf, p1);
        obj[k] = v; pos = p2;
      }
      return [obj, pos];
    }
    case 6: {
      const [v, p] = decodeCbor(buf, pos);
      return [{ tag: size, value: v }, p];
    }
    case 7:
      if (info === 20) return [false, pos];
      if (info === 21) return [true, pos];
      if (info === 22) return [null, pos];
      throw new CborError("simple value " + info + " not supported");
    default:
      throw new CborError("major type " + major + " not supported");
  }
}

function encodeCbor(value) {
  const enc = (v) => {
    if (v === null) return Buffer.from([0xf6]);
    if (typeof v === "number") {
      if (v >= 0) {
        if (v < 24) return Buffer.from([v]);
        if (v <= 0xff) return Buffer.from([24, v]);
        if (v <= 0xffff) return Buffer.from([25, v >> 8, v & 0xff]);
        return Buffer.from([26, (v >>> 24) & 0xff, (v >>> 16) & 0xff, (v >>> 8) & 0xff, v & 0xff]);
      }
      throw new CborError("negative values not needed here");
    }
    if (Buffer.isBuffer(v)) {
      if (v.length < 24) return Buffer.concat([Buffer.from([0x40 + v.length]), v]);
      if (v.length <= 0xff) return Buffer.concat([Buffer.from([0x58, v.length]), v]);
      throw new CborError("bstr too long");
    }
    if (typeof v === "string") {
      const b = Buffer.from(v, "utf8");
      if (b.length < 24) return Buffer.concat([Buffer.from([0x60 + b.length]), b]);
      throw new CborError("text too long");
    }
    if (Array.isArray(v)) {
      if (v.length >= 24) throw new CborError("array too long");
      return Buffer.concat([Buffer.from([0x80 + v.length]), ...v.map(enc)]);
    }
    throw new CborError("cannot encode " + typeof v);
  };
  return enc(value);
}

function decodeReceipt(bytes) {
  let msg;
  try { msg = decodeCbor(bytes)[0]; } catch (err) { return [null, null, null, null, "cbor: " + err.message]; }
  if (!Array.isArray(msg) || msg.length !== 4) return [null, null, null, null, "not a COSE_Sign1 4-element array"];
  const [protectedBytes, , payload, sig] = msg;
  if (!Buffer.isBuffer(protectedBytes) || !Buffer.isBuffer(sig)) {
    return [null, null, null, null, "protected/signature must be bstr"];
  }
  let hdr;
  try { hdr = decodeCbor(protectedBytes)[0]; } catch (err) {
    return [null, null, null, null, "protected header: " + err.message];
  }
  if (hdr === null || typeof hdr !== "object" || Buffer.isBuffer(hdr) || Array.isArray(hdr)) {
    return [null, null, null, null, "protected header is not a map"];
  }
  return [hdr, payload === null ? null : payload, sig, protectedBytes, ""];
}

function readVdp(vdp) {
  if (!Buffer.isBuffer(vdp)) return [null, "vdp is not a bstr"];
  let item;
  try { item = decodeCbor(vdp)[0]; } catch (err) { return [null, "vdp is not CBOR: " + err.message]; }
  if (!Array.isArray(item) || item.length !== 4) {
    return [null, "vdp must be a 4-element array, got " + (Array.isArray(item) ? item.length : typeof item)];
  }
  const [leaf, index, size, path] = item;
  if (!Buffer.isBuffer(leaf) || leaf.length !== 32) return [null, "vdp[0] (leaf) must be a 32-byte bstr"];
  if (!Number.isInteger(index) || index < 0) return [null, "vdp[1] (index) must be a non-negative int"];
  if (!Number.isInteger(size) || size < 1) return [null, "vdp[2] (tree_size) must be a positive int"];
  if (!Array.isArray(path) || !path.every((p) => Buffer.isBuffer(p) && p.length === 32)) {
    return [null, "vdp[3] (path) must be a list of 32-byte bstr"];
  }
  return [{ leaf, index, size, path }, ""];
}

function verifySignature(protectedBytes, payload, sig, issuerKey) {
  const body = encodeCbor(["Signature1", protectedBytes, Buffer.alloc(0), payload]);
  const key = createPublicKey({
    key: { kty: "OKP", crv: "Ed25519", x: issuerKey.toString("base64url") },
    format: "jwk",
  });
  return cryptoVerify(null, body, key, sig);
}

function verify(pkgDir, receiptBytes, opts = {}) {
  const steps = [];
  const notes = [];
  let issuer = "NOT_CHECKED";
  const ret = (verdict) => ({ verdict, steps, notes, issuer });

  const facts = packageFacts(pkgDir);
  if (facts.problems.length) {
    steps.push({ step: 1, name: "recompute root", outcome: FAIL_PACKAGE, detail: facts.problems.slice(0, 6) });
    return ret(FAIL_PACKAGE);
  }
  steps.push({ step: 1, name: "recompute root", outcome: "ok",
               detail: "rfc6962 root=" + facts.root.slice(0, 16) + " count=" + facts.count +
                       " agent_id=" + facts.agentId });

  const [hdr, payload, sig, protectedBytes, why] = decodeReceipt(receiptBytes);
  if (!hdr) {
    steps.push({ step: 2, name: "rebuild registered value", outcome: FAIL_MALFORMED, detail: why });
    return ret(FAIL_MALFORMED);
  }

  const want = registeredValue(facts.root, facts.count, facts.agentId);
  if (payload !== null && !payload.equals(want)) {
    steps.push({ step: 2, name: "rebuild registered value", outcome: FAIL_VALUE_MISMATCH,
                 detail: "receipt payload differs from rebuilt value (" + payload.length +
                         " vs " + want.length + " bytes)" });
    return ret(FAIL_VALUE_MISMATCH);
  }
  steps.push({ step: 2, name: "rebuild registered value", outcome: "ok",
               detail: "bytes equal (" + want.length + " B)" });

  const vds = hdr[LBL_VDS];
  if (!(vds in SUPPORTED_VDS)) {
    steps.push({ step: 3, name: "check receipt", outcome: UNSUPPORTED_SCHEME,
                 detail: "vds=" + vds + " not in " + JSON.stringify(Object.keys(SUPPORTED_VDS)) });
    notes.push("an unsupported tree is a refusal, not evidence that the package is false");
    return ret(UNSUPPORTED_SCHEME);
  }
  if (!(LBL_VDP in hdr)) {
    steps.push({ step: 3, name: "check receipt", outcome: FAIL_MALFORMED,
                 detail: "no vdp (COSE label 396) in the protected header" });
    return ret(FAIL_MALFORMED);
  }

  const [vdp, vdpWhy] = readVdp(hdr[LBL_VDP]);
  if (!vdp) {
    steps.push({ step: 3, name: "inclusion proof", outcome: FAIL_MALFORMED, detail: vdpWhy });
    return ret(FAIL_MALFORMED);
  }
  if (vdp.size !== facts.count) {
    steps.push({ step: 3, name: "inclusion proof", outcome: FAIL_INCLUSION,
                 detail: "vdp tree_size " + vdp.size + " != registered count " + facts.count });
    return ret(FAIL_INCLUSION);
  }
  if (!verifyInclusion(vdp.leaf, vdp.index, vdp.size, vdp.path, Buffer.from(facts.root, "hex"))) {
    steps.push({ step: 3, name: "inclusion proof", outcome: FAIL_INCLUSION,
                 detail: "path does not reconstruct the registered root (index " + vdp.index +
                         " of " + vdp.size + ")" });
    return ret(FAIL_INCLUSION);
  }
  steps.push({ step: 3, name: "inclusion proof", outcome: "ok",
               detail: "leaf " + vdp.leaf.toString("hex").slice(0, 16) + " at index " + vdp.index +
                       " of " + vdp.size + ", " + vdp.path.length + " sibling(s)" });

  const issuerKey = hdr[4];
  const sigOk = Buffer.isBuffer(issuerKey)
    ? verifySignature(protectedBytes, payload === null ? want : payload, sig, issuerKey)
    : false;
  if (!sigOk) {
    const outcome = payload === null ? FAIL_VALUE_MISMATCH : FAIL_SIGNATURE;
    steps.push({ step: 3, name: "check receipt", outcome,
                 detail: "signature does not verify over the rebuilt value" });
    return ret(outcome);
  }
  steps.push({ step: 3, name: "check receipt", outcome: "ok",
               detail: "signature over " + SUPPORTED_VDS[vds] + " ok" });

  if (opts.trustedIssuers && opts.trustedIssuers.length) {
    const allowed = opts.trustedIssuers.map((k) => String(k).toLowerCase().replace(/^0x/, ""));
    if (!allowed.includes(issuerKey.toString("hex"))) {
      issuer = "UNTRUSTED";
      steps.push({ step: 3, name: "issuer trust", outcome: FAIL_UNTRUSTED_ISSUER,
                   detail: "receipt key " + issuerKey.toString("hex").slice(0, 16) +
                           "... is not among the trusted issuers" });
      notes.push("a self-consistent receipt from an unknown key proves the bytes agree " +
                 "with themselves, not that a service registered them");
      return ret(FAIL_UNTRUSTED_ISSUER);
    }
    issuer = "TRUSTED";
    steps.push({ step: 3, name: "issuer trust", outcome: "ok", detail: "receipt key is a trusted issuer" });
  } else {
    steps.push({ step: 3, name: "issuer trust", outcome: "NOT_CHECKED",
                 detail: "no trusted issuer list supplied; self-consistency only" });
    notes.push("issuer trust NOT checked: pass a trusted issuer list to ask it");
  }

  if (opts.trustedSize !== null && opts.trustedSize !== undefined) {
    if (opts.trustedSize < facts.count) {
      steps.push({ step: 5, name: "tree size", outcome: FAIL_VALUE_MISMATCH,
                   detail: "count " + facts.count + " exceeds trusted size " + opts.trustedSize });
      return ret(FAIL_VALUE_MISMATCH);
    }
    steps.push({ step: 5, name: "tree size", outcome: "ok",
                 detail: "count " + facts.count + " <= trusted size " + opts.trustedSize });
  } else {
    steps.push({ step: 5, name: "tree size", outcome: "skipped", detail: "no trusted size supplied" });
  }
  steps.push({ step: 6, name: "monotonicity", outcome: "skipped",
               detail: "needs a previous receipt for the same producer" });

  if (issuer === "TRUSTED") {
    notes.push("OK here means: this file is inside a size-" + facts.count + " tree whose root " +
               "the receipt signs, and the signing key is one you were given. It does not " +
               "mean the evidence is true");
    return ret(OK);
  }
  notes.push("inclusion verified, but the issuer question was not asked; that is PARTIAL, not OK");
  return ret(PARTIAL_ISSUER_UNCHECKED);
}

// --- CLI -------------------------------------------------------------------
const here = fileURLToPath(import.meta.url);
const repoRoot = resolve(here, "..", "..", "..");

function usage() {
  console.error("usage: node tools/verify-js/profile2.mjs <package-dir> --receipt <file.cose> " +
                "[--trusted-issuer <hex>] [--trusted-size <n>]\n" +
                "       node tools/verify-js/profile2.mjs --vectors conformance/profile2/cases.json");
  process.exit(2);
}

function replayVectors(casesPath) {
  const doc = json(casesPath);
  let allOk = true;
  for (const c of doc.cases) {
    const pkg = resolve(repoRoot, c.package);
    const receipt = readFileSync(resolve(repoRoot, "conformance", "profile2", c.receipt));
    const res = verify(pkg, receipt, {
      trustedIssuers: c.trusted_issuers || null,
      trustedSize: c.trusted_size === undefined ? null : c.trusted_size,
    });
    const got = { verdict: res.verdict, issuer: res.issuer };
    const ok = got.verdict === c.expected.verdict && got.issuer === c.expected.issuer;
    allOk = allOk && ok;
    console.log((ok ? "  ok " : "  BAD") + " " + c.id.padEnd(18) + " " +
                String(got.verdict).padEnd(28) + " issuer " + String(got.issuer).padEnd(12) +
                (ok ? "" : " expected " + c.expected.verdict + "/" + c.expected.issuer));
  }
  console.log("RESULT:", allOk ? "all cases match (python and node agree)" : "MISMATCH");
  console.log("OK cases:", doc.ok_cases.join(", "));
  return allOk ? 0 : 1;
}

const argv = process.argv.slice(2);
if (!argv.length) usage();

if (argv[0] === "--vectors") {
  if (!argv[1]) usage();
  process.exit(replayVectors(resolve(argv[1])));
}

let pkg = null;
let receiptPath = null;
let trustedIssuers = null;
let trustedSize = null;
for (let i = 0; i < argv.length; i += 1) {
  if (argv[i] === "--receipt") receiptPath = argv[++i];
  else if (argv[i] === "--trusted-issuer") (trustedIssuers ||= []).push(argv[++i]);
  else if (argv[i] === "--trusted-size") trustedSize = Number(argv[++i]);
  else if (pkg === null) pkg = argv[i];
}
if (!pkg || !receiptPath) usage();

const res = verify(resolve(pkg), readFileSync(receiptPath), { trustedIssuers, trustedSize });
process.stdout.write(JSON.stringify(res, null, 1) + "\n");
process.exit(res.verdict === OK ? 0 : 1);
