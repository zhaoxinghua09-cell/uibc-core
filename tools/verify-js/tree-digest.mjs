// A second implementation of the tree digest, in a second language.
//
// `tools/outsider_rerun.py` produces two numbers that a receipt leans on:
//
//   tree_sha256    sha256 over the lines "<path>:<sha256 of the file bytes>",
//                  in path order, excluding the two files the tool writes
//   content_sha256 sha256 over the sorted per-file content digests, paths left out
//
// Those numbers are meant to be evidence. Evidence that only one program can
// produce is a program's opinion, so this file recomputes both with nothing but
// Node's standard library: no Python, no npm package, no shared code, and no
// import of the implementation it is checking.
//
// Usage:  node tools/verify-js/tree-digest.mjs --root <dir> --files-from <nul-separated list>
//         node tools/verify-js/tree-digest.mjs --root <dir>          (walks the tree itself)
//
// It prints one JSON line: {"files": n, "tree_sha256": "...", "content_sha256": "..."}

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const IGNORE_DIRS = new Set([
  ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
  "node_modules", ".venv", "venv", "htmlcov", ".tox", ".nox",
]);
const IGNORE_FILES = new Set([".coverage", "coverage.xml"]);
const GENERATED = new Set(["docs/OUTSIDER-RERUN.md", "docs/outsider-rerun-receipt.json"]);

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : process.argv[i + 1];
}

function walk(root) {
  const out = [];
  const visit = (dir, prefix) => {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      if (ent.isDirectory()) {
        if (IGNORE_DIRS.has(ent.name)) continue;
        visit(path.join(dir, ent.name), prefix ? `${prefix}/${ent.name}` : ent.name);
      } else if (ent.isFile()) {
        const rel = prefix ? `${prefix}/${ent.name}` : ent.name;
        if (/\.(pyc|pyo)$/.test(ent.name) || IGNORE_FILES.has(ent.name)) continue;
        out.push(rel);
      }
    }
  };
  visit(root, "");
  return out;
}

function listed() {
  const file = arg("--files-from");
  if (!file) return null;
  const raw = fs.readFileSync(file, "utf8");
  return raw.split("\0").filter((s) => s.length > 0);
}

// Byte order, not UTF-16 code-unit order: UTF-8 keeps codepoint order, and the
// Python side sorts strings, so comparing the encoded bytes is what agrees with
// it on every path - including the ones with astral characters, where JavaScript's
// default string comparison would not.
function byBytes(a, b) {
  return Buffer.compare(Buffer.from(a, "utf8"), Buffer.from(b, "utf8"));
}

const root = arg("--root");
if (!root) {
  console.error("need --root");
  process.exit(64);
}

const files = (listed() || walk(root)).slice().sort(byBytes);
const entries = [];
const contents = [];
for (const rel of files) {
  if (GENERATED.has(rel)) continue;
  const abs = path.join(root, ...rel.split("/"));
  let hex;
  try {
    hex = crypto.createHash("sha256").update(fs.readFileSync(abs)).digest("hex");
  } catch {
    hex = "unreadable";
  }
  entries.push(`${rel}:${hex}`);
  contents.push(hex);
}

const tree = crypto.createHash("sha256").update(entries.join("\n"), "utf8").digest("hex");
const sortedContents = contents.slice().sort(byBytes);
const content = crypto.createHash("sha256").update(sortedContents.join("\n"), "utf8").digest("hex");

process.stdout.write(JSON.stringify({
  files: entries.length,
  tree_sha256: tree,
  content_sha256: content,
}) + "\n");
