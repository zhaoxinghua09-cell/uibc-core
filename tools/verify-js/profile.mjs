#!/usr/bin/env node
// The RFC 9942 application profile, in a second language.
//
// `draft-zhao-uibc-scitt-profile-00.md` Section 5 lists six steps; `uibc_core/
// profile.py` implements them in Python. A profile that only one language can
// run is a proposal, not an application profile, so this file implements the
// same steps independently and replays the same bytes:
//
//   node tools/verify-js/profile.mjs <package-dir> --receipt <file.cose>
//   node tools/verify-js/profile.mjs --vectors conformance/profile/cases.json
//
// What this file does NOT do, for the same reason the Python one does not:
// evaluate the inclusion proof. `vdp`'s shape is defined by the verifiable-data
// structure a service applies, and this profile fixes none, so reading those
// bytes would mean inventing a format. The best verdict is therefore
// PARTIAL_INCLUSION_UNCHECKED, and it is never OK.
//
// It agrees with the Python verifier on the twelve recorded cases; the test
// `tests/test_profile_js.py` fails if the two ever disagree.

import { createHash, createPublicKey, verify as cryptoVerify } from "node:crypto";
import { createPrivateKey } from "node:crypto";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const LBL_VDS = 395;
const LBL_VDP = 396;
const PROFILE_ID = "uibc-scitt/1";

const OK = "OK";
const PARTIAL_INCLUSION_UNCHECKED = "PARTIAL_INCLUSION_UNCHECKED";
const FAIL_VALUE_MISMATCH = "FAIL_VALUE_MISMATCH";
const FAIL_SIGNATURE = "FAIL_SIGNATURE";
const FAIL_PACKAGE = "FAIL_PACKAGE";
const FAIL_MALFORMED = "FAIL_MALFORMED";
const UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME";
const FAIL_UNTRUSTED_ISSUER = "FAIL_UNTRUSTED_ISSUER";

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");
const json = (path) => JSON.parse(readFileSync(path, "utf8"));

// --- JCS, narrowed to what the registered value needs --------------------
// The four members, sorted by code point, strings escaped as JSON: that is
// RFC 8785 for this shape (no numbers besides an integer count).
function registeredValue(root, count, agentId, profile = PROFILE_ID) {
  if (!/^[0-9a-f]{64}$/.test(root)) throw new Error("root must be 64 lowercase hex");
  if (!Number.isInteger(count) || count < 1) throw new Error("count must be a positive int");
  const s = JSON.stringify(agentId);
  return Buffer.from(
    '{"agent_id":' + s + ',"count":' + count +
    ',"profile":' + JSON.stringify(profile) + ',"root":' + JSON.stringify(root) + "}",
    "utf8");
}

// --- evidence root, the same construction as uibc_core/canonical.py -----
// SHA-256 over the JCS of the sorted content hashes.
function evidenceRoot(hashes) {
  const sorted = hashes.slice().sort();
  const text = "[" + sorted.map((h) => JSON.stringify(h)).join(",") + "]";
  return sha256(Buffer.from(text, "utf8"));
}

function packageFacts(pkgDir) {
  const problems = [];
  let entries = [];
  let agentId = "";
  try {
    const idx = json(join(pkgDir, "evidence", "index.json"));
    entries = idx.entries || [];
    agentId = json(join(pkgDir, "manifest.json")).agent_id || "";
  } catch (err) {
    return { root: "", count: 0, agentId: "", problems: ["package unreadable: " + err.message] };
  }
  const declared = new Set();
  const hashes = [];
  for (const entry of entries) {
    const rel = entry.path;
    const ch = entry.content_hash;
    if (!rel || !ch) { problems.push("entry without path or content_hash"); continue; }
    const norm = rel.split("/").join("\\");
    declared.add(norm);
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
  if (problems.length) return { root: "", count: 0, agentId, problems };
  return { root: evidenceRoot(hashes), count: hashes.length, agentId, problems: [] };
}

// --- the smallest CBOR reader that can read a COSE_Sign1 header ---------
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
    case 0: return [size, pos];                       // unsigned int
    case 1: return [-1 - size, pos];                   // negative int
    case 2: {                                          // byte string
      const bytes = buf.subarray(pos, pos + size);
      if (bytes.length !== size) throw new CborError("truncated bstr");
      return [bytes, pos + size];
    }
    case 3: {                                          // text string
      const text = buf.subarray(pos, pos + size).toString("utf8");
      return [text, pos + size];
    }
    case 4: {                                          // array
      const arr = [];
      for (let i = 0; i < size; i += 1) { const [v, p] = decodeCbor(buf, pos); arr.push(v); pos = p; }
      return [arr, pos];
    }
    case 5: {                                          // map
      const obj = {};
      for (let i = 0; i < size; i += 1) {
        const [k, p1] = decodeCbor(buf, pos);
        const [v, p2] = decodeCbor(buf, p1);
        obj[k] = v; pos = p2;
      }
      return [obj, pos];
    }
    case 6: {                                          // tag: keep the tag, read the value
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
      if (b.length <= 0xff) return Buffer.concat([Buffer.from([0x78, b.length]), b]);
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
  if (!Array.isArray(msg) || msg.length !== 4) {
    return [null, null, null, null, "not a COSE_Sign1 4-element array"];
  }
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

function verifySignature(protectedBytes, payload, sig, issuerKey) {
  const body = encodeCbor(["Signature1", protectedBytes, Buffer.alloc(0), payload]);
  const key = createPublicKey({
    key: { kty: "OKP", crv: "Ed25519", x: issuerKey.toString("base64url") },
    format: "jwk",
  });
  return cryptoVerify(null, body, key, sig);
}

function jwkFromSeedHex(hex) {
  // Only used by the self-test: derive the public key a seed would produce is
  // not something this file needs; tests pass the key, not the seed.
  const priv = createPrivateKey({
    key: { kty: "OKP", crv: "Ed25519", d: Buffer.from(hex, "hex").toString("base64url") },
    format: "jwk",
  });
  return createPublicKey(priv).export({ format: "jwk" }).x;
}

function verify(pkgDir, receiptBytes, opts = {}) {
  const supportedVds = opts.supportedVds || { 1: "rfc9162-sha256" };
  const steps = [];
  const notes = [];
  let issuer = "NOT_CHECKED";
  const ret = (verdict) => ({ verdict, steps, notes, issuer });

  const facts = packageFacts(pkgDir);
  if (facts.problems.length) {
    steps.push({ step: 1, name: "recompute root", outcome: FAIL_PACKAGE,
                 detail: facts.problems.slice(0, 6) });
    return ret(FAIL_PACKAGE);
  }
  steps.push({ step: 1, name: "recompute root", outcome: "ok",
               detail: "root=" + facts.root.slice(0, 16) + " count=" + facts.count +
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
  if (!(vds in supportedVds)) {
    steps.push({ step: 3, name: "check receipt", outcome: UNSUPPORTED_SCHEME,
                 detail: "vds=" + vds + " not in supported set " +
                         JSON.stringify(Object.keys(supportedVds)) });
    notes.push("an unsupported tree is a refusal, not evidence that the package is false");
    return ret(UNSUPPORTED_SCHEME);
  }
  if (!(LBL_VDP in hdr)) {
    steps.push({ step: 3, name: "check receipt", outcome: FAIL_MALFORMED,
                 detail: "no vdp (inclusion proof) in the protected header" });
    return ret(FAIL_MALFORMED);
  }

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
  steps.push({ step: 3, name: "check receipt", outcome: PARTIAL_INCLUSION_UNCHECKED,
               detail: "signature over " + supportedVds[vds] + " ok; inclusion proof not evaluated " +
                       "(no vdp encoding fixed by this profile)" });

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
    steps.push({ step: 3, name: "issuer trust", outcome: "ok",
                 detail: "receipt key is a trusted issuer" });
  } else {
    steps.push({ step: 3, name: "issuer trust", outcome: "NOT_CHECKED",
                 detail: "no trusted issuer list supplied; the signature was checked against " +
                         "the key the receipt carries, which establishes self-consistency only" });
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
    steps.push({ step: 5, name: "tree size", outcome: "skipped",
                 detail: "no trusted size supplied; nothing invented" });
  }
  steps.push({ step: 6, name: "monotonicity", outcome: "skipped",
               detail: "needs a previous receipt for the same producer" });

  notes.push("a pass here means the package reproduces the registered value and the receipt's " +
             "signature covers it; it does not mean the evidence is true");
  return ret(PARTIAL_INCLUSION_UNCHECKED);
}

// --- CLI ----------------------------------------------------------------
const here = fileURLToPath(import.meta.url);
const repoRoot = resolve(here, "..", "..", "..");

function usage() {
  console.error("usage: node tools/verify-js/profile.mjs <package-dir> --receipt <file.cose> " +
                "[--trusted-issuer <hex>] [--trusted-size <n>]\n" +
                "       node tools/verify-js/profile.mjs --vectors conformance/profile/cases.json");
  process.exit(2);
}

function replayVectors(casesPath) {
  const doc = json(casesPath);
  let allOk = true;
  const rows = [];
  for (const c of doc.cases) {
    const pkg = resolve(repoRoot, c.package);
    const receipt = readFileSync(resolve(repoRoot, "conformance", "profile", c.receipt));
    const res = verify(pkg, receipt, {
      trustedIssuers: c.trusted_issuers || null,
      trustedSize: c.trusted_size === undefined ? null : c.trusted_size,
    });
    const got = { verdict: res.verdict, issuer: res.issuer };
    const ok = got.verdict === c.expected.verdict && got.issuer === c.expected.issuer;
    allOk = allOk && ok;
    rows.push({ id: c.id, got, expected: c.expected, ok });
  }
  for (const r of rows) {
    console.log((r.ok ? "  ok " : "  BAD") + " " + r.id.padEnd(15) + " " +
                r.got.verdict.padEnd(28) + " issuer " + r.got.issuer.padEnd(12) +
                (r.ok ? "" : " expected " + r.expected.verdict + "/" + r.expected.issuer));
  }
  console.log("RESULT:", allOk ? "all cases match (python and node agree)" : "MISMATCH");
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
  if (argv[i] === "--receipt") { receiptPath = argv[++i]; }
  else if (argv[i] === "--trusted-issuer") { (trustedIssuers ||= []).push(argv[++i]); }
  else if (argv[i] === "--trusted-size") { trustedSize = Number(argv[++i]); }
  else if (pkg === null) { pkg = argv[i]; }
}
if (!pkg || !receiptPath) usage();

const res = verify(resolve(pkg), readFileSync(receiptPath), {
  trustedIssuers, trustedSize,
});
process.stdout.write(JSON.stringify(res, null, 1) + "\n");
process.exit(res.verdict === PARTIAL_INCLUSION_UNCHECKED ? 0 : 1);
