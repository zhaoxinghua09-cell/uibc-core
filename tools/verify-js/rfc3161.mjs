// RFC 3161 timestamp tokens, verified with nothing but Node's own crypto.
//
// A timestamp token is the one witness this project cannot mint for itself: the
// signature is made with a key held by somebody else. Verifying it therefore
// requires understanding the token's structure, and that structure is ASN.1.
// There are no npm packages here on purpose - an independent verifier that
// borrows the first implementation's dependencies is not independent - so this
// file carries a minimal DER reader: enough to reach the bytes that are signed
// and the bytes that sign them, and deliberately nothing more.
//
// What it checks, and what it refuses to claim:
//
//   * the response reports `granted`;
//   * the token's messageImprint is the digest of the data being anchored;
//   * every signed attribute is covered by the signature (the signed set is
//     re-encoded as SEQUENCE, which is what RFC 5652 requires and is the
//     classic place where a naive verifier checks the wrong bytes);
//   * `messageDigest` in those attributes equals the digest of the encapsulated
//     TSTInfo;
//   * the signature verifies against a certificate named by `signingCertificate`;
//   * that certificate was issued by one of the supplied CAs and is inside its
//     validity window.
//
// It does not check revocation, policy OIDs, or that the CA is "trusted" in any
// global sense - those are trust-store questions, and a verifier that answers
// them silently is lying about what it did.

import { createHash, verify as cryptoVerify, X509Certificate } from "node:crypto";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export const OID_CONTENT_TYPE = "1.2.840.113549.1.9.3";
export const OID_MESSAGE_DIGEST = "1.2.840.113549.1.9.4";
export const OID_SIGNING_TIME = "1.2.840.113549.1.9.5";
export const OID_SIGNING_CERT = "1.2.840.113549.1.9.16.2.12";

const TAG = {
  SEQUENCE: 0x30, SET: 0x31, INTEGER: 0x02, OID: 0x06, OCTET: 0x04,
  UTCTIME: 0x17, GENTIME: 0x18, EXPLICIT0: 0xa0, BITSTRING: 0x03,
  NULL: 0x05, SEQ_WRAP: 0x30,
};

export function readTlv(buf, off, limit = buf.length) {
  if (off >= limit) throw new Error("DER: read past the end of the buffer");
  const tag = buf[off];
  let i = off + 1;
  if (i >= limit) throw new Error("DER: truncated length");
  const first = buf[i];
  i += 1;
  let len;
  if (first < 0x80) {
    len = first;
  } else {
    const n = first & 0x7f;
    if (n === 0) throw new Error("DER: indefinite length is not allowed in DER");
    if (n > 4) throw new Error("DER: length field larger than 4 bytes");
    if (i + n > limit) throw new Error("DER: truncated long-form length");
    len = 0;
    for (let k = 0; k < n; k += 1) {
      len = (len << 8) | buf[i];
      i += 1;
    }
  }
  const contentStart = i;
  const contentEnd = i + len;
  if (contentEnd > limit) throw new Error("DER: content runs past its parent");
  return { tag, contentStart, contentEnd, end: contentEnd, headerStart: off };
}

export function children(buf, start, end) {
  const out = [];
  let i = start;
  while (i < end) {
    const tlv = readTlv(buf, i, end);
    out.push(tlv);
    i = tlv.end;
  }
  return out;
}

export function decodeOid(buf, start, end) {
  if (end <= start) throw new Error("OID: empty");
  const parts = [Math.floor(buf[start] / 40), buf[start] % 40];
  let value = 0;
  for (let i = start + 1; i < end; i += 1) {
    value = (value << 7) | (buf[i] & 0x7f);
    if ((buf[i] & 0x80) === 0) {
      parts.push(value);
      value = 0;
    }
  }
  return parts.join(".");
}

const hex = (b) => Buffer.from(b).toString("hex");
const sha = (alg, b) => createHash(alg).update(b).digest("hex");

function timeOf(tlv, buf) {
  const raw = buf.slice(tlv.contentStart, tlv.contentEnd).toString("ascii");
  return raw.endsWith("Z") ? raw : raw + "Z";
}

export function parseTstInfo(der) {
  const outer = readTlv(der, 0);
  if (outer.tag !== TAG.SEQUENCE) throw new Error("TSTInfo is not a SEQUENCE");
  const fields = children(der, outer.contentStart, outer.contentEnd);
  if (fields.length < 5) throw new Error("TSTInfo has fewer fields than RFC 3161 requires");
  const [version, policy, messageImprint, serial, genTime] = fields;
  if (version.tag !== TAG.INTEGER) throw new Error("TSTInfo version is not an INTEGER");
  if (policy.tag !== TAG.OID) throw new Error("TSTInfo policy is not an OID");
  if (messageImprint.tag !== TAG.SEQUENCE) throw new Error("TSTInfo messageImprint is not a SEQUENCE");
  const imprint = children(der, messageImprint.contentStart, messageImprint.contentEnd);
  if (imprint.length < 2) throw new Error("TSTInfo messageImprint has fewer than two fields");
  const hashAlg = imprint[0];
  const hashedMessage = imprint[1];
  const algParts = children(der, hashAlg.contentStart, hashAlg.contentEnd);
  if (!algParts.length || algParts[0].tag !== TAG.OID) throw new Error("TSTInfo hash algorithm is not an OID");
  if (hashedMessage.tag !== TAG.OCTET) throw new Error("TSTInfo hashedMessage is not an OCTET STRING");
  if (genTime.tag !== TAG.GENTIME && genTime.tag !== TAG.UTCTIME) throw new Error("TSTInfo genTime is not a time");
  return {
    version: der[version.contentStart],
    policy: decodeOid(der, policy.contentStart, policy.contentEnd),
    hashAlgorithm: decodeOid(der, algParts[0].contentStart, algParts[0].contentEnd),
    hashedMessage: hex(der.slice(hashedMessage.contentStart, hashedMessage.contentEnd)),
    serial: hex(der.slice(serial.contentStart, serial.contentEnd)).replace(/^0+/, "") || "0",
    genTime: timeOf(genTime, der),
  };
}

// The digest algorithm in SignerInfo is an OID; Node wants a name.
const DIGEST_NAMES = {
  "1.3.14.3.2.26": "sha1",
  "2.16.840.1.101.3.4.2.1": "sha256",
  "2.16.840.1.101.3.4.2.2": "sha384",
  "2.16.840.1.101.3.4.2.3": "sha512",
};

export function verifyToken(tsrBytes, expectedDigestHex, caPem) {
  const problems = [];
  const info = {};
  let ok = false;
  try {
    const buf = Buffer.isBuffer(tsrBytes) ? tsrBytes : Buffer.from(tsrBytes);
    const outer = readTlv(buf, 0);
    if (outer.tag !== TAG.SEQUENCE) throw new Error("response is not a TimeStampResp SEQUENCE");
    const top = children(buf, outer.contentStart, outer.contentEnd);
    if (top.length < 2) throw new Error("response carries no token");

    // status ::= PKIStatusInfo { status INTEGER, ... }
    const statusFields = children(buf, top[0].contentStart, top[0].contentEnd);
    const status = statusFields.length ? buf[statusFields[0].contentStart] : -1;
    if (status !== 0 && status !== 1) {
      problems.push("TSA refused: status " + status);
      return { ok: false, info, problems };
    }
    info.status = status === 0 ? "granted" : "granted_with_mods";

    const contentInfo = top[1];
    const ciFields = children(buf, contentInfo.contentStart, contentInfo.contentEnd);
    if (!ciFields.length || ciFields[0].tag !== TAG.OID) throw new Error("ContentInfo has no contentType");
    const contentType = decodeOid(buf, ciFields[0].contentStart, ciFields[0].contentEnd);
    if (contentType !== "1.2.840.113549.1.7.2") throw new Error("token is not signedData (" + contentType + ")");
    const wrapped = ciFields[1];
    if (!wrapped || wrapped.tag !== TAG.EXPLICIT0) throw new Error("ContentInfo has no signedData");

    const signedData = children(buf, wrapped.contentStart, wrapped.contentEnd)[0];
    const sd = children(buf, signedData.contentStart, signedData.contentEnd);
    if (sd.length < 4) throw new Error("SignedData has fewer fields than RFC 5652 requires");
    const encap = sd[2];
    const certs = sd[3];
    const signerInfos = sd[sd.length - 1];
    if (certs.tag !== TAG.EXPLICIT0) throw new Error("SignedData carries no certificates");

    const encapFields = children(buf, encap.contentStart, encap.contentEnd);
    const eContentWrap = encapFields[1];
    if (!eContentWrap || eContentWrap.tag !== TAG.EXPLICIT0) throw new Error("token carries no encapsulated content");
    const eContentOctets = children(buf, eContentWrap.contentStart, eContentWrap.contentEnd)[0];
    if (eContentOctets.tag !== TAG.OCTET) throw new Error("eContent is not an OCTET STRING");
    const tstDer = buf.slice(eContentOctets.contentStart, eContentOctets.contentEnd);
    const tst = parseTstInfo(tstDer);

    info.version = tst.version;
    info.policy = tst.policy;
    info.serial = tst.serial;
    info.gen_time = tst.genTime;
    info.digest_hex = tst.hashedMessage;

    if (tst.hashAlgorithm !== "2.16.840.1.101.3.4.2.1") {
      problems.push("messageImprint uses " + tst.hashAlgorithm + ", not SHA-256");
    }
    if (expectedDigestHex && tst.hashedMessage !== expectedDigestHex) {
      problems.push("messageImprint is " + tst.hashedMessage.slice(0, 16) +
                    "..., but the anchored data hashes to " + expectedDigestHex.slice(0, 16) + "...");
    }

    const signerList = children(buf, signerInfos.contentStart, signerInfos.contentEnd);
    if (!signerList.length) throw new Error("SignedData carries no SignerInfo");
    const si = signerList[0];
    const siFields = children(buf, si.contentStart, si.contentEnd);

    let signedAttrsTlv = null;
    let digestAlgName = null;
    let signature = null;
    let signingCertHash = null;
    let signingCertHashAlg = null;
    let messageDigest = null;

    // SignerInfo order is fixed by RFC 5652: version, sid, digestAlgorithm,
    // [0] signedAttrs, signatureAlgorithm, signature [, unsignedAttrs]. Reading
    // it in order is safer than hunting for shapes, because a hostile token can
    // carry a SEQUENCE anywhere it likes.
    if (siFields.length < 5) throw new Error("SignerInfo has fewer fields than RFC 5652 requires");
    const digestAlgTlv = siFields[2];
    if (digestAlgTlv.tag !== TAG.SEQUENCE) throw new Error("SignerInfo digestAlgorithm is not a SEQUENCE");
    const digestParts = children(buf, digestAlgTlv.contentStart, digestAlgTlv.contentEnd);
    if (!digestParts.length || digestParts[0].tag !== TAG.OID) throw new Error("SignerInfo digestAlgorithm has no OID");
    digestAlgName = DIGEST_NAMES[decodeOid(buf, digestParts[0].contentStart, digestParts[0].contentEnd)] || null;
    if (siFields[3].tag === TAG.EXPLICIT0) signedAttrsTlv = siFields[3];
    for (const f of siFields) {
      if (f.tag === TAG.OCTET) signature = buf.slice(f.contentStart, f.contentEnd);
    }
    if (!signedAttrsTlv) throw new Error("SignerInfo has no signed attributes");
    if (!digestAlgName) throw new Error("SignerInfo names a digest algorithm Node cannot verify");
    if (!signature) throw new Error("SignerInfo has no signature");

    for (const attr of children(buf, signedAttrsTlv.contentStart, signedAttrsTlv.contentEnd)) {
      const parts = children(buf, attr.contentStart, attr.contentEnd);
      if (!parts.length) continue;
      const oid = decodeOid(buf, parts[0].contentStart, parts[0].contentEnd);
      const values = children(buf, parts[1].contentStart, parts[1].contentEnd);
      if (!values.length) continue;
      if (oid === OID_MESSAGE_DIGEST) {
        messageDigest = hex(buf.slice(values[0].contentStart, values[0].contentEnd));
      } else if (oid === OID_SIGNING_CERT) {
        // SigningCertificate { certs SEQUENCE OF ESSCertID { certHash OCTET } }
        // SigningCertificate ::= SEQUENCE OF ESSCertID; ESSCertID ::= SEQUENCE
        // { certHash OCTET STRING, issuerSerial OPTIONAL }. Depth varies between
        // implementations (the SET wrapper and the SEQUENCE OF are both there),
        // so descend to the first OCTET STRING rather than assume a nesting
        // level -- the first octet in this subtree is always the cert hash,
        // because issuerSerial holds no octets of its own.
        const findOctet = (cs, ce) => {
          for (const k of children(buf, cs, ce)) {
            if (k.tag === TAG.OCTET) return k;
            if (k.tag === TAG.SEQUENCE || k.tag === TAG.SET ||
                k.tag === TAG.EXPLICIT0) {
              const hit = findOctet(k.contentStart, k.contentEnd);
              if (hit) return hit;
            }
          }
          return null;
        };
        const certHashTlv = findOctet(values[0].contentStart, values[0].contentEnd);
        if (!certHashTlv) throw new Error("signingCertificate carries no cert hash");
        const h = hex(buf.slice(certHashTlv.contentStart, certHashTlv.contentEnd));
        signingCertHash = h;
        signingCertHashAlg = h.length === 40 ? "sha1" : h.length === 64 ? "sha256" : null;
        if (!signingCertHashAlg) throw new Error("signingCertificate hash is neither SHA-1 nor SHA-256");
      }
    }

    if (!messageDigest) {
      problems.push("signed attributes carry no messageDigest - the signature covers no statement about the content");
    } else {
      const contentDigest = sha(digestAlgName, tstDer);
      if (messageDigest !== contentDigest) {
        problems.push("messageDigest is " + messageDigest.slice(0, 16) +
                      "..., but the token content hashes to " + contentDigest.slice(0, 16) + "...");
      }
    }

    // The signed bytes are the attribute set re-tagged as SET OF (0x31). This
    // is the trap that catches most first attempts: the element sits in the
    // token as [0] IMPLICIT (0xA0), while RFC 5652 signs its DER encoding as
    // `SET OF Attribute` - same length, different tag. Getting this wrong gives
    // a well-formed signature check that simply fails, with no clue why.
    const signedBytes = Buffer.from(buf.slice(signedAttrsTlv.headerStart, signedAttrsTlv.end));
    signedBytes[0] = TAG.SET;

    const candidateCerts = children(buf, certs.contentStart, certs.contentEnd).map((tlv) => ({
      tlv,
      der: buf.slice(tlv.headerStart, tlv.end),
    }));

    let signerCert = null;
    if (signingCertHash) {
      for (const c of candidateCerts) {
        if (sha(signingCertHashAlg, c.der) === signingCertHash) {
          signerCert = c;
          break;
        }
      }
      if (!signerCert) problems.push("signingCertificate names a certificate this token does not carry");
    } else if (candidateCerts.length === 1) {
      signerCert = candidateCerts[0];
    } else {
      problems.push("token carries several certificates and no signingCertificate attribute to choose between them");
    }

    if (signerCert) {
      let cert;
      try {
        cert = new X509Certificate(signerCert.der);
      } catch (e) {
        throw new Error("the signing certificate cannot be parsed: " + e.message);
      }
      info.tsa = { subject: cert.subject.replace(/\n/g, ", "), serial: cert.serialNumber };
      const signatureOk = cryptoVerify(digestAlgName, signedBytes, cert.publicKey, signature);
      if (!signatureOk) problems.push("the CMS signature does not verify against the signing certificate");

      const now = new Date();
      if (now < cert.validFromDate || now > cert.validToDate) {
        problems.push("the signing certificate is not valid at verification time (valid " +
                      cert.validFromDate.toISOString() + " to " + cert.validToDate.toISOString() + ")");
      }

      // Issued by one of the supplied CAs? Anything else is an unsigned claim
      // about who signed, which is exactly what a timestamp must not be.
      if (!caPem) {
        problems.push("no CA bundle supplied, so the signing certificate's issuer is unproven");
      } else {
        const caText = Buffer.isBuffer(caPem) ? caPem.toString("utf8") : String(caPem);
        const pems = caText.match(/-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----/g) || [];
        if (!pems.length) problems.push("the CA bundle contains no certificate");
        let chained = false;
        for (const pem of pems) {
          try {
            const ca = new X509Certificate(pem);
            if (cert.checkIssued(ca) && cert.verify(ca.publicKey)) {
              chained = true;
              info.ca = ca.subject.replace(/\n/g, ", ");
              break;
            }
          } catch { /* a bundle entry that cannot be read proves nothing */ }
        }
        if (!chained) problems.push("the signing certificate was not issued by any supplied CA");
      }
    }

    ok = problems.length === 0;
  } catch (err) {
    problems.push("token cannot be read: " + err.message);
    ok = false;
  }
  return { ok, info, problems };
}

// A command-line entry point, so the token check can be reproduced by anyone
// with Node and this file - no package, no install, no Python:
//
//   node tools/verify-js/rfc3161.mjs <token.tsr> <expected-digest-hex> <ca.pem>
//
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [tsrPath, digestHex, caPath] = process.argv.slice(2);
  if (!tsrPath || !digestHex) {
    console.error("usage: node tools/verify-js/rfc3161.mjs <token.tsr> <digest-hex> <ca.pem>");
    process.exit(2);
  }
  let r;
  try {
    const token = readFileSync(tsrPath);
    const ca = caPath ? readFileSync(caPath) : "";
    r = verifyToken(token, digestHex, ca);
  } catch (err) {
    // A missing or unreadable input is a refusal with a reason, not a crash:
    // a verifier that throws tells the caller nothing about what it found.
    r = { ok: false, info: {}, problems: ["cannot read an input: " + err.message] };
  }
  process.stdout.write(JSON.stringify(r, null, 2) + "\n");
  process.exit(r.ok ? 0 : 1);
}
