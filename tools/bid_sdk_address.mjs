// Derive a BID address with the OFFICIAL SDK (bid-sdk-nodejs, published by Caict),
// so the address the implementation ships can be recorded rather than only our
// own reading of the protocol.
//
//   npm i bid-sdk-nodejs long sjcl bignumber.js co-wrap-all
//   node tools/bid_sdk_address.mjs
//
// This records ONE address. Do not read it as "our rule reproduces the SDK":
// over 50 seeds (tools/bid_sdk_address_batch.mjs) a Bitcoin-alphabet base58 of
// sha256(pub)[10:] agrees with the SDK on only 7. The SDK's base58 codec is not
// Bitcoin's, so its addresses are verifiable by us but not re-derivable.
// tests/test_bid_address_rule.py states both halves.
//
// Requiring the package root pulls in its transaction layer (request-promise, a
// deprecated stack, and on-chain calls we do not make here); the keypair module
// loads alone and is the part that derives an address.
//
// The seed is fixed on purpose: the recorded output lives in
// fixtures/bid/sdk_address.json and must reproduce byte for byte.

import crypto from "node:crypto";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const keypair = require("bid-sdk-nodejs/lib/keypair");

const SEED = Buffer.from(Array.from({ length: 32 }, (_, i) => i));   // 00 01 .. 1f

const PKCS8_PREFIX = Buffer.from("302e020100300506032b657004220420", "hex");
const privateKey = crypto.createPrivateKey({
  key: Buffer.concat([PKCS8_PREFIX, SEED]),
  format: "der",
  type: "pkcs8",
});
const publicKey = crypto.createPublicKey(privateKey);

const out = keypair.generate({
  privateKey: privateKey.export({ format: "jwk" }),
  publicKey: publicKey.export({ format: "jwk" }),
});

if (out.errorCode !== 0) {
  console.error(JSON.stringify(out));
  process.exit(1);
}
const { encPublicKey, address } = out.result;
console.log(JSON.stringify({ encPublicKey, address }, null, 2));
