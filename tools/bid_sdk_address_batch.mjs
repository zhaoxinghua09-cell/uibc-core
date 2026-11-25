// Ask the OFFICIAL SDK (bid-sdk-nodejs 1.0.1) to derive addresses for a batch of
// deterministic seeds. Used as a property fixture: our validator must never
// reject anything the official implementation produces.
//
//   npm i bid-sdk-nodejs long sjcl bignumber.js co-wrap-all
//   node tools/bid_sdk_address_batch.mjs > fixtures/bid/sdk_address_batch.json
//
// Seeds are fixed (00..1f, then 41 increments modulo 256), so the recorded
// output is reproducible byte for byte.

import crypto from "node:crypto";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const keypair = require("bid-sdk-nodejs/lib/keypair");

const PKCS8 = Buffer.from("302e020100300506032b657004220420", "hex");

function seedAt(i) {
  // i=0..49 -> byte0=i, byte1=0x5a, rest a fixed ramp: distinct, reproducible
  const buf = Buffer.alloc(32);
  for (let k = 0; k < 32; k++) buf[k] = (i + k * 7) % 256;
  buf[1] = 0x5a;
  return buf;
}

const out = [];
for (let i = 0; i < 50; i++) {
  const seed = seedAt(i);
  const priv = crypto.createPrivateKey({
    key: Buffer.concat([PKCS8, seed]),
    format: "der",
    type: "pkcs8",
  });
  const pub = crypto.createPublicKey(priv);
  const res = keypair.generate({
    privateKey: priv.export({ format: "jwk" }),
    publicKey: pub.export({ format: "jwk" }),
  });
  if (res.errorCode !== 0) {
    console.error(`seed ${i}: ${JSON.stringify(res)}`);
    process.exit(1);
  }
  out.push({
    seed_hex: seed.toString("hex"),
    encPublicKey: res.result.encPublicKey,
    address: res.result.address,
  });
}
console.log(JSON.stringify(out, null, 1));
