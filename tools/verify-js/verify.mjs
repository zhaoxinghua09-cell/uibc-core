#!/usr/bin/env node
// An independent structural verifier for UIBC packages, written in JavaScript
// with no dependency on uibc-core and no third-party packages.
//
// Covered here: package structure (S1), identity consistency (S2), evidence
// integrity (S4), evidence root (S5), Ed25519 seals (S6), index metadata (S7),
// the package checkpoint (S8), the closure declaration (S10), strict
// serialization (S11), timestamp and identifier strictness (S12), Merkle
// inclusion (S13) and strict base64 (S14).
//
// Not covered, on purpose: external timestamps (S16), the receipt chain (S17),
// policy artefact resolution (S18) and the out-of-band pin (S9). Those need
// RFC 3161 and an observation made outside this package. A checker that claimed them without implementing them would be worse
// than one that says it cannot.
// Because it cannot attest signatures, it never returns PASS.
//
// Usage:  node tools/verify-js/verify.mjs <package-dir>

import { createHash, createPublicKey, verify as cryptoVerify } from "node:crypto";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, normalize, sep } from "node:path";

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

// --- RFC 8785 (JCS) -------------------------------------------------------

// RFC 6962 Merkle tree: leaf = SHA-256(0x00 || data), node = SHA-256(0x01 || l || r).
// An unbalanced tail is promoted, not duplicated: duplicating it lets two
// different trees share a root, which is the classic mistake.
const LEAF_PREFIX = Buffer.from([0x00]);
const NODE_PREFIX = Buffer.from([0x01]);

function leafHash(data) {
  return createHash("sha256").update(Buffer.concat([LEAF_PREFIX, data])).digest();
}

function nodeHash(left, right) {
  return createHash("sha256").update(Buffer.concat([NODE_PREFIX, left, right])).digest();
}

function merkleRoot(leaves) {
  if (leaves.length === 0) return Buffer.alloc(32);
  if (leaves.length === 1) return leaves[0];
  let k = 1;
  while (k * 2 < leaves.length) k *= 2;
  return nodeHash(merkleRoot(leaves.slice(0, k)), merkleRoot(leaves.slice(k)));
}

function verifyInclusion(leaf, index, size, proof, root) {
  if (!Number.isInteger(size) || size <= 0) return false;
  if (!Number.isInteger(index) || index < 0 || index >= size) return false;
  let fn = index, sn = size - 1, r = leaf;
  for (const sibling of proof) {
    if (!Buffer.isBuffer(sibling) || sibling.length !== 32) return false;
    if (fn % 2 === 1 || fn === sn) {
      r = nodeHash(sibling, r);
      while (fn % 2 === 0 && fn !== 0) { fn /= 2; sn /= 2; }
    } else {
      r = nodeHash(r, sibling);
    }
    fn = Math.floor(fn / 2);
    sn = Math.floor(sn / 2);
  }
  return r.equals(root) && sn === 0;
}

function jcs(value) {
  if (value === null) return "null";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("JCS: non-finite number");
    if (!Number.isSafeInteger(value) && Number.isInteger(value)) {
      throw new Error("JCS: integer outside the ECMAScript safe range");
    }
    return Object.is(value, -0) ? "0" : JSON.stringify(value);
  }
  if (typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return "[" + value.map(jcs).join(",") + "]";
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + jcs(value[k])).join(",") + "}";
  }
  throw new Error("JCS: unsupported type " + typeof value);
}

const canonicalBytes = (value) => Buffer.from(jcs(value), "utf8");

// --- duplicate member detection -------------------------------------------
// JSON.parse keeps the last duplicate silently, so a document with a repeated
// key survives parsing. Scanning the raw text is the only way to see it.
function duplicateKeys(raw) {
  const stack = [];
  const hits = [];
  let i = 0;
  while (i < raw.length) {
    const ch = raw[i];
    if (ch === "{") { stack.push({ keys: new Set(), expectKey: true }); i++; continue; }
    if (ch === "}") { stack.pop(); i++; continue; }
    if (ch === "[") { stack.push(null); i++; continue; }
    if (ch === "]") { stack.pop(); i++; continue; }
    if (ch === "\"") {
      let j = i + 1;
      while (j < raw.length) {
        if (raw[j] === "\\") { j += 2; continue; }
        if (raw[j] === "\"") break;
        j++;
      }
      const token = raw.slice(i, j + 1);
      const top = stack[stack.length - 1];
      if (top && top.expectKey) {
        const key = JSON.parse(token);
        if (top.keys.has(key)) hits.push(key);
        top.keys.add(key);
        top.expectKey = false;
      }
      i = j + 1;
      continue;
    }
    if (ch === "," && stack.length) {
      const top = stack[stack.length - 1];
      if (top) top.expectKey = true;
    }
    i++;
  }
  return hits;
}

// --- helpers --------------------------------------------------------------
const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));

function listFiles(root, prefix = "") {
  const out = [];
  const dir = prefix ? join(root, prefix) : root;
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    const rel = prefix ? prefix + "/" + name : name;
    if (statSync(join(root, rel)).isDirectory()) out.push(...listFiles(root, rel));
    else out.push(rel);
  }
  return out;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const STAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;

function realDate(text) {
  if (typeof text !== "string" || !STAMP.test(text)) return false;
  if (Number.isNaN(Date.parse(text))) return false;
  const d = new Date(Date.parse(text));
  const [y, mo, da] = text.slice(0, 10).split("-").map(Number);
  return d.getUTCFullYear() === y && d.getUTCMonth() + 1 === mo && d.getUTCDate() === da;
}

// Files that are declared structurally rather than in the evidence index.
const STRUCTURAL = new Set(["evidence/index.json", "evidence/merkle.json",
                            "evidence/chain.json", "evidence/anchors.json",
                            "evidence/policies.json"]);

// --- checks ---------------------------------------------------------------
function verify(pkg) {
  const checks = [];
  const note = (id, name, ok, detail) =>
    checks.push({ id, name, result: ok ? "PASS" : "FAIL", detail });

  // S1 package structure, including files nobody declared
  {
    const problems = [];
    const required = ["manifest.json", "identity.json", "lifecycle.json",
                      "evidence/index.json"];
    for (const p of required) {
      if (!existsSync(join(pkg, p))) problems.push("missing: " + p);
    }
    let manifest = null;
    try { manifest = readJson(join(pkg, "manifest.json")); } catch { problems.push("manifest is not JSON"); }
    if (manifest && (typeof manifest.schema !== "string" || !manifest.schema.startsWith("uibc-core/"))) {
      problems.push("manifest.schema is not a uibc-core schema");
    }
    let declared = new Set();
    try {
      const index = readJson(join(pkg, "evidence/index.json"));
      declared = new Set((index.entries || []).map((e) => "evidence/" + String(e.path)));
    } catch { /* S4 reports the index */ }
    for (const rel of listFiles(pkg)) {
      if (rel === "manifest.json" || rel === "identity.json" || rel === "lifecycle.json") continue;
      if (rel.startsWith("signatures/")) continue;
      if (STRUCTURAL.has(rel) || rel.startsWith("evidence/policies/")) continue;
      // Lock and backup files are how a writer protects a package, not
      // evidence. Anything hidden is machinery.
      if (rel.split("/").pop().startsWith(".")) continue;
      if (!declared.has(rel)) problems.push("undeclared file: " + rel);
    }
    note("S1", "package structure", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S2 identity consistency
  {
    let ok = false, detail = "missing files";
    try {
      const id = readJson(join(pkg, "identity.json"));
      const manifest = readJson(join(pkg, "manifest.json"));
      ok = !!id.agent_id && id.agent_id === manifest.agent_id &&
           typeof id.owner === "string" && id.owner.length > 0;
      detail = ok ? "ok" : "agent_id or owner does not line up with the manifest";
    } catch { /* detail already set */ }
    note("S2", "identity consistency", ok, detail);
  }

  // S4 evidence integrity
  const hashes = [];
  {
    const problems = [];
    try {
      const index = readJson(join(pkg, "evidence/index.json"));
      const entries = index.entries || [];
      if (!entries.length) problems.push("evidence index has no entries");
      for (const e of entries) {
        if (typeof e.path !== "string") { problems.push("entry without a path"); continue; }
        const rel = normalize("evidence/" + e.path);
        if (rel.startsWith("..") || rel.includes(".." + sep)) {
          problems.push("path escapes the package: " + e.path); continue;
        }
        let body = null;
        try { body = readFileSync(join(pkg, rel)); }
        catch { problems.push("missing evidence file: " + e.path); continue; }
        const got = sha256(body);
        if (got !== e.content_hash) problems.push("content hash mismatch: " + e.path);
        else hashes.push(got);
      }
    } catch (err) { problems.push("unreadable index: " + err.message); }
    note("S4", "evidence integrity", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S5 evidence root
  {
    let ok = false, detail = "no hashes to root";
    try {
      const manifest = readJson(join(pkg, "manifest.json"));
      const root = sha256(canonicalBytes(hashes.slice().sort()));
      ok = root === manifest.evidence_root;
      detail = ok ? "ok" : "evidence_root does not re-derive: computed " + root.slice(0, 12);
    } catch (err) { detail = err.message; }
    note("S5", "evidence root", ok, detail);
  }

  // S7 evidence index metadata
  {
    const problems = [];
    try {
      const index = readJson(join(pkg, "evidence/index.json"));
      for (const e of (index.entries || [])) {
        if (!UUID.test(String(e.evidence_id))) problems.push("evidence_id is not a UUID");
        if (!["ACTION", "OUTPUT", "DECISION"].includes(e.type)) {
          problems.push("unknown evidence type: " + e.type);
        }
        if (!realDate(String(e.created_at))) problems.push("created_at is not a real ISO-8601 Z time");
        if (typeof e.content_hash !== "string" || e.content_hash.length !== 64) {
          problems.push("content_hash is not a sha256 hex digest");
        }
      }
    } catch (err) { problems.push("unreadable index: " + err.message); }
    note("S7", "evidence index metadata", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S11 strict serialization, in the same sense the Python verifier means it:
  // duplicate member names, raw control characters inside a document, bytes
  // that are not valid UTF-8. All of these are invisible to JSON.parse and
  // survive it, which is exactly the two-reader split the check exists for.
  {
    const problems = [];
    const files = ["manifest.json", "identity.json", "lifecycle.json",
                   "evidence/index.json"];
    for (const rel of files) {
      const path = join(pkg, rel);
      if (!existsSync(path)) continue;
      const buf = readFileSync(path);
      const text = buf.toString("utf8");
      if (Buffer.from(text, "utf8").length !== buf.length || text.includes("\uFFFD")) {
        problems.push(rel + ": bytes are not valid UTF-8");
      }
      const dup = duplicateKeys(text);
      if (dup.length) problems.push(rel + ": repeated member name " + dup[0]);
      const ctrl = [...text].find((ch) => ch.codePointAt(0) < 0x20 &&
                     !("\t\n\r".includes(ch)));
      if (ctrl) problems.push(rel + ": unescaped control character");
    }
    note("S11", "strict serialization", problems.length === 0, problems.slice(0, 4).join("; ") || "ok");
  }

  // S7 continued: the index METADATA digest must match the one carried in the
  // manifest. Content hashes are already bound by S4 and S5; what was left
  // unbound was path, declared type and the free-text note -- a forged
  // "reviewed and approved" note passes every hash check without this.
  {
    try {
      const manifest = readJson(join(pkg, "manifest.json"));
      const index = readJson(join(pkg, "evidence/index.json"));
      const declared = manifest.evidence_index_digest || index.evidence_index_digest;
      if (declared) {
        const meta = (index.entries || []).map((e) => ({
          path: String(e.path || ""), type: e.type, note: e.note,
          action_digest: e.action_digest ?? null,
        }));
        meta.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
        const got = "sha256:" + sha256(canonicalBytes(meta));
        if (got !== declared) {
          const c = checks.find((x) => x.id === "S7");
          c.result = "FAIL";
          c.detail = "metadata digest does not re-derive";
        }
      }
    } catch { /* S7 already reported what it could read */ }
  }

  // S6 seal signature. Ed25519 can be checked here because the package
  // records the public key: that is the whole point of an asymmetric seal --
  // a stranger verifies provenance with no secret at all. An HMAC seal cannot
  // be checked without the owner's key, and this verifier says so instead of
  // guessing.
  {
    const sealPath = join(pkg, "signatures", "seal.json");
    if (!existsSync(sealPath)) {
      note("S6", "seal signature", false, "package is unsigned; provenance is not attested");
    } else {
      let verdict = "inconclusive", detail = "";
      try {
        const seal = readJson(sealPath);
        const identity = readJson(join(pkg, "identity.json"));
        const manifest = readJson(join(pkg, "manifest.json"));
        if (seal.algorithm !== "Ed25519") {
          detail = "seal uses " + seal.algorithm +
                   "; an HMAC seal cannot be verified without the owner's key";
        } else {
          const lifecycle = readJson(join(pkg, "lifecycle.json"));
          const signed = String(seal.signed || "");
          const doc = { identity, manifest };
          if (signed.includes("lifecycle")) doc.lifecycle = lifecycle;
          const msg = canonicalBytes(doc);
          const pub = Buffer.from(String(seal.public_key), "base64");
          const sig = Buffer.from(String(seal.signature), "base64");
          const x = pub.toString("base64url");
          const key = createPublicKey({ key: { kty: "OKP", crv: "Ed25519", x }, format: "jwk" });
          const ok = cryptoVerify(null, msg, key, sig);
          verdict = ok ? "pass" : "fail";
          detail = ok ? "ok (verified with the public key recorded in the package)"
                      : "signature does not verify against the recorded public key";
        }
      } catch (err) {
        verdict = "fail";
        detail = "seal is not readable: " + err.message;
      }
      if (verdict === "inconclusive") {
        checks.push({ id: "S6", name: "seal signature", result: "INCONCLUSIVE", detail });
      } else {
        note("S6", "seal signature", verdict === "pass", detail);
      }
    }
  }

  // S14 strict base64. A canonical encoding admits exactly one string per
  // byte sequence; pad bits, missing padding and stray characters all decode
  // permissively, so two decoders can disagree about what was signed. Only
  // fields the package itself marks as base64 are examined -- a schema that
  // does not use base64 cannot be false-flagged.
  {
    const docOf = (rel) => {
      const p = join(pkg, rel);
      return existsSync(p) ? readJson(p) : null;
    };
    const manifestD = docOf("manifest.json");
    const identityD = docOf("identity.json");
    const lifecycleD = docOf("lifecycle.json");
    const indexD = docOf("evidence/index.json");
    const b64Fields = [];
    const walk = (node, path) => {
      if (Array.isArray(node)) {
        node.forEach((v, i) => walk(v, path + "[" + i + "]"));
      } else if (node && typeof node === "object") {
        for (const [k, v] of Object.entries(node)) {
          const child = path ? path + "/" + k : k;
          if (typeof v === "string" &&
              (k.endsWith("_b64") || k.endsWith("_base64") || k === "base64")) {
            b64Fields.push([child, v, k === "base64_url"]);
          } else {
            walk(v, child);
          }
        }
      }
    };
    for (const [name, doc] of [["manifest.json", manifestD], ["identity.json", identityD],
                               ["lifecycle.json", lifecycleD],
                               ["evidence/index.json", indexD]]) {
      if (doc) walk(doc, name);
    }
    if (b64Fields.length) {
      const problems = [];
      const STD = /^[A-Za-z0-9+/=]+$/, URL = /^[A-Za-z0-9-_=]+$/;
      for (const [field, value, urlsafe] of b64Fields) {
        const why = (() => {
          if (!value) return "empty";
          if (!(urlsafe ? URL : STD).test(value)) return "character outside the base64 alphabet";
          const core = value.replace(/=+$/, "");
          if (core.length % 4 === 1) return "length cannot be base64";
          if (!value.endsWith("=") && value.length % 4 !== 0) return "unpadded input";
          if (value.endsWith("=") && value.length % 4 !== 0) return "padded length is not a multiple of 4";
          const buf = Buffer.from(value, "base64");
          const back = buf.toString("base64");
          if (value.endsWith("=") && back !== value) return "non-canonical: pad bits are not zero";
          if (!urlsafe && value !== value.replace(/-/g, "+").replace(/_/g, "/")) return "urlsafe characters in standard base64";
          return null;
        })();
        if (why) problems.push(field + ": " + why);
      }
      note("S14", "strict base64", problems.length === 0,
           problems.length ? problems.slice(0, 4).join("; ")
                           : b64Fields.length + " declared base64 field(s) are canonical");
    }
  }

  // S10 attestation closure. Whether the six digests correspond to what
  // actually ran is NOT decidable from a package; this check asks only that
  // all six are declared and look like digests. Saying more would be the
  // overclaim this project refuses elsewhere.
  {
    const mp = join(pkg, "manifest.json");
    const m = existsSync(mp) ? readJson(mp) : null;
  if (m && m.closure !== undefined && m.closure !== null) {
    const CLOSURE_FIELDS = ["model_weights", "tokenizer", "chat_template",
                            "engine_build", "decoding", "numeric_env"];
    const SHA = /^(sha256:)?[0-9a-f]{64}$/;
    const closure = m.closure;
    const missing = [];
    if (typeof closure !== "object" || Array.isArray(closure)) {
      missing.push("closure is not an object");
    } else {
      for (const k of CLOSURE_FIELDS) {
        const v = closure[k];
        if (typeof v !== "string" || !SHA.test(v)) missing.push(k);
      }
    }
    note("S10", "attestation closure declared", missing.length === 0,
         missing.length ? "closure is incomplete or malformed: " + missing.join(", ")
                        : "all 6 closure components declared with digests " +
                          "(declaration only, contents are not verified)");
  }
  }

  // S13 Merkle inclusion (RFC 6962). A hash chain answers "was file N
  // changed?"; a Merkle tree answers "is this one file inside a set of size N
  // that the manifest committed to, without handing over all N files?" Runs
  // only when the package carries evidence/merkle.json -- a package with no
  // tree is not penalised for it.
  {
    const merklePath = join(pkg, "evidence", "merkle.json");
    if (existsSync(merklePath)) {
      const problems = [];
      const mdoc = readJson(merklePath);
      const idx = existsSync(join(pkg, "evidence/index.json"))
        ? readJson(join(pkg, "evidence/index.json")) : { entries: [] };
      const order = (idx.entries || []).slice().sort((a, b) =>
        String(a.path) < String(b.path) ? -1 : String(a.path) > String(b.path) ? 1 : 0);
      const leaves = [];
      for (const e of order) {
        try {
          leaves.push(leafHash(readFileSync(join(pkg, "evidence", String(e.path)))));
        } catch (err) {
          problems.push("cannot read evidence file " + JSON.stringify(e.path));
        }
      }
      const root = merkleRoot(leaves);
      if (mdoc.algorithm !== "rfc6962-sha256") {
        problems.push("algorithm " + JSON.stringify(mdoc.algorithm) + " is not rfc6962-sha256");
      }
      if (mdoc.size !== leaves.length) {
        problems.push("declared size " + JSON.stringify(mdoc.size) + " != " +
                      leaves.length + " evidence leaves");
      }
      if (String(mdoc.root || "").toLowerCase() !== root.toString("hex")) {
        problems.push("declared root does not match recomputed root");
      }
      const proofs = mdoc.proofs || [];
      for (const pr of proofs) {
        const p = String(pr.path);
        const at = order.findIndex((e) => String(e.path) === p);
        if (at < 0) {
          problems.push("proof names unknown evidence " + JSON.stringify(p));
          continue;
        }
        if (pr.index !== undefined && pr.index !== at) {
          problems.push("proof index for " + JSON.stringify(p) + " is " +
                        JSON.stringify(pr.index) + ", recomputed " + at);
        }
        const siblings = [];
        let bad = false;
        for (const h of (pr.proof || [])) {
          const hex = String(h);
          if (!/^[0-9a-fA-F]{64}$/.test(hex)) { bad = true; break; }
          siblings.push(Buffer.from(hex, "hex"));
        }
        if (bad) { problems.push("proof for " + JSON.stringify(p) + " has a non-hex sibling"); continue; }
        if (at >= leaves.length) {
          problems.push("proof names evidence " + JSON.stringify(p) + " whose file is absent");
          continue;
        }
        if (!verifyInclusion(leaves[at], at, leaves.length, siblings, root)) {
          problems.push("inclusion proof for " + JSON.stringify(p) + " does not verify");
        }
      }
      note("S13", "merkle inclusion proofs", problems.length === 0,
           problems.length ? problems.slice(0, 4).join("; ")
                           : "root " + root.toString("hex").slice(0, 16) +
                             "... over " + leaves.length + " leaves; " +
                             proofs.length + " inclusion proof(s) verified");
    }
  }

  // S8 package checkpoint head. One value committing to the WHOLE package
  // state: the lifecycle head, the evidence root, the index metadata digest and
  // the evidence count. A lifecycle-only head was not enough -- adding evidence
  // changes the root but leaves the log untouched, so two different states
  // shared one head. Truncation, rollback and post-seal replacement are what
  // this detects, and only inside this package; a rollback of the whole
  // store needs an observation made somewhere else (S9, not checkable here).
  {
    const mp = join(pkg, "manifest.json");
    const m = existsSync(mp) ? readJson(mp) : null;
    if (m && m.checkpoint_head !== undefined && m.checkpoint_head !== null) {
      const problems = [];
      let state = null;
      try {
        const idx = existsSync(join(pkg, "evidence/index.json"))
          ? readJson(join(pkg, "evidence/index.json")) : { entries: [] };
        const entries = idx.entries || [];
        const hs = [];
        for (const e of entries) {
          try { hs.push(sha256(readFileSync(join(pkg, "evidence", String(e.path))))); }
          catch { /* S4 reports the missing file; the count still stands */ }
        }
        const root = sha256(canonicalBytes(hs.slice().sort()));
        const meta = entries.map((e) => ({
          path: String(e.path || ""), type: e.type, note: e.note,
          action_digest: e.action_digest ?? null,
        }));
        meta.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
        const indexDigest = "sha256:" + sha256(canonicalBytes(meta));
        const lcPath = join(pkg, "lifecycle.json");
        const lc = existsSync(lcPath) ? readJson(lcPath) : {};
        const events = lc.events || [];
        const last = events.length ? events[events.length - 1] : null;
        const lcHead = "sha256:" + sha256(canonicalBytes({
          count: events.length,
          last_sequence_number: last ? (last.sequence_number ?? null) : null,
          last_event_digest: last ? sha256(canonicalBytes(last)) : null,
        }));
        state = "sha256:" + sha256(canonicalBytes({
          lifecycle_head: lcHead,
          evidence_root: root,
          evidence_index_digest: indexDigest,
          evidence_count: entries.length,
        }));
        if (state !== String(m.checkpoint_head)) {
          problems.push("state does not match the sealed checkpoint_head (manifest " +
                        String(m.checkpoint_head).slice(0, 20) + "..., disk " +
                        state.slice(0, 20) + "...) - state truncated, rolled back, " +
                        "or replaced after sealing");
        }
      } catch (err) {
        problems.push("state is not canonicalizable: " + err.message);
      }
      note("S8", "package checkpoint head", problems.length === 0,
           problems.length ? problems.slice(0, 2).join("; ")
                           : "checkpoint matches");
    }
  }

  // S12 timestamps, identifiers and the counts that must agree with them
  {
    const problems = [];
    try {
      const manifest = readJson(join(pkg, "manifest.json"));
      if (!realDate(manifest.created_at)) problems.push("manifest.created_at is not a real ISO-8601 Z time");
      if (!Number.isInteger(manifest.evidence_count)) problems.push("evidence_count is not an integer");
      const index = readJson(join(pkg, "evidence/index.json"));
      const n = (index.entries || []).length;
      if (Number.isInteger(manifest.evidence_count) && manifest.evidence_count !== n) {
        problems.push("evidence_count says " + manifest.evidence_count + ", index holds " + n);
      }
      const lc = readJson(join(pkg, "lifecycle.json"));
      const events = Array.isArray(lc) ? lc : (lc.events || []);
      let last = null;
      for (const ev of events) {
        const at = ev.at || ev.created_at || ev.timestamp;
        if (!realDate(at)) { problems.push("lifecycle event without a real time"); break; }
        if (last && Date.parse(at) < Date.parse(last)) {
          problems.push("lifecycle time goes backwards"); break;
        }
        last = at;
      }
    } catch (err) { problems.push(err.message); }
    note("S12", "timestamp and identifier strictness", problems.length === 0,
         problems.slice(0, 4).join("; ") || "ok");
  }

  const failed = checks.filter((c) => c.result === "FAIL").map((c) => c.id);
  return {
    result: failed.length ? "FAIL" : "INCONCLUSIVE",
    trust_level: failed.length ? "FAIL" : "INCONCLUSIVE",
    failed_checks: failed.length,
    checks,
    note: "structural verifier: signatures, Merkle proofs, external timestamps and " +
          "the receipt chain are not checked here, so a sound package is " +
          "INCONCLUSIVE rather than PASS",
    implementation: "verify-js (independent of uibc-core)",
  };
}

const target = process.argv[2];
if (!target) {
  console.error("usage: node tools/verify-js/verify.mjs <package-dir>");
  process.exit(2);
}
try {
  process.stdout.write(JSON.stringify(verify(target), null, 2) + "\n");
} catch (err) {
  process.stdout.write(JSON.stringify({
    result: "FAIL", trust_level: "FAIL", failed_checks: 1,
    checks: [{ id: "S0", name: "verifier robustness", result: "FAIL", detail: String(err.message) }],
    implementation: "verify-js",
  }, null, 2) + "\n");
}
